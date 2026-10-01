"""Vertrag zum Auftrag als PDF (seit 1.8.32, Stufe 2b, Runde 2b-1b Teil 1).

Dokumenttyp "contract" im gemeinsamen Rahmen (app/document_frame.py, RENDERERS_USING_SHARED_FRAME):
Briefpapier, Ränder und Wiederholungszeile wie Auftrag und Rechnung, Kopfbereich über
build_din5008_header_block(). Inhalt: Titel und Abschnitte der Vorlage für die Vertragsgrundlage des
Auftrags, Platzhalter ersetzt, Abschnitte "nur bei Verbrauchern" nur bei einem Verbraucher. Danach das
Angebot als Anlage (eigenes PDF aus build_quote_framed_pdf(), angehängt).

Ist die Vorlage nicht rechtlich geprüft, steht CONTRACT_WATERMARK_TEXT quer auf jeder Seite -- auch auf
den Seiten des angehängten Angebots.

Bewusst ohne Ablage und ohne eigene Nummer: Festschreiben, Versand und Unterschrift folgen in Teil 2.
Alles wird bei jedem Aufruf live gelesen.
"""

from io import BytesIO

import pypdfium2 as pdfium
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from .berlin_time import berlin_today
from .contract_templates import (
    CONTRACT_WATERMARK_TEXT, DEFAULT_CONTRACT_TITLE, contract_placeholder_values, fill, get_template_row,
    order_customer_is_consumer, template_has_content, template_is_reviewed, visible_sections,
)
from .contract_basis import contract_basis_label
from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_object_address_block, build_styles, ptext
from .models import Order, OrderContract
from .orders import order_to_dict
from .projects import load_quote
from .quote_framed_pdf import build_quote_framed_pdf
from .settings import get_or_create_general_settings

CHECKBOX_SIZE = 3.6 * mm
CHECKBOX_COL_WIDTH = 7 * mm


class _Checkbox(Flowable):
    """Leeres Ankreuzfeld -- gezeichnet, weil Helvetica kein Kästchen-Zeichen hat (ein "☐" im Text
    erschiene als fehlendes Zeichen)."""

    def __init__(self, size: float = CHECKBOX_SIZE):
        super().__init__()
        self.size = size

    def wrap(self, avail_width, avail_height):
        return self.size, self.size

    def draw(self):
        self.canv.setLineWidth(0.8)
        self.canv.rect(0, 0, self.size, self.size, stroke=1, fill=0)


def _merge(parts: list[bytes]) -> bytes:
    dest = pdfium.PdfDocument(parts[0])
    sources = []
    try:
        for extra in parts[1:]:
            source = pdfium.PdfDocument(extra)
            sources.append(source)
            dest.import_pages(source)
        buf = BytesIO()
        dest.save(buf)
        return buf.getvalue()
    finally:
        for source in sources:
            source.close()
        dest.close()


def build_contract_pdf(db, order: Order, contract: OrderContract) -> bytes:
    """Wirft ValueError, wenn es für die (heutige) Vertragsgrundlage des Auftrags keine Vorlage mit
    Inhalt gibt -- etwa nachdem die Grundlage am Auftrag geändert wurde."""
    template = get_template_row(db, order.contract_basis)
    if not template_has_content(template):
        raise ValueError(
            f"Für die Vertragsgrundlage „{contract_basis_label(order.contract_basis)}“ gibt es keine "
            "Vertragsvorlage (Einstellungen → Vertragsvorlagen)."
        )
    watermark = None if template_is_reviewed(template) else CONTRACT_WATERMARK_TEXT
    data = order_to_dict(order, db, include_sync_state=False)
    values = contract_placeholder_values(db, order, contract, data=data)
    sections = visible_sections(template, is_consumer=order_customer_is_consumer(order))
    general = get_or_create_general_settings(db)
    styles = build_styles()
    body, h1, h2 = styles["body"], styles["h1"], styles["h2"]
    heading_style = ParagraphStyle("ContractHeading", parent=h2, keepWithNext=1)

    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    sender_line = " - ".join(x for x in sender_parts if x)
    # Schnappschuss am Auftrag "Straße, PLZ Ort" -- wie order_pdf.py an der bekannten Fuge geteilt.
    recipient_lines = [order.customer_name] + (order.customer_address.split(", ", 1) if order.customer_address else [])
    content_width = frame_content_width(get_margins(db, "contract", "first"))
    title = fill(template.title, values).strip() or DEFAULT_CONTRACT_TITLE

    def section_flowables(section) -> list:
        heading = fill(section.heading, values).strip()
        text = fill(section.body_text, values).strip("\n").rstrip()
        result = []
        if section.with_checkbox:
            if heading and text:
                result.append(Paragraph(ptext(heading), heading_style))
            label = ptext(text) if text else f"<b>{ptext(heading)}</b>"
            row = Table([[_Checkbox(), Paragraph(label, body)]], colWidths=[CHECKBOX_COL_WIDTH, content_width - CHECKBOX_COL_WIDTH])
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (0, 0), 2.2),
                ("TOPPADDING", (1, 0), (1, 0), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            result.append(row)
        else:
            if heading:
                result.append(Paragraph(ptext(heading), heading_style))
            if text:
                result.append(Paragraph(ptext(text), body))
        result.append(Spacer(1, 4 * mm))
        return result

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = [
            ("Auftragsnr.", order.order_number), ("Auftragsdatum", order.order_date.strftime("%d.%m.%Y")),
            ("Ihr Angebot", order.quote_number_snapshot), ("Projekt", data["project_number"]),
        ]
        if order.customer_number:
            meta_rows.append(("Kunden-Nr.", order.customer_number))
        meta_rows += [("Stand", berlin_today().strftime("%d.%m.%Y")), ("Seite", page_value)]
        story = list(build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles, content_width=content_width))
        story += build_object_address_block(
            order.property_name, [x for x in str(order.property_address or "").splitlines() if x], styles,
        )
        story.append(Paragraph(ptext(title), h1))
        for section in sections:
            story += section_flowables(section)
        quote_date = values["{angebotsdatum}"]
        story.append(Paragraph(
            ptext(f"Anlage: Angebot {order.quote_number_snapshot}" + (f" vom {quote_date}" if quote_date else "")), body,
        ))
        return story

    continuation_header_rows = [("Vertrag zu Auftrag", order.order_number), ("Kunde", order.customer_name)]
    contract_pdf = render_framed_pdf(
        db, document_type="contract", title=f"{title} - {order.order_number}", content_story=build_story,
        continuation_header_rows=continuation_header_rows, watermark_text=watermark,
    )
    quote = load_quote(db, order.source_quote_id)
    if quote is None:
        return contract_pdf
    return _merge([contract_pdf, build_quote_framed_pdf(db, quote, watermark_text=watermark)])
