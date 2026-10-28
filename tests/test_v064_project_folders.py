import io
import re
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers, UploadFile

from app.database import Base
from app.main import create_customer, create_project, delete_project_document, list_project_documents, upload_project_document
from app.option_settings import get_option_group, load_option_groups
from app.project_documents import document_path
import app.project_documents as project_documents
from app.schemas import CustomerCreate, ProjectCreate


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_project_document_categories_are_configurable():
    db = new_db()
    groups = {g.group_key: g for g in load_option_groups(db)}
    assert "project_document_categories" in groups
    group = get_option_group(db, "project_document_categories")
    assert {o.value for o in group.options} >= {"Pläne", "Bilder / Fotos", "Lieferscheine"}


def test_project_file_upload_list_and_delete(tmp_path):
    db = new_db()
    project_documents.PROJECT_ROOT = tmp_path / "project_files"
    customer = create_customer(CustomerCreate(last_name="Projektmappen Kunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Dachsanierung"), db)
    upload = UploadFile(filename="Dachplan.pdf", file=io.BytesIO(b"%PDF-1.4 test"), headers=Headers({"content-type":"application/pdf"}))
    out = upload_project_document(project.id, upload, "Pläne", "Plan Stand Ausführung", "2026-08-31", db)
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
    """Seit 1.9.129 ist die Projektmappe die Akte (akte.html, Stufe 5 R2) -- Übersicht, Dateien und Angebote bleiben, die Projektliste
    nennt sie „Akte“ (bis 1.9.128 „Projektmappe“)."""
    root = Path(__file__).parents[1]
    main = (root / "app/main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root / "app/routers").glob("*.py")))
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    projects = (root / "app/templates/projects.html").read_text(encoding="utf-8")
    assert '@router.get("/projects/{project_id}"' in main
    assert '@router.post("/api/projects/{project_id}/documents"' in main
    for label in ["Übersicht", "Dateien", "Angebote", "Dokumentdatum", "Notiz / Beschreibung"]:
        assert label in html
    assert '<a href="/projects/${p.id}">Akte</a>' in projects


def test_project_folder_uses_real_tabs_not_jump_anchors():
    """Seit 1.3.74 echte Reiter statt Sprungmarken -- seit 1.9.129 die Reiter der Akte (Vorlage akte-uebersicht.html): nur der gewählte
    Abschnitt ist sichtbar (hidden), die Reiter des Auftrags nur mit Auftrag."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    assert "function reiterZeigen(" in html and "const REITER=[" in html
    assert ":target" not in html and 'class="side"' not in html
    for reiter in ["uebersicht", "angebote", "vertrag", "leistungen", "ausfuehrung", "abnahme", "rechnungen", "dateien", "verlauf"]:
        assert f'id="reiter-{reiter}"' in html
        assert f'data-reiter="{reiter}"' in html
    for reiter in ["vertrag", "leistungen", "ausfuehrung", "abnahme", "rechnungen"]:
        assert re.search(rf'data-reiter="{reiter}" data-auftrag hidden', html), reiter


def test_project_folder_tab_selection_is_readable_from_the_url_hash():
    """Der Reiter steht in der Adresse (Neuladen, Lesezeichen); die Anker der früheren Seiten (#sec-… der Projektmappe, #mangel-… der
    Auftragsseite) öffnen den passenden Reiter (tests/test_v549_akte_seite.py prüft die Liste). Verweise von außen nehmen die neuen Anker."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    assert "function reiterAusAnker()" in html
    assert "history.replaceState" in html
    assert "hashchange" in html
    assert "reiterZeigen(reiterAusAnker(),false)" in html.replace(" ", "")
    work_prep_html = (root / "app/templates/work_preparation.html").read_text(encoding="utf-8")
    projects_html = (root / "app/templates/projects.html").read_text(encoding="utf-8")
    assert "#ausfuehrung" in work_prep_html and "#sec-orders" not in work_prep_html
    assert "#angebote" in projects_html and "#sec-quotes" not in projects_html


def test_project_folder_defaults_to_uebersicht_tab():
    """„Übersicht“ ist ohne Anker gewählt -- im Markup (aria-current) und als Rückfall von reiterZeigen() für einen unbekannten Reiter."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    assert '<a href="#uebersicht" data-reiter="uebersicht" aria-current="page">Übersicht</a>' in html
    assert "if(!reiterErlaubt(name))name='uebersicht';" in html


def test_project_folder_tab_counts_replace_the_old_sidebar_counts():
    """Zahlen stehen an den Reitern (Angebote, Leistungen, Rechnungen, Dateien) -- vom Server (GET /api/projects/{id}/akte, zaehler);
    die früheren Zähler der Seitenleiste und des Kopfs gibt es nicht mehr."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    for element_id in ["zahlAngebote", "zahlLeistungen", "zahlRechnungen", "tabCountFiles"]:
        assert f'id="{element_id}"' in html
    assert "akte.zaehler.angebote" in html and "akte.zaehler.rechnungen" in html
    for removed_id in ["sideDocCount", "sideQuoteCount", "sideOrderCount", "sideInvoiceCount", "sideTimeCount", "docBadge", "quoteBadge", "orderBadge", "invoiceBadge", "kQuoteCount", "kOrderCount", "kInvoiceCount", "tabCountTimes"]:
        assert removed_id not in html


def test_project_folder_header_has_one_primary_button_and_a_three_dot_menu():
    """Seit 1.9.129 im Seitenkopf der Akte: genau eine Hauptaktion je Phase und Rolle (vom Server, GET /api/projects/{id}/akte), der Rest im
    Menü „⋮“ (dsMenue() über das Makro) -- „Projekt bearbeiten“, Beteiligte, Auftragsbestätigung, Kopieren, Muster, Wartungsvertrag,
    Archivieren, Löschen. „+ Angebot“ bleibt im Reiter „Angebote“."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    assert '<button type="button" class="ds-knopf ds-knopf-aktion" id="hauptaktion" data-klick="hauptaktion" hidden></button>' in html
    for klick in ["projekt-bearbeiten", "beteiligte-oeffnen", "ab-pdf", "projekt-kopieren", "als-muster", "wartungsvertrag", "archivieren",
                  "projekt-loeschen"]:
        assert f'data-klick="{klick}"' in html
    for action in ["duplicateProjectHere(false)", "duplicateProjectHere(true)", "toggleArchivedHere()", "deleteProjectHere()"]:
        assert action in html
    assert 'id="newQuote"' in html


def test_project_folder_has_a_persistent_compact_kpi_strip():
    """Seit 1.9.129 statt des Kennzahlen-Streifens die Karten „Abrechnung“ (Leistung netto, Zahlung brutto) und „Stunden“ der Übersicht
    -- Zahlen vom Server (GET /api/orders/{id}/zahlen, app/akte.py::zahlen()), die Seite rechnet nichts nach."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    assert 'class="kpi-strip card"' not in html
    for element_id in ["uAbrechnung", "uLeistung", "uZahlung", "uStunden", "uSoll", "uGebucht", "uBw"]:
        assert f'id="{element_id}"' in html
    assert "function zahlenZeichnen()" in html and "/zahlen`" in html


def test_kpi_redesign_does_not_affect_existing_metric_class_used_by_time_tracking():
    """Die Zeiten des Auftrags stehen seit 1.9.129 als Stand im Reiter „Ausführung“ (gebucht, Fahrzeit, Baustelle & Werkstatt); alle
    Buchungen zeigt „Zeiten“ (Befund L3: alle Monate des Auftrags, nicht nur der laufende) -- die eigene Tabelle der Projektmappe
    (renderTimes(), timeSummary) gibt es nicht mehr."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/akte.html").read_text(encoding="utf-8")
    assert 'id="zeitenStand"' in html and "renderTimes" not in html and 'id="timeSummary"' not in html
    assert "'/zeiten?auftrag='+orderId+'&zeitraum=alle#buchungen'" in html


def test_order_list_out_exposes_invoiced_amounts_for_project_kpi_aggregation():
    root = Path(__file__).parents[1]
    schemas = (root / "app/schemas.py").read_text(encoding="utf-8")
    match = schemas[schemas.index("class OrderListOut"):]
    match = match[:match.index("class ", 10)]
    assert "invoiced_net" in match
    assert "invoiced_gross" in match
