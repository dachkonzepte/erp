# PDF-Rahmen, Kopfbereich, Gemeinsamer Dokumenttyp

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## PDF-Rahmen (`app/document_frame.py`, seit 1.3.1)

Erste Etappe des in `docs/bestandsaufnahme_pdf.md` (09.09.2026, vollständige Bestandsaufnahme
aller sieben PDF-Renderer) skizzierten Umbaus: ein dokumenttyp-unabhängiges Modul trennt den
wiederkehrenden RAHMEN vom fließenden INHALT. **Wichtige Korrektur gegenüber der ursprünglichen
Annahme**: der Rahmen besteht in erster Linie aus hinterlegtem BRIEFPAPIER, nicht aus
gezeichneten Bausteinen – ein Unternehmen mit fertigem Briefbogen blendet Logo/Firmenkopf/
Fußzeile gerade DESHALB aus, genau wie beim Angebot heute schon. Rangfolge, in dieser
Reihenfolge:

1. **Briefpapier-Hintergrund** (`DocumentLayoutBackground`), getrennt für Seite 1/Folgeseiten
   (`page_type`, seit 1.3.1, siehe unten).
2. **Ränder je Seitentyp** (`DocumentPageMargins`, bereits seit 1.0.69 generisch über alle vier
   Dokumenttypen) – bestimmen, wo der fließende Inhalt beginnen/enden darf, damit er nicht in
   Briefkopf/Fußzeile des Briefpapiers läuft.
3. **Drei optionale, einzeln abschaltbare gezeichnete Bausteine** (Logo, Firmenkopf, Fußzeile mit
   Seitenzahl) als Rückfall für Installationen ohne eigenes Briefpapier – NIE fest verdrahtet.

**Erster Nutzer ist bewusst die Mahnung** (`app/reminder_pdf.py`) – laut Bestandsaufnahme der
risikoärmste Renderer (kürzestes Dokument, keine bestehende Testabdeckung, kein Bezug zum
bestehenden Layout-Designer). **Angebot, Auftrag, Rechnung, Einsatzbericht bleiben in dieser
Etappe vollständig unangetastet**, insbesondere `quote_layout_pdf.py` mit seinen produktiv
angepassten Layouts (verschobene Bausteine, ausgeblendetes Logo/Fußzeile) – als nächste Etappen
siehe `docs/bestandsaufnahme_pdf.md` Abschnitt 11.

- **Architektur** (`render_framed_pdf(db, *, document_type, title, content_story)`): `BaseDocTemplate`
  (nicht `SimpleDocTemplate`, wird für zwei unterschiedliche `Frame`s gebraucht) mit zwei
  `PageTemplate`s, `"first"`/`"later"`, je mit eigenem `Frame` (direkt aus den vier
  `DocumentPageMargins`-Werten des jeweiligen `page_type`, kein zusätzliches Innenpolster) und
  eigenem `onPage`-Callback (Reihenfolge: Hintergrund, dann Logo, dann Firmenkopf – erscheinen
  bewusst auf JEDER Seite, wenn aktiviert, nicht nur Seite 1 wie beim Angebot heute, ein
  sinnvollerer Rückfall für Installationen ohne Briefpapier). Der Aufrufer (`reminder_pdf.py`)
  übergibt ausschließlich den fließenden Inhalt als reine Flowable-Liste, ohne Kenntnis von
  `NextPageTemplate`/`Frame`/`canvasmaker`.
- **Seite X von Y** (neue Funktion, keine bisher existierende – siehe unten): reportlabs
  Standardtechnik (`_NumberedCanvas`, per `canvasmaker=` an `doc.build()` übergeben, NICHT an den
  `BaseDocTemplate`-Konstruktor, dort unbekannt) – `showPage()` wird abgefangen und der
  Seitenzustand zwischengespeichert, erst `save()` schreibt jede Seite mit der dann real
  bekannten Gesamtzahl fertig. **Bewusste Neuerung, keine Fehlerbehebung**: der ursprünglich
  gemeldete Seitenzahl-Befund ("bei einem 16-seitigen Angebot springt die Gesamtzahl ab Seite 10
  von 16 auf 1") kam nach eingehender Untersuchung (vollständiges Lesen aller sieben Renderer +
  Textextraktion aus einem echten generierten PDF) vom PDF-Betrachter selbst – keiner der
  bestehenden Renderer zeigte je eine Gesamtseitenzahl, nur "Seite X" ohne "von Y". Die Fußzeile
  ist der `footer_text`-Baustein; ausgeschaltet erscheint keine Seitenzahl, keine Lücke.
- **Die drei Bausteine bei der Mahnung** (`DEFAULT_REMINDER_LAYOUT` in `app/document_layout.py` --
  seit 1.3.6 umbenannt in `DEFAULT_SHARED_LAYOUT` und für JEDEN Dokumenttyp außer dem Angebot
  zuständig, siehe Abschnitt "Gemeinsamer Dokumenttyp" unten; historisch, für 1.3.1/1.3.2, war es
  ausschließlich für die Mahnung --, wiederverwendet `ensure_default_layout()`/`DocumentLayoutBlock`
  unverändert – KEINE Datenmodell-Erweiterung nötig): dieselben Standardpositionen wie die
  entsprechenden drei Zeilen in `DEFAULT_QUOTE_LAYOUT`. `x_mm`/`y_mm`/`width_mm`/`height_mm` sind
  für `footer_text` in diesem Modell NICHT die tatsächliche Zeichenposition (die Seitenzahl sitzt
  immer fest bei `20mm, 12mm`) – nur `visible` wird von `document_frame.py` gelesen. Bewusster
  Kompromiss: bestehende Tabelle/bestehende Endpunkte (`PUT /api/document-layout/blocks/{block_id}`)
  eins zu eins weiterverwenden statt einer neuen, schmaleren Tabelle nur für drei Sichtbarkeits-Flags.
  `ensure_default_layout()` seedete zunächst (1.3.1) nur "quote" (zehn Bausteine, unverändert) UND
  "reminder" (drei Bausteine) – seit 1.3.6 seedet/liest jeder Dokumenttyp außer "quote" denselben
  geteilten Satz, siehe unten.
  **`company_header`/`logo` stehen seit 1.3.2 standardmäßig auf `visible=False`** (vorher `True`
  bei `company_header`, was ein echter Fehler war – siehe nächster Punkt).
- **Überlappungsfehler von 1.3.1, behoben in 1.3.2** – im Smoke-Test überlagerte der gezeichnete
  Firmenkopf den fließenden Inhalt (Firmenname/Kundenadresse sowie Telefonnummer/
  Internetadresse standen im PDF übereinander): `DEFAULT_REMINDER_LAYOUT` setzte
  `company_header` auf `y=17mm`, der obere Standard-Rand für Seite 1 stand ebenfalls auf `17mm`
  – gezeichneter Block und `Frame` beanspruchten exakt dieselbe Fläche. Geometrische Invariante
  gegen ein erneutes Auftreten (jetzt durch `test_reminder_default_company_header_and_logo_do_not_overlap_default_frame`
  in `tests/test_v226_document_frame.py` abgesichert): `y_mm`/`top_mm` sind beide "Abstand von
  der Seitenoberkante" gemessen, ein Block überlappt den Inhaltsbereich NICHT genau dann, wenn
  `margins.top_mm >= block.y_mm + block.height_mm` gilt. Zwei Teile der Behebung, beide nötig,
  da der vom Nutzer selbst geforderte Test ("Firmenkopf aktiviert UND Standard-Rand, keine
  Überlappung") beides gleichzeitig verlangt: (1) `company_header`/`logo` standardmäßig
  `visible=False` (wer Briefpapier hinterlegt hat, braucht sie nicht; wer keins hat, schaltet
  bewusst ein), (2) neuer, dokumenttyp-spezifischer Standard-Rand-Mechanismus
  `DOCUMENT_TYPE_MARGIN_OVERRIDES` in `app/document_page_margins.py` (seit 1.3.6 umgeschlüsselt
  von `"reminder"` auf `"default"`, siehe Abschnitt "Gemeinsamer Dokumenttyp" unten -- der
  Mechanismus selbst bleibt derselbe, nur sein Schlüssel) – eine Ebene über dem
  bereits bestehenden, seitentypabhängigen `DEFAULT_MARGINS`: `{document_type: {page_type:
  {feld: wert}}}`, ausgewertet über eine neue `_default_margin_values(document_type, page_type)`,
  die `ensure_default_margins()`/`reset_margins_to_default()` jetzt statt des rohen
  `DEFAULT_MARGINS[page_type]` aufrufen. Hebt den oberen Rand der Mahnung (Seite 1 UND
  Folgeseiten) auf 42mm an, unterhalb der Unterkante von Logo/Firmenkopf – für `"quote"` (kein
  Eintrag im Dict) unverändert. In den Einstellungen steht direkt bei den drei Kontrollkästchen
  (`settings.html`) ein Hinweistext, der den Zusammenhang erklärt, falls jemand die Ränder später
  selbst anpasst. **Nebeneffekt der eigenen Smoke-Tests gegen den echten Server**: da
  `ensure_default_layout()`/`ensure_default_margins()` beim ersten Lesezugriff seeden und danach
  nie wieder an bereits bestehende Zeilen rühren, hatten eigene Testaufrufe gegen die echte
  `dachkonzepte_erp.db` bereits drei Zeilen mit den alten, fehlerhaften Werten angelegt – vor dem
  Ausliefern von 1.3.2 mit denselben Anwendungsfunktionen (kein rohes SQL) nachträglich korrigiert.
  Lehre für künftige Sitzungen: ein manueller Smoke-Test gegen den ECHTEN, produktiv laufenden
  Server kann über Seed-auf-erstem-Lesezugriff-Funktionen wie diese selbst Datenbestand
  hinterlassen, der bei einem späteren Standardwert-Fix nicht automatisch mitkorrigiert wird –
  das gehört zur Prüfung dazu, nicht nur der Code.
- **`DocumentLayoutBackground.page_type`** (seit 1.3.1, die EINZIGE Datenmodell-Erweiterung
  dieser Etappe, Muster wie `DocumentPageMargins.page_type`): vorher genau eine Zeile je
  `document_type` (`unique=True` auf `document_type` allein) – konnte keine getrennten
  Hintergründe für Seite 1/Folgeseiten halten. Migration `ec3120ba11cf`: neue Spalte
  `page_type` (`server_default='first'`, bestehende Zeilen – bisher nur das Angebot – werden
  automatisch zu `page_type='first'`), zusammengesetzter statt einzelner Unique-Index.
  **Rückwärtskompatibel**: `get_background()`/`set_background()`/`set_background_repeat()`/
  `remove_background()` (`app/document_layout.py`) bekamen alle einen neuen, optionalen
  Parameter `page_type: str = "first"` an letzter Stelle – jeder bestehende Aufrufer
  (`quote_layout_pdf.py`, der alte Bild-Upload-Endpunkt des Angebots) übergibt weiterhin keinen
  `page_type` und trifft exakt dieselbe Zeile wie vorher. `repeat_on_every_page` bleibt nur für
  diesen Altbestandsfall (ein einzelner Hintergrund) relevant; bei getrennten
  Seitentyp-Hintergründen übernimmt die bloße Existenz der `continuation`-Zeile dieselbe Rolle,
  ein zusätzliches Flag wäre dort redundant.
- **Neue, eigenständige Endpunkte** `.../backgrounds/{page_type}` (Plural, `routers/document_layout.py`)
  – bewusst ein ANDERES Pfadsegment als das bestehende, unveränderte `.../background`: die
  bestehenden Routen kennen bereits die Literale `file`/`repeat` an genau dieser Segmentposition,
  ein `/{page_type}` dort hätte eine Literal-vs-Platzhalter-Kollision riskiert (das exakte
  Muster, vor dem `tests/test_v167_pagination.py` bereits warnt). Kein page_type-bewusster
  `repeat`-Endpunkt – das Feld bleibt nur für den Altbestandsfall relevant.
- **PDF als Briefpapier-Quelle** (seit 1.3.1): reportlab kann keine PDF-Seite direkt zeichnen
  (`drawImage` nimmt nur Rasterbilder). Lösung: Rasterisierung BEIM HOCHLADEN (nicht
  Zusammenführen zweier PDFs nach dem Bauen – das bliebe als Alternative mit voller Vektortreue
  für eine spätere Etappe denkbar, ist aber der aufwendigere Weg). `pypdfium2` (neue Abhängigkeit,
  `requirements.txt`) – bewusst NICHT `PyMuPDF`/`fitz` (dessen freie Version AGPL-3.0 ist und für
  ein proprietäres ERP eine Lizenzpflicht auslösen würde) und NICHT `pdf2image` (setzt eine
  externe Poppler-Installation auf dem System voraus, ein echtes Deployment-Risiko auf einer
  einzelnen Windows-Maschine ohne vorhandene System-PDF-Tools) – reine, vorkompilierte
  Wheel-Abhängigkeit. Nur Seite 0 einer hochgeladenen PDF wird verwendet; unterschiedliches
  Briefpapier für Seite 1/Folgeseiten kommt aus zwei getrennt hochgeladenen Dateien, kein
  automatisches Aufteilen einer mehrseitigen PDF.
- **Bildformat-Entscheidung: JPEG statt PNG** (nur für den neuen, seitentypbewussten
  Upload-Endpunkt – der alte, unveränderte Bild-Upload-Endpunkt des Angebots konvertiert weiterhin
  nichts). Gemessen (Pillow, realitätsnahe Testbilder): sauberes/flächiges Briefpapier ~15 KB als
  PNG bei 200dpi; ein ganzseitiger fotografischer/körniger Extremfall dagegen ~3,7 MB als PNG,
  aber nur ~0,9 MB als JPEG q85 – Faktor ~4. Zusätzlich geprüft und beruhigend: reportlab bettet
  ein mehrfach identisch gezeichnetes Hintergrundbild nur EINMAL in die PDF ein (1/3/6 Seiten mit
  demselben Bild: 3.120/3.121/3.123 KB Gesamtgröße) – die anfängliche Sorge "bei einer
  dreiseitigen Mahnung dreimal eingebettet" trifft so nicht zu, relevant bleibt nur die Anzahl
  UNTERSCHIEDLICHER Hintergründe (maximal zwei: Seite 1 + Folgeseiten). 200dpi bleibt die
  Auflösung – JPEG statt einer DPI-Absenkung löst das Größenproblem deutlich wirksamer.
- **Seitenverhältnis**: `quote_layout_pdf.py` zeichnet den Hintergrund weiterhin mit
  `preserveAspectRatio=False` (volle Streckung, unverändert – Angebot wird nicht angefasst). Der
  neue Rahmen kombiniert zwei Maßnahmen: (1) Ablehnung beim Hochladen, wenn das Seitenverhältnis
  relativ um mehr als 2 % von A4 (210:297) abweicht (`validate_a4_aspect_ratio()`,
  `app/document_layout_background.py` – fängt z. B. US-Letter mit ~9 % Abweichung sicher ab,
  lässt normale Scan-Ungenauigkeit zu), (2) `preserveAspectRatio=True` (reportlab skaliert
  automatisch verzerrungsfrei und zentriert) statt Streckung, davor die Seite einmal weiß
  gefüllt, damit ein durch die Zentrierung entstehender minimaler Rand nie unbestimmt erscheint.
- **Oberfläche**: Einstellungen → Mahnwesen-Layout (`app/templates/settings.html`) – bewusst
  NICHT der bestehende Drag-Canvas-Editor `document_layout_editor.html` (für frei positionierbare
  Bausteine gebaut; die drei Rahmen-Bausteine der Mahnung sind nicht frei positionierbar, siehe
  oben – eine Positions-Oberfläche wäre irreführend). Zwei Briefpapier-Upload-Felder, Randabstände
  je Seitentyp (wiederverwendet die bereits bestehenden, unveränderten
  `/margins/{page_type}`-Endpunkte unverändert), drei Kontrollkästchen für Logo/Firmenkopf/
  Fußzeile (`PUT /api/document-layout/blocks/{block_id}`, bestehender Endpunkt). Seit 1.3.2 zeigt
  `document_layout_editor.html` (der Angebots-Editor) einen Verweis-Hinweis mit Link auf
  Einstellungen → Mahnwesen-Layout, damit die zwei Orte für dieselbe Art Einstellung sich nicht
  gegenseitig verwirren. Erreichbarkeit des Mahnwesen-Layout-Abschnitts wurde nach einem
  gemeldeten Smoke-Test-Befund per isolierter zweiter Serverinstanz (separater Port, separate,
  temporäre Testdatenbank) mit echter Browser-Automatisierung bestätigt funktionsfähig – kein
  Code-Fehler gefunden, vermutlich nur ein im Smoke-Test übersehener Menüpunkt.

## Kopfbereich (`build_din5008_header_block()` in `app/document_pdf.py`, seit 1.3.3)

Zweiter Baustein desselben, in `docs/bestandsaufnahme_pdf.md` Abschnitt 7 ("Bereits mehrfach
vorhandene Bausteine") skizzierten Konsolidierungsziels wie der PDF-Rahmen oben, hier aber INHALT
statt RAHMEN – Anschrift und Meta-Block gehören fachlich zum fließenden Inhalt (unterschiedliche
Datenquelle je Dokumenttyp: Angebot liest live vom Kunden-/Objektdatensatz, Auftrag/Rechnung/
Mahnung aus einem eingefrorenen Textschnappschuss), sollen aber trotzdem gleich aussehen.

- **Drei Varianten, keine davon direkt wiederverwendbar** – vor dem Bauen geprüft: (1)
  `build_customer_and_meta_block()` (`document_pdf.py`, bereits von `quote_pdf.py`/`order_pdf.py`/
  `invoice_pdf.py`/`reminder_pdf.py` identisch genutzt) zeigt die Anschrift als EINEN
  zusammengezogenen Absatz und den Meta-Block mit ZWEI Beschriftung/Wert-Paaren je Zeile. (2)
  `build_customer_address_block()`/`build_meta_table_block()` (dieselbe Datei) – toter Code, seit
  ihrer Einführung (1.0.61, "für den positionsbasierten Layout-Editor") null Aufrufer, da
  `quote_layout_pdf.py` stattdessen eigene, private Bausteine bekam; nutzen zudem noch dieselbe
  falsche Zweier-Paar-Spaltenaufteilung wie (1). (3) `quote_layout_pdf.py`s eigene, private
  `_build_line_list_block()`/`_build_field_rows_table()`/`_line_list_field_values()` – das ist
  bereits exakt die gewünschte Optik (Anschrift zeilenweise, Meta-Block eine Zeile pro Paar), aber
  fest an `DocumentTableField` (Layout-Designer-Feldkonfiguration) und live
  Customer/Property-Objekte gekoppelt, kein einfacher, datengetriebener Baustein wie die übrigen
  Funktionen in `document_pdf.py`.
- **`build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles)`** (neu, `document_pdf.py`):
  nimmt eine optionale Absenderzeile (fertig formatierter String, vom Aufrufer zusammengesetzt –
  der Baustein selbst kennt keine Firmenstammdaten), die Empfängeranschrift als Liste einzelner
  Zeilen und den Meta-Block als Liste von `(Beschriftung, Wert)`-Paaren entgegen. Anschrift: jede
  Zeile ein eigener `<br/>`-getrennter Absatzteil, keine Zusammenziehung. Meta-Block: einfache
  Zweispalten-`Table`, eine Zeile pro Paar (Muster `quote_layout_pdf.py::_build_field_rows_table()`,
  hier aber datengetrieben ohne `DocumentTableField`-Abhängigkeit). Zusätzlich eine kleine (7.5pt),
  unterstrichene Absenderzeile über der Anschrift (`<u>`-Tag, von reportlabs Paragraph-Mini-XML
  direkt unterstützt, kein gezeichnetes Element) – DIN-5008-Rücksendeangabe im Anschriftenfenster.
  **Bewusste Nutzerentscheidung, kein 1:1-Abgleich mit dem heutigen Ist-Zustand**: ein direkter
  Vergleich mit dem echten, produktiv angepassten Angebots-PDF (Rendern + visueller Vergleich vor
  Abschluss dieser Etappe) zeigte, dass die dortige Absenderzeile normal groß und ohne Unterstreichung
  ist – klein+unterstrichen ist damit ein bewusst NEUES Stilelement für den künftigen, gemeinsamen
  Auftritt, keine Anpassung an das, was heute bereits im Angebot steht. `build_customer_and_meta_block()`
  selbst bleibt dabei unangetastet (Angebot/Auftrag/Rechnung folgen erst in eigenen, späteren
  Etappen) – siehe Regel zur Vorsicht bei gemeinsam genutzten Funktionen.
- **Mahnung als erster Nutzer** (`app/reminder_pdf.py`): baut die Absenderzeile aus
  `GeneralSettings` (Firmenname, Straße, PLZ/Ort, mit " - " verbunden). Die Empfängeranschrift
  kommt weiterhin aus `invoice.customer_name`/`invoice.customer_address` (beide unverändert
  eingefroren) – `customer_address` ist ein einziger, per `orders.py::_address()` mit ", "
  verbundener Schnappschuss-String ("Straße, PLZ Ort"); `reminder_pdf.py` teilt ihn einmalig an
  dieser bekannten Fuge (`.split(", ", 1)`) in zwei Anschriftzeilen auf, OHNE die
  Schnappschuss-Erzeugung selbst in `orders.py`/`invoices.py` anzufassen – das bleibt bewusst
  Auftrag/Rechnung vorbehalten. Deshalb hat die Mahnungsanschrift heute nur 3 statt 4 Zeilen wie
  beim Angebot (kein separat eingefrorener Ansprechpartner auf `Order`/`Invoice` – keine künstlich
  erfundene vierte Zeile). Der Meta-Block hat jetzt vier eigene Zeilen (Mahnungsnr./Datum/zu
  Rechnung/vom) statt zwei Zeilen mit je zwei Paaren. Tests: `tests/test_v227_din5008_header_block.py`
  (Baustein isoliert: Unterstreichung+Schriftgröße der Absenderzeile, getrennte Anschriftzeilen,
  Meta-Tabellenform, plus die Mahnung als Nutzer inkl. Adress-Split UND, seit 1.3.4, die beiden
  Fluchtlinien-Tests unten) und die aktualisierte
  `test_v153_mahnwesen.py::test_reminder_pdf_reuses_shared_document_blocks`.
- **Fehlerbehebung seit 1.3.4, per Nachmessen im PDF gefunden** (`pypdfium2.PdfTextPage.get_charbox()`
  auf den erzeugten Bytes, nicht nach Augenmaß) – zweiter Smoke-Test bemängelte drei Dinge:
  1. **Meta-Block zu weit links / Wertespalte nicht rechtsbündig**: die Spaltenbreiten waren
     bereits korrekt (Zellgrenze lag schon bei 194mm), es fehlte aber eine `ALIGN`-Regel für die
     Wertespalte – Text blieb linksbündig in einer zu breiten Zelle (gemessen: Rechnungsnummer
     endete bei 142mm statt 194mm). Neue Konstanten `DIN5008_ADDRESS_COL_WIDTH`/
     `DIN5008_GAP_COL_WIDTH`/`DIN5008_META_COL_WIDTH` (70/36/70mm) bilden dabei die tatsächlich
     gemessene, produktiv angepasste Angebotsseite nach (Blockpositionen `company_header`/
     `meta_table` in der echten `document_layout_blocks`-Tabelle abgefragt), statt eine eigene
     Aufteilung zu erfinden – vorher direkt `CUSTOMER_COL_WIDTH`/`META_COL_WIDTH` (68/108mm,
     ohne Lücke) wiederverwendet, die für `build_customer_and_meta_block()`s andere Optik gedacht
     sind.
  2. **Uneinheitliche linke/rechte Fluchtlinien**: ein reportlab-`Table` hat per Default 6pt
     (~2,1mm) Zellenpolster auf jeder Seite, ein `Paragraph` keins – Absenderzeile/Anschrift
     (stecken in einer Tabelle, um neben dem Meta-Block zu stehen) begannen dadurch systematisch
     ~2mm zu weit rechts. Behoben durch `_ZERO_HORIZONTAL_TABLE_PADDING`
     (`LEFTPADDING`/`RIGHTPADDING` auf 0, TOP-/BOTTOMPADDING bewusst NICHT angefasst – reine
     Zeilenhöhe, kein horizontales Ausrichtungsproblem) auf der äußeren Tabelle UND der
     Meta-Tabelle in `build_din5008_header_block()`.
  3. **Forderungstabelle (`reminder_pdf.py`) "eingerückt"**: stand auf `hAlign="RIGHT"` bei nur
     160mm Breite statt der vollen 176mm Rahmenbreite – die restlichen 16mm Lücke schoben die
     GANZE Tabelle (inkl. linksbündiger Beschriftungsspalte) nach rechts, statt nur die
     Wertespalte rechtsbündig zu zeigen (das leistete die bereits vorhandene `ALIGN`-Regel für die
     zweite Spalte ohnehin schon). Behoben durch Verbreiterung auf `PAGE_CONTENT_WIDTH` (176mm,
     `hAlign` dadurch gegenstandslos, entfernt) plus dieselbe Zellenpolster-Nullung.

  Gemessen vorher → nachher (Abstand zum linken Rand bei 18mm bzw. zum rechten bei 194mm):
  Absenderzeile 20,32mm → 18,20mm; Forderungstabelle 36,27mm → 18,15mm (Überschrift/Fließtext/
  „Ausführungsort" lagen schon vorher bei 18,00-18,45mm); Meta-Wertespalte 142,18mm → 193,45mm;
  Forderungstabelle-Wertespalte 191,87mm → 193,98mm. Zwei neue Tests
  (`test_left_edge_of_sender_line_heading_body_and_amount_table_line_up`/
  `test_right_edge_of_meta_value_and_amount_table_line_up_with_right_margin`) lesen dafür direkt
  die Zeichenpositionen aus dem erzeugten PDF statt nur die Flowable-Struktur zu prüfen – geprüft
  und für machbar befunden, `pypdfium2` ist ohnehin bereits Projektabhängigkeit (seit 1.3.1).
- **Angebot/Auftrag/Rechnung bleiben in dieser Etappe unangetastet** – folgen laut
  `docs/bestandsaufnahme_pdf.md` Abschnitt 11 in eigenen, späteren Etappen, dann vermutlich unter
  Auflösung von Variante (3) in denselben gemeinsamen Baustein. Das echte Angebot erreicht die
  hier neu erzwungene Wertespalten-Rechtsbündigkeit heute selbst NICHT (gemessen:
  `Angebotsnr.`-Wert endet bei 179,72mm, `Angebotssumme brutto`-Wert bei nur 55,81mm) – dort
  zeichnet `quote_layout_pdf.py::_draw_flowables_at()` Flowables über rohes Canvas-Zeichnen ohne
  jede `hAlign`-Auswertung, ein `hAlign="RIGHT"` in `_build_field_rows_table()` ist dadurch
  faktisch wirkungslos. Bewusst nicht Teil dieser Etappe (Angebot unangetastet), aber vorgemerkt
  für die eigene, spätere Angebots-Etappe.
- **Seitenangabe im Meta-Block, seit 1.3.5** (`render_framed_pdf()`, `app/document_frame.py`):
  die Gesamtseitenzahl entsteht erst in `_NumberedCanvas.save()` (siehe Abschnitt "PDF-Rahmen"
  oben), der Meta-Block aber beim Aufbau der Story, lange davor. `quote_layout_pdf.py` löst dieses
  Problem NICHT (geprüft) – es zeigt nirgends eine Gesamtseitenzahl, nur die laufende Seite
  (`_draw_continuation_header()`: "Fortsetzung, Seite {N}"; Seite 1: hartkodiertes Literal
  `"Seite 1"`, keine Variable). Es gab also nichts zu übernehmen. Entscheidung gegen einen
  nachträglich überschriebenen Platzhalter (zum Zeitpunkt der Überschreibung sind die
  PDF-Textoperatoren bereits exakt positioniert geschrieben – ein Platzhalter mit anderer
  Zeichenlänge als die echte Zahl würde die in 1.3.4 behobene Rechtsbündigkeit der Wertespalte
  wieder verschieben) – stattdessen ein zweiter, kompletter Renderdurchlauf: `content_story` ist
  jetzt entweder (wie bisher) eine fertige Liste, oder eine Funktion `(total_pages: int | None) ->
  list`. Wird eine Funktion übergeben, ruft `render_framed_pdf()` sie zuerst mit `None` auf (reiner
  Entdeckungsdurchlauf, Bytes verworfen), liest danach `doc.page` (die jetzt bekannte
  Gesamtseitenzahl) und ruft sie erneut mit dieser Zahl auf – die Bytes dieses zweiten Durchlaufs
  werden zurückgegeben. Bewusst KEIN "billigerer" Zähl-Durchlauf mit stillgelegtem Zeichnen: die
  eigentlich teure Arbeit bei reportlab ist die Platypus-Layoutberechnung (welche `wrap()`-Aufrufe
  über Seitenumbrüche entscheiden), die fällt unabhängig davon an, ob tatsächlich gezeichnet wird –
  ein Zwischenweg hätte kaum Zeit gespart, wurde deshalb nicht gebaut. Bewusst verallgemeinert
  (nicht Mahnung-spezifisch in `document_frame.py` verdrahtet), damit ein künftiger Dokumenttyp
  dieselbe Funktions-Variante nutzen kann, ohne `render_framed_pdf()` erneut anzufassen.
  `app/reminder_pdf.py::build_reminder_pdf()` baut seine Story seither in einer lokalen
  `build_story(total_pages)`-Funktion; die neue Meta-Zeile "Seite" zeigt `"1 / {total_pages}"`
  (die Mahnung sitzt immer auf Seite 1, nur "1 /" ist fest) bzw. einen Platzhalter `"1 / …"` beim
  verworfenen ersten Durchlauf. Getestet inkl. eines echten mehrseitigen Mahnungstexts
  (`test_reminder_pdf_meta_block_shows_correct_page_count_on_multipage_document`,
  `tests/test_v226_document_frame.py`) – die ermittelte Zahl entspricht der tatsächlichen
  Seitenzahl, nicht nur dem Einseiten-Sonderfall.
  - **Fußzeile bleibt unabhängig**: geprüft, ob Fußzeile (abschaltbarer Rahmen-Baustein) und die
    neue Meta-Zeile (fester Inhaltsbestandteil wie Datum/Belegnummer, NICHT extra abschaltbar)
    gleichzeitig aktiv sein können – ja, beide sind unabhängig verdrahtet; gleichzeitig aktiv ist
    redundant (zeigt die Seitenzahl zweimal), aber nicht falsch. Keine Kopplung eingebaut.
  - **Zeilenabstände im Meta-Block, geprüft und bewusst NICHT geändert**: ein gemeldetes "zu
    große Zeilenabstände" ließ sich nicht bestätigen – direkt am `Table`-Objekt gemessen
    (`_rowHeights`) UND isoliert mit verschiedenen Schriftgrößen (8,5/9/20/60pt) getestet: die
    Zeilenhöhe ist bei Angebot UND Mahnung identisch 18pt/6,35mm, unabhängig von der Schriftgröße
    (reportlabs Standardwert für eine einfache Tabellenzeile ohne explizit gesetzte
    `rowHeights`). Auf Nutzerwunsch zurückgestellt, bis klarer ist, welcher visuelle Effekt genau
    gemeint war (vermutet: der durch die kürzere, nur dreizeilige Mahnungs-Anschrift erzwungene
    Leerraum unter der Anschrift, da die äußere Tabelle beide Spalten auf die Höhe der längeren --
    hier: der Meta-Spalte -- aufzieht; nicht bestätigt).

## Gemeinsamer Dokumenttyp (Zusammenführung der Layout-Einstellungen, seit 1.3.6)

Betreiber-Entscheidung: Briefpapier, Ränder und die drei gezeichneten Bausteine gelten für JEDEN
Dokumenttyp außer dem Angebot gemeinsam, statt je Typ eigene Zeilen zu pflegen -- die
Unterscheidung Seite 1 gegen Folgeseiten bleibt bestehen (auf Folgeseiten darf der Inhalt weiter
oben beginnen, da dort kein Anschriftenfeld mehr im Weg steht). Betrifft `DocumentLayoutBackground`/
`DocumentPageMargins`/`DocumentLayoutBlock` -- `DocumentTableField` (meta_table/totals/items_table,
ausschließlich vom Angebots-Editor genutzt) ist davon unberührt, kein Teil dieser Etappe.

- **Kein neues Feld, ein reservierter Wert** (`app/document_type_fallback.py`, neues Modul):
  `SHARED_DOCUMENT_TYPE = "default"` -- `document_type` bleibt eine unbeschränkte
  `String(20)`-Spalte auf allen drei Tabellen, kein `ALTER TABLE`. Von zwei erwogenen Wegen
  gewählt: (a) ein reservierter Fallback-Wert, den ein Dokumenttyp nur dann NICHT nutzt, wenn er
  bereits eine eigene Zeile hat, statt (b) die Spalte weiter zu führen, aber nur noch mit einem
  einzigen Wert zu bespielen. Begründung für (a): `DOCUMENT_TYPE_MARGIN_OVERRIDES` (seit 1.3.2)
  ist bereits ein Dict genau für diesen Zweck (ein späterer, echter Sonderfall je Dokumenttyp) --
  Weg (b) hätte diese Erweiterbarkeit wieder verworfen und bei Bedarf ein zweites Mal einführen
  müssen.
- **Regel, EINMAL implementiert**: `resolve_shared_document_type(db, model, document_type,
  *extra_filters) -> str` -- `"quote"` bleibt immer bei sich selbst (nimmt nie am Rückfall teil).
  Jeder andere Dokumenttyp bleibt bei sich selbst, WENN dafür (unter denselben `extra_filters`,
  z. B. `page_type`) bereits eine eigene Zeile existiert, sonst liefert die Funktion
  `SHARED_DOCUMENT_TYPE`. Von `app/document_layout.py` (Bausteine, Briefpapier) UND
  `app/document_page_margins.py` (Ränder) importiert, nicht dreimal parallel nachgebaut --
  `build_customer_and_meta_block()` mit seinen inzwischen drei auseinandergelaufenen Varianten
  (siehe Abschnitt "Kopfbereich" oben) war die konkrete Warnung dafür, die zu dieser
  Zentralisierung geführt hat. `app/document_frame.py` (der dritte Ort, an dem die Regel
  gebraucht wird) baut KEINE eigene Kopie -- es bleibt reiner, transitiver Nutzer von
  `ensure_default_layout()`/`get_margins()`/`get_effective_background()`, die die Regel bereits
  intern anwenden.
- **Lesen mit Rückfall vs. Schreiben literal -- bewusst getrennt**: `ensure_default_layout()`/
  `get_margins()`/`ensure_default_margins()`/`get_effective_background()` (neu, siehe unten)
  wenden den Rückfall an -- für darstellende/lesende Zwecke (Rendern, "was wirkt gerade für
  diesen Dokumenttyp"). `update_layout_block()`/`create_custom_text_block()`/`set_background()`/
  `set_background_repeat()`/`remove_background()`/`update_margins()`/`reset_margins_to_default()`
  wenden ihn NICHT an -- sie finden/ändern immer exakt die Zeile ihres eigenen, literal
  übergebenen `document_type`. Grund: ein Schreibzugriff mit einem echten Dokumenttyp ohne eigene
  Zeile (z. B. `update_margins(db, "invoice", ...)`) darf nicht lautlos die GETEILTE Zeile treffen
  und verändern -- er muss eine eigene, neue Zeile für "invoice" anlegen (der Escape-Hatch aus
  Option (a) tatsächlich auslösen), sonst würde ein Admin, der versehentlich mit einem echten Typ
  schreibt, die Einstellungen für ALLE anderen (noch geteilten) Dokumenttypen mitverändern, ohne
  es zu merken. `app/document_layout.py::get_background()` ist deshalb weiterhin literal (wird
  intern von den Schreibfunktionen genutzt, um die richtige Zeile zum Ändern/Löschen zu finden);
  `get_effective_background()` ist die neue, Rückfall-bewusste Variante für Rendern/Anzeige.
- **Schutzprüfung an den schreibenden Endpunkten** (`app/routers/document_layout.py`):
  `_validate_writable_document_type()` akzeptiert nur `"quote"` und `"default"`, alles andere
  (insbesondere ein echter Dokumenttyp wie `"reminder"`/`"order"`/`"invoice"`) wird mit 422
  abgelehnt -- angewendet auf Briefpapier hochladen/Wiederholung ändern/löschen (beide
  Endpunkt-Generationen), Ränder ändern/zurücksetzen, Bausteine anlegen/zurücksetzen. Lesende
  Endpunkte nutzen weiterhin `_validate_readable_document_type()` (der volle `DOCUMENT_TYPES`-Satz
  PLUS `"default"`), damit z. B. `GET .../reminder/margins/first` weiterhin zeigt, was für die
  Mahnung tatsächlich wirkt. `create_custom_text_block()`/`ensure_default_layout()` validieren
  zusätzlich auf Code-Ebene gegen `DOCUMENT_TYPES ODER SHARED_DOCUMENT_TYPE` (nicht nur
  `DOCUMENT_TYPES`), damit ein direkter Aufruf mit `"default"` nicht an einer zu strengen,
  eigentlich für etwas anderes gedachten Prüfung scheitert.
- **Migration `8567f75a5266`** (reine Daten-Migration, kein Schema-Wechsel): `UPDATE ... SET
  document_type='default' WHERE document_type='reminder'` auf allen drei Tabellen --
  überführt die bereits erprobten, 1.3.1/1.3.2 angepassten Mahnung-Zeilen (oberer Rand 42mm,
  Logo/Firmenkopf ausgeblendet, die beiden tatsächlich hochgeladenen Briefpapier-Dateien für
  Seite 1/Folgeseiten) unverändert -- nichts davon wird neu erfunden. Vor dem Schreiben der
  Migration am echten Datenbestand geprüft (siehe unten "Migrations-Workflow"): nur "quote" und
  "reminder" hatten überhaupt Zeilen in diesen drei Tabellen, "order"/"invoice" keine -- die
  Migration deckt deshalb nur den einen Fall reminder→default ab. `downgrade()` kehrt die
  Zuordnung um. Getestet, indem die Migrationsdatei über `importlib` geladen und `upgrade()`/
  `downgrade()` gegen eine mit `alembic.operations.Operations`/`MigrationContext.configure()`
  gebundene Verbindung direkt aufgerufen werden (`tests/test_v229_shared_document_layout.py`) --
  neues Testmuster für eine Migration, die tatsächlich `op.execute()` braucht statt einer
  ausgelagerten, migrationsunabhängigen Hilfsfunktion wie bei früheren Migrations-Tests
  (`test_v217_component_types_layer_flags_and_customer_fax.py`).
- **`DEFAULT_REMINDER_LAYOUT` → `DEFAULT_SHARED_LAYOUT`**, `DOCUMENT_TYPE_MARGIN_OVERRIDES`
  umgeschlüsselt von `"reminder"` auf `"default"` (app/document_layout.py bzw.
  app/document_page_margins.py) -- reine Umbenennungen/Umschlüsselungen, keine Verhaltensänderung
  für bereits migrierte Installationen; für eine komplett frische Installation ohne jede
  bestehende Zeile bestimmen sie weiterhin, was beim ersten Zugriff unter `"default"` geseedet
  wird (drei Bausteine, 42mm oberer Rand).
- **`RENDERERS_USING_SHARED_FRAME`** (`app/document_frame.py`, `dict[str, str]`, aktuell nur
  `{"reminder": "Mahnung"}`): `render_framed_pdf()` lehnt einen dort nicht eingetragenen
  `document_type` mit `ValueError` ab, statt ihn kommentarlos zu rendern -- wer einen weiteren
  Renderer (Auftrag, Rechnung, irgendwann das Angebot) auf den gemeinsamen Rahmen umstellt, MUSS
  diese Zuordnung also zwangsläufig ergänzen, sonst schlägt bereits der erste Testaufruf fehl.
  Bewusst DORT platziert, wo `render_framed_pdf()` selbst steht -- eine separate Liste (z. B. nur
  im Template) hätte vergessen werden können, ein fehlschlagender Aufruf nicht.
- **Vorschau in den Einstellungen**: `GET /api/document-layout/rollout-status`
  (`app/routers/document_layout.py`, VOR der `{document_type}`-Route registriert, sonst
  Literal-vs-Platzhalter-Kollision, siehe `tests/test_v167_pagination.py`-Kommentar zu genau
  diesem Muster) liest `RENDERERS_USING_SHARED_FRAME` direkt aus `document_frame.py` und liefert
  drei Gruppen: `using_shared_settings` (aktuell: Mahnung), `not_yet_migrated` (Auftrag, Rechnung
  -- folgen in eigenen Etappen), `excluded` (Angebot -- eigener PDF-Layout-Editor). Kann nie
  veralten, weil sie aus derselben Stelle liest, die ein neuer Renderer ohnehin anfassen muss.
- **Einstellungen-Seite**: aus "Mahnwesen-Layout" (`app/templates/settings.html`, Abschnitt-ID
  `settings-reminder-layout`) wird "Dokumente & Layout" (`settings-document-layout`) -- inhaltlich
  unverändert (Briefpapier je Seitentyp, Ränder je Seitentyp inkl. Hinweistext, warum der obere
  Rand auf Folgeseiten kleiner sein darf, drei Sichtbarkeitsschalter), jedes Feld/jeder Button
  zeigt jetzt auf `document_type="default"` statt `"reminder"`. Der bisherige Eintrag
  "PDF-Layout-Editor" (`document_layout_editor.html`) bleibt bestehen, solange das Angebot ihn
  noch braucht -- sein Hinweistext wurde um einen deutlichen Satz ergänzt, dass er nach dessen
  Umbau entfällt und wo die gemeinsamen Einstellungen inzwischen liegen.
- **Angebot vollständig unangetastet**: `quote_layout_pdf.py` und seine Zeilen (`document_type=
  "quote"`) nehmen am Rückfall nie teil, `DEFAULT_QUOTE_LAYOUT` unverändert, seine eigenen
  Randwerte (17mm oberer Rand) unverändert. Geprüft per echtem Vergleich vor/nach dieser Etappe
  (bestehende Angebots-Tests bleiben grün, kein einziger davon musste angepasst werden).
- **Mahnung sieht nachweislich genau aus wie vorher**: bestehender Inhaltstest
  (`test_reminder_pdf_reuses_shared_document_blocks` u. a.) bleibt grün, zusätzlich ein direkter
  visueller Vergleich (gerenderte PDF-Seite vor/nach dieser Etappe, identische Werte aus der
  echten, migrierten Produktionsdatenbank nachgemessen: Logo/Firmenkopf aus, Fußzeile an,
  42mm/20mm/18mm/16mm Rand, beide echten Briefpapier-Dateien über `get_effective_background()`
  weiterhin auffindbar).

### Zweite Etappe (seit 1.3.7): die Rechnung, plus Wiederholungszeile auf Folgeseiten

Angebot, Auftrag und Einsatzbericht bleiben vollständig unangetastet -- `quote_layout_pdf.py`
wird nicht berührt.

- **`app/invoice_pdf.py` auf `render_framed_pdf()` umgestellt**, `document_type="invoice"` neu in
  `RENDERERS_USING_SHARED_FRAME` eingetragen (`app/document_frame.py`). Vorbild war
  `reminder_pdf.py`: erst ein Inhaltstest gegen die noch unveränderte Fassung geschrieben
  (`tests/test_v230_invoice_pdf_shared_frame.py::test_invoice_pdf_contains_expected_content` --
  Rechnungsnummer/Kundenname/Positionen/Netto/Steuer/Brutto/Zahlungsbedingungen als Teilstrings),
  dann umgebaut, derselbe Test blieb danach unverändert grün. Firmenkopf/Fußzeile stehen nicht
  mehr fest im Renderer -- sie kommen wie bei der Mahnung entweder aus dem Briefbogen oder den
  abschaltbaren Rahmen-Bausteinen.
- **Kopfbereich wie bei der Mahnung** (`build_din5008_header_block()`, nicht mehr
  `build_customer_and_meta_block()`). Meta-Zeilen tatsächlich gegen den Bestand geprüft, nichts
  erfunden: Rechnungsnr./Datum/Kunden-Nr. kommen direkt aus `invoice_to_dict()`, Vorgangs-Nr.
  über `invoice.order.project.project_number` (nicht im Dict, aber eine echte, nicht-nullbare
  Beziehung -- genau wie `reminder_pdf.py` `reminder.invoice` direkt statt nur über das Dict
  anspricht), Seite über den unveränderten 1.3.4/1.3.5-Zweidurchlauf-Mechanismus.
  **"Sachbearbeiter" bewusst NICHT dabei** -- `Invoice.caseworker_employee_id` existiert als
  Spalte, wird aber nirgends im Code je gesetzt (siehe „Bekannte, bewusst offene Punkte"), eine
  leere Zeile wäre schlechter als keine. **"Fällig bis" entfernt** -- war vorher im Meta-Block,
  ist aber eine sichtbare Erscheinungsbild-Änderung, nicht nur eine Technik-Umstellung (im
  CHANGELOG entsprechend ausdrücklich benannt): das Fälligkeitsdatum bleibt trotzdem genauso
  prominent wie vorher, nur an anderer Stelle -- `payment_terms_sentence` ("Zahlbar rein netto bis
  zum ...") steht bereits mit eigenem, fett hervorgehobenem Label "Zahlungsbedingungen:" weiter
  unten auf dem Dokument, kein Verlust an Auffindbarkeit.
- **Summenblock, nur geprüft, noch nicht zusammengeführt** (wie verlangt): Rechnung und Mahnung
  nutzen jetzt strukturell dieselbe Formatierung (volle Rahmenbreite, genullte Zellenpolster,
  rechtsbündige Wertespalte, letzte Zeile fett mit Linie darüber -- Rechnung bekam dafür dieselbe
  1.3.4-Korrektur wie damals die Mahnung, in einer eigenen `_totals_table()`-Hilfsfunktion in
  `invoice_pdf.py`), unterscheidet sich nur noch in den Zeilenbeschriftungen. Laut Bestandsaufnahme
  ist dieser Baustein vierfach dupliziert (Angebot/Auftrag/Rechnung/Mahnung) -- Zusammenführung
  lohnt laut Klärung erst, wenn ein dritter Renderer umgestellt ist (aktuell zwei: Mahnung,
  Rechnung).
- **Wiederholungszeile auf Folgeseiten, als Teil des RAHMENS, nicht des Renderers** (damit
  künftige Renderer sie einfach mitbekommen): neuer, vierter gezeichneter Baustein
  `continuation_header` (`FRAME_BLOCK_TYPES`/`DEFAULT_SHARED_LAYOUT` in `app/document_layout.py`,
  abschaltbar wie die anderen drei). `render_framed_pdf()` bekommt einen neuen, optionalen
  Parameter `continuation_header_rows: list[tuple[str, str]] | None` -- **immer eine fertige
  Liste**, nie eine Funktion wie `content_story`: die übergebenen Werte hängen nie von der
  Gesamtseitenzahl ab (nur die angehängte "Seite X von Y" tut das, siehe unten), kein zweiter
  Zweidurchlauf-Mechanismus nötig.
  - **Seitenzahl über denselben 1.3.4-Mechanismus, nicht neu erfunden**: `_NumberedCanvas` (bereits
    zuständig für die Fußzeilen-Seitenzahl) zeichnet seit 1.3.7 zusätzlich die Wiederholungszeile
    komplett in `save()` -- zusammen mit der Fußzeile die EINZIGE Stelle, die die
    Gesamtseitenzahl kennt. Der `onPage`-Callback (`_make_on_page()`) hinterlässt dafür pro Seite
    ein Attribut `c._erp_page_type` ("first"/"continuation") auf dem Canvas, BEVOR `showPage()`
    diese Seite als Snapshot sichert -- `save()` liest das beim Nachzeichnen jeder Seite aus und
    zeichnet die Zeile nur auf "continuation"-Seiten.
  - **Ursprüngliger Beschreibungsfehler richtiggestellt**: der Nutzer beschrieb das Ziel zunächst
    als "wie beim Angebot heute" (Belegnummer/Kunden-Nr./Datum/Seite als einzelne Felder) --
    tatsächlich zeigt `quote_layout_pdf.py::_draw_continuation_header()` nur einen einzigen,
    festen String (`"{Angebotsnr.} – Fortsetzung, Seite {N}"`, ohne Gesamtzahl). Die Feldliste war
    das gewünschte ZIEL für den neuen, gemeinsamen Mechanismus, keine 1:1-Kopie des heutigen
    Angebots-Verhaltens (das bleibt ohnehin unangetastet).
  - **Position, geprüft statt nur behauptet**: fest bei `CONTINUATION_HEADER_Y_MM = 8.0`mm von
    oben (analog zur fixen Fußzeilen-Position bei 20mm/12mm von links/unten) -- bewusst OBERHALB
    von Logo/Firmenkopf (die bei `y_mm=17` beginnen), damit sich beide Bausteine nie überlappen
    können, unabhängig von der konfigurierten Randgröße. Test
    `test_continuation_header_does_not_overlap_company_header_or_content`
    (`tests/test_v230_invoice_pdf_shared_frame.py`) sichert das geometrisch ab, analog zur
    1.3.2-Regression bei der Mahnung.
  - **Migration `257fb2967c93`**: `ensure_default_layout()`/`DEFAULT_SHARED_LAYOUT` seeden den
    neuen vierten Baustein nur für eine komplett frische Installation automatisch (kein
    Nach-Seeding für "nur ein block_type fehlt" bei einem bereits bestehenden `document_type`) --
    diese Migration ergänzt ihn deshalb explizit für jede Installation, die den geteilten Satz
    ("default") bereits einmal geseedet hat (bei uns: ja, aus der 1.3.6-Migration), ohne die drei
    bestehenden Zeilen anzufassen. "quote" bleibt unberührt.
- **Bei der Verifikation gegen die echte, migrierte Datenbank zwei Funde**: die tote
  `Invoice.caseworker_employee_id`-Spalte (siehe „Bekannte, bewusst offene Punkte", nicht in
  dieser Etappe behoben), und eine ECHTE, bereits seit 1.3.1 latent vorhandene Überlagerung
  zwischen der Fußzeile ("Seite X von Y", fest bei 20mm/12mm) und dem echten, von Tobias
  hochgeladenen Mahnung/Rechnung-Briefpapier, das an genau dieser Stelle schon eine eigene,
  aufgedruckte Adresszeile zeigt -- beide Texte überlappen sichtbar. Erst jetzt gefunden, weil die
  Verifikation zum ersten Mal das tatsächliche Briefpapier UND eine sichtbare Fußzeile gemeinsam
  gegen echte Daten gerendert hat. **In 1.3.8 behoben** -- siehe eigener Unterabschnitt unten.
- **Akzeptanzkriterien geprüft**: Rechnung trägt denselben Briefbogen/dieselben Ränder wie die
  Mahnung ohne eigene Einstellung (`get_effective_background()`/`get_margins()` liefern für beide
  identische Werte); Kopfbereich sieht aus wie bei der Mahnung, mit den Meta-Zeilen der Rechnung;
  eine mehrseitige Rechnung zeigt auf Folgeseiten die Wiederholungszeile, Inhalt beginnt sichtbar
  darunter (per Rendern + pypdfium2-Textextraktion je Seite bestätigt, nicht nur angenommen);
  Inhaltstest vor/nach identisch grün; Angebot/Auftrag/Einsatzbericht unverändert, ihre Tests
  bleiben grün; `pytest` vollständig grün (900/900).

### Fehlerbehebung (seit 1.3.8): Fußzeile überlagerte echtes Briefpapier

- **Fund**: bei der 1.3.7-Verifikation gegen die echte, migrierte Datenbank (nicht gegen eine
  Testdatenbank) überlagerte die gezeichnete Fußzeile ("Seite X von Y", fest bei `20mm, 12mm` von
  links/unten, siehe `_NumberedCanvas` oben) sichtbar den eigenen, aufgedruckten Fußbereich des
  echten, von Tobias hochgeladenen Briefpapiers -- dessen Adresszeile ("52531 Übach-Palenberg")
  stand exakt an derselben Stelle. Bestätigt durch Rendern einer echten Rechnung (Nr. 5) und
  Zuschneiden/Vergrößern des erzeugten PNGs. **Anderer Fehlertyp als 1.3.2**: dort kollidierte ein
  gezeichneter Baustein (`company_header`) mit dem FLIESSENDEN INHALT (beide beanspruchten
  denselben oberen Randbereich) -- hier kollidiert ein gezeichneter Baustein mit dem BRIEFBOGEN
  SELBST, an einer vom Randabstand unabhängigen, fest verdrahteten Position (die Fußzeile sitzt
  absichtlich immer bei `20mm, 12mm`, unabhängig von `DocumentPageMargins`, siehe
  "Zweite Etappe" oben) -- ein größerer Rand hätte dieses Problem also nicht gelöst, im Unterschied
  zu 1.3.2.
- **Kleinstmögliche Lösung, wie vom Nutzer vorgegeben**: kein neuer Positionierungs-Mechanismus,
  keine Kollisionsprüfung -- `footer_text` steht in `DEFAULT_SHARED_LAYOUT`
  (`app/document_layout.py`) jetzt standardmäßig auf `visible=False` (vorher, seit 1.3.1, `True`).
  Begründung, die auch im erweiterten Code-Kommentar über `DEFAULT_SHARED_LAYOUT` steht: ein
  eigener Briefbogen trägt unten üblicherweise bereits Anschrift, Kontakt, Registergericht und
  Bankverbindung; die Seitenangabe wird an dieser Stelle ohnehin nicht mehr gebraucht, da sie seit
  1.3.4 bereits im Meta-Block auf Seite 1 und seit 1.3.7 in der Wiederholungszeile auf Folgeseiten
  steht. Der Baustein bleibt vollständig erhalten und einzeln abschaltbar -- für eine Installation
  ganz ohne eigenes Briefpapier, die trotzdem unten auf jeder Seite eine Seitenzahl haben möchte,
  bleibt er per Kontrollkästchen einschaltbar. `continuation_header` bleibt unverändert bei
  `visible=True` -- die Wiederholungszeile hat keine feste, vom Rand unabhängige Position (sie
  zeichnet innerhalb des konfigurierten Randbereichs, siehe `CONTINUATION_HEADER_Y_MM` oben) und
  war von diesem Fund nicht betroffen.
- **Korrektur der bereits gesäten Zeile in der echten Datenbank**: derselbe Mechanismus wie bei der
  1.3.2-Nachkorrektur -- ein geänderter Standardwert im Code wirkt nicht rückwirkend auf bereits
  existierende Zeilen, `ensure_default_layout()` rührt eine schon gesäte Zeile nie wieder an. Die
  echte `document_layout_blocks`-Zeile (`document_type='default'`, `block_type='footer_text'`,
  id 13) trug weiterhin `visible=1`. Korrigiert über die Anwendungsfunktion `update_layout_block()`
  (kein rohes SQL, wie ausdrücklich verlangt) via eines kleinen Scratch-Skripts gegen die echte
  `dachkonzepte_erp.db`: `vorher: footer_text.visible = True` → `korrigiert: footer_text.visible =
  False`, per Vorher/Nachher-Ausgabe bestätigt.
- **Testfolgen**: vier bestehende Tests setzten implizit den alten `True`-Standard voraus und
  mussten angepasst werden -- `test_ensure_default_layout_seeds_three_reminder_blocks`
  (Erwartung umgedreht, Kommentar ergänzt), `test_reminder_pdf_footer_and_meta_block_page_count_can_both_be_active`
  (schaltet die Fußzeile jetzt explizit über `update_layout_block()` ein, bevor sie geprüft wird),
  `test_render_framed_pdf_shows_correct_total_page_count`/`test_render_framed_pdf_single_page_shows_one_of_one`
  (neuer, gemeinsamer Helfer `_enable_footer()` in `tests/test_v226_document_frame.py`),
  `test_continuation_header_can_be_disabled` (`tests/test_v230_invoice_pdf_shared_frame.py`, die
  alte "Seite N von M"-Prüfung hing an der jetzt standardmäßig unsichtbaren Fußzeile, ersetzt durch
  `assert "Seite" not in page_text`). Zwei neue Tests ergänzt:
  `test_footer_text_defaults_to_invisible_for_every_document_type_using_the_shared_frame` (prüft
  den Standard für "reminder"/"invoice"/"order" gemeinsam) und
  `test_invoice_pdf_has_no_footer_page_number_by_default` (Ende-zu-Ende an einer echten Rechnung:
  `"Seite 1 von 1"` erscheint nicht, `"1 / 1"` aus der Wiederholungszeile/dem Meta-Block schon).
  `pytest` vollständig grün (902/902).
- **Hinweistext in den Einstellungen erweitert, nicht verdoppelt**: der bereits seit 1.3.2
  bestehende `.hint`-Absatz unter den drei Kontrollkästchen (Einstellungen → Dokumente →
  Mahnwesen-Layout, `app/templates/settings.html`) erklärte bisher nur die Kollisionsgefahr
  zwischen Logo/Firmenkopf und dem oberen Rand des fließenden Inhalts. Um denselben Absatz (statt
  einen zweiten danebenzustellen) erweitert: Logo und Firmenkopf bleiben bei der ursprünglichen
  Erklärung (Kollision mit dem fließenden Inhalt, abhängig vom oberen Rand), die Fußzeile bekommt
  einen eigenen, neuen Satz zur andersartigen Kollisionsgefahr (feste Position unabhängig vom
  Rand, überlagert bei eigenem Briefbogen dessen aufgedrucktem Fußbereich) mit der Begründung,
  warum sie deshalb standardmäßig aus ist.
- **Visuelle Nachprüfung**: dieselbe echte Rechnung (Nr. 5) erneut gerendert und denselben
  Bildausschnitt zugeschnitten/vergrößert wie beim ursprünglichen Fund -- "52531 Übach-Palenberg"
  ist wieder vollständig lesbar, keine überlagernde Seitenzahl mehr an dieser Stelle.

### Positionstabelle: Menge/Einheit/Breite (seit 1.3.9)

An einer echten Schlussrechnung gemeldet (Screenshot des Betreibers), vier Punkte, bewusst vor dem
geplanten Auftrags-Umbau erledigt, damit die Tabellen nicht zweimal angefasst werden.

- **Eine Mengenspalte statt drei**: `invoice_pdf.py`s Positionstabelle zeigte bisher "Menge
  (Soll)"/"Ist (gesamt)"/"abger. Menge" nebeneinander (`InvoiceItem.soll_quantity`/`ist_quantity`/
  `billed_quantity`, siehe deren Docstring in `models.py` für die fachliche Bedeutung) -- auf einem
  Kundendokument gehört davon nur die tatsächlich abgerechnete Menge (`billed_quantity`) hin, jetzt
  schlicht "Menge" beschriftet. **Vor dem Entfernen geprüft** (wie verlangt): `invoice_detail.html`
  (die Bildschirmansicht, `.inv-head`-Zeile) zeigt weiterhin alle drei Werte als eigene Spalten
  ("Soll"/"Ist (gesamt)"/"abgerechnet") -- die Information geht nirgends verloren, nur das PDF wird
  reduziert; abgesichert durch `test_invoice_detail_screen_still_shows_all_three_quantities()`
  (`tests/test_v231_invoice_item_table_width_and_quantity.py`), ein reiner Quelltext-Beleg (die
  Seite lädt ihre Daten client-seitig per `fetch()`, kein Rendertest möglich/nötig). **Angebot und
  Auftrag mussten nicht angefasst werden** -- `QuoteItem`/`OrderItem` kennen gar keine Soll/Ist-
  Aufteilung (nur ein einzelnes `quantity`-Feld), `quote_pdf.py`/`quote_layout_pdf.py`/
  `order_pdf.py` zeigten also schon vorher nur eine einzige Mengenspalte. Für den Auftrag war exakt
  das fachlich Richtige zu bestimmen ("was zeigt eine Auftragsbestätigung sinnvollerweise?") --
  Antwort: die beauftragte Menge (`OrderItem.quantity`, der LV-Snapshot zum Zeitpunkt der
  Beauftragung) -- das ist bereits der Ist-Zustand, keine Änderung nötig, nur bestätigt.
- **Einheit ergänzt**: `InvoiceItem.unit` existierte bereits als Spalte (unverändert aus
  `OrderItem.unit` beim Anlegen der Rechnungsposition übernommen,
  `invoices.py::_copy_order_items_with_default_ist()`, Zeile mit `unit=order_item.unit`) und war
  in `invoice_to_dict()`s `items`-Liste auch längst
  enthalten -- sie stand nur nirgends auf dem PDF. Kein fehlendes Datenmodell-Feld, wie zunächst
  befürchtet, sondern eine reine Anzeigelücke. Neue Spalte "EH" direkt neben "Menge" (14mm Breite)
  -- **geprüft statt übernommen**: die erwartete Beschriftung "Menge Einh." als EINE gemeinsame
  Spaltenüberschrift mit Wert+Einheit in derselben Zelle existiert weder im Code noch im
  tatsächlich gerenderten Angebots-PDF (`quote_layout_pdf.py::_build_configured_items_table()`,
  `PREDEFINED_TABLE_FIELDS["items_table"]` in `app/document_table_fields.py`) -- Angebot UND
  Auftrag zeigen "Menge" und "EH" bereits heute als zwei eigenständige, unmittelbar
  nebeneinanderliegende Spalten mit je eigener Überschrift (dasselbe Beschreibungsfehler-Muster
  wie schon bei der 1.3.7-Wiederholungszeile, dort aus einem "anderen System" stammend). Die
  Rechnung übernimmt jetzt exakt dieses bereits etablierte, real existierende Muster (gleiche
  Spaltenbreite/-beschriftung "EH" wie `order_pdf.py`/`quote_layout_pdf.py`), statt ein neues,
  nirgends vorhandenes zu erfinden.
- **Tabellenbreite aus den echten Randeinstellungen, nicht aus einem hart codierten Wert** -- der
  eigentliche, gemessene (nicht geschätzte) Fund: an einer gerenderten Beispielrechnung mit
  `pypdfium2`-Zeichenboxen nachgemessen (Standardränder 18mm/16mm, rechte Kante bei 194mm):
  "Position" begann bei 15,82mm statt 18,20mm (wie Absenderzeile/Überschrift/Summenblock), der
  Betrag-Wert endete bei 196,35mm statt 194,00mm -- die Positionstabelle ragte gleichzeitig LINKS
  UND RECHTS über die gemeinsame Fluchtlinie hinaus. Ursache, aus zwei zusammenwirkenden Dingen:
  ihre `colWidths` summierten sich auf 185mm bei nur 176mm tatsächlich verfügbarer Breite, UND
  reportlabs `Table`-Klasse zentriert sich ohne explizites `hAlign` standardmäßig
  (`self.hAlign = hAlign or 'CENTER'`, `reportlab/platypus/tables.py`) -- bei einer zu breiten
  Tabelle verschiebt die Zentrierung ihre linke Kante nach LINKS aus dem Rahmen heraus (in diesem
  Fall um (176-185)/2 = 4,5mm), das unveränderte Zellenpolster der Spalten (~2,1mm) verschob den
  sichtbaren Text davon wieder teilweise zurück nach rechts, macht die Nettoverschiebung sichtbar
  kleiner als die volle 4,5mm, aber klar messbar in beide Richtungen. Derselbe 185mm-vs-176mm-
  Fehlbetrag UND das fehlende `hAlign` stecken laut Code-Prüfung identisch auch in
  `order_pdf.py`s und `quote_layout_pdf.py`s Positionstabellen -- **bewusst NICHT** in dieser
  Etappe mitbehoben (Angebot bleibt grundsätzlich unangetastet, der Auftrag folgt erst im
  geplanten eigenen Auftrags-Umbau), aber als verwandter, bereits bekannter Fund hier vermerkt,
  damit er bei jenem Umbau nicht neu entdeckt werden muss.

  Neue, öffentliche Funktion `document_frame.py::frame_content_width(margins) ->
  float` (dieselbe Formel wie die bereits bestehende, private `_build_frame()`) liefert die
  tatsächlich konfigurierte Innenbreite in reportlab-Punkten. `invoice_pdf.py` und
  `reminder_pdf.py` lesen sie einmalig zu Beginn (`get_margins(db, document_type, "first")`) und
  reichen sie durch: an `build_din5008_header_block()` (neuer, optionaler Parameter
  `content_width`, Rückfall `PAGE_CONTENT_WIDTH` wenn nicht übergeben -- hält die isolierten
  Bausteintests in `tests/test_v227_din5008_header_block.py` unverändert grün, ohne dass sie
  Margins/DB kennen müssten), an die jeweils eigene `_totals_table()`/Forderungstabelle (jetzt
  mit `content_width`-Parameter statt `PAGE_CONTENT_WIDTH`), und bei der Rechnung zusätzlich an
  die neu vermessene Positionstabelle (`ITEMS_COL_WIDTHS_MM` für die fünf festen Spalten,
  "Leistung" nimmt als einzige den variablen Rest auf -- analog zum bereits bestehenden Muster in
  `order_pdf.py`/`quote_layout_pdf.py`, wo die Beschreibungsspalte ebenfalls die flexible ist).
  Betrifft dadurch **beide** bereits umgestellten Renderer (Mahnung, Rechnung) gleichermaßen, wie
  verlangt -- nicht nur die Rechnung, an der der Fund ursprünglich gemeldet wurde.

  Nur die ÄUSSEREN Zellenränder der neuen Positionstabelle wurden genullt (`LEFTPADDING` auf der
  ersten Spalte, `RIGHTPADDING` auf der letzten) statt aller wie beim zweispaltigen Summenblock --
  bei sechs Spalten hätte eine komplette Nullung Menge und Einheit ohne jeden Zwischenraum
  aneinanderkleben lassen ("50,223m²" statt "50,223 m²"); abgesichert durch
  `test_quantity_and_unit_do_not_touch_each_other()`.

  **Mit geänderten Rändern nachgewiesen, nicht nur behauptet**: `document_page_margins.py`s
  `update_margins()` testweise auf 30mm/25mm (links/rechts) gesetzt und dieselbe Rechnung erneut
  gerendert -- "Position" landet bei 30,21mm, der Betrag-Wert bei 184,96mm (erwarteter rechter
  Rand: 210-25=185mm) -- beide folgen dem neuen Randabstand exakt, nicht mehr dem alten,
  176mm-hart-codierten Wert. Dieselbe Prüfung für die Mahnung (Forderungsaufstellung) in
  `test_reminder_amount_table_follows_custom_margins_too()`. Alle Nachweise als echte Tests in
  `tests/test_v231_invoice_item_table_width_and_quantity.py` festgehalten (per
  `pypdfium2`-Zeichenboxen, Muster `tests/test_v227_din5008_header_block.py::_char_x_range_mm`,
  dort importiert statt dupliziert).
- **Farbe der Langtexte geprüft, bewusst NICHT geändert**: eine echte Rechnung mit Langtext
  gerendert und pixelgenau untersucht (vollständiges Farbhistogramm der gerenderten Seite, jeder
  einzelne nicht-weiße Pixel) -- es gibt weder Grün noch Braun im gerenderten PDF, nur zwei
  neutrale, rein achromatische Grautöne (`#555555` für die Positionsnummer, über den bereits
  bestehenden `small`-Stil aus `build_styles()`; `#666666` für den Langtext, als Inline-`<font
  color>`-Tag). Dieselbe Kombination aus kleinerer Schrift (`size=7`) und exakt demselben
  `#666666`-Grauton für den Langtext findet sich identisch in ALLEN VIER bestehenden LV-
  Positionstabellen-Renderern (`app/quote_pdf.py`, `app/quote_layout_pdf.py`, `app/order_pdf.py`,
  jetzt auch `app/invoice_pdf.py`) -- eine klar erkennbare, viermal unabhängig wiederholte
  Gestaltungsabsicht (dezente Zweitrangigkeit des Langtexts gegenüber dem Kurztext), kein
  Überbleibsel einer einzelnen Datei. Nach Vorgabe ("nur ändern, wenn keine Begründung gefunden
  wird") deshalb unverändert gelassen. Das vom Betreiber wahrgenommene Grün/Braun kommt
  vermutlich vom Papier/Drucker (z. B. Tonermischung eines Laserdruckers bei reinem Grau) oder
  einem Bildschirm-/Screenshot-Farbprofil, nicht vom PDF selbst -- keine im Code auffindbare
  Ursache.
- **Akzeptanzkriterien geprüft**: Rechnung zeigt eine Mengenspalte mit Einheit;
  Positionstabelle/Summenblock/Fließtext beginnen auf derselben linken und enden auf derselben
  rechten Fluchtlinie (Standard- UND testweise geänderte Ränder); bestehende Inhaltstests
  (`test_invoice_pdf_contains_expected_content`, die Mahnung-Kopfbereichstests) bleiben
  unverändert grün; `pytest` vollständig grün (909/909).

### Dritte Etappe (seit 1.3.10): der Auftrag, plus Summenblock-Vorschlag

Vorgehen exakt wie bei der Rechnung in 1.3.7: Inhaltstest zuerst gegen die noch unveränderte
Fassung (`test_order_pdf_contains_expected_content`, `tests/test_v232_order_pdf_shared_frame.py`
-- Auftragsnummer/Kundenname/Positionen/Netto/Steuer/Brutto/Zahlungsbedingungen als Teilstrings),
muss vor UND nach dem Umbau unverändert grün bleiben -- ist er. `app/order_pdf.py` wechselt auf
`render_framed_pdf()` (`document_type="order"`, neu in `RENDERERS_USING_SHARED_FRAME`,
`app/document_frame.py`), Kopfbereich über `build_din5008_header_block()` statt des bisherigen
`build_customer_and_meta_block()`. Firmenkopf/Fußzeile stehen nicht mehr fest im Renderer --
kommen wie bei Mahnung/Rechnung entweder aus dem Briefbogen oder den abschaltbaren
Rahmen-Bausteinen; die Wiederholungszeile auf Folgeseiten (seit 1.3.7 Teil des RAHMENS, nicht des
Renderers) greift beim Auftrag automatisch mit, ohne dass `order_pdf.py` dafür etwas Eigenes
bauen musste (`test_continuation_header_appears_on_order_multipage_pdf`).

- **Meta-Zeilen gegen den Bestand geprüft**: Auftragsnr./Datum/Ihr Angebot
  (`quote_number_snapshot`)/Projekt (`project_number`) kommen unverändert aus `order_to_dict()`.
  **Sachbearbeiter/Projektleiter (`caseworker_employee_id`/`project_manager_employee_id`) sind
  beim Auftrag -- anders als bei der Rechnung, wo die Spalte nie befüllt wird (siehe „Bekannte,
  bewusst offene Punkte") -- tatsächlich in Gebrauch**: 4 von 5 echten Aufträgen in der
  Produktionsdatenbank haben einen Sachbearbeiter hinterlegt, einer zusätzlich einen
  Projektleiter. Beide bleiben deshalb im Kopfbereich sichtbar (vorher als zwei Felder in EINER
  Zeile des alten `build_customer_and_meta_block()`-Kopfbereichs, siehe unten) -- **jetzt aber
  unabhängig voneinander**: vorher erschien "Projektleiter" ausschließlich in derselben Zeile wie
  "Sachbearb.", also NIE, wenn nur ein Projektleiter ohne Sachbearbeiter hinterlegt war (ein
  Fall, der in der echten Datenbank zwar aktuell nicht vorkommt, aber durchaus vorkommen könnte).
  Mit dem neuen, einer-Zeile-pro-Feld-Kopfbereich (`build_din5008_header_block()`s Meta-Tabelle)
  zeigt jedes der beiden Felder unabhängig, ob es gesetzt ist -- eine kleine, aber echte
  Verbesserung, kein reiner Umzug. Abgesichert durch
  `test_caseworker_and_project_manager_shown_independently()`/
  `test_project_manager_shown_even_without_caseworker()`.
- **Breitenkorrektur aus 1.3.9 mitgenommen, plus ein dritter, nur hier auftretender Effekt**: an
  einer Beispielrechnung nachgemessen (`pypdfium2`-Zeichenboxen, Standardränder 18mm/16mm) --
  vorher: die Positionstabelle begann bei 15,74mm statt 18,20mm (linke Fluchtlinie) und endete bei
  196,35mm statt 194,00mm (rechte Fluchtlinie), exakt dieselbe 185mm-`colWidths`-Summe-vs-176mm-
  verfügbare-Breite-Ursache wie bei der Rechnung (reportlabs `Table`-Standard `hAlign="CENTER"`
  verschiebt eine zu breite Tabelle nach links, siehe CLAUDE.md "Positionstabelle: Menge/Einheit/
  Breite"). **Zusätzlich, nur beim Auftrag**: der Summenblock hatte bereits `hAlign="RIGHT"` UND
  eine passend schmalere Breite (`colWidths=[115mm, 45mm]`, Summe 160mm < 176mm) -- trotzdem
  endete sein Wert bei nur 189,75mm statt 194,00mm. Ursache: der alte, unmigrierte Renderer nutzte
  `SimpleDocTemplate`, dessen intern automatisch erzeugter Standard-`Frame`
  (`doctemplate.py::SimpleDocTemplate.build()`: `Frame(self.leftMargin, self.bottomMargin, ...)`
  OHNE Padding-Argumente) selbst ein ungenulltes 6pt-Innenpolster mitbringt (reportlabs
  `Frame.__init__()`-Vorgabe `leftPadding=6, ..., rightPadding=6` in Punkten) -- zusätzlich zum
  ebenfalls ungenullten Zellenpolster der Tabelle selbst. `document_frame.py::_build_frame()`
  nullt dieses Frame-Innenpolster bereits seit 1.3.1 (`leftPadding=0, ...`) -- mit dem Wechsel auf
  den gemeinsamen Rahmen entfällt dieser Effekt automatisch, ohne dass er eigens behandelt werden
  musste. Der Summenblock (`_totals_table()`) wurde dabei zusätzlich auf dieselbe volle-Breite-
  plus-genulltes-Zellenpolster-Bauweise wie bei Mahnung/Rechnung umgestellt (`frame_content_width()`
  statt der festen 115mm/45mm-Aufteilung mit `hAlign="RIGHT"`) -- konsequent, auch wenn nur die
  Positionstabelle explizit als 185mm-Fund benannt war. Nachher: Positionstabelle bei 18,12mm/
  193,96mm, Summenblock bei 18,00mm/193,98mm -- beide innerhalb der Messtoleranz auf der jeweils
  erwarteten Fluchtlinie. Mit testweise auf 30mm/25mm geänderten Rändern zusätzlich nachgewiesen,
  dass beide Tabellen dem tatsächlich konfigurierten Randabstand folgen, nicht einem hart
  codierten Wert (`test_item_table_and_totals_follow_custom_margins_not_hardcoded_default`).
- **Geprüft, BEVOR etwas geändert wurde**: greift `order_pdf.py` oder `order_to_dict()`
  irgendwo auf `order.project.customer`/`order.project.property` (live, nachschlagbar) statt auf
  die bei Beauftragung eingefrorenen Order-Spalten `customer_name`/`customer_address`/
  `property_name`/`property_address` zu? Projektweiter Grep + vollständiges Lesen beider Dateien:
  **nein** -- beide lesen ausschließlich die eingefrorenen Spalten (`order.customer_name` usw.,
  von `_copy_quote_scope_to_order()` bei Beauftragung einmalig befüllt, siehe `app/orders.py`).
  Einzige live nachgeschlagene Werte sind `order.project.project_number`/`.name`/`.customer_id`
  (Projekt-Metadaten bzw. eine reine ID zum Verlinken, keine Adressdaten) -- unproblematisch, da
  ein Projektname/eine Projektnummer nicht dieselbe GoBD-Unveränderlichkeitsanforderung trägt wie
  eine Rechnungs-/Lieferadresse. Kein Fund, keine Änderung nötig -- als Regression festgehalten in
  `test_order_pdf_uses_frozen_snapshot_not_live_customer_or_property_data()` (Kunde zieht NACH der
  Beauftragung um, das PDF darf die neue Adresse nicht zeigen).
- **Bereits als PDF versendete Aufträge**: **keiner** -- von 5 Aufträgen in der echten,
  produktiven Datenbank hat noch keiner `email_sent_at` gesetzt (`send_order_email()`,
  `app/orders.py`, seit 1.0.90 grundsätzlich möglich). Ohnehin ohne jede GoBD-Relevanz für diese
  Etappe: `build_order_pdf()` wird bei jedem Download UND bei jedem E-Mail-Versand live neu
  aufgerufen (`routers/orders.py`/`orders.py::send_order_email()`), es existiert kein
  gespeichertes PDF-Blob, das durch den Rahmenumbau rückwirkend anders aussehen könnte -- exakt
  dieselbe, bereits für die Rechnung (1.3.7) geklärte Ausgangslage.
- **Summenblock-Vorschlag, bewusst noch nicht gebaut**: mit dem Auftrag sind jetzt DREI Renderer
  (Mahnung, Rechnung, Auftrag) auf denselben Summenblock-Aufbau umgestellt -- zweispaltige
  Tabelle über `frame_content_width() - 45mm`/`45mm`, `ALIGN` rechts auf der Wertespalte,
  `LINEABOVE`+fett auf der letzten Zeile, links/rechts genulltes Zellenpolster. Bisher drei fast
  identische Kopien (`reminder_pdf.py` inline, `invoice_pdf.py::_totals_table()`,
  `order_pdf.py::_totals_table()`) -- laut früherer Klärung (siehe 1.3.7) genau die Schwelle, ab
  der eine Zusammenführung lohnt. Vorschlag: eine einzige Funktion
  `build_totals_table(rows: list[list[str]], content_width: float) -> Table` in
  `app/document_pdf.py` (demselben Modul wie `build_din5008_header_block()`/
  `build_object_address_block()`/`build_payment_tax_closing_block()` -- der etablierte Ort für
  datengetriebene, dokumenttyp-unabhängige PDF-Bausteine), die alle drei Renderer statt ihrer
  eigenen `_totals_table()`/inline-Table importieren; jeder Renderer baut weiterhin selbst seine
  `rows`-Liste (Bezeichnungen/Werte sind fachlich unterschiedlich -- "Auftragssumme brutto" vs.
  "Rechnungsbetrag brutto" vs. "Gesamtbetrag", die Mahnung hat z. B. keine MwSt.-Zeile), nur der
  Tabellenaufbau selbst wird geteilt. Bewusst NICHT gebaut, wie verlangt -- nur vorgeschlagen.
- **Akzeptanzkriterien geprüft**: Auftrag trägt denselben Briefbogen/dieselben Ränder wie
  Mahnung/Rechnung ohne eigene Einstellung; Kopfbereich sieht aus wie bei Mahnung/Rechnung, mit
  den Meta-Zeilen des Auftrags (inkl. unabhängig sichtbarem Sachbearbeiter/Projektleiter);
  Positionstabelle/Summenblock/Fließtext beginnen auf derselben linken und enden auf derselben
  rechten Fluchtlinie (Standard- UND testweise geänderte Ränder); eine mehrseitige
  Auftragsbestätigung zeigt auf Folgeseiten die Wiederholungszeile; Inhaltstest vor/nach
  identisch grün; Angebot/Einsatzbericht unverändert, ihre Tests bleiben grün; `pytest`
  vollständig grün (920/920).

### Vierte Etappe (seit 1.3.11): der Einsatzbericht

Vorgehen wie bei Rechnung/Auftrag. **Neu gegenüber den drei vorherigen Etappen**: `service_report`
existierte als `document_type` bisher NIRGENDS -- weder in `DOCUMENT_TYPES`
(`app/document_layout.py`, sonst wirft `ensure_default_layout()` einen `ValueError`) noch in
`RENDERERS_USING_SHARED_FRAME` (`app/document_frame.py`). Beide mussten für diese Etappe zum
ersten Mal um einen komplett neuen Typ erweitert werden, nicht nur einen bereits bekannten
migrieren. `app/document_page_margins.py` brauchte dagegen keine Änderung -- validiert
`document_type` schon immer nicht gegen eine feste Liste, `resolve_shared_document_type()`
(`app/document_type_fallback.py`) ebenfalls nicht.

- **Bestehende Testabdeckung geprüft, EIN Inhaltstest ergänzt**: `test_v203/213/214/223`
  decken Prüfpunkte ("Gully Nordost"/"OK"), Mängel/Dokumentation, Material bereits gut ab -- aber
  keiner davon prüft Auftrags-/Kundenidentität oder die seit 1.3.0 bestehenden zwei
  Unterschriften-Beschriftungen zusammen. `test_service_report_pdf_contains_expected_content()`
  (`tests/test_v233_service_report_pdf_shared_frame.py`) schließt genau diese Lücke -- vor UND
  nach dem Umbau unverändert grün, wie bei Rechnung/Auftrag verlangt.
- **Meta-Zeilen gegen den Bestand geprüft**: Auftragsnr./Datum/Berichtstyp (=derselbe Text wie
  die H1-Überschrift, aus `REPORT_TYPE_LABELS`)/Kunden-Nr. (nur wenn `order.customer_number`
  gesetzt)/Monteur (`created_by_employee_name`, nur wenn gesetzt)/Seite -- alle bereits vorher im
  Fließtext vorhanden ("Auftrag: ... Kunde: ... Datum des Einsatzes: ... Durchgeführt von: ..."),
  nur in den neuen Kopfbereich umgezogen; nichts Neues erfunden. Kunde/Objektadresse wandern
  entsprechend in die Empfängerzeilen/`build_object_address_block()` (letzterer Baustein war in
  diesem Renderer vorher gar nicht verdrahtet, obwohl `Order.property_name`/`-address` dieselben
  bereits existierenden Spalten sind, die Mahnung/Rechnung/Auftrag längst nutzen -- erscheint
  weiterhin nur, wenn tatsächlich ein Objekt hinterlegt ist).
- **KeepTogether-Blöcke aus 1.2.21 -- Test allein reicht nicht, wie vom Nutzer verlangt**:
  Unterschriftenblock, Mangel-Blöcke, Prüfpunkt-Gruppen-Tabellen und Fotoblöcke bleiben
  unverändert in `KeepTogether(...)` gekapselt, nur ihre Tabellenbreiten wurden angepasst (siehe
  unten). Zusätzlich zu den automatisierten Tests ein eigens erzeugter, ELFSEITIGER Bericht (zwei
  Dachflächen, 16 Bauteile, 42 Prüfpunkte, 12 Mängel mit 15 Fotos, 4 Materialpositionen, echte
  Zwei-Unterschriften-Signierung) -- jede der 11 Seiten einzeln als PNG gerendert und durchgesehen
  (nicht nur automatisiert geprüft): kein Mangel-Block, keine Prüfpunkt-Gruppe, kein Foto und
  keine Unterschrift über einen Seitenumbruch gerissen; der letzte Mangel UND der komplette
  Unterschriftenblock landen zusammenhängend auf der letzten Seite. **Beobachtet, aber bereits vor
  diesem Umbau identisch vorhanden (keine Regression, nicht Teil dieser Etappe)**: die
  Abschnitts-/Dachflächen-Überschriften selbst (`Paragraph("Prüfpunkte", h2)`,
  `Paragraph(area_name, h2)`, `Paragraph("Festgestellte Mängel", h2)`) sind bare `Paragraph`s ohne
  eigenes `KeepTogether` -- eine Überschrift kann dadurch allein am Seitenende stehen, während ihr
  erster Tabellen-/Mangel-Block schon auf der Folgeseite beginnt. Anders als bei den vier vom
  Nutzer genannten Blöcken (die tatsächlich zusammengehörigen INHALT zerreißen würden) betrifft das
  hier nur eine einzelne Überschrittzeile -- im alten, unmigrierten Code exakt genauso vorhanden,
  unverändert übernommen.
- **Fotobreite folgt jetzt frame_content_width()**: `_pdf_image()`/`_render_photo_flowables()`
  hatten die beiden Vorschaugrößen (70mm Einzelfoto, 80mm je Vorher/Nachher-Bild) bisher absolut
  hart codiert, unabhängig vom tatsächlich konfigurierten Rand. Jetzt `min(Vorschaugröße,
  verfügbare Breite)` -- bei ausreichend Platz (der Normalfall) bleiben Fotos exakt gleich groß
  wie vorher, nur bei einem sehr schmalen, selbst konfigurierten Satzspiegel werden sie nach unten
  gekappt, statt über den Rand hinauszustehen. Bewusst KEINE Vergrößerung nach oben bei mehr
  verfügbarem Platz -- es sind Vorschaugrößen, keine "so groß wie möglich"-Vorgabe.
- **Tabellenbreiten geprüft (wie in 1.3.9 an der Rechnung), zwei echte Funde**: die
  Vorher/Nachher-Fototabelle UND die zweispaltige Unterschriften-Tabelle (Punkt 6 der Anfrage,
  seit 1.3.0) hatten beide `colWidths=[95mm, 95mm]` = 190mm -- 14mm mehr als die 176mm
  Standardbreite, reportlabs `Table`-Standard `hAlign="CENTER"` zentrierte beide dadurch sichtbar
  nach links. Nachgemessen an der Unterschriften-Tabelle (Standardränder): vorher "Bestätigt von:
  Monteur Meier" bei 13,32mm (statt 18,20mm), "Kunde"-Spalte durch die Zentrierung insgesamt zu
  weit links; nachher exakt 18,21mm (erste Spalte) und 108,32mm (zweite Spalte, `content_width`/2
  + Standard-Zellenpolster). Mit testweise auf 30mm/25mm geänderten Rändern zusätzlich
  nachgewiesen: 30,21mm/109,82mm -- folgt jetzt dem echten Rand, nicht mehr dem alten 190mm-Wert.
  Prüfpunkt-/Material-/Zeiten-Tabelle summierten sich schon vorher exakt auf 176mm (kein sichtbarer
  Fehler bei Standardrändern), waren aber ebenso hart codiert -- jetzt nach demselben Muster wie
  bei der Rechnung (`ITEMS_FIXED_COLS_MM`-artige Konstanten, eine Text-/Beschreibungsspalte nimmt
  den variablen Rest `content_width - Summe der übrigen` auf). Alle Tabellen zusätzlich mit
  `_ZERO_OUTER_TABLE_PADDING` (nur die äußersten Spaltenränder genullt, nicht alle) auf dieselbe
  Fluchtlinie wie der Kopfbereich gebracht -- bei mehr als zwei Spalten hätte eine komplette
  Nullung benachbarte Werte ohne Zwischenraum aneinanderkleben lassen.
- **Snapshot-Prüfung wie beim Auftrag (1.3.10) -- diesmal mit echtem Fund**: greift der Renderer
  auf `order.project.customer`/`-property` zu? Nein, `order.customer_name`/`-address`/
  `property_name`/`-address` sind dieselben, bereits als sicher bestätigten Order-Spalten. ABER:
  `finding.roof_component.name` (Mangel-Überschrift) UND `link.roof_area.name` (Gruppierung von
  Prüfpunkten UND Material nach Dachfläche, jeweils zwei Fundstellen) lesen den AKTUELLEN Namen
  des `RoofComponent`/`RoofArea`-Datensatzes zur Renderzeit -- keine der beiden Tabellen
  (`Finding.roof_component_id`, `ServiceReportRoofArea.roof_area_id`) trägt eine eigene
  Namensspalte, `InspectionItem.text` dagegen ist bereits eine physische Kopie (bestätigt
  unverändert sicher, siehe CLAUDE.md „Strukturierte Prüfpunkte"). Ein nach der Unterschrift
  umbenanntes Bauteil oder eine umbenannte Dachfläche würde im PDF eines bereits unterschriebenen,
  eigentlich unveränderlichen Berichts anders erscheinen als zum Unterschriftszeitpunkt. **Bewusst
  NICHT behoben** -- reine Rahmen-Umstellung, kein Datenmodell-Umbau; gemeldet statt stillschweigend
  geändert, siehe „Bekannte, bewusst offene Punkte" unten.
- **Akzeptanzkriterien geprüft**: Einsatzbericht trägt denselben Briefbogen/dieselben Ränder wie
  Mahnung/Rechnung/Auftrag ohne eigene Einstellung; Kopfbereich sieht aus wie bei den anderen drei,
  mit den Meta-Zeilen des Berichts; alle Tabellen/Fotos beginnen auf derselben linken Fluchtlinie
  (Standard- UND testweise geänderte Ränder); ein elfseitiger Bericht zeigt auf Folgeseiten die
  Wiederholungszeile und reißt an keiner Stelle einen KeepTogether-Block; Inhaltstest vor/nach
  identisch grün; Angebot unverändert, seine Tests bleiben grün; `pytest` vollständig grün
  (931/931).

### Fehlerbehebung (seit 1.3.12): einstellbare Position der Wiederholungszeile

Der 1.3.11-Fund (Wiederholungszeile auf Folgeseiten überlagert die Dekorfläche des echten
Briefpapiers) lässt sich anders als der 1.3.8-Fußzeilen-Fund NICHT durch einen Standardwert
`visible=False` lösen -- der Bezug zum Dokument (Rechnungsnr./Kunden-Nr./Datum) wird auf einer
Folgeseite eines mehrseitigen Dokuments tatsächlich gebraucht. Lösung: die Position wird
einstellbar, statt fest zu stehen.

- **`DocumentLayoutBlock.y_mm`/`height_mm` tatsächlich genutzt, statt eines neuen Felds**: der
  `continuation_header`-Block trägt (wie jeder `DocumentLayoutBlock`) bereits `x_mm`/`y_mm`/
  `width_mm`/`height_mm` -- vorher komplett ignoriert (feste Konstante
  `CONTINUATION_HEADER_Y_MM = 8.0` in `app/document_frame.py`). Jetzt liest `_NumberedCanvas.save()`
  die vertikale Position aus `self._continuation_header["y_mm"]` (vom Block selbst, über
  `_build_once()` durchgereicht), `height_mm` fließt in die geometrische Kollisionsprüfung ein.
  `x_mm`/`width_mm` bleiben bewusst UNGENUTZT für die horizontale Ausdehnung -- die kommt
  weiterhin aus `frame_content_width()`/den echten Rändern, damit die Zeile immer auf derselben
  Fluchtlinie wie der übrige Inhalt endet; würde sie stattdessen aus einem festen `width_mm`-Wert
  kommen, wäre das genau der 176mm-hart-codiert-Fehler aus 1.3.9 an anderer Stelle neu eingeführt.
  Einstellbar über dieselbe Oberfläche wie die Sichtbarkeit (`PUT /api/document-layout/blocks/{id}`,
  Einstellungen → Dokumente & Layout, neues Zahlenfeld "Position von oben (mm)" direkt unter dem
  Kontrollkästchen) -- keine neue Spalte im Datenmodell, keine neue Route.
- **Am echten Briefpapier nachgemessen** (Pixelanalyse der hochgeladenen JPEG-Datei für
  Folgeseiten, 200dpi, `data/document_layout_backgrounds/`): die Dekorfläche besteht aus zwei
  Teilen -- einem Banner (dunkelgrün zu hellgrün, endet an den meisten Stellen zwischen 7,6mm und
  11,0mm von oben) UND, zentriert, dem Firmenlogo samt Schriftzug, das deutlich tiefer reicht: bis
  30,8mm von oben. Der ursprüngliche Fund (Text sichtbar auf dem Banner) UND die Tatsache, dass
  der linksbündige Zeilentext (Auftragsnr./Datum/Kunden-Nr.) bei ausreichender Länge durch die
  Bildmitte läuft, wo das Logo sitzt, machen beide Teile relevant.
- **Neuer Codestandard 12mm/4mm** (`DEFAULT_SHARED_LAYOUT`, `app/document_layout.py`) -- bewusst
  NICHT auf den gefundenen 30,8mm-Wert dieses einen, ungewöhnlich tief reichenden Logos
  zugeschnitten (das wäre eine Überanpassung an eine einzelne Installation), sondern für einen
  Briefbogen OHNE eigene Kopfgrafik gewählt: bleibt mit 1mm Puffer unterhalb der Unterkante von
  Logo/Firmenkopf (die bei `y_mm=17` beginnen). Eine Installation mit einer tieferen Kopfgrafik
  (wie im konkreten Fund) muss den Wert selbst über das neue Feld erhöhen.
- **Die bereits gesäte "default"-Zeile in der echten Datenbank korrigiert** (`update_layout_block()`,
  kein rohes SQL, derselbe Nachkorrektur-Mechanismus wie 1.3.2/1.3.8): auf `y_mm=34`/`height_mm=4`
  gesetzt -- 32mm reichte im ersten Versuch noch nicht ganz (das Textfeld zeichnet an der
  BASELINE, nicht an der Textoberkante; bei 8pt-Schrift liegt die Oberkante rund 2mm über der
  Baseline, ein Wert von 32mm ließ die Zeile deshalb noch minimal in den Schriftzug hineinlaufen)
  -- an einer echten, signierten Rechnung aus der Produktionsdatenbank gerendert und mit einem
  zugeschnittenen Bildvergleich vorher/nachher bestätigt: die Adresse des Briefpapiers
  ("52531 Übach-Palenberg") und jetzt auch der Firmenschriftzug sind vollständig lesbar, keine
  Überlagerung mehr.
- **Test**: `test_continuation_header_vertical_position_is_configurable`
  (`tests/test_v230_invoice_pdf_shared_frame.py`) weist die Konfigurierbarkeit end-to-end nach --
  Position um 15mm ändern, real neu rendern, verschobene Zeile per `pypdfium2`-Zeichenboxen
  nachmessen (misst die Verschiebung, nicht die absolute Position, da `get_charbox()` die
  Glyphen-Oberkante liefert, nicht die Zeichen-Baseline, auf die sich `y_mm` bezieht -- die
  Differenz zwischen beiden ist bei fester Schriftgröße konstant und kürzt sich beim
  Vorher/Nachher-Vergleich heraus). Die bestehende Kollisions-Invarianten-Prüfung
  (`test_continuation_header_does_not_overlap_company_header_or_content`) liest jetzt ebenfalls
  `continuation_header.y_mm`/`.height_mm` statt der entfernten Konstante.
- **Hinweistext verallgemeinert, wie verlangt** (`app/templates/settings.html`, Abschnitt
  "Gezeichnete Bausteine") -- das ist jetzt der DRITTE Baustein mit demselben grundsätzlichen
  Problem (nach company_header/logo in 1.3.2 und footer_text in 1.3.8): der Hinweis beginnt jetzt
  mit dem allgemeinen Prinzip ("jeder der vier Bausteine wird an einer festen Stelle gezeichnet --
  trifft dort ein eigener Briefbogen bereits etwas Aufgedrucktes, überlagern sich beide sichtbar"),
  bevor die vier Bausteine einzeln erläutert werden -- statt eines vierten, separat
  danebengeschriebenen Absatzes.

### Fünfte und letzte Etappe (seit 1.3.13): das Angebot

Größter und riskantester Schritt des ganzen Umbaus -- anders als bei den vier vorherigen gibt es
hier ein produktiv angepasstes Layout, das nicht schlechter werden darf. Deshalb ANDERES
Vorgehen als bisher: neuer Renderer PARALLEL zum bestehenden gebaut, gegen echte Angebote
verglichen, gefundene Abweichungen behoben, erst DANACH umgestellt -- nicht in einem Schritt wie
bei Mahnung/Rechnung/Auftrag/Einsatzbericht.

- **Neuer, paralleler Renderer** `app/quote_framed_pdf.py::build_quote_framed_pdf()` --
  `render_framed_pdf()`, `document_type="quote"` (neu in `RENDERERS_USING_SHARED_FRAME`),
  Kopfbereich über `build_din5008_header_block()`, Positionstabelle über
  `frame_content_width()`, Summenblock wie bei Rechnung/Auftrag (eigene kleine
  `_totals_table()`-Kopie, die geplante Zusammenführung aus 1.3.10 bleibt weiterhin nur
  vorgeschlagen). `app/quote_layout_pdf.py` (produktiv, positionsbasiert) und `app/quote_pdf.py`
  (älter, einfach fließend) bleiben unangetastet. **"quote" bleibt bewusst außerhalb des
  "default"-Rückfalls** (`resolve_shared_document_type()` behandelt "quote" unverändert als
  Sonderfall, der nie zurückfällt) -- der neue Renderer liest dieselben, schon heute produktiv
  angepassten "quote"-Zeilen für Briefpapier/Ränder, keine neue Migration dafür nötig. Ein
  Umzug auf den geteilten "default"-Satz (von den quote-eigenen Zeilen weg) ist ein eigener,
  bewusst NICHT in dieser Etappe gegangener Schritt, siehe „Bekannte, bewusst offene Punkte".
- **Zehn Bausteine geprüft, bevor gebaut wurde** -- die echten, produktiven
  `document_layout_blocks`-Zeilen für "quote" enthalten KEINEN einzigen `custom_text`-Baustein
  (alle zehn sind die vordefinierten `DEFAULT_QUOTE_LAYOUT`-Typen) -- der vom Nutzer als
  wichtigster Fall benannte "eigene Textblöcke dürfen nicht verschwinden" trifft auf die reale
  Installation also nicht zu. `company_header`/`customer_address`/`meta_table` waren bereits
  produktiv in eine DIN5008-ähnliche Anordnung verschoben (kleine Absenderzeile, Anschrift
  darunter, Meta-Tabelle rechts daneben) -- exakt die Geometrie, aus der
  `build_din5008_header_block()`s Konstanten in 1.3.3 ursprünglich abgemessen wurden, der
  optische Sprung ist dadurch kleiner als befürchtet. `DocumentTableField` (Layout-Designer-
  Feldkonfiguration) ist bestätigt ausschließlich von `quote_layout_pdf.py`/dessen Editor genutzt
  (kein anderer Renderer importiert es) -- für die reale Installation ändert eine Ablösung durch
  feste Spalten (wie bei Auftrag/Rechnung) nichts Sichtbares, da dort ohnehin kein Feld vom
  Standard abweicht.
- **Echte Übertragszeile -- eine neue Funktion, kein migriertes Feature.** Weder
  `quote_layout_pdf.py` noch `quote_pdf.py` hatten je eine laufende Summe über Seitenumbrüche
  (projektweiter Grep nach "Übertrag"/"Zwischensumme" ohne Treffer) -- nur eine statische
  Fortsetzungs-Beschriftung ohne Betrag (`_draw_continuation_header()`). Auf ausdrücklichen
  Wunsch als neues Feature gebaut, UND ausdrücklich lückenlos (auch ein Umbruch GENAU zwischen
  zwei Abschnitten braucht eine Übertragszeile, nicht nur ein Umbruch mitten in einer
  Positionsgruppe). Lösung: die komplette Positionsliste (alle Abschnitte samt Titeln als Zeilen)
  ist EINE einzige `_CarryForwardItemsTable` (`Table`-Unterklasse) statt mehrerer separater
  Tabellen mit dazwischenliegenden Titel-Absätzen -- reportlab ruft `split()` nur auf Tabellen
  auf, ein Umbruch zwischen zwei getrennten Flowables (Tabelle + folgender Titel-Absatz) wäre für
  eine split()-Überschreibung sonst unsichtbar geblieben. `split()` reserviert vor dem
  eigentlichen `Table.split()`-Aufruf die Höhe einer Übertragszeile, sonst würde reportlabs
  eigene Aufteilung die Seite bereits bis zum letzten Millimeter füllen und die zusätzliche Zeile
  selbst auf die nächste Seite rutschen lassen. Eine vorab pro Körperzeile berechnete, laufende
  Netto-Summe (`row_cumulative`, Titelzeilen tragen den Vorwert unverändert fort, optionale
  Positionen tragen nichts bei -- dieselbe Netto-Logik wie der Summenblock) liefert den Betrag an
  der tatsächlichen Umbruchstelle. reportlab konstruiert beide Split-Teile intern über
  `self.__class__(...)` (`Table._splitRows()`), die Unterklasse bleibt dadurch über beliebig
  viele Folgeseiten hinweg erhalten -- verifiziert VOR dem Bauen durch Lesen des reportlab-
  Quelltexts, nicht nur durch Ausprobieren. Verifiziert an einem synthetischen 90-Positionen/
  2-Abschnitte/5-Seiten-Angebot (exakte Beträge auf beiden Seiten aller vier Umbrüche) UND am
  echten, zweiseitigen Angebot A-2026-0001 (42,63 EUR auf beiden Seiten des einzigen Umbruchs).
- **Zwei echte Funde beim Vergleich gegen A-2026-0001, beide behoben, bevor umgestellt wurde:**
  1. **Doppelter Firmenkopf.** "quote" behält (anders als jeder andere Dokumenttyp seit 1.3.2)
     seine eigene, historische `company_header`-Zeile mit `visible=True` -- eine kleine, auf
     DIN5008-Anordnung zugeschnittene Box, die nur den Firmennamen zeigt. Der neue Renderer
     zeichnete zusätzlich seine eigene DIN5008-Absenderzeile, UND der gezeichnete
     `company_header`-Rückfall (`document_frame.py::_draw_company_header()`) kennt keine
     Feldfilterung (die ist eine `DocumentTableField`-Eigenschaft nur des alten Renderers) --
     seine volle Kontaktzeile (Telefon/E-Mail/Website) lief dadurch sichtbar in den Meta-Block
     hinein. Neuer, optionaler Parameter `suppress_drawn_blocks: set[str]` an
     `render_framed_pdf()` (`app/document_frame.py`) -- **ausdrücklich als Übergangslösung
     dokumentiert**, nicht als dauerhafter Teil der Schnittstelle: ein Ändern der
     `company_header`/`logo`-Sichtbarkeit in der Datenbank (analog zur 1.3.2-Korrektur bei den
     anderen Dokumenttypen) kam nicht in Frage, solange `quote_layout_pdf.py` dieselbe Zeile noch
     produktiv liest -- das hätte dessen Ausgabe mitverändert, bevor überhaupt über eine
     Umstellung entschieden war. Entfällt zusammen mit `quote_layout_pdf.py` (siehe „Bekannte,
     bewusst offene Punkte" -- dann wird die Sichtbarkeit einfach in der Datenbank auf `False`
     gesetzt, wie bei jedem anderen Dokumenttyp).
  2. **Briefpapier verschwand auf Folgeseiten.** "quote" hat nur eine `page_type="first"`-Zeile
     in `DocumentLayoutBackground` mit `repeat_on_every_page=True` (Altbestand von vor der
     1.3.1-Seitentyp-Aufteilung, nie um eine eigene Folgeseiten-Zeile ergänzt) --
     `get_effective_background()` kannte dieses ältere Feld bisher gar nicht, da es aus der Zeit
     vor der seitentypbewussten Architektur stammt. `get_effective_background()`
     (`app/document_layout.py`) fällt jetzt auf die "first"-Zeile zurück, wenn für
     "continuation" keine eigene Zeile existiert UND `repeat_on_every_page` gesetzt ist -- ein
     generischer Fix (nicht quote-spezifisch verdrahtet), der aber aktuell nur "quote" betrifft,
     da "default" (Mahnung/Rechnung/Auftrag/Einsatzbericht) bereits zwei echte, getrennt
     hochgeladene Briefpapier-Dateien für Seite 1/Folgeseiten trägt und diesen Rückfall nie
     auslöst.
- **Wiederholungszeile auf Folgeseiten nachgerüstet** -- mit sechzehn Seiten laut Betreiber das
  mit Abstand längste Dokument im ganzen Projekt, gerade dort fehlte sie bisher am meisten.
  `DEFAULT_QUOTE_LAYOUT` bekommt einen elften Baustein (`continuation_header`, derselbe
  generische Standardwert wie überall seit 1.3.12, 12mm/4mm) -- Migration `ab5eef23f9ed` ergänzt
  ihn für die zehn bereits bestehenden "quote"-Zeilen (Muster `257fb2967c93` aus 1.3.7, dort für
  "default"). Am tatsächlichen Briefpapier gemessen (Pixelanalyse): dieselbe ~30,8mm tiefe
  Kopfgrafik wie beim "default"-Briefbogen -- die bereits gesäte Zeile in der echten Datenbank
  ist deshalb zusätzlich auf 34mm korrigiert (`update_layout_block()`, kein rohes SQL), nicht nur
  auf den generischen 12mm-Standardwert belassen. `build_quote_framed_pdf()` übergibt
  `continuation_header_rows` (Angebotsnr./Projekt) wie Auftrag/Rechnung.
- **Umstellung (Punkt 4): ausschließlich die beiden Wege, die beim Kunden ankommen.** Vor dem
  Umstellen geprüft, ob es weitere Aufrufer von `build_quote_pdf()`/`build_quote_layout_pdf()`
  gibt (Dokumentenmanagement, Sammelversand) -- keine gefunden: `customer_documents.py` kennt
  Angebote gar nicht, `send_quote_email()` hat genau einen Aufrufer
  (`routers/quotes.py::post_send_quote_email()`). `GET /api/quotes/{id}/pdf`
  (`routers/quotes.py::quote_pdf_api()`) nutzt jetzt `build_quote_framed_pdf()` statt des
  ältesten, einfachen `build_quote_pdf()` -- damit zeigt dieser Endpunkt erstmals dasselbe
  Ergebnis wie der E-Mail-Versand. `send_quote_email()` (`app/projects.py`) nutzt ebenfalls
  `build_quote_framed_pdf()` statt des bisherigen `build_quote_layout_pdf()`.
  `GET /api/quotes/{id}/pdf-layout-preview` (`quote_pdf_layout_preview_api()`) bleibt
  UNVERÄNDERT auf `build_quote_layout_pdf()` -- ausdrücklich als reine Vergleichsansicht, die
  erreichbar bleibt, bis sich der neue Renderer eine Weile im Einsatz bewährt hat. Die beiden
  zugehörigen Vorschau-Buttons -- in `quote_editor.html` ("PDF-Vorschau" /
  "PDF-Vorschau (älterer Weg)") UND im PDF-Layout-Editor
  (`document_layout_editor.html`, "Bisherige PDF-Vorschau" / "Layout-PDF-Vorschau") -- waren
  nach der Umstellung genau verkehrt beschriftet (die als "bisherig"/"älter" bezeichnete Ansicht
  zeigte plötzlich das NEUE Ergebnis). Beide Stellen umbeschriftet: der Button zum jetzt
  produktiven Endpunkt heißt schlicht "PDF-Vorschau" (Tooltip: "Entspricht dem, was per E-Mail
  versendet wird"), der Button zur Vergleichsansicht heißt deutlich "Vergleichsansicht: alter
  Renderer (entfällt demnächst)"; die "Mit Briefkopf"-Checkbox (nur vom alten Renderer über
  `include_background` unterstützt) heißt jetzt "Vergleichsansicht mit Briefkopf", damit klar
  ist, welchem der beiden Buttons sie zugeordnet ist.
- **Test-Hardening vor der Umstellung** (Punkt 1 der Planung): die vier bestehenden
  Test-Dateien für den alten Renderer (`test_v159_quote_layout_pdf.py`,
  `test_v167_pagination.py`, `test_v169_page_margins.py`, `test_v164_table_field_configuration.py`)
  waren überwiegend nur strukturell ("PDF bleibt gültig", keine Inhaltsprüfung) -- ergänzt um
  echte Inhaltsprüfungen (verstecktes Objektadresse-Feld verschwindet tatsächlich, eigene
  Textblöcke/Felder erscheinen tatsächlich, aufgelöster Mitarbeitername erscheint tatsächlich,
  ein deutlich größerer Rand verschiebt den Inhalt auf Folgeseiten tatsächlich nach unten --
  gemessen, nicht nur behauptet). Bewusst auf DATENINHALTE geprüft (Beträge, Namen, Freitext),
  NICHT auf Beschriftungswortlaut -- der neue und der alte Renderer verwenden teilweise
  unterschiedliche Label-Texte (z. B. "Ansprechpartner" vs. "Ansprechp.", "Projektnr." vs.
  "Projekt"), sollen aber irgendwann exakt dieselben Datenprüfungen bestehen, sobald diese
  Dateien selbst auf den neuen Renderer umgestellt werden. Dabei gefundene Eigenart von
  `_extract_pdf_text()` (Content-Stream-Rohbytes, kein PDF-Parser): Nicht-ASCII-Zeichen wie "ö"
  stehen im PDF-Stringliteral als Oktal-Escape `\366`, nicht als eigenes Byte -- eine
  Inhaltsprüfung auf einen umlauthaltigen String muss entweder `latin-1`-kodieren UND den
  Escape selbst nachbilden, oder (einfacher, hier gewählt) auf einen reinen ASCII-Teilstring
  ausweichen.
- **Neuer Router-Test statt nur Funktionsaufrufs**: `test_quote_pdf_endpoint_uses_new_renderer`/
  `test_quote_pdf_layout_preview_endpoint_still_uses_old_renderer`
  (`tests/test_v235_quote_framed_pdf.py`) rufen tatsächlich `GET /api/quotes/{id}/pdf` bzw.
  `.../pdf-layout-preview` über `router_test_client()` auf und unterscheiden per Inhalt (die
  Übertragszeile existiert ausschließlich im neuen Renderer), welcher Renderer tatsächlich
  antwortet -- ein reiner Endpunkt-Registrierungstest hätte den Renderer-Tausch nicht erkannt.
  Ebenso ein direkter, gepatchter Funktionsaufruf-Test für `send_quote_email()`
  (`test_send_quote_email_uses_the_shared_frame_renderer`, `tests/test_v187_quote_email.py`) --
  der vorherige Test dort (`test_send_quote_email_uses_layout_designer_pdf`) hieß zwar so, prüfte
  aber tatsächlich nur "irgendein PDF wurde angehängt", nicht welcher Renderer es gebaut hat
  (echter Fund beim Anfassen dieser Stelle, korrigiert).

### Fehlerbehebung (seit 1.3.14): drei echte Funde an A-2026-0016, einer noch offen

An einem echten, zehnseitigen Angebot gemeldet -- alle drei direkt gegen die
Produktionsdatenbank nachvollzogen, nicht nur vermutet.

- **Übertrag "fehlte" -- tatsächlich ein zweites, eigenständiges Problem.** `Frame.add()`
  platziert jedes von `split()` zurückgegebene Element dort, wo gerade noch Platz ist -- reichte
  nach `carry_out_row` (nur eine Zeilenhöhe reserviert) noch Restplatz, landete `carry_in_row`
  fälschlich AUCH auf der alten Seite statt am Kopf der neuen; die Zeilen bracketen dann keinen
  Seitenumbruch mehr, sie kleben aneinander. `_CarryForwardItemsTable.split()`
  (`app/quote_framed_pdf.py`) fügt jetzt ein `PageBreak()` zwischen beiden ein -- verifiziert,
  dass reportlab das erkennt, auch wenn es aus einem `split()`-Ergebnis stammt, nicht nur aus der
  ursprünglichen Story (`BaseDocTemplate.handle_flowable()` prüft jedes Element unabhängig von
  seiner Herkunft per `isinstance()`). Im ursprünglichen 90-Positionen-Synthetiktest (1.3.13)
  unbemerkt geblieben, weil dort an der Umbruchstelle zufällig kein Spielraum übrig war -- neuer,
  direkter `split()`-Test mit bewusst großzügiger `availHeight` deckt das jetzt gezielt ab. Der
  ursprünglich vermutete Zusammenhang mit Abschnittsgrenzen traf nicht zu.
- **Zwei Doppelungen, beide echte Datenfragen.** Kundenname UND Ansprechpartner sind beim
  betroffenen Kunden identisch ("Wolfgang Rödchen" zweimal) -- `build_quote_framed_pdf()`
  unterdrückt die Ansprechpartner-Zeile jetzt, wenn sie (getrimmt, ohne Groß-/Kleinschreibung)
  dem Kundennamen entspricht. `outro_text`/`outro_text_2` trugen wortgleich denselben
  Schlusssatz -- behoben in der GEMEINSAMEN `build_payment_tax_closing_block()`
  (`app/document_pdf.py`), nicht nur im Angebots-Renderer: `outro_text_2` wird unterdrückt, wenn
  er exakt `outro_text` entspricht. Betrifft dadurch auch `order_pdf.py` (nutzt dieselbe
  Funktion) -- dort bisher nicht beobachtet, aber derselben Gefahr ausgesetzt, kein Grund für
  eine zweite, quote-spezifische Kopie der Prüfung. Ein dritter Verdacht (Kurz-/Langtext einer
  Position scheinbar doppelt, einmal groß, einmal klein) bestätigte sich als reines
  Datenproblem: bei 17 von 25 Positionen dieses Angebots beginnt `long_text` wortgleich mit
  `short_text` (offenbar beim Anlegen hineinkopiert und dahinter weitergeschrieben) -- **nicht
  verändert**, wie ausdrücklich verlangt.
- **Große Leerräume am Seitenende -- Ursache gefunden, in 1.3.15 behoben.** reportlab kann eine
  Tabellenzeile nur als Ganzes umbrechen, nie mitten im Zelleninhalt -- verifiziert direkt am
  reportlab-Quelltext: `Table._splitRows()`s `doInRowSplit`-Zweig splittet ausschließlich rohe,
  mehrzeilige Strings, keine `Paragraph`-Flowables (wie sie hier für Kurz-/Langtext verwendet
  werden). Passte eine Position mit langem `long_text` nicht mehr vollständig auf die restliche
  Seite, wanderte die komplette Zeile (Kopf UND Langtext zusammen) auf die Folgeseite, die alte
  Seite blieb bis zu einem Drittel leer -- per Bildvergleich bestätigt, UND IDENTISCH im alten
  UND im neuen Renderer (kein neu eingeführtes Problem, aber auch im neuen nicht von selbst
  gelöst). Siehe eigener Abschnitt "Zeilenumbruch-Variante für lange Positionstexte" unter
  "Fünfte und letzte Etappe" für die vollständige Behebung.

### Zeilenumbruch-Variante für lange Positionstexte (seit 1.3.15)

Letzter offener Punkt aus 1.3.14 -- Vorschlag vorher abgestimmt, dann genau so gebaut (nicht die
verworfene, aufwendigere Variante mit Eingriff in reportlabs interne Zeilenliste).

- **Jede Position: eine unteilbare Kopfzeile PLUS eine Zeile je Absatz im Langtext.**
  `_build_items_table()` (`app/quote_framed_pdf.py`) baut für jede Position zuerst weiterhin
  genau eine Zeile mit OZ/Kurztext/Menge/EH/EP/GP (bleibt unteilbar, wie gefordert nie vom Preis
  getrennt), gefolgt von einer eigenen Tabellenzeile je durch `\n` getrenntem, nicht-leerem
  Absatz im Langtext (leere Zeilen werden übersprungen). Ein Langtext ganz ohne `\n` bleibt eine
  einzige Fortsetzungszeile -- bekannte, akzeptierte Lücke, siehe „Bekannte, bewusst offene
  Punkte" für die Begründung, warum die aufwendigere Alternative (echte Zeilen aus einem
  gelayouteten `Paragraph` extrahieren) verworfen wurde.
- **Trennlinie nur am Ende des GESAMTEN Blocks.** Vorher stand die graue Trennlinie
  (`LINEBELOW`) blanko auf jeder Zeile -- bei mehreren Zeilen je Position hätte das jede
  Fortsetzungszeile wie eine eigene, neue Position aussehen lassen. Der Standard ist jetzt
  `LINEBELOW` unsichtbar auf allen Zeilen, gezielt wieder eingeschaltet nur für den Spaltenkopf
  UND die jeweils LETZTE Zeile eines Positions-Blocks (Kopfzeile selbst, wenn kein Langtext, oder
  ihre letzte Fortsetzungszeile) -- exakt die vom Nutzer angefragte Prüfung, ob die bestehende
  Trennlinie das schon leistet (tat sie nicht, unverändert übernommen hätte sie täuschend gewirkt).
- **Fortsetzungs-Kennzeichnung nur, wenn ein Umbruch tatsächlich mitten in einer Position
  landet.** `_CarryForwardItemsTable` bekommt eine neue, parallel zu `row_cumulative` geführte
  `row_kind`-Liste (`("header"|"continuation"|"title", position_label)` je Körperzeile). Landet
  die erste Zeile von `bottom` (nach einem Split) auf einer `"continuation"`-Zeile, schiebt
  `split()` einen kleinen, kursiven Hinweis `_build_continuation_marker_row()`
  ("(Fortsetzung zu Position {OZ})") davor -- dieselbe Spaltenaufteilung wie eine
  Fortsetzungszeile selbst (leere OZ-Spalte), damit die Fluchtlinie übereinstimmt. Erscheint NUR
  dann, nicht auf jeder Fortsetzungszeile (sonst überflüssiges Rauschen auf den meisten Seiten).
- **Reduziertes Zellenpolster für Fortsetzungszeilen, sonst wächst das Dokument statt zu
  schrumpfen.** Erster Messversuch ohne diese Korrektur: A-2026-0016 wuchs von 11 auf 12 Seiten
  -- das volle 4pt/4pt-Polster kam vorher nur EINMAL pro Position vor (ein einziger mehrzeiliger
  Paragraph mit normalem Zeilenabstand zwischen den Zeilen), jetzt einmal PRO Absatz. Auf 0pt/1pt
  reduziert für alle `continuation_rows` -- damit sinkt die Seitenzahl auf 10.
- **Auswirkung auf die Übertragslogik: minimal.** Fortsetzungszeilen tragen `running`
  (die laufende Netto-Summe) unverändert weiter, exakt wie die bereits bestehenden Titelzeilen es
  tun -- keine Änderung an `_CarryForwardItemsTable.split()`s Kernlogik (Höhenreservierung,
  PageBreak zwischen Übertrags-Zeilen), nur eine zusätzliche, optionale Zeile VOR `bottom`, wenn
  `row_kind` das verlangt.
- **Nachgemessen, nicht nur behauptet** (`pypdfium2`-Zeichenboxen, tiefste Textposition je Seite
  ab 60mm von unten, um Fußzeile/Briefpapier auszuklammern -- die letzte Seite eines Dokuments
  hat strukturbedingt immer Leerraum nach den Summen/Schlusstexten und wurde deshalb aus dem
  Vergleich ausgenommen): vorher vier Seiten mit 21–31 % Leerraum der Seitenhöhe (deckt sich mit
  der ursprünglichen Meldung "über ein Drittel"), nachher eine einzige verbleibende Seite mit
  7 %. Zusätzlich ein eigens gebauter, absichtlich langer Fließtext (Ende-zu-Ende-Test) bestätigt,
  dass die Fortsetzungs-Kennzeichnung zuverlässig genau dort erscheint, wo der Umbruch tatsächlich
  mitten in einer Position landet, nicht öfter und nicht seltener.
- **Tests**: `tests/test_v235_quote_framed_pdf.py` -- Zeilenanzahl/`row_kind` für Langtext mit/
  ohne `\n` (inkl. des bewusst akzeptierten Ein-Zeilen-Falls), ein direkter `split()`-Test mit
  bewusst knapper `availHeight`, der den Umbruch gezielt mitten in die Fortsetzungszeilen einer
  einzigen Position zwingt und die Kennzeichnung im Rückgabewert prüft, sowie ein
  Ende-zu-Ende-Test über einen echten, mehrseitigen Umbruch.

### Fünf Feinheiten (seit 1.3.16): Ränder, Ausrichtung, Spaltenbreite, Beschriftung

An A-2026-0016 beobachtet, alle fünf umgesetzt -- kein neuer, eigener Fehlerfund wie 1.3.14,
sondern gezielte Nacharbeit an einem bereits produktiv laufenden Renderer.

- **Ränder neu gemessen statt geschätzt.** Unterer Rand (Seite 1 UND Folgeseiten) 50mm → 32mm:
  echter Fußbereich des Briefbogens endet bei 28mm (Pixelanalyse wie bei der Kopfgrafik in
  1.3.12/1.3.15, +4mm Sicherheitsspanne) -- ein erster Messversuch mit einem zu lockeren
  "fast-weiß"-Schwellwert fand fälschlich noch bei 80mm Inhalt (tatsächlich nur ein extrem
  blasser Papierton, kein Druck) und wurde vor dem Vorschlag verworfen, nicht blind übernommen.
  Oberer Rand Seite 1 17mm → 25mm -- **vorher geprüft, ob dies dieselbe, für alle Dokumenttypen
  geteilte Einstellung ist wie vom Nutzer angenommen: nein.** "quote" behält seine eigenen,
  unabhängigen Randzeilen (`resolve_shared_document_type()`, `app/document_type_fallback.py`,
  lässt "quote" nie am "default"-Rückfall teilnehmen, den Mahnung/Rechnung/Auftrag nutzen) --
  eine Änderung hier wirkt sich auf die anderen drei NICHT aus, es gab dafür keinen sinnvollen
  Vorher-Nachher-Vergleich zu zeigen. Zusätzlich geprüft, ob überhaupt eine echte Kollision
  vorlag: nein -- Absenderzeile (x=18-88mm) und die bis 30,8mm reichende Kopfgrafik (nur bei
  x=97-113mm) liegen in unterschiedlichen Spalten, kein Pixel-Overlap. Die 25mm sind eine
  bewusste Weißraum-Entscheidung, keine Fehlerbehebung. Beide Werte über `update_margins()`
  gesetzt (kein rohes SQL) -- vorher am echten Angebot probeweise gerendert (set → rendern →
  zurücksetzen, Rücksetzung durch erneutes Lesen bestätigt) und erst nach Zustimmung endgültig
  übernommen.
- **Menge/EH/EP/GP zentriert** (`app/quote_framed_pdf.py::_build_items_table()`, inkl.
  Spaltenköpfe) -- fachlicher Hinweis mitgegeben, wie verlangt: rechtsbündig ist bei
  Geldbeträgen üblich (Dezimalstellen stehen dann untereinander), trotzdem wie gewünscht als
  Betreiberentscheidung umgesetzt.
- **"Pos."-Spalte verschmälert (23mm → 15mm), Gewinn vollständig an "Leistung".** Längste
  tatsächlich in der Datenbank vorkommende Positionsnummer: 7 Zeichen (z. B. "01.0030"), bei
  Helvetica 8pt ~11mm breit -- 15mm deckt das mit Zellenpolster und Sicherheitsspanne ab. Da
  "Leistung" als `content_width` minus Summe der übrigen Spalten berechnet wird
  (`ITEMS_COL_WIDTHS_MM`), fließt die Differenz automatisch vollständig dorthin: bei quote's
  176mm-Satzspiegel von 73mm auf 81mm, ohne eigene Rechnung im Code. Nur für das Angebot
  geändert -- Auftrag/Rechnung behalten ihre eigene, unveränderte 23mm-Breite, das war nicht
  angefragt (der Kommentar über `ITEMS_COL_WIDTHS_MM` hält diesen bewussten Unterschied fest,
  damit er nicht wie ein Versehen wirkt).
- **Spaltenüberschrift "OZ" → "Pos.", projektweit vereinheitlicht.** `order_pdf.py` (Auftrag)
  trug tatsächlich dieselbe Überschrift "OZ" und wurde mitgeändert. `invoice_pdf.py` (Rechnung)
  zeigte dagegen gar nicht "OZ", sondern bereits "Position" (seit 1.3.9) -- der ursprünglich
  angenommene Vergleichspunkt ("dieselbe Überschrift wie das Angebot") traf für die Rechnung
  also nicht zu, das eigentlich verlangte Ziel ("alle Dokumente gleich beschriftet") aber schon:
  ebenfalls auf "Pos." vereinheitlicht. `app/quote_layout_pdf.py` (der alte, nur noch als
  Vergleichsansicht erreichbare Renderer) und `app/quote_pdf.py` (ohnehin ohne produktiven
  Aufrufer) bleiben bei "OZ" -- entfallen mit dem Rest des alten Renderers, siehe Liste der
  Aufräumschritte, kein Grund, dort noch etwas anzufassen. `tests/test_v231_*`/`test_v232_*`
  (Rechnung/Auftrag, Fluchtlinien-Messungen) nutzten "Position"/"OZ" als Text-Ankerpunkt für die
  Randmessung -- auf "Pos." umgestellt, die eigentliche Prüfung (linke/rechte Fluchtlinie)
  bleibt unverändert.

### Währung in den Spaltenkopf, Menge/EH vor Leistung, engerer Kopfbereich (seit 1.3.17)

Drei Punkte, alle auch an Auftrag und Rechnung nachgezogen ("gleiche Beschriftung in allen
Dokumenten", wie zuvor bei "Pos." in 1.3.16).

- **Punkt 1 – Währung raus aus den Wertespalten.** "288,75 EUR" in jeder Zeile → "288,75", die
  Einheit steht seither nur noch im Spaltenkopf ("EP/EUR"/"GP/EUR") -- Vorbild das dem Betreiber
  bekannte Vergleichsdokument. Neue Hilfsfunktion `money_bare()` (`app/document_pdf.py`) neben
  dem bestehenden `money()`; der Summenblock bleibt bei `money()` mit Währung, da sie dort nur
  wenige Male auftaucht. Die Rechnung hatte für dieselbe Spalte abweichend "Betrag" statt "GP" --
  im selben Zug auf "GP/EUR" vereinheitlicht (eigene Entscheidung, nicht wörtlich vom Nutzer so
  benannt: derselbe fachliche Wert wie bei Angebot/Auftrag, "Betrag" war nur eine ältere, nie
  angeglichene Eigenbezeichnung der Rechnung). Die Übertragszeile des Angebots (laufende Summe
  über Seitenumbrüche, seit 1.3.15) liegt in der GP-Spalte und folgt deshalb ebenfalls
  `money_bare()` -- ebenfalls eine eigene, nicht wörtlich angefragte Konsistenzentscheidung.
- **Punkt 2 – Menge/EH vor die Leistung.** Neue Spaltenreihenfolge Pos., Menge, EH, Leistung,
  EP/EUR, GP/EUR (vorher Pos., Leistung, Menge, EH, EP, GP) -- wieder nach dem
  Vergleichsdokument, dessen gemeinsame Kopfzelle "Menge Einh." hier per `SPAN` über beide
  Spalten übernommen wird. Menge rechtsbündig, EH linksbündig mit knappem Zwischenpolster direkt
  daneben (statt des bisherigen vollen Standard-Zellenpolsters), damit z. B. "1,25 m²" wie eine
  zusammengehörige Einheit wirkt. Betrifft `app/quote_framed_pdf.py`, `app/order_pdf.py`,
  `app/invoice_pdf.py` gleichermaßen; Fortsetzungszeilen langer Positionstexte im Angebot
  verankern ihren Text weiterhin unter der (jetzt verschobenen) Leistungsspalte, nicht unter Pos.
- **Kopfbereich: Absenderzeile enger an die Anschrift.** Der `Spacer` zwischen der kleinen,
  unterstrichenen Absenderzeile (DIN 5008) und der Empfängeranschrift darunter stand bei 2mm --
  zu großzügig, beide sollten als ein Block wirken. Auf 0,8mm reduziert, direkt in
  `build_din5008_header_block()` (`app/document_pdf.py`) -- betrifft dadurch automatisch alle
  vier Dokumenttypen, die diesen gemeinsamen Baustein nutzen (Mahnung, Rechnung, Auftrag,
  Angebot), wie bei jeder Änderung an diesem geteilten Baustein zu bedenken.
- **Tests**: bestehende Geometrie-Tests an die neue Spaltenreihenfolge angepasst (Position der
  Fortsetzungs-Markierung verschob sich von Spalte 1 auf Spalte 3, "Leistung" beginnt jetzt
  spürbar weiter rechts). Der bereits bestehende Mindestabstand-Test Menge/EH in Rechnung/Auftrag
  hing an einer festen unteren Grenze von 1,0mm (bemessen für den alten, großzügigen
  Standard-Zellenabstand) -- bewusst auf einen kleineren, aber weiterhin sichtbaren Wert gesenkt,
  passend zum neuen, absichtlich engen Erscheinungsbild, nicht nur um den Test grün zu bekommen.
  Mehrere neue Tests ergänzt (Währung nur im Kopf/Summenblock, Spaltenreihenfolge, Menge/EH-Abstand
  je Dokumenttyp, verkleinerter Absenderzeilen-Abstand). `pytest` vollständig grün (978/978).

**Im selben Zug untersucht, noch ohne Codeänderung (Nutzer wollte den Vorschlag vor der
Umstellung sehen):** eine gemeldete Beobachtung "Randeinstellungen wirken nicht" gegen die ganze
Kette geprüft (DB-Schreibpfad, `document_frame.py`-Lesepfad, 1.3.6-Rückfallmechanismus). Ergebnis
und die daraus in 1.3.18 gezogenen Entscheidungen siehe „Bekannte, bewusst offene Punkte" unten
(Abschnitt "Randeinstellungen der Einstellungsseite betreffen 'quote' nicht").

### Randkorrektur "default" (seit 1.3.18/1.3.19)

Drei Entscheidungen zur 1.3.17-Untersuchung -- Details siehe „Bekannte, bewusst offene Punkte"
unten, hier nur die Kurzfassung: **`bottom_mm`** des geteilten Satzes (Mahnung/Rechnung/Auftrag/
Einsatzbericht) auf `32mm` korrigiert (wie "quote", Code-Standard UND reale DB-Zeile über
`update_margins()`) -- der generische 20mm-Wert unterschritt den real bedruckten Fußbereich
desselben Briefpapiers. **`top_mm`** in 1.3.18 zunächst nur vermessen/vorgeschlagen, in 1.3.19
auf Anweisung ebenfalls übernommen: `25mm` (Seite 1) / `40mm` (Folgeseiten), wie "quote" --
wieder Code-Standard UND reale DB-Zeile über `update_margins()`. **Bewusst in Kauf genommene
Nebenwirkung**: der reduzierte 25mm-Rand für Seite 1 unterschreitet die Unterkante des
generischen, gezeichneten `logo`-Bausteins (30mm) -- der zugehörige Regressionstest
(`test_reminder_default_company_header_and_logo_do_not_overlap_default_frame`,
`tests/test_v226_document_frame.py`) prüft diese Geometrie seit 1.3.19 nur noch für
"continuation" (40mm, klart sicher). Kein neues Risiko, sondern dieselbe, bereits seit der
eigenen 1.3.16-Randkorrektur für "quote" unkommentiert bestehende Situation (dort ebenfalls
top_mm=25 gegen ein logo mit Unterkante 30mm) -- unschädlich, solange `logo`/`company_header`
auf `visible=False` bleiben (Standard seit 1.3.2/1.3.8). Ein Admin, der sie OHNE eigenes
Briefpapier aktivieren will, muss den oberen Rand für Seite 1 selbst wieder vergrößern. An je
einem echten Dokument pro Typ geprüft (siehe unten "Randkorrektur"-Bekannte-Punkte für die
Details, inkl. der einen zusätzlichen Seite beim Einsatzbericht durch die bottom_mm-Korrektur).
**Einstellungsseite** bekommt einen deutlichen Hinweis, für welche Dokumenttypen sie gilt.
**Zusammenführung** (quote nimmt am "default"-Rückfall teil) auf die Aufräumliste gesetzt, als
EIN Schritt zusammen mit dem Entfernen von `quote_layout_pdf.py`.

Damit ist der in `docs/bestandsaufnahme_pdf.md` skizzierte PDF-Umbau (Rahmen, Kopfbereich,
Zusammenführung der Layout-Einstellungen, alle fünf Renderer auf `render_framed_pdf()`,
Feinschliff an Angebot/Auftrag/Rechnung) abgeschlossen -- offen bleibt nur noch die eine, oben
verlinkte Aufräumliste (Entfernen von `quote_layout_pdf.py` + Zusammenführung von "quote" in den
"default"-Satz) sowie die einzeln vermerkten "Bekannte, bewusst offene Punkte".

### Referenz-PDFs (`docs/referenz-pdf/`, seit 1.3.19)

Je ein PDF pro Dokumenttyp (Angebot, Auftrag, Rechnung, Mahnung, Einsatzbericht), aus echten
Produktionsdaten erzeugt, Dateiname mit Version und Datum
(`{typ}_{nummer}_v{version}_{datum}.pdf`, z. B. `angebot_A-2026-0001_v1.3.19_2026-09-12.pdf`).

**Zweck**: fester Bezugspunkt für den gerade abgeschlossenen PDF-Umbau -- wenn jemand am Rahmen,
Kopfbereich oder den Positionstabellen etwas ändert, kann er das Ergebnis gegen diese Dateien
vergleichen, statt aus dem Gedächtnis zu urteilen, ob eine Änderung wirklich nur das betrifft,
was beabsichtigt war. Kein automatisierter Vergleich (kein Snapshot-Test) -- bewusst als
Nachschlage-/Vergleichsmaterial für einen Menschen gedacht, das sich auch optisch (Layout,
nicht nur Textinhalt) prüfen lässt.

**Pflege**: werden NICHT bei jeder Änderung neu erzeugt (kein Teil von `pytest`/CI) -- nur bei
einer bewussten, gewollten Layoutänderung am gemeinsamen Rahmen oder einem der fünf Renderer
manuell neu generieren (Skript-Ansatz wie bei der Erstellung: die jeweilige `build_*_pdf()`-
Funktion direkt gegen ein reales Datenobjekt aufrufen, siehe die fünf Aufrufe in dieser
CLAUDE.md-Historie als Vorbild) und unter demselben Namensschema mit der dann aktuellen
Version/dem aktuellen Datum neu ablegen -- alte Stände bewusst NICHT löschen, sie dokumentieren
den Verlauf. Ein Datei-Diff/visueller Vergleich vor dem Ablegen macht sichtbar, was sich durch
die Änderung wirklich verändert hat.

### Aufräumen nach dem PDF-Umbau (seit 1.3.20)

Der alte, positionsbasierte Angebots-Renderer und alles, was nur noch wegen ihm existierte, ist
entfernt -- in dieser Reihenfolge: erst die Zusammenführung (Schritt 2), dann das Löschen
(Schritt 3), da `quote_layout_pdf.py` bis dahin die quote-eigenen Zeilen noch aktiv las.

**Schritt 1 (Prüfung der 1.3.13-Liste)**: alle sechs ursprünglich genannten Positionen bestätigt.
Zwei zusätzliche, nicht auf der Liste stehende Funde: `PUT .../background/repeat` (nur von
`document_layout_editor.html` genutzt) und das `DocumentTableField`-Modell/die zugehörige
Tabelle (nicht nur die Geschäftslogik-Datei) -- beide mit entfernt, siehe unten.

**Schritt 2 (Zusammenführung)**: `resolve_shared_document_type()`
(`app/document_type_fallback.py`) kennt "quote" nicht mehr als Sonderfall -- fällt wie jeder
andere Dokumenttyp auf "default" zurück, sofern keine eigene Zeile existiert. Migration
`5c8715dba230` löscht die zuvor eigenständigen "quote"-Zeilen in `document_layout_blocks`/
`document_layout_backgrounds`/`document_page_margins` (downgrade() stellt den zuletzt echten
Stand wieder her, nicht nur Code-Standardwerte). `WRITABLE_DOCUMENT_TYPES`
(`app/routers/document_layout.py`) schrumpft auf `{"default"}` -- ohne diese Änderung hätte ein
künftiger Schreibversuch auf "quote" lautlos eine neue, eigene Zeile angelegt und den Rückfall
für "quote" erneut abgeschaltet. Die verwaiste Briefpapier-Datei
(`52c12111ef7a4994b565e30f768c4a09.png`) wurde nach Pixelvergleich gegen "default"s eigene Datei
(mittlere Kanalabweichung < 0,5 von 255 -- reine JPEG-Kompressionsartefakte, dieselbe Vorlage)
von der Festplatte gelöscht. `suppress_drawn_blocks` (`app/document_frame.py`,
`app/quote_framed_pdf.py`) entfällt ersatzlos -- "quote"s `company_header`/`logo` sind jetzt
(über den Rückfall) dieselben `visible=False`-Zeilen wie bei jedem anderen Dokumenttyp, der
Parameter wird nicht mehr gebraucht. Ein neuer Test
(`test_quote_pdf_identical_whether_quote_has_its_own_rows_or_falls_back_to_default`,
`tests/test_v235_quote_framed_pdf.py`) simuliert beide Zustände nebeneinander (eigene
"quote"-Zeilen vs. reiner "default"-Rückfall, sonst identische Konfiguration inkl. der
1.3.13-`suppress_drawn_blocks`-Ersatzeinstellung `company_header=False`) und vergleicht
Textextraktion + Seitenzahl -- identisch. Einzige real geprüfte Abweichung: `left_mm`/`right_mm`
unterschieden sich geringfügig (quote 17/17, default 18/16) -- Gesamtbreite bleibt mit 176mm
identisch (beide Werte summieren sich auf 34mm), nur ein nicht messbarer 1mm-Versatz des
gesamten Inhaltsblocks nach rechts.

**Schritt 3 (Löschen)**: `app/quote_pdf.py`, `app/quote_layout_pdf.py`,
`app/templates/document_layout_editor.html`, `app/document_table_fields.py` vollständig entfernt.
Zusätzlich (über die ursprüngliche Liste hinaus): `DocumentTableField`-Modell aus `app/models.py`
und die zugehörige Tabelle (Migration `0064c87051aa`, downgrade() stellt auch die zuletzt
tatsächlich vorhandenen 35 Zeilen wieder her -- darunter eine echte Anpassung im Firmenkopf,
"nur Firmenname sichtbar", passend zu vorgedrucktem Briefpapier); die fünf zugehörigen Router-
Endpunkte samt der jetzt ungenutzten Schemas (`DocumentTableFieldOut`/`-Update`,
`DocumentTableCustomFieldCreate`); die `custom_text`-ANLEGEN/LÖSCHEN-Endpunkte (`POST
.../{document_type}/blocks`, `DELETE .../blocks/{block_id}`) samt `create_custom_text_block()`/
`delete_custom_text_block()` in `app/document_layout.py` (0 reale `custom_text`-Zeilen in der
Produktionsdatenbank vor dem Löschen bestätigt) -- `PUT .../blocks/{block_id}` selbst BLEIBT,
da settings.html ihn generisch für die Sichtbarkeit/Position der vier verbleibenden
Rahmen-Bausteine nutzt, nicht nur für `custom_text`. Der `/document-layout-editor`-Seitenroute
(`app/routers/pages.py`) und der Menüpunkt in `settings.html` sind ebenfalls entfernt; die dort
seit 1.3.18/1.3.19 stehenden Hinweistexte ("Angebot hat eigene Werte") waren durch die
Zusammenführung ohnehin gegenstandslos geworden und wurden auf "gilt für alle Dokumenttypen"
korrigiert.

`app/routers/quotes.py`: `GET /api/quotes/{id}/pdf-layout-preview` entfernt. In
`app/templates/quote_editor.html`: Button "Vergleichsansicht: alter Renderer" und Checkbox
"Vergleichsansicht mit Briefkopf" samt `openPdfLayoutPreview()` entfernt -- Entscheidung
gegen Beibehalten (Option 1 vs. 2, vom Nutzer zur Wahl gestellt): der alte Renderer hätte für
eine reine Vergleichsansicht ohnehin fast vollständig erhalten bleiben müssen
(`quote_layout_pdf.py` UND `document_table_fields.py` UND die zugehörigen Tabellen), was der
eigentlichen Aufräum-Absicht widersprochen hätte. Referenz-PDFs (siehe oben) sind dafür kein
Ersatz (sie zeigen den neuen, nicht den alten Stand), aber `backup_windows.ps1`-Stände bleiben
als Notausgang, falls der alte Code je wieder gebraucht würde.

**Testfolgen**: `tests/test_v159_quote_layout_pdf.py`, `tests/test_v164_table_field_configuration.py`
und `tests/test_v160_layout_editor_ui.py` (100% renderer-/editor-spezifisch, keine generische
Prüfung darin) vollständig gelöscht -- letzterer erst nach dem ersten vollständigen Testlauf
gefunden (stand nicht auf der ursprünglichen Liste, testete ausschließlich
`document_layout_editor.html`). `tests/test_v158_pdf_layout_foundation.py`,
`tests/test_v167_pagination.py`, `tests/test_v169_page_margins.py` gekürzt: generische
Geschäftslogik-Tests (`ensure_default_layout()`, `update_layout_block()`,
`reset_layout_to_default()`, `set_background_repeat()`, `ensure_default_margins()`,
`update_margins()`, `reset_margins_to_default()`) bleiben erhalten, nur auf `document_type=
"default"` statt `"quote"` umgestellt (seit 1.3.20 der einzige isoliert -- ohne Rückfall --
beschreibbare Typ). `test_ensure_default_margins_matches_previous_hardcoded_values` (test_v169)
ist ersatzlos entfallen: seine Prämisse (ein Dokumenttyp OHNE jede Überschreibung, rein
generische `DEFAULT_MARGINS`-Werte) hat seit der Zusammenführung keinen realen Anwendungsfall
mehr -- jeder Typ ohne eigene Zeile fällt auf "default" zurück, und "default" selbst trägt
eigene, gegen das echte Briefpapier vermessene Überschreibungen. `tests/test_v060_lv_editor.py`s
beiläufiger `build_quote_pdf()`-Aufruf auf `build_quote_framed_pdf()` umgelenkt. Insgesamt
978 → 904 Tests (nach Abzug der neu hinzugekommenen: netto mehr als drei Dateien vollständig
entfallen) -- `pytest` vollständig grün.
