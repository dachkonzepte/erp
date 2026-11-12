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

## 1.9.323 (Nachtrag zu Punkt 1): die Regel wie DATEV

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „vorläufig – maßgeblich ist die Lohnabrechnung“ | der Text bis 1.9.322 (`323_4a`) | 1 rot: v723::test_schnittstelle_vorlaeufig |
| Nr. 1 – `vorlaeufig: true` | ohne das Feld (`323_4b`) | 1 rot: v723::test_schnittstelle_vorlaeufig |
| Nr. 2 – Unbezahlt ein Minus | wie bis 1.9.322 neutral (`323_1a`) | 4 rot: v721::test_regel_…, test_neutral_und_plus; v723::test_gutgeschrieben_genau_mit_einer_zeile_in_der_lohndatei, test_minus_ohne_zeile_und_winter_mit_vermerk |
| Nr. 2 – Schlechtwetter Sommer ein Minus | wie bis 1.9.322 neutral (`323_1b`) | 4 rot: v721::test_regel_…, test_beispielwoche; v723::test_gutgeschrieben_…, test_minus_ohne_zeile_… |
| Nr. 2 – Altbestand ohne Kategorie ein Minus | gutgeschrieben (`323_1c`) | 1 rot: v721::test_regel_… |
| Nr. 2 – Freizeitausgleich ein Minus; eine Zeile ohne Lohnart zählt | keine eigene: unverändert seit 1.9.321 (Gegenprobe `321_1a`); FE und UU prüft der Wächter v723 (Berufsschule, Silvester) | grün ohne Gegenprobe; rot würde v723::test_gutgeschrieben_… |
| Nr. 3 – Schlechtwetter je Jahreszeit wie die Lohndatei | immer Winter (`323_1d`) | 3 rot: v721::test_beispielwoche; v723::test_gutgeschrieben_…, test_minus_ohne_zeile_… |
| Nr. 3 – Winter neutral | Winter als Minus (`323_2a`) | 3 rot: v721::test_regel_…; v723::test_gutgeschrieben_…, test_minus_ohne_zeile_… |
| Nr. 3 – Vermerk am Tag | ohne Vermerk (`323_2b`) | 1 rot: v723::test_minus_ohne_zeile_und_winter_mit_vermerk |
| Nr. 3 – Hinweis am Konto | ohne Hinweis (`323_2c`) | 1 rot: v723::test_minus_ohne_zeile_und_winter_mit_vermerk |
| Nr. 4 – Mehrarbeit der Azubis aufs Konto | Arbeit nur bis zur Sollzeit (`323_3a`) | 3 rot: v721::test_beispielwoche, test_neutral_und_plus; v723::test_azubi_mehrarbeit_geht_aufs_konto |
| Nr. 5 – Sollzeit aus der Tagesbilanz | eine feste Sollzeit 8,00 h (`323_5a`) | 3 rot: v723::test_sollzeit_nach_kalenderwoche, test_azubi_mehrarbeit_geht_aufs_konto, test_minus_ohne_zeile_und_winter_mit_vermerk |

11 Gegenproben, alle rot (alle über Tests; keine Oberfläche).

## 1.9.324 (Nachrunde, Punkt A): erzeugte Testnummern aus dem erfundenen Kreis

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – erzeugte Personalnummern nur aus 0009x, 0019x, 0029x (test_v708) | test_v708 erzeugt wieder f"00{100 + i}" (`324_1a`) | 1 rot: v724::test_erzeugte_personalnummern_nur_aus_erfundenen_kreisen |
| Nr. 2 – der Wächter prüft den Testhelfer person() | person() nicht geprüft (`324_2a`) | 1 rot: v724::test_der_waechter_findet |
| Nr. 2 – der Wächter prüft datev_personnel_number, personalnummer, pnr | die Schlüsselwörter nicht geprüft (`324_2b`) | 1 rot: v724::test_der_waechter_findet |
| Nr. 2 – ohne Ziffern am Anfang frei | auch ohne Ziffern am Anfang (`324_2d`) | 2 rot: v724::test_der_waechter_findet, test_erzeugte_… (D-{nr} in test_v326) |

4 Gegenproben, alle rot (alle über Tests; keine Oberfläche).

## 1.9.325 (Nachrunde, Punkt B): Hinweis beim Deaktivieren ohne Austritt

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur beim Wechsel von aktiv auf inaktiv | auch wer schon inaktiv war (`325_1a`) | 1 rot: v725::test_hinweis_nur_beim_deaktivieren_ohne_austritt |
| Nr. 1 – nur ohne Austritt | auch mit Austritt (`325_1b`) | 1 rot: v725::test_hinweis_nur_… |
| Nr. 1 – auch ohne Lohnstammdaten | ohne Lohnstammdaten kein Hinweis (`325_1c`) | 1 rot: v725::test_hinweis_nur_… |
| Nr. 2 – nur ein Hinweis, gespeichert ist trotzdem | der Hinweis sperrt mit 409 (`325_2a`) | 1 rot: v725::test_hinweis_nur_… |
| Nr. 2 – in der Antwort auf das Speichern | das Feld fehlt in der Antwort (`325_2b`) | 1 rot: v725::test_hinweis_nur_… |
| Nr. 3 – das Formular bleibt stehen | weiter zur Liste (`325_3a`; Klicktest `325_K1`) | 1 rot: v725::test_seiten; Klicktest: „Ada 1440 hell: Seite bleibt, „Gespeichert.“ und der Hinweis“ und je Bild dieselbe Prüfung |
| Nr. 3 – Weg zu den Lohnstammdaten mit der Person | Link ohne die Person (`325_K2`) | Klicktest: „Ada 1440 hell: Text, Weg und Adresse“ (je Bild), „Lohnstammdaten: geladen, Ada sichtbar trotz …“ |
| Nr. 4 – die Person sichtbar trotz „Inaktive ausblenden“ | ohne Ziel (`325_K3`) | Klicktest: „Lohnstammdaten: geladen, Ada sichtbar trotz „Inaktive ausblenden““, „Lohnstammdaten: Zeile hervorgehoben, Cursor …“ |
| Nr. 4 – hervorgehoben, Cursor im Feld „Austritt“ | ohne lohnZielZeigen() (`325_K4`) | Klicktest: „Lohnstammdaten: Zeile hervorgehoben, Cursor im Feld „Austritt“, andere Inaktive ausgeblendet“ |
| Nr. 4 – andere Inaktive bleiben ausgeblendet | keine eigene: dieselbe Prüfung wie `325_K3`/`325_K4` (Ben steht nicht in der Liste) | – |

10 Gegenproben, alle rot (6 über Tests, 4 über `klicktest_austritt_hinweis`).

## 1.9.326 (Nachrunde, Punkt C): „DATEV bekommt keine Arbeit – Umfang prüfen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur gewerbliche | auch kaufmännische (`326_1a`) | 1 rot: v726::test_wer_einen_hinweis_bekommt |
| Nr. 1 – nur Umfang nicht „alles“ | auch „alles“ (`326_1b`) | 1 rot: v726::test_wer_einen_hinweis_bekommt |
| Nr. 1 – nur wer im Monat beschäftigt ist | auch außerhalb (`326_1c`) | 1 rot: v726::test_wer_einen_hinweis_bekommt |
| Nr. 2 – in „Vor dem Abschluss“ | nicht dort (`326_2a`; Klicktest `326_K2`) | 1 rot: v726::test_in_vor_dem_abschluss_und_monat_sperrt_nichts; Klicktest: „„Vor dem Abschluss“: die zwei gewerblichen Personen, nicht Kai und Cem“ |
| Nr. 2 – in „Monat & Lohn“ | nicht in der Antwort (`326_2b`) | 1 rot: v726::test_in_vor_dem_abschluss_… |
| Nr. 2 – in „1 Prüfen“ mit Weg „Lohnstammdaten“ | die Seite zeigt ihn nicht (`326_4a`; Klicktest `326_K1`) | 1 rot: v726::test_seite; Klicktest: „„1 Prüfen“: dieselben Zeilen mit dem Weg zu den Lohnstammdaten“ |
| Nr. 3 – sperrt die Lohndatei nicht | als Eintrag in datev_fehlt() (`326_3a`) | 1 rot: v726::test_in_vor_dem_abschluss_… |
| Nr. 3 – sperrt den Abschluss nicht, zählt nicht in „Fehlt“ | keine eigene: es gibt keinen Code, der ihn dort einträgt; v726 und der Klicktest prüfen beides | – |

9 Gegenproben, alle rot (7 über Tests, 2 über `klicktest_umfang_hinweis`).

## 1.9.327 (L2c-2, Punkt 0): Ablage mit Art, Versand und Notiz

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – der Bestand ist „datei“ | Migration mit Vorgabe „abgleich“ (`327_1a`) | 1 rot: v727::test_migration_auf_einem_bestand_sqlite |
| Nr. 1 – nur „datei“ oder „abgleich“ | ablegen() nimmt jede Art (`327_1b`) | 1 rot: v727::test_neue_zeile |
| Nr. 1 – eine neue Zeile ist nie versendet | ablegen() setzt „versendet am“ (`327_1c`) | 1 rot: v727::test_neue_zeile |
| Nr. 2 – nur „versendet am / von“ änderbar | auch die Notiz änderbar (`327_2a`) | 1 rot: v727::test_nur_versendet_laesst_sich_aendern |
| Nr. 2 – „versendet am / von“ änderbar | auch sie gesperrt, wie bis 1.9.326 (`327_2b`) | 1 rot: v727::test_nur_versendet_laesst_sich_aendern |
| Nr. 2 – Art und Monat fest | Art und Monat änderbar (`327_2c`) | 1 rot: v727::test_nur_versendet_laesst_sich_aendern |
| Nr. 3 – je Monat höchstens eine versendete (Modell) | kein eindeutiger Index (`327_3a`) | 1 rot: v727::test_je_monat_hoechstens_eine_versendete |
| Nr. 3 – je Monat höchstens eine versendete (Migration) | die Migration legt den Index nicht an (`327_3b`) | 1 rot: v727::test_migration_auf_einem_bestand_sqlite |
| Nr. 4 – downgrade bricht ab | kein Abbruch (`327_4a`) | 1 rot: v727::test_migration_auf_einem_bestand_sqlite |

9 Gegenproben, alle rot (alle über Tests; die Oberfläche ändert sich in 1.9.327 nicht).

## 1.9.328 (L2c-2, Punkt 1): „An das Steuerbüro gesendet“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur Admin und Büro – Finanzen | jede Rolle darf setzen (`328_1a`) | 1 rot: v728::test_rechte |
| Nr. 1 – mit Zeitpunkt und Konto | ohne Konto („System“) (`328_1b`) | 1 rot: v728::test_setzen_mit_zeitpunkt_und_konto |
| Nr. 1 – nur an einer Datei | auch an einem Abgleich (`328_3a`) | 1 rot: v728::test_je_monat_eine_nur_dateien |
| Nr. 2 – je Monat eine, zweite 409 mit Grund | keine Prüfung je Monat (`328_2a`) | 1 rot: v728::test_je_monat_eine_nur_dateien |
| Nr. 2 – auch zwei zugleich: Meldung statt 500 | der Index schlägt als Fehler durch (`328_2b`) | 1 rot: v728::test_zwei_zugleich_dieselbe_meldung |
| Nr. 2 – schon vermerkt 409 | nicht erkannt (`328_3b`) | 1 rot: v728::test_je_monat_eine_nur_dateien |
| Nr. 3 – zurücknehmen nur der Admin | auch Büro – Finanzen (`328_4a`) | 1 rot: v728::test_zuruecknehmen_nur_der_admin |
| Nr. 4 – Eintrag beim Setzen | keiner (`328_5a`) | 2 rot: v728::test_setzen_mit_zeitpunkt_und_konto, test_zuruecknehmen_nur_der_admin |
| Nr. 4 – Eintrag beim Zurücknehmen | keiner (`328_5b`) | 1 rot: v728::test_zuruecknehmen_nur_der_admin |
| Nr. 4 – mit dem Konto | Eintrag ohne Konto (`328_5c`) | 1 rot: v728::test_setzen_mit_zeitpunkt_und_konto |
| Nr. 4 – abgelehnt kein Eintrag | keine eigene: abgelehnt wird vor dem Eintrag (409 vor record_audit_entry); v728 prüft es (test_je_monat_eine_nur_dateien, test_zwei_zugleich_dieselbe_meldung) | – |
| Nr. 5 – Knopf nur, solange im Monat keine gesendet ist | Knopf trotz gesendeter (`328_6a`; Klicktest `328_K1`) | 1 rot: v728::test_seite_vermerk_und_knopf; Klicktest: „Fiona: kein Knopf mehr im Monat …“, „Anna: „Zurücknehmen“ nur an der gesendeten“, „Anna: „Abbrechen“ lässt den Vermerk stehen“ |
| Nr. 5 – „Zurücknehmen“ nur für den Admin | für jeden (`328_6b`; Klicktest `328_K2`) | 1 rot: v728::test_seite_vermerk_und_knopf; Klicktest: „Fiona: kein Knopf mehr im Monat …“ |
| Nr. 5 – der Vermerk an der Datei | kein Vermerk (`328_6d`; Klicktest `328_K3`) | 1 rot: v728::test_seite_vermerk_und_knopf; Klicktest: „Fiona: die ältere trägt den Vermerk …“, „Anna: „Abbrechen“ lässt den Vermerk stehen“, „Fiona: Vermerk an der jüngeren“ |
| Nr. 5 – „Zurücknehmen“ mit Rückfrage auf der Seite | ohne Rückfrage, gleich zurückgenommen (`328_6e`; Klicktest `328_K4`) | 1 rot: v728::test_seite_abschliessend_und_verdrahtet; Klicktest: „Anna: die Rückfrage auf der Seite“ |
| Nr. 5 – „gesendet“ vermerken ist abschließend | über speichern() (`328_6c`) | 2 rot: v399::test_final_actions_and_only_those_go_through_abschliessen[zeiten.html], v728::test_seite_abschliessend_und_verdrahtet |

19 Gegenproben, alle rot (15 über Tests, 4 über `klicktest_lohndatei_gesendet`). Die Rückfrage auf der Seite kam nach dem ersten Lauf dazu (vorher `confirm()`,
von `tests/test_v518_zeiten_seite.py` abgelehnt) -- danach alle Gegenproben noch einmal, alle rot. Zwei (`328_5a`, `328_5b`) hatten im ersten Anlauf einen Fehler in der Gegenprobe selbst (der Marker als Kommentar verschluckte den Rest der Zeile, nur ERROR) -- der Marker steht jetzt im Text, danach rot.

## 1.9.329 (L2c-2, Punkt 2): „Nach dem Versand geändert“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur die gesendete Datei ist Bezug | jede abgelegte Datei gilt (`329_1a`) | 1 rot: v729::test_ohne_gesendete_datei_keine_liste |
| Nr. 1 – nach „Besprochen“ die jüngste Abgleich-Zeile | ohne Abgleich (`329_1b`) | 1 rot: v729::test_bezug_ist_die_juengste_abgleich_zeile |
| Nr. 1 – nur eine Abgleich-Zeile nach der gesendeten Datei | auch eine ältere (`329_1c`) | 1 rot: v729::test_abgleich_vor_der_gesendeten_zaehlt_nicht |
| Nr. 2 – je Person und Tag mit Stunden | nur Kennzeichen und Lohnart zählen (`329_2a`; Klicktest `329_K3`) | 2 rot: v729::test_aenderung_je_tag_mit_grund, test_bezug_ist_die_juengste_abgleich_zeile; Klicktest im ersten Anlauf GRÜN (kein Fall, in dem sich nur die Stunden ändern) -- nachgezogen (Cems Urlaub wird ein halber Tag), danach rot: „Stand: vier Änderungen“, „je Zeile …“, „der Grund …“ |
| Nr. 2 – Monatszeilen für sich | ohne Monatszeilen (`329_2b`) | 1 rot: v729::test_monatszeilen_fuer_sich |
| Nr. 3 – auch über eine frühere Personalnummer | ohne frühere Nummern (`329_3a`) | 1 rot: v729::test_nummernwechsel_und_lohnstammdaten |
| Nr. 3 – Nummernwechsel als eigene Zeile | keine Zeile (`329_3b`) | 1 rot: v729::test_nummernwechsel_und_lohnstammdaten |
| Nr. 4 – Grund je Tag | keiner (`329_4a`) | 2 rot: v729::test_aenderung_je_tag_mit_grund, test_verschobene_buchung_alter_und_neuer_tag |
| Nr. 4 – Grund je Person | keiner (`329_4b`) | 1 rot: v729::test_nummernwechsel_und_lohnstammdaten |
| Nr. 4 – für viele zugleich als ein Satz oben | nichts oben (`329_4c`) | 1 rot: v729::test_ohne_eintrag_und_allgemein |
| Nr. 4 – erst seit dem Erzeugen des Bezugs | die ganze Historie (`329_4d`) | 4 rot: v729::test_aenderung_je_tag_mit_grund, test_nummernwechsel_und_lohnstammdaten, test_ohne_eintrag_und_allgemein, test_verschobene_buchung_alter_und_neuer_tag |
| Nr. 4 – ohne Eintrag „kein Eintrag …“ | leer (`329_4e`) | 1 rot: v729::test_ohne_eintrag_und_allgemein |
| Nr. 4 – auch alter und neuer Tag | nur der Tag von heute (`329_4f`) | 1 rot: v729::test_verschobene_buchung_alter_und_neuer_tag |
| Nr. 5 – nur Admin und Büro – Finanzen | auch Büro – Auftrag (`329_5a`) | 1 rot: v729::test_route_und_rechte |
| Nr. 5 – falsche Prüfsumme 409 | als Fehler (`329_5b`) | 1 rot: v729::test_route_und_rechte |
| Nr. 5 – schreibt nichts | keine eigene: `test_kein_get_schreibt` (v326) ruft jeden GET-Endpunkt mit Beobachter auf, auch diesen | – |
| Nr. 6 – lädt mit dem Monat | lädt nicht (`329_6a`; Klicktest `329_K1`) | 1 rot: v729::test_seite_laedt_mit_dem_monat; Klicktest: „dez: 2026-12 geladen“, „Bezug …“, „Stand …“, „Tabelle sichtbar …“ |
| Nr. 6 – je Zeile der Grund | ohne Grund (`329_6b`; Klicktest `329_K2`) | 1 rot: v729::test_seite_zeilen_und_bezug; Klicktest: „der Grund aus der Änderungshistorie“ |

20 Gegenproben, alle rot (17 über Tests, 3 über `klicktest_nach_dem_versand`; `329_K3` erst nach dem Nachziehen des Klicktests).

## 1.9.330 (L2c-2, Punkt 3): „Besprochen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – legt eine Abgleich-Zeile ab, danach Bezug | als Datei statt Abgleich (`330_1a`; Klicktest `330_K3`) | 1 rot: v730::test_besprochen_legt_ab_danach_leer_bis_zur_naechsten_aenderung; Klicktest: „danach: keine Änderung …“, „Bezug: besprochen, mit Notiz“, „Ablage …“ |
| Nr. 1 – „… seit „Besprochen““ | immer „nach dem Versand“ (`330_1b`) | 1 rot: v730::test_besprochen_legt_ab_… |
| Nr. 1 – die Rechnung von heute (mit den Prüfungen) | andere Bytes, ohne Prüfungen (`330_4a`) | 2 rot: v730::test_besprochen_legt_ab_…, test_dieselben_pruefungen_wie_das_erzeugen |
| Nr. 2 – Notiz Pflicht | ohne Notiz (`330_2a`) | 1 rot: v730::test_notiz_pflicht |
| Nr. 2 – höchstens 500 Zeichen | beliebig lang (`330_2b`) | 1 rot: v730::test_notiz_pflicht |
| Nr. 2 – leere Notiz meldet die Seite selbst | geht an den Server (`330_2c`) | 1 rot: v730::test_seite (der Klicktest sähe denselben Text vom Server -- deshalb keine Klick-Gegenprobe) |
| Nr. 2 – die Meldung geht beim Tippen weg | bleibt (`330_2d`; Klicktest `330_K4`) | 1 rot: v730::test_seite; Klicktest: „getippt: die Meldung ist weg“ |
| Nr. 3 – nur mit gesendeter Datei | auch ohne (`330_3a`) | 1 rot: v730::test_nur_mit_gesendeter_datei_und_aenderung |
| Nr. 3 – nur mit Änderung | auch ohne (`330_3b`) | 1 rot: v730::test_nur_mit_gesendeter_datei_und_aenderung |
| Nr. 3 – auf der Seite nur bei Änderungen | immer sichtbar (`330_3c`; Klicktest `330_K1`) | 1 rot: v730::test_seite; Klicktest: „danach: keine Änderung, keine Tabelle, kein „Besprochen““ |
| Nr. 4 – dieselben Prüfungen wie das Erzeugen | ohne Prüfungen (`330_4a`, siehe oben) | 2 rot (siehe oben) |
| Nr. 5 – nur Admin und Büro – Finanzen | auch Büro – Auftrag (`330_5a`) | 1 rot: v730::test_rechte |
| Nr. 5 – abschließend | über speichern() (`330_5b`) | 2 rot: v399::test_final_actions_and_only_those_go_through_abschliessen[zeiten.html], v730::test_seite |
| Nr. 5 – in der Ablage „Besprochen …“ | immer „Abgelegt“ (`330_5c`; Klicktest `330_K2`) | 1 rot: v730::test_seite; Klicktest: „Ablage: die Abgleich-Zeile oben, ohne Knopf …“ |
| Nr. 5 – ohne Knopf „An das Steuerbüro gesendet“ | keine eigene: unverändert seit 1.9.328 (`lohndateiKnopf()` gibt an einem Abgleich nichts; `328_6a`/v728 und die Prüfung „Ablage …“ im Klicktest decken es) | – |

17 Gegenproben, alle rot (13 über Tests, 4 über `klicktest_besprochen`).

## 1.9.331 (L2c-2, Punkt 4): „Nach dem Versand geändert“ in „Prüfen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die letzten zwölf Monate | zwei Jahre (`331_1a`) | 1 rot: v731::test_je_monat_ohne_namen |
| Nr. 1 – nur Monate mit Änderungen | auch ohne (`331_1b`) | 1 rot: v731::test_je_monat_ohne_namen |
| Nr. 1 – bis heute | auch ein Monat nach heute (`331_1c`) | 1 rot: v731::test_je_monat_ohne_namen |
| Nr. 1 – ohne Namen | mit dem ersten Namen (`331_1d`) | 1 rot: v731::test_je_monat_ohne_namen |
| Nr. 1 – nach „Besprochen“ „… seit „Besprochen““ | keine eigene: derselbe Text wie die Liste (`330_1b` macht v730 rot); v731 prüft ihn mit | – |
| Nr. 1 – falsche Prüfsumme steht mit Meldung da | bricht ab (`331_1e`) | 1 rot: v731::test_falsche_pruefsumme |
| Nr. 2 – der Weg in diesen Monat | ohne Monat (`331_2a`) | 1 rot: v731::test_seite |
| Nr. 2 – „Monat & Lohn“ öffnet diesen Monat | lohnmonat nicht gelesen (`331_2b`; Klicktest `331_K1`) | 1 rot: v731::test_seite; Klicktest: „der Weg öffnet „Monat & Lohn“ im Dezember mit der Liste“ |
| Nr. 3 – nur Admin und Büro – Finanzen | für jede Rolle (`331_3a`; Klicktest `331_K2`) | 1 rot: v731::test_pruefen_nur_admin_und_finanzen; Klicktest: „Bea: keine Karte“ |
| Nr. 3 – „Alles erledigt“ nur ohne sie | ohne nv (`331_3b`; Klicktest `331_K3`) | 1 rot: v714::test_seite_aufbau; Klicktest im ersten Anlauf GRÜN („Alles erledigt“ war schon wegen „Tage ohne Eintrag“ verborgen) -- nachgezogen (Uhr Mo 04.01.2027: keine Tage ohne Eintrag, die Karte ist der einzige Hinweis), danach rot: „Fiona: die Karte ist der einzige Hinweis …“ |
| Nr. 3 – die Karte erscheint | nie sichtbar (Klicktest `331_K4`) | Klicktest: „Fiona: die Karte mit der Zahl …“, „Fiona: die Karte ist der einzige Hinweis …“ |
| Nr. 3 – sperrt nichts, zählt nicht am Reiter | keine eigene: es gibt keinen Code, der sie in den Abschluss oder die Zahl am Reiter einträgt | – |

13 Gegenproben, alle rot (9 über Tests, 4 über `klicktest_nach_dem_versand_pruefen`; `331_K3` erst nach dem Nachziehen des Klicktests, danach K1, K2 und K4
noch einmal, rot).

## 1.9.332 (Vorweg zu L2c-3): „An das Steuerbüro gesendet“ unter PostgreSQL

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „als gesendet vermerkt“ passt in die Spalte | wieder die lange Aktion von 1.9.328 (`332_1a`) | 2 rot: v732::test_gesendet_und_zuruecknehmen_unter_postgresql (der Fehler von 1.9.328 unter PostgreSQL), test_jede_aktion_passt_in_ihre_spalte |
| Nr. 1 – „Vermerk zurückgenommen“ passt in die Spalte | wieder die lange Aktion (`332_1b`) | 2 rot: dieselben beiden |
| Nr. 2 – jede feste Aktion passt, eine nicht feste wird genannt | eine zusammengesetzte Aktion an anderer Stelle (`332_2a`) | 1 rot: v732::test_jede_aktion_passt_in_ihre_spalte |
| Nr. 3 – Setzen und Zurücknehmen auch gegen PostgreSQL | keine eigene: `332_1a`/`332_1b` machen den PostgreSQL-Test rot -- er läuft in der Suite (ERP_TEST_POSTGRES_URL gesetzt, nicht übersprungen) | – |

3 Gegenproben, alle rot (über Tests).

## 1.9.333 (L2c-3, Punkt 0): Messung von „Prüfen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – unter 1 s, das Fenster bleibt bei zwölf Monaten | keine eigene: eine Messung, kein Schutz im Code (`MONATE_ZURUECK` bleibt 12; dass das Fenster wirkt, prüfen v731 und die Gegenprobe `331_1a`) | – |
| Nr. 2 – das Skript legt den vollständigen Bestand an (zwölf gesendete Monate) | nur elf Monate gesendet (`333_2a`) | 1 rot: v733::test_messung_laeuft |
| Nr. 2 – es misst je Tag beide Fenster | ohne das Fenster von drei Monaten (`333_2b`) | 1 rot: v733::test_messung_laeuft |

2 Gegenproben, beide rot (über Tests).

## 1.9.334 (L2c-3, Punkt 1): das Arbeitszeitkonto in „Monat & Lohn“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Karte lädt mit dem Monat | lädt das Konto nicht (`334_1a`; Klicktest `334_K1`) | 1 rot: v734::test_seite; Klicktest: „jan: Konto gezeichnet“, „Januar: die Karte mit „vorläufig““, „Januar: Soll, Saldo und Stand …“, „Februar: bis gestern gezählt“ u. a. |
| Nr. 1 – Soll, Saldo, Stand je gewerblicher Person, vom Server | keine eigene: die Zahlen kommen unverändert aus `konten()` (v721); die Seite rechnet nichts -- `334_2a`/`334_K2` zeigen, dass die Zeile die Werte des Servers zeichnet | – |
| Nr. 2 – „vorläufig – maßgeblich ist die Lohnabrechnung“ darüber | ohne (`334_5a`) | 1 rot: v734::test_zeilen_und_stand |
| Nr. 3 – ohne Startwert „Startwert folgt“ | der Stand statt „Startwert folgt“ (`334_2a`; Klicktest `334_K2`) | 1 rot: v734::test_zeilen_und_stand; Klicktest: „Januar: Soll, Saldo und Stand je gewerblicher Person“ |
| Nr. 4 – vor Januar 2027 keine Karte und keine Anfrage | auch vor 2027 (`334_1b`; Klicktest `334_K3`) | 1 rot: v734::test_kontobeginn_und_startwert_wie_der_server; Klicktest im ersten Anlauf GRÜN (die Anfrage scheiterte am Server, die Karte blieb versteckt) -- nachgezogen (keine Anfrage ans Konto, keine Meldung), danach rot: „Dezember 2026: keine Karte, keine Anfrage …“ |
| Nr. 5 – laufender Monat „Stand bis <gestern>“ | immer „Stand am Monatsende“ (`334_3a`) | 1 rot: v734::test_laufender_monat_bis_gestern_und_vor_2027_nichts |
| Nr. 6 – Spalten „Konto · 0,25 je Tag“ | ohne Einheit (`334_4a`) | 1 rot: v734::test_seite |

9 Gegenproben, alle rot (6 über Tests, 3 über `klicktest_konto_monat`; `334_K3` erst nach dem Nachziehen des Klicktests, danach K1 und K2 noch einmal, rot).

## 1.9.335 (L2c-3, Punkt 2): „Tage ansehen“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur Tage mit Sollzeit, Stunden oder Posten | auch leere Tage (`335_1a`) | 1 rot: v735::test_zeilen_ohne_leere_tage |
| Nr. 1 – „Tage ansehen“ öffnet die Tage der Person | der Knopf tut nichts (`335_2a`; Klicktest `335_K1`) | 1 rot: v735::test_seite; Klicktest: „Ada: der Dialog mit Name und Stand“ und alle Prüfungen im Dialog |
| Nr. 2 – „gutgeschrieben“ bzw. „– zählt nicht“ | immer „gutgeschrieben“ (`335_1c`; Klicktest `335_K3`) | 1 rot: v735::test_vermerk_je_tag; Klicktest: „Ada: der Freizeitausgleich zählt nicht“ |
| Nr. 2 – der Vermerk des Servers | ohne (`335_1d`) | 1 rot: v735::test_vermerk_je_tag |
| Nr. 2 – „kein Eintrag – zählt als Minus“ | ohne (`335_1b`; Klicktest `335_K2`) | 2 rot: v735::test_vermerk_je_tag, test_zeilen_ohne_leere_tage; Klicktest: „Bo: kein Eintrag zählt als Minus, ohne Startwert“ |
| Nr. 3 – im Kopf „vorläufig – maßgeblich ist die Lohnabrechnung“ | ohne (`335_2b`) | 1 rot: v735::test_seite |
| Nr. 3 – Stand, ohne Startwert „Startwert folgt“; keine Anfrage | keine eigene: Kopf und Stand nehmen dieselben Werte wie die Zeile der Karte (`334_2a`); dass der Dialog nicht fragt, prüft v735::test_seite (kein `api(` in `kontoTageOeffnen`) -- es gibt keinen Schutz im Code, den eine Gegenprobe aushebeln könnte | – |

9 Gegenproben, alle rot (6 über Tests, 3 über `klicktest_konto_tage`).
