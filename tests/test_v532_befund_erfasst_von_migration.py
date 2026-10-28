"""Migration 3e9b7c41d2a8 (seit 1.9.112): findings.created_by_user_id und created_by_name („erfasst von“ als Konto).
Bestand auf dem Stand davor (750d709a4863): ein Bericht mit einem Befund (Mitarbeiter als Ersteller). Hoch: der Befund unverändert, beide neuen Spalten
leer. Runter: alles exakt wie vorher. Wieder hoch, ein Befund mit Konto -> Rückweg verweigert, nichts geändert. Auf einer Wegwerf-SQLite und (opt-in)
einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests import bestand_alt
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "3e9b7c41d2a8"
VORHER = "750d709a4863"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
NEU = {"created_by_user_id", "created_by_name"}


def _spalten(engine):
    return {c["name"] for c in inspect(engine).get_columns("findings")}


def _stand(db, engine, *, ohne=False):
    columns = sorted(_spalten(engine) - (NEU if ohne else set()))
    rows = db.execute(text(f"SELECT {', '.join(columns)} FROM findings ORDER BY id")).all()
    return [tuple("" if v is None else str(v) for v in row) for row in rows]


def _bestand(db):
    auftrag = bestand_alt.auftrag(db, number="532")
    db.execute(text("INSERT INTO employees (id, first_name, last_name, employee_group, hourly_wage, weekly_hours, active, created_at, updated_at) "
                    "VALUES (901, 'Mia', 'Monteurin', 'angestellt', 30, 40, :t, '2026-09-01 08:00:00', '2026-09-01 08:00:00')"), {"t": True})
    db.execute(text("INSERT INTO service_reports (id, order_id, report_type, created_by_employee_id, performed_at, status, created_at, "
                    "updated_at) VALUES (901, :o, 'rapport', 901, '2026-10-20', 'entwurf', '2026-10-20 08:00:00', '2026-10-20 08:00:00')"),
               {"o": auftrag.id})
    db.execute(text("INSERT INTO findings (id, service_report_id, description, severity, action, status, created_by_employee_id, created_at, "
                    "updated_at) VALUES (901, 901, 'Ziegel gebrochen', 'mittel', 'buero_pruefen', 'offen', 901, '2026-10-20 08:00:00', "
                    "'2026-10-20 08:00:00')"))
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
        assert _stand(db, engine, ohne=True) == vorher
        assert db.execute(text("SELECT created_by_user_id, created_by_name FROM findings")).all() == [(None, None)]
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher and not (NEU & _spalten(engine))
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("UPDATE findings SET created_by_user_id = 7, created_by_name = 'Bea Büro'"))
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: ein Befund trägt das Konto" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_the_finding_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'befund_erfasst_von.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_the_finding_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_befund_{uuid.uuid4().hex[:8]}"
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
