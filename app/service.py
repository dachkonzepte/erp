from sqlalchemy import select
from sqlalchemy.orm import Session
from .catalogs import ensure_import_catalog
from .importers.leistungen_dach import ParsedProject
from .material_groups import ensure_import_material_group
from .materials import (
    MaterialVariantsCache, _materials_table_has_catalog_column,
    _service_materials_has_material_id_column, find_or_create_material,
)
from .models import ImportBatch, Service, ServiceMaterial

SOURCE_TYPE = "leistungen_dach"


def persist_project(db: Session, project: ParsedProject, filename: str) -> tuple[int, int]:
    """Importiert Quelldaten neu, erhält aber Service-ID und DACHKONZEPTE-Kalkulation."""
    # ensure_import_catalog()/ensure_import_material_group() committen intern,
    # falls der jeweilige Fertigkatalog noch nicht existiert (jede frische
    # Datenbank -- z.B. jeder Testlauf). Ein commit() expired bei SQLAlchemy
    # per Default JEDES Objekt in der Session, nicht nur das gerade
    # committete. Deshalb MÜSSEN beide hier passieren, BEVOR `batch` angelegt
    # wird -- sonst wäre `batch` zum Zeitpunkt des späteren `batch.id`-
    # Zugriffs expired, das würde eine Nachlade-Abfrage auslösen, die wiederum
    # einen verfrühten Autoflush der noch unvollständigen `service`-Zeile
    # auslöst (import_batch_id ist zu dem Zeitpunkt noch nicht gesetzt) ->
    # IntegrityError. Genau das ist in 1.0.25 passiert (40 fehlgeschlagene
    # Tests). IDs zusätzlich sofort in lokale Variablen sichern, nicht
    # wiederholt über die Objekte zugreifen.
    import_catalog_id = ensure_import_catalog(db).id
    materials_catalog_ready = _materials_table_has_catalog_column(db)
    import_material_group_id = ensure_import_material_group(db).id if materials_catalog_ready else None

    batch = ImportBatch(
        source_type=SOURCE_TYPE,
        source_name=project.source_name,
        source_version=project.source_version,
        filename=filename,
    )
    db.add(batch)
    db.flush()
    batch_id = batch.id

    service_materials_ready = _service_materials_has_material_id_column(db)
    material_variants_cache: MaterialVariantsCache = {}

    inserted = 0
    replaced = 0

    for parsed in project.services:
        service = db.scalar(
            select(Service).where(
                Service.source_type == SOURCE_TYPE,
                Service.external_id == parsed.external_id,
            )
        )
        if service is None:
            service = Service(source_type=SOURCE_TYPE, external_id=parsed.external_id, catalog_id=import_catalog_id)
            db.add(service)
            inserted += 1
        else:
            replaced += 1
            # Nur die importierte Material-Stückliste wird erneuert. Eigene Overrides
            # liegen in einer separaten Tabelle und bleiben über logische Schlüssel erhalten.
            # catalog_id absichtlich NICHT angefasst -- eine bereits bestehende Leistung im
            # Fertigkatalog bleibt dort, eine vom Nutzer anderswohin verschobene bleibt dort.
            service.materials.clear()

        service.import_batch_id = batch_id
        service.title_name = parsed.title_name
        service.short_text = parsed.short_text
        service.long_text = parsed.long_text
        service.rtf_text = parsed.rtf_text
        service.image_reference = parsed.image_reference
        service.quantity = parsed.quantity
        service.unit = parsed.unit
        service.site_time_raw = parsed.site_time_raw
        service.workshop_time_raw = parsed.workshop_time_raw
        service.time_unit = "min/unit"  # Für Leistungen-Dach V3 fachlich aus Beispielkalkulation abgeleitet.
        service.sale_price = parsed.sale_price
        service.activity_code = parsed.activity_code

        for material in parsed.materials:
            catalog_material = None
            if service_materials_ready:
                catalog_material = find_or_create_material(
                    db, material.article_number, material.name, material.unit,
                    material.purchase_price, material.price_basis,
                    material_variants_cache, source="imported", catalog_id=import_material_group_id,
                )
            service.materials.append(
                ServiceMaterial(
                    material_id=catalog_material.id if catalog_material else None,
                    name=material.name,
                    article_number=material.article_number,
                    quantity=material.quantity,
                    unit=material.unit,
                    waste_raw=material.waste_raw,
                    purchase_price=material.purchase_price,
                    price_basis=material.price_basis,
                )
            )

    db.commit()
    return inserted, replaced
