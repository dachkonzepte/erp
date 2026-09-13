"""Rechnungswesen (seit 1.0.33).

Ein Auftrag kann mehrere Rechnungen haben: Abschlagsrechnungen (pauschal oder
nach Leistungsstand), eine Schlussrechnung, und Stornorechnungen zu bereits
versendeten Rechnungen. Siehe Invoice/InvoiceItem in models.py für die
Feldbeschreibungen und die Begründung der Soll/Ist-Mechanik.

Kernprinzip Soll/Ist: ist_quantity auf einer Rechnungsposition ist immer der
KUMULIERTE Stand zum Zeitpunkt dieser Rechnung (z.B. "80 von 100 m² insgesamt
fertig"), nicht der Anteil dieser einen Rechnung. Was auf einer konkreten
Rechnung abgerechnet wird (billed_quantity/billed_total), ist die Differenz
zum kumulierten Stand der letzten vorherigen, bereits versendeten Rechnung für
dieselbe Auftragsposition -- siehe berechne_abgerechnete_menge().

Nummernvergabe: eine Rechnung bekommt ihre invoice_number erst beim Versenden
(entwurf -> versendet), nicht beim Anlegen -- verworfene Entwürfe hinterlassen
so keine Lücken in der Nummernfolge (GoBD). Ab 'versendet' ist eine Rechnung
unveränderlich; Korrekturen laufen ausschließlich über eine Stornorechnung.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .calculation import effective_material_sale_price, get_or_create_settings
from .models import Invoice, InvoiceItem, Material, Order, OrderItem, PaymentTerm, ServiceReportMaterial, TaxKey, TimeEntry
from .option_settings import default_option_value
from .payment_terms import get_default_payment_term
from .settings import issue_number

INVOICE_TYPES = {"abschlag_pauschal", "abschlag_leistungsstand", "schluss", "aufwand", "storno"}
EDITABLE_STATUS = "entwurf"
PROGRESS_INVOICE_TYPES = ("abschlag_pauschal", "abschlag_leistungsstand")


def is_invoice_editable(invoice: Invoice) -> bool:
    return invoice.status == EDITABLE_STATUS


def _snapshot_order_fields(db: Session, order: Order) -> dict:
    tax_notice_text = None
    if order.tax_key_id is not None:
        key = db.get(TaxKey, order.tax_key_id)
        tax_notice_text = key.notice_text if key else None
    return {
        "customer_name": order.customer_name,
        "customer_number": order.customer_number,
        "customer_address": order.customer_address,
        "property_name": order.property_name,
        "property_address": order.property_address,
        "vat_rate": order.vat_rate,
        "tax_key_id": order.tax_key_id,
        "tax_notice_text": tax_notice_text,
    }


def _count_progress_invoices(db: Session, order_id: int) -> int:
    """Anzahl bereits vorhandener Abschlagsrechnungen (pauschal + nach
    Leistungsstand, nicht storniert) für diesen Auftrag -- Grundlage für die
    automatische Durchnummerierung ('1. Abschlagsrechnung', '2. ...').
    Entwürfe zählen bewusst mit: die Nummerierung ist rein beschreibend
    (progress_description), nicht die rechtlich bedeutsame invoice_number,
    daher darf sie auch verworfene Entwürfe grob mitzählen -- die Bezeichnung
    bleibt ohnehin frei änderbar."""
    return db.scalar(
        select(func.count()).select_from(Invoice).where(
            Invoice.order_id == order_id,
            Invoice.invoice_type.in_(PROGRESS_INVOICE_TYPES),
            Invoice.status != "storniert",
        )
    ) or 0


def _find_matching_payment_term(db: Session, label: str) -> PaymentTerm | None:
    """Robusterer Abgleich als eine reine Gleichheitsprüfung -- Leerzeichen
    am Rand und Groß-/Kleinschreibung werden ignoriert, damit z.B. ein Auftrag
    mit '14 Tage Netto ' (Leerzeichen/Großschreibung) trotzdem die passende
    Zahlungsbedingung '14 Tage netto' findet."""
    normalized = label.strip().lower()
    for term in db.scalars(select(PaymentTerm)).all():
        if term.label.strip().lower() == normalized:
            return term
    return None


def _default_payment_terms_for_order(db: Session, order: Order) -> tuple[str | None, int, object, int | None, str | None]:
    """(Bezeichnung, Tage, Skonto-Prozent, Skonto-Tage, Text-Vorlage) für
    eine neue Rechnung. Die im Auftrag hinterlegte Zahlungsbedingung hat
    Vorrang -- sie wird unverändert als Bezeichnung übernommen; Tage/Skonto/
    Textvorlage werden über eine gleichnamige PaymentTerm ermittelt, falls
    vorhanden (Neuanlagen ab 1.0.39 verwenden dieselben kurzen Bezeichnungen
    wie hier, ältere Aufträge mit dem früheren langen Fließtext-Wert finden
    ggf. keine exakte Übereinstimmung -- dann werden Tage/Skonto/Textvorlage
    über den Kunden-/Systemstandard geschätzt, die Bezeichnung des Auftrags
    bleibt trotzdem erhalten). Nur wenn der Auftrag gar keine Zahlungsbedingung
    trägt, wird komplett auf Kunden-/Systemstandard zurückgefallen."""
    _, fallback_days, fallback_skonto_pct, fallback_skonto_days, fallback_template = _fallback_payment_terms(db, order)
    if order.payment_terms:
        matching = _find_matching_payment_term(db, order.payment_terms)
        if matching:
            return order.payment_terms, matching.days, matching.skonto_percent, matching.skonto_days, matching.text_template
        return order.payment_terms, fallback_days, fallback_skonto_pct, fallback_skonto_days, fallback_template
    return _fallback_payment_terms(db, order)


def _fallback_payment_terms(db: Session, order: Order) -> tuple[str | None, int, object, int | None, str | None]:
    """Kunden-Standard, sonst Systemstandard, sonst 14 Tage ohne Bezeichnung/Skonto/Textvorlage."""
    customer = order.project.customer if order.project else None
    term = None
    if customer is not None and customer.profile and customer.profile.default_payment_term_id:
        term = db.get(PaymentTerm, customer.profile.default_payment_term_id)
    if term is None:
        term = get_default_payment_term(db)
    if term is None:
        return None, 14, None, None, None
    return term.label, term.days, term.skonto_percent, term.skonto_days, term.text_template


def _default_invoice_header_fields(db: Session, order: Order, *, due_date: date | None) -> dict:
    label, days, skonto_percent, skonto_days, text_template = _default_payment_terms_for_order(db, order)
    return {
        **_snapshot_order_fields(db, order),
        "payment_terms": label,
        "due_date": due_date or (date.today() + timedelta(days=days)),
        "skonto_percent": skonto_percent,
        "skonto_days": skonto_days,
        "payment_terms_text_template": text_template,
        "intro_text": default_option_value(db, "invoice_intro_texts"),
        "outro_text": default_option_value(db, "invoice_outro_texts"),
    }


def get_previous_cumulative_ist(
    db: Session, order_id: int, source_order_item_id: int, *, exclude_invoice_id: int | None = None,
) -> Decimal:
    """Kumulierter Ist-Stand der zeitlich letzten, bereits versendeten oder
    bezahlten (NICHT: Entwurf, NICHT: stornierte) Rechnung für dieselbe
    Auftragsposition. Entwürfe zählen bewusst nicht mit, da sie noch nicht
    endgültig sind -- eine stornierte Rechnung zählt bewusst nicht mit, da ihr
    Stand damit rückgängig gemacht wurde.

    invoice_type wird zusätzlich auf abschlag_leistungsstand/schluss begrenzt:
    eine Storno-Rechnung übernimmt ist_quantity unverändert von der Rechnung,
    die sie storniert (nur billed_quantity/-total werden negiert, siehe
    create_storno_draft) -- sie selbst würde sonst fälschlich als neuer,
    aktueller Stand erkannt, obwohl sie das genaue Gegenteil bedeutet."""
    stmt = (
        select(InvoiceItem.ist_quantity)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .where(
            Invoice.order_id == order_id,
            Invoice.status.in_(["versendet", "bezahlt"]),
            Invoice.invoice_type.in_(["abschlag_leistungsstand", "schluss"]),
            InvoiceItem.source_order_item_id == source_order_item_id,
        )
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    )
    if exclude_invoice_id is not None:
        stmt = stmt.where(Invoice.id != exclude_invoice_id)
    result = db.scalar(stmt)
    return result if result is not None else Decimal("0")


def compute_billed_quantity_and_total(
    db: Session, order_id: int, invoice_id: int | None, source_order_item_id: int | None,
    ist_quantity: Decimal, unit_price: Decimal,
) -> tuple[Decimal, Decimal]:
    """Berechnet, was auf EINER Rechnung für eine Position tatsächlich
    abgerechnet wird. Ohne Bezug zu einer Auftragsposition (neue Position/
    Nachtrag) wird die komplette ist_quantity abgerechnet, da es keinen
    vorherigen Stand gibt."""
    if source_order_item_id is None:
        billed_quantity = ist_quantity
    else:
        previous = get_previous_cumulative_ist(
            db, order_id, source_order_item_id, exclude_invoice_id=invoice_id,
        )
        billed_quantity = ist_quantity - previous
    return billed_quantity, billed_quantity * unit_price


def compute_invoice_totals(invoice: Invoice) -> dict:
    """net/vat/gross wie bei Order nicht gespeichert, sondern immer frisch
    berechnet -- für abschlag_pauschal aus lump_sum_net, sonst aus der Summe
    von billed_total über alle Positionen (unabhängig von der Ist=0-
    Anzeigeregel, die nur die Darstellung betrifft, nicht die Summe)."""
    if invoice.invoice_type == "abschlag_pauschal":
        net = invoice.lump_sum_net or Decimal("0")
    else:
        net = sum((item.billed_total for item in invoice.items), Decimal("0"))
    vat = net * invoice.vat_rate / Decimal("100")
    return {"net_total": net, "vat_total": vat, "gross_total": net + vat}


def _copy_order_items_with_default_ist(
    db: Session, invoice: Invoice, order: Order, *, full_completion: bool,
) -> None:
    """Kopiert alle Auftragspositionen als Rechnungspositionen. full_completion
    steuert den Ausgangswert von ist_quantity: bei einer Schlussrechnung wird
    sinnvollerweise von 100% Fertigstellung ausgegangen (soll_quantity), bei
    einer Abschlagsrechnung nach Leistungsstand vom zuletzt kumulierten Stand
    (0, falls noch nie abgerechnet) -- beides vom Nutzer danach anpassbar."""
    for order_item in order.items:
        if not order_item.include_in_total:
            continue
        if full_completion:
            ist_quantity = order_item.quantity
        else:
            ist_quantity = get_previous_cumulative_ist(db, order.id, order_item.id)
        billed_quantity, billed_total = compute_billed_quantity_and_total(
            db, order.id, invoice.id, order_item.id, ist_quantity, order_item.unit_price,
        )
        db.add(InvoiceItem(
            invoice_id=invoice.id, source_order_item_id=order_item.id,
            sort_order=order_item.sort_order, position_number=order_item.position_number,
            gaeb_oz=order_item.gaeb_oz, short_text=order_item.short_text, long_text=order_item.long_text,
            unit=order_item.unit, unit_price=order_item.unit_price,
            soll_quantity=order_item.quantity, ist_quantity=ist_quantity,
            billed_quantity=billed_quantity, billed_total=billed_total,
        ))


LUMP_SUM_ITEM_UNIT = "pschl."


def _sync_lump_sum_pauschal_item(db: Session, invoice: Invoice) -> None:
    """Haelt die EINZIGE InvoiceItem-Zeile einer abschlag_pauschal-Rechnung synchron zu
    lump_sum_net/progress_description (seit 1.3.24, CLAUDE.md "Pauschale Abschlagsrechnung ohne
    Positionstabelle") -- vorher hatte dieser Rechnungstyp ueberhaupt keine Position, PDF und
    Bildschirm zeigten nur einen Betrag ohne jede Beschreibung dessen, was pauschal abgerechnet
    wird.

    WICHTIG, REINE PROJEKTION: diese Zeile ist niemals unabhaengig editierbar. lump_sum_net
    bleibt die alleinige Quelle der Wahrheit fuer den Rechnungsbetrag (compute_invoice_totals()
    liest bei diesem Typ weiterhin ausschliesslich lump_sum_net, nie eine Positionssumme) --
    add_invoice_item()/update_invoice_item()/remove_invoice_item() lehnen jede Änderung an dieser
    Zeile über den allgemeinen Positionsweg deshalb explizit ab (ValueError). Eine künftige
    Positionsbearbeitung speziell für abschlag_pauschal darf NICHT gebaut werden, ohne dieses
    Prinzip zu überdenken -- zwei unabhängig editierbare Zahlen für denselben Betrag wären genau
    der Fehler, der beim Mahntext (CLAUDE.md "Mahnwesen: Löschen/Versenden/Bearbeiten") bewusst
    vermieden wurde. Menge/Einheit sind fest (1 / "pschl.") und tragen keine eigene Bedeutung --
    einzig Bezeichnung und Betrag stammen aus den beiden editierbaren Feldern des Pauschalbetrag-
    Kärtchens."""
    existing = next(iter(invoice.items), None)
    text = invoice.progress_description or "Abschlagszahlung gemäß Auftrag"
    amount = invoice.lump_sum_net if invoice.lump_sum_net is not None else Decimal("0")
    if existing is None:
        db.add(InvoiceItem(
            invoice_id=invoice.id, sort_order=10, position_number="1",
            short_text=text, long_text=None, unit=LUMP_SUM_ITEM_UNIT, unit_price=amount,
            soll_quantity=Decimal("1"), ist_quantity=Decimal("1"),
            billed_quantity=Decimal("1"), billed_total=amount,
        ))
    else:
        existing.short_text = text
        existing.unit_price = amount
        existing.billed_total = amount


def create_abschlag_pauschal(
    db: Session, order: Order, *, lump_sum_net: Decimal, progress_description: str | None = None,
    due_date: date | None = None,
) -> Invoice:
    if not progress_description:
        progress_description = f"{_count_progress_invoices(db, order.id) + 1}. Abschlagsrechnung"
    invoice = Invoice(
        order_id=order.id, invoice_type="abschlag_pauschal", status="entwurf",
        lump_sum_net=lump_sum_net, progress_description=progress_description,
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()  # invoice.id fuer die Projektions-Position
    _sync_lump_sum_pauschal_item(db, invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_abschlag_leistungsstand(db: Session, order: Order, *, due_date: date | None = None) -> Invoice:
    progress_description = f"{_count_progress_invoices(db, order.id) + 1}. Abschlagsrechnung (nach Leistungsstand)"
    invoice = Invoice(
        order_id=order.id, invoice_type="abschlag_leistungsstand", status="entwurf",
        progress_description=progress_description,
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()
    _copy_order_items_with_default_ist(db, invoice, order, full_completion=False)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_schlussrechnung(db: Session, order: Order, *, due_date: date | None = None) -> Invoice:
    invoice = Invoice(
        order_id=order.id, invoice_type="schluss", status="entwurf",
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()
    _copy_order_items_with_default_ist(db, invoice, order, full_completion=True)
    db.commit()
    db.refresh(invoice)
    return invoice


def _time_entry_employee_name(employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip() if employee else ""


def create_invoice_from_time_entries(
    db: Session, order: Order, time_entries: list[TimeEntry], materials: list[ServiceReportMaterial],
    *, due_date: date | None = None,
) -> Invoice:
    """Erzeugt eine Rechnung aus Ist-Zeitbuchungen UND verbrauchtem Material statt aus
    Auftragspositionen (seit 1.2.2, Material seit 1.2.23) -- Grundlage für zeitbasiert
    abgerechnete Reparaturen/kleine Einsätze (siehe app/service_reports.py, dessen Unterschrift
    die zugehörige "Rechnung erstellen"-Aufgabe für den Sachbearbeiter auslöst). Nur bereits
    gebuchte, nicht mehr laufende Zeiten (status="booked") werden berücksichtigt, gruppiert nach
    Mitarbeiter + Tätigkeit. Ein einheitlicher Stundenpreis für alle Zeitpositionen aus dem
    globalen Stundenverrechnungssatz (CalculationSettings.labor_rate, id ohne Katalogbezug).

    Material (seit 1.2.23, siehe list_materials_for_invoicing() in app/service_reports.py --
    nur unterschriebene Berichte liefern Zeilen): Zeitpositionen zuerst, danach Material.
    Katalogmaterial (material_id gesetzt) wird nach (material_id, unit) gruppiert und mit dem
    AKTUELLEN Katalogpreis MIT dem globalen Materialaufschlag bepreist
    (effective_material_sale_price(), CalculationSettings.material_markup_pct -- derselbe
    Mechanismus, der auch im Leistungskatalog aus Einkaufs- den Verkaufspreis macht, siehe
    app/calculation.py::build_calculation()). Frei eingetipptes Material (material_id leer) wird
    NIE zusammengefasst, auch nicht bei identischem Text, und bekommt unit_price=0 -- das Büro
    trägt den Preis im Rechnungsentwurf nach, die Position soll dabei sichtbar bleiben, nicht
    fehlen.

    Ergebnis ist wie jede andere Rechnung nur ein Entwurf, die Positionen bleiben vor dem
    Versenden vollständig prüf-/änderbar."""
    booked = [e for e in time_entries if e.status == "booked" and e.hours]
    if not booked and not materials:
        raise ValueError("Weder abrechenbare Zeitbuchungen noch Material für diesen Auftrag vorhanden.")

    # Stundenpreis/Materialaufschlag VOR dem Anlegen der Rechnung abfragen: get_or_create_settings()
    # führt bei einer noch nie gespeicherten CalculationSettings-Zeile eine eigene Schema-
    # Introspektion (sa_inspect) plus einen eigenen Commit aus. Käme das NACH einem bereits
    # geflushten, aber noch nicht committeten Invoice, kann das je nach Verbindungs-/Pooling-
    # Verhalten die noch ungesicherte Zeile verwerfen -- also lieber vorher abfragen, wenn die
    # Session noch keinen eigenen ungesicherten Stand trägt.
    settings = get_or_create_settings(db)
    hourly_rate = settings.labor_rate

    invoice = Invoice(
        order_id=order.id, invoice_type="aufwand", status="entwurf",
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()

    grouped: dict[tuple[int, str], dict] = {}
    for entry in booked:
        key = (entry.employee_id, entry.activity or "")
        bucket = grouped.setdefault(key, {"employee": entry.employee, "activity": entry.activity, "hours": Decimal("0")})
        bucket["hours"] += Decimal(entry.hours)

    ordered_buckets = sorted(
        grouped.values(), key=lambda b: (_time_entry_employee_name(b["employee"]), b["activity"] or ""),
    )
    for index, bucket in enumerate(ordered_buckets, start=1):
        employee_name = _time_entry_employee_name(bucket["employee"])
        db.add(InvoiceItem(
            invoice_id=invoice.id, source_order_item_id=None, sort_order=index * 10,
            position_number="", short_text=bucket["activity"] or "Ausgeführte Arbeiten",
            long_text=(f"Ausgeführt von {employee_name}" if employee_name else ""),
            unit="Std.", unit_price=hourly_rate, soll_quantity=None,
            ist_quantity=bucket["hours"], billed_quantity=bucket["hours"], billed_total=bucket["hours"] * hourly_rate,
        ))

    # Materialpositionen -- Katalogzeilen nach (material_id, unit) gruppiert und summiert, freie
    # Zeilen nie zusammengefasst (siehe Docstring).
    catalog_groups: dict[tuple[int, str], Decimal] = {}
    free_rows: list[ServiceReportMaterial] = []
    for m in materials:
        if m.material_id is not None:
            key = (m.material_id, m.unit or "")
            catalog_groups[key] = catalog_groups.get(key, Decimal("0")) + Decimal(m.quantity)
        else:
            free_rows.append(m)

    material_lines: list[tuple[str, str, Decimal, Decimal]] = []  # (short_text, unit, quantity, unit_price)
    materials_by_id = {
        material.id: material
        for material in (db.get(Material, mid) for mid, _unit in catalog_groups) if material is not None
    }
    for (material_id, unit), qty in sorted(
        catalog_groups.items(), key=lambda kv: materials_by_id[kv[0][0]].name if kv[0][0] in materials_by_id else "",
    ):
        material = materials_by_id.get(material_id)
        if material is None:
            continue  # Katalogeintrag inzwischen entfernt -- kann heute über die App nicht passieren, defensiv
        unit_price = effective_material_sale_price(material.purchase_price, material.price_basis, settings.material_markup_pct)
        material_lines.append((material.name, unit or material.unit, qty, unit_price))
    for m in sorted(free_rows, key=lambda r: r.description):
        material_lines.append((m.description, m.unit or "", Decimal(m.quantity), Decimal("0")))

    for offset, (short_text, unit, qty, unit_price) in enumerate(material_lines, start=1):
        index = len(ordered_buckets) + offset
        db.add(InvoiceItem(
            invoice_id=invoice.id, source_order_item_id=None, sort_order=index * 10,
            position_number="", short_text=short_text, long_text="", unit=unit, unit_price=unit_price,
            soll_quantity=None, ist_quantity=qty, billed_quantity=qty, billed_total=qty * unit_price,
        ))

    db.commit()
    db.refresh(invoice)
    return invoice


def add_invoice_item(
    db: Session, invoice: Invoice, *, short_text: str, long_text: str, unit: str,
    unit_price: Decimal, ist_quantity: Decimal, source_order_item_id: int | None = None,
    soll_quantity: Decimal | None = None, position_number: str | None = None,
    sort_order: int | None = None,
) -> InvoiceItem:
    """Für Nachträge/neue Positionen (source_order_item_id=None) sowie um
    ausdrücklich eine bestehende Auftragsposition erneut hinzuzufügen, falls
    sie zuvor entfernt wurde."""
    if not is_invoice_editable(invoice):
        raise ValueError("Nur Rechnungen im Entwurf können bearbeitet werden.")
    if invoice.invoice_type == "abschlag_pauschal":
        raise ValueError(
            "Pauschale Abschlagsrechnungen haben nur die eine, automatisch erzeugte Position -- "
            "Bezeichnung und Betrag über das Pauschalbetrag-Feld ändern."
        )
    billed_quantity, billed_total = compute_billed_quantity_and_total(
        db, invoice.order_id, invoice.id, source_order_item_id, ist_quantity, unit_price,
    )
    item = InvoiceItem(
        invoice_id=invoice.id, source_order_item_id=source_order_item_id,
        sort_order=sort_order if sort_order is not None else (len(invoice.items) + 1) * 10,
        position_number=position_number or "",
        short_text=short_text, long_text=long_text, unit=unit, unit_price=unit_price,
        soll_quantity=soll_quantity, ist_quantity=ist_quantity,
        billed_quantity=billed_quantity, billed_total=billed_total,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_invoice_item(
    db: Session, invoice: Invoice, item: InvoiceItem, *, short_text: str | None = None,
    long_text: str | None = None, unit: str | None = None, unit_price: Decimal | None = None,
    ist_quantity: Decimal | None = None,
) -> InvoiceItem:
    if not is_invoice_editable(invoice):
        raise ValueError("Nur Rechnungen im Entwurf können bearbeitet werden.")
    if invoice.invoice_type == "abschlag_pauschal":
        raise ValueError(
            "Die Position einer pauschalen Abschlagsrechnung ist eine reine Projektion von "
            "Bezeichnung/Betrag -- bitte dort ändern, siehe _sync_lump_sum_pauschal_item()."
        )
    if short_text is not None:
        item.short_text = short_text
    if long_text is not None:
        item.long_text = long_text
    if unit is not None:
        item.unit = unit
    if unit_price is not None:
        item.unit_price = unit_price
    if ist_quantity is not None:
        item.ist_quantity = ist_quantity
    # Neuberechnung immer, auch wenn nur unit_price sich geändert hat.
    item.billed_quantity, item.billed_total = compute_billed_quantity_and_total(
        db, invoice.order_id, invoice.id, item.source_order_item_id, item.ist_quantity, item.unit_price,
    )
    db.commit()
    db.refresh(item)
    return item


def remove_invoice_item(db: Session, invoice: Invoice, item_id: int) -> bool:
    if not is_invoice_editable(invoice):
        raise ValueError("Nur Rechnungen im Entwurf können bearbeitet werden.")
    if invoice.invoice_type == "abschlag_pauschal":
        raise ValueError("Die Position einer pauschalen Abschlagsrechnung kann nicht einzeln entfernt werden.")
    item = next((i for i in invoice.items if i.id == item_id), None)
    if item is None:
        return False
    # Aus der Collection entfernen, nicht db.delete(item) direkt -- siehe
    # ausführlicher Kommentar bei remove_material_from_service in services.py,
    # derselbe delete-orphan-Cascade-Konflikt gilt hier für Invoice.items.
    invoice.items.remove(item)
    db.commit()
    return True


def finalize_and_send_invoice(db: Session, invoice: Invoice) -> Invoice:
    """entwurf -> versendet: vergibt die Rechnungsnummer aus dem Nummernkreis
    und sperrt die Rechnung endgültig für Bearbeitung. Bei einer Storno-
    Rechnung wird im selben Schritt die referenzierte Original-Rechnung auf
    'storniert' gesetzt -- so entsteht nie ein Zwischenzustand mit einem noch
    verwerfbaren Storno-Entwurf, aber einer bereits als storniert markierten
    Original-Rechnung."""
    if invoice.status != "entwurf":
        raise ValueError("Nur Rechnungen im Entwurf können versendet werden.")
    invoice.invoice_number = issue_number(db, "invoice")
    invoice.status = "versendet"
    if invoice.invoice_type == "storno" and invoice.storno_of_invoice_id is not None:
        original = db.get(Invoice, invoice.storno_of_invoice_id)
        if original is not None:
            original.status = "storniert"
    db.commit()
    db.refresh(invoice)
    return invoice


def mark_invoice_paid(db: Session, invoice: Invoice, *, paid_date: date | None = None) -> Invoice:
    if invoice.status != "versendet":
        raise ValueError("Nur versendete Rechnungen können als bezahlt markiert werden.")
    invoice.status = "bezahlt"
    invoice.paid_date = paid_date or date.today()
    db.commit()
    db.refresh(invoice)
    return invoice


def delete_invoice_draft(db: Session, invoice: Invoice) -> None:
    """Löscht eine Rechnung unwiderruflich -- nur im Entwurf möglich. Bewusst
    keine Nummernkreis-Rücknahme nötig: ein Entwurf hat noch keine
    Rechnungsnummer erhalten (die wird erst in finalize_and_send_invoice()
    vergeben), Löschen kann also keine Lücke in der Rechnungsnummernfolge
    reißen -- GoBD-technisch unproblematisch. Eine Stornorechnung im Entwurf
    darf ebenfalls gelöscht werden: das Original wird erst beim tatsächlichen
    Versand des Storno auf 'storniert' gesetzt (siehe finalize_and_send_invoice),
    ist also zu diesem Zeitpunkt noch unberührt und bleibt es auch."""
    if invoice.status != EDITABLE_STATUS:
        raise ValueError("Nur Rechnungen im Entwurf können gelöscht werden.")
    db.delete(invoice)
    db.commit()


def create_storno_draft(db: Session, original: Invoice) -> Invoice:
    """Erzeugt den Entwurf einer Stornorechnung zu einer bereits versendeten
    oder bezahlten Rechnung -- kehrt Betrag und alle Positionen um (negatives
    Vorzeichen). Die Original-Rechnung wird NICHT sofort auf 'storniert'
    gesetzt, sondern erst, wenn dieser Entwurf tatsächlich versendet wird
    (siehe finalize_and_send_invoice) -- ein verworfener Storno-Entwurf lässt
    die Original-Rechnung also unangetastet."""
    if original.status not in ("versendet", "bezahlt"):
        raise ValueError("Nur versendete oder bezahlte Rechnungen können storniert werden.")
    storno = Invoice(
        order_id=original.order_id, invoice_type="storno", status="entwurf",
        storno_of_invoice_id=original.id,
        customer_name=original.customer_name, customer_number=original.customer_number,
        customer_address=original.customer_address, property_name=original.property_name,
        property_address=original.property_address, vat_rate=original.vat_rate,
        tax_key_id=original.tax_key_id, tax_notice_text=original.tax_notice_text,
        progress_description=f"Stornierung zu Rechnung {original.invoice_number or '(Entwurf)'}",
        lump_sum_net=(-original.lump_sum_net if original.lump_sum_net is not None else None),
    )
    db.add(storno)
    db.flush()
    for item in original.items:
        db.add(InvoiceItem(
            invoice_id=storno.id, source_order_item_id=item.source_order_item_id,
            sort_order=item.sort_order, position_number=item.position_number, gaeb_oz=item.gaeb_oz,
            short_text=item.short_text, long_text=item.long_text, unit=item.unit, unit_price=item.unit_price,
            soll_quantity=item.soll_quantity, ist_quantity=item.ist_quantity,
            billed_quantity=-item.billed_quantity, billed_total=-item.billed_total,
        ))
    db.commit()
    db.refresh(storno)
    return storno


def visible_items(invoice: Invoice) -> list[InvoiceItem]:
    """Positionen mit ist_quantity=0 werden auf der Rechnung selbst nicht
    angezeigt (bleiben aber in der Datenbank für die Soll/Ist-Historie
    bestehen) -- von der PDF-/Anzeigelogik zu verwenden, nicht list(invoice.items)."""
    return [item for item in invoice.items if item.ist_quantity != 0]


def update_invoice_header(
    db: Session, invoice: Invoice, *, due_date: date | None, progress_description: str | None,
    lump_sum_net: Decimal | None, intro_text: str | None, outro_text: str | None,
    outro_text_2: str | None, payment_terms: str | None,
) -> Invoice:
    if not is_invoice_editable(invoice):
        raise ValueError("Nur Rechnungen im Entwurf können bearbeitet werden.")
    invoice.due_date = due_date
    invoice.progress_description = progress_description
    if invoice.invoice_type == "abschlag_pauschal":
        invoice.lump_sum_net = lump_sum_net
        _sync_lump_sum_pauschal_item(db, invoice)
    invoice.intro_text = intro_text
    invoice.outro_text = outro_text
    invoice.outro_text_2 = outro_text_2
    invoice.payment_terms = payment_terms
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice_payment_term(db: Session, invoice: Invoice, payment_term_id: int) -> Invoice:
    """Setzt Bezeichnung, Fälligkeitsdatum UND Skonto aus einer gewählten
    Zahlungsbedingung neu (invoice_date + Tage) -- die Dropdown-Auswahl aus
    der Erfassungsoberfläche, getrennt von update_invoice_header, da dort
    due_date auch weiterhin direkt (unabhängig von einer Zahlungsbedingung)
    gesetzt werden kann."""
    if not is_invoice_editable(invoice):
        raise ValueError("Nur Rechnungen im Entwurf können bearbeitet werden.")
    term = db.get(PaymentTerm, payment_term_id)
    if term is None:
        raise ValueError("Zahlungsbedingung nicht gefunden.")
    invoice.payment_terms = term.label
    invoice.due_date = invoice.invoice_date + timedelta(days=term.days)
    invoice.skonto_percent = term.skonto_percent
    invoice.skonto_days = term.skonto_days
    invoice.payment_terms_text_template = term.text_template
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice_tax_key(db: Session, invoice: Invoice, tax_key_id: int) -> Invoice:
    """Setzt tax_key_id, vat_rate UND den eingefrorenen Hinweistext neu --
    wie bei Skonto/Zahlungsbedingung eingefroren, nicht live nachgeladen (der
    Grund steht ausführlich am Invoice.tax_notice_text-Feld in models.py)."""
    if not is_invoice_editable(invoice):
        raise ValueError("Nur Rechnungen im Entwurf können bearbeitet werden.")
    key = db.get(TaxKey, tax_key_id)
    if key is None:
        raise ValueError("Steuerschlüssel nicht gefunden.")
    invoice.tax_key_id = tax_key_id
    invoice.vat_rate = key.vat_rate
    invoice.tax_notice_text = key.notice_text
    db.commit()
    db.refresh(invoice)
    return invoice


def format_payment_terms_sentence(invoice: Invoice) -> str:
    """Automatisch aus Fälligkeitsdatum und Skonto erzeugter Satz mit echten
    Daten (nicht nur der abstrakten Bezeichnung wie '14 Tage netto') --
    zusammen mit dem Schlusstext auf Rechnung/PDF angezeigt. Absichtlich hier
    und nicht in invoice_pdf.py erzeugt, damit Oberfläche und PDF exakt
    denselben Text zeigen, nicht zwei unabhängig gepflegte Formulierungen.

    Ist auf der Zahlungsbedingung eine eigene Textvorlage hinterlegt (seit
    1.0.42, invoice.payment_terms_text_template), wird die stattdessen
    verwendet -- mit denselben, per .replace() ersetzten Platzhaltern wie
    unten. Ein unbekannter/falsch geschriebener Platzhalter bleibt einfach
    als Text stehen (kein Fehler), damit ein Tippfehler in der Vorlage nicht
    die ganze Rechnung blockiert."""
    if invoice.due_date is None:
        return ""
    due_str = invoice.due_date.strftime("%d.%m.%Y")
    has_skonto = bool(invoice.skonto_percent) and invoice.skonto_days is not None
    skonto_date_str = percent_text = amount_text = ""
    if has_skonto:
        skonto_date = invoice.invoice_date + timedelta(days=invoice.skonto_days)
        totals = compute_invoice_totals(invoice)
        skonto_amount = (totals["gross_total"] * invoice.skonto_percent / Decimal("100")).quantize(Decimal("0.01"))
        skonto_date_str = skonto_date.strftime("%d.%m.%Y")
        percent_text = f"{invoice.skonto_percent:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        amount_text = f"{skonto_amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if invoice.payment_terms_text_template:
        return (
            invoice.payment_terms_text_template
            .replace("{faelligkeitsdatum}", due_str)
            .replace("{skontodatum}", skonto_date_str)
            .replace("{skontoprozent}", percent_text)
            .replace("{skontobetrag}", amount_text)
        )

    sentence = f"Zahlbar rein netto bis zum {due_str}."
    if has_skonto:
        sentence += (
            f" Bei Zahlung bis zum {skonto_date_str} gewähren wir "
            f"{percent_text} % Skonto, das entspricht {amount_text} €."
        )
    return sentence


def invoice_to_dict(invoice: Invoice) -> dict:
    """Rechnung inkl. Positionen und berechneter Summen für API-Antworten und
    PDF-Erzeugung. visible_items() (Ist=0 ausgeblendet) wird bewusst NICHT
    hier angewendet -- die Erfassungsoberfläche muss auch Positionen mit
    Ist=0 sehen und bearbeiten können, nur die PDF-Ausgabe blendet sie aus."""
    totals = compute_invoice_totals(invoice)
    items = sorted(invoice.items, key=lambda x: (x.sort_order, x.id))
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "order_id": invoice.order_id,
        # Für die Breadcrumb (seit 1.3.23, Muster property.html/roof_area.html) -- invoice_to_dict()
        # kannte bisher nur order_id, nicht den Weg zurück zu Auftrag/Projekt/Kunde.
        "order_number": invoice.order.order_number,
        "project_id": invoice.order.project_id,
        "project_number": invoice.order.project.project_number,
        "customer_id": invoice.order.project.customer_id,
        "invoice_type": invoice.invoice_type,
        "status": invoice.status,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "paid_date": invoice.paid_date,
        "storno_of_invoice_id": invoice.storno_of_invoice_id,
        "customer_name": invoice.customer_name,
        "customer_number": invoice.customer_number,
        "customer_address": invoice.customer_address,
        "property_name": invoice.property_name,
        "property_address": invoice.property_address,
        "vat_rate": invoice.vat_rate,
        "lump_sum_net": invoice.lump_sum_net,
        "progress_description": invoice.progress_description,
        "intro_text": invoice.intro_text,
        "outro_text": invoice.outro_text,
        "outro_text_2": invoice.outro_text_2,
        "payment_terms": invoice.payment_terms,
        "tax_key_id": invoice.tax_key_id,
        "tax_notice_text": invoice.tax_notice_text,
        "skonto_percent": invoice.skonto_percent,
        "skonto_days": invoice.skonto_days,
        "payment_terms_sentence": format_payment_terms_sentence(invoice),
        "is_editable": is_invoice_editable(invoice),
        "is_overdue": (
            invoice.status == "versendet" and invoice.due_date is not None and invoice.due_date < date.today()
        ),
        "items": [
            {
                "id": i.id, "source_order_item_id": i.source_order_item_id, "sort_order": i.sort_order,
                "position_number": i.position_number, "gaeb_oz": i.gaeb_oz, "short_text": i.short_text,
                "long_text": i.long_text, "unit": i.unit, "unit_price": i.unit_price,
                "soll_quantity": i.soll_quantity, "ist_quantity": i.ist_quantity,
                "billed_quantity": i.billed_quantity, "billed_total": i.billed_total,
            }
            for i in items
        ],
        "email_sent_at": invoice.email_sent_at,
        "email_sent_to": invoice.email_sent_to,
        "recipient_email": get_invoice_recipient_email(invoice),
        **totals,
    }


def list_invoices_for_order(db: Session, order_id: int) -> list[Invoice]:
    return db.scalars(
        select(Invoice).where(Invoice.order_id == order_id).order_by(Invoice.created_at)
    ).all()


def get_invoice(db: Session, invoice_id: int) -> Invoice | None:
    return db.get(Invoice, invoice_id)


def invoice_summary_for_order(db: Session, order_id: int) -> tuple[int, bool]:
    """(Anzahl nicht stornierter Rechnungen, vollständig abgerechnet) -- für
    die Anzeige in Projektmappe/Auftragsliste, ohne dort die komplette
    Rechnungsliste laden zu müssen. 'Vollständig abgerechnet' heißt: eine
    finalisierte (nicht mehr im Entwurf, nicht stornierte) Schlussrechnung
    existiert."""
    invoices = list_invoices_for_order(db, order_id)
    active = [i for i in invoices if i.status != "storniert"]
    fully_invoiced = any(i.invoice_type == "schluss" and i.status in ("versendet", "bezahlt") for i in active)
    return len(active), fully_invoiced


def compute_order_billing_progress(db: Session, order_id: int) -> dict:
    """Wie viel von einem Auftrag bereits (verbindlich) abgerechnet wurde,
    Netto und Brutto -- für die Anzeige im Auftrag selbst. Zählt nur
    finalisierte Rechnungen (versendet/bezahlt); Entwürfe zählen bewusst
    nicht mit, da sie noch nicht endgültig sind. Stornierte Rechnungen UND
    die zugehörigen Storno-Rechnungen selbst zählen bewusst BEIDE nicht mit
    (nicht: eine zählt positiv, die andere negativ) -- sonst würde eine
    stornierte Position fälschlich einen negativen Betrag beitragen, statt
    schlicht wieder auf 'nicht abgerechnet' zurückzufallen."""
    invoices = list_invoices_for_order(db, order_id)
    counted = [i for i in invoices if i.status in ("versendet", "bezahlt") and i.invoice_type != "storno"]
    invoiced_net = Decimal("0")
    invoiced_gross = Decimal("0")
    for inv in counted:
        totals = compute_invoice_totals(inv)
        invoiced_net += totals["net_total"]
        invoiced_gross += totals["gross_total"]
    return {"invoiced_net": invoiced_net, "invoiced_gross": invoiced_gross}


def list_all_invoices(db: Session, *, status: str | None = None) -> list[Invoice]:
    """Systemweite Rechnungsliste für die Finanzen-Übersicht -- unabhängig
    vom jeweiligen Auftrag/Projekt, mit optionalem Status-Filter."""
    stmt = select(Invoice).order_by(Invoice.created_at.desc())
    if status:
        stmt = stmt.where(Invoice.status == status)
    return db.scalars(stmt).all()


def list_invoices_for_project(db: Session, project_id: int) -> list[Invoice]:
    """Alle Rechnungen über alle Aufträge eines Projekts hinweg gebündelt --
    für den eigenen Rechnungen-Reiter in der Projektmappe."""
    return db.scalars(
        select(Invoice)
        .join(Order, Invoice.order_id == Order.id)
        .where(Order.project_id == project_id)
        .order_by(Invoice.created_at.desc())
    ).all()


def invoice_overview_row(invoice: Invoice) -> dict:
    """Leichtgewichtige Zeile für die Finanzen-Übersicht (ohne Positionen,
    dafür mit Auftrags-/Projektbezug) -- bewusst getrennt von
    invoice_to_dict(), das für Detailansicht/PDF die volle Positionsliste
    mitliefert, die hier für eine Liste vieler Rechnungen unnötig wäre."""
    totals = compute_invoice_totals(invoice)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_type": invoice.invoice_type,
        "status": invoice.status,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "is_overdue": (
            invoice.status == "versendet" and invoice.due_date is not None and invoice.due_date < date.today()
        ),
        "customer_name": invoice.customer_name,
        "order_id": invoice.order_id,
        "order_number": invoice.order.order_number if invoice.order else None,
        "project_number": invoice.order.project.project_number if invoice.order and invoice.order.project else None,
        "gross_total": totals["gross_total"],
    }


DEFAULT_INVOICE_EMAIL_SUBJECT = "Rechnung {rechnungsnummer}"
DEFAULT_INVOICE_EMAIL_BODY = (
    "Sehr geehrte Damen und Herren,\n\n"
    "anbei erhalten Sie unsere Rechnung {rechnungsnummer} vom {rechnungsdatum} "
    "über {gesamtbetrag}. Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF.\n\n"
    "Mit freundlichen Grüßen"
)


def get_invoice_recipient_email(invoice: Invoice) -> str | None:
    """Aktuelle, live nachgeschlagene Kunden-E-Mail -- analog zu
    get_reminder_recipient_email() in app/reminders.py. Bewusst defensiv
    gegen fehlende Zwischenglieder (order/project/customer)."""
    order = invoice.order
    customer = order.project.customer if order and order.project else None
    return (customer.email or None) if customer else None


def send_invoice_email(db: Session, invoice: Invoice, *, to_email: str | None = None) -> Invoice:
    """Versendet eine bereits finalisierte Rechnung tatsächlich per E-Mail
    (seit 1.0.82) -- analog zu send_reminder_email() in app/reminders.py.
    Kann auch mehrfach aufgerufen werden (z.B. erneuter Versand), aktualisiert
    email_sent_at/email_sent_to bei jedem Aufruf neu.

    to_email überschreibt die automatisch ermittelte Kunden-E-Mail nur für
    DIESEN Versand, ändert aber nie die Kundenstammdaten selbst.

    PDF-Erzeugung und E-Mail-Versand erfolgen hier lokal importiert (nicht
    am Modulanfang), um Zirkel-Importe zu vermeiden -- analog zur
    Begründung bei send_reminder_email()."""
    from datetime import datetime as _datetime

    from .document_email_templates import get_email_template
    from .email_sending import send_email_with_attachment
    from .invoice_pdf import build_invoice_pdf

    if invoice.status == "entwurf":
        raise ValueError("Nur bereits versendete Rechnungen können per E-Mail versendet werden.")

    recipient = (to_email or "").strip() or get_invoice_recipient_email(invoice)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")

    totals = compute_invoice_totals(invoice)
    money = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"  # noqa: E731
    placeholders = {
        "{rechnungsnummer}": invoice.invoice_number or "",
        "{rechnungsdatum}": invoice.invoice_date.strftime("%d.%m.%Y"),
        "{faelligkeitsdatum}": invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "",
        "{gesamtbetrag}": money(totals["gross_total"]),
        "{kundenname}": invoice.customer_name,
    }

    template = get_email_template(db, "invoice")
    subject_template = (template.subject_template if template else None) or DEFAULT_INVOICE_EMAIL_SUBJECT
    body_template = (template.body_template if template else None) or DEFAULT_INVOICE_EMAIL_BODY
    subject, body = subject_template, body_template
    for placeholder, value in placeholders.items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)

    pdf_bytes = build_invoice_pdf(db, invoice)
    send_email_with_attachment(
        db, to_email=recipient, subject=subject, body_text=body,
        attachment_bytes=pdf_bytes, attachment_filename=f"{invoice.invoice_number}.pdf",
    )

    invoice.email_sent_at = _datetime.utcnow()
    invoice.email_sent_to = recipient
    db.commit()
    db.refresh(invoice)
    return invoice
