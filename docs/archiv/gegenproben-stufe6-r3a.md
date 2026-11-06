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
