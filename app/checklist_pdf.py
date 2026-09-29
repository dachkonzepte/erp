"""PDF einer abgeschlossenen Checkliste (seit 1.8.4, Modul "checklisten") über den gemeinsamen
Rahmen (render_framed_pdf(), document_type="checklist" -- Briefpapier, Ränder, Fußzeile wie jedes
andere Dokument, siehe docs/archiv/pdf-architektur.md).

Nur abgeschlossene Checklisten, bei jedem Abruf neu erzeugt (Muster Einsatzbericht). Alles, was
im Dokument steht, stammt aus eingefrorenen Daten: Vorlagenfassung (unveränderlich),
Schnappschüsse der Checkliste (Bezeichnung, Kontext), Antworten/Anhänge (nach dem Abschluss
unveränderlich) und im Kontext Auftrag die Kundenanschrift aus dem Auftrag (ebenfalls ein
unveränderlicher Schnappschuss) -- nie live aus Kunde/Objekt/Gerät gelesen. Kontext Betriebsmittel
und Betrieb ohne Anschriftenfeld.

Speicherbudget (Server 4 GB, CLAUDE.md "Produktivbetrieb"): Fotos liegen bereits auf 1600 px
verkleinert vor (app/image_storage.py), je Feld höchstens max_count bzw. 20; reportlab liest die
Datei erst beim Zeichnen, jeweils einzeln."""

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .berlin_time import to_berlin
from .checklists import _answer_value, attachment_path
from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_object_address_block, build_styles, ptext
from .models import Checklist, Order
from .settings import get_or_create_general_settings

DOCUMENT_TYPE = "checklist"
CONTEXT_LABELS = {"auftrag": "Auftrag", "objekt": "Objekt", "betriebsmittel": "Betriebsmittel", "betrieb": "Betrieb"}
YES_NO_LABELS = {"ja": "Ja", "nein": "Nein", "entfaellt": "Entfällt"}
PHOTO_WIDTH_MM = 70
SIGNATURE_WIDTH_MM, SIGNATURE_HEIGHT_MM = 60, 25
ANSWER_COL_MM = 70  # Antwortspalte; die Frage nimmt den Rest des Satzspiegels
_ZERO_OUTER_TABLE_PADDING = [("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (-1, 0), (-1, -1), 0)]


def _employee_name(e) -> str | None:
    if e is None:
        return None
    return " ".join(p for p in (e.first_name, e.last_name) if p) or None


def format_answer(field, answer) -> str:
    """Anzeigetext einer Antwort -- dieselbe Lesart wie die Ausfüllseite (checklist.html)."""
    value = _answer_value(answer, field) if answer is not None else None
    if value in (None, "", []):
        return "—"
    t = field.field_type
    if t == "ja_nein":
        return YES_NO_LABELS.get(value, value)
    if t == "auswahl":
        labels = {o.option_key: o.label for o in field.options}
        return ", ".join(labels.get(k, k) for k in (value if isinstance(value, list) else [value]))
    if t == "zahl":
        text = f"{value.normalize():f}".replace(".", ",")
        return f"{text} {field.unit}" if field.unit else text
    if t == "datum":
        return answer.value_date.strftime("%d.%m.%Y")
    if t == "datum_uhrzeit":
        return answer.value_datetime.strftime("%d.%m.%Y %H:%M")
    return str(value)


def _image(path, width_mm: float, *, max_height_mm: float | None = None):
    """Verzerrungsfrei mit fester Breite (Seitenverhältnis aus der Datei); optional in der Höhe
    begrenzt (Unterschriften)."""
    from PIL import Image as PILImage  # lokal: nur hier gebraucht

    with PILImage.open(path) as im:
        ratio = (im.height / im.width) if im.width else 1
    width = width_mm * mm
    height = width * ratio
    if max_height_mm is not None and height > max_height_mm * mm:
        height = max_height_mm * mm
        width = height / ratio if ratio else width
    image = Image(str(path), width=width, height=height)
    image.hAlign = "LEFT"  # bündig mit Überschrift und Beschriftung (Standard wäre zentriert)
    return image


def build_checklist_pdf(db, checklist: Checklist) -> bytes:
    if checklist.status != "abgeschlossen":
        raise ValueError("Nur abgeschlossene Checklisten können als PDF erzeugt werden.")
    general = get_or_create_general_settings(db)
    styles = build_styles()
    body, small, h1 = styles["body"], styles["small"], styles["h1"]
    # Überschriften bleiben mit dem Folgenden zusammen (keepWithNext) -- keine Abschnitts- oder
    # Feldüberschrift allein am Seitenende. Feldüberschrift ohne den Einzug von styles["h3"]
    # (der ist für Tabellenzellen des Einsatzberichts gedacht).
    h2 = ParagraphStyle("ChecklistH2", parent=styles["h2"], keepWithNext=1)
    h3 = ParagraphStyle("ChecklistH3", parent=styles["h3"], leftIndent=0, keepWithNext=1)
    content_width = frame_content_width(get_margins(db, DOCUMENT_TYPE, "first"))
    content_width_mm = content_width / mm

    order = db.get(Order, checklist.order_id) if checklist.context_type == "auftrag" and checklist.order_id else None
    sender_line, recipient_lines = None, []
    if order is not None:
        sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
        sender_line = " - ".join(x for x in sender_parts if x)
        recipient_lines = [order.customer_name] + (order.customer_address.split(", ", 1) if order.customer_address else [])

    completed = to_berlin(checklist.completed_at)  # Zeitstempel sind UTC, gedruckt wird Ortszeit
    creator = _employee_name(checklist.created_by_employee)
    completer = _employee_name(checklist.completed_by_employee)
    context_label = CONTEXT_LABELS.get(checklist.context_type, checklist.context_type)
    fields = checklist.template_version.fields
    answers = {a.template_field_id: a for a in checklist.answers}
    attachments: dict[int, list] = {}
    for a in checklist.attachments:
        attachments.setdefault(a.template_field_id, []).append(a)

    def answer_table(rows: list[list]) -> Table:
        question_width = content_width - ANSWER_COL_MM * mm
        table = Table(rows, colWidths=[question_width, ANSWER_COL_MM * mm])
        table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#bbbbbb")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
            *_ZERO_OUTER_TABLE_PADDING,
        ]))
        return table

    def build_story(total_pages: int | None) -> list:
        meta_rows = [("Checkliste", f"Nr. {checklist.id}"), ("Bereich", context_label)]
        if order is not None:
            meta_rows.append(("Auftragsnr.", order.order_number))
            if order.customer_number:
                meta_rows.append(("Kunden-Nr.", order.customer_number))
        if completed:
            meta_rows.append(("Abgeschlossen", completed.strftime("%d.%m.%Y")))
        meta_rows.append(("Seite", f"1 / {total_pages}" if total_pages is not None else "1 / …"))
        story = list(build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles, content_width=content_width))
        if order is not None:
            story += build_object_address_block(
                order.property_name, [x for x in str(order.property_address or "").splitlines() if x], styles,
            )

        story.append(Paragraph(ptext(checklist.template_label_snapshot), h1))
        if checklist.context_type != "auftrag":
            context_line = " – ".join(x for x in (checklist.context_label_snapshot, checklist.context_detail_snapshot) if x)
            story.append(Paragraph(ptext(f"{context_label}: {context_line}" if context_line else context_label), body))
        who = [f"Angelegt von {creator}" if creator else None,
               f"abgeschlossen am {completed.strftime('%d.%m.%Y %H:%M')} Uhr" if completed else None,
               f"von {completer}" if completer and completer != creator else None,
               f"Vorlagenfassung {checklist.template_version.version_no}"]
        story.append(Paragraph(ptext(" · ".join(x for x in who if x)), small))
        story.append(Spacer(1, 5 * mm))

        rows: list[list] = []
        group = None

        def flush_rows() -> None:
            if rows:
                story.append(answer_table(list(rows)))
                story.append(Spacer(1, 3 * mm))
                rows.clear()

        for field in fields:
            if field.group_name and field.group_name != group:
                flush_rows()
                story.append(Paragraph(ptext(field.group_name), h2))
                group = field.group_name
            if field.field_type == "hinweis":
                flush_rows()
                text = f"<b>{ptext(field.label)}</b>" + (f"<br/>{ptext(field.help_text)}" if field.help_text else "")
                story.append(Paragraph(text, small))
                story.append(Spacer(1, 3 * mm))
            elif field.field_type == "foto":
                flush_rows()
                photos = attachments.get(field.id, [])
                story.append(Paragraph(ptext(field.label), h3))  # keepWithNext: mit dem ersten Foto
                if not photos:
                    story.append(Paragraph("Keine Fotos.", small))
                width = min(PHOTO_WIDTH_MM, content_width_mm)
                for photo in photos:
                    story.append(_image(attachment_path(photo), width))
                    story.append(Spacer(1, 2 * mm))
                story.append(Spacer(1, 2 * mm))
            elif field.field_type == "unterschrift":
                flush_rows()
                story.append(Paragraph(ptext(field.label + (f" ({field.signer_label})" if field.signer_label else "")), h3))
                signatures = attachments.get(field.id, [])
                if not signatures:
                    story.append(Paragraph("Nicht unterschrieben.", small))
                for sig in signatures:  # je Unterschrift Bild + Name zusammen, nie getrennt
                    story.append(KeepTogether([
                        _image(attachment_path(sig), SIGNATURE_WIDTH_MM, max_height_mm=SIGNATURE_HEIGHT_MM),
                        Paragraph(ptext(f"{sig.signer_name or ''}, {to_berlin(sig.created_at).strftime('%d.%m.%Y %H:%M')} Uhr"), small),
                        Spacer(1, 3 * mm),
                    ]))
                story.append(Spacer(1, 2 * mm))
            else:
                rows.append([Paragraph(ptext(field.label), body), Paragraph(ptext(format_answer(field, answers.get(field.id))), body)])
        flush_rows()
        return story

    continuation = [("Checkliste", f"Nr. {checklist.id}")]
    if order is not None:
        continuation.append(("Auftragsnr.", order.order_number))
    if completed:
        continuation.append(("Abgeschlossen", completed.strftime("%d.%m.%Y")))
    return render_framed_pdf(
        db, document_type=DOCUMENT_TYPE, title=f"{checklist.template_label_snapshot} – {checklist.context_label_snapshot or context_label}",
        content_story=build_story, continuation_header_rows=continuation,
    )
