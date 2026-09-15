import logging
import os
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse

from .audit import reset_audit_context, set_audit_context
from .auth import otp_ok_for_user, user_from_request, users_exist, warn_if_secret_key_mismatches_file
from .permissions import default_home_page_for_role
from .catalogs import backfill_existing_services, ensure_import_catalog
from .database import DATABASE_URL, Base, SessionLocal, engine
from .logging_config import configure_logging
from .material_groups import backfill_existing_materials, ensure_import_material_group
from .materials import backfill_existing_service_materials
from .orders import ensure_existing_order_revisions
from .routers import (
    absence_requests, account, address_import, audit, auth, catalogs, changelog, customer_documents, customers,
    dashboard, document_email_templates, document_layout, email_settings, employees, field_view, findings, imports, inquiries, inspection_templates, invoices, labor_rate, maintenance_contracts, materials, modules, orders,
    pages, payment_terms, planning, project_documents, projects, properties, quick_service_orders, quotes, reminders,
    resource_planning, roof_areas, service_reports, services, settings, task_columns, tasks, tax_keys, time_backoffice, time_tracking, users,
    work_preparation,
)
from .version import APP_VERSION
from .work_time_models import ensure_default_work_time_models

configure_logging()
logger = logging.getLogger(__name__)
warn_if_secret_key_mismatches_file()

# Sicherheitsnetz nur fuer die lokale Entwicklung (siehe CLAUDE.md "Produktivbetrieb" --
# genau dieser Aufruf hat die Migration e057d15af828 einst zu einer leeren Huelle gemacht,
# weil er beim Start bereits alle Tabellen aus den ORM-Modellen anlegte, bevor Autogenerate
# lief). Auf dem Produktivserver (ERP_ENV=production) ist die Migrationskette
# (alembic upgrade head, siehe "Der Weg einer Aenderung auf den Server") die EINZIGE Quelle
# fuer das Schema -- eine fehlende Migration soll dort sofort sichtbar auffallen, nicht
# durch dieses Sicherheitsnetz kommentarlos verdeckt werden.
if os.getenv("ERP_ENV", "development") != "production":
    Base.metadata.create_all(bind=engine)
else:
    logger.info(
        "ERP_ENV=production -- Base.metadata.create_all() wird nicht ausgefuehrt, "
        "alembic upgrade head ist hier die alleinige Quelle fuer das Datenbankschema."
    )
with SessionLocal() as _upgrade_db:
    ensure_existing_order_revisions(_upgrade_db)
    ensure_default_work_time_models(_upgrade_db)
    _import_catalog = ensure_import_catalog(_upgrade_db)
    _backfilled = backfill_existing_services(_upgrade_db, _import_catalog)
    if _backfilled == -1:
        logger.warning(
            "Katalog-Migration noch nicht angewendet (services.catalog_id fehlt in der Datenbank) -- "
            "bitte 'alembic revision --autogenerate' + 'alembic upgrade head' ausführen. Bestehende "
            "Leistungen werden erst danach automatisch dem Fertigkatalog zugeordnet; bis dahin bleiben "
            "katalogbezogene Funktionen eingeschränkt, der übrige Betrieb ist nicht betroffen."
        )
    elif _backfilled:
        logger.info("Katalog-Migration: %s bestehende Leistung(en) dem Fertigkatalog zugeordnet.", _backfilled)
    _material_group = ensure_import_material_group(_upgrade_db)
    _materials_backfilled = backfill_existing_service_materials(_upgrade_db, _material_group.id)
    if _materials_backfilled == -1:
        logger.warning(
            "Materialkatalog-Migration noch nicht angewendet (service_materials.material_id fehlt in der "
            "Datenbank) -- bitte 'alembic revision --autogenerate' + 'alembic upgrade head' ausführen. "
            "Bestehende Materialien werden erst danach automatisch dem Materialkatalog zugeordnet."
        )
    elif _materials_backfilled:
        logger.info(
            "Materialkatalog-Migration: %s Material-Positionen dem Materialkatalog zugeordnet.",
            _materials_backfilled,
        )
    _material_groups_backfilled = backfill_existing_materials(_upgrade_db, _material_group)
    if _material_groups_backfilled == -1:
        logger.warning(
            "Materialkataloge-Migration noch nicht angewendet (materials.catalog_id fehlt in der Datenbank) -- "
            "bitte 'alembic revision --autogenerate' + 'alembic upgrade head' ausführen. Bestehende Materialien "
            "werden erst danach automatisch dem Fertigkatalog zugeordnet."
        )
    elif _material_groups_backfilled:
        logger.info(
            "Materialkataloge-Migration: %s bestehende(s) Material(ien) dem Fertigkatalog zugeordnet.",
            _material_groups_backfilled,
        )

app = FastAPI(title="DACHKONZEPTE ERP Prototype", version=APP_VERSION)

# Datenbank-Art fürs Log, bewusst OHNE die vollständige DATABASE_URL, da
# diese bei Postgres Zugangsdaten im Klartext enthalten kann.
_db_kind = "postgresql" if DATABASE_URL.startswith("postgres") else "sqlite" if DATABASE_URL.startswith("sqlite") else "sonstige"
logger.info("DACHKONZEPTE ERP startet, Version %s, Datenbank: %s", APP_VERSION, _db_kind)

# Seit 1.0.7 in app/routers/ aufgeteilt (siehe README, "main.py-Aufteilung").
# Jede Datei dort entspricht einer Fachdomäne und enthält ausschließlich die
# unveränderten, verschobenen Endpunkte dieser Domäne.
app.include_router(pages.router)
app.include_router(address_import.router)
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(projects.router)
app.include_router(project_documents.router)
app.include_router(customer_documents.router)
app.include_router(document_layout.router)
app.include_router(quotes.router)
app.include_router(orders.router)
app.include_router(work_preparation.router)
app.include_router(inquiries.router)
app.include_router(employees.router)
app.include_router(labor_rate.router)
app.include_router(settings.router)
app.include_router(resource_planning.router)
app.include_router(services.router)
app.include_router(properties.router)
app.include_router(planning.router)
app.include_router(time_tracking.router)
app.include_router(time_backoffice.router)
app.include_router(absence_requests.router)
app.include_router(audit.router)
app.include_router(imports.router)
app.include_router(catalogs.router)
app.include_router(materials.router)
app.include_router(invoices.router)
app.include_router(payment_terms.router)
app.include_router(tax_keys.router)
app.include_router(changelog.router)
app.include_router(reminders.router)
app.include_router(email_settings.router)
app.include_router(document_email_templates.router)
app.include_router(dashboard.router)
app.include_router(modules.router)
app.include_router(tasks.router)
app.include_router(task_columns.router)
app.include_router(maintenance_contracts.router)
app.include_router(service_reports.router)
app.include_router(quick_service_orders.router)
app.include_router(roof_areas.router)
app.include_router(inspection_templates.router)
app.include_router(findings.router)
app.include_router(field_view.router)


@app.exception_handler(HTTPException)
async def _role_check_403_shows_access_denied_page(request: Request, exc: HTTPException):
    """Seit "Rechtekonzept" (Seiten-Klassifizierung, siehe CLAUDE.md): ein 403 aus
    Depends(require_role(...))/require_admin() auf einer SEITEN-Route (nicht /api/) zeigt
    access_denied.html statt der für API-Clients gedachten JSON-Antwort -- dieselbe
    Standardverweigerung wie bei den API-Endpunkten, nur in einer für einen Browser lesbaren
    Antwort statt eines rohen {"detail": ...}. Jeder andere Statuscode und jeder /api/-Pfad
    verhält sich unverändert wie FastAPIs eigener Standard-Handler, an den hier bewusst
    delegiert wird (keine Kopie, kein zweiter Ort mit eigener Fehlerbehandlung).

    user is None kann diesen Zweig nur während des Bootstrap-Falls erreichen (kein ERP-Benutzer
    existiert -- _page_requires_login() redirectet sonst schon vorher auf /login, siehe dort):
    "Zur Startseite" zeigt dann auf /users, die einzige in diesem Zustand erreichbare Seite,
    statt auf das (für einen anonymen Aufruf ebenfalls gesperrte) Dashboard."""
    if exc.status_code == 403 and not request.url.path.startswith("/api/"):
        user = getattr(request.state, "erp_user", None)
        home_url = "/users" if user is None else default_home_page_for_role(user.role)
        return pages.templates.TemplateResponse(
            request=request, name="access_denied.html",
            context={"message": exc.detail if isinstance(exc.detail, str) else None, "home_url": home_url},
            status_code=403,
        )
    return await http_exception_handler(request, exc)


def _request_requires_login(has_users: bool, method: str, path: str) -> bool:
    """Ermittelt, ob für diese Anfrage ein angemeldeter ERP-Benutzer nötig ist.

    Greift erst, sobald mindestens ein ERP-Benutzer existiert (der Bootstrap-Fall
    zum Anlegen des allerersten Admin-Kontos bleibt ausgenommen). Die Login-
    Endpunkte selbst (/api/auth/...) bleiben immer erreichbar. Schreibende
    Zugriffe waren bereits zuvor geschützt; seit 1.0.6 zusätzlich lesende API-
    Zugriffe (GET /api/...), da darüber z. B. Mitarbeiterlöhne
    (EmployeeOut.effective_hourly_wage / .annual_gross_wage) und
    Kalkulationsgrundlagen ohne Anmeldung auslesbar waren.
    """
    if not has_users or path.startswith("/api/auth/"):
        return False
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return True
    return method == "GET" and path.startswith("/api/")


# Bleiben ohne Anmeldung erreichbar, obwohl sie keine /api/-Endpunkte sind: /login naturgemäß
# (sonst könnte sich niemand anmelden), /health für externe Überwachung (bereits zuvor
# ungated), /manifest.json als reine PWA-Ressource der Monteursansicht (wird ohnehin nur von
# der bereits angemeldeten Seite /vor-ort aus verlinkt, siehe app/routers/field_view.py).
_PUBLIC_PAGE_PATHS = {"/login", "/health", "/manifest.json"}


def _page_requires_login(has_users: bool, method: str, path: str) -> bool:
    """Seit 1.3.47: ohne Anmeldung führte jede Seite bisher zu einem stillen Rendern des
    Seiten-Gerüsts (kein Redirect, kein Fehler) -- ob überhaupt etwas nutzbar ist, entschied
    rein die clientseitige JS jeder Seite. Diese Funktion entscheidet stattdessen serverseitig,
    ob eine HTML-Seitenanfrage ohne angemeldeten Benutzer auf /login umgeleitet wird.

    Bewusst getrennt von _request_requires_login() oben, nicht darin verschmolzen: eine
    /api/-Anfrage soll bei fehlender Anmeldung weiterhin die dortige 401-JSON-Antwort bekommen,
    nie einen Redirect auf eine HTML-Seite -- ein API-Client würde eine Login-Seite als Antwort
    nicht sinnvoll verarbeiten können. Bewusst nur GET: Seiten kennen ohnehin kein POST/PUT/....
    """
    if not has_users or method != "GET" or path.startswith("/api/"):
        return False
    return path not in _PUBLIC_PAGE_PATHS


# Diese Endpunkte bleiben für einen Administrator erreichbar, dessen Sitzung das Passwort
# bereits bestätigt hat, aber noch keinen zweiten Faktor -- alles andere unter /api/ ist
# solange blockiert (seit 1.3.34, siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für
# Administratoren"). /api/auth/* ist bereits über _request_requires_login() immer erreichbar,
# taucht hier nicht zusätzlich auf.
_TWO_FACTOR_SETUP_PATHS = {
    "/api/account/2fa/setup/start",
    "/api/account/2fa/setup/confirm",
    "/api/account/2fa/verify",
}


def _blocked_pending_two_factor(path: str) -> bool:
    if not path.startswith("/api/") or path.startswith("/api/auth/"):
        return False
    return path not in _TWO_FACTOR_SETUP_PATHS


@app.middleware("http")
async def identity_and_audit_middleware(request: Request, call_next):
    db = SessionLocal()
    user = None
    has_users = False
    try:
        has_users = users_exist(db)
        user = user_from_request(db, request)
    finally:
        db.close()
    tokens = set_audit_context(user=user, request=request)
    request.state.erp_user = user
    otp_ok = True
    if user is not None and user.role == "admin":
        otp_ok = otp_ok_for_user(request, user.id)
    request.state.otp_ok = otp_ok
    try:
        # Sobald ERP-Benutzer eingerichtet sind, sind schreibende Vorgänge und lesende
        # API-Zugriffe nur angemeldet erlaubt (siehe _request_requires_login).
        if user is None and _request_requires_login(has_users, request.method, request.url.path):
            return JSONResponse(status_code=401, content={"detail":"Bitte zuerst als ERP-Benutzer anmelden."})
        if user is None and _page_requires_login(has_users, request.method, request.url.path):
            # Dieselbe ?next=<Pfad>-Konvention wie bei den bestehenden Abmelden-Links
            # (_sidebar.html/_topbar.html/_mobile_header.html/vor_ort.html: location.href=
            # '/login?next='+encodeURIComponent(location.pathname)) -- login.html liest und
            # honoriert next bereits (siehe dort), nur der Query-String selbst wird bewusst
            # nicht mitgegeben, exakt wie bei jenen Links.
            next_target = quote(request.url.path, safe="")
            return RedirectResponse(url=f"/login?next={next_target}", status_code=302)
        if user is not None and not otp_ok and _blocked_pending_two_factor(request.url.path):
            return JSONResponse(status_code=401, content={"detail": "Zwei-Faktor-Bestätigung ausstehend.", "two_factor_pending": True})
        try:
            return await call_next(request)
        except Exception:
            # Nur protokollieren, nicht abfangen: dieselbe Exception wird
            # unverändert weitergereicht, sodass sich am Antwortverhalten
            # nichts ändert -- neu ist ausschließlich der Log-Eintrag mit
            # vollständigem Traceback (seit 1.0.8 dauerhaft in data/erp.log
            # statt nur in der Konsole).
            logger.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
            raise
    finally:
        reset_audit_context(tokens)


# Re-Exports für Rückwärtskompatibilität (u. a. von der bestehenden Testsuite
# genutzt, die diese Namen historisch direkt aus app.main importiert).
from .routers.customers import create_customer, create_customer_extra_info, delete_customer_extra_info, list_customers, update_customer, update_customer_extra_info
from .routers.employees import get_employee, update_employee
from .routers.inquiries import convert_inquiry, create_inquiry, update_inquiry
from .routers.project_documents import delete_project_document, update_project_document
from .routers.projects import create_project, create_quote, get_project_detail, list_project_documents, update_project, upload_project_document
from .routers.properties import create_property, update_property
from .routers.quotes import add_free_item_api, add_quote_item, add_quote_section_api, auto_number_quote_api, get_quote_item_calculation, update_item_layout_api, update_quote_document_meta, update_quote_item, update_quote_item_calculation
from .routers.resource_planning import create_resource, create_supplier, create_team
from .routers.users import delete_app_user, update_app_user
from .routers.work_preparation import assign_work_preparation_team, bulk_assign_work_preparation_materials, remove_work_preparation_team, unlink_material_delivery_note, update_work_preparation_material
