"""lohndatei_versand_und_abgleich -- Art, versendet am / von und Notiz an der Ablage der Lohndatei (seit 1.9.327)

Lohn L2c-2, Punkt 0. In lohndateien die Spalten art (NOT NULL, server_default „datei“: datei | abgleich), versendet_am, versendet_von_user_id,
versendet_von_name und notiz (leer); dazu ein eindeutiger Index über monat nur für versendete Zeilen (je Monat höchstens eine versendete Datei). Der
Bestand: jede abgelegte Datei ist „datei“, nicht versendet -- nichts sonst ändert sich.

downgrade(): bricht ab, solange eine Abgleich-Zeile, eine versendete Datei oder eine Notiz da ist -- die Fassung davor kennt sie nicht, sie gingen
verloren. Sonst fallen Index und Spalten weg.

Revision ID: 517c94f6dbcf
Revises: 562f81626c3b
Create Date: 2026-11-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '517c94f6dbcf'
down_revision = '562f81626c3b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lohndateien") as batch:
        batch.add_column(sa.Column("art", sa.String(10), server_default="datei", nullable=False))
        batch.add_column(sa.Column("versendet_am", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("versendet_von_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("versendet_von_name", sa.String(160), nullable=True))
        batch.add_column(sa.Column("notiz", sa.String(500), nullable=True))
    op.create_index("uq_lohndatei_versendet_je_monat", "lohndateien", ["monat"], unique=True,
                    postgresql_where=sa.text("versendet_am IS NOT NULL"), sqlite_where=sa.text("versendet_am IS NOT NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    offen = bind.execute(sa.text("SELECT count(*) FROM lohndateien WHERE art <> 'datei' OR versendet_am IS NOT NULL OR notiz IS NOT NULL")).scalar()
    if offen:
        raise RuntimeError(f"Downgrade abgebrochen, nichts geändert: {offen} Zeile(n) der Ablage sind Abgleich, versendet oder tragen eine Notiz -- die "
                           "Fassung davor kennt das nicht, es ginge verloren.")
    op.drop_index("uq_lohndatei_versendet_je_monat", table_name="lohndateien")
    with op.batch_alter_table("lohndateien") as batch:
        batch.drop_column("notiz")
        batch.drop_column("versendet_von_name")
        batch.drop_column("versendet_von_user_id")
        batch.drop_column("versendet_am")
        batch.drop_column("art")
