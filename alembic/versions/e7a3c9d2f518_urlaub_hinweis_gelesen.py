"""urlaub_hinweis_gelesen -- wann der Hinweis auf den Resturlaub gelesen wurde (seit 1.9.367)

Urlaubsrunde, Punkt 3: in urlaubsansprueche die Spalte hinweis_gelesen_am (DateTime, leer). „Meine Zeiten“ zeigt ab dem 01.01. bis zum Verfall den Hinweis auf
den Resturlaub aus dem Vorjahr; „Gelesen“ speichert hier den Zeitpunkt (naives UTC), das Büro sieht im Urlaubskonto, wer noch nicht gelesen hat. Der Bestand
bleibt leer.

downgrade(): bricht ab, solange ein Zeitpunkt gespeichert ist (die Fassung davor kennt ihn nicht, er ginge verloren); sonst fällt die Spalte weg.

Revision ID: e7a3c9d2f518
Revises: c5e2f8a1d047
Create Date: 2026-11-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a3c9d2f518'
down_revision = 'c5e2f8a1d047'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("urlaubsansprueche") as batch:
        batch.add_column(sa.Column("hinweis_gelesen_am", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    gesetzt = bind.execute(sa.text("SELECT count(*) FROM urlaubsansprueche WHERE hinweis_gelesen_am IS NOT NULL")).scalar()
    if gesetzt:
        raise RuntimeError("Downgrade abgebrochen, nichts geändert: ein Hinweis auf den Resturlaub ist als gelesen gespeichert -- die Fassung davor kennt den "
                           "Zeitpunkt nicht, er ginge verloren.")
    with op.batch_alter_table("urlaubsansprueche") as batch:
        batch.drop_column("hinweis_gelesen_am")
