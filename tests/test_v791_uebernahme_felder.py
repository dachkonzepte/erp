"""Version 1.10.20 (Antwort F8 vom 21.11.2026): die Felder der Karte „Als Anfrage übernehmen“ wie die übrigen Formulare.

    vorher   die Felder standen in ihrer Beschriftung und erbten deren Schrift (12 px, fett), ohne Innenabstand und Breite
    jetzt    Werte wie „Neue Anfrage“: volle Breite, Innenabstand 9/11 px, 13,5 px, Schrift 400, Rahmen, Hover und Fokus -- Optionsfelder und
             Häkchen ausgenommen; gemessen in klicktest_archiv_wiederfinden („Felder wie die übrigen Formulare“)
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _css() -> str:
    text = (ROOT / "app" / "templates" / "webanfrage.html").read_text(encoding="utf-8")
    return text[text.index("<style>"):text.index("</style>")]


def _regel(css: str, selektor: str) -> str:
    m = re.search(re.escape(selektor) + r"\{([^}]*)\}", css)
    assert m, selektor
    return m.group(1)


FELDER = '.ueb input:not([type="radio"]):not([type="checkbox"]),.ueb select,.ueb textarea'


def test_felder_wie_neue_anfrage():
    regel = _regel(_css(), FELDER)
    for teil in ("width:100%", "padding:9px 11px", "border:1px solid var(--field-border)", "font:inherit", "font-size:13.5px", "font-weight:400"):
        assert teil in regel.replace("\n", "").replace("    ", ""), teil
    anfragen = (ROOT / "app" / "templates" / "inquiries.html").read_text(encoding="utf-8")
    assert "input,textarea,select{width:100%;padding:9px 11px;border:1px solid var(--field-border);" in anfragen  # dieselben Werte


def test_hover_und_fokus():
    css = _css()
    assert "border-color:var(--field-border-hover)" in _regel(css, '.ueb input:not([type="radio"]):not([type="checkbox"]):hover,.ueb select:hover,.ueb textarea:hover')
    assert "outline:2px solid var(--ds-fokus)" in _regel(css, '.ueb input:not([type="radio"]):not([type="checkbox"]):focus,.ueb select:focus,.ueb textarea:focus')


def test_grund_beim_verwerfen_wie_die_uebrigen():
    """Seit 1.10.22 (Antwort F11): das Feld „Grund“ im Bereich „Verwerfen …“ hatte dieselbe Ursache (es erbte die Schrift seiner Beschriftung) --
    dieselben Werte, dazu eine Mindestbreite (es steht in einer Zeile neben den Knöpfen); gemessen in klicktest_webanfragen."""
    css = _css()
    regel = _regel(css, ".verwerfen-panel select").replace("\n", "").replace("    ", "")
    for teil in ("width:100%", "min-width:240px", "padding:9px 11px", "border:1px solid var(--field-border)", "font:inherit", "font-size:13.5px",
                 "font-weight:400"):
        assert teil in regel, teil
    assert "border-color:var(--field-border-hover)" in _regel(css, ".verwerfen-panel select:hover")
    assert "outline:2px solid var(--ds-fokus)" in _regel(css, ".verwerfen-panel select:focus")


def test_optionsfelder_ausgenommen():
    """Optionsfelder und Häkchen bekommen weder Breite noch Innenabstand: keine Regel für alle Eingaben der Karte."""
    css = _css().replace("\n", "")
    assert ".ueb input{" not in css and ".ueb input," not in css
    assert FELDER + "{" in css
