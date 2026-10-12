"""schlussrechnung_abzuege -- Abzüge der Schlussrechnung als Endrechnung (seit 1.8.85, R4b Punkt 2)

- invoice_deductions: je festgeschriebener Schlussrechnung die Abschlagsrechnungen und Rechnungen aus Aufwand, die sie abzieht
  (beim Festschreiben eingefroren, unveränderlich). Bestand: keine Zeilen -- eine Schlussrechnung von vor 1.8.85 trägt den Rest
  über die Menge in ihren Positionen und rechnet ohne Abzüge wie bisher.

Ändert keine vorhandenen Daten.

downgrade(): verweigert, solange Abzüge bestehen -- ohne sie lautete eine Endrechnung über die volle Gesamtleistung.

Revision ID: 8c2e5a7d4f19
Revises: 3b8f1d6c9e24
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c2e5a7d4f19'
down_revision = '3b8f1d6c9e24'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'invoice_deductions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('deducted_invoice_id', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['deducted_invoice_id'], ['invoices.id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_id', 'deducted_invoice_id', name='uq_invoice_deduction'),
    )
    with op.batch_alter_table('invoice_deductions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invoice_deductions_deducted_invoice_id'), ['deducted_invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoice_deductions_invoice_id'), ['invoice_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    n = bind.execute(sa.text("SELECT COUNT(*) FROM invoice_deductions")).scalar()
    if n:
        raise RuntimeError(f"Downgrade verweigert: {n} Abzüge festgeschriebener Schlussrechnungen -- ohne sie lautete eine "
                           "Endrechnung über die volle Gesamtleistung.")
    with op.batch_alter_table('invoice_deductions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invoice_deductions_invoice_id'))
        batch_op.drop_index(batch_op.f('ix_invoice_deductions_deducted_invoice_id'))
    op.drop_table('invoice_deductions')
