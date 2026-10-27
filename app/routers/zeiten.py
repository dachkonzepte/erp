"""Router: die Daten der Büroseite „Zeiten“ (seit 1.9.95, Stufe 4, R5b).

Nur lesen. Prüfen und Buchungen ab Büro – Auftrag (es liest die Zeiten aller, seit 1.9.89), Monat & Lohn nur mit den Lohndaten (Admin und
Büro – Finanzen, require_lohndaten). Geschrieben wird über die bestehenden Endpunkte (Zeiten, Pausen, Ende nachtragen, Abschluss, Anträge),
die ihre Rechte selbst prüfen; was das Konto davon darf, steht hier je Antwort unter „rechte“ und je Zeit unter „darf_…“ -- dieselben
Regeln wie dort (app/permissions.py), die Seite bietet nur das an."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..absence_requests import list_requests, request_to_dict
from ..berlin_time import berlin_today
from ..database import get_db
from ..meldungen import KEIN_MITARBEITER
from ..models import AppUser, Employee
from ..option_settings import get_option_group
from ..permissions import (ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, darf_abwesenheiten_aller, darf_antrag_zurueckziehen, darf_lohndaten, darf_zeit_buchen,
                           darf_zeit_fuer_andere_buchen, require_lohndaten, require_min_role)
from ..time_backoffice import locked_until
from ..zeiten import arbeitstage, buchungen, monat, monat_lesen, pruefen

router = APIRouter()

_buero_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Die Seite „Zeiten“ ist nur für das Büro."))
_lohn_dep = Depends(require_lohndaten)


def _rechte(user: AppUser) -> dict:
    return {"zeit_buchen": darf_zeit_buchen(user), "zeit_fuer_andere": darf_zeit_fuer_andere_buchen(user), "lohndaten": darf_lohndaten(user),
            "antraege_entscheiden": user.role == ROLE_ADMIN, "admin": user.role == ROLE_ADMIN}


def _monat(text: str | None):
    try:
        return monat_lesen(text, berlin_today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _darf_aendern(user: AppUser, employee_id: int, work_date, lock) -> bool:
    """Wie die Endpunkte der Zeiten: buchen darf das Konto (darf_zeit_buchen()), die Zeit ist die eigene oder es bucht für andere
    (app/routers/time_tracking.py::_time_entry_can_edit()), im abgeschlossenen Zeitraum nur der Admin (_require_open_period())."""
    if not darf_zeit_buchen(user):
        return False
    if not (darf_zeit_fuer_andere_buchen(user) or (user.employee_id is not None and user.employee_id == employee_id)):
        return False
    return user.role == ROLE_ADMIN or lock is None or work_date > lock


def _sichtbare_antraege(db: Session, user: AppUser, status: str | None):
    """Die Anträge, die das Konto sieht -- wie GET /api/absence-requests: seit 1.9.101 Admin und Büro – Finanzen alle (darf_abwesenheiten_aller(),
    bis 1.9.100 nur der Admin), sonst nur die eigenen, ohne Mitarbeiter keine."""
    if darf_abwesenheiten_aller(user):
        return list_requests(db, status=status)
    if user.employee_id is not None:
        return list_requests(db, employee_id=user.employee_id, status=status)
    return []


def _antraege(db: Session, user: AppUser) -> list[dict]:
    """Die offenen Anträge, die das Konto sieht (_sichtbare_antraege()), mit Arbeitstagen."""
    return [{**request_to_dict(db, r), "arbeitstage": arbeitstage(r.start_date, r.end_date)} for r in _sichtbare_antraege(db, user, "pending")]


def _anzahl(n: int, eins: str, mehr: str) -> str:
    return f"{n} {eins if n == 1 else mehr}"


@router.get("/api/zeiten/pruefen")
def zeiten_pruefen(request: Request, db: Session = Depends(get_db, scope="function"), user: AppUser = _buero_dep):
    """„Prüfen“: Zeiten von früher (je mit darf_schliessen), Tage mit unpassender Pause (je mit darf_buchen), offene Anträge, der Monat mit
    Stunden je Mitarbeiter und „Vor dem Abschluss“; dazu die Zahlen an den Reitern."""
    daten = pruefen(db, berlin_today())
    lock = locked_until(db)
    for z in daten["offene_zeiten"]:
        z["darf_schliessen"] = _darf_aendern(user, z["employee_id"], z["tag"], lock)
    for t in daten["pausen"]:
        t["darf_buchen"] = _darf_aendern(user, t["employee_id"], t["tag"], lock)
    daten["antraege"] = _antraege(db, user)
    # seit 1.9.101: „Vor dem Abschluss“ nennt die offenen Anträge, die das Konto sieht; „Anträge entschieden“ nur, wenn keiner offen ist
    # (auch keiner, den das Konto nicht sieht -- Büro – Auftrag sieht nur die eigenen)
    if daten["antraege"]:
        daten["vor_dem_abschluss"].append({"art": "antraege", "text": _anzahl(len(daten["antraege"]), "Antrag offen", "Anträge offen")})
    daten["antraege_entschieden"] = not list_requests(db, status="pending")
    daten["rechte"] = _rechte(user)
    daten["zahlen"] = {"pruefen": len(daten["offene_zeiten"]) + len(daten["pausen"]), "abwesenheiten": len(daten["antraege"])}
    return daten


@router.get("/api/zeiten/buchungen")
def zeiten_buchungen(request: Request, monat_: str | None = Query(None, alias="monat"), mitarbeiter: int | None = None, auftrag: int | None = None,
                     zeitart: str | None = Query(None, max_length=40), db: Session = Depends(get_db, scope="function"), user: AppUser = _buero_dep):
    """„Buchungen“ eines Monats nach den Filtern, mit der „Summe der Auswahl“; je Buchung darf_aendern (Ändern und Löschen)."""
    daten = buchungen(db, _monat(monat_), employee_id=mitarbeiter, order_id=auftrag, entry_type=zeitart or None)
    lock = locked_until(db)
    for e in daten["eintraege"]:
        e["darf_aendern"] = e["status"] == "booked" and _darf_aendern(user, e["employee_id"], e["work_date"], lock)
        e["darf_schliessen"] = e["laeuft_seit_frueher"] and _darf_aendern(user, e["employee_id"], e["work_date"], lock)
    daten["rechte"] = _rechte(user)
    return daten


NUR_EIGENE_ANTRAEGE = "Hier stehen nur deine eigenen Anträge – die Anträge aller sehen Admin und Büro – Finanzen."
ANTRAG_STATUS = ("pending", "approved", "rejected", "cancelled")


@router.get("/api/zeiten/abwesenheiten")
def zeiten_abwesenheiten(status: str | None = Query(None, max_length=20), db: Session = Depends(get_db, scope="function"),
                         user: AppUser = _buero_dep):
    """Seit 1.9.97 (Stufe 4, R5b, Punkt 5): „Abwesenheiten“ -- seit 1.9.101 (Nachrunde, Punkt 1) sehen Admin und Büro – Finanzen alle Anträge
    und stellen sie auch für andere, Büro – Auftrag nur die eigenen (ohne Mitarbeiter keine, mit Hinweis); je Antrag Arbeitstage,
    darf_entscheiden (nur der Admin, offen), darf_zurueckziehen (offen und von diesem Konto gestellt -- darf_antrag_zurueckziehen()).
    1.9.97–1.9.100 sah und beantragte für andere nur der Admin."""
    if status and status not in ANTRAG_STATUS:
        raise HTTPException(status_code=422, detail="Unbekannter Status.")
    admin = user.role == ROLE_ADMIN
    aller = darf_abwesenheiten_aller(user)
    rows = _sichtbare_antraege(db, user, status or None)
    arten = get_option_group(db, "absence_types")
    # offene Anträge, die das Konto sieht -- dieselbe Zahl wie am Reiter (GET /api/zeiten/pruefen)
    offen = len(_sichtbare_antraege(db, user, "pending"))
    return {
        "antraege": [{**request_to_dict(db, r), "arbeitstage": arbeitstage(r.start_date, r.end_date),
                      "darf_entscheiden": admin and r.status == "pending",
                      "darf_zurueckziehen": r.status == "pending" and darf_antrag_zurueckziehen(user, r)}
                     for r in rows],
        "hinweis": None if aller else (NUR_EIGENE_ANTRAEGE if user.employee_id is not None else KEIN_MITARBEITER),
        "darf_beantragen": aller or user.employee_id is not None, "fuer_andere": aller, "eigener_mitarbeiter": user.employee_id,
        "mitarbeiter": [{"id": e.id, "name": f"{e.first_name} {e.last_name}".strip(), "employee_number": e.employee_number}
                        for e in db.query(Employee).filter(Employee.active == True).order_by(Employee.last_name, Employee.first_name)]  # noqa: E712
        if aller else [],
        "arten": [{"value": o.value, "label": o.label, "active": o.active} for o in sorted(arten.options if arten else [],
                                                                                         key=lambda o: (o.sort_order, o.id))],
        "offen": offen,
    }


@router.get("/api/zeiten/monat")
def zeiten_monat(monat_: str | None = Query(None, alias="monat"), db: Session = Depends(get_db, scope="function"), user: AppUser = _lohn_dep):
    """„Monat & Lohn“ -- nur mit den Lohndaten (Admin und Büro – Finanzen)."""
    return {**monat(db, _monat(monat_)), "rechte": _rechte(user)}
