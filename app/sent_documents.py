"""Ablage versendeter Dokumente (seit 1.8.17, Stufe 2, Runde 2a-3a).

Jedes per E-Mail versendete PDF wird genau so abgelegt, wie es hinausging: dieselben Bytes, die
app/email_dispatch.py als Anhang übergibt, mit SHA-256, Dokumentart, Dokument-ID, Zeitpunkt und
Benutzer (Modell SentDocument). Abgelegte Dateien werden nie überschrieben oder gelöscht:

- Die Datei wird exklusiv angelegt (`open(..., "xb")`), ein vorhandener Name führt zu einem
  Fehler statt zum Überschreiben; der Name ist zufällig und enthält den Anfang der Prüfsumme,
  nie den Dokumentnamen. Danach wird sie schreibgeschützt gesetzt.
- Es gibt keine Funktion zum Ändern oder Löschen, und die ORM-Sperre in app/models.py
  (ArchiveImmutableError) lehnt Änderung und Löschen des Eintrags ab.
- Nachträglich veränderte oder fehlende Dateien fallen bei jedem Abruf auf
  (verify_sent_document(): Prüfsumme neu gerechnet). Ausgeliefert wird nur eine Datei, deren
  Prüfsumme stimmt. Gegen jemanden mit Zugriff auf Server und Datenbank zugleich schützt das
  nicht -- es macht Veränderungen sichtbar, verhindert sie nicht.

Maßgebliche Fassung (seit 1.8.19): Rechnung (auch Storno -- eine Rechnung mit invoice_type
"storno") und Mahnung kommen ab dem ersten Versand aus der Ablage, beim Nachdruck, beim Download und
beim erneuten Versand (frozen_or_fresh_pdf()). Neu erzeugt würde das PDF mit dem Briefkopf und
Briefpapier von heute -- der Kunde hat aber das von damals. Maßgeblich ist die zuerst abgelegte
Fassung, deren Versand nicht fehlgeschlagen ist (gesendet oder womöglich gesendet, also in Arbeit/
hängend); eine fehlgeschlagene zählt nicht, dann wird beim nächsten Versand neu erzeugt und
abgelegt. Rechnungen, die vor 1.8.17 oder nie per E-Mail hinausgingen, haben keine abgelegte
Fassung und werden wie bisher neu erzeugt.

Vertrag (seit 1.8.33): die Ablage nimmt die festgeschriebene Fassung beim Festschreiben auf, also
vor jedem Versand -- sie IST ab dann das Dokument (app/contract_versions.py). Versand und
nachgetragene Zustellung verweisen auf diesen Eintrag, legen nichts erneut ab.

Rollenlos wie jede Geschäftslogik; wer lesen darf, entscheidet app/routers/email_dispatches.py.
"""

import hashlib
import os
import stat
import uuid
from datetime import datetime
from pathlib import Path

from typing import Callable, NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EmailDispatch, SentDocument
from .paths import data_dir

SENT_DOCUMENT_ROOT = Path(os.getenv("DACHKONZEPTE_SENT_DOCUMENT_ROOT", data_dir() / "sent_documents"))

# "vertrag" seit 1.8.33: die festgeschriebene Fassung liegt schon vor dem ersten Versand hier
# (app/contract_versions.py), Dokument-ID ist die des Vertrags (OrderContract), nicht der Fassung.
# "behinderungsanzeige"/"wiederaufnahme" seit 1.8.40: Briefe an den Auftraggeber (app/notice_letters.py), Dokument-ID
# ist die der Checkliste; die Fassung liegt ab dem Erstellen hier, dazu beim Versand die Vollmachten.
DOCUMENT_TYPES = {"angebot": "Angebot", "auftrag": "Auftrag", "rechnung": "Rechnung", "mahnung": "Mahnung",
                  "checkliste": "Checkliste", "vertrag": "Vertrag", "behinderungsanzeige": "Behinderungsanzeige",
                  "wiederaufnahme": "Anzeige der Wiederaufnahme"}
# Was die Ablage aufnimmt (seit 1.8.20 neben PDFs auch Belege nachgetragener Zustellungen) und mit
# welcher Endung die Datei abgelegt wird.
CONTENT_TYPE_SUFFIXES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

VERIFY_TEXTS = {
    "unveraendert": "Datei unverändert (Prüfsumme stimmt).",
    "abweichend": "Datei weicht von der beim Versand festgehaltenen Prüfsumme ab.",
    "fehlt": "Datei fehlt in der Ablage.",
}


class ArchiveFileError(Exception):
    """Die abgelegte Datei fehlt oder passt nicht zu ihrer Prüfsumme."""

    def __init__(self, status: str):
        super().__init__(VERIFY_TEXTS[status])
        self.status = status


class DocumentPdf(NamedTuple):
    content: bytes
    filename: str
    archived: SentDocument | None  # gesetzt: die abgelegte Fassung, nicht neu erzeugt


# Diese Dokumentarten kommen ab dem ersten Versand aus der Ablage (siehe Moduldocstring).
FROZEN_AFTER_FIRST_DISPATCH = {"rechnung", "mahnung"}


def _path_for(stored_filename: str) -> Path:
    """Pfad unter SENT_DOCUMENT_ROOT; ein Eintrag, der aus der Ablage hinauszeigt, gilt als fehlend."""
    root = SENT_DOCUMENT_ROOT.resolve()
    path = (root / stored_filename).resolve()
    if root not in path.parents:
        raise ArchiveFileError("fehlt")
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def store_sent_document(
    db: Session, *, document_type: str, document_id: int, document_number: str | None,
    filename: str, content: bytes, user_id: int | None, user_name: str, content_type: str = "application/pdf",
) -> SentDocument:
    """Legt `content` als neue, schreibgeschützte Datei ab und trägt sie ein (flush, kein Commit --
    der Aufrufer committet zusammen mit dem Verweis im Versandprotokoll)."""
    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"Unbekannte Dokumentart für die Ablage: {document_type}")
    if content_type not in CONTENT_TYPE_SUFFIXES:
        raise ValueError(f"Dateityp {content_type} wird nicht abgelegt.")
    sha256 = hashlib.sha256(content).hexdigest()
    now = datetime.utcnow()
    stored_filename = f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}_{sha256[:16]}{CONTENT_TYPE_SUFFIXES[content_type]}"
    path = SENT_DOCUMENT_ROOT / stored_filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    if _file_sha256(path) != sha256:
        raise OSError("Die abgelegte Datei stimmt nicht mit dem versendeten Inhalt überein.")
    row = SentDocument(
        document_type=document_type, document_id=document_id, document_number=document_number,
        filename=filename, stored_filename=stored_filename, size_bytes=len(content), sha256=sha256,
        created_at=now, created_by_user_id=user_id, created_by_name=user_name or "System", content_type=content_type,
    )
    db.add(row)
    db.flush()
    return row


def verify_sent_document(doc: SentDocument) -> dict:
    """Rechnet die Prüfsumme der Datei neu: unveraendert | abweichend | fehlt."""
    try:
        path = _path_for(doc.stored_filename)
        status = "unveraendert" if _file_sha256(path) == doc.sha256 else "abweichend"
    except (ArchiveFileError, FileNotFoundError, NotADirectoryError):
        status = "fehlt"
    return {"status": status, "text": VERIFY_TEXTS[status], "sha256": doc.sha256}


def read_sent_document(doc: SentDocument) -> bytes:
    """Die abgelegten Bytes -- nur, wenn sie zur Prüfsumme passen, sonst ArchiveFileError."""
    try:
        content = _path_for(doc.stored_filename).read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        raise ArchiveFileError("fehlt")
    if hashlib.sha256(content).hexdigest() != doc.sha256:
        raise ArchiveFileError("abweichend")
    return content


def frozen_version(db: Session, document_type: str, document_id: int) -> SentDocument | None:
    """Die maßgebliche Fassung: die zuerst abgelegte, deren Versand nicht fehlgeschlagen ist."""
    if document_type not in FROZEN_AFTER_FIRST_DISPATCH:
        return None
    not_failed = select(EmailDispatch.id).where(
        EmailDispatch.sent_document_id == SentDocument.id, EmailDispatch.status != "fehlgeschlagen",
    ).exists()
    return db.scalar(
        select(SentDocument)
        .where(SentDocument.document_type == document_type, SentDocument.document_id == document_id, not_failed)
        .order_by(SentDocument.created_at, SentDocument.id)
        .limit(1)
    )


def frozen_or_fresh_pdf(
    db: Session, document_type: str, document_id: int, *, build: Callable[[], bytes], filename: str,
) -> DocumentPdf:
    """Das PDF für Nachdruck, Download und Versand: die maßgebliche Fassung aus der Ablage, wenn es
    eine gibt (nur mit stimmender Prüfsumme, sonst ArchiveFileError -- nie still neu erzeugt), sonst
    neu erzeugt über `build`."""
    archived = frozen_version(db, document_type, document_id)
    if archived is None:
        return DocumentPdf(build(), filename, None)
    return DocumentPdf(read_sent_document(archived), archived.filename, archived)


def sent_document_to_dict(doc: SentDocument) -> dict:
    from .berlin_time import to_berlin

    return {
        "id": doc.id, "document_type": doc.document_type,
        "document_type_label": DOCUMENT_TYPES.get(doc.document_type, doc.document_type),
        "document_id": doc.document_id, "document_number": doc.document_number,
        "filename": doc.filename, "size_bytes": doc.size_bytes, "sha256": doc.sha256, "content_type": doc.content_type,
        "created_at": doc.created_at, "created_at_local": to_berlin(doc.created_at),
        "created_by_name": doc.created_by_name,
    }
