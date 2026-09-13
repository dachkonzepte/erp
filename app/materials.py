"""Materialkatalog (seit 1.0.25).

Vorher hatte jede Leistung ihre eigene, unabhängige Materialliste --
dasselbe Material tauchte in zehn Leistungen als zehn unabhängige Zeilen auf.
Jetzt: ein Material, viele Leistungen können darauf verweisen (material_id
auf service_materials, additiv -- die bestehenden Spalten dort bleiben
unverändert erhalten, für Rückwärtskompatibilität).

Deduplizierung bei importierten Daten: gleiche Artikelnummer UND gleicher
Name/Einheit/Preis/Preisbasis -> ein Material. Gleiche Artikelnummer, aber
abweichende andere Werte -> KEIN stillschweigendes Zusammenführen, sondern
ein separates Material mit sichtbar gekennzeichneter Artikelnummer
("<original>-DUP2" usw.), damit widersprüchliche Icking-Daten nicht
unbemerkt vermischt werden.
"""

from decimal import Decimal

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Material, ServiceMaterial

MaterialVariantsCache = dict[str, list[Material]]


def _service_materials_has_material_id_column(db: Session) -> bool:
    """Analog zu den gleichnamigen Prüfungen bei Katalogen: true, sobald die
    1.0.25-Migration angewendet wurde. Vorher existiert
    service_materials.material_id in der echten Datenbank noch nicht."""
    inspector = sa_inspect(db.get_bind())
    columns = {col["name"] for col in inspector.get_columns("service_materials")}
    return "material_id" in columns


def _materials_table_has_catalog_column(db: Session) -> bool:
    """Analog zu _service_materials_has_material_id_column: true, sobald die
    1.0.30-Migration (Materialkataloge) angewendet wurde. Vorher existiert
    materials.catalog_id in der echten Datenbank noch nicht."""
    inspector = sa_inspect(db.get_bind())
    columns = {col["name"] for col in inspector.get_columns("materials")}
    return "catalog_id" in columns


def find_or_create_material(
    db: Session,
    article_number: str | None,
    name: str,
    unit: str,
    purchase_price: Decimal,
    price_basis: Decimal,
    variants_cache: MaterialVariantsCache,
    source: str = "imported",
    catalog_id: int | None = None,
) -> Material:
    """Material im Katalog finden oder anlegen.

    variants_cache wird vom Aufrufer für die Dauer EINES Imports/Laufs
    verwaltet (nicht global) -- vermeidet wiederholte Datenbankabfragen für
    dieselbe Artikelnummer innerhalb eines Laufs. Leerer String als Schlüssel
    für Materialien ohne Artikelnummer. catalog_id wird nur bei NEU
    angelegten Materialien gesetzt -- bereits vorhandene (per Deduplizierung
    gefundene) behalten ihre bestehende Zuordnung unangetastet.
    """
    cache_key = article_number or ""
    if cache_key not in variants_cache:
        if article_number:
            variants_cache[cache_key] = list(
                db.scalars(select(Material).where(Material.article_number == article_number)).all()
            )
        else:
            variants_cache[cache_key] = []

    for candidate in variants_cache[cache_key]:
        if (
            candidate.name == name
            and candidate.unit == unit
            and candidate.purchase_price == purchase_price
            and candidate.price_basis == price_basis
        ):
            return candidate

    if article_number:
        existing_count = len(variants_cache[cache_key])
        used_article_number = article_number if existing_count == 0 else f"{article_number}-DUP{existing_count + 1}"
    else:
        used_article_number = None

    material = Material(
        article_number=used_article_number, name=name, unit=unit,
        purchase_price=purchase_price, price_basis=price_basis, source=source,
    )
    # catalog_id NUR setzen, wenn tatsächlich ein Wert übergeben wurde --
    # nicht im Konstruktor mit catalog_id=None, da SQLAlchemy einen explizit
    # gesetzten Wert (auch None) ins INSERT aufnimmt. Existiert die Spalte in
    # der echten Datenbank noch nicht (Migration nicht angewendet), würde
    # das mit "no such column" fehlschlagen, auch bei NULL. Ohne die
    # Zuweisung bleibt das Attribut komplett unberührt, die Spalte taucht
    # dann gar nicht erst im INSERT auf.
    if catalog_id is not None:
        material.catalog_id = catalog_id
    db.add(material)
    db.flush()
    variants_cache[cache_key].append(material)
    return material


def backfill_existing_service_materials(db: Session, import_group_id: int | None = None) -> int:
    """Einmalig: bestehende service_materials-Zeilen (material_id IS NULL) dem
    Materialkatalog zuordnen. Sicher wiederholt ausführbar (überspringt
    bereits zugeordnete Zeilen). Gibt die Anzahl der geänderten Zeilen zurück,
    oder -1, wenn die Spalte service_materials.material_id noch nicht
    existiert (Migration noch nicht angewendet). import_group_id: Zielgruppe
    für dabei neu angelegte Materialien (siehe find_or_create_material)."""
    if not _service_materials_has_material_id_column(db):
        return -1
    rows = db.scalars(select(ServiceMaterial).where(ServiceMaterial.material_id.is_(None))).all()
    variants_cache: MaterialVariantsCache = {}
    for row in rows:
        material = find_or_create_material(
            db, row.article_number, row.name, row.unit, row.purchase_price, row.price_basis,
            variants_cache, source="imported", catalog_id=import_group_id,
        )
        row.material_id = material.id
    if rows:
        db.commit()
    return len(rows)


def list_materials(db: Session, *, search: str | None = None, catalog_id: int | None = None) -> list[Material]:
    stmt = select(Material).order_by(Material.name)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((Material.name.ilike(like)) | (Material.article_number.ilike(like)))
    if catalog_id is not None:
        stmt = stmt.where(Material.catalog_id == catalog_id)
    return db.scalars(stmt).all()


def create_manual_material(
    db: Session, name: str, unit: str, purchase_price: Decimal,
    article_number: str | None = None, price_basis: Decimal = Decimal("1"),
    catalog_id: int | None = None,
) -> Material:
    material = Material(
        article_number=article_number, name=name.strip(), unit=unit.strip(),
        purchase_price=purchase_price, price_basis=price_basis, source="manual",
        catalog_id=catalog_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def get_material(db: Session, material_id: int) -> Material | None:
    return db.get(Material, material_id)


def update_material(
    db: Session, material_id: int, name: str, unit: str, purchase_price: Decimal,
    article_number: str | None, price_basis: Decimal,
) -> Material | None:
    material = db.get(Material, material_id)
    if material is None:
        return None
    material.name = name.strip()
    material.unit = unit.strip()
    material.purchase_price = purchase_price
    material.article_number = article_number
    material.price_basis = price_basis
    db.commit()
    db.refresh(material)
    return material
