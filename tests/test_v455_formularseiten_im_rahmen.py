"""Seit 1.9.22 (Stufe 2, Runde 8, Punkt 3; Entscheidung 5 der Seitenprüfung): die Formularseiten Stammdaten-Formular
(master_data_form.html) und Leistung (service_form.html) im Rahmen -- Leiste (Bereich Stammdaten), Kopfzeile, Seitenkopf mit Pfad.

    Pfad           Bereich der Leiste, dann der bisherige Rückweg, am Ende die Seite selbst (titel() setzt Titel und letztes Glied);
                   aus der Projektmappe kommend (Kontakt anlegen) Projekte / Projektmappe; jedes Ziel öffnet sich (200)
    Kopf           „Abbrechen“ neutral zum bisherigen Zurück-Ziel (dasselbe wie das letzte Glied des Pfads), „Speichern“ grün -- es ruft
                   dasselbe save() wie der Knopf unten, der bleibt; bleibt die Seite nach dem Speichern stehen, rückt die Meldung ins Bild
    unverändert    Felder und Speichern: der Knopf unten mit onclick="save()", save() selbst, die Ziele nach dem Speichern
    importiert     eine importierte Leistung speichert nicht: „Speichern“ im Kopf verborgen wie der Knopf unten

Im Browser: scripts/klicktest_rahmen.py, Teil „formularseiten“.
"""

import html
import re

import pytest

from app.routers.pages import STAMMDATEN_BEREICHE, pfad_stammdaten, zurueck_stammdaten
from tests import vorlagen_js as vj

SEITEN = ("master_data_form.html", "service_form.html")
FAELLE = [
    ("/master-data/employees/1/edit", [("/master-data", "Stammdaten"), ("/master-data#employees", "Mitarbeiter")]),
    ("/master-data/customers/new", [("/master-data", "Stammdaten"), ("/master-data#customers", "Kunden")]),
    ("/master-data/resources/new", [("/master-data", "Stammdaten"), ("/master-data#assets", "Fuhrpark & Maschinen")]),
    ("/master-data/materials/new", [("/master-data", "Stammdaten"), ("/master-data#materials", "Materialkataloge")]),
    ("/master-data/teams/2/edit", [("/master-data", "Stammdaten"), ("/master-data#teams", "Kolonnen / Teams")]),
    ("/master-data/properties/3/edit", [("/master-data", "Stammdaten"), ("/properties/3", "Objekt")]),
    ("/master-data/contacts/new?projekt=7", [("/projects", "Projekte"), ("/projects/7#sec-participants", "Projektmappe")]),
    ("/services/1/edit", [("/master-data", "Stammdaten"), ("/master-data#catalogs", "Leistungskataloge"), ("/leistungskatalog", "Leistungskatalog")]),
    ("/services/new", [("/master-data", "Stammdaten"), ("/master-data#catalogs", "Leistungskataloge"), ("/leistungskatalog", "Leistungskatalog")]),
]


def _call_block(name):
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    return re.search(r"\{%\s*call\(teil\)\s*seitenkopf\(.*?\{%\s*endcall\s*%\}", text, flags=re.S).group(0)


@pytest.mark.parametrize("name", SEITEN)
def test_im_rahmen_mit_bereich_stammdaten(name):
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    assert text.startswith('{% set bereich = "stammdaten" -%}')
    assert vj.bindet_ein(name, "_sidebar.html") and vj.bindet_ein(name, "_topbar.html") and vj.bindet_ein(name, "_aktionen.html")
    assert 'id="heading"' not in text and "el('heading')" not in text and 'class="back"' not in text


@pytest.mark.parametrize("name", SEITEN)
def test_kopf_abbrechen_neutral_speichern_gruen_knopf_unten_bleibt(name):
    aktion = re.search(r'teil == "aktion" %\}(.*?)\{%\s*endif', _call_block(name), flags=re.S).group(1)
    assert aktion == ('<a class="ds-knopf" id="abbrechenLink" href="{{ zurueck.href }}">Abbrechen</a>'
                      '<button type="button" class="ds-knopf ds-knopf-aktion" id="kopfSpeichern" data-klick="speichern">Speichern</button>')
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    assert text.count('<button id="saveBtn" onclick="save()">Speichern</button>') == 1
    skript = re.sub(r"\s+", "", vj.eigene_skripte(name).text)
    # „Speichern“ im Kopf ruft dasselbe save() wie der Knopf unten und holt danach die Meldung ins Bild
    assert re.search(r"aktion\('speichern',async\(\)=>\{awaitsave\(\);if\(el\('msg'\)\.textContent\)"
                     r"el\('msg'\)\.scrollIntoView\(\{block:'center'\}\);?\}\);", skript)


@pytest.mark.parametrize("name,anzahl", [("master_data_form.html", 11), ("service_form.html", 3)])
def test_jeder_titel_ueber_titel(name, anzahl):
    skript = vj.eigene_skripte(name).text
    assert len(re.findall(r"\btitel\(", skript)) == anzahl + 1  # die Aufrufe und die Definition
    assert re.search(r"function titel\(t\)\s*\{\s*seitenkopf\(\{\s*titel:\s*t,\s*pfad:\s*\[\.\.\.PFAD,\s*\{\s*text:\s*t\s*\}\]\s*\}\);?\s*\}", skript)


def test_pfad_endet_am_bisherigen_zurueck_ziel():
    """Für jeden Bereich des Formulars: das letzte Glied vor der Seite ist das Ziel von „Abbrechen“ (zurueck_stammdaten())."""
    for data_type in STAMMDATEN_BEREICHE:
        for kw in ({}, {"record_id": 4}, {"projekt": 9}):
            pfad = pfad_stammdaten(data_type, **kw)
            assert pfad[-1]["href"] == zurueck_stammdaten(data_type, **kw)["href"], (data_type, kw)
            assert pfad[0] in ({"href": "/master-data", "text": "Stammdaten"}, {"href": "/projects", "text": "Projekte"})


@pytest.mark.parametrize("adresse,glieder", FAELLE)
def test_pfad_gerendert_und_ziele_oeffnen_sich(threaded_db_session, router_test_client, adresse, glieder):
    from app.routers.pages import router as pages_router

    client = router_test_client(threaded_db_session, pages_router, role="buero_finanzen")
    antwort = client.get(adresse, follow_redirects=False)
    assert antwort.status_code == 200
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    nav = re.search(r'<nav class="ds-kopf-pfad" id="seitenkopfPfad" aria-label="Pfad">(.*?)</nav>', markup, flags=re.S).group(1)
    assert [(html.unescape(h), html.unescape(t)) for h, t in re.findall(r'<a class="ds-kopf-pfadglied" href="([^"]*)">([^<]*)</a>', nav)] == glieder
    abbrechen = re.search(r'<a class="ds-knopf" id="abbrechenLink" href="([^"]*)">Abbrechen</a>', markup).group(1)
    assert html.unescape(abbrechen) == glieder[-1][0]
    for ziel, _ in glieder:
        assert client.get(ziel.split("#")[0], follow_redirects=False).status_code == 200, ziel
    assert re.findall(r'class="app-sidebar-link[^"]*\bactive\b[^"]*" data-bereich="([a-z]+)"', markup) == ["stammdaten"]


def test_importierte_leistung_speichert_auch_oben_nicht():
    skript = vj.eigene_skripte("service_form.html").text
    gesperrt = skript[skript.index("if (!isEditable(service)) {"):skript.index("return;", skript.index("if (!isEditable(service)) {"))]
    assert "el('editableArea').classList.add('hidden');" in gesperrt and "el('kopfSpeichern').hidden = true;" in gesperrt
