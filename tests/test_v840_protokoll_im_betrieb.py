"""Version 1.11.49 (W1c Stufe 2, S2-0 a; Antwort W2-1 vom 28.11.2026) -- im Betrieb kein Protokoll als Datei, Parameter verdeckt.

Befund B1 des Bauplans W1c Stufe 2: data/erp.log wechselte nach Größe (5 MB, 5 alte Dateien), nicht nach Tagen, lag in jeder Sicherung und konnte über die
Fehlermeldung der Datenbank Werte einer Anweisung enthalten (Name, Adresse) -- die Datenschutzerklärung sagt „jedes Protokoll des Servers höchstens 15 Tage“.

    Datei        configure_logging(): die Datei data/erp.log nur mit ERP_ENV development oder test; sonst (auch ohne ERP_ENV) nur stderr -- unter systemd
                 das Journal (14 Tage)
    einmal       ein zweiter Aufruf hängt keinen Handler an (auch ohne Datei)
    verdeckt     app/database.py::engine_optionen(): im Betrieb hide_parameters -- ein IntegrityError nennt die Werte der Anweisung nicht; lokal und in
                 Tests weiter sichtbar
    keine Datei  kein anderer Code unter app/ oder scripts/ legt ein Protokoll als Datei an (FileHandler nur in app/logging_config.py und im
                 Klicktest-Werkzeug, das nur lokal läuft); keine Anleitung unter scripts/ hängt Ausgaben mit >> an eine Datei unter erp-data an
    Cron         der Outlook-Abgleich: die Zeile im Kopf des Skripts schreibt über systemd-cat ins Journal
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.pg_schutz import pg_url_pruefen

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
MERKMAL = "Erfunden-Probe-Merkmal-9137"

PROTOKOLL = """
import json, logging, sys
sys.path.insert(0, sys.argv[1])
from app.logging_config import configure_logging, im_betrieb
configure_logging()
configure_logging()
logging.getLogger("probe").error("Probe-Meldung")
wurzel = logging.getLogger()
print(json.dumps({"betrieb": im_betrieb(), "eigene": sum(1 for h in wurzel.handlers if getattr(h, "_dk_erp", False)),
                  "dateien": sum(1 for h in wurzel.handlers if isinstance(h, logging.FileHandler))}))
"""

FEHLER = """
import json, sys
sys.path.insert(0, sys.argv[1])
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import engine
with engine.begin() as c:
    c.execute(text("CREATE TABLE probe (name TEXT UNIQUE)"))
    c.execute(text("INSERT INTO probe (name) VALUES (:n)"), {"n": sys.argv[2]})
try:
    with engine.begin() as c:
        c.execute(text("INSERT INTO probe (name) VALUES (:n)"), {"n": sys.argv[2]})
    print(json.dumps({"meldung": None}))
except IntegrityError as e:
    print(json.dumps({"meldung": str(e)}))
"""


def _umgebung(tmp_path: Path, erp_env: str | None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ERP_") and k != "DATABASE_URL"}
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite:///" + (tmp_path / "probe.db").as_posix()), "ERP_DATA_DIR": str(tmp_path / "data"),
                "PYTHONIOENCODING": "utf-8"})
    (tmp_path / "data").mkdir(exist_ok=True)
    if erp_env is not None:
        env["ERP_ENV"] = erp_env
    return env


@pytest.mark.parametrize("erp_env, datei", [
    ("production", False), (None, False), ("", False), ("staging", False), ("Development", True), ("development", True), ("test", True),
])
def test_datei_nur_lokal(tmp_path, erp_env, datei):
    aus = subprocess.run([PY, "-c", PROTOKOLL, str(ROOT)], env=_umgebung(tmp_path, erp_env), capture_output=True, text=True, encoding="utf-8",
                         timeout=120, cwd=tmp_path)
    assert aus.returncode == 0, aus.stderr[-2000:]
    stand = json.loads(aus.stdout.strip().splitlines()[-1])
    assert stand == {"betrieb": not datei, "eigene": 2 if datei else 1, "dateien": 1 if datei else 0}
    assert "Probe-Meldung" in aus.stderr  # stderr -- unter systemd das Journal
    log = tmp_path / "data" / "erp.log"
    assert log.exists() is datei
    if datei:
        assert "Probe-Meldung" in log.read_text(encoding="utf-8")


@pytest.mark.parametrize("erp_env, sichtbar", [("production", False), (None, False), ("development", True), ("test", True)])
def test_parameter_im_betrieb_verdeckt(tmp_path, erp_env, sichtbar):
    aus = subprocess.run([PY, "-c", FEHLER, str(ROOT), MERKMAL], env=_umgebung(tmp_path, erp_env), capture_output=True, text=True, encoding="utf-8",
                         timeout=120, cwd=tmp_path)
    assert aus.returncode == 0, aus.stderr[-2000:]
    meldung = json.loads(aus.stdout.strip().splitlines()[-1])["meldung"]
    assert meldung and "UNIQUE" in meldung.upper()
    assert (MERKMAL in meldung) is sichtbar, meldung
    if not sichtbar:
        assert "hide_parameters" in meldung


def _quellen(*ordner: str):
    for name in ordner:
        for pfad in sorted((ROOT / name).rglob("*.py")):
            if "__pycache__" not in pfad.parts:
                yield pfad


def test_kein_anderes_protokoll_als_datei():
    erlaubt = {ROOT / "app" / "logging_config.py", ROOT / "scripts" / "cdp_klicktest.py"}  # das Werkzeug der Klicktests läuft nur lokal
    funde = [str(p.relative_to(ROOT)) for p in _quellen("app", "scripts") if p not in erlaubt
             and re.search(r"\b(Rotating|TimedRotating|Watched)?FileHandler\b", p.read_text(encoding="utf-8"))]
    assert funde == []


def test_keine_anleitung_haengt_an_eine_datei_unter_erp_data_an():
    muster = re.compile(r"(^|\s)>>\s*\S*erp-data/\S+\.log", re.MULTILINE)
    funde = []
    for pfad in (ROOT / "scripts").rglob("*"):
        if pfad.is_file() and "__pycache__" not in pfad.parts and pfad.suffix in (".py", ".sh", ".service", ".timer", ".conf", ".md", ".txt"):
            text = pfad.read_text(encoding="utf-8", errors="replace")
            funde += [f"{pfad.relative_to(ROOT)}: {m.group(0).strip()}" for m in muster.finditer(text)
                      if "Bis dahin hängte" not in text[max(0, m.start() - 80):m.start()]]
    assert funde == []


def test_cron_des_outlook_abgleichs_ins_journal():
    kopf = (ROOT / "scripts" / "sync_outlook_calendars.py").read_text(encoding="utf-8").split('"""')[1]
    zeilen = [z.strip() for z in kopf.splitlines() if z.strip().startswith("*/15 * * * *")]
    assert len(zeilen) == 1
    assert zeilen[0].endswith("2>&1 | systemd-cat -t erp-outlook-sync") and ">>" not in zeilen[0]
