"""Version 1.9.283 (Stufe 6, R5d, Punkt 1): in „Aufträge“ startet „Zum Einplanen“ immer offen; schmalere Tagesspalten -- bei 1280 px mit offener Liste rollt
nichts seitlich.

    Liste      beim Wechsel nach „Aufträge“ offen; zurück in den übrigen Ansichten gilt wieder der gemerkte Zustand (unter 1440 px zu, Regel 1.9.257);
               Auf- und Zuklappen in „Aufträge“ merkt nichts
    Spalten    unter 1400 px Fensterbreite die Namensspalte 200 statt 230 px, je Tag mindestens 84 statt 110 px (1 Woche; ab 2 Wochen wie bisher 56 px)
    Chips      ist eine Karte schmaler als ein Gerät mit Zeichen und Kurzname, fällt nur das Gerätezeichen weg (das Kranzeichen bleibt); Innenabstände von
               Zelle, Karte und Chip je 1 px kleiner
Gemessen im Klicktest scripts/klicktest_plantafel_auftraege.py (1280 px: 721 px Platz, Tage 94 px, kein Chip gekürzt).
"""

import json

import pytest

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

SEITE = ROOT / "app/templates/planning.html"


def _lauf(gemerkt: str | None, breite: int, ablauf: str) -> list:
    vorbereitung = (
        f"var SPEICHER = {json.dumps({'plantafel_rueckstand': gemerkt} if gemerkt else {})}; var window = globalThis; window.innerWidth = {breite};"
        "var localStorage = {getItem(k){ return k in SPEICHER ? SPEICHER[k] : null; }, setItem(k, v){ SPEICHER[k] = String(v); }};"
        "var view = 'teams', board = null, GELADEN = 0; function loadBoard(){ GELADEN++; } function renderBoard(){} function bandSchliessen(){}"
        "const ZEITRAUM_SCHLUESSEL='plantafel_zeitraum', ZEITRAUM_VORGABE={auftraege:7}, ZEITRAEUME=[7,14,21,28];"
        "document.getElementById('rangeDays').value = '14';"
        "const KLASSEN = new Set(); document.getElementById('tafelLayout').classList = {toggle(c, an){ an ? KLASSEN.add(c) : KLASSEN.delete(c); },"
        " contains(c){ return KLASSEN.has(c); }, add(c){ KLASSEN.add(c); }, remove(c){ KLASSEN.delete(c); }};"
        "document.getElementById('rkKnopf').querySelector = () => ({setAttribute(){}});"
        "const zu = () => KLASSEN.has('rk-zu');"
        "if (rueckstandStartZu(window.innerWidth)) rueckstandZeigen(false, false);")
    # seit 1.9.290 ruft setView() auftraegeListeOffen() (test_v690): ohne gemerkten Zeitraum ist es 1 Woche -- die Fälle hier unverändert
    return im_browser("planning.html", ["setView", "rueckstandZeigen", "rueckstandStartZu", "rkKnopfBeschriften", "zeitraumGemerkt", "tageAnzahl",
                                        "auftraegeListeOffen"], vorbereitung, ablauf)


@nur_mit_node
@pytest.mark.parametrize("gemerkt, breite, kolonnen_zu", [(None, 1280, True), (None, 1440, False), ("zu", 1440, True), ("offen", 1280, False)])
def test_auftraege_immer_offen_zurueck_der_gemerkte_zustand(gemerkt, breite, kolonnen_zu):
    [stand] = _lauf(gemerkt, breite, "const a=zu(); setView('auftraege'); const b=zu(); setView('teams'); const c=zu();"
                                     "AUFRUFE.push([a, b, c, SPEICHER.plantafel_rueckstand ?? null]);")
    assert stand == [kolonnen_zu, False, kolonnen_zu, gemerkt]  # nichts gemerkt


@nur_mit_node
def test_in_auftraege_zugeklappt_bleibt_zu_bis_zum_naechsten_wechsel():
    [stand] = _lauf(None, 1440, "setView('auftraege'); rueckstandZeigen(false, view!=='auftraege'); const a=zu(); setView('auftraege'); const b=zu();"
                                "setView('employees'); setView('auftraege'); AUFRUFE.push([a, b, zu(), SPEICHER.plantafel_rueckstand ?? null]);")
    assert stand == [True, True, False, None]  # zu bleibt in „Aufträge“, nichts gemerkt; der nächste Wechsel öffnet wieder


@nur_mit_node
def test_wechsel_zwischen_den_uebrigen_ansichten_aendert_die_liste_nicht():
    [stand] = _lauf(None, 1280, "rueckstandZeigen(true); setView('employees'); const a=zu(); setView('resources'); AUFRUFE.push([a, zu(), SPEICHER.plantafel_rueckstand]);")
    assert stand == [False, False, "offen"]  # der Knopf in „Kolonnen“ merkt weiter (Regel 1.9.257)


def test_spalten_und_chips():
    seite = SEITE.read_text(encoding="utf-8")
    assert "const nameW=window.innerWidth<1400||eng?200:230;" in seite  # seit 1.9.293 auch ab 2 Wochen 200 px (test_v693)
    assert '<col class="a-name-spalte" style="width:${nameW}px">' in seite
    assert 'style="min-width:${nameW+arbeit*(eng?56:84)+we*26}px"' in seite
    assert "@container (max-width:92px){.a-einsatz .geraetzeichen{display:none}}" in seite
    assert "const GERAETZEICHEN='<svg class=\"geraetzeichen\"" in seite and "const KRANZEICHEN='<svg class=\"kranzeichen\"" in seite
    assert "container-type:inline-size;" in seite and "padding:6px 4px;" in seite and "min-height:26px;padding:2px 6px;" in seite


def test_knopf_merkt_in_auftraege_nichts():
    seite = SEITE.read_text(encoding="utf-8")
    assert "addEventListener('click',()=>rueckstandZeigen(document.getElementById('tafelLayout').classList.contains('rk-zu'),view!=='auftraege'))" in seite
