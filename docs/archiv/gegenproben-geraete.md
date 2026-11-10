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

## 1.9.294 (Vorweg V2): der Kran bei schmalen Tagen nur mit seinem Zeichen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – bis 43,9 px Inhalt der Karte nur das Kranzeichen | ohne die Regel (`294_1a`, `294_1c`) | 1 rot: v694::test_kran_bis_44_px_nur_mit_zeichen; Klicktest auftraege: „1440 px, 2 Wochen (58 px je Tag): … Kran nur mit Zeichen“, „1280, 3 Wochen: Tag 56 px, kein Chip gekürzt, Kran nur mit Zeichen“ |
| Nr. 2 – das Kranzeichen verschwindet nie | mit dem Namen verschwindet auch das Zeichen (`294_1b`, `294_1d`) | 1 rot: v694::test_kran_bis_44_px_nur_mit_zeichen; Klicktest: dieselben zwei Prüfungen (kein sichtbares Zeichen) |
| Nr. 2 – darüber bleibt „Kr“ (61 px je Tag) | Grenze 50 px (`294_2a`) | Klicktest: „1280 dunkel, 2 Wochen (61 px je Tag): der Kran mit „Kr““. Test: keine eigene -- die Grenze in Pixeln prüft nur der Klicktest am Verhalten |

5 Gegenproben (2 gegen Tests, 3 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Beim Bauen: die erste Grenze (45 px,
gerechnet mit 5 px Innenabstand der Zelle) nahm auch bei 61 px je Tag den Namen weg -- der Klicktest fand es; gemessen: 4,5 px Innenabstand, 44,3 px Inhalt.
Der Test hieß zuerst „…_unter_46_px_…“ (umbenannt, die beiden Test-Gegenproben danach noch einmal: rot).
