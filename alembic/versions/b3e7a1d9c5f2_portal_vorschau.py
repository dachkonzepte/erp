"""portal_vorschau -- Vorschau eines Fotos im Kundenportal (seit 1.11.44, Stufe P2e, Teil 2; Bauplan P2, B5)

portal_freigaben.kopie_vorschau: der Name der Vorschau (längste Kante 400 px) im Ordner der Kopien, eindeutig; leer: keine. Unter PostgreSQL dazu die Funktion
portal_vorschau(sitzung, freigabe) -- liest nur, sichtbar wie die Datei (Text wörtlich aus app/portal/schaufenster.py, für alle entzogen). Das Recht des
Portals setzt portal_rechte.py --setzen (update.sh). Keine Daten geändert: Vorschauen zu vorhandenen Kopien holt der Postbote im vollen Lauf nach.

downgrade(): Funktion, Eindeutigkeit und Spalte weg -- die Dateien der Vorschauen räumt der volle Lauf des Postboten als Waisen.

Revision ID: b3e7a1d9c5f2
Revises: f8b2d6a4c9e1
Create Date: 2026-11-27

"""
import re

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b3e7a1d9c5f2'
down_revision = 'f8b2d6a4c9e1'
branch_labels = None
depends_on = None

ANWEISUNGEN_SCHAUFENSTER = (
    "CREATE OR REPLACE FUNCTION portal_vorschau(p_sitzung text, p_freigabe integer)\nRETURNS TABLE (ergebnis text, name text) LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nDECLARE\n  v_sitzung integer;\n  v_kunde integer;\nBEGIN\n  SELECT k.sitzung, k.kunde INTO v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n  IF v_sitzung IS NULL OR p_freigabe IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::text;\n    RETURN;\n  END IF;\n  IF NOT portal_sichtbar(p_freigabe, v_kunde) THEN\n    RETURN QUERY SELECT 'unbekannt'::text, NULL::text;\n    RETURN;\n  END IF;\n  RETURN QUERY SELECT (CASE WHEN f.kopie_vorschau IS NULL THEN 'keine' ELSE 'ok' END)::text, f.kopie_vorschau::text\n    FROM portal_freigaben f WHERE f.id = p_freigabe;\nEND\n$$",
    'REVOKE ALL ON FUNCTION portal_vorschau(text, integer) FROM PUBLIC',
)


def _schema() -> str:
    schema = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar()
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema or ""):
        raise RuntimeError("Ungültiges Schema für die Funktionen des Kundenportals.")
    return schema


def upgrade() -> None:
    with op.batch_alter_table('portal_freigaben') as batch_op:
        batch_op.add_column(sa.Column('kopie_vorschau', sa.String(length=80), nullable=True))
        batch_op.create_unique_constraint('uq_portal_freigabe_vorschau', ['kopie_vorschau'])
    if op.get_bind().dialect.name != "postgresql":
        return
    schema = _schema()
    for anweisung in ANWEISUNGEN_SCHAUFENSTER:
        op.get_bind().exec_driver_sql(anweisung.replace("@SCHEMA@", schema))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.get_bind().exec_driver_sql("DROP FUNCTION IF EXISTS portal_vorschau(text, integer)")
    with op.batch_alter_table('portal_freigaben') as batch_op:
        batch_op.drop_constraint('uq_portal_freigabe_vorschau', type_='unique')
        batch_op.drop_column('kopie_vorschau')
