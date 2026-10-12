"""zahlungen -- Zahlungseingänge und Zuordnungen, "bezahlt" übernommen (seit 1.8.78, Zahlungsstufe Z1)

- payments: Zahlungseingang eines Kunden (Eingangsdatum, Betrag, Notiz, Herkunft erfasst/uebernommen, Gegenbuchung mit
  Begründung über reverses_payment_id, UNIQUE).
- payment_allocations: Zuordnung auf eine Rechnung bzw. Abzug an ihr (Art zahlung/skonto/einbehalt, Gegenbuchung über
  reverses_allocation_id, UNIQUE).
- Altbestand "bezahlt" (Vorgabe Z1 Nr. 7): je Rechnung mit Status "bezahlt" eine Zahlung über das Brutto zum bezahlt-Datum
  (fehlt es: Rechnungsdatum), Herkunft "uebernommen", ganz dieser Rechnung zugeordnet; die Rechnung steht danach auf
  "versendet" (der Zahlstand ist ab 1.8.78 abgeleitet). Eine Stornorechnung mit "bezahlt" bekommt keine Zahlung (eine
  Stornorechnung ist nie offen, Vorgabe Nr. 5), ebenso eine Rechnung mit Brutto 0 oder weniger. Eine stornierte Rechnung mit
  bezahlt-Datum bleibt, wie sie ist. paid_date bleibt an jeder Rechnung stehen -- Nachweis und Rückweg.
- Das Brutto rechnet die Migration selbst (Kopie von app/invoices.py::compute_invoice_totals() zum Stand 1.8.78, auf den Cent nach
  der Rundungsregel der Rechnung), damit sie nicht vom späteren App-Code abhängt; ein Test hält beide gleich.

downgrade(): stellt "bezahlt" wieder her (jede Rechnung mit übernommener Zuordnung, dazu jede "versendet" mit bezahlt-Datum --
seit 1.8.78 schreibt niemand mehr eins) und entfernt die Tabellen. Verweigert, sobald etwas gebucht ist, das der Rückweg verlöre:
eine erfasste Zahlung, eine Gegenbuchung oder eine weitere Zuordnung.

Revision ID: c7d41e9a2b63
Revises: f3a8c2d6b190
Create Date: 2026-10-12

"""
from datetime import datetime
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d41e9a2b63'
down_revision = 'f3a8c2d6b190'
branch_labels = None
depends_on = None

CENT = Decimal("0.01")
NOTIZ = "Übernommen aus dem Status „bezahlt“ (bis 1.8.77)"

_invoices = sa.table(
    "invoices",
    sa.column("id", sa.Integer), sa.column("order_id", sa.Integer), sa.column("invoice_type", sa.String),
    sa.column("status", sa.String), sa.column("invoice_date", sa.Date), sa.column("paid_date", sa.Date),
    sa.column("vat_rate", sa.Numeric(9, 4)), sa.column("lump_sum_net", sa.Numeric(18, 6)),
    sa.column("rounding_rule", sa.String),
)
_items = sa.table("invoice_items", sa.column("invoice_id", sa.Integer), sa.column("billed_total", sa.Numeric(18, 6)))
_orders = sa.table("orders", sa.column("id", sa.Integer), sa.column("project_id", sa.Integer))
_projects = sa.table("projects", sa.column("id", sa.Integer), sa.column("customer_id", sa.Integer))


def _half_up(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def brutto(invoice_type: str, rounding_rule: str | None, vat_rate, lump_sum_net, billed_totals) -> Decimal:
    """Brutto auf den Cent wie app/payments.py::payable_gross() (compute_invoice_totals(), dann nach der Rundungsregel der
    Rechnung auf den Cent): ab 1.8.11 ("half_up") Positionen, Netto und USt kaufmännisch; davor ungerundet, auf den Cent erst am
    Ende und halb-gerade (so druckte das PDF)."""
    rate = Decimal(vat_rate)
    if rounding_rule == "half_up":
        net = _half_up(lump_sum_net) if invoice_type == "abschlag_pauschal" else sum(
            (_half_up(t) for t in billed_totals), Decimal("0"))
        return net + _half_up(net * rate / Decimal("100"))
    net = Decimal(lump_sum_net or 0) if invoice_type == "abschlag_pauschal" else sum(
        (Decimal(t) for t in billed_totals), Decimal("0"))
    return (net + net * rate / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_EVEN)


def uebernehmen(bind) -> dict:
    """Legt je bezahlter Rechnung die übernommene Zahlung an und setzt sie auf "versendet". Gibt die Zählung zurück."""
    payments = sa.table(
        "payments", sa.column("id", sa.Integer), sa.column("customer_id", sa.Integer), sa.column("received_on", sa.Date),
        sa.column("amount", sa.Numeric(18, 2)), sa.column("note", sa.Text), sa.column("origin", sa.String),
        sa.column("created_at", sa.DateTime), sa.column("created_by_name", sa.String))
    allocations = sa.table(
        "payment_allocations", sa.column("payment_id", sa.Integer), sa.column("invoice_id", sa.Integer),
        sa.column("kind", sa.String), sa.column("amount", sa.Numeric(18, 2)), sa.column("created_at", sa.DateTime),
        sa.column("created_by_name", sa.String))
    rows = bind.execute(
        sa.select(_invoices, _projects.c.customer_id)
        .select_from(_invoices.join(_orders, _orders.c.id == _invoices.c.order_id)
                     .join(_projects, _projects.c.id == _orders.c.project_id))
        .where(_invoices.c.status == "bezahlt").order_by(_invoices.c.id)
    ).all()
    counts = {"zahlungen": 0, "storno_ohne_zahlung": 0, "ohne_betrag": 0}
    now = datetime.utcnow()
    for row in rows:
        if row.invoice_type != "storno":
            totals = bind.execute(sa.select(_items.c.billed_total).where(_items.c.invoice_id == row.id)).scalars().all()
            gross = brutto(row.invoice_type, row.rounding_rule, row.vat_rate, row.lump_sum_net, totals)
            if gross > 0:
                payment_id = bind.execute(payments.insert().values(
                    customer_id=row.customer_id, received_on=row.paid_date or row.invoice_date, amount=gross, note=NOTIZ,
                    origin="uebernommen", created_at=now, created_by_name="System").returning(payments.c.id)).scalar_one()
                bind.execute(allocations.insert().values(payment_id=payment_id, invoice_id=row.id, kind="zahlung",
                                                         amount=gross, created_at=now, created_by_name="System"))
                counts["zahlungen"] += 1
            else:
                counts["ohne_betrag"] += 1
        else:
            counts["storno_ohne_zahlung"] += 1
        bind.execute(_invoices.update().where(_invoices.c.id == row.id).values(status="versendet"))
    return counts


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('received_on', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('origin', sa.String(length=20), nullable=False),
        sa.Column('reverses_payment_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_name', sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['reverses_payment_id'], ['payments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reverses_payment_id', name='uq_payment_reverses'),
    )
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payments_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_reverses_payment_id'), ['reverses_payment_id'], unique=False)

    op.create_table(
        'payment_allocations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('reverses_allocation_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_name', sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.ForeignKeyConstraint(['reverses_allocation_id'], ['payment_allocations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reverses_allocation_id', name='uq_payment_allocation_reverses'),
    )
    with op.batch_alter_table('payment_allocations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_allocations_invoice_id'), ['invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_allocations_payment_id'), ['payment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_allocations_reverses_allocation_id'), ['reverses_allocation_id'],
                              unique=False)

    uebernehmen(op.get_bind())


def verloren(bind) -> list[str]:
    """Was der Rückweg verlöre: alles außer den übernommenen Zahlungen mit ihrer einen Zuordnung."""
    counts = {
        "erfasste Zahlungen": bind.execute(sa.text(
            "SELECT COUNT(*) FROM payments WHERE origin <> 'uebernommen' OR reverses_payment_id IS NOT NULL")).scalar(),
        "Gegenbuchungen oder weitere Zuordnungen": bind.execute(sa.text(
            "SELECT COUNT(*) FROM payment_allocations a JOIN payments p ON p.id = a.payment_id "
            "WHERE a.reverses_allocation_id IS NOT NULL OR a.kind <> 'zahlung' OR p.origin <> 'uebernommen' "
            "OR (SELECT COUNT(*) FROM payment_allocations b WHERE b.payment_id = a.payment_id) <> 1")).scalar(),
    }
    return [f"{n} {label}" for label, n in counts.items() if n]


def downgrade() -> None:
    bind = op.get_bind()
    lost = verloren(bind)
    if lost:
        raise RuntimeError(f"Downgrade verweigert: {', '.join(lost)} gingen verloren -- der Rückweg kennt nur "
                           "„bezahlt“ mit Datum.")
    bind.execute(sa.text(
        "UPDATE invoices SET status = 'bezahlt' WHERE status = 'versendet' AND (paid_date IS NOT NULL OR id IN "
        "(SELECT a.invoice_id FROM payment_allocations a JOIN payments p ON p.id = a.payment_id "
        "WHERE p.origin = 'uebernommen'))"))
    with op.batch_alter_table('payment_allocations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_allocations_reverses_allocation_id'))
        batch_op.drop_index(batch_op.f('ix_payment_allocations_payment_id'))
        batch_op.drop_index(batch_op.f('ix_payment_allocations_invoice_id'))
    op.drop_table('payment_allocations')
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payments_reverses_payment_id'))
        batch_op.drop_index(batch_op.f('ix_payments_customer_id'))
    op.drop_table('payments')
