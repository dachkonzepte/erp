"""Version 1.8.111 -- Testablauf (Vorgabe "Vor dem Abnahmetest" Punkt 7, Nebenbefunde 4 und 5 aus 1.8.108;
docs/archiv/testablauf-und-klicktests.md).

- Zeitgrenze je Test (tests/zeitgrenze.py): ein hängender Test beendet seinen Testprozess mit Stapel aller Threads, statt den ganzen
  Lauf anzuhalten; im parallelen Lauf geht der Lauf ohne ihn weiter. Geprüft im Unterprozess mit Probe-Tests dieser Datei, die nur
  dort laufen (ERP_ZEITGRENZE_PROBE).
- Die Testhelfer _run in tests/test_v363_zweck_abnahme.py und tests/test_v365_abnahme_aus_protokoll.py schließen die Sitzung der
  zweiten Aktion, bevor sie auf die erste warten -- wie tests/test_v375_rechnungen_sperren.py::_run seit dem Nachtrag 2 zu 1.8.108.
  Angriffstest gegen PostgreSQL: die erste Aktion committet zweimal und braucht dazwischen eine Zeile, die die zweite gesperrt hält und
  nach einer Ablehnung offen ließe (die Verklemmung vom 15.10.2026).
- taskkill in scripts/cdp_klicktest.py::beenden() und scripts/klicktest_alle.py::_baum_beenden() mit Zeitlimit."""

import importlib.util
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

from tests import zeitgrenze

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
PROBE = os.getenv("ERP_ZEITGRENZE_PROBE")
DIESE = Path(__file__).relative_to(ROOT).as_posix()


def _modul(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_v416", SCRIPTS / f"{name}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# -- Probe-Tests: laufen nur im Unterprozess -------------------------------------------------------------------

nur_als_probe = pytest.mark.skipif(not PROBE, reason="Probe für die Zeitgrenze, läuft nur im Unterprozess")


@nur_als_probe
def test_probe_haengt():
    time.sleep(float(PROBE))


@nur_als_probe
def test_probe_schnell():
    assert True


@nur_als_probe
@pytest.mark.zeitgrenze(1)
def test_probe_mit_eigener_grenze():
    time.sleep(float(PROBE))


def _lauf(*argumente, schlafen: float = 60, timeout: float = 240):
    """pytest im Unterprozess -- ohne die PYTEST_XDIST_*-Variablen, die ein Arbeitsprozess des äußeren Laufs in seiner Umgebung trägt."""
    start = time.monotonic()
    umgebung = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_XDIST_")}
    lauf = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *argumente], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          env=dict(umgebung, PYTHONIOENCODING="utf-8", ERP_ZEITGRENZE_PROBE=str(schlafen)))
    return lauf, time.monotonic() - start


# -- Zeitgrenze je Test ---------------------------------------------------------------------------------------------

def test_die_vorgabe_gilt_fuer_jeden_test(request):
    assert zeitgrenze.GRENZE == 300
    assert zeitgrenze.grenze_fuer(request.node) in (zeitgrenze.GRENZE, request.config.getoption("--zeitgrenze"), None)


def test_ein_haengender_test_beendet_den_lauf_mit_stapel_statt_ihn_anzuhalten():
    lauf, dauer = _lauf("-p", "no:xdist", "--zeitgrenze", "3", f"{DIESE}::test_probe_haengt")
    ausgabe = lauf.stdout + lauf.stderr
    assert lauf.returncode == zeitgrenze.CODE, ausgabe[-3000:]
    assert f"ZEITGRENZE: {DIESE}::test_probe_haengt läuft länger als 3 s" in ausgabe, ausgabe[-3000:]
    assert re.search(r"line \d+ in test_probe_haengt", ausgabe), ausgabe[-3000:]  # der Stapel zeigt, wo er hängt
    assert dauer < 45, dauer


def test_im_parallelen_lauf_geht_der_lauf_weiter():
    lauf, dauer = _lauf("-n", "2", "--dist", "loadfile", "--zeitgrenze", "3", f"{DIESE}::test_probe_haengt",
                        f"{DIESE}::test_probe_schnell")
    ausgabe = lauf.stdout + lauf.stderr
    assert lauf.returncode == 1, ausgabe[-3000:]  # rot, aber zu Ende gelaufen
    assert len(re.findall(r"crashed while running .*test_probe_haengt", ausgabe)) == 1, ausgabe[-3000:]  # nur ein Absturz
    assert "nicht noch einmal ausgef" in ausgabe, ausgabe[-3000:]  # xdist gab die Datei zurück, der Test lief nicht noch einmal
    assert re.search(r"\b1 passed\b", ausgabe), ausgabe[-3000:]  # der andere Test lief trotzdem
    assert dauer < 90, dauer


def test_ein_test_kann_eine_eigene_grenze_tragen():
    lauf, dauer = _lauf("-p", "no:xdist", f"{DIESE}::test_probe_mit_eigener_grenze", schlafen=30)
    assert lauf.returncode == zeitgrenze.CODE, (lauf.stdout + lauf.stderr)[-3000:]
    assert "test_probe_mit_eigener_grenze läuft länger als 1 s" in lauf.stdout + lauf.stderr
    assert dauer < 25, dauer


def test_zeitgrenze_null_schaltet_die_uhr_ab():
    lauf, _ = _lauf("-p", "no:xdist", "--zeitgrenze", "0", f"{DIESE}::test_probe_mit_eigener_grenze", schlafen=3)
    assert lauf.returncode == 0, (lauf.stdout + lauf.stderr)[-3000:]
    assert "ZEITGRENZE" not in lauf.stdout + lauf.stderr


# -- taskkill mit Zeitlimit --------------------------------------------------------------------------------------

@pytest.mark.skipif(os.name != "nt", reason="taskkill gibt es nur unter Windows")
@pytest.mark.parametrize("modul, funktion", [("cdp_klicktest", "beenden"), ("klicktest_alle", "_baum_beenden")])
def test_taskkill_haengt_nicht(modul, funktion, monkeypatch, capsys):
    werkzeug = _modul(modul)
    haengt = [sys.executable, "-c", "import time; time.sleep(60)"]
    monkeypatch.setattr(werkzeug, "_taskkill", lambda pid: haengt)
    monkeypatch.setattr(werkzeug, "TASKKILL_SEKUNDEN", 1)
    start = time.monotonic()
    getattr(werkzeug, funktion)(4242)
    assert time.monotonic() - start < 15
    assert "taskkill für PID 4242 nach 1 s abgebrochen" in capsys.readouterr().out


def test_taskkill_hat_ein_zeitlimit():
    assert _modul("cdp_klicktest").TASKKILL_SEKUNDEN == 30
    assert _modul("klicktest_alle").TASKKILL_SEKUNDEN == 30


# -- _run: die Verklemmung vom 15.10.2026 (PostgreSQL) --------------------------------------------------------------

@pytest.fixture
def sperrprobe():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_sperrprobe_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE zeilen (id integer PRIMARY KEY)"))
            conn.execute(text("INSERT INTO zeilen VALUES (1), (2)"))
        yield sessionmaker(bind=engine)
    finally:
        # Zuerst die Verbindungen beenden: hängt ein _run (Gegenprobe), wartet sonst schon das Schließen der Sitzungen.
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _sperren(s, zeile):
    s.execute(text("SELECT id FROM zeilen WHERE id = :z FOR UPDATE"), {"z": zeile})


def _erste(s):
    """Sperrt Zeile 1 und committet (angehalten: Zeile 1 bleibt gesperrt), braucht danach Zeile 2 und committet noch einmal --
    wie create_order_from_quote() bis 1.8.109 (Auftrag, dann Revision)."""
    _sperren(s, 1)
    s.commit()
    _sperren(s, 2)
    s.commit()
    return "fertig"


def _zweite(s):
    """Sperrt Zeile 2, wartet auf Zeile 1 und wird danach abgelehnt -- ohne Rollback hält ihre Transaktion Zeile 2."""
    _sperren(s, 2)
    _sperren(s, 1)
    raise ValueError("abgelehnt")


def _helfer():
    from tests import test_v363_zweck_abnahme as v363
    from tests import test_v365_abnahme_aus_protokoll as v365
    from tests import test_v375_rechnungen_sperren as v375
    return {"v363": v363._run, "v365": v365._run, "v375": v375._run}


@pytest.mark.parametrize("name", ["v363", "v365", "v375"])
def test_pg_run_schliesst_die_zweite_sitzung_vor_dem_warten_auf_die_erste(sperrprobe, name):
    Session = sperrprobe
    ergebnis = {}
    lauf = threading.Thread(target=lambda: ergebnis.update(r=_helfer()[name](Session, _erste, _zweite)), daemon=True)
    lauf.start()
    lauf.join(timeout=60)
    assert not lauf.is_alive(), f"_run aus {name} hängt (die erste Aktion wartet auf die Sperre der offenen zweiten Sitzung)"
    r = ergebnis["r"]
    zweite = r["result"] if isinstance(r, dict) else r[1]["result"] if isinstance(r[1], dict) else r[1]
    assert isinstance(zweite, ValueError), r
    if name != "v363":  # v363 gibt nur das Ergebnis der zweiten zurück
        assert r[0] == "fertig", r
