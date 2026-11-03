"""Version 1.9.185 (L1a-Korrekturen, Punkt 6): die Klicktests legen ihre Ordner nie direkt unter einem Laufwerk an.

    ohne Angabe     ein neuer Ordner unter %TEMP%\\erp-klicktests (KLICKTEST_ORDNER, ERP_KLICKTEST_ORDNER ändert ihn)
    Name            ohne Pfad landet er dort (--arbeitsordner eines Klicktests, --ausgabe von klicktest_alle.py)
    Laufwerk        C:\\kt_x -> Abbruch mit Meldung; ein tieferer Pfad bleibt, wie er ist
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _werkzeug(monkeypatch, wurzel: Path):
    monkeypatch.setenv("ERP_KLICKTEST_ORDNER", str(wurzel))
    spec = importlib.util.spec_from_file_location("cdp_klicktest_v597", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_ohne_angabe_und_name_unter_dem_klicktest_ordner(tmp_path, monkeypatch):
    k = _werkzeug(monkeypatch, tmp_path / "erp-klicktests")
    neu = k.klicktest_ordner(None, "lauf-")
    assert neu.parent == (tmp_path / "erp-klicktests").resolve() and neu.name.startswith("lauf-") and neu.is_dir()
    assert k.klicktest_ordner(Path("end_185"), "lauf-") == (tmp_path / "erp-klicktests" / "end_185").resolve()


def test_direkt_unter_einem_laufwerk_abgelehnt(tmp_path, monkeypatch):
    k = _werkzeug(monkeypatch, tmp_path / "erp-klicktests")
    anker = Path(tmp_path.anchor)
    with pytest.raises(SystemExit, match="liegt direkt unter"):
        k.klicktest_ordner(anker / "kt_nach_185", "lauf-")
    assert not (anker / "kt_nach_185").exists()
    tiefer = tmp_path / "eigener" / "lauf"
    assert k.klicktest_ordner(tiefer, "lauf-") == tiefer.resolve()


def test_beide_werkzeuge_nehmen_die_regel():
    """Arbeitsordner eines Klicktests und Ausgabe von klicktest_alle.py gehen über klicktest_ordner() -- kein mkdtemp() mehr ohne Ordner."""
    cdp = (SCRIPTS / "cdp_klicktest.py").read_text(encoding="utf-8")
    alle = (SCRIPTS / "klicktest_alle.py").read_text(encoding="utf-8")
    assert 'ordner = klicktest_ordner(args.arbeitsordner, "erp-klicktest-")' in cdp
    assert 'ausgabe = klicktest_ordner(args.ausgabe, "lauf-")' in alle and "from cdp_klicktest import klicktest_ordner" in alle
    assert "tempfile.mkdtemp(prefix=" not in alle and cdp.count("tempfile.mkdtemp(") == 1  # nur in klicktest_ordner(), mit dir=
