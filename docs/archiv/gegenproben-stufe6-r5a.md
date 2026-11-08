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

## 1.9.260 (Punkt 1): Besetzung je Tag -- Spalte und Schreibweg

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – der Bestand steht an allen Tagen | Migration mit Vorgabe „[]“ (`260_1a`) | 2 rot: v660::test_migration_auf_einem_bestand_postgresql, v660::test_migration_auf_einem_bestand_sqlite |
| Nr. 2 – downgrade bricht ab | ohne Abbruch (`260_2a`) | 2 rot: v660::test_migration_auf_einem_bestand_postgresql, v660::test_migration_auf_einem_bestand_sqlite |
| Nr. 3 – besetzung mit Tagen | Tage verworfen (`260_3a`) | 11 rot: v660::test_aendern_setzt_genau_und_ein_teil_update_laesst_die_tage, v660::test_aenderungsprotokoll_nennt_die_tage, v660::test_anderer_zeitraum_laesst_die_tage_darin_und_wer_keinen_hat_faellt_weg, v660::test_besetzung_mit_tagen_anlegen, v660::test_doppelt_genannt_zaehlt_die_erste, v660::test_falle_tag_aktion_schreibt_auch_ungenannte_geraete_fest, v660::test_geaenderte_tage_fragen_zurueck_wie_die_besetzung, v660::test_pruefung_nennt_die_tage_je_person, v660::test_tage_einer_person_nur_im_einsatz[person0-liegt, v660::test_tage_einer_person_nur_im_einsatz[person1-mindestens, v660::test_verschieben_nimmt_die_tage_mit |
| Nr. 3 – employee_ids heißt alle Tage | leere Liste statt alle Tage (`260_3b`) | 4 rot: v660::test_aenderungsprotokoll_nennt_die_tage, v660::test_employee_ids_und_kolonne_heissen_alle_tage, v660::test_falle_tag_aktion_schreibt_die_anderen_fest, v660::test_geaenderte_tage_fragen_zurueck_wie_die_besetzung |
| Nr. 3 – beides zugleich 422 | ohne die Prüfung im Ändern (`260_3c`) | 1 rot: v660::test_unbekannt_inaktiv_und_beides_zugleich |
| Nr. 3 – Tage nur im Einsatz | ohne die Prüfung (`260_3d`) | 3 rot: v634::test_tage_wandern_mit_und_fallen_weg, v634::test_ungueltige_geraete_422[ausserhalb-liegt, v660::test_tage_einer_person_nur_im_einsatz[person0-liegt |
| Nr. 3 – doppelt genannt die erste | doppelt übernommen (`260_3e`) | 1 rot: v660::test_doppelt_genannt_zaehlt_die_erste |
| Nr. 4 – Normalform | Liste bleibt (`260_4a`) | 1 rot: v660::test_normalform_alle_tage_heisst_null_auch_bei_geraeten |
| Nr. 5 – geänderte Tage fragen zurück | nur die Personen verglichen (`260_5a`) | 1 rot: v660::test_geaenderte_tage_fragen_zurueck_wie_die_besetzung |
| Nr. 6 – Tage wandern mit | ohne Mitnehmen der Personen (`260_6a`) | 2 rot: v660::test_anderer_zeitraum_laesst_die_tage_darin_und_wer_keinen_hat_faellt_weg, v660::test_verschieben_nimmt_die_tage_mit |
| Nr. 6 – danach in der Normalform | Liste bleibt (`260_6b`) | 1 rot: v660::test_anderer_zeitraum_laesst_die_tage_darin_und_wer_keinen_hat_faellt_weg |
| Nr. 7 – die Falle: festschreiben | ohne Festschreiben (`260_7a`) | 2 rot: v660::test_falle_tag_aktion_schreibt_auch_ungenannte_geraete_fest, v660::test_falle_tag_aktion_schreibt_die_anderen_fest |
| Nr. 7 – der Dialog nimmt alle mit | Vorgabe „nicht mitnehmen“ (`260_7b`) | 1 rot: v660::test_falle_ende_aendern_nimmt_alle_tage_mit |
| Nr. 8 – der Dialog schickt besetzung | schickt employee_ids (`260_8a`) | 2 rot: v660::test_dialog_haelt_die_tage_aus_der_pruefung, v660::test_dialog_schickt_die_besetzung_mit_den_tagen |
| Nr. 8 – der Dialog hält die Tage aus der Prüfung | Tage verworfen (`260_8b`) | 1 rot: v660::test_dialog_haelt_die_tage_aus_der_pruefung |
| Nr. 8 – Antwort nennt die Tage | ohne Tage (`260_8c`) | 1 rot: v660::test_besetzung_mit_tagen_anlegen |
| Nr. 8 – Prüfung nennt die Tage | ohne Tage (`260_8d`) | 1 rot: v660::test_pruefung_nennt_die_tage_je_person |

Ohne Klicktest-Gegenprobe: Tage wählen lässt sich im Dialog erst ab 1.9.264 (dort `klicktest_plantafel_tage`).

## 1.9.261 (Punkt 2): Konflikte, Kapazität und der Zustand im Dialog je Tag

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Person doppelt nur an gemeinsamen Tagen | Überschneidung der Zeiträume (`261_1a`) | 1 rot: v661::test_person_doppelt_nur_an_gemeinsamen_tagen |
| Nr. 1 – Person doppelt nennt die Tage | ohne Tage (`261_1b`) | 2 rot: v661::test_bestand_meldet_dasselbe_mit_den_tagen, v661::test_person_doppelt_nur_an_gemeinsamen_tagen |
| Nr. 1 – Gerät doppelt nennt die Tage | ohne Tage (`261_1c`) | 1 rot: v661::test_geraet_doppelt_nennt_die_tage |
| Nr. 2 – abwesend nur an ihren Tagen | an allen Tagen (`261_2a`) | 1 rot: v661::test_abwesend_nur_an_ihren_tagen |
| Nr. 2 – Antrag nur an ihren Tagen, erster Tag | an allen Tagen (`261_2b`) | 1 rot: v661::test_antrag_offen_nur_an_ihren_tagen_mit_dem_ersten |
| Nr. 3 – Feiertag nur, wenn jemand steht | an jedem Arbeitstag (`261_3a`) | 1 rot: v661::test_feiertag_nur_wenn_jemand_steht |
| Nr. 3 – ein Gerät ist auch jemand | nur Personen (`261_3b`) | 1 rot: v661::test_feiertag_nur_wenn_jemand_steht |
| Nr. 4 – Kapazität je Tag | alle Personen an jedem Tag (`261_4a`) | 1 rot: v661::test_kapazitaet_je_tag |
| Nr. 4 – Rechnung je Person | alle Arbeitstage (`261_4b`) | 1 rot: v661::test_rechnung_im_dialog_je_person |
| Nr. 5 – gewählt an ihren Tagen | alle Tage des Einsatzes (`261_5a`) | 3 rot: v661::test_dialog_abwesend_nur_an_ihren_tagen, v661::test_dialog_antrag_nur_an_ihren_tagen, v661::test_dialog_auch_bei_nur_mit_den_gemeinsamen_tagen |
| Nr. 5 – gemeinsame Tage mit dem anderen Einsatz | dessen ganzer Zeitraum (`261_5b`) | 1 rot: v661::test_dialog_auch_bei_nur_mit_den_gemeinsamen_tagen |
| Nr. 5 – Antrag nur an ihren Tagen | jeder Antrag (`261_5c`) | 1 rot: v661::test_dialog_antrag_nur_an_ihren_tagen |
| Nr. 5 – abwesend nur an ihren Tagen | ganzer Zeitraum (`261_5d`) | 1 rot: v661::test_dialog_abwesend_nur_an_ihren_tagen |

Ohne eigene Gegenprobe: „der Zähler zählt ein Paar weiter einmal“ (Nr. 1) -- `tafel_zaehler()` unverändert seit 1.9.247, die Tage gehen nicht in seinen
Schlüssel; der Test `test_tafel_zaehlt_ein_paar_einmal` hält es fest. Ohne Klicktest-Gegenprobe: die Oberfläche zeigt die Tage erst ab 1.9.264.
