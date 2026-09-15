"""Router: tax_keys (seit 1.0.44).

Eigenständige Verwaltung, siehe Begründung in app/tax_keys.py und am
TaxKey-Modell.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..tax_keys import (
    create_tax_key, ensure_default_tax_keys, list_tax_keys,
    set_default_tax_key, set_tax_key_archived, update_tax_key,
)
from ..schemas import TaxKeyCreate, TaxKeyOut, TaxKeyUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Steuerschlüssel sind Büro-/Admin-Konfiguration, nur
# von quote_editor.html (Angebotseditor, kein Monteurs-Werkzeug) genutzt.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


@router.get("/api/tax-keys", response_model=list[TaxKeyOut])
def get_tax_keys(include_archived: bool = False, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_tax_keys(db)
    return list_tax_keys(db, include_archived=include_archived)


@router.post("/api/tax-keys", response_model=TaxKeyOut)
def post_tax_key(payload: TaxKeyCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_tax_keys(db)
    return create_tax_key(db, payload.label, payload.vat_rate, payload.notice_text)


@router.put("/api/tax-keys/{key_id}", response_model=TaxKeyOut)
def put_tax_key(key_id: int, payload: TaxKeyUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    key = update_tax_key(db, key_id, payload.label, payload.vat_rate, payload.notice_text)
    if key is None:
        raise HTTPException(status_code=404, detail="Steuerschlüssel nicht gefunden.")
    return key


@router.post("/api/tax-keys/{key_id}/set-default", response_model=TaxKeyOut)
def post_set_default_tax_key(key_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    key = set_default_tax_key(db, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="Steuerschlüssel nicht gefunden.")
    return key


@router.post("/api/tax-keys/{key_id}/archive", response_model=TaxKeyOut)
def post_archive_tax_key(key_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        key = set_tax_key_archived(db, key_id, True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if key is None:
        raise HTTPException(status_code=404, detail="Steuerschlüssel nicht gefunden.")
    return key


@router.post("/api/tax-keys/{key_id}/unarchive", response_model=TaxKeyOut)
def post_unarchive_tax_key(key_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    key = set_tax_key_archived(db, key_id, False)
    if key is None:
        raise HTTPException(status_code=404, detail="Steuerschlüssel nicht gefunden.")
    return key
