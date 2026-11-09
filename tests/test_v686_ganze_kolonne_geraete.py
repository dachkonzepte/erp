"""Version 1.9.286 (Stufe 6, R5d, Punkt 4): „Ganze Kolonne“ nennt vor dem Loslassen auch Geräte, die schon woanders sind (bis 1.9.285 nur Personen).

    Anzeige   „Ganze Kolonne – <Vornamen>, <Kurznamen der Geräte> schon woanders: Rückfrage für alle“; erst die Personen, dann die Geräte; der Kurzname wie am
              Chip (geraetName()); ist niemand und kein Gerät woanders: „Ganze Kolonne – <Tag>“
Im Browser prüft das scripts/klicktest_plantafel_auftraege_ziehen.py (Kolonne Süd auf Kaminverwahrung Mo: „Kai, Nele, HS-DK 204 schon woanders“).
"""

import json

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v680_ansicht_auftraege import BOARD, FUNKTIONEN

MO, FR = "2026-11-09", "2026-11-13"
TAFEL = {**BOARD, "teams": [
    {"id": 5, "name": "Kolonne Süd", "employees": [{"id": 2, "name": "Kai Kolb", "vorname": "Kai"}], "resources": [{"id": 7, "name": "Pritsche HS-DK 202"}]},
    {"id": 6, "name": "Kolonne Kran", "employees": [], "resources": [{"id": 9, "name": "Liebherr"}]},
    {"id": 8, "name": "Kolonne West", "employees": [{"id": 8, "name": "Ute Ufer", "vorname": "Ute"}], "resources": [{"id": 7, "name": "Pritsche HS-DK 202"}]}]}


def _anzeige(team: int, tag: str) -> dict:
    vorbereitung = (f"var board = {json.dumps(TAFEL)}; const WOCHENTAGE=['So','Mo','Di','Mi','Do','Fr','Sa'];"
                    "document.getElementById('rangeDays').value = '7';"
                    "function localDateIso(d){const p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`}")
    [a] = im_browser("planning.html", FUNKTIONEN + ["tagText", "schonWoanders", "zugAnzeige"], vorbereitung,
                     f"AUFRUFE.push(zugAnzeige({{art:'kolonne',id:{team},slot:null}},{{tag:'{tag}',auftrag:99}}));")
    return a


@nur_mit_node
def test_personen_und_geraete():
    # Kai steht am Fr am Wasserturm und an der Kranvermietung, die Pritsche 202 am Fr am Wasserturm -- erst die Personen, dann die Geräte mit Kurzname
    assert _anzeige(5, FR) == {"klasse": "woanders", "text": "Ganze Kolonne – Kai, HS-DK 202 schon woanders: Rückfrage für alle"}


@nur_mit_node
def test_nur_ein_geraet():
    assert _anzeige(6, FR) == {"klasse": "woanders", "text": "Ganze Kolonne – Liebherr schon woanders: Rückfrage für alle"}  # ohne Kurzname der Name


@nur_mit_node
def test_frei():
    # Mo: die Pritsche 202 steht am Wasserturm -- Kolonne West (Ute frei) also woanders; Kolonne Kran am Mo frei
    assert _anzeige(8, MO) == {"klasse": "woanders", "text": "Ganze Kolonne – HS-DK 202 schon woanders: Rückfrage für alle"}
    assert _anzeige(6, MO) == {"klasse": "frei", "text": "Ganze Kolonne – Mo 09.11."}
