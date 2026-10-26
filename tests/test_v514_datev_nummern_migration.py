"""Migration 750d709a4863 (seit 1.9.92): time_tracking_settings.datev_beraternummer und datev_mandantennummer.
Bestand auf dem Stand davor (c4f2a8e61d35): die Zeile der Zeiteinstellungen mit Lohnarten und Abschluss. Hoch: die Zeile unverändert, beide
neuen Spalten leer. Runter: alles exakt wie vorher. Wieder hoch, eine Beraternummer eingetragen -> Rückweg verweigert, nichts geändert. Auf einer
Wegwerf-SQLite und (opt-in) einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "750d709a4863"
VORHER = "c4f2a8e61d35"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
NEU = {"datev_beraternummer", "datev_mandantennummer"}


def _spalten(engine):
    return {c["name"] for c in inspect(engine).get_columns("time_tracking_settings")}


def _stand(db, engine, *, ohne=False):
    columns = sorted(_spalten(engine) - (NEU if ohne else set()))
    rows = db.execute(text(f"SELECT {', '.join(columns)} FROM time_tracking_settings ORDER BY id")).all()
    return [tuple("" if v is None else str(v) for v in row) for row in rows]


def _bestand(db):
    db.execute(text(
        "INSERT INTO time_tracking_settings (id, rounding_minutes, default_break_minutes, allow_manual_entries, allow_group_bookings, "
        "require_order_item, require_activity, datev_target, datev_wage_type_site, datev_wage_type_travel, locked_until, updated_at) "
        "VALUES (1, 15, 0, :t, :t, :f, :f, 'lodas', '100', '200', '2026-09-30', '2026-10-01 08:00:00')"), {"t": True, "f": False})
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
        assert _stand(db, engine, ohne=True) == vorher  # die Zeile unverändert
        assert db.execute(text("SELECT datev_beraternummer, datev_mandantennummer FROM time_tracking_settings")).all() == [(None, None)]
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher and not (NEU & _spalten(engine))
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("UPDATE time_tracking_settings SET datev_beraternummer = '1234567'"))
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: Berater- oder Mandantennummer ist eingetragen" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_the_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'datev_nummern.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_the_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_datev_{uuid.uuid4().hex[:8]}"
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
