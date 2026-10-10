"""leistungszeitraum -- Leistungszeitraum an der Rechnung (seit 1.8.74)

- invoices.service_period_start/service_period_end: Beginn und Ende des Leistungszeitraums, Pflicht beim Festschreiben (im Code,
  app/invoices.py::finalize_block_reason()), Ende >= Beginn. Leer erlaubt: festgeschriebener Altbestand bleibt unverändert, ein
  Entwurf bekommt den Zeitraum vor dem Festschreiben.
- invoices.billed_work_from/billed_work_to: nur Rechnung aus Aufwand, erster und letzter Arbeitstag der beim Anlegen
  übernommenen Zeitbuchungen (Quelle des Vorschlags).
- Kein Bestand wird befüllt: alle vier Spalten bleiben für vorhandene Rechnungen leer (kein Vorschlag wird still eingetragen).

downgrade(): verweigert, solange eine Rechnung einen Leistungszeitraum trägt -- er stünde auf festgeschriebenen Rechnungen und
ginge verloren.

Revision ID: 9b4e2c7a1d58
Revises: 5d2f8a6c1e47
Create Date: 2026-10-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b4e2c7a1d58'
down_revision = '5d2f8a6c1e47'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('service_period_start', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('service_period_end', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('billed_work_from', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('billed_work_to', sa.Date(), nullable=True))


def downgrade() -> None:
    count = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM invoices WHERE service_period_start IS NOT NULL OR service_period_end IS NOT NULL"
    )).scalar()
    if count:
        raise RuntimeError(f"Downgrade verweigert: {count} Rechnungen tragen einen Leistungszeitraum -- er ginge verloren.")
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('billed_work_to')
        batch_op.drop_column('billed_work_from')
        batch_op.drop_column('service_period_end')
        batch_op.drop_column('service_period_start')
