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
    # "Kennzahlen" ist seit 1.3.74 keine eigene Überschrift mehr, sondern ein
    # überschriftsloser, immer sichtbarer Kennzahlen-Streifen (siehe
    # test_project_folder_has_a_persistent_compact_kpi_strip) -- deshalb bewusst
    # nicht mehr in dieser Liste.
    for label in ["Übersicht", "Dateien", "Angebote", "Dokumentdatum", "Notiz / Beschreibung"]:
        assert label in html
    assert "Projektmappe" in projects


def test_project_folder_uses_real_tabs_not_jump_anchors():
    """Seit 1.3.74 (Umbau der Projekt-Detailseite): die frühere linke
    Sprungmarken-Navigation ist einer echten, waagerechten Reiterleiste
    gewichen -- nur der aktive Reiter ist sichtbar, der Rest ist per
    JavaScript ausgeblendet (`.tab-pane{display:none}`), nicht per
    Scroll-Sprungmarke (`:target`) erreichbar."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert "showTab" in html
    assert "TAB_KEYS" in html
    assert '.tab-pane{display:none}' in html.replace(" ", "")
    assert '.tab-pane.active{display:block}' in html.replace(" ", "")
    # Kein Sprungmarken-Highlight mehr (":target") und keine linke Seitenleiste.
    assert ":target" not in html
    assert 'class="side"' not in html
    for section_id in ["sec-info", "sec-files", "sec-quotes", "sec-orders", "sec-invoices", "sec-workprep", "sec-times", "sec-history"]:
        assert f'id="{section_id}"' in html
        assert f"data-tab=\"{section_id}\"" in html
        assert f"showTab('{section_id}')" in html
    # "sec-kennzahlen" ist kein Reiter mehr -- die Kennzahlen sind ein eigener,
    # immer sichtbarer Block oberhalb der Reiterleiste (siehe unten).
    assert "sec-kennzahlen" not in html


def test_project_folder_tab_selection_is_readable_from_the_url_hash():
    """Punkt 3 des Bau-Auftrags: der aktive Reiter gehört in die Adresse,
    damit ein Neuladen oder ein Lesezeichen denselben Reiter zeigt --
    adaptiert aus dem bereits etablierten Muster in settings.html
    (showSettingsSection()/history.replaceState/hashchange), nicht neu
    erfunden. Die drei bestehenden externen Tiefenverweise (projects.html,
    order.html, work_preparation.html) verlinken auf `#sec-quotes`/
    `#sec-orders` -- die Reiter-Schlüssel sind deshalb bewusst identisch mit
    den bisherigen Sprungmarken-IDs, damit keine der drei Dateien geändert
    werden musste."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert "tabFromHash" in html
    assert "history.replaceState" in html
    assert "hashchange" in html
    assert "showTab(tabFromHash(),false)" in html.replace(" ", "")
    order_html = (root / "app/templates/order.html").read_text(encoding="utf-8")
    work_prep_html = (root / "app/templates/work_preparation.html").read_text(encoding="utf-8")
    projects_html = (root / "app/templates/projects.html").read_text(encoding="utf-8")
    assert "#sec-orders" in order_html
    assert "#sec-orders" in work_prep_html
    assert "#sec-quotes" in projects_html


def test_project_folder_defaults_to_uebersicht_tab():
    """Punkt 3: 'Übersicht' (sec-info) ist beim Öffnen ohne Hash aktiv --
    sowohl im statischen Markup (active-Klasse) als auch im Rückfall von
    tabFromHash(), falls die Adresse einen unbekannten/keinen Reiter nennt."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert 'id="sec-info" class="card tab-pane active"' in html
    assert "key='sec-info'" in html.replace(" ", "")


def test_project_folder_tab_counts_replace_the_old_sidebar_counts():
    """Punkt 1: die Zählungen wandern von der linken Navigation (entfernt)
    auf die Reiter -- exakt dieselben vier Zähler wie vorher (Dateien,
    Angebote, Aufträge, Rechnungen), dazu Zeiten wie schon an der alten
    Sprungmarken-Navigation. Arbeitsvorbereitung/Historie/Übersicht hatten
    auch vorher keine Zahl und bekommen auch jetzt keine."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    for element_id in ["tabCountFiles", "tabCountQuotes", "tabCountOrders", "tabCountInvoices", "tabCountTimes"]:
        assert f'id="{element_id}"' in html
    # Die alten, dreifach redundanten Zähler (Kopfbereich-Badges UND
    # Kennzahlen-Dashboard UND Seitenleiste) sind auf genau eine Stelle
    # (die Reiter) konsolidiert.
    for removed_id in ["sideDocCount", "sideQuoteCount", "sideOrderCount", "sideInvoiceCount", "sideTimeCount", "docBadge", "quoteBadge", "orderBadge", "invoiceBadge", "kQuoteCount", "kOrderCount", "kInvoiceCount"]:
        assert removed_id not in html


def test_project_folder_header_has_one_primary_button_and_a_three_dot_menu():
    """Punkt 4: nur eine Aktion bleibt permanent sichtbar. Die reale,
    lokale Produktionsdatenbank zeigt, dass 6 von 8 Projekten bereits den
    Status 'beauftragt' tragen (Angebotsphase damit für die meiste Zeit der
    Projektlaufzeit abgeschlossen) -- 'Projektmappe bearbeiten' passt daher
    besser zum überwiegenden Nachsehen-statt-Anlegen-Ablauf als '+ Angebot'
    (bleibt als Aktion innerhalb der Reiter Übersicht/Angebote erhalten,
    verschwindet also nicht, ist nur nicht mehr die permanent sichtbare
    Kopfaktion). Der Rest wandert ins Drei-Punkte-Menü, wie in der
    Projektliste (projects.html, 1.3.72/1.3.73: .menu/.menu-btn/toggleMenu/
    positionMenu/closeAllMenus, position:fixed, Escape/Scroll/Resize
    schließen das Menü)."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert '<button class="btn primary" onclick="openProjectEdit()">Projektmappe bearbeiten</button>' in html
    for fn in ["toggleMenu", "positionMenu", "closeAllMenus"]:
        assert f"function {fn}" in html
    assert "position:fixed" in html
    for action in ["duplicateProjectHere(false)", "duplicateProjectHere(true)", "toggleArchivedHere()", "deleteProjectHere()"]:
        assert action in html
    # "+ Angebot" bleibt erhalten -- nur nicht mehr als permanente Kopfaktion.
    assert 'id="newQuote"' in html
    assert 'id="newQuote2"' in html


def test_project_folder_has_a_persistent_compact_kpi_strip():
    """Punkt 2 des Bau-Auftrags: die Kennzahlen bleiben über allen Reitern
    sichtbar (kein eigener Reiter), aber schlank -- die frühere, dritte
    KPI-Gruppe 'Dokumente' (Angebote/Aufträge/Rechnungen-Zählung) entfällt
    hier, weil dieselben Zahlen jetzt bereits an den Reitern stehen
    (test_project_folder_tab_counts_replace_the_old_sidebar_counts) --
    keine dritte, redundante Stelle für dieselbe Zahl. Übrig bleiben sechs
    kompakte Kacheln (Finanzen: Projektwert/Abgerechnet/Noch offen; Stunden:
    Soll/Ist/Abweichung), wiederverwendet über die bereits bestehenden
    .metric/.grid-Klassen (dieselben, die auch die Zeiterfassungs-Sektion
    nutzt) statt einer dritten, eigenen Kachel-Optik."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    assert 'class="kpi-strip card"' in html
    assert "kpi-groups" not in html
    assert "kpi-group-label" not in html
    for element_id in ["kValueNet", "kValueGross", "kInvoicedNet", "kInvoicedGross", "kOpenNet", "kOpenGross", "kPlannedHours", "kHours", "kHoursVariance"]:
        assert f'id="{element_id}"' in html
    assert "renderKennzahlen" in html


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
