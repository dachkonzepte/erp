"""Materialkatalog

Revision ID: 806513205b5c
Revises: 6209c357b046
Create Date: 2026-09-03 15:33:10.807833

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '806513205b5c'
down_revision = '6209c357b046'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    existing_tables = sa_inspect(bind).get_table_names()
    if 'materials' not in existing_tables:
        op.create_table('materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('article_number', sa.String(length=100), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('purchase_price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('price_basis', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )

    materials_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('materials')}
    with op.batch_alter_table('materials', schema=None) as batch_op:
        if 'ix_materials_article_number' not in materials_indexes:
            batch_op.create_index(batch_op.f('ix_materials_article_number'), ['article_number'], unique=False)
        if 'ix_materials_source' not in materials_indexes:
            batch_op.create_index(batch_op.f('ix_materials_source'), ['source'], unique=False)

    cs_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('calculation_settings')}
    cs_constraints = {c['name'] for c in sa_inspect(bind).get_unique_constraints('calculation_settings')}
    cs_fks = {fk['name'] for fk in sa_inspect(bind).get_foreign_keys('calculation_settings') if fk['name']}
    with op.batch_alter_table('calculation_settings', schema=None) as batch_op:
        if 'uq_calculation_settings_catalog' in cs_indexes and 'uq_calculation_settings_catalog' not in cs_constraints:
            batch_op.drop_index(batch_op.f('uq_calculation_settings_catalog'))
        if 'uq_calculation_settings_catalog' not in cs_constraints:
            batch_op.create_unique_constraint('uq_calculation_settings_catalog', ['catalog_id'])
        if 'fk_calculation_settings_catalog_id' not in cs_fks:
            batch_op.create_foreign_key('fk_calculation_settings_catalog_id', 'catalogs', ['catalog_id'], ['id'])

    sm_columns = {c['name'] for c in sa_inspect(bind).get_columns('service_materials')}
    sm_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('service_materials')}
    sm_fks = {fk['name'] for fk in sa_inspect(bind).get_foreign_keys('service_materials') if fk['name']}
    with op.batch_alter_table('service_materials', schema=None) as batch_op:
        if 'material_id' not in sm_columns:
            batch_op.add_column(sa.Column('material_id', sa.Integer(), nullable=True))
        if 'ix_service_materials_material_id' not in sm_indexes:
            batch_op.create_index(batch_op.f('ix_service_materials_material_id'), ['material_id'], unique=False)
        if 'fk_service_materials_material_id' not in sm_fks:
            batch_op.create_foreign_key('fk_service_materials_material_id', 'materials', ['material_id'], ['id'])

    s_columns = {c['name'] for c in sa_inspect(bind).get_columns('services')}
    s_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('services')}
    s_fks = {fk['name'] for fk in sa_inspect(bind).get_foreign_keys('services') if fk['name']}
    with op.batch_alter_table('services', schema=None) as batch_op:
        if 'service_type' not in s_columns:
            batch_op.add_column(sa.Column('service_type', sa.String(length=20), nullable=True))
        if 'ix_services_service_type' not in s_indexes:
            batch_op.create_index(batch_op.f('ix_services_service_type'), ['service_type'], unique=False)
        if 'fk_services_catalog_id' not in s_fks:
            batch_op.create_foreign_key('fk_services_catalog_id', 'catalogs', ['catalog_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.drop_constraint('fk_services_catalog_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_services_service_type'))
        batch_op.drop_column('service_type')

    with op.batch_alter_table('service_materials', schema=None) as batch_op:
        batch_op.drop_constraint('fk_service_materials_material_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_service_materials_material_id'))
        batch_op.drop_column('material_id')

    with op.batch_alter_table('calculation_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_calculation_settings_catalog_id', type_='foreignkey')
        batch_op.drop_constraint('uq_calculation_settings_catalog', type_='unique')
        batch_op.create_index(batch_op.f('uq_calculation_settings_catalog'), ['catalog_id'], unique=1)

    with op.batch_alter_table('materials', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_materials_source'))
        batch_op.drop_index(batch_op.f('ix_materials_article_number'))

    op.drop_table('materials')