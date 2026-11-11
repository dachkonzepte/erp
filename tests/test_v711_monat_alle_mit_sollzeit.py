"""Version 1.9.311 (Lohn L2a, Punkt 4; Antwort 14 des Befunds L2): „Monat & Lohn“ zeigt alle, die im Monat Sollzeit haben (app/zeiten.py::monat()).

    neu         wer im Monat nur Urlaub hat oder krank ist, und wer gar nichts hat, steht mit 0 Tagen und 0,00 h in der Tabelle, sobald er Sollzeit hat
                (bis 1.9.310 nur mit Buchung oder Ausfalltag -- Befund 7.3; in der Lohndatei stand er mit U/K)
    nicht       ohne Sollzeit im Monat (Eintritt danach, Austritt davor) und inaktiv ohne Daten im Monat
    bleibt      Personen mit Buchung oder Ausfalltag wie bisher, die Summen unverändert
Dezember 2026 (Tarif 7,50 h); stehende Uhr 10.11.2026.
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.models import EmployeeAbsence, EmployeePayrollSettings, TimeEntry
from app.routers import zeiten as zeiten_router
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0711"))
    return {"db": db, "order": order, "client": router_test_client(db, zeiten_router.router)}


def _person(w, nr, vorname, *, aktiv=True, eintritt=None, austritt=None):
    e = make_employee(w["db"], nr, vorname, "Test")
    e.active = aktiv
    if eintritt or austritt:
        w["db"].add(EmployeePayrollSettings(employee_id=e.id, eintritt=eintritt, austritt=austritt))
    w["db"].commit()
    return e


def _zeilen(w, monat="2026-12") -> dict:
    r = w["client"].get(f"/api/zeiten/monat?monat={monat}")
    assert r.status_code == 200, r.text
    d = r.json()
    return {z["name"]: (z["tage"], z["zusammen"]) for z in d["zeilen"]}, d["summe"]["zusammen"]


def test_alle_mit_sollzeit(w):
    db, o = w["db"], w["order"]
    ada = _person(w, "M-1", "Ada")  # bucht
    urs = _person(w, "M-2", "Urs")  # den ganzen Monat Urlaub
    nie = _person(w, "M-3", "Nie")  # nichts
    _person(w, "M-4", "Spaet", eintritt=date(2027, 1, 1))  # keine Sollzeit im Dezember
    _person(w, "M-5", "Frueh", austritt=date(2026, 11, 30))
    _person(w, "M-6", "Alt", aktiv=False)  # inaktiv ohne Daten
    krank = _person(w, "M-7", "Krank", aktiv=False)  # inaktiv, aber im Monat krank
    tag = date(2026, 12, 1)
    db.add(TimeEntry(employee_id=ada.id, project_id=o.project_id, order_id=o.id, work_date=tag, entry_type="site", hours=Decimal("6"), break_minutes=0,
                     status="booked", started_at=datetime.combine(tag, time(7)), ended_at=datetime.combine(tag, time(13))))
    db.add(EmployeeAbsence(employee_id=urs.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 12, 1), end_date=date(2026, 12, 31)))
    db.add(EmployeeAbsence(employee_id=krank.id, absence_type="Krankheit", absence_category="krankheit", start_date=date(2026, 12, 7),
                           end_date=date(2026, 12, 8)))
    db.commit()
    zeilen, summe = _zeilen(w)
    assert zeilen == {"Ada Test": (1, 6), "Urs Test": (0, 0), "Nie Test": (0, 0), "Krank Test": (0, 0)}
    assert summe == 6
    assert nie.id  # ohne alles, aber mit Sollzeit


def test_ein_monat_ohne_sollzeit_fuer_alle(w):
    """Im Monat vor dem Eintritt steht die Person nicht da."""
    _person(w, "M-1", "Spaet", eintritt=date(2027, 1, 1))
    zeilen, _ = _zeilen(w)
    assert "Spaet Test" not in zeilen
    zeilen, _ = _zeilen(w, "2027-01")
    assert zeilen.get("Spaet Test") == (0, 0)
