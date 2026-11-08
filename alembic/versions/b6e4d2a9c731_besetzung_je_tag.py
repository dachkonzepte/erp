"""besetzung_je_tag -- die Tage einer Person am Einsatz (seit 1.9.260, Stufe 6, R5a, Punkt 1)

planning_slot_employees.tage (TEXT, leer erlaubt) wie planning_slot_resources.tage (1.9.234): JSON-Liste einzelner Tage innerhalb des Einsatzes, leer (NULL)
= alle Tage. Keine Datenübernahme: jede bestehende Zeile bleibt leer -- jeder bestehende Einsatz behält seine Besetzung an allen Tagen.

downgrade(): bricht ab, solange eine Person an einzelnen Tagen steht -- ohne die Spalte stünde sie still an allen Tagen, das ist nicht der Vorzustand.
Sonst fällt die Spalte weg.

Revision ID: b6e4d2a9c731
Revises: e3b7c51a9d26
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6e4d2a9c731'
down_revision = 'e3b7c51a9d26'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planning_slot_employees") as batch:
        batch.add_column(sa.Column("tage", sa.Text(), nullable=True))


def downgrade() -> None:
    einzeln = op.get_bind().execute(sa.text("SELECT count(*) FROM planning_slot_employees WHERE tage IS NOT NULL")).scalar()
    if einzeln:
        raise RuntimeError(f"Downgrade abgebrochen, nichts geändert: {einzeln} Person(en) stehen an einzelnen Tagen eines Einsatzes -- die Fassung davor "
                           "kennt nur alle Tage. Bitte zuerst im Einsatz „alle Tage“ wählen oder die Person herausnehmen.")
    with op.batch_alter_table("planning_slot_employees") as batch:
        batch.drop_column("tage")
