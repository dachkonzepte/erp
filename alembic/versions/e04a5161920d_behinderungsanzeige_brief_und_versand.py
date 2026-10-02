"""Behinderungsanzeige: Brief und Versand (seit 1.8.40, Stufe 2b, Runde 2b-3 Teil 2)

- notice_letters: Brief an den Auftraggeber (Behinderungsanzeige, Anzeige der Wiederaufnahme) als Fassung
  je Unterschrift des Abschnitts -- eingefrorener Inhalt (JSON mit Prüfsumme) und das PDF in der Ablage.
  Eindeutig je Checkliste, Briefart und Unterschrift bzw. Fassungsnummer.
- notice_reservations: Vorbehalt als Textbaustein je Briefart und Gruppe der Vertragsgrundlage (VOB/B,
  BGB) mit "rechtlich geprüft am, durch" -- wie contract_basis_clauses; kein Seeding.
- dispatch_authorizations: Empfangsvollmacht zum Zeitpunkt des Versands, je Versand und
  empfangsbevollmächtigtem Empfänger, Kopie der Vollmacht in der Ablage.

Nichts zu übernehmen (neue Tabellen).

downgrade(): bricht ab, solange ein Brief, eine festgehaltene Vollmacht oder ein Vorbehalt mit Text
existiert -- Briefe und Vollmachten sind Nachweise zu versendeten Anzeigen, ein Vorbehalt ist ein
geprüfter Rechtstext; alle gingen mit den Tabellen verloren.

Revision ID: e04a5161920d
Revises: 07c03fe93478
Create Date: 2026-10-02 11:27:24.816711

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e04a5161920d'
down_revision = '07c03fe93478'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('notice_reservations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('letter_kind', sa.String(length=30), nullable=False),
    sa.Column('basis_group', sa.String(length=20), nullable=False),
    sa.Column('reservation_text', sa.Text(), nullable=True),
    sa.Column('reviewed_on', sa.Date(), nullable=True),
    sa.Column('reviewed_by', sa.String(length=160), nullable=True),
    sa.Column('updated_by_name', sa.String(length=160), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('letter_kind', 'basis_group', name='uq_notice_reservation')
    )
    op.create_table('dispatch_authorizations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dispatch_id', sa.Integer(), nullable=False),
    sa.Column('participant_id', sa.Integer(), nullable=False),
    sa.Column('contact_name', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=40), nullable=False),
    sa.Column('recipient_email', sa.String(length=255), nullable=False),
    sa.Column('sent_document_id', sa.Integer(), nullable=True),
    sa.Column('poa_sha256', sa.String(length=64), nullable=True),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['dispatch_id'], ['email_dispatches.id'], ),
    sa.ForeignKeyConstraint(['sent_document_id'], ['sent_documents.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dispatch_id', 'participant_id', name='uq_dispatch_authorization')
    )
    with op.batch_alter_table('dispatch_authorizations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dispatch_authorizations_dispatch_id'), ['dispatch_id'], unique=False)

    op.create_table('notice_letters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('checklist_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('signature_id', sa.Integer(), nullable=False),
    sa.Column('signature_sha256', sa.String(length=64), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('sent_document_id', sa.Integer(), nullable=False),
    sa.Column('reservation_printed', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_by_name', sa.String(length=160), server_default='System', nullable=False),
    sa.ForeignKeyConstraint(['checklist_id'], ['checklists.id'], ),
    sa.ForeignKeyConstraint(['sent_document_id'], ['sent_documents.id'], ),
    sa.ForeignKeyConstraint(['signature_id'], ['checklist_attachments.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('checklist_id', 'kind', 'signature_id', name='uq_notice_letter_signature'),
    sa.UniqueConstraint('checklist_id', 'kind', 'version_no', name='uq_notice_letter_version')
    )
    with op.batch_alter_table('notice_letters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notice_letters_checklist_id'), ['checklist_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    letters = bind.execute(sa.text("SELECT COUNT(*) FROM notice_letters")).scalar()
    authorizations = bind.execute(sa.text("SELECT COUNT(*) FROM dispatch_authorizations")).scalar()
    reservations = bind.execute(sa.text(
        "SELECT COUNT(*) FROM notice_reservations WHERE reservation_text IS NOT NULL"
    )).scalar()
    if letters or authorizations or reservations:
        raise RuntimeError(
            f"{letters} Briefe, {authorizations} beim Versand festgehaltene Vollmachten und {reservations} Vorbehalte "
            "mit Text gingen verloren. Downgrade abgebrochen."
        )
    with op.batch_alter_table('notice_letters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notice_letters_checklist_id'))

    op.drop_table('notice_letters')
    with op.batch_alter_table('dispatch_authorizations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dispatch_authorizations_dispatch_id'))

    op.drop_table('dispatch_authorizations')
    op.drop_table('notice_reservations')
