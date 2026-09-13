"""Router: inquiries

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 5 Endpunkt(e) und 3 interne Hilfsfunktion(en), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..inquiries import inquiry_to_dict, load_inquiry, next_inquiry_number
from ..models import Customer, Inquiry, Project, Property, Quote
from ..option_settings import default_option_value
from ..projects import load_project, load_quote, next_project_number, next_quote_number, quote_to_dict
from ..schemas import InquiryConvertOut, InquiryConvertRequest, InquiryCreate, InquiryOut, InquiryUpdate, ProjectListOut, QuoteOut
from ..settings import get_or_create_general_settings

router = APIRouter()

INQUIRY_STATUSES = {"neu", "termin_offen", "termin_geplant", "aufmass_erfolgt", "projekt_erstellt", "gewonnen", "verloren"}
INQUIRY_PRIORITIES = {"niedrig", "normal", "hoch", "dringend"}


def _validate_inquiry_payload(payload):
    if payload.status not in INQUIRY_STATUSES:
        raise HTTPException(status_code=422, detail="Ungültiger Anfragestatus.")
    if payload.priority not in INQUIRY_PRIORITIES:
        raise HTTPException(status_code=422, detail="Ungültige Priorität.")
    if payload.status == "verloren" and not (payload.lost_reason or "").strip():
        raise HTTPException(status_code=422, detail="Bei verlorenen Anfragen bitte einen Grund hinterlegen.")


def _validate_inquiry_customer_property(db: Session, customer_id: int, property_id: int | None):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    property_obj = None
    if property_id is not None:
        property_obj = db.get(Property, property_id)
        if property_obj is None or property_obj.customer_id != customer_id:
            raise HTTPException(status_code=422, detail="Objekt gehört nicht zum ausgewählten Kunden.")
    return customer, property_obj


def _project_list_out(project: Project) -> ProjectListOut:
    return ProjectListOut(
        id=project.id, project_number=project.project_number, name=project.name, status=project.status,
        customer_id=project.customer_id, customer_name=project.customer.name,
        property_id=project.property_id, property_name=project.property.name if project.property else None,
        quote_count=len(project.quotes), order_count=len(project.orders),
    )


@router.get("/api/inquiries", response_model=list[InquiryOut])
def list_inquiries(customer_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(Inquiry)
        .options(selectinload(Inquiry.customer), selectinload(Inquiry.property), selectinload(Inquiry.project))
        .order_by(Inquiry.updated_at.desc(), Inquiry.id.desc())
    )
    if customer_id is not None:
        stmt = stmt.where(Inquiry.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(Inquiry.status == status)
    return [InquiryOut.model_validate(inquiry_to_dict(x)) for x in db.scalars(stmt).all()]


@router.get("/api/inquiries/{inquiry_id}", response_model=InquiryOut)
def get_inquiry(inquiry_id: int, db: Session = Depends(get_db)):
    inquiry = load_inquiry(db, inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail="Anfrage nicht gefunden.")
    return InquiryOut.model_validate(inquiry_to_dict(inquiry))


@router.post("/api/inquiries", response_model=InquiryOut)
def create_inquiry(payload: InquiryCreate, db: Session = Depends(get_db)):
    _validate_inquiry_payload(payload)
    customer, property_obj = _validate_inquiry_customer_property(db, payload.customer_id, payload.property_id)
    inquiry = Inquiry(inquiry_number=next_inquiry_number(db), **payload.model_dump())
    if not inquiry.contact_person:
        inquiry.contact_person = customer.contact_person
    db.add(inquiry)
    db.commit()
    inquiry = load_inquiry(db, inquiry.id)
    return InquiryOut.model_validate(inquiry_to_dict(inquiry))


@router.put("/api/inquiries/{inquiry_id}", response_model=InquiryOut)
def update_inquiry(inquiry_id: int, payload: InquiryUpdate, db: Session = Depends(get_db)):
    _validate_inquiry_payload(payload)
    inquiry = load_inquiry(db, inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail="Anfrage nicht gefunden.")
    _validate_inquiry_customer_property(db, payload.customer_id, payload.property_id)
    if inquiry.project_id is not None:
        project = db.get(Project, inquiry.project_id)
        if project and (payload.customer_id != project.customer_id or payload.property_id != project.property_id):
            raise HTTPException(status_code=422, detail="Kunde oder Objekt können nach der Projektanlage nicht mehr über die Anfrage geändert werden.")
    for key, value in payload.model_dump().items():
        setattr(inquiry, key, value)
    db.commit()
    inquiry = load_inquiry(db, inquiry.id)
    return InquiryOut.model_validate(inquiry_to_dict(inquiry))


@router.post("/api/inquiries/{inquiry_id}/convert", response_model=InquiryConvertOut)
def convert_inquiry(inquiry_id: int, payload: InquiryConvertRequest, db: Session = Depends(get_db)):
    inquiry = load_inquiry(db, inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail="Anfrage nicht gefunden.")
    if inquiry.project_id is not None:
        raise HTTPException(status_code=409, detail="Für diese Anfrage wurde bereits ein Projekt erzeugt.")
    general = get_or_create_general_settings(db)
    project = Project(
        project_number=next_project_number(db),
        customer_id=inquiry.customer_id,
        property_id=inquiry.property_id,
        name=(payload.project_name or inquiry.title).strip(),
        status="angebot",
        description=inquiry.description,
    )
    db.add(project)
    db.flush()
    inquiry.project_id = project.id
    inquiry.status = "projekt_erstellt"

    quote = None
    if payload.create_quote:
        quote = Quote(
            quote_number=next_quote_number(db),
            project_id=project.id,
            title=payload.quote_title,
            vat_rate=payload.vat_rate,
            intro_text=default_option_value(db, "quote_intro_texts") or general.default_quote_intro,
            outro_text=default_option_value(db, "quote_outro_texts") or general.default_quote_outro,
        )
        db.add(quote)
    db.commit()

    inquiry = load_inquiry(db, inquiry.id)
    project = load_project(db, project.id)
    quote_out = None
    if quote is not None:
        quote = load_quote(db, quote.id)
        quote_out = QuoteOut.model_validate(quote_to_dict(quote))
    return InquiryConvertOut(
        inquiry=InquiryOut.model_validate(inquiry_to_dict(inquiry)),
        project=_project_list_out(project),
        quote=quote_out,
    )
