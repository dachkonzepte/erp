"""feste_fassung_checkliste -- feste Fassung einer Checkliste (seit 1.8.66, Stufe 2c-2e, Punkt 1)

- Tabelle checklist_versions: je Unterschrift (UNIQUE signature_id) und je Abschluss bzw. "gegenstandslos" eine Fassung mit
  fortlaufender Nummer je Checkliste (UNIQUE checklist_id, version_no), den Unterschriften, die das PDF als gültig zeigt
  (signature_ids, JSON), der Prüfsumme der Kopie beim Erstellen und dem Verweis auf das PDF in der Ablage (sent_documents).
  Fremdschlüssel benannt, damit das Zurücknehmen unter SQLite (batch) und PostgreSQL gleich läuft.
- Kein Bestand: Unterschriften und Abschlüsse von vor 1.8.66 bekommen keine Fassung (ihr PDF wird wie bisher neu erzeugt).

downgrade(): verweigert, solange eine Fassung existiert -- ihr PDF bliebe in der Ablage, aber ohne den Bezug auf Unterschrift und
Stand; "überholt" ließe sich nicht mehr feststellen.

Revision ID: 28dde84825c8
Revises: 4b9e2c7d1a63
Create Date: 2026-10-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '28dde84825c8'
down_revision = '4b9e2c7d1a63'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('checklist_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('checklist_id', sa.Integer(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('signature_id', sa.Integer(), nullable=True),
    sa.Column('signature_ids', sa.Text(), nullable=False),
    sa.Column('seal_sha256', sa.String(length=64), nullable=True),
    sa.Column('sent_document_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_by_name', sa.String(length=160), server_default='System', nullable=False),
    sa.ForeignKeyConstraint(['checklist_id'], ['checklists.id'], name='fk_checklist_versions_checklist_id'),
    sa.ForeignKeyConstraint(['sent_document_id'], ['sent_documents.id'], name='fk_checklist_versions_sent_document_id'),
    sa.ForeignKeyConstraint(['signature_id'], ['checklist_attachments.id'], name='fk_checklist_versions_signature_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('checklist_id', 'version_no', name='uq_checklist_version_no'),
    sa.UniqueConstraint('signature_id', name='uq_checklist_version_signature')
    )
    with op.batch_alter_table('checklist_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_checklist_versions_checklist_id'), ['checklist_id'], unique=False)


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM checklist_versions")).scalar()
    if count:
        raise RuntimeError(f"Downgrade verweigert: {count} feste Fassungen von Checklisten existieren -- ihr Bezug auf "
                           "Unterschrift und Stand ginge verloren.")
    with op.batch_alter_table('checklist_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_checklist_versions_checklist_id'))

    op.drop_table('checklist_versions')
