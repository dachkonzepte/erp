"""Router: Aufbewahrung, Stufe 1 -- Archiv (seit 1.10.11, Stufe W1c; docs/archiv/webseite-und-kundenportal.md).

Vorschau und Archiv lesen: Büro ab buero_auftrag. Archivieren (einzeln oder gesammelt): nur Admin und Büro – Finanzen (darf_aufbewahrung(), Antwort F8).
Zurückholen: Büro ab buero_auftrag (F12: „Büro und Admin, zurückholen per Klick“). Die Logik steht in app/aufbewahrung.py.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..aufbewahrung import NichtGefunden, NichtImArchiv, StandGeaendert, archiv, archivieren, vorschau, zurueckholen
from ..database import get_db
from ..ids import Id
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, require_aufbewahrung, require_min_role
from ..schemas import AufbewahrungArchivOut, AufbewahrungErgebnisOut, AufbewahrungGesammeltIn, AufbewahrungVorschauOut, AufbewahrungZurueckOut

router = APIRouter()
_lesen = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))
Art = Literal["eingang", "anfrage", "projekt", "kunde"]


@router.get("/api/aufbewahrung", response_model=AufbewahrungVorschauOut)
def get_vorschau(db: Session = Depends(get_db, scope="function"), _role: AppUser = _lesen):
    return vorschau(db)


@router.get("/api/aufbewahrung/archiv", response_model=AufbewahrungArchivOut)
def get_archiv(db: Session = Depends(get_db, scope="function"), _role: AppUser = _lesen):
    return archiv(db)


@router.post("/api/aufbewahrung/{art}/{vorgang_id}/archivieren", response_model=AufbewahrungErgebnisOut)
def post_archivieren(art: Art, vorgang_id: Id, db: Session = Depends(get_db, scope="function"), user: AppUser = Depends(require_aufbewahrung)):
    """Einzeln bestätigt: archiviert, wenn unter den Sperren noch fällig -- sonst steht der Grund unter „uebersprungen“."""
    return archivieren(db, [(art, vorgang_id)], user.id)


@router.post("/api/aufbewahrung/archivieren", response_model=AufbewahrungErgebnisOut)
def post_gesammelt(payload: AufbewahrungGesammeltIn, db: Session = Depends(get_db, scope="function"), user: AppUser = Depends(require_aufbewahrung)):
    """Gesammelt bestätigt: genau die Liste der Vorschau (Prüfsumme „stand“) -- hat sie sich geändert, 409 und nichts archiviert."""
    try:
        return archivieren(db, [], user.id, stand=payload.stand)
    except StandGeaendert as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/api/aufbewahrung/{art}/{vorgang_id}/zurueckholen", response_model=AufbewahrungZurueckOut)
def post_zurueckholen(art: Art, vorgang_id: Id, db: Session = Depends(get_db, scope="function"), user: AppUser = _lesen):
    try:
        return zurueckholen(db, art, vorgang_id, user.id)
    except NichtGefunden as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NichtImArchiv as e:
        raise HTTPException(status_code=409, detail=str(e))
