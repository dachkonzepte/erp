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

## 1.11.8: Mails des Kundenportals als HTML nach dem Entwurf

Probendatei `gp_1118.py`, Lauf mit `tests/test_v807_portal_mails_html.py` (Nr. 7 mit `tests/test_v804_portal_mails.py`); alle 19 rot aus dem geprüften
Grund, alle Dateien byte-gleich zurück. Der erste Lauf brach bei Nr. 6 („kein Tab“) ab: das Werkzeug hatte die Escape-Folgen für geschützte Leerzeichen als
unsichtbare Zeichen in den Quelltext geschrieben, die Probe fand ihre Zeile nicht -- im Quelltext stehen sie jetzt als `\u00a0` usw.; die drei übrigen
Proben liefen danach. Keine Probe für „die Prüfung des Links auch vor dem Bauen der Mail“: der Knopf prüft selbst, eine der beiden Prüfungen allein genügt.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – kein `<style>` | Stilblock im Kopf | 5 rot |
| Nr. 1 – höchstens 600 px | max-width 640 px | 1 rot |
| Nr. 1 – nur Systemschriften | IBM Plex Sans vorn | 1 rot |
| Nr. 1 – Wortlaut wie im Entwurf | „Ihr Anmeldecode lautet:“ | 1 rot |
| Nr. 1 – Wortmarke in zwei Zeilen | ganzer Name in einer Zeile | 2 rot |
| Nr. 2 – HTML nur für die Mails des Portals | Prüfung entfernt | 1 rot |
| Nr. 2 – Graph bekommt HTML | contentType Text | 1 rot |
| Nr. 2 – SMTP sendet kein HTML | Prüfung entfernt | 1 rot |
| Nr. 3 – jeder Wert maskiert | ohne html.escape | 1 rot |
| Nr. 3 – Link nur in genau dieser Form | jedes http(s)-Ziel | 15 rot |
| Nr. 4 – Adresse wie in der Einheit | portal.dachkonzepte.gmbh | 19 rot |
| Nr. 5 – Impressum und Datenschutz wie die Webseite | /impressum.html | 5 rot |
| Nr. 5 – nur eine gültige Webseite | jede Eingabe als Host | 5 rot |
| Nr. 5 – ohne Telefon bleibt der Satz | Satz entfällt | 1 rot |
| Nr. 6 – Code in Gruppen | ohne Leerzeichen | 1 rot |
| Nr. 6 – Portal nimmt Leerzeichen | nichts entfernt | 6 rot |
| Nr. 6 – nur Leerzeichen, kein Tab | Tab entfernt | 1 rot |
| Nr. 6 – höchstens 20 Zeichen | 100 Zeichen | 1 rot |
| Nr. 7 – „gilt bis“ in Berlin | Tag in UTC | 3 rot |

## 1.11.9: Stau-Hinweis wie die übrigen Warnhinweise, mit „Erledigt“

Probendatei `gp_1119.py`, Lauf mit `tests/test_v808_portal_stau_erledigt.py`; alle 13 rot aus dem geprüften Grund, alle Dateien byte-gleich zurück.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Warnhinweis mit Rand | Rand entfernt | 1 rot |
| Nr. 1 – Link auf die Anmeldecodes | ohne Filter | 1 rot |
| Nr. 2 – Büro ohne den Dienst | Text des Admins fürs Büro | 1 rot |
| Nr. 2 – Admin mit dem Dienst | Text des Büros für alle | 1 rot |
| Nr. 3 – nur der Admin | ab Büro – Auftrag | 1 rot |
| Nr. 3 – „erledigen“ nur für den Admin | für jede Rolle | 1 rot |
| Nr. 3 – nur der gezeigte Fehler | jeder Fehler | 1 rot |
| Nr. 4 – Erledigt beendet den Hinweis | Vermerk nicht gelesen | 2 rot |
| Nr. 4 – ein neuer Fehler zeigt ihn wieder | einmal erledigt, nie wieder | 1 rot |
| Nr. 4 – Name am Auftrag | ohne Name | 1 rot |
| Nr. 4 – Eintrag in der Änderungshistorie | ohne Eintrag | 1 rot |
| Nr. 5 – Filter nur mit Modul | immer | 1 rot |
| Nr. 6 – Migration wie das Modell | Länge 120 statt 160 | 1 rot |

## 1.11.10: Kundenportal am Kunden (P1d, Teil 1)

Probendatei `gp_11110.py`, Lauf mit `tests/test_v809_kundenportal_karte_server.py` (Nr. 8 „Router“ mit `tests/test_v793_archivschutz.py`); alle 22 rot aus dem
geprüften Grund, alle Dateien byte-gleich zurück. Eine Probe blieb zuerst grün: „50 je Seite“ -- der Test rechnete mit `kp.SEITE` wie der Code und prüfte sich
selbst; nachgezogen auf die feste Zahl, dieselbe Probe danach rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Monteurin nie | Rolle „field“ am Lesen | 1 rot |
| Nr. 1 – nur mit Modul | Prüfung entfernt | 1 rot |
| Nr. 2 – aus beendet die Sitzungen | nicht beendet | 1 rot |
| Nr. 2 – Zugang nur mit Portal an | Prüfung entfernt | 1 rot |
| Nr. 3 – nur mit E-Mail am Kunden | Prüfung entfernt | 1 rot |
| Nr. 3 – verdeckte Anzeige | zwei Zeichen | 5 rot |
| Nr. 4 – nur der Prüfwert | Wert selbst gespeichert | 1 rot |
| Nr. 4 – 12 Monate | 6 Monate | 1 rot |
| Nr. 4 – neuer Link meldet alle Geräte ab | nicht abgemeldet | 1 rot |
| Nr. 4 – derselbe Klick erzeugt nichts | Prüfung entfernt | 1 rot |
| Nr. 4 – Ablehnung vor dem Versand ändert nichts | ohne Rollback | 1 rot |
| Nr. 5 – Sperren meldet alle Geräte ab | nicht abgemeldet | 1 rot |
| Nr. 5 – Grund Pflicht | Leerzeichen zählen | 1 rot |
| Nr. 5 – gesperrt: kein neuer Link | Prüfung entfernt | 1 rot |
| Nr. 6 – Verlängern nur mit Link | Prüfung entfernt | 1 rot |
| Nr. 7 – läuft in 30 Tagen ab | 10 Tage | 1 rot |
| Nr. 8 – Zustand „Im Archiv“ | Zweig entfernt | 1 rot |
| Nr. 8 – auch die Geschäftslogik lehnt ab | Prüfung entfernt | 1 rot |
| Nr. 8 – der Router lehnt vorab ab | ohne archiv_vorab() | 1 rot (test_v793) |
| Nr. 9 – Prüfwert nie in der Historie | Prüfwert protokolliert | 2 rot |
| Nr. 9 – jede Aktion in Worten | ein Text fehlt | 1 rot |
| Nr. 9 – 50 je Seite | 500 je Seite (zweite Fassung des Tests) | 1 rot |

## 1.11.11: Karte „Kundenportal“ in der Kundenakte (P1d, Teil 2)

Probendatei `gp_11111.py`, Lauf mit `tests/test_v810_kundenportal_karte_seite.py`, `tests/test_v809_kundenportal_karte_server.py`, `tests/test_v795_nur_lesen.py`
bzw. `scripts/klicktest_kundenportal_karte.py`; alle 14 rot aus dem geprüften Grund, alle Dateien byte-gleich zurück. Ohne eigene Probe: Nr. 6 „im Archiv keine
Aktion“ -- zwei Sicherungen auf der Seite (Zustand der Karte und `_nur_lesen.html`), je eine allein entfernt bleibt der Klicktest grün; geprüft sind das
Lesen (unten) und der Server (409, 1.11.10 Nr. 8). Eine Probe blieb zuerst grün: „ohne Buchhaltung des Zugangs“ ist doppelt gesichert (in der Abfrage
und im Satz); die Abfrage verhindert, dass viele neuere solche Einträge die sichtbaren aus der Seite drängen -- dafür ein neuer Test, dieselbe Probe danach rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Karte nur mit Modul | Bedingung entfernt | 1 rot |
| Nr. 1 – ungerendert ohne Portal | „!== nein“ | 1 rot |
| Nr. 2 – gesperrt: kein „Sperren“ | „Sperren“ auch gesperrt | Klicktest rot |
| Nr. 3 – E-Mail des Kunden vorbelegt | leer | Klicktest rot |
| Nr. 3 – Warnung beim neuen Link | nie | Klicktest rot |
| Nr. 4 – Sperren abschließend | speichern() | 1 rot |
| Nr. 5 – Rückfrage vor dem Verlängern | ohne confirm() | 1 rot |
| Nr. 6 – im Archiv bleibt „Protokoll“ | ohne data-lesen | 1 rot (test_v795) |
| Nr. 7 – Protokoll als Sätze | Feldname statt Satz | 1 rot |
| Nr. 7 – gesendete Links im Protokoll | ohne Versand | 1 rot |
| Nr. 7 – ohne Buchhaltung des Zugangs | alle Felder in der Abfrage (zweite Fassung des Tests) | 1 rot |
| Nr. 8 – Attrappe nur für Test-Instanzen | ohne ERP_ENV | 1 rot |
| Nr. 8 – Attrappe nur auf 127.0.0.1 | jede Adresse | 1 rot |
| Nr. 9 – nur als Text | innerHTML | 1 rot |

## 1.11.12: Pflichtangaben in der Fußzeile der Mails

Probendatei `gp_11112.py`, Lauf mit `tests/test_v807_portal_mails_html.py`; alle 5 rot aus dem geprüften Grund, die Datei byte-gleich zurück. Nr. 2 brach im
ersten Lauf mit einem Syntaxfehler ab (der Marker stand mitten in der Zeile) -- neu mit der ganzen Zeile, dann rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Zeile in beiden Mails | nie | 23 rot |
| Nr. 1 – klein und zuletzt | vor der Fußzeile | 23 rot |
| Nr. 2 – „Sitz <Ort>“ | Ort ohne „Sitz“ | rot |
| Nr. 3 – fehlt ein Feld, fällt nur dieses weg | Zeile nur mit allen Feldern | 5 rot |
| Nr. 4 – Werte maskiert | ohne html.escape() | 1 rot |

## 1.11.13: Karte nach den Antworten des Betriebs

Probendateien `gp_11113.py` und `gp_11113b.py`, Lauf mit `tests/test_v809_kundenportal_karte_server.py`, `tests/test_v793_archivschutz.py`,
`tests/test_v795_nur_lesen.py` bzw. `scripts/klicktest_kundenportal_karte.py`; alle 17 rot aus dem geprüften Grund, alle Dateien byte-gleich zurück. Nr. 5 „eine
Zeile je Aktion“ brach im ersten Lauf mit einem Einrückungsfehler ab (die Zeile darunter hing am ersetzten `if`) -- neu mit `if True:`, dann rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „gescheitert“ ein eigener Zustand | Zweig entfernt | 3 rot |
| Nr. 1 – gesperrt und abgelaufen gehen vor | „gescheitert“ zuerst | 1 rot |
| Nr. 1 – Kennzeichen in Warnfarbe | chip-ok | Klicktest rot |
| Nr. 2 – „Link erneut senden“ | Titel nie | Klicktest rot |
| Nr. 2 – ohne Warnung | Warnung auch dort | Klicktest rot |
| Nr. 3 – Verlängern nur, solange der Link gilt (Server) | auch abgelaufen und gescheitert | rot |
| Nr. 3 – kein „Verlängern“ bei abgelaufen (Seite) | Knopf auch dort | Klicktest rot |
| Nr. 4 – Sperren im Archiv: ohne Prüfung vorab | archiv_vorab() an der Route | 2 rot |
| Nr. 4 – Sperren im Archiv: Geschäftslogik | Archiv geprüft | 1 rot |
| Nr. 4 – Sperren im Archiv: Knopf bleibt | ohne data-lesen | 1 rot (test_v795) |
| Nr. 4 – Feld „Grund“ im Archiv frei | ohne data-lesen | Klicktest rot |
| Nr. 5 – eine Zeile je Aktion | nie zusammen | rot |
| Nr. 5 – Felder einer Aktion der Reihe nach | Reihenfolge ungeprüft | 2 rot |
| Nr. 5 – nur verträgliche Arten | jede Art zusammen | 2 rot |
| Nr. 5 – der Link mit seinem Versand | nie zugeordnet | rot |
| Nr. 6 – „Neuer Link“ aus dem Versandprotokoll | aus der Historie | 1 rot |

## 1.11.14: die Seiten des Kundenportals (P1e)

Probendatei `gp_11114.py`, Lauf mit `tests/test_v811_portal_seiten.py` bzw. `scripts/klicktest_portal_seiten.py`; alle 20 rot aus dem geprüften Grund, alle Dateien
byte-gleich zurück. Nr. 7 lief danach ins Zeitlimit der Gegenprobe (jede Ansicht wartet bis 5 s auf das dunkle Thema) -- die geprüfte Zeile war vorher rot.
Ohne eigene Probe: Nr. 12 (nur Anordnung, gezeigt in den Bildern). Nach dem Fix für `test_v406` (fester Typ je Weg) Nr. 2 „Skript und Stil ein Jahr“ gegen
die neue Zeile noch einmal (`gp_11114b.py`): rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Wortlaut der Entwürfe | ein Satz anders | 1 rot |
| Nr. 2 – kein style-Attribut | style an einem span | 1 rot |
| Nr. 2 – Skript und Stil ein Jahr | ohne Cache-Control | 1 rot |
| Nr. 2 – Design-Dateien ein Jahr | Zweig der Schranke aus | 1 rot |
| Nr. 2 – ?v= aus dem Inhalt | fester Wert | 2 rot |
| Nr. 3 – nur Text | innerHTML | 1 rot |
| Nr. 4 – Link aus der Adresse | ohne replaceState | 1 rot |
| Nr. 5 – Telefon international | ohne +49 | rot |
| Nr. 5 – nur gültige E-Mail | jede Angabe als mailto: | 2 rot |
| Nr. 5 – jeder Wert maskiert | autoescape aus | rot |
| Nr. 5 – Handy angemeldet: nur „Kundenportal“ | Regel aus | Klicktest rot |
| Nr. 6 – 404 als Fehlerseite | Zweig aus | 1 rot |
| Nr. 6 – ohne Firmendaten „technisch“ | Ausnahme weiter | 1 rot |
| Nr. 6 – 502: Gleich wieder da | „technisch“ | Klicktest rot |
| Nr. 7 – hell oder dunkel nach dem Gerät | immer hell | Klicktest rot |
| Nr. 8 – Neuladen setzt fort | nichts gemerkt | Klicktest rot |
| Nr. 9 – 60 Sekunden bis „Neuen Code senden“ | kein Zähler | Klicktest rot |
| Nr. 10 – keine 6 Ziffern | ohne Prüfung | Klicktest rot |
| Nr. 11 – überall nur mit Rückfrage | ohne Dialog | Klicktest rot |
| Nr. 11 – noscript | verborgen | 1 rot |

## 1.11.15: „Gleich wieder da“ von nginx

Probendatei `gp_11115.py`, Lauf mit `tests/test_v812_portal_wartung.py`; alle 6 rot aus dem geprüften Grund, alle Dateien byte-gleich zurück.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ohne Skript | ein script | 1 rot |
| Nr. 1 – Wortlaut | anderer Satz | 1 rot |
| Nr. 1 – hell und dunkel nach dem Gerät | andere Abfrage | 2 rot |
| Nr. 2 – bei 502 und 504 | nur 502 | 1 rot |
| Nr. 3 – Prüfsumme des Stils | Stil geändert | 1 rot |
| Nr. 3 – Schutz-Kopfzeilen | ohne X-Frame-Options | 1 rot |

## 1.11.16: der Versand des Codes dauert länger

Probendateien `gp_11116.py` und `gp_11116b.py`, Lauf mit `tests/test_v811_portal_seiten.py` bzw. `scripts/klicktest_portal_seiten.py`; alle 7 rot aus dem geprüften
Grund, alle Dateien byte-gleich zurück. Nr. 4 blieb zuerst grün: ohne die Abzweigung beim Neuladen kommt die Schleife beim ersten Nachfragen zum selben Ergebnis
(die Abzweigung spart nur das kurze Aufblitzen von B) -- die Probe trifft jetzt den gemerkten Zeitpunkt der Anforderung, rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nach 30 Sekunden weiter zu C | 3000 Sekunden | Klicktest rot |
| Nr. 2 – nach 10 Minuten gescheitert | 100 Minuten | Klicktest rot |
| Nr. 3 – 60 Sekunden ab der Anforderung | ab jetzt | Klicktest rot |
| Nr. 4 – Neuladen setzt das Warten fort | Zeitpunkt nicht gemerkt | Klicktest rot |
| Nr. 5 – die Eingabe bleibt stehen | C neu gezeichnet | Klicktest rot |
| Nr. 6 – breit direkt unter dem Inhalt | wie auf dem Handy | Klicktest rot |
| Nr. 7 – Hinweis in den Farben für Fortschritt | grün | 1 rot |

## 1.11.17: Name, Anschrift und Pflichtangaben unter jeder Mail an Kunden

Probendatei `gp_11117.py`, Lauf mit `tests/test_v813_firmenangaben_mails.py`; alle 6 rot aus dem geprüften Grund, alle Dateien byte-gleich zurück. Bei Nr. 4
blieb die Angebotsmail grün -- ihr Text endet ohne Leerraum; rot sind jede Versandart und die fehlenden Felder (die Texte dort enden mit einem Zeilenende).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – jede Versandart an Kunden mit dem Schluss | „rechnung“ ohne Schluss | 5 rot |
| Nr. 2 – Aufgaben-Mails ohne | `OHNE_FIRMENANGABEN` leer | 2 rot |
| Nr. 3 – ohne jede Angabe kein Schluss | immer eine Leerzeile | 1 rot |
| Nr. 4 – Leerraum am Ende weg, genau eine Leerzeile | ohne `rstrip()` | 13 rot |
| Nr. 5 – eine Quelle für Portal und ERP | Portal mit eigener Anschrift | 2 rot |
| Nr. 6 – Portal ohne zweiten Schluss | auch an die HTML-Mail | 1 rot |
| Nr. 7 – Vorlagen und Textfeld ohne Schluss | keine eigene Gegenprobe: Ort im Code; Nr. 1 und das Beispiel prüfen den Schluss am Ausgang von `dispatch_email()`, die Angebotsmail genau einmal | – |

## Vorbereitung P1f: Server-Schritte und Datenschutz (nur Doku)

Keine Gegenprobe möglich: die Festlegungen V1–V8 sind eine Anleitung für den Server bzw. Stichpunkte für die Datenschutzerklärung -- es gibt keinen Schutz im
Code, den eine Probe aushebeln könnte. Geprüft werden sie in P1f auf dem Server (Erwartung und Abbruch je Schritt). Lokal nachgeprüft: die Shell-Ausschnitte von
S0, S3 und S7 an erfundenen Daten.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| V1 – pg_hba: dkportal nur zu dachkonzepte über 127.0.0.1 | keine: Anleitung; geprüft in S3 (drei Verbindungen ohne Passwort) | – |
| V2 – Passwort nie angezeigt, nie im Log | keine: Anleitung; Ablauf in S3 | – |
| V3 – S3b nur vor PostgreSQL 15 | keine: Anleitung; `--pruefen` meldet den Fall (W5) | – |
| V4 – Rechte nur gegen dachkonzepte | keine: Anleitung (update.sh liegt nur auf dem Server) | – |
| V5 – drei Dienste zusammen neu starten | keine: Anleitung | – |
| V6 – E4 fürs ERP mit erfundenem Namen | keine: Anleitung | – |
| V7 – erst Port 80, dann die ganze Datei | keine: Anleitung; der Ausschnitt lokal nachgeprüft | – |
| V8 – Datenschutz: zwei Cookies, Speicher des Tabs | keine: Doku; die Cookies prüfen `test_v802_portal_sitzung.py`, der Speicher `test_v811_portal_seiten.py` | – |

## 1.11.19: Satz unter den Mailvorlagen

Probendateien `gp11119.py` (Nr. 1, 2, 4, 5 mit `tests/test_v814_mail_schluss_hinweis.py`; Nr. 3 mit `scripts/klicktest_mail_schluss.py`) und `gp11119_nr3b.py`;
alle Dateien byte-gleich zurück. Nr. 3 war im ersten Lauf rot aus dem falschen Grund: die Probe blendete den ersten Satz im Dokument aus -- der gehört zur ersten
Mahnstufe (der Bereich „Mahnwesen“ steht im Dokument vor den Vorlagen), rot wurde „Mahnwesen“ statt der Vorlagen. Wiederholt mit dem Satz der Vorlagen: rot an
der geprüften Stelle.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Satz unter „Text“ der Vorlagen | Satz heraus | 5 rot |
| Nr. 2 – Satz unter „E-Mail-Text“ jeder Mahnstufe | Satz heraus | 4 rot |
| Nr. 3 – immer, auch bei gesperrtem Feld | bei gesperrter Mahnstufe ausgeblendet | Klicktest rot (Büro – Auftrag, Vorlagen) |
| Nr. 3 – immer, auch ohne Firmendaten | keine eigene Gegenprobe: der Satz hängt an keiner Bedingung, eine müsste erfunden werden; Test und Klicktest laufen ohne Firmendaten | – |
| Nr. 4 – jede Art der Auswahl mit Schluss | das Angebot in `OHNE_FIRMENANGABEN` | 1 rot |
| Nr. 5 – nur unter den Vorlagen | der Satz auch beim Versand des Angebots | 1 rot |

## 1.11.20: nginx des Kundenportals nur über IPv4

Probendatei `gp11120.py` mit `tests/test_v815_nginx_nur_ipv4.py`; die Datei byte-gleich zurück.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Port 80 nur über IPv4 | `listen [::]:80;` wieder im ersten Block | 2 rot |
| Nr. 1 – Port 443 nur über IPv4 | `listen [::]:443 ssl http2;` wieder im zweiten Block | 2 rot |
| Nr. 1 – der erste Teil zählt für S7 `1` und `0` | ein Kommentar im Kopf nennt „listen 443“ | 1 rot |
| Nr. 2 – S1 ohne AAAA für kunde | keine: Anleitung für den Server; geprüft in S1 (`dig`) | – |
| Nr. 3 – S0 erwartet nur `0.0.0.0` | keine: Anleitung; geprüft in S0 (`ss -ltn`) | – |
| Nr. 4 – S7 prüft zuerst die Datei auf dem Server | keine: Anleitung; geprüft in S7 (`grep`) | – |
| Nr. 5 – IPv6 später nur zusammen | keine: Arbeitsweise | – |

## 1.11.21: das Skript für die Rechte des Portals

Probendatei `gp11121.py` mit `tests/test_v816_portal_rechte_skript.py` allein; `scripts/portal_rechte.py` je Fall byte-gleich zurück. Nr. 2b war im ersten
Lauf schon rot an der geprüften Stelle (`--pruefen` nach dem Setzen Rückgabe 1), nur mein Suchtext im Probenlauf passte nicht zur gekürzten Ausgabe von
pytest -- berichtigt und alle drei noch einmal.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Transaktion von der ersten Anweisung an | die alte Reihenfolge: Name der Datenbank, dann `conn.begin()` | 1 rot („already initialized a SQLAlchemy Transaction“) |
| Nr. 2 – vorher meldet `--pruefen` Abweichungen | `--pruefen` meldet nie eine | 1 rot (vorher Rückgabe 0 statt 1) |
| Nr. 2 – nach `--setzen` stimmt `--pruefen` | `--setzen` ohne Commit (meldet „gesetzt“, setzt nichts) | 1 rot (`--pruefen` danach Rückgabe 1) |

## 1.11.22: gunicorn ohne Steuer-Socket

Probendatei `gp11122.py`: `--no-control-socket` aus `scripts/server/erp-portal.service` genommen, beide Tests einzeln; die Einheit danach byte-gleich zurück
(SHA-256 verglichen). Ohne die Option meldet die Attrappe den Start des Steuer-Sockets -- der Weg des Hauptprozesses ist also erreicht, nicht still grün.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1, 2 – der Hauptprozess startet keinen Steuer-Socket | ExecStart ohne `--no-control-socket` | `test_kein_steuer_socket` rot („der Hauptprozess startete den Steuer-Socket“) |
| Nr. 1, 2 – die Option steht in der Einheit | ExecStart ohne `--no-control-socket` | `test_einheit_des_dienstes` rot (`"--no-control-socket" in start.split()`) |
| Nr. 3 – ERP | keine: `erp.service` liegt nur auf dem Server | -- |
| Nr. 4 – Einheit neu installieren | keine: Schritt auf dem Server (Doku) | -- |

## 1.11.23: Begrüßung ohne Komma

Probendatei `gp11123.py`; jede Datei danach byte-gleich zurück (SHA-256 verglichen).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Portal und Mail ohne Komma nach „Guten Tag“ | Komma zurück in `begruessung.py` (Herr/Frau) | `test_v817::test_portal_und_mail`, `test_v802::test_begruessung`, `test_v807` rot („Guten Tag, Herr Dr. Muster“) |
| Nr. 2 – kein Komma unter `app/`, auch nicht über die Konstante | dieselbe Probe (`{GRUSS},`) | `test_kein_komma_nach_guten_tag_unter_app` rot (`app/portal/begruessung.py:…`) |
| Nr. 2 – kein fester Text mit Komma | in `portal.js` „Guten Tag, Gast“ als Rückfall | `test_kein_komma_nach_guten_tag_unter_app` rot (`app/portal/seiten/portal.js:…`) |

## 1.11.24: Knopf der Mail als Tabellenzelle mit Polster

Probendatei `gp11124.py`; `app/portal_mails.py` danach byte-gleich zurück (SHA-256 verglichen).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Polster an der Zelle, nicht am Link | Fassung bis 1.11.23 (Polster und `inline-block` am Link) | `test_knopf_polster_an_der_zelle` rot (`padding:14px 24px` fehlt an der Zelle) |
| Nr. 1 – Hintergrund an der Zelle, nicht am Link | Hintergrund an den Link verlegt | `test_knopf_polster_an_der_zelle` rot (`background-color:#` fehlt an der Zelle) |

## 1.11.25: e4 und Postbote als Kindprozess, `_waits_for()`

Probendatei `gp11125.py`; jede Datei danach byte-gleich zurück (SHA-256 verglichen). Nr. 2b blieb nicht beim Warten hängen: ohne die Sperre des Mangels
wartete die zweite Aktion an einer anderen Stelle und schrieb danach einen zweiten Eintrag -- rot am Ergebnis, nicht an „hat nicht gewartet“. Deshalb Nr. 2c:
eine zweite Aktion ganz ohne Datenbank.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – e4 läuft als Kindprozess gegen PostgreSQL | Rahmenfehler wie in S5: `begin()` nach der ersten Anweisung | `test_pg_pruefe_portal_e4_als_kindprozess` rot („Datenbank nicht lesbar: InvalidRequestError“, Rückgabe 2) |
| Nr. 1 – ein zweiter Postbote endet mit 3 | ohne die Sperre der Datenbank (`SELECT true`) | `test_pg_postbote_als_kindprozess` rot (der zweite läuft weiter, `TimeoutExpired`) |
| Nr. 2 – die Sperre bleibt geprüft | `_lock()` in `app/defects.py` ohne `FOR UPDATE` | `test_postgresql_two_status_changes_at_once` rot (zwei Einträge statt 409) |
| Nr. 2 – „hat gewartet“ prüft `_waits_for()` | die zweite Aktion ohne Datenbank (`test_v352`) | rot („die zweite Aktion hat nicht auf die Sperre der ersten gewartet“) |
| Nr. 2 – `join` auf die erste Aktion | erste Aktion 1,5 s langsam nach dem Commit, mit `join` | grün |
| Nr. 2 – `join` auf die erste Aktion | dieselbe Probe ohne `join` | `test_postgresql_sync_waits_for_a_running_acceptance` rot (Ergebnis der ersten noch nicht da) |
| Nr. 3 – Befund ohne Änderung | keine: nur Befund und Doku | -- |

## 1.11.26: update.sh vergleicht die Einheiten

Probendatei `gp11126.py`; jede Datei danach byte-gleich zurück (SHA-256 verglichen).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – eine Abweichung wird gemeldet | jede installierte Einheit gilt als gleich | `test_abweichung_und_fehlende_mit_befehl_nichts_installiert` rot |
| Nr. 1 – nichts installiert | bei einer Abweichung die Fassung des Repos hineinschreiben | derselbe Test rot (der Ordner der installierten Einheiten ändert sich) |
| Nr. 2 – nur vor genau einer Zeile FERTIG | nur bei 0 Zeilen abbrechen | `test_nur_bei_eindeutiger_stelle[…2-mal]` rot |
| Nr. 3 – Dienst mit Timer ohne Neustart | die Prüfung auf den Timer entfernt | `test_dienst_mit_timer_ohne_neustart` rot |

## 1.11.27: lokal Python 3.14

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Suite läuft mit Python 3.14 | `test_v803` mit der alten `.venv` (Python 3.13.15) | `test_python_wie_auf_dem_server` rot („die Suite läuft mit Python 3.13, der Server mit 3.14“) |
| Nr. 2 – Pakete unverändert | keine Gegenprobe: Vergleich `pip freeze` beider Umgebungen (gleich) | -- |
| Nr. 3 – `setup_windows.bat` nur mit 3.14 | keine Gegenprobe: Datei für Windows ohne Test; einmal von Hand geprüft (Bericht) | -- |
| Nr. 4 – alte `.venv` beiseite | keine: Arbeitsweise | -- |

## 1.11.28: Knopf der Mail wieder ganz klickbar

Probendatei `gegenprobe_11128.py` (Scratchpad); je Probe eine Zeile von `_knopf()` mit Marker `GEGENPROBE`, `app/portal_mails.py` danach byte-gleich zurück
(SHA-256 verglichen). Jede Probe: `test_knopf_ganze_flaeche_und_outlook` rot an genau der Prüfung der Aussage.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Outlook am Rechner polstert über die Zelle | `mso-padding-alt` an der Zelle entfernt | rot (`mso-padding-alt` fehlt) |
| Nr. 1 – ganze Fläche klickbar | `display:inline-block` am Link entfernt | rot (`display`) |
| Nr. 1 – ganze Fläche klickbar | `padding` am Link entfernt | rot (Polster des Links ungleich `mso-padding-alt`) |
| Nr. 1 – kein doppeltes Polster | `padding:14px 24px` zusätzlich an der Zelle (wie 1.11.24) | rot (`padding` an der Zelle) |
| Nr. 1 – dasselbe Polster | Link `12px 20px`, Zelle `14px 24px` | rot (Polster ungleich) |
| Nr. 1 – Hintergrund nur an der Zelle | Hintergrund zusätzlich am Link | rot (Hintergrund am Link) |

## 1.11.29: feste Fassung des Einsatzberichts beim Unterschreiben

Probendatei `gegenprobe_11129.py` (Scratchpad); je Probe eine Stelle unter `app/` mit Marker `GEGENPROBE`, jede Datei danach byte-gleich zurück (SHA-256
verglichen). Jede Probe: der Test der Aussage in `tests/test_v819_einsatzbericht_feste_fassung.py` rot an genau ihrer Prüfung.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Fassung bei der Unterschrift | Aufruf von `_feste_fassung()` entfernt | rot (keine Fassung am Bericht) |
| Nr. 2 – Download aus der Ablage | Route fragt eine Art ohne Ablage ab (neu erzeugt) | rot (Renderer läuft nach der Unterschrift) |
| Nr. 3 – nichts gespeichert: Bilder | Löschen der Unterschriftsbilder entfernt | rot (Bilder liegen noch) |
| Nr. 3 – nichts gespeichert: Daten | Zurückrollen entfernt | rot (Status „unterschrieben“ in der Sitzung) |
| Nr. 4 – Fassung steht fest | Wächter am Modell wirft nicht | rot (keine Ausnahme) |
| Nr. 5 – kein Abruf legt nachträglich ab | Route legt bei fehlender Fassung eine ab | rot (`X-DK-Ablage` beim zweiten Abruf) |
| Nr. 6 – nicht zustellbar | Eintrag im Verzeichnis liefert ein Dokument | rot (keine Ausnahme) |
| Nr. 7 – eine Unterschrift bei zweien (PostgreSQL) | FOR UPDATE beim Laden entfernt | rot (die zweite endet nicht mit „bereits unterschrieben“) |

Nr. 8 (Ansicht der Monteurin bleibt neu erzeugt) ohne Gegenprobe: dort ist nichts geändert.

## 1.11.30: ein Objekt wechselt den Kunden nur geprüft

Probendatei `gegenprobe_11130.py` (Scratchpad); je Probe eine Stelle unter `app/` mit Marker `GEGENPROBE` (bzw. eine Zeile weg), jede Datei danach
byte-gleich zurück (SHA-256 verglichen). Jede Probe: der Test der Aussage rot an genau ihrer Prüfung.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ein Projekt sperrt | Projekt aus `SPERREN` entfernt | rot (200 statt 409) |
| Nr. 1 – der Router prüft | Router setzt den Kunden an `kunde_wechseln()` vorbei | rot (200 statt 409) |
| Nr. 2 – Hauptadresse | Prüfung der Hauptadresse entfernt | rot (200 statt 409) |
| Nr. 3 – nur mit Begründung | Prüfung der Begründung entfernt | rot (dreimal 200 statt 422) |
| Nr. 4 – Eintrag in der Historie | `record_audit_entry()` übergangen | rot (kein Eintrag) |
| Nr. 5 – derselbe Kunde ist kein Wechsel | Rückkehr bei gleichem Kunden entfernt | rot (409 statt 200) |
| Nr. 6 – jeder Fremdschlüssel eingeordnet | Dachflächen aus `WANDERT_MIT` entfernt | rot (Liste ungleich) |

Nr. 7 (keine Oberfläche) ohne Gegenprobe: nichts gebaut.

## 1.11.31: Freigaben und Lese-Funktionen der Unterlagen (P2a)

Probendatei `gegenprobe_11131.py` (Scratchpad); je Probe eine Stelle unter `app/` mit Marker `GEGENPROBE`, jede Datei danach byte-gleich zurück (SHA-256
verglichen). Die Funktionen entstehen in jedem Testschema aus `app/portal/unterlagen.py` -- eine Änderung dort wirkt im Test. Jede Probe: der Test der
Aussage in `tests/test_v821_portal_unterlagen.py` rot an genau ihrer Prüfung.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur mit bereiter Kopie | Bedingung „Kopie bereit“ aus der Liste entfernt | rot (Freigabe ohne Kopie in der Liste) |
| Nr. 2 – Kette führt zum Kunden | Vergleich mit dem Kunden der Kette in der Liste entfernt | rot („Rechnung mit anderem Kunden“) |
| Nr. 3 – Rechnung im Entwurf nie | Bedingung „kein Entwurf“ entfernt | rot („Entwurf, Bericht ohne Fassung“) |
| Nr. 3 – Bericht nur mit fester Fassung | Bedingung „feste Fassung“ entfernt | rot („Entwurf, Bericht ohne Fassung“) |
| Nr. 3 – ersetzte Mahnung nie | Bedingung „nicht ersetzt“ entfernt | rot („Mahnung ersetzt“) |
| Nr. 3 – Mustervorgang und Archiv nie | `portal_projekt_offen()` liefert immer wahr | rot (`is_template`) |
| Nr. 4 – jede Quelle ein Zweig | ein Zweig umbenannt | rot (Liste der Zweige ungleich) |
| Nr. 5 – Auftragsnummer statt Projekttitel | Zweig „auftrag“ liefert den Projekttitel | rot („Interner Titel“) |
| Nr. 6 – Anforderung höchstens 30 Minuten alt | Zeitfenster entfernt | rot (nach 31 Minuten noch „ok“) |
| Nr. 6 – Anforderung derselben Sitzung | Vergleich der Sitzung entfernt | rot (zweites Gerät bekommt die Datei) |
| Nr. 7 – Bremse der Anforderung | Grenze je Zugang 300 000 statt 300 | rot (kein „bremse“) |
| Nr. 7 – Protokoll der Anforderung | Eintrag „ok“ entfernt | rot (Protokoll ohne Anforderung) |
| Nr. 8 – kein Helfer für die Rolle | `portal_quelle` in die Rechte des Portals aufgenommen | rot („Helfer ausführbar: portal_quelle“) |
| Nr. 9 – eine aktive Freigabe je Quelle | Teilindex nicht eindeutig | rot (keine Ausnahme) |
| Nr. 9 – Rückweg des Adressimports | Prüfung der Freigabe entfernt | rot (Lauf gilt als unberührt) |
| Nr. 11 – Text „nicht verfügbar“ | Ergebnis je Aktion nicht beachtet | rot („unbekannter Link“) |

Nr. 10 (Quelle ohne Fremdschlüssel) ohne eigene Gegenprobe: sie ist im Schema sichtbar (keine Spalte mit Fremdschlüssel), `test_pg_kette_…` löscht eine Quelle
und prüft, dass die Freigabe bleibt. Beim ersten Lauf blieb Nr. 8 grün -- der Test prüfte nur den Fehlercode, den ein Helfer ohne SECURITY DEFINER ohnehin
an den Tabellen bekommt; seitdem prüft er das Recht selbst (`has_function_privilege`).

## 1.11.32: Matrix je Quelle und Fall, zwei Lücken der Kette

Probendatei `gegenprobe_11132.py` (Scratchpad); je Probe eine Stelle unter `app/` mit Marker `GEGENPROBE`, jede Datei danach byte-gleich zurück (SHA-256
verglichen). Je Zweig von `portal_quelle()`: die Kette durch den Kunden der Freigabe selbst ersetzt (`SELECT x.customer_id` -> der `customer_id` der
Freigabe) -- die Zelle „fremder Kunde“ jeder Zeile dieses Zweigs rot („fremde Freigabe sichtbar“).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| 1.11.31-2 – Kette Rechnung | Zweig `invoices` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Mahnung | Zweig `reminders` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Ablage | Zweig `sent_documents` ohne Kette (alle drei Teile) | rot (3 Zellen: Angebot, Auftrag, Vertrag) |
| 1.11.31-2 – Kette Einsatzbericht | Zweig `service_reports` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Checkliste | Zweig `checklist_versions` ohne Kette (Auftrag und Objekt) | rot (2 Zellen) |
| 1.11.31-2 – Kette Brief | Zweig `notice_letters` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Foto des Berichts | Zweig `service_report_photos` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Kundendokument | Zweig `customer_documents` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Projektdokument | Zweig `project_documents` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Objektdokument | Zweig `property_documents` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Datei am Mangel | Zweig `defect_files` ohne Kette | rot (1 Zelle) |
| 1.11.31-2 – Kette Beleg der Abnahme | Zweig `order_acceptance_files` ohne Kette | rot (1 Zelle) |
| 1.11.32-1 – Brief ruht nach verworfener Unterschrift | Bedingung entfernt | rot (`notice_letters-quelle_ungueltig`) |
| 1.11.32-2 – Foto am Mangel ruht nach verworfenem Mangel | Bedingung entfernt | rot (`defect_files-quelle_ungueltig`) |
| Test Berliner Zeit (Vorgabe) | Zeile „Bestätigt von“ ohne `to_berlin()` | rot (Winter und Sommer: nur eine der zwei Zeiten in Berliner Zeit) |

Nr. 3 (jede Zelle Test oder „entfällt“) ohne Gegenprobe unter `app/`: der Wächter `test_jede_zelle_getestet_oder_entfaellt` prüft die Liste selbst.

## 1.11.33: Kopien der freigegebenen Unterlagen (P2b, Teil 1)

Probendatei `gegenprobe_11133.py` (Scratchpad, mit `--trocken` vorab geprüft, dass jede Änderung genau einmal passt); je Probe eine Stelle mit Marker
`GEGENPROBE` in der geänderten Zeile (die Einheit unter `scripts/server/` ohne Marker -- systemd kennt keinen Kommentar hinter einem Wert), danach jede Datei
byte-gleich zurück (SHA-256 verglichen).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| 1.11.33-2 – PDF nur mit Prüfsumme der Ablage | Datei der Ablage ohne Prüfung gelesen | rot (`[pruefsumme]`) |
| 1.11.33-2 – PDF byte-gleich | ein Byte angehängt | rot (13 Zeilen der Matrix mit PDF) |
| 1.11.33-1 – Name zufällig mit Endung | Endung .bin | rot (`[invoices]`) |
| 1.11.33-4 – höchstens 25 MB | Prüfung der Größe entfernt | rot (`[zu_gross]`) |
| 1.11.33-3 – ohne Angaben aus der Datei | Kind gibt den Eingang zurück | rot (Metadaten, ZIP, HTML) |
| 1.11.33-3 – Drehung angewandt | Drehung entfernt | rot (Maße) |
| 1.11.33-3 – Grenze für Speicher | Grenze nicht gesetzt | rot (Bild 6000 × 6000 geht durch) |
| 1.11.33-3 – Zeitgrenze | ohne timeout | rot (Dauer) |
| 1.11.33-3 – über der Pixelgrenze schon zu groß | Prüfung und Warnung als Fehler entfernt | rot (72 Mio. Bildpunkte) |
| 1.11.33-3 – Kind ohne Geheimnisse | ganze Umgebung weitergegeben | rot |
| 1.11.33-6 – Kunde im Archiv: Kopie weg | Bedingung `archiviert_am` entfernt | rot |
| 1.11.33-6 – Datei nach der Zeile weg | Löschen der Datei entfernt | rot |
| 1.11.33-7 – Waisen weg | Löschen der Waisen entfernt | rot (die Waise bleibt liegen) |
| 1.11.33-8 – fremder Ordner unberührt | Prüfung der Kennung entfernt | rot (keine OrdnerFremd) |
| 1.11.33-5 – kein zweiter Versuch | Bedingung `kopie_fehler IS NULL` entfernt | rot (7 Fehlerwörter; schon der erste Lauf wiederholt dieselbe Zeile bis zur Zeitgrenze, 707-mal) |
| 1.11.33-1 – Rücknahme während des Kodierens | Bedingung `zurueckgenommen_am` im UPDATE entfernt | rot |
| 1.11.33-1 – Teil-Datei nach Abbruch weg | Aufräumen der Teil-Datei entfernt | rot |
| 1.11.33-10 – Zeitgrenze je Durchgang | Zeitgrenze nie erreicht | rot |
| 1.11.33-9 – Weckruf nur bei Freigabe und Rücknahme | Auslöser auf jedes UPDATE | rot (`[1, 1, 1, 1]`) |
| 1.11.33-9 – Postbote legt auf den Weckruf an | Weckruf nicht ausgewertet | rot (keine Kopie in 20 s) |
| 1.11.33-11 – Fehler am Ordner beendet ihn nicht | Ausnahme nicht abgefangen | rot |
| 1.11.33-13 – Sperre am Ende frei | Freigabe der Sperre entfernt | rot |
| 1.11.33-5 – Fehlerwort „fehlt“ | „fehlt“ aus `KOPIE_FEHLER` | rot (Wörter des Moduls ≠ Liste) |
| 1.11.33-12 – Speicher der Einheit | MemoryMax 256M | rot |

Ohne Gegenprobe: 1.11.33-1 „gegengelesen“ -- eine Abweichung zwischen geschriebener und gelesener Datei lässt sich ohne Eingriff ins Dateisystem nicht
herbeiführen (nur Durchsicht); 1.11.33-1 „0640“ prüft der Test nur unter Linux (hier Windows), auf dem Server zeigt P2b-3 die Rechte.

## 1.11.34: Auslieferung über nginx (P2b, Teil 2)

Probendatei `gegenprobe_11134.py` (Scratchpad, mit `--trocken` vorab geprüft); unter `app/` mit Marker `GEGENPROBE` in der geänderten Zeile, nginx-Datei,
Einheit und Attrappe unter `scripts/` ohne Marker; jede Datei danach byte-gleich zurück (SHA-256 verglichen).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| 1.11.34-2 – 404 außen gleich | „anfordern“ unbekannt als 403 „fremd“ | rot |
| 1.11.34-3 – Name und Typ geprüft | nur der Typ geprüft | rot (ein unpassender Name ginge an nginx: leere Antwort mit X-Accel-Redirect bzw. 404 der Attrappe statt 500) |
| 1.11.34-4 – Name ohne Anführungszeichen, Schrägstriche, Steuerzeichen | Filter entfernt | rot |
| 1.11.34-4 – ASCII-Fassung | ASCII-Fassung = volle Fassung | rot |
| 1.11.34-4 – Cache-Control private, no-store | Kopfzeile entfernt | rot (nur „no-store“ der Schranke) |
| 1.11.34-1 – Herunterladen als attachment | inline | rot |
| 1.11.34-8 – Nummer höchstens int4 | Grenze 2^40 | rot (500 statt 422) |
| 1.11.34-9 – ein GET löscht kein Cookie | 401 mit gelöschtem Cookie | rot |
| 1.11.34-5 – HSTS im internal-Block | Zeile entfernt | rot |
| 1.11.34-5 – CSP ohne sandbox | sandbox ergänzt | rot |
| 1.11.34-5 – default_type application/octet-stream | text/html | rot |
| 1.11.34-6 – Protokoll ohne internen Weg | `$uri` in log_format | rot |
| 1.11.34-7 – Portal sieht den Ordner nicht | InaccessiblePaths entfernt | rot |
| 1.11.34-10 – Attrappe übernimmt nur, was nginx übernimmt | CSP des Dienstes übernommen | rot (zwei Tests) |

## 1.11.35: das Kind scheitert, nie der Postbote

Probendatei `gegenprobe_11135.py` (Scratchpad, mit `--trocken` vorab geprüft); unter `app/` mit Marker `GEGENPROBE` in der geänderten Zeile, die Einheit unter
`scripts/` ohne Marker; geprüft wird „failed“ (nicht „error“) und der Grund im Text; jede Datei danach byte-gleich zurück (SHA-256 verglichen).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| 1.11.35-1 – Vorrang geschrieben | `vorrang_setzen()` gibt wahr ohne zu schreiben | rot (zwei Tests) |
| 1.11.35-1 – Vorrang nachgelesen | der nachgelesene Wert zählt nicht | rot |
| 1.11.35-1 – ohne Vorrang Rückgabe 13 | Prüfung im Kind entfernt | rot (zwei Tests: das Kind ging weiter) |
| 1.11.35-1 – Vorrang vor der Grenze | Grenze zuerst gesetzt | rot (Grenze bei Wert 0) |
| 1.11.35-1 – 13 heißt „abbruch“ | 13 als „nicht_lesbar“ | rot |
| 1.11.35-2 – OOMPolicy=continue | Zeile entfernt | rot |
| 1.11.35-3 – Grenze unter MemoryHigh | Grenze wieder 1 GiB | rot |
| 1.11.35-3 – Aufruf mit dieser Grenze | Kind fest mit 1 GiB aufgerufen | rot |
| 1.11.35-4 – JPEG verkleinert dekodiert | `draft` entfernt | rot („abbruch“ mit 200 MB) |
| 1.11.35-5 – Spitze je Kind, Vorrang am laufenden Kind | -- | keine Gegenprobe möglich: `os.wait4` und `/proc` gibt es nur unter Linux; geprüft auf dem Server (P2b-4) |

## 1.11.36: Freigeben und Zurücknehmen im ERP (P2c, Teil 1)

Probendatei `gegenprobe_11136.py` (Scratchpad, mit `--trocken` vorab geprüft); unter `app/` mit Marker `GEGENPROBE` in der geänderten Zeile; geprüft wird
„failed“ (nicht „error“) und der Grund im Text; jede Datei danach byte-gleich zurück (SHA-256 verglichen). Vier Proben (Grund, alles oder nichts, Kunde im
Pfad, Archiv) waren im ersten Lauf aus dem richtigen Grund rot, nur der erwartete Text stand ohne die Klammern von pytest -- mit korrigiertem Text wiederholt.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| 1.11.36-2 – fremd wie unbekannt | eine fremde Unterlage mit eigener Meldung | rot |
| 1.11.36-2 – eine eigene, die nicht gilt: 409 mit Grund | Prüfung des Grunds entfernt | rot (200 statt 409) |
| 1.11.36-10 – Kette: Mangel verworfen | Bedingung in Python entfernt | rot (Zelle „defect_files – Quelle ungültig“: Python gegen SQL) |
| 1.11.36-10 – Kette: Projekt im Archiv | Bedingung in Python entfernt | rot (die Zellen „Projekt im Archiv“) |
| 1.11.36-3 – nur PDF und Bilder | Prüfung des Typs entfernt | rot |
| 1.11.36-3 – bis 25 MB | Prüfung der Größe entfernt | rot |
| 1.11.36-4 – Titel nie der Dateiname | Vorschlag = Dateiname | rot |
| 1.11.36-5 – alles oder nichts | eine fremde übersprungen | rot (200 statt 404) |
| 1.11.36-6 – Meldung nennt den anderen Kunden | „Schon im Portal freigegeben.“ | rot |
| 1.11.36-6 – gleichzeitig nie 500 | IntegrityError nicht gefangen | rot |
| 1.11.36-7 – Freigabe nur des Kunden im Pfad | Vergleich mit dem Kunden entfernt | rot (200 statt 404) |
| 1.11.36-8 – „erneut“ nur gescheitert | Prüfung entfernt | rot |
| 1.11.36-8 – „erneut“ weckt den Postboten | Weckruf entfernt | rot |
| 1.11.36-7 – Zurücknehmen auch im Archiv | `archiv_vorab` an der Route | rot (409 statt 200) |
| 1.11.36-1 – ab Büro – Auftrag | Mindestrolle Monteurin | rot |
| 1.11.36-1 – Modul aus 403 | Prüfung des Moduls entfernt | rot |
| 1.11.36-12 – Historie ohne die Felder der Kopie | Felder nicht mehr still | rot |
| 1.11.36-9 – Zustände | -- | durch die Proben zu 2, 8, 10 und den Wächter je Zelle mitgeprüft; keine eigene |
| 1.11.36-11 – jede Quelle auch von Hand | -- | keine eigene: dieselben Prüfungen wie oben, über `customer_documents`, `project_documents`, `service_report_photos` |
