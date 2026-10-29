"""Version 1.9.131 (Stufe 5, R2 Nachrunde, Punkt 2) -- Storno zurücknehmen: nur Admin, mit Pflichtbegründung, zurück auf „läuft“, im Verlauf.

Bis 1.9.130 blieb ein stornierter Auftrag storniert (Festlegung 1.9.124 Nr. 1, nicht bestätigt): ein versehentlicher Storno sperrte Auftrag und
Angebot für immer. Jetzt nimmt der Admin ihn zurück (app/auftragsstatus.py::storno_zuruecknehmen(), POST /api/orders/{id}/storno-zuruecknehmen):
Büro 403, ohne Begründung 422, an einem Auftrag, der nicht storniert ist, 409; danach läuft der Auftrag, der Wechsel steht im Verlauf mit der
Begründung. Der allgemeine Weg (POST /api/orders/{id}/status) führt weiter nicht aus „storniert“ heraus (409).
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import OrderStatusChange
from app.routers import projects as projects_router
from app.routers.pages import router as pages_router
from tests.node_lauf import node_ausfuehren
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v544_auftragsstatus import ROUTER, _bericht, _buero, _frisch, _status
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)

VORLAGEN = Path(__file__).resolve().parents[1] / "app" / "templates"


def _zurueck(client, order_id, reason=...):
    return client.post(f"/api/orders/{order_id}/storno-zuruecknehmen", json={} if reason is ... else {"reason": reason})


def _admin(w):
    return w["client"](w["db"], *ROUTER, projects_router.router, role="admin")


@pytest.mark.parametrize("rolle", ["buero_auftrag", "buero_finanzen"])
def test_buero_403(welt, rolle):  # noqa: F811
    client = _buero(welt, role=rolle)
    assert _status(client, welt["order"].id, "storniert", "Kunde hat abgesagt").status_code == 200
    antwort = _zurueck(client, welt["order"].id, "versehentlich storniert")
    assert antwort.status_code == 403 and antwort.json()["detail"] == "Einen Storno nimmt nur der Admin zurück."
    assert _frisch(welt).status == "storniert"


@pytest.mark.parametrize("reason", [..., None, "", "   "])
def test_admin_ohne_begruendung_422(welt, reason):  # noqa: F811
    client = _admin(welt)
    assert _status(client, welt["order"].id, "storniert", "Kunde hat abgesagt").status_code == 200
    assert _zurueck(client, welt["order"].id, reason).status_code == 422
    assert _frisch(welt).status == "storniert"


def test_admin_mit_begruendung_laeuft_wieder_und_im_verlauf(welt):  # noqa: F811
    """Mit Begründung 200: der Auftrag läuft, die Historie hält storniert -> läuft mit Begründung fest, der Verlauf zeigt die Zeile; danach
    geht wieder, was der Storno sperrte (neuer Bericht)."""
    db, order = welt["db"], welt["order"]
    client = _admin(welt)
    assert _status(client, order.id, "storniert", "Kunde hat abgesagt").status_code == 200
    assert _bericht(client, welt).status_code == 409
    info = client.get(f"/api/orders/{order.id}").json()["status_info"]
    assert info["storno_zuruecknehmen"] is True and info["aktionen"] == []
    antwort = _zurueck(client, order.id, "  Versehentlich storniert, Kunde hat bestätigt  ")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["status"] == "laeuft" and daten["status_info"]["storno_zuruecknehmen"] is False
    assert [a["ziel"] for a in daten["status_info"]["aktionen"]] == ["pausiert", "abgeschlossen", "storniert"]
    letzter = daten["status_info"]["letzter_wechsel"]
    assert (letzter["old_status"], letzter["new_status"], letzter["action"], letzter["reason"]) == (
        "storniert", "laeuft", "Storno zurücknehmen", "Versehentlich storniert, Kunde hat bestätigt")
    zeile = db.scalars(select(OrderStatusChange).where(OrderStatusChange.order_id == order.id).order_by(OrderStatusChange.id.desc())).first()
    assert (zeile.old_status, zeile.new_status, zeile.without_invoice) == ("storniert", "laeuft", False) and zeile.changed_by_name
    historie = client.get(f"/api/orders/{order.id}/status-changes").json()
    assert [h["action"] for h in historie] == ["Stornieren", "Storno zurücknehmen"]
    strom = client.get(f"/api/projects/{order.project_id}/verlauf", params={"art": "status"}).json()["eintraege"]
    assert strom[0]["titel"].endswith("storniert → läuft") and strom[0]["unterzeile"] == "Begründung: Versehentlich storniert, Kunde hat bestätigt"
    assert _bericht(client, welt).status_code == 200
    assert _frisch(welt).status == "laeuft"


def test_nicht_storniert_409_und_status_weg_bleibt_zu(welt):  # noqa: F811
    """Storno zurücknehmen an einem laufenden oder pausierten Auftrag 409; der allgemeine Weg führt weiter nicht aus „storniert“ heraus (409, mit
    dem Hinweis auf „Storno zurücknehmen“)."""
    client = _admin(welt)
    antwort = _zurueck(client, welt["order"].id, "doch")
    assert antwort.status_code == 409 and "nicht storniert" in antwort.json()["detail"]
    assert _status(client, welt["order"].id, "pausiert", "Gerüst fehlt").status_code == 200
    assert _zurueck(client, welt["order"].id, "doch").status_code == 409
    assert _status(client, welt["order"].id, "storniert", "Kunde hat abgesagt").status_code == 200
    antwort = _status(client, welt["order"].id, "laeuft", "doch")
    assert antwort.status_code == 409 and "Storno zurücknehmen" in antwort.json()["detail"]
    assert _zurueck(client, 987654, "doch").status_code == 404


@pytest.mark.parametrize("rolle,sichtbar", [("admin", True), ("buero_finanzen", False), ("buero_auftrag", False)])
def test_eintrag_nur_fuer_den_admin(threaded_db_session, router_test_client, rolle, sichtbar):
    text = router_test_client(threaded_db_session, pages_router, role=rolle).get("/projects/1").text
    eintrag = '<button type="button" class="ds-menue-eintrag" data-klick="stornoZuruecknehmen" hidden>Storno zurücknehmen …</button>'
    assert (eintrag in text) is sichtbar


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_eintrag_nur_solange_storniert():
    """auftragsstatusZeigen(): der Eintrag „Storno zurücknehmen …“ sichtbar genau, solange status_info.storno_zuruecknehmen gilt."""
    skripte = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_auftragsstatus.html").read_text(encoding="utf-8"), flags=re.S))
    berlin = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_berlin_date.html").read_text(encoding="utf-8"), flags=re.S))
    kennzeichen = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_statuskennzeichen.html").read_text(encoding="utf-8"), flags=re.S))
    ablauf = """
      const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
      const zurueck = [{dataset: {}, hidden: true}];
      var document = {querySelectorAll: s => s === '[data-klick="stornoZuruecknehmen"]' ? zurueck : [], getElementById: () => null};
    """ + kennzeichen + berlin + skripte + """
      auftragsstatusZeigen({status: 'storniert', status_info: {aktionen: [], storno_zuruecknehmen: true}});
      const a = zurueck[0].hidden;
      auftragsstatusZeigen({status: 'laeuft', status_info: {aktionen: [{ziel: 'pausiert'}], storno_zuruecknehmen: false}});
      console.log(JSON.stringify([a, zurueck[0].hidden]));
    """
    assert node_ausfuehren(ablauf, "Europe/Berlin") == [False, True]
