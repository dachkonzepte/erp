"""Version 1.8.124 -- Stufe 0b des Redesigns: die übrigen Strukturtests lesen Unterordner, Basis-Templates und Makros
(docs/archiv/testablauf-und-klicktests.md, "Strukturtests, Stufe 0b").

Festlegungen 1.8.123 bestätigt (17.10.2026), 1, 6 und 9 mit Ergänzungen:
- zu 9: der Wächter prüft jede Datei unter tests/ und erkennt jedes Auflisten des Vorlagenordners an vorlagen_js.alle_vorlagen() vorbei
  (glob, rglob, iterdir, os.listdir u. a.) -- test_v428::test_kein_scanner_liest_nur_die_oberste_ebene;
- zu 6: seiten() enthält genau die Vorlagen, die app/ per TemplateResponse ausliefert;
- zu 1: kein Makro-Parameter landet in type=, on…= oder href= -- was die Scanner prüfen, steht fest im Makro oder wörtlich in der Seite
  (über {% call %}); vorlagen_html.jinja_handler().

Gegenproben: je ein Fixture-Verstoß (tmp_path, nie app/ oder tests/ selbst). Wächter und Makro-Regel laufen über Einstiege, die es schon
in 1.8.123 gab (der Wächter-Test, alle_funde("jinja")) -- "rot vorher" ist ein übersehener Verstoß, kein Importfehler."""

import ast
from pathlib import Path

import pytest

import tests.test_v428_strukturtests_basis_und_makros as t428
import tests.vorlagen_html as vh
import tests.vorlagen_js as vj

# Die Dateien, die der Wächter in 1.8.123 las -- im Fixture-Projekt leer angelegt, damit derselbe Aufruf auch dort läuft.
LESER_1_8_123 = ["tests/vorlagen_js.py", "tests/vorlagen_html.py", "tests/vorlagen_zahlen.py", "tests/vorlagen_navigation.py",
                 "tests/test_v398_speichern_baustein.py", "tests/test_v399_abschliessen.py", "tests/test_v400_lesen_ueber_baustein.py",
                 "tests/test_v334_auswahl_restfaelle.py", "tests/test_v414_zahleneingaben.py"]

KOPF = "from pathlib import Path\nimport os, glob\nTEMPLATES = Path(__file__).resolve().parent.parent / 'app' / 'templates'\n"


# ---------------------------------------------------------------------------
# 2. Wächter: jedes Auflisten des Vorlagenordners unter tests/
# ---------------------------------------------------------------------------

def _projekt(tmp_path, monkeypatch, dateien: dict) -> Path:
    for name in LESER_1_8_123:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("", encoding="utf-8")
    for name, text in dateien.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    monkeypatch.setattr(t428, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize("datei, code", [
    ("tests/test_x.py", "def test_a():\n    return [p.name for p in TEMPLATES.iterdir()]\n"),
    ("tests/test_x.py", "def test_a():\n    return os.listdir(TEMPLATES)\n"),
    ("tests/test_x.py", "def test_a():\n    return list(TEMPLATES.rglob('*.html'))\n"),
    ("tests/test_x.py", "def test_a():\n    return sorted(TEMPLATES.glob('*.html'))\n"),          # glob, aber nicht in LESER
    ("tests/hilfe.py", "def liste():\n    root = Path(__file__).parents[1] / 'app' / 'templates'\n    return list(root.glob('*'))\n"),
    ("tests/test_x.py", "def test_a():\n    return glob.glob(str(TEMPLATES / '*.html'))\n"),
    ("tests/test_x.py", "def test_a():\n    return [e.name for e in os.scandir(TEMPLATES)]\n"),
    ("tests/test_x.py", "def test_a():\n    return list(os.walk(TEMPLATES))\n"),
    ("tests/test_x.py", "def test_a(templates):\n    return templates.env.list_templates()\n"),
    ("tests/vorlagen_html.py", "def alle():\n    return [p.name for p in TEMPLATES.iterdir()]\n"),  # in LESER, aber iterdir
], ids=["iterdir", "listdir", "rglob", "glob-ausserhalb", "glob-variable", "glob.glob", "scandir", "walk", "list_templates",
        "iterdir-in-leser"])
def test_gegenprobe_waechter_findet_jedes_auflisten(tmp_path, monkeypatch, datei, code):
    _projekt(tmp_path, monkeypatch, {datei: KOPF + code})
    zeile = (KOPF + code).count("\n", 0, (KOPF + code).index("return")) + 1
    with pytest.raises(AssertionError) as fehler:
        t428.test_kein_scanner_liest_nur_die_oberste_ebene()
    assert f"{datei}:{zeile}" in str(fehler.value)


def test_waechter_laesst_anderes_auflisten_stehen(tmp_path, monkeypatch):
    """Ordner außerhalb der Vorlagen, alle_vorlagen() selbst und sein einer glob in tests/vorlagen_js.py sind kein Fund."""
    _projekt(tmp_path, monkeypatch, {
        "tests/test_x.py": KOPF + (
            "import ast\nROOT = Path(__file__).parents[1]\n"
            "def test_a(tree, message, ablage):\n"
            "    a = [p for p in (ROOT / 'app').rglob('*.py')] + list((ROOT / 'alembic' / 'versions').glob('*_x.py'))\n"
            "    b = list(ablage.iterdir()) + list(ast.walk(tree)) + list(message.walk())\n"
            "    from tests import vorlagen_js\n    return a, b, vorlagen_js.alle_vorlagen(TEMPLATES)\n"),
        "tests/vorlagen_js.py": KOPF + ("def alle_vorlagen(wurzel=None):\n    wurzel = TEMPLATES if wurzel is None else wurzel\n"
                                        "    return sorted(p.relative_to(wurzel).as_posix() for p in wurzel.rglob('*.html'))\n"),
    })
    t428.test_kein_scanner_liest_nur_die_oberste_ebene()


# ---------------------------------------------------------------------------
# 4. Makro-Regel: kein Makro-Parameter in type=, on…= oder href=
# ---------------------------------------------------------------------------

@pytest.fixture
def vorlagen(tmp_path, monkeypatch):
    for modul in (vj, vh):
        monkeypatch.setattr(modul, "TEMPLATES", tmp_path)
    vh._CACHE.clear()

    def schreiben(dateien: dict) -> Path:
        for name, text in dateien.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(text, encoding="utf-8")
        vh._CACHE.clear()
        return tmp_path

    yield schreiben
    vh._CACHE.clear()


@pytest.mark.parametrize("makro", [
    '{% macro feld(typ) %}<input id="a" type="{{ typ }}">{% endmacro %}',
    '{% macro link(ziel) %}<a href="{{ ziel }}">x</a>{% endmacro %}',
    '{% macro knopf(x) %}<button onclick="{% if x %}a(){% else %}b(){% endif %}">k</button>{% endmacro %}',
    '{% macro box(attrs) %}<div {{ attrs }}>x</div>{% endmacro %}',
    '{% macro knopf(ereignis) %}<button on{{ ereignis }}="a()">k</button>{% endmacro %}',
    '{% macro link() %}<a href="{{ caller() }}">x</a>{% endmacro %}',
    '{% macro feld(typ) %}<input id="a" type={{ typ }}>{% endmacro %}',
], ids=["type", "href", "on-mit-if", "attribute", "attributname", "caller-in-href", "type-ohne-anfuehrungszeichen"])
def test_gegenprobe_makro_regel(vorlagen, makro):
    vorlagen({"makros/formular.html": makro, "seite.html": '{% import "makros/formular.html" as f %}<html></html>'})
    funde = [f for f in vh.alle_funde("jinja") if f.datei == "makros/formular.html"]
    assert funde, f"Makro-Parameter in type=/on…=/href= nicht gefunden: {makro}"


def test_makro_regel_laesst_feste_werte_und_andere_attribute_stehen(vorlagen):
    vorlagen({
        "makros/formular.html": ('{% macro feld(id, klasse, wert, beschriftung, pflicht) %}<label for="{{ id }}">{{ beschriftung }}</label>'
                                 '<input id="{{ id }}" class="{{ klasse }}" type="text" inputmode="decimal" data-zahl value="{{ wert }}"'
                                 ' data-feld="{{ beschriftung }}" onchange="speichern()" {% if pflicht %}required{% endif %}>'
                                 '<a href="/kunden">Kunden</a>{{ caller() }}{% endmacro %}'),
        "seite.html": '<a href="{{ url }}" type="{{ t }}">kein Makro</a>',
    })
    assert vh.alle_funde("jinja") == []


def test_kein_makro_parameter_in_type_on_href():
    """Die Makro-Regel an den echten Vorlagen (Festlegung 1.8.124): in keinem Makro Jinja in type=, on…= oder href= oder an der Stelle
    eines Attributnamens. Heute gibt es keine Makros -- der Test gilt ab dem ersten."""
    assert [f"{f.stelle}: {f.ausdruck}" for f in vh.alle_funde("jinja") if f.funktion.startswith("<makro")] == []


# ---------------------------------------------------------------------------
# 3. Seiten-Abgleich: seiten() = was app/ per TemplateResponse ausliefert
# ---------------------------------------------------------------------------

APP = Path(__file__).resolve().parent.parent / "app"
VORLAGEN = APP / "templates"


def _ist_template_response(k) -> bool:
    return isinstance(k, (ast.Attribute, ast.Name)) and getattr(k, "attr", getattr(k, "id", None)) == "TemplateResponse"


def _texte(knoten, funktion) -> list[str] | None:
    """Die Vorlagennamen, die ein Ausdruck sein kann: Text, a if b else c, ein Name über seine Zuweisungen in derselben Funktion.
    None, wenn sich ein Teil nicht auflösen lässt."""
    if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
        return [knoten.value]
    if isinstance(knoten, ast.IfExp):
        a, b = _texte(knoten.body, funktion), _texte(knoten.orelse, funktion)
        return None if a is None or b is None else a + b
    if isinstance(knoten, ast.Name) and funktion is not None:
        werte = [z.value for z in ast.walk(funktion) if isinstance(z, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == knoten.id for t in z.targets)]
        teile = [_texte(w, None) for w in werte]
        return None if not teile or any(t is None for t in teile) else [n for t in teile for n in t]
    return None


def ausgelieferte_vorlagen(app: Path) -> tuple[dict, list]:
    """Vorlage -> [Stellen] je Name, den ein Aufruf von TemplateResponse unter app/ zeichnet (name=, sonst das Argument nach request;
    auch run_in_threadpool(templates.TemplateResponse, …)), und die Stellen, deren Name sich nicht auflösen lässt."""
    gefunden, offen = {}, []
    for pfad in sorted(app.rglob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        eltern = {kind: k for k in ast.walk(baum) for kind in ast.iter_child_nodes(k)}
        for k in ast.walk(baum):
            if not isinstance(k, ast.Call) or not any(_ist_template_response(t) for t in [k.func, *k.args]):
                continue
            funktion = eltern.get(k)
            while funktion is not None and not isinstance(funktion, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funktion = eltern.get(funktion)
            wert = next((w.value for w in k.keywords if w.arg == "name"), None)
            if wert is None:
                argumente = [a for a in k.args if not _ist_template_response(a)]
                wert = argumente[1] if len(argumente) >= 2 else None
            stelle = f"{pfad.relative_to(app.parent).as_posix()}:{k.lineno}"
            namen = _texte(wert, funktion) if wert is not None else None
            if not namen:
                offen.append(stelle)
            for name in namen or []:
                gefunden.setdefault(name, []).append(stelle)
    return gefunden, offen


def seiten_abgleich(app: Path, vorlagen: Path) -> tuple[list, list, list]:
    """(nicht auflösbare Stellen, ausgeliefert, aber keine Seite, Seite, aber nie ausgeliefert)."""
    ausgeliefert, offen = ausgelieferte_vorlagen(app)
    seiten = set(vj.seiten(vorlagen))
    return offen, sorted(set(ausgeliefert) - seiten), sorted(seiten - set(ausgeliefert))


def test_seiten_sind_genau_die_ausgelieferten_vorlagen():
    """Festlegung 1.8.123 Nr. 6, Ergänzung: seiten() -- was die Strukturtests als Seite prüfen -- enthält genau die Vorlagen, die app/
    per TemplateResponse ausliefert. Eine ausgelieferte Vorlage, die eine andere erweitert, einbindet oder importiert (oder "_" im Namen
    trägt), prüften sie nie als Seite; eine Seite, die niemand ausliefert, ist toter Code oder ein Name, den die Suche nicht auflöst."""
    offen, keine_seite, nie_ausgeliefert = seiten_abgleich(APP, VORLAGEN)
    assert offen == [], "TemplateResponse mit einem Namen, der sich nicht auflösen lässt (fester Text, a if b else c): " + ", ".join(offen)
    assert keine_seite == [], "Ausgeliefert, aber für die Strukturtests keine Seite: " + ", ".join(keine_seite)
    assert nie_ausgeliefert == [], "Seite, die app/ nirgends ausliefert: " + ", ".join(nie_ausgeliefert)
    assert len(vj.seiten(VORLAGEN)) >= 50 and len(ausgelieferte_vorlagen(APP)[0]) >= 50  # die Suche findet etwas


AUSLIEFERUNG = ("from fastapi.templating import Jinja2Templates\ntemplates = Jinja2Templates(directory='templates')\n"
                "def a(request):\n    return templates.TemplateResponse(request=request, name='seite.html', context={})\n"
                "def b(request, feld):\n    vorlage = 'x_feld.html' if feld else 'x.html'\n"
                "    return templates.TemplateResponse(request=request, name=vorlage, context={})\n"
                "async def c(request):\n    return await run_in_threadpool(templates.TemplateResponse, request=request, name='fehler.html')\n")
SEITEN = {"basis.html": "<html>{% block inhalt %}{% endblock %}</html>", "seite.html": '{% extends "basis.html" %}',
          "x.html": "x", "x_feld.html": "x", "fehler.html": "f", "_teil.html": "t"}


@pytest.mark.parametrize("zusatz, vorlagen_zusatz, erwartet", [
    ("def d(request):\n    return templates.TemplateResponse(request=request, name='basis.html', context={})\n", {}, (1, "basis.html")),
    ("", {"waise.html": "w"}, (2, "waise.html")),
    ("def e(request, name):\n    return templates.TemplateResponse(request=request, name=name, context={})\n", {}, (0, "app/routers/a.py:")),
    ("def f(request):\n    return templates.TemplateResponse(request=request, name='_teil.html', context={})\n", {}, (1, "_teil.html")),
], ids=["basis-ausgeliefert", "seite-nie-ausgeliefert", "name-nicht-aufloesbar", "teilvorlage-ausgeliefert"])
def test_gegenprobe_seiten_abgleich(tmp_path, zusatz, vorlagen_zusatz, erwartet):
    app = tmp_path / "app"
    (app / "routers").mkdir(parents=True)
    (app / "routers" / "a.py").write_text(AUSLIEFERUNG + zusatz, encoding="utf-8")
    for name, text in {**SEITEN, **vorlagen_zusatz}.items():
        (app / "templates" / name).parent.mkdir(parents=True, exist_ok=True)
        (app / "templates" / name).write_text(text, encoding="utf-8")
    abgleich = seiten_abgleich(app, app / "templates")
    teil, name = erwartet
    assert any(eintrag.startswith(name) for eintrag in abgleich[teil]), abgleich
    assert [len(x) for x in abgleich] == [int(i == teil) for i in range(3)], abgleich  # nur dieser Verstoß


def test_seiten_abgleich_ohne_verstoss(tmp_path):
    app = tmp_path / "app"
    (app / "routers").mkdir(parents=True)
    (app / "routers" / "a.py").write_text(AUSLIEFERUNG, encoding="utf-8")
    for name, text in SEITEN.items():
        (app / "templates" / name).parent.mkdir(parents=True, exist_ok=True)
        (app / "templates" / name).write_text(text, encoding="utf-8")
    assert seiten_abgleich(app, app / "templates") == ([], [], [])


# ---------------------------------------------------------------------------
# bindet_ein(): das Include selbst oder im Basis-Template
# ---------------------------------------------------------------------------

def test_bindet_ein_selbst_oder_im_basis_template(tmp_path):
    for name, text in {"_b.html": "b", "_teil.html": '{% include "_b.html" %}', "oben.html": '{% include "_b.html" %}{% block x %}{% endblock %}',
                       "mitte.html": '{% extends "oben.html" %}', "kind.html": '{% extends "mitte.html" %}',
                       "selbst.html": '{% include "_b.html" %}', "kommentar.html": '{# {% include "_b.html" %} #}',
                       "ueber_teil.html": '{% include "_teil.html" %}'}.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert [vj.bindet_ein(n, "_b.html", tmp_path) for n in ("selbst.html", "oben.html", "mitte.html", "kind.html")] == [True] * 4
    assert vj.bindet_ein("kommentar.html", "_b.html", tmp_path) is False    # ein Kommentar zeichnet Jinja nicht
    assert vj.bindet_ein("ueber_teil.html", "_b.html", tmp_path) is False   # über eine Teilvorlage zählt nicht (wie bisher)
