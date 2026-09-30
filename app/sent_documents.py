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

Rollenlos wie jede Geschäftslogik; wer lesen darf, entscheidet app/routers/email_dispatches.py.
"""

import hashlib
import os
import stat
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .models import SentDocument
from .paths import data_dir

SENT_DOCUMENT_ROOT = Path(os.getenv("DACHKONZEPTE_SENT_DOCUMENT_ROOT", data_dir() / "sent_documents"))

DOCUMENT_TYPES = {"angebot": "Angebot", "auftrag": "Auftrag", "rechnung": "Rechnung", "mahnung": "Mahnung"}

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
    filename: str, content: bytes, user_id: int | None, user_name: str,
) -> SentDocument:
    """Legt `content` als neue, schreibgeschützte Datei ab und trägt sie ein (flush, kein Commit --
    der Aufrufer committet zusammen mit dem Verweis im Versandprotokoll)."""
    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"Unbekannte Dokumentart für die Ablage: {document_type}")
    sha256 = hashlib.sha256(content).hexdigest()
    now = datetime.utcnow()
    stored_filename = f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}_{sha256[:16]}.pdf"
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
        created_at=now, created_by_user_id=user_id, created_by_name=user_name or "System",
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


def sent_document_to_dict(doc: SentDocument) -> dict:
    from .berlin_time import to_berlin

    return {
        "id": doc.id, "document_type": doc.document_type,
        "document_type_label": DOCUMENT_TYPES.get(doc.document_type, doc.document_type),
        "document_id": doc.document_id, "document_number": doc.document_number,
        "filename": doc.filename, "size_bytes": doc.size_bytes, "sha256": doc.sha256,
        "created_at": doc.created_at, "created_at_local": to_berlin(doc.created_at),
        "created_by_name": doc.created_by_name,
    }
