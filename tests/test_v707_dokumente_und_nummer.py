"""Version 1.9.307 (L2a, Vorweg -- Frage 5 der Nachrunde der Geräte-Runde): „Betriebsmittel anlegen“ bei schmalem Fenster, die Nummer in der Liste.

    Dokumente   Art, Datei und „+ Vormerken“ stehen in einer Zeile (.dok-zeile, drei Spalten) -- unter 900 px untereinander, Auswahl und Dateifeld so breit
                wie die Karte, der Knopf links (bis 1.9.306 auch bei 412 px drei Spalten: Auswahl und Dateifeld schnitten ihren Text ab)
    Nummer      in der Liste der Betriebsmittel bricht die Nummer nicht um (.nw; bis 1.9.306 bei 412 px „BM-/12“) -- die Tabelle rollt in ihrem Rahmen
Im Browser gemessen: scripts/klicktest_geraete.py (Lage und Breite der Felder, Zeilen der Nummer bei 1440, 1280 und 412 px).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORM = ROOT / "app/templates/master_data_form.html"
LISTE = ROOT / "app/templates/master_data.html"


def test_dokumente_unter_900_px_untereinander():
    form = FORM.read_text(encoding="utf-8")
    assert ".dok-zeile{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin-top:8px;align-items:end}" in form
    schmal = re.search(r"@media\(max-width:900px\)\{(.*?)\}</style>", form, flags=re.S)
    assert schmal and ".dok-zeile{grid-template-columns:1fr}" in schmal.group(1) and ".dok-zeile>button{justify-self:start}" in schmal.group(1)
    assert '<div class="dok-zeile"><select id="assetDocType"' in form
    assert "grid-template-columns:1fr 1fr auto;gap:8px;margin-top:8px;align-items:end\"" not in form  # keine feste Zeile mehr im Markup


def test_nummer_bricht_nicht_um():
    liste = LISTE.read_text(encoding="utf-8")
    assert """<td class="nw">${esc(x.asset_number||'—')}</td>""" in liste
    assert ".nw{white-space:nowrap}" in liste
