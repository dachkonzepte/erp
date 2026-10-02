"""Adressbuch-Eintrag mit Verweis auf Kunde oder Lieferant (seit 1.8.39, Beteiligte aus den Stammdaten)

- contacts.customer_id (FK customers.id) und contacts.supplier_id (FK suppliers.id), beide optional; je
  UNIQUE (uq_contact_customer, uq_contact_supplier): höchstens ein Adressbuch-Eintrag je Kunde bzw.
  Lieferant, in weiteren Projekten wiederverwendet. Name, E-Mail, Telefon und Adresse eines solchen
  Eintrags kommen beim Lesen aus dem Stammsatz (app/contacts.py) -- keine Kopie, deshalb nichts zu
  übernehmen; bestehende Kontakte bleiben ohne Verweis.

downgrade(): bricht ab, solange ein Kontakt einen Verweis trägt -- seine eigenen Namensspalten sind leer,
ohne Verweis stünde er namenlos im Adressbuch und in seinen Projekten.

Revision ID: 07c03fe93478
Revises: d6ac03a06d6f
Create Date: 2026-10-02 10:44:11.490713

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '07c03fe93478'
down_revision = 'd6ac03a06d6f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('contacts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('supplier_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('uq_contact_customer', ['customer_id'])
        batch_op.create_unique_constraint('uq_contact_supplier', ['supplier_id'])
        batch_op.create_foreign_key('fk_contacts_customer_id', 'customers', ['customer_id'], ['id'])
        batch_op.create_foreign_key('fk_contacts_supplier_id', 'suppliers', ['supplier_id'], ['id'])


def downgrade() -> None:
    linked = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM contacts WHERE customer_id IS NOT NULL OR supplier_id IS NOT NULL"
    )).scalar()
    if linked:
        raise RuntimeError(
            f"{linked} Adressbuch-Einträge verweisen auf einen Kunden oder Lieferanten -- ohne den Verweis "
            "stünden sie namenlos da. Downgrade abgebrochen; bitte die Einträge vorher klären."
        )
    with op.batch_alter_table('contacts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_contacts_supplier_id', type_='foreignkey')
        batch_op.drop_constraint('fk_contacts_customer_id', type_='foreignkey')
        batch_op.drop_constraint('uq_contact_supplier', type_='unique')
        batch_op.drop_constraint('uq_contact_customer', type_='unique')
        batch_op.drop_column('supplier_id')
        batch_op.drop_column('customer_id')
