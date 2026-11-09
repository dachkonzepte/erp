"""Version 1.9.284 (Stufe 6, R5d, Punkt 2): Chips mit dem Finger 32 px hoch, der Treffbereich größer (statt 40 px hoher Chips, 1.9.281 Nr. 7).

    Höhe          bei grobem Zeiger 32 px (bis 1.9.283 40 px)
    Treffbereich  ein unsichtbares ::before reicht 4 px über und unter den Chip und 2 px zur Seite (inset vom Innenrand gemessen, der Rand ist 1 px: -5/-3 px)
                  -- 40 px hoch, ohne die Karte höher zu machen; zwischen zwei Chip-Zeilen einer Karte 8 px, damit sich die Treffbereiche nicht überdecken
    Kürzen        der Name kürzt in seinem eigenen Teil (span.chip-text, „…“); der Chip selbst schneidet nicht ab (sonst schnitte er den Treffbereich ab)
Gemessen im Klicktest scripts/klicktest_plantafel_auftraege_ziehen.py (Teil „Finger“: 32 px, 3 px darüber und darunter trifft noch den Chip, 7 px darüber nicht).
"""

from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
from tests.test_v680_ansicht_auftraege import _lauf

SEITE = ROOT / "app/templates/planning.html"


def test_finger_32_px_mit_groesserem_treffbereich():
    seite = SEITE.read_text(encoding="utf-8")
    assert ("@media (pointer:coarse){.ansicht-auftraege .chip[data-art]{min-height:32px;padding:3px 7px;position:relative}"
            ".ansicht-auftraege .chip[data-art]::before{content:'';position:absolute;inset:-5px -3px}.ansicht-auftraege .a-einsatz{row-gap:8px}}") in seite
    assert "min-height:40px" not in seite.split("/* seit 1.9.281 (Stufe 6, R5c, Punkt 3)")[1].split("</style>")[0]


def test_der_text_kuerzt_nicht_der_chip():
    seite = SEITE.read_text(encoding="utf-8")
    regel = next(z for z in seite.splitlines() if z.startswith(".chip{display:inline-flex;"))
    assert "overflow:hidden" not in regel and "text-overflow" not in regel  # der Chip schnitte den Treffbereich ab
    assert ".chip .chip-text{min-width:0;overflow:hidden;text-overflow:ellipsis}" in seite


def test_chip_mit_eigenem_textteil():
    [html] = _lauf("AUFRUFE.push(chipHtml({art:'person',id:1,name:'Tom',titel:'Tom Monteur',slot:3,tag:'2026-11-09'}));")
    assert html == ('<span class="chip" data-art="person" data-id="1" data-slot="3" data-tag="2026-11-09" title="Tom Monteur">'
                    '<span class="chip-text">Tom</span></span>')
