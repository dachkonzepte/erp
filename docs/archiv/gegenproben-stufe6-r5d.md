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
