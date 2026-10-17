"""Version 1.8.125 -- Stufe 0c des Redesigns: Restarbeiten am Sicherheitsnetz (docs/archiv/testablauf-und-klicktests.md,
"Strukturtests, Stufe 0c").

1. Ein Test verlangt ein Include nur über tests/vorlagen_js.py::bindet_ein() (selbst oder im Basis-Template) -- nie per Textvergleich:
   ein '{% include "_x.html" %}' in text sieht ein Include im Basis-Template nicht und hält eines im Kommentar für echt. Der Wächter
   unten findet jeden Textvergleich unter tests/.
2. Klicktest-Wackler (scripts/cdp_klicktest.py): _freier_port() nahm einen Port aus dem Bereich der kurzlebigen Ports des
   Betriebssystems; fragte _warte_auf() ihn ab, bevor Chrome dort lauschte, konnte die Verbindung zufällig denselben Port als Quellport
   bekommen und sich mit sich selbst verbinden -- die Anfrage kam als Antwort zurück (http.client.BadStatusLine: GET /json/version
   HTTP/1.1), der Klicktest brach ab (17.10.2026, klicktest_mahnen_endrechnung). Die Tests unten erzeugen den Selbstanschluss gezielt."""

import ast
import http.client
import http.server
import importlib.util
import re
import socket
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


# ---------------------------------------------------------------------------
# Wächter: kein Include per Textvergleich
# ---------------------------------------------------------------------------

_INCLUDE_TAG = re.compile(r"\{" + r"%-?\s*include\b")  # zusammengesetzt: sonst meldete der Wächter sein eigenes Muster
_INCLUDE_MUSTER = re.compile(r"(?:\\\{|\{)%.*include", re.S)  # ein Regex, der ein Include-Tag sucht
_TEXT_METHODEN = {"count", "find", "rfind", "index", "rindex", "startswith", "endswith", "split", "partition", "rpartition", "replace"}
_RE_FUNKTIONEN = {"search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "split", "compile"}


def include_textvergleiche(quelle: str) -> list[int]:
    """Zeilen, in denen ein Test ein Include per Textvergleich prüft: ein Include-Tag als Text (auch über eine Konstante) mit in/not in,
    in count()/find()/index()/… oder als Muster eines re-Aufrufs; ein Vorlagenname ("….html") mit in/not in gegen eingelesenen Text
    (read_text(), auch über eine Variable oder eine Funktion der Datei, die read_text() aufruft)."""
    baum = ast.parse(quelle)
    eltern = {kind: k for k in ast.walk(baum) for kind in ast.iter_child_nodes(k)}
    texte = {z.id: k.value.value for k in ast.walk(baum) if isinstance(k, ast.Assign) and isinstance(k.value, ast.Constant)
             and isinstance(k.value.value, str) for z in k.targets if isinstance(z, ast.Name)}
    liest = lambda k: any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "read_text"  # noqa: E731
                          for c in ast.walk(k))
    sammlung = (ast.List, ast.Set, ast.Dict, ast.Tuple, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    gibt_text = lambda r: r is not None and liest(r) and not isinstance(r, sammlung) and not (  # noqa: E731
        isinstance(r, ast.Call) and isinstance(r.func, ast.Name) and r.func.id in ("sorted", "list", "set", "tuple", "dict"))
    lesefunktionen = {f.name for f in ast.walk(baum) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and any(isinstance(r, ast.Return) and gibt_text(r.value) for r in ast.walk(f))}

    def include(k) -> bool:
        wert = k.value if isinstance(k, ast.Constant) else texte.get(k.id) if isinstance(k, ast.Name) else None
        return isinstance(wert, str) and bool(_INCLUDE_TAG.search(wert))

    def umgebung(k):
        while k in eltern and not isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef)):
            k = eltern[k]
        return k if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef)) else baum

    def vorlagentext(k, gesehen=frozenset()) -> bool:
        """Eingelesener Text: ein read_text()-Aufruf, eine Lesefunktion der Datei oder ein Name, dem so etwas zugewiesen wird."""
        if gibt_text(k) or any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in lesefunktionen
                               for c in ast.walk(k)):
            return True
        if isinstance(k, ast.Name) and k.id not in gesehen:
            return any(isinstance(z, ast.Assign) and any(isinstance(t, ast.Name) and t.id == k.id for t in z.targets)
                       and vorlagentext(z.value, gesehen | {k.id}) for z in ast.walk(umgebung(k)))
        return False

    zeilen = []
    for k in ast.walk(baum):
        if isinstance(k, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in k.ops):
            name = k.left.value if isinstance(k.left, ast.Constant) and isinstance(k.left.value, str) else ""
            if include(k.left) or (name.endswith(".html") and any(vorlagentext(c) for c in k.comparators)):
                zeilen.append(k.lineno)
        elif isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute):
            if k.func.attr in _TEXT_METHODEN and any(include(a) for a in k.args):
                zeilen.append(k.lineno)
            elif isinstance(k.func.value, ast.Name) and k.func.value.id == "re" and k.func.attr in _RE_FUNKTIONEN and k.args \
                    and isinstance(k.args[0], ast.Constant) and isinstance(k.args[0].value, str) and _INCLUDE_MUSTER.search(k.args[0].value):
                zeilen.append(k.lineno)
    return sorted(set(zeilen))


def test_kein_test_prueft_ein_include_per_textvergleich():
    """Festlegung 1.8.125: ein Include verlangt ein Test nur über vorlagen_js.bindet_ein() -- jede Datei unter tests/."""
    funde = []
    for pfad in sorted((ROOT / "tests").rglob("*.py")):
        funde += [f"{pfad.relative_to(ROOT).as_posix()}:{z}" for z in include_textvergleiche(pfad.read_text(encoding="utf-8"))]
    assert not funde, "Include per Textvergleich geprüft -- vorlagen_js.bindet_ein() nehmen (selbst oder im Basis-Template):\n" + \
        "\n".join(funde)


KOPF = "import re\nfrom pathlib import Path\nTEMPLATES = Path('app/templates')\n"

# Die alten Fassungen der vier Include-Prüfungen (1.8.124, wörtlich) und weitere Formen.
TEXTVERGLEICHE = {
    "alt_v314": "def test_a():\n    assert '{% include \"_berlin_date.html\" %}' in (TEMPLATES / \"dashboard.html\").read_text(encoding=\"utf-8\")\n",
    "alt_v338": ("def test_a():\n    source = (TEMPLATES / \"order.html\").read_text(encoding=\"utf-8\")\n"
                 "    assert '{% include \"_fehlertext.html\" %}' in source\n"),
    "alt_v340": ("def test_a():\n    mappe = (TEMPLATES / \"project_folder.html\").read_text(encoding=\"utf-8\")\n"
                 "    assert '{% include \"_fehlertext.html\" %}' in mappe\n"),
    "alt_v418": ("def test_a():\n    mappe = (TEMPLATES / \"project_folder.html\").read_text(encoding=\"utf-8\")\n"
                 "    akte = (TEMPLATES / \"customer.html\").read_text(encoding=\"utf-8\")\n"
                 "    assert all('{% include \"_email_dispatch.html\" %}' in t for t in (mappe, akte))\n"),
    "not_in": "def test_a(text):\n    assert '{% include \"_x.html\" %}' not in text\n",
    "count": "def test_a(text):\n    assert text.count('{% include \"_x.html\" %}') == 1\n",
    "regex": "def test_a(text):\n    assert re.search(r'\\{%-?\\s*include\\s+\"_x\\.html\"', text)\n",
    "konstante": "INCLUDE = '{% include \"_x.html\" %}'\ndef test_a(text):\n    assert INCLUDE in text\n",
    "leerraum": "def test_a(text):\n    assert '{%- include \"_x.html\" -%}' in text\n",
    "name_gegen_text": "def test_a():\n    assert '_x.html' not in (TEMPLATES / 'mobil.html').read_text(encoding='utf-8')\n",
    "name_ueber_variable": "def test_a():\n    quelle = (TEMPLATES / 'mobil.html').read_text(encoding='utf-8')\n    assert '_x.html' not in quelle\n",
    "name_ueber_helfer": ("def _lies(name):\n    return (TEMPLATES / name).read_text(encoding='utf-8')\n"
                          "def test_a():\n    assert '_x.html' in _lies('mobil.html')\n"),
}


@pytest.mark.parametrize("code", list(TEXTVERGLEICHE.values()), ids=list(TEXTVERGLEICHE))
def test_gegenprobe_waechter_findet_jeden_textvergleich(tmp_path, monkeypatch, code):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(KOPF + code, encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    zeile = (KOPF + code).splitlines().index(next(z for z in (KOPF + code).splitlines() if "assert" in z)) + 1
    with pytest.raises(AssertionError, match=re.escape(f"tests/test_x.py:{zeile}")):
        test_kein_test_prueft_ein_include_per_textvergleich()


def test_waechter_laesst_anderes_stehen():
    """Fixture-Vorlagen mit Include, Vergleich ganzer Ausgaben, Mengen aus der Herkunft, Kommentare und bindet_ein() sind kein Fund."""
    code = KOPF + (
        "from tests import vorlagen_js\n"
        "DATEIEN = {'seite.html': '{% include \"_x.html\" %}<p>x</p>'}\n"
        "def test_a(text, herkunft):\n"
        "    '''Ein {% include \"_x.html\" %} im Docstring.'''\n"
        "    # assert '{% include \"_x.html\" %}' in text\n"
        "    assert text == '<html>{% include \"_x.html\" %}</html>'\n"
        "    assert '_x.html' in {d for _, _, d, _ in herkunft}\n"
        "    assert 'settings.html' in ['settings.html']\n"
        "    assert vorlagen_js.bindet_ein('seite.html', '_x.html', TEMPLATES)\n")
    assert include_textvergleiche(code) == []


# ---------------------------------------------------------------------------
# Klicktest-Wackler: TCP-Selbstanschluss in cdp_klicktest._warte_auf()
# ---------------------------------------------------------------------------

def _werkzeug():
    spec = importlib.util.spec_from_file_location("cdp_klicktest_test_v430", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _unbelegter_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _dynamische_ports() -> tuple[int, int]:
    """Der Bereich der kurzlebigen Ports, unabhängig vom Werkzeug gelesen (Windows: netsh; Vorgabe 49152–65535)."""
    try:
        aus = subprocess.run(["netsh", "int", "ipv4", "show", "dynamicport", "tcp"], capture_output=True, text=True, timeout=10).stdout
        start, anzahl = (int(z) for z in re.findall(r":\s*(\d+)", aus)[:2])
        return start, start + anzahl - 1
    except Exception:
        return 49152, 65535


@pytest.fixture
def selbstanschluss(monkeypatch):
    """Jede Verbindung nimmt ihren Zielport als Quellport: lauscht dort niemand, verbindet sie sich mit sich selbst -- gezielt, was sonst
    der Zufall tut (ein Quellport aus dem Bereich der kurzlebigen Ports, der gerade dem abgefragten entspricht)."""
    original = socket.create_connection

    def selbst(adresse, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, **kwargs):
        return original(adresse, timeout, (adresse[0], adresse[1]))

    monkeypatch.setattr(socket, "create_connection", selbst)


def test_der_selbstanschluss_laesst_sich_gezielt_erzeugen(selbstanschluss):
    """Derselbe Fehler wie im Klicktest: die eigene Anfrage kommt als Antwort zurück."""
    with pytest.raises(http.client.BadStatusLine, match="GET /json/version HTTP/1.1"):
        urllib.request.urlopen(f"http://127.0.0.1:{_unbelegter_port()}/json/version", timeout=2)


def test_warte_auf_uebersteht_einen_selbstanschluss(selbstanschluss):
    """Ein Selbstanschluss heißt "noch nicht bereit": _warte_auf() wartet weiter und meldet am Ende False -- es bricht nicht ab."""
    assert _werkzeug()._warte_auf(f"http://127.0.0.1:{_unbelegter_port()}/json/version", 1.5) is False


def test_warte_auf_erkennt_einen_lauschenden_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert _werkzeug()._warte_auf(f"http://127.0.0.1:{server.server_address[1]}/json/version", 5) is True
    finally:
        server.shutdown()
        server.server_close()


def test_freier_port_liegt_nicht_bei_den_kurzlebigen_ports():
    """Ein Port außerhalb des Bereichs, aus dem das Betriebssystem Quellports nimmt: dort kann eine Verbindung nie zufällig denselben
    Quellport bekommen -- der Selbstanschluss ist ausgeschlossen, nicht nur abgefangen."""
    werkzeug = _werkzeug()
    start, ende = _dynamische_ports()
    ports = {werkzeug._freier_port() for _ in range(30)}
    assert all(not start <= p <= ende for p in ports), f"Ports im Bereich {start}–{ende}: {sorted(p for p in ports if start <= p <= ende)}"
    for p in ports:  # wirklich frei: binden geht
        with socket.socket() as s:
            s.bind(("127.0.0.1", p))
