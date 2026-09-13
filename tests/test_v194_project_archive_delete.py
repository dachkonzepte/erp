from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from app.projects import delete_project, duplicate_project, load_project, set_project_archived
from tests.test_v153_mahnwesen import db_session
from tests.test_v192_project_templates import make_full_project


# ---------------------------------------------------------------------------
# set_project_archived()
# ---------------------------------------------------------------------------

def test_archive_sets_flag():
    db = db_session()
    project = make_full_project(db)
    result = set_project_archived(db, project, True)
    assert result.archived is True


def test_unarchive_clears_flag():
    db = db_session()
    project = make_full_project(db)
    set_project_archived(db, project, True)
    result = set_project_archived(db, project, False)
    assert result.archived is False


def test_archive_leaves_other_data_untouched():
    """Rein informatives Aus-/Einblenden -- darf an Angebot, Kunde,
    Positionen usw. nichts verändern."""
    db = db_session()
    project = make_full_project(db)
    quote_number_before = project.quotes[0].quote_number
    item_count_before = len(project.quotes[0].items)
    set_project_archived(db, project, True)
    assert project.quotes[0].quote_number == quote_number_before
    assert len(project.quotes[0].items) == item_count_before


def test_archive_works_for_templates_too():
    db = db_session()
    source = make_full_project(db)
    template = duplicate_project(db, source, as_template=True)
    result = set_project_archived(db, template, True)
    assert result.archived is True
    assert result.is_template is True  # bleibt weiterhin ein Muster


# ---------------------------------------------------------------------------
# delete_project() -- die kritische GoBD-Schutzregel
# ---------------------------------------------------------------------------

def test_delete_project_without_orders_succeeds():
    db = db_session()
    project = make_full_project(db)
    project_id = project.id
    delete_project(db, project)
    assert load_project(db, project_id) is None


def test_delete_project_with_order_is_rejected():
    """Kernschutz: Order.invoices trägt cascade='all, delete-orphan' --
    ein uneingeschränktes Löschen würde über Project -> Order -> Invoice
    auch bereits finalisierte, GoBD-geschützte Rechnungen mitreißen."""
    from app.models import Order
    db = db_session()
    project = make_full_project(db)
    order = Order(
        order_number="AUF-TEST-0001", project_id=project.id, source_quote_id=project.quotes[0].id,
        quote_number_snapshot=project.quotes[0].quote_number, title="Dachsanierung", vat_rate=Decimal("19.00"),
        customer_name="Ursprungskunde", customer_number="K-0001",
    )
    db.add(order)
    db.commit()
    project = load_project(db, project.id)

    try:
        delete_project(db, project)
        assert False, "hätte ValueError werfen müssen"
    except ValueError as e:
        assert "Auftrag" in str(e)
    # Projekt muss danach unverändert weiter existieren
    assert load_project(db, project.id) is not None


def test_delete_template_always_works_since_templates_never_have_orders():
    """Ein Mustervorgang hat per Konstruktion nie einen Auftrag (siehe
    duplicate_project()) -- Löschen muss daher immer uneingeschränkt gehen."""
    db = db_session()
    source = make_full_project(db)
    template = duplicate_project(db, source, as_template=True)
    template_id = template.id
    delete_project(db, template)
    assert load_project(db, template_id) is None


def test_delete_project_cascades_to_quote_structure():
    """Prüft, dass die Kaskade tatsächlich vollständig greift -- Angebot,
    Sections, Positionen UND die migrationsarmen Zusatztabellen (Meta,
    Item-Layout) dürfen nach dem Löschen nicht mehr existieren. Deckt genau
    den tatsächlich aufgetretenen Fund ab: diese Zusatztabellen haben keine
    ORM-Relationship und wurden vor der Korrektur als verwaiste Zeilen
    zurückgelassen."""
    from sqlalchemy import select
    from app.models import Quote, QuoteDocumentMeta, QuoteItem, QuoteItemLayout, QuoteSection
    db = db_session()
    project = make_full_project(db)
    quote_id = project.quotes[0].id
    item_ids = [i.id for i in project.quotes[0].items]
    delete_project(db, project)
    assert db.scalar(select(Quote).where(Quote.id == quote_id)) is None
    assert db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote_id)).all() == []
    assert db.scalars(select(QuoteSection).where(QuoteSection.quote_id == quote_id)).all() == []
    assert db.scalar(select(QuoteDocumentMeta).where(QuoteDocumentMeta.quote_id == quote_id)) is None
    assert db.scalars(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id.in_(item_ids))).all() == []


def test_delete_project_removes_physical_document_folder(tmp_path):
    """Cascade löscht nur die Datenbankzeilen -- die eigentlichen Dateien
    liegen außerhalb der Datenbank und müssen explizit mitgelöscht werden."""
    with patch("app.project_documents.PROJECT_ROOT", tmp_path):
        from app.project_documents import project_directory
        db = db_session()
        project = make_full_project(db)
        folder = project_directory(project.id)
        (folder / "testdatei.pdf").write_bytes(b"%PDF-1.4 test")
        assert folder.exists()

        delete_project(db, project)
        assert not folder.exists()


def test_delete_project_does_not_touch_other_projects_folder(tmp_path):
    """Randfall zur physischen Löschung: nur der Ordner des gelöschten
    Projekts darf verschwinden, ein anderes bleibt unberührt."""
    with patch("app.project_documents.PROJECT_ROOT", tmp_path):
        from app.project_documents import project_directory
        db = db_session()
        project_to_delete = make_full_project(db)
        project_to_keep = make_full_project(db, project_number="P-TEST-0002", quote_number="A-TEST-0002")
        folder_to_delete = project_directory(project_to_delete.id)
        folder_to_keep = project_directory(project_to_keep.id)
        (folder_to_keep / "wichtig.pdf").write_bytes(b"%PDF-1.4 wichtig")

        delete_project(db, project_to_delete)
        assert not folder_to_delete.exists()
        assert folder_to_keep.exists()
        assert (folder_to_keep / "wichtig.pdf").exists()


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_projects_router_has_archive_and_delete_endpoints():
    src = (Path(__file__).parents[1] / "app" / "routers" / "projects.py").read_text(encoding="utf-8")
    assert '@router.post("/api/projects/{project_id}/archive"' in src
    assert '@router.post("/api/projects/{project_id}/unarchive"' in src
    assert '@router.delete("/api/projects/{project_id}"' in src


def test_project_detail_endpoint_includes_archived_field():
    """Nachstellung des tatsächlich gefundenen Fehlers: der Detail-Endpunkt
    baut ProjectDetailOut manuell zusammen und hatte 'archived' vergessen --
    das Feld wäre in der Projektmappe immer als 'nicht archiviert'
    angezeigt worden, egal was in der Datenbank stand."""
    src = (Path(__file__).parents[1] / "app" / "routers" / "projects.py").read_text(encoding="utf-8")
    detail_fn = src[src.index("def get_project_detail"):src.index("def get_project_detail") + 1500]
    assert "archived=project.archived" in detail_fn


def test_projects_page_has_archive_and_delete_actions():
    html = (Path(__file__).parents[1] / "app" / "templates" / "projects.html").read_text(encoding="utf-8")
    assert "toggleArchived" in html
    assert "deleteProjectRow" in html
    assert "showArchived" in html


def test_project_folder_page_has_archive_and_delete_actions():
    html = (Path(__file__).parents[1] / "app" / "templates" / "project_folder.html").read_text(encoding="utf-8")
    assert "toggleArchivedHere" in html
    assert "deleteProjectHere" in html
    assert "archivedBadge" in html
