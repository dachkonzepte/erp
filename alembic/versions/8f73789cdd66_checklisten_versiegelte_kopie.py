"""checklisten_versiegelte_kopie -- Unterschrift versiegelt abschnittsweise (seit 1.8.14)

Eine Spalte an checklist_attachments, nullable, keine Datenänderung beim Upgrade:
- sealed_content: feste Kopie des Inhalts, den eine Unterschrift versiegelt (kanonisches JSON:
  Fassung, Feldschlüssel, Antworten, Prüfsummen der Fotos -- nur die Felder VOR der Unterschrift).
  content_sha256 ist ab 1.8.14 die SHA-256 genau dieser Zeichenkette.

Bestehende Unterschriften bekommen keine Kopie nachgetragen (der Inhalt im Moment ihrer
Unterschrift ist nicht nachweisbar bekannt). NULL heißt "vor 1.8.14 unterschrieben"; solche
Unterschriften versiegeln weiterhin die GANZE Checkliste, wie es beim Unterschreiben galt
(app/checklists.py::sealed_field_ids()).

downgrade(): entfernt die Spalte. Danach tragen 1.8.14-Unterschriften eine Prüfsumme ohne die
Kopie, über die sie gerechnet wurde; die 1.8.13-Logik sperrt ohnehin die ganze Checkliste.

Revision ID: 8f73789cdd66
Revises: 9e1377e27340
Create Date: 2026-09-30 14:05:11.402133

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f73789cdd66'
down_revision = '9e1377e27340'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('checklist_attachments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sealed_content', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('checklist_attachments', schema=None) as batch_op:
        batch_op.drop_column('sealed_content')
