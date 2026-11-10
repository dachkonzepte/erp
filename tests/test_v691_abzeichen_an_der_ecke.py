"""Version 1.9.291 (Stufe 6, R5e, Punkt 2): ⚠ bzw. der Punkt eines Hinweises sitzt als kleines Abzeichen an der oberen rechten Ecke des Chips und nimmt dem
Namen keinen Platz -- bis 1.9.290 stand ⚠ hinter und der Punkt vor dem Namen im Chip (bei 1280 px mit dem Finger „HS-D… ⚠“, die Pritschen nicht zu unterscheiden).

    Markup     das Abzeichen steht hinter dem Namen (span.abzeichen, mit Warnung zusätzlich .warn), nie ein Zeichen im Fluss des Chips; Warnung vor Hinweis
    Lage       der Chip ist position:relative, das Abzeichen absolut 12 px groß, 5 px über die Ecke hinaus (-6 px vom Innenrand, der Rand ist 1 px)
Gemessen in scripts/klicktest_plantafel_auftraege.py und scripts/klicktest_plantafel_auftraege_ziehen.py (kein Chip gekürzt bei 1440 und 1280 px, Maus und
Finger, auch mit ⚠; das Abzeichen außerhalb des Namens, an der Ecke).
"""

import re

from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
from tests.test_v680_ansicht_auftraege import _lauf
from tests.test_v399_teil_updates_geld import nur_mit_node

SEITE = ROOT / "app/templates/planning.html"
CHIP = "{art:'geraet',id:7,name:'HS-DK 202',titel:'Pritsche HS-DK 202',slot:3,tag:'2026-11-09'"
WARN = '<span class="abzeichen warn" aria-hidden="true"><svg class="warnzeichen"></svg></span>'
HINWEIS = '<span class="abzeichen" aria-hidden="true"><span class="hinweis-punkt"></span></span>'


def _chip(zusatz: str) -> str:
    [html] = _lauf(f"AUFRUFE.push(chipHtml({CHIP}{zusatz}}}));")
    return html


@nur_mit_node
def test_warnung_als_abzeichen_hinter_dem_namen():
    html = _chip(",warn:true")
    assert html.startswith('<span class="chip warn" ') and html.endswith('<span class="chip-text">HS-DK 202</span>' + WARN + "</span>")
    assert html.count("warnzeichen") == 1  # kein ⚠ mehr im Fluss des Chips


@nur_mit_node
def test_hinweis_als_abzeichen_hinter_dem_namen():
    html = _chip(",hint:true")
    assert html.startswith('<span class="chip" ') and html.endswith('<span class="chip-text">HS-DK 202</span>' + HINWEIS + "</span>")
    assert html.count("hinweis-punkt") == 1  # kein Punkt mehr vor dem Namen


@nur_mit_node
def test_warnung_vor_hinweis_und_ohne_beides_kein_abzeichen():
    beides, keins = _chip(",warn:true,hint:true"), _chip("")
    assert WARN in beides and "hinweis-punkt" not in beides
    assert "abzeichen" not in keins and keins.endswith('<span class="chip-text">HS-DK 202</span></span>')


def test_lage_an_der_ecke():
    seite = SEITE.read_text(encoding="utf-8")
    chip = next(z for z in seite.splitlines() if z.startswith(".chip{display:inline-flex;"))
    assert chip.endswith("white-space:nowrap;position:relative}")
    regel = re.search(r"^\.chip \.abzeichen\{[^}]*\}", seite, flags=re.M).group(0)
    for teil in ("position:absolute", "top:-6px", "right:-6px", "z-index:1", "width:12px", "height:12px", "box-sizing:border-box", "border-radius:50%"):
        assert teil in regel, teil
    assert ".chip .abzeichen.warn{border-color:var(--ds-fehler);background:var(--ds-fehler-hell)}" in seite
    assert ".chip .abzeichen .warnzeichen{width:8px;height:8px}" in seite and ".chip .abzeichen .hinweis-punkt{width:6px;height:6px}" in seite
