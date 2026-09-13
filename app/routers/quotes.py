"""Router: quotes

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 20 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Employee, EmployeeRoleSettings, Order, Project, Quote, QuoteEmployeeAssignment, QuoteItem, QuoteItemCalculation, QuoteItemLayout
from ..orders import create_order_from_quote, load_order, order_to_dict
from ..projects import add_service_to_quote, auto_number_quote, build_quote_item_calculation, create_free_quote_item, create_quote_section, delete_quote_section, duplicate_quote_item, ensure_quote_item_calculation, load_quote, quote_to_dict, reorder_quote, send_quote_email, set_item_layout, update_quote_section, update_quote_tax_key
from ..quote_framed_pdf import build_quote_framed_pdf
from ..schemas import OrderCreateFromQuote, OrderOut, QuoteDocumentMetaUpdate, QuoteEmailSend, QuoteFreeItemCreate, QuoteItemCalculationOut, QuoteItemCalculationUpdate, QuoteItemCreate, QuoteItemLayoutUpdate, QuoteItemUpdate, QuoteOut, QuoteReorderRequest, QuoteSectionCreate, QuoteSectionUpdate, QuoteUpdate, TaxKeySelection

router = APIRouter()

@router.get("/api/quotes/{quote_id}/order", response_model=OrderOut)
def get_order_for_quote(quote_id: int, db: Session = Depends(get_db)):
    row = db.scalar(select(Order).where(Order.source_quote_id == quote_id))
    if row is None: raise HTTPException(status_code=404, detail="Für dieses Angebot existiert noch kein Auftrag.")
    return OrderOut.model_validate(order_to_dict(load_order(db, row.id), db))


@router.post("/api/quotes/{quote_id}/convert-to-order", response_model=OrderOut)
def convert_quote_to_order(quote_id: int, payload: OrderCreateFromQuote, request: Request, db: Session = Depends(get_db)):
    actor = getattr(request.state, "erp_user", None)
    actor_name = getattr(actor, "display_name", None) or getattr(actor, "username", None) or "System"
    try:
        order = create_order_from_quote(db, quote_id, actor_name=actor_name, **payload.model_dump())
    except ValueError as exc:
        message=str(exc); code=409 if "bereits Auftrag" in message else 422
        raise HTTPException(status_code=code, detail=message) from exc
    return OrderOut.model_validate(order_to_dict(order, db))


@router.get("/api/quotes")
def list_all_quotes(db: Session = Depends(get_db)):
    quotes = db.scalars(
        select(Quote)
        .options(
            selectinload(Quote.project).selectinload(Project.customer),
            selectinload(Quote.project).selectinload(Project.property),
            selectinload(Quote.items),
        )
        .order_by(Quote.id.desc())
    ).all()
    result = []
    for quote in quotes:
        loaded = load_quote(db, quote.id)
        values = quote_to_dict(loaded)
        project = quote.project
        meta = values.get("document_meta") or {}
        result.append({
            "id": quote.id,
            "quote_number": quote.quote_number,
            "title": quote.title,
            "status": quote.status,
            "project_id": quote.project_id,
            "project_number": project.project_number,
            "project_name": project.name,
            "customer_id": project.customer_id,
            "customer_name": project.customer.name,
            "property_name": project.property.name if project.property else None,
            "net_total": values["net_total"],
            "gross_total": values["gross_total"],
            "valid_until": meta.get("valid_until"),
            "caseworker_employee_id": meta.get("contact_person_employee_id"),
            "created_at": quote.created_at.isoformat() if quote.created_at else None,
            "updated_at": quote.updated_at.isoformat() if quote.updated_at else None,
        })
    return result


@router.put("/api/quotes/{quote_id}", response_model=QuoteOut)
def update_quote_header(quote_id: int, payload: QuoteUpdate, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    quote.title = payload.title
    quote.status = payload.status
    quote.vat_rate = payload.vat_rate
    quote.intro_text = payload.intro_text
    quote.outro_text = payload.outro_text
    quote.outro_text_2 = payload.outro_text_2
    db.commit()
    quote = load_quote(db, quote_id)
    return QuoteOut.model_validate(quote_to_dict(quote))


@router.put("/api/quotes/{quote_id}/tax-key", response_model=QuoteOut)
def put_quote_tax_key(quote_id: int, payload: TaxKeySelection, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    try:
        update_quote_tax_key(db, quote, payload.tax_key_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    quote = load_quote(db, quote_id)
    return QuoteOut.model_validate(quote_to_dict(quote))


@router.put("/api/quotes/{quote_id}/document-meta", response_model=QuoteOut)
def update_quote_document_meta(quote_id: int, payload: QuoteDocumentMetaUpdate, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    from ..projects import ensure_quote_structure
    meta, _, _ = ensure_quote_structure(db, quote)
    data = payload.model_dump()
    employee_id = data.pop("contact_person_employee_id", None)
    for key, value in data.items():
        setattr(meta, key, value)
    assignment = db.scalar(select(QuoteEmployeeAssignment).where(QuoteEmployeeAssignment.quote_id == quote.id))
    if employee_id is not None:
        employee = db.get(Employee, employee_id)
        if employee is None:
            raise HTTPException(status_code=422, detail="Sachbearbeiter wurde nicht gefunden.")
        role = db.scalar(select(EmployeeRoleSettings).where(EmployeeRoleSettings.employee_id == employee.id))
        if not employee.active or role is None or not role.available_as_caseworker:
            raise HTTPException(status_code=422, detail="Mitarbeiter ist nicht als Sachbearbeiter freigegeben.")
        if assignment is None:
            assignment = QuoteEmployeeAssignment(quote_id=quote.id)
            db.add(assignment)
        assignment.caseworker_employee_id = employee.id
        meta.contact_person = f"{employee.first_name} {employee.last_name}".strip()
    else:
        if assignment is not None:
            assignment.caseworker_employee_id = None
        if not data.get("contact_person"):
            meta.contact_person = None
    db.commit()
    quote = load_quote(db, quote_id)
    return QuoteOut.model_validate(quote_to_dict(quote))


@router.post("/api/quotes/{quote_id}/sections", response_model=QuoteOut)
def add_quote_section_api(quote_id: int, payload: QuoteSectionCreate, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    try:
        create_quote_section(db, quote_id, payload.title, payload.description, payload.parent_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.put("/api/quotes/{quote_id}/sections/{section_id}", response_model=QuoteOut)
def edit_quote_section_api(quote_id: int, section_id: int, payload: QuoteSectionUpdate, db: Session = Depends(get_db)):
    try:
        update_quote_section(db, quote_id, section_id, payload.title, payload.description, payload.parent_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.delete("/api/quotes/{quote_id}/sections/{section_id}", response_model=QuoteOut)
def remove_quote_section_api(quote_id: int, section_id: int, db: Session = Depends(get_db)):
    try:
        delete_quote_section(db, quote_id, section_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.post("/api/quotes/{quote_id}/free-items", response_model=QuoteOut)
def add_free_item_api(quote_id: int, payload: QuoteFreeItemCreate, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    try:
        create_free_quote_item(db, quote, **payload.model_dump())
        auto_number_quote(db, quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.put("/api/quotes/{quote_id}/items/{item_id}/layout", response_model=QuoteOut)
def update_item_layout_api(quote_id: int, item_id: int, payload: QuoteItemLayoutUpdate, db: Session = Depends(get_db)):
    try:
        set_item_layout(db, quote_id, item_id, payload.section_id, payload.include_in_total)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.post("/api/quotes/{quote_id}/items/{item_id}/duplicate", response_model=QuoteOut)
def duplicate_item_api(quote_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(QuoteItem).options(selectinload(QuoteItem.project_calculation).selectinload(QuoteItemCalculation.materials)).where(QuoteItem.id == item_id, QuoteItem.quote_id == quote_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Angebotsposition nicht gefunden.")
    duplicate_quote_item(db, item)
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.post("/api/quotes/{quote_id}/reorder", response_model=QuoteOut)
def reorder_quote_api(quote_id: int, payload: QuoteReorderRequest, db: Session = Depends(get_db)):
    if load_quote(db, quote_id) is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    try:
        reorder_quote(db, quote_id, [x.model_dump() for x in payload.sections], [x.model_dump() for x in payload.items])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.post("/api/quotes/{quote_id}/auto-number", response_model=QuoteOut)
def auto_number_quote_api(quote_id: int, db: Session = Depends(get_db)):
    if load_quote(db, quote_id) is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    auto_number_quote(db, quote_id)
    return QuoteOut.model_validate(quote_to_dict(load_quote(db, quote_id)))


@router.get("/api/quotes/{quote_id}/pdf")
def quote_pdf_api(quote_id: int, db: Session = Depends(get_db)):
    """Regulärer PDF-Abruf -- über den gemeinsamen PDF-Rahmen (build_quote_framed_pdf, CLAUDE.md
    "Gemeinsamer Dokumenttyp"/Angebot). Damit auf demselben Renderer wie der E-Mail-Versand
    (send_quote_email()) -- beide Wege, die tatsächlich beim Kunden ankommen, zeigen dasselbe
    Ergebnis."""
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    pdf = build_quote_framed_pdf(db, quote)
    filename = f"{quote.quote_number}.pdf".replace("/", "-")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.post("/api/quotes/{quote_id}/send-email", response_model=QuoteOut)
def post_send_quote_email(quote_id: int, payload: QuoteEmailSend, db: Session = Depends(get_db)):
    """Tatsächlicher E-Mail-Versand -- verwendet den gemeinsamen PDF-Rahmen (build_quote_framed_pdf,
    intern in send_quote_email()), damit der tatsächlich an Kunden versendete Anhang dem
    produktiv genutzten Renderer entspricht."""
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    try:
        updated = send_quote_email(db, quote, to_email=payload.to_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return quote_to_dict(updated)


@router.get("/api/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: int, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    return QuoteOut.model_validate(quote_to_dict(quote))


@router.post("/api/quotes/{quote_id}/items", response_model=QuoteOut)
def add_quote_item(quote_id: int, payload: QuoteItemCreate, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    item = add_service_to_quote(db, quote, payload.service_id, payload.quantity, payload.section_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    auto_number_quote(db, quote_id)
    quote = load_quote(db, quote_id)
    return QuoteOut.model_validate(quote_to_dict(quote))


@router.put("/api/quotes/{quote_id}/items/{item_id}", response_model=QuoteOut)
def update_quote_item(quote_id: int, item_id: int, payload: QuoteItemUpdate, db: Session = Depends(get_db)):
    item = db.get(QuoteItem, item_id)
    if item is None or item.quote_id != quote_id:
        raise HTTPException(status_code=404, detail="Angebotsposition nicht gefunden.")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    quote = load_quote(db, quote_id)
    return QuoteOut.model_validate(quote_to_dict(quote))


@router.get(
    "/api/quotes/{quote_id}/items/{item_id}/calculation",
    response_model=QuoteItemCalculationOut,
)
def get_quote_item_calculation(quote_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.scalar(
        select(QuoteItem)
        .options(
            selectinload(QuoteItem.project_calculation).selectinload(QuoteItemCalculation.materials),
            selectinload(QuoteItem.source_service),
        )
        .where(QuoteItem.id == item_id, QuoteItem.quote_id == quote_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Angebotsposition nicht gefunden.")
    calc = ensure_quote_item_calculation(db, item)
    if calc is None:
        raise HTTPException(status_code=422, detail="Für diese Position ist keine Katalogkalkulation vorhanden.")
    item = db.scalar(
        select(QuoteItem)
        .options(selectinload(QuoteItem.project_calculation).selectinload(QuoteItemCalculation.materials))
        .where(QuoteItem.id == item_id)
    )
    return QuoteItemCalculationOut.model_validate(build_quote_item_calculation(item))


@router.put(
    "/api/quotes/{quote_id}/items/{item_id}/calculation",
    response_model=QuoteItemCalculationOut,
)
def update_quote_item_calculation(
    quote_id: int, item_id: int, payload: QuoteItemCalculationUpdate, db: Session = Depends(get_db)
):
    item = db.scalar(
        select(QuoteItem)
        .options(selectinload(QuoteItem.project_calculation).selectinload(QuoteItemCalculation.materials))
        .where(QuoteItem.id == item_id, QuoteItem.quote_id == quote_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Angebotsposition nicht gefunden.")
    calc = ensure_quote_item_calculation(db, item)
    if calc is None:
        raise HTTPException(status_code=422, detail="Für diese Position ist keine Katalogkalkulation vorhanden.")

    calc.site_time_minutes = payload.site_time_minutes
    calc.workshop_time_minutes = payload.workshop_time_minutes
    calc.labor_rate = payload.labor_rate
    calc.material_markup_pct = payload.material_markup_pct
    calc.equipment_cost = payload.equipment_cost
    calc.subcontractor_cost = payload.subcontractor_cost
    calc.other_cost = payload.other_cost
    calc.overhead_pct = payload.overhead_pct
    calc.risk_profit_pct = payload.risk_profit_pct
    calc.manual_sale_price = payload.manual_sale_price
    calc.notes = payload.notes

    rows = {row.id: row for row in calc.materials}
    for material in payload.materials:
        row = rows.get(material.id)
        if row is None:
            raise HTTPException(status_code=422, detail=f"Material {material.id} gehört nicht zu dieser Angebotsposition.")
        row.quantity = material.quantity
        row.waste_pct = material.waste_pct
        row.purchase_price = material.purchase_price
        row.price_basis = material.price_basis

    result = build_quote_item_calculation(item)
    item.unit_price = result["effective_sale_price"]
    db.commit()
    item = db.scalar(
        select(QuoteItem)
        .options(selectinload(QuoteItem.project_calculation).selectinload(QuoteItemCalculation.materials))
        .where(QuoteItem.id == item_id)
    )
    return QuoteItemCalculationOut.model_validate(build_quote_item_calculation(item))


@router.delete("/api/quotes/{quote_id}/items/{item_id}", response_model=QuoteOut)
def delete_quote_item(quote_id: int, item_id: int, db: Session = Depends(get_db)):
    quote = load_quote(db, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden.")
    item = next((x for x in quote.items if x.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Angebotsposition nicht gefunden.")
    layout = db.scalar(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id == item_id))
    if layout is not None:
        db.delete(layout)
    db.delete(item)
    db.commit()
    auto_number_quote(db, quote_id)
    quote = load_quote(db, quote_id)
    return QuoteOut.model_validate(quote_to_dict(quote))
