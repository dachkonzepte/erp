"""Version 1.9.147 (Stufe 6, R1, Punkt 5, P10): Bundesland, Arbeitstage, betriebsfreie Tage ändern Admin und Büro – Finanzen; Büro – Auftrag liest.

    Angriff      Büro – Auftrag: PUT Einstellungen, Feiertag anlegen, ändern, löschen, Ferien abgleichen -> je 403 mit Grund, nichts geändert; Monteur 403
    Gegenprobe   Admin und Büro – Finanzen dürfen alles; Büro – Auftrag liest Einstellungen und Feiertage
    Seite        Büro – Auftrag sieht den Hinweis, gesperrte Felder, keine Knöpfe; Admin und Finanzen nicht
"""

from datetime import date
from pathlib import Path

import pytest

from app.models import PlanningHoliday, PlanningRegionSettings
from app.permissions import PLANUNGSGRUNDLAGEN_NUR_LESEN
from app.routers.pages import router as pages_router
from app.routers.planning import router as planning_router

ROOT = Path(__file__).resolve().parent.parent
EINSTELLUNG = {"daily_work_hours": "8", "default_travel_hours_per_employee_day": "0", "monday": True, "tuesday": True, "wednesday": True, "thursday": True, "friday": True,
               "saturday": False, "sunday": False, "federal_state_code": "BY", "auto_public_holidays": True, "show_school_holidays": False}
TAG = {"holiday_date": "2026-12-24", "name": "Betriebsferien", "active": True}


@pytest.fixture()
def tag(threaded_db_session):
    db = threaded_db_session
    zeile = PlanningHoliday(holiday_date=date(2026, 12, 28), name="Brückentag", active=True)
    db.add(zeile)
    db.commit()
    return zeile.id


def _schreibende(tag_id):
    return (("PUT", "/api/planning/settings", EINSTELLUNG), ("POST", "/api/planning/holidays", TAG), ("PUT", f"/api/planning/holidays/{tag_id}", {**TAG, "holiday_date": "2026-12-29", "name": "Anders"}),
            ("DELETE", f"/api/planning/holidays/{tag_id}", None), ("POST", "/api/planning/school-holidays/sync?years=1", None))


@pytest.mark.parametrize("rolle", ["buero_auftrag", "field"])
def test_nicht_erlaubt_403_und_nichts_geaendert(threaded_db_session, router_test_client, tag, rolle):
    db = threaded_db_session
    land_vorher = db.get(PlanningRegionSettings, 1).federal_state_code
    client = router_test_client(db, planning_router, role=rolle)
    for methode, url, body in _schreibende(tag):
        antwort = client.request(methode, url, json=body)
        assert antwort.status_code == 403, (rolle, methode, url)
        if rolle == "buero_auftrag":
            assert antwort.json()["detail"] == PLANUNGSGRUNDLAGEN_NUR_LESEN
    db.expire_all()
    assert db.get(PlanningRegionSettings, 1).federal_state_code == land_vorher
    assert db.get(PlanningHoliday, tag).name == "Brückentag"


def test_buero_auftrag_liest(threaded_db_session, router_test_client, tag):
    client = router_test_client(threaded_db_session, planning_router, role="buero_auftrag")
    assert client.get("/api/planning/settings").json()["federal_state_code"]
    assert [x["id"] for x in client.get("/api/planning/holidays").json()] == [tag]


@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen"])
def test_admin_und_finanzen_duerfen(threaded_db_session, router_test_client, tag, rolle, monkeypatch):
    import app.planning as planung

    monkeypatch.setattr(planung, "_fetch_school_holidays", lambda *_a, **_k: [])  # kein Netz im Test
    db = threaded_db_session
    client = router_test_client(db, planning_router, role=rolle)
    for methode, url, body in _schreibende(tag):
        antwort = client.request(methode, url, json=body)
        assert antwort.status_code == 200, (rolle, methode, url, antwort.text)
    db.expire_all()
    assert db.get(PlanningRegionSettings, 1).federal_state_code == "BY"


@pytest.mark.parametrize("rolle,nur_lesen", [("buero_auftrag", True), ("buero_finanzen", False), ("admin", False)])
def test_seite_sagt_es_und_sperrt(threaded_db_session, router_test_client, rolle, nur_lesen):
    html = router_test_client(threaded_db_session, pages_router, role=rolle).get("/settings").text
    assert (f'<div class="hint" data-grundlagen-nur-lesen>{PLANUNGSGRUNDLAGEN_NUR_LESEN}</div>' in html) is nur_lesen
    assert f'const GRUNDLAGEN="{"nein" if nur_lesen else "ja"}"!=="nein";' in html


def test_knoepfe_und_zeilen_haengen_an_der_regel():
    html = (ROOT / "app/templates/settings.html").read_text(encoding="utf-8")
    start = html.index('id="settings-planning"')
    abschnitt = html[start:html.index("</section>", start)]
    for aufruf in ("savePlanningSettings()", "syncSchoolHolidays(true)", "resetHoliday();showHolidayEditor()"):
        marke = abschnitt.index(aufruf)
        knopf = abschnitt[abschnitt.rindex("<button", 0, marke):marke]
        assert "data-grundlagen-knopf" in knopf, aufruf
    zeilen = html[html.index("function renderHolidays()"):]
    assert "${GRUNDLAGEN?`<button" in zeilen[:zeilen.index("\n")]
    assert "function renderPlanningSettings(){if(!planningSettings)return;grundlagenNurLesen();" in html
