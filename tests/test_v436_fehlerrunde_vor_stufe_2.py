"""Fehlerrunde vor Stufe 2 des Redesigns (1.8.132 ff., Vorgabe vom 19.10.2026): je Punkt ein Test, der vor der Behebung scheiterte.

    1  Anfragen: „Projekt öffnen“ führt direkt in die Projektmappe, „Projekt + Angebot erzeugen“ direkt ins neue Angebot (1.8.132)
    2  LV-Editor und Auftrag ohne Überlauf: Klicktest scripts/klicktest_lv_ueberlauf.py (nur im Browser messbar, 1.8.133)
    3  /users nur für Administratoren, ohne den Satz zur Ersteinrichtung (1.8.134)
    4  Zurück-Links der Formularseiten mit echtem Ziel und Namen statt history.back() (1.8.135)
    5  LV-Editor: ein Weg zum Auftrag (1.8.136)
    6  Zeiterfassung (Büro): ein Knopf zum manuellen Buchen (1.8.137)
    7  Änderungshistorie: lesbare Namen, Blättern (1.8.138)
    8  Seitentitel einheitlich „DACHKONZEPTE ERP – <Seite>“ ohne Versionsnummer (1.8.139)
    9  Leistung bearbeiten: Standardwerte der Prozente als „0 %“ statt „0.0000%“ (1.8.140)
   10  Finanzen ohne den Platzhalter „Weitere buchhalterische Themen folgen hier künftig.“ (1.8.141)
"""

import html
import json
import re

import pytest

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite


# ---------------------------------------------------------------------------
# 1. Anfragen: Projekt öffnen, Projekt + Angebot erzeugen
# ---------------------------------------------------------------------------

@nur_mit_node
def test_anfrage_projekt_oeffnen_fuehrt_in_die_projektmappe():
    """Bis 1.8.131 ging „Projekt öffnen“ auf /projects?project_id=7 -- die Projektliste wertet den Parameter nicht aus, man landete in der
    ganzen Liste."""
    lauf = im_browser(seite("inquiries.html", "init();\n"), """
      currentInquiry = {id: 3, project_id: 7};
      openLinkedProject();
      return location.href;""")
    assert lauf["ergebnis"] == "/projects/7"


@nur_mit_node
def test_nach_projekt_und_angebot_erzeugen_ins_neue_angebot():
    """Bis 1.8.131 blieb die Seite nach dem Umwandeln stehen (nur Statuszeile)."""
    antwort = {"inquiry": {"id": 3, "project_id": 7}, "project": {"id": 7, "project_number": "P-2026-0007"},
               "quote": {"id": 9, "quote_number": "A-2026-0009"}}
    lauf = im_browser(seite("inquiries.html", "init();\n"), f"""
      const echt = globalThis.fetch;
      globalThis.fetch = async (url, opt = {{}}) => {{
        if (opt.method !== 'POST' || url !== '/api/inquiries/3/convert') return echt(url, opt);
        AUFRUFE.push({{url, methode: 'POST'}});
        return {{ok: true, status: 200, statusText: 'OK', headers: {{get: () => 'application/json'}}, json: async () => ({json.dumps(antwort)})}};
      }};
      loadAll = async () => {{}};
      inquiries = [{{id: 3, project_id: null, title: 'Undichtes Flachdach'}}];
      currentInquiry = {{id: 3, project_id: null, title: 'Undichtes Flachdach'}};
      await convertInquiry();
      return location.href;""")
    assert lauf["ergebnis"] == "/quotes/9/edit"
    assert [a["url"] for a in lauf["aufrufe"] if a["methode"] == "POST"] == ["/api/inquiries/3/convert"]


# ---------------------------------------------------------------------------
# 3. /users: jede Rolle sieht nur, was sie darf
# ---------------------------------------------------------------------------

def _benutzerseite(rolle):
    from app.models import AppUser
    from app.routers import pages, users
    from app.auth import COOKIE_NAME
    from app.sitzungen import neue_sitzung
    from tests.anmeldung import app_mit_schranke, browser_client, neue_datenbank

    engine, make_session = neue_datenbank()
    with make_session() as db:
        nutzer = AppUser(username="u", display_name="U", role=rolle, password_hash="x")
        db.add(nutzer)
        db.flush()
        cookie = neue_sitzung(db, nutzer, zweiter_faktor=True)
        db.commit()
    client = browser_client(app_mit_schranke(make_session, pages.router, users.router), follow_redirects=False)
    client.cookies.set(COOKIE_NAME, cookie, domain="testserver.local")
    try:
        return client.get("/users")
    finally:
        engine.dispose()


def test_benutzerseite_nur_fuer_admins():
    """Bis 1.8.132 öffnete das Büro die Seite (ab Büro – Auftrag), sah statt der Liste die Fehlermeldung der API (Liste nur Admin) und
    trotzdem das Formular „Benutzer hinzufügen“ (Anlegen nur Admin)."""
    for rolle in ("buero_finanzen", "buero_auftrag", "field"):
        antwort = _benutzerseite(rolle)
        assert antwort.status_code == 403 and 'id="editorCard"' not in antwort.text, rolle
    antwort = _benutzerseite("admin")
    assert antwort.status_code == 200 and 'id="editorCard"' in antwort.text and "Benutzer hinzufügen" in antwort.text


def test_satz_zur_ersteinrichtung_entfernt():
    """Seit 1.8.130 entsteht das erste Konto nur per scripts/erstes_konto.py -- der Satz auf der Seite stimmte nicht mehr."""
    text = _benutzerseite("admin").text
    assert "Der erste angelegte Benutzer wird automatisch Administrator" not in text
    assert "automatisch Administrator" not in text


# ---------------------------------------------------------------------------
# 4. Zurück-Links mit echtem Ziel und echtem Namen
# ---------------------------------------------------------------------------

FORMULARSEITEN = ("project_form.html", "quote_form.html", "master_data_form.html", "service_form.html")


@pytest.mark.parametrize("adresse,ziel,name", [
    ("/projects/new", "/projects", "Projekte"),
    ("/projects/new?customer_id=5", "/customers/5", "Kundenakte"),
    ("/quotes/new", "/projects", "Projekte"),
    ("/quotes/new?project_id=7", "/projects/7", "Projektmappe"),
    # seit 1.9.22 (Stufe 2, Runde 8) Stammdaten-Formular und Leistung im Rahmen: statt „← Name“ das letzte Glied des Pfads und
    # „Abbrechen“ im Seitenkopf, beide zum selben Ziel wie bisher (bis dahin „← Stammdaten: Mitarbeiter“ usw.)
    ("/master-data/employees/1/edit", "/master-data#employees", "Mitarbeiter"),
    ("/master-data/customers/new", "/master-data#customers", "Kunden"),
    ("/master-data/resources/new", "/master-data#assets", "Fuhrpark & Maschinen"),
    ("/master-data/assets/new", "/master-data#assets", "Betriebsmittel"),
    ("/master-data/materials/new", "/master-data#materials", "Materialkataloge"),
    ("/master-data/properties/3/edit", "/properties/3", "Objekt"),
    ("/master-data/contacts/new?projekt=7", "/projects/7#sec-participants", "Projektmappe"),
    ("/services/1/edit", "/leistungskatalog", "Leistungskatalog"),
    ("/services/new", "/leistungskatalog", "Leistungskatalog"),
])
def test_zurueck_link_mit_echtem_ziel(threaded_db_session, router_test_client, adresse, ziel, name):
    """Bis 1.8.134 gingen alle vier per history.back() zurück (nach direktem Aufruf ins Leere) und nannten teils Seiten, die es nicht
    gibt („← Projekte & Belege“, „← Angebote“)."""
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role="buero_finanzen").get(adresse, follow_redirects=False)
    assert antwort.status_code == 200
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)  # Anker in Skript-Zeichenketten zählen nicht
    if adresse.startswith(("/master-data/", "/services/")):
        assert 'class="back' not in markup
        glied = re.findall(r'<a class="ds-kopf-pfadglied" href="([^"]*)">([^<]*)</a>', markup)[-1]
        abbrechen = re.search(r'<a class="ds-knopf" id="abbrechenLink" href="([^"]*)"[^>]*>Abbrechen</a>', markup).group(1)
        assert [html.unescape(glied[0]), html.unescape(glied[1]), html.unescape(abbrechen)] == [ziel, name, ziel]
        return
    links = re.findall(r'<a[^>]*class="back"[^>]*>(.*?)</a>', markup, flags=re.S)
    assert len(links) == 1, links
    anker = re.search(r'<a[^>]*class="back"[^>]*>', markup).group(0)
    assert re.search(r'href="([^"]*)"', anker).group(1) == ziel and "onclick" not in anker
    assert html.unescape(links[0]).strip() == f"← {name}"


def test_kein_history_back_in_den_formularseiten():
    from tests.vorlagen_js import zusammensetzen

    for vorlage in FORMULARSEITEN:
        text, _ = zusammensetzen(vorlage)
        assert "history.back" not in text, vorlage
        assert "Projekte & Belege" not in text, vorlage


def test_zurueck_ziele_fuehren_auf_seiten(threaded_db_session, router_test_client):
    """Jedes Ziel ist eine Seite, die dieselbe Rolle öffnet (Hash und Parameter abgeschnitten)."""
    from app.routers.pages import router as pages_router

    client = router_test_client(threaded_db_session, pages_router, role="buero_finanzen")
    for ziel in ("/projects", "/customers/5", "/projects/7", "/master-data", "/properties/3", "/leistungskatalog"):
        assert client.get(ziel, follow_redirects=False).status_code == 200, ziel


# ---------------------------------------------------------------------------
# 5. LV-Editor: ein Knopf zum Auftrag
# ---------------------------------------------------------------------------

AUFTRAG_STAENDE = {
    "gleich": {"source_quote_in_sync": True},
    "gesperrt": {"source_quote_in_sync": False, "has_active_acceptance": True},
    "abgleichbar": {"source_quote_in_sync": False},
}


@nur_mit_node
@pytest.mark.parametrize("stand", [*AUFTRAG_STAENDE, "ohne Auftrag"])
def test_lv_editor_ein_weg_zum_auftrag(stand):
    """Bis 1.8.135 stand neben „Auftrag AUF-… öffnen“ (Hauptknopf) zusätzlich der Link „Auftrag öffnen“ -- zwei Wege zum selben Ziel.
    Nur wenn die Änderungen übernommen werden können, ist der Hauptknopf „Änderungen … übernehmen“; dann bleibt der Link der eine Weg."""
    auftrag = "null" if stand == "ohne Auftrag" else json.dumps({"id": 5, "order_number": "AUF-2026-0001", **AUFTRAG_STAENDE[stand]})
    lauf = im_browser(seite("quote_editor.html", "load().catch("), f"""
      _element('orderOpenLink').hidden = true;  // seit 1.9.18 ein Eintrag im Menü „⋮“, verborgen über das Attribut hidden
      quote = {{quote_number: 'A-1', title: 'T', customer_name: 'K', project_number: 'P', property_name: null, status: 'beauftragt',
               vat_rate: '19', items: [], sections: [], document_meta: {{}}, project_id: 1, customer_id: 1}};
      existingOrder = {auftrag};
      renderQuoteEmailSection = () => {{}};  // Versand-Baustein (_email_dispatch.html) gehört nicht zur Attrappe
      renderAll();
      const link = _element('orderOpenLink'), knopf = _element('orderButton');
      return {{link: !link.hidden ? link.textContent || 'Auftrag öffnen' : null, knopf: knopf.textContent}};""")
    e = lauf["ergebnis"]
    wege = [t for t in (e["link"], e["knopf"]) if t and t.endswith("öffnen")]
    if stand == "ohne Auftrag":
        assert wege == [] and e["knopf"] == "Angebot beauftragen"
    else:
        assert wege == ["Auftrag AUF-2026-0001 öffnen"], e
    if stand == "abgleichbar":
        assert e["knopf"] == "Änderungen in AUF-2026-0001 übernehmen"


# ---------------------------------------------------------------------------
# 6. Zeiterfassung (Büro): ein Knopf zum manuellen Buchen
# ---------------------------------------------------------------------------

def test_zeiterfassung_buero_ein_knopf_zum_manuellen_buchen(threaded_db_session, router_test_client):
    """Bis 1.8.136 öffneten „+ Manuell buchen“ (Kopf von „Heutige Buchungen“) und „+ Zeitbuchung anlegen“ (eigene Karte „Manuelle
    Buchung“) denselben Dialog. Seit 1.9.98 die Seite „Zeiten“ (bis 1.9.97 die Zeiterfassung mit „+ Manuell buchen“): ein Knopf „+ Buchung“
    im Seitenkopf."""
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role="buero_finanzen").get("/zeiten")
    assert antwort.template.name == "zeiten.html"
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    assert markup.count('id="neueBuchung"') == 1 and "Manuell buchen" not in markup


# ---------------------------------------------------------------------------
# 7. Änderungshistorie: lesbare Namen, Blättern
# ---------------------------------------------------------------------------

def _protokollierte_spalten():
    from sqlalchemy import inspect as sa_inspect

    from app.audit import AUDITED_TYPES, EXCLUDED_FIELDS

    return {(cls, a.key) for cls in AUDITED_TYPES for a in sa_inspect(cls).column_attrs
            if a.key not in EXCLUDED_FIELDS and a.key != "id"}


def test_jede_protokollierte_art_hat_einen_namen():
    """Bis 1.8.137 fehlten 16 Arten (u. a. WorkPreparationTeamEmployee) -- in der Historie stand der Klassenname."""
    from app.audit import AUDITED_TYPES, TYPE_LABELS

    assert sorted(c.__name__ for c in AUDITED_TYPES if c not in TYPE_LABELS) == []


def test_jedes_protokollierte_feld_hat_einen_namen():
    """Bis 1.8.137 fehlten 199 von 419 Feldnamen (u. a. property_address) -- in der Historie stand der Spaltenname."""
    from app.audit import FIELD_LABELS

    assert sorted({feld for _, feld in _protokollierte_spalten()} - set(FIELD_LABELS)) == []


def _feste_werte_protokollierter_spalten():
    """Spalte -> feste Werte, aus dem Katalog von tests/test_v364_feste_werte_spaltenlaenge.py (Konstanten im Code und Literale)."""
    import importlib

    from tests import test_v364_feste_werte_spaltenlaenge as t364

    tabellen = {cls.__tablename__ for cls, _ in _protokollierte_spalten()}
    aus = {}
    for schluessel, quellen in {**t364.FESTE_WERTE, **t364.FESTE_LITERALE}.items():
        tabelle, spalte = schluessel.split(".")
        if tabelle not in tabellen:
            continue
        werte = set()
        for q in quellen:
            if isinstance(q, tuple) and len(q) == 2 and isinstance(q[0], str) and q[0].startswith("app."):
                werte |= set(eval(q[1], {"mod": importlib.import_module(q[0])}))
            elif isinstance(q, (list, tuple, set, frozenset)):
                werte |= set(q)
            else:
                werte.add(q)
        aus[schluessel] = werte
    return aus


def test_feste_werte_der_historie_sind_lesbar():
    """Bis 1.8.137 stand jeder Code roh in der Historie („entwurf → beauftragt“, „pending“, „site“, „vob_b“)."""
    from app.verlauf_namen import wert_lesbar

    katalog = _feste_werte_protokollierter_spalten()
    assert len(katalog) > 50  # der Katalog wird wirklich gelesen
    roh = []
    for schluessel, werte in katalog.items():
        spalte = schluessel.split(".")[1]
        for wert in werte:
            wert = str(wert)
            if wert == wert.lower() and " " not in wert and wert_lesbar(spalte, wert) == wert:
                roh.append(f"{schluessel}={wert}")
    assert sorted(roh) == []
    assert wert_lesbar("status", "entwurf") == "Entwurf" and wert_lesbar("status", "beauftragt") == "Beauftragt"


def _historie(rollen=("admin",), zeilen=()):
    from app.models import AppUser, AuditLog
    from app.routers import audit
    from app.sitzungen import neue_sitzung
    from tests.anmeldung import app_mit_schranke, browser_client, neue_datenbank

    engine, make_session = neue_datenbank()
    cookies = {}
    with make_session() as db:
        db.info["audit_disabled"] = True
        for rolle in rollen:
            nutzer = AppUser(username=rolle, display_name=rolle, role=rolle, password_hash="x")
            db.add(nutzer)
            db.flush()
            cookies[rolle] = neue_sitzung(db, nutzer, zweiter_faktor=True)
        for z in zeilen:
            db.add(AuditLog(**z))
        db.commit()
    client = browser_client(app_mit_schranke(make_session, audit.router))
    return engine, client, cookies


def test_historie_zeigt_lesbare_namen_auch_fuer_alte_eintraege():
    """Gespeichert sind die Namen von damals -- übersetzt wird beim Lesen, auch Einträge von vor 1.8.138."""
    from datetime import datetime

    from app.auth import COOKIE_NAME

    alt = {"occurred_at": datetime(2026, 10, 1, 8), "actor_name": "Bernd", "action": "geändert"}
    engine, client, cookies = _historie(("admin", "buero_auftrag"), [
        {**alt, "entity_type": "WorkPreparationTeamEmployee", "entity_id": "4", "entity_label": "WorkPreparationTeamEmployee",
         "field_name": "employee_name_snapshot", "field_label": "employee_name_snapshot", "old_value": "Mia", "new_value": "Max"},
        {**alt, "entity_type": "Auftrag", "entity_id": "1", "entity_label": "AUF-1 · Dach", "field_name": "property_address",
         "field_label": "property_address", "old_value": None, "new_value": "Werkstr. 5"},
        {**alt, "entity_type": "Angebot", "entity_id": "2", "entity_label": "A-1 · Dach", "field_name": "status",
         "field_label": "Status", "old_value": "entwurf", "new_value": "beauftragt"},
        {**alt, "entity_type": "Mitarbeiter", "entity_id": "3", "entity_label": "Mia", "field_name": "hourly_wage",
         "field_label": "Kalkulatorischer Stundenlohn", "old_value": "20", "new_value": "22"},
    ])
    try:
        client.cookies.set(COOKIE_NAME, cookies["admin"], domain="testserver.local")
        # nur die eigenen Einträge (die Grunddaten der Testdatenbank schreiben eigene)
        zeilen = {z["entity_id"]: z for z in client.get("/api/audit-logs?actor=Bernd").json()}
        assert (zeilen["4"]["entity_type"], zeilen["4"]["entity_type_label"], zeilen["4"]["entity_label"]) == (
            "WorkPreparationTeamEmployee", "AV-Teammitglied", "AV-Teammitglied")
        assert zeilen["4"]["field_label"] == "Mitarbeiter (Name)"
        assert zeilen["1"]["field_label"] == "Objektanschrift"
        assert (zeilen["2"]["old_value"], zeilen["2"]["new_value"]) == ("Entwurf", "Beauftragt")
        # die Schwärzung für Büro – Auftrag greift weiter am rohen Feldnamen
        client.cookies.set(COOKIE_NAME, cookies["buero_auftrag"], domain="testserver.local")
        ids = {z["entity_id"] for z in client.get("/api/audit-logs?actor=Bernd").json()}
        assert "3" not in ids and {"1", "2", "4"} <= ids
    finally:
        engine.dispose()


def test_historie_blaettert():
    """Bis 1.8.137 lud die Seite bis zu 500 Einträge auf einmal; die API kannte keinen Versatz."""
    from datetime import datetime, timedelta

    from app.auth import COOKIE_NAME

    start = datetime(2026, 10, 1, 8)
    engine, client, cookies = _historie(zeilen=[
        {"occurred_at": start + timedelta(minutes=i), "actor_name": "Bernd", "action": "angelegt", "entity_type": "Testeintrag",
         "entity_id": str(i), "entity_label": f"Kunde {i}"} for i in range(150)])
    try:
        client.cookies.set(COOKIE_NAME, cookies["admin"], domain="testserver.local")
        erste = client.get("/api/audit-logs?limit=100&offset=0&entity_type=Testeintrag")
        zweite = client.get("/api/audit-logs?limit=100&offset=100&entity_type=Testeintrag")
        assert len(erste.json()) == 100 and erste.headers["x-dk-weitere"] == "1"
        assert len(zweite.json()) == 50 and zweite.headers["x-dk-weitere"] == "0"
        ids = [z["entity_id"] for z in erste.json() + zweite.json()]
        assert ids == [str(i) for i in range(149, -1, -1)]  # neueste zuerst, lückenlos, keine doppelt
    finally:
        engine.dispose()


VERLAUF_FETCH = r"""
  globalThis.fetch = async (url) => {
    AUFRUFE.push({url, methode: 'GET'});
    const erste = url.includes('offset=0');
    const zeilen = erste ? Array.from({length: 100}, (_, i) => ({id: i, occurred_at: '2026-10-01T08:00:00', actor_name: 'B',
      action: 'angelegt', entity_type: 'Kunde', entity_type_label: 'Kunde', entity_label: 'K' + i})) : [];
    return {ok: true, status: 200, statusText: 'OK',
            headers: {get: k => String(k).toLowerCase() === 'x-dk-weitere' ? (erste ? '1' : '0') : 'application/json'},
            json: async () => zeilen};
  };
"""


@nur_mit_node
def test_verlaufsseite_laedt_seitenweise():
    lauf = im_browser(seite("history.html", "load();"), VERLAUF_FETCH + """
      await load();
      await aeltere();
      return AUFRUFE.map(a => a.url);""")
    assert lauf["ergebnis"] == ["/api/audit-logs?limit=100&offset=0", "/api/audit-logs?limit=100&offset=100"]


# ---------------------------------------------------------------------------
# 8. Seitentitel einheitlich „DACHKONZEPTE ERP – <Seite>“, ohne Versionsnummer
# ---------------------------------------------------------------------------

TITEL = re.compile(r"DACHKONZEPTE ERP – [^{}<>–·]+")


def _titel_in_ordnung(titel):
    return bool(TITEL.fullmatch(titel)) and not re.search(r"Version|\d+\.\d+", titel)


def test_jede_seite_hat_den_einheitlichen_titel():
    """Bis 1.8.138 u. a. „Anfragen & Pipeline 0.6“, „Version {{ app_version }}“ (Leistungskatalog, LV-Editor), „DACHKONZEPTE ERP · …“,
    „DACHKONZEPTE GmbH - Mobil“ und Formularseiten ohne Präfix („Angebot anlegen“)."""
    from tests.vorlagen_js import seiten, zusammensetzen

    abweichend = {}
    for name in seiten():
        titel = re.findall(r"<title>(.*?)</title>", zusammensetzen(name)[0], flags=re.S)
        if len(titel) != 1 or not _titel_in_ordnung(titel[0].strip()):
            abweichend[name] = titel
    assert abweichend == {}


def test_gerenderte_titel_ohne_versionsnummer(threaded_db_session, router_test_client):
    from app.routers.pages import router as pages_router
    from tests.test_v218_template_rendering import _dummy_path

    gesehen, abweichend = 0, []
    for rolle in ("admin", "buero_finanzen", "field"):
        client = router_test_client(threaded_db_session, pages_router, role=rolle)
        for route in pages_router.routes:
            if "GET" not in getattr(route, "methods", set()) or route.path == "/health":
                continue
            antwort = client.get(_dummy_path(route.path), follow_redirects=False)
            titel = re.search(r"<title>(.*?)</title>", antwort.text, flags=re.S) if antwort.status_code == 200 else None
            if titel:
                gesehen += 1
                if not _titel_in_ordnung(html.unescape(titel.group(1)).strip()):
                    abweichend.append((rolle, route.path, titel.group(1)))
    assert gesehen > 60 and abweichend == []


# ---------------------------------------------------------------------------
# 9. Leistung bearbeiten: „Standard: 0 %“ statt „Standard: 0.0000%“
# ---------------------------------------------------------------------------

@nur_mit_node
def test_leistung_standardwerte_der_prozente_lesbar():
    """Die API liefert Prozente als Dezimaltext mit vier Stellen ("0.0000") -- bis 1.8.139 stand das roh neben dem Feld."""
    lauf = im_browser(seite("service_form.html", "init().catch("), """
      globalSettings = {labor_rate: "82.00", material_markup_pct: "0.0000", overhead_pct: "12.5000", risk_profit_pct: "5.0000"};
      renderDefaults();
      return ['markupDefault', 'overheadDefault', 'riskDefault'].map(id => _element(id).textContent);""")
    assert lauf["ergebnis"] == ["(Standard: 0 %)", "(Standard: 12,5 %)", "(Standard: 5 %)"]


# ---------------------------------------------------------------------------
# 10. Finanzen: ohne Platzhaltersatz
# ---------------------------------------------------------------------------

def test_finanzen_ohne_platzhalter(threaded_db_session, router_test_client):
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role="buero_finanzen").get("/finanzen")
    assert antwort.status_code == 200
    assert "Alle Rechnungen im Überblick." in antwort.text
    assert "folgen hier künftig" not in antwort.text and "buchhalterische Themen" not in antwort.text
