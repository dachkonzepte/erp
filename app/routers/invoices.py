"""Router: invoices (seit 1.0.36).

Endpunkte für das Rechnungswesen -- Geschäftslogik liegt vollständig in
app/invoices.py, hier nur die HTTP-Anbindung und die Übersetzung von
ValueError (unzulässiger Zustandsübergang, z.B. Bearbeitung einer bereits
versendeten Rechnung) in aussagekräftige 400-Antworten.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..calculation import get_or_create_settings
from ..database import get_db
from ..invoice_pdf import build_invoice_pdf
from ..invoices import (
    add_invoice_item, create_abschlag_leistungsstand, create_abschlag_pauschal,
    create_invoice_from_time_entries, create_schlussrechnung, create_storno_draft,
    delete_invoice_draft, finalize_and_send_invoice, get_invoice, invoice_overview_row,
    invoice_to_dict, list_all_invoices, list_invoices_for_order, mark_invoice_paid,
    remove_invoice_item, send_invoice_email, update_invoice_header, update_invoice_item,
    update_invoice_payment_term, update_invoice_tax_key,
)
from ..models import AppUser, Order
from ..payment_terms import ensure_default_payment_terms
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..service_reports import list_materials_for_invoicing
from ..time_tracking import list_entries
from ..schemas import (
    InvoiceCreateAbschlagPauschal, InvoiceCreateFromOrder, InvoiceEmailSend, InvoiceHeaderUpdate,
    InvoiceItemCreate, InvoiceItemUpdate, InvoiceListOut, InvoiceMarkPaid, InvoiceOut,
    InvoiceOverviewOut, InvoicePaymentTermUpdate, TaxKeySelection,
)

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Rechnungen sind Büro-/Admin-Bereich, für einen
# Monteur an keiner Stelle vorgesehen -- keine Objekt-Filterung nötig, reiner Rollen-Block.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Rechnungen sind nur für Büro und Administratoren verfügbar."))


def _get_order_or_404(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return order


def _get_invoice_or_404(db: Session, invoice_id: int):
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden.")
    return invoice


@router.get("/api/orders/{order_id}/invoices", response_model=list[InvoiceListOut])
def get_invoices_for_order(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _get_order_or_404(db, order_id)
    invoices = list_invoices_for_order(db, order_id)
    return [invoice_to_dict(inv) for inv in invoices]


@router.get("/api/invoices", response_model=list[InvoiceOverviewOut])
def get_all_invoices(status: str | None = None, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoices = list_all_invoices(db, status=status)
    return [invoice_overview_row(inv) for inv in invoices]


@router.get("/api/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice_detail(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    return invoice_to_dict(invoice)


@router.post("/api/orders/{order_id}/invoices/abschlag-pauschal", response_model=InvoiceOut)
def post_abschlag_pauschal(order_id: int, payload: InvoiceCreateAbschlagPauschal, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    order = _get_order_or_404(db, order_id)
    ensure_default_payment_terms(db)
    invoice = create_abschlag_pauschal(
        db, order, lump_sum_net=payload.lump_sum_net,
        progress_description=payload.progress_description, due_date=payload.due_date,
    )
    return invoice_to_dict(invoice)


@router.post("/api/orders/{order_id}/invoices/abschlag-leistungsstand", response_model=InvoiceOut)
def post_abschlag_leistungsstand(order_id: int, payload: InvoiceCreateFromOrder, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    order = _get_order_or_404(db, order_id)
    ensure_default_payment_terms(db)
    invoice = create_abschlag_leistungsstand(db, order, due_date=payload.due_date)
    return invoice_to_dict(invoice)


@router.post("/api/orders/{order_id}/invoices/schlussrechnung", response_model=InvoiceOut)
def post_schlussrechnung(order_id: int, payload: InvoiceCreateFromOrder, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    order = _get_order_or_404(db, order_id)
    ensure_default_payment_terms(db)
    invoice = create_schlussrechnung(db, order, due_date=payload.due_date)
    return invoice_to_dict(invoice)


@router.post("/api/orders/{order_id}/invoices/aus-zeitbuchungen", response_model=InvoiceOut)
def post_invoice_from_time_entries(order_id: int, payload: InvoiceCreateFromOrder, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    order = _get_order_or_404(db, order_id)
    ensure_default_payment_terms(db)
    entries = list_entries(db, order_id=order_id)
    materials = list_materials_for_invoicing(db, order_id)
    try:
        invoice = create_invoice_from_time_entries(db, order, entries, materials, due_date=payload.due_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = invoice_to_dict(invoice)
    # Seit 1.2.23: sichtbarer, einmaliger Hinweis (kein persistiertes Feld), falls Katalog-
    # Material ohne konfigurierten Aufschlag abgerechnet wurde -- sonst fällt der fehlende
    # Aufschlag nicht auf, der Einkaufspreis sieht wie ein gültiger Preis aus.
    has_catalog_material = any(m.material_id is not None for m in materials)
    if has_catalog_material and get_or_create_settings(db).material_markup_pct == 0:
        result["material_markup_hint"] = (
            "Materialpositionen wurden ohne Aufschlag (Materialaufschlag steht auf 0 %) mit dem "
            "reinen Einkaufspreis eingetragen -- vor dem Versenden prüfen."
        )
    return result


@router.put("/api/invoices/{invoice_id}", response_model=InvoiceOut)
def put_invoice_header(invoice_id: int, payload: InvoiceHeaderUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        update_invoice_header(
            db, invoice, due_date=payload.due_date, progress_description=payload.progress_description,
            lump_sum_net=payload.lump_sum_net, intro_text=payload.intro_text,
            outro_text=payload.outro_text, outro_text_2=payload.outro_text_2, payment_terms=payload.payment_terms,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.put("/api/invoices/{invoice_id}/payment-term", response_model=InvoiceOut)
def put_invoice_payment_term(invoice_id: int, payload: InvoicePaymentTermUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        update_invoice_payment_term(db, invoice, payload.payment_term_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.put("/api/invoices/{invoice_id}/tax-key", response_model=InvoiceOut)
def put_invoice_tax_key(invoice_id: int, payload: TaxKeySelection, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        update_invoice_tax_key(db, invoice, payload.tax_key_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.post("/api/invoices/{invoice_id}/items", response_model=InvoiceOut)
def post_invoice_item(invoice_id: int, payload: InvoiceItemCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        add_invoice_item(
            db, invoice, short_text=payload.short_text, long_text=payload.long_text, unit=payload.unit,
            unit_price=payload.unit_price, ist_quantity=payload.ist_quantity,
            source_order_item_id=payload.source_order_item_id, soll_quantity=payload.soll_quantity,
            position_number=payload.position_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.put("/api/invoices/{invoice_id}/items/{item_id}", response_model=InvoiceOut)
def put_invoice_item(invoice_id: int, item_id: int, payload: InvoiceItemUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    item = next((i for i in invoice.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Rechnungsposition nicht gefunden.")
    try:
        update_invoice_item(
            db, invoice, item, short_text=payload.short_text, long_text=payload.long_text,
            unit=payload.unit, unit_price=payload.unit_price, ist_quantity=payload.ist_quantity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.delete("/api/invoices/{invoice_id}/items/{item_id}", response_model=InvoiceOut)
def delete_invoice_item(invoice_id: int, item_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        found = remove_invoice_item(db, invoice, item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not found:
        raise HTTPException(status_code=404, detail="Rechnungsposition nicht gefunden.")
    return invoice_to_dict(invoice)


@router.post("/api/invoices/{invoice_id}/send", response_model=InvoiceOut)
def post_send_invoice(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        finalize_and_send_invoice(db, invoice)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.post("/api/invoices/{invoice_id}/send-email", response_model=InvoiceOut)
def post_send_invoice_email(invoice_id: int, payload: InvoiceEmailSend, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Tatsächlicher E-Mail-Versand -- getrennt vom Finalisieren oben
    (/send), das nur Nummer/Status setzt. Kann auf einer bereits
    finalisierten Rechnung auch mehrfach aufgerufen werden."""
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        send_invoice_email(db, invoice, to_email=payload.to_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.post("/api/invoices/{invoice_id}/mark-paid", response_model=InvoiceOut)
def post_mark_paid(invoice_id: int, payload: InvoiceMarkPaid, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        mark_invoice_paid(db, invoice, paid_date=payload.paid_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(invoice)


@router.post("/api/invoices/{invoice_id}/storno", response_model=InvoiceOut)
def post_storno_invoice(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        storno = create_storno_draft(db, invoice)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_to_dict(storno)


@router.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        delete_invoice_draft(db, invoice)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": True}


@router.get("/api/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    invoice = _get_invoice_or_404(db, invoice_id)
    pdf = build_invoice_pdf(db, invoice)
    name_part = invoice.invoice_number or f"Entwurf-{invoice.id}"
    filename = f"Rechnung_{name_part}.pdf".replace("/", "-")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
