"""Router: address_import (Adressimport aus dem Altsystem, siehe CLAUDE.md).

Alles hier ist admin-gated -- der Import legt reale Kunden/Lieferanten an und kann einen Lauf
wieder löschen, beides keine Aktion für den normalen Tagesbetrieb."""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from .. import address_import as svc
from ..database import get_db
from ..deps import require_admin

router = APIRouter()

_ADMIN_MESSAGE = "Nur Administratoren dürfen den Adressimport verwenden."


def _employee_id_for_request(request: Request) -> int | None:
    user = getattr(request.state, "erp_user", None)
    return getattr(user, "employee_id", None) if user else None


@router.post("/api/address-import/upload")
async def upload_address_file(
    request: Request, file: UploadFile, db: Session = Depends(get_db),
    _admin=Depends(require_admin(_ADMIN_MESSAGE)),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    data = await file.read()
    try:
        return svc.create_preview(db, data, file.filename)
    except svc.AddressImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/address-import/preview")
def get_pending_preview(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    return svc.get_pending_preview(db) or {"total": 0, "counts": {}, "rows": []}


@router.post("/api/address-import/discard-preview")
def discard_preview(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    svc.discard_pending_preview(db)
    return {"ok": True}


@router.post("/api/address-import/confirm")
def confirm_preview(request: Request, filename: str, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        run = svc.confirm_import(db, filename, _employee_id_for_request(request))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": run.id, "row_count_total": run.row_count_total,
        "row_count_customers": run.row_count_customers, "row_count_suppliers": run.row_count_suppliers,
        "row_count_unassigned": run.row_count_unassigned, "row_count_skipped_duplicates": run.row_count_skipped_duplicates,
    }


@router.get("/api/address-import/runs")
def get_import_runs(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    return svc.list_import_runs(db)


@router.post("/api/address-import/runs/{run_id}/revert")
def revert_run(run_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        svc.revert_import_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/api/address-import/unassigned")
def get_unassigned(search: str | None = None, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    return svc.list_unassigned(db, search)


@router.post("/api/address-import/unassigned/{entry_id}/create-customer")
def unassigned_create_customer(entry_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        customer = svc.resolve_as_new_customer(db, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"customer_id": customer.id}


@router.post("/api/address-import/unassigned/{entry_id}/assign-property")
def unassigned_assign_property(entry_id: int, customer_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        prop = svc.resolve_as_property(db, entry_id, customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"property_id": prop.id, "customer_id": customer_id}


@router.post("/api/address-import/unassigned/{entry_id}/discard")
def unassigned_discard(entry_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        svc.discard_unassigned(db, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}
