"""Router: Freigaben der Unterlagen fürs Kundenportal im ERP (seit 1.11.36, Stufe P2c; app/portal_freigaben.py).

Rollen ab Büro – Auftrag (Entscheidung P2-6), die Monteurin nie. Ist das Modul „Kundenportal“ aus, antwortet jeder Weg 403 -- wie die Karte „Kundenportal“
(app/routers/kundenportal.py). Ein Kunde im Archiv: Freigeben und „erneut versuchen“ enden vor dem Endpunkt mit 409 (archiv_vorab()); Zurücknehmen geht
auch dort (wie Sperren -- es nimmt nur weg; tests/test_v793_archivschutz.py::OHNE_VORAB). Alle Wege an einer Freigabe nennen den Kunden im Pfad; die
Freigabe muss zu ihm gehören (Regel 25), eine Unterlage nur, wenn ihre Kette heute zu ihm führt -- sonst außen wie unbekannt (404).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import portal_freigaben as pf
from ..archivschutz import archiv_vorab
from ..database import get_db
from ..ids import Id
from ..models import AppUser, Customer
from ..modules import is_module_enabled
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import FREIGABE_QUELLE, PortalFreigabeIn, PortalFreigabenOut, PortalFreigabeZuruecknehmenIn, PortalUnterlageOut

router = APIRouter()
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))
_nicht_im_archiv = [archiv_vorab(customer_id="customers")]
MODUL = "kundenportal"
HOECHSTENS_ABFRAGE = 500  # Unterlagen je Abfrage „Im Portal zeigen“


def _modul(db: Session) -> None:
    if not is_module_enabled(db, MODUL):
        raise HTTPException(status_code=403, detail="Das Modul Kundenportal ist ausgeschaltet.")


def _kunde(db: Session, customer_id: int) -> Customer:
    kunde = db.get(Customer, customer_id)
    if kunde is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    return kunde


def _ausfuehren(aktion):
    try:
        return aktion()
    except pf.UnterlageFehlt as e:
        raise HTTPException(status_code=404, detail=str(e))
    except pf.FreigabeNicht as e:
        raise HTTPException(status_code=409, detail=str(e))


def _stand(db: Session, kunde: Customer) -> dict:
    db.refresh(kunde)
    return pf.stand(db, kunde)


@router.get("/api/customers/{customer_id}/portal/freigaben", response_model=PortalFreigabenOut)
def get_freigaben(customer_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _modul(db)
    return pf.stand(db, _kunde(db, customer_id))


@router.post("/api/customers/{customer_id}/portal/freigaben", response_model=PortalFreigabenOut, dependencies=_nicht_im_archiv)
def post_freigeben(customer_id: Id, eingabe: PortalFreigabeIn, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Eine oder mehrere Unterlagen einer Quelle freigeben (abschließend): 404, wenn eine nicht zum Kunden führt; 409 mit Grund, wenn eine nicht gilt, kein
    PDF oder Bild ist, zu groß ist oder noch bei einem anderen Kunden freigegeben ist -- dann entsteht keine."""
    _modul(db)
    kunde = _kunde(db, customer_id)
    erg = _ausfuehren(lambda: pf.freigeben(db, kunde.id, eingabe.quelle, eingabe.quelle_ids, eingabe.titel, user_id=_role.id,
                                           user_name=_role.display_name))
    return {**_stand(db, kunde), "neu": erg.neu, "schon": erg.schon}


@router.post("/api/customers/{customer_id}/portal/freigaben/{freigabe_id}/zuruecknehmen", response_model=PortalFreigabenOut)
def post_zuruecknehmen(customer_id: Id, freigabe_id: Id, eingabe: PortalFreigabeZuruecknehmenIn, db: Session = Depends(get_db, scope="function"),
                       _role: AppUser = _role_dep):
    """Auch für einen Kunden im Archiv (ohne archiv_vorab()): Zurücknehmen nimmt nur weg."""
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: pf.zuruecknehmen(db, kunde.id, freigabe_id, eingabe.grund, user_id=_role.id, user_name=_role.display_name))
    return _stand(db, kunde)


@router.post("/api/customers/{customer_id}/portal/freigaben/{freigabe_id}/erneut", response_model=PortalFreigabenOut, dependencies=_nicht_im_archiv)
def post_erneut(customer_id: Id, freigabe_id: Id, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Eine gescheiterte Kopie noch einmal versuchen (der Postbote tut es von selbst nicht, Festlegung 1.11.33-5)."""
    _modul(db)
    kunde = _kunde(db, customer_id)
    _ausfuehren(lambda: pf.erneut(db, kunde.id, freigabe_id))
    return _stand(db, kunde)


@router.get("/api/portal-freigaben/unterlagen", response_model=list[PortalUnterlageOut])
def get_unterlagen(quelle: FREIGABE_QUELLE, quelle_ids: list[Id] = Query(default=[]), db: Session = Depends(get_db, scope="function"),
                   _role: AppUser = _role_dep):
    """Für „Im Portal zeigen“ an einer Datei: Kunde der Kette, freigebbar oder warum nicht, Vorschlag für den Titel, bestehende Freigabe. Liest nur."""
    _modul(db)
    if len(quelle_ids) > HOECHSTENS_ABFRAGE:
        raise HTTPException(status_code=422, detail=f"Höchstens {HOECHSTENS_ABFRAGE} Unterlagen je Abfrage.")
    return pf.unterlagen(db, quelle, quelle_ids)
