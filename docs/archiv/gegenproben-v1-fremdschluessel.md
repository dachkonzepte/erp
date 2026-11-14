# Gegenproben Runde V1 „Fremdschlüssel in der Test-SQLite“ (ab 1.9.338)

Je neue Festlegung eine Gegenprobe (Regel 24): der Schutz wird ausgehebelt (unter `app/` mit dem Marker `GEGENPROBE`), die genannten Tests müssen rot
werden (nur FAILED zählt, ein Sammel- oder Aufbaufehler nicht), danach die Datei byte-genau zurück (Prüfsumme). Wo keine möglich ist, steht der Grund in
der Tabelle. Herleitung: `docs/archiv/sqlite-und-postgresql.md`.

## 1.9.338 (Punkt 1): Testdaten ohne erfundene Eltern

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Auftrag der Testdaten mit echtem Angebot, Wächter gegen erfundene | `make_order_with_item` (v133) wieder mit `source_quote_id=1` (`338_1`) | 2 rot: v738::test_ein_auftrag_der_testdaten_hat_sein_angebot, test_kein_order_unter_tests_mit_erfundenem_angebot |
| Nr. 2 – `router_test_client` legt das Konto an | das Anlegen in `tests/conftest.py` abgeschaltet (`338_2`) | 1 rot: v738::test_router_test_client_legt_das_konto_an |
| Nr. 3 – Migrationsproben mit echten Eltern, ohne Abschalten | prüft erst das PRAGMA (1.9.339): Gegenprobe dort | siehe 1.9.339 |
| Nr. 4 – Verteidigung mit ungespeichertem Objekt geprüft | die Verteidigung in `resolve_account_display()` entfernt (`338_4`, `app/auth.py`) | 1 rot: v254::test_resolve_account_display_falls_back_to_display_name_when_employee_id_points_nowhere |
| Nr. 5 – Prüfungen gelten für beide Datenbanken | keine Aushebelung (Aufbau der Tests); Nachweis: dieselben Tests unter PostgreSQL vorher rot (Befund: v380 9, v402 1, v539 1), jetzt grün (gezielter Lauf) | vorher 11 rot, jetzt 0 |
| Nr. 6 – Spaltenprüfungen weg, der Import behält seinen Lauf | die Prüfung über die Engine nach dem Flush des Importlaufs wieder eingesetzt (`338_6`, `app/service.py`) | 1 rot: v738::test_leistungsimport_behaelt_seinen_importlauf |

4 Gegenproben, alle rot; alle Dateien byte-gleich zurück.

## 1.9.339 (Punkt 2): PRAGMA foreign_keys=ON für jede SQLite-Verbindung der Tests

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – jede SQLite-Verbindung prüft Fremdschlüssel | das PRAGMA in `tests/conftest.py` abgeschaltet (`339_1`) | 19 rot: v739 (6: db_session, threaded_db_session, wegwerf_engine/create_engine je URL, Datei und Engine der App, Verstoß), v301 (2), die 11 Tests von E1–E5 (streng erwartet rot, werden grün) |
| Nr. 2 – kein Test schaltet ab | `PRAGMA foreign_keys=OFF` wieder in v357 (`339_2a`) | 1 rot: v739::test_kein_test_schaltet_die_pruefung_ab_oder_selbst_ein |
| Nr. 2 – kein Test schaltet selbst ein | `PRAGMA foreign_keys=ON` wieder in v301 (`339_2b`) | 1 rot: v739::test_kein_test_schaltet_die_pruefung_ab_oder_selbst_ein |
| Nr. 2 – Ausnahme v325 nötig | die Prüfung während der Migration nicht abgeschaltet (`339_5a`) | 1 rot: v325::test_migration_downgrade_removes_everything_and_refuses_when_data_would_be_lost |
| Nr. 2 – Ausnahme nur für die Dauer der Migration | nach der Migration aus gelassen (`339_5b`) | 1 rot: derselbe Test (Prüfung am Ende) |
| Nr. 3 – bekannte Fehler erwartet rot, nur bis zur Behebung | E3 aus `FREMDSCHLUESSEL_BEKANNT` genommen (`339_4`) | 1 rot: v214::test_delete_draft_report_removes_photos_from_disk_and_cleans_up_task; „streng“: siehe `339_1` (grün gewordene scheitern) |
| 1.9.338 Nr. 3 – Migrationsproben ohne Abschalten | wie `339_2a` | rot (siehe dort) |
| Nr. 1 – Kindprozesse, Klicktests und `app/database.py` ohne PRAGMA | keine: eine Festlegung über unveränderten Code (nichts auszuhebeln) | -- |

6 Gegenproben, alle rot; alle Dateien byte-gleich zurück.

## 1.9.340 (Punkt 3): E1–E5 behoben, „Benutzer löschen“ mit Meldung

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – E1: Platzierungen vor den LV-Titeln | LV-Titel wieder zuerst (`340_1`, `app/projects.py`) | 6 rot: v740::test_e1_projekt_mit_lv_titeln_ueber_die_route_loeschen, v194 (5) |
| Nr. 1 – E2: erst die Zeilen des Laufs | Kunden wieder zuerst (`340_2`, `app/address_import.py`) | 3 rot: v247 (3) |
| Nr. 1 – E3: erst der Bericht, dann die Aufgaben | Aufgaben wieder zuerst (`340_3`, `app/service_reports.py`) | 1 rot: v214::test_delete_draft_report_removes_photos_from_disk_and_cleans_up_task |
| Nr. 1 – E5: Zuordnungen in eigenem Flush | ohne den Flush (`340_5`, `app/work_preparation.py`) | 1 rot: v083::test_material_delivery_note_links_survive_order_material_refresh (die Lieferanten-Zuordnung allein bleibt grün, siehe Archiv) |
| Nr. 2 – E4: nur der Verweis wird gelöst | den Verweis nicht lösen (`340_4`, `app/service.py`) | 2 rot: v740::test_e4_erneuter_import_loest_nur_den_verweis_der_kalkulation, v105 |
| Nr. 3 – verwendetes Konto: 409 statt Löschen | Verwendung nicht prüfen (`340_6a`, `app/konto_loeschen.py`) | 1 rot: v740::test_konto_mit_verwendung_wird_nicht_geloescht_sondern_erklaert |
| Nr. 3 – was zum Konto gehört, geht mit | die Kacheln nicht löschen (`340_6b`) | 1 rot: v740::test_konto_ohne_verwendung_geht_mit_allem_was_zu_ihm_gehoert |
| Nr. 4 – jeder Fremdschlüssel eingeordnet | „Aufgaben“ aus `BEREICHE` genommen (`340_6c`) | 2 rot: v740::test_jeder_fremdschluessel_auf_konten_ist_eingeordnet, test_konto_mit_verwendung_wird_nicht_geloescht_sondern_erklaert |

8 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.
