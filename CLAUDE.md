# DACHKONZEPTE ERP – Projektkontext für Claude Code

Diese Datei fasst zusammen, was in einer langen Entwicklungssitzung mit Claude (über claude.ai)
erarbeitet wurde – Konventionen, wiederkehrende Fallstricke und der aktuelle Stand. Zweck: eine
neue Claude-Code-Sitzung soll nicht bei null anfangen, sondern die dort hart erarbeiteten Regeln
von Anfang an kennen.

**Wichtiger Hinweis zur Verlässlichkeit dieser Datei:** Sie wurde ursprünglich nicht aus dem
vollständigen lokalen Projekt erstellt, sondern aus dem Gedächtnis einer claude.ai-Sitzung und
einem Arbeits-Container, der nur die dort tatsächlich bearbeiteten Dateien enthielt. Am
09.09.2026 wurde deshalb eine vollständige Bestandsaufnahme gegen den echten Code durchgeführt
(`docs/bestandsaufnahme.md`, Anlage `docs/bestandsaufnahme_modelle.md`) – Migrationskette,
komplettes Modell-Inventar, Objekt-/Gebäudemodell, `MaintenanceContract`/`ServiceReport`
vollständig, `TimeEntry`, Plantafel, Modul-Registry, Datei-Uploads, Mobile-Tauglichkeit. Dabei
wurde u. a. eine falsche Behauptung dieser Datei korrigiert: **nicht** `bb175f455b64` ist die
älteste Alembic-Migration, sondern `2befd7907eef` ("baseline: bestehendes Schema",
02.09.2026) – acht weitere Migrationen liegen vor `bb175f455b64`. Bei Zweifeln an einer Aussage
unten zuerst in `docs/bestandsaufnahme.md` nachsehen, sonst wie bisher gegen den Code prüfen
(z. B. mit `alembic history`).

## Stand bei Übergabe

- Version: **1.3.45** (siehe `CHANGELOG.md` für die vollständige Versionshistorie)
- Migrationskette Kopf weiterhin `60d7c8a775f0` ("raise default sidebar logo height") -- 1.3.45
  (Topbar) brauchte keine eigene Migration, da sie ausschließlich Python/Jinja/CSS/JS anfasst,
  keine Datenbankspalte -- bei Bedarf per `alembic history`/`heads` prüfen statt sich auf eine
  hier aufgeschriebene Liste zu verlassen.
- Tests: **1102/1102**, zuletzt am 14.09.2026 mit `pytest` in Tobias' `.venv` unter Windows
  ausgeführt – darunter echte, über einen FastAPI-`TestClient` laufende Routen-Tests (seit
  1.2.15, Testabhängigkeit `httpx`) für die tatsächliche URL-Auflösung, nicht nur Aufrufe der
  Business-Funktionen direkt; der zugehörige Test-Helfer (`router_test_client`/
  `threaded_db_session`) lebt seit 1.2.16 als gemeinsame Fixture in `tests/conftest.py`, nicht
  mehr lokal in einer einzelnen Testdatei.
- Stabiler Pfad: `C:\DACHKONZEPTE-ERP\1 Prototype\`
- Das komplette visuelle Redesign (anpassbare Akzentfarbe, Hell-/Dunkel-Theme, eckige
  Eingabefelder, einfarbige Sidebar-Icons) ist auf **alle** Templates ausgerollt (1.0.97–1.0.100,
  siehe Changelog) – neue Seiten müssen diesem Design-System folgen, siehe unten.
- Neu seit 1.1.0: allgemeiner **Modul-Umschalter** (`app/modules.py`, Tabelle `enabled_modules`,
  Jinja-Global `is_module_enabled()`) sowie das erste damit abschaltbare Modul, das
  **Aufgabenmanagement** (`app/tasks.py`, `/tasks`, Kanban-Board) – siehe eigener Abschnitt unten.
- Neu seit 1.2.0–1.2.12: zweites abschaltbares Modul **Wartungen & Reparaturen** (`module_key
  "wartungen"`) – die drei laut Plan angekündigten Kern-Teilschritte sind fertig:
  **Wartungsverträge** (`app/maintenance_contracts.py`, `/maintenance-contracts`, seit 1.2.0),
  **digitale Einsatzberichte mit Unterschrift** (`app/service_reports.py`,
  `/orders/{id}/service-reports`, seit 1.2.1) und **Rechnung aus Zeitbuchungen** (neuer
  Rechnungstyp `invoice_type="aufwand"` in `app/invoices.py`, seit 1.2.2). Damit ist die Kette
  Wartungsvertrag → Erinnerung → Vorgang → Zeiterfassung → Einsatzbericht mit Unterschrift →
  Aufgabe → Rechnung durchgängig. Zusätzlich vier kleinere, anschließend umgesetzte
  Verbesserungen: **Reparatur/Wartung als Tätigkeiten** in der Zeiterfassung (seit
  1.2.3, reine Daten-Migration), **Wartungshistorie pro Gebäude** auf der
  Einsatzbericht-Seite (seit 1.2.4), das Dashboard-Widget **„Fällige Wartungen"** (seit
  1.2.5) und ein eigener **Einstellungen-Bereich "Wartungen"** (`MaintenanceSettings`, seit
  1.2.6) mit konfigurierbarer Vorlaufzeit (`reminder_lead_days`, Standard 30 Tage) und
  Standard-Sachbearbeiter als Rückfall. Seit 1.2.7 springt "Vorgang erstellen" bei einem fälligen
  Vertrag direkt zum neu erstellten Vorgang (`/projects/{id}`), statt nur eine Statuszeile zu
  zeigen – Tobias hatte den neuen Vorgang sonst nicht wiedergefunden, da dieser den Namen des
  Mustervorgangs trägt, nicht den des Wartungsvertrags. Seit 1.2.8 lässt sich ein
  Wartungsvertrag zusätzlich endgültig löschen; seit 1.2.10 räumt das Löschen auch die daran
  hängende Erinnerungs-Aufgabe mit auf (sonst blieb sie als toter Link zurück, siehe eigener
  Abschnitt unten); seit 1.2.11 lässt sich sowohl ein Wartungsvertrag als auch eine Aufgabe
  zusätzlich archivieren (mildere, umkehrbare Alternative zum Löschen). Seit 1.2.14 gibt es
  unter dem Kern-Stammdatum `Property` außerdem `RoofArea`/`RoofComponent` (einzelne
  Dachflächen samt Bauteilen, bewusst OHNE Modul-Zugehörigkeit). Seit 1.2.15 nutzt das Modul
  `wartungen` das: `MaintenanceContract` kann jetzt Positionen je Dachfläche
  (`MaintenanceContractItem`) mit saisonalen Wartungsfenstern (`MaintenanceWindow`) tragen –
  hat ein Vertrag aktive Positionen, übernehmen sie die Fälligkeitssteuerung vollständig von
  der Vertragsebene; `ServiceReport` bekommt dafür einen (über `ProjectProfile` durchgereichten)
  Bezug zum Vertrag, ohne `Order` anzufassen. Seit 1.2.16 bekommt `ServiceReport` zusätzlich
  strukturierte Prüfpunkte (`InspectionTemplate`/`InspectionTemplateItem`/`InspectionItem`,
  verwaltet unter Einstellungen → Prüfvorlagen): beim Anlegen eines Wartungsberichts wird eine
  Vorlage gegen den tatsächlichen Bauteilbestand der ausgewählten Dachfläche multipliziert,
  alle anzeigerelevanten Felder werden dabei physisch kopiert. Seit 1.2.17 macht `Finding`/
  `ServiceReportPhoto` aus einem negativen Prüfergebnis eine Handlung (sofort behoben,
  Folgeauftrag, Angebot nötig, zurückgestellt) und liefert eine Mängelhistorie je Bauteil –
  mobile Erfassung bleibt bewusst eine spätere Iteration (4b), die Bedienung läuft über die
  bestehende Berichtsseite im normalen Design-System. Ein echter Scheduler für eine
  vollautomatische Auftragserzeugung bleibt bewusst ausstehend (siehe Plan, „Bewusst außerhalb
  dieser Iteration"). Seit 1.2.18 gibt es eine echte Objektseite (`GET /properties/{id}`,
  `property.html`) statt der bisherigen zwei unterschiedlich reichen Ansichten (Kundenakte vs.
  generische Stammdatenmaske), mehrere Dachflächen lassen sich in einem Schritt anlegen, und
  `RoofArea.build_up`/`insulation` (Freitext) sind einer strukturierten, dachtyp-abhängigen
  Schichtenliste (`RoofLayerType`/`RoofLayer`) gewichen. Siehe eigener Abschnitt unten. Seit
  1.2.19: der bei 1.2.18 im ersten echten Gebrauch gefundene Datenverlust in der
  Schichtenliste ist behoben (`upsert_roof_layer()`/`update_inspection_item()` überschreiben
  nur noch tatsächlich mitgeschickte Felder, `exclude_unset`), `RoofLayerType` hat drei statt
  einem Flag (`has_execution`/`has_thickness`/`has_notes`), Bauteilarten sind eine echte
  Tabelle (`RoofComponentType`, statt der Optionsgruppe `roof_component_types`) mit einem
  `is_area`-Flag für flächige Markierungen (Rechteck statt Punkt) auf der Skizze, Wartungsverträge
  haben eine eigene Detailseite (`GET /maintenance-contracts/{id}`) und ein neuer Schalter
  `MaintenanceSettings.use_roof_area_items` (Default aus) macht "Zu wartende Dachflächen"
  (fachlich weiter `MaintenanceContractItem`) zur echten Option statt eines unbedingten
  Verhaltens. Siehe jeweils eigener Abschnitt unten. Seit 1.2.20: von einem Auftrag führt jetzt
  ein sichtbarer Weg zu seinen Einsatzberichten (`order.html`, `project_folder.html`), die
  Berichtsseite hat dafür eine echte Breadcrumb zum Kunden bekommen, "Vorgang erstellen" zeigt
  nach dem Anlegen ein Ergebnis-Panel statt sofort zu navigieren, und zwei Formularfelder, die
  fälschlich als "optional" beschriftet waren, nennen jetzt die Folge. `duplicate_project()`
  wurde auf eine gemeldete Beobachtung hin geprüft und bestätigt korrekt (kopiert nie einen
  Auftrag) – siehe Abschnitt "Mustervorgang" unten. Seit 1.2.21: die Mangel-Maßnahmen
  "folgeauftrag"/"angebot_erforderlich" sind zu einer einzigen Maßnahme "buero_pruefen"
  zusammengeführt, die nur noch eine Aufgabe erzeugt, nie einen Auftrag/nie ein Navigieren
  mitten im Bericht – der eigentliche Vorgang entsteht erst über eine neue "Vorgang erstellen"-
  Schaltfläche auf der Aufgabe selbst. Der Einsatzbericht bekommt ein kompaktes
  Zeitbuchungsformular direkt auf der Seite (kein Ausflug mehr in die volle Zeiterfassung und
  zurück), und `reportlab.platypus.KeepTogether` verhindert im PDF, dass die Unterschrift (und
  andere Überschrift+Inhalt-Blöcke) über einen Seitenumbruch reißen. Seit 1.2.22: ein
  `ServiceReport` kann jetzt MEHRERE Dachflächen umfassen (neue Tabelle
  `ServiceReportRoofArea`, `InspectionItem.roof_area_id`) – ein Objekt mit mehreren Dachflächen
  bekommt einen einzigen Bericht mit einer einzigen Unterschrift statt eines Berichts je Fläche.
  Welche Vorlage je Dachtyp gilt, ist jetzt explizit konfiguriert (`RoofTypeInspectionTemplateDefault`,
  Einstellungen → Prüfvorlagen) statt implizit über `sort_order`. Neuer Button "Wartung
  durchführen" auf der Vertragsseite (`create_maintenance_visit()`) fasst Auftrag- und
  Berichtsanlage über alle Dachflächen des Objekts in einem Klick zusammen; die Fälligkeit wird
  dabei bewusst erst bei der Unterschrift fortgeschrieben (`ServiceReport.advance_due_date_on_sign`),
  nicht beim Anlegen. Die Berichtsseite gruppiert Prüfpunkte jetzt nach Dachfläche (zugeklappt)
  und zeigt Mängel inline am Prüfpunkt. Seit 1.2.23: der Monteur erfasst am Einsatzbericht
  zusätzlich verbrauchtes Material (`ServiceReportMaterial`, bewusst ohne Preisspalte) – aus dem
  Katalog (Bezeichnung/Einheit als Schnappschuss kopiert) oder frei eingetippt (kein neuer
  Katalogeintrag). `create_invoice_from_time_entries()` bepreist Katalogmaterial jetzt mit dem
  aktuellen Katalogpreis **inklusive** dem globalen Materialaufschlag
  (`CalculationSettings.material_markup_pct`, derselbe Mechanismus wie im Leistungskatalog) –
  steht der Aufschlag auf 0 %, gibt es dafür einen sichtbaren, einmaligen Hinweis statt eines
  stillschweigend unaufgeschlagenen Preises. Siehe jeweils eigener Abschnitt unten.
- Neu seit 1.3.0: **Monteursansicht** (`GET /vor-ort`, `app/templates/vor_ort.html`) – erster
  Minor-Sprung seit 1.2.0, aber bewusst **kein** neuer `OPTIONAL_MODULES`-Eintrag (siehe eigener
  Abschnitt unten). Eine schmale, eigene Einstiegsseite fürs Fahrzeug-Tablet statt einer zweiten
  App: reduzierte Kopfzeile (`_mobile_header.html`), heutige Einsätze aus der Plantafel plus
  offene Entwurfsberichte, ein Klick führt direkt in den jeweiligen Bericht.
  `service_reports.html` bleibt EIN Template, wird aber per neuem `@media(max-width:900px)`
  tablet-tauglich (Bedienelemente ≥44px, Foto-Inputs mit `capture="environment"`, Tabellen als
  gestapelte Karten). `ServiceReport` bekommt eine zweite, parallele Unterschrift
  (`installer_signature_*`) – `sign_report()` verlangt jetzt beide in einem Aufruf.
  `created_by_employee_id` ist jetzt an allen vier Stellen gehärtet, die es kennen (Bericht,
  Foto, Material, Mangel), nicht nur beim Bericht – ein gemeinsamer Helfer
  `_employee_for_request()`. Neue Singleton-Tabelle `MobileSettings` (Feierabend-Uhrzeit,
  automatisches Abmelden). Web-App-Manifest + PWA-Icons über dedizierte Endpunkte, kein
  `StaticFiles`-Mount. Siehe eigener Abschnitt "Monteursansicht" unten.
- Neu seit 1.3.1: **gemeinsamer PDF-Rahmen** (`app/document_frame.py`), erste Etappe des in
  `docs/bestandsaufnahme_pdf.md` skizzierten PDF-Umbaus, erprobt an der Mahnung
  (`app/reminder_pdf.py`). Trennt den wiederkehrenden Rahmen (Briefpapier-Hintergrund, Ränder,
  optionale gezeichnete Bausteine) vom fließenden Inhalt – Angebot/Auftrag/Rechnung/
  Einsatzbericht bleiben in dieser Etappe vollständig unangetastet. Siehe eigener Abschnitt
  "PDF-Rahmen" unten.
- Neu seit 1.3.2: **Fehlerbehebung am 1.3.1-PDF-Rahmen** – der gezeichnete Firmenkopf-Baustein der
  Mahnung überlagerte den fließenden Inhalt, weil sein `y_mm` und der obere Standard-Rand für
  Seite 1 beide auf 17mm standen. `company_header`/`logo` stehen in `DEFAULT_REMINDER_LAYOUT`
  jetzt standardmäßig auf `visible=False`, zusätzlich hebt ein neuer, dokumenttyp-spezifischer
  Mechanismus (`DOCUMENT_TYPE_MARGIN_OVERRIDES` in `app/document_page_margins.py`) den
  Standard-Rand der Mahnung auf 42mm an. Details im Abschnitt "PDF-Rahmen" unten.
- Neu seit 1.3.3: **gemeinsamer Kopfbereich** (`build_din5008_header_block()` in
  `app/document_pdf.py`), erster Nutzer wieder die Mahnung. Ersetzt dort
  `build_customer_and_meta_block()` (bleibt für Angebot/Auftrag/Rechnung unverändert bestehen) –
  Empfängeranschrift jetzt als echte, einzelne Zeilen statt eines zusammengezogenen Absatzes,
  Meta-Block als Zweispalten-Tabelle mit einer Zeile pro Beschriftung/Wert-Paar, dazu eine kleine,
  unterstrichene Absenderzeile (DIN 5008). Details im Abschnitt "Kopfbereich" unten.
- Neu seit 1.3.4: **Fehlerbehebung am 1.3.3-Kopfbereich** – zweiter Smoke-Test fand den Meta-Block
  zu weit links (Wertespalte ohne `ALIGN`-Regel, dadurch nicht wirklich rechtsbündig) und
  uneinheitliche linke/rechte Fluchtlinien (`Table`-Zellenpolster ungenullt, Forderungstabelle mit
  `hAlign="RIGHT"` bei zu geringer Breite). Alles tatsächlich im PDF nachgemessen
  (`pypdfium2`-Zeichenboxen), nicht nach Augenmaß korrigiert. Details im Abschnitt "Kopfbereich"
  unten.
- Neu seit 1.3.5: **Seitenangabe im Meta-Block** – dritter Smoke-Test wollte "Seite 1 / N" als
  eigene Meta-Block-Zeile, analog zum Angebot (das dieses Problem allerdings selbst nie gelöst
  hat, siehe unten). `render_framed_pdf()` unterstützt dafür jetzt einen zweiten Renderdurchlauf
  (`content_story` als Funktion `total_pages -> list` statt einer fertigen Liste), verallgemeinert
  für künftige Dokumenttypen. Details im Abschnitt "Kopfbereich" unten.
- Neu seit 1.3.6: **Zusammenführung der Layout-Einstellungen** – Betreiber-Entscheidung, dass
  Briefpapier/Ränder/gezeichnete Bausteine für jeden Dokumenttyp außer dem Angebot geteilt gelten,
  statt je Typ eigene Zeilen zu pflegen. Kein neues Feld: `document_type="default"` ist ein
  weiterer, reservierter Wert auf der bestehenden Spalte (Option a, siehe Abschnitt "Gemeinsamer
  Dokumenttyp" unten) – ein künftiger, echter Sonderfall je Dokumenttyp bleibt dadurch möglich.
  Die Mahnung-Zeilen aus 1.3.1/1.3.2 (42mm oberer Rand, verstecktes Logo/Firmenkopf, die beiden
  echten hochgeladenen Briefpapier-Dateien) sind per Migration unverändert in den geteilten Satz
  übernommen worden. Aus "Mahnwesen-Layout" wird der Einstellungen-Eintrag "Dokumente & Layout".
  Details im Abschnitt "Gemeinsamer Dokumenttyp" unten.
- Neu seit 1.3.7: **zweite Etappe des PDF-Umbaus** – die Rechnung (`app/invoice_pdf.py`) wechselt
  auf den gemeinsamen Rahmen (`render_framed_pdf()`, `document_type="invoice"`), Kopfbereich wie
  bei der Mahnung (`build_din5008_header_block()`), eigene Meta-Zeilen (Rechnungsnr./Datum/
  Kunden-Nr./Vorgangs-Nr./Seite – bewusst OHNE Sachbearbeiter, siehe „Bekannte, bewusst offene
  Punkte"). Neu, direkt im Rahmen selbst (nicht im Renderer): eine abschaltbare
  **Wiederholungszeile auf Folgeseiten** (vierter gezeichneter Baustein `continuation_header`,
  fest oberhalb von Logo/Firmenkopf positioniert, Seitenzahl über denselben 1.3.4/1.3.5-
  Zweidurchlauf-Mechanismus wie der Meta-Block). Angebot, Auftrag und Einsatzbericht bleiben
  vollständig unangetastet. Bei der Verifikation gegen die echte Datenbank zwei Funde: die tote
  `Invoice.caseworker_employee_id`-Spalte (siehe „Bekannte, bewusst offene Punkte") und eine
  bereits seit 1.3.1 latente Überlagerung zwischen der Fußzeile und einem echten, hochgeladenen
  Briefpapier -- letztere in 1.3.8 behoben, siehe dort. Details im Abschnitt "Gemeinsamer
  Dokumenttyp" unten.
- Neu seit 1.3.8: **Fehlerbehebung** – `footer_text` (Seitenzahl) steht im gemeinsamen Standard
  jetzt auf `visible=False` (kleinstmögliche Lösung für den 1.3.7-Fund): sie zeichnet an einer
  FESTEN Position, unabhängig vom Randabstand, und lief deshalb einem echten Briefbogen in dessen
  eigenen, aufgedruckten Fußbereich. `continuation_header` bleibt Standard AN. Die bereits
  gesäte "default"-Zeile in der echten Datenbank musste dafür nachträglich korrigiert werden
  (mit `update_layout_block()`, kein rohes SQL) -- derselbe Nachkorrektur-Mechanismus wie in
  1.3.2. Details im Abschnitt "Gemeinsamer Dokumenttyp" unten.
- Neu seit 1.3.9: **Positionstabelle der Rechnung** – an einer echten Schlussrechnung gemeldet,
  vier Punkte vor dem geplanten Auftrags-Umbau behoben. Die drei Mengenspalten "Menge (Soll)"/
  "Ist (gesamt)"/"abger. Menge" weichen einer einzigen Spalte "Menge" (die tatsächlich
  abgerechnete Menge) mit neuer Einheiten-Spalte "EH" daneben -- exakt das Muster, das
  `order_pdf.py`/`quote_layout_pdf.py` für dieselbe Spalte bereits verwenden (eine einzelne,
  gemeinsame Spaltenüberschrift "Menge Einh." existiert dagegen nirgends im Code, das war ein
  Beschreibungsfehler im Musterdokument). Soll/Ist/abgerechnet bleiben auf der Bildschirmansicht
  (`invoice_detail.html`) weiterhin alle drei sichtbar, nur das PDF wurde reduziert. Neue,
  öffentliche Funktion `document_frame.py::frame_content_width()` liefert ab jetzt die
  tatsächlich konfigurierte Innenbreite (statt des hart codierten `PAGE_CONTENT_WIDTH`) --
  behebt eine real nachgemessene Fehlausrichtung der Positionstabelle (zu breite `colWidths`,
  dazu reportlabs `Table`-Standard `hAlign="CENTER"`), betrifft beide bereits umgestellten
  Renderer (Mahnung, Rechnung) gleichermaßen. Die Langtext-Farbe (`#666666`) wurde geprüft und
  bewusst NICHT geändert -- dieselbe Kombination aus kleinerer Schrift und Grauton findet sich
  identisch in allen vier LV-Positionstabellen-Renderern, klar eine wiederholte Gestaltungsabsicht,
  kein Überbleibsel. Details im Abschnitt "Gemeinsamer Dokumenttyp" unten.
- Neu seit 1.3.10: **vierte Etappe des PDF-Umbaus, der Auftrag** – `order_pdf.py` wechselt auf den
  gemeinsamen Rahmen (`render_framed_pdf()`, `document_type="order"`), Kopfbereich wie bei
  Mahnung/Rechnung über `build_din5008_header_block()`. Dieselbe 1.3.9-Breitenkorrektur (185mm-
  `colWidths`-Summe → `frame_content_width()`) betraf den Auftrag identisch, dazu ein dritter,
  nur hier auftretender Effekt: der alte `SimpleDocTemplate`-Renderer hatte ein ungenulltes
  6pt-Frame-Innenpolster (reportlab-Vorgabe), das mit dem Rahmenumbau automatisch entfällt.
  Sachbearbeiter/Projektleiter sind beim Auftrag – anders als bei der Rechnung – tatsächlich in
  Gebrauch und bleiben sichtbar, jetzt aber unabhängig voneinander (vorher nur als feste
  Zweier-Paarung in einer Zeile). Geprüft, bevor gebaut wurde: `order_to_dict()`/`order_pdf.py`
  lesen nirgends `order.project.customer` live, sondern ausschließlich den bei Beauftragung
  eingefrorenen Schnappschuss – als Regressionstest festgehalten. Kein Auftrag wurde bisher per
  E-Mail versendet (0 von 5 in der echten Datenbank), ohnehin ohne GoBD-Relevanz, da das PDF nie
  gespeichert, sondern bei jedem Versand/Download live erzeugt wird. Mit dem Auftrag sind drei
  Renderer auf denselben Summenblock-Aufbau umgestellt – ein gemeinsamer Baustein dafür ist
  vorgeschlagen, aber bewusst noch nicht gebaut. Angebot und Einsatzbericht bleiben unangetastet.
  Details im Abschnitt "Gemeinsamer Dokumenttyp" unten.
- Neu seit 1.3.11: **fünfte Etappe des PDF-Umbaus, der Einsatzbericht** – `service_report_pdf.py`
  wechselt auf den gemeinsamen Rahmen (`document_type="service_report"`, dafür neu sowohl in
  `RENDERERS_USING_SHARED_FRAME` als auch in `DOCUMENT_TYPES`, app/document_layout.py). Alle
  KeepTogether-Blöcke aus 1.2.21 (Unterschrift, Mängel, Prüfpunkt-Gruppen, Fotos) bleiben
  bestehen und funktionieren nachweislich weiter – geprüft an einem eigens erzeugten,
  elfseitigen Bericht mit 12 Mängeln/Fotos, seitenweise als Bild durchgesehen, nichts gerissen.
  Zwei echte Tabellenbreiten-Funde (Vorher/Nachher-Fototabelle UND die zweispaltige
  Unterschriften-Tabelle, beide 190mm statt 176mm) behoben, Fotobreite folgt jetzt ebenfalls
  `frame_content_width()` (Kappung nach unten, keine Vergrößerung). Bei der Snapshot-Prüfung
  (wie beim Auftrag in 1.3.10) zwei echte Funde, anders als beim Auftrag:
  `finding.roof_component.name`/`link.roof_area.name` lesen den AKTUELLEN Namen live, keine
  eingefrorene Kopie existiert dafür im Datenmodell – gemeldet, nicht behoben (siehe „Bekannte,
  bewusst offene Punkte"). Angebot bleibt unangetastet, damit sind jetzt alle Dokumenttypen außer
  dem Angebot auf dem gemeinsamen Rahmen. Details im Abschnitt "Gemeinsamer Dokumenttyp" unten.
- Neu seit 1.3.12: **zwei Funde aus 1.3.11 behoben.** Die Wiederholungszeile auf Folgeseiten
  sitzt nicht mehr fest bei 8mm von oben, sondern liest ihre Position tatsächlich aus dem
  bestehenden `DocumentLayoutBlock.y_mm`/`height_mm` des `continuation_header`-Bausteins –
  einstellbar über dieselbe Oberfläche wie die Sichtbarkeit (Einstellungen → Dokumente & Layout),
  kein neues Feld im Datenmodell. Am echten Briefpapier nachgemessen: dessen Kopfgrafik reicht bis
  30,8mm von oben – neuer Codestandard 12mm/4mm (passend für einen Briefbogen OHNE eigene
  Kopfgrafik), die bereits gesäte Zeile in der echten Datenbank auf 34mm korrigiert. Zweitens:
  `Finding.roof_component_name_snapshot`/`ServiceReportRoofArea.roof_area_name_snapshot` (neue,
  nullable Spalten, physisch beim Anlegen befüllt, Migration mit Bestandsdaten-Backfill) frieren
  jetzt den Bauteil-/Dachflächennamen zum Zeitpunkt der Anlage ein, im PDF UND in der Anzeige
  bevorzugt gelesen. Bei der zusätzlichen Prüfung auf weitere live gelesene Stellen: Bauteiltyp/
  Dachtyp kein Fund (nur bei der Erzeugung gelesen), Prüfvorlagenbezeichnung UND Mitarbeitername
  (Monteur-Meta-Zeile) sind echte, aber bewusst ungefixte Funde – gemeldet, siehe „Bekannte,
  bewusst offene Punkte". Details in den Abschnitten "Gemeinsamer Dokumenttyp" und
  "Einsatzbericht" unten.
- Neu seit 1.3.13: **letzte Etappe des PDF-Umbaus – das Angebot.** Neuer, paralleler Renderer
  `app/quote_framed_pdf.py` (`render_framed_pdf()`, `document_type="quote"`) – zunächst NEBEN
  dem bisherigen, positionsbasierten `quote_layout_pdf.py` und dem älteren, einfachen
  `quote_pdf.py` gebaut, gegen ein echtes, zweiseitiges Angebot verglichen, zwei dabei gefundene
  Fehler behoben (dazu gleich mehr), erst danach umgestellt – nicht in einem Schritt. Echte,
  neue **Übertragszeile** (gab es vorher in keinem der beiden alten Renderer, nur eine statische
  Fortsetzungs-Beschriftung ohne Betrag): die komplette Positionsliste ist jetzt eine einzige
  `Table`-Unterklasse mit überschriebenem `split()`, damit die Zeile bei JEDEM Seitenumbruch
  innerhalb der Liste erscheint, auch genau zwischen zwei Abschnitten. Zwei echte Funde beim
  Vergleich, beide behoben: ein doppelter Firmenkopf (neuer, ausdrücklich als Übergangslösung
  markierter Parameter `suppress_drawn_blocks` an `render_framed_pdf()`) und ein auf
  Folgeseiten verschwindender Briefbogen (`get_effective_background()` kennt jetzt den
  Altbestandsfall `repeat_on_every_page` auch ohne eigene Folgeseiten-Zeile). Dazu die seit
  1.3.11 fehlende Wiederholungszeile für das Angebot nachgerüstet (Migration `ab5eef23f9ed`,
  34mm am echten Briefpapier gemessen). Umgestellt (Punkt 4) wurden ausschließlich die beiden
  Wege, die beim Kunden ankommen: der reguläre PDF-Abruf (`GET /api/quotes/{id}/pdf`) und der
  E-Mail-Versand (`send_quote_email()`) – die alte Vergleichsansicht
  (`GET /api/quotes/{id}/pdf-layout-preview`) bleibt bewusst erreichbar, ihre beiden
  Vorschau-Buttons sind jetzt deutlich als "entfällt demnächst" beschriftet statt (wie vorher)
  fälschlich "bisherig". Details im Abschnitt "Gemeinsamer Dokumenttyp" unten; die Liste der
  beim späteren Aufräumen entfallenden Dateien/Endpunkte ist gemeldet, aber bewusst noch nicht
  umgesetzt (siehe „Bekannte, bewusst offene Punkte").
- Neu seit 1.3.21: **Mahnwesen vervollständigt.** Zwei gemeldete Lücken behoben, siehe eigener
  Abschnitt "Mahnwesen: Löschen/Versenden/Bearbeiten" unten. (1) "Alle Mahnungen"
  (`mahnwesen.html`) zeigte Entwürfe ohne Versenden-/Löschen-Aktionen, obwohl der Entwurfsstatus
  gerade dort anhand der Statusspalte erkennbar ist -- angebunden über dieselben, bereits
  bestehenden JS-Funktionen wie in "Benötigt Aufmerksamkeit". (2) Ein Mahnungsentwurf ließ sich
  überhaupt nicht bearbeiten -- neu: `update_reminder_draft()`, Schema `ReminderUpdate`, Endpunkt
  `PUT /api/reminders/{id}`, je ein vorausgefülltes Bearbeiten-Panel in `mahnwesen.html` UND
  `invoice_detail.html`. Dazu untersucht, wie sich eine Zahlenänderung auf den bereits
  vorhandenen, live zusammengesetzten Mahntext auswirkt, und bewusst gegen eine neue
  Erkennungsspalte für "manuell bearbeitet" entschieden -- stattdessen ein nicht-blockierender
  Hinweis beim Speichern plus eine um Bedeutungen ergänzte Platzhalterliste im Bearbeiten-Panel,
  siehe „Bekannte, bewusst offene Punkte" für die volle Begründung.
- Neu seit 1.3.22: **letzter loser Faden aus 1.3.12 geschlossen -- Prüfvorlagenbezeichnung im
  Einsatzbericht eingefroren.** Neue, nullable Spalte
  `ServiceReportRoofArea.inspection_template_label_snapshot` (Migration `14b130f9c315`,
  Bestandszeilen aus dem heutigen Namen befüllt, Muster `5149d369dbb6`) -- `_report_roof_areas_to_dicts()`
  liest sie jetzt bevorzugt statt `link.inspection_template.label` live. Bewusst NICHT auf den
  Legacy-Zweig (Berichte von vor 1.2.22) gespiegelt, exakt dieselbe seit 1.3.12 bestehende
  Asymmetrie wie bei `roof_area_name`. Bei der Gelegenheit ein letztes Mal auf weitere live statt
  eingefroren gelesene Stellen im Einsatzbericht geprüft -- kein weiterer Fund, siehe eigener
  Unterabschnitt "Eingefrorene Prüfvorlagenbezeichnung" unten.
- Neu seit 1.3.23: **Breadcrumb Kunde → Projekt → [Angebot|Auftrag|Auftrag → Rechnung]** auf
  `quote_editor.html`/`order.html`/`invoice_detail.html`, nach dem Muster aus `property.html`/
  `roof_area.html` (1.2.18) -- keine dieser drei Seiten hatte bisher eine durchgängige Navigation
  zurück zum Kunden/Projekt (Auftrag/Rechnung hatten je einen einzelnen Rücksprung-Link, das
  Angebot gar nichts). `quote_to_dict()`/`invoice_to_dict()` bekommen dafür die nötigen IDs dazu
  (`order_to_dict()` hatte sie bereits seit 1.2.20). Dazu: **"EP/EUR"/"GP/EUR" jetzt tatsächlich
  über den Werten zentriert** bei Auftrag und Rechnung (Angebot war bereits seit 1.3.16 korrekt) --
  die `ALIGN`-Regel griff bisher nur ab der ersten Positionszeile, nicht auf die Kopfzeile selbst.
  Details zu beidem im Abschnitt "Breadcrumb & Spaltenkopf-Ausrichtung (1.3.23)" unten. Bei
  derselben Gelegenheit geprüft, ob die seit 1.2.20 bestehende "Einsatzberichte"-Spalte in der
  Auftragstabelle von `project_folder.html` noch funktioniert -- ja, unverändert (Modul aktiv,
  echte Berichte/Aufträge in der Produktionsdatenbank stichprobenhaft verknüpft bestätigt), keine
  Änderung nötig.
- Neu seit 1.3.24: **drei weitere Punkte aus dem laufenden Betrieb, jeweils erst ein Befund
  berichtet, dann nach Rückmeldung umgesetzt** -- Details im Abschnitt "Direkteinstieg,
  Katalogauswahl, Pauschale Abschlagsrechnung (1.3.24)" unten. (1) Direkteinstieg vom Dashboard
  zu einer konkreten Aufgabe/Anfrage/einem Abwesenheitsantrag (`?task=`/`?inquiry=`/`?absence=`,
  Muster `?report=` aus 1.2.22) -- bewusst drei eigene, kleine Umsetzungen statt eines
  gemeinsamen JS-Bausteins, siehe dortige Begründung. (2) Katalog-Dropdown im Angebotseditor
  (vorher wurden ALLE Kataloge ungefiltert durchsucht, nicht -- wie zunächst vermutet -- ein
  einzelner fest verdrahteter) mit "Alle Kataloge"-Option und Katalogherkunft je Treffer
  (`GET /api/services` liefert dafür jetzt `catalog_id`/`catalog_name` mit). (3) Pauschale
  Abschlagsrechnungen bekommen eine einzige, reine Projektions-Position (nie unabhängig
  editierbar) statt gar keiner -- vor dem Bauen geprüft: 2 bereits existierende, beide bereits
  versendet, bewusst OHNE nachträgliche Migration (würde ein bereits verschicktes PDF rückwirkend
  verändern).
- Neu seit 1.3.25: **"Leistungen ansehen" führte auf die Startseite statt auf den Katalog** --
  `master_data.html`/`service_form.html` verlinkten auf `/?catalog_id=<id>`, ein Ziel, das diesen
  Parameter nirgends auswertet. Beim Beheben eine bereits bestehende, bisher in dieser Datei nie
  dokumentierte Seite gefunden: `/leistungskatalog` (Sidebar-Eintrag "Leistungskatalog",
  `app/templates/index.html`) ist die tatsächliche, vollständige Leistungsverwaltung (Suche,
  Bearbeiten, Verschieben/Kopieren zwischen Katalogen, Kalkulationsdetail mit Materialstückliste,
  XML-Import, globale Kalkulationsvorgaben) -- der Fehler war ein fehlendes Pfadsegment, keine
  fehlende Seite; eine dafür zunächst probeweise gebaute, redundante "Leistungen"-Ansicht
  innerhalb der Stammdatenverwaltung wurde deshalb wieder verworfen. Details im neuen Abschnitt
  "Leistungskatalog vs. Stammdaten (seit 1.3.25)" unten -- dort auch der Befund einer im selben
  Zug angefragten, noch unentschiedenen Sidebar-Bestandsaufnahme (keine Codeänderung).
- Neu seit 1.3.26: **Sidebar aufgeräumt, nach der 1.3.25-Bestandsaufnahme, mit vier Anmerkungen
  vom Nutzer umgesetzt.** Mitarbeiter-Anlegen/-Bearbeiten lebt jetzt ausschließlich auf `/employees`
  (der Sidebar-Eintrag "Mitarbeiter" entfällt, Stammdaten → "Mitarbeiter" leitet dorthin um,
  `master_data_form.html`s eigenes, schlankeres Mitarbeiterformular wurde entfernt) -- dabei einen
  echten, sonst verschwundenen Funktionsverlust gefunden und noch vor dem Abschluss behoben:
  `show_on_planning_board` (Plantafel-Sichtbarkeit) existierte auf `/employees` bisher gar nicht.
  Die vom Nutzer selbst als Verdacht nachgereichte zweite Doppelung (globale Kalkulationsvorgaben
  in `/leistungskatalog` UND in Einstellungen → Kalkulationsgrundlagen) wurde vor jeder Änderung
  geprüft und bestätigt: dieselbe Tabelle, dieselbe Zeile, dieselben Felder, derselbe Endpunkt
  (`GET/PUT /api/calculation-settings`) -- kein zweiter Datensatz, keine Divergenzgefahr. Die Karte
  in `/leistungskatalog` entfällt deshalb zugunsten eines Verweises auf die Einstellungen. Die
  beiden Sidebar-Gruppen am Ende ("Stammdaten"/"System") bekommen sichtbare Überschriften nach dem
  Muster von `settings.html`. Backoffice bleibt bei Zeiterfassung. Details, inkl. der Begründung
  für die letzten beiden Punkte und dem verbleibenden, jetzt geschrumpften Rest-Befund, im
  erweiterten Abschnitt "Leistungskatalog vs. Stammdaten" unten.
- Neu seit 1.3.27: **letzter Schritt des Sidebar-Aufräumens -- "Leistungskatalog" entfällt aus der
  Sidebar.** Vor dem Bauen geprüft (wie verlangt): eine eigene neue Ansicht in den Stammdaten war
  NICHT nötig, `/leistungskatalog` funktioniert bereits ohne `catalog_id` sinnvoll (XML-Import,
  Kalkulationsvorgaben-Verweis, katalogübergreifende Leistungsliste samt Suche). Stattdessen: die
  Stammdaten-Katalogliste verlinkt jetzt zusätzlich den parameterlosen Einstieg (Muster "alle
  Materialien anzeigen"), `/leistungskatalog` bekommt eine Rückwärtsnavigation zu den Stammdaten
  (Muster `/employees` aus 1.3.26). Dabei ein Randbefund gemeldet und auf Wunsch im selben Zug
  behoben: sowohl die Leistungs- als auch die Materialliste hatten eine mit "Katalog"
  beschriftete Spalte, die tatsächlich Aktionen zeigte, nicht den Herkunftskatalog der Zeile --
  behoben, indem eine echte Katalog-Spalte ergänzt und die Aktionsspalte umbenannt wurde. Details
  im erweiterten Abschnitt "Leistungskatalog vs. Stammdaten" unten.
- Neu seit 1.3.28: **vierter Fall derselben Aufräumreihe -- Benutzer und Änderungshistorie
  entfallen aus der Sidebar.** Anders als bei Mitarbeitern/Kalkulationsvorgaben gab es hier keine
  zwei konkurrierenden Bearbeitungsoberflächen zum Vergleichen: `settings.html` hatte für beide
  nie einen eigenen Datenbereich, nur einen reinen Navigationslink zu den ohnehin bereits
  bestehenden, alleinigen Seiten `users.html`/`history.html` -- die "vollständigere Oberfläche"
  ist deshalb trivial die jeweils einzige echte Seite. Umgesetzt: Sidebar-Direktlinks entfernt,
  Rückwärtsnavigation "← Einstellungen" auf beiden Seiten ergänzt (Muster `/employees`/1.3.26,
  `/leistungskatalog`/1.3.27). Dabei zwei Nebenbefunde: ein bei der 1.3.26-Migration liegen
  gebliebener toter Link (`/master-data#employees`, Hash-View existiert seit 1.3.26 nicht mehr)
  auf `/employees` korrigiert; `/time-backoffice` ist ebenfalls doppelt verlinkt, bleibt aber
  bewusst unverändert, da es fachlich zur täglichen Sidebar-Gruppe gehört (1.3.26-Entscheidung),
  nicht zur System-Gruppe wie Benutzer/Historie. Bei der abschließenden erneuten Vollprüfung der
  Sidebar gegen die Einstellungen kein weiterer Fund. Details im erweiterten Abschnitt
  "Leistungskatalog vs. Stammdaten" unten.
- Neu seit 1.3.29: **gemeldeter Ausreißer behoben -- `/employees` zeigte beim Einstieg direkt das
  Anlegeformular statt zuerst die Liste**, anders als jeder andere Stammdatenbereich. Ursache: die
  Seite bestand (schon vor der 1.3.26-Migration) aus einem zweispaltigen Layout mit Formular UND
  Liste gleichzeitig sichtbar, das Formular immer im Anlegen-Zustand vorbelegt. Umgebaut auf
  dasselbe Muster wie überall sonst (Liste zuerst, Formular blendet sich erst nach "+ Neuer
  Mitarbeiter"/"Bearbeiten" ein, schließt sich nach Speichern/Abbrechen wieder) -- Vergütungsrechner,
  `show_on_planning_board` und alle übrigen Formularfelder blieben dabei unangetastet, nur ihre
  Sichtbarkeit beim Laden ändert sich. Beim erneuten Abgleich der übrigen Stammdatenbereiche
  (Kunden, Objekte, Teams, Fuhrpark, Lieferanten, Kataloge, Materialien) kein weiterer Ausreißer
  gefunden -- alle laufen bereits über `master_data.html` als Liste mit ausgelagertem Formular.
  Details im Abschnitt "Mitarbeiter-Formular list-first" unten.
- Neu seit 1.3.30: **Mitarbeiter zurück in `master_data.html`/`master_data_form.html` --
  Regel 10 festgehalten.** Die 1.3.29-Korrektur (list-first auf der eigenen `/employees`-Seite)
  behob nur das eine gemeldete Symptom, ließ aber zwei weitere Abweichungen vom Stammdaten-Muster
  stehen: die gemeinsame Stammdaten-Navigation fehlte (nur ein Zurück-Link), und Anlegen/Bearbeiten
  blendeten ein Formular ein statt eine eigene Seite zu öffnen. Vor dem Bauen geprüft (wie
  verlangt), ob sich `/employees` überhaupt in `master_data.html`/`master_data_form.html`
  einfügen lässt, statt das Muster für Mitarbeiter separat nachzubauen: kein Feld, kein Endpunkt
  und keine Interaktion gefunden, die sich dort nicht unterbringen lässt -- der Vergütungsrechner
  zerfällt sauber in aggregierte Kennzahlen (wandern in die Liste) und eine Live-Vorschau im
  Formular (wandert unverändert in `master_data_form.html`). Mitarbeiter ist damit wieder ein
  regulärer Stammdatenbereich wie jeder andere, `employees.html` und die eigene Route entfallen
  vollständig. Dabei EIN neues, dauerhaftes CLAUDE.md-Prinzip ergänzt (Regel 10, siehe oben):
  jeder Stammdatenbereich -- auch jeder künftige -- zeigt beim Einstieg die Liste, trägt die
  Stammdaten-Navigation, Anlegen/Bearbeiten öffnen immer eine eigene Formularseite. Details im
  Abschnitt "Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher" unten.
- Neu seit 1.3.31: **Adressimport aus dem Altsystem** (`app/address_import.py`,
  `app/routers/address_import.py`, `/address-import`, verlinkt aus Einstellungen → neue Gruppe
  "Importe"). Dreistufig (Hochladen → Vorschau → Bestätigen), CSV und Excel (.xlsx, neue
  Abhängigkeit `openpyxl`), Wiedererkennung bereits importierter Zeilen über eine neue Spalte
  `legacy_address_number` (direkt auf `Customer`/`Supplier`). Nicht zuordenbare Adressen landen in
  einer neuen, gemeinsamen Tabelle `ImportedAddress` (dient zugleich als Vorschau-Zwischenspeicher
  UND als dauerhafte Arbeitsliste mit drei Auflösungen: Objekt bei bestehendem Kunden, neuer Kunde,
  verwerfen). Ein `ImportRun` je bestätigtem Lauf ermöglicht ein alles-oder-nichts-Rückgängigmachen,
  solange an keinem dabei erzeugten Kunden/Lieferanten schon etwas hängt. Dabei eine deutlich
  größere Datenmodell-Änderung als ursprünglich für einen Import erwartet: `Customer.name` ist seit
  dieser Version kein direkt eingegebenes Feld mehr, sondern wird aus neuen Feldern
  `salutation`/`title`/`first_name`/`last_name` zusammengesetzt (`last_name` das eigentliche
  Pflichtfeld) -- betraf beim Umbau 61 Konstruktionsaufrufe in 44 Testdateien. Zusätzlich neu:
  `Customer.country`/`.mobile`/`.email_2` (zweite E-Mail-Adresse, bewusst rein informativ) und
  `Property.country`. Details, inkl. der vier vorab abgestimmten Berichtspunkte und der Begründung
  für die Namensfeld-Entscheidung, im neuen Abschnitt "Adressimport aus dem Altsystem" unten.
- Neu seit 1.3.32: **Objekte: Hauptadressen kennzeichnen und ausblenden.** Der Adressimport
  (1.3.31) hatte die Stammdaten-Objektliste mit reinen Hauptadress-Kopien überflutet -- neues,
  robustes `Property.is_primary_address`-Flag (statt Namensvergleich `name == "Hauptadresse"`)
  löst das auf, gesetzt ausschließlich dort, wo eine Hauptadresse automatisch entsteht
  (`create_customer()`/`update_customer()`, `_create_customer_from_row()`). Migration `2fffb80e5567`
  markiert den Bestand konservativ nur, wenn Name UND Adresse mit dem Kunden übereinstimmen (161
  von 163 Objekten, 0 unsichere Fälle) -- vor dem Schreiben wie verlangt berichtet. Ausgeblendet
  (mit Wiedereinblenden-Möglichkeit bzw. weil eine redundante Alternative schon existiert):
  Stammdaten-Objektliste, `findings.html`-Filter, Wartungsvertrags-Objektauswahl. Bewusst NICHT
  ausgeblendet: Projekt-/Anfrage-Objektauswahl (dort ändert die Wahl den eingefrorenen
  Auftrags-Schnappschuss tatsächlich) und die Kundenseite selbst (zeigt weiter alle Objekte,
  markiert die Hauptadresse nur noch über das Flag statt den Namen). Dabei ein Nebenbefund
  behoben statt nur gemeldet: `_copy_quote_scope_to_order()` (`app/orders.py`) schrieb für einen
  Wartungsvertrag ohne Objekt bisher `None` statt, wie `contract_to_dict()` es für die Anzeige tut,
  "Hauptadresse" -- ein per Schnellauftrag erzeugter Auftrag zeigte dadurch gar kein Objekt.
  Details im neuen Abschnitt "Objekte: Hauptadressen kennzeichnen und ausblenden" unten.
- Neu seit 1.3.33: **Geheimnisse für den Serverbetrieb -- `ERP_SECRET_KEY`/`ERP_DATA_DIR`
  tatsächlich genutzt.** Vorbereitung für den Umzug auf einen echten Server (siehe
  Git-Einrichtung): `ERP_SECRET_KEY` wurde bereits vorrangig gelesen, `data/.erp_secret` bereits
  automatisch nur als Rückfall erzeugt, `DATABASE_URL` funktionierte bereits vollständig -- neu
  ist ausschließlich `app/paths.py::data_dir()`, das jetzt auch die sieben bisher unabhängigen
  Upload-Pfade (Firmenlogo, Briefpapier-Hintergründe, Kunden-/Projektdateien, Dachflächen-
  Skizzen, Einsatzbericht-Fotos/-Unterschriften) unter `ERP_DATA_DIR` zusammenfasst -- jeweils
  weiterhin mit eigenem, spezifischerem Override erster Priorität. Dabei eine echte
  Inkonsistenz behoben: die beiden bereits bestehenden `ERP_DATA_DIR`-Leser lösten ihren
  Rückfall relativ zum ARBEITSVERZEICHNIS auf, die sieben Upload-Pfade dagegen relativ zur LAGE
  DER DATEI SELBST -- `data_dir()` vereinheitlicht das dateibasiert, damit ein künftiger
  Serverstart mit anderem Arbeitsverzeichnis nicht stillschweigend einen anderen Ordner trifft.
  Neue Funktion `warn_if_secret_key_mismatches_file()` (`app/auth.py`, beim Start aufgerufen)
  warnt undramatisch (kein Abbruch, gibt den Schlüssel nie aus), wenn `ERP_SECRET_KEY` von einer
  bereits bestehenden `data/.erp_secret` abweicht -- genau der Fall, der auf einem Server mit
  übernommener Datenbank bereits verschlüsselte SMTP-/Microsoft-365-Zugangsdaten unlesbar macht.
  Details im Abschnitt "Geheimnisse für den Serverbetrieb" unten.
- Neu seit 1.3.34: **Anmeldesicherheit für den Onlinebetrieb.** Drei Teile: (1) die
  Anmeldesperre gegen Brute-Force ist jetzt persistent (`FailedLoginAttempt`-Tabelle, automatisch
  aufgeräumt) statt eines In-Memory-Zählers, der bei mehreren uvicorn-Workern je Prozess separat
  gezählt hätte, und prüft zusätzlich zur Benutzernamen-Sperre eine unabhängige IP-Sperre gegen
  rotierende Benutzernamen. (2) **Verpflichtende Zwei-Faktor-Authentifizierung (TOTP) für
  Administratoren** (`app/two_factor.py`, `pyotp`+`qrcode[pil]`, beide reine Pip-Pakete ohne
  Systemabhängigkeit) -- ein zweites, unabhängiges Cookie (`dk_erp_otp_ok`) belegt den bereits
  geprüften zweiten Faktor DIESER Sitzung; ohne dieses Cookie bleibt für einen Administrator nur
  "Mein Konto" und Abmelden erreichbar. Nichts wird aktiv, bevor nicht ein echter Code bestätigt
  wurde -- ein abgebrochener Einrichtungsversuch hinterlässt nie einen halb aktiven Zustand.
  Zehn einmalige Wiederherstellungscodes, ein Administrator kann den zweiten Faktor eines
  ANDEREN (nicht des eigenen) Administrators zurücksetzen, plus ein Notfall-Kommandozeilenskript
  `scripts/reset_admin_2fa.py` für den Fall, dass auch die Wiederherstellungscodes fehlen. (3)
  **Neue Selbstbedienungsseite "Mein Konto"** (`/account`) -- vorher konnte niemand sein eigenes
  Passwort selbst ändern. Details im neuen Abschnitt "Anmeldesicherheit für den Onlinebetrieb"
  unten.
- Neu seit 1.3.35: **PostgreSQL-Umstieg, erste Reparaturrunde -- nur die Migrationskette, noch
  kein Datenumzug.** Fünf Punkte: die bisher komplett leere Migration `e057d15af828` legt
  `invoices`/`invoice_items` jetzt tatsächlich an (vorher ein reiner `create_all()`-Autogenerate-
  Blindfleck, siehe eigener Abschnitt "PostgreSQL-Umstieg" unten für die volle Herleitung);
  `datetime('now')` und rohe Boolean-Literale (`1`/`0`) in insgesamt neun Migrationen durch
  dialektneutrale, gebundene Parameter ersetzt; `app/audit.py`s `.contains()` (case-insensitive
  nur unter SQLite) auf `.ilike()` umgestellt. Erstmals tatsächlich gegen eine leere PostgreSQL-
  17-Datenbank verifiziert -- alle 55 Migrationen liefen durch, siehe "Migrations-Workflow"
  unten für den Bezugspunkt. Datenumzug, Backup-Skript-Umbau und die Abschaltung von
  `create_all()` im Produktionsbetrieb bleiben ausdrücklich spätere, eigene Schritte.
- Neu seit 1.3.36: **Datenumzugsskript, erste Runde -- nur lokal erprobt.**
  `scripts/migrate_sqlite_to_postgres.py` (neu, neben `reset_admin_2fa.py`) kopiert die reale,
  ausschließlich lesend geöffnete `dachkonzepte_erp.db` tabellenweise nach PostgreSQL, verweigert
  eine bereits nicht-leere Zieldatenbank ohne ausdrückliches `--force-truncate`, prüft
  Fremdschlüssel-Konsistenz und setzt alle Sequenzen zurück. Echter, über dieses Skript
  hinausgehender Fund: `ALTER TABLE ... DISABLE TRIGGER ALL` (ursprünglicher Plan gegen die
  beiden selbstreferenzierenden Tabellen) braucht Superuser-Rechte, die eine Anwendungsrolle auf
  einem gehosteten Server nicht hat -- ersetzt durch einen rechtefreien, mehrstufigen Ladevorgang.
  Gilt als Grundsatz für jedes künftige Skript gegen PostgreSQL, siehe Abschnitt
  "PostgreSQL-Umstieg" unten. Lauf gegen die lokale `spielwiese`-Instanz erfolgreich (121
  Tabellen, 3040 Zeilen, 0 Abweichungen), Anwendung danach tatsächlich gegen PostgreSQL
  gestartet und die üblichen Lesepfade sowie das Anlegen eines neuen Kunden (Sequenz-Test)
  bestätigt. Der Umzug auf den Server selbst bleibt ein eigener, späterer Schritt.
- Neu seit 1.3.37: **Produktivbetrieb seit 14.09.2026** -- das ERP läuft seither auf einem
  echten Server, siehe eigener Abschnitt "Produktivbetrieb" unten für die vollständigen
  Rahmenbedingungen (zwei Umgebungen, Speicherbudget, der Weg einer Änderung auf den Server,
  was das für Migrationen heißt). Zwei der zuvor bewusst zurückgestellten Punkte umgesetzt:
  `Base.metadata.create_all()` läuft nicht mehr, wenn `ERP_ENV=production` gesetzt ist (die
  Migrationskette ist dort seither die einzige Quelle für das Schema), und
  `backup_windows.ps1` ist jetzt ausdrücklich als lokal-Windows-only gekennzeichnet -- der
  Server hat sein eigenes, unabhängiges Backup. Dazu zwei echte Nebenbefunde vom
  Erstaufsetzen behoben: die Verwechslungsgefahr `postgresql+psycopg` vs.
  `+psycopg2` in `requirements.txt`/`.env.example` beseitigt, und in CLAUDE.md festgehalten,
  dass `data/.erp_secret` niemals gelöscht werden darf, solange verschlüsselte Werte in der
  Datenbank stehen.
- Neu seit 1.3.38: **Firmenlogo in der Sidebar statt des Schriftzugs "DACHKONZEPTE"** --
  Befund vor dem Bauen ergab zwei Überraschungen: es gab noch nie ein hochgeladenes Logo, und es
  gab (trotz seit 1.0.58 bestehendem Upload-Endpunkt) gar keine Oberfläche dafür. Auf Rückfrage
  eine minimale Upload-Oberfläche in Einstellungen → Unternehmensstammdaten ergänzt. Kein
  zweiter, eigener Sidebar-Logo-Upload -- die Sidebar zeigt dasselbe Firmenlogo wie PDFs/das
  PWA-Icon, über eine neue, bewusst austauschbare Funktion
  (`app/company_logo.py::sidebar_logo_filename()`) und einen neuen Jinja-Global
  (`sidebar_logo_url()`). Ohne Logo bleibt der Schriftzug. Details im neuen Abschnitt
  "Firmenlogo in der Sidebar" unten.
- Neu seit 1.3.39: **Echter CSS-Fehler behoben, Sidebar-Logo-Höhe einstellbar.** `height` +
  `max-width` + `object-fit:contain` auf demselben `<img>` verkleinert bei einem breiten Logo
  die Höhe wieder (CSS-Ersatzelement-Auflösung verwirft die feste Höhe, sobald `max-width`
  eingreift) -- behoben durch einen umschließenden Wrapper (`overflow:hidden`), der ein zu
  breites Logo abschneidet statt es zu verkleinern. Neues Feld "Anzeigehöhe" (24-80px,
  Standard 48) in Einstellungen → Unternehmensstammdaten. An der tatsächlich hochgeladenen
  Datei geprüft, ob ein zweiter, eigener Sidebar-Upload nötig ist (Nutzerannahme: "Bildzeichen
  mit Schriftzug darunter") -- Ergebnis: die Datei enthält gar keinen Schriftzug, nur ein
  einzelnes geometrisches Symbol. Mehr Höhe reicht, kein zweiter Upload gebaut. Details im
  Abschnitt "Firmenlogo in der Sidebar" unten.
- Neu seit 1.3.40: **Verkleinerte Anzeige-Rendition fürs Firmenlogo.** Die reale Logo-Datei war
  8000×5295px/252KB -- bei jeder Seitenanfrage (klassische Mehrseiten-Navigation, keine SPA)
  wurden davon bisher die vollen 42 Megapixel geladen UND dekodiert, nur um sie auf 24-80px
  Höhe darzustellen. `replace_logo()` erzeugt seither zusätzlich zur unveränderten
  Originaldatei (weiterhin für PDFs/das PWA-Icon) eine auf max. 480px Kantenlänge verkleinerte
  Anzeige-Rendition -- `GET /api/settings/general/logo` (der einzige HTTP-Auslieferungsweg)
  liefert bevorzugt diese. Real gemessen: 258.475 → 19.530 Bytes (Faktor ~13), 42,4 Mio. → 153.000
  Pixel (Faktor ~278). Details im Abschnitt "Firmenlogo in der Sidebar" unten.
- Neu seit 1.3.41: **`backup_windows.ps1`-Vorfall behoben.** Die automatische Bereinigung nahm
  bisher JEDEN Ordner unter `Backup\` in die Rotation auf, nicht nur die eigenen -- ein dort
  ohne Bezug zum Skript abgelegter Ordner (`Server`, Kopien der Server-Sicherungen) wurde
  dadurch real gelöscht (kein Datenverlust, dieselben Sicherungen lagen unverändert auf dem
  Produktivserver). Bereinigung filtert seither zusätzlich auf das eigene Namensmuster. Neue
  Regel in Regel 9 unten: unter `Backup\` dürfen ausschließlich vom Skript selbst erzeugte
  Ordner liegen.
- Neu seit 1.3.42: **Zwei reale Vorfälle beim Ausliefern von 1.3.38–1.3.41 behoben.** (1)
  `alembic upgrade head` lief auf dem Server ohne geladene Umgebungsvariablen und migrierte
  dadurch stillschweigend nicht die echte Datenbank -- `alembic/env.py` verlangt `DATABASE_URL`
  seither unbedingt direkt aus der Umgebung, kein Rückfall mehr wie bei `app/database.py`, und
  der dokumentierte Bereitstellungsablauf hat seine beiden verlorengegangenen Zeilen
  (`source .env`, `alembic current`) zurück. (2) Ein fehlgeschlagener Logo-Upload legte danach
  jede Seite lahm, einschließlich der Anmeldeseite -- neue `validate_logo_image()` prüft die
  Datei jetzt tatsächlich per Pillow statt nur den spoofbaren `content_type`-Header (400 statt
  500 bei Ungültigem), und alle vier Jinja-Globals in `app/routers/pages.py`
  (`get_theme()`/`is_module_enabled()`/`sidebar_logo_url()`/`sidebar_logo_height_px()`) fangen
  seither jede Ausnahme ab und fallen auf einen sicheren Wert zurück. Details im Abschnitt
  "Produktivbetrieb" → "Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41" unten.
- Neu seit 1.3.43: **Korrektur zu 1.3.39 -- das Firmenlogo enthält doch einen Schriftzug**
  ("DACHKONZEPTE GmbH"/"RÖDCHEN" unterhalb des Dachzeichens, von der damaligen
  Alphakanal-Bounding-Box-Auswertung nicht erkannt) -- deshalb jetzt ein eigener, dedizierter
  Sidebar-Logo-Upload (`GeneralSettings.sidebar_logo_filename`, eigener Ordner unter
  `ERP_DATA_DIR`, neue Endpunkte `POST/GET/DELETE /api/settings/general/sidebar-logo`), nach dem
  Muster des bestehenden Firmenlogo-Uploads. `company_logo.py::sidebar_logo_filename()` löst
  seither drei statt zwei Stufen auf (Sidebar-Logo → Firmenlogo → Schriftzug) und liefert dafür
  ein `SidebarLogoReference`-Tupel statt eines nackten Dateinamens -- beide Logos liegen in
  getrennten Ordnern hinter getrennten Auslieferungsrouten. Die 1.3.42-Ausnahmesicherheit des
  zugehörigen Jinja-Globals bleibt dabei vollständig erhalten. Einstellungen trennen "Firmenlogo"
  (PDFs, PWA-Icon) und "Sidebar-Logo" (nur Navigation) jetzt in zwei eigene Abschnitte. Details
  im Abschnitt "Firmenlogo in der Sidebar" → "Korrektur: doch ein Schriftzug" unten.
- Neu seit 1.3.44: **Umgestaltung der Sidebar, Schritt 1 von vier.** Das Logo steht jetzt allein
  im Kopfbereich, zentriert, mit der vollen verfügbaren Breite (Breitenbegrenzung von festen
  200px auf relatives `max-width:100%` umgestellt) -- vorher teilte es sich den schmalen Kopf mit
  den beiden Schaltflächen für Hell/Dunkel und Ein-/Ausklappen. Einstellbare Höhe jetzt 24-120px
  (vorher 24-80), Standardwert 64 (vorher 48). Die eingeklappte Sidebar (60px) bekommt eine
  eigene, feste, kleinere Logo-Höhe (32px) statt der einstellbaren. Die beiden Schaltflächen sind
  in den unteren Bereich gewandert, direkt über dem Benutzer-/Abmelden-Block -- "Mein Konto"
  bleibt vorerst, wo es ist. Topbar, Suche und Schnellzugriff folgen einzeln in späteren
  Schritten. Details im neuen Abschnitt "Umgestaltung der Sidebar" unten.
- Neu seit 1.3.45: **Umgestaltung der Sidebar, Schritt 2 von vier -- die Topbar.** Eine
  waagerechte, beim Scrollen sichtbare Leiste (`_topbar.html`, neu) sitzt jetzt oberhalb des
  Inhaltsbereichs auf allen 31 Seiten mit Sidebar (bewusst NICHT auf `/vor-ort`, siehe Abschnitt
  unten) -- links bleibt in diesem Schritt Platz für die in Schritt 3 folgende Suche reserviert,
  rechts steht ein runder Kontoknopf mit den Initialen des angemeldeten Benutzers (`app/
  auth.py::resolve_account_display()`, bevorzugt aus dem verknüpften `Employee`, sonst dem
  Benutzernamen). Ein Klick öffnet ein Menü mit vollem Namen, "Mein Konto" und "Abmelden" --
  "Abmelden" bleibt zusätzlich unten in der Sidebar. Fünfter, ebenso ausnahmegesicherter
  Jinja-Global `account_display()` (Prinzip aus 1.3.42). Details im Abschnitt "Umgestaltung der
  Sidebar" → "Schritt 2: Topbar" unten.

## Produktivbetrieb (seit 14.09.2026)

Das ERP läuft seit diesem Tag auf einem echten Server, nicht mehr nur lokal auf Tobias'
Windows-Rechner. Das ändert die Rahmenbedingungen für alles, was künftig gebaut wird -- dieser
Abschnitt hält sie fest, damit eine neue Sitzung nicht erst am Betrieb selbst lernen muss, was
davor nur Theorie war.

### Die zwei Umgebungen

- **Entwicklung**: Windows-Rechner (`C:\DACHKONZEPTE-ERP\1 Prototype\`), weiterhin der Ort, an
  dem gebaut und getestet wird. **Ab sofort mit der lokalen PostgreSQL-Instanz statt SQLite**
  (siehe Abschnitt "PostgreSQL-Umstieg" unten für die portable, admin-rechte-freie Instanz),
  damit ein Postgres-spezifischer Fehler hier auffällt und nicht erst auf dem Server -- SQLite
  bleibt als schneller Einstieg für einen frischen Checkout ohne installiertes PostgreSQL
  nutzbar, ist aber nicht mehr das, wogegen ernsthaft entwickelt werden soll.
- **Produktion**: ein Ionos-VPS, Ubuntu, 2 Kerne, 4 GB RAM. PostgreSQL, Nginx als Reverse Proxy,
  HTTPS über Let's Encrypt, `gunicorn` als systemd-Dienst, erreichbar unter
  `app.dachkonzepte.gmbh`.

**Der Code kommt ausschließlich über Git dorthin. Niemals Dateien von Hand kopieren** -- jede
Abweichung zwischen dem, was lokal committet wurde, und dem, was tatsächlich auf dem Server
liegt, ist ab jetzt ein echtes Risiko (überschriebene, nie committete Änderungen; ein Server-
Stand, den `git log` nicht erklären kann), nicht nur ein theoretisches.

### Was beim Bauen zu beachten ist

- **Speicherbudget.** Der Server hat 4 GB RAM -- beim Entwickeln auf einem deutlich größeren
  Rechner fällt Speicherverbrauch nicht auf, auf dem Server schon. Beim ersten Anlauf wurden die
  Arbeitsprozesse bei 809 MB vom System abgeschossen (OOM). Bei allem, was größere Datenmengen
  im Speicher hält -- PDF-Erzeugung mit vielen Fotos (siehe `service_report_pdf.py`), Importe
  (Adressimport, XML-Import), Massenabfragen ohne Begrenzung -- den Verbrauch mitdenken, nicht
  erst auf dem Server merken.
- **Umgebungsvariablen statt fest verdrahteter Pfade/Werte.** Alles, was der Server anders
  macht als die Entwicklungsumgebung, gehört in eine Umgebungsvariable (Muster: `ERP_SECRET_KEY`,
  `ERP_DATA_DIR`, `DATABASE_URL`, jetzt auch `ERP_ENV`, siehe unten) -- nie ein Pfad oder Wert,
  der nur unter Windows bzw. nur lokal stimmt. Die vorhandenen Variablen sind in `.env.example`
  dokumentiert, das ist die verbindliche Liste.
- **Datenmenge wächst.** Heute (Stand des ersten Datenumzugs) 3040 Zeilen über alle Tabellen,
  162 Kunden. Das ist der Anfang, nicht der Bestand, mit dem langfristig geplant werden darf --
  eine Abfrage, die lokal an einer kleinen Datenmenge schnell ist, muss das bei tausenden Kunden/
  Aufträgen/Zeitbuchungen nicht bleiben. Bei neuen, potenziell großen Abfragen (fehlender Index,
  `N+1`-Nachladen, ungefilterte Listen) das im Kopf behalten, nicht erst wenn es spürbar wird.

### Die Serverumgebung im Einzelnen

| Was | Wo |
|---|---|
| Projektordner | `/home/tobias/erp` |
| Datenordner (`ERP_DATA_DIR`, außerhalb von Git) | `/home/tobias/erp-data` |
| Umgebung | `/home/tobias/erp/.env` |
| Datenbank | `dachkonzepte` (produktiv), `spielwiese` (Probe, siehe unten) |
| Dienst | `erp.service`, `gunicorn` mit einem Arbeitsprozess |
| Sicherung | `/home/tobias/backup.sh`, täglich 2 Uhr UTC, 14 Tage Aufbewahrung |
| Notfallskripte | `scripts/reset_admin_2fa.py`, `scripts/migrate_sqlite_to_postgres.py` |

Ein Arbeitsprozess (`gunicorn`, kein `--workers 2+`) ist bewusst so gewählt, nicht versehentlich
klein -- passend zum 4-GB-Speicherbudget oben; jeder zusätzliche Worker verdoppelt effektiv den
Speicherbedarf der Anwendung selbst.

### Der Weg einer Änderung auf den Server

Lokal bauen, volle Testsuite, bei Oberflächenänderungen zusätzlich ein Klicktest im Browser.
Committen -- der Betreiber pusht (etablierte Praxis dieser Sitzungen: Claude Code committet,
aber pusht nie ohne ausdrückliche Aufforderung). Auf dem Server: sichern, `git pull`, Abhängigkeiten,
Migrationen, Dienst neu starten.

**Korrigiert seit 1.3.42, nach einem realen Vorfall beim Ausliefern von 1.3.38–1.3.41** (siehe
"Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41" unten für die volle Herleitung) -- exakt diese
Abfolge, keine Zeile auslassen:

```bash
/home/tobias/backup.sh
cd /home/tobias/erp
git pull
set -a; source .env; set +a
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/alembic current
sudo systemctl restart erp
```

Die vierte Zeile (`set -a; source .env; set +a`) lädt `DATABASE_URL`/`ERP_SECRET_KEY`/`ERP_ENV`
usw. tatsächlich in die Shell-Umgebung -- ohne sie fiel `alembic upgrade head` bisher
stillschweigend auf einen falschen Wert zurück (siehe Vorfall 1 unten); seit 1.3.42 bricht
alembic statt eines stillen Rückfalls mit einer klaren Fehlermeldung ab, wenn `DATABASE_URL`
fehlt. Die siebte Zeile (`alembic current`) ist der einzige tatsächliche Nachweis, dass die
Migration gegriffen hat -- "keine Fehlermeldung gesehen" ist kein Ersatz dafür, siehe Vorfall 1.

Bei Schemaänderungen läuft die Migration vorher zusätzlich einmal gegen `spielwiese` (die
Probe-Datenbank auf demselben Server, nicht die lokale, portable Instanz aus der Entwicklung) --
`DATABASE_URL=postgresql+psycopg://<user>:<pass>@localhost:5432/spielwiese .venv/bin/alembic
upgrade head`, geprüft, danach erst die Abfolge oben gegen `dachkonzepte`.

### Was das für Migrationen heißt

Eine Migration läuft künftig auf echten Produktivdaten, nicht mehr nur auf einer leeren
Testdatenbank oder Tobias' lokaler Entwicklungskopie. Der Rückweg ist ein Backup-Restore, keine
Kleinigkeit mehr, die man nebenbei rückgängig macht.

Prüfe künftig bei **jeder** Migration, bevor sie auf den Server geht:

- **Läuft sie tatsächlich gegen PostgreSQL?** Kein `datetime('now')` (SQLite-spezifisch), keine
  nackten Boolean-Literale `1`/`0` in rohem SQL (unter PostgreSQL strikt typisiert, unter
  SQLite stillschweigend als Integer durchgewunken) -- siehe Abschnitt "PostgreSQL-Umstieg"
  unten für die Fehlerklasse im Detail.
- **Ist sie auf einem Bestand mit echten Daten getestet, nicht nur auf einer leeren
  Datenbank?** Eine leere Datenbank verdeckt genau die Fehler, die an echten Daten auffallen --
  siehe unten.
- **Kann sie rückgängig gemacht werden, und stellt `downgrade()` den tatsächlichen Vorzustand
  wieder her?** Nicht nur "irgendein" Vorzustand -- siehe die `5c8715dba230`/`0064c87051aa`-
  Migrationen (Abschnitt "Aufräumen nach dem PDF-Umbau") als Vorbild: ihr `downgrade()` liest die
  zuletzt tatsächlich vorhandenen Werte vor dem Schreiben aus, nicht nur Code-Standardwerte.
- **Ist sie tatsächlich gelaufen?** Seit 1.3.37 ist `Base.metadata.create_all()` im
  Produktivbetrieb abgeschaltet (`ERP_ENV`) -- gewollt, aber mit einer echten Konsequenz: eine
  übersprungene oder fehlgeschlagene Migration wird seither nicht mehr stillschweigend
  überbrückt (wie es unter SQLite/lokal noch geschähe), sondern legt das System beim nächsten
  Zugriff auf eine fehlende Spalte/Tabelle sofort lahm. `alembic upgrade head` ohne Fehlermeldung
  ist deshalb kein ausreichender Nachweis -- siehe Vorfall 1 im nächsten Abschnitt, in dem genau
  das passierte, weil die Migration in Wirklichkeit gegen die falsche Datenbank lief. Der Ablauf
  ("Der Weg einer Änderung auf den Server" oben) endet deshalb ausdrücklich mit `alembic
  current`, nicht mit `alembic upgrade head`.

**Warum das keine abstrakte Vorsicht ist, sondern eine bereits gemachte Erfahrung**: die
Migration `e057d15af828` war seit ihrer Erstellung eine leere Hülle (nur `pass`/`pass`) --
entstanden, weil `Base.metadata.create_all()` beim App-Start die Tabellen
`invoices`/`invoice_items` bereits real angelegt hatte, bevor `alembic revision --autogenerate`
lief, wodurch Autogenerate keinen Unterschied mehr fand. Unter SQLite (und lokal, wo
`create_all()` bis zu diesem Server-Rollout bei jedem Start nachzog) blieb das unbemerkt --
erst eine frische PostgreSQL-Datenbank
ohne dieses Sicherheitsnetz hätte die Kette mit `NoSuchTableError` abgebrochen. Siehe Abschnitt
"PostgreSQL-Umstieg: Migrationskette repariert" unten für die vollständige Herleitung und die
1.3.35-Reparaturrunde, die das (und sechs weitere, dialektbedingte Fixes) behoben hat, bevor
überhaupt umgezogen wurde. Diese Erfahrung ist der Grund für die drei Prüfpunkte oben -- nicht
Vorsicht um ihrer selbst willen.

### Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41, beide behoben (seit 1.3.42)

**Vorfall 1: `alembic upgrade head` lief ohne geladene Umgebungsvariablen, migrierte dadurch die
falsche Datenbank, und der Fehler ging unbemerkt unter.** Beim Einspielen von 1.3.38 bis 1.3.41
lief `alembic upgrade head` auf dem Server, ohne dass zuvor `.env` geladen wurde -- der
Bereitstellungsablauf hatte genau diesen Schritt verloren (siehe die korrigierte Abfolge oben).
`alembic/env.py` importierte `DATABASE_URL` bis dahin aus `app.database` -- dort ist ein stiller
Rückfall auf SQLite eine bewusste, für die lokale Entwicklung gedachte Bequemlichkeit
(`os.getenv("DATABASE_URL", "sqlite:///...")`). Ohne geladene Umgebung griff genau dieser
Rückfall auch beim Deployment: `alembic upgrade head` lief scheinbar fehlerfrei durch, migrierte
aber nicht `dachkonzepte`, ohne das an dieser Stelle sichtbar zu machen. Aufgefallen ist es erst,
als eine fehlende Spalte jede Seite mit 500 beantwortete -- die Datenbank blieb auf `1b55170709a6`,
dem Stand vor dem gesamten Umzug.

Behoben: `alembic/env.py` liest `DATABASE_URL` jetzt direkt über `os.environ.get(...)`, nicht
mehr über den bereits mit einem Vorgabewert versehenen Import aus `app.database` -- fehlt die
Variable, bricht alembic mit einer klaren, erklärenden Fehlermeldung ab, statt still auf
irgendeinen Wert zurückzufallen. **Unbedingt, unabhängig von `ERP_ENV`**: eine an
`ERP_ENV=="production"` gekoppelte Prüfung hätte hier nicht geholfen -- fehlt die Umgebung
komplett, fiele `ERP_ENV` selbst ebenso auf seinen Entwicklungs-Vorgabewert zurück, die Prüfung
griffe also nie genau dann, wenn sie gebraucht wird. Das ist eine bewusste, unbedingte Abweichung
von der bisherigen, lokal etablierten Praxis dieser Sitzungen (alembic ohne gesetzte Variablen
laufen zu lassen und sich auf denselben SQLite-Rückfall wie die App zu verlassen) -- lokal muss
`DATABASE_URL` für einen alembic-Aufruf ab jetzt ausdrücklich gesetzt werden, z. B.
`DATABASE_URL=sqlite:///./dachkonzepte_erp.db alembic upgrade head` (oder die lokale
Postgres-Verbindungszeichenfolge). Zusätzlich verlangte der Vorfall die oben bereits
beschriebene Korrektur des Bereitstellungsablaufs selbst (`set -a; source .env; set +a` UND
`alembic current` waren beide verlorengegangen).

**Vorfall 2: ein fehlgeschlagener Logo-Upload legte danach jede Seite lahm, einschließlich der
Anmeldeseite.** Nachdem die nachgeholte Migration griff, führte das Hochladen eines Logos dazu,
dass jede Seite mit 500 antwortete. Bei der Untersuchung ließ sich der genau gemeldete Ablauf
(eine Funktion `save_logo()`, bestimmte Zeilennummern in `company_logo.py`) im tatsächlichen Code
nicht wortgleich wiederfinden -- vermutlich eine sinngemäße statt einer wörtlichen Beschreibung
des Vorfalls (weder `save_logo` noch der genannte Fehlertext kamen im Projekt vor). Der reale, im
Code tatsächlich vorhandene Risikobereich war aber ebenso ernst und traf denselben Kern der
Meldung: (1) der Upload-Endpunkt (`POST /api/settings/general/logo`) prüfte bis dahin
ausschließlich den vom Client mitgeschickten `content_type`-Header -- frei wählbar, kein
Nachweis des tatsächlichen Dateiinhalts, eine beliebige Datei mit vorgetäuschtem
`image/png`-Header wäre durchgekommen; (2) KEINER der vier Jinja-Globals, die auf jeder Seite
laufen (`get_theme()`, `is_module_enabled()`, `sidebar_logo_url()`, `sidebar_logo_height_px()`
in `app/routers/pages.py`), fing eine Ausnahme ab -- ein DB-Zustand, der eine davon zum Werfen
brachte (z. B. genau die in Vorfall 1 beschriebene fehlende Spalte, oder eine kaputte
Logo-Referenz), schlug ungefiltert durch und beantwortete dadurch JEDE Seite mit 500,
einschließlich `login.html` (das `get_theme()` direkt für seine Akzentfarbe aufruft, nicht nur
über das dort gar nicht eingebundene `_sidebar.html`) -- niemand konnte sich mehr anmelden, um es
zu reparieren. Notbehelf war `UPDATE general_settings SET logo_filename = NULL` direkt in der
Datenbank.

Behoben, drei Teile:
1. `company_logo.py::validate_logo_image()` prüft jetzt VOR jeder Persistierung (vor
   `replace_logo()`, vor dem Setzen von `logo_filename`, vor `db.commit()`), ob Pillow die Datei
   tatsächlich öffnen/dekodieren kann -- SVG ausgenommen (Pillow kann SVG grundsätzlich nicht
   öffnen, das ist dort kein Fehler). `routers/settings.py::upload_company_logo()` fängt ein
   daraus resultierendes `ValueError` ab und antwortet mit **400** und einem verständlichen Text,
   nicht mit 500.
2. **Alle vier** Jinja-Globals in `app/routers/pages.py` sind jetzt gegen jede Ausnahme
   abgesichert (`try/except Exception`, über einen neuen `logger` protokolliert, mit sicherem
   Rückfallwert): `get_theme()` → Standard-Akzentfarbe (`#0d9488`), `is_module_enabled()` →
   `True` (dieselbe Opt-out-Philosophie wie im Normalfall, siehe `app/modules.py`),
   `sidebar_logo_url()` → `None` (Rückfall auf den Schriftzug), `sidebar_logo_height_px()` →
   `DEFAULT_SIDEBAR_LOGO_HEIGHT_PX`. **Prinzip, nicht nur Einzelfall-Fix**: ein Jinja-Global, der
   auf jeder Seite läuft, darf NIE eine Ausnahme werfen -- ein DB-Zustand, der das auslöst, darf
   höchstens den betroffenen Teil der Seite auf einen Rückfallwert reduzieren, niemals die ganze
   Seite (und damit möglicherweise auch die Anmeldeseite) unerreichbar machen. Geprüft, ob es
   weitere solche Globals gibt (`grep "env.globals\["` über `app/`): nein -- diese vier sind die
   einzigen mit Datenbankzugriff, alle vier sind jetzt abgesichert.
3. Tests ergänzt (`tests/test_v108_login_lockout_and_logging.py`-Nachbarschaft bzw. neue Datei,
   siehe "Testen" unten) für: den Upload-Endpunkt mit einer nicht dekodierbaren Datei (400, nicht
   500), jedes der vier Globals unter einer simulierten, fehlschlagenden Funktion (Rückfall
   greift, keine Ausnahme verlässt die Funktion), und einen Ende-zu-Ende-Test, dass eine
   `general_settings`-Zeile in einem ungültigen Zustand das Rendern echter Seiten nicht verhindert.

### Zwei Nebenbefunde vom Server, beide behoben

1. **`psycopg` (Version 3) vs. `psycopg2` -- Verwechslungsgefahr in der Verbindungszeichenfolge.**
   `requirements.txt` installiert ausschließlich `psycopg[binary]` (Version 3, SQLAlchemy-
   Dialektname `psycopg`) -- beim erstmaligen Aufsetzen des Servers wurde die
   Verbindungszeichenfolge trotzdem mit `postgresql+psycopg2://` angelegt (der weithin bekanntere,
   ältere Treibername), was zu einem Importfehler führte, da das dafür nötige, separate Paket
   `psycopg2` nirgends installiert war. Behoben durch `psycopg2-binary`, von Hand
   nachinstalliert -- funktionierte, aber ein zweiter, in `requirements.txt` nirgends
   dokumentierter Treiber, der bei einer künftigen Neuinstallation wieder fehlen würde. Jetzt
   vereinheitlicht: `requirements.txt` trägt einen erklärenden Kommentar direkt an der
   `psycopg`-Zeile, `.env.example` erklärt explizit, dass die Verbindungszeichenfolge
   `postgresql+psycopg` lauten muss und **nicht** `postgresql+psycopg2` -- mit einem Verweis auf
   genau diesen Vorfall. `psycopg2-binary` kann auf dem Server bei Gelegenheit entfernt werden,
   sobald die Verbindungszeichenfolge dort korrigiert ist (das ist eine Server-Administrations-
   aufgabe, kein Teil dieser Änderung).
2. **Ein Microsoft-365-Client-Secret ließ sich nach dem Umzug nicht mehr entschlüsseln.** Der
   gespeicherte Wert stammt aus einer Zeit mit einem anderen `ERP_SECRET_KEY`/einer anderen
   `data/.erp_secret` als der, die jetzt tatsächlich gilt -- Entschlüsselung schlägt seither mit
   dem in `app/crypto.py::decrypt_secret()` dokumentierten `ValueError` fehl. **Daraus folgt eine
   dauerhafte Regel, nicht nur eine Randnotiz: `data/.erp_secret` darf niemals gelöscht oder durch
   einen neuen, zufällig erzeugten Wert ersetzt werden, solange verschlüsselte Werte (SMTP-
   Passwort, Microsoft-365-Client-Secret, TOTP-Geheimnisse) in der Datenbank stehen** -- jeder
   dieser Werte wird mit genau diesem einen Schlüssel verschlüsselt (`app/crypto.py`, abgeleitet
   von `secret_key()` in `app/auth.py`) und wird ohne ihn unwiederbringlich unlesbar, nicht nur
   vorübergehend. Auf einem Server, auf dem `ERP_SECRET_KEY` als Umgebungsvariable gesetzt ist
   (siehe `.env.example`), gilt dasselbe für diese Variable -- sie darf sich nach dem ersten
   Verschlüsseln eines Werts nicht mehr ändern. Der bereits betroffene Wert selbst lässt sich
   nicht nachträglich reparieren (der alte Schlüssel ist verloren) -- ein Administrator muss das
   Microsoft-365-Client-Secret einmalig über Einstellungen → E-Mail-Versand neu eintragen.

## Stack & Struktur

- **Backend:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, ReportLab
- **Frontend:** Jinja2-Templates mit eingebettetem, framework-losem JavaScript (kein React/Vue) –
  jede Seite ist eine einzelne `.html`-Datei mit `<style>` und `<script>` direkt darin
- **Datenbank:** PostgreSQL produktiv (seit 14.09.2026, siehe Abschnitt "Produktivbetrieb"
  oben) und seither auch in der lokalen Entwicklung Standard, statt der früher rein lokalen
  SQLite-Datei -- SQLite bleibt als schneller Einstieg für einen frischen Checkout ohne
  installiertes PostgreSQL nutzbar (`DATABASE_URL`-Standardwert), ist aber nicht mehr das,
  wogegen ernsthaft entwickelt werden soll
- **Tests:** pytest, Dateien unter `tests/test_vNNN_thema.py` – die Nummer bezieht sich lose auf
  die Version, in der das Feature entstand
- **Layout:** `app/*.py` enthält die Geschäftslogik modulweise (z. B. `projects.py`, `invoices.py`,
  `orders.py`, `reminders.py`, `email_sending.py`), `app/routers/*.py` die dazugehörigen
  FastAPI-Endpunkte (aus `main.py` in Version 1.0.7 herausgezogen), `app/templates/*.html` die
  Oberfläche
- **Design-System (seit 1.0.97, auf alle Seiten ausgerollt):** jede Seite mit `{% include
  "_sidebar.html" %}` definiert im eigenen `:root`/`:root[data-theme="dark"]`-Block dieselben
  CSS-Variablen (`--accent` aus `{{ get_theme().accent_color }}`, `--bg`, `--card`, `--ink`,
  `--muted`, `--line`, `--field-border(-hover)`, `--soft`, `--danger(-soft)`, ggf.
  `--warning(-soft)`/`--success(-soft)`, plus die `--sidebar-*`-Token für `_sidebar.html`), dazu ein
  FOUC-Vermeidungs-Script vor dem `<style>`-Block. Eckige Ecken durchgängig (kein
  `border-radius`), keine farbige Kopfleiste – Seitentitel/Aktionen stattdessen in einer normalen
  Karte. `settings.html` als Referenzvorlage für Feldlayout, Buttons, Status-Meldungen.

## Kritische, nicht verhandelbare Regeln

Diese Punkte wurden in der Sitzung mehrfach zum echten Problem, bevor sie zur festen Regel
wurden. Bitte in jeder neuen Sitzung beachten, nicht neu lernen müssen:

1. **`server_default` bei NOT-NULL-Spalten auf bestehenden Tabellen ist Pflicht**, nicht nur
   `default=`. Ohne `server_default` schlägt die Migration auf einer bereits gefüllten Tabelle
   fehl. Gilt für jede neue Spalte, die per Alembic auf eine existierende Tabelle kommt.

2. **Keine Funktionen mit `test_`-Präfix außerhalb von Testdateien.** pytest sammelt jedes
   importierte Symbol mit diesem Präfix als eigenen Test ein und bricht ab. Wurde einmal so
   benannt (`test_smtp_connection`) und musste in `check_smtp_connection` umbenannt werden.

3. **Zirkel-Import-Falle bei PDF-Renderern:** `X_pdf.py`-Module importieren fast immer aus dem
   zugehörigen `X.py`-Geschäftslogik-Modul zurück (z. B. `invoice_pdf.py` aus `invoices.py`,
   `reminder_pdf.py` aus `reminders.py`, `quote_layout_pdf.py` aus `projects.py`, `order_pdf.py`
   aus `orders.py`). Wird `X.py` um eine neue Funktion erweitert, die ihrerseits den PDF-Renderer
   braucht, **immer lokal innerhalb der Funktion importieren**, nie auf Modulebene – sonst
   Zirkel-Import. Vor dem Hinzufügen kurz prüfen: `grep "^from \." app/X_pdf.py`.

4. **Nie `prompt()` oder andere Browser-Popups für Dateneingabe.** Ausdrücklich von Tobias
   gefordert: Eingaben (z. B. eine E-Mail-Adresse vor dem Versand) müssen als bereits sichtbares,
   vorausgefülltes Eingabefeld direkt auf der Seite erscheinen, nicht als Popup. `confirm()` für
   einfache Ja/Nein-Bestätigungen (z. B. "wirklich löschen?") ist dagegen etabliert und in Ordnung.

5. **GoBD-Unveränderlichkeit ernst nehmen.** Finalisierte Rechnungen und Mahnungen (Status
   ungleich Entwurf) dürfen nie bearbeitet oder gelöscht werden – nur Entwürfe. Ein Projekt mit
   bestehendem Auftrag darf nicht hart gelöscht werden: `Order.invoices` trägt
   `cascade="all, delete-orphan"`, ein uneingeschränktes Löschen würde auch bereits finalisierte
   Rechnungen mitreißen. Solche Projekte lassen sich nur archivieren, nicht löschen.

6. **Migrationsarme Zusatztabellen haben keine ORM-Relationship, also keine automatische
   Kaskade.** Um spätere Features ohne `ALTER TABLE` auf Kerntabellen einzuführen, wurden
   mehrfach separate "Zusatztabellen" mit reiner Fremdschlüsselspalte angelegt (Beispiel:
   `QuoteSection`, `QuoteDocumentMeta`, `QuoteEmployeeAssignment`, `QuoteItemLayout` – Zugriff
   überall per expliziter `select(...)`-Abfrage, nie über ein Attribut wie `quote.sections`).
   **Wird ein übergeordneter Datensatz (Quote, QuoteItem, …) gelöscht, müssen solche
   Zusatztabellen manuell vorher geleert werden** – SQLAlchemy kaskadiert hier nichts von allein.
   Genau das wurde einmal übersehen und führte zu verwaisten Zeilen; seither expliziter Test dafür.

7. **Vor jedem Modell-Konstruktor-Aufruf in neuem Code (Anwendungscode wie Tests) die
   tatsächlichen Feldnamen in `app/models.py` gegenprüfen**, nicht aus dem Gedächtnis raten.
   Besonders bei Tests wichtig, da diese in dieser Sitzung immer wieder real mit `pytest`
   ausgeführt wurden und falsche Feldnamen sofort auffielen. Für einen schnellen Überblick ohne
   die ganze (2361 Zeilen lange) Datei zu lesen: `docs/bestandsaufnahme_modelle.md` listet alle
   104 Modelle mit Spalten/FKs/Relationships (Stand 09.09.2026) – bei neueren Änderungen bleibt
   trotzdem `app/models.py` selbst die verbindliche Quelle, die Anlage kann veralten.

8. **`CHANGELOG.md` und `VERSION` gehören zu jeder abgeschlossenen, spürbaren Änderung dazu, nicht
   nur zu "richtigen Features".** Diese Datei war über ~45 Versionen (1.0.57–1.0.96 sowie das
   komplette visuelle Redesign) ungepflegt und musste rückwirkend aus `seit 1.0.NN`-Codekommentaren
   rekonstruiert werden, was für die undokumentierten Versionen nur noch lückenhaft möglich war –
   das soll sich nicht wiederholen. Vorgehen bei jeder abgeschlossenen Änderung (nicht erst am
   Ende einer langen Sitzung sammeln): `VERSION` um genau einen Patch-Level erhöhen, dann in
   `CHANGELOG.md` **oben** (unterhalb der Kopfzeilen) einen neuen Abschnitt `## <neue Version> –
   <Kurztitel>` einfügen, ein bis zwei Absätze in der etablierten Erzählweise (was wurde geändert
   und warum, ggf. ein dabei gefundener Fehler) – siehe bestehende Einträge als Vorlage. Auch reine
   Aufräum-/Redesign-/Cleanup-Durchgänge zählen als eigene Version, nicht nur neue fachliche
   Funktionen. Bei mehreren klar trennbaren Änderungen in einer Sitzung lieber mehrere kleine
   Versionssprünge als einen vagen Sammel-Eintrag. **Seit 1.1.0 zusätzlich:** ein
   Minor-Versionssprung (`1.X.0`) markiert die Einführung eines neuen, echten Moduls (siehe
   Modul-Umschalter unten), ein reiner Patch-Level (`1.0.X`) alles andere – Infrastruktur, Fixes,
   Redesign, Anpassungen an bestehenden Modulen.

9. **Nach jedem abgeschlossenen Update (seit 1.1.4) läuft zusätzlich `backup_windows.ps1`.**
   Grund: das Projekt liegt bisher in keinem Git-Repository – ohne ein eigenes Backup gibt es
   keinen Rollback-Mechanismus, falls sich ein Update im Nachhinein als fehlerhaft herausstellt.
   Das Skript kopiert das komplette Projekt (Code **und** Datenbank `dachkonzepte_erp.db` **und**
   `data/` mit Firmenlogo, hochgeladenen Projektdateien und dem Verschlüsselungsschlüssel
   `data/.erp_secret`) nach `C:\DACHKONZEPTE-ERP\Backup\v<VERSION>_<Zeitstempel>\` – ein neuer
   Ordner pro Lauf, nichts wird überschrieben. Ausgenommen sind nur `.venv`, `__pycache__`,
   `.pytest_cache` (reproduzierbar über `requirements.txt`) sowie Log-Dateien (kein Teil eines
   funktionierenden Zustands). Reihenfolge bei jedem abgeschlossenen Update: zuerst `VERSION` +
   `CHANGELOG.md` (Regel 8), dann `.\backup_windows.ps1` ausführen und den Erfolg (Zielordner,
   Größe) kurz prüfen. **Automatische Bereinigung (seit 1.1.5):** das Skript behält nach jedem
   Lauf nur die 3 jüngsten Backup-Ordner, ältere werden am Ende desselben Laufs automatisch
   gelöscht (Parameter `-KeepCount`, falls doch mal mehr/weniger gebraucht wird) – bei normalem
   Betrieb (ein Backup pro abgeschlossenem Update) entspricht das genau den letzten 3 Versionen.
   **Deshalb (seit 1.3.40, echter Vorfall): unter `C:\DACHKONZEPTE-ERP\Backup\` dürfen
   ausschließlich vom Skript selbst erzeugte Ordner liegen (Namensmuster `v<VERSION>_<Zeitstempel>`,
   z. B. `v1.3.40_20260914-135537`).** Die Bereinigung filtert seit 1.3.40 zwar zusätzlich auf
   genau dieses Muster (`Get-ChildItem ... -Filter "v*_*"`, vorher griff sie auf JEDEN Ordner in
   diesem Verzeichnis zu) -- ein zuvor dort abgelegter, fremder Ordner (`Server`, Kopien der
   Server-Sicherungen von `/home/tobias/backups/`) wurde dadurch real gelöscht, bevor die
   Filterung existierte (zum Glück ohne echten Datenverlust, da dieselben Sicherungen unverändert
   auf dem Produktivserver lagen). Andere Dateien -- auch fremde, auch scheinbar sicher benannte
   -- gehören deshalb in einen ANDEREN Ordner, nie direkt unter `Backup\`.

10. **Jeder Stammdatenbereich folgt demselben Muster, ausnahmslos (seit 1.3.30 als Regel
    festgehalten, nachdem Mitarbeiter zweimal davon abwich):** beim Einstieg zeigt sich immer
    zuerst die LISTE, nie ein Formular; die Seite trägt die gemeinsame Stammdaten-Navigation
    (`master_data.html`s `.side`-Leiste, mit der zwischen Kunden, Objekten, Mitarbeitern, Teams
    und allen übrigen Bereichen gewechselt wird); Anlegen UND Bearbeiten öffnen immer eine eigene
    Formularseite (`master_data_form.html`, parametrisiert über `data_type`/`record_id` -- oder,
    wenn ein Bereich eine eigene, reichhaltigere Detailseite rechtfertigt, wie bei Kunden/Objekten,
    diese eigene Seite), nie ein Formular, das unterhalb oder neben der Liste eingeblendet wird.
    Ein "Zurück"-Link ist kein Ersatz für die Navigationsleiste -- wo die Leiste vorhanden ist,
    braucht es ihn nicht. Gilt für JEDEN künftigen Stammdatenbereich, auch wenn er zunächst
    einfacher erscheint, als eigene Seite gebaut zu werden. Historie, warum das eine echte Regel
    und keine Stilfrage ist: Mitarbeiter wich davon zweimal ab -- zuerst (bis 1.3.26) implizit
    nie geprüft, dann (1.3.26–1.3.29) als bewusst gebaute, aber grundverschiedene Einzelseite
    `/employees` (Formular immer sichtbar statt Liste zuerst) --, beide Male fiel es erst auf,
    als es der einzige Weg zu Mitarbeitern war. Details der endgültigen Korrektur (inkl. der
    Prüfung, warum sich der Vergütungsrechner doch vollständig in `master_data_form.html`
    unterbringen ließ) im Abschnitt "Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher"
    unten.

## Fachbegriffe & Domänenmodell

- **"Vorgang"** (in normalem Gespräch) = **Projekt** (`Project`) – wurde in der Sitzung explizit
  geklärt, da der Begriff auf mehrere Dinge hätte zeigen können.
- Kette: `Customer` → `Project` → `Quote` (Angebot) → `Order` (Auftrag) → `Invoice` (Rechnung) →
  `Reminder` (Mahnung).
- `Quote`: frei bearbeitbar, Status u. a. `entwurf`/`versendet`/`beauftragt`. Kann `is_template=True`
  sein (Mustervorgang) und/oder `archived=True`.
- `Order`: entsteht ausschließlich durch Beauftragung eines Angebots, ist ein **unveränderlicher
  LV-Snapshot**. Kein Entwurfsstatus – startet direkt bei `beauftragt`.
- `Invoice`: `entwurf` bis zur Finalisierung (vergibt Nummer aus Nummernkreis), danach
  unveränderlich außer über eine Stornorechnung.
- `Reminder`: hängt an überfälligen Rechnungen, hat Stufen (1./2./3. Mahnung), jede Stufe mit
  eigenen Fristen/Gebühren/Textvorlagen (`ReminderLevel`). `Reminder.text` ist beim Anlegen
  (`create_reminder()`) eine reine Kopie von `ReminderLevel.text_template` mit noch
  unaufgelösten Platzhaltern (`{mahngebuehr}` usw.) – `formatted_text` (`reminder_to_dict()`)
  wird bei JEDEM Lesezugriff frisch aus `text` + den aktuellen Feldwerten zusammengesetzt
  (`format_reminder_text()`/`_reminder_placeholders()`), nie gespeichert oder gecacht. Solange
  `status="entwurf"` ist, lässt sich `text`/`fee_amount`/`new_due_date` über
  `update_reminder_draft()` (seit 1.3.21, `PUT /api/reminders/{id}`) ändern – Statusschutz sitzt
  in der Geschäftsfunktion selbst, gleiches Muster wie `update_report()` beim Einsatzbericht,
  siehe Abschnitt "Mahnwesen: Löschen/Versenden/Bearbeiten" unten. Nach `finalize_and_send_reminder()`
  (Status `versendet`, Nummernvergabe) unveränderlich wie `Invoice`/`Order` (Regel 5).
- **`Property`** ("Objekt", `app/models.py`): eigenständige Tabelle (`customer_id`, `name`,
  `street`, `postal_code`, `city`, `notes`) für ein zusätzliches Gebäude/Objekt eines Kunden
  über dessen eigene Hauptadresse hinaus. Per 09.09.2026 verifiziert (siehe
  `docs/bestandsaufnahme.md` Abschnitt 3, seither um `RoofArea` ergänzt): **vier** Stellen im
  Projekt referenzieren `properties.id` per FK – `Inquiry.property_id`, `Project.property_id`
  (beide optional, bidirektionale Relationship), `MaintenanceContract.property_id` (optional,
  unidirektional) und seit 1.2.14 `RoofArea.property_id` (Pflicht, bidirektional, **mit**
  `cascade="all, delete-orphan"` – anders als bei `projects`, siehe eigener Abschnitt unten).
  `Order` und `Invoice` haben **kein** `property_id` – nur `property_name`/`property_address`
  als reinen Text-Schnappschuss zum Zeitpunkt der Beauftragung/Rechnungsstellung. Wer von einem
  `Order` zum zugehörigen `Property` will, muss über `order.project.property_id` gehen (siehe
  `list_property_history()` in `app/service_reports.py`).
- **Dachflächen & Bauteile** (`RoofArea`/`RoofComponent`, seit 1.2.14, `app/roof_areas.py`,
  `app/routers/roof_areas.py`, `/roof-areas/{id}`): ein Dachdeckerbetrieb wartet nicht "ein
  Objekt", sondern einzelne Dachflächen, die aus einzelnen Bauteilen bestehen – erst auf
  Bauteil-Ebene wird eine Historie brauchbar ("Gully Nordost, dritte Verstopfung in zwei
  Jahren" statt "Dach hat Probleme", spätere Prüfpunkte/Mängel/Berichte folgen als eigene
  Iteration). Bewusst **keine** `is_module_enabled("wartungen")`-Prüfung – `Property` ist
  Kern-Stammdatum ohne `OPTIONAL_MODULES`-Eintrag. `roof_type`/`covering`/`component_type`
  sind bewusst freie, über `SettingOptionGroup`/`SettingOption` pflegbare Auswahllisten
  (`roof_types`/`roof_coverings`/`roof_component_types` in `app/option_settings.py`) statt
  eigener Stammdatentabellen – da sie komplett neue `group_key`s sind, seeden sie sich beim
  ersten `GET /api/settings/option-groups/{key}` selbst, **keine** Daten-Migration nötig
  (anders als beim Nachtragen zweier Werte in die schon bestehende Gruppe
  `time_entry_activities`, siehe unten). `RoofComponent.unit` nutzt die bereits bestehende
  Gruppe `units`.
  - **Cascade + Datei-Aufräumen**: `RoofArea.components` (echte `cascade="all,
    delete-orphan"`-Relationship, reiner neuer Tabellenbaum, kein migrationsarmer Sonderweg
    nötig) UND `Property.roof_areas` tragen beide Cascade. Property wird zwar aktuell
    nirgends im Code gelöscht (kein `DELETE`-Endpunkt, kein `db.delete()`), aber ein
    SQLAlchemy-Mapper-Event `@event.listens_for(RoofArea, "before_delete")` in
    `app/roof_areas.py` löscht die Skizzendatei (`sketch_path`) von der Festplatte – dieses
    Event feuert für JEDEN ORM-Löschweg, auch kaskadiert (z. B. ein künftiges
    `db.delete(property)`), da SQLAlchemy Cascade-Löschungen als einzelne Objektlöschungen
    durch den Unit-of-Work abwickelt. `delete_roof_area()` selbst ruft `delete_sketch_file()`
    deshalb nicht mehr separat auf.
  - **Skizzen-Upload** (`app/roof_area_sketches.py`, Vorbild `document_layout_background.py`,
    nicht `customer_documents.py`): ein Bild pro Dachfläche, eigener `data/roof_area_sketches/`-
    Ordner mit eigener Env-Var `DACHKONZEPTE_ROOF_SKETCH_FILE_ROOT` – das ist bereits der
    sechste unabhängige Upload-Pfad ohne zentralen `data/`-Root (siehe
    `docs/bestandsaufnahme.md` Abschnitt 9), bewusst nicht in dieser Iteration konsolidiert.
    `MAX_UPLOAD_BYTES` (10 MB) und Content-Type-Whitelist (`image/png|jpeg|webp`), eigener
    `GET /api/roof-areas/{id}/sketch`-Auslieferungs-Endpunkt.
  - **Bauteil-Positionierung**: `sketch_x`/`sketch_y` (Prozentwerte 0–100) werden per Klick auf
    die hochgeladene Skizze gesetzt (`PUT /api/roof-components/{id}/position`) – Pointer-Events
    (`onpointerup`, `getBoundingClientRect()`) wie beim Unterschriften-Canvas in
    `service_reports.html`, funktioniert also auch auf dem Tablet. **Seit 1.2.19 zusätzlich
    flächig**: `sketch_w`/`sketch_h` (ebenfalls Prozentwerte, beide `NULL` = Punktmarker, beide
    gesetzt = Rechteck) werden per Ziehen statt Tippen gesetzt (`pointerdown`/`pointermove`/
    `pointerup`, `setPointerCapture` – dasselbe Muster wie der Unterschriften-Canvas, nur mit
    Start- und Endpunkt statt einem einzelnen). Ob eine Bauteilart flächig markiert wird
    (`is_area`), hängt an der Bauteilart selbst, nicht am einzelnen Bauteil – siehe
    **Bauteilarten als echte Tabelle** unten. Ein bereits gesetztes Rechteck lässt sich durch
    erneutes Ziehen ersetzen, kein separates Löschen nötig.
  - **`RoofComponent.sort_order`** (Default 100, Muster wie `EmployeeFunction.sort_order`) von
    Anfang an ergänzt, nicht erst bei Bedarf – daraus sollen später Prüfpunkte einer vom
    Monteur in fester Reihenfolge abzuarbeitenden Checkliste entstehen.
  - **Archivieren** (`set_roof_area_archived()`/`set_roof_component_archived()`, gleiches
    Muster wie `set_contract_archived()`): Standardweg zum Ausblenden. Echtes Löschen
    (`delete_roof_area()`/`delete_roof_component()`) bleibt zusätzlich erlaubt, da es sich um
    Planungs-Stammdaten und nicht um ein GoBD-Dokument handelt.
  - **UI-Verankerung, seit 1.2.18 überholt**: ursprünglich (1.2.14) bewusst KEINE neue,
    parallele Objektseite – die Kundenakte bekam nur eine zusätzliche Dachflächen-Liste je
    Objekt-Karte, die generische Stammdatenverwaltung blieb unverändert. Im ersten echten
    Gebrauch erwies sich das als genau die gemeldete Schwäche (zwei unterschiedlich reiche
    Ansichten auf denselben Datensatz, siehe unten) – seit 1.2.18 gibt es die echte Objektseite
    doch, siehe **Objektseite** weiter unten.
  - **Objektseite** (`GET /properties/{id}`, `app/templates/property.html`, seit 1.2.18, Muster
    `roof_area.html`): zeigt die vier flachen Objektfelder zum Bearbeiten, die Dachflächenliste
    (inkl. Mehrfach-Anlegen, siehe unten) und – nur wenn `is_module_enabled('wartungen')` –
    die zugehörigen Wartungsverträge. Da `Property` keine Rückwärts-Relationship zu
    `MaintenanceContract` hat (bewusst, siehe oben), löst `list_contracts_for_property()` in
    `app/maintenance_contracts.py` das über eine reine `select`-Abfrage, keine neue
    Relationship nur für diesen einen Anzeigefall. Beide bisherigen Wege führen jetzt dorthin:
    die Kundenakte bekam einen "Öffnen"-Link je Objekt-Karte (ihr Inline-Editor bleibt als
    Schnellzugriff zusätzlich bestehen), die generische Stammdatenmaske
    (`master_data.html`/`master_data_form.html`) leitet beim Bearbeiten sofort auf
    `/properties/{id}` weiter und navigiert nach dem Anlegen direkt zum neuen Datensatz – beide
    Änderungen bewusst auf den ohnehin typspezifischen `properties`-Zweig der jeweiligen Datei
    begrenzt, kein Umbau, der andere Stammdatentypen berührt. Die Breadcrumb auf
    `roof_area.html` verweist entsprechend auf Kunde UND Objekt als echte Links (vorher war das
    Objekt nur Text).
  - **Mehrfach-Anlegen** (`create_roof_areas_bulk()` in `app/roof_areas.py`, seit 1.2.18,
    `POST /api/properties/{id}/roof-areas/bulk`): ein Dachtyp für alle Zeilen, mehrere
    Namenszeilen, leere werden übersprungen. Ruft `create_roof_area()` unverändert je Zeile
    auf, kein Nachbau. Anders als beim Einzelanlegen (direkte Navigation zur neuen Dachfläche)
    bleibt man danach auf der Objektseite, da bei mehreren keine eindeutige Zielseite existiert.
  - **Positions-Erklärung** (seit 1.2.18): die Spalte hieß "Position gesetzt" und war ohne
    hinterlegte Skizze unverständlich. Jetzt "Auf Skizze markiert", blendet sich (Spalte samt
    Marker-Bereich) komplett aus, solange `area.has_sketch` falsch ist – statt "Noch keine
    Skizze hinterlegt." steht dort "Skizze oder Luftbild hochladen, um Bauteile darauf zu
    markieren."; ist eine Skizze da, erklärt ein Satz über dem Bild den Zweck der Marker.
  - **Dachaufbau als Schichtenliste** (`RoofLayerType`/`RoofLayer`, seit 1.2.18, weiterhin in
    `app/roof_areas.py`): ersetzt `RoofArea.build_up` (Freitext) und `.insulation`. Welche
    Schichten abgefragt werden, hängt vom Dachtyp ab (`RoofLayerType.roof_type`, NULL = gilt
    für jeden – aktuell ungenutzt, siehe Migrations-Begründung). `option_group` verweist auf
    eine der sechs neuen `SettingOptionGroup`s `layer_*` (Selbst-Seeding wie
    `roof_types`/`roof_coverings`), aus der die Ausführung gewählt wird – bewusst NICHT über
    den Leistungskatalog (Material/MaterialGroup): der Katalog dient der Preisfindung, der
    Dachaufbau der Dokumentation. Fehlt eine Ausführung, lässt sie sich im Dropdown direkt per
    "+ Neu…" ergänzen (nutzt den bereits bestehenden `POST
    /api/settings/option-groups/{group_key}/options`, kein `prompt()`). Die 25 Schichttypen
    (Steildach 7, Flachdach 7, Gründach 11) kommen als **Daten-Migration** (`RoofLayerType` ist
    eine echte Tabelle, kein Selbst-Seeding wie bei den Optionsgruppen) – Verwaltung unter
    Einstellungen → Dachaufbau, bewusst **ungated** (Kern-Stammdatum wie `RoofArea` selbst),
    Löschen blockiert bei Verwendung (Muster `delete_window()`), Deaktivieren bleibt frei.
    **Gründach-Redundanz** (bewusst, siehe „Bekannte, bewusst offene Punkte" unten): Gründach
    bekommt dieselben 7 Schichten wie Flachdach unter eigenen `key`-Werten noch einmal, statt
    sie über `roof_type IS NULL` zu teilen – NULL hätte einem Steildach fälschlich auch
    Dampfsperre/Abdichtung gezeigt. **Dachtypwechsel bei bereits erfassten Schichten**: bleiben
    stehen, werden nie gelöscht (durchgängiges Prinzip dieses Projekts, erfasste Daten nie
    stillschweigend zu verwerfen) – `list_roof_layers()` liefert weiterhin ALLE `RoofLayer`
    einer Dachfläche, die Oberfläche kennzeichnet nur, welche nicht mehr zum aktuellen
    `RoofArea.roof_type` passen. **`build_up`/`insulation` bleiben in der Datenbank**
    (Altbestand geht sonst verloren), aber `create_roof_area()`/`update_roof_area()` nehmen
    diese Parameter seit 1.2.18 nicht mehr an – ein damit vermiedener Fehler: ein
    `update_roof_area()`, das sie weiterhin annimmt, hätte bei jedem Speichern über das neue,
    reduzierte Formular automatisch `None` übernommen und den historischen Text beim nächsten
    Speichern eines beliebigen anderen Feldes stillschweigend gelöscht. Die Oberfläche zeigt
    sie nur noch schreibgeschützt als "Aufbau (Altbestand, Freitext)", wenn befüllt.
    **Datenverlust behoben (seit 1.2.19)**: `upsert_roof_layer()` überschrieb bis 1.2.18
    unbedingt alle vier Spalten (`present`/`execution`/`thickness_mm`/`notes`) bei jedem
    Aufruf – in Kombination mit `roof_area.html`s ungebremsten (kein `await`), schnell
    aufeinanderfolgenden Autosave-Aufrufen (Toggle "Ja" gefolgt vom Eintippen einer Bemerkung)
    empirisch nachgewiesen zu einem Race, bei dem ein älterer Schnappschuss beim Server zuletzt
    committet und einen neueren überschreibt (derselbe Fehlertyp wie `build_up`, eine Ebene
    tiefer). `upsert_roof_layer(db, roof_area_id, layer_type_id, fields: dict)` nimmt jetzt ein
    Feld-Dict statt einzelner Parameter und überschreibt nur die tatsächlich enthaltenen
    Schlüssel (Router: `payload.model_dump(exclude_unset=True)`) – ein nicht mitgeschicktes
    Feld bleibt unverändert, ein ausdrücklich gesendetes `null` leert es weiterhin bewusst.
    `roof_area.html` sendet dazu je Änderung nur noch das geänderte Feld
    (`saveLayerField(typeId, fields)`), nicht mehr den ganzen Zeilen-Schnappschuss. Zusätzlich
    schließt ein neuer, geteilter Helfer `app/templates/_debounce.html` (per Jinja-Include wie
    `_sidebar.html`, in `roof_area.html` UND `service_reports.html` eingebunden) die
    Blur-Abhängigkeit von `onchange`: Bemerkungs-/Dicke-Felder speichern zusätzlich 600ms nach
    der letzten Eingabe, unabhängig davon, ob das Feld je den Fokus verlässt (z. B. Reload
    direkt nach dem Eintippen). **Fallstrick beim Bauen dieses Helfers**: sein erklärender
    Kommentar darf den Jinja-Include-Tag nicht als Text zitieren – Jinja erkennt `{% include %}`
    unabhängig davon, ob er in einem JS-Kommentar steht, band die Datei dadurch einmal
    rekursiv in sich selbst ein (`RecursionError`, erst bei der Server-Smoke-Prüfung
    aufgefallen, nicht durch `pytest`, da dort keine Templates gerendert werden). `dieselbe
    Lücke geprüft`: `update_inspection_item()` hatte eine eigene, deterministische Variante
    (siehe **Strukturierte Prüfpunkte** unten), `update_roof_component()` ist nicht praktisch
    verwundbar (sein einziger Aufrufer sendet immer einen vollständigen Schnappschuss aus einem
    echten Bearbeiten-Formular, bewusst unverändert gelassen).
  - **Drei Flags statt einem** (`RoofLayerType.has_execution`/`has_thickness`/`has_notes`, seit
    1.2.19): `has_thickness` allein war zu grob – ein Schichttyp ohne `option_group` hat nie
    eine Ausführungsauswahl, unabhängig von einem Flag; `has_execution` macht das explizit
    steuerbar (z. B. eine vorhandene Ausführungsliste vorübergehend ausblenden, ohne
    `option_group` zu leeren), `has_notes` blendet das Bemerkungsfeld aus, wenn ein Schichttyp
    keinen Freitext braucht. Migration setzt `has_execution` für die 25 bestehenden Zeilen
    danach, ob `option_group` gesetzt ist, `has_notes` bleibt für alle `true`. Ein
    deaktiviertes Feld verschwindet nur aus der Anzeige – dank der `exclude_unset`-Architektur
    oben wird es beim Speichern nie mitgeschickt, also nie überschrieben.
  - **Bauteilarten als echte Tabelle** (`RoofComponentType`, seit 1.2.19, weiterhin in
    `app/roof_areas.py`, ungated wie `RoofLayerType`): vorher eine reine `SettingOptionGroup`
    (`roof_component_types`) – zum `RoofLayerType`-Vorbild aus 1.2.18 hochgestuft, damit
    `is_area` (flächige vs. punktförmige Markierung auf der Skizze, siehe
    **Bauteil-Positionierung** oben) an der Bauteilart selbst hängen kann statt inkonsistent am
    einzelnen `RoofComponent`. `key` bleibt bewusst textidentisch zu den bisherigen
    Options-Werten ("Gully", "Photovoltaik", …), damit
    `RoofComponent.component_type`/`InspectionTemplateItem.component_type` (beide einfache
    Strings, kein FK – genau wie `RoofArea.roof_type` heute schon) unverändert weiter
    funktionieren; ein projektweiter `grep` auf `component_type` bei der Planung war nötig, um
    den `InspectionTemplateItem`-Bezug (1.2.16-Vorlagenabgleich) überhaupt zu finden. Migration
    liest die Werte für die neue Tabelle **nicht** aus der Code-Konstante, sondern aus den
    tatsächlichen `setting_options`-Zeilen der DB (eine Installation kann seit 1.2.14 eigene
    Bauteilarten angelegt haben) – fehlt die Gruppe ganz (frische, nie gesäte DB), fällt sie auf
    die 15 Code-Werte zurück. `roof_component_types` ist aus `DEFAULT_OPTION_GROUPS` entfernt;
    bereits gesäte `SettingOptionGroup`/`SettingOption`-Zeilen einer laufenden Installation
    bleiben als toter Datenbestand stehen (siehe „Bekannte, bewusst offene Punkte" unten).
    `delete_component_type()` blockiert, solange der `key` noch von einem `RoofComponent` oder
    einem `InspectionTemplateItem` getragen wird (String-Vergleich, kein FK), Deaktivieren
    bleibt frei. Verwaltung unter Einstellungen → Bauteilarten (eigener Abschnitt neben
    Dachaufbau).
- **Zeiterfassung (`TimeEntry`)**: hängt zwingend an einem `Order` (`order_id` NOT NULL,
  `order_item_id` optional), Status nur `running`/`booked` (kein Enum). `activity` ist ein
  freier String, fachlich befüllt über die konfigurierbare Optionsgruppe
  `time_entry_activities`. `TimeEntryGroup`/`TimeEntryGroupMember` bilden Gruppen-Zeitbuchungen
  mehrerer Mitarbeiter gleichzeitig ab (bisher hier nicht dokumentiert). Details, inkl. wie
  Zeitbuchungen zu einem Auftrag aufgelöst werden: `docs/bestandsaufnahme.md` Abschnitt 6.
- **Plantafel**: verplant wird ein Zeitabschnitt (`PlanningSlot`) je Auftrag **×** Team, nicht
  eine einzelne LV-Position und nicht direkt ein einzelner Mitarbeiter. `Team`/`TeamEmployee`
  ist eine dauerhafte, zeitlose n:m-Mitgliedschaft; beim Zuweisen eines Teams zu einer
  Arbeitsvorbereitung friert `WorkPreparationTeamAssignment` die damalige Besetzung als
  Snapshot ein. UI: Gantt-artige Zeitachse mit Drag & Drop – **funktioniert auf Touch-Geräten
  nicht** (native HTML5-DnD-API), Klick-Fallback-Dialog aber schon. Details:
  `docs/bestandsaufnahme.md` Abschnitt 7 und 10.
- **Mustervorgang** (`Project.is_template`): technisch ein ganz normales Projekt, taucht aber
  nicht in der normalen Projektliste auf. Kopieren/Als-Mustervorgang-speichern/Neuen-Vorgang-aus-
  Muster-erstellen laufen alle über dieselbe Funktion `duplicate_project()` in `app/projects.py`.
  **`duplicate_project()` kopiert nie einen Auftrag** (nur das zuletzt angelegte Angebot,
  `status` immer hartkodiert `"anfrage"`, unabhängig von `as_template`) – im zweiten Klicktest
  (1.2.20) wurde ein aus einem Wartungsvertrag erzeugtes Projekt mit sowohl Angebot ALS AUCH
  Auftrag beobachtet; Code-Prüfung (Docstring sagt es explizit) und der einzige dazu
  nachvollziehbare echte Datensatz (Projekt mit `ProjectProfile.source_maintenance_contract_id`
  gesetzt: ein Angebot, kein Auftrag) bestätigten übereinstimmend das erwartete Verhalten – nicht
  reproduzierbar, keine Codeänderung. Wahrscheinlichste Erklärung: der Auftrag entstand durch
  einen eigenen, nicht mehr erinnerten Klick auf "Beauftragen" beim Testen des neuen Angebots.
- **E-Mail-Versand**: gemeinsame Infrastruktur in `app/email_sending.py` (SMTP oder Microsoft 365
  OAuth2/Graph API, umschaltbar). Betrifft/Auftrag/Angebot/Rechnung teilen sich eine Textvorlagen-
  Tabelle (`app/document_email_templates.py`), Mahnungen haben eigene Vorlagen pro Stufe direkt
  auf `ReminderLevel` (historisch zuerst gebaut, nie migriert).
- **Modul-Umschalter** (seit 1.1.0): Tabelle `EnabledModule` (`module_key`, `enabled`), Registry
  `OPTIONAL_MODULES` in `app/modules.py` ist die einzige Stelle, an der sich ein künftiges Modul
  eintragen muss. Opt-out-Default – fehlt eine Zeile für einen `module_key`, gilt das Modul als
  aktiv, damit ein neuer Registry-Eintrag nie stillschweigend eine bestehende Installation
  verändert. Ein Admin schaltet Module live unter Einstellungen → Module um (`PUT
  /api/modules/{key}`), Prüfung überall live per `is_module_enabled(db, key)` bzw. dem
  gleichnamigen Jinja-Global – **kein** Modul darf nur an einer Stelle (z. B. nur im Sidebar-Link)
  versteckt sein; API-Endpunkte müssen den Zustand selbst prüfen (403 bei deaktiviert, auch für
  Admins), sonst bleibt die Funktion über die API erreichbar, obwohl die Oberfläche sie versteckt.
  Die Kern-ERP-Kette (`Customer`→…→`Reminder`, Zeiterfassung, Planung) hat bewusst **keinen**
  Registry-Eintrag und bleibt immer aktiv.
- **Aufgabe** (`Task`, seit 1.1.0, erstes Modul `aufgabenmanagement`): freie, eigenständige Aufgabe
  mit Status und Priorität, optional einem Mitarbeiter und/oder einem `Project` zugeordnet –
  unabhängig von den älteren, bereichsgebundenen `WorkPreparationTask`-Einträgen der
  Arbeitsvorbereitung. Sichtbarkeit folgt demselben Muster wie das Dashboard-Widget „Meine
  Aufgaben" (eigene Aufgaben für Sachbearbeiter, serverseitig erzwungen; Admin frei wählbar). Drei
  freie Felder `source_module`/`source_label`/`source_url` sind die **Automatisierungs-
  Anschlussstelle**: ein künftiges Modul (z. B. digitale Wartungsberichte) ruft `create_task()` in
  `app/tasks.py` direkt in-process auf, um automatisiert eine Aufgabe zu erzeugen, ohne dass
  `tasks` dafür etwas über das aufrufende Modul wissen muss; Idempotenz (kein doppeltes Anlegen)
  ist Sache des aufrufenden Moduls.
  - **Spalten** (`TaskColumn`, seit 1.1.1): `Task.status` ist kein fester Enum mehr, sondern
    referenziert `TaskColumn.key` – ein Admin verwaltet die Spalten (umbenennen, sortieren,
    hinzufügen, löschen sobald ungenutzt) unter Einstellungen → Aufgaben frei, angelehnt an den
    mehrstufigen Ablauf einer Kundenanfrage. Jede Spalte trägt `is_done`; `completed_at` auf
    `Task` richtet sich nach diesem Flag, nicht mehr nach dem Literal `"erledigt"`. Fehlt jede
    Spalte (z. B. eine per `Base.metadata.create_all()` erzeugte Testdatenbank ohne die Migration),
    seedet `app/task_columns.py::ensure_default_columns()` beim ersten Zugriff selbstständig die
    drei ursprünglichen Spalten nach – dieselben drei, die die Migration `6ed174efcf4a` für echte
    Installationen bereits per Daten-Seed anlegt.
  - **Checkliste** (`TaskChecklistItem`, seit 1.1.2): abhakbare Unterpunkte einer Aufgabe. Anders
    als die migrationsarmen Zusatztabellen zu bestehenden Kern-Tabellen (Quote, QuoteItem, siehe
    Regel 6) bekommt sie eine echte ORM-Relationship mit `cascade="all, delete-orphan"` auf
    `Task`, da `Task` selbst schon unser eigenes, neues Modul ist – kein manuelles Aufräumen beim
    Löschen einer Aufgabe nötig.
  - **Zuweisungs-E-Mail** (seit 1.1.3): `notify_task_assignment()` in `app/tasks.py` verschickt bei
    neuer/geänderter `assigned_employee_id` eine Benachrichtigung an `EmployeeProfile.email` (kann
    fehlen) über die neue anhangslose `send_plain_email()` in `app/email_sending.py`. Schalter dazu
    in `TaskSettings.notify_on_assignment` (Singleton wie `LaborRateSettings`). Ein Versandfehler
    wird innerhalb der Funktion abgefangen – darf das bereits erfolgte Speichern der Aufgabe nicht
    rückwirkend als Fehler erscheinen lassen.
  - **Archivieren** (`set_task_archived()`, seit 1.2.11, gleiches Muster wie
    `Project.archived`): blendet eine Aufgabe aus dem Standard-Board aus, ohne sie wie
    `delete_task()` unwiderruflich zu löschen – unabhängig von Spalte/`is_done`. `list_tasks()`
    nimmt dafür `include_archived` (Default `False`).
  - **"Vorgang erstellen" aus der Aufgabe heraus** (seit 1.2.21, für Aufgaben mit
    `source_module="wartungsbericht"`, siehe **Mängel und Fotos** oben): der eigentliche
    Folgeauftrag (Projekt + Auftrag über `create_quick_service_order()`) entsteht nicht mehr
    automatisch beim Anlegen des Mangels, sondern erst durch einen bewussten Klick auf dieser
    Aufgabe. Rückrichtung von der Aufgabe zum Mangel läuft über die bereits bestehende Spalte
    `Finding.follow_up_task_id` (`get_finding_for_task()` in `app/findings.py`, eine gezielte
    `select`-Abfrage) – bewusst KEINE neue Spalte an `Task`, um für einen einzelnen Anzeigefall
    keine neue Relationship einzuführen (gleiche Zurückhaltung wie bei
    `list_contracts_for_property()`). `create_follow_up_project_for_task()` lehnt ab, wenn kein
    zugehöriger Mangel existiert oder bereits ein Vorgang erzeugt wurde (`follow_up_order_id`
    gesetzt). Zwei neue, modulgegatete Endpunkte `GET/POST /api/tasks/{id}/finding` bzw.
    `/create-follow-up-project` – URL-Präfix richtet sich nach dem Task-Kontext, Business-Logik
    bleibt in `app/findings.py` (Muster wie `GET /api/orders/{order_id}/roof-areas`). Navigiert
    nach Erfolg **sofort** zum neuen Vorgang (anders als die 1.2.20-Ausnahme bei "Vorgang
    erstellen" auf der Wartungsvertrags-Seite) – hier sitzt der Sachbearbeiter am Schreibtisch
    und bearbeitet die Aufgabe gezielt, nicht mitten in einer Felderfassung.
- **Wartungsvertrag** (`MaintenanceContract`, seit 1.2.0, Modul `wartungen`): wiederkehrender
  Vertrag je Kunde, optional mit einem zusätzlichen **Objekt** (`property_id`, seit 1.2.9
  optional – vorher wie bei "ein Wartungsvertrag ohne Gebäude ergibt fachlich keinen Sinn"
  fälschlich als Pflichtfeld angenommen; in der Praxis hat nicht jeder Kunde zusätzliche
  Objekte über seine eigene Hauptadresse hinaus). Fehlt die Auswahl, gilt die Hauptadresse des
  Kunden selbst (`Customer.street`/`postal_code`/`city`) als Einsatzort – `contract_to_dict()`
  bildet diesen Rückfall nach (`property_name="Hauptadresse"`, `property_address` aus den
  Kundenstammdaten) und `update_contract()` erlaubt das nachträgliche Setzen/Entfernen der
  Objekt-Zuordnung. Mit Intervall (`interval_months`) und `next_due_date`. **Bewusst kein
  Scheduler**: `check_due_contracts_and_create_reminders()`
  in `app/maintenance_contracts.py` läuft nur beim Aufruf von `/maintenance-contracts`
  (On-Demand-Muster wie `auto_create_due_reminder_drafts()` in `app/reminders.py`) und erinnert
  per `create_task()` (Automatisierungs-Anschlussstelle, siehe oben) an `responsible_employee_id`
  (Rückfall: `MaintenanceSettings.default_responsible_employee_id`, siehe unten)
  – `last_reminder_due_date` ist der Idempotenz-Stempel dagegen, dass derselbe Fälligkeitszyklus
  zweimal erinnert. Ein neuer Vorgang aus dem hinterlegten `template_project_id`
  (Mustervorgang, nutzt `duplicate_project()` aus `app/projects.py`) entsteht **nie**
  automatisch, sondern nur durch bewussten Klick auf "Vorgang erstellen"
  (`create_project_from_contract()`) – erst dieser Klick rückt `next_due_date` um
  `interval_months` weiter und setzt den Idempotenz-Stempel zurück. Ohne aktives
  Aufgabenmanagement entfällt die Erinnerung ersatzlos (keine Aufgabe wäre dort sowieso
  sichtbar) – kein Fehler, keine harte Modul-Abhängigkeit. **Seit 1.2.19 immer sichtbar**: die
  Schaltfläche "Vorgang erstellen" zeigt sich (auf der eigenen Vertragsseite, siehe unten)
  jetzt unabhängig von `is_due`/`is_overdue`, sobald ein Mustervorgang existiert – vorher nur
  bei Fälligkeit, was einen frisch angelegten Vertrag praktisch untestbar machte.
  `create_project_from_contract()` selbst prüft die Fälligkeit nach wie vor nicht (reine
  Oberflächen-Rückfrage: ein `confirm()` mit dem regulären Fälligkeitsdatum, wenn der Vertrag
  noch nicht fällig ist). Fehlt ein Mustervorgang, bleibt die Schaltfläche sichtbar, aber
  deaktiviert, mit erklärendem Hinweis darunter – nie einfach ausgeblendet.
  - **Rückweg: Wartungsvertrag aus einem Projekt erzeugen**
    (`create_maintenance_contract_from_project()`, seit 1.2.12): nutzt bewusst
    `duplicate_project(as_template=True)` (`app/projects.py`) wieder – denselben Mechanismus,
    den auch der Button "Als Mustervorgang speichern" auf der Projektseite verwendet –, statt
    das Kopieren erneut nachzubauen. Lehnt Aufrufe auf einem bereits `is_template=True`-Projekt
    ab (dafür gibt es schon den direkten Weg über die Mustervorgang-Auswahl beim Anlegen eines
    Vertrags). Intervall und nächste Fälligkeit müssen dabei abgefragt werden, da sie sich aus
    einem einmaligen Projekt nicht automatisch ableiten lassen.
  - **Löschen** (`delete_contract()`, seit 1.2.8): anders als `Invoice`/`Order`/`Reminder` ist
    ein Wartungsvertrag kein GoBD-pflichtiges Dokument, sondern reine Planungsinformation –
    echtes Löschen ist daher grundsätzlich unabhängig vom Status jederzeit erlaubt (kein
    Entwurfsstatus-Vorbehalt wie bei Rechnungen) – **AUSSER** es existiert bereits ein
    **unterschriebener** Einsatzbericht dazu (seit 1.2.15, vertrags- oder positionsbezogen,
    siehe `MaintenanceContractItem` unten): dann blockiert `delete_contract()` mit `ValueError`
    statt zu kaskadieren, exakt das Muster von `delete_project()` bei bestehenden Aufträgen –
    Archivieren bleibt davon unberührt. Keine andere Tabelle trägt eine Fremdschlüsselspalte auf
    `maintenance_contracts` (kein Regel-6-Fall im engeren Sinn), ABER: die per
    `check_due_contracts_and_create_reminders()` erzeugten Erinnerungs-Aufgaben hängen locker
    über `source_module`/`source_url` am Vertrag (Automatisierungs-Anschlussstelle, bewusst
    keine FK) – ohne explizites Aufräumen blieben sie als toter Link zurück (seit 1.2.10 in
    `delete_contract()` behoben, genau das hatte Tobias nach dem ersten Löschen gemeldet).
    `MaintenanceContractItem`-Zeilen räumt seit 1.2.15 eine echte ORM-Cascade automatisch ab.
    Der literale `source_url=f"/maintenance-contracts/{contract_id}"` ist seit 1.2.19 ein
    echter, funktionierender Link (siehe **Eigene Vertragsseite** unten) – `delete_contract()`
    selbst musste dafür nicht angefasst werden.
  - **Archivieren** (`set_contract_archived()`, seit 1.2.11, gleiches Muster wie
    `Project.archived`): mildere, jederzeit umkehrbare Alternative zum Löschen – blendet aus
    der Standardliste UND aus `check_due_contracts_and_create_reminders()` aus (keine
    Erinnerung mehr), unabhängig vom Status aktiv/pausiert/beendet. `list_contracts()` nimmt
    dafür `include_archived` (Default `False`), gleiches Parameter-Muster wie bei
    `list_projects()`.
  - **`is_due`-Berechnung braucht eine Vorlaufzeit, nicht nur "überfällig"**
    (`MaintenanceSettings`, Singleton wie `TaskSettings`, seit 1.2.6): `contract_to_dict()`
    prüft `next_due_date <= heute + reminder_lead_days` (Standard 30 Tage), nicht mehr nur
    `next_due_date <= heute` – sonst taucht ein erst in wenigen Tagen fälliger Vertrag
    nirgends auf (weder im Dashboard-Widget noch als "fällig" auf `/maintenance-contracts`,
    genau das hat Tobias nach dem ersten echten Anlegen eines Vertrags gemeldet). Dieselbe
    Schwelle steuert auch, ab wann `check_due_contracts_and_create_reminders()` erinnert –
    **eine** Einstellung für Anzeige und Erinnerung, nicht zwei getrennte.
  - **Positionen je Dachfläche und saisonale Wartungsfenster** (`MaintenanceContractItem`/
    `MaintenanceWindow`, seit 1.2.15): ein `MaintenanceWindow` (admin-verwaltet unter
    Einstellungen → Wartungen, Migrations-Seed "Frühjahr"/"Herbst") definiert ein jährlich
    wiederkehrendes Fenster über Start-/Endmonat (`month_from`/`month_to`, Wraparound wie
    Dezember–Februar erlaubt) statt Kalendertage. Eine `MaintenanceContractItem` koppelt eine
    `RoofArea` (muss zum `property_id` des Vertrags gehören – ein Vertrag ohne `property_id`
    kann daher keine Positionen haben) an genau ein Fenster, mit eigenem
    `template_project_id`-Rückfall auf den des Vertrags (unterschiedliche Positionen können
    unterschiedliche Mustervorgänge brauchen) und eigenem `duration_minutes` (für spätere
    Plantafelplanung). **Hat ein Vertrag mindestens eine aktive Position UND ist
    `MaintenanceSettings.use_roof_area_items` an (seit 1.2.19, Default AUS – siehe unten), löst
    die Positionsebene die Vertragsebene VOLLSTÄNDIG ab** – `is_due`,
    `check_due_contracts_and_create_reminders()` und `create_project_from_contract()` ohne
    `item_id` werten `contract.next_due_date`/`interval_months` dann nicht mehr aus (die
    Spalten bleiben nur als Rückfall erhalten, falls alle Positionen wieder archiviert werden).
    Positions-Erinnerungen teilen sich bewusst dieselbe `source_url` wie die Vertrags-
    Erinnerung, damit `delete_contract()`s bestehendes Task-Aufräumen unverändert weiterwirkt.
    Neben `is_due` (innerhalb der Vorlaufzeit) gibt es `is_overdue` (das Fenster ist bereits
    vollständig verstrichen, `_window_close_date()`) – getrennt ausgewiesen, damit eine seit
    Monaten verpasste Wartung nicht wie eine harmlos anstehende aussieht. `duplicate_project()`
    kopiert die Vertragsherkunft (`ProjectProfile.source_maintenance_contract_id`/-`item_id`,
    siehe unten) bewusst NICHT auf ein Duplikat.
  - **"Zu wartende Dachflächen" statt "Position" (seit 1.2.19)**: das Wort "Position" ist
    komplett aus der Oberfläche verschwunden – fachlich heißt es weiterhin
    `MaintenanceContractItem`, die Oberfläche zeigt nur noch "Zu wartende Dachflächen"
    (Einzahl: "eine Dachfläche"). Neue Einstellung `MaintenanceSettings.use_roof_area_items`
    (Boolean, Default AUS, Einstellungen → Wartungen): ist sie aus, verhält sich JEDER Vertrag
    ausschließlich über `next_due_date`/`interval_months`, auch wenn er noch Altbestand-
    Positionen aus einer Zeit trägt, in der der Schalter an war – diese Zeilen bleiben in der
    DB stehen (werden nie gelöscht), erscheinen aber nirgends in der Oberfläche und fließen
    nirgends in Fälligkeit/Erinnerung ein (`_is_due()`,
    `check_due_contracts_and_create_reminders()`, `create_project_from_contract()`, dazu das
    Dashboard-Widget "Fällige Wartungen", das dieselbe eigene Verzweigung hatte und daher
    separat auf den Schalter geprüft werden musste). `create_contract_item()` lehnt bei
    ausgeschaltetem Schalter zusätzlich mit `ValueError` ab (Verteidigung in der Tiefe – die
    Oberfläche zeigt den Abschnitt dann ohnehin nirgends).
  - **Eigene Vertragsseite** (`GET /maintenance-contracts/{id}`,
    `app/templates/maintenance_contract.html`, seit 1.2.19, Muster `property.html`):
    Breadcrumb Kunde → Objekt (nur wenn `property_id` gesetzt) → Vertrag, Stammdaten-Editor
    (Kunde selbst ist NICHT editierbar – `update_contract()` kennt gar keinen
    `customer_id`-Parameter, nur ein Auswahlfeld für das Objekt), Status-Aktionen
    (Pausieren/Reaktivieren/Beenden/Archivieren/Löschen), "Zu wartende Dachflächen" (nur bei
    `use_roof_area_items`), Vertragshistorie, "Vorgang erstellen". Neuer Einzelabruf
    `get_contract()` in `app/maintenance_contracts.py` (`list_contracts()` allein reichte
    nicht mehr, sonst müsste die Detailseite die ganze Liste laden). Die Liste
    `/maintenance-contracts` selbst bleibt schlank (Übersicht, Anlegen-Formular, "Fällige
    Wartungen im Fenster", Reparatur/Wartung erfassen) – das Aufklappen je Zeile
    (`contractDetailBody()`/`toggleContractDetails()`) ist komplett auf die neue Seite
    gewandert, jede Zeile verlinkt stattdessen dorthin; nach dem Anlegen eines Vertrags geht es
    direkt zur neuen Detailseite (Projektmuster "nach Anlegen direkt zum Datensatz").
  - **"Wartung durchführen" – ein Klick von der Vertragsseite (seit 1.2.22)**: neuer, primärer
    Button auf `maintenance_contract.html` (das bisherige "Vorgang erstellen" wird zur
    Nebenaktion), `create_maintenance_visit()` in `app/maintenance_contracts.py`
    (`POST /api/maintenance-contracts/{id}/perform-maintenance`). Fasst in einem Schritt
    zusammen, was vorher fünf manuelle Schritte waren: legt über `create_quick_service_order()`
    einen Auftrag an (**ohne** Mustervorgang – Wartung wird über die Vertragspauschale oder nach
    Aufwand abgerechnet, nicht über LV-Positionen) und direkt einen vorbereiteten
    Wartungsbericht über ALLE nicht archivierten Dachflächen des Objekts (siehe "Mehrflächen-
    Berichte" unter Einsatzbericht), dann Navigation direkt in diesen Bericht. Bewusst reine
    Vertragsebene, unabhängig von `MaintenanceContractItem`/`use_roof_area_items` – hat der
    Vertrag aktive Positionen unter dem Schalter, bleibt dafür ausschließlich der bestehende Weg
    je Position zuständig (dieselbe Sperre wie bei `create_project_from_contract()`). Die
    Fälligkeit wird hier **nicht** beim Anlegen fortgeschrieben (siehe
    `ServiceReport.advance_due_date_on_sign` unter Einsatzbericht).
- **Einsatzbericht** (`ServiceReport`, seit 1.2.1, Modul `wartungen`): Rapportbericht
  (`report_type="rapport"`, Reparaturen) oder Wartungsbericht (`"wartung"`), hängt bewusst am
  `Order` (nicht am `MaintenanceContract` – auch spontane Reparaturen ohne Wartungsvertrag
  brauchen Berichte). **Vertragsbezug ohne `Order` anzufassen** (seit 1.2.15,
  `maintenance_contract_id`/`maintenance_contract_item_id`, beide optional): `Order` bleibt ein
  unveränderlicher LV-Snapshot ohne neue Spalte. Stattdessen markiert
  `create_project_from_contract()` das neu erzeugte Projekt über `ProjectProfile`
  (`source_maintenance_contract_id`/-`item_id`, bereits bestehender Mechanismus für
  "Projektstammdaten ohne ALTER TABLE") – `create_report()` liest `order.project.profile` und
  übernimmt diese Markierung als einmaligen Schnappschuss auf den neuen Bericht.
  `list_contract_history()` zeigt darüber die Vertragshistorie (bereits unterschriebene
  Berichte) direkt auf `/maintenance-contracts` an. Zeitbuchungen dazu werden **nicht** per
  eigener FK-Spalte an `TimeEntry`
  verknüpft, sondern über `Order` gemeinsam gefunden (`GET /api/time-entries?order_id=...`,
  bereits bestehender Endpunkt, kein neuer nötig). **Seit 1.2.21 direkt auf der Berichtsseite
  buchbar**: ein kompaktes Formular (Mitarbeiter/Datum/Zeitart/Tätigkeit/LV-Position optional/
  Stunden/Notizen) ruft genau diesen bereits bestehenden Endpunkt `POST /api/time-entries`
  (→ `create_manual_entry()` in `app/time_tracking.py`) auf – keine Geschäftslogik dupliziert
  (Validierung/Rundung/Berechtigung sitzen bereits vollständig im Endpunkt), nur eine
  schlankere Eingabemaske als `time_tracking.html`. Timer/Gruppenbuchung werden dort bewusst
  NICHT nachgebaut, `#timeLink` zur vollen Zeiterfassungsseite bleibt zusätzlich bestehen. Die
  Tabelle "Erfasste Zeiten zu diesem Auftrag" zeigt zusätzlich eine Summenzeile. Unterschrift erfolgt auf dem Gerät des
  Monteurs über ein neues, framework-loses `<canvas>`-Zeichenfeld (kein Kunden-Login) –
  `sign_report()` in `app/service_reports.py` schreibt die PNG-Bytes nach
  `data/service_report_signatures/` (Muster wie `app/company_logo.py`), friert den Bericht
  danach unveränderlich ein (`status="unterschrieben"`, gleiches Muster wie
  `Invoice`/`Order`/`Reminder`) und ist damit der erste echte Aufrufer der
  Automatisierungs-Anschlussstelle außerhalb der Wartungsverträge selbst: eine
  "Rechnung erstellen"-Aufgabe geht an `Order.caseworker_employee_id`. PDF-Erzeugung
  (`app/service_report_pdf.py`) nur für bereits unterschriebene Berichte, embeddet die
  Unterschrift als `platypus.Image`-Flowable (nicht `drawImage` auf einem rohen Canvas wie
  `quote_layout_pdf.py`, da dieses PDF wie `invoice_pdf.py` auf `SimpleDocTemplate`/`story`
  aufbaut).
  - **Weg zur Berichtsseite fehlte (behoben seit 1.2.20)**: `order.html` hatte keinen Link auf
    `/orders/{id}/service-reports` – im zweiten Klicktest gemeldet, weil ein aus einem
    Wartungsvertrag erzeugter Vorgang keinen erkennbaren nächsten Schritt zeigte. Jetzt ein
    eigener, erst nach `isModuleEnabled('wartungen')` eingeblendeter Link im `top-actions`-
    Bereich (Text `Einsatzberichte (N)` bzw. `Einsatzbericht anlegen` bei 0), dieselbe
    Auftragsliste auf `project_folder.html` bekommt aus demselben Grund eine zusätzliche Spalte
    (gated über die neue, seiteneigene JS-Konstante `maintenanceModuleEnabled`, per Jinja-Global
    gesetzt – gleiches Muster wie der bereits vorhandene "Wartungsvertrag erstellen"-Button dort,
    nur für eine clientseitig aus JSON gebaute Tabellenzelle statt einen serverseitig
    ausgeblendeten Button). Zählung über die neue, schlanke `count_reports_for_order()` in
    `app/service_reports.py` (Muster `finding_count`), durchgereicht über
    `OrderListOut.service_report_count`. `service_reports.html` hatte bereits einen Rückweg zum
    Auftrag (`#orderLink`), aber der Kunde stand dort nur als Text – `OrderOut`/`order_to_dict()`
    bekommen dafür zusätzlich `customer_id` (`order.project.customer_id`, `Order.project` war in
    `load_order()` bereits eager geladen), womit eine echte Breadcrumb (Muster `property.html`/
    `roof_area.html`) Kunde → Auftrag → "Einsatzberichte" zeigen kann.
  - **"Vorgang erstellen" navigiert seit 1.2.20 bewusst NICHT mehr sofort weiter** (Ausnahme von
    der sonst geltenden Regel "nach Anlegen sofort zum neuen Datensatz", siehe unten): der
    eigentliche nächste Schritt (Einsatzbericht) liegt vom neuen Vorgang aus zwei Ebenen entfernt
    (Angebot beauftragen → Auftrag entsteht → darüber Bericht anlegen), ein stiller Sprung zum
    Projekt hätte nicht gezeigt, wie es weitergeht. `createProjectNow()` in
    `maintenance_contract.html` zeigt statt dessen ein Ergebnis-Panel mit echtem Link – auf den
    neuen Vorgang mit Erklärtext im Regelfall, oder (geprüft, aber laut `duplicate_project()`
    praktisch nie zutreffend, da ein frisch erzeugter Vorgang nie einen Auftrag mitbringt) direkt
    auf die Berichtsseite, falls das neue Projekt bereits einen Auftrag hat.
  - **Formularfelder "optional" trotz Pflicht für einen Folgeschritt (behoben seit 1.2.20)**:
    "Mustervorgang (optional)" auf `maintenance_contract.html` und dem Anlegen-Formular auf
    `maintenance_contracts.html` verschwieg, dass ohne ihn `create_project_from_contract()` mit
    `ValueError` ablehnt – Hinweistext ergänzt, wortgleich zur bereits bestehenden Meldung unter
    der deaktivierten "Vorgang erstellen"-Schaltfläche. Derselbe Fall eine Ebene tiefer bei der
    Positions-Ebene (`itemTemplate`, "optional, sonst der des Vertrags") ebenfalls ergänzt. Bei
    der Gelegenheit alle übrigen "optional"-Beschriftungen im Modul geprüft (Objekt → Hauptadresse,
    Zuständig → `MaintenanceSettings.default_responsible_employee_id`, Prüfvorlage → 4-stufige
    Auflösung inkl. "keine Prüfpunkte" als gültigem Ergebnis, Dachtyp bei Prüfvorlagen → "gilt für
    jeden Dachtyp", Dauer/Beschreibung → rein informativ) – keine weiteren Fälle gefunden, jede
    hat einen echten, bereits im Hinweistext genannten Rückfall.
  - **Mehrflächen-Berichte** (`ServiceReportRoofArea`, seit 1.2.22): ein Objekt mit mehreren
    Dachflächen bekommt einen einzigen Bericht mit einer einzigen Unterschrift statt eines
    Berichts je Fläche – der Kunde bekommt fachlich eine Wartung. Neue Tabelle
    `ServiceReportRoofArea` (`service_report_id`, `roof_area_id`, mit EIGENEM
    `inspection_template_id`/`-version`-Schnappschuss je Fläche, da unterschiedliche Flächen
    unterschiedliche Dachtypen und damit unterschiedliche Vorlagen haben können) ist die
    alleinige Quelle, welche Flächen an einem NEUEN Bericht beteiligt waren – auch wenn die
    aufgelöste Vorlage für eine Fläche keine Prüfpunkte erzeugt hat (dann `inspection_template_id
    = NULL` auf dieser Zeile, aber die Zeile existiert trotzdem, die Fläche bleibt sichtbar).
    `InspectionItem.roof_area_id` (neue, nullable, indizierte Spalte) wird bei JEDER Generierung
    gesetzt, unabhängig von `roof_component_id` (der bisherige einzige, indirekte Weg über
    `roof_component.roof_area_id`, der für component-lose Punkte gar nicht existierte).
    `create_report()` nimmt dafür `roof_area_ids: list[int] | None` statt `roof_area_id: int |
    None` (Parameter umbenannt, alle Aufrufer angepasst). **Die alten Schnappschuss-Spalten am
    Bericht selbst** (`ServiceReport.roof_area_id`/`inspection_template_id`/
    `inspection_template_version`) **bleiben als Spalten erhalten und behalten ihre Werte für
    bestehende, vor 1.2.22 angelegte Berichte** (nie verworfene Daten, gleiches Prinzip wie
    `RoofArea.build_up`), werden aber von KEINEM Code-Pfad mehr beschrieben – auch nicht bei
    einem neuen Bericht mit nur einer Fläche, bewusst ohne Sonderfall (sonst bräuchte jede
    nachgelagerte Stelle zwei Fallunterscheidungen). `report_to_dict()` liefert zusätzlich ein
    einheitliches Feld `roof_areas: list[...]` – bei einem neuen Bericht aus den echten
    `ServiceReportRoofArea`-Zeilen gebaut, bei einem Altbestand-Bericht (keine solchen Zeilen)
    aus den Legacy-Spalten synthetisiert; beide Fälle laufen dadurch für Anzeige/PDF über
    denselben Lesepfad. `regenerate_inspection_items()`/`sync_inspection_items()` verzweigen
    intern genauso (neue Berichte: über alle `report_roof_areas`; Altbestand: unverändert über
    die Legacy-Spalten) – zwei Zweige in derselben Funktion, keine doppelte Datei.
    `sign_report()`s Vollständigkeits-/Negativ-/Foto-/Wiedervorlage-Prüfungen blieben dabei
    UNVERÄNDERT (von Tobias selbst bestätigt) – sie zählen ohnehin über alle Prüfpunkte des
    Berichts, unabhängig von der Fläche. PDF (`app/service_report_pdf.py`): bei vorhandenen
    `report_roof_areas` eine eigene Überschrift je Fläche vor ihren Gruppen-Tabellen; ein
    Altbestand-Bericht ohne solche Zeilen rendert unverändert flach wie vor 1.2.22.
  - **Fälligkeit erst bei der Unterschrift, nicht beim Anlegen** (`ServiceReport.
    advance_due_date_on_sign`, seit 1.2.22, NOT NULL, Default `false`): nur
    `create_maintenance_visit()` setzt sie `true`. `sign_report()` prüft sie NACH dem Einfrieren
    – ist sie wahr und `maintenance_contract_id` gesetzt, wird `contract.next_due_date`/
    `last_reminder_due_date` genau wie in `create_project_from_contract()` fortgeschrieben
    (Wiederverwendung von `add_months()`, siehe unten). Begründung: `create_project_from_contract()`
    schreibt die Fälligkeit weiterhin beim Anlegen fort, weil ein Projekt dort nur eine
    Papierhülle ohne jedes spätere "fertig"-Signal ist; der neue Weg "Wartung durchführen"
    erzeugt dagegen etwas, das der alte nicht hat – einen unterschriebenen `ServiceReport`, ein
    echtes Fertigstellungs-Signal. Würde die Fälligkeit schon beim Anlegen fortgeschrieben,
    verschöbe ein erstellter, aber nie ausgeführter Auftrag (Bericht bleibt Entwurf oder wird
    gelöscht) den Turnus trotzdem. Ist der Vertrag bis zur Unterschrift bereits gelöscht (nur ein
    Entwurfsbericht blockiert `delete_contract()` nicht), überspringt `sign_report()` die
    Fortschreibung stillschweigend – die Unterschrift selbst darf davon nicht abhängen. Reine
    Datumsarithmetik `add_months()` wanderte dafür aus `app/maintenance_contracts.py` in ein
    neues, gemeinsames Hilfsmodul `app/date_utils.py`: `service_reports.py` braucht sie für
    `sign_report()`, `maintenance_contracts.py` braucht umgekehrt `create_report()` aus
    `service_reports.py` – zwei Modulebenen-Importe in beide Richtungen hätten einen echten
    Zirkel erzeugt, den ein lokaler Import nur an einer Stelle umschifft, aber nicht auflöst
    hätte (siehe Regel 3, dort bisher nur für PDF-Renderer formuliert – hier grundsätzlich
    dieselbe Lösung: das Gemeinsame in ein drittes, domänenloses Modul auslagern, wenn möglich,
    statt den Zirkel nur zu umgehen).
  - **Explizite Dachtyp-Standardvorlage statt implizitem `sort_order`** (neue Tabelle
    `RoofTypeInspectionTemplateDefault`, seit 1.2.22, `app/inspection_templates.py`,
    Einstellungen → Prüfvorlagen, neuer Abschnitt oben auf der Seite): `_resolve_inspection_template()`s
    dritte Stufe (passender `roof_type`) fragt jetzt zuerst diese explizite, admin-änderbare
    Zuordnung ab, statt bei mehreren Vorlagen mit demselben `roof_type` den niedrigsten
    `sort_order` zu wählen ("zu implizit", die eigentliche Beschwerde). Gibt es KEINE explizite
    Zuordnung, aber GENAU EINEN nicht archivierten Kandidaten für diesen Dachtyp, wird dieser
    trotzdem verwendet – bei nur einem Kandidaten ist nichts zu erraten, das bewusst zu fordern
    hieße, dass jede frische Installation (oder ein Test) erst eine Zuordnungszeile anlegen
    müsste, obwohl die Auflösung längst eindeutig ist. Erst bei MEHREREN Kandidaten ohne
    explizite Zuordnung wird nicht mehr geraten (Rückfall auf die vierte Stufe, `roof_type IS
    NULL`). Migration `06299a5101f5` übernimmt für bestehende Installationen genau die Vorlage,
    die die alte implizite Auflösung an diesem Tag auch gewählt hätte (Logik als modulweite
    Funktion `_resolve_roof_type_default_template_rows()` direkt in der Migrationsdatei, Muster
    aus 1.2.19/`_resolve_roof_component_type_rows`, damit einzeln testbar).
  - **Kompakte Berichtsseite** (`service_reports.html`, seit 1.2.22): bei mehreren Flächen mit je
    ~20 Prüfpunkten war die vorher flache, immer ausgeklappte Liste unbedienbar. Prüfpunkte
    gruppieren sich jetzt zuerst nach Dachfläche (eigener, standardmäßig zugeklappter Block mit
    Fortschritt "12 von 31", auch bei genau einer Fläche – Konsistenz statt Sonderfall, gilt
    auch für Altbestand-Berichte über die synthetisierte `roof_areas`-Liste) und darin nach
    `group_name` wie bisher (jetzt einzeln klappbar, aber offen per Default). Ein Gesamtfortschritt
    plus Liste noch offener Pflichtpunkte steht oberhalb aller Flächen-Blöcke, sobald das
    Prüfpunkte-Panel eines Berichts geöffnet ist – Prüfpunkte werden dafür seit dieser Version
    für JEDEN Bericht eager geladen (`loadReports()`, Muster wie das bereits bestehende
    `loadReportExtras()` für Mängel/Fotos), nicht mehr erst beim ersten Aufklappen. Ein bereits
    erfasster Mangel rendert jetzt inline direkt am zugehörigen Prüfpunkt (echte `findingCard()`,
    nicht mehr nur ein Hinweis-Button) statt ausschließlich im separaten "Mängel"-Panel – das
    bleibt zusätzlich bestehen, zeigt aber seither NUR NOCH Mängel OHNE Prüfpunktbezug (sonst
    würde dieselbe Mangel-Karte zweimal mit denselben DOM-IDs rendern, sobald beide Panels
    gleichzeitig offen sind). Jeder Prüfpunkttyp kann jetzt eine Bemerkung tragen (vorher nur
    `free_text`-Punkte) über einen "+ Bemerkung"-Toggle, automatisch aufgeklappt, wenn bereits
    Text vorhanden ist. "Wartung durchführen" navigiert direkt zu
    `/orders/{order_id}/service-reports?report={report_id}` – ein neuer, seither unterstützter
    Deep-Link öffnet nur das Prüfpunkte-Panel dieses Berichts, die Dachflächen-Blöcke darin
    bleiben trotzdem zugeklappt (kein Widerspruch zum Abnahmekriterium "beim Öffnen ist keine
    Prüfliste aufgeklappt"). Bewusst NICHT das mobile Layout (spätere Iteration) – nichts hier
    Gebautes muss dafür zurückgebaut werden.
  - **Materialerfassung** (`ServiceReportMaterial`, seit 1.2.23, `__tablename__
    "service_report_materials"`): der Monteur erfasst nur, WAS verbraucht wurde, NIE einen
    Preis – bewusst keine Preisspalte an dieser Tabelle, Bepreisung passiert ausschließlich beim
    Rechnungslauf im Büro (siehe "Rechnung aus Zeitbuchungen" unten). Zwei gleichwertige
    Erfassungswege: `material_id` gesetzt (aus dem Katalog gewählt, über die bereits
    bestehende Suche `GET /api/materials?search=` – dieselbe, die `service_form.html` für die
    Kalkulation nutzt, kein zweites Widget) kopiert `description`/`unit` als Schnappschuss aus
    `Material` (`app/models.py`, `name`/`unit`/`purchase_price`/`price_basis`/`catalog_id` →
    `MaterialGroup`, **nicht** → `Catalog`, das ist der Leistungskatalog-Container für
    `Service`); ändert sich der Katalogeintrag später, bleibt im Bericht stehen, was tatsächlich
    verbaut wurde. `material_id` leer (frei eingetippt) verlangt eine eigene `description` vom
    Monteur und erzeugt NIE einen neuen Katalogeintrag – der Katalog ist Stammdatenpflege des
    Büros, nicht des Monteurs; solche Zeilen sieht das Büro erst beim Rechnungslauf.
    `roof_area_id`/`inspection_item_id`/`finding_id` sind alle unabhängig optional und schließen
    sich **nicht** aus (anders als bei `ServiceReportPhoto`, das genau eins von beiden verlangt)
    – Material kann pauschal am Bericht hängen, einer Fläche zugeordnet sein und/oder zu einem
    konkreten Mangel gehören; am Mangel gibt es dafür einen "+ Material"-Button
    (`openMaterialFormForFinding()`), der den nächsten über das Formular angelegten Eintrag
    direkt diesem Mangel zuordnet. Unveränderlich nach der Unterschrift wie Prüfpunkte und
    Fotos – anders als beim `Finding` gibt es hier keinen lebendigen Nachverfolgungsteil, was
    verbaut wurde ändert sich nicht mehr; `sign_report()` bekommt dafür KEINE neue
    Pflichtprüfung, ein Einsatz ohne Materialverbrauch ist normal. Auf der Berichtsseite ein
    dritter, gleichrangiger Panel-Umschalter ("Material") neben Prüfpunkte/Mängel – bewusst
    NICHT als Order-weiter Seitenblock wie "Erfasste Zeiten", weil `service_report_id` NOT NULL
    ist (Material gehört immer zu genau einem Bericht) und ein Order-weiter Block keine
    eindeutige Berichtszuordnung anbieten könnte. PDF: neuer Abschnitt "Verbrauchtes Material"
    nach den Prüfpunkten, vor den Mängeln (Bezeichnung/Menge/Einheit, keine Preise/Summe), bei
    mehreren Dachflächen nach Fläche gruppiert (Muster wie die Prüfpunkte); ein Bericht ohne
    Material rendert byte-identisch zu 1.2.22.
  - **Strukturierte Prüfpunkte** (`InspectionTemplate`/`InspectionTemplateItem`/
    `InspectionItem`, seit 1.2.16, `app/inspection_templates.py`/eigener Abschnitt in
    `app/service_reports.py`, Verwaltung unter Einstellungen → Prüfvorlagen bzw.
    `/inspection-templates`): eine Wartung prüft nicht "das Dach", sondern einzelne Bauteile.
    Eine Vorlage (je Dachtyp, `roof_type IS NULL` = gilt für jeden) beschreibt Prüfpunkte mit
    festem `item_type` (`ja_nein`/`condition_grade`/`measurement`/`quantity`/`leak_test`/
    `free_text`/`photo` – Code-Tupel `ITEM_TYPES`, keine Optionsgruppe). `create_report()`
    "multipliziert" beim Anlegen eines Wartungsberichts die aufgelöste Vorlage
    (`_resolve_inspection_template()`, vierstufig: explizit → Vertragsposition →
    passender `roof_type` → `roof_type IS NULL`) gegen den tatsächlichen, nicht archivierten
    Bauteilbestand der aufgelösten Dachfläche (`_resolve` analog, über `roof_area_id` oder
    `MaintenanceContractItem.roof_area_id`) – `_generate_inspection_items()` kopiert dabei
    **physisch** alle anzeigerelevanten Vorlagenfelder auf `InspectionItem` (nie zur Laufzeit
    von der Vorlage gelesen), damit eine spätere Vorlagenänderung einen bereits erzeugten
    Bericht nicht rückwirkend ändert – `template_item_id`/`roof_component_id` sind entsprechend
    reine, optionale Herkunftsangaben, die ins Leere zeigen dürfen. `sort_order` eines
    generierten Punkts = `Vorlagenpunkt-sort_order * 1_000_000 + (Bauteil-sort_order %
    1_000_000)` – der Modulo verhindert, dass eine hohe Bauteil-`sort_order` in das Band des
    nächsten Vorlagenpunkts rutscht. Ändert sich der Bauteilbestand zwischen Berichtsanlage und
    Ausführung, gibt es zwei getrennte Mechanismen: `sync_inspection_items()` (rein additiv,
    läuft automatisch beim Öffnen der Berichtsseite, ergänzt nur fehlende Punkte, rührt
    bestehende nie an) und `regenerate_inspection_items()` (kompletter Neuaufbau mit
    Datenverlust, nur auf ausdrücklichen Klick im Entwurf, nutzt bewusst die aktuelle statt der
    eingefrorenen Vorlagenversion). `sign_report()` blockiert seit 1.2.16 zusätzlich, solange
    ein Pflichtpunkt unbeantwortet ist (`ValueError` mit der Anzahl) – ein Bericht ohne
    Prüfpunkte verhält sich unverändert. `delete_roof_component()` bekommt vorausschauend
    denselben Blockier-Schutz wie `delete_roof_area()` (nur bei Verweis aus einem bereits
    **unterschriebenen** Bericht, `set_roof_component_archived()` bleibt uneingeschränkt) –
    wegen der für die nächste Iteration geplanten Mängelhistorie, die `roof_component_id`
    anders als `InspectionItem` heute aktiv dereferenzieren wird. **Datenverlust behoben (seit
    1.2.19)**: `setResultAndSave()` in `service_reports.html` (OK/Nicht-OK/Entfällt-Klick eines
    `ja_nein`/`leak_test`-Punkts) sendete nur `{result}` und übersprang dabei den sonst üblichen
    Container-Read der Geschwisterfelder – ein `leak_test`-Punkt verlor dadurch bei jedem Klick
    sein bereits erfasstes `duration_minutes`. `saveInspectionResult()` liest den Container jetzt
    IMMER, Overrides werden per `Object.assign` nur noch darübergelegt statt den Read zu
    ersetzen; `update_inspection_item(db, item_id, fields: dict)` selbst wechselt ebenfalls auf
    das `exclude_unset`-Muster von `upsert_roof_layer()` (siehe oben). Das Pflicht-Freitextfeld
    bekommt zusätzlich das debounced Speichern aus `_debounce.html` – sonst hätte ein Monteur,
    der einen Punkt austippt und direkt "Unterschreiben" drückt, ohne wegzuklicken, eine falsche
    "Pflichtpunkt nicht beantwortet"-Meldung bekommen.
  - **Mängel und Fotos** (`Finding`/`ServiceReportPhoto`, seit 1.2.17, `app/findings.py` bzw.
    Erweiterung von `app/service_reports.py`): macht aus einem negativen Prüfergebnis eine
    Handlung. `severity`/`action`/`status` sind feste Code-Tupel (`SEVERITIES`/`ACTIONS`/
    `STATUSES` in `app/findings.py`), keine Optionsgruppen. `roof_component_id` wird bei
    Anlage aus `inspection_item.roof_component_id` übernommen, falls vorhanden – dadurch
    greift der in 1.2.16 vorausschauend gebaute Blockier-Schutz auf `delete_roof_component()`
    jetzt tatsächlich, mit einer zweiten, eigenen Bedingung: ein referenzierender `Finding`
    blockiert **unabhängig vom Berichtsstatus** (anders als der `InspectionItem`-Fall, der nur
    bei unterschriebenen Berichten greift), da ein Mangel schon im Entwurf seine Wirkung
    entfaltet (Folgeauftrag/Aufgabe/Wiedervorlage). `ServiceReportPhoto` gehört immer zu GENAU
    EINEM Prüfpunkt ODER GENAU EINEM Mangel, nie zu beidem/keinem – ausschließlich in
    `add_photo()` geprüft, bewusst kein `CheckConstraint` (`models.py` enthält an keiner
    Stelle einen, das wäre der erste seiner Art). Fotos werden über
    `resize_and_store_photo()` (`app/service_report_photos.py`, Vorbild
    `app/roof_area_sketches.py`) serverseitig mit Pillow auf 1600 px verkleinert und
    einheitlich als JPEG gespeichert (`exif_transpose()` gegen die reine Metadaten-Drehung von
    Handyfotos) – Pillow ist über `reportlab` ohnehin Pflichtabhängigkeit, seit 1.2.17
    zusätzlich explizit in `requirements.txt`.

    Die drei Maßnahmen haben je einen einmaligen Ausführungsschritt (`_execute_finding_action()`):
    "sofort_behoben" schließt direkt (`closed_at`/`closed_by_employee_id`), "zurueckgestellt"
    verlangt `resubmission_date`. **"buero_pruefen" (seit 1.2.21, vorher zwei getrennte
    Maßnahmen)**: legt bei aktivem Aufgabenmodul NUR eine Aufgabe an (sonst ersatzlos, Mangel
    bleibt "offen") – erzeugt NIE mehr einen Auftrag/ein Projekt. Vorher gab es dafür zwei
    getrennte Maßnahmen ("folgeauftrag" rief sofort `create_quick_service_order()` auf und
    navigierte mitten im noch nicht unterschriebenen Bericht in die Projektmappe,
    "angebot_erforderlich" legte nur eine Aufgabe an) – fachlich dieselbe Entscheidung ("das
    muss vom Büro aus weiterbearbeitet werden"), der Monteur musste vorher nur raten, welche
    der beiden es wird. Der eigentliche Vorgang entsteht jetzt ausschließlich über
    `create_follow_up_project_for_task()` (siehe Abschnitt "Aufgabe" unten, "Vorgang erstellen"
    aus der Aufgabe heraus) – ein bewusster Klick des Sachbearbeiters am Schreibtisch, nicht
    mehr automatisch beim Anlegen des Mangels. Eine reine Daten-Migration (`9e3bb642c686`)
    schreibt bestehende Findings mit den beiden alten Maßnahmen auf "buero_pruefen" um, OHNE die
    `follow_up_*`-Spalten anzufassen. **Die Idempotenzsperre hängt bewusst an einem eigenen
    Ausführungs-Artefakt der jeweiligen Maßnahme** (`_action_already_executed()`: für
    "buero_pruefen" `follow_up_task_id` ODER `follow_up_order_id` – **beide**, nicht nur das
    neue, weil ein migrierter, ehemals "folgeauftrag"-Mangel nur `follow_up_order_id` trägt und
    ohne diese zweite Prüfung fälschlich nicht gesperrt wäre), NICHT an "war die Maßnahme vorher
    etwas anderes" – das erlaubt sowohl das spätere Nachholen einer bei deaktiviertem
    Aufgabenmodul ausgefallenen Aufgabe (exakt dieselbe Maßnahme wird erneut ausgewählt, ihr
    Artefakt fehlt weiterhin) als auch einen jederzeitigen Wechsel weg von "sofort_behoben", der
    `closed_at`/`closed_by_employee_id` zurücksetzt. **Fallstrick, der real aufgetreten ist**:
    `create_finding()`/`update_finding_followup()` müssen bei einem fehlschlagenden
    `_execute_finding_action()` (z. B. "zurueckgestellt" ohne Datum) explizit `db.rollback()`
    aufrufen – sonst bleibt eine bereits geflushte bzw. geänderte, nie committete Zeile in der
    Session hängen und wird vom nächsten, völlig unabhängigen erfolgreichen `db.commit()`
    derselben Session stillschweigend mit übernommen.

    `update_finding_followup()` ist die **einzige** Stelle, die einen `Finding` auch nach der
    Unterschrift noch ändern darf – eingefroren ist die FESTSTELLUNG (`description`/`severity`/
    Bauteilbezug/Fotos), lebendig bleibt ihre NACHVERFOLGUNG (`status`, Maßnahmenwechsel,
    `resubmission_date`, `closed_*`). Genau das bereits etablierte Muster von `sign_report()`
    neben dem allgemein blockierten `update_report()` – keine neue Erfindung, nur ein zweiter
    Anwendungsfall desselben Prinzips. **Bewusst NICHT gebaut**: ein zweiter, aus dem
    Folgeauftrag entstandener Bericht schließt den ursprünglichen Mangel nie automatisch, auch
    nicht bei seiner eigenen Unterschrift – passend zum durchgängigen Prinzip dieses Projekts
    ("Vorgang erstellen" ist immer ein bewusster Klick, kein Scheduler), und weil ein zweiter
    Bericht aus einem ganz anderen Grund unterschrieben werden könnte, ohne den ursprünglichen
    Mangel tatsächlich behandelt zu haben. Der Rückweg bleibt manuell:
    `update_finding_followup(status="erledigt")`.

    `sign_report()` bekommt drei weitere Prüfungen NACH der 1.2.16-Pflichtpunkt-Prüfung, jede
    mit eigener Meldung: (1) ein `InspectionItem` mit `result="nok"` oder `condition_grade` 3/4
    braucht mindestens einen `Finding`, (2) jeder `Finding` braucht mindestens ein Foto, (3) ein
    `Finding` mit `action="zurueckgestellt"` braucht `resubmission_date` (zusätzlich zur bereits
    bei Anlage/Änderung erzwungenen Prüfung). Ein Bericht ohne Prüfpunkte und ohne Mängel
    durchläuft alle drei mit leeren Ergebnismengen – unverändertes Regressionsverhalten.
    `delete_report()` räumt bei einem Entwurf zusätzlich die über `Finding.follow_up_task_id`
    verknüpften Aufgaben auf (direkt über die FK, nicht per URL-Textabgleich wie
    `delete_contract()` seit 1.2.10 – hier existiert eine echte, eindeutige Spalte).
    PDF (`app/service_report_pdf.py`): zwei neue Abschnitte NACH den Prüfpunkten, nur wenn
    nicht leer – "Dokumentation" (Prüfpunkt-Fotos ohne Mangel, eigener Abschnitt statt
    Tabellen-Einbettung, da eine `platypus.Table` mit unterschiedlich großen Bildern die
    Zeilenhöhen unvorhersehbar macht) und "Festgestellte Mängel"; ein Bericht ohne Mängel und
    ohne Fotos rendert exakt wie vor 1.2.17. **`KeepTogether` seit 1.2.21** (`app/service_report_pdf.py`,
    `reportlab.platypus`, davor nirgends im Projekt verwendet): hält Überschrift+zugehörigen
    Inhalt zusammen, damit kein Block über einen Seitenumbruch reißt – der gemeldete Fall war
    eine im PDF zerschnittene Unterschrift (Titel/Bestätigungssatz/Bild, ~5cm, passt praktisch
    immer auf die aktuelle Seite), ebenso angewendet auf jeden Mangel-Block (Text+Fotos), jede
    Prüfpunkt-Gruppen-Überschrift+Tabelle, jeden Dokumentation-Fotoblock und "Erfasste Zeiten"
    (Titel+Tabelle). Bewusst NICHT auf den freien Beschreibungstext ("Durchgeführte Arbeiten") –
    reiner Fließtext darf wie in jedem Dokument über Seiten umbrechen. Bewusst kein erzwungener
    `PageBreak` vor dem Unterschriftenblock statt `KeepTogether`, das hätte bei jedem kurzen
    Bericht eine unnötige, fast leere Seite erzeugt.
  - **Zweite Unterschrift und einheitliche `created_by_employee_id`-Härtung (seit 1.3.0, siehe
    Abschnitt "Monteursansicht" unten für den vollen Kontext)**: `ServiceReport` bekommt drei
    neue, nullable Spalten `installer_signature_path`/`installer_signature_name`/
    `installer_signed_at`, exakt parallel zu den bestehenden (unverändert des KUNDEN
    gebliebenen) `signature_path`/`signature_name`/`signed_at` – keine neue Tabelle, die
    Kardinalität ist fix zwei. `sign_report()` verlangt jetzt vier Pflichtparameter statt zwei
    (`installer_signature_png_bytes`/`-name`, `customer_signature_png_bytes`/`-name`) und
    schreibt beide in EINEM Aufruf, Monteur zuerst, dann Kunde – die bestehenden
    Vollständigkeitsprüfungen (Pflichtpunkte, Negativbefunde, Fotos, Wiedervorlage) bleiben davor
    unverändert. `ServiceReportSign` (Schema) hat entsprechend vier Base64-Felder statt zwei.
    PDF: ein gesetztes `installer_signature_path` löst eine zweispaltige Tabelle ("Monteur"/
    "Kunde") im selben `KeepTogether`-Block aus; fehlt es (jeder vor 1.3.0 unterschriebene
    Bestandsbericht), rendert unverändert der alte Ein-Block-Pfad – byte-/textidentisch, mit
    eigenem Regressionstest geprüft. Zusätzlich bekommt `created_by_employee_id` an ALLEN VIER
    Stellen, die es kennen (`ServiceReport`, `ServiceReportPhoto`, `ServiceReportMaterial`,
    `Finding`), dieselbe Sperre wie `TimeEntry.employee_id`: ein neuer, gemeinsamer Helfer
    `_employee_for_request()` in `app/routers/service_reports.py` (Kopie von
    `_time_entry_employee_for_request()`, aber ohne dessen 422-Zweig, da das Feld überall
    nullable bleibt) lehnt einen Nicht-Admin ab, der eine fremde `employee_id` angeben will;
    `app/routers/findings.py` importiert den Helfer, statt ihn zu duplizieren. Vorher kam das
    Feld an allen vier Stellen ungeprüft aus dem Client-Payload – bewusst NICHT nur beim Bericht
    gehärtet, obwohl nur dieser ursprünglich als Risiko benannt wurde: ein `Finding` ist die
    Feststellung, aus der ggf. ein Folgeauftrag entsteht, wer sie gemacht hat, muss ebenso
    stimmen.
  - **Eingefrorene Bauteil-/Dachflächennamen (seit 1.3.12)**: bei der 1.3.11-Rahmenumstellung
    gefunden und in dieser Version behoben -- `finding.roof_component.name` (Mangel-Überschrift
    im PDF/in der Anzeige) und `link.roof_area.name` (Gruppierung von Prüfpunkten UND Material
    nach Dachfläche, jeweils Bericht-PDF UND `_report_roof_areas_to_dicts()`) lasen bisher den
    AKTUELLEN Namen des verknüpften `RoofComponent`/`RoofArea`-Datensatzes -- ein bereits
    unterschriebener, eigentlich unveränderlicher Bericht hätte sich rückwirkend geändert,
    sobald jemand ein Bauteil oder eine Dachfläche umbenennt. Zwei neue, nullable Spalten
    `Finding.roof_component_name_snapshot`/`ServiceReportRoofArea.roof_area_name_snapshot` --
    dasselbe Prinzip wie `InspectionItem.text` seit 1.2.16 (physische Kopie beim Anlegen, nie zur
    Laufzeit vom verknüpften Datensatz gelesen). `roof_component_id`/`roof_area_id` selbst
    bleiben der reine FK-Bezug (laut `Finding`-Klassendocstring ohnehin schon "eingefroren" im
    Sinne von "zeigt nie auf ein anderes Bauteil") -- der Fund betraf ausschließlich den NAMEN
    des Zieldatensatzes, der sich unabhängig vom FK ändern kann.

    Befüllt beim Anlegen: `create_finding()` (`app/findings.py`, liest `RoofComponent.name` bei
    gesetztem `roof_component_id`) und `_generate_inspection_items_for_areas()`
    (`app/service_reports.py`, `roof_area` ist dort bereits das geladene Objekt, keine
    zusätzliche Abfrage nötig). Im PDF UND in der Anzeige bevorzugt gelesen (`finding_to_dict()`,
    `_report_roof_areas_to_dicts()`, `service_report_pdf.py` an allen drei Fundstellen) --
    Rückfall auf den aktuellen Namen nur, wenn der Schnappschuss leer ist (Bestandszeilen ohne
    ihn, oder falls `roof_component_id`/`roof_area_id` fehlt). Migration `5149d369dbb6` ergänzt
    die Spalten UND befüllt bestehende Zeilen aus dem HEUTIGEN Namen (nicht historisch korrekt --
    der Name könnte seither schon geändert worden sein -- aber näher an der Wahrheit als ein
    leerer Schnappschuss, der sonst bei jedem künftigen Lesezugriff wieder auf den dann aktuellen
    Namen zurückgefallen wäre; ab der Migration ist der Wert eingefroren). Die Backfill-Logik
    steckt als zwei eigene, modulweite Funktionen direkt in der Migrationsdatei (Muster aus
    1.2.19, siehe CLAUDE.md "Testen") -- nicht in `upgrade()` verschachtelt, weil
    `batch_alter_table()`-Aufrufe (das eigentliche `ADD COLUMN`, reines Alembic-Boilerplate) sich
    mit dem bisherigen, leichten `MigrationContext`/`Operations`-Testaufbau dieses Projekts nicht
    zuverlässig ausführen lassen (SQLite-Batch-Modus braucht eine an echtes `target_metadata`
    gebundene Umgebung) -- kein bestehender Migrationstest hatte das bisher versucht. Getestet
    wird deshalb ausschließlich die Befüll-Logik selbst, direkt gegen eine Connection, nicht der
    Schema-Umbau (reines, geprüft risikoarmes Boilerplate). Gegen die echte, migrierte Datenbank
    angewendet und stichprobenhaft geprüft (4 Findings, 4 ServiceReportRoofArea-Zeilen -- alle
    mit `roof_component_id`/`roof_area_id` korrekt aus dem damaligen Namen befüllt, die beiden
    Findings ohne Bauteilbezug bleiben `NULL`).

    **Bei der zusätzlich angefragten Prüfung auf weitere live statt eingefroren gelesene
    Stellen** (Bauteiltyp, Dachtyp, Mitarbeitername, Prüfvorlagenbezeichnung) -- Ergebnis, siehe
    „Bekannte, bewusst offene Punkte" für den verbleibenden echten Fund: Bauteiltyp
    (`RoofComponent.component_type`) und Dachtyp (`RoofArea.roof_type`) werden nirgends für die
    ANZEIGE eines bereits erzeugten Berichts gelesen -- nur bei der ERZEUGUNG selbst
    (Vorlagenauflösung in `_resolve_inspection_template()`, Bauteil-zu-Vorlagenpunkt-Zuordnung in
    `_generate_inspection_items()`/`sync_inspection_items()`), kein Fund. Prüfvorlagenbezeichnung
    (`InspectionTemplate.label`, gelesen über `link.inspection_template.label`/
    `report.inspection_template.label` in `_report_roof_areas_to_dicts()`) WAR ein echter Fund --
    seit 1.3.22 behoben, siehe eigener Unterabschnitt "Eingefrorene Prüfvorlagenbezeichnung"
    unten. Mitarbeitername: die neue Monteur-Meta-Zeile (seit 1.3.11, `created_by_employee_name`
    über `report.created_by_employee`) ist ebenfalls live: die "Erfasste Zeiten"-Tabelle im PDF
    nutzt zusätzlich `entry_to_dict()`s `employee_name`, das projektweit (nicht nur im
    Einsatzbericht) immer live über `Employee.first_name`/`last_name` aufgelöst wird -- die
    etablierte, allgemeine `TimeEntry`-Konvention, keine für Einsatzberichte spezifisch
    eingeführte Lücke -- auf ausdrücklichen Wunsch bei der 1.3.22-Anfrage erneut bestätigt
    ausgenommen, bleibt unverändert.
  - **Eingefrorene Prüfvorlagenbezeichnung (seit 1.3.22)**: letzter loser Faden derselben Kette --
    `ServiceReportRoofArea.inspection_template_label_snapshot` (neue, nullable Spalte, physisch
    beim Anlegen aus `template.label` befüllt, `_generate_inspection_items_for_areas()`, `template`
    ist dort bereits das geladene Objekt) friert jetzt auch die Vorlagenbezeichnung ein --
    `_report_roof_areas_to_dicts()` liest sie bevorzugt, Rückfall auf den aktuellen Namen nur bei
    leerem Schnappschuss (Bestandszeilen, oder falls kein Template aufgelöst wurde). Migration
    `14b130f9c315` (Muster `5149d369dbb6`, gleicher Docstring-Wortlaut zur Backfill-Begründung)
    befüllt bestehende Zeilen aus dem HEUTIGEN Label -- gegen die echte, migrierte Datenbank
    angewendet und stichprobenhaft geprüft (4 Zeilen, alle korrekt aus dem damaligen Vorlagennamen
    befüllt). **Bewusst NICHT gespiegelt auf den Legacy-Zweig** (`ServiceReport.inspection_template_id`
    für Berichte von vor 1.2.22, `_report_roof_areas_to_dicts()`s zweiter `return`-Zweig sowie
    `report_to_dict()`s Top-Level-Feld) -- exakt dieselbe, bereits von `roof_area_name` seit 1.3.12
    dort etablierte Asymmetrie: diese Spalten werden von `create_report()` für KEINEN neuen
    Bericht mehr beschrieben, ein nachträglicher Schnappschuss dort würde also nie mehr etwas
    einfrieren, was nicht schon vor der jeweiligen Migration eingefroren war. Bei der Gelegenheit
    ein letztes Mal projektweit auf weitere live statt eingefroren gelesene Stellen im
    Einsatzbericht geprüft (`service_reports.py`/`service_report_pdf.py`, vollständiger Grep auf
    `.label`/`.name`) -- kein weiterer Fund über die bereits bekannten, bewusst unveränderten
    Fälle hinaus (Mitarbeitername, siehe oben; `finding_to_dict()`s `property_name`/`customer_name`
    sind kein Fund, da sie zur lebendigen Mangel-NACHVERFOLGUNG gehören, nicht zur eingefrorenen
    Feststellung -- dieselbe Unterscheidung wie bei `update_finding_followup()`, siehe dort).
- **Rechnung aus Zeitbuchungen** (`invoice_type="aufwand"`, seit 1.2.2, in `app/invoices.py`):
  dritter und letzter laut Plan angekündigter Teilschritt des Moduls `wartungen`. Neuer,
  vierter Rechnungstyp neben `abschlag_pauschal`/`abschlag_leistungsstand`/`schluss` – Positionen
  entstehen aus `TimeEntry`-Zeilen (nur `status="booked"`, nicht laufende Timer), gruppiert nach
  Mitarbeiter+Tätigkeit, ein einheitlicher Stundenpreis für alle Positionen aus dem globalen
  Stundenverrechnungssatz (`CalculationSettings.labor_rate`, `get_or_create_settings()` in
  `app/calculation.py` – bewusst NICHT die aufwendigere `calculate_labor_rate()`-Herleitung, die
  Settings-UI-Berechnung ist ein anderer Anwendungsfall). Wie jede andere Rechnung nur ein
  Entwurf, Positionen bleiben vor dem Finalisieren voll prüf-/änderbar. **Fallstrick, den man
  kennen sollte**: `get_or_create_settings()` `db.commit()`t intern, falls noch keine
  `CalculationSettings`-Zeile existiert, UND ruft dafür `sa_inspect(db.get_bind())` auf, um die
  `catalog_id`-Spalte zu prüfen – auf einer SQLite-`:memory:`-Testdatenbank (nicht in der echten
  Datei-DB) kann das über eine zweite `Inspector`-Connection auf demselben, per
  `SingletonThreadPool` wiederverwendeten Rohverbindungsobjekt einen bereits geflushten, aber
  noch nicht committeten Datensatz verwerfen. Deshalb ruft `create_invoice_from_time_entries()`
  diese Funktion ganz bewusst **vor** dem Anlegen der neuen `Invoice` auf, nicht danach – gilt
  als Vorsichtsmaßnahme für jede künftige Funktion, die `get_or_create_settings()` mit noch
  ungesichertem Session-Zustand kombiniert, nicht nur für diese eine Stelle.
  - **Materialpositionen seit 1.2.23**: `create_invoice_from_time_entries()` bekommt einen
    neuen, dritten Parameter `materials: list[ServiceReportMaterial]` (Router lädt über die neue
    `list_materials_for_invoicing()` in `app/service_reports.py`, exakt dasselbe "Router lädt,
    Funktion verarbeitet"-Muster wie bei `time_entries`) – nur unterschriebene Berichte liefern
    Material, Entwürfe bleiben außen vor, exakt das `TimeEntry`-Prinzip. Zeitpositionen zuerst,
    danach Material. Katalogzeilen (`material_id` gesetzt) werden nach `(material_id, unit)`
    gruppiert und die Menge summiert – **über mehrere Berichte desselben Auftrags hinweg**;
    freie Zeilen (`material_id` leer) werden NIE zusammengefasst, auch nicht bei identischem
    Text, das wäre zu riskant. Bepreisung mit dem AKTUELLEN Katalogpreis zum Zeitpunkt des
    Rechnungslaufs (kein Schnappschuss) – **inklusive** globalem Materialaufschlag
    (neue Funktion `effective_material_sale_price()` in `app/calculation.py`,
    `CalculationSettings.material_markup_pct`, dieselbe Formel wie im Material-Abschnitt von
    `build_calculation()`, aber als eigene Funktion, um dieses bestehende, funktionierende Stück
    Code nicht anzufassen). **Bewusste Entscheidung, keinen ungefilterten Einkaufspreis zu
    verwenden**: `Material.purchase_price` ist ein Einkaufspreis, ihn ungefiltert als
    `unit_price` zu setzen hieße, Material ohne Aufschlag an den Kunden weiterzugeben, ohne dass
    es auffällt – schlechter als gar kein Preis, weil es wie ein gültiger Preis aussieht. Steht
    der globale Aufschlag auf 0 % (Standardwert jeder Installation, die ihn nie konfiguriert
    hat), bekommt die Antwort des Routers (`app/routers/invoices.py::post_invoice_from_time_entries()`)
    deshalb ein neues, optionales `InvoiceOut`-Feld `material_markup_hint` mit einem erklärenden
    Satz – kein persistiertes Feld, keine neue Warnleiste in `invoice.html`, `order.html`s
    `createNewInvoice()` zeigt ihn (falls vorhanden) einmalig per `alert()`, bevor sie wie bisher
    direkt zur neuen Rechnung navigiert. Frei eingetipptes Material bleibt bei `unit_price =
    Decimal("0")` – das Büro trägt den Preis im (bis zum Versenden frei bearbeitbaren)
    Rechnungsentwurf nach, die Position soll dabei sichtbar bleiben, nicht fehlen. Funktions-
    und Routenname bleiben bewusst `create_invoice_from_time_entries()`/`aus-zeitbuchungen` –
    die "Rechnung aus Aufwand"-Umbenennung ist rein am sichtbaren Text nachvollzogen
    (`order.html`/`project_folder.html`-Labels), nicht am Python-Symbol/Pfad, um keinen rein
    kosmetischen Diff ohne fachlichen Anlass zu erzeugen.
- **Schnellauftrag für Reparatur/Wartung** (`create_quick_service_order()` in
  `app/quick_service_orders.py`, seit 1.2.12, `POST /api/quick-service-orders`): ein einzelner
  Reparatur-/Wartungsauftrag soll sich in einem Schritt anlegen lassen, ohne dass der Nutzer
  Projekt, Angebot und Beauftragung einzeln durchläuft. Technisch entsteht dabei trotzdem die
  normale Kette `Project` → `Quote` → `Order`, da `create_order_from_quote()`
  (`app/orders.py`) zwingend mindestens eine `QuoteItem`-Position verlangt (leeres Angebot kann
  nicht beauftragt werden) – dafür funktionieren Rechnung, Zeiterfassung und Einsatzbericht
  anschließend ohne jeden Sonderfall weiter. Die dafür automatisch angelegte Platzhalter-
  Position ("Reparatur/Wartung nach Aufwand") trägt bewusst `unit_price=0`: abgerechnet wird
  später über "Rechnung aus Zeitbuchungen" auf Basis der tatsächlich gebuchten Stunden, nicht
  über diese LV-Position. `order_type` ("reparatur"/"wartung") steuert nur diese Bezeichnung,
  keine eigene Spalte – die eigentliche Unterscheidung passiert später am Einsatzbericht
  (`report_type` "rapport"/"wartung"). Formular als zweiter Bereich auf `/maintenance-contracts`
  (jetzt betitelt "Wartungen & Reparaturen"), verwendet dieselben JS-Helfer
  (`customerOptionsHtml`/`propertyOptionsHtml` mit Hauptadresse-Fallback) wie das
  Wartungsvertrag-Formular auf derselben Seite.
- **Wartungshistorie pro Gebäude** (seit 1.2.4, `list_property_history()` in
  `app/service_reports.py`, `GET /api/orders/{id}/property-service-reports`): zeigt auf der
  Einsatzbericht-Seite eines Auftrags alle bereits **unterschriebenen** Berichte aus ANDEREN
  Aufträgen desselben Gebäudes. Da `Order` selbst keine `property_id`-Spalte hat (nur
  `property_name`/`property_address` als Text-Schnappschuss, siehe oben), wird das Gebäude über
  `order.project.property_id` aufgelöst – ist dort kein Gebäude verknüpft (bei `Project`
  optional), bleibt die Karte im Frontend einfach ausgeblendet, kein Fehlerfall.
- **Dashboard-Widget "Fällige Wartungen"** (seit 1.2.5, `due_maintenance`-Eintrag in der
  `WIDGETS`-Registry, `app/templates/dashboard.html`): wie jedes Widget nur ein weiterer
  Registry-Eintrag (siehe `UserDashboardWidget` oben), bewusst NICHT in `DEFAULT_LAYOUT`
  aufgenommen – erscheint nur, wenn ein Nutzer es aktiv über "+ Widget hinzufügen" dazuholt.
  Zeigt `is_due`-Verträge aus `GET /api/maintenance-contracts`, blendet sich über
  `isModuleEnabled('wartungen')` selbst aus, wenn das Modul deaktiviert ist.
- **Monteursansicht** (`GET /vor-ort`, seit 1.3.0, `app/routers/field_view.py`,
  `app/templates/vor_ort.html`): eigene, schmale Einstiegsseite fürs Fahrzeug-Tablet statt einer
  zweiten App – dieselbe Codebasis, dieselbe Anmeldung. **Bewusst kein eigener
  `OPTIONAL_MODULES`-Eintrag** (siehe Modul-Umschalter oben): eine neue Oberfläche über bereits
  bestehenden (Plantafel, immer aktiv) bzw. bereits eigenständig geschalteten (Wartungsberichte,
  intern `is_module_enabled(db,"wartungen")`) Daten, kein neues fachliches Modul – analog dazu,
  dass auch Dashboard und Plantafel selbst keine `OPTIONAL_MODULES`-Einträge sind.
  - **Heutige Einsätze, beide Zuordnungswege** (`list_todays_assignments_for_employee()` in
    `app/planning.py`, neuer Endpunkt `GET /api/field-view/today`): eine
    `PlanningSlot.id IN (...)`-Vereinigung aus Team-Zugehörigkeit (`Employee` →
    `WorkPreparationTeamEmployee` → `.assignment_id` → `WorkPreparationTeamAssignment` →
    `PlanningSlot.team_assignment_id`, Snapshot der Team-Besetzung zum Zuweisungszeitpunkt) UND
    direkter Einzelzuweisung (`Employee` → `WorkPreparationEmployee` → `.preparation_id` →
    `WorkPreparation` → `PlanningSlot.preparation_id` – die Zuordnung hängt an der AV selbst,
    nicht am einzelnen Slot, jeder Slot dieser AV zählt). Ein Mitarbeiter, der für dieselbe AV
    über BEIDE Wege zutrifft, taucht nur einmal auf (`seen_slot_ids`). Adress-/Objektname-
    Auflösung exakt wie `slot_to_dict()`: `order.project.property` geht vor,
    `order.property_name`/`-address` (Text-Schnappschuss) ist der Rückfall ohne verknüpftes
    Objekt – wiederverwendet, nicht neu erfunden. Der Endpunkt löst den Mitarbeiter
    AUSSCHLIESSLICH über `request.state.erp_user.employee_id` auf, nie über einen
    Client-Parameter – jeder sieht ausschließlich seine eigenen Einsätze; fehlt die Verknüpfung,
    eine klare 422-Fehlermeldung statt eines leeren, stillen Zustands. Ein Klick auf eine Karte
    führt direkt zu `/orders/{id}/service-reports` (die Berichtsseite), NIE zur Auftragsseite.
  - **Offene Entwurfsberichte** (`list_draft_reports_for_employee()` in
    `app/service_reports.py`): `status="entwurf" AND created_by_employee_id==eigene_id`, sortiert
    nach `updated_at` absteigend ("zuletzt gearbeitet" – es gibt kein eigenes "zuletzt bearbeitet
    von"-Feld). Nur aufgerufen, wenn `is_module_enabled(db,"wartungen")`.
  - **Reduzierte Navigation statt der vollen Sidebar** (`app/templates/_mobile_header.html`):
    `_sidebar.html` ist eine reine, unparametrisierte Include-Datei ohne Zwischenstufe zwischen
    "volle Sidebar" und "gar keine" (geprüft) – neue, eigene, schlanke, sticky Kopfzeile statt
    einer Konfigurationsoption an `_sidebar.html`. Drei Ziele, alle ≥44px: Einsätze (diese
    Seite), Zeiterfassung (bestehende `/time-tracking`-Seite, unverändert), Abmelden (derselbe
    `POST /api/auth/logout`-Endpunkt, den `_sidebar.html` bereits nutzt – kein neuer
    Logout-Mechanismus). Zeigt `current_user.display_name` prominent ("ein Bericht, der
    versehentlich unter fremdem Namen unterschrieben wird, ist das Schlimmste, was hier
    passieren kann"). `service_reports.html` bekommt bewusst KEINE eigene Kopfzeile – es bleibt
    bei `_sidebar.html`, die `current_user.display_name` und einen Ein-Klick-Abmelden-Button
    bereits mitbringt.
  - **`service_reports.html` responsiv statt eines zweiten Templates**: ein neuer
    `@media(max-width:900px)`-Block (Tablet-Breakpoint, konsistent mit `planning.html` 950px/
    `tasks.html`/`time_tracking.html` 900px) bringt `ja_nein`/`leak_test` als drei große Kacheln
    (neue Wrapper-Klasse `.result-picker`, `min-height:44px`) statt der kompakten Buttons,
    `condition_grade` wechselt von einem `<select>` zu vier Klartext-Kacheln (`CONDITION_GRADE_LABELS`,
    neue Funktion `setGradeAndSave()`, Muster `setResultAndSave()` – bewusst eine universelle
    Markup-Änderung statt einer geräteabhängigen Verzweigung im JS, Größe steuert allein CSS über
    die Breakpoint-Selektorspezifität), und die Material-/Zeitbuchungen-Tabellen klappen über
    `data-label`-Attribute + CSS zu gestapelten Karten (Standard-Technik, kein `pypdf`/JS-Grid
    nötig) statt nur zu scrollen (die Zeitbuchungen-Tabelle bekommt dafür erstmals denselben
    `.table-scroll`-Wrapper wie die Material-Tabelle). Alle drei Foto-`<input type="file">`
    bekommen `capture="environment"`, damit die Kamera direkt öffnet statt einer Dateiauswahl.
    Die Flächen-/Gruppen-Zuklappblöcke aus 1.2.22 bleiben UNVERÄNDERT – sie funktionieren auf
    Tablet bereits gut, kein Grund, sie anzufassen.
  - **Zwei Unterschriften, ein Zwei-Schritt-Assistent** (Frontend zu `sign_report()`, siehe
    Abschnitt "Einsatzbericht" oben für die Backend-Seite): dasselbe Unterschrift-Panel wird ein
    Zwei-Schritt-Ablauf auf derselben Karte – Schritt 1 "Monteur unterschreibt" (Name vorbelegt
    mit `authStatus.user.display_name`, aber änderbar – es kann jemand anders vor Ort gewesen
    sein als wer gerade am ERP angemeldet ist), "Weiter" merkt die PNG-Daten zwischen
    (`installerSigDataUrl`/`installerSigName`) und leert das Canvas für Schritt 2 "Kunde
    unterschreibt", "Unterschrift bestätigen" sendet beide auf einmal. Genau der Geräteablauf:
    Monteur unterschreibt, reicht das Tablet an den Kunden weiter, kein Zwischen-Request mit
    einem inkonsistenten "nur Monteur unterschrieben"-Zustand.
  - **Automatisches Abmelden nach Feierabend** (`MobileSettings`, Singleton wie `TaskSettings`/
    `MaintenanceSettings`, `shift_end_time` Default 19:00, Verwaltung unter Einstellungen →
    Vor Ort): geprüft NUR an den beiden mobilen Einstiegspunkten (`GET /api/field-view/today`
    löscht bei Überschreitung das Auth-Cookie und liefert 401), NICHT in der globalen
    `identity_and_audit_middleware` – Schreibtisch-Nutzer mit demselben Login-Mechanismus bleiben
    unberührt. **`GET /vor-ort` selbst prüft die Grenze NICHT** (bewusste Abweichung von der
    ursprünglichen Planung, die einen serverseitigen Redirect auch auf der Seite vorsah): ein
    serverseitiger Redirect auf der Seite wäre wanduhrzeit-abhängig gewesen und hätte den
    generischen `test_v218_template_rendering.py`-Seiten-Rendertest (fester, immer angemeldeter
    Test-Admin-Kontext) an manchen Tageszeiten zum Flackern gebracht – die Seite rendert deshalb
    IMMER nur das statische Gerüst, das Frontend leitet bei einem 401 von
    `GET /api/field-view/today` selbst zu `/login` weiter. Funktional identisch (derselbe
    Redirect, nur einen Request später), aber eine einzige Quelle der Wahrheit statt zweier
    Prüfstellen. **Bewusst begrenzt**: ein bereits offener Berichtstab wird beim Erreichen der
    Grenze nicht mitten in der Bearbeitung abgemeldet – die gemeinsamen Formular-Endpunkte
    (`PUT /api/inspection-items/{id}` usw.) werden nicht geprüft, das würde auch
    Schreibtisch-Nutzer treffen, die spät noch etwas nachtragen. Die 12-Stunden-Token-Laufzeit
    (`COOKIE_MAX_AGE` in `app/auth.py`) reicht für eine normale Schicht inkl. Überstunden, keine
    Änderung nötig – das ist eine andere Frage als "automatisch abmelden nach Feierabend".
  - **`created_by_employee_id`-Härtung an allen vier Einsatzbericht-Endpunkten**: siehe Abschnitt
    "Einsatzbericht" oben, Unterpunkt "Zweite Unterschrift und einheitliche
    `created_by_employee_id`-Härtung".
  - **Web-App-Manifest und PWA-Icons** (`GET /manifest.json`, `GET /api/mobile-icon/{size}.png`,
    `app/mobile_manifest.py`, beide Endpunkte in `app/routers/field_view.py`): kein
    `StaticFiles`-Mount (geprüft, es gibt im ganzen Projekt keinen einzigen – jede
    Datei-Auslieferung läuft über einen dedizierten Endpunkt, Fotos/Logo/Signaturen eingeschlossen)
    – konsistent dazu auch hier zwei dedizierte Endpunkte statt eines neuen Static-Ordners.
    `build_icon_png()` skaliert ein hinterlegtes Firmenlogo (`GeneralSettings.logo_filename`)
    zentriert auf ein Quadrat in der Akzentfarbe, sonst bleibt es beim einfarbigen
    Platzhalter-Quadrat – reine Laufzeit-Erzeugung OHNE Caching (Icons werden selten angefragt,
    nur beim "Zum Startbildschirm hinzufügen"; Einfachheit vor Optimierung, kein
    Cache-Invalidierungsproblem bei einem späteren Logo-Wechsel). `<link rel="manifest">` plus
    `theme-color`/Apple-Touch-Icon-Tags sitzen AUSSCHLIESSLICH in `vor_ort.html`s `<head>` – das
    ist die einzige Seite, die als Startadresse installiert werden soll. Kein Service Worker,
    keine Offline-Logik (bewusst außerhalb dieser Iteration).

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

## Mahnwesen: Löschen/Versenden/Bearbeiten (seit 1.3.21)

Zwei gemeldete Lücken im Mahnwesen behoben, unabhängig vom PDF-Umbau oben.

- **"Alle Mahnungen" bot für Entwürfe keine Aktion.** `delete_reminder_draft()`/
  `DELETE /api/reminders/{id}` existierten bereits und waren korrekt auf `status="entwurf"`
  beschränkt, waren aber nur in `invoice_detail.html` und der "Benötigt Aufmerksamkeit"-Tabelle
  (`mahnwesen.html`) angebunden -- nicht in "Alle Mahnungen", der einzigen Stelle, an der ein
  Betreiber üblicherweise die gesamte Historie durchsieht und ein Entwurf über die Statusspalte
  klar erkennbar ist. `renderAllRows()` zeigt für `status==='entwurf'` jetzt dieselben
  Versenden-/PDF-/Löschen-Aktionen wie `renderAttentionRows()`, über dieselben, bereits
  bestehenden `sendReminder()`/`deleteReminder()`-Funktionen -- keine Geschäftslogik dupliziert.
  Geprüft, ob es weitere Tabellen mit derselben Lücke gibt: `invoice_detail.html` war bereits
  korrekt (Versenden+Löschen für Entwürfe, PDF für alle), Dashboard/Finanzen zeigen nur
  zusammenfassende Widgets ohne Zeilenaktionen -- kein weiterer Fund.
- **Bearbeiten fehlte komplett.** Neu: `update_reminder_draft(db, reminder, *, text, fee_amount,
  new_due_date)` (`app/reminders.py`) -- lehnt mit `ValueError` ab, wenn `reminder.status !=
  "entwurf"` ist, GENAU wie `update_report()` beim Einsatzbericht (`app/service_reports.py`); der
  Schutz sitzt damit in der Geschäftslogik, nicht nur in der Oberfläche, ein direkter API-Aufruf
  kann ihn nicht umgehen. Schema `ReminderUpdate`, Endpunkt `PUT /api/reminders/{id}`
  (`app/routers/reminders.py`, `ValueError` -> 400). `text` bleibt bewusst das ROHE Feld mit
  unaufgelösten Platzhaltern (`{mahngebuehr}` usw.) -- exakt dieselbe Konvention wie beim
  Bearbeiten einer Mahnstufe selbst (Einstellungen → Mahnstufen, `ReminderLevel.text_template`),
  keine zweite Konvention für dasselbe Konzept eingeführt. Oberfläche (Regel 4: kein `prompt()`,
  ein bereits sichtbares, vorausgefülltes Formular auf der Seite): ein "Bearbeiten"-Knopf bei
  jedem Entwurf (beide Tabellen in `mahnwesen.html`, teilen sich EIN Panel, das an den zuletzt
  geklickten Entwurf gebunden wird -- ein Entwurf kann ohnehin immer nur von einem Panel
  gleichzeitig bearbeitet werden) bzw. ein eigenes, kleineres Panel direkt in der
  Mahnwesen-Karte von `invoice_detail.html`.
- **Untersucht: Zusammenspiel von Mahntext und Zahlen.** Die Sorge war, dass eine Bearbeitung
  von `fee_amount`/`new_due_date` einen im Fließtext bereits eingesetzten, jetzt veralteten Wert
  stehen lassen könnte. Tatsächliches Verhalten beim Anlegen, geprüft direkt am Code
  (`create_reminder()`/`format_reminder_text()`): der Text wird NICHT einmalig erzeugt und
  gespeichert, sondern `Reminder.text` bleibt für die gesamte Lebensdauer eines Entwurfs die rohe
  Vorlage mit unaufgelösten Platzhaltern -- `formatted_text` (`reminder_to_dict()`) wird bei
  JEDEM Lesezugriff frisch aus `text` + den aktuellen Feldwerten zusammengesetzt, nie
  zwischengespeichert. Eine Änderung von `fee_amount`/`new_due_date` wirkt sich dadurch beim
  nächsten Lesen bereits automatisch auf den Fließtext aus, SOLANGE die Platzhalter im Text
  erhalten bleiben -- die ursprünglich befürchtete Gefahr (Fließtext zeigt eine andere Zahl als
  die Forderungsaufstellung) tritt in dieser Form also nicht ein. Das eigentliche, engere Risiko
  entsteht erst, wenn jemand über die neue Bearbeiten-Funktion einen Platzhalter manuell durch
  eine fest eingetippte Zahl ersetzt -- dann läuft genau dieser Wert bei einer späteren
  Zahlenänderung unbemerkt auseinander, weil nichts mehr automatisch nachzieht.
- **Entscheidung gegen eine Erkennungsspalte -- ein Hinweis statt Erkennung.** Ob ein Text
  "manuell bearbeitet" wurde, ließe sich nur über eine zusätzliche, beim Speichern gesetzte
  Spalte feststellen (z. B. `text_manually_edited: bool`) -- bewusst NICHT gebaut. Begründung:
  `formatted_text` wird ohnehin bei jedem Lesezugriff frisch aus `text` + den aktuellen
  Feldwerten neu zusammengesetzt (siehe oben), das Restrisiko betrifft ausschließlich den
  Sonderfall eines manuell ersetzten Platzhalters -- dafür genügt ein Hinweis im Moment des
  Speicherns, eine dauerhaft mitgeführte Spalte (samt der Frage, wann sie zurückgesetzt werden
  müsste) wäre unverhältnismäßig. Stattdessen zwei kleine, rein im Bearbeiten-Panel wirkende
  Maßnahmen (`app/templates/mahnwesen.html`/`invoice_detail.html`, kein Backend-Code nötig):
  1. **Nicht-blockierender Hinweis beim Speichern** (`reminderMissingPlaceholderWarning()`, in
     beiden Templates dupliziert -- kein gemeinsames JS-Modul in diesem Projekt, siehe
     Design-System-Konvention): prüft beim Klick auf "Speichern", ob `{mahngebuehr}` im Text
     fehlt (Feld `fee_amount` ist immer gesetzt) bzw. `{neue_frist}` fehlt, während
     `new_due_date` einen Wert trägt. Speichert trotzdem immer (kein `return` vor dem
     `PUT`-Aufruf) -- reiner `alert()` danach, GENAU wie die bereits bestehenden
     Fehlermeldungen in diesen Dateien, keine neue Interaktionsart. Es kann gute Gründe geben,
     einen Platzhalter absichtlich zu ersetzen; das wird nicht verhindert, nur sichtbar gemacht.
  2. **Platzhalterliste mit Bedeutung statt nur Token** direkt im Bearbeiten-Panel (vorher, seit
     der ersten 1.3.21-Fassung, nur eine flache Token-Zeile -- dabei fiel auf, dass sie
     fälschlich `{mahnstufe}` auflistete, das laut `_reminder_placeholders()`/
     `send_reminder_email()` NUR für die E-Mail-Vorlagen gilt, nicht für `Reminder.text`; jetzt
     korrigiert). Geprüft, ob eine solche Liste beim Bearbeiten einer Mahnstufe (Einstellungen →
     Mahnstufen, `renderReminderLevels()` in `settings.html`) schon existiert: ja, aber nur als
     flacher Token-String ohne Bedeutung -- dessen Token-Auswahl (korrekt ohne `{mahnstufe}`)
     wurde für die neue, um Bedeutungen ergänzte Liste übernommen, `settings.html` selbst blieb
     unangetastet (nicht Teil dieser Anfrage, weiterhin nur der flache Token-String dort). Wer
     sieht, dass es einen Platzhalter für die Mahngebühr gibt, tippt die Zahl seltener von Hand.

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

## Leistungskatalog vs. Stammdaten (seit 1.3.25, Sidebar-Umbau seit 1.3.26–1.3.28)

**`/leistungskatalog` (`app/templates/index.html`), bisher nirgends in dieser Datei dokumentiert.**
Sidebar-Eintrag "Leistungskatalog" (nicht zu verwechseln mit Stammdaten → "Leistungskataloge",
das nur die `Catalog`-Container selbst verwaltet -- siehe unten). Diese Seite ist die tatsächliche
Leistungsverwaltung: XML-Import ("Leistungen Dach"), globale Kalkulationsvorgaben
(Lohnansatz/Materialaufschlag/Gemeinkosten/Wagnis & Gewinn, `GET/PUT /api/calculation-settings`),
eine durchsuchbare Leistungsliste mit Verschieben/Kopieren zwischen Katalogen
(`moveOrCopyService()`, `POST /api/services/{id}/move|copy`) und ein Kalkulationsdetail je
Leistung (Quelldaten, DACHKONZEPTE-Kalkulation mit Overrides, Materialstückliste). Kennt bereits
`?catalog_id=<id>` zur Vorfilterung auf einen Katalog. `/services/new`/`/services/{id}/edit`
(`service_form.html`) sind die zugehörigen Anlegen-/Bearbeiten-Unterseiten.

**Fehlerbehebung: "Leistungen ansehen" führte auf die Startseite.** `master_data.html`
(Stammdaten → Leistungskataloge) und `service_form.html` (Redirect nach Speichern) verlinkten auf
`/?catalog_id=<id>` -- ein Ziel, das diesen Parameter nirgends auswertet, daher der Rückfall auf
das Dashboard. Ursprünglich als fehlende Seite diagnostiziert (dafür eine neue "Leistungen"-Ansicht
probeweise in `master_data.html` gebaut) -- die tatsächliche Ursache war aber nur ein fehlendes
Pfadsegment: `/leistungskatalog` (siehe oben) leistete bereits alles Nötige, inklusive desselben
`catalog_id`-Parameters. Die probeweise gebaute Ansicht wurde deshalb wieder verworfen, korrigiert
sind stattdessen die drei betroffenen Links (`/leistungskatalog?catalog_id=<id>`).

**Sidebar-Bestandsaufnahme (im selben Zug angefragt, keine Codeänderung, Vorschlag wartet auf
Rückmeldung).** Vollständige Liste aller 17 `_sidebar.html`-Ziele und aller 8
`master_data.html`-Bereiche wurde erstellt (nicht hier wiederholt, siehe Chatverlauf) -- die
wichtigsten Ergebnisse:
- **Keine zwei Sidebar-Einträge zeigen auf dasselbe Ziel.** Jeder der 17 Einträge hat ein eigenes,
  gültiges Ziel; keiner führt ins Leere oder auf eine nach jüngeren Umbauten leere Seite (`/finanzen`,
  `/history`, `/findings` wurden gezielt gegengeprüft -- alle drei vollständig funktionsfähig,
  keine Karteileichen).
- **"Mitarbeiter" ist ein ECHTES Duplikat**, wie vom Nutzer vermutet: Sidebar → `/employees`
  (`employees.html`, ein einzelnes, reichhaltiges Formular+Übersicht-Blatt mit Vergütungsrechner)
  und Stammdaten → "Mitarbeiter" (`master_data_form.html`s `employeeForm()`, separate Anlegen-/
  Bearbeiten-Seite) verwalten dieselben `Employee`-Datensätze über dieselbe API, nur mit
  unterschiedlicher, unterschiedlich reichhaltiger Oberfläche.
- **"Leistungskatalog" ist KEIN Duplikat von Stammdaten → "Leistungskataloge"**, anders als vom
  Nutzer zunächst vermutet (sie tragen nur ähnliche Namen): Stammdaten verwaltet ausschließlich die
  `Catalog`-CONTAINER (Name, Beschreibung, Archivieren) -- für die enthaltenen LEISTUNGEN selbst
  (Suche, Bearbeiten, Kalkulation, XML-Import, globale Kalkulationsvorgaben) gibt es in der
  Stammdatenverwaltung heute **keine** Entsprechung. Würde "Leistungskatalog" ersatzlos aus der
  Sidebar entfernt, wären XML-Import und die globalen Kalkulationsvorgaben ohne jede Ersatzseite
  nicht mehr erreichbar -- diese Lücke müsste zuerst geschlossen werden (naheliegend: eine
  "Leistungen"-Unteransicht analog zum bereits bestehenden "Materialien"-Muster in
  `master_data.html` ergänzen; die globalen Kalkulationsvorgaben passen inhaltlich eher zu
  Einstellungen als zu Stammdaten, da sie Systemkonfiguration und keine Stammdaten-Entität sind).
- **"Vor Ort" fehlt in der Sidebar**, obwohl vom Nutzer als tägliches Werkzeug erwartet -- das ist
  KEIN Versehen, sondern die seit 1.3.0 dokumentierte, bewusste Entscheidung: die Monteursansicht
  hat einen eigenen, reduzierten Einstiegspunkt (`_mobile_header.html` + PWA-Manifest fürs
  Fahrzeug-Tablet), keinen Platz in der vollen Desktop-Sidebar.
- **"Angebote"/"Aufträge"/"Rechnungen" haben keine eigenen Sidebar-Einträge** -- es gibt
  projektweit keine eigenständige Listenseite für Angebote oder Aufträge (`grep` bestätigt: kein
  `/quotes`- oder `/orders`-Listenendpunkt, nur `/quotes/{id}/edit` bzw. `/orders/{id}` für ein
  einzelnes Dokument); beide werden ausschließlich über "Projekte" (`project_folder.html`)
  erreicht. Rechnungen laufen über "Finanzen" (`/finanzen`, vollständige Rechnungsliste). Das
  entspricht dem heutigen Stand, nicht notwendigerweise dem, was der Nutzer mit "täglich: ...
  Angebote, Aufträge, Rechnungen" gemeint hat -- zur Klärung vorgemerkt, nicht selbst entschieden.
- Vorschlag für eine neue Sidebar-Struktur wurde vorgelegt (täglich vorne, Einrichtung hinten,
  "Mitarbeiter" aus der Sidebar zugunsten von Stammdaten entfernt, "Leistungskatalog" bleibt
  vorerst, bis die Lücke in Stammdaten geschlossen ist) -- **noch keine Entscheidung des Nutzers,
  keine Codeänderung**.

### Umsetzung der vier Anmerkungen (seit 1.3.26)

Der Nutzer hat den 1.3.25-Vorschlag mit vier Anmerkungen bestätigt ("Ja, bau das") und zusätzlich,
mitten in der Umsetzung, eine fünfte, ausdrücklich vor jeder Codeänderung zu prüfende Ergänzung
nachgereicht (siehe Anmerkung 2 unten).

**1. Mitarbeiter -> `/employees`.** Stammdaten → "Mitarbeiter" leitet jetzt per
`location.href='/employees'` um, statt eine eigene Inline-Ansicht zu zeigen. Der eigenständige
Sidebar-Eintrag "Mitarbeiter" entfällt (die Duplikat-Feststellung aus 1.3.25 war korrekt: dieselben
`Employee`-Datensätze über dieselbe API, nur unterschiedlich reichhaltig dargestellt).
`master_data_form.html`s `employeeForm()`/`syncFunction()`/`syncCompensation()` sind vollständig
entfernt, `pages.py`s `master_data_create_page`/`master_data_edit_page` akzeptieren `"employees"`
als `data_type` nicht mehr. `/employees` bekommt eine Rückwärtsnavigation ("← Stammdaten",
`history.back()` -- dasselbe Muster wie in `master_data_form.html`/`service_form.html`), da man ab
jetzt ausschließlich über Stammdaten dorthin gelangt, nicht mehr über einen eigenen Sidebar-Link.

**Echter Funktionsverlust gefunden und vor Abschluss behoben**: "die reichhaltigere Oberfläche
gewinnt" traf nur teilweise zu -- `/employees` kannte `show_on_planning_board`
(Plantafel-Sichtbarkeit/Kapazitätsberücksichtigung) bisher gar nicht; das war ausschließlich über
`master_data_form.html`s jetzt entfernte `employeeForm()` steuerbar. Ohne Nachrüsten wäre diese
Steuerung beim Wegfall der schlanken Variante ersatzlos verschwunden. Nachgerüstet: eine Checkbox
in `employees.html`, verdrahtet in `editEmployee()`/`resetForm()`/`saveEmployee()`s Payload (Feld
existiert bereits als `EmployeeUpdate.show_on_planning_board: bool = True`, `app/schemas.py`),
sowie eine neue Spalte "Planung" in der Übersichtstabelle. Die alte, in `syncFunction()` verbaute
Heuristik (automatisches Abwählen bei Funktionsnamen wie "Lager"/"Büro"/"Verwaltung") wurde bewusst
NICHT übernommen -- eine Verfeinerung, kein Kernverhalten, außerhalb des Umfangs dieser Aufräumung.

**2. Kalkulationsvorgaben -- vom vermuteten Umzug zum bestätigten Duplikat.** Der Nutzer reichte
mitten in der Umsetzung nach: die globalen Kalkulationsvorgaben stehen bereits unter Einstellungen
→ "Kalkulationsgrundlagen" -- kein Umzug, sondern mutmaßlich ein Duplikat, und forderte eine Prüfung
VOR jeder Änderung (Sorge: zwei getrennte Datensätze, von denen einer nie in `build_calculation()`
einfließt -- das wäre ein ernster Befund gewesen). Geprüft, bevor irgendetwas geändert wurde:

- Beide Oberflächen rufen exakt denselben Endpunktpaar auf: `GET/PUT /api/calculation-settings`
  (`app/routers/settings.py`), das ausschließlich `get_or_create_settings(db)`
  (`app/calculation.py`) liest/schreibt -- eine einzige, durch `catalog_id IS NULL` bestimmte
  Singleton-Zeile in `calculation_settings`.
- Direkte Abfrage der echten `dachkonzepte_erp.db` bestätigt: genau eine Zeile
  `(id=1, catalog_id=NULL, labor_rate=82.5, material_markup_pct=10, overhead_pct=0,
  risk_profit_pct=0, use_source_time_as_minutes=1)`.
- Beide Oberflächen bilden identisch dieselben fünf Felder ab (`labor_rate`/`material_markup_pct`/
  `overhead_pct`/`risk_profit_pct`/`use_source_time_as_minutes`) -- **keine** zeigt mehr oder
  andere Felder als die andere.
- `build_calculation()` liest ausschließlich über denselben `get_or_create_settings()`/
  `get_settings_for_catalog()`-Pfad -- es gibt keinen zweiten, unbenutzten Datensatz, der jemals
  gepflegt, aber nie für Angebotspreise verwendet würde. Der vom Nutzer befürchtete ernste Fall
  (Divergenz zwischen gepflegtem und tatsächlich wirksamem Wert) tritt nicht ein, weil es nur eine
  einzige Zeile gibt, die von beiden UIs gemeinsam benutzt wird.

Ergebnis: dasselbe, kein Duplikat im Sinne getrennter Datensätze, sondern **dieselbe Einstellung an
zwei Stellen editierbar** -- der genau vom Nutzer benannte Duplikat-Fall, nur mit demselben statt
verschiedenen Daten. Wie vom Nutzer für diesen Fall vorgegeben ("Falls es dasselbe ist, entfällt
die Ansicht im Leistungskatalog"): die Kalkulationsvorgaben-Karte in `/leistungskatalog`
(`app/templates/index.html`, samt `loadSettings()`/`saveSettings()`) ist entfernt, ersetzt durch
einen Verweis-Text mit Link auf `/settings#calculation` -- Einstellungen → Kalkulationsgrundlagen
bleibt die einzige Bearbeitungsoberfläche.

**Weitere Doppelungen im Projekt gesucht (auf Nachfrage), keine gefunden.** Geprüft, welche
Templates tatsächlich `PUT`-Aufrufe (nicht nur `GET`) gegen die bekannten Einstellungs-Endpunkte
absetzen (`calculation-settings`, `maintenance-settings`, `labor-rate-settings`,
`reminder-settings` u. Ä.): schreibend ist in jedem Fall ausschließlich `settings.html` --
`employees.html`/`master_data_form.html` (liest `labor-rate-settings` für die
Stundenlohn-Vorschau), `dashboard.html`/`maintenance_contract.html` (liest `maintenance-settings`
für Fälligkeitsanzeige/Vorbelegung) und `service_form.html` (liest `calculation-settings` für die
Live-Kalkulationsvorschau) sind bestätigt reine Lesezugriffe für Anzeige/Vorbelegung, keine
konkurrierenden Bearbeitungsoberflächen. Die Kalkulationsvorgaben-Karte war der einzige echte Fund.

**Damit schrumpft die verbleibende Lücke aus 1.3.25** auf genau das, was übrig bleibt, wenn
"Leistungskatalog" eines Tages aus der Sidebar entfernt werden soll: eine **Leistungen-Ansicht in
den Stammdaten** (nach dem bereits etablierten "Materialien"-Muster in `master_data.html`) **plus
der XML-Import**. Beide sind bewusst noch NICHT gebaut -- eigener, späterer Schritt, siehe
"Nächster Schritt" unten. Die Kalkulationsvorgaben sind mit dieser Version bereits vollständig aus
der Lücke heraus (nie verlagert, weil sie nie ein zweiter Ort waren -- nur der zweite Zugang
entfällt).

**Nächster Schritt, wie hier vorgemerkt, umgesetzt -- aber anders als ursprünglich skizziert (seit
1.3.27):** vor dem Bauen einer eigenen Leistungen-Ansicht in `master_data.html` erst geprüft, ob
sie überhaupt gebraucht wird. Ergebnis: nein -- `/leistungskatalog` (`app/templates/index.html`)
funktioniert bereits ohne `catalog_id` sinnvoll (XML-Import-Karte und Kalkulationsvorgaben-Verweis
sind ohnehin immer sichtbar, die Leistungsliste lädt ohne Parameter schlicht `/api/services`
ungefiltert -- Suche, Detail/Kalkulation, Verschieben/Kopieren funktionieren katalogübergreifend
identisch). Eine zweite, einfachere Ansicht in den Stammdaten wäre reine Duplikation gewesen.
Stattdessen: die Stammdaten-Katalogliste bekommt einen zusätzlichen Link zum parameterlosen
Einstieg (nach demselben Muster, das "alle Materialien anzeigen" in der Materialkataloge-Ansicht
bereits nutzt), und `/leistungskatalog` bekommt eine Rückwärtsnavigation zu den Stammdaten (Muster
`/employees` aus 1.3.26) -- die Seite ist ab jetzt nur noch von dort aus erreichbar, nicht mehr
über einen eigenen Sidebar-Eintrag. Der Sidebar-Eintrag "Leistungskatalog" entfällt damit, siehe
Abschnitt "Umsetzung der vier Anmerkungen" oben für die Bestätigung, dass "Leistungen ansehen" in
der Katalogliste bereits seit 1.3.25 korrekt verlinkt.

**Randbefund bei der Prüfung gefunden und auf Wunsch im selben Zug behoben:** sowohl die
Leistungsliste (`index.html`) als auch die Materialliste (`master_data.html`) hatten eine mit
"Katalog" beschriftete Tabellenspalte, die tatsächlich die Bearbeiten-/Verschieben-/
Kopieren-Aktionen zeigte, nicht den Herkunftskatalog der Zeile -- beim gezielt gefilterten
Aufruf (`catalog_id` gesetzt) unproblematisch, beim jetzt neu hinzukommenden parameterlosen,
katalogübergreifenden Durchsuchen fehlte dadurch eine sichtbare Zuordnung. `ServiceListOut.
catalog_name` stand bereits seit 1.3.24 bereit (`Service.catalog` per `selectinload`), musste in
`index.html`s `renderServices()` nur noch tatsächlich angezeigt werden. Für die Materialliste
existiert kein serverseitiges `catalog_name` (`MaterialCatalogOut` trägt nur `catalog_id`) --
dafür aber bereits das komplett geladene `materialGroups`-Array, aus dem eine neue, kleine
Hilfsfunktion `materialGroupName(id)` (Muster `customerName(id)`) den Namen client-seitig
auflöst, ohne Backend-Änderung. In beiden Tabellen wurde dafür eine echte, neue "Katalog"-Spalte
ergänzt und die bisher fälschlich so benannte Aktionsspalte in "Verschieben / Kopieren"
umbenannt -- statt nur einer der beiden Spalten, damit die Bedeutung an keiner Stelle mehrdeutig
bleibt.

**3. Sichtbare Gruppenüberschriften.** Neue CSS-Klasse `.app-sidebar-group` in `_sidebar.html`,
optisch nach demselben Muster wie `settings.html`s `.settings-group` (klein, fett, Großbuchstaben,
gedämpfte Farbe), inkl. eingeklappter Variante für die eingeklappte Sidebar. Die beiden Gruppen am
Seitenende heißen "Stammdaten" (Stammdatenverwaltung, Leistungskatalog) und "System" (Einstellungen,
Benutzer, Änderungshistorie).

**4. Backoffice bleibt bei Zeiterfassung.** Backoffice ist fachlich ein Teil der Zeiterfassung
(Abwesenheitsanträge/Korrekturen für den ganzen Betrieb, nicht Systemkonfiguration) und wird
täglich bzw. mehrmals wöchentlich gebraucht, nicht nur bei der Einrichtung -- admin-only ist hier
eine reine Sichtbarkeits-/Berechtigungsfrage, keine Häufigkeits- oder Kategorisierungsfrage (auch
Benutzerverwaltung ist admin-only und trotzdem eindeutig System, weil sie fachlich Einrichtung ist;
Backoffice ist fachlich Tagesgeschäft und bleibt es, unabhängig davon, wer sie sehen darf). Bleibt
deshalb unverändert als eingerückter Unterpunkt direkt unter "Zeiterfassung" im täglichen,
oberen Bereich der Sidebar -- keine Codeänderung an dieser Stelle nötig, nur die Einordnung explizit
bestätigt.

**Bestätigte, bereits vorher entschiedene Abweichungen vom 1.3.25-Vorschlag** (keine Codeänderung):
"Vor Ort" bleibt außerhalb der Desktop-Sidebar; eigene Listenseiten für Angebote/Aufträge/
Rechnungen werden nicht gebaut -- beides bleibt so, bis der laufende Betrieb zeigt, dass es fehlt.

### Benutzer und Änderungshistorie (seit 1.3.28)

Vierter Fall derselben Aufräumreihe (nach Leistungskatalog, Mitarbeitern, Kalkulationsvorgaben).
Vor jeder Änderung geprüft, wie bei den drei vorherigen Fällen:

- **Was zeigt `/users`, was der "Benutzer"-Menüpunkt in den Einstellungen?** `settings.html` hat
  in der System-Gruppe nur einen reinen Navigationslink (`<a href="/users">Benutzer &amp;
  Zugriff</a>`) -- kein eigenes `data-settings-section`, kein `<section>`, kein einziger Aufruf
  von `/api/users`/`/api/auth/status` irgendwo in der Datei. Es gibt also nur **eine** echte
  Oberfläche (`users.html`), keine zwei konkurrierenden Implementierungen wie bei Mitarbeitern
  (`employees.html` vs. das entfernte `employeeForm()`) oder Kalkulationsvorgaben (zwei Formulare
  für dieselbe Zeile). Dieselbe Prüfung für `/history`: identisches Bild, nur ein Link zu
  `history.html`, kein eigener Datenbereich, kein `/api/audit-logs`-Aufruf in `settings.html`.
- **Funktionen, die nur auf einer Seite existieren?** Erübrigt sich -- da es nur je eine echte
  Oberfläche gibt, kann nichts zwischen zwei Varianten auseinanderlaufen. Anders als beim
  1.3.26-Fund bei `show_on_planning_board` gab es hier keine zweite Implementierung, in der ein
  Feld hätte fehlen können.
- **Entscheidung**: "vollständigere Oberfläche gewinnt" löst sich trivial zugunsten der jeweils
  einzigen echten Seite auf -- beide bleiben bestehen, `settings.html` verlinkte bereits vorher
  darauf (die "wird von dort verlinkt"-Bedingung war also schon erfüllt). Übrig blieb nur die
  Navigationsfrage: Sidebar-Direktlinks entfernen (`_sidebar.html`), Rückwärtsnavigation
  "← Einstellungen" auf `users.html`/`history.html` ergänzen (Muster `/employees`/1.3.26,
  `/leistungskatalog`/1.3.27).
- **Nebenbefund 1, echter Bug, unabhängig von der Entscheidung behoben**: `settings.html`
  (Kalkulation → Stundenverrechnungssatz) verlinkte noch auf `/master-data#employees` -- dieser
  Hash-View existiert seit der 1.3.26-Mitarbeiter-Migration nicht mehr in `master_data.html`
  (`viewFromHash()`s erlaubte Liste kennt `'employees'` nicht mehr), der Link fiel seither
  stillschweigend auf die Kunden-Ansicht zurück. Korrigiert auf `/employees`.
- **Nebenbefund 2, bewusst NICHT angefasst**: `/time-backoffice` ist ebenfalls doppelt verlinkt
  (Sidebar, eingerückt unter Zeiterfassung, admin-gated -- UND Einstellungen → System →
  "Zeiterfassungs-Backoffice"). Anders als Benutzer/Historie sitzt Backoffice aber bewusst in der
  TÄGLICHEN Sidebar-Gruppe, nicht unter "System" -- die 1.3.26-Entscheidung ("fachlich
  Tagesgeschäft, admin-only ist nur eine Sichtbarkeitsfrage") bleibt gültig, das Muster
  "in beiden Oberflächen unter System einsortiert" trifft hier nicht zu. Unverändert gelassen.
- **Zugriffsasymmetrie bei `/users`, gemeldet, nicht behoben (kein Teil dieses Auftrags)**: der
  jetzt entfernte Sidebar-Link war admin-gated (`{% if is_admin %}`), der Settings-Link war es
  nie. Das ändert an der tatsächlichen Erreichbarkeit nichts -- weder `/users` selbst noch
  `GET /api/users` sind serverseitig auf Admins beschränkt (nur `PUT`/`POST`(bei bereits
  konfiguriertem System)/`DELETE`), ein Nicht-Admin konnte die volle Benutzerliste also schon
  vorher sehen, die Sidebar hat es ihm nur versteckt. `/history`/`GET /api/audit-logs` waren auf
  beiden Wegen schon immer ungated, keine Asymmetrie dort.
- **Abschließende erneute Vollprüfung der Sidebar gegen die Einstellungen** (vierter Durchgang,
  alle 14 damaligen Sidebar-Ziele gegen alle Einstellungen-Menüpunkte abgeglichen): kein weiterer
  Fund über die beiden oben genannten Nebenbefunde hinaus. Die übrigen `data-settings-section`-
  Menüpunkte (Aufgaben, Wartungen, Plantafel & Kapazität, …) sind reine Konfiguration zu einem
  Sidebar-Modul, nicht dieselben Daten -- kein Duplikat. `/inspection-templates` und `/changelog`
  waren schon vorher nur über die Einstellungen erreichbar.

### Mitarbeiter-Formular list-first (seit 1.3.29)

Gemeldeter Ausreißer, unabhängig von den vier Doppelungen-Fällen oben, aber im selben
Aufräum-Umfeld: `/employees` verhielt sich anders als jeder andere Stammdatenbereich.

- **Ursache**: `employees.html` ist eine der ältesten Seiten des Projekts (schon vor der
  1.3.26-Mitarbeiter-Migration und lange vor dem `master_data.html`/`master_data_form.html`-Muster
  gebaut) -- ein zweispaltiges `.grid`-Layout zeigte Formular UND Liste immer gleichzeitig
  nebeneinander, das Formular immer im Anlegen-Zustand vorbelegt (`<h2 id="formTitle">Mitarbeiter
  anlegen</h2>`). Mit der 1.3.26-Migration wurde diese Seite zum alleinigen Einstieg für
  Mitarbeiter, ohne dass ihr grundlegender Aufbau dabei geprüft wurde -- der Ausreißer bestand
  vorher schon, fiel aber erst jetzt auf, wo die Seite der einzige Weg zu Mitarbeitern ist.
- **Vergleich mit den übrigen Stammdatenbereichen, wie angefragt**: Kunden, Objekte, Teams,
  Fuhrpark & Maschinen, Lieferanten, Leistungskataloge, Materialkataloge/Materialien laufen alle
  über `master_data.html` -- dessen `render()` zeigt für jeden `current`-Typ sofort eine Liste
  (`table(...)`), NIE ein eingebettetes Formular. Anlegen/Bearbeiten passiert ausschließlich auf
  einer eigenen Seite (`master_data_form.html`, bzw. bei Kunden/Objekten deren eigene Detailseiten
  `customer.html`/`property.html`), erreichbar erst über einen bewussten Klick auf "+
  Hinzufügen"/"Bearbeiten"/"Öffnen" -- der SEKTIONS-Einstieg selbst ist überall die Liste. Kein
  weiterer Ausreißer gefunden.
- **Umbau, ohne die Seite auf zwei Routen aufzuteilen**: `employees.html` bleibt EINE Seite (kein
  Umzug des Formulars auf eine zweite URL wie bei den `master_data.html`-Bereichen) -- die
  Mitarbeiterübersicht ist jetzt die einzige beim Laden sichtbare Sektion (steht auch im Markup
  zuerst), das Formular steckt in einem `id="formCard"`-Abschnitt mit `class="hidden"`
  (`.hidden{display:none!important}`, Muster `index.html`/`master_data.html`). Ein neuer Knopf
  "+ Neuer Mitarbeiter" (`openCreateForm()`) im Listenkopf ruft `resetForm();showForm()` auf;
  "Bearbeiten" (`editEmployee()`) endet jetzt auf `showForm()` statt auf dem bisherigen, rohen
  `window.scrollTo({top:0,...})` (das ins Bild scrollte, aber nichts einblenden musste, da das
  Formular vorher ohnehin immer sichtbar war). Der bisherige "Neu / Abbrechen"-Knopf heißt jetzt
  schlicht "Abbrechen" (`cancelForm()`: `resetForm();hideForm()`) -- ein "Neu, aber offen bleiben"
  ergibt im list-first-Modell keinen Sinn mehr. Nach erfolgreichem Speichern (Anlegen ODER
  Bearbeiten) blendet `saveEmployee()` das Formular jetzt ebenfalls aus und kehrt zur Liste zurück
  -- exakt das Muster von `master_data_form.html`, das nach jedem Speichern auf
  `/master-data#<type>` zurückspringt, hier eben ohne Seitenwechsel.
- **Dabei gefunden und mitkorrigiert**: die bisherige "Gespeichert."-Bestätigung stand im
  `#status`-Feld INNERHALB des Formulars -- wird das Formular nach dem Speichern ausgeblendet,
  wäre sie unsichtbar gewesen. Entfernt (kein Ersatz nötig, die aktualisierte Liste ist die
  Bestätigung -- entspricht dem Projektstandard, siehe die stillen Re-Renders nach
  Archivieren/Verschieben/Kopieren in `master_data.html`/`index.html`, dort ebenfalls ohne eigene
  Erfolgsmeldung). Ein zweiter, selbst gefundener Fall derselben Art: eine STARTFEHLER-Meldung
  (`load().catch(...)`) landete vorher ebenfalls im Formular-Status -- das hätte einen echten
  Ladefehler jetzt unsichtbar gemacht, da das Formular beim ersten Laden ja gerade ausgeblendet
  ist. Dafür ein neues, immer sichtbares `<div id="startupError" class="status err hidden">`
  direkt unter der Rückwärtsnavigation ergänzt.
- **Geprüft, dass nichts verlorengeht** (wie verlangt): Vergütungsrechner (`syncCompensation()`,
  `#effectiveWage`/`#wageFormula`), `show_on_planning_board` (1.3.26) und alle übrigen Formularfelder
  (Adresse, Kontaktdaten, Kosten-Zuordnung, Sachbearbeiter-Freigabe usw.) sind unverändert im
  `#formCard`-Abschnitt vorhanden -- nur ihre Sichtbarkeit beim Laden hat sich geändert, keine
  Funktion wurde entfernt. Acht neue Tests (`tests/test_v245_employees_list_first.py`) sichern
  Struktur (Liste vor Formular im Markup, Formular initial `hidden`), Verhalten (Öffnen/Schließen/
  Speichern/Abbrechen) und die vollständige Feldliste einzeln ab.
- **UI-Testabdeckung, ehrlich benannt**: `tests/test_v218_template_rendering.py` bestätigt (als
  Teil der vollen Suite), dass die Seite server-seitig weiterhin fehlerfrei rendert; das
  clientseitige JS wurde durch sorgfältiges manuelles Nachvollziehen geprüft (Klammerbilanz,
  Kontrollfluss), nicht durch einen echten Browser -- in dieser Umgebung stand kein
  Browser-Automatisierungswerkzeug (Playwright o. Ä.) zur Verfügung, `.venv` enthält es nicht als
  Projektabhängigkeit. Kein automatisierter Ersatz für einen echten Klicktest, sollte bei
  Gelegenheit von Tobias einmal im Browser bestätigt werden.
- **Bewusst nur eine Zwischenstation**: diese Etappe behob ausschließlich das gemeldete
  list-first-Symptom, ließ `/employees` aber als eigene Seite mit eigener Formular-Logik bestehen
  -- zwei weitere Abweichungen vom Stammdaten-Muster (fehlende Navigationsleiste, Formular statt
  eigener Seite bei Anlegen/Bearbeiten) blieben zunächst bestehen und wurden erst in 1.3.30
  behoben, siehe dort. `employees.html` (inkl. `tests/test_v245_employees_list_first.py`)
  existiert seit 1.3.30 nicht mehr.

### Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher (seit 1.3.30)

Direkte Fortsetzung von 1.3.29 -- derselbe Ausreißer, zwei weitere gemeldete Abweichungen vom
Stammdaten-Muster: die Stammdaten-Navigationsleiste fehlte auf `/employees` (nur ein
Zurück-Link), und Anlegen/Bearbeiten blendeten ein Formular ein statt eine eigene Seite zu öffnen
-- bei Teams/Lieferanten/Fuhrpark/Materialien läuft beides über `master_data_form.html`.

**Vor dem Bauen geprüft, wie verlangt: lässt sich `/employees` in das bestehende Muster
einfügen, statt es dort nachzubauen?** Zwei Wege standen zur Wahl -- (a) Mitarbeiter wird ein
regulärer `master_data.html`-Bereich, Formular über `master_data_form.html`; (b) `/employees`
bleibt eigene Seite, übernimmt aber Navigation und Formularseiten-Aufbau des Stammdaten-Musters.
Geprüft wurde konkret, ob der Vergütungsrechner (der einzige Teil von `/employees`, der über ein
gewöhnliches Adressformular hinausgeht) sich sinnvoll in `master_data_form.html` unterbringen
lässt:

- Der Vergütungsrechner zerfällt bei genauem Hinsehen in ZWEI unabhängige Teile. **Aggregierte
  Kennzahlen** (gewichteter Mittellohn, Mitarbeiterzahl je Kosten-Zuordnung) sind reine
  Client-Berechnung aus dem bereits geladenen `employees`-Array -- ein reines LISTEN-Feature,
  gehört fachlich nach `master_data.html`, nicht in eine Formularseite. **Die Live-Vorschau des
  kalkulatorischen Stundenlohns** (aktualisiert sich beim Tippen von Monatsgehalt/Wochenstunden,
  bevor gespeichert wird) ist reine Formular-JS-Logik ohne Serverkontakt -- architektonisch nichts
  anderes als das, was `master_data_form.html`s `teamForm()` bereits heute mit den dynamischen
  Mitarbeiter-/Ressourcen-Checkboxen macht (Fetch beim Laden, Nachrendern bei Auswahländerung).
- Alle Felder aus `EmployeeCreate`/`EmployeeOut` (`app/schemas.py`) entsprachen 1:1 dem, was
  `employees.html` ohnehin schon abfragte -- kein Endpunkt, kein Feld verlangt etwas, das
  `master_data_form.html`s generische `init()`/`save()`-Struktur nicht bereits für andere Typen
  leistet (Datensatz laden bei `editing`, Payload zusammenbauen, `PUT`/`POST`). `EmployeeOut`
  liefert `function_name`/`effective_hourly_wage` bereits serverseitig berechnet -- die
  LISTE braucht dafür keine einzige Zusatzabfrage (kein `functions`-Fetch nötig, anders als im
  Formular).
- **Kein Hindernis gefunden -- Weg (a) gewählt**, wie vom Nutzer favorisiert ("dann existiert ein
  Muster statt zwei Ähnlicher"). Vor dem Bauen wurde das Ergebnis der Prüfung berichtet und
  bestätigt (wie verlangt), erst danach umgesetzt.

**Umsetzung:**

- `master_data.html`: Mitarbeiter ist jetzt ein regulärer `current`-Bereich wie jeder andere.
  Der Sidebar-Knopf lautet wieder `data-view="employees" onclick="showView('employees')"` (keine
  eigene Seite mehr). `employees` kommt zurück in den `load()`-`Promise.all(...)`-Aufruf
  (`/api/employees`, ungefiltert -- kein `functions`/`labor-rate-settings`-Fetch nötig, siehe
  oben). Ein neuer `current==='employees'`-Zweig zeigt die Kennzahlen-Kacheln (wiederverwendet
  die bereits vorhandene, bis dahin ungenutzte `.metric`-CSS-Klasse dieser Datei) und darunter
  die Tabelle (Muster: exakt dieselben Spalten wie das frühere `employees.html`, "Bearbeiten"
  verlinkt jetzt auf `/master-data/employees/${x.id}/edit` statt eine Inline-Funktion aufzurufen).
- `master_data_form.html`: neue `employeeForm()` plus die dafür nötigen Helfer
  (`activeFunctions()`/`renderFunctionSelect()`/`selectedFunction()`/`syncFunction()`/
  `syncCompensation()`, 1:1 aus `employees.html` übernommen, nur `document.getElementById`-Aufrufe
  auf den bereits vorhandenen `el()`-Helfer umgestellt). Neue globale Variablen `functions`/
  `laborRateSettings`, in `init()`s `employees`-Zweig per `Promise.all([...])` geladen (Muster:
  `teams`-Zweig lädt genauso `employees`/`resources`). Neue CSS-Klasse `.hint` ergänzt (für die
  Stundenlohn-Vorschau-Box) -- `.check` (Checkbox-Zeile) existierte bereits unbenutzt in dieser
  Datei und wird jetzt zum ersten Mal wirklich gebraucht. Bewusst OHNE die alten "Adresse"/
  "Kontaktdaten"-Zwischenüberschriften von `employees.html` -- kein anderes Formular in dieser
  Datei gliedert seine Felder so, ein flaches `.grid` wie überall sonst passt besser zum
  etablierten Stil dieser Datei als die alte Optik von `employees.html` zu bewahren.
- `save()` bekommt einen `employees`-Zweig; die allgemeine Pflichtfeldprüfung
  (`if(!body.name)throw Error(...)`) greift für Mitarbeiter nicht (kein `name`-Feld, nur
  `first_name`/`last_name`) -- exakt dieselbe Ausnahme-Logik, die schon vor der 1.3.26-Migration
  hier stand und beim Entfernen extra dokumentiert wurde, jetzt identisch wiederhergestellt.
- `pages.py`: Route `/employees` entfernt, `"employees"` wieder in die erlaubten `data_type`-Mengen
  von `master_data_create_page`/`master_data_edit_page` aufgenommen. `employees.html` gelöscht.
- `settings.html` (Kalkulationsgrundlagen-Hinweis): Link zurück auf `/master-data#employees`
  (die 1.3.28-Korrektur auf `/employees` wird damit bewusst zurückgenommen) -- **ausdrücklich
  keine wiedereingeschleppte Regression**: die 1.3.28-Korrektur war zum damaligen Zeitpunkt
  richtig (der Hash-View existierte seinerzeit nicht mehr), jetzt gilt das Gegenteil, weil
  `#employees` durch diese Version wieder existiert. Wer `git blame`/die Versionshistorie liest,
  soll diesen Link nicht für eine versehentliche Rückkehr des ursprünglichen 1.3.26-Bugs halten.
- **Neues, dauerhaftes Prinzip**: siehe Regel 10 oben -- jeder Stammdatenbereich zeigt beim
  Einstieg die Liste, trägt die Stammdaten-Navigation, Anlegen/Bearbeiten öffnen immer eine
  eigene Formularseite. Gilt für jeden künftigen Bereich, nicht nur rückwirkend für Mitarbeiter.
- **Tests**: `tests/test_v246_employees_master_data_reintegration.py` (neu) prüft die
  Wiedereingliederung vollständig -- Route/Datei weg, Navigationsleiste vorhanden, Liste vor
  Formular, Anlegen/Bearbeiten verlinken auf `master_data_form.html`, Vergütungsrechner in beiden
  Teilen (Kennzahlen in der Liste, Live-Vorschau im Formular) vorhanden,
  `show_on_planning_board` und alle übrigen Felder vollständig, `settings.html`-Link korrekt.
  Mehrere ältere Tests (`test_v242`, `test_v244`, `test_v063`, `test_v067`, `test_v092`,
  `test_v062`), deren Annahmen die 1.3.26–1.3.29-Zwischenstände geprüft hatten, wurden umgeschrieben
  statt nur angepasst -- sie prüfen jetzt den aktuellen, nicht mehr den historischen Zustand;
  `test_v245_employees_list_first.py` entfiel vollständig (sein gesamtes Prüfobjekt existiert
  nicht mehr). Volle Suite grün.

## Adressimport aus dem Altsystem (seit 1.3.31)

Einmaliger Import einer CSV-/Excel-Datei mit Adressen aus dem alten Programm (345 Zeilen, 19
Spalten in der ersten realen Datei). Das Altsystem vergibt jeder Adresse eine Adressnummer;
zusätzlich haben manche Zeilen eine Kundennummer oder eine Lieferantennummer -- daraus ergibt sich
die Klassifikation.

### Die vier vorab abgestimmten Berichtspunkte

1. **Wo die Altsystem-Adressnummer hingehört**: als neue Spalte `legacy_address_number` direkt auf
   `Customer` **und** `Supplier` (nicht über `CustomerProfile` -- `Supplier` hat kein
   Profil-Äquivalent, für dasselbe Konzept sollten beide denselben Ort nutzen). Dient beim
   erneuten Import derselben Datei der Wiedererkennung bereits übernommener Zeilen.
2. **openpyxl**: war weder in `requirements.txt` noch im `.venv` vorhanden (geprüft) -- als neue,
   leichtgewichtige Abhängigkeit ergänzt (MIT-lizenziert, Standard für xlsx-Lesen). CSV läuft über
   die Python-Stdlib, keine weitere Abhängigkeit nötig.
3. **Rückgängigmachen**: eine `ImportRun`-Tabelle (Zeitstempel, Dateiname, Zähler je Klassifikation)
   -- jeder dabei erzeugte `Customer`/`Supplier` trägt ein nullable `import_run_id`. Ein Lauf lässt
   sich vollständig rückgängig machen (Kunden/Lieferanten werden gelöscht, `ImportRun.status` wird
   `"reverted"`), aber nur alles-oder-nichts: sobald an EINEM der dabei erzeugten Kunden/
   Lieferanten bereits etwas hängt (Projekt, Anfrage, eigenständig hinzugefügtes Objekt über die
   automatische Hauptadresse hinaus, Verwendung in der Arbeitsvorbereitung) oder eine seiner
   unzugeordneten Zeilen bereits manuell aufgelöst wurde, wird der GANZE Lauf abgelehnt -- kein
   Teil-Rückgängig, das wäre schwerer nachzuvollziehen als gar keins. Kein Verweis auf "dann eben
   Backup zurückspielen" nötig, da sich das sauber und ohne unverhältnismäßigen Aufwand bauen ließ.
4. **Zweite E-Mail-Adresse**: `Customer.email_2` (neu, nullable) -- bewusst **rein informativ**,
   fließt NICHT in `get_quote_recipient_email()`/`get_order_recipient_email()`/
   `get_invoice_recipient_email()`/`get_reminder_recipient_email()` (`app/projects.py`,
   `orders.py`, `invoices.py`, `reminders.py`) ein. Grund: alle vier Versandfunktionen kennen
   strukturell nur einen einzigen Empfänger (`to_email: str`, ein SMTP-/Graph-Empfänger je
   Sendevorgang, `_send_via_smtp()`/`_send_via_graph()` in `app/email_sending.py`) -- echte
   Mehrfachempfänger-Unterstützung dort einzubauen wäre ein eigener, größerer Umbau, kein
   Nebeneffekt eines Adressimports.

### Name-Zusammensetzung -- die größte, nachträglich vereinbarte Erweiterung

Die Quelldaten trennen Anrede/Titel/Vorname/Name, `Customer` kannte davon bisher nur ein einziges
Feld `name`. Nach Rückfrage entschieden: **volle Ablösung**, nicht nur eine Vorbefüllung.
`Customer` bekommt vier neue Spalten `salutation`/`title`/`first_name`/`last_name` --
`last_name` ist das eigentliche Pflichtfeld (trägt bei Firmenkunden den Firmennamen, die übrigen
drei bleiben dann leer). `Customer.name` wird seither AUSSCHLIESSLICH serverseitig berechnet
(`app.crm.compose_customer_name()`, in `create_customer()`/`update_customer()` aufgerufen) --
`CustomerCreate`/`CustomerUpdate` nehmen `name` nicht mehr entgegen, `CustomerOut` führt es
weiterhin als reines Ausgabefeld (für Dokumente/PDFs/Sortierung unverändert nutzbar, keine
Änderung an irgendeiner Lese-/Druckstelle nötig).

**Vor der Umsetzung ausdrücklich der Kostenpunkt zurückgemeldet, dann auf ausdrücklichen Wunsch
trotzdem umgesetzt**: `CustomerCreate(name=...)`/`CustomerUpdate(name=...)` wurden in 20 Testdateien
direkt konstruiert (24 Aufrufe), zusätzlich in 24 weiteren Dateien wurde `Customer(name=...)` roh
als ORM-Objekt gebaut (37 Aufrufe) -- zusammen 61 Konstruktionsaufrufe in 44 Testdateien, alle auf
`last_name=` (zusätzlich zu `name=` bei der rohen ORM-Variante, da dort keine automatische
Ableitung greift) umgestellt. Kein Fallback/keine Kompatibilitätsbrücke für die alte `name=`-Kwarg
eingebaut -- entspräche einer stillen Sonderregel nur für Tests, die die eigentliche
Modellinvariante (last_name ist Pflicht) aufweichen würde.

**Migration mit Backfill statt Sonderfall**: `last_name` ist NOT NULL auf einer bereits gefüllten
Tabelle (Regel 1) -- die Migration legt die Spalte zunächst mit `server_default=''` an, führt
`UPDATE customers SET last_name = name` aus (bestehende Kunden zeigen dadurch exakt denselben
Namen wie vorher, da `compose_customer_name(None, None, None, last_name)` nur `last_name` selbst
zurückgibt) und entfernt den Default danach wieder. Gegen die echte, migrierte Datenbank geprüft:
0 Kunden mit leerem `last_name` nach dem Backfill.

**Weitere, beim Spaltenabgleich gefundene Lücken, jeweils einzeln abgestimmt:**
- **Mobil**: `Customer` hatte kein `mobile`-Feld (nur `phone`/`fax`) -- auf Wunsch eine echte neue
  Spalte `Customer.mobile` (nicht über `CustomerExtraInfo`, wie zunächst vorgeschlagen).
- **Land**: `Customer` hatte kein `country`-Feld (`Supplier` schon, mit Default "Deutschland").
  Neue Spalte `Customer.country`, gleicher Default. Auf Wunsch AUCH `Property.country` ergänzt
  (ursprünglich als akzeptierte Lücke vorgeschlagen, dann doch mitgenommen) -- `resolve_as_property()`
  übernimmt das Land der Adressimport-Zeile jetzt vollständig, nichts geht beim Umwandeln in ein
  Objekt verloren.
- Alle drei neuen Personenfelder plus Land/Mobil/zweite E-Mail sind auf Wunsch auch im normalen
  Kundenformular sichtbar und editierbar (`customer.html`, `master_data_form.html`s
  `customerForm()`) -- nicht nur reine Importdaten. Anrede läuft über eine neue, self-seedende
  Optionsgruppe `customer_salutations` (Muster `customer_categories`), Titel/Vorname/Nachname
  bleiben freier Text.

### Ablauf (dreistufig, wie gefordert)

1. **Hochladen** (`POST /api/address-import/upload`, multipart): `parse_address_file()` liest CSV
   (Stdlib `csv`, Encoding-Fallback utf-8-sig → cp1252 → latin-1, Trennzeichen per
   `csv.Sniffer()`) oder Excel (`openpyxl`, `read_only=True`) anhand der SPALTENÜBERSCHRIFTEN
   (nicht der Reihenfolge) ein. Fehlt eine benötigte Spalte, wird die GANZE Datei mit einer klaren
   Meldung abgelehnt (`AddressImportError`). Telefon/Fax/Mobil werden unverändert als Text
   übernommen -- keine Reparatur, kein Erraten (bewusst auch bei absurden Werten wie `-373367`).
   Einzige technische (keine inhaltliche) Normalisierung: eine von openpyxl als `float` gelesene
   Ganzzahl-Zelle (z. B. `2404669530.0`) wird ohne die sonst entstehende `.0`-Endung dargestellt --
   das ist eine Python-Artefakt-Korrektur, keine Interpretation der Telefonnummer selbst.
2. **Vorschau**: jede Zeile wird sofort klassifiziert (`classify_row()`) und als `ImportedAddress`
   mit `status="previewing"` gespeichert (noch OHNE `ImportRun` -- der entsteht erst beim
   Bestätigen). Klassifikation: `"customer"` (Kundennummer gesetzt), `"supplier"`
   (Lieferantennummer gesetzt), `"unassigned"` (keine von beiden), `"duplicate"` (Adressnummer
   bereits als Kunde/Lieferant/bestätigte `ImportedAddress`-Zeile bekannt -- wird bei Bestätigung
   übersprungen). `validation_notes` sammelt die geforderten Auffälligkeiten: fehlender Name,
   fehlende Adresse, Adressnummer mehrfach in derselben Datei, bereits vergebene Kunden-/
   Lieferantennummer. Ein neuer Upload verwirft automatisch eine zuvor nie bestätigte Vorschau
   (`discard_pending_preview()`), damit deren Adressnummern nicht fälschlich als "bereits
   importiert" gelten.
3. **Bestätigen** (`POST /api/address-import/confirm`): legt für `"customer"`/`"supplier"`
   tatsächlich `Customer`/`Supplier` an (inkl. `CustomerProfile`/automatischer
   "Hauptadresse"-`Property`, exakt das bestehende Muster aus `create_customer()`), lässt
   `"unassigned"` als offene Zeile stehen (das ist die Arbeitsliste) und `"duplicate"` unverändert
   (reiner Nachweis, dass die Adressnummer erneut vorkam). Schlägt eine einzelne Zeile fehl (z. B.
   doch noch ein Konflikt bei der Kundennummer), wird die GESAMTE Bestätigung zurückgerollt
   (`db.rollback()`) -- nichts bleibt halb geschrieben.

`ImportedAddress` ist bewusst EINE Tabelle für zwei Zwecke (Vorschau-Zwischenspeicher UND
dauerhafte Arbeitsliste) -- eine Zeile wird nach dem Bestätigen nie gelöscht (außer beim
Rückgängigmachen des ganzen Laufs), sonst würde ein erneuter Import derselben Datei dieselbe
Adressnummer fälschlich als neu erkennen.

### Arbeitsliste (`GET /api/address-import/unassigned`)

Zeigt alle `ImportedAddress`-Zeilen mit `classification="unassigned"` und `resolution IS NULL`.
Freitextsuche über Name/Straße/Ort/PLZ/E-Mail/Telefon/Adressnummer (client-seitig unnötig, da die
Liste ohnehin klein bleibt -- serverseitige Filterung in `list_unassigned()`). Drei Aktionen,
jede setzt `resolution`/`resolved_at` und blendet die Zeile damit aus der Liste aus:
- **Als Objekt zuordnen** (`resolve_as_property()`): legt ein `Property` beim gewählten
  Bestandskunden an, übernimmt Straße/PLZ/Ort/Land aus der Zeile.
- **Als neuen Kunden anlegen** (`resolve_as_new_customer()`): ruft denselben
  `_create_customer_from_row()`-Helfer wie die reguläre Bestätigung auf.
- **Verwerfen** (`discard_unassigned()`): setzt nur `resolution="discarded"`, erzeugt nichts.

Ist die Liste leer, zeigt die Seite einen Hinweistext statt der Tabelle (kein separates Ausblenden
des ganzen Abschnitts -- Wartungen/Mängel-Muster mit komplett verschwindendem Abschnitt wäre hier
nicht nötig gewesen, da der Abschnitt ohnehin nur auf der eigens dafür gebauten Importseite steht).

### Wo der Import liegt (Punkt 1)

`/address-import`, verlinkt aus Einstellungen → neue Gruppe **"Importe"** (unterhalb der
bestehenden "System"-Gruppe) -- nicht in den Stammdaten, da ein Import in der Regel einmalig
läuft. Geprüft, ob es dort schon etwas Vergleichbares gibt: der XML-Import für Leistungen
(`app/routers/imports.py`, `/leistungskatalog`) wäre ein Kandidat, künftig ebenfalls in diese
Gruppe zu wandern -- **bewusst nicht in dieser Etappe**, nur als Vermerk für später. Die gesamte
Adressimport-Oberfläche ist admin-gated (eigene, echte Kunden-/Lieferantenanlage, keine
Tagesbetrieb-Aktion).

### Tests

`tests/test_v247_address_import.py` -- Einlesen (CSV inkl. defekter Telefonnummern unverändert,
Excel inkl. Float-Formatierung, fehlende Pflichtspalte), Klassifikation (alle vier Fälle plus die
vier Auffälligkeits-Meldungen), der komplette Vorschau-Verwerfen/Bestätigen-Ablauf, Wiedererkennung
bei erneutem Import (inkl. des Sonderfalls "eine nie bestätigte Vorschau blockiert nichts"), die
Arbeitsliste mit allen drei Aktionen plus Suche, sowie Rückgängigmachen (Erfolgsfall, zwei
Ablehnungsfälle, und dass ein rückgängig gemachter Lauf seine Adressnummern wieder freigibt) --
sowohl direkt gegen `app/address_import.py` als auch einmal über echte Routen
(`router_test_client`). Mehrere ältere Tests wurden auf `last_name=` umgestellt, siehe oben.

## Objekte: Hauptadressen kennzeichnen und ausblenden (seit 1.3.32)

Nach dem Adressimport (1.3.31) bestand die Stammdaten-Objektliste überwiegend aus reinen
Hauptadress-Kopien -- jeder Kunde bekommt beim Anlegen automatisch ein Objekt namens
"Hauptadresse" (seine eigene Adresse, damit sofort auf sie gebucht werden kann, siehe
`create_customer()` oben). Die eigentlich interessanten, zusätzlichen Objekte (Baustellen,
Zweitgebäude) gingen darin unter.

### Punkt 1: `Property.is_primary_address` statt Namensvergleich

Neue Spalte `is_primary_address` (Boolean, NOT NULL, `server_default="0"`, indiziert) --
ersetzt den bisher überall verstreuten, fragilen String-Vergleich `p.name === 'Hauptadresse'`
durch ein echtes, robustes Flag. Gesetzt wird es **ausschließlich** an den drei Stellen, an
denen eine Hauptadresse automatisch entsteht -- nie über das normale Objektformular:

- `create_customer()` (`app/routers/customers.py`): das automatisch angelegte erste Objekt.
- `update_customer()` (`app/routers/customers.py`): die Suche nach der vorhandenen Hauptadresse
  lief bisher über den Namen (`p.name == "Hauptadresse"`) -- jetzt zuerst über das Flag, mit
  einem Namens-Fallback UND Selbstheilung (`main_property.is_primary_address = True` wird immer
  gesetzt, unabhängig davon, über welchen der drei Wege -- Flag, Name, Neuanlage -- die Zeile
  gefunden/erzeugt wurde). Verteidigung in der Tiefe: ohne diesen Fallback würde eine Zeile, die
  aus irgendeinem Grund den Namen trägt, aber nicht geflaggt ist, bei der nächsten
  Kundenbearbeitung eine zweite, doppelte "Hauptadresse"-Zeile erzeugen, statt gefunden zu
  werden -- in der echten Datenbank aktuell kein realer Fall (siehe Migrationsergebnis unten),
  aber ein günstiger, dauerhafter Schutz.
- `_create_customer_from_row()` (`app/address_import.py`): dieselbe automatische Anlage beim
  Adressimport.

**Migration `2fffb80e5567`, Erkennungssicherheit vor dem Schreiben geprüft und berichtet (wie
verlangt)**: von 163 Objekten in der echten Datenbank trugen 161 den Namen "Hauptadresse". Bei
**allen 161** stimmt zusätzlich Straße/PLZ/Ort exakt mit dem jeweiligen Kunden überein -- 0
unsichere Fälle, 0 Abweichungen zwischen Namens- und Adresskriterium. Die Migration markiert
deshalb bewusst konservativ nur, wenn **beide** Kriterien gemeinsam zutreffen
(`_resolve_primary_address_property_ids()`, direkt nach dem etablierten Migrations-Testmuster
eigenständig testbar, siehe `tests/test_v248_primary_address_flag.py`) -- ein Namenstreffer ohne
Adressübereinstimmung wird NICHT markiert. Begründung (Nutzervorgabe): lieber eine echte
Hauptadresse übersehen als eine echte Liegenschaft fälschlich aus der Objektliste verschwinden
zu lassen, was niemandem auffallen würde. Die beiden übrigen Objekte sind keine unsicheren
Namenstreffer, sondern schlicht keine Hauptadressen (kein "Hauptadresse"-Name) -- die Migration
lässt sie unverändert.

### Punkt 2: wo Hauptadressen ausgeblendet werden -- Fundstellen-Übersicht

Alle Orte im Projekt geprüft, an denen Objekte gelistet oder ausgewählt werden, mit
unterschiedlicher, begründeter Behandlung je Fundstelle:

| Ort | Behandlung | Begründung |
|---|---|---|
| `master_data.html` (Stammdaten-Objektliste) | ausgeblendet, Kontrollkästchen "Hauptadressen anzeigen" zum Wiedereinblenden | Standardfall dieser Anfrage -- die Liste soll auf die eigentlich interessanten Objekte fokussieren, ohne echte Daten unerreichbar zu machen |
| `findings.html` (Objekt-Filterdropdown) | ausgeblendet, eigenes Kontrollkästchen "Hauptadressen in Objektliste anzeigen" | vom Nutzer ausdrücklich "genauso" wie die Stammdaten-Liste gefordert |
| `maintenance_contracts.html`/`maintenance_contract.html` (`propertyOptionsHtml()`, Objektauswahl beim Wartungsvertrag) | Hauptadressen aus der Auswahlliste gefiltert, kein zusätzliches Kontrollkästchen | die bereits bestehende Option "— Hauptadresse verwenden —" deckt genau diesen Fall bereits redundant ab -- `contract_to_dict()` liefert für `property_id=None` byte-identisch dasselbe Ergebnis wie eine explizit gewählte Hauptadresse-Zeile, ein zweiter, gleichwertiger Eintrag in der Liste wäre nur verwirrend |
| `project_folder.html`/`project_form.html` (Objektauswahl beim Projekt/Vorgang), `inquiries.html` (Objektauswahl bei Anfragen) | **unverändert, Hauptadresse bleibt wählbar** | geprüft anhand `_copy_quote_scope_to_order()` (`app/orders.py`): `NULL` und eine explizit gewählte Hauptadresse-Zeile erzeugen dort tatsächlich unterschiedliche Ergebnisse im eingefrorenen Auftrags-Schnappschuss (siehe Punkt 3), die Auswahl darf deshalb nicht verschwinden |
| `customer.html` (Objektliste auf der Kundenseite) | **alle Objekte bleiben sichtbar**, Hauptadresse nur noch über das Flag statt den Namen markiert (Badge, `main`-CSS-Klasse, ausgeblendeter "Bearbeiten"-Button) | ausdrückliche Vorgabe (Punkt 3) -- der "Objekt hinzufügen"-Button bleibt unverändert |
| `property.html` (Einzelobjekt-Detailseite) | keine Änderung nötig | reine Detailansicht eines bereits bekannten Objekts, kein Listen-/Auswahlkontext |

In der Stammdaten-Objektliste durchsucht die Suche weiterhin **alle** Objekte (auch versteckte),
bevor der Sichtbarkeitsfilter greift -- ein Anruf, bei dem nur eine Adresse bekannt ist, muss
weiterhin etwas finden können, unabhängig vom Hauptadresse-Status.

### Punkt 3: Nebenbefund behoben, nicht nur gemeldet

Ein Wartungsvertrag ohne Objekt zeigt "Hauptadresse" (`contract_to_dict()`,
`app/maintenance_contracts.py`, synthetisiert das seit 1.2.9) -- ein daraus per Schnellauftrag
erzeugter Auftrag zeigte dagegen **gar kein** Objekt. Dieselbe Sache, zweimal unterschiedlich
dargestellt. `_copy_quote_scope_to_order()` (`app/orders.py`, die einzige Stelle, die den
eingefrorenen Auftrags-Schnappschuss `property_name`/`property_address` befüllt, für ALLE
Beauftragungswege inkl. Schnellauftrag) schreibt jetzt im `property is None`-Fall denselben
Wert, den `contract_to_dict()` für die Anzeige liefert ("Hauptadresse" +
`_address(customer.street, city_line)`), statt zuvor `None`. **Bestehende Aufträge bleiben
unangetastet** -- der Snapshot ist eingefroren, nur künftige Beauftragungen sind betroffen.
Regressionstest: `tests/test_v209_quick_service_orders.py`.

### Tests

`tests/test_v248_primary_address_flag.py` -- alle drei Setzstellen des Flags (`create_customer()`,
`update_customer()` inkl. Selbstheilung einer unflagged, aber namensgleichen Zeile), die Migration
isoliert (Name-und-Adresse-Kriterium vs. nur-Name). `tests/test_v247_address_import.py` um eine
Flag-Prüfung ergänzt. `tests/test_v209_quick_service_orders.py` um den Nebenbefund-Regressionstest
ergänzt (mit und ohne hinterlegte Kundenadresse).

## Geheimnisse für den Serverbetrieb (`app/paths.py`, seit 1.3.33)

Vorbereitung für den geplanten Umzug auf einen echten Server (das Projekt liegt seit derselben
Sitzung erstmals in einem privaten GitHub-Repository, siehe unten). Ziel: kein Geheimnis liegt
als Datei im Projektordner, der aus Git kommt; `ERP_SECRET_KEY` kommt aus der Umgebung;
`ERP_DATA_DIR` zeigt auf einen Ordner außerhalb des Checkouts, damit ein `git pull` nie Fotos,
Unterschriften oder den Verschlüsselungsschlüssel berührt; die Datenbankverbindung kommt aus
`DATABASE_URL`. Lokal soll ohne gesetzte Variablen weiterhin alles mit den bisherigen
Vorgabewerten funktionieren.

**Bestandsaufnahme vor dem Bauen ergab: das meiste war schon da.** `secret_key()`
(`app/auth.py`) liest `ERP_SECRET_KEY` bereits vorrangig -- ist die Variable gesetzt, wird
`data/.erp_secret` gar nicht erst gelesen oder angelegt. Die Datei wird nur als Rückfall beim
allerersten Start automatisch erzeugt (`secrets.token_hex(32)`). `DATABASE_URL`
(`app/database.py`) funktionierte bereits vollständig über die Umgebungsvariable. **Fehlend war
nur eine Vereinheitlichung**: die sieben unabhängigen Upload-Pfade (Firmenlogo,
Briefpapier-Hintergründe, Kunden-/Projektdateien, Dachflächen-Skizzen,
Einsatzbericht-Fotos/-Unterschriften) kannten `ERP_DATA_DIR` bisher nicht -- jeder hätte auf
einem Server einzeln über seine eigene, spezifischere Variable (`DACHKONZEPTE_LOGO_FILE_ROOT`
usw.) umgelenkt werden müssen.

### `app/paths.py::data_dir()` -- eine Stelle statt neun

Neues, kleines Modul mit einer einzigen Funktion, von `app/auth.py`
(Verschlüsselungsschlüssel), `app/logging_config.py` (Protokoll) und allen sieben
Upload-Modulen (`app/company_logo.py`, `app/customer_documents.py`,
`app/document_layout_background.py`, `app/project_documents.py`, `app/roof_area_sketches.py`,
`app/service_reports.py`, `app/service_report_photos.py`) genutzt:

```python
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

def data_dir() -> Path:
    root = Path(os.getenv("ERP_DATA_DIR", str(_PROJECT_ROOT / "data")))
    root.mkdir(parents=True, exist_ok=True)
    return root
```

Jedes der sieben Upload-Module behält seine eigene, spezifischere Variable als Override erster
Priorität (`Path(os.getenv("DACHKONZEPTE_LOGO_FILE_ROOT", data_dir() / "company_logo"))`) --
`ERP_DATA_DIR` bestimmt nur den gemeinsamen Fallback, falls keine der spezifischeren Variablen
gesetzt ist. Lokal ändert sich dadurch nichts: ohne jede Variable ergibt `data_dir()` exakt
denselben Pfad wie vorher (`<Projektordner>/data`).

**Dabei eine echte, kleine Inkonsistenz behoben.** Die beiden schon vorher bestehenden
`ERP_DATA_DIR`-Leser (`_secret_path()` in `app/auth.py`, `configure_logging()` in
`app/logging_config.py`) lösten ihren Fallback relativ zum AKTUELLEN ARBEITSVERZEICHNIS auf
(`Path("data")`), die sieben Upload-Pfade dagegen relativ zur LAGE DER DATEI SELBST
(`Path(__file__).resolve().parent.parent`). Heute folgenlos, weil jeder bekannte Startweg
(`start_windows.bat` wechselt vorher per `cd /d %~dp0` dorthin, `pytest` liest `pytest.ini` aus
dem Projektordner) das Arbeitsverzeichnis ohnehin auf den Projektordner setzt -- aber eine
tickende Falle für einen künftigen Server-Start mit einem anderen Arbeitsverzeichnis
(systemd-Unit, Docker-`WORKDIR`): der Ordner würde dann STILLSCHWEIGEND woanders landen (er
wird ja automatisch neu angelegt), der Schaden zeigt sich erst später als "die Uploads von
vorher sind weg". `data_dir()` verankert den Fallback jetzt einheitlich dateibasiert -- der
Docstring hält diese Begründung ausdrücklich fest, damit ein künftiger Durchgang sie nicht als
Übervorsicht wieder auf einen arbeitsverzeichnis-relativen Fallback "vereinfacht".

### Warnung statt Blockade bei abweichendem Schlüssel

`data/.erp_secret` entschlüsselt die bereits in der Datenbank gespeicherten SMTP-/
Microsoft-365-Zugangsdaten (`password_encrypted`/`graph_client_secret_encrypted`, siehe
`app/crypto.py`/`app/email_sending.py`). Setzt jemand auf dem Server versehentlich einen
anderen `ERP_SECRET_KEY` als den, mit dem eine übernommene Datenbank verschlüsselt wurde, werden
diese Werte unlesbar -- bisher unbemerkt bis zum nächsten Versandversuch
(`decrypt_secret()` wirft dann erst `ValueError`). Neue Funktion
`warn_if_secret_key_mismatches_file()` (`app/auth.py`, beim Start aus `app/main.py` aufgerufen,
direkt nach `configure_logging()`): loggt eine deutliche Warnung, wenn `ERP_SECRET_KEY` gesetzt
UND `data/.erp_secret` vorhanden UND beide unterschiedlich sind -- **kein Abbruch** (ein
abweichender Schlüssel ist bei einer frischen Testinstallation normal) und **gibt den Schlüssel
selbst nie aus, auch nicht gekürzt**. Ist `ERP_SECRET_KEY` gesetzt, aber es existiert keine
`data/.erp_secret` (frische Installation) oder ist die Variable gar nicht gesetzt, bleibt es
stumm.

**Wie der bestehende Schlüssel sauber auf den Server kommt**: der Inhalt der lokalen
`data/.erp_secret` (`Get-Content data\.erp_secret`) muss unverändert als Wert von
`ERP_SECRET_KEY` in der Serverumgebung landen -- über den Secret-Mechanismus der jeweiligen
Plattform, nie als Datei im Repository (bleibt gitignored) und nie unverschlüsselt durch einen
Chat/eine E-Mail geleitet.

### `.env.example`

Um `ERP_DATA_DIR` (jetzt mit vollständiger Erklärung, was alles darüber verlegt wird) und alle
sieben `DACHKONZEPTE_*_FILE_ROOT`-Variablen ergänzt -- auskommentiert, mit dem Hinweis, dass sie
nur gebraucht werden, wenn ein einzelner Ordner abweichend von `ERP_DATA_DIR` woanders liegen
soll. So sind sie beim Einrichten eines Servers sichtbar, ohne gesetzt werden zu müssen.

### Tests

`tests/test_v111_config_hardening.py`: `data_dir()` liefert denselben Pfad unabhängig vom
Arbeitsverzeichnis (der zentrale Fund dieser Etappe) und respektiert `ERP_DATA_DIR`;
`warn_if_secret_key_mismatches_file()` warnt bei Abweichung, bleibt stumm bei Übereinstimmung/
fehlender Datei/fehlender Variable, und gibt in keinem Fall den Schlüsselwert selbst aus (per
`caplog` geprüft). Zusätzlich manuell gegen die echte `data/.erp_secret` verifiziert (mit einem
bewusst falschen Test-Dummywert, nie dem echten Schlüssel).

## Anmeldesicherheit für den Onlinebetrieb (seit 1.3.34)

Der Server wird demnächst frei aus dem Internet erreichbar sein -- die Anmeldeseite wird ab Tag
eins automatisiert durchprobiert. Bestandsaufnahme vor dem Bauen ergab: Passwort-Hashing
(PBKDF2-HMAC-SHA256, 260.000 Iterationen) war bereits solide, das Anmelde-Cookie bereits
`httponly`+`samesite=lax`+`secure` (über `ERP_COOKIE_SECURE`, bereits der richtige
Mechanismus, keine Änderung nötig) -- die drei tatsächlichen Lücken: eine nur im Arbeitsspeicher
lebende, rein benutzernamen-basierte Anmeldesperre, kein zweiter Faktor, und keine
Selbstbedienung fürs eigene Passwort.

### Persistente, doppelte Anmeldesperre (`app/login_security.py`)

Der bisherige In-Memory-Zähler (`app/auth.py`, bis 1.3.33) zählte pro Prozess -- bei zwei
uvicorn-Workern wären aus fünf zulässigen Fehlversuchen zehn geworden, ein Neustart hätte den
Zähler ohnehin geleert. Neue Tabelle `FailedLoginAttempt` (`bucket`, `occurred_at`) -- bewusst
EINE Zeile je Fehlversuch statt eines Zählers je Schlüssel, damit das gleitende Zeitfenster ("die
letzten N Versuche innerhalb von X Sekunden") exakt wie vorher nachbildbar bleibt. Zwei
unabhängige Sperren GEMEINSAM geprüft (`login_lockout_seconds()`): je Benutzername
(`MAX_ATTEMPTS_PER_USER=5`, 15 Minuten) UND je IP-Adresse (`MAX_ATTEMPTS_PER_IP=20`, 15 Minuten,
höhere Schwelle, damit ein Büro mit mehreren Mitarbeitern hinter derselben Adresse sich nicht
durch normale Tippfehler gegenseitig aussperrt) -- eine reine Benutzernamen-Sperre ließe sich
durch rotierende Benutzernamen umgehen, eine reine IP-Sperre träfe bei wechselnden Adressen nie.
Dasselbe Muster (eigener Bucket-Präfix `twofa_user:`) sichert auch das Erraten von TOTP-/
Wiederherstellungscodes beim Login ab (`two_factor_lockout_seconds()`).

**Aufräumen ohne separaten Job**: `register_failed_attempt()` löscht bei JEDEM neuen Fehlversuch
gleich alle Zeilen, die älter als das größte verwendete Zeitfenster sind (`_RETENTION_SECONDS`)
-- kein Scheduler nötig (passt zum durchgängigen "kein echter Scheduler"-Prinzip dieses
Projekts), die Tabelle bleibt dadurch ungefähr auf die Fehlversuche der letzten Zeitfenster
begrenzt, egal wie viele insgesamt je passiert sind. Erfolg löscht nur die eigene
Benutzernamen-Sperre (`clear_failed_login()`), bewusst NICHT die IP-Sperre -- gelingt zufällig
ein Login von einer Adresse, mit der zuvor viele andere Benutzernamen durchprobiert wurden, soll
das die IP-Sperre nicht aufheben. Die Fehlermeldung ("Benutzername oder Passwort ist falsch")
war bereits vorher für unbekannten Benutzernamen und falsches Passwort identisch -- unverändert,
verrät also weiterhin nicht, ob ein Konto existiert (per Test abgesichert).

**Bewusst NICHT in dieser Version**: Auswertung von `X-Forwarded-For` hinter einem
Reverse-Proxy -- `request.client.host` ist der unmittelbare TCP-Peer. Läuft der Server später
hinter einem Reverse-Proxy, sähen alle Anfragen dieselbe (Proxy-)Adresse, die IP-Sperre würde
dann faktisch alle Nutzer gemeinsam treffen. Bekannter, bewusst offener Punkt für den Moment, in
dem ein Reverse-Proxy tatsächlich eingerichtet wird -- dann braucht es eine per Umgebungsvariable
gesteuerte "vertraue dem Proxy-Header"-Option, nicht blind vertrauen (sonst ließe sich die
Absender-IP durch den Header selbst fälschen).

### Zwei-Faktor-Authentifizierung (TOTP) für Administratoren (`app/two_factor.py`)

Nur für Administratoren -- Monteure melden sich täglich auf dem Fahrzeug-Tablet an, ein zweiter
Faktor bei jeder Anmeldung wäre dort täglicher Aufwand, und ihre Konten haben deutlich weniger
Rechte. Administratoren dagegen kommen an alle Kunden-, Mitarbeiter- und Finanzdaten.
**Verpflichtend**, nicht freiwillig -- freiwilliger zweiter Faktor wird in der Praxis fast nie
aktiviert, genau in dem Moment nicht, in dem es zählt. Bewusst KEINE "Später erinnern"-Option.

**Abhängigkeiten, tatsächlich geprüft** (Metadaten/LICENSE-Dateien der herunterladbaren Pakete
gelesen, nicht aus dem Gedächtnis, Muster wie bei `pypdfium2`): `pyotp` 2.10.0 (**MIT**, keine
eigenen Abhängigkeiten) und `qrcode[pil]` 8.2 (**BSD-3-Clause** -- ein zusätzlicher, irreführender
"Other/Proprietary"-Classifier bezieht sich nur auf eine Namensnennung für portierten JS-Code,
keine zusätzlichen Einschränkungen; zieht `pillow` als Extra, bereits Pflichtabhängigkeit über
ReportLab/Einsatzbericht-Fotos, kein neues Gewicht; unter Windows zusätzlich `colorama`, BSD, war
bereits transitiv installiert). Reine Pip-Pakete ohne Systemabhängigkeit.

**Architektur -- ein zweites, unabhängiges Cookie statt eines erweiterten Anmelde-Cookies**:
`make_cookie()`/`parse_cookie()`/`user_from_request()` (bestehend, `app/auth.py`) bleiben
komplett unverändert. Neu: `dk_erp_otp_ok` (`OTP_COOKIE_NAME`), signiert mit demselben
`secret_key()`, aber einem eigenen HMAC-Namespace-Präfix (`"otp:"`), damit eine signierte
otp-Nutzlast nicht als normales Anmelde-Cookie durchgehen könnte. Belegt, dass FÜR DIESE
SITZUNG bereits ein zweiter Faktor bestätigt wurde -- geprüft gegen das Cookie, nicht gegen
einen Zustand auf dem Benutzerdatensatz selbst (sonst würde eine einzige bestätigte Sitzung
alle Geräte/Sitzungen desselben Administrators mit freischalten).

`app/main.py`s Middleware berechnet `otp_ok` nur für Administratoren (`otp_ok_for_user()`) und
blockiert, falls nicht vorhanden, JEDEN `/api/`-Aufruf außer den in `_TWO_FACTOR_SETUP_PATHS`
gelisteten (`/api/account/2fa/setup/start|confirm`, `/api/account/2fa/verify` -- `/api/auth/*`
ist über die bereits bestehende `_request_requires_login()`-Ausnahme ohnehin immer erreichbar)
mit `401 {"two_factor_pending": true}`. Seiten-Gerüste (`GET` auf nicht-`/api/`-Pfade) bleiben
immer erreichbar -- `_sidebar.html`s bereits auf jeder Seite laufender Status-Abruf leitet bei
`two_factor_required && !otp_ok` selbst auf `/account` weiter, kein globaler
Fetch-Interceptor nötig.

`POST /api/auth/login` prüft weiterhin AUSSCHLIESSLICH Benutzername/Passwort und setzt das
normale Anmelde-Cookie IMMER -- unabhängig davon, ob der zweite Faktor noch fehlt. Jede frische
Passwort-Anmeldung löscht das `dk_erp_otp_ok`-Cookie explizit (nicht nur, wenn keiner konfiguriert
ist) -- "bei jeder weiteren Anmeldung wird nach dem Passwort zusätzlich der Code abgefragt" gilt
damit ausnahmslos, auch wenn eine vorherige Sitzung noch nicht abgelaufen wäre.

**Ablauf, wie vorgegeben**: Ersteinrichtung (`app/templates/account.html`, "Mein Konto") zeigt
einen QR-Code (`POST /api/account/2fa/setup/start` -- erzeugt ein neues, noch UNBESTÄTIGTES
Geheimnis, verschlüsselt abgelegt wie das SMTP-Passwort über `app/crypto.py::encrypt_secret()`,
da der Klartext zur Code-Prüfung wiederherstellbar sein muss), der Administrator bestätigt mit
einem ersten, echten Code (`POST /api/account/2fa/setup/confirm`) -- **erst danach** wird
`AppUser.totp_confirmed_at` gesetzt und sind zehn Wiederherstellungscodes einmalig in der
Antwort enthalten (gehasht gespeichert wie Benutzerpasswörter, `hash_password()`/
`verify_password()`, da sie nie zurückgelesen werden müssen -- nur einmal beim Verbrauch
verglichen; jeder Code funktioniert genau einmal, `used_at` markiert den Verbrauch statt den
Code zu löschen). Bei jeder weiteren Anmeldung: `POST /api/account/2fa/verify` prüft einen
aktuellen TOTP-Code (`pyotp.TOTP(secret).verify(code, valid_window=1)`, ±1 Zeitschritt
Toleranz) ODER einen noch nicht verbrauchten Wiederherstellungscode.

**Frage 1 (aus der Planung): abgebrochene Einrichtung, kein Selbstaussperrungsrisiko --
bestätigt und mit Test abgesichert.** Nichts wird als aktiv markiert, bevor nicht ein echter
Code bestätigt wurde -- schließt ein Administrator das Einrichtungsfenster, ohne zu bestätigen,
bleibt `totp_confirmed_at` `NULL`. Beim nächsten Login beginnt der Ablauf einfach neu:
`setup/start` erzeugt ein NEUES Geheimnis, das das alte, nie bestätigte kommentarlos überschreibt
-- ein Code aus dem abgebrochenen ersten Versuch funktioniert danach nachweislich nicht mehr,
nur einer aus dem tatsächlich genutzten zweiten (`test_abandoned_setup_leaves_no_half_active_state_and_retry_works`,
`tests/test_v250_two_factor_auth.py`). Kein halb aktiver Zustand, keine Aussperrungsfalle.

**Frage 2 (aus der Planung): Notfall bei verlorenem Telefon UND verlorenen
Wiederherstellungscodes.** Zwei gestaffelte Wege:
1. Existiert noch ein ANDERER aktiver Administrator: dieser setzt den zweiten Faktor über die
   Benutzerverwaltung zurück (`POST /api/users/{id}/reset-two-factor`, `app/routers/users.py`,
   `require_admin()`-gated) -- ausschließlich für ANDERE Konten, niemals für das eigene (sonst
   ließe sich die Pflicht zum zweiten Faktor über die eigene Benutzerverwaltung wieder
   abschalten). `users.html` zeigt eine deutliche Warnung, wenn nur EIN aktiver Administrator
   existiert -- dann existiert dieser Weg praktisch nicht.
2. **`scripts/reset_admin_2fa.py`** -- Notfallskript, direkt auf dem Server auszuführen:

   ```
   python scripts/reset_admin_2fa.py <benutzername>
   ```

   Nutzt dieselbe `DATABASE_URL`/`ERP_DATA_DIR`-Konfiguration wie die Anwendung selbst (kein
   zweiter Konfigurationsweg), fragt vor dem Zurücksetzen zur Bestätigung nach erneuter Eingabe
   des Benutzernamens (`--yes` überspringt das für ein automatisiertes Runbook), protokolliert
   die Aktion über den normalen Logger nach `data/erp.log` (auditierbar, wer/wann zurückgesetzt
   hat). Danach: der Benutzer wird beim nächsten Login zur vollständigen Neueinrichtung
   aufgefordert, genau wie beim allerersten Mal. Dieselbe Anleitung steht auch im Kopfkommentar
   des Skripts selbst, damit sie im Ernstfall nicht erst gesucht werden muss.

### Selbstbedienungsseite "Mein Konto" (`GET /account`, `app/routers/account.py`)

Bisher konnte NIEMAND sein eigenes Passwort selbst ändern -- nur ein Administrator konnte das
Passwort eines ANDEREN Kontos setzen (`app/routers/users.py`). Im Onlinebetrieb ein eigenes
Problem: wer sein Passwort geändert haben wollte, musste es dem Administrator sagen, der es dann
kannte. `POST /api/account/change-password` (aktuelles + neues Passwort, jeder angemeldete
Benutzer) behebt das. Auf derselben Seite richten Administratoren zusätzlich den zweiten Faktor
ein (siehe oben) -- bewusst EINE Seite statt zwei, da beides "meine eigenen
Zugangsdaten verwalten" ist. Verlinkt aus `_sidebar.html`s Fußbereich neben "Abmelden".

**Bewusst NICHT gebaut**: ein bereits bestätigter zweiter Faktor lässt sich hier nicht durch
einen neuen ersetzen (z. B. neues Telefon, altes nicht verloren) -- dafür bleibt nur der Weg über
einen anderen Administrator oder das Notfallskript, beide setzen zuerst vollständig zurück.
Erkannte, aber nicht angefragte Lücke -- bei Bedarf nachrüstbar (ein "Neu einrichten"-Knopf, der
wie `setup/start` funktioniert, aber ein bereits bestätigtes Geheimnis überschreiben darf).

### Ein real gefundener Fehler, per Smoke-Test gegen eine echte Serverinstanz entdeckt

`request.state.erp_user` wird von `app/main.py`s Middleware über eine EIGENE, bereits wieder
geschlossene `SessionLocal()`-Instanz geladen -- nicht über die Session, die ein Endpunkt per
`Depends(get_db)` bekommt (das ist grundsätzlich eine ANDERE Session, siehe `require_admin()`/
`user_from_request()`). Die erste Fassung von `app/routers/account.py` mutierte dieses Objekt
direkt (`user.totp_secret_encrypted = ...`, `user.password_hash = ...`) und committete über die
Endpunkt-eigene Session -- die Änderung wurde dadurch STILLSCHWEIGEND NICHT persistiert, ohne
jede Fehlermeldung. Aufgefallen erst bei einem echten Ende-zu-Ende-Smoke-Test gegen eine
isolierte, aber echt laufende Serverinstanz (nicht die reine Testsuite: dort teilten sich
Middleware und Endpunkt in `router_test_client()`/den ersten `TestClient`-Testaufbauten
versehentlich dieselbe Session, was den Fehler verdeckte). Behoben in
`app/routers/account.py::_current_user()`: lädt den Benutzer jetzt IMMER über `db.get()` in der
jeweils richtigen Session neu, statt das über `request.state` hereingereichte Objekt direkt zu
verwenden -- exakt das Muster, das der Rest des Projekts (z. B. `routers/users.py`) an dieser
Stelle bereits einhält (`current` aus `require_admin()` wird dort nur für Vergleiche gelesen, nie
mutiert). Die Testaufbauten in `tests/test_v250_two_factor_auth.py` wurden danach bewusst auf
GETRENNTE Session-Objekte für Middleware und Endpunkte umgestellt (ein gemeinsamer Engine, aber
`sessionmaker()` liefert für jeden Aufruf eine neue Session), damit ein künftiger Rückfall in
dasselbe Muster wieder auffällt, statt von einem zu großzügigen Testaufbau verdeckt zu werden.

### Tests

`tests/test_v108_login_lockout_and_logging.py` (überarbeitet, nicht mehr In-Memory): Benutzername-
UND IP-Sperre einzeln und gemeinsam, automatisches Aufräumen alter Zeilen, identische
Fehlermeldung für unbekannten Benutzernamen/falsches Passwort. `tests/test_v250_two_factor_auth.py`:
`app/two_factor.py` isoliert (Setup/Bestätigung/Verifikation/Wiederherstellungscodes/Reset), die
abgebrochene-Einrichtung-Frage explizit, Admin-setzt-anderen-Admin-zurück-nie-sich-selbst, sowie
eine echte Ende-zu-Ende-Prüfung über einen eigens für den Test aufgebauten `TestClient` mit
echten Cookies (nicht `router_test_client()`, das die Identität komplett fälscht) -- Login ohne
zweiten Faktor wird zur Einrichtung geleitet, Business-Endpunkte bleiben bis dahin gesperrt,
nach Bestätigung frei; ein bereits eingerichteter Administrator muss bei jedem Login erneut den
Code eingeben; Nicht-Administratoren sind nie betroffen; wiederholt falsche Codes lösen die
2FA-eigene Sperre aus. `tests/test_v251_account_self_service.py`: Passwortänderung (inkl. für
normale Benutzer, nicht nur Administratoren), Seiteninhalt/Verdrahtung (Muster
`test_v163_sidebar_login_status.py`), und `scripts/reset_admin_2fa.py`s `main()` direkt gegen
eine isolierte Testdatenbank (niemals die echte `DATABASE_URL`) -- Bestätigung korrekt/falsch/
`--yes`/unbekannter Benutzername.

## PostgreSQL-Umstieg: Migrationskette repariert (seit 1.3.35)

Erste Reparaturrunde vor dem eigentlichen Datenumzug -- Nutzervorgabe: "Wir reparieren zuerst,
bevor irgendetwas umzieht." Datenumzug (eigenes Python-Skript statt pgloader, wie abgestimmt),
Backup-Skript-Umbau und die Abschaltung von `create_all()` im Produktionsbetrieb sind bewusst
NICHT Teil dieser Runde -- alle drei sind erkannt und berichtet, aber eigene, spätere Schritte.

### Der `e057d15af828`-Fund: der Migrations-Workflow-Fallstrick, tatsächlich eingetreten

Die Migration `e057d15af828` ("Rechnungswesen") bestand vollständig aus `pass`/`pass` -- ein
echter No-op, keine invertierte oder unvollständige Logik. Betroffen waren ausgerechnet
`invoices`/`invoice_items`, zwei der zentralsten Tabellen des ganzen Projekts.

**Wie das entstanden ist** -- exakt der Mechanismus, der im Abschnitt "Migrations-Workflow"
unten bereits als allgemeine Warnung beschrieben ist ("Fallstrick, seit 1.2.23 bekannt:
`app/main.py` ruft beim Import `Base.metadata.create_all(bind=engine)` auf"), hier aber der
tatsächliche Beweis, dass er real zugeschlagen hat, nicht nur eine theoretische Gefahr: als das
Rechnungswesen-Feature gebaut wurde, hat irgendein Vorgang (ein Testlauf, ein Serverstart, ein
simpler `import app.main`) `app.main` geladen, BEVOR `alembic revision --autogenerate` für die
neuen `Invoice`/`InvoiceItem`-Modelle lief. `create_all()` legte beide Tabellen dabei bereits
real in der SQLite-Datei an. Als Autogenerate danach lief, verglich es den ORM-Modellstand gegen
die (durch `create_all()` bereits identische) reale Datenbank -- fand keinen Unterschied -- und
erzeugte eine leere Hülle statt der beiden `CREATE TABLE`-Anweisungen.

**Warum das unter SQLite jahrelang unsichtbar blieb**: `create_all()` läuft bei JEDEM Start von
`app/main.py` erneut (dasselbe Sicherheitsnetz, das den Fehler verursacht hat, verdeckte ihn
danach zuverlässig weiter) -- eine lokale, immer schon laufende SQLite-Installation hatte die
Tabellen dadurch bei jedem Start automatisch nachgezogen, unabhängig vom Zustand der
Migrationskette. Erst eine komplett FRISCHE Datenbank, aufgebaut ausschließlich über
`alembic upgrade head` OHNE je einen `create_all()`-Lauf dazwischen, würde diesen Widerspruch
zeigen -- exakt der Fall bei einer neuen PostgreSQL-Installation für den geplanten Serverumzug,
wo bei einer leeren Zieldatenbank kein `create_all()` mehr rettend eingreift. Gefunden per
Skript, das alle `Base.metadata.tables` gegen jeden `create_table(...)`-Aufruf in
`alembic/versions/*.py` abgeglichen hat -- `invoices`/`invoice_items` waren die einzigen beiden
Tabellen im ganzen Projekt ohne eine erzeugende Migration.

**Reparatur, in-place statt angehängt**: da die reale, produktive `dachkonzepte_erp.db` längst
weit über diesem Punkt steht (Head `1b55170709a6`) und Alembic Revisionen ausschließlich über
die `alembic_version`-Tabelle trackt (nie inhaltlich erneut ausführt), ist ein nachträgliches
Befüllen der bereits angewendeten Migration sicher -- verifiziert durch `alembic current`/
`alembic upgrade head` gegen die reale Datei, die dabei unverändert bei ihrem Head-Stand
blieb (kein "Running upgrade"). Die Migration musste dabei den historischen Spaltenstand ZUM
DAMALIGEN ZEITPUNKT DER KETTE abbilden, nicht das heutige Vollschema -- sonst hätten die vier
später folgenden `batch_alter_table('invoices'/'invoice_items', ...)`-Migrationen (`bb175f455b64`,
`3eb9f52b38ab`, `8c0bddc8321c`, `369f94b5d5d3`) versucht, bereits vorhandene Spalten erneut
hinzuzufügen. Rekonstruiert durch Rückrechnen: alle vier Folgemigrationen gelesen, ihre
`add_column`-Aufrufe von `invoices`s heutigem 31-Spalten-Vollschema abgezogen (Ergebnis: 23
historische Spalten -- ohne `tax_key_id`, `tax_notice_text`, `outro_text_2`, `email_sent_at`,
`email_sent_to`, `payment_terms_text_template`, `skonto_percent`, `skonto_days`), gegen
`app/models.py`s eigene "seit 1.0.4x"-datierte Docstring-Kommentare der `Invoice`-Klasse
kreuzgeprüft (deckungsgleich). `invoice_items` bekam dagegen das volle heutige Schema, da KEINE
spätere Migration diese Tabelle je verändert (zweiter Grep bestätigt).

### Die übrigen vier Reparaturpunkte derselben Runde

- **`datetime('now')`** (SQLite-spezifische SQL-Funktion, unter PostgreSQL unbekannt) in
  `257fb2967c93`/`ab5eef23f9ed` durch `sa.text(...).bindparams(now=datetime.utcnow())` ersetzt --
  SQLAlchemy übersetzt den gebundenen Python-`datetime`-Wert dialektkorrekt.
- **Boolean-Literale in rohem SQL** (`1`/`0`, unter PostgreSQL strikt typisiert statt implizit
  nach `boolean` konvertiert wie bei SQLite) in sieben Migrationen (`4609e3fc8976`,
  `06299a5101f5`, `2fffb80e5567`, `0064c87051aa`, `5c8715dba230`) auf gebundene Python-`True`/
  `False`-Parameter bzw. `TRUE`/`FALSE`-SQL-Schlüsselwörter umgestellt (letzteres nur, wo keine
  Bind-Infrastruktur in der jeweiligen Anweisung existierte). **App-seitige
  `Column == True/False`-ORM-Vergleiche blieben ausdrücklich unangetastet** -- die übersetzt
  SQLAlchemy bereits pro Dialekt korrekt, betroffen war ausschließlich rohes `sa.text()`-SQL.
- **`app/audit.py:263`**: `AuditLog.actor_name.contains(actor)` (case-insensitive unter SQLite,
  case-sensitive unter PostgreSQL -- hätte eine Audit-Log-Suche nach Beauftragtem auf Postgres
  unauffindbar strenger gemacht) auf `.ilike(f"%{actor}%")` umgestellt. Projektweite Prüfung auf
  weitere `.contains()`/`.startswith()`-Fälle mit derselben Gefahr: kein zweiter Fund.

### Verifikation -- fester Bezugspunkt für künftige Nachfragen

**Stand: Version 1.3.35, verifiziert am 13.09.2026.** Falls in einem halben Jahr jemand fragt,
ob die Migrationskette tatsächlich vollständig gegen PostgreSQL läuft: ja, ab genau dieser
Version, mit vier konkreten Nachweisen, keiner davon nur behauptet:

1. Eine lokale, portable PostgreSQL-17-Instanz (EnterpriseDB-ZIP-Binaries, kein Admin-Zugriff
   nötig -- `%LOCALAPPDATA%\pgportable`, Port 5433, Datenbank `spielwiese`) wurde geleert und
   `alembic upgrade head` OHNE `DATABASE_URL`-Override auf SQLite ausgeführt -- alle 55
   Migrationen liefen vollständig und fehlerfrei durch, `alembic_version` landete korrekt bei
   `1b55170709a6`, `information_schema.tables` zeigte die erwarteten 122 Tabellen (121
   ORM-Modelle + `alembic_version`).
2. Dieselbe, frisch geleerte SQLite-Datei (kein Bestand, kein `create_all()`-Vorlauf) durchlief
   `alembic upgrade head` ebenfalls vollständig -- keine Regression durch die vier
   dialektneutralen Fixes.
3. Die reale, bereits vollständig migrierte Produktionsdatenbank `dachkonzepte_erp.db` blieb bei
   erneutem `alembic upgrade head` unverändert bei ihrem Head-Stand (kein "Running upgrade") --
   das in-place-Editieren bereits angewendeter Migrationen hat keine Nebenwirkung auf eine
   Installation, die längst darüber hinaus ist.
4. Volle Testsuite `pytest`: 1040/1040 grün.

Sollte diese Prüfung ein weiteres Mal nötig werden (z. B. nach einer künftigen Migration, die
denselben Risikotyp trägt -- ein neues Modell, das versehentlich vor `--autogenerate` per
`create_all()` real angelegt wird), ist die oben beschriebene portable PostgreSQL-Instanz auf
Nutzerwunsch NICHT entfernt worden ("wir brauchen sie noch") -- sie steht für den geplanten
Datenumzug weiterhin bereit, aktuell gestoppt (`pg_ctl stop`), aber mit Daten und Konfiguration
unverändert vorhanden.

### Datenumzugsskript (seit 1.3.36)

Erste Runde des eigentlichen Datenumzugs -- nur das Skript bauen und lokal gegen die portable
PostgreSQL-Instanz ausprobieren; der Umzug auf den Server bleibt ein eigener, späterer Schritt.

**`scripts/migrate_sqlite_to_postgres.py`** -- Notfall-taugliche Aufrufanleitung, direkt
auszuführen (dieselbe Sofort-auffindbar-Anforderung wie bei `reset_admin_2fa.py`, siehe oben):

```
python scripts/migrate_sqlite_to_postgres.py --target-url postgresql+psycopg://user:pass@host:port/dbname
```

Liest standardmäßig die reale `dachkonzepte_erp.db` im Projektordner -- **ausschließlich
lesend**: über SQLites Online-Backup-API in eine temporäre Kopie gesichert (verträgt sich mit
einer parallel laufenden Anwendung), diese zusätzlich per `mode=ro`-URI geöffnet, ein
Schreibversuch würde vom Treiber selbst verweigert, nicht nur vermieden. **Sicherung gegen eine
nicht leere Zieldatenbank** (falsch übergebene Verbindungszeichenfolge, verwechselte
Umgebungsvariable): das Skript verweigert den Dienst, sobald in der Zieldatenbank auch nur eine
Zeile in einer der dem ORM bekannten Tabellen steht -- außer `--force-truncate` wird
ausdrücklich gesetzt, und selbst dann fragt es ohne zusätzliches `--yes` interaktiv nach dem
Datenbanknamen zur Bestätigung (Muster: `reset_admin_2fa.py`). Das Leeren selbst bleibt dabei
strikt auf die Tabellen beschränkt, die `Base.metadata` tatsächlich kennt -- nie ein
pauschales DROP SCHEMA/DATABASE anhand der übergebenen Verbindungszeichenfolge. Ablauf:
`alembic upgrade head` gegen das Ziel, Daten laden (`Base.metadata.sorted_tables`-Reihenfolge),
Fremdschlüssel-Konsistenz der geladenen Daten prüfen, Sequenzen zurücksetzen (jede Tabelle mit
Integer-Primärschlüssel, nicht nur eine vermutete Handvoll), Zeilenzahlen Quelle gegen Ziel
verifizieren, verschlüsselte SMTP-/Microsoft-365-/TOTP-Felder probeweise entschlüsseln (ohne den
Klartext je auszugeben). Dieselbe Anleitung steht auch im Kopfkommentar der Skriptdatei selbst.

**Fund, der über dieses eine Skript hinausgeht -- ein dauerhaftes Prinzip für jedes künftige
Skript gegen PostgreSQL:** der erste Entwurf schaltete für die Dauer des Ladens die
Fremdschlüssel-Trigger auf allen Zieltabellen ab (`ALTER TABLE ... DISABLE TRIGGER ALL`) --
notwendig, weil zwei Tabellen (`quote_sections`/`order_sections`) sich selbst referenzieren
(`parent_id`) und PostgreSQL eine Fremdschlüssel-Bedingung standardmäßig sofort bei jeder
einzelnen Zeile prüft, nicht erst beim Commit. Der erste tatsächliche Testlauf scheiterte damit
sofort: `InsufficientPrivilege: ... ist ein Systemtrigger`. Die internen, eine
Fremdschlüssel-Bedingung durchsetzenden Trigger (`RI_ConstraintTrigger_*`) lassen sich nur von
einem Superuser abschalten -- eine gewöhnliche Anwendungsrolle hat dieses Recht nicht, und genau
eine solche gewöhnliche Rolle ist auf einem gehosteten PostgreSQL-Server (verwaltete Datenbank,
kein eigener Serverzugriff) realistisch alles, was zur Verfügung steht. **Die eigentliche Lehre:
eine Lösung, die Superuser-Rechte voraussetzt, lässt sich lokal (wo die eigene Rolle typischerweise
Eigentümer aller Tabellen ist und mehr darf) erfolgreich testen und scheitert dann erst beim
ersten echten Einsatz auf dem Zielserver -- der schlechteste Zeitpunkt, das zu merken.** Behoben
ohne besondere Rechte: die beiden betroffenen Tabellen werden in mehreren Durchläufen geladen
(erst Zeilen ohne offene Selbstreferenz, dann die, deren Elternzeile bereits geladen ist, beliebig
tief verschachtelbar) -- funktioniert mit jeder Rolle, die schlicht INSERT auf ihre eigenen
Tabellen darf. **Gilt als Grundsatz für jedes künftige Skript, das schreibend gegen eine
PostgreSQL-Datenbank arbeitet**: nichts bauen, das `DISABLE TRIGGER ALL`, `SET
session_replication_role` oder eine vergleichbare, Superuser voraussetzende Abkürzung braucht,
ohne das vorher gegen eine Rolle ohne Superuser-Rechte zu prüfen -- lokal ist die eigene Rolle
fast immer großzügiger berechtigt als später auf dem echten Server.

**Lauf gegen die lokale `spielwiese`-Instanz, Stand 13.09.2026**: 121 Tabellen, 3040 Zeilen,
1,7 Sekunden, 0 Zeilenzahl-Abweichungen, 0 verwaiste Fremdschlüssel. Anschließend die Anwendung
tatsächlich lokal gegen PostgreSQL gestartet (Wegwerf-Testkonto ohne Admin-Rolle, um die
1.3.34-2FA-Pflicht zu umgehen) und geprüft: Kundenliste (162 Kunden), ein Angebot als PDF
(225 KB), ein Einsatzbericht als PDF (2,7 MB inkl. Fotos), das verschlüsselte
Microsoft-365-Client-Secret weiterhin entschlüsselbar. Wichtigster Test: ein neuer Kunde per
`POST /api/customers` angelegt -- id=163, exakt der nächste freie Wert nach dem bisherigen
Maximum 162, bestätigt die zurückgesetzten Sequenzen unter echter Last, nicht nur rechnerisch.
Testkonto/-kunde danach wieder entfernt. **Bewusst NICHT in dieser Runde**: der Umzug auf den
Server selbst -- erst muss der Weg lokal tragen.

## Firmenlogo in der Sidebar (seit 1.3.38)

Die Sidebar zeigte oben links immer nur den Schriftzug "DACHKONZEPTE" (`_sidebar.html`, reiner
`<span>`, keine Gestaltung außer fett/Letter-Spacing). Sollte durch ein Logo ersetzt werden,
das jederzeit austauschbar ist.

### Befund vor dem Bauen -- zwei echte Überraschungen

Es gibt bereits seit 1.0.58 ein Firmenlogo-System (`app/company_logo.py`,
`GeneralSettings.logo_filename`, `DACHKONZEPTE_LOGO_FILE_ROOT`, über `data_dir()` also bereits
`ERP_DATA_DIR`-fähig) -- genutzt für den gezeichneten `logo`-PDF-Baustein
(`app/document_frame.py::_draw_logo()`, Standard `visible=False`, siehe "PDF-Rahmen" oben) und
das PWA-Startbildschirm-Icon der Monteursansicht (`app/mobile_manifest.py::build_icon_png()`).
Erlaubt: PNG/JPEG/WebP/SVG, max. 5 MB, keine Prüfung von Seitenverhältnis oder Pixelmaßen.
Ausgeliefert über `GET /api/settings/general/logo` (nur die normale Anmeldepflicht, kein
Admin-Vorbehalt -- unabhängig davon geprüft, nicht in dieser Runde geändert).

**Erste Überraschung: es gibt (und gab) nie ein hochgeladenes Logo.** `GeneralSettings.
logo_filename` stand in der echten Datenbank auf `NULL`, `data/company_logo/` war leer. Die
Frage "taugt das vorhandene Logo für die schmale Sidebar" ließ sich deshalb nicht beantworten --
es gab keine Datei zum Ansehen.

**Zweite Überraschung: es gab (und gibt jetzt neu) keine Oberfläche dafür.** Der Upload-Endpunkt
(`POST /api/settings/general/logo`) existierte, wurde aber von KEINEM Template aufgerufen --
weder ein `<input type="file">` noch ein Aufruf der URL fand sich irgendwo. Die
"Unternehmensstammdaten"-Sektion in `settings.html` hatte nur Textfelder (Name, Adresse, Bank,
Steuer), kein Logo-Feld. Vermutlich ein Rest aus der 1.0.58-Grundlage für den seither (1.3.20)
wieder entfernten PDF-Layout-Editor, dessen eigentliche Logo-Verwaltung mit ihm verschwunden ist,
ohne dass eine Ersatzstelle nachgezogen wurde. Auf Rückfrage ergänzt (siehe unten) -- ohne sie
wäre die neue Sidebar-Anzeige nie zu testen oder zu befüllen gewesen.

### Entscheidung: dasselbe Logo, keinen zweiten Upload

Wie vom Nutzer vorgegeben: kein eigener, zweiter Sidebar-Logo-Upload. Stattdessen zeigt die
Sidebar dasselbe Firmenlogo, das auch PDFs/das PWA-Icon nutzen -- mit einer bewussten
Vorkehrung für später:

- **`app/company_logo.py::sidebar_logo_filename(db) -> str | None`** -- die eigentliche
  "welches Logo zeigt die Sidebar"-Entscheidung, heute immer `GeneralSettings.logo_filename`
  (mit Existenzprüfung der Datei -- ein Datenbankeintrag ohne Datei fällt auf den Schriftzug
  zurück, nicht auf ein defektes `<img>`). Ein späterer, dedizierter Sidebar-Logo-Upload müsste
  nur diese eine Funktion umstellen, keine der Aufrufstellen.
- **`sidebar_logo_url()`** (Jinja-Global, `app/routers/pages.py`, Muster `get_theme()`/
  `is_module_enabled()` -- eigene, kurzlebige `SessionLocal()` je Aufruf, damit ein Logo-Wechsel
  ohne Serverneustart auf der nächsten Seitenanfrage sichtbar wird, siehe "Bekannte, bewusst
  offene Punkte" für die dabei bereits bekannte Einschränkung, dass das nicht per Test-Session
  umstellbar ist). Liefert `/api/settings/general/logo?v=<stored_filename>` oder `None` --
  der `?v=`-Parameter (der pro Upload neue, zufällige `stored_filename`, siehe
  `document_storage.py::make_stored_filename()`) bricht gezielt das Browser-Bild-Caching, sobald
  ein Logo ersetzt wird.
- **`_sidebar.html`**: `{% if sidebar_logo_url() %}` zeigt ein `<img class="app-sidebar-logo">`,
  sonst unverändert der `<span class="app-sidebar-brand">`-Schriftzug -- eine leere Stelle wäre
  schlechter als Text. Ursprünglich `height:32px;width:auto;max-width:160px;object-fit:contain`
  auf demselben `<img>` -- **in 1.3.39 als echter Fehler erkannt und anders gelöst, siehe dort**.
  Verhält sich beim Einklappen der Sidebar (60px-Icon-Leiste) und auf Mobilgeräten exakt wie der
  bisherige Schriftzug (dieselben CSS-Regeln um die Logo-Elemente ergänzt statt neuer, eigener
  Regeln).
- **`_mobile_header.html` (Monteursansicht) bewusst unverändert** -- der Auftrag bezog sich
  ausdrücklich auf "die Sidebar"; die mobile Kopfzeile hat einen eigenen, deutlich schmaleren
  Aufbau (geteilte Zeile mit dem Mitarbeiternamen, Zusatz "· Vor Ort") und war nicht Teil dieser
  Anfrage.
- **Settings-Oberfläche ergänzt** (Einstellungen → Unternehmensstammdaten, neuer Abschnitt
  "Firmenlogo" -- Datei-Upload/Vorschau/Entfernen, Muster der bereits bestehenden
  Briefpapier-Upload-Felder unter Dokumente & Layout): da es vorher gar keine Oberfläche gab,
  war ein bloßer Hinweistext ("dieses Logo erscheint auch in der Sidebar") ohne Weg, überhaupt
  eines hochzuladen, wirkungslos gewesen -- die Ergänzung war Voraussetzung dafür, dass sich die
  neue Sidebar-Anzeige praktisch nutzen und testen lässt, nicht nur Text.

### Geprüft, nicht nur behauptet

Kein reales Firmenlogo vorhanden, also mit drei synthetischen Testbildern (quadratisch 200×200,
breit 600×100, hoch 100×600) gegen eine isolierte, lokale Testinstanz (frische SQLite-Datei,
eigener Port) tatsächlich durchgespielt: Hochladen über den echten Endpunkt, Sidebar zeigt danach
das `<img>` mit korrekter, cache-brechender URL, ausgeliefertes Bild byte- und
pixelgenau identisch mit der hochgeladenen Datei (Content-Type `image/png`, Pillow-Nachmessung
der Maße), für alle drei Seitenverhältnisse. Entfernen des Logos lässt die Sidebar korrekt zum
Schriftzug zurückfallen. **Kein echter Browser-Screenshot** -- in dieser Umgebung stand kein
Browser-Automatisierungswerkzeug zur Verfügung (dieselbe, bereits in "Mitarbeiter-Formular
list-first" dokumentierte Einschränkung). Genau dieser fehlende Browser-Screenshot ließ einen
echten CSS-Fehler durchrutschen -- siehe "Fehlerbehebung und einstellbare Höhe" unten: die
Behauptung "mathematisch aspect-ratio-treu" für `height`+`max-width`+`object-fit:contain` auf
demselben `<img>` war falsch.

### Fehlerbehebung und einstellbare Höhe (seit 1.3.39)

Rückmeldung nach dem ersten echten Einsatz: bei 32px Höhe war ein Schriftzug unter dem
Bildzeichen nicht mehr lesbar. Zwei Änderungen plus eine Untersuchung an der tatsächlich
hochgeladenen Datei, bevor irgendetwas an einem zweiten Upload gebaut wurde.

**Echter, selbst gefundener CSS-Fehler.** Der ursprüngliche Ansatz (`height`, `max-width` und
`object-fit:contain` alle auf demselben `<img>`) verkleinert bei einem breiten Logo die Höhe
wieder: die CSS-Ersatzelement-Breiten/Höhen-Auflösung (CSS 2.1 §10.3.2/§10.4) verwirft die feste
Höhe, sobald `max-width` als Override eingreift -- `width` wird dann auf `max-width` festgelegt
UND `height` bleibt zwar formal wie angegeben, aber `object-fit:contain` skaliert den
sichtbaren Bildinhalt anschließend so, dass er in die (jetzt schmalere) Box passt, was bei einem
hinreichend breiten Bild die tatsächlich sichtbare Höhe unter den konfigurierten Wert drückt --
exakt das Symptom, das man vermeiden will. Behoben durch Entkopplung: die Breitenbegrenzung
(jetzt 200px) sitzt auf einem umschließenden `<span class="app-sidebar-logo-wrap">`
(`overflow:hidden`), das `<img>` selbst trägt NUR noch die feste Höhe (als Inline-Style, siehe
unten) und `flex:0 0 auto` (verhindert zusätzlich ein Verkleinern durch Flexbox selbst). Ein zu
breites Logo wird dadurch rechts **abgeschnitten**, nicht mehr verkleinert -- an einem
synthetischen 1000×60px-Testbild (Seitenverhältnis 16,7:1) nachgewiesen: bei 64px eingestellter
Höhe liefert die Sidebar exakt `style="height:64px"` ohne jedes `max-width` auf dem `<img>`.
**Grundsatz für jedes künftige `<img>` mit unbekanntem Seitenverhältnis**: `height` (oder
`width`) UND eine Begrenzung der anderen Achse (`max-width`/`max-height`) nie auf demselben
Element -- die Begrenzung gehört auf einen Wrapper mit `overflow:hidden`, sonst kann die feste
Achse bei einem extremen Seitenverhältnis unbemerkt unterlaufen werden.

**Einstellbare Höhe** (24-80px, Feld direkt neben dem Upload in Einstellungen →
Unternehmensstammdaten): `GeneralSettings.sidebar_logo_height_px` (Migration `c327ff4ad332`,
`server_default='48'`), `app/company_logo.py::sidebar_logo_height_px(db)` (auf den erlaubten
Bereich geklammert, dieselbe Verteidigung-in-der-Tiefe wie bei `sidebar_logo_filename()`), neuer
Jinja-Global `sidebar_logo_height_px()` -- die Sidebar liest die Höhe live, kein
Serverneustart nötig. Auswirkung auf den Kopfbereich (wie vom Nutzer verlangt, VOR dem Bauen
berichtet): bei 48px (neuer Standard) wächst die Kopfzeile von vorher ca. 52px auf ca. 80px
(+~54%), am oberen Ende (80px) auf ca. 112px (+~115%) -- beides im normalen Rahmen für einen
Sidebar-Header mit Logo, kein Kompromiss nötig, aber bewusst nicht unbegrenzt (deshalb die
80px-Obergrenze).

**Die tatsächlich hochgeladene Datei, genau untersucht, bevor über einen zweiten Upload
entschieden wurde**: 8000×5295px RGBA-PNG, Inhalts-Bounding-Box (per Alphakanal) 5970×4907px
(Seitenverhältnis ≈1,22:1). Der Inhalt ist eine EINZIGE, durchgehende geometrische Form (ein
zweifarbiges Chevron/Dach-Symbol) -- lückenlos von y≈132px bis y≈5148px, **kein Schriftzug an
irgendeiner Stelle** (auch am unteren Rand der Inhalts-Box vergrößert nachgeprüft: reines Weiß).
Das widerlegt die ursprüngliche Annahme "Bildzeichen mit Schriftzug darunter" -- vermutlich wird
der Firmenname in PDFs ohnehin separat als echter Text gezeichnet
(`build_din5008_header_block()`), nicht als Teil der Logo-Grafik; der optische Gesamteindruck
"Icon + Name" entsteht erst durch beides zusammen, nicht durch eine einzelne Bilddatei.
**Ergebnis: mehr Höhe reicht, kein eigener Sidebar-Upload nötig** -- ein einfaches, kräftiges,
fast quadratisches Symbol ohne feine Details bleibt bei jeder Höhe zwischen 24 und 80px klar
erkennbar, die Rechnung "wird der Schriftzug bei X px unter 8px und damit unlesbar" war für
diese Datei von Anfang an gegenstandslos, da es keinen Schriftzug gibt. Vom Nutzer bestätigt --
kein zweiter Upload gebaut, `sidebar_logo_filename()` bleibt bei genau einer Stufe
(Firmenlogo → Schriftzug). **Diese Diagnose war falsch -- seit 1.3.43 korrigiert, siehe
"Korrektur: doch ein Schriftzug" am Ende dieses Abschnitts.**

### Anzeige-Rendition (seit 1.3.40)

Die echte, hochgeladene Datei war 8000×5295px/252KB -- in der Sidebar auf 24-80px Höhe
dargestellt. Ohne Gegenmaßnahme lädt UND dekodiert der Browser bei JEDER Seitenanfrage die
vollen 42 Megapixel, da dieses Projekt ausschließlich klassische Mehrseiten-Navigation macht
(keine SPA) -- die Sidebar wird bei jedem Klick neu angefordert, nicht nur einmal. Selbst mit
perfektem Netzwerk-Caching bliebe der Dekodier-Aufwand (42 Mio. Pixel → Bitmap im Speicher)
bei jedem Rendern bestehen.

**Lösung**: `replace_logo()` (`app/company_logo.py`) erzeugt beim Hochladen zusätzlich zur
unveränderten Originaldatei (weiterhin für PDFs/das PWA-Icon, die beide `logo_path()` direkt von
der Platte lesen, siehe `document_frame.py`/`mobile_manifest.py` -- dort zählt die volle
Auflösung tatsächlich, ein Druck-PDF darf nicht durch diese Änderung an Qualität verlieren) eine
verkleinerte Anzeige-Rendition (`display_logo_path()`, `<stem>_display.png`, längste Kante auf
`MAX_DISPLAY_DIMENSION=480` px herunterskaliert -- reicht für 80px CSS-Höhe selbst auf einem
3x-Retina-Bildschirm bequem aus). `GET /api/settings/general/logo` -- der EINZIGE
HTTP-Auslieferungsweg (Sidebar-`<img>` UND die Vorschau in den Einstellungen; PDFs/PWA-Icon
nutzen ihn nie) -- liefert bevorzugt diese Rendition, fällt auf das Original zurück, wenn keine
existiert (SVG -- dort unnötig, bereits vektoriell/klein -- oder ein vor 1.3.40 hochgeladenes
Logo). Scheitert die Rendition-Erzeugung (z. B. ein Pillow nicht bekanntes/beschädigtes Format),
bricht der Upload NICHT ab -- ein etwas größeres Original ist besser als ein fehlgeschlagener
Upload, `view_company_logo()` fällt dann einfach auf das Original zurück. Zusätzlich
`Cache-Control: private, max-age=31536000, immutable` auf der Antwort -- sicher, weil die URL
bereits einen `?v=<stored_filename>`-Cache-Brecher trägt (derselbe Name zeigt nie auf einen
später geänderten Inhalt, ein neuer Upload bekommt einen neuen Namen).

**Real gemessen, nicht nur behauptet** (mit der tatsächlichen Logo-Datei, gegen eine isolierte
Testinstanz): Original 258.475 Bytes/8000×5295px -- ausgelieferte Rendition 19.530 Bytes/
480×318px. **Faktor ~13 bei der Übertragungsgröße, Faktor ~278 bei der Pixelzahl** (42,4 Mio. →
153.000 Pixel). Beide Dateien bestätigt nebeneinander auf der Platte vorhanden, Sidebar zeigt
weiterhin `style="height:48px"` unverändert korrekt.

### Korrektur: doch ein Schriftzug -- dedizierter Sidebar-Logo-Upload (seit 1.3.43)

Die 1.3.39-Diagnose ("kein Schriftzug an irgendeiner Stelle", per Bounding-Box-Auswertung des
Alphakanals ermittelt) war falsch. Auf einem echten Screenshot der Sidebar ist "DACHKONZEPTE
GmbH" und darunter gesperrt "RÖDCHEN" klar erkennbar, unterhalb des Dachzeichens -- die
automatisierte Auswertung hat das nicht erkannt, mutmaßlich weil Schriftzug und Bildzeichen
räumlich zu nah beieinander liegen, um über eine einzelne Inhalts-Bounding-Box getrennt zu
werden (die Messung selbst -- 8000×5295px, Inhalts-Box 5970×4907px -- bleibt richtig, nur ihre
Interpretation "eine einzige, durchgehende Form ohne Text" war es nicht). Das ändert die
1.3.39-Antwort: ein zweiter, dedizierter Sidebar-Logo-Upload ist doch nötig.

- **Zwei unabhängige Uploads statt einem** (`app/company_logo.py`, vollständig überarbeiteter
  Moduldocstring dort): **Firmenlogo** (`LOGO_ROOT`, `GeneralSettings.logo_filename`) bleibt für
  PDFs und das PWA-Icon zuständig, unverändert. Neu: **Sidebar-Logo** (`SIDEBAR_LOGO_ROOT`, neue
  Spalte `GeneralSettings.sidebar_logo_filename`, Migration `4ba46163a7e8`, eigener Ordner unter
  `ERP_DATA_DIR` -- Umgebungsvariable `DACHKONZEPTE_SIDEBAR_LOGO_FILE_ROOT`, achte Variable dieser
  Art, siehe `.env.example`). Beide Uploads teilen sich dieselbe Speicher-/Validierungslogik
  (`validate_logo_image()`, Anzeige-Rendition aus 1.3.40) über einen gemeinsam genutzten
  `root`-Parameter an `logo_directory()`/`logo_path()`/`display_logo_path()`/
  `_generate_display_rendition()`/`replace_logo()`/`delete_logo()` -- `replace_sidebar_logo()`/
  `delete_sidebar_logo()`/`sidebar_logo_path()`/`sidebar_logo_display_path()` sind dünne
  Wrapper, die `root=SIDEBAR_LOGO_ROOT` fest einsetzen. **Fallstrick beim Bauen, selbst gefunden
  und behoben, bevor er in Produktion gegangen wäre**: ein naiver `root: Path = LOGO_ROOT`-
  Vorgabewert an diesen Funktionen hätte den bestehenden Testmustern
  (`monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / ...)`, u. a. in
  `tests/test_v158_pdf_layout_foundation.py`/`test_v249_sidebar_logo.py`) den Boden entzogen --
  ein Vorgabewert wird einmalig bei der Modul-Definition gebunden, nicht bei jedem Aufruf neu aus
  dem (dann längst geänderten) Modul-Global gelesen. Stattdessen `root: Path | None = None` mit
  `if root is None: root = LOGO_ROOT` im Funktionskörper -- liest `LOGO_ROOT` bei jedem Aufruf
  frisch, genau wie vor dem Umbau.
- **Drei statt zwei Stufen** (`sidebar_logo_filename(db)`, weiterhin in `company_logo.py`): (1)
  Sidebar-Logo, falls hinterlegt und die Datei existiert, (2) sonst Firmenlogo unter derselben
  Bedingung, (3) sonst `None` (Schriftzug). Liefert dafür seit 1.3.43 kein nacktes
  `str | None` mehr, sondern ein `SidebarLogoReference`-NamedTuple (`source: "sidebar"|"company"`,
  `stored_filename`) -- der einzige Aufrufer (`sidebar_logo_url()` in `app/routers/pages.py`)
  braucht die Quelle, um die richtige von zwei getrennten Auslieferungsrouten anzusprechen
  (`GET /api/settings/general/sidebar-logo` bzw. `.../logo`, je im eigenen Ordner). Die
  1.3.42-Ausnahmesicherheit dieses Jinja-Globals bleibt dabei unverändert vollständig -- der
  gesamte Rangfolge-Aufruf UND das URL-Zusammensetzen aus `ref.source`/`ref.stored_filename`
  liegen innerhalb desselben `try/except Exception`-Blocks, ein unerwarteter Wert schlägt also
  ebenso wenig durch wie ein DB-Fehler.
- **Zwei neue Endpunkte** (`app/routers/settings.py`, Muster der bestehenden Firmenlogo-Routen):
  `POST/GET/DELETE /api/settings/general/sidebar-logo` -- Upload validiert genauso über
  `validate_logo_image()` (400 statt 500 bei einem ungültigen Bild, siehe 1.3.42), GET liefert
  bevorzugt die Anzeige-Rendition mit demselben unveränderlichen Cache-Header wie beim
  Firmenlogo.
- **Einstellungen klar getrennt** (Unternehmensstammdaten → zwei eigene Abschnitte
  "Firmenlogo"/"Sidebar-Logo" statt eines gemeinsamen): das Firmenlogo-Feld verlor dabei sein
  bisheriges Höhenfeld (das war ohnehin die Sidebar-Anzeigehöhe, nicht seine eigene) -- es wandert
  vollständig zum neuen Sidebar-Logo-Abschnitt, wo es fachlich hingehört (gilt für das jeweils
  tatsächlich in der Seitenleiste gezeigte Logo, unabhängig davon, welche Stufe greift). Ein
  client-seitig berechneter Hinweistext im Sidebar-Logo-Abschnitt sagt live, welche Stufe ohne
  eigenes Sidebar-Logo aktuell greift ("zeigt ersatzweise das Firmenlogo" / "zeigt den
  Schriftzug").
- **Tests** (`tests/test_v249_sidebar_logo.py`, überarbeitet): alle drei Stufen einzeln (nur
  Firmenlogo, Sidebar-Logo vor Firmenlogo, Sidebar-Logo-Datei fehlt → Rückfall auf Firmenlogo,
  beides fehlt → `None`), die drei neuen Endpunkte über `router_test_client()`, und dass ein
  Sidebar-Logo-Upload den Firmenlogo-Ordner/-Datensatz unangetastet lässt (getrennte Ordner,
  getrennte Spalten).

## Umgestaltung der Sidebar (seit 1.3.44)

Größerer Umbau von `_sidebar.html`/dem Seitenlayout in vier einzelnen Schritten -- dieser
Abschnitt wächst mit jedem Schritt. Schritt 1 (1.3.44): Kopfbereich (Logo) und die beiden
Kopfzeilen-Schaltflächen. Schritt 2 (1.3.45, diese Version): eine Topbar über dem Inhaltsbereich
samt Kontobereich rechts. Schritt 3-4 (Suche, Schnellzugriff) folgen einzeln in späteren
Versionen -- **bewusst nicht vorgezogen**, auch wenn der links reservierte, noch leere
Suchen-Platz in der Topbar bereits auf Schritt 3 vorbereitet.

### Schritt 1: Kopfbereich und Schaltflächen

**Ausgangslage**: das Logo stand oben links, direkt daneben (im selben, schmalen Kopfbereich)
die beiden Schaltflächen für Hell/Dunkel und Ein-/Ausklappen -- dadurch blieb für das Logo selbst
wenig Breite, ein Logo mit Schriftzug wäre darin unlesbar klein geblieben.

**Punkt 1 -- Logo allein, zentriert, volle Breite.**

- `.app-sidebar-head` wechselt von `justify-content:space-between` (Logo links, Buttons rechts)
  zu `justify-content:center` mit nur noch einem Kind (Logo bzw. Schriftzug-Fallback) -- die
  beiden Schaltflächen sind komplett aus dem Kopf entfernt, siehe Punkt 2.
- `.app-sidebar-logo-wrap`s Breitenbegrenzung wechselt von einem festen `max-width:200px` zu
  `max-width:100%` -- **bewusst relativ statt eines neuen, größeren festen Werts**: genau das
  war die vom Nutzer benannte Gefahr ("die Breitenbegrenzung muss entsprechend mitwachsen,
  sonst greift sie wieder zuerst und drückt die Höhe herunter") -- ein fester Wert hätte bei
  einer künftigen Änderung der Sidebar-Breite (240px) wieder auseinanderlaufen können, ein
  relativer nie. Die zugrundeliegende 1.3.39-Regel (Höhe und Breitenbegrenzung nie auf
  demselben `<img>`, die Begrenzung gehört auf einen Wrapper mit `overflow:hidden`) bleibt
  unverändert gültig und wird hier nur konsequent weitergeführt, nicht neu erfunden.
- **Höhenbereich auf 24-120px erweitert** (vorher 24-80), Standardwert von 48 auf 64 angehoben
  -- `company_logo.py::MIN/MAX/DEFAULT_SIDEBAR_LOGO_HEIGHT_PX`, `GeneralSettings.
  sidebar_logo_height_px` (Migration `60d7c8a775f0`, reiner `server_default`-Wechsel 48→64),
  `GeneralSettingsUpdate.sidebar_logo_height_px` (Pydantic-Grenzen), `settings.html` (Zahlenfeld
  `min`/`max`, Hinweistext, JS-Validierung). Begründung für den angehobenen Standardwert: der
  Kopf teilt sich die Breite nicht mehr mit den beiden Schaltflächen, ein größerer Standardwert
  wirkt dadurch nicht mehr gedrängt wie vorher. **Ausdrücklich transparent**: eine erneute,
  präzise Nachrechnung "wird ein Schriftzug bei Höhe X noch lesbar" (wie in 1.3.39 versucht)
  konnte für diese Version nicht wiederholt werden -- die lokal verfügbare Beispieldatei
  (`4ce61c7cadf743b7bee52db6bac1b4f8.png`) enthält bei tatsächlichem Nachsehen (Pillow-
  Zeilenprofil der Alphakanal-Tinte UND direktes Betrachten der Datei) nachweislich **keinen**
  Schriftzug, nur das zweifarbige Dachzeichen -- ein Widerspruch zur zuletzt beschriebenen
  Beobachtung ("DACHKONZEPTE GmbH"/"RÖDCHEN" auf einem Sidebar-Screenshot erkennbar), der sich
  mit den hier verfügbaren Mitteln nicht auflösen ließ (vermutlich zeigte jener Screenshot eine
  andere, tatsächlich hochgeladene Datei aus einer Umgebung, die dieser Sitzung nicht zugänglich
  ist). 64px ist deshalb eine begründete, aber nicht anhand einer konkreten Schriftzug-Höhe
  durchgerechnete Zwischenlösung -- bei Gelegenheit gegen die tatsächlich verwendete Datei
  visuell im Browser zu prüfen.
- **Eingeklappte Sidebar (60px) -- eigene, feste Behandlung statt der einstellbaren Höhe.** Wie
  vom Nutzer erwartet ("vermutlich braucht es dafür eine eigene Behandlung") reicht die für die
  volle Breite gedachte, einstellbare Höhe bei 60px nicht: bei 6px Kopf-Padding je Seite (eigens
  für den eingeklappten Zustand reduziert, vorher 14px) bleiben nur 48px Breite, ein bei 120px
  Höhe konfiguriertes Logo würde bei gleichem Seitenverhältnis weit darüber liegen. Lösung:
  `.app-sidebar.collapsed .app-sidebar-logo{height:32px!important}` -- eine feste, vom
  eingestellten Wert unabhängige, kleinere Höhe (die `!important` ist nötig, da die konfigurierte
  Höhe als Inline-Style sonst Vorrang hätte). Für das reine Text-Schriftzug-Fallback (kein Logo
  hinterlegt) bleibt es bei "gar keins" -- vollständig ausgeblendet wie bisher, für
  "DACHKONZEPTE" ist bei 60px kein sinnvoller Platz, anders als bei einem meist eher quadratischen
  Bildzeichen. Beide Regeln bewusst in `@media(min-width:1001px)` gekapselt (nicht einfach nur
  `.app-sidebar.collapsed ...`) -- auf Mobilgeräten kann die `collapsed`-Klasse durch einen
  Resize ohne Neuladen bestehen bleiben (siehe das bereits bestehende
  `@media(max-width:1000px)`-Zurücksetzen), dort soll das aber weiterhin die volle, unveränderte
  Darstellung bedeuten, nicht die geschrumpfte Desktop-Variante.

**Punkt 2 -- Hell/Dunkel und Ein-/Ausklappen in den unteren Bereich.**

Neuer Wrapper `.app-sidebar-bottom` (mit dem `border-top`, das vorher auf `.app-sidebar-foot`
saß) umschließt jetzt in dieser Reihenfolge: eine neue Zeile `.app-sidebar-utilities` (beide
Schaltflächen, direkt unter der Navigation), `#appSidebarFoot` (Benutzer/Abmelden bzw.
Login-Formular, unverändert), `.app-sidebar-version`. "Neben Abmelden" wörtlich als eigene Zeile
direkt darüber umgesetzt, nicht als eine einzige, gemeinsame Zeile mit dem Abmelden-Button --
letzteres hätte bei einem vollbreiten Text-Button plus zwei Icon-Buttons zusammengedrängt gewirkt,
genau das vom Nutzer benannte Risiko ("ohne dass es gedrängt wirkt"). Beide Bereiche liegen
dadurch trotzdem sichtbar im selben, unteren Block direkt aneinander angrenzend.

Bewusst **keine** Änderung an `renderAuthFoot()` (dem JS, das `#appSidebarFoot` bei jedem
Auth-Status-Abruf per `innerHTML` neu aufbaut, inkl. "Mein Konto"): die beiden Schaltflächen
sitzen als statisches Jinja-Markup außerhalb von `#appSidebarFoot`, ihre einmalig beim
Skriptstart gebundenen Event-Listener (`toggle.addEventListener(...)`, `themeToggle.
addEventListener(...)`) werden dadurch nie zerstört -- kein erneutes Binden nötig, kein Risiko,
die sicherheitsrelevante Login/Logout-Logik dabei versehentlich anzufassen. "Mein Konto" bleibt
deshalb unverändert innerhalb von `#appSidebarFoot`, exakt wie vom Nutzer vorgegeben ("wandert
erst mit der Topbar in einem späteren Schritt nach oben").

**Bedienbarkeit im eingeklappten Zustand geprüft**: `.app-sidebar.collapsed .app-sidebar-toggle`
wird an KEINER Stelle auf `display:none` gesetzt (nur `.app-theme-toggle` verschwindet
eingeklappt, bereits bestehendes, unverändertes Verhalten) -- die Schaltfläche, mit der man
wieder ausklappt, bleibt im eingeklappten Zustand also garantiert erreichbar. Als Regressionstest
festgehalten (`test_collapse_toggle_is_never_hidden_when_collapsed_but_theme_toggle_is`,
`tests/test_v253_sidebar_layout.py`), da ein versehentliches `display:none` auf der falschen
Klasse genau diese Bedienbarkeit stillschweigend gebrochen hätte.

**Was unverändert bleibt, geprüft statt nur behauptet**: `_mobile_header.html` kennt keine der
hier verschobenen/neuen Klassen (`app-sidebar-head`/`app-sidebar-utilities`/`app-theme-toggle`/
`app-sidebar-toggle`) -- als Test festgehalten. Navigationseinträge, ihre Reihenfolge und die
Gruppen "Stammdaten"/"System" (1.3.28) sind an keiner Stelle angefasst, nur Kopf- und
Fußbereich drumherum.

**Kein echter Browser-Screenshot möglich** (dieselbe, bereits mehrfach dokumentierte
Werkzeug-Einschränkung dieser Umgebung) -- die tatsächliche visuelle Zentrierung/Anordnung ist
deshalb nur an der Markup-/CSS-Struktur nachgewiesen (`tests/test_v253_sidebar_layout.py`), nicht
an einem gerenderten Bild. Sollte bei Gelegenheit im Browser gegenprüft werden, insbesondere mit
dem tatsächlich hochgeladenen Sidebar-Logo.

### Schritt 2: Topbar

**Ausgangslage**: mit "Mein Konto" noch in der Sidebar (Schritt 1 verschiebt es bewusst nicht)
und keiner Leiste über dem Inhaltsbereich gab es weder Platz für eine künftige Suche (Schritt 3)
noch einen für den ganzen Bildschirm einheitlichen Ort für Kontoinformationen.

**Punkt 1 -- die Leiste selbst (`app/templates/_topbar.html`, neu).**

- Waagerecht, beginnt rechts neben der Sidebar (liegt als `{% include %}` innerhalb von
  `.app-content`, direkt nach dessen öffnendem `<div>` -- nie über die Sidebar hinweg, da
  `.app-content{flex:1;min-width:0}` in der bestehenden Flexbox-Aufteilung ohnehin nur den nach
  der Sidebar verbleibenden Platz einnimmt).
- `position:sticky;top:0` -- bleibt beim Scrollen sichtbar. Kein Zwischen-`overflow`-Vorfahre
  zwischen `.app-topbar` und dem Dokument-Scrollroot geprüft (sonst bräche die sticky-
  Positionierung), keiner gefunden.
- Höhe ergibt sich allein aus Innenabstand (`padding:12px 20px`, auf schmalen Bildschirmen
  `10px 16px`) plus dem 38px-Kontoknopf -- bewusst kein festgelegter `height`-Wert, damit die
  Leiste nicht dominiert, aber der Knopf bequem (≥38px) bedienbar bleibt.
- Ausschließlich bestehende Design-System-Variablen (`var(--card)`, `var(--line)`,
  `var(--accent)`, `var(--ink)`, `var(--soft)`) -- keine eigenen Farben. Die einzige feste
  Hex-Farbe (`#fff`, Text auf `var(--accent)` beim Kontoknopf) ist die bereits im ganzen Projekt
  etablierte Konvention für Text auf Akzentfarbe (z. B. `settings.html`s Buttons), keine neue
  Erfindung -- als Test abgesichert (`test_topbar_is_sticky_and_uses_design_system_variables_only`).
- Links bleibt in diesem Schritt ein leerer `<div class="app-topbar-search-slot">` (`flex:1`) --
  reserviert für Schritt 3, absichtlich ohne Inhalt.
- **Kollision mit der Sidebar in beiden Engpass-Zuständen geprüft, nicht nur behauptet:**
  - *Eingeklappte Desktop-Sidebar (60px)*: `.app-content{flex:1}` füllt in der bestehenden
    Flexbox-Aufteilung automatisch den nach der Sidebar verbleibenden Platz, unabhängig von deren
    aktueller Breite (240px oder 60px) -- die (in `.app-content` verschachtelte) Topbar beginnt
    dadurch ganz automatisch dort, wo die Sidebar gerade endet, ohne jede Sonderbehandlung.
  - *Schmaler Bildschirm (`@media(max-width:1000px)`)*: die mobile Sidebar wechselt dort auf
    `position:fixed` und verlässt damit den Flex-Fluss vollständig -- `.app-content` (und darin
    die Topbar) beansprucht dadurch automatisch die volle Breite, unabhängig davon, ob die
    Off-Canvas-Schublade offen oder geschlossen ist. Eine geöffnete mobile Sidebar
    (`z-index:40`)/ihr Scrim (`z-index:39`) sollen die Topbar dabei bewusst überlagern (gewolltes
    Ausklapp-Verhalten, kein Bug) -- die Topbar bekommt deshalb absichtlich ein niedrigeres
    `z-index:10`. Das Kontomenü selbst (`z-index:45`) liegt trotzdem über allem, da es ein
    eigenes, schwebendes Overlay ist.
  - **Nebenbefund, nicht behoben, nur vermerkt**: auf einem wirklich schmalen Bildschirm gibt es
    aktuell offenbar gar keinen Weg, die Off-Canvas-Sidebar überhaupt zu ÖFFNEN -- der einzige
    Umschalter (`#appSidebarToggle`) sitzt selbst innerhalb von `<aside class="app-sidebar">`,
    die im geschlossenen Zustand per `transform:translateX(-100%)` unsichtbar/unerreichbar ist.
    Vorher UND nachher bestehend (durch die 1.3.44-Verschiebung der Schaltflächen nicht
    verursacht), aber jetzt relevant, weil eine künftige Topbar-Hamburger-Schaltfläche eine
    naheliegende Lösung wäre -- nicht Teil dieses Schritts, hier nur festgehalten.

**Punkt 2 -- der Kontobereich rechts.**

- Neuer, gemeinsamer Helfer `app/auth.py::resolve_account_display(db, user) -> dict` (nach
  `user_from_request()`): bevorzugt `Employee.first_name`/`last_name` über
  `AppUser.employee_id` (seit 1.3.34 die Verknüpfung, aber **ohne** ORM-`relationship` -- daher
  ein expliziter `db.get(Employee, id)`), fällt auf `username` zurück, wenn kein Mitarbeiter
  verknüpft ist ODER die `employee_id` ins Leere zeigt (Verteidigung in der Tiefe). Initialen:
  erstes Zeichen von Vor- und Nachname bei ≥2 Namensteilen ("Tobias Rödchen" → "TR"), sonst die
  ersten zwei Zeichen des einzigen Teils, geklammert auf mindestens ein Zeichen (ein
  einbuchstabiger Benutzername liefert genau diesen einen Buchstaben, keinen `IndexError`).
  **Bewusst NICHT `AppUser.display_name`** -- das ist ein freies Textfeld ohne verlässliche
  Vorname/Nachname-Trennung, `Employee.first_name`/`last_name` sind strukturierte Felder.
- Fünfter Jinja-Global `account_display()` (`app/routers/pages.py::_account_display()`) --
  umhüllt `resolve_account_display()` mit einer eigenen, kurzlebigen `SessionLocal()` (Muster
  der bestehenden vier) und fängt jede Ausnahme ab (Prinzip aus 1.3.42: "ein Jinja-Global, der
  auf jeder Seite läuft, darf nie eine Ausnahme werfen") -- Rückfall bei Fehler: der
  Benutzername selbst, notfalls ein bloßes `"?"`. Anonym (kein `current_user`): leere Strings,
  der Kontoknopf erscheint dann gar nicht. Als sechster `env.globals[...]`-Eintrag im
  projektweiten Audit-Test (`test_no_further_database_backed_jinja_globals_exist_unguarded`,
  `tests/test_v252_deployment_hardening.py`) mitgezählt.
- **SSR statt zusätzlichem Fetch, bewusste Entscheidung**: Name/Initialen kommen direkt
  server-seitig gerendert in die Seite (wie schon die Sidebar-Nutzerinfo) -- kein zusätzlicher
  `fetch()`-Aufruf beim Laden nötig, da sich Initialen kaum je innerhalb einer Sitzung ändern.
  Nur das Öffnen/Schließen des Menüs (Klick auf den Knopf, Klick daneben, Escape) braucht JS --
  ohne jeden weiteren Netzwerkzugriff, da Name/Initialen bereits im HTML stehen.
- Menü (`#appTopbarAccountMenu`): voller Name als Überschrift, `<a href="/account">Mein
  Konto</a>`, `<button>Abmelden</button>` -- Logout dupliziert bewusst denselben
  Fetch-plus-Redirect-Code aus `_sidebar.html` (etablierte Projektkonvention: kein gemeinsames
  JS-Modul, kleine Snippets werden geteilt statt ausgelagert). Schließt bei Klick außerhalb
  (`document.addEventListener("click", ...)`, prüft `!menu.contains(e.target)`) oder Escape.

**Punkt 3 -- was in der Sidebar bleibt, unverändert.** "Abmelden" bleibt zusätzlich unten in der
Sidebar (zwei Wege schaden nicht), ebenso Benutzername und Versionsnummer. Die beiden
1.3.44-Schaltflächen (Hell/Dunkel, Ein-/Ausklappen) bleiben, wo sie sind -- `_sidebar.html` wird
in diesem Schritt an keiner Stelle angefasst.

**Rollout auf 31 Seiten**: jede Vorlage mit `{% include "_sidebar.html" %}` bekommt direkt nach
dem öffnenden `<div class="app-content">` zusätzlich `{% include "_topbar.html" %}` -- per Grep
verifiziert: genau 31 Treffer, je Datei genau einmal. **Bewusst ausgenommen**: die Monteursansicht
(`vor_ort.html`, nutzt `_mobile_header.html` statt der Sidebar) -- eigene Einschätzung, die der
Nutzer-Neigung ausdrücklich zustimmt: `_mobile_header.html` zeigt den Namen des angemeldeten
Monteurs bereits prominent und hat einen eigenen Ein-Klick-Abmelden-Button; ein zusätzlicher,
für den Desktop gedachter Kontoknopf/-menü würde der bewusst schmal gehaltenen, aufs Wesentliche
reduzierten Feld-Tablet-Ansicht entgegenwirken. Als Konsistenz-Test festgehalten
(`test_every_template_with_sidebar_also_includes_topbar`, `tests/test_v254_topbar.py`) --
Partials (Dateien mit führendem `_`) sind davon ausgenommen, da `_topbar.html`s eigener,
erklärender Jinja-Kommentar den Text `{% include "_sidebar.html" %}` selbst zitiert und sonst
fälschlich als Treffer gezählt würde (reiner Text-Scan-Fund, kein Rendering-Risiko -- ein
Jinja-Kommentar wird beim Rendern vollständig entfernt, anders als der 1.2.19-Fund in
`_debounce.html`, der ein JS-Kommentar war).

**Kein echter Browser-Screenshot möglich** (dieselbe Werkzeug-Einschränkung wie bei Schritt 1) --
Platzierung/Sticky-Verhalten/Menü-Interaktion sind ausschließlich über eine bare
`jinja2.Environment` mit gestubbten Globals (`tests/test_v254_topbar.py`) sowie an der reinen
Markup-/CSS-Struktur nachgewiesen, nicht an einem gerenderten Bild. Sollte bei Gelegenheit im
Browser gegenprüft werden.

## Migrations-Workflow

Bisher: Claude erstellt/ändert Modelle → Tobias führt lokal `alembic revision --autogenerate`
aus und schickt die generierte Datei zurück → Claude prüft sie systematisch gegen die
tatsächlichen Modelldefinitionen (Kettenanschluss an den aktuellen Kopf, `server_default` bei
neuen NOT-NULL-Spalten, Spaltennamen 1:1 gegen `app/models.py`) → nach Bestätigung führt Tobias
`alembic upgrade head` aus.

**In Claude Code kann sich das vereinfachen**, da direkter Terminalzugriff besteht: Claude Code
kann `alembic revision --autogenerate` und bei Bedarf auch `alembic upgrade head` selbst
ausführen. Die inhaltliche Prüfung (Kettenanschluss, `server_default`, Feldnamen) bleibt trotzdem
wichtig – nur eben vor Ort statt per Hochladen einer Datei.

**Seit 1.3.42 muss `DATABASE_URL` dafür ausdrücklich gesetzt sein, auch lokal** -- siehe
"Produktivbetrieb" → "Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41" oben für den realen
Vorfall, der dazu geführt hat. `alembic/env.py` fällt anders als `app/database.py` NICHT mehr
still auf SQLite zurück, sondern bricht mit einer klaren Fehlermeldung ab, wenn die Variable
fehlt. Ein `alembic`-Aufruf in dieser Sitzung/lokal sieht deshalb künftig so aus:
`DATABASE_URL=sqlite:///./dachkonzepte_erp.db alembic upgrade head` (oder die lokale
Postgres-Verbindungszeichenfolge) -- nicht mehr nackt `alembic upgrade head` ohne vorangestellte
Variable, wie es in dieser Sitzung bisher wiederholt üblich war.

**Fallstrick, seit 1.3.31 real erlebt: ein laufender `--reload`-Dev-Server tut dasselbe bei jedem
Speichern.** Läuft während der Arbeit bereits ein `uvicorn --reload`-Prozess gegen die echte
`dachkonzepte_erp.db` (z. B. vom Nutzer selbst gestartet), lädt dessen Auto-Reload bei JEDER
Dateiänderung im Projekt -- nicht nur an tatsächlich importierten Modulen, auch an einer neuen
Alembic-Migrationsdatei selbst -- `app.main` komplett neu, was denselben
`Base.metadata.create_all()`-Sicherheitsnetzaufruf erneut auslöst. Ergebnis real beobachtet: eine
neu erzeugte, noch nicht migrierte Tabelle (hier: `import_runs`/`imported_addresses`) wurde
zwischen zwei `alembic upgrade head`-Versuchen durch genau diesen Reload wiederholt neu angelegt,
obwohl sie zuvor per Skript gezielt gelöscht worden war -- `alembic upgrade head` schlug dadurch
mehrfach mit "table already exists" fehl, bis geprüft wurde, ob ein solcher Prozess überhaupt
läuft (`Get-Process` nach `uvicorn`/`python`). Lehre: vor `alembic upgrade head` prüfen, ob ein
laufender Dev-Server-Prozess existiert; wenn ja, entweder kurz stoppen lassen oder das Fenster
zwischen letzter Dateiänderung und `alembic upgrade head` so kurz wie möglich halten (keine
weitere Datei mehr anfassen, bevor die Migration durchgelaufen ist).

**Fallstrick (seit 1.2.23 bekannt): `app/main.py` ruft beim Import `Base.metadata.create_all(bind=engine)`
auf** – ein alter Sicherheitsnetz-Aufruf, der jede in `app/models.py` neu definierte Tabelle
sofort real anlegt, sobald irgendetwas `app.main` importiert (z. B. ein simpler
Smoke-Test-Aufruf wie `python -c "import app.main"`). Passiert das NACH dem Hinzufügen eines
neuen Modells, aber VOR `alembic revision --autogenerate`, findet Autogenerate keinen
Unterschied mehr (die Tabelle existiert ja schon) und erzeugt eine leere, nutzlose
No-op-Migration – die eigentliche `CREATE TABLE` fehlt dann in der Migrationskette, obwohl die
lokale DB bereits funktioniert. Selbst passiert, real erlebt: die neue Tabelle musste per
`DROP TABLE` wieder entfernt werden, bevor Autogenerate sie korrekt erkannte. Deshalb: nach dem
Anlegen eines neuen Modells zuerst `alembic revision --autogenerate`, danach erst irgendetwas
importieren, das `app.main` lädt (ein reiner `import app.models`-Check löst den Sicherheitsnetz-
Aufruf nicht aus, das ist unbedenklich).

**Dieser Mechanismus ist kein rein theoretisches Risiko** -- er ist bei `invoices`/
`invoice_items` (Migration `e057d15af828`) tatsächlich eingetreten und blieb unter SQLite
jahrelang unsichtbar, bis eine echte, frische PostgreSQL-Verifikation ihn aufgedeckt hat. Siehe
Abschnitt "PostgreSQL-Umstieg: Migrationskette repariert" oben für die vollständige Herleitung
und den Verifikationsnachweis (Version 1.3.35, 13.09.2026).

## Testen

- `pytest` läuft in Tobias' `.venv` unter Windows – **bitte tatsächlich ausführen**, nicht nur
  Syntax/Feldnamen von Hand prüfen, wenn eine Ausführung möglich ist.
- `cryptography`, `pytest` müssen in `requirements.txt` stehen (fehlten beide anfangs).
- E-Mail-Tests mocken `smtplib.SMTP` bzw. `urllib.request.urlopen` **am Verwendungsort**, nicht am
  Ursprungsmodul – also `@patch("app.email_sending.smtplib.SMTP")`, nicht
  `@patch("smtplib.SMTP")`.
- Bestehende Test-Hilfsfunktionen wiederverwenden statt neu bauen, u. a.:
  `db_session()` und `make_sent_overdue_invoice()` in `tests/test_v153_mahnwesen.py`,
  `make_order_with_item()` in `tests/test_v133_invoices.py`,
  `make_quote_with_items()` in `tests/test_v167_pagination.py`,
  `make_full_project()` in `tests/test_v192_project_templates.py` (nimmt seit Kurzem optionale
  `project_number`/`quote_number`-Parameter, falls in einem Test mehrere Projekte gebraucht werden).
- **Echte Routen-Tests über den `TestClient`** (seit 1.2.15, z. B. um eine Literal-vs-
  Platzhalter-Routenkollision zu beweisen, nicht nur die Business-Funktion direkt aufzurufen):
  `tests/conftest.py` stellt dafür die Fixtures `threaded_db_session` (wie `db_session`, aber
  `check_same_thread=False` + `StaticPool`, weil der `TestClient` Endpunkte über einen
  Threadpool ausführt) und `router_test_client` (Fabrik, baut aus echten Router-Instanzen eine
  schlanke Test-App mit fest angemeldetem Admin-Kontext, ohne die produktive
  `identity_and_audit_middleware`) bereit – seit 1.2.16 dort zentral, nicht mehr lokal in
  `test_v212_maintenance_windows.py` dupliziert. Verwendung:
  `client = router_test_client(db, some_router, other_router)`.
- **Eine Migrationsdatei selbst testen** (neu seit 1.2.19, `tests/test_v217_*.py`): Migrationen
  laufen sonst nie unter `pytest` (frische `:memory:`-DBs überspringen sie, siehe oben) – für
  Punkt 6 der 1.2.19-Planung (Bauteilarten-Migration muss vorhandene `setting_options`-Zeilen
  statt einer Code-Konstante lesen) war ein echter Test der Migrationslogik trotzdem
  gefordert. Lösung: die eigentliche Auswahl-Logik steckt als eigene, modulweite Funktion
  (`_resolve_roof_component_type_rows(bind)`) direkt in der Migrationsdatei, NICHT in
  `upgrade()` verschachtelt; der Test findet die Datei per `Path(...).glob(...)` über einen
  selbst gewählten, beschreibenden Namensteil (nicht über den Alembic-Hash, der bei einer
  erneuten `--autogenerate`-Ausführung wechseln würde), lädt sie per
  `importlib.util.spec_from_file_location()` + `exec_module()` und ruft die Funktion direkt
  gegen eine präparierte `Connection` auf. Neues Muster, kein bisheriges Vorbild – bei Bedarf
  für künftige Migrationen mit ähnlich nicht-trivialer Datenübernahme wiederverwendbar.
- **Jinja-Vorlagen wirklich rendern lassen** (neu seit 1.2.20, `tests/test_v218_template_rendering.py`):
  vorher deckte die Suite Templates gar nicht ab – ein Rekursionsfehler in `_debounce.html`
  (1.2.19) wurde erst bei der manuellen Server-Smoke-Prüfung gefunden. Neuer Test rendert JEDE
  Seiten-Route aus `app/routers/pages.py` (dynamisch aus `pages_router.routes` gewonnen, kein
  hartkodierter Pfad-Katalog) einmal über `router_test_client()` und prüft auf Status 200 – exakt
  das würde einen erneuten Rekursionsfehler in einer beliebigen Vorlage fangen, ganz unabhängig
  davon, ob die verwendete Beispiel-ID real existiert (Seiten in diesem Projekt laden alle echten
  Daten clientseitig per `fetch()` nach, der Server rendert nur das Gerüst). Siehe "Bekannte,
  bewusst offene Punkte" für die dabei ausgelöste, bestehende `SessionLocal()`-Kopplung der
  Jinja-Globals – für diesen (rein lesenden) Test unschädlich, aber kein Vorbild für einen
  künftigen, auch schreibenden Test.
- **`reportlab.platypus.Frame`-Geometrie direkt prüfen** (neu seit 1.3.1,
  `tests/test_v226_document_frame.py`): um zu belegen, dass unterschiedliche
  `DocumentPageMargins`-Werte tatsächlich unterschiedliche Seitenvorlagen ergeben, wird die
  interne Bausteinfunktion `app/document_frame.py::_build_frame()` direkt aufgerufen (kein
  vollständiges PDF nötig) und die resultierenden `Frame`-Attribute (`x1`/`y1`/`width`/`height`,
  öffentlich, kein Privat-Zugriff nötig) verglichen – robuster und schneller als Text-/
  Positionsextraktion aus gerenderten PDF-Bytes. Für "Seite X von Y" dagegen weiterhin die
  etablierte Content-Stream-Textextraktion (`_extract_pdf_text()`, seit 1.2.16 in
  `tests/test_v213_inspection_items.py`, hier wiederverwendet statt dupliziert).

## Arbeitsweise, die sich bewährt hat

- Bei größeren, mehrdeutigen Anfragen ("Vorgänge kopieren" o. Ä.) lieber kurz nachfragen bzw. den
  eigenen Plan vor dem Bauen kurz zur Bestätigung vorlegen, statt in eine falsche Richtung zu
  bauen – besonders wenn die Wahl (z. B. welcher von zwei PDF-Renderern) schwer rückgängig zu
  machen wäre.
- Selbst gefundene Fehler im eigenen Entwurf offen benennen, nicht still korrigieren.
- Veraltete oder irreführende Code-Kommentare beim Anfassen der jeweiligen Stelle korrigieren,
  nicht stehen lassen.
- Nach jeder Änderung: vollständigen Testlauf erwarten/anstoßen, bevor etwas als fertig gilt.
- **Nach dem Anlegen eines neuen Datensatzes per Klick immer direkt zu diesem Datensatz
  navigieren** (`location.href='/…/'+id`), nicht nur eine Statuszeile mit Erfolg anzeigen –
  etabliertes Muster u. a. in `order.html`s `createNewInvoice()`. Wurde bei
  `createProjectNow()` in `maintenance_contracts.html` zunächst vergessen (nur Textmeldung),
  woraufhin Tobias den neuen Vorgang nicht wiederfand (siehe 1.2.7) – bei jeder neuen
  "X erstellen"-Aktion von Anfang an mitdenken, nicht erst nachträglich beheben. **Bewusste
  Ausnahme seit 1.2.20**: `createProjectNow()` in `maintenance_contract.html` navigiert nicht
  mehr sofort, sondern zeigt ein Ergebnis-Panel mit Link – ausdrücklich vom Nutzer gefordert,
  weil der eigentliche nächste Schritt (Einsatzbericht) zwei Ebenen vom neuen Vorgang entfernt
  liegt und ein stiller Sprung nicht zeigt, wie es weitergeht. Gilt nur für diesen einen Fall,
  keine neue Standardregel – die Sofort-Navigieren-Regel bleibt für alle anderen "X erstellen"-
  Aktionen unverändert in Kraft.
- **Bei mehreren aufeinanderfolgenden Versionen innerhalb derselben Sitzung: jeweils committen,
  bevor die nächste beginnt** -- nicht mehrere Versionsstände ansammeln und erst am Ende in
  einem einzigen Commit zusammenfassen. Bei 1.3.39–1.3.41 (Sidebar-Logo: CSS-Fehler behoben,
  Anzeige-Rendition, Backup-Skript-Fix) ist genau das passiert, weil ein echter Vorfall
  (gelöschter Fremd-Ordner unter `Backup\`, siehe Regel 9) mittendrin die Aufmerksamkeit band --
  nachvollziehbar in diesem einen Fall, aber nicht der Normalfall. Ein Commit pro Version hält
  die Stände einzeln durchsuchbar/rücksetzbar; ein nachträglich zusammengefasster Commit über
  mehrere Versionen (wie bei 1.3.39–1.3.41 nötig, weil keine sauberen Zwischenstände mehr
  vorlagen) ist ein Notbehelf, kein Vorbild für den Regelfall.

## Bekannte, bewusst offene Punkte

- **Bewusst keine Erkennungsspalte für manuell bearbeiteten Mahntext -- nur ein Hinweis beim
  Speichern** (seit 1.3.21, siehe Abschnitt "Mahnwesen: Löschen/Versenden/Bearbeiten" oben für die
  volle Untersuchung/Begründung). `update_reminder_draft()` erlaubt das unabhängige Ändern von
  `text`/`fee_amount`/`new_due_date` an einem Mahnungsentwurf. Solange `text` seine Platzhalter
  (`{mahngebuehr}`/`{neue_frist}`) behält, zieht eine Zahlenänderung automatisch nach (der
  Fließtext wird bei jedem Lesezugriff neu zusammengesetzt, `format_reminder_text()`) -- das
  ursprünglich befürchtete Auseinanderlaufen tritt in dieser Form nicht ein. Ersetzt jemand einen
  Platzhalter dagegen manuell durch eine fest eingetippte Zahl, zieht eine spätere Zahlenänderung
  diesen einen Wert NICHT mehr nach -- eine echte Erkennung "wurde manuell bearbeitet" wurde
  bewusst NICHT gebaut (bräuchte eine neue, dauerhaft mitgeführte Spalte für ein Restrisiko, das
  nur diesen einen Sonderfall betrifft), stattdessen zeigt das Bearbeiten-Panel jetzt (1) einen
  nicht-blockierenden Hinweis beim Speichern, wenn der zum geänderten Feld gehörende Platzhalter
  im Text fehlt, und (2) die verfügbaren Platzhalter mit ihrer Bedeutung, damit seltener von Hand
  durch eine Zahl ersetzt wird, was ein Platzhalter bereits leisten würde
  (`reminderMissingPlaceholderWarning()` in `mahnwesen.html`/`invoice_detail.html`). Der
  Sonderfall selbst (ein Platzhalter wird trotz Hinweis absichtlich ersetzt und driftet danach
  unbemerkt auseinander) bleibt ein bewusst akzeptiertes Restrisiko, kein Fehler.
- **Langtext ganz ohne eingebettete Zeilenumbrüche bleibt eine unteilbare Zeile** (seit 1.3.15,
  CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot -- Zeilenumbruch-Variante für lange Positionstexte):
  die große-Leerräume-Behebung splittet den Langtext einer Position an jedem eingebetteten `\n`
  in eine eigene Tabellenzeile, damit reportlab dazwischen umbrechen kann. Ein Langtext ganz ohne
  `\n` (durchgehender Fließtext) bleibt dagegen weiterhin EINE einzige, unteilbare Zeile -- passt
  sie nicht mehr auf die restliche Seite, wandert sie komplett auf die nächste, mit demselben
  Leerraum-Effekt wie vor 1.3.15, nur seltener (an A-2026-0016 hatten praktisch alle längeren
  Langtexte mehrere `\n`, siehe dortige Zählung). Eine lückenlose Lösung (echtes Umbrechen mitten
  in einem Absatz) würde die von reportlab bereits umbrochenen Zeilen aus einem gelayouteten
  `Paragraph`-Objekt extrahieren (`Paragraph.wrap()` befüllt `blPara`/`lines`, aber als
  Low-Level-Fragmentliste, kein einfacher String je Zeile) -- bewusst verworfen: die Fragilität
  (reportlab-Versions-/Font-abhängige interne Datenstruktur, kein dokumentiertes öffentliches API
  dafür) steht in keinem Verhältnis zum Gewinn gegenüber der bereits deutlich wirksameren,
  einfachen `\n`-Aufteilung. Bewusst in Kauf genommen, kein Fehler -- falls in einem Jahr jemand
  fragt, warum eine bestimmte Position trotzdem noch am Stück umbricht: das ist der Grund.
- **`entry_to_dict()`s `employee_name` (Zeiterfassung) ist projektweit live, nicht nur im
  Einsatzbericht** (gefunden bei derselben 1.3.12-Prüfung): die "Erfasste Zeiten"-Tabelle im
  Einsatzbericht-PDF zeigt über `TimeEntry.employee` den AKTUELLEN Namen des Mitarbeiters --
  ebenso die neue Monteur-Meta-Zeile (`created_by_employee_name`, seit 1.3.11). Anders als die
  beiden anderen 1.3.12-Funde ist das aber keine für Einsatzberichte spezifische Lücke, sondern
  die etablierte, projektweite `TimeEntry`-Konvention (auch auf Rechnungen, in der Plantafel
  usw. immer live aufgelöst) -- ein Einfrieren nur für Einsatzberichte wäre eine neue Asymmetrie
  gegenüber jeder anderen Stelle, die `TimeEntry`/`Employee` genauso verwendet. Bewusst nicht
  behoben, gemeldet.
- **`Invoice.caseworker_employee_id` existiert, wird aber nirgends gesetzt** (gefunden bei der
  1.3.7-Planung, geprüft per projektweitem Grep): die Spalte ist da (FK auf `employees`), aber
  weder `_snapshot_order_fields()` noch sonst irgendeine Stelle kopiert sie beim Anlegen einer
  Rechnung aus `Order.caseworker_employee_id` -- sie bleibt in der Praxis immer `NULL`. `Order`
  trägt dieselbe Spalte und nutzt sie aktiv (z. B. löst `sign_report()` darüber den Empfänger der
  "Rechnung erstellen"-Aufgabe auf, siehe Abschnitt "Einsatzbericht"). Bei `Invoice` fehlt
  offenbar nur das Durchreichen aus dem Auftrag -- ob das ein vergessenes Feature oder absichtlich
  nie gebraucht wurde, ist nicht bekannt. Deshalb bewusst OHNE "Sachbearbeiter"-Zeile im neuen,
  gemeinsamen Kopfbereich der Rechnung (siehe dort) -- eine leere Zeile wäre schlechter als keine.
  Ein eigener, kleiner Punkt für später (Durchreichen beim Anlegen ergänzen, falls tatsächlich
  gewünscht), kein Teil der 1.3.7-Etappe.
- Roadmap für zurückgestellte Vorhaben wurde in einer früheren Sitzung als Datei
  `Roadmap_Zurueckgestellte_Vorhaben.md` erstellt und zum Download angeboten – **per Prüfung am
  09.09.2026 nicht im Projektverzeichnis vorhanden** (`Glob` über das ganze Projekt, kein
  Treffer). Falls sie noch irgendwo existiert, liegt sie außerhalb dieses Projektordners.
- **Redundanz zwischen Flachdach- und Gründach-Schichttypen** (seit 1.2.18, `RoofLayerType`,
  Migration `b8adafd0b997`): die 7 Schichten, die ein Gründach mit einem Flachdach gemeinsam
  hat (Traglage, Dampfsperre, Dämmung, Gefälledämmung, Trennlage, Abdichtung,
  Oberflächenschutz), existieren als ZWEI unabhängige Zeilensätze mit eigenen `key`-Werten
  (`flachdach_*` bzw. `gruendach_*`), nicht als eine gemeinsame, mehrfach zugeordnete Zeile –
  `RoofLayerType.roof_type` ist ein einzelnes Feld, kein Mehrfachbezug, und `roof_type IS NULL`
  hätte "gilt für jeden Dachtyp" bedeutet (ein Steildach hätte dann fälschlich auch
  Dampfsperre/Abdichtung angezeigt bekommen). Bewusst in Kauf genommen, aber bewusst NICHT
  automatisch synchron gehalten: wird einer der beiden Sätze in Einstellungen → Dachaufbau
  später umbenannt, die Optionsgruppe gewechselt oder die Dicke-Pflicht umgestellt, weicht die
  jeweils andere Kopie stillschweigend ab, ohne dass das an dieser Stelle auffällt. Nicht
  angegangen, solange es nicht stört. Saubere spätere Lösung, falls doch: eine Mehrfachzuordnung
  (Zwischentabelle `roof_layer_type_roof_types`) statt der einzelnen `roof_type`-Spalte.
- **Toter Datenbestand: alte `roof_component_types`-Optionsgruppe** (seit 1.2.19): mit der
  Hochstufung zu `RoofComponentType` (echte Tabelle) wurde `roof_component_types` aus
  `DEFAULT_OPTION_GROUPS` entfernt. Bereits vorhandene `SettingOptionGroup`/`SettingOption`-
  Zeilen einer laufenden Installation bleiben dabei unangetastet in der DB stehen (nichts liest
  sie mehr) statt gelöscht zu werden. Reine Aufräum-Idee für später, kein Fehler.
- **Jinja-Globals `get_theme()`/`is_module_enabled()`/`sidebar_logo_url()`/
  `sidebar_logo_height_px()` (letztere beide seit 1.3.38/1.3.39) umgehen `get_db()`**
  (`app/routers/pages.py`): alle vier öffnen bei jedem Template-Rendern selbst eine
  `SessionLocal()`-Verbindung zur echten Datenbankdatei, statt die per `get_db()` injizierte (und
  in Tests per `app.dependency_overrides` austauschbare) Session zu verwenden – sie sind damit
  nicht auf eine Test-Session umstellbar. Seit 1.2.20 (siehe `tests/test_v218_template_rendering.py`)
  löst das der erste Test aus, der praktisch jede Seite rendert (`_sidebar.html` bindet
  `is_module_enabled()` ein, jede Seite bindet `_sidebar.html` ein) – für einen reinen Lesetest
  unschädlich, aber ein Vorbild, dem ein künftiger, auch SCHREIBENDER Test nicht folgen darf.
  Geprüft, ob sich das mit wenig Aufwand beheben lässt: nein – `is_module_enabled('wartungen')`
  wird als Jinja-Global mit nur einem Argument in sieben Vorlagen aufgerufen; eine echte
  Umstellung müsste entweder jeden dieser Aufrufe um einen `db`/`request`-Parameter erweitern und
  jeden der rund 30 Seiten-Router in `app/routers/pages.py` um `db: Session = Depends(get_db)`
  plus passenden Kontext-Eintrag ergänzen, oder einen neuen contextvar-basierten Mechanismus
  einführen, der sowohl in der echten Middleware als auch in `router_test_client` verdrahtet
  werden müsste – beides kein kleiner Fix mehr, bleibt daher im Merkzettel. **Seit 1.3.42
  unabhängig davon abgesichert**: alle vier fangen jetzt jede Ausnahme ab und fallen auf einen
  sicheren Wert zurück (siehe "Produktivbetrieb" → "Zwei Vorfälle beim Ausliefern von
  1.3.38–1.3.41" oben) – das löst NICHT die hier beschriebene Test-Umstellbarkeit, aber das
  eigentlich gefährlichere Problem (eine echte Ausnahme reißt jede Seite mit sich, einschließlich
  der Anmeldeseite) ist damit unabhängig von dieser offenen Baustelle geschlossen.
- **`onchange`-only-Autosave-Muster (Blur-Abhängigkeit) existiert an weiteren Stellen**: bei der
  Behebung des 1.2.19-Datenverlusts in der Dachaufbau-Schichtenliste (siehe dort) wurde der
  neue, geteilte `_debounce.html`-Helfer bewusst nur dort UND beim Pflicht-Freitextfeld in
  `service_reports.html` angewendet, wo eine Blur-Abhängigkeit tatsächlich gemeldet war bzw.
  eine Unterschrift blockieren konnte. `measured_value`/`quantity`-Prüfpunkte in
  `service_reports.html` und potenziell weitere Autosave-Felder auf anderen Seiten haben
  dieselbe Lücke, sind aber nicht Teil dieser Iteration – der Helfer steht für eine künftige
  Behebung an Ort und Stelle bereits bereit, keine zweite Implementierung nötig.
- **Keine Doppel-Abrechnungs-Sperre bei "Rechnung aus Aufwand"** (seit 1.2.2 bei `TimeEntry`,
  jetzt seit 1.2.23 ebenso bei `ServiceReportMaterial` -- bewusst geprüft und bewusst NICHT
  behoben, siehe Rückfrage in der 1.2.23-Planung): `TimeEntry` trägt kein `invoiced`/
  `invoice_id`-Feld, `create_invoice_from_time_entries()` filtert nur `status="booked"` bzw.
  (Material) `ServiceReport.status="unterschrieben"` -- beides ohne jede Rücksicht darauf, ob
  dieselben Zeilen bereits in einer FRÜHEREN Rechnung aus Aufwand abgerechnet wurden. Ein
  zweiter Rechnungslauf für denselben Auftrag würde alle bereits abgerechneten Zeit-/
  Materialzeilen erneut als Position auf einer neuen Rechnung anlegen (volle Duplizierung, kein
  Fehler, keine Warnung). Material bekommt hier ausdrücklich dieselbe (Nicht-)Behandlung wie
  Zeit, keine neue Asymmetrie zwischen beiden. Saubere spätere Lösung, falls das stört: ein
  `invoiced_at`-Stempel auf beiden Tabellen plus eine Entscheidung, was ein zweiter Lauf tun
  soll (nur seit dem letzten Lauf Neues abrechnen? warnen? ablehnen?) -- eine eigene, bisher nie
  angefragte Funktionserweiterung, kein kleiner Fix.
- **Feierabend-Abmeldung deckt keinen bereits offenen Berichtstab ab** (seit 1.3.0, siehe
  Abschnitt "Monteursansicht"): `MobileSettings.shift_end_time` wird nur an den beiden mobilen
  Einstiegspunkten geprüft (`GET /vor-ort`-Seitenaufruf, `GET /api/field-view/today`), bewusst
  NICHT in den gemeinsamen Formular-Endpunkten (`PUT /api/inspection-items/{id}`,
  `POST /api/service-reports/{id}/sign` usw.) – das würde auch Schreibtisch-Nutzer treffen, die
  spät noch etwas nachtragen. Ein Monteur, der einen Bericht vor der Feierabend-Grenze geöffnet
  hat und danach ohne Neuladen weiterarbeitet, wird dadurch nicht unterbrochen. Deckt genau den
  beschriebenen Fall ab (niemand bucht nachts unter fremdem Namen auf einem unbeaufsichtigt
  eingeloggten Fahrzeug-Tablet), nicht jede denkbare Session-Timeout-Variante. Keine kleine
  Behebung ohne echten Bedarf – ein zeitgesteuerter serverseitiger Zwangs-Logout mitten in der
  Bearbeitung wäre eine neue, bisher nirgends im Projekt vorhandene Art von Eingriff.
Der frühere Eintrag "Randeinstellungen der Einstellungsseite betreffen 'quote' nicht" ist mit
1.3.20 vollständig aufgelöst: "quote" nimmt jetzt am "default"-Rückfall teil, siehe Abschnitt
"Aufräumen nach dem PDF-Umbau" unten.
