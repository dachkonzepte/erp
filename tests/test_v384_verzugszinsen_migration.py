"""Migration a4c9e2f7b815 (Zahlungsstufe Z2b Punkte 7-9, seit 1.8.81): Basiszinssatz, Zinszeitraum und -berechnung an
Nebenforderungen, Zinsen im Entwurf, Zahlungen auf Nebenforderungen, Rechtstexte.

Vorgabe "Vorweg" 3 (1.8.81): auch gegen PostgreSQL mit Daten, nicht nur auf leerem Schema. Bestand auf dem Stand davor
(8e2f4b6d1c97): Auftrag, Rechnung, festgeschriebene Mahnung mit Aufstellung Format 2, Gebühr und Pauschale samt Gegenbuchung,
Verzugsbeginn, Zahlung mit Zuordnung. Hoch: jede Zeile unverändert, die neuen Spalten leer bzw. "nein", die neuen Tabellen leer.
Runter: alles exakt wie vorher. Wieder hoch, ein Basiszinssatz bzw. eine Zahlung auf eine Nebenforderung -> Rückweg verweigert,
nichts geändert. Auf einer Wegwerf-SQLite und (opt-in) einem Wegwerf-Schema der lokalen PostgreSQL."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.bestand_alt import auftrag
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "a4c9e2f7b815"
VORHER = "8e2f4b6d1c97"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
TABELLEN = ("orders", "invoices", "reminders", "invoice_charges", "invoice_default_starts", "payments", "payment_allocations")
NEUE_SPALTEN = {"invoice_charges": {"period_start", "period_end", "calculation_json"}, "reminders": {"interest_accepted"},
                "payment_allocations": {"charge_id"}}
T = "2026-09-01 08:00:00"


def _spalten(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _stand(db, engine, *, ohne=None):
    """Alle Zeilen der Tabellen, je Spalte (ohne die neuen), sortiert nach id -- Werte als Text verglichen."""
    result = {}
    for table in TABELLEN:
        columns = sorted(_spalten(engine, table) - (NEUE_SPALTEN.get(table, set()) if ohne else set()))
        rows = db.execute(text(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")).all()
        result[table] = [tuple("" if v is None else str(v) for v in row) for row in rows]
    return result


def _bestand(db):
    order = auftrag(db, number="0001")
    invoice_id = db.execute(text(
        "INSERT INTO invoices (order_id, customer_id, invoice_type, status, invoice_date, due_date, customer_name, vat_rate, "
        "invoice_number, created_at, updated_at) VALUES (:o, :c, 'schluss', 'versendet', '2026-09-01', '2026-09-15', 'K', 19, "
        "'R-ALT-1', :t, :t) RETURNING id"), {"o": order.id, "c": order.customer_id, "t": T}).scalar()
    amounts = ('{"charges":[{"amount":"10.00","kind":"gebuehr","label":"Mahngebühr (2. Mahnung M-ALT-2)"}],'
               '"charges_enabled":true,"charges_open":"10.00","dunnable":"1190.00","format":2,"gross":"1190.00",'
               '"payments":[],"retained":"0.00","skonto":"0.00","total":"1200.00"}')
    reminder_id = db.execute(text(
        "INSERT INTO reminders (reminder_number, invoice_id, level, status, reminder_date, new_due_date, outstanding_amount, "
        "fee_amount, amounts_json, fee_accepted, flat_fee_accepted, created_at, updated_at) VALUES ('M-ALT-2', :i, 2, "
        "'versendet', '2026-10-01', '2026-10-08', 1190, 10, :a, :ja, :nein, :t, :t) RETURNING id"),
        {"i": invoice_id, "a": amounts, "ja": True, "nein": False, "t": T}).scalar()
    fee = db.execute(text("INSERT INTO invoice_charges (invoice_id, kind, amount, reminder_id, created_at, created_by_name) "
                          "VALUES (:i, 'gebuehr', 10, :r, :t, 'Alt') RETURNING id"), {"i": invoice_id, "r": reminder_id, "t": T}).scalar()
    flat = db.execute(text("INSERT INTO invoice_charges (invoice_id, kind, amount, reminder_id, created_at, created_by_name) "
                           "VALUES (:i, 'pauschale', 40, :r, :t, 'Alt') RETURNING id"), {"i": invoice_id, "r": reminder_id, "t": T}).scalar()
    db.execute(text("INSERT INTO invoice_charges (invoice_id, kind, amount, reminder_id, reverses_charge_id, reason, created_at, "
                    "created_by_name) VALUES (:i, 'pauschale', -40, :r, :f, 'Kulanz', :t, 'Alt')"),
               {"i": invoice_id, "r": reminder_id, "f": flat, "t": T})
    db.execute(text("INSERT INTO invoice_default_starts (invoice_id, starts_on, basis, source_text, created_at, created_by_name) "
                    "VALUES (:i, '2026-09-20', 'mahnung', 'Zugang der 1. Mahnung', :t, 'Alt')"), {"i": invoice_id, "t": T})
    payment = db.execute(text("INSERT INTO payments (customer_id, received_on, amount, origin, created_at, created_by_name) "
                              "VALUES (:c, '2026-10-05', 500, 'erfasst', :t, 'Alt') RETURNING id"),
                         {"c": order.customer_id, "t": T}).scalar()
    db.execute(text("INSERT INTO payment_allocations (payment_id, invoice_id, kind, amount, created_at, created_by_name) "
                    "VALUES (:p, :i, 'zahlung', 500, :t, 'Alt')"), {"p": payment, "i": invoice_id, "t": T})
    db.commit()
    return invoice_id, payment, fee


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        invoice_id, payment_id, fee_id = _bestand(db)
        vorher = _stand(db, engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine, ohne=True) == vorher  # keine vorhandene Zeile geändert
        for table, columns in NEUE_SPALTEN.items():
            assert columns <= _spalten(engine, table)
        assert db.execute(text("SELECT count(*) FROM invoice_charges WHERE period_start IS NOT NULL OR period_end IS NOT NULL "
                               "OR calculation_json IS NOT NULL")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM reminders WHERE interest_accepted = :ja"), {"ja": True}).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM payment_allocations WHERE charge_id IS NOT NULL")).scalar() == 0
        for table in ("base_interest_rates", "dunning_legal_texts"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
        db.close()

        # Rückweg: alles exakt wie vorher.
        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher
        assert not (NEUE_SPALTEN["payment_allocations"] & _spalten(engine, "payment_allocations"))
        assert "base_interest_rates" not in inspect(engine).get_table_names()
        db.close()

        # Wieder hoch; ein Basiszinssatz, dann eine Zahlung auf die Gebühr -> Rückweg verweigert, nichts geändert.
        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("INSERT INTO base_interest_rates (half_year_start, rate_percent, updated_at) VALUES ('2026-07-01', 1.27, :t)"),
                   {"t": T})
        db.commit()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Basiszinssätze" in ausgabe, ausgabe[-1500:]
        db.execute(text("DELETE FROM base_interest_rates"))
        db.execute(text("INSERT INTO payment_allocations (payment_id, invoice_id, kind, amount, charge_id, created_at, "
                        "created_by_name) VALUES (:p, :i, 'nebenforderung', 10, :c, :t, 'Neu')"),
                   {"p": payment_id, "i": invoice_id, "c": fee_id, "t": T})
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "1 Zuordnungen auf Nebenforderungen" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'z2b_zinsen.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_zinsen_{uuid.uuid4().hex[:8]}"
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
