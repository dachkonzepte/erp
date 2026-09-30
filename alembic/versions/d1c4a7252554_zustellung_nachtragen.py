"""zustellung_nachtragen -- Zustellung auf anderem Weg im Versandprotokoll (seit 1.8.20)

- email_dispatches: delivered_on (Datum der Zustellung), delivery_note (Notiz des Büros),
  receipt_document_id (Beleg in der Ablage) -- für nachgetragene Zustellungen per Einschreiben,
  persönlicher Übergabe, Bote oder Fax (channel).
- sent_documents.content_type (NOT NULL, server_default "application/pdf"): die Ablage nimmt neben
  PDFs auch den Beleg auf (Foto oder Scan). Bestehende Zeilen sind alle PDFs.

downgrade(): bricht ab, sobald eine Zustellung nachgetragen oder ein Beleg abgelegt ist -- sonst
gingen Datum, Notiz und die Zuordnung des Belegs verloren, und ein Beleg-Foto würde danach als PDF
ausgeliefert. Ohne solche Einträge entfernt er die Spalten.

Revision ID: d1c4a7252554
Revises: 304d6a607767
Create Date: 2026-09-30 17:40:12.905180

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1c4a7252554'
down_revision = '304d6a607767'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('email_dispatches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('delivered_on', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('delivery_note', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('receipt_document_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_email_dispatches_receipt_document_id_sent_documents', 'sent_documents',
                                    ['receipt_document_id'], ['id'])

    with op.batch_alter_table('sent_documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_type', sa.String(length=100), server_default='application/pdf', nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    manual = bind.execute(sa.text(
        "SELECT COUNT(*) FROM email_dispatches WHERE delivered_on IS NOT NULL OR receipt_document_id IS NOT NULL"
    )).scalar()
    receipts = bind.execute(sa.text("SELECT COUNT(*) FROM sent_documents WHERE content_type <> 'application/pdf'")).scalar()
    if manual or receipts:
        raise RuntimeError(
            f"Downgrade abgebrochen: {manual} nachgetragene Zustellungen, {receipts} Belege in der Ablage. "
            "Vorher sichern, siehe Docstring dieser Migration."
        )
    with op.batch_alter_table('sent_documents', schema=None) as batch_op:
        batch_op.drop_column('content_type')

    with op.batch_alter_table('email_dispatches', schema=None) as batch_op:
        batch_op.drop_constraint('fk_email_dispatches_receipt_document_id_sent_documents', type_='foreignkey')
        batch_op.drop_column('receipt_document_id')
        batch_op.drop_column('delivery_note')
        batch_op.drop_column('delivered_on')
