# Gegenproben der Runde Stufe 6, R3a (ab 1.9.230)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in der Lohnrunde
(`docs/archiv/gegenproben-lohn-l1a.md`): in einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Migration, Skript)
mit dem Marker `GEGENPROBE` ändern, die genannten Tests laufen lassen, die Datei byte-genau zurück (Prüfsumme). Werkzeug: ein Skript im Scratchpad
(je Gegenprobe alt/neu, Tests; prüft nach jeder die Prüfsumme und am Ende, dass kein Marker unter `app/` steht). „rot“ = mindestens ein Test schlägt an.

## 1.9.230 (Punkt 0a): Personalnummer mit genau 5 Ziffern, „DATEV-Nr. = ERP-Nr.“ entfällt

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – `datev_fehlt()` nennt eine Nummer ohne 5 Ziffern | Formatprüfung übergangen (`230_1a`) | 3 rot: v631 (fehlend und falsch, Prüfen, vier Ziffern) |
| Nr. 1 – „Fehlt: …“ zählt sie als Personalnummer | `datev_text()` zählt nur „personalnummer“ (`230_1b`) | 2 rot: v631 |
| Nr. 1 – Eintrag unter „Prüfen“ | `vor_dem_abschluss()` lässt „personalnummer_format“ weg (`230_1c`) | 1 rot: v631::test_pruefen_nennt_sie_unter_vor_dem_abschluss |
| Nr. 2 – die Datei lehnt sie selbst ab | Prüfung in `datei()` übergangen (`230_2`) | 1 rot: v631::test_die_datei_lehnt_sie_selbst_ab |
| Nr. 3 – Kennzeichen „nicht 5 Ziffern“ | `personalnummer_gueltig` immer wahr (`230_3`) | 1 rot: v631::test_monat_und_lohn_kennzeichnet_sie |
| Nr. 4 – Zeitregeln ohne den Schalter | Schlüssel wieder in `time_settings_dict()` (`230_4a`) | 3 rot: v104, v631, v606 |
| Nr. 4 – Seite ohne Häkchen | Häkchen wieder in `settings.html` (`230_4b`) | 1 rot: v631::test_die_seite_hat_keinen_schalter |
| Nr. 4 – ein mitgeschickter Wert wird nicht übernommen | `update_time_settings()` setzt die Spalte (`230_4c`) | 1 rot: v606::test_den_schalter_gibt_es_nicht_mehr |
| Nr. 4 – die alte Spalte liest niemand | `effective_datev_personnel_number()` liest sie wieder (`230_4d`) | 6 rot: v104, v586, v617, v608, v631 (2) |
| Nr. 5 – Anlegen merkt keine Mitarbeiternummer | `create_employee()` merkt sie (`230_5a`) | 1 rot: v606::test_anlegen_merkt_keine_mitarbeiternummer |
| Nr. 5 – Ändern merkt keine Mitarbeiternummer | `update_employee()` merkt sie (`230_5b`) | 2 rot: v593 (2) |
| Nr. 5 – eine Mitarbeiternummer hält keine Nummer (Freigabe) | `personalnummer_halter()` sieht die Mitarbeiternummer (`230_5c`) | 2 rot: v595, v607 |
| Nr. 5 – … und trägt keine (Liste „früher“) | `personalnummern_traeger()` sieht die Mitarbeiternummer (`230_5d`) | 2 rot: v601, v608 |
| Nr. 6 – Migration übernimmt | keine Übernahme (`230_6a`) | 2 rot: v631 Migration SQLite und PostgreSQL |
| Nr. 6 – nur genau 5 Ziffern | jede Mitarbeiternummer (`230_6b`) | 2 rot: dito |
| Nr. 6 – nicht, wenn eine andere Person sie trägt | Prüfung „getragen“ übergangen (`230_6c`) | Runde 1 **grün** (der Testfall war zugleich gemerkt) -> Befund, Fälle E11/E12 ergänzt; Runde 2: 2 rot |
| Nr. 6 – nicht, wenn für eine andere gemerkt | Prüfung „gemerkt“ übergangen (`230_6d`) | 2 rot: v631 Migration |
| Nr. 6 – gemerkt für die Person | nicht gemerkt (`230_6e`) | 2 rot: dito |
| Nr. 6 – nur bei eingeschaltetem Schalter | immer (`230_6f`) | 3 rot: v631 Migration (auch „ohne Schalter“) |
| Nr. 6 – eine abweichende gespeicherte wird ersetzt | nur leere ersetzt (`230_6g`) | 2 rot: v631 Migration |
| Nr. 6 – Leerzeichen am Rand zählen nicht | ohne strip (`230_6h`) | 2 rot: v631 Migration |
| Nr. 6 – dieselbe Nummer bekommt nur die erste Person | „getragen“ nicht nachgeführt (`230_6i`, neu mit E13/E14) | 2 rot: v631 Migration |
| Nr. 7 – Prüfskript nur mit der DATEV-Nummer | Mitarbeiternummer als Rückfall (`230_7`) | 3 rot: v590 |

Befund (Regel 24, „bleibt eine grün, Test nachziehen“): `230_6c` blieb in Runde 1 grün -- der Fall „eine andere Person trägt die Nummer“ (E6/E7) war
zugleich für E7 gemerkt, die zweite Prüfung verdeckte die erste. `test_v631` hat dafür die Fälle E11/E12 (getragen, nicht gemerkt) und E13/E14
(dieselbe Nummer zweimal, Gegenprobe `230_6i`). Wiederholung: rot. Kein Marker unter `app/` nach dem Lauf.

## 1.9.231 (Punkt 0b): keine Rundung je Buchung

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – keine Buchung wird gerundet | `gebucht_nach_zeitregel()` rundet wieder nach der Spalte (`231_1a`) | 10 rot: v466 (6), v483, v527, v632 (2) |
| Nr. 1 – auch die Vorschau einer Dauer nicht | `dauer_vorschau()` rundet auf 0,25 (`231_1b`) | 2 rot: v527, v632 |
| Nr. 1 – auch Nachtrag und Kolonne mit Von/Bis nicht | `nachtrag_nach_zeitregel()` rundet (`231_1c`) | 2 rot: v483, v632 |
| Nr. 1 – der Tag im Lohn bleibt auf 0,25 h | `arbeit_des_tags()` ohne Rundung (`231_3`) | 5 rot: v625 (4), v632 |
| Nr. 2 – nicht in der Antwort der Zeitregeln | Schlüssel wieder in `time_settings_dict()` (`231_2a`) | **grün** -- das Antwortschema filtert ihn; die Aussage hängt am Schema |
| Nr. 2 – … (am Schema) | Feld wieder in `TimeTrackingSettingsOut` (`231_2d`) | 1 rot: v632::test_zeitregeln_ohne_rundung |
| Nr. 2 – ein mitgeschickter Wert wird nicht übernommen | `update_time_settings()` setzt 15 (`231_2b`) | 1 rot: v632::test_zeitregeln_ohne_rundung |
| Nr. 2 – keine Auswahl auf der Seite | Auswahl wieder in `settings.html` (`231_2c`) | 1 rot: v632::test_seiten_ohne_rundung |
| Nr. 4 – Prüfabfrage nimmt ältere gerundete an | Bedingung „gerundet“ weg (`231_4a`) | 1 rot: v522 |
| Nr. 4 – … und minutengenaue | Bedingung „minutengenau“ weg (`231_4b`) | 1 rot: v522 |
| Nr. 5 – Prüfskript ohne Rundung | „Rundung: keine; “ wieder in der ersten Zeile (`231_5`) | 2 rot: v590 |
| Nr. 6 – „Pause je Person“ | „Pause und Rundung“ wieder in `mobil_zeiten.html` (`231_6`) | 1 rot: v632::test_seiten_ohne_rundung |
| Nr. 3 – gebuchte Zeiten bleiben | ohne Gegenprobe: keine Migration, kein Code ändert gespeicherte Stunden (nichts zum Aushebeln) | -- |

`231_2a` blieb grün, kein Loch im Test: `GET`/`PUT /api/time-backoffice/settings` antworten über `TimeTrackingSettingsOut`, ein zusätzlicher Schlüssel im
Dict fällt dort heraus. Die Gegenprobe am Schema (`231_2d`) ist rot. Kein Marker unter `app/` nach dem Lauf.

## 1.9.232 (Punkt 0c): Eingangsrechnung speichern und gleichzeitig löschen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Antwort entsteht vor dem Commit unter der Sperre | wieder erst `commit()`, dann neu lesen (`232_1`) | 1 rot: v399::test_postgresql_eingangsrechnung_speichern_und_loeschen_ohne_deadlock (deterministisch: der Haken an `_load` wartet nach dem Commit auf das Löschen) |
| Nr. 2 – Beleg hochladen/entfernen bleiben | ohne Gegenprobe: nichts geändert, nur benannt | -- |

## 1.9.233 (Punkte 1 und 2): Besetzung je Einsatz

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Konflikte aus der Besetzung | `_slot_members()` liest den Schnappschuss (`233_1a`) | rot: v633 |
| Nr. 1 – Kapazität aus der Besetzung | `_besetzung()` liest den Schnappschuss (`233_1b`) | rot: v633 |
| Nr. 1 – Tafel zeigt die Besetzung | `slot_to_dict()` `employees` aus dem Schnappschuss (`233_1c`) | rot: v633 |
| Nr. 1 – „Heute“ aus der Besetzung | Einsätze der Person über den Schnappschuss (`233_1d`) | rot: v633, v224 |
| Nr. 2 – nur aktive Mitglieder | auch inaktive vorgeschlagen (`233_2a`) | rot: v633 |
| Nr. 2 – heutige Mitglieder, nicht der Schnappschuss | Vorschlag aus dem Schnappschuss an der AV (`233_2b`) | rot: v633 |
| Nr. 3 – spätere Änderung ändert keinen Einsatz | ein neuer Einsatz setzt die Besetzung der anderen derselben Kolonne (`233_2c`) | rot: v633 |
| Nr. 2 – Wechsel der Kolonne setzt ihre Mitglieder | Wechsel lässt die Personen (`233_3`) | rot: v633 |
| Nr. 4 – employee_ids genau so | mit Kolonne immer ihr Vorschlag (`233_4`) | rot: v633 |
| Nr. 5 – ohne Kolonne mindestens eine Person (Schema) | Prüfung im Schema weg (`233_5a`) | Runde 1 **grün** (die Geschäftsfunktion lehnt ebenfalls ab) -> Befund, Test am Schema ergänzt; Runde 2: rot |
| Nr. 5 – … beim Ändern | Prüfung in `update_slot()` weg (`233_5b`) | rot: v633 (2) |
| Nr. 5 – „ohne Kolonne“ lässt die Personen | Wechsel auf ohne Kolonne leert sie (`233_5c`) | rot: v633 |
| Nr. 5 – … beim Anlegen | Prüfung in `create_slot()` weg (`233_5d`) | rot: v633 |
| Nr. 4 – inaktiv 422 | Prüfung „aktiv“ weg (`233_7a`) | rot: v633 |
| Nr. 4 – unbekannt 422 | Prüfung „bekannt“ weg (`233_7b`) | rot: v633 (2) |
| Nr. 4 – 422 beim Ändern, nicht 404 | eigene Ausnahme im Router nicht gefangen (`233_7c`) | rot: v633 |
| Nr. 8 – geänderte Besetzung fragt zurück | Vergleich ohne Besetzung (`233_8`) | rot: v633 |
| Nr. 7 – Zugriff über die Besetzung | Weg über die Besetzung weg (`233_9`) | rot: v633 |
| Nr. 6 – neue Einzelzuweisung ist kein Einsatz | Einsätze der Person auch über die Einzelzuweisung (`233_10`) | rot: v633 |
| Akte: Personen der Besetzung | Personen aus dem Schnappschuss (`233_11a`) | rot: v633 |
| Akte: auch ohne Kolonne | innerer statt äußerer Join (`233_11b`) | rot: v633 |
| Tafel: Zeile „Ohne Kolonne“ | Zeile weg (`233_12a`) | rot: v633 |
| Dialog: „ohne Kolonne – die Personen bleiben“ | Option weg (`233_12b`) | rot: v633 |
| Dialog: leer schickt null | `Number('')` (`233_12c`) | rot: v633 |
| Nr. 6 – Migration mit Einzelzuweisungen | ohne Einzelzuweisungen (`233_13a`) | rot: v633 Migration SQLite und PostgreSQL |
| Nr. 6 – Reihenfolge Kolonne, dann einzeln | umgekehrt (`233_13b`) | rot: dito |
| Nr. 6 – jede Person einmal | doppelt (`233_13c`) | rot: dito |
| Nr. 11 – downgrade bricht ab | ohne Abbruch (`233_13d`) | rot: dito |
| Nr. 10 – Änderungsprotokoll je Person | Zweig „Plantafel-Besetzung“ weg (`233_14a`; erster Anlauf am Text der Typenliste nicht eindeutig, nicht gelaufen) | rot: v633 |
| Nr. 10 – „Ohne Kolonne · …“ | Etikett „Team“ (`233_14b`) | rot: v633 |
| Nr. 10 – im Verlauf der Akte „Termin“ | Art fehlt (`233_14c`) | rot: v633 |
| Nr. 9 – wer bleibt, behält seinen Platz | alle Zeilen neu (`233_15`) | rot: v633 (2; Eindeutigkeit Einsatz/Person) |

Kein Marker unter `app/` nach dem Lauf.

## 1.9.234 (Punkt 3): Geräte je Einsatz

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur aktive Geräte der Kolonne | auch inaktive (`234_1a`) | rot: v634 (2) |
| Nr. 1 – die Kolonne schlägt ihre Geräte vor | kein Vorschlag (`234_1b`) | rot: v634 (2) |
| Nr. 2 – unbekannt 422 | Prüfung weg (`234_2a`) | rot: v634 |
| Nr. 2 – inaktiv 422 | Prüfung weg (`234_2b`) | rot: v634 |
| Nr. 2 – Tag außerhalb 422 | Prüfung weg (`234_2c`) | rot: v634 (2) |
| Nr. 2 – leere Tagesliste 422 | Prüfung weg (`234_2d`) | rot: v634 |
| Nr. 2 – doppelt genannt: das erste zählt | das letzte zählt (`234_2e`) | rot: v634 |
| Nr. 3 – Wechsel der Kolonne setzt ihre Geräte | Wechsel lässt die Geräte (`234_3a`) | rot: v634 |
| Nr. 3 – „ohne Kolonne“ lässt die Geräte | auch ohne Kolonne neu gesetzt (`234_3b`) | rot: v634 |
| Nr. 4 – gleiche Dauer: Tage wandern mit | nie verschieben (`234_4a`) | rot: v634 |
| Nr. 4 – ohne verbleibenden Tag fällt das Gerät weg | dann alle Tage (`234_4b`) | rot: v634 |
| Nr. 5 – Gerät doppelt nur bei gemeinsamen Tagen | Tage egal (`234_5a`) | rot: v634 |
| Nr. 5 – Kalender des Geräts nur an seinen Tagen | alle Arbeitstage (`234_5b`) | rot: v634 |
| Nr. 5 – Tafel belegt nur an seinen Tagen | ganzer Einsatz (`234_5c`) | Runde 1 rot **aus dem falschen Grund** (Marker als Kommentar mitten im Ausdruck: Sammelfehler); Runde 2 (Marker als Zeichenkette): rot, v634::test_tafel_belegung_nur_an_den_tagen |
| Nr. 6 – geänderte Geräte fragen zurück | Vergleich ohne Geräte (`234_6`) | rot: v634 |
| Nr. 7 – Gerät am Einsatz nur abgeschaltet | Prüfung weg (`234_7`) | rot: v634 |
| Nr. 8 – Migration übernimmt die Geräte | keine (`234_8a`) | rot: v634 Migration SQLite und PostgreSQL |
| Nr. 8 – alle Tage | leere Liste statt leer (`234_8b`) | rot: dito |
| Änderungsprotokoll „Plantafel-Gerät“ | Zweig weg (`234_9a`) | rot: v634 |
| Verlauf der Akte „Termin“ | Art fehlt (`234_9b`) | rot: v634 |
| Name live aus dem Gerät | „?“ (`234_10`) | rot: v634 |

Kein Marker unter `app/` nach dem Lauf. Geprüft für alle Gegenproben der Runde: jede rote nennt einen gescheiterten Test (FAILED), keinen Sammelfehler -- außer
`234_5c` in Runde 1 (oben).

## 1.9.235 (Punkt 4): Status vorläufig | fest

Gelaufen auf dem Stand 1.9.237 (alle Änderungen bis dahin), ohne PostgreSQL (die Migrationsprobe unter SQLite reicht, um rot zu sehen); jede Gegenprobe
betrifft nur ihre eigene Stelle.

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – andere Werte 422 beim Anlegen (Schema) | Schema freier Text (`235_1a`) | Runde 1 **grün** (die Geschäftsfunktion prüft auch) -> Test am Schema ergänzt; Runde 2: rot |
| Nr. 1 – … (Geschäftsfunktion Anlegen) | Prüfung in `create_slot()` weg (`235_1b`) | rot: v635 |
| Nr. 1 – … (Geschäftsfunktion Ändern) | Prüfung in `update_slot()` weg (`235_1c`) | rot: v635 |
| Nr. 1 – andere Werte 422 beim Ändern (Schema) | Schema freier Text (`235_1d`) | Runde 1 **grün** -> Test am Schema; Runde 2: rot |
| Nr. 1 – neu vorläufig (Geschäftsfunktion) | Vorgabe „fest“ in `create_slot()` (`235_1e`) | Runde 1 **grün** (die Schnittstelle schickt den Status immer) -> Test ohne Status; Runde 2: rot |
| Nr. 1 – neu vorläufig (Schema) | Vorgabe „fest“ im Schema (`235_1f`) | rot: v635 |
| Anzeige „vorläufig“ | `status_label` = Rohwert (`235_1g`) | rot: v635 |
| Dialog nur die zwei Werte | dritte Option (`235_1h`) | rot: v635, v447 (3) |
| neu im Dialog vorläufig | „fest“ (`235_1i`) | rot: v635 |
| Verlauf „Vorläufig“/„Fest“ | Namen fehlen (`235_1j`) | rot: v635 |
| Nr. 2 – „geplant“ -> vorläufig, sonst fest | auch leer -> vorläufig (`235_2a`) | rot: v635 Migration |
| Nr. 2 – downgrade | ohne Rückweg (`235_2b`) | rot: v635 Migration |
| Prüfabfrage kennt die zwei Werte | „geplant“ statt „vorlaeufig“ (`235_2c`) | rot: v447 (2) |
| Nr. 3 – vorläufig zählt wie fest | vorläufige Einsätze aus den Konflikten (`235_3`) | rot: v635 |

## 1.9.236 (Punkt 5): Konflikte auf dem neuen Modell

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – kein „Kolonne doppelt“ | Prüfung wieder da (`236_1`) | rot: v563, v636 |
| Nr. 1 – … nicht unter den Warnungen | „team“ wieder in `WARNUNG_ARTEN` (`236_1b`) | rot: v636 |
| Nr. 2 – Prüffrist wird geprüft | keine Prüfungen geladen (`236_2a`) | rot: v636 |
| Nr. 2 – der Fälligkeitstag gilt noch | „ab“ statt „nach“ (`236_2b`) | rot: v636 (2) |
| Nr. 2 – Warnung, nicht Hinweis | `pruefung` nicht in `WARNUNG_ARTEN` (`236_2c`) | rot: v636 (2) |
| Nr. 2 – mit dem ersten Tag danach | letzter Tag (`236_2d`) | rot: v636 |
| Nr. 3 – nur mit Betriebsmittelverwaltung | auch ohne (`236_3a`) | rot: v636 |
| Nr. 3 – ohne Fälligkeit keine Warnung | Prüfungen ohne Fälligkeit mitgenommen (`236_3b`) | rot: v636 |
| Nr. 4 – nur an den Tagen des Geräts | alle Tage des Einsatzes (`236_4`) | rot: v636 |
| Tafel: „Prüffrist abgelaufen“, kein „Kolonne doppelt“ | Beschriftung zurück (`236_5`) | rot: v636 |
