"""Migration 4e7a9c2b6d58 (R4b Punkte 4 und 6, seit 1.8.86): invoice_deductions.open_amount/retained_open, invoices.closes_order.

Bestand auf dem Stand davor (8c2e5a7d4f19): Auftrag mit Position, festgeschriebener Abschlag, festgeschriebene Endrechnung mit Abzug
(ohne Zahlungshinweis), ein Entwurf. Hoch: jede Zeile unverändert, Abzug ohne Stand, keine Rechnung abschließend. Runter: alles exakt
wie vorher. Wieder hoch, eine abschließende Rechnung bzw. ein Stand -> Rückweg verweigert, nichts geändert. Auf einer Wegwerf-SQLite
und (opt-in) einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v386_nachtrag_migration import _bestand

MIGRATION = "4e7a9c2b6d58"
VORHER = "8c2e5a7d4f19"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
T = "2026-09-01 08:00:00"
TABELLEN = ("orders", "order_items", "invoices", "invoice_items", "invoice_deductions")
NEUE_SPALTEN = {"invoices": {"closes_order"}, "invoice_deductions": {"open_amount", "retained_open"}}


def _spalten(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _stand(db, engine, *, ohne=False):
    result = {}
    for table in TABELLEN:
        columns = sorted(_spalten(engine, table) - (NEUE_SPALTEN.get(table, set()) if ohne else set()))
        rows = db.execute(text(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")).all()
        result[table] = [tuple("" if v is None else str(v) for v in row) for row in rows]
    return result


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        order_id, abschlag_id = _bestand(db)
        schluss_id = db.execute(text(
            "INSERT INTO invoices (order_id, invoice_type, status, invoice_date, customer_name, vat_rate, invoice_number, "
            "created_at, updated_at) VALUES (:o, 'schluss', 'versendet', '2026-09-20', 'K', 19, 'R-ALT-2', :t, :t) RETURNING id"),
            {"o": order_id, "t": T}).scalar()
        db.execute(text("INSERT INTO invoice_deductions (invoice_id, deducted_invoice_id, sort_order, created_at) "
                        "VALUES (:s, :a, 10, :t)"), {"s": schluss_id, "a": abschlag_id, "t": T})
        db.commit()
        vorher = _stand(db, engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine, ohne=True) == vorher
        for table, columns in NEUE_SPALTEN.items():
            assert columns <= _spalten(engine, table)
        assert db.execute(text("SELECT count(*) FROM invoices WHERE closes_order = :ja"), {"ja": True}).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM invoice_deductions WHERE open_amount IS NOT NULL")).scalar() == 0
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher
        assert not (NEUE_SPALTEN["invoices"] & _spalten(engine, "invoices"))
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("UPDATE invoices SET closes_order = :ja WHERE id = :i"), {"ja": True, "i": abschlag_id})
        db.execute(text("UPDATE invoice_deductions SET open_amount = 10, retained_open = 0"))
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and ("Downgrade verweigert: 1 abschließende Rechnungen aus Aufwand, 1 Abzüge mit "
                                         "Zahlungshinweis") in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'zahlungshinweis.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_zahlhinweis_{uuid.uuid4().hex[:8]}"
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
