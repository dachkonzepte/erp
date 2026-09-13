"""Materialkatalog-Gruppen (seit 1.0.30) -- Container-Konzept für Materialien,
genau nach dem Vorbild von app/catalogs.py für Leistungen.

Genau eine Gruppe trägt is_import_catalog=True ('Fertigkatalog') -- sie wird
hier automatisch angelegt, falls sie noch nicht existiert, und dient als
Standardziel für importierte und neu erzeugte Materialien sowie als neue
Heimat für alle bereits vorhandenen Materialien (siehe backfill_existing_materials).

Absichtlich MaterialGroup genannt, nicht "MaterialCatalog" -- der Name wäre
mit dem bereits bestehenden Schema MaterialCatalogOut kollidiert (das stellt
ein einzelnes Material im 1.0.25-Materialkatalog dar, nicht diese Gruppen).
Die Oberfläche spricht trotzdem von "Materialkatalogen".
"""

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Material, MaterialGroup

IMPORT_MATERIAL_GROUP_NAME = "Fertigkatalog (Importe)"


def _materials_table_has_catalog_column(db: Session) -> bool:
    """True, sobald die Alembic-Migration aus 1.0.30 angewendet wurde. Siehe
    dieselbe Begründung wie _services_table_has_catalog_column in catalogs.py."""
    inspector = sa_inspect(db.get_bind())
    columns = {col["name"] for col in inspector.get_columns("materials")}
    return "catalog_id" in columns


def ensure_import_material_group(db: Session) -> MaterialGroup:
    group = db.scalar(select(MaterialGroup).where(MaterialGroup.is_import_catalog == True))  # noqa: E712
    if group is None:
        group = MaterialGroup(
            name=IMPORT_MATERIAL_GROUP_NAME,
            description="Wird automatisch verwaltet: Standardziel für importierte Materialien.",
            is_import_catalog=True,
        )
        db.add(group)
        db.commit()
        db.refresh(group)
    return group


def backfill_existing_materials(db: Session, group: MaterialGroup) -> int:
    """Ordnet alle bislang katalog-losen Materialien der übergebenen Gruppe
    zu. Gibt die Anzahl der geänderten Zeilen zurück, oder -1, wenn die
    Spalte materials.catalog_id noch nicht existiert."""
    if not _materials_table_has_catalog_column(db):
        return -1
    rows = db.scalars(select(Material).where(Material.catalog_id.is_(None))).all()
    for material in rows:
        material.catalog_id = group.id
    if rows:
        db.commit()
    return len(rows)


def list_material_groups(db: Session, *, include_archived: bool = False) -> list[MaterialGroup]:
    stmt = select(MaterialGroup).order_by(MaterialGroup.is_import_catalog.desc(), MaterialGroup.name)
    if not include_archived:
        stmt = stmt.where(MaterialGroup.archived == False)  # noqa: E712
    return db.scalars(stmt).all()


def create_material_group(db: Session, name: str, description: str | None) -> MaterialGroup:
    group = MaterialGroup(name=name.strip(), description=description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def set_material_group_archived(db: Session, group_id: int, archived: bool) -> MaterialGroup | None:
    group = db.get(MaterialGroup, group_id)
    if group is None:
        return None
    if group.is_import_catalog and archived:
        raise ValueError("Der Fertigkatalog kann nicht archiviert werden.")
    group.archived = archived
    db.commit()
    db.refresh(group)
    return group


def move_material_to_group(db: Session, material: Material, group_id: int | None) -> Material:
    material.catalog_id = group_id
    db.commit()
    db.refresh(material)
    return material


def copy_material_to_group(db: Session, original: Material, group_id: int | None) -> Material:
    """Erzeugt eine unabhängige Kopie eines Materials in einer anderen Gruppe
    -- z.B. für eine abweichende Preisvariante unter einem anderen Katalog.
    Bestehende Zuordnungen zu Leistungen (ServiceMaterial) bleiben beim
    Original, die Kopie startet ohne Verwendung."""
    copy = Material(
        article_number=original.article_number, name=original.name, unit=original.unit,
        purchase_price=original.purchase_price, price_basis=original.price_basis,
        source=original.source, catalog_id=group_id,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy
