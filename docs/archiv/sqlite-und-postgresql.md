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
