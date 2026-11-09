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
