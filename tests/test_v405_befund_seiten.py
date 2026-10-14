"""Version 1.8.100 -- Befund Sicherheit der Seiten (Vorgabe vom 14.10.2026, Punkt 4: nur Befund, Fehler als xfail(strict=True)).

Drei Fragen: Cookie-Flags, Schutz schreibender Anfragen gegen fremde Seiten, und wo Daten ungeschützt in die Seite gelangen (innerHTML,
|safe) -- besonders Daten von außen (Outlook-Termine, Adressimport, Altkunden). Jede gefundene Lücke steht hier als Test mit
xfail(strict=True): er beschreibt das gewünschte Verhalten und ist heute rot; wird die Lücke geschlossen, wird er grün und xfail schlägt an
(dann den Marker entfernen). Was geprüft und in Ordnung ist, steht als gewöhnlicher Test daneben. Herleitung, auch der geprüften und sicheren
Stellen: docs/archiv/befund-vor-echtbetrieb.md, "Befund 1.8.100".

Nichts davon ändert den Code (Vorgabe: nur Befund)."""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import APIRouter

from app import sitzungen
from app.auth import COOKIE_NAME, hash_password
from app.models import AppUser, Customer, DocumentCategory, Project, Property
from app.routers import account as account_router
from app.routers import auth as auth_router
from app.routers import customer_documents as customer_documents_router
from app.routers import customers as customers_router
from app.routers import pages as pages_router
from app.routers import project_documents as project_documents_router
from app.routers import projects as projects_router
from app.routers import property_documents as property_documents_router
from tests.anmeldung import client_mit_schranke, neue_datenbank
from tests.pg_schutz import pg_url_pruefen
from tests.test_v314_dashboard_month_berlin import NODE, _node
from tests.test_v334_auswahl_restfaelle import FAKE_DOM, im_browser, seite

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")
SKRIPT = '<img src=x onerror="window.__dkXss=1">'


# ---------------------------------------------------------------------------
# 1. Cookie-Flags
# ---------------------------------------------------------------------------

def _set_cookies(antwort) -> dict:
    out = {}
    for zeile in antwort.headers.get_list("set-cookie"):
        name, _, rest = zeile.partition("=")
        out[name] = [teil.strip().lower() for teil in rest.split(";")[1:]]
    return out


@pytest.fixture
def anmeldung():
    engine, make_session = neue_datenbank()
    with make_session() as db:
        db.add(AppUser(username="bea", display_name="Bea", role="buero_auftrag", active=True, password_hash=hash_password("Passwort-123")))
        db.commit()
    probe = APIRouter()

    @probe.post("/api/probe/ohne-body")
    def _ohne_body():
        return {"ok": True}

    client = client_mit_schranke(make_session, auth_router.router, account_router.router, pages_router.router, probe,
                                 customers_router.router)
    yield client, make_session
    engine.dispose()


def test_das_anmelde_cookie_ist_httponly_und_samesite_lax(anmeldung):
    client, _ = anmeldung
    flags = _set_cookies(client.post("/api/auth/login", json={"username": "bea", "password": "Passwort-123"}))[COOKIE_NAME]
    assert "httponly" in flags and "samesite=lax" in flags and "path=/" in flags
    assert "max-age=43200" in flags  # 12 h, wie die Sitzung auf dem Server


@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 1: Secure kommt nur über ERP_COOKIE_SECURE=1 (Vorgabe aus), auch mit "
                                       "ERP_ENV=production -- fehlt der Eintrag in .env, geht das Anmelde-Cookie auch über http.")
def test_in_produktion_ist_das_anmelde_cookie_auch_ohne_eintrag_secure():
    env = {k: v for k, v in os.environ.items() if k != "ERP_COOKIE_SECURE"}
    env.update({"ERP_ENV": "production", "DATABASE_URL": pg_url_pruefen("sqlite://"), "PYTHONIOENCODING": "utf-8"})
    r = subprocess.run([sys.executable, "-c", "import app.auth as a; print(a.COOKIE_SECURE)"], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "True"


# ---------------------------------------------------------------------------
# 2. Schreibende Anfragen von fremden Seiten
# ---------------------------------------------------------------------------

def _angemeldet(client, make_session) -> None:
    with make_session() as db:
        user = db.query(AppUser).filter_by(username="bea").one()
        wert = sitzungen.neue_sitzung(db, user)
        db.commit()
    client.cookies.set(COOKIE_NAME, wert, domain="testserver.local")


def test_json_endpunkte_nehmen_kein_json_ohne_passenden_content_type(anmeldung):
    """Geprüft, in Ordnung: eine fremde Seite kann ohne Vorabanfrage (CORS) nur "einfache" Anfragen schicken (Formular, text/plain, ohne
    Content-Type). FastAPI liest einen JSON-Body nur mit application/json (strict_content_type) -- ein JSON-Endpunkt bleibt so außer
    Reichweite."""
    client, make_session = anmeldung
    _angemeldet(client, make_session)
    body = json.dumps({"current_password": "Passwort-123", "new_password": "Neues-Passwort-1"})
    for kopf in ({"content-type": "text/plain"}, {}, {"content-type": "application/x-www-form-urlencoded"}):
        assert client.post("/api/account/change-password", content=body.encode(), headers=kopf).status_code == 422, kopf
    assert client.get("/api/auth/status").json()["authenticated"] is True


FREMD = {"origin": "https://www.dachkonzepte.gmbh", "sec-fetch-site": "same-site", "referer": "https://www.dachkonzepte.gmbh/"}


@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 2: kein Abgleich von Origin/Sec-Fetch-Site und kein Token -- eine Seite "
                                       "derselben Site (z. B. www.dachkonzepte.gmbh) schickt schreibende Anfragen ohne Body oder als "
                                       "Formular/Upload mit dem Anmelde-Cookie (SameSite=Lax schützt nur gegen fremde Sites).")
@pytest.mark.parametrize("art", ["ohne Body", "Formular-Upload"])
def test_schreibende_anfrage_von_einem_anderen_ursprung_wird_abgelehnt(anmeldung, art):
    client, make_session = anmeldung
    _angemeldet(client, make_session)
    with make_session() as db:
        kunde = Customer(name="Kunde", last_name="Kunde")
        db.add(kunde); db.commit()
        kid = kunde.id
    if art == "ohne Body":
        antwort = client.post("/api/probe/ohne-body", headers=FREMD)
    else:
        antwort = client.post(f"/api/customers/{kid}/documents", headers=FREMD, files={"file": ("a.txt", b"x", "text/plain")})
    assert antwort.status_code == 403, antwort.status_code


@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 3: weder X-Frame-Options noch Content-Security-Policy frame-ancestors -- "
                                       "eine Seite derselben Site kann das ERP angemeldet einrahmen und Klicks unterschieben.")
def test_seiten_lassen_sich_nicht_fremd_einrahmen(anmeldung):
    client, make_session = anmeldung
    _angemeldet(client, make_session)
    antwort = client.get("/account")
    assert antwort.status_code == 200
    csp = antwort.headers.get("content-security-policy", "")
    assert antwort.headers.get("x-frame-options", "").upper() in ("DENY", "SAMEORIGIN") or "frame-ancestors" in csp


# ---------------------------------------------------------------------------
# 3. Daten ungeschützt in der Seite
# ---------------------------------------------------------------------------

def test_keine_vorlage_und_kein_modul_schaltet_das_escaping_aus():
    """Geprüft, in Ordnung: Jinja escapt alle .html-Vorlagen (select_autoescape), nirgends |safe, Markup( oder autoescape false."""
    assert pages_router.templates.env.autoescape("x.html") is True
    funde = []
    for pfad in [*TEMPLATES.glob("*.html"), *(ROOT / "app").rglob("*.py")]:
        text = pfad.read_text(encoding="utf-8")
        for muster in (r"\|\s*safe\b", r"\bMarkup\(", r"autoescape\s+false"):
            if re.search(muster, text):
                funde.append(f"{pfad.relative_to(ROOT)}: {muster}")
    assert funde == []


# --- 3a. hochgeladene Dateien als aktiver Inhalt ------------------------------------------------------------------------

SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.domain)</script></svg>'
HTML_DATEI = b"<html><body><script>alert(document.domain)</script></body></html>"


def _aktiv_inline(antwort) -> bool:
    """Liefert der Server die Datei so, dass der Browser ein Skript darin auf dem ERP-Ursprung ausführt? (inline, SVG/HTML, ohne
    CSP sandbox)."""
    art = antwort.headers.get("content-type", "").split(";")[0].strip().lower()
    inline = antwort.headers.get("content-disposition", "").lower().startswith("inline")
    sandbox = "sandbox" in antwort.headers.get("content-security-policy", "")
    return inline and art in ("image/svg+xml", "text/html", "application/xhtml+xml", "text/xml") and not sandbox


@pytest.fixture
def ablage(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde = Customer(name="Kunde", last_name="Kunde")
    db.add(kunde); db.flush()
    from app.project_pipeline_columns import default_pipeline_column_id
    projekt = Project(project_number="P-1", name="Dach", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    objekt = Property(customer_id=kunde.id, name="Halle")
    db.add_all([projekt, objekt]); db.commit()
    client = router_test_client(db, customers_router.router, customer_documents_router.router, projects_router.router,
                                project_documents_router.router, property_documents_router.router)
    return {"db": db, "client": client, "kunde": kunde.id, "projekt": projekt.id, "objekt": objekt.id}


_AKTIV = "Befund 1.8.100 Nr. 4: hochgeladene Dateien gehen inline mit dem Typ, den der Browser beim Hochladen nannte -- eine SVG- oder " \
         "HTML-Datei mit Skript läuft beim Öffnen auf dem ERP-Ursprung (mit der Sitzung der Person, die öffnet); kein nosniff, keine CSP."


@pytest.mark.xfail(strict=True, reason=_AKTIV)
def test_svg_in_der_kundenakte_laeuft_nicht_als_skript(ablage):
    c = ablage["client"]
    doc = c.post(f"/api/customers/{ablage['kunde']}/documents", files={"file": ("bild.svg", SVG, "image/svg+xml")}).json()
    assert not _aktiv_inline(c.get(f"/api/customer-documents/{doc['id']}/view"))


@pytest.mark.xfail(strict=True, reason=_AKTIV)
def test_svg_in_der_projektmappe_laeuft_nicht_als_skript(ablage):
    c = ablage["client"]
    doc = c.post(f"/api/projects/{ablage['projekt']}/documents", files={"file": ("bild.svg", SVG, "image/svg+xml")}).json()
    assert not _aktiv_inline(c.get(f"/api/project-documents/{doc['id']}/view"))


@pytest.mark.xfail(strict=True, reason=_AKTIV + " Am Objekt werden Bilder neu kodiert (SVG scheitert dort), HTML bleibt.")
def test_html_am_objekt_laeuft_nicht_als_skript(ablage):
    db, c = ablage["db"], ablage["client"]
    kategorie = db.query(DocumentCategory).first()
    doc = c.post(f"/api/properties/{ablage['objekt']}/documents", data={"category_id": str(kategorie.id)},
                 files={"file": ("plan.html", HTML_DATEI, "text/html")}).json()
    assert not _aktiv_inline(c.get(f"/api/property-documents/{doc['id']}/view"))


# --- 3b. innerHTML ohne Schutz ---------------------------------------------------------------------------------------

def _esc_js(vorlage: str) -> str:
    """Die esc()-Funktion der Vorlage, wörtlich (bis "}[c]));" -- in ihrem Text stehen selbst Semikolons)."""
    text = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    start = text.index("const esc=s=>")
    return text[start:text.index("}[c]));", start) + len("}[c]));")]


def _funktion(vorlage: str, name: str) -> str:
    """Die Funktion name aus dem Skript der Vorlage, über den Tokenizer (Template-Literale mit ${…} und Klammern darin)."""
    from tests.vorlagen_js import analysieren, eigene_skripte
    quelle = eigene_skripte(vorlage)
    a = analysieren(quelle)
    start, ende = a.funktionen[name][0]
    kopf = quelle.text.rfind("function " + name, 0, a.t[start].pos)
    return quelle.text[kopf:a.t[ende].pos + 1]


@nur_mit_node
@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 5: Gruppenname eines Prüfpunkts geht nur für JS geschützt (\\') in das "
                                       "onclick-Attribut -- ein \" beendet das Attribut, ein <img onerror> läuft beim Zeichnen des "
                                       "Einsatzberichts. Setzen kann ihn jede Rolle, die den Bericht bearbeitet (auch der Monteur).")
def test_gruppenname_im_einsatzbericht_bleibt_text():
    funktion = _funktion("service_reports.html", "inspectionItemsPanelHtml")
    js = (_esc_js("service_reports.html") + "\n" + funktion + f"""
const inspectionItemsCache={{1:[{{id:5,text:'Rinne',group_name:{json.dumps('x"' + '>' + SKRIPT)},required:false}}]}};
const inspectionSyncHints={{}}, expandedAreaKeys=new Set(['1:none']), closedGroupKeys=new Set();
function isItemAnswered(){{return false}} function inspectionItemRowHtml(){{return ''}}
process.stdout.write(JSON.stringify(inspectionItemsPanelHtml({{id:1,roof_areas:[],status:'entwurf'}})));""")
    gezeichnet = _node(js, "Europe/Berlin")
    assert "<img" not in gezeichnet


@nur_mit_node
@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 6: \"Neues Projekt\" setzt Kundennamen und Objekte ohne Schutz in die "
                                       "Auswahl (innerHTML) -- ein importierter Altkunde oder ein Name aus dem Adressimport mit <img onerror> "
                                       "läuft beim Öffnen der Seite.")
def test_kundenname_im_formular_neues_projekt_bleibt_text():
    antworten = {"/api/settings/option-groups": [], "/api/customers": [{"id": 1, "customer_number": "K-1", "name": SKRIPT}],
                 "/api/settings/option-groups/project_categories": {"options": []},
                 "/api/properties?customer_id=1": [{"id": 2, "name": SKRIPT, "postal_code": "1", "city": "Stadt"}]}
    lauf = im_browser(seite("project_form.html", "\nload()"), "await load(); return [_element('customer').innerHTML, "
                      "_element('property').innerHTML];", antworten)
    assert all("<img" not in feld for feld in lauf["ergebnis"])


@nur_mit_node
@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 6: \"Neues Angebot\" setzt Projektnummer, Kunde und Projektname ohne Schutz "
                                       "in die Auswahl (innerHTML).")
def test_kundenname_im_formular_neues_angebot_bleibt_text():
    antworten = {"/api/projects": [{"id": 1, "project_number": "P-1", "customer_name": SKRIPT, "name": "Dach"}],
                 "/api/settings/general": {"default_vat_rate": 19}}
    lauf = im_browser(seite("quote_form.html", "load()"), "await load(); return _element('project').innerHTML;", antworten)
    assert "<img" not in lauf["ergebnis"]


@nur_mit_node
@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 7: Verknüpfungssuche im Kalender -- JSON.stringify im onclick-Attribut, "
                                       "nur ' als &#39; geschützt; der Browser dekodiert &quot; im Attribut zu \", ein Projekt- oder "
                                       "Angebotstitel mit &quot; beendet die Zeichenkette (Skript beim Klick auf den Vorschlag).")
def test_vorschlag_der_verknuepfungssuche_bleibt_daten():
    vorlage = (TEMPLATES / "calendar.html").read_text(encoding="utf-8")
    ausdruck = re.search(r"box\.innerHTML=(hits\.map\(h=>`<div class=\"suggest-item\".*?`\)\.join\(''\));", vorlage).group(1)
    titel = '&quot;});window.__dkXss=1;//'
    js = (_esc_js("calendar.html") + f"\nconst hits=[{{type:'project',id:1,label:{json.dumps(titel)}}}];"
          f"\nprocess.stdout.write(JSON.stringify({ausdruck}));")
    gezeichnet = _node(js, "Europe/Berlin")
    attribut = html.unescape(re.search(r"onclick='([^']*)'", gezeichnet).group(1))  # so sieht der Browser den Code
    assert attribut == "pickLink(" + json.dumps({"type": "project", "id": 1, "label": titel}, separators=(",", ":")) + ")"


@nur_mit_node
@pytest.mark.xfail(strict=True, reason="Befund 1.8.100 Nr. 8: Planungsvorschlag der Plantafel setzt Namen abwesender Mitarbeiter und "
                                       "Feiertage ohne Schutz in den Hinweis (innerHTML).")
def test_namen_im_planungsvorschlag_bleiben_text():
    vorspann = FAKE_DOM.replace("const antwort = methode === 'GET' ? ANTWORTEN[url] : {};", "const antwort = ANTWORTEN[url];")
    berlin = re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_berlin_date.html").read_text(encoding="utf-8"), flags=re.S)[0]
    skript = vorspann + berlin + seite("planning.html", "\nloadBoard();")[len(FAKE_DOM):]
    vorschlag = {"suggested_end": "2026-10-20", "planned_hours": 8, "required_team_days_decimal": 1, "calendar_workdays_needed": 1,
                 "employee_count": 1, "daily_work_hours": 8, "travel_hours_per_employee_day": 0, "full_team_daily_capacity": 8,
                 "suggested_start": "2026-10-19", "days": [{"date": "2026-10-19", "holiday": None,
                                                            "absent_employees": [{"name": SKRIPT, "type": "Urlaub"}]}]}
    lauf = im_browser(skript, "board={settings:{daily_work_hours:8}}; await calculateSuggestion(); "
                      "return _element('suggestionBox').innerHTML;", {"/api/planning/suggestion": vorschlag})
    assert "<img" not in lauf["ergebnis"]
