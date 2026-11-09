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
