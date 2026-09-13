"""Gemeinsamer Dokumentaufbau für Angebot/Auftrag/Rechnung (seit 1.0.44).

Alle drei Dokumente folgen demselben Aufbau: Firmenkopf, Kundenadresse
(links) + Meta-Tabelle (rechts) nebeneinander, Objektanschrift, Titel,
Vortext, [Positionen/Summen -- bleiben je Dokumenttyp eigenständig, da die
Tabellenspalten sich unterscheiden], Zahlungsbedingungen (+ Fälligkeitssatz
nur bei Rechnungen), Steuerhinweis, Schlusstext (zwei Blöcke).

Bewusst als eigenständiges Modul statt Duplizierung in allen drei
PDF-Dateien: money()/qty()/ptext() lagen bisher in quote_pdf.py und wurden
von dort importiert -- das ist jetzt hierher verschoben, damit kein
Dokumenttyp mehr "führend" ist und alle drei gleichberechtigt von hier aus
importieren.

Diese Bausteine sind absichtlich klein und datengetrieben (reine Listen von
Absätzen/Zeilen als Parameter, keine Kenntnis von Quote/Order/Invoice-
Modellen) -- das ist die Grundlage, auf der ein künftiger, visueller
PDF-Layoutdesigner aufbauen kann: er müsste nicht drei Dokumenttypen einzeln
umbauen, sondern könnte an genau dieser Blockstruktur ansetzen (Blöcke ein-/
ausblenden, Reihenfolge ändern), ohne dass die Positions-/Summentabellen
je Dokumenttyp angetastet werden.
"""

from decimal import Decimal
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

# Gesamtbreite bei A4, rightMargin=16mm, leftMargin=18mm: 210 - 16 - 18 = 176mm.
PAGE_CONTENT_WIDTH = 176 * mm
CUSTOMER_COL_WIDTH = 68 * mm
META_COL_WIDTH = PAGE_CONTENT_WIDTH - CUSTOMER_COL_WIDTH


def money(value) -> str:
    value = Decimal(value or 0)
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def money_bare(value) -> str:
    """Wie money(), aber ohne die Währungsangabe -- seit 1.3.17 für die EP/GP- (bzw. Betrag-)
    Wertespalten der Positionstabelle in Angebot/Auftrag/Rechnung: die Einheit steht dort seither
    in der Spaltenüberschrift selbst ("EP/EUR"/"GP/EUR"), nicht mehr in jeder einzelnen Zelle --
    Vorbild ist ein bereits beim Betreiber etabliertes Vergleichsdokument. money() bleibt für den
    Summenblock (Nettosumme/MwSt./Brutto) unverändert -- dort steht die Währung nur wenige Male,
    kein Grund, sie dort ebenfalls in die Überschrift zu ziehen."""
    value = Decimal(value or 0)
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def qty(value) -> str:
    text = f"{Decimal(value or 0):.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def ptext(text: str | None) -> str:
    if not text:
        return ""
    return "<br/>".join(escape(str(text)).splitlines())


def build_styles() -> dict:
    """Einmal pro PDF aufrufen, das Ergebnis für alle Bausteine wiederverwenden."""
    base = getSampleStyleSheet()
    body = ParagraphStyle("BodyDE", parent=base["BodyText"], fontName="Helvetica", fontSize=9.4, leading=13)
    return {
        "body": body,
        "small": ParagraphStyle("SmallDE", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#555555")),
        "h1": ParagraphStyle("H1DE", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=19, spaceAfter=5),
        "h2": ParagraphStyle("H2DE", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=8, spaceAfter=4),
        "h3": ParagraphStyle("H3DE", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=9.5, leading=14, leftIndent=4 * mm, spaceBefore=5),
        "right": ParagraphStyle("Right", parent=body, alignment=TA_RIGHT),
    }


def build_company_header_block(general, styles: dict) -> list:
    """Firmenkopf: Firmenname/Adresse links, Kontaktdaten rechts."""
    body, right = styles["body"], styles["right"]
    company_lines = [general.company_name]
    if general.street:
        company_lines.append(general.street)
    cityline = " ".join(x for x in [general.postal_code, general.city] if x)
    if cityline:
        company_lines.append(cityline)
    contact_parts = [x for x in [general.phone, general.email, general.website] if x]
    header = Table([[
        Paragraph(f"<b>{escape(general.company_name)}</b><br/><font size=8>{'<br/>'.join(escape(x) for x in company_lines[1:])}</font>", body),
        Paragraph("<br/>".join(escape(x) for x in contact_parts), right),
    ]], colWidths=[105 * mm, 70 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    return [header, Spacer(1, 4 * mm)]


def build_customer_and_meta_block(customer_lines: list[str], meta_rows: list[list[str]], styles: dict) -> list:
    """Kundenadresse (links) und Meta-Tabelle (rechts) nebeneinander in
    derselben Zeile -- customer_lines und meta_rows werden vom jeweiligen
    Dokumenttyp zusammengestellt (unterschiedliche Datenquellen: Angebot
    liest live vom Kunden-/Objektdatensatz, Auftrag/Rechnung aus dem
    eingefrorenen Textschnappschuss), landen hier aber im selben Layout."""
    body = styles["body"]
    customer_para = Paragraph("<br/>".join(escape(x) for x in customer_lines if x), body)
    meta_table = Table(meta_rows, colWidths=[20 * mm, 35 * mm, 18 * mm, META_COL_WIDTH - 73 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    outer = Table([[customer_para, meta_table]], colWidths=[CUSTOMER_COL_WIDTH, META_COL_WIDTH])
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [outer, Spacer(1, 6 * mm)]


# Spaltenaufteilung für build_din5008_header_block() -- eigene Konstanten, nicht
# CUSTOMER_COL_WIDTH/META_COL_WIDTH (die bleiben build_customer_and_meta_block() vorbehalten,
# andere Aufteilung, siehe Klärung dort). Bildet die tatsächliche, produktiv angepasste
# Angebotsseite nach (gemessen an quote_layout_pdf.py-Blockpositionen: Anschrift x=18/Breite 70mm,
# Meta-Tabelle x=124,4/Breite 70mm) statt eine eigene Aufteilung zu erfinden -- 70mm Anschrift,
# 70mm Meta-Block, dazwischen der Rest als deutlich sichtbare Lücke (176-70-70=36mm).
DIN5008_ADDRESS_COL_WIDTH = 70 * mm
DIN5008_META_COL_WIDTH = 70 * mm
DIN5008_GAP_COL_WIDTH = PAGE_CONTENT_WIDTH - DIN5008_ADDRESS_COL_WIDTH - DIN5008_META_COL_WIDTH
DIN5008_META_LABEL_WIDTH = 35 * mm
DIN5008_META_VALUE_WIDTH = DIN5008_META_COL_WIDTH - DIN5008_META_LABEL_WIDTH

# Nur links/rechts nullen -- die vertikale Zeilenhöhe (TOP-/BOTTOMPADDING) bleibt je Tabelle ihre
# eigene, bewusst gesetzte Sache (z.B. der Zeilenabstand in der Meta-Tabelle), nur die horizontale
# Ausrichtung war das gemessene Problem (siehe Docstring unten).
_ZERO_HORIZONTAL_TABLE_PADDING = [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]


def build_din5008_header_block(
    sender_line: str | None, recipient_lines: list[str], meta_rows: list[tuple[str, str]], styles: dict,
    *, content_width: float | None = None,
) -> list:
    """Kopfbereich als eigenständiger, wiederverwendbarer Baustein (seit 1.3.3) -- Ziel: derselbe
    Auftritt (Anschrift + Meta-Block) über alle Dokumenttypen hinweg. Anders als das bestehende
    build_customer_and_meta_block() (bleibt unverändert, quote_pdf.py/order_pdf.py/invoice_pdf.py
    nutzen es weiterhin -- siehe Klärung, warum hier ein neuer Baustein statt einer Änderung dort):
    - Empfängeranschrift als echte, einzelne Zeilen (eine pro Listeneintrag), nicht ein
      zusammengezogener Absatz.
    - Meta-Block als schlichte Zweispalten-Tabelle, eine Zeile pro Beschriftung/Wert-Paar, statt
      zwei Paaren nebeneinander in einer Zeile -- Wertespalte rechtsbündig, ihre rechte Kante
      liegt exakt auf dem rechten Satzspiegel (siehe Nachtrag unten zur Nullung des
      Tabellen-Zellenpolsters).
    - zusätzlich eine kleine, unterstrichene Absenderzeile über der Anschrift (DIN 5008,
      Rücksendeangabe im Anschriftenfenster) -- die echte, produktiv angepasste Angebotsseite
      (quote_layout_pdf.py) zeigt ihre Version der Absenderzeile heute normal groß und ohne Linie;
      diese Abweichung ist eine bewusste Nutzerentscheidung für den neuen, gemeinsamen Auftritt,
      keine Anpassung an den heutigen Ist-Zustand.

    Das alte quote_layout_pdf.py (entfernt seit 1.3.20, CLAUDE.md "Gemeinsamer Dokumenttyp") hatte
    für die reale Angebotsseite bereits eigene, private Bausteine in genau dieser Form
    (_build_line_list_block()/_build_field_rows_table()) -- die waren aber an die inzwischen
    ebenfalls entfernte DocumentTableField-Feldkonfiguration und live Customer/Property-Objekte
    gekoppelt und deshalb kein Ersatz für einen einfachen, datengetriebenen Baustein wie die
    übrigen Funktionen in diesem Modul.

    Nachtrag (nach echtem Nachmessen im PDF, nicht nach Augenmaß -- siehe CLAUDE.md, Abschnitt
    "Kopfbereich"): ein reportlab-`Table` hat per Default 6pt (~2.1mm) Zellenpolster auf jeder
    Seite, ein `Paragraph` dagegen keins -- ohne explizite Nullung beginnt jeder Tabelleninhalt
    knapp 2mm weiter rechts als der umgebende Fließtext, und eine rechtsbündige Wertespalte würde
    ebenso knapp 2mm VOR dem rechten Satzspiegel enden statt exakt darauf. `_ZERO_TABLE_PADDING`
    nullt das auf beiden hier verwendeten Tabellen (äußere Tabelle UND Meta-Tabelle), damit die
    Absenderzeile links exakt auf derselben Fluchtlinie wie Überschrift/Fließtext beginnt und die
    Meta-Wertespalte rechts exakt auf dem Satzspiegel endet -- keine der beiden Tabellen war vorher
    falsch BREIT/POSITIONIERT (die Spaltenbreiten summierten sich schon vorher exakt auf die
    Rahmenbreite), nur ihr Zellenpolster verschob den sichtbaren Text nach innen.
    ("ALIGN", (1,*), "RIGHT") auf der Meta-Tabelle war der eigentlich fehlende Teil dafür, dass die
    Wertespalte überhaupt rechtsbündig wird -- vorher stand dort keine ALIGN-Regel, Text blieb also
    linksbündig in einer viel zu breiten Zelle und wirkte dadurch weit von der rechten Kante
    entfernt, obwohl die Zellgrenze selbst schon korrekt lag.

    Erster Nutzer ist die Mahnung (app/reminder_pdf.py); Angebot/Auftrag/Rechnung folgen bewusst
    erst in eigenen, späteren Etappen (siehe CLAUDE.md, Abschnitt "Kopfbereich").

    content_width (seit 1.3.9, CLAUDE.md "Positionstabelle: Menge/Einheit/Breite"): optional, in
    reportlab-Punkten (bereits '* mm') -- der tatsächlich konfigurierte Satzspiegel
    (document_frame.py::frame_content_width()), nicht der hart codierte PAGE_CONTENT_WIDTH-
    Standardwert. Fehlt er (z.B. in den isolierten Bausteintests unten), bleibt PAGE_CONTENT_WIDTH
    der Rückfall -- unverändertes Verhalten. Nur die Lücken-Spalte (DIN5008_GAP_COL_WIDTH) federt
    eine Abweichung ab, Anschrift/Meta-Spalte bleiben bei ihren festen 70mm."""
    body, small = styles["body"], styles["small"]
    content_width = PAGE_CONTENT_WIDTH if content_width is None else content_width
    gap_width = content_width - DIN5008_ADDRESS_COL_WIDTH - DIN5008_META_COL_WIDTH
    sender_style = ParagraphStyle(
        "SenderLineDIN5008", parent=small, fontSize=7.5, leading=9, textColor=colors.HexColor("#555555"),
    )

    left_flow = []
    if sender_line:
        # Seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp", Betreiberfund): 2mm ließen die
        # Absenderzeile deutlich abgesetzt von der Anschrift darunter wirken, zwei erkennbar
        # eigene Blöcke statt einer DIN-5008-typischen Einheit (kleine, unterstrichene
        # Rücksendeangabe direkt über der Anschrift). Betrifft alle vier Dokumenttypen, die
        # diesen gemeinsamen Baustein nutzen (Mahnung/Rechnung/Auftrag/Angebot) gleichermaßen --
        # bewusst keine Sonderbehandlung für einen einzelnen Dokumenttyp.
        left_flow += [Paragraph(f"<u>{escape(sender_line)}</u>", sender_style), Spacer(1, 0.8 * mm)]
    left_flow.append(Paragraph("<br/>".join(escape(x) for x in recipient_lines if x), body))

    meta_table = Table(
        [[label, value] for label, value in meta_rows],
        colWidths=[DIN5008_META_LABEL_WIDTH, DIN5008_META_VALUE_WIDTH],
    )
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        *_ZERO_HORIZONTAL_TABLE_PADDING,
    ]))

    outer = Table(
        [[left_flow, "", meta_table]],
        colWidths=[DIN5008_ADDRESS_COL_WIDTH, gap_width, DIN5008_META_COL_WIDTH],
    )
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), *_ZERO_HORIZONTAL_TABLE_PADDING]))
    return [outer, Spacer(1, 6 * mm)]


def build_customer_address_block(customer_lines: list[str], styles: dict) -> list:
    """Nur die Kundenadresse, eigenständig (seit 1.0.61) -- für den
    positionsbasierten Layout-Editor, wo Adresse und Meta-Tabelle
    unabhängig voneinander platzierbar sein sollen (z.B. Kundenadresse im
    festen Anschriftenfenster eines vorgedruckten Briefbogens, Meta-Tabelle
    frei daneben). Die bestehende build_customer_and_meta_block() bleibt
    für die fließenden Renderer unverändert -- dort ist die Kombination in
    einer Zeile weiterhin gewünscht."""
    body = styles["body"]
    return [Paragraph("<br/>".join(escape(x) for x in customer_lines if x), body)]


def build_meta_table_block(meta_rows: list[list[str]], styles: dict) -> list:
    """Nur die Meta-Tabelle, eigenständig -- siehe build_customer_address_block()
    für die Begründung. Dieselbe Spaltenaufteilung/Formatierung wie im
    kombinierten Baustein, damit beide optisch zueinander passen, falls sie
    im Editor doch nebeneinander platziert werden."""
    meta_table = Table(meta_rows, colWidths=[20 * mm, 35 * mm, 18 * mm, META_COL_WIDTH - 73 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [meta_table]


def build_object_address_block(property_name: str | None, address_lines: list[str], styles: dict) -> list:
    """Objektanschrift als eigener, sichtbarer Absatz vor den Positionen --
    nur wenn ein Objekt hinterlegt ist. Vorher stand das als Zeile in der
    kleinen Meta-Tabelle, jetzt eigenständig und damit auffindbarer, wenn
    Ausführungsort und Rechnungsadresse voneinander abweichen."""
    if not property_name:
        return []
    body = styles["body"]
    lines = [f"Ausführungsort: {property_name}"] + [x for x in address_lines if x]
    return [Paragraph("<br/>".join(escape(x) for x in lines), body), Spacer(1, 5 * mm)]


def build_payment_tax_closing_block(
    styles: dict, *, payment_terms: str | None = None, payment_terms_sentence: str | None = None,
    tax_notice_text: str | None = None, outro_text: str | None = None, outro_text_2: str | None = None,
) -> list:
    """Zahlungsbedingungen (mit automatischem Fälligkeitssatz, sofern
    payment_terms_sentence mitgegeben wird -- nur bei Rechnungen der Fall),
    Steuerhinweis zum gewählten Steuerschlüssel, Schlusstext als zwei
    unabhängig voneinander pflegbare Blöcke.

    outro_text/outro_text_2 sind bewusst zwei unabhängige Felder (unterschiedliche
    Schlusstexte möglich) -- seit der 1.3.13-Angebots-Prüfung an einem echten Angebot gefunden:
    trägt outro_text_2 GENAU denselben Text wie outro_text (Datenpflege-Versehen, kein
    Renderfehler), erschien der Satz zweimal hintereinander. outro_text_2 wird deshalb
    unterdrückt, wenn er (nach Trimmen) exakt outro_text entspricht -- betrifft jeden Aufrufer
    dieser gemeinsamen Funktion (Angebot, Auftrag), nicht nur den, an dem es gefunden wurde."""
    body = styles["body"]
    if outro_text_2 and outro_text and outro_text_2.strip() == outro_text.strip():
        outro_text_2 = None
    story = []
    if payment_terms or payment_terms_sentence:
        label_line = f"<b>Zahlungsbedingungen:</b> {escape(payment_terms)}" if payment_terms else "<b>Zahlungsbedingungen:</b>"
        sentence_line = f"<br/>{escape(payment_terms_sentence)}" if payment_terms_sentence else ""
        story += [Paragraph(label_line + sentence_line, body), Spacer(1, 3 * mm)]
    if tax_notice_text:
        story += [Paragraph(f"<b>Hinweis zur Umsatzsteuer:</b><br/>{ptext(tax_notice_text)}", body), Spacer(1, 3 * mm)]
    if outro_text:
        story.append(Paragraph(ptext(outro_text), body))
    if outro_text_2:
        story += [Spacer(1, 3 * mm), Paragraph(ptext(outro_text_2), body)]
    return story
