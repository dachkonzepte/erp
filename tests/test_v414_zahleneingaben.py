"""Version 1.8.109 -- Zahleneingaben im deutschen Format über eine gemeinsame Funktion (Vorgabe "Vor dem Abnahmetest" Punkt 1;
docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.109").

Bis 1.8.108 waren Zahlenfelder <input type="number">; Chrome liest dort bei deutscher Sprache den Punkt als Dezimaltrenner -- aus
"1.250" wurde still 1,25, aus "1.250,5" sogar 1,2505 (gemessen 15.10.2026, headless Chrome mit --lang=de-DE). Daneben hatten
einzelne Seiten eigene Umwandlungen (Komma ersetzen, num() mit Tausenderpunkt-Logik, parseFloat). Seit 1.8.109 sind Zahlenfelder
Textfelder mit data-zahl, gelesen und gefüllt nur über app/templates/_zahl.html.

- Angriffstabelle in node: zahlLesen() mit Tausenderpunkten, Mehrdeutigem ("1.25" mit Meldung abgelehnt, nie umgedeutet), fremden
  Zeichen, Grenzen, leer; zahlText() und der Weg hin und zurück; zahlFeld() liest Optionen und Beschriftung aus dem Feld und markiert
  ein abgelehntes Feld; abschliessen() (_speichern.html) geht nicht hinaus, solange ein Feld abgelehnt ist.
- Strukturtest (tests/vorlagen_zahlen.py) über alle Vorlagen: kein type="number", keine eigene Umwandlung (Number()/+/Rechnen auf
  einen Feldwert, parseFloat/parseInt, Komma ersetzen), kein roher Text eines Zahlenfelds, Füllen nur über zahlText(), Baustein
  eingebunden. Die Ausnahmeliste darf nur kürzer werden. Dazu Selbsttests des Scanners an erfundenen Vorlagen."""

import json
import re
from pathlib import Path

import pytest

from tests import vorlagen_js, vorlagen_zahlen
from tests.test_v314_dashboard_month_berlin import NODE, TEMPLATES, _node
from tests.test_v398_speichern_baustein import _ablauf

nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


def _zahl_js() -> str:
    return re.search(r"<script>(.*?)</script>", (TEMPLATES / "_zahl.html").read_text(encoding="utf-8"), flags=re.S).group(1)


def _js(code: str):
    """_zahl.html in node (ohne window und document wie in einer Testseite ohne DOM), dann code; code schreibt das Ergebnis."""
    return _node(_zahl_js() + "\n" + code, "Europe/Berlin")


def _lesen(faelle):
    """[(text, optionen)] -> je Fall {"wert": …} oder {"fehler": Meldung}."""
    return _js(f"const faelle={json.dumps(faelle)};process.stdout.write(JSON.stringify(faelle.map(([t,o])=>"
               "{try{return {wert:zahlLesen(t,o)}}catch(e){return {fehler:e.message,zahlFehler:!!e.zahlFehler}}})));")


# ---------------------------------------------------------------------------
# Angriffstabelle: zahlLesen()
# ---------------------------------------------------------------------------

GUELTIG = [
    ("1.250", {}, 1250), ("1.250,5", {}, 1250.5), ("1250,5", {}, 1250.5), ("1.250.000", {}, 1250000),
    ("1.250.000,99", {}, 1250000.99), ("0,5", {}, 0.5), (",5", {}, 0.5), ("12", {}, 12), ("-3,5", {}, -3.5),
    ("−3,5", {}, -3.5), ("+7", {}, 7), ("  42  ", {}, 42), ("007", {}, 7), ("0", {}, 0), ("-0", {}, 0),
    ("999.999,99", {"stellen": 2}, 999999.99), ("12,500", {"stellen": 2}, 12.5), ("1,0", {"ganz": True}, 1),
    ("1.250", {"ganz": True}, 1250), ("0", {"min": 0}, 0), ("365", {"max": 365}, 365),
]

MEHRDEUTIG = ["1.25", "0.5", "12.5", "1.2", "1.", "0.250", "12.50", "1.2345", "1.250.5", "1.25.000"]

KEINE_ZAHL = ["1,2,3", "1e3", "1E3", "abc", "Infinity", "NaN", "1 250", "12€", "12 %", "1.250,", "5,", "0x10", "--1", "+-1",
              "1.25,5", "12.50,5", "1,250.5", ".", ",", "-", "١٢", "１２", "1 250", "1_000", "١,٥"]


@nur_mit_node
def test_gueltige_eingaben_im_deutschen_format():
    ergebnis = _lesen([[t, o] for t, o, _ in GUELTIG])
    assert [e.get("wert", e) for e in ergebnis] == [w for _, _, w in GUELTIG]


@nur_mit_node
def test_mehrdeutiges_wird_mit_meldung_abgelehnt_nie_umgedeutet():
    ergebnis = _lesen([[t, {"feld": "Menge"}] for t in MEHRDEUTIG])
    for text, e in zip(MEHRDEUTIG, ergebnis):
        assert "wert" not in e, (text, e)
        assert e["zahlFehler"] and e["fehler"].startswith(f"Menge: „{text}“ ist nicht eindeutig"), (text, e)
        assert "1,25" in e["fehler"] and "1.250" in e["fehler"], e  # die Meldung sagt, wie es richtig geht


@nur_mit_node
def test_vier_ziffern_nach_einem_punkt_und_ein_zweiter_punkt_vor_einer_ziffer_werden_abgelehnt():
    """Vorgabe vom 16.10.2026, Punkt 6 (1.8.119): "1.2500" (vier Ziffern nach dem Punkt) und "1.250.5" (ein zweiter Punkt vor nur einer
    Ziffer) sind weder Tausenderformat noch Dezimalzahl -- abgelehnt mit Meldung, nie als 12500, 1,25 oder 1250,5 gelesen; ebenso mit
    Komma dahinter und an zahlFeld() (das Feld bleibt markiert)."""
    faelle = {
        "1.2500": "nicht eindeutig", "1.250.5": "nicht eindeutig", "12.2500": "nicht eindeutig", "1.250.50": "nicht eindeutig",
        "1.2500,5": "keine Zahl – Tausenderpunkte nur vor je drei Ziffern", "1.250.5,5": "keine Zahl – Tausenderpunkte nur vor je drei Ziffern",
    }
    ergebnis = _lesen([[t, {"feld": "Menge"}] for t in faelle])
    for (text, art), e in zip(faelle.items(), ergebnis):
        assert "wert" not in e, (text, e)
        assert e["zahlFehler"] and e["fehler"].startswith(f"Menge: „{text}“ ist {art}"), (text, e)
    feld = _js("""const attr={};const f={value:'1.2500',dataset:{zahl:''},getAttribute:k=>attr[k]??null,
      setAttribute:(k,v)=>{attr[k]=v},removeAttribute:k=>{delete attr[k]},id:'menge'};
      let fehler=null;try{zahlFeld(f,{feld:'Menge'})}catch(e){fehler=e.message}
      process.stdout.write(JSON.stringify({fehler,markiert:attr['aria-invalid']||null}));""")
    assert feld["fehler"].startswith("Menge: „1.2500“ ist nicht eindeutig") and feld["markiert"] == "true", feld


@nur_mit_node
def test_was_keine_zahl_ist_wird_abgelehnt():
    ergebnis = _lesen([[t, {"feld": "Betrag"}] for t in KEINE_ZAHL])
    for text, e in zip(KEINE_ZAHL, ergebnis):
        assert "wert" not in e, (text, e)
        assert e["zahlFehler"] and e["fehler"].startswith("Betrag: „"), (text, e)
        assert "keine Zahl" in e["fehler"] or "nicht eindeutig" in e["fehler"], (text, e)


@nur_mit_node
def test_grenzen_ganze_zahlen_stellen_und_leer():
    faelle = [
        ("1,5", {"feld": "Tage", "ganz": True}, "Tage: „1,5“ – bitte eine ganze Zahl angeben."),
        ("1,234", {"feld": "Gebühr", "stellen": 2}, "Gebühr: „1,234“ – höchstens 2 Nachkommastellen."),
        ("1,25", {"feld": "Satz", "stellen": 1}, "Satz: „1,25“ – höchstens 1 Nachkommastelle."),
        ("-1", {"feld": "Menge", "min": 0}, "Menge darf nicht kleiner als 0 sein (eingegeben „-1“)."),
        ("400", {"feld": "Zahlungsfrist", "max": 365}, "Zahlungsfrist darf nicht größer als 365 sein (eingegeben „400“)."),
        ("0,0005", {"feld": "Menge", "min": 0.001}, "Menge darf nicht kleiner als 0,001 sein (eingegeben „0,0005“)."),
        ("", {"feld": "Tage bis Fälligkeit", "pflicht": True}, "Tage bis Fälligkeit fehlt."),
        ("   ", {"feld": "Tage", "pflicht": True}, "Tage fehlt."),
    ]
    ergebnis = _lesen([[t, o] for t, o, _ in faelle])
    assert [e.get("fehler", e) for e in ergebnis] == [m for _, _, m in faelle]
    leer = _lesen([["", {}], ["  ", {"leer": 0}], ["", {"leer": 100}], ["", {"leer": None}]])
    assert [e["wert"] for e in leer] == [None, 0, 100, None]


@nur_mit_node
def test_eine_lange_eingabe_wird_in_der_meldung_gekuerzt():
    [e] = _lesen([["x" * 200, {"feld": "Menge"}]])
    assert e["fehler"] == "Menge: „" + "x" * 30 + "…“ ist keine Zahl."


# ---------------------------------------------------------------------------
# zahlText() und der Weg hin und zurück
# ---------------------------------------------------------------------------

@nur_mit_node
def test_zahltext_schreibt_deutsch_ohne_tausenderpunkte():
    faelle = [[1250.5, None], ["1.250", None], ["12.50", 2], [12.5, 2], [-0.0001, 2], [None, None], ["", None], ["abc", None],
              [0, None], [1e21, None], [0.1 + 0.2, None], [-3.5, None], ["7", None], [19, 2]]
    ergebnis = _js(f"process.stdout.write(JSON.stringify({json.dumps(faelle)}.map(([w,s])=>zahlText(w,s===null?undefined:s))));")
    assert ergebnis == ["1250,5", "1,25", "12,50", "12,50", "0,00", "", "", "", "0", "1000000000000000000000", "0,3", "-3,5",
                        "7", "19,00"]


@nur_mit_node
def test_was_zahltext_schreibt_liest_zahllesen_unveraendert_zurueck():
    werte = [0, 1, 7.5, 12.25, 1250, 1250.5, 999999.99, 0.001, -3.75, 1234567.891, 0.3, 100000]
    ergebnis = _js(f"process.stdout.write(JSON.stringify({json.dumps(werte)}.map(w=>zahlLesen(zahlText(w)))));")
    assert ergebnis == werte


# ---------------------------------------------------------------------------
# zahlFeld() und zahlVorschau() am Feld
# ---------------------------------------------------------------------------

_FELD = r"""
function feld(wert, dataset, extra) {
  const attr = {};
  return Object.assign({value: wert, dataset: dataset || {}, required: false, attr,
    getAttribute: k => (k in attr ? attr[k] : null), setAttribute: (k, v) => { attr[k] = String(v); },
    removeAttribute: k => { delete attr[k]; }}, extra || {});
}
function versuch(f) { try { return {wert: f()}; } catch (e) { return {fehler: e.message}; } }
"""


@nur_mit_node
def test_zahlfeld_liest_optionen_und_beschriftung_aus_dem_feld_und_markiert_eine_ablehnung():
    ergebnis = _js(_FELD + r"""
const tage = feld('400', {zahl: 'ganz', min: '1', max: '365', feld: 'Zahlungsfrist'});
const a = versuch(() => zahlFeld(tage));
const markiert = tage.attr['aria-invalid'];
tage.value = '30';
const b = versuch(() => zahlFeld(tage));
const nachher = tage.attr['aria-invalid'] === undefined;
const mitLabel = feld('', {}, {required: true, labels: [{childNodes: [{nodeType: 3, textContent: ' Tage bis Fälligkeit * '},
  {nodeType: 1, tagName: 'INPUT', textContent: 'x'}]}]});
const c = versuch(() => zahlFeld(mitLabel));
const gebuehr = feld('12,345', {zahl: '', stellen: '2', feld: 'Mahngebühr'});
const d = versuch(() => zahlFeld(gebuehr));
const e = versuch(() => zahlFeld(gebuehr, {stellen: 3}));
const f = versuch(() => zahlFeld(feld('', {}), {leer: 0}));
const ohne = versuch(() => zahlFeld(feld('1.25', {})));
const vorschau = [zahlVorschau(feld('1.25', {})), zahlVorschau(feld('', {}, {required: true})), zahlVorschau(feld('1.250,5', {})),
                  zahlVorschau(feld('400', {max: '365'}))];
process.stdout.write(JSON.stringify({a, markiert, b, nachher, c, d, e, f, ohne, vorschau}));
""")
    assert ergebnis["a"] == {"fehler": "Zahlungsfrist darf nicht größer als 365 sein (eingegeben „400“)."}
    assert ergebnis["markiert"] == "true" and ergebnis["b"] == {"wert": 30} and ergebnis["nachher"]
    assert ergebnis["c"] == {"fehler": "Tage bis Fälligkeit fehlt."}  # Beschriftung aus dem Label, required = Pflicht
    assert ergebnis["d"] == {"fehler": "Mahngebühr: „12,345“ – höchstens 2 Nachkommastellen."}
    assert ergebnis["e"] == {"wert": 12.345} and ergebnis["f"] == {"wert": 0}
    assert ergebnis["ohne"]["fehler"].startswith("Die Zahl: „1.25“ ist nicht eindeutig")
    assert ergebnis["vorschau"] == [None, None, 1250.5, None]  # wirft nie, auch nicht bei Pflicht


@nur_mit_node
def test_abschliessen_geht_nicht_hinaus_solange_ein_zahlenfeld_abgelehnt_ist():
    vorspann = ("globalThis.ABGELEHNT=null;globalThis.document={querySelector:s=>s==='input[data-zahl][aria-invalid=\"true\"]'"
                "?globalThis.ABGELEHNT:null};")
    log = _ablauf("""
        ABGELEHNT={dataset:{feld:'Menge'}};
        log.push(await abschliessen('unterschrift',anfrage('U1')).then(()=>'gesendet',e=>e.message+' | '+e.dkBaustein));
        ABGELEHNT=null;
        const b=abschliessen('unterschrift',anfrage('U2')); await ruhe(); await antworte('U2'); await b;
    """, vorspann=vorspann)
    assert log == ["Nicht ausgeführt: eine Zahl auf der Seite ist ungültig (Menge) und nicht gespeichert. Bitte korrigieren und "
                   "erneut versuchen. | abschluss", "gesendet U2"]


# ---------------------------------------------------------------------------
# Strukturtest über alle Vorlagen
# ---------------------------------------------------------------------------

# (Vorlage, Art, Ausschnitt, Grund) -- keine Zahleneingabe. Darf nur kürzer werden; eine neue Stelle braucht einen Grund.
AUSNAHMEN = [
    ("_berlin_date.html", "wert", "Number(p.value)",
     "Intl.DateTimeFormat.formatToParts(): p ist ein Teil des formatierten Datums, kein Eingabefeld"),
    ("inquiries.html", "wert", "Number(s.value||0)",
     "Auswahlliste Kunde (newCustomer/editCustomer), die ID kommt aus einer Schleife über beide -- für den Scanner nicht auflösbar"),
]


def _ausgenommen(fund) -> bool:
    return any(fund.vorlage == v and fund.art == art and stelle in fund.ausschnitt for v, art, stelle, _ in AUSNAHMEN)


def test_keine_zahleneingabe_an_der_gemeinsamen_funktion_vorbei():
    offen = [str(f) for f in vorlagen_zahlen.alle_funde() if not _ausgenommen(f)]
    assert not offen, ("Zahleneingabe an _zahl.html vorbei (zahlFeld()/zahlLesen()/zahlVorschau() zum Lesen, zahlText() zum Füllen, "
                       "Feld type=\"text\" inputmode=\"decimal\" data-zahl) -- oder eine begründete Ausnahme in AUSNAHMEN:\n"
                       + "\n".join(offen))


def test_die_ausnahmeliste_hat_keine_veralteten_eintraege():
    funde = vorlagen_zahlen.alle_funde()
    veraltet = [f"{v} [{art}] {stelle}" for v, art, stelle, _ in AUSNAHMEN
                if not any(f.vorlage == v and f.art == art and stelle in f.ausschnitt for f in funde)]
    assert not veraltet, "Eintrag in AUSNAHMEN ohne Fundstelle -- bitte streichen (die Liste darf nur kürzer werden):\n" + "\n".join(veraltet)
    assert len(AUSNAHMEN) <= 2  # Stand 1.8.109


def test_jede_seite_mit_zahlenfeld_bindet_den_baustein_ein():
    assert vorlagen_zahlen.ohne_einbindung() == []
    fehlt = []
    for name in vorlagen_zahlen.alle_vorlagen():
        if name.startswith("_"):
            continue
        _, herkunft = vorlagen_js.vorlage_mit_includes(name)
        if any(e.zahl for e in vorlagen_zahlen.elemente(name)) and "_zahl.html" not in {d for _, _, d, _ in herkunft}:
            fehlt.append(name)
    assert not fehlt, f"Zahlenfeld ohne _zahl.html: {fehlt}"


def test_es_gibt_zahlenfelder_und_sie_nutzen_den_baustein():
    """Die Umstellung ist da: Zahlenfelder in vielen Vorlagen, gelesen über zahlFeld() (nicht nur still alles entfernt)."""
    felder = sum(len(re.findall(r"\bdata-zahl\b", (TEMPLATES / n).read_text(encoding="utf-8"))) for n in vorlagen_zahlen.alle_vorlagen())
    lesen = sum(len(re.findall(r"\bzahlFeld\(", (TEMPLATES / n).read_text(encoding="utf-8"))) for n in vorlagen_zahlen.alle_vorlagen())
    assert felder >= 140 and lesen >= 120, (felder, lesen)


# ---------------------------------------------------------------------------
# Selbsttest des Scanners an erfundenen Vorlagen
# ---------------------------------------------------------------------------

@pytest.fixture
def vorlagen(tmp_path, monkeypatch):
    monkeypatch.setattr(vorlagen_js, "TEMPLATES", tmp_path)
    monkeypatch.setattr(vorlagen_zahlen, "TEMPLATES", tmp_path)
    vorlagen_zahlen.elemente.cache_clear()
    vorlagen_zahlen.funde_der_vorlage.cache_clear()

    def schreiben(**dateien):
        for name, text in dateien.items():
            (tmp_path / name.replace("__", ".")).write_text(text, encoding="utf-8")
        vorlagen_zahlen.elemente.cache_clear()
        vorlagen_zahlen.funde_der_vorlage.cache_clear()
    yield schreiben
    vorlagen_zahlen.elemente.cache_clear()
    vorlagen_zahlen.funde_der_vorlage.cache_clear()


ZAHL = '<input id="a" type="text" inputmode="decimal" data-zahl>'
TEXT = '<input id="t" type="text">'
AUSWAHL = '<select id="s"></select>'


def _arten(name="seite.html"):
    return sorted(f.art for f in vorlagen_zahlen.Scanner(name).pruefen())


@pytest.mark.parametrize("markup, skript, erwartet", [
    ('<input id="a" type="number">', "", ["type-number"]),
    ("<script>const e=`<input type=number id=\"b\">`</script>", "", ["type-number"]),
    ('<input id="a" type="text" data-zahl>', "", ["inputmode"]),
    (ZAHL, "const x=Number(document.getElementById('a').value)", ["roh", "wert"]),  # Zahlenfeld: beides
    (ZAHL, "const x=+document.getElementById('a').value", ["roh", "wert"]),
    (ZAHL, "const x=document.getElementById('a').value*2", ["roh", "wert"]),
    (ZAHL, "const x=Math.round(document.getElementById('a').value)", ["roh", "wert"]),
    (TEXT, "const x=Number(document.getElementById('t').value)", ["wert"]),
    (TEXT, "const t=document.getElementById('t').value.trim();const n=Number(t)", ["wert"]),
    (TEXT, "const v=id=>document.getElementById(id).value;const n=Number(v('t'))", ["wert"]),
    ("", "const x=parseFloat(y);const z=parseInt(w,10)", ["parse", "parse"]),
    ("", "const x=s.replace(',', '.');const y=s.replace(/,/g,'.')", ["komma", "komma"]),
    (ZAHL, "api('/x',{body:JSON.stringify({a:document.getElementById('a').value})})", ["roh"]),
    (ZAHL, "document.getElementById('a').value=x.menge", ["schreiben"]),
    ('<script>const z=`<input id="b${i}" type="text" inputmode="decimal" data-zahl value="${x.m}">`</script>', "", ["schreiben"]),
    ('<input id="m" type="text" inputmode="decimal" data-zahl oninput="setze(Number(this.value))">', "", ["roh", "wert"]),
    ('<input id="m" type="text" oninput="setze(Number(this.value))">', "", ["wert"]),
    ('<input class="menge" type="text">', "const a=[...document.querySelectorAll('.menge')].map(x=>Number(x.value))", ["wert"]),
    ('<input id="rl${x.id}Days" type="text" inputmode="numeric" data-zahl="ganz">',
     "const d=Number(document.getElementById('rl'+id+'Days').value)", ["roh", "wert"]),
])
def test_der_scanner_findet_jede_art(vorlagen, markup, skript, erwartet):
    vorlagen(seite__html=f"<html>{markup}<script>{skript}</script></html>")
    assert _arten() == erwartet


@pytest.mark.parametrize("markup, skript", [
    (ZAHL, "const x=zahlFeld('a');const y=zahlFeld(document.getElementById('a'),{leer:0})"),
    (ZAHL, "const x=zahlLesen(document.getElementById('a').value,{feld:'Menge'})"),
    (ZAHL, "document.getElementById('a').value=zahlText(x.menge,2);document.getElementById('a').value=''"),
    ('<script>const z=`<input id="b${i}" type="text" inputmode="decimal" data-zahl value="${zahlText(x.m)}">`</script>', ""),
    (AUSWAHL, "const id=Number(document.getElementById('s').value)"),
    (AUSWAHL, "const v=id=>document.getElementById(id).value;const n=Number(v('s'))"),
    ('<select id="s" onchange="setze(Number(this.value))"></select>', ""),
    ('<input type="checkbox" class="wahl">', "const a=[...document.querySelectorAll('.wahl:checked')].map(x=>Number(x.value))"),
    ('<input id="rl${x.id}Days" type="text" inputmode="numeric" data-zahl="ganz"><input id="rl${x.id}Label" type="text">',
     "api('/x',{body:JSON.stringify({label:document.getElementById('rl'+id+'Label').value})})"),
    (TEXT, "const n=Number(antwort.betrag);const m=Number(x.value_count)"),
    (TEXT, "const laenge=document.getElementById('t').value.length*2"),
])
def test_der_scanner_laesst_erlaubtes_stehen(vorlagen, markup, skript):
    vorlagen(seite__html=f"<html>{markup}<script>{skript}</script></html>")
    assert _arten() == []


def test_der_scanner_verlangt_die_einbindung(vorlagen):
    vorlagen(ohne__html="<script>const x=zahlFeld('a')</script>", mit__html='{% include "_zahl.html" %}<script>zahlText(1)</script>',
             _zahl__html="<script>function zahlText(){}</script>", _teil__html="<script>zahlFeld('b')</script>",
             teil__html='{% include "_teil.html" %}')
    assert vorlagen_zahlen.ohne_einbindung() == ["ohne.html", "teil.html"]


# ---------------------------------------------------------------------------
# Punkte 2–4: Zahlungsbedingungen, Festschreiben, Plantafel, Team entfernen (Angriffstests in node)
# ---------------------------------------------------------------------------

def _seite_api(vorlage: str, status: int, body) -> str:
    """Die Funktion api() der Vorlage samt ihren FELDNAMEN und _fehlertext.html, gegen eine abgelehnte Antwort; Ergebnis: die
    Meldung des Fehlers."""
    from tests.test_v399_teil_updates_geld import js_funktion
    html = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    feldnamen = re.search(r"const FELDNAMEN=\{.*?\};", html, flags=re.S)
    fehlertext = re.search(r"<script>(.*?)</script>", (TEMPLATES / "_fehlertext.html").read_text(encoding="utf-8"), flags=re.S).group(1)
    skript = "\n".join([
        fehlertext, feldnamen.group(0) if feldnamen else "", js_funktion(vorlage, "api"),
        f"globalThis.fetch=async()=>({{ok:false,status:{status},statusText:'Unprocessable',headers:{{get:()=>'application/json'}},"
        f"json:async()=>({json.dumps(body)})}});",
        "api('/x',{method:'POST'}).then(()=>process.stdout.write(JSON.stringify('kein Fehler')),"
        "e=>process.stdout.write(JSON.stringify(e.message)));",
    ])
    return _node(skript, "Europe/Berlin")


def _422(feld: str, art: str) -> dict:
    return {"detail": [{"type": art, "loc": ["body", feld], "msg": "x", "input": None}]}


@nur_mit_node
@pytest.mark.parametrize("vorlage, body, erwartet", [
    ("settings.html", _422("days", "int_type"), "Bitte die Eingabe prüfen – Tage bis Fälligkeit muss eine ganze Zahl sein."),
    ("settings.html", _422("label", "string_too_long"), "Bitte die Eingabe prüfen – Bezeichnung ist zu lang."),
    ("planning.html", _422("travel_hours_per_employee_day", "less_than"),
     "Bitte die Eingabe prüfen – Anfahrt je MA / Tag ist zu groß."),
    ("planning.html", _422("start_date", "date_from_datetime_parsing"), "Bitte die Eingabe prüfen – Beginn ist kein gültiges Datum."),
    ("work_preparation.html", {"detail": "Diese Kolonne besitzt noch einen Einsatz in der Plantafel."},
     "Diese Kolonne besitzt noch einen Einsatz in der Plantafel."),
    ("work_preparation.html", _422("team_id", "int_parsing"), "Bitte die Eingabe prüfen – Team muss eine ganze Zahl sein."),
])
def test_abgelehnte_antworten_sind_lesbar(vorlage, body, erwartet):
    """Punkte 2 und 4: bis 1.8.108 reichten Einstellungen, Plantafel und Arbeitsvorbereitung detail roh an Error() weiter -- ein 422
    erschien als "[object Object]"."""
    assert _seite_api(vorlage, 422 if isinstance(body["detail"], list) else 409, body) == erwartet


_ZAHLUNGSBEDINGUNG = (
    "var editingPaymentTermId=null; const v=id=>document.getElementById(id).value.trim(); "
    "function hidePaymentTermEditor(){} async function ladeZahlungsbedingungen(){} "
    "document.getElementById('ptDays').previousElementSibling={tagName:'LABEL',childNodes:[{nodeType:3,textContent:'Tage bis Fälligkeit'}]}; "
)


@nur_mit_node
@pytest.mark.parametrize("tage, erwartet", [
    ("", "Fehler: Tage bis Fälligkeit fehlt."),
    ("1.5", "Fehler: Tage bis Fälligkeit: „1.5“ ist nicht eindeutig"),
    ("2,5", "Fehler: Tage bis Fälligkeit: „2,5“ – bitte eine ganze Zahl angeben."),
    ("-1", "Fehler: Tage bis Fälligkeit darf nicht kleiner als 0 sein (eingegeben „-1“)."),
])
def test_zahlungsbedingung_ohne_gueltige_tage_sendet_nichts(tage, erwartet):
    """Punkt 2: ein leeres "Tage bis Fälligkeit" machte Number('') still zu 0 -- jetzt Meldung, keine Anfrage."""
    from tests.test_v399_teil_updates_geld import im_browser
    aufrufe = im_browser("settings.html", ["savePaymentTerm"], _ZAHLUNGSBEDINGUNG + (
        "const _setzen=(id,w)=>Object.assign(document.getElementById(id),{value:w,dataset:{}}); "
        f"_setzen('ptLabel','21 Tage netto'); _setzen('ptDays',{json.dumps(tage)}); "
        "document.getElementById('ptDays').dataset={zahl:'ganz',min:'0'}; "
        "_setzen('ptSkontoPercent',''); _setzen('ptSkontoDays',''); _setzen('ptTextTemplate','');"),
        "await savePaymentTerm(); AUFRUFE.push({status: document.getElementById('paymentTermStatus').textContent});")
    assert [a for a in aufrufe if "methode" in a] == []
    assert aufrufe[-1]["status"].split(" – ")[0] == erwartet.split(" – ")[0]


@nur_mit_node
def test_zahlungsbedingung_mit_null_tagen_wird_gespeichert():
    from tests.test_v399_teil_updates_geld import im_browser
    aufrufe = im_browser("settings.html", ["savePaymentTerm"], _ZAHLUNGSBEDINGUNG + (
        "const _setzen=(id,w)=>Object.assign(document.getElementById(id),{value:w,dataset:{}}); "
        "_setzen('ptLabel','Sofort fällig'); _setzen('ptDays','0'); document.getElementById('ptDays').dataset={zahl:'ganz',min:'0'}; "
        "_setzen('ptSkontoPercent','2'); _setzen('ptSkontoDays','0'); _setzen('ptTextTemplate','');"),
        "await savePaymentTerm();")
    [(methode, adresse, body)] = [(a["methode"], a["url"], a["body"]) for a in aufrufe if a.get("methode") not in (None, "GET")]
    assert (methode, adresse) == ("POST", "/api/payment-terms")
    assert (body["days"], body["skonto_percent"], body["skonto_days"]) == (0, 2, 0)


_MAHNUNGS_KNOPF = re.compile(r"""onclick="(sendReminder|sendReminderNow)\([^"]*\)">([^<]*)</button>""")


def test_der_knopf_der_nur_festschreibt_heisst_festschreiben():
    """Punkt 3: /api/reminders/{id}/send schreibt fest und verschickt nichts -- der Knopf hieß bis 1.8.108 "Versenden"."""
    gefunden = []
    for vorlage in ("mahnwesen.html", "invoice_detail.html"):
        html = (TEMPLATES / vorlage).read_text(encoding="utf-8")
        knoepfe = _MAHNUNGS_KNOPF.findall(html)
        assert knoepfe, f"{vorlage}: Knopf zum Festschreiben nicht gefunden -- Test anpassen"
        gefunden += [(vorlage, funktion, text) for funktion, text in knoepfe]
        assert "Mahnung jetzt festschreiben?" in html and "Mahnung jetzt versenden?" not in html
    assert {text for _, _, text in gefunden} == {"Festschreiben"}, gefunden
    assert "st.textContent='Festgeschrieben.'" in (TEMPLATES / "invoice_detail.html").read_text(encoding="utf-8")


@nur_mit_node
def test_team_entfernen_zeigt_die_ablehnung():
    """Punkt 4: removeTeam() hatte kein catch -- die 409 des Servers lief ins Leere."""
    from tests.test_v399_teil_updates_geld import im_browser
    aufrufe = im_browser(
        "work_preparation.html", ["removeTeam"],
        "function anwendenPrep(){} "
        "api = async (u, o) => { AUFRUFE.push({url: u, methode: o.method}); "
        "throw new Error('Diese Kolonne besitzt noch einen Einsatz in der Plantafel.'); };",
        "await removeTeam(7); AUFRUFE.push({status: document.getElementById('teamRemoveStatus').textContent});")
    assert aufrufe[0] == {"url": "/api/work-preparation/teams/7", "methode": "DELETE"}
    assert aufrufe[-1]["status"] == "Fehler: Diese Kolonne besitzt noch einen Einsatz in der Plantafel."
