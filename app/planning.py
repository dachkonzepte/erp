from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta, datetime, timezone
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    Employee, EmployeeAbsence, EmployeePlanningSettings, EmployeeProfile, OperationalResource, Order, PlanningHoliday,
    PlanningSettings, PlanningRegionSettings, PlanningSchoolHoliday, PlanningSchoolHolidaySync, PlanningSlot, PlanningSlotCapacity, Project, Property, ServiceReport, Team, TeamEmployee,
    TeamResource, WorkPreparation, WorkPreparationEmployee, WorkPreparationTeamAssignment,
    WorkPreparationTeamEmployee, WorkPreparationTeamResource,
)
from .orders import employee_assigned_order_ids, load_order
from .service_reports import count_reports_for_order
from .work_preparation import ensure_preparation, planned_hours
from .version import APP_VERSION

HOUR = Decimal("0.01")

GERMAN_STATES = {
    "BW": "Baden-Württemberg", "BY": "Bayern", "BE": "Berlin", "BB": "Brandenburg",
    "HB": "Bremen", "HH": "Hamburg", "HE": "Hessen", "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen", "NW": "Nordrhein-Westfalen", "RP": "Rheinland-Pfalz",
    "SL": "Saarland", "SN": "Sachsen", "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein", "TH": "Thüringen",
}

SCHOOL_HOLIDAY_NAMES = {
    "winterferien": "Winterferien", "osterferien": "Osterferien", "pfingstferien": "Pfingstferien",
    "sommerferien": "Sommerferien", "herbstferien": "Herbstferien", "weihnachtsferien": "Weihnachtsferien",
    "fruehjahrsferien": "Frühjahrsferien", "himmelfahrt": "Himmelfahrt / Pfingsten",
}

def get_or_create_region_settings(db: Session) -> PlanningRegionSettings:
    row = db.get(PlanningRegionSettings, 1)
    if row is None:
        row = PlanningRegionSettings(id=1, federal_state_code="NW")
        db.add(row); db.commit(); db.refresh(row)
    return row

def update_region_settings(db: Session, *, federal_state_code: str, auto_public_holidays: bool, show_school_holidays: bool) -> PlanningRegionSettings:
    code = (federal_state_code or "NW").upper()
    if code not in GERMAN_STATES:
        raise ValueError("Unbekanntes Bundesland.")
    row = get_or_create_region_settings(db)
    row.federal_state_code = code; row.auto_public_holidays = bool(auto_public_holidays); row.show_school_holidays = bool(show_school_holidays)
    db.commit(); db.refresh(row); return row

def _easter_sunday(year: int) -> date:
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31; day=((h+l-7*m+114)%31)+1
    return date(year, month, day)

def automatic_public_holidays(state_code: str, years) -> dict[date, str]:
    state=(state_code or "NW").upper(); result={}
    for year in sorted(set(int(y) for y in years)):
        easter=_easter_sunday(year)
        items={
            date(year,1,1):"Neujahr", easter-timedelta(days=2):"Karfreitag", easter+timedelta(days=1):"Ostermontag",
            date(year,5,1):"Tag der Arbeit", easter+timedelta(days=39):"Christi Himmelfahrt", easter+timedelta(days=50):"Pfingstmontag",
            date(year,10,3):"Tag der Deutschen Einheit", date(year,12,25):"1. Weihnachtstag", date(year,12,26):"2. Weihnachtstag",
        }
        if state in {"BW","BY","ST"}: items[date(year,1,6)]="Heilige Drei Könige"
        if state=="BE" or (state=="MV" and year>=2023): items[date(year,3,8)]="Internationaler Frauentag"
        if state in {"BW","BY","HE","NW","RP","SL"}: items[easter+timedelta(days=60)]="Fronleichnam"
        if state=="SL": items[date(year,8,15)]="Mariä Himmelfahrt"
        if state=="TH": items[date(year,9,20)]="Weltkindertag"
        reform={"BB","MV","SN","ST","TH"}
        if year>=2018: reform |= {"HB","HH","NI","SH"}
        if state in reform: items[date(year,10,31)]="Reformationstag"
        if state in {"BW","BY","NW","RP","SL"}: items[date(year,11,1)]="Allerheiligen"
        if state=="SN":
            nov23=date(year,11,23); wed=nov23-timedelta(days=(nov23.weekday()-2)%7); items[wed]="Buß- und Bettag"
        result.update(items)
    return result

def _manual_holiday_map(db: Session, start: date, end: date) -> dict[date, str]:
    return {x.holiday_date:x.name for x in _holiday_rows(db,start,end)}

def _combined_holiday_map(db: Session, start: date, end: date) -> tuple[dict[date,str], list[dict]]:
    region=get_or_create_region_settings(db); manual=_manual_holiday_map(db,start,end); auto={}
    if region.auto_public_holidays:
        auto=automatic_public_holidays(region.federal_state_code, range(start.year,end.year+1))
        auto={d:n for d,n in auto.items() if start<=d<=end}
    combined=dict(auto); combined.update(manual)
    rows=[]
    for d,n in sorted(combined.items()):
        rows.append({"date":d,"name":n,"source":"manual" if d in manual else "automatic"})
    return combined, rows

def _planning_visibility_map(db: Session, employees: list[Employee]) -> dict[int,bool]:
    ids=[e.id for e in employees if e.id]
    stored={r.employee_id:bool(r.show_on_planning_board) for r in db.scalars(select(EmployeePlanningSettings).where(EmployeePlanningSettings.employee_id.in_(ids))).all()} if ids else {}
    result={}
    for e in employees:
        if e.id in stored: result[e.id]=stored[e.id]; continue
        fn=(e.profile.function.name if e.profile and e.profile.function else e.job_title or "").casefold()
        result[e.id]=e.employee_group!="kaufmaennisch" and not any(t in fn for t in ("lager","büro","buero","verwaltung"))
    return result

def planning_visible_employee_ids(db: Session) -> set[int]:
    employees=db.scalars(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.active==True)).all()
    vis=_planning_visibility_map(db,employees); return {e.id for e in employees if vis.get(e.id,True)}

def _parse_ferien_api_datetime(value: str) -> datetime:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("Europe/Berlin"))

def parse_school_holiday_payload(payload: list[dict], state_code: str, year: int) -> list[dict]:
    rows=[]
    for item in payload:
        try:
            start_dt=_parse_ferien_api_datetime(str(item["start"])); end_dt=_parse_ferien_api_datetime(str(item["end"]))
            start=start_dt.date(); end=end_dt.date()-timedelta(days=1)
            if end<start: end=start
            raw=str(item.get("name") or "Schulferien").strip().casefold(); name=SCHOOL_HOLIDAY_NAMES.get(raw, raw.replace("-"," ").title())
            rows.append({"state_code":state_code,"calendar_year":year,"name":name,"start_date":start,"end_date":end})
        except Exception:
            continue
    return rows

def _fetch_school_holidays(state_code: str, year: int, timeout: float=4.0) -> list[dict]:
    url=f"https://ferien-api.de/api/v1/holidays/{state_code}/{year}"
    req=Request(url,headers={"User-Agent":f"DACHKONZEPTE-ERP/{APP_VERSION}"})
    with urlopen(req,timeout=timeout) as response:
        payload=json.loads(response.read().decode("utf-8"))
    return parse_school_holiday_payload(payload,state_code,year)

def sync_school_holidays(db: Session, state_code: str, year: int, force: bool=False) -> dict:
    code=(state_code or "NW").upper()
    sync=db.scalar(select(PlanningSchoolHolidaySync).where(PlanningSchoolHolidaySync.state_code==code,PlanningSchoolHolidaySync.calendar_year==year))
    if sync and sync.success and not force:
        return {"state_code":code,"year":year,"success":True,"cached":True}
    try:
        rows=_fetch_school_holidays(code,year)
        for old in db.scalars(select(PlanningSchoolHoliday).where(PlanningSchoolHoliday.state_code==code,PlanningSchoolHoliday.calendar_year==year)).all(): db.delete(old)
        for row in rows: db.add(PlanningSchoolHoliday(**row))
        if sync is None: sync=PlanningSchoolHolidaySync(state_code=code,calendar_year=year); db.add(sync)
        sync.success=True; sync.error_message=None; sync.synced_at=datetime.utcnow(); db.commit()
        return {"state_code":code,"year":year,"success":True,"cached":False,"count":len(rows)}
    except Exception as exc:
        if sync is None: sync=PlanningSchoolHolidaySync(state_code=code,calendar_year=year); db.add(sync)
        sync.success=False; sync.error_message=str(exc)[:1000]; sync.synced_at=datetime.utcnow(); db.commit()
        return {"state_code":code,"year":year,"success":False,"error":str(exc)}

def school_holidays_for_range(db: Session, start: date, end: date, auto_sync: bool=True) -> tuple[list[dict], list[str]]:
    region=get_or_create_region_settings(db)
    if not region.show_school_holidays: return [],[]
    warnings=[]
    years=range(start.year,end.year+1)
    if auto_sync:
        for year in years:
            result=sync_school_holidays(db,region.federal_state_code,year,force=False)
            if not result.get("success"): warnings.append(f"Ferien {year}: {result.get('error','Synchronisierung fehlgeschlagen')}")
    rows=db.scalars(select(PlanningSchoolHoliday).where(PlanningSchoolHoliday.state_code==region.federal_state_code,PlanningSchoolHoliday.start_date<=end,PlanningSchoolHoliday.end_date>=start).order_by(PlanningSchoolHoliday.start_date)).all()
    return [{"id":x.id,"name":x.name,"start_date":x.start_date,"end_date":x.end_date,"state_code":x.state_code} for x in rows], warnings



def _d(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _employee_name(emp: Employee | None) -> str:
    if emp is None:
        return ""
    return f"{emp.first_name} {emp.last_name}".strip()


def _ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def get_or_create_planning_settings(db: Session) -> PlanningSettings:
    row = db.get(PlanningSettings, 1)
    if row is None:
        row = PlanningSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def planning_settings_dict(row: PlanningSettings, db: Session | None = None) -> dict:
    result = {
        "id": row.id,
        "daily_work_hours": row.daily_work_hours,
        "default_travel_hours_per_employee_day": row.default_travel_hours_per_employee_day,
        "monday": row.monday, "tuesday": row.tuesday, "wednesday": row.wednesday,
        "thursday": row.thursday, "friday": row.friday, "saturday": row.saturday,
        "sunday": row.sunday,
    }
    if db is not None:
        region = get_or_create_region_settings(db)
        result.update({
            "federal_state_code": region.federal_state_code,
            "federal_state_name": GERMAN_STATES.get(region.federal_state_code, region.federal_state_code),
            "auto_public_holidays": region.auto_public_holidays,
            "show_school_holidays": region.show_school_holidays,
        })
    else:
        result.update({"federal_state_code":"NW","federal_state_name":GERMAN_STATES["NW"],"auto_public_holidays":True,"show_school_holidays":True})
    return result


def update_planning_settings(db: Session, **values) -> PlanningSettings:
    row = get_or_create_planning_settings(db)
    region_keys = {k: values.pop(k) for k in list(values) if k in {"federal_state_code","auto_public_holidays","show_school_holidays"}}
    for key, value in values.items():
        setattr(row, key, value)
    if region_keys:
        current = get_or_create_region_settings(db)
        update_region_settings(
            db,
            federal_state_code=region_keys.get("federal_state_code", current.federal_state_code),
            auto_public_holidays=region_keys.get("auto_public_holidays", current.auto_public_holidays),
            show_school_holidays=region_keys.get("show_school_holidays", current.show_school_holidays),
        )
    db.commit()
    db.refresh(row)
    return row


def _working_weekdays(settings: PlanningSettings) -> set[int]:
    flags = [settings.monday, settings.tuesday, settings.wednesday, settings.thursday,
             settings.friday, settings.saturday, settings.sunday]
    return {i for i, active in enumerate(flags) if active}


def _holiday_rows(db: Session, start: date, end: date) -> list[PlanningHoliday]:
    return db.scalars(
        select(PlanningHoliday)
        .where(PlanningHoliday.active == True, PlanningHoliday.holiday_date >= start, PlanningHoliday.holiday_date <= end)
        .order_by(PlanningHoliday.holiday_date)
    ).all()


def _absence_rows(db: Session, start: date, end: date, employee_ids: set[int] | None = None) -> list[EmployeeAbsence]:
    stmt = (
        select(EmployeeAbsence)
        .options(selectinload(EmployeeAbsence.employee))
        .where(EmployeeAbsence.start_date <= end, EmployeeAbsence.end_date >= start)
        .order_by(EmployeeAbsence.start_date, EmployeeAbsence.employee_id)
    )
    if employee_ids:
        stmt = stmt.where(EmployeeAbsence.employee_id.in_(employee_ids))
    return db.scalars(stmt).all()


def _absence_map(rows: list[EmployeeAbsence]) -> dict[tuple[int, date], EmployeeAbsence]:
    result = {}
    for row in rows:
        for day in _date_range(row.start_date, row.end_date):
            result[(row.employee_id, day)] = row
    return result


def _is_workday(day: date, settings: PlanningSettings, holiday_dates: set[date]) -> bool:
    return day.weekday() in _working_weekdays(settings) and day not in holiday_dates


def _employee_daily_gross_hours(emp: Employee, settings: PlanningSettings) -> Decimal:
    working_days = max(1, len(_working_weekdays(settings)))
    weekly = _d(emp.weekly_hours)
    contractual = (weekly / Decimal(working_days)) if weekly > 0 else _d(settings.daily_work_hours)
    return min(_d(settings.daily_work_hours), contractual)


def _employee_net_capacity(emp: Employee, settings: PlanningSettings, travel_hours: Decimal) -> Decimal:
    return max(Decimal("0"), _employee_daily_gross_hours(emp, settings) - travel_hours)


def _team_members_from_master(team: Team, visible_employee_ids: set[int] | None = None) -> list[Employee]:
    return [x.employee for x in team.employees if x.employee and x.employee.active and (visible_employee_ids is None or x.employee_id in visible_employee_ids)]


def _team_members_from_assignment(assignment: WorkPreparationTeamAssignment, visible_employee_ids: set[int] | None = None) -> list[Employee]:
    return [x.employee for x in assignment.employees if x.employee and x.employee.active and (visible_employee_ids is None or x.employee_id in visible_employee_ids)]


def _day_capacity(
    employees: list[Employee], day: date, settings: PlanningSettings, travel_hours: Decimal,
    holiday_dates: set[date], absences: dict[tuple[int, date], EmployeeAbsence],
) -> tuple[Decimal, list[Employee], list[EmployeeAbsence]]:
    if not _is_workday(day, settings, holiday_dates):
        return Decimal("0"), [], []
    available, absent = [], []
    total = Decimal("0")
    for emp in employees:
        absence = absences.get((emp.id, day))
        if absence:
            absent.append(absence)
            continue
        available.append(emp)
        total += _employee_net_capacity(emp, settings, travel_hours)
    return total.quantize(HOUR), available, absent


def _load_team(db: Session, team_id: int) -> Team | None:
    return db.scalar(
        select(Team)
        .options(
            selectinload(Team.employees).selectinload(TeamEmployee.employee),
            selectinload(Team.resources).selectinload(TeamResource.resource),
        )
        .where(Team.id == team_id)
    )


def ensure_team_assignment(db: Session, prep: WorkPreparation, team_id: int) -> WorkPreparationTeamAssignment:
    existing = db.scalar(
        select(WorkPreparationTeamAssignment)
        .options(
            selectinload(WorkPreparationTeamAssignment.employees).selectinload(WorkPreparationTeamEmployee.employee),
            selectinload(WorkPreparationTeamAssignment.resources).selectinload(WorkPreparationTeamResource.resource),
        )
        .where(
            WorkPreparationTeamAssignment.preparation_id == prep.id,
            WorkPreparationTeamAssignment.team_id == team_id,
        )
    )
    if existing is not None:
        return existing

    team = _load_team(db, team_id)
    if team is None or not team.active:
        raise ValueError("Kolonne / Team wurde nicht gefunden oder ist inaktiv.")

    assignment = WorkPreparationTeamAssignment(
        preparation_id=prep.id,
        team_id=team.id,
        team_name_snapshot=team.name,
        notes="Über Plantafel zugewiesen",
    )
    db.add(assignment)
    db.flush()
    for member in team.employees:
        if member.employee and member.employee.active:
            db.add(WorkPreparationTeamEmployee(
                assignment_id=assignment.id,
                employee_id=member.employee_id,
                employee_name_snapshot=_employee_name(member.employee),
                role_snapshot=member.role,
            ))
    for member in team.resources:
        if member.resource and member.resource.active:
            db.add(WorkPreparationTeamResource(
                assignment_id=assignment.id,
                resource_id=member.resource_id,
                resource_name_snapshot=member.resource.name,
                resource_type_snapshot=member.resource.resource_type,
                role_snapshot=member.role,
            ))
    db.flush()
    return assignment


def _load_slot(db: Session, slot_id: int) -> PlanningSlot | None:
    return db.scalar(
        select(PlanningSlot)
        .options(
            selectinload(PlanningSlot.capacity),
            selectinload(PlanningSlot.preparation)
            .selectinload(WorkPreparation.order)
            .selectinload(Order.project),
            selectinload(PlanningSlot.team_assignment)
            .selectinload(WorkPreparationTeamAssignment.employees)
            .selectinload(WorkPreparationTeamEmployee.employee),
            selectinload(PlanningSlot.team_assignment)
            .selectinload(WorkPreparationTeamAssignment.resources)
            .selectinload(WorkPreparationTeamResource.resource),
        )
        .where(PlanningSlot.id == slot_id)
    )


def sync_preparation_dates(db: Session, preparation_id: int) -> None:
    prep = db.get(WorkPreparation, preparation_id)
    if prep is None:
        return
    slots = db.scalars(select(PlanningSlot).where(PlanningSlot.preparation_id == preparation_id)).all()
    if slots:
        prep.planned_start = min(x.start_date for x in slots)
        prep.planned_end = max(x.end_date for x in slots)
    else:
        prep.planned_start = None
        prep.planned_end = None


def _stored_slot_hours(slot: PlanningSlot) -> Decimal | None:
    return _d(slot.capacity.planned_hours) if slot.capacity is not None else None


def _infer_slot_hours(db: Session, slot: PlanningSlot) -> Decimal:
    stored = _stored_slot_hours(slot)
    if stored is not None:
        return stored
    slots = db.scalars(
        select(PlanningSlot).options(selectinload(PlanningSlot.capacity)).where(PlanningSlot.preparation_id == slot.preparation_id)
    ).all()
    order = load_order(db, slot.preparation.order_id)
    total = planned_hours(order) if order else Decimal("0")
    if len(slots) <= 1:
        return total
    weights = {x.id: max(1, (x.end_date - x.start_date).days + 1) for x in slots}
    denom = Decimal(sum(weights.values()))
    return (total * Decimal(weights[slot.id]) / denom).quantize(HOUR) if denom else Decimal("0")


def _remaining_order_hours(db: Session, prep: WorkPreparation) -> Decimal:
    order = load_order(db, prep.order_id)
    total = planned_hours(order) if order else Decimal("0")
    existing = db.scalars(
        select(PlanningSlot).options(selectinload(PlanningSlot.capacity)).where(PlanningSlot.preparation_id == prep.id)
    ).all()
    assigned = sum((_stored_slot_hours(x) or Decimal("0") for x in existing), Decimal("0"))
    return max(Decimal("0"), total - assigned).quantize(HOUR)


def create_slot(
    db: Session, *, order_id: int, team_id: int, start_date: date, end_date: date,
    status: str = "geplant", notes: str | None = None, planned_hours: Decimal | None = None,
    travel_hours_per_employee_day: Decimal | None = None,
) -> PlanningSlot:
    if end_date < start_date:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    order = db.get(Order, order_id)
    if order is None:
        raise ValueError("Auftrag wurde nicht gefunden.")
    prep = ensure_preparation(db, order_id)
    assignment = ensure_team_assignment(db, prep, team_id)
    settings = get_or_create_planning_settings(db)
    travel = _d(travel_hours_per_employee_day if travel_hours_per_employee_day is not None else settings.default_travel_hours_per_employee_day)
    if travel >= _d(settings.daily_work_hours):
        raise ValueError("Anfahrtszeit muss kleiner als die tägliche Arbeitszeit sein.")
    slot = PlanningSlot(
        preparation_id=prep.id, team_assignment_id=assignment.id, start_date=start_date,
        end_date=end_date, status=status, notes=notes,
    )
    db.add(slot)
    db.flush()
    hours = _remaining_order_hours(db, prep) if planned_hours is None else _d(planned_hours)
    db.add(PlanningSlotCapacity(slot_id=slot.id, planned_hours=hours, travel_hours_per_employee_day=travel))
    db.flush()
    sync_preparation_dates(db, prep.id)
    db.commit()
    return _load_slot(db, slot.id)


def update_slot(
    db: Session, slot_id: int, *, team_id: int | None, start_date: date, end_date: date,
    status: str, notes: str | None, planned_hours: Decimal | None = None,
    travel_hours_per_employee_day: Decimal | None = None,
) -> PlanningSlot:
    if end_date < start_date:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    slot = _load_slot(db, slot_id)
    if slot is None:
        raise ValueError("Planeinsatz wurde nicht gefunden.")
    if team_id is not None and team_id != slot.team_assignment.team_id:
        slot.team_assignment_id = ensure_team_assignment(db, slot.preparation, team_id).id
    slot.start_date = start_date
    slot.end_date = end_date
    slot.status = status
    slot.notes = notes
    settings = get_or_create_planning_settings(db)
    capacity = slot.capacity
    if capacity is None:
        capacity = PlanningSlotCapacity(slot_id=slot.id, planned_hours=_infer_slot_hours(db, slot))
        db.add(capacity)
        slot.capacity = capacity
    if planned_hours is not None:
        capacity.planned_hours = _d(planned_hours)
    if travel_hours_per_employee_day is not None:
        travel = _d(travel_hours_per_employee_day)
        if travel >= _d(settings.daily_work_hours):
            raise ValueError("Anfahrtszeit muss kleiner als die tägliche Arbeitszeit sein.")
        capacity.travel_hours_per_employee_day = travel
    elif capacity.travel_hours_per_employee_day is None:
        capacity.travel_hours_per_employee_day = settings.default_travel_hours_per_employee_day
    db.flush()
    sync_preparation_dates(db, slot.preparation_id)
    db.commit()
    return _load_slot(db, slot.id)


def delete_slot(db: Session, slot_id: int) -> int:
    slot = db.get(PlanningSlot, slot_id)
    if slot is None:
        raise ValueError("Planeinsatz wurde nicht gefunden.")
    prep_id = slot.preparation_id
    db.delete(slot)
    db.flush()
    sync_preparation_dates(db, prep_id)
    db.commit()
    return prep_id


def _slot_members(slot: PlanningSlot, visible_employee_ids: set[int] | None = None) -> tuple[set[int], set[int]]:
    employees = {x.employee_id for x in slot.team_assignment.employees if visible_employee_ids is None or x.employee_id in visible_employee_ids}
    resources = {x.resource_id for x in slot.team_assignment.resources}
    return employees, resources


def _slot_travel(slot: PlanningSlot, settings: PlanningSettings) -> Decimal:
    if slot.capacity and slot.capacity.travel_hours_per_employee_day is not None:
        return _d(slot.capacity.travel_hours_per_employee_day)
    return _d(settings.default_travel_hours_per_employee_day)


def _slot_distribution(
    db: Session, slot: PlanningSlot, settings: PlanningSettings, holiday_dates: set[date],
    absences: dict[tuple[int, date], EmployeeAbsence], visible_employee_ids: set[int] | None = None,
) -> tuple[dict[date, dict], Decimal]:
    remaining = _infer_slot_hours(db, slot)
    travel = _slot_travel(slot, settings)
    employees = _team_members_from_assignment(slot.team_assignment, visible_employee_ids)
    distribution = {}
    for day in _date_range(slot.start_date, slot.end_date):
        capacity, available, absent = _day_capacity(employees, day, settings, travel, holiday_dates, absences)
        load = min(remaining, capacity)
        remaining -= load
        distribution[day] = {
            "capacity": capacity, "planned": load.quantize(HOUR),
            "available_employee_ids": [e.id for e in available],
            "absent_employee_ids": [a.employee_id for a in absent],
        }
    return distribution, max(Decimal("0"), remaining).quantize(HOUR)


def slot_to_dict(slot: PlanningSlot, conflicts: list[dict] | None = None, db: Session | None = None) -> dict:
    order = slot.preparation.order
    project = order.project
    prop = project.property
    address = ""
    if prop:
        address = ", ".join(x for x in [prop.street, f"{prop.postal_code or ''} {prop.city or ''}".strip()] if x)
    elif order.property_address:
        address = order.property_address.replace("\n", ", ")
    settings = get_or_create_planning_settings(db) if db is not None else None
    travel = _slot_travel(slot, settings) if settings is not None else (_d(slot.capacity.travel_hours_per_employee_day) if slot.capacity else Decimal("0"))
    hours = _infer_slot_hours(db, slot) if db is not None else (_stored_slot_hours(slot) or Decimal("0"))
    visible_ids = planning_visible_employee_ids(db) if db is not None else None
    return {
        "id": slot.id, "preparation_id": slot.preparation_id, "order_id": order.id,
        "order_number": order.order_number, "project_id": project.id,
        "project_number": project.project_number, "project_name": project.name,
        "customer_name": order.customer_name, "property_name": prop.name if prop else order.property_name,
        "property_address": address, "team_assignment_id": slot.team_assignment_id,
        "team_id": slot.team_assignment.team_id, "team_name": slot.team_assignment.team_name_snapshot,
        "start_date": slot.start_date, "end_date": slot.end_date,
        "duration_days": (slot.end_date - slot.start_date).days + 1, "status": slot.status,
        "notes": slot.notes, "planned_hours": hours,
        "travel_hours_per_employee_day": travel,
        "employees": [{"id": x.employee_id, "name": x.employee_name_snapshot, "role": x.role_snapshot} for x in slot.team_assignment.employees if visible_ids is None or x.employee_id in visible_ids],
        "resources": [{"id": x.resource_id, "name": x.resource_name_snapshot, "type": x.resource_type_snapshot, "role": x.role_snapshot} for x in slot.team_assignment.resources],
        "conflicts": conflicts or [],
    }


def _employee_assignment_slot_condition(employee_id: int):
    """Gemeinsame Zuordnungs-Bedingung Mitarbeiter -> PlanningSlot (Team- ODER Einzelzuweisung an
    der Arbeitsvorbereitung) -- seit 1.3.61 aus list_todays_assignments_for_employee()
    ausgelagert, damit list_upcoming_assignments_for_employee() (siehe dort, "Eigene
    Plantafel-Einträge" auf /mobil) dieselbe Zuordnung nutzt statt sie ein zweites Mal
    nachzubauen. Team-Zugehörigkeit über WorkPreparationTeamEmployee (Snapshot der
    Team-Besetzung zum Zuweisungszeitpunkt der WorkPreparationTeamAssignment, an der der Slot
    über team_assignment_id hängt), direkte Einzelzuweisung über WorkPreparationEmployee (an der
    WorkPreparation selbst, nicht am einzelnen Slot -- jeder Slot dieser AV zählt dann)."""
    team_slot_ids = (
        select(PlanningSlot.id)
        .join(WorkPreparationTeamAssignment, PlanningSlot.team_assignment_id == WorkPreparationTeamAssignment.id)
        .join(WorkPreparationTeamEmployee, WorkPreparationTeamEmployee.assignment_id == WorkPreparationTeamAssignment.id)
        .where(WorkPreparationTeamEmployee.employee_id == employee_id)
    )
    individual_slot_ids = (
        select(PlanningSlot.id)
        .join(WorkPreparation, PlanningSlot.preparation_id == WorkPreparation.id)
        .join(WorkPreparationEmployee, WorkPreparationEmployee.preparation_id == WorkPreparation.id)
        .where(WorkPreparationEmployee.employee_id == employee_id)
    )
    return PlanningSlot.id.in_(team_slot_ids) | PlanningSlot.id.in_(individual_slot_ids)


def _slot_query_with_order_options():
    """Gemeinsame Basisabfrage (Eager-Load bis zum Objekt) für beide Funktionen unten."""
    return select(PlanningSlot).options(
        selectinload(PlanningSlot.preparation)
        .selectinload(WorkPreparation.order)
        .selectinload(Order.project)
        .selectinload(Project.property),
    )


def _slot_to_assignment_dict(db: Session, slot: PlanningSlot, *, include_report_count: bool) -> dict:
    """Adress-/Objektname-Auflösung exakt wie in slot_to_dict(): order.project.property geht vor,
    order.property_name/-address ist der Rückfall ohne verknüpftes Objekt."""
    order = slot.preparation.order
    project = order.project
    prop = project.property if project else None
    if prop:
        address = ", ".join(x for x in [prop.street, f"{prop.postal_code or ''} {prop.city or ''}".strip()] if x)
    else:
        address = order.property_address.replace("\n", ", ") if order.property_address else ""
    result = {
        "slot_id": slot.id, "order_id": order.id, "order_number": order.order_number,
        "customer_name": order.customer_name,
        "property_name": prop.name if prop else order.property_name,
        "property_address": address,
        "start_date": slot.start_date, "end_date": slot.end_date,
    }
    if include_report_count:
        result["report_count"] = count_reports_for_order(db, order.id)
    return result


def list_todays_assignments_for_employee(db: Session, employee_id: int, day: date | None = None) -> list[dict]:
    """Für die Monteursansicht (/mobil, seit 1.3.0, bis 1.3.60 unter /vor-ort) -- alle
    PlanningSlot-Zeilen, die einen Mitarbeiter für den angegebenen Tag betreffen, über beide
    Zuordnungswege (siehe _employee_assignment_slot_condition())."""
    day = day or date.today()
    query = (
        _slot_query_with_order_options()
        .where(PlanningSlot.start_date <= day, PlanningSlot.end_date >= day, _employee_assignment_slot_condition(employee_id))
        .order_by(PlanningSlot.start_date)
    )
    slots = db.scalars(query).all()

    result = []
    seen_slot_ids: set[int] = set()
    for slot in slots:
        if slot.id in seen_slot_ids:
            continue  # ein Slot kann über BEIDE Wege gleichzeitig zutreffen, kein Duplikat
        seen_slot_ids.add(slot.id)
        result.append(_slot_to_assignment_dict(db, slot, include_report_count=True))
    return result


def list_upcoming_assignments_for_employee(db: Session, employee_id: int, *, today: date | None = None,
                                            days_ahead: int = 30) -> list[dict]:
    """"Eigene Plantafel-Einträge" auf /mobil (seit 1.3.61, siehe CLAUDE.md) -- eine reine
    Leseansicht der KOMMENDEN eigenen Termine, kein Zugriff auf die Plantafel selbst: dieselbe
    Zuordnung wie list_todays_assignments_for_employee() (_employee_assignment_slot_condition()),
    aber über ein Zeitfenster statt eines einzelnen Tages. Bewusst `end_date >= today` (nicht
    `start_date >= today`) -- ein bereits laufender, mehrtägiger Einsatz bleibt sichtbar, auch
    wenn sein Slot vor dem Fensterbeginn angefangen hat, exakt wie bei der Tagesliste selbst.
    `days_ahead` (Standard 30) begrenzt den Horizont, damit die Liste nicht mit weit in der
    Zukunft liegenden, noch unsicheren Terminen überladen wird -- kein neues Datenmodell, dieselben
    beiden Zuordnungstabellen (WorkPreparationEmployee/WorkPreparationTeamAssignment) wie überall
    sonst in diesem Abschnitt."""
    today = today or date.today()
    window_end = today + timedelta(days=days_ahead)
    query = (
        _slot_query_with_order_options()
        .where(
            PlanningSlot.end_date >= today, PlanningSlot.start_date <= window_end,
            _employee_assignment_slot_condition(employee_id),
        )
        .order_by(PlanningSlot.start_date)
    )
    slots = db.scalars(query).all()

    result = []
    seen_slot_ids: set[int] = set()
    for slot in slots:
        if slot.id in seen_slot_ids:
            continue
        seen_slot_ids.add(slot.id)
        result.append(_slot_to_assignment_dict(db, slot, include_report_count=False))
    return result


def _relevant_preparation_ids_for_employee(db: Session, employee_id: int, *, window_days: int,
                                            today: date) -> set[int]:
    """Gemeinsame Zeitfenster-Logik für list_field_relevant_property_ids() (Objekte) UND
    list_field_bookable_order_ids() (Aufträge, seit 1.3.60) -- welche Arbeitsvorbereitungen eines
    Mitarbeiters innerhalb von ±window_days um `today` liegen, entweder über einen echten
    PlanningSlot oder (Rückfall) über WorkPreparation.planned_start/planned_end. Ausgelagert, damit
    beide Funktionen exakt dasselbe Fenster auswerten statt es zweimal parallel nachzubauen --
    „was dort als 'meine Objekte' gilt, gilt hier als 'meine Aufträge'" (Betreibervorgabe)."""
    window_start = today - timedelta(days=window_days)
    window_end = today + timedelta(days=window_days)

    order_ids = employee_assigned_order_ids(db, employee_id)
    if not order_ids:
        return set()

    preps = db.scalars(select(WorkPreparation).where(WorkPreparation.order_id.in_(order_ids))).all()
    if not preps:
        return set()
    prep_by_id = {p.id: p for p in preps}

    slot_rows = db.execute(
        select(PlanningSlot.preparation_id, func.min(PlanningSlot.start_date), func.max(PlanningSlot.end_date))
        .where(PlanningSlot.preparation_id.in_(prep_by_id))
        .group_by(PlanningSlot.preparation_id)
    ).all()
    relevant_prep_ids: set[int] = set()
    prep_ids_with_slot: set[int] = set()
    for prep_id, start, end in slot_rows:
        prep_ids_with_slot.add(prep_id)
        if start <= window_end and end >= window_start:
            relevant_prep_ids.add(prep_id)

    for prep_id, prep in prep_by_id.items():
        if prep_id in prep_ids_with_slot:
            continue  # bereits über einen echten PlanningSlot entschieden
        start = prep.planned_start or prep.planned_end
        end = prep.planned_end or prep.planned_start
        if start is None:
            continue  # weder Slot noch geplanter Zeitraum -- kein Datum, keine Aufnahme
        if start <= window_end and end >= window_start:
            relevant_prep_ids.add(prep_id)

    return relevant_prep_ids


def list_field_relevant_property_ids(db: Session, employee_id: int, *, window_days: int = 14,
                                      today: date | None = None) -> set[int]:
    """Objekte, an denen ein Monteur aktuell oder in Kürze zu tun hat -- Grundlage für die Karte
    "Wartungen an meinen Objekten" auf /mobil (Rechtekonzept, siehe CLAUDE.md, Abschnitt
    "Objekt-Filterung" bzw. der Nachtrag zum /mobil-Vertragsfinder dort).

    Betreibervorgabe: kein ungefiltertes "war je einmal zugeordnet" (würde über die Jahre zu
    einer Liste mit lauter Altlasten anwachsen), stattdessen ein großzügiges Zeitfenster
    (±window_days Tage) um eine TATSÄCHLICHE Terminierung. WorkPreparation.status bewusst NICHT
    einbezogen -- geprüft: das Feld lässt sich zwar ändern (PUT .../work-preparation, Büro-
    Formular mit fünf Werten), aber die reale Datenbank enthält bei dieser Prüfung nur eine
    einzige WorkPreparation-Zeile insgesamt, zu dünn für ein Urteil über die Zuverlässigkeit im
    Alltag -- und "offen ODER Zeitfenster" hätte genau das Risiko wieder eingeführt, das dieses
    Zeitfenster vermeiden soll: eine vergessene, nie auf "abgeschlossen" gesetzte AV bliebe dann
    unabhängig vom Datum sichtbar. Zeitfenster allein ist deshalb der sauberere Weg (Nutzervorgabe
    für genau diesen Fall).

    Datumsquelle: die Zuordnung hängt an der AV (dieselben Aufträge wie employee_assigned_order_ids()
    in app/orders.py -- Team- oder Einzelzuweisung), das Datum kommt aus JEDEM PlanningSlot dieser
    AV (unabhängig davon, über welchen der beiden Wege der Mitarbeiter zugeordnet ist -- ein
    PlanningSlot trägt preparation_id, nicht employee_id). Fehlt jede Terminierung (AV noch nicht
    in die Plantafel eingeplant), WorkPreparation.planned_start/planned_end als Rückfall. Fehlt
    auch das, bleibt die AV unberücksichtigt -- kein Anhaltspunkt für "aktuell", kein Raten.

    Liefert Property.id -- bei einem Auftrag ohne verknüpftes Objekt (Order.project.property_id
    IS NULL) zusätzlich die Hauptadresse-Property-ID des Kunden (is_primary_address), damit ein
    Wartungsvertrag mit property_id IS NULL (bedeutet "Hauptadresse", siehe contract_to_dict() in
    app/maintenance_contracts.py) über denselben Abgleich gefunden werden kann."""
    today = today or date.today()
    relevant_prep_ids = _relevant_preparation_ids_for_employee(db, employee_id, window_days=window_days, today=today)
    if not relevant_prep_ids:
        return set()

    orders = db.scalars(
        select(Order)
        .join(WorkPreparation, WorkPreparation.order_id == Order.id)
        .where(WorkPreparation.id.in_(relevant_prep_ids))
        .options(selectinload(Order.project).selectinload(Project.property))
    ).all()

    property_ids: set[int] = set()
    customer_ids_needing_primary: set[int] = set()
    for order in orders:
        project = order.project
        prop = project.property if project else None
        if prop is not None:
            property_ids.add(prop.id)
        elif project is not None and project.customer_id is not None:
            customer_ids_needing_primary.add(project.customer_id)

    if customer_ids_needing_primary:
        primary_ids = db.scalars(
            select(Property.id).where(
                Property.customer_id.in_(customer_ids_needing_primary),
                Property.is_primary_address == True,  # noqa: E712 -- SQLAlchemy-Vergleich
            )
        ).all()
        property_ids.update(primary_ids)

    return property_ids


def list_field_bookable_order_ids(db: Session, employee_id: int, *, window_days: int = 14,
                                   today: date | None = None) -> set[int]:
    """Aufträge, die ein Monteur in der reduzierten Zeiterfassung auf /mobil wählen darf (seit
    1.3.60, siehe CLAUDE.md „Zeiterfassung für Monteure"). Dasselbe Zeitfenster wie
    list_field_relevant_property_ids() (1.3.58-Wartungsfinder), auf Aufträge statt Objekte
    angewendet -- „was dort als 'meine Objekte' gilt, gilt hier als 'meine Aufträge'"
    (Betreibervorgabe).

    Vor dem Bauen geprüft (Betreibervorgabe: "das Fenster muss den laufenden Einsatz sicher
    erfassen"): das Fenster selbst deckt den Fall "gestern zugewiesen, heute im Einsatz"
    zuverlässig ab, SOFERN die Arbeitsvorbereitung überhaupt ein Datum trägt (echter PlanningSlot
    oder planned_start/-end) -- ein für heute eingeplanter Einsatz liegt bei jeder sinnvollen
    Fenstergröße innerhalb ±window_days um heute. Ein echter, unabhängig von der Fenstergröße
    bestehender Fund dabei: ein per "Wartung durchführen" (create_maintenance_visit(), seit 1.3.56
    auch für Monteure) gestarteter, UNGEPLANTER Auftrag hat GAR KEINE WorkPreparation --
    create_quick_service_order() legt bewusst keine an (kein Plantafel-Bezug). Ein solcher Auftrag
    taucht in employee_assigned_order_ids() und damit in keinem Zeitfenster jemals auf, unabhängig
    von dessen Größe -- das Problem ist eine fehlende Datumsquelle, kein zu enges Fenster.

    Deshalb zusätzlich, UNGEFENSTERT: jeder Auftrag, zu dem der Monteur bereits selbst einen
    ServiceReport angelegt hat (created_by_employee_id) -- exakt der zweite der beiden Wege, über
    die field_may_access_order() (app/orders.py) einem Monteur Zugriff auf einen Auftrag gewährt.
    Ohne diese zweite Quelle könnte ein Monteur nach "Wartung durchführen" zwar seinen Bericht
    öffnen, aber keine Zeit auf den dafür entstandenen Auftrag buchen -- exakt die Divergenz, die
    field_may_access_order() an anderer Stelle bereits ausdrücklich vermeidet ("ein Monteur soll
    nie Zeit auf einen Auftrag buchen können, dessen Bericht er nicht öffnen darf, oder
    umgekehrt")."""
    today = today or date.today()
    relevant_prep_ids = _relevant_preparation_ids_for_employee(db, employee_id, window_days=window_days, today=today)

    order_ids: set[int] = set()
    if relevant_prep_ids:
        order_ids.update(db.scalars(
            select(WorkPreparation.order_id).where(WorkPreparation.id.in_(relevant_prep_ids))
        ).all())
    order_ids.update(db.scalars(
        select(ServiceReport.order_id).where(ServiceReport.created_by_employee_id == employee_id).distinct()
    ).all())
    return order_ids


def _conflicts(db: Session, slots: list[PlanningSlot], settings: PlanningSettings) -> tuple[dict[int, list[dict]], dict[int, dict[date, dict]]]:
    result: dict[int, list[dict]] = defaultdict(list)
    distributions: dict[int, dict[date, dict]] = {}
    if not slots:
        return result, distributions
    start = min(s.start_date for s in slots); end = max(s.end_date for s in slots)
    holiday_names, _holiday_meta = _combined_holiday_map(db, start, end); holiday_dates = set(holiday_names)
    visible_employee_ids = planning_visible_employee_ids(db)
    employee_ids = {x.employee_id for s in slots for x in s.team_assignment.employees if x.employee_id in visible_employee_ids}
    absence_rows = _absence_rows(db, start, end, employee_ids); absences = _absence_map(absence_rows)

    for i, a in enumerate(slots):
        a_emps, a_res = _slot_members(a, visible_employee_ids)
        for b in slots[i + 1:]:
            if not _ranges_overlap(a.start_date, a.end_date, b.start_date, b.end_date):
                continue
            b_emps, b_res = _slot_members(b, visible_employee_ids)
            issues = []
            if a.team_assignment.team_id == b.team_assignment.team_id:
                issues.append(("team", a.team_assignment.team_name_snapshot))
            for eid in sorted(a_emps & b_emps):
                name = next((x.employee_name_snapshot for x in a.team_assignment.employees if x.employee_id == eid), f"Mitarbeiter #{eid}")
                issues.append(("employee", name))
            for rid in sorted(a_res & b_res):
                resource = next((x for x in a.team_assignment.resources if x.resource_id == rid), None)
                issues.append(("resource", resource.resource_name_snapshot if resource else f"Ressource #{rid}"))
            for kind, label in issues:
                result[a.id].append({"type": kind, "label": label, "other_slot_id": b.id, "other_project": b.preparation.order.project.project_number, "other_project_name": b.preparation.order.project.name})
                result[b.id].append({"type": kind, "label": label, "other_slot_id": a.id, "other_project": a.preparation.order.project.project_number, "other_project_name": a.preparation.order.project.name})

    for slot in slots:
        distribution, shortfall = _slot_distribution(db, slot, settings, holiday_dates, absences, visible_employee_ids)
        distributions[slot.id] = distribution
        seen_absence = set()
        for day in _date_range(slot.start_date, slot.end_date):
            if day in holiday_names:
                result[slot.id].append({"type":"holiday", "label":holiday_names[day], "date":day, "other_slot_id":None, "other_project":None, "other_project_name":None})
            for member in slot.team_assignment.employees:
                if member.employee_id not in visible_employee_ids: continue
                absence = absences.get((member.employee_id, day))
                if absence and absence.id not in seen_absence:
                    seen_absence.add(absence.id)
                    # label_redacted ist das buero_auftrag-sichere Gegenstück (siehe CLAUDE.md
                    # "Krankheitssichtbarkeit") -- der Router entscheidet anhand der Rolle, welche
                    # der beiden Label-Varianten in der Antwort landet, diese Funktion bleibt
                    # rollenblind.
                    result[slot.id].append({"type":"absence", "label":f"{member.employee_name_snapshot} · {absence.absence_type}", "label_redacted":f"{member.employee_name_snapshot} · abwesend", "date":day, "other_slot_id":None, "other_project":None, "other_project_name":None})
        if shortfall > 0:
            result[slot.id].append({"type":"capacity", "label":f"Kapazität reicht um {shortfall} h nicht aus", "shortfall_hours":shortfall, "other_slot_id":None, "other_project":None, "other_project_name":None})
    return result, distributions


def planning_suggestion(
    db: Session, *, order_id: int, team_id: int, start_date: date,
    daily_work_hours: Decimal | None = None, travel_hours_per_employee_day: Decimal | None = None,
) -> dict:
    order = load_order(db, order_id)
    if order is None:
        raise ValueError("Auftrag wurde nicht gefunden.")
    team = _load_team(db, team_id)
    if team is None or not team.active:
        raise ValueError("Kolonne / Team wurde nicht gefunden oder ist inaktiv.")
    visible_employee_ids = planning_visible_employee_ids(db)
    employees = _team_members_from_master(team, visible_employee_ids)
    if not employees:
        raise ValueError("Die Kolonne hat keine aktiven Mitarbeiter.")
    settings = get_or_create_planning_settings(db)
    daily = _d(daily_work_hours if daily_work_hours is not None else settings.daily_work_hours)
    travel = _d(travel_hours_per_employee_day if travel_hours_per_employee_day is not None else settings.default_travel_hours_per_employee_day)
    if travel >= daily:
        raise ValueError("Anfahrtszeit muss kleiner als die tägliche Arbeitszeit sein.")
    # Temporäre Kopie der Einstellungen für den Vorschlag, damit ein manueller Tageswert berücksichtigt wird.
    class _Temp: pass
    tmp = _Temp()
    for attr in ("monday","tuesday","wednesday","thursday","friday","saturday","sunday"):
        setattr(tmp, attr, getattr(settings, attr))
    tmp.daily_work_hours = daily
    target = planned_hours(order)
    if target <= 0:
        raise ValueError("Für diesen Auftrag sind keine kalkulierten Soll-Stunden vorhanden.")
    horizon_end = start_date + timedelta(days=730)
    holiday_map, _holiday_meta = _combined_holiday_map(db, start_date, horizon_end); holiday_dates=set(holiday_map)
    abs_rows = _absence_rows(db, start_date, horizon_end, {e.id for e in employees}); absences = _absence_map(abs_rows)
    full_capacity, _, _ = _day_capacity(employees, next((d for d in _date_range(start_date, horizon_end) if _is_workday(d,tmp,set())), start_date), tmp, travel, set(), {})
    if full_capacity <= 0:
        raise ValueError("Mit den gewählten Arbeits-/Anfahrtszeiten ergibt sich keine verfügbare Tageskapazität.")
    remaining = target
    day_rows=[]; current=start_date; last=None; workdays_used=0
    while remaining > 0 and current <= horizon_end:
        cap, available, absent = _day_capacity(employees, current, tmp, travel, holiday_dates, absences)
        if cap > 0:
            assigned=min(remaining,cap); remaining-=assigned; workdays_used+=1; last=current
            day_rows.append({
                "date":current, "capacity_hours":cap, "assigned_hours":assigned.quantize(HOUR),
                "available_employee_count":len(available), "available_employees":[_employee_name(x) for x in available],
                "absent_employees":[{"name":_employee_name(a.employee),"type":a.absence_type} for a in absent],
                "holiday":None,
            })
        elif current in holiday_map:
            day_rows.append({"date":current,"capacity_hours":Decimal("0"),"assigned_hours":Decimal("0"),"available_employee_count":0,"available_employees":[],"absent_employees":[],"holiday":holiday_map[current]})
        current += timedelta(days=1)
    if remaining > 0 or last is None:
        raise ValueError("Im betrachteten Zeitraum konnte keine ausreichende Planungskapazität ermittelt werden.")
    equivalent_days=(target/full_capacity).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    lastrow=next((x for x in reversed(day_rows) if x["assigned_hours"]>0),None)
    last_clock=None
    if lastrow and lastrow["available_employee_count"]:
        last_clock=(lastrow["assigned_hours"]/Decimal(lastrow["available_employee_count"])+travel).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    return {
        "order_id":order_id,"team_id":team_id,"team_name":team.name,"employee_count":len(employees),
        "planned_hours":target,"daily_work_hours":daily,"travel_hours_per_employee_day":travel,
        "full_team_daily_capacity":full_capacity,"required_team_days_decimal":equivalent_days,
        "calendar_workdays_needed":workdays_used,"suggested_start":start_date,"suggested_end":last,
        "last_day_clock_hours_per_employee":last_clock,"days":day_rows,
        "formula":f"{target} h / ({len(employees)} MA × ({daily} h − {travel} h)) = {equivalent_days} Teamtage",
    }


def planning_board(db: Session, start_date: date, end_date: date) -> dict:
    if end_date < start_date:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    if (end_date - start_date).days > 62:
        raise ValueError("Die Plantafel kann maximal 63 Tage gleichzeitig anzeigen.")
    settings = get_or_create_planning_settings(db)
    all_slots = db.scalars(
        select(PlanningSlot)
        .options(
            selectinload(PlanningSlot.capacity),
            selectinload(PlanningSlot.preparation).selectinload(WorkPreparation.order).selectinload(Order.project),
            selectinload(PlanningSlot.team_assignment).selectinload(WorkPreparationTeamAssignment.employees).selectinload(WorkPreparationTeamEmployee.employee),
            selectinload(PlanningSlot.team_assignment).selectinload(WorkPreparationTeamAssignment.resources).selectinload(WorkPreparationTeamResource.resource),
        ).order_by(PlanningSlot.start_date, PlanningSlot.id)
    ).all()
    visible = [x for x in all_slots if _ranges_overlap(x.start_date, x.end_date, start_date, end_date)]
    conflict_map, distributions = _conflicts(db, all_slots, settings)

    teams = db.scalars(select(Team).options(selectinload(Team.employees).selectinload(TeamEmployee.employee),selectinload(Team.resources).selectinload(TeamResource.resource)).order_by(Team.name)).all()
    visible_employee_ids=planning_visible_employee_ids(db)
    used_team_ids = {x.team_assignment.team_id for x in visible}
    team_rows=[]
    for team in teams:
        if not team.active and team.id not in used_team_ids: continue
        team_rows.append({"id":team.id,"number":team.team_number,"name":team.name,"active":team.active,
            "employees":[{"id":x.employee_id,"name":_employee_name(x.employee),"role":x.role} for x in team.employees if x.employee and x.employee_id in visible_employee_ids],
            "resources":[{"id":x.resource_id,"name":x.resource.name,"type":x.resource.resource_type,"role":x.role} for x in team.resources if x.resource]})
    all_employees=db.scalars(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.active==True).order_by(Employee.last_name,Employee.first_name)).all()
    employees=[x for x in all_employees if x.id in visible_employee_ids]
    resources=db.scalars(select(OperationalResource).where(OperationalResource.active==True).order_by(OperationalResource.resource_type,OperationalResource.name)).all()

    holiday_names, holiday_meta=_combined_holiday_map(db,start_date,end_date); holiday_dates=set(holiday_names)
    school_holidays, school_warnings=school_holidays_for_range(db,start_date,end_date,auto_sync=False)
    school_by_day={}
    for sh in school_holidays:
        for day in _date_range(max(start_date,sh["start_date"]),min(end_date,sh["end_date"])):
            school_by_day.setdefault(day,[]).append(sh["name"])
    absence_rows=_absence_rows(db,start_date,end_date,{x.id for x in employees}); absences=_absence_map(absence_rows)
    dates=list(_date_range(start_date,end_date))
    team_capacity={}
    for team in teams:
        members=_team_members_from_master(team,visible_employee_ids); rows={}
        for day in dates:
            cap,available,absent=_day_capacity(members,day,settings,_d(settings.default_travel_hours_per_employee_day),holiday_dates,absences)
            planned=sum((distributions.get(slot.id,{}).get(day,{}).get("planned",Decimal("0")) for slot in visible if slot.team_assignment.team_id==team.id),Decimal("0"))
            util=(planned/cap*100 if cap>0 else (Decimal("100") if planned>0 else Decimal("0"))).quantize(Decimal("0.1"))
            rows[day.isoformat()]={"capacity_hours":cap,"planned_hours":planned.quantize(HOUR),"utilization_pct":util,"available_employee_count":len(available),"absences":[{"employee_id":a.employee_id,"name":_employee_name(a.employee),"type":a.absence_type} for a in absent],"holiday":holiday_names.get(day),"school_holidays":school_by_day.get(day,[])}
        team_capacity[str(team.id)]=rows
    employee_capacity={}
    for emp in employees:
        rows={}
        for day in dates:
            if not _is_workday(day,settings,holiday_dates) or absences.get((emp.id,day)):
                cap=Decimal("0")
            else: cap=_employee_net_capacity(emp,settings,_d(settings.default_travel_hours_per_employee_day))
            planned=Decimal("0")
            for slot in visible:
                dist=distributions.get(slot.id,{}).get(day)
                if not dist or emp.id not in dist.get("available_employee_ids",[]): continue
                total_cap=dist.get("capacity",Decimal("0"))
                if total_cap>0:
                    planned += dist.get("planned",Decimal("0"))*_employee_net_capacity(emp,settings,_slot_travel(slot,settings))/total_cap
            util=(planned/cap*100 if cap>0 else (Decimal("100") if planned>0 else Decimal("0"))).quantize(Decimal("0.1"))
            a=absences.get((emp.id,day))
            rows[day.isoformat()]={"capacity_hours":cap.quantize(HOUR),"planned_hours":planned.quantize(HOUR),"utilization_pct":util,"absence":a.absence_type if a else None,"holiday":holiday_names.get(day),"school_holidays":school_by_day.get(day,[])}
        employee_capacity[str(emp.id)]=rows
    resource_load={}
    for res in resources:
        resource_load[str(res.id)]={day.isoformat():sum(1 for slot in visible if any(x.resource_id==res.id for x in slot.team_assignment.resources) and slot.start_date<=day<=slot.end_date) for day in dates}

    planned_prep_ids={x.preparation_id for x in all_slots}
    orders=db.scalars(select(Order).options(selectinload(Order.project)).order_by(Order.order_date.desc(),Order.id.desc())).all()
    work_preps={x.order_id:x for x in db.scalars(select(WorkPreparation)).all()}; backlog=[]
    for order in orders:
        prep=work_preps.get(order.id)
        if prep and prep.id in planned_prep_ids: continue
        loaded_order=load_order(db,order.id); prop=order.project.property; address=""
        if prop: address=", ".join(x for x in [prop.street,f"{prop.postal_code or ''} {prop.city or ''}".strip()] if x)
        elif order.property_address: address=order.property_address.replace("\n",", ")
        backlog.append({"order_id":order.id,"order_number":order.order_number,"project_id":order.project_id,"project_number":order.project.project_number,"project_name":order.project.name,"customer_name":order.customer_name,"property_address":address,"planned_hours":planned_hours(loaded_order) if loaded_order else Decimal("0"),"suggested_start":prep.planned_start if prep else order.execution_start,"suggested_end":prep.planned_end if prep else order.execution_end})

    return {"start_date":start_date,"end_date":end_date,"settings":planning_settings_dict(settings,db),"holidays":holiday_meta,"school_holidays":school_holidays,"school_holiday_warnings":school_warnings,
        "absences":[{"id":x.id,"employee_id":x.employee_id,"employee_name":_employee_name(x.employee),"absence_type":x.absence_type,"start_date":x.start_date,"end_date":x.end_date,"notes":x.notes} for x in absence_rows],
        "teams":team_rows,
        "employees":[{"id":x.id,"employee_number":x.employee_number,"name":_employee_name(x),"function":x.profile.function.name if x.profile and x.profile.function else x.job_title} for x in employees],
        "resources":[{"id":x.id,"resource_number":x.resource_number,"name":x.name,"type":x.resource_type,"identifier":x.identifier} for x in resources],
        "slots":[slot_to_dict(x,conflict_map.get(x.id,[]),db) for x in visible],"backlog":backlog,"conflict_count":sum(1 for x in visible if conflict_map.get(x.id)),
        "team_capacity":team_capacity,"employee_capacity":employee_capacity,"resource_load":resource_load}
