"""Feste Randabstände je Seitentyp (seit 1.0.69).

Siehe DocumentPageMargins in models.py für die ausführliche Begründung.
Ersetzt die bisher in app/quote_layout_pdf.py fest verdrahteten Werte
PAGE_BOTTOM_MARGIN_MM/CONTINUATION_CONTENT_START_MM durch eine editierbare
Einstellung.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .document_type_fallback import SHARED_DOCUMENT_TYPE, resolve_shared_document_type
from .grunddaten import GrunddatenFehlen
from .models import DocumentPageMargins

PAGE_TYPES = {"first", "continuation"}

# Entspricht exakt den bisherigen, fest einprogrammierten Werten -- die
# Standardbelegung ändert also nichts am bestehenden Verhalten, solange
# niemand die Werte anpasst.
DEFAULT_MARGINS = {
    "first": {"top": Decimal("17.0"), "bottom": Decimal("20.0"), "left": Decimal("18.0"), "right": Decimal("16.0")},
    "continuation": {"top": Decimal("22.0"), "bottom": Decimal("20.0"), "left": Decimal("18.0"), "right": Decimal("16.0")},
}

# Seit 1.3.2 (CLAUDE.md "PDF-Rahmen"): einzelne Felder lassen sich je document_type gegenüber
# DEFAULT_MARGINS überschreiben -- ursprünglich nur für "reminder", seit 1.3.6 (Zusammenführung
# der Layout-Einstellungen, CLAUDE.md "Gemeinsamer Dokumenttyp") umgeschlüsselt auf
# SHARED_DOCUMENT_TYPE ("default"), da der geteilte Satz jetzt für jeden Dokumenttyp außer dem
# Angebot gilt, nicht mehr nur für die Mahnung. "quote" ist hier nicht gelistet und bleibt dadurch
# exakt beim bisherigen, generischen Wert -- unverändertes Verhalten.
#
# top (seit 1.3.19 korrigiert, CLAUDE.md "Gemeinsamer Dokumenttyp"/Randkorrektur "default"): der
# alte 42mm-Wert (1.3.2) war zur Kollisionsvermeidung mit den GEZEICHNETEN Ersatz-Bausteinen
# bemessen (company_header/logo, seit 1.3.2/1.3.8 aber ohnehin standardmäßig unsichtbar), nicht
# gegen das tatsächliche Briefpapier. In 1.3.18 gegen das reale, mit "quote" identische
# Briefpapier vermessen und an vier echten Dokumenten (Mahnung/Rechnung/Auftrag/Einsatzbericht)
# probeweise geprüft, keine Überlappung -- auf dieselben Werte wie "quote" gesetzt: "first" 25mm
# (Kopfgrafik reicht zwar bis ~31mm, aber nur im horizontal zentrierten Bereich zwischen
# Anschrift- und Meta-Spalte, wo nichts gezeichnet wird), "continuation" 40mm (dort begrenzt
# nicht die Kopfgrafik, sondern der gezeichnete continuation_header-Baustein, Unterkante bei
# 38mm, der auf jeder Folgeseite zusätzlich zum Briefpapier erscheint).
#
# bottom (seit 1.3.18 korrigiert, derselbe Fehlertyp wie die Fußzeile in 1.3.8, hier nur noch
# nicht aufgetreten): der generische DEFAULT_MARGINS-Wert (20mm) unterschreitet den real
# bedruckten Fußbereich desselben Briefpapiers (~27mm, siehe "quote", dort in 1.3.16 bereits auf
# 32mm korrigiert) -- auf denselben, gegen das reale Briefpapier vermessenen Wert wie "quote"
# gesetzt.
DOCUMENT_TYPE_MARGIN_OVERRIDES: dict[str, dict[str, dict[str, Decimal]]] = {
    "default": {
        "first": {"top": Decimal("25.0"), "bottom": Decimal("32.0")},
        "continuation": {"top": Decimal("40.0"), "bottom": Decimal("32.0")},
    },
}


def _default_margin_values(document_type: str, page_type: str) -> dict[str, Decimal]:
    values = dict(DEFAULT_MARGINS[page_type])
    values.update(DOCUMENT_TYPE_MARGIN_OVERRIDES.get(document_type, {}).get(page_type, {}))
    return values


def _validate_page_type(page_type: str) -> None:
    if page_type not in PAGE_TYPES:
        raise ValueError(f"Unbekannter Seitentyp: {page_type}")


def ensure_default_margins(db: Session) -> None:
    """Legt die Ränder des geteilten Satzes (SHARED_DOCUMENT_TYPE) für jeden Seitentyp an, wo sie
    fehlen (Standardwerte siehe DEFAULT_MARGINS). Rührt eine bereits bestehende Einstellung nicht an.
    Anlegeschritt von app.grunddaten.anlegen() (seit 1.8.42): flush, kein commit -- bis 1.8.41 legte
    der erste Lesezugriff die Zeile an und committete dabei, auch beim Rendern unter einer Zeilensperre.

    Gegen einen gleichzeitigen ersten Zugriff abgesichert (siehe CLAUDE.md "Self-Seeding gegen
    gleichzeitigen Zugriff absichern"): kollidiert der INSERT mit der UNIQUE-Verletzung auf
    (document_type, page_type), gilt das als "schon angelegt"."""
    for page_type in sorted(PAGE_TYPES):
        exists = db.scalar(select(DocumentPageMargins.id).where(
            DocumentPageMargins.document_type == SHARED_DOCUMENT_TYPE, DocumentPageMargins.page_type == page_type,
        ))
        if exists is not None:
            continue
        defaults = _default_margin_values(SHARED_DOCUMENT_TYPE, page_type)
        try:
            with db.begin_nested():
                db.add(DocumentPageMargins(
                    document_type=SHARED_DOCUMENT_TYPE, page_type=page_type,
                    top_mm=defaults["top"], bottom_mm=defaults["bottom"], left_mm=defaults["left"], right_mm=defaults["right"],
                ))
                db.flush()
        except IntegrityError:
            continue


def get_margins(db: Session, document_type: str, page_type: str) -> DocumentPageMargins:
    """Die Ränder, die für diesen Dokumenttyp und Seitentyp gelten -- nur lesen.

    Mit Rückfall (seit 1.3.6): existiert für document_type selbst keine eigene Zeile (der
    Normalfall für jeden Dokumenttyp), gilt die Zeile des geteilten Satzes (SHARED_DOCUMENT_TYPE) --
    siehe app/document_type_fallback.py. update_margins()/reset_margins_to_default() nutzen das
    bewusst NICHT (siehe dort), damit ein Schreibzugriff nie versehentlich die geteilte Zeile
    statt einer eigenen trifft. Die Zeilen des geteilten Satzes legt app.grunddaten.anlegen() beim
    Start an (seit 1.8.42)."""
    _validate_page_type(page_type)
    effective_type = resolve_shared_document_type(db, DocumentPageMargins, document_type, DocumentPageMargins.page_type == page_type)
    row = db.scalar(
        select(DocumentPageMargins)
        .where(DocumentPageMargins.document_type == effective_type, DocumentPageMargins.page_type == page_type)
    )
    if row is None:
        raise GrunddatenFehlen(f"document_page_margins: Ränder {effective_type}/{page_type} fehlen -- "
                               "app.grunddaten.anlegen() ist beim Start nicht gelaufen oder gescheitert (siehe Log).")
    return row


def update_margins(db: Session, document_type: str, page_type: str, *, top_mm: Decimal, bottom_mm: Decimal, left_mm: Decimal, right_mm: Decimal) -> DocumentPageMargins:
    """Schreibt IMMER auf die Zeile mit exakt diesem document_type -- bewusst OHNE den Rückfall
    aus get_margins(), sonst würde ein Aufruf mit einem echten Dokumenttyp ohne eigene
    Zeile (z.B. "invoice") lautlos die geteilte Zeile verändern statt eine eigene für "invoice"
    anzulegen. Die schreibenden Endpunkte lassen dafür ohnehin nur noch "quote" und
    SHARED_DOCUMENT_TYPE durch (siehe _validate_writable_document_type() in
    app/routers/document_layout.py); ein künftiger, echter Sonderfall je Dokumenttyp müsste
    diese Sperre an der entsprechenden Stelle bewusst erweitern, nicht implizit über einen
    Lese-Rückfall entstehen."""
    _validate_page_type(page_type)
    row = db.scalar(
        select(DocumentPageMargins)
        .where(DocumentPageMargins.document_type == document_type, DocumentPageMargins.page_type == page_type)
    )
    if row is None:
        row = DocumentPageMargins(document_type=document_type, page_type=page_type, top_mm=top_mm, bottom_mm=bottom_mm, left_mm=left_mm, right_mm=right_mm)
        db.add(row)
    else:
        row.top_mm = top_mm
        row.bottom_mm = bottom_mm
        row.left_mm = left_mm
        row.right_mm = right_mm
    db.commit()
    db.refresh(row)
    return row


def reset_margins_to_default(db: Session, document_type: str, page_type: str) -> DocumentPageMargins:
    """Wie update_margins() bewusst literal, kein Rückfall -- setzt die Zeile mit exakt diesem
    document_type auf IHRE eigenen Standardwerte zurück (_default_margin_values wertet
    DOCUMENT_TYPE_MARGIN_OVERRIDES weiterhin nach dem literalen document_type aus)."""
    _validate_page_type(page_type)
    defaults = _default_margin_values(document_type, page_type)
    return update_margins(
        db, document_type, page_type,
        top_mm=defaults["top"], bottom_mm=defaults["bottom"], left_mm=defaults["left"], right_mm=defaults["right"],
    )
