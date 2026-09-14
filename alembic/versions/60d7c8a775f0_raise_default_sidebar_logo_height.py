"""raise default sidebar logo height

Revision ID: 60d7c8a775f0
Revises: 4ba46163a7e8
Create Date: 2026-09-14 15:29:32.877253

Reiner server_default-Wechsel (48 -> 64, siehe CLAUDE.md "Umgestaltung der Sidebar"), kein
Schema-Umbau -- Autogenerate erzeugte hier eine leere Huelle, weil SQLite server_default-
Aenderungen nicht introspiziert/vergleicht (anders als bei einer neuen Spalte). Von Hand
nachgetragen statt die leere Huelle stehen zu lassen (siehe CLAUDE.md "Migrations-Workflow" zur
Begruendung, warum eine leere Migration in dieser Kette nicht akzeptabel ist -- hier eine andere
Ursache als beim e057d15af828-Fund, aber dieselbe Konsequenz waere es, sie leer zu lassen).
Betrifft KEINE bereits vorhandene Zeile (general_settings wird stets ueber das ORM angelegt,
dessen Python-seitiger default= bereits beim INSERT greift) -- reine Absicherung fuer den Fall
eines direkten SQL-Inserts ohne das ORM.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '60d7c8a775f0'
down_revision = '4ba46163a7e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('general_settings', schema=None) as batch_op:
        batch_op.alter_column('sidebar_logo_height_px', existing_type=sa.Integer(), server_default='64')


def downgrade() -> None:
    with op.batch_alter_table('general_settings', schema=None) as batch_op:
        batch_op.alter_column('sidebar_logo_height_px', existing_type=sa.Integer(), server_default='48')
