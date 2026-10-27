"""Version 1.9.108 (Stufe 4, R5b Nachrunde 2, Punkt 2): „Arbeitstage“ am Antrag mit den Feiertagen des Bundeslands aus der Einstellung der
Plantafel (PlanningRegionSettings.federal_state_code, eine Quelle) -- ohne Einstellung Nordrhein-Westfalen. 1.9.105–1.9.107 fest NRW.
"""

from datetime import date

import pytest

from app.models import EmployeeAbsenceRequest, PlanningRegionSettings
from app.planning import update_planning_settings
from app.routers import zeiten as zeiten_router
from app.zeiten import arbeitstage, feiertage_bundesland
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)

WOCHE = (date(2027, 1, 4), date(2027, 1, 8))  # Mo 04.01.–Fr 08.01.2027, Mi 06.01. Heilige Drei Könige (BW, BY, ST)


@pytest.mark.parametrize("land, tage", [("NW", 5), ("BY", 4), ("BW", 4), ("ST", 4), ("NI", 5)])
def test_woche_mit_heilige_drei_koenige(land, tage):
    assert arbeitstage(*WOCHE, land) == tage


def _antrag_und_tage(w):
    db = w["db"]
    if not db.query(EmployeeAbsenceRequest).count():
        db.add(EmployeeAbsenceRequest(employee_id=w["tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=WOCHE[0],
                                      end_date=WOCHE[1], status="pending"))
        db.commit()
    client = w["client"](db, zeiten_router.router, role="admin")
    return ([a["arbeitstage"] for a in client.get("/api/zeiten/abwesenheiten").json()["antraege"]],
            [a["arbeitstage"] for a in client.get("/api/zeiten/pruefen").json()["antraege"]])


def test_antrag_nach_dem_bundesland_der_plantafel(welt):  # noqa: F811
    """Angriff: die Plantafel steht auf Bayern -- Toms Urlaub Mo 04.01.–Fr 08.01.2027 hat auf „Abwesenheiten“ und „Prüfen“ 4 Arbeitstage (bis
    1.9.107: fest NRW, 5). Gegenprobe: Nordrhein-Westfalen 5. Umgestellt über die Einstellungen der Plantafel (dieselbe Funktion wie dort)."""
    update_planning_settings(welt["db"], federal_state_code="BY")
    assert feiertage_bundesland(welt["db"]) == "BY" and _antrag_und_tage(welt) == ([4], [4])
    update_planning_settings(welt["db"], federal_state_code="NW")
    assert _antrag_und_tage(welt) == ([5], [5])


def test_bayern_auch_ohne_automatische_feiertage_der_plantafel(welt):  # noqa: F811
    """Festlegung 1.9.108 Nr. 2: „Feiertage automatisch“ der Plantafel aus -- die Arbeitstage zählen die gesetzlichen Feiertage des Bundeslands
    trotzdem (die Plantafel blendet sie nur aus)."""
    update_planning_settings(welt["db"], federal_state_code="BY", auto_public_holidays=False)
    assert _antrag_und_tage(welt) == ([4], [4])


def test_ohne_einstellung_nrw(welt):  # noqa: F811
    """Ohne Einstellungszeile oder ohne Wert Nordrhein-Westfalen -- kein Fehler, 5 Arbeitstage."""
    db = welt["db"]
    zeile = db.get(PlanningRegionSettings, 1)
    zeile.federal_state_code = ""
    db.commit()
    assert feiertage_bundesland(db) == "NW" and _antrag_und_tage(welt) == ([5], [5])
    db.delete(zeile)
    db.commit()
    assert feiertage_bundesland(db) == "NW" and _antrag_und_tage(welt) == ([5], [5])
