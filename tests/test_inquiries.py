from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import create_customer, create_inquiry, update_inquiry, convert_inquiry
from app.models import Inquiry, Property, Project, Quote
from app.schemas import (
    CustomerCreate,
    InquiryConvertRequest,
    InquiryCreate,
    InquiryUpdate,
)


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_inquiry_workflow_to_project_and_quote():
    db = make_db()
    customer = create_customer(
        CustomerCreate(
            last_name="Familie Test",
            contact_person="Max Test",
            street="Dachweg 1",
            postal_code="52531",
            city="Übach-Palenberg",
        ),
        db,
    )
    main_property = db.scalar(
        select(Property).where(Property.customer_id == customer.id, Property.name == "Hauptadresse")
    )

    inquiry = create_inquiry(
        InquiryCreate(
            customer_id=customer.id,
            property_id=main_property.id,
            title="Energetische Dachsanierung",
            description="Steildach besichtigen und Aufmaß erstellen.",
            status="termin_geplant",
            priority="hoch",
            source="Empfehlung",
            visit_at=datetime.now() + timedelta(days=2),
            follow_up_at=datetime.now() + timedelta(days=3),
        ),
        db,
    )
    assert inquiry.inquiry_number.startswith("ANF-")
    assert inquiry.contact_person == "Max Test"
    assert inquiry.project_id is None

    updated = update_inquiry(
        inquiry.id,
        InquiryUpdate(
            customer_id=customer.id,
            property_id=main_property.id,
            title=inquiry.title,
            description=inquiry.description,
            status="aufmass_erfolgt",
            priority="hoch",
            source="Empfehlung",
            contact_person="Max Test",
            assigned_to="Tobias",
            visit_at=inquiry.visit_at,
            follow_up_at=inquiry.follow_up_at,
            lost_reason=None,
        ),
        db,
    )
    assert updated.status == "aufmass_erfolgt"
    assert updated.assigned_to == "Tobias"

    result = convert_inquiry(
        inquiry.id,
        InquiryConvertRequest(
            project_name="Dachsanierung Familie Test",
            quote_title="Angebot Dachsanierung",
            create_quote=True,
        ),
        db,
    )
    assert result.inquiry.status == "projekt_erstellt"
    assert result.project.project_number.startswith("P-")
    assert result.project.status == "angebot"
    assert result.quote is not None
    assert result.quote.quote_number.startswith("A-")

    stored_inquiry = db.get(Inquiry, inquiry.id)
    assert stored_inquiry.project_id == result.project.id
    assert db.get(Project, result.project.id) is not None
    assert db.get(Quote, result.quote.id) is not None
