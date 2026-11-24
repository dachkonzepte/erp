"""Router: das Kundenportal im ERP (seit 1.11.7, Stufe P1c; docs/archiv/webseite-und-kundenportal.md) -- heute der Stand des Postboten für den Hinweis
auf „Start“; die Karte „Kundenportal“ in der Kundenakte folgt mit P1d. Rollen ab Büro – Auftrag (P1-4), die Monteurin nie. Ist das Modul
„Kundenportal“ aus, antwortet jeder Weg 403 -- wie jedes Modul, auch für den Admin (die Seite fragt dann gar nicht).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..berlin_time import utc_jetzt
from ..database import get_db
from ..models import AppUser
from ..modules import is_module_enabled
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..portal_postbote import STAU_TEXTE, stau
from ..schemas import PortalPostboteOut

router = APIRouter()
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))
MODUL = "kundenportal"


def _modul(db: Session) -> None:
    if not is_module_enabled(db, MODUL):
        raise HTTPException(status_code=403, detail="Das Modul Kundenportal ist ausgeschaltet.")


@router.get("/api/kundenportal/postbote", response_model=PortalPostboteOut)
def get_postbote(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Stau des Postboten: „wartet“ (ein Auftrag länger als 2 Minuten), „fehler“ (der zuletzt erledigte scheiterte) oder keiner -- mit festem Text."""
    _modul(db)
    grund = stau(db, utc_jetzt())
    return {"stau": grund, "text": STAU_TEXTE.get(grund) if grund else None}
