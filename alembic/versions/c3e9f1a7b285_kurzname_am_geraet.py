"""kurzname_am_geraet -- ein kurzer Name für das Gerät auf der Plantafel (seit 1.9.280, Stufe 6, R5c, Punkt 2)

operational_resources.kurzname (VARCHAR(30), leer erlaubt): was der Chip in der Ansicht „Aufträge“ zeigt (leer = der Name). Keine Datenübernahme -- jedes
bestehende Gerät bleibt ohne Kurznamen und zeigt weiter seinen Namen.
downgrade(): die Spalte fällt weg (die Fassung davor kennt keinen Kurznamen; eingetragene Kurznamen gehen dabei verloren).

Revision ID: c3e9f1a7b285
Revises: b6e4d2a9c731
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3e9f1a7b285'
down_revision = 'b6e4d2a9c731'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("operational_resources") as batch:
        batch.add_column(sa.Column("kurzname", sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("operational_resources") as batch:
        batch.drop_column("kurzname")
