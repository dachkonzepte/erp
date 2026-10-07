"""protokoll_versand -- Versand des Abnahmeprotokolls und Verweis der Abnahme auf die feste Fassung (seit 1.8.67, Stufe 2c-2e,
Punkte 2 und 3)

- checklist_versions.copy_to: nullable Text (JSON) -- "Kopie an:" im PDF einer Fassung des Abnahmeprotokolls, beim Erstellen
  eingefroren. Leer bei vorhandenen Fassungen und bei jeder anderen Checkliste.
- order_acceptances.protocol_version_id: nullable, Fremdschlüssel auf checklist_versions (benannt) -- die feste Fassung der
  Unterschrift des Auftraggebers; order_acceptances.protocol_pdf_sha256: Prüfsumme ihres PDFs. Leer bei vorhandenen Abnahmen
  (Prüfsummenformat 1-3, ihr gebundener Inhalt bleibt).

downgrade(): verweigert, solange eine Abnahme auf eine Fassung verweist (ihr gebundener Inhalt im Format 4 passte nicht mehr) oder
eine Fassung "Kopie an:" trägt.

Revision ID: 7c1e5a9d3f20
Revises: 28dde84825c8
Create Date: 2026-10-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c1e5a9d3f20'
down_revision = '28dde84825c8'
branch_labels = None
depends_on = None

FK_VERSION = "fk_order_acceptances_protocol_version_id"


def upgrade() -> None:
    with op.batch_alter_table('checklist_versions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('copy_to', sa.Text(), nullable=True))
    with op.batch_alter_table('order_acceptances', schema=None) as batch_op:
        batch_op.add_column(sa.Column('protocol_version_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('protocol_pdf_sha256', sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(FK_VERSION, 'checklist_versions', ['protocol_version_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()
    acceptances = bind.execute(sa.text(
        "SELECT COUNT(*) FROM order_acceptances WHERE protocol_version_id IS NOT NULL OR protocol_pdf_sha256 IS NOT NULL"
    )).scalar()
    copies = bind.execute(sa.text("SELECT COUNT(*) FROM checklist_versions WHERE copy_to IS NOT NULL")).scalar()
    if acceptances or copies:
        raise RuntimeError(f"Downgrade verweigert: {acceptances} Abnahmen verweisen auf eine feste Fassung, {copies} Fassungen "
                           "tragen \"Kopie an:\" -- Verweis bzw. Nachweis gingen verloren.")
    with op.batch_alter_table('order_acceptances', schema=None) as batch_op:
        batch_op.drop_constraint(FK_VERSION, type_='foreignkey')
        batch_op.drop_column('protocol_pdf_sha256')
        batch_op.drop_column('protocol_version_id')
    with op.batch_alter_table('checklist_versions', schema=None) as batch_op:
        batch_op.drop_column('copy_to')
