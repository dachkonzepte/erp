"""Kalender-Modul (Modul "kalender", seit 1.7.0) -- Büro-Termine (Besichtigung/Aufmaß/
Besprechung u. Ä.), bewusst GETRENNT von der Plantafel (app/planning.py bleibt ausschließlich
für Einsatz-/Feldplanung, siehe CalendarEvent-Klassendocstring in app/models.py und CLAUDE.md
"Kalender" für die vollständige Herleitung).

Nur Stufe 1 (Termin anlegen/verwalten, Tag-/Wochen-/Monatsansicht, Privatsphäre-Redaktion,
Projekt-/Angebot-Zuordnung) -- Stufe 2 (Outlook-Synchronisation über Microsoft Graph) ist reiner
Befund in CLAUDE.md, hier bewusst nicht gebaut.

**Privatsphäre, serverseitig, nicht nur in der Anzeige**: list_events_for_range()/
list_events_for_project()/list_events_for_quote() liefern für einen Termin, der is_private=True
trägt UND nicht dem Betrachter gehört, ein REDUZIERTES Dict (siehe _redact_if_private()) --
title/location/notes/project_id/quote_id fehlen darin vollständig, nicht nur ausgeblendet. Der
Router (app/routers/calendar_events.py) übersetzt das je Zeile in CalendarEventOut oder
CalendarEventBusyOut (Muster app/service_reports.py::list_reports_for_field())."""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .auth import resolve_account_display
from .models import AppUser, CalendarEvent, Project, Quote

MODULE_KEY = "kalender"

# Fester Code-Wert wie überall im Projekt (RecurringCost.BILLING_INTERVALS, Account.
# ACCOUNT_TAX_RATES) -- kein Optionsfeld, da der Wert eine künftige Verarbeitungsregel trägt
# (Stufe 2, Outlook-Sync). "outlook" wird von keiner Funktion dieser Version je gesetzt -- reine
# Vorbereitung.
CALENDAR_EVENT_SOURCES = ("erp", "outlook")

BUSY_PLACEHOLDER_TITLE = "Belegt"


def _owner_name(db: Session, owner: AppUser | None) -> str | None:
    if owner is None:
        return None
    return resolve_account_display(db, owner)["full_name"]


def event_to_dict(db: Session, event: CalendarEvent) -> dict:
    """Volles, ungefiltertes Dict -- Privatsphäre-Redaktion passiert NICHT hier, sondern in
    _redact_if_private() bzw. beim Aufrufer, der weiß, wer gerade liest."""
    return {
        "id": event.id,
        "title": event.title,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "all_day": event.all_day,
        "location": event.location,
        "notes": event.notes,
        "owner_user_id": event.owner_user_id,
        "owner_name": _owner_name(db, event.owner),
        "project_id": event.project_id,
        "project_name": event.project.name if event.project is not None else None,
        "quote_id": event.quote_id,
        "quote_number": event.quote.quote_number if event.quote is not None else None,
        "is_private": event.is_private,
        "outlook_event_id": event.outlook_event_id,
        "external_source": event.external_source,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def is_redacted_for_viewer(data: dict, viewer_user_id: int | None) -> bool:
    """Die EINE Entscheidung, ob ein Termin für diesen Betrachter auf "belegt" reduziert werden
    muss -- genutzt vom Router, um zwischen CalendarEventOut/CalendarEventBusyOut zu wählen.
    Ein Termin wird reduziert, wenn er privat ist UND der Betrachter nicht der Besitzer ist --
    unabhängig von der Rolle (buero_finanzen sieht ein fremdes privates buero_auftrag-Termin
    genauso reduziert wie umgekehrt)."""
    return bool(data["is_private"]) and data["owner_user_id"] != viewer_user_id


def redact_for_busy(data: dict) -> dict:
    """Baut aus einem vollen Dict die reduzierte "belegt"-Variante -- title/location/notes/
    project_id/project_name/quote_id/quote_number entfernt, Rest (Zeitraum, Besitzer, ganztägig)
    bleibt, damit die Kalenderansicht die Zeile weiterhin sinnvoll als Balken zeichnen kann."""
    return {
        "id": data["id"],
        "start_at": data["start_at"],
        "end_at": data["end_at"],
        "all_day": data["all_day"],
        "owner_user_id": data["owner_user_id"],
        "owner_name": data["owner_name"],
        "is_private": True,
        "title": BUSY_PLACEHOLDER_TITLE,
    }


def _validate_single_assignment(project_id: int | None, quote_id: int | None) -> None:
    if project_id is not None and quote_id is not None:
        raise ValueError("Ein Termin kann nur einem Projekt oder einem Angebot zugeordnet werden, nicht beiden.")


def _validate_referenced_entities(db: Session, *, owner_user_id: int, project_id: int | None, quote_id: int | None) -> None:
    if db.get(AppUser, owner_user_id) is None:
        raise ValueError(f"Benutzer #{owner_user_id} wurde nicht gefunden.")
    if project_id is not None and db.get(Project, project_id) is None:
        raise ValueError(f"Projekt #{project_id} wurde nicht gefunden.")
    if quote_id is not None and db.get(Quote, quote_id) is None:
        raise ValueError(f"Angebot #{quote_id} wurde nicht gefunden.")


def _validate_time_range(start_at: datetime, end_at: datetime) -> None:
    if end_at < start_at:
        raise ValueError("Das Ende darf nicht vor dem Beginn liegen.")


def create_event(db: Session, *, title: str, start_at: datetime, end_at: datetime, all_day: bool,
                  location: str | None, notes: str | None, owner_user_id: int,
                  project_id: int | None, quote_id: int | None, is_private: bool) -> dict:
    _validate_time_range(start_at, end_at)
    _validate_single_assignment(project_id, quote_id)
    _validate_referenced_entities(db, owner_user_id=owner_user_id, project_id=project_id, quote_id=quote_id)
    event = CalendarEvent(
        title=title.strip(), start_at=start_at, end_at=end_at, all_day=all_day,
        location=(location or None), notes=(notes or None), owner_user_id=owner_user_id,
        project_id=project_id, quote_id=quote_id, is_private=is_private,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event_to_dict(db, event)


def update_event(db: Session, event_id: int, fields: dict) -> dict | None:
    """Echtes Teil-Update (nur tatsächlich mitgesendete Felder, exclude_unset auf Router-Seite,
    Muster EmployeeAbsenceUpdate) -- ein nicht mitgeschicktes Feld bleibt unverändert."""
    event = db.get(CalendarEvent, event_id)
    if event is None:
        return None
    new_start = fields.get("start_at", event.start_at)
    new_end = fields.get("end_at", event.end_at)
    _validate_time_range(new_start, new_end)
    new_project_id = fields.get("project_id", event.project_id)
    new_quote_id = fields.get("quote_id", event.quote_id)
    _validate_single_assignment(new_project_id, new_quote_id)
    _validate_referenced_entities(
        db, owner_user_id=fields.get("owner_user_id", event.owner_user_id),
        project_id=new_project_id, quote_id=new_quote_id,
    )
    for key, value in fields.items():
        if key == "title":
            value = value.strip()
        elif key in ("location", "notes") and value is not None:
            value = value or None
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event_to_dict(db, event)


def delete_event(db: Session, event_id: int) -> bool:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        return False
    db.delete(event)
    db.commit()
    return True


def get_event(db: Session, event_id: int) -> dict | None:
    event = db.get(CalendarEvent, event_id)
    return event_to_dict(db, event) if event is not None else None


def _events_query(*, start: datetime | None, end: datetime | None, project_id: int | None, quote_id: int | None):
    stmt = select(CalendarEvent).order_by(CalendarEvent.start_at)
    if start is not None:
        stmt = stmt.where(CalendarEvent.end_at >= start)
    if end is not None:
        stmt = stmt.where(CalendarEvent.start_at <= end)
    if project_id is not None:
        stmt = stmt.where(CalendarEvent.project_id == project_id)
    if quote_id is not None:
        stmt = stmt.where(CalendarEvent.quote_id == quote_id)
    return stmt


def list_events(db: Session, *, start: datetime | None = None, end: datetime | None = None,
                 project_id: int | None = None, quote_id: int | None = None) -> list[dict]:
    """Reine Datenbeschaffung, KEINE Privatsphäre-Redaktion -- der Router entscheidet je Zeile
    über is_redacted_for_viewer()/redact_for_busy(), da er (und nur er) weiß, wer liest. start/end
    filtern auf Überlappung mit dem angefragten Zeitraum (nicht nur Beginn innerhalb), ein
    mehrtägiger Termin, der VOR dem Fenster beginnt, aber hineinreicht, bleibt sichtbar."""
    rows = db.scalars(_events_query(start=start, end=end, project_id=project_id, quote_id=quote_id)).all()
    return [event_to_dict(db, e) for e in rows]


def list_owners(db: Session, *, role_keys: tuple[str, ...]) -> list[dict]:
    """Für den Besitzer-Auswahl-Dropdown und die Kollegen-Namen der Kalenderansicht --
    ausschließlich aktive Konten der übergebenen Rollen (die Büro-/Admin-Rollen mit Zugriff auf
    dieses Modul, kein AppUser mit role='field')."""
    stmt = select(AppUser).where(AppUser.active == True, AppUser.role.in_(role_keys)).order_by(AppUser.display_name)  # noqa: E712
    return [{"id": u.id, "display_name": resolve_account_display(db, u)["full_name"]} for u in db.scalars(stmt).all()]


def unlink_calendar_events_for_project(db: Session, project_id: int) -> None:
    """Vor dem (kaskadierenden) Löschen eines Projekts (app/projects.py::delete_project()) --
    ein Termin (Besichtigung/Aufmaß) bleibt auch nach dem Löschen des Projekts als eigenständige
    Historie sinnvoll, wird deshalb NICHT mitgelöscht, nur entkoppelt. delete_project() löscht
    Project.quotes per Kaskade mit -- deshalb hier auch quote_id nullen, für JEDE Quote-Zeile
    dieses Projekts, nicht nur project_id selbst. Muss vor dem eigentlichen Löschen aufgerufen
    werden, sonst verletzt PostgreSQL (anders als die lokale, ungeprüfte SQLite-Entwicklungs-
    datenbank) die Fremdschlüssel-Bedingung."""
    quote_ids = db.scalars(select(Quote.id).where(Quote.project_id == project_id)).all()
    rows = db.scalars(
        select(CalendarEvent).where(
            or_(CalendarEvent.project_id == project_id, CalendarEvent.quote_id.in_(quote_ids))
        )
    ).all()
    for row in rows:
        row.project_id = None
        row.quote_id = None
