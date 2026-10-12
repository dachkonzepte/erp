"""Migration 5db1a12b4a66 (Zahlungsstufe Z2a, seit 1.8.79): Kunde der Rechnung, Aufstellung an der Mahnung.

Bestand: jede nicht als Entwurf geführte Rechnung (versendet, storniert, Stornorechnung) bekommt den Kunden ihres Projekts, ein
Entwurf bleibt leer; Mahnungen bleiben ohne Aufstellung. Rückweg: entfernt beide Spalten -- verweigert, sobald eine
festgeschriebene Mahnung eine Aufstellung trägt (sie ginge verloren); die Aufstellung eines Entwurfs hält ihn nicht auf. Auf
einer Wegwerf-SQLite und (opt-in) einem Wegwerf-Schema der lokalen PostgreSQL."""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, insert, inspect, text
from sqlalchemy.orm import sessionmaker

from app.models import Invoice, Reminder
from tests.bestand_alt import auftrag
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "5db1a12b4a66"
VORHER = "c7d41e9a2b63"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
D = Decimal


def _rechnung(db, order, *, status, invoice_type="schluss", number=True, storno_of=None):
    """Rechnung wie im Bestand vor der Migration -- Core-Insert mit genau diesen Spalten (das ORM kennt schon customer_id)."""
    return db.execute(insert(Invoice.__table__).values(
        order_id=order.id, invoice_type=invoice_type, status=status, invoice_date=date(2026, 10, 1),
        due_date=date(2026, 10, 1), customer_name=order.customer_name, vat_rate=D("19"), storno_of_invoice_id=storno_of,
        invoice_number=f"R-ALT-{uuid.uuid4().hex[:6]}" if number else None,
    )).inserted_primary_key[0]


def _mahnung(db, invoice_id, status):
    return db.execute(insert(Reminder.__table__).values(
        invoice_id=invoice_id, level=1, status=status, reminder_date=date(2026, 10, 5), outstanding_amount=D("100"),
        fee_amount=D("5"), reminder_number=f"M-ALT-{uuid.uuid4().hex[:6]}" if status == "versendet" else None,
    )).inserted_primary_key[0]


def _spalten(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        # Seit 1.8.80 ohne Grunddaten und ORM (tests/bestand_alt.py).
        order = auftrag(db, number="0001")
        fremd = auftrag(db, number="0002")  # anderer Kunde
        kunde, kunde_fremd = order.customer_id, fremd.customer_id
        assert kunde != kunde_fremd
        ids = {
            "versendet": _rechnung(db, order, status="versendet"),
            "fremd": _rechnung(db, fremd, status="versendet"),
            "storniert": _rechnung(db, order, status="storniert"),
            "entwurf": _rechnung(db, order, status="entwurf", number=False),
        }
        ids["storno"] = _rechnung(db, order, status="versendet", invoice_type="storno", storno_of=ids["storniert"])
        gesendet = _mahnung(db, ids["versendet"], "versendet")
        entwurf = _mahnung(db, ids["fremd"], "entwurf")
        db.commit()
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        db = Session()
        kunden = dict(db.execute(text("SELECT id, customer_id FROM invoices")).all())
        assert {k: kunden[i] for k, i in ids.items()} == {
            "versendet": kunde, "fremd": kunde_fremd, "storniert": kunde, "entwurf": None, "storno": kunde}
        assert db.execute(text("SELECT COUNT(*) FROM reminders WHERE amounts_json IS NOT NULL")).scalar() == 0
        # Ein Entwurf mit Aufstellung hält den Rückweg nicht auf (er bekommt sie beim Festschreiben neu).
        db.execute(text("UPDATE reminders SET amounts_json = :a WHERE id = :i"), {"a": '{"format":1}', "i": entwurf})
        db.commit()
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        assert "customer_id" not in _spalten(engine, "invoices") and "amounts_json" not in _spalten(engine, "reminders")

        # Wieder hoch, eine festgeschriebene Mahnung mit Aufstellung -> Rückweg verweigert, nichts geändert.
        _ok(_alembic(url, "upgrade", MIGRATION))
        db = Session()
        db.execute(text("UPDATE reminders SET amounts_json = :a WHERE id = :i"), {"a": '{"format":1}', "i": gesendet})
        db.commit()
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 festgeschriebene Mahnungen" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        assert "customer_id" in _spalten(engine, "invoices") and "amounts_json" in _spalten(engine, "reminders")
    finally:
        engine.dispose()


def test_migration_holds_the_customer_of_finalized_invoices_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mahnwesen.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_holds_the_customer_of_finalized_invoices_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_z2a_{uuid.uuid4().hex[:8]}"
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
