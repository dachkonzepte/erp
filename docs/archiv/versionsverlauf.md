# Migrationsketten- und Testlauf-Historie (aus "Stand bei Übergabe")

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

- Migrationskette Kopf weiterhin `1375eeeea2fa` (1.7.6 selbst brauchte keine eigene Migration --
  reine Business-Logik-Umstellung in `app/outlook_calendar_sync.py`, siehe Abschnitt
  "Kalender-Modul" -> "Stufe 2" -> "Nachtrag (seit 1.7.6)" unten; die Migration `1375eeeea2fa`
  selbst ist weiterhin "calendar event outlook etag rename", reine
  Spalten-Umbenennung `calendar_events.outlook_change_key` -> `outlook_etag`, kein
  Datenverlust-Risiko -- die Spalte trug zu diesem Zeitpunkt bei keiner Zeile einen von Graph
  tatsächlich nutzbaren Wert, siehe Abschnitt "Kalender-Modul" -> "Stufe 2" -> "Nachtrag (seit
  1.7.5)" unten) -- davor `3e187156fa80` ("calendar event outlook change key", neue, nullable
  Spalte `calendar_events.outlook_change_key` -- der uhrzeitunabhängige Echo-Erkennungsmerker für
  den 1.7.3-Nachtrag "Schaukelnder Termin", siehe Abschnitt "Kalender-Modul" -> "Stufe 2" ->
  "Nachtrag (seit 1.7.3)" unten) -- davor `c137c16e9a5c` ("outlook calendar sync retry marker",
  neue, nullable
  Spalte `calendar_events.outlook_synced_at` -- der pro-Termin-Merker für die 1.7.2-Push-
  Wiederholung, siehe Abschnitt "Kalender-Modul" -> "Stufe 2" -> "Nachtrag (seit 1.7.2)" unten) --
  davor `6573d677bc1d` ("outlook calendar sync stufe 2", neue Tabellen
  `outlook_sync_settings`/`outlook_calendar_sync_state` PLUS die neue, nullable Spalte
  `app_users.outlook_mailbox` -- siehe Abschnitt "Kalender-Modul" -> "Stufe 2" unten) -- davor
  `7974647223ea` ("calendar events kalender modul", neue Tabelle
  `calendar_events` -- siehe Abschnitt "Kalender-Modul" unten) -- davor `d87d5bc04b69` ("ai
  fundament settings and call log", neue
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


- Tests: **1844 passed, 2 skipped** (die beiden übersprungenen sind opt-in PostgreSQL-Varianten
  des Schaukel-Tests, siehe unten -- übersprungen ohne gesetztes `ERP_TEST_POSTGRES_URL`; seit
  1.3.55 sonst wieder vollständig grün ohne `xfail` -- der Audit-Test des Rechtekonzepts steht bei
  null unklassifizierten Endpunkten und ist ein harter Test, siehe dort), zuletzt am 26.09.2026
  (1.7.6, Kalender-Modul Stufe 2, Nachtrag -- eine weitere Produktions-Diagnose zeigte trotz 1.7.5
  weiterhin unnötige Pushes; empirisch (echte SQL-Mitschnitte gegen SQLite UND PostgreSQL)
  nachgewiesen, dass `Column(..., onupdate=datetime.utcnow)` bei JEDER `UPDATE`-Anweisung gegen
  `calendar_events` greift, sobald `updated_at` nicht explizit in `.values()` steht -- ein bloßes
  Weglassen der Spalte (erster, verworfener Fix-Entwurf) reicht NICHT, ein bereits bestehender
  Test widerlegte das sofort. Die tatsächlich wirksame Lösung: `updated_at` wird in jedem reinen
  Sync-Buchhaltungs-Schreibvorgang IMMER explizit auf eine Selbstreferenz gesetzt
  (`updated_at=CalendarEvent.updated_at`) -- unterdrückt `onupdate` zuverlässig, ohne den
  aktuellen Wert vorher in Python kennen zu müssen. Neue Funktion `_write_sync_bookkeeping()`
  (löst `_mark_synced()` ab) bricht zusätzlich sofort ab, wenn eine Zeile beim Aufruf noch eine
  andere, über `setattr()` erzeugte Dirty-Markierung trägt (würde die Selbstreferenz über einen
  vorangehenden Autoflush aushebeln, ebenfalls empirisch bestätigt). Ehrlich festgehalten: ein
  exakter Nachbau der in der Diagnose gezeigten PERSISTIERTEN Werte gelang trotz umfangreicher
  Versuche weiterhin nicht -- der jetzt gefundene und behobene `onupdate`-Mechanismus trat im
  eigenen Reparaturversuch auf, nicht nachweisbar in der 1.7.1-1.7.5-Fassung, der neue
  Mechanismus ist aber unabhängig davon nachweislich exakt (kein Drift). 2 neue Tests direkt gegen
  `_write_sync_bookkeeping()`, der bestehende Sieben-Läufe-Schaukel-Test läuft seither mit einer
  GENUINE NEUEN Session je Lauf statt einer wiederverwendeten. Siehe Abschnitt "Kalender-Modul" ->
  "Stufe 2" -> "Nachtrag (seit 1.7.6)" unten; davor 1.7.5, Kalender-Modul Stufe 2, Nachtrag -- die
  tatsächliche Ursache des seit 1.7.3 gemeldeten
  Schaukelns gefunden: `changeKey` kommt in Graphs Delta-Antworten strukturell NIE an (`$select`
  wird für Kalender-Delta-Abfragen laut Microsoft-Dokumentation ignoriert, jede von Microsoft
  selbst gezeigte Beispiel-Delta-Antwort trägt `@odata.etag`, nie `changeKey`) -- die 1.7.3/1.7.4-
  Fassung der Echo-Erkennung konnte für ihren eigentlichen Zweck deshalb nie einen Treffer
  liefern. Kompletter Wechsel von `changeKey` auf `@odata.etag` (Spalte umbenannt zu
  `CalendarEvent.outlook_etag`, Migration `1375eeeea2fa`, kein Datenverlust-Risiko), dabei ein
  zweiter, unabhängiger Diagnose-Anzeigefehler behoben (die "push erfolgreich"-Zeile zeigte den
  Wert vor statt nach dem Push). `FakeGraphServer` (Testdatei) bildete den Fehler bis dahin selbst
  ab (lieferte `changeKey` auch im Delta) -- korrigiert, liefert seither realistisch nur noch
  `@odata.etag` im Delta. 2 neue Tests, siehe Abschnitt "Kalender-Modul" -> "Stufe 2" -> "Nachtrag
  (seit 1.7.5)" unten; davor 1.7.4, Kalender-Modul Stufe 2, Nachtrag "Zweite Untersuchungsrunde" --
  das Schaukeln trat trotz changeKey (1.7.3) auf dem Produktivserver weiterhin auf; vier gezielte
  Prüfungen (Datenbank/
  Zeitzone/Präzision von updated_at/outlook_synced_at, der Schaukel-Test gegen die echte, lokale
  PostgreSQL-Instanz -- MIT und OHNE changeKey --, ob Graphs Delta-Antwort changeKey überhaupt
  mitliefert, eine abschaltbare Diagnosezeile je Termin) ergaben KEINEN reproduzierbaren
  Postgres-spezifischen Fund -- ehrlich als "Ursache nicht abschließend bewiesen" festgehalten,
  dafür ein unabhängiger, real gefundener Python-Versions-Härtungsbedarf in
  `_parse_graph_datetime()` behoben (Microsofts 7-stellige Bruchteilsekunden wurden vor Python
  3.11 nicht geparst) und die neue, abschaltbare Diagnosezeile (`ERP_OUTLOOK_SYNC_DIAGNOSTICS=1`)
  als Werkzeug für den Betreiber übergeben, der Schaukel-Test läuft jetzt zusätzlich opt-in gegen
  PostgreSQL, 7 neue Tests, siehe Abschnitt "Kalender-Modul" -> "Stufe 2" -> "Nachtrag (seit
  1.7.4)" unten; davor 1.7.3, Kalender-Modul Stufe 2, Nachtrag "Schaukelnder Termin" -- ein
  gemeldeter, über mehrere Sync-Läufe pendelnder Termin geprüft (Ursache mit den hier verfügbaren
  Mitteln nicht abschließend reproduzierbar, `_mark_synced()` empirisch als korrekt bestätigt),
  zusätzlich zur bestehenden Zeitstempel-Heuristik eine uhrzeitunabhängige, exakte Echo-Erkennung
  über Graphs eigenen changeKey ergänzt -- neue Spalte CalendarEvent.outlook_change_key --, dafür
  erstmals eine Graph-Attrappe mit echtem, über mehrere Läufe fortgeschriebenem Zustand statt rein
  statischer Antworten, 6 neue Tests, siehe Abschnitt "Kalender-Modul" -> "Stufe 2" -> "Nachtrag
  (seit 1.7.3)" unten; davor 1.7.2, Kalender-Modul Stufe 2, Nachtrag -- Outlook-
  Vertraulichkeit (sensitivity) auf is_private abgebildet, zwei echte Push-Wiederholungsfehler
  behoben (verlorene Zuordnung bei einem Nachbar-Fehlschlag, ein fälschlich als "aktuell"
  erkannter Termin wegen eines rein postfachweiten statt pro-Termin-Vergleichs -- neue Spalte
  CalendarEvent.outlook_synced_at), Serientermine-Vorschlag dokumentiert (nicht gebaut), exakte
  Cron-Zeile inkl. .env-Laden, 11 neue Tests, siehe Abschnitt "Kalender-Modul" -> "Stufe 2" ->
  "Nachtrag (seit 1.7.2)" unten; davor 1.7.1, Kalender-Modul Stufe 2 -- Outlook-Kalendersynchronisation
  über Microsoft Graph, Einrichtung über Exchange "RBAC for Applications" statt globaler
  Admin-Zustimmung, 32 neue Tests (`tests/test_v297_outlook_calendar_sync.py`), siehe Abschnitt
  "Kalender-Modul" -> "Stufe 2" unten; davor 1.7.0, Kalender-Modul Stufe 1 -- Büro-Termine,
  bewusst getrennt von der Plantafel, 22 neue Tests (`tests/test_v296_calendar_events.py`), siehe
  Abschnitt "Kalender-Modul" unten; davor 1.6.3, Beleg-Upload schon beim Anlegen einer Eingangsrechnung --
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
