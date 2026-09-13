import asyncio
import io
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers, UploadFile

from app.database import Base
from app.main import (
    create_customer, create_project, get_project_detail, update_project,
    upload_project_document, update_project_document,
)
from app.models import ProjectProfile
from app.option_settings import ensure_default_option_groups, get_option_group
from app.schemas import CustomerCreate, ProjectCreate, ProjectUpdate, ProjectDocumentUpdate
import app.project_documents as project_documents


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_project_categories_are_configurable_and_saved():
    db = new_db()
    ensure_default_option_groups(db)
    group = get_option_group(db, "project_categories")
    assert group is not None
    assert {x.value for x in group.options} >= {"Steildach", "Flachdach", "Reparatur / Wartung"}
    customer = create_customer(CustomerCreate(last_name="Kunde Projektkategorie"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Dachprojekt", category="Flachdach"), db)
    assert project.category == "Flachdach"
    profile = db.scalar(select(ProjectProfile).where(ProjectProfile.project_id == project.id))
    assert profile.category == "Flachdach"


def test_project_masterdata_can_be_updated():
    db = new_db()
    customer = create_customer(CustomerCreate(last_name="Kunde Alt", street="Alt 1", postal_code="52000", city="Aachen"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Altprojekt", status="anfrage", category="Steildach"), db)
    updated = update_project(project.id, ProjectUpdate(
        customer_id=customer.id,
        property_id=None,
        name="Projekt Neu",
        status="planung",
        category="Reparatur / Wartung",
        description="Neue Projektbeschreibung",
    ), db)
    assert updated.project_number == project.project_number
    assert updated.name == "Projekt Neu"
    assert updated.status == "planung"
    assert updated.category == "Reparatur / Wartung"
    assert updated.description == "Neue Projektbeschreibung"
    detail = get_project_detail(project.id, db)
    assert detail.category == "Reparatur / Wartung"


def test_document_description_can_be_edited_after_upload(tmp_path):
    db = new_db()
    project_documents.PROJECT_ROOT = tmp_path / "project_files"
    customer = create_customer(CustomerCreate(last_name="Dokumentkunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Dokumentprojekt"), db)
    upload = UploadFile(filename="Lieferschein.pdf", file=io.BytesIO(b"%PDF-1.4 test"), headers=Headers({"content-type":"application/pdf"}))
    doc = asyncio.run(upload_project_document(project.id, upload, "Lieferscheine", None, "2026-08-31", db))
    changed = update_project_document(doc.id, ProjectDocumentUpdate(
        category="Lieferscheine",
        document_date=__import__("datetime").date(2026, 8, 30),
        description="Materiallieferung Dachziegel, Palette 1–4",
    ), db)
    assert changed.description == "Materiallieferung Dachziegel, Palette 1–4"
    assert str(changed.document_date) == "2026-08-30"


def test_project_folder_ui_has_editing_controls():
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    project_form = (root / "app/templates/project_form.html").read_text(encoding="utf-8")
    projects = (root / "app/templates/projects.html").read_text(encoding="utf-8")
    for text in ["Projektmappe bearbeiten", "Projektkategorie", "Dateiinformationen bearbeiten", "Beschreibung ergänzen"]:
        assert text in html
    assert "project_categories" in project_form
    assert "Kategorie" in projects
