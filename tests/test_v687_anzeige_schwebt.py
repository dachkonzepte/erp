"""Version 1.9.287 (Stufe 6, R5d, Punkt 5): die Anzeige vor dem Loslassen schwebt über der Zelle und macht die Zeile nicht höher.

    Anzeige   position:absolute oberhalb der Zelle (bottom: 100 % + 2 px), so breit wie die Zelle, wächst nach oben, fängt keine Zeigerereignisse ab; vorn in
              die Zelle gesetzt -- hinten wäre die letzte Karte nicht mehr :last-child, ihr Abstand nach unten machte die Zeile 4 px höher (so beim Bauen gemessen)
    Kopie     des gezogenen Chips rechts neben dem Zeiger, auf seiner Höhe (bis 1.9.286 über dem Zeiger, verdeckte dann die Anzeige)
    Finger    seitlich 6 px wie mit der Maus (1.9.284: 7 px -- bei 1280 px war „HS-DK 202“ gekürzt)
Gemessen im Klicktest scripts/klicktest_plantafel_auftraege_ziehen.py (Zeile gleich hoch beim Ziehen mit Maus und Finger, Anzeige oberhalb der Zelle).
"""

from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

SEITE = ROOT / "app/templates/planning.html"


def test_anzeige_schwebt_ueber_der_zelle():
    seite = SEITE.read_text(encoding="utf-8")
    regel = next(z for z in seite.splitlines() if z.startswith(".zug-anzeige{"))
    assert regel.startswith(".zug-anzeige{position:absolute;left:2px;right:2px;bottom:calc(100% + 2px);z-index:5;") and "pointer-events:none" in regel
    assert "margin" not in regel  # nichts im Fluss der Zelle
    assert "td.zug-woanders .zug-anzeige{color:var(--ds-fehler-text);background:var(--ds-fehler-hell)}" in seite
    assert "#planner td.a-tag{position:relative}" in seite


def test_anzeige_vorn_in_der_zelle():
    seite = SEITE.read_text(encoding="utf-8")
    assert "el.className='zug-anzeige';ziel.td.prepend(el)}" in seite and "el.className='zug-anzeige';ziel.td.appendChild(el)" not in seite


def test_kopie_neben_dem_zeiger():
    seite = SEITE.read_text(encoding="utf-8")
    assert "azug.geist.style.left=(e.clientX+16)+'px';azug.geist.style.top=(e.clientY-azug.geist.offsetHeight/2)+'px';" in seite


def test_finger_seitlich_wie_die_maus():
    seite = SEITE.read_text(encoding="utf-8")
    assert "@media (pointer:coarse){.ansicht-auftraege .chip[data-art]{min-height:32px;padding:3px 6px;position:relative}" in seite
    assert "min-height:26px;padding:2px 6px;" in seite
