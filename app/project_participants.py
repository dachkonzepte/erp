"""Beteiligte am Projekt (seit 1.8.37, Stufe 2b, Runde 2b-2): Zuordnung Projekt -- Kontakt (Adressbuch,
app/contacts.py) -- Rolle.

- Rollen fest im Code (ROLES, Betreibervorgabe), keine Auswahlliste in den Einstellungen: die Rolle
  entscheidet in den kommenden Runden mit, wer eine Behinderungs- oder Bedenkenanzeige bekommt. Die
  Schlüssel stehen in der Datenbank und werden nie umbenannt; die Beschriftungen dürfen sich ändern.
- Eindeutig je Projekt, Kontakt und Rolle (UNIQUE-Constraint); derselbe Kontakt darf in einem Projekt
  zwei Rollen haben (Eigentümer und Hausverwaltung in einer Person).
- Der Kunde ist Auftraggeber und wird nicht zusätzlich als Beteiligter geführt -- deshalb gibt es keine
  Rolle "Auftraggeber". Seit 1.8.39 kann ein Kunde zwar über einen Adressbuch-Eintrag mit Verweis Beteiligter
  eines fremden Projekts sein (Hausverwaltung, die selbst Kunde ist), nie aber in seinem eigenen
  (check_not_client()).
- Seit 1.8.39 durchsucht der Dialog "Beteiligten hinzufügen" Adressbuch, Kunden und Lieferanten, nach
  Herkunft gruppiert (participant_candidates()); welche Quellen eine Rolle sehen darf, entscheidet der Router
  mit derselben Prüfung wie die Büro-Suche (app/search.py::office_source_visible()). Mitarbeiter nicht.
- "Kopie bei Anzeigen" (copy_on_notices) und "empfangsbevollmächtigt für den Auftraggeber"
  (authorized_recipient) sind zwei unabhängige Häkchen. Zur Empfangsvollmacht kann die Vollmacht als
  Beleg hochgeladen werden (PDF oder Foto, am Inhalt erkannt wie der Beleg einer Zustellung). Hochladen
  nur mit gesetztem Häkchen; wird es später entfernt, bleibt der Beleg (er ist ein Dokument, keine
  Einstellung) und lässt sich ausdrücklich entfernen.

Rollenlos wie jede Geschäftslogik; wer darf, entscheidet app/routers/project_participants.py (nur Büro).
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .document_storage import make_stored_filename
from .models import Contact, Project, ProjectParticipant
from .paths import data_dir

ROLES = {
    "architekt_planer": "Architekt/Planer",
    "bauleitung_ag": "Bauleitung des Auftraggebers",
    "hausverwaltung": "Hausverwaltung",
    "eigentuemer": "Eigentümer",
    "sachverstaendiger": "Sachverständiger/Gutachter",
    "versicherung": "Versicherung",
    "anderes_gewerk": "Anderes Gewerk",
    "sonstiges": "Sonstiges",
}

POWER_OF_ATTORNEY_ROOT = Path(os.getenv("DACHKONZEPTE_PARTICIPANT_FILE_ROOT", data_dir() / "participant_documents"))
MAX_POWER_OF_ATTORNEY_BYTES = 15_000_000  # wie der Beleg einer Zustellung


CANDIDATE_LIMIT = 20

# Quellen des Dialogs "Beteiligten hinzufügen", Schlüssel wie in der Büro-Suche (app/search.py) -- Mitarbeiter
# bewusst nicht: sie sind Betrieb, keine Beteiligten.
CANDIDATE_SOURCES = ("contacts", "customers", "suppliers")


class DuplicateParticipantError(ValueError):
    """Dieser Kontakt hat diese Rolle in diesem Projekt schon."""


# Zwei Vollmachten am Beteiligten, je Häkchen und Beleg (Spalten mit eigenem Präfix): die Empfangsvollmacht (seit 1.8.37,
# Anzeigen und Zustellung) und die Vollmacht zur Abnahme (seit 1.8.47, nur sie zählt beim Erfassen einer Abnahme).
POA_KINDS = {
    "empfang": {"flag": "authorized_recipient", "prefix": "poa_", "label": "Empfangsvollmacht",
                "missing_flag": "Eine Vollmacht gehört zur Empfangsvollmacht – bitte zuerst „empfangsbevollmächtigt“ setzen.",
                "invalid": "Die Vollmacht muss ein PDF oder ein Foto (JPEG, PNG, WebP) sein."},
    "abnahme": {"flag": "acceptance_authorized", "prefix": "acceptance_poa_", "label": "Vollmacht zur Abnahme",
                "missing_flag": "Der Beleg gehört zur Vollmacht zur Abnahme – bitte zuerst „Vollmacht zur Abnahme“ setzen.",
                "invalid": "Die Vollmacht zur Abnahme muss ein PDF oder ein Foto (JPEG, PNG, WebP) sein."},
}
_POA_COLUMNS = ("stored_filename", "original_filename", "content_type", "size_bytes", "sha256", "uploaded_at",
                "uploaded_by_name")


def poa_value(participant: ProjectParticipant, kind: str, column: str):
    return getattr(participant, POA_KINDS[kind]["prefix"] + column)


def poa_to_dict(participant: ProjectParticipant, kind: str) -> dict | None:
    if not poa_value(participant, kind, "stored_filename"):
        return None
    return {"filename": poa_value(participant, kind, "original_filename"),
            "content_type": poa_value(participant, kind, "content_type"),
            "size_bytes": poa_value(participant, kind, "size_bytes"), "sha256": poa_value(participant, kind, "sha256"),
            "uploaded_at": poa_value(participant, kind, "uploaded_at"),
            "uploaded_by_name": poa_value(participant, kind, "uploaded_by_name")}


class ParticipantInUseError(ValueError):
    """Der Beteiligte hat eine Abnahme erklärt (seit 1.8.46) -- er bleibt im Projekt, Router: 409."""


def role_label(role: str) -> str:
    return ROLES.get(role, role)


def roles_list() -> list[dict]:
    return [{"key": key, "label": label} for key, label in ROLES.items()]


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise ValueError("Unbekannte Rolle.")


def power_of_attorney_path(stored_filename: str) -> Path:
    return POWER_OF_ATTORNEY_ROOT / stored_filename


def participant_to_dict(db: Session, p: ProjectParticipant, counts: dict[int, int] | None = None) -> dict:
    """counts: Projekte je Kontakt, falls schon für mehrere gezählt (list_participants), sonst hier."""
    from .contacts import contact_to_dict, usage_counts

    if counts is None:
        counts = usage_counts(db, [p.contact_id])
    return {
        "id": p.id, "project_id": p.project_id, "contact_id": p.contact_id, "role": p.role,
        "role_label": role_label(p.role), "copy_on_notices": p.copy_on_notices,
        "authorized_recipient": p.authorized_recipient,
        "acceptance_authorized": p.acceptance_authorized,
        "contact": contact_to_dict(p.contact, counts.get(p.contact_id, 0)),
        "power_of_attorney": poa_to_dict(p, "empfang"),
        "acceptance_power_of_attorney": poa_to_dict(p, "abnahme"),  # seit 1.8.47
        "created_at": p.created_at,
    }


def list_participants(db: Session, project_id: int) -> list[dict]:
    """In der Reihenfolge der Rollen (wie ROLES), darin nach Name."""
    from .contacts import contact_sort_columns, usage_counts, with_sources

    order = case({key: index for index, key in enumerate(ROLES)}, value=ProjectParticipant.role, else_=len(ROLES))
    rows = db.scalars(
        with_sources(select(ProjectParticipant).join(Contact, Contact.id == ProjectParticipant.contact_id))
        .where(ProjectParticipant.project_id == project_id)
        .options(selectinload(ProjectParticipant.contact).selectinload(Contact.customer),
                 selectinload(ProjectParticipant.contact).selectinload(Contact.supplier))
        .order_by(order, *contact_sort_columns(), ProjectParticipant.id)
    ).all()
    counts = usage_counts(db, sorted({p.contact_id for p in rows}))
    return [participant_to_dict(db, p, counts) for p in rows]


def _duplicate_exists(db: Session, project_id: int, contact_id: int, role: str, *, except_id: int | None = None) -> bool:
    stmt = select(ProjectParticipant.id).where(
        ProjectParticipant.project_id == project_id, ProjectParticipant.contact_id == contact_id,
        ProjectParticipant.role == role,
    )
    if except_id is not None:
        stmt = stmt.where(ProjectParticipant.id != except_id)
    return db.scalar(stmt.limit(1)) is not None


def _duplicate_text(contact: Contact, role: str) -> str:
    from .contacts import contact_display_name

    return f"{contact_display_name(contact)} ist in diesem Projekt bereits als {role_label(role)} eingetragen."


def check_not_client(project: Project, customer_id: int | None) -> None:
    """Der Kunde des Projekts ist Auftraggeber und wird nicht zusätzlich Beteiligter (Betreibervorgabe)."""
    if customer_id is not None and customer_id == project.customer_id:
        raise ValueError("Der Kunde dieses Projekts ist Auftraggeber und kann nicht zusätzlich Beteiligter sein.")


class ClientChangeConflict(ValueError):
    """Der neue Kunde des Projekts ist dort schon Beteiligter -- Router: 409."""


def check_client_change(db: Session, project: Project, new_customer_id: int) -> None:
    """Kundenwechsel am Projekt (seit 1.8.41, 1.8.39 Nebenbefund 1): ist der neue Kunde über seinen Adressbuch-Eintrag
    schon Beteiligter, stünde der Auftraggeber doppelt da. Festlegung: ablehnen und nennen, wo er eingetragen ist --
    das Büro entfernt ihn im Reiter "Beteiligte" bewusst (Kopie bei Anzeigen, Vollmacht gingen sonst still verloren).
    Seit 1.8.44 zuerst: hat ein Auftrag des Projekts einen festgeschriebenen Vertrag (mindestens eine Fassung), ist
    der Kunde Vertragspartner -- kein Wechsel. Wirft ClientChangeConflict."""
    from .contacts import contact_display_name
    from .models import Order, OrderContract, OrderContractVersion

    if new_customer_id == project.customer_id:
        return
    frozen = db.execute(
        select(Order.order_number, func.max(OrderContractVersion.version_no))
        .join(OrderContract, OrderContract.order_id == Order.id)
        .join(OrderContractVersion, OrderContractVersion.contract_id == OrderContract.id)
        .where(Order.project_id == project.id)
        .group_by(Order.order_number).order_by(Order.order_number)
    ).first()
    if frozen is not None:
        raise ClientChangeConflict(
            f"Auftrag {frozen[0]} hat einen festgeschriebenen Vertrag (Fassung {frozen[1]}) – der Kunde ist dort "
            "Vertragspartner und lässt sich im Projekt nicht mehr wechseln."
        )
    rows = db.scalars(
        select(ProjectParticipant).join(Contact, Contact.id == ProjectParticipant.contact_id)
        .where(ProjectParticipant.project_id == project.id, Contact.customer_id == new_customer_id)
        .options(selectinload(ProjectParticipant.contact).selectinload(Contact.customer))
        .order_by(ProjectParticipant.id)
    ).all()
    if rows:
        name = contact_display_name(rows[0].contact)
        roles = ", ".join(role_label(p.role) for p in rows)
        raise ClientChangeConflict(
            f"{name} ist in diesem Projekt schon Beteiligter ({roles}) und stünde als Auftraggeber doppelt da. "
            "Bitte zuerst im Reiter „Beteiligte“ entfernen, dann den Kunden wechseln."
        )


def participant_rows(db: Session, project_id: int) -> list[ProjectParticipant]:
    """Beteiligte eines Projekts in der Reihenfolge der Rollen (wie ROLES), mit Kontakt und dessen Stammsatz geladen."""
    rows = db.scalars(
        select(ProjectParticipant).where(ProjectParticipant.project_id == project_id)
        .options(selectinload(ProjectParticipant.contact).selectinload(Contact.customer),
                 selectinload(ProjectParticipant.contact).selectinload(Contact.supplier))
    ).all()
    order = {key: i for i, key in enumerate(ROLES)}
    return sorted(rows, key=lambda p: (order.get(p.role, len(order)), p.id))


def participant_info(p: ProjectParticipant) -> dict:
    """Kurzform für Anzeigen und Zustellungen (seit 1.8.40 in app/notice_letters.py, seit 1.8.41 hier):
    Name und E-Mail live aus dem Kontakt bzw. seinem Stammsatz, Rolle, Häkchen, ob eine Vollmacht hinterlegt ist."""
    from .contacts import contact_display_name, contact_values

    return {
        "participant_id": p.id, "name": contact_display_name(p.contact), "role": p.role,
        "role_label": role_label(p.role), "email": (contact_values(p.contact)["email"] or "").strip() or None,
        "copy_on_notices": p.copy_on_notices, "authorized": p.authorized_recipient,
        "has_poa": bool(p.poa_stored_filename), "archived": p.contact.archived,
        "acceptance_authorized": p.acceptance_authorized, "has_acceptance_poa": bool(p.acceptance_poa_stored_filename),
    }


def add_participant(db: Session, project: Project, contact: Contact, *, role: str, copy_on_notices: bool = False,
                    authorized_recipient: bool = False, acceptance_authorized: bool = False) -> ProjectParticipant:
    _check_role(role)
    check_not_client(project, contact.customer_id)
    if contact.archived:
        raise ValueError("Der Kontakt ist archiviert – bitte im Adressbuch erst wiederherstellen.")
    if _duplicate_exists(db, project.id, contact.id, role):
        raise DuplicateParticipantError(_duplicate_text(contact, role))
    participant = ProjectParticipant(
        project_id=project.id, contact_id=contact.id, role=role, copy_on_notices=bool(copy_on_notices),
        authorized_recipient=bool(authorized_recipient), acceptance_authorized=bool(acceptance_authorized),
    )
    try:
        # Zwei gleichzeitige Anfragen kommen beide an der Prüfung oben vorbei -- die zweite scheitert
        # am UNIQUE-Constraint; SAVEPOINT, damit nur dieser Versuch zurückrollt (Muster Self-Seeding).
        with db.begin_nested():
            db.add(participant)
    except IntegrityError as exc:
        raise DuplicateParticipantError(_duplicate_text(contact, role)) from exc
    db.commit()
    db.refresh(participant)
    return participant


def _candidate_contact_hit(contact: Contact, *, blocked: str | None = None) -> dict:
    from .contacts import contact_display_name, contact_values, source_info

    values, source = contact_values(contact), source_info(contact)
    firma = values["company_name"] if values["kind"] == "person" else None
    return {
        "contact_id": contact.id, "customer_id": contact.customer_id, "supplier_id": contact.supplier_id,
        "title": contact_display_name(contact),
        "subtitle": " · ".join(x for x in (values["function"], firma, values["city"]) if x) or None,
        "source_archived": source["source_archived"], "contact_archived": contact.archived, "blocked": blocked,
    }


def participant_candidates(db: Session, project: Project, term: str, *, sources: list[str],
                           limit: int = CANDIDATE_LIMIT) -> list[dict]:
    """Der Dialog "Beteiligten hinzufügen": Treffer nach Herkunft gruppiert -- Adressbuch (eigene Einträge, ohne
    archivierte), Kunden, Lieferanten. sources: die Schlüssel, die die Rolle sehen darf (entscheidet der Router).

    Kunden und Lieferanten über dieselbe Suche wie in der Büro-Suche (query_fn der Quelle), erst ab
    MIN_QUERY_LENGTH Zeichen; ein leerer Suchbegriff zeigt nur das Adressbuch (wie bisher). Ein Kunde oder
    Lieferant mit Adressbuch-Eintrag erscheint unter seiner Herkunft, mit contact_id. Nicht wählbar
    (blocked mit Grund): der Kunde des Projekts und ein Stammsatz, dessen Eintrag im Adressbuch archiviert ist.
    Ein archivierter (inaktiver) Lieferant bleibt wählbar und ist gekennzeichnet."""
    from .contacts import (
        contact_load_options, contact_search_filter, contact_sort_columns, with_sources,
    )
    from .search import MIN_QUERY_LENGTH, office_source

    term = (term or "").strip()
    groups = []
    if "contacts" in sources:
        stmt = (with_sources(select(Contact))
                .where(Contact.archived.is_(False), Contact.customer_id.is_(None), Contact.supplier_id.is_(None)))
        if term:
            stmt = stmt.where(contact_search_filter(term))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(stmt.options(*contact_load_options())
                          .order_by(*contact_sort_columns(), Contact.id).limit(limit)).all()
        groups.append({"key": "contacts", "label": office_source("contacts").label, "total": total,
                       "hits": [_candidate_contact_hit(c) for c in rows]})
    if len(term) >= MIN_QUERY_LENGTH:
        for key, column in (("customers", Contact.customer_id), ("suppliers", Contact.supplier_id)):
            if key not in sources:
                continue
            source = office_source(key)
            total, rows = source.query_fn(db, term, limit)
            linked = {}
            if rows:
                linked = {getattr(c, column.key): c for c in db.scalars(
                    select(Contact).where(column.in_([r.id for r in rows])).options(*contact_load_options()))}
            hits = []
            for row in rows:
                contact = linked.get(row.id)
                blocked = None
                if key == "customers" and row.id == project.customer_id:
                    blocked = "Auftraggeber dieses Projekts"
                elif contact is not None and contact.archived:
                    blocked = "im Adressbuch archiviert – dort erst wiederherstellen"
                if contact is not None:
                    hits.append(_candidate_contact_hit(contact, blocked=blocked))
                    continue
                hits.append({
                    "contact_id": None, "customer_id": row.id if key == "customers" else None,
                    "supplier_id": row.id if key == "suppliers" else None, "title": row.name,
                    "subtitle": row.city or None, "source_archived": key == "suppliers" and not row.active,
                    "contact_archived": False, "blocked": blocked,
                })
            groups.append({"key": key, "label": source.label, "total": total, "hits": hits})
    return groups


def update_participant(db: Session, participant: ProjectParticipant, values: dict) -> ProjectParticipant:
    """values: nur die gesendeten Felder (Regel 22) -- role, copy_on_notices, authorized_recipient, seit 1.8.47
    acceptance_authorized."""
    if "role" in values:
        role = values["role"]
        _check_role(role)
        if role != participant.role and _duplicate_exists(db, participant.project_id, participant.contact_id, role,
                                                          except_id=participant.id):
            raise DuplicateParticipantError(_duplicate_text(participant.contact, role))
        participant.role = role
    for key in ("copy_on_notices", "authorized_recipient", "acceptance_authorized"):
        if key in values:
            setattr(participant, key, bool(values[key]))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateParticipantError(_duplicate_text(participant.contact, values.get("role", participant.role))) from exc
    db.refresh(participant)
    return participant


def remove_participant(db: Session, participant: ProjectParticipant) -> None:
    from .acceptances import acceptances_declared_by

    if acceptances_declared_by(db, participant.id):
        # Die Abnahme verweist auf ihn (Fremdschlüssel) und bleibt unverändert -- auch eine verworfene.
        raise ParticipantInUseError("Dieser Beteiligte hat eine Abnahme erklärt und bleibt deshalb im Projekt.")
    from .models import DefectEvent

    if db.scalar(select(DefectEvent.id).where(DefectEvent.participant_id == participant.id).limit(1)):
        # Seit 1.8.49: ebenso, wenn er die Beseitigung eines Mangels abgenommen hat.
        raise ParticipantInUseError("Dieser Beteiligte hat die Beseitigung eines Mangels abgenommen und bleibt deshalb "
                                    "im Projekt.")
    from .models import ChecklistAttachment

    if db.scalar(select(ChecklistAttachment.id).where(ChecklistAttachment.signer_participant_id == participant.id).limit(1)):
        # Seit 1.8.57: ebenso, wenn er eine Checkliste unterschrieben hat (die Unterschrift verweist auf ihn).
        raise ParticipantInUseError("Dieser Beteiligte hat eine Checkliste unterschrieben und bleibt deshalb im Projekt.")
    stored = [x for x in (participant.poa_stored_filename, participant.acceptance_poa_stored_filename) if x]
    db.delete(participant)
    db.commit()
    for name in stored:
        power_of_attorney_path(name).unlink(missing_ok=True)


def store_power_of_attorney(db: Session, participant: ProjectParticipant, *, filename: str | None, data: bytes,
                            user_name: str | None, kind: str = "empfang") -> ProjectParticipant:
    """Beleg einer Vollmacht hinterlegen; kind "empfang" (Empfangsvollmacht) oder seit 1.8.47 "abnahme" (Vollmacht zur
    Abnahme) -- je mit eigenem Häkchen, das vorher gesetzt sein muss."""
    from .email_dispatch import receipt_content_type

    spec = POA_KINDS[kind]
    if not getattr(participant, spec["flag"]):
        raise ValueError(spec["missing_flag"])
    if not data:
        raise ValueError("Die Datei ist leer.")
    if len(data) > MAX_POWER_OF_ATTORNEY_BYTES:
        raise ValueError(f"Die Vollmacht ist größer als {MAX_POWER_OF_ATTORNEY_BYTES // 1_000_000} MB.")
    try:
        content_type = receipt_content_type(data)
    except ValueError as exc:
        raise ValueError(spec["invalid"]) from exc
    original = (Path(filename or "").name or "vollmacht")[:255]
    stored = make_stored_filename(original)
    POWER_OF_ATTORNEY_ROOT.mkdir(parents=True, exist_ok=True)
    power_of_attorney_path(stored).write_bytes(data)
    old = poa_value(participant, kind, "stored_filename")
    values = {"stored_filename": stored, "original_filename": original, "content_type": content_type,
              "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "uploaded_at": datetime.utcnow(),
              "uploaded_by_name": (user_name or "")[:255] or None}
    for column, value in values.items():
        setattr(participant, spec["prefix"] + column, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        power_of_attorney_path(stored).unlink(missing_ok=True)
        raise
    if old:
        power_of_attorney_path(old).unlink(missing_ok=True)
    db.refresh(participant)
    return participant


def remove_power_of_attorney(db: Session, participant: ProjectParticipant, kind: str = "empfang") -> ProjectParticipant:
    old = poa_value(participant, kind, "stored_filename")
    if not old:
        return participant
    for column in _POA_COLUMNS:
        setattr(participant, POA_KINDS[kind]["prefix"] + column, None)
    db.commit()
    power_of_attorney_path(old).unlink(missing_ok=True)
    db.refresh(participant)
    return participant


def delete_participants_of_project(db: Session, project_id: int) -> list[str]:
    """Für delete_project(): Zeilen löschen (ohne Commit), Dateinamen der Belege zurückgeben -- die
    Dateien entfernt der Aufrufer erst nach dem Commit."""
    rows = db.scalars(select(ProjectParticipant).where(ProjectParticipant.project_id == project_id)).all()
    stored = [name for p in rows for name in (p.poa_stored_filename, p.acceptance_poa_stored_filename) if name]
    for p in rows:
        db.delete(p)
    db.flush()  # vor dem Projekt -- ohne Relationship kennt der Flush die Reihenfolge nicht sicher
    return stored
