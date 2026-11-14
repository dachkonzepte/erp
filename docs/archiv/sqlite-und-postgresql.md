# SQLite gegen PostgreSQL (Befund 13.11.2026, Runde V1 ab 1.9.338)

Die Suite läuft unter SQLite, live läuft PostgreSQL. SQLite nimmt manches still an, was PostgreSQL ablehnt -- Anlass war der Fehler aus 1.9.328
(eine zu lange Aktion in `audit_logs.action`, behoben in 1.9.332). Der Befund auf 0e9de07 (1.9.337) ließ die volle Suite einmal gegen PostgreSQL
laufen; sein Bericht liegt nur lokal (`bildgrundlage/befund_sqlite_postgres_0e9de07.txt`, nicht in Git). Hier stehen die Ergebnisse ohne Einzelwerte,
die Entscheidungen und die Umsetzung.

## Befund (13.11.2026, auf 0e9de07)

- Volle Suite gegen PostgreSQL (je Testdatenbank ein Wegwerf-Schema der Spielwiese, ein pytest-Plugin außerhalb des Projekts): 9 691 Tests, 9 567 grün,
  122 rot, 4 übersprungen; dazu 1 754 Tests, die nur am Fremdschlüssel `orders_source_quote_id_fkey` scheiterten (Testhelfer legten einen Auftrag ohne
  sein Angebot an) -- für den Lauf herausgenommen.
- Fünf echte Fehler im Code (11 Tests), live je 500 ohne Änderung: **E1** Projekt löschen, wenn das Angebot Positionen in LV-Titeln hat
  (`app/projects.py::delete_project()`: LV-Titel vor den Platzierungen gelöscht); **E2** Adressimport rückgängig machen
  (`app/address_import.py::revert_import_run()`: Kunden vor den Importzeilen gelöscht, Autoflush); **E3** Entwurf eines Einsatzberichts löschen, wenn ein
  Befund eine Folgeaufgabe hat (`app/service_reports.py::delete_report()`: Aufgabe vor dem Befund gelöscht); **E4** Leistungskatalog erneut importieren,
  wenn eine Angebotskalkulation Material daraus übernommen hat (`app/service.py::persist_project()`: `service.materials.clear()` trotz
  `quote_item_material_calculations.source_material_id`); **E5** Materialbedarf der Arbeitsvorbereitung neu aufbauen -- nach jeder Positionsänderung und
  dem Abgleich --, sobald einem Material ein Lieferschein zugeordnet ist (`app/work_preparation.py::refresh_preparation_materials()`: Zuordnungen und
  Materialzeilen im selben Flush). Gemeinsame Ursache: Löschen in der falschen Reihenfolge zwischen Tabellen ohne ORM-Beziehung (Regel 6), und die Suite
  prüfte keinen Fremdschlüssel (`app/database.py` setzt `PRAGMA foreign_keys` bewusst nicht). Dazu der bekannte Fall „Benutzer löschen“ (seit 1.8.13).
- Die übrigen 111 roten Tests waren Testartefakte: angenommenes Konto ohne `AppUser` (72), erfundene IDs (12 + 6 in Migrationsproben), Fehlertext von
  SQLite (9), PRAGMA (3), Migrationsprobe auf einem Schema aus `create_all()` (2), SQLite-Mittel (2), `1/0` statt `true/false` (1), wiederverwendete ID (1),
  Werkzeug des Befunds (3 + 1 Prozess).
- Gegenprobe: SQLite mit `PRAGMA foreign_keys=ON` (volle Suite) findet dieselbe Art; E3–E5 dort von früheren Fehlern in den Testdaten verdeckt.
- Unterschiede, die kein Test berührte (Proben über echte Routen): zu langer Text 500 statt 422 (auch der Adressimport scheitert an einer Zelle ganz);
  Zahlenbereich und Rundung in Numeric; Suche mit Umlauten; Sortierung nach Namen (Kollation), leere Werte beim Sortieren, Reihenfolge ohne ORDER BY;
  Backslash in der Suche; Date-Spalte gegen Zeitpunkt.
- Zeit: SQLite 12:55 min. PostgreSQL mit einem neuen Schema je Testdatenbank trug die Instanz auf diesem Rechner nicht (rund 1 100 Dateien je Schema,
  1,6 Mio. Dateien im Datenordner, Checkpoint bis 45 min); in drei Teilen mit abgeschaltetem fsync 25, 35 und 36 min, hochgerechnet 2,5–3,5 h.
  Wiederverwenden eines Schemas mit DELETE: 0,4 s statt 2,2–3,0 s, keine neuen Dateien.
- Vorschlag: V1 Fremdschlüssel in der Test-SQLite, V2 statische Wächter (Länge, Zahlenbereich, Reihenfolge, Suchmuster), V3 Rundgang gegen PostgreSQL im
  Endlauf, V4 volle Suite gegen PostgreSQL nicht routinemäßig.

## Entscheidungen (Tobias, 14.11.2026)

- **F1** ja: E1–E5 in der Runde V1, zusammen mit V1; bei E5 die Lieferanten-Zuordnungen gleich mitprüfen.
- **F2** ja (V1).
- **F3** ja, eigene Runde nach V1 (V2).
- **F4** ja, eigene Runde nach V2 (V3).
- **F5** nein, die volle Suite gegen PostgreSQL nicht routinemäßig (V4).
- **F6** Sortierung nach Namen wie im Telefonbuch: ohne Groß- und Kleinschreibung, Umlaut beim Grundbuchstaben -- unter SQLite und PostgreSQL gleich,
  unabhängig von der Kollation des Servers. Kommt mit V2.
- **F7** Zu lange Zelle im Adressimport: die Zeile ablehnen, nicht kürzen; die übrigen Zeilen gehen durch; eine Liste nennt Zeile, Feld und Grenze.
  Kommt mit V2.

## Betreiberprüfungen (Tobias, 14.11.2026)

- **B1** Kollation der Server-Datenbank: `C.UTF-8` -- sortiert binär wie SQLite. F6 (Telefonbuch-Sortierung im Programm, unabhängig von der Kollation)
  gilt damit für V2 ohne Einschränkung.
- **B2** Dienst `erp`, Protokoll seit 01.09.2026 (21 353 Zeilen): 0 Treffer für `ForeignKeyViolation`, `StringDataRightTruncation`,
  `NumericValueOutOfRange`. E1–E5 und zu lange Texte kamen live nicht vor; keine Daten zu reparieren.

## Runde V1: Fremdschlüssel in der Test-SQLite (ab 1.9.338)

Vorgabe Tobias (14.11.2026): vorweg (keine Version) die Vorprobe September/Oktober (Muster) und die lokale echte Oktober-Datei einmal gegen ein
Wegwerf-Schema der Spielwiese erzeugen und Byte für Byte mit SQLite vergleichen (wegen der Rundung in Numeric, Probe P6b des Befunds); dann je Punkt eine
Version: **1** Testdaten aufräumen (die Helfer mit Auftrag ohne Angebot, das angenommene Konto als echter `AppUser`, die Einzeltests, N1), **2**
`PRAGMA foreign_keys=ON` für jede SQLite-Verbindung der Tests mit Wächter, **3** E1–E5 beheben, je mit einem Test, der vorher unter dem PRAGMA rot war,
dazu „Benutzer löschen“ mit verständlicher Meldung statt 500. Die Suite bleibt unter SQLite.

### Vorweg: die Lohndatei unter PostgreSQL (keine Version)

`scripts/vorprobe_time4.py` unverändert, einmal wie gewohnt (Wegwerf-SQLite) und einmal über eine Kopie im Scratchpad, die nur `DATABASE_URL` auf ein
Wegwerf-Schema der Spielwiese setzt (und dort `orders_source_quote_id_fkey` entfernt, weil die Vorprobe ihren Auftrag ohne Angebot anlegt): September
und Oktober 2026 (Muster, wie 1.9.228) und die lokale Oktober-Datei aus echten Buchungen (`bildgrundlage/lohn_echt`, keine Werte hier). Ergebnis: alle
drei Lohndateien unter PostgreSQL Byte für Byte gleich wie unter SQLite (SHA-256 gleich), die Ausgabe von `pruefe_lohndatei.py` ebenso. Die Rundung in
Numeric (P6b) trifft die Lohndatei nicht: Stunden werden vor dem Speichern über `round_hours()` gerundet (Regel 19), und `arbeit_des_tags()` rundet je Tag.

### Umsetzung 1.9.338: Testdaten ohne erfundene Eltern (Punkt 1)

- **Aufträge mit Angebot.** Neu `tests/quellangebot.py::quell_angebot(db, project_id, order_number)`: legt das Quell-Angebot an („Q-<Auftragsnummer>“,
  Status „beauftragt“, im Projekt des Auftrags) und gibt seine ID. Über den AST umgestellt: jede `Order(...)` unter `tests/` mit erfundener
  `source_quote_id` (1, 2, `int(suffix)`, 9101 …) -- 42 Stellen in 32 Dateien, darunter die Helfer `make_order_with_item` (v133),
  `make_sent_overdue_invoice` (v153), `world` (v305), `_order` (v264), `_build_extra_order` (v214, ohne den Parameter `source_quote_id`). Der Notbehelf
  „Angebots-IDs auf 900001/900002 umsetzen“ in v372, v373 (Fixture `echte_angebots_ids`) und v374 ist weg -- er verhinderte die Kollision erfundener mit
  echten Angebots-IDs. Die Klicktests (`scripts/klicktest_*.py`, 40 Seeds mit erfundener ID) bleiben: sie laufen gegen die App, nicht unter `tests/`.
- **Das angenommene Konto.** `router_test_client` legt ein Konto mit ID (`user_id=…`) als echten `AppUser` an („test-konto-<id>“, Rolle und Mitarbeiter
  wie angemeldet), wenn es noch keins gibt; ohne ID wie bisher kein Konto. Damit zeigen `requested_by_user_id`, `reviewed_by_user_id` und
  `owner_user_id` auf ein Konto (vorher 72 rote Tests unter PostgreSQL).
- **Einzeltests.** Erfundene Eltern echt angelegt: Mitarbeiter einer übernommenen Aufgabe (v283, v293), Vorlage und Fassung einer Checkliste (v418),
  Wartungsvertrag (v679, v688), Konto eines Termins (v535). Migrationsproben setzen ihre Eltern über den neuen Helfer `tests/migrationsbestand.py`
  (`auftrag()`, `dokument()`, `vertrag()`, `fassung()`, `abnahme()`, `mangel()`, `checkliste()`, `kontakt()` -- je genau ein Datensatz, damit keine Zählung
  einer Probe wackelt) und die IDs als Parameter ein: v336, v337, v338, v349 (zwei Proben), v350, v351, v357, v361 -- die beiden letzten ohne
  `PRAGMA foreign_keys=OFF`, v361 läuft damit auch unter PostgreSQL. Zustände, die ein Fremdschlüssel verhindert, stehen nicht mehr in der Datenbank:
  v254 prüft die Verteidigung in `resolve_account_display()` mit einem ungespeicherten Konto, v222 einen Bericht ohne Vertragsverweis. SQLite-Fassungen:
  v380 erkennt die verletzte Nummer an „Tabelle.Spalte“ (SQLite) oder dem Namen der Bedingung (PostgreSQL), v402 verlangt die wieder vergebene ID nur
  unter SQLite, v539 zählt ohne `group_concat`.
- **N1.** `app/materials.py` ohne `_service_materials_has_material_id_column()` und `_materials_table_has_catalog_column()` (Reste aus 1.0.25/1.0.30,
  die Migrationen sind überall durch); `persist_project()` legt immer über den Materialkatalog an, `backfill_existing_service_materials()` gibt nie mehr -1,
  der Hinweis dazu in `app/main.py` ist weg. In der Test-SQLite (eine Verbindung) rollte die Prüfung über die Engine die Transaktion des Imports zurück --
  danach fehlte der Importlauf, die Leistungen trugen seine ID (in der Suite mit dem PRAGMA 371 rote Tests).
- **Bewusst nicht geändert:** v266 und v286 bauen eigene Tabellen mit `INTEGER PRIMARY KEY` und vergeben IDs von Hand -- unter PostgreSQL bräuchten sie
  Sequenzen, das ist mehr als Testdaten aufräumen; sie bleiben Proben nur für SQLite. v335, v336 und v349 rufen `downgrade()` einer alten Migration auf
  einem Schema aus `create_all()`; PostgreSQL verweigert dort `DROP TABLE`, weil spätere Tabellen daran hängen (in der echten Kette wären sie vorher weg)
  -- kein Fehler der Migration, die Proben bleiben SQLite. v252 und v603 waren Artefakte des Werkzeugs.
- Geprüft: die volle Suite mit `PRAGMA foreign_keys=ON` (Werkzeug des Befunds, außerhalb des Projekts) danach 16 rot + 5 Fehler statt 2 217, davon 11
  E1–E5; der Rest ist in dieser Version behoben, nur v325 bleibt für 1.9.339 (siehe dort). Die 149 unter PostgreSQL roten Tests des Befunds (Einzelfälle
  und 40 Stichproben am Quell-Angebot) gezielt gegen PostgreSQL: 141 grün, rot nur v301 (PRAGMA, 1.9.339), v214 (E3), v266/v286 und v335/v336/v349 (oben).
- Nebenbei: die Systemkataloge der Spielwiese waren nach dem Befund aufgebläht (`pg_attribute` 497 MB bei 24 000 lebenden Zeilen, Tausende angelegte
  und gelöschte Schemas) -- `VACUUM FULL` auf die Kataloge, danach 33 MB für die ganze Datenbank.

#### Festlegungen 1.9.338 (Bitte bestätigen)

1. Ein Auftrag in Testdaten unter `tests/` hat sein echtes Angebot (`tests/quellangebot.py::quell_angebot()`, „Q-<Auftragsnummer>“, Status „beauftragt“,
   im Projekt des Auftrags); kein `Order(...)` unter `tests/` setzt eine erfundene `source_quote_id` (Wächter über den AST).
2. `router_test_client` legt ein Konto mit ID als echten `AppUser` an, wenn es noch keins gibt; ohne ID kein Konto.
3. Eine Migrationsprobe legt die Eltern ihres Bestands echt an (`tests/migrationsbestand.py`, je Funktion genau ein Datensatz) und setzt die IDs als
   Parameter; sie schaltet die Fremdschlüssel nicht ab.
4. Ein Zustand, den ein Fremdschlüssel verhindert, wird nicht in der Datenbank nachgestellt; eine Verteidigung im Code dafür prüft ein Test mit einem
   ungespeicherten Objekt.
5. Prüfungen, die nur unter SQLite stimmten, gelten für beide Datenbanken (Fehlertext, wiederverwendete ID, Standard-SQL); Proben mit eigenem DDL nur für
   SQLite und Migrationsproben auf `create_all()` bleiben SQLite (oben).
6. Die Spaltenprüfungen aus 1.0.25/1.0.30 in `app/materials.py` entfallen ersatzlos; `backfill_existing_service_materials()` gibt die Zahl der geänderten
   Zeilen, nie -1.

#### Tests und Prüfung 1.9.338

Neu `tests/test_v738_testdaten_ohne_erfundene_eltern.py` (4 Tests): Auftrag mit Angebot, Wächter gegen erfundene Quell-Angebote, Konto des
`router_test_client`, der Leistungsimport behält seinen Importlauf (N1). Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
`test_v125_materials::test_backfill_returns_minus_one_when_migration_not_yet_applied` (-1 ohne die Spalte) -> entfällt mit der Prüfung;
`test_v222::test_sign_report_with_flag_but_deleted_contract_does_not_error` (Vertragsverweis 999999) -> Vertragsverweis leer, Soll gleich;
`test_v254::test_resolve_account_display_falls_back_…` (gespeichertes Konto mit Mitarbeiter 999999) -> ungespeichertes Konto, Soll gleich;
`test_v380` (drei Prüfungen auf „Tabelle.Spalte“) -> „Tabelle.Spalte“ oder Name der Bedingung; `test_v402::test_benutzer_loeschen_nimmt_seine_sitzungen_mit`
(gleiche ID) -> gleiche ID nur unter SQLite; v283, v293 (Mitarbeiter 1) -> der angelegte Mitarbeiter; alle übrigen nur im Aufbau (echte Eltern statt
erfundener IDs), Soll gleich. Gegenproben: `docs/archiv/gegenproben-v1-fremdschluessel.md`.

### Umsetzung 1.9.339: PRAGMA foreign_keys=ON für jede SQLite-Verbindung der Tests (Punkt 2)

- `tests/conftest.py` meldet am Ereignis `connect` der Klasse `Engine` an: jede neue SQLite-Verbindung des Testprozesses bekommt
  `PRAGMA foreign_keys=ON` -- auch die Engine aus `app.database`, die vor `conftest` entsteht, `wegwerf_engine()`, `db_session`, `threaded_db_session`,
  Dateien und jede eigene `create_engine()` eines Tests. Kindprozesse (alembic, uvicorn) und die Klicktests haben es nicht; `app/database.py` bleibt ohne
  PRAGMA (lokale SQLite mit Altbestand), live prüft PostgreSQL.
- Wächter `tests/test_v739_fremdschluessel_sqlite.py`: jede dieser Arten hat die Prüfung an, ein Verstoß scheitert sofort, und kein Test schaltet sie
  ab oder selbst ein -- gesucht im Code ohne Kommentare und Docstrings (dort darf „PRAGMA foreign_keys=…“ erklärt werden). Einzige Ausnahme
  (`AUSNAHMEN`, darf nur kürzer werden): v325, die Migration der Vertragsgrundlage baut unter SQLite `customers` im Batch-Modus neu, und SQLite verweigert
  das Löschen der alten Tabelle, solange Projekte darauf zeigen; PostgreSQL ändert die Spalte ohne Neuaufbau. `_run()` dort schaltet die Prüfung nur für
  die Dauer der Migration ab und stellt sie danach wie vorher (der Test prüft das).
- v301 schaltete die Prüfung selbst ein (seit 1.7.11, „erst nach dem Aufbau, weil der Auftrags-Helfer ein Angebot nur vortäuscht“); jetzt stellt er nur
  fest, dass sie an ist.
- E1–E5 scheitern unter dem PRAGMA wie live. Bis zu ihrer Behebung (Punkt 3) stehen die 11 Tests in `FREMDSCHLUESSEL_BEKANNT` (`tests/conftest.py`):
  erwartet rot, streng (wird einer grün, scheitert der Lauf) und nur mit `IntegrityError`.
- Laufzeit: die volle Suite vorher (1.9.338) 11:22 min, mit dem PRAGMA (1.9.339) 11:19 min -- siehe 1.9.340.

#### Festlegungen 1.9.339 (Bitte bestätigen)

1. Jede SQLite-Verbindung im Testprozess prüft Fremdschlüssel (`PRAGMA foreign_keys=ON` über das Ereignis `connect` in `tests/conftest.py`);
   Kindprozesse und Klicktests nicht, `app/database.py` bleibt ohne PRAGMA.
2. Kein Test schaltet die Prüfung ab oder selbst ein; eine Ausnahme steht mit Grund in `AUSNAHMEN` von `tests/test_v739_fremdschluessel_sqlite.py` (darf
   nur kürzer werden) und gilt nur für die Dauer der Stelle, die sie braucht -- heute v325 (Migration im Batch-Modus).
3. Ein Fehler, den das PRAGMA findet und der noch nicht behoben ist, steht bis zur Behebung in `FREMDSCHLUESSEL_BEKANNT` (`tests/conftest.py`): erwartet
   rot, streng, nur mit `IntegrityError`. Die Liste darf nur kürzer werden; mit Punkt 3 ist sie leer und weg.

#### Tests und Prüfung 1.9.339

Neu `tests/test_v739_fremdschluessel_sqlite.py` (8 Tests). Angepasste Erwartungen (Regel 28): `test_v301` -- schaltet die Prüfung nicht mehr selbst ein,
stellt nur fest, dass sie an ist (Soll gleich); `test_v325::test_migration_downgrade_removes_everything_and_refuses_when_data_would_be_lost` -- Migration
ohne Prüfung, danach wieder mit (neue Prüfung am Ende); die 11 Tests von E1–E5 erwartet rot (xfail streng) bis Punkt 3. Gegenproben:
`docs/archiv/gegenproben-v1-fremdschluessel.md`.

### Umsetzung 1.9.340: E1–E5 behoben, „Benutzer löschen“ mit Meldung (Punkt 3)

Gemeinsames Muster: zwischen zwei Tabellen ohne ORM-Beziehung (Regel 6) zuerst löschen oder lösen, was zeigt, und das in einem eigenen Flush -- der
Unit of Work von SQLAlchemy ordnet DELETEs nicht über Mapper ohne Beziehung, die Reihenfolge im selben Flush ist Zufall.

- **E1** `app/projects.py::delete_project()`: die Platzierungen der Positionen (`quote_item_layouts`) vor den LV-Titeln (`quote_sections`).
- **E2** `app/address_import.py::revert_import_run()`: erst die Zeilen des Laufs (`imported_addresses` zeigen auf Kunde, Lieferant, Objekt), Flush,
  dann Kunden und Lieferanten.
- **E3** `app/service_reports.py::delete_report()`: erst der Bericht (mit ihm gehen die Befunde, deren `follow_up_task_id` auf die Aufgaben zeigt),
  Flush, dann die Aufgaben.
- **E4** `app/service.py::persist_project()`: vor dem Ersetzen der Materialien einer Leistung verliert jede Angebotskalkulation, die Material daraus
  übernommen hat, nur den Verweis (`quote_item_material_calculations.source_material_id` leer, über das ORM -- die Änderungshistorie hält es fest);
  ihre Werte (Name, Menge, Preis) bleiben, sie sind in der Kalkulation eingefroren.
- **E5** `app/work_preparation.py::refresh_preparation_materials()`: die Zuordnungen (Lieferant und Lieferschein) in einem eigenen Flush vor den
  Materialzeilen. **Lieferanten-Zuordnungen (F1) geprüft:** allein scheiterten sie nicht -- im selben Flush ging ihr DELETE zufällig vor dem der
  Materialzeilen hinaus, das der Lieferschein-Zuordnungen danach; jetzt sind beide durch den Flush abgesichert, `test_v740` hält die Lieferanten-
  Zuordnung allein fest.
- **Benutzer löschen** (P7, offen seit 1.8.13): neu `app/konto_loeschen.py`. Was zum Konto gehört, geht mit ihm (`MIT_DEM_KONTO`: Sitzungen,
  vertraute Geräte, Wiederherstellungscodes über die ORM-Kaskade, die Kacheln der Startseite hier gelöscht -- auch die scheiterten bisher unter
  PostgreSQL). Steht das Konto anderswo (`BEREICHE`: Aufgaben, Checklisten, Zeitbuchungen, Anträge, Kalendertermine … -- 12 Spalten), antwortet
  `DELETE /api/users/{id}` mit 409: „Das Konto wurde schon verwendet (Aufgaben, …) und lässt sich deshalb nicht löschen. Deaktiviere es stattdessen –
  dann kann es sich nicht mehr anmelden, und alles, was es angelegt hat, bleibt.“ Die Seite „Benutzer“ zeigt die Meldung wie jede andere. Jeder
  Fremdschlüssel auf `app_users` steht in genau einer der beiden Listen (Wächter); ein neuer kommt dort hinein.
- `FREMDSCHLUESSEL_BEKANNT` (1.9.339) ist leer und mit dem Hook aus `tests/conftest.py` entfernt; die 11 Tests von E1–E5 laufen wieder normal.
- Geprüft auch gegen PostgreSQL (Werkzeug des Befunds, Wegwerf-Schemas): `test_v740` und die Tests von E1–E5, 51 von 51 grün.
- **Laufzeit mit PRAGMA:** volle Suite 1.9.338 (ohne) 11:22 min, 1.9.339 (mit) 11:19 min -- kein messbarer Unterschied (16 Arbeitsprozesse, gleicher
  Rechner, je ein Lauf).

**Vorschlag (nicht gebaut): Deaktivieren statt Löschen.** Ein Konto, das gearbeitet hat, steht fast immer irgendwo (jede Zeitbuchung, jede Aufgabe);
Löschen geht dann nicht, Deaktivieren schon -- es beendet die Sitzungen (Regel 30), sperrt die Anmeldung und lässt Urheberschaft und Historie stehen.
Vorschlag: auf der Seite „Benutzer“ bei einem verwendeten Konto statt „Löschen“ gleich „Deaktivieren“ anbieten (der Server kennt die Bereiche schon,
`verwendungen()`), „Löschen“ nur für ein nie verwendetes Konto (Tippfehler beim Anlegen). Entscheidung bei Tobias.

**Neuer Fund E6 (nicht gebaut):** einen Wartungsvertrag löschen (`app/maintenance_contracts.py::delete_contract()`) scheitert unter Fremdschlüsseln,
sobald aus ihm ein Projekt entstanden ist (`project_profiles.source_maintenance_contract_id`) oder ein Berichtsentwurf auf ihn zeigt
(`service_reports.maintenance_contract_id`) -- live 500. Die Funktion sperrt nur bei einem unterschriebenen Bericht. Gefunden mit einer Probe
(SQLite mit PRAGMA): ohne beides gelöscht, mit Projekt aus dem Vertrag und mit Berichtsentwurf je `IntegrityError`; kein Test deckte den Weg ab.
Dasselbe Muster vermutlich bei `delete_contract_item()` (Verweise auf die Position). Vorschlag: wie E1–E5 die Verweise vorher lösen (Projekt-Profil und
Entwurf behalten, Verweis leer) oder wie beim unterschriebenen Bericht mit Grund ablehnen -- fachliche Entscheidung; der Rundgang V3 (jede DELETE-Route
gegen PostgreSQL) findet diese Art systematisch.

#### Festlegungen 1.9.340 (Bitte bestätigen)

1. Löschen über Tabellen ohne ORM-Beziehung: zuerst löschen oder lösen, was zeigt, in einem eigenen Flush, dann das Ziel (E1–E3, E5).
2. Ein erneuter Import einer Leistung löst nur den Verweis einer Angebotskalkulation auf das alte Quellmaterial (`source_material_id` leer); die Werte der
   Kalkulation bleiben (E4).
3. Ein Konto, das anderswo steht, wird nicht gelöscht: 409 mit den Bereichen und dem Rat zu deaktivieren. Was nur zum Konto gehört (Sitzungen,
   vertraute Geräte, Wiederherstellungscodes, Kacheln der Startseite), geht mit ihm.
4. Jeder Fremdschlüssel auf `app_users` steht in `MIT_DEM_KONTO` oder `BEREICHE` (`app/konto_loeschen.py`); ein neuer kommt dort hinein (Wächter).

#### Tests und Prüfung 1.9.340

Neu `tests/test_v740_e1_bis_e5_und_konto.py` (6 Tests): E1 über die Route, E4 mit erhaltenen Werten, E5 mit Lieferanten-Zuordnung allein, Konto mit
Verwendung (409), Konto ohne Verwendung mit Kacheln und Wiederherstellungscode (geht mit), jeder Fremdschlüssel eingeordnet. Vor den Korrekturen unter
dem PRAGMA rot: E1 über die Route, E4, beide Konto-Tests (je `IntegrityError`); grün schon vorher: E5 mit Lieferant allein (siehe oben) und der Wächter.
Die 11 Tests von E1–E5 (v194, v247, v214, v105, v083) waren seit 1.9.339 streng erwartet rot und laufen jetzt normal. Angepasste Erwartungen: keine
(nur `FREMDSCHLUESSEL_BEKANNT` entfernt).

## Nachrunde V1: E6 und die Seite „Benutzer“ (ab 1.9.341)

Runde V1 geprüft (4a704d7) und live; die 13 Festlegungen 1.9.338–1.9.340 bestätigt (14.11.2026). Antworten Tobias auf die offenen Fragen:
- **E6:** mit Grund ablehnen, nicht lösen -- ein Projekt oder Bericht aus dem Vertrag gehört zu seiner Geschichte. 409 mit den Bereichen und dem Rat, den
  Vertrag zu beenden statt zu löschen (wie bei „Benutzer löschen“); `delete_contract_item()` gleich mitprüfen. Eigene kleine Runde, jetzt.
- **Benutzer:** bei einem verwendeten Konto auf der Seite gleich „Deaktivieren“ statt „Löschen“; „Löschen“ nur für ein nie verwendetes Konto.
- **Klicktests mit PRAGMA:** mit V3.

Runde ab 1.9.341, je Punkt eine Version: **1** E6 wie oben, je mit einem Test, der vorher unter dem PRAGMA rot war; **2** Seite „Benutzer“: „Deaktivieren“
statt „Löschen“ bei verwendetem Konto (der Server sagt, ob verwendet), Bilder 1440 und 412 px, hell und dunkel; **3** nur prüfen: was passiert mit den
Folgeaufgaben, die E3 mit dem Berichtsentwurf löscht, wenn sie schon zugewiesen, eingeplant oder erledigt sind -- Vorschlag in den Bericht, erst fragen.

### Umsetzung 1.9.341: Wartungsvertrag und Position mit Geschichte nicht löschen (Punkt 1, E6)

- `app/maintenance_contracts.py`: `vertrag_verwendungen()` und `position_verwendungen()` nennen, was entstanden ist -- ein Projekt aus dem Vertrag oder
  der Position (`project_profiles.source_maintenance_contract_id` bzw. `…_item_id`) oder ein Einsatzbericht (`service_reports.maintenance_contract_id`
  bzw. `…_item_id`), auch ein Entwurf. Für den Vertrag zählt auch, was aus einer seiner Positionen entstand (die Positionen gingen sonst mit ihm).
  `delete_contract()` und `delete_contract_item()` lehnen dann mit `VertragVerwendet` ab, die Routen mit 409:
  „Aus dem Vertrag sind schon Projekte und Einsatzberichte entstanden – sie gehören zu seiner Geschichte, deshalb lässt er sich nicht löschen. Beende
  den Vertrag stattdessen (⋮ → Beenden): dann erinnert er nicht mehr, und alles bleibt.“ -- bei der Position „… Archiviere die Position stattdessen …“
  (eine Position hat kein „Beenden“; archiviert erinnert sie nicht mehr). Die Vertragsseite zeigt die Meldung in ihrer Statuszeile wie jede andere.
- Bis 1.9.340 sperrte nur ein **unterschriebener** Bericht (400, „… nur archiviert“); ein Projekt aus dem Vertrag oder ein Berichtsentwurf ließ das
  Löschen unter PostgreSQL am Fremdschlüssel mit 500 scheitern (seit 1.9.339 auch in der Suite). Ohne Geschichte unverändert: der Vertrag geht samt
  Positionen (ORM-Kaskade) und Erinnerungen (`source_url`).
- Jeder Fremdschlüssel auf `maintenance_contracts` und `maintenance_contract_items` steht in `MIT_DEM_VERTRAG`, `AUS_DEM_VERTRAG` oder
  `AUS_DER_POSITION` (Wächter). Berichtigt dabei: `docs/archiv/modul-wartungen-und-monteursansicht.md` schrieb seit 1.2.15, keine andere Tabelle trage
  einen Fremdschlüssel auf `maintenance_contracts`, und ein Entwurfsbericht blockiere das Löschen nicht -- beides galt nur ohne Prüfung der
  Fremdschlüssel. Die Stelle in `sign_report()`, die einen schon gelöschten Vertrag überspringt, bleibt als Verteidigung; erreichbar ist sie nicht mehr.

#### Festlegungen 1.9.341 (Bitte bestätigen)

1. Ein Wartungsvertrag, aus dem ein Projekt oder ein Einsatzbericht entstanden ist (auch ein Entwurf, auch über eine seiner Positionen), wird nicht
   gelöscht: 409 mit den Bereichen und dem Rat, ihn zu beenden (⋮ → Beenden).
2. Eine Position, aus der ein Projekt oder ein Einsatzbericht entstanden ist, wird nicht gelöscht: 409 mit den Bereichen und dem Rat, sie zu archivieren.
3. Jeder Fremdschlüssel auf Vertrag und Position steht in `MIT_DEM_VERTRAG`, `AUS_DEM_VERTRAG` oder `AUS_DER_POSITION`; ein neuer kommt dort hinein.
4. Ohne Geschichte geht der Vertrag wie bisher samt Positionen und Erinnerungen.

#### Tests und Prüfung 1.9.341

Neu `tests/test_v741_vertrag_loeschen.py` (6 Tests): Vertrag mit Projekt, mit Berichtsentwurf, mit Projekt und Bericht aus einer Position; Position mit
Projekt bzw. Bericht; Vertrag ohne Geschichte samt Position und Erinnerung; jeder Fremdschlüssel eingeordnet. Ohne die neue Prüfung (Gegenprobe `341_1`,
`341_2`) scheitern die vier Fälle mit Geschichte am Fremdschlüssel (`FOREIGN KEY constraint failed`) -- sie waren unter dem PRAGMA vorher rot.
Angepasste Erwartung (Regel 28): `test_v212::test_delete_contract_cascades_items_without_reports_but_blocks_when_signed_report_exists` -- Meldung mit
„archiviert“ -> mit „Beende den Vertrag stattdessen“ (der Fall selbst bleibt abgelehnt). Gegenproben: `docs/archiv/gegenproben-v1-fremdschluessel.md`.
