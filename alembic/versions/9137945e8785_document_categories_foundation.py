"""document categories foundation

Revision ID: 9137945e8785
Revises: 7a2b4e9f1c3d
Create Date: 2026-09-16 12:53:47.945541

Fundament der Dateiablage je Objekt (seit 1.3.62, siehe CLAUDE.md "Dateiablage je Objekt"):
neue Stammdatentabelle document_categories, ersetzt die bisherige freie Optionsgruppe
project_document_categories (siehe app/option_settings.py -- die acht Werte hier sind wortgleich
aus dieser Optionsgruppe übernommen, kein neuer Text erfunden). Migriert zusätzlich die
BESTEHENDEN Freitext-Kategorien auf customer_documents/project_documents -- category_id wird
NEU ergänzt, category (der Freitext) bleibt unverändert stehen (siehe Klassen-Docstring von
ProjectDocument/CustomerDocument in app/models.py für die Begründung).

Reihenfolge wegen Regel 1 (server_default bei NOT-NULL-Spalten auf bestehenden Tabellen):
category_id kann nicht direkt NOT NULL angelegt werden, da der Fremdschlüssel auf eine erst in
DIESER Migration befüllte Tabelle zeigt -- ein server_default auf eine konkrete ID wäre fragil
(hängt von der Einfügereihenfolge ab, bricht bei einer künftigen Umsortierung von
DEFAULT_CATEGORIES). Stattdessen: Spalte nullable anlegen, aus dem Bestand befüllen
(_resolve_category_id() unten, unabhängig testbar wie schon bei 5149d369dbb6/14b130f9c315),
danach erst NOT NULL setzen.

Vor dem Schreiben gegen die echte, lokale Datenbank geprüft (wie bei jeder Migration mit echtem
Bestandsdaten-Bezug verlangt): customer_documents ist LEER (0 Zeilen), project_documents hat
GENAU EINE Zeile mit category='Pläne' -- exakter Treffer auf den gleichnamigen Kategorie-Key,
kein einziger unklassifizierbarer String im gesamten Bestand.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9137945e8785'
down_revision = '7a2b4e9f1c3d'
branch_labels = None
depends_on = None


# Wortgleich zu app/document_categories.py::DEFAULT_CATEGORIES -- bewusst hier dupliziert statt
# importiert (Migrationen bleiben vom Anwendungscode unabhängig, ein künftiger Code-Refactor
# darf eine bereits gelaufene Migration nicht rückwirkend verändern, Muster aller bisherigen
# Daten-Migrationen dieses Projekts, z. B. 06299a5101f5).
DEFAULT_CATEGORIES = [
    (10, "Pläne", "Pläne", False, True),
    (20, "Bilder / Fotos", "Bilder / Fotos", False, True),
    (30, "Lieferscheine", "Lieferscheine", False, True),
    (40, "Aufmaß", "Aufmaß", False, True),
    (50, "Schriftverkehr", "Schriftverkehr", False, False),
    (60, "Verträge / Freigaben", "Verträge / Freigaben", True, False),
    (70, "Rechnungen / Belege", "Rechnungen / Belege", True, False),
    (80, "Sonstiges", "Sonstiges", False, False),
]

_document_categories_table = sa.table(
    'document_categories',
    sa.column('id', sa.Integer), sa.column('key', sa.String), sa.column('label', sa.String),
    sa.column('is_sensitive', sa.Boolean), sa.column('is_field_visible', sa.Boolean),
    sa.column('sort_order', sa.Integer), sa.column('active', sa.Boolean),
    sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
)


def _seed_default_categories(bind, now: datetime) -> None:
    for sort_order, key, label, is_sensitive, is_field_visible in DEFAULT_CATEGORIES:
        bind.execute(_document_categories_table.insert().values(
            key=key, label=label, is_sensitive=is_sensitive, is_field_visible=is_field_visible,
            sort_order=sort_order, active=True, created_at=now, updated_at=now,
        ))


def _resolve_category_id(category_string: str | None, category_ids_by_key: dict[str, int]) -> int:
    """Eigenständig testbare Zuordnungslogik (siehe tests/test_v266_document_categories.py) --
    exakte Übereinstimmung des Freitexts gegen den key; jeder Nichttreffer (leerer String,
    unbekannter/gelöschter Kategoriename) fällt auf "Sonstiges" zurück, NIE auf eine sichtbare
    oder sensible Kategorie -- im Zweifel gesperrt, nie offen."""
    key = (category_string or "").strip()
    if key in category_ids_by_key:
        return category_ids_by_key[key]
    return category_ids_by_key["Sonstiges"]


def _backfill_table_category_ids(bind, table) -> None:
    """table: ein sa.table()-Objekt mit mindestens id/category/category_id-Spalten -- für
    customer_documents UND project_documents identisch aufgerufen."""
    rows = bind.execute(sa.text("SELECT id, key FROM document_categories")).fetchall()
    category_ids_by_key = {row[1]: row[0] for row in rows}
    for row_id, category_string in bind.execute(sa.select(table.c.id, table.c.category)).fetchall():
        target_id = _resolve_category_id(category_string, category_ids_by_key)
        bind.execute(table.update().where(table.c.id == row_id).values(category_id=target_id))


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table('document_categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('label', sa.String(length=120), nullable=False),
    sa.Column('is_sensitive', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('is_field_visible', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='100', nullable=False),
    sa.Column('active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    with op.batch_alter_table('document_categories', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_categories_active'), ['active'], unique=False)

    _seed_default_categories(bind, datetime.utcnow())

    # category_id zunächst NULLABLE -- siehe Moduldocstring oben für die Begründung.
    with op.batch_alter_table('customer_documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_customer_documents_category_id'), ['category_id'], unique=False)
        batch_op.create_foreign_key('fk_customer_documents_category_id', 'document_categories', ['category_id'], ['id'])

    with op.batch_alter_table('project_documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_project_documents_category_id'), ['category_id'], unique=False)
        batch_op.create_foreign_key('fk_project_documents_category_id', 'document_categories', ['category_id'], ['id'])

    customer_documents_table = sa.table('customer_documents', sa.column('id', sa.Integer), sa.column('category', sa.String), sa.column('category_id', sa.Integer))
    project_documents_table = sa.table('project_documents', sa.column('id', sa.Integer), sa.column('category', sa.String), sa.column('category_id', sa.Integer))
    _backfill_table_category_ids(bind, customer_documents_table)
    _backfill_table_category_ids(bind, project_documents_table)

    # Jetzt hat jede Zeile einen Wert (echter Treffer oder "Sonstiges") -- sicher auf NOT NULL.
    with op.batch_alter_table('customer_documents', schema=None) as batch_op:
        batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table('project_documents', schema=None) as batch_op:
        batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('project_documents', schema=None) as batch_op:
        batch_op.drop_constraint('fk_project_documents_category_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_project_documents_category_id'))
        batch_op.drop_column('category_id')

    with op.batch_alter_table('customer_documents', schema=None) as batch_op:
        batch_op.drop_constraint('fk_customer_documents_category_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_customer_documents_category_id'))
        batch_op.drop_column('category_id')

    with op.batch_alter_table('document_categories', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_categories_active'))

    op.drop_table('document_categories')
