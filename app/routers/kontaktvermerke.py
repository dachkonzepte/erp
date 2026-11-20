"""Router: Kontakt vermerken an Anfrage, Projekt und Kunde (seit 1.10.10, Stufe W1c; docs/archiv/webseite-und-kundenportal.md).

Lesen und Vermerken: Büro ab buero_auftrag (wie die Anfragen); die Monteurin an keinem Weg. Nur Tag und Weg, nie ein Inhalt (app/kontaktvermerke.py).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..ids import Id
from ..kontaktvermerke import BezugFehlt, vermerke, vermerken
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import KontaktvermerkIn, KontaktvermerkOut

router = APIRouter()
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


def _lesen(db: Session, bezug: str, bezug_id: int) -> list[dict]:
    try:
        return vermerke(db, bezug, bezug_id)
    except BezugFehlt as e:
        raise HTTPException(status_code=404, detail=str(e))


def _vermerken(db: Session, bezug: str, bezug_id: int, payload: KontaktvermerkIn, user: AppUser) -> list[dict]:
    try:
        return vermerken(db, bezug, bezug_id, payload.kontakt_am, payload.weg, user.id)
    except BezugFehlt as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/inquiries/{inquiry_id}/kontakte", response_model=list[KontaktvermerkOut])
def get_kontakte_anfrage(inquiry_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return _lesen(db, "anfrage", inquiry_id)


@router.post("/api/inquiries/{inquiry_id}/kontakte", response_model=list[KontaktvermerkOut])
def post_kontakt_anfrage(inquiry_id: Id, payload: KontaktvermerkIn, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    return _vermerken(db, "anfrage", inquiry_id, payload, user)


@router.get("/api/projects/{project_id}/kontakte", response_model=list[KontaktvermerkOut])
def get_kontakte_projekt(project_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return _lesen(db, "projekt", project_id)


@router.post("/api/projects/{project_id}/kontakte", response_model=list[KontaktvermerkOut])
def post_kontakt_projekt(project_id: Id, payload: KontaktvermerkIn, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    return _vermerken(db, "projekt", project_id, payload, user)


@router.get("/api/customers/{customer_id}/kontakte", response_model=list[KontaktvermerkOut])
def get_kontakte_kunde(customer_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return _lesen(db, "kunde", customer_id)


@router.post("/api/customers/{customer_id}/kontakte", response_model=list[KontaktvermerkOut])
def post_kontakt_kunde(customer_id: Id, payload: KontaktvermerkIn, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    return _vermerken(db, "kunde", customer_id, payload, user)
