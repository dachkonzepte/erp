"""Version 1.8.105 -- Die Scanner lesen Pfeilfunktionen vollständig (Vorgabe vom 14.10.2026 Punkt 1, Nebenbefund 1.8.102 Nr. 1).

Bis 1.8.104 endete in tests/vorlagen_js.py der Rumpf eines Pfeils ohne geschweifte Klammern an der ersten schließenden Klammer derselben
Ebene, auch wenn ihre öffnende im Rumpf stand (`s => String(s ?? '').replace(…)` endete nach `String(s ?? ''`). Was danach kam, gehörte
für die Scanner nicht mehr zur Funktion: ein Speichern darin machte die Funktion nicht zu einer schreibenden (test_v398), und eine
Funktion galt nach ihrem abgeschnittenen Rumpf als sicher (test_v407). Seit 1.8.105 gibt es eine Funktion für das Ende eines Ausdrucks
(`_ausdruck_ende()`, auch für tests/vorlagen_navigation.py und damit tests/vorlagen_html.py): Klammern ab dem Anfang gehören dazu, eine
neue Zeile beendet ihn, wenn sie nicht fortsetzen kann (wie die automatische Semikolon-Einfügung).

Gegenproben: docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.105"."""

from __future__ import annotations

import pytest

from tests import vorlagen_js as vj
from tests.vorlagen_html import Pruefer
from tests.vorlagen_navigation import _ende


def _beispiel(js: str) -> vj.Analyse:
    return vj.analysieren(vj.Quelle("beispiel", js, [(0, len(js), "beispiel", 0)]))


def _rumpf(js: str, name: str) -> str:
    a = _beispiel(js)
    (s, e), = a.funktionen[name]
    return js[a.t[s].pos:a.t[e].pos + len(a.t[e].wert) + (2 if a.t[e].art == "str" else 0)]


@pytest.mark.parametrize("js, rumpf", [
    # die schließende Klammer eines Aufrufs im Rumpf beendet ihn nicht (bis 1.8.104: "String(s ?? ''")
    ("const f = s => String(s ?? '').replace(/a/g, 'b');", "String(s ?? '').replace(/a/g, 'b')"),
    ("const f = x => (x.liste || []).map(y => y.id).join(',');\nlet z = 1;", "(x.liste || []).map(y => y.id).join(',')"),
    ("const f = async (u, o) => (await api(u, o)).json(); g();", "(await api(u, o)).json()"),
    ("const f = x => [x.a, x.b][0], g = 2;", "[x.a, x.b][0]"),
    ("const f = x => ({a: x}).a\nconst g = 1", "({a: x}).a"),
    # die Klammer der Umgebung beendet ihn
    ("liste.forEach(x => { const f = y => g(y) })", "g(y)"),
    ("h(function(){ const f = y => g(y) })", "g(y)"),
    # Zeilenende: neue Anweisung (Schlüsselwort, Name, Zahl, String, ++, !) -- oder Fortsetzung (Operator, Punkt, Klammer, Template)
    ("const f = x => g(x)\nfetch('/a')", "g(x)"),
    ("const f = x => g(x)\nfunction h(){}", "g(x)"),
    ("const f = x => x.a\n'use strict'", "x.a"),
    ("const f = x => x\n++i", "x"),
    ("const f = x => x\n!g()", "x"),
    ("const f = x => g(x)\n  .then(h)\n  .catch(k)\nlos()", "g(x)\n  .then(h)\n  .catch(k)"),
    ("const f = x => x.a\n  + x.b\nlos()", "x.a\n  + x.b"),
    ("const f = x => x.a\n  ? x.b\n  : x.c\nlos()", "x.a\n  ? x.b\n  : x.c"),
    ("const f = x => g\n(x)\nlos()", "g\n(x)"),
    ("const f = x => x.a\n  in o\nlos()", "x.a\n  in o"),
])
def test_ein_pfeil_reicht_bis_zum_ende_seines_ausdrucks(js, rumpf):
    assert _rumpf(js, "f") == rumpf


def test_der_wert_einer_zuweisung_endet_ebenso():
    js = "let u = '/x/' + encodeURIComponent(id).trim()\nlocation.href = u"
    a = _beispiel(js)
    start = next(k for k, t in enumerate(a.t) if t.wert == "/x/")
    assert js[a.t[start].pos:a.t[_ende(a, start)].pos + 1] == "'/x/' + encodeURIComponent(id).trim()"


# --- Was die Strukturtests dadurch sehen -------------------------------------------------------------------------------------

def test_ein_speichern_im_pfeil_macht_ihn_zu_einer_schreibenden_funktion():
    """test_v398: nach dem Speichern liest die Seite nur über den Baustein -- auch wenn das Speichern in einem Pfeil steht, dessen
    Rumpf mit einem Aufruf beginnt. Bis 1.8.104 endete sichern() nach "pruefen(1", das fetch danach blieb unbemerkt."""
    js = ("const sichern = () => pruefen(1) && speichern('b', () => api('/a', {method: 'PUT'}), {neuLaden: laden});\n"
          "async function klick(){ await sichern(); fetch('/api/liste'); }\n")
    a = _beispiel(js)
    assert {weg for _, weg in vj.nach_dem_speichern(a)} == {"klick: fetch nach dem Speichern"}


def test_eine_anfrage_nach_einem_pfeil_ohne_semikolon_gehoert_nicht_zum_pfeil():
    """test_v400: eine Funktion, die nur im Baustein aufgerufen wird, ist geprüft -- eine Anfrage in der Zeile nach ihr gehört ihr nicht
    (ohne Semikolon). Ohne das Zeilenende gehörte fetch zu nr() und blieb unbemerkt."""
    js = ("const nr = x => Number(x)\n"
          "fetch('/api/frei')\n"
          "lesen('b', () => api('/a?n=' + nr(1)), zeigen)\n")
    a = _beispiel(js)
    assert vj.anfragen_ausserhalb(a, None) == {("beispiel", "<oben>", "fetch")}


def test_ein_anfragehelfer_als_pfeil_wird_erkannt():
    """test_v400: ein Anfrage-Helfer als Pfeil, dessen Rumpf mit einem Aufruf beginnt -- seine Aufrufe außerhalb des Bausteins zählen."""
    js = ("const holen = u => String(u).trim() && fetch(u);\n"
          "function laden(){ return holen('/api/x'); }\n"
          "laden();\n")
    a = _beispiel(js)
    assert vj.anfragen_ausserhalb(a, None) == {("beispiel", "laden", "holen")}


ESC = """const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));\n"""


@pytest.mark.parametrize("js, funde", [
    # ein Pfeil, der einen Wert ungeschützt einsetzt: sein Rumpf beginnt mit einer Zahl -- bis 1.8.104 endete er nach "Number(k.nr ?? 0"
    # und galt als sicher
    ("const zeile = k => Number(k.nr ?? 0).toFixed(0) + ' ' + k.name;\n"
     "function zeigen(kunde){ el.innerHTML = `<td>${zeile(kunde)}</td>`; }\nzeigen(daten);",
     [("zeigen", "zeile(kunde)")]),
    ("const zeile = k => Number(k.nr || 0) + `<b>${k.name}</b>`;\nel.innerHTML = liste.map(zeile).join('');",
     [("zeile", "k.name")]),
    # mit esc() bleibt es still
    ("const zeile = k => Number(k.nr ?? 0).toFixed(0) + ' ' + esc(k.name);\n"
     "function zeigen(kunde){ el.innerHTML = `<td>${zeile(kunde)}</td>`; }\nzeigen(daten);", []),
])
def test_ein_pfeil_der_einen_wert_ungeschuetzt_einsetzt_wird_gefunden(js, funde):
    p = Pruefer("beispiel.html", text=ESC + js)
    assert [(f.funktion, f.ausdruck) for f in p.ungeschuetzt()] == funde


def test_die_funktion_einer_fundstelle_ist_der_pfeil():
    """Die Ausnahmelisten zählen je "Datei | Funktion | Ausdruck" -- die Funktion ist der Pfeil, in dem der Wert steht (bis 1.8.104 die
    Funktion um ihn herum, wenn sein Rumpf mit einer Klammer begann: work_preparation.html, deliveryTags in renderMaterials)."""
    js = ("function render(){ const tag = x => (x.l || []).map(d => `<button onclick=\"weg(${x.id},${d.id})\">x</button>`).join('');"
          " el.innerHTML = rows.map(tag).join(''); }\nrender();")
    p = Pruefer("beispiel.html", text=ESC + js)
    assert sorted((f.funktion, f.ausdruck) for f in p.handler_mit_werten()) == [("tag", "onclick: d.id"), ("tag", "onclick: x.id")]
