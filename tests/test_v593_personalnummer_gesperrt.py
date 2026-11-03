"""Version 1.9.177 (L1a-Nachtrag, Punkt 4, Vorgabe Tobias 03.11.2026): eine Personalnummer bleibt der Person, der sie einmal gehörte.

    gesperrt      eine Nummer, die einer Person einmal gehört hat, bekommt keine andere -- auch nach Austritt und nach einem Nummernwechsel
                  (LIESMICH 8: 91008 -> 91016); dieselbe Person bekommt ihre frühere Nummer wieder (bis 1.9.176 war die alte Nummer nach einem
                  Wechsel frei, Festlegung 1.9.168 Nr. 3)
    gemerkt       PersonalnummerVergabe, beim Speichern der Lohnstammdaten und bei „DATEV-Nr. = ERP-Nr.“ der Mitarbeiternummer; nie gelöscht
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.models import EmployeePayrollSettings, PersonalnummerVergabe, TimeBackofficeAdvancedSettings
from app.routers import employees as employees_router
from app.routers import time_backoffice as time_backoffice_router
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "1e425fe7faa6"
VORHER = "2474667579d8"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
GESPERRT = "Die Personalnummer {n} gehörte schon {name} – eine Personalnummer bleibt dauerhaft gesperrt, auch nach Austritt und Nummernwechsel."


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def _client(w, rolle="buero_finanzen"):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, employees_router.router, role=rolle)


def _put(w, emp, **koerper):
    return _client(w).put(f"/api/time-backoffice/payroll-employees/{emp.id}", json=koerper)


def _gemerkt(w):
    w["db"].expire_all()
    return sorted((v.nummer, v.employee_id) for v in w["db"].query(PersonalnummerVergabe))


def test_nummernwechsel_sperrt_die_alte_nummer(welt):
    """Mia 91008 -> 91016 (wie LIESMICH 8): Tom bekommt 91008 nicht, Mia bekommt sie wieder."""
    mia, tom = welt["mia"], welt["tom"]
    assert _put(welt, mia, datev_personnel_number="91008").status_code == 200
    r = _put(welt, mia, datev_personnel_number="91016")
    assert (r.status_code, r.json()["fruehere_personalnummern"]) == (200, ["91008"])
    r = _put(welt, tom, datev_personnel_number="91008")
    assert (r.status_code, r.json()["detail"]) == (422, GESPERRT.format(n="91008", name="Mia Monteurin"))
    welt["db"].expire_all()
    assert welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=tom.id).count() == 0
    r = _put(welt, mia, datev_personnel_number="91008")
    assert (r.status_code, r.json()["fruehere_personalnummern"]) == (200, ["91016"])
    assert _gemerkt(welt) == [("91008", mia.id), ("91016", mia.id)]


def test_nach_austritt_und_geleerter_nummer_gesperrt(welt):
    mia, tom = welt["mia"], welt["tom"]
    assert _put(welt, mia, datev_personnel_number="91008").status_code == 200
    assert _put(welt, mia, datev_personnel_number=None, austritt="2026-10-31", export_umfang="nichts").status_code == 200
    assert _put(welt, tom, datev_personnel_number="91008").json()["detail"] == GESPERRT.format(n="91008", name="Mia Monteurin")
    zeilen = _client(welt).get("/api/time-backoffice/payroll-employees").json()
    assert {z["employee_name"]: z["fruehere_personalnummern"] for z in zeilen} == {"Mia Monteurin": ["91008"], "Tom Monteur": []}


def test_eine_nummer_einmal_in_der_datenbank(welt):
    db = welt["db"]
    db.add(PersonalnummerVergabe(nummer="91001", employee_id=welt["mia"].id))
    db.commit()
    db.add(PersonalnummerVergabe(nummer="91001", employee_id=welt["tom"].id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def _mitarbeiter_put(client, emp_id, **aenderung):
    stand = client.get(f"/api/employees/{emp_id}").json()
    koerper = {k: v for k, v in stand.items() if k not in ("id", "function_name", "effective_hourly_wage", "annual_gross_wage")}
    return client.put(f"/api/employees/{emp_id}", json={**koerper, **aenderung})


def test_gleichsetzung_sperrt_die_mitarbeiternummer(welt):
    """„DATEV-Nr. = ERP-Nr.“: Mia 91001 -> 91002 über das Mitarbeiterformular; 91001 bekommt weder Tom noch ein neuer Mitarbeiter."""
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    client = _client(welt)
    assert _mitarbeiter_put(client, mia.id, employee_number="91001").status_code == 200
    assert _mitarbeiter_put(client, mia.id, employee_number="91002").status_code == 200
    assert _gemerkt(welt) == [("91001", mia.id), ("91002", mia.id), ("M-1", mia.id)]  # „M-1“ war ihre bisherige Nummer
    r = _mitarbeiter_put(client, tom.id, employee_number="91001")
    assert (r.status_code, r.json()["detail"]) == (409, GESPERRT.format(n="91001", name="Mia Monteurin"))
    neu = {k: v for k, v in client.get(f"/api/employees/{tom.id}").json().items()
           if k not in ("id", "function_name", "effective_hourly_wage", "annual_gross_wage")}
    r = client.post("/api/employees", json={**neu, "employee_number": "91001", "first_name": "Lea"})
    assert (r.status_code, r.json()["detail"]) == (409, GESPERRT.format(n="91001", name="Mia Monteurin"))
    assert _mitarbeiter_put(client, mia.id, employee_number="91001").status_code == 200  # Mias eigene Nummer


def test_ohne_gleichsetzung_bleibt_die_mitarbeiternummer_frei(welt):
    client = _client(welt)
    assert _mitarbeiter_put(client, welt["mia"].id, employee_number="M-9").status_code == 200
    assert _gemerkt(welt) == []


def test_pruefskript_nennt_die_gemerkten_nummern(welt):
    from tests.test_v590_pruefe_zeitregeln import _skript
    from datetime import date
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    assert _put(welt, mia, datev_personnel_number="91008").status_code == 200
    assert _put(welt, mia, datev_personnel_number="91016").status_code == 200
    db.add(EmployeePayrollSettings(employee_id=tom.id, datev_personnel_number="91008"))  # an der Sperre vorbei, wie von Hand in der Datenbank
    db.commit()
    zeilen = []
    assert _skript().main([], sitzung=db, ausgabe=zeilen.append, heute=date(2026, 11, 10)) == 1
    assert "  Personalnummern gemerkt (dauerhaft gesperrt): 2, davon bei keiner aktiven Person: 0" in zeilen
    assert f"  ! Personalnummer 91008 gehörte Person {mia.id}, heute trägt sie Person {tom.id}." in zeilen


# --- Migration 1e425fe7faa6 -----------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        for nr, (erp, datev) in enumerate([("91001", " 91008 "), ("91002", ""), ("91003", None)], 1):
            c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, "
                           "updated_at) VALUES (:e, :v, 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"e": erp, "v": f"P{nr}", "a": True})
            c.execute(text("INSERT INTO employee_payroll_settings (employee_id, datev_personnel_number, payroll_export_enabled, export_umfang, updated_at) "
                           "VALUES ((SELECT id FROM employees WHERE employee_number = :e), :d, :a, 'alles', '2026-09-01')"), {"e": erp, "d": datev, "a": True})
        c.execute(text("INSERT INTO time_backoffice_advanced_settings (id, datev_personnel_equals_erp_number, updated_at) VALUES (1, :g, '2026-09-01')"),
                  {"g": True})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        zeilen = c.execute(text("SELECT v.nummer, e.first_name FROM personalnummern_vergeben v JOIN employees e ON e.id = v.employee_id "
                                "ORDER BY v.nummer")).all()
        assert [tuple(z) for z in zeilen] == [("91001", "P1"), ("91002", "P2"), ("91003", "P3"), ("91008", "P1")]
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM employee_payroll_settings")).scalar() == 3
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'personalnummern.db').as_posix()}"
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
