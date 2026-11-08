"""Version 1.9.264 (Stufe 6, R5a, Punkt 5): die Plantafel zeigt die Besetzung je Tag.

    Dialog      je gewählter Person ihre Tage wie bei den Geräten: „alle Tage“ oder „nur …“, Knöpfe je Tag (personTageZeigen(), personTagUmschalten());
                ändert sich der Zeitraum, bleiben nur die Tage darin (tageImZeitraum())
    Kolonnen    je Stück des Einsatzes ein Balken (abschnitte vom Server) -- eine Lücke am leeren Tag; die Vornamen je Stück
    Personen    je Folge ihrer Tage ein Balken (folgen(personTageIn()))
    Warnung     am Stück, dessen Tage sie betrifft (imStueck()); „doppelt“ in der Zeile einer Person je Tag
Im Browser: scripts/klicktest_plantafel_tage.py (Testdaten der Zeichnung, Bilder 1440 und 1280 px, hell und dunkel).
"""

import json

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v647_plantafel_tafel import ESC, _slot

TAGE = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
HELFER = ("function fmt(s){const t=String(s).slice(0,10).split('-');return t[2]+'.'+t[1]+'.'}"
          "function addDays(s,n){const d=new Date(s+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)}")
GEO = "const geo={spalten:Array.from({length:14},(_,k)=>({d:new Date(Date.UTC(2026,10,9+k)).toISOString().slice(0,10)}))};"


def _wasserturm(**mehr):
    """Am Wasserturm 4, Kolonne Nord Mo–Fr: Tom und Mia Mo, Di, Do, Fr; Kai nur Do und Fr -- am Mi niemand (Zeichnung, Fundament)."""
    ohne_mi = [TAGE[0], TAGE[1], TAGE[3], TAGE[4]]
    s = _slot(1, 1, TAGE[0], TAGE[4], employees=[{"id": 11, "name": "Tom Test", "vorname": "Tom", "tage": ohne_mi},
                                                   {"id": 12, "name": "Mia Test", "vorname": "Mia", "tage": ohne_mi},
                                                   {"id": 14, "name": "Kai Test", "vorname": "Kai", "tage": [TAGE[3], TAGE[4]]}])
    return {**s, "project_name": "Am Wasserturm 4", "abschnitte": [[TAGE[0], TAGE[1]], [TAGE[3], TAGE[4]]], "leere_tage": [TAGE[2]], "niemand": False, **mehr}


@nur_mit_node
def test_kolonne_mit_luecke_und_namen_je_stueck():
    board = {"teams": [{"id": 1, "name": "Nord", "employees": [{"id": 11, "name": "Tom Test", "vorname": "Tom", "kf": True}]}],
             "employees": [], "resources": [], "abwesenheiten": [], "geraete_termine": [], "slots": [_wasserturm()]}
    vorbereitung = (ESC + f";let board={json.dumps(board)};let view='teams';let filterAn=false;" + GEO + HELFER + ";const KONFLIKT_ART={};")
    aufrufe = im_browser("planning.html", ["fmtSpanne", "einsatzTage", "personTageIn", "vornamen", "imStueck", "einsatzTitel", "slotHinweis", "einsatzBalken",
                                           "mitgliederText", "abwesendText", "stueckItems", "zeilen"], vorbereitung,
                         "AUFRUFE.push({z:zeilen()[0].items.map(i=>[i.von,i.bis,i.b.text+' · '+i.b.leise])});")
    assert aufrufe[-1]["z"] == [[TAGE[0], TAGE[1], "Am Wasserturm 4 · Tom, Mia"], [TAGE[3], TAGE[4], "Am Wasserturm 4 · Tom, Mia, Kai"]]


@nur_mit_node
def test_ohne_abschnitte_ein_balken_und_ganz_leer_niemand():
    s = _slot(2, None, TAGE[2], TAGE[2], employees=[])
    s = {**s, "niemand": True}  # ganz leer -- vom Server ein Stück, hier ohne „abschnitte“ (wie eine Antwort von vor 1.9.263)
    vorbereitung = (ESC + f";let board={{teams:[]}};var s={json.dumps(s)};" + HELFER + ";const KONFLIKT_ART={};")
    [erg] = [x for x in im_browser("planning.html", ["einsatzTage", "personTageIn", "vornamen", "imStueck", "einsatzTitel", "slotHinweis", "einsatzBalken",
                                                     "stueckItems"], vorbereitung,
                                   "AUFRUFE.push({i:stueckItems(s,'ohne').map(i=>[i.von,i.bis,i.b.leise])});") if "i" in x]
    assert erg["i"] == [[TAGE[2], TAGE[2], "niemand"]]


@nur_mit_node
def test_person_je_folge_ihrer_tage():
    vorbereitung = f"var s={json.dumps(_wasserturm())};" + HELFER
    [erg] = [x for x in im_browser("planning.html", ["einsatzTage", "personTageIn", "folgen"], vorbereitung,
                                   "AUFRUFE.push({tom:folgen(personTageIn(s,11)),kai:folgen(personTageIn(s,14)),wer:personTageIn(s,99),"
                                   "alle:folgen(personTageIn({...s,employees:[{id:7,tage:null}]},7))});") if "tom" in x]
    assert erg == {"tom": [[TAGE[0], TAGE[1]], [TAGE[3], TAGE[4]]], "kai": [[TAGE[3], TAGE[4]]], "wer": [], "alle": [[TAGE[0], TAGE[4]]]}
    seite = (__import__("pathlib").Path(__file__).resolve().parent.parent / "app/templates/planning.html").read_text(encoding="utf-8")
    assert ".flatMap(s=>folgen(personTageIn(s,p.id)).map(([von,bis])=>({von,bis,b:einsatzBalken(s,'person',g.team,p.id,undefined,[von,bis])})))" in seite


@nur_mit_node
def test_warnung_am_stueck_ihrer_tage():
    s = _wasserturm(conflicts=[{"type": "employee", "stufe": "warnung", "employee_id": 14, "tage": [TAGE[4]]},
                               {"type": "capacity", "stufe": "hinweis"}])
    vorbereitung = (f"var board = {{teams: []}}; var s = {json.dumps(s)}; function vornamen() {{ return ''; }} function einsatzTitel() {{ return ''; }}")
    ablauf = ("AUFRUFE.push({k: [[s.abschnitte[0]], [s.abschnitte[1]]].map(([st]) => { const b = einsatzBalken(s, 'kolonne', undefined, undefined, undefined, st); "
              "return [b.warn, b.hint]; }), p: (b => [b.warn, b.hint])(einsatzBalken(s, 'person', 1, 14, undefined, [TAGE0, TAGE0]))});").replace("TAGE0", repr(TAGE[3]))
    [erg] = [x for x in im_browser("planning.html", ["imStueck", "einsatzBalken"], vorbereitung, ablauf) if "k" in x]
    assert erg["k"] == [[False, True], [True, True]]  # Mo–Di ohne Warnung (Kai erst Fr doppelt), der Kapazitätshinweis an jedem Stück
    assert erg["p"] == [False, False]  # Kais Balken nur am Do: die Warnung (Fr) gehört nicht dazu; „Personen“ zeigt nur Konflikte der Person (1.9.250)


@nur_mit_node
def test_doppelt_je_tag():
    board = {"slots": [_wasserturm(), {**_slot(2, None, TAGE[2], TAGE[2]), "employees": [{"id": 11, "tage": None}]},
                       {**_slot(3, None, TAGE[4], TAGE[4]), "employees": [{"id": 14, "tage": None}]}]}
    vorbereitung = f"var board={json.dumps(board)};" + GEO + HELFER
    [erg] = [x for x in im_browser("planning.html", ["einsatzTage", "personTageIn", "folgen", "fmtSpanne", "doppeltText"], vorbereitung,
                                   "AUFRUFE.push({tom:doppeltText(11),kai:doppeltText(14)});") if "tom" in x]
    assert erg == {"tom": "", "kai": "doppelt 13.11."}  # Tom am Mi beim Ortgang, am Wasserturm nicht -- bis 1.9.263 „doppelt 11.11.“


@nur_mit_node
def test_dialog_tage_je_person_und_zeitraum():
    vorbereitung = (HELFER + "var geaendert=new Set();var geprueft=0;function pruefenJetzt(){geprueft++}"
                    f"var einsatz={{start_date:'{TAGE[0]}',end_date:'{TAGE[4]}',besetzung:[{{employee_id:11,tage:null}},{{employee_id:14,tage:['{TAGE[3]}','{TAGE[4]}']}}],"
                    f"geraete:[{{resource_id:2,tage:['{TAGE[4]}']}},{{resource_id:3,tage:null}}]}};")
    ablauf = ("personTagUmschalten(11,'2026-11-11');const a=JSON.parse(JSON.stringify(einsatz.besetzung));"
              "personTagUmschalten(11,'2026-11-11');const b=JSON.parse(JSON.stringify(einsatz.besetzung));"
              "personTagUmschalten(14,'2026-11-12');personTagUmschalten(14,'2026-11-13');const c=JSON.parse(JSON.stringify(einsatz.besetzung));"
              "einsatz.end_date='2026-11-12';tageImZeitraum();"
              "AUFRUFE.push({a,b,c,d:einsatz.besetzung,g:einsatz.geraete,geaendert:[...geaendert],geprueft});")
    [erg] = [x for x in im_browser("planning.html", ["einsatzTage", "personTagUmschalten", "tageImZeitraum"], vorbereitung, ablauf) if "a" in x]
    assert erg["a"][0] == {"employee_id": 11, "tage": [TAGE[0], TAGE[1], TAGE[3], TAGE[4]]}  # Mi abgewählt
    assert erg["b"][0] == {"employee_id": 11, "tage": None}  # wieder alle Tage
    assert erg["c"][1] == {"employee_id": 14, "tage": [TAGE[4]]}  # der letzte Tag lässt sich nicht abwählen (dafür das Häkchen)
    assert erg["d"] == [{"employee_id": 11, "tage": None}]  # Kai stand nur am Fr -- außerhalb des neuen Zeitraums, er fällt weg
    assert erg["g"] == [{"resource_id": 3, "tage": None}]
    assert erg["geaendert"] == ["besetzung"] and erg["geprueft"] == 3


@nur_mit_node
def test_dialog_zeile_mit_tagen():
    vorbereitung = ESC + ";const ZUSTAND_KLASSE={};const WARNZEICHEN='';"
    ablauf = ("AUFRUFE.push({g:personZeile({id:14,name:'Kai Test',gewaehlt:true,zustand:'frei',text:'frei',tage:['2026-11-12'],tage_text:'nur 12.11.'}),"
              "n:personZeile({id:15,name:'Lia Test',gewaehlt:false,zustand:'frei',text:'frei'})});")
    [erg] = [x for x in im_browser("planning.html", ["personZeile"], vorbereitung, ablauf) if "g" in x]
    assert '<button type="button" class="link-knopf" data-klick="personTage" data-id="14" aria-expanded="false">nur 12.11.</button>' in erg["g"]
    assert '<div class="tage-wahl" data-tage-person="14" hidden></div>' in erg["g"]
    assert "personTage" not in erg["n"]  # nicht gewählt: keine Tage


@nur_mit_node
def test_warnung_nennt_ihre_tage():
    vorbereitung = ESC + ";const KONFLIKT_ART={employee:'Person doppelt: '};" + HELFER
    ablauf = ("AUFRUFE.push({z:konfliktZeile({type:'employee',label:'Kai Kolb',other_project:'P-1',other_project_name:'Garage',tage:['2026-11-12','2026-11-13']})});")
    [erg] = [x for x in im_browser("planning.html", ["konfliktZeile"], vorbereitung, ablauf) if "z" in x]
    assert erg["z"] == '<div class="conflict-row"><b>Person doppelt: Kai Kolb</b> · gleichzeitig in P-1 · Garage · 12.11., 13.11.</div>'


@nur_mit_node
def test_titel_nennt_die_tage_je_person():
    vorbereitung = f"var s={json.dumps(_wasserturm())};const KONFLIKT_ART={{}};" + HELFER
    [erg] = [x for x in im_browser("planning.html", ["slotHinweis", "einsatzTitel"], vorbereitung, "AUFRUFE.push({t:einsatzTitel(s).split(String.fromCharCode(10))});") if "t" in x]
    assert "Besetzung: Tom Test (nur 09.11., 10.11., 12.11., 13.11.), Mia Test (nur 09.11., 10.11., 12.11., 13.11.), Kai Test (nur 12.11., 13.11.)" in erg["t"]
