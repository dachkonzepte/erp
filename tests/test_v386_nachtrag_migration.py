"""Migration 3b8f1d6c9e24 (R4a Punkte 3 und 5, seit 1.8.83): order_items.is_addendum, invoices.finalized_at.

Bestand auf dem Stand davor (6d1e8b3f2a47): Auftrag mit Position, festgeschriebene Rechnung mit Rechnungsposition, ein Entwurf.
Hoch: jede Zeile unverändert, keine Position ist ein Nachtrag, keine Rechnung hat einen Zeitpunkt. Runter: alles exakt wie vorher.
Wieder hoch, ein Nachtrag bzw. ein Zeitpunkt -> Rückweg verweigert, nichts geändert. Auf einer Wegwerf-SQLite und (opt-in) einem
Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.bestand_alt import auftrag
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "3b8f1d6c9e24"
VORHER = "6d1e8b3f2a47"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
TABELLEN = ("orders", "order_items", "invoices", "invoice_items")
NEUE_SPALTEN = {"order_items": {"is_addendum"}, "invoices": {"finalized_at"}}
T = "2026-09-01 08:00:00"


def _spalten(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _stand(db, engine, *, ohne=False):
    result = {}
    for table in TABELLEN:
        columns = sorted(_spalten(engine, table) - (NEUE_SPALTEN.get(table, set()) if ohne else set()))
        rows = db.execute(text(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")).all()
        result[table] = [tuple("" if v is None else str(v) for v in row) for row in rows]
    return result


def _bestand(db):
    order = auftrag(db, number="0001")
    item_id = db.execute(text(
        "INSERT INTO order_items (order_id, sort_order, position_number, position_type, short_text, long_text, quantity, unit, "
        "unit_price, include_in_total) VALUES (:o, 10, '1', 'normal', 'Eindecken', '', 100, 'm2', 50, :ja) RETURNING id"),
        {"o": order.id, "ja": True}).scalar()
    invoice_id = db.execute(text(
        "INSERT INTO invoices (order_id, customer_id, invoice_type, status, invoice_date, due_date, customer_name, vat_rate, "
        "invoice_number, created_at, updated_at) VALUES (:o, :c, 'abschlag_leistungsstand', 'versendet', '2026-09-01', "
        "'2026-09-15', 'K', 19, 'R-ALT-1', :t, :t) RETURNING id"), {"o": order.id, "c": order.customer_id, "t": T}).scalar()
    db.execute(text(
        "INSERT INTO invoice_items (invoice_id, source_order_item_id, sort_order, position_number, short_text, long_text, unit, "
        "unit_price, soll_quantity, ist_quantity, billed_quantity, billed_total) VALUES (:i, :s, 10, '1', 'Eindecken', '', "
        "'m2', 50, 100, 40, 40, 2000)"), {"i": invoice_id, "s": item_id})
    db.execute(text("INSERT INTO invoices (order_id, invoice_type, status, invoice_date, customer_name, vat_rate, created_at, "
                    "updated_at) VALUES (:o, 'schluss', 'entwurf', '2026-09-02', 'K', 19, :t, :t)"), {"o": order.id, "t": T})
    db.commit()
    return order.id, invoice_id


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        order_id, invoice_id = _bestand(db)
        vorher = _stand(db, engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine, ohne=True) == vorher
        for table, columns in NEUE_SPALTEN.items():
            assert columns <= _spalten(engine, table)
        assert db.execute(text("SELECT count(*) FROM order_items WHERE is_addendum = :ja"), {"ja": True}).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM invoices WHERE finalized_at IS NOT NULL")).scalar() == 0
        # Pflichtspalte mit Vorgabe: eine neue Position ohne Angabe ist kein Nachtrag
        db.execute(text("INSERT INTO order_items (order_id, sort_order, position_number, position_type, short_text, long_text, "
                        "quantity, unit, unit_price, include_in_total) VALUES (:o, 20, '2', 'normal', 'Neu', '', 1, 'Stk', 1, "
                        ":ja)"), {"o": order_id, "ja": True})
        assert db.execute(text("SELECT is_addendum FROM order_items WHERE position_number = '2'")).scalar() in (False, 0)
        db.execute(text("DELETE FROM order_items WHERE position_number = '2'"))
        db.commit()
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher
        assert not (NEUE_SPALTEN["order_items"] & _spalten(engine, "order_items"))
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("UPDATE invoices SET finalized_at = :t WHERE id = :i"), {"t": T, "i": invoice_id})
        db.execute(text("UPDATE order_items SET is_addendum = :ja"), {"ja": True})
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Nachträge, 1 Rechnungen mit Zeitpunkt" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'nachtrag.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_nachtrag_{uuid.uuid4().hex[:8]}"
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
