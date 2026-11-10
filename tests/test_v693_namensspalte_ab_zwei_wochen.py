"""Version 1.9.293 (Geräte-Runde, Vorweg V1): in „Aufträge“ ist die Namensspalte ab 2 Wochen 200 px (wie unter 1400 px Fensterbreite) -- bei 1440 px mit
offener Liste rollt 2 Wochen dann nicht mehr (200 + 10 × 56 + 4 × 26 = 864 px bei 881 px Platz; mit 230 px rollte die Tafel 13 px). Mit 1 Woche ab 1400 px
bleibt sie 230 px; 3 und 4 Wochen dürfen rollen.
Gemessen in scripts/klicktest_plantafel_auftraege.py (1440 px: 1 Woche 230 px, 2 Wochen 200 px und rollt nicht).
"""

import re

import pytest

from tests.test_v314_dashboard_month_berlin import _node
from tests.test_v399_teil_updates_geld import nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

SEITE = ROOT / "app/templates/planning.html"


def _name_spalte(breite: int, tage: int) -> int:
    """die Zeile der Seite wörtlich, ausgeführt mit Fensterbreite und eng = mehr als 1 Woche (wie in auftraegeHtml())"""
    zeile = re.search(r"const nameW=[^;]*;", SEITE.read_text(encoding="utf-8")).group(0)
    js = f"const window={{innerWidth:{breite}}}; const eng={'true' if tage > 7 else 'false'}; {zeile} process.stdout.write(JSON.stringify(nameW));"
    return _node(js, "Europe/Berlin")


@nur_mit_node
@pytest.mark.parametrize("breite, tage, erwartet", [
    (1440, 7, 230), (1440, 14, 200), (1440, 21, 200), (1440, 28, 200),  # ab 2 Wochen 200 px (bis 1.9.292 230)
    (1280, 7, 200), (1280, 14, 200), (1920, 7, 230), (1920, 14, 200),
])
def test_namensspalte(breite, tage, erwartet):
    assert _name_spalte(breite, tage) == erwartet


def test_aufbau():
    seite = SEITE.read_text(encoding="utf-8")
    assert "const nameW=window.innerWidth<1400||eng?200:230;" in seite
    assert '<col class="a-name-spalte" style="width:${nameW}px">' in seite and 'style="min-width:${nameW+arbeit*(eng?56:84)+we*26}px"' in seite
