"""Version 1.9.290 (Stufe 6, R5e, Punkt 1): „Zum Einplanen“ in „Aufträge“ startet nach dem Zeitraum -- mit 1 Woche immer offen (1.9.283), mit 2–4 Wochen wie
„Nicht eingeplant“ in den übrigen Ansichten (gemerkt, sonst unter 1440 px zu, rueckstandStartZu() seit 1.9.257).

    Start      beim Wechsel nach „Aufträge“ mit dem gemerkten Zeitraum der Ansicht und bei jedem anderen Zeitraum in „Aufträge“ (zeitraumGewechselt());
               in den übrigen Ansichten ändert ein anderer Zeitraum die Liste nicht
    Merken     nichts: weder der Start noch der Knopf in „Aufträge“ schreiben plantafel_rueckstand (1.9.283 Nr. 2)
Gemessen im Klicktest scripts/klicktest_plantafel_auftraege.py (1280 px, 2 Wochen: Liste zu, die Tabelle rollt nicht).
"""

import json

import pytest

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

SEITE = ROOT / "app/templates/planning.html"
FUNKTIONEN = ["setView", "rueckstandZeigen", "rueckstandStartZu", "rkKnopfBeschriften", "zeitraumGemerkt", "zeitraumMerken", "tageAnzahl",
              "auftraegeListeOffen", "zeitraumGewechselt"]


def _lauf(gemerkt: str | None, breite: int, zeitraum: dict | None, ablauf: str) -> list:
    speicher = {}
    if gemerkt:
        speicher["plantafel_rueckstand"] = gemerkt
    if zeitraum:
        speicher["plantafel_zeitraum"] = json.dumps(zeitraum)
    vorbereitung = (
        f"var SPEICHER = {json.dumps(speicher)}; var window = globalThis; window.innerWidth = {breite};"
        "var localStorage = {getItem(k){ return k in SPEICHER ? SPEICHER[k] : null; }, setItem(k, v){ SPEICHER[k] = String(v); }};"
        "var view = 'teams', board = null, GELADEN = 0; function loadBoard(){ GELADEN++; } function renderBoard(){} function bandSchliessen(){}"
        "const ZEITRAUM_SCHLUESSEL='plantafel_zeitraum', ZEITRAUM_VORGABE={auftraege:7}, ZEITRAEUME=[7,14,21,28];"
        "document.getElementById('rangeDays').value = '14';"
        "const KLASSEN = new Set(); document.getElementById('tafelLayout').classList = {toggle(c, an){ an ? KLASSEN.add(c) : KLASSEN.delete(c); },"
        " contains(c){ return KLASSEN.has(c); }, add(c){ KLASSEN.add(c); }, remove(c){ KLASSEN.delete(c); }};"
        "document.getElementById('rkKnopf').querySelector = () => ({setAttribute(){}});"
        "const zu = () => KLASSEN.has('rk-zu');"
        "const zeitraum = t => { document.getElementById('rangeDays').value = String(t); zeitraumGewechselt(); };"
        "if (rueckstandStartZu(window.innerWidth)) rueckstandZeigen(false, false);")
    return im_browser("planning.html", FUNKTIONEN, vorbereitung, ablauf)


@nur_mit_node
@pytest.mark.parametrize("gemerkt, breite, tage, offen", [
    (None, 1280, 7, True), (None, 1280, 14, False), (None, 1280, 21, False), (None, 1280, 28, False),  # unter 1440 px: nur 1 Woche offen
    (None, 1440, 14, True), (None, 1440, 28, True),                                                   # ab 1440 px offen
    ("zu", 1440, 14, False), ("zu", 1280, 7, True),                                                   # gemerkt „zu“ -- mit 1 Woche trotzdem offen
    ("offen", 1280, 14, True),                                                                        # gemerkt „offen“ gilt bei jeder Breite
])
def test_wechsel_nach_auftraege_mit_dem_gemerkten_zeitraum(gemerkt, breite, tage, offen):
    [stand] = _lauf(gemerkt, breite, {"auftraege": tage}, "setView('auftraege'); AUFRUFE.push([tageAnzahl(), !zu(), SPEICHER.plantafel_rueckstand ?? null]);")
    assert stand == [tage, offen, gemerkt]  # nichts gemerkt


@nur_mit_node
def test_anderer_zeitraum_in_auftraege_startet_die_liste_neu():
    [stand] = _lauf(None, 1280, None, "setView('auftraege'); const a=!zu(); zeitraum(14); const b=!zu(); zeitraum(21); const c=!zu(); zeitraum(7); const d=!zu();"
                                      "AUFRUFE.push([a, b, c, d, GELADEN, SPEICHER.plantafel_rueckstand ?? null, JSON.parse(SPEICHER.plantafel_zeitraum)]);")
    assert stand == [True, False, False, True, 4, None, {"auftraege": 7}]  # jeder Wechsel lädt neu (der erste: von 2 Wochen auf 1), merkt den Zeitraum, nicht die Liste


@nur_mit_node
def test_von_hand_auf_oder_zugeklappt_gilt_bis_zum_naechsten_zeitraum():
    # 1 Woche, von Hand zu -> bleibt zu; 2 Wochen bei 1440 px -> wieder offen. 2 Wochen bei 1280 px, von Hand auf -> 3 Wochen: wieder zu
    [a] = _lauf(None, 1440, None, "setView('auftraege'); rueckstandZeigen(false, view!=='auftraege'); const x=zu(); zeitraum(14);"
                                  "AUFRUFE.push([x, zu(), SPEICHER.plantafel_rueckstand ?? null]);")
    [b] = _lauf(None, 1280, {"auftraege": 14}, "setView('auftraege'); rueckstandZeigen(true, view!=='auftraege'); const x=zu(); zeitraum(21);"
                                               "AUFRUFE.push([x, zu(), SPEICHER.plantafel_rueckstand ?? null]);")
    assert a == [True, False, None] and b == [False, True, None]


@nur_mit_node
def test_in_den_uebrigen_ansichten_aendert_ein_anderer_zeitraum_die_liste_nicht():
    [stand] = _lauf(None, 1280, None, "rueckstandZeigen(true); const a=!zu(); zeitraum(28); const b=!zu(); setView('employees'); zeitraum(7);"
                                      "AUFRUFE.push([a, b, !zu(), SPEICHER.plantafel_rueckstand]);")
    assert stand == [True, True, True, "offen"]  # der Knopf in „Kolonnen“ merkt weiter (1.9.257), der Zeitraum ändert nichts
    # gemerkt „zu“: in „Kolonnen“ und „Personen“ bleibt die Liste auch mit 1 Woche zu (in „Aufträge“ wäre sie mit 1 Woche offen) -- Gegenprobe 290_3c
    [zu_bleibt] = _lauf("zu", 1280, None, "const a=zu(); zeitraum(7); const b=zu(); setView('employees'); zeitraum(14); zeitraum(7); AUFRUFE.push([a, b, zu()]);")
    assert zu_bleibt == [True, True, True]


def test_aufbau():
    seite = SEITE.read_text(encoding="utf-8")
    assert "function auftraegeListeOffen(tage){return tage===7||!rueckstandStartZu(window.innerWidth)}" in seite
    assert "if(v==='auftraege'&&!warAuftraege)rueckstandZeigen(auftraegeListeOffen(zeitraumGemerkt(v)),false,false);" in seite
    assert ("function zeitraumGewechselt(){zeitraumMerken(view,tageAnzahl());if(view==='auftraege')rueckstandZeigen(auftraegeListeOffen(tageAnzahl()),false,false);"
            "loadBoard()}") in seite
    assert "document.getElementById('rangeDays').addEventListener('change',zeitraumGewechselt);" in seite
