# Gegenproben der Runde Stufe 6, R4b (ab 1.9.253)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R4 (`docs/archiv/gegenproben-stufe6-r4.md`): in
einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Migration, Skript) mit dem Marker `GEGENPROBE` ändern, die
genannten Tests laufen lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler).

## 1.9.253 (Punkt 1): Kennzeichen „Plantafel“ am Mitarbeiter

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – drei Werte, am Server erzwungen | freier Text (`253_1a`) | 1 rot: v653::test_anlegen_ohne_angabe_ist_einplanbar_aendern_ohne_angabe_unveraendert |
| Nr. 1 – Auswahl im Formular | ohne „nicht zeigen“ (`253_1b`) | 1 rot: v653::test_formular_und_liste |
| Nr. 1 – Auswahl im Formular | „Bauleiter“ statt „Bauleitung“ (`253_1e`, Klicktest Personen) | rot: plantafel_personen (Formular) |
| Nr. 1 – Liste „Bauleitung“ | „Plantafel“ auch für Bauleitung (`253_1c`) | 1 rot: v653::test_formular_und_liste |
| Nr. 1 – im Verlauf mit Namen | ohne Namen (`253_1d`) | 1 rot: v653::test_drei_werte |
| Nr. 2 – nicht gesetzt -> nicht zeigen | alle einplanbar (`253_2a`) | 2 rot: v653::test_migration_auf_einem_bestand_postgresql, v653::test_migration_auf_einem_bestand_sqlite |
| Nr. 2 – ohne Zeile die Vorgabe | immer einplanbar (`253_2b`) | 1 rot: v653::test_ohne_zeile_die_vorgabe_aus_gruppe_und_funktion |
| Nr. 2 – downgrade: Bauleitung stand in der Plantafel | Bauleitung -> nicht gesetzt (`253_2c`) | 2 rot: v653::test_migration_auf_einem_bestand_postgresql, v653::test_migration_auf_einem_bestand_sqlite |
| Nr. 3 – ohne Angabe unverändert | setzt einplanbar (`253_3a`) | 1 rot: v653::test_anlegen_ohne_angabe_ist_einplanbar_aendern_ohne_angabe_unveraendert |
| Nr. 3 – Anlegen ohne Angabe einplanbar | ohne Zeile (`253_3b`) | 1 rot: v653::test_anlegen_ohne_angabe_ist_einplanbar_aendern_ohne_angabe_unveraendert |
| Nr. 3 – das Formular schickt die Auswahl | immer einplanbar (`253_3c`, Klicktest Personen) | rot: plantafel_personen (Formular; Tafel) |
| Nr. 4 – Bauleitung geht vor der Kolonne | Bauleitung bei der Kolonne (`253_4a`) | 1 rot: v653::test_personen_nach_dem_kennzeichen |
| Nr. 4 – „Ohne Kolonne“ ohne Blick aufs Konto | Gruppe wieder nach dem Konto (`253_4b`) | 1 rot: v653::test_personen_nach_dem_kennzeichen |
| Nr. 4 – „Ohne Kolonne“ ohne Blick aufs Konto | Gruppe wieder nach dem Konto (`253_4c`, Klicktest Personen) | rot: plantafel_personen (Gruppen nach Kolonnen, Ohne Kolonne (Paul mit Konto), dann Bauleitung; jede Person einmal, Vera fehlt) |
| Nr. 5 – Bauleitung bleibt einplanbar | nur „einplanbar“ sichtbar (`253_5a`) | 1 rot: v653::test_nicht_zeigen_auch_nicht_im_einsatz_dialog |
| Nr. 6 – nicht zeigen fehlt in Tafel und Kapazität | sichtbar (`253_6a`) | 2 rot: v653::test_tafel_rechnet_wie_bisher_mit_planning_board, v653::test_tafel_schickt_das_kennzeichen_und_laesst_nicht_zeigen_weg |
| Nr. 6 – nicht zeigen fehlt in „Personen“ und unter „+ Person“ | sichtbar (`253_6c`, Klicktest Personen) | rot: plantafel_personen (Gruppen nach Kolonnen, Ohne Kolonne (Paul mit Konto), dann Bauleitung; jede Person einmal, Vera fehlt) |
| Nr. 6 – die Kolonne schlägt weiter vor | ohne „nicht zeigen“ (`253_6b`) | 1 rot: v653::test_nicht_zeigen_auch_nicht_im_einsatz_dialog |

Ohne eigene Gegenprobe: die Termine aus dem Kalender bei jeder Person mit Konto (Festlegung 1.9.250 Nr. 4, Gegenproben `250_4a`–`250_4e`, unverändert).
Kein Marker unter `app/` nach den Läufen.
