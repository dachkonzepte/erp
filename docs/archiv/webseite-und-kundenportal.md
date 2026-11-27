# Webseite und Kundenportal

Verknüpfung des ERP mit der Webseite des Betriebs (www.dachkonzepte.gmbh) und ihrem Empfangsdienst, dazu das Kundenportal. Stufen W1 (Anfragen der
Webseite ins ERP) und P1–P5 (Kundenportal). Vor jeder Änderung an diesem Bereich lesen (Regel 14).

## Herkunft: Befund vom 19.11.2026

Befund auf 8821ab3 (1.9.373), Bericht `bildgrundlage/befund_webseite_portal_8821ab3.txt` (nicht in Git). Gelesen wurden die Pakete der Webseite und des
Empfangsdienstes (webseite-2026-11-18a, anfrage-2026-11-18a); sie liegen nicht im Repository. Das Wichtigste daraus, damit diese Datei ohne den Bericht trägt:

- Die Webseite schickt Anfragen an `/api/anfrage` (Reparatur, Wartung, Kantservice, Dach-Konfigurator, PV-Konfigurator, Bewerbung), Online-Termine an
  `/api/termin`, die Mitarbeiter-Anmeldung an `/api/anmeldung`. Kontakt und Kranservice haben kein Formular (Telefon, WhatsApp, E-Mail).
- Der Empfangsdienst (Python, nur Standardbibliothek, 127.0.0.1:8095, JSON-Dateien statt Datenbank, Mails über eine eigene App in Microsoft 365) hat eine
  **ERP-Schnittstelle** (Beschreibung ERP-SCHNITTSTELLE.txt im Paket, Fassung dk-anfrage/1):
  - `GET /erp/v1/anfragen` -- Kopfdaten der noch nicht übernommenen Anfragen, älteste zuerst, seitenweise (`anzahl` 1–500, `nach` = Wert aus `naechste`,
    nur innerhalb eines Durchgangs; `alle=1` auch übernommene; andere Parameter 400). Antwort `{ok, schema, anfragen[], weitere, naechste, version}`.
  - `GET /erp/v1/anfragen/<nr>` -- eine Anfrage vollständig: schema, nr, art (kantservice | dach | pv | reparatur | wartung), art_name, eingang (ISO 8601),
    zeit (Unix), quelle, kontakt {name, telefon, email, ort}, betreff, text, daten (bei Reparatur/Wartung Fassung dk-reparatur/1), positionen und aufmass
    (nur Kantservice), spamverdacht, dateien [{name, typ, bytes, sha256, pfad, breite, hoehe}], uebernommen.
  - `GET /erp/v1/anfragen/<nr>/dateien/<name>` -- anfrage.pdf, foto-N.jpg.
  - `POST /erp/v1/anfragen/<nr>/uebernommen` mit `{"erp_id": "…"}` (1–64 Zeichen, Buchstaben, Ziffern und `. _ : / -`); wiederholen erlaubt.
  - Nur auf dem Server: nginx hat keinen Weg dorthin, der Dienst lehnt jede Anfrage mit `X-Real-IP` ab. Schlüssel als `Authorization: Bearer …` aus
    `/etc/dk-anfrage-erp.key` (64 Zeichen, 640 root:dkanfrage), falscher Schlüssel = 404. Fehler: 400, 404, 413 (Body über 64 KB), 500 (wiederholen).
  - Pflichten des ERP: jede Anfrage als übernommen melden, auch verworfene (`erp_id` „verworfen“); doppelte über `nr` ausschließen; Dateien über sha256
    prüfen; Spamverdacht nur zur Prüfung; Werte aus dem Browser (Kantservice, Dach, PV) nur grob geprüft -- nie als Code, SQL oder HTML. Der Dienst löscht
    Anfragen 180 Tage nach Eingang. Bewerbungen und Mitarbeiter-Anmeldungen gibt die Schnittstelle nie heraus.
- Im ERP fehlte dafür alles: Abholen, ein Eingang, Dateien und die Nummer der Webseite an der Anfrage; `Inquiry.customer_id` ist Pflicht.
- Nebenbefunde Empfangsdienst N1–N7 und ERP E1–E4 stehen im Bericht; N1, N3 und N5 behebt der Betrieb im Projekt der Webseite (F17).

## Entscheidungen des Betriebs (19.11.2026) -- gelten für W1 und P1–P5

- **F1 Ort des Portals:** `kunde.dachkonzepte.gmbh` (Einzahl), eigener Dienst aus dem Code des ERP, in dem nur die Wege des Portals angelegt sind (Befund
  4.1 c). DNS und Zertifikat richtet der Betreiber ein.
- **F2 Zugang:** Code per Mail beim ersten Öffnen je Gerät; danach eine Sitzung, 30 Tage gleitend. Ein weitergeleiteter Link zeigt allein nichts.
- **F3 Link:** gilt 12 Monate ab dem Erzeugen; „verlängern“ per Klick im Büro; Sperren jederzeit, mit Grund; „neu erzeugen“ macht den alten ungültig.
- **F4 Empfänger:** Link und Code gehen an die E-Mail des Zugangs (beim Privatkunden die des Kunden, bei Hausverwaltungen die des Ansprechpartners); keine SMS.
- **F5 Status:** neuer Status „vom Kunden angenommen“ zwischen „versendet“ und „beauftragt“ (heute zeigt das ERP „angenommen“ für „beauftragt“,
  `app/akte.py::ANGEBOT_STATUS`).
- **F6 Annahme:** die Annahme im Portal ist der Vertragsschluss; der Klick im Büro legt nur den Auftrag an. Ein Rechtsberater bestätigt das vor P3.
- **F7 Vertragsgrundlage:** im Portal vorerst nur die Klausel wie im PDF, kein Text der VOB/B.
- **F8 Widerruf:** auch über das Portal, als Online-Erklärung mit Eingangsbestätigung per Mail und Eintrag im ERP; Post, Mail und persönlich trägt das Büro nach.
- **F9 Was der Kunde sieht:** Angebote (versendet), Auftragsbestätigung, Vertrag, Rechnungen mit Zahlstand „offen/bezahlt“, versendete Mahnungen, Abnahme,
  Mängel nur mit Status und Frist (ohne Haltung und interne Notizen), Termine nur feste Einsatztage ohne Namen der Monteure, Wartungsprotokolle ab
  Unterschrift, Fotos nur freigegeben.
- **F10 Hausverwaltungen:** Zugang je Ansprechpartner, begrenzt auf Objekte, ab P5; bis dahin ein Zugang je Kunde.
- **F11 Anfragen der Webseite:** automatisch abholen (alle 5 Minuten), Kunde und Anfrage per Klick im Büro (Dubletten, Mieter/Hausverwaltung);
  Spamverdacht nur in der Prüfliste.
- **F12 Aufbewahrung (geändert gegenüber dem Vorschlag: archivieren statt löschen):**
  - Anfragen ohne Projekt (jede Quelle, auch der Bestand) und Eingänge ohne Übernahme gehen 6 Monate nach Eingang ins Archiv: raus aus Listen und Suche,
    eigene Ansicht „Archiv“, nur lesbar, Büro und Admin, „zurückholen“ per Klick.
  - 3 Jahre nach Ende des Jahres, in dem sie ins Archiv kamen, werden die personenbezogenen Daten entfernt (Name, Kontakt, Adresse, Nachricht, Dateien,
    Umschlag). Es bleiben Art, PLZ, Monat, Quelle, Ergebnis. Kunde und Objekt nur, wenn sonst nichts daran hängt. Hängt ein versendetes Dokument daran: nur
    archivieren und im Bericht melden.
  - Beides nur nach Vorschau und Bestätigung im Büro, nie still; Eintrag in der Änderungshistorie ohne Inhalte. Gebaut in W1c.
  - **Nachtrag des Betriebs (Vorgabe W1b, 19.11.2026; umgesetzt erst in W1c):**
    - Die 6 Monate zählen ab dem **letzten Kontakt** -- letzte Nachricht, letzter Termin, letztes Angebot, gleich in welche Richtung; ohne Kontakt ab
      Eingang. So steht es in der Datenschutzerklärung.
    - Maßgeblich ist **„kein Auftrag“**, nicht „kein Projekt“ (Datenschutzerklärung: „Kommt kein Auftrag zustande …“). Das betrifft auch Projekte und
      versendete Angebote ohne Auftrag. Vor W1c dazu ein kurzer Befund mit Vorschlag, einschließlich der gesetzlichen Aufbewahrungspflichten.
    - Fällige Archivierungen und Löschungen erinnern auf „Start“, bis das Büro bestätigt.
    - Die Fotos, die eine Übernahme als Kopie ans Objekt legt (1.10.5), fallen unter dieselbe Frist wie ihre Anfrage (Antwort F2 aus W1b, 20.11.2026).
- **F13 Absender der Portal-Mails:** das Absenderpostfach des ERP (wie Angebot und Rechnung); Mails mit Link oder Code nicht unter „Gesendete Elemente“.
- **F14 IP-Adresse und Browser:** genau einmal gespeichert -- bei der Annahme, unveränderlich in der Annahme. Sonst nie; Bremsen nur gehasht.
- **F15 Unterschrift:** Name eintragen und mit Finger oder Maus zeichnen (Zeichenfläche des ERP); ohne Zeichnung keine Annahme.
- **F16 Online-Termine:** erledigt -- das Kalender-Postfach der Webseite ist im ERP dem Konto des Chefs zugeordnet, der Abgleich läuft ohne Fehler.
- **F17 Nebenbefunde Empfangsdienst:** N1 (Klartext der Termin-Links), N3 (kein Protokoll der Link-Aufrufe) und N5 (IP-Adressen, Termin-Verlauf) behebt der
  Betrieb im Projekt der Webseite.
- **Zusatz:** das Portal bekommt ab P1 einen eigenen PostgreSQL-Benutzer und einen eigenen Systembenutzer, nicht erst als Ausbau.
- **E4 Client-Adresse:** nginx setzt X-Real-IP, X-Forwarded-For (`$proxy_add_x_forwarded_for`) und X-Forwarded-Proto; gunicorn läuft mit UvicornWorker ohne
  `--forwarded-allow-ips`. In P1 am laufenden System mit einem Nur-Lese-Befehl belegen, dass `request.client.host` die echte Adresse ist.
- **Speicher (Betreiberangabe 19.11.2026):** 3,8 GiB, davon 2,3 GiB verfügbar; ERP rund 380 MB, Empfangsdienst 35 MB.

## Stufen

- **W1 Anfragen der Webseite** (ab 1.10.0): W1a Abholen und Eingang, W1b Übernehmen und Spam-Prüfliste (ab 1.10.3), W1c Archiv (F12, direkt nach W1b;
  davor ein kurzer Befund zu „kein Auftrag“ und den Aufbewahrungspflichten). Ohne Umbau der Webseite.
- **P1 Fundament des Portals:** eigener Dienst unter kunde.dachkonzepte.gmbh mit eigenem PostgreSQL- und Systembenutzer, Schranke, Zugänge je Kunde (ab
  Werk aus), Link, Code per Mail, Sitzung, Bremsen und Zugriffsprotokoll in der Datenbank, Mailweg ohne „Gesendete Elemente“, Beleg zu E4.
- **P2 Lesen**, **P3 Angebot annehmen** (nach Bestätigung von F6), **P4 Ausführung**, **P5 Hausverwaltungen**.
- W1 abgeschlossen am 23.11.2026; P1 ab 1.11.0, abgeschlossen am 26.11.2026 mit 1.11.28 und S11 (Abschnitt „P1: Fundament des Kundenportals“ unten,
  zuletzt „P1 abgeschlossen“). P2 ab 1.11.29 (Abschnitt „P2: Unterlagen im Kundenportal lesen“ ganz unten).

## W1a: Abholen und Eingang (ab 1.10.0)

### Umsetzung 1.10.0: Abholen

- `app/webanfragen.py::abholen()` -- ein Lauf: die Liste seitenweise, je neue Anfrage den Umschlag holen und prüfen, jede Datei holen, Größe, Prüfsumme
  und Typ am Inhalt prüfen, unter einem zufälligen Namen ablegen (`ERP_DATA_DIR/webanfragen/<32 hex>.pdf|jpg`), dann EINE Transaktion für den Eingang
  (`WebAnfrage` mit `WebAnfrageDatei`) und erst danach beim Empfangsdienst „übernommen“ melden (`erp_id` = `eingang-<ID>`). Eine gelistete Anfrage, die
  schon im Eingang ist, wird nur (wieder) gemeldet.
- Fremddaten wie Angriffsdaten: Verbindung nur zu einer Adresse auf diesem Server (`DK_ANFRAGE_URL`, Vorgabe `http://127.0.0.1:8095`), ohne Proxy und
  ohne Umleitung (eine Umleitung nähme den Schlüssel zum Ziel mit); Grenzen für jede Antwort; Dateiname nur aus einer festen Liste, nie als Pfad, die
  Angabe `pfad` des Umschlags nie benutzt; Typ am Inhalt (`typ_aus_inhalt()`).
- Stand des Abholens in einer Zeile (`WebanfragenAbholung`, id=1, aus `app/grunddaten.py`): Belegung eines Laufs (bedingtes UPDATE wie beim
  Outlook-Abgleich), letzter Lauf, letzter Erfolg, letzter Fehler (fester Text), Zahl neu, „nicht abgeholt“ des letzten Laufs (Nummer und fester Grund).
- Skript `scripts/webanfragen_abholen.py` für den Timer (`scripts/server/erp-webanfragen.service` und `.timer`, alle 5 Minuten, lädt `.env` wie
  `update.sh`). Ohne `DATABASE_URL` Abbruch mit 2 (kein stiller Rückfall auf SQLite, Vorfall 1); 1 bei einem Fehler des Laufs; sonst 0.
- Attrappe des Empfangsdienstes für Tests und Klicktests: `scripts/empfangsdienst_attrappe.py` (Musterdaten, Störungen auf Bestellung).
- Migration `2394d984cea8` (drei neue Tabellen; `downgrade()` bricht ab, solange der Eingang nicht leer ist).
- Kein Modul-Umschalter: ohne Schlüssel holt das ERP nichts ab („Schnittstelle nicht eingerichtet“), sonst ändert sich nichts.

#### Festlegungen 1.10.0 (bestätigt am 20.11.2026)

1. Abgeholt wird nur über die ERP-Schnittstelle des Empfangsdienstes, an eine Adresse auf diesem Server (http, 127.0.0.1, localhost oder ::1, ohne
   Benutzer, Pfad, Abfrage; Vorgabe `http://127.0.0.1:8095`), ohne Proxy und ohne Umleitung; sonst „Adresse der Schnittstelle nicht auf diesem Server“.
2. Der Schlüssel kommt nur aus `DK_ANFRAGE_SCHLUESSEL` (32–256 sichtbare ASCII-Zeichen, sonst „Schnittstelle nicht eingerichtet“) und steht nie in
   Protokoll, Fehlermeldung, Antwort, Stand oder Bericht.
3. Eine Anfrage kommt erst in den Eingang, wenn Umschlag und alle Dateien vollständig geholt und geprüft sind -- in einer Transaktion; erst danach
   „übernommen“ melden (`erp_id` „eingang-<ID>“). Scheitert das Melden, holt es der nächste Lauf nach.
4. Nie doppelt: die Nummer der Webseite ist im Eingang eindeutig; eine schon abgeholte, noch gelistete Anfrage wird nur (wieder) gemeldet.
5. Stimmt eine Datei nicht (Prüfsumme, Größe, unvollständig übertragen, Typ am Inhalt passt nicht zum Namen, fehlt beim Empfangsdienst, zu groß):
   nichts ablegen, nichts melden; Nummer und fester Grund stehen unter „nicht abgeholt“ im Stand, der nächste Lauf versucht es wieder.
6. Dateinamen nur `anfrage.pdf` und `foto-N.jpg` (N 1–99), nie als Pfad; die Angabe `pfad` des Umschlags wird nie benutzt; abgelegt unter einem
   zufälligen Namen.
7. In die Prüfliste (Eingang mit Grund): unbekannte Art (mit Dateien); unbekannte Fassung (nur der Umschlag, ohne Dateien); Angaben zu den Dateien
   ungültig oder über den Grenzen (ohne Dateien); Betreff, Name oder Name der Art zu lang oder ungültig (Spalte leer); Eingang ungültig. Der Umschlag
   bleibt unverändert gespeichert, die Spalten daneben sind nur geprüfte Auszüge.
8. Grenzen: Seite der Liste 2 MB, Umschlag 512 KB, Datei 16 MiB, 12 Dateien und 48 MiB je Anfrage, 20 000 Teile je JSON, 20 Seiten zu 100 Einträgen,
   50 neue Anfragen je Lauf, 15 Sekunden je Aufruf.
9. Antwort unlesbar oder zu groß, abgelehnt (404: „Schlüssel prüfen“), anderer Status, nicht erreichbar, Umleitung: der Lauf endet mit einem festen
   Text im Stand; was bis dahin vollständig war, bleibt; nichts halb angelegt.
10. Ein Lauf zur Zeit: bedingtes UPDATE auf der Zeile des Stands; eine Belegung gilt 10 Minuten, danach gilt sie als liegen geblieben.
11. Spamverdacht kommt mit Kennzeichen in den Eingang (verworfen wird erst in W1b, per Klick).
12. Timer alle 5 Minuten (F11); das Skript bricht ohne `DATABASE_URL` mit 2 ab, gibt 1 bei einem Fehler des Laufs, sonst 0.
13. Kein Modul-Umschalter -- ohne Schlüssel holt das ERP nichts ab.
14. `downgrade()` der Migration bricht ab, solange der Eingang nicht leer ist.

#### Tests und Prüfung 1.10.0

Neu `tests/test_v772_webanfragen_abholen.py` gegen die Attrappe: Ablauf und Melden, nie doppelt, Datei stimmt nicht (vier Fälle), zu groß gelesen und
angekündigt, Dateiname nie als Pfad, `pfad` nie benutzt, unbekannte Art, unbekannte Fassung, ungültige Angaben (fünf Fälle), zu langer Name, Spamverdacht,
ungültige Nummer nie angefragt, Liste unlesbar (fünf Fälle) und zu groß, Umschlag unlesbar und mit anderer Nummer, Umleitung nie gefolgt (ein zweiter
Dienst hört mit), Abbruch mitten in einer Datei, Empfangsdienst aus, falscher Schlüssel, Schlüssel nie in Stand, Ergebnis, Protokoll, Adresse nur auf
diesem Server (sieben Fälle), ungültiger Schlüssel, Sperre, Melden nachgeholt, höchstens je Lauf und Seiten, Frist, Skript ohne `DATABASE_URL` und als
Kindprozess gegen eine Wegwerf-SQLite, PostgreSQL im Wegwerf-Schema (Lauf, Sperre über zwei Sitzungen, eindeutige Nummer), Downgrade; dazu Proxy der
Umgebung nie benutzt und die Lesegrenzen ohne Längenangabe (beide aus den Gegenproben). Gegenproben: `gegenproben-webseite.md`, „W1a, 1.10.0“.
Aufbau geändert (Regel 28): `tests/test_v364_feste_werte_spaltenlaenge.py` kennt `webanfragen.status`; keine angepasste Erwartung.

### Server-Schritte W1a (zum Abarbeiten, in dieser Reihenfolge)

1. Schlüssel in die `.env` übernehmen, ohne ihn anzuzeigen (als Benutzer des ERP, nur `cat` mit sudo):

       sudo cat /etc/dk-anfrage-erp.key | { IFS= read -r k; f=/home/tobias/erp/.env; sed -i '/^DK_ANFRAGE_SCHLUESSEL=/d' "$f"; printf 'DK_ANFRAGE_SCHLUESSEL=%s\n' "$k" >> "$f"; unset k; }

   Prüfen, ohne ihn zu zeigen (erwartet: `1` und `64`):

       grep -c '^DK_ANFRAGE_SCHLUESSEL=' /home/tobias/erp/.env
       awk -F= '/^DK_ANFRAGE_SCHLUESSEL=/{print length($2)}' /home/tobias/erp/.env

2. Einspielen wie immer: `/home/tobias/update.sh` (Migration `2394d984cea8`, Neustart -- danach kennt das ERP den Schlüssel).
3. Benutzer des ERP-Dienstes prüfen (die Timer-Einheit läuft als `tobias`): `systemctl show -p User erp` -- weicht er ab, `User=`/`Group=` in
   `scripts/server/erp-webanfragen.service` vor dem Kopieren anpassen.
4. Timer einrichten:

       sudo cp /home/tobias/erp/scripts/server/erp-webanfragen.service /home/tobias/erp/scripts/server/erp-webanfragen.timer /etc/systemd/system/
       sudo systemctl daemon-reload
       sudo systemctl enable --now erp-webanfragen.timer

5. Ersten Lauf von Hand anstoßen und ansehen: `sudo systemctl start erp-webanfragen.service`, dann `journalctl -u erp-webanfragen -n 20`
   (erwartet: „Anfragen der Webseite: n neu, …“; Rückgabe 0). `systemctl list-timers erp-webanfragen.timer` zeigt den nächsten Lauf.

### Umsetzung 1.10.1: Eingang

- Seite „Anfragen der Webseite“ (`/anfragen/webseite`, `webanfragen.html`): Stand des Abholens, Knopf „Jetzt abholen“, Liste des Eingangs; eine Anfrage auf
  `/anfragen/webseite/<ID>` (`webanfrage.html`). Beide im Rahmen gebaut (Seitenkopf mit Pfad über das Makro, Bereich „Anfragen“ der Leiste, kein eigener
  Eintrag), der Weg dorthin über einen neutralen Knopf im Kopf der Seite „Anfragen“.
- Router `app/routers/webanfragen.py`: `GET /api/webanfragen` (Liste), `/stand`, `/{id}` (mit Umschlag), `/{id}/dateien/{datei_id}`, `POST /abholen`;
  Büro ab Büro – Auftrag. Antwortschemas `WebAnfrageOut`, `WebAnfrageDetailOut`, `WebanfragenStandOut`, `WebanfragenAbholErgebnisOut`.
- Bildgrundlage: beide Seiten in `AUFNAHMEN` (Büro), eine Musteranfrage ohne Dateien im Seed.

#### Festlegungen 1.10.1 (bestätigt am 20.11.2026)

1. Der Eingang ist eine eigene Seite „Anfragen der Webseite“ unter „Anfragen“ (Bereich der Leiste „Anfragen“, kein eigener Eintrag); der Weg dorthin ist ein
   neutraler Knopf im Kopf von „Anfragen“, eine Anfrage hat ihre eigene Seite.
2. Lesen und Abholen darf das Büro ab Büro – Auftrag (wie die Anfragen); die Monteurin an keinem Weg.
3. „Jetzt abholen“ holt höchstens 20 neue Anfragen und nach 40 Sekunden keine neue mehr (die Seite wartet höchstens 60 Sekunden); den Rest holt der Timer.
   Das Ergebnis steht in Worten unter dem Stand.
4. Die Liste zeigt die neuesten 500, nach Eingang absteigend, ohne Eingang am Ende; Kennzeichen „Spamverdacht“, „Prüfen: <Grund>“, „noch nicht gemeldet“.
   Die Antwort der Liste enthält nur die geprüften Auszüge, nie den Umschlag.
5. Eine Anfrage zeigt Kontakt, Anfrage (Art, Eingang, Betreff, Nachricht), die Angaben aus dem Formular (Reparatur und Wartung nach dk-reparatur/1 mit
   Klartext, sonst verschachtelt mit Grenzen in Tiefe und Menge, bei Dach und PV mit dem Hinweis „Preise und Förderung … vor dem Angebot prüfen“), die
   Dateien (PDF als Link, Fotos als Vorschau) und die Herkunft.
6. Jeder Wert aus dem Umschlag -- auch jeder Schlüssel -- geht nur über esc() ins HTML; Links nur `tel:` (nur Ziffern und +), `mailto:` (nur mit @ und
   ohne Leerraum, sonst Text) und der eigene Pfad der Dateien.
7. Eine Datei gibt es nur zu ihrer Anfrage (sonst 404 wie unbekannt) und nur über `datei_antwort()`; fehlt sie oder ist ihr Ablagename nicht einer, den das
   Abholen vergibt: 404.
8. Der Stand nennt: im Eingang, davon Spamverdacht und zu prüfen, zuletzt abgeholt, zuletzt ohne Fehler, den Fehler des letzten Laufs und was nicht abgeholt
   wurde (Nummer und Grund); ohne Schlüssel „noch nicht eingerichtet – ein Administrator trägt den Schlüssel ein“. Nie Schlüssel oder Adresse.
9. Unter 650 px steht jede Anfrage der Liste als Block, jede Angabe mit ihrer Überschrift.

#### Tests und Prüfung 1.10.1

Neu `tests/test_v773_webanfragen_eingang.py` (14 Tests: Monteurin nirgends, Liste neueste zuerst ohne Umschlag, Anfrage mit Umschlag und Dateien, Datei nur
dieser Anfrage, Datei fehlt und Ablagename mit ../, Weg über „Anfragen“ und die Seiten, Stand ohne Schlüssel, Knopf gegen die Attrappe und mit seinen Grenzen,
in node: Anfrage und Liste mit HTML in Werten und Schlüsseln, allgemeine Angaben und Dateien, Hinweis ohne Schlüssel, Ergebnis in Worten). Neuer Klicktest
`scripts/klicktest_webanfragen.py` (29 Prüfungen, Attrappe im Klicktest, Bilder Eingang und Anfrage bei 1440 px hell und dunkel und bei 412 px hell).
Angepasste Erwartungen (Regel 28): `tests/test_v441_rahmen_baustein.py` -- Seiten mit Leiste alt 43, neu 45 (zweimal); `tests/test_v431_bildgrundlage.py` --
Bilder je Lauf alt 306, neu 314, davon in 412/1440 alt 244, neu 252. Aufbau geändert: `UMGEZOGEN` um die beiden Seiten, Testwerte `webanfrage_id`/`datei_id`
(`tests/test_v326_monteur_datengrenze.py`) und `webanfrage` (`test_v441`), Auslieferungsstelle `app/routers/webanfragen.py` (`tests/test_v406_dateien_nie_aktiv.py`),
das ID-Paar Anfrage/Datei in `GEPRUEFT` (`tests/test_v373_zugehoerigkeit_struktur.py`, Regel 25). Die Musteranfrage der Bildgrundlage nimmt Eingang und Nummer
von der stehenden Uhr (im ersten vollen Lauf rot: `tests/test_v453_bildgrundlage_lauftag.py` fand ein festes Datum im Umschlag).
Gegenproben: `gegenproben-webseite.md`, „W1a, 1.10.1“.

### Umsetzung 1.10.2: Hinweis auf der Startseite

Vorgabe: „Neue Einträge fallen dem Büro auf ‚Heute‘ auf (Ort schlägst du nach Bestand vor).“ „Heute“ ist im ERP die Seite der Monteurin (`/mobil`); das Büro
beginnt auf „Start“ (Dashboard mit Widgets). Deshalb ein Standard-Widget „Anfragen der Webseite“ dort, direkt unter „Meine Aufgaben“ (`app/dashboard.py`,
`DEFAULT_WIDGETS`, `dashboard.html::renderWebanfragenWidget()`), Daten aus `GET /api/webanfragen/stand` und `GET /api/webanfragen?anzahl=5`.

#### Festlegungen 1.10.2 (bestätigt am 20.11.2026)

1. Neue Anfragen der Webseite fallen dem Büro auf der Startseite „Start“ auf (nicht auf „Heute“, das ist die Seite der Monteurin): Standard-Widget „Anfragen der
   Webseite“ direkt unter „Meine Aufgaben“ (sort_order 12). Wie seit 1.8.18 erreicht ein neues Standard-Widget auch gespeicherte Layouts; wer es entfernt,
   behält es entfernt.
2. Das Widget zeigt die Zahl im Eingang (davon Spamverdacht, zu prüfen) als Weg zum Eingang, die fünf neuesten (Art, Name oder Nummer, Nummer, Kennzeichen,
   Tag des Eingangs) als Weg zur Anfrage, den Fehler des letzten Laufs und ohne Schlüssel „noch nicht eingerichtet“; leer „Keine Anfragen der Webseite im
   Eingang.“ Jeder Wert über esc().
3. Nur für Büro und Admin; für jede andere Rolle zeigt es den Hinweis und fragt nichts ab.
4. Die Liste nimmt `anzahl` (1–500, Vorgabe 500).

#### Tests und Prüfung 1.10.2

Neu `tests/test_v774_webanfragen_start.py` (5 Tests: Standard unter „Meine Aufgaben“, gespeichertes Layout bekommt es, entfernt bleibt entfernt; Liste mit
`anzahl` und Grenzen; Widget in node mit Zahl, den neuesten und HTML in Werten; leer, ohne Schlüssel, mit Fehler; nur Büro). Klicktest
`scripts/klicktest_webanfragen.py` um die Startseite ergänzt (35 Prüfungen, Bild der Startseite bei 1440 px hell). Angepasste Erwartungen (Regel 28) -- jede
Reihenfolge der Widgets bekommt „webanfragen“ an zweiter Stelle bzw. nach dem Widget mit sort_order 10:
`tests/test_v197_dashboard.py` (vier Stellen: Standard alt `my_tasks, open_office_tasks, kpis, active_projects`, neu `my_tasks, webanfragen, open_office_tasks,
kpis, active_projects`; gespeichert alt `kpis, open_office_tasks, my_tasks, active_projects`, neu `kpis, webanfragen, open_office_tasks, my_tasks,
active_projects`, zweimal; unberührt wie Standard), `tests/test_v322_unassigned_tasks.py` (zwei Stellen, wie Standard), `scripts/klicktest_aufgaben_ohne_zustaendigkeit.py`
(Titel der Widgets alt „Meine Aufgaben, Ohne Zuständigkeit, Kennzahlen, Laufende Projekte“, neu mit „Anfragen der Webseite“ an zweiter Stelle). Aufbau
geändert: `anzahl` in `KEINE_ID` (`tests/test_v761_ids_im_pfad.py`). Gegenproben: `gegenproben-webseite.md`, „W1a, 1.10.2“.

## W1b: Übernehmen und Spam-Prüfliste (ab 1.10.3)

Vorgabe des Betriebs (19.11.2026, nach dem Livegang von 1.10.2 -- acht echte Anfragen abgeholt und gemeldet, zweiter Lauf 0 neu): Übernehmen und
Spam-Prüfliste wie im Befund 3.2 („als Anfrage übernehmen“ mit Kundenvorschlag, Nummer der Webseite an der Anfrage, Dateien an Anfrage bzw. Objekt,
verwerfen, Meldungen nach F2). Antworten auf die Fragen aus W1a: F1 ja (Hinweis auf „Start“), F2 ja (nach der Übernahme noch einmal melden, mit der
Anfragenummer; beim Verwerfen „verworfen“), F3 ja (W1c direkt nach W1b). Dazu Funde aus echten Anfragen:

1. **Adresse**: bei Reparatur steht die volle Adresse nur unter „Angaben aus dem Formular → Objekt“; „Kontakt“ zeigt nur PLZ und Ort, die Liste nur den
   Betreff (Straße und Bereich, ohne Ort). Die Adresse des Objekts (Straße, PLZ, Ort) gehört oben auf die Seite und in die Liste -- nur aus den
   strukturierten Angaben, nie aus Betreff oder Nachricht. Je Art am Code des Empfangsdienstes prüfen, welche Adressfelder es gibt; Arten ohne Straße melden.
2. **Fremder Abschnitt**: eine Reparatur zeigte „Positionen aus dem Kantteil-Zeichner — Aufmaß vor Ort gewünscht: nein“. Abschnitte einer Art nur bei dieser
   Art und nur mit Inhalt; alle fünf Arten prüfen.
3. **Zeit**: die Musteranfrage …-0910-… mit Eingang 10:10, eine echte …-0705-… mit Eingang 07:05. Am Code prüfen, in welcher Zeitzone Nummer und Eingang
   stehen; Anzeige immer Europe/Berlin; die Attrappe bildet Aufbau und Zeitformat des echten Dienstes nach.
4. **Nachricht**: wiederholt sie nur die strukturierten Angaben (Reparatur, Wartung), eingeklappt zeigen; sonst offen.
5. **Kunde und Objekt** beim Übernehmen nur aus den strukturierten Feldern; meldet ein Mieter, ist die Hausverwaltung Auftraggeber (Vorschlag aus dem
   Pflichtfeld), der Mieter Ansprechpartner vor Ort. Nichts blind anlegen, das Büro bestätigt jede Zuordnung.
6. **Nachtrag zu F12** (siehe dort; umgesetzt in W1c).

Runden: 1.10.3 Anzeige nach den Funden 1–4 (dazu der Nachtrag zu F12), 1.10.4 Prüfliste und Verwerfen, 1.10.5 Übernehmen als Anfrage (Fund 5).

### Befund am Code des Empfangsdienstes (Funde 1–3)

Gelesen: `anfrage.py` (`_pruefe()`, `_pruefe_reparatur()`, `neue_nr()`, `zeit_iso()`, `umschlag()`, `erp_liste()`), `reparatur.py`, `dk-anfrage.service`
und die Formulare der Webseite (`konfigurator-dach.js`, `konfigurator-pv.js`, `kantservice.js`). Nur gelesen, keine Zugangsdaten.

**Adressfelder je Art (Fund 1)**

| Art | Adresse des Objekts | Prüfung beim Dienst | `kontakt.ort` |
|---|---|---|---|
| reparatur, wartung | `daten.objekt.strasse`, `plz`, `ort` (dk-reparatur/1) | Feld für Feld: Straße Pflicht (100), PLZ fünf Ziffern, Ort Pflicht (60) | abgeleitet „PLZ Ort“ des Objekts |
| dach | `daten.strasse`, `plz`, `ort` (Konfigurator, version 1) | nur grob (Browser: Straße 60, PLZ 10, Ort 40 Zeichen) -- **freiwillig** | abgeleitet „Straße, PLZ Ort“ |
| pv | `daten.strasse`, `plz`, `ort` (Konfigurator, **version 2** -- die Beschreibung der Schnittstelle nennt 1) | wie Dach -- **freiwillig** | wie Dach |
| kantservice | **keine** -- kein Objekt, nur ein freies Feld „Ort“ (Beispiel der Webseite „52511 Geilenkirchen“) | Text, höchstens 100 | das freie Feld |

**Arten ohne Straße:** Kantservice immer; Dach und PV, wenn der Kunde die freiwilligen Felder leer lässt. Reparatur und Wartung haben sie immer.

**Abschnitte (Fund 2):** `umschlag()` schreibt `positionen` (`a.get('positionen') or []`) und `aufmass` (`bool(a.get('aufmass'))`) bei **jeder** Art --
außer beim Kantservice also `[]` und `false`. Die Seite zeigte den Abschnitt des Kantservice, sobald die Felder da waren. Kantservice hat keine `daten`;
Dach und PV keine Dateien (der Dienst lehnt dort ein PDF ab); nur Reparatur und Wartung haben Fotos.

**Zeit (Fund 3):** der Dienst läuft mit `TZ=Europe/Berlin` (`dk-anfrage.service`, auch die Wartung und `einrichten.sh`). Die Nummer bildet `neue_nr()` mit
`time.strftime('%Y%m%d-%H%M')` -- Ortszeit Berlin; `eingang` ist `zeit_iso(zeit)` -- Ortszeit Berlin mit Versatz (`2026-11-10T09:13:27+01:00`), `zeit` die
Unix-Zeit. Das ERP liest den Eingang seit 1.10.0 aus `zeit` (naives UTC) und zeigt ihn über `berlinZeitpunkt()` -- richtig, deshalb zeigt die echte Anfrage
…-0705-… 07:05. Falsch war die Attrappe: sie bildete den Eingang in UTC (09:10 UTC zur Nummer …-0910-…, angezeigt 10:10 Berlin).

### Umsetzung 1.10.3: Anzeige nach den Funden

- `app/webanfrage_angaben.py` (neu): Angaben je Art nur aus den strukturierten Feldern -- `objekt_adresse()`, `abschnitte()`, `nachricht_wiederholt()`
  (baut die Nachricht wie `reparatur.py::text()` des Dienstes nach und vergleicht), `einzeilig()` für jeden Wert.
- Spalten `webanfragen.objekt_strasse`, `objekt_plz`, `objekt_ort` (Migration `994be7557612`, der Bestand aus seinem Umschlag; `downgrade()` nimmt sie weg),
  gefüllt beim Abholen. Liste, Anfrage und das Widget auf „Start“ zeigen sie.
- Anfrage: oben „Objekt: Straße, PLZ Ort · Eingang …“ (Kantservice „ohne Objekt-Adresse“), Zeile „Objekt“ in der Karte „Anfrage“; „Ort“ im Kontakt nur, wo
  er nicht aus dem Objekt abgeleitet ist; Abschnitte nach `abschnitte` vom Server; die Nachricht eingeklappt nach `nachricht_wiederholt`.
- Attrappe (`scripts/empfangsdienst_attrappe.py`) wie der echte Dienst: Nummer und Eingang in Berlin, Liste mit allen Kopfdaten nach Minute und Nummer, je Art
  die echten Felder, Vermerk `{zeit, erp_id}`; `meldungen` hält jedes „übernommen“ in Reihenfolge (für W1b).

#### Festlegungen 1.10.3 (bestätigt am 20.11.2026)

1. Die Adresse des Objekts kommt nur aus den strukturierten Angaben: Reparatur und Wartung aus `daten.objekt` (dk-reparatur/1), Dach und PV aus
   `daten.strasse/plz/ort`; Kantservice hat keine. Nie aus Betreff, Nachricht oder dem abgeleiteten `kontakt.ort`.
2. Ein Wert gilt nur als Text ohne Steuerzeichen, Leerraum zusammengefasst und innerhalb der Grenzen (Straße 100, PLZ 10, Ort 60 Zeichen); sonst bleibt die
   Angabe leer, nie ein Fehler. Eine andere Fassung als dk-reparatur/1 liefert keine Adresse.
3. Die Adresse steht in eigenen Spalten am Eingang, gefüllt beim Abholen; der Bestand bekommt sie über die Migration aus seinem Umschlag; `downgrade()` nimmt
   die Spalten weg (aus dem Umschlag jederzeit neu ableitbar).
4. Die Adresse steht oben auf der Anfrage („Objekt: Straße, PLZ Ort · Eingang …“, ohne Adresse „Kantservice – ohne Objekt-Adresse“ bzw. „ohne
   Objekt-Adresse“), als Zeile „Objekt“ in der Karte „Anfrage“, als Spalte „Objekt“ der Liste und im Widget auf „Start“ -- jeder Wert über esc().
5. „Ort“ im Kontakt nur beim Kantservice (und einer unbekannten Art); bei Reparatur, Wartung, Dach und PV ist er aus der Adresse des Objekts abgeleitet und
   steht oben.
6. Unter „Angaben aus dem Formular“ nur die Abschnitte der Art und nur mit Inhalt (vom Server, `abschnitte`): Reparatur und Wartung nach dk-reparatur/1;
   „Konfigurator“ nur bei Dach und PV mit Angaben (mit dem Hinweis „Preise prüfen“); „Kantservice“ nur beim Kantservice mit Positionen oder gewünschtem
   Aufmaß; „weitere“ (verschachtelt) bei einer unbekannten Fassung oder Art.
7. Die Nachricht steht eingeklappt („Wiederholt nur die Angaben aus dem Formular – anzeigen“), wenn sie bei Reparatur oder Wartung genau der Nachricht gleicht,
   die das ERP aus den Angaben wie der Empfangsdienst baut (nur Zeilenenden und Leerraum am Zeilenende dürfen abweichen); jede andere offen.
8. Zeit: Nummer und Eingang stehen beim Empfangsdienst in Europe/Berlin; das ERP liest den Eingang aus der Unix-Zeit (`zeit`, naives UTC) und zeigt ihn in
   Berlin -- er gleicht der Minute der Nummer, auch in der Sommerzeit. Am ERP nichts geändert.
9. Die Attrappe bildet Aufbau und Zeitformat des echten Dienstes nach: Nummer und Eingang in Berlin (ISO 8601 mit Versatz, ohne Bruchteile), Liste mit
   allen Kopfdaten nach Minute und Nummer, `positionen`/`aufmass` bei jeder Art, Dach und PV ohne Dateien, Kantservice ohne `daten`, PV `daten` version 2,
   Vermerk `{zeit, erp_id}`.

#### Tests und Prüfung 1.10.3

Neu `tests/test_v775_webanfragen_anzeige.py` (17 Tests: Adresse je Art, nie aus Betreff oder Nachricht, nur gültige Fremddaten, Abholen füllt die Spalten;
Abschnitte je Art und mit Inhalt, Antwort der Anfrage je Art; Nachricht wiederholt (drei Rollen, eigener Text, Nachtrag, Zeilenenden, unpassende Angaben);
Eingang gleich der Minute der Nummer im Winter und im Sommer; Liste der Attrappe; in node: Adresse oben und „Ort“ nur beim Kantservice, Abschnitte je Art,
Nachricht eingeklappt, Spalte „Objekt“, Widget auf „Start“; Migration auf einem Bestand unter SQLite und PostgreSQL mit Downgrade). Klicktest
`scripts/klicktest_webanfragen.py` um Adresse, Kantservice, Abschnitte und Nachricht erweitert (45 Prüfungen).

Angepasste Erwartungen (Regel 28):
- `tests/test_v772_webanfragen_abholen.py::test_abholen_legt_an_und_meldet` -- `eingang_am` alt 09:10 UTC, neu 08:10:27 UTC (= 09:10:27 Berlin, die Minute der
  Nummer; die Attrappe bildete den Eingang bisher in UTC).
- `tests/test_v773_webanfragen_eingang.py::test_detail_allgemeine_angaben_und_dateien` -- alt: eine Dach-Anfrage zeigt Positionen und Aufmaß des Kantservice;
  neu: nicht (Fund 2), dazu eine Kantservice-Anfrage mit beidem. Aufbau geändert: der Helfer `_detail()` setzt `abschnitte` und `nachricht_wiederholt` aus
  denselben Funktionen wie der Server (die Seite zeichnet die Abschnitte nur noch danach).
- `scripts/klicktest_webanfragen.py` -- „Liste: Eingang in Berliner Zeit“ alt „19.11.2026 10:10“ (eine Zeile), neu je Zeile 09:12, 09:11, 09:10 (= Minute der
  Nummer); „Liste: Dateien“ jetzt Spalte 8 statt 7 (neue Spalte „Objekt“).
- Kommentar in `test_v772::test_ausfall_mitten_in_einer_datei`: R1 steht jetzt vor K1 (Minute 09:10 vor 09:12); das Ergebnis des Tests ist gleich.
- `scripts/bildgrundlage.py`: die Musteranfrage nimmt ihre Nummer aus dem Eingang in Berlin (bis 1.10.2 eine feste Minute) und trägt die Adresse.

Gegenproben: `gegenproben-webseite.md`, „W1b, 1.10.3“ (31, alle rot).

### Umsetzung 1.10.4: Prüfliste und Verwerfen

- Ansichten des Eingangs (`GET /api/webanfragen?ansicht=eingang|pruefliste|erledigt`, Reiter auf der Seite, Anker `#eingang`, `#pruefliste`, `#erledigt`): die
  **Prüfliste** sind Anfragen mit Spamverdacht oder einem Grund zum Prüfen, solange sie neu sind und das Büro sie nicht in den Eingang gegeben hat
  (`app/webanfragen.py::IN_PRUEFLISTE`, `in_pruefliste()`); der **Eingang** die übrigen neuen; **Erledigt** die verworfenen (1.10.5: übernommenen), zuletzt
  erledigt zuerst. Das Widget auf „Start“ zählt und zeigt nur den Eingang und nennt die Prüfliste mit Weg dorthin.
- Aktionen (`POST /api/webanfragen/{id}/verwerfen | eingang | zurueckholen`, Büro ab Büro – Auftrag): je ein bedingtes UPDATE (`_aendern()`) -- nie zweimal,
  sonst 409; ein Eintrag in der Änderungshistorie (Art „Anfrage der Webseite“, Nummer, Status alt und neu) ohne Inhalte. Verwerfen nur mit festem Grund
  (`VERWERFEN_GRUENDE`: Spam, Doppelt, Test, Sonstiges; `WebAnfrageVerwerfenIn`), auf der Seite über `abschliessen()`.
- Meldung an den Empfangsdienst (F2): `melden_soll` ist, was er bekommen soll („verworfen“; nach dem Zurückholen wieder eingang-<ID>; leer = eingang-<ID>),
  `gemeldet_als` was er bestätigt hat. Gemeldet wird nur unter der Sperre des Abholens: direkt nach der Aktion (`nachmelden()`, 5 Sekunden), wenn gerade
  kein Lauf abholt; sonst und nach einem Fehler im nächsten Lauf (`_offene_melden()` nach der Liste, mit dem Stand von jetzt -- die Anfrage steht dort nicht
  mehr in der Liste). Der Lauf meldet auch eine noch gelistete Anfrage mit ihrem `melden_soll`.
- Neue Spalten (Migration `a107b86d8e8d`): `geprueft_am`, `geprueft_von_user_id`, `erledigt_am`, `erledigt_von_user_id`, `verworfen_grund`, `melden_soll`,
  `gemeldet_als` (der Bestand: gemeldete bekommen eingang-<ID>); `downgrade()` bricht ab, solange etwas erledigt ist. Die beiden Konten-Spalten stehen in
  `app/konto_loeschen.py::BEREICHE` („Anfragen der Webseite“).
- Statuskennzeichen „webanfrage“ (Neu, Prüfliste, Verworfen) in `_statuskennzeichen.html`.

#### Festlegungen 1.10.4 (bestätigt am 20.11.2026)

1. In die Prüfliste kommt eine Anfrage mit Spamverdacht oder einem Grund zum Prüfen (Festlegung 1.10.0 Nr. 7), solange sie neu ist und das Büro sie nicht
   in den Eingang gegeben hat; der Eingang und das Widget auf „Start“ zeigen sie nicht, „Start“ nennt die Zahl in der Prüfliste mit Weg dorthin.
2. „Kein Spam – in den Eingang“ geht nur aus der Prüfliste; danach steht die Anfrage im Eingang (mit „aus der Prüfliste gegeben am … von …“).
3. Verwerfen geht bei jeder neuen Anfrage (Eingang und Prüfliste), nur mit einem festen Grund (Spam, Doppelt, Test, Sonstiges) -- kein freier Text; auf der
   Seite als abschließende Aktion.
4. „Zurück in den Eingang“ geht nur bei einer verworfenen Anfrage; sie steht danach wieder, wo sie vorher war (mit Spamverdacht in der Prüfliste).
5. Jede Aktion ist ein bedingtes UPDATE: zweimal oder aus einem anderen Stand geht nicht (409 „nicht mehr in diesem Stand – bitte neu laden“), eine
   unbekannte Anfrage 404.
6. Jede Aktion steht in der Änderungshistorie (Art „Anfrage der Webseite“, Kennung, Nummer, Status alt und neu, beim Verwerfen mit dem Grund) -- ohne Inhalte
   aus dem Formular.
7. Nach dem Verwerfen bekommt der Empfangsdienst „verworfen“, nach dem Zurückholen wieder eingang-<ID> (F2). Gemeldet wird nur unter der Sperre des
   Abholens: direkt nach der Aktion (höchstens 5 Sekunden), wenn kein Lauf abholt; sonst und nach einem Fehler meldet der nächste Lauf -- auch eine Anfrage,
   die beim Empfangsdienst nicht mehr gelistet ist, und eine gelistete mit ihrem Stand von jetzt.
8. Die Seite zeigt, was gemeldet ist („Beim Empfangsdienst gemeldet als …“) oder dass die Meldung aussteht; Liste und Stand nennen offene Meldungen.
9. Erledigt zeigt verworfene Anfragen mit Grund, zuletzt erledigt zuerst; nichts wird gelöscht (Archiv und Löschen erst in W1c).
10. Lesen und Aktionen nur das Büro ab Büro – Auftrag; die Monteurin an keinem Weg.

#### Tests und Prüfung 1.10.4

Neu `tests/test_v776_webanfragen_pruefliste.py` (18 Tests: Prüfliste getrennt vom Eingang, auch mit einem Grund zum Prüfen; In den Eingang nur aus der
Prüfliste; Verwerfen meldet „verworfen“, zweimal 409, freier Grund 422, unbekannt 404; Historie ohne Inhalte; Zurückholen meldet wieder eingang-<ID>, steht
wieder, wo sie war, Erledigt zuletzt zuerst, nichts gelöscht; ohne Empfangsdienst meldet der nächste Lauf, während eines Laufs meldet der Lauf, eine noch
gelistete mit dem Stand von jetzt; Monteurin nirgends; Gründe fest und gleich; in node Knöpfe je Stand, Gründe über esc(), Reiter und Kennzeichen, „Start“
nennt die Prüfliste; Migration auf einem Bestand unter SQLite und PostgreSQL). Klicktest `scripts/klicktest_webanfragen.py` um Prüfliste, Verwerfen,
Erledigt, Zurückholen und In den Eingang erweitert (60 Prüfungen; dabei gefunden und behoben: das Feld „Grund“ stand vor dem Klick offen, weil
`display:flex` der Klasse das Attribut `hidden` überstimmte -- jetzt `.verwerfen-panel[hidden]{display:none}` und eine Prüfung der berechneten Anzeige). Die volle Suite fand außerdem: die Aktion der Historie stand als Variable in einem gemeinsamen Helfer -- `tests/test_v732_lohndatei_vermerk_postgresql.py` verlangt je Aufruf einen festen Text (Länge der Spalte); jetzt schreibt jede Aktion ihren Eintrag selbst.

Angepasste Erwartungen (Regel 28) -- „im Eingang“ zählt seit 1.10.4 ohne die Prüfliste:
- `tests/test_v773_webanfragen_eingang.py::test_liste_neueste_zuerst_ohne_umschlag` -- alt: die Liste enthält Spamverdacht, normal, „zu prüfen“; neu: der
  Eingang nur die normale, die Prüfliste die beiden anderen (ohne Eingang am Ende).
- `test_v773::test_stand_ohne_schluessel` -- alt `neu` 3; neu `neu` 1, `pruefliste` 2.
- `test_v773::test_knopf_holt_mit_grenze_und_ohne_schluessel_in_der_antwort` -- alt Stand `neu` 5; neu `neu` 3, `pruefliste` 2.
- `test_v773::test_liste_setzt_jeden_wert_ueber_esc` -- alt Kennzeichen „noch nicht gemeldet“ (aus `gemeldet_am`); neu „Meldung steht aus“ (aus `meldung_offen`).
- `test_v773::test_ergebnis_des_knopfs_in_worten` -- alt „davon 1 zu prüfen“; neu „davon 1 in der Prüfliste“.
- `tests/test_v774_webanfragen_start.py::test_widget_zeigt_zahl_und_die_neuesten` -- alt „2 im Eingang · davon 1 mit Spamverdacht · 1 zu prüfen“; neu „2 im
  Eingang · 3 in der Prüfliste“ (mit Weg `#pruefliste`).
- `scripts/klicktest_webanfragen.py` -- die Wartung mit Spamverdacht steht in der Prüfliste: „Liste: neueste zuerst“ alt W, K, R, neu K, R; „Eingang in
  Berliner Zeit“, „Adresse des Objekts“ und „Dateien“ je ohne die Wartung; „Stand: 3 im Eingang“ jetzt „2 im Eingang, 1 in der Prüfliste“; „Start: Zahl im
  Eingang“ alt 3, neu 2; „Start: die neuesten“ alt drei, neu zwei; die Prüfungen „Spamverdacht“ und „Name mit HTML“ jetzt in der Prüfliste.
- Aufbau geändert: `ABSCHLIESSEND` um `webanfrage.html::webanfrageVerwerfen` (`tests/test_v399_abschliessen.py`); `tests/test_v445_statuskennzeichen.py`
  prüft auch die Gruppe „webanfrage“ gegen `app/webanfragen.py::STATUS`.

Gegenproben: `gegenproben-webseite.md`, „W1b, 1.10.4“ (27, alle rot).

### Umsetzung 1.10.5: Als Anfrage übernehmen

- `app/webanfrage_uebernahme.py` (neu): `angaben()` liest nur die strukturierten Felder (Melder, Firma, Hausverwaltung, Telefon, E-Mail, Objekt, vor Ort; beim
  Kantservice, Dach und PV der Kontakt), `vorschlag()` (`GET /api/webanfragen/{id}/vorschlag`, schreibt nichts): wer Auftraggeber wird, bestehende Kunden mit
  Gründen, ein neuer Kunde und ein neues Objekt zum Ausfüllen, Ansprechpartner vor Ort, Betreff und Beschreibung der Anfrage; `objekte()`
  (`GET …/objekte?kunde_id=`): die Objekte des gewählten Kunden mit „Adresse gleich“; `uebernehmen()` (`POST …/uebernehmen`, `WebAnfrageUebernehmenIn`).
- Ein Kunde entsteht nur noch über `app/crm.py::kunde_anlegen()` -- dieselbe Stelle für `POST /api/customers` und die Übernahme (Name, Profil mit
  Kundennummer, Hauptadresse als erstes Objekt). `create_property_document(commit=False)` legt die Fotos in der Transaktion der Übernahme ab.
- `inquiries.webseite_nummer` (eindeutig) und `webanfragen.inquiry_id` (eindeutig, Fremdschlüssel; Migration `5c1e9a7b3d20`, `downgrade()` bricht ab, solange
  eine Anfrage übernommen ist). Die Anfrage nennt Nummer und Weg zum Eingang mit PDF und Fotos (`InquiryOut.webseite_nummer`, `webanfrage_id`; Seite
  „Anfragen“, Karte der Anfrage). Statuskennzeichen „Übernommen“; Erledigt zeigt „übernommen: ANF-…“.
- Seite der Anfrage: Karte „Als Anfrage übernehmen“ (nur bei einer neuen Anfrage im Eingang) -- Auftraggeber und Objekt als Auswahl ohne Vorauswahl, die
  Felder des neuen Kunden und Objekts aus dem Vorschlag, „Als Anfrage übernehmen“ abschließend; danach die neue Anfrage (`/inquiries?inquiry=<ID>`).

#### Festlegungen 1.10.5 (bestätigt am 20.11.2026)

1. Der Vorschlag kommt nur aus den strukturierten Angaben, nie aus Betreff oder Nachricht (die beiden nur als Vorschlag für Betreff und Beschreibung der
   Anfrage): Eigentümer -> der Melder wird Kunde (Verbraucher ja, die Adresse des Objekts als Vorschlag für seine Anschrift); Hausverwaltung bzw. Firma ->
   die Firma wird Kunde (Verbraucher nein, ohne Anschrift), der Melder ihr Ansprechpartner; Mieter -> die Hausverwaltung bzw. der Vermieter aus dem
   Pflichtfeld wird Kunde (Verbraucher ja/nein wählt das Büro), Telefon und E-Mail des Mieters gehören nie zum Kunden, der Mieter ist Ansprechpartner vor Ort
   (ein angegebener Ansprechpartner vor Ort geht vor); Kantservice, Dach und PV -> der Kontakt wird Kunde (Dach Verbraucher ja, PV nach „privat/gewerbe“,
   Kantservice offen; Kantservice ohne Objekt, sein „Ort“ nur als Hinweis).
2. Bestehende Kunden werden mit ihren Gründen vorgeschlagen: „E-Mail gleich“ (auch die zweite E-Mail), „Telefon gleich“ (letzte sieben Ziffern, Telefon und
   Mobil), „Name gleich“ (Person: Nach- und Vorname wie im Telefonbuch) bzw. „Name ähnlich“ (Firma, Hausverwaltung: enthalten); „PLZ gleich“ nur zusätzlich.
   Beim Mieter nur nach dem Namen der Hausverwaltung. Höchstens zehn, die meisten Gründe zuerst.
3. Zum gewählten Kunden stehen seine Objekte zur Wahl, „Adresse gleich“ (PLZ und Straße; „Str.“/„Straße“, ß/ss und Leerraum gleich) zuerst.
4. Nichts ist vorgewählt: das Büro wählt Auftraggeber (bestehend oder neu) und Objekt (bestehend, neu, Hauptadresse des neuen Kunden, ohne); beim neuen
   Kunden ist „Verbraucher“ am Server Pflicht ohne Vorgabe (die Seite belegt ihn nur vor, wo die Angaben es sagen); den Ansprechpartner vor Ort trägt die
   Übernahme an einem bestehenden Objekt nur mit Haken ein (die Seite nennt den bisherigen).
5. Übernehmen ist eine Transaktion: zuerst die Anfrage der Webseite (bedingtes UPDATE -- nicht aus der Prüfliste, nie zweimal, sonst 409), dann Kunde (über
   `kunde_anlegen()`), Objekt, Anfrage (Status neu, Quelle „Website“, Nummer der Webseite), die Fotos ans Objekt (Kategorie „Bilder / Fotos“, verkleinert
   wie ein Upload); scheitert etwas, bleibt nichts -- auch keine Datei.
6. Ein gewähltes Objekt gehört zum gewählten Kunden (sonst 422); ein unbekannter Kunde oder ein unbekanntes Objekt 404 (Regel 25).
7. Das PDF bleibt am Eingang; die Anfrage nennt die Nummer der Webseite mit Weg dorthin und PDF und Fotos als Links.
8. Nach dem Übernehmen bekommt der Empfangsdienst die Anfragenummer (F2; passt sie nicht in seine Zeichen, `anfrage-<ID>`) -- wie beim Verwerfen unter der
   Sperre des Abholens, sonst im nächsten Lauf.
9. Die Historie nennt „übernommen“ mit Nummer und Anfragenummer, ohne Inhalte; Kunde, Objekt und Anfrage stehen in ihr wie jedes Anlegen.
10. Danach öffnet die Seite die neue Anfrage; „Erledigt“ nennt „übernommen: ANF-…“.
11. Lesen und Übernehmen nur das Büro ab Büro – Auftrag; die Monteurin an keinem Weg.

#### Tests und Prüfung 1.10.5

Neu `tests/test_v777_webanfragen_uebernehmen.py` (16 Tests: Vorschlag je Rolle, Kantservice/Dach/PV, nie aus Betreff oder Nachricht; bestehende Kunden mit
Gründen, beim Mieter nur nach der Hausverwaltung; Objekte mit „Adresse gleich“; Übernehmen mit neuem Kunden, neuem Objekt, Fotos, Meldung, Historie, zweimal
409, Nummer an der Anfrage; bestehender Kunde und Objekt ohne Haken; Ansprechpartner vor Ort nur mit Haken; fremdes Objekt 422, unbekanntes Objekt und
unbekannter Kunde 404 -- nichts angelegt; eine fehlende Datei -- nichts angelegt, keine Datei; nicht aus der Prüfliste, Hauptadresse nur beim neuen Kunden,
ohne Auftraggeber und ohne „Verbraucher“ 422; Monteurin nirgends; in node nichts vorgewählt und jeder Wert über esc(), die Anfrage nennt die Nummer, Erledigt
nennt die Anfragenummer; Migration auf einem Bestand unter PostgreSQL). Die Tests der Kunden laufen unverändert über `kunde_anlegen()`. Klicktest
`scripts/klicktest_webanfragen.py` um das Übernehmen erweitert (70 Prüfungen; dabei behoben: „ja“/„nein“ unter „Verbraucher“ standen unter dem Knopf, eine
Meldung blieb nach der Auswahl stehen). Die volle Suite fand: die neue Spalte `inquiries.webseite_nummer` brauchte einen lesbaren Namen in der Änderungshistorie (`app/audit.py::FIELD_LABELS` „Nummer der Webseite“, Wächter `test_v436`/`test_v438`).

Angepasste Erwartungen (Regel 28):
- `tests/test_v776_webanfragen_pruefliste.py::test_gruende_fest_und_gleich` -- `STATUS` alt („neu“, „verworfen“), neu mit „uebernommen“.
- `scripts/klicktest_webanfragen.py` -- „Empfangsdienst aus: Liste bleibt“ alt 3, neu 2 (die Reparatur ist vorher übernommen).
- Aufbau geändert: `ABSCHLIESSEND` um `webanfrage.html::webanfrageUebernehmen` (`test_v399`); `objekt_id` der Übernahme in `GEPRUEFT`, `kunde_id` in `FREI`
  (`tests/test_v373_zugehoerigkeit_struktur.py`); Testwert `kunde_id` in `QUERY_WERTE` (`tests/test_v326_monteur_datengrenze.py`).

Gegenproben: `gegenproben-webseite.md`, „W1b, 1.10.5“ (27 über pytest und eine über den Klicktest, alle rot).

### Nachrunde W1b (ab 1.10.7)

Antworten des Betriebs (20.11.2026): Festlegungen 1.10.0–1.10.2 (W1a) und 1.10.3-1 bis 1.10.5-11 (W1b) bestätigt, W1b bis auf eine Lücke. Fragen aus W1b:
F1 ja (Verbraucher-Vorgaben beim neuen Kunden so lassen), F2 ja (Fotos als Kopie ans Objekt, das PDF bleibt am Eingang; **die Fotokopien am Objekt fallen in
W1c unter dieselbe Frist wie ihre Anfrage**), F3 ja (Kantservice vorerst „ohne Objekt“), F4 ja (als Nächstes der Befund zu F12, dann W1c). Dazu aus dem
Bericht des Aufräumens (1.10.6): der rote Klicktest als 1.10.7 (unten). Nachrunde 1.10.8: beim Übernehmen immer „Anderen bestehenden Kunden wählen“.
W1b wird zusammen mit 1.10.6 bis 1.10.8 eingespielt.

### Umsetzung 1.10.7: Zeitpunkte der Bearbeitung über utc_jetzt()

Anlass: im Endlauf des Aufräumens (b114a03, 20.11.2026) war `klicktest_webanfragen` rot (68/70): „verworfen am“ und „aus der Prüfliste gegeben am“ standen
mit `datetime.utcnow()` -- der echten Uhr -- in der Datenbank, die Uhr der Instanz stand im Klicktest auf dem 19.11.2026. Am Tag des Baus fiel beides
zusammen (Endlauf W1b 155/155), ab dem 20.11. nicht mehr. Seit 1.10.7 setzen `app/webanfragen.py` und `app/webanfrage_uebernahme.py` die Zeitpunkte der
Bearbeitung über `app/berlin_time.py::utc_jetzt()` (Vorbild 1.9.367): abgeholt (`abgeholt_am` beim Ablegen statt der Spaltenvorgabe), gemeldet, letzter
Lauf (mit und ohne Verbindung), letzter Erfolg, geprüft, verworfen, übernommen. Die Sperre des Abholens (`lauf_seit`, `stand()["laeuft"]`) bleibt auf der
echten Uhr. Im Betrieb ändert sich nichts (dieselbe Zeit, ohne Mikrosekunden); der Klicktest blieb unverändert und ist wieder 70/70.

#### Festlegungen 1.10.7 (bestätigt am 20.11.2026)

1. Abgeholt, gemeldet, letzter Lauf, letzter Erfolg, geprüft, verworfen und übernommen kommen aus `utc_jetzt()` -- dieselbe Uhr wie `berlin_now()`, im Betrieb
   gleich `datetime.utcnow()`, unter einer festen Uhr (Tests, Klicktests) stimmig zum Rest der Seite.
2. Die Sperre des Abholens bleibt auf der echten Uhr: sie gilt über Prozesse und läuft nach `SPERRE_GILT` ab -- unter einer stehenden Uhr liefe sie nie ab.
3. `klicktest_webanfragen` bleibt unverändert: seine Erwartung „am 19.11.2026“ ist jetzt richtig, weil die Seite der Uhr der Instanz folgt.

#### Tests und Prüfung 1.10.7

Neu `tests/test_v778_webanfragen_zeitpunkte.py` (4 Tests unter einer festen Uhr am 03.03.2025: Abholen und Melden, letzter Lauf ohne Verbindung, Verwerfen,
In den Eingang und Übernehmen samt Nachmelden, die Sperre auf der echten Uhr). `klicktest_webanfragen` vor 1.10.7 68/70 (Endlauf b114a03), danach 70/70
ohne Änderung. Angepasste Erwartungen: keine. Gegenproben: `gegenproben-webseite.md`, „Nachrunde W1b, 1.10.7“ (9, alle rot).

### Umsetzung 1.10.8: Anderen bestehenden Kunden wählen

Vorgabe des Betriebs (20.11.2026): beim Übernehmen konnte das Büro nur einen vorgeschlagenen oder einen neuen Kunden wählen. Findet der Vorschlag den
bestehenden Kunden nicht (neue E-Mail, neue Telefonnummer, Name anders geschrieben), blieb nur „Neuer Kunde“ -- eine Dublette. Dazu immer sichtbar „Anderen
bestehenden Kunden wählen“ mit Suche, danach seine Objekte wie beim Vorschlag; auch im Mieter-Fall; gleiche Prüfungen (422/404).

- Die Vorgabe nannte „Suche wie bei ‚Neue Anfrage‘ (Telefonbuch, passt())“. „Neue Anfrage“ (`inquiries.html`) hat keine Suche, nur eine Auswahlliste aller
  Kunden in der Reihenfolge der Kundenliste; mit `passt()` sucht die Büro-Suche. Gebaut ist deshalb deren Kundensuche: `app/search.py::kunden_suchen()`
  (dieselbe Funktion `_search_customers()` wie die Büro-Suche: `passt()` auf Name und Kundennummer, Reihenfolge `nach_namen(Nachname, Vorname)`, ab
  `MIN_QUERY_LENGTH` = 2 Zeichen).
- `app/webanfrage_uebernahme.py::kunden_suche()` gibt die Treffer in der Form der Vorschläge (`_kunde_zeile()`, ohne Gründe), höchstens `SUCHE_MAX` = 20, dazu
  die Zahl aller; `GET /api/webanfragen/{id}/kunden?suche=` (ab Büro – Auftrag, `WebAnfrageKundenSucheOut`, schreibt nichts, unbekannte Anfrage 404, Suche
  über 100 Zeichen 422). Übernehmen prüft unverändert (Objekt nur des gewählten Kunden 422, unbekannter Kunde oder unbekanntes Objekt 404).
- Seite: unter „Auftraggeber“ die Vorschläge (ohne Vorschlag der Hinweis „Kein bestehender Kunde passt zu den Angaben – unten suchen oder einen neuen
  anlegen.“), dann „Anderen bestehenden Kunden wählen“ mit Suchfeld (`uebSuche`), dann erst „Neuer Kunde“ (`uebKundeNeuWahl`). Jedes Tippen liest über
  `lesen('kundensuche', …)` (ältere Antworten verworfen); ein Treffer ist eine Wahl in derselben Radiogruppe wie ein Vorschlag (`data-quelle="suche"`), danach
  seine Objekte über `…/objekte?kunde_id=`.

#### Festlegungen 1.10.8 (bestätigt am 20.11.2026)

1. „Anderen bestehenden Kunden wählen“ steht immer auf der Karte, für jede Rolle der Anfrage (auch beim Mieter), zwischen den Vorschlägen und „Neuer Kunde“ --
   erst suchen, dann neu anlegen. Ohne Vorschlag steht dort „Kein bestehender Kunde passt zu den Angaben – unten suchen oder einen neuen anlegen.“
2. Die Suche ist die Kundensuche der Büro-Suche (`app/search.py::kunden_suchen()`): `passt()` auf Name und Kundennummer, wie im Telefonbuch, in der
   Reihenfolge der Kundenliste. Nicht nach Telefon, E-Mail oder Adresse (das kann der Vorschlag; die Suche ist für den Namen, den das Büro kennt).
3. Ab zwei Zeichen; höchstens 20 Treffer, dazu die Zahl aller („N Treffer, hier die ersten 20 – bitte genauer suchen.“); jedes Tippen liest neu, ohne Verzögerung
   (der Baustein verwirft ältere Antworten).
4. Ein Treffer ist eine Wahl wie ein Vorschlag (dieselbe Radiogruppe, ohne Gründe), danach seine Objekte wie beim Vorschlag (mit „Adresse gleich“ und dem
   Angebot „Ansprechpartner vor Ort eintragen“); nichts vorgewählt, jeder Wert über `esc()`.
5. Sucht das Büro weiter und der gewählte Treffer ist nicht mehr unter den Treffern, ist die Auswahl aufgehoben (Objekte wieder „Erst den Auftraggeber wählen.“).
6. `GET /api/webanfragen/{id}/kunden?suche=` ab Büro – Auftrag, schreibt nichts; unbekannte Anfrage 404, Suche über 100 Zeichen 422; Übernehmen mit den
   Prüfungen von 1.10.5 (Objekt nur des gewählten Kunden 422, unbekannter Kunde 404, nichts angelegt).

#### Tests und Prüfung 1.10.8

Neu `tests/test_v779_webanfragen_anderer_kunde.py` (9 Tests: Suche wie die Büro-Suche -- „grundler“ findet „Gründler“, dieselben Treffer in derselben
Reihenfolge wie `search_office()`, Kundennummer, ab zwei Zeichen, „%“ wörtlich, 422/404, schreibt nichts; höchstens 20 mit der Zahl aller; Mieter übernimmt den
gefundenen Kunden mit seinem Objekt, keine Dublette, Telefon und E-Mail des Mieters nicht beim Kunden; Prüfungen 422/404 ohne Anlegen; Monteurin 403; in node
Reihenfolge der Karte, Treffer wie ein Vorschlag, nichts vorgewählt, esc(), Auswahl aufgehoben, Hinweise). Klicktest `scripts/klicktest_webanfragen.py` um den
Mieter mit anders geschriebener Hausverwaltung erweitert (78 Prüfungen; neue Musteranfrage `R-20261119-0913-0A7B`, im Seed die „Hausverwaltung Gründler GmbH“
mit Mietshaus; neues Bild `webanfragen_anderer_kunde_1440_hell`).

Angepasste Erwartungen (Regel 28):
- `tests/test_v777_webanfragen_uebernehmen.py::test_seite_nichts_vorgewaehlt_und_ueber_esc` -- Aufbau: „Neuer Kunde“ (`value="neu"`) alt in `uebKunden`, neu in
  `uebKundeNeuWahl` (nach der Suche); die Prüfung selbst ist gleich.
- Aufbau: `ueb-suche` in `KARTEN_OHNE_NAMEN` (`tests/test_v460_ecken_der_karten.py`, Kasten in einer Karte, Ecke `var(--ds-ecke-karte)`) -- zuerst mit 8 px
  gebaut, der Wächter schlug im Lauf vor dem Commit an.

Gegenproben: `gegenproben-webseite.md`, „Nachrunde W1b, 1.10.8“ (16 über pytest und eine über den Klicktest, alle rot).

## W1c: Archiv (ab 1.10.9)

### Befund F12 und die Antworten des Betriebs (20.11.2026)

Vor W1c ein Befund nur zum Lesen (`befund_f12_ac14e6f.txt`, 20.11.2026): was unter „kein Auftrag“ fällt, welche Zeitpunkte „letzter Kontakt“ sicher belegen,
die Aufbewahrungspflichten mit Quellen (§ 257 HGB, § 147 AO, § 14b UStG, GoBD; strittig: versendete Angebote ohne Auftrag), ein Nur-Lese-Befehl für die
Mengen auf dem Server und ein Vorschlag für W1c. Kurz:

- **„Kein Auftrag“** heißt: keine Zeile in `orders` (jeder Status, auch storniert). Ein Kunde hat einen Auftrag, wenn ihm ein Auftrag, ein Projekt mit Auftrag,
  ein Wartungsvertrag, eine Rechnung oder eine Zahlung gehört. Mustervorgänge gehören nicht dazu; Kunden aus dem Adressimport sind nicht sicher zu beurteilen
  (Aufträge im Altsystem).
- **Letzter Kontakt** sicher: Eingang der Webseite, Versand und nachgetragene Zustellung, Empfang bestätigt, Termin mit Bezug zu Projekt oder Angebot,
  Besichtigung. Nicht bekannt: Telefonate, Mails außerhalb des ERP, Antworten des Kunden -- dafür „Kontakt vermerken“.

Antworten des Betriebs (20.11.2026):

- Mengen auf dem Server (Nur-Lese-Befehl): Eingang neu 7 (ältester 04.11.), verworfen 1, übernommen 0; Anfragen, Projekte und Angebote ohne Auftrag je 0;
  Kunden ohne Auftrag 159, davon 158 aus dem Adressimport; Rohzeilen des Adressimports 345, davon 186 ohne Kunden; Termine ohne Bezug 29; Historie 1444.
  Hinweis des Betriebs: `NOT IN` über eine Spalte mit NULL liefert still nichts -- im Befehl um `IS NOT NULL` ergänzt; im Code von W1c `NOT EXISTS` oder
  gleichwertig, mit Test auf NULL.
- F1 so lassen: „Ansprechpartner vor Ort eintragen“ ist nie vorbelegt. F2 ja: die vier weiteren Stellen mit Muster-Merkmalen in einem eigenen Doku-Commit vor
  W1c (`8fffc5b`). F3 (a), (c), (d), (e) gehen an den Rechtsberater; (b) entfällt -- die Datenschutzerklärung online (Paket 2026-11-19a) sagt: archivieren
  sechs Monate nach dem letzten Kontakt, die personenbezogenen Daten löschen drei Jahre nach Ende des Jahres der Archivierung (der Befund las eine alte
  Fassung). F4 grundsätzlich ja (Ausnahme von Regel 21 für Angebote ohne Auftrag nach Ablauf der Frist), gebaut erst in Stufe 2. F5: die lokale
  `dachkonzepte_erp.db` wurde nie mit echten Daten benutzt. F6 ja: Kunden aus dem Adressimport nie automatisch. F7 nein: beim Anonymisieren keine Nummern
  behalten (sie stehen in Mails im Postfach, die Zeile wäre sonst nur pseudonym), die Angebotssumme nur als Größenklasse. F8 ja: Archiv und Löschen
  bestätigen Admin und Büro – Finanzen.

Vorgabe für W1c (nur Stufe 1; Löschen ist frühestens 2030 fällig, Stufe 2 erst nach dem Rechtsberater):

1. Archiv nach 6 Monaten ab letztem Kontakt wie im Befund 5.1–5.3: Eingänge, Anfragen, Projekte ohne Auftrag; Kunde und Objekt nur, wenn nichts mehr daran
   hängt; Kunden aus dem Adressimport nie automatisch. Das vorhandene „archiviert“ am Projekt nutzen statt doppeln.
2. „Kontakt vermerken“ (Datum, Art, ohne Inhalt) an Anfrage, Projekt und Kunde.
3. Vorschau mit Herkunft des Datums, Bestätigen einzeln oder gesammelt (Admin, Büro – Finanzen), Zurückholen, Erinnerung auf „Start“ auch für unbearbeitete
   Eingänge.
4. Verworfene Eingänge mit Grund Spam, Test oder Doppelt 6 Monate nach Eingang ganz löschen, samt Dateien, nach Bestätigung; die Historie bleibt ohne Inhalte.
   „Sonstiges“ wie die übrigen.
5. Fremdschlüssel Objektdokument → Eingang der Webseite für die Fotokopien (heute nur am Text erkennbar).
6. Stufe 2 im Archiv festhalten: Befund 5.4/5.5 mit F7, Ausnahme Regel 21, Fristen als Einstellung, dazu „Aufbewahrung der Server-Sicherungen auf dem NAS prüfen“.
7. Nur melden mit Vorschlag: die Rohdaten des Adressimports (345 Zeilen, 186 ohne Kunden) -- werden sie noch gebraucht?

Runden: 1.10.9 Fremdschlüssel Objektdokument → Eingang (Punkt 5), 1.10.10 Kontakt vermerken (Punkt 2), 1.10.11 Archiv und Zurückholen mit den Filtern
(Punkt 1), 1.10.12 Seite „Aufbewahrung“ und Erinnerung auf „Start“ (Punkt 3), 1.10.13 verworfene Eingänge löschen (Punkt 4) und Stufe 2 (Punkt 6).

### Umsetzung 1.10.9: Objektdokument → Eingang der Webseite

- `PropertyDocument.webanfrage_id` (leer erlaubt, Fremdschlüssel auf `webanfragen`, Index): das Übernehmen setzt ihn an jeder Fotokopie
  (`app/webanfrage_uebernahme.py` über `create_property_document(…, webanfrage_id=…)`); Beschreibung „Foto der Anfrage der Webseite <Nummer>“ und Dateiname
  „<Nummer>-foto-N.jpg“ bleiben wie seit 1.10.5. Kein Upload-Weg (Büro, Monteurin) setzt ihn.
- Migration `7e3a9c1f5b28`: neue Spalte; im Bestand verknüpft sie nur ein Dokument mit allen drei Merkmalen -- Beschreibung genau „Foto der Anfrage der
  Webseite <Nummer>“, Dateiname beginnt mit „<Nummer>-“, die Anfrage, als die der Eingang übernommen wurde, liegt an genau diesem Objekt (`verknuepfen()`,
  `substr`/`length`/`||` wie unter SQLite so unter PostgreSQL, kein `LIKE` mit der Nummer). `downgrade()` nimmt nur die Spalte weg. Auf dem Server sind
  heute 0 Eingänge übernommen -- der Bestand bleibt leer.

#### Festlegungen 1.10.9 (bestätigt am 21.11.2026)

1. Jede Fotokopie, die das Übernehmen ans Objekt legt, trägt ihren Eingang als Fremdschlüssel; Beschreibung und Dateiname bleiben wie bisher.
2. Ein von Hand hochgeladenes Objektdokument trägt nie einen Eingang -- auch nicht mit derselben Beschreibung.
3. Im Bestand verknüpft die Migration nur bei allen drei Merkmalen (Beschreibung genau, Dateiname mit „<Nummer>-“, Objekt der übernommenen Anfrage); eine
   leere Beschreibung, ein anderes Objekt, eine Anfrage ohne Objekt, ein nicht übernommener Eingang oder „%“ im Text bleiben leer.
4. `downgrade()` nimmt nur die Spalte weg; Dokumente, Beschreibung und Dateiname bleiben.

#### Tests und Prüfung 1.10.9

Neu `tests/test_v780_objektdokument_webanfrage.py` (4 Tests: Übernehmen setzt den Eingang an jeder Fotokopie; ein Upload mit demselben Text trägt keinen;
Migration auf einem Bestand mit neun Dokumenten -- zwei verknüpft, sieben aus je einem Grund leer, ein zweiter Lauf ändert nichts, downgrade lässt alles
stehen -- unter SQLite und PostgreSQL). Angepasste Erwartungen: keine. Gegenproben: `gegenproben-webseite.md`, „W1c, 1.10.9“ (6, alle rot).

### Umsetzung 1.10.10: Kontakt vermerken

- Tabelle `kontaktvermerke` (`app/models.py::Kontaktvermerk`, Migration `2d8b6f4a9c13`): genau ein Bezug -- Anfrage, Projekt oder Kunde (CHECK
  `ck_kontaktvermerk_ein_bezug`) --, Tag (`kontakt_am`) und Weg (`weg`: telefon, email, brief, gespraech, sonstiges; `app/kontaktvermerke.py::WEGE`),
  Zeitpunkt (`utc_jetzt()`) und Konto aus der Anmeldung. Keine Spalte für einen Inhalt; das Eingabeschema `KontaktvermerkIn` lehnt jedes weitere Feld ab
  (`extra="forbid"`, 422). `downgrade()` bricht ab, solange ein Vermerk besteht.
- `GET`/`POST /api/inquiries/{id}/kontakte`, `/api/projects/{id}/kontakte`, `/api/customers/{id}/kontakte` (`app/routers/kontaktvermerke.py`, ab Büro –
  Auftrag): die Liste des Bezugs, der jüngste Kontakt zuerst; `POST` gibt die neue Liste zurück. Tag nicht in der Zukunft (Berlin), nicht vor dem 01.01.2000
  (`tag_pruefen()`, im Schema; der Dialog prüft dasselbe vor dem Senden); unbekannter Bezug 404.
- Ein Dialog für alle drei Seiten (`app/templates/_kontaktvermerk.html`, `kontaktDialogOeffnen(art, id, titel)`, bindet seine Bausteine selbst ein):
  Anfragen (Knopf im Editor), Akte („⋮ → Kontakt vermerken …“ nach „Beteiligte“), Kundenakte („⋮ → Kontakt vermerken …“ nach „Neue Anfrage“). Tag vorbelegt
  heute, Weg nicht vorgewählt; die Liste „Bisher vermerkt“ mit „vermerkt am … von …“ über `textContent` (kein HTML aus Daten).
- Historie: der Vermerk ist protokolliert (Art „Kontakt“, Bezeichnung „<Weg> am <Tag>“, nie ein Inhalt); am Projekt und an der Anfrage eines Projekts im
  Verlauf der Akte, am Kunden im Verlauf des Kunden (`app/kunde_verlauf.py::TYPEN`).
- Ein Vermerk bleibt, wie er ist (kein Ändern, kein Löschen); er geht nur mit seinem Projekt, wenn ein Projekt ohne Auftrag gelöscht wird
  (`delete_project()`, zuerst die Vermerke -- Regel 6); die Vermerke einer Anfrage bleiben an ihr. Ein Konto mit Vermerken lässt sich nicht löschen
  (`app/konto_loeschen.py::BEREICHE`, „Kontaktvermerke“).
- Für die Aufbewahrung zählt ein Vermerk ab 1.10.11 (`app/aufbewahrung.py`); in 1.10.10 wird er nur gespeichert und gezeigt.

#### Festlegungen 1.10.10 (bestätigt am 21.11.2026)

1. „Kontakt vermerken“ gibt es an der Anfrage (Knopf im Editor), am Projekt (⋮ der Akte) und am Kunden (⋮ der Kundenakte) -- ein gemeinsamer Dialog.
2. Ein Vermerk hat nur Tag und Weg (Telefon, E-Mail, Brief, Gespräch, Sonstiges); es gibt keine Spalte für einen Inhalt, jedes weitere Feld lehnt der Server ab.
3. Der Tag liegt nicht in der Zukunft (Berlin) und nicht vor dem 01.01.2000 -- Dialog und Server prüfen dasselbe; vorbelegt ist heute, der Weg ist nicht
   vorgewählt.
4. Lesen und Vermerken ab Büro – Auftrag (wie die Anfragen); die Monteurin an keinem Weg; ein unbekannter Bezug 404.
5. Jeder Vermerk hat genau einen Bezug (Prüfung in der Datenbank).
6. Ein Vermerk bleibt (kein Ändern, kein Löschen); er geht nur mit seinem Projekt, wenn ein Projekt ohne Auftrag gelöscht wird; die Vermerke einer Anfrage
   bleiben an ihr.
7. Die Historie nennt „<Weg> am <Tag>“ mit dem Konto, nie einen Inhalt; der Verlauf der Akte zeigt die Vermerke des Projekts und seiner Anfrage, der Verlauf
   des Kunden die des Kunden.
8. Die Liste im Dialog zeigt den jüngsten Kontakt zuerst, mit „vermerkt am … von …“, nur als Text.
9. Ein Konto mit Vermerken lässt sich nicht löschen (Bereich „Kontaktvermerke“, wie die übrigen Bereiche: deaktivieren).

#### Tests und Prüfung 1.10.10

Neu `tests/test_v781_kontaktvermerke.py` (25 Tests: je Bezug vermerken und lesen, Reihenfolge, Konto; Tag und Weg mit sechs Fällen 422, heute und
01.01.2000 gehen; unbekannter Bezug 404 auch über int4; Monteurin 403; genau ein Bezug in der Datenbank; keine Spalte für einen Inhalt; Historie mit Weg,
Tag und Projekt; Verlauf des Kunden; Projekt löschen nimmt seine Vermerke mit, die der Anfrage bleiben; in node: Dialog in den drei Seiten, Liste als Text,
gesendet werden nur Tag und Weg, Zukunft und vor 2000 nicht gesendet). Neuer Klicktest `scripts/klicktest_kontakt_vermerken.py` (22 Prüfungen: Anfragen,
Akte, Kundenakte bei 412 px hell und dunkel, Server, Monteurin 403; Bilder `kontakt_akte_1440_hell`, `kontakt_kundenakte_412_hell|dunkel`).

Angepasste Erwartungen (Regel 28):
- `tests/test_v557_kundenakte_seite.py::test_menue_der_akte_in_drei_gruppen` -- alt: Projektgruppe ohne „kontakt-projekt“; neu: „kontakt-projekt“ nach
  „beteiligte-oeffnen“.
- `tests/test_v557_kundenakte_seite.py::test_menue_der_kundenakte_in_zwei_gruppen_ohne_archivieren` -- alt: Kundengruppe ohne „kontakt-kunde“; neu: mit
  „kontakt-kunde“ am Ende.
- Aufbau: neue Einträge in `FUNKTIONEN` (`tests/test_v549_akte_seite.py`, `tests/test_v554_kundenakte_funktionen.py`), in `PROJEKT_FREMDSCHLUESSEL`
  (`tests/test_v746_aufgabe_und_projekt_loeschen.py`: „kontaktvermerke.project_id geht mit“), `_kontaktvermerk.html` in `BAUSTEINE` und `replaceChildren`
  an erzeugten Elementen der Attrappe (`tests/test_v334_auswahl_restfaelle.py`).
- `scripts/klicktest_kundenakte.py`, „„⋮“ des Kopfs: zwei Gruppen“ -- alt: Stammdaten bearbeiten, + Objekt, + Eintrag, Neue Anfrage · Versandprotokoll,
  Änderungshistorie; neu: „Kontakt vermerken …“ nach „Neue Anfrage“ (im Lauf vor dem Commit rot, 59/60, danach 60/60).

Klicktests der geänderten Seiten (Akte, Kundenakte, Anfragen) vor dem Commit: 41, davon 40 wie erwartet und `klicktest_kundenakte` 59/60 (die Erwartung
oben), danach 60/60.

Gegenproben: `gegenproben-webseite.md`, „W1c, 1.10.10“ (17 über pytest, eine über den Klicktest, alle rot).

### Umsetzung 1.10.11: Archiv nach dem letzten Kontakt (Rechnung, Bestätigen, Zurückholen, Filter)

- Migration `9a4c2e7b1d56`: an `webanfragen`, `inquiries`, `customers` und `projects` je `archiviert_am` (naives UTC, leer = nicht im Archiv), `archiviert_von_user_id`
  (Konto) und `zurueckgeholt_am`; am Projekt bleibt das vorhandene `archived` das Kennzeichen (nicht gedoppelt), die Spalten sagen nur wann und von wem.
  `downgrade()` bricht ab, solange ein Eingang, eine Anfrage oder ein Kunde im Archiv ist.
- `app/aufbewahrung.py`: `berechnen()` rechnet den ganzen Stand in einer festen Zahl Abfragen. Einheiten: Eingang ohne Übernahme (neu oder verworfen mit
  „Sonstiges“; Spam, Test, Doppelt löscht 1.10.13), Anfrage ohne Projekt (mit ihrem Eingang), Projekt ohne Auftrag (keine Zeile in `orders`, auch keine
  stornierte; kein Mustervorgang) mit Anfrage und Eingang. Letzter Kontakt = der späteste sichere Tag (Berlin) mit Herkunft: Eingang der Webseite, sonst das
  Anlegen; vergangene Besichtigung; Kontaktvermerk; Angebot (nicht Entwurf) mit seinem Datum, per E-Mail versendet, zugestellt, Empfang bestätigt;
  vergangener Termin am Projekt oder Angebot; Zurückholen. Fällig ab = + 6 Monate (`monate_spaeter()`, am Monatsende der letzte Tag). Sperren: offene Aufgabe
  am Projekt, Vorlage eines Wartungsvertrags (Vertrag oder Position).
- Kunde (`_kunden()`): geht nur mit, wenn ihm kein Auftrag, kein Projekt mit Auftrag, kein Wartungsvertrag, keine Rechnung und keine Zahlung gehört, er keinen
  Mustervorgang hat, nicht im Adressbuch verknüpft ist, an seinen Objekten kein Vertrag, keine Checkliste und kein Vorgang eines anderen Kunden hängt, und
  jeder seiner Vorgänge im Archiv oder mit ihm fällig ist; nie aus dem Adressimport. Sein letzter Kontakt ist der späteste aus Anlage, eigenen Vermerken,
  Zurückholen und allen seinen Vorgängen. Seine Objekte gehen mit ihm (ein Objekt allein nie). Alle Mengen in Python bzw. mit EXISTS -- kein `NOT IN` über
  eine Spalte, die leer sein darf.
- `GET /api/aufbewahrung` (Vorschau: was fällig ist und was gesperrt ist, gruppiert je Kunde, Eingänge für sich, Zahl, „seit“, Zahl der unbearbeiteten
  Eingänge, Prüfsumme `stand`) und `GET /api/aufbewahrung/archiv` -- ab Büro – Auftrag. `POST /api/aufbewahrung/{art}/{vorgang_id}/archivieren` (einzeln; ein
  Kunde nimmt seine fälligen Vorgänge mit) und `POST /api/aufbewahrung/archivieren` (gesammelt, nur mit der Prüfsumme der Vorschau, sonst 409) -- Admin und
  Büro – Finanzen (`app/permissions.py::darf_aufbewahrung()`). Bestätigt wird unter den Sperren neu gerechnet; was nicht mehr fällig ist, steht mit Grund unter
  „uebersprungen“. `POST /api/aufbewahrung/{art}/{vorgang_id}/zurueckholen` -- ab Büro – Auftrag; nicht im Archiv 409.
- Im Archiv fehlt eine Einheit in: `GET /api/customers`, `/api/properties`, `/api/inquiries` (mit `archivierte=true` auch sie, Objekte mit `kunde_im_archiv`);
  Büro-Suche (Kunden, Objekte, Anfragen; Projekte und Angebote eines archivierten Projekts ohne Auftrag -- mit Auftrag bleibt es wie bisher auffindbar);
  Objektsuche der Monteurin; Eingang der Webseite (Ansichten, Zähler, „Start“), Vorschlag und Suche beim Übernehmen; Objektdokumente (die Fotokopien eines
  Eingangs im Archiv, Büro und Monteurin); Wiedervorlage auf „Start“ (über `/api/inquiries`). Über die Kennung bleibt alles lesbar.
- Sperren am Rand: eine Anfrage an einem Kunden im Archiv anlegen oder ändern, ein Projekt für ihn anlegen, ein Projekt zu ihm wechseln -- 409 („erst
  zurückholen“); beim Übernehmen ist er wie unbekannt (404); eine Aktion an einem Eingang im Archiv 409; ein Kontaktvermerk im Archiv 409.
- Archivieren über das „⋮“ der Akte (wie bisher jedes Büro, `set_project_archived()` -> `projekt_von_hand()`): setzt Zeitpunkt und Konto, ohne Auftrag mit
  Anfrage und Eingang; Entarchivieren zählt als Zurückholen und holt einen Kunden im Archiv mit.
- Historie: je Einheit „archiviert“ bzw. „zurückgeholt“ unter der Art, die es schon gibt (Anfrage der Webseite, Anfrage, Projekt, Kunde), Feld „Archiv“
  aktiv ↔ im Archiv, mit der Nummer, ohne Inhalte; das Projekt im Verlauf der Akte.
- Seiten: „Projekt bearbeiten“ in der Akte und das Objektformular der Stammdaten laden die Kunden samt Archiv; ein gespeicherter Kunde im Archiv bleibt
  gewählt („(im Archiv)“), neu angeboten werden nur aktive. Die Kundenakte lädt ihre Objekte und Anfragen samt Archiv. Die Seite „Aufbewahrung“ und die
  Erinnerung auf „Start“ kommen mit 1.10.12.

#### Festlegungen 1.10.11 (bestätigt am 21.11.2026)

1. Einheiten: Eingang ohne Übernahme (neu oder verworfen mit „Sonstiges“), Anfrage ohne Projekt mit ihrem Eingang, Projekt ohne Auftrag (keine Zeile in
   `orders`, auch keine stornierte; kein Mustervorgang) mit Anfrage und Eingang. Am Projekt gilt das vorhandene „archiviert“, dazu Zeitpunkt und Konto.
2. Letzter Kontakt ist der späteste sichere Tag mit Herkunft: Eingang, sonst Anlage; vergangene Besichtigung; Kontaktvermerk; Angebot (nicht Entwurf) mit
   Datum, versendet, zugestellt, Empfang bestätigt; vergangener Termin am Projekt oder Angebot; Zurückholen. Ein Entwurf, eine künftige Besichtigung und ein
   künftiger Termin zählen nicht.
3. Fällig ab = letzter Kontakt + 6 Monate; gibt es den Tag nicht, der letzte des Monats. Die 6 Monate stehen in Stufe 1 fest im Code.
4. Nicht fällig, solange am Projekt eine offene Aufgabe hängt oder ein Wartungsvertrag (oder eine Position) es als Vorlage nimmt -- die Vorschau nennt den Grund.
5. Ein Kunde geht nur mit, wenn nichts mehr an ihm hängt (Auftrag, Projekt mit Auftrag, Wartungsvertrag, Rechnung, Zahlung, Mustervorgang, Adressbuch,
   Vertrag oder Checkliste an seinen Objekten, Vorgang eines anderen Kunden an seinen Objekten) und jeder seiner Vorgänge im Archiv oder mit ihm fällig ist;
   Kunden aus dem Adressimport nie (F6). Seine Objekte gehen mit ihm, ein Objekt allein nie.
6. Ins Archiv bestätigen Admin und Büro – Finanzen (F8): einzeln (ein Kunde nimmt seine fälligen Vorgänge mit) oder gesammelt -- gesammelt nur genau die Liste
   der Vorschau (Prüfsumme), sonst 409 und nichts archiviert. Unter den Sperren neu gerechnet; was nicht mehr fällig ist, bleibt mit Grund.
7. Im Archiv fehlt eine Einheit in Listen, Büro-Suche, Suche der Monteurin, Eingang der Webseite (samt Zählern), Vorschlag und Suche beim Übernehmen, den
   Fotokopien am Objekt und der Wiedervorlage auf „Start“; über die Kennung bleibt sie lesbar. Ein archiviertes Projekt mit Auftrag bleibt in der Suche (wie
   bisher). (Seit 1.10.15–1.10.17 erweitert, Antwort F4 vom 21.11.2026: Büro-Suche, „Neue Anfrage“ sowie Vorschlag und Suche beim Übernehmen zeigen das Archiv
   in einer eigenen Gruppe „im Archiv“, gewählt nur über „Zurückholen und öffnen“ bzw. „… und wählen“; Listen und die Suche der Monteurin bleiben ohne.)
8. Zurückholen darf jedes Büro (F12: „Büro und Admin“); ab dem Zurückholen zählen die 6 Monate neu; Anfrage und Projekt holen ihren Kunden mit; eine Anfrage mit
   Projekt kommt mit ihrem Projekt.
9. An einem Kunden im Archiv entsteht nichts Neues (Anfrage anlegen oder ändern, Projekt anlegen, Wechsel eines Projekts zu ihm: 409; beim Übernehmen wie
   unbekannt); kein Kontaktvermerk und keine Aktion an einem Eingang im Archiv (409). (Bleibt so; seit 1.10.16/1.10.17 bieten „Neue Anfrage“ und das
   Übernehmen davor „Zurückholen und wählen“ an.)
10. Archivieren über das „⋮“ der Akte bleibt bei jedem Büro (wie bisher) und ist dasselbe Archiv: Zeitpunkt und Konto, ohne Auftrag mit Anfrage und Eingang;
    Entarchivieren ist Zurückholen (Kunde mit).
11. Die Historie nennt je Einheit „archiviert“ bzw. „zurückgeholt“ unter der vorhandenen Art, „Archiv: aktiv ↔ im Archiv“, mit der Nummer -- ohne Inhalte.
12. In „Projekt bearbeiten“ und im Objektformular bleibt ein gespeicherter Kunde im Archiv gewählt und gekennzeichnet; neu angeboten werden nur aktive. Die
    Kundenakte zeigt ihre Objekte und Anfragen samt Archiv.
13. Keine Mengenabfrage mit `NOT IN` über eine Spalte, die leer sein darf; ein Test mit NULL in `invoices.customer_id`, `contacts.customer_id`,
    `maintenance_contracts.property_id` und `webanfragen.inquiry_id` (Hinweis des Betriebs).
14. Die Migration hat keinen Bestand; `downgrade()` bricht ab, solange ein Eingang, eine Anfrage oder ein Kunde im Archiv ist.

#### Tests und Prüfung 1.10.11

Neu `tests/test_v782_archiv.py` (27 Tests: Monatsende; Anfrage und Kunde fällig; jüngerer Kontakt aus Vermerk und Besichtigung, künftige Besichtigung zählt
nicht; Eingang der Webseite zählt; Angebot, Entwurf, Termin, Versand, offene Aufgabe, Vorlage; Auftrag auch storniert; Import, Adressbuch, Mustervorgang;
NULL in fremden Spalten; Objekt an fremdem Vorgang; Eingänge samt Spam und ohne Eingangszeit; Rechte je Rolle; einzeln und nicht fällig; Kunde nimmt seine
Vorgänge mit und fehlt in Listen, Suche, Suche der Monteurin und Objektdokumenten; gesammelt nur mit der Prüfsumme; Zurückholen zählt neu und holt den Kunden;
nichts Neues im Archiv; von Hand über die Akte; Historie ohne Inhalte; Eingang im Archiv ohne Liste und Aktion; Migration unter SQLite und PostgreSQL; in node
„Projekt bearbeiten“ und Objektformular mit einem Kunden im Archiv).

Angepasste Erwartungen (Regel 28), nur Aufbau:
- `tests/test_v557_kundenakte_seite.py::_antworten`, `tests/test_v450_auswahl_fremdschluessel.py` (Projektmappe, zwei Stellen), `tests/test_v554_kundenakte_funktionen.py`
  (Belege Objekte und Anfragen) -- die Adressen der Kundenakte und von „Projekt bearbeiten“ tragen jetzt `archivierte=true`.
- `tests/test_v447_auswahl_altwerte.py::KLASSEN` -- die drei Kundenlisten „vollstaendig“ mit neuem Grund (bis 1.10.10: „Kunden kennen kein Archiv“).
- Die Parameter `archivierte` stehen zuletzt in der Signatur (`tests/test_v05_customer_and_quote_calc.py` ruft `list_customers(db)` direkt auf -- zuerst vorn
  gebaut, im Teillauf rot); die Pfad-ID heißt `vorgang_id` (`tests/test_v761_ids_im_pfad.py`, zuerst `kennung`, im Teillauf rot); die Felder der Historie in
  `FIELD_LABELS` (`tests/test_v436_fehlerrunde_vor_stufe_2.py`, im Teillauf rot).
- Migrationsproben älterer Stände (Muster `tests/bestand_alt.py`): `tests/test_v380_nummern_eindeutig.py::_mit_nummer` legt Kunde, Anfrage und Projekt
  als Core-Insert an, `tests/test_v381_zahlungen_migration.py` bucht die eine Zahlung auf dem Stand `3e9b7c41d2a8` als Core-Insert (Zahlung und Zuordnung
  wie `book_payment()`) -- das ORM von heute liest und schreibt die Spalten des Archivs, die es dort nicht gibt (in der vollen Suite 4 rot, danach grün).
- Im ersten vollen Lauf außerdem rot und im Code behoben: `AufbewahrungGesammeltIn.stand` als `Pflichttext` (`tests/test_v756_pflichttext.py`), `order_by`
  an jeder Mengenabfrage in `_kunden()` ohne Spalte, die leer sein darf (`tests/test_v754_reihenfolge.py`), jede dieser Sortierungen auf der ID statt einer
  Vereinigung (`tests/test_v755_kundenliste_und_id.py`, im zweiten vollen Lauf rot), feste Aktion je Aufruf von
  `record_audit_entry()` (`tests/test_v732_lohndatei_vermerk_postgresql.py`).

Gegenproben: `gegenproben-webseite.md`, „W1c, 1.10.11“ (33, alle rot).

### Umsetzung 1.10.12: Seite „Aufbewahrung“ und Erinnerung auf „Start“

- Seite `/aufbewahrung` (`app/templates/aufbewahrung.html`, umgezogen; Büro ab Büro – Auftrag, die Monteurin 403): Reiter „Fällig“ und „Archiv“. „Fällig“:
  Stand („n fällig fürs Archiv seit …, davon m unbearbeitete Eingänge“), Eingänge der Webseite ohne Übernahme für sich, je Kunde eine Karte (Name, Nummer,
  Ort, letzter Kontakt mit Herkunft, „Kunde geht mit“ mit Knopf bzw. „Kunde bleibt: Grund“) mit seinen Vorgängen (Art, Nummer mit Weg, Titel, letzter
  Kontakt und Herkunft, fällig ab, was mitgeht, Sperren, „unbearbeitet“, „Archivieren“ nur an Fälligem). „Alle fälligen archivieren“ mit Rückfrage schickt
  nur die Prüfsumme der Vorschau. „Archiv“: Kunden und Vorgänge mit „im Archiv seit“ und „Zurückholen“. Knöpfe zum Archivieren nur für Admin und
  Büro – Finanzen (`darf_aufbewahrung()`, sonst der Hinweis); jeder Text über `esc()`, die Art nur aus der festen Liste.
- „Start“: Kachel „Aufbewahrung“ direkt unter „Anfragen der Webseite“ (`DEFAULT_WIDGETS`, Rang 13): Zahl der fälligen mit Weg zur Seite, seit wann, davon
  unbearbeitete Eingänge; ohne Fälliges „Nichts fällig fürs Archiv.“ mit Weg ins Archiv. Sie erinnert, bis das Büro bestätigt (F12).
- Kundenakte: „Im Archiv seit … – der Kunde fehlt in Listen, Suche und Auswahlen.“ mit „Zurückholen“ (jedes Büro); Anfragen im Archiv gekennzeichnet.
  Eingang der Webseite: „Im Archiv seit … – zurückholen unter „Aufbewahrung → Archiv“.“, keine Aktion und kein Übernehmen.
- Kein eigener Eintrag in der Leiste: der Weg führt über die Kachel auf „Start“ (dort auch „Archiv ansehen“).
- Nebenbefund behoben: auf „Anfragen der Webseite“ stand die Zahl am Reiter auch bei 0 („0“ am Reiter Eingang bzw. Prüfliste) -- `display:inline-flex`
  der Klasse überstimmte `hidden` (seit 1.10.4). Jetzt `.reiter-zahl[hidden]{display:none}`, auf beiden Seiten; der Klicktest misst die Sichtbarkeit.

#### Festlegungen 1.10.12 (bestätigt am 21.11.2026)

1. Die Seite „Aufbewahrung“ liest jedes Büro; archivieren (einzeln und „Alle fälligen archivieren“) nur Admin und Büro – Finanzen, die anderen sehen den
   Hinweis; zurückholen jedes Büro; die Monteurin bekommt die Seite nicht.
2. „Fällig“ zeigt je Vorgang den letzten Kontakt mit Herkunft, fällig ab, was mitgeht (Angebote, Dateien, Fotos am Objekt), Sperren und „unbearbeitet“;
   „Archivieren“ steht nur an Fälligem, „Kunde … archivieren“ nur, wenn der Kunde mitgeht; sonst steht der Grund, warum er bleibt.
3. „Alle fälligen archivieren“ fragt zurück und gilt nur für die Liste, die die Seite zeigt (Prüfsumme; hat sie sich geändert, 409 und nichts archiviert).
4. Die Kachel „Aufbewahrung“ steht auf „Start“ direkt unter „Anfragen der Webseite“, für jedes Büro; sie nennt die Zahl, seit wann und die unbearbeiteten
   Eingänge, ohne Fälliges den Weg ins Archiv.
5. Kundenakte und Eingang der Webseite sagen „im Archiv seit …“; die Kundenakte holt zurück, der Eingang zeigt im Archiv keine Aktion.
6. Kein eigener Eintrag in der Leiste -- der Weg ist die Kachel auf „Start“. (Seit 1.10.14 überholt, Antwort F1 vom 21.11.2026: „Aufbewahrung“ steht in
   der Leiste unter Verwaltung.)
7. Eine Zahl am Reiter steht nur, wenn sie über 0 ist (Aufbewahrung und Anfragen der Webseite).

#### Tests und Prüfung 1.10.12

Neu `tests/test_v783_aufbewahrung_seite.py` (13 Tests: Seite je Rolle mit und ohne Knöpfe, Monteurin 403; in node „Fällig“ über `esc()`, Knöpfe nur mit Recht und nur an
Fälligem, Stand; Archiv mit „Zurückholen“; Aktionen nur mit fester Art, gesammelt nur mit Prüfsumme; Kachel im Rang und mit und ohne Fälliges; Kundenakte mit
Hinweis und Zurückholen; Eingang im Archiv ohne Aktion). Neuer Klicktest `scripts/klicktest_aufbewahrung.py` (32 Prüfungen: Büro – Auftrag liest ohne
Knöpfe, Kachel auf „Start“, Admin archiviert einzeln, den Kunden und gesammelt mit Rückfrage, ohne Zahl am Reiter, der Eingang der Webseite zählt das Archiv
nicht, Archiv mit Zurückholen, Eingang und Kundenakte im Archiv, 412 px hell und dunkel ohne Überlauf, Monteurin 403; Bilder
`aufbewahrung_faellig_1440_hell`, `aufbewahrung_archiv_1440_hell`, `aufbewahrung_{faellig,archiv}_412_{hell,dunkel}`).

Angepasste Erwartungen (Regel 28), nur Aufbau: `tests/test_v441_rahmen_baustein.py` (`aufbewahrung.html` in `UMGEZOGEN`, Seiten mit Leiste 45 -> 46 an zwei Stellen),
`tests/test_v431_bildgrundlage.py` (Bilder 314 -> 318, die bisherigen 252 -> 256; neue Aufnahme in `scripts/bildgrundlage.py`), `tests/test_v554_kundenakte_funktionen.py`
(neue Funktion „im Archiv“ mit Zurückholen); in der vollen Suite rot, dann nachgezogen: die Standard-Kacheln mit „aufbewahrung“ an dritter Stelle
(`tests/test_v197_dashboard.py`, zwei Tests, alt: my_tasks, webanfragen, open_office_tasks, kpis, active_projects; `tests/test_v322_unassigned_tasks.py`,
ebenso; `scripts/klicktest_aufgaben_ohne_zustaendigkeit.py`, „Dashboard: Widget-Titel“, im Lauf der Klicktests vor dem Commit 23/24, danach grün --
alt ohne „Aufbewahrung“, neu dahinter „Aufbewahrung“ nach „Anfragen der Webseite“). Im Teillauf rot und behoben: ein Satz der Rückfrage las sich als Sie-Anrede („Sie fehlen danach …“,
`tests/test_v440_runde_du.py`) -- jetzt „Die Einträge fehlen danach …“.

Gegenproben: `gegenproben-webseite.md`, „W1c, 1.10.12“ (11 über pytest, eine über den Klicktest, alle rot).

### Umsetzung 1.10.13: verworfene Eingänge löschen

- `app/aufbewahrung.py::zum_loeschen()`: Eingänge, die als Spam, Test oder Doppelt verworfen sind, 6 Monate nach dem Eingang (ohne Eingangszeit nach dem
  Abholen; `LOESCHEN_NACH_MONATEN`) -- nie übernommen, nie mit einem Objektdokument (`NOT EXISTS`; ein Dokument ohne Eingang zählt nicht). „Sonstiges“
  geht ins Archiv wie die übrigen (1.10.11). Die Vorschau nennt sie unter `loeschen` mit `zahl_loeschen` und eigener Prüfsumme `stand_loeschen`.
- `loeschen()`: unter den Sperren neu gerechnet; je Eingang zuerst die Zeilen der Dateien, dann die Zeile (Regel 6), nach dem Commit die Dateien im
  Datenordner; was nicht mehr fällig ist, bleibt mit Grund. Die Historie behält ihre Zeilen von früher (Nummer, Status) und bekommt „gelöscht“ mit der
  Nummer und „verworfen (Grund)“ -- ohne Inhalte. Endgültig, kein Zurückholen. Der Empfangsdienst bekam schon „verworfen“ und löscht selbst nach 180 Tagen.
- `POST /api/aufbewahrung/eingang/{vorgang_id}/loeschen` (einzeln) und `POST /api/aufbewahrung/loeschen` (gesammelt, nur mit `stand_loeschen`, sonst 409) --
  Admin und Büro – Finanzen.
- Seite „Aufbewahrung“: Karte „Zum Löschen“ oben in „Fällig“ (Nummer, Betreff, verworfen als, Eingang, fällig ab, Dateien), „Löschen“ und „Alle löschen“ nur
  mit Recht, mit Rückfrage und als abschließende Aktion (`abschliessen()`, `ABSCHLIESSEND`); Stand und Kachel auf „Start“ nennen „n zum Löschen“.

#### Festlegungen 1.10.13 (bestätigt am 21.11.2026)

1. Gelöscht wird ein Eingang, der als Spam, Test oder Doppelt verworfen ist, 6 Monate nach dem Eingang (ohne Eingangszeit: nach dem Abholen) -- nur nach
   Bestätigung durch Admin oder Büro – Finanzen, einzeln oder gesammelt (nur die Liste der Seite, Prüfsumme).
2. Mit ihm gehen seine Dateien (Zeilen und Dateien im Datenordner); ein Eingang, auf den ein Objektdokument zeigt, oder ein übernommener bleibt.
3. „Sonstiges“ wird nicht gelöscht, sondern geht ins Archiv wie die übrigen Eingänge.
4. Die Historie behält ihre bisherigen Zeilen (Nummer und Status) und bekommt „gelöscht“ mit Nummer und Grund -- ohne Inhalte.
5. Löschen ist endgültig: Rückfrage, abschließende Aktion, kein Zurückholen.
6. Die Vorschau, der Stand der Seite und die Kachel auf „Start“ nennen, was zum Löschen fällig ist.

#### Tests und Prüfung 1.10.13

Neu `tests/test_v784_verworfene_loeschen.py` (9 Tests: was fällig ist -- Spam, Test, Doppelt, ohne Eingangszeit; nicht der junge, nicht „Sonstiges“, nicht der neue,
nicht der mit Objektdokument, ein Dokument ohne Eingang stört nicht; einzeln samt Datei und Historie ohne Inhalt; nicht Fälliges bleibt; gesammelt nur mit der
Prüfsumme; Büro – Auftrag und Monteurin 403; in node „Zum Löschen“ mit und ohne Knöpfe, Löschen mit Rückfrage und Prüfsumme). `scripts/klicktest_aufbewahrung.py`
um den Spam erweitert (35 Prüfungen: Büro – Auftrag sieht „Zum Löschen“ ohne Knöpfe, die Kachel nennt „1 zum Löschen“, der Admin löscht mit Rückfrage, danach
404). Angepasste Erwartungen: `tests/test_v399_abschliessen.py::ABSCHLIESSEND` um `eingangLoeschen` und `alleLoeschen` (Aufbau). Gegenproben:
`gegenproben-webseite.md`, „W1c, 1.10.13“ (11, alle rot).

### Stufe 2: Löschen bzw. Anonymisieren (festgehalten, nicht gebaut -- Vorgabe W1c, Punkt 6)

Fällig frühestens 2030: die Datenschutzerklärung (Paket 2026-11-19a) sagt „löschen drei Jahre nach Ende des Jahres der Archivierung“ -- ein Vorgang, der 2026 ins
Archiv kommt, frühestens am 01.01.2030. Gebaut erst nach dem Rechtsberater.

- **Frist**: 3 Jahre nach Ende des Archivjahres, aber nie vor dem Ende einer gesetzlichen Aufbewahrungsfrist für einen Teil (Befund F12, Abschnitt 3): eine
  Eingangsrechnung an einem Projekt ohne Auftrag ist Buchungsbeleg (8 Jahre ab Ende des Jahres); ein versendetes Angebot je nach Antwort des Rechtsberaters
  (F3 a) keine Pflicht oder 6 Jahre ab Ende des Absendejahres. Gilt eine Frist nur für ein abgelegtes PDF, bleibt nur dieses mit seiner Protokollzeile.
- **Was bleibt je Vorgang (F7)**: Art bzw. Quelle, PLZ (des Objekts, sonst des Kunden), Monat des Eingangs bzw. der Anlage, Ergebnis (verworfen mit Grund,
  verloren, abgelehnt, kein Auftrag). **Keine Nummern** -- sie stehen in Mails im Postfach, die Zeile wäre sonst nur pseudonym. Die Angebotssumme nur als
  **Größenklasse** (Klassen festzulegen, z. B. bis 5.000 €, bis 20.000 €, bis 50.000 €, darüber).
- **Was geht**: Namen, Kontaktdaten, Adressen außer der PLZ, Texte, Umschlag, Dateien (Eingang, Fotokopien am Objekt, Projekt-, Kunden-, Objektdokumente),
  Kalendertermine (mit Löschauftrag an Outlook), Aufgaben, Beteiligte (das Adressbuch bleibt, wenn es anderswo gebraucht wird), Kundenwissen, Kontaktvermerke.
- **Änderungshistorie**: Bezeichnung, alte und neue Werte der betroffenen Zeilen leeren; je Zeile bleiben Art, Zeit, Aktion, Feldname.
- **Versandprotokoll und Ablage (F4 grundsätzlich ja)**: Ausnahme von Regel 21 für Angebote ohne Auftrag nach Ablauf der Frist -- Empfänger, Betreff und PDF
  weg, die Zeile bleibt mit Art, Zeitpunkt und Ergebnis; nur nach Bestätigung.
- **Fristen als Einstellung**: Archiv nach dem letzten Kontakt (heute fest 6 Monate), Löschen verworfener Eingänge (heute fest 6 Monate), Löschen bzw.
  Anonymisieren (3 Jahre nach Ende des Archivjahres), Frist versendeter Angebote -- befüllt erst nach dem Rechtsberater.
- **Bau**: je Art ein Löschweg in fester Reihenfolge (Regel 6, wie E1–E10), ein Wächter, der jede Tabelle mit Bezug zu Kunde, Objekt, Anfrage oder Projekt
  einordnet (geht mit, bleibt, sperrt); Vorschau, Bestätigung (Admin, Büro – Finanzen), Erinnerung auf „Start“ wie in Stufe 1.
- **Betreiber**: Aufbewahrung der Server-Sicherungen auf dem NAS prüfen -- die Daten fallen mit der Aufbewahrung der Sicherungen heraus (Server 14 Tage);
  das gehört in die Datenschutzerklärung.
- **Ansprechpartner vor Ort aus einer Anfrage (Antwort F5 vom 21.11.2026)**: geht eine Anfrage eines Mieters ins Löschen bzw. Anonymisieren, während ihr
  Objekt mit der Hausverwaltung bleibt, leert Stufe 2 Name und Telefon des Ansprechpartners vor Ort am Objekt -- nur, wenn sie aus dieser Anfrage stammen
  (beim Übernehmen gesetzt) und seither unverändert sind; sonst bleibt der Ansprechpartner. Dafür muss das Übernehmen festhalten, was es gesetzt hat (heute
  nicht gespeichert -- Teil des Baus von Stufe 2).
- **Rechtsberater (F3)**: (a) versendete Angebote und Anfragen ohne Auftrag -- Handelsbrief mit 6 Jahren oder keine Pflicht; (c) trägt eine pauschale Frist von
  3 Jahren ohne konkreten Anlass; (d) reicht das Anonymisieren als Löschung (auch mit Sicherungen und Historie); (e) die Datenschutzerklärung nennt dann
  Zweck und Rechtsgrundlage des Anonymisierens.

### Punkt 7: Rohdaten des Adressimports (nur gemeldet, Vorschlag)

`imported_addresses` hält je Zeile des Altsystem-Imports eine vollständige Kopie der Rohdaten (Name, Anschrift, Telefon, Fax, Mobil, zwei Mails, Nummern) --
auf dem Server 345 Zeilen, 186 ohne Kunden. Gebraucht werden sie heute für (1) die Arbeitsliste der nicht zuordenbaren Zeilen (`list_unassigned()`: Kunde
anlegen, als Objekt, verwerfen), (2) die Wiedererkennung beim erneuten Import derselben Datei (`_address_already_imported()` prüft auch bestätigte Rohzeilen
nach der Adressnummer), (3) das Rückgängigmachen eines Importlaufs -- nur, solange nichts daran geändert ist. Die 186 ohne Kunden sind Lieferanten,
Zeilen der Arbeitsliste (offen, als Objekt zugeordnet oder verworfen) oder abgelehnte; welche, zeigt ein Nur-Lese-Befehl (im Bericht). Vorschlag: (a) die
offene Arbeitsliste abarbeiten; (b) danach in allen Rohzeilen die personenbezogenen Spalten leeren und nur Adressnummer, Art, Status, Erledigung und die
Verweise behalten -- das reicht für die Wiedererkennung, das Rückgängigmachen eines alten Laufs entfällt; (c) ist kein Import aus dem Altsystem mehr geplant, die
Rohzeilen ganz löschen. Entscheidung des Betriebs; gebaut als eigene kleine Version mit Vorschau und Bestätigung. Antwort F3 vom 21.11.2026: es kommt noch ein
Import aus dem Altsystem -- (b), gebaut mit 1.10.21 (unten).

### Antworten des Betriebs zum Bericht W1c (21.11.2026)

Festlegungen 1.10.9-1 bis 1.10.13-6 bestätigt. Geprüft auf Nachfrage: „Kontakt vermerken“ startet mit leerem Weg („Bitte wählen“, Festlegung 1.10.10 Nr. 3;
`klicktest_kontakt_vermerken.py` prüft das beim Öffnen) -- im Bild der Akte stand „Telefon“, weil der Klicktest direkt davor einen Tag in der Zukunft mit
„Telefon“ versucht hatte (abgelehnt, die Eingabe bleibt zum Korrigieren stehen). Seit 1.10.14 legt der Klicktest zusätzlich ein Bild des frisch geöffneten
Dialogs ab.

- **F1** ja: „Aufbewahrung“ in die Leiste unter Verwaltung, nur für die Rollen, die die Seite lesen (die Kachel auf „Start“ lässt sich entfernen) -- 1.10.14.
- **F2** ja, ein Commit: das Paar aus den Mustern ist erfunden (00093 -> 00097, über 00299 00350/00360) -- Commit „1.10.13 (Muster)“ vor 1.10.14.
- **F3** offen (Punkt 7: kommt noch ein Import aus dem Altsystem?) -- die Antwort im Bericht war nicht ausgefüllt.
- **F4** ja, weiter gefasst: Archiv heißt „aus dem Alltag raus“, nicht „unauffindbar“ (die Datenschutzerklärung verspricht, eine Anfrage wieder aufzunehmen,
  wenn sich jemand erneut meldet). Büro-Suche, Kundenauswahl bei „Neue Anfrage“ und Übernehmen (Vorschlag und „Anderen bestehenden Kunden wählen“) zeigen
  Kunden und Vorgänge im Archiv in einer eigenen Gruppe „im Archiv“; gewählt wird nur über „zurückholen und wählen“. Listen und die Suche der Monteurin
  bleiben ohne Archiv -- 1.10.15 bis 1.10.17.
- **F5** ja für Stufe 2, nur wenn der Ansprechpartner aus dieser Anfrage stammt und seither unverändert ist (unter „Stufe 2“ festgehalten).
- **F6** so lassen: kein „Kunde archivieren“ im „⋮“ der Kundenakte, ins Archiv nur über „Aufbewahrung“.

### Umsetzung 1.10.14: „Aufbewahrung“ in der Leiste

- `_sidebar.html`: Eintrag „Aufbewahrung“ in der Gruppe Verwaltung zwischen Stammdaten und Einstellungen, für jedes Büro (`sb_buero` -- dieselben Rollen wie
  die Seite, `require_min_role(buero_auftrag)`); die Monteurin hat keine Leiste.
- `aufbewahrung.html` nennt `bereich = "aufbewahrung"` (bis 1.10.13 „anfragen“) -- die Seite markiert ihren eigenen Eintrag.
- Die Kachel auf „Start“ bleibt.
- Leiste bei 1280 × 800 weiter ohne Bildlauf (`klicktest_rahmen.py`, Admin mit allen Modulen: der letzte Eintrag passt mit etwa 1 px) -- ein weiterer Eintrag
  in der Leiste bräuchte eine Entscheidung (kleinere Zeilen, Gruppe einklappen oder Bildlauf zulassen).

#### Festlegungen 1.10.14 (bestätigt am 21.11.2026)

1. „Aufbewahrung“ steht in der Leiste unter Verwaltung zwischen Stammdaten und Einstellungen, für Admin, Büro – Finanzen und Büro – Auftrag; die Monteurin
   sieht ihn nicht.
2. Auf der Seite „Aufbewahrung“ ist „Aufbewahrung“ markiert, nicht mehr „Anfragen“.
3. Die Kachel auf „Start“ bleibt daneben.

#### Tests und Prüfung 1.10.14

Neu `tests/test_v785_aufbewahrung_leiste.py` (8 Tests: je Büro-Rolle der Eintrag unter Verwaltung zwischen Stammdaten und Einstellungen, nicht aktiv, die Seite
öffnet; die Monteurin ohne Eintrag und ohne Seite; die Seite markiert ihren Eintrag; die Kachel auf „Start“ bleibt). Gemessen (Instanz der Bildgrundlage, alle
Module): Luft unter dem letzten Eintrag bei 1280 × 800 1,1 px für Admin und Büro – Finanzen, 73 px für Büro – Auftrag; bei 1440 × 900 101 bzw. 173 px.
`klicktest_kontakt_vermerken.py` legt zusätzlich das Bild des frisch geöffneten Dialogs ab („kontakt_dialog_frisch_1440_hell“). Angepasste Erwartungen (Aufbau):
`tests/test_v253_sidebar_layout.py::test_vier_gruppen_in_reihenfolge` (Verwaltung: stammdaten, einstellungen -> stammdaten, aufbewahrung, einstellungen),
`tests/test_v417_neue_ordnung.py::SEITENLEISTE` und `scripts/klicktest_neue_ordnung.py::SEITENLEISTE_BUERO` (ebenso), `tests/test_v441_rahmen_baustein.py::BEREICHE`
(um „aufbewahrung“). Gegenproben: `gegenproben-webseite.md`, „W1c, 1.10.14“ (4, alle rot).

### Umsetzung 1.10.15: Büro-Suche mit der Gruppe „im Archiv“

- `app/search.py`: die Abfragen der Quellen Kunden, Objekte, Anfragen, Projekte und Angebote stehen je einmal (`_kunden_stmt()`, `_property_search_base_stmt()`,
  `_anfragen_stmt()`, `_projekte_stmt()`, `_angebote_stmt()`) mit dem Archivfilter als Parameter (`_archiv_filter()`, `_projekt_archiv()` -- das Gegenteil von
  `_projekt_nicht_im_archiv()`, nie eine zweite Schreibweise). Die normalen Quellen nehmen sie ohne Archiv wie bisher, die neue Quelle `archiv` („im Archiv“,
  zuletzt in der Registry) mit: Kunden im Archiv, Objekte eines Kunden im Archiv, Anfragen im Archiv, Projekte ohne Auftrag im Archiv und deren Angebote --
  in dieser Reihenfolge, je wie ihre Quelle sortiert, zusammen höchstens `limit`, die Zahl über alle (`_search_archiv()`).
- Jeder Treffer: Art vorn im Untertitel, „im Archiv seit TT.MM.JJJJ“ (Tag in Berlin; ohne Zeitpunkt -- vor 1.10.11 von Hand archiviert -- nur „im Archiv“), beim
  Objekt „Kunde im Archiv seit …“, beim Angebot „Projekt im Archiv seit …“; dazu `zurueckholen_art`/`zurueckholen_id` (`OfficeSearchHitOut`): ein Objekt holt
  seinen Kunden zurück, ein Angebot sein Projekt, eine Anfrage mit Projekt ihr Projekt (wie `app/aufbewahrung.py::zurueckholen()`).
- Ergebnisseite (`search_results.html`): Filter „im Archiv“; die Gruppe hat einen Hinweis und keine Links -- je Treffer „Zurückholen und öffnen“
  (`POST /api/aufbewahrung/{art}/{id}/zurueckholen`, jedes Büro, über `speichern()`; danach die Seite des Treffers). Kopfzeile (`_topbar.html`): keine Treffer aus
  dem Archiv, stattdessen eine Zeile „n Treffer im Archiv“, die die Suche mit Filter „im Archiv“ öffnet.
- Ohne Archiv bleiben: die Suche der Monteurin (`search_properties_for_field()`), die Verknüpfung im Kalender (`types=projects,quotes`), „Beteiligten hinzufügen“
  (`office_source("customers")`) und alle Listen.

#### Festlegungen 1.10.15 (bestätigt am 21.11.2026)

1. Die Büro-Suche zeigt Kunden, Objekte eines Kunden im Archiv, Anfragen, Projekte ohne Auftrag und deren Angebote im Archiv in einer eigenen Gruppe
   „im Archiv“, immer zuletzt, zusammen höchstens so viele wie eine Gruppe; die übrigen Gruppen bleiben ohne Archiv. Eingänge der Webseite sucht die
   Büro-Suche nicht (wie bisher).
2. Ein Treffer im Archiv ist kein Link; geöffnet wird er nur über „Zurückholen und öffnen“ -- jedes Büro, danach zählen die 6 Monate neu. Ein Objekt holt
   seinen Kunden zurück, ein Angebot sein Projekt; die übrigen Vorgänge des Kunden bleiben im Archiv. (Seit 1.10.18 erweitert, Antwort F7: dazu „ansehen“ ohne
   Zurückholen, nur lesen.)
3. Der Treffer nennt die Art und „im Archiv seit TT.MM.JJJJ“ (Tag in Berlin).
4. Die Kopfzeile zeigt keine Treffer aus dem Archiv, nur eine Zeile „n Treffer im Archiv“ in die Suche (Filter „im Archiv“).
5. Ohne Archiv bleiben die Suche der Monteurin, die Verknüpfung im Kalender, „Beteiligten hinzufügen“ und die Listen.

#### Tests und Prüfung 1.10.15

Neu `tests/test_v786_suche_im_archiv.py` (12 Tests: Gruppe zuletzt mit allen fünf Arten und dem, was zurückgeholt wird; übrige Gruppen ohne Archiv; „im Archiv
seit“ als Tag in Berlin (23:30 UTC -> nächster Tag); ohne Zeitpunkt nur „im Archiv“; ein archiviertes Projekt mit Auftrag bleibt unter „Projekte“; Grenze über
alle Arten, Zahl über alle; Typenfilter (Kalender), Suche der Monteurin und „Beteiligten hinzufügen“ ohne Archiv; über die Schnittstelle zurückholen -- danach der
Kunde unter „Kunden“, seine Vorgänge weiter im Archiv; Monteurin 403; in node die Ergebnisseite ohne Link mit „Zurückholen und öffnen“ und der Ablauf
zurückholen -> öffnen; die Kopfzeile mit einer Zeile ins Archiv). Neu `scripts/klicktest_archiv_wiederfinden.py` (20 Prüfungen: Kopfzeile, Suche mit Filter, ohne
Link, 412 px hell und dunkel ohne Überlauf, Zurückholen und öffnen am Objekt, Kundenakte ohne Hinweis, danach die Gruppen; Monteurin 403; Bilder). Angepasste
Erwartungen: `tests/test_v270_office_search.py` (EXPECTED_OFFICE_SEARCH_KEYS um „archiv“, 19 -> 20 Quellen; die Testdaten um einen Kunden im Archiv, damit jede
Gruppe einen Treffer hat; Schlüssel je Treffer: id, title, subtitle, url -- in der Gruppe „im Archiv“ dazu zurueckholen_art/_id, über die Schnittstelle an jedem
Treffer, gesetzt nur dort), `tests/test_v271_office_search_ui.py` (19 -> 20). Gegenproben: `gegenproben-webseite.md`, „W1c, 1.10.15“ (12, alle rot; zwei
zunächst grün, Test nachgezogen).

### Umsetzung 1.10.16: „Neue Anfrage“ mit Kunden im Archiv

- `inquiries.html` lädt die Kunden samt Archiv (`GET /api/customers?archivierte=true`): `customers` sind die aktiven (beide Auswahlen), `kundenArchiv` die im Archiv.
  Die Kundenauswahl von „Neue Anfrage“ zeigt unter den aktiven die Gruppe „im Archiv“ (`<optgroup>`, „Nummer · Name (im Archiv seit TT.MM.JJJJ)“); „Bearbeiten“
  einer Anfrage bleibt ohne Archiv (eine aktive Anfrage hängt nie an einem Kunden im Archiv, 409 seit 1.10.11).
- Wird ein Kunde im Archiv gewählt, springt die Auswahl auf den vorigen Wert zurück, darunter steht „Nummer · Name ist im Archiv seit … – für eine neue Anfrage erst
  zurückholen.“ mit „Zurückholen und wählen“ und „Abbrechen“ (`neuerKundeGewaehlt()`, `archivHinweisZeigen()`). „Zurückholen und wählen“:
  `POST /api/aufbewahrung/kunde/{id}/zurueckholen` (jedes Büro), die Liste neu (`loadAll()`), der Kunde gewählt samt Hauptadresse.
- Kommt die Seite mit `?customer_id=` eines Kunden im Archiv, steht derselbe Hinweis statt der Auswahl.

#### Festlegungen 1.10.16 (bestätigt am 21.11.2026)

1. Die Kundenauswahl von „Neue Anfrage“ zeigt Kunden im Archiv in einer eigenen Gruppe „im Archiv“ unter den aktiven, mit „im Archiv seit …“; „Bearbeiten“ einer
   Anfrage zeigt sie nicht.
2. Ein Kunde im Archiv wird nicht direkt gewählt: die Auswahl springt zurück, darunter „Zurückholen und wählen“ und „Abbrechen“.
3. „Zurückholen und wählen“ holt den Kunden zurück (jedes Büro, die 6 Monate zählen neu) und wählt ihn samt Hauptadresse; seine Vorgänge im Archiv bleiben dort.
4. Kommt „Neue Anfrage“ mit einem Kunden im Archiv (`?customer_id=`), steht der Hinweis statt der Auswahl.
5. Der Server nimmt weiter keine Anfrage an einem Kunden im Archiv (409).

#### Tests und Prüfung 1.10.16

Neu `tests/test_v787_neue_anfrage_archiv.py` (5 Tests: in node die Gruppe nur bei „Neue Anfrage“, über esc(), mit Datum in Berlin; ein Kunde im Archiv wird nicht
gewählt, Hinweis; Abbrechen; Zurückholen und wählen -- POST, Liste neu, gewählt; der Server 409 vor und 200 nach dem Zurückholen). `scripts/klicktest_archiv_wiederfinden.py`
um „Neue Anfrage“ erweitert (32 Prüfungen: Gruppe mit Xaver und Yvonne, „Bearbeiten“ ohne, Auswahl springt zurück, Abbrechen, Zurückholen und wählen samt Hauptadresse,
Anfrage gespeichert, `?customer_id=` mit Hinweis, 412 px hell und dunkel ohne Überlauf, Bilder). Angepasste Erwartungen: keine. Gegenproben: `gegenproben-webseite.md`,
„W1c, 1.10.16“ (6, alle rot).

### Umsetzung 1.10.17: Übernehmen mit Kunden im Archiv

- `app/webanfrage_uebernahme.py::_kunden()` sucht wie bisher nach E-Mail, Telefon, Name (beim Mieter nach dem Namen der Hausverwaltung) und PLZ, teilt die Treffer
  aber in zwei Listen: `kunden` (aktiv, wie bisher) und `kunden_archiv` (im Archiv, dieselben Gründe, je mit `archiviert_am`). `kunden_suche()` liefert neben
  `kunden`/`anzahl` auch `archiv`/`archiv_anzahl` -- dieselbe Suche, nur das Archiv (`app/search.py::kunden_suchen(…, im_archiv=True)`,
  `_search_customers_archiv()` über `_kunden_stmt(term, True)`).
- `webanfrage.html`: unter den Vorschlägen und unter den Treffern der Suche je eine Gruppe „im Archiv“ (Name, Nummer, Adresse, Gründe, „im Archiv seit …“) ohne
  Auswahlknopf, je „Zurückholen und wählen“ (`uebArchivZurueckholen`): `POST /api/aufbewahrung/kunde/{id}/zurueckholen` (jedes Büro), dann Vorschlag und Suche neu
  (`neuLaden`), der Kunde gewählt wie per Klick -- unter den Vorschlägen bzw. den Treffern der Suche, seine Objekte geladen (`uebKundeSetzen()`). Findet die Suche
  keinen aktiven, aber einen im Archiv: „Kein aktiver Kunde gefunden – siehe „im Archiv“.“
- Das Übernehmen und die Objekte eines Kunden nehmen weiter keinen Kunden im Archiv (404, seit 1.10.11).

#### Festlegungen 1.10.17 (bestätigt am 21.11.2026)

1. Der Vorschlag zeigt Kunden im Archiv, die nach denselben Gründen passen, in einer eigenen Gruppe „im Archiv“ unter den Vorschlägen -- ohne Auswahlknopf.
2. „Anderen bestehenden Kunden wählen“ zeigt die Kunden im Archiv, die die Suche findet, ebenso unter den Treffern, mit eigener Zahl.
3. „Zurückholen und wählen“ holt den Kunden zurück (jedes Büro, die 6 Monate zählen neu), liest Vorschlag und Suche neu und wählt ihn dort samt seinen Objekten.
4. Übernehmen nimmt weiter keinen Kunden im Archiv (404) -- gewählt wird nur über „Zurückholen und wählen“.

#### Tests und Prüfung 1.10.17

Neu `tests/test_v788_uebernehmen_archiv.py` (5 Tests: Vorschlag mit der Gruppe „im Archiv“ und ihren Gründen, Objekte und Übernehmen 404 bis zum Zurückholen, danach
unter den Vorschlägen und übernommen; Suche mit `archiv`/`archiv_anzahl`; in node die Gruppen ohne Auswahlknopf, über esc(), mit „im Archiv seit“; ohne Archiv keine
Gruppe; Zurückholen und wählen -- POST vor dem Neulesen, gewählt, Objekte gelesen). `scripts/klicktest_archiv_wiederfinden.py` um das Übernehmen erweitert (40
Prüfungen: Attrappe des Empfangsdienstes, Vorschlag nur „im Archiv“, zurückgeholt und gewählt samt Objekten, Suche ohne aktiven Treffer, zurückgeholt und gewählt
unter den Treffern, 412 px hell und dunkel ohne Überlauf, Bilder). Angepasste Erwartungen: `tests/test_v779_webanfragen_anderer_kunde.py::test_suche_wie_die_buero_suche`
(ein Treffer trägt `archiviert_am`, die leere Antwort `archiv` und `archiv_anzahl` -- Aufbau); `klicktest_archiv_wiederfinden.py` „Neue Anfrage: Gruppe …“ und
„Zurückholen und wählen …“ (seit 1.10.16: Xaver, Yvonne -> neu dazu Viktor, Wilma aus den Testdaten des Übernehmens). Gegenproben: `gegenproben-webseite.md`,
„W1c, 1.10.17“ (7, alle rot).

### Antworten des Betriebs zum Bericht F1/F2/F4 (21.11.2026)

Festlegungen 1.10.14-1 bis 1.10.17-4 bestätigt. F3: es kommt noch ein Import aus dem Altsystem -- also (b): in erledigten Rohzeilen die personenbezogenen
Spalten leeren, Adressnummer, Art, Status, Erledigung und Verweise bleiben; offene Zeilen der Arbeitsliste bleiben unverändert, bis sie erledigt sind; mit
Vorschau und Bestätigung (Admin), eigene kleine Version. F7: Treffer im Archiv zusätzlich „ansehen“ ohne Zurückholen (nur lesen, die 6 Monate laufen nicht
neu). F8: die Felder der Übernahme-Karte angleichen. F9: erst, wenn ein Eintrag in der Leiste ansteht. Dazu klein: beim Übernehmen nicht „Kein bestehender
Kunde passt zu den Angaben“, wenn darunter ein Kunde im Archiv passt.

### Umsetzung 1.10.18: Treffer im Archiv ansehen

- Büro-Suche: je Treffer im Archiv „ansehen“ (Link auf die Seite des Treffers) neben „Zurückholen und öffnen“; der Hinweis der Gruppe sagt, dass „ansehen“ nur
  zum Lesen öffnet und die 6 Monate dabei nicht neu laufen. Die Zeile der Kopfzeile heißt „in der Suche ansehen oder zurückholen“.
- Die Zielseiten sagen „im Archiv“: die Kundenakte (seit 1.10.12, mit „Zurückholen“); die Akte eines Projekts im Archiv (archiviert, ohne Auftrag; „Im Archiv seit
  … – nur zum Ansehen …“ mit „Zurückholen“, `GET /api/projects/{id}` liefert dafür `archiviert_am`); das Objekt eines Kunden im Archiv (Hinweis mit Weg zur
  Kundenakte, `GET /api/properties/{id}` setzt `kunde_im_archiv`); das Angebot eines Projekts im Archiv (Hinweis mit Weg zur Akte, `projekt_im_archiv` an
  `QuoteOut`, `app/projects.py::_projekt_im_archiv()`). Eine Anfrage im Archiv steht nicht in der Pipeline: `/inquiries?inquiry=<id>` zeigt sie als Lese-Ansicht
  oben auf der Seite (Kunde, Objekt, Status, Priorität, Herkunft, Ansprechpartner, Zuständig, Projekt, Notizen -- nur als Text) mit „Zurückholen“, danach im
  Editor; die Kundenakte verlinkt eine Anfrage im Archiv als „im Archiv – ansehen“.
- Ansehen schreibt nichts (jeder Weg ist ein GET, Regel 23) -- `archiviert_am` und `zurueckgeholt_am` bleiben, die 6 Monate laufen nicht neu.
- Nicht geändert: was die Seiten eines Vorgangs im Archiv erlauben. Die Akte zeigt z. B. weiter „Beauftragen“, die Kundenakte „Stammdaten bearbeiten“ -- der
  Hinweis sagt „Zum Weiterarbeiten zurückholen“, sperrt aber nichts (Frage F10 im Bericht).

#### Festlegungen 1.10.18 (bestätigt am 23.11.2026)

1. Jeder Treffer im Archiv hat „ansehen“ (öffnet die Seite des Treffers) und „Zurückholen und öffnen“.
2. Ansehen holt nicht zurück und schreibt nichts -- die 6 Monate laufen dabei nicht neu.
3. Akte, Objekt und Angebot eines Vorgangs im Archiv zeigen den Hinweis „im Archiv“; die Akte holt zurück, Objekt und Angebot verweisen auf Kundenakte bzw. Akte.
4. Eine Anfrage im Archiv zeigt `/inquiries?inquiry=` als Lese-Ansicht (nur Text) mit „Zurückholen“; die Kundenakte verlinkt sie mit „im Archiv – ansehen“.
5. Ein archiviertes Projekt mit Auftrag ist nicht im Archiv der Aufbewahrung -- dort kein Hinweis (wie die Suche seit 1.10.11).

#### Tests und Prüfung 1.10.18

Neu `tests/test_v789_ansehen_im_archiv.py` (6 Tests: Objekt, Akte und Angebot erfahren das Archiv -- ein Projekt mit Auftrag nicht; Ansehen über alle fünf GETs
schreibt nichts; die Seiten haben den Hinweis; in node die Lese-Ansicht der Anfrage nur als Text, nicht für eine aktive, „Zurückholen“ mit POST und Editor).
`scripts/klicktest_archiv_wiederfinden.py` um „ansehen“ erweitert (48 Prüfungen: je Art die Seite mit Hinweis, danach weiter 5 im Archiv; am Ende Zurückholen
aus der Lese-Ansicht). Angepasste Erwartungen: `tests/test_v786_suche_im_archiv.py::test_ergebnisseite_ohne_link_mit_zurueckholen` -> `…_ansehen_und_zurueckholen`
(bis 1.10.17 kein Link im Archiv, jetzt genau „ansehen“ je Treffer; Hinweistext), `klicktest_archiv_wiederfinden` „Suche: … ohne Link“ -> „je „ansehen“ und
„Zurückholen und öffnen““ und „Hinweis zum Archiv“ (neuer Text). Gegenproben: `gegenproben-webseite.md`, „1.10.18“ (9, alle rot).

### Umsetzung 1.10.19: der Satz über der Gruppe „im Archiv“

Beim Übernehmen stand „Kein bestehender Kunde passt zu den Angaben – unten suchen oder einen neuen anlegen.“, auch wenn direkt darunter ein Kunde im Archiv mit
„E-Mail gleich, Name gleich“ passte (Hinweis des Betriebs, 21.11.2026). Jetzt entscheidet `uebKeinerText()` in `webanfrage.html`: passt kein aktiver Kunde,
aber einer im Archiv, heißt es „Kein aktiver Kunde passt – aber einer im Archiv:“ (bei mehreren „– aber n im Archiv:“); passt keiner, bleibt der bisherige Satz;
passt ein aktiver, steht kein Satz.

#### Festlegungen 1.10.19 (bestätigt am 23.11.2026)

1. Passt kein aktiver Kunde, aber einer bzw. mehrere im Archiv: „Kein aktiver Kunde passt – aber einer im Archiv:“ bzw. „– aber n im Archiv:“.
2. Passt keiner, bleibt „Kein bestehender Kunde passt zu den Angaben – unten suchen oder einen neuen anlegen.“; passt ein aktiver, steht kein Satz.

#### Tests und Prüfung 1.10.19

Neu `tests/test_v790_satz_kunde_im_archiv.py` (4 Tests in node: einer, zwei, keiner im Archiv; mit aktivem Vorschlag kein Satz). `klicktest_archiv_wiederfinden.py`
prüft den Satz beim Übernehmen (49 Prüfungen). Angepasste Erwartungen: keine. Gegenproben: `gegenproben-webseite.md`, „1.10.19“ (4, alle rot).

### Umsetzung 1.10.20: Felder der Karte „Als Anfrage übernehmen“

Die Felder der Karte stehen in ihrer Beschriftung (`<label>…<input></label>`) und erbten über `font: inherit` (Grundregel `ds-basis.css`) deren Schrift: 12 px,
fett; Innenabstand und Breite fehlten (seit W1b, 1.10.5/1.10.8; Nebenbefund 2 des Berichts F1/F2/F4). Jetzt tragen alle Felder der Karte (`.ueb`, ohne Optionsfelder
und Häkchen) die Werte der übrigen Formulare wie „Neue Anfrage“: volle Breite, Innenabstand 9/11 px, 13,5 px, Schrift 400, Rahmen, Hover und Fokus. Die Suche
behält ihre Höchstbreite von 420 px.

#### Festlegungen 1.10.20 (bestätigt am 23.11.2026)

1. Die Felder der Karte „Als Anfrage übernehmen“ sehen aus wie die der übrigen Formulare (Werte wie „Neue Anfrage“); Optionsfelder und Häkchen bleiben, wie sie sind.

#### Tests und Prüfung 1.10.20

Neu `tests/test_v791_uebernahme_felder.py` (3 Tests: die Regel mit den Werten von „Neue Anfrage“, Hover und Fokus, Optionsfelder ausgenommen).
`klicktest_archiv_wiederfinden.py` misst fünf Felder (Betreff, Beschreibung, Ansprechpartner, Priorität, Suche): Schrift 400 und 13,5 px, Innenabstand 9/11 px, mindestens
38 px hoch, volle Breite (50 Prüfungen). Angepasste Erwartungen: keine. Gegenproben: `gegenproben-webseite.md`, „1.10.20“.

### Umsetzung 1.10.21: Rohdaten erledigter Zeilen des Adressimports leeren (Antwort F3, Punkt 7)

- `app/address_import.py`: `rohdaten_vorschau()` zählt die erledigten Zeilen mit Rohdaten je Art (bestätigt und nicht offen in der Arbeitsliste: Kunde,
  Lieferant, Arbeitsliste erledigt, bereits importiert, ungültig, abgelehnt), dazu was bleibt (offen in der Arbeitsliste, in der Vorschau, schon leer) und die
  Prüfsumme der Liste; `rohdaten_leeren()` leert unter den Sperren genau diese Zeilen, wenn die Prüfsumme noch stimmt (sonst `RohdatenStandGeaendert`, 409,
  nichts geleert). Geleert werden `ROHDATEN_SPALTEN`: Kunden- und Lieferantennummer aus dem Altsystem, Anrede, Titel, Vorname, Name, Straße, Land, PLZ, Ort,
  Telefon, Fax, Mobil, beide Mails und die Hinweise der Prüfung (sie nennen Werte). Es bleiben Adressnummer, Art, Status, Erledigung samt Zeitpunkt, die Verweise
  auf Kunde, Lieferant und Objekt, Lauf und Zeilennummer -- die Wiedererkennung beim nächsten Import (`_address_already_imported()`) bleibt, ein Lauf lässt sich
  weiter rückgängig machen (er löscht seine Zeilen und, wenn unberührt, seine Kunden und Lieferanten; die brauchen keine Rohdaten). Offene Zeilen der
  Arbeitsliste und eine laufende Vorschau bleiben ganz.
- Geleert wird mit einem UPDATE über genau die Zeilen der Vorschau. `ImportedAddress` steht nicht in `AUDITED_TYPES` (`app/audit.py`) -- die
  Änderungshistorie hält die Rohdaten ohnehin nicht; sie bekommt eine Zeile „Rohdaten geleert“ mit der Zahl, ohne Inhalte.
- `GET /api/address-import/rohdaten` und `POST /api/address-import/rohdaten/leeren` (`{stand}`), nur Admin (wie der ganze Adressimport).
- Seite „Adressimport“: Karte „Rohdaten erledigter Zeilen“ unter den Importläufen -- Zahl je Art, was bleibt, „Rohdaten leeren …“ mit Rückfrage
  (abschließende Aktion), danach die Meldung.

#### Festlegungen 1.10.21 (bestätigt am 23.11.2026)

1. Erledigt ist eine bestätigte Zeile, die nicht offen in der Arbeitsliste steht (Kunde, Lieferant, Arbeitsliste erledigt, bereits importiert, ungültig, abgelehnt).
2. Geleert werden Kunden- und Lieferantennummer aus dem Altsystem, Anrede, Titel, Vorname, Name, Straße, Land, PLZ, Ort, Telefon, Fax, Mobil, beide Mails und die
   Hinweise der Prüfung; es bleiben Adressnummer, Art, Status, Erledigung, Verweise, Lauf und Zeilennummer.
3. Offene Zeilen der Arbeitsliste und eine laufende Vorschau bleiben unverändert; Kunden, Lieferanten und Objekte selbst bleiben, wie sie sind.
4. Vorschau und Bestätigung nur für den Admin; gesammelt nur mit der Prüfsumme der Vorschau (sonst 409, nichts geleert); Rückfrage; endgültig.
5. Die Historie nennt „Rohdaten geleert“ mit der Zahl, ohne Inhalte.
6. Wiedererkennung beim nächsten Import und Rückgängigmachen eines Laufs gehen weiter.

#### Tests und Prüfung 1.10.21

Neu `tests/test_v792_rohdaten_leeren.py` (Vorschau zählt und schreibt nichts; nur erledigte und nur die Rohdaten, Verweise und Erledigung bleiben, offene Zeile und
Vorschau ganz, Kunde und Lieferant unverändert; Wiedererkennung und Suche der Arbeitsliste; Rückgängigmachen danach; Prüfsumme -- nichts geleert; Historie ohne
Inhalte; nur Admin; über die Schnittstelle; in node Vorschau, Rückfrage, POST mit der Prüfsumme, ohne Rohdaten kein Knopf). Neu `scripts/klicktest_rohdaten_leeren.py`
(13 Prüfungen: Vorschau, 412 px hell und dunkel ohne Überlauf, Leeren mit Rückfrage, die offene Zeile bleibt, Büro – Finanzen 403, Bilder). Angepasste
Erwartungen: `tests/test_v399_abschliessen.py::ABSCHLIESSEND` um `rohdatenLeeren` (Aufbau). Gegenproben: `gegenproben-webseite.md`, „1.10.21“ (9, alle rot).

### Antworten des Betriebs zum Bericht F7 (23.11.2026)

Festlegungen 1.10.18-1 bis 1.10.21-6 bestätigt. F10: ja -- Seiten im Archiv nur lesbar: der Server lehnt Änderungen an Vorgängen im Archiv mit 409 ab, die
Seiten blenden die Knöpfe aus (z. B. „Beauftragen“ an der Akte); einzig „Zurückholen“ bleibt; eigene Version. F11: ja, klein (das Feld „Grund“ beim Verwerfen
wie die übrigen Formulare).

### Umsetzung 1.10.22: das Feld „Grund“ beim Verwerfen (Antwort F11)

- `app/templates/webanfrage.html`: das Feld „Grund“ im Bereich „Verwerfen …“ stand wie die Felder der Übernahme-Karte (bis 1.10.20) in seiner Beschriftung und
  erbte deren Schrift (12,5 px, fett), ohne Innenabstand. Jetzt dieselben Werte wie „Neue Anfrage“ und die Übernahme-Karte (volle Breite der Beschriftung,
  Innenabstand 9/11 px, 13,5 px, Schrift 400, Rahmen, Hover, Fokus), dazu mindestens 240 px breit -- es steht in einer Zeile neben „Verwerfen“ und
  „Abbrechen“ und wäre sonst nur so breit wie „Bitte wählen“.

#### Festlegungen 1.10.22 (bestätigt am 23.11.2026)

1. Das Feld „Grund“ beim Verwerfen wie die übrigen Formulare (Werte wie „Neue Anfrage“), mindestens 240 px breit.

#### Tests und Prüfung 1.10.22

`tests/test_v791_uebernahme_felder.py` um `test_grund_beim_verwerfen_wie_die_uebrigen`; `scripts/klicktest_webanfragen.py` misst das Feld (Schrift, Größe,
Innenabstand, Höhe, Breite) und nimmt das Bild `verwerfen_grund_1440_hell` auf (78 -> 79 Prüfungen). Gegenproben: `gegenproben-webseite.md`, „1.10.22“
(5, alle rot).

### Umsetzung 1.10.23: der Server lehnt Änderungen an Vorgängen im Archiv ab (Antwort F10, Teil 1)

- `app/archivschutz.py` (neu). Im Archiv ist ein Kunde oder eine Anfrage mit `archiviert_am` und ein Projekt, das archiviert ist und keinen Auftrag hat -- wie
  die Suche und die Hinweise seit 1.10.18 (ein archiviertes Projekt mit Auftrag ist nicht im Archiv der Aufbewahrung). Der Eingang der Webseite ist seit 1.10.11
  geschützt (jede Aktion ein bedingtes UPDATE) und steht dort nicht. Die Meldung (409): „Das Projekt / Die Anfrage / Der Kunde ist im Archiv – nur zum
  Ansehen. Zum Ändern erst zurückholen.“ -- sind mehrere Wurzeln im Archiv, nennt sie das Projekt vor der Anfrage vor dem Kunden.
- Zum Vorgang gehören (`TEILE`): Kunde mit Profil, Kundenwissen, Dokumenten, Objekten samt Dokumenten, Dachflächen, Schichten und Bauteilen; Projekt mit
  Profil, Dokumenten, Beteiligten und Angeboten samt Positionen, Titeln, Layout, Kalkulation und Mitarbeitern; Anfrage; Kontaktvermerke. Jede Tabelle mit einem
  Fremdschlüssel NOT NULL auf einen Teil ist selbst ein Teil oder steht mit Grund in `KEIN_TEIL` (`tests/test_v793_archivschutz.py`: Aufträge, Zeitbuchungen,
  Wartungsverträge, Zahlungen -- ein Kunde mit Bindung, ein Projekt mit Auftrag sind nie im Archiv).
- Zwei Stufen. **Sitzung**: vor jedem Flush (vor dem Änderungsprotokoll) prüft der Schutz jede neue, geänderte oder gelöschte Zeile eines Teils und jeden neu
  gesetzten Verweis einer anderen Tabelle auf einen Teil (Aufgabe, Termin, Auftrag, Zahlung, Eintrag im Adressbuch, Wartungsvertrag, Checkliste …) -- ein
  schon gesetzter Verweis bleibt änderbar (eine Aufgabe am Projekt im Archiv gehört dem Aufgabenmodul, ein Termin dem Kalender und seinem Abgleich mit Outlook).
  **Vorab**: die Router der Vorgänge (Kunden, Kundendokumente, Objekte, Objektdokumente, Dachflächen, Projekte, Projektdokumente, Beteiligte, Angebote,
  Anfragen, dazu das Hochladen am Objekt in /mobil) prüfen jede schreibende Anfrage, deren Pfad einen Teil im Archiv nennt, vor dem Endpunkt
  (`archiv_vorab()`) -- 409, bevor eine Datei geschrieben oder gelöscht oder eine Mail gesendet ist; das Versandprotokoll (Zustellung nachtragen, Empfang bzw.
  unzustellbar, Klären) ebenso über `pruefen_dokument()`. Die Monteurin bekommt auf Büro-Routen weiter 403 (die Prüfung vorab läuft vor der Rollenprüfung und
  lässt sie aus).
- Einzig das Zurückholen bleibt: an der Wurzel ändern sich dabei nur die Spalten des Archivs (Zurückholen der Aufbewahrung; Archivieren und Entarchivieren im
  „⋮“ der Akte, `ZURUECKHOLEN`). Auch Kopieren, Löschen, Beauftragen, Versenden, Zustellung nachtragen und Kontakt vermerken gehen erst nach dem Zurückholen.
- Auf einem Datenbankstand ohne die Spalten des Archivs (eine Migration der Kette auf einer frischen Datenbank, eine Migrationsprobe) prüft der Schutz nichts --
  einmal je Verbindung nachgesehen. Gefunden in der vollen Suite (`test_v380`, Migrationsprobe auf altem Stand: „Spalte customers.archiviert_am existiert nicht“).
- Die Seiten zeigen bis zu Teil 2 (1.10.24) noch ihre Knöpfe; ein Klick dort bekommt die Meldung.

#### Festlegungen 1.10.23 (bestätigt am 23.11.2026)

1. Im Archiv: Kunde und Anfrage mit `archiviert_am`, Projekt archiviert und ohne Auftrag; ein von Hand archiviertes Projekt ohne Auftrag ist damit auch nur
   lesbar, eines mit Auftrag nicht. Der Eingang der Webseite ist seit 1.10.11 geschützt.
2. Der Server lehnt jede Änderung an einem Vorgang im Archiv mit 409 ab: „… ist im Archiv – nur zum Ansehen. Zum Ändern erst zurückholen.“ (Projekt vor
   Anfrage vor Kunde).
3. Zum Vorgang gehören Kunde, Objekte, Dachflächen, Dokumente, Kundenwissen, Projekt, Angebote, Beteiligte, Anfrage und Kontaktvermerke mit allem, was an ihnen
   hängt (`TEILE`) -- jede neue, geänderte oder gelöschte Zeile.
4. Ein neuer Verweis auf einen Vorgang im Archiv wird abgelehnt (Aufgabe, Termin, Auftrag, Zahlung, Adressbuch, Wartungsvertrag, Checkliste …); was schon auf
   ihn zeigt, bleibt änderbar.
5. Nennt der Pfad einen Vorgang im Archiv, kommt die 409 vor dem Endpunkt -- vor jeder Datei und Mail; die Monteurin bekommt auf Büro-Routen weiter 403.
6. Auch Kopieren, Löschen, Beauftragen, Versenden, Zustellung nachtragen und Kontakt vermerken erst nach dem Zurückholen.
7. Einzig das Zurückholen bleibt (Aufbewahrung; „Entarchivieren“ im „⋮“ der Akte); an der Wurzel ändern sich dabei nur die Spalten des Archivs.
8. Ohne die Spalten des Archivs in der Datenbank prüft der Schutz nichts; eine künftige Migration, die über das ORM einen Teil eines Vorgangs im Archiv ändert,
   scheitert an ihm -- Migrationen schreiben mit Core.

#### Tests und Prüfung 1.10.23

Neu `tests/test_v793_archivschutz.py` (Struktur: jede Tabelle eingeordnet, jede schreibende Route mit Kunde, Objekt, Dachfläche, Projekt, Angebot, Anfrage oder
Beteiligtem im Pfad prüft vorab oder steht mit Grund in `OHNE_VORAB`; 35 Routen 409 und nichts geändert; Hochladen ohne Datei; Versenden ohne Mail; Zustellung
nachtragen; Anlegen aus der Sitzung; vorhandener Verweis änderbar; Monteurin 403; Zurückholen; Archivieren von Hand; Kontakt vermerken mit eigener Meldung; die
Sitzung direkt, auch über die Beziehung) und `tests/test_v794_archiv_rundgang.py` (jede schreibende Route der Anwendung, 495, mit den Kennungen des
Archivs: keine ändert etwas am Archiv, keine neue Datei, kein Versand; jede Route mit Prüfung vorab endet mit der Meldung -- 61 vorab, 4 aus der
Sitzung). Angepasste Testdaten (erst anlegen, dann ins Archiv): `test_v786` (Fixture; „ein Projekt mit Auftrag“: erst Auftrag, dann von Hand archiviert, Kunde
nicht im Archiv), `test_v789` (Fixture), `test_v267` (zwei Testdaten: das Dokument vor dem Archivieren); Klicktests `klicktest_archiv_wiederfinden` und
`klicktest_auswahl_inaktiv` (Seed: erst anlegen bzw. die Aufgabe, dann ins Archiv). Nebenbefund des Rundgangs (nicht geändert, kein Archiv): vier Routen der
Arbeitsvorbereitung (`POST /api/orders/{id}/work-preparation/delivery-notes`, `…/employees`, `…/tasks`, `…/teams`) antworten bei einem unbekannten Auftrag mit
500 statt 404 („Auftrag nicht gefunden.“ als ValueError). Gegenproben: `gegenproben-webseite.md`, „1.10.23“.

### Umsetzung 1.10.24: die Seiten eines Vorgangs im Archiv sind nur lesbar (Antwort F10, Teil 2)

- Neuer Baustein `app/templates/_nur_lesen.html`: `nurLesen(an)` setzt am `<body>` die Klasse `ds-nur-lesen`. Dann fehlt jeder Knopf im Inhalt (`<main>`), in
  Dialogen und Fenstern -- auch das „⋮“ und Links im Aussehen eines Knopfs --, außer Knöpfen mit `data-lesen`; Schließen und Abbrechen eines Dialogs bleiben
  von selbst. Jedes Feld dort ist gesperrt (disabled, Aussehen aus `ds-gesperrt.css`), auch was die Seite danach zeichnet oder wieder freigibt
  (MutationObserver); nichts lässt sich ziehen oder als Datei ablegen; was nur zum Schreiben da ist (Ablage zum Hochladen, „+ Termin“), trägt `data-schreiben`
  und fehlt. `nurLesen(false)` nimmt das zurück -- nach dem Zurückholen ist die Seite ohne Neuladen wieder bearbeitbar.
- Umgekehrt gedacht (Standardverweigerung): ein Knopf bleibt im Archiv nur, wenn er `data-lesen` trägt -- ein neuer Knopf zum Schreiben ist von selbst weg.
  Welche das je Seite sind, steht in `tests/test_v795_nur_lesen.py` (`LESEN`): „Zurückholen“ (Kundenakte, Akte, Eingang der Webseite), Filter und „Ältere
  laden“ im Verlauf und bei den Dokumenten, „Öffnen“ eines Objekts in der Kundenakte, „PDF-Vorschau“ und die Reiter rechts im Angebot. Reiter und Links zum
  Lesen bleiben ohnehin.
- Die Seiten rufen `nurLesen()` nach jedem Laden mit dem Stand des Vorgangs: Kundenakte (`archiviert_am`), Akte (archiviert, ohne Auftrag), Objekt
  (`kunde_im_archiv`), Dachfläche (neu: `kunde_im_archiv` an `GET /api/roof-areas/{id}` und der Hinweis wie am Objekt, mit Weg zur Kundenakte), Angebot
  (`projekt_im_archiv`), Eingang der Webseite (neu: Hinweis „Im Archiv seit … – nur zum Ansehen …“ mit „Zurückholen“ über die Aufbewahrung). Objekt,
  Dachfläche und Angebot holen nicht selbst zurück, ihr Hinweis führt zur Kundenakte bzw. Akte (wie 1.10.18). Der Hinweis der Kundenakte sagt jetzt auch „nur
  zum Ansehen … Zum Weiterarbeiten zurückholen“ (wie die Akte).

#### Festlegungen 1.10.24 (bestätigt am 23.11.2026)

1. Kundenakte, Akte, Objekt, Dachfläche, Angebot und Eingang der Webseite eines Vorgangs im Archiv sind nur lesbar: kein Knopf zum Schreiben (auch kein „⋮“,
   kein Link im Aussehen eines Knopfs, keine Ablage zum Hochladen), jedes Feld gesperrt, nichts zu ziehen.
2. Es bleiben „Zurückholen“, Reiter, Filter, „Ältere laden“, Wege zum Lesen (Öffnen, PDF-Vorschau, die Reiter rechts im Angebot) und Schließen bzw. Abbrechen
   in Dialogen.
3. Ein Knopf bleibt nur mit `data-lesen`; ein neuer Knopf zum Schreiben ist im Archiv von selbst weg.
4. Objekt, Dachfläche und Angebot holen nicht selbst zurück; ihr Hinweis führt zur Kundenakte bzw. Akte. Die Dachfläche bekommt den Hinweis neu.
5. Der Eingang der Webseite im Archiv zeigt den Hinweis mit „Zurückholen“ (wie unter Aufbewahrung, die 6 Monate zählen neu).
6. Nach dem Zurückholen ist die Seite ohne Neuladen wieder bearbeitbar.

#### Tests und Prüfung 1.10.24

Neu `tests/test_v795_nur_lesen.py` (je Seite eingebunden und genau ein Aufruf mit dem Stand des Vorgangs; je Seite genau die lesenden Knöpfe und was nur zum
Schreiben da ist; nur diese Seiten; Regeln des Bausteins; in node: schalten, zweimal derselbe Aufruf tut nichts, Sperren für Ziehen und Ablegen an und ab;
`kunde_im_archiv` an der Dachfläche). Neu `scripts/klicktest_nur_lesen.py` (33 Prüfungen: je Seite und Reiter Klasse, kein Knopf, kein Feld; lesende Knöpfe da;
„⋮“, Hauptaktion und „Angebot beauftragen“ fehlen; Hinweise mit Weg; Ablage zum Hochladen fehlt; keine Zeile des LV ziehbar; 412 px dunkel; Zurückholen an Akte
und Eingang -- alles wieder da, auch am Angebot und am mitgeholten Kunden; Bilder). Angepasste Erwartung: `tests/test_v334_auswahl_restfaelle.py::BAUSTEINE` um
`_nur_lesen.html` (die Attrappe der Seiten bindet ihn ein). Befund (nicht geändert, kein Archiv): die Akte eines Projekts ohne Auftrag läuft bei 412 px über --
die Tabelle „Angebote“ der Übersicht ist 60 px zu breit, mit und ohne Archiv (Frage F12 im Bericht). Gegenproben: `gegenproben-webseite.md`, „1.10.24“.

### Antworten des Betriebs zum Bericht F10 (23.11.2026)

Festlegungen 1.10.22-1 bis 1.10.24-6 bestätigt. F12: ja, klein (die Tabelle „Angebote“ der Akte bei 412 px im Rahmen rollen lassen). F13: ja, klein (die
Routen der Arbeitsvorbereitung antworten bei einem unbekannten Auftrag mit 404 statt 500). Dazu klein: die Kundenakte im Archiv nennt unter „Laufende
Projekte“ ein Projekt im Archiv „Abgeschlossen“ (im Klicktest P-2026-0902, nie ein Auftrag) -- ein Projekt im Archiv dort „Im Archiv“ nennen, nicht
„Abgeschlossen“. Je eine Version.

### Umsetzung 1.10.25: jede Tabelle der Akte rollt in ihrem Rahmen (Antwort F12)

- `app/templates/akte.html`: die Tabelle „Angebote“ der Übersicht (nur ein Projekt ohne Auftrag zeigt sie) stand in einem Element ohne Rahmen -- bei 412 px
  lief die ganze Akte 60 px über, mit und ohne Archiv. Jetzt trägt das Element `tabelle-wrap` wie die Tabelle im Reiter „Angebote“ und die übrigen Tabellen
  der Akte: die Tabelle rollt waagrecht in sich, die Seite nicht.
- Im Rahmen, der rollt, bricht die Nummer eines Angebots nicht mehr um (`td.nw`, Übersicht und Reiter -- beide zeichnen dieselbe Tabelle); bei 412 px stand sie
  bis dahin auf drei Zeilen („A- / 2026- / 0903“). Wie die Nummer der Rechnungsliste (`.rl-num`).

#### Festlegungen 1.10.25 (bestätigt am 23.11.2026)

1. Jede Tabelle der Akte steht in einem Rahmen, der waagrecht rollt (`tabelle-wrap`) -- auch „Angebote“ in der Übersicht eines Projekts ohne Auftrag; bei 412 px
   läuft die Akte nicht über. Eine neue Tabelle der Akte kommt in einen solchen Rahmen (der Test findet jedes Element, in das das Skript eine Tabelle zeichnet).
2. Die Nummer eines Angebots bricht in der Tabelle der Akte (Übersicht und Reiter) nicht um.

#### Tests und Prüfung 1.10.25

Neu `tests/test_v796_tabellen_der_akte.py` (jedes Element, in das das Skript der Akte eine Tabelle zeichnet, trägt `tabelle-wrap` -- gefunden über die Token des
Skripts, heute fünf; die Tabelle „Angebote“ der Übersicht im Rahmen; die Nummer ohne Umbruch). `scripts/klicktest_nur_lesen.py`: die Akte bei 412 px ohne
Überlauf auch im Archiv und neu nach dem Zurückholen, die Tabelle „Angebote“ dort sichtbar im Rahmen, die Nummer in einer Zeile (35 Prüfungen, bisher 33).
Angepasste Erwartung: `klicktest_nur_lesen` „Akte: 412 px ohne Überlauf“ -- bis 1.10.24 nur am Eingang der Webseite geprüft (Befund 1.10.24), jetzt auch an der
Akte. Gegenproben: `gegenproben-webseite.md`, „1.10.25“.

### Umsetzung 1.10.26: die Arbeitsvorbereitung antwortet bei einem unbekannten Auftrag mit 404 (Antwort F13)

- `app/routers/work_preparation.py`: `POST /api/orders/{id}/work-preparation/employees`, `/tasks`, `/teams` und `/delivery-notes` riefen
  `ensure_preparation()` ohne Abfangen auf -- ein unbekannter Auftrag ließ deren `ValueError` („Auftrag nicht gefunden.“) als 500 durch (gefunden im Rundgang
  `tests/test_v794_archiv_rundgang.py`, Befund 1.10.23). Jetzt holt jeder Schreibweg der Datei die Arbeitsvorbereitung über `_vorbereitung()`: dort wird der
  Fehler 404 mit derselben Meldung; nichts wird angelegt, keine Datei geschrieben. Anlegen und Ändern antworteten schon mit 404 und gehen denselben Weg.
- Der Rundgang des Archivs lässt seither keine 500 mehr zu (bis 1.10.25 zählte er sie nur auf).

#### Festlegungen 1.10.26 (bestätigt am 23.11.2026)

1. Ein Schreibweg der Arbeitsvorbereitung mit einem unbekannten Auftrag antwortet mit 404 „Auftrag nicht gefunden.“ und hinterlässt nichts (keine
   Arbeitsvorbereitung, keine Zuordnung, keine Datei).
2. Jeder Schreibweg des Routers holt die Arbeitsvorbereitung über `_vorbereitung()`; `ensure_preparation()` steht dort nur in dieser Funktion.
3. Der Rundgang über alle schreibenden Routen (`test_v794`) verlangt: keine 500.

#### Tests und Prüfung 1.10.26

Neu `tests/test_v797_av_unbekannter_auftrag.py` (je Schreibweg mit dem Auftrag im Pfad -- Mitarbeiter, Aufgabe, Kolonne, Lieferschein, Anlegen, Ändern -- 404
mit Meldung und ohne Spur in sechs Tabellen und der Ablage; dieselbe Anfrage mit dem echten Auftrag 200; per AST `ensure_preparation()` nur in
`_vorbereitung()`). Angepasste Erwartung: `tests/test_v794_archiv_rundgang.py` -- bis 1.10.25 nannte er die 500 nur in der Ausgabe, jetzt `fehler == []`. Kein
Klicktest (keine Seite ruft die Routen mit einem unbekannten Auftrag auf; die Seite der Arbeitsvorbereitung bleibt unverändert). Gegenproben:
`gegenproben-webseite.md`, „1.10.26“.

### Umsetzung 1.10.27: die Kundenakte nennt ein Projekt im Archiv „Im Archiv“, nicht „Abgeschlossen“

- Die Übersicht der Kundenakte zeigt unter „Laufende Projekte“ die laufenden; jedes andere Projekt stand bis 1.10.26 in einer Zeile „Abgeschlossen: …“ -- auch
  ein Projekt im Archiv, das nie einen Auftrag hatte (im Klicktest P-2026-0902).
- `app/kundenakte.py::projekte()` nennt je Projekt `im_archiv`: archiviert und ohne Auftrag, dieselbe Regel wie `app/projects.py::_projekt_im_archiv()` (Akte,
  Angebot, Suche). Die Seite (`customer.html`, `projektKurzliste()`) zeigt darunter zwei Zeilen: „Abgeschlossen: …“ (abgeschlossen, storniert, archiviert mit
  Auftrag) und „Im Archiv: …“ -- je höchstens fünf Projekte, dann „und n weitere“; eine Zeile ohne Projekt fehlt.
- Unverändert: ein archiviertes Projekt mit Auftrag ist nicht im Archiv der Aufbewahrung und bleibt „Abgeschlossen“; das Kennzeichen „archiviert“ an der
  Projektzeile im Reiter „Projekte“ bleibt (wie „· archiviert“ im Kopf der Akte).

#### Festlegungen 1.10.27 (bestätigt am 23.11.2026)

1. Unter „Laufende Projekte“ der Kundenakte steht ein Projekt im Archiv (archiviert, ohne Auftrag) in der Zeile „Im Archiv: …“, nicht unter „Abgeschlossen“.
2. „Im Archiv“ heißt dort dasselbe wie an Akte, Angebot und Suche: archiviert und ohne Auftrag -- ein archiviertes Projekt mit Auftrag bleibt „Abgeschlossen“.
3. Beide Zeilen stehen untereinander, je höchstens fünf Projekte, dann „und n weitere“; eine leere Zeile fehlt.

#### Tests und Prüfung 1.10.27

Neu `tests/test_v798_kundenakte_im_archiv.py` (Server: `im_archiv` nur archiviert und ohne Auftrag; Seite in node mit den Antworten der echten Endpunkte:
„Abgeschlossen“ mit dem archivierten Projekt mit Auftrag, „Im Archiv“ mit dem ohne; nur ein Projekt im Archiv -- nur die Zeile „Im Archiv“; ohne beides keine
Zeile). `scripts/klicktest_nur_lesen.py`: die Kundenakte im Archiv nennt „Kein laufendes Projekt.“ und „Im Archiv: P-2026-0902 Neues Dach“; nach dem Zurückholen
steht das Projekt unter den laufenden, die Zeile fehlt (37 Prüfungen, bisher 35). Unverändert grün: `klicktest_kundenakte` („Abgeschlossen: P-2025-0064 …“, ein
Projekt mit Auftrag). Gegenproben: `gegenproben-webseite.md`, „1.10.27“.

### Antworten des Betriebs zum Bericht F12/F13 (23.11.2026)

Festlegungen 1.10.25-1 bis 1.10.27-3 bestätigt. W1 ist abgeschlossen. Nächste Stufe P1 -- zuerst nur ein Bauplan (Befund Abschnitt 4 und 5, Entscheidungen
oben), dann ein Nachtrag zum Bedrohungsmodell, dann P1a.

## P1: Fundament des Kundenportals (ab 1.11.0)

### Bauplan P1, Nachtrag und Antworten des Betriebs (23.11.2026)

Bauplan `bildgrundlage/bauplan_p1_e8bb2af.txt` und Nachtrag „Portal-Prozess übernommen“ `bildgrundlage/nachtrag_p1_bedrohungsmodell_e8bb2af.txt` (nicht in
Git; seit 23.11.2026 in `C:\DACHKONZEPTE-ERP\Archiv\berichte\`, dort auch der Befund Webseite und der Bericht P1a). Das Tragende:

- **Antworten P1-1 bis P1-15** (alle wie vorgeschlagen): P1-1 Codes über einen Postboten (Dienst unter dem Benutzer des ERP, Auftrag in der Datenbank);
  P1-2 Zugriffsprotokoll 24 Monate; P1-3 Portal-Mails nur über Microsoft 365 (Graph), mit SMTP lehnt das ERP sie ab; P1-4 Zugänge verwalten ab Büro – Auftrag,
  die Monteurin nie, das Modul nur der Admin; P1-5 „neu erzeugen“ beendet alle Sitzungen des Zugangs; P1-6 „Auf allen Geräten abmelden“ schon in P1; P1-7
  Texte der Portal-Mails fest im Code; P1-8 Protokoll von nginx für kunde.… ohne IP-Adresse und ohne Abfrage; P1-9 E4 auch für das ERP belegen (Zählung
  ohne Adressen); P1-10 die Karte „Kundenportal“ im ERP nach dem Muster der Kundenakte, Bilder aller Zustände im Bericht; P1-11 lokale Testrolle
  `dkportal_test` (angelegt: NOLOGIN, `GRANT dkportal_test TO erp WITH INHERIT FALSE, SET TRUE`); P1-12 gunicorn in requirements.txt (P1b); P1-13 Version
  1.11.0 für das neue Modul, Modul „Kundenportal“ ab Werk aus (Notaus); P1-14 Kontakt aus den Firmendaten der Einstellungen; P1-15 ein Zugang je Kunde mit
  eigener E-Mail (vorbelegt mit der des Kunden), mehrere erst mit P5.
- **Nachtrag N1 (Bedrohungsmodell „Portal-Prozess übernommen“):** alles an Link und Sitzung läuft über Funktionen der Datenbank (SECURITY DEFINER, Eigentümer
  der Benutzer des ERP) -- Link öffnen, Code anfordern, Stand des Versands, Code prüfen, Sitzung prüfen, verlängern, abmelden, Willkommen. Der Benutzer des
  Portals hat danach nur EXECUTE darauf und liest sonst nur die Firmendaten und die Revision -- keine Tabelle `portal_*`, kein `customers`. Ohne Link kann ein
  übernommener Prozess keine Sitzung anlegen und keine Namen lesen. Code, Link und Cookie gehen nur als Prüfwert in die Datenbank (SHA-256 mit Zweck, in
  Python gerechnet; der Code nie, auch nicht als Parameter im Log). Zeit nur `now()` der Datenbank. Die Begrüßung als Kopie am Zugang (Punkt a) entfällt;
  ab P2 Lese-Funktionen statt Row-Level-Security und die PDFs über einen Dienst unter dem Benutzer des ERP (die Ablage liegt auf der Platte -- Rechte der
  Datenbank schützen sie nicht). Umgesetzt in P1a als 1.11.1.
- **Ergänzungen:** S0 nennt die Dateien im Repo-Ordner des Servers, die nicht in Git sind (`git status --ignored --short`, nur Namen); jedes Geheimnis außer
  .env kommt vor S6 in InaccessiblePaths (vorgeschlagen zusätzlich: der Dienst sieht nur app/, alembic/, alembic.ini, .venv). S0 belegt, dass der Benutzer des
  ERP kein Superuser ist und weder Rollen anlegen noch Zeilenrechte umgehen darf (rolsuper, rolcreaterole, rolbypassrls = false) -- die Funktionen laufen mit
  seinen Rechten; `scripts/portal_rechte.py --pruefen` meldet es ebenso. Protokolle: nginx täglich gewechselt, 14 alte Dateien (höchstens 15 Tage), das
  Journal 14 Tage.

Was gilt (Kurzfassung des Bauplans):

- **Dienst:** eigene ASGI-App `app/portal` (nur die Wege des Portals, kein Router des ERP), Systembenutzer `dkportal`, gunicorn mit einem Arbeitsprozess auf
  127.0.0.1:8010 hinter nginx unter kunde.dachkonzepte.gmbh, MemoryHigh 200M / MemoryMax 256M, gestartet über `.venv/bin/python -m gunicorn`, eigene
  Umgebung `/etc/dk-portal/portal.env` (DATABASE_URL der Rolle dkportal, ERP_ENV, PORTAL_HERKUNFT, PORTAL_BREMSE_SCHLUESSEL); Start nur, wenn die Revision der
  Datenbank zum Code passt. Das Paket importiert aus dem ERP nur `app.portal`, `app.berlin_time`, `app.design_dateien`.
- **Datenbank-Benutzer `dkportal`:** kein Superuser, legt nichts an, erbt nichts, CONNECTION LIMIT 10, statement_timeout 5 s, idle_in_transaction 15 s,
  pg_hba nur Datenbank dachkonzepte über 127.0.0.1 (jede andere `reject`). Rechte nur aus `app/portal/rechte.py`, gesetzt und geprüft von
  `scripts/portal_rechte.py` als Benutzer des ERP nach jeder Migration (update.sh), nie in einer Migration.
- **Postbote** (`erp-portalpost`, Benutzer des ERP): hört mit LISTEN (NOTIFY nur als Weckruf), erzeugt den Code, speichert nur den Prüfwert, sendet über
  `dispatch_email()` ohne „Gesendete Elemente“ (Betreff fest, ohne Code), prüft die Grenzen ein zweites Mal, räumt auf (Codes 24 Stunden, Sitzungen 30 Tage
  nach dem Ende, Bremsen 48 Stunden, Protokoll 24 Monate) und meldet einen Stau auf „Start“.
- **Sicherheit:** Link 32 Byte im #-Fragment, nur als Prüfwert gespeichert, gültig 12 Monate; ungültig, abgelaufen, gesperrt, aus und Archiv sehen von außen
  gleich aus. Code 6 Ziffern, 10 Minuten, 5 Versuche, nur für die unbestätigte Sitzung, die ihn anforderte. Sitzung im Cookie `__Host-dkportal` (Secure,
  HttpOnly, SameSite=Strict), 30 Tage gleitend über POST (kein GET schreibt), neuer Wert nach dem Code. Bremsen und Protokoll in der Datenbank. CSP ohne
  Inline-Skript, Trusted Types, im Skript des Portals kein innerHTML; Host nur kunde.…, schreibend nur same-origin, Methoden nur GET/HEAD/POST; jede Antwort
  über eine Positivliste; Angriffstests mit allen Methoden, fremder Herkunft, fremden Kennungen.
- **Server-Schritte S0–S10:** S0 Bestand lesen (Speicher, Port, Rechte der Dateien, Versionen, Dateien außerhalb von Git, Log-Einstellungen von PostgreSQL,
  Attribute des Benutzers des ERP); S1 DNS; S2 Systembenutzer; S3 Datenbank-Benutzer (Passwort nie angezeigt, über stdin, log_statement none); S4 Schlüssel der
  Bremsen; S5 Einspielen mit update.sh samt Rechten; S6 systemd; S7 nginx und Zertifikat; S8 Nachweis E4 ohne Adressen; S9 Rauchtest; S10 update.sh für
  zwei Dienste. Befehle je Schritt im Bauplan; ins Archiv mit P1f.
- **Datenschutzerklärung (für den Webseiten-Chat):** Zweck, Rechtsgrundlagen, Daten (Name, E-Mail des Zugangs, Sitzungen, Zugriffsprotokoll, Codes nur als
  Prüfwert, Anschluss nur als HMAC, Protokoll von nginx ohne IP), ein notwendiges Cookie, Mails über Microsoft 365, Fristen (Code 10 Minuten / Prüfwert 24
  Stunden, Sitzung 30 Tage nach letzter Nutzung + 30 Tage, Bremsen 48 Stunden, Zugriffsprotokoll 24 Monate, nginx höchstens 15 Tage, Journal 14 Tage).
  Ergänzt 24.11.2026 (Antwort P1b-1): „Bei technischen Fehlern kann das Fehlerprotokoll des Servers die IP-Adresse enthalten, höchstens 15 Tage.“
- **Runden:** P1a Daten, Rechte, Wächter (1.11.0) und Funktionen der Datenbank (1.11.1); P1b Dienst ohne Oberfläche; P1c Postbote und Mails; P1d Karte
  „Kundenportal“; P1e Seiten nach den Entwürfen des Betriebs; P1f Inbetriebnahme. Für die Stufe 2 der Aufbewahrung vermerkt: die E-Mail am Zugang
  (`portal_zugaenge.email`) gehört zu den Daten, die beim Löschen bzw. Anonymisieren eines Kunden mitgehen.

### Umsetzung 1.11.0: Tabellen und Rechte des Kundenportals (P1a, Teil 1)

- Neue Spalte `customers.portal_aktiv` (Pflicht, Vorgabe aus -- nur als Vorgabe der Datenbank: eine Vorgabe in Python schrieb ein Core-Insert der
  Migrationsproben alter Stände mit, Fund `test_v380` in der vollen Suite; Name in der Änderungshistorie „Kundenportal an“) und sechs Tabellen ohne
  Bestand (Migration `4f8a2c6e1b97`): `portal_zugaenge` (einer je Kunde,
  eigene E-Mail und ihre verdeckte Anzeige, Link nur als Prüfwert, gültig bis, gesperrt mit Grund), `portal_sitzungen` (nur der Prüfwert des Cookies,
  unbestätigt/bestätigt, beendet mit Grund), `portal_codes` (nur Prüfwerte, Versuche), `portal_post` (Aufträge an den Postboten), `portal_zugriffe` (nur
  feste Wörter, ohne Adresse) und `portal_bremsen` (Zähler je Schlüssel und Fenster). Die festen Werte stehen in `app/portal/werte.py`, als CHECK in der
  Datenbank und wörtlich in der Migration.
- `app/portal/rechte.py`: was der Benutzer des Portals darf -- heute nur lesen: `general_settings` (id, Firmenname, Anschrift, Telefon, E-Mail, Webseite) und
  `alembic_version`; Funktionen ab 1.11.1. `setzen()` nimmt jedes andere Recht der Rolle auf Tabellen, Sequenzen und Funktionen des Schemas weg, macht eigene
  Funktionen nicht mehr für alle ausführbar (auch künftige, ALTER DEFAULT PRIVILEGES) und setzt genau diese Rechte, in einer Transaktion; `pruefen()` liest nur
  und meldet jede Abweichung -- auch einen Benutzer des ERP mit Superuser, CREATEROLE oder BYPASSRLS und eine Rolle mit Sonderrechten, Vererbung oder
  Mitgliedschaft. `scripts/portal_rechte.py --setzen | --pruefen` (0 in Ordnung, 1 Abweichung, 2 ohne DATABASE_URL oder ohne PostgreSQL).
- Modul „Kundenportal“ in der Registry, ab Werk aus: `app/modules.py::AB_WERK_AUS` -- ohne Zeile gilt ein solches Modul als aus (bisher hieß „ohne Zeile“
  immer „aktiv“). Ein Admin schaltet es unter Einstellungen → Module ein; die Funktionen der Datenbank (1.11.1) lesen die Zeile genauso.
- Adressimport: ein Zugang zum Portal ist eine Verwendung des Kunden -- ein Lauf mit einem solchen Kunden lässt sich nicht mehr rückgängig machen (sonst
  scheiterte das Löschen des Kunden am Fremdschlüssel).
- Archivschutz: `portal_zugaenge.customer_id` in `KEIN_TEIL` (Sperren geht auch im Archiv; ein neuer Zugang an einem Kunden im Archiv ist ein neuer Verweis
  und wird abgelehnt).

#### Festlegungen 1.11.0 (bestätigt am 23.11.2026)

1. Sechs Tabellen des Portals wie oben; die festen Werte als CHECK in der Datenbank, gleich `app/portal/werte.py` und der Migration.
2. Das Portal ist am Kunden ab Werk aus (`customers.portal_aktiv`, auch für den Bestand).
3. Das Modul „Kundenportal“ ist ab Werk aus -- ohne Zeile aus (`AB_WERK_AUS`); nur ein Admin schaltet es ein.
4. Der Benutzer des Portals darf nur, was `app/portal/rechte.py` nennt: heute nur die acht Spalten der Firmendaten und die Revision lesen; keine Tabelle
   `portal_*`, keine Kundendaten, kein Schreiben.
5. Jede Tabelle ist eingeordnet (`KEIN_ZUGRIFF` in `tests/test_v799_portal_rechte.py`); Konten, Sitzungen, Geheimnisse, Personal, Lohn, Zeiten, Protokolle,
   Kundendaten und die Tabellen des Portals nie zum Lesen (`VERBOTEN`); eine weitere Tabelle zum Lesen nur nach Entscheidung des Betriebs.
6. `scripts/portal_rechte.py --setzen` setzt genau diese Rechte (alles andere fällt weg, eigene Funktionen nicht für alle ausführbar), `--pruefen` meldet jede
   Abweichung samt Benutzer des ERP mit Superuser, CREATEROLE oder BYPASSRLS; Rückgabe 0/1/2.
7. Rechte stehen nie in einer Migration; gesetzt und geprüft nach jeder Migration als Benutzer des ERP (update.sh, ab der Inbetriebnahme, P1f).
8. Das Paket `app/portal` importiert aus dem ERP nur `app.portal`, `app.berlin_time`, `app.design_dateien`.
9. Ein Zugang zum Portal ist eine Verwendung des Kunden: ein Adressimport mit einem solchen Kunden wird nicht rückgängig gemacht.
10. Die Migration lässt sich nicht herabstufen, solange ein Zugang besteht oder ein Kunde das Portal an hat.
11. Der Zugang zählt nicht zum Vorgang des Archivs: Sperren geht im Archiv, ein neuer Zugang an einem Kunden im Archiv wird abgelehnt.

#### Tests und Prüfung 1.11.0

Neu `tests/test_v799_portal_rechte.py` (18): jede Tabelle eingeordnet, VERBOTEN nie lesbar, LESEN genau, Spalten vorhanden, Namen geprüft, CHECK = werte.py =
Migration, Importe des Pakets, Modul ab Werk aus, Portal am Kunden ab Werk aus, Adressimport, Archiv (neuer Zugang abgelehnt, Sperren geht), Skript ohne
Datenbank; gegen PostgreSQL mit der Testrolle `dkportal_test` im Wegwerf-Schema: setzen und prüfen ohne Abweichung (zweimal), unter SET ROLE nur die erlaubten
Spalten, jede Tabelle des Modells mit SELECT * verweigert (42501), Schreiben, Sequenz, eigene Funktion und CREATE verweigert, `pruefen()` meldet acht
eingebaute Abweichungen und `setzen()` räumt sie ab, Rolle fehlt, Tabelle fehlt; die Migration auf einem Bestand unter SQLite und PostgreSQL (Bestand: Portal
aus, CHECK greift, Downgrade bricht mit Zugang und mit Portal an ab, sonst zurück und wieder hinauf). Angepasste Erwartung: `tests/test_v197_module_toggle.py::
test_list_module_states_covers_registry` -- bis 1.10.27 „jedes Modul ohne Zeile aktiv“, jetzt „aktiv außer AB_WERK_AUS“. Aufbau: `test_v364` kennt die fünf
Spalten mit festen Werten, `test_v793` den Zugang in `KEIN_TEIL`, `app/audit.py::FIELD_LABELS` den Namen „Kundenportal an“
(`test_v436`, `test_v438`). Gegenproben: `gegenproben-portal.md`, „1.11.0“.

### Umsetzung 1.11.1: Funktionen der Datenbank für Link und Sitzung (P1a, Teil 2; Nachtrag N1)

- `app/portal/funktionen.py`: acht Funktionen mit SECURITY DEFINER (Eigentümer der Benutzer des ERP) -- `portal_link_oeffnen` (Link prüfen; neues Gerät:
  unbestätigte Sitzung 15 Minuten, sonst „angemeldet“), `portal_code_anfordern` (Auftrag an den Postboten und NOTIFY, frühestens alle 60 Sekunden),
  `portal_post_stand`, `portal_code_pruefen` (5 Versuche; richtig: Sitzung bestätigt, neuer Wert, 30 Tage, Code verbraucht), `portal_sitzung`,
  `portal_sitzung_weiter` (höchstens einmal je Stunde um 30 Tage), `portal_abmelden` (ein Gerät; alle Geräte nur aus einer bestätigten Sitzung),
  `portal_willkommen` (Anrede, Titel, Vor- und Nachname, Name des Kunden der Sitzung) -- und sechs Helfer ohne SECURITY DEFINER (`portal_jetzt`,
  `portal_hash_gueltig`, `portal_bremse`, `portal_protokoll`, `portal_zugang_grund`, `portal_sitzung_id`). Bremsen und Zugriffsprotokoll schreiben die Funktionen.
- Regeln: fester search_path (pg_catalog, Schema der Tabellen, pg_temp; das Schema setzt das Anlegen aus current_schema() ein), kein dynamisches SQL, keine
  für alle ausführbar; Eingaben nur als Prüfwerte (64 Zeichen hexadezimal), sonst „ungueltig“ ohne zu schreiben; Zeit nur `portal_jetzt()`; Sperren Zugang
  (FOR NO KEY UPDATE) -> Sitzung -> Code. Ein Zugang gilt nur mit Link, gültig bis in der Zukunft, nicht gesperrt, Portal am Kunden an, Kunde nicht im Archiv
  und Modul an -- eine fehlende Zeile des Moduls heißt auch hier „aus“ (`AB_WERK_AUS`). Jede bestätigte Sitzung gilt nur, solange das gilt.
- `app/portal/pruefwerte.py`: Prüfwerte in Python -- Link und Cookie SHA-256 mit Zweck, Code SHA-256 über Zweck + Prüfwert der Sitzung + Code (passt nur zu
  seiner Sitzung), Anschluss HMAC-SHA-256 mit dem Schlüssel des Portals; neuer Wert 32 Byte, neuer Code 6 Ziffern.
- `app/portal/rechte.py::FUNKTIONEN` = genau die acht Funktionen; `scripts/portal_rechte.py` setzt und prüft EXECUTE darauf.
- Migration `b5d1e8a3c247` trägt die Anweisungen wörtlich (nur PostgreSQL; unter SQLite nichts); jedes `create_all()` unter PostgreSQL legt sie ebenso an
  (`app/database.py`, wie `telefonbuch()`). Das Portal läuft damit nur gegen PostgreSQL.

#### Festlegungen 1.11.1 (bestätigt am 23.11.2026)

1. Alles an Link und Sitzung läuft über acht Funktionen der Datenbank mit SECURITY DEFINER; der Benutzer des Portals darf nur sie aufrufen, keinen Helfer und
   keine Tabelle.
2. Jede Funktion hat einen festen search_path (pg_catalog, Schema, pg_temp), kein dynamisches SQL und ist nicht für alle ausführbar.
3. In die Datenbank gehen nur Prüfwerte (64 Zeichen hexadezimal) -- Link, Cookie und Code nie; jede andere Eingabe ergibt „ungueltig“ und schreibt nichts.
   Der Prüfwert des Codes hängt an der Sitzung, der Anschluss geht nur als HMAC mit dem Schlüssel des Portals ein.
4. Die Zeit kommt nur aus der Datenbank (`portal_jetzt()`), nie vom Portal.
5. Link öffnen: jeder Grund (unbekannt, gesperrt, abgelaufen oder ohne Link, Portal aus, Archiv, Modul aus) sieht von außen gleich aus und steht unterschieden
   im Protokoll; ein neues Gerät bekommt eine unbestätigte Sitzung für 15 Minuten; eine bestätigte Sitzung desselben Zugangs ist „angemeldet“.
6. Einen Code fordert nur eine unbestätigte, gültige Sitzung an; Auftrag an den Postboten mit NOTIFY nur als Weckruf (ohne Inhalt, erst beim Commit); ein neuer
   frühestens nach 60 Sekunden; Grenzen je Zugang 3 je 15 Minuten und 10 je Tag, je Anschluss 10 je Stunde, gesamt 200 je Stunde.
7. Code prüfen: 5 Versuche je Code (danach gilt auch der richtige nicht mehr); richtig: Sitzung bestätigt, neuer Wert, 30 Tage, Code verbraucht; von zwei
   gleichzeitigen richtigen Eingaben gilt eine.
8. Eine Sitzung gilt nur bestätigt und nur solange der Zugang gilt -- Sperren, Ablauf, Portal aus, Archiv und Modul aus wirken sofort; verlängert wird über
   einen eigenen Aufruf (kein Lesen schreibt), höchstens einmal je Stunde um 30 Tage.
9. Abmelden: ein Gerät immer; alle Geräte nur aus einer bestätigten Sitzung.
10. „Willkommen“ liest Anrede, Titel und Namen nur für den Kunden einer bestätigten Sitzung.
11. Sperren in fester Reihenfolge: Zugang, dann Sitzung, dann Code -- das ERP sperrt beim Sperren und neu Erzeugen ebenso zuerst den Zugang (P1d).
12. Der Text steht im Code und wörtlich in der Migration; eine Änderung braucht eine neue Migration; jedes `create_all()` unter PostgreSQL legt die Funktionen an.
13. Auch in der Datenbank gilt das Modul „Kundenportal“ ohne Zeile als aus.

#### Tests und Prüfung 1.11.1

Neu `tests/test_v800_portal_funktionen.py` (41): ohne Datenbank -- fester search_path, kein dynamisches SQL, kein Prozentzeichen, Zeit nur aus portal_jetzt(),
SECURITY DEFINER genau `rechte.FUNKTIONEN`, jede Funktion für alle entzogen, protokollierte Wörter in `werte.py`, Migration wörtlich, Prüfwerte; gegen
PostgreSQL im Wegwerf-Schema mit Aufrufen als Testrolle `dkportal_test` -- Link öffnen (unbestätigte Sitzung genau 15 Minuten nach der Zeit der Datenbank;
acht Gründe außen gleich, im Protokoll unterschieden; bestätigt angemeldet, fremder Zugang neu; Bremse je Anschluss), Code anfordern (Auftrag, NOTIFY als
Weckruf ohne Inhalt, Stand, 60 Sekunden, Grenze je Zugang, nur unbestätigt und gültig), Code prüfen (fünf falsche mit Rest, danach auch der richtige nicht,
neuer Code richtig, neuer Wert, 30 Tage, verbraucht; abgelaufen; Code einer anderen Sitzung; zwei gleichzeitig: einer), verlängern, abmelden, Willkommen,
fünf Sperren wirken sofort, die Rolle liest keine Tabelle und keinen Helfer (42501) und `pruefen()` ohne Abweichung, sieben Eingaben ohne Prüfwert schreiben
nichts, `create_all()` legt die 14 Funktionen mit festem search_path an, Migration hinauf (keine für alle ausführbar) und herab, unter SQLite ohne Funktionen.
`tests/test_v799_portal_rechte.py` prüft die Rechte jetzt samt EXECUTE. Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.1“.

### Antworten des Betriebs zum Bericht P1a (23.11.2026)

Festlegungen 1.11.0-1 bis 1.11.1-13 bestätigt. Aufräumen: bestätigte Berichte, Bauplan P1, Nachtrag und der Befund Webseite liegen jetzt im Archiv der
Berichte (`C:\DACHKONZEPTE-ERP\Archiv\berichte\`, SHA-256 geprüft) und werden dort gelesen; in `bildgrundlage/` bleiben nur Entwürfe, `lohn/`,
`lohn_echt/` und der jeweils offene Bericht -- so nach jeder Bestätigung, ohne Erwähnung. Dann P1b wie geplant (Portal-Dienst ohne Oberfläche, gunicorn in
requirements.txt).

### Umsetzung 1.11.2: der Portal-Dienst -- Gerüst, Schranke, Startprüfung (P1b, Teil 1)

- `app/portal/main.py::erzeugen()`: eigene FastAPI-App nur mit den Wegen des Portals (`app/portal/routen.py`), ohne Schnittstellen-Doku, ohne create_all() und
  Grunddaten, in der Schranke. Gestartet mit `python -m gunicorn 'app.portal.main:erzeugen()' -w 1 -k uvicorn.workers.UvicornWorker` (ein Arbeitsprozess,
  10 Fäden, Pool 3 + 3 Verbindungen, 10 Sekunden). Startprüfung: nur PostgreSQL, Revision der Datenbank = Kopf der Migrationen aus `alembic/` -- sonst kein
  Start; im Journal „Portal verbunden als <Rolle>, Revision <rev>“.
- `app/portal/einstellungen.py`: nur aus der Umgebung (`DATABASE_URL`, `PORTAL_HERKUNFT`, `PORTAL_BREMSE_SCHLUESSEL`, `ERP_ENV`), streng geprüft; fehlt
  `ERP_ENV`, gilt production; http nur für localhost mit development oder test; keine Meldung nennt einen Wert.
- `app/portal/schranke.py` (ASGI-Hülle um die App -- jede Antwort läuft hindurch, auch die 500 von Starlette): Host nur der eigene (421), Methoden nur GET,
  HEAD, POST (405 mit Allow), Körper höchstens 16 KB (413, auch stückweise ohne Content-Length), schreibend nur same-origin bzw. passende Origin (403);
  an jeder Antwort CSP ohne Inline-Skript mit Trusted Types, kein Einrahmen, nosniff, no-referrer, COOP/CORP, Permissions-Policy, no-store, HSTS außer lokal
  und in Tests. Eine Ausnahme nach der Antwort fängt die Schranke und protokolliert nur ihre Klasse (sonst schriebe uvicorn ihren Text ins Journal).
- Fehler als JSON mit festem Wort (`{"fehler": …}`): 500 ohne Detail, 503 bei leerem Pool, 422 bei falscher Eingabe.
- `app/portal/tabellen.py`: die Core-Tabellen des Dienstes = `rechte.LESEN` (Firmendaten, Revision). `app/portal/datenbank.py`: eigene Engine.
- Öffentliche Wege: `/health` (GET, HEAD -- der Dienst erreicht die Datenbank, sonst 503) und `/api/kontakt` (Firmendaten aus den Einstellungen, P1-14).
- Server-Dateien: `scripts/server/erp-portal.service` (dkportal, nur app/, alembic/, alembic.ini, .venv lesend in /srv/erp-code, ProtectHome=tmpfs,
  ProtectSystem=strict, MemoryHigh 200M, MemoryMax 256M, ohne --forwarded-allow-ips und ohne Zugriffsprotokoll), `scripts/server/nginx-kunde.conf` (E4-
  Kopfzeilen, Begrenzung je Anschluss, Protokoll ohne Adresse und ohne Abfrage, Fehler ab „error“, Meldungen der Begrenzung nicht im Fehlerprotokoll,
  16 KB, Port 80 nur ACME und Umleitung), `scripts/server/portal.env.beispiel` (Muster ohne Werte).
- `requirements.txt`: `gunicorn>=22.0,<24.0` (P1-12; die Version vom Server liest S0 -- liegt sie außerhalb, wird der Bereich angepasst).
- Speichermessung lokal (Windows, Working Set des Prozessbaums nach 50 Anfragen): Portal 90 MB, ERP 189 MB je Prozess -- passt zur Betreiberangabe (ERP
  rund 380 MB mit zwei Prozessen); Grenze des Portals MemoryHigh 200M / MemoryMax 256M.

#### Festlegungen 1.11.2 (bestätigt am 24.11.2026)

1. Der Portal-Dienst ist eine eigene App nur mit den Wegen des Portals; jeder Weg steht in genau einer Liste (öffentlich, Vorstufe, Sitzung); kein Weg des
   ERP, keine Schnittstellen-Doku.
2. Host nur der aus `PORTAL_HERKUNFT`, sonst 421.
3. Methoden nur GET, HEAD und POST, sonst 405.
4. Körper höchstens 16 KB, sonst 413 -- auch ohne Content-Length.
5. Schreibend nur von der eigenen Seite (Sec-Fetch-Site same-origin, sonst Origin gleich der Herkunft), sonst 403.
6. An jeder Antwort die Schutz-Kopfzeilen und no-store; HSTS außer lokal und in Tests.
7. Fehler ohne Detail (500), leerer Pool 503; im Protokoll nur die Klasse einer Ausnahme.
8. Einstellungen nur aus der Umgebung, streng geprüft; fehlt `ERP_ENV`, gilt production; keine Meldung nennt einen Wert.
9. Start nur gegen PostgreSQL und nur, wenn die Revision der Datenbank dem Kopf der Migrationen entspricht; im Journal Rolle und Revision.
10. Ein Arbeitsprozess mit 10 Fäden, Pool 3 + 3 Verbindungen, 10 Sekunden.
11. Der Dienst liest nur seine Core-Tabellen (= `rechte.LESEN`).
12. Öffentlich nur `/health` und `/api/kontakt` (Firmendaten).
13. Server-Dateien: die Einheit (dkportal, nur app/, alembic/, alembic.ini, .venv lesend, Speichergrenzen, ohne --forwarded-allow-ips, ohne
    Zugriffsprotokoll), der nginx-Block (E4, Begrenzung je Anschluss, Protokoll ohne Adresse und ohne Abfrage, Fehlerprotokoll ab „error“ -- dort steht bei
    einem Fehler die Adresse --, 16 KB) und das Muster der Umgebung ohne Werte.
14. gunicorn steht in requirements.txt (Bereich, abgeglichen mit dem Server in S0).

#### Tests und Prüfung 1.11.2

Neu `tests/test_v801_portal_dienst.py` (70): Wege und Listen, jeder Pfad des ERP 404 (über 400), keine Doku, fremder Host (fünf), sieben Methoden auf drei
Pfaden, zehn Fälle der Herkunft, Körper (genau 16 KB, 1 Byte mehr, stückweise, kaputte Länge), Kopfzeilen an jeder Art Antwort, 500 ohne Detail und Protokoll
nur mit Klasse, HSTS je Umgebung, Pool, zehn Fäden, `/health`, `/api/kontakt`, Einstellungen (gut und dreizehn falsche), Startprüfung (SQLite, als Rolle
`dkportal_test` gegen PostgreSQL, Revision weicht ab), Kontakt als Rolle, Core-Tabellen, Einheit, nginx, Muster der Umgebung, requirements; Angriffe mit
rohen Anfragen gegen einen echten uvicorn (h11, httptools): neun Methoden, sechs Pfade, vier Kopf-Varianten -- erreicht nur GET/HEAD auf `/health` und
`/api/kontakt` mit dem eigenen Host. Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.2“.

Die volle Suite fand vor dem Commit einen roten Wächter: `tests/test_v384_pg_nicht_public.py` (Regel 27) las die Parameter von
`test_einstellung_falsch_kein_start_und_kein_wert_in_der_meldung` -- Wörterbücher mit dem Schlüssel `DATABASE_URL` im Dekorator -- als Übergabe an
einen Kindprozess. Einen Kindprozess gibt es dort nicht; der Test nimmt jetzt Paare (Name, Inhalt), der Wächter bleibt unverändert. Beide
Gegenproben zu Nr. 8 danach noch einmal rot.

### Umsetzung 1.11.3: Link, Code und Sitzung im Portal-Dienst (P1b, Teil 2)

- Wege (`app/portal/routen.py`): `POST /api/link` (öffentlich; der Link nur in der Kopfzeile X-Portal-Link -- die Seite liest ihn aus dem #-Fragment),
  Vorstufe `POST /api/code`, `GET /api/code/stand`, `POST /api/code/pruefen` (`{"code": "123456"}`), Sitzung `POST /api/sitzung/weiter`,
  `POST /api/abmelden` (`{"ueberall": false | true}`), `GET /api/willkommen`. Jeder ruft genau eine Funktion der Datenbank aus 1.11.1
  (`app/portal/datenbank.py`: schreibende in einer Transaktion mit Commit, lesende ohne) -- an sie gehen nur Prüfwerte (`app/portal/pruefwerte.py`), nie
  Link, Code oder Wert eines Cookies. Alles Prüfen (Zugang, Sperre, Portal am Kunden, Archiv, Modul, Ablauf, Versuche, Bremsen, Protokoll) bleibt in der
  Datenbank; der Dienst bildet nur die Ergebniswörter auf Antworten ab.
- Cookies: `__Host-dkportal` (bestätigte Sitzung, 30 Tage, bei jeder Verlängerung neu gesetzt) und `__Host-dkportal-code` (unbestätigte Sitzung bis zum
  richtigen Code, 15 Minuten) -- zwei Namen, damit ein angemeldeter Browser beim Öffnen eines anderen Links seine Sitzung bis zum richtigen Code behält.
  Beide Secure, HttpOnly, SameSite=Strict, Path=/, ohne Domain; gesetzt und gelöscht nur in `_setzen()`/`_loeschen()`. Richtiger Code: neuer Wert, das
  Code-Cookie gelöscht, eine frühere Sitzung dieses Browsers endet („abgemeldet“) -- ein Browser, eine Sitzung.
- Antworten: `{"stand": …}` (Link: angemeldet | code_noetig mit verdeckter Adresse | ungueltig; Code: angefordert; Stand: wartet | gesendet | fehler |
  verworfen | keiner; Prüfen: angemeldet | falsch mit Rest | neu_anfordern; Sitzung: angemeldet; Abmelden: abgemeldet), Willkommen
  `{"begruessung": …}`. Ohne gültige Sitzung 401 `{"fehler": "sitzung"}` (ein POST löscht dabei sein Cookie, ein GET setzt keins), Bremse 429
  `{"fehler": "bremse", "minuten": n}` mit Retry-After. Ein Link, der nicht gilt, ist außen dieselbe Antwort, gleich aus welchem Grund.
- `BEHANDELT`: was jede Funktion antworten kann -- ein unbekanntes Wort (Code und Migration auseinander) beantwortet der Dienst mit 500, statt es als etwas
  anderes zu lesen.
- Begrüßung (`app/portal/begruessung.py`, Bauplan D (1)): Herr/Frau mit Titel und Nachname („Guten Tag, Herr Dr. Muster“), Firma mit dem Namen ohne
  Anrede und Titel, sonst (Divers, ohne Anrede) Titel, Vor- und Nachname, ohne Namen der zusammengesetzte Name, sonst „Guten Tag“.
- Anschluss: `request.client.host` -- hinter nginx die rechteste fremde Adresse aus X-Forwarded-For (gunicorn/uvicorn vertrauen der Kopfzeile nur von
  127.0.0.1, E4), als HMAC mit dem Schlüssel der Bremsen.
- `scripts/pruefe_portal_e4.py` (Nachweis E4, S8): zählt die Anschlüsse mit „Link geöffnet“ im laufenden und im vorigen Stundenfenster, nur Zahlen.
  **Abweichung vom Bauplan:** dort „als dkportal“ und „davon die Adresse des Servers: 0“. Seit dem Nachtrag N1 liest dkportal keine Tabelle, und den
  Prüfwert von 127.0.0.1 rechnete nur, wer den Schlüssel der Bremsen hat (er liegt nur in /etc/dk-portal/portal.env). Das Skript läuft deshalb als
  Benutzer des ERP und vergleicht die Zahl der Anschlüsse mit der Zahl der Geräte (zwei Geräte -> 2; sieht das Portal nur nginx -> 1).

#### Festlegungen 1.11.3 (bestätigt am 24.11.2026)

1. Der Link kommt nur per POST in der Kopfzeile X-Portal-Link (fehlt sie oder ist sie länger als 256 Zeichen: 422); an die Datenbank geht nur sein
   Prüfwert. Ein Link, der nicht gilt, ist außen dieselbe Antwort (200, gleicher Text, kein Cookie), gleich aus welchem Grund.
2. Zwei Cookies `__Host-dkportal` (30 Tage, bei jeder Verlängerung neu gesetzt) und `__Host-dkportal-code` (15 Minuten), beide Secure, HttpOnly,
   SameSite=Strict, Path=/, ohne Domain -- auch lokal und in Tests; gesetzt und gelöscht nur an einer Stelle.
3. Richtiger Code: neuer Wert im Cookie, das Code-Cookie gelöscht; eine frühere Sitzung desselben Browsers endet (ein Browser, eine Sitzung).
4. Ohne gültige Sitzung 401 `{"fehler": "sitzung"}`; ein POST löscht dabei sein Cookie, ein GET setzt nie ein Cookie.
5. Eine Bremse antwortet 429 `{"fehler": "bremse", "minuten": n}` mit Retry-After.
6. Code nur als genau sechs Ziffern 0–9 (sonst 422, kein Versuch, keine Anfrage an die Datenbank); `ueberall` nur true oder false.
7. Der Anschluss ist die Adresse der Verbindung nach X-Forwarded-For von 127.0.0.1 (rechteste fremde Adresse), als HMAC; eine vorangestellte Adresse ändert
   nichts.
8. Begrüßung: Herr/Frau mit Titel und Nachname; Firma mit dem Namen ohne Anrede und Titel; sonst Titel, Vor- und Nachname; ohne Namen der zusammengesetzte
   Name, sonst „Guten Tag“.
9. Jede Antwort hat genau die Schlüssel ihres Wegs und Status; kein Weg nimmt eine ID -- der Kunde kommt nur aus der Sitzung.
10. Jedes Ergebniswort jeder Funktion ist im Dienst behandelt (gegen den Text der Funktionen geprüft); ein unbekanntes Wort ist 500.
11. Kein GET schreibt: Lesen nur über Funktionen, die nichts schreiben, ohne Commit, ohne Cookie.
12. Link, Code und Wert eines Cookies stehen nie in einem Protokoll oder einer Antwort (nur in Set-Cookie).
13. Abmelden auf diesem Gerät beendet jede noch nicht beendete Sitzung des Browsers (auch eine, die nicht mehr gilt) samt einer unbestätigten; „auf allen
    Geräten“ nur mit gültiger Sitzung.
14. Die Sitzung verlängert sich höchstens einmal je Stunde, dann auch das Cookie (30 Tage ab jetzt).
15. `scripts/pruefe_portal_e4.py` läuft als Benutzer des ERP und nennt nur Zahlen; statt „davon 127.0.0.1“ der Vergleich mit der Zahl der Geräte.

#### Tests und Prüfung 1.11.3

Neu `tests/test_v802_portal_sitzung.py` (64): ohne Datenbank Begrüßung (elf Fälle), Ergebniswörter gegen den Text der Funktionen, kein Weg mit ID,
Cookies an einer Stelle, Eingaben 422 und ohne Cookie 401 vor der Datenbank (über SQLite, wo es die Funktionen nicht gibt), unbekanntes Wort 500, Prüfskript;
gegen PostgreSQL in einem Schema je Datei (zwischen den Tests geleert), der Dienst als Testrolle `dkportal_test`: ganzer Ablauf mit Protokoll, jeder
ungültige Link gleich, 401 auf jedem Weg der Sitzung (elf Zustände) und der Vorstufe (neun), Code einer anderen Sitzung, fünf Versuche, eine Sitzung je
Browser, abmelden (dieses Gerät, überall, nicht mehr gültig), verlängern, kein GET schreibt, Bremsen, nichts in Protokoll und Antwort (Protokoll auf DEBUG,
auch SQLAlchemy), Anschluss hinter nginx (echter uvicorn mit X-Forwarded-For: 30 Aufrufe mit wechselnder vorangestellter Adresse -> der 31. gebremst, eine
andere Adresse nicht), Angriffe auf die neuen Wege (neun Methoden, sieben Wege, sechs Kopf-Varianten, h11 und httptools: nichts erreicht, kein Protokoll).
Jede Antwort jedes Tests geht durch die Positivliste (`ERWARTET`). Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.3“.

### Antworten des Betriebs zum Bericht P1b (24.11.2026)

Festlegungen 1.11.2-1 bis 1.11.3-15 bestätigt, auch die Abweichung beim Prüfskript für S8 (1.11.3-15: als Benutzer des ERP, Vergleich mit der Zahl der
Geräte). P1b-1 ja: in die Stichpunkte zur Datenschutzerklärung (oben, „Datenschutzerklärung (für den Webseiten-Chat)“). P1b-2: auf dem Server laufen
gunicorn 26.2.0 und uvicorn 0.52.4 -- nicht mit 22–23 pushen; als 1.11.4 requirements.txt genau auf diese Versionen, lokal dieselben, volle Suite und die
Angriffstests des Portals mit echtem uvicorn darauf; für gunicorn 26 ausdrücklich prüfen: Vorgabe von forwarded_allow_ips (nur 127.0.0.1 bzw. ::1, E4), kein
Zugriffsprotokoll ab Werk, UvicornWorker läuft. Danach ohne zu warten P1c.

### Umsetzung 1.11.4: gunicorn und uvicorn in den Versionen des Servers

- `requirements.txt`: `gunicorn==26.2.0` und `uvicorn[standard]==0.52.4` -- genau die Versionen des Servers (ersetzt den Bereich `>=22.0,<24.0` aus 1.11.2,
  Festlegung 1.11.2-14; mit ihm hätte `update.sh` den gunicorn des ERP auf 23 zurückgesetzt). Lokal installiert; die Suite läuft damit.
- Gelesen im Quelltext von gunicorn 26.2.0: `forwarded_allow_ips` hat die Vorgabe `os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1,::1")` (seit gunicorn 22
  mit ::1); `accesslog` die Vorgabe `None` -- ein Zugriffs-Handler entsteht nur mit `--access-logfile`, Syslog oder einer Logkonfiguration
  (`glogging.Logger.setup`, `access_log_enabled`). uvicorn 0.52.4 (`uvicorn/workers.py`): der UvicornWorker übergibt `forwarded_allow_ips` aus gunicorn an
  uvicorn (proxy_headers ab Werk an) und hängt den Logger `uvicorn.access` an die Handler von gunicorn -- ohne Zugriffs-Handler keine Zeile je Anfrage.
  Seit gunicorn 25 gibt es einen eigenen ASGI-Arbeitsprozess (`-k asgi`); Portal und ERP bleiben beim UvicornWorker (uvicorn markiert `uvicorn.workers` als
  veraltet, Ersatz wäre das Paket `uvicorn-worker`) -- ein Wechsel nur für beide gemeinsam.
- gunicorn läuft unter Windows nicht (es braucht fcntl, grp, pwd, fork; WSL ist nicht installiert). Geprüft wird deshalb der echte Weg von gunicorn bis
  zum Arbeitsprozess in einem eigenen Prozess (`tests/gunicorn_wie_auf_dem_server.py`): die Argumente aus ExecStart der Einheit durch den Parser von gunicorn
  (`WSGIApplication`, auch Umgebung und eine gunicorn.conf.py im Arbeitsordner), mit der Umgebung der Einheit (Environment= und das Muster der
  EnvironmentFile, ohne DATABASE_URL), der Logger von gunicorn, die geladene Klasse des Arbeitsprozesses mit denselben Argumenten wie im Hauptprozess; sie
  bedient eine kleine App, die die Adresse der Verbindung zurückgibt, über 127.0.0.1 und ::1. Unter Windows mit leeren Platzhaltern (fcntl, grp, pwd,
  fehlende Signale, AF_UNIX, Herzschlag-Datei, SIGQUIT-Handler) -- nur in diesem Prozess, nie im Testprozess. Den Hauptprozess (fork, Signale) belegt der
  ERP-Dienst auf dem Server mit denselben Versionen; Befehl im Bericht 1.11.4.
- Kommentare in Einheit, nginx-Block, `app/portal/routen.py` und `scripts/pruefe_portal_e4.py`: „vertraut nur 127.0.0.1“ -> „127.0.0.1 und ::1“; der
  Test hinter nginx in test_v802 übergibt uvicorn die Liste wie gunicorn.

#### Festlegungen 1.11.4 (bestätigt am 24.11.2026)

1. requirements.txt nennt gunicorn und uvicorn genau in der Version des Servers (heute 26.2.0 und 0.52.4); die Suite läuft mit genau diesen -- eine andere
   installierte Version ist rot. Ein Wechsel nur zusammen mit dem Server.
2. X-Forwarded-For gilt nur von 127.0.0.1 und ::1 (Vorgabe von gunicorn 26, an uvicorn weitergereicht); weder ExecStart noch die Umgebung der Einheit setzen
   FORWARDED_ALLOW_IPS, GUNICORN_CMD_ARGS oder --forwarded-allow-ips; gebunden ist der Dienst nur an 127.0.0.1.
3. Ab Werk kein Zugriffsprotokoll: kein --access-logfile, kein Syslog, keine Logkonfiguration; uvicorn schreibt in die Handler von gunicorn; Start und Fehler
   gehen ins Fehlerprotokoll (Journal).
4. Arbeitsprozess bleibt uvicorn.workers.UvicornWorker wie im ERP; ein Wechsel (uvicorn-worker oder gunicorn asgi) nur für beide gemeinsam, mit eigener
   Prüfung von E4.
5. Geprüft wird gunicorn in einem eigenen Prozess bis zum Arbeitsprozess, unter Windows mit leeren Platzhaltern nur dort; den Hauptprozess belegt der Server.

#### Tests und Prüfung 1.11.4

Neu `tests/test_v803_gunicorn_server.py` (6): Versionen in requirements.txt und installiert gleich denen des Servers; Umgebung und ExecStart der Einheit
ohne FORWARDED_ALLOW_IPS, GUNICORN_CMD_ARGS und die Optionen für Vertrauen und Protokoll; im eigenen Prozess (`tests/gunicorn_wie_auf_dem_server.py`):
vertraute Adressen in gunicorn und uvicorn genau 127.0.0.1 und ::1, gebunden an 127.0.0.1:8010; kein Zugriffs-Handler, kein Pfad einer Anfrage in der
Ausgabe, Start im Fehlerprotokoll; der UvicornWorker bedient Anfragen -- ohne Kopfzeile die Adresse der Verbindung, mit X-Forwarded-For von 127.0.0.1 und
von ::1 die angehängte Adresse, eine vorangestellte hilft nicht; Platzhalter nur unter Windows. Angepasste Erwartung: test_v801
`test_gunicorn_in_den_abhaengigkeiten` -- alt „eine Zeile beginnt mit gunicorn>=“, neu „eine Zeile beginnt mit gunicorn==“ (die Version selbst prüft
test_v803). Gegenproben: `gegenproben-portal.md`, „1.11.4“.

### Umsetzung 1.11.5: Mails des Kundenportals ohne „Gesendete Elemente“ (P1c, Teil 1)

- Zwei Versandarten ohne Dokument (`app/email_dispatch.py::PORTAL_TYPES`): `portal_link` „Link zum Kundenportal“ (Dokument-Nummer = Zugang, ab P1d) und
  `portal_code` „Anmeldecode des Kundenportals“ (= Auftrag an den Postboten, ab 1.11.6) -- wie die Aufgaben-Benachrichtigung ohne PDF, ohne Ablage, ohne
  Versandergebnis. Im Versandprotokoll stehen Empfänger und der feste Betreff.
- `dispatch_email(…, gesendete_elemente=False)` reicht bis zum Graph-Aufruf durch (`saveToSentItems` "false", wie in der Doku von Microsoft als Text).
  Eine Art des Portals geht nur so, jede andere nur mit Kopie -- sonst ValueError, bevor etwas geschrieben wird. Über SMTP lässt sich „Gesendete Elemente“
  nicht steuern: abgelehnt mit `NUR_MICROSOFT_365` (P1-3), dazu eine zweite Sicherung im SMTP-Versand selbst.
- `app/portal_mails.py`: feste Texte (P1-7), gesiezt (`KUNDENTEXTE` in test_v440), Begrüßung wie im Portal (`app/portal/begruessung.py`), Absender aus den
  Firmendaten der Einstellungen (P1-14); fester Betreff je Art (`BETREFF`, ohne Link und Code); `senden()` ist der einzige Weg -- der Wächter in test_v804
  lässt eine Art des Portals und den Schalter `gesendete_elemente` nur dort zu. Je Art ein Aufruf mit fester Versandart: die Wächter test_v355 (eine
  veränderliche Art könnte eine Aufgaben-Mail sein) und test_v371 (Dokumente mit „Kopie an:“) verlangen eine Konstante -- gefunden von der vollen Suite,
  die erste Fassung gab die Art als Variable weiter; die Wächter blieben unverändert.
- Texte (Kunde „Herr Dr. Muster“; Absender aus den Einstellungen):

      Betreff: Ihr Anmeldecode für das Kundenportal
      Guten Tag, Herr Dr. Muster,

      Ihr Anmeldecode für das Kundenportal:

      123456

      Der Code gilt 10 Minuten und nur in dem Browser, in dem Sie ihn angefordert haben.

      Haben Sie keinen Code angefordert? Dann hat jemand Ihren Link zum Kundenportal geöffnet. Bitte rufen Sie uns an – wir sperren den Link und
      schicken Ihnen einen neuen. Wir fragen Sie nie nach diesem Code oder einem Passwort.

      Mit freundlichen Grüßen

      <Firmenname>
      <Straße>
      <PLZ Ort>
      Telefon <Telefon> · <E-Mail> · <Webseite>

      Betreff: Ihr Zugang zum Kundenportal
      Guten Tag, Herr Dr. Muster,

      über unser Kundenportal erreichen Sie Ihre Unterlagen bei uns. Ihr persönlicher Zugang:

      https://kunde.dachkonzepte.gmbh/#z=…

      Der Link gilt bis 24.11.2027. Beim ersten Öffnen auf einem Gerät schicken wir Ihnen einen Anmeldecode an diese E-Mail-Adresse.

      Bitte geben Sie den Link nicht weiter – er öffnet Ihr Kundenportal. Wir fragen Sie nie nach einem Passwort. Haben Sie diese E-Mail nicht erwartet,
      rufen Sie uns bitte an.

      Mit freundlichen Grüßen
      … (wie oben)

#### Festlegungen 1.11.5 (bestätigt am 24.11.2026 außer Nr. 5 -- geändert: HTML nach dem Entwurf, siehe 1.11.8)

1. Zwei Versandarten des Portals, `portal_link` und `portal_code`, ohne Dokument: kein PDF, keine Ablage, kein Versandergebnis; im Versandprotokoll Empfänger
   und fester Betreff.
2. Mails des Portals gehen nur über `app/portal_mails.py::senden()`, mit dem festen Betreff der Art (ohne Link und Code); keine andere Stelle nimmt eine Art
   des Portals (Wächter).
3. Ohne Kopie in „Gesendete Elemente“ nur die Mails des Portals, alle anderen weiter mit; eine Art des Portals mit Kopie oder eine andere ohne wird
   abgelehnt.
4. Über SMTP lehnt das ERP Mails des Portals ab, bevor etwas geschrieben wird -- mit dem Weg „Einstellungen → E-Mail-Versand auf Microsoft 365“.
5. Texte fest im Code wie oben: gesiezt, Begrüßung wie im Portal, Code bzw. Link allein auf einer Zeile, Sicherheitshinweis, „gilt bis“ als Tag in Berlin,
   Absender aus den Firmendaten (leere Angaben fallen weg). Der Wortlaut ist ein Vorschlag -- Änderungen über eine Version.
6. Link und Code stehen nie im Versandprotokoll, in einem Protokoll oder einer Fehlermeldung; ein gescheiterter Versand nennt nur Klasse und Code des Fehlers.

#### Tests und Prüfung 1.11.5

Neu `tests/test_v804_portal_mails.py` (13): Versandarten und feste Betreffe; Code und Link über die Graph-Attrappe aus test_v321 (die ganze Anfrage:
`saveToSentItems` "false", fester Betreff, ein Empfänger, kein Anhang, Text mit Code bzw. Link; im Protokoll weder Code noch Link); eine andere Mail weiter
mit "true"; SMTP abgelehnt ohne Eintrag und ohne Mail, auch der SMTP-Versand selbst; eine Art des Portals mit Kopie abgelehnt; gescheiterter Versand ohne
Code in Meldung, Protokoll und Versandprotokoll; Texte für Herr, Frau und Firma mit Hinweis, Absender und „gilt bis“ (23:30 UTC = nächster Tag in Berlin);
Absender ohne leere Zeilen; Wächter per AST über app/ und scripts/. Aufbau: `KUNDENTEXTE` in test_v440 kennt `app/portal_mails.py`. Keine angepasste
Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.5“.

### Umsetzung 1.11.6: der Postbote (P1c, Teil 2)

- `app/portal_postbote.py`: `naechster()` erledigt einen wartenden Auftrag aus `portal_post` -- FOR UPDATE SKIP LOCKED, dann Zugang (FOR NO KEY UPDATE) und
  Sitzung (FOR UPDATE) in der Reihenfolge der Funktionen; zweite Prüfung (`_grund()`); Code erzeugen, nur den Prüfwert speichern (frühere Codes der Sitzung
  ersetzt), über `app/portal_mails.py::senden()` schicken; Ergebnis am Auftrag (bedingtes UPDATE aus „wartet“) und im Zugriffsprotokoll
  (`portal_protokoll()`). Zeit nur aus der Datenbank (`portal_jetzt()`). `aufraeumen()` löscht nach den Fristen; `laufen()` ist die Schleife des Dienstes
  (Sperre, LISTEN, Weckruf oder jede Minute, Aufräumen beim Start und stündlich).
- `senden()` committet den Code zusammen mit dem Eintrag „in Arbeit“ im Versandprotokoll vor dem Senden (dispatch_email()). Bricht der Postbote danach ab,
  steht der Auftrag noch auf „wartet“ -- der nächste Lauf findet den Versandschlüssel `portal-code-<Auftrag>` und übernimmt dessen Ergebnis, statt einen
  zweiten Code zu senden.
- `scripts/portal_postbote.py`: nur mit DATABASE_URL für PostgreSQL (sonst 2); baut seine Engine aus genau dieser Zeichenfolge (zwei Verbindungen) --
  nicht `app.database.engine`, die DATABASE_URL noch einmal selbst läse (beim Bau der Gegenproben gefunden: die erste Fassung prüfte die übergebene
  Zeichenfolge, verband sich aber über app.database); läuft schon ein Postbote 3, ein Fehler der Datenbank 1 (systemd startet neu).
- `scripts/server/erp-portalpost.service`: Benutzer des ERP, lädt .env, Type=simple, Restart=always (5 s), MemoryHigh 200M, MemoryMax 256M, TasksMax 32.
- Speicher (lokal, Windows, Working Set nach 20 Aufträgen, zweimal gemessen): Python-Prozess 115 MB, mit dem Startprogramm von .venv 119 MB -- wie im
  Bauplan geschätzt (rund 120 MB), unter MemoryHigh 200M.

#### Festlegungen 1.11.6 (bestätigt am 24.11.2026)

1. Der Postbote ist ein eigener Dienst `erp-portalpost` unter dem Benutzer des ERP (lädt .env, Restart=always, MemoryHigh 200M, MemoryMax 256M), nur mit
   PostgreSQL, mit eigener Verbindung aus der geprüften DATABASE_URL.
2. Genau ein Postbote je Datenbank und Schema (pg_try_advisory_lock); ein zweiter endet mit Rückgabe 3.
3. Geweckt über LISTEN portal_post, sonst jede Minute; die Aufträge der Reihe nach, ein gerade gehaltener wird übersprungen (SKIP LOCKED).
4. Zweite Prüfung vor jedem Code: Auftrag höchstens 10 Minuten alt; Zugang gilt (gesperrt, abgelaufen, Portal aus, Archiv, Modul aus); Sitzung unbestätigt,
   nicht beendet, nicht abgelaufen; Grenzen an den gesendeten Codes (je Zugang 3 je 15 Minuten und 10 je Tag, gesamt 200 je Stunde) -- sonst „verworfen“ mit
   festem Text, kein Code, keine Mail.
5. Der Code: 6 Ziffern, gespeichert nur der Prüfwert, gültig 10 Minuten nach der Zeit der Datenbank; frühere Codes der Sitzung gelten nicht mehr; scheitert
   der Versand, gilt auch der neue nicht (Auftrag „fehler“).
6. Ein Auftrag geht nie zweimal hinaus: Versandschlüssel `portal-code-<Auftrag>`; liegt er schon vor, übernimmt der Postbote dessen Ergebnis (gesendet bzw.
   „Versand hängt“) ohne neuen Code.
7. Zugriffsprotokoll: „code_gesendet“ (ok) bzw. „code_fehler“ mit dem Grund (gesperrt, abgelaufen, portal_aus, archiv, modul_aus, bremse; „ungueltig“ für
   Sitzung, zu alten Auftrag und gescheiterten Versand) -- feste Wörter, keine neue Spalte, kein neuer Wert.
8. Aufräumen beim Start und stündlich: Codes 24 Stunden nach dem Anlegen; Sitzungen 30 Tage nach ihrem Ende (beendet bzw. abgelaufen) samt Codes und
   Aufträgen; Bremsen 48 Stunden nach dem Beginn ihres Fensters; Zugriffsprotokoll nach 24 Monaten. Das Versandprotokoll bleibt (Regel 21).
9. Das Protokoll des Dienstes nennt nur Nummern der Aufträge, Zähler und Namen von Ausnahmen -- nie Code, Link oder Adresse.

#### Tests und Prüfung 1.11.6

Neu `tests/test_v805_portal_postbote.py` (25): gegen PostgreSQL in einem Schema für die Datei, das Portal als Testrolle (Welt aus test_v800), Graph als
Attrappe (test_v804) -- Code geht hinaus und meldet an (ganze Anfrage, Versandprotokoll, 10 Minuten, Code in keiner Tabelle, Protokoll); neuer Code ersetzt
den alten (nur einer gilt); elf Gründe der zweiten Prüfung verwerfen (je Grund das Wort im Protokoll); knapp unter der Grenze geht hinaus; gescheiterter
Versand (Code gilt nicht, kein Code im Protokoll); SMTP (kein Eintrag, kein Code); Abbruch mitten im Versand (in Arbeit, gesendet: nie zweimal); ein
gehaltener Auftrag wird übersprungen; genau ein Postbote und Weckruf über LISTEN (Schleife in einem Faden, zweiter Postbote abgelehnt, Code ohne Warten);
Aufräumen nach den Fristen (Sitzung samt Code und Auftrag, Protokoll ohne Sitzung, Versandprotokoll bleibt); kein Code im Protokoll (mit der Ausgabe von
SQLAlchemy); ohne Datenbank das Skript (nur PostgreSQL) und die Einheit. Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.6“.

### Umsetzung 1.11.7: Stau-Hinweis des Postboten auf „Start“ (P1c, Teil 3)

- `app/portal_postbote.py::stau()`: „wartet“, wenn ein Auftrag länger als 2 Minuten wartet; „fehler“, wenn der zuletzt versuchte Versand scheiterte
  (gesendet oder gescheitert -- ein verworfener Auftrag ist kein Versand und ändert daran nichts); sonst keiner. Feste Texte in `STAU_TEXTE`.
- `app/routers/kundenportal.py` (neu, ab P1d auch die Karte): `GET /api/kundenportal/postbote` ab Büro – Auftrag; Modul „Kundenportal“ aus: 403.
- „Start“ (`dashboard.html`): eine Karte über den Widgets mit dem Text vom Server (nur textContent), gefragt nur mit eingeschaltetem Modul; sonst keine
  Anfrage. Die Monteurin kommt nie auf „Start“ (Weiterleitung auf /mobil).

#### Festlegungen 1.11.7 (Nr. 2 und 4 bestätigt am 24.11.2026; Nr. 1 und 3 geändert, siehe 1.11.9)

1. Der Hinweis erscheint auf „Start“ für Admin, Büro – Finanzen und Büro – Auftrag, über den Widgets, nicht ausblendbar, solange der Stau besteht.
2. „Wartet“: ein Auftrag wartet länger als 2 Minuten. „Fehler“: der zuletzt versuchte Versand scheiterte; ein späterer gesendeter beendet ihn, ein
   verworfener nicht.
3. Feste Texte: „Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – bitte prüfen, ob der Postbote läuft (Dienst
   erp-portalpost).“ und „Kundenportal: Der letzte Anmeldecode ging nicht hinaus – bitte im Versandprotokoll nachsehen.“
4. Nur mit eingeschaltetem Modul: sonst fragt die Seite nicht, und die Schnittstelle antwortet 403.

#### Tests und Prüfung 1.11.7

Neu `tests/test_v806_portal_stau.py` (11): ohne Aufträge keiner; 119 und 121 Sekunden; fünf Folgen erledigter Aufträge; Texte; Schnittstelle ohne und mit
Modul; die Seite fragt nur mit Modul und setzt nur Text. Neu `scripts/klicktest_portal_stau.py`: Modul aus (keine Anfrage), an ohne Aufträge, wartet (Büro –
Finanzen und Büro – Auftrag), gescheitert (hell und dunkel), wieder gut, Monteurin (Weiterleitung, 403). Keine angepasste Erwartung. Gegenproben:
`gegenproben-portal.md`, „1.11.7“.

### Antworten des Betriebs zu den Berichten 1.11.4 und P1c (24.11.2026)

- **Serverprüfung 1.11.4: alles wie erwartet.** ExecStart mit `-w 2 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 --timeout 120`, ohne
  `--forwarded-allow-ips`, `--access-logfile` oder `-c`; EnvironmentFiles nur .env, Zähler 0; im Journal je Arbeitsprozess „Booting worker“ und „Application
  startup complete“; Vorgaben von gunicorn `['127.0.0.1', '::1']` und `None`; FORWARDED_ALLOW_IPS in .env 0; keine gunicorn.conf.py. 4a518bb ist gepusht.
- Bestätigt: 1.11.4-1 bis -5, 1.11.5-1 bis -4, 1.11.5-6, 1.11.6-1 bis -9, 1.11.7-2, 1.11.7-4.
- **Geändert 1.11.5-5 (Mails):** die freigegebenen Entwürfe liegen in `bildgrundlage/entwurf-p1/` (Portal-Mails.dc.html und .png), ihr Wortlaut ist
  verbindlich (die Sicherheitssätze sind eingearbeitet). HTML wie im Entwurf: Name des Betriebs als Text, grüne Linie, Knopf „Kundenportal öffnen“, Code in
  Gruppen „481 207“ (das Portal nimmt ihn mit und ohne Leerzeichen); Tabellen und Stile in den Tags, höchstens 600 px, keine Bilder, keine Schriften, kein CSS,
  nichts von außen. Dazu ein Textteil mit demselben Wortlaut, wenn Graph das ohne eigenen MIME-Bau zulässt, sonst nur HTML. Jeder eingesetzte Wert maskiert;
  der Link nur nach strenger Prüfung (`https://kunde.dachkonzepte.gmbh/#z=<Wert>`) im Knopf; Angriffstest mit `<a href=…>`, `"><script>`, `&` und
  Anführungszeichen im Kundennamen. Telefon, Fußzeile, Impressum und Datenschutz aus den Firmendaten; ohne Telefon fällt nur die Nummer weg, der Satz „rufen
  Sie uns an“ bleibt. Bilder beider Mails in den Bericht.
- **Geändert 1.11.7-1/-3 (Hinweis auf „Start“):** Gestaltung wie die übrigen Warnhinweise, mit Link „Versandprotokoll öffnen“ (gefiltert auf die
  Anmeldecodes). Wartet ein Code, liest das Büro „… wartet seit über 2 Minuten auf den Versand – bitte den Administrator informieren.“; den Dienst
  erp-portalpost nennt der Text nur dem Admin. Versand gescheitert: der Hinweis endet auch, wenn ein Admin auf „Erledigt“ klickt -- Name und Zeit ins
  Protokoll, ein neuer Fehler zeigt ihn wieder (sonst stünde ein alter Fehler bei wenigen Portal-Kunden wochenlang auf „Start“).
- Danach ohne Warten P1d nach Bauplan Abschnitt 4 (P1-10: nach dem Muster der Kundenakte), mit dem Filter „Art“ im Versandprotokoll für die zwei neuen
  Versandarten; Bilder aller Zustände aus Abschnitt 4, Klicktest; ein Bericht je Version.

### Umsetzung 1.11.8: Mails des Kundenportals als HTML nach dem Entwurf (Antwort 1.11.5-5)

- `app/portal_mails.py`: `link_html()` und `code_html()` bauen die Mails nach `bildgrundlage/entwurf-p1/Portal-Mails.dc.html` -- äußere Tabelle in der
  Fläche, innere Tabelle `width="600"` mit `width:100%;max-width:600px` (auf dem Handy so breit wie der Bildschirm), Kopf mit der Wortmarke als Text (erstes Wort
  des Firmennamens fett, der Rest darunter) und der grünen Linie, Knopf als Tabellenzelle, Code in einem Kasten in Gruppen (`code_gruppen()`), Fußzeile aus den
  Firmendaten. Nur Systemschriften (Arial/Helvetica, für den Code Consolas/Courier New), kein `<style>`, keine Bilder, nichts von außen. Jeder eingesetzte Wert
  über `html.escape()`; der Link nur nach `link_pruefen()` -- genau `PORTAL_ADRESSE` + „/#z=“ + 43 Zeichen URL-sicher (die Form von
  `app/portal/pruefwerte.py::neuer_wert()`, seit 1.11.1); `link_adresse()` baut ihn für P1d. Die Meldung einer falschen Form nennt den Link nicht.
- `PORTAL_ADRESSE = "https://kunde.dachkonzepte.gmbh"` steht fest im Code (F1): der Satz „Unser Kundenportal finden Sie immer unter …“ und der Link können so
  nicht auseinanderlaufen; ein Test vergleicht mit `PORTAL_HERKUNFT` in `scripts/server/portal.env.beispiel`.
- Firmendaten (`firma()`): Anschrift „Name · Straße · PLZ Ort“, „Telefon … · Webseite“, darunter Impressum und Datenschutz als `https://<Webseite>/impressum`
  bzw. `/datenschutz` -- so verlinkt die Webseite sie selbst (Paket webseite-2026-11-18a: `/impressum`, `/datenschutz`; Bauplan P1, Abschnitt 5: „Links auf die
  Webseite“). Ein eigenes Feld dafür gibt es in den Firmendaten nicht. Die Webseite zählt nur als Host (auch mit `https://` oder „/“ am Ende eingetragen);
  sonst fehlen Webseite und beide Links. Ohne Telefon fällt nur die Nummer weg („Dann rufen Sie uns bitte an.“, „Rufen Sie uns bitte trotzdem an – wir
  sperren …“).
- **Nur HTML, kein Textteil:** Graph `sendMail` nimmt genau einen Körper (`body` mit `contentType` Text oder HTML); einen Textteil daneben gäbe es nur mit
  einer selbst gebauten MIME-Nachricht. Ob Exchange Online beim Versand selbst einen Textteil ergänzt, lässt sich hier nicht prüfen (nichts gegen den echten
  Mandanten) -- das zeigt der Quelltext einer echten Mail im Rauchtest S9.
- `app/email_dispatch.py::dispatch_email(body_html=…)`: als HTML genau die Mails des Portals und nur als HTML (`NUR_PORTAL_HTML`); alle anderen Mails bleiben
  Text. `app/email_sending.py`: Graph mit `contentType` HTML, SMTP lehnt HTML ab (zweite Sicherung; das Portal sendet ohnehin nur über Microsoft 365).
- Portal: `app/portal/routen.py::CodeIn` entfernt Leerzeichen (auch geschützte und schmale, `CODE_LEERZEICHEN`) aus einer Eingabe bis 20 Zeichen, danach
  genau 6 Ziffern wie bisher. Der Postbote nimmt `code_html()`.

#### Festlegungen 1.11.8 (bestätigt am 24.11.2026)

1. Beide Mails als HTML nach dem Entwurf, Wortlaut wie dort: Tabellen und Stile in den Tags, höchstens 600 px (schmaler Bildschirm: volle Breite), keine
   Bilder, kein `<style>`, nichts von außen; Systemschriften (Arial/Helvetica, Code Consolas/Courier New); Wortmarke = erstes Wort des Firmennamens, darunter
   der Rest.
2. Nur HTML ohne eigenen Textteil (Graph nimmt einen Körper); HTML gehen nur die Mails des Portals, alle anderen bleiben Text; SMTP sendet kein HTML.
3. Jeder eingesetzte Wert maskiert; der Knopf nimmt nur `https://kunde.dachkonzepte.gmbh/#z=<Wert>` mit dem Wert in der Form seit 1.11.1 (43 Zeichen
   URL-sicher, nicht hexadezimal); jede andere Form: nichts versendet, die Meldung nennt den Link nicht.
4. Die Adresse des Portals steht fest im Code (F1), gleich PORTAL_HERKUNFT der Einheit.
5. Fußzeile, Telefon, Impressum und Datenschutz aus den Firmendaten: Impressum und Datenschutz = `https://<Webseite>/impressum` bzw. `/datenschutz`; ohne
   gültige Webseite keine Links; ohne Telefon fällt nur die Nummer weg.
6. Code in Gruppen „481 207“; das Portal nimmt ihn mit und ohne Leerzeichen (auch geschützte), sonst genau 6 Ziffern 0–9.
7. „Gilt bis“ ist der Tag in Berlin (wie 1.11.5).

#### Tests und Prüfung 1.11.8

Neu `tests/test_v807_portal_mails_html.py` (64): Wortlaut beider Mails Absatz für Absatz; ohne Telefon; Webseite in 12 Formen; Absender ohne leere Teile;
Aufbau (Tags, Attribute, Stile, Schriften, Breiten, Links); Angriffe über Kundennamen und Firmendaten; Link in 20 falschen Formen; Link aus `neuer_wert()`;
Adresse wie in der Einheit; HTML nur für das Portal; Graph bekommt genau das HTML; SMTP kein HTML; Code mit Leerzeichen 7 angenommen, 9 abgelehnt.
`tests/test_v802_portal_sitzung.py`: neu `test_pg_code_mit_leerzeichen` (gegen PostgreSQL). Angepasste Erwartungen: `test_v802::test_eingaben_422_vor_der_datenbank`
-- „ 123456“ war 422, ist jetzt eine gültige Eingabe; an seiner Stelle „123<Tab>456“ (422). `test_v804`: Körper „Text“ -> „HTML“, Code als „480 913“, Link als
`href`; die beiden Texttests sind ein Test über die HTML-Fassung (Wortlaut in v807). `test_v805::_code_aus`: Code aus der Zelle „xxx xxx“ statt aus einer
Zeile. `test_v440::KUNDENTEXTE`: `link_html`, `code_html`, `_anrufen`, `_rahmen` statt `schluss`, `link_text`, `code_text`. Gegenproben:
`gegenproben-portal.md`, „1.11.8“. Bilder beider Mails (600 und 412 px, ohne Telefon) im Bericht 1.11.8.

### Umsetzung 1.11.9: Stau-Hinweis wie die übrigen Warnhinweise, mit „Erledigt“ (Antwort 1.11.7-1/-3)

- „Start“ (`dashboard.html`): der Hinweis ist ein Warnhinweis wie `.notice.warning` der Akten und `.archiv-hinweis` (Fläche `--ds-warn-hell`, Rand links 4 px
  `--ds-warn-text`), mit dem Link „Versandprotokoll öffnen“ (`/versandprotokoll?typ=portal_code`) in beiden Zuständen und -- nur für den Admin bei einem
  gescheiterten Versand -- dem Knopf „Erledigt“ (`portalStauErledigen()`, abschließend über `abschliessen()`).
- Text je Rolle (`app/portal_postbote.py::STAU_TEXTE` für das Büro, `STAU_TEXTE_ADMIN`): „… wartet seit über 2 Minuten auf den Versand – bitte den
  Administrator informieren.“; nur der Admin liest „… bitte prüfen, ob der Postbote läuft (Dienst erp-portalpost).“ „Ging nicht hinaus“ ist für alle gleich.
- „Erledigt“ (`erledigen()`, `POST /api/kundenportal/postbote/erledigt`, nur Admin, nur mit Modul): die Seite schickt den Auftrag mit, den sie zeigt
  (`stau_stand()` liefert ihn); ist inzwischen ein anderer der letzte Versand oder wartet einer, 409 und der Hinweis zeigt den neuen Stand. Am Auftrag
  `quittiert_am`, `quittiert_von_user_id`, `quittiert_von_name` (Migration `c8e2f5a1d394`, Bestand leer), in der Änderungshistorie „Versandfehler erledigt“ unter
  der Art „Kundenportal-Versand“ mit Konto und Zeit -- in einer Transaktion. Ein neuer gescheiterter Versand ist ein neuer Auftrag ohne Vermerk: der Hinweis
  ist wieder da; ein späterer gesendeter beendet ihn wie bisher.
- Versandprotokoll: der Filter „Art“ kennt „Link zum Kundenportal“ und „Anmeldecode des Kundenportals“, nur mit eingeschaltetem Modul (für P1d vorgezogen --
  der Link des Hinweises braucht ihn).

#### Festlegungen 1.11.9 (bestätigt am 24.11.2026)

1. Der Hinweis ist ein Warnhinweis wie die übrigen (Fläche und Rand der Warnfarbe), mit dem Link „Versandprotokoll öffnen“ auf die Anmeldecodes -- in beiden
   Zuständen.
2. „Wartet“: das Büro liest „… – bitte den Administrator informieren.“, nur der Admin den Satz mit dem Dienst erp-portalpost; „ging nicht hinaus“ für alle
   gleich.
3. „Erledigt“ nur der Admin, nur an einem gescheiterten Versand und nur an dem, den der Hinweis zeigt (sonst 409); bei „wartet“ gibt es kein „Erledigt“.
4. Erledigt: Name und Zeit am Auftrag und in der Änderungshistorie („Versandfehler erledigt“, Art „Kundenportal-Versand“); der Hinweis endet; ein neuer
   Fehler zeigt ihn wieder, ein späterer gesendeter beendet ihn wie bisher.
5. Der Filter „Art“ im Versandprotokoll kennt die beiden Arten des Portals, nur mit eingeschaltetem Modul.
6. Migration `c8e2f5a1d394`: drei leere Spalten an `portal_post`, der Bestand bleibt leer (ein alter Fehler zeigt den Hinweis, bis er erledigt ist oder ein
   Versand gelingt); `downgrade()` nimmt sie weg.

#### Tests und Prüfung 1.11.9

Neu `tests/test_v808_portal_stau_erledigt.py` (9): Texte je Rolle; Erledigt beendet den Hinweis, ein neuer Fehler zeigt ihn wieder, ein gesendeter beendet ihn;
nur am gezeigten Fehler (zwei Fehler, zweimal, unbekannt, gesendet); bei „wartet“ nicht; Schnittstelle je Rolle (Text, „erledigen“, 403 für Büro – Auftrag und
Büro – Finanzen, 409, Antwort, Änderungshistorie); nur mit Modul; die Seite (Warnhinweis, Link, Knopf, abschließend); Filter im Versandprotokoll; die Migration
gegen das Modell (vor und zurück). Migration zusätzlich von Hand unter SQLite und PostgreSQL (Wegwerf-Schema): ganze Kette, Abgleich mit dem Modell ohne
Abweichung, `downgrade -1`, wieder `upgrade head`. `scripts/klicktest_portal_stau.py` neu gefasst (42 Prüfungen: Texte je Rolle, Gestalt, Link mit Filter,
„Erledigt“ mit Historie, neuer Fehler, Monteurin 403 auch für „Erledigt“). Angepasste Erwartungen: `test_v806::test_schnittstelle_nur_mit_modul` -- Antwort
`{stau, text}` -> `{stau, text, post_id, erledigen}`; `klicktest_portal_stau` -- Text „wartet“ für Büro – Finanzen bis 1.11.8 mit dem Dienst, jetzt „bitte den
Administrator informieren“; Bilder `stau_wartet`, `stau_gescheitert_light/dark` -> `stau_wartet_buero`, `stau_wartet_admin`, `stau_gescheitert_admin_light/dark`.
Neue Einträge: `test_v373::GEPRUEFT` (post_id), `test_v399::ABSCHLIESSEND` (`portalStauErledigen`). Gegenproben: `gegenproben-portal.md`, „1.11.9“.

### Umsetzung 1.11.10: Kundenportal am Kunden -- Schalter, Zugang, Link, Sperren, Protokoll (P1d, Teil 1)

- `app/kundenportal.py` (neu): `stand()` (alles, was die Karte zeigt; liest nur), `schalten()`, `zugang_anlegen()`, `link_senden()`, `sperren()`,
  `entsperren()`, `verlaengern()`, `protokoll()`. Router `app/routers/kundenportal.py`: `GET /api/customers/{id}/portal`, `POST …/schalter`, `…/zugang`, `…/link`,
  `…/sperren`, `…/entsperren`, `…/verlaengern`, `GET …/protokoll?seite=`; ab Büro – Auftrag, die Monteurin nie, ohne Modul 403, unbekannter Kunde 404. Jeder Weg
  nennt nur den Kunden im Pfad -- den Zugang findet der Server über den Kunden (Regel 25: keine ID eines Zugangs aus der Anfrage). Jede Aktion antwortet mit
  dem neuen Stand.
- Zustände (`zustand()`): im Archiv, aus, ohne E-Mail, kein Zugang, ohne Link, aktiv, läuft bald ab (höchstens 30 Tage), abgelaufen, gesperrt; „Versand
  gescheitert“ als Hinweis aus dem letzten Versand des Links (Versandprotokoll, Art `portal_link`, Dokument = Zugang).
- Link senden: neuer Wert (`pruefwerte.neuer_wert()`) nur in der Mail, gespeichert sein Prüfwert; gültig 12 Kalendermonate (29.02. -> 28.02.); ein zweiter Link
  ist „neu erzeugen“ -- der alte gilt nicht mehr, alle Sitzungen enden (`neu_erzeugt`); die E-Mail ändert sich nur beim Senden (P1-15: wirkt ab diesem Link,
  auch für die Codes). Derselbe Klick (`dispatch_key`) erzeugt nichts; lehnt der Versand vor dem Eintrag im Versandprotokoll ab (SMTP, Adresse), bleibt alles,
  wie es war (ausdrückliches Rollback); scheitert erst der Versand, gilt der neue Link und die Karte zeigt „Versand gescheitert“.
- Sperren mit Grund (Pflicht) beendet alle Sitzungen (`gesperrt`), Portal aus ebenso (`portal_aus`); gesperrt: kein neuer Link, kein Verlängern; Entsperren:
  der bisherige Link gilt wieder bis zu seinem Ablauf. Verlängern: derselbe Link, gültig bis = jetzt + 12 Monate.
- Kunde im Archiv: Zustand „Im Archiv“ (dort wirkt kein Zugang), jede Aktion 409 -- am Router (`archiv_vorab()`) und in der Geschäftslogik. Festlegung 1.11.0
  („Sperren muss auch im Archiv gehen“) meinte die Daten: der Archivschutz hält das Sperren nicht auf (`KEIN_TEIL`); die Karte folgt Bauplan Abschnitt 4 (nur
  lesbar).
- Änderungshistorie: `PortalZugang` in `AUDITED_TYPES` („Zugang zum Kundenportal“), ohne Prüfwert des Links, verdeckte Anzeige und „zuletzt genutzt“
  (`STILL_JE_ART`); Feldnamen in `FIELD_LABELS`. Protokoll: Zugriffe des Portals (Aktion und Ergebnis in Worten, `AKTION_TEXT`, `ERGEBNIS_TEXT`) und die
  Historie des Zugangs und des Schalters am Kunden, neueste zuerst, 50 je Seite.

#### Festlegungen 1.11.10 (bestätigt am 24.11.2026 außer 6, 7 und 8 -- geändert, siehe „Antworten des Betriebs zu den Berichten 1.11.8 bis 1.11.11“)

1. Die Wege der Karte nennen nur den Kunden; ab Büro – Auftrag, die Monteurin nie; ohne Modul 403.
2. Portal aus beendet alle Sitzungen; ohne Portal an kein Zugang und kein Link.
3. Ein Zugang je Kunde, nur mit E-Mail am Kunden; seine E-Mail vorbelegt mit der des Kunden, genau eine gültige Adresse; verdeckte Anzeige „erstes Zeichen,
   ***, Domain“.
4. Link senden: Wert nur in der Mail, gespeichert der Prüfwert; 12 Kalendermonate; ein zweiter Link macht den ersten ungültig und meldet alle Geräte ab; die
   E-Mail ändert sich nur beim Senden; derselbe Klick erzeugt nichts; eine Ablehnung vor dem Versand ändert nichts; ein gescheiterter Versand lässt den neuen
   Link gelten.
5. Sperren nur mit Grund, meldet alle Geräte ab; gesperrt kein neuer Link und kein Verlängern; Entsperren lässt den bisherigen Link wieder gelten.
6. Verlängern: derselbe Link, ab jetzt 12 Monate; nur mit Link.
7. Zustände wie oben; „läuft bald ab“ ab 30 Tagen vor dem Ablauf; „Versand gescheitert“ aus dem letzten Versand des Links.
8. Kunde im Archiv: Zustand „Im Archiv“, jede Aktion 409 (Router und Geschäftslogik) -- auch Sperren (Bauplan Abschnitt 4 vor Festlegung 1.11.0, siehe oben).
9. Historie des Zugangs ohne Prüfwert; Protokoll aus Portal und Historie, neueste zuerst, 50 je Seite, ohne Adressen.

#### Tests und Prüfung 1.11.10

Neu `tests/test_v809_kundenportal_karte_server.py` (22) über `router_test_client` mit der Graph-Attrappe: Zustände der Reihe nach; ohne E-Mail; nur mit Portal an
und nur einer; Link nur als Prüfwert und genau dieser in der Mail; zweiter Link (ungültig, abgemeldet, neue Adresse); derselbe Klick; SMTP lehnt ab und nichts
ändert sich; Versand gescheitert; Sperren (Sitzungen, Grund Pflicht, gesperrte Aktionen); Portal aus; Archiv (Router und Geschäftslogik); Rollen und Modul;
unbekannter Kunde; Protokoll (zusammen, seitenweise); Texte für jede Aktion; verdeckte Anzeige; 12 Monate; Verlängern nur mit Link. Neuer Eintrag
`test_v761::KEINE_ID` (`seite`). Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.10“.

### Umsetzung 1.11.11: Karte „Kundenportal“ in der Kundenakte (P1d, Teil 2; P1-10 nach dem Muster der Kundenakte)

- `customer.html`, Übersicht, rechte Spalte unter „Stammdaten“: Karte mit Kopf und Kennzeichen des Zustands (Farben der Kennzeichen der Kundenakte: Im Archiv, Aus, Ohne
  E-Mail, Kein Zugang, Ohne Link, Aktiv, Läuft bald ab, Abgelaufen, Gesperrt), Satz zum Zustand, Angaben als Liste (E-Mail, Link gültig bis, Link erzeugt,
  zuletzt genutzt, gesperrt von/am, Grund), Hinweis (`.notice.warning`) bei „läuft bald ab“ (mit dem Weg „Verlängern“) und „Versand gescheitert“, Knöpfe je
  Zustand: Portal einschalten / ausschalten, Zugang anlegen, Link senden bzw. „Neuen Link senden“, Verlängern, Sperren, Entsperren, Protokoll. Ohne Modul gibt
  es Karte und Dialoge nicht (Jinja), die Seite fragt nicht; ungerendert (node-Tests) ebenso nicht.
- Dialoge statt prompt() (Regel 4): „Zugang anlegen“ (E-Mail des Kunden vorbelegt), „Link senden“ (Adresse änderbar; bei einem schon gesendeten Link die
  Warnung „Der bisherige Link gilt danach nicht mehr, alle Geräte des Kunden werden abgemeldet.“), „Zugang sperren“ (Grund Pflicht), „Protokoll“ (seitenweise,
  „Weitere laden“). Rückfrage (confirm) vor dem Ausschalten mit Zugang, dem Entsperren und dem Verlängern.
- Link senden und Sperren sind abschließend (`abschliessen()`, `ABSCHLIESSEND`), alles andere `speichern()`; jede Aktion zeichnet die Karte aus der Antwort,
  ein Fehler steht am Dialog bzw. unter der Karte und lädt den Stand neu (ein gescheiterter Versand zeigt dann den Hinweis).
- Im Archiv: Zustand „Im Archiv“, nur „Protokoll“ (`data-lesen`; dazu „Weitere laden“ und das Schließen des Dialogs), alle anderen Knöpfe aus -- doppelt: der
  Zustand der Karte und `_nur_lesen.html`; der Server lehnt ab (409, 1.11.10).
- Protokoll lesbar (`app/kundenportal.py::protokoll()`, `_historie_text()`): je Eintrag ein Satz -- Zugang angelegt, Neuer Link erzeugt, Link gültig bis
  <Tag>, E-Mail des Zugangs alt -> neu, Zugang gesperrt/entsperrt, Grund der Sperre, Kundenportal ein-/ausgeschaltet; dazu „Link gesendet an …“ / „Link nicht
  gesendet (an …)“ aus dem Versandprotokoll; nicht gezeigt: Konto-Kennungen, verdeckte Anzeige, „angelegt von“ (Buchhaltung des Zugangs).
- Testschalter `ERP_TEST_GRAPH=http://127.0.0.1:<Port>` (`app/email_sending.py::graph_attrappe()`): Anmeldung und sendMail an eine Attrappe -- nur mit
  `ERP_ENV` development oder test und nur an 127.0.0.1 (wie `ERP_TEST_FREMDSCHLUESSEL`); der Kalender-Abgleich bleibt unberührt. Ohne ihn ließe sich „Link
  senden“ im Klicktest nicht bis zum Versand prüfen (die Mails des Portals gehen nur über Microsoft 365).

#### Festlegungen 1.11.11 (bestätigt am 24.11.2026 außer 2, 6 und 7 -- geändert, siehe „Antworten des Betriebs zu den Berichten 1.11.8 bis 1.11.11“)

1. Die Karte steht in der Übersicht der Kundenakte unter „Stammdaten“, nach dem Muster der Kundenakte (Kopf mit Kennzeichen, Angaben als Liste, Hinweis als
   Warnhinweis, Knöpfe darunter); ohne Modul gibt es sie nicht.
2. Knöpfe je Zustand: aus -> „Portal einschalten“; kein Zugang -> „Zugang anlegen“; mit Zugang -> „(Neuen) Link senden“, „Verlängern“ (nur mit Link),
   „Sperren“; gesperrt -> nur „Entsperren“; immer „Portal ausschalten“, wenn an, und „Protokoll“, sobald es einen Zugang gibt oder das Portal an ist.
3. Dialoge: Zugang anlegen mit der E-Mail des Kunden vorbelegt; Link senden mit änderbarer Adresse und der Warnung bei einem schon gesendeten Link; Sperren mit
   Pflichtgrund.
4. Abschließend: Link senden und Sperren; alles andere über speichern().
5. Rückfrage vor dem Ausschalten (nur mit Zugang), dem Entsperren und dem Verlängern.
6. Im Archiv nur „Protokoll“ (lesend), sonst keine Aktion.
7. Protokoll als Sätze, mit den gesendeten Links aus dem Versandprotokoll, ohne die Buchhaltung des Zugangs; seitenweise mit „Weitere laden“.
8. Testschalter ERP_TEST_GRAPH nur für Test-Instanzen und nur an 127.0.0.1.
9. Werte vom Server nur als Text (textContent, esc(), createElement).

#### Tests und Prüfung 1.11.11

Neu `tests/test_v810_kundenportal_karte_seite.py` (14): Karte und Dialoge nur mit Modul, ungerendert ohne Portal; nur als Text; abschließend nur Link und Sperren;
Rückfragen, kein prompt(); Testschalter in 9 Formen; Umleitung von Anmeldung und Versand nur mit dem Schalter. `tests/test_v809_kundenportal_karte_server.py`:
das Protokoll als Sätze, mit gesendeten Links, ohne Buchhaltung; neu
`test_buchhaltung_des_zugangs_verdraengt_im_protokoll_nichts` (23 Tests). Neu `scripts/klicktest_kundenportal_karte.py` (88 Prüfungen): zehn Zustände mit Bild der Karte,
Angaben am gesperrten Zugang, Archiv (nur „Protokoll“, Server 409), Ablauf als Büro – Auftrag (einschalten, Zugang anlegen, Link senden an die
Graph-Attrappe -- ohne „Gesendete Elemente“, HTML, Knopf mit dem Link, fester Betreff --, neuer Link mit Warnung an eine andere Adresse, Sperren ohne und mit
Grund, Entsperren, Verlängern, Protokoll, Ausschalten, Prüfwert nie in der Historie), dunkel, 412 px ohne Überlauf, Admin, Monteurin 403, Modul aus (keine
Karte, keine Anfrage). Neue Einträge: `test_v554::FUNKTIONEN` (7 Funktionen der Karte), `test_v399::ABSCHLIESSEND` (`portalLinkSenden`, `portalSperren`),
`test_v795::LESEN` (`portal-protokoll`, `portal-protokoll-mehr`, `dialog-zu`). Angepasste Erwartung: `test_v809::test_protokoll_portal_und_historie_zusammen`
-- „Grund der Sperre: – → Test“ und „Kundenportal an“ (Feld alt -> neu, 1.11.10) sind jetzt die Sätze „Grund der Sperre: Test“ und „Kundenportal
eingeschaltet“. Gegenproben: `gegenproben-portal.md`, „1.11.11“.

### Antworten des Betriebs zu den Berichten 1.11.8 bis 1.11.11 (24.11.2026)

- Gelesen, Bilder angesehen; df8154f ist gepusht und auf dem Server. Bestätigt: 1.11.8-1 bis -7, 1.11.9-1 bis -6, 1.11.10-1 bis -5, -7 (als Zustände; „Versand
  gescheitert“ geändert, unten), -9, 1.11.11-1, -3, -4, -5, -8, -9.
- Fragen: der Link bleibt 43 Zeichen URL-sicher wie 1.11.1 („<hex>“ war ein Schreibfehler); Impressum und Datenschutz aus der Webseite der Firmendaten: so; nur
  HTML: so, den Textteil prüft der Rauchtest S9. **§ 35a GmbHG:** in die Fußzeile beider Mails eine kleine Zeile aus den Firmendaten „Sitz <Ort> ·
  <Registergericht> <Registernummer> · Geschäftsführer: <Name(n)>“; fehlt ein Feld, fällt nur dieses weg. Dazu ein Befund, nur melden: tragen die übrigen
  Mails des ERP diese Angaben?
- **Geändert 1.11.10-6 / 1.11.11-2:** Verlängern nur, solange der Link gilt (aktiv, läuft bald ab) -- nicht bei abgelaufen, gesperrt oder Versand
  gescheitert. Ein abgelaufener Link lebt nicht wieder auf; dort nur „Neuen Link senden“.
- **Geändert 1.11.10-7:** „Versand gescheitert“ ist ein eigener Zustand: Kennzeichen „Versand gescheitert“ (Warnfarbe), Satz „Der Link ging nicht hinaus.“,
  Knopf „Link erneut senden“ (bis 1.11.11 stand „Aktiv – Link versendet.“ über der Warnung).
- **Geändert 1.11.10-8 / 1.11.11-6:** Festlegung 1.11.0 gilt -- Sperren geht auch im Archiv (es nimmt nur Zugang weg; sonst wäre der Zugang nach dem
  Zurückholen offen, bis jemand sperrt). Im Archiv also „Protokoll“ und „Sperren“, alles andere 409.
- **Geändert 1.11.11-7:** Protokoll eine Zeile je Aktion statt je Feld, z. B. „Neuer Link gesendet an neu@… – gültig bis 24.11.2027 (E-Mail vorher max@…)“
  (Klammer nur bei geänderter E-Mail), „Zugang gesperrt – Grund: Kunde bittet darum“.
- Bilder der geänderten Zustände (gescheitert, abgelaufen, Archiv, Protokoll) und beider Mails mit der neuen Zeile. Danach ohne Warten P1e nach
  `bildgrundlage/entwurf-p1/` (Anmelden, Willkommen, Handy) und Bauplan Abschnitt 5; was die Entwürfe nicht abdecken, als Frage in den Bericht statt
  erfinden; Bilder aller Zustände, hell und dunkel, 390 und 1280 px, dazu 360 px.

### Umsetzung 1.11.12: Pflichtangaben in der Fußzeile der Mails (Antwort § 35a GmbHG)

- `app/portal_mails.py::pflichtangaben()`: „Sitz <Ort> · <Registergericht> <Registernummer> · Geschäftsführer: <Name(n)>“ aus den Firmendaten
  (`city`, `register_court`, `register_number`, `managing_director` -- Feld „Geschäftsführer / Inhaber“). Sitz ist der Ort der Anschrift: ein eigenes Feld
  „Sitz“ gibt es nicht. Fehlt ein Feld, fällt nur dieses weg (Gericht ohne Nummer und Nummer ohne Gericht bleiben stehen), fehlen alle, gibt es keine Zeile;
  Leerraum innerhalb eines Werts wird zu einem Leerzeichen. `Firma.pflichtangaben`.
- Die Zeile steht zuletzt in der Fußzeile, unter „Impressum · Datenschutz“, in 11 px (die Fußzeile 12 px); allein in der Fußzeile ohne Abstand nach oben. Wie
  jeder eingesetzte Wert über `html.escape()`.

#### Befund (nur gemeldet): tragen die übrigen Mails des ERP die Pflichtangaben?

Nein. Geprüft an jedem Aufrufer von `dispatch_email()` (Angebot, Auftrag, Rechnung, Mahnung, Vertrag, Checkliste, Behinderungs-, Wiederaufnahme- und
Bedenkenanzeige, Abnahmeprotokoll, Aufgaben; dazu die Mails des Portals):

- **Text der Mail:** die Vorlagen (`app/document_email_templates.py`, Mahnstufen `ReminderLevel`) und ihre eingebauten Vorgaben (`projects.py`, `orders.py`,
  `invoices.py`, `reminders.py`, `contract_versions.py`, `checklist_email.py`, `notice_letters.py`) enden mit „Mit freundlichen Grüßen“ -- ohne Firmennamen,
  ohne Sitz, Registergericht, Registernummer oder Geschäftsführer. Einen Platzhalter dafür gibt es in keiner Mail-Vorlage (`{firmenname}` nur in den
  Vertragsvorlagen, also im Vertrags-PDF). Die Vorlagen sind freier Text -- der Betrieb könnte die Angaben heute von Hand eintragen.
- **Angehängte Fußzeile:** keine. `dispatch_email()` reicht Text bzw. HTML unverändert an `send_message()` weiter, SMTP wie Graph senden ihn so. Ob Exchange
  Online eine eigene Regel mit Fußzeile hat, liegt außerhalb des Codes.
- **PDF im Anhang:** der Code druckt nur die Absenderzeile (Name, Straße, PLZ Ort -- den Namen mit „GmbH“, den Ort ohne „Sitz“); der Baustein „Firmenkopf“
  (Name, Anschrift, Telefon, E-Mail, Webseite, kein Register, kein Geschäftsführer) ist ab Werk aus, die Fußzeile nur „Seite X von Y“ und ebenfalls aus.
  Registergericht und Geschäftsführer stehen auf dem PDF nur, wenn das hochgeladene Briefpapier sie trägt (`app/document_layout.py`, Kommentar zu 1.3.8: dort
  stehen „Anschrift, Kontakt, Registergericht, Bankverbindung“) -- geprüft ist das hier nicht.
- **Aufgaben-Mails** gehen nur an Mitarbeiter des Betriebs (keine Geschäftsbriefe nach außen).
- Möglicher Weg, falls gewünscht (nicht gebaut): dieselbe Zeile zentral unter jede Mail an Kunden und Beteiligte (in `dispatch_email()` je Versandart), oder
  ein Platzhalter `{pflichtangaben}` für die Vorlagen.

#### Festlegungen 1.11.12 (bestätigt am 24.11.2026)

1. Beide Mails des Portals tragen zuletzt in der Fußzeile eine kleine Zeile (11 px) „Sitz <Ort> · <Registergericht> <Registernummer> · Geschäftsführer:
   <Name(n)>“ aus den Firmendaten.
2. Sitz ist der Ort der Anschrift der Firmendaten (es gibt kein eigenes Feld „Sitz“); Geschäftsführer ist das Feld „Geschäftsführer / Inhaber“, wie eingetragen.
3. Fehlt ein Feld, fällt nur dieses weg (Gericht und Nummer je für sich); fehlen alle, fehlt die Zeile.
4. Jeder Wert maskiert, Leerraum innerhalb eines Werts zu einem Leerzeichen.

#### Tests und Prüfung 1.11.12

`tests/test_v807_portal_mails_html.py`: neu `test_pflichtangaben_fehlt_ein_feld_faellt_nur_dieses_weg` (9 Fälle) und
`test_pflichtangaben_klein_und_zuletzt_in_der_fusszeile`; die Firmendaten der Testdaten tragen jetzt Registergericht, -nummer und Geschäftsführer; Angriff
auch über diese Felder. Angepasste Erwartungen: `test_v807::LINK_WORTLAUT`/`CODE_WORTLAUT` -- letzter Absatz bis 1.11.11 die Fußzeile, jetzt danach die
Zeile `PFLICHT`; `test_ohne_telefon_faellt_nur_die_nummer_weg` und `test_impressum_und_datenschutz_aus_der_webseite` -- die Fußzeile ist der vorletzte Absatz;
`test_absender_ohne_leere_teile` -- auch ohne Register und Geschäftsführer, dann keine Zeile; `test_v804::test_mails_gesiezt_mit_hinweis_und_absender` --
letzter Absatz „Sitz Musterstadt“ (dort ist nur der Ort gepflegt), die Fußzeile davor. Gegenproben: `gegenproben-portal.md`, „1.11.12“. Bilder beider Mails
mit der Zeile im Bericht 1.11.12.

### Umsetzung 1.11.13: Karte nach den Antworten (Verlängern, „Versand gescheitert“, Sperren im Archiv, Protokoll je Aktion)

- **„Versand gescheitert“ ist ein Zustand** (`app/kundenportal.py::zustand()`, Antwort 1.11.10-7): ist der letzte Versand des Links gescheitert und der Link
  weder gesperrt noch abgelaufen, heißt der Zustand `gescheitert` -- Kennzeichen „Versand gescheitert“ (`chip-warn`), Satz „Der Link ging nicht hinaus.“, in
  den Angaben „Versand gescheitert: <Zeit> an <Adresse>“, Knopf „Link erneut senden“. Der Warnhinweis dafür entfällt (er bleibt für „läuft bald ab“). Vorrang:
  gesperrt, dann abgelaufen, dann gescheitert, dann läuft bald ab. „Link erneut senden“ öffnet den Dialog „Link erneut senden“ ohne die Warnung „Der bisherige
  Link gilt danach nicht mehr …“ -- der gescheiterte Link erreichte niemanden, die Geräte sind seit seinem Erzeugen abgemeldet.
- **Verlängern nur, solange der Link gilt** (Antwort 1.11.10-6 / 1.11.11-2): Knopf nur bei „aktiv“ und „läuft bald ab“ (`LINK_GILT`); der Server lehnt jeden
  anderen Zustand mit 409 und dem Grund ab (`VERLAENGERN_NICHT`: abgelaufen „lebt nicht wieder auf -- bitte einen neuen Link senden“, gescheitert „bitte den
  Link erneut senden“, gesperrt, ohne Link, Portal aus). Bei „abgelaufen“ bleibt „Neuen Link senden“.
- **Sperren auch im Archiv** (Antwort 1.11.10-8 / 1.11.11-6; Festlegung 1.11.0): `archiv_vorab()` steht seit 1.11.13 an jeder Route der Karte einzeln, nur nicht
  an `POST …/portal/sperren` (`tests/test_v793_archivschutz.py::OHNE_VORAB` mit Grund); `kundenportal.sperren()` prüft das Archiv nicht mehr. Auf der Seite
  tragen der Knopf „Sperren“, das Feld „Grund“ und der Knopf im Dialog `data-lesen` (wie „Zurückholen“: bleibt im Archiv, das Feld frei). Im Archiv also
  „Protokoll“ und -- solange der Zugang nicht gesperrt ist -- „Sperren“; alles andere 409. Satz im Archiv: „Der Kunde ist im Archiv – sein Zugang wirkt nicht.“
- **Protokoll eine Zeile je Aktion** (Antwort 1.11.11-7, `protokoll()`): die Zeilen der Historie, die eine Aktion am Zugang schrieb, werden eine Zeile
  (`_aktionen()`): dasselbe Konto, höchstens 5 Sekunden auseinander, die Felder in der Reihenfolge der Spalten und jedes höchstens einmal (so schreibt ein Flush
  sie), nur verträgliche Arten (Link mit Frist; Sperre allein); Anlegen steht immer für sich. Der Link bekommt seinen Versand (`_versand_zuordnen()`: der letzte
  Link davor, höchstens 5 Sekunden). Sätze: „Link gesendet an <Adresse> – gültig bis <Tag>“, „Neuer Link gesendet an … – gültig bis … (E-Mail vorher …)“ (die
  Klammer nur bei geänderter E-Mail), „Neuer Link nicht gesendet – Versand an … gescheitert“, „Link verlängert – gültig bis …“, „Zugang gesperrt – Grund: …“,
  „Zugang entsperrt“, „Zugang angelegt für <Adresse>“, „Kundenportal eingeschaltet/ausgeschaltet“; dazu wie bisher die Zugriffe des Portals. „Neuer Link“ heißt:
  an diesen Zugang ging vorher schon ein Link hinaus (aus dem Versandprotokoll -- jeder Link hat genau einen Versand; zwei Links in derselben Sekunde hätten
  dasselbe „Link erzeugt“ und schrieben dafür keine Zeile der Historie). Die Abfrage liest höchstens 8 Zeilen der Historie je Eintrag der Seite; die älteste
  Aktion einer abgeschnittenen Abfrage steht erst auf der nächsten Seite.

#### Festlegungen 1.11.13 (bestätigt am 24.11.2026)

1. „Versand gescheitert“ ist ein Zustand: der letzte Versand des Links scheiterte, der Link ist weder gesperrt noch abgelaufen (die gehen vor); Kennzeichen in
   der Warnfarbe, Satz „Der Link ging nicht hinaus.“, Angabe mit Zeit und Adresse, Knopf „Link erneut senden“; kein Warnhinweis dazu.
2. „Link erneut senden“ öffnet den Dialog unter diesem Titel ohne die Warnung zum bisherigen Link.
3. Verlängern nur bei „aktiv“ und „läuft bald ab“; sonst kein Knopf und 409 mit dem Grund; bei „abgelaufen“ nur „Neuen Link senden“.
4. Sperren geht auch im Archiv (Server ohne Prüfung vorab, Knopf, Dialog und Feld bleiben); alles andere im Archiv 409; im Archiv der Satz „Der Kunde ist im
   Archiv – sein Zugang wirkt nicht.“
5. Das Protokoll zeigt eine Zeile je Aktion (Zeilen eines Flushs zusammen, der Link mit seinem Versand) in den Sätzen oben.
6. „Neuer Link“ = an diesen Zugang ging vorher schon ein Link (Versandprotokoll).

#### Tests und Prüfung 1.11.13

`tests/test_v809_kundenportal_karte_server.py` (36): neu `test_verlaengern_nur_solange_der_link_gilt` (7 Zustände), `test_gescheitert_nach_gesperrt_und_abgelaufen`,
`test_sperren_geht_auch_im_archiv`, `test_protokoll_eine_zeile_je_aktion` (neun Aktionen desselben Kontos, Uhr je Aufruf eine Sekunde weiter -- `uhr`),
`test_protokoll_versand_beim_richtigen_link` (Versand nach und vor der Historie), `test_protokoll_neuer_link_auch_in_derselben_sekunde`. Angepasste Erwartungen:
`test_zustaende_der_reihe_nach` -- bis 1.11.12 machte „Verlängern“ einen abgelaufenen Link wieder aktiv, jetzt 409 und „Neuen Link senden“; `test_versand_gescheitert`
-- Zustand „aktiv“ -> „gescheitert“; `test_kunde_im_archiv_nur_lesen` -- Sperren im Archiv 409 -> eigener Test, 200; `test_archiv_auch_in_der_geschaeftslogik` --
ohne Sperren; `test_protokoll_portal_und_historie_zusammen` -- „Grund der Sperre: Test“, „Zugang gesperrt“, „Neuer Link erzeugt“, „Link gesendet an …“ (je Feld)
-> „Zugang gesperrt – Grund: Test“, „Zugang angelegt für …“, „Link gesendet an … – gültig bis …“ (je Aktion); `test_buchhaltung_des_zugangs…` -- „Zugang
angelegt“ -> „Zugang angelegt für max@example.invalid“. Neue Einträge: `test_v793::OHNE_VORAB` (Sperren), `test_v795::LESEN` (`portal-sperren-dialog`,
`portal-sperren`). `scripts/klicktest_kundenportal_karte.py` (99 Prüfungen, bis 1.11.12 88): angepasst „abgelaufen: Knöpfe“ (ohne „Verlängern“),
„gescheitert“ (Zustand „Aktiv“ mit Hinweis -> „Versand gescheitert“, „Link erneut senden“), „archiv“ (nur „Protokoll“ und Server 409 auf Sperren -> „Sperren“
geht, danach nur „Protokoll“, Entsperren 409), „Mail: eine an der Attrappe“ (gezählt ab dem Ablauf), „Protokoll“ (je Feld -> je Aktion mit Konto); neu der
gescheiterte Versand erneut gesendet, Verlängern bei „abgelaufen“ 409, die Uhr eine Minute weiter je Schritt. Gegenproben: `gegenproben-portal.md`, „1.11.13“.

### Umsetzung 1.11.14: die Seiten des Kundenportals (P1e)

Nach den Entwürfen `bildgrundlage/entwurf-p1/Portal-Anmelden`, `-Willkommen` und `-Handy` (Wortlaut wie dort) und Bauplan P1, Abschnitt 5.

- **Eine Seite für alles** (`app/portal/seiten/portal.html`, gerendert von `app/portal/seiten.py` mit Jinja und autoescape): unter `GET /` stehen die Abschnitte
  A „Ihr Zugang wird geprüft …“, B „Willkommen im Kundenportal“ / „Code senden“, C „Code eingeben“ und „Neuen Code anfordern“, D „Willkommen“ und E „Fehlerseite“
  verborgen in der Seite; das Skript (`seiten/portal.js`) zeigt je Zustand einen und füllt nur Text (`textContent`; die Seite verlangt Trusted Types). Der Server
  setzt nur, was ohne Sitzung öffentlich ist: Name des Betriebs (Kopf: erstes Wort fett, darunter der Rest „· Kundenportal“; auf dem Handy angemeldet nur
  „Kundenportal“ wie im Entwurf), Kontakt (Telefon als `tel:+49…`, E-Mail als `mailto:` nur bei gültiger Adresse, Webseite nur als gültiger Host), Fuß
  (© Jahr und Name breit, Impressum und Datenschutz als `https://<Webseite>/impressum` bzw. `/datenschutz` wie in den Mails) -- jeder Wert maskiert.
  Begrüßung und verdeckte Adresse kommen nur aus den Wegen mit Sitzung bzw. Vorstufe.
- **CSP:** kein Inline-Skript, kein `style`- und kein `on…`-Attribut. Skript und Stil des Portals unter `/s/portal.js` und `/s/portal.css` (fester Typ), in der Seite
  mit `?v=<Prüfsumme des Inhalts>` und deshalb ein Jahr im Speicher des Browsers; die Seite selbst no-store. Farben, Schriften und hell/dunkel aus dem
  Design-System: `/static` (ds.css und die Schriften) bindet der Dienst über `app/design_dateien.py` ein, nur GET/HEAD, fester Typ; die Schranke gibt einer
  Design-Datei mit 200 ein Jahr, sonst no-store (wie das ERP). Hell oder dunkel nach dem Gerät: das Skript setzt `data-theme` wie im ERP; im Dunkeln steht die
  Bildmarke auf einer weißen Kachel (wie `_bildmarke.html`).
- **Abläufe** (alles Prüfen bleibt in den Funktionen der Datenbank): mit `#z=<Wert>` nimmt das Skript den Link sofort aus Adresszeile und Verlauf
  (`history.replaceState`) und schickt ihn einmal in der Kopfzeile X-Portal-Link -- angemeldet: D; neues Gerät: B mit verdeckter Adresse; sonst E „Dieser Link
  funktioniert nicht“ (gleich aus welchem Grund). Ohne Link: `POST /api/sitzung/weiter` -- angemeldet: D; sonst setzt der Tab eine laufende Anmeldung fort
  (im `sessionStorage` nur Schritt und verdeckte Adresse; Neuladen nach dem Wechsel in die Mail-App führt zurück zu C), sonst E „Bitte über den Link anmelden“.
  B: „Code senden“ -> „Wird gesendet …“ -> der Stand des Versands je Sekunde -> C mit „Code gesendet an …“ und „Neuen Code senden · in 1:00“ (Zähler bis 60
  Sekunden); gescheitert, verworfen oder nach 30 Sekunden noch nicht gesendet: „Der Code konnte gerade nicht gesendet werden. Bitte versuchen Sie es gleich
  noch einmal oder rufen Sie uns an.“ mit der Telefonnummer; Bremse: „Ein neuer Code ist in n Minuten wieder möglich.“, der Knopf bis dahin gesperrt. C: der
  Code mit und ohne Leerzeichen; keine 6 Ziffern: „Bitte geben Sie die 6 Ziffern aus der E-Mail ein.“ ohne Anfrage; falsch: „Dieser Code stimmt nicht. Noch n
  Versuche.“ (Einzahl „Noch 1 Versuch.“); abgelaufen, verbraucht oder 5 Fehlversuche: „Neuen Code anfordern“. D: Begrüßung, Kontakt, „Was Sie hier bald
  finden“, „Ihre Anmeldung“; „Abmelden“ (oben und in der Karte) ohne Rückfrage, „Auf allen Geräten abmelden“ mit dem Dialog des Entwurfs; danach E „Sie sind
  abgemeldet“. Antworten ohne passenden Ablauf: 401 -> „Bitte über den Link anmelden“, 429 -> „Zu viele Versuche“, 502/504 (nginx während eines Neustarts) ->
  „Gleich wieder da“, sonst „Gerade klappt etwas nicht“.
- **Vom Server gesetzte Fehlerseite:** eine Adresse, die es nicht gibt (GET/HEAD außerhalb von `/api/`), ist die Seite mit `data-fall="nicht_gefunden"` und 404
  („Diese Seite gibt es nicht“); liest die Seite die Firmendaten nicht, `data-fall="technisch"` ohne Kontakt mit 500 (im Journal nur die Klasse). Unter `/api/`
  bleibt es JSON. Ohne JavaScript zeigt `<noscript>` „JavaScript ist ausgeschaltet“ samt Kontakt (hell -- hell oder dunkel setzt das Skript).
- **Breite Ansicht:** „Willkommen“ ab 900 px wie der Entwurf für 1280 px (Liste links, Kontakt und Anmeldung rechts); A–C und E -- in den Entwürfen nur für das
  Handy -- als Spalte von 440 px in der Mitte, mit Kopf und Fuß wie „Willkommen“ (Frage im Bericht).

#### Festlegungen 1.11.14 (bestätigt am 24.11.2026 außer 9 -- geändert, siehe „Antworten des Betriebs zu den Berichten 1.11.12 bis 1.11.15“)

1. Eine Seite unter `/` für A–E, die Abschnitte verborgen, das Skript wählt; Wortlaut der Entwürfe.
2. Kein Inline-Skript, kein `style`- oder `on…`-Attribut; Skript und Stil des Portals unter `/s/` mit `?v=<Prüfsumme>`, ein Jahr im Speicher; die Seite no-store;
   ds.css und die Schriften aus `/static` wie im ERP (200 ein Jahr, sonst no-store).
3. Das Skript setzt nur Text (`textContent`) -- kein innerHTML, eval, document.write, kein Cookie-Zugriff.
4. Der Link geht sofort aus Adresszeile und Verlauf und nur in der Kopfzeile X-Portal-Link zum Server.
5. Öffentliche Firmendaten in Kopf, Kontakt und Fuß, jeder Wert maskiert; Telefon als `tel:+49…` (ohne erkennbare Vorwahl nur als Text), E-Mail nur gültig als
   `mailto:`, Webseite, Impressum und Datenschutz nur bei gültigem Host; ohne Telefon und E-Mail keine Kontaktkarte; auf dem Handy angemeldet im Kopf nur
   „Kundenportal“.
6. Fehlerseite: unbekannte Adresse 404 als Seite, ohne Firmendaten „technisch“ 500; 401 -> „Bitte über den Link anmelden“, 429 -> „Zu viele Versuche“, 502/504 ->
   „Gleich wieder da“, sonst „Gerade klappt etwas nicht“; immer dasselbe Link-Symbol, nur der Text wechselt.
7. Hell oder dunkel nach dem Gerät (`data-theme` wie im ERP), die Bildmarke im Dunkeln auf weißer Kachel; ohne JavaScript hell.
8. Neuladen während der Anmeldung setzt sie fort (im Speicher des Tabs nur Schritt und verdeckte Adresse).
9. „Neuen Code senden“ erst nach 60 Sekunden (Zähler); der Stand des Versands je Sekunde, nach 30 Sekunden ohne Versand die Meldung „Der Code konnte gerade nicht
   gesendet werden …“ mit Telefon.
10. Ohne 6 Ziffern: „Bitte geben Sie die 6 Ziffern aus der E-Mail ein.“, keine Anfrage.
11. Abmelden auf diesem Gerät ohne Rückfrage, auf allen Geräten mit Dialog; ohne JavaScript die Fehlerseite „JavaScript ist ausgeschaltet“ mit Kontakt.
12. Breit: „Willkommen“ wie der Entwurf; A–C und E als Spalte von 440 px in der Mitte mit Kopf und Fuß wie „Willkommen“.

#### Fragen (die Entwürfe decken es nicht ab; beantwortet am 24.11.2026: alle wie gebaut außer 4, siehe unten)

1. A–C und E am Rechner (1280 px): die Handy-Spalte in der Mitte mit dem Kopf und Fuß von „Willkommen“ -- so, oder ein eigener Entwurf?
2. B „Versand gescheitert“ und „zu viele Anforderungen“: als oranger Kasten wie „Dieser Code gilt nicht mehr“, die Telefonnummer darunter als Link -- so?
3. Weniger oder mehr als 6 Ziffern: „Bitte geben Sie die 6 Ziffern aus der E-Mail ein.“ -- Wortlaut?
4. Wartet ein Code nach 30 Sekunden noch auf den Versand, zeigt B die Meldung „Der Code konnte gerade nicht gesendet werden …“ -- so, oder länger warten?
5. „Abmelden“ auf diesem Gerät ohne Rückfrage (der Entwurf zeigt den Dialog nur für „überall“; der Bauplan nannte „mit Bestätigung“) -- so?
6. Dauert die Anmeldung länger als 15 Minuten (die vorläufige Sitzung läuft ab), zeigt die Seite „Bitte über den Link anmelden“ -- so?
7. Neuladen während der Anmeldung setzt sie fort (statt „Bitte über den Link anmelden“) -- so?
8. Dunkelmodus: Farben aus dem Design-System, Bildmarke auf weißer Kachel -- so (die Entwürfe zeigen nur hell)?
9. Fuß: breit „© Jahr Name · Impressum · Datenschutz“ auf weißem Band, auf dem Handy nur die beiden Links (wie die Entwürfe) -- auch für A–C und E so?
10. Titel des Tabs „Kundenportal – <Name des Betriebs>“ -- so?

#### Tests und Prüfung 1.11.14

Neu `tests/test_v811_portal_seiten.py` (45): Wege, Typen und Speicher (Seite, Skript, Stil, ds.css, Schrift, fehlende Design-Datei), 404 als Seite (unter `/api/`
JSON), ohne Firmendaten „technisch“ ohne Details, Aufbau der Seite (ein Skript ohne Inhalt, kein `style`-/`on…`-Attribut, kein `javascript:`, nur die erwarteten
Links), noscript, Angriff über jedes Feld der Firmendaten, Telefon (11 Fälle), Webseite wie in den Mails (12), ungültige E-Mail und Webseite ohne Links, Firma mit
einem Wort und ohne Namen, das Skript (keine gefährlichen Aufrufe, nur Wege des Portals, Link aus der Adresse vor der ersten Anfrage, Fälle der Fehlerseite),
Wortlaut der Entwürfe (67 Sätze), Stil ohne fremde Quellen. Neu `scripts/klicktest_portal_seiten.py` (111 Prüfungen) gegen den echten Dienst unter PostgreSQL
(Wegwerf-Schema `pgklick_…`, Testrolle `dkportal_test`, Postbote und Attrappe von Microsoft 365 im Testprozess, der Code aus der Mail eingetippt): vier Abläufe,
jede Fehlerseite (429, 500, 502 über eine Ersatz-Antwort im Browser), ohne JavaScript; jeder Zustand als Bild in 390 und 1280 px hell und dunkel und 360 px hell
(95 Bilder), schmal ohne Überlauf, keine Verletzung der CSP, kein JS-Fehler; unter einer Gegenprobe ohne Bilder. Angepasste Erwartung:
`test_v801::test_angriffe_gegen_einen_echten_uvicorn` -- erreicht wurden bis 1.11.13 nur GET/HEAD auf `/health` und `/api/kontakt`, jetzt auch auf
`/static/ds/ds.css` (die Seite braucht es). Gegenproben: `gegenproben-portal.md`, „1.11.14“.

Die volle Suite fand vor dem Commit zwei rote Wächter: `tests/test_v406_dateien_nie_aktiv.py` (eine Antwort mit Inhalt braucht einen festen Typ -- Skript und
Stil liefen über eine gemeinsame Hilfe mit dem Typ als Variable; jetzt je Weg eine Antwort mit festem Typ) und `tests/test_v603_engines_aufraeumen.py` (die Engine
der Testdaten legt `test_v811` jetzt über `wegwerf_engine()` an). Beide Wächter bleiben unverändert; die Gegenprobe zu Nr. 2 „Skript und Stil ein Jahr“ danach
gegen die neue Zeile noch einmal rot.

### Umsetzung 1.11.15: „Gleich wieder da“ von nginx (P1e, Bauplan P1, Abschnitt 5 E „Wartung“)

- `scripts/server/portal-wartung.html`: die feste Seite „Gleich wieder da“ / „Das Kundenportal ist in wenigen Minuten wieder erreichbar.“ (Wortlaut der Tabelle im
  Entwurf Portal-Handy) mit Bildmarke, „Kundenportal“ und dem Symbol der Fehlerseite -- ohne Skript, ohne Schrift, nichts von außen, ein `<style>` mit den Farben
  des Design-Systems hell und dunkel (`prefers-color-scheme`, ohne Skript). Kein Name des Betriebs und kein Kontakt: die Datei ist fest, die Firmendaten liest
  nur der Dienst (Frage im Bericht).
- `scripts/server/nginx-kunde.conf`: `error_page 502 504 /_wartung.html;` mit einem internen Ort, die Datei aus `/etc/nginx/dk-portal/wartung.html`; dort die
  Schutz-Kopfzeilen (CSP `default-src 'none'` und genau die SHA-256 des Stils -- wie der Server die Datei sieht, mit LF --, kein Einrahmen, nosniff, no-referrer,
  no-store, HSTS). Antworten des Dienstes selbst (auch seine 503) gehen unverändert durch (`proxy_intercept_errors` bleibt aus). Für S7: `sudo install -D -m 644
  -o root -g root scripts/server/portal-wartung.html /etc/nginx/dk-portal/wartung.html` vor `nginx -t`. Die Seite des Portals zeigt dieselbe Meldung, wenn eine
  ihrer Anfragen 502 oder 504 bekommt (1.11.14).

#### Festlegungen 1.11.15 (bestätigt am 24.11.2026)

1. Antwortet der Dienst nicht (502/504), zeigt nginx die feste Seite „Gleich wieder da“ -- ohne Skript, ohne Schrift, nichts von außen, hell und dunkel nach dem
   Gerät, ohne Name des Betriebs und ohne Kontakt.
2. nginx zeigt sie nur für seine eigenen 502 und 504; Antworten des Dienstes gehen unverändert durch.
3. Ihr Stil ist in der CSP über seine SHA-256 erlaubt, dazu kein Einrahmen, nosniff, no-referrer, no-store, HSTS; ein Test hält Prüfsumme und Datei gleich.

#### Tests und Prüfung 1.11.15

Neu `tests/test_v812_portal_wartung.py` (4): Seite ohne Skript und ohne Fremdes, Wortlaut, hell/dunkel; dieselbe Bildmarke wie die Seite des Portals; nginx
mit `error_page 502 504` und internem Ort; CSP mit genau der Prüfsumme des Stils und die übrigen Kopfzeilen. Keine angepasste Erwartung. Gegenproben:
`gegenproben-portal.md`, „1.11.15“. Bilder der Seite in 390 und 1280 px hell und dunkel und 360 px hell im Bericht 1.11.15.

### Antworten des Betriebs zu den Berichten 1.11.12 bis 1.11.15 (24.11.2026)

- Gelesen, alle Bilder angesehen (sehr nah an den Entwürfen); fc8b758 ist gepusht und auf dem Server. Bestätigt: 1.11.12-1 bis -4, 1.11.13-1 bis -6, 1.11.14-1
  bis -8, -10 bis -12, 1.11.15-1 bis -3. Fragen P1e-1, -2, -3, -5 bis -10 wie gebaut; P1e-11 (feste Seite ohne Name und Kontakt): so lassen.
- **Geändert P1e-4 / 1.11.14-9:** nach 30 Sekunden ist der Versand nicht gescheitert (der Auftrag gilt 10 Minuten) -- sonst fordert der Kunde neu an, und der
  erste Code kommt danach und gilt nicht mehr. Nach 30 Sekunden weiter zu C mit dem Hinweis „Der Versand dauert länger als sonst. Der Code kann noch einige
  Minuten brauchen – sehen Sie bitte auch im Spam-Ordner nach.“, die Seite fragt weiter nach dem Stand; „Der Code konnte gerade nicht gesendet werden …“ mit
  Telefon nur, wenn der Postbote gescheitert oder verworfen meldet oder nach 10 Minuten nichts ging; „Neuen Code senden“ bleibt erst nach 60 Sekunden.
  Kleinigkeit: in B steht am Rechner „Wir fragen Sie nie …“ weit unten am Fuß -- breit direkt unter den Inhalt.
- **§ 35a, neue Version:** dieselbe Zeile zentral unter jede Mail an Kunden und Beteiligte (Text: nach einer Leerzeile Name, Anschrift und Pflichtangaben aus
  den Firmendaten), eine Quelle für Portal und ERP; Aufgaben-Mails an Mitarbeiter ohne. Beispiel einer Angebotsmail in den Bericht.
- Danach P1f vorbereiten, nichts auf dem Server: (1) „Server-Schritte P1“ auf den Stand von fc8b758 -- je Schritt S0–S10 die Befehle zum Kopieren, was zu sehen
  sein soll und wann abzubrechen ist, Geheimnisse nie angezeigt; (2) Stichpunkte für die Datenschutzerklärung (Portal) als eigene Datei für den
  Webseiten-Chat, Stand heute. Beides als Dateien in `bildgrundlage/`, mit Bericht.

### Umsetzung 1.11.16: der Versand des Codes dauert länger (Antwort P1e-4)

- `app/portal/seiten/portal.js`: nach „Code senden“ (bzw. „Neuen Code senden“) merkt sich die Seite den Zeitpunkt der Anforderung (auch im Speicher des Tabs,
  `seit`) und fragt nach dem Stand -- je Sekunde, bis 30 Sekunden um sind (`LANGSAM_MS`), dann alle 5 Sekunden (`STAND_LANGSAM_MS`). Wartet der Code nach 30
  Sekunden noch, geht sie weiter zu C mit dem Hinweis „Der Versand dauert länger als sonst …“ (`c-dauert`, Info-Farben des Design-Systems -- „läuft,
  Fortschritt“ -- mit Uhr). Kommt der Code danach, wechselt der Hinweis auf „Code gesendet an …“, eine angefangene Eingabe bleibt stehen. Gescheitert
  („Der Code konnte gerade nicht gesendet werden …“ mit Telefon) nur, wenn der Postbote `fehler` oder `verworfen` meldet (oder keinen Auftrag kennt) oder
  nach 10 Minuten (`AUFTRAG_MS`) nichts ging -- vor den 30 Sekunden in B, danach in C. Nur die jüngste Frage nach dem Stand läuft weiter (ein neuer Code
  beendet die alte).
- „Neuen Code senden“ zählt die 60 Sekunden ab der Anforderung (nicht mehr ab dem Versand) -- auch nach dem Wechsel zu C nach 30 Sekunden („in 0:29“) und nach
  einem Neuladen (der Zeitpunkt steht im Speicher des Tabs; ein Neuladen nach mehr als 30 Sekunden zeigt C mit dem Hinweis).
- `portal.css`: breit (ab 900 px) steht „Wir fragen Sie nie …“ in B direkt unter dem Inhalt; auf dem Handy weiter unten wie im Entwurf.

#### Festlegungen 1.11.16 (bestätigt am 25.11.2026)

1. Wartet der Code nach 30 Sekunden noch, weiter zu C mit dem Hinweis „Der Versand dauert länger als sonst. Der Code kann noch einige Minuten brauchen – sehen Sie
   bitte auch im Spam-Ordner nach.“; die Seite fragt weiter nach dem Stand, dann alle 5 Sekunden.
2. „Der Code konnte gerade nicht gesendet werden …“ mit Telefon nur, wenn der Postbote gescheitert oder verworfen meldet oder nach 10 Minuten nichts ging (vor 30
   Sekunden in B, danach in C).
3. „Neuen Code senden“ erst 60 Sekunden nach der Anforderung (Zähler ab der Anforderung).
4. Ein Neuladen setzt das Warten fort (im Speicher des Tabs zusätzlich der Zeitpunkt der Anforderung).
5. Kommt der Code nach dem Hinweis, steht dort „Code gesendet an …“; eine angefangene Eingabe bleibt.
6. Am Rechner steht „Wir fragen Sie nie …“ in B direkt unter dem Inhalt.
7. Der Hinweis in den Info-Farben des Design-Systems mit Uhr.

#### Tests und Prüfung 1.11.16

`tests/test_v811_portal_seiten.py` (47): neu `test_versand_dauert_laenger_zeiten` (die Zeiten, kein „nach 30 Versuchen gescheitert“ mehr) und
`test_hinweis_versand_dauert_in_den_farben_fuer_fortschritt`; der Wortlaut kennt den neuen Satz. `scripts/klicktest_portal_seiten.py` (132 Prüfungen): der
Postbote lässt sich anhalten, die Uhr der Seite (`Date.now`) vorstellen; neu Ablauf 5 (31 Sekunden: C mit Hinweis und „in 0:2x“, neu laden: wieder C mit Hinweis,
der Postbote sendet: „Code gesendet an …“, die Eingabe bleibt, angemeldet) und Ablauf 6 (31 Sekunden, dann 10 Minuten: gescheitert mit Telefon, „Neuen Code
senden“ frei); B breit mit dem Hinweis direkt unter dem Inhalt; Bilder `c_versand_dauert`, `c_versand_gescheitert`. Angepasste Erwartung:
`test_v811::test_link_aus_der_adresse_bevor_eine_anfrage_hinausgeht` -- im Speicher des Tabs bis 1.11.15 Schritt und Anzeige, jetzt dazu `seit`. Gegenproben:
`gegenproben-portal.md`, „1.11.16“.

### Umsetzung 1.11.17: Name, Anschrift und Pflichtangaben unter jeder Mail an Kunden (§ 35a GmbHG, neue Version)

Anlass: der Befund zu 1.11.12 („tragen die übrigen Mails des ERP die Pflichtangaben?“ -- nein) und die Antwort des Betriebs vom 24.11.2026 (der dort
genannte Weg „zentral unter jede Mail an Kunden und Beteiligte“).

- `app/firmenangaben.py` (neu) ist die eine Quelle: `anschrift()` („Name · Straße · PLZ Ort“ ohne leere Teile), `pflichtangaben()` (die Zeile aus 1.11.12,
  aus `app/portal_mails.py` hierher verschoben), `zeilen(db)` (beide aus den Firmendaten der Einstellungen, ohne leere) und `text_fusszeile(db)` (eine
  Leerzeile, dann die Zeilen; ohne jede Angabe leer). `app/portal_mails.py` nimmt Anschrift und Pflichtangaben seiner HTML-Fußzeile von dort -- dieselben
  Zeichen wie bisher.
- `app/email_dispatch.py::dispatch_email()` setzt den Schluss an jede Text-Mail an, bevor sie hinausgeht: Leerraum am Ende des Texts fällt weg, dann
  `text_fusszeile()`. Ohne nur `OHNE_FIRMENANGABEN` = {„aufgabe“} (die Aufgaben-Mails gehen nur an Mitarbeiter); die Mails des Portals (HTML) tragen die Angaben
  nur in ihrer Fußzeile, nicht ein zweites Mal. Damit gilt der Schluss für jede Versandart des Versandprotokolls: Angebot, Auftrag, Rechnung (auch Storno),
  Mahnung, Vertrag, Checkliste (auch das Abnahmeprotokoll), Behinderungsanzeige, Wiederaufnahme, Bedenkenanzeige -- auch für eine Mail an einen Beteiligten
  (Kopie). Eine neue Versandart bekommt ihn ohne Zutun; geht sie nur an Mitarbeiter, kommt sie nach `OHNE_FIRMENANGABEN`.
- Unverändert: die E-Mail-Vorlagen und ihre Vorgaben, das vorausgefüllte Textfeld vor dem Versand (der Schluss ist dort nicht zu sehen), die PDFs und die
  Ablage, das Versandprotokoll (speichert keinen Text, Regel 18). *Berichtigt 25.11.2026: ein Textfeld vor dem Versand gibt es nicht -- an den Versandstellen
  stehen nur „An“ und „CC“, den Text nimmt der Server aus der Vorlage (Umsetzung 1.11.19).*

Beispiel (erfundene Firmendaten, eine Angebotsmail aus `send_quote_email()` mit dem Text der Vorgabe):

    Sehr geehrte Damen und Herren,

    anbei erhalten Sie unser Angebot A-TEST-0001 über 148,75 €. Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF.

    Mit freundlichen Grüßen

    Muster Bedachung GmbH · Dachweg 1 · 12345 Musterstadt
    Sitz Musterstadt · Amtsgericht Musterstadt HRB 99999 · Geschäftsführer: Erika Beispiel

#### Festlegungen 1.11.17 (bestätigt am 25.11.2026)

1. Unter jede Mail an Kunden und Beteiligte setzt das ERP beim Senden nach einer Leerzeile „Name · Straße · PLZ Ort“ und darunter „Sitz <Ort> ·
   <Registergericht> <Registernummer> · Geschäftsführer: <Name(n)>“ aus den Firmendaten -- jede Versandart außer den Aufgaben-Mails.
2. Die Aufgaben-Mails an Mitarbeiter bleiben ohne (`OHNE_FIRMENANGABEN`).
3. Fehlt ein Feld, fällt nur dieses weg (wie 1.11.12-3); fehlt eine ganze Zeile, steht nur die andere; ohne jede Angabe bleibt die Mail ohne Schluss.
4. Leerraum am Ende des Texts fällt weg, dann genau eine Leerzeile vor dem Schluss.
5. Eine Quelle (`app/firmenangaben.py`) für die Zeilen unter den Mails des ERP und die Fußzeile der Mails des Portals.
6. Die Mails des Portals tragen die Angaben nur in ihrer HTML-Fußzeile, kein zweiter Schluss.
7. Vorlagen und Textfeld vor dem Versand bleiben ohne Schluss; er kommt erst beim Senden dazu.

*Berichtigt 25.11.2026:* Nr. 7 und die Frage 1.11.17-F1 nannten ein Textfeld vor dem Versand -- das gibt es nicht (Fehler im Bericht, beim Bau von 1.11.19
gefunden). Nr. 7 gilt für die Vorlagen; der Satz aus F1 steht seit 1.11.19 unter dem Text der Vorlagen (Umsetzung 1.11.19).

#### Tests und Prüfung 1.11.17

`tests/test_v813_firmenangaben_mails.py` (neu, 18): jede Versandart eingeordnet (ohne nur „aufgabe“), jede Versandart an Kunden mit genau dem Schluss, die
Aufgaben-Mail unverändert, fehlende Felder (4 Fälle, auch ohne jede Angabe), eine echte Angebotsmail aus `send_quote_email()` (das Beispiel oben), eine Quelle
für Portal und ERP, die Mail des Portals ohne Text-Schluss mit den Angaben in der HTML-Fußzeile. Angepasste Erwartungen (`tests/test_v393_ueberzahlung.py`):
`test_email_of_an_overpaid_final_invoice_names_the_refund` -- bis 1.11.16 war der letzte Absatz der Mail „Mit freundlichen Grüßen“, jetzt der letzte vor dem
Schluss (der Schluss gesondert geprüft); `test_custom_template_with_placeholder_gets_no_extra_paragraph_and_other_invoices_stay` -- bis 1.11.16 der Text genau
wie die Vorlage, jetzt Vorlage und Schluss (beide Fälle). Gegenproben: `gegenproben-portal.md`, „1.11.17“.

### Vorbereitung P1f: Server-Schritte und Datenschutz (24.11.2026, nur Doku)

Auf die Antwort vom 24.11.2026 („danach P1f vorbereiten, nichts auf dem Server“): die Server-Schritte S0–S10 aus dem Bauplan P1 (Abschnitt 2) als Befehle zum
Kopieren, je Schritt mit Erwartung, Abbruch und Rückweg (unten, „Server-Schritte P1“; dieselbe Datei als `server_schritte_p1_fc8b758.md` beim Bericht), und die
Stichpunkte für die Datenschutzerklärung des Portals als eigene Datei für den Webseiten-Chat (`datenschutz_portal_2026-11-24.md` beim Bericht). Nichts auf dem
Server ausgeführt, nichts am Code geändert.

- Abgeglichen mit dem Code von fc8b758 bis 1.11.18: Einheiten (`scripts/server/erp-portal.service`, `erp-portalpost.service`), `nginx-kunde.conf`,
  `portal-wartung.html`, `portal.env.beispiel`, `scripts/portal_rechte.py` (2 Tabellen, 8 Funktionen), `scripts/pruefe_portal_e4.py` (als Benutzer des ERP seit
  1.11.3-15), die Startprüfung des Portals (`Portal verbunden als …`), die Schranke (Host kunde, sonst 421 -- `/health` lokal deshalb mit `Host:`), die Texte der
  Seite und die Spalten von `failed_login_attempts`.
- Gegenüber dem Bauplan genauer: pg_hba auch für den Socket (`local … reject`); im Anlegen der Rolle zusätzlich `log_min_error_statement = 'panic'` (sonst stünde
  die Anweisung bei einem Fehler im Log) und `pg_stat_statements.track_utility = off`, psql mit `VERBOSITY=terse` (zeigt bei einem Fehler nie die Anweisung);
  S3b für PostgreSQL vor 15 (dort darf PUBLIC im Schema public anlegen -- `--pruefen` meldete das); `systemd-analyze verify` nicht für `erp-portal` (es suchte
  den Pfad im Dienst auf dem Rechner); der erfundene Link in S8 öffnet sich je Mal in einem neuen Tab (die Seite nimmt ihn sofort aus der Adresse).
- Lokal nachgeprüft (Git Bash, erfundene Daten): der Ausschnitt des Blocks für Port 80 (`listen 80;` einmal, `listen 443` keinmal, Zonen und Protokollformat
  dabei); die Ausgabe der Verbindungszeichenfolge ohne Passwort (auch mit „@“ im Passwort und ohne Passwort); das Einfügen der drei Zeilen vor die erste Regel
  von pg_hba.
- Datenschutz, gegenüber Abschnitt 6 des Bauplans und den Stichpunkten oben („Datenschutzerklärung (für den Webseiten-Chat)“): zwei Cookies statt eines
  (`__Host-dkportal-code` nur während der Anmeldung, 15 Minuten), der Speicher des Tabs während der Anmeldung (Schritt, verdeckte Adresse, Zeitpunkt der
  Anforderung), der Link gilt 12 Monate, höchstens 5 Fehlversuche je Code, die Mails nicht in „Gesendete Elemente“.

#### Festlegungen Vorbereitung P1f (bestätigt am 25.11.2026)

V1. pg_hba: drei Zeilen vor allen übrigen -- dkportal nur zu `dachkonzepte` über 127.0.0.1 mit scram-sha-256, jede andere Verbindung von dkportal (andere
    Datenbank, andere Adresse, Socket) `reject`.
V2. Das Passwort (40 Zeichen hexadezimal) entsteht in einer root-Shell, geht über stdin an psql und gleich in `/etc/dk-portal/portal.env`; in der Sitzung
    `log_statement = 'none'`, `log_min_error_statement = 'panic'`, `pg_stat_statements.track_utility = off`; psql `VERBOSITY=terse`.
V3. S3b nur, wenn S0 zeigt, dass PUBLIC im Schema public anlegen darf: dem Benutzer des ERP `CREATE` ausdrücklich, PUBLIC weg.
V4. Rechte des Portals in `update.sh` nur gegen `dachkonzepte`, nach `alembic current`, mit Abbruch vor dem Neustart; gegen `spielwiese` nichts.
V5. `update.sh` startet `erp`, `erp-portal` und `erp-portalpost` zusammen neu und prüft danach alle drei und `/health` des Portals.
V6. Der Nachweis E4 fürs ERP nimmt den erfundenen Benutzernamen `e4-probe` (zählt gegen kein echtes Konto).
V7. Die Datei für nginx heißt `/etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf`; zuerst nur der Block für Port 80 (für certbot), dann die ganze Datei.
V8. Datenschutz: zwei Cookies und der Speicher des Tabs, Link 12 Monate (statt „ein Cookie“ im Bauplan).

#### Tests und Prüfung Vorbereitung P1f

Keine Änderung am Code, kein Test. Gegenproben: keine möglich (eine Anleitung für den Server, sie wird in P1f auf dem Server geprüft) -- Tabelle mit Begründung in
`gegenproben-portal.md`, „Vorbereitung P1f“.

### Beim Abarbeiten geändert, Datenschutz durchgesehen (25.11.2026, nur Doku)

Antwort vom 25.11.2026: bestätigt 1.11.16-1 bis -7, 1.11.17-1 bis -7, die Festlegung zum Testablauf aus 1.11.18 und V1 bis V8. 1.11.17-F1: ja, ein Satz unter
dem Textfeld -- ein Textfeld vor dem Versand gibt es aber nicht (Fehler im Bericht 1.11.17); auf Rückfrage unter den Text der Vorlagen (1.11.19). F2 prüft der
Betrieb selbst. P1f-1: nach S9 das Modul „Kundenportal“ wieder aus, bis die Datenschutzerklärung online ist und der Betrieb
den ersten Kunden einlädt. P1f-2: der Unterschied von `update.sh` kommt nach S10.

Die Server-Schritte hat der Betrieb beim Abarbeiten so geändert (unten nachgezogen):

- S0 ohne die `sed`-Zeile auf `.env`: der Datenbank-Benutzer des ERP ist `erp`, die Datenbank `dachkonzepte`, PostgreSQL 18.6 -- S3b entfällt (ab 15 darf
  PUBLIC im Schema public nichts anlegen; die Abfrage in S0 bleibt als Nachweis).
- Zu Beginn jeder Sitzung `export SYSTEMD_PAGER=cat` -- `systemctl` öffnete sonst ein Blätterfenster und schnitt lange Zeilen ab.
- `journalctl` immer mit `sudo`. Unter `sudo` kommt `SYSTEMD_PAGER` nicht an (sudo setzt die Umgebung zurück); jedes `sudo journalctl` in den Schritten trägt
  deshalb `--no-pager` (stand dort schon).

Datenschutz: die Fassung vom 25.11.2026 (`datenschutz_portal_2026-11-25.md`, vom Betrieb durchgesehen, im Archiv der Berichte neben der vom 24.11.) ersetzt die
vom 24.11.; drei Stellen berichtigt -- der Name des Verantwortlichen (wie im Impressum der Webseite); der Link geht zur Prüfung verschlüsselt (HTTPS) an den
Server, nur nicht als Teil der aufgerufenen Adresse (die Fassung vom 24.11. sagte „nie an den Server als Adresse übertragen“ -- missverständlich); der Prüfwert
der IP-Adresse (HMAC mit Schlüssel) ist eine Pseudonymisierung und gilt weiter als personenbezogen (die Fassung vom 24.11. sagte „nicht umkehrbar“).

### Umsetzung 1.11.19: Satz unter den Mailvorlagen (Antwort 1.11.17-F1)

Beim Bau gefunden: ein Textfeld vor dem Versand, wie Bericht und Festlegung 7 zu 1.11.17 es nannten, gibt es nicht -- an den acht Versandstellen (Angebot,
Auftrag, Rechnung, Mahnung, Vertrag, Checkliste, Anzeigen, Abnahmeprotokoll) stehen nur „An“ und „CC“, den Text nimmt der Server aus der Vorlage
(`*EmailSend` ohne Text). Geschrieben wird der Mailtext nur in den Einstellungen. Rückfrage beim Betrieb am 25.11.2026: der Satz unter die Vorlagen.

- Einstellungen → E-Mail-Vorlagen: direkt unter dem Feld „Text“ „Darunter setzt das ERP beim Senden Name, Anschrift und Pflichtangaben aus den Firmendaten.“ -- für jede Art der Auswahl, auch die Mahnstufen.
- Einstellungen → Mahnwesen: derselbe Satz direkt unter „E-Mail-Text“ jeder Stufe.
- Der Satz steht immer: für jede Rolle der Seite, bei gesperrtem Feld (Büro – Auftrag bei den Mahnstufen) und ohne Firmendaten (dann setzt das ERP nichts --
  „aus den Firmendaten“). Nicht an den Versandstellen.

#### Festlegungen 1.11.19 (bestätigt am 25.11.2026)

1. Unter dem Feld „Text“ der E-Mail-Vorlagen der Satz „Darunter setzt das ERP beim Senden Name, Anschrift und Pflichtangaben aus den Firmendaten.“ -- für jede Art der Auswahl, auch die Mahnstufen.
2. Derselbe Satz unter „E-Mail-Text“ jeder Mahnstufe (Einstellungen → Mahnwesen).
3. Der Satz steht immer -- auch bei gesperrtem Feld und ohne Firmendaten.
4. Er gilt für jede Art der Auswahl: keine davon geht ohne Schluss hinaus (ohne nur die Aufgaben-Mails, die hier keine Vorlage haben).
5. Nur dort -- nicht an den Versandstellen (Antwort 25.11.2026).

#### Tests und Prüfung 1.11.19

`tests/test_v814_mail_schluss_hinweis.py` (neu, 8): der Satz direkt unter „Text“ der Vorlagen (Admin, Büro – Finanzen, Büro – Auftrag) und unter „E-Mail-Text“ der
Mahnstufe (Admin, Büro – Auftrag), ohne Firmendaten, jede Art der Auswahl eine Mail an Kunden, der Satz in keiner anderen Vorlage. Klicktest
`scripts/klicktest_mail_schluss.py` (neu, 9 Prüfungen): sichtbar, höchstens 12 px unter dem Feld, dieselbe linke Kante -- Admin für Angebot, eine Mahnstufe und
jede Stufe unter „Mahnwesen“, Büro – Auftrag bei gesperrtem Feld; ohne Firmendaten; Bilder hell und dunkel. Keine angepasste Erwartung. Gegenproben:
`gegenproben-portal.md`, „1.11.19“.

### Umsetzung 1.11.20: nginx des Kundenportals nur über IPv4 (S0, 25.11.2026)

Beim Abarbeiten von S0 hat der Betrieb gesehen: nginx lauscht auf dem Server nur auf `0.0.0.0:80` und `0.0.0.0:443`, nicht auf `[::]`, und es gibt keine
AAAA-Einträge (app, web, www, kunde). Der Block des Portals lauschte zusätzlich auf `[::]:80` und `[::]:443`, S0 erwartete `[::]` und brach sonst ab, S1 legte für
kunde einen AAAA-Eintrag an, wenn app einen hat. Auf Wunsch des Betriebs (eine kleine Version, vor S7 eingespielt):

- `scripts/server/nginx-kunde.conf`: je Block nur `listen 80;` bzw. `listen 443 ssl http2;`, ein Kommentar im Kopf sagt warum. Der Kommentar nennt weder
  „listen 80;“ noch „listen 443“ -- S7 zählt mit `grep -c` im ersten Teil der Datei (`1` und `0`), Kommentare eingeschlossen.
- Server-Schritte: S0 erwartet nginx nur auf `0.0.0.0` und bricht nicht mehr ab, wenn `[::]` fehlt; S1 legt für kunde keinen AAAA-Eintrag an und bricht ab, wenn
  einer da ist; S7 prüft zuerst, dass auf dem Server 1.11.20 liegt und die Datei nur die beiden Zeilen `listen` hat.
- Nicht geändert: gunicorn vertraut `X-Forwarded-For` weiter von 127.0.0.1 und ::1 (Vorgabe von gunicorn 26) -- nginx spricht den Dienst über 127.0.0.1 an.

#### Festlegungen 1.11.20 (bestätigt am 25.11.2026)

1. Der Block des Portals lauscht nur über IPv4 -- `listen 80;` und `listen 443 ssl http2;`, wie die übrigen Seiten des Servers; keine Zeile für `[::]`.
2. S1: für kunde kein AAAA-Eintrag; zeigt `dig` einen, abbrechen und bei Ionos löschen.
3. S0 erwartet nginx nur auf `0.0.0.0:80` und `0.0.0.0:443`; fehlt `[::]`, ist das kein Grund mehr abzubrechen.
4. S7 beginnt mit der Prüfung, dass auf dem Server 1.11.20 oder später liegt (nur die beiden Zeilen `listen`).
5. Bekommt der Server später IPv6 (AAAA für app), kommen `listen [::]` im Block des Portals und der AAAA-Eintrag für kunde zusammen in einer eigenen Version.

#### Tests und Prüfung 1.11.20

`tests/test_v815_nginx_nur_ipv4.py` (neu, 3): je Block genau eine Zeile `listen` (80 bzw. 443 ssl http2); keine Adresse `[::]` und kein `ipv6only` außerhalb der
Kommentare; der erste Teil der Datei wie in S7 (`awk` bis zum zweiten `server {`) zählt mit `grep -c` `1` und `0`. Keine Seite geändert, kein Klicktest berührt.
Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.20“. Im ersten vollen Lauf ein Wackler ohne Bezug (`test_v352`, feste Pause vor dem
Schließen einer Sitzung, die noch committet; laufende Liste im Archiv „Testablauf“), nicht behoben.

### Umsetzung 1.11.21: das Skript für die Rechte des Portals bricht nicht mehr ab (S5, 25.11.2026)

Betreiberangabe 25.11.2026, S5 auf dem Server: `scripts/portal_rechte.py --setzen` brach ab, nichts gesetzt (danach 0 Spalten, 0 Funktionen für dkportal) --

    File "/home/tobias/erp/scripts/portal_rechte.py", line 53, in main
      with conn.begin():
    sqlalchemy.exc.InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction() object
    via begin() or autobegin; can't call begin() here unless rollback() or commit() is called first.

Aufruf wie in S5 (im Repo-Ordner, `.env` geladen, `alembic current` = `heads` = `c8e2f5a1d394`, Python 3.14, Pakete aus `.venv`); S0–S4 erledigt, die Rolle
dkportal neu und ohne Rechte, pg_hba wie V1, `portal.env` vollständig.

**Ursache.** Das Skript las `SELECT current_database()` auf der Verbindung und rief danach `conn.begin()` auf. SQLAlchemy 2 beginnt eine Transaktion mit der
ersten Anweisung selbst (autobegin); ein `begin()` danach lehnt es ab. Der Fehler kam vor dem ersten GRANT, die Verbindung rollte beim Schließen zurück --
deshalb nichts gesetzt, nichts aufzuräumen. Lokal nachgestellt (SQLAlchemy 2.0.52, Python 3.13): dieselbe Meldung -- die Version von Python spielt keine Rolle.

**Behebung.** `--setzen` öffnet die Transaktion vor der ersten Anweisung (`with engine.begin() as conn:`), liest den Namen der Datenbank darin und committet
nur, wenn alles gesetzt ist. `--pruefen` unverändert (liest, rollt zurück).

**Warum die bisherigen Tests es nicht fanden.** `tests/test_v799_portal_rechte.py` prüft `rechte.setzen()` und `rechte.pruefen()` gegen PostgreSQL, ruft sie
aber selbst in einer eigenen Transaktion auf (`with engine.begin() as c: rechte.setzen(c, …)`) -- die Logik war geprüft, der Rahmen des Skripts nicht. Das
Skript selbst lief in Tests nur ohne `DATABASE_URL` bzw. mit SQLite: dort gibt es vor jeder Verbindung 2 zurück. Die Aufbauten von test_v800, test_v805 und
`klicktest_portal_seiten` setzen die Rechte ebenso über die Funktion. Bei der Vorbereitung von P1f habe ich das Skript mit dem Code abgeglichen („2 Tabellen,
8 Funktionen“), aber nicht laufen lassen -- jeder echte Aufruf gegen eine Datenbank hätte den Fehler gezeigt.

**Dasselbe Muster anderswo?** Gesucht: jedes `begin()` auf einer Verbindung oder Sitzung unter `app/` und `scripts/` (außer `engine.begin()` und
`begin_nested()`) -- außer dieser Stelle keins. Die beiden anderen Skripte, die in P1f zum ersten Mal echt laufen:

- `scripts/pruefe_portal_e4.py` (S8): nur eine Sitzung, die liest und am Ende zurückrollt (`nur_lesende_sitzung()` aus `pruefe_stornos.py`), kein `begin()`.
  Getestet war es bisher nur mit SQLite und einer übergebenen Sitzung (`test_v802_portal_sitzung.py::test_pruefskript_e4_nennt_nur_zahlen`), nie über
  `DATABASE_URL` gegen PostgreSQL.
- Der Postbote (`scripts/portal_postbote.py`, S6): eine eigene Verbindung mit AUTOCOMMIT für Sperre und LISTEN, die Arbeit in Sitzungen mit commit/rollback,
  kein `begin()`. `laufen()` ist gegen PostgreSQL getestet (`test_v805_portal_postbote.py`, im Testprozess); das Skript selbst nur ohne Datenbank.
- Einmal geprüft, beide als Kindprozess wie auf dem Server (Python aus `.venv`, im Repo-Ordner, `DATABASE_URL` aus der Umgebung), gegen PostgreSQL in einem
  Wegwerf-Schema aus `alembic upgrade head` (dieselbe Revision `c8e2f5a1d394`), eigener `ERP_DATA_DIR`: `pruefe_portal_e4.py` ohne Aufrufe Rückgabe 1 „0
  Anschlüsse … Noch kein Aufruf“, mit zwei erfundenen Anschlüssen Rückgabe 0 „2 Anschlüsse, 4 Aufrufe“; der Postbote „Postbote bereit (LISTEN portal_post)“ und
  „aufgeräumt {…: 0}“, ein zweiter daneben Rückgabe 3 „Es läuft schon ein Postbote“; danach den ersten über seine PID beendet. Nicht als Test im Repo (Frage im
  Bericht).

Nebenbefund: auf dem Server Python 3.14, lokal 3.13 (`.venv`) -- hier ohne Folge, festgehalten.

#### Festlegungen 1.11.21 (bestätigt am 25.11.2026)

1. `scripts/portal_rechte.py --setzen` läuft von der ersten Anweisung an in einer Transaktion (`engine.begin()`, der Name der Datenbank darin); `--pruefen`
   unverändert.
2. Ein Test ruft das Skript wie in S5 als Kindprozess auf -- `--setzen`, dann `--pruefen`, zweimal wie `update.sh` bei jedem Einspielen --, gegen PostgreSQL
   in einem Schema aus `alembic upgrade head`, mit der Testrolle ohne Rechte im Schema; geprüft wie in S5: Rückgaben, Ausgaben, danach 9 Spalten und 8
   Funktionen.

#### Tests und Prüfung 1.11.21

`tests/test_v816_portal_rechte_skript.py` (neu, 1): vorher 0 Spalten und 0 Funktionen, `--pruefen` Rückgabe 1 mit Abweichungen; dann zweimal `--setzen`
(Rückgabe 0, „Rechte für dkportal_test gesetzt: 2 Tabellen (nur Lesen), 8 Funktionen, …“) und `--pruefen` (Rückgabe 0, „… stimmen.“), danach 9 und 8; keine
Ausgabe nennt die Verbindungszeichenfolge. Zur Abgrenzung mit `--rolle dkportal_test --schema <Wegwerf-Schema>` (auf dem Server die Vorgaben dkportal und
public); `--setzen` gibt der Testrolle auch CONNECT auf die Spielwiese (wie auf dem Server auf `dachkonzepte`; die Rolle ist NOLOGIN). Vor der Behebung rot mit
genau der Meldung vom Server. Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.21“.

### Umsetzung 1.11.22: gunicorn ohne Steuer-Socket (S6, 25.11.2026)

Betreiberangabe 25.11.2026, S6 auf dem Server: beide Dienste liefen -- Postbote bereit; Portal verbunden als dkportal, `/health` ok, 421 ohne den Namen
kunde, je rund 100 MB, `systemd-analyze security` 1.7 OK. Im Journal des Portals eine Zeile:

    [ERROR] Control server error: [Errno 30] Read-only file system: '/home/dkportal'

**Ursache.** gunicorn öffnet seit 25.1.0 ab Werk einen Steuer-Socket für `gunicornc` (Konfiguration zeigen, Arbeitsprozesse dazu oder weg, Neustart, Ende):
`$XDG_RUNTIME_DIR/gunicorn.ctl`, sonst `$HOME/.gunicorn/gunicorn.ctl`; den Ordner legt er selbst an (0700, der Socket 0600). Der Hauptprozess startet ihn in
einem eigenen Faden, nachdem die Arbeitsprozesse laufen (`Arbiter._start_control_server`); scheitert er, schreibt der Faden die Zeile oben, und der Dienst
läuft ohne ihn weiter. Im Portal gibt es kein `$XDG_RUNTIME_DIR` (Systemdienst), `$HOME` ist `/home/dkportal`, und `/home` ist leer und nur lesbar
(`ProtectHome=tmpfs`). Im ERP (Benutzer tobias, ohne ProtectHome) liegt er vermutlich unter `/home/tobias/.gunicorn/gunicorn.ctl` -- jeder Prozess als tobias
(auch Postbote und Abholer der Webanfragen) könnte darüber Arbeitsprozesse anlegen oder wegnehmen, neu starten oder den Dienst beenden. Gebraucht wird er
nirgends: Neustart und Ende laufen über `systemctl`.

**Behebung.** Die Einheit des Portals startet gunicorn mit `--no-control-socket` -- in gunicorn 26.2.0 so benannt, im Quelltext geprüft: Einstellung
`control_socket_disable` (`config.py::ControlSocketDisable`, `store_true`, seit 25.1.0), mit ihr kehrt `arbiter.py::_start_control_server` sofort zurück. Ein
Kommentar im Kopf der Einheit sagt warum. Fürs ERP dieselbe Option am Ende von `ExecStart` in `/etc/systemd/system/erp.service` -- die Datei liegt nur auf dem
Server, der Betrieb ändert sie (S6b, Teil 1). `update.sh` installiert keine Einheiten: nach dem Einspielen von 1.11.22 kommt die Einheit des Portals einmal
von Hand nach `/etc/systemd/system` (S6b, Teil 2, mit S10).

**Geprüft wird der echte Weg.** `tests/gunicorn_wie_auf_dem_server.py` gibt die Argumente aus ExecStart wie bisher durch den Parser von gunicorn und ruft dann
`Arbiter._start_control_server` mit dieser Konfiguration auf -- statt des Servers eine Attrappe, die nur festhält, ob er gestartet würde (kein Socket, kein
Ordner, auch unter Windows). Ohne die Option meldet sie den Start (Gegenprobe).

#### Festlegungen 1.11.22 (bestätigt am 25.11.2026)

1. Die Einheit des Portals startet gunicorn mit `--no-control-socket` -- kein Steuer-Socket; Neustart und Ende nur über `systemctl`.
2. Geprüft wird der Weg des Hauptprozesses (`Arbiter._start_control_server`) mit der Konfiguration aus ExecStart, mit einer Attrappe statt des Servers
   (`test_v803`); dazu die Option in der Einheit selbst (`test_v801`).
3. Das ERP bekommt dieselbe Option am Ende von `ExecStart` in `erp.service`, auf dem Server von Hand (S6b, Teil 1), sonst nichts an der Datei; ohne Test (die
   Datei liegt nicht im Repo).
4. Nach dem Einspielen von 1.11.22 wird `erp-portal.service` einmal neu installiert (S6b, Teil 2) -- `update.sh` holt die Datei, installiert sie aber nicht.

#### Tests und Prüfung 1.11.22

`tests/test_v803_gunicorn_server.py::test_kein_steuer_socket` (neu): der Hauptprozess startet den Steuer-Socket nicht, `control_socket_disable` ist gesetzt,
die Option steht in ExecStart, die Ausgabe von gunicorn nennt keinen Steuer-Socket. `test_v801_portal_dienst.py::test_einheit_des_dienstes` prüft dazu die
Option in ExecStart. Keine Seite geändert, kein Klicktest berührt. Keine angepasste Erwartung. Gegenproben: `gegenproben-portal.md`, „1.11.22“.

### P1f auf dem Server abgearbeitet (Antwort des Betriebs, 25.11.2026)

S0–S10 sind erledigt, das Kundenportal läuft unter kunde.dachkonzepte.gmbh (das Modul im ERP ist nach dem Rauchtest wieder aus). Bestätigt: 1.11.21-1 und -2,
1.11.22-1 bis -4. F1 (Tests als Kindprozess für `pruefe_portal_e4.py` und den Postboten, nach P1f) und F2 (`update.sh` vergleicht die Einheiten und meldet
Abweichungen mit dem Befehl, installiert nicht selbst; Wortlaut als Server-Schritt, Python-Ersetzung wie in S10, nur bei eindeutiger Stelle): beide ja.

Ausgaben (ohne Geheimnisse):

- **S0:** Ubuntu 26.04.1, systemd 259, PostgreSQL 18.6, nginx 1.28.3; 2443 MB verfügbar; nginx nur über IPv4 (daher 1.11.20); `.env` 600. PostgreSQL:
  `log_statement` none, `log_min_duration_statement` -1, `scram-sha-256`, `localhost`, 5432, keine preload-Bibliotheken; erp `f|f|f`; PUBLIC CREATE `f`. ufw
  22/80/443; nginx `daily`/`rotate 14`; Journal `14day`.
- **Dazu, über den Plan hinaus:** `/etc/logrotate.d/rsyslog` von `weekly`/`rotate 4` auf `daily`/`rotate 14` (syslog, mail, kern, auth, user, cron), Dateien
  älter als 15 Tage gelöscht -- „höchstens 15 Tage“ gilt damit für jedes Protokoll des Servers, so steht es in der Datenschutzerklärung.
- **S1:** kunde A 212.132.105.140, kein AAAA, kein CAA.
- **S2:** dkportal uid 994, nologin; `.env` nicht lesbar; Probelauf wie erwartet.
- **S3:** Rolle `f|f|f|f|f|f|10`; 5s/15s/public; pg_hba drei Zeilen vorn; spielwiese und `[local]` abgelehnt, dachkonzepte bis zur Passwortprüfung; ERP ok.
- **S4:** `64` / `1` / `640 root:dkportal`.
- **S5** (nach 1.11.21): 32 Anweisungen, „stimmen“, 9 und 8.
- **S6:** Postbote bereit; Portal verbunden als dkportal, Revision `c8e2f5a1d394`; `{"ok":true}`; 421; MemoryCurrent 95 bzw. 105 MB; `systemd-analyze
  security` 1.7 OK. Im Journal des Portals „Control server error“ -- daraus 1.11.22.
- **S6b** (1.11.22): Portal neu installiert, danach kein „Control server error“. ERP ohne Drop-ins; danach kein „Control socket listening“, `ss -lx` 0,
  `/home/tobias/.gunicorn` gelöscht. Die Zeile des ERP seither:

      ExecStart=/home/tobias/erp/.venv/bin/gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 --timeout 120 --no-control-socket

- **S7:** Zertifikat bis 23.02.2027 (ECDSA); alle Schutz-Kopfzeilen; `/` 200, `/api/customers` 404, `/docs` 404, DELETE 405, ERP 200; Wartungsseite bei 502;
  `certbot renew --dry-run` ok; certbot.timer da.
- **S8 (E4):** Portal „2 Anschlüsse, 4 Aufrufe“; ERP `2|0` -- beide sehen die Adresse des Geräts, nicht die von nginx.
- **S9:** wie beschrieben; keine Mail unter „Gesendete Elemente“. Die Rohdaten zeigen innerhalb des Kontos `application/ms-tnef` (Exchange stellt intern im
  eigenen Format zu) -- ob ein Textteil dazukommt, zeigt erst eine Mail an eine Adresse außerhalb: **offen** (beantwortet am 26.11.2026, „Nachtrag P1f“).
- **S10:** `update.sh` per Python-Ersetzung an fünf Stellen geändert (Sicherung `update.sh.vor-p1`); Probelauf und Einspielen von 1.11.22: Rechte gesetzt und
  stimmen, „FERTIG … ERP und Kundenportal laufen“. **Abweichung vom Vorschlag, zu Recht:** `systemctl is-active` mit mehreren Namen gibt 0 zurück, sobald einer
  läuft -- mein Schritt 3 hätte ein stehendes Portal übersehen. Der Betrieb prüft jeden Dienst einzeln (S10 unten nachgezogen). Der Unterschied:

    @@ -110,23 +110,33 @@
    +echo "=== Rechte Kundenportal ==="
    +PHASE="Rechte Kundenportal"
    +if ! ( set -a; . ./.env; set +a; .venv/bin/python scripts/portal_rechte.py --setzen && .venv/bin/python scripts/portal_rechte.py --pruefen ); then
    +    echo "!!! Rechte des Kundenportals stimmen nicht -- Abbruch vor dem Neustart. Ausgabe an Claude schicken."
    +    exit 1
    +fi
    +
     echo "=== Neustart ==="
    -sudo systemctl restart erp
    +sudo systemctl restart erp erp-portal erp-portalpost
    -    if systemctl is-active --quiet erp && curl -fsS --max-time 5 -o /dev/null "$HEALTH_URL"; then
    +    if systemctl is-active --quiet erp && systemctl is-active --quiet erp-portal && systemctl is-active --quiet erp-portalpost \
    +       && curl -fsS --max-time 5 -o /dev/null "$HEALTH_URL" \
    +       && curl -fsS --max-time 5 -o /dev/null -H "Host: kunde.dachkonzepte.gmbh" http://127.0.0.1:8010/health; then
    -    echo "!!! Das ERP antwortet nach 60 Sekunden nicht auf $HEALTH_URL. Letzte Meldungen:"
    -    sudo journalctl -u erp -n 30 --no-pager || true
    +    echo "!!! ERP oder Kundenportal antworten nach 60 Sekunden nicht. Stand und letzte Meldungen:"
    +    systemctl is-active erp erp-portal erp-portalpost || true
    +    sudo journalctl -u erp -u erp-portal -u erp-portalpost -n 40 --no-pager || true
    -echo "=== FERTIG: $ALT -> $NEU, Datenbank $AKTUELL, ERP laeuft ==="
    +echo "=== FERTIG: $ALT -> $NEU, Datenbank $AKTUELL, ERP und Kundenportal laufen ==="

- Die Datenschutzerklärung 2026-11-25a mit Abschnitt 7 „Kundenportal“ ist live.

Danach als eigene kleine Versionen, in dieser Reihenfolge (Betreibervorgabe): 1. Begrüßung ohne Komma überall -- im Portal „Guten Tag Herr Dr. Muster“, in den
Mails „Guten Tag Herr Dr. Muster,“; 2. Knopf „Kundenportal öffnen“ als Tabellenzelle mit Polster (Outlook am Rechner zeigt nur grün hinterlegten Text); 3. F1,
dazu die Wackler `test_v352`, `klicktest_kennzeichen_entziehen` und `klicktest_nach_dem_versand_pruefen`; 4. F2 (Vergleich der Einheiten in `update.sh`, Wortlaut
als Server-Schritt); 5. lokal Python 3.14 wie auf dem Server (Grundsatz wie 1.11.4), mit Bericht.

### Umsetzung 1.11.23: Begrüßung ohne Komma (25.11.2026)

Betreibervorgabe 25.11.2026 (nach P1f, Nr. 1): die Begrüßung überall ohne Komma nach „Guten Tag“ -- im Portal „Guten Tag Herr Dr. Muster“, in den Mails
„Guten Tag Herr Dr. Muster,“. Die freigegebenen Entwürfe (`bildgrundlage/entwurf-p1/`, Portal und Mails) zeigen noch das Komma; maßgeblich ist diese Vorgabe.

- `app/portal/begruessung.py` bildet die Begrüßung mit Namen, jetzt ohne Komma nach „Guten Tag“; die Regeln bleiben (Herr/Frau mit Titel und Nachname, Firma
  mit dem Namen, sonst Titel, Vor- und Nachname, ohne Namen „Guten Tag“). Die Mails des Portals hängen wie bisher nur das Komma ans Ende
  (`app/portal_mails.py::anrede()`, ohne Namen „Guten Tag,“).
- Sonst beginnt im ERP nur der Brief einer Anzeige bei „Divers“ mit „Guten Tag“ (`app/notice_letters.py::salutation_line()`: „Guten Tag <Titel Vorname
  Nachname>,“) -- schon ohne Komma. Die übrigen Kundentexte beginnen mit „Sehr geehrte …“; die Vorgabe betrifft sie nicht.
- Wächter `tests/test_v817_begruessung_ohne_komma.py`: kein Text unter `app/` setzt ein Komma zwischen „Guten Tag“ und einen Namen oder Platzhalter, auch nicht
  über die Konstante (`{GRUSS},`); dazu Portal, Mail und Brief bei „Divers“.

#### Festlegungen 1.11.23 (bestätigt am 26.11.2026)

1. Nach „Guten Tag“ steht kein Komma: im Portal „Guten Tag Herr Dr. Muster“, in den Mails „Guten Tag Herr Dr. Muster,“ (das Komma nur am Ende der Zeile); ohne
   Namen „Guten Tag“ bzw. „Guten Tag,“.
2. Kein Text unter `app/` setzt ein Komma zwischen „Guten Tag“ und einen Namen oder Platzhalter (Wächter `test_v817`).

#### Tests und Prüfung 1.11.23

Angepasste Erwartungen, je nur das Komma nach „Guten Tag“ (alt „Guten Tag, Herr Dr. Muster“, neu „Guten Tag Herr Dr. Muster“):
`test_v802_portal_sitzung.py::test_begruessung` (10 Fälle mit Namen) und die Antwort von „Willkommen“ in `test_pg_ganzer_ablauf` (1) und `test_pg_eine_sitzung_je_browser` (2);
`test_v804_portal_mails.py::test_mails_gesiezt_mit_hinweis_und_absender` (3 Fälle, mit Komma am Ende); `test_v807_portal_mails_html.py` (Wortlaut beider
Mails); `scripts/klicktest_portal_seiten.py` (drei Prüfungen: „Guten Tag Herr Dr. Muster“, „Guten Tag Alex Beispiel“, „Guten Tag Herr Langsam“, dazu der
Kopf der Datei). Neu `test_v817` (13). Klicktests vor dem Commit: `klicktest_portal_seiten`, `klicktest_kundenportal_karte`. Gegenproben:
`gegenproben-portal.md`, „1.11.23“.

### Umsetzung 1.11.24: Knopf der Mail als Tabellenzelle mit Polster (25.11.2026)

Betreibervorgabe 25.11.2026 (nach P1f, Nr. 2): Outlook am Rechner zeigte den Knopf „Kundenportal öffnen“ nur als grün hinterlegten Text ohne Polster. Ursache:
Polster und `display:inline-block` standen am Link (`<a>`), die Zelle darum hatte nur den Hintergrund. Outlook am Rechner zeichnet Mails mit Word und kennt an
einem Link weder `padding` noch `inline-block` -- die Zelle war dort so groß wie der Text.

- `app/portal_mails.py::_knopf()`: Polster (`14px 24px`), Hintergrund und Ecken an der Zelle (`<td align="center">`), der Link trägt nur Schrift, Farbe und
  „keine Unterstreichung“. In Browsern und Apps sieht der Knopf aus wie bisher; klickbar ist dort jetzt nur der Text, nicht mehr die ganze Fläche (der Preis
  dafür, dass jedes Programm die Zelle gleich zeichnet). Die runden Ecken zeigt Outlook am Rechner weiter nicht (eckig).
- Wortlaut, Farben und Maße unverändert; kein neues Attribut (die Liste der erlaubten Attribute in `test_v807` bleibt).
- Hier nicht prüfbar: wie Outlook am Rechner den Knopf zeigt -- das zeigt erst ein Link an das eigene Postfach nach dem Einspielen (wie S9, Schritt 3–4).

#### Festlegungen 1.11.24 (nicht bestätigt -- geändert am 26.11.2026, siehe 1.11.28)

1. Der Knopf einer Mail des Portals ist eine Tabellenzelle mit Polster und Hintergrund; der Link darin trägt nur Schrift und Farbe (kein Polster, kein
   Hintergrund, kein `display`).

#### Tests und Prüfung 1.11.24

Neu `test_v807_portal_mails_html.py::test_knopf_polster_an_der_zelle`: der Link steht direkt in einer Zelle mit `padding:14px 24px` und Hintergrund, der Link
selbst ohne Polster, Hintergrund und `display`, weiß und ohne Unterstreichung. Keine angepasste Erwartung. Klicktests vor dem Commit:
`klicktest_kundenportal_karte` (versendet den Link über die Attrappe von Graph). Gegenproben: `gegenproben-portal.md`, „1.11.24“.

### Umsetzung 1.11.25: e4 und Postbote als Kindprozess, Wackler (25.11.2026)

Antwort auf F1 (aus 1.11.21): ja, nach P1f, zusammen mit den Wacklern `test_v352`, `klicktest_kennzeichen_entziehen` und
`klicktest_nach_dem_versand_pruefen`.

- Neu `tests/test_v818_portal_skripte_kindprozess.py`: `scripts/pruefe_portal_e4.py` (S8) und `scripts/portal_postbote.py` (S6) laufen wie auf dem Server
  -- Python aus `.venv`, im Repo-Ordner, `DATABASE_URL` aus der Umgebung -- gegen PostgreSQL in einem Wegwerf-Schema aus `alembic upgrade head`. e4: ohne
  Aufruf Rückgabe 1 („0 Anschlüsse, 0 Aufrufe“, „Noch kein Aufruf“), mit zwei erfundenen Anschlüssen Rückgabe 0 („2 Anschlüsse, 4 Aufrufe“); Postbote:
  „bereit“ und „aufgeräumt“, ein zweiter daneben Rückgabe 3, der erste über seine PID beendet. Keine Ausgabe nennt die Verbindungszeichenfolge. Damit läuft
  jedes Skript, das die Server-Schritte P1 nennen, in einem Test als Kindprozess gegen PostgreSQL (`portal_rechte.py` seit 1.11.21).
- `test_v352` und die übrigen acht Tests mit `_waits_for()`: Archiv „Testablauf“, „Umsetzung 1.11.25“.
- Die beiden Klicktests: Befund „Stille Verbindungen (1.11.25)“ im Archiv „Testablauf“, keine Änderung am Werkzeug.

#### Festlegungen 1.11.25 (bestätigt am 26.11.2026)

1. `pruefe_portal_e4.py` und der Postbote laufen in einem Test als Kindprozess wie auf dem Server (S6, S8), gegen PostgreSQL in einem Schema aus
   `alembic upgrade head`.
2. `_waits_for()` gibt die erste Aktion erst frei, wenn eine Verbindung des Tests nachweislich an einer Sperre wartet, wartet danach auf beide Fäden und
   prüft keine Dauer -- für alle neun Tests in v349, v351, v352, v354, v356.
3. Bei „Anfrage nicht angekommen“ bleibt das Werkzeug, wie es ist (Wiederholung); der Befund „stille Verbindung“ steht im Archiv, mit dem Weg, ihn im
   Verbindungsprotokoll zu prüfen.

#### Tests und Prüfung 1.11.25

Neu `test_v818` (2). Angepasste Erwartungen (Regel 28): in den neun Tests mit `_waits_for()` entfällt „zweite Aktion ≥ 0,9 s“ (alt: Dauer gegen eine feste
Schranke; neu: `_waits_for()` prüft, dass eine Verbindung des Tests an einer Sperre gewartet hat), ebenso die festen Pausen vor `holder.close()`; in
`test_v349::test_postgresql_sync_waits_for_a_running_acceptance` die Pause vor der Prüfung der ersten Aktion (jetzt `join`). Keine Seite geändert, kein
Klicktest berührt. Gegenproben: `gegenproben-portal.md`, „1.11.25“.

### Umsetzung 1.11.26: update.sh vergleicht die Einheiten (25.11.2026)

Antwort auf F2 (aus 1.11.22): `update.sh` vergleicht die Einheiten und meldet Abweichungen mit dem Befehl, installiert nicht selbst; Wortlaut als
Server-Schritt, Python-Ersetzung wie in S10, nur bei eindeutiger Stelle.

- Der Vergleich liegt als Skript im Repo, `update.sh` ruft es nur auf: `scripts/pruefe_einheiten.py` vergleicht jede Einheit aus `scripts/server/`
  (`*.service`, `*.timer`) Byte für Byte mit `/etc/systemd/system/<Name>` und meldet jede, die abweicht, fehlt oder nicht lesbar ist -- mit „Ansehen:
  diff -u …“ und „Übernehmen: sudo install … && sudo systemctl daemon-reload && sudo systemctl restart <Einheit>“ (ein Dienst mit gleichnamigem Timer ohne
  Neustart, er läuft über den Timer). Es installiert nichts, startet nichts neu und schreibt nichts; Rückgabe 1 bei einer Abweichung, `update.sh` fährt fort.
  Nur Standardbibliothek, keine Datenbank, keine Umgebung. So ist der Vergleich getestet, und eine Änderung daran kommt über Git -- in `update.sh` steht nur
  der Aufruf.
- `scripts/server/update_einheiten_einfuegen.py` fügt den Aufruf einmal vor der Zeile FERTIG ein, nur wenn sie genau einmal dasteht (sonst Rückgabe 1,
  nichts geändert); steht er schon drin, ändert es nichts. Dieselbe Datei, nur der Inhalt (Rechte bleiben).
- Server-Schritt S11 unten.

#### Festlegungen 1.11.26 (bestätigt am 26.11.2026)

1. `update.sh` meldet vor FERTIG jede Einheit aus `scripts/server/`, die von der installierten abweicht, fehlt oder nicht lesbar ist, mit dem Befehl zum
   Ansehen und zum Übernehmen; es installiert, startet und schreibt nichts (`scripts/pruefe_einheiten.py`).
2. Der Vergleich liegt als Skript im Repo; `update.sh` enthält nur den Aufruf, eingefügt von `scripts/server/update_einheiten_einfuegen.py` nur vor genau
   einer Zeile FERTIG.
3. Ein Dienst mit gleichnamigem Timer bekommt im Befehl keinen Neustart (er läuft über den Timer).

#### Tests und Prüfung 1.11.26

Neu `tests/test_v819_einheiten_vergleichen.py` (9): die vier Einheiten des Repos; alle gleich Rückgabe 0; abweichend und fehlend mit Befehlen, Rückgabe 1,
der Ordner der installierten Einheiten unverändert; Dienst mit Timer ohne Neustart; als Kindprozess aus einem anderen Ordner; Einfügen vor FERTIG, ein
zweites Mal ohne Änderung, bei 0 oder 2 Zeilen FERTIG oder Windows-Zeilenenden Rückgabe 1 ohne Änderung. Dazu einmal von Hand: `bash -n` auf einer
nachgebauten `update.sh` nach dem Einfügen (Git Bash). Keine angepasste Erwartung, keine Seite, kein Klicktest. Gegenproben: `gegenproben-portal.md`,
„1.11.26“.

### Umsetzung 1.11.27: lokal Python 3.14 wie auf dem Server (25.11.2026)

Betreibervorgabe 25.11.2026 (nach P1f, Nr. 5), Grundsatz wie 1.11.4: die Suite läuft mit der Version des Servers. Auf dem Server läuft Python 3.14
(S5), lokal lief bis hierher 3.13.15.

- Installiert: Python 3.14.10 für Windows, der neueste Fehlerstand mit Installer auf python.org (Signatur der Python Software Foundation geprüft), nur für
  den Benutzer, ohne Eintrag in PATH, ohne Dateizuordnung, ohne eigenen Starter. Der vorhandene Starter `py` nimmt ohne Versionsangabe jetzt 3.14 (die
  neueste installierte); `python` aus PATH bleibt, wie es war. Den Fehlerstand des Servers kannte ich nicht (F3; Antwort 26.11.2026: 3.14.4 -- lokal
  bleibt 3.14.10).
- `.venv` neu mit `py -3.14 -m venv`, die Pakete mit `pip install -r requirements.txt -c <Stand der alten .venv>`: alle 51 in genau denselben Versionen
  wie unter 3.13 (`pip freeze` beider gleich) -- 1.11.27 ändert nur Python. Jedes Paket hatte ein fertiges Rad für 3.14 unter Windows.
- Die alte `.venv` (3.13) liegt bis zur Bestätigung unter `C:\DACHKONZEPTE-ERP\venv313-vor-1.11.27` (Rückweg: neue `.venv` löschen, die alte
  zurückschieben); danach löschen. Sie liegt außerhalb des Projekts, damit `backup_windows.ps1` sie nicht mitsichert.
- `tests/test_v803_gunicorn_server.py::test_python_wie_auf_dem_server`: Haupt- und Nebenversion wie auf dem Server (`SERVER_PYTHON = (3, 14)`).
- `setup_windows.bat` legt `.venv` nur mit 3.14 an: zuerst `py -3.14`, sonst `python`, wenn es 3.14 ist; sonst der Hinweis „Python 3.14 wurde nicht
  gefunden“. `requirements.txt` nennt die Version im Kopf.

#### Festlegungen 1.11.27 (bestätigt am 26.11.2026)

1. Lokal läuft Python 3.14 wie auf dem Server; `test_v803` verlangt Haupt- und Nebenversion des Servers.
2. Die Pakete der neuen `.venv` haben genau die Versionen der bisherigen -- die Version ändert nur Python.
3. `setup_windows.bat` legt `.venv` nur mit Python 3.14 an.
4. Die alte `.venv` bleibt bis zur Bestätigung außerhalb des Projekts liegen, danach wird sie gelöscht (gelöscht am 26.11.2026).

#### Tests und Prüfung 1.11.27

Neu `test_v803::test_python_wie_auf_dem_server`. Volle Suite und alle Klicktests unter 3.14 (Endlauf im Bericht). Keine angepasste Erwartung. Gegenprobe:
`gegenproben-portal.md`, „1.11.27“.

### Nachtrag P1f (Antwort des Betriebs, 26.11.2026)

- **S9.6 beantwortet:** an eine Adresse bei Gmail kommt die Mail mit dem Link als `multipart/alternative` mit `text/plain` an -- Exchange ergänzt den
  Textteil selbst; `dkim=pass`, `spf=pass`, `dmarc=pass`, im Posteingang. Ein eigener Textteil ist nicht nötig.
- **DKIM und DMARC:** für dachkonzepte.gmbh fehlten beide bis zum 26.11.2026 -- die erste Mail des Portals an eine Adresse außerhalb landete deshalb im
  Spam. Seit 26.11.2026 DKIM in Microsoft 365 (selector1, selector2) und DMARC `p=none`. Den Absendernamen von web@ setzt der Betrieb in Microsoft 365 auf
  den Namen der Firma -- das ERP setzt keinen eigenen Absender (Regel 17), der Name kommt aus dem Postfach.
- **F3:** auf dem Server läuft Python 3.14.4; lokal bleibt 3.14.10 (`test_v803` prüft Haupt- und Nebenversion).
- **Bestätigt:** 1.11.23-1 und -2, 1.11.25-1 bis -3, 1.11.26-1 bis -3, 1.11.27-1 bis -4 (die alte `.venv` ist am 26.11.2026 gelöscht). Zu Regel 15
  (1.11.26 trotz eines roten Tests committet, selbst gemeldet): die Regel bleibt, wie sie ist.
- **Geändert statt bestätigt: 1.11.24-1.** Nur der Text klickbar ist auf dem Handy, wo die meisten Kunden die Mail öffnen, ein Rückschritt. Stattdessen
  das übliche Muster: Hintergrund und Ecken an der Zelle, an der Zelle zusätzlich `mso-padding-alt:14px 24px` (liest nur Outlook am Rechner); der Link
  wieder mit `display:inline-block` und `padding:14px 24px`, damit in Browsern und Apps die ganze Fläche klickbar ist -- als 1.11.28.
- Eingespielt werden 1.11.23 bis 1.11.28 zusammen, danach S11 (wörtlich als Datei `bildgrundlage/server_schritt_s11.md`).

### Umsetzung 1.11.28: Knopf der Mail wieder ganz klickbar, Outlook über `mso-padding-alt` (26.11.2026)

Betreiberentscheidung 26.11.2026 statt 1.11.24-1: nur der Text klickbar ist auf dem Handy, wo die meisten Kunden die Mail öffnen, ein Rückschritt. Das
übliche Muster:

- `app/portal_mails.py::_knopf()`: an der Zelle (`<td align="center">`) Hintergrund, Ecken und `mso-padding-alt:14px 24px` -- eine Angabe, die nur
  Outlook am Rechner liest; die Zelle hat kein `padding`, sonst läge das Polster in Browsern doppelt. Am Link wieder `display:inline-block` und
  `padding:14px 24px` (beide aus `_KNOPF_POLSTER`), dazu Schrift, Farbe, keine Unterstreichung; kein Hintergrund am Link.
- In Browsern und Apps ist damit die ganze grüne Fläche der Link. Outlook am Rechner (Word) übergeht `padding` und `inline-block` am Link und polstert
  über `mso-padding-alt` die Zelle: dort ist wie mit 1.11.24 nur der Text klickbar, die Fläche hat aber ihr Polster; die runden Ecken zeigt es weiter nicht.
- Wortlaut, Farben und Maße unverändert, kein neues Attribut, keine andere Mail berührt (der Code steht in einem Kasten, nicht in einem Knopf).
- Hier nicht prüfbar: Outlook am Rechner und das Handy -- nach dem Einspielen ein Link an das eigene Postfach (`bildgrundlage/server_schritt_s11.md`,
  „Danach“).

#### Festlegungen 1.11.28 (bestätigt am 26.11.2026)

1. Der Knopf einer Mail des Portals: an der Zelle Hintergrund, Ecken und `mso-padding-alt:14px 24px`, kein `padding`; am Link `display:inline-block` und
   dasselbe Polster, kein Hintergrund -- ersetzt 1.11.24-1.

#### Tests und Prüfung 1.11.28

Angepasste Erwartung (Regel 28): `test_v807_portal_mails_html.py::test_knopf_polster_an_der_zelle` heißt jetzt `test_knopf_ganze_flaeche_und_outlook` --
altes Soll: Zelle mit `padding:14px 24px` und Hintergrund, Link ohne Polster, Hintergrund und `display`; neues Soll: Zelle mit Hintergrund, Ecken und
`mso-padding-alt:14px 24px`, ohne `padding`; Link mit `display:inline-block` und `padding` gleich `mso-padding-alt`, ohne Hintergrund; weiß und ohne
Unterstreichung wie bisher. Die Stile liest der Test jetzt als Wörterbuch (`_stile()`), nicht als Text. Klicktests vor dem Commit:
`klicktest_kundenportal_karte` (versendet den Link über die Attrappe von Graph), `klicktest_portal_seiten`. Gegenproben: `gegenproben-portal.md`, „1.11.28“.

### P1 abgeschlossen (Antwort des Betriebs, 26.11.2026)

- **Eingespielt:** 1.11.23 bis 1.11.28 zusammen mit `update.sh` (FERTIG 5e5b6d7 -> 038fad3). Bestätigt: 1.11.28-1.
- **S11 erledigt:** `pruefe_einheiten.py` von Hand „Einheiten wie im Repo“, Rückgabe 0; der Aufruf steht in `update.sh` (Zeilen 142–144), `bash -n` ok. Ein
  zweiter Aufruf des Einfügeskripts meldete „steht schon in update.sh -- nichts geändert“ -- es lässt sich also gefahrlos wiederholen. Ab dem nächsten
  Einspielen steht vor FERTIG „=== Einheiten ===“.
- **Mail geprüft (1.11.23 und 1.11.28):** Outlook am Rechner zeigt den Knopf als grüne Fläche mit Polster; auf dem Handy öffnet ein Tipp auf den Rand der
  Fläche das Portal (die ganze Fläche ist der Link). Begrüßung in der Mail „Guten Tag Herr Rauchtest,“ und im Portal „Guten Tag Herr Rauchtest“ -- ohne Komma
  nach „Guten Tag“. Danach der Zugang gesperrt und das Modul wieder aus.
- **P1 ist damit abgeschlossen** (1.11.0–1.11.28, Server-Schritte S0–S11). Keine Festlegung der Stufe ist offen. Bericht 1.11.28 und
  `server_schritt_s11.md` liegen seit 26.11.2026 in `C:\DACHKONZEPTE-ERP\Archiv\berichte\` (nicht in Git). Nächste Stufe laut „Stufen“ oben: P2 Lesen --
  nicht begonnen.

### Server-Schritte P1 (Inbetriebnahme des Kundenportals, Stand fc8b758)

Abgearbeitet am 25.11.2026 (Ausgaben im Abschnitt „P1f auf dem Server abgearbeitet“ oben), S11 am 26.11.2026 (Abschnitt „P1 abgeschlossen“ oben). Zum Abarbeiten in dieser Reihenfolge. Gilt für fc8b758 und jeden späteren Stand bis 1.11.22: seit fc8b758 hat sich nichts an den Migrationen oder an den
Rechten geändert; der Block für nginx lauscht seit 1.11.20 nur über IPv4, `scripts/portal_rechte.py --setzen` läuft erst seit 1.11.21 (bis dahin Abbruch, nichts
gesetzt) -- beide kommen vor S5 auf den Server (Umsetzung 1.11.20 und 1.11.21); die Einheit des Portals startet seit 1.11.22 ohne Steuer-Socket -- sie kommt
mit S10 und wird dann einmal neu installiert (S6b, Umsetzung 1.11.22).
Grundlage: Bauplan P1, Abschnitte 1 und 2 (im Archiv `bauplan_p1_e8bb2af.txt`), mit dem Stand nach Nachtrag N1 (der
Benutzer des Portals liest nur Firmendaten und Revision und ruft acht Funktionen auf) und den Antworten bis 24.11.2026. Nachgezogen am 25.11.2026, wie der
Betrieb die Schritte beim Abarbeiten geändert hat (Abschnitt oben); S0, S1 und S7 seit 1.11.20 nur IPv4 (Umsetzung 1.11.20).

So zu lesen:

- **Als tobias** heißt: in der normalen SSH-Sitzung. **In der root-Shell** heißt: nach `sudo -i`, bis `exit`.
- Jeder Schritt nennt, was zu sehen sein soll (**Erwartet**), wann nicht weiterzumachen ist (**Abbrechen**) und wie er zurückgeht (**Rückweg**). Bei „Abbrechen“
  die Ausgabe in den Chat geben -- keiner der Befehle zeigt ein Geheimnis.
- **Geheimnisse:** kein Befehl liest `.env` oder `/etc/dk-portal/portal.env` aus. Passwort und Schlüssel entstehen in der root-Shell direkt in der Datei; geprüft
  werden nur Namen und Längen. Nie `cat`, `less` oder einen Editor auf diese beiden Dateien.
- **Zu Beginn jeder Sitzung** (auch nach einem neuen Anmelden): `export SYSTEMD_PAGER=cat` -- sonst öffnet `systemctl` ein Blätterfenster und schneidet lange
  Zeilen ab (Betreiberangabe 25.11.2026). `journalctl` immer mit `sudo` und `--no-pager` (unter `sudo` kommt die Variable nicht an).
- Der Datenbank-Benutzer des ERP ist `erp`, die Datenbank `dachkonzepte`, PostgreSQL 18.6 (Betreiberangabe 25.11.2026) -- in den Befehlen steht er schon.
- Meldet psql „could not change directory to …: Permission denied“, ist das harmlos (der Benutzer postgres darf den aktuellen Ordner nicht lesen).
- Gebraucht: SSH als tobias mit sudo, der DNS-Zugang bei Ionos, ein Handy mit mobilen Daten (WLAN aus), das eigene Postfach, ein Konto im ERP als Admin.

#### S0 Bestand lesen (nichts ändern)

Als tobias:

```bash
export SYSTEMD_PAGER=cat
cd /home/tobias/erp
git log --oneline -1
lsb_release -ds; systemctl --version | head -1; psql --version; nginx -v
free -m
ss -ltn
stat -c '%a %U:%G %n' /home/tobias /home/tobias/erp /home/tobias/erp/.env /home/tobias/erp-data
.venv/bin/python -c "import uvicorn, gunicorn; print(uvicorn.__version__, gunicorn.__version__)"
systemctl show -p User -p ExecStart erp
git status --ignored --short -- app alembic alembic.ini
ls /etc/systemd/system | grep erp; ls -d /srv/erp-code 2>&1
```

(Bis 25.11.2026 stand hier eine `sed`-Zeile, die Benutzer, Rechner:Port und Datenbank aus `.env` las; entfällt -- Benutzer `erp` und Datenbank `dachkonzepte`
hat der Betrieb genannt, Adresse und Port zeigt die Abfrage von PostgreSQL unten.)

**Erwartet:**

- `git log`: fc8b758 oder später.
- `free -m`: in der Spalte „available“ mindestens 600 (zwei neue Dienste mit je höchstens 256 MB).
- `ss -ltn`: keine Zeile mit `:8010`; nginx auf `0.0.0.0:80` und `0.0.0.0:443` -- nur IPv4, wie die übrigen Seiten des Servers (bis 1.11.19 stand hier auch
  `[::]:80`, `[::]:443`; Umsetzung 1.11.20).
- `stat`: `.env` 600 tobias:tobias.
- Versionen: `0.52.4 26.2.0`.
- `systemctl show`: `User=tobias`, im ExecStart gunicorn mit `-w 2`.
- `git status`: nichts oder nur Zeilen `!! app/…/__pycache__/`.
- `ls /etc/systemd/system | grep erp`: `erp.service`, `erp-webanfragen.service`, `erp-webanfragen.timer` -- noch kein `erp-portal*`; `/srv/erp-code` gibt es noch
  nicht.

**Abbrechen,** wenn: weniger als 600 MB verfügbar; `:8010` belegt; `.env` nicht 600; andere Versionen als 0.52.4/26.2.0; `User=` nicht tobias (der Postbote
läuft als tobias); `git status` nennt unter `app/`, `alembic/` oder `alembic.ini` eine Datei
außerhalb von `__pycache__` (nur den Namen in den Chat -- sie käme vor dem Start in `InaccessiblePaths=`).

PostgreSQL lesen, als tobias:

```bash
sudo -u postgres psql -tAX -c "show log_statement" -c "show log_min_duration_statement" -c "show password_encryption" -c "show listen_addresses" -c "show port" -c "show shared_preload_libraries"
sudo -u postgres psql -tAX -c "select rolname from pg_roles where rolname = 'dkportal'"
sudo -u postgres psql -tAX -c "select rolsuper, rolcreaterole, rolbypassrls from pg_roles where rolname = 'erp'"
sudo -u postgres psql -d dachkonzepte -tAX -c "select has_schema_privilege('public', 'public', 'CREATE')"
sudo -u postgres psql -X -c "select line_number, type, database, user_name, address, auth_method from pg_hba_file_rules order by line_number"
```

**Erwartet:** `none`, `-1`, `scram-sha-256`, `localhost` (oder eine Liste mit 127.0.0.1), `5432`, leer oder `pg_stat_statements`; die Rolle `dkportal` gibt es
nicht (leere Zeile); `f|f|f`; `f` (in PostgreSQL ab 15, hier 18.6, darf PUBLIC im Schema public nichts anlegen -- deshalb kein S3b); die Regeln von pg_hba
(zum Ansehen -- `dkportal` steht in keiner).

**Abbrechen,** wenn: `password_encryption` nicht `scram-sha-256`; die Rolle `dkportal` gibt es schon; der Benutzer des ERP ist Superuser, darf Rollen anlegen
oder umgeht Zeilenrechte (nicht `f|f|f`); `shared_preload_libraries` nennt `pgaudit` oder etwas, das Anweisungen mitschreibt; `port` nicht `5432` (dann die
Zahl in S3 anpassen); für das Schema `t` (unter PostgreSQL 18 unerwartet -- melden, dann kommt S3b zurück). Nicht abbrechen bei `log_statement` anders als `none`
(S3 schaltet es für seine Sitzung ab).

nginx, Zertifikat, Protokolle, als tobias:

```bash
grep -n 'include' /etc/nginx/nginx.conf
ls /etc/nginx/conf.d /etc/nginx/sites-enabled
ls /etc/letsencrypt/options-ssl-nginx.conf /etc/letsencrypt/ssl-dhparams.pem
sudo certbot plugins 2>/dev/null | grep -A1 '^\* nginx'
sudo ufw status | grep -E '^(80|443)'
grep -E '^\s*(daily|weekly|rotate)' /etc/logrotate.d/nginx
grep -rhE '^\s*MaxRetentionSec' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/ 2>/dev/null
```

**Erwartet:** eine Zeile `include /etc/nginx/conf.d/*.conf;`; in `conf.d` noch keine Datei für kunde; beide Dateien von Let's Encrypt da; das Plugin `nginx`;
80 und 443 erlaubt (oder ufw inaktiv); `daily` und `rotate 14`; `MaxRetentionSec=14day`.

**Abbrechen,** wenn: `conf.d` nicht eingebunden ist; eine der Dateien von Let's Encrypt fehlt; das Plugin `nginx` fehlt. Nicht abbrechen, aber melden, wenn
logrotate oder das Journal andere Fristen zeigen -- die Datenschutzerklärung nennt „höchstens 15 Tage“ bzw. „14 Tage“.

#### S1 DNS (Ionos)

Bei Ionos für `kunde.dachkonzepte.gmbh` einen A-Eintrag auf dieselbe IPv4-Adresse wie `app.dachkonzepte.gmbh`, **keinen** AAAA-Eintrag: nginx lauscht nur
über IPv4, app, web und www haben keinen (Betreiberangabe 25.11.2026; bis 1.11.19 stand hier „hat `app` einen AAAA-Eintrag, ebenso einen“). Nach ein paar
Minuten, als tobias:

```bash
dig +short A app.dachkonzepte.gmbh;    dig +short A kunde.dachkonzepte.gmbh
dig +short AAAA app.dachkonzepte.gmbh; dig +short AAAA kunde.dachkonzepte.gmbh
dig +short CAA dachkonzepte.gmbh
```

(Fehlt `dig`: `resolvectl query app.dachkonzepte.gmbh` und `resolvectl query kunde.dachkonzepte.gmbh`.)

**Erwartet:** bei A dieselbe Adresse; bei AAAA beide Zeilen leer; CAA leer oder mit `letsencrypt.org`.
**Abbrechen,** wenn kunde keine oder eine andere A-Adresse hat (warten, bis der Eintrag sichtbar ist), wenn kunde eine AAAA-Adresse hat (bei Ionos löschen --
über IPv6 antwortet nginx nicht) oder CAA Let's Encrypt nicht erlaubt.
**Rückweg:** den Eintrag bei Ionos löschen.

#### S2 Systembenutzer dkportal

Als tobias:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin dkportal
id dkportal
getent passwd dkportal
sudo mkdir -p /srv/erp-code
cd / && sudo -u dkportal test -r /home/tobias/erp/.env && echo "LESBAR" || echo "nicht lesbar"
```

Dann, was der Dienst später sieht (dieselben Einhängungen wie die Einheit `erp-portal`):

```bash
sudo systemd-run --pipe --wait --quiet -p User=dkportal -p ProtectHome=tmpfs -p TemporaryFileSystem=/srv/erp-code \
  -p BindReadOnlyPaths=/home/tobias/erp/app:/srv/erp-code/app -p BindReadOnlyPaths=/home/tobias/erp/alembic:/srv/erp-code/alembic \
  -p BindReadOnlyPaths=/home/tobias/erp/alembic.ini:/srv/erp-code/alembic.ini -p BindReadOnlyPaths=/home/tobias/erp/.venv:/srv/erp-code/.venv \
  /bin/sh -c 'ls -A /srv/erp-code; echo "home: $(ls -A /home)"; test -e /srv/erp-code/.env && echo ".env SICHTBAR" || echo ".env nicht da"; ls /srv/erp-code/app/portal | head -3'
```

**Erwartet:** `uid=…(dkportal) gid=…(dkportal) groups=…(dkportal)`; die passwd-Zeile endet mit `/usr/sbin/nologin`; `nicht lesbar`; danach
`.venv alembic alembic.ini app` (auch untereinander), `home: ` (leer), `.env nicht da` und drei Dateinamen aus `app/portal` (`__init__.py` …).
**Abbrechen,** wenn `LESBAR`, `.env SICHTBAR`, `/home` nicht leer oder `systemd-run` einen Fehler meldet (dann die Meldung in den Chat).
**Rückweg:** `sudo userdel dkportal; sudo rmdir /srv/erp-code`.

#### S3 Datenbank-Benutzer dkportal (Passwort entsteht in der Datei, nie angezeigt)

In der root-Shell (`sudo -i`), Zeile für Zeile:

```bash
cd /
umask 077
install -d -m 750 -o root -g dkportal /etc/dk-portal
P=$(openssl rand -hex 20)
printf '%s\n' "SET log_statement = 'none';" "SET log_min_error_statement = 'panic';" "SET pg_stat_statements.track_utility = off;" \
  "CREATE ROLE dkportal LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION CONNECTION LIMIT 10 PASSWORD '$P';" \
  | sudo -u postgres psql -X -q -v ON_ERROR_STOP=1 -v VERBOSITY=terse
printf 'DATABASE_URL=postgresql+psycopg://dkportal:%s@127.0.0.1:5432/dachkonzepte\nPORTAL_HERKUNFT=https://kunde.dachkonzepte.gmbh\nERP_ENV=production\n' "$P" > /etc/dk-portal/portal.env
unset P
chown root:dkportal /etc/dk-portal/portal.env
chmod 640 /etc/dk-portal/portal.env
exit
```

Warum so: das Passwort (40 Zeichen 0–9a–f, nichts zu kodieren) entsteht in einer Variablen der root-Shell, geht über stdin an psql (nie als Argument, nie in einen
Verlauf -- im Verlauf steht nur `$P`) und gleich in die Datei; `printf` ist in bash eingebaut und erscheint nicht in der Prozessliste. In der Sitzung schreibt
PostgreSQL keine Anweisung ins Log, auch nicht bei einem Fehler, und `pg_stat_statements` merkt sie sich nicht. psql zeigt bei einem Fehler nur die Meldung, nie
die Anweisung. Zeigte S0 einen anderen Port als 5432, die Zahl in der `printf`-Zeile anpassen (kein Geheimnis).

Einstellungen der Rolle, als tobias:

```bash
printf '%s\n' "ALTER ROLE dkportal SET statement_timeout = '5s';" "ALTER ROLE dkportal SET idle_in_transaction_session_timeout = '15s';" \
  "ALTER ROLE dkportal SET search_path = public;" | sudo -u postgres psql -X -q -v ON_ERROR_STOP=1
```

(S3b -- dem ERP das Anlegen im Schema public ausdrücklich geben, PUBLIC nehmen -- entfällt seit 25.11.2026: PostgreSQL 18.6, S0 zeigt `f`.)

pg_hba: drei Zeilen vor alle übrigen (die erste passende Regel gilt), als tobias:

```bash
HBA=$(sudo -u postgres psql -tAX -c "show hba_file")
sudo cp -a "$HBA" "$HBA.vor-p1"
sudo awk '!fertig && $0 !~ /^[[:space:]]*(#|$)/ { print "host    dachkonzepte    dkportal    127.0.0.1/32    scram-sha-256"; print "host    all             dkportal    all             reject"; print "local   all             dkportal                    reject"; fertig = 1 } { print }' "$HBA.vor-p1" | sudo tee "$HBA" > /dev/null
sudo -u postgres psql -X -c "select line_number, type, database, user_name, address, auth_method, error from pg_hba_file_rules where 'dkportal' = any(user_name) or error is not null order by line_number"
```

**Erwartet:** genau drei Zeilen mit den kleinsten Zeilennummern -- `host {dachkonzepte} {dkportal} 127.0.0.1 scram-sha-256`, `host {all} {dkportal} all reject`,
`local {all} {dkportal} reject` --, die Spalte `error` leer.
**Abbrechen,** wenn eine Zeile einen Fehler zeigt oder die Zeilen nicht vorn stehen: `sudo cp -a "$HBA.vor-p1" "$HBA"` (noch nichts neu geladen, nichts
passiert).

Dann neu laden und ohne Passwort prüfen, als tobias:

```bash
sudo -u postgres psql -tAX -c "select pg_reload_conf()"
cd /
sudo -u dkportal psql -X -w -h 127.0.0.1 -U dkportal -d spielwiese -c 'select 1'
sudo -u dkportal psql -X -w -U dkportal -d dachkonzepte -c 'select 1'
sudo -u dkportal psql -X -w -h 127.0.0.1 -U dkportal -d dachkonzepte -c 'select 1'
curl -fsS https://app.dachkonzepte.gmbh/health; echo
sudo -u postgres psql -tAX -c "select rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls, rolconnlimit from pg_roles where rolname = 'dkportal'"
sudo -u postgres psql -tAX -c "select unnest(setconfig) from pg_db_role_setting where setrole = 'dkportal'::regrole"
sudo stat -c '%a %U:%G %n' /etc/dk-portal /etc/dk-portal/portal.env
sudo grep -o '^[A-Z_]*=' /etc/dk-portal/portal.env
sudo grep -c '^DATABASE_URL=postgresql+psycopg://dkportal:[0-9a-f]\{40\}@127.0.0.1:' /etc/dk-portal/portal.env
```

**Erwartet:** `t`; die erste Verbindung „pg_hba.conf rejects connection … database "spielwiese"“ (deutsch: „pg_hba.conf lehnt Verbindung … ab“), die zweite
ebenso für `[local]`, die dritte `fe_sendauth: no password supplied` (sie kam bis zur Passwortprüfung, die Regel greift); das ERP antwortet wie immer;
`dkportal|f|f|f|f|f|f|10`; `statement_timeout=5s`, `idle_in_transaction_session_timeout=15s`, `search_path=public`; `750 root:dkportal /etc/dk-portal` und
`640 root:dkportal /etc/dk-portal/portal.env`; `DATABASE_URL=`, `PORTAL_HERKUNFT=`, `ERP_ENV=`; `1`.
**Abbrechen,** wenn eine der drei Verbindungen anders endet, das ERP nicht antwortet (dann zuerst `sudo cp -a "$HBA.vor-p1" "$HBA"` und neu laden) oder ein Wert
abweicht.
**Rückweg:** `sudo -u postgres psql -X -c "DROP ROLE dkportal"`; `sudo cp -a "$HBA.vor-p1" "$HBA"` und `select pg_reload_conf()`; `sudo rm -r /etc/dk-portal`.

#### S4 Schlüssel der Bremsen (nie angezeigt)

Als tobias:

```bash
sudo sh -c 'umask 077; printf "PORTAL_BREMSE_SCHLUESSEL=%s\n" "$(openssl rand -hex 32)" >> /etc/dk-portal/portal.env'
sudo awk -F= '/^PORTAL_BREMSE_SCHLUESSEL=/{print length($2)}' /etc/dk-portal/portal.env
sudo grep -c '^PORTAL_BREMSE_SCHLUESSEL=' /etc/dk-portal/portal.env
sudo stat -c '%a %U:%G' /etc/dk-portal/portal.env
```

**Erwartet:** `64`, `1`, `640 root:dkportal`.
**Abbrechen,** wenn die Länge nicht 64 oder der Name zweimal da ist.
**Rückweg:** `sudo sed -i '/^PORTAL_BREMSE_SCHLUESSEL=/d' /etc/dk-portal/portal.env`. Ein neuer Schlüssel später macht nur die laufenden Bremsen wirkungslos
(höchstens eine Stunde), kein Datenverlust.

#### S5 Version und Rechte

Der Code von fc8b758 samt Migrationen ist schon eingespielt. Liegt inzwischen ein neuerer Stand im Repo, zuerst wie immer `/home/tobias/update.sh` -- für S5
mindestens 1.11.21 (`git log --oneline -1`): bis 1.11.20 brach `--setzen` mit „InvalidRequestError: This connection has already initialized a SQLAlchemy
Transaction()“ ab, nichts gesetzt (Umsetzung 1.11.21). Dann als
tobias (die Klammern laden `.env` nur für diese Befehle):

```bash
cd /home/tobias/erp
( set -a; . ./.env; set +a
  .venv/bin/alembic current 2>/dev/null
  .venv/bin/alembic heads 2>/dev/null
  .venv/bin/python scripts/portal_rechte.py --setzen && .venv/bin/python scripts/portal_rechte.py --pruefen )
sudo -u postgres psql -d dachkonzepte -tAX -c "select count(*) from information_schema.column_privileges where grantee = 'dkportal'" -c "select count(*) from information_schema.routine_privileges where grantee = 'dkportal'"
```

**Erwartet:** `current` und `heads` nennen dieselbe Revision (`… (head)`); „Rechte für dkportal gesetzt: 2 Tabellen (nur Lesen), 8 Funktionen, n Anweisungen.“ und
„Rechte für dkportal stimmen.“; `9` (Spalten: 8 der Firmendaten, 1 der Revision) und `8` (Funktionen).
**Abbrechen,** wenn `current` und `heads` verschieden sind (erst `update.sh`) oder `--pruefen` Abweichungen nennt (die Zeilen in den Chat; „Schema public: darf
Objekte anlegen“ ist unter PostgreSQL 18 unerwartet -- melden).
**Rückweg:** keiner nötig -- `--setzen` gibt nur dkportal Rechte; `DROP ROLE` (S3) nimmt sie mit (vorher `sudo -u postgres psql -d dachkonzepte -X -c "DROP OWNED
BY dkportal"`).

#### S6 Die beiden Dienste

Als tobias:

```bash
sudo install -m 644 -o root -g root /home/tobias/erp/scripts/server/erp-portalpost.service /home/tobias/erp/scripts/server/erp-portal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now erp-portalpost
sudo journalctl -u erp-portalpost -n 5 --no-pager
sudo systemctl enable --now erp-portal
sudo journalctl -u erp-portal -n 10 --no-pager
curl -fsS -H 'Host: kunde.dachkonzepte.gmbh' http://127.0.0.1:8010/health; echo
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/health
systemctl is-active erp erp-portal erp-portalpost
ss -ltn | grep 8010
systemctl show -p MemoryCurrent erp-portal erp-portalpost
sudo systemd-analyze security erp-portal | tail -1
```

(`systemd-analyze verify` hier bewusst nicht: es sucht `/srv/erp-code/.venv/bin/python` auf dem Rechner selbst -- den Pfad gibt es nur im Dienst.)

**Erwartet:**

- Postbote: „… app.portal_postbote: Postbote bereit (LISTEN portal_post)“ und „Postbote: aufgeräumt {'codes': 0, 'sitzungen': 0, 'bremsen': 0, 'zugriffe': 0}“.
- Portal: gunicorn „Listening at: http://127.0.0.1:8010“, „Booting worker …“ und „Portal verbunden als dkportal, Revision <dieselbe wie in S5>“. Bis 1.11.21
  dazu „[ERROR] Control server error: [Errno 30] Read-only file system: '/home/dkportal'“ -- ohne Folge, weg mit S6b.
- `{"ok":true}`; ohne den Namen kunde `421` (fremder Host).
- `active` dreimal; `127.0.0.1:8010` (nur lokal).
- `MemoryCurrent` je unter 200 MB (Zahl in Byte, z. B. `MemoryCurrent=95000000`).
- `Overall exposure level for erp-portal.service: …` -- den Wert in den Chat.

**Abbrechen,** wenn ein Dienst nicht `active` ist: `sudo journalctl -u erp-portal -n 30 --no-pager` bzw. `-u erp-portalpost` in den Chat (das Journal enthält keine
Geheimnisse: Fehler nur mit Namen der Klasse). Typisch: „Datenbank auf Revision …, der Code erwartet … -- erst update.sh“ (dann `update.sh`, danach
`sudo systemctl restart erp-portal`); „… startet nicht“ mit einem Namen aus portal.env (S3/S4 prüfen); beim Postboten Rückgabe 3 „Es läuft schon ein
Postbote“ (nur einer je Datenbank).
**Rückweg:** `sudo systemctl disable --now erp-portal erp-portalpost && sudo rm /etc/systemd/system/erp-portal.service /etc/systemd/system/erp-portalpost.service
&& sudo systemctl daemon-reload`.

#### S6b Kein Steuer-Socket (seit 1.11.22)

gunicorn 26 öffnet ab Werk einen Steuer-Socket (für `gunicornc`: Konfiguration zeigen, Arbeitsprozesse dazu oder weg, Neustart, Ende) unter
`$XDG_RUNTIME_DIR/gunicorn.ctl` bzw. `$HOME/.gunicorn/gunicorn.ctl`. Gebraucht wird er nicht -- Neustart und Ende laufen über `systemctl`. Im Portal scheiterte er
an ProtectHome (nach S6 im Journal „[ERROR] Control server error: [Errno 30] Read-only file system: '/home/dkportal'“, sonst ohne Folge); im ERP liegt er
vermutlich unter `/home/tobias/.gunicorn/`. Beide bekommen `--no-control-socket` (Umsetzung 1.11.22).

**Teil 1: ERP** -- jederzeit nach S6, unabhängig von 1.11.22 (die Option gibt es in gunicorn 26.2.0 schon). `erp.service` liegt nur auf dem Server. Geändert
wird genau eine Stelle: ans Ende der Zeile `ExecStart=` kommt ` --no-control-socket` (mit einem Leerzeichen davor), sonst nichts. Zuerst lesen, als tobias:

```bash
export SYSTEMD_PAGER=cat
grep -c '^ExecStart=' /etc/systemd/system/erp.service
grep '^ExecStart=' /etc/systemd/system/erp.service
ls -la /home/tobias/.gunicorn 2>&1; ss -lx | grep -c 'gunicorn.ctl'
```

**Erwartet:** `1`; die eine Zeile startet gunicorn direkt (`-w 2 … --timeout 120`, laut S0) und endet auf eine Option von gunicorn, noch ohne
`--no-control-socket`; im Ordner `/home/tobias/.gunicorn` eine Zeile `srw------- … gunicorn.ctl` und `1` (der Steuer-Socket des ERP lauscht). Fehlt der Ordner
und steht `0`, hat das ERP keinen -- die Änderung schadet dann nicht.
**Abbrechen,** wenn `grep -c` nicht `1` ist oder die Zeile auf `\` oder ein Anführungszeichen endet (dann geht sie weiter bzw. steht gunicorn in einem Aufruf
der Shell, und der Befehl unten hängt die Option an die falsche Stelle) -- die Zeile in den Chat.

Dann ändern, als tobias (der Neustart unterbricht das ERP für ein paar Sekunden wie `update.sh`):

```bash
sudo cp -a /etc/systemd/system/erp.service /home/tobias/erp.service.vor-1.11.22
sudo sed -i '/^ExecStart=/{/--no-control-socket/!s/$/ --no-control-socket/}' /etc/systemd/system/erp.service
grep '^ExecStart=' /etc/systemd/system/erp.service
diff -U0 /home/tobias/erp.service.vor-1.11.22 /etc/systemd/system/erp.service
sudo systemctl daemon-reload && sudo systemctl restart erp
systemctl is-active erp
sudo journalctl -u erp --since '2 min ago' --no-pager
ls -A /home/tobias/.gunicorn 2>&1; ss -lx | grep -c 'gunicorn.ctl'
```

**Erwartet:** die Zeile wie vorher, am Ende ` --no-control-socket`; `diff` zeigt genau diese eine Zeile alt (`-`) und neu (`+`); `active`; im Journal je
Arbeitsprozess „Booting worker“ und „Application startup complete“, keine Zeile „Control server“; `ls -A` leer (gunicorn löscht den Socket beim Beenden, den
leeren Ordner lässt er stehen) und `0`. Den leeren Ordner danach löschen: `rmdir /home/tobias/.gunicorn`.
**Abbrechen,** wenn erp nicht `active` ist: `sudo journalctl -u erp -n 30 --no-pager` in den Chat und den Rückweg gehen.
**Rückweg:** `sudo cp -a /home/tobias/erp.service.vor-1.11.22 /etc/systemd/system/erp.service && sudo systemctl daemon-reload && sudo systemctl restart erp`.

**Teil 2: Portal** -- erst wenn 1.11.22 eingespielt ist (mit S10). `update.sh` holt die geänderte Einheit, installiert sie aber nicht nach
`/etc/systemd/system`; das geschieht hier einmal von Hand. Als tobias:

```bash
git -C /home/tobias/erp log --oneline -1
grep -c -- '--no-control-socket' /home/tobias/erp/scripts/server/erp-portal.service
sudo install -m 644 -o root -g root /home/tobias/erp/scripts/server/erp-portal.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl restart erp-portal
systemctl is-active erp-portal
sudo journalctl -u erp-portal --since '2 min ago' --no-pager
curl -fsS -H 'Host: kunde.dachkonzepte.gmbh' http://127.0.0.1:8010/health; echo
```

**Erwartet:** 1.11.22 oder später; `2` (Kommentar und `ExecStart`); `active`; im Journal „Listening at: http://127.0.0.1:8010“, „Booting worker …“ und
„Portal verbunden als dkportal …“, keine Zeile „Control server error“; `{"ok":true}`. Während des Neustarts zeigt das Portal ein paar Sekunden „Gleich wieder
da“.
**Abbrechen,** wenn `grep -c` `0` zeigt (erst `update.sh`) oder erp-portal nicht `active` ist: `sudo journalctl -u erp-portal -n 30 --no-pager` in den Chat.
**Rückweg:** die Einheit aus 1.11.21 zurück: `git -C /home/tobias/erp show b96a7b8:scripts/server/erp-portal.service | sudo tee
/etc/systemd/system/erp-portal.service >/dev/null && sudo systemctl daemon-reload && sudo systemctl restart erp-portal`.

#### S7 nginx und Zertifikat

Vorher muss 1.11.20 oder später eingespielt sein (`update.sh`) -- bis 1.11.19 lauschte die Datei auch auf `[::]`. Als tobias:

```bash
git -C /home/tobias/erp log --oneline -1
grep -E '^\s*listen' /home/tobias/erp/scripts/server/nginx-kunde.conf
```

**Erwartet:** 1.11.20 oder später; genau zwei Zeilen, `listen 80;` und `listen 443 ssl http2;`.
**Abbrechen,** wenn eine Zeile `listen [::]` dabei ist (erst `update.sh`).

Dann nur der Block für Port 80 (für die Prüfung durch Let's Encrypt), als tobias:

```bash
awk '/^server [{]/{n++} n<2' /home/tobias/erp/scripts/server/nginx-kunde.conf | sudo tee /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf > /dev/null
grep -c 'listen 80;' /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf; grep -c 'listen 443' /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf
sudo nginx -t && sudo systemctl reload nginx
curl -sI http://kunde.dachkonzepte.gmbh/health | head -1
sudo certbot certonly --nginx -d kunde.dachkonzepte.gmbh
sudo certbot certificates --cert-name kunde.dachkonzepte.gmbh
```

**Erwartet:** `1` und `0`; „syntax is ok“, „test is successful“; `HTTP/1.1 301 Moved Permanently`; certbot „Successfully received certificate“ mit
`/etc/letsencrypt/live/kunde.dachkonzepte.gmbh/fullchain.pem`; in `certificates` der Name `kunde.dachkonzepte.gmbh` und ein Ablauf in rund 90 Tagen.
**Abbrechen,** wenn `nginx -t` einen Fehler meldet (`sudo rm /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf` -- ohne Neuladen ist nichts passiert) oder certbot
scheitert bzw. einen anderen Pfad nennt (etwa `…-0001`).

Dann der volle Block mit der Seite „Gleich wieder da“:

```bash
sudo install -D -m 644 -o root -g root /home/tobias/erp/scripts/server/portal-wartung.html /etc/nginx/dk-portal/wartung.html
sudo install -m 644 -o root -g root /home/tobias/erp/scripts/server/nginx-kunde.conf /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf
sudo nginx -t && sudo systemctl reload nginx
```

**Erwartet:** „syntax is ok“, „test is successful“. Ab nginx 1.25.1 (S0: `nginx -v`) steht davor eine Warnung, dass „listen … http2“ veraltet ist -- nur eine
Warnung.
**Abbrechen,** wenn `nginx -t` einen Fehler meldet: sofort `sudo rm /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf` (sonst scheiterte das nächste Neuladen, auch
das von certbot) und die Meldung in den Chat.

Prüfen, als tobias:

```bash
curl -sI http://kunde.dachkonzepte.gmbh/health | head -1
curl -sI https://kunde.dachkonzepte.gmbh/health
for p in / /api/customers /docs; do printf '%s ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "https://kunde.dachkonzepte.gmbh$p"; done
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE https://kunde.dachkonzepte.gmbh/
curl -sI https://app.dachkonzepte.gmbh/health | head -1
sudo systemctl stop erp-portal; curl -s -w '\n%{http_code}\n' https://kunde.dachkonzepte.gmbh/ | grep -oE 'Gleich wieder da|^50[24]$'; sudo systemctl start erp-portal
sleep 3; curl -fsS https://kunde.dachkonzepte.gmbh/health; echo
sudo certbot renew --dry-run --cert-name kunde.dachkonzepte.gmbh 2>&1 | tail -2
systemctl list-timers | grep -i certbot
```

**Erwartet:**

- `301`; `HTTP/2 200` mit `server: nginx` (ohne Version), `strict-transport-security: max-age=31536000`, `content-security-policy: …`,
  `x-frame-options: DENY`, `x-content-type-options: nosniff`, `referrer-policy: no-referrer`, `cache-control: no-store`.
- `/ 200`, `/api/customers 404` (kein Weg des ERP), `/docs 404`; `DELETE` `405`; das ERP `200`.
- Bei angehaltenem Portal `Gleich wieder da` und `502`, danach wieder `{"ok":true}`.
- certbot „Congratulations, all simulated renewals succeeded“; ein Timer für certbot.

Im Browser (Handy und Rechner): `https://kunde.dachkonzepte.gmbh` zeigt die Seite des Portals mit „Bitte über den Link anmelden“ (ohne
Link).
**Abbrechen,** wenn eine Schutz-Kopfzeile fehlt, ein Weg des ERP nicht 404 ist oder das ERP nicht mehr 200 antwortet.
**Rückweg:** `sudo rm /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf && sudo nginx -t && sudo systemctl reload nginx`; das Zertifikat kann bleiben (`sudo certbot
delete --cert-name kunde.dachkonzepte.gmbh` nimmt es weg).

#### S8 Nachweis E4 (sieht das Portal die Adresse des Geräts?)

Ein erfundener Link (43 Zeichen, gilt nicht):

    https://kunde.dachkonzepte.gmbh/#z=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

Vom Handy im Mobilnetz (WLAN aus) und vom Rechner im Büro je zweimal in einem neuen Tab öffnen (neu laden reicht nicht -- die Seite nimmt den Link sofort aus der
Adresse). Jedes Mal erscheint „Dieser Link funktioniert nicht“. Dann als tobias:

```bash
cd /home/tobias/erp
( set -a; . ./.env; set +a; .venv/bin/python scripts/pruefe_portal_e4.py )
```

**Erwartet:** „Link geöffnet seit HH:MM Uhr (UTC): 2 Anschlüsse, 4 Aufrufe.“ und „Erwartet nach dem Nachweis mit zwei Geräten: 2 …“ (Rückgabe 0).
**Abbrechen,** wenn dort „1 Anschlüsse“ steht: das Portal sieht nur nginx. Die Ausgabe in den Chat; nginx reicht `X-Forwarded-For` weiter (S7), gunicorn wertet es
nur von 127.0.0.1 aus.

Dasselbe fürs ERP (Frage P1-9): auf `https://app.dachkonzepte.gmbh/login` von beiden Anschlüssen je einmal mit dem erfundenen Benutzernamen `e4-probe` und
einem beliebigen Passwort anmelden (scheitert; ein Fehlversuch sperrt nichts). Dann als tobias:

```bash
sudo -u postgres psql -d dachkonzepte -tAX -c "select count(distinct bucket), count(*) filter (where bucket = 'login_ip:127.0.0.1') from failed_login_attempts where bucket like 'login_ip:%' and occurred_at > (now() at time zone 'utc') - interval '1 hour'"
```

**Erwartet:** `2|0` (die erste Zahl kann höher sein, wenn in der Stunde noch jemand sich vertippt hat; die zweite muss 0 sein). Die Abfrage zeigt keine Adresse.
**Abbrechen,** wenn die zweite Zahl nicht 0 ist.

#### S9 Rauchtest

Im ERP als Admin:

1. Einstellungen → Module: „Kundenportal“ einschalten.
2. Einen Kunden „Rauchtest Portal“ anlegen, als E-Mail die eigene Adresse (keine eines Kunden).
3. Kundenakte → Übersicht → Karte „Kundenportal“: einschalten, Zugang anlegen, „Link senden“.
4. Im eigenen Postfach: „Ihr Zugang zum Kundenportal“ -- gesiezt, Knopf, Fußzeile mit Anschrift und „Sitz … · Amtsgericht … · Geschäftsführer: …“; Betreff ohne
   Link.
5. Im Postfach des Absenders (Einstellungen → E-Mail-Versand) unter „Gesendete Elemente“: die Mail steht dort **nicht**.
6. Die Rohdaten der Mail ansehen (Outlook im Web: „…“ → Ansicht → Nachrichtenquelle anzeigen; Apple Mail: Darstellung → Nachricht → Rohdaten): steht dort
   `multipart/alternative` (Exchange hat einen Textteil ergänzt) oder nur `text/html`? Das Ergebnis in den Chat.
7. Den Link auf dem Handy öffnen: „Willkommen im Kundenportal“ → „Code senden“ → „Code eingeben“; Mail „Ihr Anmeldecode für das Kundenportal“ (Betreff ohne
   Code, auch sie nicht unter „Gesendete Elemente“); die 6 Ziffern eingeben → „Guten Tag …“ (bis 1.11.22 mit Komma) mit dem Kontakt des Betriebs.
8. Im ERP auf der Karte das Protokoll (je Aktion eine Zeile); im Versandprotokoll zwei Einträge, der Betreff ohne Link und Code.
9. Im Portal „Auf allen Geräten abmelden“; im ERP auf der Karte „Sperren“ und das Portal des Kunden ausschalten.

Ist 1.11.17 schon eingespielt: eine beliebige Mail an Kunden (etwa ein Angebot des Rauchtest-Kunden an die eigene Adresse) zeigt unten nach einer Leerzeile Name,
Anschrift und Pflichtangaben.

**Abbrechen,** wenn eine Mail unter „Gesendete Elemente“ steht, der Code nach einer Minute nicht da ist (dann `sudo journalctl -u erp-portalpost -n 20 --no-pager` und
der Hinweis auf „Start“ in den Chat) oder ein Betreff Link oder Code enthält.

#### S10 update.sh für drei Dienste

`update.sh` liegt nur auf dem Server; ich kenne ihn nicht wörtlich. Zuerst sichern:

```bash
cp -a /home/tobias/update.sh /home/tobias/update.sh.vor-p1
```

Dann drei Stellen ändern:

1. Nach der Zeile mit `alembic current` für **dachkonzepte** (die Umgebung ist dort geladen), vor dem Neustart:

   ```bash
   .venv/bin/python scripts/portal_rechte.py --setzen && .venv/bin/python scripts/portal_rechte.py --pruefen || { echo "Rechte des Kundenportals stimmen nicht -- Abbruch vor dem Neustart"; exit 1; }
   ```

   Gegen `spielwiese` nichts: der Benutzer des Portals darf dort gar nicht hin (pg_hba), die Probe bleibt, wie sie ist.

2. Den Neustart `sudo systemctl restart erp` ersetzen durch:

   ```bash
   sudo systemctl restart erp erp-portal erp-portalpost
   ```

3. Danach prüfen, jeden Dienst einzeln -- `systemctl is-active` mit mehreren Namen gibt 0 zurück, sobald einer läuft (bis 25.11.2026 stand hier eine Zeile
   mit allen dreien; der Betrieb hat es beim Einspielen so geändert, Unterschied im Abschnitt „P1f auf dem Server abgearbeitet“):

   ```bash
   systemctl is-active --quiet erp && systemctl is-active --quiet erp-portal && systemctl is-active --quiet erp-portalpost && curl -fsS -H 'Host: kunde.dachkonzepte.gmbh' http://127.0.0.1:8010/health && echo
   ```

Den Unterschied in den Chat (er enthält keine Geheimnisse): `diff -u /home/tobias/update.sh.vor-p1 /home/tobias/update.sh`.

Mit dem ersten Einspielen danach (1.11.22 oder später) einmal S6b, Teil 2: `update.sh` holt die geänderte Einheit des Portals, installiert sie aber nicht.

**Erwartet beim nächsten Einspielen:** „Rechte für dkportal gesetzt …“, „Rechte für dkportal stimmen.“, `active` dreimal, `{"ok":true}`. Während des Neustarts
zeigt das Portal für ein paar Sekunden „Gleich wieder da“.
**Rückweg:** `cp -a /home/tobias/update.sh.vor-p1 /home/tobias/update.sh`.

#### S11 update.sh vergleicht die Einheiten (seit 1.11.26; erledigt am 26.11.2026)

Erst, wenn 1.11.26 eingespielt ist (`update.sh`). `update.sh` holt die Einheiten aus `scripts/server/`, installiert sie aber nicht; ab jetzt meldet es vor
der Zeile FERTIG jede, die von der installierten abweicht, mit dem Befehl zum Ansehen und Übernehmen -- installiert wird weiter von Hand (Antwort F2,
Umsetzung 1.11.26). Als tobias:

```bash
cd /home/tobias/erp
git log --oneline -1
.venv/bin/python scripts/pruefe_einheiten.py; echo "Rückgabe $?"
cp -a /home/tobias/update.sh /home/tobias/update.sh.vor-1.11.26
python3 scripts/server/update_einheiten_einfuegen.py /home/tobias/update.sh; echo "Rückgabe $?"
bash -n /home/tobias/update.sh && echo "Syntax ok"
diff -u /home/tobias/update.sh.vor-1.11.26 /home/tobias/update.sh
```

**Erwartet:** 1.11.26 oder später; „Einheiten wie im Repo: erp-portal.service, erp-portalpost.service, erp-webanfragen.service, erp-webanfragen.timer.“ und
`Rückgabe 0` (meldet es eine Abweichung, die Zeilen in den Chat -- erst ansehen, dann entscheiden); „update.sh geändert: der Vergleich der Einheiten steht
vor der Zeile FERTIG.“ und `Rückgabe 0`; „Syntax ok“; im `diff` vor `echo "=== FERTIG: …` genau diese vier neuen Zeilen:

    +echo "=== Einheiten ==="
    +PHASE="Einheiten"
    +/home/tobias/erp/.venv/bin/python /home/tobias/erp/scripts/pruefe_einheiten.py || echo "!!! Einheiten weichen vom Repo ab (oben) -- update.sh installiert sie nicht."
    +

**Abbrechen,** wenn das Einfügen „Abbruch: …“ meldet (Rückgabe 1, `update.sh` unverändert -- die Meldung in den Chat) oder „Syntax ok“ fehlt (dann
`cp -a /home/tobias/update.sh.vor-1.11.26 /home/tobias/update.sh`).
**Erwartet beim nächsten Einspielen:** vor FERTIG „=== Einheiten ===“ und „Einheiten wie im Repo: …“.
**Rückweg:** `cp -a /home/tobias/update.sh.vor-1.11.26 /home/tobias/update.sh`.

#### Danach

Den Bericht P1f schreibe ich aus den Ausgaben im Chat: Speicher je Dienst, Wert von `systemd-analyze security`, E4 (Portal und ERP), Textteil der Mail (S9.6),
Fristen von logrotate und Journal (S0), Steuer-Socket weg in ERP und Portal (S6b).

## P2: Unterlagen im Kundenportal lesen (ab 1.11.29)

### Bauplan P2 und Entscheidungen des Betriebs (26.11.2026)

Bauplan mit Befund und Nachtrag `bildgrundlage/bauplan_p2_d86b9df.txt` (nicht in Git; nach der Bestätigung ins Archiv der Berichte). Das Tragende:

- **Befund:** kein Byte einer Kundenunterlage in der Datenbank, alles unter `ERP_DATA_DIR`; Rechnung, Vertrag, Abnahmeprotokoll und Briefe als feste Fassung in
  der Ablage, Angebot und Auftragsbestätigung je Versand, Mahnung ab dem ersten Versand; der Einsatzbericht bis 1.11.28 bei jedem Abruf neu (N3). Fotos aus
  Bericht, Checkliste und Objekt verkleinert ohne Metadaten (Versuch: EXIF, GPS, XMP, ICC weg), Uploads der Kundenakte und der Projektmappe unverändert, auch
  Fotos. Zuordnung: jede Kette endet am Kunden, als alleiniger Filter reicht sie nicht -- ein Objekt wechselt den Kunden ohne Prüfung (N1), die Dokumentliste
  des Objekts mischt Projekte fremder Kunden, Projekte auf dem Objekt eines anderen Kunden, Kundenwechsel am Projekt. Versand: die An-Adresse ist bei den
  meisten Arten frei; `reached_client()` zählt jede Mail als beim Auftraggeber angekommen (N2). Nie per Mail: Einsatzberichte, Fotos, Dokumente, Mängel,
  Termine.
- **Entscheidungen (P2-1 bis P2-21):** Versionen 1.11.29 ff.; Weg B -- bereinigte Kopien in `/srv/dk-portal/dateien`, ausgeliefert von nginx über
  X-Accel-Redirect, dkportal liest keine Datei; automatisch sichtbar: Rechnungen (festgeschrieben, angekommen), Mahnungen, je Angebot und Auftragsbestätigung
  die zuletzt versendete Fassung (nur an die Adresse des Kunden, sonst Vorschlag), Vertrag, Abnahmeprotokoll, Wartungsprotokolle und Rapporte ab Unterschrift
  (PDF wie unterschrieben, mit Namen), Briefe der Anzeigen, feste Baustellentage -- auch für alles vor der Einladung; einzeln: Fotos und Dokumente (nur PDF und
  Rasterbild, Titel statt Dateiname); Freigeben ab Büro – Auftrag; Zahlstand fein (offen, teilweise bezahlt, bezahlt, Guthaben, in Schlussrechnung enthalten),
  „offen“ nur, was das ERP mahnen würde -- Einbehalt oder genutztes Skonto nie „offen“; Termine nur feste Baustellentage, Wartungsmonat und Kran später,
  Büro-Kalender nie; Mängel in P4; Gruppen nach Adresse des Objekts und Auftragsnummer; Projekt im Archiv (von Hand oder Aufbewahrung): nichts; 25 MB je
  Datei, Bremsen laut Bauplan, Pixelgrenze; Kopien nicht in der Sicherung; „Ansehen“ im selben Tab; keine Mail bei neuen Unterlagen; Hausverwaltungen erst
  ab P5.
- **Zusätzlich:** Reihenfolge 1.11.29 = N3, 1.11.30 = N1, dann P2a, danach anhalten; N2 erst nach P2. P2d: Trigger auf Anweisungsebene statt (nur) Listener
  am Flush prüfen. P2b: der internal-Block von nginx setzt alle Kopfzeilen selbst (auch HSTS), Kopien mit Endung und festen types; Fotos neu kodiert im
  Kindprozess mit Grenze für Speicher und Zeit; Metadaten der vom ERP erzeugten PDFs prüfen; Rauchtest auch mit Android. P2c: Fotos mehrere auf einmal
  freigeben; vor dem Einladen zeigt das ERP, was der Kunde ab dann sieht. Oberfläche des Portals erst nach den Entwürfen (P2e).
- **Gemessen auf dem Server (26.11.2026):** sent_documents 2 Dateien, project_files 1, service_report_photos 42 (3,2 MB), webanfragen 8 (größte 2,3 MB),
  roof_area_sketches 3; 108 GB frei.

### Umsetzung 1.11.29: feste Fassung des Einsatzberichts beim Unterschreiben (Nebenbefund N3)

- `app/service_reports.py::sign_report()`: nach Status, Unterschriften und Zeiten (und dem Fortschreiben eines Wartungsvertrags) im selben Commit
  `_feste_fassung()` -- `build_service_report_pdf()` (lokal importiert, Regel 3), `store_sent_document()` mit Art „einsatzbericht“, Dokument-ID = Bericht,
  Nummer = Auftragsnummer, Dateiname wie der Download (`pdf_dateiname()`), dann `ServiceReport.pdf_document_id` (Migration `d7f3a9c1e284`, FK auf
  sent_documents; downgrade verweigert, solange ein Bericht eine Fassung trägt). Scheitert PDF oder Ablage: zurückrollen, die eben geschriebenen
  Unterschriftsbilder wieder löschen, 400 mit `FESTE_FASSUNG_GESCHEITERT` („… nicht unterschrieben, nichts gespeichert …“); `logger.error` nur mit dem
  Klassennamen (Regel 18).
- Die Unterschrift lädt den Bericht mit FOR UPDATE (`populate_existing`, wie Checkliste und Vertrag): eine zweite gleichzeitige wartet und bekommt „bereits
  unterschrieben“. Dahinter der Wächter am Modell (`_service_report_pdf_fixed`, wie bei der Rechnung): die Fassung wechselt genau einmal von leer auf die
  Ablage.
- `GET /api/service-reports/{id}/pdf` über `document_pdf_response()` (wie Rechnung und Mahnung): mit Fassung deren Bytes und `X-DK-Ablage`, verändert 409,
  fehlend 410, nie still neu erzeugt; ohne Fassung wie bisher neu erzeugt. Ein Entwurf hat wie bisher kein PDF (400).
- `app/sent_documents.py`: „einsatzbericht“ in `DOCUMENT_TYPES`, `frozen_version()` kennt die Fassung am Bericht. `app/dispatch_documents.py`: Eintrag im
  Verzeichnis, der jede Zustellung ablehnt (es gibt keinen Versandweg für Einsatzberichte); Projekt und Filter des Versandprotokolls kennen die Art.
- Unverändert: die Ansicht der Monteurin in der Wartungshistorie (`build_service_report_pdf_for_field()`, ohne die Zeiten der Kollegen) entsteht weiter neu --
  sie ist keine Kundenfassung; der Bestand bleibt ohne Fassung.

#### Festlegungen 1.11.29 (bestätigt am 26.11.2026)

1. Die Unterschrift legt im selben Commit das PDF als feste Fassung in die Ablage (Art „einsatzbericht“, Dokument-ID = Bericht, Nummer = Auftragsnummer,
   Dateiname wie der Download) und vermerkt sie am Bericht.
2. Nach der Unterschrift kommt der Download aus der Ablage (`X-DK-Ablage`); verändert 409, fehlend 410, nie neu erzeugt. Ein Entwurf hat weiter kein PDF.
3. Scheitert PDF oder Ablage, ist nichts gespeichert -- kein Status, keine Unterschrift, keine Unterschriftsbilder, kein Eintrag in der Ablage; Meldung 400.
4. Die feste Fassung steht fest: genau einmal von leer auf die Ablage (Wächter am Modell).
5. Vor 1.11.29 unterschriebene Berichte bleiben ohne Fassung: PDF wie bisher bei jedem Abruf neu, kein Abruf legt etwas ab, nichts nachträglich ohne
   Zustimmung des Betriebs; im Portal nicht sichtbar.
6. Ein Einsatzbericht wird über das Versandprotokoll weder versendet noch zugestellt; dort gehört er zu seinem Projekt.
7. Die Unterschrift sperrt die Zeile des Berichts: zwei gleichzeitige ergeben eine Unterschrift und eine Fassung.
8. Die Ansicht der Monteurin in der Wartungshistorie bleibt neu erzeugt (keine Kundenfassung, ohne Zeiten der Kollegen).

#### Vorschlag: vor 1.11.29 unterschriebene Berichte (nichts gebaut)

- **Ab 1.9.42 unterschrieben** (mit gespeicherten Zeiten, `time_rows_json`): auf Wunsch einmalig nachträglich festschreiben -- ein Skript nur für den Server
  (Vorschau mit Zahl, dann Bestätigung, Muster `scripts/personalnummern_einlesen.py`), die Fassung als „nachträglich festgeschrieben am …“ in der Ablage
  gekennzeichnet. Ehrlich dazu: Zeiten, Prüfpunkte, Befunde, Material und Unterschriften stimmen mit dem Unterschriebenen überein, Namen und Briefkopf sind die
  von heute.
- **Vor 1.9.42 unterschrieben** (ohne gespeicherte Zeiten): nicht nachträglich -- das PDF zeigte heute alle Zeiten des Auftrags, nicht die des Berichtstags; im
  Portal nie, auf Wunsch einzeln als Dokument über die Projektmappe.
- Zahl auf dem Server (nur lesend): `sudo -u postgres psql -tAX -d dachkonzepte -c "select count(*), count(*) filter (where time_rows_json is not null),
  count(*) filter (where pdf_document_id is not null) from service_reports where status = 'unterschrieben'"` -- unterschrieben, davon mit Zeiten, davon mit
  Fassung (nach 1.11.29).
- **Entschieden am 27.11.2026** (nach der Zählung, siehe „Antworten des Betriebs zu den Berichten 1.11.32 bis 1.11.34“): nicht nachträglich festschreiben,
  kein Skript. Die zwei schon unterschriebenen Berichte bleiben ohne Fassung und erscheinen nie im Portal.

#### Tests und Prüfung 1.11.29

`tests/test_v819_einsatzbericht_feste_fassung.py` (je Festlegung 1–7 ein Test, Nr. 7 gegen PostgreSQL mit `_run()` aus `test_v375`). Angepasste Erwartung
(Regel 28): `test_v467_zeiten_einsatzbericht.py::test_alter_bericht_ohne_stand_wie_vor_1937` -- altes Soll: nach dem Unterschreiben `time_rows_json` geleert,
das PDF zeigt alle Zeiten des Auftrags; neues Soll: dasselbe, der Bericht wird dafür ohne feste Fassung unterschrieben (ein Bericht von vor 1.9.42 hat keine;
mit Fassung käme das PDF aus der Ablage); ebenso `test_v473_zeitpunkte_berlin.py::test_unterschriftszeit_auf_der_seite_wie_im_pdf` -- altes Soll:
Unterschriftszeit nach dem Unterschreiben auf 15:33 UTC gesetzt, PDF und Seite zeigen 17:33; neues Soll: dasselbe, ohne feste Fassung unterschrieben
(die feste Fassung zeigte die echte Zeit der Unterschrift; im ersten vollen Lauf rot). Migration auf einer Wegwerf-SQLite hin, zurück, hin. Klicktests vor dem Commit: alle, die einen Einsatzbericht
unterschreiben oder sein PDF abrufen. Gegenproben: `gegenproben-portal.md`, „1.11.29“.

### Umsetzung 1.11.30: ein Objekt wechselt den Kunden nur geprüft (Nebenbefund N1)

- `app/objekt_kundenwechsel.py::kunde_wechseln()`, aufgerufen von `PUT /api/properties/{id}`, sobald `customer_id` einen anderen Kunden nennt (derselbe
  Kunde ist kein Wechsel -- das Formular schickt ihn immer mit): Sperre der Objektzeile, dann `sperrgrund()` -- je Bereich aus `SPERREN` die Zahl (Projekt,
  auch eines anderen Kunden, Anfrage, Wartungsvertrag, Dokument, Checkliste, Abnahme, Mangel) und die Hauptadresse; gibt es einen Grund, 409 mit Bereichen und
  Rat („Lege beim neuen Kunden ein neues Objekt an.“), nichts geändert. Sonst Pflicht `kundenwechsel_grund` (höchstens 500 Zeichen; fehlt sie oder ist sie
  leer, 422) und ein Eintrag in der Änderungshistorie (Aktion „Kunde gewechselt“, alter und neuer Kunde, Begründung). Was zum Gebäude gehört, wechselt mit
  (`WANDERT_MIT`: Dachflächen; die Herkunft aus dem Adressimport). Jeder Fremdschlüssel auf properties steht in genau einer der beiden Listen.
- Keine Oberfläche: in der Oberfläche des ERP gibt es keinen Weg, den Kunden eines Objekts zu ändern -- das Stammdaten-Formular leitet beim Bearbeiten
  eines Objekts auf die Objektseite um (`master_data_form.html::init()`), Objektseite und Kundenakte schicken keinen Kunden mit. N1 betraf nur die
  Schnittstelle (ein Skript oder ein direkter Aufruf); ein Feld für die Begründung wäre nie zu sehen gewesen (beim Bauen gemerkt, wieder entfernt).
- Die Sperre der Objektzeile (FOR UPDATE) hält einen Vorgang ab, der zwischen Zählen und Umsetzen dazukäme -- keine eigene Festlegung, keine eigene
  Gegenprobe (nur unter PostgreSQL wirksam).

#### Festlegungen 1.11.30 (bestätigt am 26.11.2026)

1. Hängt am Objekt ein Vorgang (Projekt -- auch eines anderen Kunden --, Anfrage, Wartungsvertrag, Dokument, Checkliste, Abnahme, Mangel), wechselt es den
   Kunden nicht: 409 mit Bereichen, Zahl und dem Rat, beim neuen Kunden ein neues Objekt anzulegen; nichts geändert.
2. Die Hauptadresse eines Kunden wechselt den Kunden nie.
3. Sonst nur mit Begründung (Pflicht, höchstens 500 Zeichen); ohne sie 422 und nichts geändert -- auch keine anderen Felder.
4. Der Wechsel steht mit altem und neuem Kunden und der Begründung in der Änderungshistorie; Dachflächen wechseln mit dem Objekt.
5. Derselbe Kunde ist kein Wechsel und braucht keine Begründung.
6. Jeder Fremdschlüssel auf Objekte steht in genau einer Liste: sperrt den Wechsel oder wechselt mit.
7. Keine Oberfläche für den Kundenwechsel (es gibt keinen Weg dorthin); wird einer gebraucht, als eigene Runde mit Feld für die Begründung.

#### Tests und Prüfung 1.11.30

`tests/test_v820_objekt_kundenwechsel.py` (15 Tests). Angepasste Erwartung (Regel 28):
`test_v067_admin_and_masterdata_edit.py::test_property_and_employee_can_be_edited_and_are_audited` -- altes Soll: das Objekt wechselt ohne Begründung den
Kunden; neues Soll: dasselbe mit `kundenwechsel_grund` (im ersten vollen Lauf rot mit „Bitte eine Begründung …“). Keine Seite geändert, keine Bilder. Klicktests vor dem Commit:
alle, die das Formular der Stammdaten oder die Objektseite öffnen. Gegenproben: `gegenproben-portal.md`, „1.11.30“.

### Umsetzung 1.11.31: Freigaben und Lese-Funktionen der Unterlagen (P2a)

- **Tabelle `portal_freigaben`** (`app/models.py::PortalFreigabe`, Migration `e5c8a1f3b9d2`): Kunde fest (`customer_id`), Art (`FREIGABE_ARTEN`: angebot,
  auftrag, vertrag, rechnung, mahnung, abnahmeprotokoll, einsatzbericht, brief, checkliste, foto, dokument), Quelle als Tabelle und ID ohne Fremdschlüssel
  (`FREIGABE_QUELLEN`, zwölf Tabellen -- eine gelöschte Quelle lässt die Freigabe ruhen, statt das Löschen zu sperren), Titel (höchstens 120 Zeichen) und
  Datum fürs Portal, Regel (leer = einzeln, ab P2c), freigegeben und zurückgenommen mit Konto, Name und Grund, Kopie (Name, Typ nur PDF oder JPEG, Größe,
  Prüfsumme, bereit, fester Fehlergrund -- ab P2b). Nie gelöscht; höchstens eine nicht zurückgenommene je Quelle (Teilindex). In `KEIN_TEIL` des
  Archivschutzes (Zurücknehmen geht auch im Archiv, eine neue Freigabe nicht); eine Freigabe hält den Rückweg eines Adressimports auf wie ein Zugang.
- **Funktionen der Datenbank** (`app/portal/unterlagen.py`, Text wörtlich in der Migration, unter PostgreSQL nach jedem `create_all()`): Helfer ohne
  SECURITY DEFINER -- `portal_quelle(quelle, id)` liefert je Quelle über einen festen Zweig Kunde, Auftragsnummer und Adresse des Objekts (Rechnung und
  Mahnung über den Kunden der Rechnung, Auftrag, Vertrag, Bericht, Fotos, Protokolle und Briefe über den Kunden des Auftrags, Angebot und Projektdokument über
  das Projekt, Objektdokument über das Objekt, Kundendokument direkt), `portal_projekt_offen`, `portal_adresse`, `portal_fassung_gilt` (keine der gezeigten
  Unterschriften verworfen), `portal_sichtbar`, `portal_kunde_der_sitzung`, `portal_protokoll_freigabe`. Für den Benutzer des Portals: `portal_unterlagen`,
  `portal_datei_anfordern`, `portal_datei` (rechte.py: 11 Funktionen statt 8).
- **Sichtbar** ist eine Freigabe nur, wenn sie zum Kunden der Sitzung gehört, nicht zurückgenommen ist, ihre Kopie bereit liegt und `portal_quelle()` heute
  denselben Kunden nennt. Nie: Rechnung im Entwurf, Mahnung nicht versendet oder ersetzt, Einsatzbericht ohne feste Fassung (1.11.29), verworfene Abnahme,
  überholte Fassung einer Checkliste, Projekt als Mustervorgang oder im Archiv (von Hand oder Aufbewahrung, Entscheidung P2-11), Objektdokument einer Anfrage
  im Archiv. Passt die Kette nicht mehr, ruht die Freigabe -- sie steht weiter, im Portal nichts.
- **Kein GET schreibt** bleibt: `portal_unterlagen` und `portal_datei_anfordern` schreiben das Zugriffsprotokoll (neue Aktionen „unterlagen“ und
  „datei_angefordert“, die Freigabe in `objekt_art`/`objekt_id` -- die Spalten gab es seit P1) und zählen die Bremsen (Bauplan B7); `portal_datei` liest nur.
- Noch nicht: Kopien und Auslieferung (P2b), Freigeben im ERP und die automatischen Regeln (P2c), Zahlstand und Termine (P2d), Seiten (P2e).

#### Festlegungen 1.11.31 (bestätigt am 26.11.2026)

1. Sichtbar ist nur, was als Freigabe für den Kunden der Sitzung steht, nicht zurückgenommen ist und eine bereite Kopie hat.
2. Zusätzlich führt die Kette der Quelle heute zu genau diesem Kunden -- sonst ruht die Freigabe (auch der neue Kunde sieht sie nicht).
3. Nie sichtbar: Rechnung im Entwurf, ersetzte oder nicht versendete Mahnung, Einsatzbericht ohne feste Fassung, Projekt als Mustervorgang oder im Archiv.
4. Jede Quelle hat genau einen festen Zweig in SQL, kein dynamisches SQL; eine neue Quelle braucht einen eigenen Zweig.
5. Die Gruppe im Portal ist Auftragsnummer und Adresse des Objekts, nie der Projekttitel.
6. Eine Datei gibt es nur nach einer Anforderung derselben Sitzung für diese Freigabe in den letzten 30 Minuten; `portal_datei()` schreibt nichts.
7. Liste und Anforderung schreiben das Zugriffsprotokoll (Aktion, Ergebnis, Freigabe, kein Inhalt) und zählen die Bremsen: Liste 120 je Sitzung und
   Stunde; Anforderung 300 je Zugang und Stunde, 1500 je Tag, 300 je Anschluss und Stunde, 5000 gesamt je Stunde.
8. Der Benutzer des Portals liest `portal_freigaben` nicht und ruft keinen Helfer auf; er darf genau die drei Funktionen.
9. Höchstens eine nicht zurückgenommene Freigabe je Quelle; eine Freigabe wird nie gelöscht und hält den Rückweg eines Adressimports auf.
10. Quelle als Tabelle und ID ohne Fremdschlüssel: das Löschen einer Quelle sperrt nichts, die Freigabe ruht.
11. Im Protokoll der Karte „Kundenportal“ heißen die neuen Aktionen „Unterlagen geöffnet“ und „Unterlage angefordert“; fand eine Anforderung nichts,
    „– nicht verfügbar“ (`ERGEBNIS_JE_AKTION`, nicht „unbekannter Link“).

#### Tests und Prüfung 1.11.31

`tests/test_v821_portal_unterlagen.py` (12 Tests, sechs davon gegen PostgreSQL mit der Testrolle `dkportal_test`; ein Wegwerf-Schema je Test). Im ersten
vollen Lauf rot und behoben: `test_v809` (die Karte braucht für jede Aktion einen Text -- daraus Festlegung 11) und `test_v738` (ein Auftrag im Test
bekommt sein Angebot sichtbar über `quell_angebot()`, nicht über eine Variable). Jeder Zweig von
`portal_quelle()` läuft einmal fehlerfrei; positiv geprüft sind die Zweige Rechnung, Mahnung, Angebot, Auftrag, Einsatzbericht, Kundendokument und
Objektdokument -- Checkliste, Brief, Foto des Berichts, Projektdokument, Datei am Mangel und Beleg der Abnahme nur auf Lauf und leeres Ergebnis; ihre echten
Fälle kommen mit den Regeln in P2c. Die Migration lief auf SQLite hin, zurück, hin und unter PostgreSQL in `test_v816` (alembic upgrade head als Kindprozess).

Angepasste Erwartungen (Regel 28):
- `test_v799_portal_rechte.py::test_feste_werte_als_check_wie_in_der_migration` -- altes Soll: alle CHECKs des Portals wörtlich in `4f8a2c6e1b97`; neues
  Soll: der CHECK der Aktionen wörtlich in `e5c8a1f3b9d2`, dessen `AKTION_VORHER` gleich dem Stand in `4f8a2c6e1b97`; die übrigen wie bisher. Dazu
  `portal_freigaben` in `KEIN_ZUGRIFF` und in der Liste der Tabellen mit Kundendaten.
- `test_v800_portal_funktionen.py::test_security_definer_genau_die_rechte_des_portals_und_keine_fuer_alle` -- altes Soll: `rechte.FUNKTIONEN` gleich den
  Funktionen aus `funktionen.py`; neues Soll: dazu die drei aus `unterlagen.py`. `test_pg_create_all_legt_die_funktionen_an` -- altes Soll: 14 Funktionen
  im Schema; neues Soll: 14 + 7 Helfer + 3 = 24.
- `test_v816_portal_rechte_skript.py::test_pg_skript_als_kindprozess_setzen_dann_pruefen` -- altes Soll: „… 8 Funktionen …“ und `(9, 8)`; neues Soll:
  „… 11 Funktionen …“ und `(9, 11)`.
- `test_v793_archivschutz.py`: `portal_freigaben.customer_id` in `KEIN_TEIL` mit Grund.

Gegenproben: `gegenproben-portal.md`, „1.11.31“. Beim Einspielen: Migration über `update.sh` (probt gegen spielwiese); danach meldet `portal_rechte.py
--setzen` „2 Tabellen (nur Lesen), 11 Funktionen, 45 Anweisungen“ (bisher 8 Funktionen). Sonst kein Server-Schritt, nichts im Portal sichtbar.

#### Prüfungen für P2d (Zusatz 2 des Betriebs) und P2b (Zusätze 3–5), festgehalten

- P2d: ein Listener am Flush sieht keine Massen-Updates (`session.execute(update(...))`), keine Skripte, kein SQL in Migrationen -- vor dem Bau Trigger auf
  Anweisungsebene für die Tabellen der Liste prüfen (setzt `portal_veraltet` und NOTIFY, der Postbote rechnet dann alle Kunden mit Portal neu); bleibt es beim
  Listener, sagt der Bericht warum.
- P2b: der internal-Block von nginx setzt den vollständigen Satz an Kopfzeilen selbst (auch HSTS; ein add_header in einer location verdrängt alle des Servers),
  Wächter darauf; Kopien mit Endung (.pdf/.jpg), im Block feste `types { application/pdf pdf; image/jpeg jpg; }` und `default_type
  application/octet-stream`; Fotos neu kodiert in einem Kindprozess mit Grenze für Speicher (RLIMIT_AS) und Zeit, Absturz oder Zeitüberschreitung ein fester
  Fehlergrund, der Postbote läuft weiter (Test mit Bombe und kaputtem Bild); die Metadaten der vom ERP erzeugten PDFs prüfen (Author, Title, Subject,
  Creator, Producer, Keywords) und Benutzernamen oder Interna melden; Rauchtest auch auf Android mit „Herunterladen“ und Öffnen der Datei.

### Antworten des Betriebs zu den Berichten 1.11.29 bis 1.11.31 (26.11.2026)

- Bestätigt: 1.11.29-1 bis -8, 1.11.30-1 bis -7, 1.11.31-1 bis -11. Berichte und Bauplan P2 seit 26.11.2026 im Archiv der Berichte.
- Vor P2b als 1.11.32 nur Tests: Matrix je Quelle (alle zwölf) × Fall gegen PostgreSQL mit der Testrolle, jede Zelle Testname oder „entfällt (Grund)“, je
  Zweig eine Gegenprobe (Kette entfernt -> fremde Freigabe sichtbar -> rot); ein Fehler im SQL wird gemeldet und behoben. Dazu ein Test: die feste Fassung
  des Einsatzberichts zeigt die Unterschriftszeit in Berliner Zeit, Winter und Sommer.
- Quelle als Tabelle und ID statt typisierter Spalten (Bauplan B4.1): einverstanden. **Abweichungen vom Bauplan künftig ausdrücklich als solche melden**
  (eigener Abschnitt im Bericht).
- Für P2c vorgemerkt: ruht die Freigabe einer Quelle für einen anderen Kunden, scheitert eine neue Freigabe an „höchstens eine je Quelle“ -- dann eine klare
  Meldung im ERP („erst beim bisherigen Kunden zurücknehmen“), kein Fehler.
- Schon unterschriebene Einsatzberichte: Entscheidung nach der Zählung auf dem Server, bis dahin nichts.
- Danach P2b wie im Bauplan mit den Zusätzen aus dem Nachtrag; nach P2b anhalten.

### Umsetzung 1.11.32: Matrix je Quelle und Fall, zwei Lücken der Kette

- `tests/test_v822_portal_unterlagen_matrix.py`: 15 Zeilen (die zwölf Quellen, die Ablage nach Angebot, Auftragsbestätigung und Vertrag, die Fassung einer
  Checkliste nach Auftrag und Objekt) × zehn Fälle; jede Zelle ein eigener Test `test_matrix[<zeile>-<fall>]` gegen PostgreSQL mit der Testrolle
  `dkportal_test` (ein Schema für das Modul, je Test eigene Kunden und eigene Anschlüsse) oder in `ENTFAELLT` mit Grund -- ein Wächter verlangt genau eins.
  Jeder Fall prüft zuerst, dass die Unterlage vor der Änderung sichtbar war. 143 Zellen, 7 entfallen (Kundendokument ohne Objekt und Projekt, Objektdokument
  und Checkliste am Objekt ohne Projekt).
- Gefunden und behoben: `portal_quelle()` prüfte beim Brief der Anzeigen nicht, ob die Unterschrift dahinter verworfen ist (bei der Fassung einer Checkliste
  schon), und bei der Datei am Mangel nicht, ob der Mangel verworfen ist -- die Freigabe blieb sichtbar. Beide ruhen jetzt; `portal_quelle()` neu in der
  Migration `f2b7d4a9c1e3` (CREATE OR REPLACE, downgrade setzt den Text aus `e5c8a1f3b9d2`). `app/portal/unterlagen.py::MIGRATIONEN` nennt die Migrationen
  mit dem Text der Funktionen; der Vergleich in `test_v821` nimmt je Funktion die neueste.
- `test_v819`: die feste Fassung zeigt die Unterschrift in Berliner Zeit (Winter 10:05 UTC -> 11:05, Sommer 10:05 UTC -> 12:05), Monteur und Kunde, aus der
  Ablage gelesen.

#### Festlegungen 1.11.32 (bestätigt am 27.11.2026)

1. Ein Brief der Anzeigen ist nur sichtbar, solange die Unterschrift dahinter nicht verworfen ist (wie die Fassung einer Checkliste).
2. Ein Foto oder Beleg am Mangel ist nur sichtbar, solange der Mangel nicht verworfen ist.
3. Jede Quelle × jeder Fall steht in der Matrix als Test oder mit Grund als „entfällt“; eine neue Quelle oder ein neuer Fall kommt dort hinein.

#### Tests und Prüfung 1.11.32

Matrix 143 Tests (dazu der Wächter der Zellen); vor der Korrektur rot genau `notice_letters-quelle_ungueltig` und `defect_files-quelle_ungueltig`. Die neue
Migration lief unter PostgreSQL hin, zurück und wieder hin (Text von `portal_quelle()` je Stand geprüft) und in `test_v816`. Angepasste Erwartung (Regel 28):
`test_v821_portal_unterlagen.py::test_migration_traegt_anweisungen_und_checks_woertlich` -- altes Soll: `e5c8a1f3b9d2.ANWEISUNGEN` gleich
`unterlagen.ANWEISUNGEN`; neues Soll: `e5c8a1f3b9d2` mit den Fassungen der neueren Migrationen aus `MIGRATIONEN` ersetzt gleich `unterlagen.ANWEISUNGEN`.
Gegenproben: `gegenproben-portal.md`, „1.11.32“. Beim Einspielen: Migration über `update.sh`; sonst nichts.

### Umsetzung 1.11.33 (P2b, Teil 1): Kopien der freigegebenen Unterlagen

- `app/portal_kopien.py::abgleich()` (der Postbote, Benutzer des ERP): Kopie weg, wo sie nicht mehr sein soll (zuerst die Zeile, dann die Datei); zu jeder
  Freigabe, die sein soll, ohne Kopie und ohne Fehler, eine neue; im vollen Lauf dazu fehlende Dateien neu, Waisen und alte Teil-Dateien weg. „Soll sein“:
  nicht zurückgenommen, Kunde nicht im Archiv, `portal_quelle()` führt heute zum Kunden der Freigabe -- dieselbe Kette wie im Portal.
- Quelle: Ablage (`sent_documents`, Rechnung und Mahnung über `frozen_version()`, Einsatzbericht über `pdf_document_id`, Fassung und Brief über
  `sent_document_id`) mit Prüfsumme der Ablage; Fotos und Dokumente aus ihrem Ordner (Pfad muss im Ordner der Art bleiben); Belege der Abnahme und Dateien am
  Mangel über `read_acceptance_file()` (Prüfsumme). Typ nur am Inhalt: PDF byte-gleich, Rasterbild neu kodiert, alles andere „falscher_typ“.
- Fotos im Kindprozess `app/portal_foto_kind.py` (`python -I`, Umgebung nur PATH): Grenze für Speicher zuerst (Linux RLIMIT_AS, Windows Job-Objekt),
  nur JPEG/PNG/WebP/GIF, über 64 Mio. Bildpunkte „zu_gross“, Drehung angewandt, sRGB, Transparenz auf Weiß, erstes Bild, Kante 1600, Qualität 82, aus einem
  frischen Bild (kein EXIF, XMP, IPTC, ICC, Kommentar, kein angehängter Rest). Zeitgrenze 60 s (subprocess beendet das Kind). Rückgabe 10/11 -> nicht_lesbar
  bzw. zu_gross, alles andere „abbruch“.
- Datei: `<64 hex>.pdf` bzw. `.jpg`, exklusiv als Teil-Datei geschrieben, umbenannt, gegengelesen, 0640; die Zeile wird erst danach bereit (bedingtes UPDATE:
  nicht zurückgenommen, noch ohne Kopie und Fehler -- eine Rücknahme während des Kodierens lässt die Datei gleich wieder verschwinden). Zeit aus der
  Datenbank (`portal_jetzt()`).
- Fehler: festes Wort an der Zeile (`fehlt` neu, `zu_gross`, `pruefsumme`, `falscher_typ`, `nicht_lesbar`, `abbruch`), kein zweiter Versuch von selbst; das
  Protokoll nennt nur Nummer der Freigabe und Wort. Keine Rechte an der Quelle (OSError beim Lesen) ist „nicht_lesbar“; ein Fehler am eigenen Ordner
  (fehlt, keine Rechte, Platte voll) ist kein Fehlerwort: der Postbote protokolliert die Klasse und versucht es im nächsten Lauf wieder.
- Ordner: `.datenbank` nennt `current_database()/current_schema()`; fehlt sie und liegen keine Kopien da, entsteht sie; sonst `OrdnerFremd` -- dort wird
  nichts angelegt oder gelöscht. Fremde Dateien bleiben (nur gezählt).
- Weckruf: `app/portal/weckruf.py`, Auslöser auf Anweisungsebene nach INSERT und UPDATE von `zurueckgenommen_am` -> `pg_notify('portal_freigabe', '')`;
  Migration `a7c3e9f1d2b4` (Text wörtlich, dazu `kopie_fehler` mit „fehlt“; downgrade setzt „fehlt“ zurück auf leer). Unter SQLite nur die Prüfung (Batch,
  der Teilindex bleibt -- geprüft hin und zurück).
- Postbote (`laufen()`): LISTEN auf beide Kanäle; Kopien beim Start und alle 15 Minuten voll, auf den Weckruf und solange Arbeit wartet; je Durchgang
  höchstens 5 s an neuen Kopien, dann wieder Codes. Ohne `PORTAL_DATEIEN` Codes wie bisher, Hinweis im Protokoll. Am Ende gibt er Sperre und LISTEN frei
  (Nebenbefund: bis 1.11.32 ging die Verbindung mit beidem in den Pool zurück -- auf dem Server ohne Folgen, der Prozess endet; im Test hielt sich ein zweiter
  Postbote derselben Engine für überzählig).
- Einheit `erp-portalpost`: MemoryHigh 640M, MemoryMax 768M (bis 1.11.32 200M/256M -- der Kindprozess zählt zur Einheit), UMask 0027. `.env.example` nennt
  `PORTAL_DATEIEN`.
- Messung (lokal, Windows, Rauschbilder als ungünstigster Fall): 48 Mio. Bildpunkte als JPEG (33 MB) -> 0,5 s, Spitze im Kind 305 MB; 50 Mio. als PNG mit
  Alpha (117 MB, über der Grenze von 25 MB) -> 0,9 s, 560 MB. Auf dem Server misst `scripts/pruefe_portal_foto.py` (Server-Schritt P2b-4) unter Linux die
  Spitze des Kinds.
- Metadaten der PDFs des ERP (Nachtrag 5, erzeugt in einer Wegwerf-Datenbank und ausgelesen): Author = Firmenname aus den Einstellungen (Scan-Seite des
  Vertrags „anonymous“), Title = Nummer und Bezeichnung, wie sie sichtbar auf dem PDF stehen (Rechnung „R-… - Rechnung“, Auftrag „<Nr> - <Titel>“, Checkliste
  „<Vorlage> – <Kontext>“, Einsatzbericht „<Art> - Auftrag <Nr>“), Creator „(unspecified)“ bzw. „anonymous“, Producer „ReportLab PDF Library -
  (opensource)“ bzw. „PDFium“ (zusammengefügte Abschrift), Subject „(unspecified)“, Keywords leer, Datum mit Zeitzone, kein XMP. Kein Benutzername, nichts
  Internes. Hochgeladene PDFs (Kundenakte, Projektmappe, Belege) tragen ihre eigenen Angaben -- dafür der Hinweis beim Freigeben (B6, P2c).

#### Festlegungen 1.11.33 (bestätigt am 27.11.2026)

1. Kopien legt nur der Postbote an, im Ordner `PORTAL_DATEIEN`; Name zufällig (64 hexadezimale Zeichen) mit Endung .pdf bzw. .jpg, Datei 0640; die Zeile
   wird erst nach geschriebener und gegengelesener Datei bereit.
2. PDFs byte-gleich, nur aus der festen Fassung der Ablage (mit Prüfsumme) bzw. aus der gespeicherten Datei; nie neu erzeugt.
3. Jedes Rasterbild wird neu kodiert, im Kindprozess mit 1 GiB Speicher (seit 1.11.35 448 MB, Festlegung 1.11.35-3), 60 s, 64 Mio. Bildpunkten (schon darüber „zu_gross“), Kante 1600, Qualität 82,
   sRGB, ohne jede Angabe aus der Datei; das Kind bekommt nur PATH.
4. Höchstens 25 MB je Quelle.
5. Fehlerwörter fest (`fehlt` neu); kein zweiter Versuch von selbst (P2c setzt zurück); das Protokoll nennt nur Nummer und Wort.
6. Rücknahme, Ruhen und Kunde im Archiv: Kopie weg (Zeile zuerst, dann Datei); wird die Freigabe wieder sichtbar, entsteht eine neue Kopie mit neuem Namen.
7. Voller Lauf alle 15 Minuten: fehlende Datei neu, Waise und Teil-Datei älter als eine Stunde weg, fremde Dateien bleiben.
8. Ein Ordner gehört genau einer Datenbank (`.datenbank`); passt sie nicht, legt und löscht der Postbote dort nichts.
9. Weckruf über einen Auslöser auf Anweisungsebene an `portal_freigaben`, nur nach INSERT und nach UPDATE von `zurueckgenommen_am`.
10. Je Durchgang höchstens 5 s an neuen Kopien, dann wieder die Codes; wartet noch Arbeit, geht es ohne Warten weiter.
11. Ohne `PORTAL_DATEIEN` laufen die Codes weiter, Kopien entstehen keine (Hinweis); ein Fehler am Ordner beendet den Postboten nicht.
12. Einheit `erp-portalpost`: MemoryHigh 640M, MemoryMax 768M, UMask 0027.
13. `laufen()` gibt am Ende Sperre und LISTEN frei.

#### Abweichungen vom Bauplan (1.11.33)

- B5 „dazu eine Vorschau 400 px für Listen“: nicht gebaut -- kommt mit den Seiten (P2e), wenn die Entwürfe zeigen, ob und in welcher Größe.
- B2.1 „NOTIFY … (Freigabe, Rücknahme, Ruhen)“: Ruhen weckt nicht -- der Auslöser sitzt nur an `portal_freigaben`. Die Kopie einer ruhenden Freigabe geht im
  nächsten vollen Lauf (höchstens 15 Minuten); im Portal ist sie sofort weg (die Funktionen prüfen die Kette selbst). Mit P2d (Auslöser an den Tabellen der
  Liste) ließe es sich mit erledigen.
- B4.1 Fehlergründe: dazu „fehlt“ (Quelle oder ihre Datei fehlt) -- der Bauplan nannte nur Beispiele.
- Nachtrag 4: die Grenze RLIMIT_AS gibt es nur unter Linux; lokal (Windows) setzt das Kind ein Job-Objekt mit derselben Grenze. Die Tests prüfen den Weg
  unter Windows; den unter Linux prüft `scripts/pruefe_portal_foto.py` auf dem Server (P2b-4) -- hier gibt es kein Linux.
- B2.1 „Speicher des Postboten … rund 100 MB“: der Kindprozess zählt zur Einheit, deshalb deren Grenze höher (Festlegung 12).

#### Tests und Prüfung 1.11.33

`tests/test_v823_portal_kopien.py` (36, PostgreSQL mit Testrolle; je Zeile der Matrix eine echte Datei), `tests/test_v824_portal_foto.py` (17, durch den echten
Kindprozess, dazu das Prüfskript als Kindprozess), `tests/test_v818_portal_skripte_kindprozess.py` (der Postbote als eigener Prozess legt auf einem Schema aus
alembic eine Kopie an). Gefunden beim Bauen: RETURNING gab beim Entfernen den neuen Wert (leer) zurück -- die Datei blieb liegen; seither die Namen vorher
unter Sperre gelesen. Angepasste Erwartungen (Regel 28):
- `test_v800_portal_funktionen.py::test_pg_create_all_legt_die_funktionen_an` -- alt: 14 + Helfer + Funktionen der Unterlagen; neu: dazu 1 (die Funktion des
  Weckrufs, `portal_freigabe_geweckt`).
- `test_v805_portal_postbote.py::test_einheit_des_postboten` -- alt: MemoryMax 256M, MemoryHigh 200M; neu: 768M, 640M und UMask 0027.
- `test_v818_portal_skripte_kindprozess.py::test_pg_postbote_als_kindprozess` -- alt: „Postbote bereit (LISTEN portal_post)“; neu: „Postbote bereit (LISTEN
  portal_post, portal_freigabe)“, dazu die Kopie.
- `test_v821_portal_unterlagen.py::test_migration_traegt_anweisungen_und_checks_woertlich` -- alt: die Prüfungen aus `e5c8a1f3b9d2`; neu: je Prüfung die
  Fassung der neuesten Migration, die sie setzt (`a7c3e9f1d2b4` für `kopie_fehler`).
Gegenproben: `gegenproben-portal.md`, „1.11.33“. Beim Einspielen: Migration über `update.sh`; die Server-Schritte P2b kommen mit 1.11.34 (Ordner, `.env`,
Einheiten, nginx, Prüfskript).

### Umsetzung 1.11.34 (P2b, Teil 2): Auslieferung über nginx

- Wege des Portals (`app/portal/routen.py`, Liste SITZUNG): `POST /api/datei/anfordern` mit `{"freigabe": n}` (1 … 2147483647, sonst 422) ruft
  `portal_datei_anfordern()` -- angefordert 200 `{"stand": "angefordert"}`, Bremse 429, ohne Sitzung 401 (Cookie gelöscht), sonst 404
  `{"fehler": "nicht_gefunden"}`. `GET/HEAD /datei/{n}` (inline) und `/datei/{n}/herunterladen` (attachment) rufen nur `portal_datei()` (STABLE): ohne
  Sitzung 401 ohne Set-Cookie, ohne Anforderung derselben Sitzung in den letzten 30 Minuten 404, sonst eine leere Antwort mit `X-Accel-Redirect:
  /_portal_dateien/<Name>`, `Content-Type` (fest application/pdf bzw. image/jpeg), `Content-Disposition` und `Cache-Control: private, no-store`. Name und Typ
  aus der Datenbank prüft der Dienst vorher noch einmal (64 hex mit passender Endung), sonst 500 ohne X-Accel-Redirect.
- Name der Datei (`dateiname()`): aus dem Titel der Freigabe, nie aus dem ursprünglichen Dateinamen; Steuerzeichen, Anführungszeichen, Schrägstrich und
  Backslash fallen weg, höchstens 100 Zeichen, leer „Unterlage“; dazu eine ASCII-Fassung (Umlaute ausgeschrieben, sonst „_“) als `filename=` und die volle
  als `filename*=UTF-8''…`.
- nginx (`scripts/server/nginx-kunde.conf`): `location /_portal_dateien/` mit `internal`, `alias /srv/dk-portal/dateien/`, `types { application/pdf pdf;
  image/jpeg jpg; }`, `default_type application/octet-stream` und genau dem Satz der Schutz-Kopfzeilen des Dienstes mit `always` (CSP der Datei
  `default-src 'none'; frame-ancestors 'none'` ohne sandbox, X-Frame-Options, nosniff, Referrer, COOP, CORP, Permissions-Policy, HSTS). Aus der Antwort des
  Dienstes übernimmt nginx bei X-Accel-Redirect nur Content-Type, Content-Disposition und Cache-Control (dazu Expires, Accept-Ranges, Set-Cookie -- der Dienst
  setzt sie dort nicht); alle übrigen Kopfzeilen des Dienstes fallen weg. Das Protokoll nennt die angefragte Adresse ohne Abfrage (`map $request_uri
  $dkportal_pfad`) statt `$uri`, das nach der Umleitung der interne Weg mit dem Namen der Kopie wäre.
- Einheit `erp-portal`: `InaccessiblePaths=/srv/dk-portal` (ohne „-“: ohne den Ordner startet der Dienst nicht -- er kommt in P2b-1 vorher).
- Attrappe von nginx (`scripts/nginx_attrappe.py`, nur ERP_ENV development/test, nur 127.0.0.1): reicht jede Anfrage an den Dienst, löst X-Accel-Redirect auf
  wie nginx -- übernommen genau `UEBERNOMMEN` (wie die Tabelle der Kopfzeilen in nginx, Feld „redirect“), dazu die add_header des internal-Blocks aus der
  nginx-Datei selbst, Range und HEAD wie für eine statische Datei; `/_portal_dateien/` direkt 404.
- Beleg B6 (lokal): `scripts/klicktest_portal_dateien.py` -- anmelden wie der Kunde, der Postbote legt die Kopien an, anfordern, dann zeigt Chrome das PDF
  im eigenen Betrachter und das Foto (Inhaltstyp, kein Download, Bild), „Herunterladen“ heißt „Dachplan Süd.pdf“ und ist byte-gleich, ohne Anforderung 404,
  der interne Weg 404 (19 Prüfungen). Firefox (headless, eigenes Profil) zeigt ein PDF mit genau diesen Kopfzeilen mit pdf.js an (einmaliger Versuch im
  Scratchpad, Bild im Bericht). Safari und beide Handy-Systeme: offen (siehe Abweichungen).

#### Festlegungen 1.11.34 (bestätigt am 27.11.2026)

1. Eine Datei gibt es nur in zwei Schritten: `POST /api/datei/anfordern` (Sitzung, Bremsen, Sichtbarkeit, Protokoll), dann `GET/HEAD /datei/<n>` bzw.
   `/datei/<n>/herunterladen` (liest nur; Anforderung derselben Sitzung in den letzten 30 Minuten).
2. Fremd, zurückgenommen, ruhend, unbekannt, ohne oder mit abgelaufener Anforderung, Anforderung einer anderen Sitzung: außen dasselbe 404
   `{"fehler": "nicht_gefunden"}`.
3. Der Dienst fasst kein Byte an: leere Antwort mit X-Accel-Redirect auf `/_portal_dateien/<Name>`; Name und Typ vorher geprüft, sonst 500.
4. Vom Dienst kommen nur Content-Type (fest), Content-Disposition (inline bzw. attachment, Name aus dem Titel, ASCII und UTF-8, höchstens 100 Zeichen, nie der
   ursprüngliche Dateiname) und `Cache-Control: private, no-store`.
5. Der internal-Block setzt den vollständigen Satz der Schutz-Kopfzeilen des Dienstes selbst, mit `always`, die CSP der Datei ohne sandbox; feste Typen pdf
   und jpg, sonst application/octet-stream; ein Wächter vergleicht den Satz mit dem Dienst.
6. Das Protokoll von nginx nennt die angefragte Adresse ohne Abfrage, nie den internen Weg.
7. Die Einheit des Portals sieht den Ordner der Kopien nicht (`InaccessiblePaths=/srv/dk-portal`).
8. Die Nummer einer Freigabe ist die einzige Nummer, die ein Weg des Portals nimmt (1 … 2147483647, sonst 422).
9. Ein GET der Dateien setzt und löscht kein Cookie; `POST /api/datei/anfordern` ohne Sitzung löscht es wie jeder POST.
10. Die Attrappe von nginx läuft nur lokal und übernimmt vom Dienst genau die Kopfzeilen, die nginx übernimmt; den internal-Block liest sie aus der nginx-Datei.

#### Abweichungen vom Bauplan (P2b)

- B6 „Zu belegen in P2b, bevor die Seiten entstehen: Anzeige eines PDFs mit genau diesen Kopfzeilen in Chrome, Firefox und Safari am Rechner und auf beiden
  Handy-Systemen“ und Nachtrag 5 „Rauchtest auch auf Android mit Herunterladen und Öffnen“: belegt sind Chrome (Klicktest, ganzer Weg über die Attrappe) und
  Firefox (PDF mit denselben Kopfzeilen) -- lokal unter Windows. Safari und die Handys gehen hier nicht; auf dem Server braucht es dafür eine Freigabe (P2c)
  und eine Seite mit Link (P2e, nach Ihren Entwürfen). Vorschlag: der Rauchtest am Rechner (Safari) und auf beiden Handys vor der Inbetriebnahme, sobald P2c
  und P2e stehen (wie P2f im Bauplan).
- B2 „welche Kopfzeilen nginx bei X-Accel-Redirect aus der Antwort des Portals übernimmt, belege ich in P2b am Server“: nicht am Server (dort liegt noch keine
  Kopie, es gibt keine Freigabe) -- genommen aus dem Quelltext von nginx (Tabelle der Kopfzeilen des Upstreams, Feld „redirect“) und so in der Attrappe;
  der Nachweis mit curl kommt mit dem Rauchtest. Für die Sicherheit hängt nichts daran: die Schutz-Kopfzeilen setzt der internal-Block selbst.
- B6 nannte als Kopfzeilen nosniff, Cache-Control, CORP und die CSP; dazu kommen nach Nachtrag 3a alle übrigen des Dienstes (X-Frame-Options, Referrer,
  COOP, Permissions-Policy, HSTS).
- Die Liste der Unterlagen (`portal_unterlagen()`) hat noch keinen Weg -- sie kommt mit den Seiten (P2e); B11 nennt für P2b nur Anfordern und Datei.

#### Tests und Prüfung 1.11.34

`tests/test_v825_portal_dateien.py` (35; PostgreSQL mit Testrolle, echter uvicorn, davor die Attrappe): Dateiname, unpassende Kopie, internal-Block gegen die
Kopfzeilen des Dienstes, Protokoll, Einheit; anfordern, ansehen, herunterladen, HEAD, Range über die Attrappe; direkt beim Dienst leer mit X-Accel-Redirect und
ohne Schreiben; 404 außen gleich in sieben Fällen; 401, 429, 422; unpassender Name 500; interner Weg 404; Angriffe mit allen Methoden (h11, httptools).
`scripts/klicktest_portal_dateien.py` 19 von 19. Angepasste Erwartungen (Regel 28):
- `test_v801_portal_dienst.py::test_nginx_block` -- alt: `$uri` in der Zeile log_format; neu: `$dkportal_pfad`, kein `$uri` (die map prüft test_v825).
- `test_v802_portal_sitzung.py::test_kein_weg_nimmt_eine_id` -- alt: kein Pfad-Parameter, Körper nur bei Code und Abmelden; neu: genau `freigabe` im Pfad der
  beiden Dateiwege und im Körper von „anfordern“ (Modell `AnfordernIn` nur mit `freigabe`).
- `test_v802_portal_sitzung.py::test_jedes_ergebniswort_jeder_funktion_ist_behandelt` -- alt: die Funktionen aus funktionen.py; neu: dazu
  `portal_datei_anfordern` und `portal_datei` (Wörter aus unterlagen.py), `portal_unterlagen` noch ohne Weg.
Gegenproben: `gegenproben-portal.md`, „1.11.34“.

### Antworten des Betriebs zu den Berichten 1.11.32 bis 1.11.34 (27.11.2026)

- Bestätigt: 1.11.32-1 bis -3, 1.11.33-1 bis -13, 1.11.34-1 bis -10. Berichte und das ZIP p2b_e99c99a seit 27.11.2026 im Archiv der Berichte.
- Zählung auf dem Server nach 1.11.31: `service_reports` unterschrieben 2, davon mit gespeicherten Zeiten 0, mit fester Fassung 0; Entwurf 3. `audit_logs`:
  keine Zeile mit `field_name = 'customer_id'`. **Entscheidung:** die zwei schon unterschriebenen Berichte nicht nachträglich festschreiben, kein Skript; sie
  bleiben ohne Fassung und erscheinen nie im Portal (Vorschlag unter 1.11.29 damit erledigt).
- Rauchtest in Safari und auf beiden Handy-Systemen (B6, Nachtrag 5): einverstanden, mit P2c und P2e als Teil von P2f.
- Vor P2c als eigene kleine Version: das Kind darf 1 GiB (RLIMIT_AS), die Einheit nur 768M -- wird es eng, darf der OOM-Killer der Einheit nie den Postboten
  treffen, nur das Kind. Prüfen, ob das Kind sich selbst oom_score_adj 1000 setzt (geht ohne Rechte) und die Grenzen so liegen, dass das Kind zuerst
  scheitert; Test dazu. MemoryMax prüft der Betrieb nach der Messung auf dem Server (P2b-4). -> 1.11.35.
- Danach P2c wie im Bauplan mit den drei vorgemerkten Punkten (klare Meldung bei ruhender Freigabe eines anderen Kunden; Fotos mehrere auf einmal; vor dem
  Einladen zeigen, was der Kunde ab dann sieht); nach P2c anhalten.

### Umsetzung 1.11.35: das Kind scheitert, nie der Postbote

Befund: das Kind durfte 1 GiB (RLIMIT_AS), die Einheit `erp-portalpost` hat MemoryHigh 640M und MemoryMax 768M. Drei Folgen, wenn ein großes Bild kommt:
(1) über MemoryHigh bremst der Kernel jeden Prozess der Einheit, auch den Postboten beim Versand der Codes; (2) an MemoryMax wählt der OOM-Killer der Einheit
nach Größe -- meist das Kind, sicher ist das nicht; (3) systemd hält mit `OOMPolicy` ab Werk („stop“, `DefaultOOMPolicy`) die ganze Einheit an, sobald der
Kernel einen ihrer Prozesse beendet -- auch wenn es nur das Kind war. Der Postbote käme erst über `Restart=always` wieder, wenn überhaupt.

- Das Kind (`app/portal_foto_kind.py`) schreibt unter Linux zuerst `1000` nach `/proc/self/oom_score_adj` und liest den Wert nach (`vorrang_setzen()`):
  anheben darf jeder Prozess ohne Rechte, nur Senken braucht CAP_SYS_RESOURCE. Steht danach nicht 1000 dort, endet es mit 13, bevor es die Grenze setzt oder
  ein Byte liest; der Postbote macht daraus „abbruch“ wie aus jeder unbekannten Rückgabe. Unter Windows (Entwicklung) entfällt das -- dort begrenzt das
  Job-Objekt den einen Prozess, einen OOM-Killer gibt es nicht.
- Einheit: `OOMPolicy=continue` -- beendet der Kernel das Kind, läuft der Postbote weiter (im Journal die Meldung des Kernels, der Postbote trägt „abbruch“ ein).
- Grenze des Kinds `FOTO_SPEICHER` 448 MB = MemoryHigh 640M minus `POSTBOTE_RAUM` 192 MB (der Postbote auf dem Server rund 100 MB, S6, dazu eine PDF-Kopie bis
  25 MB zweimal im Speicher, mit Puffer). RLIMIT_AS begrenzt den ganzen Adressraum, der belegte Speicher ist nie größer -- das Kind scheitert an seiner eigenen
  Grenze (MemoryError, Rückgabe 12, „abbruch“), bevor die Einheit MemoryHigh erreicht. `tests/test_v826_portal_foto_vorrang.py` hält Grenze + Raum ≤
  MemoryHigh < MemoryMax gegen die Einheit; `kind_befehl()` ist der eine Aufruf des Kinds (Postbote und Prüfskript).
- JPEG wird nach seinem Seitenverhältnis verkleinert dekodiert (`draft` mit dem Doppelten der Zielgröße). Bis 1.11.34 fragte `thumbnail` mit dem Quadrat
  (3200 × 3200) -- ein Foto 8000 × 6000 kam so unverkleinert in den Speicher.
- Gemessen (lokal, Windows, Job-Objekt; kleinste Grenze, mit der das Kind durchkommt): JPEG 12 Mio. Bildpunkte 100 MB; JPEG 48 Mio. 280 MB, verkleinert
  dekodiert 100 MB; PNG 36 Mio. mit Alpha 340 MB; PNG 64 Mio. 360 MB, mit Alpha 580 MB; WebP 64 Mio. 1000 MB. Mit 448 MB gehen damit alle JPEG bis zur
  Pixelgrenze, PNG bis rund 36 Mio. Bildpunkte mit Alpha bzw. 64 Mio. ohne; ein PNG 64 Mio. mit Alpha und ein WebP 64 Mio. enden mit „abbruch“ (das WebP
  schon mit 1 GiB knapp). Unter Linux zählt RLIMIT_AS den ganzen Adressraum -- die Zahlen liegen dort höher; sie misst P2b-4.
- `scripts/pruefe_portal_foto.py`: unter Linux Prüfung 4 -- `/proc/<pid>/oom_score_adj` des laufenden Kinds ist 1000, bevor es ein Byte bekommt; die Zeile
  mit der Grenze; zwei Messungen (JPEG 48 Mio., PNG 36 Mio. mit Alpha) mit der Grenze des Postboten und der Spitze je Kind (`os.wait4`) -- bis 1.11.34 las
  das Skript `RUSAGE_CHILDREN`, die Spitze aller Kinder bis dahin (die Prüfung „Speicher gesprengt“ mit 150 MB lag schon darin).
- Nach P2b-4 entscheidet der Betrieb über MemoryHigh und MemoryMax; die Grenze des Kinds ändert sich in derselben Version mit (MemoryHigh minus 192 MB).

#### Festlegungen 1.11.35 (Bitte bestätigen)

1. Das Kind setzt unter Linux selbst oom_score_adj 1000 und liest den Wert nach, bevor es seine Grenze setzt oder ein Byte liest; sonst Rückgabe 13, im
   Postboten „abbruch“.
2. Einheit `erp-portalpost`: `OOMPolicy=continue` -- beendet der Kernel nur das Kind, läuft der Postbote weiter.
3. Grenze des Kinds 448 MB = MemoryHigh der Einheit minus 192 MB für den Postboten (bis 1.11.34 1 GiB, Festlegung 1.11.33-3); ein Wächter hält Grenze + Raum
   ≤ MemoryHigh < MemoryMax. MemoryHigh, MemoryMax und die Grenze des Kinds ändern sich nur zusammen.
4. Ein JPEG wird nach seinem Seitenverhältnis verkleinert dekodiert, mindestens doppelt so groß wie das Ziel.
5. Das Prüfskript des Servers misst die Spitze je Kind und prüft unter Linux den Vorrang am laufenden Kind.

#### Abweichungen vom Bauplan (1.11.35)

- Keine vom Bauplan. Geändert ist eine bestätigte Festlegung: 1.11.33-3 (1 GiB für das Kind) -> 448 MB (Festlegung 1.11.35-3), weil die Einheit nur 768M hat
  und MemoryMax erst nach der Messung auf dem Server neu bestimmt wird. Folge: PNG über rund 36 Mio. Bildpunkte mit Alpha und große WebP enden mit „abbruch“
  statt einer Kopie (gemessen oben).

#### Tests und Prüfung 1.11.35

`tests/test_v826_portal_foto_vorrang.py` (9): OOMPolicy der Einheit; Grenze + Raum ≤ MemoryHigh < MemoryMax und der Aufruf mit dieser Grenze; Vorrang
geschrieben und nachgelesen, nicht schreibbar, anderer Wert danach; ohne Vorrang unter Linux Rückgabe 13 vor Grenze, Lesen und Kodieren; mit Vorrang steht
1000, bevor die Grenze gesetzt wird; 13 -> „abbruch“; JPEG 8000 × 6000 quer und hoch mit 200 MB Grenze in Größe und Lage. Gegenproben: 9, alle rot aus dem
geprüften Grund (`docs/archiv/gegenproben-portal.md`). Angepasste Erwartung:

- `test_v824_portal_foto.py::test_pruefskript_fuer_den_server_als_kindprozess` -- alt: dreimal „ok“, „alle drei wie erwartet“; neu: dreimal „ok“ (unter Linux
  viermal), „alle Prüfungen wie erwartet“, zwei Zeilen „Messung:“ und „Grenze des Kinds 448 MB“.
- `test_v805_portal_postbote.py::test_einheit_des_postboten` -- nur der Kommentar (1 GiB stand dort); Werte unverändert.

### Umsetzung 1.11.36 (P2c, Teil 1): Freigeben und Zurücknehmen im ERP

P2c kommt in vier Versionen: 1.11.36 Freigeben und Zurücknehmen (Modul und Wege), 1.11.37 die automatischen Regeln (B4.3), 1.11.38 die Karte „Im Portal“ in
der Kundenakte und „vor dem Einladen“ (Nachtrag 6), 1.11.39 „Im Portal zeigen“ an den Dateien samt mehreren Fotos auf einmal (B9, Nachtrag 6).

- `app/portal_freigaben.py`:
  - `kette()`: je Quelle derselbe Weg wie `portal_quelle()` in SQL -- wohin die Kette heute führt (Kunde ohne die Bedingungen der Gültigkeit) und warum sie
    nicht gilt (Grund in Worten: Rechnung im Entwurf, Mahnung nicht festgeschrieben bzw. ersetzt, Bericht nicht unterschrieben bzw. ohne feste Fassung, Fassung
    überholt, Unterschrift verworfen, Mangel bzw. Abnahme verworfen, Projekt Mustervorgang bzw. im Archiv, Eingang der Webseite im Archiv). Dazu Art, Vorschlag
    für den Titel, Datum, Auftrag, Objekt, gespeicherter Typ und Größe. Unter SQLite gibt es `portal_quelle()` nicht; das ERP braucht die Gründe für die Karte.
    Eine Änderung an einer Kette gehört in beide -- `tests/test_v827_portal_freigaben_kette.py` vergleicht in jeder der 145 Zellen der Matrix aus 1.11.32
    (gleiche Zustandswechsel) Python mit `portal_quelle()` und „sichtbar“ mit `portal_sichtbar()`.
  - `freigeben()`: eine oder mehrere Unterlagen einer Quelle (bis 200) für den Kunden aus dem Pfad -- alles oder nichts; schon für ihn freigegebene zählen als
    „schon“, ist keine neu, 409. Je Unterlage: führt die Kette heute nicht zu ihm (unbekannt oder ein anderer Kunde), 404 „Unterlage nicht gefunden.“ (Regel 25,
    außen gleich); gilt sie nicht, 409 mit Grund; ein gespeicherter Typ außer PDF, JPEG, PNG, WebP, GIF oder mehr als 25 MB, 409 (ohne gespeicherten Typ
    entscheidet der Postbote am Inhalt). Steht die Quelle noch bei einem anderen Kunden (dort ruht sie): 409 „Diese Unterlage ist noch bei Kunde <Nummer>
    (<Name>) freigegeben (dort ruht sie) – erst beim bisherigen Kunden zurücknehmen.“ -- auch, wenn zwei zugleich freigeben (der Index „höchstens eine je
    Quelle“ greift, die Meldung wird nachgeschlagen, nie 500). Titel: von Hand (1–120 Zeichen) oder je Unterlage der Vorschlag -- Kategorie bzw. Art und
    Datum, nie der Dateiname.
  - `zuruecknehmen()`: mit optionalem Grund, sofort unsichtbar (die Funktionen prüfen `zurueckgenommen_am`), die Kopie entfernt der Postbote (Auslöser);
    die Zeile bleibt. Zweimal 409; eine Freigabe eines anderen Kunden als im Pfad 404.
  - `erneut()`: nur eine gescheiterte Kopie einer nicht zurückgenommenen Freigabe -- `kopie_fehler` leer und ein Weckruf an den Postboten (`pg_notify`; der
    Auslöser greift dort nicht).
  - `zustand()`: zurückgenommen (Grund), ruht (die Unterlage gibt es nicht mehr / gehört heute zu einem anderen Kunden / Grund der Kette), gescheitert (Grund in
    Worten), wird vorbereitet, sichtbar -- in derselben Reihenfolge, in der die Funktionen der Datenbank prüfen. `stand()` für die Karte, `unterlagen()` für
    „Im Portal zeigen“ (liest nur).
- Router `app/routers/portal_freigaben.py`, ab Büro – Auftrag, Modul aus 403:
  `GET/POST /api/customers/{id}/portal/freigaben`, `POST …/freigaben/{freigabe_id}/zuruecknehmen` (auch im Archiv, `OHNE_VORAB`), `POST …/erneut`
  (`archiv_vorab`), `GET /api/portal-freigaben/unterlagen?quelle=…&quelle_ids=…` (bis 500). Freigeben geht auch, solange das Portal des Kunden aus ist (B4.2;
  der Stand nennt `portal_aktiv`).
- Änderungshistorie: „Freigabe im Kundenportal“ (`PortalFreigabe` in `app/audit.py`), ohne die Felder der Kopie (`STILL_JE_ART`) -- ihr Name steht nie dort.
- Bekannte Grenze: `stand()` liest je Freigabe ihre Kette einzeln (einige Abfragen je Zeile). Für einen Kunden mit wenigen Dutzend Freigaben unauffällig; bei
  Hunderten je Kunde gehört es gebündelt.

#### Festlegungen 1.11.36 (Bitte bestätigen)

1. Freigeben, Zurücknehmen und „erneut versuchen“ ab Büro – Auftrag (P2-6), die Monteurin nie; Modul aus: 403.
2. Freigegeben wird nur, was heute zum Kunden im Pfad führt -- unbekannt und fremd sind außen dasselbe 404; eine eigene, die nicht gilt, 409 mit Grund.
3. Nur PDF und Rasterbilder (gespeicherter Typ; ohne Typ entscheidet der Postbote am Inhalt), bis 25 MB.
4. Titel vorbelegt mit Kategorie bzw. Art und Datum, nie der Dateiname; von Hand 1–120 Zeichen; bei mehreren einer für alle oder je der Vorschlag.
5. Mehrere auf einmal (bis 200): alles oder nichts; schon freigegebene desselben Kunden zählen als „schon“; ist keine neu, 409.
6. Steht die Unterlage noch bei einem anderen Kunden, nennt die Meldung ihn (Nummer und Name) -- erst dort zurücknehmen; auch bei gleichzeitigem Freigeben nie 500.
7. Zurücknehmen mit optionalem Grund, sofort unsichtbar, auch im Archiv; die Zeile bleibt.
8. „Erneut versuchen“ nur für eine gescheiterte Kopie einer nicht zurückgenommenen Freigabe; es weckt den Postboten.
9. Zustände im ERP: sichtbar, wird vorbereitet, gescheitert (Grund in Worten), ruht (Grund), zurückgenommen.
10. Die Kette steht im ERP ein zweites Mal in Python; ein Wächter verlangt in jeder Zelle der Matrix dasselbe wie `portal_quelle()`.
11. Jede Quelle lässt sich auch von Hand freigeben, auch die der automatischen Arten (für die Vorschläge, B4.3) -- dieselben Prüfungen.
12. Änderungshistorie „Freigabe im Kundenportal“ ohne die Felder der Kopie.

#### Abweichungen vom Bauplan (1.11.36)

- B11 nennt für P2c ein Modul mit „freigeben, zurücknehmen, automatische Regeln, Gründe des Ruhens“ in einem Schritt -- hier in vier Versionen (oben); die
  Regeln folgen in 1.11.37.
- Neu gegenüber dem Bauplan: „erneut versuchen“ an einer gescheiterten Kopie (Festlegung 1.11.33-5 hatte es P2c zugewiesen, B9 nennt es nicht) und die Kette
  ein zweites Mal in Python (B4.4 sagt „im ERP mit Grund angezeigt“, ohne zu sagen, woher der Grund kommt).
- B4.3 trennt „automatisch“ und „einzeln“ je Art; von Hand freigeben lässt sich hier jede Quelle (Festlegung 11) -- sonst ginge ein Vorschlag (Angebot an eine
  andere Adresse) nicht.

#### Tests und Prüfung 1.11.36

`tests/test_v827_portal_freigaben_kette.py` (147, PostgreSQL mit der Welt der Matrix: je Zelle Python gleich SQL und „sichtbar“ gleich `portal_sichtbar()`,
jede ruhende Freigabe mit Grund; jede Quelle hat ihren Zweig; „erneut“ weckt den Postboten, gezählt nur Weckrufe dieser Verbindung),
`tests/test_v828_portal_freigaben.py` (21, über den Router: einzeln mit Vorschlag und Historie, Titel von Hand, mehrere Fotos, alles oder nichts, fremd wie
unbekannt, Grund, Typ und Größe, noch bei einem anderen Kunden samt gleichzeitigem Freigeben, Zurücknehmen, nur beim eigenen Kunden, Archiv, erneut,
sichtbar und ruht, Dialog-Abfrage, Rollen, Modul aus). Gegenproben: 17, alle rot aus dem geprüften Grund (`docs/archiv/gegenproben-portal.md`). Eingeordnet:

- `tests/test_v373_zugehoerigkeit_struktur.py::GEPRUEFT` -- `quelle_ids` beim Freigeben (`portal_freigaben.pruefen`, `k.kunde != kunde_id`), `freigabe_id`
  beim Zurücknehmen und bei „erneut“ (`portal_freigaben._freigabe_des_kunden`, `f.customer_id != kunde_id`).
- `tests/test_v793_archivschutz.py::OHNE_VORAB` -- Zurücknehmen (geht auch im Archiv, wie Sperren).
- `tests/test_v326_monteur_datengrenze.py::QUERY_JE_ROUTE` -- Werte für `/api/portal-freigaben/unterlagen` (der Monteur bekommt 403).
- Erster voller Lauf rot (2): `test_v436::test_jedes_protokollierte_feld_hat_einen_namen` und `test_v438::test_namen_der_historie_sind_lesbar` -- die 18 Felder einer Freigabe hatten in der Änderungshistorie keinen lesbaren Namen (auch die stillen der Kopie brauchen einen). Nachgetragen in `app/audit.py::FIELD_LABELS`, danach grün.

### Umsetzung 1.11.37 (P2c, Teil 2): die automatischen Regeln

- `app/portal_freigaben.py::kandidaten()` (liest nur) -- je Regel, was für diesen Kunden heute freigegeben wäre (`REGELN`, gespeichert in
  `portal_freigaben.regel`):
  - **rechnung**: `Invoice.customer_id` = Kunde, nicht Entwurf (auch Storno, Schlussrechnung), mindestens einmal angekommen
    (`app/email_dispatch.py::document_reached_on()`, Versand oder nachgetragene Zustellung).
  - **mahnung**: festgeschrieben (`versendet`), nicht ersetzt, hinausgegangen (`app/reminders.py::reached_map()`).
  - **angebot**, **auftrag**, **vertrag**: je Dokument die Fassung des jüngsten gesendeten Versands (nicht unzustellbar). Ging er per Mail und steht die
    Adresse des Kunden unter An (ohne Groß- und Kleinschreibung), bzw. wurde er nachgetragen an den Auftraggeber zugestellt: Kandidat; sonst ein Vorschlag
    (P2-4) -- nur von Hand freizugeben, gezeigt in der Karte (`vorschlaege()`, im Stand unter `vorschlaege`). Der Vertrag: jede Fassung und die
    unterschriebene Abschrift liegen als Art „vertrag“ in der Ablage; es gilt die zuletzt versendete.
  - **abnahmeprotokoll**: je Abnahmeprotokoll die Fassung aus `app/protocol_dispatch.py::protocol_version()` -- die jüngste gültige mit der gültigen
    Unterschrift des Auftraggebers.
  - **einsatzbericht**: unterschrieben mit fester Fassung (Rapport wie Wartung, P2-5).
  - **brief**: der Brief, dessen Fassung beim Auftraggeber ankam (`app/notice_letters.py::delivered_dispatches()`).
  - Jeder Kandidat führt über seine Kette heute zu genau diesem Kunden und gilt (`kette()`); die Abfragen filtern vorab, die Kette entscheidet.
- `regeln_anwenden()` (ein Commit): fehlende Zeilen anlegen (`freigegeben_von_name` „automatisch“, ohne Konto); ausgelassen, wenn eine Zeile der Quelle
  aktiv ist (hier oder ruhend bei einem anderen Kunden -- kein stilles Umhängen, B4.4) oder eine Person sie zurückgenommen hat (B4.2). Eine ältere Fassung
  derselben Gruppe (Angebot, Auftragsbestätigung, Vertrag je Dokument; Abnahmeprotokoll je Checkliste) nimmt das System zurück („neuere Fassung versendet“,
  von „System“) -- wird sie wieder die jüngste (die neuere Unterschrift verworfen), legt die Regel sie neu an. Ein gleichzeitiges Freigeben von Hand
  überspringt die eine Zeile (SAVEPOINT), nicht den Rest.
- Wann: beim Einschalten des Portals am Kunden (`app/kundenportal.py::schalten()`, auch für alles vor der Einladung, P2-3 -- so zeigt die Karte vor dem
  Einladen, was der Kunde sieht) und im vollen Lauf des Postboten (`app/portal_postbote.py::regeln()`, beim Start und alle 15 Minuten, vor den Kopien) für
  jeden Kunden mit Portal an, nicht im Archiv, nur mit eingeschaltetem Modul (`regeln_alle()`). Neue Zeilen wecken über den Auslöser die Kopien. Ein Fehler in
  den Regeln beendet den Postboten nicht (nur die Klasse ins Protokoll, nächster Versuch im nächsten vollen Lauf). Portal aus nimmt nichts zurück -- ohne
  Sitzung sieht der Kunde ohnehin nichts.
- Bekannt (Nebenbefund N2, Entscheidung P2-19 „erst nach P2“): bei Rechnung und Mahnung zählt jede gesendete Mail als angekommen, auch an eine andere
  Adresse -- dieselbe Lesart wie die Mahnstufen. Die Rechnung gehört dem Kunden ohnehin (`Invoice.customer_id`); bei Angebot, Auftragsbestätigung und
  Vertrag prüft die Regel die Adresse (P2-4).
- Gegenprobe „nicht im Archiv“: ohne den Filter bricht der Archivschutz das Anlegen für einen archivierten Kunden ab (ImArchiv) -- im Postboten hielte ein
  einziger archivierter Kunde mit Portal an die Regeln aller übrigen an. Der Filter bleibt deshalb nötig, auch wenn das Archiv selbst nichts anlegen ließe.

#### Festlegungen 1.11.37 (Bitte bestätigen)

1. Automatisch freigegeben nach B4.3: Rechnung (angekommen), Mahnung (hinausgegangen, nicht ersetzt), je Angebot, Auftragsbestätigung und Vertrag die
   zuletzt versendete Fassung an die Adresse des Kunden, die jüngste gültige Fassung des Abnahmeprotokolls mit der Unterschrift des Auftraggebers,
   unterschriebene Einsatzberichte mit fester Fassung, angekommene Briefe der Anzeigen -- jeweils nur, wenn die Kette heute zum Kunden führt und gilt.
2. „An die Adresse des Kunden“ = per Mail mit seiner heutigen E-Mail-Adresse unter An, oder nachgetragen an den Auftraggeber zugestellt; sonst nur Vorschlag.
3. Die Regeln laufen beim Einschalten des Portals am Kunden und alle 15 Minuten im Postboten -- nur für Kunden mit Portal an, nicht im Archiv, mit Modul.
4. Eine ältere Fassung nimmt das System als überholt zurück („neuere Fassung versendet“); wird sie wieder die jüngste, legt die Regel sie neu an.
5. Was eine Person zurückgenommen hat, legt keine Regel wieder an (von Hand freigeben geht weiter).
6. Kein stilles Umhängen: ist eine Unterlage noch bei einem anderen Kunden freigegeben, legt die Regel nichts an.
7. Zeilen einer Regel: von „automatisch“, ohne Konto; Portal aus nimmt nichts zurück.
8. Ein Fehler in den Regeln hält den Postboten nicht an (Klasse ins Protokoll).

#### Abweichungen vom Bauplan (1.11.37)

- B4.3 nennt „Termine automatisch (feste Einsatztage)“ -- die kommen mit dem Schaufenster in P2d, nicht hier.
- B4.3 Vertrag „die festgeschriebene Fassung, nach der Unterschrift die unterschriebene Abschrift -- je nach Versand wie Angebot“: umgesetzt als „die zuletzt
  versendete“ (Fassung und Abschrift sind dieselbe Art in der Ablage); eine nie versendete Abschrift erscheint nicht.
- B4.3 Abnahmeprotokoll „An war fest der Auftraggeber“: die Regel verlangt keinen Versand, nur die gültige Unterschrift des Auftraggebers in der Fassung
  (er hat sie unterschrieben).
- Neu: „überholt“ durch das System (B4.3 sagt „je Angebot die zuletzt versendete Fassung“, nicht, was mit der älteren geschieht).

#### Tests und Prüfung 1.11.37

`tests/test_v829_portal_regeln.py` (16, SQLite über den Router; einer gegen PostgreSQL mit dem echten Postboten): je Regel, ungültige Kette, Vorschläge,
überholt und wieder da, von einer Person zurückgenommen, kein stilles Umhängen, zweimal angewandt, Portal an, nur Portal an/Archiv/Modul, Name der Regel
passt in die Spalte, Fehler hält den Postboten nicht an. Gegenproben: 17, alle rot aus dem geprüften Grund (zwei über Abfrage und Kette zugleich -- die Kette
allein trägt; `docs/archiv/gegenproben-portal.md`). Angepasst: keine Erwartung; `test_v809` (Karte Kundenportal) unverändert grün -- Portal an wendet jetzt die
Regeln an, dort ohne Unterlagen.

### Umsetzung 1.11.38 (P2c, Teil 3): Reiter „Im Portal“ und „vor dem Einladen“

- Server (`app/portal_freigaben.py::stand()`): je Eintrag `gruppe` -- „Auftrag <Nummer> · <Adresse>“, „Auftrag …“, „Objekt …“ oder „Ohne Auftrag und Objekt“
  (`gruppe_text()`, P2-10, nie der Projekttitel); dazu `zahlen` je Art (was der Kunde sieht oder gleich sieht: sichtbar, wird vorbereitet -- nicht
  gescheitert, ruhend, zurückgenommen), `zahlen_text` („2 Rechnungen · 3 Fotos · 1 Dokument“, Einzahl und Mehrzahl aus `ART_TEXT`/`ART_MEHRZAHL`) und
  `anzahl_sichtbar` (Zahl am Reiter).
- Kundenakte (`customer.html`), nur mit Modul (sonst fehlen Reiter, Abschnitt und Dialoge, die Seite fragt nicht): Reiter „Im Portal“ (Anker `#importal`) --
  Hinweis bei Portal aus bzw. Kunde im Archiv, „Der Kunde sieht: …“, Gruppen in der Reihenfolge der jüngsten Freigabe, je Zeile Titel, Art, Datum,
  automatisch bzw. von wem, seit wann, Grund; Kennzeichen sichtbar (grün), wird vorbereitet (blau), Kopie gescheitert (Warnfarbe, „Erneut versuchen“);
  „Vorschläge“ mit „Im Portal zeigen“; „Ruht“ mit Grund; „Zurückgenommen“ eingeklappt mit Zahl, je Zeile wann, von wem, Grund. Zurücknehmen über einen Dialog
  mit freiwilligem Grund (kein prompt(), Regel 4), auch im Archiv (`data-lesen`); im Archiv sonst kein Knopf. Texte nur über `textContent`, die Knöpfe tragen
  nur Nummern. Die Reiterliste der Seite entsteht aus den vorhandenen Abschnitten.
- Vor dem Einladen (Nachtrag 6): in der Karte „Kundenportal“ in den Zuständen aus, kein Zugang, ohne Link und Versand gescheitert der Satz „Ab dem Einladen
  sieht der Kunde: …“ mit „Im Portal ansehen“ (öffnet den Reiter); derselbe Satz im Dialog „Link senden“. „Portal einschalten“ lädt danach auch die Freigaben
  (die Regeln legen beim Einschalten an, 1.11.37) -- der Satz zählt dann die automatischen mit.
- Baustein `_im_portal.html` „Im Portal zeigen“: Dialog mit Titel (bei einer Unterlage Pflicht, vorbelegt; bei mehreren leer = je Unterlage der Vorschlag),
  Hinweis zu hochgeladenen PDFs (B6), Hinweis „Portal aus“, Vorschau von Bildern (höchstens 6, `sichereBildquelle()`); Freigeben abschließend
  (`abschliessen()`, `ABSCHLIESSEND` in `tests/test_v399_abschliessen.py`), Meldung des Servers im Dialog. Hier nur für die Vorschläge, in 1.11.39 an den Dateien.

#### Festlegungen 1.11.38 (Bitte bestätigen)

1. Reiter „Im Portal“ in der Kundenakte nur mit Modul; die Zahl am Reiter ist, was der Kunde sieht oder gleich sieht.
2. „Der Kunde sieht“ zählt sichtbar und „wird vorbereitet“, nicht gescheitert, ruhend oder zurückgenommen; je Art mit Einzahl und Mehrzahl.
3. Gruppen wie im Portal: Auftragsnummer und Adresse des Objekts, nie der Projekttitel; ohne beides „Ohne Auftrag und Objekt“.
4. Darunter „Vorschläge“ (nur von Hand), „Ruht“ (mit Grund) und eingeklappt „Zurückgenommen“.
5. Zurücknehmen über einen Dialog mit freiwilligem Grund, auch im Archiv; im Archiv sonst kein Knopf.
6. Vor dem Einladen (aus, kein Zugang, ohne Link, Versand gescheitert) nennt die Karte „Kundenportal“, was der Kunde ab dann sieht, mit Link zum Reiter;
   derselbe Satz im Dialog „Link senden“.
7. Freigeben über einen gemeinsamen Dialog „Im Portal zeigen“; abschließend; bei einer Unterlage ist der Titel Pflicht.

#### Abweichungen vom Bauplan (1.11.38)

- B9 nennt „Karte bzw. Reiter“ -- ein Reiter (die Liste wird lang, die Übersicht ist schon voll); in der Übersicht steht nur der Satz „vor dem Einladen“.
- B9 Zustände „Kopie wird erstellt“ und „Büro – Auftrag (alles)“: als „Wird vorbereitet“ bzw. ohne eigene Darstellung (Büro – Auftrag sieht und darf alles,
  wie jede Büro-Rolle).
- Nachtrag 6 „Vor dem Einladen“: auch im Zustand „aus“ (da zählt nur das von Hand Freigegebene, die Regeln laufen erst mit dem Einschalten).

#### Tests und Prüfung 1.11.38

`tests/test_v830_im_portal_karte.py` (5: Zahlen nur, was der Kunde sieht; leer; ruhend zählt nicht; Ein- und Mehrzahl je Art; Gruppe wie im Portal),
Klicktest `scripts/klicktest_kundenportal_im_portal.py` (40: vor dem Einladen mit Portal aus und an, im Dialog „Link senden“, Link zum Reiter; Zahl am Reiter,
Gruppen, Kennzeichen, Grund, Ruht, Zurückgenommen, Vorschlag mit Titelpflicht und Freigeben, Zurücknehmen mit Grund, Erneut versuchen, dunkel, 412 px, Archiv nur
„Zurücknehmen“, Monteurin 403, Modul aus ohne Reiter und ohne Anfrage). Gegenproben: 8, alle rot aus dem geprüften Grund. Eingeordnet bzw. angepasst:

- `tests/test_v554_kundenakte_funktionen.py` -- drei Funktionen „Im Portal“ in `FUNKTIONEN`; `REITER` alt ohne, neu mit „importal“.
- `tests/test_v795_nur_lesen.py::LESEN` (customer.html) -- dazu „portalSiehtLink“ und „ip-zuruecknehmen“.
- `tests/test_v399_abschliessen.py::ABSCHLIESSEND` -- dazu `_im_portal.html`, `imPortalFreigeben`.
- Ein erster Seitentest in `test_v830` (Reiter nur mit Modul über `router_test_client`) war falsch gebaut -- ohne Anmeldeschranke liest der Modulschalter der
  Vorlage nicht die Testdatenbank; geprüft wird das jetzt im Klicktest.

### Umsetzung 1.11.39 (P2c, Teil 4): „Im Portal zeigen“ an den Dateien

- Baustein `_im_portal.html` erweitert: Dialog und Knöpfe nur mit Modul und ab Büro – Auftrag (`im_portal_darf` über `can()`; ungerendert ist
  `IM_PORTAL_DARF` aus). Die Seite setzt je Datei einen leeren Platz `<span data-ip-quelle="…" data-ip-id="…" data-ip-was="…" data-ip-vorschau="…">` und ruft
  danach `imPortalAnDateien(behälter, nachher)`: je Quelle eine Abfrage (`GET /api/portal-freigaben/unterlagen`), in den Platz das Kennzeichen einer
  bestehenden Freigabe („Im Portal“, „· wird vorbereitet“, „· Kopie gescheitert“, „· ruht“, „Im Portal eines anderen Kunden“; der Grund als title) und, wenn
  freigebbar, „Im Portal zeigen“. Der Dialog: Titel vorbelegt (Kategorie bzw. Art und Datum), Vorschau bei Bildern, Hinweis zu PDFs nur bei hochgeladenen
  (Kundenakte, Projekt, Objekt, Mangel, Abnahme), Kunde aus der Kette (der Server prüft ihn ohnehin). Eigene Stile im Dialog (er steht auch auf Seiten, die
  nur ihre eigenen Klassen gestalten).
- Seiten: Kundenakte (Dokumente: `customer_documents`; danach auch der Reiter „Im Portal“ neu), Akte (Dateien: `project_documents`; Abnahme:
  `order_acceptance_files`; Mängel: `defect_files`), Objekt (`property_documents`, die Dateien seiner Projekte als `project_documents`). An Belegen der Abnahme und
  Dateien am Mangel nur, solange die Datei unverändert ist (Prüfsumme) -- sonst entstünde nur eine gescheiterte Kopie („fehlt“, „pruefsumme“).
- Einsatzbericht: in der Zusammenfassung (Schritt „Unterschrift“) fürs Büro „Fotos im Portal zeigen …“ -- `imPortalFotos()`: Auswahl aller Fotos des Berichts
  mit Vorschau, nichts vorgewählt (Nachtrag 6), schon freigegebene ausgegraut mit ihrem Stand, ohne Kreuz eine Meldung, der Knopf nennt die Zahl
  („2 im Portal zeigen“); Titel leer = je Foto „Foto vom <Tag>“. Ein Klick legt alle gewählten zusammen an (alles oder nichts, 1.11.36).
- Nicht gebaut: an der Checkliste des Abnahmeprotokolls (die Mängel dort zeigt die Akte) und an Fotos einzelner Prüfpunkte im Bericht (die Auswahl deckt alle
  Fotos des Berichts ab).

#### Festlegungen 1.11.39 (Bitte bestätigen)

1. „Im Portal zeigen“ und das Kennzeichen stehen an jeder freigebbaren Datei der Kundenakte, der Akte (Dateien, Abnahme, Mängel) und des Objekts -- nur mit
   Modul und ab Büro – Auftrag.
2. Ein Knopf nur, wenn die Datei freigebbar ist; Belege der Abnahme und Dateien am Mangel nur, solange sie unverändert sind.
3. Fotos des Einsatzberichts mehrere auf einmal über eine Auswahl mit Vorschau, nichts vorgewählt; schon freigegebene nicht noch einmal.
4. Der Hinweis zu PDFs nur bei hochgeladenen PDFs, eine Vorschau nur bei Bildern.
5. Die Monteurin sieht weder Knopf noch Dialog (auch nicht im Einsatzbericht).

#### Abweichungen vom Bauplan (1.11.39)

- B9 nennt „Fotos im Einsatzbericht und am Mangel“ einzeln an der Datei: im Einsatzbericht stattdessen eine Auswahl aller Fotos des Berichts in der
  Zusammenfassung (Nachtrag 6: mehrere auf einmal) -- ein Knopf an jedem Foto der Schritte stünde mitten im Ablauf der Monteurin.
- B9 „danach Kennzeichen „im Portal“ an der Datei“: dazu „wird vorbereitet“, „Kopie gescheitert“, „ruht“ und „Im Portal eines anderen Kunden“ (aus dem Stand
  der Freigabe).
- Nicht an der Checkliste des Abnahmeprotokolls (siehe oben).

#### Tests und Prüfung 1.11.39

`tests/test_v831_im_portal_an_dateien.py` (6: jede Quelle eines Platzes bekannt; die Seiten mit Dateien haben genau ihre Quellen und rufen den Baustein; der
Bericht öffnet die Auswahl nur fürs Büro; jede Seite bindet den Baustein ein; der Dialog nur mit Modul und Büro-Rolle; Belege nur unverändert), Klicktest
`scripts/klicktest_kundenportal_an_dateien.py` (30: PDF mit Hinweis, Bild mit Vorschau, ZIP ohne Knopf, Freigeben mit Kennzeichen und Zahl am Reiter, Titel nie
der Dateiname; Akte Dateien; Beleg der Abnahme mit Datei mit, ohne Datei ohne Knopf; Objekt mit der Datei des Projekts schon im Portal; Auswahl der Fotos im
Bericht; Monteurin ohne Knopf und Dialog). Gegenproben: 7, alle rot aus dem geprüften Grund. Angepasst: keine Erwartung. Ein Fund während des Baus: im
Einsatzbericht waren Knöpfe und Feld des Dialogs ungestaltet -- seitdem eigene Stile im Dialog.

### Abschluss P2c (1.11.36–1.11.39)

P2c ist mit 1.11.39 gebaut: Freigeben und Zurücknehmen samt Gründen (1.11.36), automatische Regeln (1.11.37), Reiter „Im Portal“ und „vor dem Einladen“
(1.11.38), „Im Portal zeigen“ an den Dateien (1.11.39) -- mit den drei vorgemerkten Punkten (klare Meldung bei einer ruhenden Freigabe eines anderen Kunden,
1.11.36; mehrere Fotos auf einmal, 1.11.39; zeigen, was der Kunde ab dem Einladen sieht, 1.11.38). Nach P2c angehalten (Vorgabe 27.11.2026). Der Kunde sieht
davon im Portal noch nichts: die Seiten des Portals kommen nach den Entwürfen des Betriebs (P2e), das Schaufenster mit Zahlstand und Terminen in P2d.

### Antworten des Betriebs zu den Berichten 1.11.35 bis 1.11.39 (27.11.2026)

- Bestätigt: 1.11.35-1 bis -5 (auch die Änderung von 1.11.33-3), 1.11.36-1 bis -12, 1.11.37-1 bis -8, 1.11.38-1 bis -7, 1.11.39-1 bis -5. Berichte und das ZIP
  p2c_592022b seit 27.11.2026 im Archiv der Berichte.
- Server, 27.11.2026 auf e99c99a: P2b-0 bis P2b-6 eingespielt, alles wie erwartet. P2b-4: 48 Mio. Bildpunkte, 33 MB -> JPEG 410 KB, 0,6 s, Spitze des Kinds
  323 MB (noch mit der Grenze 1 GiB, vor 1.11.35). nginx: `/_portal_dateien/.datenbank` 404, `/datei/1` 401, `/health` 200, POST 401, Protokoll ohne IP und
  internen Weg. Danach: update.sh auf 592022b, die Einheit des Postboten neu und P2b-4 noch einmal; MemoryHigh/MemoryMax gibt der Betrieb danach vor.
- Kleinigkeiten (Kleines gleich beheben, im nächsten Bericht beantworten): 1. portal_rechte meldet seit 1.11.33 46 statt 45 Anweisungen; 2. `nginx -t`
  warnt „listen … http2 is deprecated“ (Zeile 36) -- auf „http2 on;“, Wächter anpassen; 3. die 404 von außen auf `/_portal_dateien/…` hat rund 15 KB -- welche
  Seite; 4. Fotodialog: die Meldung steht trotz zwei Kreuzen da; Vorschauen im Bild kaputt -- im Klicktest mit echten Testbildern belegen; 5. Objektseite: an
  Dateien eines Projekts eines anderen Kunden auf diesem Objekt (U2/U3) kein „Im Portal zeigen“, Test mit Gegenprobe. -> 1.11.40.
- P2e: die Entwürfe sind freigegeben (5 PNG in `bildgrundlage/Entwürfe/P2/`). **Änderung zu P2-10:** Gruppenüberschrift „Auftrag <Nummer> · <Betreff>“,
  darunter die Adresse. Betreff ist nur der Text, den der Kunde schon gedruckt auf Angebot bzw. Auftragsbestätigung hat -- nie der interne Projekttitel. Befund
  dazu im Bericht zu P2d (welches Feld, verlässlich gefüllt?), Umsetzung mit P2e; ohne Betreff nur die Nummer. Gilt auch für den Reiter „Im Portal“.
- Weiter mit P2d, dann P2e nach den Entwürfen; nach P2e anhalten.

### Umsetzung 1.11.40: Kleinigkeiten nach P2c

- Zu 1 (Antwort): seit 1.11.33 gibt es im Schema die Funktion des Weckrufs `portal_freigabe_geweckt()` (Migration a7c3e9f1d2b4). `scripts/portal_rechte.py
  --setzen` nimmt jeder eigenen Funktion des Schemas das Recht für alle (`app/portal/rechte.py::setzen()`, eine Zeile `REVOKE ALL ON FUNCTION … FROM PUBLIC` je
  Funktion aus `_eigene_funktionen()`) -- die 46. Anweisung ist `REVOKE ALL ON FUNCTION public.portal_freigabe_geweckt() FROM PUBLIC`. Der Benutzer des Portals
  bekommt auf sie kein Recht (sie ist keine aus `FUNKTIONEN`). Mit P2d kommen weitere Auslöser-Funktionen dazu; die Zahl steigt dann wieder.
- Zu 2: `listen 443 ssl;` und `http2 on;` (nginx ab 1.25.1; der Server hat 1.28.3). `tests/test_v815_nginx_nur_ipv4.py`: alt `listen 443 ssl http2;`, neu
  `listen 443 ssl;` und im zweiten Block genau `http2 on;`, keine Zeile `listen … http2`. Hinweis: lauschen andere Blöcke des Servers auf 443 noch mit
  „listen … http2“, kann `nginx -t` „protocol options redefined“ melden -- nur eine Warnung.
- Zu 3 (Antwort, hier nicht nachstellbar -- kein nginx lokal): eine Anfrage, die der internal-Block abweist, beantwortet nginx mit seiner eingebauten Seite (rund
  150 Byte; die Konfiguration hat für 404 keine eigene Seite, `error_page` nur für 502/504). Rund 15 KB passen dagegen zur Seite des Portals (`portal.html`,
  13,5 KB, die der Dienst für unbekannte Pfade mit 404 liefert) -- dann kam die Anfrage beim Dienst an. Das geschieht für jeden Pfad, der nicht mit
  `/_portal_dateien/` (mit Schrägstrich) beginnt, z. B. `/_portal_dateien` ohne ihn (`location /`). Klären mit den Befehlen im Server-Schritt N1 unten.
- Zu 4: die Meldung „Bitte mindestens ein Foto ankreuzen.“ geht mit dem ersten Kreuz (`imPortalKnopfText()`); der Klicktest legt echte Testbilder an (Fotos des
  Berichts und Bild der Kundenakte) und prüft, dass jede Vorschau lädt (`complete` und `naturalWidth > 0`) -- im Bild von 1.11.39 fehlten die Dateien der
  Testdaten, die Seite selbst war richtig.
- Zu 5: ein Platz kann den Kunden der Seite nennen (`data-ip-kunde`); führt die Unterlage zu einem anderen Kunden, gibt es keinen Knopf (Kennzeichen einer
  bestehenden Freigabe: „Im Portal eines anderen Kunden“). Die Objektseite nennt den Kunden des Objekts -- die Datei eines Projekts eines anderen Kunden auf
  diesem Objekt (Bauplan A2.2, U2/U3) gibt man in dessen Akte frei. Der Server hätte sie ohnehin nur für den Kunden ihrer Kette freigegeben (1.11.36).

#### Festlegungen 1.11.40 (Bitte bestätigen)

1. Der Block des Portals schaltet HTTP/2 mit `http2 on;` ein, kein „listen … http2“ (Wächter).
2. Die Meldung „Bitte mindestens ein Foto ankreuzen.“ steht nur, solange keins angekreuzt ist.
3. Auf der Objektseite keinen Knopf „Im Portal zeigen“ an der Datei eines Projekts eines anderen Kunden; ein Platz kann dafür den Kunden der Seite nennen.

#### Abweichungen vom Bauplan (1.11.40)

- Keine.

#### Tests und Prüfung 1.11.40

`tests/test_v815_nginx_nur_ipv4.py` angepasst (alt: `listen 443 ssl http2;`; neu: `listen 443 ssl;` und `http2 on;`, keine Zeile `listen … http2`). Klicktest
`klicktest_kundenportal_an_dateien.py` 34 (vorher 30): die Vorschau des Bilds lädt, jede Vorschau im Fotodialog lädt, die Meldung geht mit dem ersten Kreuz,
Datei des Projekts eines anderen Kunden am Objekt ohne Knopf. Gegenproben: 4, alle rot aus dem geprüften Grund.

#### Server-Schritt N1 (nach dem Einspielen von 1.11.40): nginx mit `http2 on;`, dazu die 404 klären

```bash
sudo cp /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf /root/kunde.dachkonzepte.gmbh.conf.vor-1.11.40
sudo install -m 644 -o root -g root /home/tobias/erp/scripts/server/nginx-kunde.conf /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf
sudo nginx -t && sudo systemctl reload nginx
curl -s -o /dev/null -w '%{http_version} %{http_code}\n' https://kunde.dachkonzepte.gmbh/health
for p in /_portal_dateien/x.pdf /_portal_dateien; do printf '%s ' "$p"; curl -s -o /dev/null -w '%{http_code} %{size_download}\n' "https://kunde.dachkonzepte.gmbh$p"; done
curl -sI https://kunde.dachkonzepte.gmbh/_portal_dateien/x.pdf | grep -i -E '^content-(type|length|security-policy)'
```

Erwartet: `nginx -t` ohne die Warnung zu „listen … http2“ in dieser Datei („protocol options redefined“ von anderen Blöcken ist nur eine Warnung); `2 200`;
`/_portal_dateien/x.pdf 404` mit rund 150 Byte und CSP `default-src 'none'; frame-ancestors 'none'` (die Seite von nginx aus dem internal-Block);
`/_portal_dateien 404` mit rund 13–15 KB (die Seite des Portals). Zeigt die erste Zeile rund 15 KB, bitte die Ausgabe in den Chat. Abbruch, wenn `nginx -t` einen
Fehler meldet: `sudo cp /root/kunde.dachkonzepte.gmbh.conf.vor-1.11.40 /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf && sudo nginx -t && sudo systemctl reload
nginx`. Rückweg: dieselbe Zeile.

### Server-Schritte P2b (nach dem Einspielen von 1.11.32 bis 1.11.35)

Reihenfolge wie hier; jeder Schritt mit Erwartung, Abbruch und Rückweg. Als tobias, wenn nicht anders gesagt. Keine Freigabe nötig: es gibt noch keine (P2c).

**P2b-0 Einspielen.** `/home/tobias/update.sh` (Migrationen f2b7d4a9c1e3 und a7c3e9f1d2b4, Probe gegen spielwiese). Erwartet: FERTIG; die Prüfung der Einheiten
meldet `erp-portal.service` und `erp-portalpost.service` als abweichend (sie kommen in P2b-3 und P2b-5). Bis dahin läuft der Postbote ohne Kopien („PORTAL_DATEIEN
nicht gesetzt“ im Journal), die Codes gehen weiter; `/datei/…` beantwortet der Dienst ohne Sitzung mit 401.

**P2b-1 Ordner.**

```bash
sudo install -d -o tobias -g www-data -m 0750 /srv/dk-portal
sudo install -d -o tobias -g www-data -m 2750 /srv/dk-portal/dateien
ls -ld /srv/dk-portal /srv/dk-portal/dateien
id dkportal
sudo -u dkportal ls /srv/dk-portal/dateien; echo "Rückgabe $?"
sudo -u www-data ls /srv/dk-portal/dateien; echo "Rückgabe $?"
```

Erwartet: `drwxr-x--- … tobias www-data … /srv/dk-portal`, `drwxr-s--- … tobias www-data … /srv/dk-portal/dateien`; `id dkportal` ohne www-data;
dkportal „Keine Berechtigung“ und Rückgabe 2; www-data leer und Rückgabe 0. Abbruch, wenn dkportal den Ordner lesen kann. Rückweg: `sudo rm -r /srv/dk-portal`.

**P2b-2 Umgebung.**

```bash
cd /home/tobias/erp
grep -c '^PORTAL_DATEIEN=' .env
echo 'PORTAL_DATEIEN=/srv/dk-portal/dateien' >> .env      # nur, wenn die Zeile davor 0 meldete
grep -c '^PORTAL_DATEIEN=' .env
```

Erwartet: zuletzt `1`. Rückweg: die Zeile in .env wieder löschen.

**P2b-3 Postbote.**

```bash
cd /home/tobias/erp
sudo install -m 644 -o root -g root scripts/server/erp-portalpost.service /etc/systemd/system/erp-portalpost.service
sudo systemctl daemon-reload && sudo systemctl restart erp-portalpost
systemctl is-active erp-portalpost
systemctl show erp-portalpost -p MemoryHigh -p MemoryMax -p UMask -p OOMPolicy
journalctl -u erp-portalpost --since "-3 min" --no-pager | grep -E "Postbote bereit|PORTAL_DATEIEN|Kopien"
ls -la /srv/dk-portal/dateien
```

Erwartet: `active`; `MemoryHigh=671088640`, `MemoryMax=805306368`, `UMask=0027`, `OOMPolicy=continue` (seit 1.11.35); „Postbote bereit (LISTEN portal_post, portal_freigabe)“, kein „PORTAL_DATEIEN nicht
gesetzt“, kein „Kopien nicht abgeglichen“; im Ordner nur `.datenbank` (`-rw-r----- tobias www-data`). Abbruch bei „Kopien nicht abgeglichen“ (Klasse in den
Chat). Rückweg: `git show bd0474f:scripts/server/erp-portalpost.service | sudo tee /etc/systemd/system/erp-portalpost.service > /dev/null` (Stand 1.11.32),
daemon-reload, Neustart.

**P2b-4 Fotos prüfen.**

```bash
cd /home/tobias/erp && .venv/bin/python scripts/pruefe_portal_foto.py
systemctl show erp-portalpost -p MemoryCurrent -p MemoryPeak
```

Erwartet (seit 1.11.35): viermal „ok“ (die vierte: „Vorrang für den OOM-Killer: Kind mit oom_score_adj 1000“), die Zeile „Grenze des Kinds 448 MB …“, zwei
Zeilen „Messung: … Spitze … MB“ und „alle Prüfungen wie erwartet“; dazu Speicher des Postboten selbst (noch ohne Fotos). Die Ausgabe bitte in den Chat -- unter
Linux greifen hier RLIMIT_AS und der Vorrang, lokal ließ sich beides nicht prüfen; aus den Spitzen und dem Speicher des Postboten bestimmt der Betrieb
MemoryHigh und MemoryMax, die Grenze des Kinds folgt in einer eigenen Version. Abbruch bei „!!!“ (beim Vorrang: jedes Foto endete sonst mit „abbruch“).

**P2b-5 Portal.**

```bash
cd /home/tobias/erp
sudo install -m 644 -o root -g root scripts/server/erp-portal.service /etc/systemd/system/erp-portal.service
sudo systemctl daemon-reload && sudo systemctl restart erp-portal
systemctl is-active erp-portal
systemctl show erp-portal -p InaccessiblePaths
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: kunde.dachkonzepte.gmbh' http://127.0.0.1:8010/health
.venv/bin/python scripts/pruefe_einheiten.py
```

Erwartet: `active`; `InaccessiblePaths=/srv/dk-portal`; `200`; die Prüfung der Einheiten ohne Abweichung. Abbruch, wenn der Dienst nicht startet (meist fehlt der
Ordner aus P2b-1). Rückweg: die alte Einheit wie in P2b-3 (`git show bd0474f:scripts/server/erp-portal.service`), daemon-reload, Neustart.

**P2b-6 nginx.**

```bash
sudo cp /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf /root/kunde.dachkonzepte.gmbh.conf.vor-p2b
sudo install -m 644 -o root -g root /home/tobias/erp/scripts/server/nginx-kunde.conf /etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf
sudo nginx -t && sudo systemctl reload nginx
for p in /_portal_dateien/.datenbank /datei/1 /datei/1/herunterladen /health; do printf '%s ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "https://kunde.dachkonzepte.gmbh$p"; done
curl -s -o /dev/null -X POST -H 'Content-Type: application/json' -H 'Origin: https://kunde.dachkonzepte.gmbh' -d '{"freigabe":1}' -w '%{http_code}\n' https://kunde.dachkonzepte.gmbh/api/datei/anfordern
sudo tail -n 6 /var/log/nginx/kunde.access.log
```

Erwartet: „syntax is ok“, „test is successful“; `/_portal_dateien/.datenbank 404` (internal), `/datei/1 401`, `/datei/1/herunterladen 401`, `/health 200`; POST `401`;
im Protokoll die Adressen genau so, ohne Abfrage. Abbruch, wenn `nginx -t` einen Fehler meldet: `sudo cp /root/kunde.dachkonzepte.gmbh.conf.vor-p2b
/etc/nginx/conf.d/kunde.dachkonzepte.gmbh.conf && sudo nginx -t && sudo systemctl reload nginx`, Meldung in den Chat; ebenso, wenn `/_portal_dateien/.datenbank`
etwas anderes als 404 liefert. Rückweg: dieselbe Zeile.

Der Nachweis der Kopfzeilen einer echten Datei mit curl und der Rauchtest (Safari, iPhone, Android mit Herunterladen und Öffnen) kommen, sobald es eine Freigabe
(P2c) und eine Seite mit Link (P2e) gibt.
