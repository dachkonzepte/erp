"""portal_kopien -- Weckruf an portal_freigaben und Fehlergrund „fehlt“ für die Kopien des Kundenportals (seit 1.11.33, Stufe P2b)

Der Postbote legt ab P2b die Kopien der freigegebenen Unterlagen an (app/portal_kopien.py). Dafür:
- ein Auslöser auf Anweisungsebene an portal_freigaben (nach INSERT und nach UPDATE von zurueckgenommen_am): NOTIFY portal_freigabe ohne Inhalt --
  nur unter PostgreSQL, Text wörtlich aus app/portal/weckruf.py; die Funktion für alle entzogen;
- ein weiteres festes Wort für kopie_fehler: „fehlt“ (Quelle oder ihre Datei fehlt). Bisher steht in der Spalte nichts (erst P2b schreibt sie).
Keine Daten geändert.

downgrade(): Auslöser und Funktion weg, die Prüfung wieder ohne „fehlt“ -- vorher jede Zeile mit „fehlt“ wieder ohne Fehler (der Postbote versucht sie
dann noch einmal); das sind nur Zeilen, die P2b selbst geschrieben hat.

Revision ID: a7c3e9f1d2b4
Revises: f2b7d4a9c1e3
Create Date: 2026-11-26

"""
import re

from alembic import op


# revision identifiers, used by Alembic.
revision = 'a7c3e9f1d2b4'
down_revision = 'f2b7d4a9c1e3'
branch_labels = None
depends_on = None

CHECKS = {
    'ck_portal_freigabe_kopie_fehler': "kopie_fehler IS NULL OR kopie_fehler IN ('zu_gross', 'nicht_lesbar', 'falscher_typ', 'pruefsumme', 'abbruch', 'fehlt')",
}
KOPIE_FEHLER_VORHER = "kopie_fehler IS NULL OR kopie_fehler IN ('zu_gross', 'nicht_lesbar', 'falscher_typ', 'pruefsumme', 'abbruch')"

ANWEISUNGEN = (
    "CREATE OR REPLACE FUNCTION portal_freigabe_geweckt() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nBEGIN\n  PERFORM pg_notify('portal_freigabe', '');\n  RETURN NULL;\nEND\n$$",
    'CREATE OR REPLACE TRIGGER portal_freigabe_geweckt AFTER INSERT OR UPDATE OF zurueckgenommen_am ON portal_freigaben\nFOR EACH STATEMENT EXECUTE FUNCTION portal_freigabe_geweckt()',
    'REVOKE ALL ON FUNCTION portal_freigabe_geweckt() FROM PUBLIC',
)


def _schema() -> str:
    schema = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar()
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema or ""):
        raise RuntimeError("Ungültiges Schema für die Funktionen des Kundenportals.")
    return schema


def upgrade() -> None:
    with op.batch_alter_table('portal_freigaben') as batch_op:
        batch_op.drop_constraint('ck_portal_freigabe_kopie_fehler', type_='check')
        batch_op.create_check_constraint('ck_portal_freigabe_kopie_fehler', CHECKS['ck_portal_freigabe_kopie_fehler'])
    if op.get_bind().dialect.name != "postgresql":
        return
    schema = _schema()
    for anweisung in ANWEISUNGEN:
        op.get_bind().exec_driver_sql(anweisung.replace("@SCHEMA@", schema))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.get_bind().exec_driver_sql("DROP TRIGGER IF EXISTS portal_freigabe_geweckt ON portal_freigaben")
        op.get_bind().exec_driver_sql("DROP FUNCTION IF EXISTS portal_freigabe_geweckt()")
    op.get_bind().exec_driver_sql("UPDATE portal_freigaben SET kopie_fehler = NULL WHERE kopie_fehler = 'fehlt'")
    with op.batch_alter_table('portal_freigaben') as batch_op:
        batch_op.drop_constraint('ck_portal_freigabe_kopie_fehler', type_='check')
        batch_op.create_check_constraint('ck_portal_freigabe_kopie_fehler', KOPIE_FEHLER_VORHER)
