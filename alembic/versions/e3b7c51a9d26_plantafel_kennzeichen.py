"""plantafel_kennzeichen -- das Kennzeichen „Plantafel“ am Mitarbeiter (seit 1.9.253, Stufe 6, R4b, Punkt 1)

employee_planning_settings.plantafel (VARCHAR(20), NOT NULL, Vorgabe „einplanbar“, Index) ersetzt das Häkchen show_on_planning_board:
einplanbar | bauleitung | nicht_zeigen. Bestehende Zeilen: Häkchen gesetzt -> einplanbar, nicht gesetzt -> nicht_zeigen (wer heute nicht in der Plantafel
steht, steht auch danach nicht dort); niemand wird von selbst „Bauleitung“. Mitarbeiter ohne Zeile behalten die Vorgabe aus Gruppe und Funktion
(app/employees.py::_default_plantafel()), die Migration legt keine Zeilen an. Danach fällt die Spalte show_on_planning_board samt Index weg.

downgrade(): das Häkchen zurück -- nicht_zeigen -> nicht gesetzt, einplanbar und bauleitung -> gesetzt (die Bauleitung gab es vorher nicht, sie stand
in der Plantafel); Index wie in der Baseline, dann die Spalte plantafel weg.

Revision ID: e3b7c51a9d26
Revises: c9d2e6a3f417
Create Date: 2026-11-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3b7c51a9d26'
down_revision = 'c9d2e6a3f417'
branch_labels = None
depends_on = None

TABELLE = sa.table("employee_planning_settings", sa.column("show_on_planning_board", sa.Boolean()), sa.column("plantafel", sa.String(20)))


def upgrade() -> None:
    with op.batch_alter_table("employee_planning_settings") as batch:
        batch.add_column(sa.Column("plantafel", sa.String(length=20), nullable=False, server_default="einplanbar"))
    op.execute(TABELLE.update().where(TABELLE.c.show_on_planning_board == sa.false()).values(plantafel="nicht_zeigen"))
    with op.batch_alter_table("employee_planning_settings") as batch:
        batch.create_index(batch.f("ix_employee_planning_settings_plantafel"), ["plantafel"], unique=False)
        batch.drop_index(batch.f("ix_employee_planning_settings_show_on_planning_board"))
        batch.drop_column("show_on_planning_board")


def downgrade() -> None:
    with op.batch_alter_table("employee_planning_settings") as batch:
        batch.add_column(sa.Column("show_on_planning_board", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute(TABELLE.update().where(TABELLE.c.plantafel == "nicht_zeigen").values(show_on_planning_board=False))
    with op.batch_alter_table("employee_planning_settings") as batch:
        batch.alter_column("show_on_planning_board", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)  # wie in der Baseline
        batch.create_index(batch.f("ix_employee_planning_settings_show_on_planning_board"), ["show_on_planning_board"], unique=False)
        batch.drop_index(batch.f("ix_employee_planning_settings_plantafel"))
        batch.drop_column("plantafel")
