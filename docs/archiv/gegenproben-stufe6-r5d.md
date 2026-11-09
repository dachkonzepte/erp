# Gegenproben der Runde Stufe 6, R5d (Nachrunde, ab 1.9.283)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R5c (`docs/archiv/gegenproben-stufe6-r5c.md`): in einer eigenen
Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript) mit dem Marker `GEGENPROBE` ändern, die genannten Tests bzw. den Klicktest laufen
lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler) bzw. der Klicktest endet nicht wie erwartet.

## 1.9.283 (Punkt 1): „Zum Einplanen“ immer offen, schmalere Tagesspalten

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – in „Aufträge“ immer offen | kein Öffnen beim Wechsel (`283_1a`, `283_1d`) | 2 rot: v683::test_auftraege_immer_offen_zurueck_der_gemerkte_zustand (1280 ohne Merken, 1440 „zu“); Klicktest auftraege: „1280 hell/dunkel: Liste offen …“, „1280 Aufträge: Liste offen“ u. a. |
| Nr. 1 – zurück der gemerkte Zustand | kein Zurücksetzen beim Verlassen (`283_1b`, `283_1e`) | 2 rot: v683::test_auftraege_immer_offen_zurueck_der_gemerkte_zustand; Klicktest auftraege: „1280 Kolonnen: Liste zu“ |
| Nr. 1 – das Öffnen merkt nichts | Öffnen merkt „offen“ (`283_1c`) | 4 rot: v683::test_auftraege_immer_offen_zurueck_der_gemerkte_zustand (alle vier Fälle) |
| Nr. 2 – Zuklappen in „Aufträge“ merkt nichts | der Knopf merkt immer (`283_2a`, `283_2b`) | 2 rot: v657::test_nur_der_knopf_merkt, v683::test_knopf_merkt_in_auftraege_nichts; Klicktest auftraege: „1280 Aufträge: zugeklappt, nichts gemerkt“ |
| Nr. 3 – Tage mindestens 84 px | wieder 110 px (`283_3a`, `283_3c`) | 1 rot: v683::test_spalten_und_chips; Klicktest auftraege: bei 1280 px hell und dunkel „rollt nicht …“, „Freitag zu sehen“ |
| Nr. 3 – unter 1400 px Namensspalte 200 px | immer 230 px (`283_3b`, `283_3d`) | 1 rot: v683::test_spalten_und_chips; Klicktest auftraege: bei 1280 px „kein Chip gekürzt“ (die Tage nur 88 px, „HS-DK 202“ gekürzt) |
| Nr. 4 – zu schmal: das Gerätezeichen fällt weg | ohne Container-Query (`283_4a`, `283_4b`) | 1 rot: v683::test_spalten_und_chips; Klicktest auftraege: 1280 px „kein Chip gekürzt“, „Gerätezeichen weg“ |
| Nr. 4 – das Kranzeichen bleibt | jedes Zeichen fällt weg (`283_4c`) | Klicktest auftraege: „1280 …: Kran behält sein Zeichen“ |
| Nr. 4 – Innenabstand des Chips 6 px | wieder 7 px (`283_4d`) | Klicktest auftraege: 1280 px „kein Chip gekürzt“ („HS-DK 202“ 1 px zu breit) |

15 Gegenproben (7 gegen Tests, 8 gegen den Klicktest), alle im ersten Lauf rot, jede Datei byte-genau zurück, kein Marker geblieben. Ohne eigene Gegenprobe:
Nr. 2 zweiter Satz (zugeklappt bleibt sie bis zum nächsten Wechsel -- belegt durch v683::test_in_auftraege_zugeklappt_bleibt_zu_bis_zum_naechsten_wechsel und den
Klicktest „beim nächsten Wechsel wieder offen“), Nr. 4 Innenabstände von Zelle und Karte (zusammen mit dem Chip gemessen, kein gekürzter Chip), Nr. 5 (2–4 Wochen
unverändert).

## 1.9.284 (Punkt 2): Chips mit dem Finger 32 px, der Treffbereich größer

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – mit dem Finger 32 px hoch | wieder 40 px (`284_1a`, `284_1c`) | 1 rot: v684::test_finger_32_px_mit_groesserem_treffbereich; Klicktest auftraege_ziehen: „Finger: Chip 32 px hoch, 3 px darüber und darunter …“ |
| Nr. 1 – der Treffbereich reicht darüber hinaus | ohne `::before` (`284_1b`, `284_1d`) | 1 rot: v684::test_finger_32_px_mit_groesserem_treffbereich; Klicktest: „Finger: Chip 32 px hoch, 3 px darüber und darunter …“ |
| Nr. 1 – 4 px ab der Außenkante | `inset:-4px -2px` (vom Innenrand: nur 3 px, `284_1e`) | Klicktest: „Finger: Chip 32 px hoch, 3 px darüber und darunter …“ (3 px darunter nicht mehr) |
| Nr. 2 – 8 px zwischen den Zeilen | wieder 4 px (`284_2a`, `284_2b`) | 1 rot: v684::test_finger_32_px_mit_groesserem_treffbereich; Klicktest: „Finger: …“ (3 px darunter trifft den Chip der nächsten Zeile) |
| Nr. 3 – der Chip schneidet nicht ab | `overflow:hidden` am Chip (`284_3a`, `284_3c`) | 1 rot: v684::test_der_text_kuerzt_nicht_der_chip; Klicktest: „Finger: …“ (der Treffbereich abgeschnitten) |
| Nr. 3 – der Name kürzt in seinem eigenen Teil | ohne `span.chip-text` (`284_3b`) | 1 rot: v684::test_chip_mit_eigenem_textteil |

10 Gegenproben (5 gegen Tests, 5 gegen den Klicktest), alle im ersten Lauf rot, jede Datei byte-genau zurück, kein Marker geblieben. Beim Bauen gemessen: mit
`inset:-4px -2px` reichte der Treffbereich nur 3 px über und 2 px unter den Chip -- `inset` zählt vom Innenrand, der Rand ist 1 px; deshalb `-5px -3px`.

## 1.9.285 (Punkt 3): Klick in einen freien Tag schlägt die Kolonne vor

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – genau eine Kolonne wird vorgeschlagen | `kolonneDesAuftrags()` gibt immer `null` (`285_1a`, `285_1c`) | 3 rot: v685::test_genau_eine_kolonne[10-5], [13-6], test_klick_oeffnet_den_dialog_mit_der_kolonne; Klicktest rueckgaengig: „Aufträge: Wasserturm Sa -- Kolonne Nord vorgeschlagen, nur Sa“ |
| Nr. 1 – mehrere Kolonnen: ohne | `k.length>=1` statt `===1` (`285_1b`) | 1 rot: v685::test_genau_eine_kolonne[11-None] |
| Nr. 1 – der Klick nutzt den Vorschlag | `openCreate(…, null, …)` wie bis 1.9.284 (`285_3a`, `285_3b`) | 2 rot: v682::test_klick_in_einen_freien_tag_in_auftraege, v685::test_klick_oeffnet_den_dialog_mit_der_kolonne; Klicktest: „Aufträge: Wasserturm Sa -- Kolonne Nord vorgeschlagen, nur Sa“ |
| Nr. 2 – Einsätze ohne Kolonne zählen nicht | ohne `s.team_id!=null` (`285_2a`) | 1 rot: v685::test_genau_eine_kolonne[13-6] |
| Nr. 3 – weiter nur dieser Tag, eine Karte öffnet ihren Einsatz | keine eigene Gegenprobe: unverändert seit 1.9.282 (Gegenproben dort); der Klicktest prüft „nur Sa“ in derselben Zeile wie Nr. 1 | -- |

6 Gegenproben (4 gegen Tests, 2 gegen den Klicktest), alle im ersten Lauf rot, jede Datei byte-genau zurück, kein Marker geblieben.

## 1.9.286 (Punkt 4): „Ganze Kolonne“ nennt auch Geräte

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Geräte, die schon woanders sind, stehen in der Anzeige | ohne die Geräte (`286_1a`, `286_1b`) | 3 rot: v686::test_personen_und_geraete, test_nur_ein_geraet, test_frei (nur ein Gerät woanders: dann „frei“); Klicktest auftraege_ziehen: „Kolonne: Anzeige …“ |
| Nr. 2 – erst die Personen, dann die Geräte | Geräte vor den Personen (`286_2a`) | 1 rot: v686::test_personen_und_geraete |
| Nr. 2 – das Gerät mit dem Kurznamen wie am Chip | der volle Name statt `geraetName()` (`286_2b`, `286_2c`) | 2 rot: v686::test_personen_und_geraete, test_frei; Klicktest: „Kolonne: Anzeige …“ |

5 Gegenproben (3 gegen Tests, 2 gegen den Klicktest), alle im ersten Lauf rot, jede Datei byte-genau zurück, kein Marker geblieben.

## 1.9.287 (Punkt 5): die Anzeige schwebt über der Zelle

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Anzeige schwebt, die Zeile wird nicht höher | im Fluss der Zelle (`margin-top:4px` statt `position:absolute`, `287_1a`, `287_1c`) | 1 rot: v687::test_anzeige_schwebt_ueber_der_zelle; Klicktest auftraege_ziehen: 15 rote Prüfungen, u. a. „Woanders: die Zeile wird nicht höher“, „Kolonne: …“, „Finger hell: Anzeige schwebt, die Zeile wird nicht höher“, „Maus dunkel: …“ |
| Nr. 1 – oberhalb der Zelle, Chips des Ziels zu sehen | `bottom:2px` (über den Chips in der Zelle, `287_1b`, `287_1d`) | 1 rot: v687::test_anzeige_schwebt_ueber_der_zelle; Klicktest: „Woanders: die Anzeige schwebt über der Zelle“, „Finger hell: …“ |
| Nr. 2 – vorn in der Zelle | `appendChild` statt `prepend` (`287_2a`, `287_2b`) | 1 rot: v687::test_anzeige_vorn_in_der_zelle; Klicktest: „Woanders: die Zeile wird nicht höher“ (die letzte Karte verliert ihren Abstand, +4 px) |
| Nr. 2 – fängt keine Zeigerereignisse ab | ohne `pointer-events:none` (`287_2c`, `287_2d`) | 1 rot: v687::test_anzeige_schwebt_ueber_der_zelle; Klicktest: zuerst **grün** (88 von 88), nachgezogen „Woanders: die Anzeige fängt keinen Zeiger ab“ (an der Mitte der Anzeige findet `zielAnPunkt()` nie das Ziel), danach rot |
| Nr. 3 – die Kopie rechts neben dem Zeiger | wieder darüber (`287_3a`, `287_3b`) | 1 rot: v687::test_kopie_neben_dem_zeiger; Klicktest: „Frei: nichts markiert, der Chip neben dem Zeiger“ |
| Nr. 4 – mit dem Finger seitlich 6 px | wieder 7 px (`287_4a`, `287_4b`) | 1 rot: v687::test_finger_seitlich_wie_die_maus; Klicktest: „Finger hell: kein Name ohne Warnung gekürzt (seitlich 6 px wie mit der Maus)“ |
| Nr. 4 – ein Chip mit ⚠ darf kürzen | keine eigene Gegenprobe: eine Erlaubnis, keine Prüfung -- der Klicktest nimmt Chips mit Warnung aus der Prüfung „kein Name gekürzt“ aus | -- |

12 Gegenproben (6 gegen Tests, 6 gegen den Klicktest); `287_2d` blieb zuerst grün, nach dem Nachziehen des Klicktests dieselbe Gegenprobe noch einmal: rot. Jede Datei
byte-genau zurück, kein Marker geblieben.

## 1.9.288 (Punkt 6): „Nicht eingeplant“ zeigt die Stunden wie die Akte

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „Nicht eingeplant“ rechnet die Zeile wie „Aufträge“ | `stunden` wieder „Soll <Planstunden> h“ (`288_1a`) | 1 rot: v688::test_rueckstand_wie_die_auftragsliste |
| Nr. 1 – „Rest …“, sobald gebucht ist | gebucht immer 0 (`288_1b`) | 1 rot: v688::test_rueckstand_wie_die_auftragsliste |
| Nr. 1 – „Wartungsvertrag“ | Herkunft nie Wartungsvertrag (`288_1c`) | 1 rot: v688::test_rueckstand_wie_die_auftragsliste |
| Nr. 1 – die Liste zeigt die Zeile | die Seite zeigt wieder „Soll <planned_hours> h“ (`288_2a`, `288_2b`) | 1 rot: v688::test_die_liste_zeigt_die_zeile; Klicktest rueckgaengig: „Nicht eingeplant: Kaminverwahrung wie die Akte“ |
| Nr. 1 – dieselbe Zeile wie in „Aufträge“ (Klicktest) | `stunden` immer „nach Aufwand“ (`288_1d`) | Klicktest: „Nicht eingeplant: Kaminverwahrung wie die Akte“ |
| Nr. 2 – nur Baustelle & Werkstatt | jede Zeitart zählt (`288_4a`) | 1 rot: v688::test_rueckstand_wie_die_auftragsliste (Fahrzeit 3 h: „Rest 1,50 h“) |
| Nr. 2 – keine laufende Zeit | auch laufende zählen (`288_4b`; der Test bekam dafür eine laufende Zeit mit 2 h -- vorher hätte die Gegenprobe nichts gefunden) | 1 rot: v688::test_rueckstand_wie_die_auftragsliste |
| Nr. 3 – feste Zahl Abfragen | je Auftrag eine Abfrage für gebucht (`288_3a`) | 1 rot: v564::test_abfragen_haengen_nicht_am_rueckstand |

10 Gegenproben (8 gegen Tests, 2 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Nr. 2 hatte beim Bauen noch keine eigene
Gegenprobe; `288_4a` und `288_4b` sind nachgezogen, für `288_4b` zuerst der Test um eine laufende Zeit mit Stunden ergänzt.

## 1.9.289 (Punkt 7): Leiste mit dem neuen Zeitraum, „40 h/Woche“ ohne Umbruch, Untermenü in Zeilen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – alter und neuer Zeitraum statt „→ ab <Tag>“ | wieder „→ ab <Tag>“ in der eigenen Zeile (`289_1a`, `289_1b`) | 2 rot: v689::test_kein_ab_mehr_in_der_leiste, test_leiste_mit_dem_neuen_zeitraum_vom_server; Klicktest rueckgaengig: „Personen 1440 hell: Leiste“, „Geräte: Leiste“, „Personen 1280 dunkel: Leiste“ |
| Nr. 2 – der Server liefert `ziel_tage` | `ziel_tage` leer (`289_2a`, `289_2d`) | 1 rot: v689::test_umsetzen_nennt_die_zieltage_in_arbeitstagen; Klicktest: dieselben drei Prüfungen der Leiste |
| Nr. 2 – der Zeitraum geht bis zum letzten Zieltag | nur der erste Zieltag (`289_2b`) | 2 rot: v689::test_kein_ab_mehr_in_der_leiste, test_leiste_mit_dem_neuen_zeitraum_vom_server |
| Nr. 2 – die Seite rechnet nicht nach | die Seite rechnet in Kalendertagen ab dem Zieltag (`289_2c`) | 2 rot: v689::test_kein_ab_mehr_in_der_leiste, test_leiste_mit_dem_neuen_zeitraum_vom_server (Do–Fr +1: „13.–14.11.“ statt „13.–16.11.“) |
| Nr. 3 – andere Zeile: „→ <neu>“ nur, wenn er sich ändert | immer „→ <neu>“ (`289_3a`, `289_3c`) | 1 rot: v689::test_leiste_mit_dem_neuen_zeitraum_vom_server; Klicktest: „Personen …“ („Sturmschaden … 11.11. → 11.11.: Ole Offen → Tom Monteur“) |
| Nr. 3 – andere Zeile, anderer Tag: der neue Zeitraum steht da | nie „→ <neu>“ (`289_3b`) | 1 rot: v689::test_leiste_mit_dem_neuen_zeitraum_vom_server |
| Nr. 4 – „40 h/Woche“ bricht nicht um | `.nw{}` ohne `nowrap` (`289_4a`, `289_4c`) | 1 rot: v689::test_stunden_je_woche_ohne_umbruch; Klicktest stammdaten_breite: „1280 hell/dunkel: „h/Woche“ einzeilig“, „eng (Funktion 40 px): „h/Woche“ einzeilig“ |
| Nr. 4 – in einer eigenen Hülle | ohne `<span class="nw">` (`289_4b`, `289_4d`) | 1 rot: v689::test_stunden_je_woche_ohne_umbruch; Klicktest: dieselben drei Prüfungen |
| Nr. 5 – unter 1400 px in Zeilen, ohne seitliches Rollen | wieder `overflow:auto` ohne Umbruch (`289_5a`, `289_5b`) | 2 rot: v678::test_untermenue_unter_1400_px_oben, v689::test_untermenue_in_zeilen_unter_1400_und_rollend_unter_850; Klicktest: „1280 hell/dunkel: Untermenü rollt nicht seitlich“, „… in zwei Zeilen“ |
| Nr. 5 – jeder Knopf so breit wie sein Text | ohne `width:auto` (volle Breite, `289_5c`, `289_5d`) | 2 rot: v678::test_untermenue_unter_1400_px_oben, v689::test_untermenue_in_zeilen_unter_1400_und_rollend_unter_850; Klicktest: „1280 hell/dunkel: Untermenü in zwei Zeilen“ (neun) |
| Nr. 6 – unter 850 px eine Zeile, die rollt | ohne die Regel unter 850 px (`289_6a`, `289_6b`) | 1 rot: v689::test_untermenue_in_zeilen_unter_1400_und_rollend_unter_850; Klicktest: „412 hell/dunkel: Untermenü eine Zeile, rollt im Rahmen“ |

19 Gegenproben (11 gegen Tests, 8 gegen die Klicktests), alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Beim Bauen: der erste Versuch ohne
`width:auto` ergab neun Zeilen Untermenü -- der neue Klicktest fand es; daraus Nr. 5 „jeder Knopf so breit wie sein Text“ mit eigener Gegenprobe.
