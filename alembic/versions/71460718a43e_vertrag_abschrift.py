"""vertrag_abschrift -- unterschriebene Abschrift des Vertrags (seit 1.8.35)

- Spalte order_contract_signatures.copy_document_id (nullable, FK sent_documents): die unterschriebene
  Abschrift in der Ablage, ein PDF aus der Fassung und dem Unterschriftsblatt bzw. dem Papier-Scan. Versand
  und Zustellung nach der Unterschrift verwenden sie. Bestand: leer -- eine Unterschrift von vor 1.8.35
  bekommt ihre Abschrift beim ersten Versand (app/contract_signatures.py::ensure_signed_copy()); die
  Migration selbst liest und schreibt keine Dateien der Ablage.

downgrade(): bricht ab, sobald eine Unterschrift eine Abschrift hat -- die Zuordnung ginge verloren (die
Datei bliebe in der Ablage), und nach einem erneuten upgrade entstünde beim nächsten Versand eine zweite,
andere Abschrift.

Revision ID: 71460718a43e
Revises: 65e3431d5bb6
Create Date: 2026-10-01 18:47:00.328465

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '71460718a43e'
down_revision = '65e3431d5bb6'
branch_labels = None
depends_on = None

FK_NAME = 'fk_order_contract_signatures_copy_document_id_sent_documents'


def upgrade() -> None:
    with op.batch_alter_table('order_contract_signatures', schema=None) as batch_op:
        batch_op.add_column(sa.Column('copy_document_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(FK_NAME, 'sent_documents', ['copy_document_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()
    copies = bind.execute(sa.text(
        "SELECT COUNT(*) FROM order_contract_signatures WHERE copy_document_id IS NOT NULL"
    )).scalar()
    if copies:
        raise RuntimeError(
            f"Downgrade abgebrochen: {copies} Unterschriften haben eine unterschriebene Abschrift; die Zuordnung "
            "ginge verloren. Vorher sichern, siehe Docstring."
        )
    # Ohne drop_constraint: PostgreSQL entfernt den Fremdschlüssel mit der Spalte, SQLite (batch) baut die Tabelle
    # ohne ihn neu -- so läuft der Downgrade auch, wenn der Fremdschlüssel anders heißt (Schema aus create_all()).
    with op.batch_alter_table('order_contract_signatures', schema=None) as batch_op:
        batch_op.drop_column('copy_document_id')
