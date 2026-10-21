"""Seit 1.9.21 (Stufe 2, Runde 8): Seitenkopf der Gruppen „Untermenü links“ (K5: Stammdaten, Einstellungen, Backoffice) und
„Zurück-Link + Karte“ (K6: Mein Konto, Benutzer, Änderungshistorie, Adressimport, Leistungskatalog), befund-rahmen.md.

    Pfad           die K6-Seiten tragen den bisherigen Rückweg als Pfad im Seitenkopf (statt „← …“), das letzte Glied ist die Seite
                   selbst; je Rolle, die die Seite öffnet, gerendert, und jedes Ziel öffnet sich für diese Rolle (200 ohne Umleitung) --
                   die Monteurin geht vom Konto über „Einsätze“ nach /mobil, das Büro über „Start“ nach /
    Untermenü      die K5-Seiten sind Einstiegsseiten ihres Bereichs der Leiste: kein Pfad, das Untermenü bleibt die Navigation
    Stammdaten     „+ Hinzufügen“ ist die Hauptaktion im Kopf; render() setzt Titel und Untertitel des Bereichs im Kopf und blendet die
                   Hauptaktion über hidden aus (style.display schlüge das display von .ds-knopf)
    Einstellungen  der Kopf trägt den Titel, das Menü keine eigene Überschrift mehr
    Backoffice     der Kopf steht vor <main> -- ein Ladefehler ersetzt nur den Inhalt (main.innerHTML), der Kopf bleibt; das Raster
                   ohne min-height:100vh (mit dem Kopf darüber rollte sonst jede Seite um seine Höhe)

Gemeinsame Regeln (ein h1, .ds-seite, Links, Fokus) prüft tests/test_v441_rahmen_baustein.py für alle umgezogenen Seiten; im Browser
scripts/klicktest_rahmen.py, Teil „untermenue“.
"""

import re

import pytest

from tests import vorlagen_js as vj
from tests.test_v441_rahmen_baustein import UNTERMENUE_LINKS, ZURUECK_UND_KARTE

ADRESSE = {"master_data.html": "/master-data", "settings.html": "/settings", "time_backoffice.html": "/time-backoffice",
           "account.html": "/account", "users.html": "/users", "history.html": "/history", "address_import.html": "/address-import",
           "index.html": "/leistungskatalog"}
# je K6-Seite und Rolle (die schwächste, die sie öffnet; das Konto auch als Monteurin): Pfad-Links und das letzte Glied
PFAD = {
    ("account.html", "buero_auftrag"): ([("/", "Start")], "Mein Konto"),
    ("account.html", "field"): ([("/mobil", "Einsätze")], "Mein Konto"),
    ("users.html", "admin"): ([("/settings", "Einstellungen")], "Benutzer und Zugriff"),
    ("history.html", "buero_auftrag"): ([("/settings", "Einstellungen")], "Änderungshistorie"),
    ("address_import.html", "admin"): ([("/settings", "Einstellungen")], "Adressimport"),
    ("index.html", "buero_auftrag"): ([("/master-data", "Stammdaten"), ("/master-data#catalogs", "Leistungskataloge")], "Leistungskatalog"),
}


def _seite(client, adresse):
    antwort = client.get(adresse, follow_redirects=False)
    assert antwort.status_code == 200, (adresse, antwort.status_code)
    ohne_skripte = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    return re.sub(r"<!--.*?-->", "", ohne_skripte, flags=re.S)  # das Konto erklärt in einem Kommentar, warum kein history.back()


def test_jede_k6_seite_hat_ihren_pfad():
    assert {name for name, _ in PFAD} == ZURUECK_UND_KARTE


@pytest.mark.parametrize("name,rolle", sorted(PFAD))
def test_pfad_statt_zurueck_link(threaded_db_session, router_test_client, feste_uhr, name, rolle):
    from app.routers.pages import router as pages_router

    client = router_test_client(threaded_db_session, pages_router, role=rolle)
    markup = _seite(client, ADRESSE[name])
    glieder, ende = PFAD[(name, rolle)]
    nav = re.search(r'<nav class="ds-kopf-pfad" id="seitenkopfPfad" aria-label="Pfad">(.*?)</nav>', markup, flags=re.S).group(1)
    assert re.findall(r'<a class="ds-kopf-pfadglied" href="([^"]*)">([^<]*)</a>', nav) == glieder
    assert re.findall(r'<span class="ds-kopf-pfadende" aria-current="page">([^<]*)</span>', nav) == [ende]
    assert re.findall(r'id="seitenkopfTitel">([^<]*)</h1>', markup) == [ende]  # das letzte Glied ist die Seite selbst
    assert 'class="back' not in markup and "history.back" not in markup
    for ziel, _ in glieder:
        antwort = client.get(ziel.split("#")[0], follow_redirects=False)
        assert antwort.status_code == 200 and antwort.headers["content-type"].startswith("text/html"), (ziel, antwort.status_code)


@pytest.mark.parametrize("name", sorted(UNTERMENUE_LINKS))
def test_untermenue_seiten_ohne_pfad(threaded_db_session, router_test_client, name):
    from app.routers.pages import router as pages_router

    markup = _seite(router_test_client(threaded_db_session, pages_router, role="buero_auftrag"), ADRESSE[name])
    assert 'id="seitenkopf"' in markup and 'id="seitenkopfPfad"' not in markup


def test_stammdaten_hinzufuegen_ist_die_hauptaktion_im_kopf():
    text = (vj.TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    block = re.search(r"\{%\s*call\(teil\)\s*seitenkopf\(.*?\{%\s*endcall\s*%\}", text, flags=re.S).group(0)
    assert re.findall(r"<a [^>]*>[^<]*</a>", block) == ['<a id="addLink" class="ds-knopf ds-knopf-aktion" href="#">+ Hinzufügen</a>']
    skript = vj.eigene_skripte("master_data.html").text
    assert "getElementById('seitenkopfTitel')" in skript and "getElementById('seitenkopfUntertitel')" in skript
    assert "add.style.display" not in skript and "add.hidden=!canManageEmployees;" in skript
    assert skript.count("add.hidden=false;") == 10


def test_einstellungen_menue_ohne_eigene_ueberschrift():
    text = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    menue = text[text.index('<aside class="settings-sidebar"'):text.index("</aside>", text.index('<aside class="settings-sidebar"'))]
    assert "<h2" not in menue and '{{ seitenkopf("Einstellungen") }}' in text


def test_backoffice_kopf_ueberlebt_den_ladefehler():
    text = (vj.TEMPLATES / "time_backoffice.html").read_text(encoding="utf-8")
    assert text.index('{{ seitenkopf("Zeiterfassungs-Backoffice"') < text.index("</aside><main>")  # main = Inhalt rechts vom Untermenü
    assert "document.querySelector('main').innerHTML=" in vj.eigene_skripte("time_backoffice.html").text
    raster = re.search(r"\.layout\{[^}]*\}", text).group(0)
    assert "min-height" not in raster
