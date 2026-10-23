"""zeitbuchung_mindestpause -- die eingetragene Mindestpause einer Zeitbuchung (seit 1.9.62)

- time_entries.min_break_minutes (Integer, leer erlaubt): die eingetragene Mindestpause („Pause mindestens“, beim Feierabend die
  eingegebene Pause, ohne Eingabe 0). „Pausen neu rechnen“ geht nie darunter (app/time_tracking.py::mindestpause_der_buchung()).

Ändert keine vorhandenen Daten: jede Buchung bleibt ohne Wert -- dort gilt die abgezogene Pause als Mindestpause.

downgrade(): verweigert, solange eine Buchung einen Wert hat -- er ginge verloren; ohne entfernt es die Spalte.

Revision ID: c4f2a8e61d35
Revises: b7e3d91c4a58
Create Date: 2026-10-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4f2a8e61d35'
down_revision = 'b7e3d91c4a58'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('time_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('min_break_minutes', sa.Integer(), nullable=True))


def downgrade() -> None:
    anzahl = op.get_bind().execute(sa.text("SELECT count(*) FROM time_entries WHERE min_break_minutes IS NOT NULL")).scalar()
    if anzahl:
        raise RuntimeError(f"Downgrade verweigert: {anzahl} Zeitbuchungen mit eingetragener Mindestpause -- sie ginge verloren.")
    with op.batch_alter_table('time_entries', schema=None) as batch_op:
        batch_op.drop_column('min_break_minutes')
