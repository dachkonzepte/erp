"""PDF-Erzeugung für Mahnungen (seit 1.0.53).

Seit 1.3.1: erster Nutzer des gemeinsamen PDF-Rahmens (app/document_frame.py, CLAUDE.md
"PDF-Rahmen") -- Firmenkopf/Logo/Fußzeile mit Seitenzahl sind keine feste Story mehr, sondern der
optionale, abschaltbare Rückfall des Rahmens; Briefpapier-Hintergrund und Ränder je Seitentyp
kommen ebenfalls von dort. Diese Datei baut nur noch den fließenden INHALT (Anschrift, Meta-Zeilen,
Objektanschrift, Betreff, Mahntext, Forderungsaufstellung) -- unverändert gegenüber vorher, nur
ohne Firmenkopf/Fußzeile in der eigenen story.

Seit 1.3.3: erster Nutzer des neuen, gemeinsamen Kopfbereich-Bausteins
build_din5008_header_block() (app/document_pdf.py, CLAUDE.md "Kopfbereich") -- ersetzt hier
build_customer_and_meta_block(), das die Empfängeranschrift als einen zusammengezogenen Absatz und
den Meta-Block mit zwei Beschriftung/Wert-Paaren je Zeile zeigte, uneinheitlich zur echten
Angebotsseite. Bewusst ohne Positionstabelle und ohne den Zahlungsbedingungen-/Steuerhinweis-Block
-- eine Mahnung stellt keine neue Leistung in Rechnung, sondern erinnert an eine bereits gestellte,
unveränderte Rechnung.

Seit 1.3.5: der Meta-Block bekommt eine "Seite"-Zeile ("1 / N"), analog zum Angebot. Die dafür
nötige Gesamtseitenzahl ist beim Aufbau der Story noch nicht bekannt (die entsteht erst in
_NumberedCanvas.save(), siehe app/document_frame.py) -- der Inhalt wird deshalb nicht mehr als
fertige Liste, sondern als Funktion build_story(total_pages) an render_framed_pdf() übergeben, das
sie bei Bedarf zweimal aufruft (siehe dort für die Begründung gegen einen nachträglich
überschriebenen Platzhalter).

Seit 1.8.79 (Zahlungsstufe Z2a Nr. 4): die Forderungsaufstellung zeigt Rechnungsbetrag (brutto), je Zahlung Eingangsdatum und
Betrag, Skonto und Einbehalt (nur, wenn gebucht) und den angemahnten Betrag -- aus der Aufstellung, die die Mahnung beim
Anlegen bzw. Festschreiben festhielt (app/reminders.py::amounts()). Mahnungen von vor 1.8.79 haben keine und zeigen wie bisher
nur den offenen Rechnungsbetrag. Ein Entwurf zeigt Datum und Frist des Festschreibens heute (effective_dates()).

Seit 1.8.80 (Z2b Nr. 4): unter dem angemahnten Betrag die Nebenforderungen der Rechnung (Mahngebühren, Pauschale) je Zeile und der
Gesamtbetrag (app/reminders.py::charges_view()); ohne Umsatzsteuer, nie im Rechnungsbetrag. Bei ausgeschalteten Mahngebühren keine
Zeile dafür -- nur der Gesamtbetrag. Mahnungen von vor 1.8.80 wie bisher mit "Mahngebühr".
"""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_object_address_block, build_styles, money, ptext
from .reminders import amounts, charges_view, reminder_to_dict
from .settings import load_general_settings

LEVEL_LABELS = {1: "1. Mahnung", 2: "2. Mahnung", 3: "3. Mahnung"}


def amount_rows(reminder) -> list[list[str]]:
    """Zeilen der Forderungsaufstellung vor Mahngebühr und Gesamtbetrag (seit 1.8.79): mit Aufstellung Brutto, Abzüge und
    angemahnter Betrag; ohne (vor 1.8.79) nur der offene Rechnungsbetrag wie bisher."""
    breakdown = amounts(reminder)
    if breakdown is None:
        return [["Offener Rechnungsbetrag", money(reminder.outstanding_amount)]]
    rows = [["Rechnungsbetrag (brutto)", money(breakdown["gross"])]]
    rows += [[f"abzüglich Zahlung vom {p['received_on'].strftime('%d.%m.%Y')}", money(-p["amount"])]
             for p in breakdown["payments"]]
    if breakdown["skonto"]:
        rows.append(["abzüglich Skonto", money(-breakdown["skonto"])])
    if breakdown["retained"]:
        rows.append(["abzüglich Einbehalt (wird nicht angemahnt)", money(-breakdown["retained"])])
    rows.append(["Angemahnter Betrag", money(reminder.outstanding_amount)])
    return rows


def total_rows(reminder) -> list[list[str]]:
    """Zeilen nach dem angemahnten Betrag (seit 1.8.80): je Nebenforderung eine Zeile, dann der Gesamtbetrag -- bei Mahnungen von
    vor 1.8.80 wie bisher Mahngebühr und Gesamtbetrag."""
    view = charges_view(reminder)
    if view["enabled"] is None:
        return [["Mahngebühr", money(reminder.fee_amount)], ["Gesamtbetrag", money(view["total"])]]
    return [[line["label"], money(line["amount"])] for line in view["lines"]] + [["Gesamtbetrag", money(view["total"])]]


def build_reminder_pdf(db, reminder) -> bytes:
    data = reminder_to_dict(reminder)
    invoice = reminder.invoice
    label = LEVEL_LABELS.get(data["level"], "Mahnung")
    styles = build_styles()
    body, h1 = styles["body"], styles["h1"]

    general = load_general_settings(db)
    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    sender_line = " - ".join(x for x in sender_parts if x)

    # invoice.customer_address ist ein Text-Schnappschuss "Straße, PLZ Ort" (siehe
    # orders.py::_address(), zwei per ", " zusammengefügte Teile) -- einmaliges Aufteilen
    # rekonstruiert die beiden ursprünglichen Zeilen, ohne die Schnappschuss-Erzeugung selbst
    # anzufassen (Auftrag/Rechnung bleiben in dieser Etappe unverändert).
    recipient_lines = [data["customer_name"]] + (
        invoice.customer_address.split(", ", 1) if invoice.customer_address else []
    )

    # Derselbe Satzspiegel für den gesamten fließenden Inhalt -- aus den tatsächlich
    # konfigurierten Rändern, nicht aus einem hart codierten Standardwert (seit 1.3.9, CLAUDE.md
    # "Positionstabelle: Menge/Einheit/Breite"; ursprünglich für die Rechnung gefunden, gilt aber
    # für jede Tabelle in einem bereits umgestellten Renderer gleichermaßen).
    content_width = frame_content_width(get_margins(db, "reminder", "first"))

    def build_story(total_pages: int | None) -> list:
        # Die Mahnung sitzt immer als erstes auf Seite 1, "1 /" bleibt deshalb fest -- nur die
        # Gesamtzahl ist beim ersten (verworfenen) Durchlauf noch unbekannt.
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = [
            ("Mahnungsnr.", data["reminder_number"] or "(Entwurf)"),
            ("Datum", data["effective_reminder_date"].strftime("%d.%m.%Y")),
            ("zu Rechnung", data["invoice_number"] or "(Entwurf)"),
            ("vom", invoice.invoice_date.strftime("%d.%m.%Y")),
            ("Seite", page_value),
        ]
        story = list(build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles, content_width=content_width))

        story += build_object_address_block(
            invoice.property_name,
            [x for x in str(invoice.property_address or "").splitlines() if x],
            styles,
        )

        story.append(Paragraph(label, h1))
        story += [Paragraph(ptext(data["formatted_text"]), body), Spacer(1, 6*mm)]

        rows = amount_rows(reminder) + total_rows(reminder)
        # Spalten summieren sich auf die volle Rahmenbreite (statt vorher 160mm mit
        # hAlign="RIGHT", das die Tabelle nur innerhalb des Rahmens nach rechts schob, dabei aber
        # ihre linke Kante spürbar vom Satzspiegel wegrückte -- gemessen, nicht geraten, siehe
        # CLAUDE.md, Abschnitt "Kopfbereich"). LEFTPADDING/RIGHTPADDING auf 0, damit die Tabelle
        # exakt auf derselben linken Fluchtlinie wie Überschrift/Fließtext beginnt und ihre
        # rechtsbündige Wertespalte exakt auf dem rechten Satzspiegel endet -- ein reportlab-Table
        # hat sonst 6pt (~2,1mm) Zellenpolster je Seite, ein Paragraph keins.
        tt = Table(rows, colWidths=[content_width - 45*mm, 45*mm])
        tt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, -1), (-1, -1), .8, colors.black), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story += [tt, Spacer(1, 7*mm)]
        return story

    return render_framed_pdf(
        db, document_type="reminder", title=f"{data['reminder_number'] or 'Entwurf'} - {label}",
        content_story=build_story,
    )
