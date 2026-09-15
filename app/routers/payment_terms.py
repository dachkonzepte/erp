"""Router: payment_terms (seit 1.0.37).

Eigenständige Verwaltung, siehe Begründung in app/payment_terms.py und am
PaymentTerm-Modell.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser
from ..payment_terms import (
    create_payment_term, ensure_default_payment_terms, list_payment_terms,
    set_default_payment_term, set_payment_term_archived, update_payment_term,
)
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..schemas import PaymentTermCreate, PaymentTermOut, PaymentTermUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Zahlungsbedingungen sind Büro-/Admin-Konfiguration,
# nur von quote_editor.html (Angebotseditor, kein Monteurs-Werkzeug) genutzt.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


@router.get("/api/payment-terms", response_model=list[PaymentTermOut])
def get_payment_terms(include_archived: bool = False, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_payment_terms(db)
    return list_payment_terms(db, include_archived=include_archived)


@router.post("/api/payment-terms", response_model=PaymentTermOut)
def post_payment_term(payload: PaymentTermCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_payment_terms(db)
    try:
        return create_payment_term(db, payload.label, payload.days, payload.skonto_percent, payload.skonto_days, payload.text_template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/payment-terms/{term_id}", response_model=PaymentTermOut)
def put_payment_term(term_id: int, payload: PaymentTermUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        term = update_payment_term(db, term_id, payload.label, payload.days, payload.skonto_percent, payload.skonto_days, payload.text_template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if term is None:
        raise HTTPException(status_code=404, detail="Zahlungsbedingung nicht gefunden.")
    return term


@router.post("/api/payment-terms/{term_id}/set-default", response_model=PaymentTermOut)
def post_set_default_payment_term(term_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    term = set_default_payment_term(db, term_id)
    if term is None:
        raise HTTPException(status_code=404, detail="Zahlungsbedingung nicht gefunden.")
    return term


@router.post("/api/payment-terms/{term_id}/archive", response_model=PaymentTermOut)
def post_archive_payment_term(term_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        term = set_payment_term_archived(db, term_id, True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if term is None:
        raise HTTPException(status_code=404, detail="Zahlungsbedingung nicht gefunden.")
    return term


@router.post("/api/payment-terms/{term_id}/unarchive", response_model=PaymentTermOut)
def post_unarchive_payment_term(term_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    term = set_payment_term_archived(db, term_id, False)
    if term is None:
        raise HTTPException(status_code=404, detail="Zahlungsbedingung nicht gefunden.")
    return term
