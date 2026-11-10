# Gegenproben der Runde Stufe 6, R5e (ab 1.9.290)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R5d (`docs/archiv/gegenproben-stufe6-r5d.md`): in einer eigenen
Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript) mit dem Marker `GEGENPROBE` ändern, die genannten Tests bzw. den Klicktest laufen
lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler) bzw. der Klicktest endet nicht wie erwartet.

## 1.9.290 (Punkt 1): „Zum Einplanen“ startet nach dem Zeitraum

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – mit 2–4 Wochen wie die übrigen Ansichten (unter 1440 px zu) | die Liste immer offen wie bis 1.9.289 (`290_1a`, `290_1d`) | 7 rot: v690::test_wechsel_nach_auftraege_mit_dem_gemerkten_zeitraum (4 Fälle), test_anderer_zeitraum_in_auftraege_startet_die_liste_neu, test_von_hand_auf_oder_zugeklappt_gilt_bis_zum_naechsten_zeitraum, test_aufbau; Klicktest auftraege: „1280 dunkel, 2 Wochen“, „1280, 2 Wochen“, „1280, 3 Wochen“, „1280 hell, 2 Wochen“ |
| Nr. 1 – mit 1 Woche immer offen | 1 Woche nach derselben Regel wie 2–4 Wochen (`290_1b`, `290_1e`) | 4 rot: v690::test_wechsel_… (Fälle 1280/1 Woche ohne und mit „zu“), test_anderer_zeitraum_…, test_aufbau; Klicktest: „1280 hell/dunkel: Liste offen …“, „1280 Aufträge: Liste offen“ u. a. (9 Prüfungen) |
| Nr. 1 – das Gemerkte gilt bei jeder Breite | nur die Breite, ohne Gemerktes (`290_1c`) | 3 rot: v690::test_wechsel_… (Fälle „zu“ bei 1440 px, „offen“ bei 1280 px), test_aufbau. Klicktest: keine Gegenprobe -- er merkt nichts im Browser (nur node) |
| Nr. 2 – Start beim Wechsel in die Ansicht | `setView()` öffnet wie bis 1.9.289 (`290_2a`, `290_2c`) | 5 rot: v690::test_wechsel_… (4 Fälle), test_aufbau; Klicktest: „1280, 2 Wochen: beim Wechsel in die Ansicht zu“, „1280 hell, 2 Wochen“ |
| Nr. 2 – Start bei jedem anderen Zeitraum, auch nach Hand | `zeitraumGewechselt()` ohne Neustart der Liste (`290_2b`, `290_2d`) | 3 rot: v690::test_anderer_zeitraum_…, test_von_hand_…, test_aufbau; Klicktest: „1280 dunkel, 2 Wochen“, „1280, zurück auf 1 Woche“, „1280, 1 Woche von Hand zu“, „1280, 3 Wochen“ |
| Nr. 3 – ein anderer Zeitraum merkt nichts | `zeitraumGewechselt()` merkt den Zustand (`290_3a`, `290_3d`) | 3 rot: v690::test_anderer_zeitraum_…, test_von_hand_…, test_aufbau; Klicktest: „1280, 2 Wochen: nichts gemerkt“, „1280, 3 Wochen“ u. a. (7 Prüfungen) |
| Nr. 3 – der Wechsel in die Ansicht merkt nichts | `setView()` merkt den Start (`290_3b`) | 10 rot: v690::test_wechsel_… (alle 9 Fälle), test_aufbau u. a. |
| Nr. 3 – in den übrigen Ansichten ändert ein anderer Zeitraum die Liste nicht | der Neustart in jeder Ansicht (`290_3c`) | zuerst nur test_aufbau rot (der Fall „gemerkt offen“ ergab mit beiden Regeln „offen“) -- Test nachgezogen (gemerkt „zu“, dann 1 Woche in „Kolonnen“ und „Personen“), dieselbe Gegenprobe: 2 rot: v690::test_in_den_uebrigen_ansichten_aendert_ein_anderer_zeitraum_die_liste_nicht, test_aufbau. Klicktest: keine Gegenprobe -- er wechselt den Zeitraum in „Kolonnen“ nicht mit Gemerktem |

13 Gegenproben (8 gegen Tests, 5 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Eine blieb zuerst grün (`290_3c`, bis auf den
Aufbau-Test) -- Test nachgezogen, dieselbe Gegenprobe rot.
