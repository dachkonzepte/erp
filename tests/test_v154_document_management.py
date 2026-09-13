import asyncio
import io
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers, UploadFile

import app.customer_documents as customer_documents
import app.project_documents as project_documents
from app.database import Base
from app.document_storage import can_preview_type, is_image_type, make_stored_filename
from app.main import create_customer, create_project, upload_project_document
from app.models import Customer, CustomerDocument, ProjectDocument
from app.routers.customer_documents import (
    delete_customer_document,
    download_customer_document,
    update_customer_document,
    view_customer_document,
)
from app.routers.customers import list_customer_documents, upload_customer_document
from app.schemas import CustomerCreate, CustomerDocumentUpdate, ProjectCreate


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# Gemeinsame Hilfsfunktionen (document_storage.py) -- identisch nutzbar von
# beiden Ablagen, siehe Re-Export in project_documents.py
# ---------------------------------------------------------------------------

def test_document_storage_helpers_are_shared_and_reexported():
    import app.project_documents as pd
    assert pd.make_stored_filename is make_stored_filename
    assert pd.is_image_type is is_image_type
    assert pd.can_preview_type is can_preview_type


def test_is_image_and_can_preview_type():
    assert is_image_type("image/png") is True
    assert is_image_type("application/pdf") is False
    assert is_image_type(None) is False
    assert can_preview_type("image/jpeg") is True
    assert can_preview_type("application/pdf") is True
    assert can_preview_type("application/msword") is False


def test_make_stored_filename_keeps_extension_and_is_unique():
    a = make_stored_filename("Vertrag.PDF")
    b = make_stored_filename("Vertrag.PDF")
    assert a.endswith(".pdf")  # kleingeschrieben
    assert a != b  # UUID-basiert, nie identisch


# ---------------------------------------------------------------------------
# CustomerDocument: Upload, Liste, Ansicht, Download, Bearbeiten, Löschen
# -- exakt dieselben Schritte wie test_v064's ProjectDocument-Testcase
# ---------------------------------------------------------------------------

def test_customer_document_upload_list_view_download_delete(tmp_path):
    db = new_db()
    customer_documents.CUSTOMER_ROOT = tmp_path / "customer_files"
    customer = create_customer(CustomerCreate(last_name="Dokumentenmanagement Kunde"), db)

    upload = UploadFile(filename="Rahmenvertrag.pdf", file=io.BytesIO(b"%PDF-1.4 test"), headers=Headers({"content-type": "application/pdf"}))
    out = asyncio.run(upload_customer_document(customer.id, upload, "Verträge / Freigaben", None, None, "2026-08-31", db))
    assert out.category == "Verträge / Freigaben"
    assert out.original_filename == "Rahmenvertrag.pdf"
    assert out.can_preview is True
    assert out.subfolder is None

    docs = list_customer_documents(customer.id, db)
    assert len(docs) == 1 and docs[0].id == out.id

    row = db.get(CustomerDocument, out.id)
    path = customer_documents.document_path(row)
    assert path.is_file()
    assert path.read_bytes() == b"%PDF-1.4 test"

    view_response = view_customer_document(out.id, db)
    assert str(view_response.path) == str(path)
    download_response = download_customer_document(out.id, db)
    assert str(download_response.path) == str(path)

    delete_customer_document(out.id, db)
    assert not path.exists()
    assert list_customer_documents(customer.id, db) == []


def test_customer_document_upload_with_subfolder(tmp_path):
    db = new_db()
    customer_documents.CUSTOMER_ROOT = tmp_path / "customer_files"
    customer = create_customer(CustomerCreate(last_name="Unterordner Kunde"), db)
    upload = UploadFile(filename="Freigabe.pdf", file=io.BytesIO(b"x"), headers=Headers({"content-type": "application/pdf"}))
    out = asyncio.run(upload_customer_document(customer.id, upload, "Verträge / Freigaben", "Bauantrag 2026", None, None, db))
    assert out.subfolder == "Bauantrag 2026"


def test_customer_document_update_changes_category_subfolder_and_description(tmp_path):
    db = new_db()
    customer_documents.CUSTOMER_ROOT = tmp_path / "customer_files"
    customer = create_customer(CustomerCreate(last_name="Bearbeiten Kunde"), db)
    upload = UploadFile(filename="Notiz.pdf", file=io.BytesIO(b"x"), headers=Headers({"content-type": "application/pdf"}))
    out = asyncio.run(upload_customer_document(customer.id, upload, "Sonstiges", None, None, None, db))

    changed = update_customer_document(out.id, CustomerDocumentUpdate(
        category="Schriftverkehr", subfolder="2026 Q3", description="Telefonnotiz",
    ), db)
    assert changed.category == "Schriftverkehr"
    assert changed.subfolder == "2026 Q3"
    assert changed.description == "Telefonnotiz"


def test_customer_document_cascade_deletes_with_customer(tmp_path):
    """Customer.documents trägt cascade='all, delete-orphan' analog zu
    Project.documents -- beim Löschen des Kunden müssen auch seine
    Dokument-Datenbankzeilen verschwinden (die physische Datei bleibt davon
    unberührt, das regelt ausschließlich der Router-Endpunkt beim expliziten
    Löschen -- hier wird nur die ORM-Kaskade auf DB-Zeilenebene geprüft)."""
    db = new_db()
    customer_documents.CUSTOMER_ROOT = tmp_path / "customer_files"
    customer = create_customer(CustomerCreate(last_name="Kaskaden Kunde"), db)
    upload = UploadFile(filename="X.pdf", file=io.BytesIO(b"x"), headers=Headers({"content-type": "application/pdf"}))
    out = asyncio.run(upload_customer_document(customer.id, upload, "Sonstiges", None, None, None, db))
    assert db.get(CustomerDocument, out.id) is not None

    db.delete(db.get(Customer, customer.id))
    db.commit()
    assert db.get(CustomerDocument, out.id) is None


def test_customer_documents_stored_separately_from_project_documents(tmp_path):
    """customer_documents.py hat einen eigenen Speicherort, unabhängig von
    project_documents.py -- eine Kundenlöschung darf niemals in fremden
    Projektdateien nach etwas suchen."""
    assert customer_documents.CUSTOMER_ROOT != project_documents.PROJECT_ROOT


# ---------------------------------------------------------------------------
# ProjectDocument.subfolder -- additive Erweiterung, bestehendes Verhalten
# (siehe test_v064/test_v065) muss unverändert funktionieren
# ---------------------------------------------------------------------------

def test_project_document_upload_still_works_with_old_positional_call_pattern(tmp_path):
    """Regressionstest: subfolder wurde bewusst ans Ende der Parameterliste
    gesetzt (nach db), nicht mittendrin -- sonst hätten die bestehenden
    positional-Aufrufe in test_v064/test_v065 subfolder/description/
    document_date/db falsch zugeordnet bekommen. Bildet exakt deren
    Aufrufmuster nach."""
    db = new_db()
    project_documents.PROJECT_ROOT = tmp_path / "project_files"
    customer = create_customer(CustomerCreate(last_name="Regressionstest Kunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Regressionsdach"), db)
    upload = UploadFile(filename="Plan.pdf", file=io.BytesIO(b"%PDF-1.4 test"), headers=Headers({"content-type": "application/pdf"}))
    out = asyncio.run(upload_project_document(project.id, upload, "Pläne", "Ein Text", "2026-08-31", db))
    assert out.category == "Pläne"
    assert out.description == "Ein Text"  # nicht subfolder -- genau das wäre bei falscher Parameterreihenfolge kaputt gewesen
    assert out.document_date is not None
    assert out.subfolder is None  # per Default, da nicht übergeben


def test_project_document_upload_with_explicit_subfolder(tmp_path):
    db = new_db()
    project_documents.PROJECT_ROOT = tmp_path / "project_files"
    customer = create_customer(CustomerCreate(last_name="Unterordner Projekt Kunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Dach mit Unterordner"), db)
    upload = UploadFile(filename="Statik.pdf", file=io.BytesIO(b"x"), headers=Headers({"content-type": "application/pdf"}))
    out = asyncio.run(upload_project_document(
        project.id, upload, "Pläne", None, None, db, subfolder="Statik-Nachweise",
    ))
    assert out.subfolder == "Statik-Nachweise"


def test_project_document_model_has_subfolder_column():
    import inspect
    src = Path("app/models.py").read_text(encoding="utf-8")
    body_start = src.index("class ProjectDocument(Base):")
    body_end = src.index("\n\nclass ", body_start)
    body = src[body_start:body_end]
    assert "subfolder: Mapped[str | None]" in body


# ---------------------------------------------------------------------------
# Statische Prüfungen: Router, Schemas, Oberfläche
# ---------------------------------------------------------------------------

def test_customer_document_router_registered():
    root = Path(__file__).parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    customers_src = (root / "app" / "routers" / "customers.py").read_text(encoding="utf-8")
    customer_docs_src = (root / "app" / "routers" / "customer_documents.py").read_text(encoding="utf-8")
    assert "app.include_router(customer_documents.router)" in main
    assert '@router.get("/api/customers/{customer_id}/documents"' in customers_src
    assert '@router.post("/api/customers/{customer_id}/documents"' in customers_src
    for path in [
        '@router.put("/api/customer-documents/{document_id}"',
        '@router.get("/api/customer-documents/{document_id}/view"',
        '@router.get("/api/customer-documents/{document_id}/download"',
        '@router.delete("/api/customer-documents/{document_id}"',
    ]:
        assert path in customer_docs_src, f"fehlt: {path}"


def test_customer_html_has_document_section():
    html = (Path(__file__).parents[1] / "app" / "templates" / "customer.html").read_text(encoding="utf-8")
    for marker in [
        "docUploadZone", "docCategory", "docSubfolder", "docCategoryCards", "docSubfolderCards",
        "customerDocuments", "docEditor", "uploadDocuments", "renderCustomerDocuments",
        "editDocRow", "removeDocRow", "/api/customers/${customerId}/documents",
    ]:
        assert marker in html, f"fehlt: {marker}"


def test_project_folder_html_has_subfolder_support():
    html = (Path(__file__).parents[1] / "app" / "templates" / "project_folder.html").read_text(encoding="utf-8")
    for marker in ["subfolder", "subfolderCards", "renderSubfolders", "filterSubfolder", "activeSubfolder"]:
        assert marker in html, f"fehlt: {marker}"


def test_shared_document_category_option_group_covers_both_scopes():
    src = (Path(__file__).parents[1] / "app" / "option_settings.py").read_text(encoding="utf-8")
    section = src[src.index('"project_document_categories"'):src.index('"project_document_categories"') + 400]
    assert "Kundenmappe" in section
    assert "Projektmappe" in section


def test_reminder_migration_present_and_matches_models():
    """Die von Tobias lokal via alembic autogenerate erzeugte und
    zurückgeschickte Migration -- hier nur geprüft, dass sie im Projekt
    liegt und auf die richtige vorherige Version aufsetzt.

    Gezielt über die bekannte Revisions-ID gesucht (seit 1.0.71), nicht
    mehr per Schlagwort-Glob über "*mahnwesen*" -- mit der
    Mahnwesen-Automatisierung (1.0.71) kam eine zweite, ebenfalls
    berechtigte Migration mit "mahnwesen" im Dateinamen hinzu, wodurch der
    bisherige Glob nicht mehr eindeutig war."""
    versions_dir = Path(__file__).parents[1] / "alembic" / "versions"
    migration_files = list(versions_dir.glob("0946c1a4c4be_*.py"))
    assert len(migration_files) == 1
    content = migration_files[0].read_text(encoding="utf-8")
    assert "down_revision = 'bb175f455b64'" in content
    assert "reminder_levels" in content
    assert "reminders" in content
