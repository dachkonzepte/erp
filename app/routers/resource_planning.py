"""Router: resource_planning

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 15 Endpunkt(e) und 4 interne Hilfsfunktion(en), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import AppUser, Employee, OperationalResource, Supplier, Team, TeamEmployee, TeamResource, WorkPreparationDeliveryNote, WorkPreparationMaterialSupplier, WorkPreparationTeamAssignment, WorkPreparationTeamResource
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..schemas import OperationalResourceCreate, OperationalResourceOut, OperationalResourceUpdate, SupplierCreate, SupplierOut, SupplierUpdate, TeamCreate, TeamOut, TeamUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Teams/Ressourcen/Lieferanten sind Stammdaten-
# Verwaltung, Büro-/Admin-Bereich -- geprüft, kein Endpunkt dieser Datei wird von einer
# Monteur-Vorlage aufgerufen.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))

def _supplier_dict(x: Supplier):
    return {k: getattr(x, k) for k in (
        "id","supplier_number","name","contact_person","street","postal_code","city","country",
        "phone","email","website","customer_number_at_supplier","notes","active"
    )}


def _resource_dict(x: OperationalResource):
    return {k: getattr(x, k) for k in (
        "id","resource_number","resource_type","name","manufacturer","model","identifier","notes","active"
    )}


def _team_dict(db: Session, team: Team):
    team = db.scalar(
        select(Team).options(
            selectinload(Team.employees).selectinload(TeamEmployee.employee),
            selectinload(Team.resources).selectinload(TeamResource.resource),
        ).where(Team.id == team.id)
    ) or team
    return {
        "id": team.id, "team_number": team.team_number, "name": team.name,
        "description": team.description, "active": team.active,
        "employees": [{
            "employee_id": r.employee_id,
            "employee_name": f"{r.employee.first_name} {r.employee.last_name}".strip() if r.employee else f"#{r.employee_id}",
            "role": r.role,
        } for r in team.employees],
        "resources": [{
            "resource_id": r.resource_id,
            "resource_name": r.resource.name if r.resource else f"#{r.resource_id}",
            "resource_type": r.resource.resource_type if r.resource else "Ressource",
            "role": r.role,
        } for r in team.resources],
    }


def _apply_team_payload(db:Session,team:Team,payload:TeamCreate|TeamUpdate):
    team.team_number=payload.team_number; team.name=payload.name; team.description=payload.description; team.active=payload.active
    for x in list(team.employees): db.delete(x)
    for x in list(team.resources): db.delete(x)
    db.flush()
    seen=set()
    for x in payload.employees:
        if x.employee_id in seen: continue
        e=db.get(Employee,x.employee_id)
        if e is None: raise HTTPException(status_code=422,detail=f"Mitarbeiter #{x.employee_id} wurde nicht gefunden.")
        db.add(TeamEmployee(team_id=team.id,employee_id=x.employee_id,role=x.role)); seen.add(x.employee_id)
    seen=set()
    for x in payload.resources:
        if x.resource_id in seen: continue
        r=db.get(OperationalResource,x.resource_id)
        if r is None: raise HTTPException(status_code=422,detail=f"Ressource #{x.resource_id} wurde nicht gefunden.")
        db.add(TeamResource(team_id=team.id,resource_id=x.resource_id,role=x.role)); seen.add(x.resource_id)


@router.get("/api/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return [SupplierOut.model_validate(_supplier_dict(x)) for x in db.scalars(select(Supplier).order_by(Supplier.name)).all()]


@router.get("/api/suppliers/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    x=db.get(Supplier,supplier_id)
    if x is None: raise HTTPException(status_code=404, detail="Lieferant nicht gefunden.")
    return SupplierOut.model_validate(_supplier_dict(x))


@router.post("/api/suppliers", response_model=SupplierOut)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    if payload.supplier_number and db.scalar(select(Supplier).where(Supplier.supplier_number==payload.supplier_number)):
        raise HTTPException(status_code=409, detail="Lieferantennummer ist bereits vergeben.")
    x=Supplier(**payload.model_dump()); db.add(x); db.commit(); db.refresh(x)
    return SupplierOut.model_validate(_supplier_dict(x))


@router.put("/api/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id:int,payload:SupplierUpdate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    x=db.get(Supplier,supplier_id)
    if x is None: raise HTTPException(status_code=404,detail="Lieferant nicht gefunden.")
    if payload.supplier_number:
        other=db.scalar(select(Supplier).where(Supplier.supplier_number==payload.supplier_number,Supplier.id!=supplier_id))
        if other: raise HTTPException(status_code=409,detail="Lieferantennummer ist bereits vergeben.")
    for k,v in payload.model_dump().items(): setattr(x,k,v)
    db.commit(); db.refresh(x); return SupplierOut.model_validate(_supplier_dict(x))


@router.delete("/api/suppliers/{supplier_id}")
def delete_supplier(supplier_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    x=db.get(Supplier,supplier_id)
    if x is None: raise HTTPException(status_code=404,detail="Lieferant nicht gefunden.")
    used=db.scalar(select(WorkPreparationMaterialSupplier).where(WorkPreparationMaterialSupplier.supplier_id==supplier_id)) or db.scalar(select(WorkPreparationDeliveryNote).where(WorkPreparationDeliveryNote.supplier_id==supplier_id))
    if used:
        x.active=False; db.commit(); return {"deleted":False,"deactivated":True}
    db.delete(x); db.commit(); return {"deleted":True}


@router.get("/api/resources", response_model=list[OperationalResourceOut])
def list_resources(db:Session=Depends(get_db),_role:AppUser=_role_dep):
    return [OperationalResourceOut.model_validate(_resource_dict(x)) for x in db.scalars(select(OperationalResource).order_by(OperationalResource.resource_type,OperationalResource.name)).all()]


@router.get("/api/resources/{resource_id}", response_model=OperationalResourceOut)
def get_resource(resource_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    x=db.get(OperationalResource,resource_id)
    if x is None: raise HTTPException(status_code=404,detail="Ressource nicht gefunden.")
    return OperationalResourceOut.model_validate(_resource_dict(x))


@router.post("/api/resources", response_model=OperationalResourceOut)
def create_resource(payload:OperationalResourceCreate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    if payload.resource_number and db.scalar(select(OperationalResource).where(OperationalResource.resource_number==payload.resource_number)):
        raise HTTPException(status_code=409,detail="Ressourcennummer ist bereits vergeben.")
    x=OperationalResource(**payload.model_dump()); db.add(x); db.commit(); db.refresh(x)
    return OperationalResourceOut.model_validate(_resource_dict(x))


@router.put("/api/resources/{resource_id}", response_model=OperationalResourceOut)
def update_resource(resource_id:int,payload:OperationalResourceUpdate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    x=db.get(OperationalResource,resource_id)
    if x is None: raise HTTPException(status_code=404,detail="Ressource nicht gefunden.")
    if payload.resource_number:
        other=db.scalar(select(OperationalResource).where(OperationalResource.resource_number==payload.resource_number,OperationalResource.id!=resource_id))
        if other: raise HTTPException(status_code=409,detail="Ressourcennummer ist bereits vergeben.")
    for k,v in payload.model_dump().items(): setattr(x,k,v)
    db.commit(); db.refresh(x); return OperationalResourceOut.model_validate(_resource_dict(x))


@router.delete("/api/resources/{resource_id}")
def delete_resource(resource_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    x=db.get(OperationalResource,resource_id)
    if x is None: raise HTTPException(status_code=404,detail="Ressource nicht gefunden.")
    used=db.scalar(select(TeamResource).where(TeamResource.resource_id==resource_id)) or db.scalar(select(WorkPreparationTeamResource).where(WorkPreparationTeamResource.resource_id==resource_id))
    if used:
        x.active=False; db.commit(); return {"deleted":False,"deactivated":True}
    db.delete(x); db.commit(); return {"deleted":True}


@router.get("/api/teams", response_model=list[TeamOut])
def list_teams(db:Session=Depends(get_db),_role:AppUser=_role_dep):
    rows=db.scalars(select(Team).order_by(Team.name)).all()
    return [TeamOut.model_validate(_team_dict(db,x)) for x in rows]


@router.get("/api/teams/{team_id}", response_model=TeamOut)
def get_team(team_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    x=db.get(Team,team_id)
    if x is None: raise HTTPException(status_code=404,detail="Kolonne / Team nicht gefunden.")
    return TeamOut.model_validate(_team_dict(db,x))


@router.post("/api/teams", response_model=TeamOut)
def create_team(payload:TeamCreate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    if payload.team_number and db.scalar(select(Team).where(Team.team_number==payload.team_number)):
        raise HTTPException(status_code=409,detail="Teamnummer ist bereits vergeben.")
    team=Team(team_number=payload.team_number,name=payload.name,description=payload.description,active=payload.active); db.add(team); db.flush()
    _apply_team_payload(db,team,payload); db.commit(); return TeamOut.model_validate(_team_dict(db,team))


@router.put("/api/teams/{team_id}", response_model=TeamOut)
def update_team(team_id:int,payload:TeamUpdate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    team=db.get(Team,team_id)
    if team is None: raise HTTPException(status_code=404,detail="Kolonne / Team nicht gefunden.")
    if payload.team_number:
        other=db.scalar(select(Team).where(Team.team_number==payload.team_number,Team.id!=team_id))
        if other: raise HTTPException(status_code=409,detail="Teamnummer ist bereits vergeben.")
    _apply_team_payload(db,team,payload); db.commit(); return TeamOut.model_validate(_team_dict(db,team))


@router.delete("/api/teams/{team_id}")
def delete_team(team_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    team=db.get(Team,team_id)
    if team is None: raise HTTPException(status_code=404,detail="Kolonne / Team nicht gefunden.")
    if db.scalar(select(WorkPreparationTeamAssignment).where(WorkPreparationTeamAssignment.team_id==team_id)):
        team.active=False; db.commit(); return {"deleted":False,"deactivated":True}
    db.delete(team); db.commit(); return {"deleted":True}
