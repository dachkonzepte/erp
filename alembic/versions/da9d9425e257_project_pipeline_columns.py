"""project pipeline columns

Revision ID: da9d9425e257
Revises: f803985ebc2f
Create Date: 2026-09-16 19:17:18.476605

Fundament der Projekt-Pipeline (seit 1.3.70, siehe CLAUDE.md "Projekt-Pipeline"): neue
Stammdatentabelle project_pipeline_columns (Muster TaskColumn -- key/label/sort_order, aber
OHNE is_done, siehe app/models.py::ProjectPipelineColumn für die Begründung) plus die neue
Spalte projects.pipeline_column_id -- eine von Project.status VOLLSTÄNDIG unabhängige zweite
Achse (siehe dort), NOT NULL, damit kein Projekt je ohne Kanban-Spalte entsteht.

Reihenfolge wegen Regel 1 (server_default bei NOT-NULL-Spalten auf bestehenden Tabellen):
pipeline_column_id kann nicht direkt NOT NULL angelegt werden, da der Fremdschlüssel auf eine
erst in DIESER Migration befüllte Tabelle zeigt -- ein server_default auf eine konkrete ID wäre
fragil (Muster 9137945e8785). Stattdessen: Spalte nullable anlegen, aus der ERSTEN Spalte
(niedrigste sort_order, "Neu") befüllen -- ALLE Bestandsprojekte wandern dorthin, der Betrieb
sortiert sie danach selbst per Ziehen ein (ausdrückliche Nutzervorgabe) -- danach erst NOT NULL
setzen.

Vor dem Schreiben gegen die echte, lokale Datenbank geprüft (wie bei jeder Migration mit echtem
Bestandsdaten-Bezug verlangt): 8 Projekte in `projects`, keine davon hat heute schon eine
Pipeline-Spalte (die Tabelle existiert noch nicht) -- alle 8 werden auf die neu gesäte
"Neu"-Spalte gesetzt.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da9d9425e257'
down_revision = 'f803985ebc2f'
branch_labels = None
depends_on = None


# Wortgleich zu app/project_pipeline_columns.py::DEFAULT_COLUMNS -- bewusst hier dupliziert statt
# importiert (Migrationen bleiben vom Anwendungscode unabhängig, ein künftiger Code-Refactor darf
# eine bereits gelaufene Migration nicht rückwirkend verändern, Muster aller bisherigen
# Daten-Migrationen dieses Projekts, z. B. 9137945e8785).
DEFAULT_COLUMNS = [
    (0, "neu", "Neu"),
    (10, "in_bearbeitung", "In Bearbeitung"),
    (20, "wartet", "Wartet"),
    (30, "abgeschlossen", "Abgeschlossen"),
]

_project_pipeline_columns_table = sa.table(
    'project_pipeline_columns',
    sa.column('id', sa.Integer), sa.column('key', sa.String), sa.column('label', sa.String),
    sa.column('sort_order', sa.Integer), sa.column('created_at', sa.DateTime),
)
_projects_table = sa.table('projects', sa.column('id', sa.Integer), sa.column('pipeline_column_id', sa.Integer))


def _seed_default_columns(bind, now: datetime) -> None:
    for sort_order, key, label in DEFAULT_COLUMNS:
        bind.execute(_project_pipeline_columns_table.insert().values(
            key=key, label=label, sort_order=sort_order, created_at=now,
        ))


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table('project_pipeline_columns',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=40), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key', name='uq_project_pipeline_column_key'),
    )

    _seed_default_columns(bind, datetime.utcnow())
    first_column_id = bind.execute(
        sa.select(_project_pipeline_columns_table.c.id)
        .order_by(_project_pipeline_columns_table.c.sort_order, _project_pipeline_columns_table.c.id)
        .limit(1)
    ).scalar_one()

    # pipeline_column_id zunächst NULLABLE -- siehe Moduldocstring oben für die Begründung.
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pipeline_column_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_projects_pipeline_column_id'), ['pipeline_column_id'], unique=False)
        batch_op.create_foreign_key('fk_projects_pipeline_column_id', 'project_pipeline_columns', ['pipeline_column_id'], ['id'])

    bind.execute(_projects_table.update().values(pipeline_column_id=first_column_id))

    # Jede Zeile hat jetzt einen Wert (die erste, niedrigste Spalte) -- sicher auf NOT NULL.
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.alter_column('pipeline_column_id', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_constraint('fk_projects_pipeline_column_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_projects_pipeline_column_id'))
        batch_op.drop_column('pipeline_column_id')

    op.drop_table('project_pipeline_columns')
