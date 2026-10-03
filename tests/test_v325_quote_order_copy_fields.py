"""Version 1.8.21 -- Punkt 5: jedes Feld an Angebot und Auftrag ist eingeordnet.

Anlass: tax_key_id und outro_text_2 gab es an Angebot UND Auftrag, aber weder die Beauftragung noch
der Abgleich kopierten sie -- ein Auftrag verlor still den Steuerschlüssel (Hinweistext im PDF) und
den zweiten Schlusstext. Diese Datei hält fest, woher jede Spalte eines Auftrags kommt und warum
jede Spalte eines Angebots übernommen wird oder nicht:

- ORDER_FIELDS: jede Spalte der Auftrags-Tabellen -- entweder übernommen (Quelle + wann) oder
  EIGEN mit Begründung.
- QUOTE_NOT_COPIED: jede Spalte der Angebots-Tabellen, die NICHT Quelle einer Auftragsspalte ist,
  mit Begründung.

Ein neues Feld an einer der Tabellen ohne Eintrag hier macht test_every_field_is_classified() rot.
Die beiden Verhaltenstests prüfen, dass "übernommen" auch stimmt: nach dem Beauftragen und nach dem
Abgleich (bzw. dass ein nur beim Beauftragen übernommenes Feld den Abgleich übersteht).
"""

from datetime import date
from decimal import Decimal

from app.models import (
    Employee, Order, OrderItem, OrderItemCalculationSnapshot, OrderItemMaterialSnapshot, OrderSection, Quote,
    QuoteDocumentMeta, QuoteEmployeeAssignment, QuoteItem, QuoteItemCalculation, QuoteItemLayout,
    QuoteItemMaterialCalculation, QuoteSection, TaxKey,
)
from app.orders import create_order_from_quote, load_order, order_matches_source_quote, sync_order_from_source_quote
from app.projects import ensure_quote_structure, load_quote
from tests.test_v153_mahnwesen import db_session
from tests.test_v325_contract_basis import make_quote

BEIDE = "beim Beauftragen und beim Abgleich"
NUR_BEAUFTRAGEN = "nur beim Beauftragen"


def von(source: str, wann: str = BEIDE) -> tuple:
    return ("von", source, wann)


def eigen(grund: str) -> tuple:
    return ("eigen", grund)


ORDER_FIELDS: dict[type, dict[str, tuple]] = {
    Order: {
        "id": eigen("Primärschlüssel"),
        "order_number": eigen("eigener Nummernkreis"),
        "project_id": von("Quote.project_id", NUR_BEAUFTRAGEN),
        "source_quote_id": von("Quote.id", NUR_BEAUFTRAGEN),
        "quote_number_snapshot": von("Quote.quote_number"),
        "title": von("Quote.title"),
        "status": eigen("Auftragsstatus (beauftragt … storniert), unabhängig vom Angebotsstatus"),
        "vat_rate": von("Quote.vat_rate"),
        "tax_key_id": von("Quote.tax_key_id"),
        "intro_text": von("Quote.intro_text"),
        "outro_text": von("Quote.outro_text"),
        "outro_text_2": von("Quote.outro_text_2"),
        "contract_basis": von("QuoteDocumentMeta.contract_basis"),  # außer am Auftrag geändert, test_v325_contract_basis.py
        "contract_basis_manual": eigen("am Auftrag mit Begründung geändert"),
        "customer_name": eigen("Schnappschuss aus dem Kunden des Projekts, nicht aus dem Angebot"),
        "customer_number": eigen("Schnappschuss aus dem Kunden des Projekts"),
        "customer_address": eigen("Schnappschuss aus dem Kunden des Projekts"),
        "property_name": eigen("Schnappschuss aus dem Objekt des Projekts"),
        "property_address": eigen("Schnappschuss aus dem Objekt des Projekts"),
        "order_date": eigen("im Beauftragen-Dialog eingegeben"),
        "execution_start": eigen("im Beauftragen-Dialog eingegeben"),
        "execution_end": eigen("im Beauftragen-Dialog eingegeben"),
        # Seit 1.8.32 (vorher ging der Freitext verloren, Nebenbefund 1.8.21); danach am Auftrag änderbar.
        "execution_period": von("QuoteDocumentMeta.execution_period", NUR_BEAUFTRAGEN),
        "payment_terms": von("QuoteDocumentMeta.payment_terms", NUR_BEAUFTRAGEN),  # Vorbelegung, wenn der Dialog nichts angibt
        "remarks": eigen("im Beauftragen-Dialog eingegeben"),
        "caseworker_employee_id": von("QuoteEmployeeAssignment.caseworker_employee_id", NUR_BEAUFTRAGEN),  # Vorbelegung
        "project_manager_employee_id": eigen("im Beauftragen-Dialog eingegeben"),
        "email_sent_at": eigen("Versandnachweis des Auftrags"),
        "email_sent_to": eigen("Versandnachweis des Auftrags"),
        # Seit 1.8.46: am Auftrag bewusst festgelegt (Vorschlag übernehmen oder mit Begründung), nie aus dem Angebot.
        "work_kind": eigen("am Auftrag festgelegt (app/warranty.py)"),
        "warranty_months": eigen("am Auftrag festgelegt (app/warranty.py)"),
        "warranty_days": eigen("am Auftrag festgelegt (app/warranty.py)"),
        "created_at": eigen("technisch"),
        "updated_at": eigen("technisch"),
    },
    OrderSection: {
        "id": eigen("Primärschlüssel"),
        "order_id": eigen("Zugehörigkeit zum Auftrag"),
        "parent_id": von("QuoteSection.parent_id"),  # über die Zuordnung der Titel abgebildet
        "source_quote_section_id": von("QuoteSection.id"),
        "title": von("QuoteSection.title"),
        "description": von("QuoteSection.description"),
        "sort_order": von("QuoteSection.sort_order"),
        "section_number": von("QuoteSection.section_number"),
    },
    OrderItem: {
        "id": eigen("Primärschlüssel"),
        "order_id": eigen("Zugehörigkeit zum Auftrag"),
        "section_id": von("QuoteItemLayout.section_id"),  # über die Zuordnung der Titel abgebildet
        "source_quote_item_id": von("QuoteItem.id"),
        "sort_order": von("QuoteItemLayout.sort_order"),
        "position_number": von("QuoteItem.position_number"),
        "gaeb_oz": von("QuoteItem.gaeb_oz"),
        "position_type": von("QuoteItem.position_type"),
        "source_external_id": von("QuoteItem.source_external_id"),
        "short_text": von("QuoteItem.short_text"),
        "long_text": von("QuoteItem.long_text"),
        "quantity": von("QuoteItem.quantity"),
        "unit": von("QuoteItem.unit"),
        "unit_price": von("QuoteItem.unit_price"),
        "include_in_total": von("QuoteItemLayout.include_in_total"),
    },
    OrderItemCalculationSnapshot: {
        "id": eigen("Primärschlüssel"),
        "order_item_id": eigen("Zugehörigkeit zur Auftragsposition"),
        "site_time_minutes": von("QuoteItemCalculation.site_time_minutes"),
        "workshop_time_minutes": von("QuoteItemCalculation.workshop_time_minutes"),
        "labor_rate": von("QuoteItemCalculation.labor_rate"),
        "material_markup_pct": von("QuoteItemCalculation.material_markup_pct"),
        "equipment_cost": von("QuoteItemCalculation.equipment_cost"),
        "subcontractor_cost": von("QuoteItemCalculation.subcontractor_cost"),
        "other_cost": von("QuoteItemCalculation.other_cost"),
        "overhead_pct": von("QuoteItemCalculation.overhead_pct"),
        "risk_profit_pct": von("QuoteItemCalculation.risk_profit_pct"),
        "effective_sale_price": von("QuoteItem.unit_price"),
    },
    OrderItemMaterialSnapshot: {
        "id": eigen("Primärschlüssel"),
        "calculation_id": eigen("Zugehörigkeit zur Kalkulation der Auftragsposition"),
        "article_number": von("QuoteItemMaterialCalculation.article_number"),
        "name": von("QuoteItemMaterialCalculation.name"),
        "unit": von("QuoteItemMaterialCalculation.unit"),
        "quantity": von("QuoteItemMaterialCalculation.quantity"),
        "waste_pct": von("QuoteItemMaterialCalculation.waste_pct"),
        "purchase_price": von("QuoteItemMaterialCalculation.purchase_price"),
        "price_basis": von("QuoteItemMaterialCalculation.price_basis"),
    },
}

QUOTE_NOT_COPIED: dict[str, str] = {
    "Quote.status": "Angebotsstatus; Beauftragen setzt ihn auf beauftragt, der Auftrag hat einen eigenen",
    "Quote.source_format": "Herkunft des Angebots-LV (manuell/GAEB), für den Auftrag ohne Bedeutung",
    "Quote.gaeb_exchange_phase": "GAEB-Austauschphase des Angebots-Imports",
    "Quote.email_sent_at": "Versandnachweis des Angebots",
    "Quote.email_sent_to": "Versandnachweis des Angebots",
    "Quote.created_at": "technisch",
    "Quote.updated_at": "technisch",
    "QuoteDocumentMeta.id": "technisch",
    "QuoteDocumentMeta.quote_id": "Zugehörigkeit zum Angebot",
    "QuoteDocumentMeta.updated_at": "technisch",
    "QuoteDocumentMeta.quote_date": "Angebotsdatum; der Auftrag hat order_date aus dem Beauftragen-Dialog",
    "QuoteDocumentMeta.valid_until": "Bindefrist des Angebots, mit der Beauftragung erledigt",
    "QuoteDocumentMeta.contact_person": "Anzeigename; der Auftrag übernimmt die Person selbst (QuoteEmployeeAssignment). "
                                        "Ein alter Freitext-Name ohne Mitarbeiter geht dabei nicht mit (Nebenbefund 1.8.21)",
    "QuoteDocumentMeta.internal_note": "interne Notiz zum Angebot",
    "QuoteEmployeeAssignment.id": "technisch",
    "QuoteEmployeeAssignment.quote_id": "Zugehörigkeit zum Angebot",
    "QuoteEmployeeAssignment.updated_at": "technisch",
    "QuoteSection.quote_id": "Zugehörigkeit zum Angebot",
    "QuoteSection.created_at": "technisch",
    "QuoteSection.updated_at": "technisch",
    "QuoteItem.quote_id": "Zugehörigkeit zum Angebot",
    "QuoteItem.created_at": "technisch",
    "QuoteItem.source_service_id": "Katalogbezug; der Auftrag hält die Kalkulation als Schnappschuss, nicht den Verweis",
    "QuoteItem.sort_order": "nur Rückfall ohne Layoutzeile; maßgeblich ist QuoteItemLayout.sort_order",
    "QuoteItem.source_unit_price": "Katalogpreis zum Vergleich im Editor; vereinbart ist unit_price",
    "QuoteItemLayout.id": "technisch",
    "QuoteItemLayout.quote_item_id": "Zugehörigkeit zur Angebotsposition",
    "QuoteItemLayout.updated_at": "technisch",
    "QuoteItemCalculation.id": "technisch",
    "QuoteItemCalculation.quote_item_id": "Zugehörigkeit zur Angebotsposition",
    "QuoteItemCalculation.created_at": "technisch",
    "QuoteItemCalculation.updated_at": "technisch",
    "QuoteItemCalculation.manual_sale_price": "Eingabehilfe der Kalkulation; das Ergebnis steht in unit_price "
                                              "und wird als effective_sale_price eingefroren",
    "QuoteItemCalculation.notes": "Kalkulationsnotiz des Angebots",
    "QuoteItemMaterialCalculation.id": "technisch",
    "QuoteItemMaterialCalculation.calculation_id": "Zugehörigkeit zur Kalkulation",
    "QuoteItemMaterialCalculation.source_material_id": "Katalogbezug",
    "QuoteItemMaterialCalculation.source_quantity": "Katalogwert zum Vergleich im Editor",
    "QuoteItemMaterialCalculation.source_purchase_price": "Katalogwert zum Vergleich im Editor",
}

QUOTE_MODELS = [Quote, QuoteDocumentMeta, QuoteEmployeeAssignment, QuoteSection, QuoteItem, QuoteItemLayout,
                QuoteItemCalculation, QuoteItemMaterialCalculation]


def _columns(model) -> set[str]:
    return {c.name for c in model.__table__.columns}


def test_every_field_is_classified():
    problems = []
    for model, spec in ORDER_FIELDS.items():
        cols = _columns(model)
        for name in sorted(cols - set(spec)):
            problems.append(f"{model.__name__}.{name}: neu am Auftrag -- in ORDER_FIELDS eintragen (von … oder eigen(Begründung))")
        for name in sorted(set(spec) - cols):
            problems.append(f"{model.__name__}.{name}: steht in ORDER_FIELDS, gibt es aber nicht mehr")
    sources = {entry[1] for spec in ORDER_FIELDS.values() for entry in spec.values() if entry[0] == "von"}
    quote_columns = {f"{m.__name__}.{c}" for m in QUOTE_MODELS for c in _columns(m)}
    for name in sorted(quote_columns - sources - set(QUOTE_NOT_COPIED)):
        problems.append(f"{name}: neu am Angebot -- in den Auftrag übernehmen (ORDER_FIELDS) oder in QUOTE_NOT_COPIED begründen")
    for name in sorted(sources & set(QUOTE_NOT_COPIED)):
        problems.append(f"{name}: steht als übernommen UND als nicht übernommen")
    for name in sorted((sources | set(QUOTE_NOT_COPIED)) - quote_columns):
        problems.append(f"{name}: steht in der Liste, gibt es am Angebot aber nicht mehr")
    for name, reason in QUOTE_NOT_COPIED.items():
        if not reason.strip():
            problems.append(f"{name}: ohne Begründung")
    assert not problems, "\n".join(problems)


# --- Verhalten ------------------------------------------------------------------------------------

def _build(db):
    """Angebot mit einem Wert in JEDEM übernommenen Feld, der sich von der Vorgabe unterscheidet."""
    quote = make_quote(db, is_consumer=False)
    keys = [TaxKey(label="Paragraf 13b", vat_rate=Decimal("0"), notice_text="Steuerschuldnerschaft des Leistungsempfaengers"),
            TaxKey(label="Regel", vat_rate=Decimal("7"), notice_text="ermaessigt")]
    staff = [Employee(first_name="Sabine", last_name="Sach"), Employee(first_name="Otto", last_name="Anders")]
    db.add_all(keys + staff); db.flush()
    quote.tax_key_id, quote.vat_rate = keys[0].id, Decimal("0")
    quote.intro_text, quote.outro_text, quote.outro_text_2 = "Vortext", "Schlusstext", "Zweiter Schlusstext"
    meta, _, _ = ensure_quote_structure(db, quote)
    meta.payment_terms, meta.contract_basis = "14 Tage netto", "bgb"
    meta.execution_period = "KW 42 bis 44, witterungsabhängig"
    db.add(QuoteEmployeeAssignment(quote_id=quote.id, caseworker_employee_id=staff[0].id))
    parent = QuoteSection(quote_id=quote.id, title="Dach", description="Beschreibung", sort_order=20, section_number="01")
    db.add(parent); db.flush()
    child = QuoteSection(quote_id=quote.id, parent_id=parent.id, title="Eindeckung", description="Kind", sort_order=30, section_number="01.01")
    other = QuoteSection(quote_id=quote.id, title="Rinne", description="Zweiter", sort_order=40, section_number="02")
    db.add_all([child, other]); db.flush()
    item = quote.items[0]
    item.position_number, item.gaeb_oz, item.position_type = "01.01.0010", "01.01.0010", "bedarf"
    item.source_external_id, item.short_text, item.long_text = "EXT-1", "Ziegel", "Langtext"
    item.quantity, item.unit, item.unit_price = Decimal("12.5"), "m2", Decimal("81.25")
    layout = ensure_quote_structure(db, quote)[2][item.id]
    layout.section_id, layout.sort_order, layout.include_in_total = child.id, 70, False
    calc = QuoteItemCalculation(quote_item_id=item.id, site_time_minutes=Decimal("45"), workshop_time_minutes=Decimal("5"),
                                labor_rate=Decimal("42.5"), material_markup_pct=Decimal("15"), equipment_cost=Decimal("3"),
                                subcontractor_cost=Decimal("4"), other_cost=Decimal("5"), overhead_pct=Decimal("10"),
                                risk_profit_pct=Decimal("8"))
    db.add(calc); db.flush()
    db.add(QuoteItemMaterialCalculation(calculation_id=calc.id, name="Frankfurter Pfanne", article_number="FP-1", unit="Stk",
                                        quantity=Decimal("13.2"), waste_pct=Decimal("10"), purchase_price=Decimal("1.2"),
                                        price_basis=Decimal("100")))
    db.commit()
    return load_quote(db, quote.id), keys, staff, (parent, child, other)


def _change_everything(db, quote, keys, staff, sections):
    """Jede Quelle eines BEIDE-Felds UND jede Quelle eines NUR_BEAUFTRAGEN-Felds ändern."""
    parent, child, other = sections
    quote.quote_number, quote.title = "A-NEU", "Neuer Titel"
    quote.tax_key_id, quote.vat_rate = keys[1].id, Decimal("7")
    quote.intro_text, quote.outro_text, quote.outro_text_2 = "Vortext neu", "Schlusstext neu", "Zweiter neu"
    meta, _, layouts = ensure_quote_structure(db, quote)
    meta.contract_basis, meta.payment_terms = "vob_b", "30 Tage netto"
    meta.execution_period = "KW 50"
    assignment = db.query(QuoteEmployeeAssignment).filter_by(quote_id=quote.id).one()
    assignment.caseworker_employee_id = staff[1].id
    for section, suffix in ((parent, "P"), (child, "K"), (other, "O")):
        section.title += suffix; section.description += suffix; section.sort_order += 1; section.section_number += suffix
    child.parent_id = other.id
    item = quote.items[0]
    item.position_number, item.gaeb_oz, item.position_type = "02.0020", "02.0020", "normal"
    item.source_external_id, item.short_text, item.long_text = "EXT-2", "Schiefer", "Langtext neu"
    item.quantity, item.unit, item.unit_price = Decimal("3"), "Stk", Decimal("99.99")
    layouts[item.id].section_id, layouts[item.id].sort_order, layouts[item.id].include_in_total = other.id, 80, True
    calc = item.project_calculation
    for field in ("site_time_minutes", "workshop_time_minutes", "labor_rate", "material_markup_pct", "equipment_cost",
                  "subcontractor_cost", "other_cost", "overhead_pct", "risk_profit_pct"):
        setattr(calc, field, getattr(calc, field) + 1)
    material = calc.materials[0]
    material.name, material.article_number, material.unit = "Biberschwanz", "BS-2", "m2"
    material.quantity, material.waste_pct, material.purchase_price, material.price_basis = Decimal("2"), Decimal("3"), Decimal("4"), Decimal("1")
    db.commit()


def _quote_values(db, quote) -> dict[str, dict]:
    """Quellwerte je Angebotszeile, nach der Quell-ID der Auftragszeile geordnet."""
    meta, sections, layouts = ensure_quote_structure(db, quote)
    assignment = db.query(QuoteEmployeeAssignment).filter_by(quote_id=quote.id).one_or_none()
    rows = {"header": {"Quote": quote, "QuoteDocumentMeta": meta, "QuoteEmployeeAssignment": assignment},
            "sections": {s.id: {"QuoteSection": s} for s in sections},
            "items": {}, "calcs": {}, "materials": {}}
    for item in quote.items:
        rows["items"][item.id] = {"QuoteItem": item, "QuoteItemLayout": layouts[item.id]}
        if item.project_calculation is not None:
            rows["calcs"][item.id] = {"QuoteItemCalculation": item.project_calculation, "QuoteItem": item}
            for pos, material in enumerate(item.project_calculation.materials):
                rows["materials"][(item.id, pos)] = {"QuoteItemMaterialCalculation": material}
    values = {}
    for group, by_key in rows.items():
        if group == "header":
            by_key = {"header": by_key}
        for key, objects in by_key.items():
            values[(group, key)] = {
                f"{name}.{col}": getattr(obj, col) for name, obj in objects.items() if obj is not None
                for col in _columns(type(obj))
            }
    return values


def _order_rows(order) -> dict:
    """Auftragszeilen nach derselben Quell-ID wie _quote_values()."""
    source_of_section = {s.id: s.source_quote_section_id for s in order.sections}
    rows = {("header", "header"): (Order, order, {})}
    for s in order.sections:
        rows[("sections", s.source_quote_section_id)] = (OrderSection, s, {"parent_id": source_of_section.get(s.parent_id)})
    for i in order.items:
        rows[("items", i.source_quote_item_id)] = (OrderItem, i, {"section_id": source_of_section.get(i.section_id)})
        if i.calculation_snapshot is not None:
            rows[("calcs", i.source_quote_item_id)] = (OrderItemCalculationSnapshot, i.calculation_snapshot, {})
            for pos, m in enumerate(sorted(i.calculation_snapshot.materials, key=lambda x: x.id)):
                rows[("materials", (i.source_quote_item_id, pos))] = (OrderItemMaterialSnapshot, m, {})
    return rows


def _compare(order, expected_values: dict, *, after_sync_old_values: dict | None = None) -> list[str]:
    problems = []
    rows = _order_rows(order)
    assert set(rows) == set(expected_values), (sorted(map(str, rows)), sorted(map(str, expected_values)))
    for key, (model, obj, mapped) in rows.items():
        for col, entry in ORDER_FIELDS[model].items():
            if entry[0] != "von":
                continue
            source, wann = entry[1], entry[2]
            source_values = after_sync_old_values[key] if (after_sync_old_values and wann == NUR_BEAUFTRAGEN) else expected_values[key]
            want = source_values[source]
            got = mapped[col] if col in mapped else getattr(obj, col)
            if got != want:
                problems.append(f"{model.__name__}.{col} ({wann}): {got!r} statt {want!r} aus {source}")
    return problems


def test_beauftragen_copies_every_copied_field():
    db = db_session()
    quote, *_ = _build(db)
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 30), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    problems = _compare(load_order(db, order.id), _quote_values(db, load_quote(db, quote.id)))
    assert not problems, "\n".join(problems)
    assert order_matches_source_quote(db, load_order(db, order.id))


def test_abgleich_copies_every_field_marked_so_and_keeps_the_others():
    db = db_session()
    quote, keys, staff, sections = _build(db)
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 30), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    before = _quote_values(db, load_quote(db, quote.id))
    _change_everything(db, load_quote(db, quote.id), keys, staff, sections)
    assert not order_matches_source_quote(db, load_order(db, order.id))
    sync_order_from_source_quote(db, load_order(db, order.id))
    after = _quote_values(db, load_quote(db, quote.id))
    problems = _compare(load_order(db, order.id), after, after_sync_old_values=before)
    assert not problems, "\n".join(problems)


def test_a_change_only_in_tax_key_or_second_outro_counts_as_difference():
    """Der eigentliche Fehler: vorher galt ein Angebot, das sich NUR darin änderte, als unverändert,
    und der Abgleich tat nichts."""
    db = db_session()
    quote, keys, _, _ = _build(db)
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 30), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    quote = load_quote(db, quote.id)
    quote.outro_text_2 = "Nur der zweite Schlusstext"
    db.commit()
    assert not order_matches_source_quote(db, load_order(db, order.id))
    assert sync_order_from_source_quote(db, load_order(db, order.id)).outro_text_2 == "Nur der zweite Schlusstext"
    quote = load_quote(db, quote.id)
    quote.tax_key_id = keys[1].id
    db.commit()
    assert not order_matches_source_quote(db, load_order(db, order.id))
    assert sync_order_from_source_quote(db, load_order(db, order.id)).tax_key_id == keys[1].id
