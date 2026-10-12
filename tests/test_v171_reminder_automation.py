"""Automatische Mahnungsentwürfe (1.0.71) -- seit 1.8.79 entfallen (Zahlungsstufe Z2a Nr. 1).

Bis 1.8.78 legte das Öffnen des Mahnwesens (POST /api/reminders/auto-create) je fälliger Rechnung einen Entwurf an, schaltbar
über "Mahnwesen-Einstellungen". Seit 1.8.79 liest die Liste "zur Mahnung fällig" nur; Entwürfe entstehen per Klick, einzeln
oder für mehrere (tests/test_v382_mahnwesen.py). Diese Datei hält fest, dass der alte Weg weg ist."""

from pathlib import Path

import app.reminders as reminders
from app.reminders import ensure_default_reminder_levels, list_all_reminders, list_invoices_needing_attention
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice

ROOT = Path(__file__).parents[1]


def test_no_automatic_draft_functions_any_more():
    for name in ("auto_create_due_reminder_drafts", "get_reminder_auto_create_setting", "set_reminder_auto_create_setting"):
        assert not hasattr(reminders, name), name


def test_listing_due_invoices_creates_nothing():
    db = db_session()
    ensure_default_reminder_levels(db)
    make_sent_overdue_invoice(db, days_overdue=20, suffix="0001")
    make_sent_overdue_invoice(db, days_overdue=16, suffix="0002")
    rows = list_invoices_needing_attention(db)
    assert len(rows) == 2 and all(r["is_due_now"] and r["create_block"] is None for r in rows)
    assert list_all_reminders(db) == []


def test_router_has_no_automation_endpoints():
    src = (ROOT / "app" / "routers" / "reminders.py").read_text(encoding="utf-8")
    for path in ('"/api/reminder-settings"', '"/api/reminders/auto-create"'):
        assert path not in src, path


def test_settings_page_has_no_auto_create_toggle():
    html = (ROOT / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "autoCreateDraftsCheckbox" not in html
    assert "/api/reminder-settings" not in html


def test_mahnwesen_page_does_not_create_on_load():
    html = (ROOT / "app" / "templates" / "mahnwesen.html").read_text(encoding="utf-8")
    assert "/api/reminders/auto-create" not in html
    assert "autoCreateBanner" not in html
    assert "/api/reminders/bulk" in html  # Entwürfe für die Auswahl, per Klick
