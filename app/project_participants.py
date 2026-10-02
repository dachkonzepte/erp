"""Beteiligte am Projekt (seit 1.8.37, Stufe 2b, Runde 2b-2): Zuordnung Projekt -- Kontakt (Adressbuch,
app/contacts.py) -- Rolle.

- Rollen fest im Code (ROLES, Betreibervorgabe), keine Auswahlliste in den Einstellungen: die Rolle
  entscheidet in den kommenden Runden mit, wer eine Behinderungs- oder Bedenkenanzeige bekommt. Die
  Schlüssel stehen in der Datenbank und werden nie umbenannt; die Beschriftungen dürfen sich ändern.
- Eindeutig je Projekt, Kontakt und Rolle (UNIQUE-Constraint); derselbe Kontakt darf in einem Projekt
  zwei Rollen haben (Eigentümer und Hausverwaltung in einer Person).
- Der Kunde ist Auftraggeber und wird nicht zusätzlich als Beteiligter geführt -- deshalb gibt es keine
  Rolle "Auftraggeber"; der Kunde ist kein Kontakt des Adressbuchs.
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

from sqlalchemy import case, select
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


class DuplicateParticipantError(ValueError):
    """Dieser Kontakt hat diese Rolle in diesem Projekt schon."""


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
        "contact": contact_to_dict(p.contact, counts.get(p.contact_id, 0)),
        "power_of_attorney": None if not p.poa_stored_filename else {
            "filename": p.poa_original_filename, "content_type": p.poa_content_type, "size_bytes": p.poa_size_bytes,
            "sha256": p.poa_sha256, "uploaded_at": p.poa_uploaded_at, "uploaded_by_name": p.poa_uploaded_by_name,
        },
        "created_at": p.created_at,
    }


def list_participants(db: Session, project_id: int) -> list[dict]:
    """In der Reihenfolge der Rollen (wie ROLES), darin nach Name."""
    from .contacts import contact_sort_columns, usage_counts

    order = case({key: index for index, key in enumerate(ROLES)}, value=ProjectParticipant.role, else_=len(ROLES))
    rows = db.scalars(
        select(ProjectParticipant).join(Contact, Contact.id == ProjectParticipant.contact_id)
        .where(ProjectParticipant.project_id == project_id)
        .options(selectinload(ProjectParticipant.contact))
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


def add_participant(db: Session, project: Project, contact: Contact, *, role: str, copy_on_notices: bool = False,
                    authorized_recipient: bool = False) -> ProjectParticipant:
    _check_role(role)
    if contact.archived:
        raise ValueError("Der Kontakt ist archiviert – bitte im Adressbuch erst wiederherstellen.")
    if _duplicate_exists(db, project.id, contact.id, role):
        raise DuplicateParticipantError(_duplicate_text(contact, role))
    participant = ProjectParticipant(
        project_id=project.id, contact_id=contact.id, role=role, copy_on_notices=bool(copy_on_notices),
        authorized_recipient=bool(authorized_recipient),
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


def update_participant(db: Session, participant: ProjectParticipant, values: dict) -> ProjectParticipant:
    """values: nur die gesendeten Felder (Regel 22) -- role, copy_on_notices, authorized_recipient."""
    if "role" in values:
        role = values["role"]
        _check_role(role)
        if role != participant.role and _duplicate_exists(db, participant.project_id, participant.contact_id, role,
                                                          except_id=participant.id):
            raise DuplicateParticipantError(_duplicate_text(participant.contact, role))
        participant.role = role
    for key in ("copy_on_notices", "authorized_recipient"):
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
    stored = participant.poa_stored_filename
    db.delete(participant)
    db.commit()
    if stored:
        power_of_attorney_path(stored).unlink(missing_ok=True)


def store_power_of_attorney(db: Session, participant: ProjectParticipant, *, filename: str | None, data: bytes,
                            user_name: str | None) -> ProjectParticipant:
    from .email_dispatch import receipt_content_type

    if not participant.authorized_recipient:
        raise ValueError("Eine Vollmacht gehört zur Empfangsvollmacht – bitte zuerst „empfangsbevollmächtigt“ setzen.")
    if not data:
        raise ValueError("Die Datei ist leer.")
    if len(data) > MAX_POWER_OF_ATTORNEY_BYTES:
        raise ValueError(f"Die Vollmacht ist größer als {MAX_POWER_OF_ATTORNEY_BYTES // 1_000_000} MB.")
    try:
        content_type = receipt_content_type(data)
    except ValueError as exc:
        raise ValueError("Die Vollmacht muss ein PDF oder ein Foto (JPEG, PNG, WebP) sein.") from exc
    original = (Path(filename or "").name or "vollmacht")[:255]
    stored = make_stored_filename(original)
    POWER_OF_ATTORNEY_ROOT.mkdir(parents=True, exist_ok=True)
    power_of_attorney_path(stored).write_bytes(data)
    old = participant.poa_stored_filename
    participant.poa_stored_filename = stored
    participant.poa_original_filename = original
    participant.poa_content_type = content_type
    participant.poa_size_bytes = len(data)
    participant.poa_sha256 = hashlib.sha256(data).hexdigest()
    participant.poa_uploaded_at = datetime.utcnow()
    participant.poa_uploaded_by_name = (user_name or "")[:255] or None
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


def remove_power_of_attorney(db: Session, participant: ProjectParticipant) -> ProjectParticipant:
    old = participant.poa_stored_filename
    if not old:
        return participant
    for key in ("poa_stored_filename", "poa_original_filename", "poa_content_type", "poa_size_bytes", "poa_sha256",
                "poa_uploaded_at", "poa_uploaded_by_name"):
        setattr(participant, key, None)
    db.commit()
    power_of_attorney_path(old).unlink(missing_ok=True)
    db.refresh(participant)
    return participant


def delete_participants_of_project(db: Session, project_id: int) -> list[str]:
    """Für delete_project(): Zeilen löschen (ohne Commit), Dateinamen der Belege zurückgeben -- die
    Dateien entfernt der Aufrufer erst nach dem Commit."""
    rows = db.scalars(select(ProjectParticipant).where(ProjectParticipant.project_id == project_id)).all()
    stored = [p.poa_stored_filename for p in rows if p.poa_stored_filename]
    for p in rows:
        db.delete(p)
    db.flush()  # vor dem Projekt -- ohne Relationship kennt der Flush die Reihenfolge nicht sicher
    return stored
