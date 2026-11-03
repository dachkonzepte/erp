"""Reihenfolge der Tests je Testprozess -- seit 1.9.183 (L1a-Korrekturen, Punkt 4, Vorgabe Tobias 03.11.2026).

Anlass: test_v564_plantafel_leistung.py::test_alte_einsaetze_kosten_nichts war im vollen Lauf von 1.9.177 einmal rot (30 statt 28 Abfragen),
einzeln nie; welche Tests derselbe Arbeitsprozess davor ausgeführt hatte, ließ sich danach nicht mehr sagen.

Mitschreiben (tests/conftest.py): jeder Testprozess schreibt je Test eine Zeile -- Beginn (Uhrzeit), Ergebnis, Knoten-ID -- im parallelen Lauf
(pytest-xdist) je Arbeitsprozess eine Datei gw0.txt … gw15.txt, ohne -n haupt.txt. Ordner: Umgebungsvariable ERP_TEST_REIHENFOLGE, sonst
.pytest_cache/reihenfolge (nicht im Repository; eine Option auf der Befehlszeile kennen die Arbeitsprozesse nicht). Der Ordner gilt für den letzten Lauf -- der Hauptprozess leert ihn zu Beginn; nach einem roten
Lauf also zuerst kopieren.

Nachstellen (aus dem Projektordner):

    .venv\\Scripts\\python.exe -m tests.reihenfolge ORDNER [--arbeitsprozess gw5] [--bis TEIL] [--nur-zeigen]

ohne --arbeitsprozess alle Arbeitsprozesse des Laufs zugleich, je einer mit genau seinen Testdateien in seiner Reihenfolge (dieselbe Last); mit
--arbeitsprozess nur dieser. --bis TEIL: nur bis zur ersten Datei, deren Pfad TEIL enthält (eingeschlossen). Je Prozess ein Protokoll im
Ordner nachgestellt_<Uhrzeit> neben den Dateien; Rückgabecode 1, wenn ein Prozess rot war. Nachgestellt wird die Reihenfolge der Dateien --
innerhalb einer Datei laufen die Tests wie immer in der Reihenfolge der Datei (--dist loadfile verteilt ganze Dateien).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUF = "ERP_TEST_REIHENFOLGE_LAUF"  # gesetzt vom Hauptprozess eines Laufs, geerbt von Arbeitsprozessen und von jedem pytest, das ein Test startet
AUS = "ERP_TEST_REIHENFOLGE_AUS"  # gesetzt von einem solchen verschachtelten pytest, geerbt von seinen Arbeitsprozessen: sie schreiben nicht
_ziel: Path | None = None
_laufend: dict[str, tuple[datetime, str]] = {}


def ordner(config) -> Path:
    wert = os.environ.get("ERP_TEST_REIHENFOLGE")
    return Path(wert) if wert else Path(str(config.rootpath)) / ".pytest_cache" / "reihenfolge"


def einrichten(config) -> None:
    """pytest_configure: der Hauptprozess leert den Ordner (alte Dateien des letzten Laufs), jeder Prozess, der Tests ausführt, merkt sich
    seine Datei -- der Hauptprozess eines parallelen Laufs führt keine aus (er bekommt die Berichte der Arbeitsprozesse nur weitergereicht)."""
    global _ziel
    o = ordner(config)
    o.mkdir(parents=True, exist_ok=True)
    arbeitsprozess = config.workerinput["workerid"] if hasattr(config, "workerinput") else None
    if os.environ.get(AUS):  # ein Arbeitsprozess eines verschachtelten Laufs
        return
    if arbeitsprozess is None:
        if os.environ.get(LAUF):  # ein pytest, das ein Test selbst startet (z. B. tests/test_v416_testablauf.py): gehört nicht dazu, leert nichts
            os.environ[AUS] = "1"  # auch seine Arbeitsprozesse nicht
            return
        os.environ[LAUF] = str(os.getpid())
        for alt in o.glob("*.txt"):
            alt.unlink()
        if (getattr(config.option, "dist", "no") or "no") != "no":
            return
    _ziel = o / f"{arbeitsprozess or 'haupt'}.txt"


def gestartet(nodeid: str) -> None:
    if _ziel is not None:
        _laufend[nodeid] = (datetime.now(), "passed")


def bericht(report) -> None:
    """Je Phase das Ergebnis festhalten, nach dem Abbau die Zeile schreiben (sofort auf die Platte -- ein abgestürzter Prozess hinterlässt
    alles bis zum letzten fertigen Test)."""
    if _ziel is None:
        return
    beginn, ergebnis = _laufend.get(report.nodeid, (datetime.now(), "passed"))
    if report.failed:
        ergebnis = "failed" if report.when == "call" else f"error ({report.when})"
    elif report.skipped and ergebnis == "passed":
        ergebnis = "skipped"
    _laufend[report.nodeid] = (beginn, ergebnis)
    if report.when == "teardown":
        _laufend.pop(report.nodeid, None)
        with open(_ziel, "a", encoding="utf-8") as f:
            f.write(f"{beginn:%H:%M:%S.%f}"[:-3] + f"\t{ergebnis}\t{report.nodeid}\n")


def dateien(datei: Path, bis: str | None = None) -> list[str]:
    """Die Testdateien eines Prozesses in der Reihenfolge, in der er sie begonnen hat (jede einmal)."""
    liste: list[str] = []
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        teile = zeile.split("\t")
        if len(teile) != 3:
            continue
        pfad = teile[2].split("::", 1)[0]
        if pfad not in liste:
            liste.append(pfad)
            if bis and bis in pfad:
                break
    return liste


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Reihenfolge eines Testlaufs nachstellen (tests/reihenfolge.py)")
    p.add_argument("ordner", type=Path)
    p.add_argument("--arbeitsprozess", help="nur diesen (z. B. gw5), sonst alle zugleich")
    p.add_argument("--bis", help="nur bis zur ersten Datei, deren Pfad diesen Text enthält (eingeschlossen)")
    p.add_argument("--nur-zeigen", action="store_true", help="die Dateien je Prozess nur ausgeben")
    args = p.parse_args(argv)
    quellen = sorted(args.ordner.glob(f"{args.arbeitsprozess}.txt" if args.arbeitsprozess else "*.txt"))
    if not quellen:
        print(f"Keine Reihenfolge in {args.ordner}")
        return 2
    plan = {q.stem: dateien(q, args.bis) for q in quellen}
    for name, liste in plan.items():
        print(f"{name}: {len(liste)} Dateien, zuletzt {liste[-1] if liste else '–'}")
    if args.nur_zeigen:
        for name, liste in plan.items():
            print(f"\n{name}:\n  " + "\n  ".join(liste))
        return 0
    aus = args.ordner / f"nachgestellt_{datetime.now():%H%M%S}"
    aus.mkdir()
    prozesse = {}
    for name, liste in plan.items():
        log = open(aus / f"{name}.log", "w", encoding="utf-8")
        # eigener Ordner je Prozess -- sonst leerte jeder nachgestellte Lauf den Ordner, aus dem er nachstellt
        befehl = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *liste]
        umgebung = {**{k: v for k, v in os.environ.items() if k not in (LAUF, AUS)}, "ERP_TEST_REIHENFOLGE": str(aus / name)}
        prozesse[name] = (subprocess.Popen(befehl, cwd=ROOT, env=umgebung, stdout=log, stderr=subprocess.STDOUT), log)
    rot = []
    for name, (proc, log) in prozesse.items():
        rc = proc.wait()
        log.close()
        ende = [z for z in (aus / f"{name}.log").read_text(encoding="utf-8", errors="replace").splitlines() if z.strip()][-1:]
        print(f"{name}: Rückgabecode {rc} -- {ende[0] if ende else ''}")
        if rc not in (0, 5):
            rot.append(name)
    print(f"Protokolle: {aus}")
    return 1 if rot else 0


if __name__ == "__main__":
    sys.exit(main())
