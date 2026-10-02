"""Adressbuch (seit 1.8.37, Stufe 2b, Runde 2b-2): Personen und Firmen, die an Projekten beteiligt sind,
ohne Kunde zu sein -- Architekt, Bauleitung des Auftraggebers, Hausverwaltung, Sachverständiger,
Versicherung, andere Gewerke. Welche Rolle ein Kontakt in einem Projekt hat, steht an der Zuordnung
(app/project_participants.py), nicht am Kontakt: dieselbe Hausverwaltung betreut viele Objekte.

Archivieren statt Löschen, sobald ein Kontakt in einem Projekt eingetragen ist (Betreibervorgabe):
delete_contact() lehnt dann ab (ContactInUseError), set_contact_archived() geht immer. Ein archivierter
Kontakt fehlt in der Auswahl beim Hinzufügen und lässt sich keinem Projekt neu zuordnen; wo er schon
eingetragen ist, bleibt er stehen (gekennzeichnet).

Seit 1.8.39 auch aus den Stammdaten: wählt das Büro beim Hinzufügen eines Beteiligten einen Kunden oder
Lieferanten, entsteht ein Eintrag mit Verweis darauf (linked_contact(), höchstens einer je Stammsatz,
UNIQUE), der in weiteren Projekten wiederverwendet wird. Name, E-Mail, Telefon und Adresse kommen bei jedem
Lesen aus dem Stammsatz (contact_values()) -- die eigenen Spalten dafür bleiben leer, keine Kopie -- und
sind am Eintrag nicht änderbar (update_contact()); eigen bleiben Funktion und Archiv. Suche und
Sortierung brauchen dafür Kunde und Lieferant im Statement (with_sources()).

Rollenlos wie jede Geschäftslogik; wer darf, entscheidet app/routers/contacts.py (nur Büro).
"""

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .models import Contact, Customer, Project, ProjectParticipant, Supplier

KINDS = {"person": "Person", "firma": "Firma"}
FIELDS = ("kind", "company_name", "first_name", "last_name", "function", "phone", "mobile", "email",
          "street", "postal_code", "city")
# Bei einem Eintrag mit Verweis kommen diese aus dem Stammsatz; eigen bleibt nur die Funktion.
SOURCE_FIELDS = tuple(f for f in FIELDS if f != "function")
SOURCES = {"customer": "aus Kundenstamm", "supplier": "aus Lieferantenstamm"}


class ContactInUseError(ValueError):
    """Der Kontakt ist in mindestens einem Projekt eingetragen -- archivieren statt löschen."""


def contact_source(contact: Contact) -> str | None:
    """"customer", "supplier" oder None (eigener Eintrag des Adressbuchs)."""
    if contact.customer_id is not None or contact.customer is not None:
        return "customer"
    if contact.supplier_id is not None or contact.supplier is not None:
        return "supplier"
    return None


def _customer_values(customer: Customer) -> dict:
    """Ein Firmenkunde trägt den Firmennamen in last_name, ohne Vorname (app/crm.py)."""
    person = bool(customer.first_name) or bool(customer.salutation and customer.salutation != "Firma")
    return {
        "kind": "person" if person else "firma", "company_name": None if person else customer.last_name,
        "first_name": customer.first_name if person else None, "last_name": customer.last_name if person else None,
        "phone": customer.phone, "mobile": customer.mobile, "email": customer.email, "street": customer.street,
        "postal_code": customer.postal_code, "city": customer.city,
    }


def _supplier_values(supplier: Supplier) -> dict:
    return {
        "kind": "firma", "company_name": supplier.name, "first_name": None, "last_name": None,
        "phone": supplier.phone, "mobile": None, "email": supplier.email, "street": supplier.street,
        "postal_code": supplier.postal_code, "city": supplier.city,
    }


def contact_values(contact: Contact) -> dict:
    """Die geltenden Werte der Felder in FIELDS: bei einem Eintrag mit Verweis Name, Kontaktwege und Adresse
    aus dem Stammsatz (bei jedem Lesen, keine Kopie), die Funktion vom Eintrag."""
    source = contact_source(contact)
    if source == "customer":
        values = _customer_values(contact.customer)
    elif source == "supplier":
        values = _supplier_values(contact.supplier)
    else:
        return {key: getattr(contact, key) for key in FIELDS}
    return {**values, "function": contact.function}


def contact_display_name(contact: Contact) -> str:
    """Person: "Vorname Nachname"; Firma: der Firmenname; mit Verweis der Name des Stammsatzes (beim Kunden
    samt Anrede und Titel, wie überall sonst)."""
    source = contact_source(contact)
    if source == "customer":
        return contact.customer.name or ""
    if source == "supplier":
        return contact.supplier.name or ""
    if contact.kind == "firma":
        return contact.company_name or ""
    return " ".join(x for x in (contact.first_name, contact.last_name) if x)


def with_sources(stmt):
    """Hängt Kunde und Lieferant eines Eintrags mit Verweis an (outer join, je höchstens eine Zeile) --
    Voraussetzung für contact_search_filter() und contact_sort_columns()."""
    return (stmt.outerjoin(Customer, Customer.id == Contact.customer_id)
            .outerjoin(Supplier, Supplier.id == Contact.supplier_id))


def contact_search_filter(term: str):
    """Ein Suchbegriff gegen Name, Firma, Funktion, Kontaktwege und Ort -- Adressbuch-Liste, Auswahl in der
    Projektmappe und Büro-Suche (app/search.py) suchen gleich; bei einem Eintrag mit Verweis in den Werten
    des Stammsatzes. Das Statement braucht with_sources()."""
    pattern = f"%{term}%"
    return or_(
        Contact.company_name.ilike(pattern), Contact.first_name.ilike(pattern), Contact.last_name.ilike(pattern),
        Contact.function.ilike(pattern), Contact.email.ilike(pattern), Contact.phone.ilike(pattern),
        Contact.mobile.ilike(pattern), Contact.city.ilike(pattern),
        (func.coalesce(Contact.first_name, "") + " " + func.coalesce(Contact.last_name, "")).ilike(pattern),
        Customer.name.ilike(pattern), Customer.email.ilike(pattern), Customer.phone.ilike(pattern),
        Customer.mobile.ilike(pattern), Customer.city.ilike(pattern),
        Supplier.name.ilike(pattern), Supplier.email.ilike(pattern), Supplier.phone.ilike(pattern),
        Supplier.city.ilike(pattern),
    )


def contact_sort_columns() -> tuple:
    """Nachname bzw. Firmenname, dann Vorname -- mit Verweis die des Stammsatzes. Braucht with_sources()."""
    return (func.lower(func.coalesce(Contact.last_name, Contact.company_name, Customer.last_name, Supplier.name, "")),
            func.lower(func.coalesce(Contact.first_name, Customer.first_name, "")))


def contact_load_options() -> tuple:
    """Stammsätze mitladen -- contact_to_dict() liest sie je Eintrag."""
    return (selectinload(Contact.customer), selectinload(Contact.supplier))


def _clean(values: dict) -> dict:
    out = {}
    for key, value in values.items():
        if key not in FIELDS:
            continue
        if isinstance(value, str):
            value = value.strip() or None
        out[key] = value
    return out


def _check_complete(contact: Contact) -> None:
    if contact.kind not in KINDS:
        raise ValueError("Die Art des Kontakts muss Person oder Firma sein.")
    if contact.kind == "person" and not contact.last_name:
        raise ValueError("Bei einer Person ist der Nachname Pflicht.")
    if contact.kind == "firma" and not contact.company_name:
        raise ValueError("Bei einer Firma ist der Firmenname Pflicht.")


def usage_counts(db: Session, contact_ids: list[int]) -> dict[int, int]:
    """Anzahl der Projekte je Kontakt (ein Projekt zählt einmal, auch mit zwei Rollen)."""
    if not contact_ids:
        return {}
    rows = db.execute(
        select(ProjectParticipant.contact_id, func.count(func.distinct(ProjectParticipant.project_id)))
        .where(ProjectParticipant.contact_id.in_(contact_ids))
        .group_by(ProjectParticipant.contact_id)
    )
    return {contact_id: count for contact_id, count in rows}


def source_info(contact: Contact) -> dict:
    """Herkunft eines Eintrags: Stammsatz, Hinweis ("aus Kundenstamm"), Link, und ob der Stammsatz archiviert
    ist (beim Lieferanten "inaktiv"; Kunden kennen keinen Archivstatus)."""
    source = contact_source(contact)
    if source == "customer":
        return {"source": source, "source_label": SOURCES[source], "source_id": contact.customer_id,
                "source_url": f"/customers/{contact.customer_id}", "source_archived": False}
    if source == "supplier":
        return {"source": source, "source_label": SOURCES[source], "source_id": contact.supplier_id,
                "source_url": f"/master-data/suppliers/{contact.supplier_id}/edit",
                "source_archived": not contact.supplier.active}
    return {"source": None, "source_label": None, "source_id": None, "source_url": None, "source_archived": False}


def contact_to_dict(contact: Contact, project_count: int = 0) -> dict:
    values = contact_values(contact)
    return {
        "id": contact.id, **values, "kind_label": KINDS.get(values["kind"], values["kind"]),
        "display_name": contact_display_name(contact), "archived": contact.archived,
        "archived_at": contact.archived_at, "project_count": project_count, **source_info(contact),
    }


def list_contacts(db: Session, *, search: str | None = None, include_archived: bool = False,
                  limit: int | None = None) -> list[dict]:
    stmt = with_sources(select(Contact)).options(*contact_load_options())
    if not include_archived:
        stmt = stmt.where(Contact.archived.is_(False))
    term = (search or "").strip()
    if term:
        stmt = stmt.where(contact_search_filter(term))
    stmt = stmt.order_by(*contact_sort_columns(), Contact.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    contacts = db.scalars(stmt).all()
    counts = usage_counts(db, [c.id for c in contacts])
    return [contact_to_dict(c, counts.get(c.id, 0)) for c in contacts]


def contact_projects(db: Session, contact_id: int) -> list[dict]:
    """Wo der Kontakt eingetragen ist -- je Zuordnung eine Zeile (Projekt und Rolle)."""
    from .project_participants import role_label

    rows = db.execute(
        select(ProjectParticipant, Project)
        .join(Project, Project.id == ProjectParticipant.project_id)
        .where(ProjectParticipant.contact_id == contact_id)
        .order_by(Project.project_number, ProjectParticipant.id)
    ).all()
    return [{"participant_id": p.id, "project_id": project.id, "project_number": project.project_number,
             "project_name": project.name, "project_archived": project.archived, "role": p.role,
             "role_label": role_label(p.role)} for p, project in rows]


def contact_detail(db: Session, contact: Contact) -> dict:
    projects = contact_projects(db, contact.id)
    return {**contact_to_dict(contact, len({p["project_id"] for p in projects})), "projects": projects}


def create_contact(db: Session, values: dict) -> Contact:
    contact = Contact(**_clean(values))
    contact.kind = contact.kind or "person"
    _check_complete(contact)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(db: Session, contact: Contact, values: dict) -> Contact:
    """values: nur die gesendeten Felder (Regel 22). Das Pflichtfeld der Art wird nach dem Zusammenführen
    geprüft -- wer die Art wechselt, muss das Pflichtfeld der neuen Art mitschicken oder schon haben.
    Mit Verweis auf einen Stammsatz ist nur die Funktion änderbar; der Rest wird dort gepflegt."""
    cleaned = _clean(values)
    source = contact_source(contact)
    if source is not None:
        if any(key in SOURCE_FIELDS for key in cleaned):
            stamm = "Kundenstamm" if source == "customer" else "Lieferantenstamm"
            raise ValueError(f"Name, E-Mail, Telefon und Adresse kommen aus dem {stamm} – bitte dort ändern.")
        for key, value in cleaned.items():
            setattr(contact, key, value)
        db.commit()
        db.refresh(contact)
        return contact
    for key, value in cleaned.items():
        setattr(contact, key, value)
    try:
        _check_complete(contact)
    except ValueError:
        db.rollback()
        raise
    db.commit()
    db.refresh(contact)
    return contact


def linked_contact(db: Session, *, customer: Customer | None = None, supplier: Supplier | None = None) -> Contact:
    """Der Adressbuch-Eintrag zu einem Kunden bzw. Lieferanten: der vorhandene, sonst ein neuer (ohne Commit).
    Höchstens einer je Stammsatz -- von zwei gleichzeitigen ersten Anfragen scheitert eine am UNIQUE-Constraint;
    SAVEPOINT, damit nur dieser Versuch zurückrollt, danach gilt der Eintrag der anderen (Muster Self-Seeding)."""
    if (customer is None) == (supplier is None):
        raise ValueError("Genau ein Kunde oder Lieferant.")
    column, value = (Contact.customer_id, customer.id) if customer is not None else (Contact.supplier_id, supplier.id)
    existing = db.scalar(select(Contact).where(column == value))
    if existing is not None:
        return existing
    # Die Art steht nur da, weil die Spalte kein NULL kennt; gelesen wird sie aus dem Stammsatz.
    kind = _customer_values(customer)["kind"] if customer is not None else "firma"
    contact = Contact(kind=kind, customer=customer, supplier=supplier)
    try:
        with db.begin_nested():
            db.add(contact)
    except IntegrityError:
        existing = db.scalar(select(Contact).where(column == value))
        if existing is None:
            raise
        return existing
    return contact


def set_contact_archived(db: Session, contact: Contact, archived: bool) -> Contact:
    from datetime import datetime

    if contact.archived != archived:
        contact.archived = archived
        contact.archived_at = datetime.utcnow() if archived else None
        db.commit()
        db.refresh(contact)
    return contact


def _in_use_text(count: int) -> str:
    return (f"Der Kontakt ist in {count} Projekt{'' if count == 1 else 'en'} eingetragen und kann nicht gelöscht "
            "werden – bitte archivieren.")


def delete_contact(db: Session, contact: Contact) -> None:
    count = usage_counts(db, [contact.id]).get(contact.id, 0)
    if count:
        raise ContactInUseError(_in_use_text(count))
    db.delete(contact)
    try:
        db.commit()
    except IntegrityError as exc:
        # Gleichzeitig eingetragen: unter PostgreSQL hält der Fremdschlüssel (SQLite erzwingt ihn hier nicht).
        db.rollback()
        raise ContactInUseError(_in_use_text(1)) from exc
