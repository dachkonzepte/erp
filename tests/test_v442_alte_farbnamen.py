"""Stufe 2 „Rahmen“, Runde 3 (1.9.5): die alten Farbnamen der Seiten zeigen zentral auf das Design-System.

    ds-alte-namen.css   nur :root, genau die Namen aus ALTE_NAMEN mit genau diesen --ds-*-Werten (jeder in ds.css hell und dunkel)
    Vorlagen            keine Kopie mehr: kein alter Farbname und kein --sidebar-* als Deklaration, keine Akzentfarbe aus den
                        Einstellungen (Ausnahme: theme-color der Monteursansicht, wie das App-Symbol)
    Doppelnamen         --accent, --danger, --warning, --success, --info nur als Textfarbe -- als Fläche steht der Flächenwert
    _ds_kopf.html       bindet die Datei mit Prüfsumme ein
Kontrast und Maße je Seite vorher/nachher: Messung im Archiv (docs/archiv/redesign.md, Runde 3), Werkzeug im Scratchpad der Runde."""

import re
from pathlib import Path

import pytest

from tests import vorlagen_js as vj
from tests.test_v432_design_fundament import _deklarationen, css_regeln

ROOT = Path(__file__).resolve().parent.parent
DS = ROOT / "app" / "static" / "ds"
ALTE = DS / "ds-alte-namen.css"

ALTE_NAMEN = {
    "--bg": "--ds-grund", "--card": "--ds-flaeche", "--soft": "--ds-flaeche-2", "--ink": "--ds-text", "--muted": "--ds-text-2",
    "--line": "--ds-linie", "--field-border": "--ds-feld-rand", "--field-border-hover": "--ds-text-3",
    "--accent": "--ds-aktion-text", "--danger": "--ds-fehler-text", "--danger-soft": "--ds-fehler-hell", "--warning": "--ds-warn-text",
    "--warning-soft": "--ds-warn-hell", "--success": "--ds-ok-text", "--success-soft": "--ds-ok-hell", "--info": "--ds-info-text",
    "--info-soft": "--ds-info-hell",
}
# Doppelnamen: als Textfarbe der alte Name (zeigt auf -text), als Fläche direkt dieser Wert
FLAECHE = {"--accent": "--ds-aktion", "--danger": "--ds-fehler", "--warning": "--ds-warn-text", "--success": "--ds-ok",
           "--info": "--ds-info"}
TEXT_EIG = {"color", "caret-color", "text-decoration-color", "-webkit-text-fill-color", "text-emphasis-color"}
# Die Akzentfarbe der Einstellungen bleibt nur, wo sie nicht die Oberfläche färbt -- wie das App-Symbol (Festlegung 1.8.161)
AKZENT_AUSNAHMEN = {"mobil.html": 1}  # <meta name="theme-color">: Browserleiste der Monteursansicht


def _ds_werte(thema_dunkel: bool) -> set[str]:
    text = (DS / "ds.css").read_text(encoding="utf-8")
    werte = set()
    for kopf, rumpf in css_regeln(text)[0]:
        if kopf.strip() == (':root[data-theme="dark"]' if thema_dunkel else ":root"):
            werte |= {name for name, _ in _deklarationen(rumpf)}
    return werte


def test_alte_namen_nur_root_und_genau_die_liste():
    regeln, rest = css_regeln(ALTE.read_text(encoding="utf-8"))
    assert not rest.strip()
    assert [kopf.strip() for kopf, _ in regeln] == [":root"]
    werte = {name: wert.strip() for name, wert in _deklarationen(regeln[0][1])}
    assert werte == {alt: f"var({neu})" for alt, neu in ALTE_NAMEN.items()}


def test_jeder_wert_steht_in_ds_css_hell_und_dunkel():
    hell, dunkel = _ds_werte(False), _ds_werte(True)
    for neu in {*ALTE_NAMEN.values(), *FLAECHE.values()}:
        assert neu in hell and neu in dunkel, neu


def test_ds_kopf_bindet_die_datei_mit_pruefsumme_ein():
    kopf = (ROOT / "app" / "templates" / "_ds_kopf.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/static/ds/ds-alte-namen.css?v={{ ds_alte_namen_pruefsumme }}">' in kopf
    from app.design_dateien import pruefsumme
    from app.routers.pages import templates
    assert templates.env.globals["ds_alte_namen_pruefsumme"] == pruefsumme("ds-alte-namen.css")


def _vorlagen():
    return [(name, (vj.TEMPLATES / name).read_text(encoding="utf-8")) for name in vj.alle_vorlagen()]


def test_keine_kopie_der_alten_farben_in_den_vorlagen():
    funde = []
    namen = "|".join(re.escape(n[2:]) for n in sorted(ALTE_NAMEN, key=len, reverse=True))
    for name, text in _vorlagen():
        for m in re.finditer(rf"(?<![\w-])--(?:{namen}|sidebar-[\w-]+)\s*:", text):
            funde.append(f"{name}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0)}")
    assert funde == []


def test_keine_rueckfallwerte_an_alten_namen():
    """var(--danger,#b42318) u. ä. trug eine Kopie eines alten Werts als Rückfall -- seit 1.9.5 ist jeder alte Name auf jeder Seite
    gesetzt (_ds_kopf.html), ein Rückfall griffe nie."""
    namen = "|".join(re.escape(n[2:]) for n in sorted(ALTE_NAMEN, key=len, reverse=True))
    funde = [f"{name}: {m.group(0)}" for name, text in _vorlagen() for m in re.finditer(rf"var\(--(?:{namen})\s*,[^)]*\)", text)]
    assert funde == []


def test_keine_akzentfarbe_auf_der_oberflaeche():
    gefunden = {name: len(re.findall(r"get_theme\(\)\.accent_color", text)) for name, text in _vorlagen()}
    assert {n: k for n, k in gefunden.items() if k} == AKZENT_AUSNAHMEN


def eigenschaft(text: str, i: int) -> str | None:
    """Die CSS-Eigenschaft der Deklaration, in der text[i] steht (rückwärts bis zum Doppelpunkt, Klammern übersprungen) -- None, wenn
    vorher ;, {, }, = oder ein Anführungszeichen kommt."""
    tiefe = 0
    for j in range(i - 1, max(-1, i - 400), -1):
        c = text[j]
        if c == ")":
            tiefe += 1
        elif c == "(" and tiefe:
            tiefe -= 1
        elif tiefe == 0 and c in ";{}=\"'`":
            return None
        elif tiefe == 0 and c == ":":
            m = re.search(r"(-?[a-z]+(?:-[a-z]+)*)\s*$", text[max(0, j - 60):j])
            return m.group(1) if m else None
    return None


def doppelnamen_als_flaeche(text: str) -> list[str]:
    funde = []
    for m in re.finditer(r"var\((--(?:accent|danger|warning|success|info))(?=[),\s])", text):
        eig = eigenschaft(text, m.start())
        if eig not in TEXT_EIG:
            funde.append(f"{text.count(chr(10), 0, m.start()) + 1}: {m.group(1)} in {eig!r}")
    return funde


def test_doppelnamen_nur_als_textfarbe():
    funde = [f"{name}:{f}" for name, text in _vorlagen() for f in doppelnamen_als_flaeche(text)]
    assert funde == []


@pytest.mark.parametrize("css,fund", [
    (".x{background:var(--accent)}", "'background'"),
    (".x{border:1px solid var(--danger)}", "'border'"),
    (".x{background:color-mix(in srgb,var(--warning) 18%,var(--card))}", "'background'"),
    ('<span style="outline:2px solid var(--success)">', "'outline'"),
    ('<svg fill="var(--info)">', "None"),
])
def test_waechter_doppelnamen_findet(css, fund):
    assert any(fund in f for f in doppelnamen_als_flaeche(css)), doppelnamen_als_flaeche(css)


def test_waechter_doppelnamen_laesst_durch():
    assert doppelnamen_als_flaeche(".x{color:var(--accent)}.y{background:var(--ds-aktion);color:var(--danger)}"
                                   "<b style=\"${a?'color:var(--warning)':''}\">") == []
