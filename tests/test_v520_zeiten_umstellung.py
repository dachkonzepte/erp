"""Version 1.9.98 (Stufe 4, R5b, Punkt 1) -- die Seite „Zeiten“ ersetzt Zeiterfassung (Büro) und Backoffice.

In der Leiste ein Eintrag „Zeiten“ statt „Zeiterfassung“ und „Backoffice“; die alten Adressen leiten weiter (das Büro auf „Zeiten“ mit Filter
und Reiter, die Monteurin auf „Meine Zeiten“), die Anker der früheren Reiter öffnen die neuen. Jede Funktion der alten Seiten (Liste aus dem
Befund R5, docs/archiv/redesign.md, „R5, Teil 2“) ist auf „Zeiten“ erreichbar -- oder entfällt mit der Entscheidung, die sie ersetzt.
"""

import json
import re

import pytest

from app.routers.pages import router as pages_router
from tests import vorlagen_js as vj
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

BUERO = ("buero_auftrag", "buero_finanzen", "admin")


def _ziel(client, url):
    antwort = client.get(url, follow_redirects=False)
    assert antwort.status_code == 302, (url, antwort.status_code)
    return antwort.headers["location"]


# --- alte Adressen ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle", BUERO)
def test_alte_adressen_fuehren_das_buero_auf_zeiten(rolle, threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router, role=rolle)
    assert _ziel(client, "/time-tracking") == "/zeiten"
    assert _ziel(client, "/time-tracking?order_id=5") == "/zeiten?auftrag=5#buchungen"  # Einsatzbericht, Arbeitsvorbereitung (bis 1.9.97)
    assert _ziel(client, "/time-tracking?employee_id=3") == "/zeiten?mitarbeiter=3#buchungen"
    assert _ziel(client, "/time-tracking?order_id=5&employee_id=3") == "/zeiten?auftrag=5&mitarbeiter=3#buchungen"
    assert _ziel(client, "/time-backoffice") == "/zeiten"  # den Anker (#entries …) nimmt der Browser mit
    assert _ziel(client, "/time-backoffice?absence=7") == "/zeiten?absence=7"  # Freigabe auf dem Dashboard (bis 1.9.97)
    assert client.get("/zeiten").status_code == 200


def test_alte_adressen_fuehren_die_monteurin_zu_meine_zeiten(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router, role="field")
    assert _ziel(client, "/time-tracking") == "/mobil/zeiten"
    assert _ziel(client, "/time-tracking?order_id=5") == "/mobil/zeiten?order_id=5"
    assert _ziel(client, "/time-backoffice") == "/mobil/zeiten"
    assert _ziel(client, "/time-backoffice?absence=7") == "/mobil/zeiten"
    assert _ziel(client, "/zeiten") == "/mobil/zeiten"


@pytest.mark.parametrize("rolle", ("field", "buero_finanzen"))
@pytest.mark.parametrize("wert", ["²", "٣", "5x", "-1", "1e3", " 5", "//evil.example", "5%23x", "5%26x=1", "1" * 5000])
def test_nur_eine_zahl_geht_mit(rolle, wert, threaded_db_session, router_test_client):
    """Angriff: was keine Zahl aus 0–9 ist, fällt weg -- auch eine hochgestellte „²“ (isdigit() wahr, int() scheitert: bis 1.9.97 500) und
    eine Zahl mit 5000 Stellen (int() scheitert über 4300 Stellen)."""
    client = router_test_client(threaded_db_session, pages_router, role=rolle)
    for url in (f"/time-tracking?order_id={wert}", f"/time-tracking?employee_id={wert}", f"/time-backoffice?absence={wert}"):
        ziel = _ziel(client, url)
        assert ziel in ("/zeiten", "/mobil/zeiten"), (url, ziel)


def test_zurueck_links_nehmen_nur_zahlen(threaded_db_session, router_test_client):
    """Derselbe Fehler stand seit 1.8.135 in den Zurück-Links der Formularseiten (?customer_id=², ?project_id=², ?projekt=²) und in ?report= der
    Einsatzberichte -- seit 1.9.98 eine Prüfung für alle (app/routers/pages.py::_zahl())."""
    from app.routers.pages import _zahl
    assert [_zahl(x) for x in ("5", "²", "٣", "", None, "1" * 5000, "0012")] == [5, None, None, None, None, None, 12]
    client = router_test_client(threaded_db_session, pages_router, role="admin")
    for url in ("/projects/new?customer_id=²", "/quotes/new?project_id=²", "/master-data/contacts/new?projekt=²",
                "/orders/1/service-reports?report=²", "/projects/new?customer_id=" + "1" * 5000):
        assert client.get(url, follow_redirects=False).status_code in (200, 302), url


# --- Anker der früheren Reiter -------------------------------------------------------------------------------------------------------

def _binden(anker: str, lohndaten: bool, suche: str = ""):
    ablauf = f"""
      RECHTE = {{lohndaten: {json.dumps(lohndaten)}}};
      location.hash = {json.dumps(anker)}; location.search = {json.dumps(suche)};
      let ziel = null, reiter = null;
      location.replace = u => {{ ziel = u; }};
      reiterZeigen = r => {{ reiter = r; }};
      binden();
      return [reiter, ziel];"""
    return im_browser(seite("zeiten.html", "binden();"), ablauf)["ergebnis"]


@nur_mit_node
@pytest.mark.parametrize("anker, lohndaten, soll", [
    ("", True, ["pruefen", None]),
    ("#dashboard", True, ["pruefen", None]), ("#entries", True, ["buchungen", None]), ("#absences", True, ["abwesenheiten", None]),
    ("#timesheets", True, ["monat", None]), ("#datev", True, ["monat", None]),
    ("#timesheets", False, ["pruefen", None]), ("#datev", False, ["pruefen", None]),  # Büro – Auftrag: kein „Monat & Lohn“
    ("#workmodels", True, [None, "/settings#time-rules"]), ("#settings", True, [None, "/settings#time-rules"]),
    ("#options", True, [None, "/settings#time-entry-types"]),
    ("#buchungen", True, ["buchungen", None]), ("#monat", False, ["pruefen", None]),
])
def test_anker_der_frueheren_reiter(anker, lohndaten, soll):
    assert _binden(anker, lohndaten) == soll


@nur_mit_node
def test_absence_oeffnet_die_abwesenheiten():
    assert _binden("", True, "?absence=7") == ["abwesenheiten", None]
    assert _binden("", True, "?absence=7x") == ["pruefen", None]


# --- Leiste und Links ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle", BUERO)
def test_leiste_ein_eintrag_zeiten(rolle, threaded_db_session, router_test_client):
    text = router_test_client(threaded_db_session, pages_router, role=rolle).get("/zeiten").text
    leiste = text.split('id="appSidebar"', 1)[1].split("</aside>", 1)[0]
    eintraege = re.findall(r'<a class="app-sidebar-link[^"]*" data-bereich="([^"]+)" href="([^"]+)"', leiste)
    assert ("zeiten", "/zeiten") in eintraege
    assert not [e for e in eintraege if e[1] in ("/time-tracking", "/time-backoffice")], eintraege
    assert 'aria-current="page"' in leiste.split('data-bereich="zeiten"', 1)[1].split("</a>", 1)[0]


ALTE_ADRESSE = re.compile(r"(?<![\w])/time-(tracking|backoffice)\b")


def test_kein_link_mehr_auf_die_alten_adressen():
    """Kein Link einer Vorlage führt mehr auf die alten Adressen (nur noch Kommentare nennen sie); /api/time-tracking/… zählt nicht."""
    funde = []
    for name in vj.alle_vorlagen():
        text = re.sub(r"<!--.*?-->|\{#.*?#\}", "", (vj.TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S)
        for zeile in text.splitlines():
            code = zeile.split("//", 1)[0] if "//" in zeile and "http" not in zeile else zeile
            if ALTE_ADRESSE.search(code):
                funde.append((name, zeile.strip()[:120]))
    assert funde == []


# --- jede Funktion der alten Seiten -------------------------------------------------------------------------------------------------

EIGENE_ZEIT = ("Entscheidung R5a (26.10.2026): das Büro erfasst keine eigene Zeit -- laufende Zeiten anderer stehen unter „Buchungen“ "
               "(„läuft“), eine von früher schließt „Ende eintragen“ unter „Prüfen“")
KOLONNE_START = ("die Kolonne startet der Kolonnenführer auf „Heute“ (seit 1.9.58); das Büro bucht sie nachträglich mit Von–Bis oder "
                 "Dauer („Kolonne buchen“)")

# (alte Seite, Funktion laut Befund R5, Reiter auf „Zeiten“ oder None, Belege in der Seite des Admins -- oder der Grund, warum sie entfällt)
FUNKTIONEN = [
    ("Zeiterfassung", "„Mitarbeiter“ (nur Admin): wessen Zeiten die Seite zeigt und bucht", "buchungen",
     ['id="filterMitarbeiter"', 'id="bdMitarbeiter"', "'/api/zeiten/buchungen'"]),
    ("Zeiterfassung", "„Laufende Zeiterfassung“: Uhr, „■ Zeit stoppen“", None, EIGENE_ZEIT),
    ("Zeiterfassung", "„Ende nachtragen“ bei einer Zeit von früher", "pruefen",
     ['id="offenListe"', "'/ende-vorschau?ende='", "'/ende-nachtragen'"]),
    ("Zeiterfassung", "„Schnell starten“ mit ▶ Baustelle / Fahrzeit / Werkstatt / Sonstige", None, EIGENE_ZEIT),
    ("Zeiterfassung", "„Heutige Buchungen“: Kacheln Produktiv, Fahrzeit, Gesamt", "pruefen",
     ['id="monatZeilen"', 'id="monatGebucht"', 'id="monatFahrzeit"', "'/api/zeiten/pruefen'"]),
    ("Zeiterfassung", "„Heutige Buchungen“: Liste mit „Ändern“ und „×“", "buchungen",
     ['id="buchungenZeilen"', 'id="buchungDialog"', 'id="loeschDialog"', "'/api/time-entries/'", "method:'DELETE'"]),
    ("Zeiterfassung", "„+ Manuell buchen“ (Dauer, Pause, Mitarbeiter für den Admin)", "kopf",
     ['id="neueBuchung"', 'id="bdModusDauer"', 'id="bdStunden"', 'id="bdPauseDauer"', "'/api/time-entries'"]),
    ("Zeiterfassung", "„👥 Gruppe buchen“: Kolonne, Mitglieder, Stunden je Mitarbeiter, Pause", "kopf",
     ['id="kolonneBuchen"', 'id="kolonneDialog"', 'id="kdMitglieder"', 'id="kdModusDauer"', "'/api/time-entry-groups'"]),
    ("Zeiterfassung", "„▶ Gruppen-Timer starten“", None, KOLONNE_START),
    ("Zeiterfassung", "„📅 Abwesenheit“: Antrag stellen", "abwesenheiten",
     ['id="abwNeu"', 'id="abwDialog"', 'id="adKategorie"', 'id="adArt"', "'/api/absence-requests'"]),
    ("Zeiterfassung", "Anträge: Liste, Genehmigen/Ablehnen (Admin), eigene zurückziehen", "abwesenheiten",
     ['id="abwListe"', "'/api/zeiten/abwesenheiten'", "'/review'", "method:'DELETE'"]),
    ("Zeiterfassung", "Hinweis auf offene Anträge (Admin)", "kopf", ['id="zahlAbwesenheiten"', 'id="antragListe"']),
    ("Zeiterfassung", "„Auswertung“: die Buchungen eines gewählten Tags", "buchungen",
     ['id="buchungenZeilen"', 'id="buchungenMonat"', 'id="summeAuswahl"']),
    ("Backoffice", "Filter „von“, „bis“, „Mitarbeiter“, „Aktualisieren“", "buchungen",
     ['id="buchungenMonat"', 'id="filterMitarbeiter"', 'id="filterAuftrag"', 'id="filterZeitart"']),
    ("Backoffice", "„Dashboard“: Kacheln und „Stunden je Mitarbeiter“", "pruefen",
     ['id="monatZeilen"', 'id="lohnZeilen"', "'/api/zeiten/monat'"]),
    ("Backoffice", "„Dashboard“: offene Abwesenheitsanträge", "pruefen", ['id="antragListe"']),
    ("Backoffice", "„Buchungen“: Tabelle mit „Bearbeiten“ und „Löschen“", "buchungen", ['id="buchungenZeilen"', "'/api/time-entries/'"]),
    ("Backoffice", "„Zeitbuchung bearbeiten“: Auftrag, LV-Position, Datum, Stunden, Zeitart, Tätigkeit, Notiz", "buchungen",
     ['id="bdAuftrag"', 'id="bdPosition"', 'id="bdDatum"', 'id="bdStunden"', 'id="bdZeitart"', 'id="bdTaetigkeit"', 'id="bdNotiz"']),
    ("Backoffice", "„Abwesenheiten“: Genehmigen/Ablehnen (Admin), dem Büro die eigenen", "abwesenheiten",
     ['id="abwListe"', 'id="abwStatus"', "'/review'"]),
    ("Backoffice", "„Stundenzettel“: PDF und CSV", "monat",
     ['id="lohnPdf"', 'id="lohnCsv"', "'/api/time-backoffice/timesheet.pdf?'", "'/api/time-backoffice/timesheet.csv?'"]),
    ("Backoffice", "„DATEV / Lohn“: „Abgeschlossen bis“ mit „Abschließen“", "monat",
     ['id="lohnStatus"', 'id="lohnAbschliessen"', "'/api/time-backoffice/lock'"]),
    ("Backoffice", "„Abschluss aufheben“ (Admin)", "kopf", ['id="abschlussAufheben"', 'id="aufhebenDialog"', 'id="ahBis"']),
    ("Backoffice", "„DATEV-Lohndaten exportieren“ mit Stand", "monat",
     ['id="lohnDatev"', 'id="lohnDatevFehlt"', "'/api/time-backoffice/datev-export?'"]),
    ("Backoffice", "„Einrichtung“: Zeitregeln und DATEV, Zeit-Listen", "kopf",
     ['href="/settings#time-rules"', 'href="/settings#time-entry-types"']),
    ("Befund R5", "„Pausen neu rechnen“ (fehlte dem Büro)", "pruefen", ['id="pauseListe"', "'/api/time-entries/pausen-neu-rechnen'"]),
    ("Befund R5", "Übersicht aller offenen Zeiten (fehlte)", "pruefen", ['id="offenListe"', 'id="zahlPruefen"']),
    ("Befund R5", "Von/Bis beim Ändern (fehlte)", "buchungen",
     ['id="bdModusVonBis"', 'id="bdVon"', 'id="bdBis"', "'/api/time-entries/nachtrag-vorschau?work_date='"]),
    ("Befund R5", "Kolonne mit Von/Bis (fehlte)", "kopf",
     ['id="kdModusVonBis"', 'id="kdVon"', "'/api/time-entry-groups/nachtrag-vorschau?work_date='"]),
]


def test_funktionen_vollstaendig_aus_dem_befund():
    """Die Liste deckt jede Funktion des Befunds ab (je Seite die Zahl der Spiegelstriche unter „Funktionen:“) -- entfallen dürfen nur die
    eigene Uhr (zwei Funktionen) und der Gruppen-Timer."""
    archiv = (vj.TEMPLATES.parent.parent / "docs" / "archiv" / "redesign.md").read_text(encoding="utf-8")
    befund = archiv.split("### R5, Teil 2: Befund der Büroseiten der Zeiterfassung", 1)[1].split("#### DATEV-Export", 1)[0]
    zt, bo = befund.split("#### Zeiterfassungs-Backoffice", 1)
    zaehle = lambda teil: len(re.findall(r"^- ", teil.split("Funktionen:", 1)[1].split("Was dort", 1)[0], flags=re.M))  # noqa: E731
    assert (zaehle(zt), zaehle(bo)) == (8, 8)
    seiten = {s: [f for f in FUNKTIONEN if f[0] == s] for s in ("Zeiterfassung", "Backoffice")}
    assert len(seiten["Zeiterfassung"]) >= 8 and len(seiten["Backoffice"]) >= 8
    assert [f[1] for f in FUNKTIONEN if f[2] is None] == [
        "„Laufende Zeiterfassung“: Uhr, „■ Zeit stoppen“", "„Schnell starten“ mit ▶ Baustelle / Fahrzeit / Werkstatt / Sonstige",
        "„▶ Gruppen-Timer starten“"]


def test_jede_funktion_der_alten_seiten_erreichbar(threaded_db_session, router_test_client):
    text = router_test_client(threaded_db_session, pages_router, role="admin").get("/zeiten").text
    fehlt = [(alt, funktion, beleg) for alt, funktion, reiter, belege in FUNKTIONEN if reiter for beleg in belege if beleg not in text]
    assert fehlt == []
    reiter = set(re.findall(r'data-reiter="([a-z]+)"', text))
    assert {f[2] for f in FUNKTIONEN if f[2]} - {"kopf"} <= reiter


@pytest.mark.parametrize("rolle, ohne", [
    ("buero_finanzen", ['id="abschlussAufheben"']),
    ("buero_auftrag", ['id="neueBuchung"', 'id="kolonneBuchen"', 'id="abschlussAufheben"', 'data-reiter="monat"', 'id="lohnPdf"',
                       'id="lohnDatev"', 'id="lohnAbschliessen"']),
])
def test_funktionen_je_rolle(rolle, ohne, threaded_db_session, router_test_client):
    """Was eine Rolle nicht darf, fehlt im Markup (Ausblenden statt ausgrauen): Büro – Finanzen alles außer „Abschluss aufheben“, Büro –
    Auftrag ohne Buchen, ohne „Monat & Lohn“."""
    text = router_test_client(threaded_db_session, pages_router, role=rolle).get("/zeiten").text
    markup = re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)
    assert [x for x in ohne if x in markup] == []
    assert 'data-reiter="pruefen"' in markup and 'data-reiter="buchungen"' in markup and 'data-reiter="abwesenheiten"' in markup
