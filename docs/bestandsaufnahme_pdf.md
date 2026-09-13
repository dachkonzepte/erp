# Bestandsaufnahme PDF-Renderer

Stand: 10.09.2026, Version 1.3.0. Reine Recherche gegen den tatsächlichen Code (kein
Produktivcode geändert, kein Schema geändert, kein Layout geändert). Zweck: Grundlage für den
geplanten Umbau auf einen gemeinsamen, im Layout-Designer konfigurierbaren RAHMEN (Briefkopf,
Logo, Meta-Block, Fußzeile, Ränder, Schriften, Farben) um einen weiterhin fließenden
INHALTSBEREICH je Dokumenttyp.

## Inhalt

1. Vollständige Liste aller PDF-Renderer
2. Technische Bauart je Renderer
3. Layout-Designer-Nutzung: wer, was, was ist fest verdrahtet
4. `DocumentPageMargins` im Detail
5. Briefkopf, Meta-Block, Fußzeile, Hintergrund je Renderer
6. Seitenzahlen und der "1/16 → 10/1"-Befund
7. Bereits mehrfach vorhandene Bausteine
8. Dokumente mit unvorhersehbar langem Inhalt
9. Grenzen des rohen Canvas beim Angebot
10. Testabdeckung
11. Vorschlag für den Umbau
12. Risiken und offene Entscheidungen

---

## 1. Vollständige Liste aller PDF-Renderer

Ermittelt per `grep -r "SimpleDocTemplate\|canvas.Canvas\|from reportlab" app/` – **acht**
Funktionen erzeugen PDFs, verteilt auf sieben Dateien plus eine reine Bausteinbibliothek ohne
eigene Einstiegsfunktion:

| # | Datei | Einstiegsfunktion | Erzeugt | Aufgerufen von |
|---|---|---|---|---|
| 1 | `app/quote_pdf.py:94` | `build_quote_pdf(db, quote)` | Angebot – **älterer, fließender** Renderer | `routers/quotes.py:229` (`GET /api/quotes/{id}/pdf`, Button "PDF-Vorschau (älterer Weg)") |
| 2 | `app/quote_layout_pdf.py:420` | `build_quote_layout_pdf(db, quote, *, include_background=True)` | Angebot – **aktueller, Designer-gesteuerter** Renderer | `routers/quotes.py:263` (`GET /api/quotes/{id}/pdf-layout-preview`, Button "PDF-Vorschau"); `app/projects.py:612` (`send_quote_email()`, tatsächlicher Anhang beim Versand) |
| 3 | `app/order_pdf.py:22` | `build_order_pdf(db, order)` | Auftragsbestätigung | `routers/orders.py:132` (`GET /api/orders/{id}/pdf`); `app/orders.py:381` (`send_order_email()`) |
| 4 | `app/invoice_pdf.py:30` | `build_invoice_pdf(db, invoice)` | Rechnung (alle vier Rechnungstypen) | `routers/invoices.py:253` (`GET /api/invoices/{id}/pdf`); `app/invoices.py:836` (`send_invoice_email()`) |
| 5 | `app/reminder_pdf.py:32` | `build_reminder_pdf(db, reminder)` | Mahnung (1./2./3. Stufe) | `routers/reminders.py:145` (`GET /api/reminders/{id}/pdf`); `app/reminders.py:258` (`send_reminder_email()`) |
| 6 | `app/service_report_pdf.py:105` | `build_service_report_pdf(db, report)` | Einsatzbericht (nur bereits unterschriebene) | `routers/service_reports.py:156` (`GET /api/service-reports/{id}/pdf`) |
| 7 | `app/time_backoffice.py:176` | `build_timesheet_pdf(db, start_date, end_date, employee_id=None)` | Stundenzettel (Backoffice) | `routers/time_backoffice.py:109` (`GET /api/time-backoffice/timesheet.pdf`, adminpflichtig) |
| – | `app/document_pdf.py` | *(keine eigene Einstiegsfunktion)* | – geteilte Bausteine `money()`/`qty()`/`ptext()`/`build_styles()`/`build_company_header_block()`/`build_customer_and_meta_block()`/`build_customer_address_block()`/`build_meta_table_block()`/`build_object_address_block()`/`build_payment_tax_closing_block()` | importiert von #1–5 (nicht von #6, nicht von #7) |

**Wichtiger Befund vorweg:** Für Angebote existieren **zwei parallele, vollständig unabhängige
Renderer** mit demselben fachlichen Ergebnis. `quote_editor.html` zeigt beide Buttons nebeneinander
(`app/templates/quote_editor.html:34-36`):

```html
<button class="secondary" onclick="openPdfLayoutPreview()">PDF-Vorschau</button>
<label ...><input type="checkbox" id="layoutPreviewWithBackground" checked ...> Mit Briefkopf</label>
<button class="secondary" onclick="openPdf()" title="Älterer, einfacherer PDF-Weg ohne Layout-Designer-Konfiguration">PDF-Vorschau (älterer Weg)</button>
```

`build_quote_layout_pdf` ist der **primäre** Weg (erster Button, außerdem der tatsächlich per
E-Mail versendete Anhang, siehe Kommentar `routers/quotes.py:236-239`). `build_quote_pdf` ist der
Restbestand des ursprünglichen, fließenden Renderers und wird bewusst weiter angeboten
("verlässlicher Standard", `routers/quotes.py:255`). Für den geplanten Umbau ist **`quote_layout_pdf.py`** das
relevante "heutige Angebots-Layout" – darauf beziehen sich Abschnitt 6 und 9.

---

## 2. Technische Bauart je Renderer

| Renderer | Bauart | Header/Footer-Mechanik |
|---|---|---|
| `build_quote_pdf` | `SimpleDocTemplate` + `story`-Liste (Platypus/Flowables) | `doc.build(story, onFirstPage=_footer, onLaterPages=_footer)` – Callback zeichnet nur die Fußzeile |
| `build_quote_layout_pdf` | **Rohes Canvas** (`reportlab.pdfgen.canvas.Canvas`), manuelles `wrapOn`/`drawOn`/`showPage()` | Kein `onFirstPage`/`onLaterPages` – alles wird Zeile für Zeile manuell positioniert |
| `build_order_pdf` | `SimpleDocTemplate` + `story` | wie `build_quote_pdf` |
| `build_invoice_pdf` | `SimpleDocTemplate` + `story` | wie `build_quote_pdf` |
| `build_reminder_pdf` | `SimpleDocTemplate` + `story` | wie `build_quote_pdf` |
| `build_service_report_pdf` | `SimpleDocTemplate` + `story`, zusätzlich `KeepTogether()` an sechs Stellen | wie `build_quote_pdf` |
| `build_timesheet_pdf` | `SimpleDocTemplate` + `story`, manuelle `PageBreak()` zwischen Mitarbeitern | **kein** Footer/Header-Callback überhaupt |

### 2.1 `SimpleDocTemplate` + Story (Beispiel `invoice_pdf.py:25-41`)

```python
def _footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(20 * mm, 12 * mm, f"Rechnung - Seite {doc.page}"); canvas.restoreState()


def build_invoice_pdf(db, invoice) -> bytes:
    ...
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=16*mm, leftMargin=18*mm, topMargin=17*mm, bottomMargin=20*mm, ...)
    styles = build_styles()
    story = []
    story += build_company_header_block(general, styles)
    story += build_customer_and_meta_block(addr, meta_rows, styles)
    ...
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
```

Das Muster ist in `quote_pdf.py`, `order_pdf.py`, `invoice_pdf.py`, `reminder_pdf.py` und
`service_report_pdf.py` **identisch aufgebaut** (Import derselben `document_pdf.py`-Bausteine,
eigene `_footer()`-Funktion, `story`-Liste, ein `doc.build(...)`-Aufruf am Ende). `doc.page` ist
reportlabs eingebautes, immer korrektes Attribut für die aktuelle Seitenzahl – es kennt nur "wo bin
ich gerade", nicht "wie viele Seiten werden es insgesamt" (siehe Abschnitt 6).

### 2.2 Rohes Canvas (Beispiel `quote_layout_pdf.py:432-441`, `454-469`)

```python
buf = BytesIO()
c = canvas_module.Canvas(buf, pagesize=A4)
c.setTitle(f"{data['quote_number']} - {data['title']}")
c.setAuthor(general.company_name)

background = get_background(db, "quote") if include_background else None
if background is not None:
    path = background_path(background.stored_filename)
    if path.is_file():
        c.drawImage(str(path), 0, 0, width=PAGE_WIDTH_MM * mm, height=PAGE_HEIGHT_MM * mm, preserveAspectRatio=False)

for block in blocks_before:
    ...
    if block.block_type == "logo":
        ...
        c.drawImage(str(path), float(block.x_mm) * mm, draw_y, width=..., height=..., preserveAspectRatio=True, mask="auto")
        continue
    flowables = _block_flowables(block, ...)
    _draw_flowables_at(c, flowables, block.x_mm, block.y_mm, block.width_mm, block.height_mm)
```

Jeder `DocumentLayoutBlock` wird einzeln an seiner konfigurierten `(x_mm, y_mm)`-Position
gezeichnet (`_draw_flowables_at()`, `quote_layout_pdf.py:134-152`) – reportlabs
Platypus-Flowables (`Table`, `Paragraph`) werden dabei zweckentfremdet: `wrapOn()`/`drawOn()`
statt eines automatischen Flusses durch ein `Frame`. Es gibt **kein** `SimpleDocTemplate`, **kein**
`Frame`, **kein** `onPage`-Callback – die gesamte Seitenlogik (wann `showPage()`, wo die
Fortsetzungs-Kopfzeile, wo der Hintergrund erneut gezeichnet wird) ist von Hand in
`_draw_items_table_paginated()` nachgebaut (siehe Abschnitt 6 und 9).

### 2.3 `time_backoffice.py:176-202` – Sonderfall ohne Header/Footer

```python
buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4), ...)
...
for idx,(emp_id,entries) in enumerate(...):
    story.append(Paragraph(f"<b>{escape(general.company_name)}</b> – Stundenzettel", styles["Heading2"]))
    ...
    if idx < len(grouped)-1: story.append(PageBreak())
...
doc.build(story); return buf.getvalue()
```

Landscape-A4, eigener, minimaler Styleset (nicht `document_pdf.build_styles()`), **kein**
`onFirstPage`/`onLaterPages` – also weder Seitenzahl noch Firmenkopf-Wiederholung. Pro Mitarbeiter
ein erzwungener `PageBreak()`, sonst reiner automatischer Fluss.

---

## 3. Layout-Designer-Nutzung: wer, was, was ist fest verdrahtet

**Nur ein einziger Renderer nutzt den Layout-Designer: `build_quote_layout_pdf`.** Alle anderen
sechs kennen `DocumentLayoutBlock`/`DocumentLayoutBackground`/`DocumentTableField`/
`DocumentPageMargins` überhaupt nicht (per Grep über `app/*.py` bestätigt – keine dieser vier
Klassen wird außerhalb von `quote_layout_pdf.py`, `document_layout.py`,
`document_layout_background.py`, `document_page_margins.py`, `document_table_fields.py` und
`routers/document_layout.py` importiert).

### 3.1 Die vier Modelle (`app/models.py:2287-2437`)

| Modell | Zweck | Spalten |
|---|---|---|
| `DocumentLayoutBlock` | Position/Größe/Sichtbarkeit je Baustein | `document_type`, `block_type`, `label`, `x_mm`, `y_mm`, `width_mm`, `height_mm`, `content` (nur `custom_text`), `font_size`, `font_weight`, `text_align`, `visible`, `sort_order` |
| `DocumentLayoutBackground` | Ein Hintergrundbild je Dokumenttyp | `document_type` (unique), `stored_filename`, `repeat_on_every_page` |
| `DocumentTableField` | Sichtbare Spalten/Zeilen **innerhalb** eines Tabellen-Bausteins | `document_type`, `block_type`, `field_key`, `label`, `is_custom`, `custom_value`, `visible`, `sort_order` |
| `DocumentPageMargins` | Feste Randabstände je Seitentyp | `document_type`, `page_type` (`first`\|`continuation`), `top_mm`, `bottom_mm`, `left_mm`, `right_mm` |

Alle vier tragen `document_type` als freien String. Die Konstante `DOCUMENT_TYPES = {"quote",
"order", "invoice", "reminder"}` (`app/document_layout.py:44`) definiert, was die **API**
akzeptiert (`_validate_document_type()` in `routers/document_layout.py:33-35`) – nicht, was ein
Renderer tatsächlich liest.

### 3.2 Was pro Dokumenttyp tatsächlich funktioniert

`ensure_default_layout()` (`app/document_layout.py:47-71`) seedet die zehn Standardbausteine
**ausschließlich für `document_type == "quote"`**:

```python
if document_type != "quote":
    # Für die übrigen drei Dokumenttypen ist das absichtlich noch nicht
    # ausgerollt (Klärung: "erst eins zum Ausprobieren, Rest folgt
    # später") -- ensure_default_layout() kennt zwar bereits alle vier
    # gültigen Typen, seedet aber bislang nur 'quote' wirklich.
    return []
```

Die zehn Standardbausteine (`DEFAULT_QUOTE_LAYOUT`, `app/document_layout.py:31-42`): `logo`
(standardmäßig unsichtbar), `company_header`, `customer_address`, `meta_table`, `object_address`,
`title_intro`, `items_table`, `totals`, `payment_tax_closing`, `footer_text`.

Das Frontend (`app/templates/document_layout_editor.html`) verstärkt diese Einschränkung
zusätzlich: **jeder** API-Aufruf ist dort mit dem literalen Pfadsegment `quote` hartkodiert
(`/api/document-layout/quote`, `/api/document-layout/quote/table-fields/${blockType}`,
`/api/document-layout/quote/margins/first` usw., 13 Fundstellen) – es gibt **keinen**
Dokumenttyp-Umschalter in der Oberfläche. Ergebnis: dreifache Sperre –

1. UI bietet nur "quote" an,
2. `ensure_default_layout()`/Migrationen seeden nur "quote" mit Vorgabewerten,
3. kein anderer Renderer liest die Tabellen überhaupt.

Die API selbst (`routers/document_layout.py`) ist bereits generisch für alle vier Typen gebaut –
ein `PUT /api/document-layout/order/margins/first` würde anstandslos eine Zeile anlegen, die
**kein** Renderer je liest.

### 3.3 Was konfigurierbar ist vs. was fest verdrahtet ist (nur `quote_layout_pdf.py`)

| Konfigurierbar über den Designer | Fest verdrahtet in `quote_layout_pdf.py` |
|---|---|
| Position/Größe/Sichtbarkeit jedes der 10 Bausteine (`DocumentLayoutBlock`) | Die Blockreihenfolge/-typen selbst (`block_type` ist eine feste Codeliste in `_block_flowables()`, kein freier Typ) |
| Schriftgröße/-schnitt/-ausrichtung – **nur für `custom_text`-Bausteine** (`_custom_text_style()`) | Schriftgröße/-schnitt aller vordefinierten Bausteine (`build_styles()` liefert feste `ParagraphStyle`s, z. B. `body` immer Helvetica 9.4pt) |
| Sichtbarkeit/Reihenfolge/Label einzelner Meta-/Summen-/Adressfelder (`DocumentTableField`) | Spaltenbreiten der Positionsliste (`ITEMS_COLUMN_WIDTHS_MM`, feste `dict`) |
| Eigene Zeilen bei `meta_table`/`totals`/`company_header`/`customer_address`/`object_address` (`is_custom=True`) | Farben (nirgends konfigurierbar – `colors.HexColor("#eeeeee")` etc. sind Literale) |
| Ein Hintergrundbild je Dokumenttyp, mit/ohne Wiederholung je Seite | Das Fortsetzungs-Kopfzeilenformat (`_draw_continuation_header()`, reiner Text "Fortsetzung, Seite N") |
| Randabstände Seite 1 / Folgeseiten (`DocumentPageMargins`) | Der Umbruch-Algorithmus selbst (`_draw_items_table_paginated()`) |
| Freier Zusatztext (`custom_text`-Baustein, beliebige Position) | Zeilenhöhen-/Padding-Werte innerhalb der Item-Tabelle |

**Kein Renderer** – auch nicht `quote_layout_pdf.py` – erlaubt heute die Konfiguration von
**Schriftfamilie oder Farbpalette**. `Helvetica`/`Helvetica-Bold` und eine Handvoll Hex-Farben
(`#eeeeee`, `#cccccc`, `#666666`, `#555555`, `#c0362c`) sind in `document_pdf.py`,
`quote_layout_pdf.py` und `service_report_pdf.py` jeweils eigenständig als Literale
eingetragen – für den geplanten "Schriften, Farben"-Teil des gemeinsamen Rahmens existiert also
noch **gar keine** Konfigurationsebene, auch nicht ansatzweise.

---

## 4. `DocumentPageMargins` im Detail

**Frage laut Auftrag: "prüfe, ob das heute schon geht" (separate Ränder für Seite 1 und
Folgeseiten) – Antwort: Ja, exakt das existiert bereits, aber nur für `document_type="quote"`.**

### 4.1 Spalten und Seitentypen

`app/models.py:2407-2437`:

```python
class DocumentPageMargins(Base):
    __tablename__ = "document_page_margins"
    __table_args__ = (UniqueConstraint("document_type", "page_type", name="uq_document_page_margins"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(20), index=True)
    page_type: Mapped[str] = mapped_column(String(20))  # 'first' | 'continuation'
    top_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    bottom_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    left_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    right_mm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

Genau **zwei** Seitentypen sind heute unterscheidbar: `first` (Seite 1) und `continuation`
(jede Folgeseite – **nicht** einzeln je Seitenzahl, alle Folgeseiten teilen sich dieselben
Randwerte). `PAGE_TYPES = {"first", "continuation"}` (`app/document_page_margins.py:16`).

Standardwerte (`app/document_page_margins.py:21-24`), identisch zu den vorher hart
einprogrammierten Werten:

| Seitentyp | oben | unten | links | rechts |
|---|---|---|---|---|
| `first` | 17,0 mm | 20,0 mm | 18,0 mm | 16,0 mm |
| `continuation` | 22,0 mm | 20,0 mm | 18,0 mm | 16,0 mm |

Nur der obere Rand unterscheidet sich (mehr Platz auf Seite 1 für den Firmenkopf).

### 4.2 Für welche Dokumente gilt es tatsächlich

`get_margins()`/`ensure_default_margins()`/`update_margins()` sind **generisch** nach
`document_type` parametrisiert – die Tabelle könnte beliebige Werte für "order"/"invoice"/
"reminder" speichern. Tatsächlich **gelesen** wird sie nur an genau zwei Stellen, beide in
`quote_layout_pdf.py:429-430`:

```python
first_margins = get_margins(db, "quote", "first")
continuation_margins = get_margins(db, "quote", "continuation")
```

`order_pdf.py`, `invoice_pdf.py`, `reminder_pdf.py`, `service_report_pdf.py`, `quote_pdf.py`
(der ältere Angebots-Renderer!) und `time_backoffice.py` haben ihre Ränder weiterhin **fest im
Code** stehen, identisch bei allen sechs (`rightMargin=16*mm, leftMargin=18*mm, topMargin=17*mm,
bottomMargin=20*mm` als `SimpleDocTemplate`-Konstruktorargumente – ein einziger, unveränderlicher
Wert, keine Unterscheidung Seite 1 vs. Folgeseite, weil `SimpleDocTemplate` bei automatischem
Fluss ohnehin nur einen Randsatz für das ganze Dokument kennt).

### 4.3 Wofür `top_mm`/`bottom_mm` innerhalb von `quote_layout_pdf.py` konkret verwendet werden

Nicht nur als optische Ränder, sondern als **harte Umbruchgrenzen** der Positionsliste
(`_draw_items_table_paginated()`, `quote_layout_pdf.py:90` und `:130`):

```python
page_limit = min(float(y_mm) + float(height_mm), PAGE_HEIGHT_MM - float(first_margins.bottom_mm))
...
cursor_y = float(continuation_margins.top_mm)
page_limit = PAGE_HEIGHT_MM - float(continuation_margins.bottom_mm)
```

`left_mm`/`right_mm` positionieren zusätzlich die Fortsetzungs-Kopfzeile
(`_draw_continuation_header(..., left_mm=float(continuation_margins.left_mm), top_mm=...)`),
schränken aber laut Docstring (`app/models.py:2420-2425`) **nicht** automatisch die freie
Positionierung einzelner Bausteine ein – ein Baustein kann im Editor trotzdem über den
konfigurierten Rand hinausragen.

### 4.4 Oberfläche

`app/templates/document_layout_editor.html:97-125` zeigt bereits zwei nebeneinanderliegende
Kartenbereiche "Seite 1" und "Folgeseiten" mit je vier Eingabefeldern (oben/unten/links/rechts,
mm) – die UI für getrennte Erst-/Folgeseiten-Ränder ist fertig und funktioniert, nur eben nur für
Angebote sichtbar/wirksam.

---

## 5. Briefkopf, Meta-Block, Fußzeile, Hintergrund je Renderer

Hinweis vorab: **"Seitenzahl" ist in keinem Renderer ein Meta-Block-Feld.** Weder
`PREDEFINED_TABLE_FIELDS["meta_table"]` (`document_table_fields.py:22-32`, neun mögliche Felder:
`quote_number`, `quote_date`, `valid_until`, `project_number`, `project_name`, `customer_name`,
`property_name`, `contact_person`, `caseworker`) noch die manuell gebauten `meta_rows` in
`order_pdf.py`/`invoice_pdf.py`/`reminder_pdf.py` enthalten je eine Seitenzahl – die Seitenzahl
taucht ausschließlich in der Fußzeile (SimpleDocTemplate-Renderer) bzw. der
Fortsetzungs-Kopfzeile (`quote_layout_pdf.py`) auf, nie im Meta-Block selbst.

| Renderer | Briefkopf | Meta-Block | Fußzeile | Hintergrund | Folgeseiten-Kopf |
|---|---|---|---|---|---|
| `quote_pdf.py` | `build_company_header_block()` – Firma+Adresse links, Kontakt rechts, **kein Logo** | `build_customer_and_meta_block()`: Angebotsnr./Datum/Projekt/Gültig bis/Ansprechp. | `_footer()`: `"Angebot - Seite {doc.page}"`, jede Seite | keiner | keine (automatischer Fluss, keine eigene Kopfzeile auf Folgeseiten) |
| `quote_layout_pdf.py` | eigener `company_header`-Baustein, **line_list**-Stil (ein Feld pro Zeile, kein Zwei-Spalten-Layout) + separater `logo`-Baustein (`c.drawImage`) | eigener `meta_table`-Baustein, **ein Feld pro Zeile** mit Label+Wert, konfigurierbar über `DocumentTableField` | nur auf **Seite 1**: `c.drawString(20mm, 12mm, f"{quote_number} - Seite 1")` (Zeile 479, **hartkodiert** "Seite 1", nutzt keine Variable) | ein Bild je Dokumenttyp, `repeat_on_every_page`-Schalter, Vollflächig (`0,0` bis `210×297mm`) | **ja** – `_draw_continuation_header()`: schlichter Text `"{quote_number} – Fortsetzung, Seite {page_number}"`, 10mm oberhalb des Folgeseiten-Randes; **keine** Fußzeile auf Folgeseiten |
| `order_pdf.py` | `build_company_header_block()`, kein Logo | `build_customer_and_meta_block()`: Auftragsnr./Datum/Ihr Angebot/Projekt, optional Sachbearb./Projektl. | `_footer()`: `"Auftragsbestätigung - Seite {doc.page}"` | keiner | keine |
| `invoice_pdf.py` | `build_company_header_block()`, kein Logo | `build_customer_and_meta_block()`: Rechnungsnr./Datum, optional Fällig bis | `_footer()`: `"Rechnung - Seite {doc.page}"` | keiner | keine |
| `reminder_pdf.py` | `build_company_header_block()`, kein Logo | `build_customer_and_meta_block()`: Mahnungsnr./Datum, zu Rechnung/vom | `_footer()`: `"Mahnung - Seite {doc.page}"` | keiner | keine |
| `service_report_pdf.py` | `build_company_header_block()`, kein Logo | **kein** Meta-Block – Auftrag/Kunde/Datum/Monteur als ein einziger `Paragraph` mit `<br/>` (`service_report_pdf.py:122-128`) | `_footer()`: `"Einsatzbericht - Seite {doc.page}"` | keiner | keine |
| `time_backoffice.py` | nur `"{Firmenname} – Stundenzettel"` als `Heading2`-Paragraph, keine Adresse/Kontakt | kein Meta-Block, nur Mitarbeitername + Zeitraum als Fließtext | **keine** (kein `onFirstPage`/`onLaterPages`) | keiner | keine |

Ein Firmenlogo als **Bild** erscheint aktuell in **keinem** der sechs `document_pdf.py`-basierten
Renderer – nur `quote_layout_pdf.py` zeichnet es (`block_type == "logo"`, eigener Zweig, kein
Flowable). `build_company_header_block()` (`document_pdf.py:69-84`) kennt nur Text.

---

## 6. Seitenzahlen und der "1/16 → 10/1"-Befund

### 6.1 Wie "Seite X" heute erzeugt wird

Ausschließlich über reportlabs eingebautes `doc.page` (SimpleDocTemplate-Renderer) bzw. einen
selbst mitgeführten `page_number`-Zähler (`quote_layout_pdf.py`). **Es gibt aktuell in keinem der
sieben Renderer irgendeine Form von Gesamtseitenzahl** – kein "Seite X / Y", kein "Seite X von
Y", kein Zwei-Durchlauf-Mechanismus, keine `NumberedCanvas`-artige Klasse. Das ist kein
Rand-/Einzelfall, sondern lückenlos: eine projektweite Suche nach `total_pages`, `PageCount`,
`getPageNumber`, `NumberedCanvas`, `canvasmaker`, `/ %` sowie jedem `"Seite ... {...} / {...}"`-
Muster ergab **null Treffer** außerhalb der hier zitierten `"Seite {doc.page}"`- bzw.
`"Seite {page_number}"`-Strings.

### 6.2 Der gemeldete Befund – empirisch nachgestellt

Um den gemeldeten Fall (Seite 1–9 "korrekt" `X / 16`, ab Seite 10 `X / 1`) einzuordnen, wurde ein
echtes ~130-Positionen-Angebot über `build_quote_layout_pdf()` erzeugt (7 Seiten) und der
**tatsächliche PDF-Textinhalt** durchsucht (Content-Streams dekomprimiert, Muster wie
`tests/test_v213_inspection_items.py::_extract_pdf_text`):

```
Seitenzahl (aus /Type/Page gezaehlt): 7
Treffer fuer 'Zahl / Zahl': []
Treffer fuer 'Seite ...': [b'Seite 1', b'Seite 2', b'Seite 3', b'Seite 4', b'Seite 5', b'Seite 6', b'Seite 7']
Vorkommen von 'Fortsetzung': 6
```

Das PDF selbst enthält also, exakt wie aus dem Code erwartet, nur `"Seite 1"` (Fußzeile, Seite 1)
sowie `"... – Fortsetzung, Seite 2"` bis `"... – Fortsetzung, Seite 7"` (Kopfzeile, Folgeseiten) –
**an keiner Stelle irgendeine Form von "X / Y"**. Das gilt unabhängig von der Seitenzahl,
insbesondere auch für zweistellige Seitenzahlen (mit mehr Positionen ließe sich dasselbe für 16
Seiten reproduzieren, das Ergebnis ändert sich strukturell nicht: der Code hat schlicht keine
Stelle, an der ein Gesamtwert überhaupt berechnet oder gedruckt würde).

### 6.3 Ursache

**Der beobachtete Text "X / 16" bzw. "X / 1" wird nicht von unserem Code erzeugt.** Er kann nicht
aus dem PDF-Inhalt stammen, weil dieser Inhalt – belegt durch die vollständige Durchsicht aller
sieben Renderer plus die empirische Textextraktion oben – niemals eine Gesamtseitenzahl
formatiert. Die mit Abstand plausibelste Erklärung: **das ist die Seitenanzeige des PDF-Betrachters
selbst** (z. B. die "aktuelle Seite / Gesamtzahl"-Anzeige in der Symbolleiste des in Chrome/Edge
eingebauten PDF-Viewers, der beim Öffnen über `window.open(url, '_blank')` – `quote_editor.html:200-201`
– verwendet wird; es gibt in diesem Projekt keinen eigenen, eingebetteten PDF.js-Viewer, siehe
Grep über `app/templates` nach `numPages`/`pdfDoc`/`PDFViewer` – null Treffer). Eine
Zifferzahl-abhängige Verkürzung des "Gesamt"-Feldes auf die erste Ziffer, sobald auch die
aktuelle Seite zweistellig wird, ist ein bekanntes Layout-Verhalten der Seitenzahl-Eingabebox
solcher eingebauten Betrachter, kein serverseitiges Phänomen.

**Wie sich das zweifelsfrei trennen lässt**, falls gewünscht: dieselbe erzeugte PDF-Datei in einem
zweiten Betrachter öffnen (z. B. Adobe Reader oder ein Download statt `window.open`) oder den
rohen Text-Layer wie oben extrahieren – beides würde die Vermutung bestätigen oder widerlegen,
ohne Code zu ändern.

### 6.4 Größe der Korrektur, falls eine ECHTE "Seite X von Y"-Anzeige gewünscht ist

Diese Funktion existiert heute an keiner Stelle – es wäre also eine **neue Funktion**, keine
Fehlerbehebung. Größenordnung:

- **Für die fünf `SimpleDocTemplate`-Renderer** (`quote_pdf.py`, `order_pdf.py`, `invoice_pdf.py`,
  `reminder_pdf.py`, `service_report_pdf.py`): klein. Reportlabs Standardmuster ist eine
  `canvas.Canvas`-Unterklasse, die `showPage()` abfängt, den Seitenzustand zwischenspeichert und
  erst in `save()` – wenn die Gesamtzahl real bekannt ist – jede Seite mit dem fertigen "X / Y"-Text
  tatsächlich schreibt (`canvasmaker=`-Argument von `SimpleDocTemplate`). Ca. 20–25 Zeilen einmalig
  (geteilt über `document_pdf.py`), plus eine Zeile Änderung je `_footer()`-Funktion (heute fünfmal
  fast identisch dupliziert, siehe Abschnitt 7).
- **Für `quote_layout_pdf.py`**: mittel. Die Gesamtseitenzahl wird erst am Ende von
  `_draw_items_table_paginated()` bekannt (dort bereits als dritter Rückgabewert `final_page`
  vorhanden!), aber die Seite-1-Fußzeile (Zeile 479) und jede Fortsetzungs-Kopfzeile werden
  **während** des Durchlaufs gezeichnet, bevor die Gesamtzahl feststeht – reines Canvas-Zeichnen
  kann nachträglich nicht mehr "vorher" geschriebene Seiten ändern. Nötig wäre entweder ein echter
  Zwei-Durchlauf (einmal nur zur Ermittlung von `final_page`, dann verwerfen und real zeichnen) oder
  – der ohnehin für den geplanten Umbau vorgeschlagene Weg (Abschnitt 11) – die Migration auf
  `BaseDocTemplate`, womit derselbe `canvasmaker`-Mechanismus wie bei den anderen fünf greift.

---

## 7. Bereits mehrfach vorhandene Bausteine

| Baustein | Wo vorhanden | Wie ähnlich | Fachlicher Unterschied |
|---|---|---|---|
| **Fußzeile mit Seitenzahl** | `quote_pdf.py:18-23`, `order_pdf.py:17-19`, `invoice_pdf.py:25-27`, `reminder_pdf.py:27-29`, `service_report_pdf.py:27-29` – **fünf** fast byte-identische `_footer(canvas, doc)`-Funktionen | Identisch bis auf das Label-Wort ("Angebot"/"Auftragsbestätigung"/"Rechnung"/"Mahnung"/"Einsatzbericht") und identische Koordinaten `20mm, 12mm` | Keiner – reine Kopie, kein fachlicher Grund für fünf getrennte Funktionen |
| **Firmenkopf** | `document_pdf.py:69-84` (`build_company_header_block`, Zwei-Spalten-Tabelle, kein Logo) **vs.** `quote_layout_pdf.py` `company_header`-Zweig (`_block_flowables:347-350`, line-list-Stil, konfigurierbare Felder, inkl. Logo separat) **vs.** `time_backoffice.py:189` (nur Firmenname als Überschrift) | Drei strukturell verschiedene Implementierungen derselben Absicht | Die layoutgesteuerte Variante ist bewusst anders (frei ein-/ausblendbare Felder), nicht nur kopiert – aber das Ergebnis ist dieselbe fachliche Information zweimal eigenständig gebaut |
| **Kunden-/Objektadresse** | `document_pdf.py:87-145` (drei Varianten: kombiniert, nur Kunde, nur Objekt) **vs.** `quote_layout_pdf.py` `customer_address`/`object_address`-Zweige (`_block_flowables:352-371`, wieder line-list mit `DocumentTableField`) | Zwei parallele Bausteinsysteme für denselben Zweck | Layout-Variante konfigurierbar (welche Zeilen), alte Variante fest (immer alle vorhandenen Zeilen) |
| **Meta-Block** | `document_pdf.py:87-105`/`120-133` (Zwei-Felder-pro-Zeile-Tabelle) **vs.** `quote_layout_pdf.py` `meta_table`-Zweig (`_block_flowables:357-366`, ein Feld pro Zeile) **vs.** `service_report_pdf.py:122-128` (ein einziger Paragraph, kein Tabellenbaustein) | Drei unterschiedliche Renderings derselben Informationsklasse | Jeder Dokumenttyp befüllt zusätzlich eigene `meta_rows` inline in seiner eigenen Datei (Angebotsnr. vs. Auftragsnr. vs. Rechnungsnr. vs. Mahnungsnr.) – das ist fachlich zwingend unterschiedlich, aber die **Tabellenmechanik** darunter ist zwischen `quote_pdf`/`order_pdf`/`invoice_pdf`/`reminder_pdf` bereits geteilt (`document_pdf.py`), nur `quote_layout_pdf.py` und `service_report_pdf.py` bauen komplett eigenständig |
| **Tabellenkopf/Positionsliste** | `order_pdf.py:60-67`, `quote_pdf.py:39-59` (`build_quote_items_flowables`, von `quote_pdf.py` UND ursprünglich als Vorlage für `quote_layout_pdf.py` gedacht), `invoice_pdf.py:65-80`, `quote_layout_pdf.py:270-330` (`_build_configured_items_table`, eigene, konfigurierbare Variante), `service_report_pdf.py` (Prüfpunkt-/Zeittabellen, eigener Stil), `time_backoffice.py:191-198` | `order_pdf.py` und `quote_pdf.py` sind sich am ähnlichsten (beide 6 Spalten OZ/Leistung/Menge/EH/EP/GP, fast identische `TableStyle`), weil ein Auftrag ja ein beauftragtes Angebot ist | `invoice_pdf.py` hat zwingend andere Spalten (Soll/Ist/abgerechnete Menge statt nur Menge) – fachlich begründet. `quote_layout_pdf.py` dupliziert die TableStyle-Werte ein drittes Mal, obwohl `build_quote_items_flowables` bereits existierte (bewusste Entscheidung laut Docstring `quote_pdf.py:26-32`, wegen frei wählbarer Spalten) |
| **Summenblock** | `invoice_pdf.py:82-85`, `order_pdf.py:79-83`, `quote_pdf.py:75-91` (`build_quote_totals_flowables`, einzige ausgelagerte Variante), `reminder_pdf.py:64-74` (eigene, thematisch andere Zeilen: Offener Betrag/Mahngebühr/Gesamt), `quote_layout_pdf.py` `totals`-Zweig (`_block_flowables:383-396`, vierte Variante), `time_backoffice.py:196` (Summenzeile **innerhalb** der Haupttabelle, kein eigener Block) | Identische `TableStyle` (`ALIGN RIGHT`, `LINEABOVE .8 black`, `FONTNAME bold` auf letzter Zeile) an vier Stellen copy-paste | `build_quote_totals_flowables` wurde einmal extrahiert, wird aber **nirgends außer in `quote_pdf.py` selbst** wiederverwendet – `invoice_pdf.py`/`order_pdf.py` haben ihre eigene, praktisch identische Kopie nie darauf umgestellt |
| **Unterschriftenblock** | Nur `service_report_pdf.py:283-320` | – (kein Duplikat) | Angebote/Aufträge/Rechnungen/Mahnungen werden in diesem ERP nicht digital unterschrieben – dieser Baustein ist zu Recht nur einmal vorhanden |
| **`footer_parts`-Legal-Fußtext** (Geschäftsführung/Registergericht/USt-ID/IBAN) | `quote_pdf.py:165-172` (inline) **vs.** `quote_layout_pdf.py` `footer_text`-Zweig (`_block_flowables:404-412`, fast wortgleiche Liste) | Sehr ähnlich, zwei Kopien derselben Feldliste | `order_pdf.py`/`invoice_pdf.py`/`reminder_pdf.py` zeigen diesen Block **gar nicht** – Inkonsistenz, nicht nur Duplikat |

**Kernaussage für Abschnitt 11:** Fußzeile und Summenblock sind die klarsten Kandidaten für
sofortige Konsolidierung (reine Kopien, kein fachlicher Unterschied). Firmenkopf/Adresse/Meta-Block
existieren dagegen bereits *heute* in zwei bewusst verschiedenen Stilen (fest vs. konfigurierbar)
– das deckt sich mit dem eigentlichen Umbauziel: der Designer-Stil (`line_list`,
`DocumentTableField`-gesteuert) ist im Grunde schon der Prototyp für den künftigen gemeinsamen
Rahmen, nur bisher an einen einzelnen, raw-canvas-basierten Renderer gebunden.

---

## 8. Dokumente mit unvorhersehbar langem Inhalt

| Dokument | Unvorhersehbare Quelle | Heute schon mehrseitig im Praxisbetrieb? |
|---|---|---|
| **Angebot** (`quote_layout_pdf.py`) | LV-Positionen (Titelbaum + Positionen), beliebig viele Kunden-/Projekttexte | Ja – der namensgebende Befund (16 Seiten) |
| **Auftrag** (`order_pdf.py`) | Identische Struktur wie Angebot (LV-Positionen aus dem beauftragten Angebot) | Ja, strukturell zwingend gleich lang wie das zugehörige Angebot |
| **Rechnung** (`invoice_pdf.py`) | `visible_items(invoice)` – bei Schlussrechnungen/Rechnungen nach Aufwand potenziell viele Positionen; `abschlag_pauschal` dagegen immer kurz (keine Positionsliste) | Ja, außer beim pauschalen Abschlag |
| **Einsatzbericht** (`service_report_pdf.py`) | Die unvorhersehbarste Quelle im ganzen Projekt: beliebig viele Prüfpunkte × beliebig viele Dachflächen, beliebig viele Mängel mit je eigenen Fotos, beliebig viele Dokumentationsfotos (echte Bilddateien, nicht nur Text), Materialliste, Zeitbuchungstabelle | Ja, vor allem bei mehrflächigen Wartungsberichten mit Fotos |
| **Stundenzettel** (`time_backoffice.py`) | Zeitraum × Mitarbeiteranzahl – ein Monatsbericht für ein ganzes Team kann sehr lang werden | Ja, mit erzwungenem `PageBreak()` je Mitarbeiter bereits eingeplant |
| **Mahnung** (`reminder_pdf.py`) | Nur der freie Mahntext (`ptext(data["formatted_text"])`) plus eine dreizeilige Summentabelle – in der Praxis praktisch immer eine Seite | Nein, im Normalfall einseitig; theoretisch könnte ein sehr langer Textbaustein umbrechen |

**Konsequenz:** Angebot, Auftrag, Rechnung, Einsatzbericht und Stundenzettel dürfen **nie** auf
feste Koordinaten umgestellt werden – ihr Inhaltsbereich muss zwingend fließend bleiben (bei den
vier `SimpleDocTemplate`-Renderern ist das bereits so; beim Angebot ist es aktuell **nicht** so,
siehe Abschnitt 9). Nur die Mahnung könnte man sich am ehesten "fest" vorstellen, aber selbst da
gibt es keinen zwingenden Grund, eine Ausnahme vom gemeinsamen, fließenden Modell zu machen.

---

## 9. Grenzen des rohen Canvas beim Angebot

Was ist am heutigen `quote_layout_pdf.py` **wirklich** nur deshalb möglich, weil roh gezeichnet
wird – und was ließe sich mit einem fließenden Inhaltsbereich + gezeichnetem Rahmen (das
Umbauziel) ebenso erreichen?

| Fähigkeit | Braucht wirklich rohes Canvas? | Begründung |
|---|---|---|
| Vollflächiges Hintergrundbild (Briefbogen), je Seite wiederholt | **Nein.** | `SimpleDocTemplate` reicht den `canvas` an `onFirstPage`/`onLaterPages` durch – genau dieser Mechanismus zeichnet schon heute in allen fünf anderen Renderern die Fußzeile. Ein `c.drawImage(...)` für den Hintergrund gehört exakt dorthin. |
| Firmenlogo als Bild | **Nein.** | Entweder als `platypus.Image`-Flowable im `story` (wie die Unterschrift in `service_report_pdf.py:299/308/319`) oder ebenfalls im `onPage`-Callback. |
| Fortsetzungs-Kopfzeile mit eigenem Text auf Folgeseiten | **Nein.** | `SimpleDocTemplate` erlaubt unterschiedliche `PageTemplate`s für "erste Seite" und "Folgeseiten" (`BaseDocTemplate` + `PageTemplate` + `NextPageTemplate`) – jede mit eigenem `onPage`-Callback. Das bildet `DocumentPageMargins.page_type` (`first`/`continuation`) sogar direkter ab als der heutige manuelle Cursor-Mechanismus. |
| Seite-X-von-Y-Zähler | **Nein.** | Reportlabs Standardlösung (`canvasmaker`-Canvas-Unterklasse) setzt exakt auf `SimpleDocTemplate`/`BaseDocTemplate` auf – im heutigen Canvas-Ansatz ist das dagegen der schwierigere Fall (Abschnitt 6.4). |
| Frei wählbare, sich überlappende oder unterschreitende X/Y-Positionen einzelner Bausteine (z. B. Meta-Tabelle testweise mitten in die Positionsliste legen) | **Ja**, das ist die einzige Fähigkeit, die ein `Frame`-basierter Fluss grundsätzlich nicht hergibt. | Genau diese Fähigkeit soll laut Auftrag aber ohnehin **aufgegeben** werden ("Der Designer soll also nicht einzelne Positionen frei platzieren lassen"). |
| Bauteile vor der Positionsliste an fester Stelle, unabhängig von deren Länge (heutiges Verhalten: `blocks_before` immer an ihrer festen Position, siehe `quote_layout_pdf.py:454-469`) | **Ja, in der heutigen Form** – aber nur, weil das Modell "eine Seite mit festen Feldern + eine variable Tabelle mittendrin" ist. | In einem `Frame`-Modell wandert der komplette Kopfbereich (Firmenkopf, Adresse, Meta, Titel) einfach als weitere Flowables an den Anfang der `story` – exakt das Verhalten, das die fünf anderen Renderer schon heute zeigen. Kein Funktionsverlust, nur ein anderes Modell. |
| Ein Baustein "nach" der Positionsliste, der bei Seitenumbruch lückenlos direkt weiterzeichnet (`blocks_after`, `quote_layout_pdf.py:491-505`, der `cursor_y`-Nachlauf) | **Nein**, das ist exakt das Standardverhalten eines `Frame`s – jeder Flowable fließt automatisch direkt hinter den vorherigen. Der heutige Code baut das Verhalten nur manuell nach, weil es kein `Frame` gibt. | – |

**Fazit:** Mit Ausnahme der einen, laut Auftrag ohnehin nicht mehr gewünschten Fähigkeit (freie
2D-Positionierung, auch über- oder unterschneidend) lässt sich **alles**, was
`quote_layout_pdf.py` heute bietet, mit `BaseDocTemplate`/`Frame`/`PageTemplate` plus einem
`onPage`-Callback für den Rahmen ebenso gut abbilden – und würde nebenbei die heutige,
handgestrickte Pagination samt ihrer Fehleranfälligkeit (Abschnitt 6) durch reportlabs geprüften,
eingebauten Mechanismus ersetzen.

---

## 10. Testabdeckung

| Renderer | Testdateien | Was wird geprüft |
|---|---|---|
| `build_quote_pdf` | `tests/test_v060_lv_editor.py`, `tests/test_v159_quote_layout_pdf.py` | Nur Gültigkeit (`startswith(b"%PDF-")`, Mindestlänge) – kein Inhalt, keine Seitenzahl |
| `build_quote_layout_pdf` | `tests/test_v159_quote_layout_pdf.py` (9 Tests), `tests/test_v167_pagination.py` (9 Tests), `tests/test_v164_table_field_configuration.py` (30 Tests, meist API-Ebene für `DocumentTableField`), `tests/test_v169_page_margins.py` (12 Tests, meist API-Ebene für `DocumentPageMargins`), `tests/test_v187_quote_email.py` (`test_send_quote_email_uses_layout_designer_pdf`) | Gültigkeit, Default-Layout-Seeding, ausgeblendete Bausteine, eigene Textblöcke, Hintergrund mit/ohne Wiederholung, **SeitenANZAHL** über `count_pdf_pages()` (Regex auf `/Type/Page`-Objekte) bei 1 bzw. 60 Positionen – **niemals** Seiten-TEXT-Inhalt (kein Test liest je, was auf einer Folgeseite tatsächlich steht) |
| `build_order_pdf` | `tests/test_v070_orders.py` (`test_order_pdf_is_valid`) | Nur Gültigkeit; `send_order_email`-Tests (`test_v190_order_email.py`) mocken nur `smtplib.SMTP`, rufen den echten PDF-Build also indirekt mit auf, ohne den Inhalt zu prüfen |
| `build_invoice_pdf` | **Keine direkte Testdatei.** Indirekt über `tests/test_v182_invoice_email.py` (`smtplib.SMTP` gemockt, PDF-Erzeugung läuft real mit, aber ungeprüft) | Nur "stürzt nicht ab" |
| `build_reminder_pdf` | **Keine direkte Testdatei.** Indirekt über `tests/test_v174_email_sending.py`, gleiches Muster wie Rechnung | Nur "stürzt nicht ab" |
| `build_service_report_pdf` | `tests/test_v203_service_reports.py`, `tests/test_v213_inspection_items.py`, `tests/test_v214_findings_and_photos.py`, `tests/test_v223_service_report_materials.py`, `tests/test_v224_field_view.py` (zusammen 18 Aufrufe) | Am gründlichsten getestete Datei: Gültigkeit, tatsächlicher **Text**-Inhalt über einen selbstgebauten Content-Stream-Extraktor (`_extract_pdf_text()`, seit `test_v213`), gezielte Regressionstests (z. B. "Bericht ohne Prüfpunkte/Mängel/Material rendert exakt wie vor Version X", "Ein-Unterschrift-Bestandsbericht bleibt unverändert") |
| `build_timesheet_pdf` | `tests/test_v103_time_backoffice.py` (ein Smoke-Test, Teil eines größeren Tests für PDF+CSV+DATEV zusammen) | Nur Gültigkeit |

**Auffälligster Befund für Abschnitt 11/12:** Ausgerechnet die beiden am längsten laufenden,
`SimpleDocTemplate`-basierten Renderer mit potenziell vielen Positionen (Rechnung, Mahnung) haben
**keinen einzigen direkten Test**. Und selbst der mit Abstand am besten getestete Bereich
(Angebots-Pagination, `test_v167_pagination.py`) prüft ausschließlich die **Anzahl** der Seiten,
nie deren **Inhalt** – ein Grund, warum ein Text-Bug wie der in Abschnitt 6 untersuchte (wäre er
real im Code) durch die bestehende Suite nicht auffallen würde.

---

## 11. Vorschlag für den Umbau

### 11.1 Zielbild in einem Satz

Jeder Renderer wird (oder bleibt) ein `BaseDocTemplate`/`SimpleDocTemplate` mit einer normalen,
fließenden `story` für den Inhalt; der komplette Rahmen (Hintergrund, Logo, Firmenkopf,
Meta-Block, Fußzeile, Ränder, künftig Schriften/Farben) wandert in ein `onFirstPage`/
`onLaterPages`-Callback-Paar (bzw. zwei `PageTemplate`s mit je eigenem `onPage`), das für **alle**
Dokumenttypen dieselbe, aus `DocumentLayoutBlock`/`DocumentLayoutBackground`/
`DocumentPageMargins` gespeiste Konfiguration liest. `document_pdf.py` ist bereits fast das
richtige Fundament dafür (datengetriebene Bausteine ohne Kenntnis von Quote/Order/Invoice, siehe
Docstring `document_pdf.py:15-21` – das war laut eigenem Kommentar von Anfang an für genau diesen
Zweck gedacht).

### 11.2 Technischer Bauplan für den gemeinsamen Rahmen

1. `DocumentLayoutBlock` wird für den Rahmen **nicht mehr per (x_mm, y_mm) frei positioniert**,
   sondern auf eine kleine, feste Menge an Rahmen-Slots reduziert (Kopfzeile-Bereich,
   Fußzeile-Bereich, Hintergrund) – im Widerspruch zur heutigen Nutzung als frei platzierbare
   Bausteine; siehe offene Entscheidung in Abschnitt 12.
2. Ein neues, gemeinsames Modul (z. B. `app/document_frame.py`) baut aus `general`,
   `DocumentLayoutBackground`, den Rahmen-Feldern und `DocumentPageMargins` zwei
   `onPage`-Callbacks (`on_first_page(canvas, doc)`, `on_later_pages(canvas, doc)`) – Hintergrund
   zuerst zeichnen, dann Logo, dann Firmenkopf/Meta-Block als `Paragraph`/`Table`
   (`wrapOn`/`drawOn` direkt auf dem übergebenen `canvas`, wie heute schon in
   `_draw_flowables_at()`), zuletzt die Fußzeile inkl. Seite-X-von-Y (`canvasmaker`-Technik aus
   Abschnitt 6.4, dort einmal implementiert).
3. Jeder der sieben Renderer wechselt (oder bleibt) auf `SimpleDocTemplate(..., onFirstPage=...,
   onLaterPages=...)`, sein `story` beschränkt sich auf den reinen Inhalt (Positionsliste,
   Prüfpunkte, Zeittabelle, …) – exakt das, was `order_pdf.py`/`invoice_pdf.py`/`reminder_pdf.py`/
   `service_report_pdf.py` strukturell schon heute tun, nur mit austauschbarem statt fest
   codiertem Rahmen.
4. `DocumentPageMargins` steuert `SimpleDocTemplate`s `topMargin`/`bottomMargin`/`leftMargin`/
   `rightMargin` direkt – für "Seite 1 vs. Folgeseiten" braucht es dafür zwei `PageTemplate`s
   (`BaseDocTemplate` statt `SimpleDocTemplate`, `NextPageTemplate('later')` als erstes
   Story-Element), das Modell existiert in der Datenbank bereits vollständig (Abschnitt 4).

### 11.3 Reihenfolge und risikoärmster erster Schritt

**Nicht** mit dem Angebot anfangen, obwohl es das eigentliche Ziel ist – dort ist der Umbau am
größten (raw Canvas → Frame) UND es ist das einzige Dokument mit einem produktiv genutzten,
funktionierenden Designer, den man nicht verschlechtern darf ("darf beim Umbau nicht schlechter
werden"). Reihenfolge nach Risiko, aufsteigend:

1. **`reminder_pdf.py` (Mahnung) zuerst.** Kürzestes, einfachstes Dokument (Abschnitt 8: praktisch
   immer eine Seite), **keine** Testabdeckung, die man brechen könnte (Abschnitt 10 – Risiko einer
   Testregression ist hier am kleinsten, nicht weil Tests unwichtig sind, sondern weil ein Fehler
   hier schnell auffiele und wenig Schaden anrichtet), kein Layout-Designer-Bezug, den man
   koordinieren müsste. Guter Ort, um `document_frame.py` erstmals produktiv zu erproben und die
   `canvasmaker`-Seitenzahl-Technik einmal komplett durchzuspielen.
2. **`invoice_pdf.py` (Rechnung).** Strukturell dem Auftrag/Angebot ähnlich (Positionsliste kann
   lang werden), aber GoBD-Unveränderlichkeit betrifft nur die Rechnung selbst, nicht ihr PDF –
   ein Fehler wäre ärgerlich, aber reparabel (PDF wird bei jedem Abruf neu gebaut, nichts wird
   gespeichert).
3. **`order_pdf.py` (Auftrag).** Fast identisch zu Rechnung/Angebot in der Struktur, aber ohne
   Geldbetrag-Feinheiten wie Soll/Ist.
4. **`service_report_pdf.py` (Einsatzbericht).** Am besten getestet (Abschnitt 10), aber auch am
   komplexesten (Fotos, `KeepTogether`, Mehrflächen) – bewusst spät, damit der Rahmen-Mechanismus
   an den einfacheren Dokumenten schon ausgereift ist, bevor er auf die komplizierteste
   Story-Struktur trifft.
5. **`quote_layout_pdf.py`/`quote_pdf.py` (Angebot) zuletzt.** Größter Umbau (raw Canvas → Frame),
   einziges Dokument mit echtem Designer-Publikum, direkter Bezug zum ursprünglichen
   16-Seiten-Befund. Konkretes Vorgehen zur Absicherung: den neuen, frame-basierten Renderer
   parallel zum bestehenden `build_quote_layout_pdf` unter einem neuen Funktionsnamen bauen,
   `tests/test_v159_quote_layout_pdf.py`/`test_v167_pagination.py`/`test_v169_page_margins.py`
   gegen beide laufen lassen (gleiche Erwartungen), erst nach sichtbarer Gleichwertigkeit den
   bestehenden `/pdf-layout-preview`-Endpunkt umstellen. `time_backoffice.py` (Stundenzettel)
   bewusst außen vor lassen – eigenes Layout (Querformat, keine Kundenadresse, kein
   Mahnwesen-Kontext), passt konzeptionell nicht in "Briefkopf/Kunde/Objekt"-Rahmen und hat keinen
   Layout-Designer-Bezug.

Bei jedem Schritt: bestehende Tests aus Abschnitt 10 zuerst um eine **inhaltliche** Prüfung
erweitern (Text-Extraktion wie in `service_report_pdf`-Tests bereits etabliert), bevor der jeweilige
Renderer umgebaut wird – sonst bleibt unsichtbar, ob der neue Rahmen tatsächlich dieselben Werte an
derselben Stelle zeigt.

---

## 12. Risiken und offene Entscheidungen

Punkte, an denen eine Entscheidung ansteht, bevor gebaut wird:

1. **Freie 2D-Positionierung geht verloren.** Der heutige Designer erlaubt, jeden Baustein
   pixelgenau zu verschieben (auch überlappend). Der Umbau auf einen Rahmen mit fließendem
   Inhaltsbereich gibt genau das auf. Für die zehn heutigen `quote`-Bausteine muss vorher
   festgelegt werden, welche davon künftig "Rahmen" (im `onPage`-Callback, wenige, feste Slots:
   z. B. Hintergrund, Logo, Kopfzeile-Textblock, Fußzeile-Textblock) und welche "Inhalt" (Teil der
   `story`: Kundenadresse, Meta-Tabelle, Titel/Vortext, Positionsliste, Summen, Zahlungsbedingungen)
   werden. Das ist eine fachliche, keine rein technische Entscheidung – betrifft direkt, wie stark
   sich bestehende, von echten Nutzern bereits angepasste Layouts beim Umbau optisch verschieben.
2. **Migration bestehender `DocumentLayoutBlock`-Zeilen.** Falls in der Produktivdatenbank bereits
   Bausteine verschoben/ausgeblendet wurden (unbekannt ohne Rücksprache – diese Bestandsaufnahme
   hat nur den Code geprüft, nicht den tatsächlichen Dateninhalt einer laufenden Installation):
   werden diese automatisch auf das neue Rahmen-Modell übertragen, oder verlangt der Umbau ein
   bewusstes "Layout auf Standard zurücksetzen"? Bitte klären, ob/wie viele Installationen mit
   angepasstem Angebots-Layout heute produktiv laufen.
3. **Reichweite auf `order`/`invoice`/`reminder` sofort oder schrittweise?** `DOCUMENT_TYPES`
   kennt alle vier Werte bereits, aber nur "quote" ist heute tatsächlich bespielt. Soll der
   Rahmen-Designer mit dem Umbau sofort für alle vier Dokumenttypen nutzbar werden (mehr aufeinmal,
   aber konsistent), oder zunächst nur für den gerade umgebauten Renderer freigeschaltet werden
   (kleinere Schritte, aber eine Zeit lang uneinheitliche Bedienbarkeit zwischen Dokumenttypen)?
4. **Schriften/Farben als neue Konfigurationsebene.** Existiert heute nirgends (Abschnitt 3.3) –
   das ist eine echte Neuentwicklung, kein Migrationsthema. Umfang (nur Akzentfarbe wie beim
   bestehenden Theme-System, oder freie Farbwahl je Element? System-Schriften oder Web-Font-Upload?)
   sollte vor dem Bau der Datenmodell-Erweiterung feststehen, da das die Struktur der neuen
   Rahmen-Konfiguration mitbestimmt.
5. **`time_backoffice.py` bewusst ausgeschlossen (Vorschlag), aber zu bestätigen.** Falls der
   Stundenzettel künftig doch denselben Rahmen tragen soll (z. B. Firmenlogo auch dort), ändert das
   die Reihenfolge in Abschnitt 11.3 nicht grundlegend, aber den Umfang.
6. **Seite-X-von-Y einführen – ja/nein, und wenn ja, wo zuerst?** Der ursprünglich gemeldete Befund
   stammt nach dieser Untersuchung mit hoher Wahrscheinlichkeit vom PDF-Betrachter, nicht vom Code
   (Abschnitt 6). Falls trotzdem eine echte Gesamtseitenzahl gewünscht ist, sollte das als eigener,
   bewusster Entscheid behandelt werden (nicht als "Bugfix") – am günstigsten direkt als Teil des
   gemeinsamen Fußzeilen-Bausteins im neuen Rahmen (Abschnitt 11.2, Punkt 2), statt es vorab einzeln
   in den bestehenden, bald abzulösenden Renderern nachzurüsten.
7. **`build_quote_pdf` (der ältere Angebots-Renderer) – behalten oder mit dem Umbau entfernen?**
   Er wird laut UI-Beschriftung ausdrücklich als Rückfalloption angeboten. Nach dem Umbau hätte ein
   Angebot dann potenziell DREI Renderer (alt-fließend, neu-Rahmen, plus den heutigen
   Designer-Canvas während der Übergangsphase aus Abschnitt 11.3, Schritt 5). Sollte `build_quote_pdf`
   mit abgeschaltet werden, sobald der neue Rahmen-Renderer produktiv ist, oder dauerhaft als
   Fallback bestehen bleiben?
