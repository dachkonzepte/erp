"""personalnummer_ohne_person -- eine gemerkte Personalnummer darf ohne Person stehen (seit 1.9.213, L1a Stufe 6, Punkt 2)

personalnummern_vergeben.employee_id: leer erlaubt. scripts/personalnummern_einlesen.py liest vergebene Personalnummern aus einer Datei auf
dem Server in die Sperrliste ein -- auch Nummern von Personen, die das ERP nie kannte; die stehen ohne Person (danach bekommt sie keine Person
im ERP). Nummer bleibt eindeutig, Fremdschlüssel und Index bleiben.

downgrade(): löscht die Nummern ohne Person (die alte Fassung kennt keine) und verlangt die Person wieder. Nach einem erneuten Einspielen das
Skript noch einmal laufen lassen -- es ist mehrfach ausführbar.

Revision ID: 8b4c2f9e1d07
Revises: 5d2e8a71c4f3
Create Date: 2026-11-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b4c2f9e1d07'
down_revision = '5d2e8a71c4f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("personalnummern_vergeben", schema=None) as batch_op:
        batch_op.alter_column("employee_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM personalnummern_vergeben WHERE employee_id IS NULL"))
    with op.batch_alter_table("personalnummern_vergeben", schema=None) as batch_op:
        batch_op.alter_column("employee_id", existing_type=sa.Integer(), nullable=False)
