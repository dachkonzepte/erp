"""Gemeinsamer, dokumenttyp-unabhängiger PDF-Rahmen (seit 1.3.1, erste Etappe erprobt an der
Mahnung, siehe app/reminder_pdf.py und CLAUDE.md "PDF-Rahmen").

Der Rahmen besteht aus drei Dingen, in dieser Rangfolge -- die in der Praxis übliche Reihenfolge
ist umgekehrt zur ursprünglichen Annahme: das Unternehmen hinterlegt meist sein fertiges
Briefpapier und blendet die gezeichneten Bausteine gerade DESHALB aus (genau wie beim Angebot
heute schon):

1. das hinterlegte Briefpapier als Hintergrund (DocumentLayoutBackground), getrennt für Seite 1
   und Folgeseiten (page_type)
2. die Ränder (DocumentPageMargins), ebenfalls getrennt je Seitentyp -- sie bestimmen, wo der
   fließende Inhalt beginnen/enden darf, damit er nicht in den Briefkopf oder die Fußzeile des
   Briefpapiers läuft
3. optionale, einzeln abschaltbare gezeichnete Bausteine (Logo, Firmenkopf, Fußzeile mit
   Seitenzahl) als Rückfall für Installationen ohne eigenes Briefpapier

Dieses Modul kennt keine Quote, keine Invoice und keinen Reminder -- es bekommt den Dokumenttyp
als Zeichenkette und liest die passende Konfiguration. Der Aufrufer (z. B. app/reminder_pdf.py)
übergibt nur den fließenden INHALT (eine reine Flowable-Liste, ohne Kenntnis von
NextPageTemplate/Frame/canvasmaker) -- render_framed_pdf() erledigt den Rest.

Architektur: BaseDocTemplate (nicht SimpleDocTemplate, wird für zwei unterschiedliche Frames
gebraucht) mit zwei PageTemplates, "first" und "later", je mit eigenem Frame aus den Rändern des
jeweiligen page_type und eigenem onPage-Callback (Hintergrund, dann Logo, dann Firmenkopf -- in
dieser Reihenfolge). Die Fußzeile mit Seitenzahl wird NICHT im onPage-Callback gezeichnet, sondern
über die reportlab-Standardtechnik für "Seite X von Y": eine Canvas-Unterklasse, die showPage()
abfängt und erst in save() -- wenn die Gesamtseitenzahl real bekannt ist -- jede Seite mit
fertigem Text versieht.
"""

from decimal import Decimal
from functools import partial
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_module
from reportlab.platypus import BaseDocTemplate, Frame, NextPageTemplate, PageTemplate

from .company_logo import logo_path
from .document_layout import ensure_default_layout, get_effective_background
from .document_layout_background import background_path
from .document_page_margins import get_margins
from .document_pdf import build_company_header_block, build_styles
from .models import DocumentLayoutBlock, DocumentPageMargins
from .settings import get_or_create_general_settings

PAGE_WIDTH_MM = Decimal("210.0")
PAGE_HEIGHT_MM = Decimal("297.0")

# Dieselben vier block_type-Werte wie DEFAULT_SHARED_LAYOUT (app/document_layout.py) -- die
# einzigen, die dieses Modul kennt/zeichnet. continuation_header seit 1.3.7.
FRAME_BLOCK_TYPES = ("logo", "company_header", "footer_text", "continuation_header")

# Seit 1.3.6: welche Dokumenttypen bereits über render_framed_pdf() (und damit über den
# geteilten Satz Briefpapier/Ränder/Bausteine, siehe app/document_type_fallback.py) laufen --
# Anzeigebeschriftung für die Vorschau in Einstellungen → Dokumente & Layout. render_framed_pdf()
# WEIST einen unbekannten document_type ab (siehe dort), statt ihn kommentarlos zu rendern --
# genau deshalb MUSS diese Zuordnung angefasst werden, sobald ein weiterer Renderer (Auftrag,
# irgendwann das Angebot) auf den gemeinsamen Rahmen umgestellt wird; eine reine
# Doku-Notiz an anderer Stelle könnte vergessen werden, ein fehlschlagender Aufruf nicht.
RENDERERS_USING_SHARED_FRAME: dict[str, str] = {
    "reminder": "Mahnung",
    "invoice": "Rechnung",
    "order": "Auftrag",
    "service_report": "Einsatzbericht",
    # Seit 1.3.13: der NEUE, parallele Angebots-Renderer (app/quote_framed_pdf.py) braucht diesen
    # Eintrag, um render_framed_pdf() überhaupt aufrufen zu dürfen -- der produktive PDF-Endpunkt
    # (quotes.py) und der Layout-Editor zeigen bis zur Umstellung weiterhin quote_layout_pdf.py.
    # Das lässt "quote" in der Vorschau unter Einstellungen → Dokumente & Layout bereits als
    # "nutzt den gemeinsamen Rahmen" erscheinen, obwohl produktiv noch der alte Renderer läuft --
    # bewusst in Kauf genommen für die Dauer des Parallelbetriebs, siehe CLAUDE.md.
    "quote": "Angebot",
    # Seit 1.3.61: eigener Stundenzettel für Monteure (app/field_timesheet_pdf.py) -- "mit
    # Briefkopf" war Betreibervorgabe, kein eigenes Briefpapier/keine eigenen Ränder nötig, fällt
    # ohne eigene Zeile automatisch auf den geteilten "default"-Satz zurück (siehe dort).
    "field_timesheet": "Stundenzettel (Monteur)",
}


class _NumberedCanvas(canvas_module.Canvas):
    """Sammelt alle Seiten zurück, bevor sie tatsächlich geschrieben werden -- erst in save() ist
    die Gesamtseitenzahl bekannt. Reportlabs Standardtechnik für "Seite X von Y" (siehe
    CLAUDE.md, Abschnitt "PDF-Rahmen", Nachtrag zu Seitenzahlen).

    Seit 1.3.7 zeichnet dieselbe Stelle zusätzlich die Wiederholungszeile auf Folgeseiten
    (CLAUDE.md "Gemeinsamer Dokumenttyp" -- Abschnitt Wiederholungszeile): ihre Seitenzahl hat
    dasselbe "erst am Ende bekannt"-Problem wie die Fußzeile, deshalb hier mitgezeichnet statt
    einen zweiten Mechanismus zu bauen. `_erp_page_type` wird vom onPage-Callback (siehe
    _make_on_page()) pro Seite gesetzt, BEVOR showPage() diese Seite als Snapshot sichert --
    beim Nachzeichnen in save() steht damit fest, ob eine gespeicherte Seite "first" oder
    "later" war, unabhängig von dieser Canvas-Instanz selbst (die keinen eigenen Begriff von
    Seitenvorlagen hat).

    Seit 1.3.12 (CLAUDE.md "Gemeinsamer Dokumenttyp" -- Abschnitt "Einstellbare Position der
    Wiederholungszeile"): die vertikale Position kommt aus dem `continuation_header`-
    DocumentLayoutBlock selbst (`y_mm`), nicht mehr aus einer festen Konstante -- ein echter,
    hochgeladener Briefbogen kann seine Dekorfläche an einer anderen Stelle haben als der
    ursprünglich angenommene Standardwert (8mm), siehe dortiger Fund gegen die echte Datenbank."""

    def __init__(self, *args, footer_enabled: bool, continuation_header: dict | None = None, **kwargs):
        canvas_module.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states: list[dict] = []
        self._footer_enabled = footer_enabled
        # {"rows": list[(label,value)], "margins": DocumentPageMargins, "y_mm": Decimal} oder
        # None (nicht sichtbar/keine Zeilen übergeben) -- siehe render_framed_pdf().
        self._continuation_header = continuation_header
        self._erp_page_type = "first"

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._footer_enabled:
                self.saveState()
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#666666"))
                self.drawString(20 * mm, 12 * mm, f"Seite {self._pageNumber} von {total}")
                self.restoreState()
            if self._continuation_header is not None and self._erp_page_type == "continuation":
                self.saveState()
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#666666"))
                margins = self._continuation_header["margins"]
                y = (float(PAGE_HEIGHT_MM) - float(self._continuation_header["y_mm"])) * mm
                left_x = float(margins.left_mm) * mm
                right_x = (float(PAGE_WIDTH_MM) - float(margins.right_mm)) * mm
                label_text = "   ".join(f"{label}: {value}" for label, value in self._continuation_header["rows"])
                self.drawString(left_x, y, label_text)
                self.drawRightString(right_x, y, f"Seite {self._pageNumber} von {total}")
                self.restoreState()
            canvas_module.Canvas.showPage(self)
        canvas_module.Canvas.save(self)


def _build_frame(margins: DocumentPageMargins, *, frame_id: str) -> Frame:
    """Randabstände werden direkt zur Frame-Geometrie -- kein zusätzliches Innenpolster, die
    Ränder SIND bereits die Grenze, an der der fließende Inhalt beginnen/enden darf."""
    left = float(margins.left_mm) * mm
    bottom = float(margins.bottom_mm) * mm
    width = float(PAGE_WIDTH_MM - margins.left_mm - margins.right_mm) * mm
    height = float(PAGE_HEIGHT_MM - margins.top_mm - margins.bottom_mm) * mm
    return Frame(left, bottom, width, height, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id=frame_id)


def frame_content_width(margins: DocumentPageMargins) -> float:
    """Verfügbare Innenbreite (reportlab-Punkte, bereits '* mm') für genau die Ränder, mit denen
    render_framed_pdf() auch den Frame selbst baut (_build_frame(), dieselbe Formel) -- öffentlich,
    damit ein Renderer seine Tabellen/Textblöcke exakt auf den tatsächlich KONFIGURIERTEN
    Satzspiegel ausrichten kann (seit 1.3.9, CLAUDE.md "Positionstabelle: Menge/Einheit/Breite"),
    statt auf einen hart codierten Standardwert wie PAGE_CONTENT_WIDTH (document_pdf.py), der nur
    stimmt, solange niemand die Ränder von 18mm/16mm weg ändert."""
    return float(PAGE_WIDTH_MM - margins.left_mm - margins.right_mm) * mm


def _draw_background(c, *, document_type: str, page_type: str, db) -> None:
    background = get_effective_background(db, document_type, page_type)
    if background is None:
        return
    path = background_path(background.stored_filename)
    if not path.is_file():
        return
    c.saveState()
    c.setFillColor(colors.white)
    c.rect(0, 0, float(PAGE_WIDTH_MM) * mm, float(PAGE_HEIGHT_MM) * mm, fill=1, stroke=0)
    c.drawImage(
        str(path), 0, 0, width=float(PAGE_WIDTH_MM) * mm, height=float(PAGE_HEIGHT_MM) * mm,
        preserveAspectRatio=True, anchor="c", mask="auto",
    )
    c.restoreState()


def _draw_logo(c, block: DocumentLayoutBlock, general) -> None:
    if not general.logo_filename:
        return
    path = logo_path(general.logo_filename)
    if not path.is_file():
        return
    draw_y = float(PAGE_HEIGHT_MM - block.y_mm - block.height_mm) * mm
    c.drawImage(
        str(path), float(block.x_mm) * mm, draw_y, width=float(block.width_mm) * mm,
        height=float(block.height_mm) * mm, preserveAspectRatio=True, mask="auto",
    )


def _draw_company_header(c, block: DocumentLayoutBlock, general, styles: dict) -> None:
    flowables = build_company_header_block(general, styles)
    cursor_y = float(block.y_mm)
    for flow in flowables:
        w, h = flow.wrapOn(c, float(block.width_mm) * mm, float(block.height_mm) * mm)
        draw_y = (float(PAGE_HEIGHT_MM) - cursor_y) * mm - h
        flow.drawOn(c, float(block.x_mm) * mm, draw_y)
        cursor_y += h / mm


def _make_on_page(db, *, document_type: str, page_type: str, blocks: dict[str, DocumentLayoutBlock], general, styles: dict):
    """Baut den onPage(canvas, doc)-Callback für einen Seitentyp. Zeichnet in dieser Reihenfolge:
    Hintergrund, dann Logo (wenn sichtbar UND ein Firmenlogo hinterlegt ist), dann Firmenkopf
    (wenn sichtbar) -- erscheinen bewusst auf JEDER Seite, wenn aktiviert (nicht nur Seite 1 wie
    beim Angebot heute), ein sinnvoller Rückfall für Installationen ohne Briefpapier.

    Hinterlässt seit 1.3.7 zusätzlich `c._erp_page_type` -- onPage läuft laut reportlab beim
    SEITENBEGINN, also bevor showPage() diese Seite am Seitenende als Snapshot sichert;
    _NumberedCanvas.save() liest das Attribut aus jedem Snapshot, um die Wiederholungszeile nur
    auf "continuation"-Seiten zu zeichnen (siehe dort)."""

    def _on_page(c, _doc):
        c._erp_page_type = page_type
        _draw_background(c, document_type=document_type, page_type=page_type, db=db)
        logo_block = blocks.get("logo")
        if logo_block is not None and logo_block.visible:
            _draw_logo(c, logo_block, general)
        header_block = blocks.get("company_header")
        if header_block is not None and header_block.visible:
            _draw_company_header(c, header_block, general, styles)

    return _on_page


def _build_once(
    *, document_type: str, title: str, story: list, footer_enabled: bool, general, styles: dict,
    blocks: dict[str, DocumentLayoutBlock], first_margins: DocumentPageMargins,
    continuation_margins: DocumentPageMargins, db, continuation_header_rows: list[tuple[str, str]] | None,
) -> BaseDocTemplate:
    """Baut EIN vollständiges PDF (frischer Buffer, frische PageTemplates/Frames -- die werden
    beim Bauen verbraucht, nicht wiederverwendbar). Gibt das BaseDocTemplate zurück, nicht nur die
    Bytes -- render_framed_pdf() braucht bei einem Entdeckungsdurchlauf zusätzlich `doc.page`
    (die dabei ermittelte Gesamtseitenzahl), die fertigen Bytes liegen in `doc._pdf_bytes`."""
    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, title=title, author=general.company_name)
    doc.addPageTemplates([
        PageTemplate(
            id="first", frames=[_build_frame(first_margins, frame_id="first")],
            onPage=_make_on_page(db, document_type=document_type, page_type="first", blocks=blocks, general=general, styles=styles),
        ),
        PageTemplate(
            id="later", frames=[_build_frame(continuation_margins, frame_id="later")],
            onPage=_make_on_page(db, document_type=document_type, page_type="continuation", blocks=blocks, general=general, styles=styles),
        ),
    ])
    continuation_header_block = blocks.get("continuation_header")
    continuation_header = None
    if continuation_header_block is not None and continuation_header_block.visible and continuation_header_rows:
        continuation_header = {
            "rows": continuation_header_rows, "margins": continuation_margins,
            "y_mm": continuation_header_block.y_mm,
        }
    doc.build(
        [NextPageTemplate("later"), *story],
        canvasmaker=partial(_NumberedCanvas, footer_enabled=footer_enabled, continuation_header=continuation_header),
    )
    doc._pdf_bytes = buf.getvalue()
    return doc


def render_framed_pdf(
    db, *, document_type: str, title: str, content_story, continuation_header_rows: list[tuple[str, str]] | None = None,
) -> bytes:
    """Baut ein vollständiges PDF: gemeinsamer Rahmen (Hintergrund/Ränder/optionale Bausteine) +
    fließender Inhalt. content_story ist entweder (wie bisher) eine fertige Flowable-Liste, oder --
    seit 1.3.5, für Inhalte, die die GESAMTSEITENZAHL bereits im Inhalt selbst brauchen (z. B. eine
    "Seite 1 / N"-Zeile im Meta-Block, siehe app/reminder_pdf.py, CLAUDE.md "Kopfbereich") -- eine
    Funktion `(total_pages: int | None) -> list`. Wird eine solche Funktion übergeben, läuft der
    Aufbau zweimal: ein erster, komplett verworfener Durchlauf (`total_pages=None`) ermittelt nur
    `doc.page` (die dann bekannte Gesamtseitenzahl), der zweite, echte Durchlauf bekommt sie als
    Parameter und liefert die tatsächlich zurückgegebenen Bytes. Bewusst KEIN Platzhalter, der auf
    dem Canvas nachträglich überschrieben wird -- zum Zeitpunkt, an dem die Gesamtzahl bekannt
    wird (`_NumberedCanvas.save()`), sind die Zeichenpositionen des Platzhaltertexts bereits als
    fertige, exakt positionierte PDF-Textoperatoren geschrieben; ein Ersetzungstext mit anderer
    Zeichenlänge würde die gerade erst behobene Rechtsbündigkeit wieder verschieben. Der doppelte
    Durchlauf kostet zwar Renderzeit, aber die eigentlich teure Arbeit (die Platypus-Layoutberechnung,
    die über Seitenumbrüche entscheidet) fällt in einem "billigeren" Zähl-Durchlauf ohnehin komplett
    genauso an -- ein Zwischenweg würde kaum etwas sparen, keiner gebaut. Kein Aufrufer außer der
    Mahnung nutzt bisher die Funktions-Variante -- eine einfache Liste verhält sich unverändert.

    document_type MUSS in RENDERERS_USING_SHARED_FRAME stehen (seit 1.3.6) -- wer einen weiteren
    Renderer auf den gemeinsamen Rahmen umstellt, muss diese Zuordnung dort zwangsläufig
    ergänzen, sonst schlägt der allererste Testaufruf sofort fehl. Das ist bewusst der Ort, an
    dem auch die Vorschau in Einstellungen → Dokumente & Layout abliest, welche Dokumenttypen
    die geteilten Einstellungen schon nutzen (siehe GET /api/document-layout/rollout-status).

    continuation_header_rows (seit 1.3.7): fertige Liste von Beschriftung/Wert-Paaren für die
    Wiederholungszeile auf Folgeseiten (z. B. Rechnungsnr./Kunden-Nr./Datum bei der Rechnung) --
    IMMER eine fertige Liste, nie eine Funktion wie content_story: die Werte selbst hängen nie
    von der Gesamtseitenzahl ab, nur die "Seite X von Y"-Ergänzung am Zeilenende tut das, und die
    zeichnet _NumberedCanvas.save() automatisch dazu (siehe dort) -- kein zweiter
    Zweidurchlauf-Mechanismus nötig. Erscheint nur, wenn der continuation_header-Baustein
    sichtbar ist UND hier tatsächlich Zeilen übergeben wurden; bewusst nie auf Seite 1 (die zeigt
    den vollen Kopfbereich bereits als Inhalt). Die vertikale Position kommt seit 1.3.12 aus dem
    Block selbst (`continuation_header_block.y_mm`, über Einstellungen → Dokumente & Layout
    editierbar) statt einer festen Konstante -- siehe CLAUDE.md, Abschnitt "Einstellbare Position
    der Wiederholungszeile"."""
    if document_type not in RENDERERS_USING_SHARED_FRAME:
        raise ValueError(
            f"Unbekannter Dokumenttyp für den gemeinsamen PDF-Rahmen: {document_type!r}. "
            "Neu in RENDERERS_USING_SHARED_FRAME (app/document_frame.py) eintragen."
        )
    general = get_or_create_general_settings(db)
    styles = build_styles()
    blocks = {b.block_type: b for b in ensure_default_layout(db, document_type) if b.block_type in FRAME_BLOCK_TYPES}
    footer_block = blocks.get("footer_text")
    footer_enabled = footer_block.visible if footer_block is not None else False

    first_margins = get_margins(db, document_type, "first")
    continuation_margins = get_margins(db, document_type, "continuation")

    def build(story: list) -> BaseDocTemplate:
        return _build_once(
            document_type=document_type, title=title, story=story, footer_enabled=footer_enabled,
            general=general, styles=styles, blocks=blocks, first_margins=first_margins,
            continuation_margins=continuation_margins, db=db, continuation_header_rows=continuation_header_rows,
        )

    if callable(content_story):
        discovery_doc = build(content_story(None))
        total_pages = discovery_doc.page
        final_doc = build(content_story(total_pages))
    else:
        final_doc = build(content_story)
    return final_doc._pdf_bytes
