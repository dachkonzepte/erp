"""geraete_je_einsatz -- die Geräte stehen am Einsatz, für alle oder einzelne Tage (seit 1.9.234, Stufe 6, R3a, Punkt 3)

Neu: Tabelle planning_slot_resources (Einsatz, Gerät = operational_resources, tage: JSON-Liste einzelner Tage oder leer = alle Tage; je Einsatz ein
Gerät einmal).

Daten: je Einsatz die Geräte, die bis 1.9.233 an ihm hingen -- der Schnappschuss seiner Kolonnen-Zuweisung an der Arbeitsvorbereitung
(work_preparation_team_resources, in seiner Reihenfolge), für alle Tage. Ein Einsatz ohne Kolonne (seit 1.9.233) hatte keine Geräte.

downgrade(): die Tabelle fällt weg; die Geräte der Fassung davor sind der Schnappschuss an der Arbeitsvorbereitung -- er blieb unverändert. Was nach dem
Einspielen an Geräten je Einsatz gewählt wurde (auch einzelne Tage), geht dabei verloren.

Revision ID: f2c8d4a61e93
Revises: e4b1c9d27a35
Create Date: 2026-11-06

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c8d4a61e93'
down_revision = 'e4b1c9d27a35'
branch_labels = None
depends_on = None


def geraete(bind) -> list[tuple[int, int]]:
    """(Einsatz, Gerät) in der Reihenfolge des Schnappschusses, jedes Gerät einmal je Einsatz."""
    zeilen = bind.execute(sa.text(
        "SELECT s.id, r.resource_id FROM planning_slots s JOIN work_preparation_team_resources r ON r.assignment_id = s.team_assignment_id "
        "WHERE r.resource_id IS NOT NULL ORDER BY s.id, r.id")).all()
    ergebnis, gesehen = [], set()
    for slot_id, resource_id in zeilen:
        if (slot_id, resource_id) not in gesehen:
            gesehen.add((slot_id, resource_id))
            ergebnis.append((slot_id, resource_id))
    return ergebnis


def upgrade() -> None:
    op.create_table(
        "planning_slot_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("tage", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["slot_id"], ["planning_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["operational_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "resource_id", name="uq_planning_slot_resource"),
    )
    op.create_index(op.f("ix_planning_slot_resources_slot_id"), "planning_slot_resources", ["slot_id"], unique=False)
    op.create_index(op.f("ix_planning_slot_resources_resource_id"), "planning_slot_resources", ["resource_id"], unique=False)
    bind = op.get_bind()
    jetzt = datetime.utcnow()
    for slot_id, resource_id in geraete(bind):
        bind.execute(sa.text("INSERT INTO planning_slot_resources (slot_id, resource_id, tage, created_at) VALUES (:s, :r, NULL, :j)"),
                     {"s": slot_id, "r": resource_id, "j": jetzt})


def downgrade() -> None:
    op.drop_index(op.f("ix_planning_slot_resources_resource_id"), table_name="planning_slot_resources")
    op.drop_index(op.f("ix_planning_slot_resources_slot_id"), table_name="planning_slot_resources")
    op.drop_table("planning_slot_resources")
