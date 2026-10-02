"""Adressbuch (seit 1.8.37, Stufe 2b, Runde 2b-2): Personen und Firmen, die an Projekten beteiligt sind,
ohne Kunde zu sein -- Architekt, Bauleitung des Auftraggebers, Hausverwaltung, Sachverständiger,
Versicherung, andere Gewerke. Welche Rolle ein Kontakt in einem Projekt hat, steht an der Zuordnung
(app/project_participants.py), nicht am Kontakt: dieselbe Hausverwaltung betreut viele Objekte.

Archivieren statt Löschen, sobald ein Kontakt in einem Projekt eingetragen ist (Betreibervorgabe):
delete_contact() lehnt dann ab (ContactInUseError), set_contact_archived() geht immer. Ein archivierter
Kontakt fehlt in der Auswahl beim Hinzufügen und lässt sich keinem Projekt neu zuordnen; wo er schon
eingetragen ist, bleibt er stehen (gekennzeichnet).

Rollenlos wie jede Geschäftslogik; wer darf, entscheidet app/routers/contacts.py (nur Büro).
"""

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Contact, Project, ProjectParticipant

KINDS = {"person": "Person", "firma": "Firma"}
FIELDS = ("kind", "company_name", "first_name", "last_name", "function", "phone", "mobile", "email",
          "street", "postal_code", "city")


class ContactInUseError(ValueError):
    """Der Kontakt ist in mindestens einem Projekt eingetragen -- archivieren statt löschen."""


def contact_display_name(contact: Contact) -> str:
    """Person: "Vorname Nachname"; Firma: der Firmenname."""
    if contact.kind == "firma":
        return contact.company_name or ""
    return " ".join(x for x in (contact.first_name, contact.last_name) if x)


def contact_search_filter(term: str):
    """Ein Suchbegriff gegen Name, Firma, Funktion, Kontaktwege und Ort -- Adressbuch-Liste, Auswahl in der
    Projektmappe und Büro-Suche (app/search.py) suchen gleich."""
    pattern = f"%{term}%"
    return or_(
        Contact.company_name.ilike(pattern), Contact.first_name.ilike(pattern), Contact.last_name.ilike(pattern),
        Contact.function.ilike(pattern), Contact.email.ilike(pattern), Contact.phone.ilike(pattern),
        Contact.mobile.ilike(pattern), Contact.city.ilike(pattern),
        (func.coalesce(Contact.first_name, "") + " " + func.coalesce(Contact.last_name, "")).ilike(pattern),
    )


def contact_sort_columns() -> tuple:
    """Nachname bzw. Firmenname, dann Vorname."""
    return (func.lower(func.coalesce(Contact.last_name, Contact.company_name, "")),
            func.lower(func.coalesce(Contact.first_name, "")))


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


def contact_to_dict(contact: Contact, project_count: int = 0) -> dict:
    return {
        "id": contact.id, "kind": contact.kind, "kind_label": KINDS.get(contact.kind, contact.kind),
        "display_name": contact_display_name(contact), "company_name": contact.company_name,
        "first_name": contact.first_name, "last_name": contact.last_name, "function": contact.function,
        "phone": contact.phone, "mobile": contact.mobile, "email": contact.email, "street": contact.street,
        "postal_code": contact.postal_code, "city": contact.city, "archived": contact.archived,
        "archived_at": contact.archived_at, "project_count": project_count,
    }


def list_contacts(db: Session, *, search: str | None = None, include_archived: bool = False,
                  limit: int | None = None) -> list[dict]:
    stmt = select(Contact)
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
    geprüft -- wer die Art wechselt, muss das Pflichtfeld der neuen Art mitschicken oder schon haben."""
    for key, value in _clean(values).items():
        setattr(contact, key, value)
    try:
        _check_complete(contact)
    except ValueError:
        db.rollback()
        raise
    db.commit()
    db.refresh(contact)
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
