"""rechnung_rundungsregel -- invoices.rounding_rule, kaufmännisches Runden (seit 1.8.11)

Neue Spalte invoices.rounding_rule (String(20), nullable). "half_up": Positionsbeträge, USt und
Skonto dieser Rechnung werden kaufmännisch auf den Cent gerundet (app/invoices.py). Leer: Rechnung
von vor 1.8.11, sie wird genau wie bisher gerechnet (USt ungerundet, gerundet erst beim Formatieren,
halb-gerade), damit der Nachdruck einer versendeten Rechnung dasselbe Dokument ergibt (GoBD,
CLAUDE.md Regel 5). Kein Betrag wird neu berechnet oder geschrieben.

upgrade(): Spalte anlegen, danach offene Entwürfe auf "half_up" setzen, sie sind noch nicht
versendet. Ausgenommen sind Storno-Entwürfe: Sie spiegeln eine bereits versendete Rechnung und
rechnen nach deren Regel (create_storno_draft() übernimmt sie seither ausdrücklich); eine vor
1.8.11 versendete Rechnung hat keine Regel, ihr Storno-Entwurf also auch nicht.
downgrade(): Spalte entfernen. Vorher gab es nur das alte Rechnen, mehr Zustand ist nicht
wiederherzustellen.

Nullable, deshalb kein server_default nötig (Regel 1 gilt für NOT NULL). Das UPDATE läuft über
sa.table()/sa.update() statt rohem SQL (dialektneutral). tests/test_v315_commercial_rounding.py
lädt diese Datei und ruft mark_open_drafts() direkt auf (Muster CLAUDE.md "Eine Migrationsdatei
selbst testen").

Revision ID: 7e3c1b9a5d24
Revises: 349704eab07d
Create Date: 2026-09-29 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e3c1b9a5d24'
down_revision = '349704eab07d'
branch_labels = None
depends_on = None


def mark_open_drafts(bind) -> int:
    """Setzt rounding_rule="half_up" für jeden Rechnungsentwurf außer Storno-Entwürfen. Gibt die
    Zahl der geänderten Zeilen zurück."""
    invoices = sa.table("invoices", sa.column("status", sa.String), sa.column("invoice_type", sa.String),
                        sa.column("rounding_rule", sa.String))
    result = bind.execute(
        sa.update(invoices)
        .where(invoices.c.status == "entwurf", invoices.c.invoice_type != "storno")
        .values(rounding_rule="half_up")
    )
    return result.rowcount


def upgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rounding_rule', sa.String(length=20), nullable=True))
    mark_open_drafts(op.get_bind())


def downgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('rounding_rule')
