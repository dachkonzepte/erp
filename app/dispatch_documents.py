"""Die versendbaren Dokumente an einer Stelle (seit 1.8.20, Stufe 2, Runde 2a-3b).

Für eine nachgetragene Zustellung (Einschreiben, persönliche Übergabe, Bote, Fax) kennt das
Versandprotokoll nur Art und ID. Hier steht je Art, welches Dokument dazugehört, ob es zugestellt
werden darf (dieselben Bedingungen wie beim E-Mail-Versand), wie es heißt, zu welchem Projekt es
gehört und welches PDF in die Ablage kommt:

- Rechnung (auch Storno) und Mahnung: die maßgebliche Fassung aus der Ablage, wenn es sie schon
  gibt (app/sent_documents.py::frozen_or_fresh_pdf()), sonst neu erzeugt -- und damit ab jetzt
  maßgeblich.
- Angebot, Auftrag: neu erzeugt, wie beim E-Mail-Versand.
- Checkliste: seit 1.8.66 die feste Fassung des Abschlusses aus der Ablage (app/checklist_versions.py) -- nie neu
  erzeugt; nur vor 1.8.66 abgeschlossene wie bisher neu erzeugt in voller Auflösung (so wie über den PDF-Knopf).
- Vertrag (seit 1.8.33): die gültige festgeschriebene Fassung aus der Ablage -- nie neu erzeugt, und nur,
  solange sie zum Auftrag passt (dieselbe Bedingung wie beim E-Mail-Versand,
  app/contract_versions.py::deliverable_version()). Nach der Unterschrift (seit 1.8.35) die unterschriebene
  Abschrift (deliverable_document(); bei einer Unterschrift von vor 1.8.35 hier einmal nachgeholt).
- Abnahmeprotokoll (seit 1.8.67, Art "checkliste"): die jüngste gültige Fassung mit der Unterschrift des Auftraggebers
  (app/protocol_dispatch.py), auch an einem Entwurf -- wie beim Versand.
- Behinderungsanzeige, Anzeige der Wiederaufnahme (seit 1.8.40, Dokument-ID = Checkliste): die Fassung des
  Briefs zur aktuellen Unterschrift des Abschnitts, beim ersten Mal erstellt (app/notice_letters.py) -- nie
  neu gerendert; nach der Behinderungsanzeige ist die Aufgabe "versenden" erledigt (after_delivery).

Rollenlos; wer zustellen darf, entscheidet der Router. PDF-Renderer werden lokal importiert (Regel 3).
"""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from .models import Checklist, EmailDispatch, Invoice, Order, OrderContract, Quote, Reminder
from .sent_documents import DOCUMENT_TYPES, DocumentPdf, frozen_or_fresh_pdf


@dataclass
class DispatchDocument:
    document_type: str
    document_id: int
    number: str | None
    label: str  # "Rechnung R-2026-0001" -- für Betreff und Historie
    project_id: int | None
    pdf: Callable[[], DocumentPdf]  # wirft ArchiveFileError, wenn die maßgebliche Fassung beschädigt ist
    # seit 1.8.40: nach dem Eintrag einer Zustellung; seit 1.8.41 mit dem Eintrag (an wen ging sie?)
    after_delivery: Callable[[EmailDispatch], None] | None = None


def _fresh(build: Callable[[], bytes], filename: str) -> Callable[[], DocumentPdf]:
    return lambda: DocumentPdf(build(), filename, None)


def _quote(db: Session, quote: Quote) -> DispatchDocument:
    from .quote_framed_pdf import build_quote_framed_pdf

    if quote.status == "entwurf":
        raise ValueError("Ein Angebot im Entwurf wird nicht zugestellt.")
    return DispatchDocument("angebot", quote.id, quote.quote_number, f"Angebot {quote.quote_number}", quote.project_id,
                            _fresh(lambda: build_quote_framed_pdf(db, quote), f"{quote.quote_number}.pdf"))


def _order(db: Session, order: Order) -> DispatchDocument:
    from .order_pdf import build_order_pdf

    if order.status == "storniert":
        raise ValueError("Ein stornierter Auftrag wird nicht zugestellt.")
    return DispatchDocument("auftrag", order.id, order.order_number, f"Auftrag {order.order_number}", order.project_id,
                            _fresh(lambda: build_order_pdf(db, order), f"{order.order_number}.pdf"))


def _invoice(db: Session, invoice: Invoice) -> DispatchDocument:
    from .invoice_pdf import build_invoice_pdf

    if invoice.status == "entwurf":
        raise ValueError("Eine Rechnung im Entwurf wird nicht zugestellt.")
    kind = "Stornorechnung" if invoice.invoice_type == "storno" else "Rechnung"
    return DispatchDocument(
        "rechnung", invoice.id, invoice.invoice_number, f"{kind} {invoice.invoice_number}",
        invoice.order.project_id if invoice.order else None,
        lambda: frozen_or_fresh_pdf(db, "rechnung", invoice.id, build=lambda: build_invoice_pdf(db, invoice),
                                    filename=f"{invoice.invoice_number}.pdf"),
    )


def _reminder(db: Session, reminder: Reminder) -> DispatchDocument:
    from .reminder_pdf import build_reminder_pdf

    if reminder.status != "versendet":
        raise ValueError("Ein Mahnungsentwurf wird nicht zugestellt.")
    order = reminder.invoice.order if reminder.invoice else None
    return DispatchDocument(
        "mahnung", reminder.id, reminder.reminder_number, f"Mahnung {reminder.reminder_number}",
        order.project_id if order else None,
        lambda: frozen_or_fresh_pdf(db, "mahnung", reminder.id, build=lambda: build_reminder_pdf(db, reminder),
                                    filename=f"{reminder.reminder_number}.pdf"),
    )


def _checklist(db: Session, checklist: Checklist) -> DispatchDocument:
    from .checklist_pdf import build_checklist_pdf

    if checklist.template_version.purpose == "abnahme" and checklist.order_id is not None:
        # seit 1.8.67: das Abnahmeprotokoll -- die jüngste gültige Fassung mit der Unterschrift des Auftraggebers
        from .protocol_dispatch import protocol_dispatch_document
        return protocol_dispatch_document(db, checklist)
    if checklist.status != "abgeschlossen":
        raise ValueError("Nur abgeschlossene Checklisten werden zugestellt.")
    from .checklist_versions import completion_version
    from .sent_documents import read_sent_document

    order = db.get(Order, checklist.order_id) if checklist.order_id else None
    label = f"Checkliste Nr. {checklist.id} ({checklist.template_label_snapshot})"
    version = completion_version(db, checklist)
    if version is not None:  # seit 1.8.66: die feste Fassung, ArchiveFileError bei veränderter Datei
        document = version.sent_document
        return DispatchDocument("checkliste", checklist.id, document.document_number, label,
                                order.project_id if order else None,
                                lambda: DocumentPdf(read_sent_document(document), document.filename, document))
    return DispatchDocument(
        "checkliste", checklist.id, f"Nr. {checklist.id}", label, order.project_id if order else None,
        _fresh(lambda: build_checklist_pdf(db, checklist), f"Checkliste-{checklist.id}.pdf"),
    )


def _contract(db: Session, contract: OrderContract) -> DispatchDocument:
    from .contract_versions import ContractStateError, deliverable_document
    from .sent_documents import read_sent_document

    order = contract.order
    try:
        version, document = deliverable_document(db, order, contract)
    except ContractStateError as e:
        raise ValueError(str(e)) from e
    signed = ", unterschrieben" if document.id != version.sent_document_id else ""
    return DispatchDocument(
        "vertrag", contract.id, document.document_number,
        f"Vertrag zu Auftrag {order.order_number}, Fassung {version.version_no}{signed}", order.project_id,
        lambda: DocumentPdf(read_sent_document(document), document.filename, document),
    )


def _notice(kind: str):
    def build(db: Session, checklist: Checklist) -> DispatchDocument:
        from .notice_letters import dispatch_document_for

        try:
            return dispatch_document_for(db, checklist, kind)
        except LookupError as e:  # keine passende Anzeige -- für die Zustellung "nicht zustellbar"
            raise ValueError(str(e)) from e
    return build


_REGISTRY = {"angebot": (Quote, _quote), "auftrag": (Order, _order), "rechnung": (Invoice, _invoice),
             "mahnung": (Reminder, _reminder), "checkliste": (Checklist, _checklist),
             "vertrag": (OrderContract, _contract), "behinderungsanzeige": (Checklist, _notice("behinderungsanzeige")),
             "wiederaufnahme": (Checklist, _notice("wiederaufnahme")),
             "bedenkenanzeige": (Checklist, _notice("bedenkenanzeige"))}  # seit 1.8.44
assert set(_REGISTRY) == set(DOCUMENT_TYPES), "jede Dokumentart der Ablage braucht einen Eintrag hier"


def document_row(db: Session, document_type: str, document_id: int):
    """Die Zeile des Dokuments (Angebot, Auftrag, …, Checkliste) -- None bei unbekannter Art oder fehlendem Dokument."""
    entry = _REGISTRY.get(document_type)
    return db.get(entry[0], document_id) if entry else None


def dispatch_document(db: Session, document_type: str, document_id: int) -> DispatchDocument:
    """LookupError: unbekannte Art oder Dokument fehlt (404). ValueError: nicht zustellbar (400)."""
    row = document_row(db, document_type, document_id)
    if row is None:
        raise LookupError("Dokument nicht gefunden.")
    return _REGISTRY[document_type][1](db, row)


def after_outcome(db: Session, dispatch: EmailDispatch, outcome) -> None:
    """Nachlauf eines vermerkten Versandergebnisses je Dokumentart (seit 1.8.41, nach dem Commit des Vermerks):
    Behinderungs- bzw. seit 1.8.44 Bedenkenanzeige "unzustellbar" -- kam sie auf keinem anderen Weg beim
    Auftraggeber an, ist die Aufgabe "versenden" wieder offen (app/notice_letters.py). Sonst nichts."""
    if dispatch.document_type in ("behinderungsanzeige", "bedenkenanzeige"):
        from .notice_letters import after_dispatch_outcome

        after_dispatch_outcome(db, dispatch, outcome)


def project_id_of(db: Session, document_type: str, document_id: int | None) -> int | None:
    """Projekt des Dokuments (für die Änderungshistorie), unabhängig davon, ob es heute noch
    zustellbar wäre; None, wenn es keins gibt."""
    entry = _REGISTRY.get(document_type)
    row = db.get(entry[0], document_id) if entry and document_id is not None else None
    if isinstance(row, Reminder):
        row = row.invoice
    if isinstance(row, Invoice):
        row = row.order
    if isinstance(row, Checklist):
        row = db.get(Order, row.order_id) if row.order_id else None
    if isinstance(row, OrderContract):
        row = row.order
    return getattr(row, "project_id", None)
