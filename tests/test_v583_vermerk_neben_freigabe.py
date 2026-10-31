"""Version 1.9.165 (Stufe 6, R2, Punkt 7): beim Löschen einer Abwesenheit bleibt die Freigabe-Notiz neben dem Vermerk stehen.

    Löschen    die Notiz des Admins bleibt in review_notes, der Vermerk des Programms steht daneben; bis 1.9.164 überschrieb er sie
    Bestand    Migration f1b9d2c6a470: was das Programm schrieb, wandert in vermerk; Notizen des Admins bleiben; downgrade() zurück
"""

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from app.absence_requests import ABWESENHEIT_GELOESCHT, MIGRATION_VERMERK, abwesenheit_loeschen, create_request, request_to_dict, review_request
from app.models import Employee
from tests.test_v133_invoices import db_session
from tests.test_v380_nummern_eindeutig import _alembic, _ok

TAG = date(2026, 11, 10)
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _genehmigt(db, notiz):
    emp = Employee(employee_number="M-1", first_name="Mia", last_name="Test", employee_group="gewerblich", weekly_hours=40, active=True)
    db.add(emp)
    db.commit()
    antrag = create_request(db, employee_id=emp.id, absence_type="Urlaub", absence_category="urlaub", start_date=TAG, end_date=TAG)
    return review_request(db, antrag.id, decision="approved", reviewed_by_user_id=None, review_notes=notiz)


def test_die_notiz_bleibt_neben_dem_vermerk():
    db = db_session()
    antrag = _genehmigt(db, "Vertretung geklärt")
    abwesenheit_loeschen(db, antrag.approved_absence_id)
    db.refresh(antrag)
    daten = request_to_dict(db, antrag)
    assert (daten["status"], daten["review_notes"], daten["vermerk"]) == ("cancelled", "Vertretung geklärt", ABWESENHEIT_GELOESCHT)


def test_ohne_notiz_nur_der_vermerk():
    db = db_session()
    antrag = _genehmigt(db, None)
    abwesenheit_loeschen(db, antrag.approved_absence_id)
    db.refresh(antrag)
    assert (antrag.review_notes, antrag.vermerk) == (None, ABWESENHEIT_GELOESCHT)


MIGRATION = "f1b9d2c6a470"
VORHER = "e3a7c4b95d18"
ZEIT = "2026-09-01 08:00:00"


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, hourly_wage, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 20, 40, :an, :z, :z)"), {"an": True, "z": ZEIT})
        mia = c.execute(text("SELECT id FROM employees")).scalar()
        for notiz in (MIGRATION_VERMERK, f"{MIGRATION_VERMERK}. {ABWESENHEIT_GELOESCHT}", ABWESENHEIT_GELOESCHT, "Vertretung geklärt", None):
            c.execute(text("INSERT INTO employee_absence_requests (employee_id, absence_type, absence_category, start_date, end_date, status, review_notes, created_at, updated_at) "
                           "VALUES (:e, 'Urlaub', 'urlaub', '2026-11-10', '2026-11-10', 'cancelled', :n, :z, :z)"), {"e": mia, "n": notiz, "z": ZEIT})

    def zeilen():
        with engine.connect() as c:
            return [tuple(z) for z in c.execute(text("SELECT review_notes, vermerk FROM employee_absence_requests ORDER BY id"))]

    _ok(_alembic(url, "upgrade", MIGRATION))
    assert zeilen() == [(None, MIGRATION_VERMERK), (None, f"{MIGRATION_VERMERK}. {ABWESENHEIT_GELOESCHT}"), (None, ABWESENHEIT_GELOESCHT), ("Vertretung geklärt", None), (None, None)]
    with engine.begin() as c:
        c.execute(text("UPDATE employee_absence_requests SET vermerk = :g WHERE review_notes = 'Vertretung geklärt'"), {"g": ABWESENHEIT_GELOESCHT})
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        rueck = c.execute(text("SELECT review_notes FROM employee_absence_requests ORDER BY id")).scalars().all()
    assert rueck == [MIGRATION_VERMERK, f"{MIGRATION_VERMERK}. {ABWESENHEIT_GELOESCHT}", ABWESENHEIT_GELOESCHT, "Vertretung geklärt", None]  # die Notiz des Admins geht vor
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'vermerk.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_verm_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
