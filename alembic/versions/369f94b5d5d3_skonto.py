"""Skonto

Revision ID: 369f94b5d5d3
Revises: 5581ab4df6d4
Create Date: 2026-09-04 10:24:40.435821

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '369f94b5d5d3'
down_revision = '5581ab4df6d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    inv_columns = {c['name'] for c in sa_inspect(bind).get_columns('invoices')}
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        if 'skonto_percent' not in inv_columns:
            batch_op.add_column(sa.Column('skonto_percent', sa.Numeric(precision=5, scale=2), nullable=True))
        if 'skonto_days' not in inv_columns:
            batch_op.add_column(sa.Column('skonto_days', sa.Integer(), nullable=True))

    pt_columns = {c['name'] for c in sa_inspect(bind).get_columns('payment_terms')}
    with op.batch_alter_table('payment_terms', schema=None) as batch_op:
        if 'skonto_percent' not in pt_columns:
            batch_op.add_column(sa.Column('skonto_percent', sa.Numeric(precision=5, scale=2), nullable=True))
        if 'skonto_days' not in pt_columns:
            batch_op.add_column(sa.Column('skonto_days', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('payment_terms', schema=None) as batch_op:
        batch_op.drop_column('skonto_days')
        batch_op.drop_column('skonto_percent')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('skonto_days')
        batch_op.drop_column('skonto_percent')