"""Eindeutige Nummer als Datenbank-Bedingung für alle sieben Nummernkreise (seit 1.8.77, docs/archiv/befund-vor-echtbetrieb.md
"Umsetzung 1.8.77").

- Kunde, Anfrage, Projekt, Angebot, Auftrag: eindeutig seit der Baseline (2befd7907eef); Rechnung und Mahnung seit der Migration
  f3a8c2d6b190 (uq_invoice_number, uq_reminder_number). Entwürfe ohne Nummer (NULL) bleiben beliebig viele erlaubt.
- Die Migration sucht vorher selbst nach mehrfach vergebenen Nummern (und fehlenden alten Bedingungen) und bricht mit einer Liste
  ab, ohne etwas zu ändern -- statt mit einem Datenbankfehler mitten im Anlegen.

Angriffe: eine Nummer ein zweites Mal speichern, am Nummernkreis vorbei (je Nummernkreis, SQLite und PostgreSQL); die Vergabe
liefert eine schon vergebene Nummer (Rechnung, Storno, Mahnung über den App-Weg); zwei Sitzungen schreiben gleichzeitig dieselbe
Nummer (PostgreSQL); Migration auf einem Bestand mit Dubletten (SQLite, PostgreSQL) bzw. ohne eine der alten Bedingungen.

Die Tests mit pg/pg_sitzung laufen gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in, sonst übersprungen)."""

import importlib.util
import itertools
import os
import subprocess
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import UniqueConstraint, create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.grunddaten import anlegen
from app.invoices import create_schlussrechnung, create_storno_draft, finalize_and_send_invoice
from app.models import Customer, CustomerProfile, Inquiry, Invoice, Order, Project, Quote, Reminder
from app.project_pipeline_columns import default_pipeline_column_id
from app.reminders import create_reminder, finalize_and_send_reminder
from app.settings import DEFAULT_SEQUENCES, _existing_column
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = "f3a8c2d6b190"
VORHER = "9b4e2c7a1d58"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")

BEDINGUNG = {
    "customer": "uq_customer_number", "inquiry": "uq_inquiry_number", "project": "uq_project_number",
    "quote": "uq_quote_number", "order": "uq_order_number", "invoice": "uq_invoice_number", "reminder": "uq_reminder_number",
}


def _db():
    db = db_session()
    anlegen(db)
    db.commit()
    return db


def _migration():
    path = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_1877_nummern_eindeutig", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LAUF = itertools.count(1)


def _mit_nummer(db, key: str, nummer: str | None) -> int:
    """Einen Datensatz des Nummernkreises key mit genau dieser Nummer speichern (flush) -- am Nummernkreis vorbei, wie ein
    Import, ein Skript oder ein Fehler in der Vergabe. Hilfsdatensätze tragen eigene Nummern außerhalb jedes Formats (X-…) und
    echte Fremdschlüssel (PostgreSQL prüft sie). Gibt die ID des Datensatzes mit der Nummer zurück; nummer None = Entwurf
    (nur Rechnung und Mahnung)."""
    n = f"{next(_LAUF)}-{uuid.uuid4().hex[:6]}"
    customer = Customer(name="Kunde", last_name="Kunde")
    db.add(customer); db.flush()
    if key == "customer":
        row = CustomerProfile(customer_id=customer.id, customer_number=nummer)
        db.add(row); db.flush()
        return row.id
    if key == "inquiry":
        row = Inquiry(inquiry_number=nummer, customer_id=customer.id, title="Anfrage")
        db.add(row); db.flush()
        return row.id
    project = Project(project_number=nummer if key == "project" else f"X-P-{n}", name="P", customer_id=customer.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.flush()
    if key == "project":
        return project.id
    quote = Quote(quote_number=nummer if key == "quote" else f"X-A-{n}", project_id=project.id, title="A")
    db.add(quote); db.flush()
    if key == "quote":
        return quote.id
    order = Order(order_number=nummer if key == "order" else f"X-AUF-{n}", project_id=project.id, source_quote_id=quote.id,
                  quote_number_snapshot=quote.quote_number, title="T", customer_name="Kunde")
    db.add(order); db.flush()
    if key == "order":
        return order.id
    invoice = Invoice(order_id=order.id, invoice_type="schluss", customer_name="K", vat_rate=Decimal("19"),
                      status=("versendet" if nummer else "entwurf") if key == "invoice" else "versendet",
                      invoice_number=nummer if key == "invoice" else f"X-R-{n}")
    db.add(invoice); db.flush()
    if key == "invoice":
        return invoice.id
    row = Reminder(invoice_id=invoice.id, level=1, status="versendet" if nummer else "entwurf", reminder_number=nummer,
                   reminder_date=date(2026, 10, 1), outstanding_amount=Decimal("1"), fee_amount=Decimal("0"))
    db.add(row); db.flush()
    return row.id


def _anzahl(db, key: str, nummer: str) -> int:
    column = _existing_column(key)
    return db.scalar(select(func.count()).select_from(column.table).where(column == nummer))


# ---------------------------------------------------------------------------
# Struktur: jeder Nummernkreis hat seine Bedingung, die Migration kennt alle sieben
# ---------------------------------------------------------------------------

def test_every_number_sequence_is_unique_in_the_model():
    """Ein achter Nummernkreis (DEFAULT_SEQUENCES + _existing_column()) ohne Bedingung fiele hier auf."""
    for key in DEFAULT_SEQUENCES:
        column = _existing_column(key)
        assert column is not None, f"Nummernkreis {key} ohne Spalte in _existing_column()"
        bedingungen = {con.name: [c.name for c in con.columns] for con in column.table.constraints
                       if isinstance(con, UniqueConstraint)}
        assert bedingungen.get(BEDINGUNG[key]) == [column.name], (key, bedingungen)


def test_migration_covers_exactly_the_seven_number_sequences():
    mig = _migration()
    assert mig.down_revision == VORHER
    in_migration = sorted((table, column, uq) for _label, table, column, uq, _neu in mig.NUMMERNKREISE)
    im_code = sorted((_existing_column(k).table.name, _existing_column(k).name, BEDINGUNG[k]) for k in DEFAULT_SEQUENCES)
    assert in_migration == im_code
    assert sorted(table for _l, table, _c, _u, neu in mig.NUMMERNKREISE if neu) == ["invoices", "reminders"]


# ---------------------------------------------------------------------------
# Angriff: dieselbe Nummer ein zweites Mal speichern, am Nummernkreis vorbei
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(DEFAULT_SEQUENCES))
def test_a_number_cannot_be_stored_twice(key):
    db = _db()
    _mit_nummer(db, key, "N-2026-0001")
    db.commit()
    with pytest.raises(IntegrityError) as exc:
        _mit_nummer(db, key, "N-2026-0001")
    db.rollback()
    column = _existing_column(key)
    assert f"{column.table.name}.{column.name}" in str(exc.value)  # SQLite: "UNIQUE constraint failed: <Tabelle>.<Spalte>"
    assert _anzahl(db, key, "N-2026-0001") == 1
    _mit_nummer(db, key, "N-2026-0002")  # eine andere Nummer geht
    db.commit()


def test_pg_a_number_cannot_be_stored_twice():
    with pg_sitzung("nr_eindeutig") as db:
        for key in sorted(DEFAULT_SEQUENCES):
            _mit_nummer(db, key, "N-2026-0001")
            db.commit()
            with pytest.raises(IntegrityError) as exc:
                _mit_nummer(db, key, "N-2026-0001")
            db.rollback()
            assert BEDINGUNG[key] in str(exc.value), key  # PostgreSQL nennt die Bedingung
            assert _anzahl(db, key, "N-2026-0001") == 1, key


def _entwuerfe_ohne_nummer(db) -> None:
    for _ in range(3):
        _mit_nummer(db, "invoice", None)
        _mit_nummer(db, "reminder", None)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.invoice_number.is_(None))) == 3
    assert db.scalar(select(func.count()).select_from(Reminder).where(Reminder.reminder_number.is_(None))) == 3


def test_drafts_without_number_stay_allowed():
    _entwuerfe_ohne_nummer(_db())


def test_pg_drafts_without_number_stay_allowed():
    with pg_sitzung("nr_entwurf") as db:
        _entwuerfe_ohne_nummer(db)


# ---------------------------------------------------------------------------
# Angriff: die Vergabe liefert eine schon vergebene Nummer -- die Datenbank lehnt ab, nichts bleibt halb
# ---------------------------------------------------------------------------

def _storno_mit_vergebener_nummer(db, order, monkeypatch):
    original = festschreiben(db, create_schlussrechnung(db, order))
    storno = mit_zeitraum(db, create_storno_draft(db, original))
    original_id, storno_id, nummer = original.id, storno.id, original.invoice_number
    monkeypatch.setattr("app.invoices.issue_number", lambda _db, key: nummer)
    with pytest.raises(IntegrityError) as exc:
        finalize_and_send_invoice(db, storno)
    db.rollback()
    db.expire_all()
    original, storno = db.get(Invoice, original_id), db.get(Invoice, storno_id)
    # nichts halb: das Storno bleibt Entwurf ohne Nummer, das Original wird nicht "storniert"
    assert (storno.status, storno.invoice_number) == ("entwurf", None)
    assert (original.status, original.invoice_number) == ("versendet", nummer)
    return str(exc.value)


def test_issuing_an_issued_invoice_number_is_refused_and_nothing_changes(monkeypatch):
    db = _db()
    order, _ = make_order_with_item(db)
    assert "invoices.invoice_number" in _storno_mit_vergebener_nummer(db, order, monkeypatch)


def test_pg_issuing_an_issued_invoice_number_is_refused_and_nothing_changes(pg, monkeypatch):
    Session, order_id = pg
    db = Session()
    try:
        assert "uq_invoice_number" in _storno_mit_vergebener_nummer(db, db.get(Order, order_id), monkeypatch)
    finally:
        db.close()


def test_issuing_an_issued_reminder_number_is_refused_and_nothing_changes(monkeypatch):
    db = _db()
    invoice = make_sent_overdue_invoice(db, days_overdue=40)
    erste = finalize_and_send_reminder(db, create_reminder(db, invoice, 1))
    zweite = create_reminder(db, invoice, 2)
    zweite_id, nummer = zweite.id, erste.reminder_number
    monkeypatch.setattr("app.reminders.issue_number", lambda _db, key: nummer)
    with pytest.raises(IntegrityError) as exc:
        finalize_and_send_reminder(db, zweite)
    db.rollback()
    assert "reminders.reminder_number" in str(exc.value)
    zweite = db.get(Reminder, zweite_id)
    assert (zweite.status, zweite.reminder_number) == ("entwurf", None)


# ---------------------------------------------------------------------------
# Angriff: zwei Sitzungen schreiben gleichzeitig dieselbe Nummer (so entstanden bis 1.8.72 Dubletten)
# ---------------------------------------------------------------------------

def test_pg_two_sessions_writing_the_same_number_at_once(pg):
    """Die erste hält ihren Commit eine Sekunde an; die zweite wartet am Eindeutigkeitsindex und wird danach abgelehnt --
    auch ohne die Sperre des Nummernkreises (issue_number()) entsteht keine Dublette."""
    Session, order_id = pg

    def zwei_entwuerfe(s):
        ids = []
        for _ in range(2):
            draft = Invoice(order_id=order_id, invoice_type="aufwand", status="entwurf", customer_name="K",
                            vat_rate=Decimal("19"))
            s.add(draft); s.flush()
            ids.append(draft.id)
        s.commit()
        return ids
    erste_id, zweite_id = _vorbereiten(Session, zwei_entwuerfe)

    def nummer_setzen(invoice_id):
        def action(s):
            invoice = s.get(Invoice, invoice_id)
            invoice.invoice_number, invoice.status = "R-2026-0777", "versendet"
            s.commit()
            return invoice_id
        return action

    first, second = _run(Session, nummer_setzen(erste_id), nummer_setzen(zweite_id))
    assert first == erste_id
    assert isinstance(second, IntegrityError) and "uq_invoice_number" in str(second), second
    stand = _vorbereiten(Session, lambda s: {i.id: (i.status, i.invoice_number) for i in s.scalars(select(Invoice))})
    assert stand[erste_id] == ("versendet", "R-2026-0777")
    assert stand[zweite_id] == ("entwurf", None)


# ---------------------------------------------------------------------------
# Migration: vorher nach Dubletten suchen, mit Liste abbrechen, nichts ändern
# ---------------------------------------------------------------------------

def _alembic(url: str, *args: str):
    env = dict(os.environ, DATABASE_URL=url, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=str(ROOT), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600)


def _ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def _eindeutig(engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    return [column] in [c["column_names"] for c in insp.get_unique_constraints(table)]


def _migrationsprobe(url: str, engine, Session) -> None:
    """Gemeinsamer Ablauf für SQLite und PostgreSQL: Bestand auf dem Stand vor der Migration (Grunddaten wie beim Start,
    Dubletten bei Rechnung und Mahnung, Entwürfe ohne Nummer), hoch -> Abbruch mit Liste, nichts geändert; Dubletten
    geklärt -> hoch, Bedingungen da, Entwürfe unverändert; runter und wieder hoch."""
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        anlegen(db)
        db.commit()
        r1, r2 = (_mit_nummer(db, "invoice", "R-2026-0001") for _ in range(2))
        m1, m2, m3 = (_mit_nummer(db, "reminder", "M-2026-0005") for _ in range(3))
        _mit_nummer(db, "invoice", "R-2026-0002")
        for _ in range(2):
            _mit_nummer(db, "invoice", None)
            _mit_nummer(db, "reminder", None)
        db.commit()

        lauf = _alembic(url, "upgrade", "head")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0
        assert "Migration abgebrochen, nichts geändert" in ausgabe, ausgabe[-2000:]
        assert f"Rechnung R-2026-0001: 2-mal vergeben (invoices.id {r1}, {r2})" in ausgabe
        assert f"Mahnung M-2026-0005: 3-mal vergeben (reminders.id {m1}, {m2}, {m3})" in ausgabe
        assert "R-2026-0002" not in ausgabe.split("Migration abgebrochen")[1]  # nur die Dubletten
        assert "IntegrityError" not in ausgabe and "UniqueViolation" not in ausgabe
        assert VORHER in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        assert not _eindeutig(engine, "invoices", "invoice_number")
        assert not _eindeutig(engine, "reminders", "reminder_number")

        # geklärt (im Betrieb: Prüfabfrage, dann von Hand) -> die Migration läuft
        db.execute(text("UPDATE invoices SET invoice_number = 'R-2026-0003' WHERE id = :i"), {"i": r2})
        db.execute(text("UPDATE reminders SET reminder_number = 'M-2026-0006' WHERE id = :i"), {"i": m2})
        db.execute(text("UPDATE reminders SET reminder_number = 'M-2026-0007' WHERE id = :i"), {"i": m3})
        db.commit()
        db.close()
        _ok(_alembic(url, "upgrade", "head"))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        assert _eindeutig(engine, "invoices", "invoice_number")
        assert _eindeutig(engine, "reminders", "reminder_number")
        db = Session()
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.invoice_number.is_(None))) == 2
        assert db.scalar(select(func.count()).select_from(Reminder).where(Reminder.reminder_number.is_(None))) == 2
        with pytest.raises(IntegrityError):  # die Bedingung aus der Migration, nicht aus create_all()
            _mit_nummer(db, "invoice", "R-2026-0001")
        db.rollback()
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        assert not _eindeutig(engine, "invoices", "invoice_number")
        db = Session()
        assert db.scalar(select(Invoice.invoice_number).where(Invoice.id == r2)) == "R-2026-0003"  # nichts verloren
        db.close()
        _ok(_alembic(url, "upgrade", "head"))
        engine.dispose()
        assert _eindeutig(engine, "invoices", "invoice_number")
    finally:
        db.close()
        engine.dispose()


def test_migration_refuses_with_a_list_of_duplicates_and_changes_nothing(tmp_path):
    url = f"sqlite:///{(tmp_path / 'nummern.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_refuses_with_a_list_of_duplicates_and_changes_nothing():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_nr_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    # ohne Prozentkodierung: alembic reicht die URL durch configparser
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
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


def _rohe_tabellen(conn, ohne_bedingung: str | None):
    mig = _migration()
    for _label, table, column, uq, neu in mig.NUMMERNKREISE:
        bedingung = "" if neu or table == ohne_bedingung else f", CONSTRAINT {uq} UNIQUE ({column})"
        conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, {column} VARCHAR(50){bedingung})"))
    return mig


def test_migration_check_names_a_missing_old_constraint_and_duplicates_there():
    """Fehlt eine der fünf Bedingungen aus der Baseline (z. B. von Hand entfernt), legt die Migration sie nicht still an,
    sondern bricht ab und nennt sie -- samt der Dubletten, die sich dort inzwischen gebildet haben."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        mig = _rohe_tabellen(conn, ohne_bedingung="quotes")
        conn.execute(text("INSERT INTO quotes (id, quote_number) VALUES (1, 'A-1'), (2, 'A-1'), (3, 'A-2')"))
        conn.execute(text("INSERT INTO invoices (id, invoice_number) VALUES (1, NULL), (2, NULL), (3, 'R-1')"))
        with pytest.raises(RuntimeError) as exc:
            mig.pruefen(conn)
    meldung = str(exc.value)
    assert "Angebot: quotes.quote_number ohne Bedingung „eindeutig“ (uq_quote_number)" in meldung
    assert "Angebot A-1: 2-mal vergeben (quotes.id 1, 2)" in meldung
    assert meldung.count("  - ") == 2  # sonst nichts: Entwürfe ohne Nummer sind keine Dublette


def test_migration_check_passes_on_a_clean_inventory():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        mig = _rohe_tabellen(conn, ohne_bedingung=None)
        conn.execute(text("INSERT INTO invoices (id, invoice_number) VALUES (1, NULL), (2, NULL), (3, 'R-1'), (4, 'R-2')"))
        conn.execute(text("INSERT INTO reminders (id, reminder_number) VALUES (1, NULL), (2, NULL), (3, 'M-1')"))
        mig.pruefen(conn)  # wirft nicht
