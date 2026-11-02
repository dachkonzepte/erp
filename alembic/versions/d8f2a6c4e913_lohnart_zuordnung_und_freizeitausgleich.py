"""lohnart_zuordnung_und_freizeitausgleich -- Zuordnung für den DATEV-Export, Kategorie Freizeitausgleich (seit 1.9.169, Lohn L1a, Punkt 4)

Neu: Tabelle lohnart_zuordnungen (Schlüssel, Kennzeichen, Lohnart, Monatszeile). Die festen Zeilen, vorbelegt nach E7, legt beim Start
app.grunddaten.anlegen() an (Regel 23), nicht diese Migration.

Bestand: Freizeitausgleich wird eine eigene Kategorie (Entscheidung Tobias; bis 1.9.168 Art „Freizeitausgleich“ in der Kategorie Urlaub,
Festlegung 1.9.153 Nr. 1). Abwesenheiten und Anträge mit Art „Freizeitausgleich“ (ohne Groß- und Kleinschreibung, ohne Leerzeichen
außen) und Kategorie „urlaub“ bekommen die Kategorie „freizeitausgleich“ -- sonst zählten sie im Urlaubskonto (L2) als Urlaub. Eine andere
Kategorie mit dieser Art (Altbestand, Widerspruch) bleibt, scripts/pruefe_abwesenheiten.py nennt sie.

downgrade(): jede Abwesenheit und jeder Antrag der Kategorie „freizeitausgleich“ zurück auf „urlaub“, Tabelle weg.

Revision ID: d8f2a6c4e913
Revises: c5a9e3f71d28
Create Date: 2026-11-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8f2a6c4e913'
down_revision = 'c5a9e3f71d28'
branch_labels = None
depends_on = None

TABELLEN = ("employee_absences", "employee_absence_requests")


def freizeitausgleich_umstellen(bind) -> int:
    n = 0
    for tabelle in TABELLEN:
        n += bind.execute(sa.text(f"UPDATE {tabelle} SET absence_category = 'freizeitausgleich' "
                                  "WHERE absence_category = 'urlaub' AND LOWER(TRIM(absence_type)) = 'freizeitausgleich'")).rowcount
    return n


def freizeitausgleich_zurueck(bind) -> int:
    n = 0
    for tabelle in TABELLEN:
        n += bind.execute(sa.text(f"UPDATE {tabelle} SET absence_category = 'urlaub' WHERE absence_category = 'freizeitausgleich'")).rowcount
    return n


def upgrade() -> None:
    op.create_table(
        "lohnart_zuordnungen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schluessel", sa.String(length=120), nullable=False),
        sa.Column("kennzeichen", sa.String(length=2), nullable=True),
        sa.Column("lohnart", sa.String(length=4), nullable=True),
        sa.Column("monatszeile", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schluessel", name="uq_lohnart_zuordnung_schluessel"),
    )
    freizeitausgleich_umstellen(op.get_bind())


def downgrade() -> None:
    freizeitausgleich_zurueck(op.get_bind())
    op.drop_table("lohnart_zuordnungen")
