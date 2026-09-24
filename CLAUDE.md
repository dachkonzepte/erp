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

- Version: **1.6.3** (siehe `CHANGELOG.md` für die vollständige Versionshistorie)
- Migrationskette Kopf weiterhin `d87d5bc04b69` ("ai fundament settings and call log", neue
  Tabellen `ai_settings`/`ai_call_log` -- siehe Abschnitt "KI-Fundament" unten; 1.6.3 selbst
  brauchte keine eigene Migration, reine Frontend-Änderung, siehe Abschnitt "Buchhaltung" ->
  "Beleg-Upload schon beim Anlegen" unten) -- davor `329725277349` ("accounts kontenstamm
  vorkontierung", neue Tabelle `accounts` PLUS die neue Spalte `incoming_invoices.account_id`/
  `incoming_invoice_items.account_id` (ersetzt das frühere Freitextfeld `account_code`) -- siehe
  Abschnitt "Buchhaltung" -> "Stufe 2, erster Teil" unten) -- davor `fd1cc820d6b7` ("incoming
  invoices buchhaltung stufe 1", neue
  Tabellen `incoming_invoices`/`incoming_invoice_items`/`incoming_invoice_settings` -- siehe
  Abschnitt "Buchhaltung" unten) -- davor `0f7bda3397f1` ("trusted devices for two factor auth",
  neue Tabelle `trusted_devices` -- siehe Abschnitt "Diesem Gerät für 30 Tage vertrauen" unten)
  -- davor `eda89bb8082a` (weder 1.5.8, 1.5.9 noch 1.5.10 brauchten eine eigene
  Migration -- 1.5.10 ist eine reine HTML-/CSS-/JS-Umgestaltung der Seite
  Stundenverrechnungssatz, kein Endpunkt/Schema/Modell geändert, siehe Abschnitt "Neugestaltung
  der Seite Stundenverrechnungssatz" unten; 1.5.9 ist eine reine `step`-Attribut-Korrektur auf
  zwei Rechnern in `settings.html`, kein Endpunkt/Schema/Modell geändert; 1.5.8 "Ist-Werte im
  Produktivstunden-Rechner" sind ausschließlich neue, abgeleitete Funktionen, keine neuen
  Spalten, siehe Abschnitt "Ist-Werte im Produktivstunden-Rechner" unten) -- davor
  "asset recurring cost quick entry link" --
  `operational_assets.recurring_cost_per_month` entfernt, neue Spalte
  `recurring_costs.is_asset_quick_entry` (`server_default='0'`) -- siehe Abschnitt
  "Betriebsmittel-Kosten fest als Kostenposten" unten; löst die 1.5.0-Doppelzählungs-
  Sonderbehandlung ab) -- vorher `9b3600be64af` ("recurring cost netto brutto steuersatz" --
  echte Spalten-Umbenennung `recurring_costs.amount` -> `net_amount` PLUS die neue, NOT-NULL-
  Spalte `tax_rate_pct` (`server_default='19.00'`) -- siehe Abschnitt "Netto und Brutto bei den
  Betriebskosten" unten; 1.5.6 selbst brauchte keine eigene Migration, reine Frontend-Änderung)
  -- vorher `cf4fdf4905cd` ("schlechtwetter zeitarten und
  abwesenheitskategorie" -- 1.5.4 selbst brauchte keine eigene Migration, reine Code-/Schema-
  Änderung an bestehenden Spalten, neue, indizierte Spalte `absence_category`
  (`server_default='unbekannt'`) auf `employee_absences`/`employee_absence_requests` PLUS zwei
  neue, nullable DATEV-Lohnart-Spalten auf `time_tracking_settings` PLUS ein Daten-Seed, der die
  beiden neuen Zeitarten `weather_winter`/`weather_summer` in eine bereits gesäte
  `time_entry_types`-Optionsgruppe nachträgt -- siehe Abschnitt "Schlechtwetter-Zeitarten und
  Abwesenheitskategorie" unten) -- vorher `57062a31dba7` ("productive hours settings and
  recurring cost overhead classification", neue Tabelle `productive_hours_settings` PLUS die
  neue, indizierte Spalte `recurring_costs.overhead_classification` (`server_default='keine'`)
  -- siehe Abschnitt "Betriebskosten-Übersicht" -> "Verrechnungssatz-Kreislauf Schicht 3" unten)
  -- vorher
  `fc79aa5629d0` ("recurring costs betriebskosten uebersicht",
  neue Tabellen `recurring_costs`/`recurring_cost_documents`/`recurring_cost_settings` PLUS die
  neue, nullable Spalte `tasks.min_visible_role` -- siehe Abschnitt "Betriebskosten-Übersicht"
  unten) -- davor `7677d9d878ba` ("app user role office split finanzen auftrag",
  reine Daten-Migration für die Aufteilung der Rolle "office" in `buero_finanzen`/`buero_auftrag`,
  siehe Abschnitt "Rechtekonzept" -> "Vier Rollen" unten) -- vorher `b2226e22b9f0`
  ("service_report_assets_und_selectable_in_reports", siehe Abschnitt "Betriebsmittelverwaltung"
  -> "Stufe 3 (seit 1.4.5)" unten), davor
  `ed896599a211` ("operational assets erweiterungen faelligkeit
  dokumente", siehe Abschnitt "Betriebsmittelverwaltung" -> "Vier Ergänzungen (seit 1.4.2)"
  unten), davor `ccb5c4c0915b` ("operational assets stufe 2 qr and public base url", Stufe
  2), davor `5917bb099776`
  ("operational assets betriebsmittel", Stufe 1), davor `da9d9425e257` ("project pipeline
  columns", siehe Abschnitt "Umbau der Projektliste" unten), davor `f803985ebc2f` ("property
  documents table", siehe
  Abschnitt "Dateiablage je Objekt" unten), davor `9137945e8785` ("document categories
  foundation"): keine der Versionen 1.3.52 bis 1.3.61 UND auch 1.4.8 UND auch 1.5.2 selbst
  brauchte eine eigene Migration (1.5.2: die Einspeisung des Betriebskosten-Vorschlags schreibt
  ausschließlich in bereits bestehende `LaborRateOverheadSettings`-Spalten, siehe Abschnitt
  "Betriebskosten-Übersicht" -> "Verrechnungssatz-Kreislauf Schicht 3" unten; 1.4.8: reine
  Rollen-Gate-/Response-Schema-/Audit-Redaction-Umstellungen auf bereits
  bestehenden Endpunkten und Tabellen, kein neues/geändertes Modell; 1.3.52-1.3.61: reine
  Rollen-Gate-/Response-Schema-/Objekt-Filterungs-Umstellungen auf bereits bestehenden
  Endpunkten und Tabellen; 1.3.61s neuer PDF-Dokumenttyp "field_timesheet" fällt ohne eigene
  Zeile automatisch auf den bereits bestehenden, geteilten "default"-Satz zurück, siehe "Fünf
  weitere Anpassungen"), siehe Abschnitt "Rechtekonzept" unten; bei Bedarf per `alembic
  history`/`heads` prüfen statt sich auf eine hier aufgeschriebene Liste zu verlassen.
- Tests: **1764 passed** (seit 1.3.55 wieder vollständig grün ohne `xfail` -- der Audit-Test des
  Rechtekonzepts steht bei null unklassifizierten Endpunkten und ist ein harter Test, siehe
  dort), zuletzt am 24.09.2026 (1.6.3, Beleg-Upload schon beim Anlegen einer Eingangsrechnung --
  reine Frontend-Änderung nach dem 1.5.6-Muster (Betriebsmittel), keine neuen Tests, dafür ein
  echter CDP-Browsertest gegen eine isolierte Testinstanz, siehe Abschnitt "Buchhaltung" ->
  "Beleg-Upload schon beim Anlegen" unten; davor 1.6.2, KI-Fundament -- zentrale,
  anbieterunabhängige Schnittstelle für künftige KI-Funktionen, 24 neue Tests
  (`tests/test_v295_ai_fundament.py`), siehe Abschnitt "KI-Fundament" unten; davor 1.6.1,
  Buchhaltung Stufe 2 (erster Teil) -- Kontenstamm und Vorkontierung, 23 neue Tests
  (`tests/test_v294_accounts_vorkontierung.py`), siehe Abschnitt "Buchhaltung" -> "Stufe 2,
  erster Teil" unten; davor 1.6.0, Buchhaltung Stufe 1 -- Eingangsrechnungen erfassen und
  ablegen, 31 neue Tests (`tests/test_v293_incoming_invoices.py`), siehe Abschnitt
  "Buchhaltung" unten; davor 1.5.11, "Diesem Gerät für 30 Tage vertrauen" -- 20 neue Tests
  (`tests/test_v292_device_trust.py`), siehe Abschnitt "Diesem Gerät für 30 Tage vertrauen"
  unten; davor 1.5.10, Neugestaltung der Seite Stundenverrechnungssatz -- reine
  HTML-/CSS-/JS-Umgestaltung, keine neuen Tests; davor 1.5.9, sinnvolle Pfeil-Schrittweiten auf
  den beiden Kalkulationsrechnern -- reine `step`-Attribut-Korrektur, keine neuen Tests, kein
  Backend-Verhalten geändert; davor 1.5.8, Ist-Werte im Produktivstunden-Rechner -- drei der fünf
  Annahmen bekommen einen aus TimeEntry/EmployeeAbsence/PlanningHoliday hergeleiteten
  Vergleichswert, siehe Abschnitt "Ist-Werte im Produktivstunden-Rechner" unten; davor 1.5.7,
  Betriebsmittel-Kosten fest als Kostenposten -- löst die 1.5.0-Doppelzählungs-Sonderbehandlung
  ab, siehe Abschnitt "Betriebsmittel-Kosten fest als
  Kostenposten" unten; davor 1.5.6, Dokument-Upload schon beim Erstellen des Betriebsmittels --
  reine Frontend-Änderung, keine neuen Tests, siehe Abschnitt "Betriebsmittelverwaltung" unten;
  davor 1.5.5, Netto und Brutto bei den Betriebskosten, siehe Abschnitt "Netto und Brutto
  bei den Betriebskosten" unten; davor 1.5.4, Krankheitssichtbarkeit -- buero_auftrag sieht nur
  noch "abwesend", siehe Abschnitt "Krankheitssichtbarkeit: buero_auftrag sieht nur noch
  'abwesend'" unten; davor 1.5.3, Grundlage für Ist-Werte -- Schlechtwetter-Zeitarten und
  Abwesenheitskategorie, siehe Abschnitt "Schlechtwetter-Zeitarten und Abwesenheitskategorie"
  unten; davor 1.5.2, Verrechnungssatz-Kreislauf Schicht 3 -- die Einspeisung
  des Betriebskosten-Vorschlags in die Gemeinkosten-Felder, siehe Abschnitt
  "Betriebskosten-Übersicht" unten; davor 1.5.1, dieselbe Schicht 3 -- Produktivstunden-Rechner +
  `overview_summary()`-Erweiterung; davor 1.5.0, Betriebskosten-Übersicht Schicht 1; davor 1.4.8,
  Rechtekonzept "Vier Rollen" Etappe 2 -- die Verengungen, siehe Abschnitt "Rechtekonzept" ->
  "Vier Rollen" unten; davor 1.4.7, Etappe 1 -- reine Rollen-Erweiterung) mit
  `pytest` in Tobias'
  `.venv` unter Windows
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

### Headless-Chrome-Verifikation über CDP (seit 1.3.73)

Dutzende frühere Versionen dieser Datei vermerken "kein Browser-Automatisierungswerkzeug
verfügbar" (kein Playwright/Puppeteer als Projekt- oder Systemabhängigkeit) und belegen
UI-Änderungen deshalb nur strukturell (Quelltext-/CSS-Prüfung, `node --check`). Für 1.3.73 wurde
das erste Mal geprüft, ob das wirklich stimmt -- Ergebnis: **Chrome UND Edge sind auf dieser
Windows-Maschine bereits systemweit installiert** (`C:\Program Files\Google\Chrome\Application\
chrome.exe`, `...\Microsoft\Edge\...`), auch wenn kein npm-Paket wie Playwright/Puppeteer im
Projekt oder global via npm vorhanden ist. Chrome lässt sich mit `--headless=new
--remote-debugging-port=<port>` gezielt für genau eine automatisierte Sitzung starten (eigenes
`--user-data-dir` im Scratchpad, unabhängig vom Profil des Nutzers) und über das Chrome
DevTools Protocol (CDP) fernsteuern -- **ohne** npm-Installation, da PowerShell/.NET bereits
einen WebSocket-Client mitbringt (`System.Net.WebSockets.ClientWebSocket`). Ablauf, der für
1.3.73 tatsächlich funktioniert hat: `GET http://127.0.0.1:<port>/json/list` liefert die
`webSocketDebuggerUrl` der Seite, `Network.setCookie` setzt das Session-Cookie (aus einem
vorherigen HTTP-Login übernommen -- kein UI-Login nötig), `Page.navigate` lädt die Zielseite,
`Runtime.evaluate` führt beliebiges JS aus (Klicks simulieren, Zustand auslesen), `Page.
captureScreenshot` liefert ein PNG zur visuellen Bestätigung. **Wichtig, sonst false positives**:
`Runtime.evaluate` mit `returnByValue:true` liefert bei einem JS-Fehler ein leeres Ergebnis statt
eines Fehlers, wenn `exceptionDetails` nicht explizit geprüft wird -- ein Test, der das
übersieht, hält einen kaputten Aufruf für "erfolgreich, aber leer". Ein eigens ausgeführter
Testlauf hätte ohne diese Prüfung fast einen Testfehler übersehen (siehe Abschnitt "Runde 2" bei
1.3.72 -- der erste Testdurchlauf für "letzte Zeile" schlug fehl, weil `.wrap.scrollTop=999999`
zwar den TABELLEN-eigenen Scroll ausreizt, aber die SEITE selbst (Kopfzeile+Toolbar+Karte)
zusätzlich Platz braucht, den ein echter Mausrad-Scroll durch Scroll-Chaining automatisch
mitnimmt, ein reines `.wrap.scrollTop=...` aber nicht -- `window.scrollTo(0,
document.body.scrollHeight)` musste ergänzt werden, sonst wurde ein tatsächlich unsichtbarer,
außerhalb des Ansichtsfensters liegender Knopf angeklickt, was kein reales Nutzerszenario
abbildet). **Kein dauerhaft installiertes Werkzeug, kein neuer Projektbestandteil** -- das
Skript lag nur temporär im Scratchpad dieser Sitzung, für eine künftige Sitzung ist diese
Fähigkeit (Chrome+CDP über PowerShell) neu zu bauen, aber jetzt als grundsätzlich funktionierender
Weg bekannt, bevor eine künftige Anfrage wieder pauschal auf "kein Browser verfügbar" verweist --
mindestens für gezielte, einzelne Verifikationen wie diese, nicht notwendigerweise praktikabel für
eine große Zahl laufender UI-Tests (deutlich aufwendiger als ein fertiges Test-Framework).

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
| Dienst | `erp.service`, `gunicorn -w 2 --timeout 120` |
| Sicherung | `/home/tobias/backup.sh`, täglich 2 Uhr UTC, 14 Tage Aufbewahrung |
| Notfallskripte | `scripts/reset_admin_2fa.py`, `scripts/migrate_sqlite_to_postgres.py` |

**Korrigiert (KI-Fundament-Runde, seit 1.6.2)**: diese Datei behauptete hier bisher fälschlich
"ein Arbeitsprozess, kein `--workers 2+`" -- am 22.09.2026 direkt gegen den echten `ExecStart`
der systemd-Unit auf dem VPS verifiziert: **zwei** Arbeitsprozesse (`-w 2`), explizites
`--timeout 120`. Woher die falsche Behauptung kam, lässt sich nicht mehr rekonstruieren (keine
Quellenangabe in der ursprünglichen Fassung) -- sie wurde nie gegen den echten Server geprüft,
bis zu diesem Zeitpunkt. Zwei Arbeitsprozesse bedeuten zwei unabhängige asyncio-Event-Loops mit
je eigenem Starlette-Threadpool (kein gemeinsamer Speicher, keine gemeinsame Warteschlange) --
die Gesamtkapazität ist dadurch GRÖSSER als bei einem Prozess, aber eine blockierte Event-Loop
legt jetzt "nur" die Hälfte der Kapazität lahm, nicht alles (siehe "KI-Fundament" ->
"Untersuchung" unten für die konkrete Auswirkung). Jede an dieser Stelle vorher gemachte
Speicherbudget-Begründung ("ein Worker, weil jeder zusätzliche den Speicherbedarf verdoppelt")
war demnach ebenfalls nicht (mehr) zutreffend für den tatsächlich laufenden Server -- ob das
4-GB-Budget mit zwei Workern tatsächlich knapp ist, ist an dieser Stelle nicht neu untersucht
worden, nur die Tatsachenbehauptung selbst korrigiert.

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

11. **Jeder neue `/api/`-Endpunkt braucht eine ausdrückliche Rollenangabe
    (`Depends(require_min_role(...))` aus `app/permissions.py` -- seit der Vier-Rollen-
    Erweiterung 1.4.7 die primäre, hierarchiebasierte Prüfart für die überwältigende Mehrheit
    der Fälle, siehe "Rechtekonzept" -> "Vier Rollen" --, das ältere, flache
    `Depends(require_role(...))` für echte, nicht-hierarchische Rollenmengen, oder das noch
    ältere `Depends(require_admin(...))` aus `app/deps.py`) -- Standardverweigerung, nicht
    Positivliste (seit "Rechtekonzept", siehe eigener Abschnitt unten für die volle
    Begründung).** Fehlt sie, gilt der Endpunkt als admin-only, nicht als für jeden
    Angemeldeten offen -- das ist die Umkehrung des tatsächlich wiederholt aufgetretenen
    Fehlers (`/users` seit 1.3.28, `EmployeeOut`-Lohnfelder seit 1.0.6, siehe dort): eine
    Positivliste (Sidebar/Menü zeigt einer Rolle nur, was für sie gedacht ist) lässt einen
    ungesicherten Endpunkt einfach für jeden funktionieren -- niemand merkt es, bis jemand
    gezielt danach sucht. `tests/test_v260_role_audit.py` erzwingt die Regel mechanisch: er
    geht jede registrierte Route durch und benennt jede ohne erkennbare Rollenprüfung
    namentlich -- ein vergessener Endpunkt fällt dadurch beim nächsten vollständigen
    Testlauf auf, nicht erst durch Zufall. Diese eine Prüfung bleibt bis zum Abschluss der
    dort dokumentierten Etappe 2/3 absichtlich rot (`xfail`, `strict=False`) -- ihre
    namentliche Liste ist die Checkliste für diese Etappe, kein Fehlerbefund.

12. **Testprozesse nie pauschal über den Namen beenden (`Get-Process chrome | Stop-Process`
    o. Ä.), sondern ausschließlich über die konkrete PID der selbst gestarteten Instanz.**
    Bei einer CDP-gesteuerten Headless-Chrome-Verifikation (1.5.10) wurde versehentlich
    `Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force
    -ErrorAction SilentlyContinue` ausgeführt, um vermeintlich verwaiste Testprozesse
    aufzuräumen -- das hat stattdessen JEDES `chrome.exe` auf der Maschine beendet,
    einschließlich des regulären, parallel geöffneten Chrome-Fensters des Nutzers (mit
    allen offenen Tabs). Tobias arbeitet auf demselben Rechner parallel mit seinem eigenen
    Browser -- ein namensbasiertes Beenden trifft dessen Fenster genauso wie die eigene,
    isolierte Testinstanz. Seither verbindlich: die PID des selbst per
    `Start-Process -PassThru` gestarteten Prozesses merken und ausschließlich
    `Stop-Process -Id <diese PID>` zum Aufräumen verwenden. Ist die PID nicht mehr bekannt
    (z. B. nach einem Sitzungswechsel), vor jedem Beenden über
    `Get-CimInstance Win32_Process -Filter "Name='chrome.exe'"` die vollständige
    Befehlszeile jedes einzelnen Treffers prüfen und ausschließlich Prozesse mit dem
    eigenen, eindeutigen `--user-data-dir`-Scratchpad-Pfad treffen -- nie ein bloßer
    Namensfilter ohne diese Prüfung, egal wie plausibel "das sind sicher meine
    Testprozesse" erscheint. Gilt sinngemäß für jeden anderen, für Tests/Automatisierung
    selbst gestarteten Prozess (nicht nur Chrome), auf dem der Nutzer möglicherweise
    parallel arbeitet.

13. **Nach jeder abgeschlossenen Runde wird committet, ohne dass Tobias das jedes Mal
    einzeln freigeben muss -- gepusht wird ausschließlich durch den Betreiber.** Vorher
    galt das nur als informelle, an einer einzelnen Stelle (Abschnitt "Produktivbetrieb")
    notierte Praxis dieser Sitzungen ("Claude Code committet, aber pusht nie ohne
    ausdrückliche Aufforderung") -- auf ausdrücklichen Wunsch jetzt als feste, durchgängige
    Regel festgehalten, damit für jede abgeschlossene Version (Regel 8: neuer `VERSION`-Stand
    + `CHANGELOG.md`-Eintrag) automatisch auch ein Commit entsteht, ohne dass jedes Mal erst
    nachgefragt werden muss. Ein Commit fasst dabei genau eine inhaltlich zusammenhängende
    Änderung, nicht mehrere unabhängige Themen gemeinsam (Vorbild: das eigene
    1.3.71-Vorgehen, dort ausdrücklich "eigener Commit, wie verlangt" für einen von der
    Hauptänderung unabhängigen Fund). `git push` bleibt davon ausgenommen und wird niemals
    von selbst ausgeführt -- das Hochladen auf den gemeinsamen Verlauf (und damit potenziell
    auf den Server, siehe "Produktivbetrieb") ist und bleibt ausschließlich eine Entscheidung
    des Betreibers.

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
  `entry_type` ist entgegen einer früheren Beschreibung KEIN hart geschlossener Satz (nur weich
  gegen `app/time_tracking.py::ENTRY_TYPES` geprüft) -- seit 1.5.3 kommen `weather_winter`/
  `weather_summer` (Schlechtwetter Winter/Sommer) dazu, beide `counts_as_productive=False`
  (`entry_type_is_productive()`), siehe Abschnitt "Schlechtwetter-Zeitarten und
  Abwesenheitskategorie" unten.
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
  Arbeitsvorbereitung. **Sichtbarkeit, zentral über EINE Stelle entschieden (seit 1.4.3, siehe
  Unterabschnitt "Sichtbarkeit für Büro-Konten" unten)**: `app/tasks.py::list_tasks_for_user()`
  ist der ausschließliche Einstiegspunkt -- eigene zugewiesene Aufgaben für ein Büro-Konto
  (serverseitig erzwungen, Kollegen-Aufgaben bleiben unsichtbar), Admin frei wählbar,
  empfängerlose Aufgaben zusätzlich für JEDES Büro-/Admin-Konto sichtbar. Drei
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
  - **Sichtbarkeit für Büro-Konten, "Übernehmen"/"Zurück in den Büro-Eingang" (seit 1.4.3)**:
    Anlass war der in 1.4.2 gemeldete Fund, dass eine unassigned Aufgabe für ein Büro-Konto ohne
    Admin-Rolle nach dem damaligen Filter unsichtbar blieb -- erst Befund (der Filter sitzt
    exakt an einer Stelle: `list_tasks()`, aufgerufen ausschließlich von `GET /api/tasks`),
    dann bestätigter Bauauftrag. `app/tasks.py::list_tasks_for_user(db, user, *, unassigned_only
    ..., employee_id=...)` ist seither die EINE Stelle für jede Task-Sichtbarkeitsentscheidung
    (Liste, Dashboard-Widget, jede Zählung) -- nutzt `has_role()` (`app/permissions.py`, neu die
    zentrale Rollenquelle für `require_role()` UND den Jinja-Global `can()`, statt eines
    zweiten, eigenen Wegs zur Rollenbestimmung -- genau das Muster, das bei
    `build_din5008_header_block()` bereits einmal zu drei divergierenden Varianten geführt hat,
    siehe "Kopfbereich"). `list_tasks()` bekommt dafür einen neuen, vorrangigen
    `unassigned_only: bool`-Parameter (`Task.assigned_employee_id.is_(None)`). Admin bleibt frei
    wählbar; ein Büro-Konto ist ohne `unassigned_only` weiterhin zwingend auf die eigene
    `employee_id` festgelegt (Kollegen-Aufgaben bleiben unsichtbar, unverändert); mit
    `unassigned_only=True` sieht JEDES Büro-/Admin-Konto den gemeinsamen Eingang, unabhängig von
    der eigenen `employee_id` -- das reine SEHEN braucht dafür keine Mitarbeiter-Verknüpfung
    (nur das Übernehmen selbst, siehe unten). Ein Monteur bekommt von `list_tasks_for_user()`
    stets eine leere Liste (die primäre Absicherung bleibt aber `require_role()` am Router --
    ein Monteur erreicht `GET /api/tasks` gar nicht, unverändert seit "Rechtekonzept").

    **"Übernehmen" weist fest zu, kein dritter Zustand**: `claim_task(db, task_id, user)`
    (`POST /api/tasks/{id}/claim`) setzt `assigned_employee_id` auf die eigene, verknüpfte
    `employee_id` -- exakt dasselbe Feld wie jede andere Zuweisung, keine zweite Zuweisungsart.
    Fehlt die Mitarbeiter-Verknüpfung, eine klare 400-Meldung, kein stiller Fehler -- derselbe
    Fall wie beim Monteur ohne `employee_id` an anderer Stelle. Eine bereits vergebene Aufgabe
    lässt sich nicht "übernehmen" (400) -- eine neue, bewusste Sperre gegen versehentliches
    Stehlen einer Kollegen-Aufgabe, die die bestehende PUT-Zuweisung nicht kennt. "Zurück in den
    Büro-Eingang" (`release_task()`, `POST /api/tasks/{id}/release`) setzt `assigned_employee_id`
    zurück auf `NULL`, bewusst OHNE Eigentümerschafts-Prüfung -- konsistent mit der bereits
    bestehenden, dokumentierten Lücke bei PUT/DELETE/archive/unarchive (kein Eigentümer-Check,
    siehe oben), keine isolierte Verschärfung nur hier.

    **Oberfläche**: neues, opt-in Dashboard-Widget "Offene Büro-Aufgaben" (`open_office_tasks`,
    `app/templates/dashboard.html`, Muster `due_maintenance`/`due_assets` -- NICHT im
    `DEFAULT_LAYOUT`) zeigt `GET /api/tasks?unassigned_only=true` mit einem
    "Übernehmen"-Button je Zeile, der nach Erfolg gezielt nur den eigenen Widget-Container neu
    rendert. "Meine Aufgaben" bleibt unverändert (ausschließlich eigene zugewiesene Aufgaben,
    nie unassigned). `/tasks` bekommt einen neuen Button "Zurück in den Büro-Eingang" im Editor,
    sichtbar nur bei bereits zugewiesener Aufgabe -- der Board-Fetch selbst (`loadTasks()`)
    bleibt für Nicht-Admin unverändert "nur eigene Aufgaben"; ein Monteur sieht dort weiterhin
    nichts (gesamte `/api/tasks*`-Familie bleibt Büro/Admin-only).

    **Angriffstest bestätigt** (`tests/test_v279_task_visibility.py`, 21 Tests): ein Monteur
    bekommt über `GET /api/tasks?unassigned_only=true` UND über die Claim/Release-Endpunkte --
    auch mit einer geratenen, nicht existierenden Aufgaben-ID -- durchgängig 403, bevor
    irgendeine Geschäftslogik läuft. Ein Büro-Konto sieht die empfängerlosen, aber nicht die
    persönlich zugewiesene Aufgabe eines Kollegen, auch nicht mit manipuliertem
    `employee_id`-Parameter. Die dabei transparent gemeldete, unabhängige Lücke in der
    Büro-Suche (`app/search.py::_search_tasks()` ohne Mitarbeiter-Filterung) ist seit 1.4.4
    behoben -- siehe Abschnitt "Büro-Suche" -> "Nachtrag (seit 1.4.4)" unten.

  - **Ziel-Mindestrolle für empfängerlose Aufgaben, `min_visible_role` (seit 1.5.0)**: allgemeine
    Erweiterung des obigen claim/release-Modells, nicht nur für die Betriebskosten-Übersicht
    gedacht -- Anlass war deren Kündigungsfrist-Erinnerung ("geht nur buero_finanzen etwas an,
    nicht die Auftragsbearbeitung"), aber das Feld liegt direkt auf `Task` und ist für jedes
    künftige Modul nutzbar. Neue, nullable Spalte `Task.min_visible_role: String(30)` -- `NULL`
    bedeutet unverändert "an jedes Büro-/Admin-Konto" (wie oben), ein gesetzter Rollenwert (z. B.
    `buero_finanzen`) grenzt eine empfängerlose Aufgabe zusätzlich auf diese Rolle UND alles
    Darüberliegende ein, geprüft über die bereits bestehende `has_min_role()`-Hierarchie
    (`app/permissions.py`, `ROLE_RANK`) -- **kein zweiter, eigener Rollenvergleich**, exakt die
    Vorgabe, das sauber ins bestehende Modell einzupassen statt eine Parallelstruktur zu bauen.
    `app/tasks.py::list_tasks_for_user()` filtert dafür JEDE zurückgegebene Zeile zusätzlich
    (`row.min_visible_role is None or has_min_role(user, row.min_visible_role)`) -- unbedingt,
    nicht nur im `unassigned_only`-Zweig, für Konsistenz (praktisch relevant wird es aber nur
    dort, da eine bereits einem Mitarbeiter zugewiesene Aufgabe ohnehin nur für diesen selbst
    oder Admin sichtbar ist). `create_task()`/`update_task()` validieren den Wert gegen `ROLES`
    (`app/permissions.py`), ein unbekannter String wirft `ValueError`.

    **`claim_task()` bekommt dafür ein zweites, eigenes Exception-Muster**: trägt die Aufgabe ein
    `min_visible_role`, das die übernehmende Person nicht erfüllt, wirft die Funktion
    `PermissionError` (NICHT `ValueError`) -- geprüft VOR der "bereits vergeben"-Prüfung, damit
    eine geratene Aufgaben-ID einer fremden Rolle immer dasselbe 403 liefert, unabhängig vom
    Zuweisungszustand. `app/routers/tasks.py::claim_task_endpoint()` fängt `PermissionError`
    separat ab und mappt es auf 403 -- getrennt von der bestehenden `ValueError` -> 400-Zuordnung
    für Geschäftsregeln (fehlende `employee_id`, bereits vergeben). `release_task()` bleibt
    bewusst UNVERÄNDERT ohne jede Rollenprüfung -- konsistent mit der bereits dokumentierten,
    akzeptierten Lücke bei PUT/DELETE/archive/unarchive oben, keine isolierte Verschärfung nur
    für dieses neue Feld.

    Erster echter Nutzer: `app/recurring_costs.py::check_due_cancellations_and_create_reminders()`
    setzt `min_visible_role=ROLE_OFFICE_FINANZEN` -- siehe Abschnitt "Betriebskosten-Übersicht"
    unten. Angriffstest dort: ein `buero_auftrag`-Konto sieht eine finanz-adressierte Aufgabe an
    keiner Stelle (weder in der Liste noch im gemeinsamen Eingang) und kann sie auch mit
    bekannter ID nicht übernehmen (403) -- `field` bleibt ohnehin über `require_role()` am
    Router vollständig ausgeschlossen, unverändert.
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
- **Monteursansicht** (`GET /mobil`, seit 1.3.0 -- bis 1.3.60 unter `/vor-ort`, siehe CLAUDE.md
  "Monteursansicht: Umbenennung zu /mobil" (1.3.61), `app/routers/field_view.py`,
  `app/templates/mobil.html`): eigene, schmale Einstiegsseite fürs Fahrzeug-Tablet statt einer
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
    unberührt. **`GET /mobil` selbst prüft die Grenze NICHT** (bewusste Abweichung von der
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
    `theme-color`/Apple-Touch-Icon-Tags sitzen AUSSCHLIESSLICH in `mobil.html`s `<head>` – das
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

## Diesem Gerät für 30 Tage vertrauen (seit 1.5.11)

Der zweite Faktor musste bis hierhin bei JEDER Anmeldung erneut eingegeben werden -- auf Wunsch
prüfbar/optional machen, ohne die eigentliche Pflicht (1.3.34) aufzuweichen: das Passwort bleibt
in jedem Fall bei jeder Anmeldung verlangt, nur die Code-Abfrage entfällt auf einem zuvor als
vertraut markierten Gerät für 30 Tage. Auf ausdrückliche Vorgabe erst ein reiner Befund (wie 2FA
und das Anmelde-Cookie heute funktionieren, ALLE Stellen im Code, die den zweiten Faktor oder das
Passwort ändern), dann nach Bestätigung gebaut.

### Befund: fünf Stellen ändern den zweiten Faktor oder das Passwort

Ein projektweiter Grep auf `password_hash\s*=|totp_confirmed_at\s*=|totp_secret_encrypted\s*=`
bestätigte Vollständigkeit über die reine Code-Lektüre hinaus. `two_factor.reset()`
(`app/two_factor.py`) ist eine einzige, gemeinsam genutzte Funktion mit ZWEI unabhängigen
Aufrufern (Admin-Reset eines ANDEREN Kontos, `POST /api/users/{id}/reset-two-factor`, UND das
Notfallskript `scripts/reset_admin_2fa.py`) -- ein einziger Hook dort deckt beide automatisch ab.
Dazu zwei Passwort-Stellen (`POST /api/account/change-password` für die eigene Änderung,
`PUT /api/users/{id}` für ein von einem Administrator für ein ANDERES Konto gesetztes Passwort --
letzteres der beim Befund gefundene, in der ursprünglichen Aufzählung nicht enthaltene fünfte
Fall: ohne ihn bliebe die Lücke, dass ein Admin-Passwortwechsel für einen anderen Nutzer dessen
vertraute Geräte stehen lässt). Der fünfte "Stellen"-Zähler zählt den ausdrücklichen Widerruf
("Alle vertrauten Geräte abmelden") als eigene, dritte Bedingung neben "2FA neu eingerichtet/
zurückgesetzt" und "Passwort geändert" mit -- macht rechnerisch: zwei Aufrufer von `reset()` +
zwei Passwort-Stellen + ein expliziter Widerruf = fünf Stellen insgesamt.

**Ersteinrichtung (`confirm_setup()`) ist bewusst KEINE der fünf Stellen** -- sie kann laut
Betreiberentscheidung ohnehin nur einmal auf einem noch unkonfigurierten Konto laufen
(`is_configured()`-Sperre in `start_two_factor_setup()`/`confirm_two_factor_setup()`); eine
"Neueinrichtung" existiert im Code nur als "erst `reset()`, dann `confirm_setup()` auf dem dann
wieder leeren Konto" -- bereits vollständig durch den `reset()`-Hook abgedeckt, kein eigener
sechster Fall.

### Server-seitig verwaltet, eigenständiges Cookie (`app/device_trust.py`)

Ein Cookie allein würde keinen Widerruf erlauben -- deshalb eine neue Tabelle
(`app/models.py::TrustedDevice`, `user_id`/`token_hash`/`expires_at`, `cascade="all,
delete-orphan"`-Relationship auf `AppUser`, Muster `TwoFactorRecoveryCode`) plus ein
DRITTES, von `dk_erp_auth`/`dk_erp_otp_ok` unabhängiges, signiertes Cookie (`dk_erp_trust`).
Anders als bei den beiden bestehenden Cookies trägt es aber keine HMAC-Signatur über
`secret_key()` -- unnötig, da der Cookie-Wert (Zeilen-ID + ein `secrets.token_urlsafe(32)`-
Geheimnis mit 256 Bit Entropie) selbst schon unforgeable ist: der Server vergleicht das
mitgeschickte Geheimnis gegen den in der Zeile gespeicherten Hash
(`hash_password()`/`verify_password()`, dieselbe Technik wie bei Wiederherstellungscodes --
das Geheimnis wird nie zurückgelesen, nur beim Prüfen verglichen). Migration `0f7bda3397f1`
(neue Tabelle, kein Regel-1-Fall -- keine NOT-NULL-Spalte auf einer bestehenden Tabelle).

`app/device_trust.py::create_trust(db, user)` legt eine neue Zeile an und liefert den fertigen
Cookie-Wert; `check_trust(db, user, cookie_value)` prüft Ablauf UND -- entscheidend für die
Konten-Isolation -- dass die geladene Zeile `user_id == user.id` trägt, bevor der Hash überhaupt
verglichen wird: ein (echtes oder gefälschtes) Cookie, das auf ein fremdes Konto zeigt, scheitert
so unabhängig vom Geheimnis; `revoke_all(db, user)` löscht alle Zeilen eines Kontos (aufgerufen
an allen fünf oben genannten Stellen). Gültigkeit ist FEST 30 Tage ab dem Setzen des Häkchens,
keine gleitende Verlängerung bei jeder erneuten Anmeldung.

### Checkbox nur bei der Routine-Bestätigung, nie bei der Ersteinrichtung

Auf ausdrückliche Betreiberentscheidung: die Checkbox "Diesem Gerät für 30 Tage vertrauen"
erscheint AUSSCHLIESSLICH bei `POST /api/account/2fa/verify` (neues Schema
`TwoFactorVerifyRequest(TwoFactorCodeRequest)` mit zusätzlichem `trust_device: bool = False`) --
niemals bei `POST /api/account/2fa/setup/confirm` (bleibt bei `TwoFactorCodeRequest` ohne dieses
Feld, ein untergeschobenes `trust_device` im JSON-Body wird von Pydantic stillschweigend
ignoriert). Begründung: bei der Ersteinrichtung sieht der Nutzer gerade zum ersten Mal die
Wiederherstellungscodes und baut den Schutz gerade erst auf -- ihn im selben Schritt für 30 Tage
auszusetzen wäre widersprüchlich, und wäre zudem inkonsistent mit der dritten Bedingung oben
(eine Neueinrichtung LÖSCHT alles Vertrauen über den `reset()`-Hook, direkt im selben Schritt
wieder eins zu setzen wäre in sich widersprüchlich). Das Vertrauen greift dadurch erst ab der
nächsten, zweiten Anmeldung.

**Before/after-Reihenfolge geprüft, wie vom Betreiber verlangt**: ein Widerruf darf nie ein im
selben Vorgang neu erzeugtes Vertrauen mittreffen. Bei den beiden Passwort-Stellen ist die
Reihenfolge im Code fest verankert -- erst `db.commit()` für den neuen `password_hash`, dann
erst `device_trust.revoke_all()` --, und da an keiner der beiden Stellen im selben Aufruf ein
neues Vertrauen entstehen kann (keine der beiden Endpunkte kennt `trust_device`), gibt es dort
grundsätzlich nichts, was kollidieren könnte. Bei `confirm_setup()` entsteht aus demselben Grund
(kein Häkchen an dieser Stelle) ebenfalls nie ein neues Vertrauen, das ein `reset()`-Aufruf
versehentlich mitlöschen könnte.

### Login-Integration: das Passwort bleibt unberührt, nur die Code-Abfrage entfällt

`POST /api/auth/login` (`app/routers/auth.py`) prüft weiterhin AUSSCHLIESSLICH Benutzername/
Passwort und setzt das Anmelde-Cookie IMMER. Neu: bei einem Administrator mit bereits
konfiguriertem zweiten Faktor wird zusätzlich ein mitgeschicktes `dk_erp_trust`-Cookie gegen
GENAU dieses Konto geprüft (`device_trust.check_trust()`) -- ist es gültig, wird das
`dk_erp_otp_ok`-Cookie direkt hier gesetzt statt (wie bisher unbedingt) gelöscht, und die
Antwort trägt ein neues `otp_ok`-Feld. `login.html` nutzt dieses Feld, um den bisherigen
Zwischenstopp auf `/account` zu überspringen (`(d.two_factor_required&&!d.otp_ok)?'/account':...`
statt zuvor nur `d.two_factor_required?...`) -- ein vertrautes Gerät landet dadurch direkt am
eigentlichen Ziel, nicht erst auf der Kontoseite.

### "Alle vertrauten Geräte abmelden"

Neuer, für jede angemeldete Person erreichbarer Endpunkt `POST
/api/account/trusted-devices/revoke-all` (Selbstbedienungsmuster wie `change_password()` --
`_current_user()`, keine feste Rollenprüfung, in `ROLE_AUDIT_EXEMPT` einzeln begründet wie
`change-password` direkt daneben) -- ruft `revoke_all()` für das EIGENE Konto auf und löscht das
eigene `dk_erp_trust`-Cookie. Button unter "Mein Konto" im 2FA-Statusbereich, mit `confirm()`
(Regel 4: kein `prompt()`, `confirm()` für eine einfache Ja/Nein-Bestätigung ist etabliert).

### Angriffstest

`tests/test_v292_device_trust.py` (20 Tests): `app/device_trust.py` isoliert (Rundlauf, Ablauf,
Kauderwelsch-/fehlendes Cookie, gefälschtes Geheimnis bei echter Zeilen-ID, Konten-Isolation,
`revoke_all()` trifft nie ein fremdes Konto und löscht mehrere eigene Geräte vollständig). Sowie
eine echte Ende-zu-Ende-Prüfung über einen eigens aufgebauten `TestClient` mit echten Cookies
(Muster `test_v250_two_factor_auth.py`): **jede der fünf Stellen einzeln** -- nach jeder von
ihnen ist ein zuvor vertrautes Gerät nachweislich wertlos, ein Login mit dem alten Cookie liefert
`otp_ok: false`, der Code wird wieder verlangt (zusätzlich zur Verhaltensprüfung auch direkt per
`device_trust.check_trust()` und einer leeren `TrustedDevice`-Abfrage bestätigt). Dazu eine
Gegenprobe (eine Änderung OHNE `new_password` an `PUT /api/users/{id}` lässt das Vertrauen
unangetastet -- die Revokation hängt am Passwort, nicht an jeder Änderung des Datensatzes), ein
gefälschtes/manipuliertes Trust-Cookie wird beim Login abgelehnt, und das Trust-Cookie eines
Kontos gewährt nachweislich nie Zugriff unter einem anderen Konto (inkl. der Umkehrprobe, dass
dasselbe Cookie beim RICHTIGEN Konto weiterhin funktioniert). Die Checkbox erzeugt bei
`confirm_setup()` in keinem Fall ein Vertrauen, selbst wenn das Feld im Request-Body
untergeschoben wird. Volle Suite: 1688 Tests grün.

## Serverseitige Anmeldeschranke für Seiten (seit 1.3.47)

Auf Nutzeranfrage geprüft: was passiert bei Aufruf von `/` ohne Anmeldung, `/` mit
Anmeldung, `/login` bei bestehender Anmeldung -- und ob nach dem Anmelden zur ursprünglich
gewünschten Seite zurückgeführt wird. Befund vor dieser Version: **keine** HTML-Seite prüfte
den Anmeldestatus serverseitig -- jede Seite (auch `/tasks`, `/settings`, `/` selbst) rendere
ihr Gerüst mit Status 200, unabhängig davon, ob jemand angemeldet war. Die einzige
Auswirkung fehlender Anmeldung war rein clientseitig: `_sidebar.html`s
`fetch('/api/auth/status')` zeigte dann nur ein Login-Formular im Fußbereich, der übrige
Seiteninhalt blieb (nutzlos) stehen. `/` mit Anmeldung zeigte bereits korrekt das Dashboard
-- aber nicht durch eine Weiterleitung, sondern weil `/` schon immer direkt `dashboard.html`
rendert (`dashboard_page()`, keine separate `/dashboard`-Route). `/login` bei bestehender
Anmeldung zeigte die Maske unverändert erneut -- `login_page()` prüfte den Anmeldestatus
gar nicht.

**Behoben, zwei Teile:**

1. **`app/main.py::_page_requires_login(has_users, method, path)`** -- bewusst eine neue,
   getrennte Funktion, NICHT in `_request_requires_login()` verschmolzen: eine `/api/`-Anfrage
   soll bei fehlender Anmeldung weiterhin die dortige 401-JSON-Antwort bekommen, nie einen
   Redirect auf eine HTML-Seite (ein API-Client könnte damit nichts anfangen). Greift nur bei
   `GET`, nicht `/api/...`, und lässt `/login` (sonst könnte sich niemand anmelden), `/health`
   (externe Überwachung, bereits zuvor ungated) und `/manifest.json` (reine PWA-Ressource der
   Monteursansicht, ohnehin nur von der bereits angemeldeten Seite `/mobil` aus verlinkt)
   sowie die bereits bestehende Bootstrap-Ausnahme (kein einziger ERP-Benutzer angelegt --
   `/users` muss für die allererste Kontoanlage erreichbar bleiben) unangetastet. In der
   Middleware (`identity_and_audit_middleware`) verdrahtet: ohne angemeldeten Benutzer liefert
   eine sonst betroffene Seite jetzt `302 → /login?next=<Pfad>` statt zu rendern.
2. **`app/routers/pages.py::login_page()`** -- leitet weiter, wenn `request.state.erp_user`
   bereits gesetzt ist: auf `/`, außer ein Administrator hat den zweiten Faktor noch nicht
   bestätigt (`not request.state.otp_ok`), dann auf `/account` -- dort ist ohnehin nichts
   anderes nutzbar (siehe `_blocked_pending_two_factor()`), ein Redirect aufs Dashboard hätte
   dort nur einen weiteren, überflüssigen Zwischenschritt über `_sidebar.html`s eigene
   Weiterleitung erzeugt.

**Rückführung zur ursprünglich gewünschten Seite (`?next=`), auf Nachfrage ergänzt** -- Kosten
waren minimal, da `login.html` einen solchen Parameter bereits liest und honoriert (bisher nur
für die bestehenden Abmelden-Links gebaut, siehe `_sidebar.html`/`_topbar.html`/
`_mobile_header.html`/`vor_ort.html`: `location.href='/login?next='+encodeURIComponent(
location.pathname)`). Der neue Redirect in `identity_and_audit_middleware` hängt dieselbe
Konvention an (`?next=<Pfad>`, ohne Query-String -- exakt wie bei jenen Links) -- keine
Template-Änderung nötig, `login.html`s Anmeldeformular führt danach automatisch zur
ursprünglich gewünschten Seite statt immer zu `/projects` (dem bisherigen Rückfall ohne
`next`, unverändert).

**Fallstrick beim Testen, selbst gefunden**: `tests/test_v218_template_rendering.py`
(`router_test_client()`, injiziert einen fest angemeldeten Admin-Kontext OHNE die produktive
Middleware) rendert JEDE Seiten-Route inkl. `/login` -- die neue `login_page()`-Logik griff
dabei auf `request.state.otp_ok` zu, das dieser Testaufbau nie setzt (nur die echte Middleware
tut das). `AttributeError` statt eines einfachen Testfehlers. Behoben durch
`getattr(request.state, "otp_ok", True)` statt direktem Attributzugriff -- robuster
Rückfallwert, passend zum bereits etablierten Muster in `app/deps.py::require_admin()`
(`getattr(request.state, "erp_user", None)`).

**Isolierter Ende-zu-Ende-Test** (`tests/test_v256_login_wall_for_pages.py`, Muster
`test_v250_two_factor_auth.py::_make_test_app()` -- eigene, throwaway In-Memory-SQLite-Engine,
eigene, aus den echten Funktionen `_page_requires_login()`/`_request_requires_login()`
nachgebaute Middleware, NICHT `router_test_client()`, das für "ohne Anmeldung"-Szenarien
ungeeignet ist): direkte Prüfung der Entscheidungsregel selbst (analog
`test_v106_access_control.py`), sowie über einen echten `TestClient` mit echten Cookies --
unangemeldeter Aufruf einer geschützten Seite liefert `302` mit korrektem `next=`, `/login`
selbst bleibt erreichbar und zeigt die Maske, `/health` bleibt ungated, die Bootstrap-Ausnahme
vor der ersten Kontoanlage greift, eine angemeldete Person erreicht Seiten direkt, `/login`
leitet eine bereits angemeldete Person weiter (auf `/` bzw. `/account` bei ausstehendem
zweitem Faktor). **Bewusst nicht end-to-end mit echtem Browser geprüft** (dieselbe, bereits
mehrfach dokumentierte Werkzeug-Einschränkung dieser Umgebung) -- `login.html`s eigene,
bereits bestehende JS-Auswertung von `next` (unverändert) lässt sich ohne echten Browser
nicht ausführen; die Tests belegen stattdessen den vollständigen SERVERSEITIGEN Anteil des
Rundwegs (korrekter `next`-Wert im Redirect, Zielseite nach der Anmeldung tatsächlich direkt
erreichbar).

### Fehlerbehebung (seit 1.3.48): zwei reale Fehler in der Umleitung, auf dem Produktivserver gefunden

**Fehler 1: `/login` leitete trotz bestehender, vollständiger Anmeldung nicht auf `next`
weiter.** `login_page()` (1.3.47) redirectete eine bereits angemeldete Person mit
bestätigtem zweitem Faktor immer auf `/`, unabhängig von einem mitgegebenen `?next=` --
behoben: liest `next` jetzt über die neue `_safe_next_target()` (siehe unten) und leitet
dorthin weiter, sonst weiterhin aufs Dashboard.

Die konkret gemeldete Beobachtung ("Anmeldemaske erscheint erneut, obwohl die Sitzung
besteht") hatte aber eine ANDERE, eigentliche Ursache, die dieser Fix allein nicht behoben
hätte: `account.html`s Link "← Zur Startseite" trug `onclick="if(document.referrer){
history.back();return false}"` -- während der 1.3.34-Zwei-Faktor-Pflicht zeigte
`document.referrer` dort auf `/login` (die Seite, von der `login.html`s JS nach der
Passwort-Eingabe auf `/account` weiterleitet). Ein Klick sprang deshalb über den
Browser-Verlauf zurück auf genau diese Login-Ansicht -- ggf. direkt aus dem bfcache, **ohne
jede Serveranfrage**, weshalb auch ein korrekt umleitendes `login_page()` das Symptom nicht
verhindert hätte: der Browser fragte den Server gar nicht erst. Behoben durch einen
einfachen `href="/"` ohne den `history.back()`-Zusatz -- "Zur Startseite" meint ein
konkretes Ziel, kein "zurück zur vorigen Seite" wie die sonst im Projekt üblichen
`history.back()`-Links (`users.html`, `master_data_form.html` u. a., dort unverändert
richtig, da deren Vorseite immer eine legitime, bereits angemeldete Seite ist).

**Fehler 2: nach Bestätigung des Codes landete man auf `/account` statt auf dem
eigentlichen Ziel.** `account.html::verifyCode()` (die ROUTINE-Bestätigung -- zweiter Faktor
war schon eingerichtet, nur diese Sitzung musste ihn noch bestätigen) rief nach Erfolg nur
`load()` auf, was lediglich die Kontoseite selbst neu zeichnete (zeigt dann "Passwort
ändern"/Zwei-Faktor-Status). Behoben: leitet jetzt auf `next` bzw. das Dashboard weiter.
**Bewusst unverändert**: die ERSTEINRICHTUNG (`confirmSetup()`/`finishSetup()`) bleibt auf
`/account` -- dort müssen erst die einmalig angezeigten Wiederherstellungscodes gesehen
werden, `/account` ist in diesem Fall das tatsächliche, gewollte Ziel, kein Zwischenschritt.
Damit `next` über den Zwischenschritt `/account` hinweg erhalten bleibt (vorher ging dabei
jede Information über das ursprüngliche Ziel verloren), hängt `login.html` beim Weiterleiten
auf `/account` jetzt `location.search` unverändert an.

**`_safe_next_target()`** (`app/routers/pages.py`, neu): da `login_page()` seit 1.3.48 einen
vom Client mitgegebenen `next`-Wert tatsächlich für einen SERVERSEITIGEN Redirect verwendet
(anders als `app/main.py`s Middleware, die `next` selbst aus dem aufgerufenen Pfad baut und
deshalb nichts validieren muss), wird der Wert vorher geprüft -- akzeptiert nur Werte, die
mit genau einem `/` beginnen, lehnt `//...` (protokoll-relativ) und absolute URLs ab. Ohne
diese Prüfung wäre ein serverseitiger offener Redirect entstanden (`?next=https://
evil.example/...`), eine strengere Gefahrenklasse als die bereits bestehende, rein
clientseitige `next`-Auswertung in `login.html` (dort schon seit früherer Version
ungeprüft, aber dort nur wirksam, wenn die Zielseite selbst dieses JS ausführt -- kein
neuer Fund, unverändert gelassen, siehe „Bekannte, bewusst offene Punkte").

**Geprüft, wie verlangt: `request.state.otp_ok` überall korrekt ausgewertet?** Projektweiter
Grep bestätigt genau drei Lesestellen: `app/main.py` selbst (setzt den Wert), `app/routers/
auth.py::auth_status()` und `app/routers/pages.py::login_page()` -- beide Leser nutzen
bereits `getattr(request.state, "otp_ok", True)` mit sicherem Rückfall (der zweite davon erst
seit 1.3.47, siehe dort für den Fund im Testaufbau, der genau diese Absicherung nötig
machte). Kein weiterer Fund.

**Tests** (`tests/test_v257_login_redirect_fixes.py`): vier Kombinationen (next: ja/nein ×
zweiter Faktor eingerichtet: ja/nein) für `login_page()`s Entscheidung bei bestehender
Anmeldung, sowie der vollständige serverseitige Rundweg für alle drei Anmeldewege (ohne
Zwei-Faktor, über die Ersteinrichtung, über die Routine-Bestätigung) -- jeweils bestätigt,
dass ein nachfolgender Aufruf tatsächlich zum ursprünglichen Ziel führt, nicht zurück nach
`/account`. Dazu `_safe_next_target()` isoliert sowie drei Strukturprüfungen der
Template-Quellen (next-Weitergabe in `login.html`, `verifyCode()` leitet weiter statt
`load()` erneut aufzurufen, der "Zur Startseite"-Link trägt kein `history.back()` mehr) --
die eigentliche JS-Navigation selbst lässt sich ohne echten Browser nicht ausführen
(dieselbe, wiederholt dokumentierte Werkzeug-Einschränkung dieser Umgebung).

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

### Nachtrag zu Schritt 2 (seit 1.3.46): mobiler Öffnen-Umschalter

Echter, vor Schritt 3 (Suche) gemeldeter und behobener Nebenbefund -- genau die Art Fehler, die
eine reine Struktur-/CSS-Prüfung ohne echten Browser leicht übersieht, weil sie nichts über
tatsächliche Bildschirmbreiten weiß, siehe unten für den dafür geschriebenen Test.

**Der Fund**: auf einem schmalen Bildschirm (`<1000px`) gab es keinen erreichbaren Weg, die
Off-Canvas-Sidebar überhaupt zu öffnen. Ihr einziger bisheriger Umschalter (`#appSidebarToggle`,
seit 1.3.44 unten in `.app-sidebar-utilities`) steckte selbst innerhalb von
`<aside class="app-sidebar">` -- im geschlossenen Zustand per `transform:translateX(-100%)`
komplett unsichtbar. Bereits in 1.3.45 als Nebenbefund vermerkt (siehe Schritt 2 oben, "vorher
UND nachher bestehend"), hier zuerst behoben.

**Lösung: ein zweiter Umschalter außerhalb der Sidebar.** Neuer `#appTopbarMenuBtn` in
`_topbar.html` -- als erstes Kind von `.app-topbar`, VOR dem für Schritt 3 reservierten
Suchen-Platzhalter (`.app-topbar-search-slot`), damit er auch bei geschlossener Sidebar
erreichbar bleibt (liegt in `.app-content`, nicht in `.app-sidebar`). Erscheint ausschließlich
unterhalb desselben Umbruchpunkts wie die Off-Canvas-Sidebar selbst (`max-width:1000px`, exakt
derselbe Wert wie in `_sidebar.html` -- ein abweichender Wert hätte ein Fenster geöffnet, in dem
der Knopf entweder sichtbar ist, aber nichts Erreichbares steuert, oder unsichtbar bleibt,
während die Sidebar bereits off-canvas ist). Auf Desktop-Breite `display:none`, braucht dort
keinen Platz -- der Suchen-Platzhalter bekommt seine volle Breite ungeschmälert; dieser
reservierte 38px-Knopf muss beim Bauen der Suche (Schritt 3) links mitgedacht werden.

Öffnet/schließt dasselbe Zustandspaar wie zuvor `#appSidebarToggle`
(`#appSidebar.mobile-open`/`#appSidebarScrim.visible`) -- Schließen per Klick auf den
Hintergrund bleibt unverändert bei `_sidebar.html`s bestehendem Scrim-Handler, der neue Knopf
synchronisiert dabei nur sein eigenes `aria-expanded`, damit es nach diesem Weg nicht fälschlich
`"true"` bleibt.

**Geprüft: ist der Umschalter unten aus 1.3.44 auf Mobilgeräten überhaupt noch sinnvoll?** Nein
-- auf Mobilgeräten gibt es kein Kollabieren im Desktop-Sinn (60px-Icon-Leiste), nur Auf/Zu der
Off-Canvas-Sidebar, und genau das übernimmt jetzt `#appTopbarMenuBtn`. `#appSidebarToggle`
blendet sich deshalb unterhalb des Umbruchpunkts vollständig aus (`.app-sidebar-toggle{display:
none}` innerhalb des bestehenden `@media(max-width:1000px)`-Blocks in `_sidebar.html`) --
zwei verschiedene Bedienungen für dieselbe Aktion nebeneinander wären verwirrender gewesen als
eine einzige, und die alte Beschriftung/Ikonografie ("Ein-/Ausklappen", drei horizontale
Striche) beschreibt auf Mobilgeräten ohnehin die falsche Handlung. Sein Klick-Handler verliert
dabei den jetzt toten `isMobile()`-Zweig (unerreichbar, da das Element selbst `display:none`
ist) -- bewusst entfernt statt als totes Code stehen zu lassen. **Bewusst NICHT** dieselbe Regel
wie die 1.3.44-Desktop-Prüfung (`.app-sidebar.collapsed .app-sidebar-toggle{display:none}`, die
bleibt unverändert abwesend/verboten -- dort geht es um das Kollabieren auf Desktop-Breite,
hier um eine komplett andere, mobile-spezifische Regel).

**Test, der genau diese Bildschirmbreiten-Invariante prüft** (`tests/test_v255_mobile_sidebar_
toggle.py`): nicht nur "der Knopf existiert irgendwo", sondern konkret, dass `#appTopbarMenuBtn`
außerhalb von `<aside id="appSidebar">` im Markup steht (die eigentliche Ursache des Fehlers),
dass er vor dem Suchen-Platzhalter steht, denselben Umbruchpunkt wie die Sidebar selbst nutzt,
dasselbe Zustandspaar toggelt wie zuvor `#appSidebarToggle`, `aria-controls`/`aria-expanded`
trägt und bei Klick auf den Hintergrund resynchronisiert, dass `#appSidebarToggle` unterhalb des
Umbruchpunkts tatsächlich verschwindet (und sein Klick-Handler den toten Zweig verloren hat,
ohne das Desktop-Kollabieren selbst anzufassen), und dass `/mobil` (damals `/vor-ort`) unverändert
ohne diesen Knopf bleibt.

### Aufräumen im Fußbereich (seit 1.3.49)

Im unteren Bereich standen noch Benutzername, "Mein Konto" und "Abmelden" -- alle drei bereits
seit Schritt 2 (1.3.45) über den Kontoknopf der Topbar erreichbar. Zwei Stellen für dasselbe
verwirren, alle drei entfernt: der untere Bereich zeigt jetzt nur noch die beiden
Schaltflächen (Hell/Dunkel, Ein-/Ausklappen) und die Versionsnummer.

- **`#appSidebarFoot` bleibt als Element bestehen**, rendert serverseitig aber für JEDEN
  Anmeldestatus leer (`{% if current_user %}...{% else %}...{% endif %}` entfällt, immer nur
  `<div class="app-sidebar-foot" id="appSidebarFoot"></div>`) -- es wird weiterhin gebraucht,
  aber nur noch für den einen verbleibenden Fall: eine Sitzung, die während des Browsens
  abläuft (Cookie verfällt, während der Tab offen bleibt), bekommt dort über
  `renderAuthFoot()`s bestehenden "nicht angemeldet"-Zweig (unverändert) ein kompaktes
  Anmeldeformular zurück, ohne die Seite neu laden zu müssen. Neue Regel
  `.app-sidebar-foot:empty{padding:0}` -- ohne sie hätte das jetzt immer leere Element trotzdem
  sein `padding:10px` behalten und eine unnötige, gepolsterte Leerstelle zwischen den beiden
  Schaltflächen und der Version aufgerissen.
- **Toter Code entfernt, nicht nur ausgeblendet**: `escHtml()` (diente ausschließlich dem
  Escapen von `display_name` beim JS-Aufbau des jetzt entfallenen Benutzernamen-Blocks),
  `bindLogout()` und die `LOGOUT_ICON`-Konstante (der einzige noch verbleibende Abmelden-Weg in
  diesem Include ist entfallen) sowie die CSS-Regeln `.app-sidebar-user`/`.app-sidebar-logout`
  (inkl. der eingeklappt-Sonderregel) -- alle hatten nach der Entfernung des SSR- UND des
  JS-gerenderten authentifizierten Fußbereichs keinen Aufrufer mehr.
- **Geprüft (wie verlangt): `/mobil` (damals `/vor-ort`) unangetastet.** `_mobile_header.html` hat einen
  komplett eigenständigen, unabhängigen Abmelde-Weg (`#mobileHeaderLogout`, eigene
  `.mobile-*`-CSS-Klassen ohne `app-sidebar`-Präfix) -- projektweiter Grep bestätigt, dass
  keine der entfernten Klassen/IDs (`app-sidebar-user`, `app-sidebar-logout`,
  `app-sidebar-account-link`, `appSidebarLogout`, `appSidebarFoot`) außerhalb von
  `_sidebar.html` selbst vorkommt.
- **Geprüft (wie verlangt): unterhalb des mobilen Umbruchpunkts.** Da `#appSidebarToggle`
  dort bereits seit 1.3.46 `display:none` ist, zeigt der untere Bereich auf einem schmalen
  Bildschirm jetzt tatsächlich nur noch die Hell/Dunkel-Schaltfläche (links ausgerichtet,
  passend zu den darüber ebenfalls linksbündigen Navigationseinträgen) und die Version darunter
  -- ein einzelner Icon-Button in einer eigenen Zeile ist ein unauffälliges, bereits an anderer
  Stelle im Projekt vorkommendes Muster (z. B. die eingeklappte Desktop-Sidebar zeigt ebenfalls
  einzelne, freistehende Icons), kein Sonderfall, der eine eigene Zentrierung o. Ä. gebraucht
  hätte. Kein echter Browser-Screenshot möglich (dieselbe, wiederholt dokumentierte
  Werkzeug-Einschränkung dieser Umgebung) -- nur strukturell geprüft.
- **Nebenbefund aus dem Auftrag**: der jetzt entfernte "Mein Konto"-Link
  (`.app-sidebar-account-link`) hatte keine eigene CSS-Regel und wäre als blau unterstrichener
  Browser-Standardlink erschienen, nicht im Design-System -- erledigt sich durch die
  Entfernung selbst. Auf Nachfrage projektweit nach demselben Muster gesucht (ein `<a>` ohne
  eigene Farb-/Unterstreichungsregel, weder über eine allgemeine `a{...}`-Regel im Datei-eigenen
  `<style>` noch über eine spezifische, tatsächlich definierte Klasse) -- vier weitere,
  unabhängige Funde, aber bewusst NICHT im selben Zug mitbehoben (anderer Ursprung, andere
  Dateien, kein Zusammenhang mit der Sidebar):
  - `account.html`: `<a href="/login">anmelden</a>` im "nicht angemeldet"-Hinweis (ohne Klasse,
    kein allgemeines `a{}` in dieser Datei).
  - `settings.html`: `<a href="/master-data#employees">Stammdaten → Mitarbeiter</a>` im
    Kalkulationsgrundlagen-Hinweistext (ohne Klasse, kein allgemeines `a{}`).
  - `service_reports.html`: der PDF-Öffnen-Link in `historyCard()` (Wartungshistorie-Panel) --
    eine zweite, unabhängige Kopie desselben Features, die (anders als die bereits über
    `.report-actions a{...}` gestylte erste Kopie) in einem unstyled `<div class="report-head">`
    landet.
  - `work_preparation.html`: der Datei-Öffnen-Link in `renderDelivery()` (Lieferschein-Tabelle)
    -- eine zweite, unabhängige Kopie desselben Features wie `deliveryTags()` (dort über
    `.delivery-tag a{...}` korrekt gestylt), hier ohne die umschließende Klasse.
  Alle vier folgen demselben Muster wie der ursprüngliche Fund: ein per JS-Template-String
  zusammengesetzter `<a>`, bei dem die passende CSS-Klasse beim Bauen vergessen wurde -- kein
  einzelner Ursprung, eher ein wiederkehrendes Risiko dieser Bauweise. Gemeldet, Behebung auf
  Rückmeldung.

#### Nachtrag (seit 1.3.50): die vier weiteren Funde behoben

Auf Rückmeldung nachgezogen -- alle vier bekommen eine allgemeine `a{color:var(--accent)}`
-Regel in ihrem eigenen `<style>`-Block, exakt das in `login.html` bereits etablierte,
einfachste Muster (recolort, behält den Standard-Unterstrich für einen normalen Inline-Text-
Link -- kein `text-decoration:none` wie bei den button-artigen Links dieses Design-Systems).
Bewusst KEINE HTML-Umstrukturierung (z. B. den `service_reports.html`-Link nachträglich in
`.report-actions` umzuhängen oder den `work_preparation.html`-Link in `.delivery-tag` zu
verpacken) -- beides hätte das Layout sichtbar verändert (Button-Optik bzw. Pill-Hintergrund
an einer Stelle, an der bisher ein einfacher Text stand), mehr als die angefragte, risikoarme
Farbkorrektur. Vor dem Schreiben jeweils per Grep bestätigt: der jeweils einzige unstyled
`<a>` in der betroffenen Datei -- alle bereits spezifischer gestylten Links (`.back`,
`.report-actions a`, `.top-actions a`, `.delivery-tag a`) bleiben durch die höhere
CSS-Spezifität ihrer eigenen Klassen unberührt, unabhängig von der Regel-Reihenfolge im
Stylesheet. Tests: `tests/test_v259_unstyled_link_audit.py`.

## Rechtekonzept (seit 1.3.51, Etappe 1+2)

Vorbereitung dafür, dass die kommenden Monteurskonten UND die für Schritt 3 der Sidebar-
Suche geplante Rollenfilterung auf echtem Boden stehen, nicht auf einer einzelnen `admin`-
Prüfung. Vier Etappen (siehe unten "Etappenplan"), diese Version deckt 1+2 ab und wurde vor
Etappe 3 bewusst zur Zwischenbestätigung angehalten.

### Befund vor dem Bauen

- **`AppUser.role`** (`app/models.py`) war schon immer eine unbeschränkte `String(30)`-Spalte
  ohne Datenbank-Constraint -- die einzige Einschränkung auf zwei Werte saß ausschließlich in
  Pydantic (`app/schemas.py`, `pattern="^(admin|user)$"`).
- **Reale Datenbank**: genau zwei Konten, beide `role="admin"`, beide aktiv -- Tobias mit
  verknüpftem Mitarbeiter, "Admin" als reines Systemkonto ohne Mitarbeiterverknüpfung. **Kein
  einziges `role="user"`-Konto existierte** -- die Monteurskonten, für die dieses Konzept
  gebaut wird, gab es zum Zeitpunkt dieser Untersuchung noch nicht.
- **Admin-geprüfte Bereiche** (`require_admin()`, zwölf Dateien): Benutzerverwaltung
  (Schreibzugriffe, nicht `GET /api/users` selbst), Adressimport, Zeiterfassungs-Backoffice,
  Freigabe von Abwesenheitsanträgen, Wartungsfenster-/Aufgaben-Spalten-Verwaltung,
  Modul-Umschalter, E-Mail-Einstellungen, Monteursansicht-Konfiguration -- ausschließlich
  Konfiguration/Verwaltung, keine fachlichen Kerndaten.
- **Alles andere prüfte nichts** -- für jeden angemeldeten Benutzer erreichbar: Kunden,
  Projekte, Angebote, Aufträge, Rechnungen, Mahnungen, Leistungen/Materialien (inkl.
  Einkaufspreisen), Mitarbeiter (inkl. `EmployeeOut.hourly_wage`/`effective_hourly_wage`/
  `annual_gross_wage`), Objekte, Dachflächen, Einsatzberichte, Änderungshistorie, u. v. m. --
  praktisch der gesamte fachliche Kern der Anwendung. Damit war der reale Zustand nicht
  "Admin gegen eingeschränkter Rest", sondern "Admin gegen Rest", und "Rest" hieß praktisch
  alles.
- **Der Modulschalter (`OPTIONAL_MODULES`, `app/modules.py`) bleibt eine andere, unveränderte
  Achse**: eine Zeile je `module_key` für die GANZE Installation, keine Verknüpfung zu
  `AppUser`/`role` an irgendeiner Stelle -- er entscheidet "ist die Funktion in diesem Betrieb
  eingeschaltet", nicht "darf diese Person sie nutzen". Beide Mechanismen bestehen unverändert
  parallel, keine Überschneidung.
- **`/vor-ort` heute**: die Seite selbst prüft nur die allgemeine Anmeldepflicht, keine Rolle.
  Die eigentliche Voraussetzung sitzt ausschließlich in `GET /api/field-view/today` -- der
  angemeldete `AppUser` muss ein `employee_id` tragen (422 sonst), danach sieht er
  ausschließlich seine eigenen heutigen Plantafel-Zuordnungen. Sobald er von dort in einen
  Einsatzbericht wechselt (`/orders/{id}/service-reports`), greift dagegen **keine** Prüfung
  mehr -- rein technisch könnte er heute jeden beliebigen Auftrag über die URL ansteuern, nicht
  nur seine eigenen (siehe "Objekt-Filterung" unten, Etappe 3).

### Drei Rollen: `admin` / `office` / `field`

Bewusst nicht mehr als drei -- bei einem Betrieb mit einem Büro und mehreren Monteuren
bräuchte eine frei konfigurierbare Rollenmatrix mit Einzelrechten mehr Verwaltungsaufwand als
Nutzen. `admin` behält alle bisherigen, admin-gateten Verwaltungsbereiche zusätzlich zu allem,
was `office` sieht. `office` ist fachlich das, was `role="user"` schon immer bedeutet hat --
voller Zugriff außer den zwölf Verwaltungsbereichen. `field` ist neu und deutlich enger, siehe
"Objekt-Filterung" unten.

`app/permissions.py::require_role(*rollen, message=...)` verallgemeinert
`app/deps.py::require_admin()` auf drei statt zwei Rollen -- **`require_admin()` selbst bleibt
unverändert bestehen**, an den zwölf Dateien, die es nutzen, wurde nichts geändert (es deckt
sich exakt mit `require_role("admin")`, kein Grund, etwas Funktionierendes anzufassen).

**Migration `7a2b4e9f1c3d`** (reine Daten-Migration): bestehende `role="user"`-Zeilen werden zu
`role="office"` -- auf der echten, lokalen Datenbank betraf das 0 Zeilen (siehe Befund oben),
die Migration existiert trotzdem für jede andere Installation. `downgrade()` kann `field` nicht
verlustfrei zurückführen (dieser Wert existierte im Zwei-Rollen-Modell nicht) -- sowohl
`office` als auch `field` werden beim Zurückrollen zu `user`, der nächstliegenden, am wenigsten
überraschenden Entsprechung.

### Standardverweigerung statt Positivliste -- der wichtigste Teil dieses Entwurfs

Der reale Befund oben (praktisch alles ungated) ist kein Einzelfall, sondern das erwartbare
Ergebnis einer **Positivliste**: die Sidebar/das Menü zeigt einer Rolle nur, was für sie gedacht
ist (z. B. der frühere admin-gatete `/users`-Sidebarlink, siehe 1.3.28) -- das fühlt sich nach
einer Absicherung an, ist aber nur eine Anzeige-Entscheidung. Ob der darunterliegende Endpunkt
selbst geprüft ist, ist eine ZWEITE, unabhängige Frage -- vergisst man sie, funktioniert der
Endpunkt einfach für jeden, ohne Fehler, ohne Auffälligkeit. Niemand merkt es, bis jemand
gezielt mit einer fremden Rolle danach sucht (exakt das, was die Suche-Bestandsaufnahme dieser
Sitzung getan hat).

Die Umkehrung ist eine **Negativliste**: Standardverweigerung. Ein Endpunkt ohne ausdrückliche
Rollenangabe gilt nicht als "offen", sondern als **admin-only**. Der entscheidende Unterschied:
mit dieser Umkehrung fällt ein vergessener Endpunkt beim ERSTEN Aufruf durch eine andere Rolle
auf -- sie bekommt sofort ein sichtbares 403, keine stille Funktion. Damit das nicht erst durch
einen zufälligen Praxisfall auffällt, erzwingt `tests/test_v260_role_audit.py` das bereits beim
nächsten vollständigen Testlauf: er geht jede registrierte `/api/`-Route durch (importiert dafür
jedes Modul unter `app/routers/` einzeln über `pkgutil` -- bewusst NICHT `app.main`, das würde
`Base.metadata.create_all()` gegen die echte, lokale `DATABASE_URL` auslösen, siehe
"Migrations-Workflow" unten) und listet jede Route ohne erkennbare `_dk_roles`-Markierung
(gesetzt von `require_role()`/`require_admin()`) namentlich auf. **Diese Regel ist jetzt
Regel 11** (siehe oben) -- jeder neue `/api/`-Endpunkt braucht ab sofort eine ausdrückliche
Rollenangabe, sonst schlägt der nächste Testlauf mit seinem Namen fehl.

Eine kleine, einzeln begründete Ausnahmeliste (`ROLE_AUDIT_EXEMPT` in `app/permissions.py`)
deckt die Fälle ab, die aus einem strukturellen Grund keine Rollenprüfung tragen können (Login
selbst, Zwei-Faktor-Ersteinrichtung, das eigene Passwort ändern -- für jede Rolle gedacht,
`GET /api/field-view/today` -- prüft stattdessen `employee_id`, das PWA-Icon) -- jeder Eintrag
dort ist einzeln kommentiert, kein bequemer Sammelplatz für "kommt später".

**Der Test blieb bis 1.3.54 absichtlich rot** (`@pytest.mark.xfail(..., strict=False)`, damit er
den Testlauf nicht insgesamt als fehlgeschlagen zeigte) -- seine Fehlerliste war die konkrete
Checkliste der Etappen 2/3: 1.3.51 klassifizierte drei Dateien als Nachweis
(`customers.py`/`invoices.py`/`reminders.py`, 43 Endpunkte), 1.3.52 den riskanten Batch,
1.3.54 Teil A, 1.3.55 Teil B. **Seit 1.3.55 steht er bei null und ist ein harter Test** (die
`xfail`-Markierung ist entfernt): ein neuer `/api/`-Endpunkt ohne Rollenangabe färbt den
nächsten vollständigen Testlauf rot -- genau die gewollte Standardverweigerung. Die neun
`ROLE_AUDIT_EXEMPT`-Einträge sind die einzigen rollenlosen Endpunkte, jeder einzeln begründet.

### Objekt-Filterung -- warum Rollen allein für `field` nicht reichen (Etappe 3, API-Seite seit 1.3.55 fertig)

Eine Rolle beantwortet "darf diese Person Finanzen/Kalkulation/Mitarbeiterdaten sehen" --
binär, für einen ganzen Funktionsbereich. Sie beantwortet NICHT "darf ein Monteur DIESEN
Auftrag/Bericht öffnen, nicht nur irgendeinen". Bis 1.3.54 prüften
`service_reports.py`/`findings.py`/`orders.py` genau das nicht -- ein `field`-Konto hätte jeden
beliebigen Auftrag über die URL erreichen können, nicht nur die eigenen.

**Die eine Definition (seit 1.3.55): `app/orders.py::field_may_access_order(db, employee_id,
order_id)`.** Vorgegeben war der Planungsbezug (Plantafel-Team-Besetzung, direkte Zuweisung an
der Arbeitsvorbereitung) mit der Auflage, zu prüfen, ob das vollständig ist -- war es nicht;
seit der Betreiber-Rückmeldung (1.3.56) lautet die Festlegung: **zwei Wege, Planungsbezug ODER
ein selbst angelegter Bericht, kein dritter, keine Vertrauensbasis** (Auftragsnummern sind
fortlaufend -- wer eine kennt, kennt alle; eine Zuordnung, die jeder umgehen kann, wäre
Dekoration). Zwei Funde, die sich aus dem Code ergaben, nicht aus der Vorgabe:

1a. **Team-Besetzung an der AV** (`WorkPreparationTeamAssignment` → Besetzungs-Schnappschuss
   `WorkPreparationTeamEmployee`) -- der Weg der Plantafel, denn jeder `PlanningSlot` hängt an
   genau so einer Zuweisung; geprüft wird aber an der AV, nicht am Slot, und OHNE den
   Datumsfilter von `list_todays_assignments_for_employee()`: ein vor Tagen begonnener
   Entwurfsbericht muss weiter bearbeitbar bleiben, ein für nächste Woche geplanter schon
   vorbereitet werden können. Die Tagesliste ist die datumsgefilterte Sicht auf dieselben
   Tabellen, keine dritte Quelle. **Bewusst an der Arbeitsvorbereitung geprüft, nicht am
   `PlanningSlot` selbst** (auf Nachfrage bestätigt, nicht verschärfen): ein Team, das einer AV
   bereits zugewiesen ist, aber noch keinen Termin im Kalender hat (`WorkPreparationTeamAssignment`
   existiert, aber kein `PlanningSlot` referenziert sie), soll den Auftrag schon sehen -- die
   Terminierung ist ein reiner Planungsschritt, keine Zugriffsentscheidung. Eine Prüfung, die
   zusätzlich einen `PlanningSlot` verlangt, würde genau den Fall verschärfen, der bei der
   1a./1b.-Herleitung bewusst ausgeschlossen wurde: die Tagesliste braucht den Slot nur für das
   Datum "heute", nicht für die Zugriffsfrage selbst.
1b. **Einzelzuweisung an der AV** (`WorkPreparationEmployee`) -- bewusst OHNE einen
   `PlanningSlot` vorauszusetzen: die Tagesliste braucht den Slot nur für das Datum, die
   Zuordnung selbst hängt an der AV. **Fund 1**: genau diese beiden Wege trug
   `app/time_tracking.py::employee_assigned_order_ids()` schon seit jeher als EIGENE, zweite
   Definition (Auftragsauswahl eines Nicht-Admins in der Zeiterfassung) -- seit 1.3.55 eine
   reine Weiterleitung auf `app/orders.py::_assigned_order_id_queries()`, damit Zeitbuchung
   und Berichtszugriff nie auseinanderlaufen (lokaler Import wegen Regel 3: `orders.py`
   erreicht über `invoices`/`projects` transitiv `work_preparation.py`, das `time_tracking.py`
   importiert).
2. **Eigener Bericht** (`ServiceReport.created_by_employee_id`) -- **Fund 2**: `/mobil` (damals
   `/vor-ort`) findet seine "offenen Entwurfsberichte" seit 1.3.0 über genau dieses Feld
   (`list_draft_reports_for_employee()`), unabhängig von jeder Planung. Ohne diesen zweiten Weg
   verlöre ein Monteur den Zugriff auf einen begonnenen Bericht, sobald das Büro ihn umplant
   oder aus dem Team nimmt -- die Monteursansicht zeigte den Entwurf noch, die Berichtsseite antwortete
   403 (exakt die Divergenz "Tagesliste ja, Bericht nein", die vermieden werden sollte).
   Bootstrappt nur über einen selbst angelegten Bericht: den ersten Bericht zu einem
   GEPLANTEN Auftrag legt an, wer über 1a./1b. zugeordnet ist; eine UNGEPLANTE Wartung startet
   ein Monteur vor Ort über "Wartung durchführen" (siehe unten, seit 1.3.56) -- der so erzeugte
   Bericht trägt ihn als Ersteller, das ist dann sein Zugriffsweg auf den neuen Auftrag.

Kein dritter Weg (geprüft): Monteure legen selbst keine Aufträge an (`quick_service_orders.py`
ist seit Teil A Büro/Admin; der Schnellauftrag hinter "Wartung durchführen" läuft in-process),
Zeitbuchungen setzen 1a./1b. bereits voraus, jede andere Verbindung Mitarbeiter ↔ Auftrag läuft
über eine der drei Tabellen oben.

**"Wartung durchführen" für Monteure (seit 1.3.56, Betreibervorgabe)**:
`POST /api/maintenance-contracts/{id}/perform-maintenance` war seit Teil A Büro/Admin -- ein
Monteur, der vor Ort eine ungeplante Wartung startet, hätte den Weg nicht gehabt. Jetzt
`require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD)`; `create_maintenance_visit()` bekommt
`created_by_employee_id` und setzt den Anfragenden als Ersteller des vorbereiteten Berichts
(dieselbe `_employee_for_request()`-Regel wie `POST /api/orders/{id}/service-reports`:
Nicht-Admin = eigene Mitarbeiterverknüpfung, Admin = keine). Ein `field`-Konto ohne
Mitarbeiterverknüpfung wird mit 403 abgelehnt -- der Bericht wäre sonst für niemanden
erreichbar, der ihn ausfüllen soll. Alle übrigen Endpunkte der Datei (Vertragsliste, Detail,
Bearbeitung, Historie, Einstellungen) bleiben Büro/Admin. **Korrigiert seit 1.3.59** (siehe
Abschnitt "Vertragsfinder auf /mobil" → "Fund: fremde Wartung per geratener Vertrags-ID"
unten): dieser Endpunkt prüfte bis dahin keine Zuordnung Monteur ↔ Vertrag, jeder Monteur konnte
den Vorgang für JEDEN Vertrag auslösen. Die ursprüngliche Einstufung dazu -- "legt einen Auftrag
an, Datenintegrität, kein Datenleck, so akzeptiert" -- ist überholt: ein Sicherheitstest hat
gezeigt, dass sich darüber echte Auftrags-/Projektdatensätze unter fremden Kunden anlegen
lassen, über fortlaufende, leicht erratbare IDs. Das ist Manipulation von Geschäftsdaten, keine
zu tolerierende Nebenwirkung -- `field_may_perform_maintenance()` schließt die Lücke, siehe dort.

**`sign_report()` unter dem neuen Konzept geprüft (1.3.56)**: die Unterschriftsroutine erzeugt
danach die "Rechnung erstellen"-Aufgabe (`create_task()`) und schreibt in Vertragsdaten
(`MaintenanceContract.next_due_date`) -- beides reine In-Process-Aufrufe; Rollen-Gates sitzen in
diesem Projekt ausschließlich als `Depends(...)` an Routern, nie in der Geschäftslogik. Ein
Monteur kann daran also nicht scheitern. Als Ende-zu-Ende-Test festgehalten
(`test_field_can_start_an_unplanned_maintenance_visit_and_sign_it`): Monteur startet die
ungeplante Wartung, unterschreibt über die echte Route, die Aufgabe entsteht, die Fälligkeit
rückt um `interval_months`.

**Anwendung**: `app/routers/orders.py::require_field_order_access(db, role, order_id)` ist die
eine Router-Stelle, die die Entscheidung in ein 403 übersetzt (Büro/Admin passieren ungeprüft,
ein `field`-Konto ohne Mitarbeiterverknüpfung wird immer abgelehnt) -- `service_reports.py` und
`findings.py` importieren sie. Endpunkte, die nicht über `order_id` laufen, lösen zuerst
`report_id`/`item_id`/`photo_id`/`material_id`/`finding_id` über `service_report_id` auf den
Auftrag auf (`_order_id_for_report()`/`_order_id_for_report_child()` in
`routers/service_reports.py`). `properties.py`/`roof_areas.py` brauchen keine Ableitung: seit
Teil A Büro/Admin, der Monteur liest Objekt und Dachflächen ausschließlich auftragsbezogen
(`GET /api/orders/{id}/property` bzw. `.../roof-areas`). Fremde und nicht existierende Aufträge
antworten für `field` gleichermaßen 403 (kein URL-Raten von Auftragsnummern); bei den
berichtsbezogenen Endpunkten kommt für eine nicht existierende `report_id` weiterhin das 404,
das der Endpunkt ohnehin gegeben hätte.

**Preisfreies Auftragsschema**: `GET /api/orders/{id}` liefert `field` ein `OrderFieldAccessOut`
(`app/schemas.py`) -- `id`/`order_number`/`customer_name`/`items[id, position_number, gaeb_oz,
short_text, unit]`, exakt was `service_reports.html` (Kopfzeile, LV-Auswahl für die Zeitbuchung)
und `time_tracking.html` (`ensureOrderItems()`) lesen; `order_to_dict()` hätte sonst
`unit_price`/`line_total`/Summen/Vertragstexte mitgeliefert. Ohne `customer_id` wird der
Kundenname in der Berichtsseite automatisch Text statt Link auf `/customers/{id}` -- der seit
1.3.51 vorgemerkte Punkt, ohne Rollenlogik im Template gelöst. Büro/Admin bekommen unverändert
das volle `OrderOut` (Union-Response-Model, Muster `list[EmployeeOut] | list[EmployeeNameOut]`).

**Wartungshistorie** (`GET /api/orders/{id}/property-service-reports`): ein Monteur sieht dort
gewollt frühere, unterschriebene Berichte ANDERER Aufträge desselben Objekts -- geprüft wird nur
die Zuordnung zum aktuellen Auftrag. **Seit 1.3.56 ein reduziertes Modell für `field`**
(`ServiceReportHistoryOut`, `list_property_history_for_field()`, Betreibervorgabe): Datum,
Berichtstyp, Monteur, Prüfergebnisse (Prüfpunkte mit Ergebnis/Zustand/Messwert/Bemerkung, je
Dachfläche), Mängel mit Status -- kein Beschreibungstext, kein Material, keine Unterschrifts-/
Vertrags-/Kundenfelder, keine Erledigungs-Verweise der Mängel (Folgeauftrag/Aufgabe sind
Büro-Vorgänge). Die Prüfpunkt-Bemerkung (`InspectionItem.notes`) zählt zum Prüfergebnis und
steht auf dem Kunden-PDF -- keine interne Bemerkung, deshalb enthalten. Das PDF eines fremden
Berichts bleibt für `field` über `require_field_order_access()` gesperrt (es trägt u. a. die
Zeitbuchungen der Kollegen), `service_reports.html::historyCard()` zeigt einem Monteur deshalb
Prüfergebnisse und Mängel inline statt des PDF-Links -- erkennbar an der Anwesenheit von
`inspection_items` in der Antwort, keine Rollenlogik im Template. Büro/Admin bekommen
unverändert das volle `ServiceReportOut` samt PDF-Link (Union-Response-Model wie bei
`GET /api/orders/{id}`). Per Test belegt (`test_maintenance_history_carries_no_prices_
purchase_values_or_customer_notes`): exakte Schlüsselmenge des reduzierten Modells, rekursiv
kein Preis-/Einkaufs-/Vergütungs-/Notiz-Schlüssel, Büro weiterhin mit Beschreibungstext.

**Zeiterfassung**: `?order_id=` in `GET /api/time-entries` liefert einem Monteur NICHT die
Buchungen der Kollegen -- `get_time_entries()` setzt für `ROLE_FIELD` `employee_id` auf die
eigene Person, `list_entries()` verknüpft beide Filter mit UND (geprüft, kein Fund, als Test
festgehalten); `_time_entry_can_edit()`/`_time_entry_employee_for_request()` verhindern
Ändern/Löschen fremder Zeilen und Buchen unter fremdem Namen. **Seit 1.3.56 gilt die
Lese-Eingrenzung nur noch für `field`** (vorher jeder Nicht-Admin, ein Vorher-Zustand aus der
Zeit vor dem Rechtekonzept): das Büro sieht die Buchungen aller, auch ohne eigene
Mitarbeiterverknüpfung -- es rechnet sie ab, `order.html`/`project_folder.html` lesen darüber
"alle Buchungen des Auftrags/Projekts" für "Rechnung aus Aufwand" und die Kennzahlen
(Betreiberentscheidung: "Die Summe über alle sieht das Büro"). Alle 13 Endpunkte tragen
`require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD)`, der Backoffice-Bereich
(`time_backoffice.py`) bleibt admin-only.

**Büro/Admin-only innerhalb der Teil-B-Dateien**: `GET /api/orders` (Liste), jede
Auftragsbearbeitung (`PUT`, Steuerschlüssel, Positionen, Abschnitte, Sync mit dem Quellangebot),
Revisionen, Auftrags-PDF und -Versand, `GET /api/orders/{id}/materials` (Rechnungsentscheidung
für `order.html`), `GET /api/findings` (auftragsübergreifende Mängelliste, `findings.html`),
`GET /api/roof-components/{id}/findings` (Bauteil-Mängelhistorie), die gesamte
Prüfvorlagen-Verwaltung inkl. Einzelansicht und Dachtyp-Standardzuordnung -- nur
`GET /api/inspection-templates` (Vorlagenliste) bleibt für `field` lesbar, `service_reports.html`
lädt sie für die Vorlagenauswahl.

### Vertragsfinder auf /mobil (seit 1.3.58 -- bis 1.3.60 /vor-ort): "Wartungen an meinen Objekten"

Zuletzt offener Punkt aus der Seiten-Klassifizierung (1.3.57): einem Monteur fehlte auf
`/vor-ort` (heute `/mobil`, siehe "Monteursansicht: Umbenennung zu /mobil", 1.3.61) der Weg,
einen Wartungsvertrag zu finden, um eine ungeplante Wartung zu starten --
"Wartung durchführen" (`create_maintenance_visit()`, seit 1.3.56 für Monteure erreichbar) sitzt
auf der Büro-Vertragsseite (`/maintenance-contracts/{id}`), die für `field` gesperrt ist. Ein
Monteur soll dabei NICHT die volle Vertragsliste durchsuchen können, aber die Objekte erreichen,
an denen er heute oder in Kürze zu tun hat -- Betreibervorgabe, vor dem Bauen als Vorschlag
vorgelegt und mit zwei Korrekturen bestätigt.

**Erst geprüft, wie verlangt: ist `WorkPreparation.status` zuverlässig genug, um "offene AV ODER
Zeitfenster" zu kombinieren?** Zwei Befunde, gegenläufig:
- Statisch UND tatsächlich beschreibbar: `PUT /api/orders/{order_id}/work-preparation`
  (`work_preparation.html`s `saveHeader()`, Büro/Admin) kann den Status jederzeit auf einen der
  fünf Werte setzen -- das Feld ist kein toter Code, anders als zunächst vermutet.
- Aber die reale, lokale Datenbank enthält für diese Prüfung nur **eine einzige**
  `WorkPreparation`-Zeile insgesamt (`status="offen"`) -- zu dünn, um "wird das im Alltag
  verlässlich gepflegt" empirisch zu beurteilen.
- Entscheidend gegen die Kombination: "offen ODER Zeitfenster" hätte das Risiko, das das
  Zeitfenster gerade vermeiden soll, an anderer Stelle wieder eingeführt -- eine AV, die
  tatsächlich fertig ist, aber nie manuell auf "abgeschlossen" gesetzt wurde (leicht zu
  vergessen, reines Büro-Freitextfeld ohne Zwang), bliebe dann unabhängig vom Datum sichtbar,
  exakt die Altlast, die vermieden werden sollte. **Ergebnis: Zeitfenster allein**, wie vom
  Nutzer selbst als Rückfall vorgegeben -- `WorkPreparation.status` fließt in
  `list_field_relevant_property_ids()` nirgends ein.

**`app/planning.py::list_field_relevant_property_ids(db, employee_id, window_days=14)`** -- die
eine Definition, welche Objekte relevant sind:
- Zuordnung an der AV (Team oder Einzeln) über die bereits bestehende
  `employee_assigned_order_ids()` (`app/orders.py`) -- dieselben Aufträge, über die auch die
  Zeiterfassung und `field_may_access_order()` entscheiden, keine dritte Definition.
- Datum: JEDER `PlanningSlot` dieser AV (`preparation_id`, unabhängig davon, über welchen der
  beiden Wege der Mitarbeiter zugeordnet ist -- ein Slot trägt keine `employee_id`) innerhalb
  ±14 Tage um heute. Fehlt jede Terminierung, `WorkPreparation.planned_start`/`planned_end` als
  Rückfall. Fehlt auch das, bleibt die AV unberücksichtigt -- kein Anhaltspunkt, kein Raten.
- Objekt-Auflösung: `order.project.property` geht vor, ohne verknüpftes Objekt die
  Hauptadresse-`Property` des Kunden (`is_primary_address`) -- damit ein Wartungsvertrag mit
  `property_id IS NULL` (bedeutet "Hauptadresse", `contract_to_dict()`) über denselben Abgleich
  gefunden wird.

**`app/maintenance_contracts.py::list_relevant_contracts_for_employee()`** -- gruppiert nach
Objekt, zeigt ALLE (nicht archivierten) Verträge des Objekts, `is_due` je Vertrag hervorgehoben
(zweite Nutzerkorrektur: "alle zeigen, fällige hervorheben", nicht nur die fälligen). Ein Vertrag
mit aktiven "Zu wartenden Dachflächen" unter `MaintenanceSettings.use_roof_area_items` wird
übersprungen -- `create_maintenance_visit()` lehnt "Wartung durchführen" dafür grundsätzlich ab
(reine Vertragsebene, siehe dort), ein Button, der zuverlässig mit einer Fehlermeldung endet,
wäre schlechter als gar keiner.

**Reduziertes Schema** (`FieldMaintenancePropertyGroupOut`/`FieldMaintenanceContractOut`,
`app/schemas.py`) -- erste Nutzerkorrektur: `property_name`/`customer_name` nur so weit, wie das
Objekt erkennbar wird. `customer_name` steht deshalb dabei (ohne ihn wäre "Hauptadresse" allein
niemandem zuzuordnen), aber weder Kundennummer noch Straße/PLZ -- nur `city` ("der Ort").

**`GET /api/field-view/maintenance-contracts`** (`app/routers/field_view.py`, `_any_role_dep` wie
`.../today`) -- löst den Mitarbeiter ausschließlich über `request.state.erp_user` auf. Fehlt die
Mitarbeiterverknüpfung oder ist das Modul "wartungen" aus, bewusst eine **leere Liste, kein
Fehler** -- dritte Nutzerkorrektur: die Karte "Wartungen an meinen Objekten" darf leer bleiben,
ohne zu stören. `mobil.html` zeigt bei leerer Antwort einen ruhigen Hinweistext (dasselbe
Muster wie die beiden bestehenden Karten bei "keine Einsätze"/"keine Entwürfe"), nie eine leere
Fläche. Klick auf "Wartung durchführen" ruft `POST /api/maintenance-contracts/{id}/perform-
maintenance` (seit 1.3.56 für Monteure offen) und navigiert direkt zu
`/orders/{order_id}/service-reports?report={report_id}` (Muster `maintenance_contract.html`).

### Fund: fremde Wartung per geratener Vertrags-ID (behoben seit 1.3.59)

Ein Sicherheitstest gegen eine isolierte Testinstanz (eigene, temporäre Datenbank, nie gegen die
echte `dachkonzepte_erp.db`) hat gezeigt: `POST /api/maintenance-contracts/{id}/perform-
maintenance` prüfte für `field` seit 1.3.56 zwar die Mitarbeiterverknüpfung, aber KEINE Zuordnung
zwischen Monteur und Vertrag. Ein Monteur konnte damit für JEDEN Vertrag -- fortlaufende,
leicht erratbare ID -- einen echten Auftrag samt Projekt und vorbereitetem Bericht unter einem
ihm völlig fremden Kunden anlegen. Die ursprüngliche Einstufung dieser Lücke ("legt einen
Auftrag an, kein Datenleck, so akzeptiert") ist damit überholt: das ist keine Frage vertraulicher
Daten, sondern eine Manipulation der Geschäftsdaten, über eine triviale ID-Iteration auslösbar --
genau der Angriff, den die Standardverweigerung des ganzen Rechtekonzepts verhindern soll.

**`app/maintenance_contracts.py::field_may_perform_maintenance(db, employee_id, contract_id)`**
zieht dieselbe Grenze wie der Vertragsfinder selbst: ein Monteur darf eine Wartung nur an einem
Objekt starten, das über `list_field_relevant_property_ids()` erreichbar ist -- also an einem
Objekt, an dem er über die Arbeitsvorbereitung tatsächlich aktuell oder in Kürze zu tun hat.
`contract_effective_property_id()` löst dafür denselben Hauptadresse-Rückfall auf wie
`contract_to_dict()` (ein Vertrag mit `property_id IS NULL` zählt über die Hauptadresse-`Property`
des Kunden). Der Router (`post_perform_maintenance()`) prüft das zusätzlich zur bestehenden
Mitarbeiterverknüpfung-Prüfung, ausschließlich für `field` -- Büro/Admin bleiben unbeschränkt.
Geprüft und mit einem zweiten Durchlauf desselben Angriffstests bestätigt: 0 "durchgelassen".

### Berichts-Eigentümerschaft: fremde Berichte auf einem gemeinsamen Auftrag (behoben seit 1.3.59)

Derselbe Sicherheitstest fand einen zweiten, schwerwiegenderen Fund: `require_field_order_access()`
prüft nur "gehört der AUFTRAG zu mir" -- auf einem Mehrpersonen-Auftrag (mehrere Monteure über
Team-Besetzung an der AV zugeordnet) reichte das für einen EINZELNEN Bericht nicht. Ein Monteur
mit legitimem Auftragszugriff konnte jeden Bericht eines Kollegen auf demselben Auftrag lesen
(volles Schema inkl. Freitext), ändern, löschen und sogar signieren -- dieselbe, ungeprüfte
Auftragsebene stand vor PUT/DELETE/sign UND vor Prüfpunkten, Fotos, Material und Mängeln.

**Trennung nach Zugriffsart** (Betreibervorgabe):
- **Lesen der Berichtsliste** (`GET /api/orders/{order_id}/service-reports`): bleibt für jeden
  mit Auftragszugriff erlaubt -- aber pro Bericht, nicht pro Auftrag. Der eigene Bericht
  (`created_by_employee_id` == der angemeldete Monteur) zeigt weiterhin das volle
  `ServiceReportOut` -- ohne das könnte ein Monteur seinen eigenen, noch nicht unterschriebenen
  Bericht nicht mehr bearbeiten, `service_reports.html` liest den Beschreibungstext zum
  Bearbeiten direkt aus dieser Liste, kein separater Einzelabruf davor. Jeder Bericht eines
  ANDEREN Erstellers kommt im reduzierten Schema der Wartungshistorie (`ServiceReportHistoryOut`,
  über `app/service_reports.py::list_reports_for_field()`, die dieselbe Konvertierungsfunktion
  wie `list_property_history_for_field()` wiederverwendet) -- keine vertraulichen Notizen, kein
  voller Freitext, keine Zeitbuchungen der Kollegen. Bewusst **kein** `response_model=list[A] |
  list[B]` auf der Route -- beide Schemata überlappen sich strukturell zu weit (dieselbe
  `roof_areas`-Liste, überwiegend optionale Zusatzfelder), um sich verlässlich auf Pydantics
  automatische Unterscheidung innerhalb EINER Liste zu verlassen; der Router wählt stattdessen
  je Zeile explizit das passende Schema und validiert einzeln.
- **Schreiben und Detailzugriff auf einen konkreten Bericht** (PUT/DELETE/sign, Prüfpunkte,
  Fotos, Material, Mängel, PDF): nur der Ersteller. Neue Funktion
  `app/routers/orders.py::require_field_report_ownership(db, role, report_id)` -- prüft zuerst
  wie bisher `require_field_order_access()` (derselbe Auftragsbezug), danach zusätzlich
  `report.created_by_employee_id == role.employee_id`. Büro/Admin bleiben unbeschränkt.

**Bewusste betriebliche Festlegung, keine technische Annahme** (auf Rückfrage, ob "nur der
Ersteller" zu eng ist -- könnten zwei Monteure legitim an einem Bericht arbeiten, einer beginnt,
der andere schließt ab?): in diesem Betrieb schreibt jeder Monteur seinen eigenen Bericht nach
getaner Arbeit, keine Fortführung durch einen Kollegen (Betreiberantwort). Ändert sich dieser
Ablauf, ist `require_field_report_ownership()` die Stelle, die dann von "Ersteller" auf "alle dem
Auftrag zugeordneten Monteure" (`employee_assigned_order_ids()`) erweitert werden muss -- nicht
der Auftragsbezug selbst, der bleibt richtig.

Betrifft `app/routers/service_reports.py` (PUT/DELETE/sign-Bericht, PDF, Prüfpunkte inkl.
regenerate/sync, Fotos, Material -- je Endpunkt einzeln mit einem Test belegt, der den Zugriff
eines Nicht-Erstellers ablehnt) und `app/routers/findings.py` (Mängel eines Berichts lesen/
anlegen, Nachverfolgung ändern -- Eigentümerschaft hängt am PARENT-Bericht, nicht an
`Finding.created_by_employee_id` selbst, da `InspectionItem` gar kein eigenes Ersteller-Feld
trägt und die Regel für alle Kind-Objekte eines Berichts einheitlich gelten soll). Mit einem
zweiten Durchlauf desselben Angriffstests bestätigt: 0 "durchgelassen", inklusive PUT/DELETE/
sign auf einem fremden Bericht.

### Zeiterfassung für Monteure (seit 1.3.60)

Bis dahin führte "Zeiterfassung" auf `/vor-ort` nur als Link auf die volle, sidebar-getragene
`time_tracking.html` -- für `field` seit der Seiten-Klassifizierung (1.3.57) zwar erreichbar
(eine der vier freigegebenen Seiten), aber mit der kompletten Büro-Oberfläche samt
Mitarbeiter-Umschalter-Optik und Gruppenbuchung, nicht der schmalen, handschuhtauglichen
Bedienung des restlichen `/vor-ort`. Befund vor dem Bauen (siehe eigener Befund-Austausch): die
API-Endpunkte in `app/routers/time_tracking.py`/`absence_requests.py` waren bereits vollständig
self-scoped (Rechtekonzept Teil B, 1.3.55/56) -- die Reduktion ist eine reine Darstellungsfrage,
keine Zugriffsfrage; `time_backoffice.html` (admin-only) bleibt die einzige echte Büro-Funktion
in diesem Bereich.

**Drei Betreiberentscheidungen, umgesetzt:**

1. **Manuelle Buchung/Nachtrag bleibt, aber abgespeckt.** Ein Monteur braucht sie ("merkt abends,
   dass er eine Stunde vergessen hat, oder korrigiert eine falsche"), aber nur für die eigenen
   Buchungen -- das leistete `_time_entry_employee_for_request()`/`_time_entry_can_edit()`
   bereits vorher, unverändert wiederverwendet. Feldliste in der neuen Maske: Auftrag (aus den
   eigenen Einsätzen), Datum, Von-Bis **oder** Dauer (Umschalter, Stunden werden clientseitig aus
   der Uhrzeitspanne berechnet -- `POST /api/time-entries` kennt in seinem Schema
   (`TimeEntryManualCreate`) gar kein `started_at`/`ended_at`, nur `hours`, anders als
   `create_manual_entry()` selbst, das beides könnte), Zeitart, Notiz. Kein Mitarbeiterfeld (immer
   die eigene Person -- `employee_id` wird trotzdem im Request mitgeschickt, da das Schema es
   verlangt, nur eben ohne sichtbares Feld, siehe Code-Kommentar in `time_tracking_field.html`),
   keine LV-Position, keine Pause-Minuten (nutzt `TimeTrackingSettings.default_break_minutes`
   still im Hintergrund, sofern konfiguriert). **Bekannter, bewusst nicht behobener Randfall**: ist
   `require_order_item`/`require_activity` im Backoffice aktiviert, verlangt der Server ein Feld,
   das die reduzierte Maske gar nicht anbietet -- die Anfrage schlägt dann mit einer klaren,
   bereits vorhandenen deutschen Fehlermeldung fehl (kein Absturz), aber ohne Weg, sie in dieser
   Maske zu beheben. Für diese Installation nicht relevant (beide Schalter stehen auf Default
   `False`), nicht eigens abgefangen.

2. **Auftragsauswahl: dasselbe ±14-Tage-Fenster wie der 1.3.58-Wartungsfinder, plus ein dabei
   gefundener echter Fund.** Neue Funktion `app/planning.py::list_field_bookable_order_ids()`
   nutzt exakt dieselbe, jetzt in `_relevant_preparation_ids_for_employee()` ausgelagerte
   Zeitfenster-Logik wie `list_field_relevant_property_ids()` (1.3.58) -- "was dort als 'meine
   Objekte' gilt, gilt hier als 'meine Aufträge'". Vor dem Bauen geprüft (Betreibervorgabe: "das
   Fenster muss den laufenden Einsatz sicher erfassen"): ein erst gestern zugewiesener, heute
   bearbeiteter Auftrag fällt zuverlässig ins Fenster, SOFERN die Arbeitsvorbereitung überhaupt
   ein Datum trägt (echter `PlanningSlot` oder `planned_start`/`-end`) -- für einen für heute
   terminierten Einsatz ist das bei jeder sinnvollen Fenstergröße der Fall, das war nie das
   eigentliche Risiko.

   Das eigentliche, von der Fenstergröße UNABHÄNGIGE Risiko: ein per "Wartung durchführen"
   (`create_maintenance_visit()`, seit 1.3.56 auch für Monteure) gestarteter, ungeplanter Auftrag
   hat GAR KEINE `WorkPreparation` -- `create_quick_service_order()` legt bewusst keine an (kein
   Plantafel-Bezug). Ein solcher Auftrag taucht in `employee_assigned_order_ids()` und damit in
   keinem Zeitfenster jemals auf, unabhängig von dessen Größe -- ein zu enges Fenster hätte das
   nicht gelöst, ein beliebig großes auch nicht. `list_field_bookable_order_ids()` ergänzt deshalb
   UNGEFENSTERT jeden Auftrag, zu dem der Monteur bereits selbst einen `ServiceReport` angelegt
   hat (`created_by_employee_id`) -- exakt der zweite der beiden Wege, über die
   `field_may_access_order()` (`app/orders.py`) ohnehin schon Zugriff gewährt. Ohne diese Ergänzung
   hätte ein Monteur nach "Wartung durchführen" zwar seinen Bericht öffnen, aber nie Zeit auf den
   dafür entstandenen Auftrag buchen können -- exakt die Divergenz, die `field_may_access_order()`
   an anderer Stelle bereits ausdrücklich vermeidet.

   `GET /api/field-view/time-tracking/orders` (`app/routers/field_view.py`) liefert die
   aufgelöste Liste (id/order_number/customer_name/property_address, dieselben Felder wie
   `time_tracking_context()` für die volle Seite) -- löst den Mitarbeiter ausschließlich über
   `request.state.erp_user` auf, kein `employee_id`-Parameter, bewusst eine leere Liste statt
   eines Fehlers ohne Mitarbeiterverknüpfung (Muster `GET /api/field-view/maintenance-contracts`).

3. **Gruppenbuchung komplett entfernt, Abwesenheitsantrag bleibt.** Ein Monteur bucht nur für
   sich -- die neue `time_tracking_field.html` enthält keinerlei Gruppenbuchungs-Markup, keinen
   Aufruf von `/api/time-entry-groups*`. **Offener Punkt, hier bewusst festgehalten (Betreiber-
   vorgabe):** in der Praxis bucht eine Kolonne trotzdem oft gemeinsam -- dafür bleibt vorerst nur
   der Weg über die volle `time_tracking.html` (Büro/Admin). Ob und wie ein Kolonnenführer künftig
   selbst gruppenbuchen darf (z. B. eine vierte Rollenausprägung oder ein Team-Attribut
   "Kolonnenführer"), ist eine eigene, spätere Entscheidung -- nicht Teil dieser Version.
   Abwesenheitsanträge dagegen sind unverändert self-service (siehe `absence_requests.py`, bereits
   seit dem Rechtekonzept korrekt eingegrenzt) und stehen in der reduzierten Ansicht wie in der
   vollen.

**Die Weiche hängt an der Rolle, nicht am Weg.** Auf ausdrückliche Vorgabe geprüft: es gibt DREI
unabhängige Linkquellen zu `/time-tracking` (`_sidebar.html`, `_mobile_header.html`,
`service_reports.html`s `#timeLink` mit `?order_id=`) -- eine Lösung über eine zweite Route (z. B.
`/vor-ort/zeit`) hätte alle drei einzeln anpassen müssen und wäre bei jeder künftigen, neuen
Verlinkung erneut anfällig. Stattdessen bleibt die URL `/time-tracking` für jede Rolle identisch --
`app/routers/pages.py::time_tracking_page()` entscheidet servereitig anhand der AKTUELLEN
Sitzungsrolle (`_role.role`, das `AppUser`-Objekt aus `require_role()`), welche Vorlage gerendert
wird: `time_tracking_field.html` für `field`, unverändert `time_tracking.html` sonst. Damit gilt
automatisch, ohne dass ein einziger Link geändert werden musste: ein Büro-Konto, das testweise als
`field` unterwegs ist (oder umgekehrt), sieht bei JEDEM Aufruf -- Sidebar-Link, altes Lesezeichen,
eingetippte Adresse, `?order_id=`-Link -- exakt das, was die aktuelle Rolle vorsieht, nie einen
Zwischenstand aus einer früheren Rolle. Da es dieselbe, bereits `_dk_roles`-markierte
`require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD)`-Dependency wie zuvor bleibt (nur die
Template-Wahl im Funktionskörper ist neu), bleibt `/time-tracking` unverändert eine der vier für
`field` freigegebenen Seiten -- der Audit-Test (`test_v260_role_audit.py`) prüft davon unberührt
weiter.

**Punkt 4 der Anfrage, ausdrücklich geprüft: die volle Seite ist für `field` jetzt strukturell
unerreichbar, nicht nur standardmäßig anders.** Es gibt keine zweite URL, unter der
`time_tracking.html` unabhängig von der Rolle gerendert würde -- `time_tracking_page()` ist die
EINZIGE Stelle im Code, die diese Vorlage lädt. Ein Monteur, der `/time-tracking` über die
Adresszeile eintippt oder ein altes Lesezeichen (aus der Zeit vor 1.3.60) öffnet, bekommt
serverseitig immer `time_tracking_field.html` -- der im vorherigen Screenshot gezeigte Zustand
(volle Sidebar) ist danach für `field` nicht mehr erreichbar, unabhängig vom Weg dorthin.

### Fünf weitere Anpassungen an der Monteursansicht (seit 1.3.61)

Fünf rollenbezogene Punkte, alle ohne neues Datenmodell außer Punkt 4 (siehe dort -- am Ende doch
keine neue Tabelle, nur ein neuer, bereits bestehender Mechanismus zweitverwendet).

**Punkt 1 -- Umbenennung und neue URL: `/vor-ort` → `/mobil`.** `/vor-ort` entfällt ersatzlos
(keine Weiterleitung -- der Nutzer hatte ausdrücklich bestätigt, dass es keine Lesezeichen darauf
gibt), `app/routers/pages.py::field_view_page()` ist jetzt unter `/mobil` registriert und rendert
`app/templates/mobil.html` (umbenannt und erweitert aus `vor_ort.html`, das gelöscht wurde,
Titel "DACHKONZEPTE GmbH - Mobil"). Geprüft, wie verlangt, ob im Code irgendwo `/vor-ort`
VERLINKT ist (nicht nur in Prosa erwähnt) -- alle drei tatsächlichen Linkquellen aus 1.3.60
gefunden und mitgezogen:
1. `app/mobile_manifest.py::build_manifest()` -- `start_url` jetzt `/mobil`.
2. `app/templates/login.html` -- der clientseitige Rückfall ohne `next`
   (`d.role==='field'?'/mobil':'/projects'`).
3. `app/permissions.py::default_home_page_for_role()` -- die eine, gemeinsame Quelle für
   `login_page()`, den 403-Exception-Handler UND (neu, siehe Punkt 2) `dashboard_page()`.

`app/templates/_mobile_header.html` verlinkte selbst nicht auf `/vor-ort` als Ziel (die Einträge
sind bereits relativ zur aktuellen Seite, `path == '/mobil'` statt eines hartkodierten Strings),
musste also nur den Vergleichswert mitziehen. Reine Docstring-/Kommentar-Erwähnungen in rund
einem Dutzend weiterer Dateien (`app/service_reports.py`, `app/models.py`, `app/orders.py`,
`app/mobile_settings.py`, `app/schemas.py`, `app/routers/quotes.py` u. a.) wurden für
Stellen korrigiert, die LAUFENDES Verhalten beschreiben (z. B. "GET /mobil prüft die
Feierabend-Grenze NICHT") -- rein historische "Neu seit 1.3.X"-Einträge weiter oben in dieser
Datei bleiben unverändert bei `/vor-ort`, da sie beschreiben, was zu jenem Zeitpunkt tatsächlich
gebaut wurde (Regel 8/etablierte Konvention dieser Datei), siehe z. B. "Neu seit 1.3.57"/
"Neu seit 1.3.58" oben. Der Abschnitt "Vertragsfinder auf /vor-ort" (1.3.58) heißt seither
"Vertragsfinder auf /mobil" -- er ist ein aktiver Querverweis aus mehreren Code-Kommentaren
(`app/maintenance_contracts.py`, `app/routers/maintenance_contracts.py`), keine reine
Versionshistorie, deshalb umbenannt statt unverändert gelassen.

**Punkt 2 -- Startseite für Monteure.** `app/routers/pages.py::dashboard_page()` (`GET /`) trug
bisher `_role_dep` (Büro/Admin, 403 für `field`) -- jetzt `_any_role_dep`, mit einer Weiche im
Funktionskörper: `if _role.role == ROLE_FIELD: return RedirectResponse(default_home_page_for_role(...))`,
sonst unverändert das Dashboard. Deckt beide vom Nutzer genannten Fälle in einer einzigen
Prüfung ab -- nach dem Anmelden (über `login_page()`s bereits bestehende Weiche) UND ein von
Hand eingetipptes `/` (über `dashboard_page()`s neue Weiche), da beide dieselbe
`default_home_page_for_role()`-Funktion nutzen. Kein drittes Verhalten neben "gesperrt"/"offen"
-- die Rolle entscheidet das Ziel, nicht der Weg (exakt die vom Nutzer vorgegebene Formulierung).
`tests/test_v260_role_audit.py::test_field_reaches_only_the_five_pages_it_needs` prüft seither
für `/` einen 302 auf `/mobil` statt eines 403.

**Punkt 3 -- Tätigkeit im Nachtrag, PRÄMISSE KORRIGIERT.** Der Nutzer nannte als Ausgangspunkt
"der Schnellstart hat schon ein Tätigkeitsfeld, der Nachtrag noch nicht" -- beim Nachsehen im
tatsächlichen `time_tracking_field.html` (Stand 1.3.60) stimmte das nicht: WEDER Schnellstart
NOCH Nachtrag hatten ein Tätigkeitsfeld, nur die "Zeitart"-Kacheln (Baustelle/Fahrzeit/Werkstatt/
Sonstige) existierten -- "Tätigkeit" ist ein davon unabhängiges Konzept
(`time_entry_activities`-Optionsgruppe, z. B. "Dacheindeckung", "Reparatur"), das bei der
1.3.60-Reduktion bewusst aus BEIDEN Abschnitten weggelassen worden war. Diese Diskrepanz wurde
vor der Umsetzung transparent gemacht, nicht stillschweigend nach der einen oder anderen Seite
aufgelöst. Umgesetzt wie vom Nutzer für den Korrekturfall verlangt ("ergänze es, mit denselben
Werten wie im Schnellstart"): ein neues, optionales `<select id="quickActivity">` UND
`<select id="manualActivity">`, beide befüllt aus derselben `time_entry_activities`-Optionsgruppe
wie die volle `time_tracking.html` (`safeOptionGroup('time_entry_activities', ...)`, Werte/Label
identisch zum Vorbild). Kein Backend-Fund nötig -- `TimeTimerStart`/`TimeEntryManualCreate`
(`app/schemas.py`) kannten `activity: str | None` schon immer, `_time_entry_*`-Endpunkte
verarbeiteten es bereits korrekt, nur die reduzierte Maske hatte kein Feld dafür.

**Punkt 4 -- Stundenzettel.** Neue Seite `/mobil/stundenzettel` (`field_timesheet_page()`, eigene
Seite statt eines weiteren Kartenabschnitts auf `/mobil` -- Monatswahl/Liste/PDF-Knopf passen
strukturell nicht zum einfachen Karten-Muster der übrigen Abschnitte dort). Vor dem Bauen
geprüft, wie verlangt: der bestehende Büro-Stundenzettel (`app/time_backoffice.py::
build_timesheet_pdf()`, admin-only, `GET /api/time-backoffice/timesheet.pdf`) ist ein
ALTER, eigener `SimpleDocTemplate`/`landscape(A4)`-Renderer, der den gemeinsamen PDF-Rahmen aus
dem 1.3.1–1.3.20-Umbau NIE genutzt hat (vor oder unabhängig davon entstanden) -- er konnte also
nur als inhaltliche Vorlage dienen (Spaltenauswahl Datum/Auftrag/Zeitart/Tätigkeit/Stunden,
Tagessummen-/Gesamtsummenzeilen, Gruppierung je Mitarbeiter), nicht als Code-Vorbild für den vom
Nutzer ausdrücklich geforderten "gemeinsamen Rahmen ... mit Briefkopf".

Neuer, dedizierter Renderer `app/field_timesheet_pdf.py::build_field_timesheet_pdf(db,
employee_id, year, month) -> bytes` -- nutzt `render_framed_pdf()` mit einem KOMPLETT NEUEN
`document_type="field_timesheet"` (erstmals seit `service_report` in 1.3.11 wieder ein Typ ohne
jede Vorgeschichte), eingetragen in `DOCUMENT_TYPES` (`app/document_layout.py`) UND
`RENDERERS_USING_SHARED_FRAME` (`app/document_frame.py`) -- ohne beide Einträge wirft
`render_framed_pdf()`/`ensure_default_layout()` einen `ValueError` (Muster exakt wie 1.3.11
dokumentiert). Fällt ohne eigene Zeile automatisch auf den geteilten `"default"`-Briefpapier-/
Rand-/Bausteinsatz zurück (`resolve_shared_document_type()`) -- **kein neues Datenmodell, keine
Migration**, entgegen der ursprünglichen Erwartung "Punkt 4 könnte eine Ausnahme brauchen": der
bereits bestehende Rückfallmechanismus aus 1.3.6 reicht vollständig aus. Portrait statt Landscape
(anders als der Büro-Stundenzettel), fünf Spalten (Datum/Auftrag/Zeitart/Tätigkeit/Stunden statt
neun), `build_din5008_header_block()` mit dem Mitarbeiternamen als "Empfänger" (DIN-5008-korrekt
für ein personenbezogenes Dokument) und der Personalnummer als zusätzlicher Meta-Zeile, sofern
gesetzt. Zeitart-Beschriftungen kommen server-seitig aus `get_option_group(db,
"time_entry_types")` (dieselbe Optionsgruppe, dieselbe Auflösung wie clientseitig in
`time_tracking_field.html`), keine hartkodierte Fallback-Tabelle im PDF selbst.

Kein neuer JSON-Endpunkt für die Bildschirmansicht -- bewusste Entscheidung: `field_timesheet.html`
ruft direkt das bereits bestehende, für `field` self-scoped `GET /api/time-entries?start_date=&
end_date=` auf (seit 1.3.56 self-scoped, siehe "Objekt-Filterung" oben) und gruppiert client-seitig
nach Tag. Nur die PDF-Erzeugung braucht zwangsläufig einen serverseitigen Weg: neuer Endpunkt
`GET /api/field-view/timesheet.pdf?year=&month=` (`app/routers/field_view.py`, `_any_role_dep`),
löst den Mitarbeiter ausschließlich über `request.state.erp_user` auf (kein Client-Parameter --
ein Monteur kann so nie den Stundenzettel eines Kollegen abrufen), Standard ist der laufende
Monat, 422 statt 500 ohne Mitarbeiterverknüpfung (anders als die übrigen, bewusst leer statt
fehlerhaft antwortenden Listen-Endpunkte dieser Datei -- ein Stundenzettel-PDF ohne Mitarbeiter
ergibt keinen Sinn, eine leere Liste dagegen schon).

**Punkt 5 -- Eigene Plantafel-Einträge ("Meine kommenden Termine").** Neuer Kartenabschnitt
direkt auf `/mobil` (bewusst KEIN eigener Reiter/keine eigene Seite wie bei Punkt 4 -- eine
einfache, datumssortierte Liste passt strukturell zu den drei bestehenden Kartenabschnitten
"Heutige Einsätze"/"Offene Berichte"/"Wartungen an meinen Objekten", anders als Punkt 4s
Monatswahl+PDF-Knopf). Neue Funktion `app/planning.py::list_upcoming_assignments_for_employee(db,
employee_id, *, today=None, days_ahead=30)` -- dieselbe Zuordnung wie die bereits bestehende
Tagesliste (`_employee_assignment_slot_condition()`, seit 1.3.61 aus
`list_todays_assignments_for_employee()` in eine gemeinsame, jetzt zweitverwendete Hilfsfunktion
ausgelagert, ebenso `_slot_query_with_order_options()`/`_slot_to_assignment_dict()`), aber über
ein Zeitfenster (±30 Tage voraus) statt eines einzelnen Tages. Bewusst `PlanningSlot.end_date >=
today` (nicht `start_date >= today`) -- ein bereits laufender, mehrtägiger Einsatz bleibt
sichtbar, auch wenn sein Slot vor dem Fensterbeginn angefangen hat; dieselbe Überlegung, die
schon bei der Tagesliste selbst gilt. Neuer Endpunkt `GET /api/field-view/upcoming`
(`app/routers/field_view.py`, `_any_role_dep`) -- löst den Mitarbeiter ausschließlich über
`request.state.erp_user` auf, bewusst eine leere Liste statt eines Fehlers ohne
Mitarbeiterverknüpfung (Muster `GET /api/field-view/maintenance-contracts`, da diese Karte kein
Kernbestandteil der Seite ist wie die Tagesliste). `mobil.html` rendert die Zeilen als reine,
NICHT anklickbare Karten (`<div>` statt `<a>`, anders als "Heutige Einsätze") -- bewusste, kleine
Abgrenzung, die die vom Nutzer betonte "reine Leseansicht, kein Zugriff auf die Plantafel selbst"
optisch unterstreicht, auch wenn ein Klick technisch ohnehin nirgends hinführen würde.

Geprüft, dass die volle Plantafel für Monteure gesperrt bleibt: `GET /planning`
(`app/routers/pages.py`) trägt weiterhin `_role_dep` (Büro/Admin, unverändert seit der
1.3.57-Seiten-Klassifizierung), `GET /api/planning` und die übrigen Endpunkte in
`app/routers/planning.py` tragen weiterhin `_role_dep` = `require_role(ROLE_ADMIN, ROLE_OFFICE)`
(unverändert seit Rest-Etappe Teil A, 1.3.54) -- keiner der fünf Punkte dieser Runde berührt
diese Datei.

**Der vom Nutzer verlangte, wiederholte Angriffstest** (`tests/test_v265_mobile_rename_and_extras.py::
TestVollePlantafelBleibtGesperrt`, gegen eine isolierte Testinstanz, nie gegen die echte
Datenbank): volle Plantafel-Seite (`/planning`) UND volle Plantafel-API (`GET /api/planning`,
`GET /api/planning/settings`) liefern für `field` weiterhin 403; ein `field`-Konto, das
`?employee_id=<Kollege>` an `GET /api/time-entries` anhängt, bekommt trotzdem nur die eigenen
Stunden zurück (die bestehende, seit 1.3.56 geltende Überschreibung greift unverändert); ein
`field`-Konto sieht über `GET /api/field-view/upcoming` nie die kommenden Plantafel-Einträge
eines Kollegen. Alle vier Fälle mit einem zweiten Testdurchlauf bestätigt: null "durchgelassen".
1267/1267 Tests grün.

### Kundendaten für einen Monteur: ausschließlich über den Bericht, nicht über eine Kundenseite

Enger gefasst als eine reine Rollen-Sperre auf `/customers/*`: ein Monteur soll Kundendaten nie
über eine eigene Seite oder eine Adresse mit Kunden-ID sehen, sondern ausschließlich das, was
im Einsatzbericht selbst steht. Geprüft, ob das inhaltlich schon vollständig ist -- war es
NICHT: `Order`/`ServiceReport` trugen Objektname/Anschrift (als Schnappschuss), aber weder
einen "Zugang" (Schlüssel, Codes, Hunde, Parken) noch einen vom Kunden-Hauptansprechpartner
unabhängigen "Ansprechpartner vor Ort" (Hausverwaltung vs. tatsächlich anzutreffende Person).

Ergänzt: `Property.access_notes`/`site_contact_name`/`site_contact_phone` (Migration
`1ccb91b19e8a`, alle nullable, bewusst NICHT das bestehende `notes`-Feld umgewidmet, um dort
bereits erfasste Freitexte nicht umzudeuten) -- gepflegt auf der Objektseite (`property.html`),
gelesen über einen neuen, auftragsbezogenen Weg **ohne** `/api/properties/{id}`:
`GET /api/orders/{order_id}/property` (`app/routers/service_reports.py`, Geschäftslogik
`get_property_context_for_order()` in `app/service_reports.py`, löst wie
`list_roof_areas_for_order()` über `order.project.property_id` auf) -- LIVE gelesen, kein
Schnappschuss, da sich ein Torcode/eine Kontaktperson ändern kann, ohne dass deshalb ein neuer
Auftrag entsteht. `service_reports.html` zeigt das in einer neuen Karte "Objekt & Zugang"
oberhalb des Berichts-Editors, sichtbar für jeden, der die Seite heute schon erreicht (Etappe 3
schränkt erst ein, WER die Seite erreicht -- die Anzeige selbst ist unabhängig davon richtig).

**Seit 1.3.55 gelöst, ohne Template-Änderung**: der Kundenname-Link in derselben Seite
(`document.getElementById('breadcrumb')`, `o.customer_id ? <a href="/customers/{id}"> : Text`)
wird für einen Monteur zu reinem Text, weil `OrderFieldAccessOut` (die Antwort von
`GET /api/orders/{id}` für `field`) bewusst kein `customer_id` trägt -- dieselbe Entscheidung wie
bei `PropertyAccessOut`, und keine Rollenlogik im Template nötig (Anmerkung "ausblenden, nicht
ausgrauen"). Der "Auftrag"-Link daneben (`/orders/{id}`, eine Büro-Seite) führt seit 1.3.57 für
einen Monteur auf `access_denied.html` (die Seite ist jetzt gesperrt, siehe "Seiten-
Klassifizierung" unten) -- kein Datenleck (die API dahinter war es ohnehin nie), aber ein
unnötiger Zwischenstopp; bewusst nicht mitgefixt, siehe „Bekannte, bewusst offene Punkte".

### Seiten-Klassifizierung (seit 1.3.57): dieselbe Standardverweigerung wie bei der API

Bis hierhin war ausschließlich die API rollengeprüft -- jede der (damals) 31 Seiten-Routen in
`app/routers/pages.py` rendierte ihr Gerüst für JEDE angemeldete Rolle, unabhängig davon, ob
die API-Aufrufe dahinter für diese Rolle überhaupt etwas lieferten. Für einen Monteur bedeutete
das: er konnte `/customers/{id}`, `/finanzen`, `/maintenance-contracts` usw. öffnen und sah eine
leere oder fehlerhafte Seite (die API-Aufrufe scheiterten längst mit 403) -- kein Datenleck, aber
auch keine echte Sperre, nur eine im Sidebar-Menü versteckte Tür, die trotzdem offen war. Auf
ausdrückliche Vorgabe geschlossen: **eine Seite, die eine Rolle nicht öffnen darf, muss
serverseitig sperren, nicht nur im Menü fehlen.**

- **Mechanismus, wiederverwendet statt neu erfunden**: `app/permissions.py::require_role()`
  trägt bereits die `_dk_roles`-Markierung (für den Audit-Test) und braucht für seine Prüfung
  nur `request.state.erp_user` -- exakt das, was auch eine Seiten-Route hat, keine
  Sonderfassung nötig. Jede Seiten-Route in `app/routers/pages.py` bekam deshalb schlicht
  `_role: AppUser = _role_dep` (Büro/Admin) bzw. `_any_role_dep` (jede Rolle) als zusätzlichen
  Parameter -- dieselben zwei Konstanten wie an jeder API-Datei dieser Etappe.
- **Fünf Seiten für `field`, jede andere Büro/Admin** (bei Einführung 1.3.57 waren es vier --
  `/mobil/stundenzettel` kam erst mit 1.3.61 dazu, `/vor-ort` heißt seit derselben Version
  `/mobil`, siehe "Monteursansicht: Umbenennung zu /mobil"): `/account`, `/mobil`,
  `/mobil/stundenzettel`, `/time-tracking`, `/orders/{order_id}/service-reports` -- exakt die
  Seiten, die ein Monteur tatsächlich braucht (Selbstbedienung, seine Einstiegsseite, sein
  eigener Stundenzettel, seine Zeitbuchung, sein Bericht). Jede andere
  Seite (Kunden, Objekte, Dachflächen, Projekte, Angebote/Aufträge/Rechnungen/Mahnungen,
  Stammdaten, Einstellungen, Aufgaben, Wartungsverträge, Prüfvorlagen, Mängelliste, Änderungs-
  historie, Adressimport, Zeiterfassungs-Backoffice) ist Büro/Admin -- gespiegelt an der bereits
  bestehenden API-Klassifizierung der jeweiligen Fachdomäne, keine neue Entscheidung.
  `/time-backoffice` und `/address-import` trugen bereits vorher `Depends(require_admin(...))`
  (admin-only) und blieben unverändert -- `require_admin()` markiert `_dk_roles` schon lange.
- **`/users` ist die einzige Seite mit einer bespoken Dependency statt `require_role(...)`**
  (`_require_users_page_access()`, `app/routers/pages.py`): exakt derselbe Bootstrap-Fall wie
  `POST /api/users` -- vor dem allerersten ERP-Benutzer gibt es niemanden, der eine Rollenprüfung
  erfüllen könnte, danach Büro/Admin wie die Benutzerliste selbst. Trägt deshalb keine
  `_dk_roles`-Markierung und steht einzeln begründet in der neuen `PAGE_AUDIT_EXEMPT`
  (`app/permissions.py`) -- zusammen mit `/login`, `/health`, `/manifest.json` (dieselben drei
  strukturellen Ausnahmen wie bei der API, jetzt für Seiten).
- **403 zeigt `access_denied.html`, nicht rohes JSON**: ein neuer Exception-Handler in
  `app/main.py` (`_role_check_403_shows_access_denied_page()`, registriert für `HTTPException`)
  fängt jeden 403 ab und rendert für Nicht-`/api/`-Pfade das bereits in Etappe 1 vorbereitete,
  aber nie verdrahtete `access_denied.html` -- jeder andere Statuscode und jeder `/api/`-Pfad
  läuft unverändert über FastAPIs eigenen Standard-Handler (`http_exception_handler`, daran
  delegiert, keine Kopie). "Zur Startseite" zeigt auf `app/permissions.py::
  default_home_page_for_role(role)` -- `/mobil` (bis 1.3.60 `/vor-ort`) für `field`, sonst `/` --,
  außer der Aufruf war anonym (nur im Bootstrap-Fall möglich, `_page_requires_login()` leitet
  sonst schon vorher auf `/login` um): dann auf `/users`, die einzige in diesem Zustand
  erreichbare Seite.
- **Login-Landing für `field` korrigiert, an zwei Stellen**: `default_home_page_for_role()`
  wird auch von `login_page()` genutzt (bereits angemeldeter Aufruf von `/login`, vorher
  hartkodiert `"/"`) -- ohne diese Korrektur hätte ein Monteur nach dem zweiten Login-Versuch
  auf einer jetzt gesperrten Seite gelandet. `login.html`s eigener, client-seitiger Rückfall
  ohne `next` (`"/projects"`, JS, kein gemeinsames Modul mit Python) bekam denselben Zweig
  separat dupliziert (`d.role==='field' ? '/vor-ort' : '/projects'`) -- die beiden
  unterschiedlichen Nicht-Feld-Rückfälle (`/` server-seitig, `/projects` client-seitig) sind
  ein bereits bestehender, dokumentierter Unterschied (siehe 1.3.47/1.3.48) und wurden nicht
  vereinheitlicht, nur jeweils um den `field`-Zweig ergänzt.
- **Ein vorher unbemerkter Test-Fund**: `tests/test_v256_login_wall_for_pages.py::make_user()`
  erzeugte Konten mit `role="user"` (der Rollenname vor dem Rechtekonzept) -- harmlos, solange
  keine Seite eine Rolle prüfte. Zwei Tests dieser Datei (bereits angemeldeter Nutzer erreicht
  `/`/`/tasks` direkt) schlugen mit der neuen Sperre entsprechend fehl, bis der Standard auf
  `role="office"` (den direkten Nachfolger von `"user"`) korrigiert wurde -- kein Fund an der
  neuen Logik selbst, ein veralteter Testfixture-Wert.
- **Audit-Test deckt jetzt beide Ebenen ab**: `tests/test_v260_role_audit.py::
  test_all_page_routes_have_an_explicit_role_check()` (Muster der API-Variante, dieselbe
  `_iter_role_marked_dependants()`-Hilfsfunktion, jetzt parametrisiert auf `/api/`- vs.
  Seiten-Routen) steht bei null unklassifizierten Seiten-Routen, direkt als harter Test (kein
  `xfail`-Zwischenschritt wie bei der API-Fassung, da hier von Anfang an vollständig gebaut).
  Eine zweite Testgruppe (`TestPageRouteClassification`) belegt stichprobenhaft, dass die
  Rollen dabei auch tatsächlich richtig zugeordnet sind (der Audit-Test allein sieht nur "trägt
  eine Markierung", nicht "die richtige") -- inkl. eines isolierten Tests für den neuen
  Exception-Handler selbst (HTML für Seiten, unverändert JSON für `/api/`, korrekter
  `home_url`-Wert für `field`/anonym).

### Aufgaben: heute gesperrt, nicht angefasst, dokumentierter Grund

Geprüft, bevor entschieden wurde: existiert heute überhaupt eine Aufgabe, die sinnvoll einem
Monteur statt dem Büro zugewiesen würde? Die echte Datenbank zeigt: **alle** aktuell
zugewiesenen Aufgaben (`Task.assigned_employee_id`) gehen an Employee-ID 1 -- Tobias, den
Geschäftsführer, verknüpft über `AppUser`-Konto "Tobias". Keine einzige Aufgabe ist an einen
der acht Dachdecker-Mitarbeiter (Vorarbeiter/Geselle/Auszubildende) oder die beiden
Büro-Mitarbeiterinnen adressiert. Automatisch erzeugte Aufgaben (Wartungs-Erinnerungen,
"buero_pruefen"-Mängelmaßnahme) landen laut Code ohnehin beim konfigurierten
Sachbearbeiter/Standard-Verantwortlichen -- fachlich eine Büro-Rolle, kein Monteurs-Vorgang.

**Entscheidung**: Aufgaben (`/tasks`, `/api/tasks*`, `/api/task-columns*`, `/api/task-settings`,
dazu die beiden `/api/tasks/{task_id}/finding`- und `.../create-follow-up-project`-Endpunkte, die
aus historischen Gründen in `app/routers/findings.py` statt `tasks.py` liegen)
bleiben für `field` vorerst vollständig gesperrt (umgesetzt in 1.3.52, Büro+Admin wie die übrige
Verwaltung) statt einer eigenen "nur eigene Aufgaben"-Filterung. Sollte sich der Betriebsablauf
ändern (eine Aufgabe wird künftig gezielt einem Monteur zugewiesen), ist das ein bewusster,
späterer Schritt -- keine stillschweigend mitgebaute Funktion ohne heutigen Anwendungsfall.

**Was dafür fehlen würde, festgehalten für den nächsten Durchgang** (nicht gebaut, nur
dokumentiert, wie verlangt) -- geprüft direkt am Code, nicht nur vermutet:

1. **Ein "eigene Aufgaben"-Filter existiert teilweise schon, aber lückenhaft.**
   `GET /api/tasks` (`app/routers/tasks.py::get_tasks()`) schränkt für jeden Nicht-Admin
   bereits heute auf `employee_id == request.state.erp_user.employee_id` ein, und
   `_require_task_access()` tut dasselbe für die Checklisten-Endpunkte
   (`POST/PUT/DELETE .../checklist-items*`). **Aber**: `PUT /api/tasks/{id}` (Titel/Status/
   Priorität/Zuweisung ändern), `DELETE /api/tasks/{id}` und die beiden
   Archivieren/Reaktivieren-Endpunkte prüfen GAR KEINE Eigentümerschaft -- ein Nicht-Admin
   könnte darüber heute schon jede beliebige Aufgabe ändern, nicht nur seine eigene, wenn er
   diese Endpunkte erreicht. Das ist eine bereits im Code bestehende Lücke, unabhängig vom
   Rechtekonzept -- fiele beim Öffnen von Aufgaben für `field` sofort auf, weil dann zum ersten
   Mal jemand mit einer wirklich anderen Interessenlage als "Büro" darauf träfe. Vor einer
   Öffnung für `field` müsste dieselbe `_require_task_access()`-Prüfung auch auf diese drei/vier
   Endpunkte ausgedehnt werden.
2. **Eine belastbare Zuweisung an den AppUser, nicht nur an den Employee.** Der bestehende
   Filter (Punkt 1) funktioniert nur, weil er `request.state.erp_user.employee_id` gegen
   `Task.assigned_employee_id` vergleicht -- verlässt sich also auf eine verlässliche
   Employee↔AppUser-Zuordnung. `AppUser.employee_id` ist aber nullable UND ohne
   Unique-Constraint (zwei AppUser-Konten könnten theoretisch dieselbe `employee_id` tragen,
   oder eine Aufgabe könnte einem Employee zugewiesen sein, der gar kein Login hat). Heute
   folgenlos (ein einziges Admin-Konto mit Employee-Verknüpfung), würde aber bei mehreren
   echten Monteurskonten zur tatsächlichen Fehlerquelle, sollte diese Zuordnung je nicht
   eindeutig sein.

### Sichtbarkeit in der Oberfläche: ausblenden, nicht ausgrauen (Fundament gelegt, noch nicht verdrahtet)

Ein Monteur soll nicht einmal sehen, DASS es Finanzen/Kalkulation/Stammdaten gibt -- kein
ausgegrauter, unklickbarer Menüpunkt. `_sidebar.html` bekommt dafür `is_office`/`is_field`
(neben dem bestehenden `is_admin`), nach demselben Muster berechnet -- in dieser Version noch
ungenutzt (keine Navigationseinträge wurden bereits umgestellt, das ist Teil der Etappe-2/3-
Umsetzung an den einzelnen Seiten).

**Ausnahme, wie gefordert**: wer eine Adresse von Hand eintippt (kein Menüpunkt führt dorthin,
also kein Ausblenden möglich), bekommt eine verständliche Meldung statt einer rohen
403-JSON-Antwort. Neues, eigenständiges Template `app/templates/access_denied.html` (Muster
`login.html` -- eigenständige Seite, kein `_sidebar.html`-Include, da eine Person ohne Zugriff
auf eine Seite meist auch nicht die volle Navigation sehen soll) mit einem Link zurück zur
jeweiligen Startseite. Noch nicht in die Middleware verdrahtet -- das braucht die
Seiten-Klassifizierung aus Etappe 2/3 (welche der 31 Seiten ist für wen gedacht), nicht nur die
API-Klassifizierung.

### Bestandsschutz und sichere Voreinstellung beim Anlegen (`users.html`)

Tobias und "Admin" bleiben unverändert `role="admin"` -- keine ihrer Zeilen wurde durch die
Migration berührt (0 betroffene Zeilen, siehe oben). Für NEUE Konten:
`AppUserCreate`/`AppUserUpdate` (`app/schemas.py`) haben jetzt `default="field"` statt
`default="user"` -- die am wenigsten privilegierte Rolle, nicht mehr eine, die praktisch schon
immer vollen Zugriff bedeutete. Das Auswahlfeld in `users.html` listet "Monteur" absichtlich
zuerst (Browser wählen ohne Interaktion die erste `<option>`). **Zusätzlich, wie verlangt, eine
Warnung**: legt jemand ein NEUES Konto an, ohne das Rollenfeld ausdrücklich zu ändern
(`roleTouched`-Flag, per `onchange` gesetzt), erscheint vor dem Speichern eine
`confirm()`-Bestätigung mit der Rolle, die tatsächlich vergeben würde -- verhindert, dass eine
Rolle "einfach passiert", unabhängig von der (bereits sicheren) Voreinstellung selbst. Gilt
bewusst nur beim Anlegen, nicht beim Bearbeiten eines bestehenden Kontos (dessen aktuelle Rolle
ist in der Liste ohnehin sichtbar, keine verdeckte Änderung möglich).

### Etappenplan

1. **Fundament** (diese Version): dritte Rollenstufe, `require_role()`, Migration,
   Standardverweigerungs-Mechanismus samt Audit-Test. -- **fertig**.
2. **Rollen-Gate nachziehen**: `require_role(...)` an alle heute ungeschützten Finanz-/
   Kalkulations-/Mitarbeiter-/Stammdaten-/Verwaltungs-Endpunkte hängen, entlang der vom
   Audit-Test namentlich gelisteten Routen. -- **fertig (1.3.51-1.3.55)**: der riskante Batch
   (Finanzen/Kalkulation/Mitarbeiter/Einstellungen/Benutzer/Historie/Aufgaben, 1.3.52), Teil A
   des Rests (alle Dateien ohne Monteur-Bezug, 1.3.54) und Teil B (die 65 aktiv von Monteuren
   genutzten Endpunkte in `orders.py`/`service_reports.py`/`findings.py`/`inspection_templates.py`/
   `time_tracking.py`, 1.3.55 -- erst NACH Etappe 3, weil ein blankes Büro+Admin-Gate dort den
   Einsatzbericht-Ablauf gebrochen hätte, genau der Fehler von `GET /api/employees` in 1.3.53).
   Der Audit-Test steht bei null und ist seit 1.3.55 ein harter Test (`xfail` entfernt).
3. **Objekt-Filterung für `field`** -- **fertig (1.3.55-1.3.59)**: `field_may_access_order()`
   (`app/orders.py`, zwei Wege, siehe "Objekt-Filterung" oben) und `require_field_order_access()`
   (`app/routers/orders.py`) sind auf `orders.py`/`service_reports.py`/`findings.py` angewendet;
   `properties.py`/`roof_areas.py` brauchten sie nicht (seit Teil A Büro/Admin, der Monteur liest
   Objekt und Dachflächen ausschließlich auftragsbezogen über `service_reports.py`). Nachtrag
   1.3.56 nach Betreiber-Rückmeldung: "Wartung durchführen" für Monteure, reduzierte Historie,
   Büro sieht alle Zeitbuchungen, `sign_report()` geprüft. **Seit 1.3.57 zusätzlich die
   Seiten-Klassifizierung**: dieselbe Standardverweigerung gilt jetzt auch für die
   Seiten-Routen selbst (`app/routers/pages.py`, `Depends(require_role(...))` je Route,
   `PAGE_AUDIT_EXEMPT` für die vier strukturellen Ausnahmen), ein 403 zeigt `access_denied.html`
   statt einer rohen JSON-Antwort (`app/main.py`s Exception-Handler), der Audit-Test deckt beide
   Ebenen ab -- siehe "Seiten-Klassifizierung" unten für die volle Herleitung. **Seit 1.3.58
   zusätzlich der `/mobil`-Vertragsfinder** (damals noch unter `/vor-ort`)**: die Karte "Wartungen
   an meinen Objekten" (siehe eigener Abschnitt "Objekt-Filterung" → "Vertragsfinder auf /mobil"
   unten) schließt die
   zuletzt offene Lücke -- ein Monteur konnte bisher nur eine bereits geplante Wartung
   durchführen, keine ungeplante an einem Objekt starten, an dem er gerade arbeitet. **Seit
   1.3.59 ein Sicherheitstest gegen eine isolierte Testinstanz** (nie gegen die echte
   `dachkonzepte_erp.db`) mit zwei echten Funden, beide behoben: fremde Berichte auf einem
   gemeinsamen Auftrag lesen/ändern/löschen/signieren (siehe "Berichts-Eigentümerschaft" oben)
   und eine Wartung auf einem fremden Vertrag per geratener ID auslösen (siehe "Fund: fremde
   Wartung per geratener Vertrags-ID" oben) -- ein zweiter Durchlauf desselben Angriffstests
   bestätigt beide als geschlossen. **Seit 1.3.60 zusätzlich die reduzierte Zeiterfassung**
   (siehe "Zeiterfassung für Monteure" oben) -- die volle, sidebar-getragene `time_tracking.html`
   war zuvor die letzte für `field` erreichbare Seite ohne eine eigens dafür gebaute, schmale
   Ansicht. **Noch offen**: der "Auftrag"-Link in `service_reports.html`, der auf eine jetzt
   gesperrte Büro-Seite zeigt, und die Kolonnenführer-Rolle für Gruppenbuchungen (beide siehe
   "Bekannte, bewusst offene Punkte").
4. Erstes echtes `field`-Testkonto anlegen, vollständigen Monteurs-Ablauf im Browser
   durchklicken. -- offen.

### Vier Rollen (seit 1.4.7/1.4.8, Etappe 1: Rollen-Erweiterung, Etappe 2: die Verengungen)

Vom Betreiber beauftragter Umbau auf dem obigen Fundament -- Vorgehen wie bei den größeren
Umbauten dieses Projekts üblich: erst ein reiner Befund + Vorschlag (keine Codeänderung,
separat berichtet), dann nach Bestätigung der Bau, in zwei ausdrücklich angeforderten Etappen.
**1.4.7 war Etappe 1 -- die reine Rollen-Erweiterung** (bis dahin sah `buero_auftrag` überall
exakt dasselbe wie `buero_finanzen`). **1.4.8 ist Etappe 2 -- die Verengungen selbst**, siehe
eigener Unterabschnitt unten: ab jetzt unterscheiden sich beide Rollen tatsächlich.

**Anlass**: die bisherige Rolle `office` bündelte zu viel unter einem Dach -- ein Sachbearbeiter,
der Angebote schreibt, sah damit automatisch auch die Kostenstruktur des Betriebs
(Kalkulationsgrundlagen, künftig Betriebskosten) und die Vergütung der Kollegen. Der Betreiber
wollte das trennen, ohne die seit "Rechtekonzept" etablierte Standardverweigerung/den
Audit-Mechanismus neu zu erfinden.

**Vier Rollen** (`app/permissions.py`): `admin` bleibt alles inklusive Systemverwaltung.
`buero_finanzen` = alles Fachliche/Kaufmännische PLUS Betriebskosten-Übersicht (künftig)/
Kalkulationsgrundlagen/Stundenverrechnungssatz-Herleitung/Mitarbeitervergütung -- Schnittstelle
zum Steuerberater, keine Systemverwaltung. `buero_auftrag` = derselbe fachliche/kaufmännische
Kern (Projekte, Angebote MIT voller Kalkulation/Marge/Einkaufspreisen -- das bleibt bewusst
unverengt, siehe unten --, Aufträge, Rechnungen, Mahnwesen, Planung, Wartung, Anfragen, Aufgaben,
Betriebsmittel-Bestand) OHNE die vier finanzspezifischen Bereiche oben. `field` unverändert.

**Die Hierarchie -- die zentrale, vom Betreiber selbst gestellte Frage** ("kann buero_finanzen
alles, was buero_auftrag kann, plus mehr? Prüfe, ob has_role() das als Hierarchie abbilden
kann"): ja, über eine neue, parallele Prüfart. `ROLE_RANK` (`app/permissions.py`) ist eine reine
Ganzzahl-Kette -- `field=0 < buero_auftrag=1 < buero_finanzen=2 < admin=3` --, `has_min_role(user,
min_role)` prüft `ROLE_RANK[user.role] >= ROLE_RANK[min_role]`, `require_min_role(min_role, *,
message=...)` ist die dazugehörige FastAPI-Dependency-Fabrik (Muster `require_role()`, trägt
ebenso eine `_dk_roles`-Markierung -- hier die vollständige, aus `ROLE_RANK` abgeleitete Menge
aller Rollen ab diesem Rang, damit `tests/test_v260_role_audit.py` ohne jede Sonderbehandlung
weiterläuft). `has_role()`/`require_role()` (die FLACHE Mengenprüfung) bleiben unverändert
bestehen -- für `require_admin()`-äquivalente Fälle und echte "für jede Rolle offen"-Stellen,
keine Ablösung, eine zweite, weiterhin gültige Prüfart daneben.

**Warum das die Migration deutlich weniger invasiv macht, als zunächst befürchtet**: eine
exhaustive Durchsuchung aller `require_role(...)`-Aufrufe im Projekt (vor dem Bauen, nicht
danach) ergab, dass im GESAMTEN Projekt nur genau ZWEI Rollenkombinationen je vorkamen --
`require_role(ROLE_ADMIN, ROLE_OFFICE)` in ~40 Dateien und `require_role(ROLE_ADMIN, ROLE_OFFICE,
ROLE_FIELD)` in ~15 Dateien, keine dritte. Beide übersetzen sich verlustfrei und OHNE
Einzelentscheidung in `require_min_role(ROLE_OFFICE_AUFTRAG)` bzw. `require_min_role(ROLE_FIELD)`
-- ein Skript hat diese reine Textersetzung über ~55 Endpunkt-Dependencies in ~45 `app/routers/`-
Dateien vorgenommen, gefolgt von einer automatischen Importzeilen-Bereinigung (ungenutzte Symbole
entfernt, `require_min_role` ergänzt) und einer echten Modul-für-Modul-Importprobe (jedes
`app.routers.*`-Modul einzeln importiert -- fängt einen falschen/fehlenden Import sofort als
`ImportError`, nicht erst als Testfehler). Zwei App-Kernmodule brauchten dieselbe Umstellung
manuell: `app/tasks.py::list_tasks_for_user()` (`has_role(user, ROLE_ADMIN, ROLE_OFFICE)` ->
`has_min_role(user, ROLE_OFFICE_AUFTRAG)`) und `app/search.py::OFFICE_ROLES` (die EINE, von allen
18 Büro-Suchquellen referenzierte Konstante, erweitert auf `{ROLE_ADMIN, ROLE_OFFICE_FINANZEN,
ROLE_OFFICE_AUFTRAG}` -- bestätigt exakt die in der vorangegangenen Bestandsaufnahme getroffene
Vorhersage, dass die Suche nur EINE Konstantenänderung braucht, keine 18 Einzelentscheidungen).
Ein einziger, vom Skript naturgemäß nicht erfasster manueller Rollenvergleich
(`app/routers/pages.py::_require_users_page_access()`, `user.role not in (ROLE_ADMIN,
ROLE_OFFICE)`, kein `require_role(...)`-Aufruf, sondern eine Inline-Bedingung im Bootstrap-Pfad)
wurde beim Import-Check als `ImportError` sichtbar und auf `has_min_role(user,
ROLE_OFFICE_AUFTRAG)` umgestellt. Drei literale `can(current_user, 'admin', 'office')`-Aufrufe in
`_sidebar.html`/`_topbar.html` (Jinja-Templates kennen keine Rollenkonstanten, nur String-Literale,
`can()` selbst ist eine FLACHE Mengenprüfung ohne Hierarchie -- siehe `app/routers/pages.py::_can()`)
wurden auf `can(current_user, 'admin', 'buero_finanzen', 'buero_auftrag')` erweitert.
`require_admin()` (`app/deps.py`) bleibt in dieser Etappe unverändert -- die Verschiebung von
`time_backoffice.py`/`address-import` auf `buero_auftrag` ist Teil von Etappe 2.

**Migration `7677d9d878ba`** (reine Daten-Migration, kein Schema-Umbau -- `app_users.role` war
immer schon eine unbeschränkte `String(30)`-Spalte ohne Constraint, siehe oben): ein bestehendes
`role="office"`-Konto wird `buero_finanzen` -- die umfassendere der beiden neuen Rollen, exakt
wie vom Betreiber vorgegeben (Bestandsschutz: ein bereits eingerichtetes Büro-Konto darf durch
den Split nie Zugriff verlieren, umgekehrt zur "sicherste Rolle zuerst"-Regel bei NEUEN Konten
unten). **Vor der Migration geprüft, nicht geraten, wie ausdrücklich verlangt** ("ich will
wissen, wer welche Rolle bekommt, bevor sie vergeben wird"): die echte, lokale
`dachkonzepte_erp.db` trägt genau zwei Konten -- Tobias (mit Mitarbeiterverknüpfung) und Admin
(reines Systemkonto) --, BEIDE bereits `admin`. **0 Zeilen betroffen.** Migration trotzdem
angewendet (Kettenanschluss für jede andere Installation), Bestand danach erneut verifiziert:
beide Konten unverändert `admin`. `downgrade()` bildet beide neuen Werte gleich auf `office`
zurück (kann die Aufteilung nicht verlustfrei rückgängig machen, dieselbe Konvention wie die
vorangegangene Rollen-Migration `7a2b4e9f1c3d`).

**Neue Konten, sicherer Vorgabewert** (`app/schemas.py::AppUserCreate`/`AppUserUpdate`): Pattern
erweitert auf alle vier Rollen, der SCHEMA-Vorgabewert (greift nur, wenn ein Aufruf `role` ganz
weglässt -- `users.html` schickt immer einen ausdrücklich gewählten Wert) geändert von `"field"`
auf `"buero_auftrag"` -- die restriktivere der beiden Bürorollen, damit niemand allein durch
Weglassen des Feldes Zugriff auf Kalkulationsgrundlagen/Mitarbeitervergütung erbt. Die
Sidebar-Voreinstellung in `users.html` bleibt davon bewusst UNABHÄNGIG weiterhin `field`
(Monteur) -- die am wenigsten privilegierte Rolle über alle vier Stufen hinweg, unverändert seit
1.3.51 (Begründung: die beiden Vorgaben beantworten unterschiedliche Fragen -- "welche der zwei
Bürorollen, falls office unspezifisch bliebe" vs. "welche Rolle soll ein Administrator beim
Anlegen eines neuen Kontos ohne bewusste Wahl voreingestellt sehen", und für Letzteres bleibt die
niedrigste Stufe insgesamt die sicherste Antwort). Rollen-Dropdown zeigt jetzt vier Optionen
("Monteur"/"Büro – Auftrag"/"Büro – Finanzen"/"Administrator", in dieser Rangfolge), die
bestehende Bestätigungsabfrage beim Anlegen ohne ausdrücklich gewählte Rolle bleibt unverändert.

**Testfolgen**: ~140 Vorkommen von `role="office"`/`ROLE_OFFICE` über ~35 Testdateien einzeln
durchgesehen und eingeordnet -- der weit überwiegende Teil sind reine Testaufbau-Stellen,
mechanisch auf `buero_auftrag` umbenannt (Wahl als Repräsentant, nicht willkürlich: es ist die
untere der beiden Bürorollen-Schwellen, ein damit erfolgreicher Test beweist bei einer
`>=`-Rang-Prüfung automatisch, dass auch `buero_finanzen`/`admin` bestehen würden). Eine kleine
Zahl von Stellen, die ausdrücklich "office UND admin dürfen beide" belegen sollten, wurde auf
alle drei nicht-Monteur-Rollen erweitert statt nur umbenannt -- stärkerer Nachweis der Hierarchie
an genau den Stellen, die das schon vorher zeigen wollten (u. a.
`TestRoleGateOnCustomersInvoicesReminders`, die Aufgaben-/Seiten-Klassifizierungstests in
`test_v260_role_audit.py`, die Büro-Suche in `test_v270_office_search.py`).
`tests/test_v261_permissions_foundation.py`s Migrationstest für die HISTORISCHE Migration
`7a2b4e9f1c3d` (role='user' -> 'office') blieb bewusst unverändert -- der testet eine bereits
abgeschlossene, andere Migration. Neue, dedizierte Datei `tests/test_v281_role_hierarchy.py` --
end-to-end-Nachweis der Hierarchie über eine echte FastAPI-Testroute (nicht nur die Funktion
isoliert): `require_min_role(ROLE_OFFICE_AUFTRAG)` lässt `buero_auftrag`, `buero_finanzen` UND
`admin` durch, ohne dass Letztere in der Dependency-Definition einzeln genannt wurden; ein liegen
gebliebener Altwert (`"office"`) fällt an JEDER Schwelle sicher durch (Standardverweigerung, kein
stiller Rückfall). Volle Suite: 1514 Tests grün.

**Etappe 2 (seit 1.4.8) -- die Verengungen, umgesetzt.** Drei der vier ursprünglich angekündigten
Punkte wurden gebaut, der zweite (Betriebskosten-Übersicht) bleibt ein reiner Vormerkposten, da
er im Code noch nicht existiert:

1. **Kalkulationsgrundlagen/Stundenverrechnungssatz-Herleitung -> `buero_finanzen`.** Wie beim
   Nachschärfen vorab geklärt (siehe Herleitung oben, unverändert gültig): `GET/PUT
   /api/calculation-settings` (`app/routers/settings.py`) und alle 4 Endpunkte in
   `app/routers/labor_rate.py` (ein einziger Modul-`_role_dep`) sind auf
   `require_min_role(ROLE_OFFICE_FINANZEN)` verengt -- das ist genau die Stelle, an der die
   Bestandteile GEPFLEGT werden. Der fertige Satz bleibt für `buero_auftrag` dort sichtbar, wo er
   ANGEWENDET wird (Angebotskalkulation/Leistungskatalog), ohne einen eigenen, neuen Endpunkt --
   diese Trennung ergab sich bereits aus der bestehenden Architektur, keine Endpunkt-Aufteilung
   nötig.
2. **Betriebskosten-Übersicht** -> `buero_finanzen` (existiert im Code weiterhin nicht, bleibt
   reiner Vormerkposten für ein künftiges Feature).
3. **Mitarbeitervergütung -> `buero_finanzen`, der Bestand bleibt `buero_auftrag`.** Neues
   `EmployeeRosterOut`-Schema (`app/schemas.py`) -- Name, Funktion, Kontakt, Planung,
   Kosten-Zuordnung (eine Kategorie, kein Betrag), OHNE `compensation_type`/`hourly_wage`/
   `monthly_salary`/`effective_hourly_wage`/`annual_gross_wage`. `app/routers/employees.py::
   _employee_out_for_role()` wählt je Rolle zwischen `EmployeeOut` (buero_finanzen/admin),
   `EmployeeRosterOut` (buero_auftrag) und `EmployeeNameOut` (field, unverändert seit 1.3.53) --
   angewendet auf Liste/Sachbearbeiter/Einzelabruf. **Anlegen/Bearbeiten komplett auf
   `buero_finanzen`**, nicht nur die Lohnfelder -- `master_data_form.html::employeeForm()` ist
   EIN kombiniertes Formular mit den Lohnfeldern direkt darin (Regel 10), eine Rechte-Aufteilung
   hätte ein zweites Formular gebraucht und das Risiko eingeführt, dass ein für `buero_auftrag`
   unsichtbares Lohnfeld beim Speichern den Wert eines Kollegen stillschweigend auf 0/`None`
   überschreibt -- bewusste, transparent gemeldete Erweiterung über die wörtliche Anfrage
   hinaus. `_require_finanzen_for_employees()` (`app/routers/pages.py`) sperrt zusätzlich die
   beiden Formular-SEITEN selbst, `master_data.html` blendet Vergütungsspalte/"Gewichteter
   Mittellohn"/"+ Hinzufügen"/"Bearbeiten" für `buero_auftrag` aus (ausblenden, nicht ausgrauen).
   **Eigener, bei der Umsetzung gefundener Zusatzpunkt, in der ursprünglichen Anfrage nicht
   benannt**: die Änderungshistorie (`GET /api/audit-logs`) zeigt Vorher-/Nachher-Werte und
   angelegt/gelöscht-Schnappschüsse über ALLE Entitäten -- auch eine `hourly_wage`-Änderung im
   Klartext. `app/audit.py::WAGE_FIELD_NAMES`/`redact_wage_snapshot()` entfernen für
   `buero_auftrag` betroffene "geändert"-Zeilen vollständig und bereinigen "angelegt"/
   "gelöscht"-Schnappschüsse um die drei Lohnschlüssel, ohne die `AuditLog`-Zeile selbst zu
   mutieren; `buero_finanzen`/`admin` sehen die Historie unverändert vollständig, andere
   Entitäten bleiben für `buero_auftrag` unangetastet sichtbar.
4. **Zeiterfassungs-Backoffice** (`app/routers/time_backoffice.py`, `/time-backoffice`, 15
   Endpunkte) -> von `require_admin()` auf `require_min_role(ROLE_OFFICE_AUFTRAG)` angehoben.
   Vor der Anhebung wie verlangt geprüft, ob dabei Vergütung mitsichtbar wird -- kein Fund
   (`EmployeePayrollSettingsOut` trägt nur eine DATEV-Personalnummer-Zuordnung, `backoffice_summary()`/
   `build_timesheet_pdf()`/`build_time_csv()` zeigen ausschließlich Stunden, `build_datev_export()`s
   "Lohnart" ist eine Buchungskategorie, kein €-Betrag) -- die gesamte Datei hebt sich deshalb
   einheitlich an, ohne interne Verengung. **`/address-import` bleibt bewusst UNVERÄNDERT
   admin-only** -- die Betreiberanfrage nannte ausdrücklich nur "das Zeiterfassungs-Backoffice",
   `require_admin()` bleibt in `app/routers/pages.py` deshalb weiterhin importiert und für diese
   eine Seite in Gebrauch.

**Beim Bauen gefundener Jinja-Fehler, behoben**: die neuen `{% if can(current_user, 'admin',
'buero_finanzen') %}`-Bedingungen in `settings.html`/`master_data.html` verließen sich auf ein
`{% set current_user = ... %}` aus dem eingebundenen `_sidebar.html` -- ein `{% set %}`
innerhalb eines `{% include %}` wirkt in Jinja aber NICHT in der einbindenden Vorlage nach,
unabhängig von der Rolle. Beide Dateien setzen `current_user` seither selbst, direkt nach
`<body>`. Ohne diesen Fund hätte `/settings` und `/master-data` für JEDE Rolle mit
`UndefinedError` abgebrochen -- durch den bereits bestehenden `test_v218_template_rendering.py`
gefangen, nicht durch manuelles Ausprobieren.

**Angriffstest zum Abschluss, wie vom Betreiber verlangt** (`tests/test_v282_role_narrowing_etappe2.py`,
18 Tests, je ein Testkonto pro Rolle): `buero_auftrag` bekommt 403 auf Kalkulationsgrundlagen/
Stundenverrechnungssatz-Herleitung/Mitarbeiter-Schreiben, kein Lohnfeld in irgendeiner Antwort
(rekursiver Schlüssel-Scan, auch durch als JSON-String codierte `AuditLogOut.details`-Werte
hindurch); `buero_auftrag` erreicht das Zeiterfassungs-Backoffice (erlaubt), aber ohne
Lohndaten; `buero_finanzen` sieht alles davon (erlaubt); `field` bleibt überall gesperrt, wie
zuvor. Null durchgelassen. Volle Suite: 1532 Tests grün.

## Dateiablage je Objekt ("Runde 2" der Monteurs-Erweiterung, seit 1.3.62)

Ziel (Betreibervorgabe): jeder Mitarbeiter -- auch Monteure -- kann Bilder und Dokumente zu einem
Objekt hochladen und ansehen, mit einer admin-gesteuerten Freigabe für Monteure UND einer
kategorieabhängigen Sperre für sensible Dokumente. Vorgehen ausdrücklich in Etappen: zuerst
Befund+Vorschlag (kein Code), dann diese Version -- **nur das Fundament** (Kategorie-Stammdaten,
Migration, feste Code-Sperrliste) --, danach erst die mobile Objektansicht und die geteilte Suche,
jeweils erst nach Bestätigung des vorherigen Schritts.

### Befund vor dem Bauen (Runde-2-Vorlauf, keine Codeänderung)

Vier bestehende Upload-Wege, unterschiedlich objekt-/projekt-/kundenbezogen: `roof_area_sketches`
(an `RoofArea`, damit indirekt an `Property`), `project_files`/`ProjectDocument` (an `Project`,
nicht direkt an `Property`), `customer_documents`/`CustomerDocument` (an `Customer`, nicht an
`Property`), `service_report_photos` (an `Finding`/`InspectionItem` über den Einsatzbericht).
**Keiner der vier hängt heute direkt an einem `Property`** -- eine Dateiablage je Objekt bräuchte
entweder eine neue, objektbezogene Ablage oder eine Zusammenführung der bereits projekt-/
kundenbezogenen Dokumente über die Objektzuordnung. Alle vier folgen demselben Speichermuster:
`ERP_DATA_DIR`/`data_dir()` (siehe "Geheimnisse für den Serverbetrieb" oben) plus einem
dedizierten, rollen-geprüften Auslieferungsendpunkt -- kein `StaticFiles`-Mount irgendwo im
Projekt. `resize_and_store_photo()` (`app/service_report_photos.py`, 1.2.17) verkleinert Fotos mit
Pillow (`exif_transpose()` + `thumbnail()` auf 1600px + JPEG q82) -- dabei ein echter,
architektonischer Fund: der Aufrufer (`post_service_report_photo`, eine `async def`-Route) ruft
diese synchrone, CPU-gebundene Funktion direkt auf, ohne `run_in_threadpool()`/
`asyncio.to_thread()` -- blockiert damit einen der beiden gunicorn-Arbeitsprozesse des
4-GB-Produktivservers (siehe "Produktivbetrieb" oben, `-w 2`) für die Dauer jeder Verkleinerung,
die Hälfte der Gesamtkapazität. Für eine künftige, neue Foto-Upload-Route in der Objektablage
NICHT verbatim kopieren -- entweder eine gewöhnliche `def`-Route (Starlette threadpoolt synchrone
Routen automatisch) oder ein expliziter `run_in_threadpool()`-Aufruf.

Als Vorbild für den künftigen Objektzugriff eines Monteurs vorgeschlagen (noch nicht gebaut,
Entscheidung steht noch aus): dasselbe Zwei-Wege-Muster wie `field_may_access_order()`
(`app/orders.py`, siehe "Rechtekonzept" → "Objekt-Filterung" oben) -- Planungsbezug (aktuell/nah
zugeordnet) ODER ein eigener, bereits angelegter Bezug (z. B. ein selbst hochgeladenes Dokument),
damit ein Monteur nach einer Umplanung nicht den Zugriff auf bereits Hochgeladenes verliert.

### Entscheidungen des Betreibers für diese und die folgenden Etappen (bereits getroffen, noch nicht alle umgesetzt)

1. **Objekt statt Projekt als Leitkonzept.** In der künftigen mobilen Ansicht öffnet ein Monteur
   ein Objekt und sieht die Dokumente ALLER nicht archivierten Projekte dieses Objekts,
   zusammengeführt, nach Kategorie gruppiert -- "die Pläne von der Baustelle Musterstraße", nicht
   "die Pläne aus Projekt P-2026-0012". Eigene Uploads eines Monteurs binden sich an das OBJEKT,
   nicht an ein bestimmtes Projekt (ein spontaner Einsatz hat oft gar kein Projekt) -- ob das eine
   eigene, objektbezogene Ablage-Tabelle braucht oder einem Sammelprojekt des Objekts zugeordnet
   wird, ist noch offen; der Betreiber neigt zur eigenen, objektbezogenen Ablage. **Noch nicht
   gebaut** -- gehört zur nächsten Etappe.
2. **Kategorie-Stammdaten mit `is_sensitive`/`is_field_visible`** -- diese Version, siehe unten.
3. **Feste Code-Sperrliste zusätzlich zur Einstellung** -- diese Version, siehe unten
   (`HARD_LOCKED_CATEGORY_KEYS`).
4. **Geteilte Suche mit serverseitiger Feldbegrenzung.** Eine gemeinsame Kernfunktion mit
   unterschiedlicher Feld-/Ergebnisbegrenzung statt zweier getrennter Implementierungen (Muster:
   genau das, was bei `build_customer_and_meta_block()` mit drei divergierenden Varianten zum
   Problem wurde, siehe "Kopfbereich" oben). Die Begrenzung für Monteure muss dabei SERVERSEITIG
   sitzen, nicht nur in der Aufrufweise -- ein Monteur, der den Büro-Suchendpunkt direkt aufruft,
   muss dieselbe Begrenzung bekommen, nicht die vollen Ergebnisse. **Noch nicht gebaut** -- gehört
   zur übernächsten Etappe (nach der mobilen Objektansicht).

### Diese Version: Kategorie-Stammdaten (`DocumentCategory`), Migration, zwei unabhängige Schlösser

Siehe `app/document_categories.py` für die vollständige, im Moduldocstring festgehaltene
Begründung -- hier nur die Zusammenfassung. Echte Stammdatentabelle statt einer weiteren
Optionsgruppe (dieselbe Hochstufung wie `RoofComponentType`/`RoofLayerType`, 1.2.19/1.2.18): eine
reine Auswahlliste kann `is_sensitive`/`is_field_visible` nicht tragen. `key` bleibt bewusst
textidentisch zu den bisherigen Optionswerten der abgelösten Gruppe `project_document_categories`
(`app/option_settings.py`) -- die bestehenden, unveränderten Freitext-Spalten
`CustomerDocument.category`/`ProjectDocument.category` matchen dadurch unverändert weiter.

**Acht Kategorien** (`DEFAULT_CATEGORIES`, wortgleich aus der abgelösten Optionsgruppe): Pläne,
Bilder / Fotos, Lieferscheine, Aufmaß (alle vier `is_field_visible=True`), Schriftverkehr (weder
sensibel noch sichtbar), Verträge / Freigaben und Rechnungen / Belege (beide `is_sensitive=True`),
Sonstiges (Rückfallkategorie, weder sensibel noch sichtbar).

**Zwei unabhängige Schlösser, wie ausdrücklich vom Betreiber verlangt ("zwei unabhängige
Schlösser, kein gemeinsamer Schlüssel")**:
1. `is_sensitive`/`is_field_visible` in `DocumentCategory` selbst -- `create_category()`/
   `update_category()` (`app/document_categories.py`) lehnen die Kombination
   `is_sensitive=True` + `is_field_visible=True` grundsätzlich ab, unabhängig vom Key. Zusätzlich
   ist `is_sensitive` **einmal gesetzt unveränderlich** -- `update_category()` verweigert jeden
   Versuch, eine bereits sensible Kategorie wieder auf `is_sensitive=False` zu setzen (weder über
   die Oberfläche noch über die API, da beide denselben Endpunkt nutzen).
2. `HARD_LOCKED_CATEGORY_KEYS` (`frozenset({"Rechnungen / Belege", "Verträge / Freigaben"})`) --
   eine feste, im Code verankerte Sperrliste, die `field_may_see_category()` UNABHÄNGIG von den
   beiden Datenbankfeldern prüft. Selbst wenn jemand die `document_categories`-Tabelle direkt
   manipuliert (rohes SQL, ein Bug in einer künftigen Änderung), bleibt `field_may_see_category()`
   für diese beiden Kategorien hart auf `False` -- kein gemeinsamer Prüfpfad mit Schloss 1. Per
   Test belegt (`tests/test_v266_document_categories.py::
   test_field_may_see_category_blocks_hard_locked_keys_even_with_tampered_flags`): ein
   `DocumentCategory`-Objekt wird dort DIREKT konstruiert, unter vollständiger Umgehung von
   `create_category()`/`update_category()`, mit `is_field_visible=True` für einen gesperrten Key
   -- `field_may_see_category()` liefert trotzdem `False`.

`create_category()`/`update_category()` sind noch UNGENUTZT von jedem Anzeigepfad in dieser
Version (kein Monteur sieht heute schon eine Kategorie -- die mobile Objektansicht kommt erst in
der nächsten Etappe) -- die Validierung ist bereits vollständig, damit die kommende Etappe darauf
aufbauen kann, ohne die Schloss-Logik selbst nachzuziehen.

**Migration/Backfill der bestehenden Freitext-Kategorien** (`category_id`, neue, zusätzliche
FK-Spalte -- `category`, der Freitext, bleibt unverändert stehen und ist weiterhin das einzige
Feld, das das bestehende Upload-/Bearbeiten-Formular direkt beschreibt). Migration `9137945e8785`
folgt Regel 1 (server_default bei NOT-NULL-Spalten auf bestehenden Tabellen): `category_id` wird
zunächst NULLABLE angelegt (ein `server_default` auf eine konkrete ID wäre fragil, da der
Fremdschlüssel auf eine erst in DERSELBEN Migration befüllte Tabelle zeigt), aus dem Bestand
befüllt (`_resolve_category_id()`, standalone und eigenständig testbar direkt in der
Migrationsdatei, Muster aus 1.2.19/1.3.12/1.3.22), erst danach auf NOT NULL gesetzt.
Zuordnungsregel: exakte Übereinstimmung des Freitexts gegen `key`, sonst Rückfall auf
"Sonstiges" -- NIE auf eine sichtbare oder sensible Kategorie, im Zweifel gesperrt statt offen.

**Vor dem Schreiben gegen die echte, lokale Datenbank geprüft, wie verlangt** ("berichte mir,
welche Strings du vorfindest"): `customer_documents` war zum Zeitpunkt der Migration LEER (0
Zeilen) -- kein Backfill nötig. `project_documents` hatte GENAU EINE Zeile, `category='Pläne'` --
ein exakter Treffer auf den gleichnamigen Kategorie-Key, kein einziger unklassifizierbarer String
im gesamten Bestand. Nach dem Lauf verifiziert: alle 8 Kategorien korrekt gesät, die eine reale
Zeile trägt `category_id` mit dem korrekten Bezug auf "Pläne".

**Vier bestehende Endpunkte mussten für ein funktionsfähiges Gesamtbild mit angefasst werden**
(nicht Teil der ursprünglichen "nur Stammdaten"-Anfrage im engeren Sinne, aber ohne sie hätte die
neue NOT-NULL-Spalte ab dem Moment der Migration jeden neuen Upload/jede Aktualisierung brechen
lassen -- ein unvollständiger Zustand wäre schlechter gewesen als die kleine, surgical
Erweiterung): `upload_customer_document()`/`upload_project_document()`
(`app/routers/customers.py`/`projects.py`) und `update_customer_document()`/
`update_project_document()` (`app/routers/customer_documents.py`/`project_documents.py`) befüllen
`category_id` jetzt über die neue `resolve_category_id()` zusätzlich zum unveränderten
`category`-Freitext.

**Echter Fund über diese vier Endpunkte hinaus, beim Testlauf entdeckt und sofort behoben**: der
Lieferschein-Upload `upload_work_preparation_delivery_note()`
(`app/routers/work_preparation.py`) legt ebenfalls eine `ProjectDocument`-Zeile
(`category="Lieferscheine"`) an -- ohne dieselbe Korrektur hätte dieser Endpunkt in Produktion mit
einem `IntegrityError: NOT NULL constraint failed` fehlgeschlagen, sobald die Migration gelaufen
wäre. Zwei bestehende Tests (`tests/test_v066_audit_history.py`,
`tests/test_v083_material_bulk_assignment.py`) konstruierten `ProjectDocument` ebenfalls direkt
ohne `category_id` (Regel 7: Modell-Konstruktoren gegen `app/models.py` prüfen, hier: eine neue
NOT-NULL-Spalte trifft auch bestehende Test-Fixtures) -- beide nachgezogen.

**Router und Oberfläche** (`app/routers/document_categories.py`, Muster
`app/routers/roof_areas.py`s Bauteilarten-Endpunkte): `GET/POST/PUT` + `activate`/`deactivate`,
Büro/Admin (`require_role(ROLE_ADMIN, ROLE_OFFICE)`) -- bewusst KEIN DELETE-Endpunkt in dieser
Runde (die beiden fest gesperrten Kategorien dürfen ohnehin nie verschwinden, ob ein
"Löschen blockiert bei Verwendung"-Mechanismus wie bei `RoofComponentType` gebraucht wird,
entscheidet sich erst, wenn echte Dokumente `category_id` in nennenswerter Zahl tragen).
Einstellungen → Dokumente → "Dokumentkategorien" (neuer Abschnitt, `settings.html`): Liste +
Bearbeiten-Panel, spiegelt beide Schlösser in der Oberfläche selbst (das "Sensibel"-Kontrollkästchen
lässt sich nach dem Setzen nicht mehr entfernen, "Für Monteure sichtbar" ist deaktiviert, sobald
sensibel oder fest gesperrt) -- rein kosmetisch, die eigentliche Durchsetzung sitzt serverseitig
in `create_category()`/`update_category()`.

**20 neue Tests** (`tests/test_v266_document_categories.py`): Selbst-Seeding (inkl. "rührt eine
bereits gesäte Zeile nie wieder an"), beide Schlösser einzeln (inkl. der
DB-Manipulations-Simulation für Schloss 2), Router-Rollenprüfung (`field` bekommt 403 auf jeden
Endpunkt), die Freitext-Zuordnung `resolve_category_id()` (Treffer/Rückfall), die vier
Regressions-Endpunkte (Upload/Update setzt `category_id` tatsächlich), und die Migration isoliert
(`_resolve_category_id()`/`_seed_default_categories()`/`_backfill_table_category_ids()` direkt
gegen eine eigene, leichte Connection aufgerufen -- kein `batch_alter_table()`-Aufruf getestet,
siehe CLAUDE.md "Testen" für die Begründung, warum nur die Befüll-Logik, nicht der Schema-Umbau
selbst geprüft wird).

**Bewusst NICHT Teil dieser Version** (nächste, noch zu bestätigende Etappen): die mobile
Objektansicht (Punkt 1 oben, inkl. der noch offenen Frage "eigene objektbezogene Ablage oder
Sammelprojekt je Objekt für eigene Monteur-Uploads"), die geteilte, feldbegrenzte Suche (Punkt 4
oben), und ein tatsächlicher Upload-Weg für Objektdateien selbst -- diese Version legt
ausschließlich das Fundament, mit dem eine künftige Datei ihre Kategorie zuordnen und ein Monteur
später geprüft werden kann, ob er sie sehen darf.

### Schritt 2 (seit 1.3.63): die mobile Objektansicht

Baut auf dem Kategorie-Fundament aus 1.3.62 auf. Erst die Ansicht selbst, die geteilte Suche
(Punkt 4 aus der ursprünglichen Betreiber-Entscheidung, siehe oben) kam als eigener, späterer
Schritt -- in dieser Version war `/mobil/objekt/{property_id}` deshalb nur über eine bekannte
Objekt-ID erreichbar, nicht aus `/mobil` heraus verlinkt. **Seit 1.3.64 verlinkt, siehe "Schritt 3"
unten.**

**Punkt 2 der Anfrage (Objekt- statt Sammelprojekt-Ablage), entschieden**: neue Tabelle
`PropertyDocument` (`app/models.py`), direkt an `Property` gebunden -- die vom Betreiber
favorisierte Variante. Begründung, wie angefragt geprüft: ein Sammelprojekt je Objekt hätte in
JEDER projektbezogenen Auswertung (Projektliste, Kennzahlen, Rechnungslauf-Kandidaten) als
scheinbar echter Vorgang mitgezählt, ohne einer zu sein -- eine eigene Tabelle vermeidet das
vollständig, kostet dafür eine zusätzliche, aber sehr schlanke Tabelle (nur `property_id`,
`category_id`, Datei-Metadaten, `uploaded_by_employee_id`). Anders als `CustomerDocument`/
`ProjectDocument` trägt sie bewusst NUR `category_id`, keinen zusätzlichen freien
`category`-String -- der Freitext existiert dort ausschließlich wegen Altbestands-Kompatibilität
(1.3.62 musste bestehende Freitext-Werte weiter matchen lassen), eine brandneue Tabelle ohne
Altbestand hat diesen Zwang nicht. **Auffindbarkeit fürs Büro geprüft, wie verlangt**: ein neuer
Abschnitt "Objektdateien" auf `property.html` zeigt dieselbe zusammengeführte Liste
(`list_merged_documents_for_property()`, `app/property_documents.py`) ungefiltert -- ein
Monteur-Upload landet dort sofort sichtbar, mit Upload-/Löschmöglichkeit auch fürs Büro selbst.

**Zwei Dokumentquellen, eine Funktion**: `list_merged_documents_for_property(db, property_id, *,
field_visible_only=False)` führt `PropertyDocument` (eigene Objekt-Uploads) UND `ProjectDocument`
aus ALLEN NICHT ARCHIVIERTEN Projekten des Objekts (`Project.property_id`) zusammen, sortiert
nach Kategorie-Reihenfolge -- wie vom Betreiber vorgegeben ("ein Dachdecker denkt in Objekten,
nicht in Projektnummern"). `CustomerDocument` bleibt bewusst AUSSEN VOR -- Kundenebene, nicht
Objektebene, gehört fachlich nicht zu "den Dokumenten dieses Objekts". Dieselbe Funktion bedient
Büro (`field_visible_only=False`, voller Bestand) UND Monteursansicht
(`field_visible_only=True`) -- kein zweiter, divergierender Weg (Muster: genau die Lehre aus
`build_customer_and_meta_block()`, siehe "Kopfbereich" oben).

**Bildverkleinerung wie 1.2.17, aber keine Wiederverwendung von `resize_and_store_photo()`**: die
bestehende Funktion (`app/service_report_photos.py`) ist fest an ihr eigenes `PHOTO_ROOT`
gebunden, nicht parametrisierbar -- `app/property_documents.py` trägt deshalb eine eigene,
strukturell identische Kopie (`_store_uploaded_file()`) mit eigenem `PROPERTY_ROOT`
(`DACHKONZEPTE_PROPERTY_FILE_ROOT`, neunte Env-Var dieser Art, siehe "Geheimnisse für den
Serverbetrieb" oben). Bilder werden verkleinert (1600px, JPEG q82), Dokumente (PDF u. Ä.) bleiben
im Original -- dieselbe Unterscheidung wie ursprünglich verlangt.

### Punkt 3 (Rechte) -- die eine bewusste Ausnahme im ganzen Rechtekonzept

Ab der mobilen Objektansicht gilt eine ANDERE Zugriffsregel als überall sonst im Rechtekonzept
(siehe eigener Abschnitt oben): **ein Monteur erreicht JEDES Objekt über seine ID, nicht nur die
eigenen** -- die sonst übliche Zuordnungsprüfung (`list_field_relevant_property_ids()`,
Planungsbezug) wird hier ausdrücklich NICHT angewendet, wie vom Betreiber vorgegeben ("die alte
Grenze 'nur zugeordnete Objekte' ist für diese Ansicht aufgehoben"). Die Grenze sitzt
stattdessen ausschließlich im INHALT:

- **Objektfelder**: `PropertyAccessOut` (bereits bestehendes Schema aus dem Rechtekonzept, seit
  1.3.51, dort für `GET /api/orders/{order_id}/property`) -- `id`/`name`/`street`/`postal_code`/
  `city`/`access_notes`/`site_contact_name`/`site_contact_phone`, bewusst OHNE `notes`,
  `customer_id`, `is_primary_address`. `GET /api/field-view/properties/{property_id}`
  (`app/routers/field_view.py`) liefert es unverändert bei jeder existierenden `property_id` --
  kein zweites, neues Schema nötig, das bestehende war bereits exakt die richtige Teilmenge.
- **Dokumente**: `field_may_see_category()` (beide Schlösser aus 1.3.62) filtert JEDE Anzeige --
  bei der Auflistung (`GET .../properties/{id}/documents`) UND ERNEUT, unabhängig davon, am
  Datei-Ausliefer-Endpunkt (`GET .../documents/{source}/{document_id}/view|download`). Eine über
  die Liste nie gezeigte, aber per geratener `{source}/{document_id}` angefragte Datei aus einer
  gesperrten Kategorie liefert denselben 404 wie eine tatsächlich nicht existierende Datei --
  ununterscheidbar, damit eine Anfrage nicht einmal bestätigt, dass die Datei existiert. Der
  Ausliefer-Endpunkt prüft zusätzlich, dass das Dokument tatsächlich zu der in der URL
  angegebenen `property_id` gehört (bei `source=project` zusätzlich: das Projekt ist nicht
  archiviert) -- eine Korrektheitsmaßnahme, kein Rechte-Schutz im engeren Sinn (jedes Objekt ist
  ohnehin erreichbar), aber sie verhindert, dass eine Objekt-URL fremde Dokument-IDs "durchreicht".
- **Eigene Uploads**: `POST .../properties/{property_id}/documents` prüft `category_id`
  serverseitig gegen `field_may_see_category()` -- unabhängig davon, was
  `GET .../document-categories` (die Kategorie-Auswahl der Oberfläche, selbst bereits nur
  freigegebene Kategorien listend) anbietet. Ein direkter API-Aufruf mit einer gesperrten
  Kategorie schlägt mit 422 fehl, exakt wie über die Oberfläche.
- **Wartungshistorie**: `list_maintenance_history_for_property_field()` (`app/service_reports.py`,
  neu aus der bereits bestehenden `_property_history_reports()`-Abfrage herausgelöst in eine
  property_id-first-Variante `_property_history_reports_for_property_id()`) liefert dasselbe,
  bereits etablierte reduzierte `ServiceReportHistoryOut`-Schema wie
  `list_property_history_for_field()` (Rechtekonzept → "Berichts-Eigentümerschaft") --
  objektbezogen statt auftragsbezogen, deshalb ohne den dortigen Ausschluss "nicht der eigene
  Auftrag" (hier gibt es keinen "eigenen" Auftrag, von dem aus die Ansicht geöffnet wurde).

**Angriffstest (`tests/test_v267_property_field_documents.py`, 15 Tests), wie verlangt**:
fremdes Objekt über die ID öffnen -- erlaubt, aber nur die harmlosen Felder (per
`set(body) == {...}`-Vergleich belegt, kein `notes`/`customer_id`); Datei aus gesperrter
Kategorie über geratene ID -- 404, inklusive einer direkten Datenbank-Manipulationssimulation
(dieselbe Technik wie 1.3.62: `DocumentCategory.is_field_visible` direkt auf `True` gesetzt,
`field_may_see_category()` bleibt trotzdem bei `False`, da `HARD_LOCKED_CATEGORY_KEYS`
unabhängig geprüft wird); Datei eines ANDEREN Objekts über die URL -- 404, obwohl dieselbe Datei
über die korrekte `property_id` abrufbar ist; archivierte Projekte vollständig ausgeschlossen
(Liste UND Datei-Abruf); Upload in eine nicht freigegebene bzw. fest gesperrte Kategorie --
422, server- nicht nur oberflächenseitig; kein Endpunkt dieser Runde liefert ein Preis-/Kosten-/
internes Feld (rekursiver Schlüssel-Scan über alle vier neuen Endpunkte, Fehlerklasse
`purchase_price` aus 1.3.53); Büro sieht einen Monteur-Upload sofort in der eigenen Liste. Ein
zweiter Punkt (Upload ohne Mitarbeiterverknüpfung -- 422) rundet das ab. Null "durchgelassen".

### Schritt 3 (seit 1.3.64): die geteilte Suche als Einstieg

Letzter, ursprünglich zweimal zurückgestellter Punkt (Punkt 4 der Betreiber-Entscheidung, siehe
oben) -- ein Monteur bekommt einen Weg, ein Objekt zu FINDEN, statt seine ID zu kennen. Mit
dieser Version gilt: "Damit ist die Monteursansicht vollständig" (Betreibervorgabe).

**Geteilte Kernfunktion statt zwei divergierender Implementierungen** (`app/search.py`, neu) --
die Büro-Suche existiert weiterhin nicht (nur Befund, nie gebaut), diese Datei ist trotzdem
bereits als geteilter KERN angelegt: eine künftige Büro-Suche ERWEITERT ihn um weitere
Datensatzarten (Kunden, Aufträge, ...), ersetzt ihn nicht. Zwei bewusst getrennte Schichten:

1. `search_properties(db, query, *, limit=10)` -- reine Datenbeschaffung, KEINE Rollenprüfung.
   Sucht `Property` nach Name/Straße/PLZ/Ort UND dem Namen des zugehörigen Kunden (Join), gibt
   volle `Property`-ORM-Objekte zurück. Eine zu kurze Anfrage (< `MIN_QUERY_LENGTH=2`) liefert
   bewusst `[]` statt der ersten N Objekte -- eine Vorschlagsliste ohne brauchbaren Suchbegriff
   wäre irreführend, und ein Ein-Zeichen-Muster (`ILIKE('%e%')`) würde einen unnötig breiten
   Treffer über nahezu den ganzen Bestand erzeugen.
2. `field_safe_property_search_results()`/`search_properties_for_field()` -- reduziert JEDES
   Ergebnis auf `id`/`name`/`city` (Punkt 3 der Anfrage: nur so viel wie zur Identifikation
   nötig, kein Kunde, keine volle Adresse, keine Kundennummer).

**Die Feldbegrenzung sitzt serverseitig, an der Rolle, nicht an der URL** (wie ausdrücklich
verlangt): `GET /api/field-view/properties/search` (`app/routers/field_view.py`, registriert VOR
`GET .../properties/{property_id}` -- sonst die bereits mehrfach dokumentierte
Literal-vs-Platzhalter-Kollision, "search" scheitert am `int`-Platzhalter mit 422) ruft
UNABHÄNGIG vom Aufrufer immer `search_properties_for_field()` auf -- dieser Endpunkt IST die
Monteurs-Suche, kein gemeinsamer, rollenabhängig antwortender Endpunkt. Eine künftige,
reichhaltigere Büro-Suche bekommt einen EIGENEN Endpunkt auf `search_properties()` -- der
Moduldocstring von `app/search.py` hält als verbindliche Regel fest, dass JEDER künftige, auch
für `field` erreichbare Endpunkt (auch ein gemeinsamer Büro+Monteur-Endpunkt) bei `role==
ROLE_FIELD` zwingend `search_properties_for_field()` aufrufen muss, nie die volle Kernfunktion
direkt zurückgeben darf. `response_model=list[PropertySearchHitOut]` (`app/schemas.py`) kappt
zusätzlich strukturell auf genau drei Felder (seit 1.3.65: vier, siehe Nachtrag unten) -- eine
zweite, unabhängige Sperre, falls die Funktion selbst je einen Fehler hätte. `q` ist der einzige
Client-Parameter; `limit` ist bewusst
NICHT client-steuerbar (fest auf `SEARCH_RESULT_LIMIT=10`), ein `?limit=99999` kann nie mehr als
zehn Treffer erzwingen, unbekannte Parameter (`?type=customer` u. Ä.) ignoriert FastAPI ohnehin.

**Index-Frage geprüft, nicht nur angenommen** (wie ausdrücklich verlangt): empirisch gegen die
echte, lokale `dachkonzepte_erp.db` mit `EXPLAIN QUERY PLAN` belegt -- `customers.name` trägt
bereits einen B-Baum-Index (`ix_customers_name`), trotzdem zeigt `SELECT * FROM customers WHERE
name LIKE '%test%'` `SCAN customers` (voller Tabellenscan, Index vollständig ignoriert). Ein
gewöhnlicher B-Baum-Index unterstützt nur Präfix-Suchen (`LIKE 'term%'`), keine Substring-Suchen
mit führendem Platzhalter -- ein neuer Index auf `Property.name`/`street`/`postal_code`/`city`
wäre für dieses Abfragemuster ebenso wirkungslos. Bei der aktuellen Datenmenge (163 Objekte, 162
Kunden) ist ein voller Tabellenscan je Suchanfrage ohnehin irrelevant (< 1ms) -- deshalb **keine
neue Migration für Indizes**. Die tatsächlich wirksamen Hebel gegen zu teure Anfragen sind
`MIN_QUERY_LENGTH` (verhindert eine sehr breite Anfrage bei nur einem Zeichen) und der
client-seitige Debounce (siehe unten) -- beide bereits eingebaut. Sollte die Datenmenge um
Größenordnungen wachsen, wäre der richtige nächste Schritt PostgreSQL `pg_trgm`/SQLite `FTS5`,
kein gewöhnlicher B-Baum-Index -- als Hinweis für später festgehalten, nicht gebaut.

**Oberfläche** (ursprünglich `app/templates/mobil.html`, seit 1.3.65 in `_mobile_header.html`
umgezogen, siehe Nachtrag unten): ein Suchfeld, `{% include "_debounce.html" %}` (derselbe,
bereits bestehende, generische `debounce(fn, ms)`-Helfer wie bei `roof_area.html`/
`service_reports.html`, hier zum ersten Mal für eine Suche statt eines Autosave verwendet -- der
Helfer selbst ist dafür bereits geeignet, siehe CLAUDE.md-Fußnote zu `_debounce.html`) mit 300ms
Verzögerung nach dem letzten Tastendruck. Eine Vorschlagsliste zeigt Objektname und Ort je
Treffer, ein Klick führt direkt zu `/mobil/objekt/{id}`. Bei genau zehn Treffern (dem Limit) ein
Hinweistext "Weitere Treffer möglich -- Suche verfeinern" -- ohne einen zusätzlichen
Zähl-Request: der Server liefert keine Gesamtzahl, das Erreichen des Limits ist die naheliegende
Annahme, dass mehr existieren könnten. Eine Anfrage unter zwei Zeichen löst client-seitig gar
keinen Request aus (spart den Roundtrip, den `MIN_QUERY_LENGTH` serverseitig ohnehin verwerfen
würde). Keine Ergebnisseite mit Filtern (wie bei einer künftigen Büro-Suche) -- die
Vorschlagsliste genügt, wie ausdrücklich vorgegeben.

**Angriffstest (`tests/test_v268_property_search.py`, 12 Tests), wie verlangt**: findet ein
Monteur über die Suche etwas anderes als Objekte -- nein, jede Antwort des tatsächlichen
Router-Endpunkts enthält ausschließlich `id`/`name`/`city` (seit 1.3.65 zusätzlich
`customer_name`, siehe Nachtrag -- rekursiver Schlüssel-Scan, Fehlerklasse `purchase_price`);
liefert die Vorschlagsantwort ein gesperrtes Feld mit (Kundennummer, interne Notiz) -- nein, auch
bei einem Treffer über den Kundennamen bleibt die Antwort auf die drei harmlosen Objektfelder
beschränkt (Stand 1.3.64 -- seit 1.3.65 ist der Kundenname selbst ein viertes, bewusst erlaubtes
Feld, alles andere über den Kunden bleibt weiterhin gesperrt); kommt ein Monteur, der den
Such-Endpunkt mit anderen Parametern aufruft (`type=customer`, `full=true`, `fields=all`,
`limit=99999`), an mehr als Objekte -- nein, unverändert höchstens zehn Treffer, unverändert nur
die (seit 1.3.65: vier) erlaubten Felder. Zusätzlich: Literal-vs-Platzhalter-Kollisionscheck
(`.../search` scheitert nicht am `{property_id}`-Platzhalter), `MIN_QUERY_LENGTH`-Grenze,
Limit-Kappung bei 15 tatsächlich angelegten Treffern. Null "durchgelassen". Damit ist die
Monteursansicht laut Betreibervorgabe vollständig.

### Nachtrag (seit 1.3.65): Kundenname in den Vorschlägen, Suche in die Kopfzeile

Zwei vom Betreiber nach dem ersten Einsatz gemeldete Anpassungen an der 1.3.64-Suche.

**Punkt 1 -- Kundenname in den Vorschlägen.** Nur Objektname und Ort reichten zur Identifikation
nicht: ein Objekt ist ohne Kundenname schwer einzuordnen, besonders wenn ein Kunde mehrere
Objekte hat. `PropertySearchHitOut` (`app/schemas.py`) bekommt ein viertes Feld `customer_name`
-- bewusst NICHT sensibel (ein Monteur, der zum Objekt fährt, kennt den Kunden ohnehin), im
Unterschied zu Kundennummer/interner Notiz/voller Adresse/allem Finanziellen, die weiterhin
gesperrt bleiben. Die reine Kernfunktion `search_properties()` (Schicht 1, siehe oben) bleibt
unverändert rollenlos -- nur `field_safe_property_search_results()` (Schicht 2) wurde erweitert,
mit `selectinload(Property.customer)` in `search_properties()` bereits vorgeladen, damit der
Zugriff auf `p.customer.name` keine zusätzliche Abfrage je Treffer auslöst. Der Angriffstest aus
1.3.64 wurde angepasst statt neu geschrieben: die Erwartung "nur id/name/city" wird überall zu
"id/name/city/customer_name", ein eigener Test belegt zusätzlich, dass ein Treffer über den
Kundennamen (`Customer.name` als Suchkriterium) den Namen zwar jetzt zeigen darf, aber sonst
nichts Weiteres über den Kunden durchlässt (12 Tests weiterhin in
`tests/test_v268_property_search.py`, teils erweitert, teils umbenannt).

**Punkt 2 -- Suche in die Kopfzeile.** Das Suchfeld saß bisher nur auf `mobil.html` ("Einsätze"),
unerreichbar von den drei anderen Monteursseiten aus. Umgezogen in `_mobile_header.html` -- die
gemeinsame, schlanke Kopfzeile, die `mobil.html`/`mobil_objekt.html`/`field_timesheet.html`/
`time_tracking_field.html` ohnehin schon alle einbinden -- damit ist die Suche automatisch von
jeder dieser vier Seiten aus erreichbar, ohne dass jede sie einzeln nachbauen müsste. Der
Debounce-Helfer (`_debounce.html`) zog mit um -- genau einmal eingebunden (in
`_mobile_header.html` selbst), keines der vier Templates bindet ihn zusätzlich eigenständig ein,
sonst wäre `debounce()` doppelt definiert.

**Bei der Gelegenheit die alte, seit 1.3.45 bestehende Stapel-Architektur der Kopfzeile
abgelöst.** Kopf (`.mobile-header`) und Reiter (`.mobile-nav`) waren bisher zwei EINZELN sticky
positionierte Elemente, die sich über einen hart codierten `top:45px`-Wert am Reiter aufeinander
stapelten (der Kopf-Höhe geschätzt, nie exakt vermessen -- funktionierte bisher nur, weil sich
zwischen beiden nichts einschob). Eine neue Zeile dazwischen hätte diesen Wert neu vermessen
müssen, UND hätte bei jeder künftigen Änderung der Kopf-Höhe (z. B. ein längerer Mitarbeitername)
erneut brechen können -- ein fragiles Muster für exakt das, was jetzt gebraucht wurde. Ersetzt
durch EINEN gemeinsamen sticky-Wrapper (`.mobile-header-wrap`), der Kopf/Suchfeld/Reiter als
normale, nie überlappende Blockzeilen enthält -- kein Pixelwert mehr zu pflegen, unabhängig von
der tatsächlichen Höhe jeder Zeile. Das beantwortet zugleich die geforderte Prüfung für beide
Bildschirmgrößen: auf einem schmalen Smartphone-Hochformat können normale Blockzeilen sich
strukturell nicht überlappen, unabhängig von der Fensterbreite -- kein Sonderfall nötig.

**Die Vorschlagsliste überlagert die Reiter bewusst NICHT.** Naiv direkt unter dem Eingabefeld
geöffnet, hätte sie visuell über den darunterliegenden Reitern gelegen (Suchfeld steht jetzt ÜBER
den Reitern, eine aufklappende Liste reicht überall dorthin herab) -- ein Tipp auf einen Reiter
bei offener Liste hätte dann zuerst die Liste getroffen (und nur geschlossen), nicht den Reiter
selbst; ein zweiter Tipp wäre nötig gewesen, genau das vom Betreiber benannte Risiko ("ein
offener Vorschlag ... darf nicht stehenbleiben"). Behoben durch die Positionierung: die
Vorschlagsliste ist ein Kind des GANZEN sticky-Wrappers (nicht nur des Suchfelds), mit
`top:100%` relativ zu dessen Unterkante -- sie öffnet sich dadurch strukturell erst UNTERHALB der
Reiter, kann sie also nie überdecken. Die Reiter bleiben damit bei offener Liste jederzeit mit
einem einzigen Tipp erreichbar. Dass eine offene Liste beim tatsächlichen Wechsel der Seite
verschwindet, ergibt sich zusätzlich schon aus der Architektur dieses Projekts (klassische
Mehrseiten-Navigation, kein SPA, siehe CLAUDE.md "Stack & Struktur") -- ein Tipp auf einen Reiter
lädt ohnehin die komplette Seite neu.

**Maximalbreite fürs Tablet.** Suchfeld UND Vorschlagsliste bekommen `max-width:640px` mit
zentrierenden Rändern (`margin:auto`) -- auf einem Tablet wirkt das Feld dadurch nicht unnötig
breit, auf einem Smartphone (immer schmaler als 640px) ändert die Regel nichts, das Feld bleibt
dort ohnehin voll breit.

**Kein echter Browser-Screenshot möglich** (dieselbe, wiederholt dokumentierte
Werkzeug-Einschränkung dieser Umgebung) -- die Layout-/Überlappungsfreiheit ist ausschließlich
strukturell an den Template-Quellen nachgewiesen (`tests/test_v269_mobile_header_search.py`, 8
Tests: Suchfeld/-liste liegen in `_mobile_header.html`, nicht mehr in `mobil.html`; der
Debounce-Helfer ist genau einmal eingebunden; alle vier Seiten binden die Kopfzeile ein; die
Vorschlagsliste steht strukturell nach `<nav>`; Kopf/Reiter tragen kein `position:sticky` mehr
einzeln; die Maximalbreite ist gesetzt), nicht an einem gerenderten Bild. Sollte bei Gelegenheit
im Browser gegengeprüft werden, insbesondere das Verhalten bei offener Vorschlagsliste auf einem
echten Touchscreen.

### Wartungsbericht-Detailansicht (seit 1.3.69)

Anlass: ein Monteur führt dieselbe Wartung erneut durch und will nachvollziehen, was beim
letzten Einsatz gemacht wurde -- auch von einem inzwischen ausgeschiedenen Kollegen. Die mobile
Objektansicht zeigte dafür bisher nur das reduzierte Wartungshistorie-Schema
(`ServiceReportHistoryOut`, seit 1.3.56/1.3.63) -- Datum, Berichtstyp, Monteur, Prüfergebnisse,
Mängel mit Status, aber keinen Weg, den einzelnen Bericht im Detail (samt Fotos) oder als PDF zu
öffnen. Vorab ein reiner Befund, dann auf Bestätigung gebaut.

**Befund, der die ursprüngliche Annahme korrigiert.** Die Anfrage ging von einem "PDF ohne
Preise" aus -- tatsächlich enthält das Bericht-PDF an KEINER Stelle einen Preis:
`ServiceReportMaterial` trägt strukturell keine Preisspalte (der Monteur erfasst nur, WAS
verbraucht wurde, siehe Klassendocstring in `app/models.py`), `TimeEntry` hat kein Preis-/
Stundensatzfeld. Der einzige Abschnitt, der für einen Monteur gesperrt bleiben muss, ist
"Erfasste Zeiten" (`app/service_report_pdf.py`) -- wegen der FREMDEN PERSONENDATEN (wer hat wann
wie viele Stunden gebucht), nicht wegen eines Preises. Ebenso geprüft und mit KEINEM FUND
bestätigt: ein vermutetes `internal_note`-Feld existiert an keiner Stelle im reduzierten Schema
oder den zugrunde liegenden Modellen (`ServiceReport`/`Finding`/`InspectionItem`) -- ein
rekursiver Schlüssel-Scan (Muster `test_maintenance_history_carries_no_prices_purchase_values_
or_customer_notes`, `tests/test_v260_role_audit.py`, hier um zusätzliche Suchbegriffe erweitert)
bestätigt das, nichts wurde entfernt.

**Ein Schalter statt eines eigenen Renderers.** Weil der einzige zu entfernende Abschnitt schon
vorher isoliert war (eine einzige `if entries:`-Tabelle am Ende der Story), reicht ein neuer,
optionaler Parameter: `build_service_report_pdf(db, report, include_time_entries=False)` lässt
"Erfasste Zeiten" komplett weg -- `list_entries()` wird dabei GAR NICHT ERST aufgerufen, nicht
nur die Tabelle ausgeblendet (per Test mit einem Aufruf-Wächter belegt, der eine Ausnahme wirft,
falls die Funktion doch aufgerufen würde). Alles andere bleibt exakt wie im Kundendokument,
inklusive des "Monteur"-Meta-Felds (`created_by_employee_name`) -- das bleibt ausdrücklich
sichtbar (Vorgabe: "damaliger Monteur" ist erlaubt), nur ein ZWEITER, fremder Zeitbucher
verschwindet. `build_service_report_pdf_for_field()` ist die dünne, dokumentierende
Wrapper-Funktion für genau diesen Aufruf -- kein zweiter, paralleler Renderer nach dem Muster
des Angebots-Umbaus (1.3.13): der wäre für "eine von zehn Abschnitten weglassen" unverhältnismäßig
gewesen.

**Zugang ausschließlich über das Objekt.** Neuer Endpunkt `GET /api/field-view/properties/
{property_id}/maintenance-history/{report_id}/pdf` (`app/routers/field_view.py`) --
`resolve_property_history_report_for_field()` (`app/service_reports.py`) verifiziert am
Abrufzeitpunkt ERNEUT, dass der Bericht tatsächlich zu GENAU diesem Objekt gehört und bereits
unterschrieben ist (`status=="unterschrieben"`, dieselbe Grenze wie die Historie selbst) -- Muster
`resolve_property_document_for_field()` (`app/property_documents.py`, seit 1.3.63): sonst `None`,
der Router liefert dafür 404, ununterscheidbar von "existiert nicht", NIE ein 403 (kein
Bestätigen per URL-Raten, dass irgendein Bericht mit dieser ID existiert). Bewusst OHNE die
Ersteller-Prüfung von `require_field_report_ownership()` (`app/routers/orders.py`, Rechtekonzept
-> "Berichts-Eigentümerschaft") -- die Wartungshistorie zeigt einem Monteur schon immer fremde
Berichte desselben Objekts (`list_maintenance_history_for_property_field()`, seit 1.3.56/1.3.63),
diese Version ist nur die Detail-Variante derselben, bereits etablierten Ausnahme: Objekt- statt
Ersteller-Zugehörigkeit, nur lesend, als vollständiges Dokument statt der reduzierten Liste.
`require_field_report_ownership()`s Docstring trägt seither eine ausdrückliche Notiz zu dieser
Ausnahme, damit die Behauptung dort ("nur die reduzierte Zusammenfassung, nicht mehr") nicht
stillschweigend falsch wird.

**Nur Lesen.** Unter diesem Pfad existiert kein PUT/DELETE/sign (405 bei einem Versuch, da nur
GET registriert ist) -- die bestehenden Berichts-Endpunkte (`PUT`/`DELETE`/`.../sign`) bleiben
unverändert über `require_field_report_ownership()` auf den eigenen Bericht beschränkt, komplett
unberührt von dieser Änderung (per Test belegt: derselbe Monteur, der über das Objekt lesen darf,
bekommt über den klassischen Weg weiterhin 403 für PUT/DELETE/sign an einem fremden Bericht).

`app/templates/mobil_objekt.html`s `renderHistory()` bekommt dafür einen "Als PDF ansehen"-Link
je Historieneintrag (Muster der bereits bestehenden `.doc-actions`-Knöpfe). 9 neue Tests
(`tests/test_v273_maintenance_report_field_detail.py`): geratene `report_id` ohne echten
Objektweg, ein Bericht, der zu einem ANDEREN Objekt gehört, ein noch nicht unterschriebener
Entwurf, interne/preisähnliche Schlüssel (rekursiver Scan), die fremde Zeitbuchung im PDF-Text,
und ein Schreibversuch über den alten UND den neuen Weg -- null "durchgelassen".

## Büro-Suche (seit 1.3.66, Etappe 1)

Der ursprüngliche Wunsch aus der Suche-Bestandsaufnahme (siehe "Dateiablage je Objekt" ->
"Schritt 3", 1.3.64): Vorschläge beim Tippen, Ergebnisseite mit Filtern bei Bestätigung, für die
volle "Gruppe A" (17 Datensatzarten) statt nur Objekte. Baut direkt auf zwei bereits bestehenden
Fundamenten auf, ändert an keinem der beiden etwas: dem geteilten Suchkern aus 1.3.64
(`search_properties()` bleibt UNVERÄNDERT die eine Objektsuche, die "properties"-Quelle unten
ruft sie direkt auf -- der 1.3.64-Moduldocstring-Versprecher "eine künftige Büro-Suche erweitert
den Kern, ersetzt ihn nicht" ist damit eingelöst) und dem Rechtekonzept (`require_role()`,
Standardverweigerung). Vor dem Bauen ein reiner Befund-Durchgang (keine Codeänderung), danach vom
Nutzer vier Entscheidungen -- siehe unten, jede einzeln umgesetzt. Zwei Etappen, wie verlangt:
Etappe 1 (diese Version) -- Registry, Kernstruktur, Rollensicherheit; Etappe 2 (Oberfläche:
Suchfeld in der Topbar, Ergebnisseite) folgt erst nach Rückmeldung zu dieser Etappe.

### Registry-Muster (`app/search.py`)

`SearchSource` (frozen dataclass) -- analog im Geist zu `require_role()`s "keine impliziten
Defaults"-Philosophie: `key`/`label`/`allowed_roles`/`query_fn`/`row_fn` sind Pflichtfelder, nur
`module_key` hat einen Default (`None`, siehe unten). `OFFICE_SEARCH_SOURCES` ist ein Tupel aus
17 solchen Quellen -- **Registry und Vollständigkeitstest wurden ZUSAMMEN gebaut, nicht
danach** (ausdrückliche Vorgabe): `tests/test_v270_office_search.py::
EXPECTED_OFFICE_SEARCH_KEYS` vergleicht die tatsächlich registrierten Schlüssel gegen die 17
erwarteten und prüft zusätzlich, dass jede `allowed_roles`-Menge nicht-leer und eine Teilmenge
von `{admin, office}` ist (ROLE_FIELD darf NIE enthalten sein) und jeder `module_key` entweder
`None` oder einer der beiden bekannten Modul-Schlüssel ist -- Muster: dieselbe mechanische
Absicherung wie beim Rollen-Audit-Test (Regel 11), eine Registry ohne erzwungene
Vollständigkeit ist nur ein Vorschlag, keine Absicherung.

`search_office(db, role, query, *, limit_per_type=20, types=None)` ist der EINE Dispatcher --
geht die Registry durch und filtert **dreifach**: Rolle (`source.allowed_roles`), optionaler
`types`-Filter (welche Datensatzarten überhaupt durchsucht werden sollen), Modul-Zustand (dritte,
unabhängige Achse, siehe unten). Prüft `MIN_QUERY_LENGTH` (aus der Monteurs-Suche
wiederverwendet, `=2`) EINMAL zentral, bevor irgendeine der 17 Quellfunktionen aufgerufen wird --
keine der 17 prüft es erneut, das ist beabsichtigt. `_count_and_fetch(db, stmt, order_by, limit,
*, options=())` ist der gemeinsame Helfer fast jeder Quelle: EIN gefilterter Basis-`stmt`, zwei
Verwendungen (eine echte `COUNT(*)`-Abfrage für die reale Trefferzahl, eine gekappte, geordnete
Liste für die Anzeige) -- kann nie auseinanderlaufen, im Unterschied zu
`build_customer_and_meta_block()`s historischer Divergenz in drei Varianten (siehe
"Kopfbereich"), die hier von Anfang an vermieden wird.

**Der Fund beim Customer-Suchen (Regel 7, vor dem Schreiben geprüft, nicht aus dem Gedächtnis
geraten)**: `Customer.customer_number` ist ein Python-`@property` (`self.profile.customer_number
if self.profile else None`), KEINE gemappte Spalte -- `Customer.customer_number.ilike(...)` in
einer Query würde mit einem `AttributeError` scheitern (ein Property-Descriptor kennt kein
`.ilike()`). Die "customers"-Quelle joint deshalb `CustomerProfile` (`outerjoin`, ein Kunde ohne
Profil-Zeile bleibt trotzdem über `Customer.name` allein auffindbar) und filtert auf
`CustomerProfile.customer_number` -- die tatsächliche, gemappte Spalte. Zum Vergleich geprüft:
`Order.customer_number`/`Invoice.customer_number`/`Supplier.supplier_number`/
`Employee.employee_number` sind alle echte, gemappte Spalten -- nur bei `Customer` ist es dieser
eine Sonderfall.

### Die vier Entscheidungen -- jede einzeln umgesetzt

**1. Rechnungen für Büro sichtbar, nichts in der Registry admin-only.** Die Grenze verläuft
zwischen Büro und Monteur, nicht zwischen Admin und Büro -- JEDE der 17 Quellen trägt
`allowed_roles={ROLE_ADMIN, ROLE_OFFICE}`, keine Ausnahme. Geprüfte Rückfrage (Auftrag: "prüfe,
ob es innerhalb der Finanzdaten etwas gibt, das nur Admin sehen soll"): **nein, nichts** --
Kalkulationsgrundlagen sind gar keine Gruppe-A-Entität (eine einzelne Singleton-Settings-Zeile,
nicht durchsuchbar), Einkaufspreise (`Material.purchase_price`) und Vergütung
(`Employee.hourly_wage`/`effective_hourly_wage`/`annual_gross_wage`) sind seit dem
Rechtekonzept (1.3.52) bereits über die normalen Material-/Mitarbeiter-Stammdatenseiten
Büro+Admin-sichtbar -- eine Einschränkung nur am Sucheinstieg wäre inkonsistent mit dem Rest der
Anwendung und würde nichts schützen (Büro sieht dieselben Daten ohnehin auf der jeweiligen
Stammdatenseite). Der tatsächliche, ausreichende Schutz ist unabhängig von der Rolle: JEDE
`row_fn` liefert strukturell ausschließlich `{id, title, subtitle, url}` -- eine reine
Trefferkurzform, nie ein Preis-/Lohn-/Einkaufsfeld, unabhängig davon, welche Rolle sucht.
`OfficeSearchHitOut` (Pydantic, `app/schemas.py`) kappt das zusätzlich strukturell, als zweite,
unabhängige Sperre.

**2. ILIKE statt Volltextsuche.** Empirisch geprüft (nicht angenommen), gegen die echte,
lokale `dachkonzepte_erp.db`: 472 Zeilen über alle 17 Tabellen zusammen (customers=162,
properties=163, roof_areas=4, projects=8, quotes=10, orders=6, invoices=6, reminders=2,
inquiries=0, tasks=7, employees=12, service_reports=4, findings=4, maintenance_contracts=2,
services=24, materials=56, suppliers=2). `EXPLAIN QUERY PLAN` + Zeitmessung an vier
repräsentativen, gejointen ILIKE-Abfragen (Angebot→Projekt→Kunde, Mahnung→Rechnung,
Aufgabe→Projekt, Wartungsvertrag→Kunde): alle ≈0.03ms. Bei dieser Größenordnung ist "ein Query
je Datensatzart" (17 einzelne, kleine Abfragen statt einer UNION-Abfrage über alle Tabellen)
sowohl einfacher zu warten als auch schnell genug -- eine UNION-Query über 17 strukturell
verschiedene Tabellen (unterschiedliche Spalten, unterschiedliche Joins) wäre erheblich
komplexer geworden, ohne einen messbaren Vorteil bei dieser Datenmenge.

**Schwelle für einen künftigen Wechsel, wie ausdrücklich verlangt festgehalten** (damit ein
späterer Durchgang das nicht neu herleiten muss): Volltextsuche (PostgreSQL `pg_trgm`/`tsvector`
bzw. SQLite `FTS5`) wird erst relevant, wenn EINE der beiden folgenden Schwellen überschritten
wird -- (a) die Gesamtzahl der Zeilen über alle 17 Tabellen wächst in den fünfstelligen Bereich
(grobe Faustregel: ab ~50.000-100.000 Zeilen wird ein voller Tabellenscan pro Suchanfrage auf
gewöhnlicher Server-Hardware spürbar, nicht mehr nur theoretisch), ODER (b) eine einzelne Quelle
(am ehesten "properties"/"customers"/"orders", die am schnellsten wachsen) allein bereits
mehrere tausend Zeilen trägt UND die Suche dabei spürbar (>100ms) langsam wird. Beides ist bei
472 Zeilen und ~0.03ms je Abfrage um mehrere Größenordnungen entfernt -- ein neuer Index wäre
hier ebenso wirkungslos wie bei der Monteurs-Suche (siehe "Suche als Einstieg": ein B-Baum-Index
hilft einem präfixlosen `ILIKE('%term%')` weder unter SQLite noch unter PostgreSQL, `EXPLAIN
QUERY PLAN` zeigt `SCAN` selbst bei einem bereits indizierten Feld).

**3. Snapshot UND live-Name durchsucht, unabhängig voneinander.** Der Fund, der sonst zur
stillen Lücke geworden wäre: "orders" und "invoices" durchsuchen IMMER beide Felder --
die eingefrorene Schnappschuss-Spalte (`Order.customer_name`/`Invoice.customer_name`, seit
1.3.31/1.3.32 bereits als für die Suche nutzbar verifiziert, siehe dort) UND die live
`Customer.name` über den Projekt-Join. Wer nach der alten Schreibweise sucht, findet die alte
Rechnung mit dem eingefrorenen Namen; wer nach der heutigen sucht, findet den aktuellen Kunden
UND -- über den JOIN zum heutigen Kunden, nicht über den eigenen unveränderten Schnappschuss --
auch die Rechnung, da sie ja weiterhin zu diesem Kunden gehört. Beide Suchwege bleiben dabei
unabhängig: würde nur die live `Customer.name` gejoint (die Schnappschuss-Spalte selbst nie
geprüft), verlöre eine Suche nach der ALTEN Schreibweise jede Rechnung, deren Kunde inzwischen
umbenannt/umformatiert wurde -- exakt die stille Lücke. Belegt in
`tests/test_v270_office_search.py::test_invoice_found_via_frozen_snapshot_and_customer_found_via_live_name`:
ein Kunde ("Wolfgang Rödchen"), dessen Schreibweise nach einer Rechnung auf "Wolfgang Roedchen"
korrigiert wird -- die Suche nach der alten Schreibweise findet weiterhin die alte Rechnung
(über deren unverändertes `customer_name`-Feld), die Suche nach der neuen findet den
aktualisierten Kunden. "Reminders" durchsucht dagegen nur `Invoice.customer_name` (den
Schnappschuss der zugehörigen Rechnung) -- bei nur zwei Mahnungen im echten Bestand kein
Bedarf für denselben, aufwendigeren Doppel-Join wie bei Aufträgen/Rechnungen.

**4. Ergebnisseite-Begrenzung.** `search_office()` liefert je Datensatzart die REALE Trefferzahl
(`total`, aus `_count_and_fetch()`s unabhängiger `COUNT(*)`-Abfrage) UND eine auf
`limit_per_type` (Standard 20, `OFFICE_SEARCH_RESULT_LIMIT`) gekappte Liste (`hits`) -- die
Oberfläche (Etappe 2) zeigt daraus je Datensatzart die Trefferzahl und "weitere anzeigen" statt
Seitenzahlen, konsistent mit dem Rest des Projekts (siehe CLAUDE.md: nirgends im Projekt gibt es
eine nummerierte Seitenpaginierung).

### Dritte, unabhängige Achse: der Modul-Umschalter

Nicht ausdrücklich vom Nutzer angefragt, aber Konsequenz der bereits bestehenden Regel
("API-Endpunkte müssen den Modul-Zustand selbst prüfen, sonst bleibt die Funktion über die API
erreichbar, obwohl die Oberfläche sie versteckt", siehe "Modul-Umschalter" oben): vier Quellen
hängen an einem abschaltbaren Modul -- `tasks` (Modul `"aufgabenmanagement"`),
`service_reports`/`findings`/`maintenance_contracts` (Modul `"wartungen"`).
`SearchSource.module_key` trägt dafür den jeweiligen Schlüssel (`None` für die übrigen 13),
`search_office()` prüft `is_module_enabled(db, module_key)` für jede Quelle mit gesetztem
`module_key` zusätzlich zur Rolle -- unabhängig davon, ob der Suchende Büro oder Admin ist. Bei
deaktiviertem Modul verschwinden die betroffenen Quellen komplett aus dem Ergebnis, auch wenn
die zugrunde liegenden Daten weiterhin passend wären (per Test belegt).

### Separate-Endpunkt-Prinzip (seit 1.3.64 etabliert, hier bestätigt) und Router

`GET /api/search` (`app/routers/search.py`, neu) ist ein VÖLLIG EIGENSTÄNDIGER Endpunkt --
niemals ein gemeinsamer, rollenverzweigender Endpunkt mit der Monteurs-Suche
(`GET /api/field-view/properties/search`). Das macht `Depends(require_role(ROLE_ADMIN,
ROLE_OFFICE, message=...))` (ROLE_FIELD ausdrücklich NICHT dabei) zur PRIMÄREN Sicherung: ein
Monteur bekommt 403, BEVOR `search_office()` auch nur eine Zeile liest -- die rolleninterne
Filterung in `search_office()` selbst (jede Quelle prüft `role` gegen `source.allowed_roles`)
ist eine zweite, unabhängige Absicherung, kein Ersatz dafür. Automatisch durch den bestehenden
Rollen-Audit-Test (`tests/test_v260_role_audit.py`) erfasst, da `require_role()` die dafür
nötige `_dk_roles`-Markierung trägt -- keine Änderung an jenem Test nötig.

`q` (Suchbegriff), `types` (optionale, kommagetrennte Liste von `SearchSource`-Schlüsseln, um
gezielt nur bestimmte Datensatzarten zu durchsuchen -- Etappe 2 nutzt das für Filter auf der
Ergebnisseite), `limit` (geklammert auf `[1, 100]`, bevor er als `limit_per_type` an
`search_office()` geht -- ein Client kann damit nie mehr als 100 Treffer je Datensatzart
erzwingen, unabhängig vom übergebenen Wert).

### Der verlangte Angriffstest -- null durchgelassen

Mirror des Monteurs-Suche-Angriffstests (1.3.64/1.3.65), gegen eine isolierte Testinstanz (nie
gegen die echte `dachkonzepte_erp.db`): ein Monteur, der `GET /api/search` aufruft -- **plain
UND mit manipulierten Parametern** (`types=invoices,customers,employees`, `limit=999999`) --
bekommt in BEIDEN Fällen **403**, identisch, nie irgendeine Zeile, geschweige denn eine Rechnung
oder ein Preisfeld. Büro/Admin bekommen dagegen 200 mit korrekt gruppierten Ergebnissen
INKLUSIVE einer `invoices`-Gruppe (belegt Entscheidung 1 über den tatsächlichen Router-Weg, nicht
nur die Kernfunktion direkt). Ein rekursiver Schlüssel-Scan über JEDE zurückgegebene Zeile (über
alle 17 Gruppen, mit absichtlich gesetztem `Employee.hourly_wage`/`Material.purchase_price`/
`Service.sale_price` in den Testdaten) findet in keiner Rolle ein Preis-/Lohn-/Einkaufsfeld --
strukturell garantiert, da jede Zeile ausschließlich `{id, title, subtitle, url}` trägt.
`tests/test_v270_office_search.py`, 11 neue Tests, alle grün.

### Bewusst NICHT Teil dieser Etappe

Die Oberfläche (Suchfeld im reservierten `.app-topbar-search-slot`, siehe "Umgestaltung der
Sidebar" -> "Schritt 2", die Ergebnisseite mit Filtern/"weitere anzeigen") -- wartet auf
Rückmeldung zu dieser Etappe, wie ausdrücklich vom Nutzer verlangt ("Nach Etappe 1 ... berichte
mir, bevor die Oberfläche kommt").

### Etappe 2 (seit 1.3.67): die Oberfläche

Nach Rückmeldung zu Etappe 1 gebaut -- Suchfeld in der Topbar, Ergebnisseite. Baut ausschließlich
auf bereits bestehenden Bausteinen auf: dem seit 1.3.45 reservierten `.app-topbar-search-slot`,
`GET /api/search` aus Etappe 1, und `require_role()`/`_role_dep` aus dem Rechtekonzept.

**Suchfeld in der Topbar** (`app/templates/_topbar.html`): rendert nur, wenn
`current_user.role in ("admin", "office")` -- für `field` fehlt das Eingabefeld strukturell im
Markup, kein nie funktionierendes Feld (kleine, opportunistische Vorwegnahme des in "Rechtekonzept"
-> "Sichtbarkeit in der Oberfläche" bereits als künftiges Ziel festgehaltenen "ausblenden statt
ausgrauen" -- ohne den dort beschriebenen größeren Umbau der übrigen Navigation vorzuziehen).
Vorschläge beim Tippen: 300ms Debounce, Mindestlänge 2 Zeichen -- dieselben Werte wie die
Monteurs-Suche, absichtlich NICHT über den geteilten `_debounce.html`-Helfer eingebunden, sondern
ein eigener, winziger Timer direkt in der bestehenden IIFE der Datei: `_topbar.html` wird auf
allen 31 Büro-Seiten eingebunden, von denen mindestens zwei (`roof_area.html`,
`service_reports.html`) `_debounce.html` bereits selbst einbinden -- ein zusätzliches Include hier
hätte die Funktion global doppelt definiert, exakt das Muster, das seit 1.3.65 für die
Monteurs-Kopfzeile bewusst vermieden wird. Ruft ausschließlich `GET /api/search` auf, niemals den
Monteurs-Suchendpunkt (Separate-Endpunkt-Prinzip, siehe oben) -- ein Vorschlag zeigt Gruppen-Label/
Titel/Untertitel, ein Klick führt direkt auf die `url` des Treffers. Bestätigen (Enter) öffnet
`/suche?q=...`. Schließt bei Klick daneben und bei Escape.

**Kleiner, transparent gemeldeter Fund dabei**: die Anfrage ging davon aus, dass Escape die
Monteurs-Suche bereits schließt ("wie in der Monteurs-Suche") -- tatsächlich hatte
`_mobile_header.html` bisher NUR den Klick-daneben-Schluss, keine Escape-Behandlung. Für beide
nachgezogen, nicht nur für die neue Büro-Suche, statt die Prämisse stillschweigend nur für eine
Seite aufzulösen (Muster: dieselbe Transparenz wie bei der 1.3.61-Prämisse-Korrektur zur
Tätigkeit im Nachtrag/Schnellstart).

**Ergebnisseite** (`GET /suche`, `app/routers/pages.py::office_search_page()`,
`app/templates/search_results.html`) -- trägt **dieselbe `_role_dep`-Absicherung wie jede andere
Büro-Seite**, nicht nur der API-Endpunkt dahinter: ein Monteur, der `/suche` über die Adresse
aufruft, bekommt 403 -> `access_denied.html`, bevor überhaupt etwas rendert. Automatisch vom
bestehenden Seiten-Audit-Test erfasst (`_dk_roles`-Markierung über `require_role()`), keine neue
`PAGE_AUDIT_EXEMPT`-Zeile nötig. Zusätzlich per echtem Ende-zu-Ende-Test gegen eine isolierte,
tatsächlich laufende Serverinstanz bestätigt (nicht nur `router_test_client`): ein frisch
angelegtes `field`-Konto bekommt sowohl auf `GET /suche` als auch auf `GET /api/search` über
echtes HTTP 403 -- null durchgelassen.

Die Seite selbst rendert nur das Gerüst, `q`/`types` werden client-seitig aus `location.search`
gelesen (Muster: jede andere Seite in diesem Projekt lädt ihre Daten per `fetch()` nach). Zeigt je
zurückgegebener Gruppe die reale Trefferzahl (`total`) und die auf `limit=20` gekappte Liste
(`hits`) -- "weitere anzeigen" fragt gezielt NUR diese eine Gruppe erneut ab (`types=<key>` +
erhöhtes `limit`), nicht die gesamte Suche neu. Filter nach Datensatzart: 17 Umschalt-Knöpfe
("Alle" setzt zurück), mehrere gleichzeitig wählbar -- die Schlüssel/Beschriftungen sind
client-seitig hartcodiert (`TYPE_LABELS`, kein Endpunkt liefert diese Liste, sie ändert sich nur,
wenn ohnehin die Registry selbst geändert wird), ein Regressionstest gleicht sie gegen
`OFFICE_SEARCH_SOURCES` ab (Schlüssel UND Reihenfolge), damit ein künftiges Auseinanderlaufen
auffällt.

**Tests**: `tests/test_v271_office_search_ui.py` (10 neue Tests -- Seiten-Absicherung,
Typenlisten-Abgleich, Topbar-Verdrahtung), dazu `tests/test_v254_topbar.py::
test_search_slot_is_present_and_empty` in zwei Tests umgeschrieben (die 1.3.45-Erwartung "Suchslot
bleibt leer" ist jetzt bewusst überholt -- ein Test für admin/office, ein Test für field). Volle
Suite weiterhin grün (1344/1344).

### Nachtrag (seit 1.4.4): Aufgaben-Sichtbarkeit in der Büro-Suche

Gemeldete Lücke aus 1.4.3 (siehe Abschnitt "Aufgabe" -> "Sichtbarkeit für Büro-Konten" oben):
`_search_tasks()` (die "tasks"-Quelle) hatte -- anders als jede andere Quelle -- keine
Mitarbeiter-Filterung. Ein Büro-Konto fand über `/suche` auch die persönlich zugewiesene Aufgabe
eines Kollegen, genau die Grenze, die `list_tasks_for_user()` (`GET /api/tasks`, Dashboard) seit
1.4.3 zieht -- zwei Stellen, eine Regel, aber nur an einer gepflegt.

**Behoben durch tatsächliche Wiederverwendung, keine zweite Kopie der Regel** -- ausdrückliche
Vorgabe des Betreibers ("Nutze wenn möglich dieselbe Filterfunktion, nicht eine zweite, die
dieselbe Regel nachbaut -- sonst laufen Liste und Suche beim nächsten Mal wieder auseinander").
`app/tasks.py::list_tasks()`/`list_tasks_for_user()` bekommen einen neuen, optionalen
`search: str | None`-Parameter (Titel-ILIKE, unverändert an `list_tasks()` durchgereicht).
`_search_tasks()` (`app/search.py`) ruft `list_tasks_for_user()` seither **zweimal** auf --
einmal ohne `unassigned_only` ("eigene"), einmal mit ("empfängerlose") -- und vereinigt beide
Ergebnislisten (Duplikate über die `id` entfernt): `list_tasks_for_user()` liefert für die
getrennten Board-Tabs bewusst ENTWEDER eigene ODER empfängerlose Aufgaben (ein
Entweder-Oder-Schalter, richtig so für "Meine Aufgaben"/"Offene Büro-Aufgaben" als zwei getrennte
Ansichten) -- die Suche braucht dagegen beide KOMBINIERT in einer Trefferliste, deshalb zwei
Aufrufe statt einem dritten, neuen Query-Modus. Ein Büro-Konto ohne Mitarbeiterverknüpfung kann
"eigene" nicht bestimmen (`ValueError`) -- das wird abgefangen, damit wenigstens die
empfängerlosen weiterhin gefunden werden (dieselbe Großzügigkeit wie beim direkten Sehen des
gemeinsamen Eingangs), statt die Suche für dieses Konto komplett leer zu lassen.

**Transportmechanismus**: `search_office()` bekommt einen neuen, optionalen
`employee_id: int | None = None`-Parameter (nur für "tasks" relevant, jede andere Quelle
ignoriert ihn -- kein bestehender Aufrufer musste sich ändern, da der Default `None` das
bisherige Verhalten für Admin unverändert lässt). Ein transientes, nie persistiertes
`AppUser(role=role, employee_id=employee_id)`-Objekt trägt beide Werte in
`list_tasks_for_user()` hinein -- dieselbe Technik wie `router_test_client()`s Test-Identität,
kein neuer Mechanismus. **Bewusst kein einheitlicher 4-Parameter-`query_fn` für alle 18
Quellen** (das hätte 17 unbeteiligte Funktionssignaturen um einen ungenutzten Parameter
erweitert) -- `search_office()`s Dispatch-Schleife behandelt "tasks" stattdessen als einzigen,
klar kommentierten Sonderfall (`if source.key == "tasks": ...`), der zusätzlich `role`/
`employee_id` an `source.query_fn` übergibt. `_task_row()` liest seither ein Dict
(`task_to_dict()`-Schema, geliefert von `list_tasks_for_user()`) statt eines ORM-`Task`-Objekts --
Feldnamen entsprechend angepasst (`project_name` statt `t.project.name`).

**Der verlangte Angriffstest** (`tests/test_v270_office_search.py`, vier neue Tests): ein
Büro-Konto findet über die Suche die eigenen UND die empfängerlosen Aufgaben, nie die eines
Kollegen (Kernfunktions- UND echter Router-Test); ein Büro-Konto ohne Mitarbeiterverknüpfung
findet weiterhin die empfängerlosen; Admin findet alle. Ein Monteur findet über die Büro-Suche
gar nichts -- unverändert bereits durch `allowed_roles`/den Router-`require_role()`-Gate
abgedeckt (`test_field_role_gets_nothing_from_any_source_pure_function`/
`test_office_search_router_field_role_always_gets_403`), keine neue Prüfung dafür nötig. Volle
Suite grün (1466/1466).

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

## Betriebsmittelverwaltung (seit 1.4.0, Modul "betriebsmittel")

Erstes neues Modul seit der Monteursansicht (die aber bewusst KEIN Modul ist, siehe dort) --
Befund zuvor separat berichtet (kein Code), dann fünf vom Nutzer bestätigte Bau-Entscheidungen
umgesetzt. Dreistufig: diese Version liefert ausschließlich **Stufe 1** -- Datenmodell mit
Ressourcenbezug, Prüffristen, Kosten, Stammdatenpflege, Modulschalter. QR-Code +
rollenabhängige Ansicht (Stufe 2) und Betriebsmittel im Bericht (Stufe 3) sind bewusst noch
nicht gebaut, folgen erst nach Rückmeldung zu dieser Etappe.

**Der Modulschalter zuerst, wie ausdrücklich verlangt**: `OPTIONAL_MODULES["betriebsmittel"] =
"Betriebsmittelverwaltung"` (`app/modules.py`) war der allererste Codeschritt dieser Version --
erst danach entstand ein einziger Endpunkt. Jeder Endpunkt in
`app/routers/operational_assets.py` prüft `is_module_enabled()` (403, exaktes Muster aus
`app/routers/maintenance_contracts.py`, eigener `_require_module_enabled(db)`-Helfer,
`MODULE_KEY = "betriebsmittel"`).

### Eigene Inventarschicht statt Erweiterung von `OperationalResource` -- die zentrale Entscheidung

`OperationalAsset` (`app/models.py`) ist eine eigene, neue Tabelle mit einem OPTIONALEN Bezug
zu genau einer `OperationalResource` (`resource_id`, `UniqueConstraint` -- höchstens ein
Betriebsmittel je Ressource, verhindert Doppelerfassung bereits auf Datenbankebene, nicht nur
in der Anwendungslogik). Genau die vom Nutzer vorgegebene Unterscheidung: "Ein Kran ist ein
Betriebsmittel MIT Ressourcenbezug -- inventarisiert und planbar. Eine Leiter ist ein
Betriebsmittel OHNE." Ein Kran bleibt über den komplett unveränderten `Team`/`TeamResource`/
`WorkPreparationTeamResource`/`PlanningSlot`-Weg in der Plantafel disponierbar, eine Leiter hat
mit diesem Weg nie etwas zu tun.

**Live-Auflösung statt Kopie, der eigentliche Schutz gegen Doppelerfassung/Namensdivergenz**:
ist ein Asset verknüpft (`resource_id` gesetzt), bleiben seine eigenen Identitätsfelder
(`name`/`asset_type`/`manufacturer`/`model`/`identifier`) auf der Datenbank IMMER `NULL` --
`app/operational_assets.py::asset_to_dict()` löst sie bei JEDEM Lesezugriff live aus der
verknüpften `OperationalResource` auf, niemals aus einer gespeicherten Kopie. Benennt jemand
die Ressource um, zeigt das Betriebsmittel sofort den neuen Namen, ohne selbst angefasst zu
werden -- ein klassisches "zwei Kopien laufen auseinander" kann dadurch strukturell nicht
entstehen. Ist kein Ressourcenbezug gewählt, sind dieselben Felder die einzige Quelle, `name`
wird dann zur Pflicht (Pydantic-`model_validator` in `OperationalAssetCreate`, bewusst NICHT
als DB-`NOT NULL`-Constraint, da die Spalte im verknüpften Fall zwingend `NULL` bleiben muss).
Die Business-Logik (`create_asset()`/`update_asset()`) setzt beim Verknüpfen zusätzlich die
eigenen Felder aktiv auf `NULL` zurück, falls vorher eigenständig befüllt.

**Ausdrückliche, dauerhafte Warnung -- bewusst im Klassendocstring von `OperationalAsset`
UND hier festgehalten, damit sie niemand übersieht**: `OperationalResource` und
`OperationalAsset` dürfen NIE zu einer einzigen Tabelle zusammengeführt werden. Die
Plantafel-Disposition referenziert ausschließlich `operational_resources.id` und kennt
`OperationalAsset` an keiner Stelle -- eine Zusammenführung würde diese Fremdschlüssel brechen
oder eine riskante ID-Migration erfordern. Das ist die bewusste Form von "Ressourcen
erweitern", die der Nutzer angefragt hat: eine zweite, optional angehängte Schicht, kein Umbau
der bestehenden.

### Fälligkeitslogik: Muster übernommen, Code bewusst NICHT wiederverwendet

Geprüft, ob `MaintenanceContractItem`s `_is_item_due()`/`_is_item_overdue()`
(`app/maintenance_contracts.py`) sich direkt wiederverwenden lassen -- Ergebnis: nein.
`_is_item_overdue()` ist an die saisonalen `MaintenanceWindow`-Fenster der Wartungsverträge
gekoppelt (`_window_close_date()`, Start-/Endmonat statt Kalendertage) -- das passt fachlich
nicht auf eine turnusmäßige Geräteprüfung wie "TÜV alle 12 Monate", die kein saisonales Fenster
kennt, nur ein festes Intervall. Beide Funktionen sind außerdem privat und eng an
`MaintenanceContract`/`MaintenanceContractItem` gekoppelt.

Übernommen ist deshalb nur das PATTERN, nicht der Code -- exakt die vom Nutzer verlangte
"gemeinsame Funktion, wenn sie sich anbietet, sonst dasselbe Muster mit dokumentierter
Trennung, wie bei den Pipeline-Spalten"-Vorgabe. Neue, eigenständige Funktionen
`is_inspection_due()`/`is_inspection_overdue()` (`app/operational_assets.py`): `is_due` prüft
eine konfigurierbare Vorlaufzeit VOR der eigentlichen Fälligkeit (`next_due_date <= heute +
reminder_lead_days`), `is_overdue` prüft unabhängig davon, ob das Datum bereits verstrichen ist
(`next_due_date < heute`) -- dieselbe Zwei-Stufen-Idee wie beim Wartungsmodul, aber ohne dessen
Fenster-Semantik. Eigene, unabhängige Singleton-Einstellung `OperationalAssetSettings.
reminder_lead_days` (Default 30 Tage) -- kein gemeinsamer Datensatz mit `MaintenanceSettings`.

Ein Asset aggregiert über alle seine Prüffristen: `is_due`/`is_overdue` sind `true`, wenn
MINDESTENS EINE Prüffrist das jeweils erfüllt, `next_due_date` (fürs Sortieren/Anzeigen) ist die
früheste aller künftigen Fristen.

### Datenmodell

- **`OperationalAsset`**: `resource_id` (optional, unique), eigene Identitätsfelder (nur
  relevant ohne Ressourcenbezug), `asset_number`, `notes`, `acquisition_date`,
  `acquisition_cost`, `recurring_cost_per_month`, `cost_notes`, `active`.
- **`OperationalAssetInspection`**: `asset_id`, `inspection_type` (aus der neuen, self-seedenden
  Optionsgruppe `operational_asset_inspection_types` -- TÜV/HU, Leiterprüfung, UVV-Prüfung,
  Wartung, Sonstige Prüfung), `interval_months`, `last_inspection_date`, `next_due_date`,
  `inspector`, `document_filename`/`document_original_name`, `notes`. Cascade beim Löschen des
  Assets (`cascade="all, delete-orphan"`).
- **`OperationalAssetSettings`**: Singleton (`reminder_lead_days`).

`asset_type` selbst nutzt bewusst dieselbe, bereits bestehende Optionsgruppe `resource_types`
wie `OperationalResource` -- keine zweite, parallele Typliste nur für eigenständige
Betriebsmittel.

**Migration `5917bb099776`** legt alle drei Tabellen an UND backfillt in derselben Migration
für jede der zum Zeitpunkt des Schreibens real bestehenden 5 `OperationalResource`-Zeilen
(3× Fahrzeug, 1× Kran, 1× Anhänger) ein verknüpftes `OperationalAsset` (nur `resource_id`
gesetzt, eigene Felder `NULL`) -- ohne diesen Schritt wären alle 5 Bestandsressourcen aus der
Stammdaten-Übersicht verschwunden, sobald diese (bei aktivem Modul) auf die Asset-Ansicht
umgestellt wird. Die Backfill-Logik steckt als eigenständige, direkt testbare Funktion
(`_backfill_assets_for_existing_resources()`) in der Migrationsdatei selbst (Muster aus
1.2.19/1.3.12/1.3.22, siehe "Testen" unten) -- gegen die echte, migrierte Datenbank verifiziert:
alle 5 Zeilen korrekt verknüpft, 0 verwaiste Ressourcen.

**Dokument-Ablage für Prüffristen** (`app/operational_asset_documents.py`, Muster
`app/roof_area_sketches.py`): eigener `data/operational_asset_documents/`-Ordner (neue
Umgebungsvariable `DACHKONZEPTE_OPERATIONAL_ASSET_FILE_ROOT`, in `.env.example` ergänzt, zehnte
Variable dieser Art), PDF zusätzlich zu PNG/JPEG/WebP erlaubt (Prüfprotokolle/Plaketten-Fotos,
anders als bei der reinen Bild-Skizze der Dachfläche), 10 MB-Grenze.

### Kosten: monatsnormalisiert statt Intervall+Betrag -- Vorbereitung für eine künftige Gesamtkostenübersicht

`recurring_cost_per_month` (ein einzelner, bereits auf den Monat umgerechneter Betrag) statt
eines Intervall+Betrag-Paars -- bewusste Vorentscheidung, weil der Nutzer eine spätere
"Gesamtkostenübersicht" bereits angekündigt hat: eine solche Auswertung kann dadurch trivial
über alle Assets `SUM(recurring_cost_per_month)` bilden, ohne zuvor unterschiedliche Intervalle
(monatlich/jährlich/quartalsweise) umrechnen zu müssen. **Merkposten für diese künftige
Auswertung**: `acquisition_cost` (einmalig) und `recurring_cost_per_month` (laufend) sind die
beiden Felder, die sie lesen wird -- beide bereits vorhanden, nichts davon ist noch zu ergänzen,
nur die Auswertung selbst fehlt noch.

### "Fuhrpark & Maschinen" wird zur Weiche, nicht zu zwei Parallelpflegen

Dieselbe Weiche wie bei Mitarbeitern in 1.3.26 ("die Stammdatenseite führt auf die
Betriebsmittelverwaltung, statt eine ärmere Parallelpflege zu bleiben"), aber ohne dass die
alte Seite entfällt -- die 5 Bestandsressourcen dürfen nie verschwinden, auch nicht bei
deaktiviertem Modul:

- **EIN Stammdaten-Navigationsknopf** (`master_data.html`, Jinja-bedingte Beschriftung: "Betriebsmittel"
  bei aktivem Modul, sonst weiterhin "Fuhrpark & Maschinen") statt zwei getrennter Einträge.
- **Modul an**: die reiche Asset-Liste (`GET /api/operational-assets`) -- eigener,
  `.catch(()=>[])`-abgesicherter Fetch-Zweig in `load()`s `Promise.all(...)`, da dieser
  Endpunkt (anders als jeder andere, bisher unbedingt geladene Fetch dieser Datei) modulgated
  ist und 403 liefern könnte, sobald das Modul während einer Sitzung abgeschaltet wird. Ein
  "Fällige Prüffristen"-Panel steht oben, "+ Hinzufügen" führt auf `/master-data/assets/new`.
- **Modul aus**: unverändert die alte, rohe Ressourcenliste (`GET /api/resources`, weiterhin
  ungegatet, Kern-ERP -- diese Datei fragt sie ohnehin immer ab, da `teamForm()` sie unabhängig
  vom Betriebsmittel-Modul braucht), "+ Hinzufügen" führt weiterhin auf
  `/master-data/resources/new`.
- **Anlegen** läuft über `master_data_form.html`s neue `assetForm()` (Ressourcenbezug-
  Umschalter, bereits verknüpfte Ressourcen werden aus der Auswahl ausgeschlossen). **Bearbeiten
  bewusst NICHT über dasselbe Formular** -- Regel-10-Präzedenzfall "eigene, reichere
  Detailseite statt generischem Formular, wenn ein Bereich das rechtfertigt" (wie Property/
  Wartungsvertrag): `master_data_form.html` bounct bei `type==='assets'&&editing` sofort auf
  `GET /betriebsmittel/{id}` (`app/templates/operational_asset.html`, Muster
  `maintenance_contract.html`), Anlegen bounct nach dem Speichern ebenso dorthin. Die
  Detailseite verlinkt bei verknüpfter Ressource zusätzlich auf deren eigene Stammdatenseite
  (`/master-data/resources/{id}/edit`), damit reine Ressourcenfelder (Kennzeichen, Hersteller
  bei Fuhrpark) weiterhin erreichbar bleiben, ohne sie auf der Betriebsmittelseite zu
  duplizieren.

### Sichtbarkeit auf Übersicht und Dashboard

Dashboard-Widget "Fällige Betriebsmittelfristen" (`due_assets`, Muster `due_maintenance`,
`app/templates/dashboard.html`, blendet sich über `isModuleEnabled('betriebsmittel')` selbst
aus) UND das "Fällige Prüffristen"-Panel auf der Stammdaten-Betriebsmittelliste decken die
verlangte Sichtbarkeit "auf einer Übersicht und im Dashboard" ab, ohne eine dritte, eigene
Seite dafür zu bauen.

### Einstellungen

Einstellungen → System → "Betriebsmittel" (neuer Abschnitt, `settings.html`, Muster
"Wartungen"): einziges konfigurierbares Feld ist `reminder_lead_days`, mit demselben
Deaktiviert-Hinweis-Mechanismus wie beim Wartungsmodul (`operationalAssetModuleDisabledNotice`).

### Verifikation

Per echtem, CDP-gesteuertem Headless-Chrome gegen eine isolierte, temporäre SQLite-Instanz
verifiziert (Muster 1.3.73/1.3.74, Büro-Testkonto statt Admin, um die 1.3.34-Zwei-Faktor-Pflicht
nicht extra einzurichten): Stammdatenliste zeigt korrekt "Betriebsmittel"/die Nächste-Prüffrist-
Spalte, Anlegen bounct tatsächlich zu `/betriebsmittel/{id}`, eine Prüffrist mit einem Datum in
der Vergangenheit lässt sofort das "⚠ PRÜFUNG ÜBERFÄLLIG"-Badge UND das "Fällige Prüffristen"-
Panel auf der Übersicht erscheinen, der Einstellungen-Abschnitt lädt den Wert 30 korrekt, und --
das Modul direkt in der Datenbank deaktiviert -- der vollständige Rückfall auf die alte
Fuhrpark-Ansicht (Sidebar-Label, Seitentitel, Add-Link, die alten Ressourcenspalten) samt
funktionierendem `403` auf `GET /api/operational-assets`. Keine JavaScript-Konsolenfehler
außer dem plattformweit üblichen fehlenden `favicon.ico`. `pytest` vollständig grün (1410
Tests, 17 davon neu in `tests/test_v276_operational_assets.py`: Doppelerfassungs-Schutz,
Live-Auflösung bei Umbenennung der Ressource, Name-Pflicht-Validator, Fälligkeits-Aggregation
über mehrere Prüffristen, Migrations-Backfill isoliert gegen eine frische Verbindung, Rollen-
UND Modul-Gate über echte Router-Endpunkte).

### Stufe 2 (seit 1.4.1): QR-Code-Etikett, rollenabhängige Ansicht

Zweite Etappe, nach Bestätigung von Stufe 1 gebaut. Vier Punkte plus ein abschließender, vom
Nutzer verlangter Angriffstest.

**Punkt 1 -- zwei neue Felder, nur für Büro/Admin.** `article_number` (Artikelnummer, Freitext)
und `product_url` (Produktlink) auf `OperationalAsset` -- beide gehören laut Nutzervorgabe "zur
Beschaffung, nicht zur Bedienung" und erscheinen deshalb NIE in der reduzierten Monteursansicht
(siehe Punkt 3). **`product_url` bewusst strikt validiert**: ein Feld, das eine beliebige
Zeichenkette als Link ausgibt, ist sonst ein Einfallstor (Nutzerformulierung) --
`app/schemas.py::_require_http_url()` (gemeinsamer, modulweiter `field_validator`-Helfer, per
`urlparse` auf Schema `http`/`https` und ein vorhandenes `netloc` geprüft) lehnt alles andere
mit 422 ab, insbesondere `javascript:`-Links. Derselbe Helfer sichert zusätzlich das neue
`GeneralSettings.public_base_url` (siehe Punkt 2) ab -- eine öffentliche Basis-URL trägt
dasselbe Risiko wie ein Produktlink, wenn sie ungeprüft bliebe. Der Link öffnet im
Bearbeiten-Formular über eine Vorschau mit `target="_blank" rel="noopener"` (verhindert, dass
die geöffnete Seite über `window.opener` Zugriff auf die ERP-Seite bekommt).

**Implizite Zusatzanforderung, transparent aufgelöst statt stillschweigend geraten**: Punkt 3
der Anfrage nennt "Bedienungshinweise -- falls es die gibt" als Monteur-sichtbares Feld, ohne
dass Punkt 1 es unter den neuen Feldern ausdrücklich benennt. Als drittes neues Feld
`usage_notes` (Text, nullable) ergänzt -- eine bewusste, offen kommunizierte Interpretation,
keine verdeckte Annahme, konsistent mit der sonst in diesem Projekt geübten Praxis (siehe
z. B. die 1.3.60-Prämisse-Korrektur zur Tätigkeit im Nachtrag).

**Punkt 2 -- QR-Code, Bibliotheks- und Domain-Entscheidung.** Vor jeder Codeänderung geprüft
(wie ausdrücklich verlangt): `qrcode[pil]` ist bereits seit 1.3.34 Projektabhängigkeit (für die
TOTP-Ersteinrichtung, BSD-3-Clause) -- keine neue, zusätzlich lizenzpflichtige Bibliothek nötig.
Wiederverwendet über ein neues, eigenständiges Modul `app/qr_codes.py`
(`qr_code_png_bytes(data: str) -> bytes`), NICHT durch eine Erweiterung des
sicherheitskritischen `app/two_factor.py` -- getrennte Verantwortlichkeiten, kein Risiko für den
Zwei-Faktor-Code durch eine unverwandte neue Funktion. Der Code enthält die VOLLSTÄNDIGE
Ziel-URL inklusive Domain (`asset_qr_target_url()`, `app/operational_assets.py`), damit ein
Scan mit der Telefonkamera direkt die Seite öffnet -- eine reine relative Pfadangabe hätte auf
dem Telefon nichts Sinnvolles ergeben.

**Woher die Domain kommt, bewusst nicht hartkodiert**: geprüft, ob im Projekt bereits ein
Mechanismus für eine öffentliche Basis-URL existiert -- keiner gefunden (`request.base_url`
wird an keiner Stelle projektweit für einen absoluten Link nach außen verwendet). Neues,
optionales `GeneralSettings.public_base_url` (Einstellungen → Unternehmensstammdaten,
"Öffentliche Adresse") hat Vorrang; ist es leer, fällt `_resolve_public_base_url()`
(`app/routers/operational_assets.py`) auf `request.base_url` zurück. Begründung für den
konfigurierbaren Vorrang statt eines blinden Vertrauens in `request.base_url` allein: die
Produktionsumgebung läuft hinter einem Nginx-Reverse-Proxy (siehe "Produktivbetrieb" oben),
ohne dass diese Sitzung eine bestätigte `ProxyHeadersMiddleware`/Trusted-Proxy-Konfiguration
vorgefunden hat -- `request.base_url` allein könnte dadurch das falsche Schema (`http` statt
`https`) oder die falsche interne Adresse liefern, "alle Codes zeigen auf localhost" ist genau
das vom Nutzer benannte Risiko. Neuer, Büro/Admin-only-Endpunkt
`GET /api/operational-assets/{asset_id}/qr-code.png` (`_role_dep`, wie jeder andere
Verwaltungs-Endpunkt dieses Routers außer dem in Punkt 3 erweiterten Einzelabruf) liefert das
PNG direkt als `Response(media_type="image/png")`.

**Button "Etikett drucken"**: auf `/betriebsmittel/{id}` (`operational_asset.html`) ergänzt --
zeigt ein druckbares Etikett mit QR-Code über der Bezeichnung. Umgesetzt über eine
`@media print`-Regel, die `.app-layout` komplett ausblendet und ausschließlich das
Etikett-Element einblendet. **Selbst gefundener und vor jedem Testlauf korrigierter CSS-Fehler**:
der erste Entwurf platzierte das Etikett-`<div>` verschachtelt innerhalb von `.app-layout` --
`display:none` auf einem Vorfahren blendet Nachfahren unabhängig von deren eigenem
`display`-Wert aus, das Etikett wäre beim Drucken also mit ausgeblendet worden. Behoben, indem
das Etikett-Element zu einem direkten Geschwisterelement von `.app-layout` verschoben wurde
(unmittelbar vor dem `<script>`-Tag) -- per echtem `Page.printToPDF` (CDP) bestätigt, dass beim
Drucken ausschließlich QR-Code + Name erscheinen, keine Sidebar/Topbar.

**Punkt 3 -- die rollenabhängige Ansicht, das Kernstück dieser Stufe.** Der QR-Code führt JEDEN
(Büro UND Monteur) auf dieselbe URL `/betriebsmittel/{id}` -- Inhalt ist rollenabhängig, Zugang
bleibt offen: exakt dasselbe Muster wie bei `time_tracking_page()` ("die Weiche hängt an der
Rolle, nicht am Weg"). `app/routers/pages.py::operational_asset_page()` ist von `_role_dep`
(Büro/Admin) auf `_any_role_dep` erweitert und wählt serverseitig die Vorlage:
`operational_asset_field.html` (neu, Muster `_mobile_header.html`, zeigt ausschließlich
Bezeichnung/Art/Hersteller/Modell/Bedienungshinweise) für `field`, unverändert
`operational_asset.html` für Büro/Admin.

`GET /api/operational-assets/{asset_id}` ist ebenfalls von `_role_dep` auf `_any_role_dep`
erweitert, `response_model=OperationalAssetOut | OperationalAssetFieldOut`. Neues Schema
`OperationalAssetFieldOut` (id/name/asset_type/manufacturer/model/usage_notes -- genau sechs
Felder, NICHT Prüffristen/Kosten/Artikelnummer/Produktlink). Der Router konstruiert je Rolle
EXPLIZIT `OperationalAssetFieldOut.model_validate(...)` bzw.
`OperationalAssetOut.model_validate(...)` -- niemals ein bloßes Dict zurückgegeben, Muster
`OrderOut | OrderFieldAccessOut` (Rechtekonzept, `app/routers/orders.py::get_order()`), das
Pydantics sonst mehrdeutige Union-Serialisierung vermeidet.

**Serverseitig geprüft, nicht pfadbasiert -- genau die vom Nutzer verlangte Härte**: ein Monteur,
der die volle Büro-URL `/betriebsmittel/{id}` statt des mobilen Wegs aufruft, bekommt
garantiert dieselbe reduzierte Seite UND dieselbe reduzierte API-Antwort, unabhängig vom Pfad --
die Rollenprüfung sitzt an `_any_role_dep`/der Router-internen Verzweigung, nicht an einer
zweiten, für Monteure gedachten Route. Verifiziert per rekursivem Schlüssel-Scan (Fehlerklasse
`purchase_price` -- ein Feld, das in der Antwort steht, aber nicht in der Oberfläche gezeigt
wird, ist trotzdem sichtbar) sowohl auf reiner Schema-Ebene (`asset_field_dict()`) als auch am
echten, über `router_test_client()` abgerufenen Router-Response.

**Punkt 4 -- kein dedizierter Scanner, wie ausdrücklich verlangt nicht ungefragt gebaut.**
Geprüft, ob ein eigener In-App-QR-Scanner nötig ist: moderne Telefone öffnen einen per
Kamera-App gescannten QR-Code direkt als anklickbaren Link, ohne dass die Anwendung selbst
etwas dafür bereitstellen muss. Kein Scanner umgesetzt -- sollte sich in der Praxis ein Gerät
(z. B. ein älteres Tablet ohne funktionierende Kamera-App-Integration) finden, das das nicht
leistet, ist ein eigener In-App-Scanner ein separat zu bewertender, eigenständiger Aufwand
(zusätzliche Berechtigungsanfrage für die Kamera, eine JS-Bibliothek für das Decodieren), kein
kleiner Nachtrag.

**Angriffstest, wie vom Nutzer verlangt, mit echtem Browser statt nur `pytest`**: per
CDP-gesteuertem Headless-Chrome gegen eine isolierte, temporäre SQLite-Datenbank (niemals gegen
`dachkonzepte_erp.db`) mit zwei echten Rollenkonten geprüft. Büro sieht die volle Ansicht
inklusive der drei neuen Felder, eine funktionierende QR-Code-Vorschau und -- ein
`PUT`-Request mit `product_url: "javascript:alert(1)"` -- eine 422-Ablehnung. Monteur bekommt
über dieselbe URL `/betriebsmittel/1` exakt die sechs erlaubten JSON-Schlüssel (keine Kosten,
keine Artikelnummer, kein Produktlink, keine Prüffristen), keinen "Etikett drucken"-Button im
Markup, und 403 beim direkten Aufruf des QR-Endpunkts -- null "durchgelassen".

**Tests/Migration**: 14 neue Tests (`tests/test_v277_operational_assets_stufe2.py`) -- Punkte im
Einzelnen: URL-Validierung (gültige/ungültige Schemata), Persistenz der drei neuen Felder,
exakte Schlüsselmenge des reduzierten Schemas (Funktionsebene UND Router-Response mit
rekursivem Scan), 403 für Monteur bei deaktiviertem Modul, die reine
`asset_qr_target_url()`-Funktion, PNG-Gültigkeit über Pillow, 403 für Monteur auf dem
QR-Endpunkt, unterschiedlicher QR-Inhalt mit/ohne `public_base_url`-Override,
Seitenvorlagen-Auswahl je Rolle. Migration `ccb5c4c0915b` (vier neue, nullable Spalten -- Regel
1 greift nicht, da keine NOT-NULL-Spalte auf einer bestehenden Tabelle entsteht) erfolgreich
gegen die echte, lokale `dachkonzepte_erp.db` angewendet. Volle Suite: 1424 Tests grün.

### Vier Ergänzungen (seit 1.4.2)

Vierter Auftrag zur Betriebsmittelverwaltung, unabhängig von der weiterhin gesperrten Stufe 3
(Betriebsmittel im Bericht) -- vier vom Nutzer benannte Punkte, ausdrücklich reine Bürofunktion
("Alle drei reine Bürofunktion, kein Monteur betroffen" -- tatsächlich vier Punkte plus der
abschließende Angriffstest).

**Punkt 1 -- automatische Fälligkeitsberechnung der Prüffristen, mit der entscheidenden
Feinheit.** `app/operational_assets.py::_compute_next_due_date(interval_months,
last_inspection_date, acquisition_date)` -- neu, wird von `create_inspection()`/
`update_inspection()` aufgerufen, sobald `interval_months` gesetzt ist:

```python
base = last_inspection_date or acquisition_date
if base is None:
    return None
return add_months(base, interval_months) - timedelta(days=1)
```

`add_months()` wird unverändert aus `app/date_utils.py` wiederverwendet (bereits geteilt zwischen
`maintenance_contracts.py`/`service_reports.py`, siehe dort). **Erste Fälligkeit beim Anlegen mit
Anschaffungsdatum**: `Anschaffungsdatum + Intervall − 1 Tag`, nie das Anschaffungsdatum selbst --
bei Anschaffung ist noch nichts fällig, exakt wie vom Nutzer verlangt. **Die entscheidende
Feinheit, mit eigenem Test belegt**: die Basis ist nach einer erledigten Prüfung IMMER das
tatsächliche `last_inspection_date`, nie eine kumulative Fortschreibung ab dem ursprünglichen
Anschaffungsdatum -- verspätet sich eine Prüfung, verschiebt sich der gesamte Rhythmus mit,
driftet nicht auseinander. `test_late_inspection_advances_next_due_date_from_actual_date_not_
cumulatively_from_acquisition()` (`tests/test_v278_operational_assets_erweiterungen.py`) legt eine
Prüfung deutlich verspätet an (statt am geplanten 2024-12-31 erst am 2025-02-15) und belegt
explizit, dass die neue Fälligkeit vom TATSÄCHLICHEN Datum aus (2026-02-14) berechnet wird, nicht
von der (falschen) kumulativen Rechnung ab dem Anschaffungsdatum (2025-12-31). **Eine Prüffrist
ohne Intervall (einmalige Prüfung) bleibt vollständig manuell** -- geprüft, dass es diesen Fall
gibt (`OperationalAssetInspectionCreate.next_due_date` existierte bereits, wird bei
`interval_months is None` unverändert direkt vom Client übernommen) und ihn sauber behandelt:
kein Server-Eingriff, `next_due_date` bleibt exakt, was der Client sendet, auch beim Wechsel von
intervallbasiert zurück auf manuell.

**Punkt 2 -- Meldung und Aufgabe vier Wochen vorher, derselbe Auslöser wie bei den
Wartungsverträgen.** `check_due_asset_inspections_and_create_reminders()` (neu,
`app/operational_assets.py`) -- **On-Demand, kein Scheduler**: geprüft, wie die Wartungsverträge
ihre Erinnerungen erzeugen (`check_due_contracts_and_create_reminders()`,
`app/maintenance_contracts.py`) -- derselbe Mechanismus wiederverwendet, ausgelöst per
Fire-and-Forget-`fetch()` (`master_data.html`s `load()`, gated auf `bmModuleEnabled`) beim Öffnen
der Stammdaten-Betriebsmittelliste, über einen neuen, literalen Endpunkt `POST
/api/operational-assets/check-due` (deklariert vor `/{asset_id}`, Muster
`POST /api/maintenance-contracts/check-due`). **Idempotenz über denselben Stempel-Mechanismus wie
`MaintenanceContract`**: neue, nullable Spalte `OperationalAssetInspection.last_reminder_due_date`
-- pro Prüffrist und Fälligkeitstermin genau einmal, nicht bei jedem Durchlauf erneut. **Ohne
expliziten Reset**, anders als bei `MaintenanceContract` (das ihn an mehreren Stellen zurücksetzt):
`next_due_date` wird bei diesem Feature bei JEDER Prüfung frisch neu berechnet (Punkt 1), weicht
dadurch automatisch vom alten Stempel ab, sobald sich etwas ändert -- ein Reset wäre redundant.
`test_check_due_reminds_again_after_next_due_date_actually_changes()` belegt das explizit: nach
einer neuen Prüfung mit geänderter Fälligkeit erinnert der nächste Aufruf erneut, ohne dass irgend
etwas den Stempel manuell zurücksetzen musste.

Die Aufgabe geht **unassigned** ("allgemein ans Büro", `assigned_employee_id=None`) mit Verweis
auf das Betriebsmittel (`source_module="betriebsmittel"`, `source_url="/betriebsmittel/{id}"`) --
wortgetreu wie vom Nutzer verlangt, es gibt (anders als `MaintenanceContract.
responsible_employee_id`) kein Zuständigkeits-Feld je Betriebsmittel oder eine passende
Modul-Einstellung dafür. **Dabei ein bereits bestehendes, transparent gemeldetes Verhalten des
Task-Systems entdeckt, nicht neu eingeführt**: `GET /api/tasks` (`app/routers/tasks.py`) erzwingt
für jeden NICHT-Admin-Aufrufer `employee_id == request.state.erp_user.employee_id` -- eine
unassigned Aufgabe ist damit für ein Büro-Konto ohne Admin-Rolle in der heutigen Aufgabenliste
unsichtbar, nur ein Administrator sieht sie. Bewusst NICHT durch ein ungefragtes, neues
`default_responsible_employee_id`-Einstellungsfeld umgangen -- die Anfrage sagte ausdrücklich
"allgemein ans Büro", eine stillschweigende Zuweisung an eine erratene Person hätte diese Vorgabe
unterlaufen. **Kein zweites Dashboard-Widget**: die Prüffristen erscheinen weiterhin nur im
bestehenden, seit Stufe 1 vorhandenen "Fällige Prüffristen"-Panel, die Aufgabe im Aufgabenbereich.

**Punkt 3 -- Betriebsmittel in der Büro-Suche.** 18. Eintrag in `OFFICE_SEARCH_SOURCES`
(`app/search.py`) -- `SearchSource("operational_assets", "Betriebsmittel", OFFICE_ROLES,
_search_operational_assets, _operational_asset_row, module_key="betriebsmittel")`. Mindestrolle
Büro (`OFFICE_ROLES = {ROLE_ADMIN, ROLE_OFFICE}`, dieselbe Konstante wie jede andere Quelle) -- ein
Monteur findet Betriebsmittel in der Suche NICHT, die Registry erbt die Rollenprüfung automatisch
über den bereits bestehenden `search_office()`-Dispatcher UND den primär sichernden
`GET /api/search`-Router (`require_role(ROLE_ADMIN, ROLE_OFFICE)`, ROLE_FIELD ausdrücklich nicht
dabei). Nur wenn das Modul "betriebsmittel" aktiv ist (`module_key="betriebsmittel"`, dritte,
bereits bestehende Achse des Dispatchers). Durchsucht Bezeichnung/Art/Hersteller/Modell/
Kennzeichen/Artikelnummer, führt auf `/betriebsmittel/{id}`.

**Live-Auflösung beachtet, sonst wären ressourcenverknüpfte Assets unauffindbar gewesen**: ein
Asset MIT `resource_id` trägt seine eigenen Identitätsfelder (`name`/`asset_type`/`manufacturer`/
`model`/`identifier`) als `NULL` (siehe Stufe 1, "Live-Auflösung statt Kopie") -- ein Suchfilter,
der nur `OperationalAsset` selbst prüft, hätte jeden Kran/Fahrzeug/Anhänger nie gefunden.
`_search_operational_assets()` joint deshalb zusätzlich per `outerjoin` auf `OperationalResource`
und filtert auf BEIDE Tabellen; `_operational_asset_row()` nutzt für den angezeigten Namen denselben
`resolve_asset_identity()`-Helfer wie `asset_to_dict()`/`asset_field_dict()` -- dafür musste die
Funktion umbenannt werden (`_resolve_identity()` → `resolve_asset_identity()`, ohne führenden
Unterstrich, da sie jetzt modulübergreifend genutzt wird), damit Suche, Büro-Ansicht und
Monteur-Ansicht (Stufe 2) für dasselbe Asset garantiert nie unterschiedliche Namen zeigen können.
Der Registry-Vollständigkeitstest (`EXPECTED_OFFICE_SEARCH_KEYS`,
`tests/test_v270_office_search.py`) deckt den neuen Eintrag mit ab -- inkl. eines neuen Tests, der
belegt, dass die Quelle beim Deaktivieren des Moduls "betriebsmittel" verschwindet. **Nebeneffekt
korrigiert**: `search_results.html`s clientseitig hartcodierte `TYPE_LABELS`-Liste (17 Einträge,
seit Etappe 2 der Büro-Suche) musste um den 18. Eintrag ergänzt werden, sonst hätte der
bestehende Abgleichstest (`test_search_results_page_type_filter_keys_match_the_registry`) die
Divergenz sofort angezeigt -- genau der Zweck dieses Tests.

**Punkt 4 -- Dokumentenablage am Betriebsmittel, für Anschaffungsrechnung, Leasingvertrag u. Ä.**
Vor dem Bauen geprüft, wie ausdrücklich verlangt, ob die Kategorie-Stammdaten aus 1.3.62
(`DocumentCategory`) genutzt werden können oder eine schlanke eigene Ablage genügt -- Ergebnis:
**schlanke eigene Ablage**, `DocumentCategory`s gesamter Zweck (`is_sensitive`/`is_field_visible`,
zwei unabhängige Schlösser gegen "sensible Kategorie für Monteure sichtbar") ist hier
gegenstandslos, da Betriebsmittel-Dokumente AUSNAHMSLOS Büro/Admin-only sind -- es gibt keine
Feld-sichtbare Stufe, die ein Schloss überhaupt bräuchte. Stattdessen dasselbe leichtgewichtige
Muster wie `OperationalAssetInspection.inspection_type`: eine neue, self-seedende Optionsgruppe
`operational_asset_document_types` (`app/option_settings.py`, drei Werte: Anschaffungsrechnung,
Leasingvertrag, Sonstiges).

Neue Tabelle `OperationalAssetDocument` (`app/models.py`) -- bewusst NICHT das bestehende
1:1-Muster je Prüffrist (`OperationalAssetInspection.document_filename`, ersetzt immer die
vorherige Datei) wiederverwendet, da ein Betriebsmittel beliebig viele UNABHÄNGIGE Dokumente
tragen kann (Anschaffungsrechnung UND Leasingvertrag UND ...). Neue Relationship
`OperationalAsset.documents` (`cascade="all, delete-orphan"`). Speicherort: derselbe Ordner/dieselbe
Umgebungsvariable wie die bestehende Prüffristen-Ablage (`app/operational_asset_documents.py`,
`DACHKONZEPTE_OPERATIONAL_ASSET_FILE_ROOT`, über `ERP_DATA_DIR` wie jeder Upload dieses Projekts)
-- neue `save_document()`-Funktion für das unabhängige, mehrere-Dateien-Muster, neben der
bestehenden `replace_document()` für die 1:1-Ablage. **Löschen räumt die Datei auf**: neues
`@event.listens_for(OperationalAssetDocument, "before_delete")` (Muster
`app/roof_areas.py::_delete_roof_area_sketch_file()`) -- feuert für JEDEN ORM-Löschweg, auch
kaskadiert beim Löschen des ganzen Betriebsmittels, kein separater Aufräum-Aufruf in
`delete_asset_document()`/`delete_asset()` nötig.

Drei neue Endpunkte (`app/routers/operational_assets.py`), **ausnahmslos** `_role_dep` (Büro/Admin,
NIE `_any_role_dep`, anders als der Einzelabruf aus Stufe 2): `POST
/api/operational-assets/{asset_id}/documents` (multipart, `document_type`+`notes` als Form-Felder,
`file` als Upload -- Existenzprüfung des Assets VOR dem Speichern der Datei, damit eine Datei für
ein nicht existierendes Betriebsmittel nie erst auf die Platte geschrieben wird), `GET
/api/operational-asset-documents/{document_id}/file`, `DELETE
/api/operational-asset-documents/{document_id}`.

**Abschließender Angriffstest, wie explizit für nach dieser Runde verlangt**: ein Monteur kommt
über keinen Weg an eine Betriebsmittel-Rechnung, auch nicht über eine geratene Datei-ID --
`test_field_can_never_reach_an_operational_asset_document_via_any_path()` prüft alle drei
Endpunkte sowohl mit einer echten, existierenden `document_id` als auch mit geratenen,
fortlaufenden IDs (1, 2, 9999): durchgängig 403, `require_role()` schließt die Rolle strukturell
aus, unabhängig davon, ob die ID existiert -- kein 404-vs-403-Unterschied, der verraten könnte, ob
ein Dokument existiert. Und die Büro-Suche liefert einem Monteur kein Betriebsmittel --
`test_office_search_endpoint_never_returns_an_operational_asset_to_field_role()` ruft den echten
`GET /api/search`-Router mit `role="field"` auf und erwartet 403, bevor `search_office()` auch nur
eine Zeile liest. Beide Tests in `tests/test_v278_operational_assets_erweiterungen.py`, 0
"durchgelassen".

**Verifiziert**: 16 neue Tests (`tests/test_v278_operational_assets_erweiterungen.py`) --
Fälligkeitsberechnung (Erst-Fälligkeit, verspätete Prüfung, manuelle Prüffrist, Wechsel
manuell→intervallbasiert, `_compute_next_due_date()` isoliert), Erinnerungs-Idempotenz (inkl. des
Falls "erinnert erneut nach echter Änderung" und "Modul deaktiviert"), Suche (ressourcenverknüpft
UND eigenständig, Rollenausschluss auf Funktionsebene), Dokumentenablage (voller Upload/Ansehen/
Löschen-Zyklus über den Router, Datei-Aufräumen von der Platte), die beiden Angriffstests. Dabei
zwei bereits bestehende Tests korrigiert (nicht Regressionen, sondern durch dieses Feature
tatsächlich veraltete Annahmen): `tests/test_v276_operational_assets.py::
test_office_role_full_crud_flow_via_router` sendete bisher `interval_months` UND `next_due_date`
gemeinsam und erwartete, dass der manuelle Wert übernommen wird -- genau das Verhalten, das Punkt 1
bewusst ändert; umgestellt auf `interval_months=None` (die weiterhin manuelle Variante), da der
Test generisch den CRUD-Fluss prüft, nicht die neue Berechnung selbst. `tests/
test_v271_office_search_ui.py`s hartcodierter Registrierungs-Zähler (`== 17`) und ein
Docstring-Verweis wurden auf 18 aktualisiert. Migration `ed896599a211` (neue Tabelle
`operational_asset_documents`, neue, nullable Spalte
`operational_asset_inspections.last_reminder_due_date` -- Regel 1 greift bei keiner der beiden,
da weder eine NOT-NULL-Spalte auf einer bestehenden Tabelle noch Bestandsdaten für die neue
Tabelle existieren) erfolgreich gegen die echte, lokale `dachkonzepte_erp.db` angewendet. Volle
Suite: 1441 Tests grün.

### Stufe 3 (seit 1.4.5): Eingesetzte Betriebsmittel im Einsatzbericht

Reine Dokumentation -- kein Preis, keine Menge, keine Betriebsstunden in dieser Version. Erst
Befund (Aufbau des Einsatzberichts, welches Vorbild passt, wo im PDF), dann drei vom Betreiber
entschiedene Punkte, dann in einer Runde gebaut.

**Vorbild war `ServiceReportMaterial`, nicht `ServiceReportPhoto`**: Material ist strukturell
ein reiner Datenbezug (FK + Zusatzfelder), ein Betriebsmitteleinsatz ist keine Datei. Die
Bedienung ist bewusst dieselbe wie bei Material -- ein vierter, gleichrangiger Panel-Umschalter
"Betriebsmittel" auf der Berichtskarte (neben Prüfpunkte/Mängel/Material), Tabelle + Erfassungszeile,
solange der Bericht Entwurf ist. **Ein Unterschied zu Material**: statt einer debounced
Katalogsuche ein einfaches `<select>` -- die freigegebene Liste bleibt in der Praxis kurz (Kran,
Hubsteiger, …), eine Suche wäre hier unnötiger Aufwand.

**Das Flag "im Bericht auswählbar"** (`OperationalAsset.selectable_in_reports`, Standard AUS,
`server_default='0'`) -- dasselbe restriktive Vorgabemuster wie `DocumentCategory.is_field_visible`
(1.3.62): das Büro gibt bewusst frei, was in einen Bericht darf, sonst wächst die Liste mit jedem
Kleingerät zu. Nur über die Betriebsmittel-Bearbeitungsseite änderbar (neues Feld neben "Status").
**Die 5 Bestandsressourcen** wurden bei der Migration (`b2226e22b9f0`) auf "nicht auswählbar"
gesetzt -- keine Vermutung, welche gemeint sein könnten, das Büro gibt sie gezielt frei.

**Die Freigabeprüfung gilt für JEDEN Aufrufer gleich, auch Büro/Admin** -- bewusst keine
Rollenausnahme: wer ein nicht freigegebenes Betriebsmittel einsetzen will, gibt es zuerst in der
Betriebsmittelverwaltung frei (ein Klick), statt dass die Business-Logik zwei unterschiedliche
Regeln für Büro und Monteur führen müsste. Das ist zugleich die serverseitige Absicherung gegen
eine geratene `asset_id` über den Endpunkt (`add_asset_usage()` in `app/service_reports.py`),
unabhängig davon, was die Auswahlliste selbst anzeigt.

**`ServiceReportAsset` -- die Tabelle, so geschnitten, dass die Kostenerweiterung später
sauber andockt** (siehe Klassendocstring in `app/models.py` für die volle Begründung, hier die
Kurzfassung): `service_report_id` + `asset_id` (Pflicht -- ein Betriebsmittel wird immer aus dem
Katalog gewählt, nie frei eingetippt, anders als `ServiceReportMaterial.material_id`) +
`asset_name_snapshot` (Pflicht, physisch eingefroren bei der Erfassung) + `notes` (das einzige
Zusatzfeld dieser Stufe, bleibt intern) + `sort_order`/`created_by_employee_id`/`client_uuid`
(letzteres dasselbe "vorbereiten, nicht vorbauen"-Muster wie bei Fotos/Material). **Beides, wie
verlangt**: `asset_id` bleibt als echter Verweis für eine spätere Kostenauswertung erhalten, UND
`asset_name_snapshot` zeigt unabhängig davon, was zum Zeitpunkt der Erfassung eingesetzt wurde --
dasselbe Muster wie die Bauteil-/Dachflächennamen seit 1.3.12. Bewusst KEIN `roof_area_id` (anders
als Material) -- ein Kran/Hubsteiger gehört üblicherweise zum ganzen Einsatz, nicht einer
einzelnen Dachfläche. **Diese Tabelle ist die vorgesehene Stelle für die spätere Kosten-/
Abrechnungserweiterung** (Betriebsstunden, Mietdauer, abrechenbare Menge, die in eine Rechnung
fließen) -- ein Datensatz je Einsatz, kein Name in einer Liste. Kommt diese Erweiterung, sind es
nullable `ALTER TABLE ADD COLUMN`-Ergänzungen auf genau dieser Zeile, keine Strukturänderung --
der nächste Durchgang soll das hier vorfinden, nicht neu herleiten müssen.

**`delete_asset()` blockiert jetzt, solange ein Bericht (Entwurf ODER unterschrieben) das Asset
referenziert** -- bewusst strenger als `delete_roof_component()` (das nur bei bereits
unterschriebenen Berichten blockiert): `ServiceReportAsset.asset_id` ist NICHT NULL, ein Löschen
würde die Fremdschlüsselbeziehung sonst in JEDEM Fall verletzen, nicht nur bei einem bereits
abgeschlossenen Nachweisdokument. Archivieren (`active=False`) bleibt dafür uneingeschränkt
möglich -- der übliche Weg, ein nicht mehr genutztes Betriebsmittel auszublenden, ohne seine
Verwendung in Berichten zu gefährden.

**QR-Scan im Bericht -- geprüft, nicht gebaut, wie verlangt.** Der bestehende QR-Code kodiert die
volle Ziel-URL `/betriebsmittel/{id}` für die Kamera-App des Telefons -- ein Scan öffnet eine neue
Seite und verlässt damit den gerade bearbeiteten Bericht vollständig, kein natürlicher Andock-Punkt
für "während der Erfassung kurz scannen". Ein echter In-Bericht-Scanner bräuchte Kamera-Zugriff im
Browser (`getUserMedia`) plus eine Dekodier-Bibliothek -- nichts davon existiert im Projekt, ein
eigener, spürbarer Aufwand mit Cross-Browser-Risiko (keine zuverlässige native `BarcodeDetector`-
Unterstützung auf allen Zielgeräten). Zurückgestellt, bis sich im Betrieb zeigt, dass die
Auswahlliste zu umständlich ist -- für jetzt: Auswahl aus der freigegebenen Liste.

**Einfrieren nach der Unterschrift** wie Material/Fotos/Prüfpunkte -- `add_asset_usage()`/
`update_asset_usage()`/`delete_asset_usage()` nutzen dieselbe `_require_draft_report()`-Sperre,
kein neuer Mechanismus. `sign_report()` bekommt dafür KEINE neue Pflichtprüfung (Muster Material:
ein Einsatz ohne Betriebsmittel ist normal).

**Im Kundenbericht**: neuer Abschnitt "Eingesetzte Betriebsmittel" (`app/service_report_pdf.py`),
direkt nach "Verbrauchtes Material", nur wenn tatsächlich welche erfasst wurden (Muster Material/
Mängel). Bewusst KEINE Tabelle (keine Menge/Einheit wie bei Material) und KEINE Gruppierung nach
Dachfläche (ServiceReportAsset kennt kein `roof_area_id`) -- eine schlichte, komma-getrennte
Namensliste aus den eingefrorenen `asset_name_snapshot`-Werten, über den gemeinsamen Rahmen, mit
`KeepTogether` wie die anderen Abschnitte. `notes` erscheint NIE im PDF -- bleibt der interne
Vermerk, wie `OperationalAsset.cost_notes` auch nie in einem Dokument auftaucht. Erscheint
unbedingt auch im reduzierten Feld-PDF (`build_service_report_pdf_for_field()`,
`include_time_entries=False`) -- anders als Zeitbuchungen sind eingesetzte Betriebsmittel keine
fremden Personendaten.

**Neuer, für jede Rolle erreichbarer Endpunkt** `GET /api/operational-assets/selectable-for-report`
(bewusst literal VOR `/{asset_id}` deklariert, Muster `/due`/`/check-due`) -- liefert IMMER
`OperationalAssetFieldOut` (die fünf bereits aus Stufe 2 bekannten feldsicheren Felder), gefiltert
auf `selectable_in_reports UND active`, unabhängig von der Rolle: ein Bericht braucht nie Kosten-/
Fristendaten, egal wer ihn füllt. Rekursiver Schlüssel-Scan bestätigt: kein Kosten-/Fristen-/
Artikelnummernfeld in der Antwort, für `field`/`office`/`admin` gleichermaßen.

**Modul-Doppelgate**: `POST/GET/PUT/DELETE .../service-reports/{id}/assets*` prüfen zusätzlich zu
`is_module_enabled(db, "wartungen")` auch `is_module_enabled(db, "betriebsmittel")` -- ein
Einsatzbericht kann Betriebsmittel nur dokumentieren, wenn BEIDE Module aktiv sind, sonst bliebe
die Betriebsmittelverwaltung über diesen Umweg nutzbar, obwohl sie deaktiviert ist.

**Verifiziert**: 26 neue Tests (`tests/test_v280_operational_assets_stufe3.py`) -- Namens-Snapshot
(bleibt bei Umbenennung/Archivierung des Assets unverändert), Freigabe-Flag (Standard aus, gilt für
jeden Aufrufer gleich, unbekannte/nicht freigegebene `asset_id` abgelehnt), `list_selectable_assets()`
(gefiltert auf freigegeben+aktiv, live aufgelöster Name bei ressourcenverknüpften Assets, sortiert),
`delete_asset()`-Blockade (Entwurf UND unterschrieben, Archivieren bleibt frei), Einfrieren nach
Unterschrift, PDF (Abschnitt erscheint/verschwindet korrekt, Name bleibt nach späterer Umbenennung
eingefroren, `notes` nie im PDF, auch im Feld-PDF vorhanden), Router-CRUD, der verlangte rekursive
Schlüssel-Scan über alle drei Rollen, und die beiden Angriffstests (nicht freigegebene/geratene
`asset_id` liefert 400 statt stillem Erfolg; ein Monteur kann keinem fremden Bericht ein
Betriebsmittel hinzufügen). Migration `b2226e22b9f0` (neue Tabelle `service_report_assets`, neue
NOT-NULL-Spalte `operational_assets.selectable_in_reports` mit `server_default='0'`, Regel 1
befolgt) erfolgreich gegen die echte, lokale `dachkonzepte_erp.db` angewendet, Bestandsdaten
geprüft (alle 5 Assets korrekt auf `False`). Volle Suite: 1492 Tests grün.

### Dokument-Upload schon beim Erstellen des Betriebsmittels (seit 1.5.6)

Nachbesserung, unabhängig von den Stufen 1-3 oben. Bis dahin ließ sich ein Dokument
(Anschaffungsrechnung, Leasingvertrag) erst nach dem Speichern -- im Bearbeiten-Modus -- an ein
Betriebsmittel hängen; das Anlegen-Formular (`master_data_form.html::assetForm()`) hatte keinen
Upload. **Ursache, wie vermutet und bestätigt**: `POST /api/operational-assets/{asset_id}/documents`
(1.4.2, siehe "Vier Ergänzungen" oben) verlangt zwingend eine bereits existierende `asset_id` als
Pfadparameter (`if db.get(OperationalAsset, asset_id) is None: raise HTTPException(404, ...)`) --
beim Anlegen gibt es diesen Datensatz naturgemäß noch nicht. Der Endpunkt selbst war korrekt und
brauchte keine Änderung.

**Gewählter Weg (Option a: erst speichern, dann anhängen) statt Option b (Dateien
zwischenhalten, nach dem Anlegen automatisch anhängen)**: `File`-Objekte lassen sich in
Vanilla-JS nicht über einen echten Seitenwechsel hinweg persistieren, und das Anlegen-Formular
und die Betriebsmittel-Detailseite sind zwei getrennte Templates/URLs (`master_data_form.html`
vs. `operational_asset.html`) -- Option b hätte entweder einen echten Navigations-Umweg
gebraucht (der das Problem gar nicht löst) oder eine Persistenz über `sessionStorage`/IndexedDB
nur für diesen einen Formularschritt, unverhältnismäßig für ein einziges Feld. Option a bleibt
für den Nutzer EIN Vorgang (ein Klick auf "Speichern"), intern zwei Schritte: das Betriebsmittel
zuerst per `POST /api/operational-assets` anlegen, danach die vorgemerkten Dateien sequenziell
an die zurückgegebene `id` hängen -- beides innerhalb derselben `save()`-Ausführung, kein
Seitenwechsel dazwischen.

**Mechanismus**: eine Client-seitige Warteschlange `pendingAssetDocuments` (Array aus
`{file, document_type, notes}`) -- "+ Vormerken" fügt eine Datei samt Art/Notiz hinzu, ohne
etwas zu senden; erst `save()` lädt jede vorgemerkte Datei nacheinander per
`fetch(...,{method:'POST',body:FormData})` an `/api/operational-assets/{saved.id}/documents`
hoch, NACHDEM der `POST` für das Betriebsmittel selbst erfolgreich war.

**Fehlerfall, wie ausdrücklich verlangt geprüft**: die Datei-Upload-Schleife steht im Code
zwingend NACH `const saved=await api(url,{method,...})` (der eigentlichen Anlage). Schlägt dieser
Aufruf fehl (Pflichtfeld fehlt, 422-Validierung), wirft er eine Ausnahme -- die Ausführung springt
direkt in den umschließenden `catch(e){el('msg').textContent='Fehler: '+e.message}`-Block, die
Upload-Schleife wird nie erreicht. Damit gilt zugleich: **kein verwaistes Betriebsmittel**
(es wurde ja gar nicht erst angelegt) und **keine verlorenen Dateien** (`pendingAssetDocuments`
und die Datei-Auswahl im Formular bleiben unverändert stehen, ein erneuter Speichern-Versuch nach
Korrektur des fehlenden Felds braucht keine erneute Dateiauswahl). Schlägt dagegen NUR ein
einzelner Dokument-Upload NACH erfolgreicher Anlage fehl (z. B. ein zu großes Dokument), bleibt
das Betriebsmittel bestehen (kein Rollback der Anlage selbst, die bereits abgeschlossen ist) --
`save()` sammelt fehlgeschlagene Uploads in einer Liste und zeigt sie nach der Navigation zur
neuen Detailseite per `alert()` an ("... bitte auf der Betriebsmittelseite erneut versuchen"),
statt sie stillschweigend zu verschlucken.

**Bewusst nur an dieser einen Stelle** -- die Anfrage stellte ausdrücklich klar, dass das Muster
laut Betreiber nicht verallgemeinert werden soll ("gilt nur beim Betriebsmittel, nicht
anderswo"), deshalb keine geteilte Hilfsfunktion/kein neuer, allgemeiner Mechanismus, nur die
eine Formular-Datei (`master_data_form.html`) geändert. `app/routers/operational_assets.py`
selbst wurde nicht angefasst.

**Verifikation**: `node --check` gegen den extrahierten `<script>`-Block (nach Neutralisierung der
beiden Jinja-Platzhalter `{{ data_type }}`/`{{ record_id|default('null') }}`, Projektkonvention
für Jinja-templatetes JS) -- keine Syntaxfehler. Kein Backend-Verhaltensänderung, deshalb keine
neuen `pytest`-Tests; die Absicherung dieser Version stützt sich ausschließlich auf sorgfältige
Kontrollfluss-Lektüre (`save()`s try/catch-Struktur) und `node --check`, **kein echter
Browser-Klicktest** in dieser Runde (bekannte, wiederholt dokumentierte Werkzeug-Einschränkung
dieser Sitzung war für diesen einen Punkt nicht aktiviert) -- sollte bei Gelegenheit im Browser
nachgeprüft werden (Anlegen mit zwei vorgemerkten Dokumenten, Anlegen mit absichtlich fehlendem
Pflichtfeld -- Dateien müssen erhalten bleiben).

## Betriebskosten-Übersicht (seit 1.5.0, Modul "betriebskosten")

Erstes neues Modul seit der Betriebsmittelverwaltung (`module_key "betriebskosten"`,
`OPTIONAL_MODULES`, buero_finanzen/admin-only -- siehe "Rechtekonzept" -> "Vier Rollen": die
Betriebskosten-Übersicht war dort bereits als künftiger, buero_finanzen-verengter Bereich
vorgemerkt, dieses Modul löst genau diesen Vormerkposten ein). Schicht 1 -- ausschließlich die
Kostenerfassung, wie beauftragt; der eigentliche Schritt zum Verrechnungssatz bleibt eine
spätere, eigene Schicht 3. Erst ein reiner Befund zu fünf Rückfragen berichtet (Herleitung des
Stundenverrechnungssatzes, bestehende Kostendatenquellen, Modellform, Aufgaben-Zielgruppe,
Summenansicht), dann vier vom Nutzer entschiedene Punkte gebaut.

### Zwei Kostenquellen nebeneinander, keine Migration

`RecurringCost` (`app/models.py`) ist eine neue, eigene Tabelle für den detaillierten
wiederkehrenden Vertrag (Miete, Leasing, Versicherung, Software-Abo u. Ä. -- Partner,
Kündigungsfrist, Dokument). **Bewusst NICHT** die bestehenden `OperationalAsset.
acquisition_cost`/`recurring_cost_per_month` (seit 1.4.0) migriert oder ersetzt -- Begründung des
Betreibers: die monatliche Kosten-Notiz am Betriebsmittel ist eine schnelle Notiz beim Anlegen,
der neue Kostenposten der ausführliche Vertrag. Beide Quellen bestehen unabhängig nebeneinander,
`app/recurring_costs.py::overview_summary()` führt sie ausschließlich in der SUMME zusammen.

**Doppelzählung verhindert, nicht nur erkannt** (die vom Nutzer selbst benannte Gefahr: "wenn
jemand für dieselbe Leasingrate sowohl `monthly_cost` am Transporter ALS AUCH einen Kostenposten
anlegt, zählt die Summe sie doppelt"): zeigt ein `RecurringCost` über sein optionales `asset_id`
auf ein Betriebsmittel, ERSETZT er dessen `recurring_cost_per_month` in `overview_summary()`,
statt sie zu addieren -- `annual_from_asset_quick_costs` schließt jedes Asset, dessen `id` unter
mindestens einem aktiven, verknüpften Kostenposten auftaucht, explizit aus. Bewusst **kein**
`UniqueConstraint` auf `RecurringCost.asset_id` -- ein Betriebsmittel kann mehrere unabhängige
Kostenposten tragen (z. B. Leasingrate UND Versicherung für denselben Transporter), die
Ersetzungsregel greift bereits, sobald IRGENDEIN aktiver Posten existiert, nicht erst bei genau
einem. Zwei nicht persistierte Transparenz-Hinweise (Muster `material_markup_hint`,
`app/invoices.py` seit 1.2.23) machen die Ersetzung sichtbar, statt sie stillschweigend
geschehen zu lassen: `RecurringCostOut.asset_quick_cost_hint` (nur bei gesetztem `asset_id`) und
`OperationalAssetOut.has_linked_recurring_cost` (NICHT auf `OperationalAssetFieldOut` -- ein
Monteur bekommt diesen rein bürowirtschaftlichen Hinweis nie zu sehen). Letzteres berechnet
`app/operational_assets.py::asset_to_dict()` über einen neuen, optionalen `db`-Parameter (nur
wenn übergeben, sonst konservativ `False`) -- alle bestehenden Aufrufer (Stufe 1-3, die
Büro-Suche) wurden geprüft und angepasst, wo sinnvoll (Einzelabruf/Liste/Anlegen/Ändern), keiner
musste sich strukturell ändern.

### `annual_amount` -- der Andockpunkt für den späteren Verrechnungssatz-Kreislauf

`RecurringCost.annual_amount` ist ein **gespeichertes** Feld (nicht bei jeder Summierung aus
`amount`/`billing_interval` neu berechnet) -- `app/recurring_costs.py::normalize_to_annual()`
berechnet es bei jedem Anlegen/Ändern. **Das ist ausdrücklich der Wert, den Schicht 2 nur noch
aufsummiert und Schicht 3 in die Gemeinkosten einspeist**, wie vom Nutzer verlangt hier
festgehalten, mit Verweis auf die konkrete, im Befund gefundene Stelle:
`app/labor_rate.py::calculate_labor_rate()` berechnet `fixed_overhead` bereits heute als reine
Summe (aktuell: `LaborRateOverheadSettings.fixed_overhead_value`, Modus `"eur"`, ein einzelner,
händisch gepflegter Betrag) -- die Summe aller aktiven `RecurringCost.annual_amount`-Werte
(`overview_summary()["annual_total"]`, zusammen mit den nicht-doppelt-gezählten
Betriebsmittel-Notizen) ist exakt der Wert, den ein künftiger, automatischer Kreislauf dort
einsetzen wird, statt ihn weiterhin von Hand einzutragen. Diese Version baut den Kreislauf
selbst NICHT (Schicht 3, separat) -- nur das Feld, auf dem er andocken wird.

**Seit 1.5.5 präzisiert**: `amount` hieß damals noch so und trug keine Steuersemantik -- seit
1.5.5 heißt das Feld `net_amount`, `annual_amount` wird ausschließlich daraus berechnet, nie aus
einem Bruttobetrag. Siehe Abschnitt "Netto und Brutto bei den Betriebskosten" unten für die
vollständige Herleitung.

### Rhythmus als fester Code-Wert, "einmalig" bereits vorbereitet

`BILLING_INTERVALS` (`app/recurring_costs.py`) ist ein festes Code-Tupel wie `SEVERITIES`/
`ACTIONS`/`STATUSES` bei `Finding` -- **keine** Optionsgruppe, da der Rhythmus eine Rechenregel
trägt (`normalize_to_annual()`s Multiplikator), keine freie Konfiguration: `monatlich`
(×12), `vierteljaehrlich` (×4), `halbjaehrlich` (×2), `jaehrlich` (×1), `einmalig` (×0).

**Punkt 4 der Anfrage, geprüft statt geraten**: "einmalig" ist bereits ein gültiger, im Modell
unbeschränkter Wert -- `billing_interval` ist auf keiner Ebene per DB-`CHECK`-Constraint
begrenzt (kein einziges Vorkommen davon im ganzen Projekt), nur Pydantic
(`RecurringCostCreate.billing_interval`) validiert die erlaubte Menge, erweiterbar ohne
Migration. `normalize_to_annual()` liefert für `"einmalig"` bewusst `0` -- kein laufender
Beitrag zur wiederkehrenden Summe, der Posten selbst bleibt trotzdem in `list_costs()`/der
Oberfläche sichtbar, kein Sonderfall, der ihn ausblendet (siehe
`test_normalize_to_annual_einmalig_is_zero_but_model_accepts_the_value`). **Das Modell steht
einmaligen Kosten nicht im Weg** -- eine eigene Erfassungsoberfläche dafür (z. B. ohne
Kündigungsfrist-Felder, die für einen einmaligen Posten keinen Sinn ergeben) ist NICHT Teil
dieser Version, bleibt aber eine kleine, spätere Erweiterung, keine Baustelle.

### Kündigungsfrist: reine Ableitung, keine gespeicherte Spalte

`app/recurring_costs.py::cancellation_deadline(contract_end_date, notice_period_months)` = 
`add_months(contract_end_date, -notice_period_months)` (`app/date_utils.py`, negatives Vorzeichen
-- dieselbe, bereits bestehende Funktion, wiederverwendet statt einer eigenen Rückwärtsrechnung).
Bewusst NICHT gespeichert (anders als `OperationalAssetInspection.next_due_date`, das ein
"zuletzt tatsächliches Datum" bräuchte, um korrekt fortzuschreiben) -- hier gibt es kein solches
Zwischenereignis, die Frist ergibt sich vollständig und stabil aus zwei bereits gespeicherten
Feldern, ändert sich nur durch eine bewusste Vertragsänderung. `is_cancellation_due()`/
`is_cancellation_overdue()` -- dasselbe, bereits etablierte Zwei-Stufen-Muster wie bei den
Betriebsmittel-Prüffristen (`is_inspection_due()`/`is_inspection_overdue()`, 1.4.0), eigene,
unabhängige `RecurringCostSettings.reminder_lead_days` (Singleton wie `OperationalAssetSettings`,
Default 30 Tage) -- kein gemeinsamer Datensatz mit einem anderen Modul.

### Kündigungsfrist-Aufgabe: `Task.min_visible_role`, die allgemeine Erweiterung

Siehe Abschnitt "Aufgabe" -> "Ziel-Mindestrolle für empfängerlose Aufgaben" oben für die volle
Herleitung des neuen, allgemeinen `Task.min_visible_role`-Felds -- hier nur der konkrete
Anwendungsfall: `check_due_cancellations_and_create_reminders()` (On-Demand wie
`check_due_asset_inspections_and_create_reminders()`, 1.4.2 -- läuft nur beim Aufruf von
`/betriebskosten`, kein Hintergrundjob) erzeugt eine Aufgabe MIT
`min_visible_role=ROLE_OFFICE_FINANZEN`, NICHT unassigned "ans ganze Büro" wie bei den
Betriebsmittel-Prüffristen -- eine Kündigungsfrist geht nur Finanzen/Admin etwas an, nicht die
Auftragsbearbeitung (Nutzervorgabe, wörtlich). `last_reminder_due_date` ist derselbe
Idempotenz-Stempel wie bei `OperationalAssetInspection`, ohne expliziten Reset -- ändert sich die
berechnete Frist (Vertragsänderung), unterscheidet sie sich automatisch vom alten Stempel.

### Dokumentenablage und Optionsgruppen

`RecurringCostDocument` (Muster `OperationalAssetDocument`, 1.4.2) -- mehrere unabhängige
Dateien je Kostenposten, `document_type` aus der neuen, self-seedenden Optionsgruppe
`recurring_cost_document_types` (`app/option_settings.py`), Löschen räumt die Datei über ein
`before_delete`-Event (`app/recurring_costs.py`) auf, kaskadiert auch beim Löschen des ganzen
Kostenpostens. `app/recurring_cost_documents.py` (eigener Ordner, neue Umgebungsvariable
`DACHKONZEPTE_RECURRING_COST_FILE_ROOT`, `.env.example` ergänzt) trägt bewusst nur das
unabhängige "mehrere Dateien"-Muster (`save_document()`), kein 1:1-Ersetzungsfall wie bei
Betriebsmittel-Prüffristen -- den gibt es hier nicht. Zweite neue Optionsgruppe
`recurring_cost_categories` für die freie Kategorisierung (Miete/Leasing/Versicherung/Software/
Wartungsvertrag/Sonstiges).

### Oberfläche und Einstellungen

`GET /betriebskosten` (`app/routers/pages.py::recurring_costs_page()`, `app/templates/
recurring_costs.html`) -- Summenkarte (Monats-/Jahresbetrag, Kostenposten-Zähler, Zähler der
noch nicht ersetzten Betriebsmittel-Notizen, Kündigungsfristen hervorgehoben mit fällig getrennt
von überfällig ausgewiesen), Anlegen/Bearbeiten-Formular samt Dokumentenablage (erst nach dem
ersten Speichern sichtbar, Muster: ein Dokument braucht eine `recurring_cost_id`), Liste mit
Betriebsmittel-Bezug (Name live über die bereits geladene Assets-Liste aufgelöst) und dem
`asset_quick_cost_hint`-Tooltip. Bewusst `_finanzen_role_dep` (eigene, neue Konstante in
`app/routers/pages.py`, `require_min_role(ROLE_OFFICE_FINANZEN)`) statt des generischen
`_role_dep`/`_any_role_dep` dieser Datei -- die einzige Seite in `pages.py`, die diese engere
Schwelle direkt auf sich selbst trägt (Kalkulationsgrundlagen/Mitarbeiterformular hatten das
zuvor nur über spezielle Helfer).

Sidebar-Link unter Finanzen, aber in einem EIGENEN `{% if %}`-Block, STRENGER gegated als
"Finanzen"/"Mahnwesen" selbst (`is_module_enabled('betriebskosten') and can(current_user,
'admin', 'buero_finanzen')`, kein `buero_auftrag`) -- ein `buero_auftrag`-Konto sieht "Finanzen"/
"Mahnwesen" weiterhin, nur diesen einen neuen Eintrag nicht. Neue Einstellungen-Gruppe
"Betriebskosten" (Vorlaufzeit für Kündigungsfristen) innerhalb desselben, bereits bestehenden
`buero_finanzen`-gegateten Menüblocks wie Kalkulationsgrundlagen/Stundenverrechnungssatz --
`loadRecurringCostsSettingsSection()` wird deshalb (wie die dortigen Felder) nur innerhalb von
`if(canSeeCalculationSettings){...}` in `load()` aufgerufen, nie unbedingt, da die zugehörigen
DOM-Elemente für `buero_auftrag` serverseitig aus dem Markup entfernt sind.

### Angriffstest

`buero_auftrag` und `field` kommen über KEINEN Weg an die Betriebskosten -- geprüft mit einem
rekursiven Schlüssel-Scan und je einem Testkonto pro Rolle
(`tests/test_v283_recurring_costs.py`): die Liste (`GET /api/recurring-costs`), der Einzelabruf,
die Übersicht/Summe (`GET /api/recurring-costs/overview`), Anlegen/Ändern/Löschen, die
Dokumentenablage (Hochladen/Ansehen/Löschen -- auch über eine geratene, gar nicht existierende
Datei-ID, dieselbe 403 wie bei einer echten), die Einstellungen, UND die finanz-adressierte
Erinnerungs-Aufgabe (weder in der Liste noch im gemeinsamen Eingang sichtbar, auch mit bekannter
ID nicht übernehmbar -- 403 statt 400/200). Null durchgelassen. Migration `fc79aa5629d0`
(`recurring_costs`/`recurring_cost_documents`/`recurring_cost_settings` neu, `tasks.
min_visible_role` als neue, nullable Spalte auf der bestehenden Tabelle), 26 neue Tests, volle
Suite: 1558 Tests grün.

### Verrechnungssatz-Kreislauf Schicht 3 (seit 1.5.1)

Vorbereitet durch einen reinen Befund (Punkt 1 der Anfrage: wie `labor_rate.py` den Satz heute
bildet, Prozent-oder-Betrag, fix/variabel getrennt oder nicht, die Umrechnungsformel), danach
sechs Betreiberentscheidungen -- die wichtigste davon (der Begriffskonflikt bei "variabel")
ausdrücklich VOR jedem Bauen der Einordnung/Einspeisung zu klären. Diese Version liefert
ausschließlich die beiden Teile, die der Betreiber selbst als unabhängig vom Konflikt markiert
hat (Produktivstunden-Rechner, `overview_summary()`-Erweiterung); die Einspeisung selbst (Schreiben
in `LaborRateOverheadSettings`, Modus-Zwang, Vergleichsansicht) und die endgültigen Einordnungs-
Labels warten auf die Bestätigung des folgenden Vorschlags.

#### Punkt 1 -- Befund: wie `calculate_labor_rate()` den Satz heute bildet

Vier Kostenblöcke, alle im Rückgabe-Dict von `calculate_labor_rate()` (`app/labor_rate.py`)
wiederzufinden: `gross_wages` (Bruttolöhne der direkt zugeordneten Mitarbeiter),
`employer_costs` (`gross_wages * employer_cost_pct/100`), `total_overhead` (=
`fixed_overhead` + `variable_overhead`) und `target_profit_pct` (Aufschlag auf die
Selbstkosten). **Fix/variabel sind bereits heute getrennte Felder**, keine neue Unterscheidung
nötig: `LaborRateOverheadSettings.fixed_overhead_mode/fixed_overhead_value` und
`.variable_overhead_mode/variable_overhead_value`, jedes Feld unabhängig als `"eur"` (absoluter
Jahresbetrag) oder `"pct"` (Prozent der direkten Lohnkosten inkl. AG-Nebenkosten) pflegbar --
reale Werte in der Datenbank: `fixed_overhead_value=73500` (Modus `"eur"`),
`variable_overhead_value=150000` (Modus `"eur"`).

**Die zentrale Zusammensetzung, die den Begriffskonflikt auslöst**: `variable_overhead` wird
NICHT nur aus dem gepflegten `variable_overhead_value` gebildet, sondern als
`manual_variable_overhead + variable_employee_costs` -- `variable_employee_costs` ist die Summe
aus Jahresbrutto + AG-Nebenkosten aller Mitarbeiter mit der Kosten-Zuordnung
`allocation_type="variable_overhead"` (`EmployeeCostAllocationSettings`, siehe
`effective_cost_allocation()` in `app/employees.py`) -- in der Praxis die Verwaltungslöhne
(Büro, Geschäftsführung), automatisch zum manuell gepflegten Betrag addiert.

**Produktive Jahresstunden** (`annual_productive_hours`) = `paid_hours * productive_time_pct /
100`, wobei `paid_hours` bereits die AGGREGIERTE Summe über alle direkt zugeordneten Mitarbeiter
ist (Wochenstunden × `weeks_per_year`, summiert). **Keine detaillierte Herleitung existiert
heute** -- `productive_time_pct` ist ein einzelner, pauschal gepflegter Prozentsatz (realer
Wert in der Datenbank: 95 %, eine reine Schätzung ohne Bezug zu Urlaub/Krankheit/Feiertagen) --
genau die Lücke, die der neue Produktivstunden-Rechner schließt.

#### Punkt 1 -- die Frage des Betreibers: ist die Vermischung fachlich richtig oder falsch?

Wörtlich: "Wenn ein Betriebskostenposten als 'variabel' (im Auslastungs-Sinn) eingeordnet wird
und in `variable_overhead_value` fließt, vermischt er sich dort mit den automatisch addierten
Verwaltungslöhnen (`variable_employee_costs`). Ist das fachlich richtig oder falsch?"

**Antwort**: rechnerisch harmlos, terminologisch riskant. Rechnerisch, weil Addition vor der
abschließenden Division durch die produktiven Stunden assoziativ ist -- ob ein Auslastungs-
Posten in `variable_overhead_value` oder in einem dritten, separaten Feld steht, ändert am
Ergebnis (`suggested_labor_rate`) nichts, solange am Ende alles in `total_overhead` zusammenläuft
(was ohnehin passiert). Terminologisch riskant, weil zwei fachlich verschiedene Bedeutungen von
"variabel" denselben Codenamen tragen: BWL-Sinn (steigt mit der Auslastung -- Diesel,
Verschleiß, Entsorgung) vs. Code-Sinn (Verwaltungslöhne, die nichts mit Auslastung zu tun haben,
nur mit einer Kosten-Zuordnungsentscheidung je Mitarbeiter). Verschärft dadurch, dass in DIESEM
System kein einziger Kostenposten -- fix oder variabel im BWL-Sinn -- tatsächlich dynamisch mit
der realisierten Auslastung mitläuft: jeder `RecurringCost` ist ein statischer Jahresbetrag,
unabhängig von der Klassifikation. Der Betreiber (und jeder spätere Bediener) könnte deshalb
leicht annehmen, "Auslastungsabhängige Kosten" würden sich im Verrechnungssatz automatisch nach
der tatsächlichen Auslastung richten -- das tun sie nicht, sie werden nur einmalig addiert.

#### Vorschlag zur Auflösung (noch nicht bestätigt)

1. **Die Betriebskosten-Einordnung vermeidet das Wort "variabel" bewusst** -- Werte `"fix"`/
   `"auslastungsabhaengig"`/`"keine"` statt `"fix"`/`"variabel"`/`"keine"`. Label
   "Auslastungsabhängige Kosten (z. B. Kraftstoff, Verschleiß, Entsorgung)" macht die
   BWL-Bedeutung explizit, ohne den Code-Bucket-Namen zu wiederholen.
2. **Die Kern-Felder `variable_overhead_mode`/`variable_overhead_value`
   (`LaborRateOverheadSettings`) werden NICHT umbenannt** -- eine minimale, risikoarme Änderung:
   Umbenennen würde jeden bestehenden Aufrufer/Test/jede Spalte anfassen, für einen Bucket, der
   inhaltlich unverändert bleibt (weiterhin manuelle Kosten + automatisch addierte
   Verwaltungslöhne).
3. **Transparenz statt Umbenennung**: beim Einspeisen (Schicht 3, noch nicht gebaut) zeigt die
   Vergleichsansicht einen Hinweis, dass die Summe der "auslastungsabhaengig" klassifizierten
   Posten mit den automatisch berechneten Verwaltungslöhnen zusammen in `variable_overhead_value`
   einfließt -- der Bediener sieht die Vermischung, statt dass sie stillschweigend passiert.
4. **CLAUDE.md dokumentiert die Begriffsunterscheidung** (dieser Abschnitt) als dauerhafte
   Referenz, damit ein künftiger Bearbeiter nicht erneut über dieselbe Verwechslung stolpert.

**Zum Zeitpunkt von 1.5.1 waren diese vier Punkte noch NICHT umgesetzt** -- die Klassifikations-
werte `keine`/`fix`/`auslastungsabhaengig` waren zwar bereits im Code angelegt (siehe unten, für
die `overview_summary()`-Erweiterung), aber ausdrücklich als vorläufig gekennzeichnet. **Seit
1.5.2 bestätigt und vollständig umgesetzt** -- siehe Unterabschnitt "Die Einspeisung (seit
1.5.2)" unten für alle vier Punkte inkl. Punkt 3 (Vergleichsansicht mit Pflicht-Hinweis).

#### Produktivstunden-Rechner (`app/productive_hours.py`)

Neue Singleton-Tabelle `ProductiveHoursSettings` (`weekly_hours`/`daily_hours`/`vacation_days`/
`public_holidays`/`average_sick_days`/`weather_loss_days`/`unproductive_time_pct`, alle mit
Standardwerten für einen typischen Dachdeckerbetrieb: 40h/8h/30/10/10/5/15 %, ergibt bei 52
Wochen/Jahr rund 67 % statt der bisherigen, pauschal geschätzten 95 %). `calculate_productive_hours()`
ist eine reine Funktion (Settings + `weeks_per_year` → Dict mit jedem Zwischenschritt): Bruttojahres-
stunden (`weekly_hours * weeks_per_year`) minus Urlaub/Feiertage/Ø Krankheit/Schlechtwetter (je in
Tagen × `daily_hours`) minus unproduktive Zeit (Prozentsatz der verbleibenden Stunden) = produktive
Jahresstunden, daraus ein Prozentsatz der Bruttojahresstunden.

**`weeks_per_year` kommt bewusst aus `LaborRateSettings`, kein eigenes Feld** -- exakt die vom
Betreiber selbst gezogene Lehre aus den drei divergierenden `build_customer_and_meta_block()`-
Kopien ("eine Quelle, ein Wert"): ändert sich `weeks_per_year` im Stundensatz-Rechner, zieht der
Produktivstunden-Rechner beim nächsten Lesezugriff automatisch nach, keine zweite, potenziell
abweichende Zahl.

**Schreibt nur nach bewusstem Klick**: `apply_productive_hours_to_labor_rate()` (Muster
`apply_labor_rate_calculation()`, Router `app/routers/labor_rate.py`) überschreibt
AUSSCHLIESSLICH `LaborRateSettings.productive_time_pct` -- kein anderes Feld, kein Automatismus.
`calculate_labor_rate()` selbst ist an keiner Stelle geändert; es liest weiterhin nur
`productive_time_pct`, ohne zu wissen, wie dieser Wert entstanden ist -- **keine zweite,
parallele Formel für dieselbe Zahl** (die andere, vom Betreiber selbst benannte Lehre aus den
drei `build_customer_and_meta_block()`-Kopien).

Neue Endpunkte `GET/PUT /api/productive-hours-settings` + `POST .../apply` (`app/routers/
labor_rate.py`, co-located mit dem bestehenden Stundensatz-Rechner, dieselbe
`require_min_role(ROLE_OFFICE_FINANZEN)`-Schwelle). Oberfläche: neuer Block direkt unterhalb des
bestehenden Stundenverrechnungssatz-Rechners in Einstellungen → Kalkulationsgrundlagen (`settings.html`,
`settings-labor-rate`-Sektion) -- sieben Eingabefelder, ein Rechenweg-Ergebnis (Muster
`renderLaborRate()`) und ein "Übernehmen"-Knopf, der zusätzlich das Feld "Produktive Zeit %" oben
UND die Stundensatz-Berechnung selbst aktualisiert (`refreshLaborRate()`).

Die spätere, in der Anfrage bereits vorgemerkte Ist-Wert-Verfeinerung aus
`TimeEntry.counts_as_productive` (echte Buchungen statt Annahmen) ist bewusst NICHT Teil dieser
Version -- nur hier als künftiger Punkt vermerkt, wie verlangt.

#### `overview_summary()`-Erweiterung (`app/recurring_costs.py`)

Neue, indizierte Spalte `RecurringCost.overhead_classification` (String, `server_default='keine'`
nach Regel 1) -- fester Code-Wert (`OVERHEAD_CLASSIFICATIONS = ("keine", "fix",
"auslastungsabhaengig")`) wie `billing_interval`, keine Optionsgruppe: die Einordnung bestimmt
eine künftige Rechenregel (welcher Gemeinkosten-Bucket gespeist wird), keine freie Anzeigeliste.
"keine" ist der restriktive Default -- ein Posten fließt erst nach bewusster Einordnung in eine
der beiden Summen ein.

`overview_summary()` liefert zusätzlich zur unveränderten `annual_total` (weiterhin die Summe
ALLER aktiven Posten, für die bestehende Anzeige) drei getrennte Jahressummen:
`annual_fixed_from_costs`, `annual_usage_dependent_from_costs`, `annual_none_from_costs` --
Summe der drei Gruppen ergibt exakt `annual_total`. `recurring_costs.html` zeigt sie als
zusätzliche Kennzahlen-Kacheln unterhalb der bestehenden Summenkarte, das Anlegen-/Bearbeiten-
Formular bekommt ein neues Auswahlfeld ("Kalkulatorische Einordnung"), die Kostenliste eine neue
Spalte -- zum Zeitpunkt von 1.5.1 trug jede dieser drei Stellen einen sichtbaren Hinweis
"vorläufige Bezeichnung, siehe Bericht zu Punkt 1", damit niemand die Werte für final hielt,
bevor der Vorschlag oben bestätigt war. **Seit 1.5.2 entfernt** -- die Einordnung ist bestätigt,
siehe unten.

Migration `57062a31dba7` (neue Spalte `recurring_costs.overhead_classification` PLUS neue Tabelle
`productive_hours_settings`), 15 neue Tests (`tests/test_v284_productive_hours_and_overhead_classification.py`),
volle Suite: 1573 Tests grün.

#### Die Einspeisung (seit 1.5.2)

Fortsetzung von 1.5.1, nach der Betreiber-Bestätigung des oben stehenden Vorschlags zu Punkt 1 --
wörtlich: "Der Vorschlag zu Punkt 1 ist richtig, bau ihn so. [...] Die Code-Felder
`variable_overhead_*` bleiben unangetastet, wie du sagst -- kein Umbenennen eines inhaltlich
unveränderten Buckets." Damit sind die vier Vorschlagspunkte oben final:

- `OVERHEAD_CLASSIFICATIONS`/`OVERHEAD_CLASSIFICATION_LABELS` (`app/recurring_costs.py`) sind
  nicht mehr "vorläufig" -- der Erklärtext bei `"auslastungsabhaengig"` lautet jetzt "z. B.
  Kraftstoff, Verschleiß, Entsorgung -- fließt zusammen mit den Verwaltungslöhnen in den
  variablen Gemeinkosten-Bucket", exakt wie vom Betreiber vorgegeben. Alle "vorläufig"/
  "siehe Bericht zu Punkt 1"-Marker sind aus `recurring_costs.html` entfernt (Metrik-Zeile,
  `editClassification`-Feldlabel, das `auslastungsabhaengig`-`<option>`).
- `LaborRateOverheadSettings.variable_overhead_mode`/`.variable_overhead_value` bleiben
  wortwörtlich unverändert -- kein Umbenennen, keine Migration.

Danach die Einspeisung selbst, nach fünf vom Betreiber vorgegebenen Punkten:

**Punkt 1 -- der Pflicht-Hinweis in der Vergleichsansicht.** `recurring_cost_overhead_proposal()`
(neu, `app/labor_rate.py`) baut eine reine Vorschau -- schreibt nichts -- und zeigt getrennt:
"Auslastungsabhängige Betriebskosten: X. Plus automatisch berechnete Verwaltungslöhne: Y. Ergibt
variable Gemeinkosten: X+Y.", sowohl für "aktuell" (die tatsächlich hinterlegten
`LaborRateOverheadSettings`-Werte) als auch für "Vorschlag" (die Summen aus
`overview_summary()["annual_fixed_from_costs"]`/`["annual_usage_dependent_from_costs"]`). Ohne
diesen Hinweis würde ein Betreiber sich wundern, warum der "variable" Gemeinkostenwert höher ist
als die Summe seiner auslastungsabhängigen Posten -- X, Y und X+Y stehen jetzt einzeln da.

**Punkt 2 -- Modus-Zwang, keine stille Semantikänderung.** `apply_recurring_cost_overhead_proposal()`
(neu, `app/labor_rate.py`) setzt `fixed_overhead_mode`/`variable_overhead_mode` IMMER auf `"eur"`
-- unabhängig davon, welcher Modus vorher galt. Das ist eine echte Bedeutungsänderung eines
Feldes (Prozent der Lohnkosten vs. absoluter Jahresbetrag), nicht nur ein neuer Wert -- die
Warnung dafür sitzt bewusst im FRONTEND, vor dem Aufruf (`settings.html::
applyOverheadProposal()`, `confirm()`-Dialog, Regel 4: kein `prompt()`, `confirm()` für
Ja/Nein-Bestätigungen ist etabliert), nicht in der Business-Funktion selbst -- die schreibt
unbedingt, sobald sie aufgerufen wird. Der Dialogtext benennt explizit, welches der beiden Felder
(falls überhaupt eines) vom bisherigen Prozent-Modus betroffen wäre.

**Punkt 3 -- die dreistufige Aufschlüsselung.** Summe (die beiden Kennzahlen-Kacheln oben) → fix/
auslastungsabhängig getrennt (zwei `.metric`-Kacheln, `renderOverheadProposal()` in
`settings.html`) → einzelne Posten aufklappbar (natives HTML `<details>`/`<summary>`, `ocpItemsHtml()`,
gespeist aus `proposal["fixed_costs"]`/`["usage_dependent_costs"]` -- denselben Listen, die
`recurring_cost_overhead_proposal()` über `list_costs(db, include_inactive=False)` gefiltert nach
Klassifikation liefert, "keine" und inaktive Posten bleiben draußen). Gegenüberstellung Vorschlag
gegen aktuell für beide Buckets getrennt, wie oben in Punkt 1 beschrieben.

**Punkt 4 -- eine Formel, eine Quelle.** `calculate_labor_rate()` bekommt einen neuen,
KEYWORD-ONLY-Parameter `overhead_override: dict | None = None` (Default bewahrt exakt das
bisherige Verhalten für jeden bestehenden Aufrufer, keine Signaturänderung an bestehenden
Aufrufstellen nötig). Ist er gesetzt, ersetzt er `fixed_overhead_mode`/`fixed_overhead_value`/
`variable_overhead_mode`/`variable_overhead_value` rein IN-MEMORY für genau diesen einen Aufruf --
die Datenbank wird nicht gelesen verändert, `get_or_create_overhead_settings()` liefert danach
unverändert den alten Stand. `recurring_cost_overhead_proposal()` ruft `calculate_labor_rate()`
deshalb ZWEIMAL auf (einmal unverändert für "aktuell", einmal mit dem Vorschlag als Override für
"Vorschlag") statt selbst eine zweite Kopie der Formel zu pflegen -- `annual_productive_hours`
UND jede andere im Ergebnis-Dict stehende Größe kommen für beide Zustände aus exakt demselben
Code, kein zweiter, hier nachgebauter Rechenweg (das ist die im Punkt-1-Befund selbst gezogene
Lehre, hier konkret angewendet).

**Punkt 5 -- zweistufig, zwei getrennte Knöpfe.** Der neue Knopf "Betriebskosten-Vorschlag
übernehmen" (Schritt 1, `settings.html::applyOverheadProposal()`,
`POST /api/recurring-cost-overhead-proposal/apply`) speist AUSSCHLIESSLICH die beiden
Gemeinkosten-Felder (`fixed_overhead_mode`/`fixed_overhead_value`/`variable_overhead_mode`/
`variable_overhead_value`, plus das Legacy-Spiegelfeld `LaborRateSettings.annual_overhead` im
Gleichschritt mit `fixed_overhead_value` -- dasselbe Muster wie beim bestehenden
`PUT /api/labor-rate-settings`). Er rührt `CalculationSettings.labor_rate` NICHT an. Der
bestehende Knopf "Als aktuellen Verrechnungssatz übernehmen" (Schritt 2,
`apply_labor_rate_calculation()`, unverändert) bleibt der davon getrennte zweite Schritt -- kein
Knopf erledigt beide Schritte in einem.

**Router**: `GET /api/recurring-cost-overhead-proposal` (reine Vorschau) und
`POST /api/recurring-cost-overhead-proposal/apply` (Schritt 1, gibt danach dieselbe Vorschau-
Struktur mit dem neuen Stand zurück), beide co-located im bestehenden `labor_rate`-Router,
dieselbe `require_min_role(ROLE_OFFICE_FINANZEN)`-Schwelle wie der übrige Stundensatz-Rechner
und der Produktivstunden-Rechner. Neue Schemas `OverheadProposalStateOut`/
`RecurringCostOverheadProposalItemOut`/`RecurringCostOverheadProposalOut` (`app/schemas.py`).

**Kein neues Datenmodell, keine Migration** -- die Einspeisung schreibt ausschließlich in bereits
bestehende `LaborRateOverheadSettings`-Spalten, `overhead_override` ist ein reiner
Funktionsparameter ohne Persistenz.

**Oberfläche**: neuer Block "Betriebskosten-Vorschlag für die Gemeinkosten" direkt unterhalb des
Produktivstunden-Rechners in Einstellungen → Kalkulationsgrundlagen (`settings.html`,
`settings-labor-rate`-Sektion) -- `loadOverheadProposalSection()` lädt beim Öffnen der Seite,
`renderOverheadProposal()` baut die beiden Bucket-Kacheln inkl. der aufklappbaren Postenlisten
und der Vorschau, wie sich `suggested_labor_rate` durch die Übernahme ändern würde (rein
informativ, ändert nichts, solange Schritt 2 nicht separat ausgeführt wird).

**Abschließender Angriffstest, wie vom Betreiber verlangt**: `buero_auftrag` und `field` kommen
über KEINEN Teil des Kreislaufs -- weder an die Einordnung (`POST /api/recurring-costs` mit
`overhead_classification`), noch an die Vergleichsansicht (`GET .../recurring-cost-overhead-proposal`),
noch an den Übernehmen-Knopf (`POST .../apply`), noch an den Produktivstunden-Rechner
(`GET/POST /api/productive-hours-settings*`) -- alles ausschließlich `buero_finanzen`/`admin`.
Per rekursivem Schlüssel-Scan bestätigt (kein Kalkulationsfeld wie `suggested_labor_rate`/
`fixed_overhead_annual`/`variable_employee_costs` taucht in einer 403-Antwort auf), ein
Testkonto je Rolle (`router_test_client(db, ..., role=...)`, `ALL_ROLES = ("field",
"buero_auftrag", "buero_finanzen", "admin")`). Null "durchgelassen".

9 neue Tests (`tests/test_v285_recurring_cost_overhead_proposal.py`), volle Suite: 1582 Tests
grün.

## Neugestaltung der Seite Stundenverrechnungssatz (seit 1.5.10)

Umbau von Einstellungen → Kalkulationsgrundlagen → Stundenverrechnungssatz (`app/templates/
settings.html`, `id="settings-labor-rate"`) -- erst ein reiner Befund + Vorschlag (keine
Codeänderung, drei Berichtspunkte), dann nach Bestätigung des Betreibers mit drei präzisierenden
Entscheidungen gebaut. Reine Oberflächenänderung -- kein Endpunkt, kein Schema, keine
Business-Logik geändert.

**Befund (Kurzfassung, vollständig als Text an den Betreiber geliefert)**: die Seite bündelte
DREI eng verzahnte Blöcke (Stundenkostenverrechnungssatz mit 19 Kacheln, Produktivstunden-
Rechner mit 9 Kacheln, Betriebskosten-Vorschlag) in einer Section, nur durch `<hr>` getrennt --
nicht zwei, wie ursprünglich angenommen. Beide unteren Blöcke schreiben beim Klick auf ihren
jeweiligen "Übernehmen"-Knopf sofort in die oberen Felder und lösen sofort ein sichtbares
Neu-Rechnen aus (`refreshLaborRate()`) -- ein Argument für "eine Seite statt Reiter", da ein
Reiterwechsel die gerade erzeugte Bestätigung verstecken würde. Vorschlag: eine Seite (kein
Reiter), drei Zonen (Eingaben / prominentes Ergebnis / aufklappbarer Rechenweg), lange
Fließtextblöcke aus der Fläche.

**Die drei Entscheidungen des Betreibers, umgesetzt:**

1. **Eine Seite, kein Reiter -- bestätigt.** Zusätzlich: der Produktivstunden-Rechner sitzt
   nicht mehr als eigenständiger Block weiter unten, sondern als aufklappbarer Bereich
   ("Produktive Zeit % herleiten (Produktivstunden-Rechner)") **direkt am Feld, das er speist**
   -- räumlich gelöst über CSS-Grid-Platzierung: das `<details class="calc-subsection"
   style="grid-column:1/-1">`-Element steht im DOM direkt nach dem Feld "Produktive Zeit %"
   innerhalb derselben `.rate-grid` (`grid-template-columns:repeat(5,...)`) -- ein
   vollbreites Grid-Item kann in der aktuellen Zeile nicht mehr Platz finden (Spalte 1 ist durch
   das vorherige Feld bereits belegt) und bricht deshalb zuverlässig in eine eigene, volle Zeile
   genau an dieser Stelle um, ohne dass eine feste `grid-row` nötig wäre -- funktioniert
   identisch im schmalen Einspaltenlayout (`@media(max-width:1000px)`), da dort ohnehin jedes
   Grid-Item in reiner DOM-Reihenfolge untereinandersteht. Derselbe Mechanismus für den
   Betriebskosten-Vorschlag ("Betriebskosten-Vorschlag für die Gemeinkosten anzeigen"), platziert
   direkt nach den beiden Gemeinkosten-Feldern (Fixe/Variable Gemeinkosten Wert), die er speist.
   Beide Bereiche starten geschlossen (`<details>` ohne `open`-Attribut, "nur gelegentlich
   gebraucht") -- laden ihre Daten aber unverändert unbedingt beim Seitenaufruf
   (`loadProductiveHoursSection()`/`loadOverheadProposalSection()` bleiben Teil des ungeänderten
   `load()`-Ablaufs, seit 1.5.1/1.5.2) -- nur die Sichtbarkeit ist neu, nicht der Ladezeitpunkt.
2. **Drei-Zonen-Gliederung.** Neue `.zone-label`-Beschriftung ("Eingaben"/"Ergebnis") über den
   jeweiligen Bereichen. Von den bisherigen 19 Kacheln des oberen Rechners (`renderLaborRate()`)
   bleiben **vier** immer sichtbar (neuer Container `#laborRateBasics`, `.rate-result`-Grid):
   Gewichteter Mittellohn, Produktive Jahresstunden, Selbstkosten/h, Ermittelter Satz. **Zwei**
   (Aktueller Satz, Abweichung) wandern in die prominente Ergebnisanzeige (`#laborRateApply`)
   direkt neben die große Satz-Zahl ("Aktuell hinterlegt: X €/h · Abweichung: Y €") -- bewusst
   gebündelt, da eine Abweichung ohne ihren Bezugswert nicht lesbar ist. **Eine** (Direkte
   Mitarbeiter) wird zur sichtbaren Zusatzangabe direkt in der Mittellohn-Kachel
   (`<div class="muted small">N Mitarbeiter</div>`) statt einer eigenen Kachel -- die Zahl bleibt
   damit ohne Hover sichtbar, nur ohne eigene Kachel. Die verbleibenden **13** (Mitarbeiter
   variable GK, Direkte Jahresbruttolöhne, AG-Nebenkosten direkt, Direkte Lohnkosten gesamt,
   Lohnkosten/produktive h, Fixe GK/Jahr, Fixe GK/produktive h, Variable MA-Kosten/Jahr,
   Zusätzliche variable GK/Jahr, Variable GK gesamt/Jahr, Variable GK/produktive h, GK gesamt/
   produktive h, Wagnis & Gewinn/h) stehen **vollständig**, nur zugeklappt, unter
   `#laborRateDetailsPanel` ("Rechenweg im Detail") -- per echtem Browsertest nachgewiesen
   (`document.querySelectorAll('#laborRateResult .metric').length === 13`, unverändert sowohl im
   zugeklappten als auch im aufgeklappten Zustand -- `<details>` entfernt seinen Inhalt nie aus
   dem DOM, blendet ihn nur aus). Der `!r.can_calculate`-Zustand ("Berechnung noch nicht
   möglich") zeigt sich jetzt prominent in der Ergebniszone statt versteckt in den (dann leeren)
   Detailkacheln.
3. **Erklärtext aus der Fläche.** Die beiden langen `.hint`/`.formula`-Blöcke des oberen Rechners
   (Mittellohn-Gewichtung inkl. Link zu Stammdaten → Mitarbeiter, vollständiger Rechenweg)
   wandern unverändert in `#laborRateDetailsPanel`, vor die 13 Kacheln. Die beiden Erklärblöcke
   der Unterrechner wandern mit diesen in deren jeweils eigenen Aufklapp-Bereich. **Geprüft, ob
   ein Fragezeichen-Tooltip sauberer ist als ein Textblock**: ja, für zwei kurze, linkfreie
   Erklärungen, die vorher GAR KEINE Erklärung hatten -- neue `.info-ico`-CSS-Klasse (kleines
   rundes "?", reines `title`-Attribut, keine neue JS-Logik, `cursor:help`) an "Wochen pro Jahr"
   (verweist auf dieselbe Quelle wie der Produktivstunden-Rechner -- "eine Quelle, kein zweites
   Feld", das bereits mehrfach im Projekt etablierte Prinzip) und an "Gewichteter Mittellohn"
   (Gewichtungserklärung). Ein natives `title`-Attribut kann jedoch **keine Links** tragen --
   Erklärungen mit Link (Stammdaten-Verweis) bleiben deshalb bewusst ein echter `.hint`-Block,
   wandern aber ebenfalls in den aufklappbaren Bereich statt in der Fläche zu stehen.

**Nichts geht verloren, wie gefordert**: alle 19 Kacheln, alle 9 Produktivstunden-Kacheln, die
komplette Betriebskosten-Vorschlags-Aufschlüsselung, alle Eingabefelder samt ihrer Schrittweiten
(1.5.9, unverändert) und beide Übernehmen-Abläufe (Produktivstunden-Vorschlag übernehmen → Satz
übernehmen, zwei bewusste Schritte) bleiben vollständig funktionsfähig -- nur ihre Anordnung/
Sichtbarkeit hat sich geändert.

**Alle Text-Referenzen auf "oben"/"unten" wurden an die neue räumliche Anordnung angepasst** --
insbesondere der Betriebskosten-Vorschlag-Hinweistext (der Knopf "Als aktuellen
Verrechnungssatz übernehmen" sitzt jetzt UNTERHALB der Eingaben-Zone, nicht mehr darüber) und die
beiden zugehörigen JS-Statusmeldungen nach dessen Übernahme (`renderOverheadProposal()`/
`applyOverheadProposal()`).

**Unabhängiger, vorbestehender Fund, nicht nur gemeldet, sondern behoben**: beim ersten echten
Browsertest (siehe unten) warf `loadRecurringCostsSettingsSection()` (Betriebskosten-**Modul**-
Einstellungen unter Einstellungen → System -- ein komplett anderer Abschnitt, mit dem
Verrechnungssatz-Umbau inhaltlich nicht verwandt) einen `ReferenceError: moduleStates is not
defined` in der Browser-Konsole. Ursache, per `git diff` bestätigt UNABHÄNGIG von diesem Umbau
bereits vorher so im Code: `load()` ruft `loadRecurringCostsSettingsSection()` innerhalb des
`if(canSeeCalculationSettings){...}`-Blocks auf, an einer Stelle VOR der Zeile, die `moduleStates`
zum allerersten Mal zuweist (`moduleStates=ms;` stand bisher erst später im selben `load()`, ohne
vorheriges `let`/`var` -- die Variable existiert vorher als Binding schlicht nicht). Blieb
unbemerkt, weil die Funktion ohne `await`/`.catch()` aufgerufen wird -- eine daraus resultierende
Promise-Ablehnung ("Uncaught (in promise)") stört die übrige Seite nicht sichtbar, nur die
Konsole. Behoben durch Vorziehen der `moduleStates=ms;`-Zuweisung vor den `if`-Block (ein
zusätzliches `renderModuleStates()` an der alten Stelle bleibt bestehen, harmlos redundant).

**Rollen-Check unverändert**: `{% if can(current_user, 'admin', 'buero_finanzen') %}`
(`app/templates/settings.html`) umschließt die Section nach wie vor, unverändert an derselben
Stelle -- per `git diff` UND per rekursivem Grep bestätigt, dass der Umbau daran nichts geändert
hat.

**Verifiziert**: vollständiger `pytest`-Lauf (1668 Tests) grün; `node --check` gegen den
extrahierten Skriptblock (Jinja-Platzhalter `canSeeCalculationSettings` vorher neutralisiert,
Muster aus früheren Sitzungen). Zusätzlich ein echter, CDP-gesteuerter Headless-Chrome-Durchlauf
gegen eine isolierte, temporäre SQLite-Instanz (Bootstrap-Admin, Zwei-Faktor-Ersteinrichtung mit
`pyotp`, ein Testmitarbeiter für einen berechenbaren Fall -- niemals gegen `dachkonzepte_erp.db`):
beide `<details>`-Bereiche öffnen/schließen sich per Klick auf `<summary>` (`.open`-Property
bestätigt), der Euro/Prozent-Umschalter der Gemeinkosten-Felder wechselt Label UND Schrittweite
weiterhin korrekt (`syncOverheadLabels()` unverändert wiederverwendet, `100`↔`0.5` bestätigt),
und der komplette Zwei-Schritt-Ablauf läuft Ende-zu-Ende durch: "Übernehmen" (Produktivstunden)
setzt `productiveTimePct` sichtbar von 70,00 auf 67,02 %, die Satzanzeige aktualisiert sich sofort
(44,64 → 46,63 €/h); "Als aktuellen Verrechnungssatz übernehmen" schreibt danach den Satz ins
Kalkulationsgrundlagen-Feld und die Abweichungsanzeige geht auf 0,00 € zurück. Browser-Konsole
nach der `moduleStates`-Behebung ohne jede Meldung, auch kein einziges JS-Fehler-Log während des
gesamten Durchlaufs.

## Schlechtwetter-Zeitarten und Abwesenheitskategorie (seit 1.5.3)

Vorbereitung für die spätere Ist-Wert-Auswertung im Produktivstunden-Rechner ("Grundlage für die
späteren Ist-Werte" -- die Ist-Werte selbst sind eine eigene, noch folgende Runde, diese Version
liefert ausschließlich die saubere Erfassung). Erst zwei Befund-Runden (welche Zeitarten/
Abwesenheitsarten heute existieren, ob Krankheit schon von Urlaub getrennt ist, wie viele
Bestandseinträge zu migrieren wären), dann vier vom Betreiber entschiedene Punkte gebaut.

**Punkt 1 -- Prämisse korrigiert: Krankheit/Urlaub waren schon getrennt.** Der Befund zeigte:
`EmployeeAbsence.absence_type`/`EmployeeAbsenceRequest.absence_type` sind freie `String(80)`-
Spalten, gespeist aus der Optionsgruppe `absence_types`, die bereits sechs unterschiedliche Werte
trägt (Urlaub, **Krankheit**, Weiterbildung, Berufsschule, Freizeitausgleich, Sonstiges) --
durchgängig verdrahtet von `create_request()` über `review_request()` bis zur Plantafel-Anzeige.
Der Betreiber verlangte trotzdem eine ZUSÄTZLICHE, feste Kategorie (Urlaub/Krankheit/Fortbildung/
Unbezahlt) für die spätere Ist-Wert-Zählung -- ein fester Code-Wert wie `RecurringCost.
overhead_classification` (`app/absence_requests.py::ABSENCE_CATEGORIES`), KEINE Optionsgruppe:
eine spätere Auswertung muss wissen, welche Werte existieren, ein Admin dürfte sie nicht frei
erweitern können. Das bestehende freie `absence_type`-Feld bleibt UNVERÄNDERT als Ergänzung
daneben (z. B. "Berufsschule" als Unterfall von "fortbildung") -- keine Ablösung.

**Migration ohne Ratewerte**: 0 Bestandszeilen in `employee_absences` UND
`employee_absence_requests` der echten Datenbank (frisch geprüft, nicht angenommen) -- es gab
nichts zu migrieren. Die neue Spalte `absence_category` bekommt trotzdem
`server_default='unbekannt'` (Regel 1) -- für jede andere Installation und gegen einen zwischen
Migrationserstellung und -ausführung eingefügten Datensatz. `"unbekannt"` ist beim Neu-/
Bearbeiten-Schreiben über die Schemas (`EmployeeAbsenceCreate`/`EmployeeAbsenceRequestCreate`,
`Field(pattern="^(urlaub|krankheit|fortbildung|unbezahlt)$")`) bewusst NICHT erlaubt -- entsteht
ausschließlich als Migrations-Rückfallwert, eine spätere Ist-Wert-Auswertung zählt ihn bewusst
nicht mit (verhindert, dass ein geratener/unbekannter Status den Durchschnitt verfälscht).

**Bedienung**: wer eine Abwesenheit anlegt, wählt auch die Kategorie -- dieselbe Person wie beim
bereits bestehenden freien `absence_type`. Ein Monteur/Büro-Mitarbeiter, der über
`POST /api/absence-requests` (Selbstbedienung) einen eigenen Antrag stellt, wählt beide Felder
selbst; das Büro, das über `POST /api/planning/absences` (Plantafel) direkt eine Abwesenheit für
jemand anderen anlegt, ebenso. Keine neue Zuständigkeit.

**Punkt 3 -- Krankheitssichtbarkeit, Vorschlag geprüft und vom Betreiber abgelehnt.** Vorgelegter
Vorschlag (Muster `app/audit.py::redact_wage_snapshot()`, das Lohnfelder bereits heute für
`buero_auftrag` aus der Änderungshistorie entfernt, siehe "Rechtekonzept" -> "Vier Rollen"):
`buero_auftrag` sieht bei Urlaub/Fortbildung/Unbezahlt weiterhin die echte Kategorie (für die
Plantafel-Kapazitätsplanung nötig), bei Krankheit dagegen nur ein neutrales Label ohne Notiz;
`buero_finanzen`/`admin` sehen alles unverändert. **Der Betreiber hat diesen Vorschlag zunächst
nach Rückfrage ausdrücklich abgelehnt** ("Unverändert lassen") -- `buero_auftrag` sollte demnach
weiterhin JEDE Kategorie inkl. Krankheit ungefiltert sehen, exakt wie vor dieser Version. **Seit
1.5.4 revidiert**: derselbe Vorschlag wurde in der Folgerunde erneut aufgegriffen und diesmal
umgesetzt -- siehe Abschnitt "Krankheitssichtbarkeit: buero_auftrag sieht nur noch 'abwesend'
(seit 1.5.4)" unten für die vollständige Umsetzung inkl. der dabei gelösten Anlegen/Bearbeiten-
Frage. Diese Zeile bleibt bewusst stehen, um die Entscheidungsgeschichte nachvollziehbar zu
halten, statt sie rückwirkend zu überschreiben. Für die spätere Ist-Wert-Runde festgehalten: der
Produktivstunden-Rechner selbst zeigt UNABHÄNGIG von dieser Entscheidung nur einen aggregierten
Zähler/Durchschnitt, nie eine Zeile "Mitarbeiter X war Y Tage krank" -- dieselbe Trennung wie bei
den Löhnen (aggregiert ja, personenbezogen nein), unabhängig von der Rolle, die den Rechner öffnet.

**Punkt 2 -- Schlechtwetter Winter/Sommer, drei bestehende Auswertungen mussten angefasst
werden.** Grenze wie vorgegeben: 1.12.–31.3. Winter (gesetzliche Schlechtwetterzeit im
Dachdeckerhandwerk, Saison-Kurzarbeitergeld), sonst Sommer (tarifliches Ausfallgeld) -- die
feineren Wintergeld-Zeiträume (15.12.–Ende Februar) sind bewusst NICHT in die Zeitart eingebaut,
das ist laut Vorgabe eine Abrechnungsfrage, keine Zeitart-Frage. Zwei neue Werte
`weather_winter`/`weather_summer` in der bereits bestehenden Optionsgruppe `time_entry_types`
(vier bisherige Werte: Baustellenzeit/Fahrzeit/Werkstattzeit/Sonstige Arbeitszeit) --
**Migration ergänzt sie explizit in einer bereits gesäten Installation**
(`ensure_default_option_groups()` füllt eine bereits existierende Gruppe nie nachträglich mit
neuen Defaults auf, "Existierende Gruppen werden nicht wieder mit Defaults aufgefüllt", siehe
`app/option_settings.py` -- Muster `257fb2967c93`, der vierte Rahmen-Baustein für einen bereits
gesäten Satz). `DEFAULT_OPTION_GROUPS` selbst ist ebenfalls erweitert, für jede künftige, frische
Installation ohne vorherigen Zugriff.

Erst beim genauen Hinsehen zeigte sich: `entry_type` ist entgegen einer früheren, zu groben
Beschreibung KEIN hart geschlossener Satz -- `app/time_tracking.py::ENTRY_TYPES` (die vier
bekannten Werte) wird nur weich geprüft (`create_manual_entry()`: ein unbekannter Wert wird nicht
abgelehnt, nur ein leerer auf "other" normalisiert), `start_timer()` prüft gar nicht. Die beiden
neuen Zeitarten funktionieren dadurch strukturell bereits ohne Codeänderung -- **aber drei
bestehende Auswertungen hätten sie falsch behandelt, wenn sie unangetastet geblieben wären**:

1. **Produktivität**: `entry_type_is_productive()` lautete `entry_type != "travel"` -- ein
   Einzeiler, keine Liste (die daneben liegende `PRODUCTIVE_TYPES`-Konstante war tot, nirgends
   referenziert, jetzt entfernt). Ohne Anpassung wären beide neuen Zeitarten fälschlich als
   produktiv gezählt worden. Jetzt `entry_type not in NON_PRODUCTIVE_ENTRY_TYPES`
   (`{"travel", "weather_winter", "weather_summer"}`) -- **eine Quelle für `counts_as_productive`**
   (bei Anlage/Änderung eines `TimeEntry` gesetzt), jede nachgelagerte, bereits bestehende
   Auswertung, die dieses Feld liest (Dashboard, Projektmappe, Backoffice-Summen,
   Produktivstunden-Rechner künftig), funktioniert dadurch korrekt, ohne selbst geändert werden
   zu müssen.
2. **DATEV-Export**: `_wage_type()` (`app/time_backoffice.py`) kannte nur vier feste Lohnarten
   (eigene `TimeTrackingSettings`-Spalten je Zeitart) und wäre für einen unbekannten `entry_type`
   stillschweigend auf die Lohnart "Sonstige Arbeitszeit" zurückgefallen -- tariflich falsch,
   Saison-Kurzarbeitergeld und Ausfallgeld sind eigene Lohnarten. Zwei neue Spalten
   `datev_wage_type_weather_winter`/`_weather_summer` plus zwei neue Felder in der
   Backoffice-Oberfläche (Einstellungen → Zeiterfassungs-Backoffice → DATEV/Lohnarten) --
   **bewusst KEIN Rückfall auf "Sonstige"** für diese beiden Zeitarten: fehlt die Lohnart, bricht
   der Export mit einer Warnung ab ("Zeitart weather_winter: DATEV-Lohnart fehlt"), statt falsch
   zu buchen. Der Stundenzettel-PDF/CSV-Export zeigte bisher ohnehin den rohen `entry_type`-Wert
   statt der Optionsgruppen-Bezeichnung (`_entry_type_label()`, neu) -- sonst stünde dort
   "weather_winter" statt "Schlechtwetter Winter".
3. **Abrechnungsschutz**: `create_invoice_from_time_entries()` (`app/invoices.py`, "Rechnung aus
   Zeitbuchungen") holt alle gebuchten Zeiten eines Auftrags ungefiltert nach Zeitart. Da
   `TimeEntry.order_id` NOT NULL ist, muss ein Monteur auch witterungsbedingten Ausfall
   zwangsläufig einem Kundenauftrag zuordnen (Schlechtwetter hat keinen natürlichen "eigenen"
   Auftrag) -- ohne Ausschluss hätte die Funktion diese Stunden als Position "Ausgeführt von …"
   dem Kunden in Rechnung gestellt. Die beiden neuen Zeitarten sind jetzt explizit ausgeschlossen
   (`booked = [... if e.entry_type not in ("weather_winter", "weather_summer")]`). **Fahrzeit
   bleibt davon bewusst unberührt** (bereits bestehendes, nicht Teil dieser Anfrage geändertes
   Verhalten -- Fahrzeit wird heute schon ungefiltert mit abgerechnet, wenn sie über diesen Weg
   läuft).

**Vorschlag statt Zwang beim Buchen**: die Grenze ist eine reine Kalenderregel, deshalb wird beim
Öffnen der mobilen Zeiterfassung (Schnellstart UND Nachtrag) die zum Buchungsdatum passende der
beiden Kacheln optisch hervorgehoben (`weatherSeasonFor(dateStr)`, `time_tracking_field.html`,
CSS-Klasse `.suggested`) -- **übersteuerbar**, keine der beiden Kacheln ist gesperrt oder
automatisch vorausgewählt; bei Nachtrag aktualisiert sich die Hervorhebung, wenn das Datum
geändert wird. Auf der Desktop-Seite (`time_tracking.html`) bleiben Quick-Start-Kacheln bewusst
hart codiert (4 feste Buttons, unverändert seit jeher, keine Weiche für die beiden neuen Werte) --
die beiden neuen Zeitarten sind dort trotzdem sofort über die bereits bestehenden, dynamisch aus
der Optionsgruppe befüllten Dropdown-Felder ("Manuell buchen"/"Gruppenbuchung") erreichbar, ohne
Codeänderung nötig; die Season-Hervorhebung wurde für Desktop bewusst nicht gebaut (primäres Ziel
laut Auftrag: die mobile Ansicht des Monteurs).

**Angriffstest/Regressionstest**: 20 neue Tests
(`tests/test_v286_schlechtwetter_und_abwesenheitskategorie.py`) -- Produktivitäts-Klassifikation
pur und über eine echte `TimeEntry`-Anlage, Abrechnungsschutz (Schlechtwetter wird nie zur
Rechnungsposition, eine Rechnung aus nur Schlechtwetter-Zeit schlägt fehl statt eine leere
Rechnung zu erzeugen), DATEV-Lohnart ohne Rückfall für die beiden neuen Zeitarten, Kategorie-
Validierung (jede der vier echten Kategorien wird akzeptiert, ein unbekannter Wert UND
"unbekannt" selbst werden beim Neuanlegen abgelehnt), Genehmigung kopiert die Kategorie korrekt
auf die entstehende `EmployeeAbsence`, Router-Ebene (`POST /api/absence-requests` verlangt das
neue Pflichtfeld, 422 ohne/mit ungültigem Wert), `GET /api/planning/absences` liefert das neue
Feld und unterstützt einen Filter darauf, sowie die Migrations-Seed-Funktion isoliert
(idempotent, No-op ohne bereits existierende Gruppe). Ein bestehender Test
(`test_v260_role_audit.py::test_absence_requests_stay_open_to_field_as_self_service`) musste um
das neue Pflichtfeld ergänzt werden. Volle Suite: 1602 Tests grün.

## Krankheitssichtbarkeit: buero_auftrag sieht nur noch "abwesend" (seit 1.5.4)

Kurskorrektur zu 1.5.3, wo der Betreiber einen ersten Redaktions-Vorschlag noch abgelehnt hatte
("Unverändert lassen") -- in dieser Runde ausdrücklich erneut aufgegriffen: personenbezogene
Krankheit soll für `buero_auftrag` nicht mehr sichtbar sein, weder Art (Urlaub/Krankheit/
Fortbildung/Unbezahlt) noch der Freitext-Grund. Für die Kapazitätsplanung reicht "abwesend" mit
Zeitraum. `buero_finanzen`/`admin` sehen unverändert alles. Erst ein vollständiger Befund über
jede Stelle, an der Abwesenheiten erscheinen, dann die Klärung der Anlegen/Bearbeiten-Frage
("Backoffice liegt bei buero_auftrag -- wie geht das zusammen, wenn es die Art nicht mehr sehen
darf?"), dann gebaut -- exakt das erst-Befund-dann-Vorschlag-Vorgehen dieses Projekts.

### Sechs Fundstellen

1. **Plantafel-Konflikte** (`_conflicts()`, `app/planning.py`): das Konflikt-Label je Slot
   embeddete `f"{Name} · {absence_type}"` als fertigen Text.
2. **Planungsvorschlag** (`planning_suggestion()`): `absent_employees: [{name, type}]` je Tag.
3. **Team-Tageskapazität** (`planning_board()`, `team_capacity`): `absences: [{employee_id,
   name, type}]` je Team/Tag.
4. **Mitarbeiter-Tageskapazität** (`planning_board()`, `employee_capacity`): `absence:
   absence_type` je Mitarbeiter/Tag.
5. **Die Backoffice-Abwesenheitsliste selbst** -- der eigentliche Fund: **nicht** der separate
   `GET /api/planning/absences`-Endpunkt (den liest aktuell kein Template, nur `POST`/`DELETE`
   werden von `planning.html` genutzt), sondern `GET /api/planning`s Top-Level-Feld `absences`
   -- das ist die tatsächliche Datenquelle von `planning.html::renderAbsences()`. Der separate
   Endpunkt wurde trotzdem mitkorrigiert, für den Fall, dass er künftig doch gelesen wird.
6. **Änderungshistorie** (`GET /api/audit-logs`): doppelter Fund. Die GESPEICHERTE
   `entity_label`-Zeile ("Mitarbeiter-Abwesenheit") trug `absence_type` fest im Text -- anders
   als der `details`-Schnappschuss (JSON, redigierbar) ist ein Label bereits beim Schreiben in
   die Datenbank "gebrannt", eine nachträgliche Redaktion könnte den Text nicht zuverlässig
   wieder in Name/Typ zerlegen. UND der `details`-Schnappschuss selbst enthielt
   `absence_type`/`absence_category`/`notes` wie jedes andere Feld -- `redact_wage_snapshot()`
   (Rechtekonzept "Vier Rollen" Etappe 2) kennt nur Lohnfelder, keine Abwesenheitsfelder.

**Kein Fund**: Dashboard (das "Freigabe"-Widget ruft `GET /api/absence-requests?status=pending`
ohnehin nur für `admin` ab, `isAdmin?...:Promise.resolve([])` -- `buero_auftrag`/`buero_finanzen`
bekommen dort heute schon ein leeres Array, unabhängig von dieser Änderung) und Mitarbeiterseite
(`master_data.html`/`master_data_form.html` zeigen aktuell überhaupt keine Abwesenheiten, nichts
zu redigieren). Monteur (`field`) war bereits vor dieser Version durchgängig sicher: alle sechs
Fundstellen hängen an Endpunkten mit `require_min_role(ROLE_OFFICE_AUFTRAG)`, ein Monteur bekommt
403, bevor irgendeine Geschäftslogik läuft -- geprüft, nicht nur angenommen.

### Die Anlegen/Bearbeiten-Frage: "einmal eintragen, nie wieder lesen"

Drei Varianten wurden dem Betreiber vorgelegt, bevor gebaut wurde:
- **(A) Immer "unbekannt"**: `buero_auftrag` kann beim Anlegen nichts an Art eintragen, der Wert
  wird serverseitig immer auf den Migrations-Rückfallwert "unbekannt" gezwungen, `buero_finanzen`
  muss die echte Art in einem zweiten Schritt nachtragen.
- **(B) Einmal eintragen, nie wieder lesen** -- **gewählt**: `buero_auftrag` darf beim Anlegen
  weiterhin die echte Art eintippen (z. B. nach einem Telefonanruf "Mitarbeiter X ist krank"),
  sieht sie danach aber bei JEDEM Lesen -- auch der eigenen, soeben abgeschickten Anfrage -- nur
  noch als "abwesend". Kein Zusatzschritt für `buero_finanzen`, keine Warteschlange
  unzugeordneter Einträge.
- **(C) Anlegen/Bearbeiten komplett zu `buero_finanzen`**: wie beim Mitarbeiter-Bestand ohne
  Vergütung (Rechtekonzept Etappe 2) -- `buero_auftrag` verliert die Schreibrechte vollständig.

**Der Betreiber wählte (B)** -- keine Ausnahme "aber ich habe es doch gerade selbst getippt": die
Antwort auf den eigenen `POST`/`PUT` ist für `buero_auftrag` ebenso redigiert wie jede spätere
`GET`-Abfrage, konsequent durchgezogen in `_absence_out_for_role()`
(`app/routers/planning.py`).

**Nebenbefund, unabhängig vom eigentlichen Auftrag, aber notwendig für (B)**: `PUT
/api/planning/absences/{id}` überschrieb bisher jedes Feld blind
(`for k,v in payload.model_dump().items(): setattr(row,k,v)`). Ein Formular, das Art/Kategorie/
Notiz gar nicht mehr anzeigt (weil `buero_auftrag` sie nicht lesen kann), hätte sie beim
Speichern stillschweigend auf einen Leerwert zurückgesetzt -- dieselbe Gefahrenklasse wie bei
`upsert_roof_layer()` vor 1.2.19, dort behoben durch `exclude_unset`. Neues
`EmployeeAbsenceUpdate`-Schema (alle Felder optional, kein erzwungener Wert wie bei
`EmployeeAbsenceCreate`) + `payload.model_dump(exclude_unset=True)` -- ein Feld, das der Aufrufer
nicht mitsendet, bleibt unangetastet, unabhängig von der Rolle. Die Datums-Reihenfolge-Prüfung
(`end_date >= start_date`) läuft deshalb NICHT mehr im Pydantic-Validator (der kennt bei einem
Teil-Update nur die gesendeten Felder, nicht den gespeicherten Bestand), sondern im Router NACH
dem Zusammenführen mit den bereits gespeicherten Werten. `planning.html` selbst bietet aktuell
gar keine Bearbeiten-Funktion für Abwesenheiten an (nur Anlegen/Löschen) -- der Fund betraf also
noch keine akute Regression, war aber eine Falle für die nächste UI-Erweiterung.

### Umsetzung: rollenblinde Business-Logik, Redaktion im Router

Durchgängiges Prinzip, wie beim Rechtekonzept schon etabliert: `app/planning.py` kennt keine
Rollen, `app/routers/planning.py` entscheidet.

- **`EmployeeAbsencePlanningOut`** (neues Schema, Muster `EmployeeRosterOut`/`PropertyAccessOut`):
  `id`/`employee_id`/`employee_name`/`start_date`/`end_date` -- fehlt bewusst: `absence_type`,
  `absence_category`, `notes`. `_absence_out_for_role(role, data)` ist die EINE Stelle, die
  entscheidet (`has_min_role(role, ROLE_OFFICE_FINANZEN)` → `EmployeeAbsenceOut`, sonst
  `EmployeeAbsencePlanningOut`) -- verwendet von `list_employee_absences()`,
  `create_employee_absence()` UND `update_employee_absence()` gleichermaßen, Union-Response-Model
  auf allen drei Endpunkten.
- **`_conflicts()`** (`app/planning.py`) liefert für jede Abwesenheits-Konfliktzeile zusätzlich
  ein `label_redacted`-Feld ("… · abwesend" statt "… · Krankheit") -- **bewusst KEINE
  Zeichenketten-Zerlegung** eines bereits zusammengesetzten `"{Name} · {Art}"`-Textstrings im
  Router (fragil, falls ein Name selbst " · " enthält); die Funktion liefert beide fertigen
  Varianten, der Router (`_redact_board_absences()`) wählt nur noch aus.
- **`_redact_board_absences(board, role)`**/**`_redact_suggestion_absences(suggestion, role)`**
  (`app/routers/planning.py`, neu): reine Nachbearbeitung des von `planning_board()`/
  `planning_suggestion()` zurückgegebenen Dicts -- entfernt `"type"` aus `team_capacity`-
  Einträgen, ersetzt `employee_capacity`-Einträge durch die feste Zeichenkette `"abwesend"`,
  reduziert die Top-Level-`absences`-Liste auf die fünf feldsicheren Schlüssel, wählt je Slot das
  passende Konflikt-Label. Für `buero_finanzen`/`admin` unverändert (nur die internen
  `label_redacted`-Hilfsfelder werden aufgeräumt, damit sie nicht versehentlich mit ausgeliefert
  werden).
- **`planning.html::renderAbsences()`**: prüft `'absence_category' in x`, um zwischen dem vollen
  und dem reduzierten Schema zu unterscheiden -- zeigt "Abwesend" statt einer leeren
  " · "-Lücke, wenn die Felder fehlen. Kein Eingriff in die Kachel-/Konflikt-/Kapazitäts-Anzeige
  nötig: `renderBoard()`/`cellHtml()` lesen `c.absences.length` (unverändert korrekt, da nur die
  Länge zählt) bzw. `c.absence` (zeigt jetzt "abwesend" statt der echten Art, ohne Codeänderung,
  da der Router bereits die passende Zeichenkette einsetzt) bzw. `s.conflicts[].label`
  (unverändert korrekt, da der Router bereits das passende Label auswählt).
- **Änderungshistorie**: `app/audit.py::_normalize()`s `EmployeeAbsence`/
  `EmployeeAbsenceRequest`-Zweige nennen im gespeicherten Label künftig nur noch Name + Zeitraum,
  nie die Art -- 0 Bestandszeilen in der echten Datenbank (erneut frisch geprüft), also kein
  historischer Datenverlust durch diese Änderung. Neues
  `ABSENCE_ENTITY_TYPES`/`ABSENCE_FIELD_NAMES`/`redact_absence_snapshot()` (Gegenstück zu
  `WAGE_FIELD_NAMES`/`redact_wage_snapshot()`, aber entitätstyp-GEBUNDEN statt global -- `notes`
  ist nur bei diesen beiden Entitätstypen sensibel, bei jeder anderen Entität bleibt eine Notiz
  für `buero_auftrag` unverändert sichtbar). `app/routers/audit.py` überspringt zusätzlich
  Feldänderungs-Zeilen, deren `field_name` eines dieser drei Felder ist -- exakt das bereits für
  `WAGE_FIELD_NAMES` etablierte Muster, nur um eine zweite Feldmenge ergänzt.

### Angriffstest

`tests/test_v287_absence_visibility.py` (18 Tests) -- rekursiver Schlüssel-Scan (Fehlerklasse
`purchase_price`) über `GET/POST/PUT /api/planning/absences`, `GET /api/planning`,
`POST /api/planning/suggestion` und `GET /api/audit-logs`: `buero_auftrag` bekommt in KEINER
Antwort `absence_type`/`absence_category`/`notes`, auch nicht im Ergebnis der eigenen, soeben
abgeschickten Anfrage; `buero_finanzen`/`admin` sehen alles unverändert; `field` bekommt
durchgängig 403. Zusätzlich: das Teil-Update lässt Kategorie/Notiz tatsächlich unverändert, wenn
`buero_auftrag` sie nicht mitsendet (verifiziert über einen anschließenden `buero_finanzen`-Read);
die Datums-Validierung greift auch bei einem Teil-Update korrekt gegen den gespeicherten
Bestand. Ein bestehender Test aus 1.5.3
(`test_v286_schlechtwetter_und_abwesenheitskategorie.py::test_planning_absences_list_returns_category_and_supports_filter`)
wurde auf `buero_finanzen` umgestellt -- er prüft das Kategorie-Feld/den Filter selbst, nicht die
Rollenreduktion, die jetzt separat und ausführlicher in der neuen Testdatei steht. Volle Suite:
1620 Tests grün.

## Netto und Brutto bei den Betriebskosten (seit 1.5.5)

Nachbesserung an der Betriebskosten-Übersicht (Schicht 1, siehe "Betriebskosten-Übersicht" oben)
-- unabhängig von der Krankheitssichtbarkeit dieser Version, ein eigener, kleiner Auftrag.

**Befund vor dem Bauen**: das bestehende `RecurringCost.amount`-Feld trug keine Steuersemantik --
weder das Modell noch `normalize_to_annual()` kannten einen Steuersatz, der Betrag war einfach
"der Betrag". 0 Bestandszeilen in der echten Datenbank (erneut frisch geprüft) -- eine Migration
war damit für Bestandsdaten folgenlos, aber die Frage "ist der alte Wert netto oder brutto
gemeint" musste trotzdem inhaltlich entschieden werden: `annual_amount` speist direkt in den
Verrechnungssatz-Kreislauf (Schicht 3), und ein Aufwand für die Kalkulation ist wirtschaftlich
immer der Netto-Betrag -- die Vorsteuer ist ein durchlaufender Posten, kein Aufwand. Der
Altbestand wird deshalb rückwirkend als "war schon immer netto gemeint" behandelt, die einzig
konsistente Lesart.

**Umsetzung**: echte Spalten-Umbenennung `amount` -> `net_amount` (kein Drop+Add -- ein
add/drop hätte für eine Installation MIT Bestandsdaten den alten Betrag ersatzlos verworfen, ein
`alter_column()` bewahrt ihn, hier folgenlos bei 0 Zeilen, aber die korrekte Wahl unabhängig
davon). Neue Spalte `tax_rate_pct` (`Numeric(5,2)`, `server_default='19.00'`, Regel 1 beachtet)
-- fester Code-Wert wie `billing_interval`/`overhead_classification` (`TAX_RATES = (19.00, 7.00,
0.00)` in `app/recurring_costs.py`, keine Optionsgruppe: der Satz bestimmt eine Rechenregel für
`gross_amount`, keine freie Anzeigeliste), **je Posten, kein globaler Wert** -- eine
Versicherung mit 0 % und ein Steuerberater-Honorar mit 19 % stehen nebeneinander. Neue Funktion
`gross_amount(net_amount, tax_rate_pct)` -- reine Anzeige-Ableitung wie
`cancellation_deadline()` (selbe Datei), **nie gespeichert, nie Rechenbasis für
`annual_amount`**.

**`overview_summary()` und die Gemeinkosten-Einspeisung aus Schicht 3 (`app/labor_rate.py::
recurring_cost_overhead_proposal()`) mussten NICHT geändert werden** -- beide lesen
ausschließlich das bereits gespeicherte `annual_amount` (über `RecurringCost`-ORM-Objekte bzw.
`cost_to_dict()`s `"annual_amount"`-Schlüssel), niemals `net_amount`/`amount` direkt. Da
`_payload_fields()` `annual_amount` jetzt ausschließlich aus `net_amount` berechnet
(`normalize_to_annual(net_amount, billing_interval)`, Parameter umbenannt, Formel unverändert),
ist die gesamte nachgelagerte Kette automatisch netto-basiert, ohne einen einzigen weiteren
Codepfad anzufassen -- exakt das erwartete Ergebnis einer bereits vorher etablierten "eine
Quelle, keine zweite Berechnung"-Architektur. Ein Korrektheitstest belegt das explizit
(`test_annual_amount_is_computed_from_net_not_gross`): zwei identische Netto-Beträge mit
unterschiedlichem Steuersatz (0 % und 19 %) ergeben denselben `annual_amount` -- wäre die
Rechnung brutto, kämen 1200 vs. 1428 EUR/Jahr heraus statt beide Male 1200.

**Oberfläche** (`recurring_costs.html`): "Netto-Betrag"-Feld ersetzt "Betrag", neues
Steuersatz-Dropdown (19 %/7 %/0 %, Vorgabe 19 %), ein `readonly`-Feld "Brutto-Betrag" wird
client-seitig live nachgerechnet (`updateGrossPreview()`, rein informativ -- der Server
berechnet `gross_amount` beim Speichern ohnehin selbst erneut, es wird nie mitgesendet). Die
Kostenliste zeigt beide Beträge in einer Zelle (netto, brutto nur als kleiner Zusatz, wenn der
Steuersatz > 0 % ist).

Migration `9b3600be64af`, 11 neue Tests
(`tests/test_v288_recurring_cost_netto_brutto.py`), drei bestehende Testdateien
(`test_v283_recurring_costs.py`, `test_v284_productive_hours_and_overhead_classification.py`,
`test_v285_recurring_cost_overhead_proposal.py`) auf `net_amount` umgestellt (reine
Umbenennung ihrer Testdaten, keine inhaltliche Änderung). Volle Suite: 1631 Tests grün.

## Betriebsmittel-Kosten fest als Kostenposten (seit 1.5.7)

Nachbesserung an der Betriebskosten-Übersicht (1.5.0) und der Betriebsmittelverwaltung (1.4.0)
-- löst die 1.5.0-Doppelzählungs-Sonderbehandlung vollständig ab. Erst ein reiner Befund
(berichtet, bevor gebaut wurde, siehe Chatverlauf für die vollständige Herleitung), dann nach
Bestätigung der Bau.

### Befund, in Kurzform

`recurring_cost_per_month` war die einzige Betriebsmittel-Kostenquelle, die ANLEGEN nirgends
kannte -- `master_data_form.html::assetForm()` hatte nie ein Feld dafür, nur die Edit-Seite
(`operational_asset.html`). Per direkter, lesender SQLite-Abfrage gegen die echte, lokale
Datenbank bestätigt: **0** `OperationalAsset`-Zeilen trugen einen Wert, **0** `RecurringCost`-
Zeilen existierten überhaupt -- die Migration war für echte Daten damit folgenlos, blieb aber
inhaltlich nötig (jede andere Installation, der künftige Betrieb). Die Doppelzählungs-Logik aus
1.5.0 (`overview_summary()`s `linked_asset_ids`/`assets_with_quick_cost`/
`annual_from_asset_quick_costs`/`asset_quick_cost_count`, `RecurringCostOut.
asset_quick_cost_hint`, `OperationalAssetOut.has_linked_recurring_cost`) wurde damit zu totem
Code, sobald `recurring_cost_per_month` als zweite Quelle verschwindet -- bestätigt und
ersatzlos entfernt.

### Eine Quelle statt zwei

`OperationalAsset.recurring_cost_per_month` entfällt als eigene Spalte (Migration
`eda89bb8082a`). Eine laufende Rate am Betriebsmittel-Formular erzeugt/ändert/entfernt seither
einen echten `RecurringCost` mit dem neuen Flag `RecurringCost.is_asset_quick_entry=True`
(`app/operational_assets.py::sync_asset_recurring_cost()`, die EINE Stelle, die diesen einen
Posten je Betriebsmittel anfasst). `asset_to_dict()` liefert `recurring_cost_per_month` als
API-Feld unverändert weiter -- jetzt aber LIVE aus dem verknüpften quick-entry-Posten gelesen
(zusätzlich `recurring_cost_id`, damit Finanzen/Admin direkt in die Betriebskosten-Übersicht
springen können).

**Mehrere Postens je Betriebsmittel bleiben möglich, ohne Verwechslungsgefahr.**
`RecurringCost.asset_id` trägt weiterhin bewusst KEIN Unique-Constraint (Leasingrate UND
Versicherung für denselben Transporter bleiben zwei unabhängige, über die allgemeine
Betriebskosten-Oberfläche verknüpfte Zeilen) -- `is_asset_quick_entry` markiert ausschließlich
DEN EINEN Posten, den das Betriebsmittel-Formular selbst verwaltet. "Höchstens ein
`is_asset_quick_entry=True`-Posten je `asset_id`" ist eine reine ANWENDUNGS-Invariante
(`sync_asset_recurring_cost()` sucht immer zuerst den bestehenden, bevor ein neuer angelegt
wird) -- bewusst KEIN DB-Constraint dafür, dieselbe Zurückhaltung wie beim ebenfalls fehlenden
Unique-Constraint auf `asset_id` selbst. `overview_summary()` braucht dadurch keine
Doppelzählungs-Ausnahme mehr: jeder aktive Posten (quick-entry oder eigenständig) fließt genau
einmal in `annual_total` ein.

### Nullsetzen der Rate entfernt den Posten -- mit einer geprüften Ausnahme

Betreiberentscheidung: "ein Posten, der nichts zählt, ist ein Widerspruch -- läuft der
Leasingvertrag aus, soll kein Posten mehr da sein. Trägt man später wieder eine Rate ein,
entsteht ein neuer." `sync_asset_recurring_cost(db, asset, net_amount=None)` löscht den
verknüpften Posten deshalb, statt ihn mit `net_amount=0` stehen zu lassen.

**Die verlangte Prüfung, ob dabei Dokumente/ein Vertragspartner verloren gehen könnten**: ein
frisch aus der Betriebsmittel-Rate erzeugter Posten trägt tatsächlich keine -- ABER er ist ein
vollwertiger `RecurringCost` und über die allgemeine Betriebskosten-Oberfläche (`/betriebskosten`)
später frei nachbearbeitbar (Vertragspartner, Notizen, Kategorie, Vertragsende/Kündigungsfrist,
Dokumente). Genau das kann passieren: jemand trägt nachträglich einen Vertragspartner ein oder
lädt die Leasingrechnung hoch, und Monate später wird die Rate am Betriebsmittel auf null
gesetzt. `_quick_entry_carries_extra_data()` prüft deshalb bei jedem Entfernen, ob der Posten
etwas trägt, das die Betriebsmittel-Rate selbst NIE setzt (`vendor`/`notes`/`category`/
`contract_end_date`/`notice_period_months`/Dokumente) -- ist das der Fall, wird NICHT
stillschweigend gelöscht: `LinkedRecurringCostHasDataError` (statt eines gewöhnlichen
`ValueError`, damit der Router es von Geschäftsregelfehlern unterscheiden kann). Der neue
Endpunkt macht daraus **409** mit `document_count`/`vendor` im Detail -- die Oberfläche
(`operational_asset.html::saveRecurringCost()`) zeigt eine `confirm()`-Nachfrage mit genau
diesen Angaben (Regel 4: kein `prompt()`, `confirm()` für Ja/Nein ist etabliert) und sendet bei
Bestätigung erneut mit `force_remove=true`. Wird die Rate nur GEÄNDERT (nicht auf null
gesetzt), greift die Prüfung nie -- sie betrifft ausschließlich das Entfernen, Steuersatz/
Einordnung/Vertragspartner, die zwischenzeitlich über `/betriebskosten` ergänzt wurden, bleiben
bei einer reinen Betragsänderung unberührt.

### Fest gebunden beim Löschen -- über den bestehenden `before_delete`-Weg, nicht mehr

`delete_asset()` (`app/operational_assets.py`) behandelt verknüpfte `RecurringCost`-Zeilen jetzt
zweigleisig: der EINE quick-entry-Posten wird per `db.delete()` entfernt -- NICHT per
Cascade-Relationship (eine `OperationalAsset.recurring_costs`-Relationship mit
`cascade="all, delete-orphan"` hätte, ohne einen einschränkenden `primaryjoin`, versehentlich
auch jeden eigenständig verlinkten Posten mitgerissen; ein zusätzlicher, auf
`is_asset_quick_entry=True` beschränkter `primaryjoin` wäre nötig gewesen, um das zu vermeiden
-- stattdessen eine einfache, explizite Vorab-Schleife in `delete_asset()` selbst, die dieselbe
Absicherung ohne die Overlap-Komplexität zweier Relationships auf demselben Fremdschlüssel
erreicht). `db.delete()` löst dabei zuverlässig das bereits bestehende `before_delete`-Event auf
`RecurringCostDocument` (1.5.0) aus, das dessen Dateien von der Festplatte entfernt --
`RecurringCost.documents` trägt bereits `cascade="all, delete-orphan"`, kein neuer Mechanismus
nötig. JEDER ANDERE, über `/betriebskosten` eigenständig verlinkte Posten (z. B. die
Versicherung desselben Fahrzeugs) bleibt dagegen bestehen -- nur sein `asset_id` wird auf
`NULL` gesetzt (`RecurringCost.asset_id` ist nullable). Ohne dieses Entkoppeln hätte das
anschließende `db.delete(asset)` unter PostgreSQL (das Fremdschlüssel im Gegensatz zur hier
ungeprüften lokalen SQLite-Entwicklungsdatenbank immer durchsetzt) mit einer
Integritätsverletzung abgebrochen -- geprüft, ob SQLite in diesem Projekt `PRAGMA
foreign_keys` überhaupt setzt: nein, `app/database.py` tut das nicht, das Problem wäre lokal
also unbemerkt geblieben, bis es in Produktion aufgetreten wäre.

### Vorgaben für neu erzeugte Posten

Wie vom Betreiber vorgegeben: **19 % Steuersatz, Einordnung "keine Gemeinkosten"** -- restriktiv,
fließt nicht ungefragt in den Verrechnungssatz-Kreislauf (Schicht 3, siehe oben), der Betreiber
ordnet später bewusst zu, was tatsächlich in die Gemeinkosten gehört. `billing_interval` ist
immer `"monatlich"` (dieselbe Normierung wie die abgelöste Spalte). Diese drei Felder sind im
Betriebsmittel-Formular selbst NICHT editierbar -- wer sie ändern will, tut das über die
allgemeine Betriebskosten-Oberfläche, wo der Posten als ganz normale Zeile erscheint (mit einem
kleinen ⓘ-Hinweis, dass er vom Betriebsmittel-Formular verwaltet wird).

### Rechte-Lücke geschlossen, bevor sie entstehen konnte

Die laufende Rate erzeugt einen echten `RecurringCost` -- Betriebskosten sind seit Etappe 2 des
Rechtekonzepts (1.4.8) ausschließlich `buero_finanzen`/`admin` vorbehalten
(`require_min_role(ROLE_OFFICE_FINANZEN)`, `app/routers/recurring_costs.py`). Das
Betriebsmittel-Formular selbst bleibt aber für `buero_auftrag` offen
(`require_min_role(ROLE_OFFICE_AUFTRAG)`, `app/routers/operational_assets.py`) -- Fuhrpark/
Maschinen-Bestand ist ein Auftrags-, kein Finanz-Datensatz. Ohne Gegenmaßnahme hätte
`buero_auftrag` über das für sie offene Betriebsmittel-Formular indirekt einen `RecurringCost`
erzeugen/ändern/löschen können, obwohl der gesamte `/betriebskosten`-Bereich für sie gesperrt
ist -- exakt die Art Lücke, die der abschließend verlangte Angriffstest aufdecken sollte.

Behoben durch einen **eigenen, engeren Endpunkt**: `PUT /api/operational-assets/{asset_id}/
recurring-cost` (`require_min_role(ROLE_OFFICE_FINANZEN)`, GETRENNT vom allgemeinen `PUT
/api/operational-assets/{asset_id}`) ist die einzige Stelle, die `sync_asset_recurring_cost()`
aufruft. `recurring_cost_per_month` ist aus `OperationalAssetCreate`/`-Update` vollständig
entfernt -- ein über den allgemeinen Endpunkt untergeschobener Wert wird von Pydantic schlicht
ignoriert, bewirkt nichts (per Test belegt: `buero_auftrag` sendet ihn, die Antwort zeigt
`recurring_cost_per_month: null`, kein `RecurringCost` entsteht). Clientseitig
(`operational_asset.html`) liest `init()` `GET /api/auth/status` und deaktiviert das Eingabefeld
für jede Rolle unterhalb `buero_finanzen` (`canManageRecurringCost`), mit dem Hinweis "Nur
Finanzen/Admin können diesen Wert ändern." -- `buero_auftrag` sieht die aktuelle Rate weiterhin
(reine Information, unverändert seit jeher öffentlich für Büro-Rollen), kann sie aber nicht mehr
ändern, weder über die Oberfläche noch über einen direkten API-Aufruf.

### Angriffstest

`buero_auftrag` und `field` kommen an keinen Teil der Betriebskosten, auch nicht an den neu
verknüpften Posten (`tests/test_v289_asset_recurring_cost_link.py`) -- geprüft: der neue,
engere Endpunkt liefert für beide Rollen 403; der allgemeine Betriebsmittel-Endpunkt lässt sich
mit einem untergeschobenen Kosten-Feld aufrufen, ohne dass sich am verknüpften `RecurringCost`
etwas ändert; der komplette `/betriebskosten`-Router bleibt gesperrt, auch mit der bekannten
`cost_id` (kein 404-vs-403-Unterschied, der die Existenz verraten würde). Rekursiver
Schlüssel-Scan, ein Testkonto pro Rolle, null durchgelassen.

Migration `eda89bb8082a` (Spalte entfernt, `is_asset_quick_entry` neu mit `server_default='0'`
-- Regel 1), 18 neue Tests, drei bestehende Testdateien (`test_v277_operational_assets_stufe2.py`,
`test_v280_operational_assets_stufe3.py`, `test_v283_recurring_costs.py`) auf die neue Quelle
umgestellt. Volle Suite: 1649 Tests grün.

## Ist-Werte im Produktivstunden-Rechner (seit 1.5.8)

Nachbesserung am Produktivstunden-Rechner (1.5.1) -- drei der fünf Annahmen (Feiertage,
Schlechtwetter, Krankheit) bekommen einen aus echten Daten hergeleiteten Vergleichswert. Erst
ein Befund (berichtet, bevor gebaut wurde, siehe Chatverlauf), dann drei vom Betreiber
vorgegebene Entscheidungen. Urlaub und unproduktive Zeit bleiben bewusst reine Annahmen ohne
Ist-Wert-Vergleich (Urlaub ist geplant, nicht gemessen; unproduktive Zeit ist keine für sich
buchbare Größe).

### Feiertage: errechnet, aber übersteuerbar

`count_workday_holidays(db, start, end)` (neu, `app/planning.py`, direkt neben `_holiday_rows()`/
`_working_weekdays()`) zählt aktive `PlanningHoliday`-Zeilen im Zeitraum, die auf einen laut
`PlanningSettings` konfigurierten Arbeitstag fallen -- ein Feiertag am Wochenende zieht keine
Arbeitsstunden ab. Wiederverwendet dieselbe Arbeitstage-Definition wie die Kapazitätsplanung
(`_working_weekdays()`), keine zweite, abweichende "Wochenende"-Annahme nur für diesen Rechner.

**Prämisse korrigiert**: `PlanningHoliday` trägt entgegen der ursprünglichen Annahme KEIN
Bundesland-Feld -- es ist eine einzige, unternehmensweite flache Liste (`holiday_date`, `name`,
`active`). Das ändert an der Zählbarkeit nichts: regionale Feiertage (Fronleichnam, Allerheiligen
für NRW) werden einfach als ganz normale Zeilen in dieselbe Liste eingetragen und dadurch
unterschiedslos gezählt wie jeder andere Feiertag -- es gibt nur keine eigene "regional"-Spalte,
die man separat auswerten könnte.

`public_holidays_suggestion(db)` (`app/productive_hours.py`) wertet das laufende Kalenderjahr aus
und liefert den Vorschlag als zusätzliches Feld `public_holidays_suggested` neben dem
unveränderten, frei editierbaren `public_holidays` -- die Oberfläche zeigt ihn mit einem
"übernehmen"-Link, der das Eingabefeld nur vorbefüllt (`applyHolidaySuggestion()`,
`settings.html`), schreibt ihn nie selbst. Real geprüft: 0 `PlanningHoliday`-Zeilen in der
lokalen Datenbank -- der Vorschlag liefert heute `0`, bis die Feiertage über die bestehende
Verwaltung (`/api/planning/holidays`) gepflegt sind.

### Schlechtwetter/Krankheit: Ist-Wert als Orientierung, rollierende 12 Monate

**Personenkreis, die wichtigste Korrektur dieser Runde**: "Monteure, die in den
Verrechnungssatz eingehen" wird über `effective_cost_allocation()=="labor_rate"` bestimmt
(`labor_rate_employees()`, `app/productive_hours.py`) -- dieselbe Personenmenge, die
`calculate_labor_rate()` (`app/labor_rate.py`) bereits als `direct_employees` behandelt. BEWUSST
NICHT über `AppUser.role=="field"`: die Rolle sitzt auf dem Login-Konto, nicht auf `Employee`,
und die meisten Monteure haben gar kein ERP-Login. Real geprüft: **0** `AppUser`-Konten mit
`role='field'`, aber **7** aktive Mitarbeiter mit `effective_cost_allocation()=="labor_rate"` --
ein Filter auf die Rolle hätte den Nenner auf 0 gesetzt und jeden Durchschnitt undefiniert
gemacht.

**Umrechnungsgröße Schlechtwetter (Stunden → Tage), geprüft statt erfunden**: drei
"gepflegte Sollarbeitszeiten" existieren im Projekt --
`ProductiveHoursSettings.daily_hours` (lokal zu genau diesem Rechner, Default 8,00),
`WorkTimeModel.daily_target_hours` (per Mitarbeiter, sommer-/winterabhängig, aus dem
Zeiterfassungs-Backoffice) und `PlanningSettings.daily_work_hours` (Kapazitätsplanung der
Plantafel, kombiniert mit `Employee.weekly_hours` in `_employee_daily_gross_hours()`). Gewählt:
**`ProductiveHoursSettings.daily_hours`** -- NICHT, weil es die genaueste der drei Größen ist
(die beiden anderen sind sogar präziser, weil mitarbeiter-/kalenderspezifisch), sondern weil es
GENAU die Größe ist, mit der `calculate_productive_hours()` bereits heute die Annahme
(`weather_loss_days`) in Stunden umrechnet. Der ganze Zweck dieser Anzeige ist ein direkter
Vergleich "Annahme X Tage vs. Ist-Wert Y Tage" -- dieser Vergleich braucht auf BEIDEN Seiten
dieselbe Definition von "ein Tag". Ein Wechsel auf eine der beiden anderen, für sich genommen
"besseren" Größen hätte die Vergleichbarkeit innerhalb dieses einen Rechners gebrochen, ohne
einen Nutzen zu bringen, der diesen Preis wert wäre. Die Herleitung bleibt in der Oberfläche
nachvollziehbar (`settings.html::renderProductiveHours()` zeigt "X Std. Schlechtwetter über N
Monteure ÷ Y Std./Tag ÷ N Monteure").

`weather_days_actual(db)` summiert `TimeEntry.hours` über `entry_type IN (weather_winter,
weather_summer)`, `status="booked"`, für `labor_rate_employees()` im rollierenden 12-Monats-
Fenster, teilt durch `daily_hours` und die Monteurzahl. Braucht KEINE Anonymitäts-Untergrenze --
Schlechtwetter ist keine Personalinformation.

`sick_days_actual(db)` zählt Kalendertage (inkl. Wochenende -- dieselbe Konvention wie
`average_sick_days` selbst, `calculate_productive_hours()` unterscheidet bei keiner der vier
"Tage"-Annahmen nach Wochentag) aus `EmployeeAbsence` mit `absence_category=="krankheit"`, auf
das Fenster zugeschnitten, gemittelt über dieselbe Personenmenge.

### Anonymitäts-Untergrenze bei Krankheit -- die wichtige Entscheidung

Bei wenigen Monteuren verrät der Durchschnitt eine einzelne Krankheit: drei Monteure,
Durchschnitt "8 Tage", zwei gesund -- jeder kann auf 24 Tage für den Dritten zurückrechnen.
`sick_days_actual()` liefert deshalb unter `MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE` (fester
Code-Wert, **5**, wie vom Betreiber vorgeschlagen und für plausibel befunden -- dieselbe
Größenordnung wie in vielen Datenschutz-Leitfäden übliche Small-Cell-Suppression-Schwellen)
WEDER `average_days` NOCH `total_days` -- `total_days` allein würde die Durchschnittsbildung
(`total/count`) für jeden trivial zurückrechenbar machen, der die (nicht geheime) Monteurzahl
kennt. Nur `employee_count` bleibt sichtbar (Organisationsgröße, keine Gesundheitsinformation).
Bewusst KEIN konfigurierbares Einstellungsfeld für diese Schwelle -- ein Betreiber könnte sie
versehentlich oder bewusst herabsetzen und damit genau den Schutz aufheben, den sie garantieren
soll.

**Real geprüft**: 7 `labor_rate`-Monteure heute -- über der Schwelle, der Krankheits-Ist-Wert
wäre technisch sichtbar. Da aber 0 `EmployeeAbsence`-Zeilen in der lokalen Datenbank existieren,
zeigt er heute ohnehin `0 Tage` bei `0 von 12 Monaten` Datengrundlage -- die Untergrenze greift
erst, wenn die Belegschaft unter 5 `labor_rate`-Mitarbeiter fällt, was für die reale
Installation aktuell nicht der Fall ist.

### Datengrundlage-Anzeige: Pflicht, ehrlich auch bei "0 von 12"

"Beruht auf N von 12 Monaten" -- ein Monat zählt als "mit Daten", wenn mindestens eine gebuchte
`TimeEntry` (beliebiger Zeitart, für Schlechtwetter) bzw. eine `EmployeeAbsence` beliebiger
Kategorie (für Krankheit) für einen der gezählten Monteure existiert. Bewusst DATENGETRIEBEN
statt eines hart codierten Einführungsdatums der neuen Zeitarten/Kategorien (1.5.3) --
unterscheidet "in diesem Monat gab es kein Schlechtwetter/keine Krankheit" (echte Null) von
"in diesem Monat wurde noch gar nichts erfasst" (fehlende Daten), ohne ein Versionsdatum im
Code zu verankern. Bei Krankheit zählt dafür bewusst JEDE Abwesenheitsart (nicht nur Krankheit
selbst) -- ein Monat mit erfasstem Urlaub, aber ohne Krankheit, signalisiert "Abwesenheits-
erfassung war aktiv", nicht "keine Daten vorhanden". `_rolling_window()` liefert dafür
IMMER exakt 12 volle Kalendermonate (bis einschließlich des laufenden, unvollständigen Monats),
nie 11 oder 13 je nach Tagesdatum -- ein einfaches "heute minus 365 Tage" hätte je nach
Monatslängen schwankend viele Kalendermonate berührt.

Real geprüft, Stand der lokalen Datenbank: 0 `EmployeeAbsence`-Zeilen, 0 Schlechtwetter-
Buchungen -- beide Ist-Werte zeigen heute ehrlich "0 von 12 Monaten". Kurz nach Einführung der
Zeitarten ist kaum Aussagekraft da, und die Anzeige darf das nicht beschönigen -- genau die
Nutzervorgabe.

### Keine Doppelzählung, kein neues Datenmodell

`calculate_productive_hours()`/`calculate_labor_rate()` bleiben unangetastet, lesen weiterhin
ausschließlich die gepflegten Settings-Felder (`public_holidays`/`average_sick_days`/
`weather_loss_days`) -- die drei Ist-Werte sind zusätzliche, nie geschriebene Felder in der
API-Antwort (`ProductiveHoursCalculationOut.public_holidays_suggested`/`weather_days_actual`/
`sick_days_actual`), keine neue Spalte, keine Migration nötig. `GET/PUT /api/productive-hours-
settings`/`.../apply` bleiben unverändert `require_min_role(ROLE_OFFICE_FINANZEN)`-gated --
kein neuer Endpunkt nötig, die Ist-Werte hängen sich an die bestehende Antwort.

**Angriffstest**: `buero_auftrag`/`field` bekommen 403 auf den gesamten Endpunkt, wie schon
vorher. Rekursiver Schlüssel-Scan auf der Antwort bestätigt: keine personenbezogenen Bezeichner
(kein `employee_id`/`employee_name`/`first_name`/`last_name`), unter der Anonymitäts-Untergrenze
weder `average_days` noch `total_days` für Krankheit. 19 neue Tests
(`tests/test_v291_produktivstunden_ist_werte.py`), volle Suite: 1668 Tests grün.

## Buchhaltung (seit 1.6.0, Modul "buchhaltung")

Stufe 1 -- Eingangsrechnungen erfassen und ablegen. Vorbereitende Buchhaltung, **kein Ersatz
für den Steuerberater**: sammelt und ordnet empfangene Lieferantenrechnungen mit Beleg, damit
sie später (Stufe 2) kontiert und für den Steuerberater exportiert werden können. KI-Belegauswertung
ist Stufe 3. Diese Version ist ausschließlich manuelle Erfassung -- erst ein vollständiger
Befund (Supplier/Invoice/RecurringCost/Dokumentenablage-Muster), dann zwei vom Betreiber
bestätigte Kernentscheidungen, dann in einer Runde gebaut.

### Befund, kurz zusammengefasst

- **`Supplier`** trägt bereits alles Nötige (Name, Adresse, Kontakt, `supplier_number`) und
  wird komplett über den bereits bestehenden `/api/suppliers`-Endpunkt verwaltet (liegt in
  `app/routers/resource_planning.py`, kein eigenes Business-Logic-Modul) -- Rollen-Schwelle dort
  `require_min_role(ROLE_OFFICE_AUFTRAG)`, buero_finanzen erfüllt diese Schwelle bereits über die
  Hierarchie (`ROLE_RANK`), kein Endpunkt-Umbau nötig, um einen Lieferanten aus dem
  Eingangsrechnungs-Formular heraus neu anzulegen.
- **`Invoice`** (Ausgangsrechnung) ist strukturell verwandt (Netto/Steuer/Brutto, Status,
  Skonto-Felder), aber fachlich eine andere Domäne (selbst erzeugtes, versendetes, GoBD-
  pflichtiges Dokument mit Einfrier-Snapshot-Mechanik) -- bewusst **keine gemeinsame Tabelle**,
  wie vom Betreiber vorgegeben. Übertragbar war das Prinzip fester Code-Werte für Felder mit
  Rechenregel (Steuersatz, Status) statt Optionsgruppen.
- **`RecurringCost.annual_amount`** ist bereits der gespeicherte, normierte Wert, der Schicht 3
  (`app/labor_rate.py::calculate_labor_rate()`) speist -- `RecurringCost.asset_id` (nullable FK,
  bewusst ohne Unique-Constraint) ist das bereits etablierte Muster "mehrere Fakten gegen einen
  geplanten Posten", direkt übertragbar auf Eingangsrechnung↔RecurringCost.
- **Dokumentenablage**: zwei etablierte Muster (mehrere unabhängige Dateien mit Dokumenttyp-
  Katalog wie `OperationalAssetDocument`/`RecurringCostDocument`, ODER eine einzelne, beim
  erneuten Hochladen ersetzte Datei wie `OperationalAssetInspection.document_filename`) --
  gewählt wurde das zweite, da eine Eingangsrechnung fachlich genau einen Beleg hat.

### Zwei Kernentscheidungen des Betreibers

1. **Positionen als optionale Aufschlüsselung, kein Zwang.** `IncomingInvoice.net_amount`/
   `tax_rate_pct` sind der immer vorhandene Gesamtbetrag -- eine einfache Rechnung bleibt ein
   Gesamtbetrag, eine mit gemischten Steuersätzen wird über `IncomingInvoiceItem`-Zeilen
   aufgeschlüsselt. **Existieren Positionen, muss ihre Netto-Summe zum Gesamtbetrag passen** --
   `app/incoming_invoices.py::_validate_item_sum()` meldet eine Abweichung (`ValueError` -> 422),
   statt sie still zuzulassen (Toleranz 0,01 € für Rundung). Beim Speichern werden alle
   Positionen einer Rechnung vollständig ersetzt (kein Teil-Update einzelner Zeilen) -- für die
   manuelle Erfassung in Stufe 1 ausreichend, keine eigene Positions-Historie.
   `invoice_gross_amount()` summiert bei vorhandenen Positionen deren je EIGENE Bruttobeträge
   (jede Position mit ihrem eigenen Steuersatz), nicht den Header-Satz -- eine Rechnung mit
   19%-Material und einer steuerfreien Position hat keinen gemeinsamen Satz.
2. **Plan bleibt Grundlage für den Verrechnungssatz, Ist ist der Beleg -- bestätigt, als
   dauerhafte architektonische Grenze festgehalten.** `IncomingInvoice.recurring_cost_id`
   verbindet eine Eingangsrechnung mit dem geplanten Kostenposten, gegen den sie gebucht wird --
   **ausschließlich für Anzeige/Tracking**. Keine Funktion dieses Projekts darf darüber
   `RecurringCost.annual_amount`/den Verrechnungssatz verändern (siehe `IncomingInvoice`-
   Klassendocstring, `app/models.py` -- die Grenze steht dort ausdrücklich, damit eine künftige
   Session sie nicht versehentlich verdrahtet, weil es naheliegend erscheint). Ein Plan-Ist-
   Abgleich (Summe der verknüpften Eingangsrechnungen vs. `annual_amount`) wurde als Idee
   geprüft -- er würde über `recurring_cost_id` tatsächlich fast kostenlos herausfallen, ist aber
   **nicht Teil dieser Version** (nicht ausdrücklich beauftragt), die Verknüpfung selbst
   ermöglicht ihn später ohne jeden Umbau.

### Datenmodell

Neue, von `Invoice` getrennte Tabelle `IncomingInvoice` (`app/models.py`) plus
`IncomingInvoiceItem` (optionale Positionen, cascade `all, delete-orphan`) und
`IncomingInvoiceSettings` (Singleton, `skonto_reminder_lead_days`, Default 5 Tage).

- **`payment_status`** trägt nur `"offen"`/`"bezahlt"` -- **"überfällig" wird NIE gespeichert**,
  sondern bei jedem Lesezugriff berechnet (`app/incoming_invoices.py::is_overdue()`), exakt
  konsistent mit `Invoice` (`app/invoices.py`: `is_overdue = status=="versendet" and due_date is
  not None and due_date < date.today()`). Geprüft, wie in der Anfrage verlangt, ob das bei
  Ausgangsrechnungen gespeichert oder berechnet wird -- **berechnet**, kein dritter, gespeicherter
  Statuswert, der veralten könnte. `invoice_to_dict()["display_status"]` liefert den fertigen
  Wert (`"offen"`/`"bezahlt"`/`"ueberfaellig"`) für die Listenfilterung.
- **`skonto_percent`/`skonto_deadline`**: Skontofrist als echtes `Date`-Feld (nicht als
  Tageszahl relativ zum Rechnungsdatum wie bei `Invoice.skonto_days`) -- der Beleg des
  Lieferanten nennt die Frist meist direkt als Datum, keine Zahlungsbedingungen-Textmaschinerie
  nötig. `is_skonto_due()`/`is_skonto_overdue()` greifen nur, solange `payment_status=="offen"`
  ist -- eine bereits bezahlte Rechnung braucht keine Skonto-Warnung mehr.
- **Zuordnung**: `project_id`/`asset_id`/`recurring_cost_id` sind alle optional, aber
  **höchstens eine** darf gesetzt sein -- geprüft in `_validate_single_assignment()`, bewusst
  **kein CheckConstraint** (Muster `ServiceReportPhoto`: "gehört immer zu GENAU EINEM ... ODER
  ..., nie zu beidem/keinem", ausschließlich in der Business-Logik geprüft). Eine Rechnung kann
  auch unzugeordnet bleiben.
- **`document_filename`/`document_original_name`**: ein Beleg je Rechnung, 1:1-Muster
  (`app/incoming_invoice_documents.py::replace_document()`/`delete_document_file()`, Kopie des
  ursprünglichen `OperationalAssetInspection`-Musters) -- eigener Ordner
  `DACHKONZEPTE_INCOMING_INVOICE_FILE_ROOT` unter `ERP_DATA_DIR`.
- **`last_skonto_reminder_deadline`**: Idempotenz-Stempel für die On-Demand-Erinnerung, ohne
  expliziten Reset -- Muster `RecurringCost.last_reminder_due_date`.

### Andockpunkte für Stufe 2 (Kontierung) und Stufe 3 (KI-Belegauswertung) -- explizit

- **Stufe 2**: `account_code` (String(20), optional) existiert bereits **sowohl auf
  `IncomingInvoice` als auch auf `IncomingInvoiceItem`** -- bleibt in Stufe 1 durchgängig leer.
  Bewusst ein einfaches Freitextfeld statt einer FK auf einen Kontenrahmen, der noch nicht
  existiert (Stufe 2 entscheidet erst, wie ein Kontenrahmen modelliert wird) -- ein Konto lässt
  sich später je Rechnung (kein Split nötig, `IncomingInvoice.account_code` reicht) ODER je
  Position (Split nötig, `IncomingInvoiceItem.account_code`) eintragen. Beide Felder existieren
  bereits, keine Migration nötig, wenn Stufe 2 kommt -- höchstens eine spätere Ablösung des
  Freitexts durch eine echte FK, falls ein Kontenrahmen als eigene Tabelle entsteht.
- **Stufe 3**: `supplier_id`/`supplier_invoice_number`/`invoice_date`/`net_amount`/
  `tax_rate_pct`/`due_date`/`skonto_percent`/`skonto_deadline` sind exakt die Felder, die eine
  künftige automatische Belegauswertung füllen würde -- das Modell ist 1:1 darauf zugeschnitten,
  keine Umstrukturierung nötig, wenn Stufe 3 kommt.

### Lieferant inline anlegen

Kein neuer Endpunkt -- das Formular (`incoming_invoices.html`) zeigt neben dem
Lieferanten-Dropdown einen "+ Neuer Lieferant"-Umschalter mit einem kompakten Unterformular
(Name Pflicht, Adresse/Kontakt optional). Beim Anlegen wird direkt `POST /api/suppliers`
aufgerufen (bereits bestehender, unveränderter Endpunkt), der neue Lieferant erscheint sofort im
Dropdown und wird automatisch ausgewählt -- kein Seitenwechsel, kein `prompt()` (Regel 4). Die
volle Lieferantenpflege (Adresse im Detail, `supplier_number` u. Ä.) bleibt weiterhin
ausschließlich über `/master-data#suppliers` erreichbar, Regel 10 gilt dafür unverändert -- das
Inline-Formular ist ein Satellit, keine zweite Stammdatenpflege.

### Skonto-Warnung, überfällige Hervorhebung, Ansicht

`check_due_skonto_and_create_reminders()` (`app/incoming_invoices.py`) ist das On-Demand-Muster
von `check_due_cancellations_and_create_reminders()` (`app/recurring_costs.py`) -- läuft nur
beim Laden der Eingangsrechnungen-Liste, kein Scheduler. Erzeugt eine Aufgabe mit
`min_visible_role=ROLE_OFFICE_FINANZEN` (wie bei der Betriebskosten-Kündigungsfrist: eine
Skontofrist geht nur Finanzen/Admin etwas an). Die Liste (`GET /eingangsrechnungen`) zeigt
zusätzlich eine visuelle Hervorhebung (überfällige Zeilen, Skonto-läuft-ab-/verpasst-Badges) --
beides, wie beim Betriebskosten-Vorbild ("Hervorhebung UND Aufgabe"), nicht entweder-oder.

Filter (Status/Lieferant/Zeitraum) laufen über `GET /api/incoming-invoices` -- `supplier_id`/
`date_from`/`date_to` als echte SQL-`WHERE`-Bedingungen, `payment_status` dagegen in Python
gegen den berechneten `display_status` gefiltert (kann keine SQL-Spalte sein, siehe oben).
`GET /api/incoming-invoices/open-liabilities` liefert die Summe offener Verbindlichkeiten
(brutto) plus die Skonto-Warnliste, Muster `RecurringCost.overview_summary()`.

### Rollen und Modul

Modul-Schlüssel **`"buchhaltung"`** (`"betriebskosten"` war bereits belegt). Ausnahmslos
`require_min_role(ROLE_OFFICE_FINANZEN)` an jedem Endpunkt (`app/routers/incoming_invoices.py`)
-- dieselbe Finanzen-Achse wie Betriebskosten-Übersicht/Kalkulationsgrundlagen, kein
`_any_role_dep`. Sidebar-Link und Einstellungen-Abschnitt (Skonto-Vorlaufzeit) sind genauso
strenger gegated als "Finanzen"/"Mahnwesen" selbst (nur buero_finanzen/admin, kein
buero_auftrag) -- Muster `is_module_enabled('betriebskosten') and can(current_user, 'admin',
'buero_finanzen')`.

**Angriffstest bestätigt**: `buero_auftrag`/`field` kommen über keinen Weg an die
Eingangsrechnungen -- Liste, Einzelabruf (auch mit geratener ID -- 403, nicht 404, bevor
irgendeine Geschäftslogik läuft), Beleg-Upload/-Download/-Löschen (auch über eine geratene
Rechnungs-ID), Einstellungen, `check-due`, und die finanz-adressierte Skonto-Aufgabe (weder in
der Liste noch im gemeinsamen Eingang sichtbar, auch mit bekannter ID nicht übernehmbar). 31
neue Tests (`tests/test_v293_incoming_invoices.py`), volle Suite: 1719 Tests grün. Zusätzlich
end-to-end gegen eine isolierte Testinstanz (eigene, temporäre SQLite-Datenbank, niemals gegen
die echte `dachkonzepte_erp.db`) über echtes HTTP verifiziert: Bootstrap-Admin, Zwei-Faktor-
Ersteinrichtung, Lieferant + Eingangsrechnung mit gemischten Positionen anlegen (Brutto korrekt
je Position berechnet), Liste/Summen-Endpunkt liefern die erwarteten Werte, die gerenderte Seite
enthält alle erwarteten Elemente (Supplier-Auswahl, Editor, Positionstabelle, Sidebar-Link).

### Stufe 2, erster Teil: Kontenstamm mit manueller Pflege und Vorkontierung (seit 1.6.1)

Fortsetzung von Stufe 1 -- ausdrücklich **nicht** Teil dieser Runde: der Import der
Steuerberater-Kontendatei und der DATEV-Export (beide brauchen echte Beispieldateien vom
Steuerberater, die noch nicht vorliegen). Erst ein vollständiger Befund zu drei Punkten
(`account_code`-Feld, bestehende Konten/Kontenrahmen-Konzepte, Muster für pflegbare Stammdaten),
dann zwei vom Betreiber angefragte Entscheidungen (Startbestand ja/nein, wie `account_code`
umgestellt wird), dann in einer Runde gebaut. Alles ausschließlich `buero_finanzen`/`admin`, im
bestehenden Modul `"buchhaltung"`.

#### Befund

- **`account_code`** war in Stufe 1 ein einfaches, immer leeres `String(20)`-Freitextfeld auf
  `IncomingInvoice` UND `IncomingInvoiceItem` -- ausdrücklich als Andockpunkt für eine spätere
  Kontierung angelegt (siehe CLAUDE.md-Fassung vor dieser Version), aber nie befüllt: 0 echte
  Zeilen mit einem gesetzten Wert.
- **Kein bestehendes Konten-/Kontenrahmen-Konzept im Projekt.** `TaxKey` (Steuerschlüssel,
  `app/tax_keys.py`) ist eine pflegbare Stammdatentabelle für STEUERLICHE Kennzeichen (z. B.
  "19% Vorsteuer abziehbar"), keine Kontonummer -- geprüft und bewusst getrennt gehalten: ein
  Konto (WAS wurde gebucht) und ein Steuerschlüssel (WELCHE Steuerbehandlung) sind zwei
  unabhängige Dimensionen, die sich auch beim Steuerberater nie zu einem Feld verschmelzen. Die
  DATEV-Buchungscodes an den Zeitarten (`TimeTrackingSettings.datev_wage_type_*`,
  siehe "Schlechtwetter-Zeitarten") sind Lohnarten für die Personalabrechnung -- eine dritte,
  wiederum unabhängige Dimension, kein Sachkonto. Keine der drei bestehenden Konzepte war für den
  Kontenstamm wiederverwendbar, aber `TaxKey` war das direkte Struktur-Vorbild (siehe unten).
- **Pflegbare Stammdaten-Listen**: `SettingOptionGroup`/`SettingOption` (Optionsgruppen) für
  reine Label-Listen ohne Zusatzfelder; eine echte Tabelle (`TaxKey`, `PaymentTerm`,
  `RoofComponentType` u. v. a.), sobald mehr als ein Feld + eine Rechenregel/ein Zusatzattribut
  dazukommt. Der Kontenstamm braucht Kontonummer + Bezeichnung + optionalen Standard-Steuersatz
  -- eindeutig der zweite Fall, `Account` ist deshalb eine echte Tabelle nach dem `TaxKey`-Muster
  (Kontonummer statt `key`, `active`-Flag statt eines zusätzlichen "ist Standard"-Zustands).

#### Punkt 2: der Kontenstamm -- Startbestand: **nein**, bewusst leer

Neue Tabelle `Account` (`app/models.py`): `account_number` (String(20), indiziert),
`label`, `default_tax_rate_pct` (optional, `Numeric(5,2)`, gegen `ACCOUNT_TAX_RATES = (19.00,
7.00, 0.00)` geprüft -- fester Code-Wert wie bei `RecurringCost.overhead_classification`, keine
Optionsgruppe), `active` (Bool, Default an -- **nie Löschen**, nur Archivieren, auch für ein nie
verwendetes Konto: dasselbe Muster wie `TaxKey.archived`). `UniqueConstraint` auf
`account_number`.

**Entscheidung, wie vom Betreiber ausdrücklich zur eigenen Einschätzung gestellt**: **kein**
Startbestand mit vorbelegten SKR-04-Nummern, obwohl der Betreiber selbst zu einem kleinen,
sinnvollen Startbestand neigte. Begründung: das harte Kriterium der Anfrage lautete wörtlich
"echte SKR-04-Nummern, keine erfundenen". SKR 04 und SKR 03 sind zwei unterschiedliche
Kontenrahmen mit unterschiedlichen Nummernkreisen für dieselben fachlichen Konten (z. B. steht
eine Kontenklasse in SKR 03 an anderer Stelle als in SKR 04) -- eine Verwechslung der beiden
Systeme ist ein bekanntes, reales Fehlerrisiko. Für die GRUNDSTRUKTUR (Kontenklassen-Aufbau, das
Prozessgliederungsprinzip von SKR 04 allgemein) besteht ausreichende Sicherheit, aber für die
KONKRETEN, einzelnen Kontonummern der tatsächlich gebrauchten Aufwandskonten (Wareneinkauf,
Miete, Versicherung, Fremdleistungen) ließ sich diese Sicherheit nicht mit der vom Betreiber
verlangten Garantie ("echte Nummern, keine erfundenen") herstellen, ohne eine verifizierbare
Quelle (z. B. die tatsächliche SKR-04-Kontentabelle) einzusehen, die in dieser Sitzung nicht
vorlag. Ein seed mit teilweise falschen Nummern wäre schlimmer als gar keiner -- ein Betreiber,
der einem vorbelegten Konto vertraut, prüft es typischerweise nicht gegen den echten Kontenplan.
Die Tabelle bleibt deshalb leer, bis der Betreiber Konten manuell anlegt (idealerweise nach
Rücksprache mit dem Steuerberater) oder der spätere Datei-Import (Stufe 2, zweiter Teil, nicht
Teil dieser Version) sie befüllt -- exakt dieselbe Zurückhaltung, die `TaxKey` bereits für
denselben Risikotyp übt ("keine Rechtsberatung, bitte mit dem Steuerberater abgleichen").
`Account`-Klassendocstring (`app/models.py`) hält diese Begründung fest, damit eine künftige
Sitzung nicht versucht ist, "nachträglich doch ein paar Konten zu seeden".

**Manuelle Pflege**: `app/accounts.py` (Muster `app/tax_keys.py`, aber ohne
`ensure_default_*()`-Funktion) -- `create_account()`/`update_account()` validieren
`account_number`-Eindeutigkeit (bei Update: schließt die eigene Zeile aus) und
`default_tax_rate_pct` gegen `ACCOUNT_TAX_RATES`. `app/routers/accounts.py`
(`GET/POST /api/accounts`, `GET/PUT /api/accounts/{id}`) -- ausnahmslos
`require_min_role(ROLE_OFFICE_FINANZEN)` plus `is_module_enabled(db, "buchhaltung")`, Muster
`app/routers/tax_keys.py`. Neuer Abschnitt "Kontenstamm" in Einstellungen (`settings.html`,
gleiche strenge Gate wie das übrige Buchhaltungs-Menü) -- Liste, Anlegen/Bearbeiten-Panel,
Archivieren/Aktivieren, ein sichtbarer Hinweistext, warum keine Konten vorbelegt sind.

**Andockpunkt für den späteren Datei-Import (Stufe 2, zweiter Teil, NICHT Teil dieser
Version)**: ein künftiger Import liest die Kontendatei des Steuerberaters zeilenweise und legt
über `account_number` (der stabile, natürliche Schlüssel, `UniqueConstraint`) je Zeile ein Konto
an oder aktualisiert es (Upsert) -- `create_account()`/`update_account()` validieren dafür
bereits alles Nötige, **keine Änderung an der Tabelle oder an diesen Funktionen nötig**, wenn
der Import gebaut wird. Der Andockpunkt für den DATEV-Export (ebenfalls nicht Teil dieser
Version): ein künftiger Export liest `IncomingInvoice.account_id`/`IncomingInvoiceItem.
account_id` und löst sie über `Account.account_number` auf -- beide Felder existieren bereits
(siehe Punkt 3), keine weitere Vorbereitung nötig.

#### Punkt 3: die Vorkontierung -- `account_code` wird zu `account_id` (echte FK), nicht zu einem
Nummern-Verweis-String

**Entscheidung**: der freie `account_code`-String aus Stufe 1 wird durch eine echte
Fremdschlüssel-Spalte `account_id: int | None` (FK auf `accounts.id`) ersetzt, nicht durch einen
weiterhin freien String, der die Kontonummer referenziert. Begründung: jede andere Relation in
diesem Projekt (`project_id`, `asset_id`, `recurring_cost_id`, `supplier_id`, ...) ist eine
FK-auf-Surrogat-ID, niemals ein natürlicher-Schlüssel-String -- eine Ausnahme nur hier hätte eine
zweite, abweichende Konvention eingeführt, ohne einen Vorteil zu bieten (referentielle Integrität,
Umbenennungssicherheit und die bereits bestehende Eager-Load-Infrastruktur sprechen für die FK).
**Migration war sicher, weil 0 reale Zeilen betroffen waren**: direkt gegen die echte, lokale
Datenbank geprüft, bevor die Spalte gedroppt wurde -- 0 Zeilen in `incoming_invoices` und
`incoming_invoice_items` insgesamt (Stufe 1 war zu diesem Zeitpunkt noch nicht im echten Betrieb
genutzt), ein destruktiver Spaltentausch (`DROP account_code` + `ADD account_id`) war deshalb
verlustfrei, kein Backfill nötig.

Migration `329725277349`: legt `accounts` an, tauscht auf `incoming_invoices`/
`incoming_invoice_items` `account_code` gegen `account_id` (benannte FK-Constraints --
SQLite-Batch-Modus verlangt unter Alembic einen echten Namen, `None` scheitert mit
`ValueError: Constraint must have a name`, siehe unten). `Account.default_tax_rate_pct` wird
beim Wählen eines Kontos **client-seitig** als Vorschlag übernommen
(`incoming_invoices.html::applyAccountDefaultTaxRate()`), ist aber jederzeit übersteuerbar -- die
Rechnung entscheidet den tatsächlichen Steuersatz, nicht das Konto. **Kein serverseitiger Zwang**:
`create_invoice()`/`update_invoice()` übernehmen den Kontosatz nie automatisch beim Speichern,
belegt durch `test_account_default_tax_rate_is_never_applied_server_side` (Konto mit 0 %,
Rechnung explizit mit 19 % -- bleibt 19 %).

**Je Rechnung ein Konto ODER je Position** -- `is_invoice_accounted()` (`app/incoming_invoices.py`)
ist die eine Funktion, die "kontiert" definiert: **existieren Positionen, zählt ausschließlich
deren eigener Kontobezug** (jede Position braucht ein Konto, das Header-`account_id` wird dann
irrelevant, auch wenn es noch gesetzt ist); **existieren keine Positionen, zählt der
Header-Kontobezug**. `invoice_to_dict()`/`_item_to_dict()` lösen `account_id` zu
`account_number`/`account_label` auf (Eager-Load in `_invoice_query()`), plus das neue Feld
`is_accounted: bool`.

**Vorkontierung, keine Buchung -- Docstring-Warnung**: `IncomingInvoice.account_id`s Docstring
(`app/models.py`) hält ausdrücklich fest, dass das ERP an keiner Stelle eine steuerliche
Bewertung vornimmt und keinen finalen Buchungssatz erzeugt -- der Steuerberater prüft und bucht,
diese Zuordnung ist nur ein Vorschlag/eine Vorbereitung für den späteren DATEV-Export. Dieselbe
Warnung steht auf `Account` selbst (siehe oben) -- **zwei** Stellen, damit sie unabhängig vom
Einstiegspunkt einer künftigen Sitzung gefunden wird.

**Gefundener, projektrelevanter SQLite-Migrations-Fallstrick**: Alembics `batch_alter_table()`
verlangt unter SQLite einen **explizit benannten** `create_foreign_key()`-Aufruf --
Autogenerate erzeugt standardmäßig `create_foreign_key(None, ...)`, was beim internen
Tabellen-Kopieren-und-Ersetzen mit `ValueError: Constraint must have a name` scheitert. Fix: dem
Aufruf (und dem entsprechenden `drop_constraint()` in `downgrade()`) einen echten Namen geben
(`f"fk_{table}_account_id_accounts"`). Gilt für jede künftige FK-Migration auf SQLite in diesem
Projekt, nicht nur diese eine.

#### Punkt 4: Ansicht -- Kontiert/Nicht kontiert sichtbar

`incoming_invoices.html`: neue Tabellenspalte "Kontierung" mit einem Kontiert-/
Nicht-kontiert-Badge (aus `is_accounted`) -- die unkontierten Zeilen fallen dadurch optisch auf,
bevor ein späterer DATEV-Export eine übersieht. Header-Konto-Feld ist jetzt ein `<select>` aus
dem Kontenstamm (blendet sich aus, sobald Positionen existieren -- dann entscheidet ausschließlich
deren je eigener Kontobezug, `updateAccountFieldVisibility()`), jede Position hat ihr eigenes
Konto-`<select>`. Die "Kontenübersicht" in Einstellungen (siehe Punkt 2) ist dieselbe pflegbare
Liste, kein zweiter Anzeigeort.

#### Tests, Migration, Verifikation

`tests/test_v294_accounts_vorkontierung.py` (23 Tests) -- Kontenstamm (kein Startbestand,
CRUD, Eindeutigkeit, Steuersatz-Validierung, kein Löschen, Archivieren/Aktivieren-Filter),
Vorkontierung (`is_invoice_accounted()` für Header- und Positionsfall inkl. des
"Header-Konto wird bei vorhandenen Positionen irrelevant"-Falls, Validierung unbekannter
`account_id` auf Header UND Position, Steuersatz nie serverseitig übernommen, ein archiviertes
Konto bleibt an einer bereits kontierten Rechnung gültig), und der geforderte Angriffstest:
`buero_auftrag`/`field` bekommen 403 auf jeden `/api/accounts`-Endpunkt (Liste, Einzelabruf auch
mit geratener ID, Anlegen, Ändern) UND auf eine Eingangsrechnung mit gesetztem Konto (rekursiver
Schlüssel-Scan bestätigt: kein `account_number`/`label`/`default_tax_rate_pct` in einer
403-Antwort), sowie bei deaktiviertem Modul für jede Rolle inkl. Finanzen/Admin. Volle Suite:
1740 Tests grün. Migration erfolgreich gegen die echte, lokale `dachkonzepte_erp.db` angewendet
und per direkter `PRAGMA table_info`-Abfrage nachgemessen (0 Datenverlust, Schema exakt wie
erwartet).

### Beleg-Upload schon beim Anlegen (seit 1.6.3)

Bis dahin ließ sich ein Beleg erst im Bearbeiten-Modus hochladen -- `POST /api/incoming-invoices/
{invoice_id}/document` verlangt eine bereits existierende `invoice_id` (Muster
`app/routers/operational_assets.py`), im Anlegen-Formular gab es dafür kein Feld. Auftrag: dasselbe
Warteschlangen-Muster wie beim Betriebsmittel (1.5.6, `pendingAssetDocuments` in
`master_data_form.html::assetForm()`) anwenden -- **kein Backend-Code geändert**, exakt wie beim
Vorbild: kein neuer Endpunkt, kein neues Schema, keine neue Migration. Der bereits bestehende
Upload-Endpunkt wird lediglich zu einem anderen Zeitpunkt (nach dem Anlegen, statt nur im
Bearbeiten-Modus) aus demselben Formular heraus aufgerufen.

**Punkt 1 -- geprüft, ob sich die Warteschlangen-Logik jetzt (zweites Vorkommen) als gemeinsamer
JS-Baustein lohnt: nein, bewusst zwei eigenständige Umsetzungen.** Die beiden Fälle sind
strukturell verschieden, nicht nur zufällig ähnlich benannt:
- Ein Betriebsmittel kann **mehrere unabhängige** Dokumente tragen (`OperationalAssetDocument`,
  eigene Tabelle), jedes mit eigenem `document_type` + optionaler `notes` -- die 1.5.6-Warteschlange
  ist deshalb ein Array `{document_type, file, notes}[]`, mit einer eigenen "+ Vormerken"-Liste
  samt Entfernen-Button je Zeile (`renderAssetDocQueue()`).
- Eine Eingangsrechnung trägt fachlich **immer nur genau EINEN** Beleg (1:1-Ersetzungsmuster,
  `IncomingInvoice.document_filename`/`document_original_name`, siehe `app/incoming_invoice_
  documents.py`) -- kein `document_type`, keine `notes` je Datei, kein Mehrfach-Upload. Die
  Warteschlange ist hier bestenfalls ein einzelnes, optionales `File`-Objekt (`pendingInvoiceDocument`),
  keine Liste.

Ein "gemeinsamer Baustein" hätte entweder die einfachere Eingangsrechnung-Variante künstlich auf
das Array-mit-Metadaten-Schema des Betriebsmittels aufblasen müssen (ein Array mit immer nur einem
Element, ein `document_type`-Feld, das dort nie existiert), oder umgekehrt eine generische
Konfigurationsschicht (austauschbare `buildFormData()`/`renderItem()`-Callbacks je Aufrufer)
gebraucht, deren Indirektion mehr Code wäre als die eigentliche Logik selbst (bei beiden
Implementierungen zusammen keine 40 Zeilen). Das deckt sich mit der bereits im Projekt etablierten
Konvention (siehe CLAUDE.md "Stack & Struktur": kein gemeinsames JS-Modul für kleine Schnipsel,
`_debounce.html` ist die bewusste Ausnahme für eine tatsächlich nicht-triviale, mehrfach
IDENTISCHE Timer-Logik) -- ein Baustein lohnt sich erst, wenn die Form wirklich dieselbe ist, nicht
schon beim zweiten Vorkommen einer ähnlichen IDEE. Die zugrunde liegende Verhaltensregel (vorgemerkte
Datei erst nach erfolgreichem Anlegen hochladen, ein Fehlschlag darf das Anlegen nicht rückgängig
machen) ist als Kommentar an beiden Stellen im Code festgehalten, nicht nur hier.

Kleiner, durch die Verschiedenheit der beiden Seiten bedingter Unterschied bei der Fehleranzeige:
das Betriebsmittel-Formular navigiert nach dem Anlegen auf eine ANDERE Seite (`/betriebsmittel/
{id}`) und zeigt einen Upload-Fehlschlag deshalb per `alert()` (die Statuszeile ginge beim
Seitenwechsel sonst verloren). Der Eingangsrechnungen-Editor bleibt dagegen auf derselben Seite und
wechselt nur in den Bearbeiten-Modus (`openEditEditor(saved.id)`, das war schon vor dieser Änderung
so) -- ein Upload-Fehlschlag steht deshalb einfach als Text in der bereits sichtbaren
`#editorStatus`-Zeile, kein Popup nötig.

**Punkt 2 -- Fehlerfälle, per CDP-Browsertest gegen eine isolierte Testinstanz einzeln
nachgewiesen** (siehe Verifikation unten):
- **Anlegen scheitert** (fehlendes Pflichtfeld ODER, serverseitig, `_validate_item_sum()` lehnt
  einen Positions-Summenabgleich ab -> 422): `docToUpload` wurde vor dem `try`-Block aus dem
  globalen `pendingInvoiceDocument` gelesen, der eigentliche Upload-Aufruf steht aber ERST NACH
  dem erfolgreichen Anlegen im selben `try` -- schlägt das Anlegen fehl, springt die Ausführung
  direkt in den äußeren `catch`, der Upload-Code wird nie erreicht. `pendingInvoiceDocument`
  bleibt dabei unverändert gesetzt, die Dateiauswahl im `<input>` bleibt erhalten -- kein
  verwaister Datensatz (die Rechnung wurde ja nie angelegt), keine verlorene Datei (per Test
  bestätigt: Rechnungszähler unverändert, `pendingInvoiceDocument`/`#createDocFile.files` nach
  dem Fehlschlag weiterhin gesetzt).
- **Anlegen gelingt, der Upload scheitert** (z. B. Datei über 10 MB): die Rechnung bleibt
  bestehen (kein Rollback), `saveInvoice()` zeigt eine Statuszeile, die AUSDRÜCKLICH den
  Dateinamen und den Grund nennt und auf den Bereich "Beleg" weiter unten verweist -- exakt
  dorthin wechselt die Seite ohnehin schon (`openEditEditor(saved.id)`), wo derselbe, bereits
  bestehende Bearbeiten-Modus-Upload (`uploadDocument()`) den erneuten Versuch entgegennimmt.
  Kein stilles Verschlucken -- der Fehler steht so lange sichtbar, bis der Nutzer erneut speichert
  oder die Seite verlässt.

**Punkt 3 -- Upload-Feld bewusst OBEN im Anlegen-Formular, ANDOCKPUNKT für die künftige
KI-Belegauswertung (Stufe 3, noch nicht gebaut).** `IncomingInvoice`s Klassendocstring
(`app/models.py`) nennt bereits seit 1.6.0 die Felder, die eine künftige automatische
Belegauswertung füllen würde (`supplier_id`/`supplier_invoice_number`/`invoice_date`/
`net_amount`/`tax_rate_pct`/`due_date`/`skonto_percent`/`skonto_deadline`) -- in diesem
künftigen Ablauf kommt der Beleg IMMER zuerst (Upload/Foto), erst danach füllt die KI die
restlichen Felder. Das neue `#createDocumentSection` steht deshalb als ERSTES Element im
Anlegen-Formular, noch vor der Lieferantenauswahl (`.supplier-row`) -- nicht aus rein optischen
Gründen, sondern weil genau diese Stelle der Ort ist, an dem eine künftige Stufe-3-Funktion
ansetzen wird: Beleg hochladen -> (künftig) automatisch ausgewertet -> Formularfelder darunter
vorausgefüllt. Bis Stufe 3 gebaut ist, bleibt es bei reiner manueller Erfassung, das Feld tut
nichts anderes als vormerken und nach dem Speichern hochladen.

**Rechte unverändert** -- kein neuer Endpunkt, keine neue Rollenprüfung nötig: der bereits
bestehende `POST /api/incoming-invoices/{invoice_id}/document` bleibt unter
`require_min_role(ROLE_OFFICE_FINANZEN)` (`app/routers/incoming_invoices.py`), unverändert seit
1.6.0 -- `buero_auftrag`/`field` erreichen diesen Bereich weiterhin an keiner Stelle.

**Verifikation**: `node --check` gegen den extrahierten `<script>`-Block (keine JS-Syntaxfehler).
Zusätzlich ein echter, CDP-gesteuerter Headless-Chrome-Durchlauf gegen eine isolierte, temporäre
SQLite-Testinstanz (Bootstrap-Admin, Zwei-Faktor-Ersteinrichtung mit `pyotp`, ein Testlieferant --
niemals gegen `dachkonzepte_erp.db`): das Beleg-Feld steht nachweislich (DOM-Reihenfolge,
`compareDocumentPosition()`) vor der Lieferantenauswahl, per Screenshot zusätzlich visuell
bestätigt; Szenario "Anlegen scheitert" (Positions-Summenabgleich, `50,00 €` gegen `100,00 €`)
zeigt die erwartete Server-Fehlermeldung, lässt die vorgemerkte Datei unangetastet und legt
keine Rechnung an (Zähler unverändert); Szenario "Anlegen gelingt, Upload scheitert" (>10 MB)
legt die Rechnung nachweislich an (`has_document: false` direkt danach), zeigt Dateiname + Grund
in der Statuszeile, und der anschließende Retry über das bestehende Bearbeiten-Modus-Beleg-Feld
gelingt nachweislich (`has_document: true` danach); das Beleg-Feld blendet sich beim Wechsel in
den Bearbeiten-Modus einer bereits bestehenden Rechnung korrekt wieder aus. Keine neuen
`pytest`-Tests (reine Frontend-Änderung, Muster 1.5.6) -- volle Suite weiterhin 1764 Tests grün.

## KI-Fundament (seit 1.6.2)

Fundament für künftige KI-Funktionen im ERP (Belegauswertung, Angebotstexte,
Berichtszusammenfassung) -- eine zentrale, anbieter-unabhängige Schnittstelle. **In dieser
Version wird keine konkrete KI-Funktion gebaut und kein Anbieter festgelegt** -- ausschließlich
die Schnittstelle, an die sich künftige Funktionen anhängen. Erst ein vollständiger Befund
(Zugangsdaten-Verschlüsselung, bestehendes HTTP+Schlüssel-Muster, Modul-/Einstellungssystem),
dann nach Bestätigung des Adapter-Zuschnitts gebaut, mit drei vom Betreiber vorgegebenen
Entscheidungen (Mock-Adapter statt echtem Anbieter, synchron mit hartem Zeitlimit für den
Anfang, Kostenprotokoll ohne Inhalt).

### Befund

- **Zugangsdaten-Verschlüsselung**: `app/crypto.py::encrypt_secret()`/`decrypt_secret()`
  (Fernet, Schlüssel abgeleitet von `secret_key()` aus `app/auth.py`) ist bereits generisch --
  bisher genutzt für SMTP-Passwort und Microsoft-Graph-Client-Secret, beide als
  `*_encrypted`-Spalten auf `SmtpSettings`. `AISettings.api_key_encrypted` nutzt denselben
  Mechanismus unverändert, keine Erweiterung nötig.
- **Übertragbares HTTP+Schlüssel-Muster**: `app/email_sending.py` (Microsoft Graph) ist die
  einzige bestehende externe-HTTP-Dienst-mit-Schlüssel-Anbindung -- nutzt bewusst reines
  `urllib` (Stdlib), nicht `httpx` (obwohl in `requirements.txt`), mit festen, im Code
  verankerten Timeout-Konstanten (`GRAPH_TOKEN_TIMEOUT=15`, `GRAPH_SEND_TIMEOUT=30`) und
  einheitlicher Übersetzung jeder technischen Ausnahme in eine klare `ValueError`. Genau dieses
  Muster ist auf das KI-Fundament übertragen (siehe `AI_CALL_TIMEOUT_SECONDS`,
  `AIProviderError`-Hierarchie unten).
- **Modul-/Einstellungssystem**: `OPTIONAL_MODULES` (`app/modules.py`) ist für abschaltbare
  FACHFUNKTIONEN gedacht, nicht für reine Systemkonfiguration ohne eigene Funktion --
  **bewusst KEIN Eintrag dort für "KI"**, analog zu den E-Mail-Einstellungen, die ebenfalls
  keinen Modul-Eintrag haben. Stattdessen `require_admin()` an jedem Endpunkt (Muster
  `app/routers/email_settings.py`), und `AISettings.enabled` als der eigentliche
  Gesamtschalter für KI-Funktionen (nicht der Modul-Umschalter).

### Die zentrale Schnittstelle

Fünf neue, flache Module (Projektkonvention: `app/*.py`, keine Unterpakete):

- **`app/ai_types.py`**: `AIRequest` (`caller`/`prompt`/`attachments`/`system`),
  `AIResponse` (`text`/`input_tokens`/`output_tokens`/`cost_estimate`), `AIAttachment`
  (`mime_type`/`data`/`filename` -- vorgesehen für eine künftige Belegauswertung, in dieser
  Version von keiner Fachfunktion befüllt), sowie die Fehlerhierarchie `AIProviderError` ->
  `AIProviderNotConfigured`/`AIProviderUnavailable`. `AI_PROVIDERS = ("anthropic", "openai",
  "azure_openai", "google")` -- fester Code-Wert wie `RecurringCost.billing_interval`, keine
  Optionsgruppe (die Auswahl bestimmt, welcher Adapter dispatcht wird, eine Rechenregel).
- **`app/ai_adapters.py`**: `AIProviderAdapter` (Protocol, eine Methode `complete(request, *,
  timeout)`), `MockAIAdapter` (siehe unten), `_ADAPTERS`-Registry (`dict[str, Factory]`).
- **`app/ai_settings.py`**: `get_or_create_ai_settings()`/`update_ai_settings()`/
  `is_ai_available()` -- Muster `app/email_sending.py`, Singleton wie `SmtpSettings`.
- **`app/ai_service.py`**: `call_ai()`/`call_ai_async()` -- die EINEN Stellen, durch die jeder
  künftige KI-Aufruf laufen soll. Liest die Konfiguration, wählt über `_ADAPTERS` den Adapter,
  ruft ihn mit Zeitlimit auf, protokolliert. Kein anderer Code importiert je eine
  Adapter-Klasse direkt.
- **`app/routers/ai_settings.py`**: `GET/PUT /api/ai-settings` + `POST /api/ai-settings/test`,
  ausnahmslos `require_admin()` -- Systemkonfiguration, nicht einmal `buero_finanzen`
  (Betreibervorgabe, anders als z. B. Kalkulationsgrundlagen). Antwortschema liefert nie den
  Schlüssel selbst, nur `has_api_key: bool` (Muster `SmtpSettingsOut`).

Ein Anbieterwechsel ändert dadurch tatsächlich nur eine Datenbankzeile (`AISettings.provider`)
-- kein Code, der einen Anbieter kennt, wird dafür angefasst.

### Mock-Adapter statt echtem Anbieter (Betreiberentscheidung)

Kein einziger echter Anbieter-Adapter in dieser Version -- auch kein "minimaler, aber
austauschbarer" für einen bestimmten Anbieter, wie ursprünglich als Option vorgeschlagen.
Stattdessen `MockAIAdapter` (`app/ai_adapters.py`): liefert eine feste Testantwort ohne jeden
Netzwerkzugriff, optional mit `raise_error=...` für gezielte Fehlerpfad-Tests. Macht die
gesamte Testsuite unabhängig von externen Diensten (Betreibervorgabe: "eine Testsuite darf nie
einen echten KI-Aufruf machen") -- alle 24 neuen Tests (`tests/test_v295_ai_fundament.py`)
laufen ohne jede Netzwerkverbindung.

**"mock" ist bewusst NICHT in `AI_PROVIDERS` enthalten** und kann über `update_ai_settings()`
(den einzigen Schreibweg der Admin-Oberfläche) nie persistiert werden -- geprüft per
`ValueError`. Erreichbar ist der Mock ausschließlich über `call_ai(..., adapter_override=...)`,
ein Parameter, der ausdrücklich für Tests gedacht ist. Damit kann ein Admin "mock" niemals
versehentlich als echten Anbieter wählen, aber die Testsuite deckt trotzdem die VOLLE
Dispatch-/Zeitlimit-/Protokoll-Logik von `call_ai()` ab, nicht nur eine isolierte Attrappe.

Ein künftiger, echter Anbieter ist ein neuer Eintrag in `_ADAPTERS` unter dem jeweiligen
`AI_PROVIDERS`-Wert -- `call_ai()` selbst muss dafür nicht angefasst werden. Bis dahin liefert
ein bereits eingetragener Anbieter (z. B. `provider="anthropic"`, `enabled=True`) bei jedem
Aufruf weiterhin `AIProviderNotConfigured` ("kein Adapter hinterlegt") -- derselbe
Normalzustand wie "gar kein Anbieter gewählt", nur mit spezifischerer Meldung.

### Synchron mit hartem Zeitlimit -- die bewusste Wahl für den Anfang, und wo ein Hintergrund-Ablauf andocken würde

**Betreibervorgabe**: für die künftige Belegauswertung ist ein wartender Nutzer beim Anlegen
einer Rechnung vertretbar (wie bei einem Upload) -- deshalb synchron, mit
`AI_CALL_TIMEOUT_SECONDS = 45.0` (fest im Code, NICHT in den Einstellungen editierbar, Muster
`GRAPH_SEND_TIMEOUT`) als hartes Zeitlimit.

**Wo ein späterer Hintergrund-Ablauf andocken würde, ohne die Schnittstelle umzubauen**: die
Signatur `AIRequest` rein / `AIResponse` raus (oder eine der beiden `AIProviderError`-Klassen)
bliebe unverändert. Eine künftige, lange laufende KI-Funktion (Minuten statt Sekunden, z. B.
ein langer Bericht) würde `call_ai()` nicht anders aufrufen, sondern von einem ANDEREN
Ausführungskontext aus (ein Hintergrund-Task/Worker statt direkt im Request-Response-Zyklus) --
die aufrufende Fachfunktion würde sofort mit einem "wird verarbeitet"-Status antworten und der
Hintergrund-Task würde `call_ai()` normal aufrufen, das Ergebnis in einer neuen, eigenen
Job-Tabelle ablegen (NUR Status + `AIResponse`, niemals die Anfrage selbst -- die
Datenschutz-Zusage unten gilt unverändert). `call_ai()`/`call_ai_async()` selbst bräuchten dafür
keine Änderung, nur einen zweiten, später hinzukommenden Aufrufer.

**Sicherheitsnetz-Timeout, unabhängig vom Adapter-Verhalten**: `_run_with_timeout()`
(`app/ai_service.py`) führt `adapter.complete()` in einem eigenen `ThreadPoolExecutor`-Thread
aus und erzwingt `AI_CALL_TIMEOUT_SECONDS` über `future.result(timeout=...)` -- unabhängig
davon, ob der Adapter sein eigenes `timeout`-Argument tatsächlich beachtet. **Fallstrick, der
beim Bauen gefunden und behoben wurde**: ein `with ThreadPoolExecutor(...) as executor:` ruft
bei `__exit__` IMMER `shutdown(wait=True)` auf -- das hätte den rufenden Thread bei einer
Zeitüberschreitung erneut blockiert, bis der (hängende) Hintergrund-Thread fertig ist, und den
Zweck des Zeitlimits genau dann zunichtegemacht, wenn er am nötigsten ist. Behoben durch
explizites `executor.shutdown(wait=False)` im `finally`-Block -- der rufende Thread kehrt
garantiert spätestens nach 45s zurück, der verwaiste Hintergrund-Thread darf unabhängig davon
zu Ende laufen. Als Regressionstest festgehalten
(`test_call_ai_never_blocks_beyond_the_timeout_even_if_the_adapter_ignores_it`, misst die
tatsächliche Rückkehrzeit gegen einen absichtlich hängenden Test-Adapter).

**Aus async-Code ausschließlich `call_ai_async()` verwenden, nie `call_ai()` direkt** --
`call_ai()` selbst blockiert den rufenden Thread bis zu 45s; direkt aus einer `async def`-Route
aufgerufen würde das die Event-Loop blockieren (derselbe Fehlertyp, der in dieser Datei bereits
für `post_service_report_photo()`/Bildverkleinerung dokumentiert ist). `call_ai_async()` reicht
über `starlette.concurrency.run_in_threadpool()` an Starlettes Threadpool weiter. Aus einer
gewöhnlichen `def`-Route (von Starlette automatisch threadgepoolt) `call_ai()` direkt
verwenden.

### Untersuchung: trägt synchron auf dem Produktivserver?

**Korrektur (nach Server-Verifikation durch den Betreiber, direkt im Anschluss an diese
Version)**: die vorherige Fassung dieses Abschnitts ging von "ein Arbeitsprozess" aus -- eine
zu diesem Zeitpunkt bereits an anderer Stelle in dieser Datei falsch dokumentierte Prämisse
(siehe die Korrektur unter "Produktivbetrieb" oben). Der Betreiber hat den tatsächlichen
`ExecStart` der systemd-Unit auf dem VPS eingesehen: `gunicorn -w 2 --timeout 120` -- **zwei**
Arbeitsprozesse, `--timeout` tatsächlich explizit gesetzt (nicht der gunicorn-Standardwert).
Diese eigene Einschätzung stand ausschließlich auf der Ein-Prozess-Annahme, wo es um die
KONSEQUENZ eines Fehlers ging (siehe unten) -- der Timeout-Mechanismus selbst, die
`call_ai_async()`-Regel und das gesamte übrige Fundament (Mock-Adapter, Protokoll,
Einstellungen) hängen an keiner Stelle von der Prozesszahl ab, siehe die Prüfung am Ende dieses
Abschnitts.

**Zwei Prozesse bedeuten zwei unabhängige asyncio-Event-Loops mit je eigenem
Starlette-Threadpool** -- kein gemeinsamer Speicher, keine gemeinsame Warteschlange zwischen
beiden gunicorn-Arbeitsprozessen. Das ändert die Einschätzung an genau einer Stelle:

- **Gesamtkapazität**: GRÖSSER als mit einem Prozess, nicht kleiner -- wie vom Betreiber
  richtig eingeschätzt, unkritisch. Zwei Threadpools statt einem, mehr gleichzeitig lauffähige
  KI-Aufrufe, bevor irgendein Engpass entsteht.
- **Die `call_ai_async()`-Regel bleibt GENAUSO wichtig, nicht weniger** -- nur ihre Konsequenz
  bei Verstoß ist jetzt genauer zu benennen: eine `async def`-Route, die `call_ai()` DIREKT
  (ohne `run_in_threadpool`) aufruft, blockiert die Event-Loop GENAU DES EINEN
  Arbeitsprozesses, der diese Anfrage bearbeitet -- also die Hälfte der Gesamtkapazität, nicht
  alles und nicht nichts. Das ist exakt die ursprünglich (vor der fälschlichen "ein
  Prozess"-Korrektur der letzten Runde) vom Betreiber selbst benannte Formulierung
  ("die Hälfte der Kapazität") -- sie war die ganze Zeit richtig, die Korrektur der letzten
  Runde war es nicht. Der andere Arbeitsprozess bleibt von einer blockierten Event-Loop des
  ersten vollständig unberührt (kein gemeinsamer Zustand) und bedient währenddessen weiterhin
  jede Anfrage, die gunicorn ihm zuteilt -- "die Hälfte der Kapazität" ist damit trotzdem ein
  ernstzunehmender, kein vernachlässigbarer Ausfall: für die Dauer der Blockade (bis zu
  `AI_CALL_TIMEOUT_SECONDS`) bekommt etwa jede zweite neue Anfrage keine Bearbeitung, real
  spürbar für alle gerade angemeldeten Personen, nicht nur ein theoretisches Risiko.
- **`--timeout 120` jetzt bestätigt statt nur vermutet**: mit `AI_CALL_TIMEOUT_SECONDS = 45`
  deutlich darunter -- ein korrekt thread-abgekoppelter KI-Aufruf lässt die Event-Loop des
  bearbeitenden Prozesses währenddessen frei, der gunicorn-Heartbeat bleibt unabhängig von der
  Aufrufdauer unberührt. Selbst im Fehlerfall (Event-Loop direkt blockiert) würde ein einzelner
  45s-Aufruf `--timeout 120` nicht auslösen -- ein Prozess-Neustart durch gunicorn selbst
  bräuchte entweder einen deutlich längeren Hänger oder mehrere sich überlappende Blockaden. Das
  ändert an der Schwere des "die Hälfte blockiert"-Falls nichts (der tritt schon bei einer
  einzelnen falsch aufgerufenen Route ein), macht aber einen zusätzlichen, durch gunicorn selbst
  ausgelösten Prozess-Abbruch mitten im Request unwahrscheinlich.

**Was sich NICHT ändert, ausdrücklich geprüft**: der Sicherheitsnetz-Timeout in
`_run_with_timeout()` (`ThreadPoolExecutor` + `future.result(timeout=...)` +
`shutdown(wait=False)`) operiert vollständig INNERHALB des einen Prozesses, der ihn ausführt --
er kennt und braucht die Gesamtzahl der gunicorn-Arbeitsprozesse an keiner Stelle. Genauso
unabhängig von der Prozesszahl: die `call_ai_async()`/`run_in_threadpool()`-Empfehlung selbst
(korrektes Thread-Abkoppeln ist innerhalb JEDES einzelnen Prozesses nötig, unabhängig davon, wie
viele es insgesamt gibt), das Mock-Adapter-Fundament, `AISettings`/`AICallLog` und die
Datenschutz-Zusage (keine Inhalte im Protokoll). Kein Teil des tatsächlich gebauten Codes
(`app/ai_service.py` u. a.) musste wegen dieser Korrektur geändert werden -- ausschließlich die
Prosa-Einschätzung der Konsequenz in diesem Abschnitt war betroffen.

**Schlussfolgerung zur gestellten Frage, unverändert**: synchron reicht für den Anfang, kein
sofortiger Hintergrund-Ablauf nötig -- unter der Bedingung, dass jede künftige Fachfunktion
`call_ai_async()` (nie `call_ai()` direkt) aus einer `async def`-Route aufruft, bzw. `call_ai()`
direkt nur aus einer gewöhnlichen `def`-Route. Diese Bedingung ist -- jetzt nachweislich, nicht
nur vermutet -- wichtiger als die gewählte Zeitlimit-Zahl: sie entscheidet, ob ein KI-Aufruf
eine Handvoll Threads bindet (unkritisch, siehe oben) oder die Hälfte des gesamten ERP für
jeden anderen Nutzer für bis zu 45 Sekunden lahmlegt.

### Kostenprotokoll -- niemals Inhalt

`AICallLog` (`app/models.py`): `occurred_at`/`caller`/`success`/`error_type`/`input_tokens`/
`output_tokens`/`cost_estimate`/`duration_ms` -- **strukturell** kein Feld, das Prompt, Anhang
oder Antworttext aufnehmen könnte (nicht nur eine Verhaltenszusage, siehe
`test_ai_call_log_table_has_no_column_that_could_hold_request_or_response_content()`, die
exakt die Spaltenmenge prüft). `error_type` ist der reine Exception-Klassenname, nie dessen
Text -- der könnte bei einem echten Anbieter-Adapter Teile der Anfrage enthalten.

**Geprüft wie ausdrücklich verlangt**: die Anfrage selbst (Prompt, Bild/Dokument) wird an
KEINER Stelle gespeichert -- nicht in `AICallLog`, nicht in einem Cache (es gibt keinen),
nicht in einem Debug-Log (`_log_call()` protokolliert ausschließlich die oben genannten
Metadaten-Parameter, niemals `request.prompt`/`request.attachments`). Ein eigener Test
(`test_a_long_prompt_and_attachment_never_end_up_anywhere_in_the_logged_row`) ruft `call_ai()`
mit einem bewusst vertraulich klingenden Prompt und Anhang auf und bestätigt, dass keine
gespeicherte Spalte diesen Inhalt enthält.

**Anders als `FailedLoginAttempt` bewusst OHNE automatische Bereinigung** -- der Zweck ist hier
nicht kurzlebige Sicherheits-Buchhaltung, sondern dass der Betreiber über die Zeit sieht, was
die KI kostet und ob sie funktioniert. Die Tabelle bleibt wie `AuditLog` dauerhaft bestehen.

### Datenschutz-Rahmen

- **Sichtbarkeit**: `provider`/`api_base_url`/`model` stehen als Klartext-Anzeigefelder in
  Einstellungen → KI → KI-Anbieter (admin-only) -- der Schlüssel selbst bleibt wie beim
  SMTP-Muster ausschließlich als `has_api_key`-Boolean sichtbar, nie im Klartext, auch nicht
  beim Bearbeiten.
- **Gesamtschalter**: `AISettings.enabled`, Default AUS (`server_default='0'`). `call_ai()`
  prüft ihn als Erstes, vor jeder Netzwerkaktivität -- ist er aus, verhält es sich identisch zu
  "kein Anbieter konfiguriert", unabhängig davon, ob bereits ein Anbieter/Schlüssel eingetragen
  ist. Ein Anbieter lässt sich dadurch bereits vorbereiten, ohne dass Daten fließen, solange
  kein AV-Vertrag steht.
- **Hinweistext**: ein statischer Absatz direkt über dem Gesamtschalter in der Oberfläche, der
  auf die Datenübermittlung bei aktiver externer KI und die AV-Vertrags-Pflicht hinweist.

**Nur Administratoren** sehen/konfigurieren die KI-Einstellungen -- `require_admin()` an jedem
Endpunkt, der Menüeintrag selbst ist serverseitig hinter `{% if can(current_user, 'admin') %}`
verborgen (ausblenden, nicht ausgrauen, Muster der übrigen admin-only-Bereiche). Weder
`buero_finanzen` noch `buero_auftrag` sehen den Menüpunkt oder erreichen die Endpunkte --
Systemkonfiguration, keine Finanzfrage (Betreibervorgabe, abweichend von z. B.
Kalkulationsgrundlagen).

### Bewusst NICHT Teil dieser Version

Kein `OPTIONAL_MODULES`-Eintrag (siehe Befund). Kein echter Anbieter-Adapter. Keine
Fachfunktion nutzt `call_ai()`/`call_ai_async()` -- Belegauswertung/Angebotstexte/
Berichtszusammenfassung bleiben eigene, spätere Runden. Kein Hintergrund-Ablauf (siehe oben,
nur die Docking-Stelle ist vorbereitet).

**Tests/Verifikation**: 24 neue Tests (`tests/test_v295_ai_fundament.py`) -- Typen, Mock-Adapter,
Einstellungsverwaltung (inkl. "mock" nie persistierbar), `call_ai()`/`call_ai_async()` (Normalzustand,
Dispatch ohne Adapter, Fehlerübersetzung, das Zeitlimit-Sicherheitsnetz mit Regressionstest gegen
den `shutdown(wait=False)`-Fallstrick, Async-Offloading über die `threaded_db_session`-Fixture,
da `call_ai_async()` tatsächlich in einem anderen Thread läuft), die strukturelle
Kein-Inhalt-Garantie des Protokolls, und der abschließend verlangte Angriffstest
(`buero_finanzen`/`buero_auftrag`/`field` kommen an keinen Teil der KI-Einstellungen, inkl. des
Test-Endpunkts und ohne dass der Schlüssel je in einer 403-/200-Antwort auftaucht). Migration
`d87d5bc04b69` (zwei neue Tabellen, keine Änderung an bestehenden), volle Suite: 1764 Tests grün.

## Self-Seeding gegen gleichzeitigen ersten Zugriff absichern (seit 1.4.6)

Das durchgängige `ensure_default_*()`-Muster dieses Projekts (siehe z. B. "Betriebsmittelverwaltung",
"Umbau der Projektliste", "Aufgabe" -- eine Tabelle wird lazy, beim ersten Lesezugriff, mit
Standardwerten befüllt, damit eine per `Base.metadata.create_all()` erzeugte Testdatenbank ohne
Alembic-Migration trotzdem sinnvolle Defaults bekommt) hatte eine reale Race Condition: zwei
gleichzeitige ERSTE Zugriffe auf eine frische, noch nie geseedete Tabelle lesen beide "leer",
versuchen beide dieselben Standardzeilen einzufügen -- der zweite kollidiert mit einer unabgefangenen
`sqlalchemy.exc.IntegrityError` (UNIQUE-Verletzung), die als 500 durchschlägt. Gefunden als
transparenter Nebenbefund während der 1.4.5-Browserverifikation
(`app/option_settings.py::ensure_default_option_groups()`, `group_key='units'`), in 1.4.6 behoben
-- Details, Abwägung Locking vs. Abfangen und der vollständige Sweep über alle `ensure_default_*()`-
Fundstellen stehen in CHANGELOG.md 1.4.6.

**Die Regel für jede künftige `ensure_default_*()`-Funktion, deren Tabelle einen UNIQUE-Constraint
trägt**: der Anlegeversuch (ob eine einzelne Zeile oder ein ganzer Satz -- je nachdem, ob die
Vorbedingung "dieser eine Schlüssel fehlt" oder "die Tabelle ist komplett leer" lautet) läuft in
einem `with db.begin_nested():`-Block (SAVEPOINT); eine dabei auftretende `IntegrityError` wird
abgefangen und als "ein anderer Prozess war schneller, schon gesät" behandelt, nicht als Fehler
weitergereicht. **Kein bloßes `db.rollback()`** auf der ganzen Session -- das würde auch bereits
zuvor in derselben Schleife erfolgreich angelegte, aber noch nicht committete Zeilen mit verwerfen;
das SAVEPOINT begrenzt den Rollback exakt auf den einen kollidierenden Versuch. **Kein
Sperrmechanismus** -- ein Advisory-Lock wäre PostgreSQL-spezifisch und hätte unter SQLite (dem
zweiten, gleichberechtigt unterstützten Dialekt dieses Projekts) keine Entsprechung.

**Trägt die Tabelle KEINEN UNIQUE-Constraint**, ist die Funktion nicht von dieser Race-Condition-
Klasse betroffen (kein Crash), sondern von einer anderen, leiseren: ein Wettlauf würde stille
doppelte Zeilen anlegen. Das Abfangen einer nie geworfenen `IntegrityError` bewirkt dort nichts --
eine echte Behebung bräuchte zuerst eine Migration, die den fehlenden Constraint ergänzt (bekannte,
noch offene Fälle: `app/document_layout.py`, `app/payment_terms.py`, `app/tax_keys.py`,
`app/reminders.py`, siehe CHANGELOG.md 1.4.6).

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

- **Vier `ensure_default_*()`-Self-Seeding-Funktionen ohne UNIQUE-Constraint, dadurch weiterhin
  anfällig für stille Dopplung bei gleichzeitigem erstem Zugriff** (gefunden beim 1.4.6-Sweep,
  siehe Abschnitt "Self-Seeding gegen gleichzeitigen ersten Zugriff absichern" oben):
  `app/document_layout.py::ensure_default_layout()`, `app/payment_terms.py::ensure_default_payment_terms()`,
  `app/tax_keys.py::ensure_default_tax_keys()`, `app/reminders.py::ensure_default_reminder_levels()`.
  Andere Fehlerklasse als die acht in 1.4.6 behobenen Fundstellen -- kein Crash (keine
  UNIQUE-Verletzung zum Abfangen vorhanden), sondern im seltenen Kollisionsfall zwei identische
  Standardzeilen. Nicht behoben, da eine echte Behebung zuerst eine neue Migration bräuchte
  (fehlenden Constraint ergänzen) -- ein größerer, separat zu entscheidender Schritt, kein reiner
  Code-Fix wie bei den acht anderen. **Ebenfalls bewusst außerhalb**: das strukturell verwandte,
  aber deutlich umfangreichere "get_or_create_settings(id=1)"-Singleton-Muster (`GeneralSettings`,
  `TaskSettings`, `MaintenanceSettings` u. v. a., über zehn Tabellen) -- dort kollidiert ein
  PRIMARY KEY statt eines Business-Keys, ein eigener, größerer Sweep, nicht Teil der 1.4.6-Anfrage.
- **Kolonnenführer-Rolle für Gruppenbuchungen -- bewusst offen, wie vom Betreiber vorgegeben**
  (seit 1.3.60, siehe Abschnitt "Zeiterfassung für Monteure" oben): die reduzierte
  `time_tracking_field.html` kennt keine Gruppenbuchung mehr, ein Monteur bucht nur für sich
  selbst. In der Praxis bucht eine Kolonne aber oft gemeinsam -- dafür bleibt vorerst nur die
  volle `time_tracking.html` (Büro/Admin) erreichbar. Ob und wie ein einzelner Monteur (z. B. der
  Kolonnenführer) künftig selbst gruppenbuchen darf -- eine vierte Rollenausprägung, ein
  Team-Attribut "Kolonnenführer", oder eine andere Lösung -- ist eine eigene, spätere
  Entscheidung, ausdrücklich noch nicht getroffen.
- **`service_reports.html`s "Auftrag"-Link zeigt für `field` auf eine jetzt gesperrte Seite**
  (seit 1.3.57, Seiten-Klassifizierung): `/orders/{id}` ist Büro/Admin -- ein Monteur, der auf
  diesen Link klickt, landet auf `access_denied.html` statt auf der Auftragsseite. Kein
  Datenleck (die API dahinter war für `field` nie erreichbar), aber ein unnötiger Zwischenstopp.
  Nicht mitgefixt, da außerhalb des angefragten Umfangs (Seiten-Klassifizierung, nicht
  Template-Aufräumen) -- saubere spätere Lösung: den Link clientseitig ausblenden, wenn
  `authStatus.user.role==='field'` (Muster `can()`, aber ohne Server-Rendering-Kontext auf
  dieser Seite verfügbar, siehe `_sidebar.html`s `can(current_user, ...)` für das Gegenstück
  mit Server-Rendering).
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
  Einstiegspunkten geprüft (`GET /mobil`-Seitenaufruf, `GET /api/field-view/today`), bewusst
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

Der frühere Eintrag "Büro-Suche findet Aufgaben unabhängig von der Zuweisung" ist mit 1.4.4
vollständig aufgelöst: `_search_tasks()` (`app/search.py`) nutzt seither `list_tasks_for_user()`
(`app/tasks.py`) und findet damit dieselbe Menge wie `GET /api/tasks`, siehe Abschnitt
"Büro-Suche" -> "Nachtrag (seit 1.4.4)" unten.
