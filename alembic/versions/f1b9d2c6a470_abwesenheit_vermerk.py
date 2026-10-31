"""abwesenheit_vermerk -- was das Programm schreibt, steht neben der Notiz des Admins (seit 1.9.165, Stufe 6, R2, Punkt 7)

Neue Spalte employee_absence_requests.vermerk. upgrade() verschiebt, was das Programm in review_notes geschrieben hat (die Texte aus app/absence_requests.py, hier als Kopie). Eine Notiz, die das Löschen
schon überschrieben hat, steht nur noch im Änderungsprotokoll: sie kommt nicht von selbst zurück.

downgrade(): der Vermerk geht zurück nach review_notes, wie die alte Fassung ihn liest; steht dort eine Notiz des Admins, bleibt sie und der Vermerk fällt weg.

Revision ID: f1b9d2c6a470
Revises: e3a7c4b95d18
Create Date: 2026-10-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1b9d2c6a470'
down_revision = 'e3a7c4b95d18'
branch_labels = None
depends_on = None

MIGRATION_VERMERK = "Auf der Plantafel eingetragen (vor 1.9.146)"
ABWESENHEIT_GELOESCHT = "Die genehmigte Abwesenheit wurde gelöscht."


def verschieben(bind) -> None:
    bind.execute(sa.text("UPDATE employee_absence_requests SET vermerk = review_notes, review_notes = NULL WHERE review_notes LIKE :m OR review_notes = :g"),
                 {"m": MIGRATION_VERMERK + "%", "g": ABWESENHEIT_GELOESCHT})


def upgrade() -> None:
    op.add_column("employee_absence_requests", sa.Column("vermerk", sa.Text(), nullable=True))
    verschieben(op.get_bind())


def downgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE employee_absence_requests SET review_notes = vermerk WHERE vermerk IS NOT NULL AND review_notes IS NULL"))
    with op.batch_alter_table("employee_absence_requests") as batch_op:
        batch_op.drop_column("vermerk")
