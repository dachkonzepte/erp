"""Version 1.9.228 (Lohn L1b, Punkt 5): scripts/vorprobe_time4.py -- Time-4-Buchungen durch den echten Nachtragsweg in eine Wegwerf-Datenbank,
Lohndatei erzeugen, mit der Time-4-Datei vergleichen (scripts/pruefe_lohndatei.py).

Kleinstdateien, erfunden (Dezember 2026, Tarif 7,50 h). Das Skript läuft als eigener Prozess: es setzt DATABASE_URL selbst auf eine SQLite-Datei
im Temp-Ordner und löscht sie danach.
"""

import os
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
KOPF = "personalnummer;datum;art;von;bis;stunden"


def _lauf(tmp_path, buchungen, time4, *args):
    (tmp_path / "b.csv").write_bytes(("\r\n".join([KOPF, *buchungen]) + "\r\n").encode("ascii"))
    (tmp_path / "t4.txt").write_bytes(("\r\n".join(["1234567;12345;12/2026", *time4]) + "\r\n").encode("ascii"))
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "ERP_DATA_DIR")}
    r = subprocess.run([sys.executable, str(WURZEL / "scripts" / "vorprobe_time4.py"), str(tmp_path / "b.csv"), str(tmp_path / "t4.txt"),
                        "--ausgabe", str(tmp_path / "erp.txt"), *args], capture_output=True, text=True, encoding="utf-8",
                       env={**env, "PYTHONIOENCODING": "utf-8"}, timeout=300, cwd=tmp_path)
    return r.returncode, r.stdout + r.stderr, (tmp_path / "erp.txt").read_bytes() if (tmp_path / "erp.txt").exists() else b""


def test_nachtragsweg_pause_samstag_azubi_at(tmp_path):
    """Di 01.12. 07:00–15:45 mit fester Pause in Time 4 (8,25) -- das ERP zieht 30 min ab, gleich; Sa 05.12. 07:00–15:30 ohne Pause in Time 4 (8,50),
    das ERP 8,00 (erklärt); Urlaub am 02.12.; Azubi 00291 mit 9:00 h -> Mehrarbeit; AT nicht übernommen, genannt."""
    buchungen = ["00101;2026-12-01;V;07:00;15:45;8,75", "00101;2026-12-01;P;12:00;12:30;0,50", "00101;2026-12-02;U;;;7,50",
                 "00101;2026-12-05;V;07:00;15:30;8,50", "00291;2026-12-01;V;07:00;16:45;9,75", "00291;2026-12-03;AT;08:00;10:00;2,00"]
    time4 = ["00101;1;1;1000;8,25;;;;;;", "00101;2;U;8000;7,50;;;;;;", "00101;5;1;1000;8,50;;;;;;", "00101;25;F;1012;7,50;;;;;;"]
    rc, out, erp = _lauf(tmp_path, buchungen, time4, "--azubis", "00291")
    assert rc == 0, out
    zeilen = erp.decode("ascii").split("\r\n")
    assert zeilen[0] == "1234567;12345;12/2026"
    assert ["00101;1;1;1000;8,25;;;;;;", "00101;2;U;8000;7,50;;;;;;", "00101;5;1;1000;8,00;;;;;;"] == [z for z in zeilen if z.startswith("00101;") and
                                                                                                      z.split(";")[1] in ("1", "2", "5")]
    assert "00291;1;1;1000;7,50;;;;;;" in zeilen and "00291;1;AA;1900;1,50;;;;;;" in zeilen
    assert "Nicht übernommen" in out and "00291 03.12. AT 2,00 h" in out
    assert "Pause: Time 4 ohne Pause" in out and "0 zu klären" in out


def test_teilzeit_und_zu_klaeren(tmp_path):
    """Teilzeit Di–Do 3,00 h: Urlaub am Dienstag mit 3,00; eine Stunde mehr in Time 4 bleibt zu klären (Rückgabe 1)."""
    buchungen = ["00106;2026-12-01;U;;;3,00", "00106;2026-12-02;V;07:00;10:00;3,00"]
    time4 = ["00106;1;U;8000;3,00;;;;;;", "00106;2;1;1000;4,00;;;;;;"]
    rc, out, erp = _lauf(tmp_path, buchungen, time4, "--teilzeit", "00106=0,3,3,3,0")
    assert rc == 1 and "00106;1;U;8000;3,00;;;;;;" in erp.decode("ascii")
    assert "zu klären  00106  02.12.  1: ERP 3,00, Time 4 4,00" in out


def test_echte_datenbank_unberuehrt(tmp_path):
    """Regel 16: das Skript legt seine Datenbank im Temp-Ordner an -- die Datei der Entwicklung ändert sich nicht."""
    echt = WURZEL / "dachkonzepte_erp.db"
    vorher = echt.stat().st_mtime_ns if echt.exists() else None
    _lauf(tmp_path, ["00101;2026-12-01;V;07:00;15:00;8,00"], ["00101;1;1;1000;7,50;;;;;;"])
    assert (echt.stat().st_mtime_ns if echt.exists() else None) == vorher
