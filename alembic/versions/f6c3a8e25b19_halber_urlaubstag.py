"""halber_urlaubstag -- Urlaub als halber Tag (seit 1.9.171, Lohn L1a, Punkt 6)

employee_absences.halber_tag und employee_absence_requests.halber_tag (NOT NULL, server_default false): ein Tag Urlaub mit halber Sollzeit,
zählt 0,5 Tag. Der Bestand bleibt ganz (false). Dass der 24.12. und der 31.12. an Wochentagen je 0,5 Tag Urlaub zählen, rechnet
app/sollzeit.py aus dem Datum, ohne Spalte.

downgrade(): beide Spalten weg -- ein halber Tag wird dann wieder ein ganzer.

Revision ID: f6c3a8e25b19
Revises: e4b7d1a93c56
Create Date: 2026-11-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6c3a8e25b19'
down_revision = 'e4b7d1a93c56'
branch_labels = None
depends_on = None

TABELLEN = ("employee_absences", "employee_absence_requests")


def upgrade() -> None:
    for tabelle in TABELLEN:
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.add_column(sa.Column("halber_tag", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    for tabelle in reversed(TABELLEN):
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.drop_column("halber_tag")
