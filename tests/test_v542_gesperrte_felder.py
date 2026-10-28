"""Version 1.9.122 (Stufe 5, R1 Nachrunde, Punkt 4): gesperrte Felder hell erkennbar -- eine Regel für jede Seite statt Regeln je Seite.

    Regel        app/static/ds/ds-gesperrt.css: genau eine Regel -- input mit Fläche, textarea (je :disabled und [readonly]), select (:disabled);
                 Fläche --ds-feld-gesperrt, Schrift --ds-text-2, Mauszeiger not-allowed, je !important; Ausnahme nur über data-gesperrt-eigen
    jede Seite   bindet sie über _ds_kopf.html ein, nach den anderen Design-Dateien; eine Design-Datei (ohne Anmeldung, langer Cache)
    Seiten       keine Vorlage trägt eine eigene Regel für Fläche, Schrift oder Mauszeiger gesperrter oder nur lesbarer Felder; data-gesperrt-eigen
                 nur mit Grund in AUSNAHMEN (heute keine)
    hell/dunkel  die Fläche eines gesperrten Felds ist anders als die eines offenen (--ds-flaeche, darauf zeigt --card), hell und dunkel; die
                 Schrift darauf mindestens 4,5 : 1
Im Browser misst klicktest_gesperrte_felder jedes gesperrte Feld mehrerer Seiten, hell und dunkel.
"""

import re

import pytest

from app.design_dateien import STATIC_DIR, ist_design_pfad
from tests import vorlagen_js as vj
from tests.test_v432_design_fundament import _deklarationen, _oberste_ebene, css_regeln, kontrast

DATEI = STATIC_DIR / "ds" / "ds-gesperrt.css"
DS = STATIC_DIR / "ds" / "ds.css"
ALTE = STATIC_DIR / "ds" / "ds-alte-namen.css"
# Felder mit data-gesperrt-eigen (eigene Darstellung, wenn gesperrt) -- je Vorlage mit Grund. Heute keine.
AUSNAHMEN: dict[str, str] = {}
OHNE_FLAECHE = {"checkbox", "radio", "button", "submit", "reset", "hidden", "file", "image", "range", "color"}
ERWARTET = {"background": "var(--ds-feld-gesperrt) !important", "color": "var(--ds-text-2) !important", "cursor": "not-allowed !important"}


def _regeln():
    regeln, rest = css_regeln(DATEI.read_text(encoding="utf-8"))
    assert rest == ""
    return regeln


def test_genau_eine_regel_mit_flaeche_schrift_und_mauszeiger():
    [(kopf, rumpf)] = _regeln()
    assert dict(_deklarationen(rumpf)) == ERWARTET
    selektoren = [s.strip() for s in _oberste_ebene(kopf, lambda c: c == ",")]
    assert [re.match(r"[a-z]+", s)[0] for s in selektoren] == ["input", "textarea", "select"]
    eingabe, text, auswahl = selektoren
    assert ":is(:disabled, [readonly])" in eingabe and ":is(:disabled, [readonly])" in text and ":disabled" in auswahl
    assert set(re.findall(r'\[type="([a-z]+)"\]', eingabe)) == OHNE_FLAECHE
    assert all("[data-gesperrt-eigen]" in s for s in selektoren)


def test_nur_hier_important():
    """!important gibt es unter app/static/ nur in dieser Datei -- der Zustand „gesperrt“ geht der Gestaltung vor, sonst nichts."""
    funde = [p.name for p in STATIC_DIR.rglob("*.css")  # ohne Kommentare: ds-basis.css sagt dort „kein !important“
             if p != DATEI and "!important" in re.sub(r"/\*.*?\*/", "", p.read_text(encoding="utf-8"), flags=re.S)]
    assert funde == []


def test_eine_design_datei_auf_jeder_seite_nach_den_anderen():
    pfad = "/static/ds/ds-gesperrt.css"
    assert ist_design_pfad({"type": "http", "method": "GET", "path": pfad, "raw_path": pfad.encode()})
    funde = []
    for name in vj.seiten():
        text = vj.zusammensetzen(name)[0]
        stelle = text.find('href="/static/ds/ds-gesperrt.css?v=')
        if text.count('href="/static/ds/ds-gesperrt.css?v=') != 1:
            funde.append(f"{name}: nicht genau einmal")
        elif stelle < text.find('href="/static/ds/ds-alte-namen.css?v='):
            funde.append(f"{name}: vor ds-alte-namen.css")
    assert funde == []


def _feld_regeln(name: str, text: str) -> list[str]:
    """Regeln einer Vorlage, die Fläche, Schrift oder Mauszeiger gesperrter oder nur lesbarer Felder setzen."""
    css = "\n".join(re.findall(r"<style>(.*?)</style>", text, flags=re.S))
    funde = []
    for kopf, rumpf in css_regeln(css)[0] if css.strip() else []:
        if not re.search(r"background|(?<![-\w])color|cursor", rumpf):
            continue
        for sel in _oberste_ebene(kopf, lambda c: c == ","):
            if not re.search(r":disabled|\[readonly\]|\[disabled\]", sel):
                continue
            letzter = re.split(r"[\s>+~]+", sel.strip())[-1]
            feld = re.match(r"(input|select|textarea)\b", letzter)
            if not feld and (kennung := re.match(r"#([\w-]+)", letzter)):
                tag = re.search(rf'<(\w+)[^>]*\bid="{re.escape(kennung[1])}"', text)
                feld = tag and tag[1] in ("input", "select", "textarea")
            if feld:
                funde.append(f"{name}: {sel.strip()}")
    return funde


def test_keine_seite_hat_eine_eigene_regel():
    """Bis 1.9.121 fünf Seiten mit eigener Regel (Einstellungen, Checkliste, Checklisten-Vorlage, Stammdaten-Formular, Auftrag), alle anderen
    ohne -- hell sah ein gesperrtes Feld dort aus wie ein offenes. Knöpfe (:disabled an button, .knopf, .btn …) sind keine Felder."""
    funde = []
    for name in vj.alle_vorlagen():
        funde += _feld_regeln(name, (vj.TEMPLATES / name).read_text(encoding="utf-8"))
    assert funde == []


@pytest.mark.parametrize("css, fund", [
    ("<style>input:disabled{background:#eee}</style>", "input:disabled"),
    ("<style>.lv-row input:disabled,.lv-row select:disabled{color:red}</style>", ".lv-row input:disabled"),
    ('<style>#taxKey:disabled{cursor:default}</style><select id="taxKey"></select>', "#taxKey:disabled"),
    ("<style>textarea[readonly]{background:var(--soft)}</style>", "textarea[readonly]"),
])
def test_waechter_findet(css, fund):
    assert any(fund in f for f in _feld_regeln("x.html", css))


def test_waechter_laesst_knoepfe_und_rahmen_durch():
    css = ('<style>button:disabled{opacity:.5;cursor:not-allowed}.knopf:disabled{background:#ccc}#pyConfirm:disabled{opacity:.4}'
           'input[readonly]:hover{border-color:var(--field-border)}</style><button id="pyConfirm"></button>')
    assert _feld_regeln("x.html", css) == []


def test_ausnahmen_nur_mit_grund():
    gefunden = {name for name in vj.alle_vorlagen() if "data-gesperrt-eigen" in (vj.TEMPLATES / name).read_text(encoding="utf-8")}
    assert gefunden == set(AUSNAHMEN)
    assert all(grund.strip() for grund in AUSNAHMEN.values())


def _token(text: str, name: str, dunkel: bool) -> str:
    teil = text.split(':root[data-theme="dark"]')[1 if dunkel else 0]
    return re.search(rf"--ds-{name}:\s*(#[0-9A-Fa-f]{{6}});", teil)[1]


@pytest.mark.parametrize("dunkel", [False, True], ids=["hell", "dunkel"])
def test_flaeche_anders_als_ein_offenes_feld(dunkel):
    """Ein offenes Feld trägt --card bzw. --ds-flaeche (--card zeigt in ds-alte-namen.css auf --ds-flaeche); ein gesperrtes
    --ds-feld-gesperrt -- anders, hell wie dunkel, und die gedämpfte Schrift darauf mit mindestens 4,5 : 1."""
    assert re.search(r"--card:\s*var\(--ds-flaeche\)", ALTE.read_text(encoding="utf-8"))
    text = DS.read_text(encoding="utf-8")
    gesperrt, offen = _token(text, "feld-gesperrt", dunkel), _token(text, "flaeche", dunkel)
    assert gesperrt.lower() != offen.lower()
    assert kontrast(gesperrt, offen) > 1.05, (gesperrt, offen)
    assert kontrast(_token(text, "text-2", dunkel), gesperrt) >= 4.5
