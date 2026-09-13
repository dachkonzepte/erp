"""Verwaltung der konfigurierbaren Aufgaben-Spalten (seit 1.1.1).

Ersetzt die zuvor drei fest kodierten Task-Status offen/in_arbeit/erledigt durch eine vom
Admin frei erweiterbare, umbenenn- und sortierbare Liste (siehe app/models.py::TaskColumn).
Task.status referenziert TaskColumn.key -- ein stabiler, beim Anlegen einmalig erzeugter
Slug, der beim Umbenennen des Labels nicht mehr ändert, damit bestehende Aufgaben nicht
verwaisen.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Task, TaskColumn

_SLUG_RE = re.compile(r"[^a-z0-9]+")

DEFAULT_COLUMNS = (
    {"key": "offen", "label": "Offen", "sort_order": 0, "is_done": False},
    {"key": "in_arbeit", "label": "In Arbeit", "sort_order": 10, "is_done": False},
    {"key": "erledigt", "label": "Erledigt", "sort_order": 20, "is_done": True},
)


def ensure_default_columns(db: Session) -> None:
    """Selbstheilung für Datenbanken ohne eine einzige Spalte -- vor allem Testdatenbanken, die
    nur per Base.metadata.create_all() statt per Alembic-Migration entstehen (die Migration
    selbst seedet dieselben drei Start-Spalten bereits für echte Installationen, siehe
    6ed174efcf4a_...py). Greift nie in eine bereits vorhandene Konfiguration ein."""
    if db.scalar(select(TaskColumn.id).limit(1)) is not None:
        return
    for c in DEFAULT_COLUMNS:
        db.add(TaskColumn(**c))
    db.commit()


def _slugify(label: str) -> str:
    slug = _SLUG_RE.sub("_", label.strip().lower()).strip("_")
    return slug or "spalte"


def _unique_key(db: Session, base_key: str) -> str:
    key = base_key
    suffix = 2
    while db.scalar(select(TaskColumn).where(TaskColumn.key == key)) is not None:
        key = f"{base_key}_{suffix}"
        suffix += 1
    return key


def _column_to_dict(column: TaskColumn) -> dict:
    return {
        "id": column.id,
        "key": column.key,
        "label": column.label,
        "sort_order": column.sort_order,
        "is_done": column.is_done,
    }


def list_columns(db: Session) -> list[dict]:
    ensure_default_columns(db)
    rows = db.scalars(select(TaskColumn).order_by(TaskColumn.sort_order, TaskColumn.id)).all()
    return [_column_to_dict(c) for c in rows]


def create_column(db: Session, label: str, is_done: bool = False) -> dict:
    ensure_default_columns(db)
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    max_sort = db.scalar(select(func.max(TaskColumn.sort_order))) or 0
    column = TaskColumn(key=_unique_key(db, _slugify(label)), label=label, is_done=is_done, sort_order=max_sort + 10)
    db.add(column)
    db.commit()
    return _column_to_dict(column)


def update_column(db: Session, column_id: int, label: str | None = None, is_done: bool | None = None) -> dict:
    ensure_default_columns(db)
    column = db.get(TaskColumn, column_id)
    if column is None:
        raise ValueError("Spalte nicht gefunden.")
    if label is not None:
        label = label.strip()
        if not label:
            raise ValueError("Bitte eine Bezeichnung angeben.")
        column.label = label
    if is_done is not None:
        column.is_done = is_done
    db.commit()
    return _column_to_dict(column)


def reorder_columns(db: Session, ordered_ids: list[int]) -> list[dict]:
    ensure_default_columns(db)
    columns_by_id = {c.id: c for c in db.scalars(select(TaskColumn)).all()}
    if set(ordered_ids) != set(columns_by_id.keys()):
        raise ValueError("Die Reihenfolge muss alle vorhandenen Spalten enthalten.")
    for index, column_id in enumerate(ordered_ids):
        columns_by_id[column_id].sort_order = index * 10
    db.commit()
    return list_columns(db)


def delete_column(db: Session, column_id: int) -> None:
    ensure_default_columns(db)
    column = db.get(TaskColumn, column_id)
    if column is None:
        raise ValueError("Spalte nicht gefunden.")
    if db.scalar(select(func.count()).select_from(TaskColumn)) <= 1:
        raise ValueError("Die letzte verbleibende Spalte kann nicht gelöscht werden.")
    tasks_in_use = db.scalar(select(func.count()).select_from(Task).where(Task.status == column.key))
    if tasks_in_use:
        raise ValueError(f"{tasks_in_use} Aufgabe(n) verwenden diese Spalte noch und müssen zuerst verschoben werden.")
    db.delete(column)
    db.commit()
