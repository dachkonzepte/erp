"""nachtrag_und_festgeschrieben_am -- Nachtrag am Auftrag, Zeitpunkt des Festschreibens (seit 1.8.83, R4a Punkte 3 und 5)

- order_items.is_addendum: die Position ist ein Nachtrag, am Auftrag angelegt (Punkt 3); Bestand: nein.
- invoices.finalized_at: Zeitpunkt des Festschreibens (naive UTC), Grundlage von "letzter Stand" einer Position (Punkt 5); Bestand:
  leer -- Rechnungen von vor 1.8.83 ordnen wie bisher nach Rechnungsdatum und ID, hinter jeder späteren.

Ändert keine vorhandenen Daten.

downgrade(): verweigert, solange etwas besteht, das der Rückweg verlöre (ein Nachtrag würde eine gewöhnliche Position, eine
festgeschriebene Rechnung verlöre ihren Zeitpunkt).

Revision ID: 3b8f1d6c9e24
Revises: 6d1e8b3f2a47
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b8f1d6c9e24'
down_revision = '6d1e8b3f2a47'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_addendum', sa.Boolean(), server_default='0', nullable=False))
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('finalized_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    blocking = {
        "Nachträge": ("SELECT COUNT(*) FROM order_items WHERE is_addendum = :ja", {"ja": True}),
        "Rechnungen mit Zeitpunkt des Festschreibens": ("SELECT COUNT(*) FROM invoices WHERE finalized_at IS NOT NULL", {}),
    }
    found = {label: bind.execute(sa.text(sql), params).scalar() for label, (sql, params) in blocking.items()}
    found = {label: n for label, n in found.items() if n}
    if found:
        listed = ", ".join(f"{n} {label}" for label, n in found.items())
        raise RuntimeError(f"Downgrade verweigert: {listed} -- sie gingen verloren.")
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('finalized_at')
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_column('is_addendum')
