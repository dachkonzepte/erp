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
