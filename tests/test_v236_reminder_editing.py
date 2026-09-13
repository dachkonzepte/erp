"""Mahnwesen vervollständigen (seit 1.3.21): Löschen/Versenden in "Alle Mahnungen" anbinden
(Punkt 1), Bearbeiten eines Mahnungsentwurfs neu bauen (Punkt 2)."""
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.reminders import create_reminder, ensure_default_reminder_levels, update_reminder_draft
from app.routers.reminders import router as reminders_router
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice


# ---------------------------------------------------------------------------
# Punkt 2: update_reminder_draft() -- Geschäftslogik
# ---------------------------------------------------------------------------

def test_update_reminder_draft_changes_text_fee_and_due_date():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)

    updated = update_reminder_draft(
        db, reminder, text="Neuer Text mit {mahngebuehr}", fee_amount=Decimal("12.50"),
        new_due_date=date(2026, 12, 1),
    )
    assert updated.text == "Neuer Text mit {mahngebuehr}"
    assert updated.fee_amount == Decimal("12.50")
    assert updated.new_due_date == date(2026, 12, 1)


def test_update_reminder_draft_rejects_already_sent_reminder():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    from app.reminders import finalize_and_send_reminder
    finalize_and_send_reminder(db, reminder)

    original_text = reminder.text
    try:
        update_reminder_draft(db, reminder, text="Manipuliert", fee_amount=Decimal("0"), new_due_date=None)
        assert False, "hätte ValueError werfen müssen (bereits versendet)"
    except ValueError:
        pass
    assert reminder.text == original_text


def test_update_reminder_draft_can_clear_new_due_date():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    assert reminder.new_due_date is not None

    update_reminder_draft(db, reminder, text=reminder.text, fee_amount=reminder.fee_amount, new_due_date=None)
    assert reminder.new_due_date is None


# ---------------------------------------------------------------------------
# Punkt 2: PUT /api/reminders/{id} -- Endpunkt
# ---------------------------------------------------------------------------

def test_put_reminder_endpoint_updates_draft(threaded_db_session, router_test_client):
    db = threaded_db_session
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    client = router_test_client(db, reminders_router)

    resp = client.put(f"/api/reminders/{reminder.id}", json={
        "text": "Bitte zahlen Sie {offener_betrag}.", "fee_amount": "7.50", "new_due_date": "2026-11-15",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "Bitte zahlen Sie {offener_betrag}."
    assert Decimal(body["fee_amount"]) == Decimal("7.50")
    assert body["new_due_date"] == "2026-11-15"


def test_put_reminder_endpoint_rejects_sent_reminder_with_400(threaded_db_session, router_test_client):
    db = threaded_db_session
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    from app.reminders import finalize_and_send_reminder
    finalize_and_send_reminder(db, reminder)
    client = router_test_client(db, reminders_router)

    resp = client.put(f"/api/reminders/{reminder.id}", json={
        "text": "Manipuliert", "fee_amount": "0", "new_due_date": None,
    })
    assert resp.status_code == 400


def test_put_reminder_endpoint_404_for_unknown_id(threaded_db_session, router_test_client):
    db = threaded_db_session
    ensure_default_reminder_levels(db)
    client = router_test_client(db, reminders_router)
    resp = client.put("/api/reminders/999999", json={"text": None, "fee_amount": "0", "new_due_date": None})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Punkt 1 + 2: Oberfläche -- statische Prüfungen (kein JS-Test-Runner im Projekt)
# ---------------------------------------------------------------------------

def test_mahnwesen_page_offers_edit_for_drafts_in_both_tables():
    html = (Path(__file__).parents[1] / "app" / "templates" / "mahnwesen.html").read_text(encoding="utf-8")
    attention_body = html[html.index("function renderAttentionRows("):html.index("function emailStatusLabel(")]
    all_body = html[html.index("function renderAllRows("):html.index("\nasync function sendReminderEmail")]
    assert "editReminder(" in attention_body
    assert "editReminder(" in all_body
    assert "async function saveReminderEdit()" in html
    assert 'method:\'PUT\'' in html or 'method: \'PUT\'' in html


def test_invoice_detail_page_offers_edit_for_reminder_drafts():
    html = (Path(__file__).parents[1] / "app" / "templates" / "invoice_detail.html").read_text(encoding="utf-8")
    assert "editReminderNow(" in html
    assert "async function saveReminderEditNow()" in html


# ---------------------------------------------------------------------------
# Nachtrag: Platzhalterliste mit Bedeutung + nicht-blockierender Hinweis bei fehlendem
# Platzhalter (Nutzerentscheidung gegen eine Erkennungsspalte, siehe CLAUDE.md).
# ---------------------------------------------------------------------------

def test_edit_panels_list_placeholders_with_meaning_and_exclude_mahnstufe():
    """{mahnstufe} gilt laut app/reminders.py::send_reminder_email() nur für die E-Mail-Vorlagen,
    nicht für Reminder.text (format_reminder_text() kennt es nicht) -- darf in der Liste für das
    Bearbeiten-Panel deshalb nicht auftauchen (siehe reminders.py:_reminder_placeholders())."""
    for filename in ("mahnwesen.html", "invoice_detail.html"):
        html = (Path(__file__).parents[1] / "app" / "templates" / filename).read_text(encoding="utf-8")
        assert "{mahngebuehr}</code> – Mahngebühr" in html, filename
        assert "{neue_frist}</code> – neue Zahlungsfrist" in html, filename
        assert "{mahnstufe}" not in html, filename


def test_edit_panels_warn_but_do_not_block_when_placeholder_is_missing():
    for filename in ("mahnwesen.html", "invoice_detail.html"):
        html = (Path(__file__).parents[1] / "app" / "templates" / filename).read_text(encoding="utf-8")
        body = html[html.index("function reminderMissingPlaceholderWarning("):]
        body = body[:body.index("\n}")]
        assert "{mahngebuehr}" in body
        assert "{neue_frist}" in body
        # kein "return" vor dem API-Aufruf, das den Speichervorgang abbricht -- der Aufrufer ruft
        # die Warnfunktion auf, verwendet das Ergebnis aber nur fuer eine Anzeige (alert), nie fuer
        # eine Bedingung um den PUT-Aufruf herum.
        save_fn_name = "saveReminderEdit" if filename == "mahnwesen.html" else "saveReminderEditNow"
        save_body = html[html.index(f"async function {save_fn_name}("):]
        save_body = save_body[:save_body.index("\n}")]
        assert "if(warning)" in save_body
        assert "await api(" in save_body
        assert "if(warning)return" not in save_body.replace(" ", "")
