"""geraetetypen -- die Auswahlliste „Ressourcentypen · Fuhrpark & Maschinen“ heißt „Gerätetypen · Fuhrpark & Maschinen“ (seit 1.9.301)

Nachrunde der Geräte-Runde, Punkt 1: „Ressource“ heißt in der Oberfläche überall „Gerät“. Die Bezeichnung einer Auswahlliste steht in der Datenbank
(setting_option_groups.label, angelegt beim ersten Start aus app/option_settings.py) und lässt sich in den Einstellungen nicht ändern -- die Migration
stellt sie um, nur wo noch genau die bisherige steht. Keine Schemaänderung.

downgrade(): zurück, nur wo genau die neue steht.

Revision ID: c990522c34ff
Revises: c3e9f1a7b285
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c990522c34ff'
down_revision = 'c3e9f1a7b285'
branch_labels = None
depends_on = None

BISHER = "Ressourcentypen · Fuhrpark & Maschinen"
NEU = "Gerätetypen · Fuhrpark & Maschinen"


def umbenennen(bind, von: str, nach: str) -> int:
    """Anzahl der umgestellten Zeilen (0 oder 1)."""
    return bind.execute(sa.text("UPDATE setting_option_groups SET label = :nach WHERE group_key = 'resource_types' AND label = :von"),
                        {"von": von, "nach": nach}).rowcount


def upgrade() -> None:
    umbenennen(op.get_bind(), BISHER, NEU)


def downgrade() -> None:
    umbenennen(op.get_bind(), NEU, BISHER)
