"""Versandprotokoll und Sperre gegen Doppelversand (seit 1.8.17, Stufe 2, Runde 2a-3a; Sperre je
Dokument, Klärung hängender Einträge und Versand der abgelegten Fassung seit 1.8.19, Runde 2a-3b).

dispatch_email() ist der einzige Weg, eine E-Mail zu versenden (app/email_sending.py::
send_message() hat keinen anderen Aufrufer, per Test erzwungen). Ablauf je Versandauftrag:

1. Schlüssel prüfen: Jeder Versandauftrag trägt einen Schlüssel (dispatch_key, von der Seite je
   Klick erzeugt). Gibt es ihn schon, wird nie ein zweites Mal gesendet: "gesendet" liefert den
   vorhandenen Eintrag zurück (eine wiederholte Anfrage bekommt dieselbe Antwort), "in_arbeit"
   und "fehlgeschlagen" werden mit DispatchConflict (409) abgelehnt -- ein neuer Versuch ist ein
   neuer Klick mit neuem Schlüssel.
2. Vorab prüfen, ohne etwas zu schreiben: Empfänger (jede Adresse einzeln, parse_recipients()),
   Konfiguration, Anhanggröße (3 MB), und ob für dasselbe Dokument gerade ein anderer Versand läuft
   (in_arbeit, jünger als STUCK_AFTER) -- das ergibt die verständliche Meldung im Normalfall.
3. Eintrag "in_arbeit" anlegen und committen -- VOR dem Senden. Zwei Unique-Schlüssel entscheiden
   dabei in der Datenbank, nicht im Code: dispatch_key (derselbe Klick zweimal) und lock_key
   ("<art>:<id>" -- zwei Tabs, die dasselbe Dokument in derselben Sekunde senden; beide bestehen
   die Vorabprüfung, die Datenbank legt genau einen an, der andere bekommt 409). Bricht der Prozess
   danach ab, bleibt der Eintrag "in_arbeit" stehen und erscheint nach STUCK_AFTER als
   hängengeblieben; seine Sperre gilt dann nicht mehr (ein neuer Versand gibt sie frei). Er wird
   nie automatisch erneut gesendet: ob die Mail hinausging, weiß nur der Postausgang -- das Büro
   klärt ihn mit Notiz (resolve_stuck_dispatch()).
4. PDF in die Ablage (app/sent_documents.py), Verweis am Eintrag, commit. Scheitert das Ablegen,
   wird nicht gesendet. Ist das PDF schon die abgelegte Fassung (Rechnung/Storno/Mahnung nach dem
   ersten Versand, archived_document), wird nur verwiesen, nicht noch einmal abgelegt. Seit 1.8.40
   kann der Aufrufer hier weitere Nachweise zum Versand ablegen (before_send, z. B. die Vollmacht
   eines empfangsbevollmächtigten Empfängers, app/notice_letters.py) -- ebenfalls vor dem Senden,
   scheitert es, wird nicht gesendet.
5. Senden mit der eigenen Kennung als Kopfzeile X-DK-Versand-ID, danach "gesendet" bzw.
   "fehlgeschlagen" per bedingtem UPDATE (nur aus "in_arbeit"), Sperre frei.

Zustellung auf anderem Weg (seit 1.8.20, record_manual_delivery()): Einschreiben, persönliche
Übergabe, Bote oder Fax trägt das Büro mit Datum, Notiz und optional einem Beleg (Foto/Scan) nach.
Das ist ein Eintrag im selben Protokoll (channel = Weg, sofort "gesendet"), das PDF des Dokuments und
der Beleg liegen in der Ablage. Gesendet wird dabei nichts. Seit 1.8.41 mit Empfängerauswahl
(delivery_recipients(): Auftraggeber und Beteiligte des Projekts, auch ohne E-Mail); geht sie an einen
empfangsbevollmächtigten Beteiligten, wird seine Vollmacht wie beim E-Mail-Versand eingefroren
(freeze_authorization()).

Was danach bekannt wird (seit 1.8.41, record_dispatch_outcome()): "Empfang bestätigt am" (Datum, Notiz,
optional Beleg) oder "unzustellbar" (Datum, Pflicht-Notiz) -- höchstens eines je Eintrag (DispatchOutcome,
UNIQUE), danach unveränderlich, für jede Dokumentart, nie für Aufgaben-Benachrichtigungen.

Regel 18: im Protokoll stehen Empfänger und Betreff (vom Betreiber für den Nachweis verlangt), nie
der Mailtext und nie der Fehlertext -- vom Fehler nur Klassenname und Code (HTTP-Status bzw.
SMTP-Antwortcode). Der Fehlertext geht wie bisher nur an den Menschen, der gerade sendet. Die
Notizen einer Klärung und einer nachgetragenen Zustellung schreibt das Büro selbst, sie sind
Nachweis, kein Mitschnitt.
"""

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from io import BytesIO

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .email_sending import check_attachment_size, ensure_configured, load_smtp_settings, send_message
from .models import DispatchAuthorization, DispatchOutcome, EmailDispatch, ProjectParticipant, SentDocument
from .sent_documents import DOCUMENT_TYPES, store_sent_document

HEADER_NAME = "X-DK-Versand-ID"
STUCK_AFTER = timedelta(minutes=10)
MAX_RECIPIENTS = 20
STATUSES = {"in_arbeit": "In Arbeit", "gesendet": "Gesendet", "fehlgeschlagen": "Fehlgeschlagen"}
RESOLUTION_OUTCOMES = ("gesendet", "fehlgeschlagen")
RESOLUTION_NOTE_MAX = 1000
MANUAL_CHANNELS = {"einschreiben": "Einschreiben", "persoenlich": "Persönliche Übergabe", "bote": "Bote", "fax": "Fax"}
CHANNELS = {"smtp": "SMTP", "graph_oauth2": "Microsoft 365", **MANUAL_CHANNELS}
MAX_RECEIPT_BYTES = 15_000_000  # Beleg einer nachgetragenen Zustellung (Foto vom Handy, Scan)
DELIVERY_NOTE_MAX = 1000
DISPATCH_TYPES = {**DOCUMENT_TYPES, "aufgabe": "Aufgaben-Benachrichtigung"}
DISPATCH_ENTITY_TYPE = "Versand"  # Änderungshistorie (app/audit.py) für die Klärung eines Eintrags
# Versandergebnis (seit 1.8.41, record_dispatch_outcome())
OUTCOMES = {"empfangen": "Empfang bestätigt", "unzustellbar": "Unzustellbar"}
OUTCOME_NOTE_MAX = 1000
RECIPIENT_TEXT_MAX = 300

RUNNING_TEXT = (
    "Für dieses Dokument läuft gerade ein anderer Versand. Bitte das Ergebnis abwarten und im "
    "Versandprotokoll prüfen, bevor erneut gesendet wird."
)

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,79}$")
# Adressprüfung (seit 1.8.19 strenger): Teil vor dem @ als "dot-atom" (keine Punkte am Rand oder
# doppelt), Teil nach dem @ aus Labels mit Buchstaben/Ziffern/Bindestrich (nicht am Rand), Endung aus
# Buchstaben (oder IDN "xn--"). Bis 1.8.18 ging z. B. "kunde@firma..de" durch und erst Microsoft 365
# lehnte ab (ErrorInvalidRecipients) -- nach Protokolleintrag und Ablage.
_LOCAL_CHAR = r"[\w!#$%&'*+/=?^`{|}~-]"
_LOCAL_RE = re.compile(rf"^{_LOCAL_CHAR}+(?:\.{_LOCAL_CHAR}+)*$")
_LABEL_RE = re.compile(r"^(?!-)(?:[^\W_]|-){1,63}(?<!-)$")
_TLD_RE = re.compile(r"^(?:[^\W\d_]{2,63}|xn--[a-z0-9-]{1,59})$", re.IGNORECASE)
_NAMED_RE = re.compile(r"^[^<>]*<([^<>]*)>$")
_SEPARATOR_HINT = "mehrere Adressen bitte mit Komma oder Semikolon trennen"


class DispatchConflict(Exception):
    """Dieser Versandauftrag wird nicht (noch einmal) gesendet -- Router: 409."""


@dataclass
class DispatchResult:
    dispatch: EmailDispatch
    newly_sent: bool  # False: derselbe Schlüssel war schon gesendet, nichts hinausgegangen


def new_dispatch_key(prefix: str) -> str:
    """Schlüssel für interne Aufrufer ohne Wiederholung (Aufgaben-Mail, direkte Aufrufe)."""
    return f"{prefix}-{uuid.uuid4().hex}"


def address_problem(address: str) -> str | None:
    """Warum `address` keine gültige E-Mail-Adresse ist (für die Meldung), sonst None."""
    if any(c.isspace() for c in address):
        return f"sie enthält ein Leerzeichen ({_SEPARATOR_HINT})"
    if "@" not in address:
        return "es fehlt das @"
    if address.count("@") > 1:
        return f"sie enthält mehr als ein @ ({_SEPARATOR_HINT})"
    local, domain = address.split("@")
    if len(address) > 254 or len(local) > 64:
        return "sie ist zu lang"
    if not _LOCAL_RE.match(local):
        return ("der Teil vor dem @ ist ungültig (z. B. ein Punkt am Anfang oder Ende, zwei Punkte "
                "hintereinander oder ein Sonderzeichen)")
    labels = domain.split(".")
    if len(labels) < 2:
        return "nach dem @ fehlt die Endung (z. B. .de)"
    if not all(_LABEL_RE.match(label) for label in labels):
        return ("der Teil nach dem @ ist ungültig (z. B. zwei Punkte hintereinander, ein Punkt am Ende, "
                "ein Bindestrich am Rand oder ein Sonderzeichen)")
    if not _TLD_RE.match(labels[-1]):
        return f"die Endung „.{labels[-1]}“ gibt es nicht"
    return None


def parse_recipients(text: str | None, *, label: str) -> list[str]:
    """Mehrere Adressen, getrennt durch Komma, Semikolon oder Zeilenumbruch; "Name <adresse>" wird
    auf die Adresse gekürzt. Jede Adresse wird geprüft, die erste ungültige mit Grund gemeldet.
    Doppelte (ohne Rücksicht auf Groß-/Kleinschreibung) fallen weg, die erste Schreibweise bleibt."""
    result: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;\n\r]+", text or ""):
        address = part.strip()
        if not address:
            continue
        named = _NAMED_RE.match(address)
        if named:
            address = named.group(1).strip()
        problem = address_problem(address)
        if problem:
            raise ValueError(f"{label}: „{address}“ ist keine gültige E-Mail-Adresse – {problem}.")
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
        .values(status=status, finished_at=datetime.utcnow(), error_class=error_class, error_code=error_code,
                lock_key=None)
        .execution_options(synchronize_session=False)
    )
    db.commit()


def _key_taken(db: Session, key: str) -> bool:
    """Vorabprüfung; die eigentliche Sperre ist der Unique-Schlüssel beim Anlegen (gleichzeitige
    Anfragen sehen hier beide "frei")."""
    return db.scalar(select(EmailDispatch.id).where(EmailDispatch.dispatch_key == key)) is not None


def _lock_key(document_type: str, document_id: int) -> str:
    return f"{document_type}:{document_id}"


def _running_dispatch(db: Session, document_type: str, document_id: int) -> EmailDispatch | None:
    """Vorabprüfung "läuft gerade" (für die Meldung im Normalfall); zwei gleichzeitige Anfragen
    sehen hier beide nichts -- dann entscheidet lock_key beim Anlegen."""
    return db.scalar(
        select(EmailDispatch).where(
            EmailDispatch.document_type == document_type, EmailDispatch.document_id == document_id,
            EmailDispatch.status == "in_arbeit", EmailDispatch.created_at >= datetime.utcnow() - STUCK_AFTER,
        ).limit(1)
    )


def _release_stale_lock(db: Session, lock_key: str, now: datetime) -> None:
    """Ein hängengebliebener Versand (älter als STUCK_AFTER) hält die Sperre nicht mehr: er bleibt
    "in Arbeit" und im Protokoll als hängend sichtbar, blockiert aber keinen neuen Versand des
    Dokuments (wie seit 1.8.17). Committet nicht -- gehört in die Transaktion des neuen Eintrags."""
    db.execute(
        update(EmailDispatch)
        .where(EmailDispatch.lock_key == lock_key, EmailDispatch.status == "in_arbeit",
               EmailDispatch.created_at < now - STUCK_AFTER)
        .values(lock_key=None)
        .execution_options(synchronize_session=False)
    )


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
    archived_document: SentDocument | None = None,
    user_id: int | None = None, user_name: str | None = None, block_parallel: bool = True,
    before_send: Callable[[Session, EmailDispatch], None] | None = None,
) -> DispatchResult:
    """Siehe Moduldocstring. Wirft ValueError (Eingabe/Konfiguration/Versandfehler, Router 400)
    und DispatchConflict (Router 409). Committet selbst.

    archived_document: der Anhang IST diese abgelegte Fassung (app/sent_documents.py::
    frozen_or_fresh_pdf()) -- dann wird nur auf sie verwiesen, nicht noch einmal abgelegt.

    before_send (seit 1.8.40): läuft nach dem Ablegen des PDFs und vor dem Senden, mit dem Eintrag
    (Empfänger schon geprüft und entdoppelt) -- für weitere Nachweise in der Ablage. Er committet
    nicht; scheitert er, wird nichts gesendet. Eine Wiederholung desselben Schlüssels ruft ihn nicht. Seit 1.8.67 auch für
    eine letzte Prüfung (Abnahmeprotokoll: Fassung noch gültig) -- ein ValueError von ihm geht mit seinem Text weiter."""
    if document_type not in DISPATCH_TYPES:
        raise ValueError(f"Unbekannte Versandart: {document_type}")
    key = (dispatch_key or "").strip()
    if not _KEY_RE.match(key):
        raise ValueError("Ungültiger Versandschlüssel. Bitte die Seite neu laden.")
    if (attachment_bytes is None) != (attachment_filename is None):
        raise ValueError("Anhang und Dateiname gehören zusammen.")
    if attachment_bytes is not None and document_type not in DOCUMENT_TYPES:
        raise ValueError("Nur Dokumente werden mit Anhang versendet.")
    if archived_document is not None and (
        attachment_bytes is None
        or (archived_document.document_type, archived_document.document_id) != (document_type, document_id)
        or hashlib.sha256(attachment_bytes).hexdigest() != archived_document.sha256
    ):
        raise ValueError("Der Anhang ist nicht die abgelegte Fassung dieses Dokuments -- es wurde nichts versendet.")
    if _key_taken(db, key):
        return _existing(db, key, document_type, document_id)

    to_list = parse_recipients(to, label="Empfänger")
    if not to_list:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")
    cc_list = [a for a in parse_recipients(cc, label="CC") if a.lower() not in {t.lower() for t in to_list}]
    if len(to_list) + len(cc_list) > MAX_RECIPIENTS:
        raise ValueError(f"Höchstens {MAX_RECIPIENTS} Empfänger (An und CC zusammen) je Versand.")
    settings = load_smtp_settings(db)
    ensure_configured(settings)
    check_attachment_size(attachment_bytes, attachment_filename)
    lock_key = _lock_key(document_type, document_id) if block_parallel and document_id is not None else None
    if lock_key is not None and _running_dispatch(db, document_type, document_id) is not None:
        raise DispatchConflict(RUNNING_TEXT)

    if user_id is None and user_name is None:
        from .audit import current_actor
        user_id, user_name = current_actor()
    now = datetime.utcnow()
    if lock_key is not None:
        _release_stale_lock(db, lock_key, now)
    dispatch = EmailDispatch(
        dispatch_key=key, message_ref=str(uuid.uuid4()), status="in_arbeit", channel=settings.send_method,
        document_type=document_type, document_id=document_id, document_number=document_number,
        to_recipients=", ".join(to_list), cc_recipients=", ".join(cc_list) or None, subject=subject,
        sent_document_id=archived_document.id if archived_document is not None else None,
        created_at=now, created_by_user_id=user_id, created_by_name=user_name or "System", lock_key=lock_key,
    )
    try:
        with db.begin_nested():
            db.add(dispatch)
            db.flush()
    except IntegrityError:
        # Welcher Unique-Schlüssel hat gegriffen? (Bewusst nicht _key_taken(): das ist die
        # Vorabprüfung, dies hier die Entscheidung.)
        if db.scalar(select(EmailDispatch.id).where(EmailDispatch.dispatch_key == key)) is not None:
            return _existing(db, key, document_type, document_id)  # derselbe Klick war schneller
        db.rollback()  # lock_key: ein anderer Versand desselben Dokuments ist gerade angelegt worden
        raise DispatchConflict(RUNNING_TEXT)
    db.commit()
    dispatch_id = dispatch.id

    if attachment_bytes is not None and archived_document is None:
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

    if before_send is not None:
        try:
            before_send(db, dispatch)
            db.commit()
        except Exception as e:
            db.rollback()
            _finish(db, dispatch_id, "fehlgeschlagen", e)
            if isinstance(e, ValueError):  # seit 1.8.67: eine Prüfung vor dem Senden sagt selbst, warum (Fassung überholt)
                raise ValueError(str(e)) from e
            raise ValueError("Die Nachweise zum Versand konnten nicht in der Ablage gespeichert werden -- "
                             "es wurde nichts versendet.") from e

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


def _dispatch_label(dispatch: EmailDispatch) -> str:
    """Bezeichnung für die Änderungshistorie -- Art, Nummer, Kennung; nie Betreff oder Empfänger."""
    kind = DISPATCH_TYPES.get(dispatch.document_type, dispatch.document_type)
    number = dispatch.document_number or (f"#{dispatch.document_id}" if dispatch.document_id else None)
    return " ".join(x for x in (kind, number, f"· Kennung {dispatch.message_ref}") if x)


def resolve_stuck_dispatch(
    db: Session, dispatch_id: int, *, outcome: str, note: str, user_id: int | None, user_name: str | None,
) -> EmailDispatch:
    """Das Büro klärt einen hängengebliebenen Eintrag (seit 1.8.19): nach Blick in den Postausgang
    als "gesendet" oder "fehlgeschlagen", mit Pflicht-Notiz. Nur aus "in_arbeit" und erst nach
    STUCK_AFTER (vorher läuft der Versand womöglich noch) -- bedingtes UPDATE, zwei gleichzeitige
    Klärungen: genau eine gewinnt. Gesendet wird dabei nichts. Die Klärung steht am Eintrag (wer,
    wann, Notiz) und in der Änderungshistorie. Wirft LookupError (404), ValueError (400),
    DispatchConflict (409)."""
    if outcome not in RESOLUTION_OUTCOMES:
        raise ValueError("Bitte „gesendet“ oder „fehlgeschlagen“ wählen.")
    note = (note or "").strip()
    if len(note) < 3:
        raise ValueError("Bitte in der Notiz festhalten, wie geklärt wurde (z. B. „in Gesendete Elemente gefunden“).")
    if len(note) > RESOLUTION_NOTE_MAX:
        raise ValueError(f"Die Notiz ist zu lang (höchstens {RESOLUTION_NOTE_MAX} Zeichen).")
    dispatch = db.get(EmailDispatch, dispatch_id)
    if dispatch is None:
        raise LookupError("Protokolleintrag nicht gefunden.")
    now = datetime.utcnow()
    if dispatch.status != "in_arbeit":
        raise DispatchConflict(f"Dieser Eintrag ist bereits abgeschlossen ({STATUSES.get(dispatch.status, dispatch.status)}).")
    if not is_stuck(dispatch, now):
        raise DispatchConflict(
            f"Dieser Versand läuft womöglich noch (seit weniger als {int(STUCK_AFTER.total_seconds() // 60)} Minuten). "
            "Bitte das Ergebnis abwarten."
        )
    claimed = db.execute(
        update(EmailDispatch)
        .where(EmailDispatch.id == dispatch_id, EmailDispatch.status == "in_arbeit",
               EmailDispatch.created_at < now - STUCK_AFTER)
        .values(status=outcome, resolved_at=now, resolved_by_user_id=user_id,
                resolved_by_name=user_name or "System", resolution_note=note, lock_key=None)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise DispatchConflict("Diesen Eintrag hat inzwischen jemand anderes geklärt.")
    from .audit import TASK_ENTITY_TYPE, record_audit_entry
    from .dispatch_documents import project_id_of

    if dispatch.document_type == "aufgabe":
        # Wie das Übernehmen einer Aufgabe (1.8.18): an der Aufgabe, damit nur Admin es sieht.
        entity = dict(entity_type=TASK_ENTITY_TYPE, entity_id=dispatch.document_id,
                      entity_label=f"Nr. {dispatch.document_id} · Benachrichtigung {dispatch.message_ref}")
    else:
        entity = dict(entity_type=DISPATCH_ENTITY_TYPE, entity_id=dispatch.id, entity_label=_dispatch_label(dispatch))
    record_audit_entry(
        db, action="geändert", **entity, project_id=project_id_of(db, dispatch.document_type, dispatch.document_id),
        field_name="status",
        field_label="Versandstatus (hängenden Versand geklärt)", old_value="Hängengeblieben (in Arbeit)",
        new_value=f"{STATUSES[outcome]} – Notiz: {note}", actor_user_id=user_id, actor_name=user_name or "System",
    )
    db.commit()
    db.refresh(dispatch)
    return dispatch


def receipt_content_type(content: bytes) -> str:
    """Beleg am Inhalt erkennen, nicht am Dateinamen oder an der Angabe des Browsers: JPEG, PNG,
    WebP (von Pillow vollständig gelesen) oder PDF. Alles andere (auch SVG/HTML) wird abgelehnt.
    Seit 1.8.34 auch für den Scan eines unterschriebenen Vertrags (app/contract_signatures.py)."""
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(BytesIO(content)) as im:
            fmt = im.format
            im.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        fmt = None
    types = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    if fmt not in types:
        raise ValueError("Der Beleg muss ein Foto (JPEG, PNG, WebP) oder ein PDF sein.")
    return types[fmt]


def _safe_filename(name: str | None, content_type: str) -> str:
    from .sent_documents import CONTENT_TYPE_SUFFIXES

    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", (name or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).strip(" ._")[:100]
    suffix = CONTENT_TYPE_SUFFIXES[content_type]
    stem = stem[: -len(suffix)] if stem.lower().endswith(suffix) else stem
    return f"{stem or 'Beleg'}{suffix}"


def _client_of_project(db: Session, project_id: int | None):
    from .models import Project

    project = db.get(Project, project_id) if project_id is not None else None
    return project.customer if project is not None else None


def delivery_recipients(db: Session, document_type: str, document_id: int) -> dict:
    """Empfängerauswahl für "Zustellung nachtragen" (seit 1.8.41): der Auftraggeber (Kunde des Projekts, Anschrift
    live aus dem Kundenstamm) und die Beteiligten des Projekts -- auch ohne E-Mail, archivierte Kontakte
    gekennzeichnet. Ohne Projekt (z. B. Checkliste am Objekt) leer: dann nur die freie Empfängerangabe.
    LookupError: unbekannte Art oder Dokument fehlt."""
    from .dispatch_documents import document_row, project_id_of
    from .project_participants import participant_info, participant_rows

    if document_row(db, document_type, document_id) is None:
        raise LookupError("Dokument nicht gefunden.")
    project_id = project_id_of(db, document_type, document_id)
    customer = _client_of_project(db, project_id)
    client = None
    if customer is not None:
        address = ", ".join(x for x in (customer.street, " ".join(y for y in (customer.postal_code, customer.city) if y)) if x)
        client = {"customer_id": customer.id, "name": customer.name, "address": address or None}
    participants = []
    if project_id is not None:
        for p in participant_rows(db, project_id):
            info = participant_info(p)
            participants.append({key: info[key] for key in (
                "participant_id", "name", "role", "role_label", "authorized", "has_poa", "archived", "email")})
    return {"project_id": project_id, "client": client, "participants": participants}


def record_manual_delivery(
    db: Session, *, dispatch_key: str, document_type: str, document_id: int, channel: str, delivered_on: date,
    note: str, recipient: str | None = None, receipt_bytes: bytes | None = None, receipt_filename: str | None = None,
    user_id: int | None = None, user_name: str | None = None, to_client: bool = False,
    participant_ids: list[int] | None = None,
) -> DispatchResult:
    """Zustellung auf anderem Weg nachtragen (seit 1.8.20): Eintrag im Protokoll (Weg, Datum, Notiz,
    optional Empfänger), das PDF des Dokuments und der Beleg in die Ablage -- in einer Transaktion.
    Derselbe Schlüssel wird nie zweimal eingetragen (Wiederholung liefert den Eintrag zurück).
    Wirft LookupError (404), ValueError (400).

    Seit 1.8.41 Empfängerauswahl: to_client (der Auftraggeber) und participant_ids (Beteiligte DIESES Projekts),
    dazu weiterhin die freie Angabe recipient. Die Empfänger stehen als Text im Eintrag ("Name (Rolle)"),
    delivered_to_client hält fest, ob der Auftraggeber dabei war (leer, wenn niemand gewählt wurde -- wie vor
    1.8.41). Je gewähltem empfangsbevollmächtigtem Beteiligten wird seine Vollmacht in derselben Transaktion
    eingefroren (freeze_authorization(), auch ohne E-Mail-Adresse)."""
    from .berlin_time import berlin_today
    from .dispatch_documents import dispatch_document
    from .sent_documents import ArchiveFileError

    if channel not in MANUAL_CHANNELS:
        raise ValueError("Bitte den Weg wählen: Einschreiben, persönliche Übergabe, Bote oder Fax.")
    key = (dispatch_key or "").strip()
    if not _KEY_RE.match(key):
        raise ValueError("Ungültiger Versandschlüssel. Bitte die Seite neu laden.")
    note = (note or "").strip()
    if len(note) < 3:
        raise ValueError("Bitte in der Notiz festhalten, wie zugestellt wurde (z. B. Sendungsnummer, an wen übergeben).")
    if len(note) > DELIVERY_NOTE_MAX:
        raise ValueError(f"Die Notiz ist zu lang (höchstens {DELIVERY_NOTE_MAX} Zeichen).")
    recipient = (recipient or "").strip()
    if len(recipient) > RECIPIENT_TEXT_MAX:
        raise ValueError(f"Die Empfängerangabe ist zu lang (höchstens {RECIPIENT_TEXT_MAX} Zeichen).")
    if delivered_on > berlin_today():
        raise ValueError("Das Zustelldatum liegt in der Zukunft.")
    if _key_taken(db, key):
        return _existing(db, key, document_type, document_id)
    document = dispatch_document(db, document_type, document_id)
    participant_ids = list(dict.fromkeys(participant_ids or []))
    chosen: list[ProjectParticipant] = []
    client = None
    if to_client or participant_ids:
        if document.project_id is None:
            raise ValueError("Dieses Dokument gehört zu keinem Projekt – bitte den Empfänger als Text angeben.")
        if to_client:
            client = _client_of_project(db, document.project_id)
            if client is None:
                raise ValueError("Das Projekt hat keinen Auftraggeber.")
        if participant_ids:
            from .project_participants import participant_rows

            by_id = {p.id: p for p in participant_rows(db, document.project_id)}
            if any(pid not in by_id for pid in participant_ids):
                raise ValueError("Ein gewählter Beteiligter gehört nicht zu diesem Projekt – bitte die Seite neu laden.")
            chosen = [by_id[pid] for pid in participant_ids]
    receipt_type = None
    if receipt_bytes:
        if len(receipt_bytes) > MAX_RECEIPT_BYTES:
            raise ValueError(f"Der Beleg ist größer als {MAX_RECEIPT_BYTES // 1_000_000} MB.")
        receipt_type = receipt_content_type(receipt_bytes)
    try:
        pdf = document.pdf()
    except ArchiveFileError as e:
        raise ValueError(f"Die versendete Fassung in der Ablage ist nicht mehr unversehrt: {e} "
                         "Bitte im Versandprotokoll prüfen.") from e

    if user_id is None and user_name is None:
        from .audit import current_actor
        user_id, user_name = current_actor()
    user_name = user_name or "System"
    archived = pdf.archived or store_sent_document(
        db, document_type=document_type, document_id=document_id, document_number=document.number,
        filename=pdf.filename, content=pdf.content, user_id=user_id, user_name=user_name,
    )
    receipt = None
    if receipt_type is not None:
        receipt = store_sent_document(
            db, document_type=document_type, document_id=document_id, document_number=document.number,
            filename=_safe_filename(receipt_filename, receipt_type), content=receipt_bytes, user_id=user_id,
            user_name=user_name, content_type=receipt_type,
        )
    from .project_participants import participant_info

    names = ([f"{client.name} (Auftraggeber)"] if client is not None else []) + [
        f"{info['name']} ({info['role_label']})" for info in (participant_info(p) for p in chosen)]
    now = datetime.utcnow()
    dispatch = EmailDispatch(
        dispatch_key=key, message_ref=str(uuid.uuid4()), status="gesendet", channel=channel,
        document_type=document_type, document_id=document_id, document_number=document.number,
        to_recipients="; ".join(names + ([recipient] if recipient else [])),
        subject=f"{MANUAL_CHANNELS[channel]} – {document.label}",
        sent_document_id=archived.id, receipt_document_id=receipt.id if receipt else None,
        created_at=now, finished_at=now, created_by_user_id=user_id, created_by_name=user_name,
        delivered_on=delivered_on, delivery_note=note,
        delivered_to_client=(client is not None) if (client is not None or chosen) else None,
    )
    try:
        with db.begin_nested():
            db.add(dispatch)
            db.flush()
    except IntegrityError:
        # Gleichzeitige Anfrage mit demselben Schlüssel: alles zurück (die abgelegten Dateien bleiben
        # ohne Eintrag liegen -- die Ablage löscht nie), der andere Eintrag gilt.
        db.rollback()
        return _existing(db, key, document_type, document_id)
    for participant in chosen:
        if participant.authorized_recipient:
            freeze_authorization(db, dispatch, participant, recipient_email=None, user_id=user_id, user_name=user_name)
    db.flush()
    db.commit()
    db.refresh(dispatch)
    if document.after_delivery is not None:
        # Seit 1.8.40 (Behinderungsanzeige: Aufgabe "versenden" erledigt) -- nach dem Commit, der Eintrag gilt.
        document.after_delivery(dispatch)
        db.refresh(dispatch)
    return DispatchResult(dispatch, True)


def freeze_authorization(db: Session, dispatch: EmailDispatch, participant: ProjectParticipant, *,
                         recipient_email: str | None, user_id: int | None, user_name: str | None) -> DispatchAuthorization:
    """Die Empfangsvollmacht eines Beteiligten zum Versand festhalten (seit 1.8.40 beim E-Mail-Versand eines Briefs
    an den Auftraggeber, seit 1.8.41 hier gemeinsam, auch für eine nachgetragene Zustellung ohne E-Mail): die
    hinterlegte Vollmacht als Kopie in die Ablage (Art und Dokument wie der Versand; dieselbe Datei je Dokument nur
    einmal, sonst verwiesen) und eine DispatchAuthorization-Zeile. Eine fehlende oder veränderte Vollmacht-Datei
    hält nichts auf -- die Zeile sagt es dann (note). Committet nicht."""
    from .project_participants import participant_info, power_of_attorney_path
    from .sent_documents import CONTENT_TYPE_SUFFIXES

    info = participant_info(participant)
    document, note = None, None
    if not participant.poa_stored_filename:
        note = "Keine Vollmacht hinterlegt."
    else:
        try:
            data = power_of_attorney_path(participant.poa_stored_filename).read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            data = None
        if data is None or hashlib.sha256(data).hexdigest() != participant.poa_sha256 \
                or participant.poa_content_type not in CONTENT_TYPE_SUFFIXES:
            note = "Vollmacht-Datei fehlt oder passt nicht zu ihrer Prüfsumme – nicht festgehalten."
        else:
            document = db.scalar(select(SentDocument).where(
                SentDocument.document_type == dispatch.document_type, SentDocument.document_id == dispatch.document_id,
                SentDocument.sha256 == participant.poa_sha256).limit(1))
            if document is None:
                stem = re.sub(r"[^A-Za-z0-9_-]+", "_", f"Vollmacht_{info['name']}")[:80]
                document = store_sent_document(
                    db, document_type=dispatch.document_type, document_id=dispatch.document_id,
                    document_number=dispatch.document_number,
                    filename=f"{stem}{CONTENT_TYPE_SUFFIXES[participant.poa_content_type]}", content=data,
                    user_id=user_id, user_name=user_name or "System", content_type=participant.poa_content_type,
                )
    row = DispatchAuthorization(
        dispatch_id=dispatch.id, participant_id=participant.id, contact_name=info["name"][:255], role=participant.role,
        recipient_email=recipient_email[:255] if recipient_email else None,
        sent_document_id=document.id if document else None, poa_sha256=document.sha256 if document else None, note=note,
    )
    db.add(row)
    return row


def _dispatch_day(dispatch: EmailDispatch) -> date:
    """Tag des Versands: bei einer nachgetragenen Zustellung das Zustelldatum, sonst der Abschluss in Europe/Berlin."""
    from .berlin_time import to_berlin

    return dispatch.delivered_on or to_berlin(dispatch.finished_at or dispatch.created_at).date()


def record_dispatch_outcome(
    db: Session, dispatch_id: int, *, outcome: str, outcome_on: date, note: str | None,
    receipt_bytes: bytes | None = None, receipt_filename: str | None = None,
    user_id: int | None = None, user_name: str | None = None,
) -> DispatchOutcome:
    """"Empfang bestätigt am" bzw. "als unzustellbar markieren" (seit 1.8.41, Stufe 2b, Runde 2b-3 Teil 3) -- für
    jeden gesendeten Versand und jede nachgetragene Zustellung eines Dokuments, nie für eine
    Aufgaben-Benachrichtigung. Höchstens EIN Ergebnis je Eintrag (Festlegung: Empfang und Unzustellbarkeit schließen
    sich aus); Datum nicht in der Zukunft und nicht vor dem Versand; Notiz bei "unzustellbar" Pflicht; optional ein
    Beleg (Rückschein, Rückläufer, Lesebestätigung -- am Inhalt erkannt wie der Beleg einer Zustellung) in der Ablage.
    Zwei gleichzeitige Vermerke: der UNIQUE-Schlüssel lässt genau einen zu. Historie wie beim Klären. Danach der
    Nachlauf je Dokumentart (app/dispatch_documents.py::after_outcome(), Behinderungsanzeige: Aufgabe wieder offen).
    Wirft LookupError (404), ValueError (400), DispatchConflict (409)."""
    from .berlin_time import berlin_today

    if outcome not in OUTCOMES:
        raise ValueError("Bitte „Empfang bestätigt“ oder „unzustellbar“ wählen.")
    note = (note or "").strip()
    if outcome == "unzustellbar" and len(note) < 3:
        raise ValueError("Bitte in der Notiz festhalten, warum unzustellbar (z. B. „Rückläufer: Empfänger unbekannt verzogen“).")
    if len(note) > OUTCOME_NOTE_MAX:
        raise ValueError(f"Die Notiz ist zu lang (höchstens {OUTCOME_NOTE_MAX} Zeichen).")
    if outcome_on > berlin_today():
        raise ValueError("Das Datum liegt in der Zukunft.")
    dispatch = db.get(EmailDispatch, dispatch_id)
    if dispatch is None or dispatch.document_type not in DOCUMENT_TYPES:
        raise LookupError("Protokolleintrag nicht gefunden.")
    if dispatch.status != "gesendet":
        raise DispatchConflict("Empfang oder Unzustellbarkeit lässt sich nur zu einem gesendeten Versand bzw. einer "
                               f"nachgetragenen Zustellung vermerken (dieser Eintrag: {STATUSES.get(dispatch.status, dispatch.status)}).")
    day = _dispatch_day(dispatch)
    if outcome_on < day:
        raise ValueError(f"Das Datum liegt vor dem Versand ({day.strftime('%d.%m.%Y')}).")
    existing = db.scalar(select(DispatchOutcome).where(DispatchOutcome.dispatch_id == dispatch_id))
    if existing is not None:
        raise DispatchConflict(f"Zu diesem Versand ist bereits vermerkt: {OUTCOMES.get(existing.outcome, existing.outcome)} "
                               f"am {existing.outcome_on.strftime('%d.%m.%Y')}.")
    receipt_type = None
    if receipt_bytes:
        if len(receipt_bytes) > MAX_RECEIPT_BYTES:
            raise ValueError(f"Der Beleg ist größer als {MAX_RECEIPT_BYTES // 1_000_000} MB.")
        receipt_type = receipt_content_type(receipt_bytes)
    if user_id is None and user_name is None:
        from .audit import current_actor
        user_id, user_name = current_actor()
    user_name = user_name or "System"
    receipt = None
    if receipt_type is not None:
        receipt = store_sent_document(
            db, document_type=dispatch.document_type, document_id=dispatch.document_id,
            document_number=dispatch.document_number, filename=_safe_filename(receipt_filename, receipt_type),
            content=receipt_bytes, user_id=user_id, user_name=user_name, content_type=receipt_type,
        )
    row = DispatchOutcome(dispatch_id=dispatch.id, outcome=outcome, outcome_on=outcome_on, note=note or None,
                          receipt_document_id=receipt.id if receipt else None, created_at=datetime.utcnow(),
                          created_by_user_id=user_id, created_by_name=user_name)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        db.rollback()  # ein gleichzeitiger Vermerk war schneller; ein schon abgelegter Beleg bleibt ohne Eintrag (1.8.20)
        raise DispatchConflict("Zu diesem Versand hat inzwischen jemand anderes ein Ergebnis vermerkt.")
    from .audit import record_audit_entry
    from .dispatch_documents import project_id_of

    record_audit_entry(
        db, action="geändert", entity_type=DISPATCH_ENTITY_TYPE, entity_id=dispatch.id,
        entity_label=_dispatch_label(dispatch), project_id=project_id_of(db, dispatch.document_type, dispatch.document_id),
        field_name="outcome", field_label="Versandergebnis",
        new_value=f"{OUTCOMES[outcome]} am {outcome_on.strftime('%d.%m.%Y')}" + (f" – Notiz: {note}" if note else "")
                  + (" – mit Beleg" if receipt else ""),
        actor_user_id=user_id, actor_name=user_name,
    )
    db.commit()
    db.refresh(row)
    from .dispatch_documents import after_outcome

    after_outcome(db, dispatch, row)
    return row


def outcome_to_dict(row: DispatchOutcome | None) -> dict | None:
    from .berlin_time import to_berlin
    from .sent_documents import sent_document_to_dict

    if row is None:
        return None
    return {"outcome": row.outcome, "outcome_label": OUTCOMES.get(row.outcome, row.outcome), "outcome_on": row.outcome_on,
            "note": row.note, "created_at_local": to_berlin(row.created_at), "created_by_name": row.created_by_name,
            "receipt_document": sent_document_to_dict(row.receipt_document) if row.receipt_document else None}


def dispatch_outcomes(db: Session, dispatch_ids: list[int]) -> dict[int, DispatchOutcome]:
    """Versandergebnisse je Eintrag (seit 1.8.41), für mehrere Einträge in einer Abfrage."""
    if not dispatch_ids:
        return {}
    from sqlalchemy.orm import selectinload

    rows = db.scalars(select(DispatchOutcome).where(DispatchOutcome.dispatch_id.in_(dispatch_ids))
                      .options(selectinload(DispatchOutcome.receipt_document))).all()
    return {r.dispatch_id: r for r in rows}


def authorization_to_dict(row) -> dict:
    """Beim Versand festgehaltene Empfangsvollmacht (seit 1.8.40, DispatchAuthorization)."""
    from .project_participants import role_label
    from .sent_documents import sent_document_to_dict

    return {"participant_id": row.participant_id, "contact_name": row.contact_name, "role": row.role,
            "role_label": role_label(row.role), "recipient_email": row.recipient_email, "note": row.note,
            "sent_document": sent_document_to_dict(row.sent_document) if row.sent_document else None}


def dispatch_authorizations(db: Session, dispatch_ids: list[int]) -> dict[int, list[dict]]:
    """Festgehaltene Vollmachten je Versand (seit 1.8.40), für mehrere Einträge in einer Abfrage."""
    if not dispatch_ids:
        return {}
    from sqlalchemy.orm import selectinload

    rows = db.scalars(select(DispatchAuthorization).where(DispatchAuthorization.dispatch_id.in_(dispatch_ids))
                      .options(selectinload(DispatchAuthorization.sent_document))
                      .order_by(DispatchAuthorization.id)).all()
    result: dict[int, list[dict]] = {}
    for row in rows:
        result.setdefault(row.dispatch_id, []).append(authorization_to_dict(row))
    return result


def dispatch_to_dict(dispatch: EmailDispatch, now: datetime | None = None, authorizations: list[dict] | None = None,
                     outcome: DispatchOutcome | None = None, copies: list[dict] | None = None) -> dict:
    """outcome (seit 1.8.41): das vermerkte Versandergebnis, falls schon geladen (list_dispatches()). copies (seit 1.8.69): die
    Personen unter "Kopie an:" im Dokument mit der Adresse, an die die Kopie ging, oder ohne Mail mit Grund
    (app/frozen_copies.py)."""
    from .berlin_time import to_berlin
    from .sent_documents import sent_document_to_dict

    return {
        "outcome": outcome_to_dict(outcome), "delivered_to_client": dispatch.delivered_to_client,
        "can_record_outcome": (outcome is None and dispatch.status == "gesendet"
                               and dispatch.document_type in DOCUMENT_TYPES),
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
        "resolved": dispatch.resolved_at is not None, "resolved_at_local": to_berlin(dispatch.resolved_at),
        "resolved_by_name": dispatch.resolved_by_name, "resolution_note": dispatch.resolution_note,
        "manual": dispatch.channel in MANUAL_CHANNELS, "delivered_on": dispatch.delivered_on,
        "delivery_note": dispatch.delivery_note,
        "sent_document": sent_document_to_dict(dispatch.sent_document) if dispatch.sent_document else None,
        "receipt_document": sent_document_to_dict(dispatch.receipt_document) if dispatch.receipt_document else None,
        "authorizations": authorizations or [],
        "copies": copies or [],
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
    from .frozen_copies import dispatch_copies

    authorizations = dispatch_authorizations(db, [r.id for r in rows])
    outcomes = dispatch_outcomes(db, [r.id for r in rows])
    copies = dispatch_copies(db, [r.id for r in rows])
    items = [dispatch_to_dict(r, now, authorizations.get(r.id), outcomes.get(r.id), copies.get(r.id)) for r in rows]
    # Seit 1.8.33: ein Vertrag hat keine eigene Seite, die Liste verlinkt auf seinen Auftrag.
    contract_ids = {r.document_id for r in rows if r.document_type == "vertrag" and r.document_id is not None}
    if contract_ids:
        from .models import OrderContract
        orders_of = dict(db.execute(select(OrderContract.id, OrderContract.order_id).where(OrderContract.id.in_(contract_ids))).all())
        for item in items:
            if item["document_type"] == "vertrag":
                item["order_id"] = orders_of.get(item["document_id"])
    return {"items": items, "stuck_count": stuck_count, "stuck_after_minutes": int(STUCK_AFTER.total_seconds() // 60)}
