from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item, create_team
from app.models import Employee, EmployeeAbsence, PlanningHoliday, PlanningSettings, Service
from app.orders import create_order_from_quote, load_order
from app.planning import planning_suggestion, create_slot, planning_board, update_planning_settings
from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate, TeamCreate, TeamEmployeeInput
from app.service import persist_project


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_120h_order_and_team(db):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    customer = create_customer(CustomerCreate(last_name="Kapazität Kunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Kapazität Projekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="Kapazität Angebot"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    order = create_order_from_quote(db, quote.id, order_date=date(2026,9,1), execution_start=None, execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    loaded=load_order(db,order.id)
    item=loaded.items[0]
    item.calculation_snapshot.site_time_minutes=Decimal("720")  # 12 h/EH × 10 EH = 120 h
    item.calculation_snapshot.workshop_time_minutes=Decimal("0")
    db.commit()
    employees=[]
    for i in range(3):
        e=Employee(employee_number=f"M-KAP-{i+1}",first_name=f"MA{i+1}",last_name="Kapazität",employee_group="gewerblich",hourly_wage=Decimal("20"),weekly_hours=Decimal("40"),active=True)
        db.add(e); employees.append(e)
    db.commit()
    team=create_team(TeamCreate(team_number="K-1",name="Kolonne 1",employees=[TeamEmployeeInput(employee_id=e.id,role="Dachdecker") for e in employees],resources=[]),db)
    return order,team,employees


def test_example_120_hours_three_employees_8h_minus_05h_is_533_teamdays():
    db=db_session(); order,team,_=setup_120h_order_and_team(db)
    update_planning_settings(db,daily_work_hours=Decimal("8"),default_travel_hours_per_employee_day=Decimal("0.5"),monday=True,tuesday=True,wednesday=True,thursday=True,friday=True,saturday=False,sunday=False)
    s=planning_suggestion(db,order_id=order.id,team_id=team.id,start_date=date(2026,9,7))
    assert s["planned_hours"] == Decimal("120.00")
    assert s["full_team_daily_capacity"] == Decimal("22.50")
    assert s["required_team_days_decimal"] == Decimal("5.33")
    assert s["calendar_workdays_needed"] == 6
    assert s["suggested_start"] == date(2026,9,7)
    assert s["suggested_end"] == date(2026,9,14)  # Wochenende wird übersprungen


def test_absence_and_holiday_reduce_capacity_and_shift_suggested_end():
    db=db_session(); order,team,employees=setup_120h_order_and_team(db)
    update_planning_settings(db,daily_work_hours=Decimal("8"),default_travel_hours_per_employee_day=Decimal("0.5"),monday=True,tuesday=True,wednesday=True,thursday=True,friday=True,saturday=False,sunday=False)
    db.add(EmployeeAbsence(employee_id=employees[0].id,absence_type="Urlaub",start_date=date(2026,9,7),end_date=date(2026,9,7)))
    db.add(PlanningHoliday(holiday_date=date(2026,9,8),name="Betriebsfrei",active=True)); db.commit()
    s=planning_suggestion(db,order_id=order.id,team_id=team.id,start_date=date(2026,9,7))
    assert s["days"][0]["available_employee_count"] == 2
    assert any(x["holiday"] == "Betriebsfrei" for x in s["days"])
    assert s["suggested_end"] > date(2026,9,14)


def test_capacity_conflict_if_slot_period_is_too_short():
    db=db_session(); order,team,_=setup_120h_order_and_team(db)
    update_planning_settings(db,daily_work_hours=Decimal("8"),default_travel_hours_per_employee_day=Decimal("0.5"),monday=True,tuesday=True,wednesday=True,thursday=True,friday=True,saturday=False,sunday=False)
    slot=create_slot(db,order_id=order.id,team_id=team.id,start_date=date(2026,9,7),end_date=date(2026,9,11),planned_hours=Decimal("120"),travel_hours_per_employee_day=Decimal("0.5"))
    board=planning_board(db,date(2026,9,7),date(2026,9,20))
    row=next(x for x in board["slots"] if x["id"]==slot.id)
    cap=[c for c in row["conflicts"] if c["type"]=="capacity"]
    assert cap and cap[0]["shortfall_hours"] == Decimal("7.50")
    assert board["team_capacity"][str(team.id)]["2026-09-07"]["capacity_hours"] == Decimal("22.50")


def test_v091_ui_settings_and_absence_types_are_present():
    root=Path(__file__).parents[1]
    planning=(root/"app/templates/planning.html").read_text(encoding="utf-8")
    settings=(root/"app/templates/settings.html").read_text(encoding="utf-8")
    options=(root/"app/option_settings.py").read_text(encoding="utf-8")
    assert "Planungsvorschlag" in planning and "Abwesenheiten" in planning and "utilization_pct" in planning
    assert "Plantafel & Kapazität" in settings and "planningDailyHours" in settings
    assert '"absence_types"' in options
