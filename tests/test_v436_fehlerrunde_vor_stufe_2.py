"""Fehlerrunde vor Stufe 2 des Redesigns (1.8.132 ff., Vorgabe vom 19.10.2026): je Punkt ein Test, der vor der Behebung scheiterte.

    1  Anfragen: „Projekt öffnen“ führt direkt in die Projektmappe, „Projekt + Angebot erzeugen“ direkt ins neue Angebot (1.8.132)
    2  LV-Editor und Auftrag ohne Überlauf: Klicktest scripts/klicktest_lv_ueberlauf.py (nur im Browser messbar, 1.8.133)
    3  /users nur für Administratoren, ohne den Satz zur Ersteinrichtung (1.8.134)
"""

import json

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
