"""Version 1.9.285 (Stufe 6, R5d, Punkt 3): Klick in einen freien Tag in „Aufträge“ schlägt die Kolonne vor, wenn der Auftrag an anderen Tagen genau eine hat;
sonst ohne (statt 1.9.282 Nr. 4: immer ohne).

    Kolonne   die Kolonnen der Einsätze dieses Auftrags im geladenen Zeitraum (board.slots), Einsätze ohne Kolonne zählen nicht: genau eine -> vorgeschlagen,
              keine oder mehrere -> ohne
Im Browser prüft das scripts/klicktest_plantafel_rueckgaengig.py (Wasserturm am freien Samstag: Kolonne Nord; Kaminverwahrung ohne Einsatz: ohne).
"""

import json

import pytest

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

SLOTS = [{"id": 1, "order_id": 10, "team_id": 5}, {"id": 2, "order_id": 10, "team_id": 5},
         {"id": 3, "order_id": 11, "team_id": 5}, {"id": 4, "order_id": 11, "team_id": 6},
         {"id": 5, "order_id": 12, "team_id": None},
         {"id": 6, "order_id": 13, "team_id": 6}, {"id": 7, "order_id": 13, "team_id": None}]


@nur_mit_node
@pytest.mark.parametrize("auftrag, kolonne", [(10, 5), (11, None), (12, None), (13, 6), (14, None)])
def test_genau_eine_kolonne(auftrag, kolonne):
    [ergebnis] = im_browser("planning.html", ["kolonneDesAuftrags"], f"var board = {{slots: {json.dumps(SLOTS)}}};",
                            f"AUFRUFE.push({{k: kolonneDesAuftrags({auftrag})}});")
    assert ergebnis == {"k": kolonne}  # 10 zweimal dieselbe, 11 zwei verschiedene, 12 nur ohne, 13 eine und einmal ohne, 14 kein Einsatz


@nur_mit_node
def test_klick_oeffnet_den_dialog_mit_der_kolonne():
    """der Handler aus der Seite wörtlich, mit einer Zelle des Auftrags 10 am Sa 14.11."""
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8").replace("\r\n", "\n")
    anfang = seite.index("  document.getElementById('planner').addEventListener('click',e=>{if(view!=='auftraege'")
    handler = seite[anfang:seite.index("});", anfang) + 3]
    vorbereitung = (f"var board = {{slots: {json.dumps(SLOTS)}}}; var view = 'auftraege'; var GEOEFFNET = [];"
                    "function openCreate(...a){ GEOEFFNET.push(a); }"
                    "var KLICK = null; document.getElementById('planner').addEventListener = (art, f) => { KLICK = f; };"
                    "const td = {dataset: {auftrag: '10', date: '2026-11-14'}};"
                    "const ziel = {closest: s => s === 'td.a-tag' ? td : null};")
    [aufruf] = im_browser("planning.html", ["kolonneDesAuftrags"], vorbereitung + handler,
                          "KLICK({target: ziel}); AUFRUFE.push(GEOEFFNET);")
    assert aufruf == [[10, "2026-11-14", 5, {"bis": "2026-11-14"}]]
