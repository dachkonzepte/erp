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

## Runde ab 1.9.346, 1.9.346 (Punkt 2): E7 und E8

Punkt 1 der Runde (nur geprüft) hat keine Festlegung und keine Gegenprobe: er bestätigt 1.9.343-2 durch eine Probe, ändert nichts.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Aufgabe mit Verweis nicht löschen (Stand bis 1.9.345) | ohne Prüfung in `aufgabe_loeschen()` (`346_1`) | 2 rot, je am Fremdschlüssel: v746 Befund, Checklisten-Regel |
| Nr. 1 – Antwort 409 | 400 statt 409 (`346_4`, `app/routers/tasks.py`) | 2 rot: dieselben |
| Nr. 1 – mit Rat | Meldung ohne Rat (`346_8`) | 2 rot: dieselben |
| Nr. 1 und 2 – Befund eingeordnet | Befund aus `VERWEISE_AUF_AUFGABEN` genommen (`346_2`) | 2 rot: v746 Befund (am Fremdschlüssel), Wächter `tasks` |
| Nr. 1 und 2 – Regel eingeordnet | Regel aus `VERWEISE_AUF_AUFGABEN` genommen (`346_3`) | 2 rot: v746 Checklisten-Regel (am Fremdschlüssel), Wächter `tasks` |
| Nr. 3 – Projekt mit Aufgabe nicht löschen (Stand bis 1.9.345) | ohne Prüfung in `delete_project()` (`346_5`) | 1 rot (am Fremdschlüssel): v746::test_projekt_mit_aufgabe_nicht_loeschen |
| Nr. 3 – Antwort 409 | 400 statt 409 (`346_6`, `app/routers/projects.py`) | 1 rot: derselbe |
| Nr. 3 – mit Rat | Meldung ohne Rat (`346_7`) | 1 rot: derselbe |
| Nr. 4 – jeder Fremdschlüssel auf `projects` eingeordnet | ein Eintrag aus der Einordnung genommen (`346_9`, im Test) | 1 rot: v746::test_jeder_fremdschluessel_auf_projekte_ist_eingeordnet |

9 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde ab 1.9.346, 1.9.347 (Punkt 3): beide Namen in allen Rückfragen der Zeile

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „Zweiten Faktor zurücksetzen“ über `kontoName()` | alter Text (`347_1`, `347_1k`) | 1 rot: v745; Klicktest 12 von 13 |
| Nr. 1 – „Alle Sitzungen beenden“ über `kontoName()` | alter Text (`347_2`, `347_2k`) | 1 rot: v745; Klicktest 12 von 13 |

4 Gegenproben (2 über den Test, 2 über den Klicktest), alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2a, 1.9.349 (Punkt 0): E9 und E10

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Vorlage eines Wartungsvertrags sperrt | Eintrag aus `PROJEKT_SPERREN` genommen (`349_2`) | 2 rot: v749 Vertrag (am Fremdschlüssel), Wächter `projects` |
| Nr. 1 – Vorlage einer Position sperrt | Eintrag herausgenommen (`349_3`) | 2 rot: v749 Position (am Fremdschlüssel), Wächter `projects` |
| Nr. 2 – Eingangsrechnung sperrt | Eintrag herausgenommen (`349_4`) | 3 rot: v749 Eingangsrechnungen, mehrere Gründe (am Fremdschlüssel), Wächter `projects` |
| Nr. 1–3 – `delete_project()` prüft | ohne Prüfung (`349_1`) | 5 rot: die vier aus v749 und v746 Aufgabe (je am Fremdschlüssel) |
| Nr. 3 – Zahl und Verb | immer „hängt“ (`349_5`) | 3 rot: v746 zwei Aufgaben, v749 zwei Eingangsrechnungen, mehrere Gründe |
| Nr. 1–3 – mit Rat | Meldung ohne Rat (`349_6`) | 5 rot: v749 alle vier, v746 Aufgabe |
| Nr. 4 – jeder Fremdschlüssel eingeordnet | siehe `349_2`–`349_4` (der Wächter ist je rot) | -- |

6 Gegenproben, alle rot; dazu zuerst `349_2`–`349_4` mit umbenannter Tabelle statt herausgenommenem Eintrag -- rot aus dem falschen Grund (KeyError in
jedem Löschen), verworfen und so wie oben wiederholt. Alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2a, 1.9.350 (Punkt 1): Längen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 und 2 – jedes Feld hat eine Grenze | Priorität der Aufgabe ohne Grenze (`350_1`) | 3 rot: v750 Wächter, Feld TaskCreate.priority, Route Aufgabe |
| Nr. 1 und 2 – Grenze ≤ Länge der Spalte | Grenze 31 statt 30 (`350_2`) | 3 rot: dieselben |
| Nr. 3 – eigene Definition im Update-Schema | wieder geerbt, ohne Grenze (`350_4`) | 3 rot: v750 Wächter, beide Felder der Nummern |
| Nr. 4 – Meldung mit Grenze | `fehlerText()` ohne Grenze (`350_3`) | 1 rot: v750::test_meldung_nennt_die_grenze |

4 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2a, 1.9.351 (Punkt 2, F7): Adressimport je Zeile

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 und 2 – jede Zeile geprüft (Stand bis 1.9.350) | nichts geprüft (`351_1`) | 4 rot: v751, darunter die Probe unter PostgreSQL mit `StringDataRightTruncation` |
| Nr. 1 – Grenze = kürzeste Zielspalte | PLZ mit Grenze 21 (`351_2`) | 3 rot: v751 an der Grenze (Prüfung wie PostgreSQL), PostgreSQL, Ablehnung |
| Nr. 1 – zusammengesetzter Name | nicht geprüft (`351_3`) | 1 rot: v751::test_zusammengesetzter_name |
| Nr. 1 – zweite Mail-Adresse | nicht geprüft (`351_4`) | 1 rot: v751::test_mehrere_zellen_einer_zeile_und_die_zweite_mail |
| Nr. 2 – nie gekürzt | PLZ einer abgelehnten Zeile gekürzt gespeichert (`351_5`) | 1 rot: v751::test_zu_lange_zeile_abgelehnt_die_uebrigen_gehen_durch |
| Nr. 3 und 4 – in der Vorschau, in der Antwort | abgelehnte Zeile nicht in der Vorschau (`351_6`) | 4 rot: v751 |
| Nr. 3 – nie übernommen | als „customer“ eingestuft (`351_7`) | 4 rot: v751 |
| Nr. 4 – die Seite zeigt die Liste | Liste nicht gezeichnet (`351_1k`) | Klicktest 15 von 17 |

8 Gegenproben (7 über Tests, 1 über den Klicktest), alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2b, 1.9.352 (Punkt 0): fehlerText() überall

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 und 2 – keine Seite an fehlerText() vorbei (Stand bis 1.9.351) | Aufgaben: api() wie vorher, `detail` roh (`352_1`) | 2 rot: v752 Regel A, Regel B |
| Nr. 2 – auch ohne `detail` | Änderungshistorie: `throw Error(r.statusText)` (`352_2`) | 1 rot: v752 Regel B |
| Nr. 3 – wer aufruft, bindet ein | Aufgaben ohne Include (`352_3`) | 1 rot: v752::test_wer_fehlertext_aufruft_bindet_ihn_ein |
| Nr. 3 – mehrfach einbindbar | `const _FEHLERARTEN` wie vorher (`352_4`) | 1 rot: v752 node (zweimal geladen: SyntaxError) |
| Nr. 4 – Rückfalltext | ohne `ersatz` (`352_5`) | 1 rot: v752 node |

5 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2b, 1.9.353 (Punkt 1): Listen nach Namen wie im Telefonbuch

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ohne Groß- und Kleinschreibung | Tabelle ohne A–Z (`353_1`) | 11 rot: v753 Schlüssel, Tabelle, SQLite, PostgreSQL, Migration, Kundenliste |
| Nr. 2 – Umlaute beim Grundbuchstaben | Tabelle nur A–Z (`353_2`) | 11 rot: v753 dieselben |
| Nr. 3 – ß wie ss | ohne ß/ẞ in `ERSETZEN` (`353_3`) | 9 rot: v753 u. a. Migrationstext, Kundenliste unter PostgreSQL |
| Nr. 4 – leere Namen ans Ende | ohne `nulls_last()` (`353_4a`) | 2 rot: v753 SQLite, Kundenliste |
| Nr. 4 – Leerzeichen am Rand zählen nicht | ohne `strip` (`353_4b`) | 7 rot: v753 Schlüssel, SQLite, PostgreSQL, Migration, Kundenliste |
| Nr. 5 – PostgreSQL rechnet wie Python | `pg_sql()` ohne ß (`353_5`) | 3 rot: v753 Migrationstext, PostgreSQL, Kundenliste unter PostgreSQL |
| Nr. 5 – `create_all()` legt an | ohne Ereignis an `Base.metadata` (`353_5b`) | 2 rot: v753 create_all, Kundenliste unter PostgreSQL |
| Nr. 5 – SQLite an jeder Verbindung | ohne `create_function` (`353_5c`) | 2 rot: v753 SQLite, Kundenliste |
| Nr. 6 – unabhängig von der Kollation | ohne `COLLATE "C"` (`353_6`) | 2 rot: v753 PostgreSQL, Kundenliste unter PostgreSQL |
| Nr. 7 – über `nach_namen()` | Kundenliste `order_by(Customer.name)` (`353_7a`) | 3 rot: v753 Wächter, Kundenliste SQLite und PostgreSQL |
| Nr. 7 – Klicktest | dieselbe Änderung (`353_1k`) | klicktest_telefonbuch rot (9 von 15: leerer Name zuerst, Groß vor klein) |
| Nr. 7 – kein `lower()` | Adressbuch wieder `func.lower()` (`353_7b`) | 1 rot: v753 Wächter lower |
| Nr. 7 – die ID zuletzt | Benutzer ohne `AppUser.id` (`353_7c`) | 1 rot: v753 Wächter id |
| Nr. 7 – auch Beziehungen | Dachflächen `order_by="RoofArea.name"` (`353_7d`) | 1 rot: v753 Wächter datenbank |
| Nr. 8 – Python über `sortierwert()` | „Monat & Lohn“ wieder `casefold()` (`353_8`) | 1 rot: v753 Wächter python |
| Nr. 9, 10 | keine -- nichts gebaut (Spalte und Browser unverändert) | -- |
| Nr. 11 – Betriebsmittel nach dem aufgelösten Namen | wieder `order_by(OperationalAsset.name)` (`353_9`) | 2 rot: v753 Betriebsmittel, Wächter datenbank |

16 Gegenproben (15 über Tests, 1 über den Klicktest), alle rot; `353_7c` lief zuerst aus dem falschen Grund rot (Kommentar mitten in der Zeile, die Datei
ließ sich nicht lesen) und wurde mit dem Marker am Zeilenende wiederholt. Alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2b, 1.9.354 (Punkt 2): jede Liste mit fester Reihenfolge

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – jede Listen-Beziehung | `Project.quotes` ohne `order_by` (`354_1`) | 2 rot: v754 Beziehungen, Angebote unter PostgreSQL (P2b: die Plätze getauscht) |
| Nr. 2 – jede Folge mit `order_by` | „Abgleich gesperrt“ ohne `order_by` (`354_2`) | 1 rot: v754 Abfragen |
| Nr. 3 – Liste genau | eine Stelle aus `OHNE_REIHENFOLGE` mit `order_by` (`354_3`) | 2 rot: v754 Liste genau, leere Werte (die Spalte darf leer sein) |
| Nr. 4 – leere Werte am Ende (Abfragen) | `list_entries()` ohne `nulls_last()` (`354_4`) | 2 rot: v754 Wächter, Dauer-Buchung unter PostgreSQL (P5) |
| Nr. 4 – leere Werte am Ende (Beziehungen) | Prüffristen ohne `nulls_last()` (`354_4b`) | 1 rot: v754 Beziehungen |
| Nr. 5 – jede Form | über die Probe in `test_der_waechter_erkennt_jede_form` (Schleife, `list()`) | -- (keine Änderung unter `app/`) |

5 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2c, 1.9.355 (Punkt 0): Kundenliste nach Nachname, jede Sortierung endet auf der ID

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Kundenliste nach Nachname, dann Vorname | wieder nach dem ganzen Namen (`355_1`) | 2 rot: v755 Kundenliste (SQLite, PostgreSQL) |
| Nr. 2 – Büro-Suche wie die Kundenliste | Suche nach dem ganzen Namen (`355_2`) | 1 rot: v755 Büro-Suche |
| Nr. 3 – ohne Vorname nach denen mit | Vorname ohne `nach_namen()` (`355_3`) | 3 rot: v755 Kundenliste, v753 Wächter, v754 leere Werte |
| Nr. 4 – jedes `order_by` endet auf der ID | Wartungsverträge ohne ID (`355_4`) | 2 rot: v755 Wächter, zwei am selben Tag fällige Verträge unter PostgreSQL (Plätze getauscht) |
| Nr. 5 – Listen-Beziehungen | `Invoice.reminders` ohne ID (`355_5`) | 1 rot: v755 Beziehungen |
| Nr. 4 – `AUSNAHMEN` genau | eine Ausnahme mit ID (`355_6`) | 1 rot: v755 Liste genau |
| Nr. 6 – Aufrufe der Büro-Suche | Lieferanten ohne ID (`355_7`) | 2 rot: v755 Wächter, Aufrufe der Suche |
| Nr. 7 – ID in Auswahl bzw. Gruppe | -- | über Nr. 4 (der Wächter liest beide Stellen); das Ergebnis prüfen die bestehenden Tests der Sperren und des Kundenwechsels |

7 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2c, 1.9.356 (Punkt 1): Antworten ohne Prüfung, Pflicht-Textfelder ohne Rand

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Kundenliste mit gespeichertem leeren Nachnamen | `CustomerOut` wieder von `CustomerCreate` (`356_1`) | 4 rot: v756 Kundenliste ("" und " "), v673 Paar und `BEKANNT` |
| Nr. 1 – kein Antwortschema prüft | `SupplierOut` wieder von `SupplierCreate` (`356_2`) | 2 rot: v673 Paar und `BEKANNT` |
| Nr. 2, 3 – Rand weg, nur Leerzeichen 422 | `_ohne_rand()` lässt den Wert (`356_3`) | 223 rot: v756 je Feld, Route Nachname |
| Nr. 4 – Validator um die Union | `Pflichttext | None` statt `PflichttextWennDa` (`356_4`) | 37 rot: v750 „zu lang“ (17 Felder), v756 „fehlt“ (20 Felder) |
| Nr. 5 – Passwörter ausgenommen | neues Passwort als `Pflichttext` (`356_5`) | 2 rot: v756 Wächter (`AUSNAHMEN` genau), Passwort behält Leerzeichen |
| Wächter – jedes Pflichtfeld | Nachname des Kunden wieder `str` (`356_6`), im Teil-Update `str | None` (`356_6b`) | je 2 rot: v756 Wächter, Route Nachname |
| Nr. 6 – Meldung „fehlt“ | Zeile in `_fehlertext.html` entfernt (`356_7`) | 1 rot: v756 Meldung in node |

8 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2c, 1.9.357 (Punkt 2): jedes Zahlenfeld mit Grenzen bis zur Spalte

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Numeric: Obergrenze | Dachneigung ohne `le` (`357_1`) | 3 rot: v757 Wächter, je Feld, Route |
| Nr. 2 – Integer: int4 | Kunde des Projekts ohne Grenzen (`357_2`) | 3 rot: v757 Wächter, je Feld, Route |
| Nr. 1 – Untergrenze | Steuersatz des Kontos ohne `ge` (`357_3`) | 3 rot: v757 Wächter, je Feld (Create und Update) |
| Nr. 3 – engere Grenze bleibt | Dachneigung `ge=0` -> `ge=-NUMERIC_5_2` (`357_4`) | zuerst **grün** (kein Test sah es); `test_vorhandene_grenzen_bleiben` nachgezogen (`VORHER`), dieselbe Probe: 1 rot |
| Nr. 5 – Konstante passt in die Spalte | `NUMERIC_5_2` = 1000,00 (`357_5`) | 12 rot: v757 PostgreSQL, Wächter, Route, je Feld |
| Nr. 4 – Numeric(18,…) | `ZAHL_12` = 10^16 (`357_6`) | 66 rot: v757 PostgreSQL, Wächter, je Feld |
| Nr. 6 – Meldung mit Grenze | `grenze` in `_fehlertext.html` leer (`357_7`) | 1 rot: v757 Meldung in node |
| Nr. 7 – Meldung zu vielen Stellen | `stellen` in `_fehlertext.html` leer (`357_8`) | 1 rot: v757 Meldung in node |
| Nr. 8 – Vorgabe über default_factory | Zweig entfernt (`357_9`) | 1 rot: v673 `test_vorgabe_ueber_default_factory_bleibt` |

9 Gegenproben, alle rot (eine nach nachgezogenem Test); alle Dateien byte-gleich zurück, kein Marker unter `app/`.

## Runde V2c, 1.9.358 (Punkt 3): ein Baustein für LIKE

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – jedes Zeichen wörtlich | `_schuetzen()` schützt nichts (`358_1`) | 3 rot: v758 Baustein, Verhalten unter SQLite und PostgreSQL |
| Nr. 1, 3 – jedes Muster aus dem Baustein | Aufgaben wieder `f"%{search}%"` (`358_2`) | 3 rot: v758 Wächter, „50%“ fand „500“ unter SQLite und PostgreSQL |
| Nr. 1 – Fluchtzeichen ausdrücklich | Material ohne `escape=ESCAPE` (`358_3`) | 2 rot: v758 Wächter, „A_1“ unter SQLite (PostgreSQL nimmt den Backslash ohnehin) |
| Nr. 2 – interne Muster | Folgen je Unterschrift wieder mit rohem Präfix (`358_4`) | 1 rot: v758 Wächter |
| Nr. 4 – keine Ausnahme | -- | über `358_2` bis `358_4` (der Wächter nennt jede Stelle; `AUSNAHMEN` ist leer) |

4 Gegenproben, alle rot; alle Dateien byte-gleich zurück, kein Marker unter `app/`.
