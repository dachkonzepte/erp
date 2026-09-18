"""Router: findings (seit 1.2.17) -- Mängel aus Einsatzberichten, Teil des Moduls "wartungen"
(siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() -- 403 bei
deaktiviertem Modul, gleiches Muster wie bei service_reports.py/inspection_templates.py."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..findings import (
    create_finding, create_follow_up_project_for_task, get_finding_for_task, list_findings,
    list_findings_for_component, list_findings_for_report, update_finding_followup,
)
from ..models import AppUser, Finding
from ..modules import is_module_enabled
from ..permissions import ROLE_FIELD, ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import FindingCreate, FindingFollowupUpdate, FindingOut
from .orders import require_field_report_ownership
from .service_reports import _employee_for_request

router = APIRouter()

MODULE_KEY = "wartungen"

# Seit "Rechtekonzept" (siehe CLAUDE.md): zwei Gruppen in dieser Datei.
#
# Büro/Admin: die auftragsübergreifende Mängelliste (GET /api/findings, findings.html) und die
# Mängelhistorie je Bauteil (GET /api/roof-components/{id}/findings, roof_area.html) -- beides
# Objekt-/Kundenkontext über mehrere Aufträge hinweg, den ein Monteur nicht braucht. Dazu die
# beiden /api/tasks/{task_id}/...-Endpunkte: gehören zur Aufgaben-Sperre für `field` (dieselbe
# Entscheidung wie in app/routers/tasks.py), auch wenn sie aus historischen Gründen hier liegen
# -- "Vorgang erstellen" aus einer Aufgabe heraus ist eine Büro-Aktion am Schreibtisch.
#
# Jede Rolle, mit Eigentümerschaft (Teil B, seit dem Fund "fremde Berichte lesen und schreiben
# auf einem gemeinsamen Auftrag" -- siehe CLAUDE.md "Rechtekonzept" -> "Berichts-
# Eigentümerschaft"): der Mängel-Workflow WÄHREND eines Einsatzberichts (Mängel eines Berichts
# lesen/anlegen, Nachverfolgung ändern) -- vom Monteur selbst bedient (service_reports.html). Für
# `field` zusätzlich require_field_report_ownership() -- ein Mangel gehört zu genau einem
# Bericht, dessen Ersteller muss man sein, nicht nur irgendwer mit Zugriff auf den Auftrag.
_office_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))
_any_role_dep = Depends(require_min_role(ROLE_FIELD))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Wartungen & Reparaturen ist deaktiviert.")


def _report_id_for_finding(db: Session, finding_id: int) -> int:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Mangel nicht gefunden.")
    return finding.service_report_id


@router.get("/api/findings", response_model=list[FindingOut])
def get_findings(
    status: str | None = None, severity: str | None = None, property_id: int | None = None,
    overdue_only: bool = False, date_from: date | None = None, date_to: date | None = None,
    db: Session = Depends(get_db), _role: AppUser = _office_role_dep,
):
    _require_module_enabled(db)
    return list_findings(
        db, status=status, severity=severity, property_id=property_id, overdue_only=overdue_only,
        date_from=date_from, date_to=date_to,
    )


@router.get("/api/service-reports/{report_id}/findings", response_model=list[FindingOut])
def get_report_findings(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Seit dem Fund "fremde Berichte lesen und schreiben auf einem gemeinsamen Auftrag" (siehe
    CLAUDE.md "Rechtekonzept" -> "Berichts-Eigentümerschaft"): require_field_report_ownership()
    statt require_field_order_access() -- ein Monteur sieht die vollen Mängeldaten eines Berichts
    nur, wenn er dessen Ersteller ist. Die reduzierte Mängel-Zusammenfassung eines fremden
    Berichts (Beschreibung, Schweregrad, Status) bleibt weiterhin über die Berichtsliste
    erreichbar (list_reports_for_field() in app/service_reports.py)."""
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    return list_findings_for_report(db, report_id)


@router.post("/api/service-reports/{report_id}/findings", response_model=FindingOut)
def post_finding(report_id: int, payload: FindingCreate, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    employee_id = _employee_for_request(request, payload.created_by_employee_id)
    try:
        return create_finding(
            db, report_id, payload.description, payload.severity, payload.action,
            inspection_item_id=payload.inspection_item_id, roof_component_id=payload.roof_component_id,
            resubmission_date=payload.resubmission_date, created_by_employee_id=employee_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/findings/{finding_id}/followup", response_model=FindingOut)
def put_finding_followup(finding_id: int, payload: FindingFollowupUpdate, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_finding(db, finding_id))
    try:
        result = update_finding_followup(
            db, finding_id, status=payload.status, action=payload.action,
            resubmission_date=payload.resubmission_date, closed_by_employee_id=payload.closed_by_employee_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Mangel nicht gefunden.")
    return result


@router.get("/api/roof-components/{component_id}/findings", response_model=list[FindingOut])
def get_component_findings(component_id: int, db: Session = Depends(get_db), _role: AppUser = _office_role_dep):
    _require_module_enabled(db)
    return list_findings_for_component(db, component_id)


@router.get("/api/tasks/{task_id}/finding", response_model=FindingOut | None)
def get_task_finding(task_id: int, db: Session = Depends(get_db), _role: AppUser = _office_role_dep):
    """Rückrichtung von einer Aufgabe zum Mangel, der sie erzeugt hat (seit 1.2.21) -- für die
    "Vorgang erstellen"-Schaltfläche im Aufgaben-Editor. URL-Präfix richtet sich nach dem
    Task-Kontext, aus dem der Endpunkt aufgerufen wird; die Business-Logik bleibt in
    app/findings.py (Muster wie GET /api/orders/{order_id}/roof-areas)."""
    _require_module_enabled(db)
    return get_finding_for_task(db, task_id)


@router.post("/api/tasks/{task_id}/create-follow-up-project")
def post_task_create_follow_up_project(task_id: int, db: Session = Depends(get_db), _role: AppUser = _office_role_dep):
    _require_module_enabled(db)
    try:
        return create_follow_up_project_for_task(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
