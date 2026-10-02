"""Router: Adressbuch (seit 1.8.37, Stufe 2b, Runde 2b-2).

Nur Büro (buero_auftrag und höher) -- ein Monteur sieht Beteiligte und ihre Kontaktdaten nicht
(tests/test_v326_monteur_datengrenze.py ruft jeden GET als Monteur auf: 403). Geschäftslogik in
app/contacts.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..contacts import (
    ContactInUseError, contact_detail, contact_to_dict, create_contact, delete_contact, list_contacts,
    set_contact_archived, update_contact, usage_counts,
)
from ..database import get_db
from ..models import AppUser, Contact
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import ContactCreate, ContactDetailOut, ContactOut, ContactUpdate

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


def _contact_or_404(db: Session, contact_id: int) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden.")
    return contact


def _out(db: Session, contact: Contact) -> dict:
    return contact_to_dict(contact, usage_counts(db, [contact.id]).get(contact.id, 0))


@router.get("/api/contacts", response_model=list[ContactOut])
def get_contacts(
    search: str | None = None, include_archived: bool = False, limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    return list_contacts(db, search=search, include_archived=include_archived, limit=limit)


@router.get("/api/contacts/{contact_id}", response_model=ContactDetailOut)
def get_contact(contact_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return contact_detail(db, _contact_or_404(db, contact_id))


@router.post("/api/contacts", response_model=ContactOut)
def post_contact(payload: ContactCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        contact = create_contact(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(db, contact)


@router.put("/api/contacts/{contact_id}", response_model=ContactOut)
def put_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    contact = _contact_or_404(db, contact_id)
    try:
        update_contact(db, contact, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(db, contact)


@router.post("/api/contacts/{contact_id}/archive", response_model=ContactOut)
def archive_contact(contact_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return _out(db, set_contact_archived(db, _contact_or_404(db, contact_id), True))


@router.post("/api/contacts/{contact_id}/unarchive", response_model=ContactOut)
def unarchive_contact(contact_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return _out(db, set_contact_archived(db, _contact_or_404(db, contact_id), False))


@router.delete("/api/contacts/{contact_id}")
def remove_contact(contact_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        delete_contact(db, _contact_or_404(db, contact_id))
    except ContactInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}
