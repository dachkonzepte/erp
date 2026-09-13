"""Katalog-Verwaltung (seit 1.0.14).

Genau ein Katalog trägt is_import_catalog=True ('Fertigkatalog') -- er wird
hier automatisch angelegt, falls er noch nicht existiert, und dient als
Vorgabe beim Import sowie als neue Heimat für alle bereits vorhandenen,
importierten Leistungen (siehe backfill_existing_services).
"""

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Catalog, Service

IMPORT_CATALOG_NAME = "Fertigkatalog (Importe)"


def _services_table_has_catalog_column(db: Session) -> bool:
    """True, sobald die Alembic-Migration aus 1.0.14 angewendet wurde.

    Base.metadata.create_all() legt neue Tabellen (wie 'catalogs') korrekt an,
    ergänzt aber KEINE neue Spalte an einer bereits bestehenden Tabelle wie
    'services' -- das übernimmt ausschließlich Alembic. Bis die Migration
    gelaufen ist, existiert services.catalog_id in der echten Datenbank noch
    nicht, obwohl das Modell sie schon kennt."""
    inspector = sa_inspect(db.get_bind())
    columns = {col["name"] for col in inspector.get_columns("services")}
    return "catalog_id" in columns


def ensure_import_catalog(db: Session) -> Catalog:
    catalog = db.scalar(select(Catalog).where(Catalog.is_import_catalog == True))  # noqa: E712
    if catalog is None:
        catalog = Catalog(
            name=IMPORT_CATALOG_NAME,
            description="Wird automatisch verwaltet: Standardziel für importierte Leistungen.",
            is_import_catalog=True,
        )
        db.add(catalog)
        db.commit()
        db.refresh(catalog)
    return catalog


def backfill_existing_services(db: Session, catalog: Catalog) -> int:
    """Ordnet alle bislang katalog-losen Leistungen dem übergebenen Katalog zu
    (migrationsarm, ohne bestehende Zuordnungen zu verändern). Gibt die Anzahl
    der geänderten Zeilen zurück, oder -1, wenn die Spalte services.catalog_id
    noch nicht existiert (Migration noch nicht angewendet) -- dann wird
    bewusst nichts versucht, statt mit einem Datenbankfehler abzubrechen."""
    if not _services_table_has_catalog_column(db):
        return -1
    rows = db.scalars(select(Service).where(Service.catalog_id.is_(None))).all()
    for service in rows:
        service.catalog_id = catalog.id
    if rows:
        db.commit()
    return len(rows)


def list_catalogs(db: Session, *, include_archived: bool = False) -> list[Catalog]:
    stmt = select(Catalog).order_by(Catalog.is_import_catalog.desc(), Catalog.name)
    if not include_archived:
        stmt = stmt.where(Catalog.archived == False)  # noqa: E712
    return db.scalars(stmt).all()


def create_catalog(db: Session, name: str, description: str | None) -> Catalog:
    catalog = Catalog(name=name.strip(), description=description)
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog


def set_catalog_archived(db: Session, catalog_id: int, archived: bool) -> Catalog | None:
    catalog = db.get(Catalog, catalog_id)
    if catalog is None:
        return None
    if catalog.is_import_catalog and archived:
        raise ValueError("Der Fertigkatalog kann nicht archiviert werden.")
    catalog.archived = archived
    db.commit()
    db.refresh(catalog)
    return catalog
