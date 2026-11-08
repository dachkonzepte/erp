# Gegenproben der Runde Stufe 6, R5a (ab 1.9.259)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R4b (`docs/archiv/gegenproben-stufe6-r4b.md`): in
einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Migration, Skript) mit dem Marker `GEGENPROBE` ändern, die
genannten Tests laufen lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler).

## 1.9.259 (Punkt 0): die Kolonne schlägt „nicht zeigen“ nicht mehr vor

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ohne „nicht zeigen“ | alle aktiven Mitglieder (`259_1a`) | 4 rot: v653::test_nicht_zeigen_auch_nicht_im_einsatz_dialog, v659::test_anlegen_mit_kolonne_ohne_nicht_zeigen, v659::test_pruefung_des_dialogs_schlaegt_sie_nicht_vor, v659::test_wechsel_der_kolonne_ohne_nicht_zeigen |
| Nr. 1 – ohne „nicht zeigen“, Dialog | alle aktiven Mitglieder (`259_1b`, Klicktest Besetzung) | rot: plantafel_besetzung (Dialog) |
| Nr. 1 – das Kennzeichen wie überall (Vorgabe aus der Gruppe) | nur das gespeicherte (`259_1c`) | 2 rot: v659::test_anlegen_mit_kolonne_ohne_nicht_zeigen, v659::test_pruefung_des_dialogs_schlaegt_sie_nicht_vor |
| Nr. 2 – einzeln gewählt kommt sie weiter in den Einsatz | auch einzeln gewählt herausgefiltert (`259_2a`) | 1 rot: v659::test_einzeln_gewaehlt_kommt_sie_weiter_in_den_einsatz |
| Nr. 3 – Liste nennt „nicht zeigen“ | Hinweis leer (`259_3a`) | 1 rot: v659::test_liste_der_kolonnen_nennt_nicht_zeigen |
| Nr. 3 – Liste nennt „nicht zeigen“ | Hinweis leer (`259_3b`, Klicktest Besetzung) | rot: plantafel_besetzung (Kolonnen) |
| Nr. 3 – Formular nennt „nicht zeigen“ | ohne den Zusatz (`259_3c`) | 1 rot: v659::test_formular_der_kolonne_nennt_nicht_zeigen |
| Nr. 3 – Formular nennt „nicht zeigen“ | ohne den Zusatz (`259_3d`, Klicktest Besetzung) | rot: plantafel_besetzung (Kolonnen) |

Ohne eigene Gegenprobe: „bestehende Einsätze und der Schnappschuss an der AV bleiben“ (Nr. 2) -- nichts daran geändert, keine Migration.
