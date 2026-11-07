"""Version 1.9.252 (Stufe 6, R4, Punkt 6): aus der Akte „Einsatz planen“ -> der Dialog der Plantafel -> zurück in die Akte.

    Akte         „Einsatz planen“ (Karte „Einsätze“ und Hauptaktion) führt auf /planning?auftrag=<id>&zurueck=/projects/<p>?auftrag=<id>#ausfuehrung
    Plantafel    öffnet „Einsatz planen“ für den Auftrag; nach dem Dialog -- gespeichert oder abgebrochen -- zurück zum Ziel; nur ein lokaler Pfad (Regel 30),
                 nur wenn der Dialog aufging, nur einmal; ohne zurueck bleibt sie auf der Tafel
Im Browser: scripts/klicktest_plantafel_aus_der_akte.py.
"""

import json
import re

import pytest

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.vorlagen_js import TEMPLATES

WEITERLEITUNG = re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_weiterleitung.html").read_text(encoding="utf-8"), flags=re.S)[0]
AKTE = "/projects/5?auftrag=7#ausfuehrung"


def _lauf(suche, oeffnet=True):
    vorbereitung = (WEITERLEITUNG + f"\nvar location = {{search: {json.dumps(suche)}, href: ''}}; var zurueckZiel = ''; var geoeffnet = []; "
                    f"async function openCreate(id) {{ geoeffnet.push(id); document.getElementById('einsatzDialog').open = {str(oeffnet).lower()}; }}")
    ablauf = ("await startAusAdresse(); const ziel = zurueckZiel; nachDemDialog(); const href = location.href; location.href = ''; nachDemDialog();"
              "AUFRUFE.push({ziel, href, zweimal: location.href, geoeffnet});")
    [erg] = [x for x in im_browser("planning.html", ["startAusAdresse", "nachDemDialog"], vorbereitung, ablauf) if "ziel" in x]
    return erg


@nur_mit_node
def test_zurueck_in_die_akte():
    erg = _lauf("?auftrag=7&zurueck=" + "%2Fprojects%2F5%3Fauftrag%3D7%23ausfuehrung")
    assert erg == {"ziel": AKTE, "href": AKTE, "zweimal": "", "geoeffnet": [7]}  # nach dem Dialog dorthin, nur einmal


@nur_mit_node
@pytest.mark.parametrize("zurueck", ["https%3A%2F%2Fboese.example%2F", "%2F%2Fboese.example%2Fx", "javascript%3Aalert(1)", ""])
def test_nur_ein_lokaler_pfad(zurueck):
    erg = _lauf("?auftrag=7" + (f"&zurueck={zurueck}" if zurueck else ""))
    assert (erg["ziel"], erg["href"], erg["geoeffnet"]) == ("", "", [7])  # der Dialog öffnet, danach bleibt die Tafel


@nur_mit_node
def test_nur_wenn_der_dialog_aufging():
    erg = _lauf("?auftrag=7&zurueck=%2Fprojects%2F5", oeffnet=False)  # gesperrter Auftrag: der Grund auf der Tafel, kein Rücksprung später
    assert (erg["ziel"], erg["href"]) == ("", "")


@nur_mit_node
def test_ohne_auftrag_nichts():
    erg = _lauf("?auftrag=abc&zurueck=%2Fprojects%2F5")
    assert (erg["ziel"], erg["href"], erg["geoeffnet"]) == ("", "", [])


def test_akte_fuehrt_mit_ruecksprung_zur_plantafel():
    text = (TEMPLATES / "akte.html").read_text(encoding="utf-8")
    ziel = "'/planning?auftrag='+Number(orderId)+'&zurueck='+encodeURIComponent('/projects/'+Number(projectId)+'?auftrag='+Number(orderId)+'#ausfuehrung')"
    assert f"else if(h.art==='einsatz')location.href={ziel};" in text  # Hauptaktion
    assert f"el('einsatzLink').href={ziel};" in text                    # Karte „Einsätze“
    assert "'/planning?auftrag='+Number(orderId);" not in text and "'/planning?auftrag='+orderId;" not in text


def test_plantafel_springt_nach_dem_dialog_zurueck():
    text = (TEMPLATES / "planning.html").read_text(encoding="utf-8")
    assert "document.getElementById('einsatzDialog').addEventListener('close',nachDemDialog);" in text
    assert "loadBoard().then(startAusAdresse);" in text
