"""Prüfvorlagen für Einsatzberichte (seit 1.2.16, Modul "wartungen").

Eine Vorlage beschreibt, was je Bauteilart bei einer Wartung zu prüfen ist. Sie wird beim
Anlegen eines Wartungsberichts gegen den tatsächlichen Bauteilbestand einer Dachfläche
"multipliziert" (_generate_inspection_items() in app/service_reports.py) und bleibt danach
frei bearbeitbar, da alles Relevante physisch in den Bericht kopiert wird -- version ist der
Schnappschuss-Stempel dafür, gegen welchen Stand ein Bericht generiert wurde. Sowohl
Metadaten- als auch Punkt-Änderungen zählen als "Speichern der Vorlage" und erhöhen version."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .models import InspectionItem, InspectionTemplate, InspectionTemplateItem, RoofTypeInspectionTemplateDefault
from .option_settings import get_option_group

ITEM_TYPES = ("ja_nein", "condition_grade", "measurement", "quantity", "leak_test", "free_text", "photo")


def _bump_version(template: InspectionTemplate) -> None:
    template.version += 1


def template_item_to_dict(item: InspectionTemplateItem) -> dict:
    return {
        "id": item.id,
        "template_id": item.template_id,
        "sort_order": item.sort_order,
        "group_name": item.group_name,
        "component_type": item.component_type,
        "text": item.text,
        "item_type": item.item_type,
        "required": item.required,
        "target_min": item.target_min,
        "target_max": item.target_max,
        "unit": item.unit,
        "photo_required": item.photo_required,
        "photo_before_after": item.photo_before_after,
    }


def template_to_dict(template: InspectionTemplate) -> dict:
    return {
        "id": template.id,
        "label": template.label,
        "roof_type": template.roof_type,
        "version": template.version,
        "description": template.description,
        "sort_order": template.sort_order,
        "archived": template.archived,
        "item_count": len(template.items),
        "items": [template_item_to_dict(i) for i in template.items],
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _load(db: Session, template_id: int) -> InspectionTemplate | None:
    return db.scalar(
        select(InspectionTemplate).options(selectinload(InspectionTemplate.items)).where(InspectionTemplate.id == template_id)
    )


def list_templates(db: Session, include_archived: bool = False) -> list[dict]:
    query = select(InspectionTemplate).options(selectinload(InspectionTemplate.items))
    if not include_archived:
        query = query.where(InspectionTemplate.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(InspectionTemplate.sort_order, InspectionTemplate.id)
    return [template_to_dict(t) for t in db.scalars(query).all()]


def get_template(db: Session, template_id: int) -> dict | None:
    template = _load(db, template_id)
    return template_to_dict(template) if template else None


def create_template(db: Session, label: str, roof_type: str | None = None, description: str | None = None) -> dict:
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    max_sort = db.scalar(select(func.max(InspectionTemplate.sort_order))) or 0
    template = InspectionTemplate(
        label=label, roof_type=roof_type or None, description=(description or None), sort_order=max_sort + 10,
    )
    db.add(template)
    db.commit()
    return template_to_dict(_load(db, template.id))


def update_template(db: Session, template_id: int, label: str, roof_type: str | None, description: str | None) -> dict | None:
    template = db.get(InspectionTemplate, template_id)
    if template is None:
        return None
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    template.label = label
    template.roof_type = roof_type or None
    template.description = description or None
    _bump_version(template)
    db.commit()
    return template_to_dict(_load(db, template.id))


def set_template_archived(db: Session, template_id: int, archived: bool) -> dict | None:
    """Rein informatives Aus-/Einblenden, gleiches Muster wie set_roof_area_archived() -- KEIN
    Version-Bump, da sich der Vorlageninhalt dabei nicht ändert."""
    template = db.get(InspectionTemplate, template_id)
    if template is None:
        return None
    template.archived = archived
    db.commit()
    return template_to_dict(_load(db, template.id))


def copy_template(db: Session, template_id: int, new_label: str) -> dict:
    source = _load(db, template_id)
    if source is None:
        raise ValueError("Vorlage nicht gefunden.")
    new_label = new_label.strip()
    if not new_label:
        raise ValueError("Bitte eine Bezeichnung für die Kopie angeben.")
    max_sort = db.scalar(select(func.max(InspectionTemplate.sort_order))) or 0
    copy = InspectionTemplate(label=new_label, roof_type=source.roof_type, description=source.description, sort_order=max_sort + 10)
    db.add(copy)
    db.flush()
    for item in source.items:
        db.add(InspectionTemplateItem(
            template_id=copy.id, sort_order=item.sort_order, group_name=item.group_name,
            component_type=item.component_type, text=item.text, item_type=item.item_type, required=item.required,
            target_min=item.target_min, target_max=item.target_max, unit=item.unit,
            photo_required=item.photo_required, photo_before_after=item.photo_before_after,
        ))
    db.commit()
    return template_to_dict(_load(db, copy.id))


def create_template_item(db: Session, template_id: int, text: str, item_type: str, group_name: str | None = None,
                          component_type: str | None = None, required: bool = False, target_min=None,
                          target_max=None, unit: str | None = None, photo_required: bool = False,
                          photo_before_after: bool = False, sort_order: int = 100) -> dict:
    template = db.get(InspectionTemplate, template_id)
    if template is None:
        raise ValueError("Vorlage nicht gefunden.")
    text = text.strip()
    if not text:
        raise ValueError("Bitte einen Prüftext angeben.")
    if item_type not in ITEM_TYPES:
        raise ValueError(f"Unbekannter Punkttyp: {item_type}")
    item = InspectionTemplateItem(
        template_id=template_id, sort_order=sort_order, group_name=(group_name or None),
        component_type=(component_type or None), text=text, item_type=item_type, required=required,
        target_min=target_min, target_max=target_max, unit=(unit or None), photo_required=photo_required,
        photo_before_after=photo_before_after,
    )
    db.add(item)
    _bump_version(template)
    db.commit()
    return template_item_to_dict(item)


def update_template_item(db: Session, item_id: int, text: str, item_type: str, group_name: str | None,
                          component_type: str | None, required: bool, target_min, target_max,
                          unit: str | None, photo_required: bool, photo_before_after: bool, sort_order: int) -> dict | None:
    item = db.get(InspectionTemplateItem, item_id)
    if item is None:
        return None
    text = text.strip()
    if not text:
        raise ValueError("Bitte einen Prüftext angeben.")
    if item_type not in ITEM_TYPES:
        raise ValueError(f"Unbekannter Punkttyp: {item_type}")
    item.text = text
    item.item_type = item_type
    item.group_name = group_name or None
    item.component_type = component_type or None
    item.required = required
    item.target_min = target_min
    item.target_max = target_max
    item.unit = unit or None
    item.photo_required = photo_required
    item.photo_before_after = photo_before_after
    item.sort_order = sort_order
    _bump_version(item.template)
    db.commit()
    return template_item_to_dict(item)


class VorlagenpunktInBerichten(ValueError):
    """Seit 1.9.43: ein Vorlagenpunkt, der in Einsatzberichten steckt, lässt sich nicht löschen (409) -- der Prüfpunkt im Bericht
    verweist über template_item_id auf ihn, und daran erkennt der Bericht seit 1.9.41 einen Punkt aus der Vorlage. Bis 1.9.42 lief das
    Löschen unter PostgreSQL in den Fremdschlüssel (500), unter SQLite blieb ein Verweis ins Leere."""

    def __init__(self, berichte: int):
        self.berichte = berichte
        wo = "einem Einsatzbericht" if berichte == 1 else f"{berichte} Einsatzberichten"
        super().__init__(f"Dieser Prüfpunkt steckt in {wo} und lässt sich deshalb nicht löschen. "
                         "Für neue Berichte ohne ihn: Vorlage kopieren und den Punkt in der Kopie löschen.")


def _berichte_mit_punkt(db: Session, item_id: int) -> int:
    return db.scalar(select(func.count(func.distinct(InspectionItem.service_report_id)))
                     .where(InspectionItem.template_item_id == item_id)) or 0


def delete_template_item(db: Session, item_id: int) -> bool:
    """Löscht einen Vorlagenpunkt, der in keinem Einsatzbericht steckt; sonst VorlagenpunktInBerichten (seit 1.9.43). Die Zeile
    wird zuerst gesperrt: unter PostgreSQL wartet die Sperre auf einen Bericht, der gerade aus der Vorlage entsteht (er hält den
    Punkt mit FOR KEY SHARE), danach zählt die Abfrage ihn mit. Kein ON DELETE SET NULL oder CASCADE: template_item_id eines
    Punkts aus der Vorlage wird nie leer."""
    item = db.scalar(select(InspectionTemplateItem).where(InspectionTemplateItem.id == item_id).with_for_update())
    if item is None:
        return False
    berichte = _berichte_mit_punkt(db, item_id)
    if berichte:
        db.rollback()
        raise VorlagenpunktInBerichten(berichte)
    template = item.template
    db.delete(item)
    _bump_version(template)
    try:
        db.commit()
    except IntegrityError:  # Netz: ein Verweis, den die Sperre nicht abgefangen hat -- nie 500
        db.rollback()
        raise VorlagenpunktInBerichten(max(_berichte_mit_punkt(db, item_id), 1)) from None
    return True


def list_roof_type_template_defaults(db: Session) -> list[dict]:
    """Explizite Zuordnung "je Dachtyp genau eine Standardvorlage" (seit 1.2.22, ersetzt in
    _resolve_inspection_template() die vorher implizite Auflösung über den niedrigsten
    sort_order). Liefert EINE Zeile je aktivem Wert der Optionsgruppe roof_types -- auch für
    einen Dachtyp ohne bisherige Zuordnung (inspection_template_id dann None), damit die
    Einstellungen-Oberfläche jeden bekannten Dachtyp anzeigen kann, nicht nur bereits
    zugeordnete."""
    group = get_option_group(db, "roof_types")
    defaults_by_type = {
        d.roof_type: d for d in db.scalars(
            select(RoofTypeInspectionTemplateDefault).options(
                selectinload(RoofTypeInspectionTemplateDefault.inspection_template)
            )
        ).all()
    }
    rows = []
    for option in sorted(group.options, key=lambda o: (o.sort_order, o.id)) if group else []:
        if not option.active:
            continue
        default = defaults_by_type.get(option.value)
        rows.append({
            "roof_type": option.value,
            "roof_type_label": option.label,
            "inspection_template_id": default.inspection_template_id if default else None,
            "inspection_template_label": default.inspection_template.label if default and default.inspection_template else None,
        })
    return rows


def set_roof_type_template_default(db: Session, roof_type: str, inspection_template_id: int | None) -> None:
    """Upsert/Löschen der Standardvorlage eines Dachtyps -- inspection_template_id=None entfernt
    die Zuordnung (_resolve_inspection_template() fällt dann auf die roof_type IS NULL-Stufe
    zurück, kein Fehler)."""
    existing = db.scalar(
        select(RoofTypeInspectionTemplateDefault).where(RoofTypeInspectionTemplateDefault.roof_type == roof_type)
    )
    if inspection_template_id is None:
        if existing is not None:
            db.delete(existing)
            db.commit()
        return
    template = db.get(InspectionTemplate, inspection_template_id)
    if template is None:
        raise ValueError("Vorlage nicht gefunden.")
    if existing is not None:
        existing.inspection_template_id = inspection_template_id
    else:
        db.add(RoofTypeInspectionTemplateDefault(roof_type=roof_type, inspection_template_id=inspection_template_id))
    db.commit()
