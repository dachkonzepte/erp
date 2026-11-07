# Gegenproben der Runde Stufe 6, R4 (ab 1.9.243)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R3a und R3b
(`docs/archiv/gegenproben-stufe6-r3a.md`, `-r3b.md`): in einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript)
mit dem Marker `GEGENPROBE` ändern, die genannten Tests laufen lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an
(FAILED, kein Sammelfehler).

## 1.9.243 (Punkt 0a): „Nächste Tage“ ohne Abwesende im „mit …“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – wer abwesend ist, fehlt | alle der Besetzung im „mit …“ (`243_1a`) | 3 rot: v643 (abwesend an einem Tag, alle weg, Freistellung) |
| Nr. 1 – auch die Freistellung | nur gespeicherte Abwesenheiten, ohne Arbeitszeitkalender (`243_1b`) | 1 rot: v643::test_freistellung_des_arbeitszeitkalenders_fehlt_wie_abwesend |
| Nr. 2 – offener Antrag zählt nicht | offene Anträge als abwesend (`243_2`) | 1 rot: v643::test_offener_antrag_zaehlt_nicht |
| Nr. 3 – je Tag, die Zeile teilt sich | abwesend nur am ersten Tag des Einsatzes gelesen (`243_3`) | 3 rot: v643 (abwesend an einem Tag, alle weg, Freistellung) |
| Nr. 4 – „weiter“ teilt sich nicht | „weiter ohne“, wenn jemand fehlt (`243_4`) | 1 rot: v643::test_weiter_bleibt_weiter |

Kein Marker unter `app/` nach den Läufen.
