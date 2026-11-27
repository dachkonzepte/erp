"""Router: das Kundenportal im ERP (seit 1.11.7, Stufe P1c; docs/archiv/webseite-und-kundenportal.md) -- der Stand des Postboten für den Hinweis auf
„Start“ (seit 1.11.9 mit „Erledigt“ für den Admin) und seit 1.11.10 (P1d) die Karte „Kundenportal“ der Kundenakte (app/kundenportal.py). Rollen ab
Büro – Auftrag (P1-4), die Monteurin nie. Ist das Modul „Kundenportal“ aus, antwortet jeder Weg 403 -- wie jedes Modul, auch für den Admin (die Seiten
fragen dann gar nicht). Ein Kunde im Archiv: jede schreibende Anfrage an seiner Karte endet vor dem Endpunkt mit 409 (archiv_vorab()) -- seit 1.11.13
außer Sperren (Festlegung 1.11.0: es nimmt nur Zugang weg; tests/test_v793_archivschutz.py::OHNE_VORAB).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import kundenportal as kp
from ..archivschutz import archiv_vorab
from ..email_dispatch import DispatchConflict
from ..ids import Id

from ..berlin_time import utc_jetzt
from ..database import get_db
from ..models import AppUser, Customer
from ..modules import is_module_enabled
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, has_role, require_min_role
from ..portal_postbote import STAU_TEXTE, STAU_TEXTE_ADMIN, StauVeraltet, erledigen, stau_stand
from ..schemas import (
    KundenportalEmailIn, KundenportalLinkIn, KundenportalOut, KundenportalProtokollOut, KundenportalSchalterIn, KundenportalSperrenIn,
    PortalPostboteOut, PortalPostErledigtIn,
)

router = APIRouter()
# seit 1.11.10: Kunde im Archiv -- jede schreibende Anfrage an seiner Karte endet vor dem Endpunkt mit 409; seit 1.11.13 je Route, damit Sperren auch im
# Archiv geht (Festlegung 1.11.0, Antwort des Betriebs 24.11.2026)
_nicht_im_archiv = [archiv_vorab(customer_id="customers")]
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
    return {"stau": grund, "text": texte.get(grund) if grund else None, "post_id": post_id, "erledigen": admin and grund == "fehler",
            "pflicht": kp.PFLICHT_HINWEIS if kp.pflicht_grund(db) else None}  # seit 1.11.47


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

# --- Karte „Kundenportal“ in der Kundenakte (seit 1.11.10, Stufe P1d) -------------------------------------------------------------------------------
# Alle Wege nennen nur den Kunden im Pfad; den Zugang findet der Server über den Kunden (Regel 25: keine ID eines Zugangs aus der Anfrage).


def _kunde(db: Session, customer_id: int) -> Customer:
    kunde = db.get(Customer, customer_id)
    if kunde is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    return kunde


def _antwort(db: Session, kunde: Customer) -> dict:
    db.refresh(kunde)
    return kp.stand(db, kunde, utc_jetzt())


def _ausfuehren(aktion):
    try:
        return aktion()
    except kp.ZugangFehlt as e:
        raise HTTPException(status_code=404, detail=str(e))
    except kp.PortalNicht as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DispatchConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/customers/{customer_id}/portal", response_model=KundenportalOut)
def get_portal(customer_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _modul(db)
    return kp.stand(db, _kunde(db, customer_id), utc_jetzt())


@router.post("/api/customers/{customer_id}/portal/schalter", response_model=KundenportalOut, dependencies=_nicht_im_archiv)
def post_schalter(customer_id: Id, eingabe: KundenportalSchalterIn, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: kp.schalten(db, kunde, eingabe.an, utc_jetzt()))
    return _antwort(db, kunde)


@router.post("/api/customers/{customer_id}/portal/zugang", response_model=KundenportalOut, dependencies=_nicht_im_archiv)
def post_zugang(customer_id: Id, eingabe: KundenportalEmailIn, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: kp.zugang_anlegen(db, kunde, eingabe.email, utc_jetzt(), user_id=_role.id, user_name=_role.display_name))
    return _antwort(db, kunde)


@router.post("/api/customers/{customer_id}/portal/link", response_model=KundenportalOut, dependencies=_nicht_im_archiv)
def post_link(customer_id: Id, eingabe: KundenportalLinkIn, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Link senden (abschließend): neuer Link, Mail über Microsoft 365 ohne „Gesendete Elemente“. 400 bei einem Versandfehler (der neue Link gilt
    trotzdem, die Karte zeigt „Versand gescheitert“), 409 im falschen Zustand oder bei einem laufenden Versand."""
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: kp.link_senden(db, kunde, eingabe.email, eingabe.dispatch_key, utc_jetzt(), user_id=_role.id, user_name=_role.display_name))
    return _antwort(db, kunde)


@router.post("/api/customers/{customer_id}/portal/sperren", response_model=KundenportalOut)
def post_sperren(customer_id: Id, eingabe: KundenportalSperrenIn, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.11.13 auch für einen Kunden im Archiv (ohne archiv_vorab()): Sperren nimmt nur Zugang weg."""
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: kp.sperren(db, kunde, eingabe.grund, utc_jetzt(), user_id=_role.id, user_name=_role.display_name))
    return _antwort(db, kunde)


@router.post("/api/customers/{customer_id}/portal/entsperren", response_model=KundenportalOut, dependencies=_nicht_im_archiv)
def post_entsperren(customer_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: kp.entsperren(db, kunde))
    return _antwort(db, kunde)


@router.post("/api/customers/{customer_id}/portal/verlaengern", response_model=KundenportalOut, dependencies=_nicht_im_archiv)
def post_verlaengern(customer_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: kp.verlaengern(db, kunde, utc_jetzt()))
    return _antwort(db, kunde)


@router.get("/api/customers/{customer_id}/portal/protokoll", response_model=KundenportalProtokollOut)
def get_protokoll(customer_id: Id, seite: int = Query(1, ge=1, le=1000), db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _modul(db)
    return kp.protokoll(db, _kunde(db, customer_id), seite)
