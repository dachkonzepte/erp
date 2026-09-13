"""Mehrseiten-Unterstuetzung: Hintergrund-Wiederholung

Revision ID: ef7b95affc19
Revises: fff4d8ae8433
Create Date: 2026-09-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef7b95affc19'
down_revision = 'fff4d8ae8433'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Von Hand defensiv gemacht: server_default='1' ergänzt, da SQLite beim
    # Hinzufügen einer NOT-NULL-Spalte zu einer bereits bestehenden Tabelle
    # zwingend einen Datenbank-seitigen Vorgabewert braucht (der reine
    # Python/ORM-seitige default=True im Modell reicht dafür nicht aus).
    with op.batch_alter_table('document_layout_backgrounds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('repeat_on_every_page', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    with op.batch_alter_table('document_layout_backgrounds', schema=None) as batch_op:
        batch_op.drop_column('repeat_on_every_page')
