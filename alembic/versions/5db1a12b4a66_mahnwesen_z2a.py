"""mahnwesen_z2a -- Kunde der Rechnung ab dem Festschreiben, Aufstellung des gemahnten Betrags (seit 1.8.79, Zahlungsstufe Z2a)

- invoices.customer_id (FK customers, Index): der Kunde, zu dem eine festgeschriebene Rechnung gehört (Vorgabe Z2a "Vorweg",
  Nebenbefund 1 aus 1.8.78). Bestand: jede nicht als Entwurf geführte Rechnung (versendet, storniert, auch Stornorechnungen)
  bekommt den Kunden ihres Projekts -- bis 1.8.78 galt genau der als Kunde der Rechnung (app/payments.py::invoice_customer_id()).
  Entwürfe bleiben leer; sie bekommen ihren Kunden beim Festschreiben.
- reminders.amounts_json: Aufstellung des gemahnten Betrags (Brutto, Zahlungen, Skonto, Einbehalt, mahnfähig, Vorgabe Z2a Nr. 4).
  Bestand bleibt leer -- eine Mahnung von vor 1.8.79 zeigt weiter nur den offenen Betrag.

downgrade(): verweigert, solange eine festgeschriebene Mahnung eine Aufstellung trägt (sie stünde nur dort und ginge verloren).
Der Kunde der Rechnung ginge nicht verloren: seit 1.8.79 lässt sich der Kunde eines Projekts mit festgeschriebener Rechnung nicht
mehr wechseln, er steht also gleich am Projekt.

Revision ID: 5db1a12b4a66
Revises: c7d41e9a2b63
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5db1a12b4a66'
down_revision = 'c7d41e9a2b63'
branch_labels = None
depends_on = None

FK_NAME = "fk_invoices_customer_id_customers"


def kunden_uebernehmen(bind) -> int:
    """Setzt an jeder nicht als Entwurf geführten Rechnung den Kunden ihres Projekts. Gibt die Zahl der Rechnungen zurück."""
    return bind.execute(sa.text(
        "UPDATE invoices SET customer_id = ("
        " SELECT projects.customer_id FROM orders JOIN projects ON projects.id = orders.project_id"
        " WHERE orders.id = invoices.order_id"
        ") WHERE status <> 'entwurf'"
    )).rowcount


def upgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_invoices_customer_id'), ['customer_id'], unique=False)
        batch_op.create_foreign_key(FK_NAME, 'customers', ['customer_id'], ['id'])

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('amounts_json', sa.Text(), nullable=True))

    kunden_uebernehmen(op.get_bind())


def downgrade() -> None:
    count = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM reminders WHERE amounts_json IS NOT NULL AND status <> 'entwurf'"
    )).scalar()
    if count:
        raise RuntimeError(f"Downgrade verweigert: {count} festgeschriebene Mahnungen tragen eine Aufstellung des gemahnten "
                           "Betrags -- sie ginge verloren.")
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.drop_column('amounts_json')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_invoices_customer_id'))
        batch_op.drop_column('customer_id')
