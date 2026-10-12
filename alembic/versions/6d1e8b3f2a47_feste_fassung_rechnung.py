"""feste_fassung_rechnung -- das PDF einer Rechnung entsteht beim Festschreiben und liegt ab dann in der Ablage (seit 1.8.82, R4a
Punkt 1)

- invoices.pdf_document_id (FK sent_documents): die feste Fassung, gesetzt im selben Commit wie das Festschreiben.

Ändert keine vorhandenen Daten: Rechnungen, die vor 1.8.82 festgeschrieben wurden, behalten keine feste Fassung (leer) und kommen
wie bisher ab dem ersten Versand aus der Ablage (app/sent_documents.py::frozen_version()).

downgrade(): verweigert, solange eine Rechnung eine feste Fassung trägt -- der Rückweg verlöre den Verweis, das PDF entstünde bis
zum ersten Versand wieder neu (mit dem Briefkopf von heute).

Revision ID: 6d1e8b3f2a47
Revises: a4c9e2f7b815
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d1e8b3f2a47'
down_revision = 'a4c9e2f7b815'
branch_labels = None
depends_on = None

FK_PDF_DOCUMENT = "fk_invoices_pdf_document_id"


def upgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pdf_document_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(FK_PDF_DOCUMENT, 'sent_documents', ['pdf_document_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()
    fixed = bind.execute(sa.text("SELECT COUNT(*) FROM invoices WHERE pdf_document_id IS NOT NULL")).scalar()
    if fixed:
        raise RuntimeError(f"Downgrade verweigert: {fixed} Rechnungen mit fester Fassung -- der Verweis ginge verloren.")
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_constraint(FK_PDF_DOCUMENT, type_='foreignkey')
        batch_op.drop_column('pdf_document_id')
