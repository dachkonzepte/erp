"""Betriebskosten-Übersicht, Schicht 1 -- die Kostenerfassung (seit 1.5.0, Modul
"betriebskosten").

Zwei Kostenquellen bestehen bewusst NEBENEINANDER, keine Migration der einen in die andere
(Nutzerentscheidung, siehe CLAUDE.md "Betriebskosten-Übersicht"): RecurringCost ist der
detaillierte Vertrag (Partner, Kündigungsfrist, Dokument), OperationalAsset.
recurring_cost_per_month (seit 1.4.0) bleibt die schnelle Notiz beim Anlegen eines
Betriebsmittels. overview_summary() unten führt beide in der Summe zusammen und verhindert
dabei die Doppelzählung: zeigt ein RecurringCost auf ein Betriebsmittel, ERSETZT er dessen
monthly_cost in der Summe, statt sie zu ergänzen.

annual_amount ist ein GESPEICHERTES Feld (RecurringCost.annual_amount, app/models.py) --
normalize_to_annual() berechnet es bei jedem Anlegen/Ändern, nie bei der Summierung selbst neu.
Das ist der Andockpunkt für den späteren Verrechnungssatz-Kreislauf (Schicht 3): siehe
app/labor_rate.py::calculate_labor_rate() und LaborRateOverheadSettings.fixed_overhead_value
(Modus "eur") -- die Summe aller aktiven annual_amount-Werte ist der Wert, der dort künftig
automatisch eingesetzt wird.

Kündigungsfrist: cancellation_deadline() ist eine reine Ableitung aus contract_end_date/
notice_period_months (add_months() mit negativem Vorzeichen, app/date_utils.py) -- wird nicht
gespeichert, da sie sich vollständig aus zwei bereits gespeicherten Feldern ergibt (Muster
is_due/is_overdue bei OperationalAsset, nicht next_due_date bei OperationalAssetInspection, das
zusätzlich ein "zuletzt tatsächliches Datum" bräuchte -- hier gibt es das nicht, contract_end_date
ändert sich nur durch eine Vertragsänderung selbst).

Erinnerungs-Aufgabe (check_due_cancellations_and_create_reminders()): On-Demand wie
check_due_asset_inspections_and_create_reminders() (app/operational_assets.py) -- läuft nur beim
Aufruf der Betriebskosten-Übersicht, kein Hintergrundjob. Geht (anders als bei Betriebsmitteln)
NICHT unassigned, sondern trägt min_visible_role=ROLE_OFFICE_FINANZEN (Task, seit 1.5.0) -- eine
Kündigungsfrist geht nur Finanzen/Admin etwas an, nicht die Auftragsbearbeitung."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import event, select
from sqlalchemy.orm import Session, selectinload

from .date_utils import add_months
from .modules import is_module_enabled
from .models import OperationalAsset, RecurringCost, RecurringCostDocument, RecurringCostSettings
from .permissions import ROLE_OFFICE_FINANZEN
from .recurring_cost_documents import delete_document_file
from .tasks import create_task

MODULE_KEY = "betriebskosten"

# Fester Code-Wert statt Optionsgruppe (Muster SEVERITIES/ACTIONS/STATUSES bei Finding) -- der
# Rhythmus bestimmt eine Rechenregel (normalize_to_annual() unten), keine reine Anzeigeliste.
# "einmalig" ist bereits ein gültiger Wert (Punkt 4 der Anfrage: das Modell soll einmalige
# Kosten später ohne Umbau aufnehmen können) -- eine eigene Erfassungsoberfläche dafür ist
# NICHT Teil von Schicht 1, siehe CLAUDE.md.
BILLING_INTERVALS = ("monatlich", "vierteljaehrlich", "halbjaehrlich", "jaehrlich", "einmalig")

# Kalkulatorische Einordnung für den Verrechnungssatz-Kreislauf (Schicht 3, seit 1.5.1, vom
# Betreiber bestätigt seit 1.5.2 -- siehe CLAUDE.md "Betriebskosten-Übersicht" ->
# "Verrechnungssatz-Kreislauf Schicht 3") -- fester Code-Wert wie BILLING_INTERVALS, keine
# Optionsgruppe: die Einordnung bestimmt eine Rechenregel (welche der beiden Gemeinkosten-Summen
# ein Posten speist, siehe app/labor_rate.py::recurring_cost_overhead_proposal()), keine reine
# Anzeigeliste. "keine" ist der restriktive Default -- ein Posten fließt erst nach bewusster
# Einordnung in eine Summe ein. Werte vermeiden bewusst das Wort "variabel": der Code-Bucket
# LaborRateOverheadSettings.variable_overhead_value mischt bereits automatisch addierte
# Verwaltungslöhne hinein (variable_employee_costs) -- "auslastungsabhaengig" markiert einen
# fachlich anderen Begriff von "variabel" (steigt mit der Auslastung), ohne die beiden im Namen
# zu verwechseln.
OVERHEAD_CLASSIFICATIONS = ("keine", "fix", "auslastungsabhaengig")

OVERHEAD_CLASSIFICATION_LABELS = {
    "keine": "Keine Gemeinkosten",
    "fix": "Feste Gemeinkosten",
    "auslastungsabhaengig": (
        "Auslastungsabhängige Kosten (z. B. Kraftstoff, Verschleiß, Entsorgung -- fließt "
        "zusammen mit den Verwaltungslöhnen in den variablen Gemeinkosten-Bucket)"
    ),
}

_ANNUAL_MULTIPLIER = {
    "monatlich": Decimal(12),
    "vierteljaehrlich": Decimal(4),
    "halbjaehrlich": Decimal(2),
    "jaehrlich": Decimal(1),
    "einmalig": Decimal(0),
}


def normalize_to_annual(amount: Decimal, billing_interval: str) -> Decimal:
    """Der zentrale, gespeicherte Wert (RecurringCost.annual_amount) -- "einmalig" liefert
    bewusst 0 (kein laufender Jahresbetrag, fließt nicht in die wiederkehrende Summe ein), der
    Posten selbst bleibt trotzdem in der Liste sichtbar."""
    return (amount * _ANNUAL_MULTIPLIER[billing_interval]).quantize(Decimal("0.01"))


@event.listens_for(RecurringCostDocument, "before_delete")
def _delete_recurring_cost_document_file(mapper, connection, target: RecurringCostDocument) -> None:
    """Feuert für JEDEN ORM-Löschweg -- direkt über delete_cost_document() genauso wie
    kaskadiert über RecurringCost.documents (cascade="all, delete-orphan") beim Löschen des
    ganzen Kostenpostens. Muster app/operational_assets.py."""
    delete_document_file(target.stored_filename)


def cancellation_deadline(contract_end_date: date | None, notice_period_months: int | None) -> date | None:
    """Reine Ableitung, nicht gespeichert -- fehlt eines der beiden Felder, gibt es keine
    berechenbare Frist."""
    if contract_end_date is None or notice_period_months is None:
        return None
    return add_months(contract_end_date, -notice_period_months)


def is_cancellation_due(deadline: date | None, lead_days: int, *, today: date | None = None) -> bool:
    if deadline is None:
        return False
    today = today or date.today()
    return deadline <= today + timedelta(days=lead_days)


def is_cancellation_overdue(deadline: date | None, *, today: date | None = None) -> bool:
    if deadline is None:
        return False
    today = today or date.today()
    return deadline < today


def get_or_create_recurring_cost_settings(db: Session) -> RecurringCostSettings:
    settings = db.get(RecurringCostSettings, 1)
    if settings is None:
        settings = RecurringCostSettings(id=1)
        db.add(settings)
        db.commit()
    return settings


def recurring_cost_settings_to_dict(settings: RecurringCostSettings) -> dict:
    return {"reminder_lead_days": settings.reminder_lead_days}


def update_recurring_cost_settings(db: Session, reminder_lead_days: int) -> dict:
    settings = get_or_create_recurring_cost_settings(db)
    settings.reminder_lead_days = reminder_lead_days
    db.commit()
    return recurring_cost_settings_to_dict(settings)


def _document_to_dict(document: RecurringCostDocument) -> dict:
    return {
        "id": document.id,
        "recurring_cost_id": document.recurring_cost_id,
        "document_type": document.document_type,
        "original_filename": document.original_filename,
        "notes": document.notes,
        "uploaded_at": document.uploaded_at,
    }


def cost_to_dict(cost: RecurringCost, lead_days: int, *, today: date | None = None) -> dict:
    """asset_quick_cost_hint (nur wenn asset_id gesetzt) ist der Transparenz-Hinweis, den der
    Nutzer für die Doppelzählungsfrage verlangt hat -- Muster material_markup_hint
    (app/invoices.py, seit 1.2.23): kein persistiertes Feld, nur ein erklärender Satz in der
    Antwort, damit sichtbar wird, dass die monthly_cost des verknüpften Betriebsmittels wegen
    dieses Postens NICHT zusätzlich in die Summe einfließt."""
    deadline = cancellation_deadline(cost.contract_end_date, cost.notice_period_months)
    asset_hint = None
    if cost.asset_id is not None:
        name = cost.asset.name if cost.asset and cost.asset.resource_id is None else (
            cost.asset.resource.name if cost.asset and cost.asset.resource else None
        )
        asset_hint = (
            f"Ersetzt die monatliche Kosten-Notiz am verknüpften Betriebsmittel"
            f"{f' ({name})' if name else ''} in der Betriebskosten-Summe -- keine Doppelzählung."
        )
    return {
        "id": cost.id,
        "label": cost.label,
        "category": cost.category,
        "overhead_classification": cost.overhead_classification,
        "amount": cost.amount,
        "billing_interval": cost.billing_interval,
        "annual_amount": cost.annual_amount,
        "vendor": cost.vendor,
        "contract_end_date": cost.contract_end_date,
        "notice_period_months": cost.notice_period_months,
        "cancellation_deadline": deadline,
        "is_cancellation_due": is_cancellation_due(deadline, lead_days, today=today),
        "is_cancellation_overdue": is_cancellation_overdue(deadline, today=today),
        "asset_id": cost.asset_id,
        "asset_quick_cost_hint": asset_hint,
        "active": cost.active,
        "notes": cost.notes,
        "documents": [_document_to_dict(d) for d in cost.documents],
        "created_at": cost.created_at,
        "updated_at": cost.updated_at,
    }


def _cost_query():
    return select(RecurringCost).options(
        selectinload(RecurringCost.asset).selectinload(OperationalAsset.resource),
        selectinload(RecurringCost.documents),
    )


def _load(db: Session, cost_id: int) -> RecurringCost | None:
    return db.scalar(_cost_query().where(RecurringCost.id == cost_id))


def get_cost(db: Session, cost_id: int) -> dict | None:
    cost = _load(db, cost_id)
    if cost is None:
        return None
    lead_days = get_or_create_recurring_cost_settings(db).reminder_lead_days
    return cost_to_dict(cost, lead_days)


def list_costs(db: Session, *, include_inactive: bool = True) -> list[dict]:
    lead_days = get_or_create_recurring_cost_settings(db).reminder_lead_days
    query = _cost_query()
    if not include_inactive:
        query = query.where(RecurringCost.active == True)  # noqa: E712
    query = query.order_by(RecurringCost.label)
    return [cost_to_dict(c, lead_days) for c in db.scalars(query).all()]


def _payload_fields(payload: dict) -> dict:
    amount = Decimal(str(payload["amount"]))
    billing_interval = payload["billing_interval"]
    if billing_interval not in BILLING_INTERVALS:
        raise ValueError(f"Unbekannter Rhythmus: {billing_interval}")
    overhead_classification = payload.get("overhead_classification") or "keine"
    if overhead_classification not in OVERHEAD_CLASSIFICATIONS:
        raise ValueError(f"Unbekannte Gemeinkosten-Einordnung: {overhead_classification}")
    return {
        "label": payload["label"].strip(),
        "category": payload.get("category"),
        "overhead_classification": overhead_classification,
        "amount": amount,
        "billing_interval": billing_interval,
        "annual_amount": normalize_to_annual(amount, billing_interval),
        "vendor": payload.get("vendor"),
        "contract_end_date": payload.get("contract_end_date"),
        "notice_period_months": payload.get("notice_period_months"),
        "asset_id": payload.get("asset_id"),
        "active": payload.get("active", True),
        "notes": payload.get("notes"),
    }


def create_cost(db: Session, payload: dict) -> dict:
    asset_id = payload.get("asset_id")
    if asset_id is not None and db.get(OperationalAsset, asset_id) is None:
        raise ValueError(f"Betriebsmittel #{asset_id} wurde nicht gefunden.")
    cost = RecurringCost(**_payload_fields(payload))
    db.add(cost)
    db.commit()
    lead_days = get_or_create_recurring_cost_settings(db).reminder_lead_days
    return cost_to_dict(_load(db, cost.id), lead_days)


def update_cost(db: Session, cost_id: int, payload: dict) -> dict | None:
    cost = db.get(RecurringCost, cost_id)
    if cost is None:
        return None
    asset_id = payload.get("asset_id")
    if asset_id is not None and db.get(OperationalAsset, asset_id) is None:
        raise ValueError(f"Betriebsmittel #{asset_id} wurde nicht gefunden.")
    for field, value in _payload_fields(payload).items():
        setattr(cost, field, value)
    db.commit()
    lead_days = get_or_create_recurring_cost_settings(db).reminder_lead_days
    return cost_to_dict(_load(db, cost.id), lead_days)


def delete_cost(db: Session, cost_id: int) -> bool:
    cost = db.get(RecurringCost, cost_id)
    if cost is None:
        return False
    for document in list(cost.documents):
        delete_document_file(document.stored_filename)
    db.delete(cost)
    db.commit()
    return True


def create_cost_document(db: Session, cost_id: int, *, document_type: str, notes: str | None,
                          stored_filename: str, original_filename: str) -> dict | None:
    """Muster create_asset_document() (app/operational_assets.py) -- der Router validiert
    Content-Type/Größe und speichert die Datei VOR diesem Aufruf, prüft die Existenz des
    Kostenpostens deshalb VOR dem Speichern der Datei, nicht danach."""
    cost = db.get(RecurringCost, cost_id)
    if cost is None:
        return None
    document = RecurringCostDocument(
        recurring_cost_id=cost_id, document_type=document_type.strip(), notes=(notes or None),
        stored_filename=stored_filename, original_filename=original_filename,
    )
    db.add(document)
    db.commit()
    return _document_to_dict(document)


def delete_cost_document(db: Session, document_id: int) -> bool:
    """db.delete() löst das before_delete-Event oben aus, das die Datei von der Festplatte
    entfernt."""
    document = db.get(RecurringCostDocument, document_id)
    if document is None:
        return False
    db.delete(document)
    db.commit()
    return True


def overview_summary(db: Session) -> dict:
    """Führt beide Kostenquellen zusammen (Nutzervorgabe, siehe Moduldocstring) und verhindert
    dabei die Doppelzählung: ein Betriebsmittel, das über mindestens einen aktiven RecurringCost
    verknüpft ist, liefert seine eigene recurring_cost_per_month NICHT zusätzlich in die Summe --
    der Kostenposten ersetzt sie, ergänzt sie nicht. Monats- und Jahressumme, Kündigungsfristen
    hervorgehoben (fällig/überfällig getrennt ausgewiesen) -- der eigentliche Schritt zum
    Verrechnungssatz bleibt Schicht 3, hier nur die reine Erfassungs-Übersicht."""
    lead_days = get_or_create_recurring_cost_settings(db).reminder_lead_days
    costs = [c for c in db.scalars(_cost_query().where(RecurringCost.active == True)).all()]  # noqa: E712
    cost_dicts = [cost_to_dict(c, lead_days) for c in costs]

    linked_asset_ids = {c.asset_id for c in costs if c.asset_id is not None}
    annual_from_costs = sum((c.annual_amount for c in costs), Decimal("0"))

    # Drei getrennte Summen nach kalkulatorischer Einordnung (Schicht 3, seit 1.5.1) --
    # annual_total bleibt unverändert die Summe ALLER Posten (auch "keine"), für die
    # bestehende Anzeige; die drei Gruppen sind zusätzlich, nicht ersetzend.
    annual_fixed_from_costs = sum(
        (c.annual_amount for c in costs if c.overhead_classification == "fix"), Decimal("0")
    )
    annual_usage_dependent_from_costs = sum(
        (c.annual_amount for c in costs if c.overhead_classification == "auslastungsabhaengig"),
        Decimal("0"),
    )
    annual_none_from_costs = sum(
        (c.annual_amount for c in costs if c.overhead_classification == "keine"), Decimal("0")
    )

    assets_with_quick_cost = db.scalars(
        select(OperationalAsset).where(
            OperationalAsset.recurring_cost_per_month.is_not(None),
            OperationalAsset.active == True,  # noqa: E712
        )
    ).all()
    annual_from_asset_quick_costs = sum(
        (a.recurring_cost_per_month * Decimal(12) for a in assets_with_quick_cost if a.id not in linked_asset_ids),
        Decimal("0"),
    )

    annual_total = annual_from_costs + annual_from_asset_quick_costs
    monthly_total = (annual_total / Decimal(12)).quantize(Decimal("0.01"))

    due = [c for c in cost_dicts if c["is_cancellation_due"] and not c["is_cancellation_overdue"]]
    overdue = [c for c in cost_dicts if c["is_cancellation_overdue"]]

    return {
        "monthly_total": monthly_total.quantize(Decimal("0.01")),
        "annual_total": annual_total.quantize(Decimal("0.01")),
        "annual_fixed_from_costs": annual_fixed_from_costs.quantize(Decimal("0.01")),
        "annual_usage_dependent_from_costs": annual_usage_dependent_from_costs.quantize(Decimal("0.01")),
        "annual_none_from_costs": annual_none_from_costs.quantize(Decimal("0.01")),
        "cost_count": len(costs),
        "asset_quick_cost_count": sum(1 for a in assets_with_quick_cost if a.id not in linked_asset_ids),
        "cancellations_due": due,
        "cancellations_overdue": overdue,
    }


def check_due_cancellations_and_create_reminders(db: Session) -> list[int]:
    """On-Demand-Erinnerung (kein Scheduler) -- Muster
    check_due_asset_inspections_and_create_reminders() (app/operational_assets.py): läuft nur
    beim Aufruf der Betriebskosten-Übersicht. last_reminder_due_date ist derselbe
    Idempotenz-Stempel, OHNE expliziten Reset -- ändert sich die Kündigungsfrist (Vertrags-
    änderung), unterscheidet sie sich automatisch vom alten Stempel.

    Anders als bei Betriebsmitteln geht die Aufgabe NICHT unassigned an "das ganze Büro",
    sondern trägt min_visible_role=ROLE_OFFICE_FINANZEN -- eine Kündigungsfrist geht nur
    Finanzen/Admin etwas an, nicht die Auftragsbearbeitung (Nutzervorgabe)."""
    if not is_module_enabled(db, "aufgabenmanagement"):
        return []
    settings = get_or_create_recurring_cost_settings(db)
    threshold = date.today() + timedelta(days=settings.reminder_lead_days)
    active_costs = db.scalars(
        select(RecurringCost).where(
            RecurringCost.active == True,  # noqa: E712
            RecurringCost.contract_end_date.is_not(None),
            RecurringCost.notice_period_months.is_not(None),
        )
    ).all()
    reminded = []
    for cost in active_costs:
        deadline = cancellation_deadline(cost.contract_end_date, cost.notice_period_months)
        if deadline is None or deadline > threshold:
            continue
        if cost.last_reminder_due_date == deadline:
            continue
        create_task(
            db, title=f"Kündigungsfrist beachten: {cost.label}",
            description=(
                f"Kostenposten \"{cost.label}\" -- Kündigungsfrist läuft am "
                f"{deadline.strftime('%d.%m.%Y')} ab (Vertragsende "
                f"{cost.contract_end_date.strftime('%d.%m.%Y')}, "
                f"{cost.notice_period_months} Monate Kündigungsfrist)."
            ),
            source_module="betriebskosten", source_label=f"Kostenposten {cost.label}",
            source_url="/betriebskosten", min_visible_role=ROLE_OFFICE_FINANZEN,
        )
        cost.last_reminder_due_date = deadline
        reminded.append(cost.id)
    if reminded:
        db.commit()
    return reminded
