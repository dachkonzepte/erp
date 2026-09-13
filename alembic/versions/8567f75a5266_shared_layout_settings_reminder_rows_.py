"""shared layout settings: reminder rows become the shared default

Revision ID: 8567f75a5266
Revises: ec3120ba11cf
Create Date: 2026-09-11 09:10:00.000000

Reine Daten-Migration, kein Schema-Wechsel: document_type bleibt eine unbeschraenkte
String(20)-Spalte auf allen drei betroffenen Tabellen (document_layout_blocks,
document_layout_backgrounds, document_page_margins) -- "default" ist nur ein weiterer,
bisher ungenutzter Wert darin (siehe app/document_type_fallback.py, CLAUDE.md "Gemeinsamer
Dokumenttyp"). Ueberfuehrt die bereits erprobten, 1.3.1/1.3.2 angepassten Mahnung-Zeilen
(oberer Rand 42mm, Logo/Firmenkopf ausgeblendet, echtes hochgeladenes Briefpapier) unveraendert
in den geteilten Satz, statt sie neu zu erfinden. Die Angebots-Zeilen (document_type='quote')
bleiben in jeder der drei Tabellen unberuehrt.

Vor dieser Migration wurden die tatsaechlichen Datenbestaende geprueft (siehe CLAUDE.md): nur
'quote' und 'reminder' hatten je Zeilen in diesen drei Tabellen, 'order'/'invoice' keine -- die
Migration muss deshalb nur den einen Fall reminder->default abdecken.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8567f75a5266'
down_revision = 'ec3120ba11cf'
branch_labels = None
depends_on = None

TABLES = ("document_layout_blocks", "document_layout_backgrounds", "document_page_margins")


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            sa.text(f"UPDATE {table} SET document_type = 'default' WHERE document_type = 'reminder'")
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            sa.text(f"UPDATE {table} SET document_type = 'reminder' WHERE document_type = 'default'")
        )
