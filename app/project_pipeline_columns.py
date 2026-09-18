"""Verwaltung der konfigurierbaren Projekt-Pipeline-Spalten (seit 1.3.70).

Eine zweite, von Project.status vollständig unabhängige Achse -- siehe
app/models.py::ProjectPipelineColumn für die volle Begründung, warum es zwei getrennte
Felder sind, kein Ersatz füreinander. Der Status bleibt automatisch/kennzahlengesteuert,
die Pipeline-Spalte ist eine frei per Ziehen gesetzte Arbeitsansicht.

Bewusst nach demselben Muster wie app/task_columns.py aufgebaut (Slug-Erzeugung,
sort_order-Schrittweite 10, Löschschutz bei letzter Spalte/bei Verwendung) -- damit beide
Spaltensysteme nicht auseinanderdriften, siehe CLAUDE.md "Projekt-Pipeline". Bewusst als
EIGENES Modul statt einer gemeinsamen, generischen Abstraktion mit task_columns.py: Task
verweist über den String-Schlüssel (Task.status == TaskColumn.key), Project dagegen über die
numerische ID (Project.pipeline_column_id == ProjectPipelineColumn.id) -- zwei
unterschiedliche Referenzformen -- und die Pipeline-Spalte trägt kein is_done/Automatik-Flag.
Eine Abstraktion für nur diese zwei, sich in diesem Punkt unterscheidenden Nutzer wäre eine
Überabstraktion gewesen; das MUSTER (nicht der Code) ist identisch übernommen.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Project, ProjectPipelineColumn

_SLUG_RE = re.compile(r"[^a-z0-9]+")

DEFAULT_COLUMNS = (
    {"key": "neu", "label": "Neu", "sort_order": 0},
    {"key": "in_bearbeitung", "label": "In Bearbeitung", "sort_order": 10},
    {"key": "wartet", "label": "Wartet", "sort_order": 20},
    {"key": "abgeschlossen", "label": "Abgeschlossen", "sort_order": 30},
)


def ensure_default_columns(db: Session) -> None:
    """Selbstheilung für Datenbanken ohne eine einzige Spalte -- vor allem Testdatenbanken,
    die nur per Base.metadata.create_all() statt per Alembic-Migration entstehen (die
    Migration selbst seedet dieselben vier Start-Spalten bereits für echte Installationen,
    siehe deren Revision). Greift nie in eine bereits vorhandene Konfiguration ein.

    Gegen einen gleichzeitigen ersten Zugriff abgesichert (siehe CLAUDE.md "Self-Seeding gegen
    gleichzeitigen Zugriff absichern") -- eine UNIQUE-Verletzung auf key (ein anderer Prozess
    war schneller) wird als "schon gesät" behandelt, kein Fehler."""
    if db.scalar(select(ProjectPipelineColumn.id).limit(1)) is not None:
        return
    try:
        with db.begin_nested():
            for c in DEFAULT_COLUMNS:
                db.add(ProjectPipelineColumn(**c))
            db.flush()
    except IntegrityError:
        return
    db.commit()


def _slugify(label: str) -> str:
    slug = _SLUG_RE.sub("_", label.strip().lower()).strip("_")
    return slug or "spalte"


def _unique_key(db: Session, base_key: str) -> str:
    key = base_key
    suffix = 2
    while db.scalar(select(ProjectPipelineColumn).where(ProjectPipelineColumn.key == key)) is not None:
        key = f"{base_key}_{suffix}"
        suffix += 1
    return key


def _column_to_dict(column: ProjectPipelineColumn) -> dict:
    return {"id": column.id, "key": column.key, "label": column.label, "sort_order": column.sort_order}


def list_columns(db: Session) -> list[dict]:
    ensure_default_columns(db)
    rows = db.scalars(select(ProjectPipelineColumn).order_by(ProjectPipelineColumn.sort_order, ProjectPipelineColumn.id)).all()
    return [_column_to_dict(c) for c in rows]


def default_pipeline_column_id(db: Session) -> int:
    """Die Spalte mit der niedrigsten sort_order -- Startspalte für neu angelegte Projekte.
    Aufgerufen von jeder der vier Project(...)-Konstruktionsstellen (app/projects.py::
    duplicate_project(), app/quick_service_orders.py, app/routers/inquiries.py::
    convert_inquiry(), app/routers/projects.py::create_project()), damit kein Projekt je ohne
    Spalte entsteht -- ein Projekt ohne Spalte würde im künftigen Kanban unsichtbar bleiben."""
    ensure_default_columns(db)
    column_id = db.scalar(
        select(ProjectPipelineColumn.id).order_by(ProjectPipelineColumn.sort_order, ProjectPipelineColumn.id).limit(1)
    )
    assert column_id is not None  # ensure_default_columns() garantiert mindestens eine Zeile
    return column_id


def create_column(db: Session, label: str) -> dict:
    ensure_default_columns(db)
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    max_sort = db.scalar(select(func.max(ProjectPipelineColumn.sort_order))) or 0
    column = ProjectPipelineColumn(key=_unique_key(db, _slugify(label)), label=label, sort_order=max_sort + 10)
    db.add(column)
    db.commit()
    return _column_to_dict(column)


def update_column(db: Session, column_id: int, label: str | None = None) -> dict:
    ensure_default_columns(db)
    column = db.get(ProjectPipelineColumn, column_id)
    if column is None:
        raise ValueError("Spalte nicht gefunden.")
    if label is not None:
        label = label.strip()
        if not label:
            raise ValueError("Bitte eine Bezeichnung angeben.")
        column.label = label
    db.commit()
    return _column_to_dict(column)


def reorder_columns(db: Session, ordered_ids: list[int]) -> list[dict]:
    ensure_default_columns(db)
    columns_by_id = {c.id: c for c in db.scalars(select(ProjectPipelineColumn)).all()}
    if set(ordered_ids) != set(columns_by_id.keys()):
        raise ValueError("Die Reihenfolge muss alle vorhandenen Spalten enthalten.")
    for index, column_id in enumerate(ordered_ids):
        columns_by_id[column_id].sort_order = index * 10
    db.commit()
    return list_columns(db)


def delete_column(db: Session, column_id: int) -> None:
    ensure_default_columns(db)
    column = db.get(ProjectPipelineColumn, column_id)
    if column is None:
        raise ValueError("Spalte nicht gefunden.")
    if db.scalar(select(func.count()).select_from(ProjectPipelineColumn)) <= 1:
        raise ValueError("Die letzte verbleibende Spalte kann nicht gelöscht werden.")
    projects_in_use = db.scalar(select(func.count()).select_from(Project).where(Project.pipeline_column_id == column.id))
    if projects_in_use:
        raise ValueError(f"{projects_in_use} Projekt(e) verwenden diese Spalte noch und müssen zuerst verschoben werden.")
    db.delete(column)
    db.commit()
