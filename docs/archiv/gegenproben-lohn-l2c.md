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

## 1.9.321 (L2c-1, Punkt 1): die Rechnung des Arbeitszeitkontos

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – eine Zeile je Kategorie und Quelle | die Zeile Sonderurlaub entfernt (`321_1f`) | 2 rot: v721::test_regel_ist_eine_tabelle_fuer_jede_kategorie_und_quelle, test_neutral_und_plus |
| Nr. 2 – Freizeitausgleich nicht gutgeschrieben | Freizeitausgleich gutgeschrieben (`321_1a`) | 2 rot: v721::test_regel_…, test_beispielwoche |
| Nr. 2 – Unbezahlt gutgeschrieben | Unbezahlt als Minus (`321_1b`) | 2 rot: v721::test_regel_…, test_neutral_und_plus |
| Nr. 2 – Schlechtwetter gutgeschrieben | Schlechtwetter als Minus (`321_1c`) | 2 rot: v721::test_regel_…, test_beispielwoche |
| Nr. 2 – Heiligabend und Silvester gutgeschrieben | Kalendertag als Minus (`321_1d`) | 2 rot: v721::test_regel_…, test_heiligabend_und_silvester |
| Nr. 2 – Feiertag gutgeschrieben | Feiertag als Minus (`321_1e`) | 3 rot: v721::test_regel_…, test_neutral_und_plus, test_stand_ab_dem_startwert_und_nur_bis_gestern |
| Nr. 2 – Krankheit gutgeschrieben | Krankheit als Minus (`321_1h`) | 2 rot: v721::test_regel_…, test_neutral_und_plus |
| Nr. 2 – Fortbildung gutgeschrieben | Fortbildung als Minus (`321_1i`) | 2 rot: v721::test_regel_…, test_neutral_und_plus |
| Nr. 2 – Altbestand ohne Kategorie gutgeschrieben | als Minus (`321_1g`) | 1 rot: v721::test_regel_… |
| Nr. 2 – Urlaub und Sonderurlaub gutgeschrieben | keine eigene: Urlaub trägt die Beispielwoche (Di, halber Fr), Sonderurlaub `321_1f` | rot (siehe `321_1f`, `321_1a`) |
| Nr. 3 – Arbeit mit Fahrzeit | Fahrzeit zählt nicht (`321_2a`) | 1 rot: v721::test_beispielwoche |
| Nr. 3 – Arbeit neben einem gutgeschriebenen Tag ein Plus | Arbeit an einem Tag mit Posten zählt nicht (`321_2b`) | 3 rot: v721::test_beispielwoche, test_heiligabend_und_silvester, test_neutral_und_plus |
| Nr. 3 – ein Tag ohne Eintrag ein Minus | keine eigene: die Rechnung Ist − Soll selbst; jede Gegenprobe der Regel ändert sie | v721::test_neutral_und_plus (betriebsfreier Tag −8,00), test_stand_… (−150,00) |
| Nr. 4 – nur gewerbliche | auch kaufmännische (`321_3a`) | 1 rot: v721::test_nur_gewerbliche_und_zwischen_eintritt_und_austritt |
| Nr. 4 – nur zwischen Eintritt und Austritt | Arbeit auch außerhalb (`321_4a`) | 1 rot: v721::test_nur_gewerbliche_und_zwischen_eintritt_und_austritt |
| Nr. 5 – bis gestern | heute zählt mit (`321_5a`) | 1 rot: v721::test_stand_ab_dem_startwert_und_nur_bis_gestern |
| Nr. 5 – ab 01.01.2027 | der Dezember 2026 zählt mit (`321_5b`) | 1 rot: v721::test_stand_… |
| Nr. 6 – Stand ab dem Startwert | ohne Startwert (`321_6a`) | 1 rot: v721::test_stand_… |
| Nr. 7 – nur am Stichtag beschäftigt | der Hinweis auch nach dem Stichtag (`321_7a`) | 2 rot: v721::test_beispielwoche, test_stand_… |
| Nr. 7 – wenn der Saldo fehlt | ein Startwert ohne Saldo zählt als da (`321_7b`) | 1 rot: v721::test_stand_… |
| Nr. 8 – eine feste Zahl Abfragen | eine Abfrage je Person für den Startwert (`321_8a`) | 1 rot: v721::test_eine_feste_zahl_abfragen |
| Nr. 9 – nur Admin und Büro – Finanzen | auch Büro – Auftrag (`321_9a`) | 1 rot: v721::test_schnittstelle |
| Nr. 9 – vor Januar 2027 422 | auch vor 2027 (`321_9b`) | 1 rot: v721::test_schnittstelle |
| Nr. 9 – „maßgeblich ist DATEV“ in der Antwort | ohne Hinweis (`321_9c`) | 1 rot: v721::test_schnittstelle |
| Nr. 10 – ohne Monat der laufende, frühestens Januar 2027 | ohne Monat der laufende, auch vor 2027 (`321_10a`) | 1 rot: v721::test_schnittstelle |
| Nr. 11 – die Lohndatei bleibt unverändert | keine möglich: die Runde ändert die Lohndatei nicht; Nachweis über die Vorprobe | September, Oktober und echt Oktober Byte für Byte gleich wie auf 1.9.316 |

23 Gegenproben, alle rot (alle über Tests; keine Oberfläche, kein Klicktest).

## 1.9.322 (L2c-1, Punkt 2): Hinweise zum Arbeitszeitkonto in „Zeiten → Prüfen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ohne Abwesenheit, Feiertag, Kalendertag, Ausfalltag | auch Tage mit Posten (`322_1a`) | 4 rot: v722::test_tag_ohne_eintrag, test_arbeit_an_urlaubs_oder_kranktag, test_ab_dem_kontobeginn_und_bis_gestern, test_schnittstelle_rechte_ohne_zahl_und_ohne_sperre |
| Nr. 1 – ohne laufende Zeit | auch mit laufender Zeit (`322_1b`) | 1 rot: v722::test_tag_ohne_eintrag |
| Nr. 1 – je Person die Sollzeit zusammen | nur die Sollzeit des ersten Tags (`322_1c`) | 1 rot: v722::test_tag_ohne_eintrag |
| Nr. 1 – auch ein betriebsfreier Tag | keine eigene: ein betriebsfreier Tag ist kein Posten -- es gibt keinen Code, der ihn ausnimmt; v722 prüft ihn mit (Mi 06.01.) | rot unter `322_1a` (dann zählten auch Tage mit Posten) |
| Nr. 2 – nur ganze Tage | auch der halbe Urlaubstag (`322_2a`) | 1 rot: v722::test_arbeit_an_urlaubs_oder_kranktag |
| Nr. 2 – nur Urlaub und Krankheit | auch Sonderurlaub (`322_2b`) | 1 rot: v722::test_arbeit_an_urlaubs_oder_kranktag |
| Nr. 2 – nicht am Feiertag | auch am Feiertag (`322_2c`) | 1 rot: v722::test_arbeit_an_urlaubs_oder_kranktag |
| Nr. 3 – nur gewerbliche | auch kaufmännische (`322_3a`) | 1 rot: v722::test_tag_ohne_eintrag |
| Nr. 3 – ab 01.01.2027 | auch vor dem Kontobeginn (`322_3b`) | 1 rot: v722::test_ab_dem_kontobeginn_und_bis_gestern |
| Nr. 3 – bis gestern | heute zählt mit (`322_3c`) | 4 rot: alle vier aus v722 |
| Nr. 3 – ab dem Beginn von „Prüfen“ | keine eigene: der Beginn kommt aus `pruef_beginn()` (unverändert seit 1.9.95); v722 prüft ihn mit (ab 05.01.) | rot unter `322_3b` (dann zählte der Dezember) |
| Nr. 4 – nur Admin und Büro – Finanzen | auch Büro – Auftrag (`322_4a`; Klicktest `322_K2`) | 1 rot: v722::test_schnittstelle_rechte_ohne_zahl_und_ohne_sperre; Klicktest: „Bea: beide Karten verborgen“ |
| Nr. 5 – keine Zahl am Reiter | die Tage ohne Eintrag am Reiter (`322_5a`) | 1 rot: v722::test_schnittstelle_rechte_ohne_zahl_und_ohne_sperre |
| Nr. 5 – keine Sperre | die Hinweise in „Vor dem Abschluss“ als Hindernis (`322_5b`) | 1 rot: v722::test_schnittstelle_rechte_ohne_zahl_und_ohne_sperre |
| Nr. 6 – Karte „Tage ohne Eintrag“ | die Karte nie (`322_K1`) | Klicktest: „Anna: beide Karten zur Info, keine Zahl am Reiter“ |
| Nr. 6 – Karte „Arbeit an Urlaubs- oder Kranktagen“ | die Karte nie (`322_K4`) | Klicktest: „Anna: beide Karten zur Info, keine Zahl am Reiter“ |
| Nr. 6 – „Nichts zu prüfen“ nur ohne sie | die Bedingung wie bis 1.9.321 (`322_K3`) | Klicktest: „Anna: beide Karten zur Info, keine Zahl am Reiter“ |

16 Gegenproben, alle rot (12 über Tests, 4 über `klicktest_konto_hinweise`).
