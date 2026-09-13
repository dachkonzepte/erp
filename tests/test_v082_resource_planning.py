from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    Employee, OperationalResource, Supplier, Team, TeamEmployee, TeamResource,
    WorkPreparationMaterialSupplier, WorkPreparationTeamAssignment,
    WorkPreparationTeamEmployee, WorkPreparationTeamResource,
)
from app.main import (
    create_customer, create_project, create_quote, add_quote_item,
    create_supplier, create_resource, create_team,
    assign_work_preparation_team, update_work_preparation_material,
)
from app.schemas import (
    CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate,
    SupplierCreate, OperationalResourceCreate, TeamCreate, TeamEmployeeInput, TeamResourceInput,
    WorkPreparationTeamAssign, WorkPreparationMaterialUpdateV082,
)
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.service import persist_project
from app.models import Service
from app.orders import create_order_from_quote
from app.work_preparation import ensure_preparation, preparation_to_dict, refresh_preparation_materials


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_order(db):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    customer = create_customer(CustomerCreate(last_name="Ressourcen Kunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Ressourcen Projekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="Ressourcen Angebot"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    return create_order_from_quote(db, quote.id, order_date=date(2026,9,1), execution_start=None, execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)


def test_team_snapshots_employee_and_resource_for_work_preparation():
    db = db_session(); order = setup_order(db); ensure_preparation(db, order.id)
    emp = Employee(employee_number="M-1", first_name="Max", last_name="Dach", employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True)
    db.add(emp); db.commit()
    res = create_resource(OperationalResourceCreate(resource_number="F-1", resource_type="Fahrzeug", name="Sprinter 1", identifier="HS-DK 1"), db)
    team = create_team(TeamCreate(team_number="K-1", name="Kolonne 1", employees=[TeamEmployeeInput(employee_id=emp.id, role="Vorarbeiter")], resources=[TeamResourceInput(resource_id=res.id, role="Baustellenfahrzeug")]), db)
    data = assign_work_preparation_team(order.id, WorkPreparationTeamAssign(team_id=team.id), db)
    assert len(data["teams"]) == 1
    assert data["teams"][0]["employees"][0]["employee_name"] == "Max Dach"
    assert data["teams"][0]["resources"][0]["resource_name"] == "Sprinter 1"
    # Stammteam später ändern: Projekteinsatz bleibt Snapshot.
    db.query(TeamEmployee).filter(TeamEmployee.team_id == team.id).delete()
    db.query(TeamResource).filter(TeamResource.team_id == team.id).delete(); db.commit()
    data2 = preparation_to_dict(db, ensure_preparation(db, order.id))
    assert data2["teams"][0]["employees"][0]["employee_name"] == "Max Dach"
    assert data2["teams"][0]["resources"][0]["resource_name"] == "Sprinter 1"


def test_supplier_dropdown_relation_survives_material_refresh():
    db = db_session(); order = setup_order(db); prep = ensure_preparation(db, order.id)
    supplier = create_supplier(SupplierCreate(supplier_number="L-1", name="Dachhandel GmbH"), db)
    data = preparation_to_dict(db, prep)
    mat = data["materials"][0]
    updated = update_work_preparation_material(mat["id"], WorkPreparationMaterialUpdateV082(planned_quantity=mat["planned_quantity"], status="bestellt", supplier_id=supplier.id, notes="bestellt"), db)
    row = next(x for x in updated["materials"] if x["id"] == mat["id"])
    assert row["supplier_id"] == supplier.id
    assert row["supplier"] == "Dachhandel GmbH"
    refresh_preparation_materials(db, order.id)
    data2 = preparation_to_dict(db, ensure_preparation(db, order.id))
    assert any(x["supplier_id"] == supplier.id and x["supplier"] == "Dachhandel GmbH" for x in data2["materials"])


def test_planned_hours_are_automatic_order_calculation_hours():
    db = db_session(); order = setup_order(db); data = preparation_to_dict(db, ensure_preparation(db, order.id))
    assert data["planned_total_hours"] > 0
    assert data["actual_total_hours"] == Decimal("0.00")
    assert data["hours_variance"] == -data["planned_total_hours"]


def test_v082_ui_contains_new_masterdata_and_delivery_note_flow():
    root=Path(__file__).parents[1]
    master=(root/'app/templates/master_data.html').read_text(encoding='utf-8')
    prep=(root/'app/templates/work_preparation.html').read_text(encoding='utf-8')
    main=(root/'app/main.py').read_text(encoding='utf-8') + "".join(p.read_text(encoding="utf-8") for p in sorted((root/'app/routers').glob("*.py")))
    assert 'Kolonnen / Teams' in master and 'Fuhrpark & Maschinen' in master and 'Lieferanten' in master
    assert 'Lieferschein einscannen / hochladen' in prep
    assert 'Planstunden werden nicht manuell gepflegt' in prep
    assert '/work-preparation/delivery-notes' in main and '/work-preparation/teams' in main
