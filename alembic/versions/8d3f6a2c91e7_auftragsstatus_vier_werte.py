"""auftragsstatus_vier_werte -- der Auftrag hat nur noch vier Status (seit 1.9.124, Stufe 5, R2, Punkt 1)

- orders.status: beauftragt, arbeitsvorbereitung, in_ausfuehrung (und jeder unbekannte oder leere Wert) -> laeuft; pausiert, abgeschlossen,
  storniert bleiben (Groß-/Kleinschreibung und Leerraum vereinheitlicht). Die Phase (Arbeitsvorbereitung, Ausführung …) ergibt sich seither aus
  den Daten (app/akte.py), der Status sagt nur noch, ob der Auftrag läuft, ruht, fertig oder storniert ist (app/auftragsstatus.py).
- neue Tabelle order_status_changes: je Übergang alter und neuer Status, Begründung, „ohne Rechnung“, Zeitpunkt und Person -- unveränderlich.

downgrade(): verweigert, solange ein Auftrag „läuft“ (aus welchem der drei alten Werte er kam, ist nicht mehr bekannt) oder ein Statuswechsel
festgehalten ist (die Begründung ginge verloren); ohne beides entfernt es die Tabelle.

Revision ID: 8d3f6a2c91e7
Revises: 3e9b7c41d2a8
Create Date: 2026-10-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d3f6a2c91e7'
down_revision = '3e9b7c41d2a8'
branch_labels = None
depends_on = None

BLEIBEN = ("pausiert", "abgeschlossen", "storniert")


def neuer_status(alt: str | None) -> str:
    """Der Status nach der Migration -- dieselbe Regel wie die SQL-Anweisungen in _umstellen() (der Test prüft beides)."""
    wert = (alt or "").strip().lower()
    return wert if wert in BLEIBEN else "laeuft"


def _umstellen(bind) -> None:
    for wert in BLEIBEN:
        bind.execute(sa.text("UPDATE orders SET status = :w WHERE lower(trim(status)) = :w AND status <> :w"), {"w": wert})
    bind.execute(sa.text("UPDATE orders SET status = 'laeuft' WHERE status IS NULL OR lower(trim(status)) NOT IN "
                         "('pausiert', 'abgeschlossen', 'storniert')"))


def upgrade() -> None:
    op.create_table(
        'order_status_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('old_status', sa.String(length=50), nullable=False),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('without_invoice', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('changed_by_name', sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('order_status_changes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_status_changes_order_id'), ['order_id'], unique=False)
    _umstellen(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    laeuft = bind.execute(sa.text("SELECT count(*) FROM orders WHERE status = 'laeuft'")).scalar()
    wechsel = bind.execute(sa.text("SELECT count(*) FROM order_status_changes")).scalar()
    if laeuft or wechsel:
        raise RuntimeError("Downgrade verweigert: ein Auftrag „läuft“ (aus welchem der alten Werte beauftragt, arbeitsvorbereitung, "
                           "in_ausfuehrung er kam, ist nicht mehr bekannt) oder ein Statuswechsel mit Begründung ginge verloren.")
    with op.batch_alter_table('order_status_changes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_order_status_changes_order_id'))
    op.drop_table('order_status_changes')
