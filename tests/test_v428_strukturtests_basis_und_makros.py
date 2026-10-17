"""Version 1.8.123 -- Stufe 0a des Redesigns: die Strukturtests lesen Unterordner, Basis-Templates und Makros
(docs/archiv/testablauf-und-klicktests.md, "Strukturtests für Basis-Templates und Makros").

Die Oberfläche soll auf ein gemeinsames Basis-Layout ({% extends %}) und Jinja-Makros umgestellt werden. Bis 1.8.122 lasen die Scanner
(tests/vorlagen_js.py, vorlagen_html.py, vorlagen_zahlen.py, vorlagen_navigation.py) und die node-Attrappe (test_v334 seite()) nur
Vorlagen der obersten Ebene von app/templates und setzten nur {% include %} ein: was ein Makro, ein Unterordner oder ein Basis-Template
in eine Seite bringt, sahen sie nicht -- ein Verstoß dort wäre still durchgerutscht, der Strukturtest grün geblieben.

Gegenproben: je Scanner erfundene Vorlagen in einem eigenen Ordner (tmp_path, nie app/templates) mit demselben Verstoß an vier Orten --
"direkt" in einer einzigen Datei (das fand der Scanner schon bisher: die Probe enthält etwas Erkennbares), in einem Makro, in einem
Unterordner und in einem Basis-Template. Makro und Basis-Template sind so gebaut, dass der Verstoß erst in der zusammengesetzten Seite
einer ist (ein Handler im Makro ruft eine Funktion der Seite auf, ein Feld im Basis-Template wird im Block der Seite gelesen …); läge er
ganz im Makro oder in der Basis, fände ihn schon das Lesen der Datei für sich. Jede Gegenprobe läuft nur über Schnittstellen, die es
schon vor 1.8.123 gab -- so ist "rot vorher" ein übersehener Verstoß, kein Importfehler."""

import ast
import re
from pathlib import Path

import pytest

import tests.test_v334_auswahl_restfaelle as t334
import tests.test_v398_speichern_baustein as t398
import tests.test_v400_lesen_ueber_baustein as t400
import tests.test_v414_zahleneingaben as t414
import tests.vorlagen_html as vh
import tests.vorlagen_js as vj
import tests.vorlagen_navigation as vn
import tests.vorlagen_zahlen as vz
from tests.test_v314_dashboard_month_berlin import NODE

nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")

ROOT = Path(__file__).resolve().parent.parent

# Jedes Modul, das die Vorlagen über ein eigenes TEMPLATES liest.
MODULE = (vj, vh, vz, vn, t334, t398, t400, t414)


def _caches_leeren() -> None:
    for modul in MODULE:
        for wert in list(vars(modul).values()):
            if callable(getattr(wert, "cache_clear", None)):
                wert.cache_clear()
        if isinstance(getattr(modul, "_CACHE", None), dict):
            modul._CACHE.clear()


@pytest.fixture
def vorlagen(tmp_path, monkeypatch):
    """Ein eigener Vorlagenordner für alle Scanner: schreiben({"name.html": text, "ordner/x.html": text})."""
    for modul in MODULE:
        if hasattr(modul, "TEMPLATES"):
            monkeypatch.setattr(modul, "TEMPLATES", tmp_path)
    _caches_leeren()

    def schreiben(dateien: dict) -> Path:
        for name, text in dateien.items():
            pfad = tmp_path / name
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_text(text, encoding="utf-8")
        _caches_leeren()
        return tmp_path

    yield schreiben
    _caches_leeren()


FAELLE = ["direkt", "makro", "unterordner", "basis"]


# ---------------------------------------------------------------------------
# vorlagen_js: Anfragen außerhalb des Bausteins (wie test_v400 sie sammelt)
# ---------------------------------------------------------------------------

API = "async function api(u,o){const r=await fetch(u,o);return r.json()}"

JS_VORLAGEN = {
    "seite_direkt.html": "<html><button onclick=\"api('/x')\">x</button><script>" + API + "</script></html>",
    # a) Makro (import … as): der Handler im Makro ruft den Anfrage-Helfer der Seite
    "makros_js.html": "{% macro knopf(text) %}<button onclick=\"api('/b')\">{{ text }}</button>{% endmacro %}",
    "seite_makro.html": '{% import "makros_js.html" as m %}<html>{{ m.knopf("Laden") }}<script>' + API + "</script></html>",
    # b) Unterordner
    "teile/seite_unterordner.html": "<html><script>" + API + "\nasync function laden(){await api('/c')}\nladen()</script></html>",
    # c) Basis-Template: der Handler steht in der Basis, der Helfer im Block der Seite
    "basis_js.html": "<html><body><button onclick=\"api('/d')\">x</button>{% block inhalt %}{% endblock %}</body></html>",
    "kind_js.html": '{% extends "basis_js.html" %}{% block inhalt %}<script>' + API + "</script>{% endblock %}",
}
JS_ERWARTET = {
    "direkt": ("seite_direkt.html", "<html>", "api"),
    "makro": ("makros_js.html", "<html>", "api"),
    "unterordner": ("teile/seite_unterordner.html", "laden", "api"),
    "basis": ("basis_js.html", "<html>", "api"),
}


@pytest.mark.parametrize("fall", FAELLE)
def test_gegenprobe_vorlagen_js(vorlagen, fall):
    vorlagen(JS_VORLAGEN)
    funde = t400._alle_funde()
    assert JS_ERWARTET[fall] in funde, f"{fall}: Anfrage außerhalb des Bausteins nicht gefunden -- gefunden: {sorted(funde)}"


# ---------------------------------------------------------------------------
# vorlagen_html: Werte ohne esc() im HTML, Jinja-Werte in on…-Attributen
# ---------------------------------------------------------------------------

ZEIGE = "function zeige(x){document.getElementById('z').innerHTML=`<b>${x}</b>`}\nzeige(1)"
HANDLER = "<button onclick=\"zeige(this.dataset.name)\" data-name=\"{{ name }}\">"

HTML_VORLAGEN = {
    # Eine Funktion, die nur mit sicheren Werten gerufen wird, ist sicher -- bis ein on…-Attribut sie mit einem Wert aus dem HTML ruft.
    "seite_direkt.html": "<html>" + HANDLER + "x</button><div id=\"z\"></div><script>" + ZEIGE + "</script></html>",
    # a) Makro (from … import, {% call %}): der Handler steckt im Makro
    "makros_html.html": "{% macro knopf(name) %}" + HANDLER + "{{ caller() }}</button>{% endmacro %}",
    "seite_makro.html": ('{% from "makros_html.html" import knopf %}<html>{% call knopf("x") %}Zeigen{% endcall %}'
                         "<div id=\"z\"></div><script>" + ZEIGE + "</script></html>"),
    # b) Unterordner: ein Wert ohne esc() und ein Jinja-Wert in einem on…-Attribut
    "teile/seite_unterordner.html": "<html><script>function f(x){el.innerHTML=x.name}\nf(antwort)</script></html>",
    "teile/knopf.html": "<button onclick=\"f({{ wert }})\">x</button>",
    # c) Basis-Template: die Funktion mit innerHTML steht in der Basis, der Handler im Block der Seite
    "basis_html.html": "<html><div id=\"z\"></div><script>" + ZEIGE + "</script>{% block inhalt %}{% endblock %}</html>",
    "kind_html.html": '{% extends "basis_html.html" %}{% block inhalt %}' + HANDLER + "x</button>{% endblock %}",
}
HTML_ERWARTET = {
    "direkt": [("ungeschuetzt", "seite_direkt.html | zeige | x")],
    "makro": [("ungeschuetzt", "seite_makro.html | zeige | x")],
    "unterordner": [("ungeschuetzt", "teile/seite_unterordner.html | f | x.name"), ("jinja", "teile/knopf.html")],
    "basis": [("ungeschuetzt", "basis_html.html | zeige | x")],
}


@pytest.mark.parametrize("fall", FAELLE)
def test_gegenprobe_vorlagen_html(vorlagen, fall):
    vorlagen(HTML_VORLAGEN)
    for art, erwartet in HTML_ERWARTET[fall]:
        funde = vh.alle_funde(art)
        if art == "jinja":
            gefunden = [f.datei for f in funde]
        else:
            gefunden = [f.schluessel() for f in funde]
        assert erwartet in gefunden, f"{fall}/{art}: {erwartet!r} nicht gefunden -- gefunden: {gefunden}"


# ---------------------------------------------------------------------------
# vorlagen_zahlen: Zahleneingaben an _zahl.html vorbei
# ---------------------------------------------------------------------------

ZAHL_FELD = '<input id="menge" type="text" inputmode="decimal" data-zahl>'
ROH_LESEN = "fetch('/x?m='+document.getElementById('menge').value)"  # der Rohtext eines Zahlenfelds geht an den Server

ZAHL_VORLAGEN = {
    "seite_direkt.html": "<html>" + ZAHL_FELD + "<script>" + ROH_LESEN + "</script></html>",
    # a) Makro (from … import … as): das Zahlenfeld kommt aus dem Makro, die Seite liest es roh
    "makros_zahl.html": "{% macro zahlfeld() %}" + ZAHL_FELD + "{% endmacro %}",
    "seite_makro.html": '{% from "makros_zahl.html" import zahlfeld as zf %}<html>{{ zf() }}<script>' + ROH_LESEN + "</script></html>",
    # b) Unterordner
    "teile/seite_unterordner.html": '<html><input id="a" type="number"></html>',
    # c) Basis-Template, beide Richtungen: Feld in der Basis, gelesen im Block -- und gelesen in der Basis, Feld im Block
    "basis_zahl.html": "<html>" + ZAHL_FELD + "{% block inhalt %}{% endblock %}</html>",
    "kind_zahl.html": '{% extends "basis_zahl.html" %}{% block inhalt %}<script>' + ROH_LESEN + "</script>{% endblock %}",
    "basis_zahl_skript.html": "<html>{% block inhalt %}{% endblock %}<script>" + ROH_LESEN.replace("menge", "menge2") + "</script></html>",
    "kind_zahl_feld.html": '{% extends "basis_zahl_skript.html" %}{% block inhalt %}' + ZAHL_FELD.replace("menge", "menge2")
                           + "{% endblock %}",
}
ZAHL_ERWARTET = {
    "direkt": [("seite_direkt.html", "roh")],
    "makro": [("seite_makro.html", "roh")],
    "unterordner": [("teile/seite_unterordner.html", "type-number")],
    "basis": [("kind_zahl.html", "roh"), ("basis_zahl_skript.html", "roh")],
}


@pytest.mark.parametrize("fall", FAELLE)
def test_gegenprobe_vorlagen_zahlen(vorlagen, fall):
    vorlagen(ZAHL_VORLAGEN)
    funde = vz.alle_funde()
    gefunden = [(f.vorlage, f.art) for f in funde]
    for erwartet in ZAHL_ERWARTET[fall]:
        assert erwartet in gefunden, f"{fall}: {erwartet} nicht gefunden -- gefunden: {[str(f) for f in funde]}"


def test_zahlen_kein_fehlalarm_fuer_ein_basis_template(vorlagen):
    """Eine Basis, die zahlFeld() nutzt, während die Seite _zahl.html einbindet, ist in Ordnung: geprüft wird die zusammengesetzte
    Seite. Eine Seite, deren Basis zahlFeld() nutzt und die den Baustein nirgends einbindet, nicht."""
    vorlagen({"_zahl.html": "<script>function zahlFeld(){}</script>",
              "basis.html": "<html>{% block inhalt %}{% endblock %}<script>zahlFeld('a')</script></html>",
              "mit.html": '{% extends "basis.html" %}{% block inhalt %}{% include "_zahl.html" %}{% endblock %}',
              "basis2.html": "<html>{% block inhalt %}{% endblock %}<script>zahlFeld('a')</script></html>",
              "ohne.html": '{% extends "basis2.html" %}{% block inhalt %}x{% endblock %}'})
    assert vz.ohne_einbindung() == ["ohne.html"]


@pytest.mark.parametrize("seite_ohne_baustein", [False, True])
def test_zahlen_zahlenfeld_im_basis_template(vorlagen, seite_ohne_baustein):
    """Ein Zahlenfeld im Basis-Template verlangt _zahl.html in jeder Seite, die von ihr erbt -- nicht in der Basis selbst."""
    dateien = {"_zahl.html": "<script>function zahlFeld(){}</script>",
               "basis_feld.html": "<html>" + ZAHL_FELD + "{% block inhalt %}{% endblock %}</html>",
               "mit_feld.html": '{% extends "basis_feld.html" %}{% block inhalt %}{% include "_zahl.html" %}{% endblock %}'}
    if seite_ohne_baustein:
        dateien["ohne_feld.html"] = '{% extends "basis_feld.html" %}{% block inhalt %}x{% endblock %}'
    vorlagen(dateien)
    if seite_ohne_baustein:
        with pytest.raises(AssertionError, match=re.escape("['ohne_feld.html']")):
            t414.test_jede_seite_mit_zahlenfeld_bindet_den_baustein_ein()
    else:
        t414.test_jede_seite_mit_zahlenfeld_bindet_den_baustein_ein()


# ---------------------------------------------------------------------------
# vorlagen_navigation: Navigation zu einem Wert aus der Adresse ohne sicheresZiel()
# ---------------------------------------------------------------------------

PARAMS = "const params=new URLSearchParams(location.search)"
WEITER = "<button onclick=\"location.href=params.get('n')\">weiter</button>"

NAV_VORLAGEN = {
    "seite_direkt.html": "<html><script>" + PARAMS + "</script>" + WEITER + "</html>",
    # a) Makro (import … as, ein Makro ruft ein Makro aus einer zweiten Datei): der Handler im Makro nimmt den Wert der Seite
    "makros_knopf.html": "{% macro knopf() %}" + WEITER + "{% endmacro %}",
    "makros_nav.html": '{% import "makros_knopf.html" as k %}{% macro weiter() %}<nav>{{ k.knopf() }}</nav>{% endmacro %}',
    "seite_makro.html": '{% import "makros_nav.html" as nav %}<html><script>' + PARAMS + "</script>{{ nav.weiter() }}</html>",
    # b) Unterordner
    "teile/seite_unterordner.html": "<html><script>" + PARAMS + "</script>" + WEITER + "</html>",
    # c) Basis-Template (mit {{ super() }}): der Handler steht in der Basis, die Funktion mit dem Wert aus der Adresse im Block
    "basis_nav.html": ("<html>{% block skripte %}<script>const leer=1</script>{% endblock %}"
                       "<button onclick=\"location.href=ziel()\">x</button></html>"),
    "kind_nav.html": ('{% extends "basis_nav.html" %}{% block skripte %}{{ super() }}'
                      "<script>function ziel(){return location.hash.slice(1)}</script>{% endblock %}"),
}
NAV_ERWARTET = {
    "direkt": "seite_direkt.html",
    "makro": "makros_knopf.html",
    "unterordner": "teile/seite_unterordner.html",
    "basis": "basis_nav.html",
}


@pytest.mark.parametrize("fall", FAELLE)
def test_gegenprobe_vorlagen_navigation(vorlagen, fall):
    vorlagen(NAV_VORLAGEN)
    rot = [n for v in vn.alle_vorlagen() for n in vn.navigationen_der_vorlage(v) if n.aus_adresse and not n.geprueft]
    dateien = [n.stelle.rsplit(":", 1)[0] for n in rot]
    assert NAV_ERWARTET[fall] in dateien, f"{fall}: ungeprüfte Navigation nicht gefunden -- gefunden: {[n.stelle for n in rot]}"


# ---------------------------------------------------------------------------
# node-Attrappe (test_v334 seite()): Bausteine des Basis-Templates, Reihenfolge wie im Browser
# ---------------------------------------------------------------------------

ATTRAPPE_VORLAGEN = {
    "_fehlertext.html": "<script>const FEHLER_PRAEFIX='Fehler: ';function fehlerText(b){return FEHLER_PRAEFIX+b.detail}</script>",
    "_auswahl.html": "<script>const AUSWAHL_TEXT=FEHLER_PRAEFIX+'Auswahl';</script>",
    # Der Baustein steht nur im Basis-Template
    "basis_attrappe.html": '<html>{% include "_fehlertext.html" %}{% block inhalt %}{% endblock %}</html>',
    "kind_attrappe.html": ('{% extends "basis_attrappe.html" %}{% block inhalt %}'
                           "<script>function zeigen(){return fehlerText({detail:'x'})}\nSTART</script>{% endblock %}"),
    # Reihenfolge: im Browser läuft _fehlertext.html vor _auswahl.html (sonst fehlt FEHLER_PRAEFIX)
    "reihenfolge.html": ('<html>{% include "_fehlertext.html" %}{% include "_auswahl.html" %}'
                         "<script>function zeigen(){return AUSWAHL_TEXT}\nSTART</script></html>"),
}


@nur_mit_node
@pytest.mark.parametrize("vorlage, erwartet", [("kind_attrappe.html", "Fehler: x"), ("reihenfolge.html", "Fehler: Auswahl")])
def test_gegenprobe_node_attrappe(vorlagen, vorlage, erwartet):
    vorlagen(ATTRAPPE_VORLAGEN)
    ergebnis = t334.im_browser(t334.seite(vorlage, "START"), "return zeigen();")
    assert ergebnis["ergebnis"] == erwartet


# ---------------------------------------------------------------------------
# _speichern.html: das Include darf im Basis-Template der Seite stehen
# ---------------------------------------------------------------------------

LESEN = "<script>async function f(){await lesen('x',()=>api('/a'),d=>{})}</script>"

SPEICHERN_VORLAGEN = {
    "_speichern.html": "<script>function lesen(){}</script>",
    "basis_s.html": '<html>{% include "_speichern.html" %}{% block inhalt %}{% endblock %}</html>',
    "kind_s.html": '{% extends "basis_s.html" %}{% block inhalt %}' + LESEN + "{% endblock %}",
    "basis_ohne.html": "<html>{% block inhalt %}{% endblock %}</html>",
    "kind_ohne.html": '{% extends "basis_ohne.html" %}{% block inhalt %}' + LESEN + "{% endblock %}",
    "basis_unbenutzt.html": '<html>{% include "_speichern.html" %}{% block inhalt %}{% endblock %}</html>',
    "kind_leer.html": '{% extends "basis_unbenutzt.html" %}{% block inhalt %}x{% endblock %}',
    "teile/seite.html": "<html>" + LESEN + "</html>",
}


@pytest.mark.parametrize("name", ["kind_s.html", "basis_s.html"])
def test_speichern_include_im_basis_template_genuegt(vorlagen, name):
    """Die Seite nutzt lesen(), ihr Basis-Template bindet den Baustein ein -- und die Basis bindet ihn für diese Seite ein."""
    vorlagen(SPEICHERN_VORLAGEN)
    t398.test_templates_using_the_baustein_include_it(name)


@pytest.mark.parametrize("name, meldung", [
    ("kind_ohne.html", "nutzt lesen()/speichern()"),          # weder die Seite noch ihre Basis bindet ein
    ("basis_unbenutzt.html", "nutzt es aber selbst nicht"),   # keine Seite, die von ihr erbt, nutzt den Baustein
    ("teile/seite.html", "nutzt lesen()/speichern()"),        # im Unterordner
])
def test_speichern_fehlendes_oder_unnoetiges_include_bleibt_rot(vorlagen, name, meldung):
    vorlagen(SPEICHERN_VORLAGEN)
    with pytest.raises(AssertionError, match=re.escape(meldung)):
        t398.test_templates_using_the_baustein_include_it(name)


# ---------------------------------------------------------------------------
# Das Zusammensetzen selbst (tests/vorlagen_js.py::zusammensetzen())
# ---------------------------------------------------------------------------

AUFBAU_VORLAGEN = {
    "_teil.html": "<p>Teil</p>",
    "basis_teil.html": "<i>{% block x %}x{% endblock %}</i>",
    "teile/_teil_erbt.html": '{% extends "basis_teil.html" %}{% block x %}[X aus Teil]{% endblock %}',
    "basis.html": ('<html>{# wie in _topbar.html: {% include "fehlt.html" %} #}{% block kopf %}<head>K</head>{% endblock %}<body>'
                   '{% block inhalt %}<main>{% block innen %}I{% endblock %}</main>{% endblock %}{% include "_teil.html" %}</body></html>'),
    "mitte.html": '{% extends "basis.html" %}{% block kopf %}{{ super() }}<meta>{% endblock %}{% block innen %}M{% endblock %}',
    "seite.html": ('{% extends "mitte.html" %}{# {% include "fehlt.html" %} #}{% block innen %}S{{ super() }}'
                   '{% include "teile/_teil_erbt.html" %}{% endblock %}ignoriert'),
}


def test_zusammensetzen_wie_jinja(vorlagen):
    """Ohne Ausdrücke ist die zusammengesetzte Seite genau das, was Jinja zeichnet (bis auf Kommentare, die Jinja weglässt): zwei
    Basis-Templates, verschachtelte Blöcke, {{ super() }} über zwei Stufen, ein Include im Block, das selbst erbt, ein Include im
    Kommentar (setzt Jinja nicht ein, bis 1.8.122 taten es die Scanner -- in _topbar.html), Text außerhalb der Blöcke."""
    import jinja2

    wurzel = vorlagen(AUFBAU_VORLAGEN)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(wurzel)), keep_trailing_newline=True)
    for name in ("seite.html", "mitte.html", "basis.html", "teile/_teil_erbt.html"):
        text, herkunft = vj.zusammensetzen(name)
        assert re.sub(r"\{#.*?#\}", "", text, flags=re.S) == env.get_template(name).render(), name
        for start, ende, datei, versatz in herkunft:  # jede Stelle zeigt auf ihre Datei
            assert text[start:ende] == (wurzel / datei).read_text(encoding="utf-8")[versatz:versatz + ende - start]
    assert vj.zusammensetzen("seite.html")[0] == ('<html>{# wie in _topbar.html: {% include "fehlt.html" %} #}<head>K</head><meta>'
                                                  "<body><main>SM<i>[X aus Teil]</i></main><p>Teil</p></body></html>")


def test_seitentext_laesst_includes_stehen(vorlagen):
    vorlagen(AUFBAU_VORLAGEN)
    text, _ = vj.seitentext("seite.html")
    assert text == ('<html>{# wie in _topbar.html: {% include "fehlt.html" %} #}<head>K</head><meta><body><main>SM'
                    '{% include "teile/_teil_erbt.html" %}</main>{% include "_teil.html" %}</body></html>')


def test_makros_kommen_an_die_stelle_des_imports(vorlagen):
    wurzel = vorlagen({
        "makros/knopf.html": "{% macro knopf() %}<button>K</button>{% endmacro %}",
        "makros/feld.html": ('{% import "makros/knopf.html" as k %}<p>oben, nicht im Import</p>'
                             '{% macro feld(id) %}<input id="{{ id }}">{{ k.knopf() }}{% endmacro %}'),
        "seite.html": ('{% from "makros/feld.html" import feld %}{% import "makros/feld.html" as f %}<form>{{ feld("a") }}'
                       '{% call feld("b") %}x{% endcall %}</form>'),
    })
    text, herkunft = vj.zusammensetzen("seite.html")
    assert text == ('{% macro knopf() %}<button>K</button>{% endmacro %}{% macro feld(id) %}<input id="{{ id }}">{{ k.knopf() }}'
                    '{% endmacro %}<form>{{ feld("a") }}{% call feld("b") %}x{% endcall %}</form>')  # je Datei einmal
    assert vj.ort(herkunft, text.index("<input"), wurzel) == ("makros/feld.html", 1)
    assert "makros/knopf.html" in vj.vorlagen_verweise("makros/feld.html", wurzel)


def test_seiten_und_unterordner(vorlagen):
    wurzel = vorlagen({**AUFBAU_VORLAGEN, "makros/feld.html": "{% macro f() %}{% endmacro %}",
                       "mit_makro.html": '{% import "makros/feld.html" as m %}x'})
    assert vj.alle_vorlagen(wurzel) == ["_teil.html", "basis.html", "basis_teil.html", "makros/feld.html", "mit_makro.html",
                                        "mitte.html", "seite.html", "teile/_teil_erbt.html"]
    assert vj.seiten(wurzel) == ["mit_makro.html", "seite.html"]
    assert vj.basis_kette("seite.html", wurzel) == ["mitte.html", "basis.html"]


@pytest.mark.parametrize("text, meldung", [
    ("{% include name %}", "fester Vorlagenname"),
    ("{% extends layout %}", "fester Vorlagenname"),
    ('{% include ["a.html", "b.html"] %}', "fester Vorlagenname"),
    ('{% extends "a.html" %}{% extends "b.html" %}', "zweites"),
    ('{% if x %}{% extends "a.html" %}{% endif %}', "bedingtes"),
    ("{% block a %}{% endblock %}{% block a %}{% endblock %}", "zweimal"),
    ("{% if x %}", "ohne Ende"),
])
def test_was_sich_nicht_zusammensetzen_laesst_ist_rot(vorlagen, text, meldung):
    vorlagen({"a.html": "a", "b.html": "b", "x.html": text})
    with pytest.raises(vj.VorlagenFehler, match=meldung):
        vj.zusammensetzen("x.html")


def test_schleifen_sind_rot(vorlagen):
    vorlagen({"a.html": '{% include "b.html" %}', "b.html": '{% include "a.html" %}',
              "c.html": '{% extends "d.html" %}', "d.html": '{% extends "c.html" %}'})
    with pytest.raises(vj.JsFehler, match="Include-Schleife"):
        vj.zusammensetzen("a.html")
    with pytest.raises(vj.VorlagenFehler, match="Schleife über extends"):
        vj.zusammensetzen("c.html")


# ---------------------------------------------------------------------------
# Kein Test listet den Vorlagenordner an alle_vorlagen() vorbei
# ---------------------------------------------------------------------------

_LISTEN_METHODEN = {"glob", "rglob", "iterdir", "walk", "scandir"}
_LISTEN_FUNKTIONEN = {("os", "listdir"), ("os", "scandir"), ("os", "walk"), ("glob", "glob"), ("glob", "iglob")}
_ERLAUBT = ("tests/vorlagen_js.py", "alle_vorlagen")  # die eine Stelle, an der die Liste entsteht


_VORLAGEN_NAME = re.compile(r"templates(?:_dir)?", re.I)  # TEMPLATES, TEMPLATES_DIR, vj.TEMPLATES, pages.templates -- nicht checklist_templates


def _zeigt_auf_vorlagen(knoten, namen: set) -> bool:
    """Ein Ausdruck, der den Vorlagenordner bezeichnet: ein Text "templates" bzw. ".../app/templates", ein Name oder Attribut
    TEMPLATES/TEMPLATES_DIR/templates oder ein Name, dem so etwas zugewiesen wird."""
    for k in ast.walk(knoten):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            wert = k.value.replace("\\", "/").strip("/").lower()
            if wert == "templates" or wert.endswith("/templates") or "app/templates" in wert:
                return True
        elif isinstance(k, ast.Name) and (k.id in namen or _VORLAGEN_NAME.fullmatch(k.id)):
            return True
        elif isinstance(k, ast.Attribute) and _VORLAGEN_NAME.fullmatch(k.attr):
            return True
    return False


def _muster(aufruf) -> str:
    return " ".join(a.value for a in aufruf.args if isinstance(a, ast.Constant) and isinstance(a.value, str))


def vorlagen_auflistungen(quelle: str, datei: str) -> list[int]:
    """Zeilen, in denen eine Datei den Vorlagenordner auflistet (seit 1.8.124: glob, rglob, iterdir, walk, scandir, os.listdir,
    glob.glob, list_templates() -- auf dem Vorlagenordner oder mit einem Muster *.html), außer in vorlagen_js.alle_vorlagen()."""
    baum = ast.parse(quelle)
    zuweisungen = [(z, k.value) for k in ast.walk(baum) if isinstance(k, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and k.value is not None
                   for z in (k.targets if isinstance(k, ast.Assign) else [k.target]) if isinstance(z, ast.Name)]
    namen: set = set()
    while True:
        neu = {z.id for z, wert in zuweisungen if z.id not in namen and _zeigt_auf_vorlagen(wert, namen)}
        if not neu:
            break
        namen |= neu
    erlaubt = {id(k) for f in ast.walk(baum) if isinstance(f, ast.FunctionDef) and (datei, f.name) == _ERLAUBT for k in ast.walk(f)}
    zeilen = []
    for k in ast.walk(baum):
        if not isinstance(k, ast.Call) or id(k) in erlaubt:
            continue
        f = k.func
        if isinstance(f, ast.Attribute) and f.attr == "list_templates":  # Jinja: templates.env.list_templates()
            if _zeigt_auf_vorlagen(f.value, namen):
                zeilen.append(k.lineno)
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (f.value.id, f.attr) in _LISTEN_FUNKTIONEN \
                or isinstance(f, ast.Name) and f.id in {n for _, n in _LISTEN_FUNKTIONEN}:
            if any(_zeigt_auf_vorlagen(a, namen) for a in k.args) or ".html" in _muster(k):
                zeilen.append(k.lineno)
        elif isinstance(f, ast.Attribute) and f.attr in _LISTEN_METHODEN:
            if _zeigt_auf_vorlagen(f.value, namen) or ".html" in _muster(k):
                zeilen.append(k.lineno)
    return sorted(zeilen)


def test_kein_scanner_liest_nur_die_oberste_ebene():
    """Die Liste der Vorlagen kommt aus tests/vorlagen_js.py::alle_vorlagen() (auch Unterordner) -- ein glob("*.html") sähe sie nicht.
    Seit 1.8.124 (Festlegung 1.8.123 Nr. 9, Ergänzung): jede Datei unter tests/, jedes Auflisten des Vorlagenordners."""
    funde = []
    for pfad in sorted((ROOT / "tests").rglob("*.py")):
        datei = pfad.relative_to(ROOT).as_posix()
        funde += [f"{datei}:{zeile}" for zeile in vorlagen_auflistungen(pfad.read_text(encoding="utf-8"), datei)]
    assert not funde, "Vorlagen an vorlagen_js.alle_vorlagen() vorbei aufgelistet (Unterordner fehlen dann):\n" + "\n".join(funde)
