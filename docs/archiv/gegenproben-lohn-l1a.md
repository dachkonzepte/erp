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
