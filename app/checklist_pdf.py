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
und das Dokument sagt das. Der Download (PDF-Knopf) bleibt in voller Auflösung.

Belege (seit 1.8.45, Feldtyp "beleg"): liegen unverändert vor, bis 15 MB. Ein Foto-Beleg erscheint im
Dokument verkleinert (im Speicher, wie im Versand-PDF), ein PDF-Beleg als Zeile -- beide mit der Prüfsumme
der Originaldatei, auf die sich auch Unterschriften und Abschluss beziehen.

Abnahmeprotokoll (seit 1.8.64, Zweck "abnahme"): oben "Erklärungen des Auftraggebers" gebündelt aus der versiegelten Kopie
seiner Unterschrift (app/acceptance_protocol.py::protocol_summary()), am Feld "Mängel" jeder Mangel, der im Protokoll steht
(die Kopie entscheidet) -- Beschreibung, Ort, Frist, Zahl der Fotos und Belege (die Dateien liegen im ERP am Mangel), Prüfsumme;
ein erst nach der Unterschrift verworfener mit diesem Vermerk, vorher verworfene gar nicht. Ohne Begründungen, ohne Abnahme am
Auftrag und ohne Aufgaben -- das Dokument kann an den Auftraggeber gehen.

Fotos der Mängel (seit 1.8.68): am Feld "Mängel" die Fotos jedes Mangels im Protokoll, die bei der Unterschrift zu ihm
gehörten -- die beim Erfassen (im gebundenen Inhalt des Mangels), und nur, wenn sein Inhalt zur Prüfsumme in der Kopie der
Unterschrift passt (sonst ein Hinweis statt der Bilder) und die Datei zu ihrer Prüfsumme. Später ergänzte Fotos (Ereignisse,
z. B. "beseitigt") gehören nicht dazu. Verkleinert wie die übrigen Fotos, die Originale bleiben unverändert im ERP.

Feste Fassung (seit 1.8.66, app/checklist_versions.py, build_checklist_version_pdf()): bei jeder Unterschrift, beim Abschluss
und bei "gegenstandslos" das PDF des Stands genau dieses Moments -- auch an einem Entwurf. Kopf und Unterzeile nennen Fassung und
Anlass, der Abschluss-Block sagt "noch nicht abgeschlossen"; die Fotos stufenweise verkleinert wie beim Versand-PDF, aber ohne
Abbruch: passt auch die kleinste Stufe nicht unter 3 MB, bleibt sie (der Versand meldet dann die Größe)."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .berlin_time import to_berlin
from .checklists import (
    CLOSED_STATUSES, VOID_STATUS, _answer_value, _attachment_sha256, active_attachments, attachment_content_type,
    attachment_path, check_completion, check_signature, signer_text,
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
VERSION_PHOTO_NOTE = ("Fotos in dieser Fassung auf höchstens {px} Pixel verkleinert. Die Originale liegen unverändert im ERP; "
                      "die Prüfsummen oben beziehen sich auf sie.")  # seit 1.8.66
SIGNATURE_WIDTH_MM, SIGNATURE_HEIGHT_MM = 60, 25
BELEG_PDF_PX, BELEG_PDF_QUALITY = 1600, 82  # Foto-Beleg im Dokument: wie ein Foto nach dem Hochladen
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
    if t == "dachflaechen":  # seit 1.8.61: die Namen beim Speichern
        return ", ".join(a["name"] for a in value)
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
    """Das Foto neu verkleinert, nur im Speicher -- die Datei selbst wird nur gelesen. path: Pfad oder (seit 1.8.68) die
    Bytes eines Fotos (Mangel, aus der Ablage der Abnahmen)."""
    from PIL import Image as PILImage

    with PILImage.open(BytesIO(path) if isinstance(path, bytes) else path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _is_image_beleg(attachment) -> bool:
    return attachment.kind == "beleg" and attachment_content_type(attachment) != "application/pdf"


def _beleg_block(beleg, width_mm: float, photo_bytes: dict | None, photo_hashes: dict, small) -> list:
    """Ein Beleg im Dokument (seit 1.8.45): ein Foto verkleinert, ein PDF als Zeile -- darunter Zeitpunkt und
    Prüfsumme der Originaldatei. Eine fehlende Datei steht als solche da, statt das ganze PDF abzubrechen."""
    path = attachment_path(beleg)
    when = to_berlin(beleg.created_at).strftime("%d.%m.%Y %H:%M") if beleg.created_at else ""
    sha = _attachment_sha256(beleg, photo_hashes)
    if not path.exists():
        return [Paragraph(ptext(f"Beleg vom {when} Uhr – Datei fehlt."), small)]
    if _is_image_beleg(beleg):
        source = photo_bytes[beleg.id] if photo_bytes and beleg.id in photo_bytes             else _reduced_photo(path, BELEG_PDF_PX, BELEG_PDF_QUALITY)
        head = [_image(source, width_mm), Paragraph(ptext(f"Foto-Beleg vom {when} Uhr, hier verkleinert."), small)]
    else:
        size_kb = max(1, round(path.stat().st_size / 1024))
        head = [Paragraph(ptext(f"PDF-Beleg vom {when} Uhr ({size_kb} KB) – die Datei liegt im ERP an der Checkliste."),
                          small)]
    return head + [Paragraph(ptext(f"Prüfsumme der Originaldatei (SHA-256): {sha}"), small)]


def _defect_block(d: dict, body, small) -> list:
    """Ein Mangel im Abnahmeprotokoll (seit 1.8.64, Eintrag aus app/defects.py::list_protocol_defects()): Nummer, Ort,
    Beschreibung, Frist, Belege als Anzahl (Fotos seit 1.8.68 als Bilder darunter), Prüfsumme; erst nach der Unterschrift verworfen mit Vermerk, ohne Begründung."""
    place = " · ".join(x for x in (d["roof_area_name"], d["location"]) if x)
    head = f"<b>Mangel Nr. {d['id']}</b>" + (f" – {ptext(place)}" if place else "")
    block = [Paragraph(head, body), Paragraph(ptext(d["description"]), body)]
    details = []
    if d["remedy_due_on"]:
        details.append(f"Beseitigungsfrist: {d['remedy_due_on']:%d.%m.%Y}")
    belege = sum(1 for f in d["files"] if f["kind"] != "foto")  # seit 1.8.68 die Fotos als Bilder darunter
    if belege:
        details.append(f"Belege: {belege} (liegen im ERP am Mangel)")
    details.append(f"Prüfsumme (SHA-256): {d['content_sha256']}")
    block.append(Paragraph(ptext(" · ".join(details)), small))
    if not d["intact"]:
        block.append(Paragraph(f"<b>{ptext(d['check']['text'])}</b>", small))
    if d["discarded"]:
        when = f" am {d['discarded_at_local']:%d.%m.%Y}" if d["discarded_at_local"] else ""
        block.append(Paragraph(f"<b>{ptext(f'Nach der Unterschrift verworfen{when} – bleibt im Protokoll.')}</b>", small))
    return block


def build_checklist_email_pdf(db, checklist: Checklist) -> bytes:
    """Das PDF für den Versand per E-Mail: höchstens MAX_ATTACHMENT_BYTES, Fotos stufenweise
    kleiner (EMAIL_PHOTO_STEPS). Je Stufe liegen nur deren Fotos im Speicher. Passt es auch mit der
    kleinsten Stufe nicht, ValueError mit dem Hinweis auf einen anderen Zustellweg."""
    from .email_sending import MAX_ATTACHMENT_BYTES

    photos = [a for a in active_attachments(checklist) if a.kind == "foto" or _is_image_beleg(a)]  # Belege seit 1.8.45
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


def defect_photo_rows(db, summary: dict | None) -> list:
    """Die Fotos, die bei der Unterschrift zu den Mängeln im Protokoll gehörten (seit 1.8.68): die Dateien beim Erfassen eines
    Mangels, dessen Inhalt zur Prüfsumme in der Kopie passt (files_as_signed) -- nur Fotos, nur mit stimmender Prüfsumme der
    Datei. Ohne Unterschrift unter dem Feld (noch keine Kopie) die Fotos beim Erfassen der nicht verworfenen."""
    from .models import DefectFile

    rows = []
    for d in (summary or {}).get("defects", []):
        if not d["in_protocol"] or (d["sealed"] and not d.get("files_as_signed")):
            continue
        rows += [db.get(DefectFile, f["id"]) for f in d["files"] if f["kind"] == "foto" and f["status"] == "unveraendert"]
    return rows


def _defect_photo(row, max_px: int, quality: int) -> bytes | None:
    """Ein Foto eines Mangels verkleinert -- None, wenn die Datei fehlt oder nicht zu ihrer Prüfsumme passt."""
    from .defects import read_defect_file
    from .acceptances import AcceptanceFileError

    try:
        return _reduced_photo(read_defect_file(row), max_px, quality)
    except AcceptanceFileError:
        return None


def build_checklist_version_pdf(db, checklist: Checklist, stand: dict) -> bytes:
    """Das PDF einer festen Fassung (seit 1.8.66): stand = {"version_no", "kind", "signature", "at"}. Fotos und Foto-Belege
    stufenweise verkleinert (EMAIL_PHOTO_STEPS), bis das PDF unter MAX_ATTACHMENT_BYTES liegt; passt auch die kleinste Stufe
    nicht, bleibt sie -- anders als beim Versand-PDF kein Abbruch, die Unterschrift gilt trotzdem. Je Stufe liegen nur deren
    Fotos im Speicher."""
    from .acceptance_protocol import protocol_summary
    from .email_sending import MAX_ATTACHMENT_BYTES

    photos = [a for a in active_attachments(checklist) if a.kind == "foto" or _is_image_beleg(a)]
    defect_rows = defect_photo_rows(db, protocol_summary(db, checklist))  # seit 1.8.68
    if not photos and not defect_rows:
        return build_checklist_pdf(db, checklist, stand=stand)
    pdf = None
    for index, (max_px, quality) in enumerate(EMAIL_PHOTO_STEPS):
        last = index == len(EMAIL_PHOTO_STEPS) - 1
        reduced = {a.id: _reduced_photo(attachment_path(a), max_px, quality) for a in photos}
        reduced_defects = {r.id: data for r in defect_rows if (data := _defect_photo(r, max_px, quality)) is not None}
        size = sum(len(b) for b in reduced.values()) + sum(len(b) for b in reduced_defects.values())
        if not last and size * _EMBED_FACTOR > MAX_ATTACHMENT_BYTES:
            continue
        pdf = build_checklist_pdf(db, checklist, photo_bytes=reduced, defect_photo_bytes=reduced_defects,
                                  stand={**stand, "photo_px": max_px})
        if len(pdf) <= MAX_ATTACHMENT_BYTES:
            break
    return pdf


def _stand_text(checklist: Checklist, stand: dict) -> str:
    """Unterzeile einer festen Fassung: Nummer, Anlass, Zeitpunkt (Berliner Zeit)."""
    at = to_berlin(stand.get("at"))
    when = f" am {at:%d.%m.%Y %H:%M} Uhr" if at else ""
    signature = stand.get("signature")
    if stand["kind"] == "unterschrift" and signature is not None:
        field = next((f for f in checklist.template_version.fields if f.id == signature.template_field_id), None)
        text = (f"Feste Fassung {stand['version_no']} – Stand bei der Unterschrift „{field.label if field else 'Unterschrift'}“"
                f" ({signature.signer_name or 'ohne Namen'}){when}.")
        fields = checklist.template_version.fields
        if field is not None and any(f.field_type not in ("hinweis", "unterschrift") for f in fields[fields.index(field) + 1:]):
            text += " Angaben unterhalb dieser Unterschrift waren zu diesem Zeitpunkt noch offen und sind von ihr nicht versiegelt."
        return text
    if stand["kind"] == "gegenstandslos":
        return f"Feste Fassung {stand['version_no']} – Stand beim Abschluss als gegenstandslos{when}."
    return f"Feste Fassung {stand['version_no']} – Stand beim Abschluss{when}."


def build_checklist_pdf(db, checklist: Checklist, *, photo_bytes: dict[int, bytes] | None = None,
                        stand: dict | None = None, defect_photo_bytes: dict[int, bytes] | None = None) -> bytes:
    """photo_bytes (seit 1.8.20, nur build_checklist_email_pdf()): je Foto-ID die verkleinerten
    Bytes statt der Datei, dazu ein Hinweis im Dokument. stand (seit 1.8.66, nur build_checklist_version_pdf()): das PDF
    einer festen Fassung -- dann auch an einem Entwurf. defect_photo_bytes (seit 1.8.68): je Foto eines Mangels
    (DefectFile-ID) die verkleinerten Bytes; fehlt eins, wird es hier wie ein Foto-Beleg verkleinert."""
    if checklist.status not in CLOSED_STATUSES and stand is None:  # seit 1.8.41 auch "gegenstandslos" -- bleibt als Beleg
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
    from .acceptance_protocol import protocol_summary  # seit 1.8.64; lokal wie die übrigen Fachmodule eines Renderers
    from .checklist_versions import protocol_copy_to
    summary = protocol_summary(db, checklist)
    # seit 1.8.67: "Kopie an:" im Abnahmeprotokoll -- in einer Fassung die beim Erstellen eingefrorene Liste
    copy_to = stand["copy_to"] if stand is not None and "copy_to" in stand else protocol_copy_to(db, checklist)

    defect_photo_cache = dict(defect_photo_bytes or {})

    def defect_photos(d: dict) -> list:
        """Die Fotos des Mangels wie bei der Unterschrift (seit 1.8.68, siehe defect_photo_rows()), je mit Prüfsumme der
        Originaldatei; passt der Mangel nicht zur Kopie bzw. eine Datei nicht zu ihrer Prüfsumme, ein Hinweis statt Bild."""
        from .models import DefectFile

        fotos = [f for f in d["files"] if f["kind"] == "foto"]
        if not fotos:
            return []
        if d["sealed"] and not d.get("files_as_signed"):
            return [Paragraph("<b>Fotos nicht gezeigt: der Mangel passt nicht zur Kopie der Unterschrift.</b>", small),
                    Spacer(1, 2 * mm)]
        width = min(PHOTO_WIDTH_MM, content_width_mm)
        out = []
        for f in fotos:
            if f["id"] not in defect_photo_cache and f["status"] == "unveraendert":  # einmal je PDF, nicht je Durchlauf
                defect_photo_cache[f["id"]] = _defect_photo(db.get(DefectFile, f["id"]), BELEG_PDF_PX, BELEG_PDF_QUALITY)
            data = defect_photo_cache.get(f["id"])
            if data is None:
                text = f"Foto zum Mangel Nr. {d['id']} nicht gezeigt: {f['status_text']}."
                out.append(Paragraph(f"<b>{ptext(text)}</b>", small))
                continue
            out.append(KeepTogether([_image(data, width), Paragraph(ptext(
                f"Foto zum Mangel Nr. {d['id']} – Prüfsumme der Originaldatei (SHA-256): {f['sha256']}"), small),
                Spacer(1, 2 * mm)]))
        return out

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
        if stand is not None:  # seit 1.8.66: feste Fassung
            meta_rows.append(("Fassung", str(stand["version_no"])))
            if not completed and to_berlin(stand.get("at")):
                meta_rows.append(("Stand", to_berlin(stand["at"]).strftime("%d.%m.%Y")))
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
        if stand is not None:
            story.append(Paragraph(f"<b>{ptext(_stand_text(checklist, stand))}</b>", small))
        if voided:
            # Seit 1.8.41: als gegenstandslos abgeschlossen -- Begründung gut sichtbar vor den Angaben.
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(f"<b>Gegenstandslos:</b> {ptext(checklist.void_reason or '')}", body))
        if summary is not None:  # seit 1.8.64: Abnahmeprotokoll -- die Erklärungen auf einen Blick
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Erklärungen des Auftraggebers – Zusammenfassung", h3))
            for error in summary["errors"]:  # seit 1.8.65: fehlerhafte Kopie -- sichtbar, keine Schlüsse daraus
                story.append(Paragraph(f"<b>{ptext(error)}</b>", small))
            if summary["declarations"]:
                story.append(answer_table([[Paragraph(ptext(r["label"]), body), Paragraph(ptext(r["value"]), body)]
                                           for r in summary["declarations"]]))
            sig = summary["signature"]
            stand_ag = (f"Stand der Unterschrift des Auftraggebers vom {sig['signed_at_local']:%d.%m.%Y %H:%M} Uhr – "
                     f"{sig['text'] or sig['name']}" if sig else "Noch nicht vom Auftraggeber unterschrieben.")
            story.append(Paragraph(ptext(stand_ag), small))
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
            elif field.field_type == "beleg":  # seit 1.8.45
                flush_rows()
                belege = attachments.get(field.id, [])
                story.append(Paragraph(ptext(field.label), h3))
                if not belege:
                    story.append(Paragraph("Kein Beleg.", small))
                for beleg in belege:
                    story.append(KeepTogether(_beleg_block(beleg, min(PHOTO_WIDTH_MM, content_width_mm), photo_bytes,
                                                           photo_hashes, small) + [Spacer(1, 2 * mm)]))
                story.append(Spacer(1, 2 * mm))
            elif field.field_type == "maengel" and summary is not None:  # seit 1.8.64: die Mängel im Protokoll
                flush_rows()
                story.append(Paragraph(ptext(field.label), h3))
                problem = next((d["seal_problem"] for d in summary["defects"] if d.get("seal_problem")), None)
                if problem:  # seit 1.8.65: nicht feststellbar -- kein "Keine Mängel.", keine Auswahl
                    story.append(Paragraph(f"<b>{ptext(problem)}</b>", small))
                drin = [] if problem else [d for d in summary["defects"] if d["in_protocol"]]
                if not drin and not problem:
                    story.append(Paragraph("Keine Mängel.", small))
                for d in drin:
                    story.append(KeepTogether(_defect_block(d, body, small) + [Spacer(1, 2 * mm)]))
                    story += defect_photos(d)  # seit 1.8.68
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
                    zeile = signer_text(sig, checklist.template_version.purpose)  # seit 1.8.57: Art, Rolle, Vollmacht
                    if zeile:
                        block.append(Paragraph(ptext(zeile), small))
                    if sig.content_sha256:  # seit 1.8.13; ältere Unterschriften haben keine
                        scope = "die Angaben oberhalb dieser Unterschrift" if sig.sealed_content is not None else "die ganze Checkliste"
                        block.append(Paragraph(ptext(f"Versiegelt {scope}. Prüfsumme (SHA-256): {sig.content_sha256}"), small))
                    block.append(seal_paragraph(seals[sig.id]))  # gegen den aktuellen Inhalt (seit 1.8.14)
                    story.append(KeepTogether(block + [Spacer(1, 3 * mm)]))
                story.append(Spacer(1, 2 * mm))
            else:
                rows.append([Paragraph(ptext(field.label), body), Paragraph(ptext(format_answer(field, answers.get(field.id))), body)])
        flush_rows()
        if copy_to:  # seit 1.8.67: Abnahmeprotokoll -- wer eine Kopie bekommt (wie in den Briefen der Anzeigen)
            story.append(Paragraph(ptext("Kopie an: " + "; ".join(f"{c['name']} ({c['role_label']})" for c in copy_to)),
                                   body))
            story.append(Spacer(1, 3 * mm))
        # Abschluss (seit 1.8.15): versiegelt alle Angaben samt Unterschriften.
        block = [Paragraph("Abschluss", h3)]
        if checklist.content_sha256:
            block.append(Paragraph(ptext("Versiegelt alle Angaben samt Unterschriften. "
                                         f"Prüfsumme (SHA-256): {checklist.content_sha256}"), small))
        if completion is not None:
            block.append(seal_paragraph(completion))
        else:  # seit 1.8.66: feste Fassung eines Entwurfs
            block.append(Paragraph("Noch nicht abgeschlossen.", small))
        if (photo_bytes or defect_photo_bytes) and stand is not None and stand.get("photo_px"):
            block.append(Paragraph(ptext(VERSION_PHOTO_NOTE.format(px=stand["photo_px"])), small))
        elif photo_bytes:
            block.append(Paragraph(ptext(EMAIL_PHOTO_NOTE), small))
        story.append(KeepTogether(block))
        return story

    continuation = [("Checkliste", f"Nr. {checklist.id}")]
    if stand is not None:
        continuation.append(("Fassung", str(stand["version_no"])))
    if order is not None:
        continuation.append(("Auftragsnr.", order.order_number))
    if completed:
        continuation.append(("Abgeschlossen", completed.strftime("%d.%m.%Y")))
    return render_framed_pdf(
        db, document_type=DOCUMENT_TYPE, title=f"{checklist.template_label_snapshot} – {checklist.context_label_snapshot or context_label}",
        content_story=build_story, continuation_header_rows=continuation,
    )
