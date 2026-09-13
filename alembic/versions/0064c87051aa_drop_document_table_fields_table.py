"""drop document_table_fields table

Revision ID: 0064c87051aa
Revises: 5c8715dba230
Create Date: 2026-09-12 07:59:24.062618

Teil von Schritt 3 des Aufräumens nach dem PDF-Umbau (CLAUDE.md "Gemeinsamer Dokumenttyp"): mit
app/document_table_fields.py, app/quote_layout_pdf.py und app/templates/document_layout_editor.html
entfernt, ist diese Tabelle vollständig verwaist -- ausschließlich für "quote" befüllt (bestätigt
vor dem Schreiben dieser Migration), von keinem verbleibenden Code mehr gelesen oder beschrieben.

downgrade() stellt neben der Tabellenstruktur auch die zuletzt tatsächlich vorhandenen 35 Zeilen
wieder her (alle document_type='quote', is_custom=0 -- nie ein eigenes Feld angelegt) --
insbesondere die echte, im Firmenkopf vorgenommene Anpassung (nur "Firmenname" sichtbar, alle
übrigen Felder inkl. Straße/PLZ-Ort/Telefon/E-Mail/Webseite ausgeblendet, passend zu vorgedrucktem
Briefpapier). Ohne die inzwischen ebenfalls entfernten Python-Dateien liest zwar nichts mehr
diese Zeilen -- ein Downgrade, das gemeinsam mit aus einem Backup wiederhergestellten Dateien
läuft (siehe CLAUDE.md, backup_windows.ps1), soll trotzdem den exakten letzten Stand vorfinden,
nicht nur leere Standardwerte.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0064c87051aa'
down_revision = '5c8715dba230'
branch_labels = None
depends_on = None

_ROWS = [
    ("company_header", "company_name", "Firmenname", True, 10, "2026-09-05 09:26:14.326934"),
    ("company_header", "street", "Straße", False, 20, "2026-09-05 09:26:14.326939"),
    ("company_header", "city_line", "PLZ/Ort", False, 30, "2026-09-05 09:26:14.326941"),
    ("company_header", "phone", "Telefon", False, 40, "2026-09-05 09:26:14.326942"),
    ("company_header", "email", "E-Mail", False, 50, "2026-09-05 09:26:14.326945"),
    ("company_header", "website", "Webseite", False, 60, "2026-09-05 09:26:14.326946"),
    ("company_header", "managing_director", "Geschäftsführung", False, 70, "2026-09-05 09:26:14.326947"),
    ("company_header", "tax_number", "Steuernummer", False, 80, "2026-09-05 09:26:14.326949"),
    ("company_header", "vat_id", "USt-IdNr.", False, 90, "2026-09-05 09:26:14.326950"),
    ("customer_address", "customer_name", "Name", True, 10, "2026-09-05 09:26:24.060993"),
    ("customer_address", "contact_person", "Ansprechpartner", True, 20, "2026-09-05 09:26:24.060997"),
    ("customer_address", "street", "Straße", True, 30, "2026-09-05 09:26:24.060999"),
    ("customer_address", "city_line", "PLZ/Ort", True, 40, "2026-09-05 09:26:24.061000"),
    ("items_table", "oz", "OZ", True, 10, "2026-09-05 08:58:06.459433"),
    ("items_table", "leistung", "Leistung", True, 20, "2026-09-05 08:58:06.459436"),
    ("items_table", "menge", "Menge", True, 30, "2026-09-05 08:58:06.459438"),
    ("items_table", "eh", "EH", True, 40, "2026-09-05 08:58:06.459439"),
    ("items_table", "ep", "EP", True, 50, "2026-09-05 08:58:06.459440"),
    ("items_table", "gp", "GP", True, 60, "2026-09-05 08:58:06.459441"),
    ("meta_table", "quote_number", "Angebotsnr.", True, 10, "2026-09-05 08:57:51.004370"),
    ("meta_table", "quote_date", "Datum", True, 20, "2026-09-05 08:57:51.004375"),
    ("meta_table", "valid_until", "Gültig bis", True, 30, "2026-09-05 08:57:51.004377"),
    ("meta_table", "project_number", "Projektnr.", True, 40, "2026-09-05 08:57:51.004378"),
    ("meta_table", "project_name", "Projekt", False, 50, "2026-09-05 08:57:51.004379"),
    ("meta_table", "customer_name", "Kunde", False, 60, "2026-09-05 08:57:51.004381"),
    ("meta_table", "property_name", "Objekt", False, 70, "2026-09-05 08:57:51.004382"),
    ("meta_table", "contact_person", "Ansprechpartner", True, 80, "2026-09-05 08:57:51.004383"),
    ("meta_table", "caseworker", "Bearbeiter", False, 90, "2026-09-05 08:57:51.004384"),
    ("object_address", "property_name", "Objektbezeichnung", True, 10, "2026-09-05 09:26:49.118129"),
    ("object_address", "street", "Straße", True, 20, "2026-09-05 09:26:49.118131"),
    ("object_address", "city_line", "PLZ/Ort", True, 30, "2026-09-05 09:26:49.118132"),
    ("totals", "net_total", "Nettosumme", True, 10, "2026-09-05 08:58:10.347660"),
    ("totals", "vat_total", "zzgl. MwSt.", True, 20, "2026-09-05 08:58:10.347664"),
    ("totals", "optional_total", "Optionale Positionen (nicht enthalten)", True, 30, "2026-09-05 08:58:10.347665"),
    ("totals", "gross_total", "Angebotssumme brutto", True, 40, "2026-09-05 08:58:10.347666"),
]


def upgrade() -> None:
    with op.batch_alter_table('document_table_fields', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_table_fields_block_type'))
        batch_op.drop_index(batch_op.f('ix_document_table_fields_document_type'))

    op.drop_table('document_table_fields')


def downgrade() -> None:
    op.create_table('document_table_fields',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('document_type', sa.VARCHAR(length=20), nullable=False),
    sa.Column('block_type', sa.VARCHAR(length=30), nullable=False),
    sa.Column('field_key', sa.VARCHAR(length=50), nullable=False),
    sa.Column('label', sa.VARCHAR(length=120), nullable=False),
    sa.Column('is_custom', sa.BOOLEAN(), nullable=False),
    sa.Column('custom_value', sa.TEXT(), nullable=True),
    sa.Column('visible', sa.BOOLEAN(), nullable=False),
    sa.Column('sort_order', sa.INTEGER(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_table_fields', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_table_fields_document_type'), ['document_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_table_fields_block_type'), ['block_type'], unique=False)

    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO document_table_fields "
        "(document_type, block_type, field_key, label, is_custom, custom_value, visible, sort_order, created_at) "
        "VALUES ('quote', :block_type, :field_key, :label, :is_custom, NULL, :visible, :sort_order, :created_at)"
    ), [
        {"block_type": bt, "field_key": fk, "label": label, "is_custom": False, "visible": visible, "sort_order": sort_order, "created_at": created_at}
        for bt, fk, label, visible, sort_order, created_at in _ROWS
    ])
