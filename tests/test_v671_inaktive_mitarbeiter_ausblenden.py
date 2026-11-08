"""Version 1.9.271: Stammdaten -> Mitarbeiter -- „Inaktive MA ausblenden“ über der Liste.

    Kästchen     über der Liste (unter den Kacheln), Vorgabe angehakt; daneben „N inaktiv“ -- gezählt über alle Mitarbeiter, nicht nach der Suche
    ohne Haken   inaktive Zeilen grau (Schrift var(--muted)), „Inaktiv“ in der Spalte Status wie bisher
    merken       der Browser (localStorage „erp_stammdaten_inaktive“: ausblenden | zeigen), je Gerät; ohne Speicher gilt die Wahl bis zum Neuladen
    nur Anzeige  die Kacheln zählen wie bisher nur aktive Mitarbeiter, keine Anfrage beim Umschalten, keine Änderung an Daten oder Rechten
Der Klicktest scripts/klicktest_stammdaten_inaktive.py prüft dasselbe im Browser (Mausklick, Neuladen, Suche, Kacheln, Büro – Auftrag, hell und dunkel).
"""

import re
from pathlib import Path

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node

ROOT = Path(__file__).resolve().parent.parent
VORLAGE = ROOT / "app/templates/master_data.html"
FUNKTIONEN = ["inaktiveGemerkt", "inaktiveMerken", "mitarbeiterDerListe"]


def _text() -> str:
    return VORLAGE.read_text(encoding="utf-8")


def _anweisung(anfang: str) -> str:
    """Die Anweisung der Vorlage, die mit `anfang` beginnt (bis zum Semikolon am Zeilenende) -- wörtlich, damit der Test den Code der Seite ausführt."""
    treffer = re.search(re.escape(anfang) + r"[^\n]*;", _text())
    assert treffer, f"master_data.html: {anfang!r} nicht gefunden -- Test anpassen"
    return treffer.group(0)


def _mitarbeiter_zweig() -> str:
    text = _text()
    start = text.index("else if(current==='employees')")
    return text[start:text.index("else if(current==='teams')", start)]


def _lauf(speicher: dict | None, ablauf: str, *, wirft: bool = False) -> list:
    """Führt die Merk-Funktionen der Seite mit einem Speicher-Attrappe aus; `speicher` None = leer. AUFRUFE bekommt, was `ablauf` hineinlegt."""
    import json
    vorbereitung = (
        f"var SPEICHER = {json.dumps(speicher or {})}; var WIRFT = {'true' if wirft else 'false'}; var RENDER = 0;"
        "var localStorage = {getItem(k){ if (WIRFT) throw new Error('kein Speicher'); return k in SPEICHER ? SPEICHER[k] : null; },"
        " setItem(k, v){ if (WIRFT) throw new Error('kein Speicher'); SPEICHER[k] = String(v); }};"
        "function render(){ RENDER++; }"
        "var AUFRUFE = AUFRUFE || [];\n"
        + _anweisung("const INAKTIVE_SCHLUESSEL=") + "\n"
        + _anweisung("let inaktiveVersteckt=") + "\n"
    )
    return im_browser("master_data.html", FUNKTIONEN, vorbereitung, ablauf)


# --- merken --------------------------------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_vorgabe_angehakt():
    assert _lauf(None, "AUFRUFE.push(inaktiveVersteckt);") == [True]


@nur_mit_node
def test_gemerkte_wahl_gilt_beim_laden():
    assert _lauf({"erp_stammdaten_inaktive": "zeigen"}, "AUFRUFE.push(inaktiveVersteckt);") == [False]
    assert _lauf({"erp_stammdaten_inaktive": "ausblenden"}, "AUFRUFE.push(inaktiveVersteckt);") == [True]
    # ein unbekannter Wert (älterer Stand, von Hand gesetzt) gilt als Vorgabe
    assert _lauf({"erp_stammdaten_inaktive": "irgendwas"}, "AUFRUFE.push(inaktiveVersteckt);") == [True]


@nur_mit_node
def test_umschalten_merkt_im_browser_und_zeichnet_neu():
    [aus, an] = _lauf(None, "inaktiveMerken(false); AUFRUFE.push([inaktiveVersteckt, SPEICHER.erp_stammdaten_inaktive, RENDER]);"
                            "inaktiveMerken(true); AUFRUFE.push([inaktiveVersteckt, SPEICHER.erp_stammdaten_inaktive, RENDER]);")
    assert aus == [False, "zeigen", 1]
    assert an == [True, "ausblenden", 2]


@nur_mit_node
def test_ohne_speicher_gilt_die_wahl_bis_zum_neuladen():
    """Privates Fenster, gesperrte Websitedaten: localStorage wirft -- die Seite lädt mit der Vorgabe und schaltet trotzdem um."""
    [beim_laden, nach_klick] = _lauf(None, "AUFRUFE.push(inaktiveVersteckt); inaktiveMerken(false); AUFRUFE.push([inaktiveVersteckt, RENDER]);",
                                     wirft=True)
    assert beim_laden is True
    assert nach_klick == [False, 1]


@nur_mit_node
def test_liste_ohne_inaktive_nur_mit_haken():
    liste = "[{id:1,active:true},{id:2,active:false},{id:3,active:true}]"
    [mit, ohne] = _lauf(None, f"AUFRUFE.push(mitarbeiterDerListe({liste},true).map(e=>e.id)); AUFRUFE.push(mitarbeiterDerListe({liste},false).map(e=>e.id));")
    assert mit == [1, 3]
    assert ohne == [1, 2, 3]


# --- die Liste -----------------------------------------------------------------------------------------------------------------------------

def test_kaestchen_ueber_der_liste_mit_zahl():
    zweig = _mitarbeiter_zweig()
    wahl = ('<div class="inaktiv-wahl"><label><input type="checkbox" id="inaktiveAusblenden" onchange="inaktiveMerken(this.checked)" '
            "${inaktiveVersteckt?'checked':''}> Inaktive MA ausblenden</label><span id=\"inaktivZahl\" class=\"muted\">${inaktivZahl} inaktiv</span></div>`"
            "+table(headers,rows)")
    assert wahl in zweig  # direkt über der Tabelle, unter den Kacheln
    assert zweig.index("MA in variablen GK") < zweig.index('id="inaktiveAusblenden"')


def test_zahl_ueber_alle_mitarbeiter_nicht_nach_der_suche():
    zweig = _mitarbeiter_zweig()
    assert "const inaktivZahl=employees.filter(e=>!e.active).length;" in zweig


def test_liste_filtert_nach_der_wahl_auch_in_der_suche():
    zweig = _mitarbeiter_zweig()
    assert "let rows=mitarbeiterDerListe(employees,inaktiveVersteckt).filter(x=>textMatch(" in zweig


def test_inaktive_zeile_grau_mit_inaktiv():
    zweig = _mitarbeiter_zweig()
    assert "`<tr${x.active?'':' class=\"inaktiv\"'}>" in zweig
    assert "<td><span class=\"pill\">${x.active?'Aktiv':'Inaktiv'}</span></td>" in zweig
    assert "tr.inaktiv td,tr.inaktiv td b{color:var(--muted)}" in _text()


def test_kacheln_zaehlen_weiter_nur_aktive():
    """Die Kacheln rechnen aus allen Mitarbeitern mit „aktiv“ -- nicht aus der sichtbaren Liste; das Kästchen ändert sie nicht."""
    zweig = _mitarbeiter_zweig()
    assert "const commercial=employees.filter(e=>e.active&&e.cost_allocation==='labor_rate');" in zweig
    assert "const varCount=employees.filter(e=>e.active&&e.cost_allocation==='variable_overhead').length;" in zweig
    kacheln = zweig[:zweig.index("let rows=")]
    assert "mitarbeiterDerListe" not in kacheln and "inaktiveVersteckt" not in kacheln


def test_umschalten_ohne_anfrage():
    """Nur die Anzeige: das Umschalten zeichnet neu, es lädt und speichert nichts."""
    text = _text()
    start = text.index("function inaktiveMerken(")
    rumpf = text[start:text.index("\n", start)]
    assert "render()" in rumpf
    for verboten in ("api(", "fetch(", "lesen(", "speichern(", "load("):
        assert verboten not in rumpf, verboten


def test_fuer_jede_rolle_der_liste():
    """Das Kästchen hängt nicht an der Rolle -- Büro – Auftrag sieht es wie Admin und Büro – Finanzen."""
    zweig = _mitarbeiter_zweig()
    vor = zweig[:zweig.index('<div class="inaktiv-wahl">')]
    # unmittelbar davor schließen die Kacheln -- kein canManageEmployees um das Kästchen
    assert vor.endswith("<b>${varCount}</b></div></div>")
