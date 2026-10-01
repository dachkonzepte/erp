"""vertrag_festschreiben -- festgeschriebene Vertragsfassungen (seit 1.8.33)

- Tabelle order_contract_versions: je Festschreiben eine Fassung mit eingefrorenem Inhalt (JSON-Text
  mit Prüfsumme), Verweis auf das PDF in der Ablage (sent_documents) und auf die angehängte Fassung des
  Angebots. Eindeutig je Vertrag und Fassungsnummer. order_contracts.status kennt dazu den Wert
  "festgeschrieben" -- eine Zeichenkette, keine Schemaänderung.

downgrade(): bricht ab, sobald es eine Fassung oder einen festgeschriebenen Vertrag gibt -- eingefrorener
Inhalt und Prüfsumme gingen verloren (das PDF bliebe in der Ablage, aber ohne Zuordnung zur Fassung).

Revision ID: 091e7f52649b
Revises: 8caedec524b4
Create Date: 2026-10-01 16:03:52.985763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '091e7f52649b'
down_revision = '8caedec524b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('order_contract_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contract_id', sa.Integer(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('basis_key', sa.String(length=30), nullable=False),
    sa.Column('is_consumer', sa.Boolean(), nullable=False),
    sa.Column('frozen_content', sa.Text(), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('sent_document_id', sa.Integer(), nullable=False),
    sa.Column('attachment_kind', sa.String(length=20), nullable=False),
    sa.Column('attachment_document_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_by_name', sa.String(length=160), server_default='System', nullable=False),
    sa.Column('superseded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['attachment_document_id'], ['sent_documents.id'], ),
    sa.ForeignKeyConstraint(['contract_id'], ['order_contracts.id'], ),
    sa.ForeignKeyConstraint(['sent_document_id'], ['sent_documents.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('contract_id', 'version_no', name='uq_order_contract_version_no')
    )
    with op.batch_alter_table('order_contract_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_contract_versions_contract_id'), ['contract_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    versions = bind.execute(sa.text("SELECT COUNT(*) FROM order_contract_versions")).scalar()
    frozen = bind.execute(sa.text("SELECT COUNT(*) FROM order_contracts WHERE status <> 'entwurf'")).scalar()
    if versions or frozen:
        raise RuntimeError(
            f"Downgrade abgebrochen: {versions} festgeschriebene Vertragsfassungen, {frozen} nicht mehr im "
            "Entwurf befindliche Verträge gingen verloren. Vorher sichern, siehe Docstring."
        )
    with op.batch_alter_table('order_contract_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_order_contract_versions_contract_id'))

    op.drop_table('order_contract_versions')
