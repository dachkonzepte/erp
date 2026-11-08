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

## 1.9.262 (Punkt 3): was die Monteurin merkt

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Karte nur an ihren Tagen | jeder Einsatz im Zeitraum (`262_1b`) | 3 rot: v662::test_karte_nur_an_ihren_tagen, v662::test_mobil_einsaetze_heute_und_kommend, v662::test_vorwahl_der_zeit_nur_an_ihren_tagen |
| Nr. 1 – Karte nur an ihren Tagen | jeder Einsatz im Zeitraum (`262_1e`, Klicktest Heute je Tag) | rot: heute_tage (Kai; Kai; Mia; Ole) |
| Nr. 1 – von–bis = ihre Folge | der Zeitraum der Einsätze (`262_1d`) | 2 rot: v662::test_von_bis_ist_ihre_folge_um_heute, v662::test_zwei_einsaetze_desselben_auftrags_nur_der_ihrer_tage |
| Nr. 1 – ein Tag ohne Arbeit unterbricht nicht | jeder Tag ohne sie unterbricht (`262_1c`) | 1 rot: v662::test_folge_ueber_das_wochenende |
| Nr. 2 – „Mit dir“ nur heute | die ganze Besetzung (`262_2a`) | 1 rot: v662::test_mit_dir_nur_wer_heute_dran_ist |
| Nr. 2 – ein zweiter Einsatz zählt nicht | alle Einsätze des Auftrags im Zeitraum (`262_1a`) | 1 rot: v662::test_zwei_einsaetze_desselben_auftrags_nur_der_ihrer_tage |
| Nr. 3 – Nächste Tage nur ihre Tage | alle Tage des Einsatzes (`262_3a`) | 2 rot: v662::test_naechste_tage_nur_ihre_tage_und_mit_je_tag, v662::test_weiter_nur_wenn_sie_heute_dran_ist |
| Nr. 3 – Nächste Tage nur ihre Tage | alle Tage des Einsatzes (`262_3d`, Klicktest Heute je Tag) | rot: heute_tage (Kai) |
| Nr. 3 – „mit …“ je Tag | die ganze Besetzung (`262_3b`) | 1 rot: v662::test_naechste_tage_nur_ihre_tage_und_mit_je_tag |
| Nr. 3 – „mit …“ je Tag | die ganze Besetzung (`262_3e`, Klicktest Heute je Tag) | rot: heute_tage (Lia) |
| Nr. 3 – „weiter“ nur, wenn sie heute dort steht | der Einsatz läuft heute (`262_3c`) | 1 rot: v662::test_weiter_nur_wenn_sie_heute_dran_ist |
| Nr. 4 – Vorwahl nur an ihren Tagen | jeder Einsatz im Zeitraum (`262_4a`) | 1 rot: v662::test_vorwahl_der_zeit_nur_an_ihren_tagen |
| Nr. 5 – /upcoming nur mit ihren Tagen | jeder Einsatz im Fenster (`262_5a`) | 1 rot: v662::test_mobil_einsaetze_heute_und_kommend |
| Nr. 6 – Kran-Termin je Tag | die ganze Besetzung (`262_6a`) | 1 rot: v662::test_kran_termin_nennt_wer_an_seinen_tagen_dran_ist |

Ohne eigene Gegenprobe: Nr. 7 (unverändert, nichts daran geändert).

## 1.9.263 (Punkt 4): der leere Tag

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – am Rand kürzen | nie kürzen (`263_1a`) | 4 rot: v663::test_behalten_mit_dem_zuletzt_geleerten_tag, v663::test_rand_kuerzt_auch_ein_wochenende, v663::test_rand_kuerzt_beim_aendern, v663::test_rand_kuerzt_beim_anlegen_und_die_stunden_bleiben |
| Nr. 1 – auch nach dem Ändern | nur beim Anlegen (`263_1b`) | 2 rot: v663::test_behalten_mit_dem_zuletzt_geleerten_tag, v663::test_rand_kuerzt_beim_aendern |
| Nr. 1 – danach in der Normalform | ohne Mitnehmen der Tage (`263_1c`) | 1 rot: v663::test_rand_kuerzt_beim_anlegen_und_die_stunden_bleiben |
| Nr. 1 – auch ein Wochenende | Wochenende am Rand bleibt (`263_1d`) | 1 rot: v663::test_rand_kuerzt_auch_ein_wochenende |
| Nr. 2 – leer nur an Arbeitstagen | jeder Tag (`263_2a`) | 2 rot: v663::test_lucke_am_wochenende_ohne_die_tage_ohne_arbeit, v663::test_wochenende_in_der_mitte_ist_nie_leer |
| Nr. 2 – Tag ohne Arbeit an der Lücke gehört nicht dazu | bleibt (`263_2b`) | 1 rot: v663::test_lucke_am_wochenende_ohne_die_tage_ohne_arbeit |
| Nr. 2 – ganz leer ist ein Stück | kein Stück (`263_2c`) | 1 rot: v663::test_behalten_mit_dem_zuletzt_geleerten_tag |
| Nr. 3 – Rückfrage | ohne (`263_3a`) | 5 rot: v633::test_ohne_kolonne_behaelt_die_personen, v633::test_update_slot_direkt_ohne_kolonne_ohne_personen, v640::test_aendern_einer_kranvermietung, v640::test_baustelle_ohne_kolonne_braucht_weiter_eine_person, v663::test_leer_werden_fragt_zurueck_und_aendert_nichts |
| Nr. 3 – Löschen löscht | löscht nicht (`263_3b`) | 1 rot: v663::test_loeschen |
| Nr. 3 – mehrere zugleich: der erste | der letzte (`263_3c`) | 1 rot: v663::test_behalten_mehrere_zugleich_der_erste |
| Nr. 3 – schon leer fragt nicht | fragt immer (`263_3d`) | 1 rot: v663::test_schon_leer_fragt_nicht |
| Nr. 3 – die Antwort nennt die Rückfrage | andere Art (`263_3e`) | 1 rot: v663::test_leer_werden_fragt_zurueck_und_aendert_nichts |
| Nr. 4 – die Prüfung fragt nicht | fragt (`263_4a`) | 1 rot: v663::test_pruefung_des_dialogs_sagt_leer_und_fragt_nicht |
| Nr. 4 – der Dialog nennt es vorher | ohne Hinweis (`263_4b`) | 1 rot: v663::test_dialog_und_ziehen_nehmen_die_rueckfrage |
| Nr. 4 – die Seite fragt | leerFrage antwortet nie (`263_4c`) | 1 rot: v663::test_seite_fragt_und_schickt_die_wahl |
| Nr. 4 – auch beim Ziehen | ohne (`263_4d`) | 1 rot: v663::test_dialog_und_ziehen_nehmen_die_rueckfrage |
| Nr. 5 – ohne Kolonne genügt ein Gerät | nur Personen (`263_5a`) | 1 rot: v663::test_ohne_kolonne_genuegt_beim_anlegen_ein_geraet |
| Nr. 5 – danach darf er leer werden | Mindestbesetzung wie bis 1.9.262 (`263_5b`) | 9 rot: v633::test_ohne_kolonne_behaelt_die_personen, v633::test_update_slot_direkt_ohne_kolonne_ohne_personen, v663::test_behalten_mehrere_zugleich_der_erste, v663::test_behalten_mit_dem_zuletzt_geleerten_tag, v663::test_ganz_leer_mit_stunden_meldet_die_kapazitaet, v663::test_leer_werden_fragt_zurueck_und_aendert_nichts, v663::test_loeschen, v663::test_pruefung_des_dialogs_sagt_leer_und_fragt_nicht, v663::test_schon_leer_fragt_nicht |
| Nr. 5 – Kran nur beim Anlegen | Kran immer (`263_5c`) | 1 rot: v640::test_aendern_einer_kranvermietung |

`263_3e` lief zuerst aus dem falschen Grund rot: die Ersetzung selbst war ein Syntaxfehler im Router (Sammelfehler statt FAILED). Neu ändert sie
nur die Art der Rückfrage und ist rot aus dem richtigen Grund (`test_leer_werden_fragt_zurueck_und_aendert_nichts`).

Ohne eigene Gegenprobe: „die Stunden bleiben“ (Nr. 1) -- das Kürzen fasst `PlanningSlotCapacity` nicht an, der Test hält es fest; „kein Hinweis, kein Zähler“
(Nr. 2) -- kein Weg meldet einen leeren Tag, `test_leerer_tag_zaehlt_nirgends` hält es fest; die Kapazität eines ganz leeren Einsatzes (Nr. 2) rechnet die
Verteilung wie bisher (seit 1.9.261 je Tag), `test_ganz_leer_mit_stunden_meldet_die_kapazitaet` hält es fest; der Kran-Termin teilt sich (Folge der Tage, unverändert seit
1.9.241). Die Klicktest-Gegenproben zur Rückfrage im Browser kommen mit 1.9.264 (`klicktest_plantafel_tage`).

## 1.9.264 (Punkt 5): die Tafel zeigt die Besetzung je Tag

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Tage je Person im Dialog | ohne den Knopf (`264_1a`) | 1 rot: v664::test_dialog_zeile_mit_tagen |
| Nr. 1 – Tage je Person im Dialog | ohne den Knopf (`264_1d`, Klicktest Tage) | rot: plantafel_tage (Dialog; Dialog) |
| Nr. 1 – alle gewählt heißt „alle Tage“ | Liste bleibt (`264_1b`) | 1 rot: v664::test_dialog_tage_je_person_und_zeitraum |
| Nr. 1 – ein umgeschalteter Tag geht mit | nicht als geändert vermerkt (`264_1e`, Klicktest Tage) | rot: plantafel_tage (Dialog; Kolonnen) |
| Nr. 1 – Zeitraum: nur die Tage darin | ohne (`264_1c`) | 1 rot: v664::test_dialog_tage_je_person_und_zeitraum |
| Nr. 2 – je Stück ein Balken | ein Balken über den Zeitraum (`264_2a`) | 1 rot: v664::test_kolonne_mit_luecke_und_namen_je_stueck |
| Nr. 2 – je Stück ein Balken | ein Balken über den Zeitraum (`264_2d`, Klicktest Tage) | rot: plantafel_tage (Kolonnen; Kolonnen; 1280) |
| Nr. 2 – Vornamen je Stück | alle Vornamen (`264_2b`) | 1 rot: v664::test_kolonne_mit_luecke_und_namen_je_stueck |
| Nr. 2 – Vornamen je Stück | alle Vornamen (`264_2e`, Klicktest Tage) | rot: plantafel_tage (Kolonnen) |
| Nr. 2 – ganz leer „niemand“ | ohne (`264_2c`) | 1 rot: v664::test_ohne_abschnitte_ein_balken_und_ganz_leer_niemand |
| Nr. 2 – ganz leer „niemand“ | ohne (`264_2f`, Klicktest Tage) | rot: plantafel_tage (Leer) |
| Nr. 3 – Personen je Folge | der ganze Einsatz (`264_3a`) | 1 rot: v664::test_person_je_folge_ihrer_tage |
| Nr. 3 – Personen je Folge | der ganze Einsatz (`264_3b`, Klicktest Tage) | rot: plantafel_tage (Personen; Personen) |
| Nr. 4 – Warnung am Stück | an jedem Stück (`264_4a`) | 1 rot: v664::test_warnung_am_stueck_ihrer_tage |
| Nr. 4 – Warnung am Stück | an jedem Stück (`264_4c`, Klicktest Tage) | rot: plantafel_tage (Kolonnen) |
| Nr. 4 – die Warnzeile nennt die Tage | ohne (`264_4b`) | 1 rot: v664::test_warnung_nennt_ihre_tage |
| Nr. 5 – doppelt je Tag | alle Tage des Einsatzes (`264_5a`) | 1 rot: v664::test_doppelt_je_tag |
| Nr. 5 – doppelt je Tag | alle Tage des Einsatzes (`264_5b`, Klicktest Tage) | rot: plantafel_tage (Personen) |
| Nr. 6 – der Titel nennt die Tage | ohne (`264_6a`) | 1 rot: v664::test_titel_nennt_die_tage_je_person |
| 1.9.263 Nr. 4 – die Seite fragt (im Browser) | leerFrage antwortet nie (`264_7a`, Klicktest Tage) | rot: plantafel_tage (Leer; nicht neu geladen (#planner), Anfragen {"gestartet"; Leer; nicht neu gelad) |

Ohne eigene Gegenprobe: „Ziehen eines Stücks verschiebt den ganzen Einsatz“ (Nr. 2) -- `verschieben()` unverändert seit 1.9.249, der Versatz rechnet vom Beginn
des Einsatzes.
