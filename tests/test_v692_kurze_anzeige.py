"""Version 1.9.292 (Stufe 6, R5e, Punkt 3): die Anzeige vor dem Loslassen ist bei schmalen Tagen (unter 110 px) kurz -- „Schon woanders · Rückfrage“, „Antrag
offen“, „Abwesend · Rückfrage“, „Ganze Kolonne · Rückfrage“; der Auftrag, bei dem jemand schon ist, steht dann in der Rückfrage („gleichzeitig in <Nummer> ·
<Auftrag>“, konfliktZeile()).

    kurz      zugAnzeige(z, ziel, kurz): mit kurz=true die kurze Fassung, ohne Auftrag und Namen; „Frei – <Tag>“ und „Ganze Kolonne – <Tag>“ bleiben; die Klasse
              (frei, woanders, antrag) ist dieselbe wie lang
    wann      zugZielZeigen(): kurz, wenn die Zelle schmaler als SCHMALER_TAG (110 px) ist
Im Browser: scripts/klicktest_plantafel_auftraege_ziehen.py (1440 px, Tage 120 px: lang; mit dem Finger bei 1280 px, Tage 94 px: kurz; die Rückfrage nennt den
Auftrag).
"""

import json

import pytest

from tests.test_v399_teil_updates_geld import nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
from tests.test_v681_ziehen_auftraege import DO, FR, MI, MO, _lauf

SEITE = ROOT / "app/templates/planning.html"
PERSON, GERAET, KOLONNE = {"art": "person", "slot": None}, {"art": "geraet", "slot": None}, {"art": "kolonne", "slot": None}


def _beide(z: dict, tag: str) -> list:
    """[lang, kurz] für dasselbe Ziel (ein Auftrag ohne Einsatz)"""
    ziel = {"tag": tag, "auftrag": 99}
    return _lauf(f"AUFRUFE.push(zugAnzeige({json.dumps(z)},{json.dumps(ziel)}), zugAnzeige({json.dumps(z)},{json.dumps(ziel)},true));")


@nur_mit_node
@pytest.mark.parametrize("z, tag, klasse, kurz", [
    ({**PERSON, "id": 1}, MO, "woanders", "Schon woanders · Rückfrage"),   # Tom am Mo am Wasserturm
    ({**GERAET, "id": 9}, FR, "woanders", "Schon woanders · Rückfrage"),   # der Kran am Fr an zwei Einsätzen
    ({**PERSON, "id": 4}, FR, "woanders", "Abwesend · Rückfrage"),
    ({**PERSON, "id": 3}, DO, "antrag", "Antrag offen"),
    ({**KOLONNE, "id": 5}, FR, "woanders", "Ganze Kolonne · Rückfrage"),
])
def test_kurze_fassung(z, tag, klasse, kurz):
    lang, k = _beide(z, tag)
    assert k == {"klasse": klasse, "text": kurz}
    assert lang["klasse"] == klasse and lang["text"] != kurz  # lang mit Auftrag bzw. Namen wie bis 1.9.291


@nur_mit_node
def test_lange_fassung_wie_bisher():
    lang, _ = _beide({**PERSON, "id": 1}, MO)
    assert lang["text"] == "Schon woanders: Wasserturm – Rückfrage „Trotzdem planen“"
    lang, _ = _beide({**KOLONNE, "id": 5}, FR)
    assert lang["text"] == "Ganze Kolonne – Kai, Nele schon woanders: Rückfrage für alle"


@nur_mit_node
@pytest.mark.parametrize("z, tag, text", [({**PERSON, "id": 1}, MI, "Frei – Mi 11.11."), ({**KOLONNE, "id": 5}, MO, "Ganze Kolonne – Mo 09.11.")])
def test_frei_bleibt(z, tag, text):
    lang, kurz = _beide(z, tag)
    assert lang == kurz == {"klasse": "frei", "text": text}


def test_kurz_unter_110_px():
    seite = SEITE.read_text(encoding="utf-8")
    assert "const SCHMALER_TAG=110;" in seite and "function zugAnzeige(z,ziel,kurz=false){" in seite
    assert "const a=zugAnzeige(azug,ziel,ziel.td.getBoundingClientRect().width<SCHMALER_TAG);" in seite


def test_rueckfrage_nennt_den_auftrag():
    # wer wo schon ist, nennt die Rückfrage je Warnung: „gleichzeitig in <Nummer> · <Auftrag>“ (Person bzw. Gerät doppelt bringen other_project mit)
    seite = SEITE.read_text(encoding="utf-8")
    assert "${c.other_project?` · gleichzeitig in ${esc(c.other_project)} · ${esc(c.other_project_name)}`:''}" in seite
