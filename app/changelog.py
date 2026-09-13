"""Liest und parst CHANGELOG.md für die Anzeige innerhalb des ERP selbst
(seit 1.0.52, Roadmap-Punkt "In-App Changelog/Logfile").

Bewusst kein allgemeiner Markdown-Parser und keine neue Abhängigkeit
(requirements.txt hat aktuell kein Markdown-Paket) -- die Datei hat ein
festes, selbst kontrolliertes Format (## Version – Titel, dann ein
Absatz), das mit einer einfachen, gezielten Aufteilung zuverlässig
auswertbar ist. Reicht auch für inline `code` und **fett**, mehr wird in
den Einträgen bisher nicht verwendet.
"""

import re
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def _inline_format(text: str) -> str:
    """`code` -> <code>, **fett** -> <b> -- in dieser Reihenfolge, damit
    Sternchen innerhalb von code-Spans nicht versehentlich als fett
    interpretiert werden."""
    from html import escape

    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def read_changelog_entries() -> list[dict]:
    """Liefert [{"version": "1.0.51", "title": "...", "html": "..."}, ...]
    in der Reihenfolge, wie sie in der Datei stehen (neueste zuerst, siehe
    Kopfzeile in CHANGELOG.md selbst)."""
    if not CHANGELOG_PATH.is_file():
        return []
    content = CHANGELOG_PATH.read_text(encoding="utf-8")
    sections = content.split("\n## ")
    entries = []
    for section in sections[1:]:  # erstes Element ist die Kopfzeile vor dem ersten "## "
        lines = section.split("\n", 1)
        heading = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        m = re.match(r"(\d+\.\d+\.\d+)\s*–\s*(.+)", heading)
        if not m:
            continue
        version, title = m.group(1), m.group(2)
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        html = "".join(f"<p>{_inline_format(p)}</p>" for p in paragraphs)
        entries.append({"version": version, "title": title, "html": html})
    return entries
