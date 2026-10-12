"""Router: Mahngebühren, Pauschale und Verzugsbeginn (seit 1.8.80, Zahlungsstufe Z2b, docs/archiv/zahlungen.md).

Geschäftslogik in app/dunning_charges.py; hier die HTTP-Anbindung: am Stand nicht möglich 409 (ChargeRejected: schon gegengebucht,
Verzugsbeginn schon bestätigt, Pauschale hängt daran), falsche Eingabe 400. Der Schalter "Mahngebühren und Verzugszinsen" nur
Admin (lesen ab buero_auftrag), alles andere ab buero_auftrag wie die Rechnungen; der Monteur nirgends. "Erfasst von" kommt aus
der Anmeldung.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dunning_charges import (
    ChargeRejected, charges_enabled, confirm_default_start, default_start_to_dict, discard_default_start,
    invoice_charges_view, reverse_charge, set_charges_enabled,
)
from ..email_dispatch import actor_of
from ..invoices import get_invoice
from ..models import AppUser, InvoiceCharge, InvoiceDefaultStart
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import (
    DunningSettingsOut, DunningSettingsUpdate, InvoiceChargesOut, InvoiceDefaultStartCreate, InvoiceDefaultStartOut, ReasonIn,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Mahnwesen ist nur für Büro und Administratoren verfügbar."))
_admin_dep = Depends(require_min_role(ROLE_ADMIN, message="Mahngebühren und Verzugszinsen schaltet nur ein Administrator."))


def _http(error: Exception) -> HTTPException:
    if isinstance(error, ChargeRejected):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


def _invoice_or_404(db: Session, invoice_id: int):
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden.")
    return invoice


@router.get("/api/dunning-settings", response_model=DunningSettingsOut)
def get_dunning_settings(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return {"charges_enabled": charges_enabled(db)}


@router.put("/api/dunning-settings", response_model=DunningSettingsOut)
def put_dunning_settings(payload: DunningSettingsUpdate, db: Session = Depends(get_db), _admin: AppUser = _admin_dep):
    return {"charges_enabled": set_charges_enabled(db, payload.charges_enabled)}


@router.get("/api/invoices/{invoice_id}/charges", response_model=InvoiceChargesOut)
def get_invoice_charges(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return invoice_charges_view(db, _invoice_or_404(db, invoice_id))


@router.post("/api/invoices/{invoice_id}/default-start", response_model=InvoiceDefaultStartOut)
def post_default_start(invoice_id: int, payload: InvoiceDefaultStartCreate, db: Session = Depends(get_db),
                       user: AppUser = _role_dep):
    """Verzugsbeginn bestätigen: der Vorschlag oder ein anderer Tag mit Begründung."""
    invoice = _invoice_or_404(db, invoice_id)
    user_id, user_name = actor_of(user)
    try:
        row = confirm_default_start(db, invoice, starts_on=payload.starts_on, reason=payload.reason, user_id=user_id,
                                    user_name=user_name)
    except ValueError as e:
        raise _http(e)
    return default_start_to_dict(row)


@router.post("/api/invoice-default-starts/{start_id}/discard", response_model=InvoiceDefaultStartOut)
def post_discard_default_start(start_id: int, payload: ReasonIn, db: Session = Depends(get_db), user: AppUser = _role_dep):
    row = db.get(InvoiceDefaultStart, start_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Verzugsbeginn nicht gefunden.")
    user_id, user_name = actor_of(user)
    try:
        discard_default_start(db, row, reason=payload.reason, user_id=user_id, user_name=user_name)
    except ValueError as e:
        raise _http(e)
    return default_start_to_dict(row)


@router.post("/api/invoice-charges/{charge_id}/reverse", response_model=InvoiceChargesOut)
def post_reverse_charge(charge_id: int, payload: ReasonIn, db: Session = Depends(get_db), user: AppUser = _role_dep):
    """Gegenbuchung einer Nebenforderung (Korrektur oder Erlass) mit Begründung -- Antwort: die Karte der Rechnung."""
    charge = db.get(InvoiceCharge, charge_id)
    if charge is None:
        raise HTTPException(status_code=404, detail="Nebenforderung nicht gefunden.")
    user_id, user_name = actor_of(user)
    try:
        reverse_charge(db, charge, reason=payload.reason, user_id=user_id, user_name=user_name)
    except ValueError as e:
        raise _http(e)
    return invoice_charges_view(db, _invoice_or_404(db, charge.invoice_id))
