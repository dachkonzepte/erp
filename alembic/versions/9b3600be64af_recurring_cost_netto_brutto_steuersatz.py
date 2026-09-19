"""recurring cost netto brutto steuersatz

Revision ID: 9b3600be64af
Revises: cf4fdf4905cd
Create Date: 2026-09-19 11:36:41.784726

Echte Spalten-Umbenennung (amount -> net_amount) statt des von --autogenerate vorgeschlagenen
add/drop-Paars -- 0 Bestandszeilen (real geprüft), der Wert bleibt inhaltlich unverändert (der
alte, einzelne Betrag war ohne jede Steuersemantik geführt und wird ab jetzt als das behandelt,
was er für den Verrechnungssatz-Kreislauf ohnehin schon war: netto, siehe CLAUDE.md
"Netto und Brutto bei den Betriebskosten"). Ein add/drop hätte für eine Installation MIT
Bestandsdaten den alten Betrag ersatzlos verworfen -- ein reines alter_column() bewahrt ihn.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b3600be64af'
down_revision = 'cf4fdf4905cd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('recurring_costs', schema=None) as batch_op:
        batch_op.alter_column('amount', new_column_name='net_amount')
        batch_op.add_column(sa.Column('tax_rate_pct', sa.Numeric(precision=5, scale=2), server_default='19.00', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('recurring_costs', schema=None) as batch_op:
        batch_op.drop_column('tax_rate_pct')
        batch_op.alter_column('net_amount', new_column_name='amount')
