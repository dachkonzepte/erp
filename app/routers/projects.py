"""Router: projects

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 9 Endpunkt(e) und 1 interne Hilfsfunktion(en), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from pathlib import Path
from fastapi import Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..invoices import invoice_overview_row, invoice_summary_for_order, list_invoices_for_project
from ..work_preparation import planned_hours
from ..models import Customer, Order, Project, ProjectDocument, ProjectProfile, Property, Quote
from ..option_settings import default_option_value, ensure_default_option_groups
from ..orders import load_order, order_to_dict
from ..project_documents import MAX_UPLOAD_BYTES, make_stored_filename, project_directory
from ..projects import delete_project, duplicate_project, load_project, load_quote, next_project_number, next_quote_number, quote_to_dict, set_project_archived
from ..service_reports import count_reports_for_order
from ..schemas import InvoiceOverviewOut, OrderListOut, ProjectCreate, ProjectDetailOut, ProjectDocumentOut, ProjectDuplicateRequest, ProjectListOut, ProjectUpdate, QuoteCreate, QuoteListOut, QuoteOut
from ..settings import get_or_create_general_settings

from .project_documents import _project_document_out

router = APIRouter()

def _ensure_project_profile(db: Session, project_id: int, category: str | None = None) -> ProjectProfile:
    ensure_default_option_groups(db)
    profile = db.scalar(select(ProjectProfile).where(ProjectProfile.project_id == project_id))
    if profile is None:
        profile = ProjectProfile(project_id=project_id, category=category or default_option_value(db, "project_categories"))
        db.add(profile)
        db.flush()
    elif category is not None:
        profile.category = category or None
    return profile


def _project_to_list_out(p: Project) -> "ProjectListOut":
    """Gemeinsamer Baustein für archive/unarchive/duplicate -- dieselbe
    Feldbefüllung wie _list_projects(), aber für ein einzelnes, bereits
    geladenes Projekt statt eine ganze Liste."""
    return ProjectListOut(
        id=p.id, project_number=p.project_number, name=p.name, status=p.status,
        customer_id=p.customer_id, customer_name=p.customer.name, property_id=p.property_id,
        property_name=p.property.name if p.property else None,
        category=p.profile.category if p.profile else None,
        quote_count=len(p.quotes), order_count=len(p.orders), document_count=len(p.documents),
        archived=p.archived,
    )


def _list_projects(db: Session, *, is_template: bool, include_archived: bool = False) -> list[ProjectListOut]:
    query = select(Project).options(
        selectinload(Project.customer),
        selectinload(Project.property),
        selectinload(Project.quotes),
        selectinload(Project.orders),
        selectinload(Project.documents),
        selectinload(Project.profile),
    ).where(Project.is_template == is_template)
    if not include_archived:
        query = query.where(Project.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    projects = db.scalars(query.order_by(Project.id.desc())).all()
    return [_project_to_list_out(p) for p in projects]


@router.get("/api/projects", response_model=list[ProjectListOut])
def list_projects(include_archived: bool = False, db: Session = Depends(get_db)):
    """Zeigt bewusst NUR normale Projekte -- Mustervorgänge (is_template=True)
    haben eine eigene Übersicht (siehe list_project_templates unten), damit
    sie nicht aus Versehen wie ein echtes Projekt bearbeitet werden."""
    return _list_projects(db, is_template=False, include_archived=include_archived)


@router.get("/api/project-templates", response_model=list[ProjectListOut])
def list_project_templates(include_archived: bool = False, db: Session = Depends(get_db)):
    return _list_projects(db, is_template=True, include_archived=include_archived)


@router.post("/api/projects/{project_id}/archive", response_model=ProjectListOut)
def archive_project_endpoint(project_id: int, db: Session = Depends(get_db)):
    project = load_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    set_project_archived(db, project, True)
    return _project_to_list_out(project)


@router.post("/api/projects/{project_id}/unarchive", response_model=ProjectListOut)
def unarchive_project_endpoint(project_id: int, db: Session = Depends(get_db)):
    project = load_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    set_project_archived(db, project, False)
    return _project_to_list_out(project)


@router.delete("/api/projects/{project_id}")
def delete_project_endpoint(project_id: int, db: Session = Depends(get_db)):
    project = load_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    try:
        delete_project(db, project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": True}


@router.post("/api/projects/{project_id}/duplicate", response_model=ProjectListOut)
def duplicate_project_endpoint(project_id: int, payload: ProjectDuplicateRequest, db: Session = Depends(get_db)):
    """Gemeinsamer Endpunkt für 'Vorgang kopieren', 'als Mustervorgang
    speichern' und 'neuen Vorgang aus Muster erstellen' -- der Quellstatus
    (ob is_template) spielt keine Rolle, nur payload.as_template bestimmt
    das Ergebnis. Damit lässt sich z.B. auch ein Muster in ein weiteres
    Muster duplizieren, falls das je gebraucht wird."""
    source = load_project(db, project_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    new_project = duplicate_project(db, source, as_template=payload.as_template)
    return _project_to_list_out(new_project)


@router.post("/api/projects", response_model=ProjectListOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    property_obj = None
    if payload.property_id is not None:
        property_obj = db.get(Property, payload.property_id)
        if property_obj is None or property_obj.customer_id != payload.customer_id:
            raise HTTPException(status_code=422, detail="Objekt gehört nicht zum ausgewählten Kunden.")
    data = payload.model_dump(exclude={"category"})
    project = Project(project_number=next_project_number(db), **data)
    db.add(project)
    db.flush()
    _ensure_project_profile(db, project.id, payload.category)
    db.commit()
    project = db.scalar(select(Project).options(
        selectinload(Project.customer), selectinload(Project.property), selectinload(Project.quotes), selectinload(Project.orders),
        selectinload(Project.documents), selectinload(Project.profile),
    ).where(Project.id == project.id))
    return ProjectListOut(
        id=project.id, project_number=project.project_number, name=project.name, status=project.status,
        customer_id=project.customer_id, customer_name=project.customer.name,
        property_id=project.property_id, property_name=project.property.name if project.property else None,
        category=project.profile.category if project.profile else None, quote_count=len(project.quotes), order_count=len(project.orders),
        document_count=len(project.documents),
    )


@router.put("/api/projects/{project_id}", response_model=ProjectDetailOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    prop = None
    if payload.property_id is not None:
        prop = db.get(Property, payload.property_id)
        if prop is None or prop.customer_id != payload.customer_id:
            raise HTTPException(status_code=422, detail="Objekt gehört nicht zum ausgewählten Kunden.")
    project.customer_id = payload.customer_id
    project.property_id = payload.property_id
    project.name = payload.name
    project.status = payload.status
    project.description = payload.description
    _ensure_project_profile(db, project.id, payload.category)
    db.commit()
    return get_project_detail(project_id, db)


@router.get("/api/projects/{project_id}", response_model=ProjectDetailOut)
def get_project_detail(project_id: int, db: Session = Depends(get_db)):
    project = db.scalar(
        select(Project).options(
            selectinload(Project.customer).selectinload(Customer.profile),
            selectinload(Project.property), selectinload(Project.quotes), selectinload(Project.orders), selectinload(Project.documents),
            selectinload(Project.profile),
        ).where(Project.id == project_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    prop = project.property
    return ProjectDetailOut(
        id=project.id, project_number=project.project_number, name=project.name, status=project.status,
        customer_id=project.customer_id, customer_name=project.customer.name, customer_number=project.customer.customer_number,
        customer_phone=project.customer.phone, customer_email=project.customer.email,
        property_id=project.property_id, property_name=prop.name if prop else None,
        property_street=prop.street if prop else None, property_postal_code=prop.postal_code if prop else None, property_city=prop.city if prop else None,
        quote_count=len(project.quotes), order_count=len(project.orders), document_count=len(project.documents), description=project.description,
        category=project.profile.category if project.profile else None, archived=project.archived, is_template=project.is_template,
    )


@router.get("/api/projects/{project_id}/documents", response_model=list[ProjectDocumentOut])
def list_project_documents(project_id: int, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    docs = db.scalars(select(ProjectDocument).where(ProjectDocument.project_id == project_id).order_by(ProjectDocument.uploaded_at.desc())).all()
    return [_project_document_out(d) for d in docs]


@router.post("/api/projects/{project_id}/documents", response_model=ProjectDocumentOut)
async def upload_project_document(
    project_id: int, file: UploadFile = File(...), category: str = Form("Sonstiges"),
    description: str | None = Form(None), document_date: str | None = Form(None), db: Session = Depends(get_db),
    subfolder: str | None = Form(None),
):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 50 MB.")
    stored = make_stored_filename(file.filename)
    target = project_directory(project_id) / stored
    target.write_bytes(data)
    from datetime import date as _date
    parsed_date = None
    if document_date:
        try:
            parsed_date = _date.fromisoformat(document_date)
        except ValueError:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Ungültiges Dokumentdatum.")
    doc = ProjectDocument(
        project_id=project_id, category=(category or "Sonstiges").strip(),
        subfolder=(subfolder.strip() or None) if isinstance(subfolder, str) else None,
        original_filename=Path(file.filename).name,
        stored_filename=stored, content_type=file.content_type, file_size=len(data), description=(description or None), document_date=parsed_date,
    )
    db.add(doc); db.commit(); db.refresh(doc)
    return _project_document_out(doc)


@router.get("/api/projects/{project_id}/orders", response_model=list[OrderListOut])
def list_project_orders(project_id: int, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None: raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    orders = db.scalars(select(Order).where(Order.project_id == project_id).order_by(Order.id.desc())).all()
    result=[]
    for row in orders:
        loaded=load_order(db,row.id); values=order_to_dict(loaded, db)
        invoice_count, fully_invoiced = invoice_summary_for_order(db, loaded.id)
        result.append(OrderListOut(id=loaded.id,order_number=loaded.order_number,project_id=loaded.project_id,project_number=loaded.project.project_number,project_name=loaded.project.name,customer_name=loaded.customer_name,title=loaded.title,status=loaded.status,order_date=loaded.order_date,net_total=values["net_total"],gross_total=values["gross_total"],invoice_count=invoice_count,fully_invoiced=fully_invoiced,invoiced_net=values["invoiced_net"],invoiced_gross=values["invoiced_gross"],planned_hours=planned_hours(loaded),service_report_count=count_reports_for_order(db, loaded.id)))
    return result


@router.get("/api/projects/{project_id}/invoices", response_model=list[InvoiceOverviewOut])
def list_project_invoices(project_id: int, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None: raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    invoices = list_invoices_for_project(db, project_id)
    return [invoice_overview_row(inv) for inv in invoices]


@router.get("/api/projects/{project_id}/quotes", response_model=list[QuoteListOut])
def list_project_quotes(project_id: int, db: Session = Depends(get_db)):
    project = load_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    result = []
    for summary in project.quotes:
        quote = load_quote(db, summary.id)
        values = quote_to_dict(quote)
        result.append(QuoteListOut(
            id=quote.id, quote_number=quote.quote_number, project_id=quote.project_id,
            title=quote.title, status=quote.status, net_total=values["net_total"], gross_total=values["gross_total"]
        ))
    return result


@router.post("/api/projects/{project_id}/quotes", response_model=QuoteOut)
def create_quote(project_id: int, payload: QuoteCreate, db: Session = Depends(get_db)):
    project = load_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    general = get_or_create_general_settings(db)
    quote = Quote(
        quote_number=next_quote_number(db),
        project_id=project.id,
        title=payload.title,
        vat_rate=payload.vat_rate,
        intro_text=payload.intro_text if payload.intro_text is not None else (default_option_value(db, "quote_intro_texts") or general.default_quote_intro),
        outro_text=payload.outro_text if payload.outro_text is not None else (default_option_value(db, "quote_outro_texts") or general.default_quote_outro),
    )
    db.add(quote)
    db.commit()
    quote = load_quote(db, quote.id)
    return QuoteOut.model_validate(quote_to_dict(quote))
