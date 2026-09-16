from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.document_categories import resolve_category_id
from app.main import create_customer, create_project, update_project, update_project_document
from app.schemas import CustomerCreate, ProjectCreate, ProjectUpdate, ProjectDocumentUpdate
from app.models import AuditLog, ProjectDocument
from app.audit import set_audit_context, reset_audit_context
from app.auth import hash_password, verify_password, make_cookie, parse_cookie


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class User:
    id = 12
    display_name = "Tobias Rödchen"
    username = "tobias"


def test_project_change_logs_actor_old_and_new_value():
    db = new_db()
    token = set_audit_context(User(), None)
    try:
        customer = create_customer(CustomerCreate(last_name="Audit Kunde"), db)
        project = create_project(ProjectCreate(customer_id=customer.id, name="Altes Projekt", category="Steildach"), db)
        update_project(project.id, ProjectUpdate(
            customer_id=customer.id, property_id=None, name="Neues Projekt", status="planung",
            category="Flachdach", description="Neue Beschreibung"
        ), db)
    finally:
        reset_audit_context(token)
    logs = db.scalars(select(AuditLog).where(AuditLog.project_id == project.id, AuditLog.action == "geändert")).all()
    by_field = {x.field_name: x for x in logs}
    assert by_field["name"].actor_name == "Tobias Rödchen"
    assert by_field["name"].old_value == "Altes Projekt"
    assert by_field["name"].new_value == "Neues Projekt"
    assert by_field["category"].old_value == "Steildach"
    assert by_field["category"].new_value == "Flachdach"


def test_document_description_change_is_in_project_history():
    db = new_db()
    token = set_audit_context(User(), None)
    try:
        customer = create_customer(CustomerCreate(last_name="Dok Kunde"), db)
        project = create_project(ProjectCreate(customer_id=customer.id, name="Dok Projekt"), db)
        doc = ProjectDocument(project_id=project.id, category="Pläne", category_id=resolve_category_id(db, "Pläne"), original_filename="plan.pdf", stored_filename="x-plan.pdf", file_size=10, description="Alt")
        db.add(doc); db.commit()
        update_project_document(doc.id, ProjectDocumentUpdate(category="Pläne", description="Neu beschrieben", document_date=None), db)
    finally:
        reset_audit_context(token)
    log = db.scalar(select(AuditLog).where(AuditLog.project_id == project.id, AuditLog.field_name == "description", AuditLog.entity_type == "Projektdatei").order_by(AuditLog.id.desc()))
    assert log is not None
    assert log.old_value == "Alt"
    assert log.new_value == "Neu beschrieben"
    assert log.entity_label == "plan.pdf"


def test_password_hash_and_signed_cookie():
    stored = hash_password("SicheresPasswort123")
    assert verify_password("SicheresPasswort123", stored)
    assert not verify_password("falsch", stored)
    cookie = make_cookie(42)
    assert parse_cookie(cookie) == 42


def test_history_ui_and_project_tab_exist():
    root = Path(__file__).parents[1]
    history = (root / "app/templates/history.html").read_text(encoding="utf-8")
    folder = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    settings = (root / "app/templates/settings.html").read_text(encoding="utf-8")
    assert "Wer" in history and "Änderung" in history
    assert "Änderungshistorie" in folder and "historyRows" in folder
    assert "/users" in settings and "/history" in settings
