# Grunddaten beim Start statt beim ersten Lesen (seit 1.8.42)

Vor jeder Änderung an einer Einstellung, einem Standardsatz oder einer Lesefunktion, die Einstellungen
liest, diese Datei lesen (Regel 14, Regel 23).

## Betreibervorgabe (Pflege-Runde 1.8.42)

1. Alle Einstellungen und Standardgruppen, die beim ersten Lesen angelegt werden (u. a. `labor_rate_settings`,
   Gemeinkosten-Einstellung, `ensure_default_option_groups`), per Migration bzw. beim Start anlegen. Lesepfade
   schreiben nichts mehr. Liste der umgestellten Stellen melden.
2. Dauerhafter Test: im Rundgang des Datengrenze-Tests (alle GET-Endpunkte) prüft ein Datenbank-Listener, dass
   kein GET schreibt. Feste Ausnahmeliste, die nur kürzer werden darf (wie Regel 22).
3. Gegenproben: frische Datenbank mit zwei gleichzeitigen Erstaufrufen gegen PostgreSQL ohne Fehler;
   `klicktest_vertragsgrundlage.py` mehrmals hintereinander grün; Festschreiben und Unterschreiben des Vertrags
   rendern ohne Blockade.
4. Die Reihenfolge-Regel im Docstring von `time_backoffice.py` aus 1.8.8 entfällt.

## Ausgangslage bis 1.8.41

Jede Lesefunktion legte ihre Zeile beim ersten Zugriff selbst an und committete dabei: 18 Singleton-Einstellungen
(`get_or_create_*_settings()`, id=1) plus die globalen Kalkulationsgrundlagen, dazu 12 Standardsätze
(`ensure_default_*()` in `list_*`, `get_option_group()`, `resolve_category_id()`, `default_pipeline_column_id()`,
im PDF-Rahmen usw.). 1.4.6 hatte die Sätze mit UNIQUE gegen den gleichzeitigen ersten Zugriff abgesichert
(SAVEPOINT, IntegrityError als "schon gesät"); offen blieben die vier Sätze ohne UNIQUE (still doppelt) und das
Singleton-Muster (Primärschlüssel). Folgen:

- 1.8.21 Nebenbefund 1 und 1.8.40 Nebenbefund 4: die Einstellungsseite ruft `labor-rate-settings` und
  `labor-rate-calculation` parallel; auf einer frischen Datenbank legten beide `labor_rate_settings` bzw. die
  Gemeinkosten-Einstellung an, einer scheiterte am Primärschlüssel, die Seite zeigte `alert()`. Die Klicktests
  säten die Singletons deshalb vorab.
- 1.8.40 Nebenbefund 1: `freeze_contract()` und die Unterschrift rendern unter der Zeilensperre aus
  `_locked_contract()`; `ensure_default_layout()` und `get_or_create_general_settings()` committeten beim
  allerersten Rendern und gaben die Sperre frei.
- 1.8.8: der Stundenzettel musste `_entry_type_labels()` vor `list_entries()` aufrufen, weil ein Anlegen der
  Optionsgruppe committet und die geladenen Buchungen verfallen ließ.

Probe vor dem Umbau: der Rundgang aus `test_v326_monteur_datengrenze.py` als Admin auf einer frischen Datenbank
mit Listener -- 24 GET-Routen schrieben (alle über Grunddaten, dazu je Anlegen ein `audit_logs`-Eintrag).

## Umsetzung

- **`app/grunddaten.py::anlegen(db)`** legt alles Fehlende an, rührt Vorhandenes nie an, committet einmal am
  Ende. Läuft beim Start in `app/main.py` (in jeder Umgebung, auch `ERP_ENV=production`), nach
  `ensure_existing_order_revisions()`. Scheitert es, startet die App nicht -- wie die übrigen Startschritte.
- **Sperre statt Wettlauf**: erster Schritt ist `_sperren()` -- `general_settings` id=1 anlegen (SAVEPOINT) und
  `SELECT ... FOR UPDATE`. Ein zweiter, gleichzeitig startender Arbeitsprozess (`gunicorn -w 2`) wartet dort, bis
  der erste committet hat, und findet dann alles vor. Damit entstehen auch die Sätze ohne UNIQUE (Zahlungs­
  bedingungen, Steuerschlüssel, Mahnstufen, Layout) und die globalen Kalkulationsgrundlagen (NULL ist in UNIQUE
  nie gleich) nicht doppelt -- ohne Migration für neue Constraints. Unter SQLite `BEGIN IMMEDIATE` (siehe unten).
- **Schritte committen nicht**: die `ensure_default_*()`-Funktionen der Fachmodule sind nur noch Schritte von
  `anlegen()` (flush), ein Commit gäbe die Sperre frei. Der SAVEPOINT je Schritt (1.4.6) bleibt als zweite
  Absicherung (`test_v281_self_seeding_race_safety.py` prüft ihn weiter, jetzt mit Commit der zweiten Sitzung).
- **Lesefunktionen lesen nur**: Singletons über `einzelzeile(db, Modell)`; fehlt die Zeile, `GrunddatenFehlen`
  (RuntimeError) statt Anlegen. Die Gemeinkosten-Einstellung übernimmt die alten "jährlichen Gemeinkosten"
  (<=0.6.8) jetzt beim Anlegen in `anlegen()`, nicht mehr beim ersten Lesen.
- **Neue Einstellung oder neuer Standardsatz**: in `grunddaten.py` eintragen (`_einzelzeilen()` bzw. ein Schritt in
  `anlegen()`), nie in der Lesefunktion anlegen. `test_v345_grunddaten.py::test_jede_einzelzeilen_tabelle_ist_in_grunddaten_eingetragen`
  findet jede Tabelle, deren `id` den Vorgabewert 1 hat.
- **Tests**: `tests/conftest.py` legt nach jedem `create_all()` die Grunddaten an (`after_create` auf
  `Base.metadata`) -- jede Testdatenbank sieht aus wie eine Installation nach dem Start. Eine Datenbank ohne
  Grunddaten (Migrationstests mit genauem Vorzustand, `anlegen()` selbst): `with ohne_grunddaten():` aus
  `tests/grunddaten_schalter.py` (eigenes Modul, ein Import aus conftest lüde es doppelt).
- **Klicktests**: `cdp_klicktest.py` startet die Instanz über `app.main`, also mit `anlegen()`. Das Vorab-Säen der
  Singletons in `klicktest_vertragsgrundlage.py` und `klicktest_behinderungsanzeige_versand.py` ist entfernt.
- **Punkt 4**: der Docstring von `_entry_type_labels()` (`app/time_backoffice.py`) sagt nur noch "einmal je Lauf";
  die Reihenfolge-Regel ist weg, `test_v312` prüft jetzt, dass der Lauf nichts schreibt.

### Fund beim Test mit zwei Prozessen: SAVEPOINT unter SQLite

Der erste Lauf von `test_zwei_gleichzeitige_starts_in_produktion_sqlite` ergab die Zahlungsbedingungen doppelt
(6 statt 3), PostgreSQL war richtig. Ursache: pysqlite beginnt die Transaktion erst vor der ersten Änderung. Ein
SAVEPOINT davor ist unter SQLite selbst die Transaktion, und sein RELEASE committet -- die Sperre hielt nicht.
`_sperren()` öffnet die Transaktion unter SQLite deshalb mit `BEGIN IMMEDIATE` (Schreibsperre der Datenbank, der
zweite Prozess wartet bis zum busy timeout von pysqlite, 5 Sekunden). Dasselbe Verhalten betrifft jeden anderen
SAVEPOINT im Projekt, der unter SQLite vor der ersten Änderung einer Transaktion steht -- siehe Nebenbefunde.

## Liste der umgestellten Stellen (Punkt 1)

**Singletons** -- Lesefunktion umbenannt `get_or_create_*` → `load_*` (alle Aufrufer in `app/`, `tests/`,
`scripts/`, 375 Ersetzungen in 92 Dateien), angelegt in `grunddaten._einzelzeilen()`:

| Tabelle | vorher | jetzt | Aufrufstellen in `app/` |
|---|---|---|---|
| `general_settings` (Sperrzeile) | `settings.get_or_create_general_settings` | `load_general_settings` | 31 |
| `ai_settings` | `ai_settings.get_or_create_ai_settings` | `load_ai_settings` | 4 |
| `smtp_settings` | `email_sending.get_or_create_smtp_settings` | `load_smtp_settings` | 14 |
| `incoming_invoice_settings` | `incoming_invoices.get_or_create_incoming_invoice_settings` | `load_incoming_invoice_settings` | 11 |
| `labor_rate_settings` | `labor_rate.get_or_create_labor_rate_settings` | `load_labor_rate_settings` | 9 |
| `labor_rate_overhead_settings` (Gemeinkosten) | `labor_rate.get_or_create_overhead_settings(db, base)` | `load_overhead_settings(db)` | 6 |
| `maintenance_settings` | `maintenance_contracts.get_or_create_maintenance_settings` | `load_maintenance_settings` | 19 |
| `mobile_settings` | `mobile_settings.get_or_create_mobile_settings` | `load_mobile_settings` | 3 |
| `operational_asset_settings` | `operational_assets.get_or_create_operational_asset_settings` | `load_operational_asset_settings` | 12 |
| `outlook_sync_settings` | `outlook_calendar_sync.get_or_create_outlook_sync_settings` | `load_outlook_sync_settings` | 3 |
| `planning_settings` | `planning.get_or_create_planning_settings` | `load_planning_settings` | 8 |
| `planning_region_settings` | `planning.get_or_create_region_settings` | `load_region_settings` | 6 |
| `productive_hours_settings` | `productive_hours.get_or_create_productive_hours_settings` | `load_productive_hours_settings` | 3 |
| `recurring_cost_settings` | `recurring_costs.get_or_create_recurring_cost_settings` | `load_recurring_cost_settings` | 9 |
| `task_settings` | `tasks.get_or_create_task_settings` | `load_task_settings` | 4 |
| `time_tracking_settings` | `time_backoffice.get_or_create_time_settings` | `load_time_settings` | 9 |
| `time_backoffice_advanced_settings` | `work_time_models.get_or_create_advanced_settings` (flush) | `load_advanced_settings` | 11 |
| `calculation_settings` (global, `catalog_id IS NULL`) | `calculation.get_or_create_settings` | `load_calculation_settings` | 12 |

**Standardsätze** -- `ensure_default_*()` ist nur noch Schritt von `anlegen()` (flush); aus diesen Funktionen
entfernt:

| Satz | Aufruf entfernt aus |
|---|---|
| Optionsgruppen (`ensure_default_option_groups`) | `option_settings.get_option_group()`, Router `settings`: Liste (jetzt `load_option_groups()`), Gruppe, Option anlegen/ändern/löschen; `routers/projects._ensure_project_profile()` |
| Dokumentkategorien | `document_categories.list_categories()`, `resolve_category_id()`, `routers/field_view` Kategorien |
| Mitarbeiterfunktionen | `employees._function_for_legacy_employee()`, `ensure_employee_profiles()`, `routers/employees.create_employee()`, `routers/settings` Liste (jetzt `load_employee_functions()`) |
| Zahlungsbedingungen | `routers/payment_terms` Liste und Anlegen, `routers/invoices` alle vier Rechnungsarten |
| Steuerschlüssel | `routers/tax_keys` Liste und Anlegen |
| Mahnstufen | `routers/reminders`: Stufen, überfällige Rechnungen, Entwürfe automatisch, Mahnstatus je Rechnung |
| Pipeline-Spalten | `project_pipeline_columns`: `list_columns`, `default_pipeline_column_id`, anlegen, ändern, sortieren, löschen |
| Aufgaben-Spalten | `task_columns`: `list_columns`, anlegen, ändern, sortieren, löschen; `tasks._columns_by_key()` |
| Nummernkreise | `routers/settings` Liste (jetzt `load_sequences()`); `preview_number`/`issue_number`/`update_sequence` lesen über `load_sequence()` statt `get_or_create_sequence()` |
| Arbeitszeitmodelle | `work_time_models`: `list_models`, `employee_model`, `employee_model_rows`; `main.py` (jetzt in `anlegen()`) |
| Layout-Bausteine (geteilter Satz) | PDF-Rahmen `render_framed_pdf()`, `routers/document_layout` GET -- jetzt `load_layout()` |
| Seitenränder (geteilter Satz) | `get_margins()` (PDF-Rahmen, Router) -- liest nur, `ensure_default_margins(db)` legt beide Seitentypen an |

## Dauerhafter Test (Punkt 2)

`tests/test_v326_monteur_datengrenze.py`: `_durchlauf()` hängt einen `before_cursor_execute`-Listener an die
Engine und merkt je GET-Route die Tabellen, in die geschrieben wird (INSERT/UPDATE/DELETE auf Cursor-Ebene, auch
was danach zurückgerollt wird). Neu ein zweiter Rundgang **als Admin** (`durchlauf_admin`): der Monteur bekommt
die meisten Endpunkte mit 403, bevor die Datenbank gefragt wird -- `labor-rate-settings` etwa hätte der
Monteur-Rundgang nie getroffen. Die Admin-Welt ist die Monteurswelt plus Admin-Konto, Angebot (wie
`POST /api/projects/{id}/quotes` es anlegt), Schlussrechnung, Aufgabe, Kontakt mit Beteiligung.
`test_kein_get_schreibt` vergleicht mit `SCHREIBT_BEKANNT` (Route -> Tabellen, Grund): ein neuer schreibender GET
färbt rot, ebenso ein Eintrag, der nicht mehr oder anders schreibt. `test_admin_durchlauf_ohne_serverfehler`
sorgt dafür, dass kein 500 einen Aufruf vor dem Schreiben abbricht. Stand 1.8.42: zwei Einträge (Nebenbefunde 1
und 2).

## Gegenproben (Punkt 3)

- **Frische PostgreSQL-Datenbank, gleichzeitige Starts und Erstaufrufe** (`test_v345_grunddaten.py`, opt-in über
  `ERP_TEST_POSTGRES_URL`, Wegwerf-Schema): zwei Sitzungen treffen sich vor `anlegen()` (Barriere) -- keine
  Ausnahme, kein Satz doppelt; zwei Prozesse importieren `app.main` mit `ERP_ENV=production` gleichzeitig (nach
  dem Laden der Fachmodule über Bereit-/Los-Dateien synchronisiert) -- beide Rückgabe 0, nichts doppelt; danach
  je der 23 GET-Endpunkte, die bis 1.8.41 beim ersten Aufruf anlegten, zwei Aufrufe gleichzeitig (46 Threads,
  eigene Verbindung je Anfrage) -- alle 200, kein Schreibzugriff. Dazu einmalig (Skript im Scratchpad) dasselbe auf
  einer Datenbank aus `alembic upgrade head` (Kopf `0181f8f79a6b`, `alembic current` = head): vor dem Start
  nur, was Migrationen säen (8 Dokumentkategorien, 4 Pipeline-, 3 Aufgaben-Spalten, `task_settings`), nach zwei
  gleichzeitigen Produktionsstarts alles genau einmal, 200 Protokolleinträge "System angelegt", Erstaufrufe alle
  200 ohne Schreiben, Vertrag festgeschrieben und unterschrieben.
- **SQLite**: dieselben zwei Produktionsstarts (Datei-Datenbank) -- vor `BEGIN IMMEDIATE` Zahlungsbedingungen
  doppelt (6 statt 3), danach dreimal hintereinander richtig.
- **`klicktest_vertragsgrundlage.py`** ohne Vorab-Säen dreimal hintereinander 30/30; ebenso grün
  `klicktest_vertrag_festschreiben.py` 40/40, `klicktest_vertrag_unterschrift.py` 43/43,
  `klicktest_behinderungsanzeige_versand.py` 41/41 (Vorab-Säen entfernt), dazu die drei durch die Umbenennung
  berührten `klicktest_angebot_interne_notiz.py` 7/7, `klicktest_teil_updates.py` 9/9,
  `klicktest_vertragsvorlagen.py` 36/36.
- **Vertrag rendern ohne Blockade**: `test_v345` beobachtet `render_contract_pdf()` und
  `render_signature_sheet_pdf()` beim Festschreiben und Unterschreiben -- kein Commit während des Renderns
  (SQLite und PostgreSQL), und gegen PostgreSQL bekommt eine zweite Verbindung die Vertragszeile danach mit
  `FOR UPDATE NOWAIT` nicht (`LockNotAvailable`): die Sperre ist gehalten, das Rendern läuft trotzdem durch.
- **Listener-Test**: drei Gegenproben, jede rot -- ein Lesepfad flusht wieder (Gemeinkosten-Einstellung: drei Routen
  gemeldet), ein Eintrag fehlt in `SCHREIBT_BEKANNT`, ein veralteter steht drin; unverändert grün.

## Testlaufzeit

`anlegen()` kostet auf einer In-Memory-Datenbank rund 70 ms (435 Anweisungen). Die Suite legt über 2500
Datenbanken an -- je Datenbank `anlegen()` hätte rund zwei Minuten gekostet (Teilmenge `test_v1*`: 39 s vorher,
62 s mit `anlegen()` je Datenbank). Der Hook übernimmt unter SQLite deshalb die Zeilen einer Vorlage, die
`anlegen()` einmal je Jahr erzeugt (44 s); `test_vorlage_im_test_hook_gleicht_einem_echten_anlegen` vergleicht
den Inhalt (ohne Zeitstempel) mit einem echten `anlegen()`. PostgreSQL-Tests und Datenbanken mit schon
vorhandenen Grunddaten laufen über `anlegen()` selbst.

## Nebenbefunde (nur gemeldet)

1. **`GET /api/projects/{id}/quotes` legt je Angebot Meta und Positionslayout an** (`ensure_quote_structure()`,
   `quote_document_meta`, `quote_item_layouts`): `POST /api/projects/{id}/quotes` legt sie nicht an, also schreibt
   der erste Lesezugriff auf jedes neue Angebot. Je Datensatz, keine Grunddaten -- in `SCHREIBT_BEKANNT`.
2. **`GET /api/settings/number-sequences` schreibt** (`preview_number()`): gleicht `next_value` mit schon
   vergebenen Nummern ab und setzt im neuen Jahr zurück, flusht (UPDATE samt Protokolleintrag), committet nie.
   Unter PostgreSQL sperrt das die Nummernkreis-Zeile für die Dauer der Anfrage. In `SCHREIBT_BEKANNT`.
3. **Weitere Anleger je Datensatz in GET-Pfaden, die der Rundgang nicht auslöst** (seine Testdaten sind
   vollständig): `GET /api/customers` und `/api/customers/{id}` (`ensure_customer_profile(s)`), `GET /api/employees`,
   `/caseworkers`, `/{id}` (`ensure_employee_profiles`), `GET /api/orders/{id}/work-preparation`
   (`ensure_preparation`; ein Auftrag aus dem Beauftragen hat noch keine Arbeitsvorbereitung),
   `GET /api/quotes/{id}/items/{item_id}/calculation` (`ensure_quote_item_calculation`). Die
   Erinnerungs-Prüfungen `check_due_*` laufen per POST, kein Fall.
4. **SAVEPOINT unter SQLite committet** (siehe oben): jeder `begin_nested()`, der vor der ersten Änderung einer
   Transaktion steht, ist unter pysqlite selbst die Transaktion; sein RELEASE committet alles davor. Betrifft nur
   SQLite (Entwicklung, Tests), PostgreSQL nicht. In `anlegen()` behoben, an anderen Stellen nicht geprüft.
5. **Ein Mitarbeiter mit ungültiger Gruppe legt die Mitarbeiterliste lahm**: `EmployeeOut` lehnt eine
   `employee_group` außer `gewerblich`/`kaufmaennisch` ab, `GET /api/employees` antwortet dann allen Büro-Rollen
   mit 500. Gefunden mit den Testdaten von `test_v326` ("angestellt", korrigiert).
6. **`load_calculation_settings()` prüft bei jedem Aufruf per Inspector, ob `calculation_settings.catalog_id`
   existiert** (Migration 1.0.14): auf `:memory:`-SQLite verwirft das geflushte, nicht committete Änderungen
   (1.8.42 in `test_v052` erneut gesehen, Test umgestellt). Seit dem Start mit `anlegen()` fiele eine fehlende
   Spalte ohnehin beim Start auf -- die Prüfung je Aufruf wäre entbehrlich.
