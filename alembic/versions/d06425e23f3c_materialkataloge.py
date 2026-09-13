"""Materialkataloge

Revision ID: d06425e23f3c
Revises: 806513205b5c
Create Date: 2026-09-03 17:36:25.664920

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd06425e23f3c'
down_revision = '806513205b5c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    existing_tables = sa_inspect(bind).get_table_names()
    if 'material_groups' not in existing_tables:
        op.create_table('material_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_import_catalog', sa.Boolean(), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )

    mg_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('material_groups')}
    with op.batch_alter_table('material_groups', schema=None) as batch_op:
        if 'ix_material_groups_archived' not in mg_indexes:
            batch_op.create_index(batch_op.f('ix_material_groups_archived'), ['archived'], unique=False)
        if 'ix_material_groups_is_import_catalog' not in mg_indexes:
            batch_op.create_index(batch_op.f('ix_material_groups_is_import_catalog'), ['is_import_catalog'], unique=False)

    m_columns = {c['name'] for c in sa_inspect(bind).get_columns('materials')}
    m_indexes = {ix['name'] for ix in sa_inspect(bind).get_indexes('materials')}
    m_fks = {fk['name'] for fk in sa_inspect(bind).get_foreign_keys('materials') if fk['name']}
    with op.batch_alter_table('materials', schema=None) as batch_op:
        if 'catalog_id' not in m_columns:
            batch_op.add_column(sa.Column('catalog_id', sa.Integer(), nullable=True))
        if 'ix_materials_catalog_id' not in m_indexes:
            batch_op.create_index(batch_op.f('ix_materials_catalog_id'), ['catalog_id'], unique=False)
        if 'fk_materials_catalog_id' not in m_fks:
            batch_op.create_foreign_key('fk_materials_catalog_id', 'material_groups', ['catalog_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('materials', schema=None) as batch_op:
        batch_op.drop_constraint('fk_materials_catalog_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_materials_catalog_id'))
        batch_op.drop_column('catalog_id')

    with op.batch_alter_table('material_groups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_material_groups_is_import_catalog'))
        batch_op.drop_index(batch_op.f('ix_material_groups_archived'))

    op.drop_table('material_groups')