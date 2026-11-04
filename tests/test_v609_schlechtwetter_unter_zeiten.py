"""Version 1.9.202 (Lohn L1a, Stufe 4, Punkt 1; Festlegung 1.9.170 Nr. 3): ein Ausfalltag Schlechtwetter wird auf jedem Weg nur genehmigt,
wenn der Schlechtwetter-Dialog ihn annähme -- auch, wenn der Admin ihn unter „Zeiten“ entscheidet (POST /api/absence-requests/{id}/review).

    vorher    unter „Zeiten“ genehmigt, auch an einem Tag ohne Sollzeit; der Dialog lehnte denselben Antrag ab (422)
    jetzt     app/absence_requests.py::_entscheiden() prüft grund_gegen() (app/schlechtwetter.py) -- 422 mit dem Grund, der Antrag bleibt offen,
              keine Abwesenheit; ablehnen geht weiter

Feste Tage wie tests/test_v588_schlechtwetter.py: Mo 07.12.2026, fester Tag der Uhr 10.11.2026.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import EmployeeAbsenceRequest
from app.routers import absence_requests as absence_router
from app.routers import zeiten as zeiten_router
from app.sollzeit import zeile_anlegen
from tests.test_v588_schlechtwetter import MO, _abwesenheiten, _als, _eintragen, welt  # noqa: F401  (Fixture)


def _antrag_von_tom(w) -> int:
    """Tom (ohne Kennzeichen) beantragt Schlechtwetter für Mo 07.12. -- ein offener Antrag, an dem Tag gültig."""
    r = _eintragen(_als(w, "field", "tom"), w["tom"])
    assert (r.status_code, r.json()["genehmigt"]) == (200, False), r.text
    return w["db"].scalar(select(EmployeeAbsenceRequest.id))


def _danach_ungueltig(w, art: str) -> str:
    """Nach dem Antrag ändert sich etwas, das den Tag ausschließt -- die Meldung, die der Dialog dafür gibt."""
    db = w["db"]
    if art == "ohne_soll":
        zeile_anlegen(db, w["tom"].id, date(2026, 12, 1), {"dienstag": Decimal("4")})
        db.commit()
        return "Tom Monteur: am 07.12.2026 keine Sollzeit"
    w["tom"].employee_group = "kaufmaennisch"
    db.commit()
    return "Tom Monteur: Schlechtwetter nur für gewerbliche Mitarbeiter"


def _status(w, antrag: int) -> str:
    w["db"].expire_all()
    return w["db"].get(EmployeeAbsenceRequest, antrag).status


@pytest.mark.parametrize("art", ["ohne_soll", "kaufmaennisch"])
def test_unter_zeiten_wie_im_dialog_abgelehnt(welt, art):  # noqa: F811
    """Der Admin genehmigt unter „Zeiten“: 422 mit dem Grund des Dialogs, der Antrag bleibt offen, keine Abwesenheit."""
    antrag = _antrag_von_tom(welt)
    grund = _danach_ungueltig(welt, art)
    r = _als(welt).post(f"/api/absence-requests/{antrag}/review", json={"decision": "approved"})
    assert (r.status_code, r.json()["detail"]) == (422, grund), r.text
    assert (_status(welt, antrag), _abwesenheiten(welt)) == ("pending", [])


@pytest.mark.parametrize("art", ["ohne_soll", "kaufmaennisch"])
def test_im_dialog_dieselbe_meldung(welt, art):  # noqa: F811
    """Derselbe Antrag im Schlechtwetter-Dialog (Kolonnenführer Kai): dieselbe Meldung -- ein Weg für beide."""
    antrag = _antrag_von_tom(welt)
    grund = _danach_ungueltig(welt, art)
    r = _als(welt, "field", "kai").post(f"/api/schlechtwetter/{antrag}/entscheiden", json={"decision": "approved"})
    assert (r.status_code, r.json()["detail"]) == (422, grund), r.text
    assert (_status(welt, antrag), _abwesenheiten(welt)) == ("pending", [])


def test_unter_zeiten_ablehnen_geht_weiter(welt):  # noqa: F811
    antrag = _antrag_von_tom(welt)
    _danach_ungueltig(welt, "ohne_soll")
    r = _als(welt).post(f"/api/absence-requests/{antrag}/review", json={"decision": "rejected"})
    assert (r.status_code, r.json()["status"]) == (200, "rejected"), r.text
    assert _abwesenheiten(welt) == []


def test_unter_zeiten_gueltiger_tag_genehmigt(welt):  # noqa: F811
    """Ohne Änderung genehmigt der Admin unter „Zeiten“ wie bisher; die Zeile dort bietet „Genehmigen“ an."""
    antrag = _antrag_von_tom(welt)
    client = _als(welt)
    zeiten = welt["client"](welt["db"], zeiten_router.router, absence_router.router, role="admin", user_id=7)
    zeile = next(a for a in zeiten.get("/api/zeiten/abwesenheiten").json()["antraege"] if a["id"] == antrag)
    assert (zeile["absence_category"], zeile["darf_entscheiden"]) == ("schlechtwetter", True)
    r = client.post(f"/api/absence-requests/{antrag}/review", json={"decision": "approved"})
    assert (r.status_code, r.json()["status"]) == (200, "approved"), r.text
    assert _abwesenheiten(welt) == [(welt["tom"].id, MO, MO, "schlechtwetter", "Schlechtwetter")]


def test_andere_kategorie_ohne_pruefung_des_dialogs(welt):  # noqa: F811
    """Nur der Ausfalltag wird so geprüft: Urlaub an einem Tag ohne Sollzeit genehmigt der Admin wie bisher (die Sollzeit zählt dort 0)."""
    zeile_anlegen(welt["db"], welt["tom"].id, date(2026, 12, 1), {"dienstag": Decimal("4")})
    client = _als(welt)
    r = client.post("/api/absence-requests", json={"employee_id": welt["tom"].id, "absence_category": "urlaub",
                                                    "start_date": MO.isoformat(), "end_date": MO.isoformat()})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/absence-requests/{r.json()['id']}/review", json={"decision": "approved"})
    assert (r.status_code, r.json()["status"]) == (200, "approved"), r.text
