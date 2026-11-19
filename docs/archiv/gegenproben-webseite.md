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
