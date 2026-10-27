"""Router: absence_requests

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 4 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..absence_requests import request_to_dict as absence_request_to_dict, cancel_request as cancel_absence_request_row, create_request as create_absence_request_row, list_requests as list_absence_request_rows, review_request as review_absence_request_row
from ..meldungen import KEIN_MITARBEITER
from ..database import get_db
from ..deps import require_admin
from ..models import AppUser, EmployeeAbsenceRequest
from ..permissions import ROLE_FIELD, darf_abwesenheiten_aller, darf_antrag_zurueckziehen, require_min_role
from ..schemas import EmployeeAbsenceRequestCreate, EmployeeAbsenceRequestOut, EmployeeAbsenceRequestReview

router = APIRouter()

NUR_EIGENE_ABWESENHEIT = "Du darfst nur eigene Abwesenheiten beantragen."
NUR_WER_GESTELLT = "Zurückziehen kann einen Antrag nur, wer ihn gestellt hat."


def _antrag_fuer(request: Request, employee_id: int) -> int:
    """Seit 1.9.97 (Stufe 4, R5b, Punkt 5): für wen ein Antrag gestellt wird -- seit 1.9.101 Admin und Büro – Finanzen für jeden
    (darf_abwesenheiten_aller(); 1.9.97–1.9.100 nur der Admin), sonst nur für sich (ohne Mitarbeiter 403). Bis 1.9.96 dieselbe Regel wie das
    Buchen von Zeiten: Büro – Finanzen stellte Anträge für andere, die es danach nicht sehen konnte -- seit 1.9.101 sieht es alle."""
    user = getattr(request.state, "erp_user", None)
    if darf_abwesenheiten_aller(user):
        return employee_id
    if user.employee_id is None:
        raise HTTPException(status_code=403, detail=KEIN_MITARBEITER)
    if employee_id != user.employee_id:
        raise HTTPException(status_code=403, detail=NUR_EIGENE_ABWESENHEIT)
    return user.employee_id

def _antrag_out(db: Session, row, user) -> EmployeeAbsenceRequestOut:
    """Seit 1.9.101 mit darf_zurueckziehen (offen und von diesem Konto gestellt) -- „Meine Zeiten“ und „Zeiten“ zeigen „Zurückziehen“ danach."""
    return EmployeeAbsenceRequestOut.model_validate({**absence_request_to_dict(db, row),
                                                     "darf_zurueckziehen": row.status == "pending" and darf_antrag_zurueckziehen(user, row)})


# Seit "Rechtekonzept" (siehe CLAUDE.md): Abwesenheitsanträge selbst (ansehen/stellen/
# zurückziehen) sind Selbstbedienung für JEDE Rolle -- jeder Mitarbeiter, auch ein Monteur,
# stellt seinen eigenen Urlaubs-/Abwesenheitsantrag, die bereits bestehende
# Eigentümerschafts-Filterung unten (employee_id == eigene ID für Nicht-Admin) sorgt dafür,
# dass niemand fremde Anträge sieht/ändert. Nur die FREIGABE (review_absence_request) bleibt
# admin-only, wie schon bisher über ihre eigene require_admin()-Prüfung. Seit 1.9.101 sehen Admin und Büro – Finanzen alle Anträge und
# stellen sie auch für andere (darf_abwesenheiten_aller()); zurückziehen darf, wer den Antrag gestellt hat (darf_antrag_zurueckziehen()).
_any_role_dep = Depends(require_min_role(ROLE_FIELD))


@router.get("/api/absence-requests", response_model=list[EmployeeAbsenceRequestOut])
def get_absence_requests(request: Request, employee_id: int | None = None, status: str | None = None, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    user=getattr(request.state,"erp_user",None)
    if not darf_abwesenheiten_aller(user):  # seit 1.9.101 sehen Admin und Büro – Finanzen alle (bis 1.9.100 nur der Admin)
        if user.employee_id is None:
            raise HTTPException(status_code=403,detail=KEIN_MITARBEITER)
        employee_id=user.employee_id
    rows=list_absence_request_rows(db,employee_id=employee_id,status=status)
    return [_antrag_out(db,x,user) for x in rows]


@router.post("/api/absence-requests", response_model=EmployeeAbsenceRequestOut)
def post_absence_request(payload: EmployeeAbsenceRequestCreate, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    employee_id=_antrag_fuer(request,payload.employee_id)
    user=getattr(request.state,"erp_user",None)
    try:
        row=create_absence_request_row(db,employee_id=employee_id,absence_type=payload.absence_type,absence_category=payload.absence_category,start_date=payload.start_date,end_date=payload.end_date,notes=payload.notes,requested_by_user_id=getattr(user,"id",None))
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    return _antrag_out(db,row,user)


@router.post("/api/absence-requests/{request_id}/review", response_model=EmployeeAbsenceRequestOut)
def review_absence_request(request_id:int,payload:EmployeeAbsenceRequestReview,db:Session=Depends(get_db, scope="function"),user=Depends(require_admin("Nur Administratoren dürfen Abwesenheitsanträge freigeben oder ablehnen."))):
    try:
        row=review_absence_request_row(db,request_id,decision=payload.decision,reviewed_by_user_id=getattr(user,"id",None),review_notes=payload.review_notes)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    return EmployeeAbsenceRequestOut.model_validate(absence_request_to_dict(db,row))


@router.delete("/api/absence-requests/{request_id}")
def delete_absence_request(request_id:int,request:Request,db:Session=Depends(get_db, scope="function"),_role:AppUser=_any_role_dep):
    row=db.get(EmployeeAbsenceRequest,request_id)
    if row is None: raise HTTPException(status_code=404,detail="Abwesenheitsantrag wurde nicht gefunden.")
    user=getattr(request.state,"erp_user",None)
    # seit 1.9.101: nur, wer den Antrag gestellt hat -- auch der Admin (bis 1.9.100 jeden; sonst jeder die Anträge für sich)
    if not darf_antrag_zurueckziehen(user,row):
        raise HTTPException(status_code=403,detail=NUR_WER_GESTELLT)
    try: cancel_absence_request_row(db,request_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"cancelled":True}
