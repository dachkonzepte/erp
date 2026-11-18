"""urlaub_verfall_buchen -- der gebuchte Verfall des Übertrags (seit 1.9.368)

Urlaubsrunde, Punkt 4: in urlaubsansprueche die Spalten verfall_tage (Numeric(4,1)), verfall_gebucht_am (DateTime, naives UTC) und verfall_gebucht_von
(String(120)), alle leer. Nach dem Verfall zeigt das Urlaubskonto den nicht genommenen Übertrag mit „Verfall buchen“ (Admin, Büro – Finanzen); erst die Buchung
mindert den Rest -- nichts verfällt von selbst. Der Bestand bleibt leer.

downgrade(): bricht ab, solange ein Verfall gebucht ist (die Fassung davor kennt ihn nicht, der Rest stiege still); sonst fallen die Spalten weg.

Revision ID: f8b4d0e3a629
Revises: e7a3c9d2f518
Create Date: 2026-11-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8b4d0e3a629'
down_revision = 'e7a3c9d2f518'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("urlaubsansprueche") as batch:
        batch.add_column(sa.Column("verfall_tage", sa.Numeric(4, 1), nullable=True))
        batch.add_column(sa.Column("verfall_gebucht_am", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("verfall_gebucht_von", sa.String(120), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    gesetzt = bind.execute(sa.text("SELECT count(*) FROM urlaubsansprueche WHERE verfall_tage IS NOT NULL")).scalar()
    if gesetzt:
        raise RuntimeError("Downgrade abgebrochen, nichts geändert: ein Verfall des Übertrags ist gebucht -- die Fassung davor kennt ihn nicht, der Rest "
                           "stiege still.")
    with op.batch_alter_table("urlaubsansprueche") as batch:
        batch.drop_column("verfall_gebucht_von")
        batch.drop_column("verfall_gebucht_am")
        batch.drop_column("verfall_tage")
