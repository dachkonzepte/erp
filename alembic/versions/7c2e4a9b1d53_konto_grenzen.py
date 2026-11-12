"""konto_grenzen -- Grenzen des Arbeitszeitkontos in den Zeitregeln (seit 1.9.336)

Lohn L2c-3, Punkt 3 (Antwort B9): in time_tracking_settings die Spalten konto_hinweis_plus und konto_hinweis_minus (Numeric(6,2), leer). Leer heißt kein
Hinweis -- der Bestand bleibt ohne Grenzen.

downgrade(): bricht ab, solange eine Grenze gesetzt ist (die Fassung davor kennt sie nicht, sie ginge verloren); sonst fallen beide Spalten weg.

Revision ID: 7c2e4a9b1d53
Revises: 517c94f6dbcf
Create Date: 2026-11-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c2e4a9b1d53'
down_revision = '517c94f6dbcf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("time_tracking_settings") as batch:
        batch.add_column(sa.Column("konto_hinweis_plus", sa.Numeric(6, 2), nullable=True))
        batch.add_column(sa.Column("konto_hinweis_minus", sa.Numeric(6, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    gesetzt = bind.execute(sa.text("SELECT count(*) FROM time_tracking_settings WHERE konto_hinweis_plus IS NOT NULL OR konto_hinweis_minus IS NOT NULL")).scalar()
    if gesetzt:
        raise RuntimeError("Downgrade abgebrochen, nichts geändert: eine Grenze des Arbeitszeitkontos ist gesetzt -- die Fassung davor kennt sie nicht, sie "
                           "ginge verloren.")
    with op.batch_alter_table("time_tracking_settings") as batch:
        batch.drop_column("konto_hinweis_minus")
        batch.drop_column("konto_hinweis_plus")
