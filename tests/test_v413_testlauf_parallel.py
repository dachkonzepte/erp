"""Version 1.8.108 -- Testläufe parallel (Werkzeug-Runde, docs/archiv/testablauf-und-klicktests.md).

- Liegen gebliebene Schemas pgtest_* (tests/pg_schutz.py): jedes Schema, das ein Testprozess anlegt, trägt als Kommentar die Kennung
  dieses Prozesses (Rechner, PID, Startzeit); zu Beginn eines Testlaufs löscht tests/conftest.py nur Schemas, deren Prozess nicht mehr
  läuft -- nie eines eines laufenden Prozesses, nie eines ohne Kennung oder eines anderen Rechners, nie außerhalb von pgtest_*.
- klicktest_alle.py --gleichzeitig N: höchstens N zugleich, ein Klicktest mit ALLEIN läuft, während kein anderer läuft; jeder
  zeitkritische Klicktest (Fenster, in dem nichts geschehen darf; Zeitlimit; gedrosseltes Netz) setzt ALLEIN.
- Klicktests in einer Gegenprobe (Marker GEGENPROBE unter app/) brechen nach 2 min ab: eigene Prozesse beendet, Rückgabecode 3.

Die Tests gegen PostgreSQL sind opt-in (ERP_TEST_POSTGRES_URL) wie alle anderen.

Seit 1.9.31 (Nachtrag Stufe 2, Punkt A3): die Tests, die ein liegen gebliebenes Schema nachstellen, geben ihm einen eigenen
Rechnernamen (ERP_TEST_RECHNER, tests/pg_schutz.py). Bis dahin trug es die Kennung eines beendeten Prozesses dieses Rechners -- jeder
andere Testlauf, der in dem Moment startete (z. B. die pytest-Unterprozesse von tests/test_v416_testablauf.py im selben parallelen
Lauf), durfte es löschen, bevor der Test selbst aufräumte; dann fehlte es in dessen Meldung (einmal rot in Runde 9). Jetzt stellt jeder
der beiden Tests diesen anderen Lauf ausdrücklich nach (Aufräumen mit dem echten Rechnernamen) und verlangt, dass das Schema stehen
bleibt -- ohne Zeitfenster."""

import importlib.util
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.pg_schutz import (lauf_kennung, lauf_laeuft, liegen_gebliebene_schemas_loeschen, prozess_start,
                             schema_waechter_einrichten, waechter_aktiv)

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _modul(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_v413", SCRIPTS / f"{name}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


ALLE = _modul("klicktest_alle")


def _wartender_prozess() -> subprocess.Popen:
    """Ein Kindprozess, der läuft, bis seine Eingabe geschlossen wird."""
    return subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)


def _beendete_kennung() -> str:
    proc = _wartender_prozess()
    kennung = lauf_kennung(proc.pid)
    proc.communicate(timeout=30)
    return kennung


# -- Kennung des Testprozesses ----------------------------------------------------------------------------------

def test_prozess_start_kennt_laufende_und_beendete_prozesse():
    assert isinstance(prozess_start(os.getpid()), int)
    proc = _wartender_prozess()
    pid, start = proc.pid, prozess_start(proc.pid)
    assert isinstance(start, int)
    proc.communicate(timeout=30)
    assert prozess_start(pid) != start  # beendet: None, oder die PID gehört schon einem neuen Prozess


def test_lauf_laeuft_nur_fuer_den_prozess_der_kennung():
    eigene = lauf_kennung()
    assert re.fullmatch(r"erp-pytest host=[A-Za-z0-9._-]+ pid=\d+ start=\d+", eigene)
    assert lauf_laeuft(eigene) is True
    assert lauf_laeuft(_beendete_kennung()) is False
    assert lauf_laeuft(re.sub(r"start=\d+", "start=1", eigene)) is False  # dieselbe PID, anderer Prozess
    assert lauf_laeuft(re.sub(r"host=\S+", "host=anderer-rechner", eigene)) is None
    for unklar in (None, "", "irgendein Kommentar", eigene + " mehr"):
        assert lauf_laeuft(unklar) is None


def test_der_waechter_kennzeichnet_jedes_testschema():
    schema_waechter_einrichten()
    assert waechter_aktiv()


# -- Gegen PostgreSQL ------------------------------------------------------------------------------------------

@pytest.fixture
def pg_url():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    return PG_URL


def _eigener_rechner() -> str:
    """Ein Rechnername nur für diesen Test (ERP_TEST_RECHNER): seine Schemas sind für jeden anderen Lauf die eines anderen Rechners."""
    return f"pgtest-{uuid.uuid4().hex[:12]}"


def _anderer_lauf_raeumt_auf(url: str, monkeypatch) -> dict:
    """Ein gleichzeitig startender Testlauf: räumt mit dem echten Rechnernamen auf (wie tests/conftest.py zu Beginn jedes Laufs)."""
    with monkeypatch.context() as m:
        m.delenv("ERP_TEST_RECHNER", raising=False)
        return liegen_gebliebene_schemas_loeschen(url)


def _katalog(url):
    """Engine für Katalog und Verwaltung (search_path pg_catalog, nicht public -- Regel 27)."""
    return create_engine(url, connect_args={"options": "-csearch_path=pg_catalog"})


def _kommentar(katalog, schema):
    with katalog.connect() as conn:
        return conn.execute(text("SELECT obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname = :s"),
                            {"s": schema}).scalar()


def _gibt_es(katalog, schema) -> bool:
    with katalog.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM pg_namespace WHERE nspname = :s"), {"s": schema}).scalar() == 1


def test_pg_ein_angelegtes_testschema_traegt_die_kennung_dieses_prozesses(pg_url):
    schema = f"pgtest_kennung_{uuid.uuid4().hex[:8]}"
    admin, katalog = create_engine(pg_url), _katalog(pg_url)
    try:
        with admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        assert _kommentar(katalog, schema) == lauf_kennung()
        assert lauf_laeuft(_kommentar(katalog, schema)) is True
    finally:
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()
        katalog.dispose()


def test_pg_aufraeumen_loescht_nur_schemas_beendeter_prozesse(pg_url, monkeypatch):
    monkeypatch.setenv("ERP_TEST_RECHNER", _eigener_rechner())  # die Kennungen unten tragen ihn; kein anderer Lauf räumt sie weg
    kurz = uuid.uuid4().hex[:8]
    lebend = _wartender_prozess()
    schemas = {
        "beendet": (f"pgtest_auf_beendet_{kurz}", _beendete_kennung()),
        "laufend": (f"pgtest_auf_laufend_{kurz}", lauf_kennung(lebend.pid)),
        "ohne": (f"pgtest_auf_ohne_{kurz}", None),
        "fremd": (f"pgtest_auf_fremd_{kurz}", f"erp-pytest host=anderer-rechner pid={os.getpid()} start=1"),
        "anderes_muster": (f"pgtestauf_{kurz}", _beendete_kennung()),  # kein pgtest_: nie angefasst
    }
    katalog = _katalog(pg_url)
    try:
        with katalog.connect() as conn:
            public_vorher = conn.execute(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                              "WHERE n.nspname = 'public'")).scalar()
        for schema, kennung in schemas.values():
            with katalog.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA {schema}"))
                conn.execute(text(f"CREATE TABLE {schema}.probe (id integer)"))
                conn.execute(text(f"COMMENT ON SCHEMA {schema} IS " + ("NULL" if kennung is None else f"'{kennung}'")))

        # ein anderer Lauf, der in diesem Moment startet, lässt alle stehen -- für ihn sind es Schemas eines anderen Rechners
        andere = _anderer_lauf_raeumt_auf(pg_url, monkeypatch)
        assert not {s for s, _ in schemas.values()} & set(andere["geloescht"])
        assert [_gibt_es(katalog, s) for s, _ in schemas.values()] == [True] * 5

        ergebnis = liegen_gebliebene_schemas_loeschen(pg_url)

        assert schemas["beendet"][0] in ergebnis["geloescht"]
        assert schemas["laufend"][0] in ergebnis["laufend"]
        assert schemas["ohne"][0] in ergebnis["ohne_kennung"]
        assert schemas["fremd"][0] in ergebnis["fremder_rechner"]
        alle = [n for namen in ergebnis.values() for n in namen]
        assert schemas["anderes_muster"][0] not in alle and not any(n.startswith("public") for n in alle)
        assert [_gibt_es(katalog, s) for s, _ in schemas.values()] == [False, True, True, True, True]
        with katalog.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                     "WHERE n.nspname = 'public'")).scalar() == public_vorher
    finally:
        lebend.communicate(timeout=30)
        for schema, _ in schemas.values():
            with katalog.begin() as conn:
                conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        katalog.dispose()


def test_pg_ein_testlauf_raeumt_zu_beginn_auf(pg_url, tmp_path, monkeypatch):
    """Ende zu Ende: ein Testlauf (pytest im Unterprozess) löscht beim Start ein liegen gebliebenes Schema und nennt es. Seit 1.9.31
    mit eigenem Rechnernamen: ein anderer Lauf, der vorher aufräumt, lässt es stehen (nachgestellt), der Unterprozess löscht genau dieses."""
    rechner = _eigener_rechner()
    monkeypatch.setenv("ERP_TEST_RECHNER", rechner)
    schema = f"pgtest_lauf_{uuid.uuid4().hex[:8]}"
    katalog = _katalog(pg_url)
    try:
        with katalog.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
            conn.execute(text(f"COMMENT ON SCHEMA {schema} IS '{_beendete_kennung()}'"))
        andere = _anderer_lauf_raeumt_auf(pg_url, monkeypatch)
        assert schema in andere["fremder_rechner"] and _gibt_es(katalog, schema)
        lauf = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
                               f"{Path(__file__).relative_to(ROOT).as_posix()}::test_allein_grund_wird_gelesen"],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8", ERP_TEST_RECHNER=rechner))
        assert lauf.returncode == 0, lauf.stdout[-2000:] + lauf.stderr[-2000:]
        # nur dieser Lauf kennt den Rechnernamen -- er löscht genau dieses eine Schema
        assert f"PostgreSQL-Testschemas: liegen geblieben, gelöscht: 1 ({schema})" in lauf.stdout, lauf.stdout[-2000:]
        assert not _gibt_es(katalog, schema)
    finally:
        with katalog.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        katalog.dispose()


# -- klicktest_alle.py --gleichzeitig ---------------------------------------------------------------------------

ZEITKRITISCH = re.compile(r"""warten\(\s*["']false["']|__dkZeitlimit|emulateNetworkConditions|setCPUThrottlingRate""")


def test_jeder_zeitkritische_klicktest_laeuft_allein():
    """Ein Klicktest mit einem Fenster, in dem etwas NICHT geschehen darf (warten("false", …)), einem Zeitlimit oder gedrosseltem
    Netz prüft unter Last schwächer (das Fenster ist zu kurz) oder wird rot -- er trägt ALLEIN und läuft allein."""
    zeitkritisch = {p.stem for p in SCRIPTS.glob("klicktest_*.py") if ZEITKRITISCH.search(p.read_text(encoding="utf-8"))}
    assert {"klicktest_abschliessen", "klicktest_anmelden", "klicktest_hochladen", "klicktest_veraltete_antworten",
            "klicktest_feierabend", "klicktest_fremde_seite"} <= zeitkritisch
    ohne = sorted(n for n in zeitkritisch if not ALLE.allein_grund(SCRIPTS / f"{n}.py"))
    assert ohne == [], "zeitkritisch ohne ALLEIN: " + ", ".join(ohne)


def test_allein_grund_wird_gelesen(tmp_path):
    for inhalt, soll in (('ALLEIN = "Fenster von 1 s"\n', "Fenster von 1 s"), ("x = 1\n", None), ('ALLEIN = ""\n', None),
                         ("ALLEIN = True\n", None), ('def f():\n    ALLEIN = "innen"\n', None)):
        datei = tmp_path / "klicktest_x.py"
        datei.write_text(inhalt, encoding="utf-8")
        assert ALLE.allein_grund(datei) == soll, inhalt


SCHEIN = """import sys, time, pathlib
zeiten = pathlib.Path({ordner!r}) / (pathlib.Path(__file__).stem + ".zeiten")
zeiten.write_text(f"{{time.monotonic()}}\\n")
time.sleep({dauer})
zeiten.write_text(zeiten.read_text() + f"{{time.monotonic()}}\\n")
print("2 von 2 Prüfungen wie erwartet")
sys.exit({code})
"""


UMGEBUNG = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")  # wie klicktest_alle.main()


def _schein(ordner: Path, name: str, dauer=0.6, code=0, allein=False) -> Path:
    """Ein Schein-Klicktest: schreibt Start und Ende (time.monotonic(), über Prozesse vergleichbar) in <name>.zeiten."""
    datei = ordner / f"{name}.py"
    datei.write_text(SCHEIN.format(ordner=str(ordner), dauer=dauer, code=code) + ('ALLEIN = "zeitkritisch"\n' if allein else ""),
                     encoding="utf-8")
    return datei


def _zeitraeume(ordner: Path) -> dict[str, tuple[float, float | None]]:
    raeume = {}
    for datei in ordner.glob("*.zeiten"):
        werte = [float(z) for z in datei.read_text().split()]
        raeume[datei.stem] = (werte[0], werte[1] if len(werte) > 1 else None)
    return raeume


def test_gleichzeitig_hoechstens_n_und_allein_ohne_andere(tmp_path):
    ausgabe = tmp_path / "aus"
    ausgabe.mkdir()
    allein = [_schein(tmp_path, f"klicktest_a{i}", allein=True) for i in range(2)]
    rest = [_schein(tmp_path, f"klicktest_b{i}", dauer=2.0) for i in range(7)]
    assert [ALLE.allein_grund(p) for p in allein + rest] == ["zeitkritisch"] * 2 + [None] * 7
    zeilen = ALLE.ausfuehren([(allein, 1), (rest, 3)], ausgabe, UMGEBUNG, 120, 9)
    assert sorted(z[:3] for z in zeilen) == [(p.stem, "OK", "2/2") for p in allein + rest]
    raeume = _zeitraeume(tmp_path)
    assert len(raeume) == 9 and all(e is not None for _, e in raeume.values())

    def zugleich(t):
        return sum(1 for a, e in raeume.values() if a <= t < e)

    assert max(zugleich(a) for a, _ in raeume.values()) == 3  # mehrere zugleich, nie mehr als drei
    for p in allein:
        a, e = raeume[p.stem]
        assert all(e2 <= a or a2 >= e for n, (a2, e2) in raeume.items() if n != p.stem), f"{p.stem} lief nicht allein"


def test_reihenfolge_allein_zuerst_dann_die_laengsten(tmp_path, monkeypatch):
    skripte = [_schein(tmp_path, n, allein=n.endswith("x")) for n in
               ("klicktest_a", "klicktest_bx", "klicktest_c", "klicktest_d", "klicktest_ex", "klicktest_neu")]
    monkeypatch.setattr(ALLE, "KLICKTEST_DAUERN", {"klicktest_a": 10.0, "klicktest_c": 30.0, "klicktest_d": 20.0, "klicktest_bx": 99.0})
    assert ALLE.gruppen(skripte, 1) == [(skripte, 1)]  # nacheinander: alphabetisch wie bisher
    (allein, n1), (rest, n4) = ALLE.gruppen(skripte, 4)
    assert ([p.stem for p in allein], n1) == (["klicktest_bx", "klicktest_ex"], 1)
    assert ([p.stem for p in rest], n4) == (["klicktest_neu", "klicktest_c", "klicktest_d", "klicktest_a"], 4)


def test_echte_reihenfolge_mit_vier_zugleich():
    (allein, _), (rest, _) = ALLE.gruppen(ALLE.klicktests([], None), 4)
    assert {p.stem for p in allein} == {"klicktest_abschliessen", "klicktest_anmelden", "klicktest_feierabend",
                                        "klicktest_fremde_seite", "klicktest_hochladen", "klicktest_veraltete_antworten"}
    assert len(allein) + len(rest) == len(ALLE.klicktests([], None)) and "klicktest_alle" not in {p.stem for p in rest}


def test_nacheinander_wie_bisher_und_zeitlimit(tmp_path):
    ausgabe = tmp_path / "aus"
    ausgabe.mkdir()
    skripte = [_schein(tmp_path, "klicktest_c0"), _schein(tmp_path, "klicktest_c1", code=1),
               _schein(tmp_path, "klicktest_c2", code=3), _schein(tmp_path, "klicktest_c3", dauer=60)]
    beginn = time.monotonic()
    zeilen = ALLE.ausfuehren([(skripte, 1)], ausgabe, UMGEBUNG, 8, 4)
    assert time.monotonic() - beginn < 50
    assert [z[:2] for z in zeilen] == [("klicktest_c0", "OK"), ("klicktest_c1", "ROT (1)"), ("klicktest_c2", "Zeitlimit"),
                                       ("klicktest_c3", "Zeitlimit")]
    raeume = _zeitraeume(tmp_path)
    assert raeume["klicktest_c0"][1] <= raeume["klicktest_c1"][0] and raeume["klicktest_c1"][1] <= raeume["klicktest_c2"][0]
    assert raeume["klicktest_c3"][1] is None  # beendet, bevor es fertig war


# -- Klicktests in einer Gegenprobe ----------------------------------------------------------------------------

def test_gegenprobe_im_code_findet_den_marker(tmp_path):
    werkzeug = _modul("cdp_klicktest")
    (tmp_path / "app" / "templates").mkdir(parents=True)
    (tmp_path / "app" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "app" / "bild.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00")
    assert werkzeug.gegenprobe_im_code(tmp_path) is None
    (tmp_path / "app" / "templates" / "s.html").write_text("<p>\n<script>/* " + "GEGEN" + "PROBE */</script>\n", encoding="utf-8")
    assert werkzeug.gegenprobe_im_code(tmp_path) == "app/templates/s.html:2"
    assert werkzeug.ZEITLIMIT_GEGENPROBE == 120
    assert werkzeug.gegenprobe_im_code() is None  # im echten app/ steht keiner (Regel 24, test_v357)


HAENGENDER_KLICKTEST = """import os, sys, time
from pathlib import Path
if "--nur-befuellen" in sys.argv:  # der Kindprozess des Befüllens meldet sich, bevor er app.main lädt
    Path({pid_datei!r}).write_text(str(os.getpid()))
sys.path.insert(0, {scripts!r})
import cdp_klicktest
if {gegenprobe!r}:
    cdp_klicktest.gegenprobe_im_code = lambda root=None: "app/schein.py:1"
cdp_klicktest.ZEITLIMIT_GEGENPROBE = {grenze}

def befuellen(db, k):
    time.sleep(300)  # hängt wie eine Seite, die im Kreis läuft
    return {{}}

async def pruefen(tab, seed, p):
    pass

if __name__ == "__main__":
    sys.exit(cdp_klicktest.klicktest_main(befuellen, pruefen))
"""


@pytest.mark.parametrize("gegenprobe, grenze, argumente, meldung", [
    (True, 6, [], "Zeitlimit 6 s (Gegenprobe läuft, Marker GEGENPROBE in app/schein.py:1)"),
    (True, 6, ["--zeitlimit", "100"], "Zeitlimit 6 s (Gegenprobe läuft, Marker GEGENPROBE in app/schein.py:1)"),  # nicht länger
    (True, 100, ["--zeitlimit", "6"], "Zeitlimit 6 s (--zeitlimit)"),  # kürzer geht
    (False, 6, ["--zeitlimit", "6"], "Zeitlimit 6 s (--zeitlimit)"),
], ids=["gegenprobe", "gegenprobe-nicht-laenger", "kuerzer-von-hand", "ohne-gegenprobe-von-hand"])
def test_klicktest_bricht_nach_dem_zeitlimit_ab_und_beendet_seine_prozesse(tmp_path, gegenprobe, grenze, argumente, meldung):
    """Ende zu Ende mit einem Klicktest, dessen Befüllen hängt: Abbruch nach dem Limit (in der Gegenprobe ZEITLIMIT_GEGENPROBE,
    hier verkürzt), Rückgabecode 3, der hängende Kindprozess des Befüllens ist beendet."""
    skript, pid_datei = tmp_path / "klicktest_haengt.py", tmp_path / "befuellen.pid"
    skript.write_text(HAENGENDER_KLICKTEST.format(scripts=str(SCRIPTS), gegenprobe=gegenprobe, grenze=grenze,
                                                  pid_datei=str(pid_datei)), encoding="utf-8")
    beginn = time.monotonic()
    lauf = subprocess.run([sys.executable, str(skript), "--arbeitsordner", str(tmp_path / "ordner"), *argumente], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=150,
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    dauer = time.monotonic() - beginn
    assert lauf.returncode == 3, lauf.stdout[-2000:] + lauf.stderr[-2000:]
    assert meldung in lauf.stdout
    assert "ABBRUCH: Zeitlimit 6 s erreicht" in lauf.stdout
    assert 6 <= dauer < 90
    assert pid_datei.exists()
    assert prozess_start(int(pid_datei.read_text())) is None  # das hängende Befüllen läuft nicht mehr


def test_ohne_gegenprobe_und_ohne_angabe_kein_zeitlimit():
    werkzeug = _modul("cdp_klicktest")
    assert werkzeug.gegenprobe_im_code() is None
    quelle = (SCRIPTS / "cdp_klicktest.py").read_text(encoding="utf-8")
    assert "wachhund = Wachhund(*min(grenzen)) if grenzen else None" in quelle
