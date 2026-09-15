"""Router: reminders (seit 1.0.53).

Endpunkte für das Mahnwesen -- Geschäftslogik liegt vollständig in
app/reminders.py, hier nur die HTTP-Anbindung, analog zu app/routers/invoices.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..invoices import get_invoice
from ..models import AppUser, Reminder, ReminderLevel
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..reminder_pdf import build_reminder_pdf
from ..reminders import (
    auto_create_due_reminder_drafts, compute_reminder_status, create_reminder, delete_reminder_draft,
    ensure_default_reminder_levels, finalize_and_send_reminder, get_reminder_auto_create_setting,
    list_all_reminders, list_invoices_needing_attention, list_reminder_levels,
    list_reminders_for_invoice, reminder_to_dict, send_reminder_email, set_reminder_auto_create_setting,
    update_reminder_draft, update_reminder_level,
)
from ..schemas import ReminderCreate, ReminderEmailSend, ReminderLevelOut, ReminderLevelUpdate, ReminderOut, ReminderSettingsOut, ReminderSettingsUpdate, ReminderStatusOut, ReminderUpdate, InvoiceNeedingAttentionOut

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Mahnwesen ist Büro-/Admin-Bereich, für einen Monteur
# an keiner Stelle vorgesehen -- keine Objekt-Filterung nötig, reiner Rollen-Block.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, message="Mahnwesen ist nur für Büro und Administratoren verfügbar."))


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
def get_reminder_levels(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_reminder_levels(db)
    return list_reminder_levels(db)


@router.put("/api/reminder-levels/{level_id}", response_model=ReminderLevelOut)
def put_reminder_level(level_id: int, payload: ReminderLevelUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    level_row = db.get(ReminderLevel, level_id)
    if level_row is None:
        raise HTTPException(status_code=404, detail="Mahnstufe nicht gefunden.")
    return update_reminder_level(
        db, level_row, label=payload.label, days_after_previous_step=payload.days_after_previous_step,
        fee_amount=payload.fee_amount, text_template=payload.text_template, active=payload.active,
        email_subject_template=payload.email_subject_template, email_body_template=payload.email_body_template,
    )


@router.get("/api/reminders/overdue", response_model=list[InvoiceNeedingAttentionOut])
def get_overdue_invoices(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_reminder_levels(db)
    return list_invoices_needing_attention(db)


@router.get("/api/reminders", response_model=list[ReminderOut])
def get_all_reminders(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return [reminder_to_dict(r) for r in list_all_reminders(db)]


@router.get("/api/reminder-settings", response_model=ReminderSettingsOut)
def get_reminder_settings(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return ReminderSettingsOut(auto_create_drafts=get_reminder_auto_create_setting(db))


@router.put("/api/reminder-settings", response_model=ReminderSettingsOut)
def put_reminder_settings(payload: ReminderSettingsUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return ReminderSettingsOut(auto_create_drafts=set_reminder_auto_create_setting(db, payload.auto_create_drafts))


@router.post("/api/reminders/auto-create", response_model=list[ReminderOut])
def post_auto_create_reminder_drafts(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_reminder_levels(db)
    return [reminder_to_dict(r) for r in auto_create_due_reminder_drafts(db)]


@router.get("/api/invoices/{invoice_id}/reminder-status", response_model=ReminderStatusOut)
def get_invoice_reminder_status(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    ensure_default_reminder_levels(db)
    return compute_reminder_status(db, invoice)


@router.get("/api/invoices/{invoice_id}/reminders", response_model=list[ReminderOut])
def get_invoice_reminders(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _get_invoice_or_404(db, invoice_id)
    return [reminder_to_dict(r) for r in list_reminders_for_invoice(db, invoice_id)]


@router.post("/api/invoices/{invoice_id}/reminders", response_model=ReminderOut)
def post_invoice_reminder(invoice_id: int, payload: ReminderCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        reminder = create_reminder(db, invoice, payload.level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.post("/api/reminders/{reminder_id}/send", response_model=ReminderOut)
def post_send_reminder(reminder_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        finalize_and_send_reminder(db, reminder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.post("/api/reminders/{reminder_id}/send-email", response_model=ReminderOut)
def post_send_reminder_email(reminder_id: int, payload: ReminderEmailSend, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Tatsächlicher E-Mail-Versand (seit 1.0.74) -- getrennt vom
    Finalisieren oben (/send), das nur Nummer/Status setzt. Kann auf einer
    bereits finalisierten Mahnung auch mehrfach aufgerufen werden (z.B.
    erneuter Versand)."""
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        send_reminder_email(db, reminder, to_email=payload.to_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.put("/api/reminders/{reminder_id}", response_model=ReminderOut)
def put_reminder(reminder_id: int, payload: ReminderUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        update_reminder_draft(
            db, reminder, text=payload.text, fee_amount=payload.fee_amount, new_due_date=payload.new_due_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reminder_to_dict(reminder)


@router.delete("/api/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    reminder = _get_reminder_or_404(db, reminder_id)
    try:
        delete_reminder_draft(db, reminder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": True}


@router.get("/api/reminders/{reminder_id}/pdf")
def get_reminder_pdf(reminder_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    reminder = _get_reminder_or_404(db, reminder_id)
    pdf = build_reminder_pdf(db, reminder)
    name_part = reminder.reminder_number or f"Entwurf-{reminder.id}"
    filename = f"Mahnung_{name_part}.pdf".replace("/", "-")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
