from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Inquiry, Project
from .settings import preview_number


def next_inquiry_number(db: Session) -> str:
    return preview_number(db, "inquiry")

def load_inquiry(db: Session, inquiry_id: int) -> Inquiry | None:
    return db.scalar(
        select(Inquiry)
        .options(
            selectinload(Inquiry.customer),
            selectinload(Inquiry.property),
            selectinload(Inquiry.project),
        )
        .where(Inquiry.id == inquiry_id)
    )


def inquiry_to_dict(inquiry: Inquiry) -> dict:
    property_address = None
    if inquiry.property:
        property_address = ", ".join(
            part for part in [
                inquiry.property.street,
                " ".join(x for x in [inquiry.property.postal_code, inquiry.property.city] if x),
            ] if part
        ) or None

    return {
        "id": inquiry.id,
        "inquiry_number": inquiry.inquiry_number,
        "customer_id": inquiry.customer_id,
        "customer_name": inquiry.customer.name,
        "property_id": inquiry.property_id,
        "property_name": inquiry.property.name if inquiry.property else None,
        "property_address": property_address,
        "project_id": inquiry.project_id,
        "project_number": inquiry.project.project_number if inquiry.project else None,
        "title": inquiry.title,
        "description": inquiry.description,
        "status": inquiry.status,
        "priority": inquiry.priority,
        "source": inquiry.source,
        "contact_person": inquiry.contact_person,
        "assigned_to": inquiry.assigned_to,
        "visit_at": inquiry.visit_at,
        "follow_up_at": inquiry.follow_up_at,
        "lost_reason": inquiry.lost_reason,
        "created_at": inquiry.created_at,
        "updated_at": inquiry.updated_at,
    }
