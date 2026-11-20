"""kontaktvermerke -- Kontakt vermerken an Anfrage, Projekt und Kunde (seit 1.10.10, Stufe W1c)

Neue Tabelle kontaktvermerke: genau ein Bezug (Anfrage, Projekt oder Kunde; CHECK ck_kontaktvermerk_ein_bezug), Tag und Weg des Kontakts, wann und
von welchem Konto vermerkt -- keine Spalte für einen Inhalt. Ohne Bestand.

downgrade(): bricht ab, solange ein Vermerk besteht (er ginge verloren); sonst fällt die Tabelle weg.

Revision ID: 2d8b6f4a9c13
Revises: 7e3a9c1f5b28
Create Date: 2026-11-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d8b6f4a9c13'
down_revision = '7e3a9c1f5b28'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'kontaktvermerke',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inquiry_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('kontakt_am', sa.Date(), nullable=False),
        sa.Column('weg', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.CheckConstraint("(CASE WHEN inquiry_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN project_id IS NULL THEN 0 ELSE 1 END)"
                           " + (CASE WHEN customer_id IS NULL THEN 0 ELSE 1 END) = 1", name='ck_kontaktvermerk_ein_bezug'),
        sa.ForeignKeyConstraint(['inquiry_id'], ['inquiries.id'], name='fk_kontaktvermerke_inquiry_id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_kontaktvermerke_project_id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name='fk_kontaktvermerke_customer_id'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['app_users.id'], name='fk_kontaktvermerke_created_by_user_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_kontaktvermerke_inquiry_id', 'kontaktvermerke', ['inquiry_id'], unique=False)
    op.create_index('ix_kontaktvermerke_project_id', 'kontaktvermerke', ['project_id'], unique=False)
    op.create_index('ix_kontaktvermerke_customer_id', 'kontaktvermerke', ['customer_id'], unique=False)


def downgrade() -> None:
    anzahl = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM kontaktvermerke")).scalar()
    if anzahl:
        raise RuntimeError(f"kontaktvermerke: {anzahl} Vermerke -- sie gingen mit dem Downgrade verloren.")
    op.drop_index('ix_kontaktvermerke_customer_id', table_name='kontaktvermerke')
    op.drop_index('ix_kontaktvermerke_project_id', table_name='kontaktvermerke')
    op.drop_index('ix_kontaktvermerke_inquiry_id', table_name='kontaktvermerke')
    op.drop_table('kontaktvermerke')
