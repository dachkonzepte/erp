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

## 1.11.2: der Portal-Dienst -- Gerüst, Schranke, Startprüfung

Probendatei `gp_1112.py` (Fälle einzeln wählbar), Lauf mit `tests/test_v801_portal_dienst.py` und je Fall einem Ausschnitt (`-k`); alle 23 rot aus dem
geprüften Grund, alle Dateien byte-gleich zurück. Drei Proben brauchten eine zweite Fassung:
- „Ein Weg außerhalb der Listen“: der Test „kein Weg des ERP“ übersprang zuerst jeden Weg, der im Router steht -- auch den eingeschmuggelten. Er misst jetzt
  gegen die erklärten Listen; danach beide rot.
- „Schnittstellen-Doku an“: die erste Ersetzung kommentierte den Rest des Aufrufs aus (ERROR statt FAILED); danach rot.
- „Herkunft nicht geprüft“ erwartete zuerst auch den Angriff gegen den echten uvicorn rot -- in 1.11.2 gibt es noch keinen schreibenden Weg, die Probe
  zeigt sich nur am Test der Herkunft (ab 1.11.3 auch an den Wegen der Sitzung).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur die erklärten Wege | ein Weg `/api/customers` außerhalb der Listen | 2 rot |
| Nr. 1 – keine Schnittstellen-Doku | `/docs` und `/openapi.json` an | 1 rot |
| Nr. 2 – Host nur der eigene | Prüfung weg | 6 rot (fünf Hosts, echter uvicorn) |
| Nr. 3 – nur GET, HEAD, POST | PUT erlaubt | 3 rot |
| Nr. 4 – höchstens 16 KB | 64 KB | 1 rot |
| Nr. 5 – schreibend nur von der eigenen Seite | Prüfung weg | 7 rot (jeder fremde Fall) |
| Nr. 6 – Schutz-Kopfzeilen an jeder Antwort | X-Frame-Options fehlt | viele rot (jede Art Antwort) |
| Nr. 6 – no-store von selbst | fehlt | 1 rot |
| Nr. 6 – HSTS nur außerhalb von Test und Entwicklung | immer | 1 rot |
| Nr. 7 – 500 ohne Detail | Text in der Antwort | 1 rot |
| Nr. 7 – im Protokoll nur die Klasse | Text im Protokoll | 1 rot |
| Nr. 7 – leerer Pool 503 | als 500 | 1 rot |
| Nr. 8 – ohne ERP_ENV production | development | 1 rot |
| Nr. 8 – keine Meldung nennt einen Wert | Herkunft in der Meldung | 1 rot |
| Nr. 9 – Start nur auf dem Stand der Migrationen | Revision nicht geprüft | 1 rot |
| Nr. 10 – Pool 3 + 3 | 5 + 35 | 1 rot |
| Nr. 10 – 10 Fäden | 40 | 1 rot |
| Nr. 11 – nur die Core-Tabellen | eine Spalte mehr (IBAN) | 1 rot |
| Nr. 12 – `/health` prüft die Datenbank | immer gesund | 1 rot |
| Nr. 13 – Einheit mit Speichergrenze | MemoryMax fehlt | 1 rot |
| Nr. 13 – gunicorn vertraut nur 127.0.0.1 | `--forwarded-allow-ips '*'` | 1 rot |
| Nr. 13 – nginx protokolliert keine Adresse | `$remote_addr` im Format | 1 rot |
| Nr. 14 – gunicorn in requirements.txt | fehlt | 1 rot |

## 1.11.3: Link, Code und Sitzung im Portal-Dienst

Probendatei `gp_1113.py`, Lauf mit `tests/test_v802_portal_sitzung.py` und je Fall einem Ausschnitt (`-k`); alle 28 beim ersten Anlauf rot aus dem
geprüften Grund (FAILED, kein ERROR), alle Dateien byte-gleich zurück. Ohne eigene Gegenprobe: „lesend ohne Commit“ (Nr. 11) -- eine Funktion, die nichts
schreibt (STABLE), kann in PostgreSQL nicht schreiben; geprüft ist der Weg (ein GET, der eine schreibende Funktion ruft, ist rot).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ohne Kopfzeile 422 | Prüfung weg | 13 rot (500 statt 422) |
| Nr. 1 – ungültiger Link außen gleich | anderer Text bei „ungültig“ | 1 rot |
| Nr. 2 – Cookie HttpOnly | für Skripte lesbar | 2 rot |
| Nr. 2 – Cookie SameSite=Strict | lax | 1 rot |
| Nr. 2 – Code-Cookie 15 Minuten | eine Stunde | 1 rot |
| Nr. 3 – frühere Sitzung des Browsers endet | bleibt | 1 rot |
| Nr. 3 – Code-Cookie nach dem Code gelöscht | bleibt | 1 rot |
| Nr. 4 – 401 löscht das Cookie | löscht nicht | 21 rot (jeder Zustand, jeder Weg) |
| Nr. 4 – ein GET setzt kein Cookie | Willkommen löscht bei 401 | 1 rot |
| Nr. 5 – Bremse 429 | als 200 | 1 rot |
| Nr. 5 – mit Retry-After | ohne | 1 rot |
| Nr. 6 – Code nur Ziffern 0–9 | `\d` (nimmt auch breite Ziffern) | 1 rot |
| Nr. 6 – `ueberall` nur true/false | `bool` (nimmt 1) | 1 rot |
| Nr. 7 – Anschluss rechts aus X-Forwarded-For | von links | 1 rot (echter uvicorn) |
| Nr. 8 – Firma ohne Anrede | „Firma“ wie Herr/Frau | 1 rot |
| Nr. 8 – Herr/Frau mit Titel | ohne Titel | 3 rot |
| Nr. 9 – genau die Schlüssel | ein Schlüssel mehr in Willkommen | 1 rot |
| Nr. 9 – kein Weg nimmt eine ID | `kunde` als Abfrage | 1 rot |
| Nr. 10 – jedes Ergebniswort behandelt | „keiner“ fehlt | 2 rot (Wächter, Ablauf 500) |
| Nr. 11 – kein GET schreibt | Willkommen öffnet einen Link | 1 rot |
| Nr. 12 – Link nie im Protokoll | im Protokoll | 1 rot |
| Nr. 12 – Code nie im Protokoll | im Protokoll | 1 rot |
| Nr. 13 – auf allen Geräten | wie dieses Gerät | 1 rot |
| Nr. 13 – unbestätigte Sitzung endet mit | bleibt | 1 rot |
| Nr. 13 – dieses Gerät auch ohne gültige Sitzung | nur mit gültiger | 1 rot |
| Nr. 14 – Verlängern setzt das Cookie | setzt nicht | 1 rot |
| Nr. 15 – Prüfskript nur Zahlen | nennt die Prüfwerte | 1 rot |
| Nr. 15 – erst zwei Anschlüsse sind gut | einer reicht | 1 rot |

## 1.11.4: gunicorn und uvicorn in den Versionen des Servers

Probendatei `gp_1114.py`, Lauf mit `tests/test_v803_gunicorn_server.py`; alle 11 beim ersten Anlauf rot aus dem geprüften Grund (FAILED, kein ERROR), alle
Dateien byte-gleich zurück -- auch die drei Dateien von gunicorn und uvicorn unter `.venv` (dort zeigt die Gegenprobe, dass der Test die echte Vorgabe der
installierten Pakete sieht, nicht eine Kopie). Ohne eigene Gegenprobe: Nr. 5 (Arbeitsweise der Prüfung) -- die Platzhalter prüft der Test selbst.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – gunicorn genau 26.2.0 | requirements.txt auf 23.0.0 | 1 rot |
| Nr. 1 – uvicorn genau 0.52.4 | requirements.txt auf den Bereich | 1 rot |
| Nr. 2 – Vorgabe von gunicorn gesehen | Vorgabe in gunicorn/config.py nur 127.0.0.1 | 2 rot (vertraut, ::1 nicht genommen) |
| Nr. 2 – nichts in der Umgebung | FORWARDED_ALLOW_IPS=* im Muster | 3 rot |
| Nr. 2 – nichts in ExecStart | --forwarded-allow-ips * | 3 rot |
| Nr. 2 – an uvicorn weitergereicht | Übergabe im UvicornWorker entfernt | 2 rot |
| Nr. 3 – Vorgabe gesehen | Vorgabe accesslog „-“ in gunicorn/config.py | 1 rot |
| Nr. 3 – nichts in ExecStart | --access-logfile - | 2 rot |
| Nr. 3 – uvicorn ohne eigenes Protokoll | eigener Handler am Logger uvicorn.access | 1 rot |
| Nr. 4 – UvicornWorker | --worker-class asgi (Arbeitsprozess von gunicorn) | 3 rot |
| Nr. 4 – vorangestellte Adresse hilft nicht | uvicorn liest X-Forwarded-For von links | 1 rot |

## 1.11.5: Mails des Kundenportals ohne „Gesendete Elemente“

Probendatei `gp_1115.py`, Lauf mit `tests/test_v804_portal_mails.py`; alle 15 rot aus dem geprüften Grund (FAILED, kein ERROR), alle Dateien
byte-gleich zurück. Eine Gegenprobe in zweiter Fassung: „Absender aus den Firmendaten“ setzte den Marker zuerst mitten in die Zeile (der Rest wurde
Kommentar, ERROR beim Sammeln) -- neu mit dem Marker am Ende der Zeile, dann rot. Nachdem `senden()` je Art einen Aufruf mit fester Versandart bekam
(Wächter test_v355 und test_v371), liefen alle noch einmal, dazu neu „Betreff passt zur Art“.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Arten bekannt, keine Dokumente | Arten nicht in DISPATCH_TYPES | 6 rot |
| Nr. 2 – Betreff ohne Code | Ziffer im Betreff | 2 rot |
| Nr. 2 – fester Betreff in senden() | Betreff aus einem Ausdruck mit dem Text | 4 rot (Wächter und Ablauf) |
| Nr. 2 – Betreff passt zur Art | der Link mit dem Betreff des Codes | 2 rot |
| Nr. 2 – nur senden() nimmt eine Art | zweiter Aufruf mit portal_code in email_dispatch.py | 1 rot |
| Nr. 3 – ohne Kopie über Graph | saveToSentItems immer "true" | 2 rot |
| Nr. 3 – Art des Portals nur ohne Kopie | Prüfung entfernt | 1 rot |
| Nr. 4 – SMTP abgelehnt, bevor etwas geschrieben wird | Prüfung entfernt | 1 rot |
| Nr. 4 – zweite Sicherung im SMTP-Versand | Prüfung entfernt | 1 rot |
| Nr. 5 – Sicherheitshinweis | Satz entfernt | 3 rot |
| Nr. 5 – Begrüßung wie im Portal | nur „Guten Tag,“ | 3 rot |
| Nr. 5 – Absender aus den Firmendaten | ohne Telefon (zweite Fassung) | 3 rot |
| Nr. 5 – „gilt bis“ in Berlin | Tag in UTC | 3 rot |
| Nr. 6 – Fehler nennt nichts vom Text | Fehlermeldung mit dem Text der Mail | 1 rot |

## 1.11.6: der Postbote

Probendatei `gp_1116.py`, Lauf mit `tests/test_v805_portal_postbote.py`; alle 19 beim ersten Anlauf rot aus dem geprüften Grund (FAILED, kein ERROR), alle
Dateien byte-gleich zurück. Ohne eigene Gegenprobe: die Einheit außer Restart (MemoryHigh/Max, Benutzer, ExecStart prüft derselbe Test).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Einheit | Restart=on-failure | 1 rot |
| Nr. 2 – genau ein Postbote | Sperre nicht geprüft | 2 rot |
| Nr. 3 – Weckruf über LISTEN | kein LISTEN | 1 rot |
| Nr. 3 – gehaltene Aufträge übersprungen | NOWAIT statt SKIP LOCKED | 1 rot |
| Nr. 4 – höchstens 10 Minuten alt | Prüfung entfernt | 1 rot |
| Nr. 4 – Zugang gilt | Prüfung entfernt | 6 rot |
| Nr. 4 – Sitzung gültig | Ablauf nicht geprüft | 1 rot |
| Nr. 4 – Grenzen | Prüfung entfernt | 3 rot |
| Nr. 5 – 10 Minuten | 60 Minuten | 1 rot |
| Nr. 5 – frühere Codes gelten nicht | nicht ersetzt | 1 rot |
| Nr. 5 – gescheitert: der Code gilt nicht | nicht ersetzt | 1 rot |
| Nr. 6 – nie zweimal | Versandschlüssel nicht gesucht | 2 rot |
| Nr. 7 – Grund im Protokoll | immer „ungueltig“ | 6 rot |
| Nr. 8 – Codes nach 24 Stunden | 48 Stunden | 1 rot |
| Nr. 8 – Sitzungen nach 30 Tagen | 60 Tage | 1 rot |
| Nr. 8 – Bremsen nach 48 Stunden | 72 Stunden | 1 rot |
| Nr. 8 – Zugriffsprotokoll nach 24 Monaten | 36 Monate | 1 rot |
| Nr. 9 – kein Code im Protokoll | Code ins Protokoll | 2 rot |
| Nr. 1 – nur PostgreSQL | Prüfung entfernt | 1 rot |

## 1.11.7: Stau-Hinweis des Postboten auf „Start“

Probendatei `gp_1117.py`, Lauf mit `tests/test_v806_portal_stau.py` bzw. `scripts/klicktest_portal_stau.py`; alle 10 rot aus dem geprüften Grund, alle
Dateien byte-gleich zurück. Drei Gegenproben in zweiter Fassung (zuerst falsch gebaut, nicht der Code): zweimal stand der Marker mitten in der Zeile
(ERROR beim Sammeln), einmal fehlte er (der Läufer brach vor der Änderung ab).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Monteurin nie | Rolle „field“ an der Schnittstelle | Klicktest: 1 rot (Monteurin bekommt 200) |
| Nr. 1 – ab Büro – Auftrag | erst ab Büro – Finanzen | Klicktest: 3 rot |
| Nr. 2 – länger als 2 Minuten | 1 Minute | 1 rot |
| Nr. 2 – verworfen ist kein Versand | verworfen zählt mit (zweite Fassung) | 1 rot |
| Nr. 2 – ein späterer gesendeter beendet ihn | nur „fehler“ gezählt (zweite Fassung) | 1 rot |
| Nr. 3 – feste Texte | ohne „Kundenportal:“ (zweite Fassung) | 1 rot |
| Nr. 3 – nur als Text | innerHTML | 1 rot |
| Nr. 4 – Schnittstelle nur mit Modul | Prüfung entfernt | 1 rot |
| Nr. 4 – die Seite fragt nur mit Modul | immer an | 1 rot |
| Nr. 4 – ohne Modul keine Anfrage | Abfrage der Seite entfernt | Klicktest: 1 rot |
