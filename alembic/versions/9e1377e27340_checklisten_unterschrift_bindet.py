"""checklisten_unterschrift_bindet -- Unterschrift sperrt den Inhalt einer Checkliste (seit 1.8.13)

Fünf Spalten an checklist_attachments, alle nullable, keine Datenänderung beim Upgrade:
- content_sha256: Prüfsumme der Antworten und Fotos im Moment der Unterschrift.
- discarded_at / discarded_by_user_id / discarded_by_name / discard_reason: "Unterschriften
  verwerfen" durch das Büro. Die Unterschrift bleibt als Nachweis stehen, zählt aber nicht mehr.

Bestehende Unterschriften (vor 1.8.13) bekommen bewusst KEINE Prüfsumme nachgetragen: der
Inhalt zum Zeitpunkt ihrer Unterschrift ist nicht mehr bekannt (bis 1.8.12 ließ er sich nach der
Unterschrift noch ändern), eine heute berechnete Summe würde etwas bescheinigen, was niemand
unterschrieben hat. NULL heißt "vor 1.8.13 unterschrieben". Die Sperre selbst hängt nicht an der
Prüfsumme, sondern am Vorhandensein einer nicht verworfenen Unterschrift -- ein unterschriebener,
noch nicht abgeschlossener Entwurf ist deshalb ab diesem Upgrade gesperrt. Abschließen geht
weiterhin; wer noch etwas ändern muss, braucht das Büro ("Unterschriften verwerfen").

downgrade(): vor 1.8.13 gab es kein Verwerfen. Eine verworfene Unterschrift würde nach dem
Entfernen der Spalten wieder als gültige Unterschrift zählen -- sie wird deshalb gelöscht (die
Bilddatei bleibt im Datenordner liegen, eine Migration fasst keine Dateien an; die
Änderungshistorie behält Name, Zeitpunkt und Begründung).

Revision ID: 9e1377e27340
Revises: 7e3c1b9a5d24
Create Date: 2026-09-30 07:21:34.589475

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e1377e27340'
down_revision = '7e3c1b9a5d24'
branch_labels = None
depends_on = None

FK_NAME = "fk_checklist_attachments_discarded_by_user_id"


def upgrade() -> None:
    with op.batch_alter_table('checklist_attachments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_sha256', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('discarded_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('discarded_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('discarded_by_name', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('discard_reason', sa.Text(), nullable=True))
        batch_op.create_foreign_key(FK_NAME, 'app_users', ['discarded_by_user_id'], ['id'])


def downgrade() -> None:
    attachments = sa.table("checklist_attachments", sa.column("discarded_at", sa.DateTime()))
    op.execute(attachments.delete().where(attachments.c.discarded_at.isnot(None)))
    with op.batch_alter_table('checklist_attachments', schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_='foreignkey')
        batch_op.drop_column('discard_reason')
        batch_op.drop_column('discarded_by_name')
        batch_op.drop_column('discarded_by_user_id')
        batch_op.drop_column('discarded_at')
        batch_op.drop_column('content_sha256')
