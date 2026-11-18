"""urlaub_verfall_31_03 -- Vorgabe „Verfall“ des Übertrags 31.03. (seit 1.9.366)

Urlaubsrunde, Punkt 2 (Antwort Tobias 18.11.2026): der Übertrag aus dem Vorjahr verfällt am 31.03.; bis dahin verbraucht Urlaub zuerst ihn. Die Vorgabe
„Verfall“ der Zeitregeln (time_tracking_settings.urlaub_verfall) war ausgeliefert leer (= nie) -- diese Migration setzt sie auf „31.03.“, wo sie leer ist. Ein
eingetragener Wert bleibt.

downgrade(): ändert nichts. Die Fassung davor kennt die Spalte und den Wert (dort „nur vorgemerkt“), es geht nichts verloren; ob die Vorgabe vor dem Upgrade
leer war oder von Hand auf „31.03.“ stand, ist nicht mehr zu unterscheiden -- ein Zurücksetzen könnte einen eigenen Eintrag löschen.

Revision ID: c5e2f8a1d047
Revises: a4d1e6c93b20
Create Date: 2026-11-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5e2f8a1d047'
down_revision = 'a4d1e6c93b20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE time_tracking_settings SET urlaub_verfall = '31.03.' WHERE urlaub_verfall IS NULL OR urlaub_verfall = ''"))


def downgrade() -> None:
    pass  # siehe Docstring: der Wert bleibt, die Fassung davor kennt ihn
