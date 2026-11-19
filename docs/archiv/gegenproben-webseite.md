# Gegenproben: Webseite und Kundenportal (ab 1.10.0)

Je Festlegung eine Gegenprobe (Regel 24): eine Änderung unter `app/` (bzw. am Skript oder an der Migration), die genau die Aussage aushebelt; der
zugehörige Test muss aus dem geprüften Grund FAILED werden (nicht ERROR). Danach jede Datei byte-gleich zurück (SHA-256). Festlegungen und Herleitung:
`docs/archiv/webseite-und-kundenportal.md`.

## W1a, 1.10.0: Abholen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur eine Adresse auf diesem Server | jeder Host, auch https/ftp (`1100_1`) | 4 rot: fremde Adressen angefragt |
| Nr. 1 – ohne Umleitung | Öffner ohne Sperre der Umleitung (`1100_1b`) | 1 rot: der Mithörer bekommt den Schlüssel |
| Nr. 1 – ohne Proxy | Öffner mit dem Proxy der Umgebung (`1100_1c`) | 1 rot: der Proxy bekommt den Aufruf samt Schlüssel |
| Nr. 2 – nur gültige Schlüssel | jedes Zeichen erlaubt (`1100_2`) | 3 rot: Zeilenumbruch, Umlaute, zu kurz |
| Nr. 2 – nie im Protokoll | Schlüssel ins Protokoll (`1100_2b`) | 2 rot |
| Nr. 3 – eine Transaktion nach allen Dateien | Zeile vor den Dateien anlegen (`1100_3`) | 23 rot |
| Nr. 3 – erst danach melden | vor dem Holen melden (`1100_3b`) | 8 rot: gemeldet, obwohl nichts abgelegt |
| Nr. 3 – Melden nachholen | nur neu geholte melden (`1100_3c`) | 2 rot |
| Nr. 4 – nie doppelt holen | vorhandene Nummer nicht nachsehen (`1100_4`) | 1 rot: Umschlag zweimal geholt |
| Nr. 4 – Nummer eindeutig | Eindeutigkeit am Modell weg (`1100_4b`) | 1 rot: PostgreSQL nimmt die zweite Zeile an |
| Nr. 5 – Prüfsumme | Vergleich weg (`1100_5`) | 1 rot |
| Nr. 5 – Größe | Vergleich weg (`1100_5b`) | 1 rot |
| Nr. 5 – Typ am Inhalt | Vergleich weg (`1100_5c`) | 1 rot: HTML als Foto abgelegt |
| Nr. 5 – unvollständig übertragen | Vergleich mit der Längenangabe weg (`1100_5d`) | 1 rot |
| Nr. 5 – zu groß beim Lesen | Grenze in der Leseschleife weg (`1100_5e`) | im ersten Lauf GRÜN (s. u.), danach 1 rot |
| Nr. 5 – nichts abgelegt | geschriebene Dateien nicht wegräumen (`1100_5f`) | 5 rot |
| Nr. 6 – Dateiname aus fester Liste | jeder Name auf .pdf/.jpg (`1100_6`) | 1 rot |
| Nr. 6 – `pfad` nie benutzt | `pfad` des Umschlags benutzen (`1100_6b`, zwei Ersetzungen) | 1 rot |
| Nr. 7 – unbekannte Art in die Prüfliste | Prüfung der Art weg (`1100_7`) | 1 rot |
| Nr. 7 – unbekannte Fassung ohne Dateien | Dateien trotzdem holen (`1100_7b`) | 1 rot |
| Nr. 7 – Betreff zu lang | Grenze 100 000 (`1100_7c`) | 1 rot |
| Nr. 7 – Eingang ungültig | Bereich nicht prüfen (`1100_7d`) | 1 rot |
| Nr. 8 – Teile eines JSON | Grenze weg (`1100_8`) | 1 rot |
| Nr. 8 – Bytes einer Antwort | Grenze beim Lesen weg (`1100_8b`) | im ersten Lauf GRÜN (s. u.), danach 1 rot |
| Nr. 8 – höchstens je Lauf | Grenze weg (`1100_8c`) | 2 rot |
| Nr. 9 – abgelehnt mit festem Text | 404 nicht abfangen (`1100_9`) | 1 rot |
| Nr. 9 – nicht erreichbar mit festem Text | Text der Ausnahme weitergeben (`1100_9b`) | 1 rot |
| Nr. 10 – ein Lauf zur Zeit | Bedingung der Belegung weg (`1100_10`) | 2 rot |
| Nr. 10 – Belegung gilt 10 Minuten | 10 Tage (`1100_10b`) | im ersten Lauf GRÜN (s. u.), danach 1 rot |
| Nr. 11 – Spamverdacht als Kennzeichen | immer falsch (`1100_11`) | 1 rot |
| Nr. 12 – Skript ohne `DATABASE_URL`: 2 | Rückgabe 0 (`1100_12`) | 1 rot |
| Nr. 12 – Skript bei Fehler: 1 | Rückgabe 0 (`1100_12b`) | 1 rot |
| Nr. 14 – Downgrade bricht mit Eingang ab | Prüfung weg (`1100_14`) | 1 rot |
| Nr. 13 – kein Modul-Umschalter | -- (eine Abwesenheit; geprüft über Nr. 2: ohne Schlüssel holt das ERP nichts ab) | -- |

34 Gegenproben, alle Dateien byte-gleich zurück. Drei blieben im ersten Lauf grün -- je eine Lücke im Test, nicht im Code:
- `1100_5e` und `1100_8b`: die Tests lösten die Grenze über die Längenangabe (Content-Length) aus; die Grenze in der Leseschleife greift nur ohne sie. Die
  Attrappe antwortet auf Bestellung jetzt ohne Längenangabe (`ohne_laenge`), zwei neue Tests; beide Gegenproben noch einmal: rot.
- `1100_10b`: der Test rechnete mit derselben Konstante (`SPERRE_GILT`) wie der Code. Er prüft jetzt feste 9 und 11 Minuten; noch einmal: rot.
Ein vierter Fund vorher, beim Vorbereiten: der Öffner wurde beim Import gebaut -- ein Proxy der Umgebung, der erst später gesetzt wird, wäre im Test nie
angekommen. Er wird jetzt je Aufruf gebaut (`_oeffner()`), dazu der Test `test_proxy_der_umgebung_nie_benutzt`.

## W1a, 1.10.1: Eingang

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Weg über „Anfragen“ | Knopf im Kopf weg (`1101_1`) | 1 rot |
| Nr. 2 – Büro ab Büro – Auftrag, Monteurin nirgends | ab Monteur (`1101_2`) | 1 rot: 200 statt 403 |
| Nr. 3 – höchstens 20 je Klick | 50 (`1101_3`) | 1 rot |
| Nr. 3 – Frist 40 s | ohne Frist (`1101_3b`) | 1 rot |
| Nr. 3 – Ergebnis in Worten | „davon … zu prüfen“ weg (`1101_3c`) | 1 rot |
| Nr. 4 – neueste zuerst | nach ID aufsteigend (`1101_4`) | 1 rot |
| Nr. 4 – ohne Eingang am Ende | ohne Eingang zuerst (`1101_4b`) | 1 rot |
| Nr. 4 – nie der Umschlag in der Liste | Umschlag im Antwortschema der Liste (`1101_4c`) | im ersten Lauf GRÜN (s. u.), danach 1 rot |
| Nr. 4 – „noch nicht gemeldet“ | Kennzeichen nie (`1101_4d`) | 1 rot |
| Nr. 5 – Hinweis auf die Preise | nie (`1101_5`) | 1 rot |
| Nr. 5 – Reparatur nach dk-reparatur/1 | allgemeine Darstellung statt Klartext (`1101_5b`) | 1 rot: Melder ohne Links |
| Nr. 5 – Dateien aus dem eigenen Pfad | anderer Pfad (`1101_5c`) | 1 rot |
| Nr. 6 – esc() für Werte | Text ohne esc() (`1101_6`) | 1 rot |
| Nr. 6 – esc() für Schlüssel | Schlüssel ohne esc() (`1101_6b`) | 1 rot |
| Nr. 6 – tel: nur Ziffern und + | ganze Angabe im Link (`1101_6c`) | 1 rot |
| Nr. 6 – mailto: nur mit @ ohne Leerraum | jede Angabe als Link (`1101_6d`) | 1 rot |
| Nr. 7 – nur eine Datei dieser Anfrage | Zugehörigkeit nicht geprüft (`1101_7`) | 1 rot: 200 statt 404 |
| Nr. 7 – nur ein vergebener Ablagename | Prüfung des Namens weg (`1101_7b`) | 1 rot: `../geheim.jpg` geliefert |
| Nr. 8 – Hinweis ohne Schlüssel | nie (`1101_8`) | 1 rot |
| Nr. 8 – Zähler im Stand | „zu prüfen“ immer 0 (`1101_8b`) | 1 rot |
| Nr. 9 – unter 650 px als Block | -- (reine Anzeige; geprüft im Klicktest: bei 412 px läuft nichts über, Bild im Bericht) | -- |

20 Gegenproben, alle Dateien byte-gleich zurück. `1101_4c` setzte zuerst an der Hilfsfunktion `zeile_zu_dict()` an und blieb grün -- das
Antwortschema der Liste ist eine Positivliste und ließ den Umschlag ohnehin weg. Der Schutz ist das Schema; dort angesetzt: rot.

## W1a, 1.10.2: Hinweis auf der Startseite

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – direkt unter „Meine Aufgaben“ | sort_order 40 (`1102_1`) | 1 rot |
| Nr. 1 – Standard-Widget | nicht in `DEFAULT_WIDGETS` (`1102_1b`) | 1 rot |
| Nr. 1 – erreicht gespeicherte Layouts | fehlende Standards nicht anhängen (`1102_1c`) | 1 rot |
| Nr. 2 – Zahl als Weg zum Eingang | Weg zu „Anfragen“ (`1102_2`) | 1 rot |
| Nr. 2 – davon Spamverdacht | weg (`1102_2b`) | 1 rot |
| Nr. 2 – die neuesten als Weg zur Anfrage | Weg zum Eingang (`1102_2c`) | 1 rot |
| Nr. 2 – Fehler des letzten Laufs | nie (`1102_2d`) | 1 rot |
| Nr. 2 – „noch nicht eingerichtet“ | nie (`1102_2e`) | 1 rot |
| Nr. 2 – esc() für Werte | Name ohne esc() (`1102_2f`) | 1 rot |
| Nr. 3 – nur Büro und Admin | Prüfung der Rolle weg (`1102_3`) | 1 rot: Abfrage als Monteurin |
| Nr. 4 – `anzahl` wirkt | immer 500 (`1102_4`) | 1 rot |
| Nr. 4 – `anzahl` 1–500 | ohne Grenzen (`1102_4b`) | 1 rot: 0 und 501 angenommen |

12 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück.

## W1b, 1.10.3: Anzeige nach den Funden

Probendatei im Scratchpad (`proben_1103.py`), Lauf mit `tests/test_v775_webanfragen_anzeige.py`; alle 31 rot aus dem geprüften Grund (je FAILED, kein ERROR),
alle Dateien byte-gleich zurück.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Kantservice ohne Adresse | Ort aus `kontakt.ort` (`1103_1`) | 5 rot |
| Nr. 1 – nie aus dem Betreff | ohne Angaben der Betreff als Straße (`1103_1b`) | 4 rot |
| Nr. 1 – Reparatur aus `daten.objekt` | aus `daten` selbst (`1103_1c`) | 5 rot |
| Nr. 2 – ohne Steuerzeichen | Prüfung weg (`1103_2`) | 1 rot |
| Nr. 2 – innerhalb der Grenzen | Grenze weg (`1103_2b`) | 1 rot |
| Nr. 2 – andere Fassung liefert nichts | Fassung nicht prüfen (`1103_2c`) | 2 rot |
| Nr. 2 – Leerraum zusammengefasst | nur `strip()` (`1103_2d`) | 1 rot |
| Nr. 3 – Abholen füllt die Spalten | Spalten nicht setzen (`1103_3`) | 2 rot |
| Nr. 3 – Migration füllt den Bestand | nichts schreiben (`1103_3b`) | 2 rot: SQLite und PostgreSQL |
| Nr. 3 – `downgrade()` nimmt die Spalten weg | nur eine Spalte (`1103_3c`) | 2 rot: SQLite und PostgreSQL |
| Nr. 4 – oben auf der Anfrage | Untertitel ohne Adresse (`1103_4`) | 1 rot |
| Nr. 4 – Zeile „Objekt“ in der Karte | Zeile weg (`1103_4b`) | 1 rot |
| Nr. 4 – Spalte der Liste | Spalte leer (`1103_4c`) | 1 rot |
| Nr. 4 – Widget auf „Start“ | Adresse weg (`1103_4d`) | 1 rot |
| Nr. 4 – über esc() | Adresse ohne esc() im Widget (`1103_4e`) | 1 rot |
| Nr. 5 – kein abgeleiteter Ort | „Ort“ bei jeder Art (`1103_5`) | 1 rot |
| Nr. 5 – Ort beim Kantservice | Kantservice ohne „Ort“ (`1103_5b`) | 1 rot |
| Nr. 6 – Kantservice nur beim Kantservice | Art nicht prüfen (`1103_6`) | 1 rot |
| Nr. 6 – nur mit Inhalt | leere Positionen genügen (`1103_6b`) | 1 rot |
| Nr. 6 – die Seite folgt dem Server | alte Bedingung `Array.isArray(u.positionen)` (`1103_6c`) | 1 rot |
| Nr. 6 – „Preise prüfen“ nur beim Konfigurator | Hinweis bei jeder Art mit Angaben (`1103_6d`) | 1 rot |
| Nr. 6 – „weitere“ bei unbekannter Fassung oder Art | nie (`1103_6e`) | 1 rot |
| Nr. 7 – eingeklappt nur, wenn gleich | ohne Vergleich (`1103_7`) | 2 rot |
| Nr. 7 – die Seite klappt ein | nie eingeklappt (`1103_7b`) | 1 rot |
| Nr. 7 – Zeilenenden dürfen abweichen | genauer Vergleich (`1103_7c`) | 1 rot |
| Nr. 8 – Eingang aus der Unix-Zeit als UTC | `fromtimestamp()` in Ortszeit (`1103_8`) | 2 rot: Winter und Sommer (rot auf einem Rechner in Berlin -- auf einem Rechner in UTC bliebe diese Probe grün; die Anzeige prüft der Klicktest) |
| Nr. 9 – Nummer in Berlin | Nummer aus UTC (`1103_9`) | 2 rot |
| Nr. 9 – Eingang in Berlin mit Versatz | Eingang in UTC (`1103_9b`) | 3 rot |
| Nr. 9 – Liste nach Minute, dann Nummer | nur nach Nummer (`1103_9c`) | 1 rot |
| Nr. 9 – Liste mit allen Kopfdaten | nur `nr` (`1103_9d`) | 1 rot |
| Nr. 9 – `positionen` bei jeder Art | nur beim Kantservice (`1103_9e`) | 1 rot |

## W1b, 1.10.4: Prüfliste und Verwerfen

Probendatei im Scratchpad (`proben_1104.py`), Lauf mit `tests/test_v776_webanfragen_pruefliste.py` (Nr. 3c mit `tests/test_v399_abschliessen.py`); alle 27 rot
aus dem geprüften Grund (je FAILED, kein ERROR), alle Dateien byte-gleich zurück.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – auch mit einem Grund zum Prüfen | nur Spamverdacht (`1104_1`) | 1 rot |
| Nr. 1 – der Eingang ohne die Prüfliste | Eingang = alle neuen (`1104_1b`) | 2 rot |
| Nr. 1 – in den Eingang gegeben = nicht mehr Prüfliste | `geprueft_am` nicht beachten (`1104_1c`) | 1 rot |
| Nr. 1 – „Start“ nennt die Prüfliste | Zeile weg (`1104_1d`) | 1 rot |
| Nr. 1 – Zahl im Eingang ohne Prüfliste | alle neuen zählen (`1104_1e`) | 1 rot |
| Nr. 2 – In den Eingang nur aus der Prüfliste | jede neue (`1104_2`) | 1 rot |
| Nr. 3 – nur ein fester Grund | freier Text (`1104_3`) | 2 rot |
| Nr. 3 – nur eine neue Anfrage | ohne Bedingung (`1104_3b`) | 1 rot |
| Nr. 3 – abschließende Aktion | über `speichern()` (`1104_3c`) | 1 rot (Wächter Regel 29) |
| Nr. 4 – Zurückholen nur verworfen | ohne Bedingung (`1104_4`) | 1 rot |
| Nr. 4 – wieder, wo sie war | beim Zurückholen als geprüft vermerken (`1104_4b`) | 1 rot |
| Nr. 5 – nie zweimal | Trefferzahl nicht prüfen (`1104_5`) | 3 rot |
| Nr. 5 – unbekannt 404 | 409 statt 404 (`1104_5b`) | 2 rot |
| Nr. 6 – Eintrag in der Historie | keiner beim Verwerfen (`1104_6`, nach dem Umbau für `test_v732` neu angesetzt) | 1 rot |
| Nr. 6 – ohne Inhalte | Betreff im neuen Wert (`1104_6b`, ebenso neu angesetzt; `1104_5` danach noch einmal: 3 rot) | 1 rot |
| Nr. 7 – „verworfen“ melden | `melden_soll` nicht setzen (`1104_7`) | 5 rot |
| Nr. 7 – direkt nach der Aktion | nie (`1104_7b`) | 2 rot |
| Nr. 7 – nur unter der Sperre | auch ohne Sperre (`1104_7c`) | 1 rot: an einem laufenden Lauf vorbei gemeldet |
| Nr. 7 – der Lauf holt nach | `_offene_melden()` weg (`1104_7d`) | 2 rot |
| Nr. 7 – mit dem Stand von jetzt | immer eingang-<ID> (`1104_7e`) | 5 rot |
| Nr. 7 – nach dem Zurückholen eingang-<ID> | anderer Wert (`1104_7f`) | 1 rot |
| Nr. 8 – die Seite nennt die offene Meldung | nie (`1104_8`) | 1 rot |
| Nr. 8 – Liste nennt offene Meldungen | Kennzeichen weg (`1104_8b`) | 1 rot |
| Nr. 8 – Stand nennt offene Meldungen | Zeile weg (`1104_8c`) | 1 rot |
| Nr. 9 – zuletzt erledigt zuerst | nach ID (`1104_9`) | 1 rot |
| Nr. 9 (Seite) – Knöpfe je Stand | „In den Eingang“ bei jeder neuen (`1104_9b`) | 1 rot |
| Nr. 10 – nur das Büro | Monteurin zugelassen (`1104_10`) | 1 rot |

Ohne Gegenprobe: Nr. 9 „nichts wird gelöscht“ -- es gibt keinen Weg, der löscht (geprüft im Test: Umschlag und Dateien bleiben).
