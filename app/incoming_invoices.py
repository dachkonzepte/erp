"""Buchhaltung Stufe 1 -- Eingangsrechnungen erfassen und ablegen (Modul "buchhaltung").

Vorbereitende Buchhaltung, kein Ersatz für den Steuerberater: sammelt und ordnet
Eingangsrechnungen mit Belegen, damit sie später (Stufe 2) kontiert und für den Steuerberater
exportiert werden können. KI-Belegauswertung ist Stufe 3. Diese Version ist ausschließlich
manuelle Erfassung -- Modell und Router sind so geschnitten, dass Stufe 2/3 andocken, siehe
CLAUDE.md "Buchhaltung" für die Andockpunkte im Detail und IncomingInvoice-Klassendocstring
(app/models.py) für die einzelnen Felder.

Positionen (IncomingInvoiceItem) sind eine OPTIONALE Aufschlüsselung des Gesamtbetrags --
IncomingInvoice.net_amount bleibt bei jeder Rechnung die maßgebliche Summe. Existieren
Positionen, muss ihre Netto-Summe zum Gesamtbetrag passen (siehe _validate_item_sum()) --
Stufe 2 kontiert dann je nach Fall den Gesamtbetrag (kein Split nötig) oder die einzelnen
Positionen (Split nötig).

Verrechnungssatz-Grenze (bestätigt, siehe CLAUDE.md "Buchhaltung"): eine Eingangsrechnung
ändert NIE RecurringCost.annual_amount/den Verrechnungssatz -- ein Plan-Ist-Abgleich (über
recurring_cost_id) bliebe reine Anzeige ohne Rückwirkung, ist aber NICHT Teil dieser Version
(nicht explizit beauftragt) -- die Verknüpfung selbst existiert bereits und würde eine solche
Auswertung später ohne Umbau ermöglichen.

Vorkontierung (seit Buchhaltung Stufe 2, erster Teil, siehe app/accounts.py für den
Kontenstamm): account_id (Header UND je Position) verweist optional auf ein Sachkonto --
**das ist eine VORKONTIERUNG, kein finaler Buchungssatz**. Der Steuerberater prüft und bucht,
das ERP nimmt an keiner Stelle eine steuerliche Bewertung vor. is_invoice_accounted() ist eine
reine Anzeige-Ableitung (sichtbar in der Liste, welche Rechnungen noch offen sind), keine
Voraussetzung zum Speichern -- eine unkontierte Rechnung bleibt vollständig gültig."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .incoming_invoice_documents import delete_document_file
from .models import (
    Account, IncomingInvoice, IncomingInvoiceItem, IncomingInvoiceSettings, OperationalAsset,
    Project, RecurringCost, Supplier,
)
from .modules import is_module_enabled
from .operational_assets import resolve_asset_identity
from .permissions import ROLE_OFFICE_FINANZEN
from .tasks import create_task

MODULE_KEY = "buchhaltung"

# Fester Code-Wert wie bei RecurringCost.TAX_RATES -- dieselben drei Sätze, dieselbe Begründung
# (nur diese drei real relevant, Rechenregel statt freier Anzeigeliste).
TAX_RATES = (Decimal("19.00"), Decimal("7.00"), Decimal("0.00"))

# payment_status trägt NUR diese zwei Werte -- "ueberfaellig" wird NIE gespeichert, siehe
# is_overdue() unten (konsistent mit Invoice, app/invoices.py).
PAYMENT_STATUSES = ("offen", "bezahlt")

_ITEM_SUM_TOLERANCE = Decimal("0.01")


def gross_amount(net_amount: Decimal, tax_rate_pct: Decimal) -> Decimal:
    """Reine Anzeige-Ableitung, NIE gespeichert -- Muster RecurringCost.gross_amount()."""
    return (net_amount * (Decimal("1") + tax_rate_pct / Decimal("100"))).quantize(Decimal("0.01"))


def invoice_gross_amount(invoice: IncomingInvoice) -> Decimal:
    """Positionen vorhanden -> Summe ihrer je EIGENEN Bruttobeträge (jede Position mit ihrem
    eigenen Steuersatz, da eine gemischte Rechnung keinen einzigen gemeinsamen Satz hat); sonst
    Gesamtbetrag*Steuersatz -- Muster RecurringCost.gross_amount(), hier zusätzlich
    Positions-bewusst."""
    if invoice.items:
        return sum(
            (gross_amount(i.net_amount, i.tax_rate_pct) for i in invoice.items), Decimal("0")
        ).quantize(Decimal("0.01"))
    return gross_amount(invoice.net_amount, invoice.tax_rate_pct)


def is_overdue(payment_status: str, due_date: date | None, *, today: date | None = None) -> bool:
    """Reine Ableitung, NIE gespeichert -- konsistent mit Invoice (app/invoices.py:
    is_overdue = status=="versendet" and due_date is not None and due_date < date.today())."""
    if payment_status != "offen" or due_date is None:
        return False
    today = today or date.today()
    return due_date < today


def is_skonto_due(skonto_deadline: date | None, payment_status: str, lead_days: int, *, today: date | None = None) -> bool:
    if skonto_deadline is None or payment_status != "offen":
        return False
    today = today or date.today()
    return skonto_deadline <= today + timedelta(days=lead_days)


def is_skonto_overdue(skonto_deadline: date | None, payment_status: str, *, today: date | None = None) -> bool:
    if skonto_deadline is None or payment_status != "offen":
        return False
    today = today or date.today()
    return skonto_deadline < today


def is_invoice_accounted(invoice: IncomingInvoice) -> bool:
    """Reine Anzeige-Ableitung (Liste: "kontiert"/"nicht kontiert") -- existieren Positionen,
    muss JEDE davon ein Konto tragen (sonst bliebe ein Teil der Rechnung beim Export offen);
    ohne Positionen entscheidet allein das Header-Konto."""
    if invoice.items:
        return all(i.account_id is not None for i in invoice.items)
    return invoice.account_id is not None


def get_or_create_incoming_invoice_settings(db: Session) -> IncomingInvoiceSettings:
    settings = db.get(IncomingInvoiceSettings, 1)
    if settings is None:
        settings = IncomingInvoiceSettings(id=1)
        db.add(settings)
        db.commit()
    return settings


def incoming_invoice_settings_to_dict(settings: IncomingInvoiceSettings) -> dict:
    return {"skonto_reminder_lead_days": settings.skonto_reminder_lead_days}


def update_incoming_invoice_settings(db: Session, skonto_reminder_lead_days: int) -> dict:
    settings = get_or_create_incoming_invoice_settings(db)
    settings.skonto_reminder_lead_days = skonto_reminder_lead_days
    db.commit()
    return incoming_invoice_settings_to_dict(settings)


def _item_to_dict(item: IncomingInvoiceItem) -> dict:
    return {
        "id": item.id,
        "description": item.description,
        "net_amount": item.net_amount,
        "tax_rate_pct": item.tax_rate_pct,
        "gross_amount": gross_amount(item.net_amount, item.tax_rate_pct),
        "account_id": item.account_id,
        "account_number": item.account.account_number if item.account else None,
        "account_label": item.account.label if item.account else None,
    }


def invoice_to_dict(invoice: IncomingInvoice, skonto_lead_days: int, *, today: date | None = None) -> dict:
    overdue = is_overdue(invoice.payment_status, invoice.due_date, today=today)
    asset_name = None
    if invoice.asset is not None:
        asset_name = resolve_asset_identity(invoice.asset)[0]
    return {
        "id": invoice.id,
        "supplier_id": invoice.supplier_id,
        "supplier_name": invoice.supplier.name if invoice.supplier else None,
        "supplier_invoice_number": invoice.supplier_invoice_number,
        "invoice_date": invoice.invoice_date,
        "net_amount": invoice.net_amount,
        "tax_rate_pct": invoice.tax_rate_pct,
        "gross_amount": invoice_gross_amount(invoice),
        "due_date": invoice.due_date,
        "skonto_percent": invoice.skonto_percent,
        "skonto_deadline": invoice.skonto_deadline,
        "is_skonto_due": is_skonto_due(invoice.skonto_deadline, invoice.payment_status, skonto_lead_days, today=today),
        "is_skonto_overdue": is_skonto_overdue(invoice.skonto_deadline, invoice.payment_status, today=today),
        "payment_status": invoice.payment_status,
        "is_overdue": overdue,
        # display_status ist der Wert, nach dem die Liste filtert -- "ueberfaellig" existiert
        # ausschließlich hier, nie als gespeicherter Spaltenwert.
        "display_status": "ueberfaellig" if overdue else invoice.payment_status,
        "payment_date": invoice.payment_date,
        "has_document": invoice.document_filename is not None,
        "document_original_name": invoice.document_original_name,
        "project_id": invoice.project_id,
        "project_name": invoice.project.name if invoice.project else None,
        "asset_id": invoice.asset_id,
        "asset_name": asset_name,
        "recurring_cost_id": invoice.recurring_cost_id,
        "recurring_cost_label": invoice.recurring_cost.label if invoice.recurring_cost else None,
        "account_id": invoice.account_id,
        "account_number": invoice.account.account_number if invoice.account else None,
        "account_label": invoice.account.label if invoice.account else None,
        "is_accounted": is_invoice_accounted(invoice),
        "notes": invoice.notes,
        "items": [_item_to_dict(i) for i in invoice.items],
        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,
    }


def _invoice_query():
    return select(IncomingInvoice).options(
        selectinload(IncomingInvoice.supplier),
        selectinload(IncomingInvoice.project),
        selectinload(IncomingInvoice.asset).selectinload(OperationalAsset.resource),
        selectinload(IncomingInvoice.recurring_cost),
        selectinload(IncomingInvoice.account),
        selectinload(IncomingInvoice.items).selectinload(IncomingInvoiceItem.account),
    )


def _load(db: Session, invoice_id: int) -> IncomingInvoice | None:
    return db.scalar(_invoice_query().where(IncomingInvoice.id == invoice_id))


def get_invoice(db: Session, invoice_id: int) -> dict | None:
    invoice = _load(db, invoice_id)
    if invoice is None:
        return None
    lead_days = get_or_create_incoming_invoice_settings(db).skonto_reminder_lead_days
    return invoice_to_dict(invoice, lead_days)


def list_invoices(
    db: Session, *, payment_status: str | None = None, supplier_id: int | None = None,
    date_from: date | None = None, date_to: date | None = None, today: date | None = None,
) -> list[dict]:
    """supplier_id/date_from/date_to filtern auf echten Spalten (SQL), payment_status filtert
    auf dem berechneten display_status (siehe invoice_to_dict()) -- "ueberfaellig" ist kein
    gespeicherter Spaltenwert, kann also nicht Teil der WHERE-Klausel sein."""
    lead_days = get_or_create_incoming_invoice_settings(db).skonto_reminder_lead_days
    query = _invoice_query()
    if supplier_id is not None:
        query = query.where(IncomingInvoice.supplier_id == supplier_id)
    if date_from is not None:
        query = query.where(IncomingInvoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.where(IncomingInvoice.invoice_date <= date_to)
    query = query.order_by(IncomingInvoice.invoice_date.desc(), IncomingInvoice.id.desc())
    rows = [invoice_to_dict(i, lead_days, today=today) for i in db.scalars(query).all()]
    if payment_status is not None:
        rows = [r for r in rows if r["display_status"] == payment_status]
    return rows


def _validate_single_assignment(project_id: int | None, asset_id: int | None, recurring_cost_id: int | None) -> None:
    set_count = sum(1 for v in (project_id, asset_id, recurring_cost_id) if v is not None)
    if set_count > 1:
        raise ValueError(
            "Eine Eingangsrechnung kann nur einem Projekt, Betriebsmittel oder Kostenposten "
            "zugeordnet sein, nicht mehreren."
        )


def _validate_referenced_entities(db: Session, fields: dict) -> None:
    if fields["project_id"] is not None and db.get(Project, fields["project_id"]) is None:
        raise ValueError(f"Projekt #{fields['project_id']} wurde nicht gefunden.")
    if fields["asset_id"] is not None and db.get(OperationalAsset, fields["asset_id"]) is None:
        raise ValueError(f"Betriebsmittel #{fields['asset_id']} wurde nicht gefunden.")
    if fields["recurring_cost_id"] is not None and db.get(RecurringCost, fields["recurring_cost_id"]) is None:
        raise ValueError(f"Kostenposten #{fields['recurring_cost_id']} wurde nicht gefunden.")
    if fields["account_id"] is not None and db.get(Account, fields["account_id"]) is None:
        raise ValueError(f"Konto #{fields['account_id']} wurde nicht gefunden.")


def _validate_items_payload(db: Session, items_payload: list[dict] | None) -> list[dict]:
    if not items_payload:
        return []
    result = []
    for item in items_payload:
        description = (item.get("description") or "").strip()
        if not description:
            raise ValueError("Jede Position braucht eine Beschreibung.")
        net_amount = Decimal(str(item["net_amount"]))
        tax_rate_pct = Decimal(str(item.get("tax_rate_pct", "19.00")))
        if tax_rate_pct not in TAX_RATES:
            raise ValueError(f"Unbekannter Steuersatz: {tax_rate_pct}")
        account_id = item.get("account_id")
        if account_id is not None and db.get(Account, account_id) is None:
            raise ValueError(f"Konto #{account_id} wurde nicht gefunden.")
        result.append({
            "description": description, "net_amount": net_amount, "tax_rate_pct": tax_rate_pct,
            "account_id": account_id,
        })
    return result


def _validate_item_sum(net_amount: Decimal, items: list[dict]) -> None:
    """Wenn Positionen vorhanden sind, muss ihre Netto-Summe zum Gesamtbetrag passen -- meldet
    eine Abweichung (ValueError), statt sie still zuzulassen (Betreibervorgabe)."""
    if not items:
        return
    item_sum = sum((i["net_amount"] for i in items), Decimal("0"))
    if abs(item_sum - net_amount) > _ITEM_SUM_TOLERANCE:
        raise ValueError(
            f"Die Summe der Positionen ({item_sum:.2f} €) stimmt nicht mit dem Gesamtbetrag "
            f"({net_amount:.2f} €) überein."
        )


def _payload_fields(payload: dict) -> dict:
    net_amount = Decimal(str(payload["net_amount"]))
    tax_rate_pct = Decimal(str(payload.get("tax_rate_pct", "19.00")))
    if tax_rate_pct not in TAX_RATES:
        raise ValueError(f"Unbekannter Steuersatz: {tax_rate_pct}")
    payment_status = payload.get("payment_status") or "offen"
    if payment_status not in PAYMENT_STATUSES:
        raise ValueError(f"Unbekannter Zahlungsstatus: {payment_status}")
    project_id = payload.get("project_id")
    asset_id = payload.get("asset_id")
    recurring_cost_id = payload.get("recurring_cost_id")
    _validate_single_assignment(project_id, asset_id, recurring_cost_id)
    skonto_percent = payload.get("skonto_percent")
    return {
        "supplier_id": payload["supplier_id"],
        "supplier_invoice_number": payload.get("supplier_invoice_number") or None,
        "invoice_date": payload["invoice_date"],
        "net_amount": net_amount,
        "tax_rate_pct": tax_rate_pct,
        "due_date": payload.get("due_date"),
        "skonto_percent": Decimal(str(skonto_percent)) if skonto_percent is not None else None,
        "skonto_deadline": payload.get("skonto_deadline"),
        "payment_status": payment_status,
        # payment_date wird beim Verlassen von "bezahlt" bewusst mit zurückgesetzt -- ein
        # stehen gebliebenes altes Zahlungsdatum bei erneut "offen" wäre irreführend.
        "payment_date": payload.get("payment_date") if payment_status == "bezahlt" else None,
        "project_id": project_id,
        "asset_id": asset_id,
        "recurring_cost_id": recurring_cost_id,
        "account_id": payload.get("account_id"),
        "notes": payload.get("notes") or None,
    }


def create_invoice(db: Session, payload: dict) -> dict:
    if db.get(Supplier, payload["supplier_id"]) is None:
        raise ValueError(f"Lieferant #{payload['supplier_id']} wurde nicht gefunden.")
    fields = _payload_fields(payload)
    _validate_referenced_entities(db, fields)
    items = _validate_items_payload(db, payload.get("items"))
    _validate_item_sum(fields["net_amount"], items)
    invoice = IncomingInvoice(**fields)
    invoice.items = [IncomingInvoiceItem(**item) for item in items]
    db.add(invoice)
    db.commit()
    lead_days = get_or_create_incoming_invoice_settings(db).skonto_reminder_lead_days
    return invoice_to_dict(_load(db, invoice.id), lead_days)


def update_invoice(db: Session, invoice_id: int, payload: dict) -> dict | None:
    invoice = db.get(IncomingInvoice, invoice_id)
    if invoice is None:
        return None
    if db.get(Supplier, payload["supplier_id"]) is None:
        raise ValueError(f"Lieferant #{payload['supplier_id']} wurde nicht gefunden.")
    fields = _payload_fields(payload)
    _validate_referenced_entities(db, fields)
    items = _validate_items_payload(db, payload.get("items"))
    _validate_item_sum(fields["net_amount"], items)
    for field, value in fields.items():
        setattr(invoice, field, value)
    # Vollständiger Ersatz der Positionen (Muster IncomingInvoiceItem-Klassendocstring) --
    # cascade="all, delete-orphan" löscht die alten Zeilen, sobald sie aus der Collection
    # entfernt werden.
    invoice.items = [IncomingInvoiceItem(**item) for item in items]
    db.commit()
    lead_days = get_or_create_incoming_invoice_settings(db).skonto_reminder_lead_days
    return invoice_to_dict(_load(db, invoice.id), lead_days)


def delete_invoice(db: Session, invoice_id: int) -> bool:
    invoice = db.get(IncomingInvoice, invoice_id)
    if invoice is None:
        return False
    delete_document_file(invoice.document_filename)
    db.delete(invoice)
    db.commit()
    return True


def set_invoice_document(db: Session, invoice_id: int, *, stored_filename: str, original_filename: str) -> dict | None:
    """Der Router ruft vorher incoming_invoice_documents.py::replace_document() auf (löscht die
    alte Datei bereits, schreibt die neue) -- hier nur noch die DB-Felder setzen."""
    invoice = db.get(IncomingInvoice, invoice_id)
    if invoice is None:
        return None
    invoice.document_filename = stored_filename
    invoice.document_original_name = original_filename
    db.commit()
    lead_days = get_or_create_incoming_invoice_settings(db).skonto_reminder_lead_days
    return invoice_to_dict(_load(db, invoice.id), lead_days)


def remove_invoice_document(db: Session, invoice_id: int) -> dict | None:
    invoice = db.get(IncomingInvoice, invoice_id)
    if invoice is None:
        return None
    delete_document_file(invoice.document_filename)
    invoice.document_filename = None
    invoice.document_original_name = None
    db.commit()
    lead_days = get_or_create_incoming_invoice_settings(db).skonto_reminder_lead_days
    return invoice_to_dict(_load(db, invoice.id), lead_days)


def open_liabilities_summary(db: Session, *, today: date | None = None) -> dict:
    """Summe offener Verbindlichkeiten (payment_status=="offen") -- Muster
    RecurringCost.overview_summary(), hier ohne Kündigungsfristen, dafür mit Skonto-/
    Überfälligkeits-Kennzeichnung."""
    settings = get_or_create_incoming_invoice_settings(db)
    open_invoices = db.scalars(_invoice_query().where(IncomingInvoice.payment_status == "offen")).all()
    total_gross = sum((invoice_gross_amount(i) for i in open_invoices), Decimal("0")).quantize(Decimal("0.01"))
    dicts = [invoice_to_dict(i, settings.skonto_reminder_lead_days, today=today) for i in open_invoices]
    overdue = [d for d in dicts if d["is_overdue"]]
    skonto_due = [d for d in dicts if d["is_skonto_due"]]
    return {
        "open_gross_total": total_gross,
        "open_count": len(open_invoices),
        "overdue_count": len(overdue),
        "skonto_due": skonto_due,
    }


def check_due_skonto_and_create_reminders(db: Session) -> list[int]:
    """On-Demand-Erinnerung (kein Scheduler) -- Muster
    check_due_cancellations_and_create_reminders() (app/recurring_costs.py): läuft nur beim
    Aufruf der Eingangsrechnungen-Liste. Trägt min_visible_role=ROLE_OFFICE_FINANZEN -- eine
    Skontofrist geht nur Finanzen/Admin etwas an. last_skonto_reminder_deadline ist der
    Idempotenz-Stempel, OHNE expliziten Reset -- ändert sich die Frist (Rechnung bearbeitet),
    unterscheidet sie sich automatisch vom alten Stempel; wird die Rechnung bezahlt, greift
    is_skonto_due() ohnehin nicht mehr (payment_status != "offen")."""
    if not is_module_enabled(db, "aufgabenmanagement"):
        return []
    settings = get_or_create_incoming_invoice_settings(db)
    threshold = date.today() + timedelta(days=settings.skonto_reminder_lead_days)
    candidates = db.scalars(
        select(IncomingInvoice).options(selectinload(IncomingInvoice.supplier)).where(
            IncomingInvoice.payment_status == "offen",
            IncomingInvoice.skonto_deadline.is_not(None),
        )
    ).all()
    reminded = []
    for invoice in candidates:
        deadline = invoice.skonto_deadline
        if deadline > threshold:
            continue
        if invoice.last_skonto_reminder_deadline == deadline:
            continue
        supplier_name = invoice.supplier.name if invoice.supplier else "Lieferant"
        skonto_note = f" ({invoice.skonto_percent}% Skonto)" if invoice.skonto_percent else ""
        create_task(
            db, title=f"Skonto sichern: {supplier_name}",
            description=(
                f"Eingangsrechnung von {supplier_name} (Lieferantenrechnungsnr. "
                f"{invoice.supplier_invoice_number or '-'}) -- Skontofrist läuft am "
                f"{deadline.strftime('%d.%m.%Y')} ab{skonto_note}."
            ),
            source_module="buchhaltung", source_label=f"Eingangsrechnung {supplier_name}",
            source_url="/eingangsrechnungen", min_visible_role=ROLE_OFFICE_FINANZEN,
        )
        invoice.last_skonto_reminder_deadline = deadline
        reminded.append(invoice.id)
    if reminded:
        db.commit()
    return reminded
