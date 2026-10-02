"""PDF einer abgeschlossenen Checkliste (seit 1.8.4, Modul "checklisten") über den gemeinsamen
Rahmen (render_framed_pdf(), document_type="checklist" -- Briefpapier, Ränder, Fußzeile wie jedes
andere Dokument, siehe docs/archiv/pdf-architektur.md).

Unter jeder Unterschrift steht, was sie versiegelt, ihre Prüfsumme und (seit 1.8.14) ob der
aktuelle Inhalt noch dazu passt -- eine Änderung an der Sperre vorbei, etwa direkt in der
Datenbank, erscheint dort samt der betroffenen Felder. Dasselbe am Ende für den Abschluss, der
seit 1.8.15 alle Angaben samt Unterschriften versiegelt.

Nur abgeschlossene Checklisten, bei jedem Abruf neu erzeugt (Muster Einsatzbericht). Alles, was
im Dokument steht, stammt aus eingefrorenen Daten: Vorlagenfassung (unveränderlich),
Schnappschüsse der Checkliste (Bezeichnung, Kontext), Antworten/Anhänge (nach dem Abschluss
unveränderlich) und im Kontext Auftrag die Kundenanschrift aus dem Auftrag (ebenfalls ein
unveränderlicher Schnappschuss) -- nie live aus Kunde/Objekt/Gerät gelesen. Kontext Betriebsmittel
und Betrieb ohne Anschriftenfeld.

Speicherbudget (Server 4 GB, CLAUDE.md "Produktivbetrieb"): Fotos liegen bereits auf 1600 px
verkleinert vor (app/image_storage.py), je Feld höchstens max_count bzw. 20; reportlab liest die
Datei erst beim Zeichnen, jeweils einzeln.

Versand per E-Mail (seit 1.8.20, build_checklist_email_pdf()): dasselbe Dokument, die Fotos aber im
Speicher neu verkleinert, bis das PDF unter der Anhanggrenze von 3.000.000 Bytes liegt
(app/email_sending.py::MAX_ATTACHMENT_BYTES). Die Originale bleiben unverändert -- sie werden nur
gelesen, nie geschrieben; die Prüfsummen der Unterschriften und des Abschlusses beziehen sich auf sie,
und das Dokument sagt das. Der Download (PDF-Knopf) bleibt in voller Auflösung."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .berlin_time import to_berlin
from .checklists import (
    CLOSED_STATUSES, VOID_STATUS, _answer_value, active_attachments, attachment_path, check_completion, check_signature,
)
from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_object_address_block, build_styles, ptext
from .models import Checklist, Order
from .settings import load_general_settings

DOCUMENT_TYPE = "checklist"
CONTEXT_LABELS = {"auftrag": "Auftrag", "objekt": "Objekt", "betriebsmittel": "Betriebsmittel", "betrieb": "Betrieb"}
YES_NO_LABELS = {"ja": "Ja", "nein": "Nein", "entfaellt": "Entfällt"}
PHOTO_WIDTH_MM = 70
# Stufen für das Versand-PDF: längste Kante (px), JPEG-Qualität. Eine Stufe wird nur gerendert, wenn
# ihre Fotos zusammen überhaupt noch unter die Grenze passen können; reportlab bettet Bilder
# ASCII85-kodiert ein (4 Bytes werden 5 Zeichen), daher der Faktor.
EMAIL_PHOTO_STEPS = ((1600, 80), (1280, 75), (1024, 70), (800, 65), (640, 60), (480, 55), (360, 50))
_EMBED_FACTOR = 1.25
EMAIL_PHOTO_NOTE = ("Fotos für den Versand per E-Mail verkleinert. Die Originale liegen unverändert im ERP; "
                    "die Prüfsummen oben beziehen sich auf sie.")
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


def _image(source, width_mm: float, *, max_height_mm: float | None = None):
    """Verzerrungsfrei mit fester Breite (Seitenverhältnis aus der Datei); optional in der Höhe
    begrenzt (Unterschriften). source: Pfad oder (seit 1.8.20) die Bytes eines verkleinerten Fotos."""
    from PIL import Image as PILImage  # lokal: nur hier gebraucht

    with PILImage.open(BytesIO(source) if isinstance(source, bytes) else source) as im:
        ratio = (im.height / im.width) if im.width else 1
    width = width_mm * mm
    height = width * ratio
    if max_height_mm is not None and height > max_height_mm * mm:
        height = max_height_mm * mm
        width = height / ratio if ratio else width
    image = Image(BytesIO(source) if isinstance(source, bytes) else str(source), width=width, height=height)
    image.hAlign = "LEFT"  # bündig mit Überschrift und Beschriftung (Standard wäre zentriert)
    return image


def _reduced_photo(path, max_px: int, quality: int) -> bytes:
    """Das Foto neu verkleinert, nur im Speicher -- die Datei selbst wird nur gelesen."""
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def build_checklist_email_pdf(db, checklist: Checklist) -> bytes:
    """Das PDF für den Versand per E-Mail: höchstens MAX_ATTACHMENT_BYTES, Fotos stufenweise
    kleiner (EMAIL_PHOTO_STEPS). Je Stufe liegen nur deren Fotos im Speicher. Passt es auch mit der
    kleinsten Stufe nicht, ValueError mit dem Hinweis auf einen anderen Zustellweg."""
    from .email_sending import MAX_ATTACHMENT_BYTES

    photos = [a for a in active_attachments(checklist) if a.kind == "foto"]
    for max_px, quality in EMAIL_PHOTO_STEPS:
        reduced = {a.id: _reduced_photo(attachment_path(a), max_px, quality) for a in photos}
        if sum(len(b) for b in reduced.values()) * _EMBED_FACTOR > MAX_ATTACHMENT_BYTES:
            continue
        pdf = build_checklist_pdf(db, checklist, photo_bytes=reduced)
        if len(pdf) <= MAX_ATTACHMENT_BYTES:
            return pdf
    raise ValueError(
        "Die Checkliste ist auch mit stark verkleinerten Fotos größer als 3 MB und kann nicht per E-Mail "
        "versendet werden. Bitte als PDF herunterladen und auf anderem Weg zustellen (danach unter "
        "„Zustellung nachtragen“ festhalten)."
    )


def build_checklist_pdf(db, checklist: Checklist, *, photo_bytes: dict[int, bytes] | None = None) -> bytes:
    """photo_bytes (seit 1.8.20, nur build_checklist_email_pdf()): je Foto-ID die verkleinerten
    Bytes statt der Datei, dazu ein Hinweis im Dokument."""
    if checklist.status not in CLOSED_STATUSES:  # seit 1.8.41 auch "gegenstandslos" -- bleibt als Beleg
        raise ValueError("Nur abgeschlossene Checklisten können als PDF erzeugt werden.")
    voided = checklist.status == VOID_STATUS
    general = load_general_settings(db)
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
    for a in active_attachments(checklist):  # verworfene Unterschriften gehören nicht ins Dokument
        attachments.setdefault(a.template_field_id, []).append(a)
    # Einmal je PDF geprüft (build_story läuft für "Seite 1/N" zweimal), jede Fotodatei einmal gelesen.
    photo_hashes: dict = {}
    seals = {a.id: check_signature(checklist, a, photo_hashes)
             for items in attachments.values() for a in items if a.kind == "unterschrift"}
    completion = check_completion(checklist, photo_hashes)

    def seal_paragraph(check: dict) -> Paragraph:
        text = ptext(check["text"])  # eine Abweichung fett
        return Paragraph(f"<b>{text}</b>" if check["status"] in ("abweichend", "kopie_veraendert") else text, small)

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
            meta_rows.append(("Gegenstandslos" if voided else "Abgeschlossen", completed.strftime("%d.%m.%Y")))
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
               (f"{'als gegenstandslos abgeschlossen' if voided else 'abgeschlossen'} am "
                f"{completed.strftime('%d.%m.%Y %H:%M')} Uhr") if completed else None,
               (f"von {checklist.voided_by_name}" if voided and checklist.voided_by_name
                else f"von {completer}" if completer and completer != creator and not voided else None),
               f"Vorlagenfassung {checklist.template_version.version_no}"]
        story.append(Paragraph(ptext(" · ".join(x for x in who if x)), small))
        if voided:
            # Seit 1.8.41: als gegenstandslos abgeschlossen -- Begründung gut sichtbar vor den Angaben.
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(f"<b>Gegenstandslos:</b> {ptext(checklist.void_reason or '')}", body))
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
                    source = photo_bytes[photo.id] if photo_bytes is not None else attachment_path(photo)
                    story.append(_image(source, width))
                    story.append(Spacer(1, 2 * mm))
                story.append(Spacer(1, 2 * mm))
            elif field.field_type == "unterschrift":
                flush_rows()
                story.append(Paragraph(ptext(field.label + (f" ({field.signer_label})" if field.signer_label else "")), h3))
                signatures = attachments.get(field.id, [])
                if not signatures:
                    story.append(Paragraph("Nicht unterschrieben.", small))
                for sig in signatures:  # je Unterschrift Bild + Name zusammen, nie getrennt
                    block = [
                        _image(attachment_path(sig), SIGNATURE_WIDTH_MM, max_height_mm=SIGNATURE_HEIGHT_MM),
                        Paragraph(ptext(f"{sig.signer_name or ''}, {to_berlin(sig.created_at).strftime('%d.%m.%Y %H:%M')} Uhr"), small),
                    ]
                    if sig.content_sha256:  # seit 1.8.13; ältere Unterschriften haben keine
                        scope = "die Angaben oberhalb dieser Unterschrift" if sig.sealed_content is not None else "die ganze Checkliste"
                        block.append(Paragraph(ptext(f"Versiegelt {scope}. Prüfsumme (SHA-256): {sig.content_sha256}"), small))
                    block.append(seal_paragraph(seals[sig.id]))  # gegen den aktuellen Inhalt (seit 1.8.14)
                    story.append(KeepTogether(block + [Spacer(1, 3 * mm)]))
                story.append(Spacer(1, 2 * mm))
            else:
                rows.append([Paragraph(ptext(field.label), body), Paragraph(ptext(format_answer(field, answers.get(field.id))), body)])
        flush_rows()
        # Abschluss (seit 1.8.15): versiegelt alle Angaben samt Unterschriften.
        block = [Paragraph("Abschluss", h3)]
        if checklist.content_sha256:
            block.append(Paragraph(ptext("Versiegelt alle Angaben samt Unterschriften. "
                                         f"Prüfsumme (SHA-256): {checklist.content_sha256}"), small))
        block.append(seal_paragraph(completion))
        if photo_bytes:
            block.append(Paragraph(ptext(EMAIL_PHOTO_NOTE), small))
        story.append(KeepTogether(block))
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
