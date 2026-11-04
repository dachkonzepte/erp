"""Seit 1.9.192 (Lohn L1a, Stufe 3, Punkt 1): „Meine Zeiten“, Monat des Starts -- eine laufende Zeit von einem früheren Tag desselben
Monats bekommt denselben Dialog „Beenden“ wie die angeheftete Zeit (1.9.186); der Link nach /mobil entfällt (für ein Büro-Konto zeichnet
/mobil nur das Gerüst, GET /api/field-view/today antwortet 403).

Stehende Uhr Mi 18.11.2026, 10:00 (Europe/Berlin). Mia startete am Mo 16.11.2026 um 07:00 und hat den Feierabend vergessen.

    Server     die Zeile der laufenden Zeit trägt start_tag, "beenden" und "grund" -- nach denselben Regeln wie POST …/ende-nachtragen
               (ende_nachtragen_pruefen()); eine heute begonnene Zeit nicht (sie stoppt auf „Heute“ normal)
    Seite      die Zeile zeigt „Beenden“ (data-aktion="beenden", data-id) statt des Links, sonst die Meldung; der Klick öffnet den Dialog der
               angehefteten Zeit mit den Feldern der Zeile (laufendeZeit())

Im Browser: scripts/klicktest_meine_zeiten.py (Ole, Fin).
"""

import json
import re
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.meldungen import MONAT_ABGESCHLOSSEN
from app.models import TimeEntry
from app.permissions import ZEITEN_NUR_LESEN
from app.routers.time_tracking import GRUPPENZEIT_NUR_KOLONNENFUEHRER
from app.time_backoffice import load_time_settings
from app.time_tracking import start_group_timer, start_timer
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v598_meine_zeiten_angeheftet import _als, _funktion, _seite
from tests.uhr import uhr_festhalten

HEUTE = date(2026, 11, 18)
START = date(2026, 11, 16)


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    with uhr_festhalten(tag=HEUTE):
        db = threaded_db_session
        order = beauftragen(db, make_quote(db, is_consumer=False, number="0602a"))
        order.title = "Wartung"
        team = make_team(db, "K-1", "Kolonne 1")
        mia = make_employee(db, "M-1", "Mia", "Monteurin")
        tom = make_employee(db, "M-2", "Tom", "Monteur")
        from app.models import TeamEmployee
        for emp, fuehrt in ((mia, True), (tom, False)):
            db.add(TeamEmployee(team_id=team.id, employee_id=emp.id, is_crew_leader=fuehrt))
        db.commit()
        yield {"db": db, "order": order, "team": team, "mia": mia, "tom": tom, "client": router_test_client}


def _vergessen(w, emp=None, tag=START):
    return start_timer(w["db"], employee_id=(emp or w["mia"]).id, order_id=w["order"].id, started_at=datetime.combine(tag, time(7)))


def _laufend(d):
    return [z for t in d["tage"] for z in t["zeilen"] if z["laeuft"]]


def test_zeile_von_frueher_im_monat_mit_beenden(welt):
    """Im November (Monat des Starts) nichts angeheftet; die Zeile am 16.11. trägt Starttag und „Beenden“."""
    row = _vergessen(welt)
    d = _seite(welt, welt["mia"])
    assert d["monat"] == "2026-11" and d["angeheftet"] is None
    [z] = _laufend(d)
    assert (z["id"], z["start_tag"], z["von"], z["laeuft_seit_frueher"], z["beenden"], z["grund"]) == (
        row.id, "2026-11-16", "07:00", True, True, None)


def test_heute_begonnene_zeit_ohne_beenden(welt):
    """Gegenprobe: eine heute begonnene Zeit stoppt auf „Heute“ normal -- kein „Beenden“, kein Grund."""
    _vergessen(welt, tag=HEUTE)
    [z] = _laufend(_seite(welt, welt["mia"]))
    assert (z["laeuft_seit_frueher"], z["start_tag"], "beenden" in z, "grund" in z) == (False, "2026-11-18", False, False)


def test_beenden_im_monat_traegt_das_ende_am_starttag_nach(welt):
    """„Beenden“ über die Endpunkte von „Ende nachtragen“ am Starttag -- danach eine gebuchte Zeile am 16.11."""
    row = _vergessen(welt)
    client = _als(welt, welt["mia"])
    v = client.get(f"/api/time-entries/{row.id}/ende-vorschau", params={"ende": "2026-11-16T16:00"})
    b = client.post(f"/api/time-entries/{row.id}/ende-nachtragen", json={"ende": "2026-11-16T16:00"})
    assert (v.status_code, b.status_code) == (200, 200), (v.text, b.text)
    assert Decimal(str(v.json()["gebucht"])) == Decimal(str(b.json()["hours"])) == Decimal("8.5")
    d = _seite(welt, welt["mia"])
    assert _laufend(d) == [] and [(z["id"], z["von"], z["bis"]) for t in d["tage"] for z in t["zeilen"]] == [(row.id, "07:00", "16:00")]


def test_buero_finanzen_beendet_ohne_heute(welt):
    """Ein Büro-Konto mit eigener Zeit: „Heute“ verweigert ihm die Daten (403, der frühere Link führte ins Leere) -- „Beenden“ gilt und bucht."""
    row = _vergessen(welt)
    client = _als(welt, welt["mia"], role="buero_finanzen")
    assert client.get("/api/field-view/today").status_code == 403
    [z] = _laufend(_seite(welt, welt["mia"], role="buero_finanzen"))
    assert (z["beenden"], z["grund"]) == (True, None)
    b = client.post(f"/api/time-entries/{row.id}/ende-nachtragen", json={"ende": "2026-11-16T15:30"})
    assert b.status_code == 200, b.text


def test_ohne_beenden_der_grund_des_servers(welt):
    """Angriff: Toms Teil einer Gruppenzeit (nur die Kolonnenführerin), Monat abgeschlossen (Monteurin), Büro – Auftrag (nur lesen) --
    je ohne „Beenden“, mit der Meldung des Endpunkts."""
    start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id, actor_employee_id=welt["mia"].id,
                      is_admin=False, order_id=welt["order"].id, started_at=datetime.combine(START, time(7)))
    [tom] = _laufend(_seite(welt, welt["tom"]))
    assert (tom["beenden"], tom["grund"]) == (False, GRUPPENZEIT_NUR_KOLONNENFUEHRER)
    [mia] = _laufend(_seite(welt, welt["mia"]))
    assert (mia["beenden"], mia["grund"]) == (True, None)
    load_time_settings(welt["db"]).locked_until = START
    welt["db"].commit()
    [mia] = _laufend(_seite(welt, welt["mia"]))
    assert (mia["beenden"], mia["grund"]) == (False, MONAT_ABGESCHLOSSEN)
    load_time_settings(welt["db"]).locked_until = None
    welt["db"].commit()
    [tom] = _laufend(_seite(welt, welt["tom"], role="buero_auftrag"))
    assert (tom["beenden"], tom["grund"]) == (False, ZEITEN_NUR_LESEN)
    eigene = welt["db"].scalar(select(TimeEntry).where(TimeEntry.employee_id == welt["tom"].id, TimeEntry.status == "running"))
    assert eigene is not None


# --- Seite --------------------------------------------------------------------------------------------------------------------------

def _zeile(z) -> str:
    """zeileHtml() der Seite in node -- zurück: das HTML der Zeile."""
    text = vj.eigene_skripte("mobil_zeiten.html").text
    teile = [_funktion(text, k) for k in ("function esc(", "function zeileHtml(", "function menueHtml(")]
    js = ("function stunden(x){return String(x)}\n" + "\n".join(teile)
          + f"\nprocess.stdout.write(JSON.stringify(zeileHtml({json.dumps(z)},{{tag:'2026-11-16'}})));")
    return node_ausfuehren(js)


ZEILE = {"id": 9, "zeitart": "Baustellenzeit", "order_number": "AUF-1", "project_name": "Dach <Süd>", "von": "07:00", "bis": None,
         "laeuft": True, "laeuft_seit_frueher": True, "start_tag": "2026-11-16", "beenden": True, "grund": None, "activity": None,
         "notes": None, "gebucht_von": None, "auftrag_geschlossen": None, "gebucht": None}


def test_seite_zeile_mit_beenden_statt_link():
    html = _zeile(ZEILE)
    assert '<button type="button" class="knopf knopf-aktion knopf-klein" data-aktion="beenden" data-id="9">Beenden</button>' in html
    assert "href" not in html and "Heute" not in html
    assert "Baustellenzeit" in re.sub(r"<[^>]+>", "|", html) and "läuft seit 07:00" in html


def test_seite_zeile_ohne_beenden_nennt_den_grund():
    html = _zeile({**ZEILE, "beenden": False, "grund": "Nur <der> Kolonnenführer"})
    assert "Beenden" not in html and "href" not in html
    assert '<span class="zeile-zu" data-grund>Nur &lt;der&gt; Kolonnenführer</span>' in html
    assert "Beenden" not in _zeile({**ZEILE, "laeuft_seit_frueher": False, "beenden": None, "grund": None})


def test_seite_klick_oeffnet_den_dialog_mit_den_feldern_der_zeile():
    """laufendeZeit() gibt dem Dialog dieselben Felder wie die angeheftete Zeit; der Klick in „Buchungen“ ruft ihn auf."""
    text = vj.eigene_skripte("mobil_zeiten.html").text
    js = _funktion(text, "function laufendeZeit(") + f"\nprocess.stdout.write(JSON.stringify(laufendeZeit({json.dumps(ZEILE)})));"
    assert node_ausfuehren(js) == {"id": 9, "tag": "2026-11-16", "beginn": "07:00", "zeitart": "Baustellenzeit", "order_number": "AUF-1",
                                   "project_name": "Dach <Süd>", "beenden": True}
    binden = _funktion(text, "function binden(")
    assert "else if(a==='beenden')beendenOeffnen(laufendeZeit(zeileZu(b.dataset.id)));" in binden
    assert 'href="/mobil">Feierabend' not in text
