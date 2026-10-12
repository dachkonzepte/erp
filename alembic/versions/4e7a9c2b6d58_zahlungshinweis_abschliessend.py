"""zahlungshinweis_abschliessend -- Zahlungshinweis der Endrechnung, abschließende Rechnung aus Aufwand (seit 1.8.86, R4b Punkte 4 und 6)

- invoice_deductions.open_amount, .retained_open: was an der abgezogenen Rechnung beim Festschreiben der Schlussrechnung noch offen
  war (einschließlich Einbehalt) und wie viel davon Einbehalt -- Zahlungshinweis "Stand <Tag des Festschreibens>". Bestand: leer
  (Abzüge von 1.8.85 zeigen keinen Zahlungshinweis).
- invoices.closes_order: die Rechnung aus Aufwand schließt einen Auftrag nach Aufwand ab ("vollständig abgerechnet"). Bestand: nein.

Ändert keine vorhandenen Daten.

downgrade(): verweigert, solange etwas besteht, das der Rückweg verlöre (eine abschließende Rechnung, ein eingefrorener
Zahlungshinweis).

Revision ID: 4e7a9c2b6d58
Revises: 8c2e5a7d4f19
Create Date: 2026-10-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e7a9c2b6d58'
down_revision = '8c2e5a7d4f19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('invoice_deductions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('open_amount', sa.Numeric(precision=18, scale=2), nullable=True))
        batch_op.add_column(sa.Column('retained_open', sa.Numeric(precision=18, scale=2), nullable=True))
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('closes_order', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    blocking = {
        "abschließende Rechnungen aus Aufwand": ("SELECT COUNT(*) FROM invoices WHERE closes_order = :ja", {"ja": True}),
        "Abzüge mit Zahlungshinweis": ("SELECT COUNT(*) FROM invoice_deductions WHERE open_amount IS NOT NULL", {}),
    }
    found = {label: bind.execute(sa.text(sql), params).scalar() for label, (sql, params) in blocking.items()}
    found = {label: n for label, n in found.items() if n}
    if found:
        listed = ", ".join(f"{n} {label}" for label, n in found.items())
        raise RuntimeError(f"Downgrade verweigert: {listed} -- sie gingen verloren.")
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('closes_order')
    with op.batch_alter_table('invoice_deductions', schema=None) as batch_op:
        batch_op.drop_column('retained_open')
        batch_op.drop_column('open_amount')
