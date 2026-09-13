"""Rechnungswesen

Revision ID: e057d15af828
Revises: d06425e23f3c
Create Date: 2026-09-04 08:15:16.219118

Nachträglich befüllt (siehe CLAUDE.md "PostgreSQL-Umstieg: Migrationskette repariert") --
diese Migration wurde ursprünglich leer generiert, weil Base.metadata.create_all() (der
Sicherheitsnetz-Aufruf in app/main.py) invoices/invoice_items beim App-Start bereits direkt aus
den Modellen angelegt hatte, bevor `alembic revision --autogenerate` lief. Autogenerate fand
dadurch "keinen Unterschied" und erzeugte eine leere Hülle -- unter SQLite folgenlos (der
Sicherheitsnetz-Aufruf holt es beim nächsten Start ohnehin nach), aber eine leere Datenbank, die
NUR über `alembic upgrade head` aufgebaut wird (z. B. eine frische PostgreSQL-Instanz), bekommt
diese beiden Tabellen dadurch nie -- die nächste Migration (369f94b5d5d3, Skonto) scheitert dort
beim Versuch, ihre Spalten zu reflektieren.

Der Spaltenumfang bildet bewusst den STAND VON DAMALS ab, nicht das heutige Modell: acht Spalten
auf invoices werden von vier späteren Migrationen selbst hinzugefügt (tax_key_id/tax_notice_text/
outro_text_2 in bb175f455b64, email_sent_at/email_sent_to in 3eb9f52b38ab,
payment_terms_text_template in 8c0bddc8321c, skonto_percent/skonto_days in 369f94b5d5d3 -- exakt
die im Modell selbst mit "seit 1.0.4x" datierten Felder) und würden sonst mit "Spalte existiert
bereits" scheitern. invoice_items bekommt dagegen das volle heutige Schema unverändert -- keine
spätere Migration fasst diese Tabelle je an (per Volltextsuche über alle 55 Migrationsdateien
bestätigt).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e057d15af828'
down_revision = 'd06425e23f3c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_number', sa.String(length=50), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('invoice_type', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('paid_date', sa.Date(), nullable=True),
        sa.Column('storno_of_invoice_id', sa.Integer(), nullable=True),
        sa.Column('customer_name', sa.String(length=255), nullable=False),
        sa.Column('customer_number', sa.String(length=50), nullable=True),
        sa.Column('customer_address', sa.Text(), nullable=True),
        sa.Column('property_name', sa.String(length=255), nullable=True),
        sa.Column('property_address', sa.Text(), nullable=True),
        sa.Column('vat_rate', sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column('lump_sum_net', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('progress_description', sa.Text(), nullable=True),
        sa.Column('intro_text', sa.Text(), nullable=True),
        sa.Column('outro_text', sa.Text(), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('caseworker_employee_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['storno_of_invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['caseworker_employee_id'], ['employees.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invoices_invoice_number'), ['invoice_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoices_order_id'), ['order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoices_invoice_type'), ['invoice_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoices_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoices_storno_of_invoice_id'), ['storno_of_invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoices_caseworker_employee_id'), ['caseworker_employee_id'], unique=False)

    op.create_table(
        'invoice_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('source_order_item_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('position_number', sa.String(length=50), nullable=False),
        sa.Column('gaeb_oz', sa.String(length=100), nullable=True),
        sa.Column('short_text', sa.Text(), nullable=False),
        sa.Column('long_text', sa.Text(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('soll_quantity', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('ist_quantity', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('billed_quantity', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('billed_total', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['source_order_item_id'], ['order_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('invoice_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invoice_items_invoice_id'), ['invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoice_items_source_order_item_id'), ['source_order_item_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('invoice_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invoice_items_source_order_item_id'))
        batch_op.drop_index(batch_op.f('ix_invoice_items_invoice_id'))
    op.drop_table('invoice_items')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invoices_caseworker_employee_id'))
        batch_op.drop_index(batch_op.f('ix_invoices_storno_of_invoice_id'))
        batch_op.drop_index(batch_op.f('ix_invoices_status'))
        batch_op.drop_index(batch_op.f('ix_invoices_invoice_type'))
        batch_op.drop_index(batch_op.f('ix_invoices_order_id'))
        batch_op.drop_index(batch_op.f('ix_invoices_invoice_number'))
    op.drop_table('invoices')
