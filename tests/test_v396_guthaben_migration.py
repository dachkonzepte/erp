"""Migration 7b3e9d1f5a26 (Nacharbeit R4c Punkt 3, seit 1.8.93): Tabelle payment_refund_sources (Erstattung aus dem Rest einer Zahlung).

Bestand auf dem Stand davor (4e7a9c2b6d58): Auftrag mit Position, festgeschriebener Abschlag, Entwurf, eine Zahlung mit Zuordnung und
Rest, ein Zahlungsausgang mit Zuordnung "erstattung". Hoch: jede Zeile unverändert, neue Tabelle leer. Runter: alles exakt wie vorher,
Tabelle weg. Wieder hoch, eine Erstattung aus dem Rest -> Rückweg verweigert, nichts geändert. Auf einer Wegwerf-SQLite und (opt-in)
einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v386_nachtrag_migration import _bestand

MIGRATION = "7b3e9d1f5a26"
VORHER = "4e7a9c2b6d58"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
T = "2026-09-01 08:00:00"
TABELLEN = ("orders", "order_items", "invoices", "invoice_items", "payments", "payment_allocations")


def _stand(db, engine):
    result = {}
    for table in TABELLEN:
        columns = sorted(c["name"] for c in inspect(engine).get_columns(table))
        rows = db.execute(text(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")).all()
        result[table] = [tuple("" if v is None else str(v) for v in row) for row in rows]
    return result


def _zahlung(db, customer_id, amount, received_on="2026-09-10"):
    return db.execute(text(
        "INSERT INTO payments (customer_id, received_on, amount, origin, created_at, created_by_name) "
        "VALUES (:c, :r, :a, 'erfasst', :t, 'Test') RETURNING id"), {"c": customer_id, "r": received_on, "a": amount, "t": T}).scalar()


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        order_id, abschlag_id = _bestand(db)
        customer_id = db.execute(text("SELECT customer_id FROM invoices WHERE id = :i"), {"i": abschlag_id}).scalar()
        eingang = _zahlung(db, customer_id, 3000)  # 2.380 zugeordnet, 620 Rest
        db.execute(text("INSERT INTO payment_allocations (payment_id, invoice_id, kind, amount, created_at, created_by_name) "
                        "VALUES (:p, :i, 'zahlung', 2380, :t, 'Test')"), {"p": eingang, "i": abschlag_id, "t": T})
        ausgang = _zahlung(db, customer_id, -100, "2026-09-12")
        db.execute(text("INSERT INTO payment_allocations (payment_id, invoice_id, kind, amount, created_at, created_by_name) "
                        "VALUES (:p, :i, 'erstattung', -100, :t, 'Test')"), {"p": ausgang, "i": abschlag_id, "t": T})
        db.commit()
        vorher = _stand(db, engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher
        assert db.execute(text("SELECT count(*) FROM payment_refund_sources")).scalar() == 0
        uniques = [c["column_names"] for c in inspect(engine).get_unique_constraints("payment_refund_sources")]
        assert ["refund_payment_id", "source_payment_id"] in uniques
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher
        assert "payment_refund_sources" not in inspect(engine).get_table_names()
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        zweiter = _zahlung(db, customer_id, -50, "2026-09-13")
        db.execute(text("INSERT INTO payment_refund_sources (refund_payment_id, source_payment_id, amount, created_at, "
                        "created_by_name) VALUES (:r, :s, 50, :t, 'Test')"), {"r": zweiter, "s": eingang, "t": T})
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Erstattungen aus dem Rest einer Zahlung" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
        assert db.execute(text("SELECT count(*) FROM payment_refund_sources")).scalar() == 1
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'guthaben.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_guthaben_{uuid.uuid4().hex[:8]}"
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
