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
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, has_role, require_min_role
from ..portal_postbote import STAU_TEXTE, STAU_TEXTE_ADMIN, StauVeraltet, erledigen, stau_stand
from ..schemas import PortalPostboteOut, PortalPostErledigtIn

router = APIRouter()
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))
_admin_dep = Depends(require_min_role(ROLE_ADMIN))
MODUL = "kundenportal"


def _modul(db: Session) -> None:
    if not is_module_enabled(db, MODUL):
        raise HTTPException(status_code=403, detail="Das Modul Kundenportal ist ausgeschaltet.")


def _stand(db: Session, user: AppUser) -> dict:
    grund, post_id = stau_stand(db, utc_jetzt())
    admin = has_role(user, ROLE_ADMIN)
    texte = STAU_TEXTE_ADMIN if admin else STAU_TEXTE  # seit 1.11.9: den Dienst nennt nur der Text für den Admin
    return {"stau": grund, "text": texte.get(grund) if grund else None, "post_id": post_id, "erledigen": admin and grund == "fehler"}


@router.get("/api/kundenportal/postbote", response_model=PortalPostboteOut)
def get_postbote(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Stau des Postboten: „wartet“ (ein Auftrag länger als 2 Minuten), „fehler“ (der zuletzt erledigte scheiterte, seit 1.11.9 nicht erledigt) oder
    keiner -- mit festem Text je Rolle."""
    _modul(db)
    return _stand(db, _role)


@router.post("/api/kundenportal/postbote/erledigt", response_model=PortalPostboteOut)
def post_erledigt(eingabe: PortalPostErledigtIn, db: Session = Depends(get_db, scope="function"), _admin: AppUser = _admin_dep):
    """Seit 1.11.9 (Antwort 1.11.7-1): nur der Admin schließt den gezeigten gescheiterten Versand ab -- 409, wenn der Hinweis inzwischen etwas
    anderes zeigt. Antwort: der neue Stand."""
    _modul(db)
    try:
        erledigen(db, eingabe.post_id, jetzt_=utc_jetzt(), user_id=_admin.id, user_name=_admin.display_name)
    except StauVeraltet as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _stand(db, _admin)
