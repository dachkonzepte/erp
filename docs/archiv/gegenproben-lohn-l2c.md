# Gegenproben Lohn L2c (ab 1.9.320)

Je neue Festlegung eine Gegenprobe (Regel 24): der Schutz wird mit dem Marker `GEGENPROBE` ausgehebelt, die genannten Tests müssen rot werden (nur FAILED
zählt, ein Sammel- oder Aufbaufehler nicht), danach die Datei byte-genau zurück (Prüfsumme). Wo keine möglich ist, steht der Grund in der Tabelle.

## 1.9.320 (L2c-1, Punkt 0): „ohne Startwert“ nur, wer am Stichtag beschäftigt war

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur, wer am 31.12.2026 beschäftigt war | der Hinweis für jeden ohne Startwert, wie bis 1.9.319 (`320_1a`) | 4 rot: v715::test_hinweise, v720::test_hinweis_nur_wer_am_stichtag_beschaeftigt_war, test_austritt_vor_und_am_stichtag, test_danach_rest_und_meine_zeiten |
| Nr. 1 – beide Tage eingeschlossen | Stichtag einen Tag später (`320_1b`) | 4 rot: v720::test_regel_am_stichtag, test_hinweis_nur_wer_am_stichtag_beschaeftigt_war, test_austritt_vor_und_am_stichtag, test_danach_rest_und_meine_zeiten |
| Nr. 1 – beide Tage eingeschlossen | Stichtag einen Tag früher (`320_1c`) | 4 rot: dieselben vier aus v720 |
| Nr. 2 – wer danach eintritt: 0 ohne Hinweis | wie `320_1a` (der Hinweis für jeden) | rot (siehe `320_1a`); „Anspruch prüfen“ ist unverändert seit 1.9.315, v720 prüft es mit |
| Nr. 3 – ohne Lohnstammdaten beschäftigt | ohne Lohnstammdaten nicht beschäftigt (`320_3a`) | 2 rot: v720::test_regel_am_stichtag, test_hinweis_nur_wer_am_stichtag_beschaeftigt_war |
| Nr. 3 – ohne Eintritt beschäftigt | ohne Eintritt nicht beschäftigt (`320_3b`) | 3 rot: v720::test_regel_am_stichtag, test_hinweis_nur_wer_am_stichtag_beschaeftigt_war, test_danach_rest_und_meine_zeiten |
| Nr. 4 – eine Stelle, „danach Rest“ und „Meine Zeiten“ folgen | keine eigene: dieselbe Regel ausgehebelt (`320_1a`) macht v720::test_danach_rest_und_meine_zeiten rot -- beide lesen den Hinweis aus dem Konto | rot (siehe `320_1a`) |

5 Gegenproben, alle rot (alle über Tests; kein Klicktest berührt eine Person mit Eintritt 2027).
