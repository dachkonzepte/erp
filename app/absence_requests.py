from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import AppUser, Employee, EmployeeAbsence, EmployeeAbsenceRequest

# Feste Abwesenheitskategorie (Schlechtwetter/Krankheit-Trennung) -- kein Optionsgruppen-Wert,
# da eine spaetere Ist-Wert-Auswertung (Produktivstunden-Rechner) auf genau diese Werte prueft.
# "unbekannt" ist ausschliesslich der Migrations-Ruecksfallwert fuer Altbestand ohne Kategorie
# und deshalb NICHT in ABSENCE_CATEGORIES enthalten -- create_request()/create_employee_absence()
# lehnen ihn beim Neuanlegen ab, er kann nur ueber die Migration selbst entstehen.
ABSENCE_CATEGORIES = ("urlaub", "krankheit", "fortbildung", "unbezahlt")
ABSENCE_CATEGORY_UNKNOWN = "unbekannt"
ABSENCE_CATEGORY_LABELS = {
    "urlaub": "Urlaub",
    "krankheit": "Krankheit",
    "fortbildung": "Fortbildung",
    "unbezahlt": "Unbezahlt",
    ABSENCE_CATEGORY_UNKNOWN: "Unbekannt (Altbestand)",
}


def _employee_name(emp: Employee | None) -> str | None:
    return f"{emp.first_name} {emp.last_name}".strip() if emp else None


def load_request(db: Session, request_id: int) -> EmployeeAbsenceRequest | None:
    return db.scalar(
        select(EmployeeAbsenceRequest)
        .options(selectinload(EmployeeAbsenceRequest.employee), selectinload(EmployeeAbsenceRequest.approved_absence))
        .where(EmployeeAbsenceRequest.id == request_id)
    )


def request_to_dict(db: Session, row: EmployeeAbsenceRequest) -> dict:
    reviewer = db.get(AppUser, row.reviewed_by_user_id) if row.reviewed_by_user_id else None
    # seit 1.9.101: wer den Antrag für eine andere Person gestellt hat (Büro – Finanzen oder Admin) -- leer, wenn die Person ihn selbst stellte
    # oder niemand vermerkt ist
    antragsteller = db.get(AppUser, row.requested_by_user_id) if row.requested_by_user_id else None
    fuer_andere = antragsteller is not None and antragsteller.employee_id != row.employee_id
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": _employee_name(row.employee),
        "absence_type": row.absence_type,
        "absence_category": row.absence_category,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "notes": row.notes,
        "status": row.status,
        "requested_by_user_id": row.requested_by_user_id,
        "beantragt_von": (antragsteller.display_name or antragsteller.username) if fuer_andere else None,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "reviewed_by_name": (reviewer.display_name or reviewer.username) if reviewer else None,
        "reviewed_at": row.reviewed_at,
        "review_notes": row.review_notes,
        "approved_absence_id": row.approved_absence_id,
        "created_at": row.created_at,
    }


def list_requests(db: Session, *, employee_id: int | None = None, status: str | None = None) -> list[EmployeeAbsenceRequest]:
    stmt = (
        select(EmployeeAbsenceRequest)
        .options(selectinload(EmployeeAbsenceRequest.employee), selectinload(EmployeeAbsenceRequest.approved_absence))
        .order_by(EmployeeAbsenceRequest.created_at.desc(), EmployeeAbsenceRequest.id.desc())
    )
    if employee_id is not None:
        stmt = stmt.where(EmployeeAbsenceRequest.employee_id == employee_id)
    if status:
        stmt = stmt.where(EmployeeAbsenceRequest.status == status)
    return db.scalars(stmt).all()


def _antrag_anlegen(
    db: Session, *, employee_id: int, absence_type: str, absence_category: str, start_date, end_date,
    notes: str | None = None, requested_by_user_id: int | None = None,
) -> EmployeeAbsenceRequest:
    """Prüft und legt an, ohne Commit."""
    emp = db.get(Employee, employee_id)
    if emp is None or not emp.active:
        raise ValueError("Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if absence_category not in ABSENCE_CATEGORIES:
        raise ValueError(f"Unbekannte Abwesenheitskategorie: {absence_category}")
    if end_date < start_date:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    overlap_pending = db.scalar(
        select(EmployeeAbsenceRequest.id).where(
            EmployeeAbsenceRequest.employee_id == employee_id,
            EmployeeAbsenceRequest.status == "pending",
            EmployeeAbsenceRequest.end_date >= start_date,
            EmployeeAbsenceRequest.start_date <= end_date,
        ).limit(1)
    )
    if overlap_pending:
        raise ValueError("Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.")
    row = EmployeeAbsenceRequest(
        employee_id=employee_id, absence_type=absence_type.strip() or "Urlaub",
        absence_category=absence_category,
        start_date=start_date, end_date=end_date, notes=notes or None,
        status="pending", requested_by_user_id=requested_by_user_id,
    )
    db.add(row); db.flush()
    return row


def create_request(db: Session, **werte) -> EmployeeAbsenceRequest:
    row = _antrag_anlegen(db, **werte)
    db.commit()
    return load_request(db, row.id)


def eintragen(db: Session, *, gleich_genehmigt: bool, **werte) -> EmployeeAbsenceRequest:
    """„Abwesenheit eintragen“ auf der Plantafel (seit 1.9.146, Stufe 6, R1, Punkt 4): derselbe Weg wie unter „Zeiten“ -- ein Antrag; vom Admin gleich genehmigt, in einem
    Commit. Scheitert das Genehmigen (schon eine Abwesenheit im Zeitraum), bleibt auch kein Antrag zurück."""
    try:
        row = _antrag_anlegen(db, **werte)
        if gleich_genehmigt:
            _entscheiden(db, row, decision="approved", reviewed_by_user_id=werte.get("requested_by_user_id"))
    except ValueError:
        db.rollback()
        raise
    db.commit()
    return load_request(db, row.id)


def review_request(
    db: Session, request_id: int, *, decision: str, reviewed_by_user_id: int | None,
    review_notes: str | None = None,
) -> EmployeeAbsenceRequest:
    row = db.get(EmployeeAbsenceRequest, request_id)
    if row is None:
        raise ValueError("Abwesenheitsantrag wurde nicht gefunden.")
    _entscheiden(db, row, decision=decision, reviewed_by_user_id=reviewed_by_user_id, review_notes=review_notes)
    db.commit()
    return load_request(db, row.id)


def _entscheiden(db: Session, row: EmployeeAbsenceRequest, *, decision: str, reviewed_by_user_id: int | None, review_notes: str | None = None) -> None:
    """Die Entscheidung, ohne Commit."""
    if row.status != "pending":
        raise ValueError("Dieser Abwesenheitsantrag wurde bereits bearbeitet.")
    if decision not in {"approved", "rejected"}:
        raise ValueError("Ungültige Entscheidung.")
    if decision == "approved":
        overlap = db.scalar(
            select(EmployeeAbsence.id).where(
                EmployeeAbsence.employee_id == row.employee_id,
                EmployeeAbsence.end_date >= row.start_date,
                EmployeeAbsence.start_date <= row.end_date,
            ).limit(1)
        )
        if overlap:
            raise ValueError("Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits eine genehmigte Abwesenheit.")
        absence = EmployeeAbsence(
            employee_id=row.employee_id, absence_type=row.absence_type,
            absence_category=row.absence_category,
            start_date=row.start_date, end_date=row.end_date, notes=row.notes,
        )
        db.add(absence); db.flush()
        row.approved_absence_id = absence.id
    row.status = decision
    row.reviewed_by_user_id = reviewed_by_user_id
    row.reviewed_at = datetime.utcnow()
    row.review_notes = review_notes or None
    db.flush()


ABWESENHEIT_GELOESCHT = "Die genehmigte Abwesenheit wurde gelöscht."


def abwesenheit_loeschen(db: Session, absence_id: int, *, geloescht_von_user_id: int | None = None) -> None:
    """Eine genehmigte Abwesenheit löschen (seit 1.9.146, P1): der Antrag folgt -- er ist danach zurückgezogen, mit Vermerk, und zeigt auf nichts mehr. Bis 1.9.145 scheiterte
    das Löschen unter PostgreSQL am Fremdschlüssel (500), unter SQLite blieb der Antrag „genehmigt“ und zeigte ins Leere."""
    row = db.get(EmployeeAbsence, absence_id)
    if row is None:
        raise ValueError("Abwesenheit nicht gefunden.")
    for antrag in db.scalars(select(EmployeeAbsenceRequest).where(EmployeeAbsenceRequest.approved_absence_id == absence_id)):
        antrag.approved_absence_id = None
        antrag.status = "cancelled"
        antrag.reviewed_by_user_id = geloescht_von_user_id
        antrag.reviewed_at = datetime.utcnow()
        antrag.review_notes = ABWESENHEIT_GELOESCHT
    db.flush()
    db.delete(row)
    db.commit()


def cancel_request(db: Session, request_id: int) -> None:
    row = db.get(EmployeeAbsenceRequest, request_id)
    if row is None:
        raise ValueError("Abwesenheitsantrag wurde nicht gefunden.")
    if row.status != "pending":
        raise ValueError("Nur offene Abwesenheitsanträge können zurückgezogen werden.")
    row.status = "cancelled"
    row.reviewed_at = datetime.utcnow()
    db.commit()
