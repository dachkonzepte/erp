"""Abnahmeprotokoll an den Auftraggeber (seit 1.8.67, Stufe 2c-2e, Punkt 2).

Herleitung: docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.67". Über den Weg der Anzeigen (app/notice_letters.py),
nichts nachgebaut -- dieselben Funktionen: An fest der Auftraggeber (Kunde des Projekts, die API nimmt keine An-Adresse), Prüfung
auf abweichenden Kunden mit Bestätigung (Historie), CC vorbelegt mit den Beteiligten "Kopie bei Anzeigen", die Vollmacht eines
empfangsbevollmächtigten Empfängers beim Versand in der Ablage, E-Mail-Vorlage mit denselben Platzhaltern, "Zustellung nachtragen"
und "Empfang bestätigt"/"unzustellbar" im Versandprotokoll.

Versendet wird nur aus der Ablage: die jüngste gültige feste Fassung (app/checklist_versions.py), die die gültige Unterschrift des
Auftraggebers zeigt -- nie neu erzeugt, nur mit stimmender Prüfsumme. Ist die Fassung überholt (eine Unterschrift darin verworfen),
geht sie nicht mehr hinaus; vor dem Senden prüft der Versand das unter der Zeilensperre der Checkliste noch einmal
(dispatch_email(before_send=…)), so fällt ein gleichzeitiges Verwerfen nicht zwischen Prüfung und Versand. "Kopie an:" steht im PDF
jeder Fassung des Protokolls (app/checklist_pdf.py, beim Erstellen der Fassung eingefroren: checklist_versions.copy_to).

Dokumentart im Versandprotokoll und in der Ablage bleibt "checkliste" (Dokument-ID = Checkliste); der allgemeine Versand einer
Checkliste mit freiem Empfänger ist für das Abnahmeprotokoll gesperrt (app/checklist_email.py). Rollenlos; nur das Büro
(app/routers/notice_letters.py)."""

import json

from sqlalchemy.orm import Session

from .acceptance_protocol import customer_signature
from .berlin_time import to_berlin
from .checklist_purposes import ACCEPTANCE_PURPOSE
from .checklist_versions import latest_valid_version, shown_signature_ids
from .models import Checklist, ChecklistVersion, EmailDispatch, Order
from .notice_letters import (
    NoticeStateError, client_address, client_recipients, delivery_status, dispatch_to_client, letter_was_sent,
)

DOCUMENT_TYPE = "checkliste"  # Ablage und Versandprotokoll
TEMPLATE_KEY = "abnahmeprotokoll"  # E-Mail-Vorlage (app/document_email_templates.py)
LABEL = "Abnahmeprotokoll"
WAITING_TEXT = "Möglich nach der Unterschrift des Auftraggebers – versendet wird die feste Fassung, die sie zeigt."
NO_VERSION_TEXT = ("Zur gültigen Unterschrift des Auftraggebers gibt es keine gültige feste Fassung (Unterschrift vor 1.8.66 oder "
                   "die Fassung ist überholt). Die nächste Unterschrift legt eine an; sonst die Unterschrift mit Begründung "
                   "verwerfen und neu leisten lassen.")


def _protocol(db: Session, checklist_id: int, *, for_update: bool = False) -> Checklist:
    from .checklists import _load

    checklist = _load(db, checklist_id, for_update=for_update)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    if checklist.template_version.purpose != ACCEPTANCE_PURPOSE or checklist.order_id is None:
        raise LookupError("Diese Checkliste ist kein Abnahmeprotokoll zu einem Auftrag.")
    return checklist


def protocol_version(db: Session, checklist: Checklist) -> ChecklistVersion | None:
    """Die Fassung, die hinausgeht: die jüngste gültige, wenn sie die gültige Unterschrift des Auftraggebers zeigt -- sonst
    None (noch nicht unterschrieben, oder keine gültige Fassung mit dieser Unterschrift)."""
    signature = customer_signature(checklist)
    if signature is None:
        return None
    version = latest_valid_version(db, checklist)
    return version if version is not None and signature.id in shown_signature_ids(version) else None


def _require_version(db: Session, checklist: Checklist) -> ChecklistVersion:
    if customer_signature(checklist) is None:
        raise NoticeStateError(WAITING_TEXT)
    version = protocol_version(db, checklist)
    if version is None:
        raise NoticeStateError(NO_VERSION_TEXT)
    return version


def _document(version: ChecklistVersion) -> bytes:
    from .sent_documents import ArchiveFileError, read_sent_document

    try:
        return read_sent_document(version.sent_document)
    except ArchiveFileError as exc:
        raise NoticeStateError(f"Die feste Fassung {version.version_no} in der Ablage ist nicht mehr unversehrt: {exc} Es "
                               "wurde nichts versendet.") from exc


def _still_current(version_id: int, checklist_id: int):
    """Haken vor dem Senden: unter der Zeilensperre der Checkliste ist die Fassung noch die, die hinausgehen darf -- sonst
    ValueError, der Eintrag wird "fehlgeschlagen", nichts gesendet."""
    def check(session: Session, _dispatch: EmailDispatch) -> None:
        checklist = _protocol(session, checklist_id, for_update=True)
        current = protocol_version(session, checklist)
        if current is None or current.id != version_id:
            raise ValueError("Die Fassung ist inzwischen überholt (eine Unterschrift wurde verworfen) – es wurde nichts "
                             "versendet. Bitte die Seite neu laden.")
    return check


def send_protocol(db: Session, checklist_id: int, *, cc_email: str | None = None, dispatch_key: str | None = None,
                  user=None, confirm_customer: bool = False):
    """Versendet die jüngste gültige Fassung an den Auftraggeber. NoticeStateError (Zustand, 409; CustomerMismatch ohne
    Bestätigung), ValueError (Eingabe/Versand, 400), DispatchConflict (409)."""
    from .email_dispatch import actor_of

    user_id, user_name = actor_of(user)
    checklist = _protocol(db, checklist_id)
    version = _require_version(db, checklist)  # Zustand zuerst, vor Empfänger und Datei
    order = db.get(Order, checklist.order_id)
    to, mismatch = client_address(order, confirm_customer)
    pdf = _document(version)
    return dispatch_to_client(
        db, checklist=checklist, order=order, template_key=TEMPLATE_KEY, label=LABEL, document_type=DOCUMENT_TYPE,
        document=version.sent_document, pdf=pdf, to=to, cc_email=cc_email, dispatch_key=dispatch_key, user_id=user_id,
        user_name=user_name, mismatch=mismatch, check=_still_current(version.id, checklist.id),
    )


def protocol_dispatch_document(db: Session, checklist: Checklist):
    """Eintrag für app/dispatch_documents.py (Zustellung nachtragen, Art "checkliste" eines Abnahmeprotokolls): dieselbe Fassung
    wie beim Versand, aus der Ablage -- ValueError, solange es keine gibt."""
    from .dispatch_documents import DispatchDocument
    from .sent_documents import DocumentPdf, read_sent_document

    try:
        version = _require_version(db, checklist)
    except NoticeStateError as exc:
        raise ValueError(f"{LABEL}: {exc}") from exc
    order = db.get(Order, checklist.order_id)
    document = version.sent_document
    return DispatchDocument(DOCUMENT_TYPE, checklist.id, document.document_number,
                            f"{LABEL} Nr. {checklist.id} zu Auftrag {order.order_number}", order.project_id,
                            lambda: DocumentPdf(read_sent_document(document), document.filename, document))


def protocol_dispatch_state(db: Session, checklist_id: int) -> dict:
    """Alles für die Karte "Protokoll an den Auftraggeber" (nur Büro): Empfänger wie bei den Anzeigen, die Fassung, die
    hinausgeht, und der Stand (versendet = beim Auftraggeber angekommen, wie bei den Anzeigen)."""
    from .sent_documents import sent_document_to_dict

    checklist = _protocol(db, checklist_id)
    order = db.get(Order, checklist.order_id)
    signature = customer_signature(checklist)
    version = protocol_version(db, checklist)
    ready = version is not None
    return {
        **client_recipients(db, order), "checklist_id": checklist.id, "order_id": order.id,
        "order_number": order.order_number, "label": LABEL,
        "signed": signature is not None, "ready": ready,
        "waiting_text": None if ready else (WAITING_TEXT if signature is None else NO_VERSION_TEXT),
        "status": delivery_status(db, DOCUMENT_TYPE, checklist.id, ready),
        "sent": letter_was_sent(db, DOCUMENT_TYPE, checklist.id),
        "version": None if version is None else {
            "id": version.id, "version_no": version.version_no, "created_at": version.created_at,
            "created_at_local": to_berlin(version.created_at), "copy_to": json.loads(version.copy_to or "[]"),
            "sent_document": sent_document_to_dict(version.sent_document)},
    }

