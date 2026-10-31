"""Version 1.9.156 (Stufe 6, R1 Nachrunde, Nachtrag): was der Balken sagt, passt hinein.

Der Balken ist 56 px hoch und schneidet ab, es passen drei Zeilen. „Auftrag pausiert“ (seit 1.9.124), „Auftrag storniert“ (1.9.143), „Auftrag abgeschlossen“ (1.9.151) und „Antrag offen“ (1.9.152)
standen als vierte Zeile: im Dokument da, auf dem Bildschirm abgeschnitten. Dass sie zu sehen sind, misst klicktest_plantafel_konflikte; hier die Zeilen.
"""

import json
import re

import pytest

from tests.node_lauf import node_lauf
from tests.vorlagen_js import TEMPLATES

BASIS = {"id": 1, "order_number": "AU-1", "project_number": "P-1", "project_name": "Dach", "customer_name": "Kunde", "start_date": "2026-11-02", "end_date": "2026-11-03", "planned_hours": 8,
         "property_address": "Dachweg 1", "property_name": None, "order_status": "laeuft", "order_status_label": "läuft", "order_status_reason": None, "conflicts": []}
ANTRAG = {"type": "antrag_offen", "label": "Sol Test · Krankheit"}
FEIERTAG = {"type": "holiday", "label": "Neujahr"}


def _balken(**anders):
    text = (TEMPLATES / "planning.html").read_text(encoding="utf-8")
    teile = [re.search(r"function slotHinweis\(.*?\n", text).group(0), re.search(r"function renderSlot\(slot\)\{.*?\n", text).group(0)]
    skript = ("const view='teams';const visibleSpan=()=>({left:0,width:200});const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;');const fmt=x=>x;const num=x=>String(x);\n"
              + "".join(teile) + f"\nconsole.log(JSON.stringify(renderSlot({json.dumps({**BASIS, **anders})})));")
    return json.loads(node_lauf(skript).stdout.strip())


def _zeilen(html):
    return len(re.findall(r'class="slot-meta', html)) + len(re.findall(r"<b>", html))


@pytest.mark.parametrize("anders, text", [
    ({"order_status": "pausiert", "order_status_label": "pausiert", "order_status_reason": "Gerüst fehlt"}, "Auftrag pausiert · Gerüst fehlt"),
    ({"order_status": "storniert", "order_status_label": "storniert"}, "Auftrag storniert"),
    ({"order_status": "abgeschlossen", "order_status_label": "abgeschlossen"}, "Auftrag abgeschlossen"),
    ({"conflicts": [ANTRAG]}, "Antrag offen: Sol Test · Krankheit"),
    ({"order_status": "pausiert", "order_status_label": "pausiert", "conflicts": [ANTRAG, {"type": "antrag_offen", "label": "Tom Test"}]}, "Auftrag pausiert · Antrag offen: Sol Test · Krankheit, Tom Test"),
])
def test_hinweis_statt_adresse_in_der_dritten_zeile(anders, text):
    html = _balken(**anders)
    assert _zeilen(html) == 3
    assert f'<div class="slot-meta slot-hinweis">{text}</div>' in html
    assert "Dachweg 1" not in html
    assert f"· {text}\"" in html  # und vollständig im title, die Zeile kürzt mit „…“


def test_ohne_hinweis_bleibt_die_adresse():
    html = _balken()
    assert _zeilen(html) == 3
    assert "Dachweg 1" in html and "slot-hinweis" not in html


def test_antrag_macht_nicht_rot_anderer_hinweis_weiter():
    assert 'class="slot "' in _balken(conflicts=[ANTRAG])
    assert 'class="slot conflict"' in _balken(conflicts=[FEIERTAG, ANTRAG])


def test_name_im_hinweis_ist_maskiert():
    html = _balken(conflicts=[{"type": "antrag_offen", "label": '<img src=x onerror="a()">'}])
    assert "<img" not in html
