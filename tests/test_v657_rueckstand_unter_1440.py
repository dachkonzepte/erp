"""Version 1.9.257 (Stufe 6, R4b, Punkt 8): unter 1440 px startet „Nicht eingeplant“ eingeklappt, solange im Browser nichts anderes gemerkt ist.

    Start        rueckstandStartZu(Breite): gemerkt „zu“ -> zu; gemerkt „offen“ -> offen (jede Breite); nichts gemerkt -> zu unter 1440 px, sonst offen;
                 ohne Zugriff auf den Speicher wie „nichts gemerkt“
    Merken       nur der Knopf merkt (rueckstandZeigen(offen) wie seit 1.9.247), der Start nicht (rueckstandZeigen(false, false))
Im Browser: scripts/klicktest_plantafel_tafel.py (1280 px eingeklappt ohne Merken, 1440 px offen, gemerkt „offen“ bei 1280 px offen).
"""

import json
from pathlib import Path

import pytest

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node

ROOT = Path(__file__).resolve().parent.parent


def _start(gemerkt, breite, kaputt=False):
    speicher = ("var localStorage = {getItem() { throw new Error('gesperrt'); }};" if kaputt
                else f"var localStorage = {{getItem(k) {{ return k === 'plantafel_rueckstand' ? {json.dumps(gemerkt)} : null; }}}};")
    [erg] = im_browser("planning.html", ["rueckstandStartZu"], speicher, f"AUFRUFE.push(rueckstandStartZu({breite}));")
    return erg


@nur_mit_node
@pytest.mark.parametrize("gemerkt, breite, zu", [
    (None, 1280, True), (None, 1439, True), (None, 1440, False), (None, 1920, False),
    ("offen", 1280, False), ("zu", 1280, True), ("zu", 1920, True), ("offen", 1920, False),
])
def test_start(gemerkt, breite, zu):
    assert _start(gemerkt, breite) is zu


@nur_mit_node
def test_ohne_speicher_wie_nichts_gemerkt():
    assert _start(None, 1280, kaputt=True) is True and _start(None, 1440, kaputt=True) is False


def test_nur_der_knopf_merkt():
    html = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "function rueckstandZeigen(offen,merken=true){" in html
    assert "if(merken)try{localStorage.setItem('plantafel_rueckstand',offen?'offen':'zu')}catch(e){}" in html
    assert "if(rueckstandStartZu(window.innerWidth))rueckstandZeigen(false,false);" in html
    assert "addEventListener('click',()=>rueckstandZeigen(document.getElementById('tafelLayout').classList.contains('rk-zu')))" in html
