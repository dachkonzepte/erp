"""Angebot: PDF-Renderer auf dem gemeinsamen Rahmen (seit 1.3.13, letzte Etappe des PDF-Umbaus,
CLAUDE.md "Gemeinsamer Dokumenttyp"; seit 1.3.20 der einzige -- app/quote_pdf.py und
app/quote_layout_pdf.py sind beim Aufräumen nach dem PDF-Umbau entfernt worden).

document_type="quote" liest seit 1.3.20 wie jeder andere Dokumenttyp über den "default"-Rückfall
(app/document_type_fallback.py) -- eine Migration hat die zuvor eigenständigen quote-Zeilen
(Briefpapier/Ränder/Logo/Firmenkopf/Fußzeile) gelöscht, seither gilt für das Angebot derselbe
geteilte Satz wie für Mahnung/Rechnung/Auftrag/Einsatzbericht. Bis dahin lief dieser Renderer
bewusst PARALLEL zum alten, positionsbasierten `quote_layout_pdf.py`, unter eigenem Namen, damit
beide gegen echte Angebote verglichen werden konnten (siehe docs/bestandsaufnahme_pdf.md,
Abschnitt 11.3), bevor umgestellt wurde.

Übertragszeile (echte, neue Funktion -- vorher gab es weder im alten noch im neuen Renderer eine
laufende Summe über Seitenumbrüche, nur eine statische Fortsetzungs-Beschriftung ohne Betrag):
die GESAMTE Positionsliste (alle Abschnitte samt Titeln) wird als EINE einzige Tabelle
(_CarryForwardItemsTable) gebaut, nicht als mehrere separate Tabellen mit dazwischenliegenden
Titel-Absätzen wie bei build_quote_items_flowables()/order_pdf.py. Grund: reportlab ruft split()
nur auf, wenn EINE Tabelle nicht vollständig auf die Seite passt -- ein Seitenumbruch GENAU
ZWISCHEN zwei separaten Flowables (z.B. eine Tabelle endet exakt am Seitenende, der nächste
Abschnittstitel beginnt erst auf der Folgeseite) würde dabei unbemerkt bleiben und keine
Übertragszeile bekommen. Da Titel hier als eigene, gespannte Zeilen INNERHALB derselben Tabelle
stehen, gibt es innerhalb der Positionsliste keine Flowable-Grenze mehr, an der ein Umbruch
"unsichtbar" für unsere split()-Überschreibung passieren könnte -- jeder Umbruch innerhalb der
Liste läuft über genau diese eine Tabelle.
"""

from decimal import Decimal
from html import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import (
    build_din5008_header_block, build_object_address_block, build_payment_tax_closing_block,
    build_styles, money, money_bare, ptext, qty,
)
from .projects import quote_to_dict
from .settings import get_or_create_general_settings

# Menge/EH/EP/GP wie bei Auftrag/Rechnung (order_pdf.py/invoice_pdf.py) -- "Leistung" nimmt den
# Rest der tatsächlich konfigurierten Satzspiegelbreite auf (CLAUDE.md "Positionstabelle:
# Menge/Einheit/Breite", 1.3.9). "oz" weicht seit 1.3.16 bewusst von Auftrag/Rechnung ab (dort
# weiterhin 23mm, hier nicht angetastet): 23mm war für eine frei formatierte GAEB-Ordnungszahl
# bemessen, tatsächlich ist die längste in der echten Datenbank vorkommende Positionsnummer
# genau 7 Zeichen (z.B. "01.0030") -- bei Helvetica 8pt ~11mm breit, +6pt Standard-Zellenpolster
# rechts (LEFTPADDING links ist bereits 0) ergibt knapp 13mm, hier auf 15mm aufgerundet als
# Sicherheitsspanne. Der komplette Unterschied (23-15=8mm) fließt automatisch vollständig in
# "Leistung" (= content_width minus Summe der übrigen, siehe build_quote_framed_pdf()), ohne
# eigene Rechnung -- genau die inhaltlich wichtigste Spalte, die laut Betreiber heute unnötig oft
# umbricht.
ITEMS_COL_WIDTHS_MM = {"oz": 15, "menge": 18, "eh": 14, "ep": 23, "gp": 25}


def _totals_table(rows: list[list[str]], content_width: float) -> Table:
    """Wie order_pdf.py::_totals_table()/invoice_pdf.py -- volle Rahmenbreite, genulltes
    Zellenpolster, letzte Zeile fett mit Linie darüber. Eigene, kleine Kopie statt eines
    gemeinsamen Imports: der Rest dieser Etappe fasst laut Auftrag nur an, was für das Angebot
    gebraucht wird; eine Zusammenführung aller vier fast identischen Summenblöcke ist laut
    CLAUDE.md ("Gemeinsamer Dokumenttyp", zweite Etappe) bewusst zurückgestellt, bis ein dritter
    Renderer umgestellt ist -- mit dem Angebot sind es jetzt drei (Mahnung hat keinen
    Summenblock, Rechnung/Auftrag/Angebot haben ihn), die Zusammenführung bleibt trotzdem ein
    eigener, hier nicht mitgemachter Schritt."""
    tt = Table(rows, colWidths=[content_width - 45 * mm, 45 * mm])
    tt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), .8, colors.black), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tt


def _build_continuation_marker_row(position_label: str, col_widths: list, styles: dict) -> Table:
    """Erscheint am Kopf einer Folgeseite, wenn diese mit einer Fortsetzungszeile eines
    Langtexts beginnt (siehe _CarryForwardItemsTable.split()) -- ohne diesen Hinweis stünde dort
    kleiner, grauer Text ohne jede Positionsnummer, der wie ein eigenständiges Fragment aussehen
    könnte, statt erkennbar zur Position auf der vorherigen Seite zu gehören (Nutzeranforderung,
    CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot). Dieselbe Zellenaufteilung wie eine
    Fortsetzungszeile selbst (leere OZ-Spalte, Text in der Leistungsspalte), damit die
    Fluchtlinie exakt übereinstimmt."""
    style = ParagraphStyle("ContinuationMarkerDE", parent=styles["small"], fontName="Helvetica-Oblique", textColor=colors.HexColor("#888888"))
    row = Table([["", "", "", Paragraph(escape(f"(Fortsetzung zu Position {position_label})"), style), "", ""]], colWidths=col_widths)
    row.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("TOPPADDING", (0, 0), (-1, 0), 2), ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
    ]))
    return row


def _build_carry_row(label: str, value, col_widths: list, styles: dict) -> Table:
    """Eine einzelne Übertragszeile ("Übertrag auf nächste Seite"/"Übertrag von vorheriger
    Seite") -- dieselben Spaltenbreiten wie die Positionstabelle, Beschriftung über die ersten
    fünf Spalten gespannt, Betrag rechtsbündig in der letzten (GP-)Spalte, damit sie optisch
    unter der Summenspalte der Positionen steht. Seit 1.3.17 money_bare() statt money(): diese
    Zelle liegt IN der GP-Spalte (nur über mehrere Spalten hinweg beschriftet), sie folgt deshalb
    derselben Konvention wie jede andere Zelle dieser Spalte -- die Einheit steht bereits einmalig
    im Spaltenkopf "GP/EUR", nicht mehr in der Zelle selbst."""
    style = ParagraphStyle("CarryRowDE", parent=styles["small"], fontName="Helvetica-Oblique")
    row = Table([[Paragraph(escape(label), style), "", "", "", "", money_bare(value)]], colWidths=col_widths)
    row.setStyle(TableStyle([
        ("SPAN", (0, 0), (4, 0)),
        ("ALIGN", (5, 0), (5, 0), "RIGHT"),
        ("FONTNAME", (5, 0), (5, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("LINEABOVE", (0, 0), (-1, 0), .5, colors.HexColor("#999999")),
        ("LINEBELOW", (0, 0), (-1, 0), .5, colors.HexColor("#999999")),
        ("TOPPADDING", (0, 0), (-1, 0), 3), ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
    ]))
    return row


class _CarryForwardItemsTable(Table):
    """Eine Table-Unterklasse, deren split() beim Seitenumbruch automatisch eine Übertragszeile
    anhängt (aktuelle Seite) bzw. voranstellt (Folgeseite) -- die laufende Netto-Summe kommt aus
    einer beim Bauen vorab berechneten, pro Körperzeile fortgeschriebenen Liste
    (row_cumulative[i] = Summe nach Körperzeile i; Titelzeilen tragen den Wert der Vorzeile
    unverändert fort, sie tragen selbst nichts bei).

    reportlab konstruiert die beiden Split-Teile intern über self.__class__(...) (siehe
    Table._splitRows() in reportlab/platypus/tables.py) -- unsere Unterklasse bleibt dadurch auch
    nach dem Splitten erhalten, ABER reportlab kennt row_cumulative/carry_row_builder nicht und
    reicht sie beim Nachbau nicht durch (nur die reportlab-eigenen Konstruktorargumente wie
    colWidths/repeatRows/cellStyles/normalizedData). __init__ braucht deshalb Standardwerte für
    beide, split() patcht sie auf dem zurückgegebenen zweiten Teil ("bottom") direkt nach, bevor
    es zurückgegeben wird -- nur so weiß ein DRITTER Split (eine noch längere Liste über drei oder
    mehr Seiten) wieder, ab welcher Zeile die Summe weiterzählt.

    Der verfügbare Platz für den eigentlichen Split wird VOR dem eigentlichen Table.split()-Aufruf
    um die Höhe einer Übertragszeile verkleinert -- sonst würde reportlabs eigene Aufteilung die
    aktuelle Seite bereits bis zum letzten Millimeter mit Positionszeilen füllen und für die
    zusätzliche, hier eingefügte Übertragszeile am Seitenende keinen Platz mehr lassen (sie würde
    dann selbst auf die nächste Seite rutschen -- keine Übertragszeile am Fuß der aktuellen
    Seite, sondern zwei am Kopf der nächsten).

    Fund an einem echten, zehnseitigen Angebot (A-2026-0016, siehe CLAUDE.md "Gemeinsamer
    Dokumenttyp"/Angebot): reportlabs Frame.add() platziert JEDES zurückgegebene Element dort,
    wo es gerade noch hinpasst -- reichte auf der endenden Seite nach `top` UND
    `carry_out_row` noch Platz (regelmäßig der Fall, da nur die Höhe EINER Zeile reserviert
    wird), landete `carry_in_row` fälschlich AUCH noch auf der alten Seite, direkt unter
    `carry_out_row` -- beide Zeilen standen dann nebeneinander auf derselben Seite, statt den
    Seitenwechsel zu markieren, und die neue Seite begann ohne jeden Hinweis auf den Übertrag.
    Ein `PageBreak()` zwischen beiden erzwingt den Wechsel an exakt dieser Stelle, unabhängig
    davon, wie viel Platz noch übrig wäre -- reportlab erkennt PageBreak-Objekte auch dann, wenn
    sie (wie hier) aus einem split()-Ergebnis stammen, nicht nur aus der ursprünglichen Story
    (siehe BaseDocTemplate.handle_flowable(), das jedes Element unabhängig von seiner Herkunft
    per isinstance() prüft).

    row_kind (seit 1.3.15, CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot -- Zeilenumbruch-Variante
    für lange Positionstexte): parallel zu row_cumulative eine Liste von (kind, position_label)
    je Körperzeile -- kind ist "header" (die unteilbare OZ/Kurztext/Menge/EH/EP/GP-Zeile einer
    Position), "continuation" (eine Fortsetzungszeile ihres Langtexts) oder "title"
    (Abschnittstitel). Fällt der Seitenumbruch so, dass die erste Zeile von `bottom` eine
    "continuation"-Zeile ist, fehlt ihr auf der neuen Seite jeder Bezug zu ihrer Position (keine
    OZ-Nummer, kein Kurztext sichtbar) -- ein zusätzlicher, kleiner Hinweis
    (continuation_marker_builder) wird dann vor `bottom` eingefügt."""

    def __init__(self, data, *, row_cumulative=None, carry_row_builder=None, row_kind=None, continuation_marker_builder=None, **kwargs):
        Table.__init__(self, data, **kwargs)
        self._row_cumulative = row_cumulative
        self._carry_row_builder = carry_row_builder
        self._row_kind = row_kind
        self._continuation_marker_builder = continuation_marker_builder

    def split(self, availWidth, availHeight):
        if not self._row_cumulative or self._carry_row_builder is None:
            return Table.split(self, availWidth, availHeight)

        probe = self._carry_row_builder("Übertrag auf nächste Seite", Decimal("0"))
        _, carry_height = probe.wrap(availWidth, availHeight)
        reserved_height = max(availHeight - carry_height - 2, 0)

        pieces = Table.split(self, availWidth, reserved_height)
        if not pieces:
            return []
        top, bottom = pieces

        repeat = self.repeatRows if isinstance(self.repeatRows, int) else len(self.repeatRows or ())
        k = len(top._cellvalues) - repeat
        if k < 1:
            return []
        carry_value = self._row_cumulative[k - 1]

        carry_out_row = self._carry_row_builder("Übertrag auf nächste Seite", carry_value)
        carry_in_row = self._carry_row_builder("Übertrag von vorheriger Seite", carry_value)
        bottom._row_cumulative = self._row_cumulative[k:]
        bottom._carry_row_builder = self._carry_row_builder
        bottom._row_kind = self._row_kind[k:] if self._row_kind else None
        bottom._continuation_marker_builder = self._continuation_marker_builder

        extra = [carry_out_row, PageBreak(), carry_in_row]
        if self._row_kind and k < len(self._row_kind) and self._continuation_marker_builder is not None:
            kind, position_label = self._row_kind[k]
            if kind == "continuation":
                extra.append(self._continuation_marker_builder(position_label))
        return [top, *extra, bottom]


def _build_items_table(
    items_by_section: dict, children: dict, styles: dict, col_widths: list, carry_row_builder,
    continuation_marker_builder=None,
):
    """Baut die GESAMTE Positionsliste (alle Abschnitte samt Titeln) als eine einzige
    _CarryForwardItemsTable -- siehe Moduldocstring, warum das für eine lückenlose Übertragszeile
    nötig ist. Reihenfolge/Traversierung identisch zu build_quote_items_flowables()/
    order_pdf.py::add_items(): Positionen ohne Titel zuerst, dann je Abschnitt Titel(+Beschreibung)
    gefolgt von seinen Positionen, verschachtelt für Unterabschnitte.

    Seit 1.3.15 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot -- Zeilenumbruch-Variante für lange
    Positionstexte): reportlab kann eine Tabellenzeile nur als Ganzes umbrechen (verifiziert
    direkt am reportlab-Quelltext, Table._splitRows()s doInRowSplit-Zweig splittet ausschließlich
    rohe, mehrzeilige Strings, keine Paragraph-Flowables) -- ein Langtext, der bisher als EIN
    Paragraph in der Kopfzeile der Position steckte, musste deshalb komplett mit ihr auf die
    nächste Seite wandern, sobald er nicht mehr vollständig auf die restliche Seite passte, und
    ließ die alte Seite bis zu einem Drittel leer (an A-2026-0016 gemessen). Jede Position ist
    jetzt eine UNTEILBARE Kopfzeile (OZ/Kurztext/Menge/EH/EP/GP, wie gefordert nie von ihrem
    Preis getrennt) GEFOLGT von einer eigenen Tabellenzeile je durch "\\n" getrenntem Absatz im
    Langtext -- reportlab kann jetzt zwischen JEDER dieser Zeilen umbrechen, auch mitten in
    einer Position. Ein Langtext ganz ohne eingebettete Zeilenumbrüche bleibt weiterhin eine
    einzige, unteilbare Fortsetzungszeile (siehe CLAUDE.md, "Bekannte, bewusst offene Punkte" --
    echtes Umbrechen mitten in einem Absatz würde das Extrahieren bereits umbrochener Zeilen aus
    einem gelayouteten Paragraph-Objekt erfordern, deutlich fragiler als der hier gewählte Weg)."""
    small, body = styles["small"], styles["body"]
    h2_cell = ParagraphStyle("H2Cell", parent=styles["h2"], spaceBefore=0, spaceAfter=0)
    h3_cell = ParagraphStyle("H3Cell", parent=styles["h3"], spaceBefore=0, spaceAfter=0)
    continuation_style = ParagraphStyle("LongTextRowDE", parent=small, textColor=colors.HexColor("#666666"))

    data = [["Pos.", "Menge Einh.", "", "Leistung", "EP/EUR", "GP/EUR"]]
    title_rows: list[int] = []
    continuation_rows: list[int] = []
    separator_rows: list[int] = [0]  # Zeilen MIT Trennlinie danach -- Spaltenkopf immer dabei.
    row_cumulative: list[Decimal] = []
    row_kind: list[tuple[str, str | None]] = []
    running = Decimal("0")

    def add_items(section_id):
        nonlocal running
        for item in items_by_section.get(section_id, []):
            position_label = item.get("gaeb_oz") or item["position_number"]
            label = ptext(item["short_text"])
            if item.get("include_in_total", True):
                running += Decimal(item["line_total"])
            else:
                label += "<br/><font size=7><b>Optional / nicht in Angebotssumme enthalten</b></font>"
            data.append([
                Paragraph(escape(position_label), small),
                qty(item["quantity"]), escape(item["unit"]), Paragraph(label, body),
                money_bare(item["unit_price"]), money_bare(item["line_total"]),
            ])
            row_cumulative.append(running)
            row_kind.append(("header", position_label))
            last_row_idx = len(data) - 1

            chunks = [c for c in (item.get("long_text") or "").split("\n") if c.strip()]
            for chunk in chunks:
                data.append(["", "", "", Paragraph(ptext(chunk), continuation_style), "", ""])
                row_cumulative.append(running)
                row_kind.append(("continuation", position_label))
                last_row_idx = len(data) - 1
                continuation_rows.append(last_row_idx)

            # Die Trennlinie zu der jeweils NÄCHSTEN Position/dem nächsten Titel gehört ans Ende
            # des GESAMTEN Blocks (Kopfzeile + alle Fortsetzungszeilen dieser Position), nicht an
            # jede einzelne Zeile dazwischen -- sonst sähe jede Fortsetzungszeile wie eine eigene,
            # neue Position aus.
            separator_rows.append(last_row_idx)

    def add_title(text: str, style: ParagraphStyle):
        data.append([Paragraph(text, style), "", "", "", "", ""])
        title_rows.append(len(data) - 1)
        row_cumulative.append(running)
        row_kind.append(("title", None))

    add_items(None)
    for top in children.get(None, []):
        text = f"{escape(top.get('section_number') or '')} {escape(top['title'])}"
        if top.get("description"):
            text += f"<br/><font size=7 color='#666666'>{ptext(top['description'])}</font>"
        add_title(text, h2_cell)
        add_items(top["id"])
        for child in children.get(top["id"], []):
            child_text = f"{escape(child.get('section_number') or '')} {escape(child['title'])}"
            if child.get("description"):
                child_text += f"<br/><font size=7 color='#666666'>{ptext(child['description'])}</font>"
            add_title(child_text, h3_cell)
            add_items(child["id"])

    if len(data) == 1:
        return None  # keine einzige Position -- kein Baustein, wie build_quote_items_flowables()

    style_commands = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        # Spaltenreihenfolge seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot, Punkt 2):
        # Pos., Menge, EH, Leistung, EP/EUR, GP/EUR -- Menge/EH stehen jetzt VOR der Leistung
        # (Vorbild: das dem Betreiber bekannte Vergleichsdokument), Kopfzelle "Menge Einh." spannt
        # beide Spalten (SPAN weiter unten). Menge rechtsbündig, EH direkt links daneben
        # (verringertes Zwischenpolster unten), damit "1,00 psch" wie eine zusammengehörige
        # Einheit wirkt statt wie zwei beliebige Zellen. EP/GP bleiben wie bisher (seit 1.3.16)
        # zentriert -- Betreiberwunsch, siehe frühere Begründung dazu im Changelog.
        ("ALIGN", (1, 0), (2, 0), "CENTER"), ("SPAN", (1, 0), (2, 0)),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"), ("ALIGN", (2, 1), (2, -1), "LEFT"),
        ("RIGHTPADDING", (1, 1), (1, -1), 2), ("LEFTPADDING", (2, 1), (2, -1), 0),
        ("ALIGN", (4, 0), (5, -1), "CENTER"),
        # Standard: KEINE Trennlinie -- wird gezielt nur für separator_rows (Spaltenkopf + jeweils
        # letzte Zeile eines Positions-Blocks) wieder eingeschaltet, siehe unten. Vorher lag sie
        # auf jeder Zeile, das hätte bei mehreren Zeilen je Position (Kopf + Fortsetzungszeilen)
        # jede Fortsetzungszeile wie eine eigene, neue Position aussehen lassen.
        ("LINEBELOW", (0, 0), (-1, -1), 0, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
    ]
    for row_idx in separator_rows:
        style_commands.append(("LINEBELOW", (0, row_idx), (-1, row_idx), .25, colors.HexColor("#cccccc")))
    for row_idx in title_rows:
        style_commands += [
            ("SPAN", (0, row_idx), (-1, row_idx)),
            ("TOPPADDING", (0, row_idx), (-1, row_idx), 8),
        ]
    for row_idx in continuation_rows:
        # Ohne diese Reduzierung bläht die Aufteilung in einzelne Zeilen ein Angebot spürbar auf:
        # das volle 4pt/4pt-Zellenpolster kam vorher nur einmal pro Position vor (ein einziger
        # mehrzeiliger Paragraph, mit normalem Zeilenabstand zwischen den Zeilen), jetzt einmal
        # PRO Absatz des Langtexts. An A-2026-0016 gemessen: ohne diese Zeile wuchs das Angebot
        # von 11 auf 12 Seiten, nur durch das zusätzliche Zellenpolster -- mit ihr auf 10.
        style_commands += [
            ("TOPPADDING", (0, row_idx), (-1, row_idx), 0), ("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 1),
        ]

    def carry_row_builder_bound(label, value):
        return carry_row_builder(label, value, col_widths)

    marker_builder_bound = None
    if continuation_marker_builder is not None:
        def marker_builder_bound(position_label):
            return continuation_marker_builder(position_label, col_widths)

    return _CarryForwardItemsTable(
        data, colWidths=col_widths, repeatRows=1, style=TableStyle(style_commands),
        row_cumulative=row_cumulative, carry_row_builder=carry_row_builder_bound,
        row_kind=row_kind, continuation_marker_builder=marker_builder_bound,
    )


def build_quote_framed_pdf(db, quote) -> bytes:
    data = quote_to_dict(quote)
    general = get_or_create_general_settings(db)
    customer = quote.project.customer
    property_obj = quote.project.property
    styles = build_styles()
    body, h1 = styles["body"], styles["h1"]

    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    sender_line = " - ".join(x for x in sender_parts if x)

    recipient_lines = [customer.name]
    # Gefunden an einem echten Angebot (CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot): Kunde UND
    # Ansprechpartner sind bei einer Einzelperson oft derselbe Name -- eine zweite, identische
    # Zeile darunter ist keine zusätzliche Information, nur eine sichtbare Wiederholung.
    if customer.contact_person and customer.contact_person.strip().casefold() != (customer.name or "").strip().casefold():
        recipient_lines.append(customer.contact_person)
    if customer.street:
        recipient_lines.append(customer.street)
    ccity = " ".join(x for x in [customer.postal_code, customer.city] if x)
    if ccity:
        recipient_lines.append(ccity)

    # Seit 1.3.20 (Aufräumen nach dem PDF-Umbau): "quote" hat keine eigenen Zeilen mehr, liest
    # über den "default"-Rückfall wie jeder andere Dokumenttyp (app/document_type_fallback.py).
    content_width = frame_content_width(get_margins(db, "quote", "first"))

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta = data.get("document_meta") or {}
        quote_date = meta.get("quote_date")
        valid_until = meta.get("valid_until")
        meta_rows = [
            ("Angebotsnr.", data["quote_number"]),
            ("Datum", quote_date.strftime("%d.%m.%Y") if quote_date else ""),
            ("Gültig bis", valid_until.strftime("%d.%m.%Y") if valid_until else ""),
            ("Projekt", data["project_number"]),
        ]
        if meta.get("contact_person"):
            meta_rows.append(("Ansprechp.", meta["contact_person"]))
        meta_rows.append(("Seite", page_value))

        story = list(build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles, content_width=content_width))

        object_lines = []
        if property_obj:
            if property_obj.street:
                object_lines.append(property_obj.street)
            pcity = " ".join(x for x in [property_obj.postal_code, property_obj.city] if x)
            if pcity:
                object_lines.append(pcity)
        story += build_object_address_block(property_obj.name if property_obj else None, object_lines, styles)

        story.append(Paragraph(ptext(data["title"]), h1))
        if data.get("intro_text"):
            story += [Paragraph(ptext(data["intro_text"]), body), Spacer(1, 5 * mm)]

        children: dict = {}
        for s in data.get("sections", []):
            children.setdefault(s["parent_id"], []).append(s)
        for rows in children.values():
            rows.sort(key=lambda x: (x["sort_order"], x["id"]))
        items_by_section: dict = {}
        for item in data["items"]:
            items_by_section.setdefault(item.get("section_id"), []).append(item)
        for rows in items_by_section.values():
            rows.sort(key=lambda x: (x["layout_sort_order"], x["id"]))

        fixed_width = sum(ITEMS_COL_WIDTHS_MM.values()) * mm
        leistung_width = content_width - fixed_width
        col_widths = [
            ITEMS_COL_WIDTHS_MM["oz"] * mm, ITEMS_COL_WIDTHS_MM["menge"] * mm,
            ITEMS_COL_WIDTHS_MM["eh"] * mm, leistung_width,
            ITEMS_COL_WIDTHS_MM["ep"] * mm, ITEMS_COL_WIDTHS_MM["gp"] * mm,
        ]

        def carry_row_builder(label, value, widths):
            return _build_carry_row(label, value, widths, styles)

        def continuation_marker_builder(position_label, widths):
            return _build_continuation_marker_row(position_label, widths, styles)

        table = _build_items_table(items_by_section, children, styles, col_widths, carry_row_builder, continuation_marker_builder)
        if table is not None:
            story += [table, Spacer(1, 3 * mm)]

        story.append(Spacer(1, 5 * mm))
        totals = [
            ["Nettosumme", money(data["net_total"])],
            [f"zzgl. MwSt. {qty(data['vat_rate'])} %", money(data["vat_total"])],
            ["Angebotssumme brutto", money(data["gross_total"])],
        ]
        if Decimal(data.get("optional_total") or 0) != 0:
            totals.insert(1, ["Optionale Positionen (nicht enthalten)", money(data["optional_total"])])
        story += [_totals_table(totals, content_width), Spacer(1, 7 * mm)]

        if meta.get("execution_period"):
            story += [Paragraph(f"<b>Ausführungszeitraum:</b> {ptext(meta['execution_period'])}", body), Spacer(1, 2 * mm)]
        story += build_payment_tax_closing_block(
            styles, payment_terms=meta.get("payment_terms"), tax_notice_text=data.get("tax_notice_text"),
            outro_text=data.get("outro_text"), outro_text_2=data.get("outro_text_2"),
        )
        return story

    continuation_header_rows = [
        ("Angebotsnr.", data["quote_number"]), ("Projekt", data["project_number"]),
    ]

    return render_framed_pdf(
        db, document_type="quote", title=f"{data['quote_number']} - {data['title']}",
        content_story=build_story, continuation_header_rows=continuation_header_rows,
    )
