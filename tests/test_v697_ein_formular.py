"""Version 1.9.297 (Geräte-Runde, Punkt 2): ein Formular je Gerät -- die Betriebsmittelseite.

    Haken       „Auf der Plantafel einplanbar“ unter den Stammdaten; das Wort „Ressource“ steht auf der Seite nirgends (nur in Code-Kommentaren)
    oben        Bezeichnung, Typ, Hersteller, Modell, Kennzeichen immer -- mit Haken die des Plantafel-Geräts; mit Haken ist der Typ Pflicht
    Plantafel   mit Haken ein Abschnitt mit Kurzname und Postfach (nur lesen); der Link in die Einstellungen nur für den Admin
    Auswahl     „Vorhandenes Plantafel-Gerät verknüpfen“ nur, wenn es ein freies gibt (ohne Betriebsmittel; bis 1.9.304 nur aktive) und das Gerät noch keins hat
Im Browser: scripts/klicktest_geraete.py (speichern, verknüpfen, Rückfrage beim Entfernen, Büro – Auftrag, Bilder).
"""

import json
import re

import pytest

from tests.test_v399_teil_updates_geld import nur_mit_node
from tests.test_v447_auswahl_altwerte import lauf
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

SEITE = ROOT / "app/templates/operational_asset.html"
TYPEN = [{"value": "Fahrzeug", "label": "Fahrzeug", "active": True}, {"value": "Kran", "label": "Kran", "active": True}]
MIT = {"id": 1, "resource_id": 7, "einplanbar": True, "name": "Pritsche HS-DK 202", "asset_type": "Fahrzeug", "manufacturer": "MAN", "model": None,
       "identifier": "HS-DK 202", "kurzname": "HS-DK 202", "outlook_mailbox": "pritsche@example.test", "active": True, "inspections": [], "documents": []}
OHNE = {**MIT, "id": 2, "resource_id": None, "einplanbar": False, "name": "Leiter", "asset_type": None, "kurzname": None, "outlook_mailbox": None}
FREI = {"id": 9, "name": "Anhänger Humbaur", "resource_type": "Kran", "manufacturer": None, "model": None, "identifier": "HS-A 77", "kurzname": "A 77",
        "active": True, "taken": False}
ZUSTAND = ("return [_element('editEinplanbar').checked, _element('plantafelAbschnitt').hidden, _element('typPflicht').hidden, _element('verknuepfenWrap').hidden,"
           "_element('editName').value, _element('editKurzname').value, _element('postfachText').textContent, _element('postfachLink').hidden];")


def _zustand(asset: dict, frei: list, admin: bool, danach: str = "") -> list:
    ablauf = (f"assetTypes = {json.dumps(TYPEN)}; resources = {json.dumps(frei)}; asset = {json.dumps(asset)}; istAdmin = {'true' if admin else 'false'};"
              f"fillEditor(); {danach} {ZUSTAND}")
    return lauf("operational_asset.html", "\ninit();", ablauf)


@nur_mit_node
def test_mit_haken_angaben_oben_und_abschnitt_plantafel():
    assert _zustand(MIT, [], True) == [True, False, False, True, "Pritsche HS-DK 202", "HS-DK 202", "pritsche@example.test", False]
    assert _zustand(MIT, [], False)[-1] is True  # Büro: das Postfach ohne Link


@nur_mit_node
def test_ohne_haken_kein_abschnitt_und_haken_setzen():
    assert _zustand(OHNE, [FREI], True) == [False, True, True, True, "Leiter", "", "— (keins)", False]
    # Haken setzen: Abschnitt, Typ als Pflicht, Auswahl (es gibt ein freies Plantafel-Gerät)
    assert _zustand(OHNE, [FREI], True, "_element('editEinplanbar').checked = true; plantafelZeigen();")[:4] == [True, False, False, False]
    # ohne freies keine Auswahl; ein vergebenes zählt nicht -- ein inaktives seit 1.9.305 schon (mit „(inaktiv)“, tests/test_v705_wieder_verknuepfen_und_loeschen.py;
    # bis 1.9.304 stand hier auch ein inaktives als „zählt nicht“)
    ohne_freies = [{**FREI, "taken": True}]
    assert _zustand(OHNE, ohne_freies, True, "_element('editEinplanbar').checked = true; plantafelZeigen();")[3] is True


@nur_mit_node
def test_verknuepfen_zeigt_die_angaben_des_vorhandenen_geraets():
    danach = ("_element('editEinplanbar').checked = true; plantafelZeigen(); _element('editVerknuepfen').value = '9'; verknuepfenGewaehlt();"
              "const gewaehlt = [_element('editName').value, _element('editIdentifier').value, _element('editKurzname').value];"
              "_element('editVerknuepfen').value = ''; verknuepfenGewaehlt();"
              "return [gewaehlt, [_element('editName').value, _element('editIdentifier').value]];")
    assert _zustand(OHNE, [FREI], True, danach) == [["Anhänger Humbaur", "HS-A 77", "A 77"], ["Leiter", "HS-DK 202"]]


def test_kein_wort_ressource_auf_der_seite():
    text = SEITE.read_text(encoding="utf-8")
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    ohne_kommentare = re.sub(r"(?<![:'\"])//[^\n]*", "", ohne_kommentare)
    ohne_kommentare = re.sub(r"\{#.*?#\}", "", ohne_kommentare, flags=re.S)
    assert "Ressource" not in ohne_kommentare
    assert "Auf der Plantafel einplanbar" in text and '<h3 id="plantafelTitel">Plantafel</h3>' in text
    assert "/master-data/resources/" not in text and "editResource" not in text  # kein Weg mehr ins Ressourcen-Formular


def test_aufbau():
    text = SEITE.read_text(encoding="utf-8")
    assert '<a href="/settings#outlook-sync"' in text and "document.getElementById('postfachLink').hidden=!istAdmin;" in text
    assert "...(einplanbar?{ressource:{kurzname:document.getElementById('editKurzname').value.trim()||null}}:{})," in text
    assert "...(verknuepfen?{resource_id:verknuepfen}:{})," in text
