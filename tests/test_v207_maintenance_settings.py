from datetime import date, timedelta

from app.maintenance_contracts import (
    check_due_contracts_and_create_reminders, create_contract, get_or_create_maintenance_settings,
    list_contracts, update_maintenance_settings,
)
from app.models import Employee
from app.tasks import list_tasks
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v153_mahnwesen import db_session


def test_settings_default_to_thirty_days_lead_time():
    db = db_session()
    settings = get_or_create_maintenance_settings(db)
    assert settings.reminder_lead_days == 30
    assert settings.default_responsible_employee_id is None


def test_update_settings_rejects_negative_lead_days():
    db = db_session()
    try:
        update_maintenance_settings(db, -1, False, None)
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_contract_due_soon_within_lead_time_shows_as_due():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "In zwei Tagen", 12, date.today() + timedelta(days=2))
    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[contract["id"]]["is_due"] is True  # 2 Tage <= Standard-Vorlaufzeit von 30 Tagen


def test_lowering_lead_time_hides_a_contract_again():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "In zwei Tagen", 12, date.today() + timedelta(days=2))
    update_maintenance_settings(db, 1, False, None)  # Vorlaufzeit auf 1 Tag reduziert
    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[contract["id"]]["is_due"] is False


def test_reminder_uses_lead_time_threshold_not_just_overdue():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    emp = Employee(first_name="Erika", last_name="Eins", employee_group="angestellt", active=True)
    db.add(emp); db.commit()
    contract = create_contract(db, customer.id, prop.id, "In zwei Tagen", 12, date.today() + timedelta(days=2),
                                responsible_employee_id=emp.id)
    reminded = check_due_contracts_and_create_reminders(db)
    assert reminded == [contract["id"]]
    assert len(list_tasks(db, employee_id=emp.id)) == 1


def test_reminder_falls_back_to_default_responsible_employee():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    default_emp = Employee(first_name="Standard", last_name="Sachbearbeiter", employee_group="angestellt", active=True)
    db.add(default_emp); db.commit()
    update_maintenance_settings(db, 30, False, default_emp.id)

    contract = create_contract(db, customer.id, prop.id, "Ohne eigenen Zustaendigen", 12, date.today())
    check_due_contracts_and_create_reminders(db)

    tasks = list_tasks(db, employee_id=default_emp.id)
    assert len(tasks) == 1
    assert tasks[0]["source_url"] == f"/maintenance-contracts/{contract['id']}"


def test_contracts_own_responsible_employee_wins_over_default():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    own_emp = Employee(first_name="Eigen", last_name="Zustaendig", employee_group="angestellt", active=True)
    default_emp = Employee(first_name="Standard", last_name="Sachbearbeiter", employee_group="angestellt", active=True)
    db.add_all([own_emp, default_emp]); db.commit()
    update_maintenance_settings(db, 30, False, default_emp.id)

    create_contract(db, customer.id, prop.id, "Mit eigenem Zustaendigen", 12, date.today(),
                     responsible_employee_id=own_emp.id)
    check_due_contracts_and_create_reminders(db)

    assert len(list_tasks(db, employee_id=own_emp.id)) == 1
    assert len(list_tasks(db, employee_id=default_emp.id)) == 0


def test_maintenance_settings_endpoints_return_403_when_module_disabled():
    from app.modules import set_module_enabled
    from app.routers.maintenance_contracts import get_maintenance_settings, put_maintenance_settings
    from app.schemas import MaintenanceSettingsUpdate

    db = db_session()
    set_module_enabled(db, "wartungen", False)

    def expect_403(fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
            assert False, "sollte HTTPException auslösen"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403

    expect_403(get_maintenance_settings, db=db)
    expect_403(put_maintenance_settings, MaintenanceSettingsUpdate(reminder_lead_days=30), db=db)
