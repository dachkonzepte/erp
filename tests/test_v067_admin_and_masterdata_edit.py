from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.database import Base
from app.models import AppUser, AuditLog, Customer, Property, Employee
from app.auth import COOKIE_NAME, hash_password, make_cookie
from app.main import update_app_user, delete_app_user, update_property, get_employee, update_employee
from app.schemas import AppUserUpdate, PropertyUpdate, EmployeeUpdate
from app.employees import ensure_default_employee_functions
from app.audit import set_audit_context, reset_audit_context


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def request_for(user_id: int, method="PUT", path="/api/test"):
    cookie = f"{COOKIE_NAME}={make_cookie(user_id)}".encode()
    return Request({"type":"http","method":method,"path":path,"headers":[(b"cookie",cookie)],"query_string":b"","server":("test",80),"client":("test",1234),"scheme":"http"})


def test_admin_can_edit_and_delete_other_user():
    db = new_db()
    admin = AppUser(username="admin", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    other = AppUser(username="user1", display_name="User Eins", role="user", active=True, password_hash=hash_password("Passwort123"))
    db.add_all([admin, other]); db.commit()
    updated = update_app_user(other.id, AppUserUpdate(username="user.neu", display_name="User Neu", employee_id=None, role="admin", active=True, new_password="NeuesPasswort123"), db, admin)
    assert updated.username == "user.neu"
    assert updated.role == "admin"
    assert delete_app_user(other.id, db, admin) == {"ok": True}
    assert db.get(AppUser, other.id) is None


def test_admin_cannot_delete_self_or_remove_last_admin():
    db = new_db()
    admin = AppUser(username="admin", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()
    try:
        delete_app_user(admin.id, db, admin)
        assert False, "self delete should fail"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    try:
        update_app_user(admin.id, AppUserUpdate(username="admin", display_name="Admin", employee_id=None, role="user", active=True, new_password=None), db, admin)
        assert False, "last admin demotion should fail"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409


def test_property_and_employee_can_be_edited_and_are_audited():
    db = new_db()
    token = set_audit_context(type("U",(),{"id":1,"display_name":"Administrator","username":"admin"})(), None)
    try:
        c1 = Customer(name="Kunde A", last_name="Kunde A"); c2 = Customer(name="Kunde B", last_name="Kunde B")
        db.add_all([c1,c2]); db.commit()
        prop = Property(customer_id=c1.id, name="Altobjekt", city="Aachen")
        db.add(prop); db.commit()
        updated_prop = update_property(prop.id, PropertyUpdate(customer_id=c2.id, name="Neuobjekt", street="Neue Str. 1", postal_code="52531", city="Übach-Palenberg", notes="bearbeitet"), db)
        assert updated_prop.customer_id == c2.id and updated_prop.name == "Neuobjekt"

        fn = ensure_default_employee_functions(db)[0]
        emp = Employee(first_name="Max", last_name="Alt", employee_group="gewerblich", hourly_wage=20, weekly_hours=40, active=True)
        db.add(emp); db.commit()
        payload = EmployeeUpdate(employee_number="MA-1", first_name="Max", last_name="Neu", function_id=fn.id, employee_group=fn.employee_group, hourly_wage=22, weekly_hours=39, street="Mitarbeiterstr. 1", postal_code="52531", city="Übach-Palenberg", country="Deutschland", phone="02451", mobile="0170", email="max@example.de", birthday=None, important_info="Hinweis", available_as_caseworker=True, active=True)
        out = update_employee(emp.id, payload, db)
        assert out["last_name"] == "Neu" and out["available_as_caseworker"] is True
        assert get_employee(emp.id, db)["email"] == "max@example.de"
    finally:
        reset_audit_context(token)
    assert db.scalar(select(AuditLog).where(AuditLog.entity_type == "Objekt", AuditLog.action == "geändert")) is not None
    assert db.scalar(select(AuditLog).where(AuditLog.entity_type == "Mitarbeiter", AuditLog.action == "geändert")) is not None


def test_edit_links_and_admin_ui_exist():
    root=Path(__file__).parents[1]
    master=(root/'app/templates/master_data.html').read_text(encoding="utf-8")
    form=(root/'app/templates/master_data_form.html').read_text(encoding="utf-8")
    users=(root/'app/templates/users.html').read_text(encoding="utf-8")
    users_router=(root/'app/routers/users.py').read_text(encoding="utf-8")
    employees_router=(root/'app/routers/employees.py').read_text(encoding="utf-8")
    # Seit 1.2.18 zeigt die generische Stammdatenmaske für Objekte nicht mehr auf die eigene
    # (flache) Bearbeitungsmaske, sondern auf die neue, reichere Objektseite /properties/{id}
    # (siehe app/templates/property.html) -- kein Umbau des generischen Mechanismus für andere
    # Stammdatentypen, siehe CLAUDE.md.
    assert '/properties/${x.id}' in master
    # Mitarbeiter-Bearbeiten lebt seit 1.3.30 wieder über master_data_form.html (die
    # zwischenzeitliche 1.3.26-Auslagerung auf /employees wurde zurückgenommen, siehe CLAUDE.md
    # "Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher") -- master_data.html verlinkt
    # jede Mitarbeiterzeile direkt auf ihre Bearbeiten-Seite, wie bei Teams/Lieferanten/usw.
    assert '/master-data/employees/${x.id}/edit' in master
    assert 'employeeForm(' in form
    assert 'Objekt bearbeiten' in form
    assert 'Benutzer bearbeiten' in users and 'Löschen' in users and 'Neues Passwort (optional)' in users
    assert '@router.delete("/api/users/{user_id}")' in users_router
    assert '@router.get("/api/employees/{employee_id}"' in employees_router
