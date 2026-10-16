"""Router: Zahlungseingänge (seit 1.8.78, Zahlungsstufe Z1, docs/archiv/zahlungen.md).

Geschäftslogik in app/payments.py; hier die HTTP-Anbindung: unbekannte ID 404 (IdNichtGefunden), am Stand nicht möglich 409
(PaymentRejected: Überbuchung, Rechnung eines anderen Kunden, Stornorechnung, schon gegengebucht), falsche Eingabe 400.
Rollen wie die Rechnungen (ab buero_auftrag, für den Monteur nicht vorgesehen). "Erfasst von" kommt aus der Anmeldung.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_dispatch import actor_of
from ..invoices import get_invoice
from ..models import AppUser, Customer, Invoice, Payment, PaymentAllocation
from ..payments import (
    ChargeLine, Line, PaymentRejected, RefundLine, allocate_rest, book_customer_refund, book_payment, book_refund, customer_balances,
    customer_payments, open_invoices_of_customer, payment_to_dict, proposal, reverse_allocation, reverse_payment,
    unallocated_by_customer,
)
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import (
    CustomerBalanceOut, CustomerPaymentsOut, CustomerRefundCreate, OpenInvoiceOut, PaymentAllocate, PaymentCreate, PaymentOut,
    PaymentProposalOut, PaymentReverse, RefundCreate, UnallocatedPaymentsOut,
)
from ..zugehoerigkeit import IdNichtGefunden

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Zahlungen sind nur für Büro und Administratoren verfügbar."))


def _lines(payload_lines) -> list[Line]:
    # Seit 1.8.81 mit den Zahlungen auf Nebenforderungen der Rechnung (§ 367 BGB, app/payments.py).
    return [Line(invoice_id=line.invoice_id, zahlung=line.zahlung, skonto=line.skonto, einbehalt=line.einbehalt,
                 charges=tuple(ChargeLine(c.charge_id, c.amount) for c in line.charges))
            for line in payload_lines]


def _http(error: Exception) -> HTTPException:
    if isinstance(error, IdNichtGefunden):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, PaymentRejected):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


def _customer_or_404(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    return customer


def _payment_or_404(db: Session, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Zahlung nicht gefunden.")
    return payment


@router.get("/api/customers/{customer_id}/payments", response_model=CustomerPaymentsOut)
def get_customer_payments(customer_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _customer_or_404(db, customer_id)
    return customer_payments(db, customer_id)


@router.get("/api/customers/{customer_id}/open-invoices", response_model=list[OpenInvoiceOut])
def get_customer_open_invoices(customer_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    _customer_or_404(db, customer_id)
    return open_invoices_of_customer(db, customer_id)


@router.get("/api/payments/unallocated", response_model=list[UnallocatedPaymentsOut])
def get_unallocated_payments(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return unallocated_by_customer(db)


@router.get("/api/payments/customer-balances", response_model=list[CustomerBalanceOut])
def get_customer_balances(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.8.93 (Nacharbeit R4c Punkt 3): Guthaben der Kunden -- nicht zugeordneter Rest und Guthaben aus Endrechnungen je Kunde."""
    return customer_balances(db)


@router.post("/api/customers/{customer_id}/refunds", response_model=PaymentOut)
def post_customer_refund(customer_id: int, payload: CustomerRefundCreate, db: Session = Depends(get_db, scope="function"),
                         user: AppUser = _role_dep):
    """Seit 1.8.93: Erstattung des Guthabens des Kunden als ein Zahlungsausgang -- aus Resten seiner Zahlungen und aus Guthaben von
    Endrechnungen (app/payments.py::book_customer_refund())."""
    _customer_or_404(db, customer_id)
    user_id, user_name = actor_of(user)
    try:
        payment = book_customer_refund(
            db, customer_id, paid_on=payload.paid_on, note=payload.note,
            lines=[RefundLine(amount=line.amount, invoice_id=line.invoice_id, payment_id=line.payment_id) for line in payload.lines],
            user_id=user_id, user_name=user_name)
    except ValueError as e:
        raise _http(e) from e
    return payment_to_dict(db, payment)


@router.get("/api/invoices/{invoice_id}/payment-proposal", response_model=PaymentProposalOut)
def get_payment_proposal(invoice_id: int, amount: Decimal = Query(gt=0), received_on: date = Query(),
                         db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Nur ein Vorschlag (liest, schreibt nichts): ältere offene Rechnungen desselben Auftrags zuerst, dann diese; Skonto, wo
    der Eingang in der Frist liegt und der Betrag passt."""
    invoice = get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden.")
    try:
        return proposal(db, invoice, amount=amount, received_on=received_on)
    except ValueError as e:
        raise _http(e) from e


@router.post("/api/payments", response_model=PaymentOut)
def post_payment(payload: PaymentCreate, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    user_id, user_name = actor_of(user)
    try:
        payment = book_payment(db, customer_id=payload.customer_id, received_on=payload.received_on, amount=payload.amount,
                               note=payload.note, lines=_lines(payload.lines), user_id=user_id, user_name=user_name)
    except ValueError as e:
        raise _http(e) from e
    return payment_to_dict(db, payment)


@router.post("/api/payments/{payment_id}/allocations", response_model=PaymentOut)
def post_payment_allocations(payment_id: int, payload: PaymentAllocate, db: Session = Depends(get_db, scope="function"),
                             user: AppUser = _role_dep):
    payment = _payment_or_404(db, payment_id)
    user_id, user_name = actor_of(user)
    try:
        allocate_rest(db, payment, _lines(payload.lines), user_id=user_id, user_name=user_name)
    except ValueError as e:
        raise _http(e) from e
    return payment_to_dict(db, payment)


@router.post("/api/payments/{payment_id}/reverse", response_model=PaymentOut)
def post_payment_reverse(payment_id: int, payload: PaymentReverse, db: Session = Depends(get_db, scope="function"),
                         user: AppUser = _role_dep):
    payment = _payment_or_404(db, payment_id)
    user_id, user_name = actor_of(user)
    try:
        reverse_payment(db, payment, reason=payload.reason, user_id=user_id, user_name=user_name)
    except ValueError as e:
        raise _http(e) from e
    return payment_to_dict(db, payment)


@router.post("/api/invoices/{invoice_id}/refunds", response_model=PaymentOut)
def post_refund(invoice_id: int, payload: RefundCreate, db: Session = Depends(get_db, scope="function"), user: AppUser = _role_dep):
    """Seit 1.8.90 (R4c Punkt 6): Erstattung eines Guthabens als Zahlungsausgang (app/payments.py::book_refund())."""
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden.")
    user_id, user_name = actor_of(user)
    try:
        payment = book_refund(db, invoice, paid_on=payload.paid_on, amount=payload.amount, note=payload.note, user_id=user_id,
                              user_name=user_name)
    except ValueError as e:
        raise _http(e) from e
    return payment_to_dict(db, payment)


@router.post("/api/payment-allocations/{allocation_id}/reverse", response_model=PaymentOut)
def post_allocation_reverse(allocation_id: int, payload: PaymentReverse, db: Session = Depends(get_db, scope="function"),
                            user: AppUser = _role_dep):
    allocation = db.get(PaymentAllocation, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Zuordnung nicht gefunden.")
    user_id, user_name = actor_of(user)
    try:
        reverse_allocation(db, allocation, reason=payload.reason, user_id=user_id, user_name=user_name)
    except ValueError as e:
        raise _http(e) from e
    return payment_to_dict(db, db.get(Payment, allocation.payment_id))
