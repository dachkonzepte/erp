"""Digitale Einsatzberichte (seit 1.2.1, Modul "wartungen") -- Rapportbericht bei
Reparaturen, Wartungsbericht bei Wartungen. Siehe app/models.py::ServiceReport für die
Begründung, warum der Bericht am Order (nicht am MaintenanceContract) hängt.

sign_service_report() ist der erste echte Aufrufer der Automatisierungs-Anschlussstelle
(create_task() in app/tasks.py) außerhalb der Wartungsverträge selbst: die Unterschrift löst
eine "Rechnung erstellen"-Aufgabe für den Sachbearbeiter des Auftrags aus.

Strukturierte Prüfpunkte (InspectionItem, seit 1.2.16): create_report() "multipliziert" eine
InspectionTemplate gegen den tatsächlichen Bauteilbestand der betroffenen Dachfläche
(_generate_inspection_items()) -- alles Anzeige-relevante wird dabei PHYSISCH auf InspectionItem
kopiert, nie zur Laufzeit von der Vorlage gelesen, damit sich ein bereits erzeugter Bericht bei
einer späteren Vorlagenänderung nicht rückwirkend ändert. sync_inspection_items() (rein additiv)
und regenerate_inspection_items() (vollständiger Neuaufbau, nur Entwurf) sind die beiden
Antworten auf einen sich zwischen Berichtsanlage und Ausführung ändernden Bauteilbestand."""

import os
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session, selectinload

from .date_utils import add_months
from .document_storage import make_stored_filename
from .inspection_templates import ITEM_TYPES
from .modules import is_module_enabled
from .paths import data_dir
from .models import (
    Finding, InspectionItem, InspectionTemplate, InspectionTemplateItem, MaintenanceContract,
    MaintenanceContractItem, Material, Order, Project, RoofArea, RoofTypeInspectionTemplateDefault, ServiceReport,
    ServiceReportMaterial, ServiceReportPhoto, ServiceReportRoofArea, Task,
)
from .roof_areas import list_roof_areas
from .service_report_photos import delete_photo_file, resize_and_store_photo
from .tasks import create_task


@event.listens_for(ServiceReportPhoto, "before_delete")
def _delete_service_report_photo_file(mapper, connection, target: ServiceReportPhoto) -> None:
    """Feuert für JEDEN ORM-Löschweg eines ServiceReportPhoto -- direkt über delete_photo()
    genauso wie kaskadiert über ServiceReport.photos (cascade="all, delete-orphan") beim
    Löschen eines Berichtsentwurfs. Gleiches Muster wie das RoofArea-Event in
    app/roof_areas.py (1.2.14)."""
    delete_photo_file(target.file_path)

REPORT_TYPES = ("rapport", "wartung")
REPORT_TYPE_LABELS = {"rapport": "Rapportbericht", "wartung": "Wartungsbericht"}

# Bandbreite für die sort_order eines generierten InspectionItem: Vorlagenpunkt-Anteil *
# COMPONENT_SORT_SPAN + (Bauteil-sort_order % COMPONENT_SORT_SPAN). RoofComponent.sort_order
# ist ein freies, von Hand befüllbares Zahlenfeld -- der Modulo verhindert, dass ein hoher Wert
# (z. B. 5000) in das Band des nächsten Vorlagenpunkts hineinrutscht.
COMPONENT_SORT_SPAN = 1_000_000

SIGNATURE_ROOT = Path(os.getenv("DACHKONZEPTE_SIGNATURE_FILE_ROOT", data_dir() / "service_report_signatures"))


def _signature_directory() -> Path:
    SIGNATURE_ROOT.mkdir(parents=True, exist_ok=True)
    return SIGNATURE_ROOT


def signature_path(stored_filename: str) -> Path:
    return SIGNATURE_ROOT / stored_filename


def _employee_name(e) -> str | None:
    return f"{e.first_name} {e.last_name}".strip() if e else None


def _report_roof_areas_to_dicts(report: ServiceReport) -> list[dict]:
    """Einheitliche Flächen-Liste eines Berichts (seit 1.2.22) -- bei einem NEUEN Bericht aus
    den echten ServiceReportRoofArea-Zeilen, bei einem Altbestand-Bericht (vor 1.2.22, keine
    solchen Zeilen) aus den weiterhin gepflegten Legacy-Spalten am Bericht selbst synthetisiert.
    Ein Bericht ohne jeden Flächenbezug liefert eine leere Liste."""
    if report.report_roof_areas:
        return [
            {
                "roof_area_id": link.roof_area_id,
                # Schnappschuss bevorzugt (seit 1.3.12) -- Rückfall auf den aktuellen Namen nur
                # für Bestandszeilen ohne Schnappschuss (siehe Migration).
                "roof_area_name": link.roof_area_name_snapshot or (link.roof_area.name if link.roof_area else None),
                "inspection_template_id": link.inspection_template_id,
                # Schnappschuss bevorzugt (seit 1.3.22) -- Rückfall auf den aktuellen Namen nur
                # für Bestandszeilen ohne Schnappschuss (siehe Migration).
                "inspection_template_label": link.inspection_template_label_snapshot or (
                    link.inspection_template.label if link.inspection_template else None
                ),
                "inspection_template_version": link.inspection_template_version,
            }
            for link in report.report_roof_areas
        ]
    if report.roof_area_id is not None:
        # Legacy-Zweig (vor 1.2.22): bewusst ohne Namens-Schnappschuss, exakt wie roof_area_name
        # hier schon seit 1.3.12 -- diese Spalten werden von create_report() für KEINEN neuen
        # Bericht mehr beschrieben, ein nachträglicher Schnappschuss würde also nie mehr etwas
        # einfrieren, was nicht schon vor der Migration eingefroren war (siehe CLAUDE.md).
        return [{
            "roof_area_id": report.roof_area_id,
            "roof_area_name": report.roof_area.name if report.roof_area else None,
            "inspection_template_id": report.inspection_template_id,
            "inspection_template_label": report.inspection_template.label if report.inspection_template else None,
            "inspection_template_version": report.inspection_template_version,
        }]
    return []


def report_to_dict(report: ServiceReport) -> dict:
    return {
        "id": report.id,
        "order_id": report.order_id,
        "order_number": report.order.order_number if report.order else None,
        "report_type": report.report_type,
        "report_type_label": REPORT_TYPE_LABELS.get(report.report_type, report.report_type),
        "description": report.description,
        "created_by_employee_id": report.created_by_employee_id,
        "created_by_employee_name": _employee_name(report.created_by_employee),
        "performed_at": report.performed_at,
        "signature_name": report.signature_name,
        "signed_at": report.signed_at,
        "installer_signature_name": report.installer_signature_name,
        "installer_signed_at": report.installer_signed_at,
        "status": report.status,
        "maintenance_contract_id": report.maintenance_contract_id,
        "maintenance_contract_item_id": report.maintenance_contract_item_id,
        "advance_due_date_on_sign": report.advance_due_date_on_sign,
        # Legacy (vor 1.2.22, ein Bericht = eine Fläche) -- bleibt für Altbestand gefüllt,
        # wird von create_report() für neue Berichte nicht mehr beschrieben. roof_areas ist der
        # einheitliche Lesepfad für BEIDE Fälle, siehe _report_roof_areas_to_dicts().
        "roof_area_id": report.roof_area_id,
        "roof_area_name": report.roof_area.name if report.roof_area else None,
        "inspection_template_id": report.inspection_template_id,
        "inspection_template_label": report.inspection_template.label if report.inspection_template else None,
        "inspection_template_version": report.inspection_template_version,
        "roof_areas": _report_roof_areas_to_dicts(report),
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def _load(db: Session, report_id: int) -> ServiceReport | None:
    return db.scalar(
        select(ServiceReport)
        .options(
            selectinload(ServiceReport.order), selectinload(ServiceReport.created_by_employee),
            selectinload(ServiceReport.roof_area), selectinload(ServiceReport.inspection_template),
            selectinload(ServiceReport.report_roof_areas).selectinload(ServiceReportRoofArea.roof_area),
            selectinload(ServiceReport.report_roof_areas).selectinload(ServiceReportRoofArea.inspection_template),
            selectinload(ServiceReport.inspection_items).selectinload(InspectionItem.roof_area),
            selectinload(ServiceReport.materials),
        )
        .where(ServiceReport.id == report_id)
    )


def get_report_row(db: Session, report_id: int) -> ServiceReport | None:
    """Gibt (anders als report_to_dict()) das ORM-Objekt selbst zurück -- für
    build_service_report_pdf(), das u. a. report.order und report.signature_path braucht."""
    return _load(db, report_id)


def count_reports_for_order(db: Session, order_id: int) -> int:
    """Schlanke Zählung für Übersichten (seit 1.2.20, z. B. die Auftragsliste in
    project_folder.html) -- Muster wie finding_count in roof_component_to_dict(), keine
    vollständigen Berichtsobjekte nur für eine Zahl laden."""
    return db.scalar(select(func.count(ServiceReport.id)).where(ServiceReport.order_id == order_id)) or 0


def list_reports(db: Session, order_id: int) -> list[dict]:
    query = (
        select(ServiceReport)
        .options(selectinload(ServiceReport.order), selectinload(ServiceReport.created_by_employee))
        .where(ServiceReport.order_id == order_id)
        .order_by(ServiceReport.performed_at.desc(), ServiceReport.id.desc())
    )
    return [report_to_dict(r) for r in db.scalars(query).all()]


def list_draft_reports_for_employee(db: Session, employee_id: int) -> list[dict]:
    """Für die Monteursansicht (/vor-ort, seit 1.3.0) -- offene (noch nicht unterschriebene)
    Berichte, an denen dieser Mitarbeiter zuletzt gearbeitet hat. created_by_employee_id ist die
    einzige vorhandene Zuordnung (kein eigenes "zuletzt bearbeitet von"-Feld), sortiert nach
    updated_at absteigend."""
    query = (
        select(ServiceReport)
        .options(selectinload(ServiceReport.order), selectinload(ServiceReport.created_by_employee))
        .where(ServiceReport.created_by_employee_id == employee_id, ServiceReport.status == "entwurf")
        .order_by(ServiceReport.updated_at.desc())
    )
    return [report_to_dict(r) for r in db.scalars(query).all()]


def list_property_history(db: Session, order_id: int) -> list[dict]:
    """Frühere, bereits unterschriebene Berichte zu ANDEREN Aufträgen desselben Gebäudes (seit
    1.2.3) -- hilfreich für den Monteur beim nächsten Einsatz, um frühere Feststellungen zu
    sehen. Order selbst trägt property_name/-address nur als Text-Schnappschuss (kein
    property_id) -- das zugehörige Gebäude wird deshalb über order.project.property_id
    aufgelöst. Ohne verknüpftes Gebäude (property_id ist bei Project optional) gibt es keine
    Historie, das ist kein Fehler."""
    order = db.get(Order, order_id)
    if order is None or order.project is None or order.project.property_id is None:
        return []
    property_id = order.project.property_id
    query = (
        select(ServiceReport)
        .join(Order, ServiceReport.order_id == Order.id)
        .join(Project, Order.project_id == Project.id)
        .options(selectinload(ServiceReport.order), selectinload(ServiceReport.created_by_employee))
        .where(
            Project.property_id == property_id, ServiceReport.order_id != order_id,
            ServiceReport.status == "unterschrieben",
        )
        .order_by(ServiceReport.performed_at.desc(), ServiceReport.id.desc())
    )
    return [
        {**report_to_dict(r), "order_title": r.order.title if r.order else None}
        for r in db.scalars(query).all()
    ]


def list_contract_history(db: Session, contract_id: int) -> list[dict]:
    """Bereits unterschriebene Berichte, die aus einem Vorgang dieses Wartungsvertrags
    entstanden sind (seit 1.2.15) -- direkter FK-Zugriff auf ServiceReport.maintenance_contract_id,
    kein Join über Order/Project nötig (anders als list_property_history(), das ohne diesen
    FK auskommen musste)."""
    query = (
        select(ServiceReport)
        .options(selectinload(ServiceReport.order), selectinload(ServiceReport.created_by_employee))
        .where(ServiceReport.maintenance_contract_id == contract_id, ServiceReport.status == "unterschrieben")
        .order_by(ServiceReport.performed_at.desc(), ServiceReport.id.desc())
    )
    return [
        {**report_to_dict(r), "order_title": r.order.title if r.order else None}
        for r in db.scalars(query).all()
    ]


def _resolve_inspection_template(db: Session, explicit_id: int | None, contract_item_id: int | None,
                                  roof_area: RoofArea | None) -> InspectionTemplate | None:
    """Vierstufige Auflösung: explizit übergeben -> Vertragsposition -> Dachtyp-Standardvorlage
    -> roof_type IS NULL (gilt für jeden Dachtyp).

    Die dritte Stufe fragt seit 1.2.22 zuerst RoofTypeInspectionTemplateDefault ab (explizite,
    unter Einstellungen -> Prüfvorlagen änderbare Zuordnung) -- ersetzt die vorher rein
    implizite Auflösung über den niedrigsten sort_order, WENN mehrere Vorlagen denselben
    roof_type tragen (genau das war die Beschwerde: "zu implizit"). Gibt es dagegen KEINEN
    expliziten Default, aber GENAU EINEN nicht archivierten Kandidaten für diesen Dachtyp, wird
    dieser trotzdem verwendet -- bei nur einem Kandidaten ist nichts zu erraten, das bewusst
    NICHT zu fordern hieße, dass jede frische Installation (oder ein Test) erst eine
    Zuordnungszeile anlegen müsste, obwohl die Auflösung längst eindeutig ist. Erst bei
    MEHREREN Kandidaten ohne expliziten Default wird nicht mehr geraten (Rückfall auf Stufe
    vier) -- die ursprüngliche Beschwerde bezog sich genau auf diesen Mehrdeutigkeitsfall."""
    if explicit_id is not None:
        return db.get(InspectionTemplate, explicit_id)
    if contract_item_id is not None:
        item = db.get(MaintenanceContractItem, contract_item_id)
        if item is not None and item.inspection_template_id is not None:
            return db.get(InspectionTemplate, item.inspection_template_id)
    if roof_area is not None and roof_area.roof_type:
        default = db.scalar(
            select(RoofTypeInspectionTemplateDefault)
            .where(RoofTypeInspectionTemplateDefault.roof_type == roof_area.roof_type)
        )
        if default is not None and default.inspection_template is not None and not default.inspection_template.archived:
            return default.inspection_template
        candidates = db.scalars(
            select(InspectionTemplate)
            .where(InspectionTemplate.archived == False, InspectionTemplate.roof_type == roof_area.roof_type)  # noqa: E712
        ).all()
        if len(candidates) == 1:
            return candidates[0]
    return db.scalar(
        select(InspectionTemplate)
        .where(InspectionTemplate.archived == False, InspectionTemplate.roof_type.is_(None))  # noqa: E712
        .order_by(InspectionTemplate.sort_order, InspectionTemplate.id)
    )


def _create_inspection_item_from_template(db: Session, report: ServiceReport, template_item: InspectionTemplateItem,
                                           sort_order: int, text: str, roof_component, roof_area_id: int | None) -> None:
    db.add(InspectionItem(
        service_report_id=report.id, template_item_id=template_item.id,
        roof_component_id=roof_component.id if roof_component else None, roof_area_id=roof_area_id,
        sort_order=sort_order, group_name=template_item.group_name, text=text, item_type=template_item.item_type,
        required=template_item.required, target_min=template_item.target_min, target_max=template_item.target_max,
        unit=template_item.unit, photo_required=template_item.photo_required,
        photo_before_after=template_item.photo_before_after,
    ))


def _generate_inspection_items(db: Session, report: ServiceReport, roof_area: RoofArea, template: InspectionTemplate) -> None:
    """Multipliziert die Vorlage gegen den tatsächlichen Bauteilbestand der Dachfläche -- alle
    Anzeige-relevanten Felder werden dabei PHYSISCH auf InspectionItem kopiert (siehe
    Moduldocstring), nie zur Laufzeit vom Template gelesen. roof_area_id wird auf jedem
    erzeugten Punkt gesetzt (seit 1.2.22), unabhängig von component_type."""
    components_by_type: dict[str | None, list] = {}
    for component in roof_area.components:
        if component.archived:
            continue
        components_by_type.setdefault(component.component_type, []).append(component)

    for template_item in sorted(template.items, key=lambda i: (i.sort_order, i.id)):
        if template_item.component_type is None:
            sort_order = template_item.sort_order * COMPONENT_SORT_SPAN
            _create_inspection_item_from_template(db, report, template_item, sort_order, template_item.text, None, roof_area.id)
        else:
            for component in components_by_type.get(template_item.component_type, []):
                sort_order = template_item.sort_order * COMPONENT_SORT_SPAN + (component.sort_order % COMPONENT_SORT_SPAN)
                text = f"{component.name}: {template_item.text}"
                _create_inspection_item_from_template(db, report, template_item, sort_order, text, component, roof_area.id)


def _generate_inspection_items_for_areas(
    db: Session, report: ServiceReport, pairs: list[tuple[RoofArea, InspectionTemplate | None]],
) -> None:
    """Legt für JEDES (Fläche, Vorlage)-Paar eine ServiceReportRoofArea-Zeile an (mit eigenem
    Vorlagen-Schnappschuss, seit 1.2.22) und generiert bei vorhandener Vorlage deren Punkte über
    _generate_inspection_items() -- unverändert. Eine Fläche ohne auflösbare Vorlage (template
    None) bekommt trotzdem ihre Zeile, damit sie als beteiligte Fläche sichtbar bleibt, nur eben
    ohne InspectionItem-Zeilen."""
    for roof_area, template in pairs:
        db.add(ServiceReportRoofArea(
            service_report_id=report.id, roof_area_id=roof_area.id,
            # Physischer Namens-Schnappschuss (seit 1.3.12, CLAUDE.md "Eingefrorene Bauteil-/
            # Dachflächennamen") -- roof_area ist hier bereits das geladene Objekt, keine
            # zusätzliche Abfrage nötig.
            roof_area_name_snapshot=roof_area.name,
            inspection_template_id=template.id if template else None,
            inspection_template_version=template.version if template else None,
            # Physischer Namens-Schnappschuss (seit 1.3.22, letzter loser Faden derselben Kette) --
            # template ist hier bereits das geladene Objekt, keine zusätzliche Abfrage nötig.
            inspection_template_label_snapshot=template.label if template else None,
        ))
        if template is not None:
            _generate_inspection_items(db, report, roof_area, template)


def create_report(db: Session, order_id: int, report_type: str, description: str | None = None,
                   created_by_employee_id: int | None = None, performed_at: date | None = None,
                   roof_area_ids: list[int] | None = None, inspection_template_id: int | None = None,
                   advance_due_date_on_sign: bool = False) -> dict:
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Unbekannter Berichtstyp: {report_type}")
    order = db.get(Order, order_id)
    if order is None:
        raise ValueError("Auftrag nicht gefunden.")
    report = ServiceReport(
        order_id=order_id, report_type=report_type, description=(description or None),
        created_by_employee_id=created_by_employee_id, performed_at=performed_at or date.today(),
        advance_due_date_on_sign=advance_due_date_on_sign,
    )
    # Vertragsbezug als einmaliger Schnappschuss übernehmen (seit 1.2.15) -- sofern der Auftrag
    # über create_project_from_contract() oder create_maintenance_visit() entstanden ist, trägt
    # order.project.profile die Herkunft, ohne dass Order selbst dafür angefasst werden musste.
    if order.project is not None and order.project.profile is not None:
        report.maintenance_contract_id = order.project.profile.source_maintenance_contract_id
        report.maintenance_contract_item_id = order.project.profile.source_maintenance_contract_item_id
    db.add(report)
    db.flush()  # report.id für ServiceReportRoofArea/InspectionItem.service_report_id

    # Dachflächen-Auflösung (seit 1.2.16, ab 1.2.22 mehrere Flächen je Bericht möglich): explizit
    # übergebene Liste -> über die Vertragsposition, aus der der Auftrag entstanden ist
    # (item.roof_area_id, als Einzelfläche -- Rückfall für bestehende Aufrufer) -> keine Fläche
    # (Bericht bleibt ohne Prüfpunkte, wie vor 1.2.16). Legacy-Spalten (report.roof_area_id/
    # inspection_template_id/-version) werden für NEUE Berichte bewusst nicht mehr beschrieben
    # (siehe ServiceReport-Docstring) -- ServiceReportRoofArea ist die alleinige Quelle.
    if roof_area_ids is not None:
        resolved_ids = roof_area_ids
    elif report.maintenance_contract_item_id is not None:
        item = db.get(MaintenanceContractItem, report.maintenance_contract_item_id)
        resolved_ids = [item.roof_area_id] if item is not None else []
    else:
        resolved_ids = []

    # Jede aufgelöste Fläche bekommt IMMER ihre ServiceReportRoofArea-Zeile (Fläche bleibt so
    # auch bei einem Rapportbericht ohne Vorlage am Bericht dokumentiert -- exakt das bisherige
    # Verhalten von report.roof_area_id, das früher unbedingt gesetzt wurde). Die Vorlage selbst
    # wird nur bei Wartungsberichten ODER einer ausdrücklich übergebenen Vorlage aufgelöst (deckt
    # den vom Auftrag genannten Ausnahmefall für Rapportberichte ab).
    should_resolve_template = report_type == "wartung" or inspection_template_id is not None
    # Eine explizite inspection_template_id gilt nur, wenn genau eine Fläche aufgelöst wird --
    # bei mehreren Flächen entscheidet ausschließlich die Dachtyp-Standardvorlage
    # (RoofTypeInspectionTemplateDefault, siehe _resolve_inspection_template()).
    explicit_template_id = inspection_template_id if len(resolved_ids) == 1 else None
    pairs = []
    for roof_area_id in resolved_ids:
        roof_area = db.get(RoofArea, roof_area_id)
        if roof_area is None:
            continue
        template = None
        if should_resolve_template:
            template = _resolve_inspection_template(
                db, explicit_template_id, report.maintenance_contract_item_id, roof_area,
            )
        pairs.append((roof_area, template))
    _generate_inspection_items_for_areas(db, report, pairs)
    db.commit()
    return report_to_dict(_load(db, report.id))


def list_roof_areas_for_order(db: Session, order_id: int) -> list[dict]:
    """Löst wie list_property_history() order.project.property_id auf und liefert dessen
    Dachflächen -- für die Dachflächen-Auswahl beim Anlegen eines Wartungsberichts. Leere Liste
    ohne Fehler, wenn kein Gebäude verknüpft ist."""
    order = db.get(Order, order_id)
    if order is None or order.project is None or order.project.property_id is None:
        return []
    return list_roof_areas(db, order.project.property_id)


def update_report(db: Session, report_id: int, report_type: str, description: str | None,
                   performed_at: date) -> dict | None:
    report = db.get(ServiceReport, report_id)
    if report is None:
        return None
    if report.status == "unterschrieben":
        raise ValueError("Ein unterschriebener Bericht kann nicht mehr bearbeitet werden.")
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Unbekannter Berichtstyp: {report_type}")
    report.report_type = report_type
    report.description = description or None
    report.performed_at = performed_at
    db.commit()
    return report_to_dict(_load(db, report.id))


def delete_report(db: Session, report_id: int) -> bool:
    """Ein unterschriebener Bericht ist ohnehin nicht löschbar (GoBD-Unveränderlichkeit) -- bei
    einem Entwurf müssen zusätzlich die über Finding.follow_up_task_id locker angehängten
    Aufgaben mit aufgeräumt werden, genau wie delete_contract() das seit 1.2.10 für seine
    Erinnerungs-Aufgaben tut. Anders als dort (URL-Textabgleich, da MaintenanceContract keine
    direkte FK zu Task hat) geht das hier direkt über die FK-Spalte follow_up_task_id -- eindeutig
    und ohne die dort nötige Ungenauigkeit bei mehreren Entwürfen desselben Auftrags.
    follow_up_order_id/follow_up_project_id bleiben unangetastet: der daraus entstandene Auftrag
    ist ein eigenständiges, bereits reales Geschäftsvorgang -- nur die lose Rückverweis-Markierung
    am (gleich gelöschten) Finding verschwindet mit. Die Herkunft selbst geht dabei NICHT
    verloren, weil sie beim Anlegen zusätzlich als Text in die description des neuen,
    unabhängigen Project geschrieben wurde (siehe _execute_finding_action() in app/findings.py)."""
    report = db.get(ServiceReport, report_id)
    if report is None:
        return False
    if report.status == "unterschrieben":
        raise ValueError("Ein unterschriebener Bericht kann nicht mehr gelöscht werden.")
    task_ids = [f.follow_up_task_id for f in report.findings if f.follow_up_task_id]
    for task_id in task_ids:
        task = db.get(Task, task_id)
        if task is not None:
            db.delete(task)
    db.delete(report)
    db.commit()
    return True


def inspection_item_to_dict(item: InspectionItem) -> dict:
    return {
        "id": item.id,
        "service_report_id": item.service_report_id,
        "template_item_id": item.template_item_id,
        "roof_component_id": item.roof_component_id,
        "roof_area_id": item.roof_area_id,
        "sort_order": item.sort_order,
        "group_name": item.group_name,
        "text": item.text,
        "item_type": item.item_type,
        "required": item.required,
        "target_min": item.target_min,
        "target_max": item.target_max,
        "unit": item.unit,
        "photo_required": item.photo_required,
        "photo_before_after": item.photo_before_after,
        "result": item.result,
        "condition_grade": item.condition_grade,
        "measured_value": item.measured_value,
        "quantity": item.quantity,
        "duration_minutes": item.duration_minutes,
        "notes": item.notes,
        "recorded_at": item.recorded_at,
        "recorded_by_employee_id": item.recorded_by_employee_id,
        "client_uuid": item.client_uuid,
    }


def _is_item_answered(item: InspectionItem) -> bool:
    if item.item_type in ("ja_nein", "leak_test"):
        return item.result is not None
    if item.item_type == "condition_grade":
        return item.condition_grade is not None
    if item.item_type == "measurement":
        return item.measured_value is not None
    if item.item_type == "quantity":
        return item.quantity is not None
    if item.item_type == "free_text":
        return bool(item.notes and item.notes.strip())
    if item.item_type == "photo":
        return True  # Fotoerfassung folgt in der nächsten Iteration, gilt bis dahin immer als beantwortet
    return False


def list_inspection_items(db: Session, report_id: int) -> list[dict]:
    report = db.get(ServiceReport, report_id)
    if report is None:
        return []
    return [inspection_item_to_dict(i) for i in report.inspection_items]


def _require_draft_report(db: Session, report_id: int) -> ServiceReport:
    report = db.get(ServiceReport, report_id)
    if report is None:
        raise ValueError("Bericht nicht gefunden.")
    if report.status == "unterschrieben":
        raise ValueError("Prüfpunkte eines unterschriebenen Berichts können nicht mehr geändert werden.")
    return report


def add_inspection_item(db: Session, report_id: int, text: str, item_type: str, group_name: str | None = None,
                         required: bool = False, target_min=None, target_max=None, unit: str | None = None,
                         roof_component_id: int | None = None, roof_area_id: int | None = None) -> dict:
    """Manuelle Ergänzung im Entwurf -- der Monteur findet vor Ort ein Bauteil, das in den
    Stammdaten fehlt. template_item_id bleibt NULL (keine Vorlagen-Herkunft). roof_area_id (seit
    1.2.22) ordnet den Punkt bei Mehrflächen-Berichten der richtigen Fläche zu -- ohne Angabe
    bleibt er ohne Flächenbezug (rendert außerhalb jedes Flächen-Blocks)."""
    report = _require_draft_report(db, report_id)
    text = text.strip()
    if not text:
        raise ValueError("Bitte einen Prüftext angeben.")
    if item_type not in ITEM_TYPES:
        raise ValueError(f"Unbekannter Punkttyp: {item_type}")
    max_sort = max((i.sort_order for i in report.inspection_items), default=0)
    item = InspectionItem(
        service_report_id=report_id, template_item_id=None, roof_component_id=roof_component_id,
        roof_area_id=roof_area_id, sort_order=max_sort + 10, group_name=(group_name or None), text=text,
        item_type=item_type, required=required, target_min=target_min, target_max=target_max, unit=(unit or None),
    )
    db.add(item)
    db.commit()
    return inspection_item_to_dict(item)


_INSPECTION_ITEM_UPDATE_FIELDS = {
    "result", "condition_grade", "measured_value", "quantity", "duration_minutes", "notes",
    "recorded_by_employee_id",
}


def update_inspection_item(db: Session, item_id: int, fields: dict) -> dict | None:
    """Seit 1.2.19 überschreibt diese Funktion NUR NOCH die in fields tatsächlich enthaltenen
    Schlüssel (Router: payload.model_dump(exclude_unset=True)), analog zu upsert_roof_layer() in
    app/roof_areas.py. Vorher überschrieb jeder Aufruf unbedingt alle Felder -- in Kombination
    mit dem Frontend-Muster "OK/Nicht OK/Entfällt-Klick sendet NUR {result}" (setResultAndSave()
    in service_reports.html) löschte jeder Klick auf einem leak_test-Prüfpunkt dessen bereits
    erfasste duration_minutes. Der Frontend-Teil dieses Fundes ist inzwischen ebenfalls behoben
    (saveInspectionResult() liest den Container jetzt immer und legt Overrides nur noch
    darüber), diese Funktion wird trotzdem auf das robustere Muster umgestellt."""
    item = db.get(InspectionItem, item_id)
    if item is None:
        return None
    _require_draft_report(db, item.service_report_id)
    for key, value in fields.items():
        if key not in _INSPECTION_ITEM_UPDATE_FIELDS:
            continue
        if key == "notes" and value == "":
            value = None
        setattr(item, key, value)
    client_uuid = fields.get("client_uuid")
    if client_uuid:
        item.client_uuid = client_uuid
    item.recorded_at = datetime.utcnow()
    db.commit()
    return inspection_item_to_dict(item)


def delete_inspection_item(db: Session, item_id: int) -> bool:
    item = db.get(InspectionItem, item_id)
    if item is None:
        return False
    _require_draft_report(db, item.service_report_id)
    db.delete(item)
    db.commit()
    return True


def regenerate_inspection_items(db: Session, report_id: int) -> dict:
    """Löscht alle Prüfpunkte und baut sie komplett neu auf -- nur im Entwurf, nur auf
    ausdrücklichen Klick (Datenverlust-Warnung ist Sache der Oberfläche). Nutzt bewusst den
    AKTUELLEN Stand der jeweils schon zugeordneten Vorlage (nicht die beim Anlegen eingefrorene
    Version), das ist der Sinn eines expliziten Neuaufbaus -- welche Vorlage einer Fläche
    zugeordnet ist, ändert regenerate NICHT (das würde eine erneute Auflösung bedeuten, nicht
    nur einen Neuaufbau).

    Seit 1.2.22: bei Mehrflächen-Berichten (ServiceReportRoofArea-Zeilen vorhanden) wird über
    ALLE iteriert; ein Altbestand-Bericht (vor 1.2.22, keine solchen Zeilen) verhält sich exakt
    wie zuvor über seine Legacy-Spalten."""
    report = _require_draft_report(db, report_id)
    if report.report_roof_areas:
        for item in list(report.inspection_items):
            db.delete(item)
        db.flush()
        for link in report.report_roof_areas:
            if link.inspection_template_id is None or link.roof_area is None:
                continue
            template = db.get(InspectionTemplate, link.inspection_template_id)
            if template is not None:
                link.inspection_template_version = template.version
                _generate_inspection_items(db, report, link.roof_area, template)
        db.commit()
        return report_to_dict(_load(db, report_id))

    if report.roof_area_id is None or report.inspection_template_id is None:
        raise ValueError("Für diesen Bericht ist keine Dachfläche/Vorlage hinterlegt.")
    for item in list(report.inspection_items):
        db.delete(item)
    db.flush()
    roof_area = db.get(RoofArea, report.roof_area_id)
    template = db.get(InspectionTemplate, report.inspection_template_id)
    report.inspection_template_version = template.version
    _generate_inspection_items(db, report, roof_area, template)
    db.commit()
    return report_to_dict(_load(db, report_id))


def _sync_inspection_items_for_area(db: Session, report: ServiceReport, roof_area: RoofArea,
                                     template: InspectionTemplate, existing_keys: set) -> int:
    """Additiver Kern von sync_inspection_items() für EINE Fläche -- ergänzt nur fehlende
    Punkte, rührt bestehende nie an. existing_keys wird über den ganzen Bericht (alle Flächen)
    gebildet, da ein Bauteil ohnehin genau einer Fläche gehört, keine Kollisionsgefahr."""
    components_by_type: dict[str | None, list] = {}
    for component in roof_area.components:
        if component.archived:
            continue
        components_by_type.setdefault(component.component_type, []).append(component)

    added = 0
    for template_item in sorted(template.items, key=lambda i: (i.sort_order, i.id)):
        if template_item.component_type is None:
            if (template_item.id, None) not in existing_keys:
                sort_order = template_item.sort_order * COMPONENT_SORT_SPAN
                _create_inspection_item_from_template(
                    db, report, template_item, sort_order, template_item.text, None, roof_area.id,
                )
                added += 1
        else:
            for component in components_by_type.get(template_item.component_type, []):
                if (template_item.id, component.id) in existing_keys:
                    continue
                sort_order = template_item.sort_order * COMPONENT_SORT_SPAN + (component.sort_order % COMPONENT_SORT_SPAN)
                text = f"{component.name}: {template_item.text}"
                _create_inspection_item_from_template(db, report, template_item, sort_order, text, component, roof_area.id)
                added += 1
    return added


def sync_inspection_items(db: Session, report_id: int) -> dict:
    """Ergänzt ausschließlich fehlende Punkte für seit der letzten Generierung hinzugekommene
    Bauteile -- rührt bestehende InspectionItem-Zeilen nie an, entfernt/markiert auch nie
    Punkte zu inzwischen entfernten Bauteilen. No-op (kein Fehler), wenn keine Fläche/Vorlage
    hinterlegt ist oder der Bericht unterschrieben ist. Gibt zusätzlich zurück, wie viele Punkte
    ergänzt wurden -- die Oberfläche zeigt das nur an, wenn > 0.

    Seit 1.2.22: bei Mehrflächen-Berichten wird über ALLE beteiligten Flächen (mit jeweils
    eigener Vorlage) ergänzt; ein Altbestand-Bericht verhält sich unverändert über seine
    Legacy-Spalten."""
    report = db.get(ServiceReport, report_id)
    if report is None:
        raise ValueError("Bericht nicht gefunden.")
    if report.status == "unterschrieben":
        return {"added": 0, "items": list_inspection_items(db, report_id)}

    existing_keys = {(i.template_item_id, i.roof_component_id) for i in report.inspection_items}
    added = 0
    if report.report_roof_areas:
        for link in report.report_roof_areas:
            if link.inspection_template_id is None or link.roof_area is None:
                continue
            template = db.get(InspectionTemplate, link.inspection_template_id)
            if template is not None:
                added += _sync_inspection_items_for_area(db, report, link.roof_area, template, existing_keys)
    elif report.roof_area_id is not None and report.inspection_template_id is not None:
        roof_area = db.get(RoofArea, report.roof_area_id)
        template = db.get(InspectionTemplate, report.inspection_template_id)
        added += _sync_inspection_items_for_area(db, report, roof_area, template, existing_keys)

    db.commit()
    return {"added": added, "items": list_inspection_items(db, report_id)}


def photo_to_dict(photo: ServiceReportPhoto) -> dict:
    return {
        "id": photo.id,
        "service_report_id": photo.service_report_id,
        "inspection_item_id": photo.inspection_item_id,
        "finding_id": photo.finding_id,
        "kind": photo.kind,
        "original_filename": photo.original_filename,
        "caption": photo.caption,
        "sort_order": photo.sort_order,
        "created_at": photo.created_at,
        "created_by_employee_id": photo.created_by_employee_id,
        "client_uuid": photo.client_uuid,
    }


def list_photos(db: Session, report_id: int) -> list[dict]:
    report = db.get(ServiceReport, report_id)
    if report is None:
        return []
    return [photo_to_dict(p) for p in sorted(report.photos, key=lambda p: (p.sort_order, p.id))]


def add_photo(
    db: Session, service_report_id: int, data: bytes, original_filename: str,
    inspection_item_id: int | None = None, finding_id: int | None = None, kind: str = "allgemein",
    caption: str | None = None, created_by_employee_id: int | None = None,
) -> dict:
    """Ein Foto gehört immer zu GENAU EINEM Prüfpunkt ODER GENAU EINEM Mangel, nie zu beidem und
    nie zu keinem von beidem -- rein in der Business-Logik erzwungen, kein CheckConstraint (siehe
    app/models.py::ServiceReportPhoto für die Begründung). kind ist nur bei einem Prüfpunkt mit
    photo_before_after relevant und wird sonst immer auf "allgemein" normalisiert."""
    report = _require_draft_report(db, service_report_id)
    if (inspection_item_id is None) == (finding_id is None):
        raise ValueError("Ein Foto muss zu genau einem Prüfpunkt ODER genau einem Mangel gehören.")

    item = None
    if inspection_item_id is not None:
        item = db.get(InspectionItem, inspection_item_id)
        if item is None or item.service_report_id != service_report_id:
            raise ValueError("Prüfpunkt nicht gefunden.")
        if not item.photo_before_after or kind not in ("vorher", "nachher"):
            kind = "allgemein"
        else:
            existing = sum(1 for p in report.photos if p.inspection_item_id == inspection_item_id and p.kind == kind)
            if existing:
                raise ValueError(f"Für diesen Prüfpunkt existiert bereits ein Foto \"{kind}\".")
    else:
        finding = db.get(Finding, finding_id)
        if finding is None or finding.service_report_id != service_report_id:
            raise ValueError("Mangel nicht gefunden.")
        kind = "allgemein"

    stored = resize_and_store_photo(original_filename, data)
    photo = ServiceReportPhoto(
        service_report_id=service_report_id, inspection_item_id=inspection_item_id, finding_id=finding_id,
        kind=kind, file_path=stored, original_filename=original_filename, caption=(caption or None),
        created_by_employee_id=created_by_employee_id,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo_to_dict(photo)


def delete_photo(db: Session, photo_id: int) -> bool:
    photo = db.get(ServiceReportPhoto, photo_id)
    if photo is None:
        return False
    _require_draft_report(db, photo.service_report_id)
    db.delete(photo)  # löst das before_delete-Event oben aus, das die Datei von der Platte entfernt
    db.commit()
    return True


def material_to_dict(m: ServiceReportMaterial) -> dict:
    return {
        "id": m.id,
        "service_report_id": m.service_report_id,
        "material_id": m.material_id,
        "description": m.description,
        "quantity": m.quantity,
        "unit": m.unit,
        "roof_area_id": m.roof_area_id,
        "inspection_item_id": m.inspection_item_id,
        "finding_id": m.finding_id,
        "notes": m.notes,
        "sort_order": m.sort_order,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
        "created_by_employee_id": m.created_by_employee_id,
        "client_uuid": m.client_uuid,
    }


def list_materials_for_report(db: Session, report_id: int) -> list[dict]:
    report = db.get(ServiceReport, report_id)
    if report is None:
        return []
    return [material_to_dict(m) for m in sorted(report.materials, key=lambda m: (m.sort_order, m.id))]


def _report_covered_roof_area_ids(report: ServiceReport) -> set[int]:
    """Welche Dachflächen an diesem Bericht beteiligt sind -- Mehrflächen-Berichte (seit 1.2.22)
    über report_roof_areas, ein Altbestand-Bericht über die weiterhin gepflegte Legacy-Spalte."""
    ids = {link.roof_area_id for link in report.report_roof_areas}
    if report.roof_area_id is not None:
        ids.add(report.roof_area_id)
    return ids


def add_material(
    db: Session, service_report_id: int, *, material_id: int | None = None, description: str | None = None,
    quantity, unit: str | None = None, roof_area_id: int | None = None, inspection_item_id: int | None = None,
    finding_id: int | None = None, notes: str | None = None, created_by_employee_id: int | None = None,
    client_uuid: str | None = None,
) -> dict:
    """Zwei gleichwertige Erfassungswege (siehe Moduldocstring von ServiceReportMaterial):
    material_id gesetzt kopiert description/unit als Schnappschuss aus dem Katalog (ein
    mitgegebener Wert wird dabei überschrieben); material_id leer verlangt eine eigene
    description vom Monteur und erzeugt NIE einen neuen Material-Katalogeintrag."""
    report = _require_draft_report(db, service_report_id)
    if quantity is None or quantity <= 0:
        raise ValueError("Bitte eine Menge größer als 0 angeben.")

    if material_id is not None:
        material = db.get(Material, material_id)
        if material is None:
            raise ValueError("Material nicht gefunden.")
        description = material.name
        unit = material.unit
    else:
        description = (description or "").strip()
        if not description:
            raise ValueError("Bitte eine Bezeichnung angeben.")

    if inspection_item_id is not None:
        item = db.get(InspectionItem, inspection_item_id)
        if item is None or item.service_report_id != service_report_id:
            raise ValueError("Prüfpunkt nicht gefunden.")
    if finding_id is not None:
        finding = db.get(Finding, finding_id)
        if finding is None or finding.service_report_id != service_report_id:
            raise ValueError("Mangel nicht gefunden.")
    if roof_area_id is not None:
        covered = _report_covered_roof_area_ids(report)
        if covered and roof_area_id not in covered:
            raise ValueError("Diese Dachfläche gehört nicht zu diesem Bericht.")

    material_row = ServiceReportMaterial(
        service_report_id=service_report_id, material_id=material_id, description=description,
        quantity=quantity, unit=(unit or None), roof_area_id=roof_area_id, inspection_item_id=inspection_item_id,
        finding_id=finding_id, notes=(notes or None), created_by_employee_id=created_by_employee_id,
        client_uuid=(client_uuid or None),
    )
    db.add(material_row)
    db.commit()
    db.refresh(material_row)
    return material_to_dict(material_row)


_MATERIAL_UPDATE_FIELDS = {"quantity", "unit", "description", "notes", "roof_area_id", "inspection_item_id", "finding_id"}


def update_material(db: Session, material_id: int, fields: dict) -> dict | None:
    """exclude_unset-Muster wie update_inspection_item() seit 1.2.19 -- ein nicht mitgeschickter
    Schlüssel bleibt unverändert. Wird material_id selbst mitgeschickt (auch mit einem neuen
    Katalogeintrag), werden description/unit erneut aus dem Katalog übernommen -- dieselbe
    Schnappschuss-Regel wie beim Anlegen; ein ausdrücklicher Wechsel auf material_id=None lässt
    die zuletzt gesetzte Bezeichnung als freien Text stehen."""
    row = db.get(ServiceReportMaterial, material_id)
    if row is None:
        return None
    report = _require_draft_report(db, row.service_report_id)

    if "material_id" in fields:
        new_material_id = fields["material_id"]
        row.material_id = new_material_id
        if new_material_id is not None:
            material = db.get(Material, new_material_id)
            if material is None:
                raise ValueError("Material nicht gefunden.")
            row.description = material.name
            row.unit = material.unit

    for key, value in fields.items():
        if key not in _MATERIAL_UPDATE_FIELDS:
            continue
        if key == "quantity" and (value is None or value <= 0):
            raise ValueError("Bitte eine Menge größer als 0 angeben.")
        if key == "description" and not (value or "").strip():
            raise ValueError("Bitte eine Bezeichnung angeben.")
        if key == "inspection_item_id" and value is not None:
            item = db.get(InspectionItem, value)
            if item is None or item.service_report_id != row.service_report_id:
                raise ValueError("Prüfpunkt nicht gefunden.")
        if key == "finding_id" and value is not None:
            finding = db.get(Finding, value)
            if finding is None or finding.service_report_id != row.service_report_id:
                raise ValueError("Mangel nicht gefunden.")
        if key == "roof_area_id" and value is not None:
            covered = _report_covered_roof_area_ids(report)
            if covered and value not in covered:
                raise ValueError("Diese Dachfläche gehört nicht zu diesem Bericht.")
        setattr(row, key, value)

    db.commit()
    return material_to_dict(row)


def delete_material(db: Session, material_id: int) -> bool:
    row = db.get(ServiceReportMaterial, material_id)
    if row is None:
        return False
    _require_draft_report(db, row.service_report_id)
    db.delete(row)
    db.commit()
    return True


def list_materials_for_invoicing(db: Session, order_id: int) -> list[ServiceReportMaterial]:
    """Für create_invoice_from_time_entries() (app/invoices.py, Rechnung aus Aufwand) -- liefert
    ORM-Zeilen (nicht Dicts), da der Aufrufer über material.material_id/.quantity/.unit direkt
    weiterrechnet. Nur unterschriebene Berichte liefern Material, Entwürfe bleiben außen vor --
    exakt das TimeEntry-Prinzip (dort nur status=\"booked\")."""
    query = (
        select(ServiceReportMaterial)
        .join(ServiceReport, ServiceReportMaterial.service_report_id == ServiceReport.id)
        .where(ServiceReport.order_id == order_id, ServiceReport.status == "unterschrieben")
        .order_by(ServiceReportMaterial.id)
    )
    return list(db.scalars(query).all())


def sign_report(
    db: Session, report_id: int, *,
    installer_signature_png_bytes: bytes, installer_signature_name: str,
    customer_signature_png_bytes: bytes, customer_signature_name: str,
) -> dict | None:
    """Schreibt beide Unterschriften auf die Festplatte, friert den Bericht danach ein
    (status="unterschrieben", gleiches Unveränderlichkeits-Muster wie Invoice/Order/Reminder)
    und löst -- sofern Aufgabenmanagement aktiv ist -- die "Rechnung erstellen"-Aufgabe für
    den Sachbearbeiter des Auftrags aus.

    Seit 1.2.16: blockiert zusätzlich, solange mindestens ein Pflicht-Prüfpunkt noch nicht
    beantwortet ist. Ein Bericht ohne Prüfpunkte hat eine leere inspection_items-Liste, verhält
    sich also unverändert wie vor dieser Erweiterung.

    Seit 1.2.17: drei weitere Prüfungen NACH der obigen, jede mit eigener Meldung -- ein
    Bericht ohne Prüfpunkte UND ohne Mängel durchläuft alle drei mit leeren Ergebnismengen und
    verhält sich damit ebenfalls unverändert (Regressionsfall).

    Seit 1.2.22: bei advance_due_date_on_sign (nur von create_maintenance_visit() gesetzt) wird
    NACH dem Einfrieren die Fälligkeit des verknüpften MaintenanceContract fortgeschrieben --
    bewusst erst hier, nicht beim Anlegen, damit ein abgebrochener/gelöschter Entwurf den
    Turnus nicht verschiebt (siehe ServiceReport-Docstring). Ist der Vertrag inzwischen
    gelöscht, wird das stillschweigend übersprungen -- die Unterschrift selbst darf davon nicht
    abhängen.

    Seit 1.3.0 (Monteursansicht): verlangt BEIDE Unterschriften in einem Aufruf -- Monteur
    zuerst, dann Kunde (Reihenfolge auf dem Gerät: Tablet wird nach der Monteursunterschrift an
    den Kunden weitergereicht), dann erst das Einfrieren. Die bestehenden
    Vollständigkeitsprüfungen oben bleiben unverändert davor. signature_path/-name/signed_at
    bleiben unverändert die Felder des KUNDEN; installer_signature_* sind die neuen, parallelen
    Felder des Monteurs."""
    report = db.get(ServiceReport, report_id)
    if report is None:
        return None
    if report.status == "unterschrieben":
        raise ValueError("Dieser Bericht ist bereits unterschrieben.")
    open_required = [i for i in report.inspection_items if i.required and not _is_item_answered(i)]
    if open_required:
        raise ValueError(f"{len(open_required)} Pflichtpunkt(e) sind noch nicht beantwortet.")

    findings_by_item_id = {f.inspection_item_id for f in report.findings if f.inspection_item_id is not None}
    negative_items = [
        i for i in report.inspection_items
        if (i.result == "nok" or i.condition_grade in (3, 4)) and i.id not in findings_by_item_id
    ]
    if negative_items:
        raise ValueError(f"{len(negative_items)} Prüfpunkt(e) mit negativem Ergebnis haben noch keinen Mangel.")

    findings_without_photo = [f for f in report.findings if not f.photos]
    if findings_without_photo:
        raise ValueError(f"{len(findings_without_photo)} Mangel/Mängel haben noch kein Foto.")

    postponed_without_date = [f for f in report.findings if f.action == "zurueckgestellt" and f.resubmission_date is None]
    if postponed_without_date:
        raise ValueError(f"{len(postponed_without_date)} zurückgestellte(r) Mangel/Mängel ohne Wiedervorlagedatum.")

    if not installer_signature_name.strip():
        raise ValueError("Bitte den Namen des unterschreibenden Monteurs angeben.")
    if not customer_signature_name.strip():
        raise ValueError("Bitte den Namen der unterschreibenden Person angeben.")

    _signature_directory()
    installer_stored = make_stored_filename("unterschrift_monteur.png")
    signature_path(installer_stored).write_bytes(installer_signature_png_bytes)
    report.installer_signature_path = installer_stored
    report.installer_signature_name = installer_signature_name.strip()
    report.installer_signed_at = datetime.utcnow()

    customer_stored = make_stored_filename("unterschrift.png")
    signature_path(customer_stored).write_bytes(customer_signature_png_bytes)
    report.signature_path = customer_stored
    report.signature_name = customer_signature_name.strip()
    report.signed_at = datetime.utcnow()
    report.status = "unterschrieben"

    if report.advance_due_date_on_sign and report.maintenance_contract_id is not None:
        contract = db.get(MaintenanceContract, report.maintenance_contract_id)
        if contract is not None:
            contract.next_due_date = add_months(contract.next_due_date, contract.interval_months)
            contract.last_reminder_due_date = None

    db.commit()
    report = _load(db, report.id)

    if is_module_enabled(db, "aufgabenmanagement"):
        order = report.order
        label = REPORT_TYPE_LABELS.get(report.report_type, report.report_type)
        create_task(
            db, title=f"Rechnung erstellen für {label} zu Auftrag {order.order_number}",
            description=f"{label} zu Auftrag {order.order_number} wurde unterschrieben und ist bereit zur Abrechnung.",
            assigned_employee_id=order.caseworker_employee_id,
            source_module="wartungsbericht", source_label=f"{label} {order.order_number}",
            source_url=f"/orders/{order.id}",
        )
    return report_to_dict(report)
