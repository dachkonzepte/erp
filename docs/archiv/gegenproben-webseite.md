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

## W1b, 1.10.5: Als Anfrage übernehmen

Probendatei im Scratchpad (`proben_1105.py`), Lauf mit `tests/test_v777_webanfragen_uebernehmen.py`; alle 27 rot aus dem geprüften Grund (je FAILED, kein ERROR),
alle Dateien byte-gleich zurück. Dazu Nr. 10 über den Klicktest.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Eigentümer Verbraucher ja, Firma nein | ohne Vorschlag (`1105_1`) | 2 rot |
| Nr. 1 – Telefon und E-Mail des Mieters nie beim Kunden | beim Kunden (`1105_1b`) | 1 rot |
| Nr. 1 – der Mieter Ansprechpartner vor Ort | nie (`1105_1c`) | 2 rot |
| Nr. 1 – PV nach „privat/gewerbe“ | ohne (`1105_1d`) | 1 rot |
| Nr. 1 – nie aus dem Betreff | Straße aus dem Betreff (`1105_1e`) | 2 rot |
| Nr. 2 – E-Mail gleich | weg (`1105_2`) | 1 rot |
| Nr. 2 – Telefon gleich (Ziffern) | nur genau gleich geschrieben (`1105_2b`) | 1 rot |
| Nr. 2 – beim Mieter nur die Hausverwaltung | auch Telefon und E-Mail des Mieters (`1105_2c`) | 1 rot |
| Nr. 2 – PLZ zusätzlich | weg (`1105_2d`) | 1 rot |
| Nr. 3 – Adresse gleich | nie (`1105_3`) | 1 rot |
| Nr. 4 – Verbraucher ohne Vorgabe am Server | Vorgabe ja (`1105_4`) | 1 rot |
| Nr. 4 – Ansprechpartner vor Ort nur mit Haken | immer (`1105_4b`) | 1 rot |
| Nr. 4 – auf der Seite nichts vorgewählt | „Neuer Kunde“ vorgewählt (`1105_4c`) | 1 rot |
| Nr. 5 – nicht aus der Prüfliste | Prüfliste nicht beachten (`1105_5`) | 1 rot |
| Nr. 5 – nie zweimal | Trefferzahl nicht prüfen (`1105_5b`) | 2 rot |
| Nr. 5 – Quelle „Website“ | „sonstiges“ (`1105_5c`) | 1 rot |
| Nr. 5 – Fotos ans Objekt | keine (`1105_5d`) | 2 rot |
| Nr. 5 – scheitert etwas, keine Datei | nicht wegräumen (`1105_5e`) | 1 rot |
| Nr. 5 – Kunde mit Hauptadresse an einer Stelle | ohne Hauptadresse in `kunde_anlegen()` (`1105_5f`) | 2 rot |
| Nr. 6 – Objekt nur des Kunden | Vergleich weg (`1105_6`) | 1 rot |
| Nr. 6 – unbekannter Kunde 404 | Prüfung weg (`1105_6b`) | 1 rot |
| Nr. 7 – die Anfrage nennt die Nummer | leer (`1105_7`) | 1 rot |
| Nr. 7 – Weg zum Eingang | Link auf „Anfragen“ (`1105_7b`) | 1 rot |
| Nr. 8 – die Anfragenummer melden | `melden_soll` nicht setzen (`1105_8`) | 1 rot |
| Nr. 9 – Historie | kein Eintrag (`1105_9`) | 1 rot |
| Nr. 10 – Erledigt nennt die Anfragenummer | Kennzeichen weg (`1105_10`) | 1 rot |
| Nr. 10 – danach die neue Anfrage | Weiterleitung weg (über `klicktest_webanfragen.py`) | rot: wartet vergeblich auf `/inquiries`, 2 Prüfungen rot |
| Nr. 11 – nur das Büro | Monteurin zugelassen (`1105_11`) | 1 rot |

## Nachrunde W1b, 1.10.7: Zeitpunkte über utc_jetzt()

Probendatei im Scratchpad (`proben_1107.py`), Lauf mit `tests/test_v778_webanfragen_zeitpunkte.py`; alle 9 rot aus dem geprüften Grund (je FAILED, kein ERROR,
der Tag der echten Uhr statt 03.03.2025 bzw. umgekehrt), alle Dateien byte-gleich zurück.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – abgeholt | Spaltenvorgabe statt `utc_jetzt()` (`1107_1`) | 1 rot |
| Nr. 1 – gemeldet | `datetime.utcnow()` (`1107_2`) | 2 rot |
| Nr. 1 – letzter Lauf | `datetime.utcnow()` (`1107_3`) | 1 rot |
| Nr. 1 – letzter Erfolg | `datetime.utcnow()` (`1107_4`) | 1 rot |
| Nr. 1 – letzter Lauf ohne Verbindung | Zeit der Sperre (`1107_5`) | 1 rot |
| Nr. 1 – verworfen | `datetime.utcnow()` (`1107_6`) | 1 rot |
| Nr. 1 – geprüft | `datetime.utcnow()` (`1107_7`) | 1 rot |
| Nr. 1 – übernommen | `datetime.utcnow()` (`1107_8`) | 1 rot |
| Nr. 2 – Sperre auf der echten Uhr | Sperre über `utc_jetzt()` (`1107_9`) | 1 rot |
| Nr. 3 – Klicktest unverändert | -- (vor 1.10.7 rot 68/70 im Endlauf b114a03, danach 70/70: das ist die Gegenprobe in umgekehrter Richtung) | -- |

## Nachrunde W1b, 1.10.8: Anderen bestehenden Kunden wählen

Probendatei im Scratchpad (`proben_1108.py`), Lauf mit `tests/test_v779_webanfragen_anderer_kunde.py`; alle 16 rot aus dem geprüften Grund (je FAILED, kein
ERROR), alle Dateien byte-gleich zurück (`1108_6` zuerst als Entfernen angesetzt -- rot über eine Ausnahme beim Suchen statt über die Reihenfolge --, dann als
Verschieben neu: rot über die Reihenfolge). Dazu Nr. 4 über den Klicktest.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 2 – passt() wie im Telefonbuch | Suche mit `contains()` auf dem Namen (`1108_1`) | 3 rot |
| Nr. 2 – Reihenfolge der Kundenliste | nach ID (`1108_1b`) | 1 rot |
| Nr. 3 – ab zwei Zeichen | ab einem Zeichen (`1108_2`) | 1 rot |
| Nr. 3 – höchstens 20 | 30 (`1108_3`) | 1 rot |
| Nr. 3 – die Zahl aller | Zahl der gezeigten (`1108_3b`) | 1 rot |
| Nr. 6 – unbekannte Anfrage 404 | ohne Prüfung (`1108_4`) | 1 rot |
| Nr. 6 – Suche über 100 Zeichen 422 | ohne Grenze (`1108_4b`) | 1 rot |
| Nr. 6 – ab Büro – Auftrag | ohne Rollenprüfung (`1108_4c`) | 1 rot |
| Nr. 6 – Objekt nur des gewählten Kunden | Prüfung weg (`1108_5`) | 1 rot |
| Nr. 1 – zwischen Vorschlägen und „Neuer Kunde“ | „Neuer Kunde“ vor der Suche (`1108_6`) | 1 rot |
| Nr. 1 – immer sichtbar | Suche `hidden` (`1108_6b`) | 1 rot |
| Nr. 4 – eine Wahl wie ein Vorschlag | ohne `data-aenderung` (`1108_7`) | 1 rot |
| Nr. 4 – nichts vorgewählt | jeder Treffer `checked` (`1108_7b`) | 1 rot |
| Nr. 4 – jeder Wert über esc() | Name ohne `esc()` (`1108_7c`) | 1 rot |
| Nr. 5 – Auswahl aufgehoben | ohne Aufheben (`1108_8`) | 1 rot |
| Nr. 3 – Hinweis mit der Zahl aller | nur die gezeigten (`1108_9`) | 1 rot |
| Nr. 4 – danach seine Objekte | ohne `data-aenderung` (über `klicktest_webanfragen.py`) | rot: wartet vergeblich auf die Objekte, 5 Prüfungen rot |

## W1c, 1.10.9: Objektdokument → Eingang der Webseite

Probendatei im Scratchpad (`gp_1109.py` über `gegenprobe.py`: Marker `GEGENPROBE` in der geänderten Zeile, danach byte-genau zurück, Prüfsumme verglichen),
Lauf mit `tests/test_v780_objektdokument_webanfrage.py`; alle 6 rot aus dem geprüften Grund (je FAILED, kein ERROR).

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Übernehmen setzt den Eingang | `webanfrage_id=None` beim Übernehmen | 1 rot |
| Nr. 2 – ein Upload trägt keinen | Vorgabe `webanfrage_id or 1` in `create_property_document()` | 1 rot |
| Nr. 3 – nur am Objekt der übernommenen Anfrage | Bedingung Objekt weg | 2 rot (SQLite, PostgreSQL) |
| Nr. 3 – nur mit „<Nummer>-“ im Dateinamen | Bedingung Dateiname weg | 2 rot |
| Nr. 3 – Beschreibung genau, „%“ wörtlich | `LIKE :text || '%'` statt Gleichheit | 2 rot |
| Nr. 4 – downgrade nimmt nur die Spalte | `DELETE` der verknüpften Dokumente im downgrade | 2 rot |

## W1c, 1.10.10: Kontakt vermerken

Probendateien im Scratchpad (`gp_1110.py`, `gp_1110b.py` über `gegenprobe.py`; `gp_1110k.py` über `gegenprobe_klick.py` mit dem Klicktest), Lauf mit
`tests/test_v781_kontaktvermerke.py` bzw. `tests/test_v740_e1_bis_e5_und_konto.py`; alle rot aus dem geprüften Grund (je FAILED, kein ERROR), alle Dateien
byte-gleich zurück. 8a zuerst mit einem Kommentar mitten im Ausdruck angesetzt -- Syntaxfehler (ERROR) statt Rot --, dann richtig gesetzt: rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Akte mit Menüeintrag | Eintrag entfernt | 1 rot |
| Nr. 2 – jedes weitere Feld 422 | `extra="ignore"` | 1 rot |
| Nr. 2 – Weg nur aus der Liste | `weg: str` | 1 rot |
| Nr. 2 – keine Spalte für einen Inhalt | Spalte `notiz` im Modell | 1 rot |
| Nr. 3 – Server: nicht in der Zukunft | Prüfung aus | 1 rot |
| Nr. 3 – Server: nicht vor 2000 | Prüfung aus | 1 rot |
| Nr. 3 – Dialog: Zukunft nicht gesendet | Prüfung im Dialog aus | 1 rot |
| Nr. 3 – vorbelegt heute | Tag leer | 2 rot |
| Nr. 3 – Weg nicht vorgewählt | `selectedIndex = 1` (Klicktest) | rot: „Weg leer“ 21/22 |
| Nr. 4 – ab Büro – Auftrag | Rolle `field` zugelassen | 1 rot |
| Nr. 4 – unbekannter Bezug 404 | Prüfung aus | 3 rot |
| Nr. 5 – genau ein Bezug | CHECK `>= 0` | 1 rot |
| Nr. 6 – geht mit dem Projekt | Vermerke nicht gelöscht (Fremdschlüssel) | 1 rot |
| Nr. 7 – Akte nennt die Vermerke der Anfrage | `project_id` nur direkt | 1 rot |
| Nr. 7 – Verlauf des Kunden | „Kontakt“ nicht in `TYPEN` | 1 rot |
| Nr. 8 – jüngster Kontakt zuerst | aufsteigend sortiert | 1 rot |
| Nr. 8 – nur als Text | `innerHTML` statt `textContent` | 1 rot |
| Nr. 9 – Konto mit Vermerken | Bereich entfernt | 1 rot (Wächter der Fremdschlüssel auf Konten) |

## W1c, 1.10.11: Archiv nach dem letzten Kontakt

Probendateien im Scratchpad (`gp_1111.py`, `gp_1111b.py`, `gp_1111c.py` über `gegenprobe.py`), Lauf mit `tests/test_v782_archiv.py`; alle rot aus dem geprüften
Grund (je FAILED, kein ERROR), alle Dateien byte-gleich zurück. 1b zuerst mitten in einem mehrzeiligen Ausdruck angesetzt (ERROR), dann an der Konstante: rot.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – auch ein stornierter Auftrag ist ein Auftrag | nur nicht stornierte zählen | 1 rot |
| Nr. 1 – Spam, Test, Doppelt nicht ins Archiv | `LOESCHEN_GRUENDE = ()` | 1 rot |
| Nr. 2 – Entwurf zählt nicht | jedes Angebotsdatum | 1 rot |
| Nr. 2 – künftige Besichtigung zählt nicht | jede Besichtigung | 1 rot |
| Nr. 2 – Kontaktvermerk zählt | Vermerk der Anfrage weg | 1 rot |
| Nr. 2 – Eingang der Webseite zählt | nur die Anlage | 1 rot |
| Nr. 2 / 8 – Zurückholen zählt neu | Zurückholen weg | 1 rot |
| Nr. 3 – Monatsende | höchstens der 28. | 2 rot |
| Nr. 4 – offene Aufgabe sperrt | Sperre aus | 1 rot |
| Nr. 4 – Vorlage sperrt | Sperre aus | 1 rot |
| Nr. 5 – Import nie | Grund aus | 1 rot |
| Nr. 5 / 13 – NULL sperrt nichts | wie `NOT IN` mit NULL | 1 rot |
| Nr. 5 – fremder Vorgang am Objekt | Grund aus | 1 rot |
| Nr. 6 – nur Admin und Büro – Finanzen | jedes Büro | 1 rot |
| Nr. 6 – gesammelt nur mit Prüfsumme | Prüfung aus | 1 rot |
| Nr. 6 – nicht Fälliges bleibt | ohne Prüfung „fällig“ | 1 rot |
| Nr. 7 – Kundenliste | ohne Filter | 1 rot |
| Nr. 7 – Büro-Suche Kunden | ohne Filter | 1 rot |
| Nr. 7 – Suche der Monteurin (Objekte) | ohne Filter | 1 rot |
| Nr. 7 – Fotokopien am Objekt | ohne Filter | 1 rot |
| Nr. 7 – Eingang der Webseite | Ansicht ohne Filter | 1 rot |
| Nr. 9 – keine Aktion am Eingang im Archiv | Bedingung weg | 1 rot |
| Nr. 8 – Kunde kommt mit | Kunde bleibt im Archiv | 1 rot |
| Nr. 9 – Anfrage am Kunden im Archiv | Prüfung aus | 1 rot |
| Nr. 9 – Wechsel ins Archiv | Prüfung aus | 1 rot |
| Nr. 9 – kein Kontaktvermerk im Archiv | Prüfung aus | 1 rot |
| Nr. 10 – von Hand mit Anfrage | Anfrage bleibt | 1 rot |
| Nr. 11 – ohne Inhalte | Titel in der Bezeichnung | 1 rot |
| Nr. 12 – neu nur aktive (Akte) | jeder Kunde im Archiv angeboten | 1 rot |
| Nr. 12 – gekennzeichnet (Akte) | ohne „(im Archiv)“ | 1 rot |
| Nr. 12 – neu nur aktive (Objektformular) | jeder Kunde im Archiv angeboten | 1 rot |
| Nr. 14 – downgrade bricht ab | Prüfung aus | 2 rot (SQLite, PostgreSQL) |

## W1c, 1.10.12: Seite „Aufbewahrung“ und Erinnerung auf „Start“

Probendateien im Scratchpad (`gp_1112.py`, `gp_1112b.py` über `gegenprobe.py`, die letzte über `gegenprobe_klick.py`), Lauf mit
`tests/test_v783_aufbewahrung_seite.py` bzw. dem Klicktest; alle rot aus dem geprüften Grund, alle Dateien byte-gleich zurück. Im ersten Lauf meldete der
Läufer sieben Fälle als „ERROR“: er zählte die mitgeschriebenen Protokollzeilen „ERROR app.seitendaten …“ der roten Seitentests als Fehler -- Filter auf
„ERROR tests…“ korrigiert, der zweite Lauf (`gp_1112b.py`) alle FAILED.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „Alle“ nur mit Recht | Knopf für jedes Büro | 1 rot |
| Nr. 1 – Knöpfe an den Zeilen nur mit Recht | `DARF` übergangen | 1 rot |
| Nr. 1 – Monteurin bekommt die Seite nicht | Rolle `field` zugelassen | 1 rot |
| Nr. 2 – jeder Text über esc() | Titel ohne esc() | 2 rot |
| Nr. 2 – Knopf nur an Fälligem | Knopf auch am Gesperrten | 1 rot |
| Nr. 3 – nur die Liste der Seite | Körper ohne Prüfsumme | 1 rot |
| Nr. 3 / 2 – Art nur aus der festen Liste | Prüfung der Art weg | 1 rot |
| Nr. 4 – Kachel unter den Anfragen | Rang 40 | 1 rot |
| Nr. 4 – ohne Fälliges der Weg ins Archiv | Link weg | 1 rot |
| Nr. 5 – Kundenakte sagt „im Archiv“ | Hinweis immer verborgen | 1 rot |
| Nr. 5 – Eingang im Archiv ohne Aktion | Knöpfe bleiben | 1 rot |
| Nr. 7 – keine „0“ am Reiter | Regel `[hidden]` weg (Klicktest) | rot: „ohne Zahl am Reiter“, 31/32 |
| Nr. 6 – kein Eintrag in der Leiste | -- (eine Entscheidung ohne Prüfung im Code) | -- |

## W1c, 1.10.13: verworfene Eingänge löschen

Probendatei im Scratchpad (`gp_1113.py` über `gegenprobe.py`), Lauf mit `tests/test_v784_verworfene_loeschen.py` bzw. `tests/test_v399_abschliessen.py`; alle 11
rot aus dem geprüften Grund (je FAILED, kein ERROR), alle Dateien byte-gleich zurück.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 / 3 – nur Spam, Test, Doppelt | auch „Sonstiges“ | 2 rot |
| Nr. 1 – 6 Monate nach Eingang | 3 Monate | 2 rot |
| Nr. 1 – nur Admin und Büro – Finanzen | jedes Büro | 1 rot |
| Nr. 1 – gesammelt nur mit Prüfsumme | Prüfung aus | 1 rot |
| Nr. 1 – nicht Fälliges bleibt | alles bis 2999 fällig | 1 rot |
| Nr. 2 – nie mit Objektdokument | NOT EXISTS weg | 1 rot |
| Nr. 2 – die Dateien gehen mit | Dateien bleiben liegen | 1 rot |
| Nr. 4 – Historie ohne Inhalt | Betreff als neuer Wert | 1 rot |
| Nr. 5 – Rückfrage | ohne Rückfrage | 1 rot |
| Nr. 5 – abschließend | `speichern()` statt `abschliessen()` | 1 rot (Wächter `test_v399`) |
| Nr. 6 / 1 – Knöpfe nur mit Recht | Knopf für jedes Büro | 1 rot |
