"""Betriebsmittelverwaltung (seit 1.4.0, Modul "betriebsmittel").

Eigene Inventarschicht MIT optionalem Bezug zu genau einer OperationalResource -- siehe
Klassendocstring von OperationalAsset (app/models.py) für die vollständige Begründung, warum
das bewusst KEINE Erweiterung von OperationalResource selbst ist, sondern eine getrennte
Tabelle: die Plantafel-Disposition (Team/TeamResource/PlanningSlot) referenziert weiterhin
ausschließlich operational_resources.id, unverändert.

Live-Auflösung statt Kopie: ist ein Asset verknüpft (resource_id gesetzt), werden
name/asset_type/manufacturer/model/identifier bei JEDEM Lesezugriff live von der Ressource
gelesen (asset_to_dict()) -- niemals als eigene Kopie auf OperationalAsset gespeichert. Das
verhindert die vom Nutzer explizit benannte Doppelerfassung/Namensdivergenz. Zusätzlich
erzwingt UniqueConstraint("resource_id") auf Datenbankebene, dass eine Ressource höchstens
ein Asset hat.

Fälligkeitslogik (is_inspection_due()/is_inspection_overdue()): bewusst NICHT dieselben
Funktionen wie MaintenanceContractItem (app/maintenance_contracts.py) wiederverwendet -- deren
_is_item_overdue() ist an die saisonalen MaintenanceWindow-Fenster gekoppelt, was für eine
turnusmäßige Geräteprüfung (z. B. "TÜV alle 12 Monate") fachlich nicht passt. Übernommen ist
nur das PATTERN: is_due prüft eine Vorlaufzeit (reminder_lead_days) VOR dem eigentlichen
next_due_date, is_overdue prüft, ob next_due_date bereits verstrichen ist -- exakt dieselbe
Zwei-Stufen-Idee wie beim Wartungsmodul, mit eigenen, einfacheren, an die Gerätefrist
angepassten Funktionen (siehe CLAUDE.md, "gleiches Muster, dokumentierte Trennung", analog zu
den Projekt-Pipeline-Spalten)."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import OperationalAsset, OperationalAssetInspection, OperationalAssetSettings, OperationalResource
from .operational_asset_documents import delete_document_file

MODULE_KEY = "betriebsmittel"


def is_inspection_due(next_due_date: date | None, lead_days: int, *, today: date | None = None) -> bool:
    if next_due_date is None:
        return False
    today = today or date.today()
    return next_due_date <= today + timedelta(days=lead_days)


def is_inspection_overdue(next_due_date: date | None, *, today: date | None = None) -> bool:
    if next_due_date is None:
        return False
    today = today or date.today()
    return next_due_date < today


def get_or_create_operational_asset_settings(db: Session) -> OperationalAssetSettings:
    settings = db.get(OperationalAssetSettings, 1)
    if settings is None:
        settings = OperationalAssetSettings(id=1)
        db.add(settings)
        db.commit()
    return settings


def operational_asset_settings_to_dict(settings: OperationalAssetSettings) -> dict:
    return {"reminder_lead_days": settings.reminder_lead_days}


def update_operational_asset_settings(db: Session, reminder_lead_days: int) -> dict:
    settings = get_or_create_operational_asset_settings(db)
    settings.reminder_lead_days = reminder_lead_days
    db.commit()
    return operational_asset_settings_to_dict(settings)


def _inspection_to_dict(inspection: OperationalAssetInspection, lead_days: int, *, today: date | None = None) -> dict:
    return {
        "id": inspection.id,
        "asset_id": inspection.asset_id,
        "inspection_type": inspection.inspection_type,
        "interval_months": inspection.interval_months,
        "last_inspection_date": inspection.last_inspection_date,
        "next_due_date": inspection.next_due_date,
        "inspector": inspection.inspector,
        "document_filename": inspection.document_filename,
        "document_original_name": inspection.document_original_name,
        "notes": inspection.notes,
        "is_due": is_inspection_due(inspection.next_due_date, lead_days, today=today),
        "is_overdue": is_inspection_overdue(inspection.next_due_date, today=today),
    }


def asset_to_dict(asset: OperationalAsset, lead_days: int, *, today: date | None = None) -> dict:
    """Löst bei verknüpfter Ressource die Identitätsfelder LIVE auf -- niemals von
    OperationalAsset selbst gelesen, solange resource_id gesetzt ist (siehe Moduldocstring)."""
    resource = asset.resource
    if resource is not None:
        name = resource.name
        asset_type = resource.resource_type
        manufacturer = resource.manufacturer
        model = resource.model
        identifier = resource.identifier
        resource_number = resource.resource_number
    else:
        name = asset.name
        asset_type = asset.asset_type
        manufacturer = asset.manufacturer
        model = asset.model
        identifier = asset.identifier
        resource_number = None

    inspections = [_inspection_to_dict(i, lead_days, today=today) for i in asset.inspections]
    due_dates = [i["next_due_date"] for i in inspections if i["next_due_date"] is not None]
    next_due_date = min(due_dates) if due_dates else None
    is_due = any(i["is_due"] for i in inspections)
    is_overdue = any(i["is_overdue"] for i in inspections)

    return {
        "id": asset.id,
        "resource_id": asset.resource_id,
        "asset_number": asset.asset_number,
        "name": name,
        "asset_type": asset_type,
        "manufacturer": manufacturer,
        "model": model,
        "identifier": identifier,
        "resource_number": resource_number,
        "notes": asset.notes,
        "acquisition_date": asset.acquisition_date,
        "acquisition_cost": asset.acquisition_cost,
        "recurring_cost_per_month": asset.recurring_cost_per_month,
        "cost_notes": asset.cost_notes,
        "active": asset.active,
        "is_due": is_due,
        "is_overdue": is_overdue,
        "next_due_date": next_due_date,
        "inspections": inspections,
    }


def _asset_query():
    return select(OperationalAsset).options(
        selectinload(OperationalAsset.resource), selectinload(OperationalAsset.inspections)
    )


def _load(db: Session, asset_id: int) -> OperationalAsset | None:
    return db.scalar(_asset_query().where(OperationalAsset.id == asset_id))


def get_asset(db: Session, asset_id: int) -> dict | None:
    asset = _load(db, asset_id)
    if asset is None:
        return None
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return asset_to_dict(asset, lead_days)


def list_assets(db: Session, *, include_inactive: bool = True) -> list[dict]:
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    query = _asset_query()
    if not include_inactive:
        query = query.where(OperationalAsset.active == True)  # noqa: E712
    query = query.order_by(OperationalAsset.name)
    return [asset_to_dict(a, lead_days) for a in db.scalars(query).all()]


def list_due_assets(db: Session) -> list[dict]:
    """Für die Übersicht in master_data.html UND das Dashboard-Widget -- nur Assets, bei
    denen mindestens eine Prüffrist fällig oder überfällig ist."""
    return [a for a in list_assets(db, include_inactive=False) if a["is_due"] or a["is_overdue"]]


def _validate_resource_not_taken(db: Session, resource_id: int | None, *, exclude_asset_id: int | None = None) -> None:
    if resource_id is None:
        return
    query = select(OperationalAsset.id).where(OperationalAsset.resource_id == resource_id)
    if exclude_asset_id is not None:
        query = query.where(OperationalAsset.id != exclude_asset_id)
    if db.scalar(query.limit(1)) is not None:
        raise ValueError("Diese Ressource ist bereits einem anderen Betriebsmittel zugeordnet.")


def create_asset(db: Session, payload: dict) -> dict:
    resource_id = payload.get("resource_id")
    if resource_id is not None and db.get(OperationalResource, resource_id) is None:
        raise ValueError(f"Ressource #{resource_id} wurde nicht gefunden.")
    _validate_resource_not_taken(db, resource_id)

    own_fields = {"name", "asset_type", "manufacturer", "model", "identifier"}
    asset = OperationalAsset(
        resource_id=resource_id,
        asset_number=payload.get("asset_number"),
        notes=payload.get("notes"),
        acquisition_date=payload.get("acquisition_date"),
        acquisition_cost=payload.get("acquisition_cost"),
        recurring_cost_per_month=payload.get("recurring_cost_per_month"),
        cost_notes=payload.get("cost_notes"),
        active=payload.get("active", True),
        **{k: (None if resource_id is not None else payload.get(k)) for k in own_fields},
    )
    db.add(asset)
    db.commit()
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return asset_to_dict(_load(db, asset.id), lead_days)


def update_asset(db: Session, asset_id: int, payload: dict) -> dict | None:
    asset = db.get(OperationalAsset, asset_id)
    if asset is None:
        return None
    resource_id = payload.get("resource_id")
    if resource_id is not None and db.get(OperationalResource, resource_id) is None:
        raise ValueError(f"Ressource #{resource_id} wurde nicht gefunden.")
    _validate_resource_not_taken(db, resource_id, exclude_asset_id=asset_id)

    own_fields = ("name", "asset_type", "manufacturer", "model", "identifier")
    asset.resource_id = resource_id
    for field in own_fields:
        setattr(asset, field, None if resource_id is not None else payload.get(field))
    asset.asset_number = payload.get("asset_number")
    asset.notes = payload.get("notes")
    asset.acquisition_date = payload.get("acquisition_date")
    asset.acquisition_cost = payload.get("acquisition_cost")
    asset.recurring_cost_per_month = payload.get("recurring_cost_per_month")
    asset.cost_notes = payload.get("cost_notes")
    asset.active = payload.get("active", True)
    db.commit()
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return asset_to_dict(_load(db, asset.id), lead_days)


def delete_asset(db: Session, asset_id: int) -> bool:
    """Löscht das Betriebsmittel samt seiner Prüffristen (ORM-Cascade) UND deren
    Dokumenten von der Festplatte. Die verknüpfte OperationalResource selbst bleibt davon
    unberührt -- ein Betriebsmittel löschen darf nie die zugrunde liegende Ressource
    (und damit deren Planungshistorie) mitreißen."""
    asset = db.get(OperationalAsset, asset_id)
    if asset is None:
        return False
    for inspection in list(asset.inspections):
        delete_document_file(inspection.document_filename)
    db.delete(asset)
    db.commit()
    return True


def create_inspection(db: Session, asset_id: int, payload: dict) -> dict | None:
    asset = db.get(OperationalAsset, asset_id)
    if asset is None:
        return None
    inspection = OperationalAssetInspection(
        asset_id=asset_id,
        inspection_type=payload["inspection_type"].strip(),
        interval_months=payload.get("interval_months"),
        last_inspection_date=payload.get("last_inspection_date"),
        next_due_date=payload.get("next_due_date"),
        inspector=payload.get("inspector"),
        notes=payload.get("notes"),
    )
    db.add(inspection)
    db.commit()
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return _inspection_to_dict(inspection, lead_days)


def update_inspection(db: Session, inspection_id: int, payload: dict) -> dict | None:
    inspection = db.get(OperationalAssetInspection, inspection_id)
    if inspection is None:
        return None
    inspection.inspection_type = payload["inspection_type"].strip()
    inspection.interval_months = payload.get("interval_months")
    inspection.last_inspection_date = payload.get("last_inspection_date")
    inspection.next_due_date = payload.get("next_due_date")
    inspection.inspector = payload.get("inspector")
    inspection.notes = payload.get("notes")
    db.commit()
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return _inspection_to_dict(inspection, lead_days)


def delete_inspection(db: Session, inspection_id: int) -> bool:
    inspection = db.get(OperationalAssetInspection, inspection_id)
    if inspection is None:
        return False
    delete_document_file(inspection.document_filename)
    db.delete(inspection)
    db.commit()
    return True


def set_inspection_document(db: Session, inspection_id: int, stored_filename: str, original_name: str) -> dict | None:
    inspection = db.get(OperationalAssetInspection, inspection_id)
    if inspection is None:
        return None
    delete_document_file(inspection.document_filename)
    inspection.document_filename = stored_filename
    inspection.document_original_name = original_name
    db.commit()
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return _inspection_to_dict(inspection, lead_days)


def remove_inspection_document(db: Session, inspection_id: int) -> dict | None:
    inspection = db.get(OperationalAssetInspection, inspection_id)
    if inspection is None:
        return None
    delete_document_file(inspection.document_filename)
    inspection.document_filename = None
    inspection.document_original_name = None
    db.commit()
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return _inspection_to_dict(inspection, lead_days)
