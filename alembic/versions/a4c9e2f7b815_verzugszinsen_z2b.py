"""verzugszinsen_z2b -- Basiszinssatz, Verzugszinsen, Zahlungen auf Nebenforderungen, Rechtstexte (seit 1.8.81, Z2b Punkte 7-9)

- base_interest_rates: Basiszinssatz je Halbjahr mit "geprüft am/durch" (Punkt 7), keine vorgegebenen Werte.
- invoice_charges.period_start/period_end/calculation_json: Zeitraum und eingefrorene Berechnung der Verzugszinsen (Art "zinsen").
- reminders.interest_accepted: Zinsen im Entwurf bewusst übernommen, Bestand: nein.
- payment_allocations.charge_id (FK invoice_charges, Index): Zahlung auf eine Nebenforderung (Art "nebenforderung", Punkt 8).
- dunning_legal_texts: Rechtstexte zu Verzug, Zinsen und Pauschale mit "geprüft am/durch" (Punkt 9), keine vorgegebenen Texte.

Ändert keine vorhandenen Daten (nur neue Tabellen und Spalten, alle leer bzw. "nein").

downgrade(): verweigert, solange etwas besteht, das der Rückweg verlöre (Verzugszinsen, Zahlungen auf Nebenforderungen, übernommene
Zinsen im Entwurf, eine Mahnung mit Aufstellung Format 3, ein Basiszinssatz, ein Rechtstext).

Revision ID: a4c9e2f7b815
Revises: 8e2f4b6d1c97
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4c9e2f7b815'
down_revision = '8e2f4b6d1c97'
branch_labels = None
depends_on = None

FK_ALLOCATION_CHARGE = "fk_payment_allocations_charge_id_invoice_charges"


def upgrade() -> None:
    op.create_table(
        'base_interest_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('half_year_start', sa.Date(), nullable=False),
        sa.Column('rate_percent', sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column('reviewed_on', sa.Date(), nullable=True),
        sa.Column('reviewed_by', sa.String(length=160), nullable=True),
        sa.Column('updated_by_name', sa.String(length=160), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('half_year_start', name='uq_base_interest_rate_half_year'),
    )
    op.create_table(
        'dunning_legal_texts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text_key', sa.String(length=20), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('reviewed_on', sa.Date(), nullable=True),
        sa.Column('reviewed_by', sa.String(length=160), nullable=True),
        sa.Column('updated_by_name', sa.String(length=160), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('text_key', name='uq_dunning_legal_text_key'),
    )
    with op.batch_alter_table('invoice_charges', schema=None) as batch_op:
        batch_op.add_column(sa.Column('period_start', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('period_end', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('calculation_json', sa.Text(), nullable=True))
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interest_accepted', sa.Boolean(), server_default='0', nullable=False))
    with op.batch_alter_table('payment_allocations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('charge_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_payment_allocations_charge_id'), ['charge_id'], unique=False)
        batch_op.create_foreign_key(FK_ALLOCATION_CHARGE, 'invoice_charges', ['charge_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()
    blocking = {
        "Verzugszinsen": ("SELECT COUNT(*) FROM invoice_charges WHERE kind = 'zinsen'", {}),
        "Zuordnungen auf Nebenforderungen": ("SELECT COUNT(*) FROM payment_allocations WHERE charge_id IS NOT NULL", {}),
        "Entwürfe mit übernommenen Zinsen": ("SELECT COUNT(*) FROM reminders WHERE interest_accepted = :ja", {"ja": True}),
        "Mahnungen mit Aufstellung Format 3": ("SELECT COUNT(*) FROM reminders WHERE amounts_json LIKE :f", {"f": '%"format":3%'}),
        "Basiszinssätze": ("SELECT COUNT(*) FROM base_interest_rates", {}),
        "Rechtstexte": ("SELECT COUNT(*) FROM dunning_legal_texts", {}),
    }
    found = {label: bind.execute(sa.text(sql), params).scalar() for label, (sql, params) in blocking.items()}
    found = {label: n for label, n in found.items() if n}
    if found:
        listed = ", ".join(f"{n} {label}" for label, n in found.items())
        raise RuntimeError(f"Downgrade verweigert: {listed} -- sie gingen verloren.")

    with op.batch_alter_table('payment_allocations', schema=None) as batch_op:
        batch_op.drop_constraint(FK_ALLOCATION_CHARGE, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_payment_allocations_charge_id'))
        batch_op.drop_column('charge_id')
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.drop_column('interest_accepted')
    with op.batch_alter_table('invoice_charges', schema=None) as batch_op:
        batch_op.drop_column('calculation_json')
        batch_op.drop_column('period_end')
        batch_op.drop_column('period_start')
    op.drop_table('dunning_legal_texts')
    op.drop_table('base_interest_rates')
