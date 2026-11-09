"""Version 1.9.281 (Stufe 6, R5c, Punkt 3): Ziehen in der Ansicht „Aufträge“ mit Maus und Finger.

    Liste -> Zelle    Person, Kolonne oder Gerät für diesen Tag an den Auftrag (POST /api/planning/tag-setzen; auf einer Karte genau dieser Einsatz)
    Zelle -> Zelle    diese Person bzw. dieses Gerät für diesen Tag umsetzen (POST …/slots/{id}/umsetzen) -- auf einen anderen Auftrag oder Tag
    Zelle -> Liste    für diesen Tag herausnehmen (POST …/herausnehmen); angetippt: Leiste mit „Für diesen Tag herausnehmen“, „An allen Tagen
                      herausnehmen“, „Einsatz öffnen“
    Anzeige           vor dem Loslassen aus den geladenen Daten: frei, schon woanders (Rückfrage), Antrag offen (ohne Rückfrage), abwesend, ganze Kolonne
    danach            Leiste am Chip „nur <Tag>“ mit den übrigen Tagen, „bis … verlängern“ (POST …/verlaengern) und „Rückgängig“ (die Umkehrung der Antwort)
    Finger            touch-action:none an den Chips, bei grobem Zeiger mindestens 40 px hoch; keine Textauswahl beim Ziehen
Die Abläufe mit echten Maus- und Fingerereignissen prüft scripts/klicktest_plantafel_auftraege_ziehen.py.
"""

import json
import re

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
from tests.test_v680_ansicht_auftraege import BOARD, FUNKTIONEN

SEITE = ROOT / "app/templates/planning.html"
MO, DI, MI, DO, FR = "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"
TAFEL = {**BOARD, "teams": [{"id": 5, "name": "Kolonne Süd", "employees": [{"id": 2, "name": "Kai Kolb", "vorname": "Kai"},
                                                                         {"id": 3, "name": "Nele Neu", "vorname": "Nele"}]},
                            {"id": 6, "name": "Kolonne West", "employees": [{"id": 8, "name": "Ute Ufer", "vorname": "Ute"}]}]}
ZIEHEN = ["tagText", "slotVon", "schonWoanders", "zugAnzeige", "zugAusfuehren", "zugSenden", "merkeZug", "herausnehmenTag", "zugVerlaengern", "zugZurueck"]


def _seitenzeile(anfang: str) -> str:
    """eine Deklaration der Seite wörtlich (z. B. const FELD=…;)"""
    treffer = re.search(re.escape(anfang) + r"[^\n]*", SEITE.read_text(encoding="utf-8"))
    assert treffer, anfang
    return treffer.group(0)


def _lauf(ablauf: str) -> list:
    vorbereitung = (f"var board = {json.dumps(TAFEL)}; const WOCHENTAGE=['So','Mo','Di','Mi','Do','Fr','Sa'];"
                    "document.getElementById('rangeDays').value = '7';"
                    "function esc(s){return String(s??'').replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',\"'\":'&#39;','\"':'&quot;'}[c]))}"
                    "function localDateIso(d){const p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`}"
                    + _seitenzeile("let azug=null,letzterZug=null,chipTipp=false;") + _seitenzeile("const FELD=")
                    + "var GELADEN=0; async function loadBoard(){GELADEN++} function einsatzHinweise(){} function zugLeisteSchliessen(){}"
                    "function konfliktFrage(){return false} function leerFrage(){return false}")
    return im_browser("planning.html", FUNKTIONEN + ZIEHEN, vorbereitung, ablauf)


def _anzeige(z: dict, ziel: dict) -> dict:
    [a] = _lauf(f"AUFRUFE.push(zugAnzeige({json.dumps(z)},{json.dumps(ziel)}));")
    return a


# --- Anzeige vor dem Loslassen ---------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_anzeige_frei_und_schon_woanders():
    aus_liste = {"art": "person", "id": 1, "slot": None}
    assert _anzeige(aus_liste, {"tag": MI, "auftrag": 99}) == {"klasse": "frei", "text": "Frei – Mi 11.11."}  # Tom steht am Mi nicht
    assert _anzeige(aus_liste, {"tag": MO, "auftrag": 99}) == {"klasse": "woanders", "text": "Schon woanders: Wasserturm – Rückfrage „Trotzdem planen“"}
    assert _anzeige(aus_liste, {"tag": MO, "auftrag": 10})["klasse"] == "frei"  # am selben Auftrag ist nicht „woanders“
    # aus seiner Zelle: der Einsatz, aus dem er kommt, zählt nicht -- umgesetzt ohne Rückfrage
    assert _anzeige({"art": "person", "id": 1, "slot": 1}, {"tag": MO, "auftrag": 99}) == {"klasse": "frei", "text": "Frei – Mo 09.11."}
    # Kai steht am Fr an zwei Einsätzen: aus dem einen umgesetzt, bleibt der andere -- die Rückfrage kommt
    assert _anzeige({"art": "person", "id": 2, "slot": 1}, {"tag": FR, "auftrag": 99}) == {
        "klasse": "woanders", "text": "Schon woanders: Kran – Rückfrage „Trotzdem planen“"}


@nur_mit_node
def test_anzeige_antrag_abwesend_und_geraet():
    assert _anzeige({"art": "person", "id": 3, "slot": None}, {"tag": DO, "auftrag": 99}) == {"klasse": "antrag", "text": "Antrag offen – plant ohne Rückfrage"}
    assert _anzeige({"art": "person", "id": 4, "slot": None}, {"tag": FR, "auftrag": 99}) == {"klasse": "woanders", "text": "Abwesend – Rückfrage „Trotzdem planen“"}
    assert _anzeige({"art": "geraet", "id": 9, "slot": None}, {"tag": FR, "auftrag": 99}) == {
        "klasse": "woanders", "text": "Schon woanders: Wasserturm, Kran – Rückfrage „Trotzdem planen“"}
    assert _anzeige({"art": "geraet", "id": 7, "slot": None}, {"tag": MI, "auftrag": 99}) == {"klasse": "frei", "text": "Frei – Mi 11.11."}


@nur_mit_node
def test_anzeige_ganze_kolonne():
    assert _anzeige({"art": "kolonne", "id": 5, "slot": None}, {"tag": FR, "auftrag": 99}) == {
        "klasse": "woanders", "text": "Ganze Kolonne – Kai, Nele schon woanders: Rückfrage für alle"}
    assert _anzeige({"art": "kolonne", "id": 5, "slot": None}, {"tag": MO, "auftrag": 99}) == {"klasse": "frei", "text": "Ganze Kolonne – Mo 09.11."}
    assert _anzeige({"art": "kolonne", "id": 6, "slot": None}, {"tag": FR, "auftrag": 99})["klasse"] == "frei"


# --- was beim Loslassen hinausgeht -----------------------------------------------------------------------------------------------------

ANTWORT = ("ANTWORT = (url) => ({slot_id: 1, tage: ['2026-11-12'], umkehrung: {pfad: '/api/planning/rueckgaengig', "
           "body: {schritte: [{art: 'weg', slot_id: 1, employee_id: 2, tage: ['2026-11-12']}]}}});")


def _gesendet(ablauf: str) -> list:
    return [(a["url"], a["body"]) for a in _lauf(ANTWORT + ablauf) if a.get("methode") == "POST"]


@nur_mit_node
def test_aus_der_liste_tag_setzen():
    assert _gesendet(f"await zugAusfuehren({{art:'person',id:2,slot:null}},{{art:'zelle',tag:'{DO}',auftrag:10,karte:1}});") == [
        ("/api/planning/tag-setzen", {"order_id": 10, "tag": DO, "employee_id": 2, "slot_id": 1})]  # auf der Karte: genau dieser Einsatz
    assert _gesendet(f"await zugAusfuehren({{art:'kolonne',id:5,slot:null}},{{art:'zelle',tag:'{MO}',auftrag:12,karte:null}});") == [
        ("/api/planning/tag-setzen", {"order_id": 12, "tag": MO, "team_id": 5})]  # ohne Karte entscheidet der Server (dazu, verlängert, neu)
    assert _gesendet(f"await zugAusfuehren({{art:'geraet',id:7,slot:null}},{{art:'zelle',tag:'{MI}',auftrag:12,karte:null}});") == [
        ("/api/planning/tag-setzen", {"order_id": 12, "tag": MI, "resource_id": 7})]
    assert _gesendet("await zugAusfuehren({art:'person',id:2,slot:null},{art:'liste'});") == []  # aus der Liste auf die Liste: nichts


@nur_mit_node
def test_aus_der_zelle_umsetzen_oder_herausnehmen():
    assert _gesendet(f"await zugAusfuehren({{art:'person',id:1,slot:1,tag:'{MO}'}},{{art:'zelle',tag:'{FR}',auftrag:11,karte:2}});") == [
        ("/api/planning/slots/1/umsetzen", {"employee_id": 1, "tage": [MO], "ziel_tag": FR, "ziel_order_id": 11, "ziel_slot_id": 2})]
    assert _gesendet(f"await zugAusfuehren({{art:'geraet',id:7,slot:1,tag:'{MO}'}},{{art:'zelle',tag:'{DI}',auftrag:10,karte:null}});") == [
        ("/api/planning/slots/1/umsetzen", {"resource_id": 7, "tage": [MO], "ziel_tag": DI, "ziel_order_id": 10})]  # anderer Tag, derselbe Auftrag
    assert _gesendet(f"await zugAusfuehren({{art:'person',id:1,slot:1,tag:'{MO}'}},{{art:'zelle',tag:'{MO}',auftrag:10,karte:1}});") == []  # zurück an seinen Platz
    assert _gesendet(f"await zugAusfuehren({{art:'person',id:1,slot:1,tag:'{MO}'}},{{art:'liste'}});") == [
        ("/api/planning/slots/1/herausnehmen", {"employee_id": 1, "tage": [MO]})]
    assert _gesendet(f"await herausnehmenTag({{art:'person',id:1,slot:1,tag:'{MO}'}},{{alle:true}});") == [
        ("/api/planning/slots/1/herausnehmen", {"employee_id": 1, "alle": True})]


@nur_mit_node
def test_danach_verlaengern_und_rueckgaengig():
    [zug] = _lauf(ANTWORT + f"await zugAusfuehren({{art:'person',id:2,slot:null}},{{art:'zelle',tag:'{DO}',auftrag:10,karte:1}});"
                  "AUFRUFE.length=0;AUFRUFE.push({tag:letzterZug.tag,tage:letzterZug.antwort.tage,geladen:GELADEN});")
    assert zug == {"tag": DO, "tage": [DO], "geladen": 1}  # die Antwort bleibt für die Leiste, die Tafel lädt neu
    assert _gesendet(f"await zugAusfuehren({{art:'person',id:2,slot:null}},{{art:'zelle',tag:'{DO}',auftrag:10,karte:1}});AUFRUFE.length=0;"
                     "await zugVerlaengern();") == [("/api/planning/slots/1/verlaengern", {"employee_id": 2, "ab_tag": DO})]
    # stand sie danach schon an weiteren Tagen des Einsatzes, verlängert es ab ihrem letzten Tag (nicht ab dem Tag des Zugs)
    assert _gesendet(f"ANTWORT = () => ({{slot_id: 1, tage: ['{DO}', '{FR}', '{MO}'], umkehrung: null}});"
                     f"await zugAusfuehren({{art:'person',id:2,slot:null}},{{art:'zelle',tag:'{MO}',auftrag:10,karte:1}});AUFRUFE.length=0;"
                     "await zugVerlaengern();") == [("/api/planning/slots/1/verlaengern", {"employee_id": 2, "ab_tag": FR})]
    assert _gesendet(f"await zugAusfuehren({{art:'person',id:2,slot:null}},{{art:'zelle',tag:'{DO}',auftrag:10,karte:1}});AUFRUFE.length=0;"
                     "await zugZurueck();") == [("/api/planning/rueckgaengig", {"schritte": [{"art": "weg", "slot_id": 1, "employee_id": 2, "tage": [DO]}]})]
    # nach „Rückgängig“ ist nichts mehr zurückzunehmen
    assert _gesendet(f"await zugAusfuehren({{art:'person',id:2,slot:null}},{{art:'zelle',tag:'{DO}',auftrag:10,karte:1}});AUFRUFE.length=0;"
                     "await zugZurueck();AUFRUFE.length=0;await zugZurueck();await zugVerlaengern();") == []
    # ohne Umkehrung in der Antwort kein Rückgängig
    assert _gesendet("ANTWORT = () => ({slot_id: 1, tage: ['2026-11-12'], umkehrung: null});"
                     f"await zugAusfuehren({{art:'person',id:2,slot:null}},{{art:'zelle',tag:'{DO}',auftrag:10,karte:1}});AUFRUFE.length=0;"
                     "await zugZurueck();") == []


@nur_mit_node
def test_rueckfragen_nacheinander_gelten_zusammen():
    """erst „niemand mehr“ (Behalten), dann eine neue Warnung (Trotzdem planen): die letzte Anfrage trägt beide Antworten"""
    ablauf = ("var WEITER={};"
              "konfliktFrage=(e,w)=>{if(e.status!==409||!e.warnungen)return false;WEITER.konflikt=w;AUFRUFE.push({frage:'konflikt'});return true};"
              "leerFrage=(e,w)=>{if(e.status!==409||!e.rueckfrage)return false;WEITER.leer=w;AUFRUFE.push({frage:'leer'});return true};"
              "api=async(url,opt)=>{const b=JSON.parse(opt.body);AUFRUFE.push({url,body:b});"
              "if(!b.wenn_leer){const e=new Error('leer');e.status=409;e.rueckfrage={art:'einsatz_leer'};throw e}"
              "if(!b.trotzdem_planen){const e=new Error('warnung');e.status=409;e.warnungen=[{art:'person'}];throw e}"
              "return {slot_id:2,tage:['2026-11-13']}};"
              "await zugSenden('/api/planning/slots/1/umsetzen',{employee_id:1},a=>AUFRUFE.push({fertig:a.slot_id}));"
              "await WEITER.leer('behalten');await WEITER.konflikt();AUFRUFE.push({geladen:GELADEN});")
    url = "/api/planning/slots/1/umsetzen"
    assert _lauf(ablauf) == [
        {"url": url, "body": {"employee_id": 1}}, {"frage": "leer"},
        {"url": url, "body": {"employee_id": 1, "wenn_leer": "behalten"}}, {"frage": "konflikt"},
        {"url": url, "body": {"employee_id": 1, "wenn_leer": "behalten", "trotzdem_planen": True}}, {"fertig": 2}, {"geladen": 1}]
    # umgekehrt: erst die Warnung (Trotzdem planen), dann „niemand mehr“ (Löschen) -- „Trotzdem planen“ bleibt
    umgekehrt = ablauf.replace("if(!b.wenn_leer){const e=new Error('leer')", "if(!b.trotzdem_planen){const e=new Error('warnung');e.status=409;e.warnungen=[{art:'person'}];throw e}"
                               "if(!b.wenn_leer){const e=new Error('leer')").replace("await WEITER.leer('behalten');await WEITER.konflikt();",
                                                                                     "await WEITER.konflikt();await WEITER.leer('loeschen');")
    assert _lauf(umgekehrt)[-3:] == [{"url": url, "body": {"employee_id": 1, "trotzdem_planen": True, "wenn_leer": "loeschen"}}, {"fertig": 2}, {"geladen": 1}]


# --- Aufbau der Seite --------------------------------------------------------------------------------------------------------------------

def test_chips_mit_dem_finger_greifbar_ohne_textauswahl():
    seite = SEITE.read_text(encoding="utf-8")
    assert ".ansicht-auftraege .chip[data-art]{touch-action:none;cursor:grab;-webkit-user-select:none;user-select:none}" in seite
    # seit 1.9.284 (R5d, Punkt 2): mit dem Finger 32 px hoch und ein größerer Treffbereich (bis 1.9.283 40 px hohe Chips, test_v684)
    assert "@media (pointer:coarse){.ansicht-auftraege .chip[data-art]{min-height:32px;" in seite
    # Pointer Events am Layout (Maus und Finger), Escape bricht ab, Antippen öffnet das Menü statt des Einsatzes
    for teil in ("lay.addEventListener('pointerdown',", "lay.addEventListener('pointermove',", "lay.addEventListener('pointerup',",
                 "lay.addEventListener('pointercancel',()=>zugAbbrechen());", "if(e.key==='Escape'&&azug){chipTipp=true;zugAbbrechen()}",
                 "if(!z.aktiv){if(z.slot)chipMenue(z);return}"):
        assert teil in seite, teil


def test_knopf_und_hinweis_je_ansicht():
    seite = SEITE.read_text(encoding="utf-8")
    assert "k.setAttribute('aria-label',(view==='auftraege'?'Zum Einplanen':'Nicht eingeplant')+(k.getAttribute('aria-expanded')==='true'?' einklappen':' aufklappen'))" in seite
    assert "document.getElementById('fussTafel').hidden=view==='auftraege';document.getElementById('fussAuftraege').hidden=view!=='auftraege';" in seite
    assert '<span id="fussAuftraege" hidden>Eine Karte ist ein Einsatz an diesem Tag, Klick öffnet ihn.' in seite
