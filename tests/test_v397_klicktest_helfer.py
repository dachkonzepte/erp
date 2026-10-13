"""Version 1.8.94 -- Klicktest-Helfer "warte auf neu geladene Liste" (scripts/cdp_klicktest.py, Tab.warte_auf_neu_geladene_liste()).

Nach einer Aktion, die speichert und neu lädt, belegt weder ein Statustext (oft vor dem Neuladen gesetzt) noch eine feste Pause, dass
die Anzeige neu ist. Der Helfer zählt die Anfragen der Seite (ANFRAGEN_ZAEHLER, in jedes Dokument eingesetzt) und wartet, bis seit der
Aktion eine gestartet, keine mehr unterwegs und eine Ruhezeit vergangen ist (neu_geladen_bedingung()), mit Liste zusätzlich, bis deren
alte Elemente aus dem Dokument sind. Hier laufen Zählerskript und Bedingung in node mit einer gestellten Uhr und gestellten Anfragen;
dazu der Strukturtest, dass die Klicktests mit dem Muster ihn nutzen."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

from tests.test_v314_dashboard_month_berlin import NODE, _node

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


def _werkzeug():
    spec = importlib.util.spec_from_file_location("cdp_klicktest_test", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _ablauf(schritte: str, *, vorher: int | None, mit_liste: bool = False) -> list:
    """Führt das Zählerskript und die Bedingung in node aus. schritte: JS mit den Hilfen jetzt (Uhr in ms), anfrage() (startet
    einen fetch, gibt die Funktion zum Beenden zurück), xhr(), pruefe() (wertet die Bedingung aus, Ergebnis in die Liste);
    async, Mikrotasks über ruhe()."""
    w = _werkzeug()
    bedingung = w.neu_geladen_bedingung(vorher, mit_liste, 0.3)
    script = "\n".join([
        "let jetzt=1000;const performance={now:()=>jetzt};const window=globalThis;",
        "const offen=[];globalThis.fetch=()=>new Promise((res,rej)=>offen.push(res));",
        "class XMLHttpRequest{constructor(){this.h={}}addEventListener(n,f){this.h[n]=f}send(){}}globalThis.XMLHttpRequest=XMLHttpRequest;",
        w.ANFRAGEN_ZAEHLER,
        "const ergebnisse=[];const pruefe=()=>ergebnisse.push(eval(" + json.dumps(bedingung) + "));",
        "const ruhe=()=>new Promise(r=>setTimeout(r,0));",
        "const anfrage=()=>{window.fetch('/api/x');const res=offen[offen.length-1];return async()=>{res({ok:true});await ruhe()}};",
        "const xhr=()=>{const x=new XMLHttpRequest();x.send();return ()=>x.h.loadend()};",
        f"(async()=>{{{schritte}\nprocess.stdout.write(JSON.stringify(ergebnisse))}})()",
    ])
    return _node(script, "Europe/Berlin")


@nur_mit_node
def test_waits_until_the_request_is_done_and_the_page_was_quiet():
    ergebnisse = _ablauf("""
        pruefe();                       // nach der Aktion noch keine Anfrage gestartet
        const fertig=anfrage();
        jetzt=5000; pruefe();           // unterwegs, auch nach langer Zeit
        await fertig(); jetzt=5200; pruefe();   // fertig, aber erst 200 ms ruhig
        jetzt=5300; pruefe();           // 300 ms ruhig
    """, vorher=0)
    assert ergebnisse == [False, False, False, True]


@nur_mit_node
def test_a_reload_chain_restarts_the_quiet_time():
    """Speichern -> reload(): die zweite Anfrage startet nach der ersten; erst nach ihr und der Ruhezeit ist die Seite neu."""
    ergebnisse = _ablauf("""
        const speichern=anfrage(); await speichern();
        jetzt=1100; const neu=anfrage(); jetzt=1500; pruefe();  // erste fertig, zweite unterwegs
        await neu(); jetzt=1700; pruefe(); jetzt=1800; pruefe();
    """, vorher=0)
    assert ergebnisse == [False, False, True]


@nur_mit_node
def test_xhr_counts_like_fetch():
    ergebnisse = _ablauf("""
        const fertig=xhr(); jetzt=3000; pruefe(); fertig(); jetzt=3400; pruefe();
    """, vorher=0)
    assert ergebnisse == [False, True]


@nur_mit_node
def test_without_an_action_only_quiet_counts():
    ergebnisse = _ablauf("""
        jetzt=1200; pruefe(); jetzt=1300; pruefe();   // nichts gestartet: ruhig seit dem Laden (1000)
        const fertig=anfrage(); pruefe(); await fertig(); jetzt=1700; pruefe();
    """, vorher=None)
    assert ergebnisse == [False, True, False, True]


@nur_mit_node
def test_with_a_list_the_old_elements_must_be_gone():
    ergebnisse = _ablauf("""
        const alt={isConnected:true}; window.__dkAlteListe=[alt];
        const fertig=anfrage(); await fertig(); jetzt=2000; pruefe();   // geladen, Liste noch die alte
        alt.isConnected=false; pruefe();
    """, vorher=0, mit_liste=True)
    assert ergebnisse == [False, True]


def test_every_tab_gets_the_counter():
    text = (SCRIPTS / "cdp_klicktest.py").read_text(encoding="utf-8")
    lauf = text[text.index("async def _lauf("):]
    assert 'await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=ANFRAGEN_ZAEHLER)' in lauf
    helfer = text[text.index("async def warte_auf_neu_geladene_liste("):text.index("async def warten(")]
    assert "await self.js(aktion)" in helfer and "neu_geladen_bedingung(" in helfer and "self.nicht_geladen.append(" in helfer


# Klicktests mit dem Muster "nach einer Aktion, die neu lädt, Text oder Pause abwarten und dann lesen" (Durchsicht 1.8.94); jede
# Stelle ruft den Helfer auf, die festen Pausen dort sind weg.
UMGESTELLT = {
    "klicktest_checkliste_abschnitte.py": 1,  # zwei Speichern gleichzeitig (Ende, Kachel), dann der Hinweis
    "klicktest_checkliste_verwerfen.py": 1,   # Ende speichern, dann lesen (bis 1.8.93 0,5 s Pause)
    "klicktest_mahnwesen.py": 1,              # "3 Entwürfe angelegt." vor reload() (von Hand seit 1.8.87)
    "klicktest_abnahme.py": 1,                # "Vorschlag übernommen." vor loadAcceptanceSection()
    "klicktest_bedenkenanzeige.py": 2,        # Hinweis darf NICHT erscheinen: erst nach dem Nachladen prüfen
    "klicktest_nebenforderungen.py": 1,       # Text vor loadAndRenderReminders() (nicht abgewartet)
}


@pytest.mark.parametrize("name, anzahl", sorted(UMGESTELLT.items()))
def test_the_klicktests_with_the_pattern_use_the_helper(name, anzahl):
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert len(re.findall(r"await tab\.warte_auf_neu_geladene_liste\(", text)) >= anzahl, name
    assert "asyncio.sleep(0.3)\n    p.pruefe(\"Hinweis weg nach der Antwort\"" not in text
    if name in ("klicktest_checkliste_abschnitte.py", "klicktest_checkliste_verwerfen.py", "klicktest_bedenkenanzeige.py"):
        assert "asyncio.sleep(" not in text, name
