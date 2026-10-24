"""Seit 1.9.65 (Stufe 4, R4 Punkt 6): in den Dialogen des Monteursrahmens bleibt die Knopfleiste unten im Bild.

    Befund       Kolonnen-Dialog und „Zeit ändern“ (aufgeklappt) sind bei 1280 × 620 höher als das Fenster; der Dialog scrollt, die Knöpfe
                 lagen unter dem Rand (R3-Nachrunde: „Speichern“ erst nach Bildlauf im Dialog)
    jetzt        jede Seite im Monteursrahmen mit Dialogkarten hält deren Knopfleiste mit position:sticky unten fest; jede Dialogkarte
                 endet mit ihrer Knopfleiste (sonst klebt nichts unten). Gemessen im Klicktest meine_zeiten (1280 × 620)
"""

import re

from tests import vorlagen_js as vj

STICKY = re.compile(r"\.dialog-karte>\.dialog-knoepfe\{position:sticky;bottom:-22px;[^}]*background:var\(--ds-flaeche\)")


def _monteursseiten_mit_dialogen():
    seiten = []
    for name in vj.alle_vorlagen():
        if name.startswith("_") or not vj.bindet_ein(name, "_mobile_header.html"):
            continue
        text, _ = vj.seitentext(name)
        if 'class="dialog-karte"' in text:
            seiten.append((name, text))
    return seiten


def test_es_gibt_dialogkarten_im_monteursrahmen():
    assert {n for n, _ in _monteursseiten_mit_dialogen()} >= {"mobil.html", "mobil_zeiten.html"}


def test_jede_seite_haelt_die_knopfleiste_unten_fest():
    ohne = [n for n, text in _monteursseiten_mit_dialogen() if not STICKY.search(text)]
    assert ohne == [], "Knopfleiste der Dialoge nicht unten festgehalten"


def test_eine_vorschau_im_dialog_haelt_abstand_zur_leiste():
    """Die Vorschau rückt sich im Kolonnen-Dialog selbst ins Bild (scrollIntoView) -- ohne Abstand läge sie unter der Knopfleiste."""
    ohne = [n for n, text in _monteursseiten_mit_dialogen()
            if re.search(r'<dialog[^>]*class="dialog-karte".*?class="vorschau"', text, flags=re.S)
            and ".dialog-karte .vorschau{scroll-margin-bottom:" not in text]
    assert ohne == []


def test_jede_dialogkarte_endet_mit_ihrer_knopfleiste():
    falsch = []
    for name, text in _monteursseiten_mit_dialogen():
        for m in re.finditer(r'<dialog id="(\w+)" class="dialog-karte"[^>]*>(.*?)</dialog>', text, flags=re.S):
            letzte = re.findall(r'^  <div class="([^"]+)"', m.group(2), flags=re.M)
            if not letzte or letzte[-1] != "dialog-knoepfe":
                falsch.append(f"{name}#{m.group(1)}")
    assert falsch == []
