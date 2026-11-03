"""arbeitszeitkalender -- Tage, die jedes Jahr am selben Datum anders laufen (seit 1.9.175, L1a-Nachtrag, Punkt 2)

Neu: Tabelle arbeitszeit_kalendertage (Schlüssel, Name, Monat und Tag, Sollzeit, Abwesenheit, bezahlt, was ein Urlaub über den Tag zählt, nur
gewerbliche, nur Montag bis Freitag, aktiv). Heiligabend (24.12., 7,00 h, „Heiligabend – bezahlte Freistellung“) und seine Zuordnung für den
Export (BF, Lohnart offen) legt beim Start app.grunddaten.anlegen() an (Regel 23), nicht diese Migration. Kein Bestand wird geändert: die
Abwesenheit des Kalenders wird nicht gespeichert, sondern je Tag abgeleitet (app/arbeitszeitkalender.py).

downgrade(): Tabelle weg, dazu die Zeilen der Zuordnung zu Kalendertagen („kalender:…“), die der Stand davor nicht kennt.

Revision ID: fcbfd2cea2da
Revises: f6c3a8e25b19
Create Date: 2026-11-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fcbfd2cea2da'
down_revision = 'f6c3a8e25b19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "arbeitszeit_kalendertage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schluessel", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("monat", sa.Integer(), nullable=False),
        sa.Column("tag", sa.Integer(), nullable=False),
        sa.Column("sollzeit", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("abwesenheit", sa.String(length=120), nullable=False),
        sa.Column("bezahlt", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("im_urlaub", sa.String(length=20), server_default="kein_urlaubstag", nullable=False),
        sa.Column("nur_gewerblich", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("nur_mo_fr", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("aktiv", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schluessel", name="uq_arbeitszeit_kalendertag_schluessel"),
        sa.UniqueConstraint("monat", "tag", name="uq_arbeitszeit_kalendertag_datum"),
    )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM lohnart_zuordnungen WHERE schluessel LIKE 'kalender:%'"))
    op.drop_table("arbeitszeit_kalendertage")
