# Dachflächen & Bauteile, Wartungsvertrag, Einsatzbericht, Rechnung aus Zeitbuchungen, Schnellauftrag, Wartungshistorie, Monteursansicht

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

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
  ungesichertem Session-Zustand kombiniert, nicht nur für diese eine Stelle. **Seit 1.8.42** heißt die
  Funktion `load_calculation_settings()` und committet nicht mehr (Grunddaten beim Start,
  `docs/archiv/grunddaten-beim-start.md`); die Schema-Introspektion bleibt und mit ihr die Reihenfolge --
  1.8.42 erneut gesehen in `test_v052` (geflushte Werte auf `:memory:`-SQLite verworfen).
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

---

## Nachtrag 1.8.34 (01.10.2026) -- gemeinsame Zeichenfläche im Einsatzbericht

Die Unterschriftskarte des Einsatzberichts (`service_reports.html`, Monteur und Kunde nacheinander auf derselben
Fläche) zeichnet seit 1.8.34 über `app/templates/_unterschrift.html` (`unterschriftsfeld()`), gemeinsam mit
Checkliste und Vertrag (siehe `docs/archiv/vertragsgrundlage-und-vertrag.md`, "Umsetzung 1.8.34"). Behoben dabei:
die Fläche hatte `background:var(--card)` und Strich `#182420` -- im dunklen Theme war die Unterschrift beim
Zeichnen kaum zu sehen; jetzt in beiden Themes weiß mit dunklem Strich. Neu: Zeichnen in Geräteauflösung
(`devicePixelRatio`, vorher CSS-Pixel) -- das PNG ist auf einem Tablet entsprechend größer, das PDF zeigt es
weiterhin in 60×30 mm. Ablauf, API (`installer_/customer_signature_png_base64`) und `sign_report()` unverändert.
Nebenbefund: `_decode_signature_png()` begrenzt die Größe nicht (Checkliste und Vertrag: 2 MB).
