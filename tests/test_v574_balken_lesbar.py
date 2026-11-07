"""Version 1.9.156 (Stufe 6, R1 Nachrunde, Nachtrag): was der Balken sagt, passt hinein -- seit 1.9.247 (Stufe 6, R4, Punkt 1) nach der Zeichnung.

1.9.156–1.9.246: der Balken war 56 px hoch, „Auftrag pausiert“, „Auftrag storniert“, „Auftrag abgeschlossen“ und „Antrag offen“ standen in seiner dritten
Zeile statt der Adresse. Seit 1.9.247 ist ein Balken einzeilig (Zeichnung plantafel-kolonnen.html): Text = Projektname · Vornamen; der Status des Auftrags und
ein offener Antrag stehen im title (er beginnt mit dem Text des Balkens), ein abgeschlossener oder stornierter Auftrag ist blass, ein Hinweis (auch der offene
Antrag) trägt den grauen Punkt, nur eine Warnung macht den Balken rot. Dass Texte sichtbar sind oder im title stehen, misst klicktest_plantafel_tafel.
"""

import json
import re

import pytest

from tests.node_lauf import node_lauf
from tests.vorlagen_js import TEMPLATES

BASIS = {"id": 1, "order_number": "AU-1", "project_number": "P-1", "project_name": "Dach", "customer_name": "Kunde", "start_date": "2026-11-02",
         "end_date": "2026-11-03", "planned_hours": 8, "art": "baustelle", "art_label": "Baustelle", "status": "fest", "status_label": "fest",
         "employees": [{"id": 5, "name": "Tom Test", "vorname": "Tom"}], "resources": [], "property_address": "Dachweg 1", "property_name": None,
         "order_status": "laeuft", "order_status_label": "läuft", "order_status_reason": None, "conflicts": []}
ANTRAG = {"type": "antrag_offen", "label": "Sol Test · Krankheit", "stufe": "hinweis"}
FEIERTAG = {"type": "holiday", "label": "Neujahr", "stufe": "hinweis"}
DOPPELT = {"type": "employee", "label": "Tom Test", "stufe": "warnung"}
FUNKTIONEN = ("fmt", "vornamen", "slotHinweis", "einsatzTitel", "balkenHtml", "einsatzBalken")


def _balken(**anders):
    text = (TEMPLATES / "planning.html").read_text(encoding="utf-8")
    teile = [re.search(r"function " + n + r"\(.*?\n", text).group(0) for n in FUNKTIONEN]
    konst = re.search(r"const KONFLIKT_ART=\{.*?\};", text).group(0) + re.search(r"const WARNZEICHEN='.*?';", text).group(0)
    skript = ("const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');" + konst + "".join(teile)
              + f"\nconst b=einsatzBalken({json.dumps({**BASIS, **anders})},'kolonne');"
              "console.log(JSON.stringify({b,html:balkenHtml({...b,left:0,top:0,width:200})}));")
    return json.loads(node_lauf(skript).stdout.strip())


@pytest.mark.parametrize("anders, text", [
    ({"order_status": "pausiert", "order_status_label": "pausiert", "order_status_reason": "Gerüst fehlt"}, "Auftrag pausiert · Gerüst fehlt"),
    ({"order_status": "storniert", "order_status_label": "storniert"}, "Auftrag storniert"),
    ({"order_status": "abgeschlossen", "order_status_label": "abgeschlossen"}, "Auftrag abgeschlossen"),
    ({"conflicts": [ANTRAG]}, "Antrag offen: Sol Test · Krankheit"),
    ({"order_status": "pausiert", "order_status_label": "pausiert", "conflicts": [ANTRAG, {**ANTRAG, "label": "Tom Test"}]},
     "Auftrag pausiert · Antrag offen: Sol Test · Krankheit, Tom Test"),
])
def test_status_und_antrag_im_title(anders, text):
    r = _balken(**anders)
    assert (r["b"]["text"], r["b"]["leise"]) == ("Dach", "Tom")  # eine Zeile: Projektname · Vornamen
    assert r["b"]["title"].startswith("Dach · Tom\n") and text in r["b"]["title"]


def test_abgeschlossen_und_storniert_blass():
    for status in ("abgeschlossen", "storniert"):
        assert "zu" in _balken(order_status=status, order_status_label=status)["b"]["klasse"].split()
    assert "zu" not in _balken(order_status="pausiert", order_status_label="pausiert")["b"]["klasse"].split()


def test_antrag_macht_nicht_rot_nur_eine_warnung():
    antrag = _balken(conflicts=[ANTRAG])["html"]
    assert "conflict" not in antrag and 'class="hinweis-punkt"' in antrag
    assert "conflict" not in _balken(conflicts=[FEIERTAG, ANTRAG])["html"]
    rot = _balken(conflicts=[DOPPELT, ANTRAG])["html"]
    assert 'class="slot fest conflict"' in rot and "warnzeichen" in rot


def test_name_im_hinweis_ist_maskiert():
    html = _balken(conflicts=[{"type": "antrag_offen", "label": '<img src=x onerror="a()">', "stufe": "hinweis"}])["html"]
    assert "<img" not in html
