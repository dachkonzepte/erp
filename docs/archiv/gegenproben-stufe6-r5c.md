# Gegenproben der Runde Stufe 6, R5c (ab 1.9.276)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R5b (`docs/archiv/gegenproben-stufe6-r5b.md`): in einer eigenen
Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript) mit dem Marker `GEGENPROBE` ändern, die genannten Tests bzw. den Klicktest laufen
lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler) bzw. der Klicktest endet nicht wie erwartet.

## 1.9.276 (Punkt 0a): Heiligabend und Silvester keine Arbeitstage

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – kein Arbeitstag | ohne den Arbeitszeitkalender (`276_1a`) | 3 rot: v676::test_verlaengern_laesst_heiligabend_und_silvester_aus, v676::test_geraet_ebenso, v676::test_direkt_anschliessend_ueber_die_feiertage |
| Nr. 1 – für alle, Gruppe egal | nur Kalendertage ohne „nur gewerblich“ (`276_1b`) | 3 rot: dieselben |
| Nr. 2 – auch „direkt anschließend“ | Tag setzen zählt ohne den Kalender (`276_2a`) | 1 rot: v676::test_direkt_anschliessend_ueber_die_feiertage |
| Nr. 3 – abgeschaltet wieder Arbeitstag | auch inaktive Kalendertage (`276_3a`, drei Stellen) | 1 rot: v676::test_abgeschalteter_kalendertag_ist_wieder_arbeitstag |

Alle 4 im ersten Lauf rot. Ohne Gegenprobe: „ab 1.9.277 Verschieben“ (Nr. 2) -- belegt mit den Gegenproben von 1.9.277.
