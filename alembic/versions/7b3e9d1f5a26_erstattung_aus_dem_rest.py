"""erstattung_aus_dem_rest -- Guthaben des Kunden: Erstattung auch aus dem nicht zugeordneten Rest einer Zahlung (seit 1.8.93,
Nacharbeit R4c Punkt 3)

- payment_refund_sources: Teil eines Zahlungsausgangs (Erstattung), der den nicht zugeordneten Rest einer Zahlung desselben Kunden
  erstattet (refund_payment_id = der Zahlungsausgang, source_payment_id = die Zahlung, amount positiv). Höchstens eine Zeile je
  Zahlungsausgang und Zahlung (UNIQUE). Unveränderlich; gilt, solange der Zahlungsausgang nicht zurückgenommen ist.

Ändert keine vorhandenen Daten.

downgrade(): verweigert, solange eine Erstattung aus einem Rest besteht (sie ginge verloren, der Rest der Zahlung stünde wieder offen).

Revision ID: 7b3e9d1f5a26
Revises: 4e7a9c2b6d58
Create Date: 2026-10-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b3e9d1f5a26'
down_revision = '4e7a9c2b6d58'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payment_refund_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('refund_payment_id', sa.Integer(), nullable=False),
        sa.Column('source_payment_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_name', sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(['refund_payment_id'], ['payments.id'], ),
        sa.ForeignKeyConstraint(['source_payment_id'], ['payments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refund_payment_id', 'source_payment_id', name='uq_payment_refund_source'),
    )
    with op.batch_alter_table('payment_refund_sources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_refund_sources_refund_payment_id'), ['refund_payment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_refund_sources_source_payment_id'), ['source_payment_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    found = bind.execute(sa.text("SELECT COUNT(*) FROM payment_refund_sources")).scalar()
    if found:
        raise RuntimeError(f"Downgrade verweigert: {found} Erstattungen aus dem Rest einer Zahlung -- sie gingen verloren.")
    with op.batch_alter_table('payment_refund_sources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_refund_sources_source_payment_id'))
        batch_op.drop_index(batch_op.f('ix_payment_refund_sources_refund_payment_id'))
    op.drop_table('payment_refund_sources')
