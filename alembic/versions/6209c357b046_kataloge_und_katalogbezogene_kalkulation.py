"""Kataloge und katalogbezogene Kalkulation

Revision ID: 6209c357b046
Revises: 2befd7907eef
Create Date: 2026-09-02 19:01:09.498458

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6209c357b046'
down_revision = '2befd7907eef'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    existing_tables = sa_inspect(bind).get_table_names()
    if 'catalogs' not in existing_tables:
        op.create_table('catalogs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_import_catalog', sa.Boolean(), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )

    catalogs_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('catalogs')}
    with op.batch_alter_table('catalogs', schema=None) as batch_op:
        if 'ix_catalogs_archived' not in catalogs_indexes:
            batch_op.create_index(batch_op.f('ix_catalogs_archived'), ['archived'], unique=False)
        if 'ix_catalogs_is_import_catalog' not in catalogs_indexes:
            batch_op.create_index(batch_op.f('ix_catalogs_is_import_catalog'), ['is_import_catalog'], unique=False)

    cs_columns = {c['name'] for c in sa_inspect(bind).get_columns('calculation_settings')}
    if 'catalog_id' not in cs_columns:
        with op.batch_alter_table('calculation_settings', schema=None) as batch_op:
            batch_op.add_column(sa.Column('catalog_id', sa.Integer(), nullable=True))
            batch_op.create_unique_constraint('uq_calculation_settings_catalog', ['catalog_id'])
            batch_op.create_foreign_key('fk_calculation_settings_catalog_id', 'catalogs', ['catalog_id'], ['id'])

    s_columns = {c['name'] for c in sa_inspect(bind).get_columns('services')}
    if 'catalog_id' not in s_columns:
        with op.batch_alter_table('services', schema=None) as batch_op:
            batch_op.add_column(sa.Column('catalog_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f('ix_services_catalog_id'), ['catalog_id'], unique=False)
            batch_op.create_foreign_key('fk_services_catalog_id', 'catalogs', ['catalog_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.drop_constraint('fk_services_catalog_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_services_catalog_id'))
        batch_op.drop_column('catalog_id')

    with op.batch_alter_table('calculation_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_calculation_settings_catalog_id', type_='foreignkey')
        batch_op.drop_constraint('uq_calculation_settings_catalog', type_='unique')
        batch_op.drop_column('catalog_id')

    with op.batch_alter_table('catalogs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_catalogs_is_import_catalog'))
        batch_op.drop_index(batch_op.f('ix_catalogs_archived'))

    op.drop_table('catalogs')