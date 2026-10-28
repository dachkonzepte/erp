"""Version 1.9.115 (Stufe 5, R1, Punkt 5, Befund F13/F14): das Änderungsprotokoll erfasst Auftragspositionen und -titel, Rechnungen (mit Positionen
und Statuswechseln), Mahnungen, Einsatzberichte, Wartungsverträge, Dachflächen und Termine; /history zeigt „verworfen“ und „Pausen neu gerechnet“
richtig.

    Auftrag       Menge einer Position, Titel eines LV-Titels -> Zeile mit alt und neu, in der Historie der Projektmappe (project_id)
    Rechnung      Anlegen, Ist-Menge einer Position, Festschreiben (Status entwurf -> versendet, Nummer), Storno-Entwurf
    Mahnung       Anlegen, Frist ändern, Festschreiben
    Bericht       Anlegen, Datum und Art ändern; die Beschreibung im Entwurf nicht je Speichern (wie die Antworten einer Checkliste)
    Wartung, Dachfläche, Termin   Anlegen und Ändern; ein privater Termin nie mit Inhalt (Titel, Ort, Notiz als „(privat)“)
    Anzeige       verlaufAenderung() (_verlauf.html, /history und Projektmappe): „verworfen“ mit Begründung, „Pausen neu gerechnet“ alt -> neu,
                  „angelegt“/„gelöscht“ als Satz (bis 1.9.114 stand für jede andere Aktion „Datensatz gelöscht“)
"""

import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.audit import reset_audit_context, set_audit_context
from app.invoices import create_abschlag_leistungsstand, create_storno_draft, update_invoice_item
from app.models import AuditLog, CalendarEvent, MaintenanceContract, OrderSection, Property, RoofArea, ServiceReport
from app.orders import update_order_item, update_order_section
from app.reminders import create_reminder, finalize_and_send_reminder, update_reminder_draft
from app.service_reports import create_report
from tests.leistungszeitraum import festschreiben
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v334_auswahl_restfaelle import nur_mit_node

VORLAGEN = Path(__file__).resolve().parent.parent / "app" / "templates"


class Konto:
    id = 5
    display_name = "Fin Finanzen"
    username = "fin"


@pytest.fixture
def db():
    sitzung = db_session()
    token = set_audit_context(Konto(), None)
    try:
        yield sitzung
    finally:
        reset_audit_context(token)
        sitzung.close()


def _zeilen(db, art, **filter):
    db.expire_all()
    stmt = select(AuditLog).where(AuditLog.entity_type == art)
    for k, v in filter.items():
        stmt = stmt.where(getattr(AuditLog, k) == v)
    return db.scalars(stmt.order_by(AuditLog.id)).all()


def test_auftragsposition_und_lv_titel(db):
    order, item = make_order_with_item(db)
    update_order_item(db, order.id, item.id, quantity=Decimal("120"))
    [zeile] = _zeilen(db, "Auftragsposition", field_name="quantity")
    assert (Decimal(zeile.old_value), Decimal(zeile.new_value), zeile.project_id, zeile.actor_name) == (
        Decimal("100"), Decimal("120"), order.project_id, "Fin Finanzen")
    assert zeile.entity_label == "1 Dacheindeckung" and zeile.action == "geändert"
    titel = OrderSection(order_id=order.id, sort_order=10, title="Dach")
    db.add(titel)
    db.commit()
    update_order_section(db, order.id, titel.id, title="Dach Nord", description=None)
    assert [(z.action, z.field_name, z.old_value, z.new_value) for z in _zeilen(db, "Auftrags-LV-Titel")] == [
        ("angelegt", None, None, None), ("geändert", "title", "Dach", "Dach Nord")]


def test_rechnung_mit_positionen_und_statuswechsel(db):
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=Decimal("40"))
    [ist] = _zeilen(db, "Rechnungsposition", field_name="ist_quantity")
    assert Decimal(ist.new_value) == Decimal("40") and ist.project_id == order.project_id
    assert ist.entity_label.startswith("Entwurf · Abschlag (Leistungsstand) · 1 Dacheindeckung")
    festschreiben(db, invoice)
    rechnung = {z.field_name: z for z in _zeilen(db, "Rechnung", action="geändert")}
    assert (rechnung["status"].old_value, rechnung["status"].new_value) == ("entwurf", "versendet")
    assert rechnung["invoice_number"].new_value == invoice.invoice_number and rechnung["status"].project_id == order.project_id
    assert [z.action for z in _zeilen(db, "Rechnung", action="angelegt")] == ["angelegt"]
    storno = create_storno_draft(db, invoice)
    assert any(z.entity_id == str(storno.id) for z in _zeilen(db, "Rechnung", action="angelegt"))


def test_mahnung(db):
    invoice = make_sent_overdue_invoice(db)
    mahnung = create_reminder(db, invoice)
    update_reminder_draft(db, mahnung, text=mahnung.text, payment_days=21)
    finalize_and_send_reminder(db, mahnung)
    zeilen = _zeilen(db, "Mahnung")
    assert zeilen[0].action == "angelegt" and zeilen[0].entity_label.startswith("Entwurf · 1. Mahnung zu ")
    status = [z for z in zeilen if z.field_name == "status"]
    assert [(z.old_value, z.new_value) for z in status] == [("entwurf", "versendet")]
    assert all(z.field_name != "amounts_json" for z in zeilen)  # eingefrorene Aufstellung steht an der Mahnung


def test_einsatzbericht_ohne_beschreibung_im_entwurf(db):
    order, _ = make_order_with_item(db)
    bericht = create_report(db, order.id, report_type="rapport", description="Kehle geprüft")
    row = db.get(ServiceReport, bericht["id"])
    row.description = "Kehle geprüft, Laub entfernt"
    db.commit()
    row.performed_at = date(2026, 10, 20)
    db.commit()
    zeilen = _zeilen(db, "Einsatzbericht")
    assert [z.action for z in zeilen][0] == "angelegt" and zeilen[0].project_id == order.project_id
    assert [z.field_name for z in zeilen if z.action == "geändert"] == ["performed_at"]
    assert zeilen[-1].entity_label == f"Rapportbericht vom 20.10.2026 · {order.order_number}"


def test_wartungsvertrag_dachflaeche_und_termin(db):
    order, _ = make_order_with_item(db)
    customer_id = order.project.customer_id
    vertrag = MaintenanceContract(customer_id=customer_id, title="Dachwartung", interval_months=12, next_due_date=date(2027, 4, 1))
    objekt = Property(customer_id=customer_id, name="Halle")
    db.add_all([vertrag, objekt])
    db.commit()
    vertrag.interval_months = 6
    vertrag.last_reminder_due_date = date(2027, 4, 1)  # Stempel gegen doppeltes Erinnern -- still
    flaeche = RoofArea(property_id=objekt.id, name="Nordseite")
    db.add(flaeche)
    db.commit()
    flaeche.area_sqm = Decimal("120.50")
    db.commit()
    assert [(z.action, z.field_name) for z in _zeilen(db, "Wartungsvertrag")] == [("angelegt", None), ("geändert", "interval_months")]
    assert [(z.action, z.field_name, z.entity_label) for z in _zeilen(db, "Dachfläche")] == [
        ("angelegt", None, "Nordseite · Halle"), ("geändert", "area_sqm", "Nordseite · Halle")]
    start = datetime(2026, 11, 2, 9, 0)
    termin = CalendarEvent(title="Aufmaß Halle", start_at=start, end_at=start + timedelta(hours=1), owner_user_id=1, project_id=order.project_id)
    privat = CalendarEvent(title="Arzt", location="Praxis", notes="Kontrolle", start_at=start, end_at=start + timedelta(hours=1),
                           owner_user_id=1, is_private=True)
    db.add_all([termin, privat])
    db.commit()
    # wie app/calendar_events.py::update_event(): geladen, dann geändert (nach dem Commit abgelaufen -- ohne Laden kennt die Historie den alten Wert nicht)
    termin, privat = db.get(CalendarEvent, termin.id), db.get(CalendarEvent, privat.id)
    termin.title = "Aufmaß Halle Nord"
    privat.title = "Zahnarzt"
    privat.outlook_etag = "abc"  # Buchhaltung des Abgleichs -- still
    db.commit()
    offen = _zeilen(db, "Termin", entity_id=str(termin.id))
    assert [(z.action, z.field_name, z.old_value, z.new_value) for z in offen][1:] == [("geändert", "title", "Aufmaß Halle", "Aufmaß Halle Nord")]
    assert offen[0].project_id == order.project_id
    geheim = _zeilen(db, "Termin", entity_id=str(privat.id))
    assert [(z.action, z.field_name, z.old_value, z.new_value) for z in geheim][1:] == [("geändert", "title", "(privat)", "(privat)")]
    schnappschuss = json.loads(geheim[0].details)
    assert (schnappschuss["title"], schnappschuss["location"], schnappschuss["notes"]) == ("(privat)",) * 3
    assert all("Arzt" not in (z.entity_label or "") + (z.details or "") for z in geheim)


def test_auftragsstaende_versprechen_stimmt(db):
    """Die Karte „Auftragsstände“ sagt seit jeher „Einzeländerungen bleiben zusätzlich im Änderungsprotokoll sichtbar“ -- seit 1.9.115 stimmt es.
    Seit 1.9.129 in der Akte: „jede Einzeländerung steht zusätzlich im Verlauf“ (dem Strom der Akte, app/akte_verlauf.py)."""
    text = (VORLAGEN / "akte.html").read_text(encoding="utf-8")
    assert "jede Einzeländerung steht zusätzlich im Verlauf" in text
    from app.audit import AUDITED_TYPES
    from app.models import Invoice, InvoiceItem, OrderItem, Reminder
    assert {OrderItem, OrderSection, Invoice, InvoiceItem, Reminder, ServiceReport, MaintenanceContract, RoofArea, CalendarEvent} <= set(AUDITED_TYPES)


@nur_mit_node
def test_verlauf_aenderung_zeigt_verworfen_und_pausen():
    from tests.test_v314_dashboard_month_berlin import _node
    skript = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_verlauf.html").read_text(encoding="utf-8"), re.S))
    faelle = [
        {"action": "verworfen", "field_name": "discard_reason", "new_value": "doppelt erfasst"},
        {"action": "Pausen neu gerechnet", "field_name": "break_minutes", "old_value": "0", "new_value": "30"},
        {"action": "angelegt"}, {"action": "gelöscht"},
        {"action": "geändert", "old_value": "100", "new_value": "<b>120</b>"},
    ]
    ergebnis = (_node(skript + f"\nprocess.stdout.write(JSON.stringify({json.dumps(faelle)}.map(verlaufAenderung)));", "Europe/Berlin"))
    assert ergebnis == [
        "Verworfen – Begründung: doppelt erfasst",
        '<span class="old">0</span> → <span class="new">30</span>',
        "Datensatz angelegt", "Datensatz gelöscht",
        '<span class="old">100</span> → <span class="new">&lt;b&gt;120&lt;/b&gt;</span>',
    ]


@pytest.mark.parametrize("vorlage", ["history.html", "akte.html"])
def test_history_und_projektmappe_nehmen_verlauf_aenderung(vorlage):
    from tests import vorlagen_js
    text = (VORLAGEN / vorlage).read_text(encoding="utf-8")
    # seit 1.9.129 die Akte (Einzelheiten einer Zeile des Verlaufs, Variable z) statt der Projektmappe
    assert ("${verlaufAenderung(x)}" if vorlage == "history.html" else "${verlaufAenderung(z)}") in text and "Datensatz gelöscht" not in text
    assert vorlagen_js.bindet_ein(vorlage, "_verlauf.html", wurzel=VORLAGEN)
