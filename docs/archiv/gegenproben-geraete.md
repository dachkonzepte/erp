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
