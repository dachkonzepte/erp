"""seed reparatur wartung time entry activities

Revision ID: 2ba59ab6f30a
Revises: 6d2ca9ae3761
Create Date: 2026-09-08 17:52:36.945759

Reine Daten-Migration, keine Schema-Aenderung: ergaenzt die bereits bestehende, frei vom
Admin editierbare Auswahlliste "Zeiterfassung -- Taetigkeiten" (group_key
time_entry_activities) um "Reparatur"/"Wartung" (seit 1.2.3, Anregung aus dem
Wartungen-&-Reparaturen-Modul). app/option_settings.py::DEFAULT_OPTION_GROUPS seedet diese
Gruppe nur beim allerersten Anlegen (ensure_default_option_groups() -- "Existierende Gruppen
werden nicht wieder mit Defaults aufgefuellt") -- fuer eine bereits bestehende Installation wie
diese hier muessen die beiden neuen Werte deshalb per Migration nachgetragen werden, nicht nur
im Code ergaenzt werden. Idempotent: ueberspringt beide Werte, falls die Gruppe noch gar nicht
existiert (ganz frische Installation -- dort greift beim ersten Start ohnehin bereits die
aktualisierte DEFAULT_OPTION_GROUPS-Liste) oder falls ein Wert bereits vorhanden ist (z. B. weil
ein Admin ihn zwischenzeitlich selbst angelegt hat).
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2ba59ab6f30a'
down_revision = '6d2ca9ae3761'
branch_labels = None
depends_on = None

NEW_OPTIONS = [(90, "Reparatur", "Reparatur"), (100, "Wartung", "Wartung")]


def upgrade() -> None:
    bind = op.get_bind()
    groups = sa.table(
        "setting_option_groups", sa.column("id", sa.Integer), sa.column("group_key", sa.String),
    )
    options = sa.table(
        "setting_options", sa.column("id", sa.Integer), sa.column("group_id", sa.Integer),
        sa.column("label", sa.String), sa.column("value", sa.Text), sa.column("sort_order", sa.Integer),
        sa.column("active", sa.Boolean), sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    group_id = bind.execute(
        sa.select(groups.c.id).where(groups.c.group_key == "time_entry_activities")
    ).scalar()
    if group_id is None:
        return
    existing_labels = {
        row[0] for row in bind.execute(sa.select(options.c.label).where(options.c.group_id == group_id))
    }
    now = datetime.utcnow()
    for sort_order, label, value in NEW_OPTIONS:
        if label in existing_labels:
            continue
        bind.execute(options.insert().values(
            group_id=group_id, label=label, value=value, sort_order=sort_order, active=True, is_default=False,
            created_at=now, updated_at=now,
        ))


def downgrade() -> None:
    bind = op.get_bind()
    groups = sa.table("setting_option_groups", sa.column("id", sa.Integer), sa.column("group_key", sa.String))
    options = sa.table("setting_options", sa.column("group_id", sa.Integer), sa.column("label", sa.String))
    group_id = bind.execute(
        sa.select(groups.c.id).where(groups.c.group_key == "time_entry_activities")
    ).scalar()
    if group_id is None:
        return
    labels = [label for _, label, _ in NEW_OPTIONS]
    bind.execute(options.delete().where(options.c.group_id == group_id, options.c.label.in_(labels)))
