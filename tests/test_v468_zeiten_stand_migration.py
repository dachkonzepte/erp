"""Migration b7e3d91c4a58 (seit 1.9.42): service_reports.time_rows_json, die Zeiten eines Einsatzberichts mit der Unterschrift gespeichert.
Bestand auf dem Stand davor (8c86e12540cf): Auftrag, ein unterschriebener Bericht, ein Entwurf. Hoch: jede Zeile unverändert, die neue
Spalte leer -- kein Bericht bekommt nachträglich einen Stand. Runter: alles exakt wie vorher. Wieder hoch, ein Bericht mit Stand -> Rückweg
verweigert, nichts geändert. Auf einer Wegwerf-SQLite und (opt-in) einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests.bestand_alt import auftrag
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "b7e3d91c4a58"
VORHER = "8c86e12540cf"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
T = "2026-10-01 08:00:00"


def _spalten(engine):
    return {c["name"] for c in inspect(engine).get_columns("service_reports")}


def _stand(db, engine, *, ohne=False):
    columns = sorted(_spalten(engine) - ({"time_rows_json"} if ohne else set()))
    rows = db.execute(text(f"SELECT {', '.join(columns)} FROM service_reports ORDER BY id")).all()
    return [tuple("" if v is None else str(v) for v in row) for row in rows]


def _bestand(db):
    order = auftrag(db, number="0001")
    for status in ("unterschrieben", "entwurf"):
        db.execute(text(
            "INSERT INTO service_reports (order_id, report_type, performed_at, status, signature_name, advance_due_date_on_sign, created_at, "
            "updated_at) VALUES (:o, 'rapport', '2026-10-01', :s, :n, :f, :t, :t)"),
            {"o": order.id, "s": status, "n": "Bernd" if status == "unterschrieben" else None, "f": False, "t": T})
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
        assert _stand(db, engine, ohne=True) == vorher  # keine vorhandene Zeile geändert
        assert db.execute(text("SELECT count(*) FROM service_reports WHERE time_rows_json IS NOT NULL")).scalar() == 0
        db.close()

        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == vorher and "time_rows_json" not in _spalten(engine)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        engine.dispose()
        db = Session()
        db.execute(text("UPDATE service_reports SET time_rows_json = :j WHERE status = 'unterschrieben'"), {"j": '{"format": 1, "zeilen": []}'})
        db.commit()
        nachher = _stand(db, engine)
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 Einsatzberichte mit gespeicherten Zeiten" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, engine) == nachher
    finally:
        db.close()
        engine.dispose()


def test_migration_keeps_every_row_and_the_way_back(tmp_path):
    url = f"sqlite:///{(tmp_path / 'zeiten_stand.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_with_data_keeps_every_row_and_the_way_back():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_zeiten_{uuid.uuid4().hex[:8]}"
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
