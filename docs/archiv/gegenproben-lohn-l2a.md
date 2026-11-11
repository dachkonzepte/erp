# Gegenproben zu den Festlegungen der Lohnrunde L2a (ab 1.9.308)

Regel 24 (stehende Regel seit 1.9.210): jede neue Festlegung bekommt in derselben Runde ihre eigene Gegenprobe, je Aussage; wo keine möglich ist, steht sie mit
Begründung in der Tabelle. Ablauf: die Änderung in einer eigenen Arbeitskopie auf dem Stand des Commits, Marker `GEGENPROBE`, die genannten Tests bzw. der
Klicktest, die Datei byte-genau zurück (Prüfsumme). Rot zählt nur ein FAILED, kein ERROR. Herleitung und Umsetzung: Archiv `zeiterfassung-und-abwesenheit.md`,
„Lohn L2a“.

## 1.9.308 (Punkt 1): die Tagesbilanz

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Feiertag als Posten nur mit Sollzeit | auch ohne Sollzeit (`308_1c`) | 1 rot: v708::test_ein_tag_mit_allem (Sa 26.12.) |
| Nr. 1 – Schlechtwetter = Soll − Arbeit | nur die Sollzeit (`308_1d`) | 1 rot: v708::test_ein_tag_mit_allem |
| Nr. 2 – die Fahrzeit getrennt | keine Fahrzeit (`308_1a`) | 1 rot: v708::test_ein_tag_mit_allem |
| Nr. 2 – die Arbeit ohne Fahrzeit | mit Fahrzeit (`308_1b`) | 1 rot: v708::test_ein_tag_mit_allem |
| Nr. 3 – unabhängig vom Export-Umfang | Posten nach dem Umfang „nichts“ weggelassen (`308_2a`) | 1 rot: v708::test_unabhaengig_von_umfang_und_zuordnung |
| Nr. 4 – eine feste Zahl Abfragen | je Abwesenheit eigene Abfragen (`308_3a`) | 1 rot: v708::test_eine_feste_zahl_abfragen |
| Nr. 5 – die Lohndatei rechnet über die Tagesbilanz | die Arbeit der Bilanz um 0,25 h verfälscht (`308_4a`); dasselbe gegen die Vorprobe September (`308_4b`, von Hand) | 9 rot: v626::test_azubi_mehrarbeit, test_ein_monat_einer_person, test_eintritt_und_kaufmaennisch, test_format_kopf_und_reihenfolge, test_leere_zuordnung_keine_zeile_und_null_stunden, test_mehrarbeit_hoechstens_die_arbeit, test_mehrarbeit_ohne_kennzeichen_bleibt_arbeit, test_monatszeile_zuletzt, test_schnittstelle; Vorprobe: die Datei weicht ab |
| Nr. 6 – eine Regel für Abwesenheitstage und Kalendertage | `abwesenheit_tage()` nimmt die Kalendertage des Aufrufers nicht (`308_5a`) | 1 rot: v708::test_eine_regel_fuer_abwesenheitstage_und_kalendertage |

9 Gegenproben (8 gegen Tests, 1 gegen die Vorprobe), alle rot; jede Datei byte-genau zurück, kein Marker geblieben. „Byte für Byte gleich“ (Nr. 5) ist
der Nachweis selbst: die Vorprobe September und Oktober (Muster) und die lokale Oktober-Datei aus echten Buchungen auf 1.9.307 und auf diesem Stand --
dieselben SHA-256. Kein Klicktest (keine Oberfläche).
