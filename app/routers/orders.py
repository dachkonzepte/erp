"""Router: orders

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 9 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..invoices import invoice_summary_for_order
from ..models import Order
from ..order_pdf import build_order_pdf
from ..orders import create_order_revision, list_order_revisions, load_order, order_to_dict, send_order_email, sync_order_from_source_quote, update_order_header, update_order_item, update_order_section, update_order_tax_key
from ..schemas import OrderEmailSend, OrderItemUpdate, OrderListOut, OrderOut, OrderRevisionCreate, OrderRevisionOut, OrderSectionUpdate, OrderSyncRequest, OrderUpdate, TaxKeySelection

router = APIRouter()

@router.get("/api/orders", response_model=list[OrderListOut])
def list_all_orders(db: Session = Depends(get_db)):
    orders = db.scalars(select(Order).options(selectinload(Order.project), selectinload(Order.items)).order_by(Order.id.desc())).all()
    result = []
    for order in orders:
        loaded = load_order(db, order.id)
        values = order_to_dict(loaded, db)
        invoice_count, fully_invoiced = invoice_summary_for_order(db, loaded.id)
        result.append(OrderListOut(
            id=loaded.id, order_number=loaded.order_number, project_id=loaded.project_id,
            project_number=loaded.project.project_number, project_name=loaded.project.name,
            customer_name=loaded.customer_name, title=loaded.title, status=loaded.status,
            order_date=loaded.order_date, net_total=values["net_total"], gross_total=values["gross_total"],
            invoice_count=invoice_count, fully_invoiced=fully_invoiced,
        ))
    return result


@router.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = load_order(db, order_id)
    if order is None: raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return OrderOut.model_validate(order_to_dict(order, db))


@router.put("/api/orders/{order_id}", response_model=OrderOut)
def put_order(order_id: int, payload: OrderUpdate, db: Session = Depends(get_db)):
    order=load_order(db,order_id)
    if order is None: raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    try:
        order=update_order_header(db,order,**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OrderOut.model_validate(order_to_dict(order, db))


@router.put("/api/orders/{order_id}/tax-key", response_model=OrderOut)
def put_order_tax_key(order_id: int, payload: TaxKeySelection, db: Session = Depends(get_db)):
    order = load_order(db, order_id)
    if order is None: raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    try:
        order = update_order_tax_key(db, order, payload.tax_key_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OrderOut.model_validate(order_to_dict(order, db))


@router.put("/api/orders/{order_id}/items/{item_id}", response_model=OrderOut)
def put_order_item(order_id: int, item_id: int, payload: OrderItemUpdate, db: Session = Depends(get_db)):
    try:
        order = update_order_item(db, order_id, item_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OrderOut.model_validate(order_to_dict(order, db))


@router.put("/api/orders/{order_id}/sections/{section_id}", response_model=OrderOut)
def put_order_section(order_id: int, section_id: int, payload: OrderSectionUpdate, db: Session = Depends(get_db)):
    try:
        order = update_order_section(db, order_id, section_id, title=payload.title, description=payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OrderOut.model_validate(order_to_dict(order, db))


@router.post("/api/orders/{order_id}/sync-source-quote", response_model=OrderOut)
def sync_order_source(order_id: int, payload: OrderSyncRequest, request: Request, db: Session = Depends(get_db)):
    order = load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    actor = getattr(request.state, "erp_user", None)
    actor_name = getattr(actor, "display_name", None) or getattr(actor, "username", None) or "System"
    try:
        order = sync_order_from_source_quote(db, order, actor_name=actor_name, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OrderOut.model_validate(order_to_dict(order, db))


@router.get("/api/orders/{order_id}/revisions", response_model=list[OrderRevisionOut])
def get_order_revisions(order_id: int, db: Session = Depends(get_db)):
    if db.get(Order, order_id) is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return [OrderRevisionOut.model_validate({
        "id": r.id, "order_id": r.order_id, "revision_number": r.revision_number,
        "reason": r.reason, "source": r.source, "created_by_name": r.created_by_name,
        "created_at": r.created_at,
    }) for r in list_order_revisions(db, order_id)]


@router.post("/api/orders/{order_id}/revisions", response_model=OrderRevisionOut)
def save_order_revision_route(order_id: int, payload: OrderRevisionCreate, request: Request, db: Session = Depends(get_db)):
    order = load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    actor = getattr(request.state, "erp_user", None)
    actor_name = getattr(actor, "display_name", None) or getattr(actor, "username", None) or "System"
    rev = create_order_revision(db, order, reason=payload.reason, source="manual", actor_name=actor_name)
    return OrderRevisionOut.model_validate({
        "id": rev.id, "order_id": rev.order_id, "revision_number": rev.revision_number,
        "reason": rev.reason, "source": rev.source, "created_by_name": rev.created_by_name,
        "created_at": rev.created_at,
    })


@router.get("/api/orders/{order_id}/pdf")
def order_pdf(order_id: int, db: Session = Depends(get_db)):
    order=load_order(db,order_id)
    if order is None: raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    pdf=build_order_pdf(db,order)
    filename=f"Auftragsbestaetigung_{order.order_number}.pdf".replace("/","-")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition":f'inline; filename="{filename}"'})


@router.post("/api/orders/{order_id}/send-email", response_model=OrderOut)
def post_send_order_email(order_id: int, payload: OrderEmailSend, db: Session = Depends(get_db)):
    order = load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    try:
        updated = send_order_email(db, order, to_email=payload.to_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return order_to_dict(updated, db)
