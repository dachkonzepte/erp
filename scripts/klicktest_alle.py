"""Alle Klicktests nacheinander (seit 1.8.75): scripts/klicktest_*.py, je einer in einem eigenen Prozess mit eigenem Arbeitsordner,
danach eine Übersicht mit Ergebnis, Prüfungen und Laufzeit je Test und gesamt.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_alle.py [--nur TEIL ...] [--ab NAME] [--ausgabe ORDNER] [--zeitlimit SEK]

    --nur TEIL      nur Klicktests, deren Name TEIL enthält (mehrfach möglich)
    --ab NAME       erst ab diesem Klicktest (alphabetisch), z. B. nach einem Abbruch
    --ausgabe       Ordner für Protokolle, Screenshots und die Übersicht (Vorgabe: neuer Temp-Ordner); je Klicktest ein
                    Unterordner als dessen --arbeitsordner, dazu <name>.log mit der vollen Ausgabe
    --zeitlimit     Sekunden je Klicktest (Vorgabe 900); danach wird der Klicktest samt seinen Kindprozessen (ERP-Instanz,
                    Chrome) über die eigene PID beendet (taskkill /T, Regel 12) und als "Zeitlimit" geführt

Rückgabecode 0, wenn alle wie erwartet liefen. Jeder Klicktest startet seine eigene Wegwerf-Instanz (Regel 16) und beendet
seine Prozesse selbst; dieses Skript beendet nur den eigenen Kindprozess und dessen Baum. Kein Teil der pytest-Suite."""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent


def _dauer(sekunden: float) -> str:
    m, s = divmod(int(round(sekunden)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _baum_beenden(pid: int) -> None:
    """Nur der eigene Kindprozess und dessen Kinder (Regel 12) -- nie über einen Prozessnamen."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def klicktests(nur: list[str], ab: str | None) -> list[Path]:
    alle = sorted(p for p in SCRIPTS.glob("klicktest_*.py") if p.name != Path(__file__).name)
    if nur:
        alle = [p for p in alle if any(t in p.stem for t in nur)]
    if ab:
        alle = [p for p in alle if p.stem >= ab.removesuffix(".py")]
    return alle


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Alle Klicktests nacheinander")
    parser.add_argument("--nur", action="append", default=[])
    parser.add_argument("--ab")
    parser.add_argument("--ausgabe", type=Path)
    parser.add_argument("--zeitlimit", type=int, default=900)
    args = parser.parse_args()

    ausgabe = (args.ausgabe or Path(tempfile.mkdtemp(prefix="erp-klicktests-"))).resolve()
    ausgabe.mkdir(parents=True, exist_ok=True)
    liste = klicktests(args.nur, args.ab)
    print(f"{len(liste)} Klicktests, Ausgabe {ausgabe}", flush=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    zeilen, gesamt_start = [], time.monotonic()
    for nr, skript in enumerate(liste, start=1):
        name = skript.stem
        log = ausgabe / f"{name}.log"
        start = time.monotonic()
        with open(log, "wb") as out:
            proc = subprocess.Popen([sys.executable, str(skript), "--arbeitsordner", str(ausgabe / name)], cwd=ROOT, env=env,
                                    stdout=out, stderr=subprocess.STDOUT)
            try:
                code = proc.wait(timeout=args.zeitlimit)
            except subprocess.TimeoutExpired:
                _baum_beenden(proc.pid)
                proc.wait(timeout=30)
                code = None
        dauer = time.monotonic() - start
        text = log.read_text(encoding="utf-8", errors="replace")
        treffer = re.findall(r"(\d+) von (\d+) Prüfungen wie erwartet", text)
        pruefungen = f"{treffer[-1][0]}/{treffer[-1][1]}" if treffer else "-"
        ergebnis = "Zeitlimit" if code is None else ("OK" if code == 0 else f"ROT ({code})")
        zeilen.append((name, ergebnis, pruefungen, dauer))
        print(f"[{nr:>2}/{len(liste)}] {ergebnis:<9} {pruefungen:>7}  {_dauer(dauer):>7}  {name}", flush=True)
    gesamt = time.monotonic() - gesamt_start
    ok = sum(1 for z in zeilen if z[1] == "OK")
    rot = [z for z in zeilen if z[1] != "OK"]
    zusammenfassung = [f"{ok} von {len(zeilen)} Klicktests wie erwartet, Laufzeit gesamt {_dauer(gesamt)}"]
    zusammenfassung += [f"  {z[1]:<9} {z[2]:>7}  {_dauer(z[3]):>7}  {z[0]}  (Protokoll: {ausgabe / (z[0] + '.log')})" for z in rot]
    (ausgabe / "zusammenfassung.txt").write_text(
        "\n".join(zusammenfassung + ["", *(f"{z[1]:<9} {z[2]:>7}  {_dauer(z[3]):>7}  {z[0]}" for z in zeilen)]) + "\n",
        encoding="utf-8")
    print("\n".join(zusammenfassung), flush=True)
    return 0 if not rot else 1


if __name__ == "__main__":
    sys.exit(main())
