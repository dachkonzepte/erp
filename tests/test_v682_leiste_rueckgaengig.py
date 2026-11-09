"""Version 1.9.282 (Stufe 6, R5c, Punkt 4): Leiste „Rückgängig“ über der Tafel in „Kolonnen“, „Personen“ und „Geräte“ (Antwort 5 zu R5b) und Klick in einen
freien Tag in „Aufträge“.

    Leiste     nach einem Zug (Einsatz verschieben in „Kolonnen“, Person bzw. Gerät ziehen in „Personen“ und „Geräte“) eine schmale Leiste über der Tafel: was
               geschah und „Rückgängig“ (die Umkehrung aus der Antwort); bis zur nächsten Aktion -- der nächste Klick außerhalb der Leiste, eine andere Ansicht,
               ein anderer Zeitraum; ohne Umkehrung kein „Rückgängig“
    Rückfragen beide Züge gehen über zugSenden() (seit 1.9.281): Warnungen und „niemand mehr“ fragen nacheinander, die Antworten gelten zusammen -- bis 1.9.281
               ging beim Ziehen in „Personen“ eine zweite Rückfrage verloren
    Aufträge   Klick in einen freien Teil eines Tags öffnet den Dialog für diesen Auftrag und diesen Tag (ohne Kolonne); eine Karte öffnet ihren Einsatz
Die Abläufe mit echter Maus prüft scripts/klicktest_plantafel_rueckgaengig.py.
"""

import json

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
from tests.test_v680_ansicht_auftraege import BOARD, FUNKTIONEN

SEITE = ROOT / "app/templates/planning.html"
TAFEL = {**BOARD, "employees": [{"id": 1, "name": "Tom Monteur"}, {"id": 2, "name": "Kai Kolb"}, {"id": 3, "name": "Nele Neu"}],
         "teams": [{"id": 5, "name": "Kolonne Süd", "employees": []}]}
TAFEL["slots"] = [{**TAFEL["slots"][0], "team_id": None}, TAFEL["slots"][1]]
WEITERE = ["findSlot", "fmtSpanne", "tagText", "verschieben", "umsetzenZiehen", "zugSenden", "bandZeigen", "bandSchliessen", "bandZurueck", "personName"]
UMKEHRUNG = {"pfad": "/api/planning/rueckgaengig", "body": {"schritte": [{"art": "zurueck", "slot_id": 1, "stand": "x"}]}}


def _lauf(ablauf: str, antwort: dict | None = None) -> list:
    antwort = {"slot_id": 1, "start_date": "2026-11-10", "end_date": "2026-11-16", "umkehrung": UMKEHRUNG} if antwort is None else antwort
    vorbereitung = (f"var board = {json.dumps(TAFEL)}; const WOCHENTAGE=['So','Mo','Di','Mi','Do','Fr','Sa']; var geo = {{spalten: [{{d: '2026-11-09'}}]}};"
                    f"ANTWORT = () => ({json.dumps(antwort)});"
                    "document.getElementById('rangeDays').value = '7';"
                    "function esc(s){return String(s??'').replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',\"'\":'&#39;','\"':'&quot;'}[c]))}"
                    "function localDateIso(d){const p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`}"
                    "var bandUmkehrung=null; var GELADEN=0; async function loadBoard(){GELADEN++} function einsatzHinweise(){}"
                    "function konfliktFrage(){return false} function leerFrage(){return false}"
                    "const band=()=>{const b=document.getElementById('zugBand');return b.hidden?null:b.innerHTML};")
    return im_browser("planning.html", FUNKTIONEN + WEITERE, vorbereitung, ablauf)


def _post(aufrufe: list) -> list:
    return [(a["url"], a["body"]) for a in aufrufe if a.get("methode") == "POST"]


@nur_mit_node
def test_verschieben_zeigt_die_leiste():
    aufrufe = _lauf("await verschieben(1,{dataset:{zeile:'kolonne',id:'5'}},1);AUFRUFE.push({band:band()});")
    assert _post(aufrufe) == [("/api/planning/slots/1/verschieben", {"auf": "2026-11-10", "team_id": 5})]
    assert aufrufe[-1]["band"] == ('<span class="zug-band-text">Wasserturm: 09.–13.11. → 10.–16.11. · Kolonne Süd</span>'
                                   '<button type="button" class="ds-knopf" data-klick="bandZurueck">Rückgängig</button>')


@nur_mit_node
def test_ohne_umkehrung_kein_rueckgaengig():
    [*_, letzte] = _lauf("await verschieben(1,null,1);AUFRUFE.push({band:band()});",
                        antwort={"slot_id": 1, "start_date": "2026-11-10", "end_date": "2026-11-16", "umkehrung": None})
    assert letzte["band"] == '<span class="zug-band-text">Wasserturm: 09.–13.11. → 10.–16.11.</span>'


@nur_mit_node
def test_umsetzen_in_der_eigenen_und_einer_anderen_zeile():
    # seit 1.9.289 nennt die Leiste den neuen Zeitraum aus der Antwort (ziel_tage) statt „ab <Tag>“ (test_v689)
    neu = {"slot_id": 1, "ziel_tage": ["2026-11-11", "2026-11-12"], "umkehrung": UMKEHRUNG}
    eigene = _lauf("await umsetzenZiehen({id:1,zeile:'person',wer:1,von:'2026-11-09',bis:'2026-11-10'},{dataset:{zeile:'person',id:'1'}},2);"
                   "AUFRUFE.push({band:band()});", antwort=neu)
    assert _post(eigene) == [("/api/planning/slots/1/umsetzen", {"employee_id": 1, "tage": ["2026-11-09", "2026-11-10"], "ziel_tag": "2026-11-11",
                                                                 "ziel_slot_id": 1, "genau": True})]
    assert eigene[-1]["band"].startswith('<span class="zug-band-text">Tom Monteur · Wasserturm: 09.–10.11. → 11.–12.11.</span>')
    andere = _lauf("await umsetzenZiehen({id:1,zeile:'person',wer:1,von:'2026-11-09',bis:'2026-11-10'},{dataset:{zeile:'person',id:'2'}},0);"
                   "AUFRUFE.push({band:band()});", antwort={**neu, "ziel_tage": ["2026-11-09", "2026-11-10"]})
    assert _post(andere)[0][1]["auf_employee_id"] == 2
    assert andere[-1]["band"].startswith('<span class="zug-band-text">Wasserturm 09.–10.11.: Tom Monteur → Kai Kolb</span>')


@nur_mit_node
def test_rueckgaengig_schickt_die_umkehrung_und_schliesst():
    aufrufe = _lauf("await verschieben(1,null,1);AUFRUFE.length=0;await bandZurueck();AUFRUFE.push({band:band(),geladen:GELADEN});"
                    "await bandZurueck();")
    assert _post(aufrufe) == [("/api/planning/rueckgaengig", UMKEHRUNG["body"])]  # einmal -- danach ist nichts mehr zurückzunehmen
    assert {"band": None, "geladen": 2} in aufrufe


@nur_mit_node
def test_ziehen_in_personen_fragt_nacheinander():
    """bis 1.9.281 ging hier nach „niemand mehr“ (Behalten) die Rückfrage einer Warnung verloren -- jetzt über zugSenden()"""
    ablauf = ("var WEITER={};"
              "konfliktFrage=(e,w)=>{if(e.status!==409||!e.warnungen)return false;WEITER.konflikt=w;return true};"
              "leerFrage=(e,w)=>{if(e.status!==409||!e.rueckfrage)return false;WEITER.leer=w;return true};"
              "api=async(url,opt)=>{const b=JSON.parse(opt.body);AUFRUFE.push({body:b});"
              "if(!b.wenn_leer){const e=new Error('leer');e.status=409;e.rueckfrage={art:'einsatz_leer'};throw e}"
              "if(!b.trotzdem_planen){const e=new Error('w');e.status=409;e.warnungen=[{}];throw e}return {slot_id:1,umkehrung:null}};"
              "await umsetzenZiehen({id:1,zeile:'person',wer:2,von:'2026-11-12',bis:'2026-11-13'},{dataset:{zeile:'person',id:'3'}},3);"
              "await WEITER.leer('loeschen');await WEITER.konflikt();")
    letzte = _lauf(ablauf)[-1]["body"]
    assert (letzte["wenn_leer"], letzte["trotzdem_planen"], letzte["auf_employee_id"]) == ("loeschen", True, 3)
    # umgekehrt: erst die Warnung (Trotzdem planen), dann „niemand mehr“ (Löschen)
    umgekehrt = ablauf.replace("if(!b.wenn_leer){const e=new Error('leer')", "if(!b.trotzdem_planen){const e=new Error('w');e.status=409;e.warnungen=[{}];throw e}"
                               "if(!b.wenn_leer){const e=new Error('leer')").replace("await WEITER.leer('loeschen');await WEITER.konflikt();",
                                                                                     "await WEITER.konflikt();await WEITER.leer('loeschen');")
    letzte = _lauf(umgekehrt)[-1]["body"]
    assert (letzte["wenn_leer"], letzte["trotzdem_planen"], letzte["auf_employee_id"]) == ("loeschen", True, 3)


def test_leiste_schliesst_mit_der_naechsten_aktion():
    seite = SEITE.read_text(encoding="utf-8")
    assert '<div class="zug-band" id="zugBand" role="status" hidden></div>' in seite
    # beim Klick, nicht beim Drücken -- sonst rückt die Tafel mitten im Ziehen (die Leiste verschwände beim Greifen eines Balkens)
    assert "document.addEventListener('click',e=>{if(!e.target.closest||!e.target.closest('#zugBand'))bandSchliessen()},true);" in seite
    assert "addEventListener('pointerdown',e=>{if(!e.target.closest||!e.target.closest('#zugBand'))" not in seite
    assert "function movePeriod(n){bandSchliessen();" in seite and "function setView(v){bandSchliessen();" in seite


def test_klick_in_einen_freien_tag_in_auftraege():
    seite = SEITE.read_text(encoding="utf-8")
    # seit 1.9.285 mit der Kolonne des Auftrags, wenn er an anderen Tagen genau eine hat (test_v685; bis 1.9.284 immer ohne: null)
    assert ("document.getElementById('planner').addEventListener('click',e=>{if(view!=='auftraege'||e.target.closest('.a-einsatz'))return;"
            "const td=e.target.closest('td.a-tag');if(!td)return;\n    const auftrag=Number(td.dataset.auftrag);"
            "openCreate(auftrag,td.dataset.date,kolonneDesAuftrags(auftrag),{bis:td.dataset.date})});") in seite.replace("\r\n", "\n")
    assert "Klick in einen freien Teil eines Tags plant den Auftrag an diesem Tag (mit seiner Kolonne, wenn er genau eine hat)." in seite
