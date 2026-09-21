"""Router: incoming_invoices -- Buchhaltung Stufe 1 (Eingangsrechnungen), Teil des Moduls
"buchhaltung" (siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() -- 403
bei deaktiviertem Modul, unabhängig von der Rolle, gleiches Muster wie recurring_costs.py.

Ausnahmslos require_min_role(ROLE_OFFICE_FINANZEN) -- Buchhaltung ist wie Betriebskosten-
Übersicht/Kalkulationsgrundlagen die Finanzen-Achse: ein buero_auftrag-Konto sieht diesen
gesamten Bereich an KEINER Stelle (Liste, Einzelabruf, Beleg, Skonto-Aufgaben-Auslöser), kein
_any_role_dep."""

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..incoming_invoice_documents import (
    ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, document_path, replace_document,
)
from ..incoming_invoices import (
    MODULE_KEY, check_due_skonto_and_create_reminders, create_invoice, delete_invoice,
    get_invoice, get_or_create_incoming_invoice_settings, incoming_invoice_settings_to_dict,
    list_invoices, open_liabilities_summary, remove_invoice_document, set_invoice_document,
    update_incoming_invoice_settings, update_invoice,
)
from ..models import AppUser, IncomingInvoice
from ..modules import is_module_enabled
from ..permissions import ROLE_OFFICE_FINANZEN, require_min_role
from ..schemas import (
    IncomingInvoiceCreate, IncomingInvoiceOpenLiabilitiesOut, IncomingInvoiceOut,
    IncomingInvoiceSettingsOut, IncomingInvoiceSettingsUpdate, IncomingInvoiceUpdate,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_FINANZEN))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Buchhaltung ist deaktiviert.")


@router.get("/api/incoming-invoices/open-liabilities", response_model=IncomingInvoiceOpenLiabilitiesOut)
def get_incoming_invoices_open_liabilities(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Summe offener Verbindlichkeiten + Skonto-Warnungen -- bewusst als literaler Pfad VOR
    /{invoice_id} deklariert (Muster GET /api/recurring-costs/overview)."""
    _require_module_enabled(db)
    return open_liabilities_summary(db)


@router.post("/api/incoming-invoices/check-due")
def post_incoming_invoices_check_due(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """On-Demand-Erinnerung -- vom Frontend beim Aufruf der Eingangsrechnungen-Liste ausgelöst,
    kein Hintergrund-Job (Muster POST /api/recurring-costs/check-due)."""
    _require_module_enabled(db)
    reminded = check_due_skonto_and_create_reminders(db)
    return {"reminded_invoice_ids": reminded}


@router.get("/api/incoming-invoices", response_model=list[IncomingInvoiceOut])
def get_incoming_invoices(
    payment_status: str | None = None, supplier_id: int | None = None,
    date_from: date | None = None, date_to: date | None = None,
    db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    _require_module_enabled(db)
    return list_invoices(
        db, payment_status=payment_status, supplier_id=supplier_id, date_from=date_from, date_to=date_to,
    )


@router.get("/api/incoming-invoices/{invoice_id}", response_model=IncomingInvoiceOut)
def get_incoming_invoice(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = get_invoice(db, invoice_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Eingangsrechnung nicht gefunden.")
    return result


@router.post("/api/incoming-invoices", response_model=IncomingInvoiceOut)
def post_incoming_invoice(payload: IncomingInvoiceCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_invoice(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/api/incoming-invoices/{invoice_id}", response_model=IncomingInvoiceOut)
def put_incoming_invoice(invoice_id: int, payload: IncomingInvoiceUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_invoice(db, invoice_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Eingangsrechnung nicht gefunden.")
    return result


@router.delete("/api/incoming-invoices/{invoice_id}")
def delete_incoming_invoice(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_invoice(db, invoice_id):
        raise HTTPException(status_code=404, detail="Eingangsrechnung nicht gefunden.")
    return {"deleted": True}


@router.post("/api/incoming-invoices/{invoice_id}/document", response_model=IncomingInvoiceOut)
async def upload_incoming_invoice_document(
    invoice_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    _require_module_enabled(db)
    invoice = db.get(IncomingInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Eingangsrechnung nicht gefunden.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    if (file.content_type or "").lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Bitte PDF, PNG, JPEG oder WebP verwenden.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 10 MB.")
    stored = replace_document(invoice.document_filename, file.filename, data)
    return set_invoice_document(db, invoice_id, stored_filename=stored, original_filename=file.filename)


@router.get("/api/incoming-invoices/{invoice_id}/document/file")
def get_incoming_invoice_document_file(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    invoice = db.get(IncomingInvoice, invoice_id)
    if invoice is None or not invoice.document_filename:
        raise HTTPException(status_code=404, detail="Kein Beleg hinterlegt.")
    path = document_path(invoice.document_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Belegdatei nicht gefunden.")
    return FileResponse(path, filename=invoice.document_original_name or path.name)


@router.delete("/api/incoming-invoices/{invoice_id}/document", response_model=IncomingInvoiceOut)
def delete_incoming_invoice_document(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = remove_invoice_document(db, invoice_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Eingangsrechnung nicht gefunden.")
    return result


@router.get("/api/incoming-invoice-settings", response_model=IncomingInvoiceSettingsOut)
def get_incoming_invoice_settings_endpoint(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return incoming_invoice_settings_to_dict(get_or_create_incoming_invoice_settings(db))


@router.put("/api/incoming-invoice-settings", response_model=IncomingInvoiceSettingsOut)
def put_incoming_invoice_settings_endpoint(
    payload: IncomingInvoiceSettingsUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    _require_module_enabled(db)
    return update_incoming_invoice_settings(db, payload.skonto_reminder_lead_days)
