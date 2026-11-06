"""einsatz_art -- die Art eines Einsatzes: Baustelle oder Kranvermietung (seit 1.9.240, Stufe 6, R3b, Punkt 2)

planning_slots.art, NOT NULL mit server_default 'baustelle' (Regel 1): jeder bestehende Einsatz ist einer auf der Baustelle (an einem Auftrag);
eine Kranvermietung gab es bis 1.9.239 nicht. downgrade(): die Spalte fällt weg -- eine Kranvermietung bleibt als Einsatz an ihrem Auftrag stehen
(ohne Kolonne, ihre Geräte und Bediener am Einsatz), nur ohne Art.

Revision ID: b5f1c7e2a948
Revises: a7d3e5f9c214
Create Date: 2026-11-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5f1c7e2a948'
down_revision = 'a7d3e5f9c214'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planning_slots") as batch:
        batch.add_column(sa.Column("art", sa.String(length=20), nullable=False, server_default="baustelle"))


def downgrade() -> None:
    with op.batch_alter_table("planning_slots") as batch:
        batch.drop_column("art")
