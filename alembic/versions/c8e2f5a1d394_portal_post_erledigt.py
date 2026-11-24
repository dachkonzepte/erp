"""portal_post_erledigt -- „Erledigt“ an einem gescheiterten Versand des Postboten (seit 1.11.9, Antwort 1.11.7-1/-3)

Ein gescheiterter Anmeldecode zeigt auf „Start“ einen Hinweis, bis ein späterer Versand gelingt -- oder bis ein Admin ihn mit „Erledigt“ abschließt. Dafür
drei Spalten am Auftrag, „quittiert“ (erledigt_am ist schon der Zeitpunkt des Postboten): wann und von wem (Konto und Name, wie gesperrt_von_* am Zugang).
Leer = nicht erledigt; der Bestand bleibt leer (ein alter Fehler zeigt den Hinweis weiter, bis er erledigt ist oder ein Versand gelingt). Die Funktionen der
Datenbank schreiben portal_post mit Spaltenliste -- die neuen Spalten berühren sie nicht; der Benutzer des Portals hat auf portal_post kein Recht
(app/portal/rechte.py).

downgrade(): die drei Spalten fallen weg -- mit ihnen nur der Vermerk am Auftrag (in der Änderungshistorie steht er weiter).

Revision ID: c8e2f5a1d394
Revises: b5d1e8a3c247
Create Date: 2026-11-24

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c8e2f5a1d394'
down_revision = 'b5d1e8a3c247'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('portal_post') as batch_op:
        batch_op.add_column(sa.Column('quittiert_am', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('quittiert_von_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('quittiert_von_name', sa.String(length=160), nullable=True))


def downgrade():
    with op.batch_alter_table('portal_post') as batch_op:
        batch_op.drop_column('quittiert_von_name')
        batch_op.drop_column('quittiert_von_user_id')
        batch_op.drop_column('quittiert_am')
