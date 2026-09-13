"""continuation_header block for already-seeded shared layout installations

Revision ID: 257fb2967c93
Revises: 8567f75a5266
Create Date: 2026-09-11 11:05:00.000000

Reine Daten-Migration, kein Schema-Wechsel. Der neue vierte Rahmen-Baustein
"continuation_header" (Wiederholungszeile auf Folgeseiten, seit 1.3.7) wird von
ensure_default_layout()/DEFAULT_SHARED_LAYOUT nur fuer eine KOMPLETT frische Installation
automatisch geseedet (kein Rueckfall-Seeding auf "fehlt nur ein einzelner block_type").
Diese Migration ergaenzt ihn deshalb explizit fuer jede Installation, die den geteilten Satz
("default", seit 1.3.6) bereits einmal geseedet hat, ohne die drei bestehenden Zeilen
(logo/company_header/footer_text) anzufassen. "quote" bleibt unberuehrt -- das Angebot bekommt
diesen Baustein nicht, es hat seinen eigenen, unveraenderten Fortsetzungs-Mechanismus.

Dieselben Standardwerte wie in DEFAULT_SHARED_LAYOUT (app/document_layout.py): sichtbar,
Position/Groesse ohne praktische Bedeutung (die Zeile wird an fester Position gezeichnet, siehe
app/document_frame.py::CONTINUATION_HEADER_Y_MM).
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '257fb2967c93'
down_revision = '8567f75a5266'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # datetime('now') war SQLite-spezifisch (unter PostgreSQL: "Funktion datetime(unknown)
    # existiert nicht"), der rohe Boolean-Literal "1" scheiterte dort ebenfalls ("Spalte
    # »visible« hat Typ boolean, aber der Ausdruck hat Typ integer") -- beides durch gebundene
    # Parameter ersetzt (dasselbe, bereits bewaehrte Muster wie in 5c8715dba230), SQLAlchemy
    # uebersetzt Python-Werte dialektkorrekt statt roher SQL-Literale.
    op.execute(sa.text(
        """
        INSERT INTO document_layout_blocks
            (document_type, block_type, label, x_mm, y_mm, width_mm, height_mm,
             font_size, font_weight, text_align, visible, sort_order, created_at, updated_at)
        SELECT
            'default', 'continuation_header', 'Wiederholungszeile (Folgeseiten)',
            18, 8, 176, 6, 8, 'normal', 'left', :visible, 40, :now, :now
        WHERE EXISTS (SELECT 1 FROM document_layout_blocks WHERE document_type = 'default')
          AND NOT EXISTS (
              SELECT 1 FROM document_layout_blocks
              WHERE document_type = 'default' AND block_type = 'continuation_header'
          )
        """
    ).bindparams(visible=True, now=datetime.utcnow()))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM document_layout_blocks WHERE document_type = 'default' AND block_type = 'continuation_header'"
    ))
