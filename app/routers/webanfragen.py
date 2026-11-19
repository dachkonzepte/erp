"""Router: Anfragen der Webseite (seit 1.10.1, Stufe W1a; docs/archiv/webseite-und-kundenportal.md).

Eingang lesen (Liste, eine Anfrage, ihre Dateien), Stand des Abholens und „Jetzt abholen“ -- Büro ab buero_auftrag (wie die Anfragen). Die Geschäftslogik
steht in app/webanfragen.py; hier nur Rollen und Antworten. Der Umschlag geht unverändert an die Seite (Fremddaten: die Seite setzt jeden Wert über esc()).
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..dateiauslieferung import datei_antwort
from ..ids import Id
from ..models import AppUser, WebAnfrage, WebAnfrageDatei
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import WebanfragenAbholErgebnisOut, WebanfragenStandOut, WebAnfrageDetailOut, WebAnfrageOut
from ..webanfragen import KNOPF_FRIST, KNOPF_HOECHSTENS, abholen, datei_pfad, eingang, stand, zeile_zu_dict

router = APIRouter()
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


@router.get("/api/webanfragen/stand", response_model=WebanfragenStandOut)
def get_stand(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return stand(db)


@router.get("/api/webanfragen", response_model=list[WebAnfrageOut])
def get_liste(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return [zeile_zu_dict(z) for z in eingang(db)]


@router.post("/api/webanfragen/abholen", response_model=WebanfragenAbholErgebnisOut)
def post_abholen(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Der Knopf „Jetzt abholen“: höchstens KNOPF_HOECHSTENS neue Anfragen und KNOPF_FRIST Sekunden -- den Rest holt der Timer."""
    erg = abholen(db, hoechstens=KNOPF_HOECHSTENS, frist_sekunden=KNOPF_FRIST)
    return {**erg.als_dict(), "stand": stand(db)}


def _zeile(db: Session, webanfrage_id: int) -> WebAnfrage:
    zeile = db.scalar(select(WebAnfrage).options(selectinload(WebAnfrage.dateien)).where(WebAnfrage.id == webanfrage_id))
    if zeile is None:
        raise HTTPException(status_code=404, detail="Anfrage der Webseite nicht gefunden.")
    return zeile


@router.get("/api/webanfragen/{webanfrage_id}", response_model=WebAnfrageDetailOut)
def get_eine(webanfrage_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    zeile = _zeile(db, webanfrage_id)
    try:
        umschlag = json.loads(zeile.umschlag)
    except ValueError:
        umschlag = None
    return {**zeile_zu_dict(zeile), "umschlag": umschlag if isinstance(umschlag, dict) else None,
            "dateiliste": [{"id": d.id, "name": d.name, "typ": d.typ, "groesse": d.groesse} for d in zeile.dateien]}


@router.get("/api/webanfragen/{webanfrage_id}/dateien/{datei_id}")
def get_datei(webanfrage_id: Id, datei_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    datei = db.get(WebAnfrageDatei, datei_id)
    if datei is None or datei.webanfrage_id != webanfrage_id:  # Regel 25: nur eine Datei dieser Anfrage
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.")
    try:
        pfad = datei_pfad(datei)
    except ValueError:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from None
    if not pfad.is_file():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.")
    return datei_antwort(pfad, datei.name)
