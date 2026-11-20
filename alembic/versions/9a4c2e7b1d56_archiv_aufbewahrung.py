"""archiv_aufbewahrung -- Archiv nach dem letzten Kontakt, Stufe 1 (seit 1.10.11, Stufe W1c)

Neue Spalten (leer erlaubt, ohne Bestand) an webanfragen, inquiries, customers und projects: archiviert_am (naives UTC; leer = nicht im Archiv -- am Projekt
gilt weiter das vorhandene „archived“, die Spalte sagt nur wann), archiviert_von_user_id (Fremdschlüssel auf app_users) und zurueckgeholt_am (ab da zählen
die 6 Monate neu). Index auf archiviert_am bei webanfragen, inquiries und customers (die Listen filtern danach).

downgrade(): bricht ab, solange ein Eingang, eine Anfrage oder ein Kunde im Archiv ist (sie stünden sonst wieder in jeder Liste); am Projekt bleibt
„archived“, nur Zeitpunkt und Konto fallen weg.

Revision ID: 9a4c2e7b1d56
Revises: 2d8b6f4a9c13
Create Date: 2026-11-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a4c2e7b1d56'
down_revision = '2d8b6f4a9c13'
branch_labels = None
depends_on = None

TABELLEN = ("webanfragen", "inquiries", "customers", "projects")
MIT_INDEX = ("webanfragen", "inquiries", "customers")


def upgrade() -> None:
    for tabelle in TABELLEN:
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.add_column(sa.Column('archiviert_am', sa.DateTime(), nullable=True))
            batch_op.add_column(sa.Column('archiviert_von_user_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('zurueckgeholt_am', sa.DateTime(), nullable=True))
            batch_op.create_foreign_key(f'fk_{tabelle}_archiviert_von_user_id', 'app_users', ['archiviert_von_user_id'], ['id'])
            if tabelle in MIT_INDEX:
                batch_op.create_index(f'ix_{tabelle}_archiviert_am', ['archiviert_am'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    for tabelle in MIT_INDEX:
        anzahl = bind.execute(sa.text(f"SELECT COUNT(*) FROM {tabelle} WHERE archiviert_am IS NOT NULL")).scalar()
        if anzahl:
            raise RuntimeError(f"{tabelle}: {anzahl} im Archiv -- sie stünden nach dem Downgrade wieder in jeder Liste.")
    for tabelle in reversed(TABELLEN):
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            if tabelle in MIT_INDEX:
                batch_op.drop_index(f'ix_{tabelle}_archiviert_am')
            batch_op.drop_constraint(f'fk_{tabelle}_archiviert_von_user_id', type_='foreignkey')
            batch_op.drop_column('zurueckgeholt_am')
            batch_op.drop_column('archiviert_von_user_id')
            batch_op.drop_column('archiviert_am')
