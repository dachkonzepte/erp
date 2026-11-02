"""schlechtwetter_als_ausfalltag -- Schlechtwetter als Abwesenheit, Vorarbeiter (seit 1.9.170, Lohn L1a, Punkt 5)

- employee_role_settings.vorarbeiter (NOT NULL, server_default false): trägt wie ein Kolonnenführer Schlechtwetter ein und bestätigt
  Anträge. Niemand wird automatisch Vorarbeiter -- auch nicht über die Funktion „Dachdecker Vorarbeiter“ oder die Rolle in einer Kolonne
  (reiner Text); das Büro setzt das Kennzeichen am Mitarbeiter.
- Die Zeitarten weather_winter und weather_summer (Optionsgruppe time_entry_types) werden inaktiv: Schlechtwetter ist seitdem ein
  Ausfalltag (Kategorie schlechtwetter), keine Buchung auf einen Auftrag. Gebuchtes bleibt lesbar (Regel 22).

downgrade(): Spalte weg, die beiden Zeitarten wieder aktiv -- nur, wenn sie inaktiv sind.

Revision ID: e4b7d1a93c56
Revises: d8f2a6c4e913
Create Date: 2026-11-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4b7d1a93c56'
down_revision = 'd8f2a6c4e913'
branch_labels = None
depends_on = None

ZEITARTEN = ("weather_winter", "weather_summer")


def zeitarten_setzen(bind, aktiv: bool) -> int:
    return bind.execute(sa.text(
        "UPDATE setting_options SET active = :aktiv WHERE value IN ('weather_winter', 'weather_summer') AND active = :vorher "
        "AND group_id IN (SELECT id FROM setting_option_groups WHERE group_key = 'time_entry_types')"),
        {"aktiv": aktiv, "vorher": not aktiv}).rowcount


def upgrade() -> None:
    with op.batch_alter_table("employee_role_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("vorarbeiter", sa.Boolean(), server_default="0", nullable=False))
    zeitarten_setzen(op.get_bind(), False)


def downgrade() -> None:
    zeitarten_setzen(op.get_bind(), True)
    with op.batch_alter_table("employee_role_settings", schema=None) as batch_op:
        batch_op.drop_column("vorarbeiter")
