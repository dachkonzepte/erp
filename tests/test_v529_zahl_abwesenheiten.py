"""Version 1.9.109 (Stufe 4, R5b Nachrunde 2, Punkt 3): die Zahl am Reiter „Abwesenheiten“ zählt wie „Prüfen“ nur, was auf das Konto wartet --
offene Anträge beim Admin (er entscheidet sie); Büro – Finanzen und Büro – Auftrag ohne Zahl. „Vor dem Abschluss“ nennt offene Anträge weiter.
1.9.101–1.9.108 zählte sie die offenen Anträge, die das Konto sieht.
"""

from datetime import date

import pytest

from app.models import EmployeeAbsenceRequest
from app.routers import zeiten as zeiten_router
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)


def _pruefen(w, rolle, employee_id=None):
    antwort = w["client"](w["db"], zeiten_router.router, role=rolle, employee_id=employee_id).get("/api/zeiten/pruefen")
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _antrag(w, emp):
    w["db"].add(EmployeeAbsenceRequest(employee_id=emp.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 11, 2),
                                       end_date=date(2026, 11, 6), status="pending"))
    w["db"].commit()


@pytest.mark.parametrize("rolle, zahl, sieht", [("admin", 1, True), ("buero_finanzen", 0, True), ("buero_auftrag", 0, False)])
def test_zahl_nur_beim_admin_vor_dem_abschluss_bei_beiden(welt, rolle, zahl, sieht):  # noqa: F811
    """Ein offener Antrag (Tom): Admin Zahl 1; Büro – Finanzen keine Zahl (bis 1.9.108: 1), sieht den Antrag aber auf „Prüfen“ und unter „Vor
    dem Abschluss“ wie der Admin; Büro – Auftrag (Mia) sieht ihn nicht, keine Zahl."""
    _antrag(welt, welt["tom"])
    p = _pruefen(welt, rolle, employee_id=welt["mia"].id if rolle == "buero_auftrag" else None)
    assert p["zahlen"]["abwesenheiten"] == zahl
    assert (len(p["antraege"]), {"art": "antraege", "text": "1 Antrag offen"} in p["vor_dem_abschluss"]) == ((1, True) if sieht else (0, False))
    assert p["antraege_entschieden"] is False


def test_eigener_antrag_des_bueros_ohne_zahl(welt):  # noqa: F811
    """Angriff: Büro – Auftrag hat selbst einen offenen Antrag -- er wartet auf den Admin, nicht auf sie: keine Zahl, der Antrag steht unter
    „Vor dem Abschluss“. Der Admin: Zahl 1."""
    _antrag(welt, welt["mia"])
    bea = _pruefen(welt, "buero_auftrag", employee_id=welt["mia"].id)
    assert (bea["zahlen"]["abwesenheiten"], len(bea["antraege"]), {"art": "antraege", "text": "1 Antrag offen"} in bea["vor_dem_abschluss"]) == (0, 1, True)
    assert _pruefen(welt, "admin")["zahlen"]["abwesenheiten"] == 1


def test_ohne_offenen_antrag_keine_zahl(welt):  # noqa: F811
    assert _pruefen(welt, "admin")["zahlen"]["abwesenheiten"] == 0
