"""Router: Ausfalltag Schlechtwetter (seit 1.9.170, Lohn L1a, Punkt 5, Entscheidung Tobias E5).

Wer darf was -- hier, nicht in app/schlechtwetter.py (rollenlose Geschäftslogik):
    eintragen, gilt sofort   Admin, Büro – Finanzen, Kolonnenführer, Vorarbeiter -- für jeden gewerblichen Mitarbeiter
    beantragen               jede andere Person für sich selbst (ein offener Antrag)
    bestätigen, ablehnen     Admin, Kolonnenführer, Vorarbeiter
Der Kontext nennt der Seite nur Namen, keine Personaldaten.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..absence_requests import AbschlussGesperrt, request_to_dict
from ..database import get_db
from ..meldungen import KEIN_MITARBEITER
from ..models import AppUser, Employee
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_FINANZEN, darf_im_abschluss_aendern, has_role, require_min_role
from ..schemas import SchlechtwetterEintragen, SchlechtwetterEntscheidung
from ..schlechtwetter import (SchlechtwetterAbgelehnt, SchlechtwetterWarnung, eintragen, entscheiden, gewerbliche, ist_fuehrung, kolonnen,
                              offene_antraege)

router = APIRouter()
_any_role_dep = Depends(require_min_role(ROLE_FIELD))

NUR_FUER_DICH = "Schlechtwetter für andere tragen Kolonnenführer, Vorarbeiter, Admin und Büro – Finanzen ein – du beantragst ihn für dich."
NUR_FUEHRUNG = "Schlechtwetter bestätigen Kolonnenführer, Vorarbeiter und der Admin."


def darf_eintragen(db: Session, user: AppUser | None) -> bool:
    return user is None or has_role(user, ROLE_ADMIN, ROLE_OFFICE_FINANZEN) or ist_fuehrung(db, user.employee_id)


def darf_bestaetigen(db: Session, user: AppUser | None) -> bool:
    return user is None or has_role(user, ROLE_ADMIN) or ist_fuehrung(db, user.employee_id)


def _name(emp: Employee) -> str:
    return f"{emp.first_name} {emp.last_name}".strip()


@router.get("/api/schlechtwetter/kontext")
def get_kontext(request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Für den Dialog: darf das Konto für andere eintragen und bestätigen, welche Personen und Kolonnen, welche Anträge warten."""
    user = getattr(request.state, "erp_user", None)
    fuer_andere = darf_eintragen(db, user)
    personen = [{"id": e.id, "name": _name(e)} for e in gewerbliche(db)]
    if not fuer_andere:
        eigene = getattr(user, "employee_id", None)
        personen = [p for p in personen if p["id"] == eigene]
    bestaetigen = darf_bestaetigen(db, user)
    offen = [{"id": a.id, "employee_id": a.employee_id, "name": _name(a.employee) if a.employee else "", "tag": a.start_date}
             for a in offene_antraege(db)] if bestaetigen else []
    return {"fuer_andere": fuer_andere, "bestaetigen": bestaetigen, "personen": personen,
            "kolonnen": kolonnen(db) if fuer_andere else [], "antraege_offen": offen}


@router.post("/api/schlechtwetter")
def post_schlechtwetter(payload: SchlechtwetterEintragen, request: Request, db: Session = Depends(get_db, scope="function"),
                        _role: AppUser = _any_role_dep):
    """Ein Ausfalltag für eine oder mehrere Personen (alles oder nichts). 422 mit Liste, wenn ein Tag nicht geht; 409 mit Warnungen, wenn
    schon Zeit gebucht ist oder (seit 1.9.178) der Tag als betriebsfreier Tag eingetragen ist und „trotzdem“ fehlt."""
    user = getattr(request.state, "erp_user", None)
    gleich = darf_eintragen(db, user)
    if not gleich:
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail=KEIN_MITARBEITER)
        if set(payload.employee_ids) != {user.employee_id}:
            raise HTTPException(status_code=403, detail=NUR_FUER_DICH)
    try:
        antraege = eintragen(db, employee_ids=payload.employee_ids, tag=payload.tag, notes=payload.notes, gleich_genehmigt=gleich,
                             user_id=getattr(user, "id", None), trotzdem=payload.trotzdem, abschluss_erlaubt=darf_im_abschluss_aendern(user))
    except AbschlussGesperrt as exc:  # seit 1.9.309: wie eine Zeitbuchung im abgeschlossenen Zeitraum
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SchlechtwetterWarnung as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc), "warnungen": jsonable_encoder(exc.warnungen)})
    except SchlechtwetterAbgelehnt as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "liste": exc.liste})
    return {"genehmigt": gleich, "antraege": jsonable_encoder([request_to_dict(db, a) for a in antraege])}


@router.post("/api/schlechtwetter/{antrag_id}/entscheiden")
def post_entscheiden(antrag_id: int, payload: SchlechtwetterEntscheidung, request: Request, db: Session = Depends(get_db, scope="function"),
                     _role: AppUser = _any_role_dep):
    user = getattr(request.state, "erp_user", None)
    if not darf_bestaetigen(db, user):
        raise HTTPException(status_code=403, detail=NUR_FUEHRUNG)
    try:
        row = entscheiden(db, antrag_id, decision=payload.decision, user_id=getattr(user, "id", None), notes=payload.notes,
                          abschluss_erlaubt=darf_im_abschluss_aendern(user))
    except AbschlussGesperrt as exc:  # seit 1.9.309
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return jsonable_encoder(request_to_dict(db, row))
