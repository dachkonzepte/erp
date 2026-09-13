"""Services-Verwaltung: manuelle Erfassung (seit 1.0.23, erweitert um vollständige
Kalkulation und Materialzuordnung seit 1.0.28), Kopieren zwischen Katalogen
(seit 1.0.26).

Jede Leistung braucht laut Datenmodell einen import_batch_id -- damit dafür
keine Migration nötig ist (import_batch_id nullbar zu machen hätte auf
SQLite dieselbe Art riskanter Tabellen-Neuerstellung gebraucht, die zuletzt
so viel Ärger gemacht hat), bekommen alle manuell erfassten UND alle
kopierten Leistungen einen gemeinsamen, automatisch angelegten
"synthetischen" ImportBatch -- exakt das Muster, das sich beim Fertigkatalog
schon bewährt hat.

WICHTIG (siehe 1.0.27-Regression): ensure_manual_import_batch() committet
intern, falls der Batch noch nicht existiert -- das expired bei SQLAlchemy
per Default JEDES Objekt in der Session, nicht nur das gerade committete.
Deshalb wird sie in jeder Funktion hier IMMER als Erstes aufgerufen, bevor
irgendein anderes Objekt angelegt wird, und ihre .id wird sofort in eine
lokale Variable gesichert statt wiederholt über das Objekt gelesen.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .calculation import build_calculation, get_settings_for_catalog
from .models import ImportBatch, Material, MaterialCalculationOverride, Service, ServiceCalculation, ServiceMaterial

MANUAL_SOURCE_TYPE = "manual"
COPIED_SOURCE_TYPE = "copied"
IMPORTED_SOURCE_TYPE = "leistungen_dach"


def ensure_manual_import_batch(db: Session) -> ImportBatch:
    batch = db.scalar(select(ImportBatch).where(ImportBatch.source_type == MANUAL_SOURCE_TYPE))
    if batch is None:
        batch = ImportBatch(
            source_type=MANUAL_SOURCE_TYPE,
            source_name="Manuelle Erfassung",
            filename="—",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
    return batch


def new_manual_external_id() -> str:
    return f"MANUAL-{uuid.uuid4().hex[:10]}"


def is_service_editable(service: Service) -> bool:
    """Basisfelder (Kurztext, Menge, Material, Kalkulationsdetails) dürfen nur
    bearbeitet werden, wenn ein Re-Import sie nicht wieder überschreiben würde.
    Das hängt an source_type, nicht am aktuellen Katalog: eine importierte
    Leistung bleibt re-import-empfindlich, auch wenn sie inzwischen aus dem
    Fertigkatalog in einen eigenen Katalog verschoben wurde -- persist_project()
    findet und überschreibt sie über external_id, unabhängig von catalog_id."""
    return service.source_type != IMPORTED_SOURCE_TYPE


def _apply_computed_sale_price(db: Session, service: Service) -> None:
    """Schreibt den aktuell berechneten/effektiven Preis als service.sale_price
    fest -- nur für eigene Leistungen sinnvoll (siehe is_service_editable):
    dort gibt es keinen externen Referenzpreis, den man erhalten müsste, und
    ohne das würde die Δ-Spalte nach jeder Kalkulationsänderung wieder eine
    Differenz zu einem Wert zeigen, der nie ein echter Vergleichsmaßstab war
    (derselbe Grundsatz wie der 1.0.24-Fix, jetzt konsequent auch hier)."""
    if not is_service_editable(service):
        return
    settings = get_settings_for_catalog(db, service.catalog_id)
    calc_result = build_calculation(service, settings)
    service.sale_price = calc_result["effective_sale_price"]


def create_manual_service(
    db: Session,
    *,
    catalog_id: int | None,
    service_type: str | None,
    short_text: str,
    long_text: str | None,
    quantity: Decimal,
    unit: str,
    site_time_raw: Decimal,
    workshop_time_raw: Decimal,
    labor_rate_override: Decimal | None,
    material_markup_pct_override: Decimal | None,
    equipment_cost: Decimal,
    subcontractor_cost: Decimal,
    other_cost: Decimal,
    overhead_pct_override: Decimal | None,
    risk_profit_pct_override: Decimal | None,
    manual_sale_price: Decimal | None,
    materials: list[tuple[Material, Decimal, Decimal]] | None = None,
) -> Service:
    """Erzeugt eine manuell erfasste Leistung inkl. vollständiger Kalkulation
    (Zeit, Material aus dem Katalog, Fremdleistung, Zuschläge) in einem
    Schritt. `materials` ist eine Liste aus (Material, Menge, Verschnitt-%).

    Zeit wird bewusst direkt in die Kalkulation geschrieben (nicht dem
    globalen "Quellzeit verwenden"-Schalter überlassen) -- der ist für den
    Umgang mit importierten Zeitwerten gedacht, nicht für eigene, direkt
    angegebene Zeiten; wäre er global deaktiviert, würde die eigene Zeit
    sonst fälschlich ignoriert."""
    # Beide möglicherweise intern committenden Aufrufe ganz an den Anfang,
    # bevor irgendetwas Abhängiges (service, materials, calculation) existiert
    # -- siehe 1.0.27-Regression: ein commit() expired sonst alles, was schon
    # in der Sitzung hängt, nicht nur das gerade committete.
    batch = ensure_manual_import_batch(db)
    settings = get_settings_for_catalog(db, catalog_id)

    service = Service(
        import_batch_id=batch.id,
        catalog_id=catalog_id,
        service_type=service_type,
        source_type=batch.source_type,
        external_id=new_manual_external_id(),
        short_text=short_text.strip(),
        long_text=(long_text or "").strip(),
        quantity=quantity,
        unit=unit.strip(),
        site_time_raw=site_time_raw,
        workshop_time_raw=workshop_time_raw,
        sale_price=manual_sale_price or Decimal("0"),  # vorläufig, wird unten final gesetzt
    )
    db.add(service)
    db.flush()

    for material, mat_quantity, waste_pct in (materials or []):
        service.materials.append(ServiceMaterial(
            material_id=material.id, name=material.name, article_number=material.article_number,
            quantity=mat_quantity, unit=material.unit, waste_raw=waste_pct,
            purchase_price=material.purchase_price, price_basis=material.price_basis,
        ))

    service.calculation = ServiceCalculation(
        service_id=service.id,
        site_time_minutes=site_time_raw, workshop_time_minutes=workshop_time_raw,
        labor_rate_override=labor_rate_override, material_markup_pct_override=material_markup_pct_override,
        equipment_cost=equipment_cost, subcontractor_cost=subcontractor_cost, other_cost=other_cost,
        overhead_pct_override=overhead_pct_override, risk_profit_pct_override=risk_profit_pct_override,
        manual_sale_price=manual_sale_price,
    )
    db.flush()

    if is_service_editable(service):  # gilt hier immer (frisch angelegt), Konsistenz mit _apply_computed_sale_price
        calc_result = build_calculation(service, settings)
        service.sale_price = calc_result["effective_sale_price"]

    db.commit()
    db.refresh(service)
    return service


def add_material_to_service(db: Session, service: Service, material: Material, quantity: Decimal, waste_pct: Decimal) -> ServiceMaterial:
    row = ServiceMaterial(
        material_id=material.id, name=material.name, article_number=material.article_number,
        quantity=quantity, unit=material.unit, waste_raw=waste_pct,
        purchase_price=material.purchase_price, price_basis=material.price_basis,
    )
    service.materials.append(row)
    # Vollständig committen und row auffrischen, BEVOR service.materials für die
    # Neuberechnung erneut angefasst wird (_apply_computed_sale_price liest die
    # Collection erneut). Zwei bereits versuchte, engere Varianten (db.add()
    # durch service.materials.append() ersetzt; Reihenfolge der intern
    # committenden Aufrufe umgestellt) haben das Problem NICHT behoben --
    # diese vollständige Trennung in zwei Transaktionen umgeht es unabhängig
    # vom genauen Mechanismus, statt ihn weiter zu vermuten.
    db.commit()
    db.refresh(row)
    _apply_computed_sale_price(db, service)
    db.commit()
    return row


def remove_material_from_service(db: Session, service: Service, service_material_id: int) -> bool:
    row = next((m for m in service.materials if m.id == service_material_id), None)
    if row is None:
        return False
    service.materials.remove(row)
    # Siehe ausführlicher Kommentar in add_material_to_service: vollständig
    # committen, BEVOR service.materials für die Neuberechnung erneut
    # angefasst wird.
    db.commit()
    _apply_computed_sale_price(db, service)
    db.commit()
    return True


def update_service_base_fields(
    db: Session, service: Service, *, service_type: str | None,
    short_text: str, long_text: str | None, quantity: Decimal, unit: str,
) -> Service:
    service.service_type = service_type
    service.short_text = short_text.strip()
    service.long_text = (long_text or "").strip()
    service.quantity = quantity
    service.unit = unit.strip()
    _apply_computed_sale_price(db, service)
    db.commit()
    db.refresh(service)
    return service


def copy_service_to_catalog(db: Session, original: Service, catalog_id: int | None) -> Service:
    """Erzeugt eine vollständig unabhängige Kopie einer Leistung (neue ID,
    neue external_id, eigene Kalkulation und Materialzuordnungen) -- ein
    späterer Re-Import der ursprünglichen Quelle wirkt sich nicht auf die
    Kopie aus. Materialien werden als neue, unabhängige Zuordnungen kopiert,
    verweisen aber weiterhin auf dieselben Material-Katalog-Einträge (ein
    Material ist ein globales Fakt, kein Katalog-Duplikat -- wie vereinbart).
    """
    batch = ensure_manual_import_batch(db)
    copy = Service(
        import_batch_id=batch.id,
        catalog_id=catalog_id,
        source_type=COPIED_SOURCE_TYPE,
        external_id=new_manual_external_id(),
        title_name=original.title_name,
        short_text=original.short_text,
        long_text=original.long_text,
        quantity=original.quantity,
        unit=original.unit,
        site_time_raw=original.site_time_raw,
        workshop_time_raw=original.workshop_time_raw,
        time_unit=original.time_unit,
        sale_price=original.sale_price,
        activity_code=original.activity_code,
        service_type=original.service_type,
    )
    db.add(copy)
    db.flush()

    if original.calculation is not None:
        oc = original.calculation
        copy.calculation = ServiceCalculation(
            service_id=copy.id,
            site_time_minutes=oc.site_time_minutes, workshop_time_minutes=oc.workshop_time_minutes,
            labor_rate_override=oc.labor_rate_override, material_markup_pct_override=oc.material_markup_pct_override,
            equipment_cost=oc.equipment_cost, subcontractor_cost=oc.subcontractor_cost, other_cost=oc.other_cost,
            overhead_pct_override=oc.overhead_pct_override, risk_profit_pct_override=oc.risk_profit_pct_override,
            manual_sale_price=oc.manual_sale_price, notes=oc.notes,
        )

    for om in original.materials:
        copy.materials.append(ServiceMaterial(
            material_id=om.material_id, name=om.name, article_number=om.article_number,
            quantity=om.quantity, unit=om.unit, waste_raw=om.waste_raw,
            purchase_price=om.purchase_price, price_basis=om.price_basis,
        ))

    for override in original.material_overrides:
        db.add(MaterialCalculationOverride(
            service_id=copy.id, article_number_key=override.article_number_key,
            material_name_key=override.material_name_key,
            quantity_override=override.quantity_override, waste_pct=override.waste_pct,
            purchase_price_override=override.purchase_price_override,
            price_basis_override=override.price_basis_override,
        ))

    db.commit()
    db.refresh(copy)
    return copy
