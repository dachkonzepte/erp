"""Version 1.9.244 (Stufe 6, R4, Punkt 0b): keine echte Personalnummer in einer versionierten Datei.

    Quelle     die echten Nummern stehen nur in bildgrundlage/lohn_echt/ (nicht in Git, nur auf dem Rechner des Betreibers): die erste Spalte der Dateien
               aus Time 4 und des ERP, dazu die fünfstelligen Zahlen im LIESMICH -- ohne den Platzhalter des Kopfs (1234567;12345). Fehlt der Ordner
               (Server, frischer Checkout) oder git, wird der Wächter übersprungen.
    Prüfung    jede von git verwaltete Textdatei (git grep über den Baum der Arbeitskopie); ein Treffer nennt Datei, Zeile und eine Kennung (P01 …), nie
               die Nummer selbst -- die Ausgabe eines roten Laufs darf sie nicht weitertragen.
    Ersatz     seit 1.9.244 stehen in Tests und Doku erfundene Nummern (0009x, 0019x, 0029x -- der Kreis des Lohnbüros bleibt).
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parent.parent
LOHN_ECHT = PROJEKT / "bildgrundlage" / "lohn_echt"
PLATZHALTER = {"12345", "1234567"}
GIT_WINDOWS = Path(r"C:\Program Files\Git\cmd\git.exe")


def echte_nummern(ordner: Path) -> list[str]:
    nummern = set()
    for datei in sorted(ordner.glob("*.txt")) + sorted(ordner.glob("*.csv")):
        text = datei.read_text(encoding="utf-8", errors="replace")
        if datei.name.upper().startswith("LIESMICH"):
            nummern |= set(re.findall(r"(?<!\d)\d{5}(?!\d)", text))
            continue
        for zeile in text.splitlines():
            feld = zeile.split(";")[0].strip()
            if re.fullmatch(r"\d{5}", feld):
                nummern.add(feld)
    return sorted(nummern - PLATZHALTER)


def fundstellen(zeilen: list[str], nummern: list[str]) -> list[str]:
    """Aus Zeilen „Datei:Zeile:Text“ (git grep -n) die Fundstellen -- maskiert: „Datei:Zeile (P03)“, nie die Nummer."""
    kennung = {n: f"P{i + 1:02d}" for i, n in enumerate(nummern)}
    muster = re.compile(r"(?<!\d)(" + "|".join(map(re.escape, nummern)) + r")(?!\d)")
    aus = []
    for z in zeilen:
        datei, nr, text = z.split(":", 2)
        gefunden = muster.findall(text)
        if gefunden:
            aus.append(f"{datei}:{nr} ({', '.join(kennung[g] for g in dict.fromkeys(gefunden))})")
    return aus


def _git() -> str | None:
    return shutil.which("git") or (str(GIT_WINDOWS) if GIT_WINDOWS.exists() else None)


def test_keine_echte_personalnummer_in_einer_versionierten_datei():
    nummern = echte_nummern(LOHN_ECHT) if LOHN_ECHT.is_dir() else []
    git = _git()
    if not nummern or git is None:
        pytest.skip("bildgrundlage/lohn_echt oder git fehlt -- nur auf dem Rechner des Betreibers")
    r = subprocess.run([git, "-c", "core.quotepath=off", "grep", "-n", "-I", "-E",
                        r"(^|[^0-9])(" + "|".join(nummern) + r")([^0-9]|$)", "--", "."],
                       cwd=PROJEKT, capture_output=True)
    assert r.returncode in (0, 1), r.stderr.decode("utf-8", "replace")[:300]
    treffer = fundstellen(r.stdout.decode("utf-8", "replace").splitlines(), nummern)
    assert not treffer, "echte Personalnummern (aus bildgrundlage/lohn_echt) in versionierten Dateien:\n" + "\n".join(treffer)


def test_fundstellen_nennen_nie_die_nummer():
    zeilen = ["tests/a.py:3:    person(w, \"55501\", azubi=True)", "docs/b.md:9:Zeile 55501;7;1 und 55777", "c.py:1:ohne 555010 und 0055501x"]
    treffer = fundstellen(zeilen, ["55501", "55777"])
    assert treffer == ["tests/a.py:3 (P01)", "docs/b.md:9 (P01, P02)"]  # 555010 und 0055501 sind andere Zahlen
    assert not any("55501" in t or "55777" in t for t in treffer)


def test_echte_nummern_aus_den_dateien(tmp_path):
    (tmp_path / "time4_x.txt").write_text("1234567;12345;10/2026\n55501;7;1;1000;7,50;;;;;;\n55502;;;8110;;;15,00;;;;\n", encoding="utf-8")
    (tmp_path / "buchungen_x.csv").write_text("personalnummer;datum\n55503;2026-10-01\n", encoding="utf-8")
    (tmp_path / "LIESMICH.txt").write_text("Azubis: 55504, 55505. Kopf 1234567;12345\n", encoding="utf-8")
    assert echte_nummern(tmp_path) == ["55501", "55502", "55503", "55504", "55505"]
