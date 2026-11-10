"""Version 1.9.295 (Geräte-Runde, Vorweg V4): in schmalen Chips (ab 2 Wochen) hießen beide Pritschen „HS“. Endet der Kurzname eines Geräts (ohne Kurzname: sein
Name) auf eine Zahl, zeigt der schmale Chip die Zahl („HS-DK 202“ -> „202“), sonst wie bisher die ersten zwei Zeichen; Personen weiter zwei Zeichen; mit
1 Woche unverändert der volle Name. Der volle Name steht im title.
Gemessen in scripts/klicktest_plantafel_auftraege.py (1440 px, 2 Wochen: „202“, „204“, „Kr“).
"""

import pytest

from tests.test_v399_teil_updates_geld import nur_mit_node
from tests.test_v680_ansicht_auftraege import _lauf


@nur_mit_node
@pytest.mark.parametrize("name, art, tage, erwartet", [
    ("HS-DK 202", "geraet", 14, "202"), ("Pritsche HS-DK 204", "geraet", 21, "204"), ("LKW 7", "geraet", 28, "7"), ("Hebebühne 12 ", "geraet", 14, "12"),
    ("Kran", "geraet", 14, "Kr"), ("A1-Bagger", "geraet", 14, "A1"),   # ohne Zahl am Ende: zwei Zeichen wie bisher
    ("Tom", "person", 14, "To"), ("Team 2", "kolonne", 14, "Te"), ("Ole 2", "person", 14, "Ol"),  # nur Geräte
    ("HS-DK 202", "geraet", 7, "HS-DK 202"), ("Tom", "person", 7, "Tom"),  # mit 1 Woche der volle Name
])
def test_schmaler_chip(name, art, tage, erwartet):
    assert _lauf(f"AUFRUFE.push(chipName({name!r},{art!r}));", tage=tage) == [erwartet]


@nur_mit_node
def test_chip_mit_der_zahl_und_dem_namen_im_title():
    [html] = _lauf("AUFRUFE.push(chipHtml({art:'geraet',id:7,name:'HS-DK 202',titel:'Pritsche HS-DK 202',slot:3,tag:'2026-11-09'}));", tage=14)
    assert '<span class="chip-text">202</span>' in html and 'title="Pritsche HS-DK 202"' in html
