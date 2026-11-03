"""Version 1.9.183 (L1a-Korrekturen, Punkt 4): Reihenfolge der Tests je Testprozess (tests/reihenfolge.py, eingehängt in tests/conftest.py).

    mitschreiben  je Arbeitsprozess eine Datei gw<N>.txt (ohne -n haupt.txt), je Test Beginn, Ergebnis, Knoten-ID; der Hauptprozess eines
                  parallelen Laufs schreibt nichts; ein neuer Lauf leert den Ordner
    verschachtelt ein pytest, das ein Test selbst startet (tests/test_v416_testablauf.py), und seine Arbeitsprozesse schreiben und leeren nichts
    nachstellen  python -m tests.reihenfolge ORDNER: die Dateien je Prozess in ihrer Reihenfolge, --bis schneidet ab
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from tests import reihenfolge

ROOT = Path(__file__).resolve().parent.parent
ZEILE = re.compile(r"^\d\d:\d\d:\d\d\.\d{3}\t(passed|failed|skipped|error \(\w+\))\t\S+$")


def _dateien(tmp_path: Path) -> list[Path]:
    a = tmp_path / "test_a_probe.py"
    a.write_text("def test_eins():\n    pass\n\ndef test_zwei():\n    assert False\n", encoding="utf-8")
    b = tmp_path / "test_b_probe.py"
    b.write_text("import pytest\n\ndef test_drei():\n    pass\n\n@pytest.mark.skip\ndef test_vier():\n    pass\n", encoding="utf-8")
    return [a, b]


def _lauf(tmp_path: Path, ordner: Path, *argumente: str, verschachtelt: bool = False) -> subprocess.CompletedProcess:
    umgebung = {k: v for k, v in os.environ.items() if k not in (reihenfolge.LAUF, reihenfolge.AUS, "ERP_TEST_POSTGRES_URL")}
    umgebung["ERP_TEST_REIHENFOLGE"] = str(ordner)
    if verschachtelt:
        umgebung[reihenfolge.LAUF] = "1"  # wie in einem Test eines laufenden Laufs
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "tests.conftest", "-p", "no:cacheprovider", "--rootdir", str(ROOT),
                           *argumente, *map(str, _dateien(tmp_path))], cwd=ROOT, env=umgebung, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=240)


def _zeilen(ordner: Path) -> dict[str, list[str]]:
    return {d.name: d.read_text(encoding="utf-8").splitlines() for d in sorted(ordner.glob("*.txt"))}


def test_parallel_je_arbeitsprozess_eine_datei(tmp_path):
    ordner = tmp_path / "r"
    ordner.mkdir()
    (ordner / "gw9.txt").write_text("vom letzten Lauf\n", encoding="utf-8")
    lauf = _lauf(tmp_path, ordner, "-n", "2", "--dist", "loadfile")
    assert "1 failed, 2 passed, 1 skipped" in lauf.stdout, lauf.stdout[-2000:]
    zeilen = _zeilen(ordner)
    assert set(zeilen) <= {"gw0.txt", "gw1.txt"} and zeilen, zeilen  # gw9 vom letzten Lauf geleert, der Hauptprozess schreibt nichts
    alle = [z for liste in zeilen.values() for z in liste]
    assert all(ZEILE.match(z) for z in alle), alle
    ergebnis = {z.split("\t")[2].split("::")[-1]: z.split("\t")[1] for z in alle}
    assert ergebnis == {"test_eins": "passed", "test_zwei": "failed", "test_drei": "passed", "test_vier": "skipped"}
    for liste in zeilen.values():  # --dist loadfile: eine Datei bleibt bei einem Arbeitsprozess, in ihrer Reihenfolge
        namen = [z.split("::")[-1] for z in liste]
        assert namen in (["test_eins", "test_zwei"], ["test_drei", "test_vier"], ["test_eins", "test_zwei", "test_drei", "test_vier"],
                         ["test_drei", "test_vier", "test_eins", "test_zwei"]), namen


def test_ohne_n_eine_datei_haupt(tmp_path):
    ordner = tmp_path / "r"
    _lauf(tmp_path, ordner)
    assert list(_zeilen(ordner)) == ["haupt.txt"] and len(_zeilen(ordner)["haupt.txt"]) == 4


def test_verschachtelt_schreibt_und_leert_nichts(tmp_path):
    ordner = tmp_path / "r"
    ordner.mkdir()
    (ordner / "gw0.txt").write_text("12:00:00.000\tpassed\ttests/test_x.py::test_y\n", encoding="utf-8")
    lauf = _lauf(tmp_path, ordner, "-n", "2", "--dist", "loadfile", verschachtelt=True)
    assert "1 failed, 2 passed, 1 skipped" in lauf.stdout, lauf.stdout[-2000:]
    assert _zeilen(ordner) == {"gw0.txt": ["12:00:00.000\tpassed\ttests/test_x.py::test_y"]}


def test_nachstellen_nennt_die_dateien_in_ihrer_reihenfolge(tmp_path, capsys):
    (tmp_path / "gw3.txt").write_text("".join(f"10:00:0{i}.000\tpassed\t{n}\n" for i, n in enumerate([
        "tests/test_c.py::test_1", "tests/test_c.py::test_2", "tests/test_a.py::test_1", "tests/test_v564_x.py::test_1", "tests/test_b.py::test_1"])),
        encoding="utf-8")
    assert reihenfolge.dateien(tmp_path / "gw3.txt") == ["tests/test_c.py", "tests/test_a.py", "tests/test_v564_x.py", "tests/test_b.py"]
    assert reihenfolge.dateien(tmp_path / "gw3.txt", bis="v564") == ["tests/test_c.py", "tests/test_a.py", "tests/test_v564_x.py"]
    assert reihenfolge.main([str(tmp_path), "--bis", "v564", "--nur-zeigen"]) == 0
    assert "gw3: 3 Dateien, zuletzt tests/test_v564_x.py" in capsys.readouterr().out
