from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .models import (
    Employee, EmployeeWorkTimeModel, TimeBackofficeAdvancedSettings,
    WorkTimeBreakRule, WorkTimeModel, WorkTimeModelValidity,
)


def week_in_range(week: int, valid_from_week: int, valid_to_week: int) -> bool:
    week = int(week); start = int(valid_from_week or 1); end = int(valid_to_week or 53)
    if start <= end:
        return start <= week <= end
    return week >= start or week <= end


def validity_row(db: Session, model_id: int, *, create: bool = True, default_from: int = 1, default_to: int = 53) -> WorkTimeModelValidity | None:
    row = db.scalar(select(WorkTimeModelValidity).where(WorkTimeModelValidity.model_id == model_id))
    if row is None and create:
        row = WorkTimeModelValidity(model_id=model_id, valid_from_week=default_from, valid_to_week=default_to)
        db.add(row); db.flush()
    return row


def model_validity(db: Session, model_id: int) -> tuple[int, int]:
    row = validity_row(db, model_id, create=False)
    return (int(row.valid_from_week), int(row.valid_to_week)) if row else (1, 53)


def model_is_valid_on(db: Session, model_id: int, on_date: date | None = None) -> bool:
    week = int((on_date or date.today()).isocalendar().week)
    start, end = model_validity(db, model_id)
    return week_in_range(week, start, end)


def get_or_create_advanced_settings(db: Session) -> TimeBackofficeAdvancedSettings:
    row = db.get(TimeBackofficeAdvancedSettings, 1)
    if row is None:
        row = TimeBackofficeAdvancedSettings(id=1, datev_personnel_equals_erp_number=False)
        db.add(row)
        db.flush()
    return row


def ensure_default_work_time_models(db: Session) -> None:
    """Legt nur fehlende Startmodelle an; vorhandene Nutzerkonfiguration wird nie überschrieben."""
    if db.scalar(select(WorkTimeModel.id).limit(1)) is not None:
        settings = get_or_create_advanced_settings(db)
        for model in db.scalars(select(WorkTimeModel)).all():
            if validity_row(db, model.id, create=False) is None:
                code=(model.code or "").lower()
                if code == "summer" or "sommer" in (model.name or "").lower():
                    validity_row(db, model.id, create=True, default_from=13, default_to=43)
                elif code == "winter" or "winter" in (model.name or "").lower():
                    validity_row(db, model.id, create=True, default_from=44, default_to=12)
                else:
                    validity_row(db, model.id, create=True)
        if settings.default_work_time_model_id is None:
            first = db.scalar(select(WorkTimeModel).where(WorkTimeModel.active.is_(True)).order_by(WorkTimeModel.sort_order, WorkTimeModel.id))
            if first:
                settings.default_work_time_model_id = first.id
        db.commit()
        return
    # Gegen einen gleichzeitigen ersten Zugriff abgesichert (siehe CLAUDE.md "Self-Seeding
    # gegen gleichzeitigen Zugriff absichern"): der komplette Satz (beide Modelle samt
    # Gültigkeit/Pausenregeln) wird in einem SAVEPOINT eingefügt -- kollidiert er mit der
    # UNIQUE-Verletzung auf name (ein anderer Prozess war zwischen dem obigen SELECT und hier
    # schneller), gilt das als "schon gesät", kein Fehler.
    try:
        with db.begin_nested():
            summer = WorkTimeModel(name="Sommermodell", code="summer", daily_target_hours=Decimal("8.00"), description="Arbeitszeitmodell für die Sommerperiode.", sort_order=10)
            winter = WorkTimeModel(name="Wintermodell", code="winter", daily_target_hours=Decimal("8.00"), description="Arbeitszeitmodell für die Winterperiode.", sort_order=20)
            db.add_all([summer, winter]); db.flush()
            db.add_all([
                WorkTimeModelValidity(model_id=summer.id, valid_from_week=13, valid_to_week=43),
                WorkTimeModelValidity(model_id=winter.id, valid_from_week=44, valid_to_week=12),
            ])
            # Konfigurierbare Startwerte. Sie können im Backoffice vollständig verändert/gelöscht werden.
            for model in (summer, winter):
                db.add_all([
                    WorkTimeBreakRule(model_id=model.id, threshold_hours=Decimal("6.00"), break_minutes=30, sort_order=10),
                    WorkTimeBreakRule(model_id=model.id, threshold_hours=Decimal("9.00"), break_minutes=45, sort_order=20),
                ])
            settings = get_or_create_advanced_settings(db)
            settings.default_work_time_model_id = summer.id
    except IntegrityError:
        return
    db.commit()


def model_to_dict(model: WorkTimeModel, db: Session | None = None) -> dict:
    valid_from, valid_to = model_validity(db, model.id) if db is not None else (1, 53)
    return {
        "id": model.id,
        "name": model.name,
        "code": model.code,
        "daily_target_hours": model.daily_target_hours,
        "valid_from_week": valid_from,
        "valid_to_week": valid_to,
        "description": model.description,
        "active": model.active,
        "sort_order": model.sort_order,
        "break_rules": [
            {"id": r.id, "threshold_hours": r.threshold_hours, "break_minutes": r.break_minutes, "sort_order": r.sort_order}
            for r in sorted(model.break_rules, key=lambda x: (Decimal(x.threshold_hours), x.sort_order, x.id))
        ],
    }


def list_models(db: Session) -> list[dict]:
    ensure_default_work_time_models(db)
    rows = db.scalars(select(WorkTimeModel).options(selectinload(WorkTimeModel.break_rules)).order_by(WorkTimeModel.sort_order, WorkTimeModel.name)).all()
    return [model_to_dict(x, db) for x in rows]


def save_model(db: Session, *, model_id: int | None, name: str, code: str | None, daily_target_hours: Decimal, valid_from_week: int = 1, valid_to_week: int = 53, description: str | None, active: bool, sort_order: int, break_rules: list[dict]) -> WorkTimeModel:
    name = (name or "").strip()
    if not name:
        raise ValueError("Bezeichnung des Arbeitszeitmodells ist erforderlich.")
    dup = db.scalar(select(WorkTimeModel).where(WorkTimeModel.name == name, WorkTimeModel.id != (model_id or -1)))
    if dup:
        raise ValueError("Ein Arbeitszeitmodell mit dieser Bezeichnung existiert bereits.")
    row = db.get(WorkTimeModel, model_id) if model_id else WorkTimeModel()
    if model_id and row is None:
        raise ValueError("Arbeitszeitmodell wurde nicht gefunden.")
    row.name = name; row.code = (code or "").strip() or None
    row.daily_target_hours = Decimal(daily_target_hours or 0); row.description = (description or "").strip() or None
    row.active = bool(active); row.sort_order = int(sort_order or 100)
    if row.daily_target_hours <= 0 or row.daily_target_hours > 24:
        raise ValueError("Tägliche Soll-Arbeitszeit muss größer 0 und höchstens 24 Stunden sein.")
    valid_from_week = int(valid_from_week or 1); valid_to_week = int(valid_to_week or 53)
    if not (1 <= valid_from_week <= 53 and 1 <= valid_to_week <= 53):
        raise ValueError("Kalenderwochen müssen zwischen 1 und 53 liegen.")
    if model_id is None:
        db.add(row); db.flush()
    validity = validity_row(db, row.id, create=True)
    validity.valid_from_week = valid_from_week; validity.valid_to_week = valid_to_week
    existing = {x.id: x for x in row.break_rules}
    keep = set()
    seen_thresholds = set()
    for idx, item in enumerate(break_rules or []):
        threshold = Decimal(str(item.get("threshold_hours") or 0))
        minutes = int(item.get("break_minutes") or 0)
        if threshold <= 0 or threshold > 24:
            raise ValueError("Pausenschwelle muss zwischen 0 und 24 Stunden liegen.")
        if minutes < 0 or minutes > 720:
            raise ValueError("Pausenwert ist ungültig.")
        if threshold in seen_thresholds:
            raise ValueError("Eine Pausenschwelle darf pro Modell nur einmal vorkommen.")
        seen_thresholds.add(threshold)
        rid = item.get("id")
        rule = existing.get(int(rid)) if rid else None
        if rule is None:
            rule = WorkTimeBreakRule(model_id=row.id)
            db.add(rule)
        rule.threshold_hours = threshold; rule.break_minutes = minutes; rule.sort_order = int(item.get("sort_order") or (idx+1)*10)
        db.flush(); keep.add(rule.id)
    for rid, rule in existing.items():
        if rid not in keep:
            db.delete(rule)
    settings = get_or_create_advanced_settings(db)
    if settings.default_work_time_model_id is None:
        settings.default_work_time_model_id = row.id
    db.commit(); db.refresh(row)
    return db.scalar(select(WorkTimeModel).options(selectinload(WorkTimeModel.break_rules)).where(WorkTimeModel.id == row.id))


def delete_model(db: Session, model_id: int) -> None:
    row = db.get(WorkTimeModel, model_id)
    if row is None:
        raise ValueError("Arbeitszeitmodell wurde nicht gefunden.")
    used = db.scalar(select(EmployeeWorkTimeModel.id).where(EmployeeWorkTimeModel.model_id == model_id).limit(1))
    settings = get_or_create_advanced_settings(db)
    if used is not None or settings.default_work_time_model_id == model_id:
        raise ValueError("Arbeitszeitmodell ist noch als Standard oder bei Mitarbeitern zugeordnet.")
    validity = validity_row(db, model_id, create=False)
    if validity is not None:
        db.delete(validity)
    db.delete(row); db.commit()


def employee_model_id(db: Session, employee_id: int) -> int | None:
    assignment = db.scalar(select(EmployeeWorkTimeModel).where(EmployeeWorkTimeModel.employee_id == employee_id))
    if assignment:
        return assignment.model_id
    return get_or_create_advanced_settings(db).default_work_time_model_id


def employee_model(db: Session, employee_id: int, on_date: date | None = None) -> WorkTimeModel | None:
    """Ermittelt das für das Datum wirksame Modell.

    Das explizit zugeordnete Modell hat Vorrang, sofern seine KW-Gültigkeit passt.
    Außerhalb seiner Gültigkeit wird zunächst das gültige Standardmodell und danach
    das erste aktive, für die Kalenderwoche gültige Modell verwendet.
    """
    ensure_default_work_time_models(db)
    on_date = on_date or date.today()
    assigned_id = employee_model_id(db, employee_id)
    assigned = db.scalar(select(WorkTimeModel).options(selectinload(WorkTimeModel.break_rules)).where(WorkTimeModel.id == assigned_id)) if assigned_id else None
    if assigned is not None and assigned.active and model_is_valid_on(db, assigned.id, on_date):
        return assigned
    settings = get_or_create_advanced_settings(db)
    if settings.default_work_time_model_id and settings.default_work_time_model_id != assigned_id:
        default = db.scalar(select(WorkTimeModel).options(selectinload(WorkTimeModel.break_rules)).where(WorkTimeModel.id == settings.default_work_time_model_id, WorkTimeModel.active.is_(True)))
        if default is not None and model_is_valid_on(db, default.id, on_date):
            return default
    candidates = db.scalars(select(WorkTimeModel).options(selectinload(WorkTimeModel.break_rules)).where(WorkTimeModel.active.is_(True)).order_by(WorkTimeModel.sort_order, WorkTimeModel.id)).all()
    for model in candidates:
        if model_is_valid_on(db, model.id, on_date):
            return model
    return assigned


def set_employee_model(db: Session, employee_id: int, model_id: int) -> dict:
    emp = db.get(Employee, employee_id); model = db.get(WorkTimeModel, model_id)
    if emp is None: raise ValueError("Mitarbeiter wurde nicht gefunden.")
    if model is None or not model.active: raise ValueError("Arbeitszeitmodell wurde nicht gefunden oder ist inaktiv.")
    row = db.scalar(select(EmployeeWorkTimeModel).where(EmployeeWorkTimeModel.employee_id == employee_id))
    if row is None:
        row = EmployeeWorkTimeModel(employee_id=employee_id, model_id=model_id); db.add(row)
    else:
        row.model_id = model_id
    db.commit()
    return {"employee_id": employee_id, "employee_name": f"{emp.first_name} {emp.last_name}".strip(), "model_id": model.id, "model_name": model.name}


def bulk_set_employee_model(db: Session, employee_ids: list[int], model_id: int) -> list[dict]:
    return [set_employee_model(db, int(eid), model_id) for eid in employee_ids]


def employee_model_rows(db: Session) -> list[dict]:
    ensure_default_work_time_models(db)
    employees = db.scalars(select(Employee).order_by(Employee.active.desc(), Employee.last_name, Employee.first_name)).all()
    result=[]
    for emp in employees:
        assigned_id=employee_model_id(db, emp.id)
        assigned=db.get(WorkTimeModel, assigned_id) if assigned_id else None
        effective=employee_model(db, emp.id, date.today())
        function_name = emp.profile.function.name if emp.profile and emp.profile.function else emp.job_title
        result.append({"employee_id":emp.id,"employee_name":f"{emp.first_name} {emp.last_name}".strip(),"employee_number":emp.employee_number,"employee_group":emp.employee_group,"function_name":function_name,"active":emp.active,"model_id":assigned.id if assigned else None,"model_name":assigned.name if assigned else None,"effective_model_id":effective.id if effective else None,"effective_model_name":effective.name if effective else None})
    return result


def automatic_break_minutes_for_duration(db: Session, employee_id: int, gross_hours: Decimal, on_date: date | None = None) -> int:
    model = employee_model(db, employee_id, on_date or date.today())
    if model is None:
        return 0
    gross = Decimal(str(gross_hours or 0))
    result = 0
    for rule in sorted(model.break_rules, key=lambda x: Decimal(x.threshold_hours)):
        if gross >= Decimal(rule.threshold_hours):
            result = max(result, int(rule.break_minutes or 0))
    return result


def automatic_break_minutes_for_timer(db: Session, employee_id: int, started_at: datetime, ended_at: datetime) -> int:
    if ended_at <= started_at:
        return 0
    gross = Decimal(str((ended_at - started_at).total_seconds())) / Decimal("3600")
    return automatic_break_minutes_for_duration(db, employee_id, gross, started_at.date())
