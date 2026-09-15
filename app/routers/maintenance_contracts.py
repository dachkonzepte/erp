"""Router: maintenance_contracts (seit 1.2.0) -- Wartungsverträge, Teil des Moduls
"wartungen" (siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() -- 403 bei
deaktiviertem Modul, unabhängig von der Rolle, gleiches Muster wie bei tasks.py/modules.py."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..maintenance_contracts import (
    check_due_contracts_and_create_reminders, create_contract, create_contract_item,
    create_maintenance_contract_from_project, create_maintenance_visit, create_project_from_contract,
    create_window, delete_contract,
    delete_contract_item, delete_window, get_contract, get_or_create_maintenance_settings, list_contracts,
    list_contracts_for_property, list_due_items_grouped,
    list_windows, maintenance_settings_to_dict, reorder_windows, set_contract_archived, set_contract_status,
    set_item_archived, update_contract, update_contract_item, update_maintenance_settings, update_window,
)
from ..modules import is_module_enabled
from ..service_reports import list_contract_history
from ..schemas import (
    MaintenanceContractCreate, MaintenanceContractCreateProjectRequest, MaintenanceContractFromProjectCreate,
    MaintenanceContractItemCreate, MaintenanceContractItemOut, MaintenanceContractItemUpdate,
    MaintenanceContractOut, MaintenanceContractStatusUpdate, MaintenanceContractUpdate, MaintenanceSettingsOut,
    MaintenanceSettingsUpdate, MaintenanceWindowCreate, MaintenanceWindowOut, MaintenanceWindowReorder,
    MaintenanceWindowUpdate, ServiceReportOut,
)

router = APIRouter()

MODULE_KEY = "wartungen"

# Seit "Rechtekonzept" (siehe CLAUDE.md): Wartungsverträge sind Büro-/Admin-Bereich -- geprüft,
# kein Endpunkt dieser Datei wird von einer Monteur-Vorlage aufgerufen (die vom Monteur genutzte
# "Wartung durchführen"-Kette läuft über service_reports.html/den erzeugten Auftrag, nicht über
# diese Verwaltungsendpunkte selbst). Einige Endpunkte hier tragen bereits eine eigene,
# strengere require_admin()-Prüfung (Wartungsfenster/-einstellungen ändern) -- unverändert.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Wartungen & Reparaturen ist deaktiviert.")


@router.get("/api/maintenance-contracts", response_model=list[MaintenanceContractOut])
def get_maintenance_contracts(status: str | None = None, include_archived: bool = False, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_contracts(db, status=status, include_archived=include_archived)


@router.get("/api/properties/{property_id}/maintenance-contracts", response_model=list[MaintenanceContractOut])
def get_maintenance_contracts_for_property(property_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Für die Objektseite (seit 1.2.18) -- Business-Logik lebt in app/maintenance_contracts.py,
    deshalb hier trotz abweichendem URL-Präfix (Muster wie GET /api/orders/{order_id}/roof-areas
    in routers/service_reports.py)."""
    _require_module_enabled(db)
    return list_contracts_for_property(db, property_id)


@router.get("/api/maintenance-contracts/due-items")
def get_maintenance_contracts_due_items(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Für die Übersicht "Fällige Wartungen im Fenster" -- vorsorglich als literaler Pfad VOR
    jeder künftigen /{contract_id}-Route deklariert (siehe Routen-Reihenfolge-Hinweis unten)."""
    _require_module_enabled(db)
    return list_due_items_grouped(db)


@router.get("/api/maintenance-contracts/{contract_id}", response_model=MaintenanceContractOut)
def get_maintenance_contract(contract_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Für die eigene Vertragsseite (seit 1.2.19) -- bewusst NACH der literalen GET-Route
    /due-items deklariert (Starlette matched nach Deklarationsreihenfolge), sonst würde ein
    GET auf /due-items fälschlich hier landen (contract_id="due-items")."""
    _require_module_enabled(db)
    result = get_contract(db, contract_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Wartungsvertrag nicht gefunden.")
    return result


@router.post("/api/maintenance-contracts/check-due")
def post_check_due_maintenance_contracts(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Analog zu POST /api/reminders/auto-create -- vom Frontend beim Seitenaufruf
    ausgelöst, kein Hintergrund-Job (siehe Modul-Docstring in app/maintenance_contracts.py)."""
    _require_module_enabled(db)
    reminded = check_due_contracts_and_create_reminders(db)
    return {"reminded_contract_ids": reminded}


@router.post("/api/maintenance-contracts", response_model=MaintenanceContractOut)
def post_maintenance_contract(payload: MaintenanceContractCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_contract(
            db, customer_id=payload.customer_id, property_id=payload.property_id, title=payload.title,
            interval_months=payload.interval_months, next_due_date=payload.next_due_date,
            template_project_id=payload.template_project_id,
            responsible_employee_id=payload.responsible_employee_id, notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/maintenance-contracts/{contract_id}", response_model=MaintenanceContractOut)
def put_maintenance_contract(contract_id: int, payload: MaintenanceContractUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_contract(
            db, contract_id, title=payload.title, interval_months=payload.interval_months,
            next_due_date=payload.next_due_date, template_project_id=payload.template_project_id,
            responsible_employee_id=payload.responsible_employee_id, notes=payload.notes,
            property_id=payload.property_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Wartungsvertrag nicht gefunden.")
    return result


@router.put("/api/maintenance-contracts/{contract_id}/status", response_model=MaintenanceContractOut)
def put_maintenance_contract_status(contract_id: int, payload: MaintenanceContractStatusUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = set_contract_status(db, contract_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Wartungsvertrag nicht gefunden.")
    return result


@router.delete("/api/maintenance-contracts/{contract_id}")
def delete_maintenance_contract(contract_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        deleted = delete_contract(db, contract_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Wartungsvertrag nicht gefunden.")
    return {"ok": True}


@router.post("/api/maintenance-contracts/{contract_id}/archive", response_model=MaintenanceContractOut)
def archive_maintenance_contract(contract_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_contract_archived(db, contract_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Wartungsvertrag nicht gefunden.")
    return result


@router.post("/api/maintenance-contracts/{contract_id}/unarchive", response_model=MaintenanceContractOut)
def unarchive_maintenance_contract(contract_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_contract_archived(db, contract_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Wartungsvertrag nicht gefunden.")
    return result


@router.post("/api/maintenance-contracts/{contract_id}/create-project")
def post_create_project_from_contract(contract_id: int, payload: MaintenanceContractCreateProjectRequest, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_project_from_contract(db, contract_id, item_id=payload.item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/maintenance-contracts/{contract_id}/perform-maintenance")
def post_perform_maintenance(contract_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_maintenance_visit(db, contract_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/maintenance-contracts/{contract_id}/items", response_model=MaintenanceContractItemOut)
def post_maintenance_contract_item(contract_id: int, payload: MaintenanceContractItemCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_contract_item(
            db, contract_id, roof_area_id=payload.roof_area_id, maintenance_window_id=payload.maintenance_window_id,
            description=payload.description, template_project_id=payload.template_project_id,
            inspection_template_id=payload.inspection_template_id, duration_minutes=payload.duration_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/maintenance-contracts/{contract_id}/history", response_model=list[ServiceReportOut])
def get_maintenance_contract_history(contract_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_contract_history(db, contract_id)


@router.post("/api/maintenance-contracts/from-project/{project_id}", response_model=MaintenanceContractOut)
def post_maintenance_contract_from_project(project_id: int, payload: MaintenanceContractFromProjectCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_maintenance_contract_from_project(
            db, project_id, interval_months=payload.interval_months, next_due_date=payload.next_due_date,
            responsible_employee_id=payload.responsible_employee_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/maintenance-settings", response_model=MaintenanceSettingsOut)
def get_maintenance_settings(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return maintenance_settings_to_dict(get_or_create_maintenance_settings(db))


@router.put("/api/maintenance-settings", response_model=MaintenanceSettingsOut)
def put_maintenance_settings(payload: MaintenanceSettingsUpdate, db: Session = Depends(get_db),
                              _admin=Depends(require_admin("Nur Administratoren dürfen die Wartungen-Einstellungen ändern."))):
    _require_module_enabled(db)
    try:
        return update_maintenance_settings(
            db, payload.reminder_lead_days, payload.use_roof_area_items, payload.default_responsible_employee_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Positionen (eigener Pfad-Präfix "maintenance-contract-items", keine Kollisionsgefahr
# mit den maintenance-contracts-Routen oben) ---

@router.put("/api/maintenance-contract-items/{item_id}", response_model=MaintenanceContractItemOut)
def put_maintenance_contract_item(item_id: int, payload: MaintenanceContractItemUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_contract_item(
            db, item_id, roof_area_id=payload.roof_area_id, maintenance_window_id=payload.maintenance_window_id,
            description=payload.description, template_project_id=payload.template_project_id,
            inspection_template_id=payload.inspection_template_id, duration_minutes=payload.duration_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Position nicht gefunden.")
    return result


@router.post("/api/maintenance-contract-items/{item_id}/archive", response_model=MaintenanceContractItemOut)
def archive_maintenance_contract_item(item_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_item_archived(db, item_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Position nicht gefunden.")
    return result


@router.post("/api/maintenance-contract-items/{item_id}/unarchive", response_model=MaintenanceContractItemOut)
def unarchive_maintenance_contract_item(item_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_item_archived(db, item_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Position nicht gefunden.")
    return result


@router.delete("/api/maintenance-contract-items/{item_id}")
def delete_maintenance_contract_item(item_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        deleted = delete_contract_item(db, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Position nicht gefunden.")
    return {"ok": True}


# --- Saisonale Wartungsfenster -- Routen-Reihenfolge bindend: /reorder (literal) MUSS vor
# /{window_id} (Platzhalter) deklariert werden, sonst matcht ein PUT auf /reorder fälschlich
# als window_id="reorder" (siehe app/routers/task_columns.py für dasselbe, dort bereits
# richtig gelöste Muster) ---

@router.get("/api/maintenance-windows", response_model=list[MaintenanceWindowOut])
def get_maintenance_windows(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_windows(db)


@router.post("/api/maintenance-windows", response_model=MaintenanceWindowOut)
def post_maintenance_window(payload: MaintenanceWindowCreate, db: Session = Depends(get_db),
                             _admin=Depends(require_admin("Nur Administratoren dürfen Wartungsfenster anlegen."))):
    _require_module_enabled(db)
    try:
        return create_window(db, payload.label, payload.month_from, payload.month_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/maintenance-windows/reorder", response_model=list[MaintenanceWindowOut])
def put_maintenance_windows_reorder(payload: MaintenanceWindowReorder, db: Session = Depends(get_db),
                                     _admin=Depends(require_admin("Nur Administratoren dürfen Wartungsfenster umsortieren."))):
    _require_module_enabled(db)
    try:
        return reorder_windows(db, payload.ordered_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/maintenance-windows/{window_id}", response_model=MaintenanceWindowOut)
def put_maintenance_window(window_id: int, payload: MaintenanceWindowUpdate, db: Session = Depends(get_db),
                            _admin=Depends(require_admin("Nur Administratoren dürfen Wartungsfenster bearbeiten."))):
    _require_module_enabled(db)
    try:
        result = update_window(db, window_id, payload.label, payload.month_from, payload.month_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Wartungsfenster nicht gefunden.")
    return result


@router.delete("/api/maintenance-windows/{window_id}")
def delete_maintenance_window(window_id: int, db: Session = Depends(get_db),
                               _admin=Depends(require_admin("Nur Administratoren dürfen Wartungsfenster löschen."))):
    _require_module_enabled(db)
    try:
        deleted = delete_window(db, window_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Wartungsfenster nicht gefunden.")
    return {"ok": True}
