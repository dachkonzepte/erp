"""Version 1.9.256 (Stufe 6, R4b, Punkt 6): ein vorläufiger Einsatz mit Warnung bleibt gestrichelt -- roter, gestrichelter Rand, in jeder Ansicht.

Bis 1.9.255 überschrieb `.slot.conflict` (2 px rot, durchgezogen) den gestrichelten Rand von `.slot.vorlaeufig`; „Garage Lindenweg 7“ (vorläufig, Kai doppelt)
sah aus wie ein fester Einsatz mit Warnung. Die Regel `.slot.vorlaeufig.conflict` setzt den Strich zurück -- sie wiegt drei Klassen, mehr als beide.
Im Browser messen scripts/klicktest_plantafel_tafel.py („Kolonnen“, hell und dunkel) und klicktest_plantafel_personen.py („Personen“) den Rand.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _stil():
    html = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    return html[html.index("<style>"):html.index("</style>")]


def test_vorlaeufig_mit_warnung_gestrichelt():
    stil = _stil()
    assert "  .slot.conflict{border:2px solid var(--ds-fehler)}" in stil
    assert re.search(r"^  \.slot\.vorlaeufig\.conflict\{border-style:dashed\}", stil, re.M)
    # nach der Warnung, damit sie auch bei gleichem Gewicht gälte; Farbe und Breite bleiben die der Warnung
    assert stil.index(".slot.vorlaeufig.conflict{") > stil.index(".slot.conflict{")
    assert not re.search(r"\.slot\.vorlaeufig\.conflict\{[^}]*(border-color|border-width|border:)", stil)


def test_keine_andere_regel_setzt_den_rand_der_warnung_durchgezogen():
    """Keine spätere Regel mit mindestens drei Klassen setzt bei .conflict einen durchgezogenen Rand (die Gerätezeile, Personen, Filter nutzen dieselbe Klasse)."""
    stil = _stil()
    for sel, rumpf in re.findall(r"([^{}]+)\{([^}]*)\}", stil):
        if ".conflict" in sel and "solid" in rumpf:
            assert sel.strip() == ".slot.conflict", sel
