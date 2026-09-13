"""continuation_header block for quote

Revision ID: ab5eef23f9ed
Revises: 5149d369dbb6
Create Date: 2026-09-11 15:33:45.326833

Reine Daten-Migration, kein Schema-Wechsel -- Muster von 257fb2967c93 (1.3.7, dieselbe
Ergänzung damals für "default"), hier für "quote". Der neue, parallele Angebots-Renderer
(app/quote_framed_pdf.py, seit 1.3.13) nutzt render_framed_pdf() und damit denselben
continuation_header-Mechanismus wie Mahnung/Rechnung/Auftrag/Einsatzbericht -- ensure_default_
layout()/DEFAULT_QUOTE_LAYOUT seedet den neuen vierten Baustein aber nur für eine KOMPLETT
frische Installation automatisch (kein Rückfall-Seeding auf "fehlt nur ein einzelner
block_type"). Diese Migration ergänzt ihn deshalb explizit für die bereits bestehenden zehn
"quote"-Zeilen, ohne sie anzufassen. Andere Dokumenttypen bleiben unberührt.

Position/Größe wie DEFAULT_QUOTE_LAYOUT (12mm/4mm, derselbe generische Standardwert wie
DEFAULT_SHARED_LAYOUT seit 1.3.12) -- die bereits gesäte Zeile in der echten Datenbank wird
zusätzlich per update_layout_block() auf den für das echte Briefpapier gemessenen Wert (34mm)
korrigiert, siehe CLAUDE.md "Einsatzbericht"/"Gemeinsamer Dokumenttyp": dasselbe, mit ~30,8mm
Kopfgrafik gemessene Briefpapier wie bei "default".
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab5eef23f9ed'
down_revision = '5149d369dbb6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        """
        INSERT INTO document_layout_blocks
            (document_type, block_type, label, x_mm, y_mm, width_mm, height_mm,
             font_size, font_weight, text_align, visible, sort_order, created_at, updated_at)
        SELECT
            'quote', 'continuation_header', 'Wiederholungszeile (Folgeseiten)',
            18, 12, 176, 4, 8, 'normal', 'left', 1, 110, datetime('now'), datetime('now')
        WHERE EXISTS (SELECT 1 FROM document_layout_blocks WHERE document_type = 'quote')
          AND NOT EXISTS (
              SELECT 1 FROM document_layout_blocks
              WHERE document_type = 'quote' AND block_type = 'continuation_header'
          )
        """
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM document_layout_blocks WHERE document_type = 'quote' AND block_type = 'continuation_header'"
    ))
