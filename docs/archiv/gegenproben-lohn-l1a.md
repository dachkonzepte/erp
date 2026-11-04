# Gegenproben zu den Festlegungen der Lohnrunde L1a (1.9.166–1.9.191)

Vorgabe Tobias (04.11.2026, L1a Stufe 3, Punkt 5): für jede Festlegung von 1.9.166 bis 1.9.191 eine Gegenprobe nach Regel 24, in Blöcken je
Versionsbereich, je Block eine Version und ein Commit. Wo keine Gegenprobe möglich ist (reine Doku, reine Anzeige ohne Prüfung), keine erfinden,
sondern mit Begründung aufführen. Bleibt eine Gegenprobe grün, ist das ein Befund wie bei 1.9.169 Nr. 2 (Nachtrag 1.9.173): fehlenden Test
nachziehen, dann dieselbe Gegenprobe noch einmal.

Ablauf je Block: eine eigene Arbeitskopie (Stand 1.9.194 mit 1.9.192–1.9.194), in der nichts anderes lief (Regel 24); je Aussage einer Festlegung
eine Änderung mit Marker `GEGENPROBE`, die Tests des Themas, die Datei danach byte-genau zurück (Prüfsumme). Gezählt ist nur FAILED aus dem
geprüften Grund, nie ERROR. Neue Tests nur in einer neuen Datei je Block. Die Dateien ALT/NEU und die Protokolle der Läufe lagen im Scratchpad
der Runde (nicht im Repo); die Tabellen unten nennen je Gegenprobe Datei und Änderung, sodass sie sich nachstellen lässt. Je Block steht oben,
wie viele Festlegungen, Gegenproben, sofort rot, Befunde und ohne Gegenprobe; darunter Tabelle, Befunde und Bemerkungen.

## 1.9.197: Festlegungen 1.9.166–1.9.169

23 Festlegungen (1.9.166 Nr. 1–4, 1.9.167 Nr. 1–6, 1.9.168 Nr. 1–5, 1.9.169 Nr. 1–7, Werkzeug 1.9.166 Nr. 1), 48 Gegenproben, 39 sofort rot,
9 grün -> Befunde an 6 Festlegungen, 7 neue Tests in `tests/test_v604_festlegungen_166_169.py`, danach alle 48 rot. Ohne Gegenprobe: die
Werkzeug-Festlegung und 8 Teilaussagen (in der Tabelle mit Grund). Migrationsproben nur unter SQLite.

| Festlegung | Gegenprobe | Ergebnis |
|---|---|---|
| **1.9.166 Nr. 1a** – Minuten über der Schwelle abgerundet (6:00 h + 40 s -> 0) | `work_time_models.py::_minuten_ueber()` ROUND_FLOOR -> ROUND_CEILING (`166_1a`) | 1 rot: `test_v584::test_sekunden_und_vier_stellen` |
| **1.9.166 Nr. 1b** – kleinster Wert, unter 6,00 h nie (je Regel höchstens die Minuten darüber) | `pflichtpause()` ohne Deckel: volle Pause, sobald die Schwelle überschritten ist (`166_1b`) | 18 rot: `test_v584::test_pflichtpause_lesart_a[6:01-1, 6:15-15, 6:20-20, 9:01-30, 9:15-30, 9:30-30, 9:40-40]`, `::test_waechst_nie_schneller_als_die_anwesenheit`, `::test_sekunden_und_vier_stellen`, `::test_beispiel_tobias_0715_bis_1330`, `::test_letzte_buchung_nimmt_die_fehlende_pause_ganz_auf` ×5, `::test_spaetere_zeit_zuerst_wie_am_stueck`, `::test_alte_buchung_heisst_jetzt_passt_nicht`, `test_v104::test_work_time_models_and_automatic_break_on_timer` |
| **1.9.166 Nr. 1c** – unter 9,00 h schon (9:15 h -> 30 min, 8,75 h) | `pflichtpause()` nur die höchste überschrittene Regel (= alter Wortlaut „nie unter die Schwelle“, 9:15 -> 15) (`166_1c`) | 3 rot: `test_v584::test_pflichtpause_lesart_a[9:01-30]`, `[9:15-30]`, `::test_waechst_nie_schneller_als_die_anwesenheit` |
| **1.9.166 Nr. 2a** – Dauer braucht die volle Pause, sobald die Arbeitszeit über der Schwelle liegt (6,25 -> 30, 9,25 -> 45) | `fehlende_pause()` = Pflichtpause der Anwesenheit − abgezogen (alte Rechnung) (`166_2a`) | 2 rot: `test_v584::test_fehlende_pause_einer_dauer[6.25-0-30]`, `::test_dauer_6_25_sagt_gleich_30` |
| **1.9.166 Nr. 2b** – die Zahl ist dieselbe wie unter „Prüfen“ | `time_tracking.py::dauer_vorschau()` „noetig“ = `nach_zeitregel` (ohne „fehlt“) (`166_2b`) | 1 rot: `test_v584::test_dauer_6_25_sagt_gleich_30` |
| **1.9.166 Nr. 2c** – die Meldung nennt diese Zahl (Dialog „Neue Buchung“) | `zeiten.html`: „passt danach nicht (nach Zeitregel …)“ mit 0 statt `v.noetig` (`166_2c`) | 1 rot: `test_v527::test_dialog_dauer_vorschau_text` |
| **1.9.166 Nr. 2d** – ebenso je Person in „Kolonne buchen“ | `zeiten.html`: 0 statt `m.noetig` (`166_2d`) | 1 rot: `test_v527::test_kolonne_vorschau_text` |
| **1.9.166 Nr. 3a** – Lesart A für jede Pausenregel, auch selbst angelegte | `pflichtpause()`: Lesart A nur für die Schwellen 6 und 9 h, jede andere Regel volle Pause (`166_3a`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_selbst_angelegte_pausenregeln_nach_lesart_a` |
| **1.9.166 Nr. 3b** – Schwellen und Pausen je Modell einstellbar | `_regeln()` fest 6 h/30, 9 h/45 statt der Regeln des Modells (`166_3b`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_selbst_angelegte_pausenregeln_nach_lesart_a` |
| **1.9.166 Nr. 4a** – kein Stichtag | `automatic_break_minutes_for_duration()`: vor dem 10.11.2026 die alte Regel (`166_4a`) | 8 rot: `test_v584::test_alte_buchung_heisst_jetzt_passt_nicht` (dazu die übrigen sieben Buchungstests am 09.11.: `test_beispiel_tobias…`, `test_letzte_buchung…` ×5, `test_spaetere_zeit…`) |
| **1.9.166 Nr. 4b** – alte Buchungen bleiben, wie gebucht; neu gerechnet nur auf Klick | `_pausen_stand()` („Prüfen“) bucht die neue Pause gleich (flush) (`166_4b`) | 1 rot: `test_v584::test_alte_buchung_heisst_jetzt_passt_nicht` |
| **1.9.166 Nr. 4c** – „passt nicht“ sperrt den Abschluss | `time_backoffice.py::abschluss_hindernisse()` ohne `unpassende_pausen()` (`166_4c`) | 6 rot: `test_v512::test_unpassende_pause_sperrt_den_abschluss`, `::test_beides_in_einer_liste`, `::test_nur_ab_dem_bisherigen_abschluss`, `::test_ohne_bisherigen_abschluss_der_monat_des_datums`, `test_v527::test_tag_nur_aus_dauern_sperrt_den_abschluss`, `::test_bestehende_dauern_bleiben_unveraendert` |
| 1.9.166 Nr. 4, Satz „auf dem Server gibt es keine echten Buchungen, die das träfe“ | keine – Aussage über den Bestand des Servers, nicht über Code | – |
| **1.9.167 Nr. 1a** – ohne eigene Werte Tarif auch für Azubis | `sollzeit.py::tarif()`: Funktion „Auszubildende/r“ ohne Sollzeit (`167_1a`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_tarif_auch_fuer_azubis_und_aushilfen` |
| **1.9.167 Nr. 1b** – ebenso für Aushilfen | `tarif()`: unter 30 Wochenstunden die Wochenstunden / 5 (`167_1b`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_tarif_auch_fuer_azubis_und_aushilfen` |
| **1.9.167 Nr. 2** – eigene Werte ändern sich nicht mit der Kalenderwoche | `soll_zeitraum()`: eigene Werte in KW 49–17 −0,5 h wie der Tarif (`167_2`) | 1 rot: `test_v585::test_teilzeit_di_bis_do_und_zurueck_zum_tarif` |
| **1.9.167 Nr. 3a** – „gültig ab“ nach „Abgeschlossen bis“ | `zeile_anlegen()` ohne Sperre (`167_3a`) | 1 rot: `test_v585::test_sollzeit_nie_im_abgeschlossenen_zeitraum` |
| **1.9.167 Nr. 3b** – Löschen ebenso | `zeile_loeschen()` ohne Sperre (`167_3b`) | 1 rot: `test_v585::test_sollzeit_nie_im_abgeschlossenen_zeitraum` |
| **1.9.167 Nr. 3c** – Eintritt und Austritt prüfen den Abschluss nicht | `set_employee_payroll()` lehnt Eintritt/Austritt bis „Abgeschlossen bis“ ab (`167_3c`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_eintritt_und_austritt_auch_im_abgeschlossenen_zeitraum` |
| 1.9.167 Nr. 3, Satz „der abgelegte Export (L1b) hält fest, was abgerechnet ist“ | keine – L1b nicht gebaut | – |
| **1.9.167 Nr. 4a** – eine Änderung am Modell gilt auch rückwirkend | `save_model()` lehnt Änderungen ab, solange ein Zeitraum abgeschlossen ist (`167_4a`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_modellaenderung_gilt_auch_im_abgeschlossenen_zeitraum` |
| **1.9.167 Nr. 4b** – die Seite sagt, erst nach dem Abschluss der Monate davor zu ändern | `settings.html`: Hinweis über den Arbeitszeitmodellen entfernt (`167_4b`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_seite_sagt_modell_erst_nach_dem_abschluss_aendern` |
| **1.9.167 Nr. 5** – Formular „Zeitregeln“ ändern nur Admin und Büro – Finanzen | `routers/time_backoffice.py`: `PUT /api/time-backoffice/settings` mit `_role_dep` (ab Büro – Auftrag) (`167_5`) | 2 rot: `test_v585::test_buero_auftrag_liest_nur`, `test_v109::test_time_backoffice_router_fully_uses_shared_dependency` |
| **1.9.167 Nr. 6** – Sollzeit mit zwei Nachkommastellen | `soll_zeitraum()` ohne `round_hours()` (`167_6`) | 1 rot: `test_v585::test_teilzeit_di_bis_do_und_zurueck_zum_tarif` („7.5000“ statt „7.50“) |
| **1.9.168 Nr. 1a** – höchstens 5 Ziffern | `personalnummer_gueltig()` bis 6 Ziffern (`168_1a`) | 1 rot: `test_v586::test_personalnummer_nur_ziffern[123456]` |
| **1.9.168 Nr. 1b** – ohne führende Null | `personalnummer_gueltig()` mit führender Null (`168_1b`) | 1 rot: `test_v586::test_personalnummer_nur_ziffern[0]` |
| 1.9.168 Nr. 1, Satz „falls DATEV längere Nummern nimmt … zu klären mit LB2“ | keine – offene Frage, kein Verhalten | – |
| **1.9.168 Nr. 2a** – bei „DATEV-Nr. = ERP-Nr.“ gilt das Format für die ERP-Nummer | Prüfung der ERP-Nummer übergangen (`168_2a`) | 1 rot: `test_v586::test_gleichsetzung_mit_erp_nummer` |
| **1.9.168 Nr. 2b** – mit „nichts“ bleibt sie speicherbar | Prüfung auch bei „nichts“ (`168_2b`) | 1 rot: `test_v586::test_gleichsetzung_mit_erp_nummer` |
| **1.9.168 Nr. 2c** – „solange von der Person etwas in die Datei geht“: auch „nur Abwesenheiten“ | Prüfung nur beim Umfang „alles“ (`168_2c`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_gleichsetzung_nur_abwesenheiten_verlangt_das_format` |
| **1.9.168 Nr. 3a** (neu gefasst 1.9.177) – eine Nummer bleibt dauerhaft gesperrt | `personalnummer_gesperrt()` immer frei (`168_3a`) | 3 rot: `test_v593::test_nummernwechsel_sperrt_die_alte_nummer`, `::test_nach_austritt_und_geleerter_nummer_gesperrt`, `::test_gleichsetzung_sperrt_die_mitarbeiternummer` |
| **1.9.168 Nr. 3b** – nur dieselbe Person bekommt sie wieder | gesperrt auch für dieselbe Person (`168_3b`) | 2 rot: `test_v593::test_nummernwechsel_sperrt_die_alte_nummer` (422, im Test KeyError am Körper der 422), `::test_gleichsetzung_sperrt_die_mitarbeiternummer` (409 statt 200) |
| **1.9.168 Nr. 3c** – auch nach Austritt | frei, sobald die Person, der sie gehörte, einen Austritt hat (`168_3c`) | 1 rot: `test_v593::test_nach_austritt_und_geleerter_nummer_gesperrt` |
| **1.9.168 Nr. 3d** – auch nach einem Nummernwechsel (die alte bleibt gemerkt) | `set_employee_payroll()` merkt die Nummer nicht (`168_3d`) | 6 rot: `test_v593::test_nummernwechsel_sperrt_die_alte_nummer`, `::test_nach_austritt_und_geleerter_nummer_gesperrt`, `::test_pruefskript_nennt_die_gemerkten_nummern`, `test_v595::test_admin_gibt_eine_fruehere_nummer_frei`, `::test_nur_der_admin`, `::test_eine_getragene_nummer_bleibt` |
| **1.9.168 Nr. 4** – „nur Abwesenheiten“ wirkt im heutigen Export wie „nichts“ | `exportiert_arbeit()` auch bei „abwesenheiten“ (`168_4`) | 1 rot: `test_v586::test_export_umfang[abwesenheiten-False]` |
| 1.9.168 Nr. 4, Satz „mit L1b stehen dann U, K … in der Datei“ | keine – L1b nicht gebaut | – |
| **1.9.168 Nr. 5a** – die Migration bricht bei einer Dublette ab | Migration `c5a9e3f71d28` ohne `pruefen()` (`168_5`) | 1 rot: `test_v586::test_migration_auf_einem_bestand_sqlite` (Abbruch erst an der Bedingung, ohne die Liste) |
| **1.9.168 Nr. 5b** – statt eine Nummer zu leeren | `pruefen()` leert die Dublette und läuft weiter (`168_5b`) | 1 rot: `test_v586::test_migration_auf_einem_bestand_sqlite` (Rückgabe 0, kein Abbruch) |
| 1.9.169 Nr. 1a – Arbeit trägt die gebuchten Stunden (auch Weiterbildung mit der Sollzeit trotz 1/1000) | keine – der Export dafür (L1b) ist nicht gebaut; heute steht es nur als Text der Spalte „Stunden“ in der Zuordnung (`lohnarten.py::FEST`, reine Anzeige) | – |
| **1.9.169 Nr. 1b** – jede andere Zeile die Sollzeit des Tags | `sollzeit.py::abwesenheit_tage()` feste 8 h statt der Sollzeit (`169_1b`) | 4 rot: `test_v589::test_halber_urlaubstag`, `::test_weihnachten_und_silvester_ganze_tage`, `::test_tage_nach_sollzeit`, `test_v591::test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht` |
| **1.9.169 Nr. 2a** – eine Art geht ihrer Kategorie vor, wenn sie eine Lohnart hat | `zuordnung()`: die Art geht nie vor (`169_2a`) | 3 rot: `test_v587::test_art_vor_kategorie[fortbildung-Weiterbildung]`, `::test_geleerte_art_heisst_wie_die_kategorie`, `::test_eigene_zuordnung_einer_art_und_leeren` |
| **1.9.169 Nr. 2b** – eine leere Art heißt „wie die Kategorie“ | `zuordnung()`: eine vorhandene, leere Zeile der Art gilt (wie im Nachtrag 1.9.173) (`169_2b`) | 1 rot: `test_v587::test_geleerte_art_heisst_wie_die_kategorie` |
| 1.9.169 Nr. 2, Satz „wer eine Art nicht exportieren will, leert ihre Kategorie …“ | keine eigene – Folge aus 2a/2b, belegt durch `test_v587::test_art_vor_kategorie[fortbildung-Berufsschule-None]` | – |
| **1.9.169 Nr. 3a** – Schlechtwetter Winter 01.12.–31.03., sonst Sommer | `schlechtwetter_schluessel()` immer Winter (`169_3a`) | 1 rot: `test_v587::test_schlechtwetter_nach_datum` |
| 1.9.169 Nr. 3b – „nicht je Art“ | keine – im Code gibt es keinen Schutz, den man aushebeln könnte; die Probe zeigt das Gegenteil (siehe Bemerkungen) | – |
| **1.9.169 Nr. 3c** – eine Monatszeile nur bei Schlechtwetter | Prüfung „nur für Schlechtwetter“ übergangen (`169_3b`) | 1 rot: `test_v587::test_pruefungen[arbeit-None-1000-True-nur für Schlechtwetter]` |
| 1.9.169 Nr. 3, Satz „ob beide denselben Schlüssel bekommen, klärt das Lohnbüro (E5)“ | keine – offene Frage | – |
| **1.9.169 Nr. 4a** – Kennzeichen 1 bis 2 Zeichen | `KENNZEICHEN_FORMAT` {1,3} (`169_4a`) | 1 rot: `test_v587::test_pruefungen[arbeit-UU1-1000-False-ein oder zwei Zeichen]` |
| **1.9.169 Nr. 4b** – Lohnart 1 bis 4 Ziffern | `LOHNART_FORMAT` {1,5} (`169_4b`) | 1 rot: `test_v587::test_pruefungen[arbeit-1-10000-False-1 bis 4 Ziffern]` |
| **1.9.169 Nr. 5a** – die festen Zeilen legt der Start an | `ensure_default_lohnart_zuordnungen()` ohne die festen Zeilen (`169_5a`) | 5 rot: `test_v587::test_vorbelegt_nach_e7`, `::test_art_vor_kategorie[urlaub-Sonstiges]`, `[krankheit-Kind krank]`, `::test_geleerte_art_heisst_wie_die_kategorie`, `::test_schlechtwetter_nach_datum` |
| **1.9.169 Nr. 5b** – eine geleerte bleibt leer | der Start füllt eine geleerte Zeile wieder nach START (`169_5b`) | 1 rot: `test_v587::test_eigene_zuordnung_einer_art_und_leeren` |
| **1.9.169 Nr. 5c** – eine Zeile je Art erst beim ersten Speichern (außer Weiterbildung) | der Start legt je Art aus `ART_KATEGORIEN` eine leere Zeile an (`169_5c`) | **grün (Befund)**; mit neuem Test 1 rot: `test_v604::test_zeile_je_art_erst_beim_ersten_speichern` |
| **1.9.169 Nr. 6a** – die bisherigen Lohnarten je Zeitart bleiben stehen (Formular speichert sie) | `update_time_settings()` ohne die sechs Felder (`169_6a`) | 1 rot: `test_v104::test_datev_can_use_erp_employee_number` |
| **1.9.169 Nr. 6b** – der heutige Export nimmt sie, bis L1b sie ersetzt | `_wage_type()` gibt für jede Zeitart None (`169_6b`) | 11 rot: `test_v104::test_datev_can_use_erp_employee_number`, `test_v513` ×10 (`test_offener_zeitraum_kein_export`, `test_datev_summe_gleich_stundenzettel_und_uebersicht`, `test_fehlende_lohnart_kein_export_auch_nicht_unter_sonstige`, `test_fehlende_personalnummer_kein_export`, `test_ohne_lohnexport_keine_personalnummer_noetig`, `test_fehlende_datev_nummern_kein_export` ×3, `test_mehreres_fehlt_alles_in_der_liste`, `test_lodas_mit_kopf_und_einer_zeile_je_monat_und_lohnart`) |
| **1.9.169 Nr. 7a** – nur Art Freizeitausgleich in Kategorie Urlaub wird umgestellt | Migration `d8f2a6c4e913` ohne die Bedingung Kategorie Urlaub (`169_7a`) | 1 rot: `test_v587::test_migration_auf_einem_bestand_sqlite` |
| **1.9.169 Nr. 7b** – dieselbe Art in einer anderen Kategorie bleibt ein Widerspruch (`scripts/pruefe_abwesenheiten.py` nennt ihn über `ist_widerspruch()`) | `ART_KATEGORIEN` ohne Freizeitausgleich (passt zu jeder Kategorie) (`169_7b`) | 4 rot: `test_v571_kategorie_und_art::test_zuordnung[Freizeitausgleich]`, `::test_jede_art_der_grundeinstellung_ist_eingeordnet`, `test_v587::test_vorbelegt_nach_e7`, `::test_freizeitausgleich_eigene_kategorie` |
| Werkzeug 1.9.166 Nr. 1 – neue Tests der Zeitregeln nehmen `fester_tag` | keine – Arbeitsweise für das Schreiben von Tests, kein Code (siehe Bemerkungen) | – |

Zahlen: 23 Festlegungen, 48 Gegenproben, beim ersten Lauf 39 rot und 9 grün; nach den neuen Tests 48 rot. Ohne Gegenprobe: eine ganze
Festlegung (Werkzeug 1.9.166 Nr. 1) und acht Teilaussagen (1.9.166 Nr. 4 Bestand des Servers; 1.9.167 Nr. 3 und 1.9.168 Nr. 4 je L1b;
1.9.168 Nr. 1 und 1.9.169 Nr. 3 offene Fragen an DATEV bzw. Lohnbüro; 1.9.169 Nr. 1a, Nr. 2 „Ausweg“, Nr. 3b).

### Befunde

1. **1.9.166 Nr. 3 (Lesart A für jede Pausenregel, auch selbst angelegte; je Modell einstellbar)** – grün blieben `166_3a` (Lesart A nur für
   die Schwellen 6 und 9 h) und `166_3b` (Regeln fest 6 h/30, 9 h/45 statt der des Modells): kein Test rechnete mit einem Modell mit anderen
   Regeln. Neu `test_selbst_angelegte_pausenregeln_nach_lesart_a` (eigenes Modell 5 h -> 20 min, 8 h -> 40 min: acht Anwesenheiten, die fehlende
   Pause einer Dauer von 5,25 h, eine Buchung 07:00–12:15 mit 15 min und 5,00 h). Wiederholung: beide rot (1 rot je Lauf).
2. **1.9.167 Nr. 1 (Tarif auch für Azubis und Aushilfen)** – grün blieben `167_1a` (Funktion „Auszubildende/r“ ohne Sollzeit) und `167_1b`
   (unter 30 Wochenstunden die Wochenstunden / 5): kein Test hatte eine Person mit Funktion oder anderen Wochenstunden. Neu
   `test_tarif_auch_fuer_azubis_und_aushilfen` (Ali mit Funktion „Dachdecker Auszubildende/r“, Hanna mit 10 Wochenstunden: Fr KW 48 8,00 h,
   Mo KW 49 7,50 h, Sa 0). Wiederholung: beide rot.
3. **1.9.167 Nr. 3, Satz „Eintritt und Austritt prüfen das nicht“** – grün blieb `167_3c` (Eintritt/Austritt bis „Abgeschlossen bis“ 422).
   Neu `test_eintritt_und_austritt_auch_im_abgeschlossenen_zeitraum` (abgeschlossen bis 31.10.2026, Eintritt 05.10., Austritt 30.10. -> 200,
   Sollzeit folgt). Wiederholung: rot (422 „Eintritt und Austritt liegen nach dem Abschluss.“).
4. **1.9.167 Nr. 4 (Modell rückwirkend, Hinweis der Seite)** – grün blieben `167_4a` (Modell gesperrt, solange abgeschlossen ist) und `167_4b`
   (Hinweis in `settings.html` entfernt). Neu `test_modellaenderung_gilt_auch_im_abgeschlossenen_zeitraum` (Winter auf 7,00 h bei
   Abschluss 31.10.2026: 200, Mo 02.03.2026 7,50 -> 7,00 h) und `test_seite_sagt_modell_erst_nach_dem_abschluss_aendern` (Wortlaut im Kopf der
   Arbeitszeitmodelle). Wiederholung: beide rot.
5. **1.9.168 Nr. 2 („solange von der Person etwas in die Datei geht“)** – grün blieb `168_2c` (Format der ERP-Nummer nur bei „alles“, nicht
   bei „nur Abwesenheiten“): `test_v586::test_gleichsetzung_mit_erp_nummer` prüft nur „alles“ und „nichts“. Neu
   `test_gleichsetzung_nur_abwesenheiten_verlangt_das_format` (Gleichsetzung, „M-1“, Umfang „abwesenheiten“ -> 422). Wiederholung: rot (200).
6. **1.9.169 Nr. 5, Satz „eine Zeile je Art entsteht erst beim ersten Speichern“** – grün blieb `169_5c` (der Start legt je Art eine leere Zeile
   an): die Liste zeigt eine leere Zeile genauso wie keine. Neu `test_zeile_je_art_erst_beim_ersten_speichern` (nach dem Start, auch nach einem
   zweiten, unter „art:“ nur Weiterbildung; nach dem Speichern von Sonderurlaub zwei). Wiederholung: rot.

### Bemerkungen

- **1.9.169 Nr. 3 „nicht je Art“ passt nicht ganz zum Code.** `lohnarten.py::zuordnung()` prüft die Art vor der Kategorie, auch bei
  Schlechtwetter. Probe (`n4/g/b1/probe_schlechtwetter_art.py`, Wegwerf-SQLite im Speicher): `speichern("art:schlechtwetter", "S", "8111")` –
  das nimmt auch `PUT /api/time-backoffice/lohnarten` an – und danach liefert `zuordnung("schlechtwetter", "Schlechtwetter", …)` im Winter wie im
  Sommer 8111 statt 8110 bzw. „nicht exportiert“; die Liste zeigt dann „Art schlechtwetter (inaktiv) – S / 8111“. Der Ausfalltag trägt die Art
  „Schlechtwetter“ (Name der Kategorie). In der Oberfläche erscheint die Zeile erst, wenn es sie schon gibt oder jemand die Art „Schlechtwetter“
  unter den Abwesenheitsarten anlegt. Kein Test geschrieben (er wäre heute rot); zu entscheiden: Schlüssel „art:schlechtwetter“ ablehnen bzw.
  bei Kategorie Schlechtwetter die Art übergehen – oder den Wortlaut anpassen.
- **1.9.168 Nr. 3 „nur dieselbe Person bekommt sie wieder“** gilt seit 1.9.181 nicht mehr ausnahmslos: der Admin gibt eine gemerkte, von
  niemandem getragene Nummer frei (Festlegung 1.9.177 Nr. 3, neu gefasst mit 1.9.181), danach bekommt sie jede Person. Der Wortlaut von 1.9.168
  Nr. 3 nennt das nicht – geprüft wurde der Wortlaut ohne die Freigabe; die Freigabe selbst gehört zu 1.9.181.
- **1.9.168 Nr. 5**: die Gegenprobe des Archivs („Migration ohne `pruefen()`“) wird nur rot, weil die Liste in der Meldung fehlt – abgebrochen
  wird auch dann, an der Bedingung. Deshalb zusätzlich `168_5b` („Dublette leeren statt abbrechen“), die genau das ausgeschlossene Verhalten
  einsetzt: rot (Rückgabe 0). Beide Migrationsproben nur unter SQLite gefahren (`-k "migration and sqlite"`), die PostgreSQL-Fassung desselben
  Tests lief im Grundlauf grün.
- **1.9.167 Nr. 6**: ohne `round_hours()` wird nur `test_teilzeit_di_bis_do_und_zurueck_zum_tarif` rot, weil er die Texte „7.50“, „3.00“
  vergleicht; ein Modellwert mit vier Stellen (7,3333 h) kommt in keinem Test vor. Kein Befund (die Gegenprobe ist rot), ein Test mit
  7,3333 h wäre eine Ergänzung.
- **1.9.169 Nr. 1a**: die Spalte „Stunden“ der Zuordnung („gebuchte Stunden“ / „Sollzeit“) prüft kein Test (auch nicht `klicktest_lohnarten`);
  als reine Anzeige ohne Prüfung keine Gegenprobe – mit L1b gehört der Test an den Export.
- **1.9.169 Nr. 7b**: geprüft über `ist_widerspruch()`/`ART_KATEGORIEN`, auf die sich das Prüfskript allein stützt
  (`test_v571_pruefe_abwesenheiten::test_widersprueche_mit_id_und_zeitraum_rueckgabe_1` deckt die Ausgabe des Skripts); ein Lauf des Skripts mit
  genau „Freizeitausgleich in Unbezahlt“ steht nur in der Migrationsprobe von `test_v587` (bleibt „unbezahlt“), nicht im Skripttest.
- **Werkzeug 1.9.166 Nr. 1**: Stichprobe statt Gegenprobe – von den neuen Testdateien der Zeitregeln 1.9.166–1.9.191 nehmen `fester_tag` (direkt
  oder über `welt` aus `test_v588`) oder `uhr_festhalten(tag=…)`: v584, v585, v586, v588, v589, v591–v594, v598–v600; ohne Uhr laufen v587,
  v590, v595, v601 (feste Daten bzw. Lohnstammdaten ohne Datum); keine dieser Dateien ruft `berlin_today()` oder `date.today()` auf (grep, kein
tieferer Nachweis).
- Gegenproben `166_2c`/`166_2d` setzen die Zahl auf 0 (statt eines anderen Felds), damit kein JS-Fehler in der Attrappe den Test rot macht;
  rot jeweils mit AssertionError am Text.
- `166_4a` macht neben dem Zieltest alle Buchungstests am 09.11.2026 rot (der Tag liegt vor dem eingesetzten Stichtag) – erwartet.
- `168_3b`: `test_nummernwechsel_sperrt_die_alte_nummer` scheitert mit KeyError im Test (die 422 hat kein Feld `fruehere_personalnummern`) –
  FAILED aus dem geprüften Grund (Mia bekommt 91008 nicht wieder).

## 1.9.198: Festlegungen 1.9.170–1.9.173

20 Festlegungen (1.9.170 Nr. 1–9, 1.9.171 Nr. 1–6 -- Nr. 2 zurückgezogen, Gegenprobe der Rücknahme --, 1.9.172 Nr. 1–4, Werkzeug 1.9.173 Nr. 1),
67 Gegenproben (davon drei Fassungen im Klicktest `klicktest_monteurin_regeln`), keine Festlegung ohne Gegenprobe. pytest: 44 sofort rot, 22 grün ->
17 Befunde, neue Tests in `tests/test_v605_festlegungen_170_173.py` (17 Testfunktionen, 21 Fälle), danach alle 22 rot. Klicktest: am Monatsersten
rot wie im Archiv (30 von 31). Drei Abweichungen von Wortlaut und Code unter „Bemerkungen“ (gemessen mit einer vorübergehenden Probe, nichts geändert).

| Festlegung | Gegenprobe | Ergebnis |
|---|---|---|
| 1.9.170 Nr. 1 a – Vorarbeiter ist das Kennzeichen am Mitarbeiter | 170_1a: `app/schlechtwetter.py::ist_vorarbeiter()` liefert immer False | 3 rot: test_v588::test_eintragen_gilt_sofort[vorarbeiterin], ::test_antrag_bestaetigen[vorarbeiterin], ::test_vorarbeiter_im_mitarbeiterformular |
| 1.9.170 Nr. 1 b – gesetzt im Mitarbeiterformular | 170_1b: `app/routers/employees.py::update_employee()` übernimmt `vorarbeiter` nicht | 1 rot: test_v588::test_vorarbeiter_im_mitarbeiterformular |
| 1.9.170 Nr. 1 c – setzen dürfen Admin und Büro – Finanzen | 170_1c: `_finanzen_dep` in `app/routers/employees.py` auf Büro – Auftrag | 1 rot: test_v282::test_employee_create_and_update_require_buero_finanzen |
| 1.9.170 Nr. 1 d – die Rolle „Vorarbeiter“ in einer Kolonne macht keinen Vorarbeiter | 170_1d: `ist_vorarbeiter()` zählt auch `TeamEmployee.role` mit „vorarbeiter“ | Runde 1 grün (Befund 1); mit dem neuen Test 1 rot: test_v605::test_rolle_vorarbeiter_in_der_kolonne_macht_keinen_vorarbeiter |
| 1.9.170 Nr. 1 e – die Funktion „Dachdecker Vorarbeiter“ macht keinen Vorarbeiter | 170_1e: `ist_vorarbeiter()` zählt auch eine Funktion mit „Vorarbeiter“ im Namen | Runde 1 grün (Befund 2); neu 1 rot: test_v605::test_funktion_dachdecker_vorarbeiter_macht_keinen_vorarbeiter |
| 1.9.170 Nr. 2 a – Kolonnenführer trägt für jeden gewerblichen ein, nicht nur für seine Kolonne | 170_2a: `app/routers/schlechtwetter.py::post_schlechtwetter()` lässt den Kolonnenführer nur für Mitglieder seiner Kolonnen zu (403) | 1 rot: test_v588::test_eintragen_gilt_sofort[kolonnenfuehrer] |
| 1.9.170 Nr. 2 b – nur Kolonnenführer einer aktiven Kolonne | 170_2b: `ist_kolonnenfuehrer()` ohne `Team.active` | 1 rot: test_v588::test_kolonnenfuehrer_einer_abgeschalteten_kolonne_ist_keiner |
| 1.9.170 Nr. 3 a – Büro – Finanzen trägt sofort ein | 170_3a: `darf_eintragen()` ohne Büro – Finanzen | 2 rot: test_v588::test_eintragen_gilt_sofort[buero_finanzen], ::test_kontext |
| 1.9.170 Nr. 3 b – Büro – Finanzen bestätigt keine Anträge | 170_3b: `darf_bestaetigen()` mit Büro – Finanzen | 2 rot: test_v588::test_antrag_bestaetigen[buero_finanzen], ::test_kontext |
| 1.9.170 Nr. 3 c – der Admin entscheidet auch unter „Zeiten“ | 170_3c: `app/absence_requests.py::review_request()` lehnt Kategorie Schlechtwetter ab | Runde 1 grün (Befund 3); neu 1 rot: test_v605::test_admin_entscheidet_schlechtwetter_auch_unter_zeiten |
| 1.9.170 Nr. 4 a – nur gewerbliche Mitarbeiter | 170_4a: `grund_gegen()` ohne Prüfung der Gruppe | 1 rot: test_v588::test_tag_ohne_soll_und_nicht_gewerblich_nichts_gespeichert |
| 1.9.170 Nr. 4 b – auch Azubis | 170_4b: `grund_gegen()` lehnt Funktion „…Auszubild…“ ab | Runde 1 grün (Befund 4); neu 1 rot: test_v605::test_schlechtwetter_auch_fuer_azubis |
| 1.9.170 Nr. 4 c – der Dialog bietet nur gewerbliche an | 170_4c: `gewerbliche()` liefert alle aktiven | 1 rot: test_v588::test_kontext |
| 1.9.170 Nr. 5 a – alles oder nichts | 170_5a: `eintragen()` übergeht abgelehnte Personen und trägt die übrigen ein | 1 rot: test_v588::test_tag_ohne_soll_und_nicht_gewerblich_nichts_gespeichert |
| 1.9.170 Nr. 5 b – die Meldung nennt jede Person mit Grund | 170_5b: nur der erste Grund in `SchlechtwetterAbgelehnt` | 1 rot: test_v588::test_tag_ohne_soll_und_nicht_gewerblich_nichts_gespeichert |
| 1.9.170 Nr. 5 c – alles oder nichts auch im zweiten Schritt (Genehmigen scheitert an einer späteren Person) | 170_5c: `eintragen()` committet statt zurückzurollen | Runde 1 grün (Befund 5); neu 1 rot: test_v605::test_alles_oder_nichts_wenn_eine_spaetere_person_schon_abwesend_ist |
| 1.9.170 Nr. 6 a – Warnung bei gebuchter Zeit | 170_6a: `warnungen()` nur `running` | 2 rot: test_v588::test_gebuchte_zeit_warnung_und_trotzdem, test_v594::test_betriebsfrei_und_gebucht_in_einer_meldung |
| 1.9.170 Nr. 6 b – Warnung bei laufender Zeit | 170_6b: `warnungen()` nur `booked` | Runde 1 grün (Befund 6); neu 1 rot: test_v605::test_laufende_zeit_warnt_wie_gebuchte |
| 1.9.170 Nr. 6 c – „trotzdem“ trägt für alle ein | 170_6c: nach „trotzdem“ nur die Personen ohne Warnung | 1 rot: test_v588::test_gebuchte_zeit_warnung_und_trotzdem |
| 1.9.170 Nr. 6 d – die Buchungen bleiben | 170_6d: „trotzdem“ löscht die Zeiten des Tags | Runde 1 grün (Befund 7); neu 1 rot: test_v605::test_trotzdem_laesst_die_buchungen_stehen |
| 1.9.170 Nr. 7 a (neu gefasst 1.9.178) – gesetzlicher Feiertag abgelehnt | 170_7a: `grund_gegen()` ohne Feiertag | 2 rot: test_v588::test_kein_arbeitstag[feiertag], test_v594::test_gesetzlicher_feiertag_bleibt_abgelehnt |
| 1.9.170 Nr. 7 b – nur gesetzliche: ein betriebsfreier Tag wird nicht abgelehnt | 170_7b: `gesetzlicher_feiertag()` nimmt auch `PlanningHoliday` (422) | 3 rot: test_v594::test_betriebsfreier_tag_fragt_nach, ::test_betriebsfrei_und_gebucht_in_einer_meldung, ::test_die_monteurin_wird_gefragt |
| 1.9.170 Nr. 7 c – am betriebsfreien Tag Rückfrage (409, „trotzdem“) | 170_7c: `warnungen()` ohne betriebsfreien Tag (Stand bis 1.9.177) | 3 rot: dieselben drei aus test_v594 |
| 1.9.170 Nr. 8 a – POST /api/absence-requests lässt Schlechtwetter nicht zu | 170_8a: Muster von `EmployeeAbsenceRequestCreate` mit `schlechtwetter` | 1 rot: test_v588::test_allgemeiner_weg_laesst_schlechtwetter_nicht_zu |
| 1.9.170 Nr. 8 b – die Plantafel lässt Schlechtwetter nicht zu | 170_8b: Muster von `EmployeeAbsenceCreate` (POST /api/planning/absences) mit `schlechtwetter` | Runde 1 grün (Befund 8); neu 1 rot: test_v605::test_plantafel_laesst_schlechtwetter_nicht_zu |
| 1.9.170 Nr. 8 c – „Zeiten“ bietet Schlechtwetter nicht an | 170_8c: `<option value="schlechtwetter">` in `zeiten.html` (#adKategorie) | Runde 1 grün (Befund 9); neu 1 rot: test_v605::test_allgemeine_dialoge_bieten_schlechtwetter_nicht_an[zeiten.html-adKategorie] |
| 1.9.170 Nr. 8 d – die Plantafel bietet es nicht an | 170_8d: dieselbe Option in `planning.html` (#absenceCategory) | Runde 1 grün (Befund 9); neu 1 rot: …[planning.html-absenceCategory] |
| 1.9.170 Nr. 8 e – „Meine Zeiten“ bietet es nicht an | 170_8e: dieselbe Option in `mobil_zeiten.html` (#adKategorie) | Runde 1 grün (Befund 9); neu 1 rot: …[mobil_zeiten.html-adKategorie] |
| 1.9.170 Nr. 9 a – Zeitarten Schlechtwetter in neuer Installation inaktiv | 170_9a: `NEU_INAKTIV = {}` | 1 rot: test_v588::test_zeitarten_schlechtwetter_inaktiv_bei_neuer_installation |
| 1.9.170 Nr. 9 b – sie bleiben in der Liste | 170_9b: `ensure_default_option_groups()` legt sie gar nicht an | 1 rot: test_v588::test_zeitarten_schlechtwetter_inaktiv_bei_neuer_installation |
| 1.9.170 Nr. 9 c – wieder eingeschaltet: Kachel zurück | 170_9c: `app/heute.py::zeitarten()` blendet `weather_*` immer aus | Runde 1 grün (Befund 10); neu 1 rot: test_v605::test_wieder_eingeschaltete_zeitart_bekommt_ihre_kachel_zurueck |
| 1.9.171 Nr. 1 a – halber Tag nur bei Urlaub | 171_1a: `_antrag_anlegen()` prüft die Kategorie nicht | 1 rot: test_v589::test_halber_tag_nur_urlaub_an_einem_tag[krankheit] |
| 1.9.171 Nr. 1 b – nur für einen einzelnen Tag | 171_1b: `_antrag_anlegen()` prüft die Tage nicht | 1 rot: test_v589::test_halber_tag_nur_urlaub_an_einem_tag[zwei_tage] |
| 1.9.171 Nr. 1 c – Freizeitausgleich bleibt ganze Tage | 171_1c: halber Tag auch bei Freizeitausgleich | Runde 1 grün (Befund 11); neu 1 rot: test_v605::test_halber_tag_nicht_bei_anderen_kategorien[freizeitausgleich] |
| 1.9.171 Nr. 2 (zurückgezogen 1.9.174) – Gegenprobe der Rücknahme | 171_2: Halbierung von Urlaub am 24.12./31.12. wieder in `app/sollzeit.py::abwesenheit_tage()` | 8 rot: test_v589::test_weihnachten_und_silvester_ganze_tage, ::test_zeiten_zeigt_halbe_tage; test_v525::test_antrag_ueber_weihnachten_acht_arbeitstage; test_v591::test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht, ::test_zeiten_zeigt_die_arbeitstage_und_den_kalender; test_v592::test_antwort_zaehlt[urlaubstag], ::test_ohne_silvester_keine_frage, ::test_alter_urlaub_ohne_antwort_gilt_wie_der_vorschlag |
| 1.9.171 Nr. 3 a – Arbeitstage nach der Sollzeit der Person | 171_3a: `abwesenheit_tage()` zählt Mo–Fr statt Tage mit Sollzeit | 1 rot: test_v589::test_tage_nach_sollzeit |
| 1.9.171 Nr. 3 b – die Plantafel rechnet weiter je ganzem Tag | 171_3b: `app/planning.py::_absence_rows()` ohne halbe Tage | Runde 1 grün (Befund 12); neu 1 rot: test_v605::test_plantafel_rechnet_den_halben_urlaubstag_als_ganzen_tag |
| 1.9.171 Nr. 4 a – Sammeleintrag beim Admin gleich genehmigt | 171_4a: `gleich_genehmigt=user is None` im Router | 1 rot: test_v589::test_admin_traegt_fuer_alle_ein |
| 1.9.171 Nr. 4 b – bei Büro – Finanzen offene Anträge | 171_4b: `gleich_genehmigt=True` | 1 rot: test_v589::test_buero_finanzen_stellt_antraege |
| 1.9.171 Nr. 4 c – einzeln bleibt es ein Antrag | 171_4c: POST /api/absence-requests genehmigt beim Admin gleich | 3 rot: test_v523::test_admin_entscheidet_und_zieht_nur_eigene_zurueck; test_v592::test_antwort_zaehlt[urlaubstag], [frei] (ValueError „bereits bearbeitet“ beim späteren Entscheiden des schon genehmigten Antrags) |
| 1.9.171 Nr. 5 a – alles oder nichts | 171_5a: `sammel_eintragen()` committet statt zurückzurollen | 1 rot: test_v589::test_alles_oder_nichts |
| 1.9.171 Nr. 5 b – die Meldung nennt jede Person | 171_5b: `SammelAbgelehnt(fehler[:1])` | Runde 1 grün (Befund 13); neu 1 rot: test_v605::test_sammel_nennt_jede_person_auch_wer_schon_abwesend_ist |
| 1.9.171 Nr. 5 c – wer schon abwesend ist, muss abgewählt werden | 171_5c: `sammel_eintragen()` übergeht „bereits eine genehmigte Abwesenheit“ still | Runde 1 grün (Befund 13); neu 1 rot: derselbe Test |
| 1.9.171 Nr. 6 a – „Alle“ = alle aktiven, auch kaufmännische | 171_6a: `GET /api/zeiten/abwesenheiten` liefert unter `mitarbeiter` nur gewerbliche | Runde 1 grün (Befund 14); neu 1 rot: test_v605::test_alle_heisst_alle_aktiven_auch_kaufmaennische |
| 1.9.171 Nr. 6 b – der Sammeleintrag nimmt kaufmännische an | 171_6b: `sammel_eintragen()` lehnt nicht gewerbliche ab | Runde 1 grün (Befund 14); neu 1 rot: derselbe Test |
| 1.9.171 Nr. 6 c – Schlechtwetter nur über den eigenen Dialog | 171_6c: Muster von `AbwesenheitSammel` mit `schlechtwetter` | Runde 1 grün (Befund 15); neu 1 rot: test_v605::test_sammel_schlechtwetter_auch_fuer_einen_tag_nicht |
| 1.9.172 Nr. 1 a – Personalnummer fehlt nur bei Export ≠ „nichts“ | 172_1a: auch bei „nichts“ verlangt | 1 rot: test_v590::test_personalnummern_fehlend_falsch_doppelt |
| 1.9.172 Nr. 1 b – fehlende Nummer ist zu klären | 172_1b: nur Zeile, kein Befund | 2 rot: test_v590::test_die_eigene_sitzung_schreibt_nicht, ::test_unter_postgresql_lesen_und_nicht_schreiben (Rückgabe 0 statt 1) |
| 1.9.172 Nr. 1 c – Format 1 bis 5 Ziffern ohne führende Null | 172_1c: Format nicht geprüft | 2 rot: test_v590::test_personalnummern_fehlend_falsch_doppelt, ::test_gleichsetzung_prueft_die_erp_nummer |
| 1.9.172 Nr. 1 d – doppelte Nummer | 172_1d: Dubletten erst ab 100 | 1 rot: test_v590::test_personalnummern_fehlend_falsch_doppelt |
| 1.9.172 Nr. 1 e – Startmodell mit alten Grundwerten | 172_1e: nicht erkannt | 1 rot: test_v590::test_alte_grundwerte_sind_zu_klaeren |
| 1.9.172 Nr. 1 f – Kalenderwochen ohne aktives Modell | 172_1f: dieselbe Zeile, aber kein Befund | 1 rot: test_v590::test_kalenderwochen_ohne_aktives_modell |
| 1.9.172 Nr. 1 g – kein Modell | 172_1g: „Kein Arbeitszeitmodell“ nur als Hinweis | Runde 1 grün (Befund 16); neu 1 rot: test_v605::test_ohne_arbeitszeitmodell_zu_klaeren |
| 1.9.172 Nr. 1 h – abweichende Pausenregeln nur Hinweis | 172_1h: zusätzlich als Befund gezählt | 1 rot: test_v590::test_hinweise_aendern_die_rueckgabe_nicht |
| 1.9.172 Nr. 1 i – mehrere Modelle in einer Woche nur Hinweis | 172_1i: zusätzlich als Befund gezählt | 1 rot: test_v590::test_hinweise_aendern_die_rueckgabe_nicht |
| 1.9.172 Nr. 1 j – kein Standardmodell nur Hinweis | 172_1j: zusätzlich als Befund gezählt | 1 rot: test_v590::test_hinweise_aendern_die_rueckgabe_nicht |
| 1.9.172 Nr. 2 – bei Gleichsetzung die ERP-Nummer | 172_2: immer die DATEV-Nummer | 1 rot: test_v590::test_gleichsetzung_prueft_die_erp_nummer |
| 1.9.172 Nr. 3 a – nur aktive Mitarbeiter | 172_3a: auch inaktive geprüft | 1 rot: test_v590::test_personalnummern_fehlend_falsch_doppelt |
| 1.9.172 Nr. 3 b – „aktiv, aber ausgetreten“ ist kein Befund | 172_3b: als Befund gezählt | 1 rot: test_v590::test_eintritt_austritt_eigene_sollzeit_und_zuordnung_der_modelle |
| 1.9.172 Nr. 3 c – „aktiv, aber ausgetreten“ wird genannt | 172_3c: nicht genannt | 1 rot: derselbe Test |
| 1.9.172 Nr. 4 a – Personen nur mit Kennung | 172_4a: je Person eine Zeile mit Vor- und Nachname | 2 rot: test_v590::test_kein_name_in_der_ausgabe, ::test_gleichsetzung_prueft_die_erp_nummer (die neue Zeile „Person <ID>:“) |
| 1.9.172 Nr. 4 b – von Hand eingetragene Tage mit Namen | 172_4b: ohne Namen | 1 rot: test_v590::test_anderes_bundesland_und_von_hand_eingetragene_tage |
| 1.9.172 Nr. 4 c – Modelle mit Namen | 172_4c: ohne Namen | 2 rot: test_v590::test_grunddaten_nichts_zu_klaeren, ::test_eintritt_austritt_eigene_sollzeit_und_zuordnung_der_modelle |
| 1.9.172 Nr. 4 d – Feiertage mit Namen | 172_4d: ohne Namen | 1 rot: test_v590::test_feiertage_dieses_und_naechsten_jahres |
| 1.9.173 Nr. 1 a (Werkzeug) – fester Tag: der Klicktest hängt am Tag | 173_1a_k: `klicktest_monteurin_regeln` mit `uhr="2026-12-01 10:00"` (Monatserster) | rot (Rückgabe 1): 30 von 31, „/mobil/zeiten: Seite nicht bereit“ und die Zeile „läuft seit 06:45“ fehlt -- wie im Archiv; Grundlauf auf demselben Stand 31 von 31 |
| 1.9.173 Nr. 1 b – stehende Uhr auch im Browser | 173_1b: `tab.browser_uhr_fest(…)` entfernt | Klicktest: grün (31 von 31); pytest Runde 1 grün (Befund 17); neu 1 rot: test_v605::test_klicktest_monteurin_regeln_an_einem_festen_tag |
| 1.9.173 Nr. 1 c – fester Tag statt Lauftag | 173_1c: `uhr="10:00"` (Lauftag, Stand bis 1.9.172) | Klicktest: grün (31 von 31); pytest Runde 1 grün (Befund 17); neu 1 rot: derselbe Test |

Zahlen: 20 Festlegungen, 67 Gegenproben (66 mit pytest -- darunter 173_1b und 173_1c als Strukturtest --, dazu 3 mit dem Klicktest:
173_1a, 173_1b, 173_1c), ohne Gegenprobe: keine Festlegung. pytest Runde 1: 44 rot, 22 grün (17 Befunde, s. u.) -- mit dem neuen Test alle
22 rot. Klicktest: 1 rot (173_1a), 2 grün (173_1b, 173_1c; s. Bemerkung 6).

### Befunde

Je Befund: was grün blieb, der neue Test in `tests/test_v605_festlegungen_170_173.py`, Ergebnis der Wiederholung.

1. **1.9.170 Nr. 1 (Rolle in der Kolonne)** -- 170_1d grün: kein Test hatte eine Kolonnenrolle „Vorarbeiter“. Neu `test_rolle_vorarbeiter_in_der_kolonne_macht_keinen_vorarbeiter` (Tom mit Rolle „Vorarbeiter“: Kontext ohne „für andere“, für Mia 403). Wiederholung: 1 rot.
2. **1.9.170 Nr. 1 (Funktion)** -- 170_1e grün: kein Test mit Funktion „Dachdecker Vorarbeiter“. Neu `test_funktion_dachdecker_vorarbeiter_macht_keinen_vorarbeiter`. Wiederholung: 1 rot.
3. **1.9.170 Nr. 3 (Admin unter „Zeiten“)** -- 170_3c grün (126 Tests aus v588, v594, v519, v520, v523, v566): niemand entschied einen Schlechtwetter-Antrag über `POST /api/absence-requests/{id}/review`. Neu `test_admin_entscheidet_schlechtwetter_auch_unter_zeiten` (Antrag steht unter „Zeiten“ mit `darf_entscheiden`, Admin genehmigt dort, Abwesenheit da). Wiederholung: 1 rot (422 statt 200).
4. **1.9.170 Nr. 4 (Azubis)** -- 170_4b grün: kein Test mit Azubi. Neu `test_schlechtwetter_auch_fuer_azubis` (Funktion „Dachdecker Auszubildende/r“: im Kontext, eingetragen). Wiederholung: 1 rot.
5. **1.9.170 Nr. 5 (alles oder nichts im zweiten Schritt)** -- 170_5c grün: `test_v588::test_schon_abwesend` nimmt Mia (schon abwesend) zuerst -- scheitert sie, ist für Tom noch nichts angelegt; ein Commit statt Rollback ließ nur Mias neuen offenen Antrag stehen, und der Test zählt nur Abwesenheiten. Neu `test_alles_oder_nichts_wenn_eine_spaetere_person_schon_abwesend_ist` (Tom vor Mia; Anträge und Abwesenheiten unverändert). Wiederholung: 1 rot.
6. **1.9.170 Nr. 6 (laufende Zeit)** -- 170_6b grün: nur gebuchte Zeit war geprüft. Neu `test_laufende_zeit_warnt_wie_gebuchte` (laufende Zeit: 409, `laeuft` True, „eine Zeit läuft“, nichts gespeichert). Wiederholung: 1 rot.
7. **1.9.170 Nr. 6 (Buchungen bleiben)** -- 170_6d grün: kein Test sah nach „trotzdem“ auf die Buchung. Neu `test_trotzdem_laesst_die_buchungen_stehen`. Wiederholung: 1 rot.
8. **1.9.170 Nr. 8 (Plantafel)** -- 170_8b grün (172 Tests aus v588, v594, v566, v571, v286, v287): kein Test schickte Schlechtwetter an `POST /api/planning/absences`. Neu `test_plantafel_laesst_schlechtwetter_nicht_zu` (422, nichts gespeichert). Wiederholung: 1 rot.
9. **1.9.170 Nr. 8 (Dialoge)** -- 170_8c/8d/8e grün: kein Test sah in die Kategorie-Auswahl der drei Dialoge (v587 prüft nur, dass Freizeitausgleich da ist). Neu `test_allgemeine_dialoge_bieten_schlechtwetter_nicht_an` (je Vorlage genau die fünf Kategorien in `#adKategorie` bzw. `#absenceCategory`). Wiederholung: je 1 rot (der Fall der geänderten Vorlage).
10. **1.9.170 Nr. 9 (Kachel zurück)** -- 170_9c grün (auch mit v286 und v472): kein Test schaltete eine Zeitart Schlechtwetter wieder ein. Neu `test_wieder_eingeschaltete_zeitart_bekommt_ihre_kachel_zurueck` (`app/heute.py::zeitarten()`). Wiederholung: 1 rot.
11. **1.9.171 Nr. 1 (Freizeitausgleich)** -- 171_1c grün: nur Krankheit war geprüft. Neu `test_halber_tag_nicht_bei_anderen_kategorien[freizeitausgleich|fortbildung|unbezahlt]`. Wiederholung: 1 rot (freizeitausgleich).
12. **1.9.171 Nr. 3 (Plantafel je ganzem Tag)** -- 171_3b grün (101 Tests aus v600, v563, v090, v589, v525, v591, v592): kein Test mit halbem Tag auf der Plantafel. Neu `test_plantafel_rechnet_den_halben_urlaubstag_als_ganzen_tag` (Kapazität 0, Abwesenheit „Urlaub“, Tom und der Folgetag unberührt). Wiederholung: 1 rot.
13. **1.9.171 Nr. 5 (jede Person; schon abwesend)** -- 171_5b und 171_5c grün: `test_v589::test_alles_oder_nichts` hat nur eine abgelehnte Person (offener Antrag) und niemanden, der schon abwesend ist. Neu `test_sammel_nennt_jede_person_auch_wer_schon_abwesend_ist` (Kai frei, Mia genehmigter Urlaub, Tom offener Antrag: 422, die Liste nennt Mia und Tom, nichts gespeichert). Wiederholung: beide 1 rot.
14. **1.9.171 Nr. 6 („Alle“ auch kaufmännische)** -- 171_6a (163 Tests) und 171_6b grün: in den Tests des Sammeleintrags war niemand kaufmännisch. Neu `test_alle_heisst_alle_aktiven_auch_kaufmaennische` (die Liste nennt Bea (kaufmännisch), nicht Ina (inaktiv); Sammeleintrag für Bea und Mia genehmigt). Wiederholung: beide 1 rot.
15. **1.9.171 Nr. 6 (Schlechtwetter im Sammeleintrag)** -- 171_6c grün: `test_v589::test_sammel_halber_tag_und_schlechtwetter` schickt Schlechtwetter über drei Tage -- auch mit erlaubtem Muster 422 („Schlechtwetter wird je Tag eingetragen“), aus dem falschen Grund. Neu `test_sammel_schlechtwetter_auch_fuer_einen_tag_nicht` (ein Tag, 422, nichts gespeichert). Wiederholung: 1 rot.
16. **1.9.172 Nr. 1 (kein Modell)** -- 172_1g grün: ohne Modell ist die Rückgabe ohnehin 1 (Kalenderwochen ohne Modell), die Zeile „Kein Arbeitszeitmodell“ prüfte niemand. Neu `test_ohne_arbeitszeitmodell_zu_klaeren` (alle Modelle gelöscht: Rückgabe 1, „Arbeitszeitmodelle: 0“, „  ! Kein Arbeitszeitmodell …“). Wiederholung: 1 rot.
17. **1.9.173 Nr. 1 (fester Tag in Instanz und Browser)** -- 173_1b und 173_1c als pytest grün (`test_v339_feste_uhr` verlangt nur `uhr=`, eine Uhrzeit genügt); im Klicktest selbst grün (31 von 31: der Lauftag 04.11.2026 liegt im selben Monat wie der feste Tag 11.11.2026). Neu `test_klicktest_monteurin_regeln_an_einem_festen_tag` (AST: `klicktest_main(…, uhr="JJJJ-MM-TT HH:MM")` mit gültigem Datum und ein Aufruf `….browser_uhr_fest(…)`). Wiederholung: beide 1 rot. Bewusst nur für diesen Klicktest: die Festlegung lässt bestehende Klicktests erst umstellen, wenn sie rot werden oder ohnehin angefasst werden.

### Bemerkungen

1. **1.9.170 Nr. 5 -- die Meldung nennt nicht jede Person, wenn jemand schon abwesend ist.** Gemessen (vorübergehende Probe, wieder gelöscht): Mia und Tom haben am Mo 07.12.2026 schon Schlechtwetter, ein zweites Eintragen für beide ergibt 422 mit `detail` „Nicht eingetragen: Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits eine genehmigte Abwesenheit.“ -- ohne Namen und nur ein Grund. `app/schlechtwetter.py::eintragen()` sammelt nur die Gründe aus `grund_gegen()` je Person; „schon abwesend“ und „offener Antrag“ kommen erst im zweiten Schritt als einzelne `ValueError` (Abbruch beim ersten). Der Sammeleintrag (1.9.171) macht es je Person mit Namen. Nicht geändert.
2. **1.9.171 Nr. 5 -- „wer schon abwesend ist, muss abgewählt werden“ gilt nur beim Admin.** Gemessen: Büro – Finanzen trägt per Sammeleintrag Urlaub 28.–30.12.2026 für Mia (am 29.12. genehmigter Urlaub) und Tom ein -> 200, beide als offene Anträge; erst die Entscheidung des Admins scheitert dann an Mia. `_antrag_anlegen()` prüft nur offene Anträge, die genehmigte Abwesenheit erst `_entscheiden()` -- das läuft beim Sammeleintrag nur für den Admin. (Beim Einzelantrag ist es seit 1.9.101 ebenso.) Nicht geändert.
3. **1.9.170 Nr. 3 / Docstring `app/schlechtwetter.py::entscheiden()` („beim Bestätigen gelten dieselben Regeln wie beim Eintragen“) -- nicht auf dem Weg über „Zeiten“.** Gemessen: Tom beantragt Mo 07.12.2026, danach bekommt er eine eigene Sollzeit ohne Montag. Bestätigen im Schlechtwetter-Dialog -> 422 „Tom Monteur: am 07.12.2026 keine Sollzeit“; derselbe Antrag über „Zeiten“ (`POST /api/absence-requests/{id}/review`) -> 200, Abwesenheit angelegt. `review_request()` prüft `grund_gegen()` nicht. Die Festlegung sagt nur, dass der Admin auch dort entscheidet; ob dort dieselben Regeln gelten sollen, ist offen. Nicht geändert.
4. Die neuen Tests prüften zuerst Status und Körper in einem Tupel (`(r.status_code, r.json()["status"])`); unter der Gegenprobe 170_3c endete das mit `KeyError: 'status'` statt einer AssertionError (FAILED, aber nicht aus dem lesbaren Grund). Umgestellt auf zuerst den Status, dann den Körper (drei Stellen); 170_3c, 170_4b und 171_6b danach noch einmal mit `-rf`: AssertionError mit der Antwort des Servers.
5. 171_4c (Einzelantrag des Admins gleich genehmigt) wird in test_v592 nicht an der Erwartung „offen“ rot, sondern weil der Test den Antrag danach selbst entscheidet und `_entscheiden()` „bereits bearbeitet“ wirft (FAILED mit ValueError). Der unmittelbare Test ist `test_v523::test_admin_entscheidet_und_zieht_nur_eigene_zurueck` (rot).
6. 1.9.173: Die Klicktest-Fassungen 173_1b (Browser ohne stehende Uhr) und 173_1c (Lauftag) sind heute nur deshalb grün, weil der Lauftag
   (04.11.2026) im selben Monat liegt wie der feste Tag; ein Klicktest kann den Schutz nur an einem Monatsersten zeigen. Deshalb sichert ihn
   jetzt der Strukturtest (Befund 17). Die Bereitschaftsbedingung `ZEITEN_BEREIT` (`D.tage.length>0`) ist auch nach 1.9.186 (angeheftete Zeit)
   am Monatsersten nie wahr -- die laufende Zeit vom Vortag steht dann angeheftet, nicht in `D.tage`; das ist eine Eigenschaft des Klicktests,
   kein Fehler der Seite (der Fall „Monatserster“ ist in `klicktest_meine_zeiten_angeheftet` abgedeckt). Grundlauf und Gegenproben je eigene
   Instanz, Prozesse über das Werkzeug (eigene PID).
7. `app/` ist in der Arbeitskopie unverändert: `git status --short` zeigt außer den Änderungen 1.9.192–1.9.194 nur `tests/test_v605_festlegungen_170_173.py` (die Probe-Datei für die Bemerkungen 1–3 ist wieder gelöscht).

## 1.9.199: Festlegungen 1.9.174–1.9.179

24 Festlegungen (1.9.175 Nr. 1–7, 1.9.176 Nr. 1–8, 1.9.177 Nr. 1–6, 1.9.178 Nr. 1–3; 1.9.174 und 1.9.179 ohne eigene Festlegung), 77 Gegenproben
(davon zwei im Klicktest `klicktest_silvester`), 62 sofort rot, 15 grün -> 14 Befunde an 9 Festlegungen, 15 neue Tests in
`tests/test_v606_festlegungen_174_179.py`, danach alle rot. Ohne Gegenprobe: 5 Teilaussagen. Eine Fassung (176_3e) war zuerst falsch gebaut (rot aus dem
falschen Grund) und ist neu gebaut, siehe „Bemerkungen“. Gegenproben auch in einer Migration (1.9.177 Nr. 5) und in `scripts/pruefe_zeitregeln.py`.

| Festlegung | Gegenprobe (Datei: was geändert) | Ergebnis |
|---|---|---|
| 1.9.175 Nr. 1a – eigene Liste in den Einstellungen | `settings.html`: `id="kalenderBlock"` umbenannt | 1 rot: v591::test_seiten |
| 1.9.175 Nr. 1b – Anlegen nur Admin und Büro – Finanzen | `routers/time_backoffice.py`: POST Kalender mit `_role_dep` (Lesen) statt `_regeln_dep` | 2 rot: v591::test_buero_auftrag_liest_nur, v109::test_time_backoffice_router_fully_uses_shared_dependency |
| 1.9.175 Nr. 1c – Ändern nur Admin und Büro – Finanzen | dito PUT | 2 rot: v591::test_buero_auftrag_liest_nur, v109::test_time_backoffice_router_fully_uses_shared_dependency |
| 1.9.175 Nr. 1d – Büro – Auftrag liest | GET Kalender mit `_regeln_dep` | 1 rot: v591::test_buero_auftrag_liest_nur |
| 1.9.175 Nr. 1e – ein Eintrag je Datum | `arbeitszeitkalender.py::_pruefen()`: Prüfung „steht schon … im Kalender“ übergangen | 1 rot: v591::test_abgelehnte_eingaben[doppelt] |
| 1.9.175 Nr. 1f – abschalten wirkt | `aktive()` und `_datum_passt()` ohne `aktiv` (beide, siehe Bemerkungen) | 2 rot: v591::test_anlegen_aendern_abschalten, v600::test_abgeschalteter_kalendertag_wie_bisher |
| 1.9.175 Nr. 1g – nur gewerbliche | `gilt()` ohne Gruppe | 8 rot: v591::test_sollzeit_an_heiligabend, ::test_abwesenheit_von_selbst, ::test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht, ::test_halber_urlaubstag_an_heiligabend_nur_kaufmaennisch, v592::test_sollzeit_und_freistellung, ::test_ohne_silvester_keine_frage, ::test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort, v599::test_kaufmaennisch_ohne |
| 1.9.175 Nr. 1h – nur Montag bis Freitag | `_datum_passt()` ohne Wochentag | **grün -> Befund 1**; mit v606: 1 rot (v606::test_nur_mo_fr_auch_bei_eigener_sollzeit_am_wochenende) |
| 1.9.175 Nr. 1 – „abschalten statt löschen“ (kein Löschweg) | keine | bewusst nicht gebaut: es gibt keinen Endpunkt zum Löschen, nichts zum Aushebeln |
| 1.9.175 Nr. 2a – Abwesenheit nicht gespeichert | `abwesenheiten()` legt je Tag eine `EmployeeAbsence` an | 1 rot, nur mittelbar: v599::test_silvester_als_ganzer_urlaubstag_fehlt (die gespeicherte Zeile blockiert eine spätere Genehmigung); mit v606 dazu direkt v606::test_abwesenheit_des_kalenders_wird_nicht_gespeichert |
| 1.9.175 Nr. 2b – eigene Karte unter „Zeiten → Abwesenheiten“ | `routers/zeiten.py`: `"kalender": []` | 1 rot: v591::test_zeiten_zeigt_die_arbeitstage_und_den_kalender |
| 1.9.175 Nr. 2 – nicht einzeln löschbar | keine | bewusst nicht gebaut (die Abwesenheit ist nirgends gespeichert, es gibt keinen Weg) |
| 1.9.175 Nr. 2 – „stimmt sofort“ bei Kalender, Funktion, Eintritt | siehe 1f (Kalender), 1g (Funktion), 3c (Eintritt) | dieselbe Ableitung, dort rot |
| 1.9.175 Nr. 3a – 7,00 h nur bei Sollzeit über 0 | `sollzeit.py::soll_zeitraum()`: Kalender-Sollzeit auch bei `wert == 0` | 7 rot: v591::test_teilzeit_an_einem_tag_mit_sollzeit_voll, ::test_ohne_sollzeit_am_wochentag_weder_sollzeit_noch_freistellung, v599::test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll, v600::test_freistellungen_nur_mit_sollzeit, ::test_tafel_zeigt_die_betroffenen_abwesend, ::test_gespeicherte_abwesenheit_geht_vor, ::test_vorschlag_rechnet_den_tag_ohne_die_betroffenen |
| 1.9.175 Nr. 3b – voll, nicht anteilig | `soll_zeitraum()`: `min(wert, Kalender-Sollzeit)` | 2 rot: v591::test_teilzeit_an_einem_tag_mit_sollzeit_voll, v599::test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll |
| 1.9.175 Nr. 3c – ohne Sollzeit am Tag weder Sollzeit noch Freistellung, vor dem Eintritt nicht | `kalendertage_im_zeitraum()` ohne Bedingung `soll > 0` | 3 rot: v591::test_ohne_sollzeit_am_wochentag_weder_sollzeit_noch_freistellung, ::test_vor_dem_eintritt_kein_heiligabend, v599::test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll |
| 1.9.175 Nr. 3d – nach dem Austritt nicht | `sollzeit.py::beschaeftigt_am()` ohne Austritt | 1 rot: test_v585_sollzeit.py::test_eintritt_und_austritt (siehe Bemerkungen) |
| 1.9.175 Nr. 4a – keine andere Abwesenheit zählt den Kalendertag | `abwesenheit_tage()` zählt Kalendertage mit | 7 rot: v591::test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht, ::test_zeiten_zeigt_die_arbeitstage_und_den_kalender, v592::test_antwort_zaehlt[frei], ::test_ohne_silvester_keine_frage, test_v589::test_weihnachten_und_silvester_ganze_tage, ::test_zeiten_zeigt_halbe_tage, test_v525::test_antrag_ueber_weihnachten_acht_arbeitstage |
| 1.9.175 Nr. 4b – auch Krankheit zählt 0 | `abwesenheit_tage()` überspringt den Kalendertag nur bei Urlaub | 3 rot: v591::test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht, v592::test_ohne_silvester_keine_frage, test_v589::test_weihnachten_und_silvester_ganze_tage |
| 1.9.175 Nr. 4c – halber Urlaubstag 422 | `absence_requests.py::_antrag_anlegen()`: Prüfung Kalendertag übergangen | 2 rot: v591::test_halber_urlaubstag_an_heiligabend_nur_kaufmaennisch, v592::test_kein_halber_tag_an_silvester |
| 1.9.175 Nr. 4d – Schlechtwetter 422 | `schlechtwetter.py::grund_gegen()`: Kalendertag übergangen | 2 rot: v591::test_kein_schlechtwetter_an_heiligabend, v592::test_kein_schlechtwetter_an_silvester |
| 1.9.175 Nr. 5a – Kennzeichen ohne Lohnart am Kalendertag erlaubt | `lohnarten.py::speichern()`: „Zum Kennzeichen gehört eine Lohnart“ auch am Kalendertag | 1 rot: v591::test_zuordnung_des_kalendertags |
| 1.9.175 Nr. 5b – nur dort | dieselbe Prüfung überall übergangen | 2 rot: v591::test_zuordnung_des_kalendertags, test_v587::test_pruefungen[feiertag-F-None-False-gehört eine Lohnart] |
| 1.9.175 Nr. 5c – je Kalendertag eine Zeile | `lohnarten.py::liste()` ohne Kalenderzeilen | 2 rot: v591::test_heiligabend_ist_vorbelegt, ::test_anlegen_aendern_abschalten |
| 1.9.175 Nr. 5d – exportiert erst mit Lohnart | `lohnarten.py::kalender()`: `exportiert` immer wahr | 3 rot: v591::test_heiligabend_ist_vorbelegt, ::test_zuordnung_des_kalendertags, v592::test_silvester_ist_vorbelegt |
| 1.9.175 Nr. 5e – Text „BF / Lohnart offen – nicht exportiert“ | `lohnarten.py::_text()` ohne „Lohnart offen – nicht exportiert“ | 1 rot: v591::test_heiligabend_ist_vorbelegt |
| 1.9.175 Nr. 5 – Export der Zeile mit Lohnart (L1b) | keine | L1b ist nicht gebaut |
| 1.9.175 Nr. 6a – Änderung gilt auch für zurückliegende Jahre | `_datum_passt()`: Kalendertag nur ab heute | **grün -> Befund 2**; mit v606: 1 rot (v606::test_aenderung_gilt_auch_fuer_zurueckliegende_jahre) |
| 1.9.175 Nr. 6b – die Seite sagt das | `settings.html`: Satz „Eine Änderung gilt auch für zurückliegende Jahre“ entfernt | **grün -> Befund 3**; mit v606: 1 rot (v606::test_seite_sagt_zurueckliegende_jahre) |
| 1.9.175 Nr. 7a – ab heute | `naechste()`: auch vergangene Tage | **grün -> Befund 4**; mit v606: 2 rot (v606::test_naechste_ab_heute, ::test_naechste_ganz) |
| 1.9.175 Nr. 7b – dieses und das nächste Jahr | `naechste(jahre=3)` | **grün -> Befund 5**; mit v606: 1 rot (v606::test_naechste_ganz) |
| 1.9.175 Nr. 7c – ohne Sa/So bei „nur Mo–Fr“ | `naechste()` ohne Wochenend-Filter | **grün -> Befund 6**; mit v606: 2 rot (v606::test_naechste_ohne_samstag_und_sonntag, ::test_naechste_ganz) |
| 1.9.175 Nr. 7d – nur aktive Tage | `naechste()` über alle statt `aktive()` | **grün -> Befund 7**; mit v606: 2 rot (v606::test_naechste_nur_aktive_tage, ::test_naechste_ganz) |
| 1.9.176 Nr. 1a – ohne Antwort 409 auf allen Wegen | `_antrag_anlegen()`: keine `KalendertagFrage` | 4 rot: v592::test_ohne_antwort_fragt_der_server[einzeln], [sammel], [plantafel], ::test_die_monteurin_wird_gefragt |
| 1.9.176 Nr. 1b – nichts gespeichert (Sammeleintrag) | `sammel_eintragen()`: kein `rollback()` bei der Rückfrage | 1 rot: v592::test_ohne_antwort_fragt_der_server[sammel] |
| 1.9.176 Nr. 1c – Plantafel 409 mit Rückfrage | `routers/planning.py`: Rückfrage als 422 ohne `rueckfrage` | 1 rot: v592::test_ohne_antwort_fragt_der_server[plantafel] |
| 1.9.176 Nr. 1d – Sammeleintrag: eine Antwort für alle | `sammel_eintragen()`: Antwort nur für die erste Person | **grün -> Befund 8**; mit v606: 1 rot (v606::test_sammeleintrag_eine_antwort_fuer_alle) |
| 1.9.176 Nr. 1e – … für die der Tag gilt | `_antrag_anlegen()`: Antwort auch ohne Kalendertag gespeichert | 1 rot: v592::test_ohne_silvester_keine_frage |
| 1.9.176 Nr. 2a – nur Kategorie Urlaub | `_antrag_anlegen()`: Rückfrage für jede Kategorie | 1 rot: v592::test_ohne_silvester_keine_frage |
| 1.9.176 Nr. 2b – nur wenn Silvester gilt (gewerblich, Mo–Fr, beschäftigt, Sollzeit) | `rueckfrage_tage()`: jeder aktive Tag nach Datum, ohne Person | 3 rot: v591::test_ohne_sollzeit_am_wochentag_weder_sollzeit_noch_freistellung, v592::test_ohne_silvester_keine_frage, ::test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort |
| 1.9.176 Nr. 2c – Krankheit zählt Silvester nicht | `abwesenheit_tage()`: Krankheit zählt den Tag mit Rückfrage wie Urlaub | 1 rot: v592::test_ohne_silvester_keine_frage |
| 1.9.176 Nr. 3a – Antwort am Antrag | `_antrag_anlegen()`: `kalendertag_urlaub` immer leer | 3 rot: v592::test_antwort_zaehlt[urlaubstag], [frei], ::test_die_monteurin_wird_gefragt |
| 1.9.176 Nr. 3b – Antwort an der Abwesenheit | `_entscheiden()`: `kalendertag_urlaub` nicht übernommen | 2 rot: v592::test_antwort_zaehlt[urlaubstag], [frei] |
| 1.9.176 Nr. 3c – „ganzer Urlaubstag“ ersetzt die Freistellung | `urlaub_ersetzt()` leer | 3 rot: v592::test_antwort_zaehlt[urlaubstag], ::test_alter_urlaub_ohne_antwort_gilt_wie_der_vorschlag, v599::test_silvester_als_ganzer_urlaubstag_fehlt |
| 1.9.176 Nr. 3d – zählt mit der Sollzeit des Modells | `abwesenheit_tage()`: Antwort nicht gezählt | 6 rot: v591::test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht, ::test_zeiten_zeigt_die_arbeitstage_und_den_kalender, v592::test_antwort_zaehlt[urlaubstag], ::test_alter_urlaub_ohne_antwort_gilt_wie_der_vorschlag, test_v589::test_weihnachten_und_silvester_ganze_tage, ::test_zeiten_zeigt_halbe_tage |
| 1.9.176 Nr. 3e – bis zur Genehmigung gilt die Freistellung | `urlaub_ersetzt()`: offene Anträge zählen dazu (176_3e2; die erste Fassung 176_3e war falsch gebaut, siehe Bemerkungen) | 1 rot: v599::test_silvester_als_ganzer_urlaubstag_fehlt („offen: zählt noch nicht“) |
| 1.9.176 Nr. 4a – ohne Antwort wie der Vorschlag | `als_urlaubstag()`: nur `True` | 3 rot: v591::test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht, v592::test_alter_urlaub_ohne_antwort_gilt_wie_der_vorschlag, test_v589::test_weihnachten_und_silvester_ganze_tage |
| 1.9.176 Nr. 4b – Prüfskript zählt solche Anträge | `scripts/pruefe_zeitregeln.py::_urlaub_ohne_antwort()`: zählt 0 | 1 rot: v592::test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort |
| 1.9.176 Nr. 5 – kein halber Urlaubstag an Silvester | `_antrag_anlegen()`: Prüfung nur noch an Tagen ohne Rückfrage | 1 rot: v592::test_kein_halber_tag_an_silvester |
| 1.9.176 Nr. 6 – gebuchte Arbeit an Silvester kommt dazu | `abwesenheiten()`: Tag mit Rückfrage und gebuchter Zeit fällt weg | **grün -> Befund 9**; mit v606: 1 rot (v606::test_gebuchte_arbeit_an_silvester_kommt_dazu). Querprobe ohne Einschränkung auf Silvester (176_6x): 1 rot v591::test_gebuchte_arbeit_mindert_die_freistellung_nicht |
| 1.9.176 Nr. 7a – die Antwort steht in der Antwort der Schnittstelle | `request_to_dict()`: `kalendertag_urlaub` leer | 3 rot: v592::test_antwort_zaehlt[urlaubstag], [frei], ::test_die_monteurin_wird_gefragt |
| 1.9.176 Nr. 7b – Liste „Zeiten → Abwesenheiten“ nennt sie | `zeiten.html::abwesenheitHtml()` ohne den Zusatz | Klicktest: klicktest_silvester rot (Rückgabe 1, 2 Prüfungen: „Ada: Liste nennt „frei“ und 8 Arbeitstage“, „Ada: Tom mit Urlaubstag, Kim ohne Frage“); Grundlauf vorher 0 |
| 1.9.176 Nr. 7c – Liste „Meine Zeiten“ nennt sie | `mobil_zeiten.html` (Anträge) ohne den Zusatz | Klicktest: klicktest_silvester rot (Rückgabe 1, „Mia: Liste nennt den Urlaubstag“) |
| 1.9.176 Nr. 7d – Liste „Zeiten → Prüfen“ (offene Anträge) nennt sie | `zeiten.html::antragHtml()` ohne den Zusatz | **grün -> Befund 10** (kein pytest, kein Klicktest liest sie); mit v606: 1 rot (v606::test_beide_listen_unter_zeiten_nennen_die_antwort) |
| 1.9.176 Nr. 8a – „Im Urlaub“ hat zwei Werte | `IM_URLAUB` ohne „fragen“ | 1 rot: v591::test_buero_auftrag_liest_nur |
| 1.9.176 Nr. 8b – jeder weitere Kalendertag kann „Rückfrage“ (fragt dann) | `rueckfrage_tage()` nur für den Schlüssel „silvester“ | **grün -> Befund 11**; mit v606: 1 rot (v606::test_ein_weiterer_kalendertag_mit_rueckfrage) |
| 1.9.176 Nr. 8c – … und lässt sich so anlegen | `_pruefen()` lehnt „fragen“ ab | **grün -> Befund 11** (derselbe); mit v606: 1 rot (v606::test_ein_weiterer_kalendertag_mit_rueckfrage) |
| 1.9.177 Nr. 1a – gemerkt beim Speichern der Lohnstammdaten | `set_employee_payroll()`: `personalnummer_merken()` weg | 7 rot: v593::test_nummernwechsel_sperrt_die_alte_nummer, ::test_nach_austritt_und_geleerter_nummer_gesperrt, ::test_pruefskript_nennt_die_gemerkten_nummern, v595::test_admin_gibt_eine_fruehere_nummer_frei, ::test_nur_der_admin, ::test_eine_getragene_nummer_bleibt, v601::test_liste_nennt_wer_eine_fruehere_nummer_traegt |
| 1.9.177 Nr. 1b – Gleichsetzung: bisherige Mitarbeiternummer beim Ändern | `routers/employees.py::update_employee()`: bisherige nicht gemerkt | 2 rot: v593::test_gleichsetzung_sperrt_die_mitarbeiternummer, v601::test_bei_gleichsetzung_auch_die_mitarbeiternummer |
| 1.9.177 Nr. 1c – Gleichsetzung: neue Mitarbeiternummer beim Ändern | dito, neue nicht gemerkt | 1 rot: v593::test_gleichsetzung_sperrt_die_mitarbeiternummer |
| 1.9.177 Nr. 1d – Gleichsetzung: Mitarbeiternummer beim Anlegen | `create_employee()`: nicht gemerkt | **grün -> Befund 12**; mit v606: 1 rot (v606::test_anlegen_merkt_die_mitarbeiternummer_bei_gleichsetzung) |
| 1.9.177 Nr. 1e – das Einschalten der Gleichsetzung merkt nichts | `update_time_settings()`: beim Einschalten alle Mitarbeiternummern gemerkt | **grün -> Befund 13**; mit v606: 1 rot (v606::test_einschalten_der_gleichsetzung_merkt_nichts) |
| 1.9.177 Nr. 2 – dieselbe Person bekommt ihre Nummer wieder | `personalnummer_gesperrt()` sperrt auch die eigene | 2 rot: v593::test_nummernwechsel_sperrt_die_alte_nummer, ::test_gleichsetzung_sperrt_die_mitarbeiternummer |
| 1.9.177 Nr. 3a – auch ein Tippfehler bleibt gemerkt | `set_employee_payroll()`: beim Wechsel die übrigen Nummern der Person gelöscht | 5 rot: v593::test_nummernwechsel_sperrt_die_alte_nummer, ::test_pruefskript_nennt_die_gemerkten_nummern, v595::test_admin_gibt_eine_fruehere_nummer_frei, ::test_nur_der_admin, v601::test_liste_nennt_wer_eine_fruehere_nummer_traegt |
| 1.9.177 Nr. 3b – freigeben nur, solange sie niemand trägt | `personalnummer_freigeben()`: Prüfung des Trägers übergangen | 4 rot: v595::test_eine_getragene_nummer_bleibt, ::test_eine_mitarbeiternummer_bei_gleichsetzung_bleibt, v601::test_liste_nennt_wer_eine_fruehere_nummer_traegt, ::test_bei_gleichsetzung_auch_die_mitarbeiternummer |
| 1.9.177 Nr. 3c – nur der Admin, Büro – Finanzen nicht | `permissions.py`: `PERSONALNUMMER_FREIGEBEN_ROLLEN` mit Büro – Finanzen | 2 rot: v595::test_nur_der_admin, ::test_seite |
| 1.9.177 Nr. 3d – Eintrag in der Änderungshistorie | `personalnummer_freigeben()` ohne `record_audit_entry()` | 1 rot: v595::test_admin_gibt_eine_fruehere_nummer_frei |
| 1.9.177 Nr. 3e – Warnung im Dialog | `settings.html`: Warnsatz geändert | 1 rot: v595::test_seite |
| 1.9.177 Nr. 3 – Notiz für L1b (abgelegter Export sperrt dauerhaft) | keine | L1b ist nicht gebaut |
| 1.9.177 Nr. 4a – Liste zeigt „früher: …“ | `_payroll_dict()`: `fruehere_personalnummern` leer | 4 rot: v593::test_nummernwechsel_sperrt_die_alte_nummer, ::test_nach_austritt_und_geleerter_nummer_gesperrt, v601::test_liste_nennt_wer_eine_fruehere_nummer_traegt, ::test_bei_gleichsetzung_auch_die_mitarbeiternummer |
| 1.9.177 Nr. 4b – Meldung nennt, wem sie gehörte | `personalnummer_gesperrt()`: Meldung ohne Namen | 3 rot: v593::test_nummernwechsel_sperrt_die_alte_nummer, ::test_nach_austritt_und_geleerter_nummer_gesperrt, ::test_gleichsetzung_sperrt_die_mitarbeiternummer |
| 1.9.177 Nr. 4c – die Seite zeigt „früher:“ | `settings.html`: „früher:“ ersetzt | 1 rot: v595::test_seite |
| 1.9.177 Nr. 5a – Migration übernimmt die DATEV-Nummern | `alembic/versions/1e425fe7faa6_…py::nummern_uebernehmen()`: DATEV-Nummern übergangen | 2 rot: v593::test_migration_auf_einem_bestand_sqlite, ::test_migration_auf_einem_bestand_postgresql |
| 1.9.177 Nr. 5b – … bei Gleichsetzung die Mitarbeiternummern | dito, Mitarbeiternummern übergangen | 2 rot: v593::test_migration_auf_einem_bestand_sqlite, ::test_migration_auf_einem_bestand_postgresql |
| 1.9.177 Nr. 5 – „frühere Nummern kennt der Bestand nicht“ | keine | Aussage über den Bestand vor der Migration, kein Verhalten |
| 1.9.177 Nr. 6a – Prüfskript zählt die gemerkten Nummern | `scripts/pruefe_zeitregeln.py`: Zahl um 1 verfälscht | 1 rot: v593::test_pruefskript_nennt_die_gemerkten_nummern |
| 1.9.177 Nr. 6b – fremde gemerkte Nummer ist ein Befund (Rückgabe 1) | dito: Befund nur als Zeile | 1 rot: v593::test_pruefskript_nennt_die_gemerkten_nummern |
| 1.9.178 Nr. 1a – Rückfrage an einem aktiven betriebsfreien Tag | `schlechtwetter.py::betriebsfrei()` immer leer | 3 rot: v594::test_betriebsfreier_tag_fragt_nach, ::test_betriebsfrei_und_gebucht_in_einer_meldung, ::test_die_monteurin_wird_gefragt |
| 1.9.178 Nr. 1b – ein abgeschalteter fragt nicht | `betriebsfrei()` ohne Bedingung `active` | 1 rot: v594::test_abgeschalteter_betriebsfreier_tag_fragt_nicht |
| 1.9.178 Nr. 2a – eine Meldung, zuerst der betriebsfreie Tag | `SchlechtwetterWarnung`: Teile der Meldung umgedreht | 1 rot: v594::test_betriebsfrei_und_gebucht_in_einer_meldung |
| 1.9.178 Nr. 2b – … auch in der Liste `warnungen` | `warnungen()` umgedreht | 1 rot: v594::test_betriebsfrei_und_gebucht_in_einer_meldung |
| 1.9.178 Nr. 2c – „Trotzdem eintragen“ gilt für alles | `eintragen()`: der betriebsfreie Tag fragt auch mit `trotzdem` | 2 rot: v594::test_betriebsfreier_tag_fragt_nach, ::test_die_monteurin_wird_gefragt |
| 1.9.178 Nr. 3 – Bestätigen fragt nicht noch einmal | `schlechtwetter.py::entscheiden()`: am betriebsfreien Tag `SchlechtwetterWarnung` | **grün -> Befund 14**; mit v606: 1 rot (v606::test_bestaetigen_fragt_nicht_noch_einmal) |

### Befunde

Je Befund: die Gegenprobe blieb auf den vorhandenen Tests grün; neuer Test in `tests/test_v606_festlegungen_174_179.py`; dieselbe Gegenprobe noch
einmal mit der Datei: rot (Protokoll `n4/g/b3/lauf5.txt`, endgültiger Stand der Datei).

1. **1.9.175 Nr. 1, „nur Montag bis Freitag“** -- `_datum_passt()` ohne Wochentag blieb grün: bei Tarif ist die Sollzeit am Wochenende ohnehin 0,
   der Kalendertag fällt dann über „nur mit Sollzeit“ weg. Der Schalter wirkt nur bei eigener Sollzeit am Wochenende. Neu
   `test_nur_mo_fr_auch_bei_eigener_sollzeit_am_wochenende` (Tom So 4,00 h: So 24.12.2028 bleibt 4,00 h, kein Kalendertag; mit „nur Mo–Fr“ aus
   7,00 h). Wiederholung: 1 rot.
2. **1.9.175 Nr. 6, Änderung gilt auch für zurückliegende Jahre** -- „Kalendertag nur ab heute“ blieb grün (alle Tests liegen nach dem festen Tag
   10.11.2026). Neu `test_aenderung_gilt_auch_fuer_zurueckliegende_jahre` (Heiligabend auf 6,50 h geändert -> Mi 24.12.2025 Soll 6,50 h,
   Freistellung 6,50 h). Wiederholung: 1 rot.
3. **1.9.175 Nr. 6, „die Seite sagt das“** -- Satz aus `settings.html` entfernt blieb grün (auch `klicktest_arbeitszeitkalender` liest ihn nicht).
   Neu `test_seite_sagt_zurueckliegende_jahre` (der Satz im Block `kalenderBlock`). Wiederholung: 1 rot.
4. **1.9.175 Nr. 7, ab heute** -- `naechste()` mit vergangenen Tagen blieb grün (die Vorgaben 24.12./31.12. liegen nach dem festen Tag). Neu
   `test_naechste_ab_heute` und `test_naechste_ganz` (heute 01.03.2027, dazu Rosenmontag 15.02. aktiv und ein abgeschaltetes Betriebsfest 01.06.).
   Wiederholung: 2 rot.
5. **1.9.175 Nr. 7, dieses und das nächste Jahr** -- `jahre=3` blieb grün: im dritten Jahr (2028) fallen Heiligabend und Silvester auf einen Sonntag
   und fallen über „nur Mo–Fr“ weg. Abgedeckt von `test_naechste_ganz` (2029 brächte drei Tage dazu). Wiederholung: 1 rot.
6. **1.9.175 Nr. 7, ohne Samstag und Sonntag** -- ohne Filter blieb grün (2026/2027 fallen beide Tage auf Do/Fr). Neu
   `test_naechste_ohne_samstag_und_sonntag`. Wiederholung: 2 rot (mit `test_naechste_ganz`).
7. **1.9.175 Nr. 7, nur aktive Tage** -- `eintraege()` statt `aktive()` blieb grün (keine abgeschalteten Tage in den Tests). Neu
   `test_naechste_nur_aktive_tage`. Wiederholung: 2 rot (mit `test_naechste_ganz`).
8. **1.9.176 Nr. 1, Sammeleintrag: eine Antwort für alle** -- Antwort nur für die erste Person blieb grün (der Sammeleintrag über Silvester war nur
   ohne Antwort geprüft; mit Antwort nur im Klicktest mit einer gewerblichen Person). Neu `test_sammeleintrag_eine_antwort_fuer_alle` (Mia, Tom
   gewerblich, Kim kaufmännisch, „frei“ -> False, False, leer). Wiederholung: 1 rot.
9. **1.9.176 Nr. 6, gebuchte Arbeit an Silvester kommt dazu** -- geprüft war nur Heiligabend (die Querprobe ohne Einschränkung ist dort rot). Neu
   `test_gebuchte_arbeit_an_silvester_kommt_dazu` (4,00 h gebucht am Do 31.12.2026, Freistellung 7,50 h bleibt). Wiederholung: 1 rot.
10. **1.9.176 Nr. 7, die Liste „Zeiten → Prüfen“ nennt die Antwort** -- `antragHtml()` (offene Anträge unter „Prüfen“) ohne den Zusatz blieb grün;
    die Liste „Abwesenheiten“ (`abwesenheitHtml()`) prüft nur `klicktest_silvester`. Neu `test_beide_listen_unter_zeiten_nennen_die_antwort`
    (node, beide Funktionen über die Helfer aus `test_v518`, mit True/False/leer). Wiederholung: 1 rot.
11. **1.9.176 Nr. 8, jeder weitere Kalendertag kann „Rückfrage“ bekommen** -- zwei Gegenproben blieben grün: die Rückfrage nur für den Schlüssel
    „silvester“, und Anlegen mit „fragen“ abgelehnt (geprüft war nur der vorbelegte Silvester). Neu `test_ein_weiterer_kalendertag_mit_rueckfrage`
    (Büro – Finanzen legt „Brückentag“ 07.12. mit „Rückfrage“ an, ein Urlaub 07.–11.12.2026 fragt mit 409 und `rueckfrage`, mit Antwort 200).
    Wiederholung: beide 1 rot.
12. **1.9.177 Nr. 1, Gleichsetzung: Anlegen merkt die Mitarbeiternummer** -- nicht gemerkt blieb grün (geprüft war nur das Ändern; das Anlegen nur als
    abgelehnter Fall). Neu `test_anlegen_merkt_die_mitarbeiternummer_bei_gleichsetzung`. Wiederholung: 1 rot.
13. **1.9.177 Nr. 1, das Einschalten der Gleichsetzung merkt nichts** -- Merken beim Einschalten blieb grün. Neu
    `test_einschalten_der_gleichsetzung_merkt_nichts` (PUT `/api/time-backoffice/settings` mit Gleichsetzung -> nichts gemerkt). Wiederholung: 1 rot.
14. **1.9.178 Nr. 3, Bestätigen fragt nicht noch einmal** -- eine Rückfrage beim Bestätigen am betriebsfreien Tag blieb grün (bestätigt wurde nur an
    einem gewöhnlichen Tag). Neu `test_bestaetigen_fragt_nicht_noch_einmal` (Uwe beantragt am betriebsfreien Mo 07.12.2026 mit „trotzdem“, der Admin
    bestätigt: 200, Abwesenheit da). Wiederholung: 1 rot.

Dazu, kein Befund: `test_abwesenheit_des_kalenders_wird_nicht_gespeichert` (1.9.175 Nr. 2) -- die Gegenprobe war rot, aber nur mittelbar (siehe
Bemerkungen); der Test prüft die Aussage direkt (keine neue Zeile in der Sitzung, keine Abwesenheit, kein Antrag). Wiederholung: rot.

`tests/test_v606_festlegungen_174_179.py` allein: 15 passed (`"$PY" -m pytest -q -p no:cacheprovider tests/test_v606_festlegungen_174_179.py`).

### Bemerkungen

- **176_3e zuerst falsch gebaut**: die erste Fassung ersetzte in `urlaub_ersetzt()` die genehmigten Abwesenheiten durch die Anträge (Alias-Import);
  rot wurden v592::test_alter_urlaub_ohne_antwort_gilt_wie_der_vorschlag und v599::test_silvester_als_ganzer_urlaubstag_fehlt -- der erste, weil er
  eine Abwesenheit ohne Antrag anlegt, also aus dem falschen Grund. Neu gebaut als 176_3e2 (offene Anträge zusätzlich zu den Abwesenheiten): rot nur
  v599::test_silvester_als_ganzer_urlaubstag_fehlt („offen: zählt noch nicht“, seit 1.9.187) -- also kein Befund; ein dafür schon geschriebener Test
  in v606 wurde wieder entfernt.
- **175_2a nur mittelbar rot**: die Gegenprobe (`abwesenheiten()` speichert je Tag eine Abwesenheit) machte nur
  v599::test_silvester_als_ganzer_urlaubstag_fehlt rot, weil die gespeicherte Zeile die spätere Genehmigung des Urlaubs mit „bereits eine genehmigte
  Abwesenheit“ ablehnt. Rot aus der gespeicherten Zeile, aber an einer fremden Stelle; deshalb der direkte Test in v606 (siehe oben).
- **175_1f doppelte Sicherung**: „aktiv“ prüfen sowohl `aktive()` als auch `_datum_passt()`; jede allein auszuhebeln ändert nichts. Die Gegenprobe
  hebelt beide aus.
- **175_1e**: ohne die Prüfung in `_pruefen()` fängt die Datenbank-Bedingung den zweiten Eintrag für dasselbe Datum weiter ab (422 mit der Meldung aus
  `_commit()`); rot wird der Test über den Wortlaut der Meldung. Der Schutz selbst ist doppelt.
- **175_3d (nach dem Austritt)**: rot nur in `test_v585_sollzeit.py::test_eintritt_und_austritt` -- der Kalender folgt der Sollzeit, ein
  kalenderbezogener Test nach dem Austritt fehlt (für den Eintritt gibt es `test_vor_dem_eintritt_kein_heiligabend`). Kein Befund, weil die Sperre an
  einer Stelle sitzt (`beschaeftigt_am()`), die dort geprüft ist.
- **175_7b**: die Festlegung „dieses und das nächste Jahr“ war auf diesem Stand nur zufällig unsichtbar: 2028 fallen beide Vorgaben auf einen
  Sonntag (siehe Befund 5).
- **176_7b/7c** liefen als Klicktest-Gegenproben (`klicktest_silvester`, je 1–2 min; Grundlauf vorher Rückgabe 0). Die Listen in „Zeiten“ gibt es zweimal
  (`antragHtml` unter „Prüfen“, `abwesenheitHtml` unter „Abwesenheiten“); nur die zweite prüfte bisher etwas -> Befund 10.
- **177 Nr. 5 (Migration)**: die Gegenproben liefen in der Migrationsdatei `alembic/versions/1e425fe7faa6_personalnummern_gesperrt.py`, nicht unter
  `app/`; beide Migrationstests (SQLite und PostgreSQL, Wegwerf-Schema) wurden rot, die Datei ist byte-genau zurück.
- **Wortlaut und Code**: keine Abweichung gefunden. Hinweis zu 1.9.175 Nr. 1: der Schalter „nur Montag bis Freitag“ wirkt im Rechnen nur bei
  eigener Sollzeit am Wochenende (Tarif: Sa/So 0) und in der Liste unter „Zeiten → Abwesenheiten“.
- In der Arbeitskopie ist `app/`, `scripts/` und `alembic/` unverändert (`git status --short`: nur die Änderungen des Ausgangsstands 1.9.192–1.9.194
  und die neue Testdatei `tests/test_v606_festlegungen_174_179.py`). Die Hilfsdateien liegen unter `n4/g/b3/`.

### Zahlen

24 Festlegungen; 77 Gegenproben (davon 2 Klicktest-Gegenproben), dazu 1 Querprobe (176_6x) und 1 verworfene Fassung (176_3e); auf den
vorhandenen Tests 62 rot, 15 grün -> 14 Befunde (8b und 8c sind einer) in 9 Festlegungen (1.9.175 Nr. 1, 6, 7; 1.9.176 Nr. 1, 6, 7, 8; 1.9.177
Nr. 1; 1.9.178 Nr. 3), alle mit neuem Test in v606 jetzt rot; 5 Teilaussagen ohne Gegenprobe (kein Löschweg ×2, Export L1b, Notiz L1b, Aussage
über den Bestand) -- jede der 24 Festlegungen hat mindestens eine Gegenprobe.

## 1.9.200: Festlegungen 1.9.180–1.9.185

13 Festlegungen (1.9.180 Nr. 1–2, 1.9.181 Nr. 1–3, 1.9.184 Nr. 1–2, Werkzeug 1.9.183 Nr. 1–3 und 1.9.185 Nr. 1–3), 42 Gegenproben und eine Nullprobe,
29 sofort rot, 13 grün -> Befunde an 10 Aussagen, 10 neue Tests in `tests/test_v607_festlegungen_180_185.py`, danach alle rot; die Nullprobe blieb grün,
wie sie soll. Ohne Gegenprobe: 5 Teilaussagen. Hinweis: `test_v564` zählt auf diesem Stand 33/32 statt der 31/30 aus dem Archiv von 1.9.183 -- `GET
/api/planning` braucht seit dem Arbeitszeitkalender auf der Tafel (1.9.188) zwei Abfragen mehr; die Prüfung (gleich viele) bleibt.

| Festlegung | Gegenprobe | Ergebnis |
|---|---|---|
| 1.9.180 Nr. 1 a – Kalendertag nur an einem Tag mit Sollzeit (Sollzeit) | `app/sollzeit.py::soll_zeitraum()`: Kalendertag auch bei Tageswert 0 (`and wert > 0` raus) | 7 rot: test_v591::test_teilzeit_an_einem_tag_mit_sollzeit_voll, ::test_ohne_sollzeit_am_wochentag_weder_sollzeit_noch_freistellung, test_v599::test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll, test_v600::test_freistellungen_nur_mit_sollzeit, ::test_tafel_zeigt_die_betroffenen_abwesend, ::test_gespeicherte_abwesenheit_geht_vor, ::test_vorschlag_rechnet_den_tag_ohne_die_betroffenen |
| 1.9.180 Nr. 1 b – Kalendertag (Freistellung, Rückfrage) nur mit Sollzeit über 0 | `app/arbeitszeitkalender.py::kalendertage_im_zeitraum()`: Filter `soll[t] > 0` raus | 3 rot: test_v591::test_ohne_sollzeit_am_wochentag…, ::test_vor_dem_eintritt_kein_heiligabend, test_v599::test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll |
| 1.9.180 Nr. 1 c – gilt für jeden Kalendertag, nicht nur Heiligabend | `kalendertage_im_zeitraum()`: Bedingung nur für den Schlüssel „heiligabend“ (Silvester ohne) | 3 rot: dieselben drei wie 1 b |
| 1.9.180 Nr. 1 d – Kalendertag mit eigener Sollzeit setzt sie voll | `soll_zeitraum()`: `min(Tageswert, Kalender)` statt Kalenderwert (anteilig) | 2 rot: test_v591::test_teilzeit_an_einem_tag_mit_sollzeit_voll, test_v599::test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll |
| 1.9.180 Nr. 2 a – Schlechtwetter nennt dort „keine Sollzeit“ | `app/schlechtwetter.py::grund_gegen()`: Kalendertag über `fuer_tag(aktive(db), …)` ohne Sollzeitbedingung statt `kalendertag()` | 1 rot: test_v591::test_ohne_sollzeit_am_wochentag_weder_sollzeit_noch_freistellung |
| 1.9.180 Nr. 2 b – halber Urlaubstag dort angenommen | `app/absence_requests.py::_antrag_anlegen()`: Prüfung „halber Tag am Kalendertag“ ohne Sollzeitbedingung | Runde 1 grün (122 passed) → **Befund**; Runde 2: 1 rot: test_v607::test_halber_urlaubstag_an_einem_kalendertag_ohne_sollzeit (422 statt 200) |
| 1.9.180 Nr. 2 c – … und zählt 0 | `app/sollzeit.py::abwesenheit_tage()`: halber Tag an einem Tag ohne Sollzeit zählt (0,5) | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_halber_urlaubstag_an_einem_kalendertag_ohne_sollzeit (0,5 statt 0 Tage) |
| 1.9.181 Nr. 1 a – freigeben nur, wenn niemand sie trägt (409) | `app/time_backoffice.py::personalnummer_freigeben()`: Prüfung `personalnummer_halter()` übergangen | 4 rot: test_v595::test_eine_getragene_nummer_bleibt, ::test_eine_mitarbeiternummer_bei_gleichsetzung_bleibt, test_v601::test_liste_nennt_wer_eine_fruehere_nummer_traegt, ::test_bei_gleichsetzung_auch_die_mitarbeiternummer |
| 1.9.181 Nr. 1 b – auch nicht die Person, der sie gemerkt ist (heutige Nummer nicht freigebbar) | `personalnummer_freigeben()`: Halter = gemerkte Person zählt nicht | 1 rot: test_v595::test_eine_getragene_nummer_bleibt |
| 1.9.181 Nr. 1 c – bei „DATEV-Nr. = ERP-Nr.“ die Mitarbeiternummer | `personalnummer_halter()`: Mitarbeiternummer nie geprüft | 2 rot: test_v595::test_eine_mitarbeiternummer_bei_gleichsetzung_bleibt, test_v601::test_bei_gleichsetzung_auch_die_mitarbeiternummer |
| 1.9.181 Nr. 1 d – Mitarbeiternummer nur bei Gleichsetzung | `personalnummer_halter()`: Mitarbeiternummer auch ohne Gleichsetzung | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_ohne_gleichsetzung_traegt_eine_mitarbeiternummer_keine_personalnummer (409 statt 200) |
| 1.9.181 Nr. 1 e – Ablehnung mit dem Namen | Meldung von `PersonalnummerGehalten` ohne Namen („eine Person“) | 2 rot: test_v595::test_eine_getragene_nummer_bleibt, ::test_eine_mitarbeiternummer_bei_gleichsetzung_bleibt |
| 1.9.181 Nr. 2 a – Freigeben löscht den Eintrag, nicht mehr unter „früher“ | `personalnummer_freigeben()`: `db.delete(row)` übersprungen | 1 rot: test_v595::test_admin_gibt_eine_fruehere_nummer_frei |
| 1.9.181 Nr. 2 b – steht in der Änderungshistorie | `record_audit_entry()` nicht aufgerufen | 1 rot: test_v595::test_admin_gibt_eine_fruehere_nummer_frei |
| 1.9.181 Nr. 2 c – … wem sie gehörte | `old_value` ohne Namen | 1 rot: test_v595::test_admin_gibt_eine_fruehere_nummer_frei |
| 1.9.181 Nr. 2 d – … welche Nummer | `entity_id` „?“ | 1 rot: test_v595::test_admin_gibt_eine_fruehere_nummer_frei |
| 1.9.181 Nr. 2 e – … wer (frei gab) | `actor_name="unbekannt"` statt aus der Anfrage | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_die_freigabe_nennt_wer_und_wann |
| 1.9.181 Nr. 2 f – … und wann | keine: der Zeitpunkt ist die Spaltenvorgabe `AuditLog.occurred_at`, nicht Teil von `personalnummer_freigeben()`; der neue Test prüft nur, dass er gesetzt ist | – |
| 1.9.181 Nr. 3 a – Warnung nennt „nie abgerechnet“ | `settings.html::pnrFreigabeOeffnen()`: Satz ohne „nie abgerechnet“ | 1 rot: test_v595::test_seite |
| 1.9.181 Nr. 3 b – Warnung nennt „Tippfehler“ | `pnrFreigabeOeffnen()`: ohne „(z. B. nach einem Tippfehler)“ | Runde 1 grün (Suite) → **Befund**; Runde 2: 1 rot: test_v607::test_dialog_ohne_begruendung_die_warnung_nennt_den_fall |
| 1.9.181 Nr. 3 c – keine Begründung (Server verlangt keine) | `app/schemas.py::PersonalnummerFreigabeIn`: Pflichtfeld `begruendung` | 6 rot: test_v595::test_admin_gibt_eine_fruehere_nummer_frei, ::test_eine_getragene_nummer_bleibt, ::test_eine_mitarbeiternummer_bei_gleichsetzung_bleibt, ::test_eine_nicht_gemerkte_nummer, test_v601::test_liste_nennt_wer_eine_fruehere_nummer_traegt, ::test_bei_gleichsetzung_auch_die_mitarbeiternummer |
| 1.9.181 Nr. 3 d – keine Begründung im Dialog | `settings.html`: Textfeld „Begründung“ im Dialog `pnrFreigabeDialog` | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_dialog_ohne_begruendung_die_warnung_nennt_den_fall |
| 1.9.183 Nr. 1 a – Abräumen vor dem Zählen | `tests/test_v564_plantafel_leistung.py::Zaehler.__enter__`: ohne `gc.collect()` | 1 rot: test_v564::test_abraeumen_mitten_im_zaehlen_verfaelscht_nichts (33, 32) |
| 1.9.183 Nr. 1 b – keine Speicherbereinigung während des Zählens | `Zaehler.__enter__`: ohne `gc.disable()` | 1 rot: test_v564::test_zaehler_stellt_die_speicherbereinigung_wieder_her[mitten_im_zaehlen] |
| 1.9.183 Nr. 1 c – gilt für jede Zählung (`Zaehler`), nicht nur den einen Test | `Zaehler.__enter__`: Abräumen und Ausschalten nur, wenn `PYTEST_CURRENT_TEST` test_alte_einsaetze_kosten_nichts nennt | 2 rot: test_v564::test_abraeumen_mitten_im_zaehlen_verfaelscht_nichts, ::test_zaehler_stellt_die_speicherbereinigung_wieder_her[mitten_im_zaehlen] |
| 1.9.183 Nr. 1 d – Leeraufruf nur dort, wo die Vorgabe ihn nennt | keine: Aussage über den Aufbau einer Testdatei (wo ein Aufruf steht), kein Verhalten; ein weiterer Leeraufruf verfälschte nichts | – |
| 1.9.183 Nr. 2 a – Reihenfolge immer mitgeschrieben (keine Option) | `tests/reihenfolge.py::einrichten()`: nur mit Umgebungsvariable `ERP_TEST_REIHENFOLGE_AN` | 2 rot: test_v596::test_parallel_je_arbeitsprozess_eine_datei, ::test_ohne_n_eine_datei_haupt |
| 1.9.183 Nr. 2 b – nur der letzte Lauf bleibt | `einrichten()`: Ordner zu Beginn nicht geleert | 1 rot: test_v596::test_parallel_je_arbeitsprozess_eine_datei (gw9.txt vom letzten Lauf bleibt) |
| 1.9.183 Nr. 2 c – nach einem roten Lauf den Ordner kopieren | keine: Handlungsanweisung | – |
| 1.9.183 Nr. 3 a – nachgestellt wird die Reihenfolge der Dateien | `reihenfolge.dateien()`: sortiert statt in Reihenfolge | 1 rot: test_v596::test_nachstellen_nennt_die_dateien_in_ihrer_reihenfolge |
| 1.9.183 Nr. 3 b – nicht die Zeit dazwischen | keine: das Werkzeug stellt keine Zeit nach (bewusst nicht gebaut), es gibt nichts auszuhebeln | – |
| 1.9.183 Nr. 3 c – Last der übrigen nur durch gleichzeitiges Nachstellen aller | `reihenfolge.main()`: jeden Prozess abwarten, bevor der nächste startet | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_nachstellen_startet_alle_zugleich_je_mit_seinen_dateien |
| 1.9.184 Nr. 1 a – gezählt werden alle Status | `scripts/pruefe_zeitregeln.py::_urlaub_ohne_antwort()`: nur genehmigte | 1 rot: test_v592::test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort |
| 1.9.184 Nr. 1 b – … auch abgelehnte | `_urlaub_ohne_antwort()`: abgelehnte ausgenommen | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_pruefskript_zaehlt_auch_abgelehnte |
| 1.9.184 Nr. 1 c – je Status für sich genannt | ohne Aufteilung nach Status | 1 rot: test_v592::test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort |
| 1.9.184 Nr. 2 a – nur, wo die Frage heute gestellt würde | Prüfung `rueckfrage_tage()` übergangen | 1 rot: test_v592::test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort |
| 1.9.184 Nr. 2 b – … gewerblich | Nachbau der Prüfung im Skript ohne Gruppe (Nullprobe mit allen drei Bedingungen: grün) | 1 rot: test_v592::test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort |
| 1.9.184 Nr. 2 c – … Montag bis Freitag | Nachbau ohne Wochentag | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_pruefskript_nur_wo_heute_gefragt_wuerde |
| 1.9.184 Nr. 2 d – … Sollzeit über 0 | Nachbau ohne Sollzeit | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_pruefskript_nur_wo_heute_gefragt_wuerde |
| 1.9.185 Nr. 1 a – Name ohne Pfad unter `%TEMP%\erp-klicktests` | `scripts/cdp_klicktest.py::klicktest_ordner()`: Name relativ zum Projektordner (wie bis 1.9.184) | 1 rot: test_v597::test_ohne_angabe_und_name_unter_dem_klicktest_ordner |
| 1.9.185 Nr. 1 b – Vorgabe ist `%TEMP%\erp-klicktests` | `KLICKTEST_ORDNER` ohne Umgebung im Projektordner | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_ohne_umgebung_unter_temp_erp_klicktests |
| 1.9.185 Nr. 1 c – gilt für `--ausgabe` (klicktest_alle.py) | `scripts/klicktest_alle.py`: `args.ausgabe` an `klicktest_ordner()` vorbei | 1 rot: test_v597::test_beide_werkzeuge_nehmen_die_regel |
| 1.9.185 Nr. 1 d – gilt für `--arbeitsordner` (cdp_klicktest.py) | `_ablauf()`: `args.arbeitsordner` an `klicktest_ordner()` vorbei | 1 rot: test_v597::test_beide_werkzeuge_nehmen_die_regel |
| 1.9.185 Nr. 2 a – direkt unter einem Laufwerk abgelehnt | `klicktest_ordner()`: Prüfung aus | 1 rot: test_v597::test_direkt_unter_einem_laufwerk_abgelehnt |
| 1.9.185 Nr. 2 b – jeder tiefere erlaubt, auch außerhalb von `%TEMP%` | `klicktest_ordner()`: nur unter `%TEMP%` | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_ein_tieferer_ordner_ausserhalb_von_temp_bleibt |
| 1.9.185 Nr. 3 a – Ordner bleiben nach dem Lauf liegen | `cdp_klicktest.py::_ablauf()`: `shutil.rmtree(ordner)` im `finally` | Runde 1 grün → **Befund**; Runde 2: 1 rot: test_v607::test_kein_werkzeug_loescht_seinen_ordner |
| 1.9.185 Nr. 3 b – aufgeräumt wird von Hand | keine: Handlungsanweisung | – |

### Befunde

Neue Datei `tests/test_v607_festlegungen_180_185.py` (10 Tests, Docstrings „Seit 1.9.200 (Gegenprobe zu Festlegung …)“, allein grün:
`10 passed`). Kein Befund ist ein Fehler im Programm -- jedes Mal tat der Code, was die Festlegung sagt, nur prüfte kein Test es.

1. **1.9.180 Nr. 2** (2 b, 2 c): kein Test für einen halben Urlaubstag an einem Kalendertag ohne Sollzeit; Annahme und Zählung blieben
   ausgehebelt grün. Neu `test_halber_urlaubstag_an_einem_kalendertag_ohne_sollzeit` (Tom Di–Do 3,00 h, Mo 24.12.2029: 200, gespeichert
   mit halber_tag, 0 Tage, 0 h). Wiederholung: 2 b rot (422 „gilt Heiligabend …“), 2 c rot (0,5 statt 0).
2. **1.9.181 Nr. 1** (1 d): dass eine Mitarbeiternummer ohne Gleichsetzung die Nummer nicht trägt, prüfte niemand. Neu
   `test_ohne_gleichsetzung_traegt_eine_mitarbeiternummer_keine_personalnummer`. Wiederholung: rot (409 „trägt heute Tom Monteur“).
3. **1.9.181 Nr. 2** (2 e): „wer“ im Eintrag ungeprüft (die Test-App setzt keinen Anfragekontext). Neu `test_die_freigabe_nennt_wer_und_wann`
   (Kontext über `set_audit_context()` wie test_v463, Konto und Name, Zeitpunkt gesetzt). Wiederholung: rot („unbekannt“ statt „Admin Anna“).
4. **1.9.181 Nr. 3** (3 b, 3 d): die Suite prüfte nur „nie abgerechnet“ und kein Feld im Dialog. Neu
   `test_dialog_ohne_begruendung_die_warnung_nennt_den_fall` (kein textarea/input/select im Dialog, Senden nur `JSON.stringify({nummer})`,
   der Satz mit „Tippfehler“). Wiederholung: 3 b rot, 3 d rot (`<textarea` gefunden).
5. **1.9.183 Nr. 3** (3 c): `main()` ohne `--nur-zeigen` lief in keinem Test. Neu `test_nachstellen_startet_alle_zugleich_je_mit_seinen_dateien`
   (`subprocess` im Modul durch eine Attrappe ersetzt: erst alle Starts, dann das Warten; je Prozess genau seine Dateien). Wiederholung: rot
   (start, warten, start, warten …).
6. **1.9.184 Nr. 1** (1 b): kein abgelehnter Antrag im Test. Neu `test_pruefskript_zaehlt_auch_abgelehnte` („4 (genehmigt 1, offen 1,
   abgelehnt 1, zurückgezogen 1)“). Wiederholung: rot.
7. **1.9.184 Nr. 2** (2 c, 2 d): der Sonntag 31.12.2028 schloss im Test schon die Sollzeit aus (Tarif 0 am Sonntag), eine Person ohne
   Sollzeit am Wochentag gab es nicht -- „Mo–Fr“ und „Sollzeit über 0“ waren nicht getrennt geprüft. Neu
   `test_pruefskript_nur_wo_heute_gefragt_wuerde` (Tom Di–Do am Mo 31.12.2029, Ole mit eigenen Werten auch sonntags am So 31.12.2028, Mia
   als Gegenstück: „1 (genehmigt 1)“). Wiederholung: 2 c rot, 2 d rot; die Nullprobe (Nachbau mit allen drei Bedingungen) bleibt grün.
8. **1.9.185 Nr. 1** (1 b): alle Tests setzten `ERP_KLICKTEST_ORDNER`, die Vorgabe `%TEMP%\erp-klicktests` lief nie. Neu
   `test_ohne_umgebung_unter_temp_erp_klicktests` (nichts wird angelegt). Wiederholung: rot (Ordner im Projektordner).
9. **1.9.185 Nr. 2** (2 b): der „tiefere“ Pfad des Tests lag unter tmp_path, also unter `%TEMP%`. Neu
   `test_ein_tieferer_ordner_ausserhalb_von_temp_bleibt` (`<Laufwerk>\erp_v607_gibt_es_nicht\lauf`, es entsteht nichts). Wiederholung: rot
   (SystemExit „nur unter %TEMP%“).
10. **1.9.185 Nr. 3** (3 a): nichts prüfte, dass die Werkzeuge ihre Ordner liegen lassen. Neu `test_kein_werkzeug_loescht_seinen_ordner`
    (AST über cdp_klicktest.py und klicktest_alle.py: kein rmtree, rmdir, unlink, removedirs, os.remove). Wiederholung: rot
    (`cdp_klicktest.py:1548 rmtree`).

### Bemerkungen

- 1.9.183 Nr. 1 a: rot mit (33, 32) statt der (31, 30) aus dem Archiv -- `GET /api/planning` braucht auf diesem Stand zwei Abfragen mehr
  (vermutlich der Arbeitszeitkalender seit 1.9.188, nicht nachgezählt); dieselbe Art Abweichung (eine weniger).
- 1.9.183 Nr. 1 b: nur `[mitten_im_zaehlen]` rot, `[beim_abmelden]` bleibt grün: dort ersetzt die `_Absicht` aus dem gestörten
  `event.remove` im `__exit__` den AssertionError aus dem Rumpf, `pytest.raises(_Absicht)` fängt sie -- die Prüfung „währenddessen aus“
  greift in diesem Fall nicht. Für die Festlegung reicht der eine rote Test; nur gemeldet.
- 1.9.183 Nr. 2 a/2 b: die gefilterte Ausgabe des Werkzeugs zeigte die Zeile `assert "1 failed, 2 passed, 1 skipped" in lauf.stdout` --
  eine Kontextzeile des Tracebacks, nicht die rote Prüfung. Mit `--tb=short` nachgesehen: rot an Zeile 50 (gw9.txt bleibt) bzw. 64 (kein
  haupt.txt) -- der geprüfte Grund.
- 1.9.180 Nr. 1 a färbt auch vier Tests von test_v600 (Plantafel) rot: `freistellungen()` holt die Sollzeit über `soll_an_tagen()` ->
  `soll_zeitraum()`. Der eigene Filter `soll[t] > 0` in `app/arbeitszeitkalender.py::freistellungen()` (1.9.188) ist hier nicht
  einzeln geprobt -- er gehört zu den Festlegungen von 1.9.188.
- 1.9.181 Nr. 3 b: `klicktest_personalnummer_freigeben` prüft den vollen Warntext (Zeilen 103–106, mit „Tippfehler“) und wäre rot
  geworden; als Klicktest nicht gelaufen, weil der Text in der Vorlage steht und jetzt auch die Suite ihn prüft.
- 1.9.184 Nr. 2 b–d: das Skript fragt `rueckfrage_tage()`, also dieselbe Regel wie der Server. Damit die Gegenprobe nur das Skript trifft,
  ersetzt sie den Aufruf durch einen Nachbau der drei Bedingungen und lässt je eine weg; die Nullprobe (alle drei) war in beiden Runden grün.
- „Nur der Admin gibt frei“ (Archiv-Gegenprobe zu 1.9.181 „Recht der Lohnregeln statt nur Admin“) steht im Wortlaut von Festlegung
  1.9.177 Nr. 3 (neu gefasst), nicht in 1.9.181 Nr. 1–3 -- hier nicht geprobt.
- Gegenproben an Testwerkzeugen (`tests/test_v564_plantafel_leistung.py`, `tests/reihenfolge.py`, `scripts/*.py`) liefen mit demselben
  Werkzeug; der Marker steht dort nicht unter `app/`, die Dateien sind byte-genau zurück (Prüfsumme). `grep GEGENPROBE` über `app/` leer,
  test_v357 grün; `scripts/cdp_klicktest.py` enthält den Marker nur als seine Konstante `GEGENPROBE_MARKER`.
- „Grün“ in Runde 1 heißt grün in den genannten Testgruppen des Themas (Kalender, Personalnummer, Skript, v564, v596, Werkzeug), nicht in
  der ganzen Suite.
- Der Wortlaut aller 13 Festlegungen passt zum Code; keine Abweichung gefunden.
- `git -C wt_b4 status --short` zeigt außer den vorhandenen Änderungen 1.9.192–1.9.194 (8 Dateien, unverändert) und
  `tests/test_v602_…` nur `tests/test_v607_festlegungen_180_185.py`.
