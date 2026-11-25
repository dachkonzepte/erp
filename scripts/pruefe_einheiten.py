"""Einheiten vergleichen (seit 1.11.26, Frage F2 aus 1.11.22): liegen die Einheiten aus scripts/server/ so in /etc/systemd/system, wie das Repo sie hat?

update.sh holt mit git pull die Einheiten des Repos, installiert sie aber nicht -- nach einer Änderung (etwa 1.11.22: gunicorn ohne Steuer-Socket) liefe der
Dienst sonst still mit der alten Fassung weiter. Dieses Skript ruft update.sh vor der Zeile FERTIG auf (Server-Schritt S11). Es vergleicht nur und meldet
jede Abweichung mit dem Befehl zum Ansehen und zum Übernehmen; es installiert nichts, startet nichts neu und schreibt nichts (Betreibervorgabe 25.11.2026).

Rückgabe 0: alle Einheiten wie im Repo. 1: mindestens eine weicht ab, fehlt oder ist nicht lesbar. Nur Standardbibliothek, keine Datenbank, keine Umgebung.
--ziel nur für Tests (auf dem Server /etc/systemd/system).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EINHEITEN = REPO / "scripts" / "server"
ZIEL = Path("/etc/systemd/system")


def einheiten(ordner: Path = EINHEITEN) -> list[Path]:
    """Jede Einheit des Repos (*.service, *.timer), nach Namen."""
    return sorted([*ordner.glob("*.service"), *ordner.glob("*.timer")], key=lambda p: p.name)


def _uebernehmen(datei: Path, ziel: Path) -> str:
    befehl = f"sudo install -m 644 -o root -g root {datei.as_posix()} {ziel.as_posix()}/ && sudo systemctl daemon-reload"
    if datei.suffix == ".service" and (datei.with_suffix(".timer")).exists():
        return befehl + f"   (läuft über {datei.stem}.timer -- kein Neustart nötig)"
    return befehl + f" && sudo systemctl restart {datei.name}"


def vergleichen(ziel: Path = ZIEL, ordner: Path = EINHEITEN) -> list[str]:
    """Die Zeilen der Meldung je abweichender, fehlender oder nicht lesbarer Einheit; leer, wenn alle wie im Repo sind."""
    zeilen: list[str] = []
    for datei in einheiten(ordner):
        installiert = ziel / datei.name
        if not installiert.exists():
            zeilen.append(f"!!! {datei.name} ist nicht installiert ({installiert.as_posix()} fehlt) -- Einrichtung in den Server-Schritten.")
            continue
        try:
            gleich = installiert.read_bytes() == datei.read_bytes()
        except OSError as fehler:
            zeilen.append(f"!!! {datei.name}: {installiert.as_posix()} nicht lesbar ({type(fehler).__name__}).")
            continue
        if not gleich:
            zeilen += [f"!!! {datei.name} weicht vom Repo ab -- installiert ist eine andere Fassung.",
                       f"    Ansehen:    diff -u {installiert.as_posix()} {datei.as_posix()}",
                       f"    Übernehmen: {_uebernehmen(datei, ziel)}"]
    return zeilen


def main(argv=None, *, ausgabe=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ziel", default=str(ZIEL), help="Ordner der installierten Einheiten (nur für Tests)")
    args = parser.parse_args(argv)
    namen = [d.name for d in einheiten()]
    zeilen = vergleichen(Path(args.ziel))
    for zeile in zeilen:
        ausgabe(zeile)
    if zeilen:
        ausgabe(f"Einheiten: {len(namen)} im Repo, mindestens eine weicht ab -- nichts installiert.")
        return 1
    ausgabe(f"Einheiten wie im Repo: {', '.join(namen)}.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
