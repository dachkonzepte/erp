# Gegenproben der Runde Stufe 6, R4b (ab 1.9.253)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R4 (`docs/archiv/gegenproben-stufe6-r4.md`): in
einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Migration, Skript) mit dem Marker `GEGENPROBE` ändern, die
genannten Tests laufen lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler).

## 1.9.253 (Punkt 1): Kennzeichen „Plantafel“ am Mitarbeiter

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – drei Werte, am Server erzwungen | freier Text (`253_1a`) | 1 rot: v653::test_anlegen_ohne_angabe_ist_einplanbar_aendern_ohne_angabe_unveraendert |
| Nr. 1 – Auswahl im Formular | ohne „nicht zeigen“ (`253_1b`) | 1 rot: v653::test_formular_und_liste |
| Nr. 1 – Auswahl im Formular | „Bauleiter“ statt „Bauleitung“ (`253_1e`, Klicktest Personen) | rot: plantafel_personen (Formular) |
| Nr. 1 – Liste „Bauleitung“ | „Plantafel“ auch für Bauleitung (`253_1c`) | 1 rot: v653::test_formular_und_liste |
| Nr. 1 – im Verlauf mit Namen | ohne Namen (`253_1d`) | 1 rot: v653::test_drei_werte |
| Nr. 2 – nicht gesetzt -> nicht zeigen | alle einplanbar (`253_2a`) | 2 rot: v653::test_migration_auf_einem_bestand_postgresql, v653::test_migration_auf_einem_bestand_sqlite |
| Nr. 2 – ohne Zeile die Vorgabe | immer einplanbar (`253_2b`) | 1 rot: v653::test_ohne_zeile_die_vorgabe_aus_gruppe_und_funktion |
| Nr. 2 – downgrade: Bauleitung stand in der Plantafel | Bauleitung -> nicht gesetzt (`253_2c`) | 2 rot: v653::test_migration_auf_einem_bestand_postgresql, v653::test_migration_auf_einem_bestand_sqlite |
| Nr. 3 – ohne Angabe unverändert | setzt einplanbar (`253_3a`) | 1 rot: v653::test_anlegen_ohne_angabe_ist_einplanbar_aendern_ohne_angabe_unveraendert |
| Nr. 3 – Anlegen ohne Angabe einplanbar | ohne Zeile (`253_3b`) | 1 rot: v653::test_anlegen_ohne_angabe_ist_einplanbar_aendern_ohne_angabe_unveraendert |
| Nr. 3 – das Formular schickt die Auswahl | immer einplanbar (`253_3c`, Klicktest Personen) | rot: plantafel_personen (Formular; Tafel) |
| Nr. 4 – Bauleitung geht vor der Kolonne | Bauleitung bei der Kolonne (`253_4a`) | 1 rot: v653::test_personen_nach_dem_kennzeichen |
| Nr. 4 – „Ohne Kolonne“ ohne Blick aufs Konto | Gruppe wieder nach dem Konto (`253_4b`) | 1 rot: v653::test_personen_nach_dem_kennzeichen |
| Nr. 4 – „Ohne Kolonne“ ohne Blick aufs Konto | Gruppe wieder nach dem Konto (`253_4c`, Klicktest Personen) | rot: plantafel_personen (Gruppen nach Kolonnen, Ohne Kolonne (Paul mit Konto), dann Bauleitung; jede Person einmal, Vera fehlt) |
| Nr. 5 – Bauleitung bleibt einplanbar | nur „einplanbar“ sichtbar (`253_5a`) | 1 rot: v653::test_nicht_zeigen_auch_nicht_im_einsatz_dialog |
| Nr. 6 – nicht zeigen fehlt in Tafel und Kapazität | sichtbar (`253_6a`) | 2 rot: v653::test_tafel_rechnet_wie_bisher_mit_planning_board, v653::test_tafel_schickt_das_kennzeichen_und_laesst_nicht_zeigen_weg |
| Nr. 6 – nicht zeigen fehlt in „Personen“ und unter „+ Person“ | sichtbar (`253_6c`, Klicktest Personen) | rot: plantafel_personen (Gruppen nach Kolonnen, Ohne Kolonne (Paul mit Konto), dann Bauleitung; jede Person einmal, Vera fehlt) |
| Nr. 6 – die Kolonne schlägt weiter vor | ohne „nicht zeigen“ (`253_6b`) | 1 rot: v653::test_nicht_zeigen_auch_nicht_im_einsatz_dialog |

Ohne eigene Gegenprobe: die Termine aus dem Kalender bei jeder Person mit Konto (Festlegung 1.9.250 Nr. 4, Gegenproben `250_4a`–`250_4e`, unverändert).
Kein Marker unter `app/` nach den Läufen.

## 1.9.254 (Punkt 2): Termin einer Person öffnet den Kalender

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – privat für andere „belegt“ | nie belegt (`254_1a`) | 1 rot: v654::test_belegt_nur_fuer_andere |
| Nr. 1 – privat für andere kein Knopf | nie belegt (`254_1e`, Klicktest Personen) | rot: plantafel_personen (Bea) |
| Nr. 1 – jeder andere Termin ein Knopf | kein Knopf (`254_1b`) | 1 rot: v654::test_knopf_und_ziel |
| Nr. 1 – „Belegt“ kein Knopf | jeder ein Knopf (`254_1c`, Klicktest Personen) | rot: plantafel_personen (Bea) |
| Nr. 1 – title „· im Kalender öffnen“ | ohne (`254_1d`) | 1 rot: v654::test_knopf_und_ziel |
| Nr. 2 – erster Tag des Termins | letzter Tag (`254_2a`) | 1 rot: v654::test_knopf_und_ziel |
| Nr. 2 – Serie in der Leseansicht | immer als Termin (`254_2b`) | 1 rot: v654::test_knopf_und_ziel |
| Nr. 2 – Serie in der Leseansicht | immer als Termin (`254_2c`, Klicktest Personen) | rot: plantafel_personen (Kalender) |
| Nr. 2 – Tagesansicht | ohne (`254_2g`, Klicktest Personen) | rot: plantafel_personen (Kalender; Kalender) |
| Nr. 2 – die gemerkte Ansicht bleibt | gemerkt (`254_2d`) | 1 rot: v654::test_kalender_liest_tag_und_termin |
| Nr. 2 – der Termin öffnet nach dem Laden | sofort (`254_2e`) | 1 rot: v654::test_kalender_liest_tag_und_termin |
| Nr. 2 – der Termin öffnet nach dem Laden | sofort (`254_2f`, Klicktest Personen) | rot: plantafel_personen (Kalender) |
| Nr. 3 – Tag nur als JJJJ-MM-TT | jeder Wert (`254_3a`) | 1 rot: v654::test_kalender_liest_tag_und_termin |

Ohne eigene Gegenprobe: `termin`/`serie` nur als Zahl -- derselbe Prüfausdruck wie der Tag, der statische Test liest beide; ein falscher Wert öffnet ohnehin
nichts (`openEdit()` findet keinen Termin). Kein Marker unter `app/` nach den Läufen.

## 1.9.255 (Punkt 5): Gerätezeilen nur mit Warnungen zum Gerät

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur die Konflikte des Geräts | Zeile des Geräts ohne Filter (`255_1a`) | 2 rot: v655::test_geraetezeile_mit_ihren_eigenen, v655::test_geraetezeile_ohne_konflikte_der_personen |
| Nr. 1 – nur die Konflikte des Geräts | dasselbe (`255_1b`, Klicktest Tafel) | rot: plantafel_tafel (Balken; Filter) |
| Nr. 1 – je Gerät seine Zeile | Zeile ohne die ID des Geräts (`255_1c`, Klicktest Tafel) | rot: plantafel_tafel (Balken; Filter) |
| Nr. 2 – Gerät doppelt nennt das Gerät | ohne (`255_2a`) | 1 rot: v655::test_geraet_doppelt_und_person_doppelt_nennen_wen |
| Nr. 2 – Prüffrist nennt das Gerät | ohne (`255_2b`) | 1 rot: v655::test_pruefung_nennt_das_geraet |
| Nr. 2 – Prüffrist nennt das Gerät | ohne (`255_2c`, Klicktest Personen) | rot: plantafel_personen (Geräte) |
| Nr. 3 – Termin im Postfach warnt auf der Tafel | nur beim Speichern (`255_3a`) | 2 rot: v579::test_die_tafel_zeigt_ihn_als_warnung_am_geraet, v655::test_termin_im_postfach_warnt_auf_der_tafel |
| Nr. 3 – Termin im Postfach warnt auf der Tafel | nur beim Speichern (`255_3e`, Klicktest Personen) | rot: plantafel_personen (Geräte; Kolonnen) |
| Nr. 3 – an den Tagen des Geräts | an allen Arbeitstagen des Einsatzes (`255_3b`) | 1 rot: v655::test_termin_im_postfach_warnt_auf_der_tafel |
| Nr. 3 – nicht bei geschlossenen Aufträgen | auch dann (`255_3c`) | 1 rot: v655::test_termin_eines_geschlossenen_auftrags_warnt_nicht |
| Nr. 3 – mit dem Gerät | ohne (`255_3d`) | 2 rot: v579::test_die_tafel_zeigt_ihn_als_warnung_am_geraet, v655::test_termin_im_postfach_warnt_auf_der_tafel |

Ohne eigene Gegenprobe: „zählt im Knopf Warnungen“ -- `tafel_zaehler()` zählt jede Warnung der Einsätze (Gegenproben 1.9.247 Nr. 2), der Test prüft den
Zähler mit. Kein Marker unter `app/` nach den Läufen.
