"""vertrag_unterschrift -- Unterschrift unter dem Vertrag (seit 1.8.34)

- Tabelle order_contract_signatures: höchstens eine Unterschrift je Vertrag (unique contract_id), gebunden
  an eine festgeschriebene Fassung (version_id), auf dem Gerät oder als Papier-Scan, mit dem
  unterschriebenen Inhalt als JSON-Text samt Prüfsumme und Verweisen auf Unterschriftsblatt/Scan und die
  beiden Unterschriftsbilder in der Ablage (sent_documents). order_contracts.status kennt dazu den Wert
  "unterschrieben" -- eine Zeichenkette, keine Schemaänderung.
- Spalte contract_template_sections.early_start (Boolean, NOT NULL, server_default falsch): kennzeichnet
  das Ankreuzfeld "Verlangen des vorzeitigen Beginns" für den Vermerk bei der Widerrufsfrist. Bestand:
  kein Abschnitt gekennzeichnet.

downgrade(): bricht ab, sobald es eine Unterschrift, einen unterschriebenen Vertrag oder einen als
"vorzeitiger Beginn" gekennzeichneten Abschnitt gibt -- unterschriebener Inhalt, Prüfsumme und Kennzeichen
gingen verloren (Unterschriftsblatt, Scan und Bilder blieben in der Ablage, aber ohne Zuordnung).

Revision ID: 65e3431d5bb6
Revises: 091e7f52649b
Create Date: 2026-10-01 17:24:05.340640

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65e3431d5bb6'
down_revision = '091e7f52649b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('order_contract_signatures',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contract_id', sa.Integer(), nullable=False),
    sa.Column('version_id', sa.Integer(), nullable=False),
    sa.Column('method', sa.String(length=20), nullable=False),
    sa.Column('signed_on', sa.Date(), nullable=False),
    sa.Column('customer_signer_name', sa.String(length=160), nullable=True),
    sa.Column('company_signer_name', sa.String(length=160), nullable=True),
    sa.Column('signed_content', sa.Text(), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('customer_image_document_id', sa.Integer(), nullable=True),
    sa.Column('company_image_document_id', sa.Integer(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(), nullable=False),
    sa.Column('recorded_by_user_id', sa.Integer(), nullable=True),
    sa.Column('recorded_by_name', sa.String(length=160), server_default='System', nullable=False),
    sa.ForeignKeyConstraint(['company_image_document_id'], ['sent_documents.id'], ),
    sa.ForeignKeyConstraint(['contract_id'], ['order_contracts.id'], ),
    sa.ForeignKeyConstraint(['customer_image_document_id'], ['sent_documents.id'], ),
    sa.ForeignKeyConstraint(['document_id'], ['sent_documents.id'], ),
    sa.ForeignKeyConstraint(['version_id'], ['order_contract_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('contract_id', name='uq_order_contract_signature_contract')
    )
    with op.batch_alter_table('order_contract_signatures', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_contract_signatures_contract_id'), ['contract_id'], unique=False)

    with op.batch_alter_table('contract_template_sections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('early_start', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    signatures = bind.execute(sa.text("SELECT COUNT(*) FROM order_contract_signatures")).scalar()
    signed = bind.execute(sa.text("SELECT COUNT(*) FROM order_contracts WHERE status = 'unterschrieben'")).scalar()
    marked = bind.execute(sa.text("SELECT COUNT(*) FROM contract_template_sections WHERE early_start")).scalar()
    if signatures or signed or marked:
        raise RuntimeError(
            f"Downgrade abgebrochen: {signatures} Unterschriften, {signed} unterschriebene Verträge, {marked} als "
            "„vorzeitiger Beginn“ gekennzeichnete Vorlagenabschnitte gingen verloren. Vorher sichern, siehe Docstring."
        )
    with op.batch_alter_table('contract_template_sections', schema=None) as batch_op:
        batch_op.drop_column('early_start')

    with op.batch_alter_table('order_contract_signatures', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_order_contract_signatures_contract_id'))

    op.drop_table('order_contract_signatures')
