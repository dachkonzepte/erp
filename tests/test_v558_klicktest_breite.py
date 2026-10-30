"""Version 1.9.138 -- Breitenprüfung der Klicktests (Stufe 5, R4, Punkt 1; Fund aus R3).

In der Mobil-Emulation (`mobile`, alle Geräte unter 1280 px) wächst innerWidth mit dem Inhalt: `scrollWidth <= innerWidth` ist dort immer wahr, die
Prüfung „kein waagrechtes Scrollen“ sah deshalb nichts. Gemessen wird gegen die feste Gerätebreite: `tab.ueberlauf()` (scripts/cdp_klicktest.py::UEBERLAUF)
nennt die Seite, wenn sie breiter ist, und jedes sichtbare Element, das über den Bildschirm ragt -- außer in einem Behälter, der selbst rollt oder schneidet
(eine breite Tabelle in einem rollenden Rahmen ist gewollt).

- Kein Klicktest vergleicht scrollWidth mit innerWidth (außer in Kommentaren).
- Die 15 Klicktests aus dem Bericht R3 messen über tab.ueberlauf().
- UEBERLAUF in node an einer Attrappe: zu breite Seite, zu breites Element, Element in einem Behälter mit Bildlauf, verstecktes Element, passender Inhalt."""

import asyncio
import importlib.util
import json
import re
from pathlib import Path

import pytest

from tests.node_lauf import NODE, node_ausfuehren

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")

UMGESTELLT = ("bedenkenanzeige", "bedenkenanzeige_versand", "behinderungsanzeige", "behinderungsanzeige_abschluss", "behinderungsanzeige_versand",
              "beleg_und_hinweis", "beteiligte", "beteiligte_stammdaten", "ersteinrichtung", "nebenforderungen", "rahmen", "versandprotokoll", "versandverlauf",
              "vertragsvorlagen", "zeiten", "kundenakte", "lv_ueberlauf", "zahlungen_kleinkram")
GEGEN_INNERWIDTH = re.compile(r"scrollWidth\s*(?:<=|<|>=|>|===?)\s*(?:window\.)?innerWidth|(?:window\.)?innerWidth\s*(?:<=|<|>=|>|===?)\s*[\w.]*scrollWidth")


def _ohne_kommentare(text: str) -> str:
    return "\n".join(zeile for zeile in text.splitlines() if not zeile.lstrip().startswith("#"))


def _werkzeug():
    spec = importlib.util.spec_from_file_location("cdp_klicktest_test", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_kein_klicktest_misst_gegen_innerwidth():
    treffer = [p.name for p in sorted(SCRIPTS.glob("klicktest_*.py")) if GEGEN_INNERWIDTH.search(_ohne_kommentare(p.read_text(encoding="utf-8")))]
    assert treffer == []


def test_das_muster_erkennt_die_alte_pruefung():
    # Die Schreibweisen, die bis 1.9.137 in den Klicktests standen -- sonst prüfte der Wächter oben nichts.
    for alt in ("document.documentElement.scrollWidth<=innerWidth", "document.documentElement.scrollWidth <= window.innerWidth",
                "innerWidth>=document.documentElement.scrollWidth"):
        assert GEGEN_INNERWIDTH.search(alt), alt


@pytest.mark.parametrize("name", UMGESTELLT)
def test_umgestellter_klicktest_misst_ueber_das_werkzeug(name):
    assert ".ueberlauf(" in _ohne_kommentare((SCRIPTS / f"klicktest_{name}.py").read_text(encoding="utf-8"))


def _messen(elemente: list[dict], seite: int = 412, breite: int = 412) -> list[str]:
    """elemente: {name, rechts, breite?, display?, visibility?, eltern? (Index), overflowX?}"""
    skript = f"""
const liste={json.dumps(elemente)};
const koerper={{tagName:'BODY',parentElement:null}};
const wurzel={{scrollWidth:{seite},tagName:'HTML',parentElement:null}};
const objekte=liste.map(d=>({{tagName:d.name.toUpperCase(),id:'',className:'',d}}));
objekte.forEach(o=>{{o.parentElement=o.d.eltern==null?koerper:objekte[o.d.eltern];
  o.getBoundingClientRect=()=>({{right:o.d.rechts,width:o.d.breite??100,height:o.d.hoehe??20}})}});
globalThis.document={{documentElement:wurzel,body:koerper,querySelectorAll:()=>objekte}};
globalThis.scrollX=0;
globalThis.getComputedStyle=o=>({{display:o.d?.display??'block',visibility:o.d?.visibility??'visible',overflowX:o.d?.overflowX??'visible'}});
console.log(JSON.stringify(({_werkzeug().UEBERLAUF})({breite})));
"""
    return node_ausfuehren(skript)


@nur_mit_node
def test_passender_inhalt_ergibt_nichts():
    assert _messen([{"name": "div", "rechts": 412}, {"name": "p", "rechts": 200}]) == []


@nur_mit_node
def test_zu_breite_seite_wird_genannt():
    aus = _messen([{"name": "table", "rechts": 700}], seite=700)
    assert aus[0] == "Seite 700 px breit"
    assert aus[1] == "table bis 700 px"


@nur_mit_node
def test_zu_breites_element_wird_auch_bei_passender_seite_genannt():
    # Die Seite schneidet am Rand (overflow-x:hidden am body): scrollWidth bleibt, das Element ragt trotzdem aus dem Bild.
    assert _messen([{"name": "button", "rechts": 480}]) == ["button bis 480 px"]


@nur_mit_node
def test_element_im_rollenden_behaelter_zaehlt_nicht():
    assert _messen([{"name": "div", "rechts": 400, "overflowX": "auto"}, {"name": "table", "rechts": 900, "eltern": 0}]) == []


@nur_mit_node
def test_verstecktes_und_leeres_element_zaehlen_nicht():
    assert _messen([{"name": "div", "rechts": 900, "display": "none"}, {"name": "span", "rechts": 900, "visibility": "hidden"},
                    {"name": "i", "rechts": 900, "breite": 0}]) == []


@nur_mit_node
def test_rand_innerhalb_eines_halben_pixels_passt():
    assert _messen([{"name": "div", "rechts": 412.4}]) == []
    assert _messen([{"name": "div", "rechts": 412.6}]) == ["div bis 413 px"]


def test_ueberlauf_ohne_breite_ist_ein_fehler():
    tab = _werkzeug().Tab.__new__(_werkzeug().Tab)
    tab.geraet_breite = None
    with pytest.raises(ValueError):
        asyncio.run(tab.ueberlauf())
