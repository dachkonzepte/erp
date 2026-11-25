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
