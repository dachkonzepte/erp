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

## 1.9.291 (Punkt 2): Warnung und Hinweis als Abzeichen an der Ecke

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – das Abzeichen sitzt außerhalb des Flusses, nimmt dem Namen keinen Platz | das Abzeichen im Fluss des Chips (`position:static`; `291_1a`, `291_2a`, `291_2b`) | 1 rot: v691::test_lage_an_der_ecke; Klicktest auftraege: „1440 hell“, „1280 hell/dunkel“, „1280 dunkel/hell, 2 Wochen“ (Abzeichen nicht an der Ecke, 2 Wochen gekürzt); Klicktest ziehen: alle sechs Kombinationen („Maus 1440 hell“ … „Finger 1440 dunkel“: gekürzt, nicht an der Ecke) |
| Nr. 1 – an der oberen rechten Ecke | an der oberen linken Ecke (`291_1b`, `291_2c`) | 1 rot: v691::test_lage_an_der_ecke; Klicktest auftraege: „1440 hell“, „1280 hell/dunkel“, „1280 dunkel, 2 Wochen“ |
| Nr. 1 – über die Ecke hinaus, außerhalb des Namens | innen in der Ecke (`top:2px; right:2px`; `291_1c`, `291_2d`) | 1 rot: v691::test_lage_an_der_ecke; Klicktest ziehen: alle sechs Kombinationen |
| Nr. 1 – an der Ecke des eigenen Chips | der Chip ohne `position:relative` (`291_1d`, `291_2e`) | 1 rot: v691::test_lage_an_der_ecke. Klicktest auftraege zuerst GRÜN: die Karte ist ein Container und fing das Abzeichen auf, alle landeten an ihrer Ecke -- die Prüfung verlangte nur „über und rechts vom Chip“. Nachgezogen (5 px ±1 über die Ecke des eigenen Chips), dieselbe Gegenprobe: rot („1440 hell“, „1280 hell/dunkel“, „1280 dunkel, 2 Wochen“); `291_2a` mit der neuen Prüfung noch einmal: rot |
| Nr. 1 – Warnung vor Hinweis (mit beidem nur ⚠, wie bisher) | der Hinweis vor der Warnung (`291_1e`) | 1 rot: v691::test_warnung_vor_hinweis_und_ohne_beides_kein_abzeichen. Klicktest: keine Gegenprobe -- in den Testdaten hat kein Chip beides |
| Nr. 2 – kein Chip gekürzt (1440/1280 px, Maus/Finger, 1 Woche; 2 Wochen eingeklappt) | das Abzeichen im Fluss (`291_2a`, `291_2b`, siehe oben) | Klicktest auftraege: „1280 dunkel/hell, 2 Wochen: … kein Chip gekürzt“; Klicktest ziehen: „… kein Chip gekürzt …“ in allen sechs Kombinationen (HS-DK 204 mit ⚠ gekürzt) |

11 Gegenproben (5 gegen Tests, 6 gegen die Klicktests), alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Eine blieb zuerst grün (`291_2e`) --
Klicktest nachgezogen, dieselbe Gegenprobe rot.
