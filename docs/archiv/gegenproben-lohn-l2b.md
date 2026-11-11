# Gegenproben zu den Festlegungen der Lohnrunde L2b (ab 1.9.312)

Regel 24 (stehende Regel seit 1.9.210): jede neue Festlegung bekommt in derselben Runde ihre eigene Gegenprobe, je Aussage; wo keine möglich ist, steht sie mit
Begründung in der Tabelle. Ablauf: die Änderung in einer eigenen Arbeitskopie auf dem Stand des Commits, Marker `GEGENPROBE`, die genannten Tests bzw. der
Klicktest, die Datei byte-genau zurück (Prüfsumme). Rot zählt nur ein FAILED, kein ERROR. Herleitung und Umsetzung: Archiv `zeiterfassung-und-abwesenheit.md`,
„Lohn L2b“.

## 1.9.312 (Punkt 0): Korrektur aus L2a

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – inaktive ausgeblendet | `lohnDerListe()` ohne Filter (`312_1a`) | 1 rot: v712::test_js_inaktive_ausblenden |
| Nr. 1 – Vorgabe an | ohne gemerkten Wert gezeigt (`312_1b`) | 1 rot: v712::test_js_inaktive_ausblenden |
| Nr. 1 – eigener Schlüssel | der Schlüssel der Mitarbeiterliste (`312_1c`) | 1 rot: v712::test_js_inaktive_ausblenden |
| Nr. 1 – ein Stand für beide Listen | „Inaktive ausblenden“ zeichnet die Konten nicht neu (`312_1d`) | 1 rot: v712::test_js_inaktive_ausblenden |
| Nr. 1 – die Zahl „n inaktiv“ | alle gezählt (`312_1f`) | 1 rot: v712::test_js_inaktive_ausblenden |
| Nr. 1 – nur Anzeige, auch ohne Recht bedienbar | `lohnregelnNurLesen()` sperrt auch das Kästchen (`312_1e`; Klicktest `312_K3`) | 1 rot: v712::test_seite_aufbau; Klicktest: „Bea: „Inaktive ausblenden“ bleibt bedienbar (nur Anzeige)“ |
| Nr. 1 – inaktive grau | ohne die Farbe (`312_K4`, Klicktest) | Klicktest: „Fin: Kästchen ab -- Ute in beiden Listen, grau“ |
| Nr. 1 – die Lohnstammdaten nennen „active“ | ohne `active` (Vorgabe true, `312_2a`) | 1 rot: v712::test_lohnstammdaten_nennen_aktiv |
| Nr. 2 – 2027 ist der Übertrag der Startwert | 2027 wie jedes Jahr (`312_3a`) | 5 rot: v710::test_anspruch_je_jahr, v712::test_doppelt_bleibt_bis_von_hand_entfernt, test_js_quelle_wie_der_server, test_quelle_je_jahr, test_uebertrag_2027_nur_aus_dem_startwert |
| Nr. 2 – am Anspruch 2027 abgelehnt | 2027 von Hand erlaubt (`312_3b`) | 2 rot: v710::test_anspruch_je_jahr, v712::test_uebertrag_2027_nur_aus_dem_startwert |
| Nr. 2 – die Liste zeigt den Startwert als Übertrag | kein Übertrag aus dem Startwert (`312_3d`) | 1 rot: v712::test_js_anspruch_mit_dem_uebertrag |
| Nr. 2 – das erste Jahr kommt vom Server | `erstes_jahr` 2028 (`312_3e`) | 1 rot: v712::test_uebertrag_2027_nur_aus_dem_startwert |
| Nr. 3 – ab 2028 von Hand frei | auch von Hand abgelehnt (`312_4b`) | 2 rot: v710::test_anspruch_je_jahr, v712::test_uebertrag_2027_nur_aus_dem_startwert |
| Nr. 3 – unter „automatisch“ abgelehnt | automatisch von Hand erlaubt (`312_4a`) | 1 rot: v712::test_uebertrag_2027_nur_aus_dem_startwert |
| Nr. 4 – „Übertrag doppelt – prüfen“ | nie doppelt (`312_5a`) | 1 rot: v712::test_doppelt_bleibt_bis_von_hand_entfernt |
| Nr. 4 – nichts still gelöscht (Speichern) | beim Speichern still geleert (`312_5b`) | 1 rot: v712::test_doppelt_bleibt_bis_von_hand_entfernt |
| Nr. 4 – der Dialog sendet den Übertrag nur von Hand | immer gesendet (`312_K2`, Klicktest) | Klicktest: „Fin: Kai weiter doppelt“ |
| Nr. 5 – der Haken zeigt den Stand | immer leer wie bis 1.9.311 (`312_6a`) | 2 rot: v712::test_js_geprueft_gesendet_nur_wenn_sich_etwas_tut (geprüft, nichts geändert), test_js_geprueft_zeigt_den_stand_und_faellt_bei_aenderung |
| Nr. 5 – ein geänderter Wert nimmt ihn heraus, mit Hinweis | kein Hinweis (`312_6b`) | 3 rot: v712::test_js_geprueft_zeigt_den_stand_und_faellt_bei_aenderung, test_js_geprueft_gesendet_nur_wenn_sich_etwas_tut (zwei Fälle) |
| Nr. 5 – gesendet nur, wenn sich etwas tut | wie bis 1.9.311: angehakt = geprüft (`312_6c`) | 4 rot: v712::test_js_geprueft_gesendet_nur_wenn_sich_etwas_tut (vier Fälle) |
| Nr. 5 – vor dem Senden noch einmal verglichen | ohne den Vergleich (`312_6d`) | 1 rot: v712::test_js_geprueft_gesendet_nur_wenn_sich_etwas_tut (geändert ohne Eingabe-Ereignis) |
| Nr. 6 – Trennlinie in der ersten Spalte | ohne die Linie (`312_7a`) | 1 rot: v712::test_seite_aufbau |
| Nr. 6 – Werte ohne Umbruch | mit Umbruch (`312_K1`, Klicktest) | Klicktest: „Bild 412 hell/dunkel: Anspruch auf einer Zeile“ |
| Nr. 7 – die Seite rechnet wie der Server | die Seite ohne Startwert (`312_3c`) | 2 rot: v712::test_js_anspruch_mit_dem_uebertrag, test_js_quelle_wie_der_server |

25 Gegenproben, alle rot. Ohne eigene Gegenprobe: „Diesen Übertrag entfernen“ (null) -- das Leeren war schon erlaubt (1.9.310), geprüft im Klicktest („Fin:
entfernt“) und in v712::test_doppelt_bleibt_bis_von_hand_entfernt.

## 1.9.313 (Punkt 1): Kategorie „Sonderurlaub“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Kategorie gibt es | ohne Sonderurlaub (`313_1a`) | 6 rot: v713::test_antrag_ohne_art_und_ohne_halben_tag, test_jede_seite_kennt_jede_kategorie (drei Seiten), test_kategorie_und_art, … |
| Nr. 1 – nach Urlaub | hinten (`313_1b`) | 4 rot: v713::test_jede_seite_kennt_jede_kategorie (drei Seiten), test_kategorie_und_art |
| Nr. 1 – kein halber Tag | halber Sonderurlaub erlaubt (`313_1c`) | 1 rot: v713::test_antrag_ohne_art_und_ohne_halben_tag |
| Nr. 2 – die Art „Sonderurlaub“ passt nur zu Sonderurlaub | passt zu jeder Kategorie (`313_2a`) | 2 rot: v713::test_antrag_ohne_art_und_ohne_halben_tag, test_kategorie_und_art |
| Nr. 3 – ohne Zuordnung nicht in der Lohndatei | Sonderurlaub nimmt die Zuordnung von Urlaub (`313_4a`) | 3 rot: v713::test_ohne_zuordnung_nicht_in_der_datei_und_vor_dem_abschluss, test_sperrt_nichts, test_umfang_nichts_und_ein_tag |
| Nr. 3 – die Zuordnung ist leer | vorbelegt U / 8000 (`313_4b`) | 3 rot: dieselben drei |
| Nr. 4 – „Vor dem Abschluss“ nennt die Tage | nicht gemerkt (`313_5a`); die Meldung fehlt (`313_5e`) | 3 rot bzw. 1 rot: v713::test_ohne_zuordnung_nicht_in_der_datei_und_vor_dem_abschluss (u. a.) |
| Nr. 4 – nicht Unbezahlt und Freizeitausgleich | alle genannt (`313_5b`) | 2 rot: v713::test_auch_eine_andere_kategorie_ohne_zuordnung, test_ohne_zuordnung_nicht_in_der_datei_und_vor_dem_abschluss |
| Nr. 4 – nicht bei Export-Umfang „nichts“ | auch „nichts“ gezählt (`313_5c`) | 1 rot: v713::test_umfang_nichts_und_ein_tag |
| Nr. 4 – ohne Namen | mit den Namen (`313_5d`) | 3 rot: v713::test_auch_eine_andere_kategorie_ohne_zuordnung, test_ohne_zuordnung_nicht_in_der_datei_und_vor_dem_abschluss, test_umfang_nichts_und_ein_tag |
| Nr. 4 – sperrt nichts | sperrt die Lohndatei (in `datev_fehlt()`, `313_5f`) | 2 rot: v713::test_ohne_zuordnung_nicht_in_der_datei_und_vor_dem_abschluss, test_sperrt_nichts |
| Nr. 6 – je Art die Kategorie vom Server | ohne Text (`313_7a`); die Seite ohne die Zeile (`313_K2`, Klicktest) | 2 rot: v713::test_arten_mit_kategorie_auch_inaktive, test_kategorie_und_art; Klicktest: „Fin: je Art die Kategorie vom Server“ (u. a.) |
| Nr. 6 – auch inaktive Arten | `alle` übergangen (`313_7b`) | 1 rot: v713::test_arten_mit_kategorie_auch_inaktive |
| Nr. 6 – eine neue Art gleich mit Kategorie | nicht neu geladen (`313_K1`, Klicktest) | Klicktest: „Fin: „Umzug“ mit Kategorie, ohne Neuladen“ |
| Nr. 7 – jede Seite kennt jede Kategorie | Plantafel ohne Sonderurlaub (`313_8a`) | 1 rot: v713::test_jede_seite_kennt_jede_kategorie[planning.html] |

17 Gegenproben, alle rot. Ohne eigene Gegenprobe hier: Nr. 5 „zählt nicht gegen das Urlaubskonto“ -- das Urlaubskonto kommt mit 1.9.315, die Gegenprobe
steht dort; Nr. 8 „keine Migration“ (nichts gebaut, nichts zu prüfen).

## 1.9.314 (Punkt 2): Hinweis Rückfahrt

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Beginn nicht vor dem Arbeitsende (auch genau ab dem Ende) | erst nach dem Ende (`314_1a`) | 2 rot: v714::test_nur_die_fahrzeit_nach_der_letzten_arbeit, test_pruefen_mit_rechten_und_ohne_zahl |
| Nr. 1 – nach der letzten Arbeit | nach der ersten Arbeit (`314_1b`) | 2 rot: dieselben |
| Nr. 1 – der Text des Hinweises | anderer Text (`314_6a`) | 1 rot: v714::test_nur_die_fahrzeit_nach_der_letzten_arbeit |
| Nr. 2 – nicht mit einer Buchung ohne Uhrzeiten | Dauern übergangen (`314_2a`) | 2 rot: v714::test_nur_die_fahrzeit_nach_der_letzten_arbeit, test_pruefen_mit_rechten_und_ohne_zahl |
| Nr. 2 – nicht an einem Tag nur mit Fahrzeit | auch ohne Arbeit (`314_2b`) | 2 rot: dieselben |
| Nr. 2 – nicht Hinfahrt und Fahrt zwischen Baustellen | über `314_1b` (Arbeitsende = erste Arbeit) | siehe dort |
| Nr. 3 – Zeitraum wie die Pausen | ohne den Abschluss (`314_3a`) | 1 rot: v714::test_pruefen_mit_rechten_und_ohne_zahl |
| Nr. 4 – keine Zahl am Reiter | mitgezählt (`314_4a`); Klicktest ohne „Nichts zu prüfen“-Regel (`314_K2`) | 1 rot: v714::test_pruefen_mit_rechten_und_ohne_zahl; Klicktest: „Anna: Karte zur Info, keine Zahl am Reiter dafür“ |
| Nr. 4 – nichts gesperrt | in „Vor dem Abschluss“ (`314_4b`) | 1 rot: v714::test_nichts_abgezogen_nichts_gesperrt |
| Nr. 5 – „Ändern“ nur, wer ändern darf | jeder ändert (`314_5a`); die Seite ohne Bedingung (`314_5b`) | 1 rot: v714::test_pruefen_mit_rechten_und_ohne_zahl; 1 rot: v714::test_seite_zeichnet_den_hinweis |
| Nr. 5 – „Ändern“ öffnet die Buchung | tut nichts (`314_K1`, Klicktest) | Klicktest: „Anna: „Ändern“ öffnet die Buchung“, „Anna: im Dialog die Fahrzeit“ |

12 Gegenproben, alle rot. Ohne eigene Gegenprobe: Nr. 4 „nichts abgezogen“ -- `rueckfahrten()` schreibt nicht (ein GET schreibt nie, Regel 23,
`test_kein_get_schreibt`); geprüft in v714::test_nichts_abgezogen_nichts_gesperrt. Nr. 6 „kein Quittieren“ -- nichts gebaut.

## 1.9.315 (Punkt 3): das Urlaubskonto

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – der Anspruch je Person | immer die Vorgabe (`315_1a`) | 1 rot: v715::test_hinweise |
| Nr. 1 – „Anspruch prüfen“ bei Eintritt/Austritt | kein Hinweis (`315_9a`) | 1 rot: v715::test_hinweise |
| Nr. 2 – Übertrag 2027 = Startwert | ohne Startwert (`315_2a`) | 5 rot: v715::test_ab_2028_von_hand_und_automatisch, test_hinweise, test_offene_antraege, test_schnittstelle_mit_rechten, test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit |
| Nr. 2 – „ohne Übertrag – Startwert folgt“ | kein Hinweis (`315_2b`) | 2 rot: v715::test_hinweise, test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit |
| Nr. 3 – „automatisch“: Rest des Vorjahres | 0 (`315_3a`) | 1 rot: v715::test_ab_2028_von_hand_und_automatisch |
| Nr. 3 – „von Hand“: der Wert am Anspruch | übergangen (`315_3b`) | 1 rot: v715::test_ab_2028_von_hand_und_automatisch |
| Nr. 4 – der doppelte Übertrag zählt nicht | er zählt (`315_4a`) | 2 rot: v715::test_ab_2028_von_hand_und_automatisch, test_hinweise |
| Nr. 5 – nur Urlaub | jede Kategorie (`315_5a`) | 1 rot: v715::test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit |
| Nr. 5 – halber Tag mit Anteil | als ganzer (`315_5b`) | 1 rot: v715::test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit |
| Nr. 5 – Heiligabend zählt nicht | Tage des Arbeitszeitkalenders als ganze Tage gezählt (`315_5c`; der erste Versuch stürzte am fehlenden Anteil ab, neu gefasst) | 6 rot (Zählung, z. B. 12,5 statt 11,5): v715::test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit, test_silvester_frei_zaehlt_nicht, test_offene_antraege, test_hinweise, test_ab_2028_von_hand_und_automatisch, test_schnittstelle_mit_rechten |
| Nr. 6 – heute zählt als vorbei | heute künftig (`315_6a`) | 1 rot: v715::test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit |
| Nr. 7 – nur offene Anträge auf Urlaub | jede Kategorie (`315_7a`); auch entschiedene (`315_7b`) | je 1 rot: v715::test_offene_antraege |
| Nr. 8 – Rest mit Übertrag | ohne Übertrag (`315_8a`) | 5 rot: v715::test_ab_2028_von_hand_und_automatisch, test_hinweise, test_offene_antraege, test_schnittstelle_mit_rechten, test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit |
| Nr. 8 – Rest nach den offenen Anträgen | ohne die Anträge (`315_8b`) | 1 rot: v715::test_offene_antraege |
| Nr. 9 – Verfall vorgemerkt | kein Hinweis (`315_9b`) | 1 rot: v715::test_hinweise |
| Nr. 9 – Rest unter 0 | kein Hinweis (`315_9c`) | 1 rot: v715::test_hinweise |
| Nr. 10 – feste Zahl Abfragen | je Person eine Abfrage (`315_10a`) | 1 rot: v715::test_eine_feste_zahl_abfragen |
| Nr. 11 – Rechte | jeder sieht alle (`315_11a`) | 1 rot: v715::test_schnittstelle_mit_rechten |
| Nr. 11 – vor 2027 nicht | auch vor 2027 (`315_11b`) | 2 rot: v715::test_schnittstelle_mit_rechten, test_vor_2027_nicht |
| Nr. 12 – wer im Konto steht | jede Person der Tagesbilanz (`315_12a`) | 1 rot: v715::test_personen_aktiv_oder_mit_urlaub_im_jahr |

21 Gegenproben, alle rot. Die Regeln der Tagesbilanz selbst (Sollzeit der eigenen Woche, Feiertage, Silvester als ganzer Urlaubstag) sind in 1.9.308
gegengeprobt (`gegenproben-lohn-l2a.md`); hier zählt das Konto ihre Posten.

## 1.9.316 (Punkt 4): das Urlaubskonto auf den Seiten

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Rest minus dieser Urlaub, andere offene Anträge zählen nicht mit | Rest nach den offenen Anträgen (`316_1a`) | 2 rot: v716::test_an_offenen_antraegen, test_rest_danach |
| Nr. 1 – über den Jahreswechsel je Jahr | nur das erste Jahr (`316_1b`) | 2 rot: v716::test_rest_danach, test_rest_danach_schnittstelle_rechte |
| Nr. 1 – vor 2027 nichts | auch vor 2027 (`316_1c`) | 2 rot: dieselben |
| Nr. 1 – „1 Urlaubstag“ | ohne Einzahl (`316_1d`; der erste Versuch zerbrach die Datei -- ERROR, neu gefasst) | 1 rot: v716::test_rest_danach |
| Nr. 2 – nur die eigene Person, Admin und Büro – Finanzen jede | jeder für jeden (`316_2a`); Klicktest: Mia fragt eine andere Person (403) | 1 rot: v716::test_rest_danach_schnittstelle_rechte |
| Nr. 2 – Bis vor Von abgelehnt | angenommen (`316_2b`) | 1 rot: v716::test_rest_danach_schnittstelle_rechte |
| Nr. 3 – an jedem offenen Antrag auf Urlaub | auch an entschiedenen (`316_3a`) | 1 rot: v716::test_an_offenen_antraegen |
| Nr. 3 – auch in „Prüfen“ | nicht in „Prüfen“ (`316_3b`) | 1 rot: v716::test_an_offenen_antraegen |
| Nr. 4 – Inaktive ausgeblendet | ohne Filter (`316_4a`) | 1 rot: v716::test_zeiten_karte_mit_inaktiven |
| Nr. 4 – eigener Schlüssel | der Schlüssel der Mitarbeiterliste (`316_4b`) | 1 rot: v716::test_seiten_aufbau |
| Nr. 4 – Jahre 2027 bis ein Jahr nach dem laufenden | nur das gewählte (`316_4c`) | 1 rot: v716::test_jahre_meine_zeiten_und_rest_2027 |
| Nr. 4 – die Karte lädt mit dem Reiter | lädt nicht (`316_K5`, Klicktest) | Klicktest: „Fin: Abwesenheiten mit Konto“ (und folgende) |
| Nr. 5 – „danach Rest“ nur bei Urlaub | jede Kategorie (`316_K1`, Klicktest Zeiten) | Klicktest: „Fin: Krankheit -- kein Rest“ |
| Nr. 5 – neu bei jeder Änderung im Dialog | Plantafel ohne (`316_K3`); „Meine Zeiten“ ohne (`316_K4`) | Klicktest: „Anna: Plantafel „danach Rest““; „Mia: im Antrag „danach Rest““ |
| Nr. 6 – Meine Zeiten nur das eigene | nicht nur das eigene (`316_6b`; blieb zuerst grün -- die richtige Person stand zufällig vorn, Test um die zweite Person ergänzt, dann rot) | 1 rot: v716::test_jahre_meine_zeiten_und_rest_2027 |
| Nr. 6 – Schlüssel „urlaub“, Datengrenze unverändert | alter Name „urlaubskonto“ (`316_6a`) | 4 rot: v326 (Datengrenze, „skonto“) und v716 |
| Nr. 7 – Spalte „Rest 2027“ | ohne Rest (`316_7a`) | 1 rot: v716::test_jahre_meine_zeiten_und_rest_2027 |
| Nr. 8 – nach dem Genehmigen ohne Neuladen | das Konto nicht mitgeladen (`316_K2`, Klicktest) | Klicktest: „Anna: Toms Zeile ohne Neuladen -- genehmigt 5, Rest 25“ |

19 Gegenproben, alle rot (14 über Tests, 5 über `klicktest_urlaubskonto`).

## 1.9.317 (Nachrunde, Punkt A): Lohndatei vollständig

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – sperrt die Lohndatei | nicht in `datev_fehlt()` (`317_1a`; Klicktest `317_K1`) | 3 rot: v713::test_ohne_zuordnung_nicht_in_der_datei_und_vor_dem_abschluss, test_sperrt_die_lohndatei_nicht_den_abschluss, v717::test_sperrt_wie_eine_fehlende_personalnummer; Klicktest: „Anna: „Vor dem Abschluss“ nennt Sonderurlaub ohne Zuordnung“, „Anna: Fehlt mit der Zuordnung, Zeile mit Weg“ |
| Nr. 1 – nicht den Abschluss | sperrt auch den Abschluss (`317_1b`) | 2 rot: v713::test_sperrt_die_lohndatei_nicht_den_abschluss, v717::test_sperrt_wie_eine_fehlende_personalnummer |
| Nr. 2 – nicht Unbezahlt und Freizeitausgleich | auch sie sperren (`317_2a`) | 2 rot: v717::test_in_der_auslieferung_ohne_zuordnung, test_sperrt_wie_eine_fehlende_personalnummer |
| Nr. 2 – nicht bei Export-Umfang „nichts“ | auch „nichts“ (`317_2b`) | 1 rot: v717::test_export_umfang_nichts_sperrt_nicht |
| Nr. 2 – eine Art mit eigener Zuordnung geht vor | die Zuordnung der Art übergangen (`317_2c`) | 1 rot: v717::test_sperrt_wie_eine_fehlende_personalnummer |
| Nr. 3 – der Zusatz „– keine Lohndatei, bis die Zuordnung steht“ | ohne Zusatz (`317_3a`) | 5 rot: v713 (drei Tests), v717 (zwei Tests) |
| Nr. 3 – einmal je Kategorie in „Vor dem Abschluss“ | doppelt (`317_3b`) | 1 rot: v717::test_sperrt_wie_eine_fehlende_personalnummer |
| Nr. 3 – „Fehlt: n Zuordnungen“ | ohne Zahl (`317_3c`) | 1 rot: v717::test_sperrt_wie_eine_fehlende_personalnummer |
| Nr. 4 – ohne Zuordnung ausgeliefert: Sonderurlaub und Fortbildung | Fortbildung mit Zuordnung (`317_4a`) | 2 rot: v717::test_in_der_auslieferung_ohne_zuordnung, test_sperrt_wie_eine_fehlende_personalnummer |
| Nr. 5 – Vorprobe September/Oktober Byte für Byte gleich | die Zuordnung der Art übergangen, Vorprobe September (`317_5a`, Skript) | rot: keine Datei („Kein DATEV-Export: Fortbildung ohne Zuordnung: 16 Tage …“) |

11 Gegenproben, alle rot (9 über Tests, eine über den Klicktest, eine über die Vorprobe).

## 1.9.318 (Nachrunde, Punkt B): „Meine Zeiten“ ohne Startwert

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – das Konto in „Meine Zeiten“ zeigt den Hinweis | die Karte ohne Hinweise (`318_2a`; Klicktest `318_K2`) | 1 rot: v716::test_meine_zeiten_eigenes_konto; Klicktest: „Tom 412 hell/dunkel: das Konto mit dem Hinweis“ |
| Nr. 2 – „danach Rest“ mit „ · ohne Übertrag – Startwert folgt“ | kein Hinweis (`318_1a`; Klicktest `318_K1`) | 4 rot: v716::test_an_offenen_antraegen, test_rest_danach_schnittstelle_rechte, v718::test_danach_rest_mit_dem_hinweis, test_im_antrag_von_meine_zeiten; Klicktest: „Tom 412 hell/dunkel: im Antrag „danach Rest“ mit dem Hinweis“ |
| Nr. 3 – nicht mit Startwert | immer (`318_1b`) | 3 rot: v716::test_rest_danach, test_rest_danach_schnittstelle_rechte, v718::test_danach_rest_mit_dem_hinweis |
| Nr. 3 – nicht ab 2028 | nach dem Startwert auch ab 2028 (`318_1c`) | 1 rot: v718::test_danach_rest_mit_dem_hinweis |

6 Gegenproben, alle rot (4 über Tests, 2 über `klicktest_urlaubskonto`).

## 1.9.319 (Nachrunde, Punkt C): „danach Rest“ mit den anderen offenen Anträgen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – beim Stellen mit weiteren offenen Anträgen der Zusatz | ohne Zusatz (`319_1a`; Klicktest `319_K1`) | 1 rot: v719::test_mit_weiteren_offenen; Klicktest: „Fin: Tom -- mit den anderen offenen Anträgen“ |
| Nr. 1 – ohne weitere offene Anträge kein Zusatz | auch ohne (`319_1b`) | 2 rot: v719::test_ohne_weitere_offene_kein_zusatz, test_mit_weiteren_offenen |
| Nr. 2 – m = Rest nach den offenen Anträgen minus dieser Urlaub | ohne diesen Urlaub (`319_1d`) | 1 rot: v719::test_mit_weiteren_offenen |
| Nr. 3 – nicht beim Genehmigen | auch beim Genehmigen (`319_1c`) | 1 rot: v719::test_beim_genehmigen_nicht |
| Nr. 4 – vor dem Hinweis „ohne Übertrag – Startwert folgt“ | der Hinweis vorn (`319_1e`) | 1 rot: v719::test_mit_weiteren_offenen |

6 Gegenproben, alle rot (5 über Tests, eine über `klicktest_urlaubskonto`). Dass Sonderurlaub, entschiedene Anträge und Anträge eines anderen Jahrs nicht
zählen, ist die Regel „beantragt“ des Kontos (1.9.315, Gegenproben 315_7a/b); v719 prüft es hier mit.
