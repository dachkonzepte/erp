"""Migration 6d1e8b3f2a47 (R4a Punkt 1, seit 1.8.82): invoices.pdf_document_id, die feste Fassung einer Rechnung.

Bestand auf dem Stand davor (a4c9e2f7b815): Auftrag, festgeschriebene Rechnung mit einem Ablage-Eintrag vom Versand (alte Regel),
ein Entwurf. Hoch: jede Zeile unverändert, die neue Spalte leer -- keine Rechnung bekommt nachträglich eine feste Fassung. Runter:
alles exakt wie vorher. Wieder hoch, eine Rechnung mit fester Fassung -> Rückweg verweigert, nichts geändert. Auf einer
Wegwerf-SQLite und (opt-in) einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.bestand_alt import auftrag
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "6d1e8b3f2a47"
VORHER = "a4c9e2f7b815"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
TABELLEN = ("orders", "invoices", "sent_documents")
T = "2026-09-01 08:00:00"


def _spalten(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _stand(db, engine, *, ohne=False):
    result = {}
    for table in TABELLEN:
        columns = sorted(_spalten(engine, table) - ({"pdf_document_id"} if ohne and table == "invoices" else set()))
        rows = db.execute(text(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")).all()
        result[table] = [tuple("" if v is None else str(v) for v in row) for row in rows]
    return result


def _bestand(db):
    order = auftrag(db, number="0001")
    invoice_id = db.execute(text(
        "INSERT INTO invoices (order_id, customer_id, invoice_type, status, invoice_date, due_date, customer_name, vat_rate, "
        "invoice_number, created_at, updated_at) VALUES (:o, :c, 'schluss', 'versendet', '2026-09-01', '2026-09-15', 'K', 19, "
        "'R-ALT-1', :t, :t) RETURNING id"), {"o": order.id, "c": order.customer_id, "t": T}).scalar()
    db.execute(text("INSERT INTO invoices (order_id, invoice_type, status, invoice_date, customer_name, vat_rate, created_at, "
                    "updated_at) VALUES (:o, 'abschlag_pauschal', 'entwurf', '2026-09-02', 'K', 19, :t, :t)"),
               {"o": order.id, "t": T})
    doc_id = db.execute(text(
        "INSERT INTO sent_documents (document_type, document_id, document_number, filename, stored_filename, size_bytes, sha256, "
        "created_at, created_by_name, content_type) VALUES ('rechnung', :i, 'R-ALT-1', 'R-ALT-1.pdf', '2026/09/alt.pdf', 10, "
        ":s, :t, 'Alt', 'application/pdf') RETURNING id"), {"i": invoice_id, "s": "0" * 64, "t": T}).scalar()
    db.commit()
    return invoice_id, doc_id


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        invoice_id, doc_id = _bestand(db)
        vorher = _stand(db, engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine, ohne=True) == vorher  # keine vorhandene Zeile geändert
        assert "pdf_document_id" in _spalten(engine, "invoices")
        assert db.execute(text("SELECT count(*) FROM invoices WHERE pdf_document_id IS NOT NULL")).scalar() == 0
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher and "pdf_document_id" not in _spalten(engine, "invoices")
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("UPDATE invoices SET pdf_document_id = :d WHERE id = :i"), {"d": doc_id, "i": invoice_id})
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Rechnungen mit fester Fassung" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'feste_fassung.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_fassung_{uuid.uuid4().hex[:8]}"
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
