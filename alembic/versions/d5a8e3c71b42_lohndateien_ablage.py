"""lohndateien_ablage -- jede erzeugte Lohndatei bleibt auf dem Server (seit 1.9.226, Lohn L1b, Punkt 3)

- lohndateien: Monat (der Erste), Dateiname, die Bytes (inhalt), SHA-256, Größe, erzeugt am (naives UTC), Konto (ohne Fremdschlüssel) und sein Name.
  Unveränderlich über die ORM-Sperre in app/models.py (kein Ändern, kein Löschen); eine neue Tabelle, kein Bestand wird berührt.

downgrade(): Tabelle weg -- die abgelegten Dateien sind dann verloren (vorher sichern).

Revision ID: d5a8e3c71b42
Revises: c7e2b94a1f60
Create Date: 2026-11-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5a8e3c71b42'
down_revision = 'c7e2b94a1f60'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lohndateien",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("monat", sa.Date(), nullable=False),
        sa.Column("dateiname", sa.String(length=80), nullable=False),
        sa.Column("inhalt", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("groesse", sa.Integer(), nullable=False),
        sa.Column("erzeugt_am", sa.DateTime(), nullable=False),
        sa.Column("erzeugt_von_user_id", sa.Integer(), nullable=True),
        sa.Column("erzeugt_von_name", sa.String(length=160), server_default="System", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lohndateien", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_lohndateien_monat"), ["monat"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("lohndateien", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lohndateien_monat"))
    op.drop_table("lohndateien")
