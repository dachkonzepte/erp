"""Seit 1.9.50 (Stufe 4, R2 Nachrunde, Punkt 3): Kleinigkeiten auf „Heute“.

    Checkliste     die Zeile einer Checkliste im Einsatz heißt „Checkliste <Name>“ (app/heute.py::checklisten_titel(); ein Name, der schon
                   mit „Checkliste“ beginnt, bleibt)
    Knöpfe         „Bericht anlegen“ und „Checklisten zum Auftrag“ sind neutrale Knöpfe 48 px (knopf knopf-neutral knopf-klein), bis dahin Links
    Abstand        bei einer Zeit von gestern ist der Einsatz leer und nimmt keinen Platz (#assignmentsList:empty) -- im Hochformat 16 statt
                   32 px zwischen Arbeitszeit und „Offen“
    Feldrahmen     das Feld „Feierabend … um“ auf der Signalfläche trägt --ds-feld-rand-signal, mindestens 3 : 1 zu signal-hell, hell und
                   dunkel (Prüfpaar im Kopf von ds.css; feld-rand hatte dort hell 2,84 : 1)

Im Browser misst das scripts/klicktest_heute.py (Knöpfe 48 px, Abstand 16 px, Kontrast an den berechneten Farben).
"""

import re

import pytest

from app.design_dateien import STATIC_DIR
from app.heute import checklisten_titel
from tests import vorlagen_js as vj
from tests.test_v432_design_fundament import _tokens, kontrast, pruefpaare
from tests.test_v472_heute_seite import _stil


@pytest.mark.parametrize("name, titel", [
    ("Sicherheitscheck", "Checkliste Sicherheitscheck"),
    ("Checkliste Absturzsicherung", "Checkliste Absturzsicherung"),  # keine Doppelung
    ("checkliste Leiter", "checkliste Leiter"),
    ("  Dachrinne  ", "Checkliste Dachrinne"),
    (None, "Checkliste"),
])
def test_checklisten_titel(name, titel):
    assert checklisten_titel(name) == titel


def test_einsatz_wege_als_neutrale_knoepfe_48_px():
    skript = vj.eigene_skripte("mobil.html").text
    teil = skript[skript.index("function einsatzKarte("):skript.index("function renderEinsaetze(")]
    assert re.findall(r'<a class="knopf knopf-neutral knopf-klein" href="([^"]+)">([^<]+)</a>', teil) == [
        ("/orders/'+k.order_id+'/service-reports", "Bericht anlegen"), ("/checklisten/auftrag/'+k.order_id+'", "Checklisten zum Auftrag")]
    stil = _stil()
    assert re.search(r"\.knopf-klein\{height:48px;", stil)
    assert not re.search(r"\.einsatz-wege a\{|\.einsatz-wegea\{", stil)  # keine Regel mehr, die die Knöpfe zu Links macht


def test_leerer_einsatz_nimmt_keinen_platz():
    assert "#assignmentsList:empty{display:none}" in _stil()


def test_feldrahmen_auf_der_signalflaeche():
    assert re.search(r"\.ende-zeileinput\{[^}]*border:1pxsolidvar\(--ds-feld-rand-signal\)", _stil())
    text = (STATIC_DIR / "ds" / "ds.css").read_text(encoding="utf-8")
    assert {(a, b) for g, a, b in pruefpaare(text) if g == 3.0} >= {("feld-rand-signal", "signal-hell"), ("feld-rand-signal", "flaeche")}
    hell, dunkel = _tokens(text)
    for werte in (hell, dunkel):
        assert kontrast(werte["feld-rand-signal"], werte["signal-hell"]) >= 3.0
    assert kontrast(hell["feld-rand"], hell["signal-hell"]) < 3.0  # der Grund: feld-rand reicht dort hell nicht
