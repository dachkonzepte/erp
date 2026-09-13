"""Zahlungsbedingungen

Revision ID: 5581ab4df6d4
Revises: e057d15af828
Create Date: 2026-09-04 09:16:24.031601

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5581ab4df6d4'
down_revision = 'e057d15af828'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    existing_tables = sa_inspect(bind).get_table_names()
    if 'payment_terms' not in existing_tables:
        op.create_table('payment_terms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('days', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )

    pt_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('payment_terms')}
    with op.batch_alter_table('payment_terms', schema=None) as batch_op:
        if 'ix_payment_terms_archived' not in pt_indexes:
            batch_op.create_index(batch_op.f('ix_payment_terms_archived'), ['archived'], unique=False)
        if 'ix_payment_terms_is_default' not in pt_indexes:
            batch_op.create_index(batch_op.f('ix_payment_terms_is_default'), ['is_default'], unique=False)

    cp_columns = {c['name'] for c in sa_inspect(bind).get_columns('customer_profiles')}
    cp_fks = {fk['name'] for fk in sa_inspect(bind).get_foreign_keys('customer_profiles') if fk['name']}
    with op.batch_alter_table('customer_profiles', schema=None) as batch_op:
        if 'default_payment_term_id' not in cp_columns:
            batch_op.add_column(sa.Column('default_payment_term_id', sa.Integer(), nullable=True))
        if 'fk_customer_profiles_default_payment_term_id' not in cp_fks:
            batch_op.create_foreign_key('fk_customer_profiles_default_payment_term_id', 'payment_terms', ['default_payment_term_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('customer_profiles', schema=None) as batch_op:
        batch_op.drop_constraint('fk_customer_profiles_default_payment_term_id', type_='foreignkey')
        batch_op.drop_column('default_payment_term_id')

    with op.batch_alter_table('payment_terms', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_terms_is_default'))
        batch_op.drop_index(batch_op.f('ix_payment_terms_archived'))

    op.drop_table('payment_terms')