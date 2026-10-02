"""Brief an den Auftraggeber als PDF (seit 1.8.40, Stufe 2b, Runde 2b-3 Teil 2; seit 1.8.44 auch die Bedenkenanzeige): Behinderungsanzeige und
Anzeige der Wiederaufnahme (app/notice_letters.py).

Dokumenttyp "notice" im gemeinsamen Rahmen (app/document_frame.py, RENDERERS_USING_SHARED_FRAME): Briefpapier,
Ränder und Wiederholungszeile wie die übrigen Dokumente, Kopf über build_din5008_header_block(). Gerendert wird
ausschließlich aus der Inhaltsstruktur (build_letter_content()) -- Empfänger, Anrede, Betreff mit Bauvorhaben und
Auftragsnummer, Einleitung, die Angaben der versiegelten Abschnitte, Vorbehalt (nur geprüft), Grußformel mit der
Unterschrift des Abschnitts (seit 1.8.41 bei der Anzeige der Wiederaufnahme "i. A." und das Büro-Konto, content
["signoff"]), "Kopie an:", Hinweis auf die Anlage, darunter die Prüfsumme des unterschriebenen Inhalts. Danach die
Fotos als Anlage.

Fotos verkleinert (Muster app/checklist_pdf.py::build_checklist_email_pdf()): stufenweise im Speicher neu
kodiert, bis das PDF unter der Anhanggrenze von 3.000.000 Bytes liegt; die Originale werden nur gelesen. Passt
es auch mit der kleinsten Stufe nicht, bleibt diese -- der Brief lässt sich dann drucken und auf anderem Weg
zustellen (der E-Mail-Versand meldet die Größe). Je Stufe liegen nur deren Fotos im Speicher (Speicherbudget,
CLAUDE.md "Produktivbetrieb").
"""

from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

from .checklist_pdf import EMAIL_PHOTO_STEPS, _EMBED_FACTOR, _image, _reduced_photo
from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_styles, ptext

DOCUMENT_TYPE = "notice"
LABEL_COL_MM = 52
PHOTO_WIDTH_MM = 120
PHOTO_MAX_HEIGHT_MM = 105
SIGNATURE_WIDTH_MM, SIGNATURE_HEIGHT_MM = 60, 22


def _de(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d.%m.%Y") if iso else ""


def render_notice_letter_pdf(db, content: dict, *, signature_png: bytes | None, photos: list[bytes],
                             watermark: str | None = None) -> bytes:
    """Brief aus der Inhaltsstruktur; photos: die (verkleinerten) Bytes in der Reihenfolge von content["photos"]."""
    styles = build_styles()
    body, small, h1 = styles["body"], styles["small"], styles["h1"]
    subject_style = ParagraphStyle("NoticeSubject", parent=body, fontName="Helvetica-Bold", fontSize=10.5, leading=14)
    content_width = frame_content_width(get_margins(db, DOCUMENT_TYPE, "first"))
    letter_date = _de(content["letter_date"])
    version = f"Fassung {content['version_no']}" if content.get("version_no") else "Vorschau"

    def items_table() -> Table:
        rows = [[Paragraph(ptext(i["label"]), body), Paragraph(ptext(i["value"]), body)] for i in content["items"]]
        table = Table(rows, colWidths=[LABEL_COL_MM * mm, content_width - LABEL_COL_MM * mm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#bbbbbb")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ]))
        return table

    def signature_block() -> list:
        sig = content["signature"]
        block = [Paragraph(ptext(content["closing"]), body), Spacer(1, 1.5 * mm)]
        if content.get("company_name"):
            block.append(Paragraph(ptext(content["company_name"]), body))
        signoff = content.get("signoff")
        if signoff and signoff.get("mode") == "i_a":
            # Seit 1.8.41 (Anzeige der Wiederaufnahme): "i. A." und das Büro-Konto, kein Unterschriftsbild -- die
            # Unterschrift im Abschnitt Wegfall bleibt interner Beleg.
            block += [Spacer(1, 8 * mm), Paragraph(ptext(f"i. A. {signoff['name']}"), body)]
            return block
        if signature_png:
            image = Image(BytesIO(signature_png), width=SIGNATURE_WIDTH_MM * mm, height=SIGNATURE_HEIGHT_MM * mm,
                          kind="proportional", hAlign="LEFT")
            block.append(image)
        else:
            block.append(Spacer(1, SIGNATURE_HEIGHT_MM * mm))
        block.append(Paragraph(ptext(sig.get("signer_name") or ""), body))
        return block

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = [("Auftragsnr.", content["order_number"]), ("Datum", letter_date)]
        if content.get("customer_number"):
            meta_rows.append(("Kunden-Nr.", content["customer_number"]))
        meta_rows.append(("Seite", page_value))
        story = list(build_din5008_header_block(
            content["sender_line"], content["recipient"]["lines"], meta_rows, styles, content_width=content_width,
        ))
        story.append(Paragraph(ptext(content["subject"]), h1))
        story.append(Paragraph(ptext(content["subject_line"]), subject_style))
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(ptext(content["salutation"]), body))
        story.append(Spacer(1, 2.5 * mm))
        story.append(Paragraph(ptext(content["intro"]), body))
        story.append(Spacer(1, 3 * mm))
        if content["items"]:
            story.append(items_table())
            story.append(Spacer(1, 5 * mm))
        if content["reservation"]["printed"]:
            story.append(Paragraph(ptext(content["reservation"]["text"]), body))
            story.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(signature_block()))
        story.append(Spacer(1, 5 * mm))
        if content["copy_to"]:
            names = "; ".join(f"{c['name']} ({c['role_label']})" for c in content["copy_to"])
            story.append(Paragraph(f"<b>Kopie an:</b> {ptext(names)}", body))
        if content["photos"]:
            count = len(content["photos"])
            story.append(Paragraph(f"<b>Anlage:</b> {count} {'Foto' if count == 1 else 'Fotos'} (verkleinert)", body))
        sig = content["signature"]
        signed_at = datetime.fromisoformat(sig["signed_at"]).strftime("%d.%m.%Y %H:%M") if sig.get("signed_at") else ""
        story.append(Spacer(1, 6 * mm))
        section = " (Abschnitt Wegfall)" if content.get("signoff") else ""
        story.append(Paragraph(ptext(
            f"Erstellt aus der {content.get('source_label', 'Behinderungsanzeige')} Nr. {content['checklist_id']} ({version}); "
            f"unterschrieben{section} am "
            f"{signed_at} Uhr. Prüfsumme (SHA-256) des unterschriebenen Inhalts: {sig.get('content_sha256') or '—'}"
        ), small))
        if photos:
            story.append(PageBreak())
            story.append(Paragraph("Anlage – Fotos", styles["h2"]))
            width = min(PHOTO_WIDTH_MM, content_width / mm)
            for index, (meta, data) in enumerate(zip(content["photos"], photos), start=1):
                story.append(KeepTogether([
                    Paragraph(ptext(f"Foto {index} von {len(photos)} – {meta['label']}"), small), Spacer(1, 1.5 * mm),
                    _image(data, width, max_height_mm=PHOTO_MAX_HEIGHT_MM), Spacer(1, 5 * mm),
                ]))
        return story

    continuation = [(f"{content['subject']} zu Auftrag", content["order_number"]), ("Datum", letter_date)]
    return render_framed_pdf(
        db, document_type=DOCUMENT_TYPE, title=f"{content['subject']} - {content['order_number']}",
        content_story=build_story, continuation_header_rows=continuation, watermark_text=watermark,
    )


def build_notice_letter_pdf(db, content: dict, *, signature_path, photo_paths: list, watermark: str | None = None) -> bytes:
    """Das PDF mit verkleinerten Fotos unter der Anhanggrenze (siehe Moduldocstring)."""
    from .email_sending import MAX_ATTACHMENT_BYTES

    try:
        signature_png = signature_path.read_bytes()
    except FileNotFoundError:
        signature_png = None
    if not photo_paths:
        return render_notice_letter_pdf(db, content, signature_png=signature_png, photos=[], watermark=watermark)
    pdf = None
    for max_px, quality in EMAIL_PHOTO_STEPS:
        reduced = [_reduced_photo(path, max_px, quality) for path in photo_paths]
        if sum(len(b) for b in reduced) * _EMBED_FACTOR > MAX_ATTACHMENT_BYTES and (max_px, quality) != EMAIL_PHOTO_STEPS[-1]:
            continue
        pdf = render_notice_letter_pdf(db, content, signature_png=signature_png, photos=reduced, watermark=watermark)
        if len(pdf) <= MAX_ATTACHMENT_BYTES:
            return pdf
    return pdf
