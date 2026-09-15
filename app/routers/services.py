"""Router: services

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 4 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from decimal import Decimal
from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..calculation import build_calculation, get_settings_for_catalog, get_service_for_calculation
from ..database import get_db
from ..models import AppUser, Catalog, Material, MaterialCalculationOverride, Service, ServiceCalculation
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..schemas import (
    ServiceBaseUpdate, ServiceCalculationOut, ServiceCalculationUpdate, ServiceCreate,
    ServiceDetailOut, ServiceListOut, ServiceMaterialAdd, ServiceMoveOrCopy,
)
from ..services import (
    add_material_to_service, copy_service_to_catalog, create_manual_service,
    is_service_editable, remove_material_from_service, update_service_base_fields,
)

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Leistungskatalog trägt Kalkulation/Verkaufspreise --
# Büro/Admin, nirgends von einer Monteurs-Seite genutzt (geprüft, anders als bei
# GET /api/materials, siehe dort).
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


@router.get("/api/services", response_model=list[ServiceListOut])
def list_services(catalog_id: int | None = Query(default=None), db: Session = Depends(get_db), _role: AppUser = _role_dep):
    settings_cache: dict[int | None, object] = {}
    stmt = (
        select(Service)
        .options(
            selectinload(Service.materials),
            selectinload(Service.calculation),
            selectinload(Service.material_overrides),
            selectinload(Service.catalog),
        )
        .order_by(Service.external_id)
    )
    if catalog_id is not None:
        stmt = stmt.where(Service.catalog_id == catalog_id)
    services = db.scalars(stmt).all()

    result = []
    for service in services:
        settings = get_settings_for_catalog(db, service.catalog_id, settings_cache)
        calc = build_calculation(service, settings)
        result.append(
            ServiceListOut(
                id=service.id,
                external_id=service.external_id,
                source_type=service.source_type,
                short_text=service.short_text,
                unit=service.unit,
                site_time_raw=service.site_time_raw,
                sale_price=service.sale_price,
                activity_code=service.activity_code,
                material_count=len(service.materials),
                catalog_id=service.catalog_id,
                catalog_name=service.catalog.name if service.catalog else None,
                calculated_sale_price=calc["effective_sale_price"],
                calculation_delta=calc["delta_to_source"],
            )
        )
    return result


def _resolve_materials(db: Session, items: list[ServiceMaterialAdd]) -> list[tuple[Material, Decimal, Decimal]]:
    resolved = []
    for item in items:
        material = db.get(Material, item.material_id)
        if material is None:
            raise HTTPException(status_code=404, detail=f"Material {item.material_id} nicht gefunden.")
        resolved.append((material, item.quantity, item.waste_pct))
    return resolved


@router.post("/api/services", response_model=ServiceDetailOut)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Erzeugt eine manuell erfasste Leistung mit vollständiger Kalkulation
    (Zeit, Material aus dem Katalog, Fremdleistung, Zuschläge). Eigentliche
    Logik in app/services.py, testbar ohne FastAPI."""
    if payload.catalog_id is not None and db.get(Catalog, payload.catalog_id) is None:
        raise HTTPException(status_code=404, detail="Katalog nicht gefunden.")
    resolved_materials = _resolve_materials(db, payload.materials)

    service = create_manual_service(
        db, catalog_id=payload.catalog_id, service_type=payload.service_type,
        short_text=payload.short_text, long_text=payload.long_text,
        quantity=payload.quantity, unit=payload.unit,
        site_time_raw=payload.site_time_raw, workshop_time_raw=payload.workshop_time_raw,
        labor_rate_override=payload.labor_rate_override,
        material_markup_pct_override=payload.material_markup_pct_override,
        equipment_cost=payload.equipment_cost, subcontractor_cost=payload.subcontractor_cost,
        other_cost=payload.other_cost,
        overhead_pct_override=payload.overhead_pct_override,
        risk_profit_pct_override=payload.risk_profit_pct_override,
        manual_sale_price=payload.sale_price,
        materials=resolved_materials,
    )
    return ServiceDetailOut.model_validate(service)


_EDIT_LOCKED_DETAIL = "Importierte Leistungen können nicht direkt bearbeitet werden -- bitte zuerst in einen eigenen Katalog kopieren."


@router.put("/api/services/{service_id}", response_model=ServiceDetailOut)
def update_service_base(service_id: int, payload: ServiceBaseUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    service = get_service_for_calculation(db, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    if not is_service_editable(service):
        raise HTTPException(status_code=403, detail=_EDIT_LOCKED_DETAIL)
    updated = update_service_base_fields(
        db, service, service_type=payload.service_type, short_text=payload.short_text,
        long_text=payload.long_text, quantity=payload.quantity, unit=payload.unit,
    )
    return ServiceDetailOut.model_validate(updated)


@router.post("/api/services/{service_id}/materials", response_model=ServiceDetailOut)
def add_service_material(service_id: int, payload: ServiceMaterialAdd, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    service = get_service_for_calculation(db, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    if not is_service_editable(service):
        raise HTTPException(status_code=403, detail=_EDIT_LOCKED_DETAIL)
    material = db.get(Material, payload.material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    add_material_to_service(db, service, material, payload.quantity, payload.waste_pct)
    service = get_service_for_calculation(db, service_id)
    return ServiceDetailOut.model_validate(service)


@router.delete("/api/services/{service_id}/materials/{service_material_id}", response_model=ServiceDetailOut)
def delete_service_material(service_id: int, service_material_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    service = get_service_for_calculation(db, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    if not is_service_editable(service):
        raise HTTPException(status_code=403, detail=_EDIT_LOCKED_DETAIL)
    removed = remove_material_from_service(db, service, service_material_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Materialzeile nicht gefunden.")
    service = get_service_for_calculation(db, service_id)
    return ServiceDetailOut.model_validate(service)


@router.post("/api/services/{service_id}/move", response_model=ServiceDetailOut)
def move_service(service_id: int, payload: ServiceMoveOrCopy, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    if payload.catalog_id is not None and db.get(Catalog, payload.catalog_id) is None:
        raise HTTPException(status_code=404, detail="Katalog nicht gefunden.")
    service.catalog_id = payload.catalog_id
    db.commit()
    db.refresh(service)
    return ServiceDetailOut.model_validate(service)


@router.post("/api/services/{service_id}/copy", response_model=ServiceDetailOut)
def copy_service(service_id: int, payload: ServiceMoveOrCopy, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Erzeugt eine unabhängige Kopie einer Leistung -- ein späterer
    Re-Import der ursprünglichen Quelle wirkt sich nicht auf die Kopie aus,
    siehe Konzept 'Fertigkatalog nur zur Aufnahme, Arbeit findet in eigenen
    Katalogen statt'. Eigentliche Logik in app/services.py, testbar ohne
    FastAPI."""
    original = get_service_for_calculation(db, service_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    if payload.catalog_id is not None and db.get(Catalog, payload.catalog_id) is None:
        raise HTTPException(status_code=404, detail="Katalog nicht gefunden.")
    copy = copy_service_to_catalog(db, original, payload.catalog_id)
    return ServiceDetailOut.model_validate(copy)


@router.get("/api/services/{service_id}", response_model=ServiceDetailOut)
def get_service(service_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    service = db.scalar(
        select(Service)
        .options(selectinload(Service.materials))
        .where(Service.id == service_id)
    )
    if service is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    return ServiceDetailOut.model_validate(service)


@router.get("/api/services/{service_id}/calculation", response_model=ServiceCalculationOut)
def get_service_calculation(service_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    service = get_service_for_calculation(db, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")
    settings = get_settings_for_catalog(db, service.catalog_id)
    return ServiceCalculationOut.model_validate(build_calculation(service, settings))


@router.put("/api/services/{service_id}/calculation", response_model=ServiceCalculationOut)
def update_service_calculation(
    service_id: int,
    payload: ServiceCalculationUpdate,
    db: Session = Depends(get_db),
    _role: AppUser = _role_dep,
):
    service = get_service_for_calculation(db, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Leistung nicht gefunden.")

    calc = service.calculation
    if calc is None:
        calc = ServiceCalculation(service_id=service.id)
        db.add(calc)
        service.calculation = calc

    calc.site_time_minutes = payload.site_time_minutes
    calc.workshop_time_minutes = payload.workshop_time_minutes
    calc.labor_rate_override = payload.labor_rate_override
    calc.material_markup_pct_override = payload.material_markup_pct_override
    calc.equipment_cost = payload.equipment_cost
    calc.subcontractor_cost = payload.subcontractor_cost
    calc.other_cost = payload.other_cost
    calc.overhead_pct_override = payload.overhead_pct_override
    calc.risk_profit_pct_override = payload.risk_profit_pct_override
    calc.manual_sale_price = payload.manual_sale_price
    calc.notes = payload.notes

    material_by_id = {material.id: material for material in service.materials}
    existing_overrides = {
        (override.article_number_key or "", override.material_name_key): override
        for override in service.material_overrides
    }

    for item in payload.material_overrides:
        material = material_by_id.get(item.material_id)
        if material is None:
            raise HTTPException(
                status_code=422,
                detail=f"Material-ID {item.material_id} gehört nicht zu dieser Leistung.",
            )

        key = (material.article_number or "", material.name)
        override = existing_overrides.get(key)
        has_custom_value = any(
            [
                item.quantity_override is not None,
                item.waste_pct != Decimal("0"),
                item.purchase_price_override is not None,
                item.price_basis_override is not None,
            ]
        )

        if not has_custom_value:
            if override is not None:
                db.delete(override)
            continue

        if override is None:
            override = MaterialCalculationOverride(
                service_id=service.id,
                article_number_key=material.article_number or "",
                material_name_key=material.name,
            )
            db.add(override)
            existing_overrides[key] = override

        override.quantity_override = item.quantity_override
        override.waste_pct = item.waste_pct
        override.purchase_price_override = item.purchase_price_override
        override.price_basis_override = item.price_basis_override

    db.commit()

    service = get_service_for_calculation(db, service_id)
    if is_service_editable(service):
        # Eigene (nicht importierte) Leistungen: berechneten Preis als
        # sale_price festschreiben, damit die Δ-Spalte danach wieder bei 0
        # steht -- derselbe Grundsatz wie bei der Erfassung, jetzt auch bei
        # jeder späteren Kalkulationsänderung konsequent angewendet.
        sync_settings = get_settings_for_catalog(db, service.catalog_id)
        preview = build_calculation(service, sync_settings)
        service.sale_price = preview["effective_sale_price"]
        db.commit()
        service = get_service_for_calculation(db, service_id)

    settings = get_settings_for_catalog(db, service.catalog_id)
    return ServiceCalculationOut.model_validate(build_calculation(service, settings))
