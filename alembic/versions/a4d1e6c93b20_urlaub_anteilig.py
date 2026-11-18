"""urlaub_anteilig -- Jahresanspruch hinter einem übernommenen anteiligen Anspruch (seit 1.9.365)

Urlaubsrunde, Punkt 1: in urlaubsansprueche die Spalte anteilig_aus (Numeric(4,1), leer). „Vorschlag übernehmen“ setzt die Urlaubstage des Jahrs auf den
anteiligen Anspruch und merkt hier den Jahresanspruch, aus dem er gerechnet ist -- sonst rechnete der nächste Vorschlag aus dem schon gekürzten Wert. Leer
heißt nicht übernommen; der Bestand bleibt leer.

downgrade(): bricht ab, solange ein Wert gesetzt ist (die Fassung davor kennt ihn nicht, er ginge verloren); sonst fällt die Spalte weg.

Revision ID: a4d1e6c93b20
Revises: 9e4b2c7d1a35
Create Date: 2026-11-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4d1e6c93b20'
down_revision = '9e4b2c7d1a35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("urlaubsansprueche") as batch:
        batch.add_column(sa.Column("anteilig_aus", sa.Numeric(4, 1), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    gesetzt = bind.execute(sa.text("SELECT count(*) FROM urlaubsansprueche WHERE anteilig_aus IS NOT NULL")).scalar()
    if gesetzt:
        raise RuntimeError("Downgrade abgebrochen, nichts geändert: ein anteiliger Anspruch ist übernommen (anteilig_aus gesetzt) -- die Fassung davor "
                           "kennt ihn nicht, er ginge verloren.")
    with op.batch_alter_table("urlaubsansprueche") as batch:
        batch.drop_column("anteilig_aus")
