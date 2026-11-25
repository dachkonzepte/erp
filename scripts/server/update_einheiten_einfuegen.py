"""Einmal auf dem Server (Server-Schritt S11, seit 1.11.26): fügt in update.sh vor der Zeile FERTIG den Vergleich der Einheiten ein
(scripts/pruefe_einheiten.py) -- nur, wenn diese Zeile genau einmal dasteht. Sonst ändert es nichts: Rückgabe 1 mit dem Grund. Steht der Vergleich schon
drin, ändert es ebenfalls nichts (Rückgabe 0). Nur Standardbibliothek (python3 des Servers); die Sicherung macht der Schritt vorher (cp -a). Datei und
Rechte bleiben, nur der Inhalt wird ersetzt.

    python3 scripts/server/update_einheiten_einfuegen.py /home/tobias/update.sh
"""

from __future__ import annotations

import sys
from pathlib import Path

ANKER = b'echo "=== FERTIG: $ALT -> $NEU, Datenbank $AKTUELL, ERP und Kundenportal laufen ==="\n'
MARKE = b'echo "=== Einheiten ==="\n'
EINSCHUB = (MARKE
            + b'PHASE="Einheiten"\n'
            + b'/home/tobias/erp/.venv/bin/python /home/tobias/erp/scripts/pruefe_einheiten.py'
            + b' || echo "!!! Einheiten weichen vom Repo ab (oben) -- update.sh installiert sie nicht."\n'
            + b"\n")


def einfuegen(inhalt: bytes) -> tuple[bytes | None, str]:
    """Der neue Inhalt und eine Meldung; None, wenn nichts zu ändern ist oder nicht geändert werden darf."""
    if b"\r\n" in inhalt:
        return None, "Abbruch: update.sh hat Windows-Zeilenenden -- nichts geändert."
    if MARKE in inhalt:
        return None, "Der Vergleich der Einheiten steht schon in update.sh -- nichts geändert."
    anzahl = inhalt.count(ANKER)
    if anzahl != 1:
        return None, f"Abbruch: die Zeile FERTIG steht {anzahl}-mal in update.sh (erwartet genau einmal) -- nichts geändert."
    return inhalt.replace(ANKER, EINSCHUB + ANKER), "update.sh geändert: der Vergleich der Einheiten steht vor der Zeile FERTIG."


def main(argv=None, *, ausgabe=print) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        ausgabe("Aufruf: python3 scripts/server/update_einheiten_einfuegen.py /home/tobias/update.sh")
        return 2
    datei = Path(argv[0])
    if not datei.is_file():
        ausgabe(f"Abbruch: {datei} gibt es nicht -- nichts geändert.")
        return 1
    inhalt = datei.read_bytes()
    neu, meldung = einfuegen(inhalt)
    ausgabe(meldung)
    if neu is None:
        return 0 if MARKE in inhalt else 1
    with open(datei, "r+b") as f:  # dieselbe Datei (Rechte, Besitzer), nur der Inhalt
        f.write(neu)
        f.truncate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
