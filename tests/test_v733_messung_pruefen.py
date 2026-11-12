"""Version 1.9.333 (Lohn L2c-3, Punkt 0): die Messung von „Prüfen“ (scripts/messe_pruefen.py) läuft.

Das Skript baut einen Testbestand (15 gewerbliche Personen, zwölf gesendete Lohndateien) in einer Wegwerf-Datenbank und misst GET /api/zeiten/pruefen über
die echte Anmeldeschranke. Der Test prüft keine Dauer (keine feste Schranke, Testablauf) -- nur, dass das Skript läuft, den Bestand vollständig anlegt und je
Tag und Fenster eine Zeile ausgibt; so bleibt die Messung wiederholbar, wenn „Prüfen“ wächst. Ergebnis der Messung vom 12.11.2026: Archiv „Lohn L2c-3“.
"""

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]


def test_messung_laeuft():
    r = subprocess.run([sys.executable, str(WURZEL / "scripts" / "messe_pruefen.py"), "--aufrufe", "1"], cwd=str(WURZEL), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "3735 Buchungen, 180 Abwesenheiten, 12 Lohndateien" in r.stdout
    zeilen = [z for z in r.stdout.splitlines() if z.startswith("SQLite ")]
    assert [z.split()[1:4] for z in zeilen] == [["31.12.2027", "12", "Mon."], ["31.12.2027", "3", "Mon."], ["17.01.2028", "12", "Mon."],
                                                ["17.01.2028", "3", "Mon."]]
    assert [int(z.split()[4]) for z in zeilen] == [12, 3, 11, 2]  # gesendete Monate mit Änderungen im Fenster
