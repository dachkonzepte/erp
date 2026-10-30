"""Migration b2c7f4e19a06 (seit 1.9.146, Stufe 6, R1, Punkt 4): jede Abwesenheit hat einen Antrag -- die ganze Kette über alembic, auf einem Bestand.

Bestand auf dem Stand davor (8d3f6a2c91e7): eine direkt auf der Tafel eingetragene Abwesenheit, eine aus einem genehmigten Antrag, ein offener Antrag. Hoch: genau ein genehmigter Antrag dazu, mit
Vermerk, Verweis und den Werten der Abwesenheit; die anderen Zeilen unverändert. Runter: genau dieser Antrag wieder weg, Abwesenheiten bleiben. Auf einer Wegwerf-SQLite und (opt-in) in einem
Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "b2c7f4e19a06"
VORHER = "8d3f6a2c91e7"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
MERKER = "Auf der Plantafel eingetragen (vor 1.9.146)"
JETZT = "2026-09-01 08:00:00"


def _bestand(engine) -> dict:
    """Core-Insert mit den Spalten dieses Stands, wie ein echter Bestand ihn hat."""
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, hourly_wage, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 20, 40, :an, :z, :z)"), {"an": True, "z": JETZT})
        mia = c.execute(text("SELECT id FROM employees")).scalar()

        def abwesenheit(art, kategorie, von, bis, notiz):
            c.execute(text("INSERT INTO employee_absences (employee_id, absence_type, absence_category, start_date, end_date, notes, created_at, updated_at) "
                           "VALUES (:e, :a, :k, :v, :b, :n, :z, :z)"), {"e": mia, "a": art, "k": kategorie, "v": von, "b": bis, "n": notiz, "z": JETZT})
            return c.execute(text("SELECT max(id) FROM employee_absences")).scalar()

        direkt = abwesenheit("Urlaub", "urlaub", "2026-11-02", "2026-11-06", "Sommer")
        genehmigt = abwesenheit("Krankheit", "krankheit", "2026-12-01", "2026-12-01", None)
        for von, status, verweis in (("2026-12-01", "approved", genehmigt), ("2027-01-04", "pending", None)):
            c.execute(text("INSERT INTO employee_absence_requests (employee_id, absence_type, absence_category, start_date, end_date, status, approved_absence_id, created_at, updated_at) "
                           "VALUES (:e, 'Krankheit', 'krankheit', :v, :v, :s, :a, :z, :z)"), {"e": mia, "v": von, "s": status, "a": verweis, "z": JETZT})
    return {"direkt": direkt, "genehmigt": genehmigt}


def _antraege(engine) -> list[tuple]:
    with engine.connect() as c:
        return [tuple(str(x) if x is not None else None for x in z) for z in c.execute(text(
            "SELECT status, absence_type, absence_category, start_date, end_date, notes, review_notes, requested_by_user_id, reviewed_by_user_id, approved_absence_id "
            "FROM employee_absence_requests ORDER BY id"))]


def _abwesenheiten(engine) -> int:
    with engine.connect() as c:
        return c.execute(text("SELECT count(*) FROM employee_absences")).scalar()


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    ids = _bestand(engine)
    vorher = _antraege(engine)
    assert len(vorher) == 2

    _ok(_alembic(url, "upgrade", MIGRATION))
    assert MIGRATION in _ok(_alembic(url, "current")).stdout
    nachher = _antraege(engine)
    assert nachher[:2] == vorher  # die vorhandenen unverändert
    assert len(nachher) == 3
    status, art, kategorie, von, bis, notiz, vermerk, antragsteller, entscheider, verweis = nachher[2]
    assert (status, art, kategorie, notiz, vermerk, antragsteller, entscheider, verweis) == ("approved", "Urlaub", "urlaub", "Sommer", MERKER, None, None, str(ids["direkt"]))
    assert von.startswith("2026-11-02") and bis.startswith("2026-11-06")
    assert _abwesenheiten(engine) == 2

    _ok(_alembic(url, "downgrade", VORHER))
    assert VORHER in _ok(_alembic(url, "current")).stdout
    assert _antraege(engine) == vorher
    assert _abwesenheiten(engine) == 2

    _ok(_alembic(url, "upgrade", "head"))
    assert len(_antraege(engine)) == 3


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'abwesenheiten.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_abw_{uuid.uuid4().hex[:8]}"
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
