# Gegenproben der Stufe P1 „Kundenportal“

Je Festlegung eine Gegenprobe (Regel 24): ein Schutz wird absichtlich ausgehebelt (Marker GEGENPROBE), der zugehörige Test muss rot werden -- aus dem
geprüften Grund (FAILED, nicht ERROR). Danach byte-genau zurück. Läufer im Scratchpad der Sitzung (`gegenprobe.py`, `gegenprobe_klick.py`).

## 1.11.0: Tabellen und Rechte des Kundenportals

Probendateien `gp_1110.py`, `gp_1110b.py`, Lauf mit `tests/test_v799_portal_rechte.py` (bei Nr. 3 dazu `tests/test_v197_module_toggle.py`); alle 17 rot aus
dem geprüften Grund, alle Dateien byte-gleich zurück. Zwei Probeläufe brauchten eine zweite Fassung: Nr. 3 erwartete zuerst auch `test_v197` rot -- der folgt
seit 1.11.0 der Liste `AB_WERK_AUS` und hält sie nicht fest (das tut `test_v799`); Nr. 6 („Benutzer des ERP“) kommentierte in der ersten Fassung den Rest der
Zeile aus (ERROR statt FAILED). Nr. 2 lief nach dem Fund aus der vollen Suite (keine Vorgabe in Python mehr) ein zweites Mal (`gp_1110c.py`): rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – CHECK gleich werte.py und Migration | ein Wert mehr in der Migration | 3 rot (Vergleich, beide Migrationsproben) |
| Nr. 1 – CHECK greift | CHECK der Sitzung fehlt in der Migration | 1 rot (Migrationsprobe SQLite) |
| Nr. 2 – Portal am Kunden ab Werk aus | Vorgabe an | 1 rot |
| Nr. 3 – Modul ab Werk aus | `AB_WERK_AUS` leer | 1 rot |
| Nr. 4 – keine Kundendaten | `customers` in LESEN | 2 rot |
| Nr. 4 – genau die acht Spalten | IBAN dazu | 4 rot (LESEN genau, drei Proben gegen PostgreSQL) |
| Nr. 5 – jede Tabelle eingeordnet | `portal_bremsen` fehlt in KEIN_ZUGRIFF | 2 rot |
| Nr. 6 – setzen nimmt alte Rechte weg | REVOKE auf alle Tabellen fehlt | 1 rot |
| Nr. 6 – eigene Funktionen nicht für alle | REVOKE … FROM PUBLIC fehlt | 3 rot |
| Nr. 6 – pruefen: Spalten zu viel | Meldung fehlt | 1 rot |
| Nr. 6 – pruefen: Rechte auf ganze Tabellen | Abfrage liefert nichts | 1 rot |
| Nr. 6 – pruefen: Benutzer des ERP | Prüfung verkehrt | 2 rot |
| Nr. 6 – Rückgabe 2 ohne DATABASE_URL | gibt 0 | 1 rot |
| Nr. 8 – Importe des Pakets | `import app.database` in rechte.py | 1 rot |
| Nr. 9 – Adressimport | Zugang zählt nicht | 1 rot |
| Nr. 10 – Downgrade bricht ab | ohne Abbruch | 1 rot (Migrationsprobe SQLite) |
| Nr. 11 – Zugang nicht Teil des Vorgangs | `portal_zugaenge` in TEILE | 1 rot |

Ohne eigene Gegenprobe: Nr. 7 (Arbeitsweise -- keine Rechte in Migrationen; der Test der Rechte läuft gegen `create_all()` ohne Migration und setzt sie mit
dem Skript).

## 1.11.1: Funktionen der Datenbank für Link und Sitzung

Probendatei `gp_1111.py` (Fälle einzeln wählbar), Lauf mit `tests/test_v800_portal_funktionen.py` und je Fall einem Ausschnitt (`-k`); alle 22 rot aus dem
geprüften Grund, alle Dateien byte-gleich zurück. Drei Proben brauchten eine zweite Fassung:
- „Ein Helfer für das Portal ausführbar“ erwartete zuerst auch den Test der Rolle rot. Der blieb grün -- zu Recht: ein Helfer ohne SECURITY DEFINER läuft mit
  den Rechten der Rolle und scheitert an der Tabelle (42501), auch mit EXECUTE. Rot wird der Wächter am Text.
- „Ohne Sperren beim Prüfen“ blieb zweimal grün: zuerst überlappten zwei Fäden mit Barriere nicht sicher (der Test wurde umgebaut: die erste Eingabe hält
  ihre Sperren, die zweite wartet nachweislich -- `pg_stat_activity` --, dann erst Commit), dann reihte die Bremse beide an ihrer Zählerzeile hintereinander,
  weil beide vom selben Anschluss kamen (die zweite Eingabe kommt jetzt von einem anderen Anschluss, wie ein zweites Gerät). Danach rot.
- Zwei Ersetzungen waren nicht eindeutig (Textblock bzw. „interval '15 minutes')“ je zweimal) -- der Läufer brach vor jeder Änderung ab; eindeutig gemacht.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Funktionen laufen mit den Rechten des ERP | Willkommen ohne SECURITY DEFINER | 2 rot (Wächter, Willkommen: keine Berechtigung) |
| Nr. 1 – kein Helfer für das Portal | `portal_bremse` in `rechte.FUNKTIONEN` | 1 rot (Wächter) |
| Nr. 2 – fester search_path | bei `portal_sitzung` weg | 1 rot |
| Nr. 2 – nicht für alle ausführbar | REVOKE für einen Helfer fehlt | 1 rot |
| Nr. 3 – nur Prüfwerte, sonst nichts geschrieben | Prüfung beim Link weg | 7 rot (jede Eingabe) |
| Nr. 3 – Code an die Sitzung gebunden | Prüfwert ohne Sitzung | 1 rot |
| Nr. 4 – Zeit nur aus portal_jetzt() | now() beim Anlegen der Sitzung | 1 rot |
| Nr. 5 – jeder Grund unterschieden im Protokoll | Archiv vergessen | 3 rot |
| Nr. 5 – unbestätigt 15 Minuten | 30 Minuten | 1 rot |
| Nr. 6 – neuer Code frühestens nach 60 Sekunden | Sperre weg | 1 rot |
| Nr. 6 – Grenze je Zugang | 4 statt 3 | 1 rot |
| Nr. 6 – NOTIFY als Weckruf | kein NOTIFY | 1 rot |
| Nr. 7 – fünf Versuche | sechs | 1 rot |
| Nr. 7 – neuer Wert nach dem Code | Wert bleibt | 3 rot |
| Nr. 7 und 11 – von zwei gleichzeitigen gilt eine (Sperren Zugang -> Sitzung) | Sperren von Zugang und Sitzung beim Prüfen weg | 1 rot (die zweite bekommt „neu_anfordern“ statt „ungueltig“) |
| Nr. 8 – höchstens einmal je Stunde | bei jedem Aufruf verlängert | 1 rot |
| Nr. 8 – Sperren wirken sofort | Sitzung ohne Prüfung des Zugangs | 5 rot (jede Sperre) |
| Nr. 9 – alle Geräte nur bestätigt | auch unbestätigt | 1 rot |
| Nr. 10 – Willkommen nur bestätigt | auch unbestätigt | 1 rot |
| Nr. 12 – Migration wörtlich | ein Wert anders in der Migration | 1 rot |
| Nr. 12 – create_all legt sie an | Ereignis weg | 1 rot |
| Nr. 13 – Modul ohne Zeile aus | ohne Zeile an | 1 rot |
