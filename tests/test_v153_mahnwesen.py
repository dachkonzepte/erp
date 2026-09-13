from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.invoices import create_schlussrechnung, finalize_and_send_invoice
from app.models import Customer, Order, OrderItem, Project, ReminderLevel
from app.reminders import (
    compute_reminder_status,
    create_reminder,
    delete_reminder_draft,
    ensure_default_reminder_levels,
    finalize_and_send_reminder,
    format_reminder_text,
    list_invoices_needing_attention,
    list_reminder_levels,
    list_reminders_for_invoice,
    reminder_to_dict,
    update_reminder_level,
)


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_sent_overdue_invoice(db, days_overdue=16, quantity=Decimal("100"), unit_price=Decimal("50"), suffix="0001"):
    """Legt Kunde/Projekt/Auftrag/Schlussrechnung an und versendet sie sofort
    mit einem in der Vergangenheit liegenden Fälligkeitsdatum -- der übliche
    Ausgangspunkt für Mahnwesen-Tests.

    suffix (seit 1.0.71): erlaubt mehrere Rechnungen in DERSELBEN Datenbank
    innerhalb eines Tests (z.B. für Automatisierungs-Tests über mehrere
    Rechnungen hinweg) -- ohne eigenen suffix pro Aufruf würden
    project_number/order_number/source_quote_id sonst gegen ihre
    UNIQUE-Constraints verstoßen. Bestehende Aufrufe ohne suffix bleiben
    durch den Standardwert "0001" unverändert."""
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number=f"P-TEST-{suffix}", name="Testprojekt", customer_id=customer.id)
    db.add(project)
    db.flush()
    order = Order(
        order_number=f"AUF-TEST-{suffix}", project_id=project.id, source_quote_id=int(suffix), quote_number_snapshot=f"A-TEST-{suffix}",
        title="Testauftrag", vat_rate=Decimal("19.00"), customer_name="Test Kunde", customer_number=f"K-{suffix}",
    )
    db.add(order)
    db.flush()
    item = OrderItem(
        order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
        quantity=quantity, unit="m²", unit_price=unit_price,
    )
    db.add(item)
    db.commit()
    db.refresh(order)

    due_date = date.today() - timedelta(days=days_overdue)
    invoice = create_schlussrechnung(db, order, due_date=due_date)
    invoice = finalize_and_send_invoice(db, invoice)
    return invoice


# ---------------------------------------------------------------------------
# ensure_default_reminder_levels
# ---------------------------------------------------------------------------

def test_ensure_default_reminder_levels_seeds_three_active_levels():
    db = db_session()
    ensure_default_reminder_levels(db)
    levels = list_reminder_levels(db)
    assert len(levels) == 3
    assert [l.level for l in levels] == [1, 2, 3]
    assert all(l.active for l in levels)
    assert all(l.fee_amount > 0 for l in levels)


def test_ensure_default_reminder_levels_does_not_duplicate_on_second_call():
    db = db_session()
    ensure_default_reminder_levels(db)
    ensure_default_reminder_levels(db)
    assert len(list_reminder_levels(db)) == 3


def test_ensure_default_reminder_levels_does_not_overwrite_edits():
    db = db_session()
    ensure_default_reminder_levels(db)
    lvl1 = list_reminder_levels(db)[0]
    update_reminder_level(
        db, lvl1, label="Eigene Bezeichnung", days_after_previous_step=10,
        fee_amount=Decimal("7.50"), text_template="Eigener Text", active=False,
    )
    ensure_default_reminder_levels(db)  # darf die Bearbeitung nicht zurücksetzen
    lvl1_reloaded = [l for l in list_reminder_levels(db) if l.level == 1][0]
    assert lvl1_reloaded.label == "Eigene Bezeichnung"
    assert lvl1_reloaded.active is False


# ---------------------------------------------------------------------------
# compute_reminder_status
# ---------------------------------------------------------------------------

def test_compute_reminder_status_for_invoice_not_yet_sent():
    db = db_session()
    ensure_default_reminder_levels(db)
    customer = Customer(name="Test Kunde", last_name="Test Kunde"); db.add(customer); db.flush()
    project = Project(project_number="P-TEST-0002", name="Testprojekt", customer_id=customer.id); db.add(project); db.flush()
    order = Order(order_number="AUF-TEST-0002", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0002",
                   title="Testauftrag", vat_rate=Decimal("19.00"), customer_name="Test Kunde"); db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="X",
                      quantity=Decimal("1"), unit="Stk", unit_price=Decimal("100"))); db.commit(); db.refresh(order)
    draft = create_schlussrechnung(db, order)  # bleibt Entwurf

    status = compute_reminder_status(db, draft)
    assert status["current_level"] == 0
    assert status["next_level"] is None  # kein Mahnwesen für unversendete Rechnungen
    assert status["is_due_now"] is False


def test_compute_reminder_status_overdue_invoice_without_reminders():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, days_overdue=16)  # Standard-Stufe-1-Frist: 7 Tage
    status = compute_reminder_status(db, invoice)
    assert status["current_level"] == 0
    assert status["next_level"] == 1
    assert status["next_due_on"] == invoice.due_date + timedelta(days=7)
    assert status["is_due_now"] is True  # 16 Tage überfällig > 7 Tage Frist


def test_compute_reminder_status_not_yet_due():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, days_overdue=2)  # unter der 7-Tage-Frist
    status = compute_reminder_status(db, invoice)
    assert status["next_level"] == 1
    assert status["is_due_now"] is False


def test_compute_reminder_status_progresses_after_sent_reminder():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, days_overdue=16)
    r1 = create_reminder(db, invoice, 1)
    finalize_and_send_reminder(db, r1)
    db.refresh(invoice)

    status = compute_reminder_status(db, invoice)
    assert status["current_level"] == 1
    assert status["next_level"] == 2
    assert status["next_due_on"] == r1.reminder_date + timedelta(days=7)
    assert status["is_due_now"] is False  # gerade erst versendet


def test_compute_reminder_status_skips_inactive_level():
    db = db_session()
    ensure_default_reminder_levels(db)
    lvl2 = [l for l in list_reminder_levels(db) if l.level == 2][0]
    update_reminder_level(
        db, lvl2, label=lvl2.label, days_after_previous_step=lvl2.days_after_previous_step,
        fee_amount=lvl2.fee_amount, text_template=lvl2.text_template, active=False,
    )
    invoice = make_sent_overdue_invoice(db, days_overdue=16)
    r1 = create_reminder(db, invoice, 1)
    finalize_and_send_reminder(db, r1)
    db.refresh(invoice)

    status = compute_reminder_status(db, invoice)
    assert status["current_level"] == 1
    assert status["next_level"] == 3  # Stufe 2 übersprungen


def test_compute_reminder_status_none_when_all_levels_exhausted():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, days_overdue=60)
    for level in (1, 2, 3):
        r = create_reminder(db, invoice, level)
        finalize_and_send_reminder(db, r)
        db.refresh(invoice)
    status = compute_reminder_status(db, invoice)
    assert status["current_level"] == 3
    assert status["next_level"] is None
    assert status["is_due_now"] is False


# ---------------------------------------------------------------------------
# create_reminder / finalize_and_send_reminder / delete_reminder_draft
# ---------------------------------------------------------------------------

def test_create_reminder_requires_sent_invoice():
    db = db_session()
    ensure_default_reminder_levels(db)
    customer = Customer(name="Test Kunde", last_name="Test Kunde"); db.add(customer); db.flush()
    project = Project(project_number="P-TEST-0003", name="Testprojekt", customer_id=customer.id); db.add(project); db.flush()
    order = Order(order_number="AUF-TEST-0003", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0003",
                   title="Testauftrag", vat_rate=Decimal("19.00"), customer_name="Test Kunde"); db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="X",
                      quantity=Decimal("1"), unit="Stk", unit_price=Decimal("100"))); db.commit(); db.refresh(order)
    draft = create_schlussrechnung(db, order)
    try:
        create_reminder(db, draft, 1)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_create_reminder_rejects_inactive_or_unknown_level():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    try:
        create_reminder(db, invoice, 4)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_create_reminder_snapshots_outstanding_amount_and_fee():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, quantity=Decimal("100"), unit_price=Decimal("50"))  # 5000 netto -> 5950 brutto
    reminder = create_reminder(db, invoice, 1)
    assert reminder.outstanding_amount == Decimal("5950.000000")
    assert reminder.fee_amount == Decimal("5.00")  # Standard-Gebühr Stufe 1
    assert reminder.status == "entwurf"
    assert reminder.reminder_number is None


def test_finalize_and_send_reminder_assigns_number_and_locks():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    finalize_and_send_reminder(db, reminder)
    assert reminder.status == "versendet"
    assert reminder.reminder_number is not None
    assert reminder.reminder_number.startswith("M-")

    try:
        finalize_and_send_reminder(db, reminder)
        assert False, "zweites Versenden hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_delete_reminder_draft_only_works_on_drafts():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    reminder_id = reminder.id
    finalize_and_send_reminder(db, reminder)
    try:
        delete_reminder_draft(db, reminder)
        assert False, "hätte ValueError werfen müssen (bereits versendet)"
    except ValueError:
        pass

    reminder2 = create_reminder(db, invoice, 2)
    delete_reminder_draft(db, reminder2)
    remaining = list_reminders_for_invoice(db, invoice.id)
    assert [r.id for r in remaining] == [reminder_id]


# ---------------------------------------------------------------------------
# format_reminder_text
# ---------------------------------------------------------------------------

def test_format_reminder_text_replaces_all_placeholders():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, days_overdue=16, quantity=Decimal("100"), unit_price=Decimal("50"))
    reminder = create_reminder(db, invoice, 1)
    text = format_reminder_text(reminder)
    assert "{" not in text and "}" not in text
    assert invoice.invoice_number in text
    assert "5.950,00 €" in text  # offener Betrag
    assert "5,00 €" in text      # Mahngebühr


def test_format_reminder_text_shows_previous_reminder_date_on_level_two():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, days_overdue=30)
    r1 = create_reminder(db, invoice, 1)
    finalize_and_send_reminder(db, r1)
    db.refresh(invoice)
    r2 = create_reminder(db, invoice, 2)
    text = format_reminder_text(r2)
    assert r1.reminder_date.strftime("%d.%m.%Y") in text


# ---------------------------------------------------------------------------
# list_invoices_needing_attention
# ---------------------------------------------------------------------------

def test_list_invoices_needing_attention_only_includes_overdue_sent_invoices():
    db = db_session()
    ensure_default_reminder_levels(db)
    overdue = make_sent_overdue_invoice(db, days_overdue=16)

    # eine zweite, noch nicht fällige Rechnung -- darf nicht in der Liste auftauchen
    customer = Customer(name="Anderer Kunde", last_name="Anderer Kunde"); db.add(customer); db.flush()
    project = Project(project_number="P-TEST-0009", name="Anderes Projekt", customer_id=customer.id); db.add(project); db.flush()
    order2 = Order(order_number="AUF-TEST-0009", project_id=project.id, source_quote_id=2, quote_number_snapshot="A-TEST-0009",
                    title="Anderer Auftrag", vat_rate=Decimal("19.00"), customer_name="Anderer Kunde"); db.add(order2); db.flush()
    db.add(OrderItem(order_id=order2.id, sort_order=10, position_number="1", short_text="X",
                      quantity=Decimal("1"), unit="Stk", unit_price=Decimal("100"))); db.commit(); db.refresh(order2)
    not_due = create_schlussrechnung(db, order2, due_date=date.today() + timedelta(days=10))
    finalize_and_send_invoice(db, not_due)

    rows = list_invoices_needing_attention(db)
    assert len(rows) == 1
    assert rows[0]["invoice_id"] == overdue.id
    assert rows[0]["next_level"] == 1
    assert rows[0]["is_due_now"] is True


def test_reminder_to_dict_includes_total_amount():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    reminder = create_reminder(db, invoice, 1)
    data = reminder_to_dict(reminder)
    assert data["total_amount"] == Decimal("5955.000000").quantize(Decimal("0.01"))
    assert data["invoice_number"] == invoice.invoice_number


# ---------------------------------------------------------------------------
# Statische Prüfungen: Router, Schemas, Oberfläche
# ---------------------------------------------------------------------------

def test_reminder_router_registered_and_endpoints_present():
    root = Path(__file__).parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    router_src = (root / "app" / "routers" / "reminders.py").read_text(encoding="utf-8")
    assert "reminders" in main
    assert "app.include_router(reminders.router)" in main
    for path in [
        '@router.get("/api/reminder-levels"', '@router.put("/api/reminder-levels/{level_id}"',
        '@router.get("/api/reminders/overdue"', '@router.get("/api/invoices/{invoice_id}/reminder-status"',
        '@router.get("/api/invoices/{invoice_id}/reminders"', '@router.post("/api/invoices/{invoice_id}/reminders"',
        '@router.post("/api/reminders/{reminder_id}/send"', '@router.delete("/api/reminders/{reminder_id}"',
        '@router.get("/api/reminders/{reminder_id}/pdf"',
    ]:
        assert path in router_src, f"fehlt: {path}"


def test_reminder_settings_ui_exists_and_is_in_whitelist():
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert 'id="settings-reminder-levels"' in html
    assert 'data-settings-section="reminder-levels"' in html
    assert "'reminder-levels'" in html[html.index("SETTINGS_SECTIONS"):html.index("SETTINGS_SECTIONS") + 300]
    assert "renderReminderLevels" in html
    assert "saveReminderLevel" in html


def test_invoice_detail_has_reminder_section():
    html = (Path(__file__).parents[1] / "app" / "templates" / "invoice_detail.html").read_text(encoding="utf-8")
    assert 'id="remindersCard"' in html
    assert "loadAndRenderReminders" in html
    assert "createReminderNow" in html
    assert "sendReminderNow" in html


def test_finanzen_has_reminder_overview():
    html = (Path(__file__).parents[1] / "app" / "templates" / "finanzen.html").read_text(encoding="utf-8")
    assert 'id="reminderCard"' in html
    assert "renderReminderOverview" in html
    assert "/api/reminders/overdue" in html


def test_reminder_pdf_reuses_shared_document_blocks():
    """Bewusst geprüft, dass die Mahnungs-PDF gemeinsame Bausteine aus document_pdf.py verwendet
    statt eigene, duplizierte Logik. Seit 1.3.1 kommt der Firmenkopf nicht mehr aus
    reminder_pdf.py selbst, sondern aus dem gemeinsamen PDF-Rahmen (app/document_frame.py, siehe
    test_v226_document_frame.py) -- build_company_header_block() wird dort weiterhin genutzt, nur
    nicht mehr an dieser Stelle. Seit 1.3.3 nutzt die Mahnung für Anschrift/Meta-Block den neuen
    build_din5008_header_block() (CLAUDE.md "Kopfbereich") statt build_customer_and_meta_block()
    -- letzteres bleibt für Angebot/Auftrag/Rechnung unverändert bestehen (siehe
    test_v227_din5008_header_block.py), ist für die Mahnung aber bewusst kein Nutzer mehr."""
    src = (Path(__file__).parents[1] / "app" / "reminder_pdf.py").read_text(encoding="utf-8")
    assert "build_din5008_header_block" in src
    assert "build_object_address_block" in src
    assert "render_framed_pdf" in src
    frame_src = (Path(__file__).parents[1] / "app" / "document_frame.py").read_text(encoding="utf-8")
    assert "build_company_header_block" in frame_src


def test_no_hand_written_migration_needed_new_tables_only():
    """Dokumentiert bewusst die Entscheidung: reminder_levels/reminders sind
    zwei komplett neue, unabhängige Tabellen ohne Änderung an bestehenden
    Spalten -- der normale `alembic revision --autogenerate` reicht aus,
    es gibt (wie bei allen bisherigen sauberen Neu-Tabellen-Migrationen,
    z.B. 1.0.14) keine von Claude handgeschriebene Migrationsdatei dafür."""
    from app.models import Reminder, ReminderLevel
    assert ReminderLevel.__tablename__ == "reminder_levels"
    assert Reminder.__tablename__ == "reminders"
