"""Version 1.9.363 -- Klicktests mit Fremdschlüsselprüfung; der Bilderordner vor jedem Bild (Runde V3, Punkt 3).

Seit 1.9.339 prüft die Suite unter SQLite Fremdschlüssel (tests/conftest.py), eine Klicktest-Instanz nicht: 42 Seeds legten einen Auftrag mit einer erfundenen
Angebots-ID an (source_quote_id=1, 900 + nr …), die Instanz nahm ihn still an. Jetzt schaltet ERP_TEST_FREMDSCHLUESSEL=1 die Prüfung in app/database.py ein --
nur mit ERP_ENV development oder test, nie im Betrieb --, das Klicktest-Werkzeug setzt den Schalter für jede Instanz, und jeder Seed legt das Angebot seines
Auftrags an (tests/quellangebot.py::quell_angebot(), importiert in befuellen()).

Dazu (Fund im Endlauf von V2c): ein Aufräumen leerer Ordner unter %TEMP% löschte den noch leeren Bilderordner laufender Klicktests. Tab.ablage() legt ihn
direkt vor jeder Datei an; jedes Bild und jede Datei im Bilderordner geht darüber.

    Schalter     PRAGMA foreign_keys der Engine aus app/database.py je Kombination von ERP_TEST_FREMDSCHLUESSEL und ERP_ENV (Kindprozess)
    Werkzeug     _isolierte_umgebung() setzt den Schalter; die Instanz lehnt einen Auftrag ohne Angebot ab
    Seeds        kein Order(...) unter scripts/ mit einer erfundenen source_quote_id (AUSNAHMEN genau); kein Import aus tests auf oberster Ebene
    Bilder       Tab.ablage() legt den Ordner an; bild() und bild_ganz() nehmen ablage(); kein Klicktest schreibt an ablage() vorbei in den Bilderordner
"""

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.pg_schutz import pg_url_pruefen

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PY = sys.executable
# Datei -> Grund. Darf nur kürzer werden.
AUSNAHMEN = {"scripts/vorprobe_time4.py": "eigene Wegwerf-SQLite ohne Test-Instanz (Vorprobe der Lohndatei), legt ihr Angebot nicht über ein Seed an"}


def _werkzeug():
    spec = importlib.util.spec_from_file_location("cdp_klicktest_v763", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# --- der Schalter --------------------------------------------------------------------------------------------------------------------------------

PROBE = """
import json, os, sys
sys.path.insert(0, sys.argv[1])
from sqlalchemy import text
from app.database import engine, fremdschluessel_pruefen
with engine.connect() as conn:
    an = conn.execute(text("PRAGMA foreign_keys")).scalar()
print(json.dumps({"an": an, "schalter": fremdschluessel_pruefen()}))
"""


@pytest.mark.parametrize("schalter,umgebung,erwartet", [
    ("1", "development", 1), ("1", "test", 1), ("1", "production", 0), ("1", None, 0), (None, "development", 0), ("0", "test", 0), ("ja", "test", 0),
])
def test_schalter_nur_fuer_test_instanzen(tmp_path, schalter, umgebung, erwartet):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ERP_") and k != "DATABASE_URL"}
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite:///" + (tmp_path / "probe.db").as_posix()), "ERP_DATA_DIR": str(tmp_path / "data"),
                "PYTHONIOENCODING": "utf-8"})
    if schalter is not None:
        env["ERP_TEST_FREMDSCHLUESSEL"] = schalter
    if umgebung is not None:
        env["ERP_ENV"] = umgebung
    aus = subprocess.run([PY, "-c", PROBE, str(ROOT)], env=env, capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert aus.returncode == 0, aus.stderr[-2000:]
    ergebnis = json.loads(aus.stdout.strip().splitlines()[-1])
    assert ergebnis == {"an": erwartet, "schalter": bool(erwartet)}


def test_das_werkzeug_setzt_den_schalter(tmp_path):
    env = _werkzeug()._isolierte_umgebung(tmp_path)
    assert env["ERP_TEST_FREMDSCHLUESSEL"] == "1" and env["ERP_ENV"] == "development"


def test_die_instanz_lehnt_einen_auftrag_ohne_angebot_ab(tmp_path):
    """Mit der Umgebung des Werkzeugs: ein Auftrag mit erfundener Angebots-ID scheitert am Fremdschlüssel, mit quell_angebot() geht er."""
    env = _werkzeug()._isolierte_umgebung(tmp_path)
    env["DATABASE_URL"] = pg_url_pruefen(env["DATABASE_URL"])  # Regel 27 (hier SQLite des Werkzeugs)
    skript = """
import sys
sys.path.insert(0, sys.argv[1])
import app.main  # create_all() auf der Wegwerf-Datenbank des Werkzeugs
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models import Customer, Order, Project
from app.project_pipeline_columns import default_pipeline_column_id
from tests.quellangebot import quell_angebot
db = SessionLocal()
k = Customer(name="Probe", last_name="Probe"); db.add(k); db.flush()
p = Project(project_number="P-FK-1", name="Probe", customer_id=k.id, pipeline_column_id=default_pipeline_column_id(db)); db.add(p); db.flush()
try:
    db.add(Order(order_number="AUF-FK-1", project_id=p.id, source_quote_id=900, quote_number_snapshot="A-1", title="x", customer_name="Probe",
                 customer_id=k.id)); db.flush(); print("erfunden: angenommen")
except IntegrityError:
    db.rollback(); print("erfunden: abgelehnt")
k = Customer(name="Probe", last_name="Probe"); db.add(k); db.flush()
p = Project(project_number="P-FK-2", name="Probe", customer_id=k.id, pipeline_column_id=default_pipeline_column_id(db)); db.add(p); db.flush()
db.add(Order(order_number="AUF-FK-2", project_id=p.id, source_quote_id=quell_angebot(db, p.id, "AUF-FK-2"), quote_number_snapshot="Q-AUF-FK-2",
             title="x", customer_name="Probe", customer_id=k.id)); db.commit(); print("echt: angenommen")
"""
    aus = subprocess.run([PY, "-c", skript, str(ROOT)], env=env, capture_output=True, text=True, timeout=180, cwd=tmp_path)
    assert aus.returncode == 0, aus.stderr[-2000:]
    assert [z for z in aus.stdout.splitlines() if ": " in z] == ["erfunden: abgelehnt", "echt: angenommen"]


# --- die Seeds -----------------------------------------------------------------------------------------------------------------------------------

def _erfundene(rel: str, text: str) -> list[str]:
    out = []
    for n in ast.walk(ast.parse(text)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Order":
            wert = {k.arg: k.value for k in n.keywords}.get("source_quote_id")
            echt = wert is None or isinstance(wert, ast.Attribute) or (isinstance(wert, ast.Call) and getattr(wert.func, "id", None) == "quell_angebot")
            if not echt:
                out.append(f"{rel}:{n.lineno}")
    return out


def _skripte():
    return sorted(SCRIPTS.glob("*.py"))


def test_kein_seed_mit_erfundenem_angebot():
    funde = [s for f in _skripte() for s in _erfundene(f.relative_to(ROOT).as_posix(), f.read_text(encoding="utf-8"))]
    assert sorted({s.split(":")[0] for s in funde}) == sorted(AUSNAHMEN), funde


def test_der_waechter_erkennt_jede_form():
    rot = ["Order(order_number='A', project_id=1, source_quote_id=1)", "Order(source_quote_id=900 + nr)", "Order(source_quote_id=x)"]
    gruen = ["Order(source_quote_id=quell_angebot(db, p.id, 'A'))", "Order(source_quote_id=angebot.id)", "Order(order_number='A')"]
    assert [bool(_erfundene("x", q)) for q in rot] == [True] * 3
    assert [_erfundene("x", q) for q in gruen] == [[]] * 3


def test_kein_import_aus_tests_auf_oberster_ebene():
    """Im Hauptprozess eines Klicktests liegt nur scripts/ im Suchpfad -- tests importiert erst befuellen() (dort steht das Projekt im Pfad)."""
    falsch = [f.name for f in _skripte() for s in ast.parse(f.read_text(encoding="utf-8")).body
              if isinstance(s, ast.ImportFrom) and (s.module or "").startswith("tests")]
    assert falsch == []


# --- der Bilderordner ----------------------------------------------------------------------------------------------------------------------------

def test_ablage_legt_den_ordner_an(tmp_path):
    tab = _werkzeug().Tab(None, "http://127.0.0.1", tmp_path / "arbeit" / "shots")
    ziel = tab.ablage("bild.png")
    assert ziel == tmp_path / "arbeit" / "shots" / "bild.png" and ziel.parent.is_dir()
    ziel.parent.rmdir()  # wie das Aufräumen unter %TEMP%
    assert tab.ablage("zwei.png").parent.is_dir()


def test_jedes_bild_ueber_ablage():
    """bild() und bild_ganz() nehmen ablage(); kein Skript setzt einen Pfad im Bilderordner an ablage() vorbei zusammen (… shots / name)."""
    baum = ast.parse((SCRIPTS / "cdp_klicktest.py").read_text(encoding="utf-8"))
    tab = next(n for n in baum.body if isinstance(n, ast.ClassDef) and n.name == "Tab")
    methoden = {f.name: f for f in tab.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in ("bild", "bild_ganz"):
        assert any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "ablage" for c in ast.walk(methoden[name])), name
    falsch = []
    for f in _skripte():
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) and isinstance(n.left, ast.Attribute) and n.left.attr == "shots"):
                fn = "ablage" if f.name == "cdp_klicktest.py" and n.lineno in range(methoden["ablage"].lineno, methoden["ablage"].end_lineno + 1) else None
                if fn is None:
                    falsch.append(f"{f.name}:{n.lineno}")
    assert falsch == [], "Dateien im Bilderordner über tab.ablage(name)"
