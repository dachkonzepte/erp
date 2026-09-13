"""quote joins the shared default layout, own rows removed

Revision ID: 5c8715dba230
Revises: ab5eef23f9ed
Create Date: 2026-09-12 07:37:07.490100

Reine Daten-Migration, kein Schema-Wechsel (CLAUDE.md "Gemeinsamer Dokumenttyp"/Aufräumen nach
dem PDF-Umbau, Schritt 2). Der alte, positionsbasierte Angebots-Renderer (quote_layout_pdf.py)
ist entfernt -- "quote" braucht damit keine eigenen Zeilen in document_layout_blocks/
document_layout_backgrounds/document_page_margins mehr und nimmt seither wie jeder andere
Dokumenttyp am "default"-Rückfall teil (app/document_type_fallback.py). Vorher geprüft: die
Randwerte (top_mm/bottom_mm) sind bereits identisch zu "default" (25/32mm Seite 1, 40/32mm
Folgeseiten, seit 1.3.18/1.3.19) -- nur left_mm/right_mm bleiben geringfügig anders (17/17 statt
18/16, Gesamtbreite unverändert 176mm, nur ein 1mm-Versatz des ganzen Inhaltsblocks). Die
Briefpapier-Datei (52c12111ef7a4994b565e30f768c4a09.png) wurde per Pixelvergleich gegen
"default"s eigene Datei (8d72ece3ed7843dd8485f53c60843b20.jpg) als dieselbe Vorlage bestätigt
(mittlere Kanalabweichung < 0,5 von 255 -- reine JPEG-Kompressionsartefakte) und wird nach dieser
Migration als verwaiste Datei von der Festplatte entfernt (nicht Teil dieser Migration selbst,
siehe CLAUDE.md).

downgrade() rekonstruiert die zum Zeitpunkt dieser Migration tatsächlich in der Produktions-
datenbank vorhandenen Werte (vor dem Löschen ausgelesen) -- kein Rückgriff auf die ursprünglichen
Code-Standardwerte (DEFAULT_QUOTE_LAYOUT existierte zu diesem Zeitpunkt bereits nicht mehr im
Code), damit ein Downgrade den zuletzt aktiven, produktiv genutzten Stand wiederherstellt. Die
Briefpapier-DATEI selbst kann ein Downgrade nicht zurückholen, falls sie inzwischen von der
Festplatte gelöscht wurde -- die Zeile verweist dann auf eine fehlende Datei (derselbe Zustand,
den ein manuelles Löschen der Datei ohnehin jederzeit erzeugen könnte, kein neues Risiko).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c8715dba230'
down_revision = 'ab5eef23f9ed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM document_layout_blocks WHERE document_type = 'quote'"))
    op.execute(sa.text("DELETE FROM document_layout_backgrounds WHERE document_type = 'quote'"))
    op.execute(sa.text("DELETE FROM document_page_margins WHERE document_type = 'quote'"))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text(
        "INSERT INTO document_layout_blocks "
        "(document_type, block_type, label, x_mm, y_mm, width_mm, height_mm, content, "
        "font_size, font_weight, text_align, visible, sort_order, created_at, updated_at) VALUES "
        "('quote', :block_type, :label, :x_mm, :y_mm, :width_mm, :height_mm, NULL, "
        ":font_size, 'normal', 'left', :visible, :sort_order, :created_at, :updated_at)"
    ), [
        {"block_type": "logo", "label": "Firmenlogo", "x_mm": 155, "y_mm": 10, "width_mm": 35, "height_mm": 20, "font_size": 9.5, "visible": False, "sort_order": 10, "created_at": "2026-09-05 08:27:12.024370", "updated_at": "2026-09-05 08:27:12.024373"},
        {"block_type": "company_header", "label": "Firmenkopf", "x_mm": 18, "y_mm": 50, "width_mm": 70, "height_mm": 6.4, "font_size": 9.5, "visible": True, "sort_order": 20, "created_at": "2026-09-05 08:27:12.024375", "updated_at": "2026-09-05 08:29:49.257334"},
        {"block_type": "customer_address", "label": "Kundenadresse", "x_mm": 18, "y_mm": 60, "width_mm": 70, "height_mm": 30, "font_size": 9.5, "visible": True, "sort_order": 30, "created_at": "2026-09-05 08:27:12.024377", "updated_at": "2026-09-05 08:30:30.873107"},
        {"block_type": "meta_table", "label": "Meta-Tabelle (Angebotsnr., Datum, ...)", "x_mm": 124.4, "y_mm": 50, "width_mm": 70, "height_mm": 37.6, "font_size": 9.5, "visible": True, "sort_order": 40, "created_at": "2026-09-05 08:27:12.024380", "updated_at": "2026-09-05 08:30:14.913703"},
        {"block_type": "object_address", "label": "Objektanschrift", "x_mm": 18, "y_mm": 93, "width_mm": 90, "height_mm": 10, "font_size": 9.5, "visible": True, "sort_order": 50, "created_at": "2026-09-05 08:27:12.024381", "updated_at": "2026-09-05 09:28:10.403775"},
        {"block_type": "title_intro", "label": "Titel & Vortext", "x_mm": 18, "y_mm": 112, "width_mm": 176, "height_mm": 18, "font_size": 9.5, "visible": True, "sort_order": 60, "created_at": "2026-09-05 08:27:12.024383", "updated_at": "2026-09-05 08:31:32.903876"},
        {"block_type": "items_table", "label": "Positionsliste", "x_mm": 18, "y_mm": 132, "width_mm": 176, "height_mm": 95, "font_size": 8, "visible": True, "sort_order": 70, "created_at": "2026-09-05 08:27:12.024385", "updated_at": "2026-09-05 08:32:12.392477"},
        {"block_type": "totals", "label": "Summenblock", "x_mm": 18, "y_mm": 229, "width_mm": 176, "height_mm": 18, "font_size": 9, "visible": True, "sort_order": 80, "created_at": "2026-09-05 08:27:12.024387", "updated_at": "2026-09-05 08:32:43.935640"},
        {"block_type": "payment_tax_closing", "label": "Zahlungsbedingungen, Steuerhinweis, Schlusstexte", "x_mm": 18, "y_mm": 249, "width_mm": 176, "height_mm": 18.6, "font_size": 9.5, "visible": True, "sort_order": 90, "created_at": "2026-09-05 08:27:12.024389", "updated_at": "2026-09-05 08:32:49.296339"},
        {"block_type": "footer_text", "label": "Fußzeile (Geschäftsführung, Bank, USt-ID)", "x_mm": 18, "y_mm": 282, "width_mm": 176, "height_mm": 8, "font_size": 8, "visible": False, "sort_order": 100, "created_at": "2026-09-05 08:27:12.024390", "updated_at": "2026-09-05 08:27:51.763030"},
        {"block_type": "continuation_header", "label": "Wiederholungszeile (Folgeseiten)", "x_mm": 18, "y_mm": 34, "width_mm": 176, "height_mm": 4, "font_size": 8, "visible": True, "sort_order": 110, "created_at": "2026-09-11 13:34:10", "updated_at": "2026-09-11 13:34:26.883009"},
    ])

    conn.execute(sa.text(
        "INSERT INTO document_layout_backgrounds "
        "(document_type, page_type, stored_filename, repeat_on_every_page, uploaded_at) VALUES "
        "('quote', 'first', '52c12111ef7a4994b565e30f768c4a09.png', 1, '2026-09-10 16:11:45.701643')"
    ))

    conn.execute(sa.text(
        "INSERT INTO document_page_margins "
        "(document_type, page_type, top_mm, bottom_mm, left_mm, right_mm, updated_at) VALUES "
        "('quote', 'first', 25, 32, 17, 17, '2026-09-11 15:32:55.101907'), "
        "('quote', 'continuation', 40, 32, 17, 17, '2026-09-11 15:32:55.106462')"
    ))
