"""Version 1.9.110 (Stufe 4, R5b Nachrunde 2, Punkt 4): gesperrte Felder im Dunkeln erkennbar wie im Hellen.

Bis 1.9.109 trugen gesperrte Felder die Fläche --soft (= --ds-flaeche-2): dunkel #222A2F auf der Fläche #1A2024, kaum zu sehen. Seit 1.9.110
das Token --ds-feld-gesperrt (app/static/ds/ds.css): hell wie bisher (#F3F5F6), dunkel #2B3339 -- der Helligkeitsabstand (CIELAB L*) zur Fläche
ist im Dunkeln mindestens doppelt so groß wie im Hellen (gleich gut zu sehen braucht im Dunkeln mehr Abstand). Jede Seite, die gesperrte Felder
mit einer eigenen Fläche zeigt, nimmt das Token.
"""

import re

import pytest

from tests import vorlagen_js as vj
from tests.test_v432_design_fundament import DS_CSS

SEITEN = ("settings.html", "checklist.html", "checklist_template.html", "akte.html", "master_data_form.html")


def _token(text: str, name: str, dunkel: bool) -> str:
    teil = text.split(':root[data-theme="dark"]')[1 if dunkel else 0]
    return re.search(rf"--ds-{name}:\s*(#[0-9A-Fa-f]{{6}});", teil)[1]


def _l_stern(farbe: str) -> float:
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(farbe[i:i + 2], 16) for i in (1, 3, 5))
    y = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return 116 * (y ** (1 / 3) if y > 0.008856 else 7.787 * y + 16 / 116) - 16


def _abstand(fuellung: str, flaeche: str) -> float:
    return abs(_l_stern(fuellung) - _l_stern(flaeche))


def test_hell_unveraendert_dunkel_doppelt_so_deutlich():
    """Hell bleibt die Fläche wie bisher (flaeche-2); dunkel ist der Abstand zur Fläche mindestens doppelt so groß wie hell. Gegenprobe: die
    Fläche bis 1.9.109 (flaeche-2 dunkel, #222A2F) erfüllt das nicht."""
    text = DS_CSS.read_text(encoding="utf-8")
    assert _token(text, "feld-gesperrt", False) == _token(text, "flaeche-2", False)
    hell = _abstand(_token(text, "feld-gesperrt", False), _token(text, "flaeche", False))
    dunkel = _abstand(_token(text, "feld-gesperrt", True), _token(text, "flaeche", True))
    assert dunkel >= 2 * hell, (hell, dunkel)
    assert _abstand(_token(text, "flaeche-2", True), _token(text, "flaeche", True)) < 2 * hell


@pytest.mark.parametrize("seite", SEITEN)
def test_gesperrte_felder_nehmen_das_token(seite):
    """Seit 1.9.122: die fünf Seiten tragen keine eigene Regel mehr für gesperrte oder nur lesbare Felder -- die eine Regel steht in
    app/static/ds/ds-gesperrt.css und nimmt --ds-feld-gesperrt (tests/test_v542_gesperrte_felder.py). 1.9.110–1.9.121 trug jede der fünf
    Seiten eine eigene Regel mit dem Token."""
    css = "\n".join(re.findall(r"<style>(.*?)</style>", (vj.TEMPLATES / seite).read_text(encoding="utf-8"), flags=re.S))
    regeln = [r for r in re.findall(r"([^{}]*(?::disabled|\[readonly\])[^{}]*)\{([^}]*)\}", css) if "background" in r[1]
              and "button" not in r[0] and ".knopf" not in r[0] and "btn" not in r[0] and "#pyConfirm" not in r[0]]
    assert regeln == [], seite
    zentral = (DS_CSS.parent / "ds-gesperrt.css").read_text(encoding="utf-8")
    assert "background: var(--ds-feld-gesperrt) !important;" in zentral


def test_keine_seite_graut_mit_soft():
    """Wächter über alle Vorlagen: kein gesperrtes oder nur lesbares Feld mit der Fläche --soft (dunkel kaum zu sehen)."""
    funde = []
    for name in vj.alle_vorlagen():
        text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
        for auswahl, rumpf in re.findall(r"([^{}<>]*(?:input|select|textarea)[^{}<>]*(?::disabled|\[readonly\])[^{}<>]*)\{([^}]*)\}", text):
            if "var(--soft)" in rumpf:
                funde.append(f"{name}: {auswahl.strip()[:80]}")
    assert funde == []
