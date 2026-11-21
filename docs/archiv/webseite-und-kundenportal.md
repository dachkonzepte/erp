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

#### Festlegungen 1.10.18 (Bitte bestätigen)

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

#### Festlegungen 1.10.19 (Bitte bestätigen)

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

#### Festlegungen 1.10.20 (Bitte bestätigen)

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

#### Festlegungen 1.10.21 (Bitte bestätigen)

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
