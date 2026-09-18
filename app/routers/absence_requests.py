"""Router: absence_requests

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 4 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..absence_requests import request_to_dict as absence_request_to_dict, cancel_request as cancel_absence_request_row, create_request as create_absence_request_row, list_requests as list_absence_request_rows, review_request as review_absence_request_row
from ..database import get_db
from ..deps import require_admin
from ..models import AppUser, EmployeeAbsenceRequest
from ..permissions import ROLE_FIELD, require_min_role
from ..schemas import EmployeeAbsenceRequestCreate, EmployeeAbsenceRequestOut, EmployeeAbsenceRequestReview

from .time_tracking import _time_entry_employee_for_request

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Abwesenheitsanträge selbst (ansehen/stellen/
# zurückziehen) sind Selbstbedienung für JEDE Rolle -- jeder Mitarbeiter, auch ein Monteur,
# stellt seinen eigenen Urlaubs-/Abwesenheitsantrag, die bereits bestehende
# Eigentümerschafts-Filterung unten (employee_id == eigene ID für Nicht-Admin) sorgt dafür,
# dass niemand fremde Anträge sieht/ändert. Nur die FREIGABE (review_absence_request) bleibt
# admin-only, wie schon bisher über ihre eigene require_admin()-Prüfung.
_any_role_dep = Depends(require_min_role(ROLE_FIELD))


@router.get("/api/absence-requests", response_model=list[EmployeeAbsenceRequestOut])
def get_absence_requests(request: Request, employee_id: int | None = None, status: str | None = None, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    user=getattr(request.state,"erp_user",None)
    if user is not None and user.role != "admin":
        if user.employee_id is None:
            raise HTTPException(status_code=403,detail="Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
        employee_id=user.employee_id
    rows=list_absence_request_rows(db,employee_id=employee_id,status=status)
    return [EmployeeAbsenceRequestOut.model_validate(absence_request_to_dict(db,x)) for x in rows]


@router.post("/api/absence-requests", response_model=EmployeeAbsenceRequestOut)
def post_absence_request(payload: EmployeeAbsenceRequestCreate, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    employee_id=_time_entry_employee_for_request(request,payload.employee_id,db)
    user=getattr(request.state,"erp_user",None)
    try:
        row=create_absence_request_row(db,employee_id=employee_id,absence_type=payload.absence_type,start_date=payload.start_date,end_date=payload.end_date,notes=payload.notes,requested_by_user_id=getattr(user,"id",None))
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    return EmployeeAbsenceRequestOut.model_validate(absence_request_to_dict(db,row))


@router.post("/api/absence-requests/{request_id}/review", response_model=EmployeeAbsenceRequestOut)
def review_absence_request(request_id:int,payload:EmployeeAbsenceRequestReview,db:Session=Depends(get_db),user=Depends(require_admin("Nur Administratoren dürfen Abwesenheitsanträge freigeben oder ablehnen."))):
    try:
        row=review_absence_request_row(db,request_id,decision=payload.decision,reviewed_by_user_id=getattr(user,"id",None),review_notes=payload.review_notes)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    return EmployeeAbsenceRequestOut.model_validate(absence_request_to_dict(db,row))


@router.delete("/api/absence-requests/{request_id}")
def delete_absence_request(request_id:int,request:Request,db:Session=Depends(get_db),_role:AppUser=_any_role_dep):
    row=db.get(EmployeeAbsenceRequest,request_id)
    if row is None: raise HTTPException(status_code=404,detail="Abwesenheitsantrag wurde nicht gefunden.")
    user=getattr(request.state,"erp_user",None)
    if user is not None and user.role != "admin":
        if user.employee_id is None or row.employee_id != user.employee_id:
            raise HTTPException(status_code=403,detail="Sie dürfen diesen Abwesenheitsantrag nicht zurückziehen.")
    try: cancel_absence_request_row(db,request_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"cancelled":True}
