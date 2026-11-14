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
