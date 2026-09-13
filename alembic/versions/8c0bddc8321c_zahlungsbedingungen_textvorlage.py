"""Zahlungsbedingungen Textvorlage

Revision ID: 8c0bddc8321c
Revises: 369f94b5d5d3
Create Date: 2026-09-04 10:45:40.998187

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c0bddc8321c'
down_revision = '369f94b5d5d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    inv_columns = {c['name'] for c in sa_inspect(bind).get_columns('invoices')}
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        if 'payment_terms_text_template' not in inv_columns:
            batch_op.add_column(sa.Column('payment_terms_text_template', sa.Text(), nullable=True))

    pt_columns = {c['name'] for c in sa_inspect(bind).get_columns('payment_terms')}
    with op.batch_alter_table('payment_terms', schema=None) as batch_op:
        if 'text_template' not in pt_columns:
            batch_op.add_column(sa.Column('text_template', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('payment_terms', schema=None) as batch_op:
        batch_op.drop_column('text_template')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('payment_terms_text_template')