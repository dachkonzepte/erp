"""kran_termine -- Termine der Einsätze im Kalender des Krans (seit 1.9.241, Stufe 6, R3b, Punkt 3)

calendar_events.planning_slot_id (nullable, Fremdschlüssel auf planning_slots mit ON DELETE SET NULL, Index): ein Termin, der zu einem Einsatz gehört
(app/kran_kalender.py) -- für ihn ist die Plantafel führend. Bestehende Termine bleiben ohne Einsatz (Termine am Kran, wie sie in Outlook entstanden);
die Termine der laufenden und künftigen Einsätze legt der nächste Abgleich des Geräte-Postfachs an (nachziehen()).

downgrade(): erst die Termine der Einsätze -- sie gibt es nur, weil die Plantafel sie angelegt hat; in Outlook bleiben sie stehen, bis jemand sie dort
löscht (ein downgrade erreicht Outlook nicht) --, dann die Spalte.

Revision ID: c9d2e6a3f417
Revises: b5f1c7e2a948
Create Date: 2026-11-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d2e6a3f417'
down_revision = 'b5f1c7e2a948'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.add_column(sa.Column("planning_slot_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_calendar_events_planning_slot_id_planning_slots", "planning_slots", ["planning_slot_id"], ["id"],
                                 ondelete="SET NULL")
        batch.create_index(batch.f("ix_calendar_events_planning_slot_id"), ["planning_slot_id"], unique=False)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM calendar_events WHERE planning_slot_id IS NOT NULL"))
    with op.batch_alter_table("calendar_events") as batch:
        batch.drop_index(batch.f("ix_calendar_events_planning_slot_id"))
        batch.drop_constraint("fk_calendar_events_planning_slot_id_planning_slots", type_="foreignkey")
        batch.drop_column("planning_slot_id")
