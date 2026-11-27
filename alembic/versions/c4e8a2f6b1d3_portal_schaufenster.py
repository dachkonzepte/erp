"""portal_schaufenster -- Schaufenster des Kundenportals: Zahlstand der Rechnungen, feste Einsatztage, Stand (seit 1.11.41, Stufe P2d)

Das ERP rechnet, die Funktionen der Datenbank lesen nur (Bauplan P2, B3): drei Tabellen, die der Postbote je Kunde mit Portal neu füllt
(app/portal_schaufenster.py) -- portal_rechnungen (je festgeschriebener Rechnung Zustand, offener Betrag, überfällig), portal_termine (Folgen fester
Baustellentage ohne Namen), portal_schaufenster (Stand je Kunde). Dazu unter PostgreSQL je Tabelle aus app/portal/weckruf.py::TABELLEN_SCHAUFENSTER ein
Auslöser auf Anweisungsebene: NOTIFY portal_schaufenster ohne Inhalt; Text wörtlich aus app/portal/weckruf.py, die Funktion für alle entzogen.
Keine Daten geändert (die Tabellen sind neu und leer; der Postbote füllt sie).

downgrade(): Auslöser, Funktion und die drei Tabellen weg -- sie lassen sich aus dem ERP jederzeit neu rechnen.

Revision ID: c4e8a2f6b1d3
Revises: a7c3e9f1d2b4
Create Date: 2026-11-27

"""
import re

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c4e8a2f6b1d3'
down_revision = 'a7c3e9f1d2b4'
branch_labels = None
depends_on = None

TABELLEN = ('invoices', 'invoice_items', 'invoice_deductions', 'payments', 'payment_allocations', 'orders', 'projects', 'customers', 'planning_slots', 'planning_slot_employees')
ANWEISUNGEN = (
    "CREATE OR REPLACE FUNCTION portal_schaufenster_geweckt() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nBEGIN\n  PERFORM pg_notify('portal_schaufenster', '');\n  RETURN NULL;\nEND\n$$",
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON invoices\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON invoice_items\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON invoice_deductions\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON payments\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON payment_allocations\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON orders\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON projects\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON customers\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON planning_slots\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'CREATE OR REPLACE TRIGGER portal_schaufenster_geweckt AFTER INSERT OR UPDATE OR DELETE ON planning_slot_employees\nFOR EACH STATEMENT EXECUTE FUNCTION portal_schaufenster_geweckt()',
    'REVOKE ALL ON FUNCTION portal_schaufenster_geweckt() FROM PUBLIC',
)


def _schema() -> str:
    schema = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar()
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema or ""):
        raise RuntimeError("Ungültiges Schema für die Funktionen des Kundenportals.")
    return schema


def upgrade() -> None:
    op.create_table(
        'portal_rechnungen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('nummer', sa.String(length=50), nullable=False),
        sa.Column('art_text', sa.String(length=120), nullable=False),
        sa.Column('datum', sa.Date(), nullable=False),
        sa.Column('faellig', sa.Date(), nullable=True),
        sa.Column('brutto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('zustand', sa.String(length=20), nullable=False),
        sa.Column('offen', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
        sa.Column('ueberfaellig', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('bezug_nummer', sa.String(length=50), nullable=True),
        sa.Column('stand_am', sa.DateTime(), nullable=False),
        sa.CheckConstraint("zustand IN ('offen', 'teilweise_bezahlt', 'bezahlt', 'guthaben', 'enthalten', 'storniert', 'storno', 'ohne')", name='ck_portal_rechnung_zustand'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_id', name='uq_portal_rechnung_invoice'),
    )
    op.create_index(op.f('ix_portal_rechnungen_customer_id'), 'portal_rechnungen', ['customer_id'], unique=False)
    op.create_table(
        'portal_termine',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('von', sa.Date(), nullable=False),
        sa.Column('bis', sa.Date(), nullable=False),
        sa.Column('stand_am', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portal_termine_customer_id'), 'portal_termine', ['customer_id'], unique=False)
    op.create_table(
        'portal_schaufenster',
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('stand_am', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('customer_id'),
    )
    if op.get_bind().dialect.name != "postgresql":
        return
    schema = _schema()
    for anweisung in ANWEISUNGEN:
        op.get_bind().exec_driver_sql(anweisung.replace("@SCHEMA@", schema))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for tabelle in TABELLEN:
            op.get_bind().exec_driver_sql(f"DROP TRIGGER IF EXISTS portal_schaufenster_geweckt ON {tabelle}")
        op.get_bind().exec_driver_sql("DROP FUNCTION IF EXISTS portal_schaufenster_geweckt()")
    op.drop_table('portal_schaufenster')
    op.drop_index(op.f('ix_portal_termine_customer_id'), table_name='portal_termine')
    op.drop_table('portal_termine')
    op.drop_index(op.f('ix_portal_rechnungen_customer_id'), table_name='portal_rechnungen')
    op.drop_table('portal_rechnungen')
