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

## Nachrunde V1, 1.9.341 (Punkt 1, E6): Wartungsvertrag und Position mit Geschichte nicht löschen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Vertrag mit Projekt oder Bericht: 409 statt Löschen | keine Prüfung im Vertrag (`341_1`, wie bis 1.9.340 ohne unterschriebenen Bericht) | 3 rot, je am Fremdschlüssel: v741::test_vertrag_mit_projekt_daraus_wird_nicht_geloescht, test_vertrag_mit_berichtsentwurf_wird_nicht_geloescht, test_vertrag_zaehlt_auch_was_aus_seinen_positionen_entstand |
| Nr. 1 – auch über eine Position | nur, was aus dem Vertrag selbst entstand (`341_3`) | 1 rot: v741::test_vertrag_zaehlt_auch_was_aus_seinen_positionen_entstand |
| Nr. 1 und 2 – Antwort 409 | 400 statt 409 (`341_6`, Route) | 3 rot: die drei Vertragsfälle aus `341_1` |
| Nr. 2 – Position mit Projekt oder Bericht: 409 | keine Prüfung in der Position (`341_2`) | 1 rot (am Fremdschlüssel): v741::test_position_mit_projekt_oder_bericht_wird_nicht_geloescht |
| Nr. 3 – jeder Fremdschlüssel eingeordnet | Berichte der Position aus `AUS_DER_POSITION` genommen (`341_4`) | 3 rot: v741::test_jeder_fremdschluessel_auf_vertrag_und_position_ist_eingeordnet, test_position_…, test_vertrag_zaehlt_… |
| Nr. 4 – ohne Geschichte samt Positionen und Erinnerungen | die Erinnerungen nicht löschen (`341_5`) | 1 rot: v741::test_vertrag_ohne_geschichte_geht_mit_positionen_und_erinnerungen |

6 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Nachrunde V1, 1.9.342 (Punkt 2): Seite „Benutzer“ -- „Deaktivieren“ statt „Löschen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – der Server sagt, wo ein Konto steht | `verwendet_in` immer leer (`342_1`, `app/routers/users.py`) | 1 rot: v742::test_liste_sagt_wo_ein_konto_steht; Klicktest (`342_1k`) 8 von 12 |
| Nr. 2 – „Löschen“ nur ohne Verwendung | die Seite bietet immer „Löschen“ (`342_2`, `app/templates/users.html`) | 1 rot: v742::test_seite_bietet_loeschen_nur_ohne_verwendung; Klicktest (`342_2k`) 8 von 12 |
| Nr. 3 – Deaktivieren beendet alle Sitzungen | ohne `alle_beenden()` (`342_3a`) | 1 rot: v742::test_deaktivieren_laesst_den_rest_und_beendet_die_sitzungen |
| Nr. 3 – nicht der letzte aktive Administrator | ohne die Sperre (`342_3b`) | 1 rot: v742::test_deaktivieren_nicht_sich_selbst_nicht_den_letzten_admin_nur_admin |
| Nr. 3 – nicht das eigene Konto | ohne die Sperre (`342_3c`) | 1 rot: derselbe Test |
| Nr. 3 – nur `active` ändert sich | Deaktivieren setzt auch die Rolle zurück (`342_4`) | 1 rot: v742::test_deaktivieren_laesst_den_rest_und_beendet_die_sitzungen |

8 Gegenproben (6 über Tests, 2 über den Klicktest), alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde ab 1.9.343, 1.9.343 (Punkt 1): Folgeaufgabe nur unangetastet mitlöschen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur unangetastet mitlöschen (Stand bis 1.9.342 nachgestellt) | jede Folgeaufgabe geht mit (`343_1`) | 13 rot: v743, alle zehn Arten „angefasst“, Vorgang bleibt, nur die angefasste von zweien, Route |
| Nr. 1 und 3 – nicht mehr in der Anfangsspalte (auch erledigt) | ohne Spaltenmerkmal (`343_2`) | 3 rot: v743 [spalte gewechselt], [erledigt], Route |
| Nr. 1 – mit Unteraufgaben | ohne Merkmal Unteraufgaben (`343_3`) | 2 rot: v743 [mit unteraufgabe], nur die angefasste von zweien |
| Nr. 1 – mit Vorgang daraus | ohne Merkmal Vorgang (`343_4`) | 2 rot: v743 [vorgang daraus], test_vorgang_aus_der_aufgabe_bleibt_bestehen |
| Nr. 1 und 2 – sonst seit dem Anlegen geändert | ohne Merkmal `updated_at` (`343_5`) | 6 rot: v743 [prioritaet], [faelligkeit], [beschreibung], [zugewiesen], [uebernommen], [archiviert] |
| Nr. 2 – erst mehr als eine Sekunde zählt | Spanne 0 statt 1 s (`343_6`) | 3 rot: beide unangetasteten, nur die angefasste von zweien |
| Nr. 4 – Konto im Vermerk | Name immer aus dem Anfragekontext (`343_7`) | 11 rot: v743, die zehn Arten und die Route |
| Nr. 4 – Vermerk vorn, Beschreibung darunter | Vermerk hinten angehängt (`343_8`) | 11 rot: dieselben |

8 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde ab 1.9.343, 1.9.344 (Punkt 2): Löschen von Aufgaben in der Änderungshistorie

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – jedes Löschen steht drin (Stand bis 1.9.343) | kein Eintrag für gelöschte Aufgaben (`344_1`, `app/audit.py`) | 5 rot: v744 von Hand, Berichtsentwurf, Wartungsvertrag, an `aufgabe_loeschen()` vorbei, nur der Admin sieht |
| Nr. 1 – mit Titel | Bezeichnung ohne Titel (`344_7`) | 3 rot: v744 von Hand, Berichtsentwurf, vorbei |
| Nr. 1 und 2 – Konto aus `aufgabe_loeschen()` | Konto nur aus der Anfrage (`344_6`) | 3 rot: v744 von Hand, Berichtsentwurf, Wartungsvertrag |
| Nr. 1 – keine andere Änderung kommt dazu | `Task` in `AUDITED_TYPES` (`344_10`) | zuerst grün (der Test sah nur die Art „Aufgabe“), nachgezogen: 1 rot: v744::test_sonstige_aenderungen_an_aufgaben_nicht |
| Nr. 2 – `aufgabe_loeschen()` merkt Anlass und Konto | ohne Merken (`344_2`, `app/tasks.py`) | 3 rot: v744 von Hand, Berichtsentwurf, Wartungsvertrag |
| Nr. 2 und 3 – von Hand über `aufgabe_loeschen()` | `delete_task()` vorbei (`344_3`) | 1 rot: v744 von Hand |
| Nr. 2 und 3 – Berichtsentwurf über `aufgabe_loeschen()` | `delete_report()` vorbei (`344_4`) | 1 rot: v744 Berichtsentwurf |
| Nr. 2 und 5 – Wartungsvertrag einzeln, kein Löschen über die Tabelle | Stand bis 1.9.343: `delete(Task)` (`344_5`) | 2 rot: v744 Wartungsvertrag (am Fremdschlüssel der Unteraufgabe), Wächter |
| Nr. 4 – nur der Admin | Aufgaben auch fürs Büro (`344_8`, `app/routers/audit.py`) | 1 rot: v744::test_nur_der_admin_sieht_die_eintraege |
| Nr. 6 – Anlass in der Anzeige | ohne Anlass (`344_9`, `_verlauf.html`) | 1 rot: v744::test_historie_zeigt_den_anlass |

10 Gegenproben, alle rot (eine nach dem Nachziehen); alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde ab 1.9.343, 1.9.345 (Punkt 3): Rückfrage auf „Benutzer“ nennt Anzeigename und Benutzername

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Benutzername in der Rückfrage | `kontoName()` ohne Benutzername (`345_1`, `345_1k`) | 1 rot: v745; Klicktest 9 von 11 |
| Nr. 1 – „Löschen“ nimmt `kontoName()` | alter Text bei „Löschen“ (`345_2`, `345_2k`) | 1 rot: v745; Klicktest 10 von 11 |
| Nr. 1 – „Deaktivieren“ nimmt `kontoName()` | alter Text bei „Deaktivieren“ (`345_3`) | 1 rot: v745 |

5 Gegenproben (3 über den Test, 2 über den Klicktest), alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.
