"""Seit 1.9.195 (Lohn L1a, Stufe 3, Punkt 4): jede Engine eines Tests wird am Ende ihres Aufbaus geschlossen, nicht von der Speicherbereinigung.

Bis 1.9.194 räumte die Speicherbereinigung die Engines vieler Testaufbauten ab (z. B. tests/test_v133_invoices.py::db_session() -- eine
Sitzung, die nie geschlossen wurde), oft im Thread eines späteren TestClient: „Exception during reset or similar … SQLite objects created in a
thread can only be used in that same thread“, 79 bis 197 Zeilen je vollem Lauf. Seitdem:

    Regel      jede create_engine() unter tests/ steht in einer Funktion, die die Engine selbst mit dispose() schließt -- sonst
               tests/aufraeumen.py::wegwerf_engine(); auf Modulebene keine
    Ablauf     wegwerf_engine() merkt die Engine, die autouse-Fixtures in tests/conftest.py schließen sie am Ende des Tests (des Moduls, des
               Laufs, wenn ein Aufbau dieses Umfangs sie anlegte)
    Wirkung    eine nie geschlossene Sitzung, die erst eine Speicherbereinigung in einem anderen Thread abräumt, hinterlässt keinen Fehler
"""

import ast
import gc
import logging
import sqlite3
import threading
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, close_all_sessions

from tests import aufraeumen
from tests.aufraeumen import wegwerf_engine

TESTS = Path(__file__).resolve().parent


def _innerste_funktion(baum):
    eltern = {k: n for n in ast.walk(baum) for k in ast.iter_child_nodes(n)}

    def finden(n):
        while n in eltern:
            n = eltern[n]
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return n
        return None
    return finden


def test_jede_engine_unter_tests_wird_geschlossen():
    funde, selbst, gemerkt = [], 0, 0
    for datei in sorted(TESTS.rglob("*.py")):
        if datei.name == "aufraeumen.py":
            continue
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        finden = _innerste_funktion(baum)
        for n in ast.walk(baum):
            if not isinstance(n, ast.Call):
                continue
            name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else None
            if name == "wegwerf_engine":
                gemerkt += 1
            if name != "create_engine":
                continue
            f = finden(n)
            if f is not None and ".dispose()" in ast.unparse(f):
                selbst += 1
                continue
            funde.append(f"{datei.relative_to(TESTS).as_posix()}:{n.lineno} {f.name if f else '(Modulebene)'}")
    assert gemerkt >= 140 and selbst >= 80, (gemerkt, selbst)
    assert funde == [], "create_engine() ohne dispose() in derselben Funktion -- wegwerf_engine() nehmen: " + ", ".join(funde)


def test_schliessen_schliesst_ab_der_marke():
    """Was vor der Marke gemerkt wurde, bleibt offen; danach Angelegtes wird geschlossen -- die Verbindung ist danach zu."""
    vorher = wegwerf_engine("sqlite:///:memory:")
    marke = aufraeumen.marke()
    danach = wegwerf_engine("sqlite:///:memory:")
    verbindungen = []
    for engine in (vorher, danach):
        with engine.connect() as conn:
            conn.execute(text("select 1"))
            verbindungen.append(conn.connection.dbapi_connection)
    assert aufraeumen.schliessen(marke) == 1
    verbindungen[0].execute("select 1")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        verbindungen[1].execute("select 1")


def test_offene_sitzung_raeumt_in_fremdem_thread_ohne_fehler_ab(caplog):
    """Der Fall der Testaufbauten bis 1.9.194: eine Sitzung mit offener Transaktion bleibt liegen, die Speicherbereinigung räumt sie in
    einem anderen Thread ab. Nach schliessen() ist ihre Verbindung schon zu -- kein „Exception during reset or similar“."""
    marke = aufraeumen.marke()
    sitzung = Session(wegwerf_engine("sqlite:///:memory:"))
    sitzung.execute(text("select 1"))  # Transaktion offen, Verbindung im Thread des Tests ausgeliehen
    aufraeumen.schliessen(marke)
    ablage = [sitzung]
    del sitzung

    def abraeumen():
        ablage.clear()
        gc.collect()

    with caplog.at_level(logging.ERROR, logger="sqlalchemy.pool"):
        t = threading.Thread(target=abraeumen)
        t.start()
        t.join()
    assert [r.getMessage() for r in caplog.records if r.name.startswith("sqlalchemy.pool")] == []


def test_liegen_gebliebene_sitzung_ist_danach_geschlossen():
    """Eine nie geschlossene Sitzung schließt schliessen() vor dem dispose() mit -- sonst wirft ihr close() später auf der geschlossenen
    Verbindung, etwa in close_all_sessions() eines PostgreSQL-Tests (tests/befund_vor_echtbetrieb.py::pg_sitzung(); im ersten Lauf von
    1.9.195 so 45-mal)."""
    marke = aufraeumen.marke()
    sitzung = Session(wegwerf_engine("sqlite:///:memory:"))
    sitzung.execute(text("select 1"))
    aufraeumen.schliessen(marke)
    assert not sitzung.in_transaction()
    close_all_sessions()


def test_die_fixtures_jedes_umfangs_laufen(request):
    """Test, Modul und Lauf schließen ihre Engines je über eine autouse-Fixture in tests/conftest.py."""
    assert {"_engines_des_tests", "_engines_des_moduls", "_engines_des_laufs"} <= set(request.fixturenames)
