from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    Employee, Order, OrderItem, OrderSection, OrderRevision,
    OrderItemCalculationSnapshot, OrderItemMaterialSnapshot,
    Project, QuoteEmployeeAssignment, TaxKey,
)
from .invoices import compute_order_billing_progress
from .projects import ensure_quote_structure, load_quote
from .settings import issue_number

CENT = Decimal("0.01")


def money_q(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def employee_name(employee: Employee | None) -> str | None:
    if employee is None:
        return None
    return f"{employee.first_name} {employee.last_name}".strip()


def _address(*parts) -> str | None:
    values = [str(x).strip() for x in parts if x and str(x).strip()]
    return ", ".join(values) if values else None


def _json_default(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def load_order(db: Session, order_id: int) -> Order | None:
    return db.scalar(
        select(Order)
        .options(
            selectinload(Order.project).selectinload(Project.customer),
            selectinload(Order.project).selectinload(Project.property),
            selectinload(Order.sections),
            selectinload(Order.items).selectinload(OrderItem.calculation_snapshot).selectinload(OrderItemCalculationSnapshot.materials),
            selectinload(Order.caseworker),
            selectinload(Order.project_manager),
            selectinload(Order.revisions),
        )
        .where(Order.id == order_id)
    )


def _quote_scope_payload(db: Session, quote_id: int) -> dict | None:
    quote = load_quote(db, quote_id)
    if quote is None:
        return None
    _, sections, layouts = ensure_quote_structure(db, quote)
    sec_rows = sorted(sections, key=lambda s: (s.sort_order, s.id))
    item_rows = sorted(
        quote.items,
        key=lambda i: ((layouts.get(i.id).sort_order if layouts.get(i.id) else i.sort_order), i.id),
    )
    return {
        "title": quote.title,
        "vat_rate": format(Decimal(quote.vat_rate or 0), "f"),
        "intro_text": quote.intro_text or "",
        "outro_text": quote.outro_text or "",
        "sections": [
            {
                "source_id": s.id,
                "parent_source_id": s.parent_id,
                "title": s.title,
                "description": s.description or "",
                "sort_order": s.sort_order,
                "section_number": s.section_number or "",
            }
            for s in sec_rows
        ],
        "items": [
            {
                "source_id": i.id,
                "section_source_id": (layouts.get(i.id).section_id if layouts.get(i.id) else None),
                "sort_order": (layouts.get(i.id).sort_order if layouts.get(i.id) else i.sort_order),
                "position_number": i.position_number,
                "gaeb_oz": i.gaeb_oz or "",
                "position_type": i.position_type,
                "source_external_id": i.source_external_id or "",
                "short_text": i.short_text,
                "long_text": i.long_text or "",
                "quantity": format(Decimal(i.quantity or 0), "f"),
                "unit": i.unit,
                "unit_price": format(Decimal(i.unit_price or 0), "f"),
                "include_in_total": (layouts.get(i.id).include_in_total if layouts.get(i.id) else True),
            }
            for i in item_rows
        ],
    }


def _order_scope_payload(order: Order) -> dict:
    sections = sorted(order.sections, key=lambda s: (s.sort_order, s.id))
    items = sorted(order.items, key=lambda i: (i.sort_order, i.id))
    # Map snapshot section IDs back to source quote section IDs for a stable comparison.
    source_by_snapshot = {s.id: s.source_quote_section_id for s in sections}
    return {
        "title": order.title,
        "vat_rate": format(Decimal(order.vat_rate or 0), "f"),
        "intro_text": order.intro_text or "",
        "outro_text": order.outro_text or "",
        "sections": [
            {
                "source_id": s.source_quote_section_id,
                "parent_source_id": source_by_snapshot.get(s.parent_id) if s.parent_id else None,
                "title": s.title,
                "description": s.description or "",
                "sort_order": s.sort_order,
                "section_number": s.section_number or "",
            }
            for s in sections
        ],
        "items": [
            {
                "source_id": i.source_quote_item_id,
                "section_source_id": source_by_snapshot.get(i.section_id) if i.section_id else None,
                "sort_order": i.sort_order,
                "position_number": i.position_number,
                "gaeb_oz": i.gaeb_oz or "",
                "position_type": i.position_type,
                "source_external_id": i.source_external_id or "",
                "short_text": i.short_text,
                "long_text": i.long_text or "",
                "quantity": format(Decimal(i.quantity or 0), "f"),
                "unit": i.unit,
                "unit_price": format(Decimal(i.unit_price or 0), "f"),
                "include_in_total": bool(i.include_in_total),
            }
            for i in items
        ],
    }


def _signature(payload: dict | None) -> str | None:
    if payload is None:
        return None
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def order_matches_source_quote(db: Session, order: Order) -> bool:
    return _signature(_quote_scope_payload(db, order.source_quote_id)) == _signature(_order_scope_payload(order))


def _order_snapshot_payload(order: Order) -> dict:
    data = order_to_dict(order, db=None, include_sync_state=False)
    # Revision snapshot also carries the calculation/material basis.
    item_by_id = {x.id: x for x in order.items}
    for row in data["items"]:
        item = item_by_id[row["id"]]
        calc = item.calculation_snapshot
        row["calculation"] = None
        if calc is not None:
            row["calculation"] = {
                "site_time_minutes": calc.site_time_minutes,
                "workshop_time_minutes": calc.workshop_time_minutes,
                "labor_rate": calc.labor_rate,
                "material_markup_pct": calc.material_markup_pct,
                "equipment_cost": calc.equipment_cost,
                "subcontractor_cost": calc.subcontractor_cost,
                "other_cost": calc.other_cost,
                "overhead_pct": calc.overhead_pct,
                "risk_profit_pct": calc.risk_profit_pct,
                "effective_sale_price": calc.effective_sale_price,
                "materials": [
                    {
                        "article_number": m.article_number,
                        "name": m.name,
                        "unit": m.unit,
                        "quantity": m.quantity,
                        "waste_pct": m.waste_pct,
                        "purchase_price": m.purchase_price,
                        "price_basis": m.price_basis,
                    }
                    for m in calc.materials
                ],
            }
    return data


def create_order_revision(db: Session, order: Order, *, reason: str, source: str = "manual", actor_name: str = "System") -> OrderRevision:
    current = db.scalar(select(func.max(OrderRevision.revision_number)).where(OrderRevision.order_id == order.id)) or 0
    rev = OrderRevision(
        order_id=order.id,
        revision_number=int(current) + 1,
        reason=(reason or "Auftragsstand gesichert").strip(),
        source=source,
        snapshot_json=json.dumps(_order_snapshot_payload(order), ensure_ascii=False, default=_json_default),
        created_by_name=actor_name or "System",
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)
    return rev


def order_to_dict(order: Order, db: Session | None = None, include_sync_state: bool = True) -> dict:
    tax_key = db.get(TaxKey, order.tax_key_id) if (db is not None and order.tax_key_id) else None
    sections = sorted(order.sections, key=lambda x: (x.sort_order, x.id))
    items = sorted(order.items, key=lambda x: (x.sort_order, x.id))
    item_rows = []
    net = Decimal("0")
    optional = Decimal("0")
    for item in items:
        line = money_q(Decimal(item.quantity or 0) * Decimal(item.unit_price or 0))
        if item.include_in_total:
            net += line
        else:
            optional += line
        item_rows.append({
            "id": item.id,
            "section_id": item.section_id,
            "source_quote_item_id": item.source_quote_item_id,
            "sort_order": item.sort_order,
            "position_number": item.position_number,
            "gaeb_oz": item.gaeb_oz,
            "position_type": item.position_type,
            "source_external_id": item.source_external_id,
            "short_text": item.short_text,
            "long_text": item.long_text,
            "quantity": item.quantity,
            "unit": item.unit,
            "unit_price": item.unit_price,
            "include_in_total": item.include_in_total,
            "line_total": line,
            "has_calculation_snapshot": item.calculation_snapshot is not None,
            "planned_hours_per_unit": ((Decimal(item.calculation_snapshot.site_time_minutes or 0) + Decimal(item.calculation_snapshot.workshop_time_minutes or 0)) / Decimal("60")) if item.calculation_snapshot else Decimal("0"),
            "planned_total_hours": (((Decimal(item.calculation_snapshot.site_time_minutes or 0) + Decimal(item.calculation_snapshot.workshop_time_minutes or 0)) / Decimal("60")) * Decimal(item.quantity or 0)) if item.calculation_snapshot else Decimal("0"),
        })
    net = money_q(net)
    optional = money_q(optional)
    vat = money_q(net * Decimal(order.vat_rate or 0) / Decimal("100"))
    gross = money_q(net + vat)
    revisions = sorted(getattr(order, "revisions", []) or [], key=lambda r: r.revision_number)
    result = {
        "id": order.id,
        "order_number": order.order_number,
        "project_id": order.project_id,
        "project_number": order.project.project_number,
        "project_name": order.project.name,
        "source_quote_id": order.source_quote_id,
        "quote_number_snapshot": order.quote_number_snapshot,
        "title": order.title,
        "status": order.status,
        "vat_rate": order.vat_rate,
        "intro_text": order.intro_text,
        "outro_text": order.outro_text,
        "outro_text_2": order.outro_text_2,
        "tax_key_id": order.tax_key_id,
        "tax_notice_text": tax_key.notice_text if tax_key else None,
        "customer_id": order.project.customer_id if order.project else None,
        "customer_name": order.customer_name,
        "customer_number": order.customer_number,
        "customer_address": order.customer_address,
        "property_name": order.property_name,
        "property_address": order.property_address,
        "order_date": order.order_date,
        "execution_start": order.execution_start,
        "execution_end": order.execution_end,
        "payment_terms": order.payment_terms,
        "remarks": order.remarks,
        "caseworker_employee_id": order.caseworker_employee_id,
        "caseworker_name": employee_name(order.caseworker),
        "project_manager_employee_id": order.project_manager_employee_id,
        "project_manager_name": employee_name(order.project_manager),
        "sections": [{
            "id": s.id, "parent_id": s.parent_id, "title": s.title,
            "description": s.description, "sort_order": s.sort_order,
            "section_number": s.section_number,
        } for s in sections],
        "items": item_rows,
        "net_total": net,
        "optional_total": optional,
        "vat_total": vat,
        "gross_total": gross,
        "created_at": order.created_at,
        "revision_count": len(revisions),
        "current_revision_number": (revisions[-1].revision_number if revisions else 0),
        "email_sent_at": order.email_sent_at,
        "email_sent_to": order.email_sent_to,
        "recipient_email": get_order_recipient_email(order),
    }
    if include_sync_state:
        if db is None:
            # Best effort for callers that only need the snapshot representation.
            result["source_quote_in_sync"] = None
            result["invoiced_net"] = None
            result["invoiced_gross"] = None
            result["open_net"] = None
            result["open_gross"] = None
        else:
            result["source_quote_in_sync"] = order_matches_source_quote(db, order)
            progress = compute_order_billing_progress(db, order.id)
            result["invoiced_net"] = progress["invoiced_net"]
            result["invoiced_gross"] = progress["invoiced_gross"]
            result["open_net"] = net - progress["invoiced_net"]
            result["open_gross"] = gross - progress["invoiced_gross"]
    return result


DEFAULT_ORDER_EMAIL_SUBJECT = "Auftragsbestätigung {auftragsnummer}"
DEFAULT_ORDER_EMAIL_BODY = (
    "Sehr geehrte Damen und Herren,\n\n"
    "anbei erhalten Sie unsere Auftragsbestätigung {auftragsnummer} über {gesamtbetrag}. "
    "Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF.\n\n"
    "Mit freundlichen Grüßen"
)


def get_order_recipient_email(order: Order) -> str | None:
    """Aktuelle, live nachgeschlagene Kunden-E-Mail -- analog zu
    get_quote_recipient_email()/get_invoice_recipient_email(). order.project
    ist wie bei Quote eine direkte Beziehung. Bewusst NICHT order.customer_name
    verwendet, das ist ein reiner Anzeige-Snapshot vom Beauftragungszeitpunkt,
    keine E-Mail-Adresse -- für den tatsächlichen Versand zählt immer der
    aktuelle Kundenstammdatensatz, falls sich die Adresse seither geändert hat."""
    project = order.project
    customer = project.customer if project else None
    return (customer.email or None) if customer else None


def send_order_email(db: Session, order: Order, *, to_email: str | None = None) -> Order:
    """Versendet eine Auftragsbestätigung tatsächlich per E-Mail (seit
    1.0.90) -- analog zu send_quote_email()/send_invoice_email(). Ein
    Auftrag hat (anders als Angebot/Rechnung/Mahnung) von Anfang an keinen
    'entwurf'-Status -- er entsteht erst durch die Beauftragung eines
    Angebots und ist dann bereits ein vollständiges Dokument. Einzige
    Ausnahme: ein stornierter Auftrag wird nicht mehr per E-Mail versendet.

    Kann auch mehrfach aufgerufen werden, aktualisiert email_sent_at/
    email_sent_to bei jedem Aufruf neu. to_email überschreibt die
    automatisch ermittelte Kunden-E-Mail nur für DIESEN Versand.

    PDF-Erzeugung lokal importiert -- siehe Begründung bei
    send_quote_email()/send_invoice_email() zu Zirkel-Importen
    (order_pdf.py importiert ebenfalls aus diesem Modul)."""
    from datetime import datetime as _datetime

    from .document_email_templates import get_email_template
    from .email_sending import send_email_with_attachment
    from .order_pdf import build_order_pdf

    if order.status == "storniert":
        raise ValueError("Ein stornierter Auftrag kann nicht per E-Mail versendet werden.")

    recipient = (to_email or "").strip() or get_order_recipient_email(order)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")

    data = order_to_dict(order, db, include_sync_state=False)
    money = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"  # noqa: E731
    placeholders = {
        "{auftragsnummer}": order.order_number,
        "{gesamtbetrag}": money(data["gross_total"]),
        "{kundenname}": order.customer_name,
    }

    template = get_email_template(db, "order")
    subject_template = (template.subject_template if template else None) or DEFAULT_ORDER_EMAIL_SUBJECT
    body_template = (template.body_template if template else None) or DEFAULT_ORDER_EMAIL_BODY
    subject, body = subject_template, body_template
    for placeholder, value in placeholders.items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)

    pdf_bytes = build_order_pdf(db, order)
    send_email_with_attachment(
        db, to_email=recipient, subject=subject, body_text=body,
        attachment_bytes=pdf_bytes, attachment_filename=f"{order.order_number}.pdf",
    )

    order.email_sent_at = _datetime.utcnow()
    order.email_sent_to = recipient
    db.commit()
    db.refresh(order)
    return order


def update_order_tax_key(db: Session, order: Order, tax_key_id: int) -> Order:
    """Setzt tax_key_id UND vat_rate zusammen aus dem gewählten
    Steuerschlüssel -- die eigentliche Summenberechnung (order_to_dict) liest
    weiterhin nur vat_rate und merkt vom Steuerschlüssel selbst nichts."""
    key = db.get(TaxKey, tax_key_id)
    if key is None:
        raise ValueError("Steuerschlüssel nicht gefunden.")
    order.tax_key_id = tax_key_id
    order.vat_rate = key.vat_rate
    db.commit()
    db.refresh(order)
    return order


def _validate_employees(db: Session, caseworker_employee_id: int | None, project_manager_employee_id: int | None):
    for employee_id, label in ((caseworker_employee_id, "Sachbearbeiter"), (project_manager_employee_id, "Projektleiter / Vorarbeiter")):
        if employee_id is not None:
            employee = db.get(Employee, employee_id)
            if employee is None or not employee.active:
                raise ValueError(f"{label} wurde nicht gefunden oder ist inaktiv.")


def _copy_quote_scope_to_order(db: Session, order: Order, quote) -> None:
    meta, sections, layouts = ensure_quote_structure(db, quote)
    project = quote.project
    customer = project.customer
    prop = project.property

    customer_city = " ".join(x for x in [customer.postal_code, customer.city] if x)

    order.title = quote.title
    order.vat_rate = quote.vat_rate
    order.intro_text = quote.intro_text
    order.outro_text = quote.outro_text
    order.customer_name = customer.name
    order.customer_number = customer.customer_number
    order.customer_address = _address(customer.street, customer_city)
    if prop:
        prop_city = " ".join(x for x in [prop.postal_code, prop.city] if x)
        order.property_name = prop.name
        order.property_address = _address(prop.street, prop_city)
    else:
        # Kein Objekt gewählt -- die Hauptadresse des Kunden gilt als Einsatzort, exakt wie
        # contract_to_dict() (app/maintenance_contracts.py) es für den Wartungsvertrag selbst
        # bereits synthetisiert. Vorher wurde hier None geschrieben: ein per Schnellauftrag
        # ohne Objekt erzeugter Auftrag zeigte dadurch gar kein Objekt, obwohl der zugehörige
        # Wartungsvertrag "Hauptadresse" anzeigt -- dieselbe Sache, zweimal unterschiedlich
        # dargestellt (siehe CLAUDE.md "Objekte: Hauptadressen kennzeichnen und ausblenden").
        order.property_name = "Hauptadresse"
        order.property_address = _address(customer.street, customer_city)
    order.quote_number_snapshot = quote.quote_number

    # Existing scope is replaced as one controlled synchronization transaction.
    for item in list(order.items):
        db.delete(item)
    for section in list(order.sections):
        db.delete(section)
    db.flush()

    section_map: dict[int, int] = {}
    top = sorted([s for s in sections if s.parent_id is None], key=lambda x: (x.sort_order, x.id))
    children = sorted([s for s in sections if s.parent_id is not None], key=lambda x: (x.sort_order, x.id))
    for source in top + children:
        parent_snapshot_id = section_map.get(source.parent_id) if source.parent_id else None
        snap = OrderSection(
            order_id=order.id,
            parent_id=parent_snapshot_id,
            source_quote_section_id=source.id,
            title=source.title,
            description=source.description,
            sort_order=source.sort_order,
            section_number=source.section_number,
        )
        db.add(snap)
        db.flush()
        section_map[source.id] = snap.id

    # Keep quote ordering from the layout table, not the raw relationship order.
    quote_items = sorted(quote.items, key=lambda i: ((layouts.get(i.id).sort_order if layouts.get(i.id) else i.sort_order), i.id))
    for item in quote_items:
        layout = layouts.get(item.id)
        order_item = OrderItem(
            order_id=order.id,
            section_id=section_map.get(layout.section_id) if layout and layout.section_id else None,
            source_quote_item_id=item.id,
            sort_order=(layout.sort_order if layout else item.sort_order or 10),
            position_number=item.position_number,
            gaeb_oz=item.gaeb_oz,
            position_type=item.position_type,
            source_external_id=item.source_external_id,
            short_text=item.short_text,
            long_text=item.long_text,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            include_in_total=(layout.include_in_total if layout else True),
        )
        db.add(order_item)
        db.flush()
        source_calc = item.project_calculation
        if source_calc is not None:
            snap_calc = OrderItemCalculationSnapshot(
                order_item_id=order_item.id,
                site_time_minutes=source_calc.site_time_minutes,
                workshop_time_minutes=source_calc.workshop_time_minutes,
                labor_rate=source_calc.labor_rate,
                material_markup_pct=source_calc.material_markup_pct,
                equipment_cost=source_calc.equipment_cost,
                subcontractor_cost=source_calc.subcontractor_cost,
                other_cost=source_calc.other_cost,
                overhead_pct=source_calc.overhead_pct,
                risk_profit_pct=source_calc.risk_profit_pct,
                effective_sale_price=item.unit_price,
            )
            db.add(snap_calc)
            db.flush()
            for material in source_calc.materials:
                db.add(OrderItemMaterialSnapshot(
                    calculation_id=snap_calc.id,
                    article_number=material.article_number,
                    name=material.name,
                    unit=material.unit,
                    quantity=material.quantity,
                    waste_pct=material.waste_pct,
                    purchase_price=material.purchase_price,
                    price_basis=material.price_basis,
                ))


def create_order_from_quote(
    db: Session, quote_id: int, *, order_date: date, execution_start: date | None,
    execution_end: date | None, caseworker_employee_id: int | None,
    project_manager_employee_id: int | None, payment_terms: str | None,
    remarks: str | None, status: str = "beauftragt", actor_name: str = "System",
) -> Order:
    existing = db.scalar(select(Order).where(Order.source_quote_id == quote_id))
    if existing is not None:
        raise ValueError(f"Aus diesem Angebot existiert bereits Auftrag {existing.order_number}. Änderungen können in diesen Auftrag übernommen werden.")
    quote = load_quote(db, quote_id)
    if quote is None:
        raise ValueError("Angebot nicht gefunden.")
    if not quote.items:
        raise ValueError("Das Angebot enthält keine Positionen und kann nicht beauftragt werden.")
    meta, _, _ = ensure_quote_structure(db, quote)
    project = quote.project

    if caseworker_employee_id is None:
        assignment = db.scalar(select(QuoteEmployeeAssignment).where(QuoteEmployeeAssignment.quote_id == quote.id))
        if assignment is not None:
            caseworker_employee_id = assignment.caseworker_employee_id
    _validate_employees(db, caseworker_employee_id, project_manager_employee_id)

    order = Order(
        order_number=issue_number(db, "order"),
        project_id=project.id,
        source_quote_id=quote.id,
        quote_number_snapshot=quote.quote_number,
        title=quote.title,
        status=status or "beauftragt",
        vat_rate=quote.vat_rate,
        intro_text=quote.intro_text,
        outro_text=quote.outro_text,
        customer_name=project.customer.name,
        customer_number=project.customer.customer_number,
        customer_address=None,
        property_name=project.property.name if project.property else None,
        property_address=None,
        order_date=order_date,
        execution_start=execution_start,
        execution_end=execution_end,
        payment_terms=payment_terms if payment_terms is not None else meta.payment_terms,
        remarks=remarks,
        caseworker_employee_id=caseworker_employee_id,
        project_manager_employee_id=project_manager_employee_id,
    )
    db.add(order)
    db.flush()
    _copy_quote_scope_to_order(db, order, quote)

    quote.status = "beauftragt"
    project.status = "beauftragt"
    db.commit()
    order = load_order(db, order.id)
    create_order_revision(db, order, reason="Erstbeauftragung aus Angebot", source="quote", actor_name=actor_name)
    return load_order(db, order.id)


def sync_order_from_source_quote(db: Session, order: Order, *, actor_name: str = "System", reason: str | None = None) -> Order:
    quote = load_quote(db, order.source_quote_id)
    if quote is None:
        raise ValueError("Quellangebot nicht gefunden.")
    if not quote.items:
        raise ValueError("Das Quellangebot enthält keine Positionen.")
    if order_matches_source_quote(db, order):
        return order

    # Preserve manually planned procurement data before replacing order-item IDs.
    from .work_preparation import capture_preparation_material_state, refresh_preparation_materials, load_preparation
    preserved = capture_preparation_material_state(db, order.id)
    prep = load_preparation(db, order.id)
    if prep is not None:
        # Release FK references before the old order-item snapshot is replaced.
        for row in prep.materials:
            row.source_material_snapshot_id = None
            row.source_order_item_id = None
        db.flush()

    _copy_quote_scope_to_order(db, order, quote)
    quote.status = "beauftragt"
    order.project.status = "beauftragt"
    db.commit()
    order = load_order(db, order.id)
    create_order_revision(
        db,
        order,
        reason=(reason or f"Auftragsstand aus {quote.quote_number} aktualisiert"),
        source="quote_sync",
        actor_name=actor_name,
    )
    refresh_preparation_materials(db, order.id, preserved=preserved)
    return load_order(db, order.id)


def update_order_header(db: Session, order: Order, **values) -> Order:
    _validate_employees(db, values.get("caseworker_employee_id"), values.get("project_manager_employee_id"))
    for key, value in values.items():
        setattr(order, key, value)
    db.commit()
    return load_order(db, order.id)


def update_order_item(db: Session, order_id: int, item_id: int, **values) -> Order:
    item = db.get(OrderItem, item_id)
    if item is None or item.order_id != order_id:
        raise ValueError("Auftragsposition nicht gefunden.")
    for key, value in values.items():
        setattr(item, key, value)
    # Keep the effective snapshot sales price aligned with direct EP edits.
    if item.calculation_snapshot is not None and "unit_price" in values:
        item.calculation_snapshot.effective_sale_price = values["unit_price"]
    db.commit()
    from .work_preparation import refresh_preparation_materials
    refresh_preparation_materials(db, order_id)
    return load_order(db, order_id)


def update_order_section(db: Session, order_id: int, section_id: int, *, title: str, description: str | None) -> Order:
    section = db.get(OrderSection, section_id)
    if section is None or section.order_id != order_id:
        raise ValueError("Auftragstitel nicht gefunden.")
    section.title = title.strip()
    section.description = description
    db.commit()
    return load_order(db, order_id)


def list_order_revisions(db: Session, order_id: int) -> list[OrderRevision]:
    return list(db.scalars(select(OrderRevision).where(OrderRevision.order_id == order_id).order_by(OrderRevision.revision_number.desc())).all())


def ensure_existing_order_revisions(db: Session) -> int:
    """Legt für Bestandsaufträge aus <=0.8 einmalig Revision 1 an."""
    created = 0
    order_ids = list(db.scalars(select(Order.id).order_by(Order.id)).all())
    for order_id in order_ids:
        exists = db.scalar(select(OrderRevision.id).where(OrderRevision.order_id == order_id).limit(1))
        if exists is not None:
            continue
        order = load_order(db, order_id)
        if order is None:
            continue
        create_order_revision(
            db, order,
            reason="Bestandsauftrag beim Update auf 0.8.1 übernommen",
            source="migration",
            actor_name="System",
        )
        created += 1
    return created
