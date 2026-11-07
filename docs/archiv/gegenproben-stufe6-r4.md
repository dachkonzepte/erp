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

## 1.9.244 (Punkt 0b): Tests und Doku ohne echte Personalnummern

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – keine echte Nummer in einer versionierten Datei | eine echte Nummer zurück in `tests/test_v626_lohndatei.py` (`244_1`) | 1 rot: v644::test_keine_echte_personalnummer_in_einer_versionierten_datei |
| Nr. 1 – auch das LIESMICH zählt | LIESMICH nicht gelesen (`244_1b`) | 1 rot: v644::test_echte_nummern_aus_den_dateien |
| Nr. 2 – nie die Nummer, nur Datei, Zeile, Kennung | Fundstelle mit der Nummer statt der Kennung (`244_2`) | 1 rot: v644::test_fundstellen_nennen_nie_die_nummer |

Ohne Gegenprobe: Nr. 2 „nur lokal“ (ohne den Ordner übersprungen -- das zeigt der Lauf auf einem Rechner ohne `lohn_echt`), Nr. 3 (Arbeitsweise), 0e
(reine Doku). Kein Marker unter `app/` nach den Läufen.

## 1.9.245 (Punkt 0c): Schnellauftrag in einer Transaktion

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ein Commit | `auftrag_nach_aufwand()` wieder mit Commit unterwegs (`245_1a`) | 4 rot: v645 (ein Commit, Auftrag scheitert, Folgeauftrag, Wartung) |
| Nr. 1 – bei einem Fehler bleibt nichts | ohne `rollback()` beim Fehler (`245_1b`) | 1 rot: v645::test_scheitert_der_auftrag_bleibt_nichts |
| Nr. 2 – Folgeauftrag mit dem Verweis am Befund | Schnellauftrag dort für sich festgeschrieben (`245_2a`) | 1 rot: v645::test_folgeauftrag_aus_einem_befund_ein_commit_und_bei_fehler_nichts |
| Nr. 2 – Wartung durchführen mit dem Vertrag | Schnellauftrag dort für sich festgeschrieben (`245_2b`) | 1 rot: v645::test_wartung_durchfuehren_vorgang_und_vertrag_in_einem_commit |

Kein Marker unter `app/` nach den Läufen.

## 1.9.246 (Punkt 0d): test_v224 auf den Tag der App-Uhr

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Werkzeug Nr. 1 – Daten auf „heute“ der App über `berlin_today()` | ein Einsatz wieder auf `date.today()`, Lauf mit `--wanduhr "2026-11-10 10:00"` (`246_1`) | 1 rot: v224::test_individual_path_returns_todays_assignment (mit --wanduhr "2026-11-10 10:00") |

Kein Marker unter `app/` nach den Läufen (die Gegenprobe ändert nur den Test).

## 1.9.247 (Punkt 1): die Tafel „Kolonnen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – umgezogen | `ds-seite` am body entfernt (`247_1a`) | 1 rot: v441::test_umgezogen_heisst_ds_seite_am_body |
| Nr. 1 – Menü mit Einstellungen der Planung | Eintrag entfernt (`247_1b`) | 1 rot: v647::test_seitenkopf_mit_einsatz_und_menue |
| Nr. 2 – ein Paar zählt einmal | Schlüssel je Einsatz (`247_2a`) | 1 rot: v647::test_zaehler_ein_paar_zaehlt_einmal (zuerst ein Sammelfehler durch den Marker mitten in der Zeile -- neu gefasst) |
| Nr. 2 – Filter | jeder Balken bleibt (`247_2b`, Klicktest) | rot: klicktest_plantafel_tafel „Filter: nur Einsätze mit Warnung oder Hinweis“ |
| Nr. 3 – Sa/So schmal | Wochenende so breit wie ein Arbeitstag (`247_3`) | 1 rot: v647::test_spuren_und_geometrie |
| Nr. 4 – „(KF)“ | ohne (`247_4a`) | 1 rot: v647::test_zeilen_der_kolonnen |
| Nr. 4 – kein Antrag in der Zeile der Kolonne | Anträge mitgezählt (`247_4b`) | 1 rot: v647::test_zeilen_der_kolonnen |
| Nr. 4 – „Ohne Kolonne“ immer | nur mit Einsatz (`247_4c`) | 1 rot: v647::test_zeilen_der_kolonnen |
| Nr. 4 – Geräte nach Namen | Reihenfolge des Servers (`247_4d`) | 1 rot: v647::test_zeilen_der_kolonnen |
| Nr. 5 – Kranvermietung nicht in „Ohne Kolonne“ | mitgezählt (`247_5a`) | 1 rot: v647::test_zeilen_der_kolonnen |
| Nr. 5 – je Folge der Tage ein Balken | immer der ganze Einsatz (`247_5b`) | 1 rot: v647::test_geraet_an_einzelnen_tagen_je_folge |
| Nr. 6 – vorläufig gestrichelt | immer „fest“ (`247_6a`, Klicktest) | rot: klicktest_plantafel_tafel „Balken: Zeile, Text, Art, Hinweis“ |
| Nr. 6 – Kranvermietung blau | ohne Klasse (`247_6b`, Klicktest) | rot: klicktest_plantafel_tafel „Balken: Zeile, Text, Art, Hinweis“ |
| Nr. 6 – abgeschlossen blass | ohne Klasse (`247_6c`, Klicktest Konflikte) | rot: klicktest_plantafel_konflikte „Abgeschlossen: Balken sagt es“ |
| Nr. 7 – Spuren | alles in Spur 0 (`247_7`) | 1 rot: v647::test_spuren_und_geometrie |
| Nr. 8 – title beginnt mit dem Text | ohne den Text vorn (`247_8`, Klicktest) | rot: klicktest_plantafel_tafel „Jeder Text im Balken sichtbar oder im title“ (1440 und 1280 px) |
| Nr. 10 – einklappbar | Knopf ohne Wirkung (`247_10`, Klicktest) | rot: klicktest_plantafel_tafel „Rückstand: eingeklappt“ |
| Nr. 11 – ohne Termine der Einsätze | Bedingung entfernt (`247_11a`) | 1 rot: v647::test_termine_am_geraet_ohne_die_der_einsaetze |
| Nr. 11 – privat „Belegt“ | Titel (`247_11b`) | 1 rot: v647::test_termine_am_geraet_ohne_die_der_einsaetze |
| Nr. 12 – Freistellung | ohne (`247_12a`) | 1 rot: v647::test_abwesenheiten_genehmigt_freistellung_beantragt |
| Nr. 12 – beantragt | ohne (`247_12b`) | 1 rot: v647::test_abwesenheiten_genehmigt_freistellung_beantragt |
| Nr. 12 – Art nur ab Büro – Finanzen | nicht geschwärzt (`247_12c`) | 1 rot: v647::test_abwesenheiten_genehmigt_freistellung_beantragt |
| Nr. 13 – Satz am Knopf | entfernt (`247_13`) | 2 rot: v600 (test_seite_nennt_die_freistellung, test_lange_abwesenheit_in_der_zelle_gekuerzt_mit_tooltip) |
| Nr. 14 – Kontrast | dunkle Termin-Schrift (`247_14`) | 1 rot: v432::test_kontrast_der_pruefpaare_hell_und_dunkel |
| Nr. 15 – „Anfahrt je Tag“ | alter Name (`247_15`) | 1 rot: v414::test_abgelehnte_antworten_sind_lesbar[planning.html …] (zuerst ein Sammelfehler -- Befund: die angepasste Erwartung in v414 hatte selbst einen Syntaxfehler, behoben) |
| Nr. 16 – fällig seit | immer „gültig bis“ (`247_16a`) | 1 rot: v647::test_geraet_mit_pruefung_und_kalender |
| Nr. 16 – Outlook-Kalender | immer ohne (`247_16b`) | 1 rot: v647::test_geraet_mit_pruefung_und_kalender |
| Nr. 17 – Kolonnenführer | immer ohne (`247_17`) | 1 rot: v647::test_kolonne_nennt_vornamen_und_kolonnenfuehrer |
| Nr. 18 – Schulferien getönt | Klasse entfernt (`247_18`) | 1 rot: v647::test_schulferien_nur_zur_anzeige |
| Nr. 19 – eine Abfrage für die Anträge | Abwesenheiten fragen selbst (`247_19`) | 1 rot: v570::test_eine_abfrage_fuer_alle_antraege |

Ohne Gegenprobe: Nr. 9 (entfallene Anzeige, keine Regel mehr da), Nr. 10 „Stand im Browser“ (Bequemlichkeit, `localStorage`). Kein Marker unter `app/` nach den
Läufen.

## 1.9.248 (Punkt 4): der Einsatz-Dialog

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „Kranvermietung anlegen“ im Menü | ausgeblendet (`248_1`, Klicktest) | rot: klicktest_plantafel_dialog „Menü: Kranvermietung anlegen steht im Menü“ |
| Nr. 2 – schreibt nichts | commit statt rollback (`248_2a`) | 5 rot: v648 (test_neu_mit_kapazitaet_und_ohne_spuren, test_aendern_nennt_alle_warnungen_und_laesst_alles, test_kranvermietung_mit_kunde_laesst_kein_projekt_und_keine_nummer, test_zustand_je_person, test_schnittstelle_mit_rolle_und_fehlern) |
| Nr. 2 – beim Ändern nichts, alle Warnungen | Prüfen beim Ändern ausgeschaltet (`248_2b`) | 1 rot: v648::test_aendern_nennt_alle_warnungen_und_laesst_alles |
| Nr. 3 – Rechnung gleich je Person und Tag | immer je Person (`248_3a`) | 2 rot: v648 (test_neu_mit_kapazitaet_und_ohne_spuren, test_aendern_nennt_alle_warnungen_und_laesst_alles) |
| Nr. 3 – Zusatz Anfahrt | ohne (`248_3b`) | 1 rot: v648::test_anfahrt_und_ungleiche_tage_je_person |
| Nr. 3 – Rest nur mit Soll | immer ein Rest (`248_3c`) | 1 rot: v648::test_kranvermietung_mit_kunde_laesst_kein_projekt_und_keine_nummer |
| Nr. 4 – „auch bei …“ | ohne „auch“ (`248_4a`) | 1 rot: v648::test_zustand_je_person |
| Nr. 4 – Art nur ab Büro – Finanzen | immer die Art (`248_4b`) | 1 rot: v648::test_schnittstelle_mit_rolle_und_fehlern |
| Nr. 4 – ganzer Antrag | gekürzt auf den Einsatz (`248_4c`) | 1 rot: v648::test_zustand_je_person |
| Nr. 5 – „vermietet …“ | immer „bei P-…“ (`248_5a`) | 1 rot: v648::test_zustand_je_geraet_und_einzelne_tage |
| Nr. 5 – „nur …“ | immer „alle Tage“ (`248_5b`) | 1 rot: v648::test_zustand_je_geraet_und_einzelne_tage |
| Nr. 6 – Warnungen fragen nur bei Kolonne, Zeitraum, Besetzung, Geräten | fragt immer (`248_6a`, Klicktest Konflikte) | rot: klicktest_plantafel_konflikte „nur Notiz“ |
| Nr. 6 – Speichern prüft zuerst neu | ohne neue Prüfung (`248_6b`, Klicktest Dialog) | rot: klicktest_plantafel_dialog „Kolonne gewechselt und sofort gespeichert“ (dazu Folgeprüfungen) |
| Nr. 7 – eine andere Kolonne schlägt ihre Mitglieder vor | Besetzung bleibt (`248_7`, Klicktest Dialog) | zuerst GRÜN gegen klicktest_plantafel_besetzung (siehe Fund) -- Prüfung im Klicktest Dialog ergänzt, dieselbe Gegenprobe: rot „Neu, Kolonne Süd“ |
| Nr. 7 – Geräte unabhängig von der Besetzung | Geräte nur neu, wenn auch die Besetzung unverändert ist (`248_7b`, Klicktest Dialog) | rot: klicktest_plantafel_dialog „Tom von Hand ab, dann Kolonne Süd“ |
| Nr. 10 – Projekt und Kunde in der Auswahl | ohne (`248_10`) | 1 rot: v564::test_auswahl_nur_offene_auftraege_nur_was_sie_zeigt_eine_abfrage |

Ohne Gegenprobe: Nr. 8 und Nr. 9 (entfallene Anzeige). Kein Marker unter `app/` nach den Läufen.

## 1.9.249 (Punkt 2): die Tafel bedienen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nach dem Ziehen kein Klick | Sperre nicht beachtet (`249_1a`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Maus: … kein Dialog danach“ (dazu „freie Zelle Süd“) |
| Nr. 1 – Sperre endet beim nächsten Drücken | nicht zurückgesetzt (`249_1b`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „nach dem Finger: der nächste Klick öffnet“ |
| Nr. 2 – erst ab 6 px | Schwelle 1 px (`249_2a`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Klick: der Einsatz öffnet sich“ |
| Nr. 2 – Escape bricht ab | Escape ohne Wirkung (`249_2b`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Escape: abgebrochen, nichts verschoben“ |
| Nr. 2 – Escape: das Loslassen öffnet nicht | ohne Sperre (`249_2c`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Escape: abgebrochen, nichts verschoben“ (der Dialog öffnete) |
| Nr. 2 – `touch-action: none` | entfernt (`249_2d`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Finger: Notdienst auf 09.–10.11.“ |
| Nr. 3 – Zeile einer Kolonne | Kolonne nicht gesetzt (`249_3a`) | 1 rot: v649::test_ziehen_je_zielzeile |
| Nr. 3 – „Ohne Kolonne“ | Kolonne bleibt (`249_3b`) | 1 rot: v649::test_ziehen_je_zielzeile |
| Nr. 3 – Person, Gerät: nur Zeitraum | dort ohne Kolonne (`249_3c`) | 1 rot: v649::test_ziehen_je_zielzeile |
| Nr. 3 – Kranvermietung nie mit Kolonne | auch dort (`249_3d`) | 1 rot: v649::test_ziehen_je_zielzeile |
| Nr. 3 – gefasster Tag bleibt unter dem Zeiger | Abstand 0 (`249_3e`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Finger: Notdienst auf 09.–10.11.“ |
| Nr. 3 – die ganze Zeile | `height` statt `min-height` (`249_3f`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Rückfrage beim Ziehen in die Zeile Nord“ |
| Nr. 4 – ohne Änderung keine Anfrage | immer senden (`249_4`) | 1 rot: v649::test_ziehen_je_zielzeile |
| Nr. 5 – Warnungen fragen zurück | ohne Rückfrage (`249_5`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Rückfrage beim Ziehen in die Zeile Nord“ |
| Nr. 6 – Zelle einer Kolonne | ohne Kolonne (`249_6a`) | 1 rot: v649::test_freie_zelle_plant_fuer_zeile_und_tag |
| Nr. 6 – Zelle eines Geräts | ohne Gerät (`249_6b`) | 1 rot: v649::test_freie_zelle_plant_fuer_zeile_und_tag |
| Nr. 6 – Zelle einer Person | ohne Person (`249_6c`) | 1 rot: v649::test_freie_zelle_plant_fuer_zeile_und_tag |
| Nr. 6 – Zelle „Ohne Kolonne“ | mit einer Kolonne (`249_6f`) | 1 rot: v649::test_freie_zelle_plant_fuer_zeile_und_tag |
| Nr. 6 – Klick in die Zelle | ohne Wirkung (`249_6d`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „freie Zelle …“ (alle vier) und „Art Kranvermietung“ |
| Nr. 6 – Tag = Beginn und Ende | Ende wie „+ Einsatz“ (`249_6e`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „freie Zelle Süd am 02.11.“, „freie Zelle Ohne Kolonne am 06.11.“ |
| Nr. 7 – Art wechseln behält die Geräte | Geräte zurückgesetzt (`249_7`, Klicktest Bedienen) | rot: klicktest_plantafel_bedienen „Art Kranvermietung: der Kran bleibt gewählt“ |

Kein Marker unter `app/` nach den Läufen.

## 1.9.250 (Punkt 3): „Personen“ und „Geräte“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Kolonnenführer zuerst | nur nach Namen (`250_1a`) | 1 rot: v650::test_gruppen_doppelt_und_antrag |
| Nr. 1 – jede Person einmal | in jeder Kolonne (`250_1b`) | 1 rot: v650::test_gruppen_doppelt_und_antrag |
| Nr. 1 – „Bauleitung“ = mit Konto | alle unter „Ohne Kolonne“ (`250_1c`) | 1 rot: v650::test_gruppen_doppelt_und_antrag |
| Nr. 2 – geschlossene Aufträge zählen nicht | zählen mit (`250_2a`) | 1 rot: v650::test_gruppen_doppelt_und_antrag |
| Nr. 2 – auf das Bild begrenzt | nicht begrenzt (`250_2b`) | 1 rot: v650::test_gruppen_doppelt_und_antrag |
| Nr. 2 – zusammengefasst | je Paar (`250_2c`) | 1 rot: v650::test_gruppen_doppelt_und_antrag |
| Nr. 2 – nur offene Anträge | auch genehmigte (`250_2d`) | 1 rot: v650::test_gruppen_doppelt_und_antrag |
| Nr. 2 – „doppelt“ rot | ohne Klasse (`250_2e`, Klicktest Personen) | rot: klicktest_plantafel_personen „doppelt“ rot, die übrigen Unterzeilen nicht |
| Nr. 3 – „mit <Kolonne>“ | ohne (`250_3a`, Klicktest Personen) | rot: klicktest_plantafel_personen „Kai: mit Nord …“ |
| Nr. 3 – Kranvermietung nach dem Gerät | „Vermietung“ wie in „Kolonnen“ (`250_3b`, Klicktest Personen) | rot: klicktest_plantafel_personen „Lia: Kranvermietung mit dem Gerät …“ |
| Nr. 4 – nur aktive Konten | auch inaktive (`250_4a`) | 1 rot: v650::test_personen_mit_konto_und_ihre_termine |
| Nr. 4 – privat „Belegt“ außer für den Besitzer | immer der Titel (`250_4b`) | 2 rot: v650::test_personen_mit_konto_und_ihre_termine, test_privat_nur_fuer_den_besitzer_mit_titel |
| Nr. 4 – auch Serienvorkommen | ohne (`250_4c`) | 1 rot: v650::test_personen_mit_konto_und_ihre_termine |
| Nr. 4 – ohne Modul „Kalender“ keine | trotzdem (`250_4d`) | 1 rot: v650::test_ohne_modul_kalender_keine_termine |
| Nr. 4 – der Besitzer sieht den Titel (Schnittstelle) | Router ohne Betrachter (`250_4e`) | 1 rot: v650::test_privat_nur_fuer_den_besitzer_mit_titel |
| Nr. 4 – zweizeilig | einzeilig (`250_4f`, Klicktest Personen) | rot: klicktest_plantafel_personen „Termin zweizeilig“ |
| Nr. 5 – „doppelt“ nennt die Person | ohne (`250_5a`) | 1 rot: v650::test_konflikte_nennen_die_person |
| Nr. 5 – „abwesend“ nennt die Person | ohne (`250_5b`) | 1 rot: v650::test_konflikte_nennen_die_person |
| Nr. 5 – „Antrag offen“ nennt die Person | ohne (`250_5c`) | 1 rot: v650::test_konflikte_nennen_die_person |
| Nr. 5 – die Freistellung nennt die Personen | ohne (`250_5d`) | 1 rot: v650::test_freistellung_nennt_die_personen |
| Nr. 5 – der Balken nur mit den Konflikten der Person | alle des Einsatzes (`250_5e`) | 1 rot: v650::test_balken_einer_person_nur_mit_ihren_konflikten |
| Nr. 5 – im Browser | alle des Einsatzes (`250_5f`, Klicktest Personen) | rot: klicktest_plantafel_personen „Mia …“, „Kai …“, „Nele …“, „Büro – Auftrag …“ |

Kein Marker unter `app/` nach den Läufen.

## 1.9.251 (Punkt 5): Termin aus dem Kran-Postfach

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – der Termin ist ein Knopf | kein Knopf (`251_1a`, Klicktest Kran-Termin) | rot: klicktest_plantafel_kran_termin „Kran: Termine als Knöpfe“ (dazu alle Folgeschritte) |
| Nr. 1 – title nennt den nächsten Schritt | ohne (`251_1b`, Klicktest Kran-Termin) | rot: klicktest_plantafel_kran_termin „Kran: Termine als Knöpfe“ |
| Nr. 2 – Knopf nur beim Einzeltermin | immer (`251_2a`) | 1 rot: v651::test_dialog_des_termins_und_uebernahme |
| Nr. 2 – Serie: keine Übernahme | übernimmt auch sie (`251_2b`) | 1 rot: v651::test_dialog_des_termins_und_uebernahme |
| Nr. 3 – privat ohne Notiz | Titel auch dann (`251_3a`) | 1 rot: v651::test_dialog_des_termins_und_uebernahme |
| Nr. 3 – Anfahrt wie beim Anlegen | Feld nicht in der Übernahme (`251_3e`) | 1 rot: v651::test_pruefen_wie_uebernehmen_ohne_spuren |
| Nr. 3 – Zeitraum gesperrt | frei (`251_3b`, Klicktest Kran-Termin) | rot: klicktest_plantafel_kran_termin „Übernehmen: Kopf, Art fest, Zeitraum und Gerät vom Termin, Notiz“ |
| Nr. 3 – Gerät gesperrt | frei (`251_3c`, Klicktest Kran-Termin) | rot: klicktest_plantafel_kran_termin „Übernehmen: …“ |
| Nr. 3 – Art gesperrt | frei (`251_3d`, Klicktest Kran-Termin) | rot: klicktest_plantafel_kran_termin „Übernehmen: …“ |
| Nr. 4 – Prüfen über den Weg des Termins | über `…/slots/pruefen` (`251_4a`, Klicktest Kran-Termin) | rot: klicktest_plantafel_kran_termin „geprüft über den Weg des Termins, ohne Warnung“ |
| Nr. 4 – der eigene Termin warnt nicht | Termin nicht am Einsatz (`251_4b`) | 2 rot: v651::test_pruefen_wie_uebernehmen_ohne_spuren, test_pruefen_warnt_wie_uebernehmen_und_lehnt_ab_wie_uebernehmen |
| Nr. 4 – dieselben Ablehnungen | ohne Prüfung des Termins (`251_4d`) | 1 rot: v651::test_pruefen_warnt_wie_uebernehmen_und_lehnt_ab_wie_uebernehmen |
| Nr. 4 – nur, was die Übernahme nimmt | alles (`251_4e`) | 1 rot: v651::test_aus_dem_termin_nur_was_die_uebernahme_nimmt |

Ohne eigene Gegenprobe: „nichts wird geschrieben“ -- die Vorschau geht über `einsatz_pruefen()` (rollback, Gegenprobe `248_2a`); `test_v651` zählt
Einsätze, Projekte und Termine davor und danach. Kein Marker unter `app/` nach den Läufen.

## 1.9.252 (Punkt 6): aus der Akte und zurück

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Link der Karte mit Rücksprung | ohne (`252_1a`) | 1 rot: v652::test_akte_fuehrt_mit_ruecksprung_zur_plantafel |
| Nr. 1 – Hauptaktion mit Rücksprung | ohne (`252_1b`) | 1 rot: v652::test_akte_fuehrt_mit_ruecksprung_zur_plantafel |
| Nr. 1 – im Browser | Link ohne Rücksprung (`252_1c`, Klicktest aus der Akte) | rot: klicktest_plantafel_aus_der_akte „Link mit Rücksprung“ (und alle Rücksprünge danach) |
| Nr. 2 – nach dem Dialog zurück | Rücksprung nicht am Dialog (`252_2a`, Klicktest aus der Akte) | rot: klicktest_plantafel_aus_der_akte „gespeichert: zurück in der Akte …“, „abgebrochen …“ |
| Nr. 2 – nur einmal | Ziel bleibt (`252_2b`) | 1 rot: v652::test_zurueck_in_die_akte |
| Nr. 3 – nur ein lokaler Pfad | jedes Ziel (`252_3a`) | 3 rot: v652::test_nur_ein_lokaler_pfad (fremde Seite, //, javascript:) |
| Nr. 3 – nur wenn der Dialog aufging | auch ohne Dialog (`252_3b`) | 1 rot: v652::test_nur_wenn_der_dialog_aufging |

Kein Marker unter `app/` nach den Läufen.
