from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Customer, CustomerProfile
from .settings import issue_number


def compose_customer_name(salutation: str | None, title: str | None, first_name: str | None, last_name: str) -> str:
    """Setzt Customer.name aus salutation/title/first_name/last_name zusammen -- last_name
    ist das eigentliche Pflichtfeld (trägt bei Firmenkunden den Firmennamen), die übrigen
    drei sind optional und werden nur eingefügt, wenn sie tatsächlich gesetzt sind. Einzige
    Quelle für Customer.name -- weder create_customer() noch update_customer() nehmen name
    mehr direkt entgegen, siehe CLAUDE.md "Adressimport aus dem Altsystem"."""
    parts = [salutation, title, first_name, last_name]
    return " ".join(p.strip() for p in parts if p and p.strip())


class KundennameZuLang(ValueError):
    """Anrede, Titel, Vorname und Nachname zusammen länger als Customer.name (seit 1.9.362) -- Router: 422 mit dem Text."""


def kundenname(salutation: str | None, title: str | None, first_name: str | None, last_name: str) -> str:
    """compose_customer_name() mit Prüfung der Länge (seit 1.9.362, Rundgang gegen PostgreSQL): jedes Feld passt für sich, zusammen bis zu 508
    Zeichen in einer Spalte mit 255 -- unter PostgreSQL 500, unter SQLite still gespeichert. Der Adressimport lehnt eine solche Zeile seit 1.9.351
    ab (app/address_import.py::NAME_ZUSAMMEN), Anlegen und Ändern jetzt ebenso."""
    from .spaltenlaenge import laenge
    name = compose_customer_name(salutation, title, first_name, last_name)
    grenze = laenge(Customer.name)
    if len(name) > grenze:
        raise KundennameZuLang(f"Anrede, Titel, Vorname und Nachname sind zusammen zu lang ({len(name)} Zeichen, höchstens {grenze}).")
    return name


def next_customer_number(db: Session) -> str:
    """Vergibt die nächste automatische Kundennummer -- seit 1.8.73 über issue_number() (gesperrt, hochgezählt); vorher
    nur die Vorschau, zwei gleichzeitig angelegte Kunden bekamen dieselbe."""
    return issue_number(db, "customer")


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
