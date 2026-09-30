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

Unterschrift bindet den Inhalt (seit 1.8.13): mit der ersten Unterschrift sind Antworten und Fotos
gesperrt (ChecklistLocked → 409). Jede Unterschrift speichert ihren Zeitpunkt (created_at, UTC) und
die SHA-256-Prüfsumme der Antworten und Fotos (signed_content_sha256()). Weitere Unterschriften
bleiben möglich, keine wird ersetzt oder gelöscht -- auch kein Entwurf mehr, der eine trägt. Nur
das Büro kann die Unterschriften mit Begründung verwerfen (discard_signatures(), der Router prüft
die Rolle); sie bleiben dann als Nachweis stehen, zählen aber nicht mehr, und die Checkliste ist
wieder offen.

Rollenlos wie jede Geschäftslogik dieses Projekts -- wer was sehen/ändern darf, entscheidet
app/routers/checklists.py."""

import hashlib
import json
import os
from datetime import date, datetime, time as dt_time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .berlin_time import to_berlin
from .checklist_templates import CONTEXT_COLUMNS, CONTEXT_TYPES, MAX_ATTACHMENTS_PER_FIELD, field_to_dict
from .image_storage import resize_and_store_jpeg, store_png
from .models import (
    Checklist, ChecklistAnswer, ChecklistAnswerSelection, ChecklistAssetRelease, ChecklistAttachment,
    ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion, Employee, OperationalAsset, Order, Property,
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
    """Neue Änderung an einer abgeschlossenen oder unterschriebenen Checkliste -- der Router
    antwortet 409."""


SIGNED_LOCKED = ("Die Checkliste ist unterschrieben – Antworten und Fotos sind gesperrt. "
                 "Das Büro kann die Unterschriften mit Begründung verwerfen.")


# --- Hilfen ---------------------------------------------------------------------------------

def _employee_name(e: Employee | None) -> str | None:
    if e is None:
        return None
    return " ".join(p for p in (e.first_name, e.last_name) if p) or None


def attachment_path(attachment: ChecklistAttachment) -> Path:
    return CHECKLIST_ROOT / str(attachment.checklist_id) / attachment.stored_filename


def active_attachments(checklist: Checklist) -> list[ChecklistAttachment]:
    """Fotos und Unterschriften, die zählen -- ohne verworfene Unterschriften (seit 1.8.13).
    Jede Auswertung (Pflichtangaben, Regeln, PDF, Anzeige) geht hierüber, nie direkt über
    checklist.attachments."""
    return [a for a in checklist.attachments if a.discarded_at is None]


def is_signed(checklist: Checklist) -> bool:
    return any(a.kind == "unterschrift" for a in active_attachments(checklist))


def _berlin_text(value: datetime | None) -> str | None:
    local = to_berlin(value)
    return local.strftime("%d.%m.%Y %H:%M") if local else None


@event.listens_for(ChecklistAttachment, "before_delete")
def _delete_attachment_file(_mapper, _connection, target: ChecklistAttachment) -> None:
    """Feuert für jeden ORM-Löschweg, auch kaskadiert beim Löschen eines ganzen Entwurfs
    (Muster app/roof_areas.py)."""
    if target.stored_filename:
        attachment_path(target).unlink(missing_ok=True)


def _load(db: Session, checklist_id: int, *, for_update: bool = False) -> Checklist | None:
    query = select(Checklist).options(
        selectinload(Checklist.template_version).selectinload(ChecklistTemplateVersion.fields)
        .selectinload(ChecklistTemplateField.options),
        selectinload(Checklist.answers).selectinload(ChecklistAnswer.selections),
        selectinload(Checklist.attachments),
        selectinload(Checklist.template),
        selectinload(Checklist.created_by_employee),
    ).where(Checklist.id == checklist_id)
    if for_update:
        # Zeilensperre bis zum Commit (seit 1.8.13): Antwort, Foto, Unterschrift, Verwerfen,
        # Abschließen und Löschen derselben Checkliste laufen nacheinander -- sonst könnte eine
        # Antwort zwischen Sperrprüfung und Unterschrift durchrutschen. Wirkt unter PostgreSQL,
        # SQLite (nur Entwicklung) ignoriert FOR UPDATE. populate_existing: der Router hat die
        # Checkliste vorher schon ungesperrt geladen, ohne das bliebe dieser ältere Stand stehen.
        query = query.with_for_update(of=Checklist).execution_options(populate_existing=True)
    return db.scalar(query)


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


def _file_sha256(path: Path) -> str | None:
    """Prüfsumme einer gespeicherten Datei, blockweise gelesen (Speicherbudget: bis zu 20 Fotos
    je Feld). None, wenn die Datei fehlt -- das geht so in die Prüfsumme ein."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except FileNotFoundError:
        return None
    return digest.hexdigest()


def _canonical(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")  # 12.5000 (aus der DB) und 12.5 (frisch) gleich
    return value


def signed_content_sha256(checklist: Checklist) -> str:
    """SHA-256 über das, was eine Unterschrift bindet (seit 1.8.13): Checkliste, Fassung, die
    eingefrorenen Bezeichnungen, jede ausgefüllte Antwort (nach field_key, Werte je Feldtyp wie in
    der Anzeige) und jedes nicht verworfene Foto (Prüfsumme der gespeicherten Datei). Andere
    Unterschriften gehören nicht dazu -- solange sich der Inhalt nicht ändert, tragen alle
    Unterschriften einer Checkliste dieselbe Summe. Kanonisch als JSON mit sortierten Schlüsseln;
    "v" nummeriert das Format, damit eine spätere Änderung alte Summen nachprüfbar lässt."""
    fields = checklist.template_version.fields
    by_field = {a.template_field_id: a for a in checklist.answers}
    answers = []
    for field in fields:
        answer = by_field.get(field.id)
        if answer is None or field.field_type in _NO_ANSWER_TYPES:
            continue
        value = _answer_value(answer, field)
        if _is_filled(value):
            answers.append({"field_key": field.field_key, "value": _canonical(value)})
    order = {f.id: i for i, f in enumerate(fields)}
    photos = sorted((a for a in active_attachments(checklist) if a.kind == "foto"),
                    key=lambda a: (order.get(a.template_field_id, 999_999), a.sort_order, a.id))
    keys = {f.id: f.field_key for f in fields}
    content = {
        "v": 1, "checklist_id": checklist.id, "template_version_id": checklist.template_version_id,
        "template_label": checklist.template_label_snapshot, "context_type": checklist.context_type,
        "context_label": checklist.context_label_snapshot, "context_detail": checklist.context_detail_snapshot,
        "answers": answers,
        "photos": [{"field_key": keys.get(a.template_field_id), "id": a.id,
                    "sha256": _file_sha256(attachment_path(a))} for a in photos],
    }
    raw = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _attachment_dict(a: ChecklistAttachment) -> dict:
    return {
        "id": a.id, "field_id": a.template_field_id, "kind": a.kind, "signer_name": a.signer_name,
        "created_at": a.created_at, "created_at_local": _berlin_text(a.created_at),
        "content_sha256": a.content_sha256, "url": f"/api/checklist-attachments/{a.id}/file",
    }


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
        "attachments": [_attachment_dict(a) for a in active_attachments(checklist)],
        "discarded_signatures": [{
            **_attachment_dict(a), "discarded_at": a.discarded_at, "discarded_at_local": _berlin_text(a.discarded_at),
            "discarded_by_name": a.discarded_by_name, "discard_reason": a.discard_reason,
        } for a in checklist.attachments if a.discarded_at is not None],
        "signed": is_signed(checklist),
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
                    ids: list[int] | None = None, limit: int = 200) -> list[dict]:
    query = select(Checklist).options(selectinload(Checklist.template), selectinload(Checklist.created_by_employee))
    if ids is not None:
        query = query.where(Checklist.id.in_(ids))
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


def _latest_readiness_answer(db: Session, asset_id: int):
    return db.execute(
        select(Checklist, ChecklistAnswer.value_text)
        .join(ChecklistAnswer, ChecklistAnswer.checklist_id == Checklist.id)
        .where(Checklist.operational_asset_id == asset_id, Checklist.status == "abgeschlossen",
               ChecklistAnswer.field_key == READINESS_FIELD_KEY, ChecklistAnswer.value_text.in_(("ja", "nein")))
        .order_by(Checklist.completed_at.desc(), Checklist.id.desc())
        .limit(1)
    ).first()


def asset_readiness(db: Session, asset_id: int) -> dict:
    """Entscheidung B, Zusatz: die jüngste ABGESCHLOSSENE Checkliste am Betriebsmittel mit einer
    Antwort auf das Feld "einsatzbereit" entscheidet. "nein" → deutlicher Hinweis auf der
    Geräteseite. Aufgehoben wird er auf zwei Wegen (seit 1.8.2): eine spätere Checkliste mit "ja"
    ODER das Büro markiert das Gerät als repariert (ChecklistAssetRelease an genau dieser
    "nein"-Checkliste). Eine danach erneut abgeschlossene Checkliste mit "nein" gilt wieder."""
    row = _latest_readiness_answer(db, asset_id)
    if row is None:
        return {"asset_id": asset_id, "ready": None}
    checklist, value = row
    data = {
        "asset_id": asset_id, "ready": value == "ja", "checklist_id": checklist.id,
        "template_label": checklist.template_label_snapshot, "completed_at": checklist.completed_at,
        "created_by_name": _employee_name(checklist.created_by_employee),
        "reported_ready": value == "ja",
    }
    if value == "nein":
        release = db.scalar(select(ChecklistAssetRelease).where(ChecklistAssetRelease.checklist_id == checklist.id))
        if release is not None:
            data.update({"ready": True, "released_at": release.released_at,
                         "released_by_name": release.released_by_name, "release_note": release.note})
    return data


def mark_asset_repaired(db: Session, asset_id: int, *, note: str | None = None, user_id: int | None = None,
                        employee_id: int | None = None, by_name: str | None = None) -> dict:
    """Hebt die aktuell wirksame Meldung "nicht einsatzbereit" auf (seit 1.8.2, nur Büro --
    entscheidet der Router). Die Checkliste selbst bleibt unverändert. Wiederholt (schon
    aufgehoben) → aktueller Stand, kein Fehler. Kein wirksames "nein" → ValueError. Seit 1.8.13
    ist die Notiz Pflicht (was wurde repariert?) -- sie steht mit Wer/Wann in der
    Änderungshistorie."""
    if db.get(OperationalAsset, asset_id) is None:
        raise LookupError("Betriebsmittel nicht gefunden.")
    row = _latest_readiness_answer(db, asset_id)
    if row is None or row[1] != "nein":
        raise ValueError("Für dieses Gerät liegt keine Meldung „nicht einsatzbereit“ vor.")
    note = (note or "").strip()[:MAX_TEXT_LENGTH]
    if not note:
        raise ValueError("Bitte in der Notiz angeben, was repariert wurde.")
    checklist = row[0]
    if db.scalar(select(ChecklistAssetRelease.id).where(ChecklistAssetRelease.checklist_id == checklist.id)) is None:
        release = ChecklistAssetRelease(
            operational_asset_id=asset_id, checklist_id=checklist.id, released_by_user_id=user_id,
            released_by_employee_id=employee_id, released_by_name=(by_name or "").strip()[:160] or None,
            note=note,
        )
        try:
            with db.begin_nested():
                db.add(release)
                db.flush()
        except IntegrityError:
            pass  # gleichzeitiger zweiter Klick -- der andere war schneller, Ergebnis dasselbe
        db.commit()
    return asset_readiness(db, asset_id)


# --- Antworten ------------------------------------------------------------------------------

def _require_draft(checklist: Checklist) -> None:
    if checklist.status != "entwurf":
        raise ChecklistLocked("Die Checkliste ist abgeschlossen und kann nicht mehr geändert werden.")


def _require_unsigned(checklist: Checklist, message: str = SIGNED_LOCKED) -> None:
    if is_signed(checklist):
        raise ChecklistLocked(message)


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
    checklist = _load(db, checklist_id, for_update=True)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    client_uuid = (client_uuid or "").strip() or None
    if client_uuid and any(a.client_uuid == client_uuid for a in checklist.answers):
        return checklist_to_dict(checklist)  # Wiederholung -- auch nach dem Abschluss ein Erfolg
    _require_draft(checklist)
    _require_unsigned(checklist)
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
    checklist = _load(db, checklist_id, for_update=True)
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
    existing = [a for a in active_attachments(checklist) if a.template_field_id == field.id]
    single_signature = kind == "unterschrift" and not field.multiple
    if kind == "foto":
        _require_unsigned(checklist)
    elif single_signature and existing:
        raise ChecklistLocked(f"\"{field.label}\" ist bereits unterschrieben – eine Unterschrift wird nicht ersetzt.")
    if not data:
        raise ValueError("Die Datei ist leer.")
    limit = MAX_PHOTO_UPLOAD_BYTES if kind == "foto" else MAX_SIGNATURE_UPLOAD_BYTES
    if len(data) > limit:
        raise ValueError(f"Die Datei ist zu groß (höchstens {limit // (1024 * 1024)} MB).")
    signer_name = (signer_name or "").strip() or None
    if kind == "unterschrift" and not signer_name:
        raise ValueError("Bitte den Namen der unterschreibenden Person angeben.")

    maximum = 1 if single_signature else (field.max_count or MAX_ATTACHMENTS_PER_FIELD)
    if len(existing) >= maximum:
        raise ValueError(f"Für \"{field.label}\" sind höchstens {maximum} erlaubt.")
    # Was diese Unterschrift bindet -- berechnet vor dem Speichern, also ohne sie selbst.
    content_sha256 = signed_content_sha256(checklist) if kind == "unterschrift" else None

    directory = CHECKLIST_ROOT / str(checklist.id)
    try:
        stored = resize_and_store_jpeg(directory, data) if kind == "foto" else store_png(directory, data, max_dimension=1200)
    except Exception as exc:  # Pillow wirft je nach Format unterschiedliche Ausnahmen
        raise ValueError("Die Datei ist kein lesbares Bild.") from exc
    attachment = ChecklistAttachment(
        checklist_id=checklist.id, template_field_id=field.id, kind=kind, stored_filename=stored,
        signer_name=signer_name if kind == "unterschrift" else None,
        sort_order=(max((a.sort_order for a in checklist.attachments if a.template_field_id == field.id), default=0) + 10),
        created_by_employee_id=created_by_employee_id, client_uuid=client_uuid, content_sha256=content_sha256,
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
    checklist = _load(db, checklist_id, for_update=True)
    _require_draft(checklist)
    if attachment.discarded_at is not None:
        raise ChecklistLocked("Eine verworfene Unterschrift bleibt als Nachweis erhalten.")
    _require_unsigned(checklist)  # weder Foto noch Unterschrift -- ab der ersten Unterschrift
    db.delete(attachment)
    checklist.updated_at = datetime.utcnow()
    db.commit()
    db.expire_all()
    return checklist_to_dict(_load(db, checklist_id))


def discard_signatures(db: Session, checklist_id: int, *, reason: str | None, user_id: int | None = None,
                       by_name: str | None = None) -> dict:
    """"Unterschriften verwerfen" (seit 1.8.13, nur Büro -- entscheidet der Router): alle
    gültigen Unterschriften eines Entwurfs werden mit Begründung, Wer und Wann als verworfen
    markiert, die Checkliste ist danach wieder offen. Gelöscht wird nichts -- Bild, Name,
    Zeitpunkt und Prüfsumme bleiben als Nachweis stehen, die Änderungshistorie hält den Vorgang
    fest. Eine abgeschlossene Checkliste bleibt eingefroren (409)."""
    checklist = _load(db, checklist_id, for_update=True)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    _require_draft(checklist)
    reason = (reason or "").strip()[:MAX_TEXT_LENGTH]
    if not reason:
        raise ValueError("Bitte begründen, warum die Unterschriften verworfen werden.")
    signatures = [a for a in active_attachments(checklist) if a.kind == "unterschrift"]
    if not signatures:
        raise ValueError("Diese Checkliste trägt keine Unterschrift.")
    now = datetime.utcnow()
    for signature in signatures:
        signature.discarded_at = now
        signature.discarded_by_user_id = user_id
        signature.discarded_by_name = (by_name or "").strip()[:160] or None
        signature.discard_reason = reason
    checklist.updated_at = now
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
    for a in active_attachments(checklist):
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
    kein Fehler (idempotent). Die Regeln (Aufgaben, seit 1.8.3) laufen NACH diesem Commit
    (Fund 4: create_task() committet selbst) -- ein Fehler dort macht den Abschluss nicht
    rückgängig, die Aufgabe bleibt im Büro nachholbar."""
    checklist = _load(db, checklist_id, for_update=True)
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
    from .checklist_rules import run_rules_after_completion  # lokal, Muster Regel 3
    run_rules_after_completion(db, checklist_id)
    db.expire_all()
    return checklist_to_dict(_load(db, checklist_id))


def delete_checklist(db: Session, checklist_id: int) -> bool:
    """Nur ein Entwurf -- eine abgeschlossene Checkliste ist ein Nachweis und bleibt. Seit 1.8.13
    auch kein unterschriebener Entwurf: Löschen würde die Unterschriften mitlöschen."""
    checklist = _load(db, checklist_id, for_update=True)
    if checklist is None:
        return False
    _require_draft(checklist)
    _require_unsigned(checklist, "Die Checkliste ist unterschrieben und kann nicht gelöscht werden. "
                                 "Das Büro kann die Unterschriften mit Begründung verwerfen.")
    db.delete(checklist)
    db.commit()
    return True

