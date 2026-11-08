from __future__ import annotations

from collections import defaultdict
from datetime import date, time, timedelta, datetime, timezone
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .auftragsstatus import AuftragGeschlossen, einsatz_gesperrt, geschlossen, name as status_name, offen_bedingung, pause_begruendung, pause_begruendungen, wert as status_wert
from .grunddaten import einzelzeile
from .berlin_time import berlin_today
from .calendar_events import BUSY_PLACEHOLDER_TITLE
from .models import (
    CalendarEvent, OutlookSeriesOccurrence, OperationalAsset, OperationalAssetInspection,
    Employee, EmployeeAbsence, EmployeeAbsenceRequest, EmployeePlanningSettings, EmployeeProfile, OperationalResource, Order, OrderItem, PlanningHoliday,
    PlanningSettings, PlanningRegionSettings, PlanningSchoolHoliday, PlanningSchoolHolidaySync, PlanningSlot, PlanningSlotCapacity, PlanningSlotEmployee,
    PlanningSlotResource, Project, Property, ServiceReport, Team, TeamEmployee,
    TeamResource, WorkPreparation, WorkPreparationEmployee, WorkPreparationTeamAssignment,
    WorkPreparationTeamEmployee, WorkPreparationTeamResource,
)
from .akte import stunden_text
from . import kran_kalender
from .orders import employee_assigned_order_ids, load_order
from .service_reports import count_reports_for_order
from .work_preparation import ensure_preparation, planned_hours
from .version import APP_VERSION
from .rounding import round_half_up, round_hours


# Seit 1.9.143 (Stufe 6, R1, Punkt 1): was beim Speichern eines Einsatzes rückfragt (409 mit Liste, bis „trotzdem planen“ mitkommt) und was nur in der
# Antwort steht. Der Betrieb darf alles planen -- Tobias: „Konflikte warnen, trotzdem planbar“.
# Seit 1.9.236 (Stufe 6, R3a, Punkt 5, Zeichnung „Konflikte“): ohne „team“ (Kolonne doppelt -- es zählen die Personen), dazu „pruefung“ (Gerät mit
# abgelaufener Prüffrist). Bis 1.9.235: team, employee, resource, absence.
WARNUNG_ARTEN = frozenset({"employee", "resource", "absence", "pruefung"})  # Kolonne, Person, Gerät doppelt; Person abwesend
HINWEIS_ARTEN = frozenset({"holiday", "capacity", "antrag_offen", "kalendertag"})  # Feiertag, betriebsfreier Tag, Kapazität, offener Antrag; seit 1.9.188 Freistellung des Arbeitszeitkalenders. Seit 1.9.150 kein Wochenende: es ist nur kein Arbeitstag, ein Einsatz darüber meldet nichts
FAERBT_NICHT = frozenset({"antrag_offen"})  # seit 1.9.152: steht beim Einsatz, macht ihn aber nicht zum Konflikt -- kein rot, nicht in conflict_count
WARNUNG_TEXT = "Der Einsatz überschneidet sich – bitte prüfen oder trotzdem planen."


# Seit 1.9.235 (Stufe 6, R3a, Punkt 4): der Status eines Einsatzes -- vorläufig (auf der Tafel gestrichelt, R4) oder fest. Abgeschlossen und storniert
# kommen vom Auftrag (app/auftragsstatus.py), nicht vom Einsatz. Bis 1.9.234 freier Text ohne Wirkung (geplant, bestaetigt, in_ausfuehrung, pausiert,
# abgeschlossen; Befund Stufe 6, 3.3); die Migration a7d3e5f9c214 machte „geplant“ zu vorläufig, alles andere zu fest.
EINSATZ_STATUS = {"vorlaeufig": "vorläufig", "fest": "fest"}
EINSATZ_STATUS_FALSCH = "Der Status eines Einsatzes ist „vorläufig“ oder „fest“."
# seit 1.9.240 (Stufe 6, R3b, Punkt 2): die Art eines Einsatzes, fest ab dem Anlegen
EINSATZ_ARTEN = {"baustelle": "Baustelle", "kranvermietung": "Kranvermietung"}
KRANVERMIETUNG_POSITION = "Kranvermietung nach Aufwand"
KRAN_OHNE_GERAET = "Eine Kranvermietung braucht den Kran: bitte mindestens ein Gerät wählen."
KRAN_OHNE_KOLONNE = "Eine Kranvermietung hat keine Kolonne; Bediener bitte einzeln wählen."


EINSATZ_LEER = "Der Einsatz hat dann niemanden mehr."  # seit 1.9.263 (Stufe 6, R5a, Punkt 4, Antwort 3)
WENN_LEER = ("loeschen", "behalten")


class EinsatzWirdLeer(Exception):
    """Seit 1.9.263: eine Änderung nähme dem Einsatz den letzten Tag mit jemandem (keine Person, kein Gerät mehr) -- nichts gespeichert, 409 mit der
    Rückfrage „Löschen | Behalten“; gefragt wird erneut mit wenn_leer."""


class PlanungsWarnung(Exception):
    """Der Einsatz hat Warnungen und „trotzdem planen“ fehlt -- nichts gespeichert (409). Die Listen sind reine Daten, kein ORM-Objekt."""

    def __init__(self, warnungen: list[dict], hinweise: list[dict]):
        super().__init__(WARNUNG_TEXT)
        self.warnungen = warnungen
        self.hinweise = hinweise


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

def load_region_settings(db: Session) -> PlanningRegionSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, PlanningRegionSettings)

def update_region_settings(db: Session, *, federal_state_code: str, auto_public_holidays: bool, show_school_holidays: bool) -> PlanningRegionSettings:
    code = (federal_state_code or "NW").upper()
    if code not in GERMAN_STATES:
        raise ValueError("Unbekanntes Bundesland.")
    row = load_region_settings(db)
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
    region=load_region_settings(db); manual=_manual_holiday_map(db,start,end); auto={}
    if region.auto_public_holidays:
        auto=automatic_public_holidays(region.federal_state_code, range(start.year,end.year+1))
        auto={d:n for d,n in auto.items() if start<=d<=end}
    combined=dict(auto); combined.update(manual)
    rows=[]
    for d,n in sorted(combined.items()):
        rows.append({"date":d,"name":n,"source":"manual" if d in manual else "automatic"})
    return combined, rows

def _plantafel_map(db: Session, employees: list[Employee]) -> dict[int,str]:
    """Seit 1.9.253: das Kennzeichen „Plantafel“ je Mitarbeiter (einplanbar | bauleitung | nicht_zeigen), eine Abfrage für alle; ohne Zeile die Vorgabe
    aus Gruppe und Funktion (app/employees.py::_default_plantafel())."""
    from .employees import _default_plantafel
    ids=[e.id for e in employees if e.id]
    stored={r.employee_id:r.plantafel for r in db.scalars(select(EmployeePlanningSettings).where(EmployeePlanningSettings.employee_id.in_(ids))).all()} if ids else {}
    return {e.id:stored.get(e.id) or _default_plantafel(e) for e in employees}

def planning_visible_employee_ids(db: Session) -> set[int]:
    """In Plantafel und Kapazität: aktiv und nicht „nicht zeigen“ (seit 1.9.253 das Kennzeichen, bis 1.9.252 das Häkchen)."""
    employees=db.scalars(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.active==True)).all()
    kz=_plantafel_map(db,employees); return {e.id for e in employees if kz.get(e.id,"einplanbar")!="nicht_zeigen"}

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
    region=load_region_settings(db)
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


def load_planning_settings(db: Session) -> PlanningSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, PlanningSettings)


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
        region = load_region_settings(db)
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
    row = load_planning_settings(db)
    region_keys = {k: values.pop(k) for k in list(values) if k in {"federal_state_code","auto_public_holidays","show_school_holidays"}}
    for key, value in values.items():
        setattr(row, key, value)
    if region_keys:
        current = load_region_settings(db)
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


def count_workday_holidays(db: Session, start: date, end: date) -> int:
    """Feiertage im Zeitraum, die auf einen laut PlanningSettings konfigurierten Arbeitstag
    fallen -- ein Feiertag am Wochenende zieht keine Arbeitsstunden ab. Nimmt die Arbeitstage der
    Planung (_working_weekdays()), keine zweite, abweichende "Wochenende"-Annahme (bis 1.9.210 auch die
    der Kapazität; seit 1.9.211 rechnet die Kapazität mit der Sollzeit) -- genutzt vom Produktivstunden-Rechner
    (app/productive_hours.py) für den Feiertage-Vorschlag. Zählt genau die hinterlegten Zeilen,
    unabhängig davon, für welches Bundesland sie gedacht sind -- PlanningHoliday kennt keine
    Bundesland-Spalte, es ist eine einzige, unternehmensweite Liste."""
    working_days = _working_weekdays(load_planning_settings(db))
    return sum(1 for h in _holiday_rows(db, start, end) if h.holiday_date.weekday() in working_days)


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


def _offene_antraege(db: Session, start: date, end: date, employee_ids: set[int]) -> dict[int, list[EmployeeAbsenceRequest]]:
    """Seit 1.9.152: offene Anträge je Mitarbeiter im Zeitraum, eine Abfrage. Sie zählen in keiner Kapazität -- dafür gibt es nur die genehmigte Abwesenheit (_absence_rows())."""
    if not employee_ids:
        return {}
    je_person: dict[int, list[EmployeeAbsenceRequest]] = defaultdict(list)
    for antrag in db.scalars(select(EmployeeAbsenceRequest).where(
            EmployeeAbsenceRequest.status == "pending", EmployeeAbsenceRequest.start_date <= end, EmployeeAbsenceRequest.end_date >= start,
            EmployeeAbsenceRequest.employee_id.in_(employee_ids)).order_by(EmployeeAbsenceRequest.start_date, EmployeeAbsenceRequest.id)):
        je_person[antrag.employee_id].append(antrag)
    return je_person


def _absence_map(rows: list[EmployeeAbsence]) -> dict[tuple[int, date], EmployeeAbsence]:
    result = {}
    for row in rows:
        for day in _date_range(row.start_date, row.end_date):
            result[(row.employee_id, day)] = row
    return result


class Freistellung:
    """Seit 1.9.188 (L1a Stufe 2, Punkt 3): ein Tag des Arbeitszeitkalenders (Heiligabend, Silvester) als Abwesenheit auf der Plantafel --
    abgeleitet, nicht gespeichert (keine Zeile in EmployeeAbsence, nicht in der Liste der Abwesenheiten, nicht löschbar). Trägt die Felder, die
    Kapazität und Tafel von einer Abwesenheit lesen; ein Einsatz an dem Tag bekommt einen Hinweis (kalendertag), keine Warnung."""

    absence_category = "kalender"
    notes = None

    def __init__(self, employee: Employee, tag: date, eintrag):
        self.id = f"kalender:{employee.id}:{tag.isoformat()}"
        self.employee_id, self.employee, self.start_date, self.end_date = employee.id, employee, tag, tag
        self.absence_type, self.kalendertag = eintrag.abwesenheit, eintrag.name


def _abwesend_map(db: Session, rows: list[EmployeeAbsence], personen, start: date, end: date) -> dict[tuple[int, date], EmployeeAbsence | Freistellung]:
    """Seit 1.9.188: die Abwesenheiten je Person und Tag samt den Freistellungen des Arbeitszeitkalenders (app/arbeitszeitkalender.py::freistellungen(),
    nur gewerbliche mit Sollzeit an dem Tag) -- eine gespeicherte Abwesenheit geht vor."""
    from .arbeitszeitkalender import freistellungen
    je_id = {p.id: p for p in personen if p is not None}
    kalender = {(eid, tag): Freistellung(je_id[eid], tag, eintrag) for (eid, tag), eintrag in freistellungen(db, je_id.values(), start, end).items()}
    return {**kalender, **_absence_map(rows)}


def _is_workday(day: date, settings: PlanningSettings, holiday_dates: set[date]) -> bool:
    return day.weekday() in _working_weekdays(settings) and day not in holiday_dates


def _soll_je_tag(db: Session, personen, start: date, end: date) -> dict[tuple[int, date], Decimal]:
    """Seit 1.9.211 (L1a Stufe 5, Punkt 4): die Sollzeit des Lohns je Person und Tag (app/sollzeit.py, Tarif, eigene Werte, Eintritt und Austritt,
    Arbeitszeitkalender) -- die Grundlage der Kapazität. Bis 1.9.210 rechnete die Tafel mit Wochenstunden durch die Zahl der Arbeitstage der
    Planung, höchstens den Arbeitsstunden je Tag, an jedem Arbeitstag der Planung gleich."""
    from .sollzeit import soll_fuer_personen
    werte = soll_fuer_personen(db, {p.id for p in personen if p is not None}, start, end)
    return {(eid, tag): stunden for eid, tage in werte.items() for tag, stunden in tage.items()}


class _SollAbschnitte:
    """Seit 1.9.211: die Sollzeit für den Planungsvorschlag in Abschnitten von 62 Tagen nachgeladen -- er schaut bis zu zwei Jahre voraus, endet
    aber meist nach wenigen Wochen. get() wie bei einem dict."""

    def __init__(self, db: Session, personen, start: date):
        self.db, self.personen, self.bis, self.werte = db, personen, start - timedelta(days=1), {}

    def get(self, schluessel: tuple[int, date], vorgabe=Decimal("0")) -> Decimal:
        while schluessel[1] > self.bis:
            von = self.bis + timedelta(days=1)
            self.bis = von + timedelta(days=61)
            self.werte.update(_soll_je_tag(self.db, self.personen, von, self.bis))
        return self.werte.get(schluessel, vorgabe)


def _netto(soll: Decimal, travel_hours: Decimal) -> Decimal:
    """Kapazität einer Person an einem Tag: die Sollzeit abzüglich der Anfahrt, nie unter 0; ohne Sollzeit 0 (auch ohne Anfahrt)."""
    return max(Decimal("0"), soll - travel_hours) if soll > 0 else Decimal("0")


def _team_members_from_master(team: Team, visible_employee_ids: set[int] | None = None) -> list[Employee]:
    return [x.employee for x in team.employees if x.employee and x.employee.active and (visible_employee_ids is None or x.employee_id in visible_employee_ids)]


def _besetzung(slot: PlanningSlot, visible_employee_ids: set[int] | None = None) -> list[Employee]:
    """Seit 1.9.233 (Stufe 6, R3a, Punkt 2): die Personen des Einsatzes, die zählen -- aktiv und (wenn angegeben) auf der Plantafel sichtbar, in der
    Reihenfolge der Besetzung. Bis 1.9.232 _team_members_from_assignment(): der Schnappschuss der Kolonne an der Arbeitsvorbereitung."""
    return [x.employee for x in slot.besetzung if x.employee and x.employee.active and (visible_employee_ids is None or x.employee_id in visible_employee_ids)]


def _rolle_des_geraets(slot: PlanningSlot, resource_id: int) -> str | None:
    """Die Rolle des Geräts in der Kolonne des Einsatzes (Schnappschuss an der AV), sonst keine -- nur zur Anzeige (seit 1.9.234)."""
    if slot.team_assignment is None:
        return None
    return next((x.role_snapshot for x in slot.team_assignment.resources if x.resource_id == resource_id), None)


def _rolle_in_kolonne(slot: PlanningSlot, employee_id: int) -> str | None:
    """Die Rolle der Person in der Kolonne des Einsatzes (Schnappschuss an der AV), sonst keine -- nur zur Anzeige."""
    if slot.team_assignment is None:
        return None
    return next((x.role_snapshot for x in slot.team_assignment.employees if x.employee_id == employee_id), None)


class BesetzungUngueltig(ValueError):
    """Seit 1.9.233: eine Besetzung, die nicht geht (unbekannte oder inaktive Person, ohne Kolonne ohne Personen) -- 422."""


def _kolonne_schlaegt_vor(db: Session, team_id: int) -> list[int]:
    """Die Personen, die eine Kolonne heute vorschlägt: ihre aktiven Mitglieder aus den Stammdaten, in ihrer Reihenfolge (seit 1.9.233; bis 1.9.232
    der Schnappschuss beim ersten Zuweisen an der AV, für jeden späteren Einsatz derselbe). Seit 1.9.259 (Stufe 6, R5a, Punkt 0) ohne die mit dem Kennzeichen
    „nicht zeigen“ (1.9.253–1.9.258 schlug sie auch diese vor); wer sie trotzdem im Einsatz will, wählt sie einzeln."""
    team = _load_team(db, team_id)
    if team is None or not team.active:
        raise ValueError("Kolonne / Team wurde nicht gefunden oder ist inaktiv.")
    mitglieder = [m.employee for m in team.employees if m.employee and m.employee.active]
    kennzeichen = _plantafel_map(db, mitglieder)
    return [e.id for e in mitglieder if kennzeichen[e.id] != "nicht_zeigen"]


def _besetzung_pruefen(db: Session, employee_ids) -> list[int]:
    """Gewählte Personen: jede bekannt und aktiv, jede einmal (Reihenfolge der Anfrage). Unbekannt oder inaktiv: BesetzungUngueltig."""
    ids: list[int] = []
    for eid in employee_ids:
        if eid not in ids:
            ids.append(int(eid))
    if ids:
        personen = {e.id: e for e in db.scalars(select(Employee).where(Employee.id.in_(ids)))}
        fehlt = [i for i in ids if i not in personen]
        if fehlt:
            raise BesetzungUngueltig(f"Mitarbeiter #{fehlt[0]} wurde nicht gefunden.")
        inaktiv = [personen[i] for i in ids if not personen[i].active]
        if inaktiv:
            raise BesetzungUngueltig(f"{_employee_name(inaktiv[0])} ist nicht aktiv und kann nicht eingeplant werden.")
    return ids


def _personen_pruefen(db: Session, besetzung, start: date, ende: date) -> list[dict]:
    """Seit 1.9.260 (Stufe 6, R5a, Punkt 1): gewählte Personen mit ihren Tagen ([{employee_id, tage}], tage leer = alle Tage) -- jede bekannt und aktiv,
    jede einmal (die erste zählt), Tage wie bei den Geräten (_tage_pruefen()). employee_ids heißt dasselbe mit „alle Tage“ (_alle_tage())."""
    ergebnis: list[dict] = []
    for p in besetzung:
        eid = int(p["employee_id"])
        if any(x["employee_id"] == eid for x in ergebnis):
            continue
        ergebnis.append({"employee_id": eid, "tage": _tage_pruefen(p.get("tage"), start, ende, BesetzungUngueltig, "eine Person")})
    _besetzung_pruefen(db, [x["employee_id"] for x in ergebnis])
    return ergebnis


def _alle_tage(employee_ids) -> list[dict]:
    """Personen an allen Tagen des Einsatzes (employee_ids, Vorschlag der Kolonne)."""
    return [{"employee_id": eid, "tage": None} for eid in employee_ids]


def _besetzung_stand(slot: PlanningSlot) -> tuple:
    return tuple((x.employee_id, x.tage) for x in slot.besetzung)


def _besetzung_setzen(db: Session, slot: PlanningSlot, personen: list[dict]) -> bool:
    """Die Besetzung genau auf diese Personen setzen (Reihenfolge wie gegeben), seit 1.9.260 mit ihren Tagen ([{employee_id, tage}]); True, wenn sich
    etwas geändert hat. Wer bleibt, behält seine Zeile."""
    neu = tuple((p["employee_id"], _tage_schreiben(p["tage"])) for p in personen)
    if _besetzung_stand(slot) == neu:
        return False
    bleiben = {x.employee_id: x for x in slot.besetzung}
    zeilen = []
    for eid, tage in neu:
        row = bleiben.get(eid) or PlanningSlotEmployee(employee_id=eid)
        row.tage = tage
        zeilen.append(row)
    slot.besetzung = zeilen
    return True


# --- Tage je Zeile: Geräte seit 1.9.234 (Stufe 6, R3a, Punkt 3), Personen seit 1.9.260 (R5a, Punkt 1) ------------------------------------------

class GeraeteUngueltig(BesetzungUngueltig):
    """Seit 1.9.234: Geräte, die nicht gehen (unbekannt, inaktiv, Tag außerhalb des Einsatzes, leere Tagesliste) -- 422 wie die Besetzung."""


def _tage_lesen(row: PlanningSlotResource | PlanningSlotEmployee) -> list[date] | None:
    """Die einzelnen Tage eines Geräts bzw. (seit 1.9.260) einer Person am Einsatz, None = alle Tage."""
    return [date.fromisoformat(x) for x in json.loads(row.tage)] if row.tage else None


def _tage_schreiben(tage: list[date] | None) -> str | None:
    return json.dumps(sorted({t.isoformat() for t in tage})) if tage is not None else None


def _tage_der_zeile(slot: PlanningSlot, row: PlanningSlotResource | PlanningSlotEmployee) -> set[date]:
    """An welchen Tagen das Gerät bzw. die Person am Einsatz ist: die einzelnen Tage oder alle Tage des Einsatzes. Seit 1.9.260 eine Funktion für beide
    (bis 1.9.259 _geraet_tage(), nur Geräte -- eine Person stand immer an allen Tagen)."""
    tage = _tage_lesen(row)
    return set(tage) if tage is not None else set(_date_range(slot.start_date, slot.end_date))


def _tage_pruefen(tage, start: date, ende: date, fehler, wer: str) -> list[date] | None:
    """Einzelne Tage einer Person oder eines Geräts: nur innerhalb des Einsatzes, eine leere Liste geht nicht (fehler, 422). Seit 1.9.260 die Normalform auf
    dem Server: stehen sie an allen Tagen des Einsatzes, heißt das „alle Tage“ (None) -- bis 1.9.259 speicherte das nur die Oberfläche so."""
    if tage is None:
        return None
    tage = sorted({t if isinstance(t, date) else date.fromisoformat(str(t)) for t in tage})
    if not tage:
        raise fehler(f"Für {wer} an einzelnen Tagen bitte mindestens einen Tag wählen.")
    draussen = [t for t in tage if t < start or t > ende]
    if draussen:
        raise fehler(f"Der Tag {draussen[0]:%d.%m.%Y} liegt außerhalb des Einsatzes.")
    return None if len(tage) == (ende - start).days + 1 else tage


def _alle_tage_festschreiben(slot: PlanningSlot, zeilen: list) -> None:
    """Seit 1.9.260 (Stufe 6, R5a, Punkt 1, „die Falle“): wer an allen Tagen steht, steht danach an genau den Tagen, die der Einsatz jetzt hat. Vor einer
    Änderung des Zeitraums, die niemanden mitnehmen soll (update_slot(alle_tage_mitnehmen=False), für die Tag-Aktionen ab R5b) -- „alle Tage“ heißt „alle
    Tage des Einsatzes“, ohne das stünde bei jeder Verlängerung die ganze Kolonne auch am neuen Tag."""
    tage = list(_date_range(slot.start_date, slot.end_date))
    for row in zeilen:
        if row.tage is None:
            row.tage = _tage_schreiben(tage)


def _kolonne_schlaegt_geraete_vor(db: Session, team_id: int) -> list[dict]:
    """Die Geräte, die eine Kolonne vorschlägt: ihre aktiven Geräte aus den Stammdaten (jede Rolle), für alle Tage -- wie bis 1.9.233 der Schnappschuss."""
    team = _load_team(db, team_id)
    if team is None:
        return []
    return [{"resource_id": r.resource_id, "tage": None} for r in team.resources if r.resource and r.resource.active]


def _geraete_pruefen(db: Session, geraete, start: date, ende: date) -> list[dict]:
    """Gewählte Geräte: jedes bekannt und aktiv, jedes einmal (das erste zählt); Tage nur innerhalb des Einsatzes, eine leere Liste geht nicht."""
    ergebnis: list[dict] = []
    for g in geraete:
        rid = int(g["resource_id"])
        if any(x["resource_id"] == rid for x in ergebnis):
            continue
        ergebnis.append({"resource_id": rid, "tage": _tage_pruefen(g.get("tage"), start, ende, GeraeteUngueltig, "ein Gerät")})
    if ergebnis:
        geraete_db = {r.id: r for r in db.scalars(select(OperationalResource).where(OperationalResource.id.in_([x["resource_id"] for x in ergebnis])))}
        for x in ergebnis:
            r = geraete_db.get(x["resource_id"])
            if r is None:
                raise GeraeteUngueltig(f"Gerät #{x['resource_id']} wurde nicht gefunden.")
            if not r.active:
                raise GeraeteUngueltig(f"{r.name} ist nicht aktiv und kann nicht eingeplant werden.")
    return ergebnis


def _geraete_setzen(slot: PlanningSlot, geraete: list[dict]) -> None:
    """Die Geräte genau so setzen; wer bleibt, behält seine Zeile (die Tage werden übernommen)."""
    bleiben = {x.resource_id: x for x in slot.geraete}
    neu = []
    for g in geraete:
        row = bleiben.get(g["resource_id"]) or PlanningSlotResource(resource_id=g["resource_id"])
        row.tage = _tage_schreiben(g["tage"])
        neu.append(row)
    slot.geraete = neu


def _tage_mitnehmen(slot: PlanningSlot, alt_start: date, alt_ende: date, attr: str = "geraete") -> None:
    """Der Einsatz hat einen neuen Zeitraum: um gleich viele Tage verschoben (gleiche Dauer) -> einzelne Tage wandern mit; sonst bleiben nur die Tage
    im neuen Zeitraum, ein Gerät ohne verbleibenden Tag fällt weg. Seit 1.9.260 ebenso die Personen (attr „besetzung“), und in der Normalform: stehen die
    Tage danach an allen Tagen des Einsatzes, heißt das „alle Tage“. Wer an allen Tagen steht, kommt mit (die Falle: _alle_tage_festschreiben())."""
    versatz = slot.start_date - alt_start
    gleich = (slot.end_date - slot.start_date) == (alt_ende - alt_start)
    alle = (slot.end_date - slot.start_date).days + 1
    zeilen = getattr(slot, attr)
    bleiben = []
    for row in zeilen:
        tage = _tage_lesen(row)
        if tage is not None:
            tage = [t + versatz for t in tage] if gleich else [t for t in tage if slot.start_date <= t <= slot.end_date]
            if not tage:
                continue
            row.tage = None if len(set(tage)) == alle else _tage_schreiben(tage)
        bleiben.append(row)
    if len(bleiben) != len(zeilen):
        setattr(slot, attr, bleiben)


def _tage_aendern(db: Session, slot: PlanningSlot, *, dazu: list[dict], weg: list[dict]) -> None:
    """Seit 1.9.267 (Stufe 6, R5b, Tag-Aktionen): einer Person ({employee_id, tage}) oder einem Gerät ({resource_id, tage}) Tage geben (dazu) oder nehmen
    (weg, tage None = alle). Ihre übrigen Tage bleiben, ebenso jede andere Zeile -- nur die genannte ändert sich. Wer keinen Tag mehr hat, fällt aus dem
    Einsatz; wer danach an allen Tagen steht, heißt „alle Tage“ (Normalform). Neue Tage liegen im Zeitraum (der Aufrufer verlängert vorher, mit der Falle:
    update_slot(alle_tage_mitnehmen=False))."""
    alle = set(_date_range(slot.start_date, slot.end_date))

    def _zeilen(eintrag):
        if eintrag.get("employee_id") is not None:
            return "besetzung", "employee_id", int(eintrag["employee_id"])
        return "geraete", "resource_id", int(eintrag["resource_id"])

    for eintrag in dazu:
        attr, feld, wer = _zeilen(eintrag)
        tage = {t if isinstance(t, date) else date.fromisoformat(str(t)) for t in eintrag["tage"]}
        if not tage or not tage <= alle:
            raise BesetzungUngueltig("Der Tag liegt außerhalb des Einsatzes.")
        row = next((x for x in getattr(slot, attr) if getattr(x, feld) == wer), None)
        if row is None:
            if attr == "besetzung":
                _besetzung_pruefen(db, [wer])
                row = PlanningSlotEmployee(employee_id=wer)
            else:
                _geraete_pruefen(db, [{"resource_id": wer}], slot.start_date, slot.end_date)
                row = PlanningSlotResource(resource_id=wer)
            getattr(slot, attr).append(row)
            vorher: set[date] = set()
        else:
            vorher = _tage_der_zeile(slot, row)
        row.tage = _tage_schreiben(sorted(vorher | tage))
    for eintrag in weg:
        attr, feld, wer = _zeilen(eintrag)
        row = next((x for x in getattr(slot, attr) if getattr(x, feld) == wer), None)
        if row is None:
            raise BesetzungUngueltig(("Die Person" if attr == "besetzung" else "Das Gerät") + " steht nicht an diesem Einsatz.")
        tage = None if eintrag.get("tage") is None else {t if isinstance(t, date) else date.fromisoformat(str(t)) for t in eintrag["tage"]}
        bleibt = set() if tage is None else _tage_der_zeile(slot, row) - tage
        if bleibt:
            row.tage = _tage_schreiben(sorted(bleibt))
        else:
            setattr(slot, attr, [x for x in getattr(slot, attr) if x is not row])
    for row in (*slot.besetzung, *slot.geraete):  # Normalform: an allen Tagen heißt „alle Tage“
        if row.tage is not None and set(_tage_lesen(row)) == alle:
            row.tage = None


def _geraete_stand(slot: PlanningSlot) -> tuple:
    return tuple((x.resource_id, x.tage) for x in slot.geraete)


def _day_capacity(
    employees: list[Employee], day: date, settings: PlanningSettings, travel_hours: Decimal,
    holiday_dates: set[date], absences: dict[tuple[int, date], EmployeeAbsence], soll,
) -> tuple[Decimal, list[Employee], list[EmployeeAbsence]]:
    """Seit 1.9.211: je Person die Sollzeit des Tags (soll: (Person, Tag) -> Stunden, _soll_je_tag()) abzüglich der Anfahrt. Ohne Sollzeit an dem
    Tag ist die Person weder verfügbar noch abwesend (wie bis 1.9.210 an einem Tag, der kein Arbeitstag der Planung war); an einem Feiertag oder
    betriebsfreien Tag hat niemand Kapazität. Bis 1.9.210 entschieden die Arbeitstage der Planung, ob überhaupt gearbeitet wird."""
    if day in holiday_dates:
        return Decimal("0"), [], []
    available, absent = [], []
    total = Decimal("0")
    for emp in employees:
        stunden = soll.get((emp.id, day), Decimal("0"))
        if stunden <= 0:
            continue
        absence = absences.get((emp.id, day))
        if absence:
            absent.append(absence)
            continue
        available.append(emp)
        total += _netto(stunden, travel_hours)
    return round_hours(total), available, absent


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


def _load_slot(db: Session, slot_id: int, *, frisch: bool = False) -> PlanningSlot | None:
    """frisch (seit 1.8.96): schon geladene Objekte mit dem Stand aus der Datenbank überschreiben (nach einer Sperre)."""
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
            selectinload(PlanningSlot.besetzung).selectinload(PlanningSlotEmployee.employee),
            selectinload(PlanningSlot.geraete).selectinload(PlanningSlotResource.resource),
        )
        .where(PlanningSlot.id == slot_id)
        .execution_options(populate_existing=frisch)
    )


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
    return round_hours(total * Decimal(weights[slot.id]) / denom) if denom else Decimal("0")


def _remaining_order_hours(db: Session, prep: WorkPreparation) -> Decimal:
    order = load_order(db, prep.order_id)
    total = planned_hours(order) if order else Decimal("0")
    existing = db.scalars(
        select(PlanningSlot).options(selectinload(PlanningSlot.capacity)).where(PlanningSlot.preparation_id == prep.id)
    ).all()
    assigned = sum((_stored_slot_hours(x) or Decimal("0") for x in existing), Decimal("0"))
    return round_hours(max(Decimal("0"), total - assigned))


def create_slot(db: Session, **werte) -> PlanningSlot:
    """Seit 1.9.240: wird ein Einsatz abgelehnt (ValueError, auch nach dem Anlegen von Projekt und Auftrag einer Kranvermietung), bleibt nichts in der
    Sitzung zurück -- rollback, dann der Fehler. Die Regeln stehen in _create_slot()."""
    try:
        return _create_slot(db, **werte)
    except ValueError:
        db.rollback()
        raise


def _create_slot(
    db: Session, *, order_id: int | None, team_id: int | None, start_date: date, end_date: date,
    status: str = "vorlaeufig", notes: str | None = None, planned_hours: Decimal | None = None,
    travel_hours_per_employee_day: Decimal | None = None, trotzdem_planen: bool = False, employee_ids: list[int] | None = None,
    geraete: list[dict] | None = None, art: str = "baustelle", customer_id: int | None = None, property_id: int | None = None,
    confirm_property_customer: bool = False, titel: str | None = None, kran_termin_id: int | None = None, _pruefen: dict | None = None,
    besetzung: list[dict] | None = None, _offen: bool = False,
) -> PlanningSlot:
    """Seit 1.9.143: mit Warnungen (einsatz_konflikte()) nur mit trotzdem_planen, sonst PlanungsWarnung -- dann bleibt nichts zurück, auch keine neu
    angelegte Arbeitsvorbereitung oder Kolonnen-Zuweisung.
    Seit 1.9.233 (Stufe 6, R3a, Punkt 2) die Besetzung am Einsatz: mit Kolonne schlägt sie ihre heutigen aktiven Mitglieder vor (employee_ids nicht
    angegeben), mit employee_ids genau diese Personen; ohne Kolonne (team_id None) braucht es mindestens eine Person. Die Kolonnen-Zuweisung an der AV
    entsteht mit Kolonne weiter wie bisher (AV-Seite, Zugriff).
    Seit 1.9.234 (Punkt 3) die Geräte am Einsatz: ohne geraete schlägt die Kolonne ihre aktiven Geräte vor (alle Tage), ohne Kolonne keine; mit geraete
    ([{resource_id, tage}], tage leer = alle Tage) genau diese.
    Seit 1.9.240 (Stufe 6, R3b, Punkt 2) die Art: „baustelle“ an einem Auftrag (order_id) oder „kranvermietung“ -- an einem bestehenden Auftrag
    (order_id) oder mit Kunde (customer_id, Objekt wahlweise): dann entstehen wie beim Schnellauftrag Projekt und Auftrag „Kranvermietung nach Aufwand“,
    in derselben Transaktion wie der Einsatz (eine Warnung lässt nichts zurück). Eine Kranvermietung hat keine Kolonne, mindestens ein Gerät (den Kran)
    und Bediener als Besetzung, auch keine."""
    if end_date < start_date:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    if art not in EINSATZ_ARTEN:
        raise ValueError("Die Art eines Einsatzes ist „Baustelle“ oder „Kranvermietung“.")
    kran = art == "kranvermietung"
    if kran and team_id is not None:
        raise BesetzungUngueltig(KRAN_OHNE_KOLONNE)
    if kran and not geraete:
        raise GeraeteUngueltig(KRAN_OHNE_GERAET)
    if (order_id is None) == (customer_id is None) if kran else (order_id is None or customer_id is not None):
        raise ValueError("Eine Kranvermietung braucht einen Auftrag oder einen Kunden, nicht beides." if kran
                         else "Ein Einsatz auf der Baustelle braucht einen Auftrag.")
    if employee_ids is not None and besetzung is not None:  # seit 1.9.260
        raise BesetzungUngueltig("Die Besetzung bitte als employee_ids oder als besetzung schicken, nicht beides.")
    if team_id is None and not employee_ids and not besetzung and not geraete and not kran:  # seit 1.9.263 (Antwort 4) auch nur ein Gerät
        raise BesetzungUngueltig("Ohne Kolonne bitte mindestens eine Person oder ein Gerät wählen.")
    if status not in EINSATZ_STATUS:  # seit 1.9.235
        raise ValueError(EINSATZ_STATUS_FALSCH)
    if customer_id is not None:
        # wie der Schnellauftrag, ohne Commit: Personen und Geräte prüft _besetzung_pruefen()/_geraete_pruefen() unten, eine Warnung nimmt alles zurück
        from .quick_service_orders import auftrag_nach_aufwand
        _besetzung_pruefen(db, employee_ids or [])
        _personen_pruefen(db, besetzung or [], start_date, end_date)
        _geraete_pruefen(db, geraete, start_date, end_date)
        _, neu = auftrag_nach_aufwand(db, customer_id=customer_id, property_id=property_id, title=(titel or "").strip() or "Kranvermietung",
                                      position=KRANVERMIETUNG_POSITION, execution_start=start_date,
                                      confirm_property_customer=confirm_property_customer, commit=False)
        order_id = neu.id
    order = db.get(Order, order_id)
    if order is None:
        raise ValueError("Auftrag wurde nicht gefunden.")
    # Seit 1.9.124 (Stufe 5, R2, Punkt 1, Befund F5): kein neuer Einsatz für einen abgeschlossenen oder stornierten Auftrag (409); ein
    # bestehender lässt sich weiter verschieben und löschen.
    gesperrt = einsatz_gesperrt(order)
    if gesperrt:
        raise AuftragGeschlossen(gesperrt)
    # seit 1.9.260 mit den Tagen je Person: employee_ids und der Vorschlag der Kolonne heißen alle Tage, besetzung nennt sie einzeln
    personen = (_alle_tage(_besetzung_pruefen(db, employee_ids)) if employee_ids is not None
                else _personen_pruefen(db, besetzung, start_date, end_date) if besetzung is not None
                else _alle_tage(_kolonne_schlaegt_vor(db, team_id)) if team_id is not None else [])
    prep = ensure_preparation(db, order_id, festschreiben=False)
    assignment = ensure_team_assignment(db, prep, team_id) if team_id is not None else None
    settings = load_planning_settings(db)
    travel = _d(travel_hours_per_employee_day if travel_hours_per_employee_day is not None else settings.default_travel_hours_per_employee_day)
    if travel >= _d(settings.daily_work_hours):
        raise ValueError("Anfahrtszeit muss kleiner als die tägliche Arbeitszeit sein.")
    slot = PlanningSlot(
        preparation_id=prep.id, team_assignment_id=assignment.id if assignment is not None else None, start_date=start_date,
        end_date=end_date, status=status, notes=notes, art=art,
    )
    slot.besetzung = [PlanningSlotEmployee(employee_id=p["employee_id"], tage=_tage_schreiben(p["tage"])) for p in personen]
    _geraete_setzen(slot, _geraete_pruefen(db, geraete, start_date, end_date) if geraete is not None
                    else _kolonne_schlaegt_geraete_vor(db, team_id) if team_id is not None else [])
    _raender_kuerzen(slot)  # seit 1.9.263: am Rand kein Tag ohne jemanden
    db.add(slot)
    db.flush()
    hours = _remaining_order_hours(db, prep) if planned_hours is None else _d(planned_hours)
    db.add(PlanningSlotCapacity(slot_id=slot.id, planned_hours=hours, travel_hours_per_employee_day=travel))
    if kran_termin_id is not None:
        # seit 1.9.241: der übernommene Termin am Kran gehört ab jetzt zum Einsatz (vor der Prüfung -- sonst warnte er gegen sich selbst)
        termin = db.get(CalendarEvent, kran_termin_id)
        termin.planning_slot_id, termin.external_source = slot.id, "erp"
    db.flush()
    if _offen:  # seit 1.9.267 (Stufe 6, R5b): eine Tag-Aktion schließt selbst ab -- Warnungen, Kran-Kalender, Commit (app/tag_aktionen.py)
        return _load_slot(db, slot.id, frisch=True)
    if _pruefen is not None:  # seit 1.9.248: nur prüfen (einsatz_pruefen()), nichts bleibt
        return _nur_pruefen(db, slot.id, **_pruefen)
    if not trotzdem_planen:
        _warnungen_pruefen(db, slot.id)
    zu_senden = kran_kalender.abgleichen(db, _load_slot(db, slot.id, frisch=True))  # seit 1.9.241: Termine im Kalender des Krans
    db.commit()
    kran_kalender.senden(db, zu_senden)
    return _load_slot(db, slot.id)


_SLOT_FIELDS = frozenset({"team_id", "start_date", "end_date", "status", "notes", "planned_hours",
                          "travel_hours_per_employee_day", "employee_ids", "geraete", "besetzung",
                          "dazu", "weg"})  # seit 1.9.267 nur für die Tag-Aktionen (app/tag_aktionen.py), nicht an der API (PUT)


def update_slot(db: Session, slot_id: int, *, trotzdem_planen: bool = False, alle_tage_mitnehmen: bool = True, wenn_leer: str | None = None,
                **changes) -> PlanningSlot | None:
    """Seit 1.9.240: wird die Änderung abgelehnt (ValueError, auch nach einem Teil der Änderung am Objekt), nimmt die Sitzung alles zurück --
    rollback (gibt auch die Sperre frei), dann der Fehler. Die Regeln stehen in _update_slot(). Seit 1.9.263 None, wenn der Einsatz mit
    wenn_leer="loeschen" gelöscht wurde; EinsatzWirdLeer nimmt ebenso alles zurück."""
    try:
        return _update_slot(db, slot_id, trotzdem_planen=trotzdem_planen, alle_tage_mitnehmen=alle_tage_mitnehmen, wenn_leer=wenn_leer, **changes)
    except (ValueError, EinsatzWirdLeer):
        db.rollback()
        raise


def _update_slot(db: Session, slot_id: int, *, trotzdem_planen: bool = False, alle_tage_mitnehmen: bool = True, wenn_leer: str | None = None,
                 _pruefen: dict | None = None, _offen: bool = False, **changes) -> PlanningSlot | dict | None:
    """Seit 1.8.96 Teil-Update (Regel 22): ändert nur die übergebenen Felder (Verschieben auf der Plantafel übergibt Team, Beginn
    und Ende). Ende vor Beginn, Anfahrtszeit und Team prüft sie vor jeder Änderung auf gespeichertem Stand + übergebenen Werten,
    unter der Sperre der Arbeitsvorbereitung: zwei gleichzeitige Änderungen (Beginn hier, Ende dort) prüften sonst je gegen den Stand vor der anderen.
    Seit 1.9.145 schreibt ein Einsatz nicht mehr in die Arbeitsvorbereitung (F12, app/work_preparation.py::einsatz_zeitraum()).
    team_id, planned_hours, travel_hours_per_employee_day: None heißt wie bisher unverändert (die API lehnt null ab).
    Seit 1.9.143: ändert sich Kolonne oder Zeitraum, fragen Warnungen zurück (PlanungsWarnung, nichts gespeichert), bis trotzdem_planen kommt; wer
    nur Notiz, Status oder Stunden ändert, wird nicht erneut gefragt -- die Konflikte stehen in der Antwort.
    Seit 1.9.233 (Stufe 6, R3a, Punkt 2): team_id None heißt „ohne Kolonne“ (die Personen bleiben); eine andere Kolonne setzt deren heutige aktive
    Mitglieder als Besetzung (auch beim Ziehen in ihre Zeile), employee_ids setzt die Besetzung genau so. Eine geänderte Besetzung fragt wie Kolonne
    und Zeitraum zurück. Ohne Kolonne bleibt mindestens eine Person.
    Seit 1.9.234 (Punkt 3): geraete setzt die Geräte genau so; eine andere Kolonne ohne geraete setzt ihre Geräte, „ohne Kolonne“ lässt sie. Ein neuer
    Zeitraum nimmt einzelne Tage mit (gleiche Dauer: verschoben, sonst nur die Tage im neuen Zeitraum; ein Gerät ohne Tag fällt weg). Geänderte Geräte
    fragen zurück wie Besetzung, Kolonne und Zeitraum.
    Seit 1.9.260 (Stufe 6, R5a, Punkt 1): besetzung ([{employee_id, tage}]) setzt die Besetzung mit den Tagen je Person, employee_ids heißt alle Tage (beides
    zugleich 422). Ein neuer Zeitraum nimmt auch die einzelnen Tage der Personen mit wie die der Geräte; wer an allen Tagen steht, steht danach an allen Tagen des
    neuen Zeitraums (Dialog, Ziehen des ganzen Einsatzes). alle_tage_mitnehmen=False (die Falle, für die Tag-Aktionen ab R5b): wer in dieser Änderung nicht
    gesetzt wird und an allen Tagen stand, steht danach an genau den bisherigen Tagen (_alle_tage_festschreiben()).
    Seit 1.9.263 (Punkt 4, der leere Tag): am Rand fällt jeder Tag ohne Person und Gerät weg (_raender_kuerzen()); in der Mitte bleibt der Einsatz einer.
    Nähme die Änderung dem Einsatz den letzten Tag mit jemandem, fragt sie zurück (EinsatzWirdLeer, nichts gespeichert): wenn_leer="loeschen" löscht ihn
    (Rückgabe None), "behalten" lässt ihn mit dem zuletzt geleerten Tag stehen („niemand“) -- werden mehrere Tage zugleich leer (Dialog), mit dem ersten. Ohne Kolonne darf er danach leer sein; eine Kranvermietung
    braucht ihr Gerät nur beim Anlegen (bis 1.9.262: ohne Kolonne immer eine Person, eine Kranvermietung immer ein Gerät -- je 422)."""
    unbekannt = set(changes) - _SLOT_FIELDS
    if unbekannt:
        raise TypeError("Unbekannte Felder: " + ", ".join(sorted(unbekannt)))
    if "status" in changes and changes["status"] not in EINSATZ_STATUS:  # seit 1.9.235
        raise ValueError(EINSATZ_STATUS_FALSCH)
    if wenn_leer is not None and wenn_leer not in WENN_LEER:  # seit 1.9.263
        raise ValueError("Ein leerer Einsatz wird gelöscht oder behalten.")
    prep_id = db.scalar(select(PlanningSlot.preparation_id).where(PlanningSlot.id == slot_id))
    if prep_id is None:
        raise ValueError("Planeinsatz wurde nicht gefunden.")
    db.execute(select(WorkPreparation.id).where(WorkPreparation.id == prep_id).with_for_update())
    slot = _load_slot(db, slot_id, frisch=True)  # nach der Sperre: der Stand nach einer gleichzeitigen Änderung
    if slot is None:
        raise ValueError("Planeinsatz wurde nicht gefunden.")
    vorher_team = slot.team_assignment.team_id if slot.team_assignment is not None else None
    vorher = (vorher_team, slot.start_date, slot.end_date, _besetzung_stand(slot), _geraete_stand(slot))
    alt_start, alt_ende = slot.start_date, slot.end_date
    besetzt_vorher = _besetzte_tage(slot)  # seit 1.9.263: wer stand vorher an welchem Tag (leer werden, zuerst geleerter Tag)
    start_date = changes.get("start_date", slot.start_date)
    end_date = changes.get("end_date", slot.end_date)
    if end_date < start_date:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    settings = load_planning_settings(db)
    travel_hours = changes.get("travel_hours_per_employee_day")
    if travel_hours is not None and _d(travel_hours) >= _d(settings.daily_work_hours):
        raise ValueError("Anfahrtszeit muss kleiner als die tägliche Arbeitszeit sein.")
    neues_team = changes.get("team_id", vorher_team)
    kran = slot.art == "kranvermietung"  # seit 1.9.240: keine Kolonne, mindestens ein Gerät, Bediener auch keine
    if kran and neues_team is not None:
        raise BesetzungUngueltig(KRAN_OHNE_KOLONNE)
    if changes.get("employee_ids") is not None and changes.get("besetzung") is not None:  # seit 1.9.260
        raise BesetzungUngueltig("Die Besetzung bitte als employee_ids oder als besetzung schicken, nicht beides.")
    personen = (_alle_tage(_besetzung_pruefen(db, changes["employee_ids"])) if changes.get("employee_ids") is not None
                else _personen_pruefen(db, changes["besetzung"], start_date, end_date) if changes.get("besetzung") is not None else None)
    if not alle_tage_mitnehmen and (start_date, end_date) != (alt_start, alt_ende):  # seit 1.9.260: die Falle
        if personen is None:
            _alle_tage_festschreiben(slot, slot.besetzung)
        if changes.get("geraete") is None:
            _alle_tage_festschreiben(slot, slot.geraete)
    if neues_team != vorher_team:
        if neues_team is None:
            slot.team_assignment_id, slot.team_assignment = None, None
        else:
            assignment = ensure_team_assignment(db, slot.preparation, neues_team)
            slot.team_assignment_id, slot.team_assignment = assignment.id, assignment
            if personen is None:
                personen = _alle_tage(_kolonne_schlaegt_vor(db, neues_team))
    if personen is not None:
        _besetzung_setzen(db, slot, personen)
    slot.start_date = start_date
    slot.end_date = end_date
    if personen is None and (start_date, end_date) != (alt_start, alt_ende):  # seit 1.9.260 auch die Tage der Personen
        _tage_mitnehmen(slot, alt_start, alt_ende, "besetzung")
    if changes.get("geraete") is not None:
        _geraete_setzen(slot, _geraete_pruefen(db, changes["geraete"], start_date, end_date))
    elif neues_team != vorher_team and neues_team is not None:
        _geraete_setzen(slot, _kolonne_schlaegt_geraete_vor(db, neues_team))
    elif (start_date, end_date) != (alt_start, alt_ende):
        _tage_mitnehmen(slot, alt_start, alt_ende)
    if changes.get("dazu") or changes.get("weg"):  # seit 1.9.267 (Stufe 6, R5b): Tag-Aktionen -- Tage einzelner Personen und Geräte
        _tage_aendern(db, slot, dazu=changes.get("dazu") or [], weg=changes.get("weg") or [])
    # seit 1.9.263 (Punkt 4): am Rand kein Tag ohne jemanden; wird der Einsatz leer, die Rückfrage (Antwort 3)
    leer = bool(besetzt_vorher) and not _besetzte_tage(slot)
    if leer:
        if _pruefen is None and wenn_leer is None:
            raise EinsatzWirdLeer(EINSATZ_LEER)
        if _pruefen is None and wenn_leer == "loeschen":
            kran_kalender.entfernen(db, slot.id)
            db.delete(slot)
            if _offen:  # seit 1.9.267: die Tag-Aktion committet selbst
                db.flush()
                return None
            db.commit()
            kran_kalender.senden(db, [])
            return None
        tag = min([t for t in besetzt_vorher if slot.start_date <= t <= slot.end_date] or [slot.start_date])
        alt_s, alt_e = slot.start_date, slot.end_date
        slot.start_date = slot.end_date = tag
        _tage_mitnehmen(slot, alt_s, alt_e, "besetzung")
        _tage_mitnehmen(slot, alt_s, alt_e)
    else:
        _raender_kuerzen(slot)
    start_date, end_date = slot.start_date, slot.end_date
    for key in ("status", "notes"):
        if key in changes:
            setattr(slot, key, changes[key])
    capacity = slot.capacity
    if capacity is None:
        capacity = PlanningSlotCapacity(slot_id=slot.id, planned_hours=_infer_slot_hours(db, slot))
        db.add(capacity)
        slot.capacity = capacity
    if changes.get("planned_hours") is not None:
        capacity.planned_hours = _d(changes["planned_hours"])
    if travel_hours is not None:
        capacity.travel_hours_per_employee_day = _d(travel_hours)
    elif capacity.travel_hours_per_employee_day is None:
        capacity.travel_hours_per_employee_day = settings.default_travel_hours_per_employee_day
    db.flush()
    if _offen:  # seit 1.9.267 (Stufe 6, R5b): die Tag-Aktion schließt selbst ab -- Warnungen, Kran-Kalender, Commit (app/tag_aktionen.py)
        return _load_slot(db, slot.id, frisch=True)
    if _pruefen is not None:  # seit 1.9.248: nur prüfen (einsatz_pruefen()) -- alle Warnungen, auch ohne Änderung; nichts bleibt
        return {**_nur_pruefen(db, slot.id, **_pruefen), "leer": leer}  # seit 1.9.263: würde der Einsatz leer (Rückfrage beim Speichern)
    if not trotzdem_planen and (neues_team, start_date, end_date, _besetzung_stand(slot), _geraete_stand(slot)) != vorher:
        _warnungen_pruefen(db, slot.id)
    zu_senden = kran_kalender.abgleichen(db, _load_slot(db, slot.id, frisch=True))  # seit 1.9.241
    db.commit()
    kran_kalender.senden(db, zu_senden)
    return _load_slot(db, slot.id)


# --- seit 1.9.248 (Stufe 6, R4, Punkt 4): der Einsatz-Dialog prüft, bevor gespeichert wird ---------------------------------------------------

def einsatz_pruefen(db: Session, slot_id: int | None = None, *, mit_art: bool = False, weitere_personen=(), weitere_geraete=(), **werte) -> dict:
    """Rechnet einen Einsatz wie beim Speichern (dieselben Regeln, dieselbe Prüfung der Warnungen), schreibt nichts: nach dem Flush die Warnungen und
    Hinweise (einsatz_konflikte()), die Kapazität mit ihrer Rechnung, der Zustand je Person und je Gerät -- dann rollback. Ohne slot_id wie das Anlegen
    (create_slot()), sonst wie das Ändern (update_slot(), werte = die Änderungen). mit_art: die Art einer Abwesenheit darf im Text stehen (Admin und
    Büro – Finanzen, der Router entscheidet). weitere_personen/weitere_geraete: dazu der Zustand dieser IDs („+ Person“, „+ Gerät“ im Dialog)."""
    pruefen = {"mit_art": mit_art, "weitere_personen": [int(x) for x in weitere_personen], "weitere_geraete": [int(x) for x in weitere_geraete]}
    werte.pop("trotzdem_planen", None)
    try:
        if slot_id is None:
            return _create_slot(db, trotzdem_planen=True, _pruefen=pruefen, **werte)
        return _update_slot(db, slot_id, trotzdem_planen=True, _pruefen=pruefen, **werte)
    except Exception:
        db.rollback()
        raise


def _nur_pruefen(db: Session, slot_id: int, *, mit_art: bool, weitere_personen: list[int], weitere_geraete: list[int]) -> dict:
    slot = _load_slot(db, slot_id, frisch=True)
    konflikte = einsatz_konflikte(db, slot)
    andere = [s for s in db.scalars(_einsatz_abfrage().where(PlanningSlot.id != slot.id, PlanningSlot.start_date <= slot.end_date,
                                                            PlanningSlot.end_date >= slot.start_date)).all() if not geschlossen(s.preparation.order)]
    ergebnis = {"warnungen": konflikte["warnungen"], "hinweise": konflikte["hinweise"], "kapazitaet": _kapazitaet_rechnung(db, slot),
                "personen": _personen_zustand(db, slot, andere, weitere_personen, mit_art), "geraete": _geraete_zustand(db, slot, andere, weitere_geraete)}
    db.rollback()
    return ergebnis


def _spanne(von: date, bis: date) -> str:
    """„03.–05.11.“, ein Tag „05.11.“, über den Monat „30.10.–04.11.“ -- wie die Tafel."""
    if von == bis:
        return f"{von:%d.%m.}"
    return f"{von:%d.}–{bis:%d.%m.}" if (von.year, von.month) == (bis.year, bis.month) else f"{von:%d.%m.}–{bis:%d.%m.}"


def _folgen_der_tage(tage) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for t in sorted(tage):
        if out and t == out[-1][1] + timedelta(days=1):
            out[-1] = (out[-1][0], t)
        else:
            out.append((t, t))
    return out


def _kapazitaet_rechnung(db: Session, slot: PlanningSlot) -> dict:
    """Die Kapazität des Einsatzes aus der Sollzeit der Besetzung an den Arbeitstagen minus Anfahrt (dieselbe Rechnung wie die Konflikte, 1.9.211/1.9.233),
    mit ihrer Rechnung als Text: gleich je Person und Tag „2 Personen × 3 Arbeitstage × 7,50 h = 45,00 h“, sonst je Person. Dazu der Rest laut Kalkulation
    (Soll des Auftrags minus die Stunden der anderen Einsätze des Auftrags)."""
    settings = load_planning_settings(db)
    feiertage = set(_combined_holiday_map(db, slot.start_date, slot.end_date)[0])
    tage = [t for t in _date_range(slot.start_date, slot.end_date) if _is_workday(t, settings, feiertage)]
    sichtbar = planning_visible_employee_ids(db)
    personen = [x.employee for x in slot.besetzung if x.employee is not None and x.employee_id in sichtbar]
    ids = {p.id for p in personen}
    abwesend = _abwesend_map(db, _absence_rows(db, slot.start_date, slot.end_date, ids), personen, slot.start_date, slot.end_date) if ids else {}
    soll = _soll_je_tag(db, personen, slot.start_date, slot.end_date) if ids else {}
    anfahrt = _slot_travel(slot, settings)
    tage_je = _tage_je_person(slot)  # seit 1.9.261: je Person ihre Arbeitstage am Einsatz
    je_person = [(p, [n for t in tage if t in tage_je[p.id] and not abwesend.get((p.id, t)) and (n := _netto(soll.get((p.id, t), Decimal("0")), anfahrt)) > 0])
                 for p in personen]
    summe = sum((sum(w, Decimal("0")) for _, w in je_person), Decimal("0"))
    alle = [w for _, ws in je_person for w in ws]
    if not je_person:
        text = f"niemand eingeplant = {stunden_text(Decimal('0'))}"
    elif alle and len(set(alle)) == 1 and all(len(ws) == len(tage) for _, ws in je_person):
        n, m = len(je_person), len(tage)
        text = f"{n} {'Person' if n == 1 else 'Personen'} × {m} {'Arbeitstag' if m == 1 else 'Arbeitstage'} × {stunden_text(alle[0])} = {stunden_text(summe)}"
    else:
        teile = []
        for p, ws in je_person:
            name = (p.first_name or _employee_name(p)).strip()
            teile.append(f"{name} {len(ws)} × {stunden_text(ws[0])}" if ws and len(set(ws)) == 1 else f"{name} {stunden_text(sum(ws, Decimal('0')))}")
        text = " + ".join(teile) + f" = {stunden_text(summe)}"
    if anfahrt > 0:
        text += f" (Sollzeit je Tag − {stunden_text(anfahrt)} Anfahrt)"
    order = slot.preparation.order
    soll_auftrag = planned_hours(order)
    andere = sum((_stored_slot_hours(x) or Decimal("0") for x in db.scalars(select(PlanningSlot).options(selectinload(PlanningSlot.capacity)).where(
        PlanningSlot.preparation_id == slot.preparation_id, PlanningSlot.id != slot.id))), Decimal("0"))
    rest = round_hours(max(Decimal("0"), soll_auftrag - andere)) if soll_auftrag > 0 else None
    return {"summe": round_hours(summe), "text": text, "rest": rest, "stunden": round_hours(_infer_slot_hours(db, slot))}


def _personen_zustand(db: Session, slot: PlanningSlot, andere: list[PlanningSlot], weitere: list[int], mit_art: bool) -> list[dict]:
    """Je Person der Besetzung, der Kolonne (ihr Vorschlag) und „+ Person“: frei, anderer Einsatz im Zeitraum („auch bei …“ für eine gewählte -- eine Warnung),
    abwesend (genehmigt oder Freistellung -- die Art nur mit mit_art), Antrag offen."""
    gewaehlt = [x.employee_id for x in slot.besetzung]
    vorschlag = _kolonne_schlaegt_vor(db, slot.team_assignment.team_id) if slot.team_assignment is not None and slot.team_assignment.team_id else []
    ids = list(dict.fromkeys([*gewaehlt, *vorschlag, *weitere]))
    sichtbar = planning_visible_employee_ids(db)
    personen = {p.id: p for p in db.scalars(select(Employee).where(Employee.id.in_(ids)))} if ids else {}
    ids = [i for i in ids if i in personen and (i in sichtbar or i in gewaehlt)]
    von, bis = slot.start_date, slot.end_date
    abwesend = _abwesend_map(db, _absence_rows(db, von, bis, set(ids)), list(personen.values()), von, bis) if ids else {}
    antraege = _offene_antraege(db, von, bis, set(ids))
    out = []
    alle_tage = set(_date_range(von, bis))
    tage_je = _tage_je_person(slot)
    for i in ids:
        teile, stufe = [], "frei"
        meine = tage_je.get(i, alle_tage)  # seit 1.9.261: eine gewählte Person an ihren Tagen, sonst an allen Tagen des Einsatzes
        for o in andere:
            zeile = next((x for x in o.besetzung if x.employee_id == i), None)
            gemeinsam = meine & _tage_der_zeile(o, zeile) if zeile is not None else set()
            if gemeinsam:
                sp = ", ".join(_spanne(a, b) for a, b in _folgen_der_tage(gemeinsam))  # seit 1.9.261 die gemeinsamen Tage (bis 1.9.260 die Überschneidung)
                if i in gewaehlt:
                    teile.append(f"auch bei {o.preparation.order.project.project_number} · {sp}")
                    stufe = "doppelt"
                else:
                    teile.append(f"Kranvermietung {sp}" if o.art == "kranvermietung" else f"bei {o.preparation.order.project.project_number} · {sp}")
                    stufe = stufe if stufe != "frei" else "belegt"
        tage_weg = sorted(t for (eid, t) in abwesend if eid == i and t in meine)
        for a, b in _folgen_der_tage(tage_weg):
            art = abwesend[(i, a)].kalendertag if isinstance(abwesend[(i, a)], Freistellung) else abwesend[(i, a)].absence_type
            teile.append(f"{art if mit_art and art else 'abwesend'} {_spanne(a, b)}")
            stufe = "abwesend" if stufe in ("frei", "belegt", "antrag") else stufe
        for a in antraege.get(i, []):
            if not any(a.start_date <= t <= a.end_date for t in meine):  # seit 1.9.261: nur ein Antrag an ihren Tagen
                continue
            teile.append(f"{a.absence_type + ' ' if mit_art and a.absence_type else ''}beantragt {_spanne(a.start_date, a.end_date)}")  # der ganze Antrag (Zeichnung)
            stufe = "antrag" if stufe in ("frei", "belegt") else stufe
        zeile = next((x for x in slot.besetzung if x.employee_id == i), None)
        tage = sorted(_tage_lesen(zeile)) if zeile is not None and zeile.tage else None
        out.append({"id": i, "name": _employee_name(personen[i]), "gewaehlt": i in gewaehlt, "vorschlag": i in vorschlag, "zustand": stufe,
                    "text": " · ".join(teile) or "frei",
                    # seit 1.9.260 die Tage je gewählter Person wie bei den Geräten
                    "tage": [t.isoformat() for t in tage] if tage else None, "tage_text": _tage_text(tage) if zeile is not None else ""})
    return out


def _tage_text(tage: list[date] | None) -> str:
    """„alle Tage“ oder „nur 03., 05.11.“ -- für Personen (seit 1.9.260) und Geräte (seit 1.9.248) dieselbe Schreibweise im Dialog."""
    if not tage:
        return "alle Tage"
    return "nur " + ", ".join(f"{t:%d.}" for t in tage[:-1]) + (", " if len(tage) > 1 else "") + f"{tage[-1]:%d.%m.}"


def _geraete_zustand(db: Session, slot: PlanningSlot, andere: list[PlanningSlot], weitere: list[int]) -> list[dict]:
    """Je Gerät des Einsatzes, der Kolonne und „+ Gerät“: seine Tage (alle oder einzelne), an diesen Tagen ein anderer Einsatz („vermietet …“ bei einer
    Kranvermietung), ein Termin in seinem Kalender, eine abgelaufene Prüffrist."""
    zeilen = {x.resource_id: x for x in slot.geraete}
    vorschlag = [g["resource_id"] for g in _kolonne_schlaegt_geraete_vor(db, slot.team_assignment.team_id)] \
        if slot.team_assignment is not None and slot.team_assignment.team_id else []
    ids = list(dict.fromkeys([*zeilen, *vorschlag, *weitere]))
    geraete = {r.id: r for r in db.scalars(select(OperationalResource).where(OperationalResource.id.in_(ids)))} if ids else {}
    ids = [i for i in ids if i in geraete]
    alle_tage = set(_date_range(slot.start_date, slot.end_date))
    pruefungen = _pruefungen(db, set(ids))
    termine = {}
    for t in geraete_termine(db, set(ids), slot.start_date, slot.end_date):
        termine.setdefault(t["resource_id"], []).append(t)
    out = []
    for i in ids:
        row = zeilen.get(i)
        meine = _tage_der_zeile(slot, row) if row is not None else alle_tage
        teile, stufe = [], "frei"
        for o in andere:
            for x in o.geraete:
                if x.resource_id != i:
                    continue
                for a, b in _folgen_der_tage(meine & _tage_der_zeile(o, x)):
                    teile.append(("vermietet " if o.art == "kranvermietung" else f"bei {o.preparation.order.project.project_number} · ") + _spanne(a, b))
                    stufe = "doppelt" if row is not None else "belegt"
        for t in termine.get(i, []):
            if any(t["von"] <= d <= t["bis"] for d in meine):
                teile.append(f"Termin {t['titel']} {_spanne(t['von'], t['bis'])}")
                stufe = "doppelt" if row is not None else ("belegt" if stufe == "frei" else stufe)
        for art, faellig in pruefungen.get(i, []):
            if any(d > faellig for d in meine):
                teile.append(f"{art} fällig seit {faellig:%d.%m.%Y}")
                stufe = "pruefung" if stufe in ("frei", "belegt") else stufe
        tage = sorted(_tage_lesen(row)) if row is not None and row.tage else None
        out.append({"id": i, "name": geraete[i].name, "gewaehlt": row is not None, "vorschlag": i in vorschlag,
                    "tage": [t.isoformat() for t in tage] if tage else None,
                    "tage_text": _tage_text(tage) if row is not None else "", "zustand": stufe, "text": " · ".join(teile)})
    return out


def delete_slot(db: Session, slot_id: int) -> int:
    slot = db.get(PlanningSlot, slot_id)
    if slot is None:
        raise ValueError("Planeinsatz wurde nicht gefunden.")
    prep_id = slot.preparation_id
    # Seit 1.8.96 zuerst die Sperre der Arbeitsvorbereitung wie update_slot() (dieselbe Reihenfolge: Vorbereitung, dann Einsatz)
    # -- sonst konnten Entfernen (Einsatz, dann Vorbereitung) und gleichzeitiges Verschieben desselben Einsatzes sich gegenseitig
    # blockieren (Deadlock unter PostgreSQL).
    db.execute(select(WorkPreparation.id).where(WorkPreparation.id == prep_id).with_for_update())
    kran_kalender.entfernen(db, slot_id)  # seit 1.9.241: seine Termine im Kalender des Krans fallen weg
    db.delete(slot)
    db.commit()
    kran_kalender.senden(db, [])
    return prep_id


def _tage_je_person(slot: PlanningSlot) -> dict[int, set[date]]:
    """Seit 1.9.261 (Stufe 6, R5a, Punkt 2): je Person der Besetzung ihre Tage am Einsatz."""
    return {x.employee_id: _tage_der_zeile(slot, x) for x in slot.besetzung}


def _besetzte_tage(slot: PlanningSlot) -> set[date]:
    """Seit 1.9.263 (Stufe 6, R5a, Punkt 4): die Tage, an denen jemand am Einsatz steht -- eine Person oder ein Gerät (Kalendertage)."""
    tage: set[date] = set()
    for x in (*slot.besetzung, *slot.geraete):
        tage |= _tage_der_zeile(slot, x)
    return tage


def _raender_kuerzen(slot: PlanningSlot) -> None:
    """Seit 1.9.263 (Antwort 3, der leere Tag): am Rand fällt jeder Tag weg, an dem niemand steht -- auch ein Wochenende; einzelne Tage bleiben, wer danach
    an allen Tagen steht, heißt „alle Tage“. Steht gar niemand am Einsatz, bleibt der Zeitraum (ein ganz leerer Einsatz zeigt „niemand“)."""
    tage = _besetzte_tage(slot)
    if not tage or (min(tage), max(tage)) == (slot.start_date, slot.end_date):
        return
    alt_start, alt_ende = slot.start_date, slot.end_date
    slot.start_date, slot.end_date = min(tage), max(tage)
    _tage_mitnehmen(slot, alt_start, alt_ende, "besetzung")
    _tage_mitnehmen(slot, alt_start, alt_ende)


def leere_tage(slot: PlanningSlot, arbeitstag) -> list[date]:
    """Seit 1.9.263: die Arbeitstage des Einsatzes, an denen niemand steht (in der Mitte: „niemand“). Ein Tag, der kein Arbeitstag ist, ist nie leer."""
    return [t for t in _date_range(slot.start_date, slot.end_date) if arbeitstag(t) and not _jemand_am(slot, t)]


def abschnitte(slot: PlanningSlot, arbeitstag) -> list[tuple[date, date]]:
    """Seit 1.9.263: die Stücke des Balkens -- der Einsatz ohne seine leeren Tage; ein Tag ohne Arbeit an einer Lücke gehört nicht dazu, ein Stück nur aus
    solchen Tagen fällt weg. Ein ganz leerer Einsatz ist ein Stück (er bleibt sichtbar, „niemand“)."""
    leer = set(leere_tage(slot, arbeitstag))
    if not _besetzte_tage(slot) or not leer:
        return [(slot.start_date, slot.end_date)]
    stuecke, lauf = [], []
    for t in _date_range(slot.start_date, slot.end_date):
        if t in leer:
            if lauf:
                stuecke.append(lauf)
            lauf = []
        else:
            lauf.append(t)
    if lauf:
        stuecke.append(lauf)
    out = []
    for s in stuecke:
        if s[0] - timedelta(days=1) in leer:
            while s and not arbeitstag(s[0]):
                s = s[1:]
        if s and s[-1] + timedelta(days=1) in leer:
            while s and not arbeitstag(s[-1]):
                s = s[:-1]
        if s:
            out.append((s[0], s[-1]))
    return out


def _jemand_am(slot: PlanningSlot, tag: date) -> bool:
    """Seit 1.9.261: steht an dem Tag jemand am Einsatz -- eine Person oder ein Gerät?"""
    return any(tag in _tage_der_zeile(slot, x) for x in (*slot.besetzung, *slot.geraete))


def _slot_members(slot: PlanningSlot, visible_employee_ids: set[int] | None = None) -> tuple[set[int], set[int]]:
    """Seit 1.9.233 die Personen aus der Besetzung des Einsatzes (bis 1.9.232 aus dem Schnappschuss der Kolonne), seit 1.9.234 die Geräte aus den
    Geräten des Einsatzes (bis 1.9.233 aus der Kolonne; ob sie sich an einem Tag treffen, prüft _conflicts())."""
    employees = {x.employee_id for x in slot.besetzung if visible_employee_ids is None or x.employee_id in visible_employee_ids}
    resources = {x.resource_id for x in slot.geraete}
    return employees, resources


def _slot_travel(slot: PlanningSlot, settings: PlanningSettings) -> Decimal:
    if slot.capacity and slot.capacity.travel_hours_per_employee_day is not None:
        return _d(slot.capacity.travel_hours_per_employee_day)
    return _d(settings.default_travel_hours_per_employee_day)


def _slot_distribution(
    db: Session, slot: PlanningSlot, settings: PlanningSettings, holiday_dates: set[date],
    absences: dict[tuple[int, date], EmployeeAbsence], visible_employee_ids: set[int] | None = None, soll=None,
) -> tuple[dict[date, dict], Decimal]:
    remaining = _infer_slot_hours(db, slot)
    travel = _slot_travel(slot, settings)
    employees = _besetzung(slot, visible_employee_ids)
    if soll is None:  # seit 1.9.211: ohne mitgegebene Sollzeit (einzelner Aufruf) für diesen Einsatz nachschlagen
        soll = _soll_je_tag(db, employees, slot.start_date, slot.end_date)
    tage_je = _tage_je_person(slot)  # seit 1.9.261: je Tag nur, wer an dem Tag am Einsatz steht
    distribution = {}
    for day in _date_range(slot.start_date, slot.end_date):
        capacity, available, absent = _day_capacity([e for e in employees if day in tage_je[e.id]], day, settings, travel, holiday_dates, absences, soll)
        load = min(remaining, capacity)
        remaining -= load
        distribution[day] = {
            "capacity": capacity, "planned": round_hours(load),
            "available_employee_ids": [e.id for e in available],
            "absent_employee_ids": [a.employee_id for a in absent],
        }
    return distribution, round_hours(max(Decimal("0"), remaining))


def slot_to_dict(slot: PlanningSlot, conflicts: list[dict] | None = None, db: Session | None = None, *, tafel: dict | None = None) -> dict:
    """tafel (seit 1.9.144, planning_board()): Einstellungen, sichtbare Mitarbeiter und Pausen schon geladen -- ohne Abfrage je Einsatz."""
    order = slot.preparation.order
    project = order.project
    prop = project.property
    address = ""
    if prop:
        address = ", ".join(x for x in [prop.street, f"{prop.postal_code or ''} {prop.city or ''}".strip()] if x)
    elif order.property_address:
        address = order.property_address.replace("\n", ", ")
    if tafel is not None:
        settings, visible_ids, pause = tafel["settings"], tafel["sichtbar"], tafel["pausen"].get(order.id)
    else:
        settings = load_planning_settings(db) if db is not None else None
        visible_ids = planning_visible_employee_ids(db) if db is not None else None
        pause = pause_begruendung(db, order) if db is not None else None
    travel = _slot_travel(slot, settings) if settings is not None else (_d(slot.capacity.travel_hours_per_employee_day) if slot.capacity else Decimal("0"))
    hours = _infer_slot_hours(db, slot) if db is not None else (_stored_slot_hours(slot) or Decimal("0"))
    # seit 1.9.263 (Stufe 6, R5a, Punkt 4): die leeren Tage („niemand“) und die Stücke des Balkens (Lücke in „Kolonnen“) -- nach den Arbeitstagen der Planung
    if tafel is not None and "feiertage" in tafel:
        feiertage = tafel["feiertage"]
    else:
        feiertage = set(_combined_holiday_map(db, slot.start_date, slot.end_date)[0]) if db is not None else set()
    arbeitstag = (lambda t: _is_workday(t, settings, feiertage)) if settings is not None else (lambda t: t.weekday() < 5)
    return {
        "id": slot.id, "preparation_id": slot.preparation_id, "order_id": order.id,
        "order_number": order.order_number, "project_id": project.id,
        # seit 1.9.124: Status des Auftrags -- die Plantafel zeigt „pausiert“ mit Begründung als Hinweis
        "order_status": status_wert(order.status), "order_status_label": status_name(order.status),
        "order_status_reason": pause,
        "project_number": project.project_number, "project_name": project.name,
        "customer_name": order.customer_name, "property_name": prop.name if prop else order.property_name,
        "property_address": address, "team_assignment_id": slot.team_assignment_id,
        # seit 1.9.233: ohne Kolonne beides leer (Zeile „Ohne Kolonne“)
        "team_id": slot.team_assignment.team_id if slot.team_assignment is not None else None,
        "team_name": slot.team_assignment.team_name_snapshot if slot.team_assignment is not None else None,
        "start_date": slot.start_date, "end_date": slot.end_date,
        "duration_days": (slot.end_date - slot.start_date).days + 1, "status": slot.status,
        "status_label": EINSATZ_STATUS.get(slot.status, slot.status),  # seit 1.9.235
        "art": slot.art, "art_label": EINSATZ_ARTEN.get(slot.art, slot.art),  # seit 1.9.240
        "notes": slot.notes, "planned_hours": hours,
        "travel_hours_per_employee_day": travel,
        # seit 1.9.233 die Besetzung des Einsatzes (Name live, Rolle aus der Kolonne, wenn die Person dort steht); bis 1.9.232 der Schnappschuss der Kolonne
        "employees": [{"id": x.employee_id, "name": _employee_name(x.employee), "vorname": ((x.employee.first_name if x.employee else "") or _employee_name(x.employee)).strip(),
                       "role": _rolle_in_kolonne(slot, x.employee_id),
                       "tage": [t.isoformat() for t in _tage_lesen(x)] if x.tage else None}  # seit 1.9.260 die Tage je Person (leer = alle Tage)
                      for x in slot.besetzung if visible_ids is None or x.employee_id in visible_ids],  # seit 1.9.247 mit Vorname (Balken)
        # seit 1.9.234 die Geräte des Einsatzes (Name live, Rolle aus der Kolonne, wenn das Gerät dort steht; tage leer = alle Tage)
        "resources": [{"id": x.resource_id, "name": x.resource.name if x.resource else f"Gerät #{x.resource_id}",
                       "type": x.resource.resource_type if x.resource else None, "role": _rolle_des_geraets(slot, x.resource_id),
                       "tage": [t.isoformat() for t in _tage_lesen(x)] if x.tage else None} for x in slot.geraete],
        "conflicts": conflicts or [],
        "niemand": not _besetzte_tage(slot),  # seit 1.9.263: ganz leer
        "leere_tage": [t.isoformat() for t in leere_tage(slot, arbeitstag)],
        "abschnitte": [[a.isoformat(), b.isoformat()] for a, b in abschnitte(slot, arbeitstag)],
    }


def _employee_assignment_slot_condition(employee_id: int):
    """Seit 1.9.233 (Stufe 6, R3a, Punkt 2): die Einsätze, in deren Besetzung die Person steht -- nichts sonst. Bis 1.9.232 (Text unten): Team-
    ODER Einzelzuweisung an der Arbeitsvorbereitung; die Migration e4b1c9d27a35 hat beide in die Besetzung übernommen, eine spätere Einzelzuweisung
    an der AV ist eine Zuweisung ohne Datum (Zugriff auf den Auftrag, kein Einsatz).

    Bis 1.9.232: Gemeinsame Zuordnungs-Bedingung Mitarbeiter -> PlanningSlot (Team- ODER Einzelzuweisung an
    der Arbeitsvorbereitung) -- seit 1.3.61 aus list_todays_assignments_for_employee()
    ausgelagert, damit list_upcoming_assignments_for_employee() (siehe dort, "Eigene
    Plantafel-Einträge" auf /mobil) dieselbe Zuordnung nutzt statt sie ein zweites Mal
    nachzubauen. Team-Zugehörigkeit über WorkPreparationTeamEmployee (Snapshot der
    Team-Besetzung zum Zuweisungszeitpunkt der WorkPreparationTeamAssignment, an der der Slot
    über team_assignment_id hängt), direkte Einzelzuweisung über WorkPreparationEmployee (an der
    WorkPreparation selbst, nicht am einzelnen Slot -- jeder Slot dieser AV zählt dann)."""
    return PlanningSlot.id.in_(select(PlanningSlotEmployee.slot_id).where(PlanningSlotEmployee.employee_id == employee_id))


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
    day = day or berlin_today()
    query = (
        _slot_query_with_order_options().options(selectinload(PlanningSlot.besetzung))
        .where(PlanningSlot.start_date <= day, PlanningSlot.end_date >= day, _employee_assignment_slot_condition(employee_id))
        .order_by(PlanningSlot.start_date)
    )
    # seit 1.9.262 (Stufe 6, R5a, Punkt 3): nur Einsätze, an denen sie an diesem Tag steht (ihre Tage am Einsatz)
    slots = [s for s in db.scalars(query).all() if any(x.employee_id == employee_id and day in _tage_der_zeile(s, x) for x in s.besetzung)]

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
    today = today or berlin_today()
    window_end = today + timedelta(days=days_ahead)
    query = (
        _slot_query_with_order_options().options(selectinload(PlanningSlot.besetzung))
        .where(
            PlanningSlot.end_date >= today, PlanningSlot.start_date <= window_end,
            _employee_assignment_slot_condition(employee_id),
        )
        .order_by(PlanningSlot.start_date)
    )
    # seit 1.9.262: nur Einsätze, an denen sie im Fenster an einem Tag steht
    slots = [s for s in db.scalars(query).all()
             if any(x.employee_id == employee_id and any(today <= t <= window_end for t in _tage_der_zeile(s, x)) for x in s.besetzung)]

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
    today = today or berlin_today()
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


def _undatiert_zugeordnete_order_ids(db: Session, employee_id: int) -> set[int]:
    """Seit 1.9.76 (Stufe 4, R4 Nachtrag 2): Aufträge, denen der Mitarbeiter an der Arbeitsvorbereitung zugeordnet ist
    (employee_assigned_order_ids(), Team- oder Einzelzuweisung), deren Arbeitsvorbereitung aber kein Datum trägt -- weder einen Abschnitt
    der Plantafel noch einen geplanten Zeitraum. Eine datierte Arbeitsvorbereitung entscheidet weiter das Zeitfenster."""
    order_ids = employee_assigned_order_ids(db, employee_id)
    if not order_ids:
        return set()
    preps = db.scalars(select(WorkPreparation).where(
        WorkPreparation.order_id.in_(order_ids), WorkPreparation.planned_start.is_(None), WorkPreparation.planned_end.is_(None))).all()
    if not preps:
        return set()
    mit_abschnitt = set(db.scalars(
        select(PlanningSlot.preparation_id).where(PlanningSlot.preparation_id.in_([p.id for p in preps])).distinct()).all())
    return {p.order_id for p in preps if p.id not in mit_abschnitt}


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
    umgekehrt").

    Seit 1.9.76 (Stufe 4, R4 Nachtrag 2) dazu, ebenfalls ungefenstert: jeder Auftrag, dem er an der Arbeitsvorbereitung zugeordnet ist,
    deren Arbeitsvorbereitung gar kein Datum trägt (_undatiert_zugeordnete_order_ids()) -- bis 1.9.75 fehlte er ("kein Anhaltspunkt
    für aktuell"), obwohl Buchen und Zugriff ihn zuließen. 1.9.74–1.9.78 galt diese Liste auch fürs Anlegen eines Berichts (seit
    1.9.79 zu jedem nicht stornierten Auftrag); außerhalb des Fensters datierte Aufträge bleiben draußen, abgeschlossene und stornierte
    filtert list_field_bookable_orders()."""
    today = today or berlin_today()
    relevant_prep_ids = _relevant_preparation_ids_for_employee(db, employee_id, window_days=window_days, today=today)

    order_ids: set[int] = set()
    if relevant_prep_ids:
        order_ids.update(db.scalars(
            select(WorkPreparation.order_id).where(WorkPreparation.id.in_(relevant_prep_ids))
        ).all())
    order_ids.update(db.scalars(
        select(ServiceReport.order_id).where(ServiceReport.created_by_employee_id == employee_id).distinct()
    ).all())
    order_ids.update(_undatiert_zugeordnete_order_ids(db, employee_id))
    return order_ids


def list_field_bookable_orders(db: Session, employee_id: int) -> list[dict]:
    """Die offenen Aufträge aus list_field_bookable_order_ids() als Anzeige-Dict (ID,
    Auftragsnummer, Kundenname, Objektadresse; seit 1.9.78 Titel und Objekt -- zwei Aufträge am selben Objekt
    unterscheidet der Titel, app/templates/_auftrag_text.html) -- die Auftragsauswahl der reduzierten
    Zeiterfassung. Eine Definition für GET /api/field-view/time-tracking/orders und den
    Monteur-Zweig von GET /api/time-tracking/context (seit 1.8.24)."""
    order_ids = list_field_bookable_order_ids(db, employee_id)
    if not order_ids:
        return []
    rows = db.scalars(
        select(Order)
        .where(
            Order.id.in_(order_ids),
            or_(Order.status.is_(None), func.lower(func.coalesce(Order.status, "")).not_in(["abgeschlossen", "storniert"])),
        )
        .order_by(Order.order_number.desc())
    ).all()
    return [auftrag_zeile(o) for o in rows]


def auftrag_zeile(o: Order) -> dict:
    """Seit 1.9.79: ein Auftrag, wie ihn die Monteurin in einer Liste sieht -- Nummer, Titel, Objekt, Kunde, Adresse (Schnappschüsse am
    Auftrag), sonst nichts. Für ihre Liste (list_field_bookable_orders()), die Auftragssuche (app/search.py::search_orders_for_field()) und
    die Daten zum Anlegen eines Berichts. Bis 1.9.78 hieß hier field_order_in_list(): seit 1.9.79 legt sie Berichte zu jedem nicht stornierten
    Auftrag an (app/service_reports.py::bericht_zum_auftrag_moeglich()), nicht mehr nur zu denen ihrer Liste."""
    return {"id": o.id, "order_number": o.order_number, "title": o.title, "property_name": o.property_name,
            "customer_name": o.customer_name, "property_address": o.property_address}


def _einsatz_abfrage():
    """Ein Einsatz mit allem, was Konflikte, Kapazität und slot_to_dict() lesen -- ohne Abfrage je Einsatz (seit 1.9.144). Nach Beginn sortiert."""
    return (
        select(PlanningSlot)
        .options(
            selectinload(PlanningSlot.capacity),
            selectinload(PlanningSlot.preparation).selectinload(WorkPreparation.order).selectinload(Order.project).selectinload(Project.property),
            selectinload(PlanningSlot.team_assignment).selectinload(WorkPreparationTeamAssignment.employees).selectinload(WorkPreparationTeamEmployee.employee),
            selectinload(PlanningSlot.team_assignment).selectinload(WorkPreparationTeamAssignment.resources).selectinload(WorkPreparationTeamResource.resource),
            selectinload(PlanningSlot.besetzung).selectinload(PlanningSlotEmployee.employee),
            selectinload(PlanningSlot.geraete).selectinload(PlanningSlotResource.resource),
        )
        .order_by(PlanningSlot.start_date, PlanningSlot.id)
    )


def _conflicts(db: Session, slots: list[PlanningSlot], settings: PlanningSettings, *, visible_employee_ids: set[int] | None = None,
               soll=None, antraege: dict | None = None) -> tuple[dict[int, list[dict]], dict[int, dict[date, dict]]]:
    """Seit 1.9.143 (P8): Einsätze stornierter Aufträge zählen nicht -- weder als Konflikt noch in der Kapazität, seit 1.9.151 ebenso die abgeschlossener
    Aufträge (Vorgabe Tobias, Zeichnung „zählt nicht“). Jeder Konflikt trägt seine Stufe
    („warnung“ fragt beim Speichern zurück, „hinweis“ steht nur in der Antwort). Seit 1.9.144 bekommt sie nur noch die Einsätze, um die es geht (nach
    Beginn sortiert, ein Paar ohne Überschneidung beendet die Runde), nicht mehr alle Einsätze aller Jahre."""
    result: dict[int, list[dict]] = defaultdict(list)
    distributions: dict[int, dict[date, dict]] = {}
    slots = sorted((s for s in slots if not geschlossen(s.preparation.order)), key=lambda s: (s.start_date, s.id))
    if not slots:
        return result, distributions
    start = min(s.start_date for s in slots); end = max(s.end_date for s in slots)
    holiday_names, _holiday_meta = _combined_holiday_map(db, start, end); holiday_dates = set(holiday_names)
    if visible_employee_ids is None:
        visible_employee_ids = planning_visible_employee_ids(db)
    # seit 1.9.233 aus der Besetzung der Einsätze (bis 1.9.232 aus dem Schnappschuss der Kolonnen)
    employee_ids = {x.employee_id for s in slots for x in s.besetzung if x.employee_id in visible_employee_ids}
    personen = [x.employee for s in slots for x in s.besetzung if x.employee_id in visible_employee_ids and x.employee is not None]
    absence_rows = _absence_rows(db, start, end, employee_ids); absences = _abwesend_map(db, absence_rows, personen, start, end)
    offene_antraege = antraege if antraege is not None else _offene_antraege(db, start, end, employee_ids)  # seit 1.9.247 von der Tafel mitgegeben
    if soll is None:  # seit 1.9.211: die Kapazität aus der Sollzeit des Lohns, einmal für alle Einsätze (die Tafel gibt ihre mit)
        soll = _soll_je_tag(db, personen, start, end)
    arbeitstage = _working_weekdays(settings)
    pruefungen = _pruefungen(db, {x.resource_id for s in slots for x in s.geraete})  # seit 1.9.236

    for i, a in enumerate(slots):
        a_emps, a_res = _slot_members(a, visible_employee_ids)
        for j in range(i + 1, len(slots)):
            b = slots[j]
            if b.start_date > a.end_date:
                break
            b_emps, b_res = _slot_members(b, visible_employee_ids)
            issues = []
            # seit 1.9.236 kein „Kolonne doppelt“ mehr: zwei Einsätze derselben Kolonne mit verschiedenen Personen sind kein Konflikt (Zeichnung)
            for eid in sorted(a_emps & b_emps):
                xa = next(x for x in a.besetzung if x.employee_id == eid)
                xb = next(x for x in b.besetzung if x.employee_id == eid)
                gemeinsam = _tage_der_zeile(a, xa) & _tage_der_zeile(b, xb)  # seit 1.9.261 nur an gemeinsamen Tagen (bis 1.9.260: Zeiträume überschneiden sich)
                if gemeinsam:
                    # seit 1.9.250: wen der Konflikt betrifft („Personen“ zeigt ihn nur bei ihr); seit 1.9.261 an welchen Tagen
                    issues.append(("employee", _employee_name(xa.employee), {"employee_id": eid, "tage": sorted(gemeinsam)}))
            for rid in sorted(a_res & b_res):  # seit 1.9.234 nur, wenn sich die Tage des Geräts in beiden Einsätzen treffen
                ra = next(x for x in a.geraete if x.resource_id == rid)
                rb = next(x for x in b.geraete if x.resource_id == rid)
                gemeinsam = _tage_der_zeile(a, ra) & _tage_der_zeile(b, rb)
                if gemeinsam:
                    # seit 1.9.255: welches Gerät -- die Zeile eines Geräts zeigt nur seine Warnungen; seit 1.9.261 an welchen Tagen
                    issues.append(("resource", ra.resource.name if ra.resource else f"Ressource #{rid}", {"resource_id": rid, "tage": sorted(gemeinsam)}))
            for kind, label, wen in issues:
                result[a.id].append({"type": kind, "label": label, "other_slot_id": b.id, "other_project": b.preparation.order.project.project_number, "other_project_name": b.preparation.order.project.name, **wen})
                result[b.id].append({"type": kind, "label": label, "other_slot_id": a.id, "other_project": a.preparation.order.project.project_number, "other_project_name": a.preparation.order.project.name, **wen})

    for slot in slots:
        distribution, shortfall = _slot_distribution(db, slot, settings, holiday_dates, absences, visible_employee_ids, soll)
        distributions[slot.id] = distribution
        seen_absence = set()
        tage_je = _tage_je_person(slot)  # seit 1.9.261: abwesend, Freistellung und Antrag nur an den Tagen der Person
        for day in _date_range(slot.start_date, slot.end_date):
            # seit 1.9.150: ein Feiertag an einem Tag, der ohnehin kein Arbeitstag ist, meldet nichts; seit 1.9.261 auch nicht, wenn an dem Tag niemand steht
            if day in holiday_names and day.weekday() in arbeitstage and _jemand_am(slot, day):
                result[slot.id].append({"type":"holiday", "label":holiday_names[day], "date":day, "other_slot_id":None, "other_project":None, "other_project_name":None})
            frei = []  # seit 1.9.188: wer an dem Tag eine Freistellung des Arbeitszeitkalenders hat -- ein Hinweis je Tag, wie der betriebsfreie Tag
            for member in slot.besetzung:  # seit 1.9.233 die Besetzung des Einsatzes
                if member.employee_id not in visible_employee_ids or day not in tage_je[member.employee_id]: continue
                name = _employee_name(member.employee)
                absence = absences.get((member.employee_id, day))
                if isinstance(absence, Freistellung):
                    frei.append((absence.kalendertag, name, member.employee_id))
                    continue
                if absence and absence.id not in seen_absence:
                    seen_absence.add(absence.id)
                    # label_redacted ist das buero_auftrag-sichere Gegenstück (siehe CLAUDE.md
                    # "Krankheitssichtbarkeit") -- der Router entscheidet anhand der Rolle, welche
                    # der beiden Label-Varianten in der Antwort landet, diese Funktion bleibt
                    # rollenblind.
                    result[slot.id].append({"type":"absence", "label":f"{name} · {absence.absence_type}", "label_redacted":f"{name} · abwesend", "date":day, "employee_id":member.employee_id, "other_slot_id":None, "other_project":None, "other_project_name":None})
            if frei:
                result[slot.id].append({"type":"kalendertag", "label":f"{frei[0][0]} – {', '.join(n for _, n, _i in frei)}", "date":day, "employee_ids":[i for *_, i in frei], "other_slot_id":None, "other_project":None, "other_project_name":None})
        # Seit 1.9.152 (R1 Nachrunde, Punkt 3): ein offener Antrag ist ein Hinweis -- keine Rückfrage, keine Kapazität. Die Art wie bei der Abwesenheit nur für
        # Admin und Büro – Finanzen, der Router wählt die Fassung (label_redacted).
        for member in slot.besetzung:
            if member.employee_id not in visible_employee_ids: continue
            name = _employee_name(member.employee)
            for antrag in offene_antraege.get(member.employee_id, ()):
                betroffen = sorted(t for t in tage_je[member.employee_id] if antrag.start_date <= t <= antrag.end_date)  # seit 1.9.261 an ihren Tagen
                if betroffen:
                    result[slot.id].append({"type":"antrag_offen", "label":f"{name} · {antrag.absence_type}", "label_redacted":name, "date":betroffen[0], "employee_id":member.employee_id, "other_slot_id":None, "other_project":None, "other_project_name":None})
        # Seit 1.9.236 (Punkt 5): ein Gerät, dessen Prüfung an einem seiner Tage abgelaufen ist (fällig vor dem Tag) -- eine Warnung je Gerät und
        # Prüfung, mit dem ersten solchen Tag; gezählt werden die Arbeitstage des Geräts (hat es keinen, alle seine Tage), wie beim Kalender des Geräts.
        for row in slot.geraete:
            tage = sorted(_tage_der_zeile(slot, row))
            tage = [t for t in tage if _is_workday(t, settings, holiday_dates)] or tage
            for art, faellig in pruefungen.get(row.resource_id, ()):
                spaeter = [t for t in tage if t > faellig]
                if spaeter:
                    name = row.resource.name if row.resource else f"Gerät #{row.resource_id}"
                    result[slot.id].append({"type":"pruefung", "label":f"{name} · {art} fällig am {faellig:%d.%m.%Y}", "date":spaeter[0],
                                            "resource_id":row.resource_id,  # seit 1.9.255
                                            "other_slot_id":None, "other_project":None, "other_project_name":None})
        # seit 1.9.266 (Stufe 6, R5b, Punkt 0b, Frage 2 aus R5a): ein ganz leerer Einsatz („niemand“) meldet keine Kapazität -- bis 1.9.265 sagte er
        # „Kapazität reicht nicht“ für seine Stunden (Festlegung 1.9.263 Nr. 2, zweiter Teil)
        if shortfall > 0 and _besetzte_tage(slot):
            result[slot.id].append({"type":"capacity", "label":f"Kapazität reicht um {stunden_text(shortfall)} nicht aus", "shortfall_hours":shortfall, "other_slot_id":None, "other_project":None, "other_project_name":None})
    for liste in result.values():
        for konflikt in liste:
            konflikt["stufe"] = "warnung" if konflikt["type"] in WARNUNG_ARTEN else "hinweis"
    return result, distributions


def termine_der_geraete(db: Session, slot: PlanningSlot, settings: PlanningSettings) -> list[tuple[str, CalendarEvent | OutlookSeriesOccurrence, date]]:
    """Einträge im Kalender eines Geräts, die die Arbeitstage eines Einsatzes berühren (seit 1.9.161, Kran-Kalender): je Eintrag Name des Geräts, Zeile und erster betroffener Tag. Ein Einsatz belegt
    ganze Tage, deshalb zählt jeder Termin an einem dieser Tage, auch einer von zwei Stunden. Tage, an denen nicht gearbeitet wird, belegen das Gerät nicht (1.9.150); hat der Einsatz gar keinen
    Arbeitstag, zählen alle seine Tage. Serienvorkommen zählen wie Einzeltermine."""
    # seit 1.9.234 die Geräte des Einsatzes, je an seinen Tagen (bis 1.9.233 die der Kolonne, alle Tage)
    if not slot.geraete:
        return []
    feiertage = set(_combined_holiday_map(db, slot.start_date, slot.end_date)[0])
    return _termine_am_einsatz(slot, settings, feiertage, _termin_zeilen(db, {x.resource_id for x in slot.geraete}, slot.start_date, slot.end_date))


def _termin_zeilen(db: Session, geraete: set[int], von: date, bis: date) -> list:
    """Die Einträge in den Kalendern der Geräte, die den Zeitraum berühren -- Termine (ohne die der Einsätze selbst, seit 1.9.241) und Serienvorkommen,
    je Tabelle eine Abfrage (seit 1.9.255 auch für die Tafel, alle Einsätze im Bild auf einmal)."""
    out = []
    for modell in (CalendarEvent, OutlookSeriesOccurrence):
        bedingung = [modell.resource_id.in_(geraete), modell.start_at <= datetime.combine(bis, time.max), modell.end_at >= datetime.combine(von, time.min)]
        if modell is CalendarEvent:
            bedingung.append(CalendarEvent.planning_slot_id.is_(None))  # seit 1.9.241: die Termine der Einsätze selbst sind keine fremde Belegung
        out.extend(db.scalars(select(modell).where(*bedingung).order_by(modell.start_at)))
    return out


def _termine_am_einsatz(slot: PlanningSlot, settings: PlanningSettings, feiertage: set[date], zeilen: list) -> list[tuple[str, CalendarEvent | OutlookSeriesOccurrence, date]]:
    """Welche dieser Einträge die Tage der Geräte des Einsatzes treffen (Arbeitstage; hat der Einsatz keinen, alle seine Tage) -- mit dem ersten Tag."""
    geraete = {x.resource_id: x.resource.name if x.resource else f"Gerät #{x.resource_id}" for x in slot.geraete}
    alle_tage = list(_date_range(slot.start_date, slot.end_date))
    arbeitstage = [t for t in alle_tage if _is_workday(t, settings, feiertage)] or alle_tage
    tage_je = {x.resource_id: [t for t in arbeitstage if t in _tage_der_zeile(slot, x)] or sorted(_tage_der_zeile(slot, x)) for x in slot.geraete}
    out = []
    for zeile in zeilen:
        if zeile.resource_id not in tage_je:
            continue
        tag = next((t for t in tage_je[zeile.resource_id] if zeile.start_at.date() <= t <= zeile.end_at.date()), None)
        if tag is not None:
            out.append((geraete[zeile.resource_id], zeile, tag))
    return out


def _termin_warnung(name: str, zeile, tag: date) -> dict:
    """Ein Eintrag im Kalender eines Geräts als Warnung „Gerät doppelt“ (seit 1.9.255 mit dem Gerät); der Titel eines privaten Termins heißt „Belegt“."""
    return {"type": "resource", "label": f"{name} · Termin: {BUSY_PLACEHOLDER_TITLE if zeile.is_private else zeile.title}", "date": tag, "stufe": "warnung",
            "resource_id": zeile.resource_id, "other_slot_id": None, "other_project": None, "other_project_name": None}


def termin_warnungen_der_tafel(db: Session, slots: list[PlanningSlot], settings: PlanningSettings) -> dict[int, list[dict]]:
    """Seit 1.9.255 (Stufe 6, R4b, Punkt 5): die Einträge im Postfach eines Geräts warnen auch auf der Tafel -- wie beim Speichern
    (termine_der_geraete()), für alle Einsätze im Bild mit einer Abfrage je Tabelle. Einsätze geschlossener Aufträge zählen nicht (1.9.143/1.9.151)."""
    slots = [s for s in slots if s.geraete and not geschlossen(s.preparation.order)]
    if not slots:
        return {}
    von, bis = min(s.start_date for s in slots), max(s.end_date for s in slots)
    zeilen = _termin_zeilen(db, {x.resource_id for s in slots for x in s.geraete}, von, bis)
    if not zeilen:
        return {}
    feiertage = set(_combined_holiday_map(db, von, bis)[0])
    out: dict[int, list[dict]] = {}
    for slot in slots:
        treffer = [_termin_warnung(*t) for t in _termine_am_einsatz(slot, settings, feiertage, zeilen)]
        if treffer:
            out[slot.id] = treffer
    return out


def _termine_der_geraete(db: Session, slot: PlanningSlot, settings: PlanningSettings) -> list[dict]:
    """Dasselbe als Warnung „Gerät doppelt“ beim Speichern; der Titel eines privaten Termins steht als „Belegt“ da."""
    return [_termin_warnung(name, zeile, tag) for name, zeile, tag in termine_der_geraete(db, slot, settings)]


def einsatz_konflikte(db: Session, slot: PlanningSlot) -> dict:
    """Warnungen und Hinweise eines Einsatzes (seit 1.9.143) -- dieselbe Rechnung wie die Tafel (_conflicts()), gegen die Einsätze, die seinen Zeitraum
    berühren. Liest nur, sieht den Stand der offenen Transaktion. Ein Einsatz eines stornierten (P8) oder abgeschlossenen Auftrags (seit 1.9.151) hat keine."""
    if geschlossen(slot.preparation.order):
        return {"warnungen": [], "hinweise": []}
    settings = load_planning_settings(db)
    andere = db.scalars(_einsatz_abfrage().where(PlanningSlot.id != slot.id, PlanningSlot.start_date <= slot.end_date, PlanningSlot.end_date >= slot.start_date)).all()
    konflikte, _ = _conflicts(db, [slot, *andere], settings)
    liste = konflikte.get(slot.id, []) + _termine_der_geraete(db, slot, settings)
    return {"warnungen": [k for k in liste if k["stufe"] == "warnung"], "hinweise": [k for k in liste if k["stufe"] == "hinweis"]}


def _pruefungen(db: Session, geraet_ids: set[int]) -> dict[int, list[tuple[str, date]]]:
    """Seit 1.9.236 (Stufe 6, R3a, Punkt 5): je Gerät (OperationalResource) die Prüfungen seines Betriebsmittels mit Fälligkeit -- (Art, fällig am),
    eine Abfrage für alle. Nur bei eingeschalteter Betriebsmittelverwaltung: ausgeschaltet pflegt niemand die Prüffristen."""
    from .modules import is_module_enabled
    if not geraet_ids or not is_module_enabled(db, "betriebsmittel"):
        return {}
    je: dict[int, list[tuple[str, date]]] = {}
    for rid, art, faellig in db.execute(
            select(OperationalAsset.resource_id, OperationalAssetInspection.inspection_type, OperationalAssetInspection.next_due_date)
            .join(OperationalAssetInspection, OperationalAssetInspection.asset_id == OperationalAsset.id)
            .where(OperationalAsset.resource_id.in_(geraet_ids), OperationalAssetInspection.next_due_date.is_not(None))
            .order_by(OperationalAssetInspection.next_due_date, OperationalAssetInspection.id)):
        je.setdefault(rid, []).append((art, faellig))
    return je


def termin_tage(termin) -> tuple[date, date]:
    """Erster und letzter Tag eines Termins: ganztägig der erste bis letzte Tag, sonst der Tag des Beginns bis zum Tag vor einem Ende um Mitternacht
    (seit 1.9.241 in kran_termin_uebernehmen(), seit 1.9.247 auch für die Tafel)."""
    von = termin.start_at.date()
    if termin.all_day:
        bis = termin.end_at.date()
    else:
        bis = (termin.end_at - timedelta(microseconds=1)).date() if termin.end_at > termin.start_at else von
    return von, max(von, bis)


def geraete_termine(db: Session, geraet_ids: set[int], start: date, end: date) -> list[dict]:
    """Seit 1.9.247 (Stufe 6, R4, Punkt 1): Termine im Kalender eines Geräts, die direkt in Outlook entstanden (nicht die der Einsätze,
    planning_slot_id leer), im Zeitraum der Tafel -- für die Zeile des Geräts. Ein privater Termin heißt „Belegt“. uebernehmbar: ein Einzeltermin
    lässt sich als Kranvermietung übernehmen (kran_termin_uebernehmen()), ein Serienvorkommen nicht."""
    if not geraet_ids:
        return []
    von, bis = datetime.combine(start, time.min), datetime.combine(end, time.max)
    out = []
    for modell in (CalendarEvent, OutlookSeriesOccurrence):
        bedingung = [modell.resource_id.in_(geraet_ids), modell.start_at <= bis, modell.end_at >= von]
        if modell is CalendarEvent:
            bedingung.append(CalendarEvent.planning_slot_id.is_(None))
        for zeile in db.scalars(select(modell).where(*bedingung).order_by(modell.start_at, modell.id)):
            erster, letzter = termin_tage(zeile)
            out.append({"id": zeile.id, "resource_id": zeile.resource_id, "titel": BUSY_PLACEHOLDER_TITLE if zeile.is_private else zeile.title,
                        "von": erster, "bis": letzter, "zeit": None if zeile.all_day else f"{zeile.start_at:%H:%M}",
                        "uebernehmbar": modell is CalendarEvent, "privat": bool(zeile.is_private)})  # seit 1.9.251 privat
    return out


def personen_termine(db: Session, employee_ids: set[int], start: date, end: date, betrachter_user_id: int | None = None) -> tuple[set[int], list[dict]]:
    """Seit 1.9.250 (Stufe 6, R4, Punkt 3): die Personen mit Konto (aktives Konto mit Mitarbeiter) und die Termine aus ihrem Kalender im Zeitraum der
    Tafel -- für ihre Zeile in „Personen“. Ein privater Termin heißt „Belegt“, außer für seinen Besitzer (calendar_events.is_redacted_for_viewer(), wie im
    Kalender). Ohne Modul „Kalender“ keine Termine (die Personen mit Konto bleiben). Serienvorkommen zählen wie Einzeltermine."""
    from .calendar_events import is_redacted_for_viewer
    from .models import AppUser
    from .modules import is_module_enabled

    if not employee_ids:
        return set(), []
    konten = {u.id: u.employee_id for u in db.scalars(select(AppUser).where(AppUser.employee_id.in_(employee_ids), AppUser.active == True))}  # noqa: E712
    mit_konto = set(konten.values())
    if not konten or not is_module_enabled(db, "kalender"):
        return mit_konto, []
    von, bis = datetime.combine(start, time.min), datetime.combine(end, time.max)
    out = []
    for modell in (CalendarEvent, OutlookSeriesOccurrence):
        for zeile in db.scalars(select(modell).where(modell.owner_user_id.in_(konten), modell.start_at <= bis, modell.end_at >= von)
                                .order_by(modell.start_at, modell.id)):
            erster, letzter = termin_tage(zeile)
            belegt = is_redacted_for_viewer({"is_private": zeile.is_private, "owner_user_id": zeile.owner_user_id}, betrachter_user_id)
            # seit 1.9.254 „belegt“: ein privater Termin für jemand anderen -- auf der Tafel kein Knopf in den Kalender
            out.append({"id": zeile.id, "employee_id": konten[zeile.owner_user_id], "titel": BUSY_PLACEHOLDER_TITLE if belegt else zeile.title,
                        "von": erster, "bis": letzter, "zeit": None if zeile.all_day else f"{zeile.start_at:%H:%M}", "serie": modell is OutlookSeriesOccurrence,
                        "belegt": belegt})
    return mit_konto, out


def _geraet_pruefung(pruefungen: list[tuple[str, date]], heute: date) -> str | None:
    """Seit 1.9.247: die nächste Prüfung eines Geräts für die Zeile der Tafel -- „UVV gültig bis 03/2027“, abgelaufen „UVV fällig seit 03.11.2026“."""
    if not pruefungen:
        return None
    art, faellig = pruefungen[0]
    return f"{art} fällig seit {faellig:%d.%m.%Y}" if faellig < heute else f"{art} gültig bis {faellig:%m/%Y}"


def abwesenheiten_der_tafel(db: Session, absence_rows: list[EmployeeAbsence], absences: dict, employee_ids: set[int], start: date, end: date,
                            antraege: dict | None = None) -> list[dict]:
    """Seit 1.9.247 (Stufe 6, R4): je Person die Abwesenheiten im Bild als Zeiträume -- genehmigt (gespeichert), Freistellung des Arbeitszeitkalenders
    (abgeleitet, je Folge gleicher Tage) und offene Anträge (beantragt). art ist die Art bzw. der Tag des Kalenders; die Fassung für Büro – Auftrag
    schwärzt der Router (Krankheitssichtbarkeit)."""
    out = [{"employee_id": a.employee_id, "art": a.absence_type, "stand": "genehmigt", "von": a.start_date, "bis": a.end_date} for a in absence_rows]
    frei = sorted((eid, tag, f.kalendertag) for (eid, tag), f in absences.items() if isinstance(f, Freistellung) and start <= tag <= end)
    for eid, tag, name in frei:
        letzte = out[-1] if out else None
        if letzte and letzte["stand"] == "frei" and letzte["employee_id"] == eid and letzte["art"] == name and letzte["bis"] + timedelta(days=1) == tag:
            letzte["bis"] = tag
        else:
            out.append({"employee_id": eid, "art": name, "stand": "frei", "von": tag, "bis": tag})
    for eid, liste in (antraege if antraege is not None else _offene_antraege(db, start, end, employee_ids)).items():
        out += [{"employee_id": eid, "art": a.absence_type, "stand": "beantragt", "von": a.start_date, "bis": a.end_date} for a in liste
                if eid in employee_ids and a.start_date <= end and a.end_date >= start]
    return out


def tafel_zaehler(slots: list[dict]) -> dict:
    """Seit 1.9.247: Warnungen und Hinweise im Bild für den Knopf der Leiste -- ein Paar (Person oder Gerät doppelt) zählt einmal, nicht je Einsatz."""
    warnungen, hinweise = set(), 0
    for s in slots:
        for k in s.get("conflicts", []):
            if k.get("stufe") == "warnung":
                warnungen.add((k["type"], k.get("label"), frozenset({s["id"], k.get("other_slot_id")}) if k.get("other_slot_id") else s["id"], str(k.get("date"))))
            else:
                hinweise += 1
    return {"warnungen": len(warnungen), "hinweise": hinweise}


class KranTerminUngueltig(ValueError):
    """Seit 1.9.241: der Termin lässt sich nicht als Kranvermietung übernehmen (kein Termin am Gerät, schon übernommen) -- 409."""


def kran_termin_uebernehmen(db: Session, event_id: int, **werte) -> PlanningSlot:
    """Seit 1.9.241 (Stufe 6, R3b, Punkt 3): ein Termin, der direkt im Kalender des Krans entstand (Telefon, WhatsApp, Mail), wird eine Kranvermietung --
    an einem Auftrag oder mit Kunde wie create_slot(), mit dem Gerät des Termins für alle Tage, an seinen Tagen (ein ganztägiger von erstem bis letztem
    Tag, sonst der Tag des Beginns bis zum Tag vor dem Ende um Mitternacht). Der Termin wird der Termin des neuen Einsatzes (die Plantafel ist ab jetzt
    führend, der nächste Abgleich überschreibt ihn in Outlook). Ohne Notiz übernimmt der Einsatz den Titel des Termins, außer der Termin ist privat."""
    return create_slot(db, **_kran_termin_werte(_kran_termin(db, event_id), werte))


def kran_termin_pruefen(db: Session, event_id: int, *, mit_art: bool = False, weitere_personen=(), weitere_geraete=(), **werte) -> dict:
    """Seit 1.9.251 (Stufe 6, R4, Punkt 5): die Vorschau des Dialogs „Als Kranvermietung übernehmen …“ -- derselbe Weg wie kran_termin_uebernehmen()
    (der Termin gehört schon im Flush zum Einsatz, warnt also nicht gegen sich selbst), schreibt nichts (einsatz_pruefen(), rollback)."""
    return einsatz_pruefen(db, mit_art=mit_art, weitere_personen=weitere_personen, weitere_geraete=weitere_geraete,
                           **_kran_termin_werte(_kran_termin(db, event_id), werte))


def _kran_termin(db: Session, event_id: int) -> CalendarEvent:
    """Der Termin am Gerät, gesperrt bis zum Commit -- 404 („Termin nicht gefunden.“) bzw. KranTerminUngueltig (kein Gerät, schon übernommen)."""
    termin = db.scalar(select(CalendarEvent).where(CalendarEvent.id == event_id).with_for_update())
    if termin is None:
        db.rollback()
        raise ValueError("Termin nicht gefunden.")
    if termin.resource_id is None or termin.planning_slot_id is not None:
        db.rollback()
        raise KranTerminUngueltig("Nur ein Termin aus dem Kalender eines Geräts lässt sich als Kranvermietung übernehmen." if termin.resource_id is None
                                  else "Dieser Termin gehört schon zu einem Einsatz der Plantafel.")
    return termin


def _kran_termin_werte(termin: CalendarEvent, werte: dict) -> dict:
    """Gerät und Zeitraum vom Termin, ohne Notiz sein Titel (nicht bei einem privaten)."""
    von, bis = termin_tage(termin)
    if werte.get("notes") is None and not termin.is_private:
        werte["notes"] = termin.title
    return {"art": "kranvermietung", "team_id": None, "geraete": [{"resource_id": termin.resource_id}], "start_date": von, "end_date": max(von, bis),
            "kran_termin_id": termin.id, **werte}


def _warnungen_pruefen(db: Session, slot_id: int) -> None:
    """Nach dem Flush, vor dem Commit: mit Warnungen alles zurück (auch die Sperre) und PlanungsWarnung."""
    konflikte = einsatz_konflikte(db, _load_slot(db, slot_id, frisch=True))
    if konflikte["warnungen"]:
        db.rollback()
        raise PlanungsWarnung(konflikte["warnungen"], konflikte["hinweise"])


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
    settings = load_planning_settings(db)
    daily = _d(daily_work_hours if daily_work_hours is not None else settings.daily_work_hours)
    travel = _d(travel_hours_per_employee_day if travel_hours_per_employee_day is not None else settings.default_travel_hours_per_employee_day)
    if travel >= daily:
        raise ValueError("Anfahrtszeit muss kleiner als die tägliche Arbeitszeit sein.")
    target = planned_hours(order)
    if target <= 0:
        raise ValueError("Für diesen Auftrag sind keine kalkulierten Soll-Stunden vorhanden.")
    horizon_end = start_date + timedelta(days=730)
    holiday_map, _holiday_meta = _combined_holiday_map(db, start_date, horizon_end); holiday_dates=set(holiday_map)
    abs_rows = _absence_rows(db, start_date, horizon_end, {e.id for e in employees}); absences = _abwesend_map(db, abs_rows, employees, start_date, horizon_end)  # seit 1.9.188
    # seit 1.9.211 (L1a Stufe 5, Punkt 4): Kapazität aus der Sollzeit des Lohns. Die volle Tageskapazität der Kolonne ist die des ersten Tags ab dem
    # Start, an dem sie ohne Abwesenheiten und Feiertage Sollzeit hat (bis 1.9.210: MA × (Arbeitsstunden je Tag − Anfahrt) am ersten Arbeitstag
    # der Planung); daily_work_hours prüft nur noch die Anfahrt
    soll = _SollAbschnitte(db, employees, start_date)
    voll_tag = next((d for d in _date_range(start_date, horizon_end) if _day_capacity(employees, d, settings, travel, set(), {}, soll)[0] > 0), None)
    full_capacity, voll_da, _ = _day_capacity(employees, voll_tag, settings, travel, set(), {}, soll) if voll_tag else (Decimal("0"), [], [])
    if full_capacity <= 0:
        raise ValueError("Mit den gewählten Arbeits-/Anfahrtszeiten ergibt sich keine verfügbare Tageskapazität.")
    remaining = target
    day_rows=[]; current=start_date; last=None; workdays_used=0
    while remaining > 0 and current <= horizon_end:
        cap, available, absent = _day_capacity(employees, current, settings, travel, holiday_dates, absences, soll)
        if cap > 0:
            assigned=min(remaining,cap); remaining-=assigned; workdays_used+=1; last=current
            day_rows.append({
                "date":current, "capacity_hours":cap, "assigned_hours":round_hours(assigned),
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
        "full_team_daily_capacity":full_capacity,"full_team_capacity_date":voll_tag,"required_team_days_decimal":equivalent_days,
        "calendar_workdays_needed":workdays_used,"suggested_start":start_date,"suggested_end":last,
        "last_day_clock_hours_per_employee":last_clock,"days":day_rows,
        # seit 1.9.148 (P13) deutsch, zwei Stellen wie „Zeiten“ (bis 1.9.147 „24.00 h / (4 MA × (8.00 h − 0 h)) = 0.75 Teamtage“); seit 1.9.211 mit
        # der Kapazität aus der Sollzeit (bis 1.9.210 „… / (4 MA × (8,00 h − 0,00 h)) = …“)
        "formula":f"{stunden_text(target)} / {stunden_text(full_capacity)} (Sollzeit von {len(voll_da)} MA am {voll_tag:%d.%m.%Y} − je {stunden_text(travel)} Anfahrt) = {str(equivalent_days).replace('.', ',')} Teamtage",
    }


def offene_auftraege(db: Session) -> list[dict]:
    """Die Auswahl im Dialog „Einsatz planen“ (seit 1.9.144, GET /api/planning/auftraege): nur offene Aufträge, nur was die Auswahl zeigt, eine Abfrage.
    Bis 1.9.143 lud die Tafel dafür bei jedem Laden GET /api/orders -- rund 39 Abfragen je Auftrag, 53 s bei 4000 Aufträgen (Befund Stufe 6, 7.3)."""
    return [{"id": i, "order_number": nummer, "project_number": projekt, "project_name": name, "project_id": pid, "customer_name": kunde}  # seit 1.9.248 Projekt und Kunde (Kopf des Dialogs)
            for i, nummer, projekt, name, pid, kunde in db.execute(
                select(Order.id, Order.order_number, Project.project_number, Project.name, Project.id, Order.customer_name)
                .join(Project, Order.project_id == Project.id).where(offen_bedingung()).order_by(Order.id.desc()))]


def rueckstand(db: Session) -> list[dict]:
    """„Nicht eingeplant“: offene Aufträge ohne Einsatz (seit 1.9.144 im SQL gefiltert und auf einmal geladen; bis 1.9.143 alle Aufträge und load_order() je Auftrag)."""
    mit_einsatz = select(WorkPreparation.order_id).join(PlanningSlot, PlanningSlot.preparation_id == WorkPreparation.id)
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.project).selectinload(Project.property), selectinload(Order.items).selectinload(OrderItem.calculation_snapshot))
        .where(offen_bedingung(), Order.id.not_in(mit_einsatz))
        .order_by(Order.order_date.desc(), Order.id.desc())
    ).all()
    if not orders:
        return []
    vorbereitungen = {x.order_id: x for x in db.scalars(select(WorkPreparation).where(WorkPreparation.order_id.in_([o.id for o in orders])))}
    pausen = pause_begruendungen(db, orders)
    zeilen = []
    for order in orders:
        prep = vorbereitungen.get(order.id)
        prop = order.project.property
        address = ""
        if prop:
            address = ", ".join(x for x in [prop.street, f"{prop.postal_code or ''} {prop.city or ''}".strip()] if x)
        elif order.property_address:
            address = order.property_address.replace("\n", ", ")
        zeilen.append({"order_id": order.id, "order_number": order.order_number, "project_id": order.project_id, "project_number": order.project.project_number,
                       "project_name": order.project.name, "customer_name": order.customer_name, "property_address": address, "planned_hours": planned_hours(order),
                       "suggested_start": prep.planned_start if prep else order.execution_start, "suggested_end": prep.planned_end if prep else order.execution_end,
                       "order_status": status_wert(order.status), "order_status_label": status_name(order.status), "order_status_reason": pausen.get(order.id)})
    return zeilen


def planning_board(db: Session, start_date: date, end_date: date, betrachter_user_id: int | None = None) -> dict:
    if end_date < start_date:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    if (end_date - start_date).days > 62:
        raise ValueError("Die Plantafel kann maximal 63 Tage gleichzeitig anzeigen.")
    settings = load_planning_settings(db)
    visible = db.scalars(_einsatz_abfrage().where(PlanningSlot.start_date <= end_date, PlanningSlot.end_date >= start_date)).all()
    # Seit 1.9.144: Konflikte nur für Einsätze, die den Zeitraum berühren -- und gegen die, die mit ihnen über den Rand hinaus zusammenfallen. Ein alter
    # Einsatz kostet nichts mehr (bis 1.9.143 paarweise über alle Einsätze aller Jahre: 15 s bei 7.600 Einsätzen, Befund Stufe 6, 7.3).
    relevant = visible
    if visible:
        rand_start, rand_ende = min(x.start_date for x in visible), max(x.end_date for x in visible)
        if rand_start < start_date or rand_ende > end_date:
            relevant = db.scalars(_einsatz_abfrage().where(PlanningSlot.start_date <= rand_ende, PlanningSlot.end_date >= rand_start)).all()
    all_employees=db.scalars(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.active==True).order_by(Employee.last_name,Employee.first_name)).all()
    kennzeichen=_plantafel_map(db,all_employees)  # seit 1.9.253: das Kennzeichen „Plantafel“ einmal für alle
    visible_employee_ids={x.id for x in all_employees if kennzeichen[x.id]!="nicht_zeigen"}
    employees=[x for x in all_employees if x.id in visible_employee_ids]
    # seit 1.9.211: die Sollzeit einmal für Tafel und Konflikte, über den Zeitraum der Tafel samt dem der Einsätze, die über den Rand reichen --
    # sonst hinge die Zahl der Abfragen an den Einsätzen im Bild (test_v564)
    soll_von = min([start_date] + [x.start_date for x in relevant]); soll_bis = max([end_date] + [x.end_date for x in relevant])
    soll=_soll_je_tag(db,employees,soll_von,soll_bis)
    # seit 1.9.247: die offenen Anträge einmal für Konflikte und die Abwesenheiten der Tafel (test_v570: eine Abfrage)
    antraege=_offene_antraege(db,soll_von,soll_bis,{x.id for x in employees}|{x.employee_id for s in relevant for x in s.besetzung})
    conflict_map, distributions = _conflicts(db, relevant, settings, visible_employee_ids=visible_employee_ids, soll=soll, antraege=antraege)
    for slot_id, warnungen in termin_warnungen_der_tafel(db, visible, settings).items():  # seit 1.9.255 (bis 1.9.254 nur beim Speichern)
        conflict_map[slot_id] = conflict_map.get(slot_id, []) + warnungen

    teams = db.scalars(select(Team).options(selectinload(Team.employees).selectinload(TeamEmployee.employee),selectinload(Team.resources).selectinload(TeamResource.resource)).order_by(Team.name)).all()
    used_team_ids = {x.team_assignment.team_id for x in visible if x.team_assignment is not None}
    team_rows=[]
    for team in teams:
        if not team.active and team.id not in used_team_ids: continue
        team_rows.append({"id":team.id,"number":team.team_number,"name":team.name,"active":team.active,
            # seit 1.9.247 Vorname und Kolonnenführer (Zeile der Tafel: „Tom (KF), Mia, Ole“)
            "employees":[{"id":x.employee_id,"name":_employee_name(x.employee),"vorname":(x.employee.first_name or _employee_name(x.employee)).strip(),"role":x.role,"kf":bool(x.is_crew_leader)} for x in team.employees if x.employee and x.employee_id in visible_employee_ids],
            "resources":[{"id":x.resource_id,"name":x.resource.name,"type":x.resource.resource_type,"role":x.role} for x in team.resources if x.resource]})
    resources=db.scalars(select(OperationalResource).where(OperationalResource.active==True).order_by(OperationalResource.resource_type,OperationalResource.name)).all()

    holiday_names, holiday_meta=_combined_holiday_map(db,start_date,end_date); holiday_dates=set(holiday_names)
    school_holidays, school_warnings=school_holidays_for_range(db,start_date,end_date,auto_sync=False)
    school_by_day={}
    for sh in school_holidays:
        for day in _date_range(max(start_date,sh["start_date"]),min(end_date,sh["end_date"])):
            school_by_day.setdefault(day,[]).append(sh["name"])
    absence_rows=_absence_rows(db,start_date,end_date,{x.id for x in employees}); absences=_abwesend_map(db,absence_rows,employees,start_date,end_date)  # seit 1.9.188 mit den Freistellungen des Kalenders
    dates=list(_date_range(start_date,end_date))
    team_capacity={}
    for team in teams:
        members=_team_members_from_master(team,visible_employee_ids); rows={}
        for day in dates:
            cap,available,absent=_day_capacity(members,day,settings,_d(settings.default_travel_hours_per_employee_day),holiday_dates,absences,soll)
            planned=sum((distributions.get(slot.id,{}).get(day,{}).get("planned",Decimal("0")) for slot in visible if slot.team_assignment is not None and slot.team_assignment.team_id==team.id),Decimal("0"))
            util=round_half_up(planned/cap*100 if cap>0 else (Decimal("100") if planned>0 else Decimal("0")),Decimal("0.1"))
            rows[day.isoformat()]={"capacity_hours":cap,"planned_hours":round_hours(planned),"utilization_pct":util,"available_employee_count":len(available),"absences":[{"employee_id":a.employee_id,"name":_employee_name(a.employee),"type":a.absence_type} for a in absent],"holiday":holiday_names.get(day),"school_holidays":school_by_day.get(day,[])}
        team_capacity[str(team.id)]=rows
    employee_capacity={}
    for emp in employees:
        rows={}
        for day in dates:
            soll_tag=soll.get((emp.id,day),Decimal("0"))  # seit 1.9.211 (bis 1.9.210 Wochenstunden je Arbeitstag der Planung)
            if day in holiday_dates or absences.get((emp.id,day)):
                cap=Decimal("0")
            else: cap=_netto(soll_tag,_d(settings.default_travel_hours_per_employee_day))
            planned=Decimal("0")
            for slot in visible:
                dist=distributions.get(slot.id,{}).get(day)
                if not dist or emp.id not in dist.get("available_employee_ids",[]): continue
                total_cap=dist.get("capacity",Decimal("0"))
                if total_cap>0:
                    planned += dist.get("planned",Decimal("0"))*_netto(soll_tag,_slot_travel(slot,settings))/total_cap
            util=round_half_up(planned/cap*100 if cap>0 else (Decimal("100") if planned>0 else Decimal("0")),Decimal("0.1"))
            a=absences.get((emp.id,day))  # 1.9.188 (Nachtrag): eine Freistellung heißt in der schmalen Zelle nur nach ihrem Tag („Heiligabend“)
            rows[day.isoformat()]={"capacity_hours":round_hours(cap),"planned_hours":round_hours(planned),"utilization_pct":util,"absence":(a.kalendertag if isinstance(a,Freistellung) else a.absence_type) if a else None,"holiday":holiday_names.get(day),"school_holidays":school_by_day.get(day,[])}
        employee_capacity[str(emp.id)]=rows
    resource_load={}
    zaehlend=[slot for slot in visible if not geschlossen(slot.preparation.order)]  # seit 1.9.143 (P8), seit 1.9.151 auch abgeschlossene
    for res in resources:
        # seit 1.9.234 aus den Geräten des Einsatzes, an ihren Tagen
        resource_load[str(res.id)]={day.isoformat():sum(1 for slot in zaehlend if any(x.resource_id==res.id and day in _tage_der_zeile(slot,x) for x in slot.geraete)) for day in dates}
    tafel={"settings":settings,"sichtbar":visible_employee_ids,"pausen":pause_begruendungen(db,[slot.preparation.order for slot in visible]),
           "feiertage":set(_combined_holiday_map(db,soll_von,soll_bis)[0])}  # seit 1.9.263: für die leeren Tage aller Einsätze im Bild, eine Abfrage
    slot_dicts=[slot_to_dict(x,conflict_map.get(x.id,[]),db,tafel=tafel) for x in visible]
    pruefungen=_pruefungen(db,{x.id for x in resources})
    _mit_konto,termine_der_personen=personen_termine(db,{x.id for x in employees},start_date,end_date,betrachter_user_id)  # seit 1.9.250

    return {"start_date":start_date,"end_date":end_date,"settings":planning_settings_dict(settings,db),"holidays":holiday_meta,"school_holidays":school_holidays,"school_holiday_warnings":school_warnings,
        "absences":[{"id":x.id,"employee_id":x.employee_id,"employee_name":_employee_name(x.employee),"absence_type":x.absence_type,"absence_category":x.absence_category,"start_date":x.start_date,"end_date":x.end_date,"notes":x.notes} for x in absence_rows],
        "teams":team_rows,
        "employees":[{"id":x.id,"employee_number":x.employee_number,"name":_employee_name(x),"vorname":(x.first_name or _employee_name(x)).strip(),"function":x.profile.function.name if x.profile and x.profile.function else x.job_title,
                     "plantafel":kennzeichen[x.id]} for x in employees],  # seit 1.9.253 das Kennzeichen (1.9.250–1.9.252 „konto“: ohne Kolonne mit Konto hieß „Bauleitung“)
        # seit 1.9.247: die nächste Prüfung (Betriebsmittel) und ob das Gerät einen Kalender hat (eigenes Postfach)
        "resources":[{"id":x.id,"resource_number":x.resource_number,"name":x.name,"type":x.resource_type,"identifier":x.identifier,
                      "pruefung":_geraet_pruefung(pruefungen.get(x.id,[]),berlin_today()),"kalender":bool(x.outlook_mailbox)} for x in resources],
        "slots":slot_dicts,"backlog":rueckstand(db),"conflict_count":sum(1 for x in visible if any(k["type"] not in FAERBT_NICHT for k in conflict_map.get(x.id,[]))),
        "zaehler":tafel_zaehler(slot_dicts),  # seit 1.9.247: Knopf „n Warnungen · n Hinweise“
        "geraete_termine":geraete_termine(db,{x.id for x in resources},start_date,end_date),  # seit 1.9.247: Termine direkt im Kalender eines Geräts
        "personen_termine":termine_der_personen,  # seit 1.9.250: Termine aus dem Kalender der Personen mit Konto (privat „Belegt“, außer für den Besitzer)
        # seit 1.9.247: Abwesenheiten je Person als Zeiträume -- genehmigt, Freistellung, beantragt (Zeilen der Kolonnen und „Personen“)
        "abwesenheiten":abwesenheiten_der_tafel(db,absence_rows,absences,{x.id for x in employees},start_date,end_date,antraege=antraege),
        "team_capacity":team_capacity,"employee_capacity":employee_capacity,"resource_load":resource_load}
