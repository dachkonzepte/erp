"""Version 1.9.113 (Stufe 5, R1, Punkt 3, Befund F3/D14): „Einsatzberichte“ bucht keine eigene Dauer mehr.

    Admin, Büro – Finanzen  die Karte „Erfasste Zeiten“ zeigt die Zeiten und „Zeit buchen“ -- ein Link auf /zeiten?auftrag=<id>&buchung=neu#buchungen;
                            dort öffnet „Neue Buchung“ mit dem Auftrag (Pause des Tags, Vorschau vom Server). Keine Felder zum Buchen mehr auf
                            der Seite (bis 1.9.112 buchte sie eine Dauer ohne Pause und ohne Vorschau).
    Büro – Auftrag          liest nur (Hinweis), kein Link.
    Monteurin               unverändert „Zeit nachtragen“ auf „Meine Zeiten“.
    „Zeiten“                ?buchung=neu öffnet den Dialog nur, wer bucht, und streicht den Schalter aus der Adresse.
    Server                  die Vorschau, die der Dialog zeigt: 8 h Dauer ohne Pause an einem leeren Tag -> „passt danach nicht“, mit 30 min -> passt
                            (GET /api/time-entries/dauer-vorschau, dieselbe Regel wie „Prüfen“) -- im Browser scripts/klicktest_zeit_aus_einsatzberichte.py.
"""

import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.berlin_time import berlin_today
from app.routers.pages import router as pages_router
from app.routers.time_tracking import router as time_router
from tests.test_v264_field_time_tracking import _assign_via_team, _employee, _order

VORLAGEN = Path(__file__).resolve().parent.parent / "app" / "templates"


def _welt(db):
    order, _ = _order(db, "AUF-533-0001", "P-533-0001")
    mia = _employee(db, "E-533-1", "Mia", "Monteurin")
    _assign_via_team(db, order, mia)
    return order, mia


@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen", "buero_auftrag", "field"])
def test_karte_erfasste_zeiten_je_rolle(threaded_db_session, router_test_client, rolle):
    db = threaded_db_session
    order, mia = _welt(db)
    html = router_test_client(db, pages_router, role=rolle, employee_id=mia.id if rolle == "field" else None).get(
        f"/orders/{order.id}/service-reports").text
    for alt in ('id="teHours"', 'id="teEmployeeField"', 'id="teVon"', 'data-klick="zeit-buchen"', "saveReportTimeEntry"):
        assert alt not in html, alt
    link = f'href="/zeiten?auftrag={order.id}&amp;buchung=neu#buchungen"'
    if rolle == "field":
        assert 'id="zeitNachtragen"' in html and link not in html
    elif rolle == "buero_auftrag":
        assert 'id="zeitNurLesen"' in html and link not in html and 'id="timeEntriesTable"' in html
    else:
        assert re.search(r'<a class="zeit-nachtragen" id="zeitBuchenLink" ' + re.escape(link) + r'>Zeit buchen</a>', html)
        assert 'id="timeEntriesTable"' in html and 'id="zeitNurLesen"' not in html


def test_zeiten_oeffnet_neue_buchung_mit_buchung_neu():
    text = (VORLAGEN / "zeiten.html").read_text(encoding="utf-8")
    binden = re.search(r"function binden\(\)\{.*?\n\}", text, re.S).group(0)
    assert "var neuBuchen=q.get('buchung')==='neu'&&!!el('neueBuchung');" in binden
    assert "if(neuBuchen)buchungDialogOeffnen(null);" in binden and "q.delete('buchung')" in binden
    # „+ Buchung“ (neueBuchung) gibt es nur, wer bucht; der Auftrag kommt aus ?auftrag= (FILTER.auftrag) in die Auswahl des Dialogs
    assert "aendern?e.order_id:(FILTER.auftrag||'')" in text


@pytest.mark.parametrize("pause, passt", [(0, False), (30, True)])
def test_vorschau_im_dialog_8_stunden(threaded_db_session, router_test_client, pause, passt):
    db = threaded_db_session
    order, mia = _welt(db)
    tag = berlin_today() - timedelta(days=1)
    client = router_test_client(db, time_router, role="buero_finanzen")
    antwort = client.get("/api/time-entries/dauer-vorschau", params={"work_date": tag.isoformat(), "hours": "8", "break_minutes": pause,
                                                                     "employee_id": mia.id})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["passt"] is passt
