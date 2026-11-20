"""objektdokument_webanfrage -- Objektdokument zeigt auf den Eingang der Webseite (seit 1.10.9, Stufe W1c)

Neue Spalte property_documents.webanfrage_id (leer erlaubt, Fremdschlüssel auf webanfragen, Index): die Fotos, die das Übernehmen einer Anfrage der
Webseite als Kopie ans Objekt legt (seit 1.10.5), zeigen auf ihren Eingang -- bis 1.10.8 nur am Text erkennbar.

Bestand: verknüpft wird nur ein Dokument, das alle drei Merkmale trägt -- Beschreibung genau „Foto der Anfrage der Webseite <Nummer>“, Dateiname beginnt
mit „<Nummer>-“, und die Anfrage, als die der Eingang übernommen wurde, liegt an genau diesem Objekt. Alles andere (auch eine von Hand getippte
Beschreibung ohne passenden Eingang) bleibt leer. Die Nummer ist eindeutig (uq_webanfragen_nummer), je Dokument passt höchstens ein Eingang.

downgrade(): die Spalte fällt weg -- Beschreibung und Dateiname bleiben, wie bis 1.10.8.

Revision ID: 7e3a9c1f5b28
Revises: 5c1e9a7b3d20
Create Date: 2026-11-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e3a9c1f5b28'
down_revision = '5c1e9a7b3d20'
branch_labels = None
depends_on = None

TEXT = 'Foto der Anfrage der Webseite '

# substr/length/|| gelten unter SQLite und PostgreSQL gleich; kein LIKE mit der Nummer (sie ginge als Muster durch).
VERKNUEPFEN = sa.text(
    "UPDATE property_documents SET webanfrage_id = ("
    " SELECT w.id FROM webanfragen w JOIN inquiries i ON i.id = w.inquiry_id"
    " WHERE property_documents.description = :text || w.nummer"
    " AND substr(property_documents.original_filename, 1, length(w.nummer) + 1) = w.nummer || '-'"
    " AND i.property_id = property_documents.property_id)"
    " WHERE webanfrage_id IS NULL AND description IS NOT NULL AND substr(description, 1, :laenge) = :text"
)


def verknuepfen(bind) -> None:
    """Füllt webanfrage_id im Bestand (für sich aufrufbar, tests/test_v780_objektdokument_webanfrage.py)."""
    bind.execute(VERKNUEPFEN, {"text": TEXT, "laenge": len(TEXT)})


def upgrade() -> None:
    with op.batch_alter_table('property_documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('webanfrage_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_property_documents_webanfrage_id', ['webanfrage_id'], unique=False)
        batch_op.create_foreign_key('fk_property_documents_webanfrage_id', 'webanfragen', ['webanfrage_id'], ['id'])
    verknuepfen(op.get_bind())


def downgrade() -> None:
    with op.batch_alter_table('property_documents', schema=None) as batch_op:
        batch_op.drop_constraint('fk_property_documents_webanfrage_id', type_='foreignkey')
        batch_op.drop_index('ix_property_documents_webanfrage_id')
        batch_op.drop_column('webanfrage_id')
