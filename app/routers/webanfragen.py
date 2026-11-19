"""Router: Anfragen der Webseite (seit 1.10.1, Stufe W1a; docs/archiv/webseite-und-kundenportal.md).

Eingang lesen (Liste, eine Anfrage, ihre Dateien), Stand des Abholens und „Jetzt abholen“ -- Büro ab buero_auftrag (wie die Anfragen). Die Geschäftslogik
steht in app/webanfragen.py; hier nur Rollen und Antworten. Der Umschlag geht unverändert an die Seite (Fremddaten: die Seite setzt jeden Wert über esc()).
Seit 1.10.4 (Stufe W1b): Ansichten Eingang, Prüfliste, Erledigt; Verwerfen, In den Eingang, Zurückholen -- danach die Meldung an den Empfangsdienst,
wenn gerade kein Lauf abholt (sonst meldet der Lauf).
"""

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..dateiauslieferung import datei_antwort
from ..ids import Id
from ..models import AppUser, WebAnfrage, WebAnfrageDatei
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import WebanfragenAbholErgebnisOut, WebanfragenStandOut, WebAnfrageDetailOut, WebAnfrageOut, WebAnfrageVerwerfenIn
from ..webanfrage_angaben import abschnitte, nachricht_wiederholt
from ..webanfragen import (EINGANG_MAX, KNOPF_FRIST, KNOPF_HOECHSTENS, VERWERFEN_GRUENDE, SchonErledigt, abholen, datei_pfad, eingang, in_den_eingang,
                           nachmelden, stand, verwerfen, zeile_zu_dict, zurueckholen)

router = APIRouter()
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


@router.get("/api/webanfragen/stand", response_model=WebanfragenStandOut)
def get_stand(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return stand(db)


@router.get("/api/webanfragen", response_model=list[WebAnfrageOut])
def get_liste(anzahl: int = Query(default=EINGANG_MAX, ge=1, le=EINGANG_MAX),
              ansicht: Literal["eingang", "pruefliste", "erledigt"] = Query(default="eingang"), db: Session = Depends(get_db, scope="function"),
              _role: AppUser = _role_dep):
    """Die neuesten Anfragen des Eingangs; anzahl seit 1.10.2 (die Startseite nimmt fünf), ansicht seit 1.10.4."""
    return [zeile_zu_dict(z) for z in eingang(db, anzahl, ansicht)]


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


def _name(db: Session, user_id: int | None) -> str | None:
    konto = db.get(AppUser, user_id) if user_id is not None else None
    return (konto.display_name or konto.username) if konto is not None else None


@router.get("/api/webanfragen/{webanfrage_id}", response_model=WebAnfrageDetailOut)
def get_eine(webanfrage_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return _detail(db, webanfrage_id)


def _detail(db: Session, webanfrage_id: int) -> dict:
    zeile = _zeile(db, webanfrage_id)
    try:
        umschlag = json.loads(zeile.umschlag)
    except ValueError:
        umschlag = None
    umschlag = umschlag if isinstance(umschlag, dict) else None
    return {**zeile_zu_dict(zeile), "umschlag": umschlag,
            "dateiliste": [{"id": d.id, "name": d.name, "typ": d.typ, "groesse": d.groesse} for d in zeile.dateien],
            "abschnitte": abschnitte(zeile.art, umschlag), "nachricht_wiederholt": nachricht_wiederholt(zeile.art, umschlag),
            "erledigt_von_name": _name(db, zeile.erledigt_von_user_id), "geprueft_am": zeile.geprueft_am,
            "geprueft_von_name": _name(db, zeile.geprueft_von_user_id), "verwerfen_gruende": VERWERFEN_GRUENDE}


def _aktion(db: Session, webanfrage_id: int, ausfuehren, melden: bool) -> dict:
    """Eine Aktion des Büros (seit 1.10.4): 404 unbekannt, 409 nicht (mehr) in dem Stand; danach melden, wenn gerade kein Lauf abholt."""
    try:
        ausfuehren()
    except LookupError:
        raise HTTPException(status_code=404, detail="Anfrage der Webseite nicht gefunden.") from None
    except SchonErledigt:
        raise HTTPException(status_code=409, detail="Diese Anfrage ist nicht mehr in diesem Stand – bitte die Seite neu laden.") from None
    if melden:
        nachmelden(db, webanfrage_id)
    return _detail(db, webanfrage_id)


@router.post("/api/webanfragen/{webanfrage_id}/verwerfen", response_model=WebAnfrageDetailOut)
def post_verwerfen(webanfrage_id: Id, payload: WebAnfrageVerwerfenIn, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    """Verwerfen mit festem Grund; der Empfangsdienst bekommt „verworfen“ (F2)."""
    return _aktion(db, webanfrage_id, lambda: verwerfen(db, webanfrage_id, payload.grund, user.id), melden=True)


@router.post("/api/webanfragen/{webanfrage_id}/eingang", response_model=WebAnfrageDetailOut)
def post_in_den_eingang(webanfrage_id: Id, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    """Aus der Prüfliste in den Eingang (kein Spam bzw. geprüft)."""
    return _aktion(db, webanfrage_id, lambda: in_den_eingang(db, webanfrage_id, user.id), melden=False)


@router.post("/api/webanfragen/{webanfrage_id}/zurueckholen", response_model=WebAnfrageDetailOut)
def post_zurueckholen(webanfrage_id: Id, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    """Eine verworfene Anfrage zurück in den Eingang; der Empfangsdienst bekommt wieder eingang-<ID>."""
    return _aktion(db, webanfrage_id, lambda: zurueckholen(db, webanfrage_id, user.id), melden=True)


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
