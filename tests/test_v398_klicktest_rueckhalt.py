"""Version 1.8.95 -- Klicktest-Werkzeug: Antwort gezielt zurückhalten (scripts/cdp_klicktest.py, ANTWORT_RUECKHALT,
Tab.zurueckhalten()/freigeben()).

Die Klicktests zu veralteten Antworten (scripts/klicktest_veraltete_antworten.py) halten eine Antwort der Seite zurück: art
"antwort" -- die Anfrage geht sofort hinaus (der Server bearbeitet sie), die Seite bekommt die Antwort erst bei freigeben(); art
"anfrage" -- sie geht erst dann hinaus. Hier läuft das Skript in node mit einem gestellten fetch, zusammen mit dem Anfragenzähler aus
1.8.94 (der eine zurückgehaltene Antwort als unterwegs zählt, weil der Rückhalter vor ihm eingesetzt wird)."""

import importlib.util
import inspect
from pathlib import Path

import pytest

from tests.test_v314_dashboard_month_berlin import NODE, _node

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


def _werkzeug():
    spec = importlib.util.spec_from_file_location("cdp_klicktest_rueckhalt", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _ablauf(schritte: str) -> list:
    """Gestelltes fetch: protokolliert 'server <url>' beim Aufruf (= der Server bekommt die Anfrage) und antwortet sofort; die Seite
    protokolliert 'seite <url>', wenn ihre Antwort ankommt. Danach Rückhalter, dann Zähler -- wie in _lauf()."""
    w = _werkzeug()
    script = "\n".join([
        "let jetzt=1000;const performance={now:()=>jetzt};const window=globalThis;const log=[];",
        "globalThis.fetch=(url,init)=>{log.push('server '+url);return Promise.resolve({ok:true,url})};",
        "class XMLHttpRequest{send(){}addEventListener(){}};globalThis.XMLHttpRequest=XMLHttpRequest;",
        w.ANTWORT_RUECKHALT + ";", w.ANFRAGEN_ZAEHLER + ";",  # im Browser je ein eigenes Skript
        "const ruhe=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setTimeout(r,0))};",
        "const R=window.__dkRueckhalt,Z=window.__dkAnfragen;",
        "const seite=(url,init)=>window.fetch(url,init).then(r=>log.push('seite '+r.url));",
        f"(async()=>{{{schritte}\nawait ruhe();process.stdout.write(JSON.stringify(log))}})().catch(e=>{{console.error(e);process.exit(1)}})",
    ])
    return _node(script, "Europe/Berlin")


@nur_mit_node
def test_a_held_response_reaches_the_page_only_after_release():
    log = _ablauf("""
        R.regeln.push({muster:'/api/x$',methode:'GET',anzahl:1,art:'antwort'});
        seite('/api/x'); await ruhe();
        log.push('gehalten '+JSON.stringify(R.stand())+' offen '+Z.offen);
        seite('/api/x'); await ruhe();        // Regel verbraucht: geht durch
        R.freigeben(); await ruhe();
        log.push('offen '+Z.offen);
    """)
    assert log == ["server /api/x", 'gehalten [{"url":"/api/x","methode":"GET","art":"antwort","beantwortet":true}] offen 1',
                   "server /api/x", "seite /api/x", "seite /api/x", "offen 0"]


@nur_mit_node
def test_a_held_request_reaches_the_server_only_after_release():
    log = _ablauf("""
        R.regeln.push({muster:'/answers/7$',methode:'PUT',anzahl:1,art:'anfrage'});
        seite('/answers/7',{method:'PUT'}); await ruhe();
        log.push('vor der Freigabe');
        R.freigeben(); await ruhe();
    """)
    assert log == ["vor der Freigabe", "server /answers/7", "seite /answers/7"]


@nur_mit_node
def test_other_urls_and_methods_pass_through():
    log = _ablauf("""
        R.regeln.push({muster:'/api/x$',methode:'GET',anzahl:1,art:'antwort'});
        seite('/api/x/1'); seite('/api/x',{method:'PUT'}); await ruhe();
        log.push('gehalten '+R.stand().length);
    """)
    assert log == ["server /api/x/1", "server /api/x", "seite /api/x/1", "seite /api/x", "gehalten 0"]


@nur_mit_node
def test_release_goes_in_order():
    log = _ablauf("""
        R.regeln.push({muster:'/api/',anzahl:2,art:'antwort'});
        seite('/api/eins'); seite('/api/zwei'); await ruhe();
        R.freigeben(); await ruhe(); log.push('-'); R.freigeben(); await ruhe();
        log.push('noch '+R.freigeben());
    """)
    assert log == ["server /api/eins", "server /api/zwei", "seite /api/eins", "-", "seite /api/zwei", "noch false"]


def test_every_tab_gets_the_holder_before_the_counter():
    quelle = inspect.getsource(_werkzeug()._lauf)
    assert quelle.index("source=ANTWORT_RUECKHALT") < quelle.index("source=ANFRAGEN_ZAEHLER")


def test_the_stale_response_click_test_holds_a_response_on_each_required_page():
    """Vorgabe: mindestens Checkliste, Abnahme, Mahnung und Einstellungen."""
    quelle = (SCRIPTS / "klicktest_veraltete_antworten.py").read_text(encoding="utf-8")
    for teil in ("async def _checkliste", "async def _abnahme", "async def _mahnung_rechnung", "async def _einstellungen"):
        rumpf = quelle.split(teil, 1)[1].split("\nasync def ", 1)[0]
        assert "await tab.zurueckhalten(" in rumpf and "await tab.freigeben()" in rumpf, teil
