import asyncio
import io
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers, UploadFile

from app.database import Base
from app.main import create_customer, create_project, delete_project_document, list_project_documents, upload_project_document
from app.option_settings import ensure_default_option_groups, get_option_group
from app.project_documents import document_path
import app.project_documents as project_documents
from app.schemas import CustomerCreate, ProjectCreate


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_project_document_categories_are_configurable():
    db = new_db()
    groups = {g.group_key: g for g in ensure_default_option_groups(db)}
    assert "project_document_categories" in groups
    group = get_option_group(db, "project_document_categories")
    assert {o.value for o in group.options} >= {"Pläne", "Bilder / Fotos", "Lieferscheine"}


def test_project_file_upload_list_and_delete(tmp_path):
    db = new_db()
    project_documents.PROJECT_ROOT = tmp_path / "project_files"
    customer = create_customer(CustomerCreate(last_name="Projektmappen Kunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Dachsanierung"), db)
    upload = UploadFile(filename="Dachplan.pdf", file=io.BytesIO(b"%PDF-1.4 test"), headers=Headers({"content-type":"application/pdf"}))
    out = asyncio.run(upload_project_document(project.id, upload, "Pläne", "Plan Stand Ausführung", "2026-08-31", db))
    assert out.category == "Pläne"
    assert out.original_filename == "Dachplan.pdf"
    assert out.can_preview is True
    docs = list_project_documents(project.id, db)
    assert len(docs) == 1 and docs[0].description == "Plan Stand Ausführung"
    from app.models import ProjectDocument
    row = db.get(ProjectDocument, out.id)
    path = document_path(row)
    assert path.is_file()
    delete_project_document(out.id, db)
    assert not path.exists()


def test_project_folder_ui_exists():
    root = Path(__file__).parents[1]
    main = (root / "app/main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root / "app/routers").glob("*.py")))
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    projects = (root / "app/templates/projects.html").read_text(encoding="utf-8")
    assert '@router.get("/projects/{project_id}"' in main
    assert '@router.post("/api/projects/{project_id}/documents"' in main
    # "Übersicht" bewusst nicht mehr in dieser Liste: seit 1.0.48 wurde der frühere
    # Übersicht-Reiter in eine eigenständige "Kennzahlen"-Sektion und eine
    # "Projektinformationen"-Sektion aufgeteilt (siehe Roadmap-Punkt "Projektmappen-
    # Übersicht als zentrales Cockpit").
    for label in ["Projektinformationen", "Kennzahlen", "Dateien", "Angebote", "Dokumentdatum", "Notiz / Beschreibung"]:
        assert label in html
    assert "Projektmappe" in projects


def test_project_folder_is_a_single_consolidated_page_not_tabs():
    """Seit 1.0.48 (Roadmap: 'Projektmappen-Übersicht als zentrales Cockpit')
    sind alle Bereiche gleichzeitig auf einer Seite sichtbar statt einzeln
    umschaltbarer Reiter -- die Seitenleiste ist eine Sprungmarken-Liste,
    keine Tab-Auswahl mehr."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    # Bewusst die genaue frühere Regel geprüft (".section{display:none}"), NICHT
    # nur "display:none}.section" -- seit 1.0.50 gibt es mit ".section-body"
    # eine neue, absichtliche Regel, die zufällig densel­ben, zu weit gefassten
    # Teilstring enthalten würde und den Test sonst fälschlich hätte anschlagen lassen.
    assert ".section{display:none}" not in html.replace(" ", "")
    assert "showTab" not in html
    for section_id in ["sec-kennzahlen", "sec-info", "sec-files", "sec-quotes", "sec-orders", "sec-invoices", "sec-workprep", "sec-times", "sec-history"]:
        assert f'id="{section_id}"' in html
        assert f'href="#{section_id}"' in html


def test_project_folder_sections_are_collapsible():
    """Seit 1.0.50: jedes Modul lässt sich einzeln ein-/ausklappen (bleibt
    dabei aber immer mit sichtbarem Titel auffindbar), Zustand wird in
    localStorage gemerkt -- reine UI-Präferenz, bewusst nicht in der
    Datenbank, da sie keinen fachlichen Bezug zum Projekt hat."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert "toggleSection" in html
    assert "localStorage" in html
    for section_id in ["sec-kennzahlen", "sec-info", "sec-files", "sec-quotes", "sec-orders", "sec-invoices", "sec-workprep", "sec-times", "sec-history"]:
        assert f'id="toggle-{section_id}"' in html
        assert f"toggleSection('{section_id}')" in html
    # Jede Sektion muss einen section-body-Wrapper haben, der beim Einklappen
    # ausgeblendet wird -- der Titel selbst (Toolbar) bleibt außerhalb davon,
    # damit er beim Einklappen sichtbar und klickbar bleibt.
    assert html.count('class="section-body"') == 9


def test_project_folder_shows_kpi_dashboard():
    """Die vier bei der Klärung ausgewählten Kennzahlen müssen als eigene
    Elemente vorhanden sein: Projektwert, Abgerechnet/offen,
    Zeiterfassungsstand, Anzahl Angebote/Aufträge/Rechnungen."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    for element_id in ["kValueNet", "kValueGross", "kInvoicedNet", "kInvoicedGross", "kOpenNet", "kOpenGross", "kHours", "kQuoteCount", "kOrderCount", "kInvoiceCount"]:
        assert f'id="{element_id}"' in html
    assert "renderKennzahlen" in html


def test_kpi_dashboard_grouped_into_three_balanced_clusters_since_1065():
    """Die Kennzahlen-Kacheln waren bis 1.0.64 neun optisch identische
    Karten in einem einzelnen 4er-Raster (unausgeglichene letzte Zeile,
    keine Hierarchie -- vom Nutzer als 'noch nicht überzeugend' bemängelt).
    Seit 1.0.65 in drei natürliche, gleich große Gruppen (Finanzen, Stunden,
    Dokumente) sortiert, 'Noch offen' als wichtigste Zahl optisch betont.
    Alle bestehenden IDs müssen dabei unverändert erhalten bleiben (siehe
    test_project_folder_shows_kpi_dashboard und test_v141), damit
    renderKennzahlen() unverändert funktioniert."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert "kpi-groups" in html
    assert html.count('class="kpi-group-label"') == 3
    assert "Finanzen" in html and "Stunden" in html and "Dokumente" in html
    assert "kpi-emphasis" in html  # "Noch offen" optisch hervorgehoben
    for element_id in ["kValueNet", "kValueGross", "kInvoicedNet", "kInvoicedGross", "kOpenNet", "kOpenGross", "kPlannedHours", "kHours", "kHoursVariance", "kQuoteCount", "kOrderCount", "kInvoiceCount"]:
        assert f'id="{element_id}"' in html


def test_kpi_redesign_does_not_affect_existing_metric_class_used_by_time_tracking():
    """Wichtige Abgrenzung: .metric/.k/.v/.v2 werden auch von der
    Zeiterfassungs-Sektion (renderTimes(), id="timeSummary") verwendet und
    dürfen durch die Kennzahlen-Neugestaltung nicht verändert oder entfernt
    werden -- die neue Gestaltung nutzt bewusst eigene, neue Klassennamen
    (kpi-*) statt die bestehenden umzuwidmen."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert ".metric{" in html
    assert 'id="timeSummary" class="grid"' in html
    assert "renderTimes" in html


def test_order_list_out_exposes_invoiced_amounts_for_project_kpi_aggregation():
    root = Path(__file__).parents[1]
    schemas = (root / "app/schemas.py").read_text(encoding="utf-8")
    match = schemas[schemas.index("class OrderListOut"):]
    match = match[:match.index("class ", 10)]
    assert "invoiced_net" in match
    assert "invoiced_gross" in match
