"""Versandprotokoll und Sperre gegen Doppelversand (seit 1.8.17, Stufe 2, Runde 2a-3a).

dispatch_email() ist der einzige Weg, eine E-Mail zu versenden (app/email_sending.py::
send_message() hat keinen anderen Aufrufer, per Test erzwungen). Ablauf je Versandauftrag:

1. Schlüssel prüfen: Jeder Versandauftrag trägt einen Schlüssel (dispatch_key, von der Seite je
   Klick erzeugt). Gibt es ihn schon, wird nie ein zweites Mal gesendet: "gesendet" liefert den
   vorhandenen Eintrag zurück (eine wiederholte Anfrage bekommt dieselbe Antwort), "in_arbeit"
   und "fehlgeschlagen" werden mit DispatchConflict (409) abgelehnt -- ein neuer Versuch ist ein
   neuer Klick mit neuem Schlüssel.
2. Vorab prüfen, ohne etwas zu schreiben: Empfänger, Konfiguration, Anhanggröße (3 MB). Dazu:
   läuft für dasselbe Dokument gerade ein anderer Versand (in_arbeit, jünger als STUCK_AFTER),
   409 -- fängt "Seite neu geladen, noch einmal geklickt" ab, während der erste noch sendet.
3. Eintrag "in_arbeit" anlegen (Unique-Schlüssel im SAVEPOINT, bei gleichzeitigem Doppelklick
   gewinnt genau einer) und committen -- VOR dem Senden. Bricht der Prozess danach ab, bleibt der
   Eintrag "in_arbeit" stehen und erscheint nach STUCK_AFTER als hängengeblieben. Er wird nie
   automatisch erneut gesendet: ob die Mail hinausging, weiß nur der Postausgang.
4. PDF in die Ablage (app/sent_documents.py), Verweis am Eintrag, commit. Scheitert das Ablegen,
   wird nicht gesendet.
5. Senden mit der eigenen Kennung als Kopfzeile X-DK-Versand-ID, danach "gesendet" bzw.
   "fehlgeschlagen" per bedingtem UPDATE (nur aus "in_arbeit").

Regel 18: im Protokoll stehen Empfänger und Betreff (vom Betreiber für den Nachweis verlangt), nie
der Mailtext und nie der Fehlertext -- vom Fehler nur Klassenname und Code (HTTP-Status bzw.
SMTP-Antwortcode). Der Fehlertext geht wie bisher nur an den Menschen, der gerade sendet.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .email_sending import check_attachment_size, ensure_configured, get_or_create_smtp_settings, send_message
from .models import EmailDispatch
from .sent_documents import DOCUMENT_TYPES, store_sent_document

HEADER_NAME = "X-DK-Versand-ID"
STUCK_AFTER = timedelta(minutes=10)
MAX_RECIPIENTS = 20
STATUSES = {"in_arbeit": "In Arbeit", "gesendet": "Gesendet", "fehlgeschlagen": "Fehlgeschlagen"}
CHANNELS = {"smtp": "SMTP", "graph_oauth2": "Microsoft 365"}
DISPATCH_TYPES = {**DOCUMENT_TYPES, "aufgabe": "Aufgaben-Benachrichtigung"}

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,79}$")
_ADDRESS_RE = re.compile(r"^[^@\s,;<>\"]+@[^@\s,;<>\"]+\.[^@\s,;<>\"]+$")


class DispatchConflict(Exception):
    """Dieser Versandauftrag wird nicht (noch einmal) gesendet -- Router: 409."""


@dataclass
class DispatchResult:
    dispatch: EmailDispatch
    newly_sent: bool  # False: derselbe Schlüssel war schon gesendet, nichts hinausgegangen


def new_dispatch_key(prefix: str) -> str:
    """Schlüssel für interne Aufrufer ohne Wiederholung (Aufgaben-Mail, direkte Aufrufe)."""
    return f"{prefix}-{uuid.uuid4().hex}"


def parse_recipients(text: str | None, *, label: str) -> list[str]:
    """Mehrere Adressen, getrennt durch Komma, Semikolon oder Zeilenumbruch. Doppelte (ohne
    Rücksicht auf Groß-/Kleinschreibung) fallen weg, die erste Schreibweise bleibt."""
    result: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;\n\r]+", text or ""):
        address = part.strip()
        if not address:
            continue
        if not _ADDRESS_RE.match(address):
            raise ValueError(f"{label}: „{address}“ ist keine gültige E-Mail-Adresse.")
        if address.lower() not in seen:
            seen.add(address.lower())
            result.append(address)
    return result


def _error_info(exc: BaseException) -> tuple[str, str | None]:
    """Klassenname und Code der innersten Ursache -- nie ihr Text (Regel 18)."""
    root = exc
    while root.__cause__ is not None:
        root = root.__cause__
    code = getattr(root, "code", None)
    if code is None:
        code = getattr(root, "smtp_code", None)
    return type(root).__name__[:120], (str(code)[:20] if isinstance(code, int) else None)


def _finish(db: Session, dispatch_id: int, status: str, exc: BaseException | None = None) -> None:
    error_class, error_code = _error_info(exc) if exc is not None else (None, None)
    db.execute(
        update(EmailDispatch)
        .where(EmailDispatch.id == dispatch_id, EmailDispatch.status == "in_arbeit")
        .values(status=status, finished_at=datetime.utcnow(), error_class=error_class, error_code=error_code)
        .execution_options(synchronize_session=False)
    )
    db.commit()


def _key_taken(db: Session, key: str) -> bool:
    """Vorabprüfung; die eigentliche Sperre ist der Unique-Schlüssel beim Anlegen (gleichzeitige
    Anfragen sehen hier beide "frei")."""
    return db.scalar(select(EmailDispatch.id).where(EmailDispatch.dispatch_key == key)) is not None


def _existing(db: Session, key: str, document_type: str, document_id: int | None) -> DispatchResult:
    existing = db.scalar(select(EmailDispatch).where(EmailDispatch.dispatch_key == key))
    if existing.document_type != document_type or existing.document_id != document_id:
        raise ValueError("Dieser Versandschlüssel gehört zu einem anderen Versand. Bitte die Seite neu laden.")
    if existing.status == "gesendet":
        return DispatchResult(existing, False)
    if existing.status == "in_arbeit":
        raise DispatchConflict(
            "Dieser Versand läuft bereits. Bitte das Ergebnis abwarten und im Versandprotokoll prüfen -- "
            "er wird nicht ein zweites Mal gesendet."
        )
    raise DispatchConflict(
        "Dieser Versandauftrag ist fehlgeschlagen und wird nicht wiederholt. "
        "Für einen neuen Versuch bitte erneut auf Senden klicken."
    )


def dispatch_email(
    db: Session, *, dispatch_key: str, document_type: str, document_id: int | None,
    document_number: str | None, to: str | None, cc: str | None, subject: str, body_text: str,
    attachment_bytes: bytes | None = None, attachment_filename: str | None = None,
    user_id: int | None = None, user_name: str | None = None, block_parallel: bool = True,
) -> DispatchResult:
    """Siehe Moduldocstring. Wirft ValueError (Eingabe/Konfiguration/Versandfehler, Router 400)
    und DispatchConflict (Router 409). Committet selbst."""
    if document_type not in DISPATCH_TYPES:
        raise ValueError(f"Unbekannte Versandart: {document_type}")
    key = (dispatch_key or "").strip()
    if not _KEY_RE.match(key):
        raise ValueError("Ungültiger Versandschlüssel. Bitte die Seite neu laden.")
    if (attachment_bytes is None) != (attachment_filename is None):
        raise ValueError("Anhang und Dateiname gehören zusammen.")
    if attachment_bytes is not None and document_type not in DOCUMENT_TYPES:
        raise ValueError("Nur Dokumente werden mit Anhang versendet.")
    if _key_taken(db, key):
        return _existing(db, key, document_type, document_id)

    to_list = parse_recipients(to, label="Empfänger")
    if not to_list:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")
    cc_list = [a for a in parse_recipients(cc, label="CC") if a.lower() not in {t.lower() for t in to_list}]
    if len(to_list) + len(cc_list) > MAX_RECIPIENTS:
        raise ValueError(f"Höchstens {MAX_RECIPIENTS} Empfänger (An und CC zusammen) je Versand.")
    settings = get_or_create_smtp_settings(db)
    ensure_configured(settings)
    check_attachment_size(attachment_bytes, attachment_filename)
    if block_parallel and document_id is not None:
        running = db.scalar(
            select(EmailDispatch).where(
                EmailDispatch.document_type == document_type, EmailDispatch.document_id == document_id,
                EmailDispatch.status == "in_arbeit", EmailDispatch.created_at >= datetime.utcnow() - STUCK_AFTER,
            ).limit(1)
        )
        if running is not None:
            raise DispatchConflict(
                "Für dieses Dokument läuft gerade ein anderer Versand. Bitte das Ergebnis abwarten und im "
                "Versandprotokoll prüfen, bevor erneut gesendet wird."
            )

    if user_id is None and user_name is None:
        from .audit import current_actor
        user_id, user_name = current_actor()
    dispatch = EmailDispatch(
        dispatch_key=key, message_ref=str(uuid.uuid4()), status="in_arbeit", channel=settings.send_method,
        document_type=document_type, document_id=document_id, document_number=document_number,
        to_recipients=", ".join(to_list), cc_recipients=", ".join(cc_list) or None, subject=subject,
        created_at=datetime.utcnow(), created_by_user_id=user_id, created_by_name=user_name or "System",
    )
    try:
        with db.begin_nested():
            db.add(dispatch)
            db.flush()
    except IntegrityError:
        # Gleichzeitige Anfrage mit demselben Schlüssel war schneller.
        return _existing(db, key, document_type, document_id)
    db.commit()
    dispatch_id = dispatch.id

    if attachment_bytes is not None:
        try:
            archived = store_sent_document(
                db, document_type=document_type, document_id=document_id, document_number=document_number,
                filename=attachment_filename, content=attachment_bytes, user_id=user_id,
                user_name=user_name or "System",
            )
            dispatch.sent_document_id = archived.id
            db.commit()
        except Exception as e:
            db.rollback()
            _finish(db, dispatch_id, "fehlgeschlagen", e)
            raise ValueError("Das Dokument konnte nicht in der Ablage gespeichert werden -- es wurde nichts versendet.") from e

    try:
        send_message(
            settings, to=to_list, cc=cc_list, subject=subject, body_text=body_text,
            attachment_bytes=attachment_bytes, attachment_filename=attachment_filename,
            headers={HEADER_NAME: dispatch.message_ref},
        )
    except Exception as e:
        _finish(db, dispatch_id, "fehlgeschlagen", e)
        raise
    _finish(db, dispatch_id, "gesendet")
    db.refresh(dispatch)
    return DispatchResult(dispatch, True)


def actor_of(user) -> tuple[int | None, str | None]:
    """(ID, Anzeigename) eines AppUser für dispatch_email(); None -> aus der laufenden Anfrage."""
    if user is None:
        return None, None
    return user.id, (user.display_name or user.username or "System")


def mark_document_sent(db: Session, document, result: DispatchResult) -> None:
    """email_sent_at/email_sent_to am Dokument (Angebot, Auftrag, Rechnung, Mahnung) -- nur bei
    einem tatsächlich neuen Versand; die Wiederholung eines gesendeten Schlüssels ändert nichts.
    email_sent_to trägt die An-Empfänger (auf die Spaltenlänge gekürzt), CC steht im Protokoll."""
    if result.newly_sent:
        document.email_sent_at = result.dispatch.finished_at or datetime.utcnow()
        document.email_sent_to = result.dispatch.to_recipients[:255]
        db.commit()
    db.refresh(document)


def is_stuck(dispatch: EmailDispatch, now: datetime | None = None) -> bool:
    return dispatch.status == "in_arbeit" and dispatch.created_at < (now or datetime.utcnow()) - STUCK_AFTER


def dispatch_to_dict(dispatch: EmailDispatch, now: datetime | None = None) -> dict:
    from .berlin_time import to_berlin
    from .sent_documents import sent_document_to_dict

    return {
        "id": dispatch.id, "dispatch_key": dispatch.dispatch_key, "message_ref": dispatch.message_ref,
        "status": dispatch.status, "status_label": STATUSES.get(dispatch.status, dispatch.status),
        "stuck": is_stuck(dispatch, now), "channel": dispatch.channel,
        "channel_label": CHANNELS.get(dispatch.channel, dispatch.channel),
        "document_type": dispatch.document_type,
        "document_type_label": DISPATCH_TYPES.get(dispatch.document_type, dispatch.document_type),
        "document_id": dispatch.document_id, "document_number": dispatch.document_number,
        "to_recipients": dispatch.to_recipients, "cc_recipients": dispatch.cc_recipients,
        "subject": dispatch.subject, "created_at": dispatch.created_at,
        "created_at_local": to_berlin(dispatch.created_at), "finished_at": dispatch.finished_at,
        "finished_at_local": to_berlin(dispatch.finished_at), "created_by_name": dispatch.created_by_name,
        "error_class": dispatch.error_class, "error_code": dispatch.error_code,
        "sent_document": sent_document_to_dict(dispatch.sent_document) if dispatch.sent_document else None,
    }


def list_dispatches(
    db: Session, *, status: str | None = None, document_type: str | None = None,
    document_id: int | None = None, stuck_only: bool = False, include_task_mails: bool = False,
    limit: int = 200,
) -> dict:
    """Neueste zuerst, höchstens `limit`. Hängengebliebene werden zusätzlich immer vollständig
    gezählt (stuck_count), damit die Seite sie auch jenseits des Ausschnitts meldet."""
    now = datetime.utcnow()
    query = select(EmailDispatch)
    stuck_query = select(func.count(EmailDispatch.id)).where(
        EmailDispatch.status == "in_arbeit", EmailDispatch.created_at < now - STUCK_AFTER,
    )
    if not include_task_mails:
        query = query.where(EmailDispatch.document_type != "aufgabe")
        stuck_query = stuck_query.where(EmailDispatch.document_type != "aufgabe")
    if status:
        query = query.where(EmailDispatch.status == status)
    if document_type:
        query = query.where(EmailDispatch.document_type == document_type)
    if document_id is not None:
        query = query.where(EmailDispatch.document_id == document_id)
    if stuck_only:
        query = query.where(EmailDispatch.status == "in_arbeit", EmailDispatch.created_at < now - STUCK_AFTER)
    rows = db.scalars(query.order_by(EmailDispatch.created_at.desc(), EmailDispatch.id.desc()).limit(limit)).all()
    stuck_count = db.scalar(stuck_query) or 0
    return {"items": [dispatch_to_dict(r, now) for r in rows], "stuck_count": stuck_count,
            "stuck_after_minutes": int(STUCK_AFTER.total_seconds() // 60)}
