"""outlook_loeschauftraege -- ein Termin, der aus einem Postfach noch gelöscht werden muss (seit 1.9.160, Stufe 6, R2, Punkt 4)

Reine neue Tabelle, leer. downgrade() entfernt sie; was darin noch offen ist, bleibt in Outlook liegen und kommt mit der alten Fassung beim nächsten Lauf als neu zurück.

Revision ID: 9d4b6f02a7c1
Revises: 7c2e9b41d3a8
Create Date: 2026-10-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d4b6f02a7c1'
down_revision = '7c2e9b41d3a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outlook_delete_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("postfach", sa.String(length=255), nullable=False),
        sa.Column("outlook_event_id", sa.String(length=255), nullable=False),
        sa.Column("last_error_type", sa.String(length=120), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("postfach", "outlook_event_id", name="uq_outlook_delete_order"),
    )


def downgrade() -> None:
    op.drop_table("outlook_delete_orders")
