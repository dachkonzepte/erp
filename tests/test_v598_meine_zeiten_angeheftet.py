"""Seit 1.9.186 (Lohn L1a, Stufe 2, Punkt 1): „Meine Zeiten“ heftet eine laufende Zeit an, die vor dem Monatsanfang begann.

Stehende Uhr Di 01.12.2026, 10:00 (Europe/Berlin). Mia startete am Mo 30.11.2026 um 07:00 und hat den Feierabend vergessen.

    Server     GET /api/field-view/meine-zeiten liefert "angeheftet" (Startdatum, Beginn, Zeitart, Auftrag) nur, wenn die laufende Zeit vor
               dem ersten Tag des angezeigten Monats begann -- im November steht sie an ihrem Tag, eine heute begonnene Zeit nie angeheftet
    Beenden    "beenden" nach denselben Regeln wie POST …/ende-nachtragen (ende_nachtragen_pruefen()): die Monteurin ja; Mitglied einer
               Gruppenzeit, Monat abgeschlossen (Monteurin), Büro – Auftrag nein, dafür "grund" mit der Meldung des Endpunkts
    Seite      die Zeile oben in „Buchungen“ mit Startdatum und „Beenden“; der Dialog trägt das Ende am Starttag nach (POST …/ende-nachtragen,
               Vorschau GET …/ende-vorschau) -- danach ist nichts mehr angeheftet

Im Browser: scripts/klicktest_meine_zeiten_angeheftet.py (dieselbe stehende Uhr).
"""

import json
import re
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.meldungen import MONAT_ABGESCHLOSSEN
from app.models import TeamEmployee, TimeEntry
from app.permissions import ZEITEN_NUR_LESEN
from app.routers import field_view as field_view_router
from app.routers import time_tracking as time_tracking_router
from app.routers.time_tracking import GRUPPENZEIT_NUR_KOLONNENFUEHRER
from app.time_backoffice import load_time_settings
from app.time_tracking import start_group_timer, start_timer
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.uhr import uhr_festhalten

HEUTE = date(2026, 12, 1)
VORTAG = date(2026, 11, 30)


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    with uhr_festhalten(tag=HEUTE):
        db = threaded_db_session
        order = beauftragen(db, make_quote(db, is_consumer=False, number="0598a"))
        order.title = "Wartung"
        team = make_team(db, "K-1", "Kolonne 1")
        mia = make_employee(db, "M-1", "Mia", "Monteurin")
        tom = make_employee(db, "M-2", "Tom", "Monteur")
        for emp, fuehrt in ((mia, True), (tom, False)):
            db.add(TeamEmployee(team_id=team.id, employee_id=emp.id, is_crew_leader=fuehrt))
        db.commit()
        yield {"db": db, "order": order, "team": team, "mia": mia, "tom": tom, "client": router_test_client}


def _als(w, emp, role="field"):
    return w["client"](w["db"], time_tracking_router.router, field_view_router.router, role=role, employee_id=emp.id)


def _seite(w, emp, monat=None, role="field"):
    antwort = _als(w, emp, role).get("/api/field-view/meine-zeiten", params={"monat": monat} if monat else None)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _vergessen(w, emp=None):
    return start_timer(w["db"], employee_id=(emp or w["mia"]).id, order_id=w["order"].id, started_at=datetime.combine(VORTAG, time(7)))


def test_laufende_zeit_vom_vormonat_angeheftet(welt):
    """Am 01.12. zeigt der Dezember keinen Tag -- die Zeit vom 30.11. steht angeheftet mit Startdatum und Beginn, „Beenden“ gilt."""
    row = _vergessen(welt)
    d = _seite(welt, welt["mia"])
    assert d["monat"] == "2026-12" and d["tage"] == []
    a = d["angeheftet"]
    assert (a["id"], a["tag"], a["beginn"], a["zeitart"], a["order_number"]) == (row.id, "2026-11-30", "07:00", "Baustellenzeit",
                                                                                 welt["order"].order_number)
    assert (a["beenden"], a["grund"], a["auftrag_geschlossen"]) == (True, None, None)
    assert Decimal(str(d["kacheln"]["monat"])) == 0  # eine laufende Zeit zählt nicht mit


def test_im_monat_des_starts_nicht_angeheftet(welt):
    """Gegenprobe: im November steht sie an ihrem Tag (wie bisher, mit „läuft seit“), nichts angeheftet."""
    row = _vergessen(welt)
    d = _seite(welt, welt["mia"], monat="2026-11")
    assert d["angeheftet"] is None
    zeilen = [z for t in d["tage"] for z in t["zeilen"]]
    assert [(z["id"], z["laeuft"], z["laeuft_seit_frueher"]) for z in zeilen] == [(row.id, True, True)]


def test_heute_begonnene_zeit_nie_angeheftet(welt):
    """Gegenprobe: eine Zeit, die heute (01.12.) begann, steht im Dezember an ihrem Tag."""
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(HEUTE, time(7)))
    d = _seite(welt, welt["mia"])
    assert d["angeheftet"] is None and [t["tag"] for t in d["tage"]] == ["2026-12-01"]


def test_beenden_traegt_das_ende_am_starttag_nach(welt):
    """„Beenden“: Vorschau und Buchung über die Endpunkte von „Ende nachtragen“ -- danach nichts angeheftet, die Buchung im November."""
    row = _vergessen(welt)
    client = _als(welt, welt["mia"])
    v = client.get(f"/api/time-entries/{row.id}/ende-vorschau", params={"ende": "2026-11-30T16:00"})
    assert v.status_code == 200, v.text
    b = client.post(f"/api/time-entries/{row.id}/ende-nachtragen", json={"ende": "2026-11-30T16:00"})
    assert b.status_code == 200, b.text
    assert Decimal(str(v.json()["gebucht"])) == Decimal(str(b.json()["hours"])) == Decimal("8.5")
    assert _seite(welt, welt["mia"])["angeheftet"] is None
    nov = _seite(welt, welt["mia"], monat="2026-11")
    assert [(z["id"], z["laeuft"], z["von"], z["bis"]) for t in nov["tage"] for z in t["zeilen"]] == [(row.id, False, "07:00", "16:00")]


def test_gruppenzeit_beendet_nur_der_kolonnenfuehrer(welt):
    """Angriff: Toms Teil einer Gruppenzeit -- angeheftet, aber ohne „Beenden“, mit der Meldung des Endpunkts; Mia (Kolonnenführerin) darf."""
    start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id, actor_employee_id=welt["mia"].id,
                      is_admin=False, order_id=welt["order"].id, started_at=datetime.combine(VORTAG, time(7)))
    tom = _seite(welt, welt["tom"])["angeheftet"]
    assert (tom["beenden"], tom["grund"]) == (False, GRUPPENZEIT_NUR_KOLONNENFUEHRER)
    eigene = welt["db"].scalar(select(TimeEntry).where(TimeEntry.employee_id == welt["tom"].id, TimeEntry.status == "running"))
    abgelehnt = _als(welt, welt["tom"]).post(f"/api/time-entries/{eigene.id}/ende-nachtragen", json={"ende": "2026-11-30T16:00"})
    assert (abgelehnt.status_code, abgelehnt.json()["detail"]) == (403, GRUPPENZEIT_NUR_KOLONNENFUEHRER)
    mia = _seite(welt, welt["mia"])["angeheftet"]
    assert (mia["beenden"], mia["grund"]) == (True, None)


def test_monat_abgeschlossen_und_nur_lesen(welt):
    """Angriff: November abgeschlossen -- die Monteurin sieht die Zeit, beendet sie aber nicht (MONAT_ABGESCHLOSSEN, wie der Endpunkt);
    Büro – Auftrag mit eigener Zeit liest nur (ZEITEN_NUR_LESEN)."""
    _vergessen(welt)
    load_time_settings(welt["db"]).locked_until = VORTAG
    welt["db"].commit()
    a = _seite(welt, welt["mia"])["angeheftet"]
    assert (a["beenden"], a["grund"]) == (False, MONAT_ABGESCHLOSSEN)
    load_time_settings(welt["db"]).locked_until = None
    welt["db"].commit()
    _vergessen(welt, welt["tom"])
    b = _seite(welt, welt["tom"], role="buero_auftrag")["angeheftet"]
    assert (b["beenden"], b["grund"]) == (False, ZEITEN_NUR_LESEN)


# --- Seite --------------------------------------------------------------------------------------------------------------------------

def _funktion(text: str, kopf: str) -> str:
    i = text.index(kopf)
    tiefe, j = 0, text.index("{", i)
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _zeichnen(a) -> dict:
    """angeheftetZeichnen() der Seite in node mit einem Kasten als Attrappe -- zurück: hidden und das HTML."""
    text = vj.eigene_skripte("mobil_zeiten.html").text
    teile = [_funktion(text, k) for k in ("function esc(", "function pad2(", "function teile(", "function tagLang(", "function angeheftetZeichnen(")]
    js = ("var WOCHENTAG=['So','Mo','Di','Mi','Do','Fr','Sa'];var box={hidden:false,innerHTML:'x'};function el(id){return box}\n"
          + "\n".join(teile) + f"\nangeheftetZeichnen({json.dumps(a)});process.stdout.write(JSON.stringify({{hidden:box.hidden,html:box.innerHTML}}));")
    return node_ausfuehren(js)


ANGEHEFTET = {"id": 7, "tag": "2026-11-30", "beginn": "07:00", "zeitart": "Baustellenzeit", "order_number": "AUF-1", "project_name": "Dach <Süd>",
              "auftrag_geschlossen": None, "beenden": True, "grund": None}


def test_seite_zeigt_startdatum_und_beenden():
    d = _zeichnen(ANGEHEFTET)
    assert d["hidden"] is False
    text = re.sub(r"<[^>]+>", "|", d["html"])
    assert "Baustellenzeit läuft seit Mo 30.11.2026, 07:00" in text and "AUF-1 · Dach &lt;Süd&gt;" in text
    assert '<button type="button" class="knopf knopf-aktion knopf-klein" data-aktion="beenden">Beenden</button>' in d["html"]


def test_seite_ohne_beenden_nennt_den_grund_und_leer_ohne_zeit():
    d = _zeichnen({**ANGEHEFTET, "beenden": False, "grund": GRUPPENZEIT_NUR_KOLONNENFUEHRER})
    assert "Beenden" not in d["html"] and GRUPPENZEIT_NUR_KOLONNENFUEHRER in d["html"]
    assert _zeichnen(None) == {"hidden": True, "html": ""}


def test_seite_beendet_ueber_ende_nachtragen():
    """Der Dialog nimmt die Endpunkte von „Ende nachtragen“ (Vorschau über lesen(), Buchung über speichern(), danach neu geladen)."""
    text = vj.eigene_skripte("mobil_zeiten.html").text
    beenden = _funktion(text, "function beenden(")
    assert ("speichern('zeiten',()=>api('/api/time-entries/'+a.id+'/ende-nachtragen',{method:'POST',headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({ende:a.tag+'T'+wert})}),{neuLaden:laden})") in beenden
    vorschau = _funktion(text, "function bdVorschauLaden(")
    assert "var url='/api/time-entries/'+a.id+'/ende-vorschau?ende='+encodeURIComponent(a.tag+'T'+wert);" in vorschau
    assert "lesen('beenden-vorschau',()=>wert?api(url):Promise.resolve(null)" in vorschau
    assert "angeheftetZeichnen(d.angeheftet);" in _funktion(text, "function zeichnen(")
