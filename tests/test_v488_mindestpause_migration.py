"""Migration c4f2a8e61d35 (seit 1.9.62): time_entries.min_break_minutes, die eingetragene Mindestpause einer Zeitbuchung.
Bestand auf dem Stand davor (b7e3d91c4a58): Auftrag, Mitarbeiter, zwei Zeitbuchungen (mit Uhrzeiten und Pause, eine Dauer). Hoch: jede
Zeile unverändert, die neue Spalte leer -- keine Buchung bekommt nachträglich einen Wert (dort gilt die abgezogene Pause). Runter: alles
exakt wie vorher. Wieder hoch, eine Buchung mit Wert -> Rückweg verweigert, nichts geändert. Auf einer Wegwerf-SQLite und (opt-in) einem
Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.bestand_alt import auftrag
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "c4f2a8e61d35"
VORHER = "b7e3d91c4a58"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
T = "2026-10-01 08:00:00"


def _spalten(engine):
    return {c["name"] for c in inspect(engine).get_columns("time_entries")}


def _stand(db, engine, *, ohne=False):
    columns = sorted(_spalten(engine) - ({"min_break_minutes"} if ohne else set()))
    rows = db.execute(text(f"SELECT {', '.join(columns)} FROM time_entries ORDER BY id")).all()
    return [tuple("" if v is None else str(v) for v in row) for row in rows]


def _bestand(db):
    order = auftrag(db, number="0001")
    emp = db.execute(text(
        "INSERT INTO employees (first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
        "VALUES ('Mia', 'Monteurin', 'gewerblich', 40, :a, :t, :t) RETURNING id"), {"a": True, "t": T}).scalar()
    for beginn, ende, pause, stunden in (("2026-10-01 07:00:00", "2026-10-01 16:15:00", 45, "8.5"), (None, None, 30, "4")):
        db.execute(text(
            "INSERT INTO time_entries (employee_id, project_id, order_id, work_date, entry_type, counts_as_productive, started_at, ended_at, "
            "break_minutes, hours, source, status, created_at, updated_at) "
            "VALUES (:e, :p, :o, '2026-10-01', 'site', :prod, :b, :en, :pause, :h, 'manual', 'booked', :t, :t)"),
            {"e": emp, "p": order.project_id, "o": order.id, "prod": True, "b": beginn, "en": ende, "pause": pause, "h": stunden, "t": T})
    db.commit()


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        _bestand(db)
        vorher = _stand(db, engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine, ohne=True) == vorher  # keine vorhandene Zeile geändert
        assert db.execute(text("SELECT count(*) FROM time_entries WHERE min_break_minutes IS NOT NULL")).scalar() == 0
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher and "min_break_minutes" not in _spalten(engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("UPDATE time_entries SET min_break_minutes = 45 WHERE started_at IS NOT NULL"))
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Zeitbuchungen mit eingetragener Mindestpause" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mindestpause.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_mindest_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _migrationsprobe(url, engine, sessionmaker(bind=engine))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
