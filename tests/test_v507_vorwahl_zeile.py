"""Seit 1.9.86 (Stufe 4, R5, Teil 1 Punkt 1): „Meine Zeiten“ nennt die Vorwahl eines Auftrags außerhalb der Liste beim Namen.

    Server     GET /api/field-view/meine-zeiten?vorwahl=<id>: "vorwahl" = die Zeile des Auftrags (auftrag_zeile(): Id, Nummer, Titel,
               Objekt, Kunde, Adresse) und "geschlossen" (abgeschlossen/storniert/null) -- nur bei Zugang (Monteurin: field_may_access_order(),
               Büro immer); fremd oder unbekannt: null, kein Fehler
    Seite      vorwahlText(): „<Zeile> (Auftrag abgeschlossen)“ bzw. „(nicht in der Auswahl)“ in „Zeit nachtragen“ und „Nachtrag für die
               Kolonne“; ohne Zeile wie bis 1.9.85 die Nummer
Die Bedienung prüft scripts/klicktest_zeiten_abgeschlossen.py (Bild 2).
"""

import re
from datetime import timedelta

from app.routers import field_view as field_view_router
from app.time_tracking import auftrag_geschlossen
from tests import vorlagen_js as vj
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _als, _einsatz, welt  # noqa: F401  (Fixture)

ZEILE = {"id", "order_number", "title", "property_name", "customer_name", "property_address", "geschlossen"}


def _vorwahl(client, order_id):
    antwort = client.get("/api/field-view/meine-zeiten", params={"vorwahl": order_id})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["vorwahl"]


def _auftrag(w, nummer, status=None, titel=None):
    order = beauftragen(w["db"], make_quote(w["db"], is_consumer=False, number=nummer))
    if status:
        order.status = status
    order.title = titel or f"Auftrag {nummer}"
    w["db"].commit()
    return order


def test_geschlossen_als_wort():
    for status, soll in (("abgeschlossen", "abgeschlossen"), (" Storniert ", "storniert"), ("beauftragt", None), (None, None), ("", None)):
        assert auftrag_geschlossen(status) == soll, status


def test_vorwahl_mit_zugang_auch_ausserhalb_der_liste(welt):  # noqa: F811
    """Angriff: abgeschlossen (eingeplant) und offen, aber vor 40 Tagen eingeplant (nicht in ihrer Liste) -> die Zeile mit
    „geschlossen“; der Auftrag ihrer Liste ebenso (die Seite nimmt dann die Liste)."""
    zu = _auftrag(welt, "0507a", "abgeschlossen", "Flachdach Halle")
    alt = _auftrag(welt, "0507b", None, "Altauftrag")
    _einsatz(welt, zu, [(welt["gestern"], welt["gestern"])], [welt["mia"]])
    _einsatz(welt, alt, [(welt["heute"] - timedelta(days=40), welt["heute"] - timedelta(days=40))], [welt["mia"]])
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"]])
    mia = _als(welt, welt["mia"])
    z = _vorwahl(mia, zu.id)
    assert set(z) == ZEILE and (z["id"], z["order_number"], z["title"], z["geschlossen"]) == (zu.id, zu.order_number, "Flachdach Halle", "abgeschlossen")
    a = _vorwahl(mia, alt.id)
    assert (a["id"], a["title"], a["geschlossen"]) == (alt.id, "Altauftrag", None)
    assert alt.id not in [o["id"] for o in mia.get("/api/field-view/meine-zeiten").json()["auftraege"]]
    assert _vorwahl(mia, welt["order"].id)["id"] == welt["order"].id


def test_ohne_zugang_oder_unbekannt_null(welt):  # noqa: F811
    """Angriff: ein fremder Auftrag (nie zugeordnet, kein Bericht) und eine unbekannte Id -> null, kein Fehler, nichts über den Auftrag;
    ohne vorwahl ist der Schlüssel null."""
    fremd = _auftrag(welt, "0507c", None, "Geheimauftrag")
    mia = _als(welt, welt["mia"])
    assert _vorwahl(mia, fremd.id) is None
    assert _vorwahl(mia, 999999) is None
    antwort = mia.get("/api/field-view/meine-zeiten")
    assert antwort.json()["vorwahl"] is None
    assert "Geheimauftrag" not in mia.get("/api/field-view/meine-zeiten", params={"vorwahl": fremd.id}).text
    assert mia.get("/api/field-view/meine-zeiten", params={"vorwahl": 0}).status_code == 422


def test_buero_sieht_jede_vorwahl(welt):  # noqa: F811
    fremd = _auftrag(welt, "0507d", "storniert", "Stornoauftrag")
    bea = make_employee(welt["db"], "B-507", "Bea", "Büro")
    buero = welt["client"](welt["db"], field_view_router.router, role="buero_auftrag", employee_id=bea.id)
    z = _vorwahl(buero, fremd.id)
    assert (z["id"], z["geschlossen"]) == (fremd.id, "storniert")


def test_seite_nennt_die_vorwahl_beim_namen():
    text = vj.seitentext("mobil_zeiten.html")[0]
    laden = re.search(r"function laden\(\)\{.*?\n\}\n", text, flags=re.S)[0]
    assert "if(VORWAHL)teile.push('vorwahl='+encodeURIComponent(VORWAHL));" in laden
    vorwahl = re.search(r"function vorwahlText\(w\)\{.*?\n\}\n", text, flags=re.S)[0]
    assert "if(!v||String(v.id)!==String(w))return w+' (nicht in der Auswahl)';" in vorwahl
    assert "return auftragTitel(v)+' ('+(v.geschlossen?'Auftrag '+v.geschlossen:'nicht in der Auswahl')+')';" in vorwahl
    assert text.count(":vorwahlText(w)}});") == 2  # Zeit nachtragen und Nachtrag für die Kolonne
