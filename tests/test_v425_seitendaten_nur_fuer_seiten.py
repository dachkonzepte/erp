"""Version 1.8.120 -- die Anmeldeschranke lädt die Seitendaten nur für Seiten, die gezeichnet werden (Korrektur 114-5 vom 16.10.2026).

Bis 1.8.119 lud sie Akzentfarbe, Module, Logo und Kontoknopf für jede GET-Anfrage außerhalb von /api/ (außer /health und
/manifest.json) -- auch für /docs, /openapi.json, eine unbekannte Adresse wie /static/app.css und eine Seitenroute, die nur umleitet
(/login für Angemeldete, / für Monteure). Jetzt nur für eine Seitenroute (GET, HTMLResponse), die für diesen Benutzer nicht umleitet
(app/seitendaten.py::wird_gezeichnet(), Umleitung an der Route: dk_ohne_seite).

Angriffstest: jede GET-Route der Seiten und jede Nicht-Seite, je Rolle (abgemeldet, Admin, Büro – Auftrag, Monteur): geladen genau
dann, wenn eine Vorlage gezeichnet wird (gezählt an jinja2.Template.render, auch die 403-Seite aus app/main.py), und die Jinja-Globals
laden nie selbst nach. Ausnahme: eine Seitenadresse mit ungültigen Werten (/orders/abc) lädt die Schranke nie -- als Admin endet sie mit 422
(JSON); als Monteur greift die Rollenprüfung vorher und zeichnet die 403-Seite, die ihre Daten dann einmal selbst lädt."""

from __future__ import annotations

import re
from decimal import Decimal

import jinja2
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app import seitendaten, sitzungen
from app.auth import COOKIE_NAME, hash_password
from app.main import _role_check_403_shows_access_denied_page
from app.customer_documents import customer_directory
from app.document_categories import resolve_category_id
from app.models import AppUser, Customer, CustomerDocument, Employee
from app.routers import customer_documents, field_view, pages
from tests.anmeldung import app_mit_schranke, browser_client, neue_datenbank

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
NICHT_SEITEN = ["/health", "/manifest.json", "/docs", "/openapi.json", "/redoc", "/static/app.css", "/favicon.ico",
                "/api/customer-documents/1/download", "/api/customer-documents/1/view", "/api/customer-documents/99/download",
                "/api/auth/status", "/gibt-es-nicht", "/projects/x/y", "/orders/1/work-preparation?x=1"]
UNGUELTIG = ["/orders/abc", "/master-data/customers/abc/edit", "/projects/1x"]
SONDER = {"/master-data/{data_type}/new": "/master-data/customers/new",
          "/master-data/{data_type}/{record_id}/edit": "/master-data/properties/1/edit"}


def _seiten() -> list[str]:
    return [SONDER.get(r.path) or re.sub(r"\{[^}]+\}", "1", r.path) for r in pages.router.routes
            if isinstance(r, APIRoute) and "GET" in r.methods and r.path != "/health"]


@pytest.fixture(scope="module")
def welt():
    engine, make_session = neue_datenbank()
    werte = {}
    with make_session() as db:
        mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich",
                       hourly_wage=Decimal("20"))
        kunde = Customer(name="Kunde", last_name="Kunde")
        db.add_all([mia, kunde])
        db.flush()
        (customer_directory(kunde.id) / "plan.pdf").write_bytes(PDF)
        dokument = CustomerDocument(customer_id=kunde.id, category="Sonstiges", category_id=resolve_category_id(db, "Sonstiges"),
                                    original_filename="plan.pdf", stored_filename="plan.pdf", content_type="application/pdf",
                                    file_size=len(PDF))
        db.add(dokument)
        db.flush()
        assert dokument.id == 1
        for rolle, extra in (("admin", {}), ("buero_auftrag", {}), ("field", {"employee_id": mia.id})):
            user = AppUser(username=rolle, display_name=rolle, role=rolle, active=True, password_hash=hash_password("Pw-12345678"), **extra)
            db.add(user)
            db.flush()
            werte[rolle] = sitzungen.neue_sitzung(db, user, zweiter_faktor=True)
        db.commit()
    app = app_mit_schranke(make_session, pages.router, field_view.router, customer_documents.router)
    app.add_exception_handler(HTTPException, _role_check_403_shows_access_denied_page)  # die 403-Seite wie app/main.py
    yield app, werte
    engine.dispose()


@pytest.fixture
def zaehler(monkeypatch):
    stand = {"schranke": 0, "nachgeladen": 0, "gezeichnet": 0}
    original_laden, original_eigene, original_render = seitendaten.laden, seitendaten.laden_mit_eigener_sitzung, jinja2.Template.render
    im_nachladen = [False]

    def laden(db, user):
        stand["schranke"] += not im_nachladen[0]  # laden_mit_eigener_sitzung() ruft laden() auf -- das ist nicht die Schranke
        return original_laden(db, user)

    def eigene(user):
        stand["nachgeladen"] += 1
        im_nachladen[0] = True
        try:
            return original_eigene(user)
        finally:
            im_nachladen[0] = False

    def render(self, *args, **kwargs):
        stand["gezeichnet"] += 1
        return original_render(self, *args, **kwargs)

    monkeypatch.setattr(seitendaten, "laden", laden)
    monkeypatch.setattr(seitendaten, "laden_mit_eigener_sitzung", eigene)
    monkeypatch.setattr(jinja2.Template, "render", render)
    return stand


@pytest.mark.parametrize("rolle", [None, "admin", "buero_auftrag", "field"])
def test_seitendaten_genau_fuer_gezeichnete_seiten(welt, zaehler, rolle):
    app, werte = welt
    client = browser_client(app, raise_server_exceptions=False)
    if rolle:
        client.cookies.set(COOKIE_NAME, werte[rolle], domain="testserver.local")
    falsch, gezeichnet = [], 0
    for pfad in _seiten() + NICHT_SEITEN + UNGUELTIG:
        zaehler.update(schranke=0, nachgeladen=0, gezeichnet=0)
        antwort = client.get(pfad, follow_redirects=False)
        soll = zaehler["gezeichnet"] > 0
        gezeichnet += soll
        # ungültiger Pfad: die Schranke lädt nichts, der erste Global der gezeichneten Seite lädt nach -- die Sperrseite (403) liest seit
        # 1.9.5 keine Seitendaten mehr (bis dahin die Akzentfarbe über get_theme()), dort lädt nichts nach
        erwartet = (0, int(soll and antwort.status_code != 403)) if pfad in UNGUELTIG else (int(soll), 0)
        if (zaehler["schranke"], zaehler["nachgeladen"]) != erwartet or (soll and not antwort.text.lstrip().lower().startswith("<!doctype html")):
            falsch.append((pfad, antwort.status_code, dict(zaehler)))
        if pfad in UNGUELTIG and rolle in ("admin", "buero_auftrag"):
            assert antwort.status_code == 422 and not soll, (pfad, antwort.status_code)
    assert not falsch, f"(Pfad, Status, Zähler): {falsch}"
    assert gezeichnet >= (1 if rolle is None else 5)


def test_die_datei_kommt_ohne_seitendaten(welt, zaehler):
    """Die Datei wird wirklich ausgeliefert (nicht nur 404/403) -- und die Schranke lädt dafür nichts."""
    app, werte = welt
    client = browser_client(app)
    client.cookies.set(COOKIE_NAME, werte["buero_auftrag"], domain="testserver.local")
    for pfad in ("/api/customer-documents/1/download", "/api/customer-documents/1/view"):
        zaehler.update(schranke=0, nachgeladen=0, gezeichnet=0)
        antwort = client.get(pfad)
        assert (antwort.status_code, antwort.content) == (200, PDF), pfad
        assert zaehler == {"schranke": 0, "nachgeladen": 0, "gezeichnet": 0}, pfad


def test_die_umleitungen_sind_dabei(welt, zaehler):
    """/login für Angemeldete und / für den Monteur leiten um -- ohne Seitendaten; dieselben Adressen zeichnen sonst eine Seite."""
    app, werte = welt
    for rolle, pfad, gezeichnet in (("admin", "/login", False), (None, "/login", True), ("field", "/", False), ("buero_auftrag", "/", True),
                                    ("field", "/orders/1/service-reports?report=1", False),  # seit 1.9.67 zum Bericht
                                    ("field", "/orders/1/service-reports", True)):
        client = browser_client(app)
        if rolle:
            client.cookies.set(COOKIE_NAME, werte[rolle], domain="testserver.local")
        zaehler.update(schranke=0, nachgeladen=0, gezeichnet=0)
        antwort = client.get(pfad, follow_redirects=False)
        assert (antwort.status_code == 302) is (not gezeichnet), (rolle, pfad, antwort.status_code)
        assert zaehler["schranke"] == int(gezeichnet), (rolle, pfad, zaehler)


def test_jede_umleitung_einer_seitenroute_steht_an_der_route():
    """Eine Seitenroute, die RedirectResponse zurückgibt, braucht dk_ohne_seite -- sonst lüde die Schranke umsonst."""
    quelle = (pages.__file__ and open(pages.__file__, encoding="utf-8").read())
    umleitend = {m.group(1) for m in re.finditer(r"\ndef (\w+)\([^)]*\):(?:(?!\ndef ).)*?return RedirectResponse", quelle, flags=re.S)
                 if m.group(1).endswith("_page")}
    mit_merkmal = {name for name in dir(pages) if callable(getattr(pages, name)) and hasattr(getattr(pages, name), "dk_ohne_seite")}
    # seit 1.9.59 dazu der Stundenzettel (immer) und /time-tracking (für die Monteurin) -- beide auf „Meine Zeiten“; seit 1.9.67 die
    # Auftragsseite mit ?report= (zum Bericht); seit 1.9.96 „Zeiten“ (für die Monteurin auf „Meine Zeiten“)
    # seit 1.9.98 das Backoffice (jede Rolle auf „Zeiten“ bzw. „Meine Zeiten“)
    assert umleitend == {"login_page", "dashboard_page", "field_timesheet_page", "time_tracking_page", "service_reports_page", "zeiten_page",
                         "time_backoffice_page"}
    assert umleitend <= mit_merkmal
