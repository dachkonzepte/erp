"""Router: reminders (seit 1.0.53).

Endpunkte für das Mahnwesen -- Geschäftslogik liegt vollständig in
app/reminders.py, hier nur die HTTP-Anbindung, analog zu app/routers/invoices.py. Seit 1.8.72
InvoiceBlocked (Rechnung storniert oder bezahlt) als 409. Seit 1.8.79 (Z2a) keine Entwürfe mehr von selbst
(POST /api/reminders/auto-create und /api/reminder-settings entfallen), dafür Entwürfe für mehrere Rechnungen
(POST /api/reminders/bulk); Bearbeiten eines festgeschriebenen 409. Seit 1.8.80 (Z2b) Mahnstufen als Teil-Update, Gebühr und
Pauschale im Entwurf über PUT /api/reminders/{id}/charges (nur bei eingeschalteten Mahngebühren, sonst 409).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_dispatch import DispatchConflict
from .email_dispatches import document_pdf_response
from ..invoices import InvoiceBlocked, get_invoice
from ..models import AppUser, Reminder, ReminderLevel
from ..permissions import ROLE_OFFICE_AUFTRAG, require_geld, require_min_role
from ..reminder_pdf import build_reminder_pdf
from ..reminders import (
    compute_reminder_status, create_reminder, create_reminders, delete_reminder_draft, finalize_and_send_reminder,
    list_all_reminders, list_invoices_needing_attention, list_reminder_levels, list_reminders_for_invoice,
    reminder_to_dict, reminders_to_dicts, send_reminder_email, set_reminder_charges, update_reminder_draft,
    update_reminder_level,
)
from ..schemas import (
    InvoiceNeedingAttentionOut, ReminderBulkCreate, ReminderBulkOut, ReminderChargesUpdate, ReminderCreate, ReminderEmailSend,
    ReminderLevelOut, ReminderLevelUpdate, ReminderOut, ReminderStatusOut, ReminderUpdate,
)

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Mahnwesen ist Büro-/Admin-Bereich, für einen Monteur
# an keiner Stelle vorgesehen -- keine Objekt-Filterung nötig, reiner Rollen-Block.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Mahnwesen ist nur für Büro und Administratoren verfügbar."))

# Seit 1.9.111 (Stufe 5, R1): schreiben nur Admin und Büro – Finanzen (app/permissions.py::darf_geld()), lesen jedes Büro.
_geld_dep = Depends(require_geld)


def _get_invoice_or_404(db: Session, invoice_id: int):
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden.")
    return invoice


def _get_reminder_or_404(db: Session, reminder_id: int) -> Reminder:
    reminder = db.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Mahnung nicht gefunden.")
    return reminder


@router.get("/api/reminder-levels", response_model=list[ReminderLevelOut])
def get_reminder_levels(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return list_reminder_levels(db)


@router.put("/api/reminder-levels/{level_id}", response_model=ReminderLevelOut)
def put_reminder_level(level_id: int, payload: ReminderLevelUpdate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    level_row = db.get(ReminderLevel, level_id)
    if level_row is None:
        raise HTTPException(status_code=404, detail="Mahnstufe nicht gefunden.")
    # Seit 1.8.80 nur die gesendeten Felder (Regel 22).
    return update_reminder_level(db, level_row, **payload.model_dump(exclude_unset=True))


@router.get("/api/reminders/overdue", response_model=list[InvoiceNeedingAttentionOut])
def get_overdue_invoices(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return list_invoices_needing_attention(db)


@router.get("/api/reminders", response_model=list[ReminderOut])
def get_all_reminders(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return reminders_to_dicts(db, list_all_reminders(db))


@router.post("/api/reminders/bulk", response_model=ReminderBulkOut)
def post_reminders_bulk(payload: ReminderBulkCreate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _geld_dep):
    """Seit 1.8.79 (Z2a Nr. 1): je Rechnung ein Entwurf der nächsten Stufe, jede einzeln unter ihrer Sperre geprüft -- eine
    abgelehnte hält die anderen nicht auf, die Antwort nennt sie mit Grund (immer 200)."""
    result = create_reminders(db, payload.invoice_ids)
    return {"created": reminders_to_dicts(db, result["created"]), "rejected": result["rejected"]}


@router.get("/api/invoices/{invoice_id}/reminder-status", response_model=ReminderStatusOut)
def get_invoice_reminder_status(invoice_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    return compute_reminder_status(db, invoice)


@router.get("/api/invoices/{invoice_id}/reminders", response_model=list[ReminderOut])
def get_invoice_reminders(invoice_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _get_invoice_or_404(db, invoice_id)
    return reminders_to_dicts(db, list_reminders_for_invoice(db, invoice_id))


@router.post("/api/invoices/{invoice_id}/reminders", response_model=ReminderOut)
def post_invoice_reminder(invoice_id: int, payload: ReminderCreate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _geld_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        reminder = create_reminder(db, invoice, payload.level)
    except InvoiceBlocked as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.post("/api/reminders/{reminder_id}/send", response_model=ReminderOut)
def post_send_reminder(reminder_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _geld_dep):
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        finalize_and_send_reminder(db, reminder)
    except InvoiceBlocked as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.post("/api/reminders/{reminder_id}/send-email", response_model=ReminderOut)
def post_send_reminder_email(reminder_id: int, payload: ReminderEmailSend, db: Session = Depends(get_db, scope="function"), user: AppUser = _geld_dep):
    """Tatsächlicher E-Mail-Versand (seit 1.0.74) -- getrennt vom
    Finalisieren oben (/send), das nur Nummer/Status setzt. Kann auf einer
    bereits finalisierten Mahnung auch mehrfach aufgerufen werden (z.B.
    erneuter Versand)."""
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        send_reminder_email(
            db, reminder, to_email=payload.to_email, cc_email=payload.cc_email,
            dispatch_key=payload.dispatch_key, user=user,
        )
    except (DispatchConflict, InvoiceBlocked) as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.put("/api/reminders/{reminder_id}", response_model=ReminderOut)
def put_reminder(reminder_id: int, payload: ReminderUpdate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _geld_dep):
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        update_reminder_draft(db, reminder, text=payload.text, payment_days=payload.payment_days)
    except InvoiceBlocked as e:  # seit 1.8.79: unter der Sperre nicht (mehr) Entwurf
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.put("/api/reminders/{reminder_id}/charges", response_model=ReminderOut)
def put_reminder_charges(reminder_id: int, payload: ReminderChargesUpdate, db: Session = Depends(get_db, scope="function"),
                         _role: AppUser = _geld_dep):
    """Seit 1.8.80 (Z2b Nr. 5 und 6): Gebühr und Pauschale im Entwurf bewusst übernehmen. 409, wenn Mahngebühren ausgeschaltet
    sind, die Mahnung kein Entwurf mehr ist oder die Pauschale nicht möglich ist (mit Grund). Seit 1.8.81 dazu die
    Verzugszinsen (409 ohne Vorschlag) und keine Gebühr neben der Pauschale (409)."""
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        set_reminder_charges(db, reminder, fee_amount=payload.fee_amount, fee_accepted=payload.fee_accepted,
                             flat_fee_accepted=payload.flat_fee_accepted, interest_accepted=payload.interest_accepted)
    except InvoiceBlocked as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.delete("/api/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _geld_dep):
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        delete_reminder_draft(db, reminder)
    except InvoiceBlocked as e:  # seit 1.8.73: nicht (mehr) Entwurf nach der Sperre
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": True}


@router.get("/api/reminders/{reminder_id}/pdf")
def get_reminder_pdf(reminder_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.8.19 ab dem ersten Versand die abgelegte Fassung, sonst neu erzeugt (siehe
    document_pdf_response())."""
    reminder = _get_reminder_or_404(db, reminder_id)
    name_part = reminder.reminder_number or f"Entwurf-{reminder.id}"
    filename = f"Mahnung_{name_part}.pdf".replace("/", "-")
    return document_pdf_response(db, "mahnung", reminder.id, build=lambda: build_reminder_pdf(db, reminder),
                                 filename=filename)
