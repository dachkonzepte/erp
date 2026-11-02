"""Version 1.9.168 (Lohn L1a, Punkt 3, Entscheidung Tobias E3): DATEV-Personalnummer nur Ziffern und eindeutig, Export-Umfang je Person.

    Format        1 bis 5 Ziffern ohne führende Null (wie in den Mustern aus Time 4) -- sonst 422; bei „DATEV-Nr. = ERP-Nr.“ nur, wenn von der
                  Person etwas in die Datei geht
    eindeutig     in der Datenbank (uq_employee_payroll_datev_number); die Migration c5a9e3f71d28 bricht bei einer Dublette ab, ohne etwas zu
                  ändern; Leerzeichen um eine Nummer zählen nicht, eine leere wird NULL
    Umfang        alles | abwesenheiten | nichts statt „Export an/aus“; der heutige Export nimmt die Arbeit nur bei „alles“
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.models import EmployeePayrollSettings, TimeBackofficeAdvancedSettings
from app.routers import time_backoffice as time_backoffice_router
from app.time_backoffice import exportiert_arbeit
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "c5a9e3f71d28"
VORHER = "b7e3c91d4a52"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def _put(w, emp, rolle="buero_finanzen", **koerper):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, role=rolle).put(f"/api/time-backoffice/payroll-employees/{emp.id}", json=koerper)


@pytest.mark.parametrize("nummer", ["9100A", "091001", "123456", "0", "91 001", "91;01", "-5"])
def test_personalnummer_nur_ziffern(welt, nummer):
    r = _put(welt, welt["mia"], datev_personnel_number=nummer)
    assert r.status_code == 422 and "1 bis 5 Ziffern ohne führende Null" in r.json()["detail"], r.text
    assert welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=welt["mia"].id).count() == 0


@pytest.mark.parametrize("nummer", ["1", "9005", "91001", " 91001 "])
def test_gueltige_personalnummer(welt, nummer):
    r = _put(welt, welt["mia"], datev_personnel_number=nummer)
    assert (r.status_code, r.json()["datev_personnel_number"]) == (200, nummer.strip())


def test_dieselbe_nummer_fuer_zwei_personen(welt):
    """Angriff: dieselbe Nummer für Tom -> 422, Toms Zeile unverändert; in der Datenbank verhindert sie die Bedingung auch ohne Programm."""
    assert _put(welt, welt["mia"], datev_personnel_number="91001").status_code == 200
    r = _put(welt, welt["tom"], datev_personnel_number="91001")
    assert r.status_code == 422 and r.json()["detail"] == "Diese DATEV-Personalnummer ist bereits vergeben."
    db = welt["db"]
    db.add(EmployeePayrollSettings(employee_id=welt["tom"].id, datev_personnel_number="91001"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_leer_beliebig_oft(welt):
    assert _put(welt, welt["mia"], datev_personnel_number="").status_code == 200
    assert _put(welt, welt["tom"], datev_personnel_number=None).status_code == 200
    assert {p.datev_personnel_number for p in welt["db"].query(EmployeePayrollSettings)} == {None}


@pytest.mark.parametrize("umfang, arbeit", [("alles", True), ("abwesenheiten", False), ("nichts", False)])
def test_export_umfang(welt, umfang, arbeit):
    r = _put(welt, welt["mia"], export_umfang=umfang)
    assert (r.status_code, r.json()["export_umfang"], r.json()["payroll_export_enabled"]) == (200, umfang, umfang != "nichts")
    welt["db"].expire_all()
    assert exportiert_arbeit(welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=welt["mia"].id).one()) is arbeit


def test_export_umfang_falsch_und_altes_haekchen(welt):
    assert _put(welt, welt["mia"], export_umfang="halb").status_code == 422
    assert _put(welt, welt["mia"], export_umfang=None).status_code == 422
    assert _put(welt, welt["mia"], payroll_export_enabled=False).json()["export_umfang"] == "nichts"
    assert _put(welt, welt["mia"], payroll_export_enabled=True).json()["export_umfang"] == "alles"


def test_gleichsetzung_mit_erp_nummer(welt):
    """„DATEV-Nr. = ERP-Nr.“: die ERP-Nummer „M-1“ taugt nicht -- abgelehnt, solange etwas von der Person in die Datei geht; mit „nichts“
    speicherbar (Eintritt u. a. bleiben pflegbar)."""
    db = welt["db"]
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    r = _put(welt, welt["mia"], eintritt="2026-11-05")
    assert r.status_code == 422 and "„M-1“ taugt nicht als DATEV-Personalnummer" in r.json()["detail"]
    assert _put(welt, welt["mia"], export_umfang="nichts", eintritt="2026-11-05").status_code == 200


def test_buero_auftrag_403(welt):
    r = _put(welt, welt["mia"], rolle="buero_auftrag", datev_personnel_number="91001")
    assert r.status_code == 403


# --- Migration c5a9e3f71d28 -----------------------------------------------------------------------------------------------------------------

def _bestand(engine, mit_dublette: bool) -> None:
    with engine.begin() as c:
        for i in range(1, 5):
            c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                           "VALUES (:n, 'P', :l, 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"n": f"M-{i}", "l": f"P{i}", "a": True})
        ids = [r[0] for r in c.execute(text("SELECT id FROM employees ORDER BY id"))]
        werte = [("91001", True), (" 91002 ", False), ("   ", True), ("91001 " if mit_dublette else "91004", True)]
        for emp, (nummer, an) in zip(ids, werte):
            c.execute(text("INSERT INTO employee_payroll_settings (employee_id, datev_personnel_number, payroll_export_enabled, updated_at) "
                           "VALUES (:e, :n, :a, '2026-09-01')"), {"e": emp, "n": nummer, "a": an})


def _zeilen(engine, mit_umfang: bool) -> list[tuple]:
    spalten = "datev_personnel_number, payroll_export_enabled" + (", export_umfang" if mit_umfang else "")
    with engine.connect() as c:
        return [tuple(z) for z in c.execute(text(f"SELECT {spalten} FROM employee_payroll_settings ORDER BY employee_id"))]


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine, mit_dublette=True)
    vorher = _zeilen(engine, False)
    abbruch = _alembic(url, "upgrade", MIGRATION)
    assert abbruch.returncode != 0 and "Personalnummer 91001: 2 Personen" in (abbruch.stdout + abbruch.stderr)
    assert VORHER in _ok(_alembic(url, "current")).stdout and _zeilen(engine, False) == vorher  # nichts geändert
    with engine.begin() as c:
        c.execute(text("UPDATE employee_payroll_settings SET datev_personnel_number = '91004' WHERE datev_personnel_number = '91001 '"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert [(n, bool(a), u) for n, a, u in _zeilen(engine, True)] == [
        ("91001", True, "alles"), ("91002", False, "nichts"), (None, True, "alles"), ("91004", True, "alles")]
    with engine.connect() as c:
        with pytest.raises(IntegrityError):
            c.execute(text("UPDATE employee_payroll_settings SET datev_personnel_number = '91001' WHERE datev_personnel_number = '91004'"))
    _ok(_alembic(url, "downgrade", VORHER))
    assert [(n, bool(a)) for n, a in _zeilen(engine, False)] == [("91001", True), ("91002", False), (None, True), ("91004", True)]
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'personalnummer.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_pnr_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_pruefabfrage_nur_lesen():
    """scripts/pruefabfrage_personalnummern.sql enthält nur SELECT (Regel 16) und dieselbe Formatregel wie das Programm."""
    from pathlib import Path
    sql = Path("scripts/pruefabfrage_personalnummern.sql").read_text(encoding="utf-8")
    anweisungen = [s.strip() for s in "\n".join(z for z in sql.splitlines() if not z.strip().startswith("--")).split(";") if s.strip()]
    assert len(anweisungen) == 3 and all(a.upper().startswith("SELECT") for a in anweisungen)
    assert "'^[1-9][0-9]{0,4}$'" in sql
    from app.time_backoffice import PERSONALNUMMER_FORMAT
    assert PERSONALNUMMER_FORMAT.pattern == "^[1-9][0-9]{0,4}$"
