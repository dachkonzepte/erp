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
