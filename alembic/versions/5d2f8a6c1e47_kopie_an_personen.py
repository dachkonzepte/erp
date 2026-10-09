"""kopie_an_personen -- Kopien an die im Dokument eingefrorenen Personen (seit 1.8.69, Nacharbeit zu Stufe 2c-2)

- Tabelle dispatch_copies: je Versand eines Dokuments mit "Kopie an:" im PDF (Briefe der Anzeigen, Abnahmeprotokoll) und je dort
  eingefrorenem Empfänger eine Zeile -- an welche Adresse die Kopie tatsächlich ging, oder keine Mail und warum. Fremdschlüssel
  auf email_dispatches benannt (batch unter SQLite und PostgreSQL gleich); Beteiligter und Kontakt ohne Fremdschlüssel.
- Kein Bestand: Versände vor 1.8.69 haben keine Zeilen (ihre Kopien stehen in email_dispatches.cc_recipients).

downgrade(): verweigert, solange eine Zeile existiert -- der Nachweis, wer laut Dokument keine Mail bekam, ginge verloren.

Revision ID: 5d2f8a6c1e47
Revises: 7c1e5a9d3f20
Create Date: 2026-10-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d2f8a6c1e47'
down_revision = '7c1e5a9d3f20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('dispatch_copies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dispatch_id', sa.Integer(), nullable=False),
    sa.Column('participant_id', sa.Integer(), nullable=False),
    sa.Column('contact_id', sa.Integer(), nullable=True),
    sa.Column('contact_name', sa.String(length=255), nullable=False),
    sa.Column('role_label', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['dispatch_id'], ['email_dispatches.id'], name='fk_dispatch_copies_dispatch_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dispatch_id', 'participant_id', name='uq_dispatch_copy')
    )
    with op.batch_alter_table('dispatch_copies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dispatch_copies_dispatch_id'), ['dispatch_id'], unique=False)


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM dispatch_copies")).scalar()
    if count:
        raise RuntimeError(f"Downgrade verweigert: {count} beim Versand festgehaltene Kopien existieren -- der Nachweis, an "
                           "welche Adresse eine Kopie ging oder wer laut Dokument keine Mail bekam, ginge verloren.")
    with op.batch_alter_table('dispatch_copies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dispatch_copies_dispatch_id'))

    op.drop_table('dispatch_copies')
