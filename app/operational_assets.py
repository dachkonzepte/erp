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
den Projekt-Pipeline-Spalten).

Automatische Fälligkeitsberechnung (seit 1.4.2, _compute_next_due_date()): next_due_date wird
nicht mehr direkt vom Client übernommen, sobald interval_months gesetzt ist -- stattdessen
IMMER aus dem tatsächlichen last_inspection_date (oder, beim allerersten Anlegen ohne dieses,
aus dem Anschaffungsdatum des Betriebsmittels) plus Intervall minus einen Tag berechnet. Der
entscheidende Punkt: eine verspätet erledigte Prüfung verschiebt den GESAMTEN Rhythmus mit --
die Basis ist immer das zuletzt tatsächliche Prüfdatum, nie eine kumulative Fortschreibung ab
dem ursprünglichen Anschaffungsdatum (siehe tests/test_v278_operational_assets_erweiterungen.py
für den Belegtest). Eine Prüffrist ohne interval_months (einmalige Prüfung) bleibt vollständig
manuell.

Erinnerungs-Aufgabe (check_due_asset_inspections_and_create_reminders()): On-Demand wie
check_due_contracts_and_create_reminders() (app/maintenance_contracts.py) -- läuft nur beim
Aufruf der Stammdaten-Betriebsmittelliste, kein Hintergrundjob. last_reminder_due_date ist
derselbe Idempotenz-Stempel wie bei MaintenanceContract."""

from datetime import date, timedelta

from sqlalchemy import event, select
from sqlalchemy.orm import Session, selectinload

from .date_utils import add_months
from .modules import is_module_enabled
from .models import (
    OperationalAsset, OperationalAssetDocument, OperationalAssetInspection, OperationalAssetSettings,
    OperationalResource, ServiceReportAsset,
)
from .operational_asset_documents import delete_document_file
from .tasks import create_task

MODULE_KEY = "betriebsmittel"


@event.listens_for(OperationalAssetDocument, "before_delete")
def _delete_operational_asset_document_file(mapper, connection, target: OperationalAssetDocument) -> None:
    """Feuert für JEDEN ORM-Löschweg -- direkt über delete_asset_document() genauso wie
    kaskadiert über OperationalAsset.documents (cascade="all, delete-orphan") beim Löschen des
    ganzen Betriebsmittels. Muster app/roof_areas.py::_delete_roof_area_sketch_file()."""
    delete_document_file(target.stored_filename)


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


def resolve_asset_identity(asset: OperationalAsset) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """Löst bei verknüpfter Ressource die Identitätsfelder LIVE auf -- niemals von
    OperationalAsset selbst gelesen, solange resource_id gesetzt ist (siehe Moduldocstring).
    Geteilt zwischen asset_to_dict() (volle Ansicht), asset_field_dict() (Monteur-Ansicht,
    Stufe 2) UND, seit 1.4.2, app/search.py::_operational_asset_row() (Büro-Suche, Punkt 3) --
    damit alle drei Ansichten für dasselbe Asset nie unterschiedliche Namen/Typen zeigen
    könnten. Ohne führenden Unterstrich (seit 1.4.2), da search.py als dritter Aufrufer
    hinzukam -- ein modulübergreifend genutzter Helfer ist kein privates Implementierungsdetail
    mehr."""
    resource = asset.resource
    if resource is not None:
        return resource.name, resource.resource_type, resource.manufacturer, resource.model, resource.identifier, resource.resource_number
    return asset.name, asset.asset_type, asset.manufacturer, asset.model, asset.identifier, None


def asset_field_dict(asset: OperationalAsset) -> dict:
    """Reduzierte Ansicht für die Rolle `field` (Rechtekonzept, Betriebsmittelverwaltung
    Stufe 2, siehe CLAUDE.md) -- ausschließlich Bezeichnung/Art/Hersteller/Modell/
    Bedienungshinweise. Bewusst KEIN Ressourcenbezug, keine Prüffristen, keine Kosten, keine
    Artikelnummer/kein Produktlink, keine Dokumente -- diese Felder gehören zur Beschaffung/
    Planung, nicht zur Bedienung vor Ort."""
    name, asset_type, manufacturer, model, _identifier, _resource_number = resolve_asset_identity(asset)
    return {
        "id": asset.id,
        "name": name,
        "asset_type": asset_type,
        "manufacturer": manufacturer,
        "model": model,
        "usage_notes": asset.usage_notes,
    }


def asset_qr_target_url(base_url: str, asset_id: int) -> str:
    """Baut die vollständige, im QR-Code kodierte Ziel-URL -- inklusive Domain, damit ein Scan
    mit der Telefonkamera direkt die Seite öffnet, ohne dass die Kamera-App einen relativen
    Pfad raten müsste. base_url kommt vom Router (request.base_url oder
    GeneralSettings.public_base_url, siehe routers/operational_assets.py) -- diese Funktion
    kennt selbst keine Domain, damit sie nie hartkodiert werden kann."""
    return f"{base_url.rstrip('/')}/betriebsmittel/{asset_id}"


def _document_to_dict(document: OperationalAssetDocument) -> dict:
    return {
        "id": document.id,
        "asset_id": document.asset_id,
        "document_type": document.document_type,
        "original_filename": document.original_filename,
        "notes": document.notes,
        "uploaded_at": document.uploaded_at,
    }


def asset_to_dict(asset: OperationalAsset, lead_days: int, *, today: date | None = None) -> dict:
    """Löst bei verknüpfter Ressource die Identitätsfelder LIVE auf -- niemals von
    OperationalAsset selbst gelesen, solange resource_id gesetzt ist (siehe Moduldocstring).
    Bewusst die einzige Stelle, die je documents befüllt -- asset_field_dict() (Rolle `field`)
    kennt dieses Feld an keiner Stelle, ein Monteur bekommt es dadurch strukturell nie, auch
    nicht über den QR-Code (siehe Klassendocstring von OperationalAssetDocument)."""
    name, asset_type, manufacturer, model, identifier, resource_number = resolve_asset_identity(asset)

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
        "article_number": asset.article_number,
        "product_url": asset.product_url,
        "usage_notes": asset.usage_notes,
        "acquisition_date": asset.acquisition_date,
        "acquisition_cost": asset.acquisition_cost,
        "recurring_cost_per_month": asset.recurring_cost_per_month,
        "cost_notes": asset.cost_notes,
        "active": asset.active,
        "selectable_in_reports": asset.selectable_in_reports,
        "is_due": is_due,
        "is_overdue": is_overdue,
        "next_due_date": next_due_date,
        "inspections": inspections,
        "documents": [_document_to_dict(d) for d in asset.documents],
    }


def _asset_query():
    return select(OperationalAsset).options(
        selectinload(OperationalAsset.resource), selectinload(OperationalAsset.inspections),
        selectinload(OperationalAsset.documents),
    )


def _load(db: Session, asset_id: int) -> OperationalAsset | None:
    return db.scalar(_asset_query().where(OperationalAsset.id == asset_id))


def get_asset(db: Session, asset_id: int) -> dict | None:
    asset = _load(db, asset_id)
    if asset is None:
        return None
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return asset_to_dict(asset, lead_days)


def get_asset_field(db: Session, asset_id: int) -> dict | None:
    """Reduzierter Einzelabruf für die Rolle `field` (siehe asset_field_dict())."""
    asset = _load(db, asset_id)
    if asset is None:
        return None
    return asset_field_dict(asset)


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


def list_selectable_assets(db: Session) -> list[dict]:
    """Für die Betriebsmittel-Auswahl im Einsatzbericht (Stufe 3, seit 1.4.5) -- ausschließlich
    freigegebene, aktive Assets (selectable_in_reports UND active), im reduzierten Schema
    (asset_field_dict()) für JEDE Rolle, die einen Bericht ausfüllt (Büro/Admin/Monteur
    gleichermaßen): ein Bericht braucht nie Kosten-/Fristendaten, unabhängig davon, wer ihn
    ausfüllt -- dieselbe Reduktion, die field_asset_dict() für die Rolle `field` schon leistet,
    hier bewusst für alle Rollen angewendet (siehe app/routers/operational_assets.py). Sortiert
    nach dem LIVE aufgelösten Namen (nicht der DB-Spalte OperationalAsset.name, die bei
    ressourcenverknüpften Assets NULL bleibt, siehe resolve_asset_identity())."""
    query = _asset_query().where(
        OperationalAsset.selectable_in_reports == True, OperationalAsset.active == True,  # noqa: E712
    )
    rows = [asset_field_dict(a) for a in db.scalars(query).all()]
    rows.sort(key=lambda r: (r["name"] or "").lower())
    return rows


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
        article_number=payload.get("article_number"),
        product_url=payload.get("product_url"),
        usage_notes=payload.get("usage_notes"),
        acquisition_date=payload.get("acquisition_date"),
        acquisition_cost=payload.get("acquisition_cost"),
        recurring_cost_per_month=payload.get("recurring_cost_per_month"),
        cost_notes=payload.get("cost_notes"),
        active=payload.get("active", True),
        selectable_in_reports=payload.get("selectable_in_reports", False),
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
    asset.article_number = payload.get("article_number")
    asset.product_url = payload.get("product_url")
    asset.usage_notes = payload.get("usage_notes")
    asset.acquisition_date = payload.get("acquisition_date")
    asset.acquisition_cost = payload.get("acquisition_cost")
    asset.recurring_cost_per_month = payload.get("recurring_cost_per_month")
    asset.cost_notes = payload.get("cost_notes")
    asset.active = payload.get("active", True)
    asset.selectable_in_reports = payload.get("selectable_in_reports", False)
    db.commit()
    lead_days = get_or_create_operational_asset_settings(db).reminder_lead_days
    return asset_to_dict(_load(db, asset.id), lead_days)


def delete_asset(db: Session, asset_id: int) -> bool:
    """Löscht das Betriebsmittel samt seiner Prüffristen (ORM-Cascade) UND deren
    Dokumenten von der Festplatte. Die verknüpfte OperationalResource selbst bleibt davon
    unberührt -- ein Betriebsmittel löschen darf nie die zugrunde liegende Ressource
    (und damit deren Planungshistorie) mitreißen.

    Blockiert (seit 1.4.5), solange mindestens ein Einsatzbericht dieses Asset über
    ServiceReportAsset.asset_id referenziert -- unabhängig davon, ob der jeweilige Bericht noch
    Entwurf oder bereits unterschrieben ist (bewusst strenger als delete_roof_component(), das
    nur bei bereits unterschriebenen Berichten blockiert: ServiceReportAsset.asset_id ist NICHT
    NULL, ein Löschen würde die Fremdschlüsselbeziehung sonst in JEDEM Fall verletzen, nicht nur
    bei einem Nachweisdokument). Archivieren (active=False) bleibt dafür uneingeschränkt
    möglich -- der übliche Weg, ein nicht mehr genutztes Betriebsmittel auszublenden, ohne seine
    Verwendung in Berichten zu gefährden."""
    asset = db.get(OperationalAsset, asset_id)
    if asset is None:
        return False
    if db.scalar(select(ServiceReportAsset.id).where(ServiceReportAsset.asset_id == asset_id).limit(1)) is not None:
        raise ValueError(
            "Dieses Betriebsmittel ist in mindestens einem Einsatzbericht erfasst und kann nicht "
            "gelöscht werden -- archivieren Sie es stattdessen (Status auf Inaktiv)."
        )
    for inspection in list(asset.inspections):
        delete_document_file(inspection.document_filename)
    db.delete(asset)
    db.commit()
    return True


def _compute_next_due_date(
    interval_months: int | None, last_inspection_date: date | None, acquisition_date: date | None,
) -> date | None:
    """Automatische Fälligkeitsberechnung (siehe Moduldocstring) -- None bedeutet "kein
    Intervall, next_due_date bleibt manuell/vom Client übernommen", NICHT "unbekannt".
    Basis ist last_inspection_date, falls vorhanden (auch beim allerersten Anlegen, wenn eine
    frühere Prüfung nachträglich als last_inspection_date eingetragen wird), sonst das
    Anschaffungsdatum des Betriebsmittels (erste Fälligkeit ohne jede vorherige Prüfung). Fehlt
    beides, kann nichts berechnet werden -- next_due_date wird dann None, nicht der zuletzt
    manuell eingegebene Wert, da sonst kein Ankerdatum für den "nie kumulativ"-Anspruch existiert."""
    if interval_months is None:
        return None
    base = last_inspection_date or acquisition_date
    if base is None:
        return None
    return add_months(base, interval_months) - timedelta(days=1)


def create_inspection(db: Session, asset_id: int, payload: dict) -> dict | None:
    asset = db.get(OperationalAsset, asset_id)
    if asset is None:
        return None
    interval_months = payload.get("interval_months")
    last_inspection_date = payload.get("last_inspection_date")
    next_due_date = _compute_next_due_date(interval_months, last_inspection_date, asset.acquisition_date)
    if interval_months is None:
        next_due_date = payload.get("next_due_date")  # manuell, einmalige Prüfung ohne Intervall
    inspection = OperationalAssetInspection(
        asset_id=asset_id,
        inspection_type=payload["inspection_type"].strip(),
        interval_months=interval_months,
        last_inspection_date=last_inspection_date,
        next_due_date=next_due_date,
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
    interval_months = payload.get("interval_months")
    last_inspection_date = payload.get("last_inspection_date")
    next_due_date = _compute_next_due_date(interval_months, last_inspection_date, inspection.asset.acquisition_date)
    if interval_months is None:
        next_due_date = payload.get("next_due_date")  # manuell, einmalige Prüfung ohne Intervall
    inspection.inspection_type = payload["inspection_type"].strip()
    inspection.interval_months = interval_months
    inspection.last_inspection_date = last_inspection_date
    inspection.next_due_date = next_due_date
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


def create_asset_document(db: Session, asset_id: int, *, document_type: str, notes: str | None,
                           stored_filename: str, original_filename: str) -> dict | None:
    """Anders als set_inspection_document() (1:1 je Prüffrist, ersetzt immer die vorherige
    Datei) legt dies IMMER eine neue, unabhängige Zeile an -- ein Betriebsmittel kann beliebig
    viele Dokumente tragen (Anschaffungsrechnung UND Leasingvertrag UND ...). Der Aufrufer
    (Router) validiert Content-Type/Größe und speichert die Datei VOR diesem Aufruf -- schlägt
    die Zuordnung fehl (Asset nicht gefunden), bleibt die Datei bewusst auf der Platte liegen
    statt hier nachträglich aufgeräumt zu werden; der Router prüft die Asset-Existenz deshalb
    VOR dem Speichern der Datei, nicht danach (siehe routers/operational_assets.py)."""
    asset = db.get(OperationalAsset, asset_id)
    if asset is None:
        return None
    document = OperationalAssetDocument(
        asset_id=asset_id, document_type=document_type.strip(), notes=(notes or None),
        stored_filename=stored_filename, original_filename=original_filename,
    )
    db.add(document)
    db.commit()
    return _document_to_dict(document)


def delete_asset_document(db: Session, document_id: int) -> bool:
    """db.delete() löst das before_delete-Event oben aus, das die Datei von der Festplatte
    entfernt -- kein separater delete_document_file()-Aufruf hier nötig (Muster
    app/service_reports.py::delete_photo())."""
    document = db.get(OperationalAssetDocument, document_id)
    if document is None:
        return False
    db.delete(document)
    db.commit()
    return True


def check_due_asset_inspections_and_create_reminders(db: Session) -> list[int]:
    """On-Demand-Erinnerung (kein Scheduler) -- Muster
    check_due_contracts_and_create_reminders() (app/maintenance_contracts.py): läuft nur beim
    Aufruf der Stammdaten-Betriebsmittelliste (master_data.html), nicht als Hintergrundjob.
    last_reminder_due_date verhindert, dass ein erneuter Seitenaufruf für dieselbe Fälligkeit
    doppelt erinnert -- OHNE expliziten Reset an anderer Stelle nötig: ändert sich
    next_due_date (Neuberechnung nach einer Prüfung), unterscheidet es sich automatisch vom
    alten Stempel, die Gleichheitsprüfung unten wird dadurch von selbst wieder False.

    Die Aufgabe geht bewusst UNASSIGNED ("allgemein ans Büro") statt an einen konkreten
    Mitarbeiter -- es gibt (anders als bei MaintenanceContract.responsible_employee_id) kein
    Feld für einen Zuständigen je Betriebsmittel oder Modul-Einstellung. Für die reale, aktuell
    ausschließlich aus Admin-Konten bestehende Installation ist das folgenlos; sobald echte
    Büro-Konten ohne Admin-Rolle existieren, sehen NUR Admins eine unassigned Aufgabe
    (GET /api/tasks filtert für jeden Nicht-Admin auf assigned_employee_id==eigene_id,
    siehe app/routers/tasks.py) -- ein bereits bestehendes, allgemeines Verhalten des
    Aufgabenmoduls, keine für dieses Feature neu eingeführte Lücke."""
    if not is_module_enabled(db, "aufgabenmanagement"):
        return []
    settings = get_or_create_operational_asset_settings(db)
    threshold = date.today() + timedelta(days=settings.reminder_lead_days)
    due = db.scalars(
        select(OperationalAssetInspection)
        .options(selectinload(OperationalAssetInspection.asset).selectinload(OperationalAsset.resource))
        .where(
            OperationalAssetInspection.next_due_date.is_not(None),
            OperationalAssetInspection.next_due_date <= threshold,
        )
    ).all()
    reminded = []
    for inspection in due:
        if inspection.last_reminder_due_date == inspection.next_due_date:
            continue
        asset = inspection.asset
        name, *_rest = resolve_asset_identity(asset)
        create_task(
            db, title=f"Prüffrist fällig: {name} -- {inspection.inspection_type}",
            description=(
                f"Prüffrist \"{inspection.inspection_type}\" für Betriebsmittel \"{name}\" ist am "
                f"{inspection.next_due_date.strftime('%d.%m.%Y')} fällig."
            ),
            source_module="betriebsmittel", source_label=f"Betriebsmittel {name}",
            source_url=f"/betriebsmittel/{asset.id}",
        )
        inspection.last_reminder_due_date = inspection.next_due_date
        reminded.append(inspection.id)
    if reminded:
        db.commit()
    return reminded
