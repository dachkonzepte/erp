"""Router: pages

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 22 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from pathlib import Path
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..company_logo import sidebar_logo_filename
from ..database import SessionLocal, get_db
from ..deps import require_admin
from ..modules import is_module_enabled
from ..settings import get_accent_color
from ..version import APP_VERSION

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.globals["app_version"] = APP_VERSION


def _current_theme() -> dict:
    """Jinja-Global (Aufruf als Funktion, kein statischer Wert): liest die
    Akzentfarbe live aus general_settings, damit Änderungen ohne Neustart
    des Servers auf der nächsten Seitenanfrage sichtbar werden."""
    with SessionLocal() as db:
        return {"accent_color": get_accent_color(db)}


templates.env.globals["get_theme"] = _current_theme


def _is_module_enabled(module_key: str) -> bool:
    """Jinja-Global (seit 1.0.103): liest den Modul-Zustand live aus der DB, damit ein
    Admin ein Modul in den Einstellungen umschalten kann, ohne den Server neu zu
    starten. Verwendung z. B. in _sidebar.html: {% if is_module_enabled('aufgabenmanagement') %}."""
    with SessionLocal() as db:
        return is_module_enabled(db, module_key)


templates.env.globals["is_module_enabled"] = _is_module_enabled


def _sidebar_logo_url() -> str | None:
    """Jinja-Global: liefert die URL des Logos, das _sidebar.html oben links statt des
    Schriftzugs "DACHKONZEPTE" zeigen soll, oder None, wenn keins hinterlegt ist (Fallback
    dann der Schriftzug -- eine leere Stelle wäre schlechter als Text). Die eigentliche
    "welches Logo"-Entscheidung liegt bewusst in company_logo.py::sidebar_logo_filename(),
    nicht hier -- dieser Global bleibt ein reiner URL-Baukasten (Muster get_theme()/
    is_module_enabled() oben: live aus der DB, eigene, kurzlebige Session je Aufruf, damit ein
    Logo-Wechsel ohne Serverneustart auf der nächsten Seitenanfrage sichtbar wird). Der
    Query-Parameter ?v=<stored_filename> bricht das Browser-Bild-Caching gezielt auf, sobald
    ein Logo ersetzt wird -- stored_filename ist ein neuer, zufälliger Name je Upload."""
    with SessionLocal() as db:
        filename = sidebar_logo_filename(db)
    if not filename:
        return None
    return f"/api/settings/general/logo?v={filename}"


templates.env.globals["sidebar_logo_url"] = _sidebar_logo_url


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    return templates.TemplateResponse(request=request, name="account.html", context={})


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    return templates.TemplateResponse(request=request, name="users.html", context={})


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    return templates.TemplateResponse(request=request, name="history.html", context={})


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={})


@router.get("/leistungskatalog", response_class=HTMLResponse)
def service_catalog_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    return templates.TemplateResponse(request=request, name="tasks.html", context={})


@router.get("/vor-ort", response_class=HTMLResponse)
def field_view_page(request: Request):
    """Monteursansicht (seit 1.3.0) -- eigene, schlanke Seite statt der vollen Sidebar (siehe
    _mobile_header.html). Rendert nur das statische Gerüst (Projektkonvention, siehe
    test_v218_template_rendering.py) -- die Feierabend-Prüfung sitzt bewusst NUR in GET
    /api/field-view/today (einzige Quelle der Wahrheit statt zweier Prüfstellen), dessen 401
    das Frontend (vor_ort.html) zu /login weiterleitet. Ein serverseitiger Redirect hier hätte
    denselben Effekt gehabt, wäre aber zusätzlich wanduhrzeit-abhängig und damit gegen den
    generischen Seiten-Rendertest geflackert."""
    return templates.TemplateResponse(request=request, name="vor_ort.html", context={})


@router.get("/maintenance-contracts", response_class=HTMLResponse)
def maintenance_contracts_page(request: Request):
    return templates.TemplateResponse(request=request, name="maintenance_contracts.html", context={})


@router.get("/maintenance-contracts/{contract_id}", response_class=HTMLResponse)
def maintenance_contract_page(request: Request, contract_id: int):
    return templates.TemplateResponse(
        request=request, name="maintenance_contract.html", context={"contract_id": contract_id}
    )


@router.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    return templates.TemplateResponse(request=request, name="projects.html", context={})


@router.get("/planning", response_class=HTMLResponse)
def planning_page(request: Request):
    return templates.TemplateResponse(request=request, name="planning.html", context={})


@router.get("/time-tracking", response_class=HTMLResponse)
def time_tracking_page(request: Request):
    return templates.TemplateResponse(request=request, name="time_tracking.html", context={})


@router.get("/time-backoffice", response_class=HTMLResponse)
def time_backoffice_page(request: Request, db: Session = Depends(get_db), _admin=Depends(require_admin("Das Zeiterfassungs-Backoffice ist nur für Administratoren verfügbar."))):
    return templates.TemplateResponse(request=request, name="time_backoffice.html", context={})


@router.get("/projects/new", response_class=HTMLResponse)
def project_create_page(request: Request):
    return templates.TemplateResponse(request=request, name="project_form.html", context={})


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_folder_page(request: Request, project_id: int):
    return templates.TemplateResponse(request=request, name="project_folder.html", context={"project_id": project_id})


@router.get("/quotes/new", response_class=HTMLResponse)
def quote_create_page(request: Request):
    return templates.TemplateResponse(request=request, name="quote_form.html", context={})


@router.get("/services/new", response_class=HTMLResponse)
def service_create_page(request: Request):
    return templates.TemplateResponse(request=request, name="service_form.html", context={"service_id": None})


@router.get("/services/{service_id}/edit", response_class=HTMLResponse)
def service_edit_page(request: Request, service_id: int):
    return templates.TemplateResponse(request=request, name="service_form.html", context={"service_id": service_id})


@router.get("/master-data", response_class=HTMLResponse)
def master_data_page(request: Request):
    return templates.TemplateResponse(request=request, name="master_data.html", context={})


@router.get("/master-data/{data_type}/new", response_class=HTMLResponse)
def master_data_create_page(request: Request, data_type: str):
    if data_type not in {"customers", "properties", "employees", "suppliers", "resources", "teams", "catalogs", "materials", "materialGroups"}:
        raise HTTPException(status_code=404, detail="Stammdatenbereich nicht gefunden.")
    return templates.TemplateResponse(request=request, name="master_data_form.html", context={"data_type": data_type})


@router.get("/master-data/{data_type}/{record_id}/edit", response_class=HTMLResponse)
def master_data_edit_page(request: Request, data_type: str, record_id: int):
    if data_type not in {"properties", "employees", "suppliers", "resources", "teams", "materials"}:
        raise HTTPException(status_code=404, detail="Stammdatenbereich nicht gefunden.")
    return templates.TemplateResponse(
        request=request, name="master_data_form.html",
        context={"data_type": data_type, "record_id": record_id},
    )


@router.get("/quotes/{quote_id}/edit", response_class=HTMLResponse)
def quote_editor_page(request: Request, quote_id: int):
    return templates.TemplateResponse(request=request, name="quote_editor.html", context={"quote_id": quote_id})


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_page(request: Request, order_id: int):
    return templates.TemplateResponse(request=request, name="order.html", context={"order_id": order_id})


@router.get("/invoices/{invoice_id}", response_class=HTMLResponse)
def invoice_page(request: Request, invoice_id: int):
    return templates.TemplateResponse(request=request, name="invoice_detail.html", context={"invoice_id": invoice_id})


@router.get("/finanzen", response_class=HTMLResponse)
def finanzen_page(request: Request):
    return templates.TemplateResponse(request=request, name="finanzen.html", context={})


@router.get("/mahnwesen", response_class=HTMLResponse)
def mahnwesen_page(request: Request):
    return templates.TemplateResponse(request=request, name="mahnwesen.html", context={})


@router.get("/changelog", response_class=HTMLResponse)
def changelog_page(request: Request):
    return templates.TemplateResponse(request=request, name="changelog.html", context={})


@router.get("/orders/{order_id}/work-preparation", response_class=HTMLResponse)
def work_preparation_page(request: Request, order_id: int):
    return templates.TemplateResponse(request=request, name="work_preparation.html", context={"order_id": order_id})


@router.get("/orders/{order_id}/service-reports", response_class=HTMLResponse)
def service_reports_page(request: Request, order_id: int):
    return templates.TemplateResponse(request=request, name="service_reports.html", context={"order_id": order_id})


@router.get("/roof-areas/{roof_area_id}", response_class=HTMLResponse)
def roof_area_page(request: Request, roof_area_id: int):
    return templates.TemplateResponse(request=request, name="roof_area.html", context={"roof_area_id": roof_area_id})


@router.get("/properties/{property_id}", response_class=HTMLResponse)
def property_page(request: Request, property_id: int):
    return templates.TemplateResponse(request=request, name="property.html", context={"property_id": property_id})


@router.get("/findings", response_class=HTMLResponse)
def findings_page(request: Request):
    return templates.TemplateResponse(request=request, name="findings.html", context={})


@router.get("/inspection-templates", response_class=HTMLResponse)
def inspection_templates_page(request: Request):
    return templates.TemplateResponse(request=request, name="inspection_templates.html", context={})


@router.get("/inspection-templates/{template_id}", response_class=HTMLResponse)
def inspection_template_page(request: Request, template_id: int):
    return templates.TemplateResponse(request=request, name="inspection_template.html", context={"template_id": template_id})


@router.get("/inquiries", response_class=HTMLResponse)
def inquiries_page(request: Request):
    return templates.TemplateResponse(request=request, name="inquiries.html", context={})


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_record_page(request: Request, customer_id: int):
    return templates.TemplateResponse(
        request=request, name="customer.html", context={"customer_id": customer_id}
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html", context={})


@router.get("/address-import", response_class=HTMLResponse)
def address_import_page(
    request: Request, _admin=Depends(require_admin("Der Adressimport ist nur für Administratoren verfügbar.")),
):
    return templates.TemplateResponse(request=request, name="address_import.html", context={})


@router.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}
