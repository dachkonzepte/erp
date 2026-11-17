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

### Umsetzung 1.9.342: Seite „Benutzer“ -- „Deaktivieren“ statt „Löschen“ bei verwendetem Konto (Punkt 2)

- **Server:** `GET /api/users` nennt je Konto `verwendet_in` -- die Bereiche aus `app/konto_loeschen.py::verwendungen()`, leer = nie verwendet. Neu
  `POST /api/users/{id}/deaktivieren` (nur Admin): setzt nur `active` auf aus und beendet im selben Commit alle Sitzungen des Kontos (Regel 30);
  Rolle, Mitarbeiter und alles andere bleiben. Dieselben Sperren wie beim Ändern: nicht das eigene Konto, nicht der letzte aktive Administrator (409);
  ein schon inaktives Konto bleibt, wie es ist. Ein eigener Endpunkt, weil `PUT /api/users/{id}` ein volles Update ist -- schickte die Seite dort nur
  `active=false`, fielen Rolle und Mitarbeiter auf die Vorgaben (Regel 22).
- **Seite:** je Konto genau ein Knopf neben „Bearbeiten“ (`kontoKnopf()`): nie verwendet -> „Löschen“; verwendet und aktiv -> „Deaktivieren“ (title
  „Verwendet in: …“, Rückfrage nennt die Bereiche und dass sie bleiben); verwendet und schon inaktiv -> keiner (wieder aktivieren über „Bearbeiten“).
  Das eigene Konto wie bisher ohne. Der Hinweistext der Karte sagt es: „Löschen lässt sich nur ein Konto, das nie verwendet wurde – ein verwendetes wird
  deaktiviert, was es angelegt hat, bleibt.“ Beide Knöpfe über `data-klick` (Regel 32; „Löschen“ trug bis dahin die ID im `onclick` -- die
  Ausnahmeliste von `test_v407` ist um eins kürzer), die Anfrage über `speichern()` (Regel 29).
- Klicktest `scripts/klicktest_benutzer_deaktivieren.py` mit Bildern bei 1440 und 412 px, hell und dunkel. Bei 412 px rollt die Tabelle wie bisher in
  ihrem Rahmen (nichts läuft über die Seite); fürs Bild ist sie zu den Knöpfen gerollt.

#### Festlegungen 1.9.342 (Bitte bestätigen)

1. Der Server sagt je Konto, wo es steht (`verwendet_in` in `GET /api/users`, leer = nie verwendet); die Seite rechnet das nicht selbst.
2. Die Seite bietet „Löschen“ nur für ein nie verwendetes Konto, „Deaktivieren“ für ein verwendetes aktives, keinen der beiden für ein verwendetes
   inaktives und für das eigene Konto.
3. Deaktivieren hat einen eigenen Endpunkt, der nur `active` ändert und alle Sitzungen beendet; nicht das eigene Konto, nicht der letzte aktive
   Administrator.

#### Tests und Prüfung 1.9.342

Neu `tests/test_v742_benutzer_deaktivieren.py` (4 Tests) und `scripts/klicktest_benutzer_deaktivieren.py` (12 Prüfungen, Bilder). Angepasste Erwartung
(Regel 28): `test_v407`, `AUSNAHMEN_HANDLER` „users.html | render | onclick: u.id“ 3 -> 2 (nur kürzer, „Löschen“ über `data-klick`).

### Punkt 3 (nur geprüft, nicht gebaut): Folgeaufgaben, die E3 mit dem Berichtsentwurf löscht

Entschieden 17.11.2026: Variante A, gebaut in 1.9.343; das Löschen von Aufgaben steht seit 1.9.344 in der Änderungshistorie (siehe „Runde ab 1.9.343“).

- **Wie sie entsteht:** wählt die Monteurin an einem Befund die Maßnahme „Büro prüfen lassen“, legt `app/findings.py::_execute_finding_action()` sofort
  eine Aufgabe an („Büro prüfen lassen: <Befund>“), zugewiesen an den Sachbearbeiter des Auftrags, mit Mail an ihn -- schon im Entwurf des Berichts.
  `Finding.follow_up_task_id` zeigt auf sie. Das Büro sieht sie sofort.
- **Was das Büro daran tun kann:** Spalte und Status (auch erledigt, mit `completed_at`), Zuständigkeit ändern oder übernehmen, Fälligkeit, Priorität,
  Beschreibung, Unteraufgaben (`TaskChecklistItem`) abhaken, und „Vorgang erstellen“ -- daraus entstehen Projekt und Auftrag
  (`create_follow_up_project_for_task()`), die wiederum eingeplant werden können. „Eingeplant“ ist die Aufgabe selbst nur über ihre Fälligkeit: kein
  Fremdschlüssel verbindet eine Aufgabe mit Plantafel oder Kalender.
- **Was beim Löschen des Entwurfs passiert:** `delete_report()` löscht jede Folgeaufgabe, egal in welchem Zustand -- zugewiesen, mit Fälligkeit,
  erledigt, mit Unteraufgaben (gehen mit). Löschen darf die Monteurin ihren eigenen Entwurf (`require_field_report_ownership()`), das Büro jeden. Ein
  aus der Aufgabe erstellter Vorgang bleibt (Herkunft als Text in der Projektbeschreibung), verliert aber den Weg zurück.
- **Geht Arbeit verloren?** Ja, und spurlos: `Task` steht nicht in der Änderungshistorie (`AUDITED_TYPES`); nur „übernommen“ schreibt `claim_task()`
  selbst. Was das Büro an der Aufgabe getan hat, ist danach nicht mehr nachvollziehbar; die Zuständige merkt es nur daran, dass die Aufgabe fehlt.
- **Vorschlag (erst fragen):** die Folgeaufgabe nur mitlöschen, solange niemand sie angefasst hat (noch im Anfangsstatus, nicht erledigt, ohne
  Unteraufgaben, ohne Vorgang daraus, sonst unverändert seit dem Anlegen). Sonst bleibt sie: der Verweis des Befunds entfällt mit dem Entwurf, die Aufgabe
  bekommt einen Vermerk in der Beschreibung („Der Berichtsentwurf mit diesem Befund wurde am … gelöscht.“), und das Büro entscheidet. Alternative: das
  Löschen des Entwurfs mit 409 ablehnen, solange eine Folgeaufgabe bearbeitet ist -- dann kann die Monteurin ihren Entwurf nicht mehr selbst aufräumen.

## Runde ab 1.9.343: Aufgaben beim Löschen

Nachrunde V1 geprüft (f67cba8) und live; die 7 Festlegungen 1.9.341–1.9.342 bestätigt (17.11.2026). Antworten Tobias:
- **Punkt 3: Variante A.** „Angefasst“ wie beschrieben: nicht mehr im Anfangsstatus, erledigt, mit Unteraufgaben, mit Vorgang daraus oder sonst
  seit dem Anlegen geändert. Unangetastet geht sie mit dem Entwurf; angefasst bleibt sie, der Verweis entfällt, Vermerk in der Beschreibung „Der
  Berichtsentwurf mit diesem Befund wurde am … von … gelöscht – bitte prüfen.“
- **Änderungshistorie:** nur das Löschen von Aufgaben -- jedes Löschen, auch das Mitlöschen mit einem Entwurf, mit Titel, Konto, Zeitpunkt und
  Anlass. Sonstige Änderungen an Aufgaben nicht.

Runde ab 1.9.343, je Punkt eine Version: **1** Variante A, mit einem Test, der vorher rot war; **2** Löschen von Aufgaben in die Änderungshistorie,
auf allen Wegen, die Aufgaben löschen (Liste der Wege in den Bericht); **3** Seite „Benutzer“: die Rückfrage bei „Deaktivieren“ und „Löschen“ nennt
Benutzername und Anzeigename (bei 412 px ist neben dem Knopf kein Name zu sehen), Bilder 412 px hell und dunkel. Rückfrage 17.11.2026: die Rückfrage
ist ein `confirm()` des Browsers, ein Bildschirmfoto zeigt ihn nicht -- Antwort Tobias: `confirm()` bleibt (Regel 4); die Bilder zeigen die Zeile mit dem
Knopf, der Klicktest liest den Text des Dialogs, der Bericht zitiert ihn.

### Umsetzung 1.9.343: Folgeaufgabe nur unangetastet mitlöschen (Punkt 1, Variante A)

- `app/service_reports.py::folgeaufgabe_angefasst()`: angefasst ist eine Folgeaufgabe, wenn sie nicht mehr in der Anfangsspalte steht (das deckt
  „erledigt“: jede Spalte „erledigt“ ist eine andere als die erste), Unteraufgaben hat, aus ihr ein Vorgang erstellt wurde (`follow_up_order_id`
  bzw. `follow_up_project_id` am Befund) oder sie sonst seit dem Anlegen geändert wurde: `updated_at` liegt mehr als `UNVERAENDERT_BIS` (1 s) nach
  `created_at`. Beide Zeitpunkte setzt das Anlegen getrennt, gemessen 2 µs auseinander -- deshalb nicht „ungleich“. Jede Änderung an der Zeile der
  Aufgabe setzt `updated_at` neu: Spalte, Zuständigkeit, Fälligkeit, Priorität, Titel, Beschreibung, Archiv, auch das bedingte UPDATE beim Übernehmen
  (geprüft: `onupdate` greift dort). Unteraufgaben und Vorgang ändern die Zeile nicht, deshalb eigene Merkmale.
- `delete_report()` prüft je Befund vor dem Löschen; danach (eigener Flush wie seit 1.9.340) geht eine unangetastete Folgeaufgabe, eine angefasste
  bleibt: der Befund geht mit dem Bericht und mit ihm der Verweis, die Beschreibung bekommt vorn `folgeaufgabe_vermerk()` -- Wortlaut wie oben, Datum in
  Berlin, Konto = Anzeigename des löschenden Kontos (sonst Benutzername; ohne Konto der Auslöser der Anfrage). Die Route gibt das Konto mit
  (`DELETE /api/service-reports/{id}`, Monteurin für den eigenen Entwurf wie Büro). Ein aus der Aufgabe erstellter Vorgang bleibt wie bisher.
- Nicht geändert: Wartungsvertrag und Aufgaben von Hand. Die Änderung der Beschreibung steht nicht in der Historie (nur das Löschen, Punkt 2).

#### Festlegungen 1.9.343 (Bitte bestätigen)

1. Eine Folgeaufgabe geht mit ihrem Berichtsentwurf nur unangetastet. Angefasst: nicht in der Anfangsspalte (auch erledigt), mit Unteraufgaben (beim
   Löschen vorhanden), mit Vorgang daraus oder sonst seit dem Anlegen geändert.
2. „Sonst seit dem Anlegen geändert“ = `updated_at` mehr als eine Sekunde nach `created_at` (das Anlegen setzt beide Mikrosekunden auseinander).
3. Anfangsspalte = die heute erste Spalte der Aufgaben. Hat der Admin die Spalten seit dem Anlegen umgestellt, gilt eine Aufgabe in der früheren ersten
   Spalte als angefasst und bleibt -- die sichere Richtung.
4. Eine angefasste bleibt mit dem Vermerk vorn in der Beschreibung (Wortlaut Tobias, Datum in Berlin, Anzeigename des löschenden Kontos), die bisherige
   Beschreibung darunter.

#### Tests und Prüfung 1.9.343

Neu `tests/test_v743_folgeaufgabe_angefasst.py` (15 Tests): unangetastet geht (auch eine ältere), je eine Art „angefasst“ (Spalte, erledigt, Unteraufgabe,
Vorgang, Priorität, Fälligkeit, Beschreibung, zugewiesen, übernommen, archiviert) bleibt mit Vermerk, der Vorgang bleibt, von zwei Folgeaufgaben nur die
angefasste, über die Route mit dem Namen des Kontos. Für die Arten, die nur über `updated_at` erkennbar sind, setzt der Test beide Zeitpunkte eine Stunde
zurück (eine Änderung liegt dann wie im Betrieb nach dem Anlegen). Mit dem Stand bis 1.9.342 nachgestellt (`343_1`: jede Folgeaufgabe geht mit) sind 13
rot -- alle außer den beiden unangetasteten. Angepasste Erwartungen: keine.

### Umsetzung 1.9.344: Löschen von Aufgaben in der Änderungshistorie (Punkt 2)

- **Ein Weg:** `app/tasks.py::aufgabe_loeschen(db, task, anlass, user)` merkt Anlass und Konto an der Aufgabe und löscht sie (Unteraufgaben per Kaskade).
  Den Eintrag schreibt `app/audit.py::collect_audit()` im Flush für **jede** Aufgabe in `session.deleted` (`_aufgabe_geloescht()`): Aktion „gelöscht“,
  Art „Aufgabe“, Bezeichnung „Nr. <id> · <Titel>“, Projekt der Aufgabe, Feld „Anlass“ mit dem Anlass als neuem Wert, Konto aus `aufgabe_loeschen()` (sonst
  das der Anfrage), Zeitpunkt wie jeder Eintrag (`occurred_at`). Ein Löschen an `aufgabe_loeschen()` vorbei steht trotzdem drin, mit „ohne Angabe (<Methode>
  <Pfad>)“. `Task` bleibt außerhalb von `AUDITED_TYPES`: Anlegen und jede andere Änderung schreiben nichts (wie bisher nur „übernommen“, seit 1.8.18).
- **Die Wege, die Aufgaben löschen** (gesucht: `db.delete`/`session.delete` auf einer Aufgabe, `delete(Task)`, `Task.__table__`, `query(Task)….delete()`,
  SQL mit `tasks` unter `app/`, `scripts/` und `alembic/`; ORM-Kaskaden auf `Task`: keine):
  1. **Von Hand:** `DELETE /api/tasks/{id}` -> `delete_task()` (Aufgabenboard, Editor) -- Anlass „von Hand“.
  2. **Mit dem Berichtsentwurf:** `DELETE /api/service-reports/{id}` -> `delete_report()`, nur eine unangetastete Folgeaufgabe (1.9.343) -- Anlass „mit dem
     Berichtsentwurf Nr. <id> (Auftrag <Nummer>), unangetastet“. Eine angefasste bleibt; ihr Vermerk ist keine Zeile der Historie.
  3. **Mit dem Wartungsvertrag:** `DELETE /api/maintenance-contracts/{id}` -> `delete_contract()`, seine Erinnerungen (Vertrag und Positionen teilen den
     Link) -- Anlass „mit dem Wartungsvertrag „<Titel>“ (Erinnerung)“. Bis 1.9.343 über die Tabelle (`delete(Task)`): ohne Eintrag, und eine Erinnerung mit
     Unteraufgabe ließ das Löschen am Fremdschlüssel scheitern (live 500) -- jetzt einzeln, die Unteraufgaben per Kaskade.
  Kein anderer Weg löscht eine Aufgabe: keine Migration, kein Skript, keine Kaskade; ein Projekt, ein Konto, ein Mitarbeiter nehmen ihre Aufgaben nicht mit
  (siehe die Funde unten).
- **Sichtbar** wie jeder Eintrag zu Aufgaben seit 1.8.18 nur für den Admin (`app/routers/audit.py::sichtbar()`: der Titel kann eine fremde oder eine
  Finanz-Aufgabe nennen); im Verlauf der Akte (Projekt der Aufgabe) ebenso nur für den Admin. Die Anzeige „Datensatz gelöscht“ nennt den Anlass dahinter
  (`_verlauf.html::verlaufAenderung()`): „Datensatz gelöscht – von Hand“.
- **Wächter:** kein Löschen von Aufgaben über die Tabelle unter `app/` (`delete(Task)`, `Task.__table__.delete()`, `query(Task)….delete()`, SQL
  „DELETE FROM tasks“) -- das sähe `collect_audit()` nicht.

#### Funde dabei (nicht gebaut, erst fragen)

- **E7 -- Aufgabe von Hand löschen, auf die etwas zeigt:** `DELETE /api/tasks/{id}` scheitert am Fremdschlüssel (live unter PostgreSQL 500, in der Suite
  `FOREIGN KEY constraint failed`), wenn ein Befund (`findings.follow_up_task_id`, „Büro prüfen lassen“) oder eine Regel einer Checkliste
  (`checklist_rule_executions.task_id`) auf die Aufgabe zeigt. Geprüft mit beiden Fällen. Live laut B2 nie vorgekommen. Vorschlag A: lösen -- der Verweis
  wird leer, Befund bzw. Regel bleiben; beim Befund ließe sich „Büro prüfen lassen“ dann erneut auslösen (die Sperre hängt am Verweis), bei der Regel
  stünde „Aufgabe angelegt“ ohne Aufgabe. Vorschlag B: 409 mit dem Grund und dem Rat, die Aufgabe zu archivieren oder zu erledigen.
- **E8 -- Projekt ohne Auftrag mit Aufgabe löschen:** `delete_project()` scheitert am Fremdschlüssel `tasks.project_id` (live 500), sobald eine Aufgabe am
  Projekt hängt (geprüft). Vorschlag A: die Aufgaben vom Projekt lösen -- sie bleiben ohne Projekt (kein Löschen, kein Eintrag). Vorschlag B: 409 mit
  dem Grund. V3 (Rundgang gegen PostgreSQL) fände beides systematisch.

#### Festlegungen 1.9.344 (Bitte bestätigen)

1. Jedes Löschen einer Aufgabe steht in der Änderungshistorie: Aktion „gelöscht“, Art „Aufgabe“, Bezeichnung „Nr. … · Titel“, Konto, Zeitpunkt, Feld
   „Anlass“. Keine andere Änderung an Aufgaben kommt dazu; was schon drinsteht, bleibt (seit 1.8.18 „übernommen“, seit 1.8.19 der geklärte Versand
   einer Benachrichtigung).
2. Eine Aufgabe löscht nur `app/tasks.py::aufgabe_loeschen()` mit Anlass und Konto. Ein Löschen daran vorbei steht trotzdem drin („ohne Angabe (Methode
   Pfad)“); ein Löschen über die Tabelle ist verboten (Wächter).
3. Die Anlässe: „von Hand“; „mit dem Berichtsentwurf Nr. … (Auftrag …), unangetastet“; „mit dem Wartungsvertrag „…“ (Erinnerung)“.
4. Sichtbar nur für den Admin, wie jeder Eintrag zu Aufgaben seit 1.8.18 -- in der Änderungshistorie und im Verlauf der Akte.
5. Die Erinnerungen eines Wartungsvertrags gehen einzeln mit ihm, ihre Unteraufgaben mit ihnen.
6. Die Historie zeigt den Anlass hinter „Datensatz gelöscht“ („Datensatz gelöscht – von Hand“).

#### Tests und Prüfung 1.9.344

Neu `tests/test_v744_aufgaben_loeschen_historie.py` (9 Tests): von Hand über die Route (Titel, Konto, Zeitpunkt, Anlass, Projekt), mit dem
Berichtsentwurf (nur die unangetastete, mit Anlass und Konto), mit dem Wartungsvertrag samt Unteraufgabe, an `aufgabe_loeschen()` vorbei („ohne Angabe“),
keine Zeile für sonstige Änderungen, nur der Admin sieht die Einträge, Wächter gegen das Löschen über die Tabelle samt Probe jeder Form, Anzeige des
Anlasses (node). Vorher rot (Stand bis 1.9.343 nachgestellt, `344_1` und `344_5`): jede Prüfung eines Eintrags; der Wartungsvertrag mit Unteraufgabe dazu
am Fremdschlüssel. Eine Gegenprobe blieb zuerst grün (`344_10`, `Task` in `AUDITED_TYPES`): der Test zählte nur Einträge der Art „Aufgabe“, die Einträge
hießen dann „Task“ -- nachgezogen, er zählt jetzt alle Einträge; danach rot. Angepasste Erwartungen: keine.

### Umsetzung 1.9.345: Rückfrage auf „Benutzer“ nennt Anzeigename und Benutzername (Punkt 3)

- `app/templates/users.html`: die Rückfrage bei „Löschen“ und „Deaktivieren“ beginnt mit `kontoName(u)` -- „Benutzer „Bea Büro“ (Benutzername „bea“)
  deaktivieren?“ bzw. „… wirklich löschen?“; der Rest der Rückfrage bleibt. Anlass: bei 412 px rollt die Tabelle in ihrem Rahmen, neben dem Knopf steht
  kein Name (der Klicktest misst es: Benutzername und Anzeigename der Zeile außerhalb des sichtbaren Rahmens, der Knopf darin).
- Die Rückfrage bleibt ein `confirm()` (Regel 4, Antwort Tobias 17.11.2026). Ein Bildschirmfoto zeigt sie nicht; der Klicktest fängt ihren Text ab
  (`window.confirm` umgeleitet) und prüft ihn, die Bilder zeigen die Zeilen mit den Knöpfen.
- Nicht geändert: „Zweiten Faktor zurücksetzen“ und „Alle Sitzungen beenden“ nennen weiter nur den Anzeigenamen (bei 412 px dieselbe Lage) -- nicht
  verlangt, Hinweis im Bericht.

#### Festlegungen 1.9.345 (Bitte bestätigen)

1. Die Rückfrage bei „Löschen“ und „Deaktivieren“ nennt das Konto als „Benutzer „<Anzeigename>“ (Benutzername „<Benutzername>“)“ -- eine Stelle,
   `kontoName()`.

#### Tests und Prüfung 1.9.345

Neu `tests/test_v745_benutzer_rueckfrage.py` (node: beide Rückfragen mit einem Konto, dessen Anzeigename Markup enthält -- `confirm()` zeigt Text) und
`scripts/klicktest_benutzer_rueckfrage.py` (11 Prüfungen: bei 412 px kein Name neben dem Knopf, beide Rückfragen abgebrochen ohne Änderung, Löschen
bestätigt, Bilder 412 px hell und dunkel). Angepasste Erwartungen: keine.

## Runde ab 1.9.346: E7, E8, Rückfragen auf „Benutzer“, `_run` in v363 und v365

Runde ab 1.9.343 geprüft (e0f1c16) und live; die 11 Festlegungen 1.9.343–1.9.345 bestätigt (17.11.2026), 1.9.343-2 unter dem Vorbehalt von Punkt 1.
Antworten Tobias:
- **E7:** B -- 409 mit Grund und dem Rat, die Aufgabe zu erledigen oder zu archivieren.
- **E8:** B -- 409 mit Grund und dem Rat, das Projekt abzusagen oder zuerst die Aufgaben zu löschen. Rückfrage 17.11.2026: „absagen“ gibt es für ein
  Projekt nicht (vorhanden: „Archivieren“ am Projekt, „abgelehnt“ am Angebot) -- Antwort: der Rat heißt „archivieren“.
- **„Zweiten Faktor zurücksetzen“ und „Alle Sitzungen beenden“:** ja, beide Namen wie `kontoName()`.
- **v363 und v365:** ja, `_run` auf das Warten an der Sperre umstellen wie 1.9.8 in v375; Wackler-Liste nachtragen.

Runde ab 1.9.346: **1** nur prüfen, vorweg (keine Version): berührt nach dem Anlegen einer Folgeaufgabe irgendetwas Automatisches ihre Zeile? **2** E7
und E8 (1.9.346); **3** die beiden Rückfragen (1.9.347); **4** v363 und v365 (1.9.348).

### Punkt 1 (nur geprüft): nichts Automatisches berührt die Zeile einer Folgeaufgabe

- **Statisch:** jeder schreibende Weg an Aufgaben unter `app/` (Zuweisung an ein Feld einer Aufgabe, `update_task()`, `set_task_archived()`,
  `release_task()`, `claim_task()`, `update(Task)`). Außerhalb von `app/tasks.py` schreiben nur drei Stellen, alle in ihre eigenen Aufgaben:
  `app/checklist_follow_ups.py` (Aufgaben aus Folgen einer Checkliste, über `ChecklistFollowUp.target_id`), `app/defects.py` und
  `app/acceptance_protocol.py` (Aufgaben eines Mangels, über `Defect.task_id`/`DefectEvent.task_id`). Eine Folgeaufgabe eines Befunds ist keine davon.
  Die Benachrichtigung (`notify_task_assignment()` -> `dispatch_email()`) schreibt nur ins Versandprotokoll; `mark_document_sent()` gilt nur für
  Angebot, Auftrag, Rechnung und Mahnung. Übernehmen und „zurück in den Büro-Eingang“ sind Klicks eines Menschen. Zähler gibt es an der Aufgabe nicht.
- **Datenbank:** `tasks.updated_at` setzt nur die Anwendung (`onupdate` in Python) -- kein Trigger, keine Vorgabe der Datenbank; keine Migration ändert
  Zeilen von `tasks` (nur Spalten).
- **Probe (Wegwerf-Test, nicht im Repo):** jedes UPDATE auf `tasks` mitgezählt, während das Büro über die Route einen Befund mit „Büro prüfen lassen“
  anlegt (Folgeaufgabe an die Sachbearbeiterin, Mail ging hinaus) und danach: Aufgabenliste, Aufgabenliste ohne Zuständigkeit, Befund zur Aufgabe,
  Startseite, Suche, Bericht ändern, Befund erledigt und wieder offen, die vier Erinnerungsläufe (Wartung, Prüffristen, Kündigung, Skonto) -- 0 UPDATE
  auf `tasks`; `updated_at` 2 µs nach `created_at`.
- **Ergebnis:** Variante A läuft nicht ins Leere; 1.9.343-2 gilt ohne Vorbehalt. Kein Vorschlag nötig.

### Umsetzung 1.9.346: E7 und E8 (Punkt 2)

- **E7:** `app/tasks.py::aufgabe_loeschen()` prüft vor dem Löschen `aufgabe_verwendungen()`: zeigt ein Befund (`findings.follow_up_task_id`) oder eine
  Regel einer Checkliste (`checklist_rule_executions.task_id`) auf die Aufgabe, `AufgabeVerwendet` -> `DELETE /api/tasks/{id}` 409: „Die Aufgabe gehört zu
  einem Befund im Einsatzbericht – deshalb lässt sie sich nicht löschen. Erledige oder archiviere sie stattdessen.“ (bzw. „… zu einer Regel einer
  Checkliste …“). Die Prüfung sitzt im einen Weg, gilt also für jeden; Berichtsentwurf und Wartungsvertrag treffen sie nicht (der Befund ist dann schon
  weg, auf Erinnerungen zeigt nichts). Jeder Fremdschlüssel auf `tasks` steht in `MIT_DER_AUFGABE` oder `VERWEISE_AUF_AUFGABEN` (Wächter). Aufgaben eines
  Mangels und aus Folgen einer Checkliste haben keinen Fremdschlüssel und bleiben löschbar (so gebaut: `Defect.task_id`, `DefectEvent.task_id`,
  `ChecklistFollowUp.target_id` in `app/models.py`).
- **E8:** `app/projects.py::delete_project()` prüft nach dem Auftrag die Aufgaben am Projekt: `ProjektVerwendet` -> `DELETE /api/projects/{id}` 409: „Am
  Projekt hängt noch 1 Aufgabe – deshalb lässt es sich nicht löschen. Archiviere das Projekt stattdessen oder lösche zuerst seine Aufgaben.“ (ab zwei
  „hängen noch n Aufgaben“). Ein Projekt mit Auftrag bleibt bei 400 („nur archiviert“), unverändert. Akte und Projektliste zeigen die Meldung als „Fehler: …“.
- **Funde dabei (nicht gebaut):** ein Projekt ohne Auftrag scheitert beim Löschen auch, wenn es **Vorlage eines Wartungsvertrags** oder einer Position ist
  (`maintenance_contracts.template_project_id`, `maintenance_contract_items.template_project_id`; ein Mustervorgang) oder eine **Eingangsrechnung** an ihm
  hängt (`incoming_invoices.project_id`) -- beide nachgestellt, `FOREIGN KEY constraint failed`, live 500 (E9, E10). Der Test ordnet jeden Fremdschlüssel
  auf `projects` ein; diese drei stehen dort in `OFFEN` (darf nur kürzer werden). Eine Anfrage am Projekt löst die Beziehung (`source_inquiry`), geprüft.

#### Festlegungen 1.9.346 (Bitte bestätigen)

1. Eine Aufgabe, auf die ein Befund oder eine Regel einer Checkliste zeigt, wird nicht gelöscht: 409 mit dem Grund und dem Rat „Erledige oder archiviere sie
   stattdessen.“ Die Prüfung sitzt in `aufgabe_loeschen()`.
2. Jeder Fremdschlüssel auf `tasks` steht in `MIT_DER_AUFGABE` oder `VERWEISE_AUF_AUFGABEN`; ein neuer kommt dort hinein (Wächter).
3. Ein Projekt ohne Auftrag, an dem eine Aufgabe hängt, wird nicht gelöscht: 409 mit der Zahl der Aufgaben und dem Rat „Archiviere das Projekt stattdessen
   oder lösche zuerst seine Aufgaben.“
4. Jeder Fremdschlüssel auf `projects` ist eingeordnet (was `delete_project()` mit ihm tut); was heute noch scheitert, steht in `OFFEN` und darf nur kürzer
   werden.

#### Tests und Prüfung 1.9.346

Neu `tests/test_v746_aufgabe_und_projekt_loeschen.py` (7 Tests): Folgeaufgabe eines Befunds und Aufgabe einer Checklisten-Regel von Hand 409 (Aufgabe und
Verweis bleiben, kein Eintrag „gelöscht“), Aufgabe ohne Verweis geht, Wächter `tasks`; Projekt mit einer und mit zwei Aufgaben 409, Projekt ohne Aufgabe
geht, Wächter `projects`. Ohne die Prüfungen (`346_1`, `346_5`) scheitern die drei Fälle mit Verweis am Fremdschlüssel -- vorher rot. Angepasste
Erwartungen: keine.

### Umsetzung 1.9.347: „Zweiten Faktor zurücksetzen“ und „Alle Sitzungen beenden“ mit beiden Namen (Punkt 3)

- `app/templates/users.html`: beide Rückfragen nennen das Konto über `kontoName(u)` -- „Zweiten Faktor von Benutzer „Dirk Zweit“ (Benutzername „dirk“)
  wirklich zurücksetzen?“, „Alle Sitzungen von Benutzer „Bea Büro“ (Benutzername „bea“) beenden?“; der Rest bleibt. Damit nennen alle vier Rückfragen
  der Zeile eines Kontos beide Namen aus einer Stelle. Der Knopf „Zweiten Faktor zurücksetzen“ trägt weiter `onclick` mit der ID (Ausnahmeliste der
  Regel 32, unverändert).

#### Festlegungen 1.9.347 (Bitte bestätigen)

1. Auch die Rückfragen „Zweiten Faktor zurücksetzen“ und „Alle Sitzungen beenden“ nennen das Konto über `kontoName()`.

#### Tests und Prüfung 1.9.347

`tests/test_v745_benutzer_rueckfrage.py` und `scripts/klicktest_benutzer_rueckfrage.py` erweitert (der Klicktest mit Dirk Zweit als zweitem Administrator
und einer Sitzung für Bea, 13 Prüfungen). Angepasste Erwartungen (Regel 28): v745 liest 5 statt 3 Funktionen und prüft 4 statt 2 Rückfragen; der Klicktest
„kein Name im Bild“ mit Dirk (4 statt 3 Zeilen), „nichts geändert“ mit den Sitzungen je Konto, „Carl gelöscht“ `["anna", "bea"]` -> `["anna", "bea", "dirk"]`
(Testdaten um Dirk erweitert).

### Umsetzung 1.9.348: `_run` in v363 und v365 (Punkt 4)

Nur Testablauf: `_run` gibt die erste Aktion frei, sobald eine Verbindung nachweislich auf ihre Sperre wartet (`pg_blocking_pids()`), statt nach einer festen
Sekunde; der Wackler `test_v369` vom 17.11.2026 ist damit behoben. Herleitung, zwei Festlegungen zu Werkzeug und Testablauf, sieben angepasste
Erwartungen und die Gegenprobe: `docs/archiv/testablauf-und-klicktests.md`, „Umsetzung 1.9.348“.

## Runde V2a ab 1.9.349: E9, E10, Längen, Adressimport, Berater- und Mandantennummer

Runde ab 1.9.346 geprüft (6e78ae8) und live; die 5 Festlegungen 1.9.346–1.9.347 und die 2 zum Testablauf aus 1.9.348 bestätigt, 1.9.343-2 gilt ohne
Vorbehalt (17.11.2026). Antworten Tobias:
- **E9 und E10:** B wie empfohlen -- 409 mit Grund und Rat wie bei E8.
- **V2** kommt in drei Runden: V2a Längen und Adressimport, V2b Sortierung und Reihenfolge (F6), V2c Zahlenbereiche und Suchmuster. Jetzt V2a.

Runde ab 1.9.349, je Punkt eine Version: **0** E9 und E10, je mit einem Test, der vorher rot war (1.9.349); **1** Längen: jedes Eingabefeld, das in eine
Spalte String(n) geht, bekommt max_length ≤ n (die 89 aus dem Befund, Abschnitt 3 A), zu lang heißt 422 mit Feld und Grenze, nie 500; Wächter: die Liste
der offenen Felder darf nur kürzer werden und ist am Ende leer (1.9.350); **2** Adressimport (F7): jede Zeile einzeln prüfen, eine Zeile mit zu langem
Wert abgelehnt, nicht gekürzt, die übrigen gehen durch; die Antwort nennt je abgelehnter Zeile Zeilennummer, Feld und Grenze, die Seite zeigt die
Liste; Bilder 1440 und 412 px, hell und dunkel (1.9.351); **3** Berater- und Mandantennummer in den Zeitregeln: nur Ziffern, höchstens 7 bzw. 5
Stellen, Meldung am Feld statt 500, falls es das nicht schon gibt (1.9.352).

### Umsetzung 1.9.349: Projekt als Vorlage eines Wartungsvertrags oder mit Eingangsrechnung nicht löschen (Punkt 0, E9, E10)

- `app/projects.py::PROJEKT_SPERREN` und `projekt_sperren()`: was das Löschen eines Projekts ohne Auftrag sperrt, je Fremdschlüssel mit Bezeichnung in
  Einzahl und Mehrzahl und Rat -- Aufgaben (E8, seit 1.9.346), Vorlage eines Wartungsvertrags (`maintenance_contracts.template_project_id`) und einer
  Position (`maintenance_contract_items.template_project_id`, E9), Eingangsrechnungen (`incoming_invoices.project_id`, E10). `delete_project()` antwortet
  mit einer Meldung für alles zusammen, 409:
  „Am Projekt hängt noch 1 Wartungsvertrag, der es als Vorlage nimmt – deshalb lässt es sich nicht löschen. Archiviere das Projekt stattdessen oder
  wähle im Wartungsvertrag eine andere Vorlage.“
  „Am Projekt hängen noch 2 Eingangsrechnungen – … oder ordne die Eingangsrechnungen einem anderen Projekt zu.“
  „Am Projekt hängen noch 1 Aufgabe und 1 Eingangsrechnung – … oder lösche zuerst seine Aufgaben und ordne die Eingangsrechnung einem anderen Projekt zu.“
  Nur Aufgaben: unverändert wie 1.9.346. Der Rat nennt, was es im Bestand gibt: die Vorlage wählt man im Vertrag und in der Position beim Bearbeiten
  („Vorlage“), das Projekt einer Eingangsrechnung in ihrem Formular („Projekt“).
- Bis 1.9.348 scheiterte das Löschen an jedem davon am Fremdschlüssel (live 500). Der Wächter über die Fremdschlüssel auf `projects`
  (`tests/test_v746_aufgabe_und_projekt_loeschen.py`) hat kein `OFFEN` mehr; was dort „sperrt (409“ heißt, steht genau in `PROJEKT_SPERREN`.

#### Festlegungen 1.9.349 (Bitte bestätigen)

1. Ein Projekt ohne Auftrag, das Vorlage eines Wartungsvertrags oder einer Position ist, wird nicht gelöscht: 409 mit dem Rat, es zu archivieren oder im
   Vertrag bzw. in der Position eine andere Vorlage zu wählen.
2. Ein Projekt ohne Auftrag, an dem eine Eingangsrechnung hängt, wird nicht gelöscht: 409 mit dem Rat, es zu archivieren oder die Eingangsrechnung einem
   anderen Projekt zuzuordnen.
3. Hängt mehreres daran, nennt eine Meldung alles mit Zahl und alle Räte; nur Aufgaben wie seit 1.9.346.
4. Was das Löschen mit 409 sperrt, steht in `PROJEKT_SPERREN`; jeder Fremdschlüssel auf `projects` ist im Wächter eingeordnet, `OFFEN` ist leer.

#### Tests und Prüfung 1.9.349

Neu `tests/test_v749_projekt_vorlage_und_eingangsrechnung.py` (4 Tests): Vorlage eines Wartungsvertrags, Vorlage einer Position, zwei
Eingangsrechnungen, Aufgabe und Eingangsrechnung zusammen. Ohne den jeweiligen Eintrag in `PROJEKT_SPERREN` (`349_2`–`349_4`) scheitern die Fälle am
Fremdschlüssel -- vorher rot. Angepasste Erwartung (Regel 28): `test_v746::test_jeder_fremdschluessel_auf_projekte_ist_eingeordnet` -- die drei
Fremdschlüssel stehen nicht mehr in `OFFEN`, sondern als „sperrt (409, E9/E10)“, und alles, was mit 409 sperrt, muss in `PROJEKT_SPERREN` stehen.

### Umsetzung 1.9.350: jedes Eingabefeld mit der Länge seiner Spalte (Punkt 1)

- **Was offen war:** auf dem Stand von 1.9.349 dieselben 89 Spalten wie im Befund (Abschnitt 3 A, Zuordnung unverändert: ein Eingabeschema gehört zum
  Modell, mit dessen Klassennamen sein Name beginnt -- der längste Treffer --, ein Textfeld zur Spalte gleichen Namens). Sie stecken in 127
  Felddefinitionen, alle in `app/schemas.py` (geerbte Felder an der Stelle, an der sie definiert sind).
- **Gebaut:** jede dieser Definitionen hat `max_length` = Länge der Spalte -- `Field(default=…, max_length=n)` bzw. ein vorhandenes `Field(…)` um
  `max_length` ergänzt (ein Muster `pattern=` bleibt daneben). Berater- und Mandantennummer erbt `TimeTrackingSettingsUpdate` vom Antwortschema
  `TimeTrackingSettingsOut`; ein Antwortschema prüft nichts (1.9.273, `test_v673`), deshalb stehen die beiden dort im Update-Schema neu, mit 7 bzw. 5.
  `update_time_settings()` übernimmt sie ohnehin nicht -- gesetzt werden sie nur über `PUT /api/time-backoffice/datev-nummern` (`DatevNummernUpdate`,
  seit 1.9.92, siehe Punkt 3).
- **Zu lang:** 422 aus der Schemaprüfung, je Feld ein Eintrag mit `loc` (Feld), `type` „string_too_long“ und `ctx.max_length` (Grenze) -- nie mehr 500 unter
  PostgreSQL. Die vier Proben des Befunds über echte Routen (PLZ des Kunden, PLZ der Firma, Straße des Objekts, Priorität der Aufgabe) antworten so.
- **Auf der Seite:** `fehlerText()` (`_fehlertext.html`) hängt die Grenze an, wenn die Antwort sie nennt: „Bitte die Eingabe prüfen – PLZ ist zu lang
  (höchstens 20 Zeichen).“ Ohne `ctx` wie bisher „ist zu lang“. Seiten ohne `fehlerText()` (seit 1.8.35 bekannt: „28 weitere Vorlagen reichen detail
  roh weiter“) zeigen eine 422-Liste weiter als „Fehler: [object Object]“ -- grob ermittelt u. a. Aufgaben, Eingangsrechnungen, Betriebskosten,
  Prüfvorlagen, Wartungsverträge, Angebots-Editor, Leistung, Benutzer, Projekt anlegen, Anfragen. Dort sind die betroffenen Felder überwiegend
  Auswahllisten; nicht umgestellt, Vorschlag im Bericht.
- **Wächter** `tests/test_v750_laengen.py`: dieselbe Zuordnung über alle Eingabeschemas unter `app/` (ohne `app.main`); jedes zugeordnete Feld braucht
  `max_length` ≤ n. `OFFEN` darf nur kürzer werden und ist leer; ein neues Feld ohne Grenze macht ihn rot. Dazu je Feld die Probe „ein Zeichen zu viel“
  über `model_validate()` (417 Felder in 264 Spalten).
- Nicht in dieser Zuordnung (Grenzen der Heuristik, Befund): Formularfelder von Uploads (`Form(...)`), Felder mit anderem Namen als ihre Spalte, Schemas,
  deren Name nicht mit dem Modell beginnt. Sie findet der Rundgang V3 (jede schreibende Route mit Text an der Grenze und einem Zeichen darüber).

#### Festlegungen 1.9.350 (Bitte bestätigen)

1. Jedes Eingabefeld, das in eine Spalte `String(n)` geht, hat `max_length` ≤ n -- hier gleich n; zu lang ist 422 mit Feld und Grenze, nie 500.
2. Die Zuordnung Feld ↔ Spalte ist die des Befunds (Schemaname beginnt mit dem Modell, Feld = Spalte); der Wächter hält sie, `OFFEN` ist leer und darf nur
   kürzer werden.
3. Ein Update-Schema, das vom Antwortschema erbt, bekommt die Grenze in einer eigenen Definition, nie im Antwortschema.
4. Die Meldung auf der Seite nennt die Grenze, wenn die Antwort sie nennt („ist zu lang (höchstens n Zeichen)“).

#### Tests und Prüfung 1.9.350

Neu `tests/test_v750_laengen.py` (423 Tests: Wächter, je Feld ein Zeichen zu viel, die vier Routen des Befunds, Meldung). Auf dem Stand von 1.9.349 rot:
133 Felder lassen ein Zeichen zu viel durch, die vier Routen antworten 200 (live unter PostgreSQL 500), der Wächter nennt alle offenen Felder, die Meldung
ohne Grenze. Angepasste Erwartung (Regel 28): `test_v351_maengel` -- eine Ortsangabe aus 501 Zeichen gab bis 1.9.349 400 „Die Ortsangabe …“ aus
`app/defects.py`, jetzt greift die Grenze am Schema `DefectCreate.location` vorher: 422 mit Feld und Grenze (eigener Test
`test_zu_lange_ortsangabe_422_mit_feld_und_grenze`, der Fall aus der Parametrierung genommen). Die Seite der Mängel zeigt „Ortsangabe ist zu lang
(höchstens 500 Zeichen)“ (`defFeldnamen()`); die Prüfung in `app/defects.py` bleibt für andere Aufrufer.
Angepasste Erwartung des Klicktests (Regel 28): `klicktest_zahleneingaben`, Prüfung „422: Text“ -- „Fehler: Bitte die Eingabe prüfen – Bezeichnung
ist zu lang.“ -> „… ist zu lang (höchstens 120 Zeichen).“ (die Meldung nennt jetzt die Grenze; aufgefallen im Lauf aller Klicktests vor dem Commit).

### Umsetzung 1.9.351: Adressimport prüft jede Zeile (Punkt 2, F7)

- `app/address_import.py::zellen_grenzen()`: je Datei-Spalte die Grenze = die kürzeste Spalte, in die ihr Wert geht -- die Vorschau (`ImportedAddress`),
  Kunde, Lieferant, die Hauptadresse als Objekt (die Straße auch als Name eines Objekts aus der Arbeitsliste), die Kundennummer --, gelesen aus dem Modell
  (`app/spaltenlaenge.py::laenge()`). Dazu `zu_lang()`: die beiden Adressen aus „Mail“ (die zweite geht nur in `Customer.email_2`) und der zusammengesetzte
  Name (Anrede, Titel, Vorname, Name -> `Customer.name`, als Nachname, wenn „Name“ fehlt, und `Supplier.name`), wenn keiner seiner Teile schon zu lang ist.
- **Eine Zeile mit zu langem Wert** wird abgelehnt, nicht gekürzt; die übrigen gehen durch. Sie steht in der Vorschau mit der neuen Klasse „abgelehnt“:
  nur Zeilennummer und die Werte, die passen (Adressnummer, Vor- und Nachname, Ort -- zum Wiedererkennen), die Treffer in `validation_notes` (JSON, nur bei
  dieser Klasse). Bestätigen übernimmt sie nie; sie bleibt als Nachweis im Lauf wie „bereits importiert“ und geht beim Rückgängigmachen mit. Eine neue Spalte
  für die Zahl im Importlauf gibt es nicht (keine Migration) -- die Tabelle „Importläufe“ nennt abgelehnte Zeilen nicht.
- **Antwort** von `POST /api/address-import/upload` und `GET /api/address-import/preview`: `abgelehnt` -- je zu langer Zelle `zeile`, `feld` (Name der
  Datei-Spalte), `grenze`, `laenge`; `counts.abgelehnt`; die Zeile selbst mit dem Hinweis „Zeile abgelehnt – PLZ hat 21 Zeichen, höchstens 20.“
- **Seite** (`address_import.html`): Kennzahl „Abgelehnt (zu lang)“, darüber der Tabelle der Kasten „Abgelehnte Zeilen – werden nicht übernommen“ mit je
  einer Zeile „Zeile 3: PLZ hat 21 Zeichen – höchstens 20.“ und dem Rat (Datei korrigieren und neu hochladen, oder ohne diese Zeilen bestätigen); in der
  Tabelle die Zeile mit „Abgelehnt“; nach dem Bestätigen „…, 1 abgelehnt (nicht übernommen).“ Die Spalte „Hinweise“ hat eine Mindestbreite (bei 412 px rollt
  die Tabelle in ihrem Rahmen, ein langer Hinweis machte die Zeile sonst sehr hoch).
- Bis 1.9.350 schrieb der Import jede Zelle ungekürzt: SQLite nahm sie still an, unter PostgreSQL scheiterte die ganze Datei mit 500, ohne die Zeile zu
  nennen (Befund P11).

#### Festlegungen 1.9.351 (Bitte bestätigen)

1. Jede Zelle wird gegen die kürzeste Spalte geprüft, in die ihr Wert geht (Vorschau, Kunde, Lieferant, Objekt, Kundennummer), aus dem Modell gelesen;
   dazu die zweite Adresse aus „Mail“ und der zusammengesetzte Name.
2. Eine Zeile mit zu langem Wert wird abgelehnt, nie gekürzt; die übrigen Zeilen gehen durch.
3. Die abgelehnte Zeile steht in der Vorschau als „abgelehnt“ (nur Zeilennummer und die Werte, die passen) und bleibt nach dem Bestätigen als Nachweis im
   Lauf; übernommen wird sie nie.
4. Die Antwort nennt je zu langer Zelle Zeile, Feld, Grenze und Länge; die Seite zeigt die Liste, die Kennzahl und die Zahl beim Bestätigen.

#### Tests und Prüfung 1.9.351

Neu `tests/test_v751_adressimport_zeilen.py` (5 Tests): zu lange Zeile abgelehnt, die übrigen gehen durch, auch nach dem Neuladen, Bestätigen übernimmt sie
nicht; mehrere Zellen einer Zeile samt zweiter Mail-Adresse; zusammengesetzter Name (genau an der Grenze geht, ein Zeichen mehr nicht); jede Zelle genau an
ihrer Grenze bis in Kunde, Lieferant, Objekt und Kundennummer, mit einer Prüfung wie unter PostgreSQL (jeder Flush bricht ab, wenn ein Text länger als
seine Spalte ist) -- der Wächter für die Grenzen; die Probe P11 gegen PostgreSQL (Wegwerf-Schema). Mit dem Stand bis 1.9.350 (`351_1`) scheitert die Probe
unter PostgreSQL an `StringDataRightTruncation` (live 500), drei weitere Tests sind rot. Neu `scripts/klicktest_adressimport_abgelehnt.py` (17 Prüfungen,
Bilder 1440 und 412 px, hell und dunkel). Angepasste Erwartungen (Regel 28): `test_v364` -- die festen Werte von `imported_addresses.classification`
um „abgelehnt“ erweitert; `test_v460` -- der Kasten `.abgelehnt-box` in `KARTEN_OHNE_NAMEN` (Hinweiskasten mit der Ecke einer Karte; aufgefallen im vollen
Lauf vor dem Commit).

## Runde V2b ab 1.9.352: lesbare Fehler überall, Telefonbuch-Sortierung, Reihenfolge

V2a geprüft (3578f0f) und live; die 12 Festlegungen 1.9.349–1.9.351 bestätigt (17.11.2026). Antworten Tobias: „[object Object]“ umstellen -- Punkt 0
dieser Runde; Berater- und Mandantennummer nicht rot markieren, die Meldung unter den Feldern reicht.

Runde ab 1.9.352, je Punkt eine Version: **0** jede Seite, die eine abgelehnte Antwort zeigt, nutzt fehlerText() (die Vorlagen aus H1 und CLAUDE.md),
Wächter: keine Seite kann „[object Object]“ zeigen (1.9.352); **1** F6 Telefonbuch-Sortierung: Listen nach Namen ohne Groß- und Kleinschreibung, Umlaute
beim Grundbuchstaben (Ä wie A, ß wie ss), unter SQLite und PostgreSQL gleich, unabhängig von der Kollation des Servers (C.UTF-8); Liste der betroffenen
Listen in den Bericht; eine Migration ist erlaubt, wenn der Weg sie braucht; Bilder der Kundenliste mit Umlauten, Kleinbuchstaben und leerem Namen, 1440
und 412 px, hell und dunkel (1.9.353); **2** Reihenfolge: die 26 Beziehungen und 49 Abfragen aus dem Befund (Abschnitt 3 E) sichten, jede Liste, die eine
Antwort zeigt, bekommt eine feste Reihenfolge, leere Werte ausdrücklich ans Ende, Wächter (1.9.354).

### Umsetzung 1.9.352: jede Seite zeigt eine abgelehnte Antwort über fehlerText() (Punkt 0)

- **Bestand:** 37 Vorlagen zeigten eine abgelehnte Antwort an `fehlerText()` vorbei -- meist `throw Error(d.detail || r.statusText)` in der eigenen
  `api()`: eine 422-Liste wurde zu „Fehler: [object Object]“, ein Status ohne Text zu Englisch („Unprocessable Entity“). Dazu eigene Ersatzlösungen (nur
  ein Text-`detail`, sonst ein fester Satz) in Versand, Checklisten-Sektion, Leiste, Anmeldung.
- **Umgestellt:** jede dieser Stellen ruft `fehlerText(body, status)`; wo die Seite bisher einen eigenen Satz zeigte, wenn die Antwort keinen Text trug
  („Anmeldung fehlgeschlagen.“, „Für deine Rolle nicht verfügbar.“, „Keine Wartungshistorie für dieses Objekt.“, „Fehler beim Anlegen.“, „Fehler beim
  Speichern.“, im Versand bei 5xx der Satz zum Versandprotokoll), bleibt er über den neuen vierten Parameter `ersatz`. Ein Text-`detail` erscheint wie
  bisher unverändert. Neu ist nur, was vorher roh oder englisch war.
- **Einbinden:** jede Vorlage, deren eigenes Skript `fehlerText()` aufruft, bindet `_fehlertext.html` selbst ein -- 31 kamen dazu, auch die Bausteine
  Leiste, Versand, Checklisten-Sektion, Zeitliste, Abnahme und Mängel. Damit eine Seite den Baustein doppelt einbinden darf (selbst und über einen
  Baustein), trägt er auf oberster Ebene nur `var` und eine Funktionsdeklaration (`_FEHLERARTEN` war `const`: ein zweites Einbinden wäre ein SyntaxError).
- **Ausnahme:** `master_data_form.html` liest `detail` als Objekt (Teams: Rückfrage „laufende Gruppenzeit“ aus `detail.code`/`detail.message`); die
  Meldung jeder anderen Ablehnung zeigt seine `api()` über `fehlerText()` -- in `AUSNAHMEN` mit Grund, die Liste darf nur kürzer werden.
- **Wächter** `tests/test_v752_fehlertext_ueberall.py` (über die Skripte jeder Vorlage, Tokenizer aus `tests/vorlagen_js.py`): Regel A -- keine Vorlage liest
  `.detail` (außer dem Baustein und `AUSNAHMEN`); Regel B -- jeder Zweig `if(!x.ok)`, der etwas zeigt oder wirft (throw, Error, alert, textContent,
  innerHTML, confirm, eine Funktion „…Fehler…“), ruft `fehlerText()`; still endende Zweige (`return []`, `null`) zeigen nichts. Dazu: wer `fehlerText()`
  aufruft, bindet ihn ein; der Baustein gibt für keine Form der Antwort „[object Object]“ zurück und lässt sich zweimal laden (node).
- Seiten ohne eigene Feldnamen (`FELDNAMEN`) nennen in einer 422 den Namen des Felds aus der Schnittstelle („priority ist zu lang …“) -- wie seit 1.8.35
  jede Seite ohne Feldnamen; nicht geändert, Hinweis im Bericht.

#### Festlegungen 1.9.352 (Bitte bestätigen)

1. Jede Vorlage zeigt eine abgelehnte Antwort nur über `fehlerText()`; keine liest `.detail` an ihm vorbei (Ausnahme mit Grund in `AUSNAHMEN`, die Liste
   darf nur kürzer werden).
2. Jeder Zweig einer Prüfung `!x.ok`, der etwas zeigt oder wirft, ruft `fehlerText()`; still endende Zweige bleiben still.
3. Wer `fehlerText()` im eigenen Skript aufruft, bindet `_fehlertext.html` selbst ein, auch ein Baustein; der Baustein lässt sich mehrfach einbinden.
4. `fehlerText()` nimmt einen Rückfalltext (`ersatz`) für Antworten ohne verwertbare Meldung; die bisherigen eigenen Sätze der Seiten bleiben so erhalten.

#### Tests und Prüfung 1.9.352

Neu `tests/test_v752_fehlertext_ueberall.py` (5 Tests: Regel A, Regel B, Einbinden, Probe jeder Form des Wächters, Baustein in node). Auf dem Stand von
1.9.351 meldet der Wächter 103 Stellen in 37 Vorlagen (Regel A und B). Angepasste Erwartung (Regel 28): `test_v411_vorweg`, Feierabend in `/mobil`
bei 502 ohne JSON -- „HTTP 502.“ -> „Serverfehler (502) …“ (Text aus `fehlerText()`); der Test führt das Skript in node jetzt mit dem Baustein aus.

### Umsetzung 1.9.353: Listen nach Namen wie im Telefonbuch (Punkt 1, F6)

- **Bestand:** 39 Abfragen sortierten in der Datenbank roh nach einer Namensspalte (`order_by(Customer.name)` …), dazu die Beziehung Objekt → Dachflächen
  (`order_by="RoofArea.name"`), sieben Quellen der Büro-Suche und Adressbuch/Beteiligte über `func.lower()` (unter SQLite nur ASCII). SQLite sortierte binär
  (Großbuchstaben vor Kleinbuchstaben, Umlaute ans Ende, ein leerer Name zuerst), PostgreSQL nach seiner Kollation (Befund P4). 17 Stellen sortierten in Python
  über `casefold()`/`lower()` oder roh (Umlaute ans Ende, leere Namen zuerst).
- **Der Weg:** `app/telefonbuch.py` -- ein Sortierschlüssel je Name: Leerzeichen am Rand weg, A–Z auf a–z und jeder Buchstabe mit Umlaut oder Akzent auf
  seinen Grundbuchstaben (eine Tabelle, `GRUNDBUCHSTABEN`), ß/ẞ zu ss, Æ zu ae, Œ zu oe, leer = NULL. In der Datenbank die Funktion `telefonbuch(text)`:
  unter SQLite die Python-Funktion an jeder Verbindung (Ereignis „connect“ an der Klasse Engine), unter PostgreSQL eine SQL-Funktion aus derselben Tabelle --
  auf dem Server von der Migration `9e4b2c7d1a35` angelegt (Text wörtlich, keine Tabelle, keine Daten), sonst nach jedem `create_all()` (Testschemas,
  lokale Entwicklung). Kein `lower()` der Datenbank (hängt unter PostgreSQL an der Zeichenklassifizierung des Servers); verglichen wird der Schlüssel unter
  PostgreSQL mit `COLLATE "C"` (byteweise, wie SQLite) -- die lokale Instanz (German_Germany.1252) ordnete „Müller Bau“ und „Müller-Bau“ sonst umgekehrt.
- **Im Code:** `.order_by(*nach_namen(Customer.name), Customer.id)` (leere Namen über `nulls_last()` ans Ende, die ID als letzter Schlüssel), in Python
  `sortierwert(x.name)`. `_count_and_fetch()` der Büro-Suche nimmt dafür auch ein Tupel. Die Spalte bleibt, nach der eine Liste schon sortierte -- die
  Kundenliste nach dem ganzen Namen samt Anrede (Frage im Bericht).
- **Wächter** `tests/test_v753_telefonbuch.py`: keine Sortierung nach einer Namensspalte (`name`, `display_name`, `first_name`, `last_name`, `label`,
  `title`, `company_name`, `kurzname`, `username`) an `nach_namen()` vorbei -- `order_by`, Beziehungen, die Suche --, danach die ID; `func.lower()`/`upper()`
  nur in einem Vergleich; in Python kein `casefold()`/`lower()` und kein roher Name als Sortierschlüssel. `AUSNAHMEN` ist leer und darf nur kürzer werden.
- **Im Browser** sortieren vier Listen selbst (`localeCompare(…, 'de')`: Geräte und Mitglieder einer Kolonne in der Plantafel, Kategorien der Projekte,
  Bereiche der Änderungshistorie) -- schon ohne Groß- und Kleinschreibung und mit Umlaut beim Grundbuchstaben, unabhängig von der Datenbank; nicht geändert.
- **Fund im Klicktest (gebaut):** die Betriebsmittel-Liste (`list_assets()`) sortierte in der Datenbank nach `OperationalAsset.name` -- bei einem
  Betriebsmittel mit Gerät ist die Spalte leer, der Name kommt erst beim Lesen aus dem Gerät (`resolve_asset_identity()`). Solche standen unter SQLite
  vorn (in der Reihenfolge des Anlegens), unter PostgreSQL hinten, nie nach ihrem Namen; mit „leer ans Ende“ wurde es sichtbar (`klicktest_geraete`
  rot). Jetzt nach dem aufgelösten Namen in Python, wie schon die Auswahl im Einsatzbericht (`list_selectable_assets()`).
- **Befunde (nicht gebaut):** ein Nachname aus Leerzeichen geht durch (`CustomerCreate`: `min_length=1` zählt das Leerzeichen), der Name wird leer -- die
  Liste zeigt einen Kunden ohne Namen; ein Kunde mit Nachnamen "" (nur über die Datenbank) lässt die ganze Kundenliste mit 500 scheitern (`CustomerOut` erbt
  `min_length=1`, steht in `BEKANNT` von `test_v673`).

#### Festlegungen 1.9.353 (Bitte bestätigen)

1. Listen nach Namen sortieren ohne Groß- und Kleinschreibung (A–Z wie a–z).
2. Umlaute und Akzente beim Grundbuchstaben (Ä wie A, é wie e, ł wie l; Tabelle `GRUNDBUCHSTABEN` in `app/telefonbuch.py`); andere Schriften bleiben, wie sie sind.
3. ß und ẞ wie ss; Æ wie ae, Œ wie oe.
4. Leere Namen (keiner, leer, nur Leerzeichen) stehen am Ende; Leerzeichen am Anfang und Ende zählen nicht.
5. SQLite, PostgreSQL und Python rechnen denselben Schlüssel aus einer Tabelle: unter SQLite an jeder Verbindung, unter PostgreSQL aus der Migration
   `9e4b2c7d1a35` (Text wörtlich -- eine geänderte Tabelle braucht eine neue Migration) und nach jedem `create_all()`.
6. Unabhängig von der Kollation des Servers: unter PostgreSQL wird der Schlüssel mit `COLLATE "C"` verglichen.
7. Jede Sortierung nach einer Namensspalte in der Datenbank geht über `nach_namen()`, danach die ID als letzter Schlüssel; kein `lower()` zum Sortieren.
8. Jede Sortierung nach Namen in Python geht über `sortierwert()`.
9. Sortiert wird nach derselben Spalte wie bisher -- die Kundenliste weiter nach dem ganzen Namen samt Anrede.
10. Die vier Listen, die der Browser selbst sortiert (`localeCompare(…, 'de')`), bleiben.
11. Betriebsmittel sortieren nach dem aufgelösten Namen (mit Gerät der Name des Geräts), nicht nach der Spalte.

#### Tests und Prüfung 1.9.353

Neu `tests/test_v753_telefonbuch.py` (30 Tests: 14 Fälle des Schlüssels, jedes Zeichen der Tabelle, SQLite und PostgreSQL rechnen wie Python, Kollation,
Migration -- Text gleich, angelegt und wieder entfernt --, `create_all()` legt an, Kundenliste unter SQLite und PostgreSQL, Wächter in vier Teilen mit Probe
jeder Form) und Klicktest `scripts/klicktest_telefonbuch.py` (15 Prüfungen: Kundenliste, API und Büro-Suche in der Reihenfolge des Telefonbuchs, der leere
Name zuletzt, Bilder 1440 und 412 px, hell und dunkel); dazu die Betriebsmittel nach dem aufgelösten Namen. Angepasste Erwartung (Regel 28):
`klicktest_geraete`, „Liste: Plantafel und nur Plantafel“ -- „Pritsche, Leiter, Rüttelplatte, Hubsteiger“ (die mit Gerät vorn, in der Reihenfolge
des Anlegens) -> „Leiter, Pritsche, Rüttelplatte, Hubsteiger“ (nach Namen; „nur Plantafel“ weiter am Ende).

### Umsetzung 1.9.354: jede Liste mit fester Reihenfolge, leere Werte am Ende (Punkt 2)

- **Gesichtet:** die 26 Listen-Beziehungen ohne `order_by` und die Abfragen ohne `order_by` aus dem Befund (Abschnitt 3 E). Der Befund zählte nur `.all()`
  und übersprang grob jede Zeile mit `set(`, `{` oder `len(` (49); der Wächter liest den Baum und zählt auch Schleifen über `db.scalars(select …)` und
  `list(…)` -- 127 Stellen, deren Ergebnis eine Folge ist, dazu 96, deren Ergebnis direkt eine Menge, Summe oder Zuordnung wird (zählen nicht).
- **Beziehungen (26):** jede bekommt eine Reihenfolge -- ohne eigene Ordnung die des Anlegens (ID), mit Reihenfolgefeld `sort_order, id` (Fotos eines Berichts
  und eines Befunds, wie der Code sie ohnehin sortiert). Darunter die beiden sichtbaren aus dem Befund: `Project.quotes` (`GET /api/projects/{id}/quotes`,
  Befund P2b) und `ServiceReport.findings`.
- **Abfragen (127):** 66 bekommen ein `order_by` (meist die ID): Listen und Meldungen (z. B. die Rechnungsnummern in „Abgleich gesperrt“ und „Abschließen“, die
  erste blockierende Abnahme beim Verwerfen einer Unterschrift, die Abzüge, die Dokumente am Objekt, „zur Mahnung fällig“), Lösch- und Änderungsschleifen (ihre
  Reihenfolge landet in der Änderungshistorie), Kopien (die Positionen eines kopierten Angebots behalten ihre Reihenfolge), Erinnerungen, die Aufgaben anlegen,
  und Zeilensperren (`pausen_neu_rechnen()`, Zuordnungen einer Zahlung: feste Reihenfolge gegen Verklemmen). 61 bleiben ohne, mit Grund in `OHNE_REIHENFOLGE`
  (`tests/test_v754_reihenfolge.py`): Zuordnung je Schlüssel, Menge, Summe/Anzahl/min/max, nur Prüfung, nur neu geladen, danach vollständig sortiert. „Rest am
  Kunden“ (`unallocated_by_customer()`) sortiert bei gleichem Betrag nach dem Kunden.
- **Leere Werte (14):** jedes `order_by` auf einer Spalte, die leer sein darf, sagt `nulls_last()` -- 13 Abfragen und die Beziehung Betriebsmittel →
  Prüffristen. Sichtbar unter PostgreSQL: in den Zeitbuchungen (`list_entries()`, je Tag nach Beginn absteigend) stand eine Dauer-Buchung ohne Beginn vorn,
  unter SQLite hinten -- jetzt überall hinten. Wo schon `is_(None)` davor sortierte (Aufgaben, Befunde, Aufgaben der Arbeitsvorbereitung), ändert sich nichts.
- **Wächter** `tests/test_v754_reihenfolge.py`: jede Listen-Beziehung mit `order_by`; jede Abfrage, deren Ergebnis eine Folge ist, mit `order_by` oder in
  `OHNE_REIHENFOLGE` (Zahl je Funktion, die Liste stimmt genau); jedes `order_by` auf einer Spalte, die leer sein darf, mit `nulls_last()` (oder `nulls_first()`
  mit Grund in `NULLS_FIRST`, leer) -- in Abfragen und Beziehungen; dazu zwei Verhaltenstests gegen PostgreSQL (P2b, P5).
- **Befund (nicht gebaut):** 54 von 243 `order_by` enden nicht auf der ID -- bei Gleichstand (gleicher Status, gleiches Datum, gleicher Rang) ist die Reihenfolge
  unter PostgreSQL weiter offen (z. B. die Befunde nach Schwere und Wiedervorlage). Nicht Teil von Abschnitt 3 E; Vorschlag im Bericht.

#### Festlegungen 1.9.354 (Bitte bestätigen)

1. Jede Listen-Beziehung hat eine Reihenfolge: ohne eigene Ordnung die des Anlegens (ID), mit Reihenfolgefeld `sort_order`, dann ID.
2. Jede Abfrage, deren Ergebnis eine Folge ist, hat ein `order_by` -- auch Lösch- und Änderungsschleifen, Kopien, Erinnerungen und Zeilensperren.
3. Ohne `order_by` nur, wo das Ergebnis eine Zuordnung, Menge, Summe, Prüfung wird, nur neu geladen oder danach vollständig sortiert wird -- jede solche Stelle
   steht mit Grund in `OHNE_REIHENFOLGE`, die Liste stimmt genau.
4. Leere Werte stehen beim Sortieren ausdrücklich am Ende (`nulls_last()`), aufsteigend wie absteigend, in Abfragen und Beziehungen; `nulls_first()` nur mit Grund.
5. Der Wächter zählt jede Form, die eine Folge liefert (`.all()`, Schleife, `list()`), nicht nur `.all()` wie der Befund.

#### Tests und Prüfung 1.9.354

Neu `tests/test_v754_reihenfolge.py` (8 Tests: Abfragen mit `order_by`, `OHNE_REIHENFOLGE` genau, Beziehungen, leere Werte in Beziehungen und Abfragen, Probe
jeder Form, die Angebote eines Projekts nach einer Statusänderung und die Dauer-Buchung am Ende ihres Tags -- beide gegen PostgreSQL).

## Runde V2c ab 1.9.355: Kundenliste, ID zuletzt, leere Pflichttexte, Zahlenbereiche, Suchmuster

V2b geprüft (e74e5aa) und live; die 20 Festlegungen 1.9.352–1.9.354 bestätigt (17.11.2026). Antworten Tobias: **F1** ja -- die Kundenliste nach Nachname,
dann Vorname, ohne Anrede und Titel (Firmen nach ihrem Namen); **F2** ja, in dieser Runde; **B1** und **B2** beide beheben.

Runde ab 1.9.355, je Punkt eine Version: **0** F1 und F2 (die 54 Sortierungen enden auf der ID; Wächter) (1.9.355); **1** B1: `CustomerOut` ohne Prüfung wie
die übrigen Antwortschemas; B2: bei allen Pflicht-Textfeldern Leerzeichen am Rand vor der Prüfung entfernen -- nur Leerzeichen heißt 422; Wächter (1.9.356);
**2** Zahlenbereiche: jedes Eingabefeld, das in Numeric(p,s) oder Integer geht, bekommt passende Grenzen (die 98 und 150 aus dem Befund, Abschnitt 3 G); zu
groß heißt 422 mit Feld und Grenze, nie 500; Wächter wie bei den Längen (1.9.357); **3** Suchmuster: ein Baustein für LIKE mit geschützten Zeichen und
escape wie `app/search.py:198`, für alle 18 Muster (1.9.358); **4** Suche wie die Sortierung: die Büro-Suche vergleicht über `telefonbuch()`, sodass
„muller“, „Müller“ und „MÜLLER“ dasselbe finden -- unter SQLite und PostgreSQL gleich; geht das nur mit großem Umbau: Vorschlag in den Bericht, erst fragen.

### Umsetzung 1.9.355: Kundenliste nach Nachname, dann Vorname; jede Sortierung endet auf der ID (Punkt 0, F1 und F2)

- **Kundenliste (F1):** `GET /api/customers` sortiert nach `nach_namen(Customer.last_name, Customer.first_name)`, dann ID -- statt nach dem ganzen Namen
  samt Anrede und Titel („Frau Dr. Erika Probe“ stand unter F). Eine Firma trägt ihren Namen im Nachnamen (Vorname leer) und steht damit unter ihrem Namen.
  Die Kunden der Büro-Suche in derselben Reihenfolge (`app/search.py::_search_customers()`). Ohne Vorname steht ein Kunde nach denen mit Vornamen bei gleichem
  Nachnamen (leere Werte ans Ende, `nach_namen()` wie seit 1.9.353). Keine Migration: beide Spalten gibt es, `telefonbuch()` rechnet sie. Unverändert: das
  Adressbuch sortiert einen Eintrag mit Verweis auf einen Kunden weiter nach dem angezeigten Namen (`contact_sort_columns()`).
- **ID zuletzt (F2):** 54 `order_by` endeten nicht auf der ID (B3 im Bericht V2b; der Wächter zählt 57, darunter drei, die schon auf `modell.id` enden). 50 enden
  jetzt auf der ID -- bei absteigender Sortierung absteigend (Dokumente „neueste zuerst“, Rechnungen, Revisionen, laufende Zeit). Zwei davon brauchten die ID
  in Auswahl bzw. Gruppe: die Rechnungsnummern je Position (`app/order_locks.py::billed_items()`, DISTINCT verlangt die Sortierspalte in der Auswahl -- je
  Rechnung eine Nummer, das Ergebnis bleibt gleich) und der Auftrag mit festgeschriebenem Vertrag beim Kundenwechsel
  (`app/project_participants.py::check_client_change()`, GROUP BY über ID und Nummer -- die Nummer ist eindeutig). Ohne ID bleiben vier, mit Grund in
  `AUSNAHMEN`: zwei Abfragen mit GROUP BY je Checkliste (sortiert nach ihrer ID), der Helfer der Büro-Suche (`_count_and_fetch()`, jeder Aufruf gibt die ID mit)
  und die Werte einer Nummernspalte (`highest_existing()`). Dazu 18 Listen-Beziehungen (Positionen, Abschnitte, Revisionen, Fassungen, Mahnungen,
  Pausenregeln, Optionen, Dokumente): jetzt `…, X.id`.
- **Wächter** `tests/test_v755_kundenliste_und_id.py`: jedes `order_by` unter `app/` und jeder Aufruf von `_count_and_fetch()` endet auf der ID
  (`X.id` oder Primärschlüssel; `*(…)` eines Tupels aufgelöst) -- ohne nur mit Grund in `AUSNAHMEN`, die Liste stimmt genau; jede Listen-Beziehung mit
  Reihenfolge endet auf ihrem Primärschlüssel. Dazu die Kundenliste und die Büro-Suche (SQLite), die Kundenliste und zwei am selben Tag fällige
  Wartungsverträge gegen PostgreSQL -- ohne ID tauschten sie nach einer Änderung des ersten die Plätze (Gegenprobe `355_4`).

#### Festlegungen 1.9.355 (Bitte bestätigen)

1. Die Kundenliste sortiert nach Nachname, dann Vorname wie im Telefonbuch, ohne Anrede und Titel; eine Firma steht unter ihrem Namen (im Nachnamen).
2. Die Kunden der Büro-Suche stehen in derselben Reihenfolge wie die Kundenliste.
3. Ohne Vorname steht ein Kunde nach denen mit Vornamen bei gleichem Nachnamen (leere Werte ans Ende); gleicher Name in der Reihenfolge des Anlegens.
4. Jedes `order_by` endet auf der ID, bei absteigender Sortierung absteigend -- ohne nur mit Grund in `AUSNAHMEN` (GROUP BY je ID, nur der Wert einer Spalte,
   Helfer der Suche), die Liste stimmt genau.
5. Jede Listen-Beziehung mit Reihenfolge endet auf der ID.
6. Jeder Aufruf der Büro-Suche (`_count_and_fetch()`) gibt die ID als letzten Schlüssel mit.
7. Schließen DISTINCT oder GROUP BY die ID aus, kommt sie in Auswahl bzw. Gruppe, wenn das Ergebnis gleich bleibt.

#### Tests und Prüfung 1.9.355

Neu `tests/test_v755_kundenliste_und_id.py` (9 Tests). Angepasst: `tests/test_v753_telefonbuch.py`, die beiden Kundenlisten-Tests -- der Kunde ohne Namen
bekommt den Nachnamen " " (wie über die Oberfläche) statt "-", weil die Liste jetzt nach dem Nachnamen sortiert; die Erwartung bleibt. Klicktest
`klicktest_telefonbuch.py`: 17 statt 15 Kunden (dazu „Herr Bernd Abel“ und „Frau Dr. Erika Probe“), erwartet „Herr Bernd Abel, apfelbaum Gartenbau, …,
Ökohaus Probe, Frau Dr. Erika Probe, Straßenbau Probe, …“ statt der Liste ohne die beiden.
