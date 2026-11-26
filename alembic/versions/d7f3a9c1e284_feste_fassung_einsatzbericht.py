"""feste_fassung_einsatzbericht -- das PDF eines Einsatzberichts entsteht beim Unterschreiben und liegt ab dann in der Ablage (seit 1.11.29,
Nebenbefund N3 aus dem Bauplan P2)

- service_reports.pdf_document_id (FK sent_documents): die feste Fassung, gesetzt im selben Commit wie die Unterschrift (Art „einsatzbericht“).

Ändert keine vorhandenen Daten: Berichte, die vor 1.11.29 unterschrieben wurden, behalten keine feste Fassung (leer) -- ihr PDF entsteht wie bisher bei
jedem Abruf neu. Nachträglich festgeschrieben wird nichts ohne Zustimmung des Betriebs (Entscheidung vom 26.11.2026); bis dahin erscheinen sie nicht im
Kundenportal.

downgrade(): verweigert, solange ein Bericht eine feste Fassung trägt -- der Rückweg verlöre den Verweis, das PDF entstünde wieder bei jedem Abruf neu (mit
den Namen und dem Briefkopf von heute).

Revision ID: d7f3a9c1e284
Revises: c8e2f5a1d394
Create Date: 2026-11-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7f3a9c1e284'
down_revision = 'c8e2f5a1d394'
branch_labels = None
depends_on = None

FK_PDF_DOCUMENT = "fk_service_reports_pdf_document_id"


def upgrade() -> None:
    with op.batch_alter_table('service_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pdf_document_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(FK_PDF_DOCUMENT, 'sent_documents', ['pdf_document_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()
    fixed = bind.execute(sa.text("SELECT COUNT(*) FROM service_reports WHERE pdf_document_id IS NOT NULL")).scalar()
    if fixed:
        raise RuntimeError(f"Downgrade verweigert: {fixed} Einsatzberichte mit fester Fassung -- der Verweis ginge verloren.")
    with op.batch_alter_table('service_reports', schema=None) as batch_op:
        batch_op.drop_constraint(FK_PDF_DOCUMENT, type_='foreignkey')
        batch_op.drop_column('pdf_document_id')
