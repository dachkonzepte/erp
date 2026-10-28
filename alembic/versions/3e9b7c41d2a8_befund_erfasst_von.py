"""befund_erfasst_von -- wer einen Befund angelegt hat, als Konto (seit 1.9.112)

- findings.created_by_user_id (Integer, leer erlaubt, ohne Fremdschlüssel wie email_dispatches.created_by_user_id): das Konto, das den
  Befund angelegt hat
- findings.created_by_name (String(160), leer erlaubt): sein Anzeigename beim Anlegen -- „erfasst von“

Beide setzt der Server aus der Anmeldung (app/routers/findings.py::post_finding()); bis 1.9.111 hielt der Befund nur einen Mitarbeiter fest,
den die Berichtsseite mitschickte (den Ersteller des Berichts -- das Büro bekam 403, der Admin schrieb den Befund still der Monteurin zu).

Ändert keine vorhandenen Daten: beide Spalten bleiben für ältere Befunde leer (die Seite zeigt dann den Mitarbeiter, falls einer da ist).

downgrade(): verweigert, solange ein Befund ein erfassendes Konto trägt -- es ginge verloren; ohne entfernt es die Spalten.

Revision ID: 3e9b7c41d2a8
Revises: 750d709a4863
Create Date: 2026-10-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e9b7c41d2a8'
down_revision = '750d709a4863'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('findings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by_name', sa.String(length=160), nullable=True))


def downgrade() -> None:
    anzahl = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM findings WHERE created_by_user_id IS NOT NULL OR created_by_name IS NOT NULL")).scalar()
    if anzahl:
        raise RuntimeError("Downgrade verweigert: ein Befund trägt das Konto, das ihn erfasst hat -- es ginge verloren.")
    with op.batch_alter_table('findings', schema=None) as batch_op:
        batch_op.drop_column('created_by_name')
        batch_op.drop_column('created_by_user_id')
