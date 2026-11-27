"""Version 1.11.47 -- Klicktests ohne Datei für das Journal von SQLite (Fund im Endlauf vom 27.11.2026).

Im Endlauf auf 6662aea4 scheiterten 29 von 168 Klicktests beim Befüllen mit „disk I/O error“ (SQLite, bei CREATE INDEX). Das Protokoll von SQLite
(SQLITE_CONFIG_LOG) nannte die Ursache: winDelete(<Arbeitsordner>\\erp.db-journal) mit Windows-Fehler 32 -- eine andere Anwendung (der Virenscanner des
Entwicklungsrechners) hielt das eben geschlossene Journal offen, SQLite gab nach seinen Wiederholungen auf (SQLITE_IOERR_DELETE). create_all() legt jede Tabelle
und jeden Index in einer eigenen Transaktion an -- über tausend Journale in Sekunden; zu viert zugleich traf es etwa jeden sechsten Klicktest. Gleiche Namen der
Wegwerf-Datenbanken waren es nicht: jeder Klicktest hat seinen Arbeitsordner.

    Schalter     PRAGMA journal_mode der Engine aus app/database.py je Kombination von ERP_TEST_JOURNAL_SPEICHER und ERP_ENV (Kindprozess): „memory“ nur
                 mit 1 und development/test, sonst „delete“ (die Vorgabe von SQLite)
    Werkzeug     _isolierte_umgebung() setzt den Schalter -- Befüllen und Instanz jedes Klicktests (und der Bildgrundlage) schreiben kein Journal als Datei
    Befüllen     create_all() samt Grunddaten mit dem Schalter: neben der Datenbank entsteht nie eine Datei <db>-journal (Beobachter am Ordner)
    Suite        jede SQLite-Verbindung dieses Testprozesses (tests/conftest.py) hält ihr Journal im Speicher; Kindprozesse bekommen den Schalter
    alembic      alembic/env.py folgt dem Schalter -- eine Migrationskette auf einer Wegwerf-SQLite ohne Journal-Datei
    Reihenfolge  tests/reihenfolge.py: die Datei bleibt offen; ein gesperrtes Öffnen wartet, gibt notfalls nur die Reihenfolge auf, nie den Lauf
                 (am Nachmittag des 27.11.2026 brach ein Lauf mit „Permission denied“ auf diese Datei ab -- derselbe Scanner)
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.pg_schutz import pg_url_pruefen

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from sqlalchemy import text
from app.database import engine, journal_im_speicher
with engine.connect() as conn:
    modus = conn.execute(text("PRAGMA journal_mode")).scalar()
print(json.dumps({"modus": modus, "schalter": journal_im_speicher()}))
"""


def _umgebung(tmp_path: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ERP_") and k != "DATABASE_URL"}
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite:///" + (tmp_path / "probe.db").as_posix()), "ERP_DATA_DIR": str(tmp_path / "data"),
                "PYTHONIOENCODING": "utf-8"})
    return env


@pytest.mark.parametrize("schalter,umgebung,erwartet", [
    ("1", "development", "memory"), ("1", "test", "memory"), ("1", "production", "delete"), ("1", None, "delete"), (None, "development", "delete"),
    ("0", "test", "delete"), ("ja", "test", "delete"),
])
def test_schalter_nur_fuer_test_instanzen(tmp_path, schalter, umgebung, erwartet):
    env = _umgebung(tmp_path)
    if schalter is not None:
        env["ERP_TEST_JOURNAL_SPEICHER"] = schalter
    if umgebung is not None:
        env["ERP_ENV"] = umgebung
    aus = subprocess.run([PY, "-c", PROBE, str(ROOT)], env=env, capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert aus.returncode == 0, aus.stderr[-2000:]
    assert json.loads(aus.stdout.strip().splitlines()[-1]) == {"modus": erwartet, "schalter": erwartet == "memory"}


def test_das_werkzeug_setzt_den_schalter(tmp_path):
    spec = importlib.util.spec_from_file_location("cdp_klicktest_v836", ROOT / "scripts" / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    env = modul._isolierte_umgebung(tmp_path)
    assert env["ERP_TEST_JOURNAL_SPEICHER"] == "1" and env["ERP_ENV"] == "development"


BEFUELLEN = """
import os, sys, threading, time
sys.path.insert(0, sys.argv[1])
ordner = sys.argv[2]
gesehen, halt = set(), threading.Event()
def beobachten():  # sieht jede Datei, die neben der Datenbank entsteht -- auch eine, die gleich wieder gelöscht wird, wenn sie lange genug lebt
    while not halt.is_set():
        gesehen.update(os.listdir(ordner))
threading.Thread(target=beobachten, daemon=True).start()
import app.main  # create_all() und Grunddaten auf der Wegwerf-Datenbank
from app.database import SessionLocal
from app.models import Customer
db = SessionLocal()
for i in range(200):  # zweihundert einzelne Transaktionen wie im Befüllen eines Klicktests
    db.add(Customer(name=f"Erfunden {i}", last_name=f"Erfunden {i}"))
    db.commit()
db.close()
halt.set()
print(sorted(gesehen))
"""


def test_befuellen_ohne_journal_datei(tmp_path):
    """Mit der Umgebung des Werkzeugs: create_all(), Grunddaten und 200 Transaktionen -- neben erp.db entsteht keine Datei erp.db-journal."""
    spec = importlib.util.spec_from_file_location("cdp_klicktest_v836b", ROOT / "scripts" / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    ordner = tmp_path / "instanz"
    ordner.mkdir()
    env = modul._isolierte_umgebung(ordner)
    env["DATABASE_URL"] = pg_url_pruefen(env["DATABASE_URL"])  # Regel 27 (hier SQLite des Werkzeugs)
    aus = subprocess.run([PY, "-c", BEFUELLEN, str(ROOT), str(ordner)], env=env, capture_output=True, text=True, timeout=300, cwd=ordner)
    assert aus.returncode == 0, aus.stderr[-3000:]
    gesehen = aus.stdout.strip().splitlines()[-1]
    assert "erp.db" in gesehen and "journal" not in gesehen, gesehen


def test_testprozess_journal_im_speicher(tmp_path):
    """tests/conftest.py: jede SQLite-Verbindung dieses Testprozesses (Ereignis „connect“ an jeder Engine) hält ihr Journal im Speicher."""
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite:///" + (tmp_path / "x.db").as_posix())
    try:
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "memory"
    finally:
        engine.dispose()
    assert os.environ.get("ERP_TEST_JOURNAL_SPEICHER") == "1"  # für Kindprozesse (alembic, app.main)


def test_alembic_mit_schalter_ohne_journal_datei(tmp_path):
    """alembic/env.py: eine Migrationskette auf eine Wegwerf-SQLite mit dem Schalter (wie aus der Suite) -- neben der Datenbank entsteht kein Journal."""
    import threading

    ordner = tmp_path / "mig"
    ordner.mkdir()
    env = _umgebung(ordner)
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite:///" + (ordner / "mig.db").as_posix()), "ERP_ENV": "test", "ERP_TEST_JOURNAL_SPEICHER": "1"})
    gesehen, halt = set(), threading.Event()

    def beobachten():
        while not halt.is_set():
            gesehen.update(os.listdir(ordner))

    faden = threading.Thread(target=beobachten, daemon=True)
    faden.start()
    try:
        aus = subprocess.run([PY, "-m", "alembic", "upgrade", "806513205b5c"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=600)
    finally:
        halt.set()
        faden.join(5)
    assert aus.returncode == 0, aus.stderr[-3000:]
    assert "mig.db" in gesehen and not any("journal" in n for n in gesehen), sorted(gesehen)


def test_reihenfolge_wartet_auf_eine_gesperrte_datei(tmp_path, monkeypatch):
    """tests/reihenfolge.py (Fund 27.11.2026: „Permission denied“ brach einen Lauf ab): die Datei bleibt offen; scheitert das Öffnen, wartet der Prozess und
    versucht es wieder -- bleibt sie gesperrt, endet nur die Reihenfolge, nie der Lauf."""
    import builtins

    from tests import reihenfolge

    echt, zaehler = builtins.open, {"n": 0}

    def gesperrt(sperren):
        def oeffnen(pfad, *a, **k):
            if str(pfad).endswith("probe.txt") and zaehler["n"] < sperren:
                zaehler["n"] += 1
                raise PermissionError(13, "Permission denied")
            return echt(pfad, *a, **k)
        return oeffnen

    monkeypatch.setattr(reihenfolge.time, "sleep", lambda s: None)
    monkeypatch.setattr(reihenfolge, "_datei", None)
    monkeypatch.setattr(reihenfolge, "_ziel", tmp_path / "probe.txt")
    monkeypatch.setattr(builtins, "open", gesperrt(3))
    reihenfolge._schreiben("eins\n")
    reihenfolge._schreiben("zwei\n")
    assert zaehler["n"] == 3  # dreimal gesperrt, dann geöffnet -- und offen geblieben (die zweite Zeile öffnet nicht neu)
    reihenfolge._datei.close()
    monkeypatch.setattr(reihenfolge, "_datei", None)
    assert (tmp_path / "probe.txt").read_text(encoding="utf-8") == "eins\nzwei\n"
    zaehler["n"] = 0
    monkeypatch.setattr(builtins, "open", gesperrt(1000))
    reihenfolge._schreiben("drei\n")  # bleibt gesperrt: keine Ausnahme
    assert reihenfolge._ziel is None and zaehler["n"] == 20
