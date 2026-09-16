"""Router: work_preparation

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 15 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from pathlib import Path
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..document_categories import resolve_category_id
from ..models import AppUser, Employee, Order, PlanningSlot, ProjectDocument, Supplier, Team, TeamEmployee, TeamResource, WorkPreparation, WorkPreparationDeliveryNote, WorkPreparationEmployee, WorkPreparationMaterial, WorkPreparationMaterialDeliveryNote, WorkPreparationMaterialSupplier, WorkPreparationTask, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee, WorkPreparationTeamResource
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..project_documents import MAX_UPLOAD_BYTES, document_path, make_stored_filename, project_directory
from ..schemas import WorkPreparationEmployeeCreate, WorkPreparationEmployeeUpdate, WorkPreparationMaterialBulkAssign, WorkPreparationMaterialUpdateV082, WorkPreparationOut, WorkPreparationTaskCreate, WorkPreparationTaskUpdate, WorkPreparationTeamAssign, WorkPreparationUpdate
from ..work_preparation import ensure_preparation, list_open_tasks, load_preparation, preparation_to_dict

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): die Arbeitsvorbereitung selbst (Zuordnungen/Material/
# Teams/Lieferscheine bearbeiten) ist Büro-/Admin-Bereich -- kein Endpunkt dieser Datei wird von
# einer Monteur-Vorlage aufgerufen. EINE Ausnahme (_any_role_dep unten): das Dashboard-Widget
# "Meine Aufgaben" ist Selbstbedienung für jede Rolle, analog zu absence_requests.py -- die
# bereits bestehende Eigentümerschafts-Filterung sorgt dafür, dass ein Nicht-Admin nur seine
# eigenen Aufgaben sieht.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))
_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))


@router.get("/api/work-preparation/tasks")
def get_open_work_preparation_tasks(request: Request, employee_id: int | None = None, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Offene Arbeitsvorbereitungs-Aufgaben über alle Aufträge hinweg, fürs
    Dashboard-Widget "Meine Aufgaben" (seit 1.0.102). Rechteprüfung analog zu
    get_absence_requests() in routers/absence_requests.py: Nicht-Admins sehen
    ausschließlich ihre eigenen Aufgaben, unabhängig vom übergebenen Parameter."""
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role != "admin":
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail="Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
        employee_id = user.employee_id
    return list_open_tasks(db, employee_id=employee_id)


@router.get("/api/orders/{order_id}/work-preparation", response_model=WorkPreparationOut)
def get_work_preparation(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        prep = ensure_preparation(db, order_id)
        return preparation_to_dict(db, prep)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/api/orders/{order_id}/work-preparation", response_model=WorkPreparationOut)
def update_work_preparation(order_id: int, payload: WorkPreparationUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        prep = ensure_preparation(db, order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    for key, value in payload.model_dump().items():
        setattr(prep, key, value)
    db.commit()
    return preparation_to_dict(db, load_preparation(db, order_id))


@router.post("/api/orders/{order_id}/work-preparation/employees", response_model=WorkPreparationOut)
def add_work_preparation_employee(order_id: int, payload: WorkPreparationEmployeeCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    prep = ensure_preparation(db, order_id)
    employee = db.get(Employee, payload.employee_id)
    if employee is None or not employee.active:
        raise HTTPException(status_code=422, detail="Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    existing = db.scalar(select(WorkPreparationEmployee).where(WorkPreparationEmployee.preparation_id==prep.id, WorkPreparationEmployee.employee_id==payload.employee_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Mitarbeiter ist bereits dieser Arbeitsvorbereitung zugeordnet.")
    db.add(WorkPreparationEmployee(preparation_id=prep.id, **payload.model_dump()))
    db.commit()
    return preparation_to_dict(db, load_preparation(db, order_id))


@router.put("/api/work-preparation/employees/{assignment_id}", response_model=WorkPreparationOut)
def update_work_preparation_employee(assignment_id: int, payload: WorkPreparationEmployeeUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    row = db.get(WorkPreparationEmployee, assignment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Mitarbeiterzuordnung nicht gefunden.")
    order_id = row.preparation.order_id
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    db.commit()
    return preparation_to_dict(db, load_preparation(db, order_id))


@router.delete("/api/work-preparation/employees/{assignment_id}", response_model=WorkPreparationOut)
def delete_work_preparation_employee(assignment_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    row = db.get(WorkPreparationEmployee, assignment_id)
    if row is None: raise HTTPException(status_code=404, detail="Mitarbeiterzuordnung nicht gefunden.")
    order_id=row.preparation.order_id; db.delete(row); db.commit()
    return preparation_to_dict(db, load_preparation(db, order_id))


@router.post("/api/orders/{order_id}/work-preparation/tasks", response_model=WorkPreparationOut)
def add_work_preparation_task(order_id: int, payload: WorkPreparationTaskCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    prep=ensure_preparation(db,order_id)
    if payload.assigned_employee_id is not None:
        e=db.get(Employee,payload.assigned_employee_id)
        if e is None or not e.active: raise HTTPException(status_code=422,detail="Zugeordneter Mitarbeiter ist nicht aktiv.")
    db.add(WorkPreparationTask(preparation_id=prep.id,**payload.model_dump())); db.commit()
    return preparation_to_dict(db,load_preparation(db,order_id))


@router.put("/api/work-preparation/tasks/{task_id}", response_model=WorkPreparationOut)
def update_work_preparation_task(task_id: int, payload: WorkPreparationTaskUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    row=db.get(WorkPreparationTask,task_id)
    if row is None: raise HTTPException(status_code=404,detail="Aufgabe nicht gefunden.")
    if payload.assigned_employee_id is not None:
        e=db.get(Employee,payload.assigned_employee_id)
        if e is None or not e.active: raise HTTPException(status_code=422,detail="Zugeordneter Mitarbeiter ist nicht aktiv.")
    order_id=row.preparation.order_id
    for key,value in payload.model_dump().items(): setattr(row,key,value)
    db.commit(); return preparation_to_dict(db,load_preparation(db,order_id))


@router.delete("/api/work-preparation/tasks/{task_id}", response_model=WorkPreparationOut)
def delete_work_preparation_task(task_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    row=db.get(WorkPreparationTask,task_id)
    if row is None: raise HTTPException(status_code=404,detail="Aufgabe nicht gefunden.")
    order_id=row.preparation.order_id; db.delete(row); db.commit(); return preparation_to_dict(db,load_preparation(db,order_id))


@router.post("/api/work-preparation/materials/bulk-assign", response_model=WorkPreparationOut)
def bulk_assign_work_preparation_materials(payload: WorkPreparationMaterialBulkAssign, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    material_ids=list(dict.fromkeys(payload.material_ids))
    rows=db.scalars(select(WorkPreparationMaterial).where(WorkPreparationMaterial.id.in_(material_ids))).all()
    if len(rows)!=len(material_ids):
        raise HTTPException(status_code=404,detail="Mindestens eine Materialposition wurde nicht gefunden.")
    prep_ids={row.preparation_id for row in rows}
    if len(prep_ids)!=1:
        raise HTTPException(status_code=422,detail="Materialpositionen müssen aus derselben Arbeitsvorbereitung stammen.")
    prep_id=next(iter(prep_ids))
    prep=db.get(WorkPreparation,prep_id); order_id=prep.order_id

    supplier=None
    if payload.supplier_id is not None:
        supplier=db.get(Supplier,payload.supplier_id)
        if supplier is None or not supplier.active:
            raise HTTPException(status_code=422,detail="Lieferant wurde nicht gefunden oder ist inaktiv.")

    delivery_note=None
    if payload.delivery_note_id is not None:
        delivery_note=db.get(WorkPreparationDeliveryNote,payload.delivery_note_id)
        if delivery_note is None or delivery_note.preparation_id!=prep_id:
            raise HTTPException(status_code=422,detail="Lieferschein gehört nicht zu dieser Arbeitsvorbereitung.")
        if supplier is None and delivery_note.supplier_id:
            supplier=db.get(Supplier,delivery_note.supplier_id)
        elif supplier is not None and delivery_note.supplier_id and delivery_note.supplier_id!=supplier.id:
            raise HTTPException(status_code=422,detail="Ausgewählter Lieferschein gehört zu einem anderen Lieferanten.")
        elif supplier is not None and delivery_note.supplier_id is None:
            delivery_note.supplier_id=supplier.id

    if supplier is None and delivery_note is None:
        raise HTTPException(status_code=422,detail="Bitte Lieferant und/oder Lieferschein auswählen.")

    for row in rows:
        if supplier is not None:
            row.supplier=supplier.name
            link=db.scalar(select(WorkPreparationMaterialSupplier).where(WorkPreparationMaterialSupplier.material_id==row.id))
            if link is None:
                db.add(WorkPreparationMaterialSupplier(material_id=row.id,supplier_id=supplier.id))
            else:
                link.supplier_id=supplier.id
        if delivery_note is not None:
            exists=db.scalar(select(WorkPreparationMaterialDeliveryNote).where(
                WorkPreparationMaterialDeliveryNote.material_id==row.id,
                WorkPreparationMaterialDeliveryNote.delivery_note_id==delivery_note.id,
            ))
            if exists is None:
                db.add(WorkPreparationMaterialDeliveryNote(material_id=row.id,delivery_note_id=delivery_note.id))
    db.commit()
    return preparation_to_dict(db,load_preparation(db,order_id))


@router.put("/api/work-preparation/materials/{material_id}", response_model=WorkPreparationOut)
def update_work_preparation_material(material_id: int, payload: WorkPreparationMaterialUpdateV082, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    row=db.get(WorkPreparationMaterial,material_id)
    if row is None: raise HTTPException(status_code=404,detail="Materialbedarf nicht gefunden.")
    order_id=row.preparation.order_id
    row.planned_quantity=payload.planned_quantity; row.status=payload.status; row.notes=payload.notes
    link=db.scalar(select(WorkPreparationMaterialSupplier).where(WorkPreparationMaterialSupplier.material_id==row.id))
    if payload.supplier_id is not None:
        supplier=db.get(Supplier,payload.supplier_id)
        if supplier is None or not supplier.active: raise HTTPException(status_code=422,detail="Lieferant wurde nicht gefunden oder ist inaktiv.")
        row.supplier=supplier.name
        if link is None: db.add(WorkPreparationMaterialSupplier(material_id=row.id,supplier_id=supplier.id))
        else: link.supplier_id=supplier.id
    else:
        row.supplier=payload.supplier
        if link is not None: db.delete(link)
    db.commit(); return preparation_to_dict(db,load_preparation(db,order_id))


@router.post("/api/orders/{order_id}/work-preparation/teams", response_model=WorkPreparationOut)
def assign_work_preparation_team(order_id:int,payload:WorkPreparationTeamAssign,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    prep=ensure_preparation(db,order_id)
    team=db.scalar(select(Team).options(selectinload(Team.employees).selectinload(TeamEmployee.employee),selectinload(Team.resources).selectinload(TeamResource.resource)).where(Team.id==payload.team_id))
    if team is None or not team.active: raise HTTPException(status_code=422,detail="Kolonne / Team wurde nicht gefunden oder ist inaktiv.")
    if db.scalar(select(WorkPreparationTeamAssignment).where(WorkPreparationTeamAssignment.preparation_id==prep.id,WorkPreparationTeamAssignment.team_id==team.id)):
        raise HTTPException(status_code=409,detail="Kolonne / Team ist bereits dieser Arbeitsvorbereitung zugeordnet.")
    assignment=WorkPreparationTeamAssignment(preparation_id=prep.id,team_id=team.id,team_name_snapshot=team.name,notes=payload.notes); db.add(assignment); db.flush()
    for m in team.employees:
        if m.employee and m.employee.active:
            db.add(WorkPreparationTeamEmployee(assignment_id=assignment.id,employee_id=m.employee_id,employee_name_snapshot=f"{m.employee.first_name} {m.employee.last_name}".strip(),role_snapshot=m.role))
    for r in team.resources:
        if r.resource and r.resource.active:
            db.add(WorkPreparationTeamResource(assignment_id=assignment.id,resource_id=r.resource_id,resource_name_snapshot=r.resource.name,resource_type_snapshot=r.resource.resource_type,role_snapshot=r.role))
    db.commit(); return preparation_to_dict(db,load_preparation(db,order_id))


@router.delete("/api/work-preparation/teams/{assignment_id}", response_model=WorkPreparationOut)
def remove_work_preparation_team(assignment_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(WorkPreparationTeamAssignment,assignment_id)
    if row is None: raise HTTPException(status_code=404,detail="Teamzuordnung nicht gefunden.")
    if db.scalar(select(PlanningSlot).where(PlanningSlot.team_assignment_id==assignment_id)):
        raise HTTPException(status_code=409,detail="Diese Kolonne besitzt noch einen Einsatz in der Plantafel. Bitte den Planeinsatz dort zuerst entfernen oder umplanen.")
    prep=db.get(WorkPreparation,row.preparation_id); order_id=prep.order_id
    db.delete(row); db.commit(); return preparation_to_dict(db,load_preparation(db,order_id))


@router.post("/api/orders/{order_id}/work-preparation/delivery-notes", response_model=WorkPreparationOut)
async def upload_work_preparation_delivery_note(
    order_id:int, file:UploadFile=File(...), supplier_id:int|None=Form(None), delivery_note_number:str|None=Form(None),
    document_date:str|None=Form(None), description:str|None=Form(None), db:Session=Depends(get_db),
    _role:AppUser=_role_dep,
):
    prep=ensure_preparation(db,order_id); order=db.get(Order,order_id)
    if not file.filename: raise HTTPException(status_code=400,detail="Bitte Lieferschein-Datei auswählen.")
    supplier=None
    if supplier_id:
        supplier=db.get(Supplier,supplier_id)
        if supplier is None: raise HTTPException(status_code=422,detail="Lieferant nicht gefunden.")
    data=await file.read(MAX_UPLOAD_BYTES+1)
    if len(data)>MAX_UPLOAD_BYTES: raise HTTPException(status_code=413,detail="Datei ist größer als 50 MB.")
    from datetime import date as _date
    parsed_date=None
    if document_date:
        try: parsed_date=_date.fromisoformat(document_date)
        except ValueError: raise HTTPException(status_code=422,detail="Ungültiges Dokumentdatum.")
    stored=make_stored_filename(file.filename); target=project_directory(order.project_id)/stored; target.write_bytes(data)
    doc=ProjectDocument(project_id=order.project_id,category="Lieferscheine",category_id=resolve_category_id(db,"Lieferscheine"),original_filename=Path(file.filename).name,stored_filename=stored,content_type=file.content_type,file_size=len(data),description=description or None,document_date=parsed_date)
    db.add(doc); db.flush()
    link=WorkPreparationDeliveryNote(preparation_id=prep.id,project_document_id=doc.id,supplier_id=supplier.id if supplier else None,delivery_note_number=(delivery_note_number or None),document_date=parsed_date,notes=description or None)
    db.add(link); db.commit(); return preparation_to_dict(db,load_preparation(db,order_id))


@router.delete("/api/work-preparation/materials/{material_id}/delivery-notes/{delivery_note_id}", response_model=WorkPreparationOut)
def unlink_material_delivery_note(material_id:int, delivery_note_id:int, db:Session=Depends(get_db),_role:AppUser=_role_dep):
    material=db.get(WorkPreparationMaterial,material_id)
    if material is None:
        raise HTTPException(status_code=404,detail="Materialposition nicht gefunden.")
    link=db.scalar(select(WorkPreparationMaterialDeliveryNote).where(
        WorkPreparationMaterialDeliveryNote.material_id==material_id,
        WorkPreparationMaterialDeliveryNote.delivery_note_id==delivery_note_id,
    ))
    if link is None:
        raise HTTPException(status_code=404,detail="Lieferschein-Zuordnung nicht gefunden.")
    prep=db.get(WorkPreparation,material.preparation_id); order_id=prep.order_id
    db.delete(link); db.commit()
    return preparation_to_dict(db,load_preparation(db,order_id))


@router.delete("/api/work-preparation/delivery-notes/{delivery_note_id}", response_model=WorkPreparationOut)
def delete_work_preparation_delivery_note(delivery_note_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(WorkPreparationDeliveryNote,delivery_note_id)
    if row is None: raise HTTPException(status_code=404,detail="Lieferschein nicht gefunden.")
    prep=db.get(WorkPreparation,row.preparation_id); order_id=prep.order_id; doc=db.get(ProjectDocument,row.project_document_id)
    path=document_path(doc) if doc else None
    for link in db.scalars(select(WorkPreparationMaterialDeliveryNote).where(WorkPreparationMaterialDeliveryNote.delivery_note_id==row.id)).all():
        db.delete(link)
    db.delete(row)
    if doc is not None: db.delete(doc)
    db.commit()
    if path: path.unlink(missing_ok=True)
    return preparation_to_dict(db,load_preparation(db,order_id))
