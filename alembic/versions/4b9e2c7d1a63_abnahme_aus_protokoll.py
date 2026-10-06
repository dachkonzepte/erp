"""abnahme_aus_protokoll -- Abnahme aus dem Abnahmeprotokoll (seit 1.8.63, Stufe 2c-2d Teil 2, Punkt 3)

- order_acceptances.checklist_id: nullable, Fremdschlüssel auf checklists (benannt), Index -- das Protokoll.
- order_acceptances.checklist_attachment_id: nullable, Fremdschlüssel auf checklist_attachments (benannt), UNIQUE
  (uq_order_acceptance_checklist_attachment) -- die Unterschrift des Auftraggebers; höchstens eine Abnahme je Unterschrift,
  auch wenn das Nachholen der Folge nach einem Abbruch noch einmal läuft.
- order_acceptances.protocol_seal_sha256: Prüfsumme der Kopie dieser Unterschrift.
- order_acceptances.declared_by_person / declared_by_function: wer für den Auftraggeber laut Auftrag unterschrieben hat.
Alle leer bei vorhandenen Abnahmen (von Hand erfasst) -- ihr gebundener Inhalt bleibt in ihrem Format (checksum_format 1/2).

downgrade(): verweigert, solange eine Abnahme aus einem Protokoll existiert -- sie verlöre ihren Nachweis, und ihr gebundener
Inhalt (Format 3) passte nicht mehr; ebenso, solange eine Abnahme Person oder Funktion trägt.

Revision ID: 4b9e2c7d1a63
Revises: 65c57e30d0f3
Create Date: 2026-10-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b9e2c7d1a63'
down_revision = '65c57e30d0f3'
branch_labels = None
depends_on = None

FK_CHECKLIST = "fk_order_acceptances_checklist_id"
FK_SIGNATURE = "fk_order_acceptances_checklist_attachment_id"
UQ_SIGNATURE = "uq_order_acceptance_checklist_attachment"


def upgrade() -> None:
    with op.batch_alter_table('order_acceptances', schema=None) as batch_op:
        batch_op.add_column(sa.Column('checklist_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('checklist_attachment_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('protocol_seal_sha256', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('declared_by_person', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('declared_by_function', sa.String(length=120), nullable=True))
        batch_op.create_index(batch_op.f('ix_order_acceptances_checklist_id'), ['checklist_id'], unique=False)
        batch_op.create_unique_constraint(UQ_SIGNATURE, ['checklist_attachment_id'])
        batch_op.create_foreign_key(FK_CHECKLIST, 'checklists', ['checklist_id'], ['id'])
        batch_op.create_foreign_key(FK_SIGNATURE, 'checklist_attachments', ['checklist_attachment_id'], ['id'])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM order_acceptances WHERE checklist_attachment_id IS NOT NULL OR checklist_id IS NOT NULL "
        "OR declared_by_person IS NOT NULL OR declared_by_function IS NOT NULL")).scalar()
    if count:
        raise RuntimeError(f"Downgrade verweigert: {count} Abnahmen stammen aus einem Abnahmeprotokoll bzw. tragen die "
                           "unterschreibende Person -- sie verlören ihren Nachweis, und ihr gebundener Inhalt passte nicht mehr.")
    with op.batch_alter_table('order_acceptances', schema=None) as batch_op:
        batch_op.drop_constraint(FK_SIGNATURE, type_='foreignkey')
        batch_op.drop_constraint(FK_CHECKLIST, type_='foreignkey')
        batch_op.drop_constraint(UQ_SIGNATURE, type_='unique')
        batch_op.drop_index(batch_op.f('ix_order_acceptances_checklist_id'))
        batch_op.drop_column('declared_by_function')
        batch_op.drop_column('declared_by_person')
        batch_op.drop_column('protocol_seal_sha256')
        batch_op.drop_column('checklist_attachment_id')
        batch_op.drop_column('checklist_id')
