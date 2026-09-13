"""Steuerschluessel und Dokumentstruktur

Revision ID: bb175f455b64
Revises: 8c0bddc8321c
Create Date: 2026-09-04 11:39:22.212069

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bb175f455b64'
down_revision = '8c0bddc8321c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(bind)

    # --- tax_keys (neue Tabelle) ---
    if 'tax_keys' not in inspector.get_table_names():
        op.create_table('tax_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('vat_rate', sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column('notice_text', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
    tax_keys_indexes = {ix['name'] for ix in inspector.get_indexes('tax_keys')} if 'tax_keys' in inspector.get_table_names() else set()
    with op.batch_alter_table('tax_keys', schema=None) as batch_op:
        if 'ix_tax_keys_archived' not in tax_keys_indexes:
            batch_op.create_index(batch_op.f('ix_tax_keys_archived'), ['archived'], unique=False)
        if 'ix_tax_keys_is_default' not in tax_keys_indexes:
            batch_op.create_index(batch_op.f('ix_tax_keys_is_default'), ['is_default'], unique=False)

    # --- invoices ---
    inv_columns = {c['name'] for c in inspector.get_columns('invoices')}
    inv_indexes = {ix['name'] for ix in inspector.get_indexes('invoices')}
    inv_fks = {fk['name'] for fk in inspector.get_foreign_keys('invoices')}
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        if 'tax_key_id' not in inv_columns:
            batch_op.add_column(sa.Column('tax_key_id', sa.Integer(), nullable=True))
        if 'tax_notice_text' not in inv_columns:
            batch_op.add_column(sa.Column('tax_notice_text', sa.Text(), nullable=True))
        if 'outro_text_2' not in inv_columns:
            batch_op.add_column(sa.Column('outro_text_2', sa.Text(), nullable=True))
        if 'ix_invoices_tax_key_id' not in inv_indexes:
            batch_op.create_index(batch_op.f('ix_invoices_tax_key_id'), ['tax_key_id'], unique=False)
        if 'fk_invoices_tax_key_id' not in inv_fks:
            batch_op.create_foreign_key('fk_invoices_tax_key_id', 'tax_keys', ['tax_key_id'], ['id'])

    # --- orders ---
    ord_columns = {c['name'] for c in inspector.get_columns('orders')}
    ord_indexes = {ix['name'] for ix in inspector.get_indexes('orders')}
    ord_fks = {fk['name'] for fk in inspector.get_foreign_keys('orders')}
    with op.batch_alter_table('orders', schema=None) as batch_op:
        if 'tax_key_id' not in ord_columns:
            batch_op.add_column(sa.Column('tax_key_id', sa.Integer(), nullable=True))
        if 'outro_text_2' not in ord_columns:
            batch_op.add_column(sa.Column('outro_text_2', sa.Text(), nullable=True))
        if 'ix_orders_tax_key_id' not in ord_indexes:
            batch_op.create_index(batch_op.f('ix_orders_tax_key_id'), ['tax_key_id'], unique=False)
        if 'fk_orders_tax_key_id' not in ord_fks:
            batch_op.create_foreign_key('fk_orders_tax_key_id', 'tax_keys', ['tax_key_id'], ['id'])

    # --- quotes ---
    quote_columns = {c['name'] for c in inspector.get_columns('quotes')}
    quote_indexes = {ix['name'] for ix in inspector.get_indexes('quotes')}
    quote_fks = {fk['name'] for fk in inspector.get_foreign_keys('quotes')}
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        if 'tax_key_id' not in quote_columns:
            batch_op.add_column(sa.Column('tax_key_id', sa.Integer(), nullable=True))
        if 'outro_text_2' not in quote_columns:
            batch_op.add_column(sa.Column('outro_text_2', sa.Text(), nullable=True))
        if 'ix_quotes_tax_key_id' not in quote_indexes:
            batch_op.create_index(batch_op.f('ix_quotes_tax_key_id'), ['tax_key_id'], unique=False)
        if 'fk_quotes_tax_key_id' not in quote_fks:
            batch_op.create_foreign_key('fk_quotes_tax_key_id', 'tax_keys', ['tax_key_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_quotes_tax_key_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_quotes_tax_key_id'))
        batch_op.drop_column('outro_text_2')
        batch_op.drop_column('tax_key_id')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_tax_key_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_orders_tax_key_id'))
        batch_op.drop_column('outro_text_2')
        batch_op.drop_column('tax_key_id')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_constraint('fk_invoices_tax_key_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_invoices_tax_key_id'))
        batch_op.drop_column('outro_text_2')
        batch_op.drop_column('tax_notice_text')
        batch_op.drop_column('tax_key_id')

    with op.batch_alter_table('tax_keys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tax_keys_is_default'))
        batch_op.drop_index(batch_op.f('ix_tax_keys_archived'))

    op.drop_table('tax_keys')