"""Fehlerrunde vor Stufe 2 des Redesigns (1.8.132 ff., Vorgabe vom 19.10.2026): je Punkt ein Test, der vor der Behebung scheiterte.

    1  Anfragen: „Projekt öffnen“ führt direkt in die Projektmappe, „Projekt + Angebot erzeugen“ direkt ins neue Angebot (1.8.132)
    2  LV-Editor und Auftrag ohne Überlauf: Klicktest scripts/klicktest_lv_ueberlauf.py (nur im Browser messbar, 1.8.133)
    3  /users nur für Administratoren, ohne den Satz zur Ersteinrichtung (1.8.134)
    4  Zurück-Links der Formularseiten mit echtem Ziel und Namen statt history.back() (1.8.135)
    5  LV-Editor: ein Weg zum Auftrag (1.8.136)
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
    ("/master-data/employees/1/edit", "/master-data#employees", "Stammdaten: Mitarbeiter"),
    ("/master-data/customers/new", "/master-data#customers", "Stammdaten: Kunden"),
    ("/master-data/resources/new", "/master-data#assets", "Stammdaten: Fuhrpark & Maschinen"),
    ("/master-data/assets/new", "/master-data#assets", "Stammdaten: Betriebsmittel"),
    ("/master-data/materials/new", "/master-data#materials", "Stammdaten: Materialkataloge"),
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
      const k = new Set(['hidden']);
      _element('orderOpenLink').classList = {{add: c => k.add(c), remove: c => k.delete(c), contains: c => k.has(c),
        toggle: (c, an) => (an ?? !k.has(c)) ? k.add(c) : k.delete(c)}};
      quote = {{quote_number: 'A-1', title: 'T', customer_name: 'K', project_number: 'P', property_name: null, status: 'beauftragt',
               vat_rate: '19', items: [], sections: [], document_meta: {{}}, project_id: 1, customer_id: 1}};
      existingOrder = {auftrag};
      renderQuoteEmailSection = () => {{}};  // Versand-Baustein (_email_dispatch.html) gehört nicht zur Attrappe
      renderAll();
      const link = _element('orderOpenLink'), knopf = _element('orderButton');
      return {{link: !link.classList.contains('hidden') ? link.textContent || 'Auftrag öffnen' : null, knopf: knopf.textContent}};""")
    e = lauf["ergebnis"]
    wege = [t for t in (e["link"], e["knopf"]) if t and t.endswith("öffnen")]
    if stand == "ohne Auftrag":
        assert wege == [] and e["knopf"] == "Angebot beauftragen"
    else:
        assert wege == ["Auftrag AUF-2026-0001 öffnen"], e
    if stand == "abgleichbar":
        assert e["knopf"] == "Änderungen in AUF-2026-0001 übernehmen"
