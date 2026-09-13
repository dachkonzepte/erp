from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.employees import effective_planning_visibility, set_planning_visibility
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item, create_team
from app.models import (
    Employee, EmployeeFunction, EmployeeProfile, PlanningSchoolHoliday, Service,
)
from app.orders import create_order_from_quote
from app.planning import (
    automatic_public_holidays, parse_school_holiday_payload, planning_board,
    planning_suggestion, update_planning_settings,
)
from app.schemas import (
    CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate,
    TeamCreate, TeamEmployeeInput,
)
from app.service import persist_project


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_order(db, suffix="v092"):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    if db.scalar(select(Service)) is None:
        persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    customer = create_customer(CustomerCreate(last_name=f"Kalender Kunde {suffix}"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name=f"Kalender Projekt {suffix}"), db)
    quote = create_quote(project.id, QuoteCreate(title=f"Kalender Angebot {suffix}"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    return create_order_from_quote(
        db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None,
    )


def add_employee(db, number, first, last, function_name, group="gewerblich", weekly=40):
    fn = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == function_name))
    if fn is None:
        fn = EmployeeFunction(name=function_name, employee_group=group, sort_order=500, active=True)
        db.add(fn); db.flush()
    emp = Employee(
        employee_number=number, first_name=first, last_name=last, employee_group=group,
        hourly_wage=Decimal("20") if group == "gewerblich" else None,
        weekly_hours=Decimal(str(weekly)), active=True,
    )
    db.add(emp); db.flush()
    db.add(EmployeeProfile(employee_id=emp.id, function_id=fn.id)); db.commit(); db.refresh(emp)
    return emp


def test_office_and_warehouse_default_hidden_but_can_be_enabled():
    db = db_session()
    office = add_employee(db, "M-BUERO", "Anna", "Office", "Büro / Verwaltung", "kaufmaennisch")
    warehouse = add_employee(db, "M-LAGER", "Lars", "Lager", "Lagerist", "gewerblich")
    roofer = add_employee(db, "M-DACH", "Max", "Dach", "Dachdecker Geselle", "gewerblich")
    assert effective_planning_visibility(db, office) is False
    assert effective_planning_visibility(db, warehouse) is False
    assert effective_planning_visibility(db, roofer) is True
    set_planning_visibility(db, warehouse, True); db.commit()
    assert effective_planning_visibility(db, warehouse) is True


def test_hidden_employee_is_not_counted_in_planning_suggestion_capacity():
    db = db_session(); order = setup_order(db)
    visible = add_employee(db, "M-VIS", "Vera", "Dach", "Dachdecker Geselle")
    hidden = add_employee(db, "M-HID", "Lars", "Lager", "Lagerist")
    team = create_team(TeamCreate(
        team_number="K-V092", name="Kolonne Sichtbarkeit",
        employees=[TeamEmployeeInput(employee_id=visible.id, role="Geselle"), TeamEmployeeInput(employee_id=hidden.id, role="Lager")],
        resources=[],
    ), db)
    update_planning_settings(
        db, daily_work_hours=Decimal("8"), default_travel_hours_per_employee_day=Decimal("0.5"),
        monday=True, tuesday=True, wednesday=True, thursday=True, friday=True, saturday=False, sunday=False,
        federal_state_code="NW", auto_public_holidays=False, show_school_holidays=True,
    )
    result = planning_suggestion(db, order_id=order.id, team_id=team.id, start_date=date(2026, 9, 7))
    assert result["employee_count"] == 1
    assert result["full_team_daily_capacity"] == Decimal("7.50")


def test_nrw_public_holidays_are_generated_and_reduce_capacity():
    db = db_session(); order = setup_order(db, "holiday")
    emp = add_employee(db, "M-HOL", "Heinz", "Dach", "Dachdecker Geselle")
    team = create_team(TeamCreate(
        team_number="K-HOL", name="Kolonne Feiertag",
        employees=[TeamEmployeeInput(employee_id=emp.id, role="Geselle")], resources=[],
    ), db)
    holidays = automatic_public_holidays("NW", [2026])
    assert holidays[date(2026, 6, 4)] == "Fronleichnam"
    assert date(2026, 10, 31) not in holidays  # Reformationstag ist in NRW kein gesetzlicher Feiertag.
    update_planning_settings(
        db, daily_work_hours=Decimal("8"), default_travel_hours_per_employee_day=Decimal("0"),
        monday=True, tuesday=True, wednesday=True, thursday=True, friday=True, saturday=False, sunday=False,
        federal_state_code="NW", auto_public_holidays=True, show_school_holidays=True,
    )
    result = planning_suggestion(db, order_id=order.id, team_id=team.id, start_date=date(2026, 6, 4))
    holiday_row = next(x for x in result["days"] if x["date"] == date(2026, 6, 4))
    assert holiday_row["holiday"] == "Fronleichnam"
    assert holiday_row["capacity_hours"] == Decimal("0")


def test_school_holiday_payload_is_cached_as_local_inclusive_dates():
    payload = [{
        "name": "sommerferien",
        "start": "2026-07-19T22:00:00.000Z",
        "end": "2026-09-01T22:00:00.000Z",
    }]
    rows = parse_school_holiday_payload(payload, "NW", 2026)
    assert rows == [{
        "state_code": "NW", "calendar_year": 2026, "name": "Sommerferien",
        "start_date": date(2026, 7, 20), "end_date": date(2026, 9, 1),
    }]


def test_school_holidays_are_visual_only_and_do_not_reduce_capacity():
    db = db_session(); order = setup_order(db, "school")
    emp = add_employee(db, "M-SCH", "Susi", "Dach", "Dachdecker Geselle")
    team = create_team(TeamCreate(
        team_number="K-SCH", name="Kolonne Ferien",
        employees=[TeamEmployeeInput(employee_id=emp.id, role="Geselle")], resources=[],
    ), db)
    update_planning_settings(
        db, daily_work_hours=Decimal("8"), default_travel_hours_per_employee_day=Decimal("0"),
        monday=True, tuesday=True, wednesday=True, thursday=True, friday=True, saturday=False, sunday=False,
        federal_state_code="NW", auto_public_holidays=False, show_school_holidays=True,
    )
    db.add(PlanningSchoolHoliday(
        state_code="NW", calendar_year=2026, name="Sommerferien",
        start_date=date(2026, 9, 7), end_date=date(2026, 9, 8), source="test",
    )); db.commit()
    from app.planning import create_slot
    create_slot(db, order_id=order.id, team_id=team.id, start_date=date(2026, 9, 7), end_date=date(2026, 9, 11), planned_hours=Decimal("8"), travel_hours_per_employee_day=Decimal("0"))
    board = planning_board(db, date(2026, 9, 7), date(2026, 9, 11))
    assert any(x["name"] == "Sommerferien" and x["start_date"] == date(2026, 9, 7) for x in board["school_holidays"])
    day = board["team_capacity"][str(team.id)]["2026-09-07"]
    assert day["capacity_hours"] == Decimal("8.00")
    assert day["school_holidays"] == ["Sommerferien"]


def test_v092_ui_contains_state_school_holiday_and_employee_visibility_controls():
    root = Path(__file__).parents[1]
    planning = (root / "app/templates/planning.html").read_text(encoding="utf-8")
    settings = (root / "app/templates/settings.html").read_text(encoding="utf-8")
    # Mitarbeiter-Anlegen/-Bearbeiten lebt seit 1.3.30 wieder auf master_data_form.html (die
    # zwischenzeitliche 1.3.26-Auslagerung auf /employees wurde zurückgenommen, siehe CLAUDE.md
    # "Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher").
    employee = (root / "app/templates/master_data_form.html").read_text(encoding="utf-8")
    assert "Schulferien nur visuell" in planning and "school-holiday" in planning
    assert "Bundesland" in settings and "planningState" in settings and "Ferien jetzt aktualisieren" in settings
    assert "In Plantafel anzeigen / Kapazität berücksichtigen" in employee
