"""nur_geraetetypen -- die Auswahlliste „Gerätetypen · Fuhrpark & Maschinen“ heißt nur „Gerätetypen“ (seit 1.9.306)

Lohn L2a, Vorweg (Frage 2 der Nachrunde der Geräte-Runde): ohne den Zusatz „· Fuhrpark & Maschinen“. Die Bezeichnung einer Auswahlliste steht in der
Datenbank (setting_option_groups.label, angelegt beim ersten Start aus app/option_settings.py) und lässt sich in den Einstellungen nicht ändern -- die
Migration stellt sie um, nur wo noch genau die bisherige steht (wie c990522c34ff). Keine Schemaänderung.

downgrade(): zurück, nur wo genau die neue steht.

Revision ID: 84ee228b331e
Revises: c990522c34ff
Create Date: 2026-11-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '84ee228b331e'
down_revision = 'c990522c34ff'
branch_labels = None
depends_on = None

BISHER = "Gerätetypen · Fuhrpark & Maschinen"
NEU = "Gerätetypen"


def umbenennen(bind, von: str, nach: str) -> int:
    """Anzahl der umgestellten Zeilen (0 oder 1)."""
    return bind.execute(sa.text("UPDATE setting_option_groups SET label = :nach WHERE group_key = 'resource_types' AND label = :von"),
                        {"von": von, "nach": nach}).rowcount


def upgrade() -> None:
    umbenennen(op.get_bind(), BISHER, NEU)


def downgrade() -> None:
    umbenennen(op.get_bind(), NEU, BISHER)
