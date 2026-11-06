"""besetzung_je_einsatz -- die Personen stehen am Einsatz (seit 1.9.233, Stufe 6, R3a, Punkt 2)

Neu: Tabelle planning_slot_employees (Einsatz, Person; je Einsatz eine Person einmal). planning_slots.team_assignment_id darf leer sein
(„ohne Kolonne“, Personen einzeln gewählt).

Daten: je Einsatz die Personen, die bis 1.9.232 an ihm arbeiteten -- der Schnappschuss seiner Kolonnen-Zuweisung an der Arbeitsvorbereitung
(work_preparation_team_employees, in seiner Reihenfolge) und danach die Einzelzuweisungen derselben Arbeitsvorbereitung (work_preparation_employees:
sie sahen bis 1.9.232 jeden Einsatz der Arbeitsvorbereitung auf „Heute“, Befund Stufe 6, B5). Jede Person einmal je Einsatz. Übernommen wird jede
Zeile, auch eine inaktive Person: gefiltert wird beim Lesen wie bisher (aktiv, sichtbar auf der Plantafel).

downgrade(): bricht ab, ohne etwas zu ändern, solange ein Einsatz ohne Kolonne besteht (die Fassung davor kennt keinen); sonst fällt die Tabelle
weg und team_assignment_id ist wieder Pflicht. Die Besetzung der Fassung davor ist der Schnappschuss an der Arbeitsvorbereitung -- er blieb unverändert.

Revision ID: e4b1c9d27a35
Revises: b6d14e8a2f73
Create Date: 2026-11-06

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4b1c9d27a35'
down_revision = 'b6d14e8a2f73'
branch_labels = None
depends_on = None


def besetzungen(bind) -> list[tuple[int, int]]:
    """(Einsatz, Person) in der Reihenfolge, in der sie eingetragen werden: je Einsatz erst die Kolonne, dann die Einzelzuweisungen der AV."""
    kolonne = bind.execute(sa.text(
        "SELECT s.id, e.employee_id FROM planning_slots s JOIN work_preparation_team_employees e ON e.assignment_id = s.team_assignment_id "
        "ORDER BY s.id, e.id")).all()
    einzeln = bind.execute(sa.text(
        "SELECT s.id, w.employee_id FROM planning_slots s JOIN work_preparation_employees w ON w.preparation_id = s.preparation_id "
        "ORDER BY s.id, w.id")).all()
    je: dict[int, list[int]] = {}
    for slot_id, employee_id in [*kolonne, *einzeln]:
        liste = je.setdefault(slot_id, [])
        if employee_id not in liste:
            liste.append(employee_id)
    return [(slot_id, employee_id) for slot_id in sorted(je) for employee_id in je[slot_id]]


def upgrade() -> None:
    op.create_table(
        "planning_slot_employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["slot_id"], ["planning_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "employee_id", name="uq_planning_slot_employee"),
    )
    op.create_index(op.f("ix_planning_slot_employees_slot_id"), "planning_slot_employees", ["slot_id"], unique=False)
    op.create_index(op.f("ix_planning_slot_employees_employee_id"), "planning_slot_employees", ["employee_id"], unique=False)
    with op.batch_alter_table("planning_slots", schema=None) as batch_op:
        batch_op.alter_column("team_assignment_id", existing_type=sa.Integer(), nullable=True)
    bind = op.get_bind()
    jetzt = datetime.utcnow()
    for slot_id, employee_id in besetzungen(bind):
        bind.execute(sa.text("INSERT INTO planning_slot_employees (slot_id, employee_id, created_at) VALUES (:s, :e, :j)"),
                     {"s": slot_id, "e": employee_id, "j": jetzt})


def downgrade() -> None:
    bind = op.get_bind()
    ohne = bind.execute(sa.text("SELECT count(*) FROM planning_slots WHERE team_assignment_id IS NULL")).scalar()
    if ohne:
        raise RuntimeError(f"Downgrade abgebrochen, nichts geändert: {ohne} Einsatz/Einsätze ohne Kolonne -- die Fassung davor kennt keinen. "
                           "Bitte zuerst eine Kolonne zuweisen oder die Einsätze löschen.")
    op.drop_index(op.f("ix_planning_slot_employees_employee_id"), table_name="planning_slot_employees")
    op.drop_index(op.f("ix_planning_slot_employees_slot_id"), table_name="planning_slot_employees")
    op.drop_table("planning_slot_employees")
    with op.batch_alter_table("planning_slots", schema=None) as batch_op:
        batch_op.alter_column("team_assignment_id", existing_type=sa.Integer(), nullable=False)
