"""Vertrag zum Auftrag als PDF (seit 1.8.32, Stufe 2b, Runde 2b-1b Teil 1).

Dokumenttyp "contract" im gemeinsamen Rahmen (app/document_frame.py, RENDERERS_USING_SHARED_FRAME):
Briefpapier, Ränder und Wiederholungszeile wie Auftrag und Rechnung, Kopfbereich über
build_din5008_header_block(). Inhalt: Titel und Abschnitte der Vorlage für die Vertragsgrundlage des
Auftrags, Platzhalter ersetzt, Abschnitte "nur bei Verbrauchern" nur bei einem Verbraucher. Danach das
Angebot als Anlage (eigenes PDF, angehängt).

Seit 1.8.33 rendert render_contract_pdf() aus der Inhaltsstruktur von
app/contract_templates.py::contract_content(): der Entwurf (build_contract_pdf()) mit dem Inhalt von
heute und dem heutigen Stand des Angebots, das Festschreiben (app/contract_versions.py) mit genau dem
Inhalt, den es einfriert, und der gewählten Anlage. Eine festgeschriebene Fassung wird danach nie neu
gerendert -- sie liegt in der Ablage.

Ist die Vorlage nicht rechtlich geprüft, steht CONTRACT_WATERMARK_TEXT quer auf jeder Seite des
Entwurfs -- auch auf den Seiten des angehängten Angebots. Festgeschrieben wird nur eine geprüfte
Vorlage, eine Fassung trägt das Wasserzeichen also nie.

Seit 1.8.34 außerdem das Unterschriftsblatt (render_signature_sheet_pdf()): eine Seite im selben Rahmen mit
der unterschriebenen Fassung samt PDF-Prüfsumme, dem Stand der Ankreuzfelder, den beiden Unterschriften und
der Prüfsumme des unterschriebenen Inhalts (app/contract_signatures.py legt es in der Ablage ab).

Größe (gemessen 1.8.33 mit dem echten Briefpapier, JPEG 1655×2340, 104 KB): Vertrag mit 13 Abschnitten
und Angebot mit 30 Positionen 237 KB, als PNG-Briefpapier 656 KB -- Vertrag und Anlage betten das
Briefpapier je einmal ein, bis zur Versandgrenze von 3 MB bleibt viel Luft. Ein gemeinsamer
Renderdurchgang wäre ohnehin nur für den heutigen Stand möglich, nicht für die versendete Fassung aus
der Ablage.
"""

from datetime import date, datetime
from io import BytesIO

import pypdfium2 as pdfium
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .berlin_time import berlin_today
from .contract_templates import CONTRACT_WATERMARK_TEXT, contract_content
from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_object_address_block, build_styles, ptext
from .models import Order, OrderContract
from .projects import load_quote
from .quote_framed_pdf import build_quote_framed_pdf

CHECKBOX_SIZE = 3.6 * mm
CHECKBOX_COL_WIDTH = 7 * mm


class _Checkbox(Flowable):
    """Ankreuzfeld -- gezeichnet, weil Helvetica kein Kästchen-Zeichen hat (ein "☐" im Text erschiene als
    fehlendes Zeichen). Leer im Vertrag; seit 1.8.34 auf dem Unterschriftsblatt mit Kreuz, wenn angekreuzt."""

    def __init__(self, size: float = CHECKBOX_SIZE, checked: bool = False):
        super().__init__()
        self.size = size
        self.checked = checked

    def wrap(self, avail_width, avail_height):
        return self.size, self.size

    def draw(self):
        self.canv.setLineWidth(0.8)
        self.canv.rect(0, 0, self.size, self.size, stroke=1, fill=0)
        if self.checked:
            inset = self.size * 0.2
            self.canv.setLineWidth(1.1)
            self.canv.line(inset, inset, self.size - inset, self.size - inset)
            self.canv.line(inset, self.size - inset, self.size - inset, inset)


def merge_pdfs(parts: list[bytes]) -> bytes:
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


def _de(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d.%m.%Y") if iso else ""


def attachment_line(content: dict) -> str:
    """"Anlage: Angebot … vom …" -- mit Fassung, sobald festgeschrieben (content["attachment"])."""
    line = f"Anlage: Angebot {content['quote_number']}" + (f" vom {content['quote_date']}" if content["quote_date"] else "")
    attachment = content.get("attachment")
    if attachment and attachment["kind"] == "versendet":
        line += f", in der am {_de(attachment['sent_on'])} versendeten Fassung"
    elif attachment and attachment["kind"] == "aktuell":
        line += f", Stand {_de(content['stand'])}"
    return line


def render_contract_pdf(
    db, content: dict, *, attachment_pdf: bytes | None, version_label: str, stand: date,
    watermark: str | None = None,
) -> bytes:
    """Vertrag aus der Inhaltsstruktur rendern und die Anlage anhängen (falls vorhanden)."""
    styles = build_styles()
    body, h1, h2 = styles["body"], styles["h1"], styles["h2"]
    heading_style = ParagraphStyle("ContractHeading", parent=h2, keepWithNext=1)
    content_width = frame_content_width(get_margins(db, "contract", "first"))

    def section_flowables(section: dict) -> list:
        heading, text = section["heading"], section["text"]
        result = []
        if section["with_checkbox"]:
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
            ("Auftragsnr.", content["order_number"]), ("Auftragsdatum", _de(content["order_date"])),
            ("Ihr Angebot", content["quote_number"]), ("Projekt", content["project_number"]),
        ]
        if content["customer_number"]:
            meta_rows.append(("Kunden-Nr.", content["customer_number"]))
        meta_rows += [("Fassung", version_label), ("Stand", stand.strftime("%d.%m.%Y")), ("Seite", page_value)]
        story = list(build_din5008_header_block(
            content["sender_line"], content["recipient_lines"], meta_rows, styles, content_width=content_width,
        ))
        story += build_object_address_block(content["property_name"], content["property_lines"], styles)
        story.append(Paragraph(ptext(content["title"]), h1))
        for section in content["sections"]:
            story += section_flowables(section)
        story.append(Paragraph(ptext(attachment_line(content)), body))
        return story

    continuation_header_rows = [
        ("Vertrag zu Auftrag", content["order_number"]), ("Fassung", version_label),
        ("Kunde", content["recipient_lines"][0] if content["recipient_lines"] else ""),
    ]
    contract_pdf = render_framed_pdf(
        db, document_type="contract", title=f"{content['title']} - {content['order_number']}",
        content_story=build_story, continuation_header_rows=continuation_header_rows, watermark_text=watermark,
    )
    return contract_pdf if attachment_pdf is None else merge_pdfs([contract_pdf, attachment_pdf])


SIGNATURE_BOX_WIDTH = 70 * mm
SIGNATURE_BOX_HEIGHT = 28 * mm


def _signature_cell(label: str, png: bytes | None, name: str | None, styles) -> list:
    cell = [Paragraph(f"<b>{ptext(label)}</b>", styles["body"]), Spacer(1, 2 * mm)]
    if png:
        cell.append(Image(BytesIO(png), width=SIGNATURE_BOX_WIDTH, height=SIGNATURE_BOX_HEIGHT, kind="proportional", hAlign="LEFT"))
    else:
        cell.append(Spacer(1, SIGNATURE_BOX_HEIGHT))
    line = Table([[""]], colWidths=[SIGNATURE_BOX_WIDTH], rowHeights=[1])
    line.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.6, "#555555"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    line.hAlign = "LEFT"
    cell += [line, Paragraph(ptext(name or ""), styles["body"])]
    return cell


def render_signature_sheet_pdf(
    db, content: dict, signed: dict, *, content_sha256: str, customer_png: bytes | None, company_png: bytes | None,
    recorded_local: datetime,
) -> bytes:
    """Unterschriftsblatt zu einer festgeschriebenen Fassung (seit 1.8.34). content: der eingefrorene Inhalt
    der Fassung; signed: der unterschriebene Inhalt (app/contract_signatures.py), content_sha256 seine
    Prüfsumme -- das Blatt druckt nur, was dort steht (die Bilder sind die, deren Prüfsumme darin steht)."""
    styles = build_styles()
    body, h1, h2 = styles["body"], styles["h1"], styles["h2"]
    mono = ParagraphStyle("ContractSha", parent=body, fontName="Courier", fontSize=8.5, leading=11)
    content_width = frame_content_width(get_margins(db, "contract", "first"))
    signed_on = date.fromisoformat(signed["signed_on"])
    version_label = str(signed["version_no"])
    firm = (content.get("placeholders") or {}).get("{firmenname}") or "Auftragnehmer"
    when = f"{recorded_local:%d.%m.%Y} um {recorded_local:%H:%M} Uhr"

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = [("Auftragsnr.", content["order_number"]), ("Vertrag", f"Fassung {version_label}")]
        if content["customer_number"]:
            meta_rows.append(("Kunden-Nr.", content["customer_number"]))
        meta_rows += [("Unterschrieben am", signed_on.strftime("%d.%m.%Y")), ("Seite", page_value)]
        story = list(build_din5008_header_block(
            content["sender_line"], content["recipient_lines"], meta_rows, styles, content_width=content_width,
        ))
        story.append(Paragraph("Unterschriftsblatt", h1))
        consumer = " Verbrauchervertrag." if signed["is_consumer"] else ""
        story.append(Paragraph(ptext(
            f"Zum {content['title']} zu Auftrag {content['order_number']}, Fassung {version_label}, festgeschrieben am "
            f"{_de(content['stand'])}. Vertragsgrundlage: {content['basis_label']}.{consumer}"
        ), body))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("Unterschrieben wurde genau diese Fassung. Ihr PDF in der Ablage hat die Prüfsumme (SHA-256):", body))
        story.append(Paragraph(signed["pdf_sha256"], mono))
        story.append(Spacer(1, 4 * mm))
        if signed["checkboxes"]:
            story.append(Paragraph("Ankreuzfelder (vom Kunden beim Unterschreiben gesetzt)", h2))
            for box in signed["checkboxes"]:
                label = " – ".join(ptext(x) for x in (box["heading"], box["text"]) if x)
                state = "angekreuzt" if box["checked"] else "nicht angekreuzt"
                row = Table([[_Checkbox(checked=box["checked"]), Paragraph(f"{label} <b>({state})</b>", body)]],
                            colWidths=[CHECKBOX_COL_WIDTH, content_width - CHECKBOX_COL_WIDTH])
                row.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (0, 0), 2.2),
                    ("TOPPADDING", (1, 0), (1, 0), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(row)
            story.append(Spacer(1, 4 * mm))
        half = content_width / 2
        customer = signed.get("customer") or {}
        company = signed.get("company") or {}
        table = Table([[
            _signature_cell("Auftraggeber", customer_png, customer.get("name"), styles),
            _signature_cell(f"Auftragnehmer – {firm}", company_png, company.get("name"), styles),
        ]], colWidths=[half, half])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(KeepTogether([Paragraph("Unterschriften", h2), table]))
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(ptext(
            f"Unterschrieben auf dem Gerät am {when}, erfasst von {signed['recorded_by']}. "
            "Prüfsumme des unterschriebenen Inhalts (SHA-256):"
        ), body))
        story.append(Paragraph(content_sha256, mono))
        return story

    continuation_header_rows = [("Unterschriftsblatt zu Auftrag", content["order_number"]), ("Fassung", version_label)]
    return render_framed_pdf(
        db, document_type="contract", title=f"Unterschriftsblatt - {content['order_number']}",
        content_story=build_story, continuation_header_rows=continuation_header_rows,
    )


def build_contract_pdf(db, order: Order, contract: OrderContract) -> bytes:
    """Entwurfs-PDF: alles live, die Anlage ist der heutige Stand des Angebots. Wirft ValueError, wenn
    es für die (heutige) Vertragsgrundlage des Auftrags keine Vorlage mit Inhalt gibt -- etwa nachdem
    die Grundlage am Auftrag geändert wurde."""
    content = contract_content(db, order, contract)
    watermark = None if content["template"]["reviewed"] else CONTRACT_WATERMARK_TEXT
    quote = load_quote(db, order.source_quote_id)
    attachment = build_quote_framed_pdf(db, quote, watermark_text=watermark) if quote is not None else None
    return render_contract_pdf(db, content, attachment_pdf=attachment, version_label="Entwurf",
                               stand=berlin_today(), watermark=watermark)
