from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Customer, CustomerProfile
from .settings import preview_number


def compose_customer_name(salutation: str | None, title: str | None, first_name: str | None, last_name: str) -> str:
    """Setzt Customer.name aus salutation/title/first_name/last_name zusammen -- last_name
    ist das eigentliche Pflichtfeld (trägt bei Firmenkunden den Firmennamen), die übrigen
    drei sind optional und werden nur eingefügt, wenn sie tatsächlich gesetzt sind. Einzige
    Quelle für Customer.name -- weder create_customer() noch update_customer() nehmen name
    mehr direkt entgegen, siehe CLAUDE.md "Adressimport aus dem Altsystem"."""
    parts = [salutation, title, first_name, last_name]
    return " ".join(p.strip() for p in parts if p and p.strip())


def next_customer_number(db: Session) -> str:
    """Reserviert die nächste automatische Kundennummer."""
    return preview_number(db, "customer")


def customer_number_preview(db: Session) -> str:
    return preview_number(db, "customer")


def ensure_customer_profile(
    db: Session,
    customer: Customer,
    category: str | None = None,
    customer_number: str | None = None,
    default_payment_term_id: int | None = None,
    set_payment_term: bool = False,
) -> CustomerProfile:
    profile = customer.profile
    if profile is None:
        profile = db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == customer.id))

    requested_number = (customer_number or "").strip() or None
    if requested_number:
        existing = db.scalar(
            select(CustomerProfile).where(
                CustomerProfile.customer_number == requested_number,
                CustomerProfile.customer_id != customer.id,
            )
        )
        if existing is not None:
            raise ValueError(f"Die Kundennummer {requested_number} ist bereits vergeben.")

    if profile is None:
        effective_number = requested_number or next_customer_number(db)
        profile = CustomerProfile(
            customer_id=customer.id,
            customer_number=effective_number,
            category=(category or "Privatkunde").strip() or "Privatkunde",
            default_payment_term_id=default_payment_term_id if set_payment_term else None,
        )
        db.add(profile)
        db.flush()
        customer.profile = profile
    else:
        if requested_number:
            profile.customer_number = requested_number
        if category is not None:
            profile.category = category.strip() or "Privatkunde"
        if set_payment_term:
            profile.default_payment_term_id = default_payment_term_id
    return profile


def ensure_customer_profiles(db: Session, customers: list[Customer]) -> None:
    changed = False
    for customer in customers:
        if customer.profile is None:
            ensure_customer_profile(db, customer)
            changed = True
    if changed:
        db.commit()
