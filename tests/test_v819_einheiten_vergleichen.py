"""Version 1.11.26 (Frage F2 aus 1.11.22, bestätigt 25.11.2026): update.sh vergleicht die Einheiten aus scripts/server/ mit den installierten und meldet
jede Abweichung mit dem Befehl -- es installiert nichts (scripts/pruefe_einheiten.py). Den Aufruf fügt scripts/server/update_einheiten_einfuegen.py einmal
in update.sh ein, nur vor genau einer Zeile FERTIG (Server-Schritt S11).

    vergleichen  alle gleich: Rückgabe 0, eine Zeile; abweichend: „!!! … weicht vom Repo ab“ mit diff- und install-Befehl, fehlend: „ist nicht installiert“,
                 Rückgabe 1; ein Dienst mit gleichnamigem Timer ohne Neustart; der Ordner der installierten Einheiten bleibt unverändert
    Kindprozess  wie update.sh es aufruft, aus einem anderen Ordner (das Skript findet das Repo über seinen eigenen Pfad)
    einfügen     vor der Zeile FERTIG, genau einmal; ein zweites Mal ändert nichts; 0 oder 2 Zeilen FERTIG oder Windows-Zeilenenden: Rückgabe 1, nichts geändert
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EINHEITEN = ["erp-portal.service", "erp-portalpost.service", "erp-webanfragen.service", "erp-webanfragen.timer"]


def _modul(name: str, pfad: Path):
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


pe = _modul("pruefe_einheiten", ROOT / "scripts" / "pruefe_einheiten.py")
ue = _modul("update_einheiten_einfuegen", ROOT / "scripts" / "server" / "update_einheiten_einfuegen.py")


def _installiert(tmp_path: Path, *, ohne=(), anders=()) -> Path:
    ziel = tmp_path / "system"
    ziel.mkdir()
    for datei in pe.einheiten():
        if datei.name in ohne:
            continue
        inhalt = datei.read_bytes()
        (ziel / datei.name).write_bytes(inhalt + "# von Hand geändert\n".encode() if datei.name in anders else inhalt)
    return ziel


def _stand(ordner: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(ordner.iterdir())}


def test_die_einheiten_des_repos():
    assert [d.name for d in pe.einheiten()] == EINHEITEN


def test_alle_wie_im_repo(tmp_path):
    ziel = _installiert(tmp_path)
    vorher, zeilen = _stand(ziel), []
    assert pe.main(["--ziel", str(ziel)], ausgabe=zeilen.append) == 0
    assert zeilen == ["Einheiten wie im Repo: " + ", ".join(EINHEITEN) + "."]
    assert _stand(ziel) == vorher


def test_abweichung_und_fehlende_mit_befehl_nichts_installiert(tmp_path):
    ziel = _installiert(tmp_path, anders=("erp-portal.service",), ohne=("erp-webanfragen.timer",))
    vorher, zeilen = _stand(ziel), []
    assert pe.main(["--ziel", str(ziel)], ausgabe=zeilen.append) == 1
    text = "\n".join(zeilen)
    quelle, installiert = (ROOT / "scripts" / "server" / "erp-portal.service").as_posix(), (ziel / "erp-portal.service").as_posix()
    assert "!!! erp-portal.service weicht vom Repo ab -- installiert ist eine andere Fassung." in zeilen
    assert f"    Ansehen:    diff -u {installiert} {quelle}" in zeilen
    assert (f"    Übernehmen: sudo install -m 644 -o root -g root {quelle} {ziel.as_posix()}/ && sudo systemctl daemon-reload "
            "&& sudo systemctl restart erp-portal.service") in zeilen
    assert f"!!! erp-webanfragen.timer ist nicht installiert ({(ziel / 'erp-webanfragen.timer').as_posix()} fehlt)" in text
    assert "erp-portalpost.service" not in text and "erp-webanfragen.service" not in text  # gleich -- nicht gemeldet
    assert zeilen[-1] == "Einheiten: 4 im Repo, mindestens eine weicht ab -- nichts installiert."
    assert _stand(ziel) == vorher  # nichts installiert, nichts geschrieben


def test_dienst_mit_timer_ohne_neustart(tmp_path):
    ziel = _installiert(tmp_path, anders=("erp-webanfragen.service",))
    zeilen = []
    assert pe.main(["--ziel", str(ziel)], ausgabe=zeilen.append) == 1
    [uebernehmen] = [z for z in zeilen if "Übernehmen:" in z]
    assert uebernehmen.endswith("sudo systemctl daemon-reload   (läuft über erp-webanfragen.timer -- kein Neustart nötig)"), uebernehmen
    assert "restart" not in uebernehmen


def test_als_kindprozess_wie_update_sh(tmp_path):
    ziel = _installiert(tmp_path, anders=("erp-portalpost.service",))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pruefe_einheiten.py"), "--ziel", str(ziel)], cwd=str(tmp_path), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 1 and "!!! erp-portalpost.service weicht vom Repo ab" in r.stdout and r.stderr == "", r
    (tmp_path / "zwei").mkdir()
    gleich = _installiert(tmp_path / "zwei")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pruefe_einheiten.py"), "--ziel", str(gleich)], cwd=str(tmp_path), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0 and r.stdout == "Einheiten wie im Repo: " + ", ".join(EINHEITEN) + ".\n" and r.stderr == "", r


UPDATE = (b"#!/bin/bash\nset -e\ncd /home/tobias/erp\nPHASE=\"Neustart\"\necho \"=== Neustart ===\"\n"
          b"sudo systemctl restart erp erp-portal erp-portalpost\n" + ue.ANKER + b"exit 0\n")


def test_einfuegen_vor_fertig_und_nur_einmal(tmp_path):
    datei = tmp_path / "update.sh"
    datei.write_bytes(UPDATE)
    zeilen = []
    assert ue.main([str(datei)], ausgabe=zeilen.append) == 0
    neu = datei.read_bytes()
    assert neu == UPDATE.replace(ue.ANKER, ue.EINSCHUB + ue.ANKER)
    assert neu.index(b'echo "=== Einheiten ==="') < neu.index(b'echo "=== FERTIG')
    assert b"/home/tobias/erp/.venv/bin/python /home/tobias/erp/scripts/pruefe_einheiten.py || echo" in neu
    assert zeilen == ["update.sh geändert: der Vergleich der Einheiten steht vor der Zeile FERTIG."]
    assert ue.main([str(datei)], ausgabe=zeilen.append) == 0 and datei.read_bytes() == neu  # ein zweites Mal: nichts geändert
    assert zeilen[-1] == "Der Vergleich der Einheiten steht schon in update.sh -- nichts geändert."


@pytest.mark.parametrize("inhalt, grund", [
    (UPDATE.replace(ue.ANKER, b""), "die Zeile FERTIG steht 0-mal"),
    (UPDATE + ue.ANKER, "die Zeile FERTIG steht 2-mal"),
    (UPDATE.replace(b"\n", b"\r\n"), "Windows-Zeilenenden"),
])
def test_nur_bei_eindeutiger_stelle(tmp_path, inhalt, grund):
    datei = tmp_path / "update.sh"
    datei.write_bytes(inhalt)
    zeilen = []
    assert ue.main([str(datei)], ausgabe=zeilen.append) == 1
    assert datei.read_bytes() == inhalt and grund in zeilen[-1] and "nichts geändert" in zeilen[-1]
