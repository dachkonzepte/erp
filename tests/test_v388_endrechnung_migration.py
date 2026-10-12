"""Migration 8c2e5a7d4f19 (R4b Punkt 2, seit 1.8.85): Tabelle invoice_deductions (Abzüge der Schlussrechnung als Endrechnung).

Bestand auf dem Stand davor (3b8f1d6c9e24): Auftrag mit Position, festgeschriebener Abschlag, festgeschriebene Schlussrechnung von
früher (Rest über die Menge), ein Entwurf. Hoch: jede Zeile unverändert, keine Abzüge -- die alte Schlussrechnung rechnet weiter aus
ihren Positionen. Runter: alles exakt wie vorher, Tabelle weg. Wieder hoch, ein Abzug -> Rückweg verweigert, nichts geändert. Auf
einer Wegwerf-SQLite und (opt-in) einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v386_nachtrag_migration import _bestand, _stand

MIGRATION = "8c2e5a7d4f19"
VORHER = "3b8f1d6c9e24"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
T = "2026-09-01 08:00:00"


def _tabellen(engine):
    return set(inspect(engine).get_table_names())


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        order_id, abschlag_id = _bestand(db)
        schluss_id = db.execute(text(
            "INSERT INTO invoices (order_id, invoice_type, status, invoice_date, customer_name, vat_rate, invoice_number, "
            "created_at, updated_at) VALUES (:o, 'schluss', 'versendet', '2026-09-20', 'K', 19, 'R-ALT-2', :t, :t) RETURNING id"),
            {"o": order_id, "t": T}).scalar()
        db.commit()
        vorher = _stand(db, engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher
        assert "invoice_deductions" in _tabellen(engine)
        assert db.execute(text("SELECT count(*) FROM invoice_deductions")).scalar() == 0
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher
        assert "invoice_deductions" not in _tabellen(engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("INSERT INTO invoice_deductions (invoice_id, deducted_invoice_id, sort_order, created_at) "
                        "VALUES (:s, :a, 10, :t)"), {"s": schluss_id, "a": abschlag_id, "t": T})
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Abzüge festgeschriebener Schlussrechnungen" in ausgabe, \
            ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
        assert db.execute(text("SELECT count(*) FROM invoice_deductions")).scalar() == 1
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'abzuege.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_abzuege_{uuid.uuid4().hex[:8]}"
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
