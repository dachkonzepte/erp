"""einsatz_status_vorlaeufig_fest -- der Status eines Einsatzes ist vorläufig oder fest (seit 1.9.235, Stufe 6, R3a, Punkt 4)

planning_slots.status war bis 1.9.234 freier Text ohne Wirkung (geplant, bestaetigt, in_ausfuehrung, pausiert, abgeschlossen; Befund Stufe 6, 3.3).
Vorgabe (Zeichnung Stufe 6, „Status“): „geplant“ wird vorläufig, alles andere fest -- auch ein leerer oder unbekannter Wert.

downgrade(): vorlaeufig -> geplant, fest -> bestaetigt. Die übrigen Werte von vorher (in_ausfuehrung, pausiert, abgeschlossen, Freitext) kommen nicht
zurück; sie hatten keine Wirkung.

Revision ID: a7d3e5f9c214
Revises: f2c8d4a61e93
Create Date: 2026-11-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7d3e5f9c214'
down_revision = 'f2c8d4a61e93'
branch_labels = None
depends_on = None


def neu(alt: str | None) -> str:
    """Der Status nach der Migration."""
    return "vorlaeufig" if alt == "geplant" else "fest"


def upgrade() -> None:
    op.execute(sa.text("UPDATE planning_slots SET status = CASE WHEN status = 'geplant' THEN 'vorlaeufig' ELSE 'fest' END"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE planning_slots SET status = CASE WHEN status = 'vorlaeufig' THEN 'geplant' ELSE 'bestaetigt' END"))
