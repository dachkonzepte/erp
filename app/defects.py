"""Mängel (seit 1.8.49, Stufe 2c-2a, docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.49").

Ein Mangel (Defect, bewusst nicht der Befund am Einsatzbericht, Finding) hat eine Quelle -- vorerst nur "abnahme":
eine nicht verworfene Abnahme mit "Vorbehalt Mängel: ja" oder "verweigert" (später kommt die Rüge dazu). Er hält
fest: Beschreibung (Pflicht), optional eine Dachfläche (nur aus dem Objekt der Abnahme, nicht archiviert, Name als
Schnappschuss), Ortsangabe, Beseitigungsfrist, Fotos und Belege. Nach dem Speichern unveränderlich wie die Abnahme:
ORM-Sperre (app/models.py), Dateien exklusiv angelegt und schreibgeschützt mit SHA-256 (Ablage der Abnahme, Ordner
"maengel"), content_sha256 mit der Fassung des Prüfsummenformats im Inhalt; Korrektur durch Verwerfen mit Begründung
(bedingtes UPDATE mit Siegel, Änderungshistorie).

Was danach geschieht, steht in Ereignissen (DefectEvent) -- jedes unveränderlich, versiegelt und an den Inhalt des
Mangels und das vorige Ereignis gebunden (Kette: ein entferntes oder vertauschtes Ereignis fällt auf, nur das letzte
nicht). Daraus ergibt sich der Stand (defect_state()):
- Haltung: offen (ohne Ereignis) -> anerkannt oder bestritten (Begründung Pflicht); wechselbar, nie zurück auf offen.
- Status: offen -> beseitigt (Datum) -> Beseitigung abgenommen (Datum, erklärt durch, Beleg oder Begründung);
  offen -> erledigt ohne Beseitigung (Begründung); beseitigt -> offen (Begründung, z. B. Beseitigung nicht gelungen).
  Beseitigung abgenommen und erledigt ohne Beseitigung sind endgültig.
- Freigabe zur Beseitigung: nur bewusst, unabhängig von der Haltung -- bei "bestritten" mit Begründung (Kulanz);
  Zurücknehmen mit Begründung; nach einem endgültigen Status nicht mehr.
- Fotos ergänzen, seit 1.8.51 auch Belege: nur hinzufügen.

Nur bei Vertragsgrundlage vob_b abgeleitet (nie gespeichert): "Nachbesserung regulär bis" = das spätere von "Gewährleistung
regulär bis" der Abnahme und Abnahme der Beseitigung plus 24 Monate (§ 13 Abs. 5 Nr. 1 Satz 3 VOB/B), mit Prüfstatus.

Beim Erfassen entsteht eine Aufgabe ohne Zuständigkeit (Büro), fällig zur Beseitigungsfrist, in derselben Transaktion;
Verweis in beide Richtungen (Defect.task_id, Task.source_url). Der Mangel ist die Wahrheit: seine Erledigung (Beseitigung
abgenommen, erledigt ohne Beseitigung, verworfen) erledigt die Aufgabe; eine erledigte Aufgabe ändert am Mangel nichts.
Seit 1.8.54 folgt die Aufgabe dem Status: "beseitigt" (Büro oder Monteur) erledigt "Mangel beseitigen" und legt
"Beseitigung abnehmen lassen" an, zurück auf "offen" erledigt diese und legt wieder "Mangel beseitigen" an -- im selben
Commit wie der Eintrag, die neue Aufgabe steht am Eintrag (DefectEvent.task_id). Die aktuelle Aufgabe ist die des letzten
Eintrags, der eine angelegt hat, sonst die beim Erfassen (current_task()).

Seit 1.8.55 trägt "zurück auf offen" optional eine neue Beseitigungsfrist (DefectEvent.due_on, nicht vor heute). Die aktuelle
Frist ist die des letzten Eintrags mit einer, sonst die beim Erfassen (current_due()) -- Aufgabe "Erneut beseitigen",
Büro-Seite, Überschreitung und /mobil nutzen sie.

Seit 1.8.60 (Stufe 2c-2d) die Quelle "protokoll": ein Mangel aus dem Feld "Mängel" eines Abnahmeprotokolls
(create_protocol_defect()) -- im Entwurf der Checkliste, solange keine gültige Unterschrift das Feld versiegelt, unter der
Zeilensperre der Checkliste (dieselbe wie beim Unterschreiben). Der gebundene Inhalt trägt checklist_id statt acceptance_id;
die Abnahme entsteht erst mit der Unterschrift des Auftraggebers und wird dann angehängt (seit 1.8.63
app/acceptance_protocol.py, samt Aufgabe). Bis dahin keine Aufgabe und keine Einträge im Verlauf (_lock()), Verwerfen geht. An
einer Abnahme aus dem Protokoll erfasst man keine Mängel (seit 1.8.63, DefectConflict) -- ihre Mängel stehen im Protokoll.

Rollenlos wie jede Geschäftslogik; app/routers/defects.py lässt nur das Büro zu (ab buero_auftrag). Seit 1.8.52 sieht der
Monteur in /mobil (app/routers/field_defects.py) die Mängel, die er beseitigen soll -- freigegeben, Status offen, nicht
verworfen, an einem Auftrag, den er öffnen darf (field_may_see_defect(), field_may_access_order()) -- mit einer
Positivliste von Feldern (field_defect_dict()) und meldet "beseitigt" mit mindestens einem Foto (report_remedied(),
idempotent über client_uuid), seit 1.8.54 optional mit einem kurzen Hinweis fürs Büro (Text des Eintrags, nie in /mobil).
"""

import hashlib
import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .acceptances import (  # noqa: F401  (AcceptanceFileError: der Router fängt sie beim Ausliefern einer Datei)
    DECLARERS, KINDS, PROTOCOL_DEFECTS_TEXT, REGULAR_HINT, SCOPES, AcceptanceFileError, _checked_upload, _clean,
    _frozen_power_of_attorney,
    _remove_written, _verify_file, _write_file, acceptance_allows_defects, acceptance_warranty, check_summary,
    content_sha256, discard_content, lock_order, read_acceptance_file, result_text, verify_acceptance,
)
from .berlin_time import berlin_today, to_berlin
from .models import (
    Defect, DefectEvent, DefectFile, Order, OrderAcceptance, Project, ProjectParticipant, Property, RoofArea, Task,
    TaskColumn,
)
from .warranty import warranty_end

logger = logging.getLogger(__name__)

SOURCES = {"abnahme": "Abnahme", "protokoll": "Abnahmeprotokoll"}  # später "ruege" (Rüge in der Gewährleistung)
STANCES = {"offen": "offen", "anerkannt": "anerkannt", "bestritten": "bestritten"}
STATUSES = {"offen": "offen", "beseitigt": "beseitigt", "beseitigung_abgenommen": "Beseitigung abgenommen",
            "erledigt_ohne": "erledigt ohne Beseitigung"}
RELEASES = {"freigegeben": "zur Beseitigung freigegeben", "zurueckgenommen": "Freigabe zurückgenommen"}
EVENT_KINDS = {"haltung": "Haltung", "status": "Status", "freigabe": "Freigabe zur Beseitigung",
               "fotos": "Fotos ergänzt", "belege": "Belege ergänzt"}
DONE_STATUSES = {"beseitigung_abgenommen", "erledigt_ohne"}
# Status -> mögliche nächste Status. Die beiden erledigten Status haben keinen Nachfolger.
STATUS_STEPS = {"offen": ("beseitigt", "erledigt_ohne"), "beseitigt": ("beseitigung_abgenommen", "offen")}
FILE_KINDS = {"foto": "Foto", "beleg": "Beleg",
              "abnahmevollmacht": "Vollmacht zur Abnahme (beim Erfassen hinterlegt)"}
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Fassung des Prüfsummenformats -- steht von Anfang an im gebundenen Inhalt (Muster der Abnahme ab 1.8.48).
CHECKSUM_FORMAT = 1
REMEDY_MONTHS = 24
REMEDY_RULE = ("§ 13 Abs. 5 Nr. 1 Satz 3 VOB/B: für die Mängelbeseitigung beginnen 2 Jahre neu ab ihrer Abnahme, "
               "aber nicht vor Ende der regulären Gewährleistung")

MAX_FILES = 10
MAX_FILE_BYTES = 15_000_000
MAX_TOTAL_BYTES = 30_000_000  # je Speichern -- Speicherbudget des Servers
DESCRIPTION_MAX = 5000
LOCATION_MAX = 500
REASON_MAX = 2000
FILE_SUBDIR = "maengel"

TASK_MODULE = "aufgabenmanagement"
TASK_ROLE = "buero_auftrag"
TASK_SOURCE = "maengel"
TASK_SHORT_TEXT = 60  # Zeichen der Beschreibung im Aufgabentitel (seit 1.8.51)
# Art der Aufgabe zum Mangel (seit 1.8.54) und welcher Status welche anlegt -- die bisherige wird dabei erledigt.
TASK_KINDS = {"beseitigen": "Mangel beseitigen", "abnahme": "Beseitigung abnehmen lassen"}
STATUS_TASKS = {"beseitigt": "abnahme", "offen": "beseitigen"}
ENTITY_TYPE = "Mangel"  # Änderungshistorie (app/audit.py)

DISCARD_TEXTS = {"unveraendert": "Verwerfen unverändert (Prüfsumme stimmt)",
                 "abweichend": "Verwerfen weicht von seiner Prüfsumme ab"}


class DefectConflict(ValueError):
    """Der Stand hat sich geändert (verworfen, anderer Status, Abnahme verworfen) -- Router: 409."""


PROTOCOL_PENDING_TEXT = ("Der Mangel steht in einem Abnahmeprotokoll, aus dem noch keine Abnahme angelegt ist – Haltung, "
                         "Freigabe, Status und Nachträge erst danach.")


def protocol_pending(d: Defect) -> bool:
    """Mangel aus einem Abnahmeprotokoll, an dem noch keine Abnahme hängt (seit 1.8.60)."""
    return d.source == "protokoll" and d.acceptance_id is None


# ---------------------------------------------------------------------------
# Quelle
# ---------------------------------------------------------------------------

def _not_allowed_text(a: OrderAcceptance) -> str | None:
    if a.discarded_at is not None:
        return "Die Abnahme ist verworfen – Mängel nur an einer gültigen Abnahme erfassen."
    if a.checklist_attachment_id is not None:  # seit 1.8.63: die Mängel stehen im Abnahmeprotokoll
        return PROTOCOL_DEFECTS_TEXT
    if not acceptance_allows_defects(a):
        return ("Mängel nur an einer Abnahme mit „Vorbehalt Mängel: ja“ oder an einer verweigerten Abnahme – diese "
                "wurde ohne Vorbehalt wegen Mängeln abgenommen.")
    return None


# ---------------------------------------------------------------------------
# Dateien
# ---------------------------------------------------------------------------

def _checked_files(files: list[tuple[str, str | None, bytes]], kinds: set[str]) -> list[tuple[str, bytes, str]]:
    """(Art, Dateiname, Inhalt) -> (Art, Inhalt, Dateiart); PDF oder Foto am Inhalt erkannt, ein Foto nur als Bild."""
    if len(files) > MAX_FILES:
        raise ValueError(f"Höchstens {MAX_FILES} Dateien je Speichern.")
    checked = []
    for kind, name, data in files:
        if kind not in kinds:
            raise ValueError(f"Unbekannte Dateiart: {kind!r}.")
        content, content_type = _checked_upload(name, data)
        if len(content) > MAX_FILE_BYTES:
            raise ValueError(f"„{name}“ ist größer als {MAX_FILE_BYTES // 1_000_000} MB.")
        if kind == "foto" and content_type not in PHOTO_TYPES:
            raise ValueError(f"„{name}“: Ein Foto muss JPEG, PNG oder WebP sein – ein PDF bitte als Beleg.")
        checked.append((kind, content, content_type))
    if sum(len(c) for _, c, _ in checked) > MAX_TOTAL_BYTES:
        raise ValueError(f"Die Dateien sind zusammen größer als {MAX_TOTAL_BYTES // 1_000_000} MB.")
    if len({hashlib.sha256(c).hexdigest() for _, c, _ in checked}) != len(checked):
        raise ValueError("Dieselbe Datei ist mehrfach ausgewählt.")
    return checked


def _store(written: list[str], defect_id: int | None, kind: str, content: bytes, content_type: str,
           created_at: datetime) -> DefectFile:
    stored = _write_file(content, content_type, subdir=FILE_SUBDIR)
    written.append(stored)
    return DefectFile(defect_id=defect_id, kind=kind, stored_filename=stored, content_type=content_type,
                      size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), created_at=created_at)


def read_defect_file(row: DefectFile) -> bytes:
    """Die gespeicherten Bytes -- nur mit stimmender Prüfsumme (sonst AcceptanceFileError, wie bei der Abnahme)."""
    return read_acceptance_file(row)


# ---------------------------------------------------------------------------
# Inhalt, Prüfsumme, Stand
# ---------------------------------------------------------------------------

def _file_entries(files) -> list[dict]:
    return sorted(({"kind": f.kind, "content_type": f.content_type, "size_bytes": f.size_bytes, "sha256": f.sha256}
                   for f in files), key=lambda f: (f["kind"], f["sha256"], f["size_bytes"]))


def defect_content(d: Defect) -> dict:
    """Der gebundene Inhalt des Mangels: alles außer Verwerfen und Aufgabe, die Dateien beim Erfassen (event_id leer),
    "Erfasst von" als Kopie, die Fassung des Prüfsummenformats. Seit 1.8.60 bei der Quelle "protokoll" die Checkliste statt
    der Abnahme -- die kommt erst später dazu und wird angehängt, ohne den Inhalt zu ändern."""
    if d.source == "protokoll":
        content = _base_content(d)
        content.pop("acceptance_id")
        content["checklist_id"] = d.checklist_id
        return content
    return _base_content(d)


def _base_content(d: Defect) -> dict:
    return {
        "checksum_format": d.checksum_format, "order_id": d.order_id, "property_id": d.property_id,
        "source": d.source, "acceptance_id": d.acceptance_id, "description": d.description,
        "roof_area_id": d.roof_area_id, "roof_area_name": d.roof_area_name, "location": d.location,
        "remedy_due_on": d.remedy_due_on.isoformat() if d.remedy_due_on else None,
        "files": _file_entries(f for f in d.files if f.event_id is None),
        "created_at": d.created_at.replace(microsecond=0).isoformat(), "created_by_name": d.created_by_name,
    }


def event_content(e: DefectEvent, defect_hash: str) -> dict:
    """Der gebundene Inhalt eines Ereignisses -- samt Prüfsumme des Mangels und des vorigen Ereignisses (Kette). Die neue
    Frist (seit 1.8.55) nur, wenn gesetzt: so bleiben die Prüfsummen aller früheren Einträge gültig, und ein am ORM vorbei
    gesetztes oder entferntes Datum ändert den Inhalt trotzdem."""
    content = {
        "checksum_format": e.checksum_format, "defect_id": e.defect_id, "defect_content_sha256": defect_hash,
        "previous_event_sha256": e.previous_event_sha256, "kind": e.kind, "value": e.value,
        "previous_value": e.previous_value, "event_date": e.event_date.isoformat() if e.event_date else None,
        "reason": e.reason, "declared_by": e.declared_by, "participant_id": e.participant_id,
        "declared_by_name": e.declared_by_name, "declared_by_role": e.declared_by_role,
        "poa_on_record": e.poa_on_record, "files": _file_entries(e.files),
        "created_at": e.created_at.replace(microsecond=0).isoformat(), "created_by_name": e.created_by_name,
    }
    if e.due_on is not None:
        content["due_on"] = e.due_on.isoformat()
    return content


def _verify_discard(d: Defect) -> str | None:
    if d.discarded_at is None:
        return "abweichend" if d.discard_sha256 or d.discarded_by_name or d.discard_reason else None
    if not d.discard_sha256 or not d.discarded_by_name or not d.discard_reason:
        return "abweichend"
    expected = content_sha256(discard_content(d.content_sha256, d.discarded_at, d.discarded_by_name, d.discard_reason))
    return "unveraendert" if expected == d.discard_sha256 else "abweichend"


def verify_defect(d: Defect) -> dict:
    """Inhalt, alle Dateien, jedes Ereignis samt Kette und das Verwerfen nachgerechnet. Eine Abweichung meldet
    zusätzlich logger.error -- nur Kennungen, kein Inhalt (Regel 18)."""
    content_ok = content_sha256(defect_content(d)) == d.content_sha256
    files = {f.id: _verify_file(f) for f in d.files}
    events, previous = {}, None
    for e in sorted(d.events, key=lambda x: x.id):
        events[e.id] = (content_sha256(event_content(e, d.content_sha256)) == e.content_sha256
                        and e.previous_event_sha256 == previous)
        previous = e.content_sha256
    discard = _verify_discard(d)
    problems = []
    if not content_ok:
        problems.append("Inhalt weicht von seiner Prüfsumme ab")
    bad_files = sorted(fid for fid, status in files.items() if status != "unveraendert")
    for text in dict.fromkeys("Datei fehlt" if files[fid] == "fehlt" else "Datei weicht von ihrer Prüfsumme ab"
                              for fid in bad_files):
        problems.append(text)
    bad_events = sorted(eid for eid, ok in events.items() if not ok)
    if bad_events:
        problems.append("Verlauf weicht von seiner Prüfsumme ab")
    if discard == "abweichend":
        problems.append(DISCARD_TEXTS["abweichend"])
    ok = not problems
    if not ok:
        logger.error("Mangel %s (Auftrag %s): Prüfung weicht ab -- Inhalt %s, Dateien %s, Ereignisse %s, Verwerfen %s",
                     d.id, d.order_id, "ok" if content_ok else "abweichend",
                     ",".join(f"{fid}:{files[fid]}" for fid in bad_files) or "ok",
                     ",".join(str(eid) for eid in bad_events) or "ok", discard or "-")
    return {"content_ok": content_ok, "files": files, "events": events, "discard": discard, "ok": ok,
            "text": "Prüfsumme stimmt" if ok else "; ".join(problems)}


def defect_state(events: list[DefectEvent]) -> dict:
    """Stand aus den Ereignissen in ihrer Reihenfolge: Haltung, Status (mit Datum), Freigabe."""
    stance, status, released = "offen", "offen", False
    stance_event = status_event = release_event = None
    for e in sorted(events, key=lambda x: x.id):
        if e.kind == "haltung":
            stance, stance_event = e.value, e
        elif e.kind == "status":
            status, status_event = e.value, e
        elif e.kind == "freigabe":
            released, release_event = e.value == "freigegeben", e
    return {"stance": stance, "status": status, "released": released, "done": status in DONE_STATUSES,
            "status_date": status_event.event_date if status_event is not None else None,
            "stance_event": stance_event, "status_event": status_event, "release_event": release_event}


# ---------------------------------------------------------------------------
# Erfassen
# ---------------------------------------------------------------------------

def defect_options(db: Session, acceptance: OrderAcceptance) -> dict:
    """Auswahl zum Erfassen und für "Beseitigung abgenommen": Dachflächen aus dem Objekt DER ABNAHME (nicht dem
    heutigen des Projekts), Beteiligte des Projekts mit Stand der Vollmacht zur Abnahme, Auftraggeber laut Auftrag."""
    from .project_participants import participant_info

    order = db.get(Order, acceptance.order_id)
    prop = db.get(Property, acceptance.property_id) if acceptance.property_id else None
    roof_areas = db.scalars(
        select(RoofArea).where(RoofArea.property_id == prop.id, RoofArea.archived.is_(False)).order_by(RoofArea.name)
    ).all() if prop else []
    participants = db.scalars(
        select(ProjectParticipant).options(selectinload(ProjectParticipant.contact))
        .where(ProjectParticipant.project_id == order.project_id).order_by(ProjectParticipant.id)
    ).all()
    return {
        "allowed": _not_allowed_text(acceptance) is None, "not_allowed_text": _not_allowed_text(acceptance),
        "acceptance": {"id": acceptance.id, "accepted_on": acceptance.accepted_on,
                       "scope_label": SCOPES.get(acceptance.scope, acceptance.scope),
                       "kind_label": KINDS.get(acceptance.kind, acceptance.kind), "result_text": result_text(acceptance)},
        "client_name": order.customer_name,
        "property": {"id": prop.id, "name": prop.name} if prop else None,
        "roof_areas": [{"id": r.id, "name": r.name} for r in roof_areas],
        "participants": [{**participant_info(p), "poa_on_record": _frozen_power_of_attorney(p) is not None}
                         for p in participants],
        "max_files": MAX_FILES, "max_file_mb": MAX_FILE_BYTES // 1_000_000, "max_total_mb": MAX_TOTAL_BYTES // 1_000_000,
    }


def short_text(text: str, limit: int = TASK_SHORT_TEXT) -> str:
    """Kurzfassung eines Freitexts: Leerraum zusammengezogen, höchstens `limit` Zeichen, an einer Wortgrenze mit "…"
    gekürzt (ein einzelnes überlanges Wort hart)."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    if " " in cut and text[limit - 1] != " ":
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.-–") + "…"


def _task_title(order: Order, place: str | None, description: str) -> str:
    where = f" – {place}" if place else ""
    return f"Mangel aus Abnahme {order.order_number}{where}: {short_text(description)}"


def _add_task(db: Session, order: Order, *, title: str, description: str, due, user_id: int | None,
              source_url: str | None = None) -> Task | None:
    """Eine Aufgabe zum Mangel -- in der Transaktion des Aufrufers, ohne Zuständigkeit, nur fürs Büro. Ohne
    Aufgabenmodul keine (der Mangel zeigt das, nachgeholt wird nicht)."""
    from .modules import is_module_enabled
    from .tasks import _default_column_key

    if not is_module_enabled(db, TASK_MODULE):
        return None
    task = Task(title=title[:255], description=description, status=_default_column_key(db), priority="normal",
                due_date=due, assigned_employee_id=None, project_id=order.project_id, created_by_user_id=user_id,
                source_module=TASK_SOURCE, source_label=f"Mangel – {order.order_number}"[:255], source_url=source_url,
                min_visible_role=TASK_ROLE)
    db.add(task)
    db.flush()
    return task


def _new_task(db: Session, order: Order, acceptance: OrderAcceptance, *, place: str | None, description: str, due,
              user_id: int | None, user_name: str) -> Task | None:
    """Die Aufgabe beim Erfassen ("Mangel beseitigen"). Seit 1.8.51 trägt der Titel eine Kurzfassung der Beschreibung
    (Betreibervorgabe 2c-2b); die Beschreibung der Aufgabe bleibt bei Metadaten (wer, wann, welche Abnahme, Frist) --
    wie bei den Aufgaben aus Anzeigen (app/obstruction_notices.py). Der Titel ist eine Kopie: maßgeblich bleibt der
    Mangel."""
    due_text = due.strftime("%d.%m.%Y") if due else "keine"
    text = (f"Mangel aus der {SCOPES.get(acceptance.scope, acceptance.scope)} vom "
            f"{acceptance.accepted_on:%d.%m.%Y} ({result_text(acceptance)}), erfasst von {user_name}. "
            f"Beseitigungsfrist: {due_text}. Haltung, Freigabe und Erledigung am Mangel auf der Auftragsseite "
            f"festhalten – ist der Mangel erledigt, erledigt sich diese Aufgabe von selbst (umgekehrt nicht).")
    return _add_task(db, order, title=_task_title(order, place, description), description=text, due=due,
                     user_id=user_id)


def _follow_task(db: Session, defect: Defect, kind: str, *, event_date, user_id: int | None, user_name: str,
                 via_field_view: bool, due=None) -> Task | None:
    """Die Aufgabe nach einem Statuswechsel (seit 1.8.54, Betreibervorgabe 2c-2b): "abnahme" nach "beseitigt" --
    "Beseitigung abnehmen lassen", ohne Fälligkeit; "beseitigen" nach "zurück auf offen" -- "Erneut beseitigen",
    fällig zur aktuellen Beseitigungsfrist (`due`, seit 1.8.55 die neue des Eintrags oder die bisher geltende). Titel wie
    beim Erfassen mit vorangestellter Art, Beschreibung nur Metadaten (nicht Mangeltext, Begründung oder Hinweis des
    Monteurs)."""
    order = db.get(Order, defect.order_id)
    base = _task_title(order, defect.roof_area_name or defect.location, defect.description)
    who = f"{'in der Monteursansicht von ' if via_field_view else 'von '}{user_name}"
    url = f"/orders/{order.id}#mangel-{defect.id}"
    if kind == "abnahme":
        text = (f"Mangel Nr. {defect.id} ist als beseitigt eingetragen (am {event_date:%d.%m.%Y}, {who}). Die "
                "Beseitigung vom Auftraggeber abnehmen lassen und am Mangel als „Beseitigung abgenommen“ festhalten – "
                "ist sie nicht gelungen, zurück auf „offen“. Ist der Mangel erledigt, erledigt sich diese Aufgabe von "
                "selbst (umgekehrt nicht).")
        return _add_task(db, order, title=f"Beseitigung abnehmen lassen – {base}", description=text, due=None,
                         user_id=user_id, source_url=url)
    text = (f"Mangel Nr. {defect.id} ist wieder offen (zurückgesetzt {who}) – die Beseitigung ist nicht gelungen oder "
            f"nicht abgenommen. Beseitigungsfrist: {due.strftime('%d.%m.%Y') if due else 'keine'}. Ist der Mangel "
            "erledigt, erledigt sich diese Aufgabe von selbst (umgekehrt nicht).")
    return _add_task(db, order, title=f"Erneut beseitigen – {base}", description=text, due=due, user_id=user_id,
                     source_url=url)


def current_due(defect: Defect, events):
    """Die aktuelle Beseitigungsfrist (seit 1.8.55): die des letzten Eintrags, der eine neue gesetzt hat ("zurück auf
    offen" mit Frist), sonst die beim Erfassen. None = keine Frist."""
    due = defect.remedy_due_on
    for e in sorted(events, key=lambda x: x.id):
        if e.due_on is not None:
            due = e.due_on
    return due


def current_task(defect: Defect, events) -> tuple[int | None, str]:
    """(ID, Art) der aktuellen Aufgabe des Mangels (seit 1.8.54): die des letzten Eintrags, der eine angelegt hat, sonst
    die beim Erfassen ("beseitigen")."""
    task_id, kind = defect.task_id, "beseitigen"
    for e in sorted(events, key=lambda x: x.id):
        if e.task_id is not None:
            task_id, kind = e.task_id, STATUS_TASKS.get(e.value, "beseitigen")
    return task_id, kind


def create_defect(db: Session, acceptance: OrderAcceptance, data: dict, files: list[tuple[str, str | None, bytes]], *,
                  user_id: int | None, user_name: str | None) -> Defect:
    """Einen Mangel an der Abnahme erfassen. `data`: description, roof_area_id, location, remedy_due_on;
    `files`: (Art "foto"/"beleg", Dateiname, Inhalt). ValueError bei ungültiger Eingabe (Router 400), DefectConflict,
    wenn die Abnahme keine Mängel (mehr) zulässt (Router 409 bzw. 400) -- nichts gespeichert."""
    description = _clean(data.get("description"), DESCRIPTION_MAX, "Die Beschreibung")
    if description is None:
        raise ValueError("Bitte den Mangel beschreiben.")
    location = _clean(data.get("location"), LOCATION_MAX, "Die Ortsangabe")
    due = data.get("remedy_due_on")
    if due is not None and due < acceptance.accepted_on:
        raise ValueError("Die Beseitigungsfrist liegt vor dem Datum der Abnahme.")
    uploads = _checked_files(files, {"foto", "beleg"})

    lock_order(db, acceptance.order_id)  # wie Verwerfen der Abnahme: Erfassen und Verwerfen warten aufeinander
    db.refresh(acceptance)
    problem = _not_allowed_text(acceptance)
    if problem:
        db.rollback()
        if acceptance.discarded_at is not None or acceptance.checklist_attachment_id is not None:
            raise DefectConflict(problem)
        raise ValueError(problem)
    roof_area = None
    if data.get("roof_area_id") is not None:
        roof_area = db.get(RoofArea, data["roof_area_id"])
        if roof_area is None or acceptance.property_id is None or roof_area.property_id != acceptance.property_id:
            db.rollback()
            raise ValueError("Die gewählte Dachfläche gehört nicht zum Objekt der Abnahme.")
        if roof_area.archived:
            db.rollback()
            raise ValueError(f"Die Dachfläche „{roof_area.name}“ ist archiviert.")
    order = db.get(Order, acceptance.order_id)
    name = (user_name or "System")[:160]
    now = datetime.utcnow().replace(microsecond=0)

    written: list[str] = []
    try:
        task = _new_task(db, order, acceptance, place=roof_area.name if roof_area else location,
                         description=description, due=due, user_id=user_id, user_name=name)
        defect = Defect(
            order_id=order.id, property_id=acceptance.property_id, source="abnahme", acceptance_id=acceptance.id,
            description=description, roof_area_id=roof_area.id if roof_area else None,
            roof_area_name=roof_area.name[:255] if roof_area else None, location=location, remedy_due_on=due,
            task_id=task.id if task else None, content_sha256="", checksum_format=CHECKSUM_FORMAT, created_at=now,
            created_by_user_id=user_id, created_by_name=name,
        )
        for kind, content, content_type in uploads:
            defect.files.append(_store(written, None, kind, content, content_type, now))
        defect.content_sha256 = content_sha256(defect_content(defect))
        db.add(defect)
        db.flush()
        if task is not None:
            task.source_url = f"/orders/{order.id}#mangel-{defect.id}"
        db.commit()
    except Exception:
        db.rollback()
        _remove_written(written)
        raise
    db.refresh(defect)
    return defect


# ---------------------------------------------------------------------------
# Aus dem Abnahmeprotokoll (seit 1.8.60)
# ---------------------------------------------------------------------------

def _protocol_field(checklist):
    return next((f for f in checklist.template_version.fields if f.field_type == "maengel"), None)


def protocol_options(db: Session, checklist) -> dict:
    """Auswahl zum Erfassen im Protokoll: Dachflächen aus dem Objekt des Projekts (nicht archiviert)."""
    order = db.get(Order, checklist.order_id) if checklist.order_id else None
    project = db.get(Project, order.project_id) if order else None
    prop = db.get(Property, project.property_id) if project and project.property_id else None
    areas = db.scalars(select(RoofArea).where(RoofArea.property_id == prop.id, RoofArea.archived.is_(False))
                       .order_by(RoofArea.name)).all() if prop else []
    return {"property": {"id": prop.id, "name": prop.name} if prop else None,
            "roof_areas": [{"id": r.id, "name": r.name} for r in areas]}


def create_protocol_defect(db: Session, checklist_id: int, data: dict, files: list[tuple[str, str | None, bytes]], *,
                           user_id: int | None, user_name: str | None) -> Defect:
    """Einen Mangel im Feld "Mängel" eines Abnahmeprotokolls erfassen. `data`: description, roof_area_id, location,
    remedy_due_on (nicht in der Vergangenheit); `files` wie beim Erfassen an der Abnahme. Unter der Zeilensperre der
    Checkliste (wie beim Unterschreiben): nur im Entwurf und solange keine gültige Unterschrift das Feld versiegelt -- sonst
    ChecklistLocked (409). Keine Aufgabe, keine Abnahme: beides entsteht erst mit der Unterschrift des Auftraggebers."""
    from .checklists import ChecklistLocked, _load as load_checklist, _require_draft, sealed_field_ids

    description = _clean(data.get("description"), DESCRIPTION_MAX, "Die Beschreibung")
    if description is None:
        raise ValueError("Bitte den Mangel beschreiben.")
    location = _clean(data.get("location"), LOCATION_MAX, "Die Ortsangabe")
    due = data.get("remedy_due_on")
    if due is not None and due < berlin_today():
        raise ValueError("Die Beseitigungsfrist liegt in der Vergangenheit.")
    uploads = _checked_files(files, {"foto", "beleg"})

    checklist = load_checklist(db, checklist_id, for_update=True)
    if checklist is None:
        db.rollback()
        raise LookupError("Checkliste nicht gefunden.")
    try:
        _require_draft(checklist)
        field = _protocol_field(checklist)
        if field is None or checklist.order_id is None:
            raise ValueError("Diese Checkliste hat kein Feld „Mängel“.")
        if field.id in sealed_field_ids(checklist):
            raise ChecklistLocked("Das Protokoll ist unterschrieben – an diesem Protokoll entstehen keine neuen Mängel "
                                  "mehr.")
        order = db.get(Order, checklist.order_id)
        project = db.get(Project, order.project_id)
        property_id = project.property_id if project else None
        roof_area = None
        if data.get("roof_area_id") is not None:
            roof_area = db.get(RoofArea, data["roof_area_id"])
            if roof_area is None or property_id is None or roof_area.property_id != property_id:
                raise ValueError("Die gewählte Dachfläche gehört nicht zum Objekt des Projekts.")
            if roof_area.archived:
                raise ValueError(f"Die Dachfläche „{roof_area.name}“ ist archiviert.")
    except (ValueError, LookupError, ChecklistLocked):
        db.rollback()
        raise
    name = (user_name or "System")[:160]
    now = datetime.utcnow().replace(microsecond=0)
    written: list[str] = []
    try:
        defect = Defect(
            order_id=order.id, property_id=property_id, source="protokoll", acceptance_id=None,
            checklist_id=checklist.id, description=description, roof_area_id=roof_area.id if roof_area else None,
            roof_area_name=roof_area.name[:255] if roof_area else None, location=location, remedy_due_on=due,
            task_id=None, content_sha256="", checksum_format=CHECKSUM_FORMAT, created_at=now, created_by_user_id=user_id,
            created_by_name=name,
        )
        for kind, content, content_type in uploads:
            defect.files.append(_store(written, None, kind, content, content_type, now))
        defect.content_sha256 = content_sha256(defect_content(defect))
        db.add(defect)
        db.commit()
    except Exception:
        db.rollback()
        _remove_written(written)
        raise
    db.refresh(defect)
    return defect


def list_protocol_defects(db: Session, checklist) -> list[dict]:
    """Die Mängel eines Protokolls für die Protokollseite (seit 1.8.60): Inhalt, Dateien, Prüfstatus und ob der Mangel in
    der Kopie der ersten Unterschrift unter dem Feld steht -- vorher verworfene nicht, danach verworfene schon (verworfen
    gekennzeichnet). Seit 1.8.62 entscheidet das die abgelegte Kopie selbst (sealed_defect_ids()), kein Zeitvergleich."""
    from .checklists import active_attachments, defect_in_seal, protocol_defects, sealed_defect_ids

    field = _protocol_field(checklist)
    if field is None:
        return []
    position = {f.id: i for i, f in enumerate(checklist.template_version.fields)}
    sealing = sorted((a for a in active_attachments(checklist) if a.kind == "unterschrift"
                      and position.get(a.template_field_id, -1) > position[field.id]), key=lambda a: (a.created_at, a.id))
    sealed_ids = sealed_defect_ids(sealing[0].sealed_content) if sealing else None
    result = []
    for d in protocol_defects(checklist):
        check = verify_defect(d)
        result.append({
            "id": d.id, "description": d.description, "roof_area_id": d.roof_area_id, "roof_area_name": d.roof_area_name,
            "location": d.location, "remedy_due_on": d.remedy_due_on, "acceptance_id": d.acceptance_id,
            "files": [_file_dict(f, check["files"][f.id]) for f in d.files if f.event_id is None],
            "content_sha256": d.content_sha256, "intact": check["ok"], "check": check_summary(check),
            "created_at": d.created_at, "created_at_local": to_berlin(d.created_at), "created_by_name": d.created_by_name,
            "discarded": d.discarded_at is not None, "discarded_at_local": to_berlin(d.discarded_at),
            "discarded_by_name": d.discarded_by_name, "discard_reason": d.discard_reason,
            # Ohne Unterschrift: steht in der nächsten Kopie, wenn nicht verworfen (defect_in_seal(d, None)) -- ein schon
            # verworfener Mangel kommt in keine Kopie mehr.
            "sealed": bool(sealing), "in_protocol": defect_in_seal(d, sealed_ids),
        })
    return result


# ---------------------------------------------------------------------------
# Ereignisse
# ---------------------------------------------------------------------------

def _lock(db: Session, defect: Defect) -> list[DefectEvent]:
    """Sperrt den Mangel bis zum Commit und liest Stand und Ereignisse neu (zwei Bearbeiter gleichzeitig)."""
    db.execute(select(Defect.id).where(Defect.id == defect.id).with_for_update())
    db.refresh(defect)
    if defect.discarded_at is not None:
        db.rollback()
        raise DefectConflict("Der Mangel ist verworfen – keine weiteren Einträge.")
    if protocol_pending(defect):  # seit 1.8.60
        db.rollback()
        raise DefectConflict(PROTOCOL_PENDING_TEXT)
    return list(db.scalars(select(DefectEvent).where(DefectEvent.defect_id == defect.id).order_by(DefectEvent.id)).all())


def _complete_task(db: Session, task_id: int | None) -> bool:
    """Die Aufgabe zum Mangel in die erste "erledigt"-Spalte -- archivierte und schon erledigte bleiben, wie sie sind."""
    task = db.get(Task, task_id) if task_id is not None else None
    if task is None or task.archived:
        return False
    columns = db.scalars(select(TaskColumn).order_by(TaskColumn.sort_order, TaskColumn.id)).all()
    done = [c.key for c in columns if c.is_done]
    if not done or task.status in done:
        return False
    task.status = done[0]
    task.completed_at = datetime.utcnow()
    return True


def _append(db: Session, defect: Defect, events: list[DefectEvent], *, kind: str, value: str | None,
            previous_value: str | None, files: list[tuple[str, bytes, str]] = (), event_date=None,
            reason: str | None = None, declared: dict | None = None, user_id: int | None, user_name: str | None,
            complete_task: bool = False, task_kind: str | None = None, client_uuid: str | None = None,
            due_on=None) -> DefectEvent:
    """Ein Eintrag im Verlauf, in einem Commit mit der Aufgabe: complete_task erledigt die aktuelle Aufgabe, task_kind
    (seit 1.8.54) erledigt sie ebenfalls und legt die nächste an -- vor dem Eintrag, damit er ihre ID beim Einfügen trägt
    (danach ist er unveränderlich). due_on (seit 1.8.55): neue Beseitigungsfrist des Eintrags, auch die der neuen
    Aufgabe."""
    name = (user_name or "System")[:160]
    now = datetime.utcnow().replace(microsecond=0)
    written: list[str] = []
    try:
        task_id = None
        if complete_task or task_kind:
            _complete_task(db, current_task(defect, events)[0])
        if task_kind:
            task = _follow_task(db, defect, task_kind, event_date=event_date, user_id=user_id, user_name=name,
                                via_field_view=client_uuid is not None,
                                due=due_on if due_on is not None else current_due(defect, events))
            task_id = task.id if task is not None else None
        event = DefectEvent(
            defect_id=defect.id, kind=kind, value=value, previous_value=previous_value, event_date=event_date,
            reason=reason, previous_event_sha256=events[-1].content_sha256 if events else None,
            content_sha256="", checksum_format=CHECKSUM_FORMAT, created_at=now, created_by_user_id=user_id,
            created_by_name=name, client_uuid=client_uuid, task_id=task_id, due_on=due_on, **(declared or {}),
        )
        for file_kind, content, content_type in files:
            event.files.append(_store(written, defect.id, file_kind, content, content_type, now))
        event.content_sha256 = content_sha256(event_content(event, defect.content_sha256))
        db.add(event)
        db.commit()
    except Exception:
        db.rollback()
        _remove_written(written)
        raise
    db.refresh(event)
    return event


def set_stance(db: Session, defect: Defect, *, stance: str, reason: str | None, user_id: int | None,
               user_name: str | None) -> DefectEvent:
    """Haltung zum Mangel: anerkannt oder bestritten (Begründung Pflicht). Nie zurück auf "offen"."""
    if stance not in ("anerkannt", "bestritten"):
        raise ValueError("Haltung: anerkannt oder bestritten.")
    text = _clean(reason, REASON_MAX, "Die Begründung")
    if stance == "bestritten" and text is None:
        raise ValueError("Bitte begründen, warum der Mangel bestritten wird.")
    events = _lock(db, defect)
    current = defect_state(events)["stance"]
    if current == stance:
        db.rollback()
        raise DefectConflict(f"Der Mangel ist bereits {STANCES[stance]}.")
    return _append(db, defect, events, kind="haltung", value=stance, previous_value=current, reason=text,
                   user_id=user_id, user_name=user_name)


def set_release(db: Session, defect: Defect, *, released: bool, reason: str | None, user_id: int | None,
                user_name: str | None) -> DefectEvent:
    """Freigabe zur Beseitigung -- bewusst, unabhängig von der Haltung; bei "bestritten" mit Begründung (Kulanz),
    Zurücknehmen immer mit Begründung; nach einem erledigten Status nicht mehr."""
    text = _clean(reason, REASON_MAX, "Die Begründung")
    events = _lock(db, defect)
    state = defect_state(events)
    problem = None
    if state["done"]:
        problem = DefectConflict(f"Der Mangel ist erledigt ({STATUSES[state['status']]}) – keine Freigabe mehr.")
    elif state["released"] == released:
        problem = DefectConflict("Der Mangel ist bereits zur Beseitigung freigegeben." if released
                                 else "Der Mangel ist nicht zur Beseitigung freigegeben.")
    elif released and state["stance"] == "bestritten" and text is None:
        problem = ValueError("Der Mangel ist bestritten – eine Freigabe trotzdem (z. B. aus Kulanz) bitte begründen.")
    elif not released and text is None:
        problem = ValueError("Bitte begründen, warum die Freigabe zurückgenommen wird.")
    if problem is not None:
        db.rollback()
        raise problem
    value = "freigegeben" if released else "zurueckgenommen"
    previous = "freigegeben" if state["released"] else ("zurueckgenommen" if state["release_event"] else None)
    return _append(db, defect, events, kind="freigabe", value=value, previous_value=previous, reason=text,
                   user_id=user_id, user_name=user_name)


def _declarer(db: Session, defect: Defect, data: dict) -> tuple[dict, tuple[bytes, str] | None]:
    from .contacts import contact_display_name
    from .project_participants import role_label

    declared_by, participant_id = data.get("declared_by"), data.get("participant_id")
    if declared_by not in DECLARERS:
        raise ValueError("Bitte angeben, wer die Beseitigung abgenommen hat.")
    order = db.get(Order, defect.order_id)
    if declared_by == "auftraggeber":
        if participant_id is not None:
            raise ValueError("Ein Beteiligter gehört nur zu „erklärt durch einen Beteiligten“.")
        return {"declared_by": "auftraggeber", "declared_by_name": (order.customer_name or "Auftraggeber")[:255]}, None
    participant = db.get(ProjectParticipant, participant_id) if participant_id is not None else None
    if participant is None or participant.project_id != order.project_id:
        raise ValueError("Bitte einen Beteiligten dieses Projekts wählen.")
    if participant.contact.archived:
        raise ValueError("Der gewählte Beteiligte ist im Adressbuch archiviert.")
    frozen = _frozen_power_of_attorney(participant)
    return {"declared_by": "beteiligter", "participant_id": participant.id,
            "declared_by_name": (contact_display_name(participant.contact) or f"Kontakt #{participant.contact_id}")[:255],
            "declared_by_role": role_label(participant.role), "poa_on_record": frozen is not None}, frozen


def set_status(db: Session, defect: Defect, data: dict, files: list[tuple[str, str | None, bytes]], *,
               user_id: int | None, user_name: str | None) -> DefectEvent:
    """Status weiterschreiben. `data`: status, event_date, reason, declared_by, participant_id, seit 1.8.55 due_on (neue
    Beseitigungsfrist, nur bei "zurück auf offen", optional, nicht vor heute); `files`: Belege nur bei "Beseitigung
    abgenommen". Ein Übergang, den der Stand nicht (mehr) zulässt, ist ein DefectConflict (409)."""
    status = data.get("status")
    if status not in STATUSES:
        raise ValueError("Unbekannter Status.")
    text = _clean(data.get("reason"), REASON_MAX, "Die Begründung")
    event_date = data.get("event_date")
    uploads = _checked_files(files, {"beleg"}) if files else []
    if files and status != "beseitigung_abgenommen":
        raise ValueError("Belege gehören zu „Beseitigung abgenommen“ – Fotos bitte über „Fotos ergänzen“.")
    if status in ("beseitigt", "beseitigung_abgenommen"):
        if event_date is None:
            raise ValueError("Bitte das Datum angeben.")
        if event_date > berlin_today():
            raise ValueError("Das Datum darf nicht in der Zukunft liegen.")
    elif event_date is not None:
        raise ValueError("Ein Datum gehört nur zu „beseitigt“ und „Beseitigung abgenommen“.")
    if status in ("erledigt_ohne", "offen") and text is None:
        raise ValueError("Bitte begründen, warum der Mangel ohne Beseitigung erledigt ist." if status == "erledigt_ohne"
                         else "Bitte begründen, warum der Mangel wieder offen ist (z. B. Beseitigung nicht gelungen).")
    if status == "beseitigung_abgenommen" and not uploads and text is None:
        raise ValueError("Bitte einen Nachweis der Abnahme der Beseitigung angeben: einen Beleg (PDF oder Foto) oder "
                         "eine Begründung, woraus sie sich ergibt.")
    if status != "beseitigung_abgenommen" and (data.get("declared_by") or data.get("participant_id") is not None):
        raise ValueError("„Erklärt durch“ gehört nur zu „Beseitigung abgenommen“.")
    due_on = data.get("due_on")
    if due_on is not None and status != "offen":
        raise ValueError("Eine neue Beseitigungsfrist gehört nur zu „zurück auf offen“.")
    if due_on is not None and due_on < berlin_today():
        raise ValueError("Die neue Beseitigungsfrist liegt in der Vergangenheit.")

    events = _lock(db, defect)
    state = defect_state(events)
    if status not in STATUS_STEPS.get(state["status"], ()):
        db.rollback()
        raise DefectConflict(f"Der Mangel steht auf „{STATUSES[state['status']]}“ – „{STATUSES[status]}“ ist von dort "
                             "nicht möglich. Bitte die Seite neu laden.")
    acceptance = db.get(OrderAcceptance, defect.acceptance_id) if defect.acceptance_id else None
    try:
        if status == "beseitigt" and acceptance is not None and event_date < acceptance.accepted_on:
            raise ValueError("Das Datum der Beseitigung liegt vor der Abnahme, bei der der Mangel festgehalten wurde.")
        if status == "beseitigung_abgenommen" and event_date < state["status_date"]:
            raise ValueError("Die Abnahme der Beseitigung liegt vor dem Datum der Beseitigung.")
        declared, frozen = _declarer(db, defect, data) if status == "beseitigung_abgenommen" else (None, None)
    except ValueError:
        db.rollback()
        raise
    stored_files = [("beleg", c, t) for _, c, t in uploads]
    if frozen is not None:
        stored_files.append(("abnahmevollmacht", *frozen))
    return _append(db, defect, events, kind="status", value=status, previous_value=state["status"],
                   files=stored_files, event_date=event_date, reason=text, declared=declared, user_id=user_id,
                   user_name=user_name, complete_task=status in DONE_STATUSES, task_kind=STATUS_TASKS.get(status),
                   due_on=due_on)


def add_photos(db: Session, defect: Defect, files: list[tuple[str, str | None, bytes]], *, user_id: int | None,
               user_name: str | None) -> DefectEvent:
    """Fotos ergänzen -- nur hinzufügen, nie ersetzen oder entfernen."""
    uploads = _checked_files([("foto", name, data) for _, name, data in files], {"foto"})
    if not uploads:
        raise ValueError("Bitte mindestens ein Foto auswählen.")
    events = _lock(db, defect)
    return _append(db, defect, events, kind="fotos", value=None, previous_value=None, files=uploads, user_id=user_id,
                   user_name=user_name)


def add_receipts(db: Session, defect: Defect, files: list[tuple[str, str | None, bytes]], *, user_id: int | None,
                 user_name: str | None) -> DefectEvent:
    """Belege ergänzen (seit 1.8.51) -- wie Fotos: nur hinzufügen, eigener Eintrag im Verlauf; PDF oder Foto, am Inhalt
    erkannt. Auch nach der Erledigung, nicht nach dem Verwerfen."""
    uploads = _checked_files([("beleg", name, data) for _, name, data in files], {"beleg"})
    if not uploads:
        raise ValueError("Bitte mindestens einen Beleg auswählen.")
    events = _lock(db, defect)
    return _append(db, defect, events, kind="belege", value=None, previous_value=None, files=uploads, user_id=user_id,
                   user_name=user_name)


def discard_defect(db: Session, defect: Defect, *, reason: str, user_id: int | None, user_name: str | None) -> Defect:
    """Verwirft einen Mangel mit Begründung -- genau einmal (bedingtes UPDATE mit Siegel an der ORM-Sperre vorbei),
    Historie, erledigt die aktuelle Aufgabe."""
    from .audit import record_audit_entry

    text = _clean(reason, REASON_MAX, "Die Begründung")
    if text is None:
        raise ValueError("Bitte begründen, warum der Mangel verworfen wird.")
    if defect.checklist_id is not None:
        # Seit 1.8.60: erst die Checkliste, dann der Mangel (wie beim Erfassen) -- Unterschrift und Verwerfen laufen
        # nacheinander; ob der Mangel danach im Protokoll bleibt, sagt die Kopie der Unterschrift (seit 1.8.62).
        from .models import Checklist
        db.execute(select(Checklist.id).where(Checklist.id == defect.checklist_id).with_for_update())
    db.execute(select(Defect.id).where(Defect.id == defect.id).with_for_update())
    now = datetime.utcnow()  # volle Genauigkeit seit 1.8.60 -- das Siegel des Verwerfens rundet selbst auf Sekunden
    name = (user_name or "System")[:160]
    seal = content_sha256(discard_content(defect.content_sha256, now, name, text))
    done = db.execute(
        update(Defect).where(Defect.id == defect.id, Defect.discarded_at.is_(None))
        .values(discarded_at=now, discarded_by_user_id=user_id, discarded_by_name=name, discard_reason=text,
                discard_sha256=seal)
        .execution_options(synchronize_session=False)
    ).rowcount
    if done != 1:
        db.rollback()
        raise DefectConflict("Dieser Mangel ist bereits verworfen.")
    order = db.get(Order, defect.order_id)
    record_audit_entry(db, action="verworfen", entity_type=ENTITY_TYPE, entity_id=defect.id,
                       entity_label=defect_label(defect, order), project_id=order.project_id if order else None,
                       field_name="discard_reason", old_value=None, new_value=text, actor_user_id=user_id,
                       actor_name=name)
    events = db.scalars(select(DefectEvent).where(DefectEvent.defect_id == defect.id)).all()
    _complete_task(db, current_task(defect, events)[0])
    db.commit()
    db.expire(defect)
    db.refresh(defect)
    return defect


# ---------------------------------------------------------------------------
# Nachbesserung (nur VOB/B)
# ---------------------------------------------------------------------------

def remedy_warranty(defect: Defect, state: dict, acceptance: OrderAcceptance | None, order: Order,
                    acceptance_check: dict | None, defect_check: dict) -> dict | None:
    """"Nachbesserung regulär bis" -- nur bei Vertragsgrundlage vob_b und "Beseitigung abgenommen": das spätere von
    "Gewährleistung regulär bis" der Abnahme und Abnahme der Beseitigung plus 24 Monate. Prüfstatus aus Abnahme und
    Mangel; nie gespeichert."""
    if order.contract_basis != "vob_b" or state["status"] != "beseitigung_abgenommen" or defect.discarded_at:
        return None
    remedy_on = state["status_date"]
    remedy_end = warranty_end(remedy_on, REMEDY_MONTHS, 0)
    base = acceptance_warranty(acceptance, order, acceptance_check) if acceptance is not None else None
    problems = [c["text"] for c in (check_summary(acceptance_check) if acceptance_check else None, defect_check)
                if c is not None and not c["ok"]]
    check = {"ok": not problems, "text": "; ".join(problems) if problems else "Prüfsumme stimmt"}
    if base is None:
        return {"end": None, "check": check, "rule": REMEDY_RULE, "hint": None,
                "text": "Nachbesserung regulär bis: nicht berechenbar – die Abnahme ist verweigert oder verworfen, es "
                        "gibt kein reguläres Ende"}
    if base["end"] is None:
        return {"end": None, "check": check, "rule": REMEDY_RULE, "hint": None,
                "text": "Nachbesserung regulär bis: nicht berechenbar – Gewährleistungsdauer am Auftrag nicht festgelegt"}
    end = max(base["end"], remedy_end)
    return {"end": end, "regular_end": base["end"], "remedy_end": remedy_end, "remedy_accepted_on": remedy_on,
            "check": check, "rule": REMEDY_RULE, "hint": REGULAR_HINT,
            "text": f"Nachbesserung regulär bis {end:%d.%m.%Y} (das spätere von „Gewährleistung regulär bis“ "
                    f"{base['end']:%d.%m.%Y} und Abnahme der Beseitigung {remedy_on:%d.%m.%Y} + {REMEDY_MONTHS} Monate "
                    f"= {remedy_end:%d.%m.%Y})"}


# ---------------------------------------------------------------------------
# Anzeige
# ---------------------------------------------------------------------------

def defect_label(d: Defect, order: Order | None) -> str:
    number = order.order_number if order else f"Auftrag #{d.order_id}"
    place = d.roof_area_name or d.location
    return f"{number} · Mangel Nr. {d.id}{' · ' + place if place else ''}"[:255]


def _file_dict(f: DefectFile, status: str) -> dict:
    from .acceptances import VERIFY_TEXTS

    return {"id": f.id, "kind": f.kind, "kind_label": FILE_KINDS.get(f.kind, f.kind), "content_type": f.content_type,
            "size_bytes": f.size_bytes, "sha256": f.sha256, "status": status, "status_text": VERIFY_TEXTS[status]}


def _event_dict(e: DefectEvent, check: dict) -> dict:
    labels = {"haltung": STANCES, "status": STATUSES, "freigabe": RELEASES}.get(e.kind, {})
    return {
        "id": e.id, "kind": e.kind, "kind_label": EVENT_KINDS.get(e.kind, e.kind),
        "value": e.value, "value_label": labels.get(e.value, e.value),
        "previous_value": e.previous_value, "previous_value_label": labels.get(e.previous_value, e.previous_value),
        "event_date": e.event_date, "reason": e.reason, "due_on": e.due_on,  # due_on: neue Frist (seit 1.8.55)
        "declared_by": e.declared_by, "declared_by_label": DECLARERS.get(e.declared_by) if e.declared_by else None,
        "declared_by_name": e.declared_by_name, "declared_by_role": e.declared_by_role,
        "without_power_of_attorney": e.declared_by == "beteiligter" and not any(f.kind == "abnahmevollmacht"
                                                                                 for f in e.files),
        "files": [_file_dict(f, check["files"].get(f.id, "fehlt")) for f in e.files],
        "intact": check["events"].get(e.id, False),
        "created_at": e.created_at, "created_at_local": to_berlin(e.created_at), "created_by_name": e.created_by_name,
        "via_field_view": e.client_uuid is not None,  # seit 1.8.52: Meldung aus der Monteursansicht (reason = Hinweis)
        # seit 1.8.54: die Aufgabe, die dieser Eintrag angelegt hat
        "task_id": e.task_id,
        "task_label": TASK_KINDS[STATUS_TASKS.get(e.value, "beseitigen")] if e.task_id is not None else None,
    }


def _task_dict(task: Task | None, task_id: int | None, kind: str, columns: dict[str, TaskColumn]) -> dict:
    if task_id is None:
        return {"exists": False, "text": "keine Aufgabe angelegt (Aufgabenmodul beim Erfassen ausgeschaltet)"}
    if task is None:
        return {"exists": False, "id": task_id, "text": f"Aufgabe Nr. {task_id} wurde gelöscht"}
    column = columns.get(task.status)
    done = bool(column and column.is_done)
    return {"exists": True, "id": task.id, "title": task.title, "done": done, "archived": task.archived,
            "status_label": column.label if column else task.status, "kind_label": TASK_KINDS[kind],
            "url": f"/tasks?task={task.id}"}


def defect_to_dict(d: Defect, *, order: Order, acceptance: OrderAcceptance | None, acceptance_check: dict | None,
                   tasks: dict[int, Task], columns: dict[str, TaskColumn]) -> dict:
    check = verify_defect(d)
    state = defect_state(d.events)
    task_id, task_kind = current_task(d, d.events)
    task_info = _task_dict(tasks.get(task_id), task_id, task_kind, columns)
    if protocol_pending(d):  # seit 1.8.60
        task_info = {"exists": False, "text": "entsteht mit der Abnahme aus dem Abnahmeprotokoll"}
    due = current_due(d, d.events)
    task_hint = None
    if task_info.get("done") and not state["done"] and d.discarded_at is None:
        task_hint = "Die Aufgabe ist erledigt, der Mangel aber nicht – maßgeblich ist der Mangel."
    return {
        "id": d.id, "order_id": d.order_id, "order_number": order.order_number, "source": d.source,
        "source_label": SOURCES.get(d.source, d.source), "acceptance_id": d.acceptance_id,
        # seit 1.8.60: aus einem Abnahmeprotokoll; ohne Abnahme noch keine Haltung, Freigabe, Status
        "checklist_id": d.checklist_id, "protocol_pending": protocol_pending(d),
        "acceptance": None if acceptance is None else {
            "id": acceptance.id, "accepted_on": acceptance.accepted_on,
            "scope_label": SCOPES.get(acceptance.scope, acceptance.scope), "result_text": result_text(acceptance),
            "discarded": acceptance.discarded_at is not None},
        "property_id": d.property_id, "description": d.description, "roof_area_id": d.roof_area_id,
        # remedy_due_on: die aktuelle Frist (seit 1.8.55), remedy_due_on_original: die beim Erfassen
        "roof_area_name": d.roof_area_name, "location": d.location, "remedy_due_on": due,
        "remedy_due_on_original": d.remedy_due_on, "remedy_due_changed": due != d.remedy_due_on,
        "remedy_overdue": bool(due and not state["done"] and d.discarded_at is None and due < berlin_today()),
        "files": [_file_dict(f, check["files"][f.id]) for f in d.files if f.event_id is None],
        "stance": state["stance"], "stance_label": STANCES[state["stance"]],
        "status": state["status"], "status_label": STATUSES[state["status"]], "status_date": state["status_date"],
        "released": state["released"], "done": state["done"],
        "next_statuses": [{"value": s, "label": STATUSES[s]} for s in STATUS_STEPS.get(state["status"], ())],
        "events": [_event_dict(e, check) for e in sorted(d.events, key=lambda x: x.id)],
        "remedy_warranty": remedy_warranty(d, state, acceptance, order, acceptance_check, check_summary(check)),
        "task": task_info, "task_hint": task_hint,
        "content_sha256": d.content_sha256, "checksum_format": d.checksum_format,
        "intact": check["ok"], "check": check_summary(check),
        "created_at": d.created_at, "created_at_local": to_berlin(d.created_at), "created_by_name": d.created_by_name,
        "discarded": d.discarded_at is not None, "discarded_at": d.discarded_at,
        "discarded_at_local": to_berlin(d.discarded_at), "discarded_by_name": d.discarded_by_name,
        "discard_reason": d.discard_reason,
        "discard_check": check["discard"], "discard_check_text": DISCARD_TEXTS.get(check["discard"]),
    }


def _load_defects(db: Session, query) -> list[Defect]:
    return db.scalars(query.options(selectinload(Defect.files),
                                    selectinload(Defect.events).selectinload(DefectEvent.files))).all()


def _dicts(db: Session, rows: list[Defect], order: Order) -> list[dict]:
    acceptance_ids = {d.acceptance_id for d in rows if d.acceptance_id}
    acceptances = {a.id: a for a in db.scalars(
        select(OrderAcceptance).where(OrderAcceptance.id.in_(acceptance_ids))
        .options(selectinload(OrderAcceptance.roof_areas), selectinload(OrderAcceptance.files))
    ).all()} if acceptance_ids else {}
    checks = {a_id: verify_acceptance(a) for a_id, a in acceptances.items()}
    task_ids = {current_task(d, d.events)[0] for d in rows} - {None}
    tasks = {t.id: t for t in db.scalars(select(Task).where(Task.id.in_(task_ids))).all()} if task_ids else {}
    columns = {c.key: c for c in db.scalars(select(TaskColumn)).all()}
    return [defect_to_dict(d, order=order, acceptance=acceptances.get(d.acceptance_id),
                           acceptance_check=checks.get(d.acceptance_id), tasks=tasks, columns=columns)
            for d in rows]


def list_defects(db: Session, order: Order) -> list[dict]:
    """Alle Mängel des Auftrags samt verworfener (Historie), in der Reihenfolge des Erfassens."""
    return _dicts(db, _load_defects(db, select(Defect).where(Defect.order_id == order.id).order_by(Defect.id)), order)


def get_defect_dict(db: Session, defect: Defect) -> dict:
    order = db.get(Order, defect.order_id)
    return _dicts(db, _load_defects(db, select(Defect).where(Defect.id == defect.id)), order)[0]


# ---------------------------------------------------------------------------
# Monteur (seit 1.8.52, Stufe 2c-2b): Mängel zur Beseitigung in /mobil
# ---------------------------------------------------------------------------

FIELD_KEY_MAX = 36
FIELD_NOTE_MAX = 500  # Hinweis des Monteurs zur Meldung (seit 1.8.54), nur fürs Büro
FIELD_PHOTO_KIND = "foto"  # nur Fotos -- Belege und Vollmachten nie (können Schreiben des Kunden sein)


def field_may_see_defect(d: Defect, state: dict) -> bool:
    """Die eine Regel, wann ein Monteur einen Mangel sieht (neben dem Zugriff auf den Auftrag): zur Beseitigung
    freigegeben, Status "offen", nicht verworfen. Nimmt das Büro die Freigabe zurück, setzt es einen anderen Status oder
    verwirft es den Mangel, verschwindet er; setzt es nach "beseitigt" zurück auf "offen", ist er wieder da."""
    return d.discarded_at is None and state["released"] and state["status"] == "offen"


def field_defect_dict(d: Defect, order: Order, prop: Property | None) -> dict:
    """Die Positivliste für den Monteur: Beschreibung, Ort, Dachfläche, Frist (seit 1.8.55 die aktuelle, current_due()),
    Fotos -- dazu, wo er hin muss (Auftrag, Objekt der Abnahme, sonst der Schnappschuss am Auftrag). Keine Haltung, keine
    Abnahmedaten, keine Gewährleistung, kein Verlauf. Das Antwortschema (FieldDefectOut) lässt zusätzlich nichts anderes
    durch."""
    if prop is not None:
        name = prop.name
        address = ", ".join(x for x in (prop.street, " ".join(y for y in (prop.postal_code, prop.city) if y)) if x)
    else:
        name, address = order.property_name, order.property_address
    due = current_due(d, d.events)
    return {
        "id": d.id, "order_id": d.order_id, "order_number": order.order_number,
        "property_name": name, "property_address": address or None,
        "description": d.description, "location": d.location, "roof_area_name": d.roof_area_name,
        "remedy_due_on": due,
        "remedy_overdue": bool(due and due < berlin_today()),
        "photos": [{"id": f.id} for f in sorted(d.files, key=lambda f: f.id) if f.kind == FIELD_PHOTO_KIND],
    }


def list_field_defects(db: Session, employee_id: int) -> list[dict]:
    """Die Mängel, die der Monteur beseitigen soll: an Aufträgen, die er öffnen darf (field_accessible_order_ids(),
    dieselbe Regel wie field_may_access_order()), nach field_may_see_defect(). Frist zuerst (ohne Frist zuletzt)."""
    from .orders import field_accessible_order_ids

    order_ids = field_accessible_order_ids(db, employee_id)
    if not order_ids:
        return []
    rows = [d for d in _load_defects(db, select(Defect).where(Defect.order_id.in_(order_ids),
                                                              Defect.discarded_at.is_(None)))
            if field_may_see_defect(d, defect_state(d.events))]
    orders = {o.id: o for o in db.scalars(select(Order).where(Order.id.in_({d.order_id for d in rows})))} if rows else {}
    prop_ids = {d.property_id for d in rows if d.property_id}
    props = {p.id: p for p in db.scalars(select(Property).where(Property.id.in_(prop_ids)))} if prop_ids else {}
    dues = {d.id: current_due(d, d.events) for d in rows}
    rows.sort(key=lambda d: (dues[d.id] is None, dues[d.id] or berlin_today(), d.id))
    return [field_defect_dict(d, orders[d.order_id], props.get(d.property_id)) for d in rows]


def field_visible_defect(db: Session, employee_id: int, defect_id: int) -> Defect | None:
    """Der Mangel, wenn der Monteur ihn sehen darf -- sonst None (der Router antwortet 404, ohne zu verraten, ob es ihn
    gibt, ob er nicht freigegeben ist oder zu einem fremden Auftrag gehört)."""
    from .orders import field_may_access_order

    d = db.get(Defect, defect_id, options=[selectinload(Defect.files), selectinload(Defect.events)])
    if d is None or not field_may_access_order(db, employee_id, d.order_id):
        return None
    return d if field_may_see_defect(d, defect_state(d.events)) else None


def field_photo(d: Defect, file_id: int) -> DefectFile | None:
    """Ein Foto genau dieses Mangels (beim Erfassen, ergänzt oder aus einer früheren Meldung) -- nie ein Beleg."""
    return next((f for f in d.files if f.id == file_id and f.kind == FIELD_PHOTO_KIND), None)


def _field_key(client_uuid: str | None) -> str:
    key = (client_uuid or "").strip()
    if not key or len(key) > FIELD_KEY_MAX:
        raise ValueError("Die Kennung der Meldung (client_uuid) fehlt oder ist zu lang.")
    return key


def _event_by_key(db: Session, key: str) -> DefectEvent | None:
    return db.scalar(select(DefectEvent).where(DefectEvent.client_uuid == key))


def _replay(event: DefectEvent, defect_id: int, user_id: int | None) -> DefectEvent:
    """Eine gespeicherte Meldung zu dieser Kennung -- nur an dieselbe Person für denselben Mangel."""
    if event.defect_id != defect_id or user_id is None or event.created_by_user_id != user_id:
        raise ValueError("Diese Kennung (client_uuid) ist bereits vergeben.")
    return event


def field_report_replay(db: Session, defect_id: int, client_uuid: str | None, user_id: int | None) -> DefectEvent | None:
    """Gibt es zu dieser Kennung schon eine Meldung, ist das die Antwort -- auch wenn der Mangel inzwischen nicht mehr
    sichtbar ist (die Meldung selbst hat ihn auf "beseitigt" gesetzt). Deshalb fragt der Router das VOR der
    Sichtbarkeit. ValueError, wenn die Kennung zu einer anderen Person oder einem anderen Mangel gehört."""
    event = _event_by_key(db, _field_key(client_uuid))
    return _replay(event, defect_id, user_id) if event is not None else None


def report_remedied(db: Session, defect: Defect, *, event_date, client_uuid: str | None,
                    files: list[tuple[str, str | None, bytes]], user_id: int | None,
                    user_name: str | None, note: str | None = None) -> DefectEvent:
    """Der Monteur meldet "beseitigt": Status offen -> beseitigt mit Datum und mindestens einem Foto (Dateien des
    Eintrags, Art "foto"), ohne Erklärenden. Seit 1.8.54 optional ein kurzer Hinweis (höchstens FIELD_NOTE_MAX Zeichen)
    als Text des Eintrags -- im gebundenen Inhalt, nur fürs Büro sichtbar (die Positivliste in /mobil kennt keinen
    Verlauf). Wie im Büro erledigt "beseitigt" die Aufgabe "Mangel beseitigen" und legt "Beseitigung abnehmen lassen"
    an. Idempotent über client_uuid (global eindeutig): eine schon gespeicherte Meldung mit dieser Kennung ist die
    Antwort, geprüft vor dem Einfügen und unter der Sperre des Mangels; eine gleichzeitige Wiederholung, die beides
    passiert, fängt der UNIQUE-Schlüssel ab. Unter der Sperre neu geprüft: verworfen, Freigabe zurückgenommen oder
    Status nicht mehr "offen" -> DefectConflict (409). Ob der Monteur den Mangel sehen darf, prüft der Router vorher
    (field_visible_defect())."""
    key = _field_key(client_uuid)
    existing = _event_by_key(db, key)
    if existing is not None:
        return _replay(existing, defect.id, user_id)
    text = _clean(note, FIELD_NOTE_MAX, "Der Hinweis")
    uploads = _checked_files([("foto", name, data) for _, name, data in files], {"foto"})
    if not uploads:
        raise ValueError("Bitte mindestens ein Foto der Beseitigung aufnehmen.")
    if event_date is None:
        raise ValueError("Bitte das Datum der Beseitigung angeben.")
    if event_date > berlin_today():
        raise ValueError("Das Datum darf nicht in der Zukunft liegen.")
    acceptance = db.get(OrderAcceptance, defect.acceptance_id) if defect.acceptance_id else None
    if acceptance is not None and event_date < acceptance.accepted_on:
        raise ValueError("Das Datum der Beseitigung liegt vor der Abnahme, bei der der Mangel festgehalten wurde.")

    db.execute(select(Defect.id).where(Defect.id == defect.id).with_for_update())
    db.refresh(defect)
    existing = _event_by_key(db, key)
    if existing is not None:  # dieselbe Meldung war gleichzeitig unterwegs und hat zuerst committet
        db.rollback()
        return _replay(existing, defect.id, user_id)
    events = list(db.scalars(select(DefectEvent).where(DefectEvent.defect_id == defect.id).order_by(DefectEvent.id)))
    state = defect_state(events)
    problem = None
    if defect.discarded_at is not None:
        problem = "Der Mangel ist verworfen – keine Meldung mehr."
    elif not state["released"]:
        problem = "Der Mangel ist nicht mehr zur Beseitigung freigegeben."
    elif state["status"] != "offen":
        problem = f"Der Mangel steht schon auf „{STATUSES[state['status']]}“."
    if problem:
        db.rollback()
        raise DefectConflict(problem + " Bitte die Seite neu laden.")
    try:
        return _append(db, defect, events, kind="status", value="beseitigt", previous_value="offen", files=uploads,
                       event_date=event_date, reason=text, client_uuid=key, user_id=user_id, user_name=user_name,
                       task_kind=STATUS_TASKS["beseitigt"])
    except IntegrityError:
        existing = _event_by_key(db, key)  # _append hat zurückgerollt
        if existing is None:
            raise
        return _replay(existing, defect.id, user_id)


def field_report_dict(event: DefectEvent) -> dict:
    """Die Antwort auf eine Meldung -- dieselbe beim ersten Mal und bei jeder Wiederholung der Kennung."""
    return {"defect_id": event.defect_id, "event_id": event.id, "event_date": event.event_date,
            "photo_count": sum(f.kind == FIELD_PHOTO_KIND for f in event.files)}
