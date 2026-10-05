"""Version 1.8.55 -- Regel 24 (CLAUDE.md): eine Gegenprobe bleibt nie im Code.

Eine Gegenprobe hebelt einen Schutz in app/ absichtlich aus, um zu zeigen, dass sein Test dann rot wird. Jede Änderung
dafür trägt den Marker GEGENPROBE (als Kommentar in der geänderten Zeile oder direkt darüber). Dieser Dauertest schlägt
an, sobald der Marker irgendwo unter app/ steht -- eine vergessene Gegenprobe fällt im nächsten vollen Lauf auf, nicht
erst auf dem Server. Anlass: in 1.8.54 lief eine Migrationsprobe, während eine Gegenprobe app/defects.py ausgehebelt hatte
(docs/archiv/abnahme-und-gewaehrleistung.md, "Verifikation 1.8.54")."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "GEGENPROBE"


def marker_funde(root: Path) -> list[str]:
    """Jede Datei unter root (alle Arten, auch Vorlagen und Skripte) mit Zeilennummer, deren Text den Marker enthält."""
    funde = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # Bilder, Schriften
        for nummer, zeile in enumerate(text.splitlines(), start=1):
            if MARKER in zeile:
                funde.append(f"{path.relative_to(ROOT).as_posix()}:{nummer}: {zeile.strip()[:120]}")
    return funde


def test_no_counter_check_left_in_app():
    funde = marker_funde(ROOT / "app")
    assert not funde, "Gegenprobe noch im Code (Regel 24) -- Datei byte-genau zurücksetzen:\n" + "\n".join(funde)


def test_marker_search_finds_a_marked_line(tmp_path, monkeypatch):
    """Die Suche selbst: eine markierte Zeile in einer Python-Datei und in einer Vorlage wird gefunden, Binärdateien
    stören nicht."""
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    (tmp_path / "app" / "templates").mkdir(parents=True)
    (tmp_path / "app" / "x.py").write_text(f"a = 1\nif False:  # {MARKER}\n    pass\n", encoding="utf-8")
    (tmp_path / "app" / "templates" / "s.html").write_text(f"<script>/* {MARKER} */</script>\n", encoding="utf-8")
    (tmp_path / "app" / "bild.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00")
    assert marker_funde(tmp_path / "app") == [f"app/templates/s.html:1: <script>/* {MARKER} */</script>",
                                              f"app/x.py:2: if False:  # {MARKER}"]
