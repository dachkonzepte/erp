"""outlook_fehlerstatus -- HTTP-Status des letzten Fehlers je Postfach (seit 1.9.162, Stufe 6, R2, Punkt 6)

Eine neue leere Spalte: die Anzeige sagt damit, was zu tun ist (403: Gruppe ERP-Zugriff). Ein Fehler von vor dieser Version hat keinen Status, bis der nächste Lauf ihn neu setzt oder löscht.

Revision ID: e3a7c4b95d18
Revises: b6e1d8f37a42
Create Date: 2026-10-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3a7c4b95d18'
down_revision = 'b6e1d8f37a42'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outlook_calendar_sync_state", sa.Column("last_error_status", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("outlook_calendar_sync_state") as batch_op:
        batch_op.drop_column("last_error_status")
