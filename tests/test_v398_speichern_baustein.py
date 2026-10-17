"""Version 1.8.95 -- gemeinsamer Baustein gegen veraltete Antworten (app/templates/_speichern.html; Vorgabe 1.8.95 Punkt 1,
Nebenbefunde 1 und 3 aus 1.8.94).

Bis 1.8.94 übernahm eine Seite jede Antwort in der Reihenfolge, in der sie ankam: lief ein Speichern parallel zu einem zweiten (oder
das Neuladen nach dem ersten parallel zum Neuladen nach dem zweiten) und kam die früher berechnete Antwort später an, stand der alte
Stand wieder da (Checkliste: "Vor der Unterschrift fehlen noch: …" trotz gespeicherter Kachel). Und viele Seiten setzten "Gespeichert."
vor dem Neuladen. Seit 1.8.95 läuft jedes Speichern über speichern(bereich, ()=>api(…), {anwenden | neuLaden}) und jedes Neuladen
danach über lesen(bereich, anfrage, anwenden): je Bereich eine laufende Nummer beim Absenden, angewandt wird nur, was nicht älter ist
als das schon Angewandte; Speichern geht je Bereich nacheinander hinaus, Lesen erst, wenn kein Speichern mehr unterwegs ist.

Hier:
- der Baustein in node mit gestellten Anfragen (Reihenfolge, Verwerfen, nacheinander, Fehler, Rückkehr erst nach dem Neuladen);
- der Strukturtest je Vorlage (tests/vorlagen_js.py): jede schreibende Anfrage (method ungleich GET) ist der ganze Rumpf eines Pfeils,
  der als zweites Argument an ein awaitetes speichern() geht; was nach einem Speichern noch läuft (Aufrufe, anwenden, neuLaden, auch
  über andere Funktionen der Seite), fragt nur über lesen()/speichern() an; "Gespeichert" steht nur hinter einem awaiteten
  Speichern; wer den Baustein nutzt, bindet ihn ein;
- der Scanner selbst an kleinen Beispielen (sonst bliebe ein blinder Scanner grün);
- jedes Skript jeder gerenderten Seite (als Büro und als Monteur) ist gültiges JavaScript -- der Umbau fasst fast alle Vorlagen an."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests import vorlagen_js as vj
from tests.test_v314_dashboard_month_berlin import NODE, _node

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
BAUSTEIN = TEMPLATES / "_speichern.html"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


def _baustein_js() -> str:
    return re.search(r"<script>(.*?)</script>", BAUSTEIN.read_text(encoding="utf-8"), flags=re.S).group(1)


def _ablauf(schritte: str, *, baustein_zweimal: bool = False, zeitlimit: int | None = None, vorspann: str = "") -> list:
    """Führt den Baustein in node aus. Gestelltes fetch(name[, init]): protokolliert 'gesendet name', wenn die Anfrage wirklich
    hinausgeht, und legt eine offene Antwort an (ein Abbruch über init.signal protokolliert 'abgebrochen name' und lehnt sie ab);
    antworte(name[, antwort])/scheitere(name) beantworten sie. anfrage(name, daten) -> Pfeil für lesen()/speichern() über
    fetch(name), Ergebnis daten (Vorgabe name). anwenden() protokolliert 'angewandt <daten>'; console.error landet als 'fehler: …'
    im Protokoll; log.push(...) für eigene Marken. zeitlimit (seit 1.8.96): window.__dkZeitlimit in ms vor dem Baustein;
    vorspann: Skript vor dem Baustein (z. B. ein gestelltes window.addEventListener). Am Ende beendet sich node sofort -- ein
    offener Zeitlimit-Timer hielte es sonst bis zu 60 s am Leben."""
    js = _baustein_js()
    script = "\n".join([
        "const window=globalThis;",
        f"window.__dkZeitlimit={int(zeitlimit)};" if zeitlimit else "",
        vorspann,
        js, js if baustein_zweimal else "",
        "const log=[];const offen={};console.error=m=>log.push('fehler: '+m);",
        "const ruhe=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setTimeout(r,0))};",
        "const warte=ms=>new Promise(r=>setTimeout(r,ms));",
        "globalThis.fetch=(name,init)=>{log.push('gesendet '+name);return new Promise((res,rej)=>{offen[name]={res,rej};"
        "if(init&&init.signal)init.signal.addEventListener('abort',()=>{log.push('abgebrochen '+name);rej(new Error('abgebrochen'))})})};",
        "function anfrage(name,daten){return ()=>fetch(name).then(()=>daten===undefined?name:daten)}",
        "async function antworte(name,antwort){offen[name].res(antwort===undefined?{ok:true}:antwort);await ruhe()}",
        "async function scheitere(name){offen[name].rej(new Error('kaputt '+name));await ruhe()}",
        "const anwenden=()=>d=>{log.push('angewandt '+JSON.stringify(d))};",
        f"(async()=>{{{schritte}\nawait ruhe();process.stdout.write(JSON.stringify(log),()=>process.exit(0))}})()"
        ".catch(e=>{console.error(e);process.exit(1)})",
    ])
    return _node(script, "Europe/Berlin")


# --- Der Baustein ----------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_an_older_read_arriving_after_a_newer_one_is_discarded():
    log = _ablauf("""
        const a=lesen('liste',anfrage('L1','alt'),anwenden());
        const b=lesen('liste',anfrage('L2','neu'),anwenden());
        await ruhe();
        await antworte('L2'); await antworte('L1');
        log.push('ergebnis '+JSON.stringify([await a,await b]));
    """)
    assert log == ["gesendet L1", "gesendet L2", 'angewandt "neu"', "ergebnis [false,true]"]


@nur_mit_node
def test_reads_arriving_in_order_are_both_applied():
    log = _ablauf("""
        lesen('liste',anfrage('L1','eins'),anwenden()); lesen('liste',anfrage('L2','zwei'),anwenden());
        await ruhe(); await antworte('L1'); await antworte('L2');
    """)
    assert log == ["gesendet L1", "gesendet L2", 'angewandt "eins"', 'angewandt "zwei"']


@nur_mit_node
def test_other_areas_do_not_discard_each_other():
    log = _ablauf("""
        lesen('a',anfrage('A','a'),anwenden()); lesen('b',anfrage('B','b'),anwenden());
        await ruhe(); await antworte('B'); await antworte('A');
    """)
    assert log == ["gesendet A", "gesendet B", 'angewandt "b"', 'angewandt "a"']


@nur_mit_node
def test_saves_in_one_area_go_out_one_after_another():
    log = _ablauf("""
        const s1=speichern('form',anfrage('S1')); const s2=speichern('form',anfrage('S2'));
        await ruhe(); log.push('-'); await antworte('S1'); await antworte('S2'); await s1; await s2;
    """)
    assert log == ["gesendet S1", "-", "gesendet S2"]


@nur_mit_node
def test_saves_in_different_areas_go_out_together():
    log = _ablauf("""
        speichern('a',anfrage('S1')); speichern('b',anfrage('S2'));
        await ruhe(); log.push('-'); await antworte('S2'); await antworte('S1');
    """)
    assert log == ["gesendet S1", "gesendet S2", "-"]


@nur_mit_node
def test_a_read_waits_for_a_save_of_its_area_only():
    log = _ablauf("""
        speichern('form',anfrage('S1')); await ruhe();
        lesen('form',anfrage('L1','neu'),anwenden()); lesen('anders',anfrage('M1','m'),anwenden()); await ruhe();
        log.push('-'); await antworte('S1'); await antworte('L1'); await antworte('M1');
    """)
    assert log == ["gesendet S1", "gesendet M1", "-", "gesendet L1", 'angewandt "neu"', 'angewandt "m"']


@nur_mit_node
def test_a_read_sent_before_a_save_does_not_overwrite_the_save_response():
    """Die Antwort eines Speicherns trägt den Stand (anwenden): ein vorher abgeschicktes Lesen, das danach ankommt, ist älter."""
    log = _ablauf("""
        const l=lesen('cl',anfrage('L1','alt'),anwenden()); await ruhe();
        const s=speichern('cl',anfrage('S1','neu'),{anwenden:anwenden()}); await ruhe();
        await antworte('S1'); await antworte('L1');
        log.push('lesen '+(await l));
    """)
    assert log == ["gesendet L1", "gesendet S1", 'angewandt "neu"', "lesen false"]


@nur_mit_node
def test_speichern_returns_after_the_reload_is_applied():
    """Erst danach darf "Gespeichert." erscheinen (Nebenbefund 3 aus 1.8.94)."""
    log = _ablauf("""
        const neuLaden=()=>lesen('form',anfrage('L1','frisch'),anwenden());
        const s=speichern('form',anfrage('S1'),{neuLaden}).then(()=>log.push('Gespeichert.'));
        await ruhe(); await antworte('S1'); log.push('-'); await antworte('L1'); await s;
    """)
    assert log == ["gesendet S1", "gesendet L1", "-", 'angewandt "frisch"', "Gespeichert."]


@nur_mit_node
def test_two_saves_with_reloads_end_on_the_newest_state():
    """Zwei Speichern mit Neuladen: das Neuladen nach dem ersten wartet, bis auch das zweite gespeichert ist; was zuletzt angewandt
    ist, kennt beide. Ein spät ankommendes älteres Neuladen wird verworfen."""
    log = _ablauf("""
        let server=0;
        const schreibe=n=>()=>fetch(n).then(()=>{server++;return n});
        const liesStand=n=>()=>{const p=fetch(n),stand=server;return p.then(()=>'Stand '+stand)};
        const s1=speichern('form',schreibe('S1'),{neuLaden:()=>lesen('form',liesStand('L1'),anwenden())}).then(()=>log.push('fertig S1'));
        const s2=speichern('form',schreibe('S2'),{neuLaden:()=>lesen('form',liesStand('L2'),anwenden())}).then(()=>log.push('fertig S2'));
        await ruhe(); await antworte('S1'); await antworte('S2');
        await antworte('L1'); await antworte('L2'); await s1; await s2;
    """)
    assert log[:4] == ["gesendet S1", "gesendet S2", "gesendet L2", "gesendet L1"]
    angewandt = [x for x in log if x.startswith("angewandt")]
    assert angewandt == ['angewandt "Stand 2"']  # L1 (später abgeschickt) zuerst angewandt, L2 danach verworfen
    assert log.index("fertig S1") > log.index('angewandt "Stand 2"')


@nur_mit_node
def test_a_failed_save_applies_nothing_and_does_not_block_the_next():
    log = _ablauf("""
        const s1=speichern('form',anfrage('S1'),{anwenden:anwenden(),neuLaden:()=>log.push('neu geladen')}).then(()=>'kein',e=>e.message);
        const s2=speichern('form',anfrage('S2'),{anwenden:anwenden()});
        await ruhe(); await scheitere('S1');
        log.push('fehler '+(await s1));
        await antworte('S2'); await s2;
    """)
    assert log == ["gesendet S1", "gesendet S2", "fehler kaputt S1", 'angewandt "S2"']


@nur_mit_node
def test_a_fetch_response_with_error_status_is_returned_without_applying():
    log = _ablauf("""
        const s=speichern('form',()=>fetch('R1'),{anwenden:anwenden(),neuLaden:()=>log.push('neu geladen')});
        await ruhe(); await antworte('R1',new Response('{"detail":"nein"}',{status:409}));
        log.push('status '+(await s).status);
        const s2=speichern('form',()=>fetch('R2'),{neuLaden:()=>log.push('neu geladen')});
        await ruhe(); await antworte('R2',new Response('{}',{status:200}));
        log.push('status '+(await s2).status);
    """)
    assert log == ["gesendet R1", "status 409", "gesendet R2", "neu geladen", "status 200"]


@nur_mit_node
def test_the_checklist_case_keeps_both_answers():
    """Nebenbefund 1 aus 1.8.94: Feld per blur, sofort danach eine Kachel; die Antwort des Felds kommt spät. Der Server antwortet mit
    allen Antworten -- mit dem Baustein geht die Kachel erst nach der Antwort des Felds hinaus, am Ende stehen beide."""
    log = _ablauf("""
        let server={};
        const sende=(feld,wert)=>()=>fetch(feld).then(()=>{server={...server,[feld]:wert};return {...server}});
        let antworten={};
        const ueb=d=>{antworten=d};
        const a=speichern('checkliste',sende('A','Text'),{anwenden:ueb});
        const b=speichern('checkliste',sende('B','ja'),{anwenden:ueb});
        // Der Server bearbeitet eine Anfrage, wenn er sie beantwortet. Ist B schon bei ihm (ohne "nacheinander"), kommt B zuerst
        // dran -- wie bei zwei Arbeitsprozessen -- und die Antwort von A, die beides kennt, wäre die ältere.
        await ruhe(); const bSchonDa='B' in offen;
        if(bSchonDa)await antworte('B');
        await antworte('A');
        if(!bSchonDa)await antworte('B');
        await a; await b;
        log.push(JSON.stringify(antworten));
    """)
    assert log == ["gesendet A", "gesendet B", '{"A":"Text","B":"ja"}']


@nur_mit_node
def test_a_waiting_save_is_built_when_called_not_when_sent():
    """Wartet ein Speichern auf das vorige, sendet es trotzdem die Werte vom Klick -- nicht ein Formular, das die Antwort des
    vorigen inzwischen neu gezeichnet hat (gemeldet beim Umbau der Arbeitsvorbereitung)."""
    log = _ablauf("""
        let feld='beim Klick';
        const s1=speichern('form',anfrage('S1'),{anwenden:()=>{feld='vom Server neu gezeichnet'}});
        const s2=speichern('form',()=>fetch('S2 '+feld));
        await ruhe(); log.push('-'); await antworte('S1'); await s1;
    """)
    assert log == ["gesendet S1", "-", "gesendet S2 beim Klick"]


@nur_mit_node
def test_an_anfrage_that_does_not_reach_fetch_at_once_is_reported():
    log = _ablauf("""
        const s=speichern('form',async()=>{await null;return fetch('S1')});
        await ruhe(); await antworte('S1'); await s;
    """)
    assert len(log) == 2 and log[0].startswith("fehler: speichern('form'): die Anfrage ging nicht sofort über fetch()")
    assert log[1] == "gesendet S1"


@nur_mit_node
def test_an_anfrage_that_throws_at_once_rejects_and_frees_the_area():
    log = _ablauf("""
        const s1=speichern('form',()=>{throw new Error('kein Formular')}).then(()=>'kein',e=>e.message);
        const s2=speichern('form',anfrage('S2'),{anwenden:anwenden()});
        log.push('fehler '+(await s1)); await ruhe(); await antworte('S2'); await s2;
    """)
    assert log == ["gesendet S2", "fehler kein Formular", 'angewandt "S2"']


@nur_mit_node
def test_the_baustein_may_be_included_twice_and_shares_its_state():
    log = _ablauf("""
        const a=lesen('liste',anfrage('L1','alt'),anwenden()); const b=lesen('liste',anfrage('L2','neu'),anwenden());
        await ruhe(); await antworte('L2'); await antworte('L1');
        log.push(String(window.__dkBereiche.size));
    """, baustein_zweimal=True)
    assert log == ["gesendet L1", "gesendet L2", 'angewandt "neu"', "1"]


# --- Strukturtest je Vorlage ---------------------------------------------------------------------------------------------

VORLAGEN = vj.alle_vorlagen(TEMPLATES)  # seit 1.8.123 auch in Unterordnern


def _analyse(name):
    return vj.analysieren(vj.skript_der_vorlage(name))


@pytest.mark.parametrize("name", VORLAGEN)
def test_every_write_request_goes_through_speichern(name):
    a = _analyse(name)
    offen = [f"{a.stelle(s.index)}: {s.grund}" for s in vj.schreibstellen(a) if not s.ok]
    assert not offen, ("Schreibende Anfrage nicht über den Baustein -- erwartet `await speichern('<bereich>', ()=>api(url, "
                       "{method: …}), {anwenden | neuLaden})` (app/templates/_speichern.html):\n" + "\n".join(offen))


@pytest.mark.parametrize("name", VORLAGEN)
def test_after_saving_the_page_reads_only_through_the_baustein(name):
    a = _analyse(name)
    offen = sorted({f"{a.stelle(k)}: {weg}" for k, weg in vj.nach_dem_speichern(a)})
    assert not offen, ("Nach einem Speichern fragt die Seite ohne lesen()/speichern() an -- eine solche Antwort könnte älter "
                       "sein als eine schon angewandte:\n" + "\n".join(offen))


def _gespeichert_stellen(a):
    """(Token-Index, Grund) je "Gespeichert" in einem String, das nicht hinter einem awaiteten Speichern derselben Funktion steht."""
    schreib_memo, out = {}, []
    rumpfe = [(s, e, n) for n, liste in a.funktionen.items() for s, e in liste]
    for k, tok in enumerate(a.t):
        if tok.art not in ("str", "tpl") or "Gespeichert" not in tok.wert:
            continue
        umgebend = [(s, e, n) for s, e, n in rumpfe if s <= k <= e]
        if not umgebend:
            out.append((k, "außerhalb einer Funktion"))
            continue
        s, e, n = min(umgebend, key=lambda x: x[1] - x[0])
        davor = [auf for auf, name in a.aufrufe() if s <= auf < k and not a.ist_methode(auf)
                 and (name in vj.SCHREIBEND or (name in a.funktionen and name != n and vj._schreibt(a, name, schreib_memo)))
                 and a.partner[auf] < k and vj.abgewartet(a, auf)]
        if not davor:
            out.append((k, f"in {n}() ohne awaitetes speichern() davor"))
    return out


@pytest.mark.parametrize("name", VORLAGEN)
def test_gespeichert_only_after_an_awaited_save(name):
    a = _analyse(name)
    offen = [f"{a.stelle(k)}: {grund}" for k, grund in _gespeichert_stellen(a)]
    assert not offen, '"Gespeichert" vor dem Anwenden -- es gehört hinter `await speichern(…)`:\n' + "\n".join(offen)


def _nutzt_den_baustein(name) -> bool:
    a = vj.analysieren(vj.eigene_skripte(name))
    return any(not a.ist_methode(auf) for auf, _ in a.aufrufe() if a.t[auf - 1].wert in vj.GEPRUEFT_RUFE)


def _bindet_den_baustein_ein(name) -> bool:
    """Die Vorlage selbst bindet _speichern.html ein (seit 1.8.125 über vj.bindet_ein(), nicht per Textvergleich)."""
    return vj.bindet_ein(name, BAUSTEIN.name, TEMPLATES, nur_selbst=True)


@pytest.mark.parametrize("name", VORLAGEN)
def test_templates_using_the_baustein_include_it(name):
    """Wer in den eigenen Skripten lesen()/speichern() aufruft, bindet den Baustein selbst ein (er darf mehrfach eingebunden
    sein); wer ihn nicht selbst nutzt, bindet ihn nicht ein -- dafür sorgen die Teilvorlagen, die ihn brauchen. Seit 1.8.123
    genügt das Include im Basis-Template der Seite; ein Basis-Template darf ihn für eine Seite einbinden, die von ihm erbt und ihn
    nutzt."""
    if name == BAUSTEIN.name:
        return
    nutzt = _nutzt_den_baustein(name)
    if nutzt:
        assert vj.bindet_ein(name, BAUSTEIN.name, TEMPLATES), (
            f"{name} nutzt lesen()/speichern(), bindet _speichern.html aber weder selbst noch über ein Basis-Template ein")
    elif _bindet_den_baustein_ein(name):
        erben = [v for v in vj.alle_vorlagen(TEMPLATES) if name in vj.basis_kette(v, TEMPLATES)]
        assert any(_nutzt_den_baustein(v) for v in erben), (
            f"{name} bindet _speichern.html ein, nutzt es aber selbst nicht" + (" (und keine Vorlage, die von ihm erbt)" if erben else ""))


def test_every_template_is_scanned():
    """Der Scanner liest jede Vorlage (ein Lesefehler ließe den Strukturtest leer laufen) und findet die Schreibstellen."""
    gesamt = 0
    for name in VORLAGEN:
        gesamt += len(vj.schreibstellen(_analyse(name)))
    assert gesamt > 400


# --- Der Scanner an Beispielen ---------------------------------------------------------------------------------------------

def _beispiel(js: str) -> vj.Analyse:
    return vj.analysieren(vj.Quelle("beispiel", js, [(0, len(js), "beispiel", 0)]))


@pytest.mark.parametrize("js, ok", [
    ("async function f(){await speichern('x',()=>api('/a',{method:'PUT'}),{neuLaden:g})}", True),
    ("async function f(){return speichern('x',()=>fetch('/a',{method:'POST',body:fd}))}", True),
    ("async function f(){await api('/a',{method:'PUT'})}", False),
    ("async function f(){speichern('x',()=>api('/a',{method:'PUT'}))}", False),                 # ohne await
    ("async function f(){await speichern('x',()=>api('/a',{method:'PUT'}).then(r=>r))}", False),  # mehr als die Anfrage
    ("async function f(){await speichern('x',async()=>api('/a',{method:'PUT'}))}", False),
    ("async function f(){await speichern(()=>api('/a',{method:'PUT'}))}", False),               # Pfeil als erstes Argument
    ("async function f(){const o={method:'POST'};await speichern('x',()=>fetch('/a',o))}", False),
    ("async function f(m){await speichern('x',()=>api('/a',{method:m}))}", True),
    ("async function f(method){await api('/a',{method})}", False),                              # Kurzform
    ("async function f(){await lesen('x',()=>api('/a',{method:'GET'}),g)}", None),               # GET zählt nicht
    ("async function f(){await x.api('/a',{method:'DELETE'})}", False),
])
def test_scanner_finds_write_requests(js, ok):
    stellen = vj.schreibstellen(_beispiel(js))
    if ok is None:
        assert stellen == []
    else:
        assert len(stellen) == 1 and stellen[0].ok is ok, [s.grund for s in stellen]


@pytest.mark.parametrize("js, funde", [
    # ungeprüftes Neuladen direkt danach
    ("async function f(){await speichern('x',()=>api('/a',{method:'PUT'}));rows=await api('/b');render()}", 1),
    # über eine Funktion der Seite
    ("async function load(){rows=await api('/b')}async function f(){await speichern('x',()=>api('/a',{method:'PUT'}));await load()}", 1),
    # als neuLaden übergeben
    ("async function load(){rows=await api('/b')}async function f(){await speichern('x',()=>api('/a',{method:'PUT'}),{neuLaden:load})}", 1),
    # in anwenden über render()
    ("function render(){loadSub()}async function loadSub(){await fetch('/s')}"
     "async function f(){await speichern('x',()=>api('/a',{method:'PUT'}),{anwenden:d=>{x=d;render()}})}", 1),
    # über lesen(): in Ordnung
    ("async function load(){await lesen('x',()=>api('/b'),d=>{rows=d})}async function f(){await speichern('x',()=>api('/a',{method:'PUT'}),{neuLaden:load})}", 0),
    # Lesen VOR dem Speichern zählt nicht (Vorschau)
    ("async function f(){const v=await api('/vorschau');await speichern('x',()=>api('/a',{method:'PUT'}))}", 0),
    # über eine Funktion, die selbst speichert
    ("async function senden(){await speichern('y',()=>fetch('/m',{method:'POST'}))}async function load(){rows=await api('/b')}"
     "async function f(){await senden();await load()}", 1),
])
def test_scanner_finds_reads_after_saving(js, funde):
    api = "async function api(u,o){const r=await fetch(u,o);return r.json()}"
    assert len({k for k, _ in vj.nach_dem_speichern(_beispiel(api + js))}) == funde


def test_scanner_handles_template_literals_regex_and_comments():
    js = ("async function f(){const re=/[/(]x/g;// api('/a',{method:'PUT'})\n"
          "const h=`<a onclick=\"x('${y.map(z=>`${z}`).join('')}')\">{method:'PUT'}</a>`;"
          "/* {method:'DELETE'} */await speichern('x',()=>api(`/a/${id}`,{method:'PUT'}))}")
    stellen = vj.schreibstellen(_beispiel(js))
    assert [s.ok for s in stellen] == [True]


def test_gespeichert_check_on_examples():
    gut = _beispiel("async function f(){try{await speichern('x',()=>api('/a',{method:'PUT'}),{neuLaden:g});st.textContent='Gespeichert.'}catch(e){}}")
    vorher = _beispiel("async function f(){await api('/a',{method:'PUT'});st.textContent='Gespeichert.';await load()}")
    drin = _beispiel("async function f(){await speichern('x',()=>api('/a',{method:'PUT'}),{anwenden:d=>{st.textContent='Gespeichert.'}})}")
    assert _gespeichert_stellen(gut) == []
    assert len(_gespeichert_stellen(vorher)) == 1
    assert len(_gespeichert_stellen(drin)) == 1


# --- Jedes Seitenskript ist gültiges JavaScript ----------------------------------------------------------------------------

_INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", flags=re.S | re.I)
_PARSE = r"""
const vm=require('vm');const fs=require('fs');
const liste=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));const fehler=[];
for(const [name,code] of liste){try{new vm.Script(code,{filename:name})}catch(e){fehler.push(name+': '+e.message)}}
process.stdout.write(JSON.stringify(fehler));
"""


@nur_mit_node
def test_every_rendered_page_script_is_valid_javascript(threaded_db_session, router_test_client):
    from app.routers.pages import router as pages_router
    from tests.test_v218_template_rendering import _dummy_path

    skripte, seiten = [], 0
    for rolle in ("admin", "field"):
        client = router_test_client(threaded_db_session, pages_router, role=rolle)
        for route in pages_router.routes:
            if "GET" not in getattr(route, "methods", set()) or route.path == "/health":
                continue
            resp = client.get(_dummy_path(route.path), follow_redirects=False)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                continue
            seiten += 1
            for nr, m in enumerate(_INLINE.finditer(resp.text), start=1):
                skripte.append((f"{rolle} {route.path} Skript {nr}", m.group(1)))
    assert seiten > 60 and len(skripte) > 150
    with tempfile.TemporaryDirectory() as ordner:
        datei = Path(ordner) / "skripte.json"
        datei.write_text(json.dumps(skripte), encoding="utf-8")
        ergebnis = subprocess.run([NODE, "-e", _PARSE, str(datei)], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert ergebnis.returncode == 0, ergebnis.stderr
    fehler = json.loads(ergebnis.stdout)
    assert not fehler, "Ungültiges JavaScript in gerenderten Seiten:\n" + "\n".join(fehler)
