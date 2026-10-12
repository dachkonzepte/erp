"""Migration 8e2f4b6d1c97 (Zahlungsstufe Z2b, seit 1.8.80): Kunde am Auftrag, Mahnung ersetzen, Mahngebühren und Pauschale.

Bestand: jeder Auftrag bekommt den Kunden seines Projekts (auch einer, dessen Kunde am Projekt nach dem Beauftragen gewechselt wurde
-- den findet scripts/pruefabfrage_auftrag_kunde.sql); die Gebühr 5,00 € der Stufe 1 wird 0,00 €, die drei Standard-Mahntexte
werden ersetzt, ein geänderter Text bleibt; der Schalter steht aus. Rückweg: alles exakt wie vorher -- verweigert, sobald eine
Nebenforderung (oder Verzugsbeginn, Kundenwechsel am Auftrag, ersetzte Mahnung) besteht. Auf einer Wegwerf-SQLite und (opt-in)
einem Wegwerf-Schema der lokalen PostgreSQL."""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.reminders import DEFAULT_REMINDER_LEVELS
from tests.bestand_alt import auftrag
from tests.test_v380_nummern_eindeutig import _alembic, _ok

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = "8e2f4b6d1c97"
VORHER = "5db1a12b4a66"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _migration():
    path = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_1880_nebenforderungen", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migrations_new_texts_are_the_defaults_of_today():
    """Die Migration ersetzt die alten Standardtexte durch genau die heutigen (app/reminders.py::DEFAULT_REMINDER_LEVELS)."""
    m = _migration()
    assert m.NEW_TEXTS == {level: text_ for level, _, _, _, text_ in DEFAULT_REMINDER_LEVELS}
    assert all("{mahngebuehr}" in t for t in m.OLD_TEXTS.values())


def _spalten(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _stufen(db):
    return {level: (text_, float(fee)) for level, text_, fee in
            db.execute(text("SELECT level, text_template, fee_amount FROM reminder_levels ORDER BY level")).all()}


def _migrationsprobe(url: str, engine, Session) -> None:
    m = _migration()
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        order = auftrag(db, number="0001")
        gewechselt = auftrag(db, number="0002")
        anderer = auftrag(db, number="0003")
        # Kunde am Projekt nach dem Beauftragen gewechselt (bis 1.8.79 ohne Rechnung möglich)
        db.execute(text("UPDATE projects SET customer_id = :c WHERE id = :p"),
                   {"c": anderer.customer_id, "p": gewechselt.project_id})
        for level, text_, fee in ((1, m.OLD_TEXTS[1], 5), (2, "Eigener Text {mahngebuehr}", 10), (3, m.OLD_TEXTS[3], 15)):
            db.execute(text("INSERT INTO reminder_levels (level, label, days_after_previous_step, fee_amount, text_template, "
                            "active, sort_order, created_at) VALUES (:l, :lbl, 7, :f, :t, :a, :s, '2026-09-01 00:00:00')"),
                       {"l": level, "lbl": f"{level}. Mahnung", "f": fee, "t": text_, "a": True, "s": level * 10})
        db.commit()
        vorher = _stufen(db)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        db = Session()
        kunden = dict(db.execute(text("SELECT id, customer_id FROM orders")).all())
        assert kunden == {order.id: order.customer_id, gewechselt.id: anderer.customer_id, anderer.id: anderer.customer_id}
        assert _stufen(db) == {1: (m.NEW_TEXTS[1], 0.0), 2: ("Eigener Text {mahngebuehr}", 10.0), 3: (m.NEW_TEXTS[3], 15.0)}
        for table in ("invoice_charges", "invoice_default_starts", "order_customer_changes"):
            assert table in inspect(engine).get_table_names()
        assert {"replaced_by_id", "fee_accepted", "flat_fee_accepted"} <= _spalten(engine, "reminders")
        # Prüfabfrage: findet genau den Auftrag mit dem alten Namen im Schnappschuss
        sql = (ROOT / "scripts" / "pruefabfrage_auftrag_kunde.sql").read_text(encoding="utf-8")
        erste = sql[sql.index("SELECT"):sql.index(";") + 1]
        assert [r[0] for r in db.execute(text(erste)).all()] == ["AU-0002"]
        db.close()

        # Rückweg: alles exakt wie vorher.
        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stufen(db) == vorher
        assert "customer_id" not in _spalten(engine, "orders") and "invoice_charges" not in inspect(engine).get_table_names()
        assert "dunning_charges_enabled" not in _spalten(engine, "general_settings")
        db.close()

        # Wieder hoch, eine Nebenforderung -> Rückweg verweigert, nichts geändert.
        _ok(_alembic(url, "upgrade", MIGRATION))
        db = Session()
        invoice_id = db.execute(text(
            "INSERT INTO invoices (order_id, invoice_type, status, invoice_date, customer_name, vat_rate, invoice_number, "
            "created_at, updated_at) VALUES (:o, 'schluss', 'versendet', '2026-09-01', 'K', 19, 'R-ALT-1', "
            "'2026-09-01 00:00:00', '2026-09-01 00:00:00') RETURNING id"), {"o": order.id}).scalar()
        db.execute(text("INSERT INTO invoice_charges (invoice_id, kind, amount, created_at, created_by_name) "
                        "VALUES (:i, 'gebuehr', 10, '2026-10-01 00:00:00', 'Test')"), {"i": invoice_id})
        db.commit()
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Nebenforderungen" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        assert "customer_id" in _spalten(engine, "orders")
    finally:
        engine.dispose()


def test_migration_holds_the_customer_of_orders_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'z2b.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_holds_the_customer_of_orders_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_z2b_{uuid.uuid4().hex[:8]}"
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
