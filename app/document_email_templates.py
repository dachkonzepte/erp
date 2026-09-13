"""E-Mail-Betreff/-Text-Vorlagen je Dokumenttyp (seit 1.0.82).

Siehe DocumentEmailTemplate in models.py für die ausführliche Begründung.
Bewusst eigenständig (nicht in app/quotes.py/orders.py/invoices.py), da
alle drei Dokumenttypen dieselbe, einfache Struktur teilen -- analog zu
app/document_page_margins.py für die Randabstände.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DocumentEmailTemplate

DOCUMENT_TYPES = {"quote", "order", "invoice"}


def _validate_document_type(document_type: str) -> None:
    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"Unbekannter Dokumenttyp: {document_type}")


def get_email_template(db: Session, document_type: str) -> DocumentEmailTemplate | None:
    """Gibt None zurück, wenn noch nichts angepasst wurde -- die jeweilige
    Versandfunktion nutzt dann ihren eingebauten Standardtext. Anders als
    z.B. ensure_default_reminder_levels() bewusst OHNE automatisches
    Anlegen einer Zeile: es gibt keine "Standardwerte", die eine leere Zeile
    sinnvoll vorausfüllen könnte -- der eingebaute Text lebt im jeweiligen
    Python-Modul, nicht in der Datenbank."""
    _validate_document_type(document_type)
    return db.scalar(select(DocumentEmailTemplate).where(DocumentEmailTemplate.document_type == document_type))


def update_email_template(db: Session, document_type: str, *, subject_template: str | None, body_template: str | None) -> DocumentEmailTemplate:
    _validate_document_type(document_type)
    row = get_email_template(db, document_type)
    if row is None:
        row = DocumentEmailTemplate(document_type=document_type)
        db.add(row)
    row.subject_template = subject_template
    row.body_template = body_template
    db.commit()
    db.refresh(row)
    return row
