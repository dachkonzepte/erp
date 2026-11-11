# Gegenproben zu den Festlegungen der Lohnrunde L2a (ab 1.9.308)

Regel 24 (stehende Regel seit 1.9.210): jede neue Festlegung bekommt in derselben Runde ihre eigene Gegenprobe, je Aussage; wo keine möglich ist, steht sie mit
Begründung in der Tabelle. Ablauf: die Änderung in einer eigenen Arbeitskopie auf dem Stand des Commits, Marker `GEGENPROBE`, die genannten Tests bzw. der
Klicktest, die Datei byte-genau zurück (Prüfsumme). Rot zählt nur ein FAILED, kein ERROR. Herleitung und Umsetzung: Archiv `zeiterfassung-und-abwesenheit.md`,
„Lohn L2a“.

## 1.9.308 (Punkt 1): die Tagesbilanz

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Feiertag als Posten nur mit Sollzeit | auch ohne Sollzeit (`308_1c`) | 1 rot: v708::test_ein_tag_mit_allem (Sa 26.12.) |
| Nr. 1 – Schlechtwetter = Soll − Arbeit | nur die Sollzeit (`308_1d`) | 1 rot: v708::test_ein_tag_mit_allem |
| Nr. 2 – die Fahrzeit getrennt | keine Fahrzeit (`308_1a`) | 1 rot: v708::test_ein_tag_mit_allem |
| Nr. 2 – die Arbeit ohne Fahrzeit | mit Fahrzeit (`308_1b`) | 1 rot: v708::test_ein_tag_mit_allem |
| Nr. 3 – unabhängig vom Export-Umfang | Posten nach dem Umfang „nichts“ weggelassen (`308_2a`) | 1 rot: v708::test_unabhaengig_von_umfang_und_zuordnung |
| Nr. 4 – eine feste Zahl Abfragen | je Abwesenheit eigene Abfragen (`308_3a`) | 1 rot: v708::test_eine_feste_zahl_abfragen |
| Nr. 5 – die Lohndatei rechnet über die Tagesbilanz | die Arbeit der Bilanz um 0,25 h verfälscht (`308_4a`); dasselbe gegen die Vorprobe September (`308_4b`, von Hand) | 9 rot: v626::test_azubi_mehrarbeit, test_ein_monat_einer_person, test_eintritt_und_kaufmaennisch, test_format_kopf_und_reihenfolge, test_leere_zuordnung_keine_zeile_und_null_stunden, test_mehrarbeit_hoechstens_die_arbeit, test_mehrarbeit_ohne_kennzeichen_bleibt_arbeit, test_monatszeile_zuletzt, test_schnittstelle; Vorprobe: die Datei weicht ab |
| Nr. 6 – eine Regel für Abwesenheitstage und Kalendertage | `abwesenheit_tage()` nimmt die Kalendertage des Aufrufers nicht (`308_5a`) | 1 rot: v708::test_eine_regel_fuer_abwesenheitstage_und_kalendertage |

9 Gegenproben (8 gegen Tests, 1 gegen die Vorprobe), alle rot; jede Datei byte-genau zurück, kein Marker geblieben. „Byte für Byte gleich“ (Nr. 5) ist
der Nachweis selbst: die Vorprobe September und Oktober (Muster) und die lokale Oktober-Datei aus echten Buchungen auf 1.9.307 und auf diesem Stand --
dieselben SHA-256. Kein Klicktest (keine Oberfläche).

## 1.9.309 (Punkt 2): Sperre nach dem Abschluss für Abwesenheiten und Ausfalltage

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – im abgeschlossenen Zeitraum nur der Admin, jeder Weg | keine Sperre (`309_1a`, `309_1f`, `309_1g`) | 7 rot: v709::test_buero_finanzen_im_abschluss_gesperrt[antrag], [plantafel], [sammel], [schlechtwetter], test_geschaeftslogik_sperrt_ohne_angabe, test_kolonnenfuehrer_schlechtwetter_eintragen_und_bestaetigen, test_monteurin_und_buero_auftrag_fuer_sich; Klicktests: klicktest_zeiten „Fin: im abgeschlossenen Zeitraum …“ (3 Prüfungen), klicktest_schlechtwetter „Fin: im abgeschlossenen Zeitraum …“ (2 Prüfungen) |
| Nr. 1 – … beim Anlegen | das Anlegen ohne Sperre (`309_1b`) | 4 rot: v709::test_buero_finanzen_im_abschluss_gesperrt[antrag], [plantafel], test_geschaeftslogik_sperrt_ohne_angabe, test_monteurin_und_buero_auftrag_fuer_sich |
| Nr. 1 – … beim Genehmigen | das Genehmigen ohne Sperre (`309_1c`) | 2 rot: v709::test_geschaeftslogik_sperrt_ohne_angabe, test_kolonnenfuehrer_schlechtwetter_eintragen_und_bestaetigen |
| Nr. 1 – … beim Löschen | das Löschen ohne Sperre (`309_1d`) | 1 rot: v709::test_geschaeftslogik_sperrt_ohne_angabe |
| Nr. 2 – ablehnen bleibt frei | auch das Ablehnen gesperrt (`309_2a`) | 1 rot: v709::test_kolonnenfuehrer_schlechtwetter_eintragen_und_bestaetigen |
| Nr. 3 – eine Regel: der Admin darf | auch der Admin nicht (`309_3a`) | 7 rot: v709::test_admin_auch_im_abschluss[antrag], [plantafel], [sammel], [schlechtwetter], test_eine_regel_fuer_zeiten_und_abwesenheiten, test_kolonnenfuehrer_schlechtwetter_eintragen_und_bestaetigen, test_offenen_antrag_zurueckziehen_frei_genehmigen_nur_admin |
| Nr. 4 – jeder Router gibt die Rolle mit | die Plantafel ohne Rolle (`309_4a`) | 2 rot: v709::test_buero_finanzen_im_abschluss_gesperrt[plantafel], test_jeder_router_gibt_die_rolle_mit |
| Nr. 5 – die Meldung | eine andere Meldung (`309_5a`, `309_5b`) | 6 rot: v709::test_buero_finanzen_im_abschluss_gesperrt[antrag], [plantafel], [sammel], [schlechtwetter], test_kolonnenfuehrer_schlechtwetter_eintragen_und_bestaetigen, test_monteurin_und_buero_auftrag_fuer_sich; Klicktest: klicktest_zeiten „Fin: im abgeschlossenen Zeitraum die Meldung …“ |
| Nr. 5 – beim Sammeleintrag einmal statt je Person | ohne die Prüfung vorweg (`309_5c`) | 1 rot: v709::test_buero_finanzen_im_abschluss_gesperrt[sammel] (422 mit der Meldung je Person statt 403) |
| Nr. 5 – beim Ausfalltag vor jeder anderen Prüfung | ohne die Prüfung vorweg (`309_1e`, `309_1h`) | 2 rot: v709::test_buero_finanzen_im_abschluss_gesperrt[schlechtwetter], test_kolonnenfuehrer_schlechtwetter_eintragen_und_bestaetigen (422 statt 403); Klicktest: klicktest_schlechtwetter „Fin: im abgeschlossenen Zeitraum die Meldung, keine Rückfrage“ |

14 Gegenproben (10 gegen Tests, 4 gegen Klicktests), alle rot; jede Datei byte-genau zurück, kein Marker geblieben. Ohne eigene Gegenprobe: „zurückziehen
bleibt frei“ (Nr. 2, zweiter Teil) -- `cancel_request()` prüft nichts und wurde nicht angefasst (der Test `test_offenen_antrag_zurueckziehen_frei_genehmigen_nur_admin`
hält es fest).

## 1.9.310 (Punkt 3): Urlaubsanspruch und Startwerte

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Verfall „TT.MM.“, nicht der 29.02. | geprüft gegen ein Schaltjahr (`310_1a`) | 1 rot: v710::test_vorgaben_lesen_und_teil_update -- im ersten Lauf GRÜN, siehe unten |
| Nr. 1 – Vorgabe 30 Tage im Bestand | die Migration mit 25 (`310_1b`) | 2 rot: v710::test_migration_auf_einem_bestand_sqlite, …_postgresql |
| Nr. 2 – Tage in halben Schritten | ganz beliebige Tage (`310_2a`) | 3 rot: v710::test_anspruch_je_jahr, test_startwert_mit_herkunft_und_pruefung, test_vorgaben_lesen_und_teil_update |
| Nr. 2 – leer = die Vorgabe | ohne Vorgabe (`310_2b`) | 1 rot: v710::test_anspruch_je_jahr |
| Nr. 2 – Verfallsdatum im Jahr des Anspruchs | in jedem Jahr (`310_2c`) | 1 rot: v710::test_anspruch_je_jahr |
| Nr. 3 – Saldo mit höchstens zwei Stellen | drei Stellen erlaubt (`310_3a`) | 1 rot: v710::test_startwert_mit_herkunft_und_pruefung |
| Nr. 4 – ein geänderter Wert verliert die Prüfung | die Prüfung bleibt (`310_4a`, `310_4b`) | 1 rot: v710::test_startwert_mit_herkunft_und_pruefung; Klicktest: „Fin: die Prüfung ist weg“ |
| Nr. 5 – Admin und Büro – Finanzen alle, sonst die eigenen | jeder sieht alle (`310_5a`, `310_5b`) | 1 rot: v710::test_wer_sieht_und_aendert_was; Klicktest: „Bea: nur die eigene Zeile“ |
| Nr. 6 – Startwert nach dem Januar nur der Admin | nie gesperrt (`310_6a`, `310_6b`) | 1 rot: v710::test_startwert_nach_dem_januar_nur_der_admin; Klicktest: „Fin: Startwert gesperrt mit Hinweis …“ |
| Nr. 7 – für Büro – Auftrag geschwärzt | nicht geschwärzt (`310_7a`) | 1 rot: v710::test_historie_mit_namen_und_fuer_buero_auftrag_geschwaerzt |
| Nr. 8 – ein Lesepfad legt nichts an | das Lesen legt Ansprüche an (`310_8a`) | 1 rot: v710::test_anspruch_je_jahr |
| Nr. 9 – downgrade() bricht ab, solange etwas eingetragen ist | ohne Prüfung (`310_9a`) | 2 rot: v710::test_migration_auf_einem_bestand_sqlite, …_postgresql |
| Nr. 11 – zuerst das laufende Jahr, frühestens 2027 | das laufende Jahr (2026) (`310_11a`, `310_11b`) | 1 rot: v710::test_vorgaben_lesen_und_teil_update; Klicktest: „Fin: Vorgaben 30 Tage …“ (Kopf „Urlaub 2026“), „Fin: Titel, Jahre …“ |

17 Gegenproben (13 gegen Tests, 4 gegen den Klicktest), alle rot; jede Datei byte-genau zurück, kein Marker geblieben. 310_1a war im ersten Lauf GRÜN: die
Gegenprobe nahm die eigene Prüfung auf den 29.02. weg -- den Tag lehnt aber schon das Jahr der Prüfung ab (2027, kein Schaltjahr). Die eigene Prüfung war
doppelt; sie ist entfallen, die Stelle sagt jetzt, warum 2027, und die Gegenprobe prüft gegen ein Schaltjahr -- rot. Ohne eigene Gegenprobe: Nr. 3 Herkunft
und Bemerkung (feste Liste im Code, im Test geprüft), Nr. 10 (Ort auf der Seite, im Klicktest und in `test_seite_block_und_dialog`).
