# Chronik: "Neu seit 1.1.0" bis "Neu seit 1.6.0"

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

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
- Neu seit 1.3.46: **Echter Nebenbefund aus Schritt 2 behoben, vor Schritt 3 (Suche).** Auf einem
  schmalen Bildschirm ließ sich die Off-Canvas-Sidebar überhaupt nicht öffnen -- ihr einziger
  Umschalter (`#appSidebarToggle`) steckte selbst innerhalb des `<aside>`, das im geschlossenen
  Zustand unsichtbar ist. Neuer Umschalter `#appTopbarMenuBtn` links in der Topbar (vor dem für
  Schritt 3 reservierten Suchen-Platzhalter), erscheint nur unterhalb des Umbruchpunkts, öffnet/
  schließt dieselbe Off-Canvas-Sidebar. `#appSidebarToggle` blendet sich dort im Gegenzug
  vollständig aus (kein Kollabieren im Desktop-Sinn auf Mobilgeräten, nur Auf/Zu -- zwei
  Bedienungen für dieselbe Aktion nebeneinander wären verwirrender gewesen). Details im
  Abschnitt "Umgestaltung der Sidebar" → "Nachtrag zu Schritt 2" unten.
- Neu seit 1.3.47: **Serverseitige Anmeldeschranke für Seiten.** Auf Nutzeranfrage geprüft:
  bisher rendierte JEDE Seite (auch `/`, `/tasks`, `/settings`) ihr Gerüst unabhängig vom
  Anmeldestatus -- keine Umleitung, kein Fehler, nur clientseitig ein Login-Formular im
  Sidebar-Fußbereich. Jetzt: ohne Anmeldung führt jede Seite (außer `/login`/`/health`/
  `/manifest.json`, plus die bestehende Bootstrap-Ausnahme) auf `/login`, `/login` bei
  bestehender Anmeldung leitet aufs Dashboard weiter (bzw. `/account` bei ausstehendem
  zweitem Faktor) statt die Maske erneut zu zeigen. `/` mit Anmeldung zeigte das Dashboard
  bereits korrekt (keine Änderung nötig). Auf Nachfrage ergänzt, Kosten minimal, da
  `login.html` es bereits liest: die Umleitung hängt `?next=<Pfad>` an, dieselbe Konvention
  wie die bestehenden Abmelden-Links -- nach dem Anmelden geht es zur ursprünglich
  gewünschten Seite, nicht immer zum Rückfall `/projects`. Details im neuen Abschnitt
  "Serverseitige Anmeldeschranke für Seiten" unten.
- Neu seit 1.3.48: **Zwei reale Fehler aus 1.3.47, auf dem Produktivserver gefunden.** (1)
  `/login` leitete trotz bestehender Anmeldung nicht auf `next` weiter (immer aufs
  Dashboard) -- behoben, plus die eigentliche Ursache des konkret gemeldeten Symptoms
  ("Anmeldemaske erscheint erneut"): `account.html`s Link "Zur Startseite" sprang bei
  vorhandenem `document.referrer` per `history.back()` zurück auf die während der
  Zwei-Faktor-Pflicht durchlaufene, noch unangemeldete `/login`-Ansicht -- teils direkt aus
  dem Bfcache, ganz ohne Serveranfrage. Jetzt ein einfacher `href="/"`. (2) Nach Bestätigung
  des Codes landete man auf `/account` statt auf dem eigentlichen Ziel --
  `verifyCode()` leitet jetzt auf `next`/das Dashboard weiter, statt nur die Kontoseite neu
  zu zeichnen; die Ersteinrichtung bleibt bewusst auf `/account` (Wiederherstellungscodes
  müssen erst gesehen werden). Details im Abschnitt "Serverseitige Anmeldeschranke für
  Seiten" → "Fehlerbehebung" unten.
- Neu seit 1.3.49: **Aufräumen im Fußbereich der Sidebar.** Benutzername, "Mein Konto" und
  "Abmelden" standen dort noch, obwohl alle drei bereits seit Schritt 2 (1.3.45) über den
  Kontoknopf der Topbar erreichbar sind -- entfernt, der untere Bereich zeigt jetzt nur noch
  die beiden Schaltflächen (Hell/Dunkel, Ein-/Ausklappen) und die Version. `#appSidebarFoot`
  bleibt als Element bestehen (rendert aber jetzt immer leer), da es weiterhin fürs
  clientseitige Wiederanmelde-Formular bei einer während des Browsens ablaufenden Sitzung
  gebraucht wird -- eine neue `:empty{padding:0}`-Regel verhindert dabei eine unnötig
  gepolsterte Leerstelle. Toter Code (escHtml/bindLogout/LOGOUT_ICON) entfernt statt nur
  ausgeblendet. `/vor-ort` unangetastet (eigener, unabhängiger Abmelde-Weg). Nebenbefund: der
  entfernte "Mein Konto"-Link hatte keine eigene CSS-Regel (blauer Standardlink statt
  Design-System) -- auf Nachfrage vier weitere, unabhängige Fälle desselben Musters anderswo
  gefunden und gemeldet (`account.html`, `settings.html`, `service_reports.html`,
  `work_preparation.html`), Behebung bewusst zurückgestellt. Details im Abschnitt
  "Umgestaltung der Sidebar" → "Aufräumen im Fußbereich" unten.
- Neu seit 1.3.50: **Die vier weiteren Funde aus 1.3.49 behoben.** Jeweils eine allgemeine
  `a{color:var(--accent)}`-Regel im eigenen `<style>`-Block der betroffenen Datei -- dasselbe,
  in `login.html` bereits etablierte Muster, keine HTML-Umstrukturierung. Details im
  Abschnitt "Umgestaltung der Sidebar" → "Nachtrag (seit 1.3.50)" unten.
- Neu seit 1.3.51: **Rechtekonzept, Etappe 1+2 -- Fundament, Standardverweigerung, drei
  Beispieldateien.** Vorbereitung für die kommenden Monteurskonten (Schritt 4 der Suche, siehe
  eigener, ausführlicher Abschnitt "Rechtekonzept" unten). Aus zwei Rollen (`admin`/`user`)
  werden drei (`admin`/`office`/`field`), zentral geprüft über die neue
  `app/permissions.py::require_role()` -- `app/deps.py::require_admin()` bleibt unverändert
  bestehen (deckt sich mit `require_role("admin")`), Bestandskonten bleiben unverändert
  Administratoren. **Standardverweigerung statt Positivliste**: ein neuer, automatisierter Test
  geht jede registrierte `/api/`-Route durch und benennt jede ohne erkennbare Rollenprüfung --
  ein vergessener Endpunkt fällt dadurch beim nächsten vollständigen Testlauf auf, nicht erst
  durch Zufall (neue Regel 11). Als Nachweis bereits umgestellt: `customers.py`/`invoices.py`/
  `reminders.py` (Büro+Admin, Monteur ausgeschlossen, keine Objekt-Filterung nötig). Dabei
  zusätzlich: `Property` bekommt Zugang/Ansprechpartner-vor-Ort-Felder samt einem neuen,
  auftragsbezogenen Lesepfad für den Einsatzbericht; geprüft, ob Aufgaben heute je einem
  Monteur zugewiesen werden (nein) -- Aufgaben bleiben für diese Rolle vorerst gesperrt;
  `users.html` bekommt eine sichere Voreinstellung ("Monteur" statt eines bare "Benutzer") und
  eine Bestätigungsabfrage beim Anlegen ohne ausdrücklich gewählte Rolle. Die übrigen, noch
  unklassifizierten Endpunkte sind die konkrete Checkliste für die nächste, noch zu bestätigende
  Etappe -- bewusst noch nicht angefasst.
- Neu seit 1.3.52: **Rechtekonzept, Etappe 3 -- der riskante Batch, nach Risiko statt Alphabet
  geordnet.** Auf Vorgabe zuerst alles, was Geld, Preise oder Personendaten zeigt: `settings.py`,
  `document_layout.py`, `document_email_templates.py`, `payment_terms.py`, `tax_keys.py`,
  `changelog.py`, `catalogs.py`, `labor_rate.py`, `imports.py`, `audit.py`, `employees.py`
  (behebt den ursprünglichen Suche-Fund `hourly_wage`/`effective_hourly_wage`/
  `annual_gross_wage`), `services.py`, `users.py` (nur die Benutzerliste), `materials.py` (Suche
  bleibt für Monteure offen, Verwaltung nicht -- der dabei zunächst offen gebliebene Fund, dass
  die Suche `purchase_price` mitliefert, ist seit 1.3.53 behoben, siehe dort). Dazu, wie in 1.3.51 vorgeschlagen und vom Nutzer
  bestätigt: **Aufgaben** (`app/routers/tasks.py`/`task_columns.py`, dazu die beiden
  `/api/tasks/{task_id}/finding`- und `.../create-follow-up-project`-Endpunkte, die aus
  historischen Gründen in `app/routers/findings.py` liegen) auf Büro+Admin umgestellt, Monteur
  ausgeschlossen -- siehe eigener Abschnitt "Aufgaben" unten für den dabei gefundenen, bewusst
  nicht behobenen Eigentümerschafts-Fund bei PUT/DELETE/archive/unarchive. Die übrigen Endpunkte
  von `findings.py` (Mängel-Workflow während eines Einsatzberichts, von Monteuren selbst
  bedient) bleiben bewusst unklassifiziert -- gehören zur nächsten Etappe, nicht zu dieser.
  Neuer Jinja-Global `can(current_user, *roles)` (`app/routers/pages.py`) löst lokale
  `current_user.role == '...'`-Vergleiche in `_sidebar.html` ab -- genau das Muster, das bei
  `build_customer_and_meta_block()` zu drei divergierenden Varianten geführt hat. Der
  Vollständigkeits-Audit-Test (seit 1.3.51) sinkt dadurch von 243 auf 230 unklassifizierte
  Endpunkte -- der Rest (überwiegend risikoärmer: Objekte, Aufträge, Angebote, Projekte,
  Einsatzberichte, Zeiterfassung, Plantafel u. a.) ist die nächste, separate Etappe, wie
  ausdrücklich vom Nutzer verlangt ("erst die riskanten, dann berichten, dann die übrigen").
- Neu seit 1.3.53: **Rechtekonzept -- Preisleck bei `GET /api/materials` behoben, zwei weitere
  echte Funde beim angefragten Nachziehen desselben Musters.** `field` bekommt seither
  `MaterialSearchOut` (nur `id`/`article_number`/`name`/`unit`) statt der vollen
  `MaterialCatalogOut` (`purchase_price`/`price_basis`) -- ein Endpunkt, rollenabhängige Antwort
  (`response_model=list[MaterialCatalogOut] | list[MaterialSearchOut]`), keine zweite Route.
  Dieselbe Prüfung bei allen bewusst für `field` offenen Endpunkten ergab zwei weitere Funde:
  `GET /api/orders/{order_id}/property` (seit 1.3.51) lieferte die volle `PropertyOut` inkl.
  `notes`/`customer_id` -- genau der Kundenkontext, den der Endpunkt laut eigener Begründung
  nicht zeigen sollte, jetzt `PropertyAccessOut`. `GET /api/employees` war seit der 1.3.52-Sperre
  für `field` komplett unerreichbar (403), obwohl `service_reports.html` darüber sein
  Mitarbeiter-Auswahlfeld für die Zeitbuchung füllt (durch `.catch(()=>[])` unbemerkt leer
  geblieben) -- jetzt wieder erreichbar, liefert `field` aber `EmployeeNameOut` (nur
  `id`/`first_name`/`last_name`/`active`) statt der vollen `EmployeeOut`. Bewusst nicht
  behoben: `GET /api/orders/{id}` liefert weiterhin die volle, bepreiste LV an jede Rolle --
  das braucht die noch nicht gebaute Objekt-Filterung (Etappe 3), siehe CLAUDE.md
  "Rechtekonzept" und CHANGELOG.md für die volle Begründung.
- Neu seit 1.3.54: **Rechtekonzept, Rest-Etappe Teil A -- 164 weitere, monteur-unabhängige
  Endpunkte klassifiziert.** `quotes.py`/`planning.py`/`maintenance_contracts.py`/`projects.py`/
  `resource_planning.py` (Teams/Ressourcen/Lieferanten)/`roof_areas.py`/`properties.py`/
  `inquiries.py`/`customer_documents.py`/`project_documents.py`/`quick_service_orders.py` auf
  Büro+Admin umgestellt -- vorher geprüft, dass keiner ihrer Endpunkte von
  `service_reports.html`/`vor_ort.html`/`_mobile_header.html` aufgerufen wird. Drei Dateien
  bekamen stattdessen eine feinere, rollenoffene Behandlung, weil sie bereits bestehende
  Selbstbedienungs-Endpunkte mit eigener Eigentümerschafts-Filterung enthalten (Abwesenheitsanträge,
  das "Meine Aufgaben"-Widget der Arbeitsvorbereitung, das eigene Dashboard-Layout, der
  Modul-Ein/Aus-Zustand) -- jede Rolle darf diese lesen/für sich selbst schreiben, siehe
  CHANGELOG.md für die Einzelheiten. Der Audit-Test sinkt von 230 auf 66 unklassifizierte
  Endpunkte -- Teil B (Aufträge/Einsatzberichte/Mängel/Prüfvorlagen/Zeiterfassung) bleibt bewusst
  offen, bis die Objekt-Filterung (Etappe 3) gebaut ist.
- Neu seit 1.3.55: **Rechtekonzept, Etappe 3 + Rest-Etappe Teil B -- Objekt-Filterung für
  Monteure, Audit-Test bei null.** `app/orders.py::field_may_access_order()` ist die EINE
  Definition, wann ein Monteur einen Auftrag sehen darf (Team-Besetzung an der AV, Einzelzuweisung
  an der AV, eigener Bericht -- der dritte Weg ist ein echter Fund, ohne ihn wäre ein begonnener
  Bericht nach einer Umplanung unerreichbar, obwohl `/vor-ort` ihn weiter zeigt); die Zeiterfassung
  (`employee_assigned_order_ids()`) leitet seither auf dieselbe Definition weiter statt eine
  eigene zu tragen. Die 65 verbleibenden Endpunkte (`orders.py`/`service_reports.py`/`findings.py`/
  `inspection_templates.py`/`time_tracking.py`) sind klassifiziert, `GET /api/orders/{id}` liefert
  Monteuren ein preisfreies `OrderFieldAccessOut`, der Audit-Test ist ab jetzt ein harter Test
  (`xfail` entfernt, null Ausnahmen jenseits der neun begründeten `ROLE_AUDIT_EXEMPT`-Einträge).
  Geprüft, kein Fund: `?order_id=` in der Zeiterfassung leakte nie Kollegen-Buchungen an Monteure.
  Nebenbefund (nicht behoben, siehe "Bekannte, bewusst offene Punkte"): dieselbe Eingrenzung trifft
  auch `office`-Konten mit Mitarbeiterverknüpfung in `order.html`/`project_folder.html`. Details im
  Abschnitt "Rechtekonzept" → "Objekt-Filterung" unten.
- Neu seit 1.3.56: **Rechtekonzept, Nachtrag zu Teil B nach Betreiber-Rückmeldung.** Vier Punkte:
  (1) `POST /api/maintenance-contracts/{id}/perform-maintenance` ("Wartung durchführen") ist für
  jede Rolle offen, der vorbereitete Bericht trägt den Anfragenden als Ersteller -- ein Monteur
  muss vor Ort eine ungeplante Wartung starten können, und der eigene Bericht ist dann sein
  Zugriffsweg auf den neuen Auftrag (Vertragsdaten selbst bleiben Büro; ein `/vor-ort`-Einstieg
  dazu fehlt noch). (2) Die Wartungshistorie liefert `field` ein reduziertes Modell
  (`ServiceReportHistoryOut`: Datum, Berichtstyp, Monteur, Prüfergebnisse, Mängel mit Status),
  `service_reports.html` zeigt sie inline statt des für fremde Berichte gesperrten PDF-Links.
  (3) Büro sieht alle Zeitbuchungen -- die Eingrenzung in `GET /api/time-entries` gilt nur noch
  für `field`, der 1.3.55-Nebenbefund ist behoben. (4) `sign_report()` geprüft: Aufgabe und
  Vertragsfortschreibung sind In-Process-Aufrufe ohne Rollenprüfung, per Ende-zu-Ende-Test
  belegt. Wortwahl angeglichen: zwei Wege (Planungsbezug in zwei Formen ODER eigener Bericht),
  kein dritter. Details im Abschnitt "Rechtekonzept" → "Objekt-Filterung" unten.
- Neu seit 1.3.57: **Rechtekonzept, Seiten-Klassifizierung.** Dieselbe Standardverweigerung wie
  bei der API, jetzt auch für die Seiten-Routen selbst (`app/routers/pages.py`) -- vorher
  rendierte jede Seite ihr Gerüst für jede Rolle, erst der API-Aufruf dahinter antwortete 403
  (kein Datenleck, aber keine echte Sperre). `require_role()` wiederverwendet (keine neue
  Dependency-Art), vier Seiten für `field` (`/account`, `/vor-ort`, `/time-tracking`,
  `/orders/{id}/service-reports`), jede andere Büro/Admin; `/users` bootstrap-aware wie
  `POST /api/users`. Ein neuer Exception-Handler in `app/main.py` zeigt bei einem 403 auf einer
  Seiten-Route `access_denied.html` statt roher JSON, "Zur Startseite" führt rollenabhängig
  (`/vor-ort` für `field`, sonst `/`, `/users` im anonymen Bootstrap-Fall). Login-Landing ohne
  `next` dafür an zwei Stellen auf `/vor-ort` für `field` korrigiert (`login_page()`,
  `login.html`). Der Audit-Test deckt jetzt Seiten UND API ab, beide bei null. Details im
  Abschnitt "Rechtekonzept" → "Seiten-Klassifizierung" unten.
- Neu seit 1.3.58: **Rechtekonzept, Nachtrag -- Vertragsfinder auf `/vor-ort`.** Letzte
  Seiten-Klassifizierungs-Lücke geschlossen: ein Monteur konnte "Wartung durchführen" bisher nur
  von der Büro-Vertragsseite aus starten, die für ihn gesperrt ist. Neue Karte "Wartungen an
  meinen Objekten" -- zeigt die Objekte, an denen er über die Arbeitsvorbereitung aktuell oder in
  Kürze (±14 Tage um eine echte `PlanningSlot`-Terminierung, `WorkPreparation.planned_start/
  planned_end` als Rückfall) zugeordnet ist, mit allen Wartungsverträgen des Objekts, fällige
  hervorgehoben. Vorher geprüft und bewusst gegen eine Kombination mit
  `WorkPreparation.status` entschieden (Feld ist zwar über die AV-Oberfläche änderbar, aber die
  reale Datenbank hat dafür nur eine einzige Zeile -- zu dünn für ein Urteil -- und "offen ODER
  Zeitfenster" hätte das Altlasten-Risiko, das das Zeitfenster gerade vermeiden soll, an anderer
  Stelle wieder eingeführt). Reduziertes Schema (kein Kundennummer, keine Adresse über den Ort
  hinaus), Karte blendet bei fehlender Objektzuordnung nur einen ruhigen Hinweis ein, nie eine
  leere Fläche. Details im Abschnitt "Rechtekonzept" → "Vertragsfinder auf /mobil" unten.
- Neu seit 1.3.59: **Rechtekonzept, zwei Funde aus einem Sicherheitstest behoben.** Ein
  adversarialer Test gegen eine isolierte Testinstanz (eigene, temporäre Datenbank, nie gegen
  die echte `dachkonzepte_erp.db`) fand zwei echte Lücken, beide geschlossen, ein zweiter
  Durchlauf desselben Tests bestätigt: null "durchgelassen". (1) Ein Monteur mit Zugriff auf
  einen Mehrpersonen-Auftrag konnte jeden Bericht eines Kollegen darauf lesen, ändern, löschen
  und signieren -- `require_field_order_access()` prüfte nur den Auftrag, nie den Bericht selbst.
  Neue `require_field_report_ownership()` (`app/routers/orders.py`) verlangt für jeden Schreib-/
  Detailzugriff auf einen konkreten Bericht (PUT/DELETE/sign, Prüfpunkte, Fotos, Material,
  Mängel, PDF) den Ersteller -- eine bewusste betriebliche Festlegung (jeder Monteur schreibt
  seinen eigenen Bericht), keine technische Annahme. Die Berichtsliste selbst bleibt für jeden
  mit Auftragszugriff sichtbar, aber pro Bericht: der eigene voll, jeder fremde im reduzierten
  Schema der Wartungshistorie (`list_reports_for_field()`). (2) "Wartung durchführen" prüfte für
  Monteure keine Zuordnung zum Vertrag -- eine geratene, fortlaufende ID legte einen echten
  Auftrag unter einem fremden Kunden an. `field_may_perform_maintenance()` zieht jetzt dieselbe
  Grenze wie der Vertragsfinder (`list_field_relevant_property_ids()`). Die frühere Einstufung
  dieser zweiten Lücke ("kein Datenleck, so akzeptiert") ist damit überholt und aus CLAUDE.md
  entfernt. Details im Abschnitt "Rechtekonzept" → "Berichts-Eigentümerschaft" bzw. "Fund:
  fremde Wartung per geratener Vertrags-ID" unten.
- Neu seit 1.3.60: **Zeiterfassung für Monteure -- reduzierte Ansicht statt der vollen,
  sidebar-getragenen Seite.** `/time-tracking` rendert seit dieser Version rollenbewusst zwei
  verschiedene Vorlagen unter derselben URL: `time_tracking_field.html` (neu, im Stil von
  `_mobile_header.html`/`vor_ort.html`, keine Gruppenbuchung, keine Mitarbeiterauswahl) für
  `field`, unverändert `time_tracking.html` für Büro/Admin -- die Weiche hängt dafür bewusst an
  der Rolle (`app/routers/pages.py::time_tracking_page()`), nicht an einer zweiten Route, damit
  alle drei bestehenden Linkquellen (`_sidebar.html`, `_mobile_header.html`,
  `service_reports.html`s `#timeLink`) unverändert bleiben konnten und die volle Seite für
  `field` strukturell unerreichbar wird, unabhängig vom Weg dorthin. Die Auftragsauswahl der
  reduzierten Nachtrag-/Schnellstart-Maske nutzt ein neues `list_field_bookable_order_ids()`
  (`app/planning.py`, dasselbe ±14-Tage-Fenster wie der 1.3.58-Wartungsfinder) -- dabei ein
  echter Fund: ein per "Wartung durchführen" gestarteter, ungeplanter Auftrag hat gar keine
  `WorkPreparation` und wäre in jedem Zeitfenster unsichtbar geblieben, unabhängig von dessen
  Größe; behoben durch eine ungefensterte Ergänzung um selbst angelegte Berichte (derselbe zweite
  Weg wie `field_may_access_order()`). Gruppenbuchung ist für Monteure vollständig entfernt
  (Betreibervorgabe: "ein Monteur bucht nur für sich") -- ob künftig ein Kolonnenführer
  gruppenbuchen darf, ist als offener Punkt festgehalten, siehe „Bekannte, bewusst offene
  Punkte". Details im Abschnitt "Rechtekonzept" → "Zeiterfassung für Monteure" unten.
- Neu seit 1.3.61: **fünf weitere, rollenbezogene Anpassungen an der Monteursansicht.** (1)
  Umbenennung: `/vor-ort` → `/mobil`, Titel "DACHKONZEPTE GmbH - Mobil", `/vor-ort` entfällt
  ersatzlos (alle drei tatsächlichen Linkquellen geprüft und mitgezogen: `mobile_manifest.py`,
  `login.html`, `default_home_page_for_role()`). (2) `GET /` leitet für `field` jetzt auf `/mobil`
  weiter statt mit 403 zu sperren -- die Rolle entscheidet das Ziel, nicht der Weg, deckt auch
  einen von Hand eingetippten Aufruf ab. (3) Tätigkeit im Nachtrag UND im Schnellstart ergänzt --
  **Prämisse korrigiert**: der Nutzer nahm an, der Schnellstart habe das Feld schon, tatsächlich
  hatte KEINS von beiden es (nur die Zeitart-Kacheln), transparent gemeldet statt stillschweigend
  einseitig aufgelöst. (4) Eigener Stundenzettel (`/mobil/stundenzettel`, neuer Renderer
  `app/field_timesheet_pdf.py`, PDF über den gemeinsamen Rahmen mit Briefkopf, neuer, komplett
  neuer PDF-Dokumenttyp `"field_timesheet"` -- fällt ohne eigene Zeile automatisch auf den
  geteilten "default"-Satz zurück, keine Migration nötig) -- der bestehende, admin-only
  Büro-Stundenzettel (`app/time_backoffice.py`) diente nur inhaltlich als Vorlage, nutzt selbst
  nie den gemeinsamen Rahmen. (5) "Meine kommenden Termine" -- neue Karte auf `/mobil`
  (`list_upcoming_assignments_for_employee()`, `app/planning.py`, ±30 Tage, dieselbe Zuordnung wie
  die Tagesliste, nur über ein Zeitfenster statt eines Tages), reine Leseansicht ohne Zugriff auf
  die Plantafel selbst. Abschließender, vom Nutzer verlangter Angriffstest bestätigt: volle
  Plantafel (Seite und API), fremde Stunden und fremde Plantafel-Einträge bleiben für `field`
  gesperrt -- null "durchgelassen". Details im Abschnitt "Rechtekonzept" → "Fünf weitere
  Anpassungen an der Monteursansicht" unten.
- Neu seit 1.3.62: **Dateiablage je Objekt, Schritt 1 -- Kategorie-Stammdaten, ausdrücklich nur
  das Fundament.** Neue echte Stammdatentabelle `DocumentCategory` (`app/document_categories.py`)
  löst die bisherige freie Optionsgruppe `project_document_categories` ab -- dieselbe Hochstufung
  wie bei `RoofComponentType`/`RoofLayerType`. Acht Kategorien wortgleich übernommen, zwei davon
  ("Rechnungen / Belege", "Verträge / Freigaben") als sensibel markiert. **Zwei unabhängige
  Schlösser gegen "sensible Kategorie für Monteure sichtbar"**: (1) `is_sensitive` kann, einmal
  gesetzt, nie wieder auf `False` zurückgesetzt werden, und die Kombination `is_sensitive=True` +
  `is_field_visible=True` ist in `create_category()`/`update_category()` immer verboten; (2) eine
  feste, im Code verankerte Sperrliste (`HARD_LOCKED_CATEGORY_KEYS`), die `field_may_see_category()`
  unabhängig von diesen beiden Feldern prüft -- bleibt selbst bei einer direkten
  Datenbankmanipulation wirksam, per Test belegt. Neue Spalte `category_id` (FK, zusätzlich zur
  bestehenden Freitextspalte `category`) auf `CustomerDocument`/`ProjectDocument`, Migration
  `9137945e8785` befüllt sie aus dem Bestand (Regel 1: nullable anlegen, backfillen, erst danach
  NOT NULL) -- gegen die echte Datenbank geprüft: `customer_documents` leer, `project_documents`
  eine Zeile mit einem exakten Treffer ("Pläne"), kein unklassifizierbarer String. Dabei ein
  echter, über die vier bereits angepassten Upload-/Update-Endpunkte hinausgehender Fund: der
  Lieferschein-Upload in `app/routers/work_preparation.py` legt ebenfalls `ProjectDocument`-Zeilen
  an und hätte ohne dieselbe Korrektur in Produktion mit einem `IntegrityError` fehlgeschlagen --
  behoben. Neuer Einstellungen-Abschnitt "Dokumentkategorien" (Büro/Admin, kein Löschen in dieser
  Runde). **Bewusst NICHT Teil dieser Version**: die mobile Objektansicht (zusammengeführte
  Dokumente aller nicht archivierten Projekte eines Objekts) und die geteilte, feldbegrenzte Suche
  -- beides wartet auf die ausdrückliche Bestätigung der hier gebauten Grundlage. Details im neuen
  Abschnitt "Dateiablage je Objekt" unten.
- Neu seit 1.3.63: **Dateiablage je Objekt, Schritt 2 -- die mobile Objektansicht.** Neue Tabelle
  `PropertyDocument` (eigene, objektgebundene Uploads eines Monteurs -- bewusst objektbezogen
  statt einem Sammelprojekt je Objekt, ein spontaner Einsatz hat oft kein Projekt). Neue Seite
  `/mobil/objekt/{property_id}` (in dieser Runde noch ohne Suche, nur über eine bekannte
  Objekt-ID) zeigt Objektname/Adresse (Google-Maps-Link), Ansprechpartner (`tel:`-Link),
  Zugangshinweise, eine zusammengeführte, nach Kategorie gruppierte Dokumentliste (eigene
  Objekt-Uploads PLUS alle nicht archivierten Projekte des Objekts), eigene Uploads (Bilder
  verkleinert wie 1.2.17) und frühere Wartungsberichte im reduzierten Schema. **Ab hier gilt eine
  ANDERE Regel als sonst im Rechtekonzept**: ein Monteur erreicht JEDES Objekt über seine ID,
  nicht nur die eigenen -- die Sperre sitzt ausschließlich im Inhalt (harmlose Objektfelder,
  `field_may_see_category()` bei jeder Dokumentanzeige UND erneut am Datei-Ausliefer-Endpunkt,
  reduziertes Wartungshistorie-Schema). Büro sieht dieselbe Dokumentliste (ungefiltert) über
  einen neuen Abschnitt auf `property.html`. 15 neue Angriffstests, null "durchgelassen". Details
  im Abschnitt "Dateiablage je Objekt" unten.
- Neu seit 1.3.64: **Dateiablage je Objekt, Schritt 3 -- die geteilte Suche als Einstieg,
  letzter Schritt der Monteurs-Erweiterung.** Neue, geteilte Kernfunktion (`app/search.py`) --
  die Büro-Suche existiert weiterhin nicht (nur Befund), aber die Datei ist bereits als Kern
  angelegt, den eine künftige Büro-Suche um weitere Datensatzarten erweitert statt sie zu
  ersetzen. Sucht Objekte nach Name/Straße/PLZ/Ort und Kundenname, neuer Endpunkt
  `GET /api/field-view/properties/search` liefert dabei UNABHÄNGIG vom Aufrufer immer nur die
  drei harmlosen Felder (`id`/`name`/`city`) -- die Feldbegrenzung sitzt serverseitig, an der
  Rolle, nicht an der URL. Suchfeld auf `/mobil` mit 300ms-Debounce, Vorschlagsliste führt direkt
  zu `/mobil/objekt/{id}`. Index-Frage empirisch geprüft (nicht nur angenommen): ein
  gewöhnlicher B-Baum-Index hilft einer Substring-Suche nachweislich nicht (`EXPLAIN QUERY PLAN`
  zeigt `SCAN` selbst bei einem bereits indizierten Feld) -- keine neue Migration. 12 neue
  Angriffstests, null "durchgelassen". Details im Abschnitt "Dateiablage je Objekt" unten.
- Neu seit 1.3.65: **Zwei Anpassungen an der Monteurs-Suche, nach dem ersten Einsatz
  gemeldet.** (1) Kundenname als viertes, bewusst erlaubtes Feld in den Vorschlägen
  (`PropertySearchHitOut.customer_name`) -- ein Objekt ist ohne Kunde schwer einzuordnen,
  besonders bei mehreren Objekten desselben Kunden; nicht sensibel, ein Monteur kennt den Kunden
  ohnehin. Kundennummer/interne Notiz/volle Adresse/alles Finanzielle bleiben weiterhin gesperrt,
  der Angriffstest aus 1.3.64 wurde entsprechend angepasst (weiterhin 12 Tests). (2) Die Suche
  wandert von `mobil.html` in die gemeinsame Kopfzeile `_mobile_header.html` -- damit von jeder
  der vier Monteursseiten aus erreichbar, nicht nur von "Einsätze". Dabei die alte, seit 1.3.45
  bestehende Kopfzeilen-Architektur (zwei einzeln mit hart codierten `top`-Pixelwerten
  gestapelte sticky-Elemente) durch EINEN gemeinsamen sticky-Wrapper mit normalen, nie
  überlappenden Blockzeilen abgelöst -- robuster gegen künftige neue Zeilen. Die Vorschlagsliste
  öffnet sich bewusst unterhalb der GESAMTEN Kopfzeile (nicht direkt unter dem Suchfeld), damit
  sie die Reiter darunter nie überdeckt -- sonst hätte ein Tipp auf einen Reiter bei offener
  Liste zuerst nur die Liste geschlossen, ein zweiter Tipp wäre nötig gewesen. 8 neue,
  strukturelle Tests (`tests/test_v269_mobile_header_search.py`). Details im Abschnitt
  "Dateiablage je Objekt" → "Nachtrag (seit 1.3.65)" unten.
- Neu seit 1.3.66: **Büro-Suche, Etappe 1 -- Registry, Kernstruktur, Rollensicherheit.**
  Erweitert den geteilten Suchkern aus 1.3.64 (`app/search.py`) um 16 weitere
  Gruppe-A-Datensatzarten (Kunden, Aufträge, Rechnungen, Mahnungen, Angebote, Projekte,
  Dachflächen, Anfragen, Aufgaben, Mitarbeiter, Einsatzberichte, Mängel, Wartungsverträge,
  Leistungen, Materialien, Lieferanten) über eine neue `SearchSource`-Registry
  (`OFFICE_SEARCH_SOURCES`, 17 Einträge) und einen Dispatcher (`search_office()`) -- die
  Vollständigkeitsprüfung wurde ZUSAMMEN mit der Registry gebaut, nicht danach. JEDE Quelle
  bleibt Büro+Admin (nichts admin-only: Kalkulationsgrundlagen sind keine Gruppe-A-Entität,
  Einkaufspreise/Vergütung sind bereits anderswo Büro+Admin-sichtbar), JEDE `row_fn` liefert
  strukturell nur `{id, title, subtitle, url}` -- nie ein Preis-/Lohnfeld. ILIKE statt
  Volltextsuche (empirisch geprüft: 472 Zeilen, ~0.03ms je Abfrage; die Schwelle für einen
  künftigen Wechsel ist dokumentiert). "orders"/"invoices" durchsuchen Snapshot UND live
  Kundenname unabhängig voneinander -- der Fund, der sonst zur stillen Lücke geworden wäre.
  Neuer, eigenständiger Endpunkt `GET /api/search` (niemals gemeinsam mit der Monteurs-Suche),
  `require_role(ROLE_ADMIN, ROLE_OFFICE)` als primäre Sicherung. Angriffstest wie bei der
  Monteurs-Suche: ein Monteur bekommt 403 -- plain und mit manipulierten Parametern --, null
  durchgelassen. Die Oberfläche (Etappe 2) ist bewusst noch nicht Teil dieser Version. Details
  im neuen Abschnitt "Büro-Suche" unten.
- Neu seit 1.3.67: **Büro-Suche, Etappe 2 -- die Oberfläche.** Suchfeld in der seit 1.3.45
  reservierten Topbar-Position (`_topbar.html`), Vorschläge beim Tippen mit demselben Debounce
  (300ms) und derselben Mindestlänge (2 Zeichen) wie die Monteurs-Suche -- ruft ausschließlich
  `GET /api/search`, nie den Monteurs-Endpunkt. Rendert nur für `admin`/`office` (die Suche
  selbst fehlt im Markup für `field`, kein nie funktionierendes Eingabefeld). Bestätigen öffnet
  `/suche` -- die Ergebnisseite, nach Datensatzart gruppiert, reale Trefferzahl je Gruppe, Liste
  je Art auf 20 gekappt mit "weitere anzeigen", Filter nach Art (die 17 Filter-Schlüssel sind
  client-seitig hartcodiert, ein Test gleicht sie gegen `OFFICE_SEARCH_SOURCES` ab). `/suche`
  trägt dieselbe `require_role(ROLE_ADMIN, ROLE_OFFICE)`-Absicherung wie jede andere Büro-Seite
  -- ein Monteur, der die Adresse von Hand eintippt, bekommt 403, bevor irgendetwas rendert
  (per echtem Ende-zu-Ende-Test gegen eine isolierte Serverinstanz bestätigt, nicht nur per
  `router_test_client`). Dabei ein kleiner, transparent gemeldeter Fund: die Monteurs-Suche
  (`_mobile_header.html`) schloss ihre Vorschlagsliste bisher nur per Klick daneben, nicht per
  Escape, obwohl die Anfrage für die Büro-Suche "wie in der Monteurs-Suche" annahm, dass Escape
  dort schon funktioniert -- für beide nachgezogen, nicht nur für die neue. 10 neue Tests
  (`tests/test_v271_office_search_ui.py`), dazu ein bestehender Test in `tests/test_v254_topbar.py`
  in zwei umgeschrieben (die 1.3.45-Erwartung "Suchslot bleibt leer" ist jetzt bewusst überholt).
- Neu seit 1.3.68: **Hell/Dunkel-Umschalter in der Monteurs-Kopfzeile.** Gemeldete Lücke: die
  Büro-Sidebar hat den Umschalter seit 1.3.44 im Fußbereich, `_mobile_header.html` hatte nie
  einen. Ergänzt nach demselben Mechanismus wie die Sidebar (`data-theme`-Attribut,
  `localStorage`-Schlüssel `'erp_theme'`, dieselben SUN_ICON/MOON_ICON-SVGs) -- dupliziert statt
  geteilt, wie bei kleinen JS-Schnipseln in diesem Projekt üblich. Der neue, kleine Icon-Knopf
  (`#mobileThemeToggle`, 30×30px) sitzt oben rechts neben dem Benutzernamen, beide zusammen in
  einem neuen `.mobile-header-right`-Wrapper (`flex:0 0 auto`) -- `.mobile-header` behält dadurch
  genau zwei direkte Kinder, sein `justify-content:space-between` bleibt unverändert. Kollidiert
  strukturell nicht mit Suchfeld (1.3.65) oder den vier Reitern (beide in eigenen Blockzeilen des
  seit 1.3.65 gemeinsamen sticky-Wrappers); auf schmalen Bildschirmen kann nur
  `.mobile-header-brand` (bereits `overflow:hidden`) schrumpfen, der rechte Block bleibt fest --
  die Kopfzeile kann dadurch nicht umbrechen. Geprüft statt angenommen: `get_theme()` wird bereits
  in allen vier Monteursseiten (`mobil.html`/`mobil_objekt.html`/`field_timesheet.html`/
  `time_tracking_field.html`) im eigenen `:root`-Block gelesen, exakt wie auf jeder anderen Seite
  -- keine Codeänderung nötig, nur als Regressionstest festgehalten (`tests/
  test_v272_mobile_header_theme_toggle.py`).
- Neu seit 1.3.69: **Wartungsbericht-Detailansicht für Monteure, ausschließlich über das Objekt.**
  Ein Monteur, der dieselbe Wartung erneut durchführt, will nachvollziehen, was letztes Jahr
  gemacht wurde -- auch von einem inzwischen ausgeschiedenen Kollegen. Vorab ein Befund: der
  vermutete "internal_note"-Fund existiert nicht (rekursiver Schlüssel-Scan gegen
  `ServiceReportHistoryOut` und die zugrunde liegenden Modelle, kein Fund -- nichts entfernt),
  und der Bericht-PDF trug ohnehin nie einen Preis (`ServiceReportMaterial`/`TimeEntry` haben
  strukturell keine Preisspalte) -- der einzige gesperrte Abschnitt ist "Erfasste Zeiten" wegen
  fremder Personendaten, nicht wegen eines Preises. Das preisfreie, zeitfreie PDF entsteht deshalb
  NICHT über einen eigenen Renderer, sondern über einen Schalter am bestehenden:
  `build_service_report_pdf(db, report, include_time_entries=False)` (Wrapper
  `build_service_report_pdf_for_field()`) lässt "Erfasste Zeiten" komplett weg -- `list_entries()`
  wird dabei gar nicht erst aufgerufen. Neuer Endpunkt `GET /api/field-view/properties/
  {property_id}/maintenance-history/{report_id}/pdf` -- `resolve_property_history_report_for_field()`
  (`app/service_reports.py`) verifiziert erneut, dass der Bericht zu GENAU diesem Objekt gehört
  und bereits unterschrieben ist (Muster `resolve_property_document_for_field()`), sonst 404,
  ununterscheidbar von "existiert nicht". Reines Lesen -- kein PUT/DELETE/sign unter diesem Pfad,
  die bestehenden Endpunkte bleiben unverändert über `require_field_report_ownership()`
  beschränkt (dessen Docstring trägt seither eine dokumentierte Ausnahme für diesen neuen,
  objektbezogenen Weg). Siehe eigener Unterabschnitt "Wartungsbericht-Detailansicht" im Abschnitt
  "Dateiablage je Objekt" unten.
- Neu seit 1.3.70: **Umbau der Projektliste, Fundament -- Projekt-Pipeline.** Erste Etappe eines
  vom Nutzer angefragten, mehrstufigen Umbaus (Befund zuvor separat berichtet, keine
  Codeänderung -- siehe eigener Abschnitt "Umbau der Projektliste" unten für die vollständige
  Herleitung inkl. der wichtigsten Entscheidung: Kanban-Spalte als neues, von `Project.status`
  UNABHÄNGIGES Feld, kein Ersatz dafür). Neue Stammdatentabelle `ProjectPipelineColumn` (Muster
  `TaskColumn`, aber ohne `is_done`), neue Spalte `Project.pipeline_column_id` (FK, NOT NULL --
  Migration `da9d9425e257` befüllt dafür ALLE Bestandsprojekte auf die erste Spalte "Neu"), alle
  vier `Project(...)`-Konstruktionsstellen setzen sie jetzt explizit über die neue
  `default_pipeline_column_id()`. Spaltenverwaltung unter Einstellungen → Projekte →
  Projekt-Pipeline (`app/routers/project_pipeline_columns.py`, dieselbe Büro+Admin-Sperre wie
  der Rest der Projektverwaltung). Diese Version liefert AUSSCHLIESSLICH das Fundament -- die
  Listen- und Kanban-Oberfläche selbst folgt erst in der zweiten Runde, nach Bestätigung
  (umgesetzt seit 1.3.72, siehe dort).
- Neu seit 1.3.71: **Wanduhrzeit-Flake in `tests/test_v224_field_view.py` behoben, unabhängig
  von der Projekt-Pipeline (eigener Commit, wie verlangt).** Zwei bereits vor 1.3.70 bestehende
  Tests (`test_field_view_today_returns_assignments_and_drafts_for_linked_employee`/
  `..._rejects_unlinked_employee`) riefen `get_field_view_today()` direkt auf und schlugen
  deshalb JEDEN Tag nach 19 Uhr (dem Standard-Feierabend) fehl, unabhängig von jeder
  Codeänderung -- ein Test, der irgendwann garantiert rot wird, gewöhnt an eine rote Suite und
  verdeckt dadurch echte Fehler. Neue, private Bruchstelle `app/routers/field_view.py::_now()`
  (liefert `datetime.now()`, von `get_field_view_today()` jetzt statt des impliziten Rückfalls
  in `is_past_shift_end()` explizit durchgereicht) -- **bewusst NICHT als Query-/Body-Parameter
  auf der Route selbst**, das hätte einem Monteur erlaubt, die Feierabend-Abmeldung per
  `?now=...` zu umgehen, ein echtes Sicherheitsrisiko. Die beiden Tests monkeypatchen
  `_now()` jetzt auf einen festen Vormittagswert -- exakt das Muster, das
  `test_is_past_shift_end_before_and_after_configured_time()` in derselben Datei für
  `is_past_shift_end()` bereits direkt vormacht (ein festes `now`), nur über die private
  Python-Bruchstelle statt eines HTTP-Parameters. Verifiziert um 20:22 Uhr (nach dem
  Standard-Feierabend) grün.
- Neu seit 1.3.72: **Umbau der Projektliste, Runde 2 -- die Oberfläche.** `app/templates/
  projects.html` vollständig neu gebaut (siehe Abschnitt "Umbau der Projektliste" unten für die
  volle Herleitung). Linker Fünf-Reiter-Kasten entfällt, volle Breite, Kategoriefilter, Kontext-
  menü je Zeile statt sechs Inline-Links, umschaltbare Kanban-Ansicht (native HTML5-Drag-and-
  Drop, Muster Plantafel) mit den Pipeline-Spalten aus 1.3.70. Vor dem Entfernen geprüft und dem
  Nutzer gemeldet: die Angebote/Aufträge-Reiter waren die einzige projektübergreifende Über-
  sicht -- auf Rückmeldung durch einen neuen, rein client-seitigen Status-Filter ersetzt
  ("Angebot: Entwurf"/"Versendet"/"Auftrag vorhanden"/"Ohne Angebot"), der Anfragen-Reiter war
  dagegen redundant (`/inquiries` existiert bereits) und entfällt ersatzlos. Mustervorgänge
  bleiben über ein Kontrollkästchen "Nur Mustervorgänge" in derselben Liste erreichbar statt
  eines eigenen Zugangs. Neuer Endpunkt `PUT /api/projects/{id}/pipeline-column` ändert
  ausschließlich `pipeline_column_id`, nie `Project.status`, kein Bestätigungsdialog (Absicherung
  aus dem Fundament). `ProjectListOut`/`ProjectDetailOut` liefern jetzt `pipeline_column_id` mit.
  Per echtem HTTP-Smoke-Test gegen eine isolierte, temporäre Datenbank bestätigt: Monteur bleibt
  weiterhin vollständig ausgesperrt (Seite UND API 403), Verschieben im Kanban ändert nachweis-
  lich nie den Status. Kein echter Browser-Klicktest möglich (Werkzeug-Einschränkung dieser
  Umgebung) -- Drag-and-Drop/Kontextmenü nur über Quelltext- und Endpunktprüfung abgesichert.
- Neu seit 1.3.74: **Umbau der Projekt-Detailseite (die Projektmappe).** `app/templates/
  project_folder.html` vollständig neu gebaut -- die linke, sprungmarken-basierte
  Bereichsnavigation ist einer echten, waagerechten Reiterleiste gewichen (siehe Abschnitt
  "Umbau der Projekt-Detailseite" unten für die vollständige Herleitung inkl. Befund und der
  fünf vom Nutzer bestätigten Bau-Entscheidungen). Kennzahlen bleiben als schlanker, immer
  sichtbarer Block über den Reitern (ausdrücklich gegen die eigene Befund-Empfehlung, die eine
  Zusammenlegung mit "Übersicht" vorgeschlagen hatte), der permanente Kopf-Button ist entgegen
  der eigenen Vermutung "Projektmappe bearbeiten" statt "+ Angebot" -- gegen die reale,
  lokale Datenbank begründet (6 von 8 Projekten bereits "beauftragt"). Reiter-Auswahl steht im
  URL-Hash (Muster `settings.html`), die drei externen Tiefenverweise (`projects.html`/
  `order.html`/`work_preparation.html`) mussten dafür nicht geändert werden. Per echtem,
  CDP-gesteuertem Headless-Chrome gegen eine isolierte Testinstanz verifiziert (Muster 1.3.73).
- Neu seit 1.4.0: **Betriebsmittelverwaltung, Stufe 1** -- erstes neues Modul (`module_key
  "betriebsmittel"`) seit der Monteursansicht. `OperationalAsset` ist eine eigene, neue Tabelle
  mit optionalem Bezug zu genau einer `OperationalResource` (unique -- höchstens ein
  Betriebsmittel je Ressource), NICHT deren Erweiterung -- die Plantafel-Disposition
  referenziert weiterhin ausschließlich `operational_resources.id`. Ist ein Asset verknüpft,
  werden Name/Typ/Hersteller/Modell/Kennzeichen bei jedem Lesezugriff LIVE aus der Ressource
  aufgelöst, nie als Kopie gespeichert -- der Schutz gegen Doppelerfassung/Namensdivergenz.
  Prüf-/Wartungsfristen (`OperationalAssetInspection`) mit eigener, frischer Fälligkeitslogik
  (`is_inspection_due()`/`is_inspection_overdue()`) -- bewusst NICHT dieselben Funktionen wie
  beim Wartungsmodul wiederverwendet (dessen `_is_item_overdue()` ist an saisonale
  `MaintenanceWindow`-Fenster gekoppelt), nur das Muster ist identisch. Kosten
  monatsnormalisiert (`recurring_cost_per_month`) als Vorbereitung für eine spätere
  Gesamtkostenübersicht. Migration `5917bb099776` backfillt für alle 5 real bestehenden
  `OperationalResource`-Zeilen ein verknüpftes Asset. Stammdaten-Navigationsknopf schaltet
  zwischen der reichen Asset-Ansicht (Modul an) und der alten, rohen Ressourcenliste (Modul
  aus) um -- keine zweite, verwaiste Pflege. Eigene Detailseite `/betriebsmittel/{id}` (Regel
  10, wie Property/Wartungsvertrag). Siehe eigener Abschnitt "Betriebsmittelverwaltung" unten
  für die vollständige Herleitung. QR-Code + rollenabhängige Ansicht (Stufe 2) und
  Betriebsmittel im Bericht (Stufe 3) sind bewusst noch nicht gebaut.
- Neu seit 1.4.1: **Betriebsmittelverwaltung, Stufe 2 -- QR-Code-Etikett, rollenabhängige
  Ansicht.** Drei neue, nullable Felder auf `OperationalAsset` (`article_number`/`product_url`/
  `usage_notes`, letzteres eine transparent dokumentierte, nicht wörtlich als eigenes Feld
  angeforderte Ergänzung -- Punkt 3 der Anfrage nannte "Bedienungshinweise" als Monteur-
  sichtbares Feld, ohne es unter Punkt 1 als neues Feld zu benennen). `product_url` erzwingt
  über einen Pydantic-`field_validator` (`_require_http_url()`, `app/schemas.py`) ausschließlich
  http(s)-Adressen -- `javascript:`/andere Schemata werden mit 422 abgelehnt, der Link öffnet im
  Formular mit `target="_blank" rel="noopener"`. Jedes Betriebsmittel bekommt einen QR-Code
  (`app/qr_codes.py`, neues, eigenständiges Modul statt einer Erweiterung des
  sicherheitskritischen `app/two_factor.py`) über die bereits bestehende Abhängigkeit
  `qrcode[pil]` (seit 1.3.34, BSD-3-Clause, keine neue Bibliothek nötig) -- kodiert die
  **vollständige** Ziel-URL inklusive Domain, damit ein Kamera-Scan die Seite direkt öffnet.
  **Domain-Herkunft bewusst nicht hartkodiert**: neues, optionales
  `GeneralSettings.public_base_url` (Einstellungen → Unternehmensstammdaten, "Öffentliche
  Adresse") hat Vorrang, sonst Rückfall auf `request.base_url` -- gewählt, weil im Projekt noch
  kein Basis-URL-Mechanismus existiert und der Produktions-Nginx-Reverse-Proxy ohne bestätigte
  `ProxyHeadersMiddleware`/Trusted-Proxy-Konfiguration `request.base_url` allein nicht verlässlich
  macht. Neuer, Büro/Admin-only-Endpunkt `GET /api/operational-assets/{asset_id}/qr-code.png`,
  Button "Etikett drucken" auf `/betriebsmittel/{id}` zeigt QR-Code + Name als druckbares Etikett
  über eine `@media print`-Regel, die den kompletten `.app-layout` ausblendet und nur das
  Etikett-Element (bewusst als direktes Geschwisterelement, nicht verschachtelt -- ein
  `display:none` auf einem Vorfahren hätte es sonst ebenfalls versteckt) einblendet.

  **Rollenabhängige Ansicht, das eigentliche Kernstück**: der QR-Code führt JEDEN (Büro UND
  Monteur) auf dieselbe URL `/betriebsmittel/{id}` -- die Weiche hängt an der Rolle, nicht am
  Pfad, exakt das schon bei `time_tracking_page()` etablierte Muster.
  `app/routers/pages.py::operational_asset_page()` wählt serverseitig zwischen
  `operational_asset_field.html` (neu -- Bezeichnung/Art/Hersteller/Modell/Bedienungshinweise,
  NICHT Prüffristen/Kosten/Artikelnummer/Produktlink) und dem unveränderten
  `operational_asset.html`. `GET /api/operational-assets/{asset_id}` ist von Büro/Admin-only auf
  `_any_role_dep` erweitert und liefert je Rolle explizit `OperationalAssetFieldOut.model_validate(...)`
  oder `OperationalAssetOut.model_validate(...)` (Union-Response-Model, Muster
  `OrderOut | OrderFieldAccessOut` aus dem Rechtekonzept -- nie ein bloßes Dict zurückgegeben,
  um Pydantics mehrdeutige Union-Serialisierung zu vermeiden). **Serverseitig, nicht pfadbasiert
  geprüft**: ein Monteur, der die volle Büro-URL statt des mobilen Wegs aufruft, bekommt
  garantiert dieselbe reduzierte Ansicht -- verifiziert per rekursivem Schlüssel-Scan (Fehlerklasse
  `purchase_price`) sowohl auf der reinen Schema-Ebene als auch am echten Router-Response.

  **Punkt 4 (Scan-Weg) geprüft, wie verlangt NICHT ungefragt gebaut**: moderne Telefone öffnen
  einen per Kamera-App gescannten QR-Code direkt als Link, ohne dass ein eigener Scanner in die
  Anwendung eingebaut werden muss -- kein dedizierter In-App-Scanner umgesetzt.

  **Verifiziert**: 14 neue Tests (`tests/test_v277_operational_assets_stufe2.py`, u. a.
  URL-Validierung, reduziertes Schema exakt, QR-PNG-Gültigkeit über Pillow, 403 für Monteur auf
  dem QR-Endpunkt), volle Suite grün, dazu ein echter, CDP-gesteuerter Zwei-Rollen-Browsertest
  (Büro voll inkl. neuer Felder + funktionierender QR-Endpunkt + 422 bei `javascript:`-Produktlink;
  Monteur strikt reduziert mit exakt sechs erlaubten JSON-Schlüsseln + 403 auf dem QR-Endpunkt)
  gegen eine isolierte, temporäre Datenbank -- inkl. einer über `Page.printToPDF` echt gerenderten
  Bestätigung, dass das Druck-Etikett ausschließlich QR-Code + Name zeigt, keine Sidebar. Dabei
  ein selbst gefundener und vor jedem Test korrigierter CSS-Fehler: das Etikett-Element lag
  ursprünglich verschachtelt innerhalb des ausgeblendeten `.app-layout`, siehe oben.
- Neu seit 1.4.2: **Betriebsmittelverwaltung, vier weitere Ergänzungen -- alle reine
  Bürofunktion, kein Monteur betroffen.** (1) **Automatische Fälligkeitsberechnung**:
  `OperationalAssetInspection.next_due_date` wird bei gesetztem `interval_months` seither
  automatisch berechnet (`_compute_next_due_date()`, `app/operational_assets.py`) --
  `letztes tatsächliches Prüfdatum (oder, ohne dieses, Anschaffungsdatum) + Intervall − 1 Tag`,
  NIE kumulativ vom Anschaffungsdatum fortgeschrieben: verspätet sich eine Prüfung, verschiebt
  sich der ganze Rhythmus mit, statt auseinanderzudriften -- mit einem eigenen Test belegt, der
  genau diese Feinheit gegen die (falsche) kumulative Rechnung abgrenzt. Eine Prüffrist ohne
  Intervall bleibt vollständig manuell. (2) **Meldung und Aufgabe vier Wochen vorher**, On-Demand
  wie bei den Wartungsverträgen: neuer, Fire-and-Forget-ausgelöster Endpunkt `POST
  /api/operational-assets/check-due` (beim Laden von `master_data.html#assets`, kein
  Hintergrundjob), erinnert per `create_task()` (Aufgabe **unassigned**, "allgemein ans Büro" --
  es gibt kein Zuständigkeits-Feld je Betriebsmittel), idempotent über einen neuen Stempel
  `OperationalAssetInspection.last_reminder_due_date` (dasselbe Muster wie `MaintenanceContract`,
  kein expliziter Reset nötig). Erscheint ausschließlich im bestehenden "Fällige
  Prüffristen"-Panel und im Aufgabenbereich, kein zweites Dashboard-Widget. **Transparent
  festgehalten**: eine unassigned Aufgabe ist für Nicht-Admin-Büro-Konten nach dem heutigen
  Task-System unsichtbar (`GET /api/tasks` filtert für jeden Nicht-Admin auf die eigene
  `employee_id`) -- eine bereits bestehende, allgemeine Einschränkung des Aufgabenmoduls, keine
  neu eingeführte Lücke. (3) **Betriebsmittel in der Büro-Suche**, 18. Registry-Eintrag
  (`app/search.py`, Mindestrolle Büro, modulgated) -- durchsucht Bezeichnung/Art/Hersteller/
  Modell/Kennzeichen/Artikelnummer; ein ressourcenverknüpftes Asset (Kran, Fahrzeug, Anhänger)
  trägt seine eigenen Identitätsfelder als `NULL` (Live-Auflösung seit 1.4.0), die neue Quelle
  joint deshalb `OperationalResource` und nutzt denselben `resolve_asset_identity()`-Helfer wie
  die Betriebsmittelseite selbst -- sonst wäre jedes ressourcenverknüpfte Asset unauffindbar
  gewesen. (4) **Dokumentenablage am Betriebsmittel** (Anschaffungsrechnung, Leasingvertrag
  u. Ä.): neue Tabelle `OperationalAssetDocument` (mehrere unabhängige Dateien je Betriebsmittel,
  anders als die bestehende 1:1-Ablage je Prüffrist), `document_type` über eine neue, schlanke,
  self-seedende Optionsgruppe statt der schwergewichtigen `DocumentCategory`-Stammdatentabelle
  aus 1.3.62 -- deren zwei Schlösser gegen "sensible Kategorie für Monteure sichtbar" sind hier
  gegenstandslos, da Betriebsmittel-Dokumente ausnahmslos Büro/Admin-only sind, ohne jede
  Monteur-sichtbare Stufe. Löschen räumt die Datei über ein `before_delete`-Event auf (Muster
  `app/roof_areas.py`). **Abschließender Angriffstest, wie verlangt**: ein Monteur erreicht
  keinen der drei Dokumentenablage-Endpunkte, auch nicht über eine geratene, fortlaufende
  Datei-ID (`require_role()` schließt die Rolle strukturell aus); die Büro-Suche liefert einem
  Monteur über den echten Router durchgängig 403, nie ein Betriebsmittel -- beide Fälle in
  `tests/test_v278_operational_assets_erweiterungen.py` belegt. Migration `ed896599a211`,
  volle Suite 1441 Tests grün.
- Neu seit 1.3.73: **Kontextmenü der Projektliste -- Beschneidung durch `overflow:auto`
  behoben, per echtem Headless-Browser-Test verifiziert.** Gemeldeter Fehler an 1.3.72: das
  Drei-Punkte-Menü klappte innerhalb des seit 1.3.9 scrollbaren `.wrap`-Tabellencontainers auf
  und wurde von dessen `overflow:auto` auch vertikal beschnitten. `.menu` wechselt von
  `position:absolute` auf `position:fixed` (kein anderer, dafür geeigneter Vorfahre trägt
  `transform`/`filter`/`contain`, geprüft) -- Position wird per JS aus der `getBoundingClientRect()`
  des Drei-Punkte-Knopfs berechnet, klappt bei zu wenig Platz nach oben statt unten, ein globaler
  Scroll-Listener schließt ein offenes Menü statt es fehlpositioniert stehen zu lassen. **Erste
  echte Browser-Verifikation seit langer Zeit** (siehe unten "Werkzeug-Notiz") -- die bisher in
  dieser Datei wiederholte Einschränkung "kein Browser-Automatisierungswerkzeug verfügbar" ist
  damit für Headless-Chrome-Fälle nicht mehr uneingeschränkt gültig, siehe eigener Abschnitt
  "Headless-Chrome-Verifikation über CDP" unten.
- Neu seit 1.4.3: **Änderung am Aufgabenmodul -- empfängerlose Aufgaben für ganz Büro sichtbar,
  "Übernehmen"/"Zurück in den Büro-Eingang".** Anlass war der in 1.4.2 transparent gemeldete
  Fund, dass eine unassigned Aufgabe für Nicht-Admin-Büro-Konten unsichtbar bleibt -- erst
  Befund (wo der Filter überall sitzt: exakt eine Stelle, `list_tasks()`/dessen einziger
  Aufrufer `GET /api/tasks`), dann bestätigter Bauauftrag. Neues `has_role(user, *roles) ->
  bool` (`app/permissions.py`) ist jetzt die EINE Rollenquelle -- `require_role()` und der
  Jinja-Global `can()` delegieren beide daran, statt je einen eigenen Vergleich zu tragen
  (genau das bei `build_din5008_header_block()` bereits einmal aufgetretene
  Drei-Varianten-Muster, hier vermieden). Neues `app/tasks.py::list_tasks_for_user(db, user,
  ...)` ist der ausschließliche Einstiegspunkt für jede Task-Sichtbarkeit -- Admin frei
  wählbar, Büro ohne `unassigned_only` zwingend auf die eigene `employee_id` (Kollegen-Aufgaben
  bleiben unsichtbar, unverändert), mit `unassigned_only=True` sieht JEDES Büro-/Admin-Konto den
  gemeinsamen Eingang (`list_tasks()` bekommt dafür einen neuen, vorrangigen
  `unassigned_only`-Parameter). "Übernehmen" (`claim_task()`, `POST /api/tasks/{id}/claim`)
  weist fest zu -- kein dritter Zustand neben zugewiesen/empfängerlos -- über exakt dasselbe
  Feld wie jede andere Zuweisung, lehnt eine bereits vergebene Aufgabe ab (400, verhindert
  versehentliches Stehlen) und verlangt eine `employee_id`-Verknüpfung (klare 400-Meldung, kein
  stiller Fehler -- derselbe Fall wie beim Monteur ohne Mitarbeiterverknüpfung). "Zurück in den
  Büro-Eingang" (`release_task()`, `POST /api/tasks/{id}/release`) macht eine Aufgabe wieder
  empfängerlos, bewusst OHNE Eigentümerschafts-Prüfung -- konsistent mit der bereits
  bestehenden, dokumentierten Lücke bei PUT/DELETE/archive/unarchive (siehe "Aufgabe" unten),
  keine isolierte Verschärfung nur hier. Neues, opt-in Dashboard-Widget "Offene
  Büro-Aufgaben" (`open_office_tasks`, Muster `due_maintenance`/`due_assets`, nicht im
  Standard-Layout) samt "Übernehmen"-Button je Zeile; `/tasks` bekommt einen neuen Button
  "Zurück in den Büro-Eingang" im Editor, sichtbar nur bei bereits zugewiesener Aufgabe -- der
  Board-Fetch selbst bleibt für Nicht-Admin unverändert "nur eigene". Ein Monteur bleibt von der
  gesamten `/api/tasks*`-Familie weiterhin vollständig ausgeschlossen (unverändert seit
  "Rechtekonzept") -- bestätigt per Angriffstest: 403 auf Liste UND auf Übernehmen/Zurückgeben,
  auch mit geratener Aufgaben-ID, bevor irgendeine Geschäftslogik läuft.
  Die dabei transparent vermerkte, unabhängige Lücke in der Büro-Suche
  (`app/search.py::_search_tasks()` ohne Mitarbeiter-Filterung) ist seit 1.4.4 behoben, siehe
  dort.
- Neu seit 1.4.4: **Nachtrag zu 1.4.3 -- Büro-Suche findet Aufgaben jetzt über dieselbe
  Sichtbarkeitsregel wie `GET /api/tasks`.** Die in 1.4.3 transparent gemeldete, unabhängige
  Lücke (`app/search.py::_search_tasks()` ohne Mitarbeiter-Filterung -- ein Büro-Konto fand
  darüber auch die persönlich zugewiesene Aufgabe eines Kollegen) wurde behoben, solange der
  Zusammenhang frisch war. **Keine zweite Kopie der Regel**, wie ausdrücklich verlangt:
  `app/tasks.py::list_tasks()`/`list_tasks_for_user()` bekommen einen neuen, optionalen
  `search`-Parameter, `_search_tasks()` ruft `list_tasks_for_user()` seither zweimal auf (eigene
  + empfängerlose) und vereinigt beide Listen -- keine eigene, hier nachgebaute SQL-Filterlogik.
  `search_office()` bekommt dafür einen neuen, optionalen `employee_id`-Parameter (nur für
  "tasks" relevant, jede andere Quelle unverändert), ein transientes `AppUser`-Objekt trägt
  Rolle/`employee_id` in `list_tasks_for_user()` hinein. Angriffstest bestätigt: Büro-Konto
  findet eigene + empfängerlose, nie die eines Kollegen; Admin findet alle; Monteur findet
  weiterhin nichts (bereits über die Registry-Rollenprüfung abgedeckt). Siehe Abschnitt
  "Büro-Suche" -> "Nachtrag (seit 1.4.4)" unten für die volle Herleitung. Volle Suite: 1466
  Tests grün.
- Neu seit 1.4.5: **Betriebsmittelverwaltung, Stufe 3 -- eingesetzte Betriebsmittel im
  Einsatzbericht.** Reine Dokumentation (kein Preis, keine Menge, keine Betriebsstunden), erst
  Befund dann Vorschlag dann in einer Runde gebaut. Neue Tabelle `ServiceReportAsset` (Vorbild
  `ServiceReportMaterial`, nicht Fotos) -- `asset_id` als Pflicht-Verweis für eine spätere
  Kostenauswertung UND ein physisch eingefrorener `asset_name_snapshot` (Muster Bauteil-/
  Dachflächennamen seit 1.3.12), bewusst so geschnitten, dass eine künftige Kosten-/
  Abrechnungserweiterung (Betriebsstunden, Mietdauer, abrechenbare Menge) als nullable
  `ALTER TABLE ADD COLUMN` auf genau dieser Zeile andockt, keine Strukturänderung. Neues Flag
  `OperationalAsset.selectable_in_reports` (Standard AUS, Muster `DocumentCategory.
  is_field_visible`) bestimmt die Auswahlliste am Bericht -- gilt für JEDEN Aufrufer gleich,
  auch Büro/Admin, keine Rollenausnahme (das ist zugleich die Absicherung gegen eine geratene
  `asset_id`). Vierter, gleichrangiger Panel-Umschalter "Betriebsmittel" auf der Berichtskarte
  (Bedienung wie Material, aber `<select>` statt Debounce-Suche -- die freigegebene Liste bleibt
  kurz). `delete_asset()` blockiert jetzt, solange ein Bericht (Entwurf ODER unterschrieben) das
  Asset referenziert (strenger als `delete_roof_component()`, da `asset_id` NICHT NULL ist) --
  Archivieren bleibt frei. Neuer Abschnitt "Eingesetzte Betriebsmittel" im Kundenbericht (nur
  wenn erfasst, schlichte Namensliste ohne `notes`, auch im reduzierten Feld-PDF). QR-Scan im
  Bericht **geprüft, nicht gebaut** -- der bestehende QR-Code würde den Bericht beim Scannen
  verlassen, ein In-Bericht-Scanner bräuchte Kamera-Zugriff im Browser plus eine neue
  Dekodier-Bibliothek, zurückgestellt bis sich im Betrieb zeigt, dass die Auswahlliste zu
  umständlich ist. Angriffstest bestätigt: die neue Auswahlliste liefert für jede Rolle nur die
  fünf feldsicheren Felder (rekursiver Schlüssel-Scan), eine nicht freigegebene/geratene
  `asset_id` liefert 400 statt stillem Erfolg. Migration `b2226e22b9f0`, 26 neue Tests, volle
  Suite: 1492 Tests grün.
- Neu seit 1.5.0: **Betriebskosten-Übersicht, Schicht 1 -- die Kostenerfassung**, erstes neues
  Modul seit der Betriebsmittelverwaltung (`module_key "betriebskosten"`, buero_finanzen/
  admin-only). Neue Tabelle `RecurringCost` bildet den detaillierten wiederkehrenden Vertrag ab
  (Miete, Leasing, Versicherung, Software-Abo u. Ä.) -- bewusst KEINE Migration der bestehenden
  `OperationalAsset.recurring_cost_per_month` (die schnelle Notiz beim Anlegen bleibt bestehen),
  beide Quellen führt `overview_summary()` in der Summe zusammen und verhindert dabei die
  Doppelzählung: ein verknüpfter Kostenposten ERSETZT die Notiz am Betriebsmittel, statt sie zu
  ergänzen (zwei nicht persistierte Transparenz-Hinweise, `asset_quick_cost_hint`/
  `has_linked_recurring_cost`). `annual_amount` ist ein gespeichertes, normiertes Feld -- der
  Andockpunkt für den späteren Verrechnungssatz-Kreislauf, siehe eigener Abschnitt
  "Betriebskosten-Übersicht" unten für die volle Herleitung inkl. der konkreten Codestelle in
  `app/labor_rate.py`. Dabei eine allgemeine, nicht nur für Betriebskosten gedachte Erweiterung
  des Aufgabenmodells: `Task.min_visible_role` (siehe Abschnitt "Aufgabe" unten) grenzt eine
  empfängerlose Aufgabe optional auf eine Ziel-Mindestrolle ein. Migration `fc79aa5629d0`, 26
  neue Tests, volle Suite: 1558 Tests grün.
- Neu seit 1.5.1: **Verrechnungssatz-Kreislauf Schicht 3 -- die beiden begriffskonflikt-
  unabhängigen Teile.** Vor dem Bauen ein reiner Befund zu Punkt 1 (wie `labor_rate.py` den
  Satz heute bildet, ob die Vermischung mit den automatisch addierten Verwaltungslöhnen in
  `variable_overhead_value` fachlich sauber ist), danach sechs Betreiberentscheidungen -- zwei
  davon ausdrücklich unabhängig vom offenen Begriffskonflikt "variabel" und deshalb schon jetzt
  gebaut, die eigentliche "Einspeisung" bleibt offen. **Produktivstunden-Rechner**
  (`app/productive_hours.py`, neue Singleton-Tabelle `ProductiveHoursSettings`) leitet
  `LaborRateSettings.productive_time_pct` nachvollziehbar aus Wochen-/Tagesstunden, Urlaub,
  Feiertagen, Ø Krankheitstagen, Schlechtwetter und geschätzter unproduktiver Zeit ab, statt den
  Wert (real: pauschal 95 %) zu raten -- `weeks_per_year` kommt bewusst aus `LaborRateSettings`
  (eine Quelle, kein zweites Feld), schreibt erst nach bewusstem "Übernehmen"-Klick
  (`apply_productive_hours_to_labor_rate()`, Muster `apply_labor_rate_calculation()`) in
  `productive_time_pct`, `calculate_labor_rate()` bleibt dabei vollständig unverändert. Neue
  Endpunkte `GET/PUT /api/productive-hours-settings` + `.../apply`, co-located im
  `labor_rate`-Router, Oberfläche direkt unter dem bestehenden Stundensatz-Rechner in
  Einstellungen → Kalkulationsgrundlagen. **`overview_summary()`-Erweiterung**: neue, indizierte
  Spalte `RecurringCost.overhead_classification` (`keine`/`fix`/`auslastungsabhaengig`, fester
  Code-Wert wie `billing_interval`, `server_default='keine'`) -- Werte vermeiden bewusst das
  Wort "variabel" (siehe unten "Terminologie 'variabel'"), **ausdrücklich als vorläufig
  gekennzeichnet**, bis der Punkt-1-Vorschlag bestätigt ist. Drei zusätzliche, getrennte
  Jahressummen (`annual_fixed_from_costs`/`annual_usage_dependent_from_costs`/
  `annual_none_from_costs`) neben der unveränderten `annual_total`. **Bewusst NICHT Teil dieser
  Version**: jede Änderung an `app/labor_rate.py`/`LaborRateOverheadSettings`, der Modus-Zwang
  beim Übernehmen, der Schritt-1-Knopf und die dreistufige Vergleichsansicht. Migration
  `57062a31dba7`, 15 neue Tests, volle Suite: 1573 Tests grün.
- Neu seit 1.5.2: **Verrechnungssatz-Kreislauf Schicht 3 -- die Einspeisung.** Fortsetzung von
  1.5.1, nach Bestätigung des Punkt-1-Vorschlags: die Einordnungswerte `keine`/`fix`/
  `auslastungsabhaengig` sind jetzt final (kein "vorläufig" mehr, Erklärtext bei
  "auslastungsabhaengig" ergänzt), die Code-Felder `variable_overhead_*` bleiben bewusst
  unangetastet. `calculate_labor_rate()` (`app/labor_rate.py`) bekommt einen neuen, optionalen,
  keyword-only Parameter `overhead_override: dict | None = None` -- lässt die Formel MIT
  hypothetischen Gemeinkosten-Werten rechnen, rein in-memory, ohne die Datenbank anzufassen;
  `recurring_cost_overhead_proposal()` ruft die Funktion deshalb ZWEIMAL auf (unverändert für
  "aktuell", mit Override für "Vorschlag") statt eine zweite Berechnung zu pflegen -- eine
  Quelle für `annual_productive_hours` und jede andere Größe in beiden Zuständen. Die
  Vergleichsansicht zeigt den Punkt-1-Hinweis jetzt als Pflichtangabe: "Auslastungsabhängige
  Betriebskosten: X. Plus automatisch berechnete Verwaltungslöhne: Y. Ergibt variable
  Gemeinkosten: X+Y.", dreistufig aufgeschlüsselt (Summe / fix+auslastungsabhängig / einzelne
  Posten aufklappbar über `<details>`), Gegenüberstellung aktuell/Vorschlag für beide Buckets
  getrennt. **Zweistufig**: neuer Knopf "Betriebskosten-Vorschlag übernehmen" (Schritt 1,
  `apply_recurring_cost_overhead_proposal()`, `POST /api/recurring-cost-overhead-proposal/apply`)
  schreibt ausschließlich die beiden Gemeinkosten-Felder und erzwingt dabei immer den Modus
  "eur" auf beiden -- mit `confirm()`-Warnung im Frontend, falls das den bisherigen
  Prozent-Modus überschreibt (keine stille Semantikänderung). Der bestehende "Als aktuellen
  Verrechnungssatz übernehmen"-Knopf (Schritt 2, `apply_labor_rate_calculation()`) bleibt
  unverändert der davon getrennte, zweite Schritt. Neuer Endpunkt
  `GET /api/recurring-cost-overhead-proposal` (reine Vorschau, schreibt nichts), co-located im
  `labor_rate`-Router, dieselbe `require_min_role(ROLE_OFFICE_FINANZEN)`-Schwelle. Kein neues
  Datenmodell, keine Migration. Abschließender Angriffstest (Betreibervorgabe):
  `buero_auftrag`/`field` kommen an keinen Teil des Kreislaufs -- weder an die Einordnung, noch
  an die Vergleichsansicht, noch an den Übernehmen-Knopf, noch an den Produktivstunden-Rechner,
  per rekursivem Schlüssel-Scan mit einem Testkonto je Rolle bestätigt. 9 neue Tests, volle
  Suite: 1582 Tests grün.
- Neu seit 1.5.3: **Grundlage für Ist-Werte -- Schlechtwetter-Zeitarten und Abwesenheitskategorie.**
  Vorbereitung für die spätere Ist-Wert-Auswertung im Produktivstunden-Rechner (eigene, noch
  folgende Runde), erst nach zwei Befund-Runden gebaut (siehe Abschnitt
  "Schlechtwetter-Zeitarten und Abwesenheitskategorie" unten für die volle Herleitung). Zwei neue
  Zeitarten `weather_winter`/`weather_summer` in der Optionsgruppe `time_entry_types`, beide
  `counts_as_productive=False` (`entry_type_is_productive()` erweitert -- ohne diese Änderung
  wären beide fälschlich als produktiv gezählt worden), von der DATEV-Lohnart-Zuordnung und von
  "Rechnung aus Zeitbuchungen" ausgeschlossen (sonst würde witterungsbedingter Ausfall dem Kunden
  in Rechnung gestellt, da `TimeEntry.order_id` NOT NULL ist). Neue, feste Abwesenheitskategorie
  `absence_category` (urlaub/krankheit/fortbildung/unbezahlt, Rückfallwert `unbekannt` nur für
  Altbestand -- 0 Bestandszeilen real geprüft) neben dem unveränderten, freien `absence_type`.
  Krankheitssichtbarkeit für `buero_auftrag` bewusst UNVERÄNDERT gelassen -- ein Redaktions-
  Vorschlag (Muster `redact_wage_snapshot()`) wurde vorgelegt und vom Betreiber ausdrücklich
  abgelehnt. Migration `cf4fdf4905cd`, 20 neue Tests, volle Suite: 1602 Tests grün.
- Neu seit 1.5.4: **Krankheitssichtbarkeit -- buero_auftrag sieht nur noch "abwesend".**
  Kurskorrektur zu 1.5.3: derselbe Redaktions-Vorschlag, den der Betreiber dort noch abgelehnt
  hatte, wurde in dieser Runde erneut aufgegriffen und umgesetzt (siehe Abschnitt
  "Krankheitssichtbarkeit: buero_auftrag sieht nur noch 'abwesend'" unten). Sechs Fundstellen
  redigiert (Plantafel-Konflikte, Planungsvorschlag, Team-/Mitarbeiter-Tageskapazität,
  Backoffice-Abwesenheitsliste, Änderungshistorie), Betreiberentscheidung "einmal eintragen, nie
  wieder lesen" für das Anlegen/Bearbeiten-Problem (`buero_auftrag` darf die Art weiterhin
  eintippen, sieht sie danach aber nie wieder, auch nicht im eigenen Antwort-Payload). Dabei
  einen echten, unabhängigen Nebenbefund behoben: `PUT /api/planning/absences/{id}` überschrieb
  bisher blind jedes Feld -- neues `EmployeeAbsenceUpdate` mit `exclude_unset=True` schützt vor
  stillem Datenverlust, unabhängig von dieser Änderung. Keine Migration nötig. 18 neue Tests,
  volle Suite: 1620 Tests grün.
- Neu seit 1.5.5: **Netto und Brutto bei den Betriebskosten.** `RecurringCost.amount` (ohne
  jede Steuersemantik) per echter Spalten-Umbenennung zu `net_amount`, neue Spalte
  `tax_rate_pct` (Vorgabe 19 %, wählbar auf 7 %/0 %, Feld je Posten). `gross_amount` ist eine
  reine, nicht gespeicherte Anzeige-Ableitung. `overview_summary()`/die Gemeinkosten-Einspeisung
  aus Schicht 3 mussten nicht geändert werden -- beide lesen ohnehin nur das bereits
  gespeicherte `annual_amount`, das jetzt automatisch netto-basiert ist. Siehe Abschnitt "Netto
  und Brutto bei den Betriebskosten" unten. Migration `9b3600be64af`, 11 neue Tests, volle
  Suite: 1631 Tests grün.
- Neu seit 1.5.6: **Dokument-Upload schon beim Erstellen des Betriebsmittels.** Der Upload-
  Endpunkt verlangte zwingend eine bereits existierende `asset_id` -- beim ersten Anlegen gab es
  dafür bisher gar kein Formularfeld. Neue, rein clientseitige Warteschlange in
  `master_data_form.html::assetForm()`: Dokumente werden vorgemerkt, nach erfolgreichem Anlegen
  des Betriebsmittels automatisch angehängt, vor der Navigation zur Detailseite. Scheitert das
  Anlegen selbst, wird die Upload-Schleife nie erreicht -- kein verwaistes Betriebsmittel, die
  vorgemerkten Dateien bleiben erhalten. Reine Frontend-Änderung, kein Endpunkt/Schema geändert,
  siehe Abschnitt "Betriebsmittelverwaltung" unten.
- Neu seit 1.5.7: **Betriebsmittel-Kosten fest als Kostenposten.** Löst die
  1.5.0-Doppelzählungs-Sonderbehandlung ab -- 0 Bestandszeilen betroffen (real geprüft), aber
  eine echte Vereinfachung: `OperationalAsset.recurring_cost_per_month` entfällt als Spalte,
  eine laufende Rate am Betriebsmittel-Formular erzeugt/ändert/entfernt seither einen echten
  `RecurringCost` (`RecurringCost.is_asset_quick_entry`), `overview_summary()` braucht dadurch
  keine Doppelzählungs-Ausnahme mehr. Nullsetzen der Rate entfernt den Posten (statt ihn bei 0
  stehen zu lassen), außer er trägt bereits Dokumente/einen Vertragspartner -- dann 409 statt
  stillem Löschen, `force_remove=true` bestätigt. Fest gebunden beim Löschen des Betriebsmittels
  über den bestehenden `before_delete`-Weg, ein davon unabhängig verlinkter Posten wird dabei
  nur entkoppelt, nicht mitgelöscht. Neuer, `require_min_role(ROLE_OFFICE_FINANZEN)`-gateter
  Endpunkt für die Rate, getrennt vom allgemeinen (für `buero_auftrag` offenen)
  Betriebsmittel-Endpunkt -- schließt eine sonst entstandene Rechte-Lücke. Migration
  `eda89bb8082a`, 18 neue Tests, volle Suite: 1649 Tests grün, siehe Abschnitt
  "Betriebsmittel-Kosten fest als Kostenposten" unten.
- Neu seit 1.5.8: **Ist-Werte im Produktivstunden-Rechner.** Drei der fünf Annahmen bekommen
  einen aus echten Daten hergeleiteten Vergleichswert -- reine Orientierung, nie automatisch
  übernommen. Feiertage: `count_workday_holidays()` (`app/planning.py`) zählt `PlanningHoliday`-
  Zeilen im laufenden Kalenderjahr, die auf einen konfigurierten Arbeitstag fallen -- errechnet,
  aber übersteuerbar (füllt `public_holidays` nur vor). Schlechtwetter/Krankheit: rollierende
  12 Monate, Durchschnitt über die Monteure mit `effective_cost_allocation()=="labor_rate"`
  (bewusst NICHT `AppUser.role` -- real 0 Konten mit `role='field'`, aber 7 solche Mitarbeiter).
  Schlechtwetter rechnet `TimeEntry.hours` über `ProductiveHoursSettings.daily_hours` in Tage um
  -- dieselbe Größe, die auch die Annahme selbst umrechnet, für echte Vergleichbarkeit.
  **Anonymitäts-Untergrenze bei Krankheit**: unter `MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE` (5)
  liefert der Endpunkt weder Durchschnitt noch Summe -- eine Summe allein wäre bei wenigen
  Monteuren trivial auf eine einzelne Krankheit zurückrechenbar. Datengrundlage-Anzeige Pflicht
  ("Beruht auf N von 12 Monaten"), datengetrieben statt eines hart codierten Einführungsdatums.
  Keine Doppelzählung, `calculate_productive_hours()`/`calculate_labor_rate()` unangetastet,
  keine Migration nötig. 19 neue Tests, volle Suite: 1668 Tests grün, siehe Abschnitt
  "Ist-Werte im Produktivstunden-Rechner" unten.
- Neu seit 1.5.9: **Sinnvolle Pfeil-Schrittweiten auf den beiden Kalkulationsrechnern.** Alle
  Zahlenfelder des Stundenkostenverrechnungssatz-/Produktivstunden-Rechners trugen `step="0.01"`
  -- bei einem Tage-Feld fünfzig Klicks für einen halben Tag. Neue Schrittweiten je Feldart:
  Tage `0,5`, Prozentwerte `0,5`, Tagesstunden `0,5`/Wochenstunden `1`, Wochen pro Jahr `1`, die
  beiden Gemeinkosten-Beträge `100` (im Euro-Modus) bzw. `0,5` (im Prozent-Modus -- die
  Eingabeart lässt sich per Umschalter wechseln, `syncOverheadLabels()` setzt die Schrittweite
  seither im selben Zug wie die Beschriftung um). `step` steuert ausschließlich die Pfeile, nie
  eine Eingabesperre -- Zwischenwerte (30,5 Urlaubstage) bleiben per Tastatur uneingeschränkt
  eintippbar, diese Seite validiert nie nativ gegen `step` (sendet per `fetch()`, kein
  Formular-Submit). Bewusst unverändert: "Aktueller Stundenkostenverrechnungssatz €/h"
  (außerhalb der beiden benannten Rechner, Cent-Ebene bei einem Stundensatz weiterhin relevant).
  Reine HTML-/JS-Änderung, kein Endpunkt/Schema geändert, keine neuen Tests nötig.
- Neu seit 1.5.10: **Neugestaltung der Seite Stundenverrechnungssatz.** Erst Befund + Vorschlag
  (keine Codeänderung), dann nach Bestätigung gebaut -- siehe eigener Abschnitt
  "Neugestaltung der Seite Stundenverrechnungssatz" unten für die vollständige Herleitung. Aus
  19 gleich aussehenden Kacheln plus zwei separaten, weit unten stehenden Rechnern werden drei
  Zonen: Eingaben, das eine Ergebnis prominent (Satz + Abweichung zum aktuellen zusammen), der
  Rechenweg aufklappbar (13 verbleibende Kacheln, vollständig, nur zugeklappt). Der
  Produktivstunden-Rechner und der Betriebskosten-Vorschlag sitzen jetzt als aufklappbare
  Bereiche direkt an den Feldern, die sie speisen (CSS-Grid-Vollbreiten-Platzierung direkt nach
  dem jeweiligen Feld), statt als eigenständige Blöcke weiter unten. Lange Erklärtexte sind aus
  der immer sichtbaren Fläche entfernt -- in die Aufklapp-Bereiche verschoben oder (zwei reine
  Text-ohne-Link-Fälle) als kleines Fragezeichen-Tooltip direkt am Feld. Dabei einen
  unabhängigen, vorbestehenden Fehler gefunden und behoben (nicht durch diesen Umbau
  verursacht): `loadRecurringCostsSettingsSection()` griff in `load()` auf `moduleStates` zu,
  bevor diese Variable zum ersten Mal zugewiesen war (`ReferenceError`, unbemerkt geblieben, da
  ohne `await`/`.catch()` aufgerufen). Rollen-Check unverändert (`buero_finanzen`/`admin`). Rein
  clientseitig, kein Endpunkt/Schema geändert; verifiziert per vollständigem `pytest`-Lauf,
  `node --check` und einem echten, CDP-gesteuerten Headless-Chrome-Durchlauf gegen eine
  isolierte Testinstanz (Aufklappen, Euro/Prozent-Umschalter, beide Übernehmen-Knöpfe
  Ende-zu-Ende, Browser-Konsole fehlerfrei).
- Neu seit 1.5.11: **"Diesem Gerät für 30 Tage vertrauen"** -- siehe Abschnitt "Diesem Gerät für
  30 Tage vertrauen" unten für die vollständige Herleitung (Checkbox nur bei der Routine-
  Bestätigung des zweiten Faktors, niemals bei der Ersteinrichtung; neue Tabelle
  `TrustedDevice`, eigenständiges Cookie `dk_erp_trust`; fünf Stellen widerrufen bestehendes
  Vertrauen -- zweimal `two_factor.reset()`, zwei Passwortänderungen, der explizite Widerruf).
- Neu seit 1.6.0: **Buchhaltung, Stufe 1 -- Eingangsrechnungen erfassen und ablegen**, erstes
  neues Modul seit der Betriebskosten-Übersicht (`module_key "buchhaltung"`, buero_finanzen/
  admin-only). Siehe eigener Abschnitt "Buchhaltung" unten für die vollständige Herleitung
  (Befund zu Supplier/Invoice/RecurringCost/Dokumentenablage-Muster, die beiden bestätigten
  Kernentscheidungen -- Positionen als optionale Aufschlüsselung mit Summen-Abgleich, Plan
  bleibt Grundlage für den Verrechnungssatz -- und die expliziten Andockpunkte für Stufe 2
  (Kontierung) und Stufe 3 (KI-Belegauswertung), die diese Version bewusst offen lässt).
