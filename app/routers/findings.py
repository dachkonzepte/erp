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
from ..models import AppUser
from ..modules import is_module_enabled
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..schemas import FindingCreate, FindingFollowupUpdate, FindingOut
from .service_reports import _employee_for_request

router = APIRouter()

MODULE_KEY = "wartungen"

# Seit "Rechtekonzept" (siehe CLAUDE.md → "Aufgaben"): die beiden /api/tasks/{task_id}/...-
# Endpunkte unten gehören inhaltlich zur Aufgaben-Sperre für `field` (dieselbe Entscheidung wie
# in app/routers/tasks.py/task_columns.py), auch wenn sie aus historischen Gründen in dieser
# Datei liegen -- "Vorgang erstellen" aus einer Aufgabe heraus ist ohnehin eine Büro-Aktion am
# Schreibtisch (siehe CLAUDE.md "Aufgabe"). Die übrigen Endpunkte dieser Datei (Mängel-
# Workflow während eines Einsatzberichts) bleiben bewusst unklassifiziert -- Teil der nächsten,
# noch zu bestätigenden Etappe (Monteure erfassen Mängel selbst, siehe CLAUDE.md "Mängel und
# Fotos"), nicht dieser Runde.
_task_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Wartungen & Reparaturen ist deaktiviert.")


@router.get("/api/findings", response_model=list[FindingOut])
def get_findings(
    status: str | None = None, severity: str | None = None, property_id: int | None = None,
    overdue_only: bool = False, date_from: date | None = None, date_to: date | None = None,
    db: Session = Depends(get_db),
):
    _require_module_enabled(db)
    return list_findings(
        db, status=status, severity=severity, property_id=property_id, overdue_only=overdue_only,
        date_from=date_from, date_to=date_to,
    )


@router.get("/api/service-reports/{report_id}/findings", response_model=list[FindingOut])
def get_report_findings(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_findings_for_report(db, report_id)


@router.post("/api/service-reports/{report_id}/findings", response_model=FindingOut)
def post_finding(report_id: int, payload: FindingCreate, request: Request, db: Session = Depends(get_db)):
    _require_module_enabled(db)
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
def put_finding_followup(finding_id: int, payload: FindingFollowupUpdate, db: Session = Depends(get_db)):
    _require_module_enabled(db)
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
def get_component_findings(component_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_findings_for_component(db, component_id)


@router.get("/api/tasks/{task_id}/finding", response_model=FindingOut | None)
def get_task_finding(task_id: int, db: Session = Depends(get_db), _role: AppUser = _task_role_dep):
    """Rückrichtung von einer Aufgabe zum Mangel, der sie erzeugt hat (seit 1.2.21) -- für die
    "Vorgang erstellen"-Schaltfläche im Aufgaben-Editor. URL-Präfix richtet sich nach dem
    Task-Kontext, aus dem der Endpunkt aufgerufen wird; die Business-Logik bleibt in
    app/findings.py (Muster wie GET /api/orders/{order_id}/roof-areas)."""
    _require_module_enabled(db)
    return get_finding_for_task(db, task_id)


@router.post("/api/tasks/{task_id}/create-follow-up-project")
def post_task_create_follow_up_project(task_id: int, db: Session = Depends(get_db), _role: AppUser = _task_role_dep):
    _require_module_enabled(db)
    try:
        return create_follow_up_project_for_task(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
