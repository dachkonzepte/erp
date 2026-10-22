"""Seit 1.9.28 (Stufe 2, Runde 9, Punkt 5): ein Hinweis der Oberfläche nennt keine internen Dateien, sondern sagt, was zu tun ist.

Anlass: „Benutzer und Zugriff“ warnte bei nur einem Administrator mit „… das Notfallskript auf dem Server (siehe CLAUDE.md) sind die
einzige Absicherung …“ -- wer die Seite benutzt, kennt CLAUDE.md nicht. Beim Durchsehen aller Vorlagen und Meldungen dazu gefunden: der
Hinweis zum Outlook-Kalender in den Einstellungen („vollständige Anleitung: docs/archiv/…“) und die Meldung eines abgelehnten
Graph-Aufrufs („siehe docs/archiv/…“).

    Vorlagen       sichtbarer Text und Skript ohne Kommentare ({# … #}, <!-- … -->, /* … */, // …): kein CLAUDE.md, docs/…, scripts/…, app/….py
    Meldungen      jeder Text in app/*.py ebenso, außer freistehenden Strings (Docstrings, Beschreibungen unter einer Zuweisung -- nie
                   angezeigt); Ausnahmen nur mit Grund in AUSNAHMEN: der Befehl, den die geschlossene Ersteinrichtung zeigt (er ist
                   selbst, was zu tun ist), und die Meldung eines Programmierfehlers an Entwickler (erreicht die Oberfläche nie)
"""

import ast
import re
from pathlib import Path

import pytest

from tests import vorlagen_js as vj

ROOT = Path(__file__).resolve().parents[1]
INTERN = re.compile(r"CLAUDE\.md|docs/[\w./-]+|scripts/[\w./-]+\.py|app/[\w./-]+\.py")
# (Datei, Fund) -> Grund
AUSNAHMEN = {
    ("app/anmeldeschranke.py", "scripts/erstes_konto.py"): "der Befehl der Ersteinrichtung ist selbst, was zu tun ist (Regel 30, seit 1.8.130)",
    ("app/document_frame.py", "app/document_frame.py"): "ValueError bei einem nicht eingetragenen Dokumenttyp -- ein Programmierfehler, die Oberfläche sieht nur die 500 ohne Text (serverfehler())",
}


def _ohne_kommentare(text: str) -> str:
    """Kommentare durch gleich viele Zeilenumbrüche ersetzt (Zeilennummern bleiben); // nur am Zeilenanfang oder nach einem Zeichen,
    das kein Teil einer Adresse oder eines Texts ist (https://… bleibt)."""
    leer = lambda m: "\n" * m.group(0).count("\n")  # noqa: E731
    text = re.sub(r"\{#.*?#\}", leer, text, flags=re.S)
    text = re.sub(r"<!--.*?-->", leer, text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", leer, text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`\\/])//.*$", r"\1", text)


def interne_dateien_in_vorlage(text: str) -> list[str]:
    ohne = _ohne_kommentare(text)
    return [f"{ohne.count(chr(10), 0, m.start()) + 1}: {m.group(0)}" for m in INTERN.finditer(ohne)]


def interne_dateien_in_python(quelle: str) -> list[tuple[int, str]]:
    """Funde in Texten des Codes; freistehende Strings (Docstrings, Beschreibungen unter einer Zuweisung) zählen nicht."""
    baum = ast.parse(quelle)
    docstrings = {id(k.value) for k in ast.walk(baum)
                  if isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str)}
    return [(k.lineno, m.group(0)) for k in ast.walk(baum)
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in docstrings for m in INTERN.finditer(k.value)]


def test_keine_vorlage_nennt_interne_dateien():
    funde = [f"{name}:{f}" for name in vj.alle_vorlagen() for f in interne_dateien_in_vorlage((vj.TEMPLATES / name).read_text(encoding="utf-8"))]
    assert funde == []


def test_keine_meldung_nennt_interne_dateien():
    funde, gesehen = [], set()
    for pfad in sorted((ROOT / "app").rglob("*.py")):
        rel = pfad.relative_to(ROOT).as_posix()
        for zeile, fund in interne_dateien_in_python(pfad.read_text(encoding="utf-8")):
            if (rel, fund) in AUSNAHMEN:
                gesehen.add((rel, fund))
            else:
                funde.append(f"{rel}:{zeile}: {fund}")
    assert funde == []
    assert gesehen == set(AUSNAHMEN)  # jede Ausnahme gibt es noch


def test_benutzer_und_zugriff_sagt_was_zu_tun_ist():
    seite = (vj.TEMPLATES / "users.html").read_text(encoding="utf-8")
    hinweis = re.search(r'<div id="soleAdminWarning"[^>]*>(.*?)</div>', seite, flags=re.S).group(1)
    assert "CLAUDE" not in hinweis and "siehe" not in hinweis
    for teil in ("nur einen aktiven Administrator", "Wiederherstellungscodes sicher auf", "lege einen zweiten Administrator an",
                 "wer Zugang zum Server hat"):
        assert teil in hinweis, teil


@pytest.mark.parametrize("text, fund", [
    ('<p>Notfallskript (siehe CLAUDE.md)</p>', ["1: CLAUDE.md"]),
    ("<div>\nAnleitung: docs/archiv/x.md</div>", ["2: docs/archiv/x.md"]),
    ("<script>meldung('scripts/reset_admin_2fa.py')</script>", ["1: scripts/reset_admin_2fa.py"]),
    ("<script>const t = `siehe app/routers/pages.py`;</script>", ["1: app/routers/pages.py"]),
])
def test_waechter_vorlage_findet(text, fund):
    assert interne_dateien_in_vorlage(text) == fund


def test_waechter_vorlage_laesst_kommentare_und_adressen_durch():
    text = ("{# siehe CLAUDE.md #}<!-- docs/archiv/a.md -->\n<style>/* CLAUDE.md */</style>\n<script>// siehe CLAUDE.md\n"
            "const u = 'https://example.org/docs';</script>")
    assert interne_dateien_in_vorlage(text) == []


def test_waechter_python():
    quelle = ('"""Modul, siehe CLAUDE.md."""\nWERTE = (1, 2)\n"""Beschreibung, siehe app/x.py"""\ndef f():\n'
              '    """docs/archiv/x.md"""\n    raise ValueError("siehe docs/archiv/x.md")\n')
    assert interne_dateien_in_python(quelle) == [(6, "docs/archiv/x.md")]
