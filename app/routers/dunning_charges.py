"""Router: Mahngebühren, Pauschale und Verzugsbeginn (seit 1.8.80, Zahlungsstufe Z2b, docs/archiv/zahlungen.md).

Geschäftslogik in app/dunning_charges.py; hier die HTTP-Anbindung: am Stand nicht möglich 409 (ChargeRejected: schon gegengebucht,
Verzugsbeginn schon bestätigt, Pauschale hängt daran), falsche Eingabe 400. Der Schalter "Mahngebühren und Verzugszinsen" nur
Admin (lesen ab buero_auftrag), alles andere ab buero_auftrag wie die Rechnungen; der Monteur nirgends. "Erfasst von" kommt aus
der Anmeldung.

Seit 1.8.81 (Z2b Punkte 7 und 9): Basiszinssatz je Halbjahr und Rechtstexte zu Verzug, Zinsen und Pauschale -- lesen ab
buero_auftrag, pflegen nur Admin (die Prüfangabe entscheidet, ob gerechnet bzw. gedruckt wird, wie bei den Klauseln).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..default_interest import RateConflict, create_rate, delete_rate, list_rates, rate_to_dict, update_rate
from ..dunning_charges import (
    ChargeRejected, charges_enabled, confirm_default_start, default_start_to_dict, discard_default_start,
    invoice_charges_view, reverse_charge, set_charges_enabled,
)
from ..dunning_texts import LEGAL_TEXT_KEYS, list_texts, update_text
from ..email_dispatch import actor_of
from ..invoices import get_invoice
from ..models import AppUser, BaseInterestRate, InvoiceCharge, InvoiceDefaultStart
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_geld, require_min_role
from ..schemas import (
    BaseInterestRateCreate, BaseInterestRateOut, BaseInterestRateUpdate, DunningLegalTextOut, DunningLegalTextUpdate,
    DunningSettingsOut, DunningSettingsUpdate, InvoiceChargesOut, InvoiceDefaultStartCreate, InvoiceDefaultStartOut, ReasonIn,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Mahnwesen ist nur für Büro und Administratoren verfügbar."))

# Seit 1.9.111 (Stufe 5, R1): schreiben nur Admin und Büro – Finanzen (app/permissions.py::darf_geld()), lesen jedes Büro.
_geld_dep = Depends(require_geld)

_admin_dep = Depends(require_min_role(ROLE_ADMIN, message="Mahngebühren und Verzugszinsen schaltet nur ein Administrator."))
_rates_admin_dep = Depends(require_min_role(ROLE_ADMIN, message="Basiszinssatz und Rechtstexte pflegen nur Administratoren."))


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
def get_dunning_settings(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return {"charges_enabled": charges_enabled(db)}


@router.put("/api/dunning-settings", response_model=DunningSettingsOut)
def put_dunning_settings(payload: DunningSettingsUpdate, db: Session = Depends(get_db, scope="function"), _admin: AppUser = _admin_dep):
    return {"charges_enabled": set_charges_enabled(db, payload.charges_enabled)}


@router.get("/api/invoices/{invoice_id}/charges", response_model=InvoiceChargesOut)
def get_invoice_charges(invoice_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return invoice_charges_view(db, _invoice_or_404(db, invoice_id))


@router.post("/api/invoices/{invoice_id}/default-start", response_model=InvoiceDefaultStartOut)
def post_default_start(invoice_id: int, payload: InvoiceDefaultStartCreate, db: Session = Depends(get_db, scope="function"),
                       user: AppUser = _geld_dep):
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
def post_discard_default_start(start_id: int, payload: ReasonIn, db: Session = Depends(get_db, scope="function"), user: AppUser = _geld_dep):
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
def post_reverse_charge(charge_id: int, payload: ReasonIn, db: Session = Depends(get_db, scope="function"), user: AppUser = _geld_dep):
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


# ---------------------------------------------------------------------------
# Basiszinssatz (seit 1.8.81, Z2b Punkt 7)
# ---------------------------------------------------------------------------

def _actor_name(user: AppUser) -> str:
    return actor_of(user)[1] or "System"


def _rate_or_404(db: Session, rate_id: int) -> BaseInterestRate:
    row = db.get(BaseInterestRate, rate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Basiszinssatz nicht gefunden.")
    return row


def _rate_http(error: Exception) -> HTTPException:
    if isinstance(error, RateConflict):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("/api/base-interest-rates", response_model=list[BaseInterestRateOut])
def get_base_interest_rates(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return list_rates(db)


@router.post("/api/base-interest-rates", response_model=BaseInterestRateOut)
def post_base_interest_rate(payload: BaseInterestRateCreate, db: Session = Depends(get_db, scope="function"), user: AppUser = _rates_admin_dep):
    try:
        row = create_rate(db, half_year_start=payload.half_year_start, rate_percent=payload.rate_percent,
                          reviewed_on=payload.reviewed_on, reviewed_by=payload.reviewed_by, actor_name=_actor_name(user))
    except ValueError as e:
        raise _rate_http(e) from e
    return rate_to_dict(row)


@router.put("/api/base-interest-rates/{rate_id}", response_model=BaseInterestRateOut)
def put_base_interest_rate(rate_id: int, payload: BaseInterestRateUpdate, db: Session = Depends(get_db, scope="function"),
                           user: AppUser = _rates_admin_dep):
    row = _rate_or_404(db, rate_id)
    try:
        row, review_reset = update_rate(db, row, rate_percent=payload.rate_percent, reviewed_on=payload.reviewed_on,
                                        reviewed_by=payload.reviewed_by, actor_name=_actor_name(user))
    except ValueError as e:
        raise _rate_http(e) from e
    return {**rate_to_dict(row), "review_reset": review_reset}


@router.delete("/api/base-interest-rates/{rate_id}")
def delete_base_interest_rate(rate_id: int, db: Session = Depends(get_db, scope="function"), _admin: AppUser = _rates_admin_dep):
    row = _rate_or_404(db, rate_id)
    try:
        delete_rate(db, row)
    except ValueError as e:
        raise _rate_http(e) from e
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Rechtstexte zu Verzug, Zinsen und Pauschale (seit 1.8.81, Z2b Punkt 9)
# ---------------------------------------------------------------------------

@router.get("/api/dunning-legal-texts", response_model=list[DunningLegalTextOut])
def get_dunning_legal_texts(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return list_texts(db)


@router.put("/api/dunning-legal-texts/{text_key}", response_model=DunningLegalTextOut)
def put_dunning_legal_text(text_key: str, payload: DunningLegalTextUpdate, db: Session = Depends(get_db, scope="function"),
                           user: AppUser = _rates_admin_dep):
    if text_key not in LEGAL_TEXT_KEYS:
        raise HTTPException(status_code=404, detail="Unbekannter Rechtstext.")
    try:
        text, review_reset = update_text(db, text_key, body=payload.body, reviewed_on=payload.reviewed_on,
                                         reviewed_by=payload.reviewed_by, actor_name=_actor_name(user))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {**text, "review_reset": review_reset}
