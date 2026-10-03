"""Abnahme zum Auftrag (seit 1.8.46, Stufe 2c-1, docs/archiv/abnahme-und-gewaehrleistung.md).

Mehrere Einträge je Auftrag (Teilabnahmen, Verweigerung, Korrektur). Ein Eintrag hält fest:

- Art: förmlich, ausdrücklich, schlüssig. Datum: Pflicht, ohne Vorgabe, nicht in der Zukunft.
- Umfang: gesamt, oder Teil mit Pflicht-Beschreibung; Dachflächen optional (bei beiden), nur aus dem Objekt des
  Projekts beim Erfassen (property_id wird mitgespeichert), nicht archiviert.
- Ergebnis: abgenommen oder verweigert. Bei "abgenommen" zwei Pflichtfragen ohne Vorgabe (Vorbehalt Mängel, Vorbehalt
  Vertragsstrafe); "mit Vorbehalten" wird nur abgeleitet (result_text()), nie gespeichert.
- Einwendungen des Auftragnehmers (Text).
- Erklärt durch: Auftraggeber (Name = Kunde laut Auftrag) oder einen Beteiligten des Projekts (Name und Rolle als
  Schnappschuss). Ohne Empfangsvollmacht mit Beleg nur eine Warnung (poa_on_record falsch); mit ihr wird der Beleg
  als Kopie mit Prüfsumme festgehalten -- der Beteiligte kann ihn später ersetzen oder entfernen.
- Nachweis: Beleg (PDF oder Foto, am Inhalt erkannt, unverändert gespeichert, SHA-256); bei "schlüssig" stattdessen
  eine Pflicht-Begründung (ein Beleg ist dort zusätzlich erlaubt).

Nach dem Speichern unveränderlich: ORM-Sperre (app/models.py), Dateien exklusiv angelegt und schreibgeschützt,
content_sha256 über den Inhalt samt Prüfsummen der Belege -- jeder Abruf rechnet nach (verify_acceptance()), eine am
ORM vorbei geänderte Zeile oder Datei erscheint als "weicht ab". Korrektur nur durch Verwerfen mit Begründung
(bedingtes UPDATE, Historie) und einen neuen Eintrag.

Abgleich mit dem Angebot: gesperrt, solange eine nicht verworfene Abnahme besteht (ensure_no_active_acceptance(),
seit 1.8.46 Punkt 7). Erfassen, Verwerfen und Abgleich sperren dieselbe Zeile (der Auftrag, SELECT … FOR UPDATE).

Rollenlos wie jede Geschäftslogik; wer erfassen darf, entscheidet der Router (ab buero_auftrag, Monteure nichts).
"""

import hashlib
import json
import os
import stat
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from .berlin_time import berlin_today, to_berlin
from .models import (
    Order, OrderAcceptance, OrderAcceptanceFile, OrderAcceptanceRoofArea, Project, ProjectParticipant, Property,
    RoofArea,
)
from .paths import data_dir
from .warranty import END_RULE_TEXT, duration_text, warranty_end

KINDS = {"foermlich": "förmlich", "ausdruecklich": "ausdrücklich", "schluessig": "schlüssig"}
SCOPES = {"gesamt": "Gesamtabnahme", "teil": "Teilabnahme"}
RESULTS = {"abgenommen": "abgenommen", "verweigert": "verweigert"}
DECLARERS = {"auftraggeber": "Auftraggeber", "beteiligter": "Beteiligter"}
FILE_KINDS = {"nachweis": "Nachweis", "vollmacht": "Vollmacht des Beteiligten (beim Erfassen hinterlegt)"}

MAX_FILES = 5
MAX_FILE_BYTES = 15_000_000  # wie der Beleg einer Zustellung (app/email_dispatch.py::MAX_RECEIPT_BYTES)
MAX_TOTAL_BYTES = 30_000_000  # alle Belege eines Eintrags zusammen -- Speicherbudget des Servers
SCOPE_TEXT_MAX = 2000
TEXT_MAX = 5000
REASON_MAX = 2000

ACCEPTANCE_FILE_ROOT = Path(os.getenv("DACHKONZEPTE_ACCEPTANCE_FILE_ROOT", data_dir() / "acceptance_documents"))
_SUFFIXES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

ENTITY_TYPE = "Abnahme"  # Änderungshistorie (app/audit.py)

VERIFY_TEXTS = {
    "unveraendert": "unverändert (Prüfsumme stimmt)",
    "abweichend": "weicht von der beim Speichern festgehaltenen Prüfsumme ab",
    "fehlt": "Datei fehlt",
}


class AcceptanceExistsError(ValueError):
    """Eine nicht verworfene Abnahme sperrt die Aktion (Abgleich mit dem Angebot) -- Router: 409."""


class AcceptanceConflict(ValueError):
    """Der Stand hat sich geändert (schon verworfen) -- Router: 409."""


class AcceptanceFileError(Exception):
    def __init__(self, status: str):
        super().__init__(VERIFY_TEXTS[status])
        self.status = status


# ---------------------------------------------------------------------------
# Sperre und Abgleich
# ---------------------------------------------------------------------------

def lock_order(db: Session, order_id: int) -> None:
    """Sperrt die Zeile des Auftrags bis zum Commit (PostgreSQL; SQLite ignoriert FOR UPDATE und serialisiert ohnehin
    jeden Schreibzugriff). Erfassen, Verwerfen und der Abgleich mit dem Angebot warten so aufeinander."""
    db.execute(select(Order.id).where(Order.id == order_id).with_for_update())


def has_active_acceptance(db: Session, order_id: int) -> bool:
    return db.scalar(
        select(OrderAcceptance.id)
        .where(OrderAcceptance.order_id == order_id, OrderAcceptance.discarded_at.is_(None))
        .limit(1)
    ) is not None


def ensure_no_active_acceptance(db: Session, order_id: int, action: str) -> None:
    """Sperrt den Auftrag und wirft AcceptanceExistsError, wenn eine nicht verworfene Abnahme besteht (auch eine
    verweigerte: sie hält den Leistungsstand ebenso fest)."""
    lock_order(db, order_id)
    if has_active_acceptance(db, order_id):
        raise AcceptanceExistsError(
            f"Zu diesem Auftrag ist eine Abnahme erfasst – {action} ist danach gesperrt. Änderungen (z. B. Nachträge) "
            "direkt am Auftrag erfassen; eine falsch erfasste Abnahme lässt sich mit Begründung verwerfen."
        )


# ---------------------------------------------------------------------------
# Dateien
# ---------------------------------------------------------------------------

def _path_for(stored_filename: str) -> Path:
    root = ACCEPTANCE_FILE_ROOT.resolve()
    path = (root / stored_filename).resolve()
    if root not in path.parents:
        raise AcceptanceFileError("fehlt")
    return path


def _write_file(content: bytes, content_type: str) -> str:
    """Exklusiv anlegen (nie überschreiben), schreibgeschützt setzen, Prüfsumme gegenlesen."""
    sha256 = hashlib.sha256(content).hexdigest()
    now = datetime.utcnow()
    stored = f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}_{sha256[:16]}{_SUFFIXES[content_type]}"
    path = ACCEPTANCE_FILE_ROOT / stored
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise OSError("Der gespeicherte Beleg stimmt nicht mit dem hochgeladenen Inhalt überein.")
    return stored


def _remove_written(stored_filenames: list[str]) -> None:
    """Nur für Dateien eines gescheiterten Speicherns, die nie zu einem Eintrag gehörten."""
    for stored in stored_filenames:
        path = ACCEPTANCE_FILE_ROOT / stored
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            path.unlink()
        except OSError:
            pass


def read_acceptance_file(row: OrderAcceptanceFile) -> bytes:
    """Die gespeicherten Bytes -- nur, wenn sie zur Prüfsumme passen, sonst AcceptanceFileError."""
    try:
        content = _path_for(row.stored_filename).read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        raise AcceptanceFileError("fehlt")
    if hashlib.sha256(content).hexdigest() != row.sha256:
        raise AcceptanceFileError("abweichend")
    return content


def _verify_file(row: OrderAcceptanceFile) -> str:
    try:
        read_acceptance_file(row)
        return "unveraendert"
    except AcceptanceFileError as e:
        return e.status


def _checked_upload(filename: str | None, data: bytes) -> tuple[bytes, str]:
    from .email_dispatch import receipt_content_type

    label = f"„{filename}“" if filename else "Der Beleg"
    if not data:
        raise ValueError(f"{label} ist leer.")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{label} ist größer als {MAX_FILE_BYTES // 1_000_000} MB.")
    try:
        content_type = receipt_content_type(data)
    except ValueError as exc:
        raise ValueError(f"{label}: Der Beleg muss ein Foto (JPEG, PNG, WebP) oder ein PDF sein.") from exc
    return data, content_type


def _frozen_power_of_attorney(participant: ProjectParticipant) -> tuple[bytes, str] | None:
    """Die hinterlegte Vollmacht des Beteiligten -- nur mit gesetzter Empfangsvollmacht, vorhandener Datei und
    stimmender Prüfsumme, sonst None (dann warnt die Abnahme)."""
    from .project_participants import power_of_attorney_path

    if not participant.authorized_recipient or not participant.poa_stored_filename \
            or participant.poa_content_type not in _SUFFIXES:
        return None
    try:
        data = power_of_attorney_path(participant.poa_stored_filename).read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return None
    if hashlib.sha256(data).hexdigest() != participant.poa_sha256:
        return None
    return data, participant.poa_content_type


# ---------------------------------------------------------------------------
# Inhalt und Prüfsumme
# ---------------------------------------------------------------------------

def acceptance_content(a: OrderAcceptance) -> dict:
    """Der gebundene Inhalt (kanonisches JSON für content_sha256): alles außer den Verwerfen-Feldern."""
    return {
        "order_id": a.order_id, "property_id": a.property_id, "kind": a.kind, "accepted_on": a.accepted_on.isoformat(),
        "scope": a.scope, "scope_description": a.scope_description,
        "roof_areas": sorted(({"id": r.roof_area_id, "name": r.roof_area_name} for r in a.roof_areas),
                             key=lambda r: r["id"]),
        "result": a.result, "reservation_defects": a.reservation_defects, "reservation_penalty": a.reservation_penalty,
        "contractor_objections": a.contractor_objections,
        "declared_by": a.declared_by, "participant_id": a.participant_id, "declared_by_name": a.declared_by_name,
        "declared_by_role": a.declared_by_role, "poa_on_record": a.poa_on_record, "conduct_reason": a.conduct_reason,
        "files": sorted(({"kind": f.kind, "content_type": f.content_type, "size_bytes": f.size_bytes, "sha256": f.sha256}
                         for f in a.files), key=lambda f: (f["kind"], f["sha256"], f["size_bytes"])),
        "created_at": a.created_at.replace(microsecond=0).isoformat(), "created_by_name": a.created_by_name,
    }


def content_sha256(content: dict) -> str:
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def verify_acceptance(a: OrderAcceptance) -> dict:
    """Inhalt und Belege nachgerechnet: {"content_ok", "files": {id: status}, "ok"}."""
    content_ok = content_sha256(acceptance_content(a)) == a.content_sha256
    files = {f.id: _verify_file(f) for f in a.files}
    return {"content_ok": content_ok, "files": files,
            "ok": content_ok and all(s == "unveraendert" for s in files.values())}


# ---------------------------------------------------------------------------
# Erfassen
# ---------------------------------------------------------------------------

def _clean(value: str | None, limit: int, label: str) -> str | None:
    value = (value or "").strip()
    if len(value) > limit:
        raise ValueError(f"{label} darf höchstens {limit} Zeichen lang sein.")
    return value or None


def acceptance_options(db: Session, order: Order) -> dict:
    """Auswahl für das Erfassen: Objekt des Projekts mit seinen (nicht archivierten) Dachflächen, Beteiligte mit
    Rolle und Vollmacht-Stand, Auftraggeber laut Auftrag."""
    from .project_participants import participant_info

    project = db.get(Project, order.project_id)
    prop = db.get(Property, project.property_id) if project and project.property_id else None
    roof_areas = db.scalars(
        select(RoofArea).where(RoofArea.property_id == prop.id, RoofArea.archived.is_(False)).order_by(RoofArea.name)
    ).all() if prop else []
    participants = db.scalars(
        select(ProjectParticipant).options(selectinload(ProjectParticipant.contact))
        .where(ProjectParticipant.project_id == order.project_id).order_by(ProjectParticipant.id)
    ).all()
    return {
        "client_name": order.customer_name,
        "property": {"id": prop.id, "name": prop.name} if prop else None,
        "roof_areas": [{"id": r.id, "name": r.name} for r in roof_areas],
        "participants": [
            {**participant_info(p), "poa_on_record": _frozen_power_of_attorney(p) is not None} for p in participants
        ],
        "kinds": KINDS, "scopes": SCOPES, "results": RESULTS, "declarers": DECLARERS,
        "max_files": MAX_FILES, "max_file_mb": MAX_FILE_BYTES // 1_000_000, "max_total_mb": MAX_TOTAL_BYTES // 1_000_000,
    }


def create_acceptance(
    db: Session, order: Order, data: dict, files: list[tuple[str | None, bytes]], *,
    user_id: int | None, user_name: str | None,
) -> OrderAcceptance:
    """Eine Abnahme erfassen. `data`: die Felder aus OrderAcceptanceCreate (app/schemas.py), `files`: (Dateiname,
    Inhalt) der Nachweise. ValueError bei ungültiger Eingabe (Router 400), nichts gespeichert."""
    kind, scope, result, declared_by = data["kind"], data["scope"], data["result"], data["declared_by"]
    if kind not in KINDS or scope not in SCOPES or result not in RESULTS or declared_by not in DECLARERS:
        raise ValueError("Unbekannte Art, Umfang, Ergebnis oder Erklärende.")
    accepted_on = data["accepted_on"]
    if accepted_on is None:
        raise ValueError("Bitte das Datum der Abnahme angeben.")
    if accepted_on > berlin_today():
        raise ValueError("Das Datum der Abnahme darf nicht in der Zukunft liegen.")

    scope_description = _clean(data.get("scope_description"), SCOPE_TEXT_MAX, "Die Beschreibung des Umfangs")
    if scope == "teil" and scope_description is None:
        raise ValueError("Bei einer Teilabnahme bitte beschreiben, welcher Teil abgenommen wurde.")
    if scope == "gesamt" and scope_description is not None:
        raise ValueError("Eine Beschreibung des Umfangs gehört nur zur Teilabnahme.")

    defects, penalty = data.get("reservation_defects"), data.get("reservation_penalty")
    if result == "abgenommen":
        if defects is None:
            raise ValueError("Bitte beantworten: Wurde der Vorbehalt wegen bekannter Mängel erklärt?")
        if penalty is None:
            raise ValueError("Bitte beantworten: Wurde der Vorbehalt der Vertragsstrafe erklärt?")
    elif defects is not None or penalty is not None:
        raise ValueError("Bei einer verweigerten Abnahme gibt es keine Vorbehalte.")

    objections = _clean(data.get("contractor_objections"), TEXT_MAX, "Die Einwendungen")
    conduct_reason = _clean(data.get("conduct_reason"), TEXT_MAX, "Die Begründung")
    if kind == "schluessig" and conduct_reason is None:
        raise ValueError("Bei einer schlüssigen Abnahme bitte begründen, woraus sie sich ergibt (z. B. Ingebrauchnahme, "
                         "vorbehaltlose Zahlung).")
    if kind != "schluessig" and conduct_reason is not None:
        raise ValueError("Eine Begründung gehört nur zur schlüssigen Abnahme – sonst ist der Beleg der Nachweis.")

    if len(files) > MAX_FILES:
        raise ValueError(f"Höchstens {MAX_FILES} Belege je Abnahme.")
    if kind != "schluessig" and not files:
        raise ValueError(f"Bitte den Nachweis der {KINDS[kind]}en Abnahme als Beleg hochladen (PDF oder Foto).")
    uploads = [_checked_upload(name, content) for name, content in files]
    if sum(len(c) for c, _ in uploads) > MAX_TOTAL_BYTES:
        raise ValueError(f"Die Belege sind zusammen größer als {MAX_TOTAL_BYTES // 1_000_000} MB.")
    if len({hashlib.sha256(c).hexdigest() for c, _ in uploads}) != len(uploads):
        raise ValueError("Derselbe Beleg ist mehrfach ausgewählt.")

    lock_order(db, order.id)
    project = db.get(Project, order.project_id)
    property_id = project.property_id if project else None

    roof_area_ids = list(dict.fromkeys(data.get("roof_area_ids") or []))
    roof_areas = []
    for roof_area_id in roof_area_ids:
        area = db.get(RoofArea, roof_area_id)
        if area is None or property_id is None or area.property_id != property_id:
            raise ValueError("Eine gewählte Dachfläche gehört nicht zum Objekt des Projekts.")
        if area.archived:
            raise ValueError(f"Die Dachfläche „{area.name}“ ist archiviert.")
        roof_areas.append(area)

    participant, frozen_poa, role_text = None, None, None
    participant_id = data.get("participant_id")
    if declared_by == "beteiligter":
        from .contacts import contact_display_name
        from .project_participants import role_label

        participant = db.get(ProjectParticipant, participant_id) if participant_id is not None else None
        if participant is None or participant.project_id != order.project_id:
            raise ValueError("Bitte einen Beteiligten dieses Projekts wählen.")
        if participant.contact.archived:
            raise ValueError("Der gewählte Beteiligte ist im Adressbuch archiviert.")
        declared_name = contact_display_name(participant.contact) or f"Kontakt #{participant.contact_id}"
        role_text = role_label(participant.role)
        frozen_poa = _frozen_power_of_attorney(participant)
    else:
        if participant_id is not None:
            raise ValueError("Ein Beteiligter gehört nur zu „erklärt durch einen Beteiligten“.")
        declared_name = order.customer_name

    written: list[str] = []
    try:
        acceptance = OrderAcceptance(
            order_id=order.id, property_id=property_id, kind=kind, accepted_on=accepted_on, scope=scope,
            scope_description=scope_description, result=result, reservation_defects=defects,
            reservation_penalty=penalty, contractor_objections=objections, declared_by=declared_by,
            participant_id=participant.id if participant else None, declared_by_name=declared_name[:255],
            declared_by_role=role_text, poa_on_record=(frozen_poa is not None) if participant else None,
            conduct_reason=conduct_reason, content_sha256="",
            created_at=datetime.utcnow().replace(microsecond=0), created_by_user_id=user_id,
            created_by_name=(user_name or "System")[:160],
        )
        for area in roof_areas:
            acceptance.roof_areas.append(OrderAcceptanceRoofArea(roof_area_id=area.id, roof_area_name=area.name[:255]))
        stored_files = [("nachweis", content, content_type) for content, content_type in uploads]
        if frozen_poa is not None:
            stored_files.append(("vollmacht", *frozen_poa))
        for file_kind, content, content_type in stored_files:
            stored = _write_file(content, content_type)
            written.append(stored)
            acceptance.files.append(OrderAcceptanceFile(
                kind=file_kind, stored_filename=stored, content_type=content_type, size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(), created_at=acceptance.created_at,
            ))
        acceptance.content_sha256 = content_sha256(acceptance_content(acceptance))
        db.add(acceptance)
        db.commit()
    except Exception:
        db.rollback()
        _remove_written(written)
        raise
    db.refresh(acceptance)
    return acceptance


# ---------------------------------------------------------------------------
# Verwerfen
# ---------------------------------------------------------------------------

def discard_acceptance(
    db: Session, acceptance: OrderAcceptance, *, reason: str, user_id: int | None, user_name: str | None,
) -> OrderAcceptance:
    """Verwirft eine Abnahme mit Begründung -- genau einmal (bedingtes UPDATE an der ORM-Sperre vorbei, wie das
    Nachholen der Abschrift in app/contract_signatures.py), mit Eintrag in der Änderungshistorie."""
    from .audit import record_audit_entry

    text = _clean(reason, REASON_MAX, "Die Begründung")
    if text is None:
        raise ValueError("Bitte begründen, warum die Abnahme verworfen wird.")
    lock_order(db, acceptance.order_id)
    now = datetime.utcnow().replace(microsecond=0)
    name = (user_name or "System")[:160]
    done = db.execute(
        update(OrderAcceptance)
        .where(OrderAcceptance.id == acceptance.id, OrderAcceptance.discarded_at.is_(None))
        .values(discarded_at=now, discarded_by_user_id=user_id, discarded_by_name=name, discard_reason=text)
        .execution_options(synchronize_session=False)
    ).rowcount
    if done != 1:
        db.rollback()
        raise AcceptanceConflict("Diese Abnahme ist bereits verworfen.")
    order = db.get(Order, acceptance.order_id)
    record_audit_entry(
        db, action="verworfen", entity_type=ENTITY_TYPE, entity_id=acceptance.id,
        entity_label=_label(acceptance, order), project_id=order.project_id if order else None,
        field_name="discard_reason", old_value=None, new_value=text, actor_user_id=user_id, actor_name=name,
    )
    db.commit()
    db.expire(acceptance)
    db.refresh(acceptance)
    return acceptance


# ---------------------------------------------------------------------------
# Anzeige
# ---------------------------------------------------------------------------

def _label(a: OrderAcceptance, order: Order | None) -> str:
    number = order.order_number if order else f"Auftrag #{a.order_id}"
    return f"{number} · {SCOPES.get(a.scope, a.scope)} {a.accepted_on:%d.%m.%Y}"[:255]


def result_text(a: OrderAcceptance) -> str:
    """"verweigert", "abgenommen ohne Vorbehalte", "abgenommen mit Vorbehalten (Mängel, Vertragsstrafe)" -- abgeleitet."""
    if a.result != "abgenommen":
        return RESULTS.get(a.result, a.result)
    reserved = [label for flag, label in ((a.reservation_defects, "Mängel"), (a.reservation_penalty, "Vertragsstrafe"))
                if flag]
    return f"abgenommen mit Vorbehalten ({', '.join(reserved)})" if reserved else "abgenommen ohne Vorbehalte"


def acceptance_warranty(a: OrderAcceptance, order: Order) -> dict | None:
    """Gewährleistungsende dieser Abnahme -- nur für eine nicht verworfene, abgenommene; ohne festgelegte Dauer
    {"end": None} mit Hinweis."""
    if a.discarded_at is not None or a.result != "abgenommen":
        return None
    if order.warranty_months is None or order.warranty_days is None:
        return {"end": None, "text": "Gewährleistungsende nicht berechenbar – Dauer am Auftrag nicht festgelegt"}
    end = warranty_end(a.accepted_on, order.warranty_months, order.warranty_days)
    return {"end": end, "duration_text": duration_text(order.warranty_months, order.warranty_days),
            "text": f"Gewährleistung bis {end:%d.%m.%Y} ({duration_text(order.warranty_months, order.warranty_days)} "
                    f"ab Abnahme)", "rule": END_RULE_TEXT}


def acceptance_to_dict(a: OrderAcceptance, order: Order) -> dict:
    check = verify_acceptance(a)
    without_poa = a.declared_by == "beteiligter" and not a.poa_on_record
    return {
        "id": a.id, "order_id": a.order_id, "order_number": order.order_number, "project_id": order.project_id,
        "property_id": a.property_id,
        "kind": a.kind, "kind_label": KINDS.get(a.kind, a.kind),
        "accepted_on": a.accepted_on,
        "scope": a.scope, "scope_label": SCOPES.get(a.scope, a.scope), "scope_description": a.scope_description,
        "roof_areas": [{"id": r.roof_area_id, "name": r.roof_area_name} for r in a.roof_areas],
        "result": a.result, "result_text": result_text(a),
        "reservation_defects": a.reservation_defects, "reservation_penalty": a.reservation_penalty,
        "contractor_objections": a.contractor_objections,
        "declared_by": a.declared_by, "declared_by_label": DECLARERS.get(a.declared_by, a.declared_by),
        "participant_id": a.participant_id, "declared_by_name": a.declared_by_name,
        "declared_by_role": a.declared_by_role, "poa_on_record": a.poa_on_record,
        "without_power_of_attorney": without_poa,
        "conduct_reason": a.conduct_reason,
        "files": [{
            "id": f.id, "kind": f.kind, "kind_label": FILE_KINDS.get(f.kind, f.kind), "content_type": f.content_type,
            "size_bytes": f.size_bytes, "sha256": f.sha256, "status": check["files"][f.id],
            "status_text": VERIFY_TEXTS[check["files"][f.id]],
        } for f in a.files],
        "content_sha256": a.content_sha256, "content_ok": check["content_ok"], "intact": check["ok"],
        "created_at": a.created_at, "created_at_local": to_berlin(a.created_at), "created_by_name": a.created_by_name,
        "discarded": a.discarded_at is not None, "discarded_at": a.discarded_at,
        "discarded_at_local": to_berlin(a.discarded_at), "discarded_by_name": a.discarded_by_name,
        "discard_reason": a.discard_reason,
        "warranty": acceptance_warranty(a, order),
    }


def _load(db: Session, query) -> list[OrderAcceptance]:
    return db.scalars(
        query.options(selectinload(OrderAcceptance.roof_areas), selectinload(OrderAcceptance.files))
    ).all()


def list_acceptances(db: Session, order: Order) -> list[dict]:
    """Alle Einträge des Auftrags, neueste zuerst, verworfene eingeschlossen (Historie)."""
    rows = _load(db, select(OrderAcceptance).where(OrderAcceptance.order_id == order.id)
                 .order_by(OrderAcceptance.accepted_on.desc(), OrderAcceptance.id.desc()))
    return [acceptance_to_dict(a, order) for a in rows]


def _warranty_rows(db: Session, rows: list[OrderAcceptance]) -> list[dict]:
    orders = {o.id: o for o in db.scalars(select(Order).where(Order.id.in_({a.order_id for a in rows}))).all()} \
        if rows else {}
    result = []
    for a in rows:
        order = orders[a.order_id]
        item = acceptance_to_dict(a, order)
        item["order_title"] = order.title
        result.append(item)
    return result


def property_acceptance_warranties(db: Session, property_id: int) -> dict:
    """Für die Objektseite: jede nicht verworfene, abgenommene Abnahme an diesem Objekt (Objekt beim Erfassen) mit
    ihrem Gewährleistungsende, dazu je Dachfläche das späteste Ende der Abnahmen, die sie nennen."""
    rows = _load(db, select(OrderAcceptance).where(
        OrderAcceptance.property_id == property_id, OrderAcceptance.discarded_at.is_(None),
        OrderAcceptance.result == "abgenommen",
    ).order_by(OrderAcceptance.accepted_on.desc(), OrderAcceptance.id.desc()))
    items = _warranty_rows(db, rows)
    latest: dict[int, dict] = {}
    for item in items:
        end = (item["warranty"] or {}).get("end")
        for area in item["roof_areas"]:
            current = latest.get(area["id"])
            if current is None or (end is not None and (current["end"] is None or end > current["end"])):
                latest[area["id"]] = {"end": end, "order_number": item["order_number"]}
    return {"acceptances": items, "roof_areas": {str(k): v for k, v in latest.items()}}


def roof_area_acceptance_warranties(db: Session, roof_area: RoofArea) -> dict:
    """Für die Dachflächenseite: die nicht verworfenen, abgenommenen Abnahmen, die diese Dachfläche nennen; dazu, wie
    viele am Objekt ohne Angabe von Dachflächen erfasst sind (die gelten womöglich auch hier -- das sagt die Seite)."""
    rows = _load(db, select(OrderAcceptance).join(OrderAcceptanceRoofArea).where(
        OrderAcceptanceRoofArea.roof_area_id == roof_area.id, OrderAcceptance.discarded_at.is_(None),
        OrderAcceptance.result == "abgenommen",
    ).order_by(OrderAcceptance.accepted_on.desc(), OrderAcceptance.id.desc()))
    without_areas = [a for a in _load(db, select(OrderAcceptance).where(
        OrderAcceptance.property_id == roof_area.property_id, OrderAcceptance.discarded_at.is_(None),
        OrderAcceptance.result == "abgenommen",
    )) if not a.roof_areas]
    return {"acceptances": _warranty_rows(db, rows), "property_without_roof_areas": len(without_areas)}


def acceptances_naming_roof_area(db: Session, roof_area_id: int) -> int:
    return len(db.scalars(
        select(OrderAcceptanceRoofArea.id).where(OrderAcceptanceRoofArea.roof_area_id == roof_area_id)
    ).all())


def acceptances_declared_by(db: Session, participant_id: int) -> int:
    return len(db.scalars(select(OrderAcceptance.id).where(OrderAcceptance.participant_id == participant_id)).all())
