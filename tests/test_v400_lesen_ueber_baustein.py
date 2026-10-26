"""Version 1.8.97 -- jede Anfrage über den Baustein (Vorgabe 1.8.96 Punkt 4; app/templates/_speichern.html, tests/vorlagen_js.py).

Bis 1.8.96 mussten nur das Speichern und das Lesen danach über den Baustein (Festlegung 1.8.95 Nr. 8): ein Lesen, das ein Formular
füllt, ohne dass vorher gespeichert wurde (erstes Laden, Monatswechsel, Wechsel des Dachtyps, Dokumenttyp der E-Mail-Vorlage), konnte
mit einer späten, älteren Antwort eine neuere überschreiben -- und das Formular, aus dem danach gespeichert wird, zeigte den falschen
Stand. Seit 1.8.97:

- kein fetch() außerhalb des Bausteins: jede Stelle, an der eine Seite eine Anfrage außerhalb von lesen()/speichern()/abschliessen()
  abschickt, steht in AUSNAHMEN -- mit Grund, und die Liste darf nur kürzer werden (ein Eintrag ohne Fund ist rot);
- jedes Lesen, das ein Formular füllt, aus dem gespeichert werden kann, geht über lesen() -- es steht deshalb nie in AUSNAHMEN (die
  Gründe dort sind "nur Anzeige", "Suche", "Anmeldestatus" u. ä.); die fünf ausdrücklich verlangten Stellen prüfen eigene Tests;
- veraltete Fehler verwirft der Baustein wie veraltete Erfolge: scheitert ein älteres Lesen, nachdem ein neueres angewandt ist, endet
  es still (false); scheitert ein neueres Lesen, wird ein älteres, das danach ankommt, verworfen (Festlegung 1.8.95 Nr. 3, ergänzt)."""

import re
from pathlib import Path

import pytest

from tests import vorlagen_js as vj
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v398_speichern_baustein import _ablauf

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


# --- Veraltete Fehler ------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_an_older_read_failing_after_a_newer_one_is_applied_ends_quietly():
    log = _ablauf("""
        const a=lesen('liste',anfrage('L1','alt'),anwenden()).then(r=>'ergebnis '+r,e=>'fehler '+e.message);
        const b=lesen('liste',anfrage('L2','neu'),anwenden());
        await ruhe(); await antworte('L2'); await scheitere('L1');
        log.push(await a);
    """)
    assert log == ["gesendet L1", "gesendet L2", 'angewandt "neu"', "ergebnis false"]


@nur_mit_node
def test_after_a_newer_read_failed_an_older_one_is_discarded():
    log = _ablauf("""
        const a=lesen('liste',anfrage('L1','alt'),anwenden()).then(r=>'a '+r);
        const b=lesen('liste',anfrage('L2','neu'),anwenden()).then(r=>'b '+r,e=>'b fehler '+e.message);
        await ruhe(); await scheitere('L2'); await antworte('L1');
        log.push(await b); log.push(await a);
    """)
    assert log == ["gesendet L1", "gesendet L2", "b fehler kaputt L2", "a false"]


@nur_mit_node
def test_a_read_failing_while_it_is_the_newest_still_reports_its_error():
    log = _ablauf("""
        const a=lesen('liste',anfrage('L1'),anwenden()).then(r=>'a '+r,e=>'a fehler '+e.message);
        await ruhe(); await scheitere('L1'); log.push(await a);
        const b=lesen('liste',anfrage('L2','danach'),anwenden()); await ruhe(); await antworte('L2'); log.push('b '+(await b));
    """)
    assert log == ["gesendet L1", "a fehler kaputt L1", "gesendet L2", 'angewandt "danach"', "b true"]


@nur_mit_node
def test_a_failed_save_still_lets_an_older_read_apply():
    """Für Speichern bleibt es bei Festlegung 1.8.95 Nr. 3: scheitert ein Speichern, gilt die zuletzt angekommene Antwort."""
    log = _ablauf("""
        const l=lesen('form',anfrage('L1','stand'),anwenden()); await ruhe();
        const s=speichern('form',anfrage('S1')).catch(e=>'s fehler'); await ruhe();
        await scheitere('S1'); await antworte('L1'); log.push('lesen '+(await l));
    """)
    assert log == ["gesendet L1", "gesendet S1", 'angewandt "stand"', "lesen true"]


# --- Kein fetch außerhalb des Bausteins --------------------------------------------------------------------------------------

# (Datei, Funktion, Ziel) -> Grund. Eine Stelle, an der eine Seite außerhalb von lesen()/speichern()/abschliessen() anfragt (Funktion
# "<oben>": Skript auf oberster Ebene; Ziel: fetch oder der Anfrage-Helfer der Seite). Darf nur kürzer werden: ein Eintrag ohne Fund ist
# rot. Kein Eintrag füllt ein Formular, aus dem gespeichert werden kann -- das geht über lesen().
AUSNAHMEN = {
    ("_mobile_header.html", "<oben>", "runObjectSearch"): "Suche",
    ("_sidebar.html", "<oben>", "fetch"): "Anmeldestatus",
    ("_topbar.html", "<oben>", "runTopbarSearch"): "Suche",
    ("changelog.html", "<oben>", "load"): "nur Anzeige",
    ("checklist.html", "checkVersion", "api"): "Prüfung ohne Formular",
    ("checklist_order.html", "<oben>", "fetch"): "nur Anzeige",
    ("checklists.html", "init", "api"): "nur Anzeige",
    ("dashboard.html", "isModuleEnabled", "api"): "Prüfung ohne Formular",
    ("dashboard.html", "renderActiveProjectsWidget", "api"): "nur Anzeige",
    ("dashboard.html", "renderCriticalFindingsWidget", "api"): "nur Anzeige",
    ("dashboard.html", "renderDueAssetsWidget", "api"): "nur Anzeige",
    ("dashboard.html", "renderDueMaintenanceWidget", "api"): "nur Anzeige",
    ("dashboard.html", "renderKpisWidget", "api"): "nur Anzeige",
    ("email_dispatches.html", "checkArchive", "api"): "Prüfung ohne Formular",
    ("finanzen.html", "load", "api"): "nur Anzeige",
    ("findings.html", "init", "api"): "nur Anzeige",
    ("findings.html", "loadFindings", "api"): "nur Anzeige",
    ("history.html", "load", "api"): "nur Anzeige",
    ("mobil_objekt.html", "<oben>", "api"): "nur Anzeige",
    ("mobil_objekt.html", "<oben>", "fetch"): "nur Anzeige",
    ("operational_asset_field.html", "<oben>", "init"): "nur Anzeige",
    ("order.html", "loadOpenConcerns", "api"): "nur Anzeige",
    ("project_folder.html", "pmSearchNow", "api"): "Suche",
    ("property.html", "isModuleEnabled", "api"): "Prüfung ohne Formular",
    ("property.html", "loadAcceptanceWarranties", "api"): "nur Anzeige",
    ("roof_area.html", "isModuleEnabled", "api"): "Prüfung ohne Formular",
    ("roof_area.html", "loadAcceptanceWarranties", "api"): "nur Anzeige",
    ("roof_area.html", "toggleComponentFindings", "api"): "nur Anzeige",
    ("service_form.html", "searchMaterials", "api"): "Suche",
    ("tasks.html", "updateCreateProjectFromTaskButton", "api"): "Prüfung ohne Formular",
}

GRUENDE = {"nur Anzeige", "Suche", "Anmeldestatus", "Prüfung ohne Formular"}


def _alle_funde():
    funde = set()
    for name in vj.alle_vorlagen(TEMPLATES):  # seit 1.8.123 auch in Unterordnern
        if name == "_speichern.html":
            continue
        funde |= vj.anfragen_ausserhalb(vj.analysieren(vj.skript_der_vorlage(name)), name)
    return funde


def test_no_request_outside_the_baustein_beyond_the_known_exceptions():
    funde = _alle_funde()
    neu = sorted(funde - set(AUSNAHMEN))
    erledigt = sorted(set(AUSNAHMEN) - funde)
    assert not neu, ("Anfrage außerhalb von lesen()/speichern()/abschliessen() -- über den Baustein stellen (Regel 29):\n"
                     + "\n".join(f"{d}: {f}() -> {m}" for d, f, m in neu))
    assert not erledigt, ("Erledigt, bitte aus AUSNAHMEN streichen (die Liste darf nur kürzer werden):\n"
                          + "\n".join(f"{d}: {f}() -> {m}" for d, f, m in erledigt))


def test_every_exception_has_a_reason_that_is_no_form():
    assert set(AUSNAHMEN.values()) <= GRUENDE


@pytest.mark.parametrize("js, funde", [
    # direkt
    ("async function f(){const r=await fetch('/a');x=await r.json()}f()", {("beispiel", "<oben>", "f")}),  # f ist selbst ein Anfrage-Helfer
    # über einen Helfer, nur in lesen(): kein Fund
    ("async function api(u){const r=await fetch(u);return r.json()}async function f(){await lesen('x',()=>api('/a'),d=>{x=d})}f()", set()),
    # über einen Helfer außerhalb
    ("async function api(u){const r=await fetch(u);return r.json()}async function f(){x=await api('/a')}f()", {("beispiel", "f", "api")}),
    # Ladefunktion, die nur in lesen() steckt
    ("async function api(u){const r=await fetch(u);return r.json()}function hol(){return api('/a')}"
     "async function f(){await lesen('x',hol,d=>{x=d})}f()", set()),
    # dieselbe Ladefunktion auch direkt aufgerufen
    ("async function api(u){const r=await fetch(u);return r.json()}function hol(){return api('/a')}"
     "async function f(){await lesen('x',hol,d=>{x=d})}async function g(){x=await hol()}g()", {("beispiel", "hol", "api")}),
    # oben im Skript
    ("fetch('/api/auth/status').then(r=>r.json())", {("beispiel", "<oben>", "fetch")}),
])
def test_scanner_finds_requests_outside(js, funde):
    a = vj.analysieren(vj.Quelle("beispiel", js, [(0, len(js), "beispiel", 0)]))
    a.baustein = set()
    assert vj.anfragen_ausserhalb(a, None) == funde


def test_a_function_called_from_the_html_counts_as_outside():
    """Eine Ladefunktion, die nur ein onclick im Markup aufruft, ist nicht "nur im Baustein erreicht"."""
    js = "async function api(u){const r=await fetch(u);return r.json()}async function ladeMonat(){x=await api('/m')}"
    a = vj.analysieren(vj.Quelle("beispiel", js, [(0, len(js), "beispiel", 0)]))
    assert vj.anfragen_ausserhalb(a, None, html='<button onclick="ladeMonat()">') == {("beispiel", "ladeMonat", "api")}


@pytest.mark.parametrize("html, funde", [
    ('<button onclick="api(\'/x\',{method:\'DELETE\'})">x</button>', {(None, "<html>", "api")}),
    ('<button onclick="fetch(\'/x\')">x</button>', {(None, "<html>", "fetch")}),
    ("el.innerHTML=`<a onclick=\"api('/x/${id}')\">x</a>`", {(None, "<html>", "api")}),
    ('<button onclick="zeige(1)">x</button>', set()),
])
def test_a_direct_call_from_the_html_is_reported(html, funde):
    """Seit 1.8.99 (Festlegung 1.8.97 Nr. 1, korrigiert): auch ein direkter Aufruf von api() oder fetch() aus einem on…-Attribut --
    im Markup oder in einem Template-Literal -- ist eine Anfrage außerhalb von lesen()/speichern()/abschliessen(). Bis 1.8.98 sah der
    Scanner nur die Skripte."""
    js = "const api=async(u,o)=>{const r=await fetch(u,o);return r.json()};function zeige(n){x=n}lesen('b',()=>api('/y'),zeige);"
    a = vj.analysieren(vj.Quelle("beispiel", js, [(0, len(js), "beispiel", 0)]))
    assert vj.anfragen_ausserhalb(a, None, html=html) == funde


# --- Die ausdrücklich verlangten Stellen ------------------------------------------------------------------------------------

from tests.test_v399_teil_updates_geld import _speichern_js, js_funktion  # noqa: E402

# Gestelltes fetch mit zurückgehaltenen Antworten: antworte(url, daten) beantwortet die offene Anfrage auf url.
VERZOEGERT = r"""
var window = globalThis;
var LOG = [];
var OFFEN = {};
globalThis.fetch = (url, opt = {}) => {
  LOG.push('fetch ' + url);
  return new Promise(res => { OFFEN[url] = res; });
};
async function antworte(url, daten, kopf = {}) {
  if (!OFFEN[url]) throw new Error('keine offene Anfrage ' + url);
  const res = OFFEN[url]; delete OFFEN[url];
  res({ok: true, status: 200, statusText: 'OK', headers: {get: k => kopf[k] ?? null}, json: async () => daten});
  await ruhe();
}
const ruhe = async () => { for (let i = 0; i < 10; i++) await new Promise(r => setTimeout(r, 0)); };
async function api(url, opt = {}) { const r = await fetch(url, opt); return r.json(); }
const _el = {};
var document = {
  getElementById: id => _el[id] || (_el[id] = {id, value: '', textContent: '', innerHTML: '', className: '', hidden: false,
    href: '', checked: false, style: {}, dataset: {}, classList: {add() {}, remove() {}, toggle() {}}}),
  querySelectorAll: () => [], querySelector: () => null,
};
"""


def _ausfuehren(vorlage: str, funktionen: list[str], vorbereitung: str, ablauf: str) -> list:
    from tests.test_v314_dashboard_month_berlin import _node
    js = (VERZOEGERT + _speichern_js() + "\n" + vorbereitung + "\n"
          + "\n".join(js_funktion(vorlage, n) for n in funktionen)
          + f"\n(async () => {{ {ablauf}\n }})().then(() => process.stdout.write(JSON.stringify(LOG), () => process.exit(0)))"
          ".catch(e => { console.error(e && e.stack || e); process.exit(1); });")
    return _node(js, "Europe/Berlin")


@nur_mit_node
def test_email_templates_the_last_chosen_type_wins():
    """Rechnung gewählt (Antwort hängt), dann Mahnstufe 1: die späte Antwort der Rechnung überschreibt die Felder der Mahnstufe nicht
    mehr -- bis 1.8.96 setzte die Mahnstufe die Felder sofort aus dem gemerkten Stand, die Rechnung kam danach und gewann."""
    log = _ausfuehren("settings.html", ["loadEmailTemplate"], """
        const setv=(id,x)=>document.getElementById(id).value=x??'';
        const EMAIL_TEMPLATE_PLACEHOLDER_HINTS={};
        let reminderLevels=[{id:1,level:1,email_subject_template:'gemerkt',email_body_template:'gemerkt'}];
    """, """
        document.getElementById('emailTemplateType').value='invoice'; const a=loadEmailTemplate(); await ruhe();
        document.getElementById('emailTemplateType').value='reminder:1'; const b=loadEmailTemplate(); await ruhe();
        await antworte('/api/reminder-levels',[{id:1,level:1,email_subject_template:'Mahnung frisch',email_body_template:'Text frisch'}]);
        await antworte('/api/document-email-templates/invoice',{subject_template:'Rechnung',body_template:'Rechnungstext'});
        await a; await b;
        LOG.push(document.getElementById('emailTemplateSubject').value+' | '+document.getElementById('emailTemplateBody').value);
    """)
    assert log == ["fetch /api/document-email-templates/invoice", "fetch /api/reminder-levels", "Mahnung frisch | Text frisch"]


def test_email_template_of_a_reminder_level_is_saved_in_the_form_area():
    """Das Speichern der Mahnstufe läuft im Bereich des Formulars -- ein Wechsel der Art danach liest erst nach dem Speichern."""
    rumpf = js_funktion("settings.html", "saveEmailTemplate")
    assert "speichern('emailvorlagen', () => api(`/api/reminder-levels/${rl.id}`" in rumpf
    assert "speichern('mahnstufen'" not in rumpf


@nur_mit_node
def test_roof_type_change_the_last_chosen_type_wins():
    """Dachtyp A gewählt (Antwort hängt), dann B: die späte Antwort von A zeichnet die Schichten nicht über B; ebenso nach einem
    Wechsel auf "keine Auswahl"."""
    vorbereitung = """
        const roofAreaId=7; let layerTypesForRoofType=[], existingLayers=[], layerOptionGroupsCache={};
        function auswahlEintraege(t){return t}
        async function safeOptionGroup(k){return {options:[]}}
        function renderLayerRows(){LOG.push('gezeichnet '+layerTypesForRoofType.map(t=>t.key).join(','))}
    """
    log = _ausfuehren("roof_area.html", ["currentRoofTypeSelection", "loadLayers"], vorbereitung, """
        const sel=document.getElementById('editRoofType');
        sel.value='steildach'; const a=loadLayers(); await ruhe();
        const ersteSchichten=OFFEN['/api/roof-areas/7/layers'];
        sel.value='flachdach'; const b=loadLayers(); await ruhe();
        await antworte('/api/roof-areas/7/layers',[]);
        await antworte('/api/roof-layer-types?roof_type=flachdach&include_inactive=true',[{key:'flach'}]);
        OFFEN['/api/roof-areas/7/layers']=ersteSchichten; await antworte('/api/roof-areas/7/layers',[]);
        await antworte('/api/roof-layer-types?roof_type=steildach&include_inactive=true',[{key:'steil'}]);
        await a; await b;
        LOG.push('am Ende '+layerTypesForRoofType.map(t=>t.key).join(','));
        sel.value='steildach'; const c=loadLayers(); await ruhe();
        sel.value=''; await loadLayers();
        await antworte('/api/roof-areas/7/layers',[]);
        await antworte('/api/roof-layer-types?roof_type=steildach&include_inactive=true',[{key:'steil'}]);
        await c;
        LOG.push('ohne Dachtyp '+layerTypesForRoofType.map(t=>t.key).join(',')+'|'+document.getElementById('layerTypeHint').textContent);
    """)
    gezeichnet = [x for x in log if x.startswith(("gezeichnet", "am Ende", "ohne"))]
    assert gezeichnet == ["gezeichnet flach", "am Ende flach", "ohne Dachtyp flach|Bitte zuerst oben einen Dachtyp wählen."]


@nur_mit_node
def test_meine_zeiten_month_change_the_last_chosen_month_wins():
    """„Meine Zeiten“ (seit 1.9.59, bis dahin der Stundenzettel): September gewählt (Antwort hängt), dann Oktober -- die späte Antwort
    für September überschreibt Oktober nicht."""
    log = _ausfuehren("mobil_zeiten.html", ["laden"], """
        let D=null,MONAT=null,VORWAHL=null;const KEIN_MITARBEITER='';  // VORWAHL seit 1.9.86 (laden() schickt die Vorwahl mit)
        async function api(url){const r=await fetch(url);return r.json()}
        function ladeHinweis(){}
        function zeichnen(d){LOG.push('gezeichnet '+d.monat)}
    """, """
        MONAT='2026-09'; const a=laden(); await ruhe(); MONAT='2026-10'; const b=laden(); await ruhe();
        await antworte('/api/field-view/meine-zeiten?monat=2026-10',{monat:'2026-10'});
        await antworte('/api/field-view/meine-zeiten?monat=2026-09',{monat:'2026-09'});
        await a; await b;
        LOG.push('Monat '+MONAT);
    """)
    assert [x for x in log if not x.startswith("fetch")] == ["gezeichnet 2026-10", "Monat 2026-10"]


def test_customer_documents_are_set_only_in_their_own_area():
    """Die Kundenakte lädt die Dokumente nur noch im Bereich 'dokumente' (bis 1.8.96 auch in load(), Bereich 'kunde')."""
    text = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    load = js_funktion("customer.html", "load")
    assert "/documents" not in load and "loadDocuments()" in load
    zuweisungen = re.findall(r"customerDocuments\s*=(?!=)", text)
    assert len(zuweisungen) == 2  # Deklaration und loadDocuments()
    assert "lesen('dokumente',()=>api(`/api/customers/${customerId}/documents`),d=>{customerDocuments=d;" in text


def test_checklist_template_keeps_template_and_version_in_one_area():
    """Vorlage und Fassung setzen beide den Stand der Fassung (version) -- ein Bereich, nicht zwei."""
    a = vj.analysieren(vj.eigene_skripte("checklist_template.html"))
    bereiche = {a.t[a.argumente(auf)[0][0]].wert for auf, n in a.aufrufe() if n in ("speichern", "lesen", "abschliessen")
                and not a.ist_methode(auf)}
    assert bereiche == {"vorlage", "fassungsansicht"}


@nur_mit_node
def test_quote_editor_calculation_and_list_reload_do_not_discard_each_other():
    """Gefunden beim Umbau (Gruppe A): im selben Bereich 'angebot' verwarfen sich das Laden der Kalkulation beim Öffnen einer Position
    und das Neuladen des LV -- das Kalkulationsfeld blieb zu. Seit 1.8.97 eigener Bereich 'kalkulation'. Und: Position A mit
    Kalkulation geöffnet, dann schnell B ohne -- die späte Kalkulation von A wird verworfen, statt bei B angezeigt zu werden."""
    vorbereitung = """
        const quoteId=3; let quote={items:[{id:1,has_project_calculation:true},{id:2,has_project_calculation:false}]};
        let currentItem=null,currentCalc=null;
        function fillItemEditor(){} function showEditMode(){} function renderAll(){LOG.push('LV gezeichnet '+quote.stand)}
        function fillCalc(){LOG.push('Kalkulation von '+currentItem.id+': '+currentCalc.wer)}
    """
    log = _ausfuehren("quote_editor.html", ["reloadQuote", "editItem"], vorbereitung, """
        const a=editItem(1); await ruhe(); const r=reloadQuote(); await ruhe();
        await antworte('/api/quotes/3',{items:quote.items,stand:'neu'});
        await antworte('/api/quotes/3/items/1/calculation',{wer:'A'});
        await a; await r;
        const b=editItem(1); await ruhe(); const c=editItem(2); await ruhe();
        await antworte('/api/quotes/3/items/1/calculation',{wer:'A spät'});
        await b; await c;
        LOG.push('am Ende bei '+currentItem.id+': '+(currentCalc?currentCalc.wer:'keine Kalkulation'));
    """)
    assert [x for x in log if not x.startswith("fetch")] == ["LV gezeichnet neu", "Kalkulation von 1: A", "am Ende bei 2: keine Kalkulation"]


# --- Doppelklick: dieselbe Anfrage nicht zweimal (gefunden mit klicktest_anmelden) ---------------------------------------------

@nur_mit_node
def test_the_same_request_while_the_first_is_pending_goes_out_once():
    """Doppelklick auf "Anmelden": bis 1.8.96 reihte der Baustein die zweite, gleiche Anfrage ein; seit 1.8.96 hielt sie nach der
    Weiterleitung der ersten die Warnung beim Verlassen auf. Jetzt bekommt sie das Ergebnis der ersten, ohne zu senden oder zu warten."""
    from tests.test_v398_speichern_baustein import _ablauf as ablauf
    log = ablauf("""
        const a=speichern('anmeldung',()=>fetch('/login',{method:'POST',body:'{"u":"bea"}'}),{anwenden:anwenden()});
        const b=speichern('anmeldung',()=>fetch('/login',{method:'POST',body:'{"u":"bea"}'}),{anwenden:anwenden()});
        await ruhe(); log.push('wartend '+window.__dkSpeichern.size);
        await antworte('/login',{ok:true,stand:'angemeldet'});
        log.push('a '+JSON.stringify(await a)); log.push('b '+JSON.stringify(await b));
    """)
    assert log == ["gesendet /login", "wartend 1", 'angewandt {"ok":true,"stand":"angemeldet"}',
                   'a {"ok":true,"stand":"angemeldet"}', 'b {"ok":true,"stand":"angemeldet"}']


@nur_mit_node
def test_a_different_body_or_a_file_is_not_the_same_request():
    from tests.test_v398_speichern_baustein import _ablauf as ablauf
    log = ablauf("""
        speichern('feld',()=>fetch('/x',{method:'PUT',body:'1'})); speichern('feld',()=>fetch('/x',{method:'PUT',body:'2'}));
        const fd=new FormData(); speichern('foto',()=>fetch('/f',{method:'POST',body:fd})); speichern('foto',()=>fetch('/f',{method:'POST',body:fd}));
        await ruhe(); await antworte('/x'); await antworte('/f'); await antworte('/x'); await antworte('/f');
    """)
    assert log == ["gesendet /x", "gesendet /f", "gesendet /x", "gesendet /f"]


@nur_mit_node
def test_the_same_request_after_the_first_answer_goes_out_again():
    from tests.test_v398_speichern_baustein import _ablauf as ablauf
    log = ablauf("""
        const a=speichern('feld',anfrage('S1')); await ruhe(); await antworte('S1'); await a;
        const b=speichern('feld',anfrage('S1')); await ruhe(); await antworte('S1'); await b;
    """)
    assert log == ["gesendet S1", "gesendet S1"]


@nur_mit_node
def test_a_duplicate_gets_its_own_readable_fetch_answer_and_shares_a_failure():
    from tests.test_v398_speichern_baustein import _ablauf as ablauf
    log = ablauf("""
        const a=speichern('anmeldung',()=>fetch('/login',{method:'POST',body:'x'}));
        const b=speichern('anmeldung',()=>fetch('/login',{method:'POST',body:'x'}));
        await ruhe(); await antworte('/login',new Response('{"role":"field"}',{status:200}));
        log.push('a '+JSON.stringify(await (await a).json())); log.push('b '+JSON.stringify(await (await b).json()));
        const c=speichern('feld',anfrage('S1')).catch(e=>'c '+e.message), d=speichern('feld',anfrage('S1')).catch(e=>'d '+e.message);
        await ruhe(); await scheitere('S1'); log.push(await c); log.push(await d);
    """)
    assert log == ["gesendet /login", 'a {"role":"field"}', 'b {"role":"field"}', "gesendet S1", "c kaputt S1", "d kaputt S1"]


@nur_mit_node
def test_a_final_action_clicked_twice_runs_once():
    from tests.test_v398_speichern_baustein import _ablauf as ablauf
    log = ablauf("""
        const a=abschliessen('rechnung',()=>fetch('/send',{method:'POST'})), b=abschliessen('rechnung',()=>fetch('/send',{method:'POST'}));
        await ruhe(); await antworte('/send'); await a; await b;
    """)
    assert log == ["gesendet /send"]
