"""Version 1.8.118 -- der Outlook-Hinweis erscheint nur, wenn Zugangsdaten fehlen (Vorgabe vom 16.10.2026, Punkt 4).

Bis 1.8.117 stand unter Einstellungen -> Outlook-Kalender immer "noch keine vollständigen Microsoft-365-Zugangsdaten": settings.html hatte
keine CSS-Regel für die Klasse "hidden", mit der loadOutlookSyncSettings() ihn ausblendet (Nebenbefund 1.8.112 Nr. 2). Jede Seite hat ihr
eigenes <style> -- eine Vorlage, die "hidden" setzt, braucht die Regel selbst. Dazu liest das Speichern der Microsoft-365-Zugangsdaten
den Hinweis neu. Im Browser: scripts/klicktest_outlook_hinweis.py."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests import vorlagen_js

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"

NUTZT = (re.compile(r"""classList\.(?:toggle|add|remove)\(\s*['"]hidden['"]"""), re.compile(r"""class=["'][^"']*\bhidden\b"""),
         re.compile(r"""className\s*[+]?=\s*[^;]*\bhidden\b"""))
REGEL = re.compile(r"\.hidden\s*\{[^}]*display\s*:\s*none")


def nutzt_hidden(text: str) -> bool:
    return any(m.search(text) for m in NUTZT)


def _hidden_vorlagen() -> tuple[list[str], list[str]]:
    """(Vorlagen, die die Klasse "hidden" setzen, davon ohne Regel .hidden{display:none}). Seit 1.8.124 (Stufe 0b): jede Vorlage, auch
    in Unterordnern; die Regel zählt, wo die Vorlage gezeichnet wird -- in ihrer zusammengesetzten Seite (auch im Basis-Template oder
    einer eingebundenen Teilvorlage) oder, für eine Teilvorlage, ein Basis-Template oder eine Makro-Datei, in jeder Seite, die sie nutzt."""
    alle = vorlagen_js.alle_vorlagen(TEMPLATES)
    gesehen = [name for name in alle if nutzt_hidden((TEMPLATES / name).read_text(encoding="utf-8"))]
    seiten = {seite: vorlagen_js.zusammensetzen(seite, wurzel=TEMPLATES) for seite in vorlagen_js.seiten(TEMPLATES)}

    def mit_regel(name: str) -> bool:
        if REGEL.search(vorlagen_js.zusammensetzen(name, wurzel=TEMPLATES)[0]):
            return True
        nutzer = [s for s, (_, herkunft) in seiten.items() if s != name and name in {d for _, _, d, _ in herkunft}]
        return bool(nutzer) and all(REGEL.search(seiten[s][0]) for s in nutzer)

    return gesehen, [name for name in gesehen if not mit_regel(name)]


def test_jede_vorlage_mit_der_klasse_hidden_blendet_sie_aus():
    gesehen, ohne = _hidden_vorlagen()
    assert "settings.html" in gesehen and len(gesehen) >= 15  # der Scanner sieht die Vorlagen
    assert ohne == [], f"Klasse 'hidden' ohne Regel .hidden{{display:none}}: {ohne}"


@pytest.mark.parametrize("text, erwartet", [
    ("el.classList.toggle('hidden', x)", True), ('<div class="hint hidden">', True), ("el.className = 'card hidden'", True),
    ('<input type="hidden">', False), ("overflow:hidden", False), ("el.hidden = true", False),
])
def test_der_scanner(text, erwartet):
    assert nutzt_hidden(text) is erwartet


def test_der_hinweis_haengt_an_den_zugangsdaten_und_wird_nach_dem_speichern_neu_gelesen():
    quelle = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert re.search(r'id="outlookGraphMissingHint" class="hint hidden"', quelle)
    assert "classList.toggle('hidden', !!s.graph_configured)" in quelle
    speichern = re.search(r"async function saveGraphSettings\(\)\{.*?\n\}", quelle, flags=re.S).group(0)
    assert "neuLaden: async () => { await loadEmailSettings(); await loadOutlookSyncSettings(); }" in speichern
