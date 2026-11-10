"""Version 1.9.294 (Geräte-Runde, Vorweg V2): in „Aufträge“ zeigt der Kran bei 56 px je Tag nur sein Zeichen -- Kranzeichen und „Kr“ brauchen gemessen 43,7 px,
die Karte hat dort 39 px Inhalt, bei 58 px je Tag 41 px (bis 1.9.293 hieß es „K…“). Die Karte ist ein Container (1.9.283); bis 43,9 px Inhalt verschwindet der
Name des Krans, das Zeichen bleibt, der Name steht im title. Bei 61 px je Tag (2 Wochen, 1280 px, Liste zu: 44,3 px Inhalt) passt „Kr“ noch.
Gemessen in scripts/klicktest_plantafel_auftraege.py (1280 px mit 3 Wochen: 56 px, kein Chip gekürzt; 1440 px mit 2 Wochen; 1280 px mit 2 Wochen „Kr“).
"""

from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

SEITE = ROOT / "app/templates/planning.html"


def test_kran_bis_44_px_nur_mit_zeichen():
    seite = SEITE.read_text(encoding="utf-8")
    assert "@container (max-width:43.9px){.a-einsatz .chip:has(.kranzeichen) .chip-text{display:none}}" in seite
    # die Karte ist der Container; das Kranzeichen selbst verschwindet nie (nur das Gerätezeichen unter 93 px, 1.9.283)
    assert "container-type:inline-size;" in seite
    assert ".kranzeichen{display:none}" not in seite
