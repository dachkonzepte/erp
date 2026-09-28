# Breadcrumb/Direkteinstieg/Katalogauswahl, Umbau Projektliste & Projektmappe

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Breadcrumb & Spaltenkopf-Ausrichtung (seit 1.3.23)

Zwei von sechs aus dem laufenden Betrieb gemeldeten Punkten, unabhängig von den anderen vier
umgesetzt.

- **Breadcrumb Kunde → Projekt → [Angebot|Auftrag|Auftrag → Rechnung].** Geprüft, was die drei
  Seiten bisher an Rück-Navigation hatten: `order.html` einen einzelnen "← Projektmappe"-Link
  (`/projects/{id}#sec-orders`), `invoice_detail.html` einen einzelnen "← Auftrag"-Link
  (`/orders/{id}`), `quote_editor.html` GAR NICHTS. Keine der drei zeigte den Kunden. Neu: ein
  `<div class="breadcrumb" id="breadcrumb">` mit denselben CSS-Klassen/derselben Optik wie
  `property.html`/`roof_area.html` (1.2.18) -- Zwischenebenen als `<a>`, aktuelle Seite als reiner
  Text, per `renderBreadcrumb()` aus den bereits geladenen Kunden-/Projektdaten aufgebaut. Die
  bereits bestehenden Einzel-Links bleiben zusätzlich bestehen (unterschiedlicher Zweck: gezielter
  Rücksprung vs. vollständiger Pfad).
  - `order_to_dict()`/`OrderOut` hatten `customer_id`/`project_id`/`project_number` bereits seit
    1.2.20 (dort für die Breadcrumb auf `service_reports.html` ergänzt) -- `order.html` brauchte
    dafür keine Backend-Änderung, nur die Template-Ergänzung.
  - `quote_to_dict()`/`QuoteOut` bekommen neu `customer_id` (`quote.project.customer_id`) --
    `project_id`/`project_number`/`customer_name` waren schon vorhanden.
  - `invoice_to_dict()`/`InvoiceOut` bekommen neu `order_number`/`project_id`/`project_number`/
    `customer_id` (alle über `invoice.order`/`invoice.order.project` aufgelöst) -- vorher kannte
    der Rechnungs-Dict nur die nackte `order_id`, keinen Weg zu Projekt oder Kunde.
  - **Rechnung bekommt bewusst eine vierte Ebene** (Kunde → Projekt → **Auftrag** → Rechnung,
    nicht nur drei wie bei Angebot/Auftrag): ihr tatsächlicher fachlicher Elternknoten in der
    Kette `Customer → Project → Quote → Order → Invoice → Reminder` ist der Auftrag, nicht direkt
    das Projekt, und `invoice_detail.html` hatte vorher (abgesehen vom einzelnen "← Auftrag"-Link)
    überhaupt keinen Weg zurück. Angebot/Auftrag bleiben bei drei Ebenen (Kunde → Projekt →
    aktuelle Seite), exakt das vom Nutzer vorgegebene Muster.
  - **Mahnung hat keine eigene Seite** -- geprüft (`app/routers/pages.py`, kein
    `/reminders/{id}`-Route): Mahnungen leben ausschließlich in `mahnwesen.html` (Liste) und
    eingebettet in `invoice_detail.html` (Mahnwesen-Karte). Die neue Rechnungs-Breadcrumb deckt
    diesen Fall deshalb automatisch mit ab, kein eigener Punkt nötig.
- **"EP/EUR"/"GP/EUR"-Kopfzeile jetzt tatsächlich über den Werten.** Im Angebot
  (`quote_framed_pdf.py`) bereits seit 1.3.16 korrekt zentriert, Kopfzeile inklusive
  (`("ALIGN", (4, 0), (5, -1), "CENTER")`, Zeile 0 = Kopfzeile ausdrücklich mit erfasst). Bei
  Auftrag (`order_pdf.py`) und Rechnung (`invoice_pdf.py`) betraf die entsprechende `ALIGN`-Regel
  dagegen nur `(4,1)` bis `(5,-1)` -- Zeile 0 blieb außen vor und fiel dadurch auf reportlabs
  `Table`-Standard LEFT zurück, während die Werte darunter RECHTS standen. Das ist nicht nur
  "nicht zentriert", sondern Kopf und Wert standen an zwei unterschiedlichen Rändern derselben
  Spalte. Nachgemessen (`pypdfium2`-Zeichenboxen, `tests/test_v227_din5008_header_block.py::_char_x_range_mm`,
  Beispielposition 100 × 50,00 €): Kopf-/Wert-Mittelpunkt lagen beim Auftrag 9,9mm (EP) bzw.
  11,9mm (GP) auseinander, bei der Rechnung 6,9mm bzw. 11,9mm. Behoben durch dieselbe Regel wie im
  Angebot (`("ALIGN", (4,0), (5,-1), "CENTER")` statt `("ALIGN", (4,1), (5,-1), "RIGHT")`) --
  danach liegt der Versatz in allen drei Dokumenttypen unter 0,1mm (Restwert allein durch
  unterschiedliche Zeichenbreiten der jeweiligen Zahl, kein Ausrichtungsfehler mehr).
- **Einsatzberichte-Spalte in der Projektübersicht, geprüft statt vermutet.** `project_folder.html`s
  `renderOrders()` hat die seit 1.2.20 dokumentierte "Einsatzberichte"-Spalte tatsächlich im Code
  (`maintenanceModuleEnabled`-Gate, Link auf `/orders/{id}/service-reports`,
  `count_reports_for_order()` korrekt bis zum Endpunkt durchverdrahtet). Gegen die echte
  Produktionsdatenbank geprüft: Modul `wartungen` aktiv (kein Eintrag in `enabled_modules` --
  Opt-out-Default greift), 4 Einsatzberichte über 3 der 6 Aufträge verteilt, alle Zuordnungen
  korrekt. Kein Fehler gefunden, keine Änderung vorgenommen.

## Direkteinstieg, Katalogauswahl, Pauschale Abschlagsrechnung (seit 1.3.24)

Drei weitere Punkte aus dem laufenden Betrieb -- alle drei erst als Befund berichtet, dann nach
Rückmeldung gebaut.

- **Direkteinstieg vom Dashboard zu Aufgabe/Anfrage/Abwesenheitsantrag.** Befund: `tasks.html`
  kannte keinen Weg, eine bestimmte Aufgabe direkt zu öffnen (kein Query-Parameter, keine
  Analogie zu `?report=`); dieselbe Lücke hatten die "Wiedervorlage"-Zeilen (`/inquiries`) und
  "Freigabe"-Zeilen (`/time-backoffice#absences`, immerhin schon mit korrektem Tab) im selben
  Dashboard-Widget. Gebaut, alle drei nach dem `?report=`-Muster aus 1.2.22:
  - `tasks.html` (`?task=<id>`) und `inquiries.html` (`?inquiry=<id>`) rufen nach dem initialen
    Laden `openEditor(id)`/`openInquiry(id)` auf (dieselben Funktionen, die auch ein Klick auf die
    Karte/Zeile auslöst) -- Editor öffnet sich, Seite scrollt dorthin. Kein Treffer im geladenen
    Datensatz (z. B. Admin-Filter auf eine andere Person): stiller No-op, kein Fehler, exakt wie
    beim Vorbild `?report=`.
  - `time_backoffice.html` (`?absence=<id>`) markiert die Zeile in der Antragsliste
    (`#absenceRows [data-abs-id="<id>"]`, neue CSS-Klasse `.setting-row.highlight`) und scrollt
    dorthin -- **ohne** die bestehende Hash-basierte Tab-Auswahl (`init()`s `location.hash`)
    anzufassen, wie ausdrücklich verlangt. Der Dashboard-Link setzt deshalb beides zusammen:
    `?absence=<id>#absences`. `absCard()` rendert denselben Antrag ggf. ZWEIMAL (Dashboard-Tab
    UND vollständige Antragsliste) -- ein `id`-Attribut wäre dort doppelt und
    `getElementById()` hätte die falsche (verborgene) Kopie gefunden; ein `data-abs-id`-Attribut
    plus gezielter Selector auf `#absenceRows` (die tatsächliche Antragsliste) umgeht das.
  - **Bewusst drei eigene, kleine Umsetzungen statt eines gemeinsamen JS-Bausteins** (Frage war
    ausdrücklich gestellt): das einzig echte wiederverwendbare Stück ist eine Zeile
    (`Number(new URLSearchParams(location.search).get(name))`) -- was danach mit der gefundenen
    id passiert, unterscheidet sich an allen drei Stellen (Editor öffnen + scrollen / nur
    markieren + scrollen ohne Tab-Wechsel), ein gemeinsamer Baustein hätte diese Verzweigung per
    Callback ohnehin an jeder Stelle einzeln parametrisieren müssen -- keine echte Ersparnis
    gegenüber der Duplikation einer einzigen, offensichtlichen Zeile. Anders als `_debounce.html`
    (echte, nicht-triviale Timer-/Zustandslogik, die es sich lohnt, nicht zu wiederholen) fehlt
    hier die Komplexität, die eine Include-Datei rechtfertigen würde. Arbeitsvorbereitung/Akute
    Mängel bleiben unverändert auftragsbezogen verlinkt (dort ist "der Auftrag" bereits die
    richtige Ebene, kein Duplikat desselben Problems).
- **Katalog-Dropdown im Angebotseditor.** Befund widerlegte die ursprüngliche Vermutung ("ein
  Katalog fest verwendet"): `quote_editor.html` lud `GET /api/services` bisher OHNE
  `catalog_id`-Parameter -- alle Kataloge wurden ungefiltert zusammen durchsucht, ohne dass
  irgendwo sichtbar war, aus welchem Katalog ein Treffer stammt. Der Endpunkt kannte
  `catalog_id` server-seitig bereits (nur ungenutzt von der Oberfläche), `GET /api/catalogs`
  existierte ebenfalls schon. Gebaut: neues `<select id="catalogFilter">` über dem Suchfeld,
  befüllt aus `GET /api/catalogs`, "Alle Kataloge" als zusätzliche, erste Option (= bisheriges
  Verhalten, wer es gewohnt ist, verliert nichts). Vorbelegung: zuletzt gewählter Katalog
  (`localStorage`, Schlüssel `quoteEditorLastCatalogId`, je Browser wie das Theme) oder, falls
  keiner gemerkt/nicht mehr vorhanden, der erste aus der Liste. Filterung passiert bewusst
  CLIENTSEITIG in `renderCatalog()` (zusätzlich zur bereits bestehenden Textsuche) statt über
  einen erneuten Server-Request mit `catalog_id` -- alle Leistungen sind nach dem initialen Laden
  ohnehin schon vollständig im Speicher, ein Roundtrip pro Auswahl brächte keinen Vorteil; der
  serverseitige Parameter bleibt dafür unverändert nutzbar (siehe Test
  `test_list_services_catalog_id_filter_still_works`). `ServiceListOut`/`list_services()`
  bekommen dafür `catalog_id`/`catalog_name` (`Service.catalog` per `selectinload`
  mitgeladen, keine zusätzliche Abfrage je Zeile) -- jeder Treffer zeigt seinen Katalognamen
  darunter, damit zwei ähnliche Leistungen aus unterschiedlichen Katalogen bei "Alle Kataloge"
  unterscheidbar bleiben. Geprüft, ob dieselbe Einschränkung anderswo besteht, wo Leistungen
  ausgewählt werden: nein -- `quote_editor.html` ist die einzige Stelle im Projekt mit einer
  Leistungssuche (Aufträge entstehen ausschließlich durch Beauftragung eines Angebots, keine
  eigene Suche).
- **Position bei pauschaler Abschlagsrechnung.** Befund: `create_abschlag_pauschal()` legte
  ausschließlich `Invoice.lump_sum_net`/`progress_description` an, nie eine `InvoiceItem`-Zeile --
  PDF und Bildschirm zeigten dadurch nur einen nackten Betrag samt einer kurzen Bezeichnung
  (Standard z. B. "1. Abschlagsrechnung"), nie eine Position mit Beschreibung dessen, was pauschal
  abgerechnet wird. Die anderen beiden Abschlagsarten (`abschlag_leistungsstand`/`schluss`) waren
  NICHT betroffen -- beide kopieren über `_copy_order_items_with_default_ist()` bereits die
  echten Auftragspositionen.

  Gebaut wie vorgeschlagen (nicht die Pflichtfeld-Alternative): `_sync_lump_sum_pauschal_item()`
  in `app/invoices.py` hält GENAU EINE `InvoiceItem`-Zeile synchron zu `lump_sum_net`/
  `progress_description` -- aufgerufen aus `create_abschlag_pauschal()` (neu) und
  `update_invoice_header()` (bei jeder Änderung von Bezeichnung/Betrag, solange die Rechnung noch
  Entwurf ist). **Reine Projektion, wie ausdrücklich gefordert im Docstring festgehalten** (an
  drei Stellen: der Funktion selbst, `InvoiceItem`- und `Invoice.lump_sum_net`-Klassendocstring
  in `app/models.py`) -- `lump_sum_net` bleibt die alleinige Quelle der Wahrheit für den
  Rechnungsbetrag, `compute_invoice_totals()` liest für diesen Typ unverändert ausschließlich
  `lump_sum_net`, nie eine Positionssumme. `add_invoice_item()`/`update_invoice_item()`/
  `remove_invoice_item()` lehnen jede Änderung an dieser Zeile über den allgemeinen Positionsweg
  jetzt mit `ValueError` ab -- verhindert, dass später jemand eine eigene Positionsbearbeitung
  dafür baut und dadurch zwei unabhängig editierbare Zahlen für denselben Betrag entstehen lässt,
  exakt der Fehler, der beim Mahntext (1.3.21, CLAUDE.md "Mahnwesen: Löschen/Versenden/Bearbeiten")
  bewusst vermieden wurde. Menge/Einheit der Zeile sind fest (1 / `"pschl."`) ohne eigene
  Bedeutung. `invoice_detail.html`s Bildschirmoberfläche bleibt bewusst UNVERÄNDERT (weiterhin nur
  das Pauschalbetrag-Kärtchen mit Bezeichnung/Betrag, `itemsCard` bleibt für diesen Typ
  ausgeblendet) -- die Projektion braucht keine eigene Bearbeitungsfläche, eine sichtbare, aber
  nicht editierbare Positionstabelle auf dem Bildschirm wäre nur verwirrend gewesen.

  **PDF** (`invoice_pdf.py`): die Weiche ist nicht mehr der Rechnungstyp allein, sondern ob
  tatsächlich eine Position existiert (`pauschal_has_item = invoice_type=="abschlag_pauschal" and
  bool(visible_items(invoice))`) -- mit Position die reguläre Positionstabelle (Pos./Menge/EH/
  Leistung/EP/GP) wie bei jedem anderen Typ, die bisherige, separate Überschrift entfällt dabei
  (der Text steht bereits als Positionsbeschreibung in der Tabelle, sonst erschiene er doppelt).
  Ohne Position (Bestandsfall) bleibt die Darstellung exakt wie vorher: Überschrift +
  Netto/MwSt.-/Bruttoblock, keine Tabelle.

  **Vor dem Schreiben einer Migration gegen die echte Datenbank geprüft, wie verlangt**: genau
  **2 pauschale Abschlagsrechnungen** (R-2026-0001, R-2026-0002), **beide bereits
  `status="versendet"`**, keine mit einer Position. Entscheidung: **keine Migration** -- eine
  nachträglich erzeugte Position an einem bereits versendeten, GoBD-unveränderlichen Dokument
  hätte das PDF anders aussehen lassen als beim tatsächlichen Versand an den Kunden (genau das
  vom Nutzer benannte Risiko). Beide Rechnungen bleiben deshalb unverändert ohne Position -- die
  oben beschriebene PDF-Weiche sorgt dafür, dass ihr Rendering dadurch automatisch unangetastet
  bleibt, ganz ohne eigenen Sonderfall dafür schreiben zu müssen. Ein bereits im Entwurf
  befindlicher (noch nicht finalisierter) pauschaler Abschlag hätte die Position stattdessen beim
  nächsten Speichern von Bezeichnung/Betrag automatisch nachgeholt (`update_invoice_header()`) --
  in der echten Datenbank betraf das aktuell keine Zeile, da beide vorhandenen bereits versendet
  sind.


## Umbau der Projektliste (seit 1.3.70, Fundament + 1.3.72, Oberfläche)

Betreiber-Auftrag: die Projektliste (Sidebar → Projekte) wird breiter und ruhiger -- der linke
Kasten "Projekte & Vorgänge" mit den vier Reitern Angebote/Aufträge/Anfragen/Mustervorgänge
entfällt zugunsten einer Liste über die volle Breite mit Kategoriefilter, plus einer
umschaltbaren Kanban-Ansicht mit frei konfigurierbaren Spalten wie bei den Aufgaben. Vorgehen
ausdrücklich in Etappen (Muster "Dateiablage je Objekt"): erst Befund (keine Codeänderung),
dann diese Version -- **nur das Fundament** --, danach erst die Listen-/Kanban-Oberfläche.

### Befund (vor dieser Version, keine Codeänderung)

- **Projektliste heute**: fünf separate Endpunkte (`/api/projects`, `/api/quotes`, `/api/orders`,
  `/api/inquiries`, `/api/project-templates`), parallel geladen (`Promise.all`) -- Angebote/
  Aufträge/Anfragen sind KEINE `Project`-Zeilen, sondern eigene Tabellen
  (`Quote`/`Order`/`Inquiry`), die an ein Projekt hängen. Ein Kategoriefilter auf der
  Projektliste kann diese drei Reiter deshalb nicht ersetzen -- nur "Mustervorgänge"
  (`Project.is_template=True`) ist dieselbe Tabelle wie die Hauptliste. Seit der Büro-Suche
  (1.3.66/1.3.67) sind Angebote/Aufträge/Anfragen bereits unabhängig über `GET /api/search`
  auffindbar, was den ursprünglichen Zweck der Reiter (schnelles Finden ohne Umweg über das
  Projekt) teilweise entkräftet, aber die reinen Zähler nicht ersetzt.
- **Kategorie**: `ProjectProfile.category`, Optionsgruppe `project_categories` -- heute nur
  Anzeige + Teil der Freitextsuche, kein eigenes Filter-Dropdown.
- **`Project.status`**: ein ungeprüfter freier String ohne Datenbank-Constraint (Pydantic prüft
  nichts Sinnvolles), OHNE eine einzige Quelle der Wahrheit -- teils frei vom Nutzer editierbar
  (`PUT /api/projects/{id}`), teils automatisch überschrieben: `create_order_from_quote()`/
  `sync_order_from_source_quote()` (`app/orders.py`) setzen `"beauftragt"`,
  `duplicate_project()` (`app/projects.py`) setzt `"anfrage"` zurück, `convert_inquiry()`
  (`app/routers/inquiries.py`) setzt `"angebot"` -- ein Wert, der in keiner UI-Dropdown-Liste
  vorkommt (ein bereits bestehender, unabhängiger Rohrbruch, nur gemeldet, nicht behoben).
  Gelesen wird `status` u. a. von den Dashboard-KPIs "Aktive Projekte"/"Laufende Projekte"
  (feste Wortlaute fest verdrahtet).
- **Task-Kanban als Vorbild geprüft**: `TaskColumn` (key/label/sort_order/is_done) --
  `Task.status` **IST** direkt `TaskColumn.key`, kein separates Feld daneben.
  `TaskColumn.is_done` steuert automatisch `Task.completed_at`. **Korrigierte Prämisse**: die
  Aufgabenseite hat entgegen der ursprünglichen Annahme des Nutzers **kein Drag & Drop und
  keinen Listen/Kanban-Umschalter** -- es gibt nur eine einzige Board-Ansicht, das Verschieben
  zwischen Spalten läuft ausschließlich über ein `<select>`-Feld im Bearbeiten-Formular plus
  "Speichern". Transparent gemeldet statt stillschweigend umgangen, siehe Segment-Historie
  dieser Sitzung.

### Die wichtigste Entscheidung (Punkt 2 der Anfrage): zwei unabhängige Felder

Variante A gewählt (vom Nutzer bestätigt): `Project.pipeline_column_id` ist ein NEUES,
UNABHÄNGIGES Feld neben dem bestehenden `status` -- keine Ablösung des Status durch die
Kanban-Spalten (Variante B, das Task-Muster). Begründung, warum Project hier NICHT dem
Task-Vorbild folgt, obwohl "so viel wie möglich vom bestehenden Mechanismus" wiederverwendet
werden sollte: `Project.status` trägt echte Geschäftslogik-Automatik (Beauftragung,
Duplizieren, Anfrage-Umwandlung) UND wird von Kennzahlen mit festen Wortlauten gelesen
(Dashboard-KPIs) -- `Task.status` hatte davon nichts, bei Aufgaben WAR die Spalte schon immer
der einzige Status. Eine freie, per Ziehen sortierbare Kanban-Spalte, wäre sie dasselbe Feld,
hätte zwei echte Risiken: (1) ein Admin könnte eine Spalte umbenennen/löschen, deren Wortlaut in
den KPI-Auswertungen fest verdrahtet ist -- eine Kennzahl würde lautlos falsch, nicht nur die
Kanban-Anzeige; (2) ein von Hand verschobenes Projekt würde beim nächsten automatischen
Schreibvorgang (Beauftragung, Resync) unbemerkt wieder zurückspringen -- ein Zurückspringen,
das der Nutzer nicht erwartet und nicht sofort bemerkt.

**Die beiden Felder bleiben strikt getrennt, in beide Richtungen**: `status` bleibt exakt wie
bisher automatisch/kennzahlengesteuert -- keine Funktion dieses Projekts darf ihn aus
`pipeline_column_id` ableiten. Und `pipeline_column_id` wird NIE automatisch von einer
Geschäftslogik-Funktion überschrieben (anders als `status`) -- es ist eine rein freie, vom
Nutzer per Ziehen gesetzte Arbeitsansicht ohne jede fachliche Bedeutung, die einzige Automatik
ist die Startspalte bei der Neuanlage. **Transparente Randnotiz**: der Nutzer bezog sich in
seiner Entscheidung auf eine Funktion `_recompute_project_status()` als Sinnbild für "die
Status-Automatik" -- eine Funktion mit genau diesem Namen existiert im Code nicht; die
tatsächliche Automatik sitzt verteilt an den vier oben genannten Stellen
(`create_order_from_quote()`/`sync_order_from_source_quote()`/`duplicate_project()`/
`convert_inquiry()`). Die Entscheidung selbst ("keine dieser Stellen rührt
`pipeline_column_id` an, und keine künftige Pipeline-Funktion rührt `status` an") gilt davon
unberührt -- nur der Name war ein Sinnbild, keine wörtliche Referenz auf eine existierende
Funktion.

### Was in dieser Version gebaut wurde (Fundament)

- **`ProjectPipelineColumn`** (`app/models.py`, Migration `da9d9425e257`) -- `key`/`label`/
  `sort_order`, bewusst nach demselben MUSTER wie `TaskColumn` aufgebaut (Slug-Erzeugung,
  `sort_order`-Schrittweite 10, Löschschutz bei letzter Spalte/bei Verwendung), aber OHNE
  `is_done` -- die Pipeline-Spalte trägt keine Automatik, ein wirkungsloses "erledigt"-Flag wäre
  nur irreführend gewesen. Vier Startspalten: "Neu", "In Bearbeitung", "Wartet",
  "Abgeschlossen" -- ein schlanker, allgemeiner Satz statt fein aufgeteilter Branchenphasen, der
  Betrieb passt sie in den Einstellungen frei an.
- **`Project.pipeline_column_id`** (FK auf `ProjectPipelineColumn.id`, NOT NULL) -- ein Projekt
  ohne Spalte würde im künftigen Kanban unsichtbar bleiben, deshalb Pflichtfeld statt optional.
  Migration legt die Spalte zunächst NULLABLE an (Regel 1 -- der Fremdschlüssel zeigt auf eine
  erst in derselben Migration befüllte Tabelle, ein `server_default` auf eine konkrete ID wäre
  fragil), befüllt ALLE Bestandsprojekte auf die erste Spalte ("Neu", niedrigste `sort_order`)
  und setzt danach NOT NULL. Gegen die echte, lokale Datenbank geprüft: 8 Bestandsprojekte,
  0 mit einer vorher schon vorhandenen Pipeline-Spalte (Tabelle existierte noch nicht), alle 8
  nach der Migration korrekt auf die "Neu"-Spalte gesetzt, 0 NULL-Werte.
- **Startspalte für neue Projekte**: alle VIER Stellen, die ein `Project` konstruieren
  (`app/projects.py::duplicate_project()`, `app/quick_service_orders.py::
  create_quick_service_order()`, `app/routers/inquiries.py::convert_inquiry()`,
  `app/routers/projects.py::create_project()`) setzen `pipeline_column_id` jetzt explizit über
  die neue `app/project_pipeline_columns.py::default_pipeline_column_id(db)` -- die Spalte mit
  der niedrigsten `sort_order`, selbst-seedend wie bei den Aufgaben-Spalten, falls die Tabelle
  (z. B. eine per `Base.metadata.create_all()` erzeugte Testdatenbank) noch komplett leer ist.
  Ein Duplikat/eine Kopie startet dabei bewusst NEU in der ersten Spalte, unabhängig davon, wo
  die Quelle stand -- exakt dasselbe Prinzip wie bei `status="anfrage"` in `duplicate_project()`.
- **Bewusst KEINE gemeinsame, generische Abstraktion mit `app/task_columns.py`.** Task verweist
  über den STRING-Schlüssel (`Task.status == TaskColumn.key`), Project dagegen über die
  NUMERISCHE ID (`Project.pipeline_column_id == ProjectPipelineColumn.id`) -- zwei
  unterschiedliche Referenzformen -- und die Pipeline-Spalte kennt kein `is_done`. Eine
  Abstraktion für nur diese zwei, sich in diesem Punkt unterscheidenden Nutzer wäre eine
  Überabstraktion gewesen (Regel dieses Projekts: keine Abstraktion vor dem dritten Nutzer,
  siehe z. B. den zurückgestellten `build_totals_table()`-Vorschlag unter "Gemeinsamer
  Dokumenttyp"). Stattdessen ist das MUSTER (nicht der Code) identisch übernommen -- dieselbe
  Slug-Erzeugung, dieselbe `sort_order`-Schrittweite, dieselben zwei Löschschutz-Bedingungen --
  damit beide Spaltensysteme nicht auseinanderdriften, wie vom Nutzer verlangt. Neues, eigenes
  Modul `app/project_pipeline_columns.py`, neuer Router `app/routers/project_pipeline_columns.py`
  (`/api/project-pipeline-columns`, dieselbe Büro+Admin-Sperre wie der Rest der
  Projektverwaltung, `require_role(ROLE_ADMIN, ROLE_OFFICE)` für GET, zusätzlich admin-only für
  die vier verändernden Endpunkte -- Muster `app/routers/task_columns.py`). Kein Modul-Gate --
  Projekte sind Teil der immer aktiven Kern-ERP-Kette.
- **Spaltenverwaltung** unter Einstellungen → neue Gruppe "Projekte" → "Projekt-Pipeline" --
  dieselbe Bearbeiten/Verschieben/Löschen-Oberfläche wie bei den Aufgaben-Spalten (Label-Feld,
  ↑/↓-Buttons, Löschen), nur ohne die "zählt als erledigt"-Checkbox.

### Runde 2 (seit 1.3.72): die Oberfläche

`app/templates/projects.html` wurde vollständig neu gebaut -- kein inkrementelles Anpassen des
alten Fünf-Reiter-Templates.

**Vorab erneut geprüft, wie beim Fundament (Muster "Dateiablage je Objekt"/"Büro-Suche"): erst
Befund, dann bauen.** Zwei offene Fragen aus dem Fundament wurden dabei neu bewertet, nicht nur
aus dem Gedächtnis übernommen:

- **Angebote/Aufträge-Reiter -- echter Funktionsverlust, dem Nutzer VOR dem Entfernen
  gemeldet** (wie ausdrücklich verlangt: "sag mir das, bevor du sie ersatzlos entfernst").
  `app/routers/pages.py` hat bis heute keine `/quotes`- oder `/orders`-Seite -- die beiden Reiter
  waren die einzige Möglichkeit, alle Angebote/Aufträge projektübergreifend in einer Liste zu
  sehen. Die ursprüngliche Nutzer-Annahme ("ersetzbar durch Suche und Kategoriefilter") trifft
  nur teilweise zu: die Büro-Suche (`/suche`, seit 1.3.66/1.3.67) verlangt einen Suchbegriff und
  ersetzt kein "alle Angebote im Entwurf durchblättern", der Kategoriefilter filtert nach
  *Projekt*-Kategorie, nicht nach Angebots-/Auftragsstatus. Drei Lösungen zur Wahl gestellt
  (ersatzlos entfernen / Status-Filter in der neuen Liste ergänzen / eigene schlanke
  `/quotes`-`/orders`-Seiten neu bauen) -- Nutzer wählte **Status-Filter in der neuen Liste**.
  "Anfragen" war dagegen redundant (`/inquiries` existiert bereits als eigenständige Seite,
  `app/routers/pages.py:463`) -- entfällt ersatzlos, ohne Ersatzlösung nötig.
- **Tasks-Prämisse ein zweites Mal verifiziert** (nicht nur aus dem Fundament-Befund erinnert):
  `tasks.html` hat weiterhin kein `draggable`/`dragstart`/`dragover`/`drop` und keinen
  Listen/Kanban-Umschalter -- ein erneuter, gezielter Grep bestätigt das. Umschalter und
  Drag-and-drop der Projekt-Kanban-Ansicht sind deshalb ein eigenständiger Entwurf, keine Kopie
  eines bestehenden Mechanismus -- nur die bereits im Fundament vereinbarte
  Absicherungs-Begründung ("nur die Pipeline-Spalte ändert sich, kein fachlicher Status, kein
  Bestätigungsdialog nötig") bleibt unverändert gültig.

**Status-Filter, technisch** (Punkt 1 der Nutzerentscheidung): kein neues Backend-Feld, keine
neue Aggregation -- rein client-seitig aus den bereits bestehenden, unverändert weiterlaufenden
`GET /api/quotes`/`GET /api/orders` berechnet (beide liefern `project_id`, `status` je
Angebot/Auftrag). Dropdown "Angebot / Auftrag": Alle / Angebot: Entwurf / Angebot: Versendet /
Auftrag vorhanden / Ohne Angebot -- wirkt identisch in Liste UND Kanban (eine gemeinsame
`filteredRows()`-Funktion für beide Ansichten).

**Listenansicht** (volle Breite -- das `.layout`-Grid mit der 245px-Seitenspalte ist komplett
entfernt): Spalten Projektnummer/Bezeichnung/Kunde/Objekt/Kategorie/Status/Angebote/Dateien wie
bisher, Kategoriefilter oberhalb, bestehende Textsuche und "Archivierte anzeigen" bleiben. Die
sechs Zeilenaktionen (Projektmappe/+Angebot/Angebote/Kopieren/Als Mustervorgang speichern/
Archivieren/Löschen) wandern in ein Drei-Punkte-Kontextmenü je Zeile (`.menu-cell`, öffnet/
schließt über `toggleMenu()`/`closeAllMenus()`, Escape schließt zusätzlich) -- die Zeile selbst
führt per Klick in die Projektmappe (`event.stopPropagation()` auf der Menüzelle verhindert die
Navigation bei einem Klick auf ⋮ oder einen Menüpunkt). "Angebote" führt jetzt auf
`/projects/{id}#sec-quotes` (die bereits bestehende Angebote-Sektion in `project_folder.html`)
statt auf den entfallenen, projektübergreifenden Reiter -- das reicht, weil der Status-Filter
oben das projektübergreifende Durchsuchen jetzt übernimmt.

**Kanban-Ansicht**: Spalten aus `GET /api/project-pipeline-columns` in `sort_order`, eine Karte
je Projekt (Projektnummer, Bezeichnung, Kunde/Objekt, Status als kleines Kennzeichen).
Verschieben per **nativem HTML5-Drag-and-drop** (`draggable`, `dragstart`/`dragover`/`drop` --
dieselbe Technik wie die Plantafel, nicht Pointer-Events wie die Dachflächen-Skizze/der
Unterschriften-Canvas): Projekte sind Büro/Admin-only, also strukturell Desktop-orientiert, nicht
der Touch-first-Monteur-Kontext, in dem native HTML5-DnD laut Plantafel-Erfahrung nicht
funktioniert -- deshalb hier unproblematisch. Ruft den neuen Endpunkt
`PUT /api/projects/{id}/pipeline-column` (`ProjectPipelineColumnMove`-Schema, `{pipeline_column_id:
int}`) auf -- ändert ausschließlich `Project.pipeline_column_id`, fasst `status` nie an, 404 bei
unbekanntem Projekt/unbekannter Spalte, `require_role(ROLE_ADMIN, ROLE_OFFICE)` wie der Rest der
Projektverwaltung (kein admin-only-Sonderfall wie bei den Spalten-STAMMDATEN selbst -- das
Verschieben eines einzelnen Projekts ist Tagesgeschäft, nicht Konfiguration). Optimistisches
UI-Update (`moveProjectColumn()` setzt `pipeline_column_id` sofort lokal, rendert neu, rollt bei
einem fehlgeschlagenen Request zurück) statt auf die Server-Antwort zu warten. Kein
Bestätigungsdialog -- wie im Fundament entschieden.

**Mustervorgänge** (Punkt 1 der Anfrage, dritter Teil): Kontrollkästchen "Nur Mustervorgänge"
statt eines eigenen Zugangs -- schaltet die Datenquelle der ganzen Liste (Liste UND Kanban) auf
`GET /api/project-templates` um, Kontextmenü zeigt für Mustervorgang-Zeilen "Neuen Vorgang
erstellen" statt der sechs normalen Aktionen. Kein zweiter Rendering-Pfad -- dieselben
`renderList()`/`renderKanban()`-Funktionen, nur `menuItemsFor()` verzweigt.

**Kopfzeile, Punkt 4 der Anfrage**: Suche, Kategoriefilter, Status-Filter, "Nur Mustervorgänge",
"Archivierte anzeigen" und der Liste/Kanban-Umschalter sitzen in EINER gemeinsamen Kopfzeile über
dem Inhalt (`.toolbar`), nicht verstreut -- Muster an `tasks.html`s Kopfzeile angelehnt (Suche +
Checkbox in einer Reihe), um zwei unterschiedlich bediente Umschalter für dasselbe Prinzip zu
vermeiden. Die Ansichtswahl (`erp_project_view`, `localStorage`, Muster `erp_theme`) bleibt beim
nächsten Öffnen erhalten.

**Schema-Erweiterung, technisch notwendig für die Kanban-Gruppierung**: `ProjectListOut`/
`ProjectDetailOut` bekommen `pipeline_column_id` als Pflichtfeld -- ergänzt an allen vier
Stellen, die das Schema manuell befüllen (`routers/projects.py`: Liste, Anlegen, Detail;
`routers/inquiries.py`: `convert_inquiry()`s Rückgabe), sonst hätte ein bestehender Aufrufer mit
einem Pydantic-Validierungsfehler abgebrochen (per Testlauf bestätigt, bevor die Endpunkte
angepasst waren).

**Rollen geprüft, keine Änderung nötig** (letztes Akzeptanzkriterium): `/projects` UND
`/api/projects*` tragen unverändert `require_role(ROLE_ADMIN, ROLE_OFFICE)` -- der Umbau
selbst rührt daran nichts an. Per echtem HTTP-Smoke-Test gegen eine isolierte, temporäre
Serverinstanz bestätigt (nicht nur angenommen): ein Monteur-Konto bekommt sowohl auf die Seite
als auch auf `GET /api/projects` 403, `/mobil` bleibt für dieselbe Rolle unverändert erreichbar.

**Verifikation**: `node --check` gegen den extrahierten `<script>`-Block (keine JS-Syntaxfehler).
Neue Tests (`tests/test_v275_project_list_pipeline_move.py`) für den neuen Endpunkt (ändert nur
die Spalte, nie `status`; 404 bei unbekanntem Projekt/unbekannter Spalte; `field` bekommt 403,
`admin`/`office` dürfen verschieben) und die `pipeline_column_id`-Präsenz in allen drei
betroffenen Response-Pfaden. Drei bestehende Tests, die die alte Fünf-Reiter-Struktur
voraussetzten (`test_v063_navigation_hubs.py`, `test_v192_project_templates.py`), auf die neue
Struktur umgeschrieben, nicht nur angepasst. **Echter End-to-end-Smoke-Test** gegen eine
isolierte, temporäre SQLite-Datenbank (niemals `dachkonzepte_erp.db`) auf einem separaten Port:
Projekt anlegen, per `PUT .../pipeline-column` zwischen zwei Spalten verschieben (`status` blieb
dabei nachweislich `"anfrage"`, unverändert), Büro-Rolle sieht `/projects` (200), Monteur-Rolle
bekommt 403 auf Seite und API, `/mobil` bleibt für sie erreichbar -- Instanz und temporäre
Datenbank danach vollständig entfernt. **Bewusst NICHT möglich**: ein echter Browser-Klicktest
(Drag-and-drop, Kontextmenü-Öffnen/-Schließen per Maus, Live-Filtern) -- dieselbe, in dieser
Sitzung bereits mehrfach dokumentierte Werkzeug-Einschränkung (kein
Browser-Automatisierungswerkzeug verfügbar). Die clientseitige Interaktionslogik ist dadurch nur
über Quelltextprüfung und `node --check` abgesichert, nicht über eine tatsächliche
Bildschirminteraktion -- sollte bei Gelegenheit im Browser nachgeprüft werden, insbesondere das
Drag-and-drop-Gefühl und ob das Kontextmenü auf einem schmalen Bildschirm (`@media(max-width:
850px)`) noch bedienbar bleibt.

**Korrektur (seit 1.3.73)**: genau dieser fehlende Klicktest ließ einen echten Fehler durch --
das Kontextmenü wurde vom `overflow:auto` des `.wrap`-Tabellencontainers abgeschnitten. Siehe
"Kontextmenü der Projektliste" unten für die Behebung, und "Headless-Chrome-Verifikation über
CDP" dafür, dass ein echter Browsertest in dieser Umgebung entgegen der bisherigen Annahme doch
möglich ist -- die obige "kein echter Browser-Klicktest möglich"-Einschränkung war zu pauschal.

### Kontextmenü der Projektliste: Beschneidung durch overflow:auto behoben (seit 1.3.73)

Siehe CHANGELOG.md 1.3.73 für die vollständige Herleitung (Ursache, geprüfte Alternativen,
gewählte Lösung `position:fixed` statt DOM-Umzug, Scroll-Schließen, Verifikationsdetails) --
hier nur die Kurzfassung: `.menu` (`app/templates/projects.html`) ist jetzt `position:fixed`,
Position wird per JS aus `getBoundingClientRect()` des Drei-Punkte-Knopfs berechnet (rechtsbündig,
klappt bei zu wenig Platz nach oben statt unten), ein globaler `scroll`-Listener (Capture-Phase)
schließt ein offenes Menü. Geprüft, ob dasselbe Muster anderswo im Projekt bereits gelöst wurde
(wie verlangt) -- einziger Fund war der Kontoknopf in `_topbar.html`, der aber nie in einem
`overflow`-Container sitzt und deshalb kein Vorbild für DIESES Problem ist; kein zweiter,
divergierender Lösungsweg also, aber auch kein wiederverwendbarer bestehender.

## Umbau der Projekt-Detailseite (die Projektmappe, seit 1.3.74)

Zweistufiger Auftrag (Muster "Dateiablage je Objekt"/"Büro-Suche"): erst Befund + Vorschlag
(keine Codeänderung), dann nach Bestätigung der Bau. Vorbild war ein vom Nutzer gezeigtes
LB.tec-Layout: oben der Projektkopf, darunter die Reiter, darunter der breite Inhalt.

### Befund (keine Codeänderung, vorher berichtet)

`project_folder.html` nutzte bis 1.3.73 CSS `:target`-Sprungmarken, kein `showTab`, keine
Tab-Auswahl -- die linke `.side`-Leiste war eine reine Anker-Liste (`<a href="#sec-...">`), neun
Bereiche gleichzeitig im DOM (`.card:target{outline:...}` als Beleg). Das entspricht fachlich
KEINEN echten Reitern, obwohl die Oberfläche optisch danach aussah. Drei externe Dateien
verlinken auf zwei dieser Anker (`projects.html` → `#sec-quotes`, `order.html`/
`work_preparation.html` → `#sec-orders`) -- mussten beim Umbau berücksichtigt werden, damit sie
nicht brechen.

### Fünf Bau-Entscheidungen, jede einzeln bestätigt und umgesetzt

1. **Acht echte Reiter statt neun Sprungmarken** -- Kennzahlen wird kein eigener Reiter (siehe
   Punkt 2). Übersicht (frühere "Projektinformationen"), Dateien, Angebote, Aufträge,
   Rechnungen, Arbeitsvorbereitung, Zeiten, Historie, mit denselben Zählungen wie zuvor an der
   linken Navigation (Dateien/Angebote/Aufträge/Rechnungen/Zeiten). **Reiter-Schlüssel bewusst
   identisch mit den bisherigen Sprungmarken-IDs** (`sec-info`/`sec-files`/`sec-quotes`/
   `sec-orders`/`sec-invoices`/`sec-workprep`/`sec-times`/`sec-history`) -- eine kürzere,
   sprechendere Schlüsselliste (wie bei `settings.html`s `SETTINGS_SECTIONS`) hätte die drei
   externen Tiefenverweise gebrochen; Wiederverwendung derselben Strings kostet nichts (URLs
   sind nicht zum Lesen gedacht) und macht `projects.html`/`order.html`/`work_preparation.html`
   komplett unangetastet.
2. **Kennzahlen als fester, immer sichtbarer Block über den Reitern, kein eigener Reiter** --
   entgegen der eigenen Befund-Empfehlung (Zusammenlegung mit "Übersicht"), auf ausdrücklichen
   Nutzerwunsch ("Sie gehören nicht in einen Reiter"). Schlank gehalten: die frühere dritte
   KPI-Gruppe "Dokumente" (Angebote/Aufträge/Rechnungen-Zählung, `kQuoteCount`/`kOrderCount`/
   `kInvoiceCount`) entfällt ersatzlos -- dieselben drei Zahlen standen vorher DREIFACH auf der
   Seite (Kopf-Badges, Kennzahlen-Dashboard, linke Navigation), jetzt genau EINMAL (an den
   Reitern). Übrig bleiben sechs kompakte Kacheln (Finanzen: Projektwert/Abgerechnet/Noch offen;
   Stunden: Soll/Ist/Abweichung) über die bereits bestehenden `.metric`/`.grid`-Klassen (dieselben,
   die auch `sec-times`s eigene Zusammenfassung nutzt) -- keine dritte, eigene Kachel-Optik neben
   den alten, jetzt entfernten `.kpi-groups`/`.kpi-group-label`/`.kpi-value`-Regeln. Per echtem
   Browser-Test nachgemessen: Kopf (141px) + Kennzahlen-Streifen (105px) + Reiterleiste (39px) =
   309px bei 855px Ansichtsfensterhöhe (~36 %) -- der geforderte "nicht die halbe Bildschirmhöhe"
   ist damit klar erfüllt, nicht nur behauptet.
3. **"Übersicht" ist der Reiter beim Öffnen, der aktive Reiter steht im URL-Hash.** Vor dem
   Bauen geprüft, welche bestehende Seite das Problem "Reiter in der Adresse, Reload/Lesezeichen
   zeigt denselben Reiter" schon löst, statt es neu zu erfinden: `settings.html`
   (`showSettingsSection(key,updateHash=true)`/`settingsSectionFromHash()`/
   `history.replaceState` (nicht `pushState`)/`hashchange`-Listener mit einer validierten
   `SETTINGS_SECTIONS`-Allowlist) passt genau. `master_data.html`s älteres, einfacheres
   `viewFromHash()` (nur eine Allowlist + `showView()`, kein `replaceState`/kein
   `hashchange`-Listener) wurde ebenfalls geprüft, aber verworfen -- es kennt kein Zurücksynchen
   bei Browser-Vor/Zurück und keine explizite "nur bei tatsächlicher Änderung schreiben"-Regel,
   beides für einen Reload/Lesezeichen-Anwendungsfall relevanter als bei einer reinen
   Stammdaten-Ansichtsumschaltung. `project_folder.html`s `showTab(key,updateHash=true)`/
   `tabFromHash()`/`hashchange`-Listener sind deshalb eine wörtliche Adaption von
   `settings.html`s Fassung, nur auf die 8 Reiter-Schlüssel umgestellt.
4. **Ein einziger permanenter Kopf-Button: "Projektmappe bearbeiten", nicht "+ Angebot".** Die
   eigene Befund-Vermutung ("+ Angebot", da einzige `btn primary`-Farbe im alten Kopf) wurde beim
   Bauen widerlegt -- gegen die echte, lokale `dachkonzepte_erp.db` geprüft statt nur vermutet:
   **6 von 8 Projekten tragen bereits `status="beauftragt"`, 6 von 8 haben genau EIN Angebot**
   (nur zwei haben ein zweites). Die Angebotsphase ist damit für die meiste Projektlaufzeit
   bereits abgeschlossen -- die Projektmappe wird überwiegend zum Nachsehen (Dateien, Aufträge,
   Rechnungen, Zeiten) geöffnet, nicht zum Anlegen eines weiteren Angebots. "+ Angebot"
   verschwindet dabei nicht (bleibt unverändert in den Reitern Übersicht UND Angebote, wie schon
   vorher an zwei Stellen) -- nur die permanente Kopf-Position wechselt. Der Rest (Kopieren, Als
   Mustervorgang speichern, Wartungsvertrag erstellen, Archivieren/Entarchivieren, Löschen)
   wandert ins Drei-Punkte-Menü, **exakt nach dem in `projects.html` etablierten Muster**
   (1.3.72/1.3.73: `.menu`/`.menu-btn`/`toggleMenu()`/`positionMenu()`/`closeAllMenus()`,
   `position:fixed`, Escape/Scroll/Resize schließen das Menü) -- keine zweite, eigene
   Menü-Implementierung, wie ausdrücklich verlangt geprüft und wiederverwendet.
5. **Bereichsinhalte unverändert, nur ihre Erreichbarkeit ändert sich.** Upload-Zone mit
   Drag&Drop, Kategorie-/Unterordner-Filterkarten, Suche, alle Tabellen, alle drei Modals
   (Projekt bearbeiten, Dateimetadaten bearbeiten, Wartungsvertrag erstellen) sind eins zu eins
   aus dem bisherigen Template übernommen. **Explizit entschieden und gestrichen**: die
   Collapse-Buttons (▾/▸, `toggleSection()`/`setSectionCollapsed()`) und ihr `localStorage`-
   Zustand (`dachkonzepte_project_folder_collapsed_sections`) -- bei genau einem sichtbaren
   Bereich zur selben Zeit (echte Reiter statt gleichzeitig sichtbarer Karten) ist ein
   Ein-/Ausklappen wirkungslos geworden, keine Funktion, die noch etwas leistet, kein
   Funktionsverlust im Sinne der Vorgabe "kein Bereich verliert Funktion" (die bezog sich auf
   Bereichs-INHALTE/Aktionen, nicht auf diese jetzt gegenstandslose UI-Bequemlichkeit). **Eager
   statt lazy Laden, wie im Bau-Auftrag ausdrücklich zur Wahl gestellt**: der bestehende einzelne
   `Promise.all(...)`-Aufruf in `load()` bleibt unverändert -- bei den heutigen Datenmengen (8
   Bestandsprojekte, je einstellige bis niedrige zweistellige Zeilenzahlen pro Bereich) gäbe es
   keinen messbaren Ladezeitgewinn durch ein Nachladen je Reiterwechsel, nur zusätzliche
   Komplexität (Ladezustand je Reiter, doppelte Fehlerbehandlung) ohne fachlichen Nutzen --
   ein Reiterwechsel schaltet ausschließlich `display:none`/`display:block` um
   (`.tab-pane{display:none}.tab-pane.active{display:block}`), keine zweite Ladelogik.

### Rollen-Check, bestätigt statt angenommen

`/projects/{project_id}` (Seitenroute, `app/routers/pages.py::project_folder_page()`) UND der
komplette `app/routers/projects.py`-Router (`_role_dep`, inkl. `GET /api/projects/{id}`) tragen
unverändert `require_role(ROLE_ADMIN, ROLE_OFFICE)` -- dieser Umbau rührt an keiner der beiden
Stellen etwas an, ein Monteur bleibt vollständig ausgesperrt (Seite UND API 403), genau wie vor
diesem Umbau.

### Verifikation

Per echtem, gegen eine isolierte, temporäre SQLite-Testinstanz (niemals `dachkonzepte_erp.db`)
CDP-gesteuertem Headless-Chrome bestätigt (Muster 1.3.73, eigener PowerShell/.NET-Treiber, kein
Playwright im Projekt vorhanden): Standardansicht zeigt "Übersicht" aktiv; die drei genannten
Höhen (Kopf/Kennzahlen-Streifen/Reiterleiste) wie oben gemessen; Klick auf "Dateien" schaltet
den Reiter tatsächlich um (`sec-info` wird inaktiv, `sec-files` aktiv) und setzt den URL-Hash auf
`#sec-files`; ein Neuladen mit `#sec-quotes` in der Adresse aktiviert direkt den
Angebote-Reiter (Tiefenverweis-Fähigkeit bestätigt, nicht nur angenommen); das Drei-Punkte-Menü
öffnet vollständig innerhalb des Ansichtsfensters mit allen fünf erwarteten Einträgen; keine
JavaScript-Konsolenfehler beim Laden oder bei den drei Interaktionen (die eine beobachtete
404-Konsolenmeldung ist plattformweit üblich -- ein vom Browser automatisch angefragtes,
fehlendes `favicon.ico`, unabhängig von diesem Template, auf jeder Seite dieses Projekts
gleichermaßen zu erwarten).
