"""Ausgefüllte Checklisten (seit 1.8.1, Modul "checklisten").

Herleitung, Betreiberentscheidungen und Etappenplan: docs/archiv/modul-checklisten.md.

Eine Checkliste verweist auf GENAU EINE veröffentlichte Vorlagenfassung -- die ist eingefroren
und damit der Schnappschuss (keine Feldkopie). Zusätzlich eingefroren werden beim Anlegen die
Bezeichnung der Vorlage und die Kontextangaben (Auftragsnummer, Objekt, Gerät), damit ein
abgeschlossenes Dokument sich nie rückwirkend ändert.

Idempotenz (Vorbereitung für Stufe 3, offline): Checkliste, Antwort und Anhang tragen eine
optionale client_uuid. Kommt dieselbe client_uuid ein zweites Mal, liefert der Server den
vorhandenen Stand zurück statt eines Fehlers -- geprüft VOR dem Schreiben, zusätzlich eine
IntegrityError aus einem gleichzeitigen Einfügen im SAVEPOINT abgefangen (Muster "Self-Seeding",
CLAUDE.md). Eine Wiederholung zählt auch nach dem Abschluss als Erfolg; eine NEUE Änderung an einer
abgeschlossenen Checkliste nicht (ChecklistLocked → 409). Antworten sind je Feld eindeutig, das
Speichern ist ein Upsert; client_recorded_at verhindert, dass eine ältere Antwort eine neuere
überschreibt.

Rollenlos wie jede Geschäftslogik dieses Projekts -- wer was sehen/ändern darf, entscheidet
app/routers/checklists.py."""

import os
from datetime import date, datetime, time as dt_time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .checklist_templates import CONTEXT_COLUMNS, CONTEXT_TYPES, MAX_ATTACHMENTS_PER_FIELD, field_to_dict
from .image_storage import resize_and_store_jpeg, store_png
from .models import (
    Checklist, ChecklistAnswer, ChecklistAnswerSelection, ChecklistAttachment, ChecklistTemplate,
    ChecklistTemplateField, ChecklistTemplateVersion, Employee, OperationalAsset, Order, Property,
)
from .operational_assets import resolve_asset_identity
from .paths import data_dir

CHECKLIST_ROOT = Path(os.getenv("DACHKONZEPTE_CHECKLIST_FILE_ROOT", data_dir() / "checklist_files"))
MAX_PHOTO_UPLOAD_BYTES = 15 * 1024 * 1024  # Rohdatei vor der Verkleinerung -- Handyfotos sind groß
MAX_SIGNATURE_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_TEXT_LENGTH = 10_000
READINESS_FIELD_KEY = "einsatzbereit"  # Entscheidung B, Zusatz: fester Schlüssel für Geräte-Checklisten

ATTACHMENT_FIELD_TYPES = {"foto": "foto", "unterschrift": "unterschrift"}
_NO_ANSWER_TYPES = {"hinweis", "foto", "unterschrift"}


class ChecklistLocked(Exception):
    """Neue Änderung an einer abgeschlossenen Checkliste -- der Router antwortet 409."""


# --- Hilfen ---------------------------------------------------------------------------------

def _employee_name(e: Employee | None) -> str | None:
    if e is None:
        return None
    return " ".join(p for p in (e.first_name, e.last_name) if p) or None


def attachment_path(attachment: ChecklistAttachment) -> Path:
    return CHECKLIST_ROOT / str(attachment.checklist_id) / attachment.stored_filename


@event.listens_for(ChecklistAttachment, "before_delete")
def _delete_attachment_file(_mapper, _connection, target: ChecklistAttachment) -> None:
    """Feuert für jeden ORM-Löschweg, auch kaskadiert beim Löschen eines ganzen Entwurfs
    (Muster app/roof_areas.py)."""
    if target.stored_filename:
        attachment_path(target).unlink(missing_ok=True)


def _load(db: Session, checklist_id: int) -> Checklist | None:
    return db.scalar(
        select(Checklist).options(
            selectinload(Checklist.template_version).selectinload(ChecklistTemplateVersion.fields)
            .selectinload(ChecklistTemplateField.options),
            selectinload(Checklist.answers).selectinload(ChecklistAnswer.selections),
            selectinload(Checklist.attachments),
            selectinload(Checklist.template),
            selectinload(Checklist.created_by_employee),
        ).where(Checklist.id == checklist_id)
    )


def get_checklist_row(db: Session, checklist_id: int) -> Checklist | None:
    return _load(db, checklist_id)


# --- Serialisierung -------------------------------------------------------------------------

def _answer_value(answer: ChecklistAnswer, field: ChecklistTemplateField):
    t = field.field_type
    if t in ("ja_nein", "text"):
        return answer.value_text
    if t == "zahl":
        return answer.value_number
    if t == "auswahl":
        if field.multiple:
            order = {o.option_key: i for i, o in enumerate(field.options)}
            return sorted((s.option_key for s in answer.selections), key=lambda k: order.get(k, 999))
        return answer.value_text
    if t == "datum":
        return answer.value_date.isoformat() if answer.value_date else None
    if t == "uhrzeit":
        return answer.value_time.strftime("%H:%M") if answer.value_time else None
    if t == "datum_uhrzeit":
        return answer.value_datetime.strftime("%Y-%m-%dT%H:%M") if answer.value_datetime else None
    return None


def _is_filled(value) -> bool:
    return value not in (None, "", [])


def checklist_summary(checklist: Checklist) -> dict:
    return {
        "id": checklist.id, "template_id": checklist.template_id,
        "template_label": checklist.template_label_snapshot, "context_type": checklist.context_type,
        "order_id": checklist.order_id, "property_id": checklist.property_id,
        "operational_asset_id": checklist.operational_asset_id,
        "context_label": checklist.context_label_snapshot, "context_detail": checklist.context_detail_snapshot,
        "status": checklist.status, "created_at": checklist.created_at, "updated_at": checklist.updated_at,
        "completed_at": checklist.completed_at, "created_by_employee_id": checklist.created_by_employee_id,
        "created_by_name": _employee_name(checklist.created_by_employee),
        "field_readable": bool(checklist.template and checklist.template.field_readable),
    }


def checklist_to_dict(checklist: Checklist) -> dict:
    """Vollständig -- Felder der Fassung (OHNE Regeln: die sind Büro-intern und für das
    Ausfüllen bedeutungslos), Antworten je Feld-ID, Anhänge."""
    fields = checklist.template_version.fields
    by_field = {a.template_field_id: a for a in checklist.answers}
    answers = {}
    for field in fields:
        answer = by_field.get(field.id)
        if answer is None or field.field_type in _NO_ANSWER_TYPES:
            continue
        answers[str(field.id)] = {
            "value": _answer_value(answer, field), "recorded_at": answer.recorded_at,
            "client_recorded_at": answer.client_recorded_at,
        }
    data = checklist_summary(checklist)
    data.update({
        "template_version_id": checklist.template_version_id,
        "version_no": checklist.template_version.version_no,
        "fields": [field_to_dict(f) for f in fields],
        "answers": answers,
        "attachments": [{
            "id": a.id, "field_id": a.template_field_id, "kind": a.kind, "signer_name": a.signer_name,
            "created_at": a.created_at, "url": f"/api/checklist-attachments/{a.id}/file",
        } for a in checklist.attachments],
        "missing_required": missing_required_labels(checklist),
    })
    return data


# --- Anlegen --------------------------------------------------------------------------------

def published_version(db: Session, template_id: int) -> ChecklistTemplateVersion | None:
    return db.scalar(select(ChecklistTemplateVersion).where(
        ChecklistTemplateVersion.template_id == template_id, ChecklistTemplateVersion.status == "veroeffentlicht",
    ))


def list_startable_templates(db: Session, context_type: str) -> list[dict]:
    """Vorlagen, die in diesem Kontext gestartet werden können: nicht archiviert, veröffentlicht,
    Kontext erlaubt. Nur Bezeichnung/Beschreibung -- keine Regeln, keine Entwürfe."""
    if context_type not in CONTEXT_TYPES:
        raise ValueError(f"Unbekannter Kontext: {context_type}")
    column = getattr(ChecklistTemplate, CONTEXT_COLUMNS[context_type])
    rows = db.execute(
        select(ChecklistTemplate, ChecklistTemplateVersion.version_no)
        .join(ChecklistTemplateVersion, ChecklistTemplateVersion.template_id == ChecklistTemplate.id)
        .where(ChecklistTemplate.archived == False, column == True,  # noqa: E712 -- SQLAlchemy-Vergleich
               ChecklistTemplateVersion.status == "veroeffentlicht")
        .order_by(ChecklistTemplate.sort_order, ChecklistTemplate.label)
    ).all()
    return [{"id": t.id, "label": t.label, "description": t.description, "version_no": no} for t, no in rows]


def _context_snapshot(db: Session, context_type: str, *, order_id, property_id, asset_id) -> tuple[str, str | None]:
    if context_type == "auftrag":
        order = db.get(Order, order_id) if order_id else None
        if order is None:
            raise LookupError("Auftrag nicht gefunden.")
        place = " · ".join(p for p in (order.property_name, (order.property_address or "").replace("\n", ", ")) if p)
        return f"Auftrag {order.order_number}", " – ".join(p for p in (order.customer_name, place) if p) or None
    if context_type == "objekt":
        prop = db.get(Property, property_id) if property_id else None
        if prop is None:
            raise LookupError("Objekt nicht gefunden.")
        address = ", ".join(p for p in (prop.street, " ".join(x for x in (prop.postal_code, prop.city) if x)) if p)
        customer = prop.customer.name if getattr(prop, "customer", None) is not None else None
        return prop.name, " – ".join(p for p in (address, customer) if p) or None
    if context_type == "betriebsmittel":
        asset = db.get(OperationalAsset, asset_id) if asset_id else None
        if asset is None:
            raise LookupError("Betriebsmittel nicht gefunden.")
        name, asset_type, manufacturer, model, _identifier, _resource_number = resolve_asset_identity(asset)
        label = name or f"Betriebsmittel #{asset.id}"
        if asset.asset_number:
            label = f"{label} ({asset.asset_number})"
        return label, " · ".join(p for p in (asset_type, manufacturer, model) if p) or None
    return "Betrieb", None


def _same_creator(checklist: Checklist, user_id: int | None, employee_id: int | None) -> bool:
    return checklist.created_by_user_id == user_id and checklist.created_by_employee_id == employee_id


def create_checklist(db: Session, *, template_id: int, context_type: str, order_id: int | None = None,
                     property_id: int | None = None, asset_id: int | None = None,
                     created_by_employee_id: int | None = None, created_by_user_id: int | None = None,
                     client_uuid: str | None = None) -> dict:
    """Legt eine Checkliste auf der AKTUELL veröffentlichten Fassung an. Gleiche client_uuid ein
    zweites Mal: derselbe Datensatz (nur, wenn ihn dieselbe Person angelegt hat -- sonst Fehler,
    eine fremde UUID darf nie fremde Daten zurückliefern)."""
    client_uuid = (client_uuid or "").strip() or None
    if client_uuid:
        existing = db.scalar(select(Checklist).where(Checklist.client_uuid == client_uuid))
        if existing is not None:
            if not _same_creator(existing, created_by_user_id, created_by_employee_id):
                raise ValueError("Diese Kennung (client_uuid) ist bereits vergeben.")
            return checklist_to_dict(_load(db, existing.id))
    if context_type not in CONTEXT_TYPES:
        raise ValueError(f"Unbekannter Kontext: {context_type}")
    template = db.get(ChecklistTemplate, template_id)
    if template is None or template.archived:
        raise LookupError("Vorlage nicht gefunden.")
    if not getattr(template, CONTEXT_COLUMNS[context_type]):
        raise ValueError("Diese Vorlage ist für diesen Kontext nicht vorgesehen.")
    version = published_version(db, template_id)
    if version is None:
        raise ValueError("Diese Vorlage ist noch nicht veröffentlicht.")
    ids = {"auftrag": order_id, "objekt": property_id, "betriebsmittel": asset_id}
    label, detail = _context_snapshot(db, context_type, order_id=order_id, property_id=property_id, asset_id=asset_id)
    checklist = Checklist(
        template_id=template.id, template_version_id=version.id, template_label_snapshot=template.label,
        context_type=context_type,
        order_id=ids["auftrag"] if context_type == "auftrag" else None,
        property_id=ids["objekt"] if context_type == "objekt" else None,
        operational_asset_id=ids["betriebsmittel"] if context_type == "betriebsmittel" else None,
        context_label_snapshot=label[:255], context_detail_snapshot=(detail or None) and detail[:500],
        created_by_employee_id=created_by_employee_id, created_by_user_id=created_by_user_id,
        client_uuid=client_uuid,
    )
    try:
        with db.begin_nested():
            db.add(checklist)
            db.flush()
    except IntegrityError:
        # Gleichzeitige Wiederholung derselben client_uuid -- der andere Aufruf war schneller.
        existing = db.scalar(select(Checklist).where(Checklist.client_uuid == client_uuid))
        if existing is None or not _same_creator(existing, created_by_user_id, created_by_employee_id):
            raise ValueError("Diese Kennung (client_uuid) ist bereits vergeben.")
        return checklist_to_dict(_load(db, existing.id))
    db.commit()
    return checklist_to_dict(_load(db, checklist.id))


# --- Lesen ----------------------------------------------------------------------------------

def get_checklist(db: Session, checklist_id: int) -> dict | None:
    checklist = _load(db, checklist_id)
    return checklist_to_dict(checklist) if checklist else None


def list_checklists(db: Session, *, context_type: str | None = None, order_id: int | None = None,
                    property_id: int | None = None, asset_id: int | None = None, status: str | None = None,
                    template_id: int | None = None, created_by_employee_id: int | None = None,
                    limit: int = 200) -> list[dict]:
    query = select(Checklist).options(selectinload(Checklist.template), selectinload(Checklist.created_by_employee))
    if context_type:
        query = query.where(Checklist.context_type == context_type)
    if order_id is not None:
        query = query.where(Checklist.order_id == order_id)
    if property_id is not None:
        query = query.where(Checklist.property_id == property_id)
    if asset_id is not None:
        query = query.where(Checklist.operational_asset_id == asset_id)
    if status:
        query = query.where(Checklist.status == status)
    if template_id is not None:
        query = query.where(Checklist.template_id == template_id)
    if created_by_employee_id is not None:
        query = query.where(Checklist.created_by_employee_id == created_by_employee_id)
    query = query.order_by(Checklist.created_at.desc(), Checklist.id.desc()).limit(max(1, min(limit, 500)))
    return [checklist_summary(c) for c in db.scalars(query).all()]


def asset_readiness(db: Session, asset_id: int) -> dict:
    """Entscheidung B, Zusatz: die jüngste ABGESCHLOSSENE Checkliste am Betriebsmittel mit einer
    Antwort auf das Feld "einsatzbereit" entscheidet. "nein" → deutlicher Hinweis auf der
    Geräteseite, eine spätere Checkliste mit "ja" hebt ihn auf."""
    row = db.execute(
        select(Checklist, ChecklistAnswer.value_text)
        .join(ChecklistAnswer, ChecklistAnswer.checklist_id == Checklist.id)
        .where(Checklist.operational_asset_id == asset_id, Checklist.status == "abgeschlossen",
               ChecklistAnswer.field_key == READINESS_FIELD_KEY, ChecklistAnswer.value_text.in_(("ja", "nein")))
        .order_by(Checklist.completed_at.desc(), Checklist.id.desc())
        .limit(1)
    ).first()
    if row is None:
        return {"asset_id": asset_id, "ready": None}
    checklist, value = row
    return {
        "asset_id": asset_id, "ready": value == "ja", "checklist_id": checklist.id,
        "template_label": checklist.template_label_snapshot, "completed_at": checklist.completed_at,
        "created_by_name": _employee_name(checklist.created_by_employee),
    }


# --- Antworten ------------------------------------------------------------------------------

def _require_draft(checklist: Checklist) -> None:
    if checklist.status != "entwurf":
        raise ChecklistLocked("Die Checkliste ist abgeschlossen und kann nicht mehr geändert werden.")


def _field_of(checklist: Checklist, field_id: int) -> ChecklistTemplateField:
    field = next((f for f in checklist.template_version.fields if f.id == field_id), None)
    if field is None:
        raise LookupError("Dieses Feld gehört nicht zu dieser Checkliste.")
    return field


def _parse_value(field: ChecklistTemplateField, value):
    """Wandelt den gesendeten Wert je Feldtyp in die Spaltenwerte um. None/""/[] leert."""
    t = field.field_type
    empty = value is None or value == "" or value == []
    columns = {"value_text": None, "value_number": None, "value_date": None, "value_time": None,
               "value_datetime": None}
    selections: list[str] = []
    if empty:
        return columns, selections
    try:
        if t == "ja_nein":
            allowed = {"ja", "nein"} | ({"entfaellt"} if field.allow_na else set())
            if value not in allowed:
                raise ValueError(f"Erlaubt sind: {', '.join(sorted(allowed))}.")
            columns["value_text"] = value
        elif t == "text":
            text = str(value).strip()
            if len(text) > MAX_TEXT_LENGTH:
                raise ValueError(f"Höchstens {MAX_TEXT_LENGTH} Zeichen.")
            columns["value_text"] = text or None
        elif t == "zahl":
            number = Decimal(str(value).replace(",", "."))
            if not number.is_finite():
                raise ValueError("Keine gültige Zahl.")
            if field.min_value is not None and number < field.min_value:
                raise ValueError(f"Mindestens {field.min_value.normalize():f}.")
            if field.max_value is not None and number > field.max_value:
                raise ValueError(f"Höchstens {field.max_value.normalize():f}.")
            if field.decimals is not None and -number.as_tuple().exponent > field.decimals:
                raise ValueError(f"Höchstens {field.decimals} Nachkommastellen.")
            columns["value_number"] = number
        elif t == "auswahl":
            keys = {o.option_key for o in field.options}
            if field.multiple:
                chosen = value if isinstance(value, list) else [value]
                if any(k not in keys for k in chosen):
                    raise ValueError("Unbekannte Option.")
                selections = list(dict.fromkeys(chosen))
            else:
                if value not in keys:
                    raise ValueError("Unbekannte Option.")
                columns["value_text"] = value
        elif t == "datum":
            columns["value_date"] = date.fromisoformat(str(value))
        elif t == "uhrzeit":
            columns["value_time"] = dt_time.fromisoformat(str(value))
        elif t == "datum_uhrzeit":
            columns["value_datetime"] = datetime.fromisoformat(str(value)).replace(tzinfo=None, second=0, microsecond=0)
        else:
            raise ValueError("Dieses Feld nimmt keine Antwort auf.")
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"\"{field.label}\": ungültiger Wert.") from exc
    except ValueError as exc:
        raise ValueError(f"\"{field.label}\": {exc}") from exc
    return columns, selections


def save_answer(db: Session, checklist_id: int, field_id: int, value, *, recorded_by_employee_id: int | None = None,
                client_uuid: str | None = None, client_recorded_at: datetime | None = None) -> dict:
    checklist = _load(db, checklist_id)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    client_uuid = (client_uuid or "").strip() or None
    if client_uuid and any(a.client_uuid == client_uuid for a in checklist.answers):
        return checklist_to_dict(checklist)  # Wiederholung -- auch nach dem Abschluss ein Erfolg
    _require_draft(checklist)
    field = _field_of(checklist, field_id)
    if field.field_type in _NO_ANSWER_TYPES:
        raise ValueError("Fotos und Unterschriften werden als Anhang gespeichert, Hinweistexte nicht beantwortet.")
    columns, selections = _parse_value(field, value)
    if client_recorded_at is not None:
        client_recorded_at = client_recorded_at.replace(tzinfo=None)

    answer = next((a for a in checklist.answers if a.template_field_id == field.id), None)
    if answer is not None and client_recorded_at and answer.client_recorded_at \
            and client_recorded_at < answer.client_recorded_at:
        return checklist_to_dict(checklist)  # ältere Antwort überschreibt keine neuere (Stufe 3)
    if answer is None:
        try:
            with db.begin_nested():
                answer = ChecklistAnswer(checklist_id=checklist.id, template_field_id=field.id, field_key=field.field_key)
                db.add(answer)
                db.flush()
        except IntegrityError:
            db.expire_all()
            answer = db.scalar(select(ChecklistAnswer).where(
                ChecklistAnswer.checklist_id == checklist.id, ChecklistAnswer.template_field_id == field.id))
            if answer is None:
                raise
    for key, val in columns.items():
        setattr(answer, key, val)
    # Abgleich statt Ersetzen der ganzen Liste: beim Ersetzen könnte die Unit of Work eine
    # gleichnamige neue Zeile vor dem Löschen der alten einfügen (Unique answer_id+option_key).
    wanted = set(selections)
    for selection in list(answer.selections):
        if selection.option_key not in wanted:
            answer.selections.remove(selection)
    present = {s.option_key for s in answer.selections}
    for key in selections:
        if key not in present:
            answer.selections.append(ChecklistAnswerSelection(option_key=key))
    answer.recorded_at = datetime.utcnow()
    answer.recorded_by_employee_id = recorded_by_employee_id
    if client_uuid:
        answer.client_uuid = client_uuid
    if client_recorded_at:
        answer.client_recorded_at = client_recorded_at
    checklist.updated_at = datetime.utcnow()
    db.commit()
    db.expire_all()
    return checklist_to_dict(_load(db, checklist_id))


# --- Anhänge (Fotos, Unterschriften) --------------------------------------------------------

def add_attachment(db: Session, checklist_id: int, field_id: int, data: bytes, *, signer_name: str | None = None,
                   created_by_employee_id: int | None = None, client_uuid: str | None = None) -> dict:
    checklist = _load(db, checklist_id)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    client_uuid = (client_uuid or "").strip() or None
    if client_uuid and any(a.client_uuid == client_uuid for a in checklist.attachments):
        return checklist_to_dict(checklist)  # Wiederholung -- keine zweite Datei
    _require_draft(checklist)
    field = _field_of(checklist, field_id)
    kind = ATTACHMENT_FIELD_TYPES.get(field.field_type)
    if kind is None:
        raise ValueError("Dieses Feld nimmt keine Fotos oder Unterschriften auf.")
    if not data:
        raise ValueError("Die Datei ist leer.")
    limit = MAX_PHOTO_UPLOAD_BYTES if kind == "foto" else MAX_SIGNATURE_UPLOAD_BYTES
    if len(data) > limit:
        raise ValueError(f"Die Datei ist zu groß (höchstens {limit // (1024 * 1024)} MB).")
    signer_name = (signer_name or "").strip() or None
    if kind == "unterschrift" and not signer_name:
        raise ValueError("Bitte den Namen der unterschreibenden Person angeben.")

    existing = [a for a in checklist.attachments if a.template_field_id == field.id]
    single_signature = kind == "unterschrift" and not field.multiple
    maximum = 1 if single_signature else (field.max_count or MAX_ATTACHMENTS_PER_FIELD)
    if not single_signature and len(existing) >= maximum:
        raise ValueError(f"Für \"{field.label}\" sind höchstens {maximum} erlaubt.")

    directory = CHECKLIST_ROOT / str(checklist.id)
    try:
        stored = resize_and_store_jpeg(directory, data) if kind == "foto" else store_png(directory, data, max_dimension=1200)
    except Exception as exc:  # Pillow wirft je nach Format unterschiedliche Ausnahmen
        raise ValueError("Die Datei ist kein lesbares Bild.") from exc
    if single_signature:
        for old in existing:  # neu unterschreiben ersetzt die bisherige Unterschrift
            db.delete(old)
    attachment = ChecklistAttachment(
        checklist_id=checklist.id, template_field_id=field.id, kind=kind, stored_filename=stored,
        signer_name=signer_name if kind == "unterschrift" else None,
        sort_order=(max((a.sort_order for a in existing), default=0) + 10),
        created_by_employee_id=created_by_employee_id, client_uuid=client_uuid,
    )
    try:
        with db.begin_nested():
            db.add(attachment)
            db.flush()
    except IntegrityError:
        (directory / stored).unlink(missing_ok=True)  # gleichzeitige Wiederholung: Datei nicht doppelt behalten
        db.expire_all()
        return checklist_to_dict(_load(db, checklist_id))
    checklist.updated_at = datetime.utcnow()
    db.commit()
    db.expire_all()
    return checklist_to_dict(_load(db, checklist_id))


def get_attachment(db: Session, attachment_id: int) -> ChecklistAttachment | None:
    return db.get(ChecklistAttachment, attachment_id)


def delete_attachment(db: Session, attachment_id: int) -> dict | None:
    attachment = db.get(ChecklistAttachment, attachment_id)
    if attachment is None:
        return None
    checklist_id = attachment.checklist_id
    checklist = _load(db, checklist_id)
    _require_draft(checklist)
    db.delete(attachment)
    checklist.updated_at = datetime.utcnow()
    db.commit()
    db.expire_all()
    return checklist_to_dict(_load(db, checklist_id))


# --- Abschließen, Löschen -------------------------------------------------------------------

def missing_required_labels(checklist: Checklist) -> list[str]:
    """Beschriftungen aller noch fehlenden Pflichtangaben. Bei Foto/Unterschrift zählt die
    Mindestanzahl (min_count, bei Pflicht mindestens 1) -- ein nicht als Pflicht markiertes
    Fotofeld mit Mindestanzahl gilt ebenfalls als Pflicht."""
    by_field = {a.template_field_id: a for a in checklist.answers}
    counts: dict[int, int] = {}
    for a in checklist.attachments:
        counts[a.template_field_id] = counts.get(a.template_field_id, 0) + 1
    missing = []
    for field in checklist.template_version.fields:
        if field.field_type == "hinweis":
            continue
        if field.field_type in ATTACHMENT_FIELD_TYPES:
            needed = max(field.min_count or 0, 1 if field.required else 0)
            if counts.get(field.id, 0) < needed:
                missing.append(field.label if needed <= 1 else f"{field.label} (mindestens {needed})")
            continue
        if field.required:
            answer = by_field.get(field.id)
            if answer is None or not _is_filled(_answer_value(answer, field)):
                missing.append(field.label)
    return missing


def complete_checklist(db: Session, checklist_id: int, *, completed_by_employee_id: int | None = None) -> dict:
    """Friert ein. Zweiter Aufruf auf einer bereits abgeschlossenen Checkliste: aktueller Stand,
    kein Fehler (idempotent). Die Regeln (Aufgaben) laufen ab 1.8.2 NACH diesem Commit."""
    checklist = _load(db, checklist_id)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    if checklist.status == "abgeschlossen":
        return checklist_to_dict(checklist)
    missing = missing_required_labels(checklist)
    if missing:
        raise ValueError("Noch nicht ausgefüllt: " + ", ".join(missing) + ".")
    checklist.status = "abgeschlossen"
    checklist.completed_at = datetime.utcnow()
    checklist.completed_by_employee_id = completed_by_employee_id
    db.commit()
    db.expire_all()
    return checklist_to_dict(_load(db, checklist_id))


def delete_checklist(db: Session, checklist_id: int) -> bool:
    """Nur ein Entwurf -- eine abgeschlossene Checkliste ist ein Nachweis und bleibt."""
    checklist = _load(db, checklist_id)
    if checklist is None:
        return False
    _require_draft(checklist)
    db.delete(checklist)
    db.commit()
    return True

