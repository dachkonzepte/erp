from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.employees import apply_employee_payload, employee_to_dict, ensure_default_employee_functions
from app.models import Employee, EmployeeFunction, EmployeeRoleSettings, QuoteEmployeeAssignment, SettingOption
from app.option_settings import ensure_default_option_groups, get_option_group, default_option_value
from app.schemas import EmployeeCreate, CustomerCreate, ProjectCreate, QuoteCreate, QuoteDocumentMetaUpdate
from app.main import create_customer, create_project, create_quote, update_quote_document_meta


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_generic_option_groups_have_units_texts_and_categories():
    db = new_db()
    groups = {g.group_key: g for g in ensure_default_option_groups(db)}
    assert {"units", "quote_payment_terms", "quote_intro_texts", "quote_outro_texts", "customer_categories"} <= set(groups)
    assert default_option_value(db, "units") == "Stück"
    assert default_option_value(db, "quote_payment_terms")


def test_removing_unit_is_not_reseeded_after_group_exists():
    db = new_db()
    ensure_default_option_groups(db)
    group = get_option_group(db, "units")
    row = next(o for o in group.options if o.value == "m³")
    db.delete(row); db.commit()
    ensure_default_option_groups(db)
    group = get_option_group(db, "units")
    assert all(o.value != "m³" for o in group.options)


def test_employee_caseworker_flag_and_quote_assignment():
    db = new_db()
    ensure_default_employee_functions(db)
    function = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == "Büro / Verwaltung"))
    payload = EmployeeCreate(
        employee_number="MA-SB", first_name="Anna", last_name="Büro",
        function_id=function.id, job_title=function.name, employee_group=function.employee_group,
        hourly_wage=None, weekly_hours=Decimal("40"), available_as_caseworker=True, active=True,
    )
    employee = Employee(first_name="Anna", last_name="Büro", employee_group="kaufmaennisch", weekly_hours=Decimal("40"))
    apply_employee_payload(db, employee, payload); db.add(employee); db.commit(); db.refresh(employee)
    role = EmployeeRoleSettings(employee_id=employee.id, available_as_caseworker=True); db.add(role); db.commit()
    assert employee_to_dict(employee, db)["available_as_caseworker"] is True

    customer = create_customer(CustomerCreate(last_name="Kunde Sachbearbeiter"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Projekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="Angebot"), db)
    out = update_quote_document_meta(quote.id, QuoteDocumentMetaUpdate(
        quote_date="2026-08-31", contact_person_employee_id=employee.id,
        payment_terms="14 Tage netto", execution_period=None, internal_note=None,
    ), db)
    assert out.document_meta.contact_person_employee_id == employee.id
    assert out.document_meta.contact_person == "Anna Büro"
    assignment = db.scalar(select(QuoteEmployeeAssignment).where(QuoteEmployeeAssignment.quote_id == quote.id))
    assert assignment.caseworker_employee_id == employee.id


def test_templates_use_global_dropdowns():
    root = Path(__file__).parents[1]
    settings = (root / "app/templates/settings.html").read_text(encoding="utf-8")
    quote = (root / "app/templates/quote_editor.html").read_text(encoding="utf-8")
    employees = (root / "app/templates/master_data_form.html").read_text(encoding="utf-8")
    assert 'data-settings-section="option-lists"' in settings
    assert '/api/settings/option-groups' in settings
    assert "quote_payment_terms" in quote and "quote_intro_texts" in quote and "quote_outro_texts" in quote
    assert "/api/employees/caseworkers" in quote
    assert 'id="availableAsCaseworker"' in employees
