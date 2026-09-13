from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item, create_resource, create_team
from app.models import Employee, PlanningSlot, Service, WorkPreparation
from app.orders import create_order_from_quote
from app.planning import create_slot, delete_slot, planning_board, update_slot
from app.schemas import (
    CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate,
    OperationalResourceCreate, TeamCreate, TeamEmployeeInput, TeamResourceInput,
)
from app.service import persist_project


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_order(db, suffix="1"):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    if db.scalar(select(Service)) is None:
        persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    customer = create_customer(CustomerCreate(last_name=f"Plan Kunde {suffix}"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name=f"Plan Projekt {suffix}"), db)
    quote = create_quote(project.id, QuoteCreate(title=f"Plan Angebot {suffix}"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    return create_order_from_quote(
        db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None,
    )


def setup_shared_teams(db):
    emp = Employee(employee_number="M-PLAN", first_name="Max", last_name="Plan", employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True)
    db.add(emp); db.commit()
    res = create_resource(OperationalResourceCreate(resource_number="F-PLAN", resource_type="Fahrzeug", name="Sprinter Planung", identifier="HS-PL 1"), db)
    team1 = create_team(TeamCreate(team_number="K-1", name="Kolonne 1", employees=[TeamEmployeeInput(employee_id=emp.id, role="Vorarbeiter")], resources=[TeamResourceInput(resource_id=res.id, role="Fahrzeug")]), db)
    team2 = create_team(TeamCreate(team_number="K-2", name="Kolonne 2", employees=[TeamEmployeeInput(employee_id=emp.id, role="Aushilfe")], resources=[TeamResourceInput(resource_id=res.id, role="Fahrzeug")]), db)
    return emp, res, team1, team2


def test_planning_board_detects_team_employee_and_resource_conflicts():
    db = db_session(); order1 = setup_order(db, "1"); order2 = setup_order(db, "2"); emp, res, team1, team2 = setup_shared_teams(db)
    s1 = create_slot(db, order_id=order1.id, team_id=team1.id, start_date=date(2026,9,7), end_date=date(2026,9,11))
    s2 = create_slot(db, order_id=order2.id, team_id=team2.id, start_date=date(2026,9,9), end_date=date(2026,9,12))
    data = planning_board(db, date(2026,9,7), date(2026,9,20))
    by_id = {x["id"]: x for x in data["slots"]}
    kinds1 = {x["type"] for x in by_id[s1.id]["conflicts"]}
    kinds2 = {x["type"] for x in by_id[s2.id]["conflicts"]}
    assert "employee" in kinds1 and "resource" in kinds1
    assert "employee" in kinds2 and "resource" in kinds2
    assert data["conflict_count"] == 2
    assert any(x["id"] == emp.id for x in data["employees"])
    assert any(x["id"] == res.id for x in data["resources"])


def test_same_team_overlap_is_conflict_and_unplanned_backlog_disappears_after_planning():
    db = db_session(); order1 = setup_order(db, "1"); order2 = setup_order(db, "2"); _, _, team1, _ = setup_shared_teams(db)
    before = planning_board(db, date(2026,9,1), date(2026,9,20))
    assert {x["order_id"] for x in before["backlog"]} >= {order1.id, order2.id}
    s1 = create_slot(db, order_id=order1.id, team_id=team1.id, start_date=date(2026,9,7), end_date=date(2026,9,10))
    create_slot(db, order_id=order2.id, team_id=team1.id, start_date=date(2026,9,10), end_date=date(2026,9,12))
    after = planning_board(db, date(2026,9,1), date(2026,9,20))
    assert order1.id not in {x["order_id"] for x in after["backlog"]}
    row = next(x for x in after["slots"] if x["id"] == s1.id)
    assert any(x["type"] == "team" for x in row["conflicts"])


def test_planning_slot_updates_work_preparation_dates_and_can_switch_team():
    db = db_session(); order = setup_order(db); _, _, team1, team2 = setup_shared_teams(db)
    slot = create_slot(db, order_id=order.id, team_id=team1.id, start_date=date(2026,9,7), end_date=date(2026,9,11))
    prep = db.get(WorkPreparation, slot.preparation_id)
    assert prep.planned_start == date(2026,9,7) and prep.planned_end == date(2026,9,11)
    moved = update_slot(db, slot.id, team_id=team2.id, start_date=date(2026,9,14), end_date=date(2026,9,18), status="bestaetigt", notes="verschoben")
    assert moved.team_assignment.team_id == team2.id
    prep = db.get(WorkPreparation, slot.preparation_id)
    assert prep.planned_start == date(2026,9,14) and prep.planned_end == date(2026,9,18)
    delete_slot(db, slot.id)
    prep = db.get(WorkPreparation, slot.preparation_id)
    assert prep.planned_start is None and prep.planned_end is None


def test_multiple_slots_define_overall_work_preparation_period():
    db = db_session(); order = setup_order(db); _, _, team1, team2 = setup_shared_teams(db)
    a = create_slot(db, order_id=order.id, team_id=team1.id, start_date=date(2026,9,7), end_date=date(2026,9,9))
    b = create_slot(db, order_id=order.id, team_id=team2.id, start_date=date(2026,9,14), end_date=date(2026,9,18))
    prep = db.get(WorkPreparation, a.preparation_id)
    assert prep.planned_start == date(2026,9,7) and prep.planned_end == date(2026,9,18)
    delete_slot(db, a.id)
    prep = db.get(WorkPreparation, b.preparation_id)
    assert prep.planned_start == date(2026,9,14) and prep.planned_end == date(2026,9,18)


def test_v09_planning_ui_and_routes_exist():
    root = Path(__file__).parents[1]
    html = (root / "app/templates/planning.html").read_text(encoding="utf-8")
    main = (root / "app/main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root / "app/routers").glob("*.py")))
    models = (root / "app/models.py").read_text(encoding="utf-8")
    assert "Kolonnen" in html and "Mitarbeiter" in html and "Fahrzeuge / Maschinen" in html
    assert "ondrop=\"dropSlot" in html and "Nicht eingeplant" in html
    assert '@router.get("/planning"' in main and '@router.get("/api/planning")' in main
    assert "class PlanningSlot" in models

def test_planned_team_assignment_cannot_be_removed_from_work_preparation():
    from fastapi import HTTPException
    from app.main import remove_work_preparation_team
    db = db_session(); order = setup_order(db); _, _, team1, _ = setup_shared_teams(db)
    slot = create_slot(db, order_id=order.id, team_id=team1.id, start_date=date(2026,9,7), end_date=date(2026,9,11))
    try:
        remove_work_preparation_team(slot.team_assignment_id, db)
        assert False, "geplanter Teameinsatz darf nicht entfernt werden"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Plantafel" in exc.detail
