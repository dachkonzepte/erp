"""webanfragen_uebernehmen -- Anfrage der Webseite als Anfrage übernehmen (seit 1.10.5, Stufe W1b)

Neue Spalten (leer erlaubt, ohne Bestand): inquiries.webseite_nummer (eindeutig: die Nummer der Webseite an der Anfrage) und webanfragen.inquiry_id
(eindeutig, Fremdschlüssel auf inquiries: übernommen als).

downgrade(): bricht ab, solange eine Anfrage der Webseite übernommen ist (die Verbindung ginge verloren); sonst fallen die Spalten weg.

Revision ID: 5c1e9a7b3d20
Revises: a107b86d8e8d
Create Date: 2026-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c1e9a7b3d20'
down_revision = 'a107b86d8e8d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('inquiries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('webseite_nummer', sa.String(length=40), nullable=True))
        batch_op.create_unique_constraint('uq_inquiries_webseite_nummer', ['webseite_nummer'])
    with op.batch_alter_table('webanfragen', schema=None) as batch_op:
        batch_op.add_column(sa.Column('inquiry_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('uq_webanfragen_inquiry_id', ['inquiry_id'])
        batch_op.create_foreign_key('fk_webanfragen_inquiry_id', 'inquiries', ['inquiry_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()
    uebernommen = bind.execute(sa.text("SELECT COUNT(*) FROM webanfragen WHERE status = 'uebernommen' OR inquiry_id IS NOT NULL")).scalar()
    if uebernommen:
        raise RuntimeError(f"webanfragen: {uebernommen} Anfragen sind übernommen -- die Verbindung zur Anfrage ginge mit dem Downgrade verloren.")
    with op.batch_alter_table('webanfragen', schema=None) as batch_op:
        batch_op.drop_constraint('fk_webanfragen_inquiry_id', type_='foreignkey')
        batch_op.drop_constraint('uq_webanfragen_inquiry_id', type_='unique')
        batch_op.drop_column('inquiry_id')
    with op.batch_alter_table('inquiries', schema=None) as batch_op:
        batch_op.drop_constraint('uq_inquiries_webseite_nummer', type_='unique')
        batch_op.drop_column('webseite_nummer')
