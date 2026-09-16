from pathlib import Path

from app.reminders import compute_reminder_status, create_reminder, ensure_default_reminder_levels, list_all_reminders, list_invoices_needing_attention
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice


# ---------------------------------------------------------------------------
# compute_reminder_status(): neues 'draft'-Feld (seit 1.0.70)
# ---------------------------------------------------------------------------

def test_compute_reminder_status_draft_is_none_without_existing_draft():
    db = db_session()
    invoice = make_sent_overdue_invoice(db)
    status = compute_reminder_status(db, invoice)
    assert status["draft"] is None


def test_compute_reminder_status_draft_reflects_existing_draft():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    status = compute_reminder_status(db, invoice)
    reminder = create_reminder(db, invoice, status["next_level"])
    db.refresh(invoice)

    status2 = compute_reminder_status(db, invoice)
    assert status2["draft"] is not None
    assert status2["draft"]["id"] == reminder.id
    assert status2["draft"]["level"] == reminder.level
    assert status2["draft"]["status"] == "entwurf"


def test_compute_reminder_status_draft_none_for_invoice_without_due_date():
    """Randfall: eine versendete Rechnung ohne Fälligkeitsdatum (due_date ist
    nullable) muss über die frühe Rückgabe sicher 'draft': None liefern,
    nicht abstürzen."""
    from decimal import Decimal
    from app.models import Customer, Invoice, Order, Project
    from app.project_pipeline_columns import default_pipeline_column_id
    db = db_session()
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0002", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0002", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0002",
        title="Testauftrag", vat_rate=Decimal("19.00"), customer_name="Test Kunde", customer_number="K-0002",
    )
    db.add(order)
    db.flush()
    invoice = Invoice(
        invoice_number="R-TEST-0002", order_id=order.id, invoice_type="schluss", status="versendet",
        due_date=None, customer_name="Test Kunde", vat_rate=Decimal("19.00"),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    status = compute_reminder_status(db, invoice)
    assert status["draft"] is None


# ---------------------------------------------------------------------------
# list_invoices_needing_attention(): draft wird durchgereicht
# ---------------------------------------------------------------------------

def test_list_invoices_needing_attention_includes_draft():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    rows = list_invoices_needing_attention(db)
    assert rows[0]["draft"] is None

    status = compute_reminder_status(db, invoice)
    create_reminder(db, invoice, status["next_level"])
    db.refresh(invoice)

    rows2 = list_invoices_needing_attention(db)
    assert rows2[0]["draft"] is not None


# ---------------------------------------------------------------------------
# list_all_reminders(): systemweite Historie (seit 1.0.70)
# ---------------------------------------------------------------------------

def test_list_all_reminders_empty_when_none_created():
    db = db_session()
    ensure_default_reminder_levels(db)
    make_sent_overdue_invoice(db)
    assert list_all_reminders(db) == []


def test_list_all_reminders_finds_created_reminder():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    status = compute_reminder_status(db, invoice)
    reminder = create_reminder(db, invoice, status["next_level"])

    all_reminders = list_all_reminders(db)
    assert len(all_reminders) == 1
    assert all_reminders[0].id == reminder.id


def test_list_all_reminders_across_multiple_invoices():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice1 = make_sent_overdue_invoice(db, days_overdue=20, suffix="0001")
    invoice2 = make_sent_overdue_invoice(db, days_overdue=10, suffix="0002")
    s1 = compute_reminder_status(db, invoice1)
    s2 = compute_reminder_status(db, invoice2)
    create_reminder(db, invoice1, s1["next_level"])
    create_reminder(db, invoice2, s2["next_level"])

    assert len(list_all_reminders(db)) == 2


# ---------------------------------------------------------------------------
# Statische Prüfungen: Router, Seite, Navigation
# ---------------------------------------------------------------------------

def test_reminders_router_has_new_overview_endpoint():
    src = (Path(__file__).parents[1] / "app" / "routers" / "reminders.py").read_text(encoding="utf-8")
    assert '@router.get("/api/reminders", response_model=list[ReminderOut])' in src


def test_pages_router_has_mahnwesen_route():
    src = (Path(__file__).parents[1] / "app" / "routers" / "pages.py").read_text(encoding="utf-8")
    assert '@router.get("/mahnwesen", response_class=HTMLResponse)' in src


def test_sidebar_links_to_mahnwesen():
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert 'href="/mahnwesen"' in html


def test_mahnwesen_page_has_key_elements():
    html = (Path(__file__).parents[1] / "app" / "templates" / "mahnwesen.html").read_text(encoding="utf-8")
    for marker in ["attentionRows", "allRows", "createReminder", "sendReminder", "deleteReminder", "levelLabel"]:
        assert marker in html, f"fehlt: {marker}"


def test_all_reminders_table_offers_send_and_delete_for_drafts():
    """Regressionstest: "Alle Mahnungen" zeigte Entwürfe und versendete Mahnungen gemeinsam an,
    hatte aber -- anders als "Benötigt Aufmerksamkeit" und invoice_detail.html -- für Entwürfe
    weder eine Versenden- noch eine Löschen-Aktion, obwohl gerade hier ein Entwurf als solcher
    erkennbar ist (Statusspalte). Prüft gezielt INNERHALB von renderAllRows(), nicht nur, dass die
    Funktionsnamen irgendwo in der Datei vorkommen (das taten sie bereits vorher, nur innerhalb
    von renderAttentionRows())."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "mahnwesen.html").read_text(encoding="utf-8")
    body = html[html.index("function renderAllRows("):]
    body = body[:body.index("\nasync function sendReminderEmail")]
    assert "sendReminder(" in body
    assert "deleteReminder(" in body
    assert "r.status==='entwurf'" in body  # die Aktionen sind bedingt, nicht immer sichtbar


def test_finanzen_page_no_longer_duplicates_full_reminder_table():
    """Die ausführliche Tabelle lebt jetzt ausschließlich auf der eigenen
    Mahnwesen-Seite -- Finanzen zeigt nur noch eine schlichte
    Zusammenfassung mit Link, damit dieselbe Logik nicht doppelt gepflegt
    werden muss. Geprüft wird gezielt das alte HTML-Element (id-Attribut),
    nicht die bloße Zeichenkette -- "reminderRows" lebt weiterhin legitim
    als JS-Variablenname für die von /api/reminders/overdue geladenen
    Daten, die renderReminderOverview() für die Zusammenfassung braucht."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "finanzen.html").read_text(encoding="utf-8")
    assert 'id="reminderRows"' not in html
    assert 'href="/mahnwesen"' in html
