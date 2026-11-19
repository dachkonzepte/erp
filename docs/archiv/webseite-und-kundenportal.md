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

#### Festlegungen 1.10.0 (Bitte bestätigen)

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

#### Festlegungen 1.10.1 (Bitte bestätigen)

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

#### Festlegungen 1.10.2 (Bitte bestätigen)

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

#### Festlegungen 1.10.3 (Bitte bestätigen)

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

#### Festlegungen 1.10.4 (Bitte bestätigen)

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
