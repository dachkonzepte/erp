"""Dachflächen und Bauteile (seit 1.2.14) -- ein Dachdeckerbetrieb wartet nicht "ein Objekt"
(Property), sondern einzelne Dachflächen (RoofArea), die aus einzelnen Bauteilen
(RoofComponent) bestehen. Erst auf Bauteil-Ebene werden spätere Prüfpunkte/Mängel/Historie
fachlich sinnvoll.

Bewusst KEINE is_module_enabled("wartungen")-Prüfung hier oder im zugehörigen Router: Property
ist Kern-Stammdatum ohne Eintrag in OPTIONAL_MODULES, Dachflächen/Bauteile daran zu koppeln
würde bei deaktiviertem Modul "wartungen" Stammdaten verstecken."""

from datetime import date
from decimal import Decimal

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    Finding, InspectionItem, InspectionTemplateItem, MaintenanceContractItem, Property, RoofArea,
    RoofComponent, RoofComponentType, RoofLayer, RoofLayerType, ServiceReport,
)
from .roof_area_sketches import delete_sketch_file, replace_sketch


@event.listens_for(RoofArea, "before_delete")
def _delete_roof_area_sketch_file(mapper, connection, target: RoofArea) -> None:
    """Feuert für JEDEN ORM-Löschweg einer RoofArea -- direkt über delete_roof_area() genauso
    wie kaskadiert über Property.roof_areas (cascade="all, delete-orphan"). Ohne dieses Event
    würde eine kaskadierte Löschung (z. B. ein künftiges db.delete(property)) die Zeile zwar
    entfernen, die Skizzendatei aber verwaist auf der Festplatte zurücklassen, da
    delete_roof_area() selbst dabei nie durchlaufen wird."""
    delete_sketch_file(target.sketch_path)


def roof_area_to_dict(roof_area: RoofArea) -> dict:
    prop = roof_area.property
    return {
        "id": roof_area.id,
        "property_id": roof_area.property_id,
        "property_name": prop.name if prop else None,
        "customer_id": prop.customer_id if prop else None,
        "customer_name": prop.customer.name if prop and prop.customer else None,
        "name": roof_area.name,
        "roof_type": roof_area.roof_type,
        "covering": roof_area.covering,
        "pitch_degrees": roof_area.pitch_degrees,
        "area_sqm": roof_area.area_sqm,
        "build_up": roof_area.build_up,
        "insulation": roof_area.insulation,
        "last_renovation": roof_area.last_renovation,
        "contractor": roof_area.contractor,
        "warranty_until": roof_area.warranty_until,
        "has_sketch": roof_area.sketch_path is not None,
        "notes": roof_area.notes,
        "archived": roof_area.archived,
        "component_count": len(roof_area.components),
        "created_at": roof_area.created_at,
        "updated_at": roof_area.updated_at,
    }


def roof_component_to_dict(component: RoofComponent, db: Session | None = None) -> dict:
    """finding_count (seit 1.2.17) ist eine einfache COUNT-Abfrage -- akzeptierter
    N+1-Charakter wie beim Rest dieser Funktion, Bauteilzahl je Dachfläche liegt im niedrigen
    zweistelligen Bereich. Ohne übergebene db (z. B. innerhalb eines frisch konstruierten,
    noch nicht gespeicherten Objekts) bleibt der Zähler 0."""
    finding_count = (
        db.scalar(select(func.count(Finding.id)).where(Finding.roof_component_id == component.id))
        if db is not None else 0
    )
    return {
        "id": component.id,
        "roof_area_id": component.roof_area_id,
        "component_type": component.component_type,
        "name": component.name,
        "quantity": component.quantity,
        "unit": component.unit,
        "year_built": component.year_built,
        "sketch_x": component.sketch_x,
        "sketch_y": component.sketch_y,
        "sketch_w": component.sketch_w,
        "sketch_h": component.sketch_h,
        "sort_order": component.sort_order,
        "notes": component.notes,
        "archived": component.archived,
        "finding_count": finding_count,
        "created_at": component.created_at,
        "updated_at": component.updated_at,
    }


def _load_roof_area(db: Session, roof_area_id: int) -> RoofArea | None:
    return db.scalar(
        select(RoofArea)
        .options(
            selectinload(RoofArea.property).selectinload(Property.customer),
            selectinload(RoofArea.components),
        )
        .where(RoofArea.id == roof_area_id)
    )


def list_roof_areas(db: Session, property_id: int, include_archived: bool = False) -> list[dict]:
    query = (
        select(RoofArea)
        .options(selectinload(RoofArea.property).selectinload(Property.customer), selectinload(RoofArea.components))
        .where(RoofArea.property_id == property_id)
    )
    if not include_archived:
        query = query.where(RoofArea.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(RoofArea.name)
    return [roof_area_to_dict(r) for r in db.scalars(query).all()]


def get_roof_area(db: Session, roof_area_id: int) -> dict | None:
    roof_area = _load_roof_area(db, roof_area_id)
    return roof_area_to_dict(roof_area) if roof_area else None


def create_roof_area(
    db: Session, property_id: int, name: str, roof_type: str | None = None, covering: str | None = None,
    pitch_degrees: Decimal | None = None, area_sqm: Decimal | None = None,
    last_renovation: date | None = None, contractor: str | None = None,
    warranty_until: date | None = None, notes: str | None = None,
) -> dict:
    """Seit 1.2.18 OHNE build_up/insulation-Parameter -- die Schichtenliste (RoofLayer) hat das
    Freitextfeld abgelöst, siehe RoofArea-Docstring in app/models.py. Neue Dachflächen starten
    ohne Altbestand-Text, es gibt also keinen Übernahmefall."""
    if db.get(Property, property_id) is None:
        raise ValueError("Objekt nicht gefunden.")
    name = name.strip()
    if not name:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    roof_area = RoofArea(
        property_id=property_id, name=name, roof_type=roof_type, covering=covering,
        pitch_degrees=pitch_degrees, area_sqm=area_sqm,
        last_renovation=last_renovation, contractor=contractor, warranty_until=warranty_until,
        notes=(notes or None),
    )
    db.add(roof_area)
    db.commit()
    return roof_area_to_dict(_load_roof_area(db, roof_area.id))


def update_roof_area(
    db: Session, roof_area_id: int, name: str, roof_type: str | None = None, covering: str | None = None,
    pitch_degrees: Decimal | None = None, area_sqm: Decimal | None = None,
    last_renovation: date | None = None, contractor: str | None = None,
    warranty_until: date | None = None, notes: str | None = None,
) -> dict | None:
    """Seit 1.2.18 OHNE build_up/insulation-Parameter -- **bewusst**, nicht nur zur
    Vereinfachung: der bisherige Parameter build_up: str | None = None hätte bei jedem Speichern
    über das neue, reduzierte Formular (das dieses Feld gar nicht mehr sendet) automatisch None
    übernommen und damit einen vorhandenen Altbestand-Text bei der nächsten Änderung eines
    BELIEBIGEN anderen Feldes stillschweigend gelöscht. build_up/insulation bleiben in der
    Datenbank und in roof_area_to_dict() lesbar, aber ab hier für immer unverändert."""
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        return None
    name = name.strip()
    if not name:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    roof_area.name = name
    roof_area.roof_type = roof_type
    roof_area.covering = covering
    roof_area.pitch_degrees = pitch_degrees
    roof_area.area_sqm = area_sqm
    roof_area.last_renovation = last_renovation
    roof_area.contractor = contractor
    roof_area.warranty_until = warranty_until
    roof_area.notes = notes or None
    db.commit()
    return roof_area_to_dict(_load_roof_area(db, roof_area.id))


def create_roof_areas_bulk(db: Session, property_id: int, roof_type: str, names: list[str]) -> list[dict]:
    """Mehrere Dachflächen desselben Dachtyps in einem Schritt (seit 1.2.18) -- ein Gebäude hat
    selten nur eine Dachfläche. Ruft create_roof_area() unverändert je nicht-leerem Namen auf,
    kein Nachbau der dortigen Validierung. Leere Namenszeilen (z. B. unbenutzte Vorbelegung im
    Formular) werden übersprungen, nicht als Fehler gewertet."""
    cleaned = [n.strip() for n in names if n and n.strip()]
    if not cleaned:
        raise ValueError("Bitte mindestens eine Bezeichnung angeben.")
    return [create_roof_area(db, property_id, name, roof_type=roof_type) for name in cleaned]


def set_roof_area_archived(db: Session, roof_area_id: int, archived: bool) -> dict | None:
    """Rein informatives Aus-/Einblenden aus der Standardliste (gleiches Muster wie
    set_project_archived()/set_contract_archived()) -- jederzeit umkehrbar. Echtes Löschen
    (delete_roof_area()) bleibt zusätzlich möglich, da es sich um Planungs-Stammdaten und
    nicht um ein GoBD-Dokument handelt."""
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        return None
    roof_area.archived = archived
    db.commit()
    return roof_area_to_dict(_load_roof_area(db, roof_area.id))


def delete_roof_area(db: Session, roof_area_id: int) -> bool:
    """Löscht die Dachfläche endgültig, kaskadiert per ORM auf ihre Bauteile. Die Skizzendatei
    räumt ausschließlich das before_delete-Event oben ab -- kein separater
    delete_sketch_file()-Aufruf hier, eine Quelle der Wahrheit, die auch den über
    Property.roof_areas kaskadierten Löschweg abdeckt.

    Blockiert (seit 1.2.15), solange eine MaintenanceContractItem noch auf diese Dachfläche
    verweist -- SQLite erzwingt Fremdschlüssel in diesem Projekt nicht selbst
    (app/database.py setzt kein PRAGMA foreign_keys=ON), ein ungeprüftes Löschen würde also
    eine tote Fremdschlüsselzeile zurücklassen."""
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        return False
    if db.scalar(select(MaintenanceContractItem.id).where(MaintenanceContractItem.roof_area_id == roof_area_id).limit(1)):
        raise ValueError("Diese Dachfläche wird noch in einem Wartungsvertrag als Position verwendet.")
    db.delete(roof_area)
    db.commit()
    return True


def set_roof_area_sketch(db: Session, roof_area_id: int, original_filename: str, data: bytes) -> dict | None:
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        return None
    roof_area.sketch_path = replace_sketch(roof_area.sketch_path, original_filename, data)
    db.commit()
    return roof_area_to_dict(_load_roof_area(db, roof_area.id))


def clear_roof_area_sketch(db: Session, roof_area_id: int) -> dict | None:
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        return None
    delete_sketch_file(roof_area.sketch_path)
    roof_area.sketch_path = None
    db.commit()
    return roof_area_to_dict(_load_roof_area(db, roof_area.id))


def list_roof_components(db: Session, roof_area_id: int, include_archived: bool = False) -> list[dict]:
    query = select(RoofComponent).where(RoofComponent.roof_area_id == roof_area_id)
    if not include_archived:
        query = query.where(RoofComponent.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(RoofComponent.sort_order, RoofComponent.id)
    return [roof_component_to_dict(c, db) for c in db.scalars(query).all()]


def create_roof_component(
    db: Session, roof_area_id: int, name: str, component_type: str | None = None,
    quantity: Decimal | None = None, unit: str | None = None, year_built: int | None = None,
    sort_order: int = 100, notes: str | None = None,
) -> dict:
    if db.get(RoofArea, roof_area_id) is None:
        raise ValueError("Dachfläche nicht gefunden.")
    name = name.strip()
    if not name:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    component = RoofComponent(
        roof_area_id=roof_area_id, name=name, component_type=component_type, quantity=quantity,
        unit=unit, year_built=year_built, sort_order=sort_order, notes=(notes or None),
    )
    db.add(component)
    db.commit()
    db.refresh(component)
    return roof_component_to_dict(component, db)


def update_roof_component(
    db: Session, component_id: int, name: str, component_type: str | None = None,
    quantity: Decimal | None = None, unit: str | None = None, year_built: int | None = None,
    sort_order: int = 100, notes: str | None = None,
) -> dict | None:
    component = db.get(RoofComponent, component_id)
    if component is None:
        return None
    name = name.strip()
    if not name:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    component.name = name
    component.component_type = component_type
    component.quantity = quantity
    component.unit = unit
    component.year_built = year_built
    component.sort_order = sort_order
    component.notes = notes or None
    db.commit()
    db.refresh(component)
    return roof_component_to_dict(component, db)


def set_roof_component_position(
    db: Session, component_id: int, sketch_x: Decimal, sketch_y: Decimal,
    sketch_w: Decimal | None = None, sketch_h: Decimal | None = None,
) -> dict | None:
    """Eigene, schlanke Funktion nur für den Klick/Zug-auf-Skizze-Fall -- setzt ausschließlich
    die Position, ohne das restliche Formular anzufassen. sketch_w/sketch_h (seit 1.2.19) sind
    beide None für einen Punktmarker (Klick) oder beide gesetzt für ein Rechteck (Ziehen) -- ein
    einziger Aufrufer legt in einem Zug fest, was gemeint ist, deshalb hier bewusst KEIN
    exclude_unset-Feld-Dict wie bei upsert_roof_layer(): es gibt keinen zweiten, unabhängigen
    Aufrufer, der nur einen Teil dieser vier Werte ändern wollte."""
    component = db.get(RoofComponent, component_id)
    if component is None:
        return None
    component.sketch_x = sketch_x
    component.sketch_y = sketch_y
    component.sketch_w = sketch_w
    component.sketch_h = sketch_h
    db.commit()
    db.refresh(component)
    return roof_component_to_dict(component, db)


def set_roof_component_archived(db: Session, component_id: int, archived: bool) -> dict | None:
    component = db.get(RoofComponent, component_id)
    if component is None:
        return None
    component.archived = archived
    db.commit()
    db.refresh(component)
    return roof_component_to_dict(component, db)


def delete_roof_component(db: Session, component_id: int) -> bool:
    """Blockiert (seit 1.2.16), solange ein InspectionItem eines bereits UNTERSCHRIEBENEN
    Berichts noch auf dieses Bauteil verweist -- exakt das Muster von delete_roof_area()
    (1.2.15), nur eine Ebene tiefer. Ein aktueller InspectionItem bräuchte das eigentlich nicht
    (kopiert seinen Text physisch, siehe app/service_reports.py), aber die für die nächste
    Iteration geplante Mängelhistorie wird roof_component_id aktiv dereferenzieren -- den
    Schutz dann nachzurüsten wäre eine Verhaltensänderung an einem bereits benutzten Endpunkt.
    set_roof_component_archived() bleibt bewusst unverändert und uneingeschränkt möglich.

    Seit 1.2.17 zusätzlich, UNABHÄNGIG vom Berichtsstatus: blockiert, solange irgendein Finding
    (Mangel) auf dieses Bauteil verweist -- ein Finding entfaltet seine Wirkung (Folgeauftrag,
    Aufgabe, Wiedervorlage) bereits während der Bericht noch Entwurf ist, die Mängelhistorie
    darf deshalb nicht erst ab der Unterschrift geschützt sein."""
    component = db.get(RoofComponent, component_id)
    if component is None:
        return False
    if db.scalar(
        select(InspectionItem.id).join(ServiceReport, InspectionItem.service_report_id == ServiceReport.id)
        .where(InspectionItem.roof_component_id == component_id, ServiceReport.status == "unterschrieben").limit(1)
    ):
        raise ValueError("Dieses Bauteil wird in einem bereits unterschriebenen Einsatzbericht referenziert und kann nicht gelöscht werden.")
    if db.scalar(select(Finding.id).where(Finding.roof_component_id == component_id).limit(1)):
        raise ValueError("Für dieses Bauteil sind Mängel erfasst -- es kann daher nicht gelöscht werden.")
    db.delete(component)
    db.commit()
    return True


# --- Dachaufbau als Schichtenliste (RoofLayerType/RoofLayer, seit 1.2.18) -- ersetzt
# RoofArea.build_up (Freitext) und RoofArea.insulation, siehe Docstrings in app/models.py.
# Bewusst ebenfalls KEINE is_module_enabled()-Prüfung: Schichttypen beschreiben physische
# Bausubstanz, kein Modul "Wartungen" (gleiche Begründung wie am Dateianfang für
# RoofArea/RoofComponent selbst). ---

def layer_type_to_dict(layer_type: RoofLayerType) -> dict:
    return {
        "id": layer_type.id,
        "key": layer_type.key,
        "label": layer_type.label,
        "roof_type": layer_type.roof_type,
        "option_group": layer_type.option_group,
        "has_execution": layer_type.has_execution,
        "has_thickness": layer_type.has_thickness,
        "has_notes": layer_type.has_notes,
        "sort_order": layer_type.sort_order,
        "active": layer_type.active,
    }


def list_layer_types(db: Session, roof_type: str | None = None, include_inactive: bool = False) -> list[dict]:
    """Ohne roof_type-Filter: alle Schichttypen (für die Einstellungen-Verwaltung). Mit Filter:
    ausschließlich Schichttypen mit exakt diesem roof_type -- KEINE automatische Ergänzung von
    roof_type IS NULL, da die Migrations-Seeddaten bewusst keine geteilten NULL-Zeilen anlegen
    (siehe Migration). roof_type IS NULL bleibt als Möglichkeit für künftige, wirklich
    universelle Schichttypen offen, ist aber aktuell ungenutzt."""
    query = select(RoofLayerType)
    if roof_type is not None:
        query = query.where(RoofLayerType.roof_type == roof_type)
    if not include_inactive:
        query = query.where(RoofLayerType.active == True)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(RoofLayerType.sort_order, RoofLayerType.id)
    return [layer_type_to_dict(t) for t in db.scalars(query).all()]


def _validate_layer_type_key(key: str) -> str:
    key = key.strip()
    if not key:
        raise ValueError("Bitte einen technischen Schlüssel angeben.")
    return key


def create_layer_type(
    db: Session, key: str, label: str, roof_type: str | None = None, option_group: str | None = None,
    has_execution: bool = True, has_thickness: bool = False, has_notes: bool = True,
) -> dict:
    key = _validate_layer_type_key(key)
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    if db.scalar(select(RoofLayerType.id).where(RoofLayerType.key == key).limit(1)):
        raise ValueError(f"Der Schlüssel \"{key}\" wird bereits verwendet.")
    max_sort = db.scalar(select(func.max(RoofLayerType.sort_order)).where(RoofLayerType.roof_type == roof_type)) or 0
    layer_type = RoofLayerType(
        key=key, label=label, roof_type=(roof_type or None), option_group=(option_group or None),
        has_execution=has_execution, has_thickness=has_thickness, has_notes=has_notes, sort_order=max_sort + 10,
    )
    db.add(layer_type)
    db.commit()
    return layer_type_to_dict(layer_type)


def update_layer_type(
    db: Session, layer_type_id: int, label: str, roof_type: str | None = None, option_group: str | None = None,
    has_execution: bool = True, has_thickness: bool = False, has_notes: bool = True,
) -> dict | None:
    layer_type = db.get(RoofLayerType, layer_type_id)
    if layer_type is None:
        return None
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    layer_type.label = label
    layer_type.roof_type = roof_type or None
    layer_type.option_group = option_group or None
    layer_type.has_execution = has_execution
    layer_type.has_thickness = has_thickness
    layer_type.has_notes = has_notes
    db.commit()
    return layer_type_to_dict(layer_type)


def set_layer_type_active(db: Session, layer_type_id: int, active: bool) -> dict | None:
    layer_type = db.get(RoofLayerType, layer_type_id)
    if layer_type is None:
        return None
    layer_type.active = active
    db.commit()
    return layer_type_to_dict(layer_type)


def reorder_layer_types(db: Session, roof_type: str | None, ordered_ids: list[int]) -> list[dict]:
    """Wie reorder_windows() in app/maintenance_contracts.py, aber auf die Teilmenge mit genau
    diesem roof_type-Wert (inklusive None) begrenzt -- die Einstellungen-Oberfläche sortiert je
    Dachtyp-Gruppe einzeln, eine globale Reihenfolge über alle Dachtypen hinweg ergäbe keinen
    Sinn."""
    group = {
        t.id: t for t in db.scalars(select(RoofLayerType).where(RoofLayerType.roof_type == roof_type)).all()
    }
    if set(ordered_ids) != set(group.keys()):
        raise ValueError("Die Reihenfolge muss alle Schichttypen dieser Dachtyp-Gruppe enthalten.")
    for index, layer_type_id in enumerate(ordered_ids):
        group[layer_type_id].sort_order = index * 10
    db.commit()
    return list_layer_types(db, roof_type=roof_type, include_inactive=True)


def delete_layer_type(db: Session, layer_type_id: int) -> bool:
    """Blockiert (seit 1.2.18), solange ein RoofLayer noch auf diesen Schichttyp verweist --
    exakt das Muster von delete_window() für MaintenanceWindow. set_layer_type_active() bleibt
    uneingeschränkt möglich."""
    layer_type = db.get(RoofLayerType, layer_type_id)
    if layer_type is None:
        return False
    if db.scalar(select(RoofLayer.id).where(RoofLayer.layer_type_id == layer_type_id).limit(1)):
        raise ValueError("Dieser Schichttyp wird noch von mindestens einer Dachfläche verwendet.")
    db.delete(layer_type)
    db.commit()
    return True


def roof_layer_to_dict(layer: RoofLayer) -> dict:
    lt = layer.layer_type
    return {
        "id": layer.id,
        "roof_area_id": layer.roof_area_id,
        "layer_type_id": layer.layer_type_id,
        "layer_type_key": lt.key if lt else None,
        "layer_type_label": lt.label if lt else None,
        "layer_type_roof_type": lt.roof_type if lt else None,
        "layer_type_option_group": lt.option_group if lt else None,
        "layer_type_has_execution": lt.has_execution if lt else True,
        "layer_type_has_thickness": lt.has_thickness if lt else False,
        "layer_type_has_notes": lt.has_notes if lt else True,
        "present": layer.present,
        "execution": layer.execution,
        "thickness_mm": layer.thickness_mm,
        "notes": layer.notes,
    }


def list_roof_layers(db: Session, roof_area_id: int) -> list[dict]:
    """Alle vorhandenen RoofLayer-Zeilen der Dachfläche -- bewusst ungefiltert nach dem
    aktuellen RoofArea.roof_type (siehe Rückfrage zur Planung): eine Zeile, deren Schichttyp
    nach einem Dachtypwechsel nicht mehr passt, bleibt stehen und wird nur in der Oberfläche
    gekennzeichnet. Sortierung nach der sort_order des Schichttyps -- RoofLayer selbst hat keine
    eigene, daher in Python statt per ORM-order_by über die Fremdtabelle."""
    query = (
        select(RoofLayer).options(selectinload(RoofLayer.layer_type))
        .where(RoofLayer.roof_area_id == roof_area_id)
    )
    rows = db.scalars(query).all()
    rows_sorted = sorted(rows, key=lambda l: (l.layer_type.sort_order, l.layer_type.id) if l.layer_type else (0, 0))
    return [roof_layer_to_dict(l) for l in rows_sorted]


_LAYER_UPSERT_FIELDS = {"present", "execution", "thickness_mm", "notes"}


def upsert_roof_layer(db: Session, roof_area_id: int, layer_type_id: int, fields: dict) -> dict:
    """Autosave-Baustein je Zeile (Muster update_inspection_item() in app/service_reports.py) --
    legt die Zeile beim ersten Kontakt mit diesem Schichttyp auf dieser Dachfläche mit den
    Modell-Defaults an, sonst aktualisiert sie dieselbe ((roof_area_id, layer_type_id) ist
    eindeutig).

    Seit 1.2.19 überschreibt diese Funktion NUR NOCH die in fields tatsächlich enthaltenen
    Schlüssel (Router: payload.model_dump(exclude_unset=True), unterscheidet "Feld nicht
    mitgeschickt" von "Feld ausdrücklich auf null gesetzt"). Vorher überschrieb jeder Aufruf
    unbedingt alle vier Spalten -- in Kombination mit parallelen, ungebremsten
    Autosave-Aufrufen aus roof_area.html (setLayerPresent() feuert saveLayerField() ohne
    await, kurz gefolgt vom Speichern eines eingetippten Bemerkungstexts) konnte ein älterer
    Schnappschuss, der beim Server zuletzt committete, einen neueren überschreiben -- empirisch
    nachgestellt bei der Planung dieser Version. Ein fehlender Schlüssel lässt die Spalte
    unverändert, ein ausdrücklich gesendetes null leert sie bewusst."""
    if db.get(RoofArea, roof_area_id) is None:
        raise ValueError("Dachfläche nicht gefunden.")
    if db.get(RoofLayerType, layer_type_id) is None:
        raise ValueError("Schichttyp nicht gefunden.")
    layer = db.scalar(
        select(RoofLayer).where(RoofLayer.roof_area_id == roof_area_id, RoofLayer.layer_type_id == layer_type_id)
    )
    if layer is None:
        layer = RoofLayer(roof_area_id=roof_area_id, layer_type_id=layer_type_id)
        db.add(layer)
    for key, value in fields.items():
        if key not in _LAYER_UPSERT_FIELDS:
            continue
        if key in ("execution", "notes") and value == "":
            value = None
        setattr(layer, key, value)
    db.commit()
    db.refresh(layer)
    return roof_layer_to_dict(layer)


# --- Bauteilarten als echte Tabelle (seit 1.2.19, vorher SettingOptionGroup "roof_component_types")
# -- Muster 1:1 wie die RoofLayerType-Funktionen oben. Bewusst ebenfalls KEINE
# is_module_enabled()-Prüfung, gleiche Begründung. ---

def component_type_to_dict(component_type: RoofComponentType) -> dict:
    return {
        "id": component_type.id,
        "key": component_type.key,
        "label": component_type.label,
        "is_area": component_type.is_area,
        "sort_order": component_type.sort_order,
        "active": component_type.active,
    }


def list_component_types(db: Session, include_inactive: bool = False) -> list[dict]:
    query = select(RoofComponentType)
    if not include_inactive:
        query = query.where(RoofComponentType.active == True)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(RoofComponentType.sort_order, RoofComponentType.id)
    return [component_type_to_dict(t) for t in db.scalars(query).all()]


def create_component_type(db: Session, key: str, label: str, is_area: bool = False) -> dict:
    key = key.strip()
    if not key:
        raise ValueError("Bitte einen technischen Schlüssel angeben.")
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    if db.scalar(select(RoofComponentType.id).where(RoofComponentType.key == key).limit(1)):
        raise ValueError(f"Der Schlüssel \"{key}\" wird bereits verwendet.")
    max_sort = db.scalar(select(func.max(RoofComponentType.sort_order))) or 0
    component_type = RoofComponentType(key=key, label=label, is_area=is_area, sort_order=max_sort + 10)
    db.add(component_type)
    db.commit()
    return component_type_to_dict(component_type)


def update_component_type(db: Session, component_type_id: int, label: str, is_area: bool = False) -> dict | None:
    component_type = db.get(RoofComponentType, component_type_id)
    if component_type is None:
        return None
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    component_type.label = label
    component_type.is_area = is_area
    db.commit()
    return component_type_to_dict(component_type)


def set_component_type_active(db: Session, component_type_id: int, active: bool) -> dict | None:
    component_type = db.get(RoofComponentType, component_type_id)
    if component_type is None:
        return None
    component_type.active = active
    db.commit()
    return component_type_to_dict(component_type)


def reorder_component_types(db: Session, ordered_ids: list[int]) -> list[dict]:
    all_types = {t.id: t for t in db.scalars(select(RoofComponentType)).all()}
    if set(ordered_ids) != set(all_types.keys()):
        raise ValueError("Die Reihenfolge muss alle Bauteilarten enthalten.")
    for index, component_type_id in enumerate(ordered_ids):
        all_types[component_type_id].sort_order = index * 10
    db.commit()
    return list_component_types(db, include_inactive=True)


def delete_component_type(db: Session, component_type_id: int) -> bool:
    """Blockiert, solange der key-Wert noch von einem RoofComponent ODER einem
    InspectionTemplateItem als component_type getragen wird -- reiner String-Vergleich, da
    component_type bewusst kein Fremdschlüssel ist (siehe Klassen-Docstring von
    RoofComponentType)."""
    component_type = db.get(RoofComponentType, component_type_id)
    if component_type is None:
        return False
    key = component_type.key
    if db.scalar(select(RoofComponent.id).where(RoofComponent.component_type == key).limit(1)):
        raise ValueError("Diese Bauteilart wird noch von mindestens einem Bauteil verwendet.")
    if db.scalar(select(InspectionTemplateItem.id).where(InspectionTemplateItem.component_type == key).limit(1)):
        raise ValueError("Diese Bauteilart wird noch von mindestens einer Prüfvorlage verwendet.")
    db.delete(component_type)
    db.commit()
    return True
