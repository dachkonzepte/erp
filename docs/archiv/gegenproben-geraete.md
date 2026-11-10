# Gegenproben der Geräte-Runde (ab 1.9.293)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R5e (`docs/archiv/gegenproben-stufe6-r5e.md`): in einer eigenen
Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript) mit dem Marker `GEGENPROBE` ändern, die genannten Tests bzw. den Klicktest laufen
lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler) bzw. der Klicktest endet nicht wie erwartet.

## 1.9.293 (Vorweg V1): Namensspalte ab 2 Wochen 200 px

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ab 2 Wochen 200 px | wie bis 1.9.292 nur unter 1400 px (`293_1a`, `293_1c`) | 5 rot: v693::test_namensspalte (1440 px mit 2, 3, 4 Wochen), test_aufbau; Klicktest auftraege: „1440 px, 2 Wochen: Namensspalte 200 px, rollt nicht“ |
| Nr. 1 – mit 1 Woche ab 1400 px weiter 230 px | immer 200 px (`293_1b`, `293_1d`) | 3 rot: v693::test_namensspalte (1440 und 1920 px mit 1 Woche), test_aufbau; Klicktest: „1440 hell, 1 Woche: Namensspalte 230 px“ |
| Nr. 2 – 3 und 4 Wochen dürfen rollen | keine -- eine Erlaubnis, unverändert seit 1.9.283 (mindestens 56 px je Tag) | -- |

4 Gegenproben (2 gegen Tests, 2 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben.
