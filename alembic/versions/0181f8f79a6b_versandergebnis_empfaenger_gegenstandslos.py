"""Versandergebnis, Empfänger einer Zustellung, Anzeige als gegenstandslos (seit 1.8.41, Stufe 2b, Runde 2b-3 Teil 3)

- dispatch_outcomes: "Empfang bestätigt am" bzw. "unzustellbar" je Versand oder nachgetragener Zustellung --
  höchstens ein Ergebnis je Eintrag (UNIQUE), mit Datum, Notiz und optional Beleg in der Ablage.
- email_dispatches.delivered_to_client: ging eine nachgetragene Zustellung an den Auftraggeber (Empfängerauswahl)?
  Leer bei E-Mail und bei Zustellungen ohne Auswahl -- der Bestand bleibt leer.
- dispatch_authorizations.recipient_email darf leer sein: die Vollmacht wird jetzt auch bei einer nachgetragenen
  Zustellung (ohne E-Mail-Adresse) festgehalten.
- checklists.voided_at/voided_by_user_id/voided_by_name/void_reason: Behinderungs- bzw. Bedenkenanzeige als
  gegenstandslos abgeschlossen (Status "gegenstandslos", den kennt die Spalte status schon als freien Text).

Nichts zu übernehmen.

downgrade(): bricht ab, solange ein Versandergebnis, eine Zustellung mit Empfängerauswahl, eine festgehaltene
Vollmacht ohne E-Mail-Adresse oder eine gegenstandslose Checkliste existiert -- jedes davon ist ein Nachweis, der mit
den Spalten verloren ginge (bzw. die Vollmacht-Zeile verstieße gegen NOT NULL).

Revision ID: 0181f8f79a6b
Revises: e04a5161920d
Create Date: 2026-10-02 13:45:43.022627

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0181f8f79a6b'
down_revision = 'e04a5161920d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('dispatch_outcomes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dispatch_id', sa.Integer(), nullable=False),
    sa.Column('outcome', sa.String(length=20), nullable=False),
    sa.Column('outcome_on', sa.Date(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('receipt_document_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_by_name', sa.String(length=160), server_default='System', nullable=False),
    sa.ForeignKeyConstraint(['dispatch_id'], ['email_dispatches.id'], name='fk_dispatch_outcomes_dispatch_id'),
    sa.ForeignKeyConstraint(['receipt_document_id'], ['sent_documents.id'], name='fk_dispatch_outcomes_receipt_document_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dispatch_id', name='uq_dispatch_outcome')
    )
    with op.batch_alter_table('dispatch_outcomes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dispatch_outcomes_dispatch_id'), ['dispatch_id'], unique=False)

    with op.batch_alter_table('checklists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voided_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('voided_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('voided_by_name', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('void_reason', sa.Text(), nullable=True))

    with op.batch_alter_table('dispatch_authorizations', schema=None) as batch_op:
        batch_op.alter_column('recipient_email',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)

    with op.batch_alter_table('email_dispatches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('delivered_to_client', sa.Boolean(), nullable=True))


def _refuse_lossy_downgrade(bind) -> None:
    checks = (
        ("SELECT COUNT(*) FROM dispatch_outcomes", "Versandergebnisse (Empfang bestätigt / unzustellbar)"),
        ("SELECT COUNT(*) FROM email_dispatches WHERE delivered_to_client IS NOT NULL",
         "nachgetragene Zustellungen mit Empfängerauswahl"),
        ("SELECT COUNT(*) FROM dispatch_authorizations WHERE recipient_email IS NULL",
         "Vollmachten aus nachgetragenen Zustellungen"),
        ("SELECT COUNT(*) FROM checklists WHERE voided_at IS NOT NULL OR status = 'gegenstandslos'",
         "als gegenstandslos abgeschlossene Checklisten"),
    )
    found = [label for sql, label in checks if bind.execute(sa.text(sql)).scalar()]
    if found:
        raise RuntimeError("Downgrade abgebrochen: es gibt " + ", ".join(found) + " -- diese Nachweise gingen verloren.")


def downgrade() -> None:
    _refuse_lossy_downgrade(op.get_bind())
    with op.batch_alter_table('email_dispatches', schema=None) as batch_op:
        batch_op.drop_column('delivered_to_client')

    with op.batch_alter_table('dispatch_authorizations', schema=None) as batch_op:
        batch_op.alter_column('recipient_email',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)

    with op.batch_alter_table('checklists', schema=None) as batch_op:
        batch_op.drop_column('void_reason')
        batch_op.drop_column('voided_by_name')
        batch_op.drop_column('voided_by_user_id')
        batch_op.drop_column('voided_at')

    with op.batch_alter_table('dispatch_outcomes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dispatch_outcomes_dispatch_id'))

    op.drop_table('dispatch_outcomes')
