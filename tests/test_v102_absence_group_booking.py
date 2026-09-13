from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.absence_requests import create_request, review_request
from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item
from app.models import Employee, EmployeeAbsence, Service, Team, TeamEmployee, TimeEntry, TimeEntryGroupMember
from app.orders import create_order_from_quote
from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate
from app.service import persist_project
from app.time_tracking import create_group_manual_entry, start_group_timer, stop_group_timer, active_entry


def db_session():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_order(db):
    sample=Path(__file__).parents[1]/"sample_data"/"Thiefes.xml"
    persist_project(db,parse_leistungen_dach_xml(sample.read_bytes()),"Thiefes.xml")
    customer=create_customer(CustomerCreate(last_name="Gruppenkunde"),db)
    project=create_project(ProjectCreate(customer_id=customer.id,name="Gruppenprojekt"),db)
    quote=create_quote(project.id,QuoteCreate(title="Gruppenangebot"),db)
    service=db.scalar(select(Service).where(Service.external_id=="L600109101011"))
    add_quote_item(quote.id,QuoteItemCreate(service_id=service.id,quantity=Decimal("10")),db)
    return create_order_from_quote(db,quote.id,order_date=date(2026,9,1),execution_start=None,execution_end=None,caseworker_employee_id=None,project_manager_employee_id=None,payment_terms=None,remarks=None)


def employees_and_team(db):
    emps=[]
    for idx,name in enumerate(["Max","Moritz","Mia"],1):
        e=Employee(employee_number=f"G-{idx}",first_name=name,last_name="Team",employee_group="gewerblich",hourly_wage=Decimal("20"),weekly_hours=Decimal("40"),active=True)
        db.add(e);db.flush();emps.append(e)
    team=Team(team_number="K-GRP",name="Kolonne Gruppe",active=True);db.add(team);db.flush()
    for e in emps: db.add(TeamEmployee(team_id=team.id,employee_id=e.id,role="Geselle"))
    outsider=Employee(employee_number="G-X",first_name="Otto",last_name="Extern",employee_group="gewerblich",hourly_wage=Decimal("20"),weekly_hours=Decimal("40"),active=True);db.add(outsider)
    db.commit();return emps,team,outsider


def test_absence_request_only_affects_planning_after_approval():
    db=db_session();emps,team,_=employees_and_team(db);emp=emps[0]
    req=create_request(db,employee_id=emp.id,absence_type="Urlaub",start_date=date(2026,9,14),end_date=date(2026,9,18),notes="Familienurlaub")
    assert req.status=="pending"
    assert db.scalar(select(EmployeeAbsence).where(EmployeeAbsence.employee_id==emp.id)) is None
    approved=review_request(db,req.id,decision="approved",reviewed_by_user_id=None,review_notes="Freigegeben")
    assert approved.status=="approved" and approved.approved_absence_id
    absence=db.get(EmployeeAbsence,approved.approved_absence_id)
    assert absence.start_date==date(2026,9,14) and absence.absence_type=="Urlaub"


def test_rejected_absence_request_creates_no_absence():
    db=db_session();emps,_,_=employees_and_team(db);emp=emps[0]
    req=create_request(db,employee_id=emp.id,absence_type="Freizeitausgleich",start_date=date(2026,9,21),end_date=date(2026,9,21))
    result=review_request(db,req.id,decision="rejected",reviewed_by_user_id=None,review_notes="Baustelle")
    assert result.status=="rejected"
    assert db.scalar(select(EmployeeAbsence).where(EmployeeAbsence.employee_id==emp.id)) is None


def test_group_manual_booking_creates_person_specific_entries():
    db=db_session();order=setup_order(db);emps,team,_=employees_and_team(db)
    group=create_group_manual_entry(db,employee_ids=[e.id for e in emps],team_id=team.id,actor_employee_id=emps[0].id,is_admin=False,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("8"),entry_type="site",created_by_user_id=None)
    rows=db.scalars(select(TimeEntry).where(TimeEntry.order_id==order.id)).all()
    links=db.scalars(select(TimeEntryGroupMember).where(TimeEntryGroupMember.group_id==group.id)).all()
    assert len(rows)==3 and len(links)==3
    assert {r.employee_id for r in rows}=={e.id for e in emps}
    assert all(r.hours==Decimal("8.0000") and r.source=="group_manual" for r in rows)


def test_group_timer_starts_and_stops_all_members():
    db=db_session();order=setup_order(db);emps,team,_=employees_and_team(db)
    group=start_group_timer(db,employee_ids=[e.id for e in emps],team_id=team.id,actor_employee_id=emps[0].id,is_admin=False,order_id=order.id,entry_type="site",started_at=datetime(2026,9,7,7,0))
    assert group.status=="running"
    assert all(active_entry(db,e.id) is not None for e in emps)
    group=stop_group_timer(db,group.id,ended_at=datetime(2026,9,7,16,0),break_minutes=30)
    assert group.status=="booked" and group.hours==Decimal("8.2500")
    assert all(active_entry(db,e.id) is None for e in emps)


def test_employee_cannot_group_book_for_outsider_or_without_self():
    db=db_session();order=setup_order(db);emps,team,outsider=employees_and_team(db)
    with pytest.raises(ValueError,match="selbst enthalten"):
        create_group_manual_entry(db,employee_ids=[emps[1].id],team_id=team.id,actor_employee_id=emps[0].id,is_admin=False,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("8"))
    with pytest.raises(ValueError,match="ausgewählten Teams"):
        create_group_manual_entry(db,employee_ids=[emps[0].id,outsider.id],team_id=team.id,actor_employee_id=emps[0].id,is_admin=False,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("8"))


def test_mobile_ui_contains_group_and_absence_request_workflows():
    root=Path(__file__).parents[1]
    html=(root/"app/templates/time_tracking.html").read_text(encoding="utf-8")
    main=(root/"app/main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root/"app/routers").glob("*.py")))
    assert "Gruppenbuchung" in html and "Abwesenheitsanträge" in html
    assert "/api/time-entry-groups/start" in main and "/api/absence-requests" in main
    assert re.match(r"^\d+\.\d+\.\d+$", (root/"VERSION").read_text(encoding="utf-8").strip())
