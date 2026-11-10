# Gegenproben der Geräte-Runde (ab 1.9.293)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R5e (`docs/archiv/gegenproben-stufe6-r5e.md`): in einer eigenen
Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript) mit dem Marker `GEGENPROBE` ändern, die genannten Tests bzw. den Klicktest laufen
lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler) bzw. der Klicktest endet nicht wie erwartet.

## 1.9.293 (Vorweg V1): Namensspalte ab 2 Wochen 200 px

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ab 2 Wochen 200 px | wie bis 1.9.292 nur unter 1400 px (`293_1a`, `293_1c`) | 5 rot: v693::test_namensspalte (1440 px mit 2, 3, 4 Wochen), test_aufbau; Klicktest auftraege: „1440 px, 2 Wochen: Namensspalte 200 px, rollt nicht“ |
| Nr. 1 – mit 1 Woche ab 1400 px weiter 230 px | immer 200 px (`293_1b`, `293_1d`) | 3 rot: v693::test_namensspalte (1440 und 1920 px mit 1 Woche), test_aufbau; Klicktest: „1440 hell, 1 Woche: Namensspalte 230 px“ |
| Nr. 2 – 3 und 4 Wochen dürfen rollen | keine -- eine Erlaubnis, unverändert seit 1.9.283 (mindestens 56 px je Tag) | -- |

4 Gegenproben (2 gegen Tests, 2 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben.

## 1.9.294 (Vorweg V2): der Kran bei schmalen Tagen nur mit seinem Zeichen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – bis 43,9 px Inhalt der Karte nur das Kranzeichen | ohne die Regel (`294_1a`, `294_1c`) | 1 rot: v694::test_kran_bis_44_px_nur_mit_zeichen; Klicktest auftraege: „1440 px, 2 Wochen (58 px je Tag): … Kran nur mit Zeichen“, „1280, 3 Wochen: Tag 56 px, kein Chip gekürzt, Kran nur mit Zeichen“ |
| Nr. 2 – das Kranzeichen verschwindet nie | mit dem Namen verschwindet auch das Zeichen (`294_1b`, `294_1d`) | 1 rot: v694::test_kran_bis_44_px_nur_mit_zeichen; Klicktest: dieselben zwei Prüfungen (kein sichtbares Zeichen) |
| Nr. 2 – darüber bleibt „Kr“ (61 px je Tag) | Grenze 50 px (`294_2a`) | Klicktest: „1280 dunkel, 2 Wochen (61 px je Tag): der Kran mit „Kr““. Test: keine eigene -- die Grenze in Pixeln prüft nur der Klicktest am Verhalten |

5 Gegenproben (2 gegen Tests, 3 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Beim Bauen: die erste Grenze (45 px,
gerechnet mit 5 px Innenabstand der Zelle) nahm auch bei 61 px je Tag den Namen weg -- der Klicktest fand es; gemessen: 4,5 px Innenabstand, 44,3 px Inhalt.
Der Test hieß zuerst „…_unter_46_px_…“ (umbenannt, die beiden Test-Gegenproben danach noch einmal: rot).

## 1.9.295 (Vorweg V4): schmaler Geräte-Chip mit der Zahl am Ende des Kurznamens

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ein Gerät zeigt die Zahl am Ende | ohne die Zahl (`295_1a`, `295_1d`) | 5 rot: v695::test_schmaler_chip (die Geräte mit Zahl), test_chip_mit_der_zahl_und_dem_namen_im_title; Klicktest auftraege: „2 Wochen: Geräte „202“, „204“, der Kran „Kr“ …“ |
| Nr. 1 – der Chip gibt seine Art mit | `chipName()` ohne die Art (`295_1b`, `295_1e`) | 1 rot: v695::test_chip_mit_der_zahl_und_dem_namen_im_title; Klicktest: dieselbe Prüfung |
| Nr. 1 – sonst wie bisher zwei Zeichen | drei Zeichen (`295_1c`) | 5 rot: v695::test_schmaler_chip (Kran, A1-Bagger, Personen, Kolonne) |
| Nr. 2 – nur Geräte | die Zahl bei jeder Art (`295_2a`) | 2 rot: v695::test_schmaler_chip („Ole 2“, „Team 2“) |
| Nr. 3 – mit 1 Woche der volle Name | die Zahl auch mit 1 Woche (`295_3a`, `295_3b`) | 1 rot: v695::test_schmaler_chip (1 Woche); Klicktest: „Wasserturm Mo“, „Wasserturm Fr mit Kai und Kran“, „Garage vorläufig“, „Wartung Do“, „Kranvermietung Fr“, „Wochenleiste Kran“, „Wochenleiste HS-DK 202“ |

8 Gegenproben (5 gegen Tests, 3 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben.

## 1.9.296 (Punkt 1): ein Speicherweg in einer Transaktion

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Teil-Update | der PUT übernimmt das ganze Schema (`model_dump()`, `296_1a`) | 13 rot: v696 (u. a. test_teil_update_laesst_ungesendete_felder_stehen, test_ein_status_fuer_beides_und_kurzname, test_aufbau) |
| Nr. 2 – Anlegen mit `einplanbar` legt beides an | `einplanbar` überhört (`296_2a`) | 13 rot: v696 (u. a. test_anlegen_mit_haken_legt_beides_an, test_haken_setzen_…, test_haken_entfernen_…) |
| Nr. 2 – eine Transaktion | ein eigener Commit nach dem Anlegen des Plantafel-Geräts (`296_2b`) | 1 rot: v696::test_aufbau (`geraet_speichern()` committet nicht). Am Verhalten nicht zu sehen: jede Prüfung läuft vor dem ersten Schreiben -- deshalb am Aufbau geprüft |
| Nr. 3 – Ressourcennummer „R-<id>“ | keine Nummer (`296_3a`) | 2 rot: v696::test_anlegen_mit_haken_legt_beides_an, test_ressourcennummer_mit_zusatz_wenn_vergeben |
| Nr. 3 – vergeben: mit Zusatz | kein Zusatz (`296_3b`) | 1 rot: v696::test_ressourcennummer_mit_zusatz_wenn_vergeben |
| Nr. 4 – Identität mit Plantafel in der Ressource | immer ins Betriebsmittel (`296_4a`) | 2 rot: v696::test_anlegen_mit_haken_legt_beides_an, test_identitaet_mit_haken_in_der_ressource_ohne_im_betriebsmittel |
| Nr. 5 – Haken setzen: die Spalten des Betriebsmittels werden leer | sie bleiben (`296_5a`) | 1 rot: v696::test_haken_setzen_laesst_die_werte_wandern |
| Nr. 5 – die Werte des Geräts wandern | nur die gesendeten (`296_5b`) | 2 rot: v696::test_haken_setzen_laesst_die_werte_wandern, test_haken_setzen_ohne_typ_legt_nichts_an |
| Nr. 6 – verknüpfen übernimmt das vorhandene Gerät | die gesendeten Werte gelten (`296_6a`) | 1 rot: v696::test_freies_vorhandenes_geraet_verknuepfen |
| Nr. 7 – Haken entfernen: die Werte wandern | nichts wandert (`296_7a`) | 7 rot: v696::test_haken_entfernen_benutzt_deaktiviert_ohne_rueckfrage (alle Fälle) u. a. |
| Nr. 7 – nirgends benutzt: gelöscht | nie gelöscht (`296_7b`) | 1 rot: v696::test_haken_entfernen_nirgends_benutzt_loescht_die_ressource |
| Nr. 7 – mit Postfach: deaktiviert | das Postfach zählt nicht (`296_7c`) | 1 rot: v696::test_haken_entfernen_benutzt_deaktiviert_ohne_rueckfrage[postfach] |
| Nr. 7 – künftige Einsätze: Rückfrage | keine Rückfrage (`296_7d`) | 1 rot: v696::test_haken_entfernen_mit_kuenftigem_einsatz_fragt_zurueck |
| Nr. 7 – stornierte Aufträge zählen nicht | sie zählen (`296_7e`) | 1 rot: v696::…[stornierter_einsatz] |
| Nr. 7 – nur Tage ab heute | auch vergangene Tage des Geräts (`296_7f`) | 1 rot: v696::…[nur_vergangene_tage] |
| Nr. 8 – ein Status für beides | die Ressource bleibt (`296_8a`) | 1 rot: v696::test_ein_status_fuer_beides_und_kurzname |
| Nr. 9 – Kurzname über `ressource` | überhört (`296_9a`) | 3 rot: v696::test_anlegen_mit_haken_legt_beides_an, test_ein_status_…, test_haken_setzen_… |
| Nr. 10 – Typ Pflicht, keine stille Vorgabe | still „Maschine“ (`296_10a`) | 2 rot: v696::test_anlegen_mit_haken_ohne_typ_oder_name_legt_nichts_an[Typ], test_haken_setzen_ohne_typ_legt_nichts_an |
| Nr. 11 – kein „Ressource“ in den Meldungen | die alte Meldung (`296_11a`) | 1 rot: v696::test_freies_vorhandenes_geraet_verknuepfen |

20 Gegenproben, alle gegen Tests, alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Klicktests: keine -- die Seite speichert schon über den neuen
Weg, ihr Aufbau wird mit 1.9.297 ersetzt; das Speichern über die Seite prüft ab dort `klicktest_geraete.py` (Gegenproben dort).
Beim Bauen gefunden: ein abgelehntes Anlegen ließ im Test das Betriebsmittel in der geteilten Sitzung hängen -- `create_asset()`/`update_asset()` rollen
seither bei jedem Fehler zurück; der Test legte zuerst einen Einsatz an einem stornierten Auftrag an, das lehnt die Plantafel zu Recht ab (Test berichtigt).

## 1.9.297 (Punkt 2): ein Formular je Gerät

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „Auf der Plantafel einplanbar“, kein „Ressource“ | der alte Text „Mit Ressourcenbezug“ (`297_1a`, `297_1b`) | 1 rot: v697::test_kein_wort_ressource_auf_der_seite; Klicktest geraete: „Pritsche: nirgends „Ressource““ und alle zwölf Bilder-Prüfungen |
| Nr. 2 – die Angaben immer oben | mit Haken leer wie bis 1.9.295 (`297_2a`, `297_2c`) | 1 rot: v697::test_mit_haken_angaben_oben_und_abschnitt_plantafel; Klicktest: „Pritsche“ (Angaben, nicht geladen), „Kran“ u. a. |
| Nr. 2 – mit Haken der Typ Pflicht | das Sternchen nie (`297_2b`, `297_2d`) | 2 rot: v697::test_mit_haken_…, test_ohne_haken_…; Klicktest: „Pritsche: Typ als Pflicht“, „Leiter mit Haken“ |
| Nr. 3 – mit Haken der Abschnitt „Plantafel“ | der Abschnitt nie (`297_3a`, `297_3c`) | 2 rot: v697::test_mit_haken_…, test_ohne_haken_…; Klicktest: „Pritsche“, „Leiter mit Haken“, sechs Bilder mit Haken |
| Nr. 3 – der Link nur für den Admin | der Link für alle (`297_3b`, `297_3d`) | 2 rot: v697::test_aufbau, test_mit_haken_…; Klicktest: „Bea: Postfach ohne Link“ |
| Nr. 4 – die Auswahl nur mit freiem Gerät | auch ohne freies (`297_4a`) | 1 rot: v697::test_ohne_haken_kein_abschnitt_und_haken_setzen. Klicktest: keine eigene -- dort gibt es zu dem Zeitpunkt ein freies |
| Nr. 4 – gewählt, stehen oben dessen Angaben | nichts gefüllt (`297_4b`, `297_4c`) | 1 rot: v697::test_verknuepfen_zeigt_die_angaben_des_vorhandenen_geraets; Klicktest: „Verknüpfen: die Angaben oben vom vorhandenen Gerät“ |
| Nr. 5 – nach dem Speichern auf dem Gerät, kein Link ins Formular der Ressource | keine eigene -- belegt durch v697::test_kein_wort_ressource_auf_der_seite (kein `/master-data/resources/`) und den Klicktest („Pritsche: … die Seite bleibt auf dem Gerät“) | -- |
| Nr. 6 – Rückfrage beim Entfernen | keine Rückfrage, der Fehler bleibt stehen (`297_6a`) | Klicktest: „Kran: Rückfrage nennt den Einsatz“, „Kran bestätigt“, „Kran: ohne Plantafel …“. Test: keine -- die Rückfrage läuft nur im Browser |

14 Gegenproben (7 gegen Tests, 7 gegen den Klicktest), alle rot, jede Datei byte-genau zurück, kein Marker geblieben. Beim Bauen: die ersten Bilder waren nur
der sichtbare Ausschnitt (der Abschnitt „Plantafel“ lag bei 412 px darunter, die Kopfleiste verdeckte die erste Zeile) -- jetzt die ganze Seite; der Lauf der
betroffenen Klicktests fand die Erwartung „Leiter · Eigenständig“ in klicktest_rahmen (angepasst).

## 1.9.298 (Punkt 3): Liste und Anlegen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „+ Hinzufügen“ legt mit Haken auch das Plantafel-Gerät an | `einplanbar` immer false im Körper (`298_1a`, `298_1b`) | 1 rot: v698::test_anlegen_mit_haken_und_verknuepfen; Klicktest geraete: „Betriebsmittel anlegen“, „+ Hinzufügen“ (zweimal), „Suche über den Kurznamen“ |
| Nr. 1 – mit Haken der Typ Pflicht | das Sternchen nie (`298_1c`) | Klicktest: „+ Hinzufügen mit Haken“. Test: keine eigene -- die Anzeige setzt erst der Haken im Browser |
| Nr. 2 – die Auswahl nur mit freiem Gerät | nie (`298_2a`, `298_2c`) und immer (`298_2b`) | 1 rot: v698::test_anlegen_mit_haken_und_verknuepfen (nie); Klicktest: „Betriebsmittel anlegen“ (nie), „+ Hinzufügen“ (immer, dort gibt es kein freies) |
| Nr. 3 – „Plantafel“ statt „Ressourcenbezug“ | das alte Wort (`298_3a`, `298_3b`) | 1 rot: v698::test_liste_plantafel_und_nur_plantafel; Klicktest: „Liste“ (zweimal) und alle sechs Bilder der Liste |
| Nr. 4 – „nur Plantafel“ steht in der Liste | die Zeilen nie (`298_4a`, `298_4c`) | **zuerst grün** gegen v698 (der Test prüfte nur Filter und Text der Zeile, nicht, dass sie in die Liste kommt) -- nachgezogen, dieselbe Gegenprobe noch einmal: 1 rot: v698::test_liste_plantafel_und_nur_plantafel. Klicktest: „Liste“, „Betriebsmittel anlegen“ (dreimal) |
| Nr. 4 – ein inaktives nicht | auch die inaktiven (`298_4b`, `298_4d`) | 1 rot: v698::test_liste_plantafel_und_nur_plantafel; Klicktest: „Liste“ (der Autokran nach dem Entfernen des Hakens als zweites „nur Plantafel“), „Betriebsmittel anlegen“ (dreimal) |
| Nr. 4 – „Betriebsmittel anlegen“ startet mit Haken und verknüpft | die Vorgabe aus der Adresse nie (`298_4e`) | Klicktest: „Betriebsmittel anlegen“ (dreimal). Test: keine eigene -- die Vorgabe wirkt nur im Browser |
| Nr. 5 – die Suche findet den Kurznamen | ohne Kurzname (`298_5a`, `298_5b`) | 1 rot: v698::test_suche_findet_den_kurznamen; Klicktest: „Suche über den Kurznamen“ |
| Nr. 6 – Modul aus: „Fuhrpark & Maschinen“ bleibt | „+ Hinzufügen“ auch dort ins Formular der Betriebsmittel (`298_6a`) | 1 rot: v698::test_modul_aus_bleibt_das_formular_fuhrpark. Klicktest: keine -- er läuft mit eingeschaltetem Modul |

16 Gegenproben (7 gegen Tests, 9 gegen den Klicktest), alle rot -- `298_4a` erst nach dem Nachziehen von v698; jede Datei byte-genau zurück, kein Marker
geblieben. Vor dem Festhalten fand der volle Lauf zwei Wächter rot (v414: `Number()` auf der Auswahl „verknüpfen“; v447: Typ und Auswahl über `.value`
gesetzt statt über `auswahlOptionen()`) -- jetzt sucht das Formular das Gerät über den Text seiner ID, baut beide Auswahlen über `auswahlOptionen()` neu und
blendet die Auswahl „verknüpfen“ nur aus (sie steht immer im Markup).

## 1.9.299 (Punkt 4): Änderungshistorie, N1, N6

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Betriebsmittel in der Historie | das Betriebsmittel nicht in `AUDITED_TYPES` (`299_1a`) | 1 rot: v699::test_betriebsmittel_und_pruefung_in_der_historie (keine Einträge „Betriebsmittel“) |
| Nr. 1 – Prüffristen in der Historie | die Prüffrist nicht in `AUDITED_TYPES` (`299_1b`) | 1 rot: v699::test_betriebsmittel_und_pruefung_in_der_historie (keine Einträge „Prüffrist“) |
| Nr. 1 – die Bezeichnung wie auf der Seite des Geräts | ohne Nummer (`299_1c`) | 1 rot: v699::test_betriebsmittel_und_pruefung_in_der_historie („Pritsche HS-DK 202“ statt „BM-7 Pritsche HS-DK 202“) |
| Nr. 2 – ein neues Betriebsmittel gleich mit Nummer und Namen | das Betriebsmittel gleich zu Beginn in der Sitzung, wie bis 1.9.298 (`299_2a`) | 1 rot: v699::test_betriebsmittel_und_pruefung_in_der_historie (ein Eintrag nur „Betriebsmittel“) |
| Nr. 3 – Löschen eines Plantafel-Geräts mit Betriebsmittel: 409 | ohne die Prüfung (`299_3a`) | 1 rot: v699::test_ressource_mit_betriebsmittel_nicht_loeschen (200 statt 409) |
| Nr. 4 – gleichzeitige Verknüpfung: Meldung statt 500 | ohne die Umwandlung des IntegrityError (`299_4a`) | 1 rot: v699::test_gleichzeitige_verknuepfung_meldung_statt_500 (IntegrityError statt 422) |

6 Gegenproben, alle gegen Tests, alle rot -- je die rote Zeile angesehen, jede scheitert an ihrer eigenen Prüfung; jede Datei byte-genau zurück, kein Marker
geblieben. Klicktests: keine -- kein Klicktest liest die Änderungshistorie eines Betriebsmittels, und die beiden 500er sind über die Seiten nicht zu erreichen
(die Liste bietet kein Löschen eines Plantafel-Geräts mit Betriebsmittel, die Gleichzeitigkeit braucht zwei Anfragen im selben Augenblick).

# Nachrunde der Geräte-Runde (ab 1.9.300)

Bestätigt am 10.11.2026: die Festlegungen 1.9.293–1.9.299. Fünf Punkte, je eine Version: 0 Wackler test_v596, 1 „Ressource“ heißt überall „Gerät“, 2 „Inaktive
ausblenden“ in der Liste der Betriebsmittel, 3 die Suche findet „nur Plantafel“, 4 „Betriebsmittel anlegen“ wie die Seite des Geräts. Ablauf wie oben.

## 1.9.300 (Punkt 0): Wackler test_v596

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – das innere pytest sammelt nur im Ordner der Probedateien | ohne `--confcutdir` (`300_1a`) | 1 rot: v596::test_sammelt_nur_im_eigenen_ordner (der Baum beginnt bei `<Dir Users>`) |

1 Gegenprobe gegen den Test, rot; die Datei byte-genau zurück. Die Gegenprobe ändert den Test selbst (die Behebung steht dort, nicht unter `app/`).
Klicktests: keine -- die Änderung betrifft nur einen Test.

## 1.9.301 (Punkt 1): „Ressource“ heißt überall „Gerät“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Auswahlliste „Gerätetypen · Fuhrpark & Maschinen“ (neue Installation) | die bisherige Bezeichnung in `app/option_settings.py` (`301_1a`) | 2 rot: v701::test_auswahlliste_heisst_geraetetypen, test_keine_meldung_nennt_ressource |
| Nr. 1 – im Bestand über die Migration | `upgrade()` tut nichts (`301_2a`) | 2 rot: v701::test_migration_auf_einem_bestand_sqlite, …_postgresql |
| Nr. 1 – nur wo genau die bisherige Bezeichnung steht | ohne die Bedingung auf die Bezeichnung (`301_2b`) | 2 rot: dieselben (eine andere Bezeichnung wurde umgestellt) |
| Nr. 2 – „Kolonnen / Geräte“ | der Reiter wie bisher (`301_3a`) | 2 rot: v701::test_keine_vorlage_zeigt_ressource, test_neue_texte_stehen |
| Nr. 2 – „Noch keine Geräte angelegt.“ | der Text wie bisher (`301_4a`) | 2 rot: dieselben |
| Nr. 3 – Modul aus: „N planbare Geräte“ | der Untertitel wie bisher (`301_5a`) | 2 rot: dieselben |
| Nr. 3 – Modul aus: „Gerät anlegen“ / „Gerät bearbeiten“ | der Titel wie bisher (`301_5b`) | 2 rot: dieselben |
| Nr. 4 – „Gerät nicht gefunden.“ | die Meldung von `GET /api/resources/{id}` wie bisher (`301_6a`) | 2 rot: v701::test_meldungen_nennen_das_geraet, test_keine_meldung_nennt_ressource |
| Nr. 4 – Konflikt ohne Namen „Gerät #…“ | „Ressource #…“ in `app/planning.py` (`301_6b`) | 1 rot: v701::test_keine_meldung_nennt_ressource |
| Nr. 5 – angezeigt „Gerät“ | ohne die Übersetzung von „Ressource“ (`301_7a`) | 2 rot: v701::test_angezeigte_arten_und_felder, test_historie_zeigt_geraet_gespeichert_bleibt_ressource |
| Nr. 5 – „Gerät am Einsatz“ | ohne die Übersetzung von „Plantafel-Gerät“ (`301_7b`) | 1 rot: v701::test_angezeigte_arten_und_felder |
| Nr. 5 – „Gerät der Kolonne“ | ohne „Team-Ressource“ (`301_7c`) | 2 rot: v701::test_angezeigte_arten_und_felder, test_keine_meldung_nennt_ressource |
| Nr. 5 – „Gerät der Kolonne (AV)“ | ohne „AV-Team-Ressource“ (`301_7d`) | 2 rot: dieselben |
| Nr. 6 – gespeichert bleibt die bisherige Art | `TYPE_LABELS` speichert „Gerät“ (`301_8a`) | 3 rot: v699::test_betriebsmittel_und_pruefung_in_der_historie, v701::test_angezeigte_arten_und_felder, test_historie_zeigt_geraet_gespeichert_bleibt_ressource (der Filter mit der gespeicherten Art fand die neuen Einträge nicht mehr) |
| Nr. 7 – Feld „Gerätetyp“ | `FIELD_LABELS` wie bisher (`301_9a`) | 1 rot: v701::test_angezeigte_arten_und_felder |
| Nr. 7 – auch bei älteren Einträgen | ohne `ALTE_FELDNAMEN` (`301_9b`) | 2 rot: v701::test_angezeigte_arten_und_felder, test_historie_zeigt_geraet_gespeichert_bleibt_ressource |

16 Gegenproben, alle gegen Tests, alle rot -- je die rote Zeile angesehen; jede Datei byte-genau zurück, kein Marker geblieben. Die Migration auch gegen
PostgreSQL in einem Wegwerf-Schema mit Bestand. `301_9a` fängt nur der Einzeltest: ein neuer Eintrag speichert die Bezeichnung des Felds beim Schreiben, und die
alte („Ressourcentyp“) übersetzt `ALTE_FELDNAMEN` beim Lesen -- angezeigt wird in beiden Fällen „Gerätetyp“. Klicktests: keine eigene Gegenprobe -- kein
Klicktest liest diese Texte; die Klicktests der berührten Seiten laufen vor dem Commit.

## 1.9.302 (Punkt 2): „Inaktive ausblenden“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Kästchen über der Liste, Vorgabe angehakt | Vorgabe „zeigen“ (`302_1a`, `302_1b`) | 2 rot: v702::test_vorgabe_angehakt_und_eigene_wahl_je_liste, test_ohne_speicher_gilt_die_wahl_bis_zum_neuladen; Klicktest: „Inaktive: angehakt (Vorgabe)“, „Inaktive angehakt: …“, „Rüttler: …“ u. a. (9 Prüfungen) |
| Nr. 2 – eigene Wahl je Liste | der Schlüssel der Mitarbeiter (`302_2a`, `302_2b`) | 2 rot: v702::test_vorgabe_angehakt_und_eigene_wahl_je_liste, test_umschalten_merkt_im_browser_und_zeichnet_neu; Klicktest: „Mitarbeiter: eigene Wahl, weiter angehakt“ und die Bilder „Liste …“ (7 Prüfungen) |
| Nr. 3 – ohne Haken grau | ohne die Klasse `inaktiv` an den Betriebsmitteln (`302_3a`, `302_3b`) | 1 rot: v702::test_inaktive_zeilen_grau_und_nur_plantafel_inaktiv; Klicktest: „Inaktive ohne Haken: drei Zeilen mehr“, „… grau …“ |
| Nr. 4 – „nur Plantafel · inaktiv“ | die Pille ohne „· inaktiv“ (`302_4a`, `302_4c`) | 2 rot: v702::test_inaktive_zeilen_grau_und_nur_plantafel_inaktiv, v698::test_liste_plantafel_und_nur_plantafel; Klicktest: „Inaktive ohne Haken: Kompressor, die Reste …“, „Liste ohne Haken …“ (7 Prüfungen) |
| Nr. 4 – ohne Haken auch das inaktive Gerät ohne Betriebsmittel | „nur Plantafel“ immer nur aktive (`302_4b`, `302_4d`) | 1 rot: v702::test_zeilen_und_zahlen; Klicktest: „Inaktive ohne Haken …“, „Rüttler: …“ (6 Prüfungen) |
| Nr. 5 – „N inaktiv“ über Betriebsmittel und Geräte ohne Betriebsmittel | nur die Betriebsmittel gezählt (`302_5a`, `302_5b`) | 1 rot: v702::test_zeilen_und_zahlen; Klicktest: „Inaktive: angehakt (Vorgabe), Zahl daneben“ und alle Bilder der Liste (14 Prüfungen) |
| Nr. 6 – Untertitel wie bisher (aktive „nur Plantafel“) | alle Geräte ohne Betriebsmittel gezählt (`302_6a`, `302_6b`) | 1 rot: v702::test_zeilen_und_zahlen; Klicktest: „Liste: Untertitel …“, „Inaktive ohne Haken: grau, Zahl und Untertitel unverändert“ |
| Nr. 7 – Anlegen nimmt auch ein inaktives freies Gerät | nur ein aktives (`302_7a`, `302_7c`) | 1 rot: v702::test_anlegen_nimmt_auch_ein_inaktives_freies_geraet; Klicktest: „Rüttler: das Anlegen mit dem Gerät“ u. a. (3 Prüfungen) |
| Nr. 7 – Status wie das Gerät | ohne die Übernahme des Status (`302_7b`, `302_7d`) | 1 rot: v702::test_anlegen_nimmt_auch_ein_inaktives_freies_geraet; Klicktest: „Rüttler: Haken, Auswahl mit „(inaktiv)“, Status Inaktiv“, „Rüttler: verknüpft, beide inaktiv“ und die Bilder (das Gerät wurde aktiv, „3 inaktiv“ wurde „2“) |

18 Gegenproben (9 gegen Tests, 9 gegen den Klicktest), alle rot; jede Datei byte-genau zurück, kein Marker geblieben.
