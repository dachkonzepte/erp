"""azubi_merkmal -- Merkmal „Azubi“ an den Lohnstammdaten (seit 1.9.224, Lohn L1b, Punkt 1)

- employee_payroll_settings.azubi (NOT NULL, server_default false): die Arbeit über der Sollzeit des Tags steht in der Lohndatei als Mehrarbeit
  (AA / 1900, app/lohndatei.py). Niemand wird automatisch Azubi -- auch nicht über den Kreis der Personalnummer (00200–00299, nur ein Hinweis)
  oder die Funktion; das Büro (Admin, Büro – Finanzen) setzt das Häkchen.

Die Zeile „Mehrarbeit Azubis“ der Zuordnung legt der Start an (app/lohnarten.py::ensure_default_lohnart_zuordnungen(), vorbelegt AA / 1900),
keine Migration dafür. Spalten des alten Exports (Zielsystem, sechs Lohnarten) bleiben unverändert stehen.

downgrade(): Spalte weg.

Revision ID: c7e2b94a1f60
Revises: a3f61c8d2b95
Create Date: 2026-11-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e2b94a1f60'
down_revision = 'a3f61c8d2b95'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("employee_payroll_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("azubi", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("employee_payroll_settings", schema=None) as batch_op:
        batch_op.drop_column("azubi")
