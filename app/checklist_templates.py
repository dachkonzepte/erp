"""Checklisten-Vorlagen (seit 1.8.0, Modul "checklisten").

Herleitung, Betreiberentscheidungen und Etappenplan: docs/archiv/modul-checklisten.md.

Eine Vorlage (ChecklistTemplate) trägt nur Identität und veränderliche Verwaltungsdaten
(Bezeichnung, erlaubte Kontexte, field_readable, Archiv). Der Inhalt -- Felder, Auswahloptionen,
Regeln -- hängt an einer nummerierten Fassung (ChecklistTemplateVersion):

- Höchstens EINE Entwurfsfassung je Vorlage; nur sie ist änderbar (_require_draft()).
- Veröffentlichen macht den Entwurf gültig und die bisher gültige Fassung zu "abgeloest".
- Eine veröffentlichte/abgelöste Fassung ist eingefroren -- sie IST der Schnappschuss, auf den
  eine ausgefüllte Checkliste verweist. Eine Vorlagenänderung ändert deshalb nie eine bereits
  ausgefüllte Checkliste (Betreiberentscheidung F: Fassungen statt Feldkopie).
- "Bearbeiten" einer Vorlage ohne Entwurf legt eine neue Entwurfsfassung als vollständige Kopie
  der gültigen an (start_draft()); field_key bleibt dabei erhalten.

Zweck (seit 1.8.16, Registry app/checklist_purposes.py): steht an der Vorlage und ist nur bis zur
ersten Veröffentlichung änderbar; Veröffentlichen friert ihn an der Fassung ein. Der Zweck
beschränkt die Kontexte und verlangt seine Systemfelder -- das Setzen des Zwecks legt sie im
Entwurf an (sync_system_fields()), ein neuer Entwurf und eine Kopie gleichen sie an, das
Veröffentlichen PRÜFT nur (fehlt eines oder weicht es ab, wird nicht veröffentlicht). Eine Vorlage
mit Zweck ist nur archivierbar, nicht löschbar. Seit 1.8.38 prüft das Veröffentlichen auch die
Reihenfolge der Abschnitte, die ein Zweck vorgibt, und eine Regel kann ihre Aufgabe aufs Anlegen
einer Checkliste mit Zweck verlinken (link_purpose, link_purpose_choices()).

Rollenlos wie jede Geschäftslogik dieses Projekts -- die Rollenentscheidung sitzt im Router."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .checklist_purposes import (
    DEFAULT_PURPOSE, PURPOSES, get_purpose, purpose_label, section_order_problem, system_field_spec,
)
from .models import (
    Checklist, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateFieldOption, ChecklistTemplateRule,
    ChecklistTemplateVersion,
)
from .permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN
from .tasks import PRIORITIES

FIELD_TYPES = (
    "ja_nein", "text", "zahl", "auswahl", "datum", "uhrzeit", "datum_uhrzeit", "foto", "unterschrift", "hinweis",
)
FIELD_TYPE_LABELS = {
    "ja_nein": "Ja/Nein", "text": "Text", "zahl": "Zahl", "auswahl": "Auswahl", "datum": "Datum",
    "uhrzeit": "Uhrzeit", "datum_uhrzeit": "Datum und Uhrzeit", "foto": "Foto", "unterschrift": "Unterschrift",
    "hinweis": "Hinweistext",
}
CONTEXT_TYPES = ("auftrag", "objekt", "betriebsmittel", "betrieb")
CONTEXT_COLUMNS = {
    "auftrag": "context_order", "objekt": "context_property",
    "betriebsmittel": "context_asset", "betrieb": "context_company",
}

RULE_OPERATORS = ("immer", "ist_ja", "ist_nein", "enthaelt", "kleiner", "groesser", "gleich", "ausgefuellt")
# Welcher Operator zu welchem Feldtyp passt -- "ausgefuellt" zu jedem Typ mit einer Antwort.
_OPERATOR_FIELD_TYPES = {
    "ist_ja": {"ja_nein"}, "ist_nein": {"ja_nein"}, "enthaelt": {"auswahl"},
    "kleiner": {"zahl"}, "groesser": {"zahl"}, "gleich": {"zahl"},
    "ausgefuellt": set(FIELD_TYPES) - {"hinweis"},
}
ASSIGNEE_MODES = ("rolle", "sachbearbeiter")
# Fund 3 des Befunds: Monteure haben keinen Aufgabenzugriff, "field" ist als Zielrolle sinnlos.
RULE_TARGET_ROLES = (ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_ADMIN)

# Obergrenze Fotos/Unterschriften je Feld -- Speicherbudget des 4-GB-Servers (PDF mit Fotos).
MAX_ATTACHMENTS_PER_FIELD = 20

_FIELD_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.]{0,79}$")
_FIELD_UPDATE_KEYS = {
    "field_key", "sort_order", "group_name", "field_type", "label", "help_text", "required", "allow_na",
    "multiline", "multiple", "unit", "min_value", "max_value", "decimals", "min_count", "max_count",
    "prefill_now", "signer_label",
}
_RULE_UPDATE_KEYS = {
    "field_key", "operator", "operand", "task_title", "task_description", "task_priority", "due_in_days",
    "assignee_mode", "min_visible_role", "sort_order", "link_purpose",
}
# An einem Systemfeld fest (Betreibervorgabe 1.8.16) -- dazu die Optionen. Frei bleiben
# Beschriftung, Hilfetext, Abschnitt, Reihenfolge und die übrigen Eigenschaften.
SYSTEM_LOCKED_ATTRIBUTES = {
    "field_key": "Schlüssel", "field_type": "Typ", "required": "Pflichtfeld", "allow_na": "Wahl „entfällt“",
    "multiple": "Mehrfach", "min_count": "Mindestanzahl",
}
_PUBLISHED_STATUSES = ("veroeffentlicht", "abgeloest")


# --- Serialisierung -------------------------------------------------------------------------

def option_to_dict(option: ChecklistTemplateFieldOption) -> dict:
    return {"id": option.id, "field_id": option.field_id, "option_key": option.option_key,
            "label": option.label, "sort_order": option.sort_order}


def field_to_dict(field: ChecklistTemplateField, purpose_key: str | None = None) -> dict:
    """purpose_key (seit 1.8.38): Zweck der Fassung -- ein Systemfeld bekommt daraus office_only
    und option_hints (app/checklist_purposes.py)."""
    spec = system_field_spec(purpose_key, field.field_key) if field.is_system else None
    return {
        "id": field.id, "version_id": field.version_id, "field_key": field.field_key,
        "sort_order": field.sort_order, "group_name": field.group_name, "field_type": field.field_type,
        "label": field.label, "help_text": field.help_text, "required": field.required,
        "allow_na": field.allow_na, "multiline": field.multiline, "multiple": field.multiple,
        "unit": field.unit, "min_value": field.min_value, "max_value": field.max_value,
        "decimals": field.decimals, "min_count": field.min_count, "max_count": field.max_count,
        "prefill_now": field.prefill_now, "signer_label": field.signer_label, "is_system": field.is_system,
        "options": [option_to_dict(o) for o in field.options],
        "office_only": bool(spec and spec.office_only),
        "option_hints": dict(spec.option_hints) if spec else {},
    }


def rule_to_dict(rule: ChecklistTemplateRule) -> dict:
    return {
        "id": rule.id, "version_id": rule.version_id, "field_key": rule.field_key, "operator": rule.operator,
        "operand": rule.operand, "task_title": rule.task_title, "task_description": rule.task_description,
        "task_priority": rule.task_priority, "due_in_days": rule.due_in_days,
        "assignee_mode": rule.assignee_mode, "min_visible_role": rule.min_visible_role,
        "sort_order": rule.sort_order, "link_purpose": rule.link_purpose,
    }


def version_to_dict(version: ChecklistTemplateVersion) -> dict:
    return {
        "id": version.id, "template_id": version.template_id, "version_no": version.version_no,
        "status": version.status, "purpose": version.purpose,
        "published_at": version.published_at, "created_at": version.created_at,
        "fields": [field_to_dict(f, version.purpose) for f in version.fields],
        "rules": [rule_to_dict(r) for r in version.rules],
    }


def _version_summary(version: ChecklistTemplateVersion) -> dict:
    return {"id": version.id, "version_no": version.version_no, "status": version.status,
            "published_at": version.published_at, "field_count": len(version.fields)}


def template_contexts(template: ChecklistTemplate) -> list[str]:
    return [c for c in CONTEXT_TYPES if getattr(template, CONTEXT_COLUMNS[c])]


def _published(template: ChecklistTemplate) -> ChecklistTemplateVersion | None:
    return next((v for v in template.versions if v.status == "veroeffentlicht"), None)


def _draft(template: ChecklistTemplate) -> ChecklistTemplateVersion | None:
    return next((v for v in template.versions if v.status == "entwurf"), None)


def _ever_published(template: ChecklistTemplate) -> bool:
    return any(v.status in _PUBLISHED_STATUSES for v in template.versions)


def template_to_dict(template: ChecklistTemplate, *, with_editable_version: bool = False) -> dict:
    published = _published(template)
    draft = _draft(template)
    data = {
        "id": template.id, "label": template.label, "description": template.description,
        "purpose": template.purpose, "purpose_label": purpose_label(template.purpose),
        "purpose_locked": _ever_published(template), "contexts": template_contexts(template),
        "field_readable": template.field_readable, "sort_order": template.sort_order,
        "archived": template.archived, "created_at": template.created_at, "updated_at": template.updated_at,
        "published_version_no": published.version_no if published else None,
        "published_version_id": published.id if published else None,
        "draft_version_no": draft.version_no if draft else None,
        "draft_version_id": draft.id if draft else None,
        "versions": [_version_summary(v) for v in template.versions],
    }
    if with_editable_version:
        # Im Editor zeigt sich der Entwurf, falls vorhanden, sonst die gültige Fassung (nur lesend).
        shown = draft or published
        data["editable_version"] = version_to_dict(shown) if shown else None
        # Was am Entwurf den Systemfeldern des Zwecks widerspricht -- der Editor bietet dafür
        # "Systemfelder angleichen" an, Veröffentlichen würde es ablehnen.
        data["system_field_problems"] = system_field_problems(template.purpose, draft) if draft else []
    return data


# --- Laden ----------------------------------------------------------------------------------

def _template_query():
    return select(ChecklistTemplate).options(
        selectinload(ChecklistTemplate.versions).selectinload(ChecklistTemplateVersion.fields)
        .selectinload(ChecklistTemplateField.options),
        selectinload(ChecklistTemplate.versions).selectinload(ChecklistTemplateVersion.rules),
    )


def _load_template(db: Session, template_id: int) -> ChecklistTemplate | None:
    return db.scalar(_template_query().where(ChecklistTemplate.id == template_id))


def _load_version(db: Session, version_id: int) -> ChecklistTemplateVersion | None:
    return db.scalar(
        select(ChecklistTemplateVersion).options(
            selectinload(ChecklistTemplateVersion.fields).selectinload(ChecklistTemplateField.options),
            selectinload(ChecklistTemplateVersion.rules),
        ).where(ChecklistTemplateVersion.id == version_id)
    )


def _require_draft(version: ChecklistTemplateVersion | None) -> ChecklistTemplateVersion:
    if version is None:
        raise LookupError("Fassung nicht gefunden.")
    if version.status != "entwurf":
        raise ValueError("Nur eine Entwurfsfassung kann geändert werden. Bitte zuerst einen neuen Entwurf anlegen.")
    return version


def _template_detail(db: Session, template_id: int) -> dict:
    db.expire_all()
    return template_to_dict(_load_template(db, template_id), with_editable_version=True)


# --- Vorlagen -------------------------------------------------------------------------------

def list_templates(db: Session, include_archived: bool = False) -> list[dict]:
    query = _template_query()
    if not include_archived:
        query = query.where(ChecklistTemplate.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich
    query = query.order_by(ChecklistTemplate.sort_order, ChecklistTemplate.label, ChecklistTemplate.id)
    return [template_to_dict(t) for t in db.scalars(query).all()]


def get_template(db: Session, template_id: int) -> dict | None:
    template = _load_template(db, template_id)
    return template_to_dict(template, with_editable_version=True) if template else None


def get_version(db: Session, version_id: int) -> dict | None:
    version = _load_version(db, version_id)
    return version_to_dict(version) if version else None


CONTEXT_LABELS = {"auftrag": "Auftrag", "objekt": "Objekt", "betriebsmittel": "Betriebsmittel", "betrieb": "Betrieb"}


def _check_purpose_contexts(purpose_key: str, contexts: list[str]) -> None:
    """Die Kontexte einer Vorlage müssen zu ihrem Zweck passen. Ein unbekannter Zweck (aus der
    Registry entfernt) sperrt die Verwaltungsdaten nicht -- neue Checklisten lehnt dann
    create_checklist() ab."""
    purpose = get_purpose(purpose_key)
    if purpose is None:
        return
    foreign = [c for c in contexts if c not in purpose.contexts]
    if foreign:
        allowed = ", ".join(CONTEXT_LABELS[c] for c in purpose.contexts)
        raise ValueError(f"Der Zweck {purpose.label} ist nur im Kontext {allowed} möglich -- bitte "
                         f"{', '.join(CONTEXT_LABELS.get(c, c) for c in foreign)} abwählen.")


def _apply_template_meta(template: ChecklistTemplate, *, label: str, description: str | None,
                         contexts: list[str], field_readable: bool) -> None:
    label = (label or "").strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    unknown = [c for c in contexts if c not in CONTEXT_TYPES]
    if unknown:
        raise ValueError(f"Unbekannter Kontext: {', '.join(unknown)}")
    _check_purpose_contexts(template.purpose or DEFAULT_PURPOSE, contexts)
    template.label = label
    template.description = (description or "").strip() or None
    for context, column in CONTEXT_COLUMNS.items():
        setattr(template, column, context in contexts)
    template.field_readable = bool(field_readable)


def _checked_purpose(purpose_key: str) -> str:
    if get_purpose(purpose_key) is None:
        raise ValueError(f"Unbekannter Zweck: {purpose_key}")
    return purpose_key


def create_template(db: Session, *, label: str, description: str | None = None, contexts: list[str] | None = None,
                    field_readable: bool = False, purpose: str | None = None) -> dict:
    """Legt eine Vorlage mit einer Entwurfsfassung 1 an -- leer, bzw. mit den Systemfeldern des
    Zwecks."""
    template = ChecklistTemplate(purpose=_checked_purpose(purpose or DEFAULT_PURPOSE))
    _apply_template_meta(template, label=label, description=description, contexts=contexts or [],
                         field_readable=field_readable)
    template.sort_order = (db.scalar(select(func.max(ChecklistTemplate.sort_order))) or 0) + 10
    db.add(template)
    db.flush()
    draft = ChecklistTemplateVersion(template_id=template.id, version_no=1, status="entwurf", purpose=template.purpose)
    db.add(draft)
    db.flush()
    _sync_system_fields(db, draft, template.purpose)
    db.commit()
    return _template_detail(db, template.id)


def update_template(db: Session, template_id: int, *, label: str, description: str | None, contexts: list[str],
                    field_readable: bool, purpose: str | None = None) -> dict | None:
    """Verwaltungsdaten sind KEIN Fassungsinhalt -- ändern sich ohne neue Fassung. Eine bereits
    ausgefüllte Checkliste bleibt davon unberührt (Label eingefroren, Kontexte wirken nur aufs
    Anlegen). purpose None = unverändert. Der Zweck selbst ist nur änderbar, solange die Vorlage
    nie veröffentlicht wurde (danach ist er an ihren Fassungen eingefroren); ein neuer Zweck legt
    seine Systemfelder im Entwurf an, die des alten werden gewöhnliche Felder."""
    template = _load_template(db, template_id)
    if template is None:
        return None
    new_purpose = purpose if purpose is not None else template.purpose
    changed = new_purpose != template.purpose
    try:
        if changed:
            if _ever_published(template):
                raise ValueError("Der Zweck ist seit der ersten Veröffentlichung festgelegt. Für einen anderen Zweck "
                                 "die Vorlage kopieren.")
            template.purpose = _checked_purpose(new_purpose)
        _apply_template_meta(template, label=label, description=description, contexts=contexts,
                             field_readable=field_readable)
        draft = _draft(template)
        if changed and draft is not None:
            draft.purpose = template.purpose
            _sync_system_fields(db, draft, template.purpose)
    except ValueError:
        db.rollback()  # sonst nähme der nächste Commit derselben Session den halben Stand mit
        raise
    db.commit()
    return _template_detail(db, template_id)


def set_template_archived(db: Session, template_id: int, archived: bool) -> dict | None:
    template = db.get(ChecklistTemplate, template_id)
    if template is None:
        return None
    template.archived = archived
    db.commit()
    return _template_detail(db, template_id)


def delete_template(db: Session, template_id: int) -> bool:
    """Nur solange keine Checkliste die Vorlage verwendet -- sonst archivieren (die Fassungen
    sind der Schnappschuss ausgefüllter Checklisten und dürfen nie verschwinden). Eine Vorlage mit
    Zweck nie (seit 1.8.16, Betreibervorgabe): nur archivieren."""
    template = _load_template(db, template_id)
    if template is None:
        return False
    if template.purpose != DEFAULT_PURPOSE or any(v.purpose != DEFAULT_PURPOSE for v in template.versions):
        raise ValueError(f"Eine Vorlage mit Zweck ({purpose_label(template.purpose)}) kann nur archiviert werden.")
    used = db.scalar(select(func.count(Checklist.id)).where(Checklist.template_id == template_id)) or 0
    if used:
        raise ValueError(f"Die Vorlage wird von {used} Checkliste(n) verwendet und kann nur archiviert werden.")
    db.delete(template)
    db.commit()
    return True


def _copy_version_content(db: Session, source: ChecklistTemplateVersion, target: ChecklistTemplateVersion) -> None:
    for field in source.fields:
        new_field = ChecklistTemplateField(
            version_id=target.id, field_key=field.field_key, sort_order=field.sort_order,
            group_name=field.group_name, field_type=field.field_type, label=field.label,
            help_text=field.help_text, required=field.required, allow_na=field.allow_na,
            multiline=field.multiline, multiple=field.multiple, unit=field.unit, min_value=field.min_value,
            max_value=field.max_value, decimals=field.decimals, min_count=field.min_count,
            max_count=field.max_count, prefill_now=field.prefill_now, signer_label=field.signer_label,
            is_system=field.is_system,
        )
        db.add(new_field)
        db.flush()
        for option in field.options:
            db.add(ChecklistTemplateFieldOption(
                field_id=new_field.id, option_key=option.option_key, label=option.label, sort_order=option.sort_order,
            ))
    for rule in source.rules:
        db.add(ChecklistTemplateRule(
            version_id=target.id, field_key=rule.field_key, operator=rule.operator, operand=rule.operand,
            task_title=rule.task_title, task_description=rule.task_description, task_priority=rule.task_priority,
            due_in_days=rule.due_in_days, assignee_mode=rule.assignee_mode,
            min_visible_role=rule.min_visible_role, sort_order=rule.sort_order, link_purpose=rule.link_purpose,
        ))


def start_draft(db: Session, template_id: int) -> dict | None:
    """Neue Entwurfsfassung als Kopie der gültigen -- existiert schon ein Entwurf, wird er
    unverändert zurückgegeben (idempotent, kein zweiter Entwurf)."""
    template = _load_template(db, template_id)
    if template is None:
        return None
    if _draft(template) is None:
        source = _published(template) or (template.versions[-1] if template.versions else None)
        next_no = max((v.version_no for v in template.versions), default=0) + 1
        draft = ChecklistTemplateVersion(template_id=template.id, version_no=next_no, status="entwurf",
                                         purpose=template.purpose)
        db.add(draft)
        db.flush()
        if source is not None:
            _copy_version_content(db, source, draft)
        _try_sync_system_fields(db, draft, template.purpose)
        db.commit()
    return _template_detail(db, template_id)


def discard_draft(db: Session, template_id: int) -> dict | None:
    """Verwirft den Entwurf. Nicht erlaubt, solange die Vorlage noch nie veröffentlicht wurde --
    dann gäbe es gar keine Fassung mehr; dafür ist "Vorlage löschen" da."""
    template = _load_template(db, template_id)
    if template is None:
        return None
    draft = _draft(template)
    if draft is None:
        raise ValueError("Es gibt keinen Entwurf.")
    if _published(template) is None and not any(v.status == "abgeloest" for v in template.versions):
        raise ValueError("Die Vorlage wurde noch nie veröffentlicht -- stattdessen die Vorlage löschen.")
    db.delete(draft)
    db.commit()
    return _template_detail(db, template_id)


def copy_template(db: Session, template_id: int, new_label: str) -> dict:
    """Neue, eigenständige Vorlage mit einer Entwurfsfassung 1 aus dem aktuellen Stand (Entwurf
    vor gültiger Fassung) der Quelle. Erbt den Zweck und die Systemfelder (seit 1.8.16); da die
    Kopie noch nie veröffentlicht wurde, ist ihr Zweck wieder änderbar."""
    source = _load_template(db, template_id)
    if source is None:
        raise LookupError("Vorlage nicht gefunden.")
    copy = ChecklistTemplate(purpose=source.purpose)
    _apply_template_meta(copy, label=new_label, description=source.description,
                         contexts=template_contexts(source), field_readable=source.field_readable)
    copy.sort_order = (db.scalar(select(func.max(ChecklistTemplate.sort_order))) or 0) + 10
    db.add(copy)
    db.flush()
    draft = ChecklistTemplateVersion(template_id=copy.id, version_no=1, status="entwurf", purpose=copy.purpose)
    db.add(draft)
    db.flush()
    source_version = _draft(source) or _published(source)
    if source_version is not None:
        _copy_version_content(db, source_version, draft)
    _try_sync_system_fields(db, draft, copy.purpose)
    db.commit()
    return _template_detail(db, copy.id)


# --- Veröffentlichen ------------------------------------------------------------------------

def validate_version_for_publish(template: ChecklistTemplate, version: ChecklistTemplateVersion) -> list[str]:
    """Liefert alle Gründe, die gegen das Veröffentlichen sprechen (leer = in Ordnung). Regeln
    werden hier ERNEUT geprüft, weil sich ein Feld nach dem Anlegen der Regel geändert haben kann
    (Typwechsel, Option gelöscht)."""
    problems: list[str] = []
    if not template_contexts(template):
        problems.append("Mindestens ein Kontext (Auftrag, Objekt, Betriebsmittel, Betrieb) muss gewählt sein.")
    try:
        _check_purpose_contexts(template.purpose, template_contexts(template))
    except ValueError as exc:
        problems.append(str(exc))
    problems.extend(system_field_problems(template.purpose, version))
    answerable = [f for f in version.fields if f.field_type != "hinweis"]
    if not answerable:
        problems.append("Die Vorlage braucht mindestens ein Feld, das ausgefüllt wird.")
    for field in version.fields:
        if field.field_type == "auswahl" and not field.options:
            problems.append(f"Das Auswahlfeld \"{field.label}\" hat keine Optionen.")
    fields_by_key = {f.field_key: f for f in version.fields}
    for rule in version.rules:
        try:
            _validate_rule_values(fields_by_key, rule.field_key, rule.operator, rule.operand, rule.task_title,
                                  rule.task_priority, rule.assignee_mode, rule.min_visible_role, rule.due_in_days,
                                  rule.link_purpose)
        except ValueError as exc:
            problems.append(f"Regel \"{rule.task_title}\": {exc}")
    return problems


def publish_draft(db: Session, template_id: int, published_by_user_id: int | None = None) -> dict | None:
    template = _load_template(db, template_id)
    if template is None:
        return None
    draft = _draft(template)
    if draft is None:
        raise ValueError("Es gibt keinen Entwurf zum Veröffentlichen.")
    problems = validate_version_for_publish(template, draft)
    if problems:
        raise ValueError(" ".join(problems))
    previous = _published(template)
    if previous is not None:
        previous.status = "abgeloest"
    draft.status = "veroeffentlicht"
    draft.purpose = template.purpose  # eingefroren: jede Checkliste dieser Fassung nutzt diesen Zweck
    draft.published_at = datetime.utcnow()
    draft.published_by_user_id = published_by_user_id
    db.commit()
    return _template_detail(db, template_id)


# --- Felder ---------------------------------------------------------------------------------

def _slugify_key(text: str) -> str:
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    text = "".join(replacements.get(c, c) for c in (text or "").lower())
    key = re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:60]
    return key or "feld"


def _unique_key(version: ChecklistTemplateVersion, base: str, exclude_field_id: int | None = None) -> str:
    taken = {f.field_key for f in version.fields if f.id != exclude_field_id}
    key, n = base, 2
    while key in taken:
        key = f"{base}_{n}"
        n += 1
    return key


def _to_decimal(value, label: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} ist keine gültige Zahl.") from exc


def _normalize_field(field: ChecklistTemplateField) -> None:
    """Prüft die Feldwerte und setzt typfremde Eigenschaften auf ihren neutralen Wert zurück,
    damit z. B. ein von "foto" auf "text" umgestelltes Feld keine verwaiste Mindestanzahl trägt."""
    if field.field_type not in FIELD_TYPES:
        raise ValueError(f"Unbekannter Feldtyp: {field.field_type}")
    field.label = (field.label or "").strip()
    if not field.label:
        raise ValueError("Bitte eine Beschriftung angeben.")
    if not _FIELD_KEY_PATTERN.match(field.field_key or ""):
        raise ValueError("Der Feldschlüssel darf nur Kleinbuchstaben, Ziffern, Unterstrich und Punkt enthalten.")
    field.group_name = (field.group_name or "").strip() or None
    field.help_text = (field.help_text or "").strip() or None
    t = field.field_type
    if t == "hinweis":
        field.required = False
    if t != "ja_nein":
        field.allow_na = False
    if t != "text":
        field.multiline = False
    if t not in ("auswahl", "unterschrift"):
        field.multiple = False
    if t != "zahl":
        field.unit = None
        field.min_value = None
        field.max_value = None
        field.decimals = None
    else:
        field.unit = (field.unit or "").strip() or None
        if field.min_value is not None and field.max_value is not None and field.min_value > field.max_value:
            raise ValueError("Der Mindestwert ist größer als der Höchstwert.")
        if field.decimals is not None and not 0 <= field.decimals <= 4:
            raise ValueError("Nachkommastellen: 0 bis 4.")
    if t in ("foto", "unterschrift"):
        if field.min_count is not None and field.min_count < 0:
            raise ValueError("Die Mindestanzahl darf nicht negativ sein.")
        if field.max_count is not None and not 1 <= field.max_count <= MAX_ATTACHMENTS_PER_FIELD:
            raise ValueError(f"Die Höchstanzahl muss zwischen 1 und {MAX_ATTACHMENTS_PER_FIELD} liegen.")
        if field.min_count is not None and field.max_count is not None and field.min_count > field.max_count:
            raise ValueError("Die Mindestanzahl ist größer als die Höchstanzahl.")
        if t == "unterschrift" and not field.multiple:
            field.max_count = 1
    else:
        field.min_count = None
        field.max_count = None
    if t not in ("datum", "uhrzeit", "datum_uhrzeit"):
        field.prefill_now = False
    if t != "unterschrift":
        field.signer_label = None
    else:
        field.signer_label = (field.signer_label or "").strip() or None


def _field_values_from(fields: dict) -> dict:
    values = {k: v for k, v in fields.items() if k in _FIELD_UPDATE_KEYS}
    for key, label in (("min_value", "Mindestwert"), ("max_value", "Höchstwert")):
        if key in values:
            values[key] = _to_decimal(values[key], label)
    return values


def add_field(db: Session, version_id: int, fields: dict) -> dict:
    version = _require_draft(_load_version(db, version_id))
    values = _field_values_from(fields)
    values.setdefault("field_type", "ja_nein")
    values.setdefault("label", "Neues Feld")
    base_key = values.pop("field_key", None) or _slugify_key(values["label"])
    if "sort_order" not in values:
        values["sort_order"] = max((f.sort_order for f in version.fields), default=0) + 10
    field = ChecklistTemplateField(version_id=version.id, field_key=_unique_key(version, base_key), **values)
    _normalize_field(field)
    db.add(field)
    db.commit()
    return get_version(db, version.id)


def update_field(db: Session, field_id: int, fields: dict) -> dict | None:
    """exclude_unset-Muster: nur tatsächlich mitgeschickte Schlüssel ändern sich. Ein
    geänderter field_key wird in den Regeln derselben Fassung mitgezogen."""
    field = db.get(ChecklistTemplateField, field_id)
    if field is None:
        return None
    version = _require_draft(_load_version(db, field.version_id))
    values = _field_values_from(fields)
    if field.is_system:
        _check_system_field_update(field, values)
    old_key = field.field_key
    if "field_key" in values:
        new_key = (values["field_key"] or "").strip()
        if new_key != old_key and new_key in {f.field_key for f in version.fields if f.id != field.id}:
            raise ValueError(f"Der Feldschlüssel \"{new_key}\" ist in dieser Fassung schon vergeben.")
        values["field_key"] = new_key
    for key, value in values.items():
        setattr(field, key, value)
    try:
        _normalize_field(field)
    except ValueError:
        db.rollback()  # sonst nähme der nächste Commit derselben Session den halben Stand mit
        raise
    if field.field_type != "auswahl":
        for option in list(field.options):
            db.delete(option)
    if field.field_key != old_key:
        for rule in version.rules:
            if rule.field_key == old_key:
                rule.field_key = field.field_key
    db.commit()
    return get_version(db, version.id)


def delete_field(db: Session, field_id: int) -> dict | None:
    field = db.get(ChecklistTemplateField, field_id)
    if field is None:
        return None
    version = _require_draft(_load_version(db, field.version_id))
    if field.is_system:
        raise ValueError("Ein Systemfeld kann nicht gelöscht werden.")
    referencing = [r.task_title for r in version.rules if r.field_key == field.field_key]
    if referencing:
        raise ValueError(f"Das Feld wird von einer Regel verwendet ({referencing[0]}). Bitte zuerst die Regel löschen.")
    db.delete(field)
    db.commit()
    return get_version(db, version.id)


def reorder_fields(db: Session, version_id: int, field_ids: list[int]) -> dict:
    version = _require_draft(_load_version(db, version_id))
    by_id = {f.id: f for f in version.fields}
    if set(field_ids) != set(by_id):
        raise ValueError("Die Reihenfolge muss alle Felder dieser Fassung genau einmal enthalten.")
    for index, field_id in enumerate(field_ids):
        by_id[field_id].sort_order = (index + 1) * 10
    db.commit()
    return get_version(db, version.id)


# --- Systemfelder (seit 1.8.16) -------------------------------------------------------------

def _normalized_locked(attribute: str, value):
    if attribute == "field_key":
        return (value or "").strip()
    if attribute in ("required", "allow_na", "multiple"):
        return bool(value)
    return value


def _check_system_field_update(field: ChecklistTemplateField, values: dict) -> None:
    """Die festen Eigenschaften eines Systemfelds dürfen mitgeschickt werden, aber nur mit dem
    vorhandenen Wert (der Editor schickt ganze Formulare)."""
    for attribute, label in SYSTEM_LOCKED_ATTRIBUTES.items():
        if attribute in values and _normalized_locked(attribute, values[attribute]) != _normalized_locked(
                attribute, getattr(field, attribute)):
            raise ValueError(f"{label} eines Systemfelds kann nicht geändert werden.")


def _require_not_system(field: ChecklistTemplateField) -> None:
    if field.is_system:
        raise ValueError("Die Optionen eines Systemfelds sind fest vorgegeben.")


def system_field_problems(purpose_key: str, version: ChecklistTemplateVersion) -> list[str]:
    """Was einer Fassung an den Systemfeldern ihres Zwecks fehlt oder davon abweicht (leer = in
    Ordnung). Veröffentlichen lehnt ab, solange etwas übrig ist."""
    purpose = get_purpose(purpose_key)
    if purpose is None:
        return [f"Unbekannter Zweck: {purpose_key}"]
    by_key = {f.field_key: f for f in version.fields}
    problems = []
    for spec in purpose.system_fields:
        field = by_key.get(spec.key)
        if field is None or not field.is_system:
            problems.append(f"Das Systemfeld „{spec.label}“ ({spec.key}) fehlt.")
            continue
        wanted = {"field_type": spec.field_type, "required": spec.required, "allow_na": spec.allow_na,
                  "multiple": spec.multiple, "min_count": spec.min_count}
        differs = [SYSTEM_LOCKED_ATTRIBUTES[a] for a, v in wanted.items() if getattr(field, a) != v]
        if {o.option_key for o in field.options} != {key for key, _label in spec.options}:
            differs.append("Optionen")
        if differs:
            problems.append(f"Das Systemfeld „{field.label}“ ({spec.key}) weicht von der Vorgabe ab: {', '.join(differs)}.")
    # Seit 1.8.38: Abschnitte in der vorgegebenen Reihenfolge, jede Unterschrift an ihrem Ende --
    # sonst versiegelte z. B. die Unterschrift der Meldung nicht die ganze Meldung.
    order_problem = section_order_problem(purpose, [f.field_key for f in version.fields if f.is_system])
    if order_problem:
        problems.append(order_problem)
    return problems


def _sync_system_fields(db: Session, version: ChecklistTemplateVersion, purpose_key: str) -> None:
    """Gleicht die Systemfelder einer Entwurfsfassung an ihren Zweck an: fehlende anlegen (am
    Ende), feste Eigenschaften und Optionen auf die Vorgabe setzen, ein gleichnamiges gewöhnliches
    Feld desselben Typs übernehmen. Systemfelder, die der Zweck nicht (mehr) kennt, werden
    gewöhnliche Felder. Kein Commit. ValueError, bevor sich etwas ändert, wenn ein Feld mit dem
    Schlüssel eines Systemfelds einen anderen Typ hat."""
    purpose = get_purpose(purpose_key)
    if purpose is None:
        raise ValueError(f"Unbekannter Zweck: {purpose_key}")
    db.flush()
    db.expire(version, ["fields"])  # frisch kopierte Felder sind nur per version_id angehängt
    by_key = {f.field_key: f for f in version.fields}
    for spec in purpose.system_fields:
        field = by_key.get(spec.key)
        if field is not None and field.field_type != spec.field_type:
            raise ValueError(f"Das Feld „{field.label}“ trägt den Schlüssel {spec.key} des Systemfelds „{spec.label}“, "
                             f"hat aber einen anderen Typ. Bitte zuerst seinen Schlüssel ändern.")
    wanted_keys = {spec.key for spec in purpose.system_fields}
    for field in version.fields:
        if field.is_system and field.field_key not in wanted_keys:
            field.is_system = False
    next_sort = max((f.sort_order for f in version.fields), default=0) + 10
    for spec in purpose.system_fields:
        field = by_key.get(spec.key)
        if field is None:  # Abschnitt, mehrzeilig, Rollenbeschriftung: Vorschläge der Vorgabe (seit 1.8.38)
            field = ChecklistTemplateField(field_key=spec.key, field_type=spec.field_type, label=spec.label,
                                           sort_order=next_sort, group_name=spec.section, multiline=spec.multiline,
                                           signer_label=spec.signer_label)
            version.fields.append(field)
            next_sort += 10
        field.is_system = True
        field.required, field.allow_na, field.multiple = spec.required, spec.allow_na, spec.multiple
        field.min_count = spec.min_count
        _normalize_field(field)
        spec_keys = {key for key, _label in spec.options}
        for option in list(field.options):
            if option.option_key not in spec_keys:
                field.options.remove(option)
        present = {o.option_key for o in field.options}
        for index, (key, label) in enumerate(spec.options):
            if key not in present:
                field.options.append(ChecklistTemplateFieldOption(option_key=key, label=label, sort_order=(index + 1) * 10))


def _try_sync_system_fields(db: Session, version: ChecklistTemplateVersion, purpose_key: str) -> None:
    """Beim Anlegen eines Entwurfs bzw. einer Kopie: angleichen, soweit es ohne Rückfrage geht.
    Scheitert es (Schlüsselkonflikt, unbekannter Zweck), bleibt der Entwurf eine reine Kopie --
    Editor und Veröffentlichen nennen dann, was fehlt."""
    try:
        with db.begin_nested():
            _sync_system_fields(db, version, purpose_key)
            db.flush()
    except ValueError:
        pass


def sync_system_fields(db: Session, version_id: int) -> dict:
    """"Systemfelder angleichen" im Editor -- z. B. wenn der Zweck nach dem Anlegen des Entwurfs
    ein weiteres Systemfeld bekommen hat."""
    version = _require_draft(_load_version(db, version_id))
    try:
        _sync_system_fields(db, version, version.template.purpose)
    except ValueError:
        db.rollback()
        raise
    version.purpose = version.template.purpose
    db.commit()
    return get_version(db, version_id)


# --- Auswahloptionen ------------------------------------------------------------------------

def add_option(db: Session, field_id: int, label: str, option_key: str | None = None) -> dict:
    field = db.get(ChecklistTemplateField, field_id)
    if field is None:
        raise LookupError("Feld nicht gefunden.")
    _require_draft(field.version)
    _require_not_system(field)
    if field.field_type != "auswahl":
        raise ValueError("Optionen gibt es nur bei Auswahlfeldern.")
    label = (label or "").strip()
    if not label:
        raise ValueError("Bitte eine Beschriftung angeben.")
    key = (option_key or "").strip() or _slugify_key(label)
    if not _FIELD_KEY_PATTERN.match(key):
        raise ValueError("Der Optionsschlüssel darf nur Kleinbuchstaben, Ziffern, Unterstrich und Punkt enthalten.")
    taken = {o.option_key for o in field.options}
    base, n = key, 2
    while key in taken:
        key = f"{base}_{n}"
        n += 1
    sort_order = max((o.sort_order for o in field.options), default=0) + 10
    db.add(ChecklistTemplateFieldOption(field_id=field.id, option_key=key, label=label, sort_order=sort_order))
    db.commit()
    return get_version(db, field.version_id)


def update_option(db: Session, option_id: int, *, label: str | None = None, sort_order: int | None = None) -> dict | None:
    """Der option_key ist nicht änderbar -- Regeln und (in späteren Fassungen) Auswertungen
    verweisen darauf. Nur Beschriftung und Reihenfolge."""
    option = db.get(ChecklistTemplateFieldOption, option_id)
    if option is None:
        return None
    _require_draft(option.field.version)
    _require_not_system(option.field)
    if label is not None:
        label = label.strip()
        if not label:
            raise ValueError("Bitte eine Beschriftung angeben.")
        option.label = label
    if sort_order is not None:
        option.sort_order = sort_order
    db.commit()
    return get_version(db, option.field.version_id)


def delete_option(db: Session, option_id: int) -> dict | None:
    option = db.get(ChecklistTemplateFieldOption, option_id)
    if option is None:
        return None
    field = option.field
    version = _require_draft(field.version)
    _require_not_system(field)
    for rule in version.rules:
        if rule.field_key == field.field_key and rule.operator == "enthaelt" and rule.operand == option.option_key:
            raise ValueError(f"Die Option wird von einer Regel verwendet ({rule.task_title}).")
    version_id = field.version_id
    db.delete(option)
    db.commit()
    return get_version(db, version_id)


# --- Regeln ---------------------------------------------------------------------------------

def link_purpose_choices() -> list[dict]:
    """Zwecke, auf deren Anlegen die Aufgabe einer Regel verlinken kann (seit 1.8.38): jeder Zweck
    außer "allgemein", der am Auftrag erlaubt ist -- der Link führt zum Anlegen am selben Auftrag."""
    return [{"key": p.key, "label": p.label} for p in PURPOSES.values()
            if p.key != DEFAULT_PURPOSE and "auftrag" in p.contexts]


def _validate_rule_values(fields_by_key: dict, field_key, operator, operand, task_title, task_priority,
                          assignee_mode, min_visible_role, due_in_days, link_purpose=None) -> None:
    if operator not in RULE_OPERATORS:
        raise ValueError(f"Unbekannte Bedingung: {operator}")
    if link_purpose is not None and link_purpose not in {c["key"] for c in link_purpose_choices()}:
        raise ValueError(f"Unbekannter Zweck für den Link der Aufgabe: {link_purpose}")
    if not (task_title or "").strip():
        raise ValueError("Bitte einen Aufgabentitel angeben.")
    if task_priority not in PRIORITIES:
        raise ValueError(f"Unbekannte Priorität: {task_priority}")
    if assignee_mode not in ASSIGNEE_MODES:
        raise ValueError(f"Unbekannter Empfänger: {assignee_mode}")
    if min_visible_role not in RULE_TARGET_ROLES:
        raise ValueError("Zielrolle muss eine Büro- oder Admin-Rolle sein (Monteure sehen keine Aufgaben).")
    if due_in_days is not None and not 0 <= due_in_days <= 365:
        raise ValueError("Fällig in: 0 bis 365 Tage.")
    if operator == "immer":
        return
    field = fields_by_key.get(field_key)
    if field is None:
        raise ValueError("Das Feld der Bedingung existiert in dieser Fassung nicht.")
    if field.field_type not in _OPERATOR_FIELD_TYPES[operator]:
        raise ValueError(f"Die Bedingung passt nicht zum Feldtyp {FIELD_TYPE_LABELS[field.field_type]}.")
    if operator == "enthaelt" and operand not in {o.option_key for o in field.options}:
        raise ValueError("Die gewählte Option existiert bei diesem Feld nicht.")
    if operator in ("kleiner", "groesser", "gleich"):
        if _to_decimal(operand, "Der Vergleichswert") is None:
            raise ValueError("Bitte einen Vergleichswert angeben.")


def _apply_rule(rule: ChecklistTemplateRule, version: ChecklistTemplateVersion) -> None:
    rule.task_title = (rule.task_title or "").strip()
    rule.task_description = (rule.task_description or "").strip() or None
    rule.link_purpose = (rule.link_purpose or "").strip() or None
    if rule.operator == "immer":
        rule.field_key = None
        rule.operand = None
    elif rule.operator in ("ist_ja", "ist_nein", "ausgefuellt"):
        rule.operand = None
    fields_by_key = {f.field_key: f for f in version.fields}
    _validate_rule_values(fields_by_key, rule.field_key, rule.operator, rule.operand, rule.task_title,
                          rule.task_priority, rule.assignee_mode, rule.min_visible_role, rule.due_in_days,
                          rule.link_purpose)


def add_rule(db: Session, version_id: int, fields: dict) -> dict:
    version = _require_draft(_load_version(db, version_id))
    values = {k: v for k, v in fields.items() if k in _RULE_UPDATE_KEYS}
    values.setdefault("operator", "immer")
    values.setdefault("task_priority", "normal")
    values.setdefault("assignee_mode", "rolle")
    values.setdefault("min_visible_role", ROLE_OFFICE_AUFTRAG)
    values.setdefault("sort_order", max((r.sort_order for r in version.rules), default=0) + 10)
    rule = ChecklistTemplateRule(version_id=version.id, **values)
    _apply_rule(rule, version)
    db.add(rule)
    db.commit()
    return get_version(db, version.id)


def update_rule(db: Session, rule_id: int, fields: dict) -> dict | None:
    rule = db.get(ChecklistTemplateRule, rule_id)
    if rule is None:
        return None
    version = _require_draft(_load_version(db, rule.version_id))
    for key, value in fields.items():
        if key in _RULE_UPDATE_KEYS:
            setattr(rule, key, value)
    try:
        _apply_rule(rule, version)
    except ValueError:
        db.rollback()
        raise
    db.commit()
    return get_version(db, version.id)


def delete_rule(db: Session, rule_id: int) -> dict | None:
    rule = db.get(ChecklistTemplateRule, rule_id)
    if rule is None:
        return None
    version_id = rule.version_id
    _require_draft(rule.version)
    db.delete(rule)
    db.commit()
    return get_version(db, version_id)
