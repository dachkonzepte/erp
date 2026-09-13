from pathlib import Path

from app.reminders import (
    auto_create_due_reminder_drafts,
    compute_reminder_status,
    create_reminder,
    ensure_default_reminder_levels,
    get_reminder_auto_create_setting,
    list_all_reminders,
    set_reminder_auto_create_setting,
)
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice


# ---------------------------------------------------------------------------
# Einstellung: an/aus (seit 1.0.71)
# ---------------------------------------------------------------------------

def test_auto_create_setting_defaults_to_true():
    db = db_session()
    assert get_reminder_auto_create_setting(db) is True


def test_set_reminder_auto_create_setting_toggles():
    db = db_session()
    set_reminder_auto_create_setting(db, False)
    assert get_reminder_auto_create_setting(db) is False
    set_reminder_auto_create_setting(db, True)
    assert get_reminder_auto_create_setting(db) is True


# ---------------------------------------------------------------------------
# auto_create_due_reminder_drafts()
# ---------------------------------------------------------------------------

def test_auto_create_creates_draft_for_due_invoice():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)  # days_overdue=16 -> Stufe 1 (7 Tage) ist fällig
    created = auto_create_due_reminder_drafts(db)
    assert len(created) == 1
    assert created[0].level == 1
    assert created[0].status == "entwurf"  # niemals automatisch versendet


def test_auto_create_skips_invoice_with_existing_draft():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    status = compute_reminder_status(db, invoice)
    create_reminder(db, invoice, status["next_level"])  # bereits ein Entwurf vorhanden

    created = auto_create_due_reminder_drafts(db)
    assert created == []
    assert len(list_all_reminders(db)) == 1  # kein zweiter, doppelter Entwurf


def test_auto_create_skips_when_not_yet_due():
    db = db_session()
    ensure_default_reminder_levels(db)
    make_sent_overdue_invoice(db, days_overdue=2)  # unter den 7 Tagen für Stufe 1
    created = auto_create_due_reminder_drafts(db)
    assert created == []


def test_auto_create_respects_disabled_setting():
    db = db_session()
    make_sent_overdue_invoice(db)
    set_reminder_auto_create_setting(db, False)
    created = auto_create_due_reminder_drafts(db)
    assert created == []
    assert list_all_reminders(db) == []


def test_auto_create_across_multiple_due_invoices():
    db = db_session()
    ensure_default_reminder_levels(db)
    make_sent_overdue_invoice(db, days_overdue=20, suffix="0001")
    make_sent_overdue_invoice(db, days_overdue=16, suffix="0002")
    created = auto_create_due_reminder_drafts(db)
    assert len(created) == 2


def test_auto_create_never_sends_only_creates_drafts():
    """Kernanforderung der Klärung: Automatisierung darf niemals versenden,
    nur Entwürfe anlegen."""
    db = db_session()
    ensure_default_reminder_levels(db)
    make_sent_overdue_invoice(db)
    created = auto_create_due_reminder_drafts(db)
    assert created  # nicht leer -- sonst wären die folgenden all()-Prüfungen nur vakuos wahr
    assert all(r.status == "entwurf" for r in created)
    assert all(r.reminder_number is None for r in created)


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_reminders_router_has_automation_endpoints():
    src = (Path(__file__).parents[1] / "app" / "routers" / "reminders.py").read_text(encoding="utf-8")
    for path in [
        '@router.get("/api/reminder-settings"',
        '@router.put("/api/reminder-settings"',
        '@router.post("/api/reminders/auto-create"',
    ]:
        assert path in src, f"fehlt: {path}"


def test_settings_page_has_auto_create_toggle():
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "autoCreateDraftsCheckbox" in html
    assert "saveAutoCreateSetting" in html


def test_mahnwesen_page_triggers_auto_create_on_load():
    html = (Path(__file__).parents[1] / "app" / "templates" / "mahnwesen.html").read_text(encoding="utf-8")
    assert "/api/reminders/auto-create" in html
    assert "autoCreateBanner" in html
