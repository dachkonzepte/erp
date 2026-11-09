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

## 1.9.277 (Punkt 0b): Verschieben in Arbeitstagen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – in Arbeitstagen | Abbild in Kalendertagen (`277_1a`) | 10 rot: v677 (Abbildung, freier Tag, Umsetzen beider Arten, ganzer Einsatz, einzelne Tage, Wochenende, freier Zieltag, andere Kolonne, API) |
| Nr. 1 – auch beim Umsetzen | Umsetzen in Kalendertagen (`277_1b`) | 2 rot: v677::test_umsetzen_in_arbeitstagen, v677::test_umsetzen_eines_geraets |
| Nr. 2 – ein freier Tag geht im Arbeitstag davor auf | Abstand zählt auch freie Tage (`277_2a`) | 3 rot: v677::test_freier_tag_nur_ausdruecklich, v677::test_ein_wochenende_im_einsatz_wird_nicht_mitgezogen, v677::test_ausdruecklich_auf_einen_freien_tag |
| Nr. 2 – der Zieltag darf frei sein | ein freier Zieltag rückt weiter (`277_2b`) | 2 rot: v677::test_ausdruecklich_auf_einen_freien_tag, v677::test_freier_tag_nur_ausdruecklich |
| Nr. 3 – „alle Tage“ nur an allen Tagen | immer „alle Tage“ (`277_3a`) | 5 rot: v677 (ganzer Einsatz, einzelne Tage, Wochenende, freier Zieltag, andere Kolonne) |
| Nr. 3 – neue Mitglieder an den Abbildern | neue Mitglieder an allen Tagen (`277_3b`) | 1 rot: v677::test_in_eine_andere_kolonne |
| Nr. 4 – fragt bei jeder Warnung | fragt nicht (`277_4a`) | 1 rot: v677::test_fragt_bei_jeder_warnung_des_einsatzes |
| Nr. 4 – die Tafel schickt `…/verschieben` | wieder PUT (`277_4b`) | 1 rot: v649::test_ziehen_je_zielzeile |
| Nr. 4 – Rückgängig nur unverändert | ohne Prüfung des Stands (`277_4c`) | 1 rot: v677::test_rueckgaengig_stellt_den_stand_wieder_her |
| Nr. 4 – Rückgängig stellt wieder her | stellt nichts her (`277_4d`) | 1 rot: v677::test_rueckgaengig_stellt_den_stand_wieder_her |

Alle 10 im ersten Lauf rot. Ohne Gegenprobe: Nr. 5 (der Dialog bleibt in Kalendertagen -- nichts daran geändert, belegt durch
v677::test_dialog_bleibt_in_kalendertagen und die Tests des Dialogs). Im Browser: die Klicktests mit Ziehen (`plantafel_bedienen`, `plantafel_ziehen`,
`plantafel_konflikte`, `plantafel_besetzung`) liefen grün; sie ziehen innerhalb einer Woche, eine eigene Gegenprobe im Browser hat Nr. 1 nicht (die Anfrage der
Tafel prüft v649 in node).

## 1.9.278 (Punkt 0c): Untermenü der Stammdaten unter 1400 px oben

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – unter 1400 px oben | die Regel wieder erst unter 850 px (`278_1a`) | 2 rot: v678::test_untermenue_unter_1400_px_oben, v678::test_unter_850_px_wie_bisher |
| Nr. 1 – im Browser | ebenso (`278_1b`, Klicktest) | rot: stammdaten_breite -- „1400: Untermenü oben“, bei 1280 px hell und dunkel Untermenü, Rollen, Status und Bearbeiten, E-Mail zweizeilig, ohne Silbentrennung |
| Nr. 2 – Telefonnummer ohne Umbruch | ohne `white-space:nowrap` (`278_2a`) | 1 rot: v678::test_telefonnummer_ohne_umbruch |
| Nr. 2 – im Browser | ebenso (`278_2b`, Klicktest) | im ersten Lauf GRÜN -- mit den Testdaten ist die Spalte Kontakt bei 1440, 1280 und 412 px breit genug, die Nummer bricht auch ohne die Regel nicht. Klicktest nachgezogen (die Spalte eng gezwungen, „eng (Kontakt 60 px): Telefonnummern einzeilig“), dieselbe Gegenprobe: rot -- „eng (Kontakt 60 px)“ |
| Nr. 3 – unter 850 px wie bisher | ohne `overflow-wrap:normal` für die E-Mail (`278_3a`) | 1 rot: v678::test_unter_850_px_wie_bisher |

Alle 5 rot (`278_2b` nach dem Nachziehen des Klicktests).

## 1.9.279 (Punkt 1): Auftragsliste der Woche und „1 Woche“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – eingeplante oben | nur nach Nummer (`279_1a`) | 1 rot: v679::test_alle_offenen_eingeplante_oben |
| Nr. 1 – nur offene | auch abgeschlossene und stornierte (`279_1b`) | 1 rot: v679::test_alle_offenen_eingeplante_oben |
| Nr. 1 – nach ihrem ersten Tag im Zeitraum | erster Tag des Einsatzes, auch vor dem Zeitraum (`279_1c`) | 1 rot: v679::test_alle_offenen_eingeplante_oben |
| Nr. 2 – gebucht = Baustelle & Werkstatt | jede gebuchte Zeitart (`279_2a`) | 1 rot: v679::test_stunden_wie_die_akte |
| Nr. 2 – „Soll“, solange nichts gebucht ist | immer „Rest“ (`279_2b`) | 2 rot: v679::test_stunden_wie_die_akte, v679::test_stunden_zeile |
| Nr. 2 – Vorrang der Kranvermietung | Wartungsvertrag vor Kran (`279_2c`) | 1 rot: v679::test_stunden_zeile |
| Nr. 3 – „vorläufig“, wenn einer vorläufig ist | nur, wenn alle vorläufig sind (`279_3a`) | 1 rot: v679::test_vorlaeufig_und_pausiert |
| Nr. 3 – „pausiert“ | ohne (`279_3b`) | 1 rot: v679::test_vorlaeufig_und_pausiert |
| Nr. 3 – „ab <Tag>“ | immer „ohne Termin“ (`279_3c`) | 1 rot: v679::test_alle_offenen_eingeplante_oben |
| Nr. 4 – feste Zahl Abfragen | Positionen je Auftrag nachgeladen (`279_4a`) | 1 rot: v679::test_feste_zahl_abfragen |
| Nr. 4 – ab Büro – Auftrag | ohne Rollenprüfung (`279_4b`) | 1 rot: v679::test_api_und_rolle |
| Nr. 5 – „1 Woche“ | nicht in der Auswahl (`279_5a`) | 1 rot: v679::test_auswahl_mit_einer_woche_und_merken |
| Nr. 5 – jede Ansicht merkt sich ihren Zeitraum | merkt nichts (`279_5b`) | 1 rot: v679::test_jede_ansicht_merkt_sich_ihren_zeitraum |
| Nr. 5 – „Aufträge“ 1 Woche, sonst 2 | ohne Vorgabe für „Aufträge“ (`279_5c`) | 2 rot: v679::test_vorgaben_je_ansicht, v679::test_jede_ansicht_merkt_sich_ihren_zeitraum |
| Nr. 5 – neu laden nur bei anderer Zahl der Tage | lädt immer (`279_5d`) | 1 rot: v679::test_wechsel_laedt_nur_bei_anderer_zahl_der_tage |

Alle 15 im ersten Lauf rot. Ohne Gegenprobe im Browser: die Tafel zeigt in 1.9.279 noch keine Ansicht mit der Liste (ab 1.9.280 im Klicktest
`plantafel_auftraege`); „die gezeigte Woche bleibt“ (Nr. 5) beschreibt, was bleibt (`periodStart` unberührt).

## 1.9.280 (Punkt 2): Ansicht „Aufträge“, Kurzname am Gerät

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Leerzeichen am Rand weg, leer = kein Kurzname | ohne Bereinigung (`280_1a`) | 1 rot: v680::test_kurzname_anlegen_und_aendern_als_teil_update |
| Nr. 1 – `PUT /api/resources/{id}` als Teil-Update | `model_dump()` ohne `exclude_unset` (`280_1b`) | 1 rot: v680::test_kurzname_anlegen_und_aendern_als_teil_update |
| Nr. 1 – höchstens 30 Zeichen | ohne Grenze (`280_1c`) | 1 rot: v680::test_kurzname_anlegen_und_aendern_als_teil_update |
| Nr. 1 – im Stammdaten-Formular | Formular schickt ihn nicht (`280_1d`) | 1 rot: v680::test_stammdaten_formular_mit_kurzname |
| Nr. 2 – Kran am Typ (enthält „Kran“) | nur genau „Kran“ (`280_2a`) | 2 rot: v680::test_kran_am_typ[Autokran], [kran] |
| Nr. 2 – eigenes Zeichen am Chip | Kran mit dem Zeichen eines Geräts (`280_2b`, `280_2c`) | 1 rot: v680::test_karte_mit_chips_am_tag; Klicktest auftraege: „Wasserturm Fr mit Kai und Kran“, „Kranvermietung Fr“, „Kran mit eigenem Zeichen in der Liste“ |
| Nr. 3 – nur „Aufträge“ lädt die Auftragsliste | jede Ansicht lädt sie (`280_3a`) | 1 rot: v680::test_reiter_legende_und_laden_nur_in_auftraege |
| Nr. 3 – der Name öffnet die Akte des Auftrags | Link nur auf das Projekt (`280_3b`) | Klicktest auftraege: „Name verlinkt die Akte“ |
| Nr. 3 – Abschnitte „Eingeplant in …“ | Titel ohne Woche (`280_3c`) | Klicktest auftraege: „Zeilen“ |
| Nr. 4 – „niemand“ an einem Tag ohne jemanden | nie „niemand“ (`280_4a`, `280_4d`) | 1 rot: v680::test_karte_mit_chips_am_tag; Klicktest auftraege: „Wasserturm Mi“ |
| Nr. 4 – Chips nur der Personen dieses Tags | alle Personen des Einsatzes (`280_4b`) | 1 rot: v680::test_karte_mit_chips_am_tag |
| Nr. 4 – Klick auf die Karte öffnet den Einsatz | Klick tut nichts (`280_4c`, `280_4e`) | 1 rot: v680::test_reiter_legende_und_laden_nur_in_auftraege; Klicktest auftraege: „Klick auf die Karte öffnet den Einsatz“ |
| Nr. 5 – ⚠ nur am betroffenen Chip | jeder Konflikt an jedem Chip des Tags (`280_5b`, `280_5c`) | 2 rot: v680::test_karte_mit_chips_am_tag, ::test_karte_vorlaeufig_kran_und_hinweis; Klicktest auftraege: „Wasserturm Fr …“, „Wartung Do“, „Kranvermietung Fr“ |
| Nr. 5 – … und nur an seinem Tag | Konflikt an jedem Tag (`280_5a`) | 1 rot: v680::test_karte_mit_chips_am_tag |
| Nr. 6 – ab 2 Wochen schmalere Chips | immer der ganze Name (`280_6a`, `280_6b`) | 1 rot: v680::test_ab_zwei_wochen_schmale_chips_mit_name_im_title; Klicktest auftraege: „2 Wochen“ |
| Nr. 7 – abwesend | genehmigte Abwesenheit nicht erkannt (`280_7a`) | 1 rot: v680::test_wochenleiste |
| Nr. 7 – abwesend ohne Art | mit Art (`280_7b`) | 1 rot: v680::test_wochenleiste |
| Nr. 7 – doppelt | Gerät nie doppelt (`280_7c`, `280_7d`) | 1 rot: v680::test_wochenleiste; Klicktest auftraege: „Wochenleiste Kran“ |
| Nr. 8 – Filter nur mit Warnung oder Hinweis | Filter zeigt alle (`280_8a`) | Klicktest auftraege: „Filter“ |
| Nr. 9 – downgrade entfernt die Spalte | downgrade ohne Wirkung (`280_9a`) | 2 rot: v680::test_migration_sqlite, ::test_migration_postgresql |

Alle 26 rot (17 gegen Tests, 9 gegen den Klicktest), jede Datei byte-genau zurück, kein Marker geblieben. Ein erster Lauf auf dem Stand mit der Klasse `.a-karte`
war ebenfalls ganz rot; wiederholt nach der Umbenennung in `.a-einsatz` (v460: ein Name mit „karte“ verlangt die Ecke der Karte). Ohne eigene Gegenprobe: Nr. 3
„vierter Reiter“ (Aufbau, v647 prüft die Reiter), Nr. 7 „Kolonnen mit Mitgliedern und Geräten“ (Anzeige, im Klicktest „Kolonnen in der Liste“ und im Bild),
Nr. 9 „bestehende Geräte ohne Kurznamen“ (nach `280_9a` belegt die Migrationsprobe den leeren Wert).

## 1.9.281 (Punkt 3): Ziehen in „Aufträge“ mit Maus und Finger

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – auf einer Karte genau dieser Einsatz (`slot_id`) | ohne `slot_id` (`281_1a`) | 1 rot: v681::test_aus_der_liste_tag_setzen |
| Nr. 1 – Person, Kolonne oder Gerät | Kolonne mit falschem Feld (`281_1b`) | 1 rot: v681::test_aus_der_liste_tag_setzen |
| Nr. 1 – für diesen Auftrag | anderer Auftrag (`281_1c`) | Klicktest auftraege_ziehen: „Frei“, „nur Do mit verlängern“ und 16 weitere |
| Nr. 2 – auf einer Karte in genau diesen Einsatz (`ziel_slot_id`) | ohne `ziel_slot_id` (`281_2a`) | 1 rot: v681::test_aus_der_zelle_umsetzen_oder_herausnehmen |
| Nr. 2 – an den eigenen Platz zurück: nichts | sendet trotzdem (`281_2b`) | 1 rot: v681::test_aus_der_zelle_umsetzen_oder_herausnehmen |
| Nr. 2 – umsetzen statt dazu | aus der Zelle `tag-setzen` (`281_2c`) | Klicktest auftraege_ziehen: „Umsetzen: keine Rückfrage“ und 15 weitere |
| Nr. 3 – auf die Liste gezogen: herausnehmen | nichts (`281_3a`, `281_3d`) | 1 rot: v681::test_aus_der_zelle_umsetzen_oder_herausnehmen; Klicktest: „Liste: Lia herausgenommen“, „Finger: Nele auf die Liste“ u. a. |
| Nr. 3 – angetippt die Leiste | kein Menü (`281_3b`, `281_3e`) | 1 rot: v681::test_chips_mit_dem_finger_greifbar_ohne_textauswahl; Klicktest: „Kai angetippt: Leiste“, „Finger: angetippt“ u. a. |
| Nr. 3 – Antippen öffnet den Einsatz nicht | Karte öffnet auch nach dem Antippen (`281_3c`, `281_3f`) | 1 rot: v680::test_reiter_legende_und_laden_nur_in_auftraege; Klicktest: „Antippen öffnet den Einsatz nicht“ u. a. |
| Nr. 4 – der eigene Einsatz zählt nicht als „woanders“ | zählt mit (`281_4a`) | 1 rot: v681::test_anzeige_frei_und_schon_woanders |
| Nr. 4 – „Antrag offen – plant ohne Rückfrage“ | Antrag offen als „Frei“ (`281_4b`) | 1 rot: v681::test_anzeige_antrag_abwesend_und_geraet |
| Nr. 4 – ganze Kolonne: wer schon woanders ist | nie woanders (`281_4c`) | 1 rot: v681::test_anzeige_ganze_kolonne |
| Nr. 4 – „Abwesend – Rückfrage …“ | ohne (`281_4d`) | 1 rot: v681::test_anzeige_antrag_abwesend_und_geraet |
| Nr. 4 – auch am Gerät | Gerät nie woanders (`281_4e`) | 1 rot: v681::test_anzeige_antrag_abwesend_und_geraet |
| Nr. 4 – die Liste als Ziel umrandet | nicht umrandet (`281_4f`) | Klicktest: „Liste: Ziel markiert“ |
| Nr. 4 – ohne Anfrage beim Ziehen | eine Anfrage je Bewegung (`281_4g`) | Klicktest: „Frei: keine Anfrage beim Ziehen“ |
| Nr. 5 – Rückfrage bei neuer Warnung | ohne Konflikt-Dialog (`281_5b`, `281_5c`) | 1 rot: v681::test_rueckfragen_nacheinander_gelten_zusammen; Klicktest: „Woanders: Rückfrage“, „Kolonne: eine Rückfrage“ u. a. |
| Nr. 5 – die Antworten gelten zusammen (erst Warnung, dann „niemand mehr“) | „niemand mehr“ vergisst „Trotzdem planen“ (`281_5a`) | im ersten Lauf GRÜN; Test nachgezogen (umgekehrte Reihenfolge), dieselbe Gegenprobe: 1 rot: v681::test_rueckfragen_nacheinander_gelten_zusammen |
| Nr. 5 – … (erst „niemand mehr“, dann Warnung) | „Trotzdem planen“ vergisst „Behalten“ (`281_5d`) | 1 rot: v681::test_rueckfragen_nacheinander_gelten_zusammen |
| Nr. 6 – verlängern ab ihrem letzten Tag | ab dem Tag des Zugs (`281_6a`) | im ersten Lauf GRÜN; Test nachgezogen (sie steht danach schon an weiteren Tagen), dieselbe Gegenprobe: 1 rot: v681::test_danach_verlaengern_und_rueckgaengig |
| Nr. 6 – Rückgängig einmal | bleibt nach dem Rückgängig (`281_6b`) | 1 rot: v681::test_danach_verlaengern_und_rueckgaengig |
| Nr. 6 – Rückgängig nur mit Umkehrung | auch ohne (`281_6c`) | 1 rot: v681::test_danach_verlaengern_und_rueckgaengig |
| Nr. 6 – „<Name> · nur <Tage>“ | „am …“ (`281_6d`) | Klicktest: „nur Do mit verlängern“, „verlängert: Leiste“, „Umsetzen: Leiste“, „Finger: Leiste“ |
| Nr. 6 – verlängern nur mit Tagen danach | immer (`281_6e`) | Klicktest: „Umsetzen: Leiste“, „Finger: Leiste“ |
| Nr. 6 – die übrigen Tage mit Zustand | ohne (`281_6f`) | Klicktest: „nur Do mit verlängern“ und vier weitere |
| Nr. 7 – Chips mit `touch-action:none` | ohne (`281_7a`, `281_7d`) | 1 rot: v681::test_chips_…; Klicktest: sechs Prüfungen „Finger“ |
| Nr. 7 – keine Textauswahl | ohne `user-select:none` (`281_7e`) | Klicktest: „Frei: nichts markiert, der Chip über dem Zeiger“ |
| Nr. 7 – bei grobem Zeiger mindestens 40 px | ohne (`281_7b`, `281_7f`) | 1 rot: v681::test_chips_…; Klicktest: „Finger: Chips greifbar“ |
| Nr. 7 – Escape bricht ab | ohne (`281_7c`, `281_7g`) | 1 rot: v681::test_chips_…; Klicktest: „Escape: Anzeige weg“ |
| Nr. 7 – die Kopie über dem Zeiger | unter dem Zeiger (`281_7h`) | Klicktest: „Frei: nichts markiert, der Chip über dem Zeiger“ |
| Nr. 8 – der Knopf heißt wie die Liste | immer „Nicht eingeplant“ (`281_8a`, `281_8c`) | 1 rot: v681::test_knopf_und_hinweis_je_ansicht; Klicktest: „Finger: Liste eingeklappt, Knopf …“ |
| Nr. 8 – eigener Hinweis unter der Tafel | ohne Wechsel (`281_8b`) | 1 rot: v681::test_knopf_und_hinweis_je_ansicht |

40 Gegenproben (23 gegen Tests, 17 gegen den Klicktest), alle rot -- `281_5a` und `281_6a` erst nach dem nachgezogenen Test (Regel 24); jede Datei byte-genau
zurück, kein Marker geblieben. Ohne eigene Gegenprobe: Nr. 1 „sonst entscheidet der Server“ (die Entscheidung dazu/verlängert/neu prüft v667 seit 1.9.267), Nr. 6
„bis zur nächsten Aktion“ (die Leiste schließt beim nächsten Ziehen, belegt durch „Frei: die Leiste ist beim Ziehen zu“).

## 1.9.282 (Punkt 4): Leiste „Rückgängig“ über der Tafel, Klick in einen freien Tag

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – der Zug in Worten (Verschieben: alter → neuer Zeitraum) | ohne den alten Zeitraum (`282_1a`, `282_1f`) | 2 rot: v682::test_verschieben_zeigt_die_leiste, ::test_ohne_umkehrung_kein_rueckgaengig; Klicktest rueckgaengig: „Kolonnen: Leiste“ |
| Nr. 1 – „Rückgängig“ mit der Umkehrung der Antwort | Umkehrung nie gemerkt (`282_1b`, `282_1g`) | 2 rot: v682::test_verschieben_zeigt_die_leiste, ::test_rueckgaengig_schickt_die_umkehrung_und_schliesst; Klicktest rueckgaengig: 11 Prüfungen (Kolonnen, Personen, Geräte, JS-Fehler) |
| Nr. 1 – andere Zeile „Name → Name“ | immer wie die eigene Zeile (`282_1c`) | 1 rot: v682::test_umsetzen_in_der_eigenen_und_einer_anderen_zeile |
| Nr. 1 – Rückgängig einmal | die Leiste bleibt nach „Rückgängig“ (`282_1d`) | 1 rot: v682::test_rueckgaengig_schickt_die_umkehrung_und_schliesst |
| Nr. 1 – nur mit Umkehrung | Knopf auch ohne (`282_1e`) | 1 rot: v682::test_ohne_umkehrung_kein_rueckgaengig |
| Nr. 2 – der nächste Klick außerhalb schließt | kein Schließen beim Klick (`282_2a`, `282_2d`) | 1 rot: v682::test_leiste_schliesst_mit_der_naechsten_aktion; Klicktest rueckgaengig: „Personen: ein Klick auf die Seite schließt die Leiste“ u. a. |
| Nr. 2 – beim Klick, nicht schon beim Drücken | Schließen bei `pointerdown` (`282_2f`, `282_2g`) | 1 rot: v682::test_leiste_schliesst_mit_der_naechsten_aktion; Klicktest plantafel_ziehen: der zweite Zug in „Personen“ und „Geräte“ landet in der falschen Zeile (1440 und 1280 px, hell und dunkel) -- so im ersten Lauf vor dem Commit, als die Leiste noch beim Drücken schloss |
| Nr. 2 – eine andere Ansicht schließt | `setView()` ohne (`282_2b`, `282_2e`) | 1 rot: v682::test_leiste_schliesst_mit_der_naechsten_aktion; Klicktest rueckgaengig: „Geräte: eine andere Ansicht schließt die Leiste“ |
| Nr. 2 – ein anderer Zeitraum schließt | `movePeriod()` ohne (`282_2c`) | 1 rot: v682::test_leiste_schliesst_mit_der_naechsten_aktion |
| Nr. 3 – Rückfragen gelten zusammen (auch beim Ziehen in „Personen“) | „niemand mehr“ vergisst „Trotzdem planen“ (`282_3a`) | im ersten Lauf GRÜN (der Test fragte nur „niemand mehr“ zuerst); Test nachgezogen (umgekehrte Reihenfolge), dieselbe Gegenprobe: 1 rot: v682::test_ziehen_in_personen_fragt_nacheinander |
| Nr. 4 – Klick in einen freien Tag: nur dieser Tag | ohne `bis` (`282_4a`, `282_4c`) | 1 rot: v682::test_klick_in_einen_freien_tag_in_auftraege; Klicktest: im ersten Lauf GRÜN (der Tag gehörte zu einem eingeplanten Auftrag, dort schlägt der Dialog ohnehin nur den Tag vor); Klicktest mit einem nicht eingeplanten Auftrag nachgezogen, dieselbe Gegenprobe: „Aufträge: für diesen Auftrag, nur diesen Tag, ohne Kolonne“ |
| Nr. 4 – eine Karte öffnet ihren Einsatz | Klick auf die Karte öffnet auch den Dialog für einen neuen (`282_4b`, `282_4d`) | 1 rot: v682::test_klick_in_einen_freien_tag_in_auftraege; Klicktest rueckgaengig: „Aufträge: eine Karte öffnet ihren Einsatz“ |
| Nr. 5 – in „Aufträge“ keine Leiste über der Tafel | auch dort (`282_5a`) | Klicktest auftraege_ziehen: „Frei: keine Leiste über der Tafel“ |

20 Gegenproben (12 gegen Tests, 8 gegen Klicktests), alle rot -- `282_3a` und `282_4c` erst nach dem nachgezogenen Test bzw. Klicktest (Regel 24). Weil die
Leiste danach beim Klick statt beim Drücken schließt (der erste Lauf vor dem Commit fand das Rücken der Tafel), alle 20 noch einmal auf dem endgültigen Stand,
dazu `282_2f`/`282_2g` für genau diese Aussage; jede Datei byte-genau zurück, kein Marker geblieben.
