from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload

from .models import (
    Employee, Order, OrderItem, Project, TimeEntry, Team, TeamEmployee,
    TimeEntryGroup, TimeEntryGroupMember,
    WorkPreparation, WorkPreparationEmployee, WorkPreparationTeamAssignment,
    WorkPreparationTeamEmployee,
)

from .work_time_models import automatic_break_minutes_for_timer

HOUR = Decimal("0.01")
ENTRY_TYPES = {"site", "workshop", "travel", "other"}
PRODUCTIVE_TYPES = {"site", "workshop", "other"}


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def employee_name(emp: Employee | None) -> str | None:
    return f"{emp.first_name} {emp.last_name}".strip() if emp else None


def entry_type_is_productive(entry_type: str) -> bool:
    return entry_type != "travel"


def compute_hours(started_at: datetime, ended_at: datetime, break_minutes: int = 0) -> Decimal:
    if ended_at <= started_at:
        raise ValueError("Endzeit muss nach der Startzeit liegen.")
    seconds = Decimal(str((ended_at - started_at).total_seconds()))
    net = seconds / Decimal("3600") - Decimal(max(0, int(break_minutes or 0))) / Decimal("60")
    if net <= 0:
        raise ValueError("Die Netto-Arbeitszeit muss größer als 0 sein.")
    return net.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def load_entry(db: Session, entry_id: int) -> TimeEntry | None:
    return db.scalar(
        select(TimeEntry)
        .options(
            selectinload(TimeEntry.employee), selectinload(TimeEntry.order),
            selectinload(TimeEntry.project), selectinload(TimeEntry.order_item),
        )
        .where(TimeEntry.id == entry_id)
    )


def active_entry(db: Session, employee_id: int) -> TimeEntry | None:
    return db.scalar(
        select(TimeEntry)
        .options(selectinload(TimeEntry.order), selectinload(TimeEntry.project), selectinload(TimeEntry.order_item))
        .where(TimeEntry.employee_id == employee_id, TimeEntry.status == "running")
        .order_by(TimeEntry.started_at.desc())
    )


def validate_order_item(db: Session, order_id: int, order_item_id: int | None) -> OrderItem | None:
    if order_item_id is None:
        return None
    item = db.get(OrderItem, order_item_id)
    if item is None or item.order_id != order_id:
        raise ValueError("Die LV-Position gehört nicht zum ausgewählten Auftrag.")
    return item


def create_manual_entry(
    db: Session, *, employee_id: int, order_id: int, work_date: date,
    hours: Decimal, entry_type: str = "site", order_item_id: int | None = None,
    activity: str | None = None, notes: str | None = None,
    started_at: datetime | None = None, ended_at: datetime | None = None,
    break_minutes: int = 0, created_by_user_id: int | None = None,
) -> TimeEntry:
    employee = db.get(Employee, employee_id)
    order = db.get(Order, order_id)
    if employee is None or not employee.active:
        raise ValueError("Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if order is None:
        raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db, order_id, order_item_id)
    if entry_type not in ENTRY_TYPES:
        # frei gepflegte Typen bleiben möglich; nur travel ist nicht-produktiv
        entry_type = entry_type.strip() or "other"
    amount = _d(hours)
    if started_at and ended_at:
        amount = compute_hours(started_at, ended_at, break_minutes)
    if amount <= 0:
        raise ValueError("Die Stunden müssen größer als 0 sein.")
    row = TimeEntry(
        employee_id=employee.id, project_id=order.project_id, order_id=order.id,
        order_item_id=order_item_id, work_date=work_date, entry_type=entry_type,
        counts_as_productive=entry_type_is_productive(entry_type), activity=(activity or None),
        started_at=started_at, ended_at=ended_at, break_minutes=max(0, int(break_minutes or 0)),
        hours=amount, notes=(notes or None), source="manual", status="booked",
        created_by_user_id=created_by_user_id,
    )
    db.add(row); db.commit()
    return load_entry(db, row.id)


def start_timer(
    db: Session, *, employee_id: int, order_id: int, entry_type: str = "site",
    order_item_id: int | None = None, activity: str | None = None, notes: str | None = None,
    started_at: datetime | None = None, created_by_user_id: int | None = None,
) -> TimeEntry:
    if active_entry(db, employee_id) is not None:
        raise ValueError("Für diesen Mitarbeiter läuft bereits eine Zeiterfassung.")
    employee = db.get(Employee, employee_id); order = db.get(Order, order_id)
    if employee is None or not employee.active:
        raise ValueError("Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if order is None:
        raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db, order_id, order_item_id)
    start = started_at or datetime.now().replace(microsecond=0)
    row = TimeEntry(
        employee_id=employee.id, project_id=order.project_id, order_id=order.id,
        order_item_id=order_item_id, work_date=start.date(), entry_type=entry_type,
        counts_as_productive=entry_type_is_productive(entry_type), activity=(activity or None),
        started_at=start, ended_at=None, break_minutes=0, hours=Decimal("0"),
        notes=(notes or None), source="timer", status="running", created_by_user_id=created_by_user_id,
    )
    db.add(row); db.commit()
    return load_entry(db, row.id)


def stop_timer(db: Session, entry_id: int, *, ended_at: datetime | None = None, break_minutes: int = 0) -> TimeEntry:
    row = db.get(TimeEntry, entry_id)
    if row is None:
        raise ValueError("Laufende Zeiterfassung wurde nicht gefunden.")
    if row.status != "running" or row.started_at is None:
        raise ValueError("Diese Zeiterfassung läuft nicht mehr.")
    end = ended_at or datetime.now().replace(microsecond=0)
    row.ended_at = end
    auto_break = automatic_break_minutes_for_timer(db, row.employee_id, row.started_at, end)
    row.break_minutes = max(0, int(break_minutes or 0), int(auto_break or 0))
    row.hours = compute_hours(row.started_at, end, row.break_minutes)
    row.status = "booked"
    db.commit()
    return load_entry(db, row.id)


def update_entry(
    db: Session, entry_id: int, *, employee_id: int, order_id: int, work_date: date,
    hours: Decimal, entry_type: str, order_item_id: int | None = None,
    activity: str | None = None, notes: str | None = None, break_minutes: int = 0,
) -> TimeEntry:
    row = db.get(TimeEntry, entry_id)
    if row is None:
        raise ValueError("Zeitbuchung wurde nicht gefunden.")
    if row.status == "running":
        raise ValueError("Eine laufende Zeiterfassung kann erst nach dem Stoppen bearbeitet werden.")
    employee = db.get(Employee, employee_id); order = db.get(Order, order_id)
    if employee is None or not employee.active: raise ValueError("Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if order is None: raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db, order_id, order_item_id)
    amount = _d(hours)
    if amount <= 0: raise ValueError("Die Stunden müssen größer als 0 sein.")
    row.employee_id=employee_id; row.order_id=order_id; row.project_id=order.project_id
    row.order_item_id=order_item_id; row.work_date=work_date; row.hours=amount
    row.entry_type=entry_type; row.counts_as_productive=entry_type_is_productive(entry_type)
    row.activity=activity or None; row.notes=notes or None; row.break_minutes=max(0,int(break_minutes or 0))
    # Bei manueller Korrektur zählt der Stundenwert als führend; alte Timer-Zeitstempel bleiben Nachweis.
    db.commit()
    return load_entry(db, row.id)


def delete_entry(db: Session, entry_id: int) -> None:
    row = db.get(TimeEntry, entry_id)
    if row is None: raise ValueError("Zeitbuchung wurde nicht gefunden.")
    if row.status == "running": raise ValueError("Laufende Zeiterfassung zuerst stoppen.")
    db.delete(row); db.commit()


def entry_to_dict(row: TimeEntry) -> dict:
    item = row.order_item
    return {
        "id": row.id, "employee_id": row.employee_id, "employee_name": employee_name(row.employee),
        "project_id": row.project_id, "project_number": row.project.project_number if row.project else None,
        "project_name": row.project.name if row.project else None,
        "order_id": row.order_id, "order_number": row.order.order_number if row.order else None,
        "order_title": row.order.title if row.order else None,
        "order_item_id": row.order_item_id,
        "order_item_oz": (item.gaeb_oz or item.position_number) if item else None,
        "order_item_text": item.short_text if item else None,
        "work_date": row.work_date, "entry_type": row.entry_type,
        "counts_as_productive": row.counts_as_productive, "activity": row.activity,
        "started_at": row.started_at, "ended_at": row.ended_at, "break_minutes": row.break_minutes,
        "hours": row.hours, "notes": row.notes, "source": row.source, "status": row.status,
        "created_at": row.created_at,
    }


def list_entries(
    db: Session, *, employee_id: int | None = None, project_id: int | None = None,
    order_id: int | None = None, start_date: date | None = None, end_date: date | None = None,
    limit: int = 500,
) -> list[TimeEntry]:
    stmt = select(TimeEntry).options(
        selectinload(TimeEntry.employee), selectinload(TimeEntry.project),
        selectinload(TimeEntry.order), selectinload(TimeEntry.order_item),
    ).order_by(TimeEntry.work_date.desc(), TimeEntry.started_at.desc(), TimeEntry.id.desc()).limit(min(max(limit,1),2000))
    if employee_id is not None: stmt=stmt.where(TimeEntry.employee_id==employee_id)
    if project_id is not None: stmt=stmt.where(TimeEntry.project_id==project_id)
    if order_id is not None: stmt=stmt.where(TimeEntry.order_id==order_id)
    if start_date is not None: stmt=stmt.where(TimeEntry.work_date>=start_date)
    if end_date is not None: stmt=stmt.where(TimeEntry.work_date<=end_date)
    return db.scalars(stmt).all()


def order_actual_hours(db: Session, order_id: int) -> dict:
    rows = db.execute(
        select(TimeEntry.counts_as_productive, TimeEntry.entry_type, func.coalesce(func.sum(TimeEntry.hours), 0))
        .where(TimeEntry.order_id==order_id, TimeEntry.status=="booked")
        .group_by(TimeEntry.counts_as_productive, TimeEntry.entry_type)
    ).all()
    productive=Decimal("0"); travel=Decimal("0"); total=Decimal("0")
    by_type={}
    for productive_flag, entry_type, hours in rows:
        h=_d(hours); total+=h; by_type[entry_type]=h.quantize(HOUR)
        if productive_flag: productive+=h
        if entry_type=="travel": travel+=h
    return {"productive_hours":productive.quantize(HOUR),"travel_hours":travel.quantize(HOUR),"total_hours":total.quantize(HOUR),"by_type":by_type}


def order_item_actual_hours(db: Session, order_id: int) -> dict[int, Decimal]:
    rows=db.execute(
        select(TimeEntry.order_item_id, func.coalesce(func.sum(TimeEntry.hours),0))
        .where(TimeEntry.order_id==order_id, TimeEntry.status=="booked", TimeEntry.counts_as_productive==True, TimeEntry.order_item_id.is_not(None))
        .group_by(TimeEntry.order_item_id)
    ).all()
    return {int(item_id):_d(hours).quantize(HOUR) for item_id,hours in rows}


def employee_assigned_order_ids(db: Session, employee_id: int) -> set[int]:
    ids=set(db.scalars(
        select(WorkPreparation.order_id)
        .join(WorkPreparationEmployee, WorkPreparationEmployee.preparation_id==WorkPreparation.id)
        .where(WorkPreparationEmployee.employee_id==employee_id)
    ).all())
    ids.update(db.scalars(
        select(WorkPreparation.order_id)
        .join(WorkPreparationTeamAssignment, WorkPreparationTeamAssignment.preparation_id==WorkPreparation.id)
        .join(WorkPreparationTeamEmployee, WorkPreparationTeamEmployee.assignment_id==WorkPreparationTeamAssignment.id)
        .where(WorkPreparationTeamEmployee.employee_id==employee_id)
    ).all())
    return ids


def time_tracking_context(db: Session, employee_id: int | None = None, include_all_orders: bool = False) -> dict:
    emp_stmt=select(Employee).where(Employee.active==True).order_by(Employee.last_name,Employee.first_name)
    employees=db.scalars(emp_stmt).all()
    # Bestandsauftraege aus aelteren Versionen koennen einen leeren/NULL-Status haben.
    # Diese duerfen in der Zeiterfassung nicht versehentlich ausgefiltert werden.
    order_stmt=(
        select(Order)
        .options(selectinload(Order.project), selectinload(Order.items))
        .where(or_(Order.status.is_(None), func.lower(func.coalesce(Order.status, "")).not_in(["abgeschlossen", "storniert"])))
        .order_by(Order.order_number.desc())
    )
    orders=db.scalars(order_stmt).unique().all()
    assigned_ids=employee_assigned_order_ids(db, employee_id) if employee_id else set()
    if employee_id and assigned_ids and not include_all_orders:
        orders=[o for o in orders if o.id in assigned_ids]
    team_stmt = select(Team).options(selectinload(Team.employees).selectinload(TeamEmployee.employee)).where(Team.active==True).order_by(Team.name)
    teams = db.scalars(team_stmt).unique().all()
    if employee_id and not include_all_orders:
        teams = [t for t in teams if any(m.employee_id == employee_id for m in t.employees)]
    return {
        "employees":[{"id":e.id,"name":employee_name(e),"employee_number":e.employee_number} for e in employees],
        "teams":[{
            "id":t.id,"name":t.name,"team_number":t.team_number,
            "employees":[{"id":m.employee_id,"name":employee_name(m.employee),"role":m.role} for m in t.employees if m.employee and m.employee.active]
        } for t in teams],
        "orders":[{
            "id":o.id,"order_number":o.order_number,"project_id":o.project_id,
            "project_number":o.project.project_number if o.project else None,"project_name":o.project.name if o.project else None,
            "customer_name":o.customer_name,"property_address":o.property_address,"title":o.title,
            "items":[{"id":i.id,"oz":i.gaeb_oz or i.position_number,"short_text":i.short_text,"unit":i.unit} for i in o.items],
        } for o in orders],
    }


# --- Version 1.0.2: Gruppenbuchungen ---
def load_group(db: Session, group_id: int) -> TimeEntryGroup | None:
    return db.get(TimeEntryGroup, group_id)


def group_for_entry(db: Session, entry_id: int) -> TimeEntryGroup | None:
    link = db.scalar(select(TimeEntryGroupMember).where(TimeEntryGroupMember.time_entry_id == entry_id))
    return db.get(TimeEntryGroup, link.group_id) if link else None


def group_member_ids(db: Session, group_id: int) -> list[int]:
    return list(db.scalars(select(TimeEntryGroupMember.employee_id).where(TimeEntryGroupMember.group_id == group_id)).all())


def validate_group_members(db: Session, employee_ids: list[int], *, team_id: int | None = None, actor_employee_id: int | None = None, is_admin: bool = False) -> list[Employee]:
    ids = list(dict.fromkeys(int(x) for x in employee_ids if x))
    if not ids:
        raise ValueError("Bitte mindestens einen Mitarbeiter auswählen.")
    employees = list(db.scalars(select(Employee).where(Employee.id.in_(ids), Employee.active==True)).all())
    if len(employees) != len(ids):
        raise ValueError("Mindestens ein ausgewählter Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if is_admin:
        if team_id is not None:
            member_ids=set(db.scalars(select(TeamEmployee.employee_id).where(TeamEmployee.team_id==team_id)).all())
            if not set(ids).issubset(member_ids):
                raise ValueError("Mindestens ein Mitarbeiter gehört nicht zum ausgewählten Team.")
        return employees
    if actor_employee_id is None:
        raise ValueError("Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
    if actor_employee_id not in ids:
        raise ValueError("Bei einer Gruppenbuchung muss der buchende Mitarbeiter selbst enthalten sein.")
    if team_id is None:
        raise ValueError("Bitte für die Gruppenbuchung ein Team auswählen.")
    actor_in_team = db.scalar(select(TeamEmployee.id).where(TeamEmployee.team_id==team_id, TeamEmployee.employee_id==actor_employee_id).limit(1))
    if actor_in_team is None:
        raise ValueError("Sie gehören nicht zum ausgewählten Team.")
    member_ids=set(db.scalars(select(TeamEmployee.employee_id).where(TeamEmployee.team_id==team_id)).all())
    if not set(ids).issubset(member_ids):
        raise ValueError("Sie dürfen nur für Kollegen des ausgewählten Teams mitbuchen.")
    return employees


def _create_group_header(db: Session, *, initiated_by_employee_id: int | None, team_id: int | None, order: Order, order_item_id: int | None, mode: str, entry_type: str, activity: str | None, work_date: date, started_at: datetime | None, hours: Decimal, break_minutes: int, notes: str | None, status: str, created_by_user_id: int | None) -> TimeEntryGroup:
    row=TimeEntryGroup(
        initiated_by_employee_id=initiated_by_employee_id, team_id=team_id, order_id=order.id, project_id=order.project_id,
        order_item_id=order_item_id, mode=mode, entry_type=entry_type, activity=activity or None,
        work_date=work_date, started_at=started_at, ended_at=None, break_minutes=max(0,int(break_minutes or 0)),
        hours=_d(hours), notes=notes or None, status=status, created_by_user_id=created_by_user_id,
    )
    db.add(row);db.flush();return row


def create_group_manual_entry(db: Session, *, employee_ids: list[int], team_id: int | None, actor_employee_id: int | None, is_admin: bool, order_id: int, work_date: date, hours: Decimal, entry_type: str='site', order_item_id: int | None=None, activity: str | None=None, notes: str | None=None, break_minutes: int=0, created_by_user_id: int | None=None) -> TimeEntryGroup:
    employees=validate_group_members(db,employee_ids,team_id=team_id,actor_employee_id=actor_employee_id,is_admin=is_admin)
    order=db.get(Order,order_id)
    if order is None: raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db,order_id,order_item_id)
    amount=_d(hours)
    if amount<=0: raise ValueError("Die Stunden müssen größer als 0 sein.")
    group=_create_group_header(db,initiated_by_employee_id=actor_employee_id,team_id=team_id,order=order,order_item_id=order_item_id,mode='manual',entry_type=entry_type,activity=activity,work_date=work_date,started_at=None,hours=amount,break_minutes=break_minutes,notes=notes,status='booked',created_by_user_id=created_by_user_id)
    for emp in employees:
        entry=TimeEntry(employee_id=emp.id,project_id=order.project_id,order_id=order.id,order_item_id=order_item_id,work_date=work_date,entry_type=entry_type,counts_as_productive=entry_type_is_productive(entry_type),activity=activity or None,started_at=None,ended_at=None,break_minutes=max(0,int(break_minutes or 0)),hours=amount,notes=notes or None,source='group_manual',status='booked',created_by_user_id=created_by_user_id)
        db.add(entry);db.flush();db.add(TimeEntryGroupMember(group_id=group.id,employee_id=emp.id,time_entry_id=entry.id))
    db.commit();return db.get(TimeEntryGroup,group.id)


def start_group_timer(db: Session, *, employee_ids: list[int], team_id: int | None, actor_employee_id: int | None, is_admin: bool, order_id: int, entry_type: str='site', order_item_id: int | None=None, activity: str | None=None, notes: str | None=None, started_at: datetime | None=None, created_by_user_id: int | None=None) -> TimeEntryGroup:
    employees=validate_group_members(db,employee_ids,team_id=team_id,actor_employee_id=actor_employee_id,is_admin=is_admin)
    order=db.get(Order,order_id)
    if order is None: raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db,order_id,order_item_id)
    busy=[employee_name(e) for e in employees if active_entry(db,e.id) is not None]
    if busy: raise ValueError("Für folgende Mitarbeiter läuft bereits eine Zeiterfassung: "+", ".join(busy))
    start=started_at or datetime.now().replace(microsecond=0)
    group=_create_group_header(db,initiated_by_employee_id=actor_employee_id,team_id=team_id,order=order,order_item_id=order_item_id,mode='timer',entry_type=entry_type,activity=activity,work_date=start.date(),started_at=start,hours=Decimal('0'),break_minutes=0,notes=notes,status='running',created_by_user_id=created_by_user_id)
    for emp in employees:
        entry=TimeEntry(employee_id=emp.id,project_id=order.project_id,order_id=order.id,order_item_id=order_item_id,work_date=start.date(),entry_type=entry_type,counts_as_productive=entry_type_is_productive(entry_type),activity=activity or None,started_at=start,ended_at=None,break_minutes=0,hours=Decimal('0'),notes=notes or None,source='group_timer',status='running',created_by_user_id=created_by_user_id)
        db.add(entry);db.flush();db.add(TimeEntryGroupMember(group_id=group.id,employee_id=emp.id,time_entry_id=entry.id))
    db.commit();return db.get(TimeEntryGroup,group.id)


def stop_group_timer(db: Session, group_id: int, *, ended_at: datetime | None=None, break_minutes: int=0, break_minutes_by_employee: dict[int,int] | None=None) -> TimeEntryGroup:
    group=db.get(TimeEntryGroup,group_id)
    if group is None: raise ValueError("Gruppenbuchung wurde nicht gefunden.")
    if group.status!='running' or group.started_at is None: raise ValueError("Diese Gruppenbuchung läuft nicht mehr.")
    end=ended_at or datetime.now().replace(microsecond=0)
    links=db.scalars(select(TimeEntryGroupMember).where(TimeEntryGroupMember.group_id==group.id)).all()
    amounts=[]; applied_breaks=[]
    for link in links:
        entry=db.get(TimeEntry,link.time_entry_id)
        if entry and entry.status=='running':
            auto=(break_minutes_by_employee or {}).get(link.employee_id)
            if auto is None:
                auto=automatic_break_minutes_for_timer(db,link.employee_id,group.started_at,end)
            applied=max(0,int(break_minutes or 0),int(auto or 0))
            amount=compute_hours(group.started_at,end,applied)
            entry.ended_at=end;entry.break_minutes=applied;entry.hours=amount;entry.status='booked'
            amounts.append(amount);applied_breaks.append(applied)
    group.ended_at=end
    group.break_minutes=max(applied_breaks or [max(0,int(break_minutes or 0))])
    group.hours=(sum(amounts,Decimal('0'))/Decimal(len(amounts))).quantize(Decimal('0.0001')) if amounts else Decimal('0')
    group.status='booked'
    db.commit();return db.get(TimeEntryGroup,group.id)


def group_to_dict(db: Session, group: TimeEntryGroup) -> dict:
    links=db.scalars(select(TimeEntryGroupMember).where(TimeEntryGroupMember.group_id==group.id).order_by(TimeEntryGroupMember.id)).all()
    member_entries=[]
    for link in links:
        entry=load_entry(db,link.time_entry_id)
        if entry: member_entries.append(entry_to_dict(entry))
    return {"id":group.id,"initiated_by_employee_id":group.initiated_by_employee_id,"team_id":group.team_id,"order_id":group.order_id,"project_id":group.project_id,"order_item_id":group.order_item_id,"mode":group.mode,"entry_type":group.entry_type,"activity":group.activity,"work_date":group.work_date,"started_at":group.started_at,"ended_at":group.ended_at,"break_minutes":group.break_minutes,"hours":group.hours,"notes":group.notes,"status":group.status,"member_entries":member_entries}


def active_group_for_employee(db: Session, employee_id: int, *, initiated_only: bool = False) -> TimeEntryGroup | None:
    stmt=(
        select(TimeEntryGroup)
        .join(TimeEntryGroupMember, TimeEntryGroupMember.group_id==TimeEntryGroup.id)
        .join(TimeEntry, TimeEntry.id==TimeEntryGroupMember.time_entry_id)
        .where(TimeEntryGroupMember.employee_id==employee_id, TimeEntryGroup.status=='running', TimeEntry.status=='running')
        .order_by(TimeEntryGroup.started_at.desc())
    )
    if initiated_only:
        stmt=stmt.where(TimeEntryGroup.initiated_by_employee_id==employee_id)
    return db.scalar(stmt)
