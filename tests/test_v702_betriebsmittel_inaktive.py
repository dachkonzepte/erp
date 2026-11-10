"""Version 1.9.302 (Nachrunde der Geräte-Runde, Punkt 2): Stammdaten -> Betriebsmittel -- „Inaktive ausblenden“ über der Liste.

    Kästchen     wie bei den Mitarbeitern (1.9.271): über der Liste, Vorgabe angehakt, daneben „N inaktiv“ -- gezählt über alle Betriebsmittel und
                 Plantafel-Geräte ohne Betriebsmittel, nicht nach der Suche; die Wahl merkt sich der Browser je Liste (erp_betriebsmittel_inaktive)
    ohne Haken   inaktive Zeilen grau; ein inaktives Plantafel-Gerät ohne Betriebsmittel (der Rest vom Entfernen des Hakens an einem noch benutzten Gerät)
                 steht als „nur Plantafel · inaktiv“ mit „Betriebsmittel anlegen“
    Anlegen      /master-data/assets/new?ressource=<id> nimmt auch ein inaktives freies Gerät: verknüpft, in der Auswahl „(inaktiv)“, Status wie das Gerät
                 (ein Schalter für beides -- es wird nicht still wieder aktiv)
    nur Anzeige  der Untertitel zählt wie bisher aktive „nur Plantafel“, die Fälligkeiten zählen alle; keine Anfrage beim Umschalten
Der Klicktest scripts/klicktest_geraete.py prüft dasselbe im Browser.
"""

import re
from pathlib import Path

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node

ROOT = Path(__file__).resolve().parent.parent
LISTE = ROOT / "app/templates/master_data.html"
FORM = ROOT / "app/templates/master_data_form.html"
FUNKTIONEN = ["bmInaktiveGemerkt", "bmInaktiveMerken", "betriebsmittelDerListe", "bmInaktivZahl"]


def _text() -> str:
    return LISTE.read_text(encoding="utf-8")


def _anweisung(anfang: str) -> str:
    treffer = re.search(re.escape(anfang) + r"[^\n]*;", _text())
    assert treffer, f"master_data.html: {anfang!r} nicht gefunden -- Test anpassen"
    return treffer.group(0)


def _zweig() -> str:
    text = _text()
    start = text.index("else if(current==='assets'&&bmModuleEnabled)")
    return text[start:text.index("else if(current==='assets')", start + 10)]


def _lauf(speicher: dict | None, ablauf: str, *, wirft: bool = False) -> list:
    import json
    vorbereitung = (
        f"var SPEICHER = {json.dumps(speicher or {})}; var WIRFT = {'true' if wirft else 'false'}; var RENDER = 0;"
        "var localStorage = {getItem(k){ if (WIRFT) throw new Error('kein Speicher'); return k in SPEICHER ? SPEICHER[k] : null; },"
        " setItem(k, v){ if (WIRFT) throw new Error('kein Speicher'); SPEICHER[k] = String(v); }};"
        "function render(){ RENDER++; }"
        "var AUFRUFE = AUFRUFE || [];\n"
        + _anweisung("const BM_INAKTIVE_SCHLUESSEL=") + "\n"
        + _anweisung("let bmInaktiveVersteckt=") + "\n"
    )
    return im_browser("master_data.html", FUNKTIONEN, vorbereitung, ablauf)


# --- merken --------------------------------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_vorgabe_angehakt_und_eigene_wahl_je_liste():
    assert _lauf(None, "AUFRUFE.push(bmInaktiveVersteckt);") == [True]
    assert _lauf({"erp_betriebsmittel_inaktive": "zeigen"}, "AUFRUFE.push(bmInaktiveVersteckt);") == [False]
    # die Wahl der Mitarbeiterliste gilt hier nicht
    assert _lauf({"erp_stammdaten_inaktive": "zeigen"}, "AUFRUFE.push(bmInaktiveVersteckt);") == [True]


@nur_mit_node
def test_umschalten_merkt_im_browser_und_zeichnet_neu():
    [aus, an] = _lauf(None, "bmInaktiveMerken(false); AUFRUFE.push([bmInaktiveVersteckt, SPEICHER.erp_betriebsmittel_inaktive, RENDER, "
                            "SPEICHER.erp_stammdaten_inaktive === undefined]);"
                            "bmInaktiveMerken(true); AUFRUFE.push([bmInaktiveVersteckt, SPEICHER.erp_betriebsmittel_inaktive, RENDER]);")
    assert aus == [False, "zeigen", 1, True]
    assert an == [True, "ausblenden", 2]


@nur_mit_node
def test_ohne_speicher_gilt_die_wahl_bis_zum_neuladen():
    [beim_laden, nach_klick] = _lauf(None, "AUFRUFE.push(bmInaktiveVersteckt); bmInaktiveMerken(false); AUFRUFE.push([bmInaktiveVersteckt, RENDER]);",
                                     wirft=True)
    assert beim_laden is True and nach_klick == [False, 1]


@nur_mit_node
def test_zeilen_und_zahlen():
    assets = "[{id:1,active:true,resource_id:11},{id:2,active:false,resource_id:null},{id:3,active:true,resource_id:null}]"
    resources = "[{id:11,active:true},{id:12,active:true},{id:13,active:false}]"
    [mit, ohne] = _lauf(None, f"for (const a of [true,false]) {{ const bm = betriebsmittelDerListe({assets},{resources},a);"
                              f"AUFRUFE.push([bm.betriebsmittel.map(x=>x.id), bm.nurPlantafel.map(x=>x.id), bmInaktivZahl({assets},{resources}), bm.nurAktiv]); }}")
    assert mit == [[1, 3], [12], 2, 1]  # angehakt: nur aktive; gezählt über alle
    assert ohne == [[1, 2, 3], [12, 13], 2, 1]  # ohne Haken: auch das inaktive Betriebsmittel und das inaktive Gerät ohne Betriebsmittel


# --- die Liste -----------------------------------------------------------------------------------------------------------------------------

def test_kaestchen_ueber_der_liste_mit_zahl():
    zweig = _zweig()
    wahl = ('c.innerHTML=panel+`<div class="inaktiv-wahl"><label><input type="checkbox" id="bmInaktiveAusblenden" onchange="bmInaktiveMerken(this.checked)" '
            "${bmInaktiveVersteckt?'checked':''}> Inaktive ausblenden</label><span id=\"bmInaktivZahl\" class=\"muted\">${bmInaktivZahl(assets,resources)} inaktiv</span></div>`"
            "+table(['Nr.','Typ','Betriebsmittel','Nächste Prüffrist','Status',''],rows)")
    assert wahl in zweig  # unter den Fälligkeiten, direkt über der Tabelle


def test_liste_nach_der_wahl_untertitel_wie_bisher():
    zweig = _zweig()
    assert "const bm=betriebsmittelDerListe(assets,resources,bmInaktiveVersteckt);" in zweig
    assert "sub.textContent=`${assets.length} inventarisierte Betriebsmittel${bm.nurAktiv?` · ${bm.nurAktiv} nur Plantafel`:''}`;" in zweig
    assert "let rows=bm.betriebsmittel.filter(x=>textMatch(" in zweig and "rows=rows.concat(bm.nurPlantafel.filter(r=>textMatch(" in zweig
    faellig = zweig[zweig.index("let due="):zweig.index("let rows=")]
    assert "assets.filter(" in faellig and "bm." not in faellig  # die Fälligkeiten zählen alle wie bisher


def test_inaktive_zeilen_grau_und_nur_plantafel_inaktiv():
    zweig = _zweig()
    assert zweig.count("`<tr${x.active?'':' class=\"inaktiv\"'}>") == 1 and zweig.count("`<tr${r.active?'':' class=\"inaktiv\"'}>") == 1
    assert "<span class=\"pill\">nur Plantafel${r.active?'':' · inaktiv'}</span>" in zweig
    assert '<a class="link" href="/master-data/assets/new?ressource=${r.id}">Betriebsmittel anlegen</a>' in zweig
    assert "tr.inaktiv td,tr.inaktiv td b{color:var(--muted)}" in _text()


def test_umschalten_ohne_anfrage():
    text = _text()
    start = text.index("function bmInaktiveMerken(")
    rumpf = text[start:text.index("\n", start)]
    assert "render()" in rumpf
    for verboten in ("api(", "fetch(", "lesen(", "speichern(", "load("):
        assert verboten not in rumpf, verboten


# --- Anlegen mit einem inaktiven Gerät ------------------------------------------------------------------------------------------------------

def test_anlegen_nimmt_auch_ein_inaktives_freies_geraet():
    form = FORM.read_text(encoding="utf-8")
    assert "const vorgabeGeraet=vorgabe?assetResources.find(x=>x.id===vorgabe&&!x.taken)||null:null;if(vorgabeGeraet){el('assetVerknuepfenWrap').hidden=false;" in form
    # der Status des gewählten Geräts -- ein inaktives wird nicht still wieder aktiv
    assert "if(r)auswahlWert(el('assetActiveSelect'),r.active?'1':'0')}" in form
    # in der Auswahl als „(inaktiv)“ (auswahlOptionen kennzeichnet einen gewählten, nicht neu angebotenen Eintrag)
    assert "{leer:'— neues Plantafel-Gerät —',aktiv:x=>x.active&&!x.taken}" in form
