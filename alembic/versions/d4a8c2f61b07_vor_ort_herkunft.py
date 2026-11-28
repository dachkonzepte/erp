"""vor_ort_herkunft -- Herkunft des Ansprechpartners vor Ort am Objekt (seit 1.11.50, W1c Stufe 2, S2-0 b; Bauplan B6, Antwort F5 vom 21.11.2026)

properties.vor_ort_aus_webanfrage_id (Fremdschlüssel auf webanfragen, leer erlaubt, Index) und properties.vor_ort_pruefwert (SHA-256, 64 Zeichen): hat das
Übernehmen eines Eingangs der Webseite Ansprechpartner vor Ort und Telefon gesetzt, halten sie Eingang und Prüfwert der gesetzten Werte fest. Keine Daten
geändert: ältere Übernahmen bleiben ohne Herkunft (Stufe 2 lässt deren Ansprechpartner stehen).

Unter SQLite die Spalte mit REFERENCES in einem ALTER TABLE ADD COLUMN (erlaubt bei leerer Vorgabe) -- ein batch_alter_table bräuchte den Fremdschlüssel als
eigene Anweisung und baute properties neu; mit eingeschalteter Prüfung der Fremdschlüssel (Tests) verweigerte SQLite das Löschen der alten Tabelle, solange
etwas auf sie zeigt (wie bei tests/test_v325_contract_basis.py). Unter PostgreSQL Spalte und benannter Fremdschlüssel.

downgrade(): Index, Fremdschlüssel und beide Spalten weg (unter SQLite über batch_alter_table).

Revision ID: d4a8c2f61b07
Revises: b3e7a1d9c5f2
Create Date: 2026-11-28

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'd4a8c2f61b07'
down_revision = 'b3e7a1d9c5f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("ALTER TABLE properties ADD COLUMN vor_ort_aus_webanfrage_id INTEGER REFERENCES webanfragen (id)")
    else:
        op.add_column('properties', sa.Column('vor_ort_aus_webanfrage_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_properties_vor_ort_aus_webanfrage_id', 'properties', 'webanfragen', ['vor_ort_aus_webanfrage_id'], ['id'])
    op.add_column('properties', sa.Column('vor_ort_pruefwert', sa.String(length=64), nullable=True))
    op.create_index('ix_properties_vor_ort_aus_webanfrage_id', 'properties', ['vor_ort_aus_webanfrage_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_properties_vor_ort_aus_webanfrage_id', table_name='properties')
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table('properties', schema=None) as batch_op:
            batch_op.drop_column('vor_ort_pruefwert')
            batch_op.drop_column('vor_ort_aus_webanfrage_id')
    else:
        op.drop_constraint('fk_properties_vor_ort_aus_webanfrage_id', 'properties', type_='foreignkey')
        op.drop_column('properties', 'vor_ort_pruefwert')
        op.drop_column('properties', 'vor_ort_aus_webanfrage_id')
