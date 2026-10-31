"""outlook_postfach_am_geraet -- ein Postfach gehört einem Konto oder einem Gerät (seit 1.9.161, Stufe 6, R2, Punkt 5)

operational_resources.outlook_mailbox (leer, eindeutig). calendar_events und outlook_series_occurrences: resource_id, owner_user_id darf leer sein, genau eines von beiden (CHECK). Bestehende Zeilen
haben alle einen Besitzer, keine ändert sich.

downgrade(): entfernt Termine und Vorkommen an Geräten (ohne Konto darf es sie vorher nicht geben), dann die Spalten. Die Termine liegen weiter im Postfach des Geräts.

Revision ID: b6e1d8f37a42
Revises: 9d4b6f02a7c1
Create Date: 2026-10-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6e1d8f37a42'
down_revision = '9d4b6f02a7c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("operational_resources") as batch_op:
        batch_op.add_column(sa.Column("outlook_mailbox", sa.String(length=255), nullable=True))
    op.create_index("ix_operational_resources_outlook_mailbox", "operational_resources", ["outlook_mailbox"], unique=True)
    for tabelle, pruefung in (("calendar_events", "ck_calendar_events_besitzer"), ("outlook_series_occurrences", "ck_outlook_series_besitzer")):
        with op.batch_alter_table(tabelle) as batch_op:
            batch_op.add_column(sa.Column("resource_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(f"fk_{tabelle}_resource_id", "operational_resources", ["resource_id"], ["id"])
            batch_op.alter_column("owner_user_id", existing_type=sa.Integer(), nullable=True)
            batch_op.create_check_constraint(pruefung, "(owner_user_id IS NULL) <> (resource_id IS NULL)")
        op.create_index(f"ix_{tabelle}_resource_id", tabelle, ["resource_id"])


def downgrade() -> None:
    for tabelle, pruefung in (("outlook_series_occurrences", "ck_outlook_series_besitzer"), ("calendar_events", "ck_calendar_events_besitzer")):
        op.execute(f"DELETE FROM {tabelle} WHERE resource_id IS NOT NULL")
        op.drop_index(f"ix_{tabelle}_resource_id", table_name=tabelle)
        with op.batch_alter_table(tabelle) as batch_op:
            batch_op.drop_constraint(pruefung, type_="check")
            batch_op.drop_constraint(f"fk_{tabelle}_resource_id", type_="foreignkey")
            batch_op.alter_column("owner_user_id", existing_type=sa.Integer(), nullable=False)
            batch_op.drop_column("resource_id")
    op.drop_index("ix_operational_resources_outlook_mailbox", table_name="operational_resources")
    with op.batch_alter_table("operational_resources") as batch_op:
        batch_op.drop_column("outlook_mailbox")
