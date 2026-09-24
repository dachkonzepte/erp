from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re
import shutil

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, object_session, selectinload

from .calculation import build_calculation, get_settings_for_catalog, get_service_for_calculation
from .models import (
    Customer, Project, ProjectProfile, Property, Quote, QuoteItem, QuoteItemCalculation,
    QuoteItemMaterialCalculation, QuoteDocumentMeta, QuoteSection, QuoteItemLayout,
    QuoteEmployeeAssignment, TaxKey,
)
from .project_documents import project_directory
from .project_pipeline_columns import default_pipeline_column_id
from .settings import preview_number
from .payment_terms import get_default_payment_term

CENT = Decimal("0.01")


def money_q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def next_project_number(db: Session) -> str:
    return preview_number(db, "project")


def next_quote_number(db: Session) -> str:
    return preview_number(db, "quote")


def load_project(db: Session, project_id: int) -> Project | None:
    return db.scalar(
        select(Project)
        .options(
            selectinload(Project.customer),
            selectinload(Project.property),
            selectinload(Project.quotes),
        )
        .where(Project.id == project_id)
    )


def load_quote(db: Session, quote_id: int) -> Quote | None:
    return db.scalar(
        select(Quote)
        .options(
            selectinload(Quote.items).selectinload(QuoteItem.project_calculation).selectinload(QuoteItemCalculation.materials),
            selectinload(Quote.project).selectinload(Project.customer).selectinload(Customer.profile),
            selectinload(Quote.project).selectinload(Project.property),
        )
        .where(Quote.id == quote_id)
    )


def ensure_quote_structure(db: Session, quote: Quote) -> tuple[QuoteDocumentMeta, list[QuoteSection], dict[int, QuoteItemLayout]]:
    """Stellt 0.6-Zusatztabellen auch für bestehende 0.5-Angebote her."""
    changed = False
    meta = db.scalar(select(QuoteDocumentMeta).where(QuoteDocumentMeta.quote_id == quote.id))
    if meta is None:
        qdate = quote.created_at.date() if quote.created_at else date.today()
        default_term = get_default_payment_term(db)
        meta = QuoteDocumentMeta(
            quote_id=quote.id,
            quote_date=qdate,
            valid_until=qdate + timedelta(days=30),
            contact_person=None,
            payment_terms=default_term.label if default_term else None,
        )
        db.add(meta)
        changed = True

    sections = db.scalars(
        select(QuoteSection).where(QuoteSection.quote_id == quote.id).order_by(QuoteSection.sort_order, QuoteSection.id)
    ).all()
    section_ids = {s.id for s in sections}
    layouts = {
        row.quote_item_id: row for row in db.scalars(
            select(QuoteItemLayout).join(QuoteItem, QuoteItemLayout.quote_item_id == QuoteItem.id).where(QuoteItem.quote_id == quote.id)
        ).all()
    }
    for item in quote.items:
        if item.id not in layouts:
            row = QuoteItemLayout(
                quote_item_id=item.id,
                section_id=None,
                sort_order=item.sort_order or 10,
                include_in_total=True,
            )
            db.add(row)
            db.flush()
            layouts[item.id] = row
            changed = True
        elif layouts[item.id].section_id not in section_ids and layouts[item.id].section_id is not None:
            layouts[item.id].section_id = None
            changed = True
    if changed:
        db.commit()
        db.refresh(meta)
    return meta, sections, layouts


def build_quote_item_calculation(item: QuoteItem) -> dict | None:
    calc = item.project_calculation
    if calc is None:
        return None

    site = Decimal(calc.site_time_minutes or 0)
    workshop = Decimal(calc.workshop_time_minutes or 0)
    labor_rate = Decimal(calc.labor_rate or 0)
    material_markup_pct = Decimal(calc.material_markup_pct or 0)
    overhead_pct = Decimal(calc.overhead_pct or 0)
    risk_profit_pct = Decimal(calc.risk_profit_pct or 0)

    labor_amount = (site + workshop) / Decimal("60") * labor_rate
    material_base_cost = Decimal("0")
    materials = []
    for row in calc.materials:
        qty = Decimal(row.quantity or 0)
        waste = Decimal(row.waste_pct or 0)
        effective_qty = qty * (Decimal("1") + waste / Decimal("100"))
        basis = Decimal(row.price_basis or 1) or Decimal("1")
        price = Decimal(row.purchase_price or 0)
        cost = effective_qty / basis * price
        material_base_cost += cost
        materials.append({
            "id": row.id,
            "source_material_id": row.source_material_id,
            "name": row.name,
            "article_number": row.article_number,
            "unit": row.unit,
            "source_quantity": Decimal(row.source_quantity or 0),
            "quantity": qty,
            "waste_pct": waste,
            "source_purchase_price": Decimal(row.source_purchase_price or 0),
            "purchase_price": price,
            "price_basis": basis,
            "effective_quantity": effective_qty,
            "base_cost": money_q(cost),
        })

    material_markup_amount = material_base_cost * material_markup_pct / Decimal("100")
    material_amount = material_base_cost + material_markup_amount
    equipment = Decimal(calc.equipment_cost or 0)
    subcontract = Decimal(calc.subcontractor_cost or 0)
    other = Decimal(calc.other_cost or 0)
    subtotal_before_overhead = labor_amount + material_amount + equipment + subcontract + other
    overhead_amount = subtotal_before_overhead * overhead_pct / Decimal("100")
    subtotal_before_risk_profit = subtotal_before_overhead + overhead_amount
    risk_profit_amount = subtotal_before_risk_profit * risk_profit_pct / Decimal("100")
    calculated = subtotal_before_risk_profit + risk_profit_amount
    manual = Decimal(calc.manual_sale_price) if calc.manual_sale_price is not None else None
    effective = manual if manual is not None else calculated

    return {
        "quote_item_id": item.id,
        "quote_id": item.quote_id,
        "position_number": item.position_number,
        "service_external_id": item.source_external_id,
        "service_name": item.short_text.splitlines()[0] if item.short_text else "",
        "unit": item.unit,
        "site_time_minutes": site,
        "workshop_time_minutes": workshop,
        "labor_rate": labor_rate,
        "material_markup_pct": material_markup_pct,
        "equipment_cost": money_q(equipment),
        "subcontractor_cost": money_q(subcontract),
        "other_cost": money_q(other),
        "overhead_pct": overhead_pct,
        "risk_profit_pct": risk_profit_pct,
        "manual_sale_price": money_q(manual) if manual is not None else None,
        "notes": calc.notes,
        "labor_amount": money_q(labor_amount),
        "material_base_cost": money_q(material_base_cost),
        "material_markup_amount": money_q(material_markup_amount),
        "material_amount": money_q(material_amount),
        "subtotal_before_overhead": money_q(subtotal_before_overhead),
        "overhead_amount": money_q(overhead_amount),
        "subtotal_before_risk_profit": money_q(subtotal_before_risk_profit),
        "risk_profit_amount": money_q(risk_profit_amount),
        "calculated_sale_price": money_q(calculated),
        "effective_sale_price": money_q(effective),
        "materials": materials,
    }


def create_project_calculation_snapshot(db: Session, item: QuoteItem, service, catalog_calc: dict) -> QuoteItemCalculation:
    calc = QuoteItemCalculation(
        quote_item_id=item.id,
        site_time_minutes=Decimal(catalog_calc["site_time_minutes"]),
        workshop_time_minutes=Decimal(catalog_calc["workshop_time_minutes"]),
        labor_rate=Decimal(catalog_calc["labor_rate"]),
        material_markup_pct=Decimal(catalog_calc["material_markup_pct"]),
        equipment_cost=Decimal(catalog_calc["equipment_cost"]),
        subcontractor_cost=Decimal(catalog_calc["subcontractor_cost"]),
        other_cost=Decimal(catalog_calc["other_cost"]),
        overhead_pct=Decimal(catalog_calc["overhead_pct"]),
        risk_profit_pct=Decimal(catalog_calc["risk_profit_pct"]),
        manual_sale_price=Decimal(catalog_calc["manual_sale_price"]) if catalog_calc["manual_sale_price"] is not None else None,
        notes=catalog_calc.get("notes"),
    )
    db.add(calc)
    db.flush()
    item.project_calculation = calc
    for m in catalog_calc["materials"]:
        base_qty = Decimal(m["quantity_override"]) if m.get("quantity_override") is not None else Decimal(m["source_quantity"] or 0)
        calc.materials.append(QuoteItemMaterialCalculation(
            source_material_id=m["material_id"],
            name=m["name"],
            article_number=m["article_number"],
            unit=m["unit"],
            source_quantity=Decimal(m["source_quantity"] or 0),
            quantity=base_qty,
            waste_pct=Decimal(m["waste_pct"] or 0),
            source_purchase_price=Decimal(m["source_purchase_price"] or 0),
            purchase_price=Decimal(m["effective_purchase_price"] or 0),
            price_basis=Decimal(m["effective_price_basis"] or 1),
        ))
    return calc


def ensure_quote_item_calculation(db: Session, item: QuoteItem) -> QuoteItemCalculation | None:
    if item.project_calculation is not None:
        return item.project_calculation
    if item.source_service_id is None:
        return None
    service = get_service_for_calculation(db, item.source_service_id)
    if service is None:
        return None
    catalog_calc = build_calculation(service, get_settings_for_catalog(db, service.catalog_id))
    calc = create_project_calculation_snapshot(db, item, service, catalog_calc)
    db.commit()
    return calc


def _validate_section(db: Session, quote_id: int, section_id: int | None) -> QuoteSection | None:
    if section_id is None:
        return None
    section = db.get(QuoteSection, section_id)
    if section is None or section.quote_id != quote_id:
        raise ValueError("LV-Titel gehört nicht zu diesem Angebot.")
    return section


def add_service_to_quote(db: Session, quote: Quote, service_id: int, quantity: Decimal, section_id: int | None = None) -> QuoteItem | None:
    service = get_service_for_calculation(db, service_id)
    if service is None:
        return None
    _validate_section(db, quote.id, section_id)
    settings = get_settings_for_catalog(db, service.catalog_id)
    catalog_calc = build_calculation(service, settings)
    max_sort = max((item.sort_order for item in quote.items), default=0)
    unit_price = money_q(Decimal(catalog_calc["effective_sale_price"]))
    item = QuoteItem(
        quote_id=quote.id,
        source_service_id=service.id,
        sort_order=max_sort + 10,
        position_number=str(len(quote.items) + 1),
        gaeb_oz=str(len(quote.items) + 1),
        position_type="normal",
        source_external_id=service.external_id,
        short_text=service.short_text,
        long_text=service.long_text,
        quantity=quantity,
        unit=service.unit,
        unit_price=unit_price,
        source_unit_price=unit_price,
    )
    db.add(item)
    db.flush()
    create_project_calculation_snapshot(db, item, service, catalog_calc)
    max_layout = db.scalar(select(QuoteItemLayout.sort_order).join(QuoteItem).where(QuoteItem.quote_id == quote.id, QuoteItemLayout.section_id == section_id).order_by(QuoteItemLayout.sort_order.desc()).limit(1)) or 0
    db.add(QuoteItemLayout(quote_item_id=item.id, section_id=section_id, sort_order=max_layout + 10, include_in_total=True))
    db.commit()
    return item


def create_free_quote_item(db: Session, quote: Quote, *, short_text: str, long_text: str, quantity: Decimal,
                           unit: str, unit_price: Decimal, position_type: str, section_id: int | None,
                           include_in_total: bool = True) -> QuoteItem:
    _validate_section(db, quote.id, section_id)
    max_sort = max((item.sort_order for item in quote.items), default=0)
    item = QuoteItem(
        quote_id=quote.id, source_service_id=None, sort_order=max_sort + 10,
        position_number=str(len(quote.items) + 1), gaeb_oz=str(len(quote.items) + 1),
        position_type=position_type, source_external_id=None, short_text=short_text,
        long_text=long_text or "", quantity=quantity, unit=unit, unit_price=unit_price,
        source_unit_price=None,
    )
    db.add(item)
    db.flush()
    max_layout = db.scalar(select(QuoteItemLayout.sort_order).join(QuoteItem).where(QuoteItem.quote_id == quote.id, QuoteItemLayout.section_id == section_id).order_by(QuoteItemLayout.sort_order.desc()).limit(1)) or 0
    db.add(QuoteItemLayout(quote_item_id=item.id, section_id=section_id, sort_order=max_layout + 10, include_in_total=include_in_total))
    db.commit()
    return item


def duplicate_quote_item(db: Session, item: QuoteItem) -> QuoteItem:
    quote = load_quote(db, item.quote_id)
    _, _, layouts = ensure_quote_structure(db, quote)
    source_layout = layouts[item.id]
    new_item = QuoteItem(
        quote_id=item.quote_id, source_service_id=item.source_service_id,
        sort_order=item.sort_order + 1, position_number=item.position_number,
        gaeb_oz=item.gaeb_oz, position_type=item.position_type,
        source_external_id=item.source_external_id, short_text=item.short_text,
        long_text=item.long_text, quantity=item.quantity, unit=item.unit,
        unit_price=item.unit_price, source_unit_price=item.source_unit_price,
    )
    db.add(new_item)
    db.flush()
    db.add(QuoteItemLayout(
        quote_item_id=new_item.id, section_id=source_layout.section_id,
        sort_order=source_layout.sort_order + 1, include_in_total=source_layout.include_in_total,
    ))
    if item.project_calculation:
        c = item.project_calculation
        nc = QuoteItemCalculation(
            quote_item_id=new_item.id, site_time_minutes=c.site_time_minutes,
            workshop_time_minutes=c.workshop_time_minutes, labor_rate=c.labor_rate,
            material_markup_pct=c.material_markup_pct, equipment_cost=c.equipment_cost,
            subcontractor_cost=c.subcontractor_cost, other_cost=c.other_cost,
            overhead_pct=c.overhead_pct, risk_profit_pct=c.risk_profit_pct,
            manual_sale_price=c.manual_sale_price, notes=c.notes,
        )
        db.add(nc); db.flush()
        for m in c.materials:
            db.add(QuoteItemMaterialCalculation(
                calculation_id=nc.id, source_material_id=m.source_material_id, name=m.name,
                article_number=m.article_number, unit=m.unit, source_quantity=m.source_quantity,
                quantity=m.quantity, waste_pct=m.waste_pct, source_purchase_price=m.source_purchase_price,
                purchase_price=m.purchase_price, price_basis=m.price_basis,
            ))
    db.commit()
    auto_number_quote(db, quote.id)
    return new_item


def create_quote_section(db: Session, quote_id: int, title: str, description: str | None, parent_id: int | None) -> QuoteSection:
    if parent_id is not None:
        parent = _validate_section(db, quote_id, parent_id)
        if parent.parent_id is not None:
            raise ValueError("In Version 0.6 sind maximal Titel und Untertitel vorgesehen.")
    siblings = db.scalars(select(QuoteSection).where(QuoteSection.quote_id == quote_id, QuoteSection.parent_id == parent_id)).all()
    row = QuoteSection(quote_id=quote_id, parent_id=parent_id, title=title, description=description, sort_order=(max((s.sort_order for s in siblings), default=0) + 10))
    db.add(row); db.commit(); db.refresh(row)
    auto_number_quote(db, quote_id)
    return row


def update_quote_tax_key(db: Session, quote: Quote, tax_key_id: int) -> Quote:
    """Setzt tax_key_id UND vat_rate zusammen aus dem gewählten
    Steuerschlüssel -- die eigentliche Summenberechnung (quote_to_dict) liest
    weiterhin nur vat_rate und merkt vom Steuerschlüssel selbst nichts."""
    key = db.get(TaxKey, tax_key_id)
    if key is None:
        raise ValueError("Steuerschlüssel nicht gefunden.")
    quote.tax_key_id = tax_key_id
    quote.vat_rate = key.vat_rate
    db.commit()
    db.refresh(quote)
    return quote


def update_quote_section(db: Session, quote_id: int, section_id: int, title: str, description: str | None, parent_id: int | None) -> QuoteSection:
    section = _validate_section(db, quote_id, section_id)
    if parent_id == section_id:
        raise ValueError("Ein Titel kann nicht sein eigener Untertitel sein.")
    if parent_id is not None:
        parent = _validate_section(db, quote_id, parent_id)
        if parent.parent_id is not None:
            raise ValueError("In Version 0.6 sind maximal Titel und Untertitel vorgesehen.")
        children = db.scalars(select(QuoteSection).where(QuoteSection.parent_id == section.id)).all()
        if children:
            raise ValueError("Ein Titel mit Untertiteln kann nicht selbst zum Untertitel werden.")
    section.title = title; section.description = description; section.parent_id = parent_id
    db.commit(); db.refresh(section); auto_number_quote(db, quote_id)
    return section


def delete_quote_section(db: Session, quote_id: int, section_id: int) -> None:
    section = _validate_section(db, quote_id, section_id)
    # Inhalte eine Ebene nach oben verschieben, damit beim Löschen nichts verloren geht.
    for child in db.scalars(select(QuoteSection).where(QuoteSection.parent_id == section.id)).all():
        child.parent_id = section.parent_id
    for layout in db.scalars(select(QuoteItemLayout).where(QuoteItemLayout.section_id == section.id)).all():
        layout.section_id = section.parent_id
    db.delete(section); db.commit(); auto_number_quote(db, quote_id)


def set_item_layout(db: Session, quote_id: int, item_id: int, section_id: int | None, include_in_total: bool) -> QuoteItemLayout:
    item = db.get(QuoteItem, item_id)
    if item is None or item.quote_id != quote_id:
        raise ValueError("Angebotsposition nicht gefunden.")
    _validate_section(db, quote_id, section_id)
    layout = db.scalar(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id == item_id))
    if layout is None:
        layout = QuoteItemLayout(quote_item_id=item_id, section_id=section_id, sort_order=item.sort_order, include_in_total=include_in_total)
        db.add(layout)
    else:
        layout.section_id = section_id; layout.include_in_total = include_in_total
    db.commit(); auto_number_quote(db, quote_id); db.refresh(layout)
    return layout


def reorder_quote(db: Session, quote_id: int, sections: list[dict], items: list[dict]) -> None:
    valid_sections = {s.id: s for s in db.scalars(select(QuoteSection).where(QuoteSection.quote_id == quote_id)).all()}
    for row in sections:
        section = valid_sections.get(row["id"])
        if not section: raise ValueError("Unbekannter LV-Titel.")
        parent_id = row.get("parent_id")
        if parent_id is not None and parent_id not in valid_sections: raise ValueError("Ungültiger übergeordneter Titel.")
        section.parent_id = parent_id; section.sort_order = row["sort_order"]
    valid_items = {i.id: i for i in db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote_id)).all()}
    layouts = {l.quote_item_id: l for l in db.scalars(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id.in_(valid_items.keys()))).all()} if valid_items else {}
    for row in items:
        item = valid_items.get(row["id"])
        if not item: raise ValueError("Unbekannte Angebotsposition.")
        section_id = row.get("section_id")
        if section_id is not None and section_id not in valid_sections: raise ValueError("Ungültiger LV-Titel.")
        layout = layouts.get(item.id)
        if layout is None:
            layout = QuoteItemLayout(quote_item_id=item.id); db.add(layout); layouts[item.id] = layout
        layout.section_id = section_id; layout.sort_order = row["sort_order"]
        item.sort_order = row["sort_order"]
    db.commit(); auto_number_quote(db, quote_id)


def auto_number_quote(db: Session, quote_id: int) -> None:
    quote = load_quote(db, quote_id)
    if quote is None: return
    _, sections, layouts = ensure_quote_structure(db, quote)
    tops = sorted([s for s in sections if s.parent_id is None], key=lambda s: (s.sort_order, s.id))
    section_number = {}
    for top_idx, top in enumerate(tops, 1):
        top.section_number = f"{top_idx:02d}"
        section_number[top.id] = top.section_number
        children = sorted([s for s in sections if s.parent_id == top.id], key=lambda s: (s.sort_order, s.id))
        for child_idx, child in enumerate(children, 1):
            child.section_number = f"{top_idx:02d}.{child_idx:02d}"
            section_number[child.id] = child.section_number
    orphan_sections = [s for s in sections if s.id not in section_number]
    for idx, s in enumerate(orphan_sections, len(tops) + 1):
        s.parent_id = None; s.section_number = f"{idx:02d}"; section_number[s.id] = s.section_number

    grouped: dict[int | None, list[QuoteItem]] = {}
    for item in quote.items:
        layout = layouts[item.id]
        grouped.setdefault(layout.section_id, []).append(item)
    for sec_id, rows in grouped.items():
        rows.sort(key=lambda i: (layouts[i.id].sort_order, i.id))
        prefix = section_number.get(sec_id)
        for idx, item in enumerate(rows, 1):
            suffix = f"{idx * 10:04d}"
            oz = f"{prefix}.{suffix}" if prefix else suffix
            item.position_number = oz
            item.gaeb_oz = oz
            item.sort_order = layouts[item.id].sort_order
    db.commit()


def renumber_quote_items(quote: Quote) -> None:
    """Kompatibilitätsfunktion für ältere Aufrufer; nutzt ab 0.6 die LV-OZ-Logik."""
    db = object_session(quote)
    if db is not None:
        auto_number_quote(db, quote.id)
        return
    ordered = sorted(quote.items, key=lambda item: (item.sort_order, item.id))
    for idx, item in enumerate(ordered, start=1):
        item.sort_order = idx * 10
        item.position_number = str(idx)
        if not item.gaeb_oz or re.fullmatch(r"\d+", item.gaeb_oz):
            item.gaeb_oz = str(idx)


def quote_to_dict(quote: Quote) -> dict:
    db = object_session(quote)
    meta = None; sections = []; layouts = {}
    if db is not None:
        meta, sections, layouts = ensure_quote_structure(db, quote)
    items = []
    net = Decimal("0"); optional = Decimal("0")
    def item_key(item):
        layout = layouts.get(item.id)
        sid = layout.section_id if layout else None
        section = next((s for s in sections if s.id == sid), None)
        parent = next((s for s in sections if section and s.id == section.parent_id), None)
        return ((parent.sort_order if parent else (section.sort_order if section else 999999)),
                (section.sort_order if section else 999999), (layout.sort_order if layout else item.sort_order), item.id)
    for item in sorted(quote.items, key=item_key):
        layout = layouts.get(item.id)
        line_total = money_q(Decimal(item.quantity) * Decimal(item.unit_price))
        included = layout.include_in_total if layout else True
        if included: net += line_total
        else: optional += line_total
        items.append({
            "id": item.id, "source_service_id": item.source_service_id,
            "source_external_id": item.source_external_id, "position_number": item.position_number,
            "gaeb_oz": item.gaeb_oz, "position_type": item.position_type,
            "short_text": item.short_text, "long_text": item.long_text,
            "quantity": Decimal(item.quantity), "unit": item.unit,
            "unit_price": money_q(Decimal(item.unit_price)),
            "source_unit_price": money_q(Decimal(item.source_unit_price)) if item.source_unit_price is not None else None,
            "line_total": line_total,
            "has_project_calculation": item.project_calculation is not None or item.source_service_id is not None,
            "section_id": layout.section_id if layout else None,
            "layout_sort_order": layout.sort_order if layout else item.sort_order,
            "include_in_total": included,
        })
    net = money_q(net); optional = money_q(optional)
    vat = money_q(net * Decimal(quote.vat_rate) / Decimal("100")); gross = money_q(net + vat)
    meta_dict = None
    if meta is not None:
        assignment = db.scalar(select(QuoteEmployeeAssignment).where(QuoteEmployeeAssignment.quote_id == quote.id)) if db is not None else None
        meta_dict = {
            "id": meta.id, "quote_id": meta.quote_id, "quote_date": meta.quote_date,
            "valid_until": meta.valid_until, "contact_person": meta.contact_person,
            "contact_person_employee_id": assignment.caseworker_employee_id if assignment else None,
            "payment_terms": meta.payment_terms, "execution_period": meta.execution_period,
            "internal_note": meta.internal_note,
        }
    tax_key = db.get(TaxKey, quote.tax_key_id) if (db is not None and quote.tax_key_id) else None
    return {
        "id": quote.id, "quote_number": quote.quote_number, "project_id": quote.project_id,
        "project_number": quote.project.project_number, "project_name": quote.project.name,
        "customer_id": quote.project.customer_id, "customer_name": quote.project.customer.name,
        "property_name": quote.project.property.name if quote.project.property else None,
        "title": quote.title, "status": quote.status, "vat_rate": Decimal(quote.vat_rate),
        "intro_text": quote.intro_text, "outro_text": quote.outro_text, "outro_text_2": quote.outro_text_2,
        "tax_key_id": quote.tax_key_id,
        "tax_notice_text": tax_key.notice_text if tax_key else None,
        "source_format": quote.source_format, "gaeb_exchange_phase": quote.gaeb_exchange_phase,
        "document_meta": meta_dict,
        "sections": [{"id": s.id, "quote_id": s.quote_id, "parent_id": s.parent_id, "title": s.title,
                      "description": s.description, "sort_order": s.sort_order, "section_number": s.section_number}
                     for s in sorted(sections, key=lambda s: (s.parent_id is not None, s.sort_order, s.id))],
        "items": items, "net_total": net, "optional_total": optional,
        "vat_total": vat, "gross_total": gross,
        "email_sent_at": quote.email_sent_at, "email_sent_to": quote.email_sent_to,
        "recipient_email": get_quote_recipient_email(quote),
    }


DEFAULT_QUOTE_EMAIL_SUBJECT = "Angebot {angebotsnummer}"
DEFAULT_QUOTE_EMAIL_BODY = (
    "Sehr geehrte Damen und Herren,\n\n"
    "anbei erhalten Sie unser Angebot {angebotsnummer} über {gesamtbetrag}. "
    "Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF.\n\n"
    "Mit freundlichen Grüßen"
)


def get_quote_recipient_email(quote: Quote) -> str | None:
    """Aktuelle, live nachgeschlagene Kunden-E-Mail -- analog zu
    get_invoice_recipient_email()/get_reminder_recipient_email(). Einfacher
    als bei Rechnung/Mahnung: quote.project ist eine direkte Beziehung,
    kein Umweg über einen Auftrag nötig. Bewusst trotzdem defensiv gegen
    ein fehlendes project, falls diese Funktion je auf einem nicht über
    load_quote() geladenen Objekt aufgerufen würde."""
    project = quote.project
    customer = project.customer if project else None
    return (customer.email or None) if customer else None


def send_quote_email(db: Session, quote: Quote, *, to_email: str | None = None) -> Quote:
    """Versendet ein Angebot tatsächlich per E-Mail (seit 1.0.87) -- analog
    zu send_invoice_email()/send_reminder_email(). Anders als bei Rechnung/
    Mahnung gibt es bei Angeboten keinen GoBD-artigen
    Unveränderlichkeits-Mechanismus (quote_number existiert schon ab
    Anlage) -- der Entwurfs-Schutz hier ist eine bewusste Geschäftsregel
    ("kein Versand eines noch unfertigen Angebots"), keine technische
    Notwendigkeit wie bei den anderen beiden.

    Kann auch mehrfach aufgerufen werden (z.B. erneuter Versand), aktualisiert
    email_sent_at/email_sent_to bei jedem Aufruf neu. to_email überschreibt
    die automatisch ermittelte Kunden-E-Mail nur für DIESEN Versand.

    PDF-Erzeugung und E-Mail-Versand erfolgen hier lokal importiert -- siehe
    Begründung bei send_invoice_email()/send_reminder_email() zu
    Zirkel-Importen (quote_framed_pdf.py importiert ebenfalls aus diesem Modul).

    Seit 1.3.13 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot, Punkt 4 der letzten Etappe):
    build_quote_framed_pdf() (gemeinsamer PDF-Rahmen) statt des bisherigen
    build_quote_layout_pdf() (positionsbasierter Layout-Designer) -- derselbe Grund wie vorher:
    der tatsächlich an Kunden versendete Anhang soll dem produktiv genutzten Renderer
    entsprechen, das ist jetzt der neue. quote_layout_pdf.py bleibt vorerst über die
    Vergleichsansicht im Layout-Editor erreichbar (GET /api/quotes/{id}/pdf-layout-preview),
    bekommt aber keine echten Versand-/Abruf-Aufrufe mehr."""
    from datetime import datetime as _datetime

    from .document_email_templates import get_email_template
    from .email_sending import send_email_with_attachment
    from .quote_framed_pdf import build_quote_framed_pdf

    if quote.status == "entwurf":
        raise ValueError("Nur bereits fertiggestellte Angebote (nicht mehr im Status 'Entwurf') können per E-Mail versendet werden.")

    recipient = (to_email or "").strip() or get_quote_recipient_email(quote)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")

    data = quote_to_dict(quote)
    money = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"  # noqa: E731
    placeholders = {
        "{angebotsnummer}": quote.quote_number,
        "{gesamtbetrag}": money(data["gross_total"]),
        "{kundenname}": data["customer_name"],
    }

    template = get_email_template(db, "quote")
    subject_template = (template.subject_template if template else None) or DEFAULT_QUOTE_EMAIL_SUBJECT
    body_template = (template.body_template if template else None) or DEFAULT_QUOTE_EMAIL_BODY
    subject, body = subject_template, body_template
    for placeholder, value in placeholders.items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)

    pdf_bytes = build_quote_framed_pdf(db, quote)
    send_email_with_attachment(
        db, to_email=recipient, subject=subject, body_text=body,
        attachment_bytes=pdf_bytes, attachment_filename=f"{quote.quote_number}.pdf",
    )

    quote.email_sent_at = _datetime.utcnow()
    quote.email_sent_to = recipient
    db.commit()
    db.refresh(quote)
    return quote


def _copy_quote_into_project(db: Session, source_quote: Quote, target_project: Project) -> Quote:
    """Interner Baustein von duplicate_project() -- kopiert ein einzelnes
    Angebot samt vollständiger Struktur (Kopfdaten, Sachbearbeiter,
    Gliederung, Positionen, Kalkulation, Materialzeilen) in ein neues,
    bereits angelegtes Zielprojekt. quote_date wird auf heute gesetzt,
    valid_until bewusst nicht übernommen -- eine alte Gültigkeitsfrist wäre
    für ein neu erstelltes Angebot nicht mehr sinnvoll."""
    new_quote = Quote(
        quote_number=next_quote_number(db), project_id=target_project.id, title=source_quote.title,
        status="entwurf", vat_rate=source_quote.vat_rate, tax_key_id=source_quote.tax_key_id,
        intro_text=source_quote.intro_text, outro_text=source_quote.outro_text, outro_text_2=source_quote.outro_text_2,
        source_format=source_quote.source_format,
    )
    db.add(new_quote)
    db.flush()

    source_meta = db.scalar(select(QuoteDocumentMeta).where(QuoteDocumentMeta.quote_id == source_quote.id))
    if source_meta is not None:
        db.add(QuoteDocumentMeta(
            quote_id=new_quote.id, quote_date=date.today(), valid_until=None,
            contact_person=source_meta.contact_person, payment_terms=source_meta.payment_terms,
            execution_period=source_meta.execution_period, internal_note=source_meta.internal_note,
        ))

    source_assignment = db.scalar(select(QuoteEmployeeAssignment).where(QuoteEmployeeAssignment.quote_id == source_quote.id))
    if source_assignment is not None:
        db.add(QuoteEmployeeAssignment(quote_id=new_quote.id, caseworker_employee_id=source_assignment.caseworker_employee_id))

    # Sections können bis zu zwei Ebenen tief sein -- Eltern zuerst
    # verarbeiten (parent_id is None sortiert vor allem anderen), damit
    # section_id_map beim Verarbeiten eines Kindes bereits die neue
    # Eltern-ID kennt.
    source_sections = db.scalars(select(QuoteSection).where(QuoteSection.quote_id == source_quote.id)).all()
    section_id_map: dict[int, int] = {}
    for s in sorted(source_sections, key=lambda x: (x.parent_id is not None, x.sort_order, x.id)):
        new_section = QuoteSection(
            quote_id=new_quote.id, parent_id=section_id_map.get(s.parent_id) if s.parent_id else None,
            title=s.title, description=s.description, sort_order=s.sort_order, section_number=s.section_number,
        )
        db.add(new_section)
        db.flush()
        section_id_map[s.id] = new_section.id

    source_items = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == source_quote.id)).all()
    for item in source_items:
        new_item = QuoteItem(
            quote_id=new_quote.id, source_service_id=item.source_service_id, sort_order=item.sort_order,
            position_number=item.position_number, gaeb_oz=item.gaeb_oz, position_type=item.position_type,
            source_external_id=item.source_external_id, short_text=item.short_text, long_text=item.long_text,
            quantity=item.quantity, unit=item.unit, unit_price=item.unit_price, source_unit_price=item.source_unit_price,
        )
        db.add(new_item)
        db.flush()

        source_layout = db.scalar(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id == item.id))
        if source_layout is not None:
            db.add(QuoteItemLayout(
                quote_item_id=new_item.id,
                section_id=section_id_map.get(source_layout.section_id) if source_layout.section_id else None,
                sort_order=source_layout.sort_order, include_in_total=source_layout.include_in_total,
            ))

        # Kalkulation (Zeiten, Zuschläge, Material) bewusst mitkopiert --
        # ohne sie müsste jede Position für den neuen Vorgang komplett neu
        # kalkuliert werden, was dem eigentlichen Zweck (Zeitersparnis bei
        # wiederkehrenden Vorgängen) entgegenlaufen würde.
        source_calc = db.scalar(select(QuoteItemCalculation).where(QuoteItemCalculation.quote_item_id == item.id))
        if source_calc is not None:
            new_calc = QuoteItemCalculation(
                quote_item_id=new_item.id, site_time_minutes=source_calc.site_time_minutes,
                workshop_time_minutes=source_calc.workshop_time_minutes, labor_rate=source_calc.labor_rate,
                material_markup_pct=source_calc.material_markup_pct, equipment_cost=source_calc.equipment_cost,
                subcontractor_cost=source_calc.subcontractor_cost, other_cost=source_calc.other_cost,
                overhead_pct=source_calc.overhead_pct, risk_profit_pct=source_calc.risk_profit_pct,
                manual_sale_price=source_calc.manual_sale_price, notes=source_calc.notes,
            )
            db.add(new_calc)
            db.flush()
            source_materials = db.scalars(
                select(QuoteItemMaterialCalculation).where(QuoteItemMaterialCalculation.calculation_id == source_calc.id)
            ).all()
            for m in source_materials:
                db.add(QuoteItemMaterialCalculation(
                    calculation_id=new_calc.id, source_material_id=m.source_material_id, name=m.name,
                    article_number=m.article_number, unit=m.unit, source_quantity=m.source_quantity,
                    quantity=m.quantity, waste_pct=m.waste_pct, source_purchase_price=m.source_purchase_price,
                    purchase_price=m.purchase_price, price_basis=m.price_basis,
                ))

    db.flush()
    ensure_quote_structure(db, new_quote)  # Sicherheitsnetz: legt fehlende Meta/Struktur an, falls die Quelle unvollständig war (ältere Angebote)
    return new_quote


def duplicate_project(db: Session, source_project: Project, *, as_template: bool) -> Project:
    """Erstellt eine vollständige Kopie eines Projekts samt dessen zuletzt
    angelegtem Angebot (seit 1.0.92) -- gemeinsamer Mechanismus für 'Vorgang
    kopieren', 'als Mustervorgang speichern' und 'neuen Vorgang aus Muster
    erstellen'; nur as_template unterscheidet das Ergebnis.

    Bewusst NICHT mitkopiert: ein eventuell vorhandener Auftrag (unveränder-
    licher LV-Snapshot -- die Kopie startet wieder im Angebotsstadium, wie
    jedes neue Angebot), Rechnungen, Mahnungen, Dokumente, Revisionen,
    Ausführungsdaten.

    Falls das Quellprojekt mehrere Angebote hat, wird nur das zuletzt
    angelegte (höchste id) kopiert -- ein 'Vorgang' im Sinne dieser Funktion
    hat typischerweise genau ein repräsentatives Angebot; alternative/
    verworfene Angebotsversionen sollen sich nicht anhäufen."""
    new_project = Project(
        project_number=next_project_number(db), customer_id=source_project.customer_id,
        property_id=source_project.property_id, name=source_project.name, status="anfrage",
        description=source_project.description, is_template=as_template,
        pipeline_column_id=default_pipeline_column_id(db),
    )
    db.add(new_project)
    db.flush()

    if source_project.profile is not None and source_project.profile.category:
        db.add(ProjectProfile(project_id=new_project.id, category=source_project.profile.category))
        # source_maintenance_contract_id/-item_id werden bewusst NICHT mitkopiert -- ein
        # "Vorgang kopieren"/"Als Mustervorgang speichern" auf einem aus einem Wartungsvertrag
        # entstandenen Projekt darf die Vertragsherkunft nicht mitschleppen, sonst erschienen
        # spätere Einsatzberichte des Duplikats fälschlich in list_contract_history() (seit 1.2.15).

    source_quote = max(source_project.quotes, key=lambda q: q.id, default=None)
    if source_quote is not None:
        _copy_quote_into_project(db, source_quote, new_project)

    db.commit()
    db.refresh(new_project)
    return new_project


def get_or_create_project_profile(db: Session, project_id: int) -> ProjectProfile:
    """Öffentliches Gegenstück zum privaten, router-lokalen Helfer in
    app/routers/projects.py (seit 1.2.15) -- für Business-Logik-Module wie
    app/maintenance_contracts.py, die eine ProjectProfile-Zeile brauchen, ohne die
    Kategorie-Auswahl-Logik des Routers mitzubekommen."""
    profile = db.scalar(select(ProjectProfile).where(ProjectProfile.project_id == project_id))
    if profile is None:
        profile = ProjectProfile(project_id=project_id)
        db.add(profile)
        db.flush()
    return profile


def set_project_archived(db: Session, project: Project, archived: bool) -> Project:
    """Rein informatives Aus-/Einblenden (seit 1.0.94) -- jederzeit
    umkehrbar, ändert an den Daten selbst nichts. Gilt für Mustervorgänge
    wie für normale Projekte gleichermaßen."""
    project.archived = archived
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    """Löscht ein Projekt unwiderruflich (seit 1.0.94) -- nur möglich, wenn
    noch kein Auftrag daraus entstanden ist. Order.invoices trägt
    cascade='all, delete-orphan': ein uneingeschränktes Löschen würde über
    Project -> Order -> Invoice auch bereits finalisierte, GoBD-geschützte
    Rechnungen unwiderruflich mitreißen. Bei vorhandenem Auftrag bleibt nur
    das Archivieren (set_project_archived) -- gilt unabhängig davon, ob es
    sich um einen Mustervorgang handelt (der hat per Konstruktion ohnehin
    nie einen Auftrag, siehe duplicate_project()) oder ein normales Projekt.

    Cascade auf Project.quotes/items/documents/profile übernimmt einen Teil
    der Datenbank-Aufräumarbeit automatisch (echte ORM-Relationships mit
    cascade='all, delete-orphan'). Die später als migrationsarme Zusatz-
    tabellen angelegten Quote-Nebentabellen (QuoteSection, QuoteDocumentMeta,
    QuoteEmployeeAssignment, QuoteItemLayout) haben dagegen bewusst KEINE
    ORM-Relationship zu Quote/QuoteItem -- nur eine rohe Fremdschlüssel-
    spalte, Zugriff überall im Projekt per expliziter Abfrage statt über ein
    Attribut. Ohne manuelles Löschen blieben sie als verwaiste Zeilen
    zurück (in einem echten Testlauf tatsächlich aufgefallen: QuoteSection
    überlebte die Kaskade). Deshalb hier vorab explizit geleert.

    Physische Dokument-Dateien liegen außerhalb der Datenbank (siehe
    project_directory()) und müssen ebenfalls explizit mitgelöscht werden --
    erst NACH erfolgreichem db.commit(), damit bei einem Datenbankfehler
    keine Dateien verloren gehen, die noch von einem (dann nicht gelöschten)
    Datenbankeintrag referenziert würden.

    Seit dem Kalender-Modul (1.7.0) zusätzlich: unlink_calendar_events_for_project() hängt
    referenzierende CalendarEvent-Zeilen aus (project_id/quote_id -> NULL), statt sie zu
    löschen -- ein Termin (Besichtigung/Aufmaß) bleibt auch nach Löschen des Projekts als
    eigenständige Historie sinnvoll. Muss VOR dem Löschen der Quotes (Kaskade unten) laufen,
    sonst verletzt PostgreSQL die Fremdschlüssel-Bedingung auf CalendarEvent.quote_id."""
    if project.orders:
        raise ValueError("Projekte mit bestehendem Auftrag können nicht gelöscht werden, nur archiviert.")
    from .calendar_events import unlink_calendar_events_for_project
    unlink_calendar_events_for_project(db, project.id)
    directory = project_directory(project.id)
    for quote in project.quotes:
        db.execute(delete(QuoteSection).where(QuoteSection.quote_id == quote.id))
        db.execute(delete(QuoteDocumentMeta).where(QuoteDocumentMeta.quote_id == quote.id))
        db.execute(delete(QuoteEmployeeAssignment).where(QuoteEmployeeAssignment.quote_id == quote.id))
        item_ids = [item.id for item in quote.items]
        if item_ids:
            db.execute(delete(QuoteItemLayout).where(QuoteItemLayout.quote_item_id.in_(item_ids)))
    db.delete(project)
    db.commit()
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)
