"""Migration 8d3f6a2c91e7 (seit 1.9.124, Stufe 5, R2, Punkt 1): der Auftrag hat nur noch vier Status, dazu die Tabelle order_status_changes.

Bestand auf dem Stand davor (3e9b7c41d2a8): je ein Auftrag mit jedem Wert, den die Oberfläche bis 1.9.123 anbot, dazu Schreibweisen und Werte, die
es nur über die API gab. Hoch: jeder alte Wert landet richtig (beauftragt, arbeitsvorbereitung, in_ausfuehrung, leer und unbekannt -> laeuft;
pausiert, abgeschlossen, storniert bleiben, auch in anderer Schreibweise), alles andere am Auftrag unverändert. Runter: verweigert, solange ein
Auftrag „läuft“ oder ein Statuswechsel festgehalten ist -- nichts geändert. Ohne solche Daten geht der Rückweg. Auf einer Wegwerf-SQLite und (opt-in)
einem Wegwerf-Schema der lokalen PostgreSQL (Regel 27)."""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from tests import bestand_alt
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "8d3f6a2c91e7"
VORHER = "3e9b7c41d2a8"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")

ALT_NEU = {
    "beauftragt": "laeuft", "arbeitsvorbereitung": "laeuft", "in_ausfuehrung": "laeuft", "pausiert": "pausiert",
    "abgeschlossen": "abgeschlossen", "storniert": "storniert",
    # nur über die API möglich (bis 1.9.123 ohne Werteliste)
    " Storniert ": "storniert", "ABGESCHLOSSEN": "abgeschlossen", "": "laeuft", "erledigt": "laeuft",
}


def _modul():
    pfad = next((Path(__file__).resolve().parent.parent / "alembic" / "versions").glob("*_auftragsstatus_vier_werte.py"))
    spec = importlib.util.spec_from_file_location("auftragsstatus_migration", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_regel_der_migration_je_wert():
    """Die Python-Fassung der Regel (für den Test) sagt dasselbe wie ALT_NEU; die SQL-Fassung prüft die Probe unten."""
    neuer_status = _modul().neuer_status
    assert {alt: neuer_status(alt) for alt in ALT_NEU} == ALT_NEU
    assert neuer_status(None) == "laeuft"


def _stand(db, *, ohne_status=False):
    spalten = sorted(c["name"] for c in inspect(db.get_bind()).get_columns("orders") if not (ohne_status and c["name"] == "status"))
    return [tuple("" if v is None else str(v) for v in row)
            for row in db.execute(text(f"SELECT {', '.join(spalten)} FROM orders ORDER BY id")).all()]


def _bestand(db) -> dict[int, str]:
    werte = {}
    for i, alt in enumerate(ALT_NEU):
        auftrag = bestand_alt.auftrag(db, number=f"544{i}")
        db.execute(text("UPDATE orders SET status = :s WHERE id = :i"), {"s": alt, "i": auftrag.id})
        werte[auftrag.id] = alt
    db.commit()
    return werte


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        werte = _bestand(db)
        vorher = _stand(db, ohne_status=True)
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db, ohne_status=True) == vorher
        nachher = dict(db.execute(text("SELECT id, status FROM orders")).all())
        assert {werte[i]: nachher[i] for i in werte} == ALT_NEU
        assert "order_status_changes" in inspect(engine).get_table_names()
        stand = _stand(db)
        db.close()

        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: ein Auftrag „läuft“" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert _stand(db) == stand

        # ein Statuswechsel allein sperrt den Rückweg ebenso (die Begründung ginge verloren)
        db.execute(text("UPDATE orders SET status = 'pausiert' WHERE status = 'laeuft'"))
        erster = min(werte)
        db.execute(text("INSERT INTO order_status_changes (order_id, old_status, new_status, reason, without_invoice, changed_at, "
                        "changed_by_name) VALUES (:o, 'laeuft', 'pausiert', 'Regen', :f, '2026-10-28 08:00:00', 'Bea Büro')"),
                   {"o": erster, "f": False})
        db.commit()
        db.close()
        lauf = _alembic(url, "downgrade", "-1")
        assert lauf.returncode != 0 and "Downgrade verweigert" in lauf.stdout + lauf.stderr
        engine.dispose()
        db = Session()
        db.execute(text("DELETE FROM order_status_changes"))
        db.commit()
        db.close()

        # ohne „läuft“ und ohne Wechsel geht er: die Tabelle ist weg, die Status bleiben
        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert "order_status_changes" not in inspect(engine).get_table_names()
        assert VORHER in _ok(_alembic(url, "current")).stdout
    finally:
        db.close()
        engine.dispose()


def test_migration_jeder_alte_wert_und_der_rueckweg(tmp_path):
    url = f"sqlite:///{(tmp_path / 'auftragsstatus.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_jeder_alte_wert_und_der_rueckweg():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_status_{uuid.uuid4().hex[:8]}"
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
