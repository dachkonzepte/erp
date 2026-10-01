"""vertragsvorlagen -- Vertragsvorlagen und Vertragsentwurf am Auftrag (seit 1.8.32)

- Tabellen contract_templates (eine Vorlage je Vertragsgrundlage, Titel und rechtliche Prüfung) und
  contract_template_sections (Abschnitte mit Text, "nur bei Verbrauchern", Ankreuzfeld). Kein Seeding:
  bewusst keine vorgegebenen Vertragstexte.
- Tabelle order_contracts: der Vertragsentwurf am Auftrag mit den Fallfeldern Ausführungszeitraum,
  Abschlagsplan, Besonderheiten -- höchstens einer je Auftrag.
- orders.execution_period: der Freitext-Ausführungszeitraum aus dem Angebot, ab jetzt beim Beauftragen
  übernommen. Bestehende Aufträge bleiben leer (wie bei tax_key_id in 1.8.21: ein Nachdruck eines
  schon versendeten Auftrags-PDFs sähe sonst anders aus); am Auftrag lässt er sich nachtragen.

downgrade(): bricht ab, sobald etwas verloren ginge -- eine Vorlage, ein Vertragsentwurf oder ein
Ausführungszeitraum an einem Auftrag.

Revision ID: 8caedec524b4
Revises: 8af8137cc57c
Create Date: 2026-10-01 15:05:38.343338

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8caedec524b4'
down_revision = '8af8137cc57c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('contract_templates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('basis_key', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('reviewed_on', sa.Date(), nullable=True),
    sa.Column('reviewed_by', sa.String(length=160), nullable=True),
    sa.Column('updated_by_name', sa.String(length=160), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('basis_key', name='uq_contract_template_basis_key')
    )
    op.create_table('contract_template_sections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('heading', sa.String(length=255), nullable=True),
    sa.Column('body_text', sa.Text(), nullable=True),
    sa.Column('consumer_only', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('with_checkbox', sa.Boolean(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['template_id'], ['contract_templates.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('contract_template_sections', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contract_template_sections_template_id'), ['template_id'], unique=False)

    op.create_table('order_contracts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='entwurf', nullable=False),
    sa.Column('execution_period', sa.Text(), nullable=True),
    sa.Column('payment_plan', sa.Text(), nullable=True),
    sa.Column('special_terms', sa.Text(), nullable=True),
    sa.Column('created_by_name', sa.String(length=160), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_by_name', sa.String(length=160), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_id', name='uq_order_contract_order')
    )
    with op.batch_alter_table('order_contracts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_contracts_order_id'), ['order_id'], unique=False)

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('execution_period', sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    templates = bind.execute(sa.text("SELECT COUNT(*) FROM contract_templates")).scalar()
    contracts = bind.execute(sa.text("SELECT COUNT(*) FROM order_contracts")).scalar()
    periods = bind.execute(sa.text("SELECT COUNT(*) FROM orders WHERE COALESCE(execution_period, '') <> ''")).scalar()
    if templates or contracts or periods:
        raise RuntimeError(
            f"Downgrade abgebrochen: {templates} Vertragsvorlagen, {contracts} Vertragsentwürfe, "
            f"{periods} Aufträge mit Ausführungszeitraum gingen verloren. Vorher sichern, siehe Docstring."
        )

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('execution_period')

    with op.batch_alter_table('order_contracts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_order_contracts_order_id'))

    op.drop_table('order_contracts')
    with op.batch_alter_table('contract_template_sections', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_contract_template_sections_template_id'))

    op.drop_table('contract_template_sections')
    op.drop_table('contract_templates')
