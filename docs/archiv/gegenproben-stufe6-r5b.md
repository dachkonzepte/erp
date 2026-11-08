# Gegenproben der Runde Stufe 6, R5b (ab 1.9.265)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R5a (`docs/archiv/gegenproben-stufe6-r5a.md`): in
einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript) mit dem Marker `GEGENPROBE` ändern, die genannten Tests laufen
lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler).

## 1.9.265 (Punkt 0a): Mitarbeiterliste ohne die Prüfung des Formulars

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – die Antwort prüft nicht wie das Formular | `EmployeeOut` wieder von `EmployeeCreate` (`265_1a`) | 3 rot: v665::test_antwort_ohne_pruefung_mit_allen_feldern, v665::test_beim_speichern_bleibt_die_pruefung, v665::test_liste_und_einzeln_mit_einem_mitarbeiter_ohne_stundenlohn |
| Nr. 1 – ohne Grenzen | Felder mit ihren Grenzen übernommen (`265_1b`) | 1 rot: v665::test_antwort_ohne_pruefung_mit_allen_feldern |
| Nr. 2 – geprüft wird beim Speichern | Prüfung des Formulars aus, an beiden Stellen (`265_2a`) | 1 rot: v665::test_beim_speichern_bleibt_die_pruefung |

Ohne eigene Gegenprobe: Nr. 3 (nichts geändert). `265_2a` blieb im ersten Lauf grün: sie schaltete nur die Prüfung im Schema ab, das Speichern prüft
denselben Stundenlohn aber ein zweites Mal in `app/employees.py::apply_employee_payload()`. Der Test war richtig, die Gegenprobe unvollständig -- sie schaltet
jetzt beide Stellen ab (das Werkzeug kann seit dieser Runde mehrere Stellen in einer Gegenprobe ändern) und ist rot.

## 1.9.266 (Punkt 0b): „niemand“ meldet keine Kapazität

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – „niemand“ meldet keine Kapazität | wie bis 1.9.265 (`266_1a`) | 3 rot: v663::test_ganz_leer_mit_stunden_meldet_keine_kapazitaet, v666::test_niemand_auf_der_tafel_und_im_zaehler, v666::test_niemand_beim_speichern_und_in_der_pruefung |
| Nr. 1 – auf der Tafel | wie bis 1.9.265 (`266_1b`, Klicktest Tage) | rot: plantafel_tage (Leer) |
| Nr. 2 – mit jemandem, auch nur einem Gerät, wie bisher | nur mit Personen (`266_2a`) | 1 rot: v666::test_mit_jemandem_meldet_es_weiter |

## 1.9.267 (Punkt 1): Tag setzen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – genau eine | eine oder mehrere (`267_1a`) | 1 rot: v667::test_api |
| Nr. 1 – prüfen schreibt nichts | commit statt rollback (`267_1b`) | 3 rot: v667::test_api, v667::test_pruefen_schreibt_nichts, v667::test_zwei_einsaetze_am_tag_karte_und_vorschlag |
| Nr. 2 – dazu, wenn der Auftrag an dem Tag einen Einsatz hat | nie dazu (`267_2a`) | 7 rot: v667::test_abwesend_fragt_antrag_nicht, v667::test_api, v667::test_dazu_nur_an_diesem_tag, v667::test_geraet_setzen, v667::test_kranvermietung_antwort_8, v667::test_was_vorher_schon_da_war_fragt_nicht, v667::test_zwei_einsaetze_am_tag_karte_und_vorschlag |
| Nr. 2 – Person oder Gerät: der ohne Kolonne zuerst | nur der früheste (`267_2b`) | 1 rot: v667::test_zwei_einsaetze_am_tag_karte_und_vorschlag |
| Nr. 3 – verlängert Fr -> Mo | nur der nächste Kalendertag (`267_2c`) | 1 rot: v667::test_verlaengert_ueber_das_wochenende_mit_der_falle |
| Nr. 3 – der vordere zuerst | der hintere zuerst (`267_2d`) | 1 rot: v667::test_verlaengert_nach_vorn_und_der_vordere_zuerst |
| Nr. 4 – auf der Karte dieser Einsatz | Karte übergangen (`267_3a`) | 1 rot: v667::test_zwei_einsaetze_am_tag_karte_und_vorschlag |
| Nr. 4 – Karte eines anderen Auftrags 404 | nur unbekannt (`267_3b`) | 1 rot: v667::test_api |
| Nr. 4 – Karte an dem Tag, sonst 422 | ohne Prüfung (`267_3c`) | 1 rot: v667::test_api |
| Nr. 4 – Kolonne auf anderer Kolonne: ein eigener | in die Karte (`267_3d`) | 1 rot: v667::test_zwei_einsaetze_am_tag_karte_und_vorschlag |
| Nr. 5 – neu vorläufig | fest (`267_4a`) | 1 rot: v667::test_neu_ohne_anschluss |
| Nr. 5 – Art des letzten Einsatzes | immer Baustelle (`267_4b`) | 1 rot: v667::test_kranvermietung_antwort_8 |
| Nr. 5 – mit Kolonne nur, wenn eine gezogen wurde | Kolonne des letzten Einsatzes (`267_4c`) | 1 rot: v667::test_neu_ohne_anschluss |
| Nr. 5 – Stunden = Rest | 0 Stunden (`267_4d`) | 1 rot: v667::test_neu_ohne_anschluss |
| Nr. 6 – Kolonne nie auf eine Kran-Karte | ohne die Prüfung der Karte (`267_5a`) | 1 rot: v667::test_kranvermietung_antwort_8 |
| Nr. 6 – Kolonne nie an einen Kran-Auftrag | ohne (`267_5b`) | 1 rot: v667::test_kranvermietung_antwort_8 |
| Nr. 6 – Person nur dazu | auch verlängern und neu (`267_5c`) | 1 rot: v667::test_kranvermietung_antwort_8 |
| Nr. 6 – ein Gerät darf | auch das Gerät nur dazu (`267_5d`) | 1 rot: v667::test_kranvermietung_antwort_8 |
| Nr. 7 – die Falle | alle_tage_mitnehmen=True (`267_6a`) | 2 rot: v667::test_verlaengert_nach_vorn_und_der_vordere_zuerst, v667::test_verlaengert_ueber_das_wochenende_mit_der_falle |
| Nr. 7 – auch Geräte | Geräte nicht festgeschrieben (`267_6b`) | 1 rot: v667::test_verlaengert_ueber_das_wochenende_mit_der_falle |
| Nr. 8 – nur der Tag der Genannten | alle Tage (`267_7a`) | 5 rot: v667::test_api, v667::test_dazu_nur_an_diesem_tag, v667::test_geraet_setzen, v667::test_verlaengert_nach_vorn_und_der_vordere_zuerst, v667::test_verlaengert_ueber_das_wochenende_mit_der_falle |
| Nr. 8 – Normalform | ohne (`267_7b`) | 2 rot: v667::test_dazu_nur_an_diesem_tag, v667::test_kolonne_ohne_nicht_zeigen |
| Nr. 9 – ohne „nicht zeigen“ | alle Mitglieder (`267_8a`) | 1 rot: v667::test_kolonne_ohne_nicht_zeigen |
| Nr. 9 – ohne Vorschlag 422 | ein leerer Einsatz (`267_8b`) | 1 rot: v667::test_kolonne_ohne_vorschlag |
| Nr. 10 – nur neue Warnungen | jede Warnung (`267_9a`) | 1 rot: v667::test_was_vorher_schon_da_war_fragt_nicht |
| Nr. 10 – ein neuer Tag fragt | Tage nicht verglichen (`267_9b`) | 1 rot: v667::test_was_vorher_schon_da_war_fragt_nicht |
| Nr. 10 – neue Warnung fragt | fragt nie (`267_9c`) | 5 rot: v667::test_abwesend_fragt_antrag_nicht, v667::test_api, v667::test_ganze_kolonne_eine_rueckfrage, v667::test_neue_warnung_fragt_nichts_gespeichert, v667::test_was_vorher_schon_da_war_fragt_nicht |
| Nr. 10 – Hinweise nie | auch Hinweise (`267_9d`) | 2 rot: v667::test_abwesend_fragt_antrag_nicht, v667::test_kranvermietung_antwort_8 |
| Nr. 10 – eine Rückfrage für alle | nur die erste Warnung (`267_9e`) | 1 rot: v667::test_ganze_kolonne_eine_rueckfrage |
| Nr. 11 – geschlossen 409, auch dazu | ohne (`267_10a`) | 1 rot: v667::test_geschlossener_auftrag |

Ohne eigene Gegenprobe: „nie zusammengelegt“ (Nr. 3) -- kein Weg legt zusammen, `test_verlaengert_nach_vorn_und_der_vordere_zuerst` hält den Zeitraum des
hinteren fest; Nr. 12 (Sperren, Rolle, Zugehörigkeit, Event-Loop) mit Punkt 3.

Erst im zweiten Anlauf rot: `267_8a` blieb grün -- der Test legte die Kolonne nur neu an, dort schlägt `_create_slot()` selbst vor, `_eintraege()` lief nicht; der
Test verlängert jetzt zusätzlich. `267_9b` blieb grün -- der neue Tag kam an einem anderen Einsatz dazu, die Warnung war schon dadurch neu; der Test nimmt jetzt
denselben Einsatz, an dem Kai schon doppelt war. Danach alle 30 Gegenproben und die Suite neu, alle rot bzw. grün.

## 1.9.268 (Punkt 2): Umsetzen, Herausnehmen, Verlängern

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1, 6 – nur ihre Tage | nur „steht am Einsatz“ (`268_1b`) | 1 rot: v668::test_herausnehmen_geraet_und_fehler |
| Nr. 1 – eine Transaktion | Commit nach dem Setzen (`268_1c`) | 3 rot: v668::test_neue_warnung_am_ziel_fragt, v668::test_pruefen_schreibt_nichts, v668::test_quelle_wird_leer_fragt |
| Nr. 2 – gleich viele Kalendertage | nur der erste Tag (`268_2a`) | 1 rot: v668::test_umsetzen_mehrerer_tage_ueberlappend_mit_der_falle |
| Nr. 2 – im selben Einsatz bleiben ihre Tage | alle alten Tage heraus (`268_2b`) | 1 rot: v668::test_umsetzen_mehrerer_tage_ueberlappend_mit_der_falle |
| Nr. 3 – der alte Platz fragt nicht | geprüft vor dem Herausnehmen (`268_3a`) | 5 rot: v668::test_api, v668::test_geraet_umsetzen, v668::test_quelle_wird_leer_fragt, v668::test_umsetzen_auf_eine_karte, v668::test_umsetzen_auf_einen_anderen_auftrag_fragt_nicht_nach_dem_alten_platz |
| Nr. 3 – neue Warnung am Ziel fragt | fragt nie (`268_3b`) | 1 rot: v668::test_neue_warnung_am_ziel_fragt |
| Nr. 4 – weniger Tage sind nicht neu | andere Tage gelten als neu (`268_3c`) | 1 rot: v668::test_weniger_tage_einer_warnung_sind_nicht_neu |
| Nr. 5 – Rückfrage „niemand mehr“ | immer behalten (`268_4a`) | 3 rot: v668::test_api, v668::test_herausnehmen_alle_und_leer, v668::test_quelle_wird_leer_fragt |
| Nr. 5 – im selben Einsatz nie | erst herausnehmen, dann setzen (`268_4b`) | 5 rot: v668::test_allein_im_einsatz_wandert_der_einsatz, v668::test_neue_warnung_am_ziel_fragt, v668::test_pruefen_schreibt_nichts, v668::test_quelle_wird_leer_fragt, v668::test_umsetzen_auf_eine_karte |
| Nr. 6 – Tage oder alle | ohne die Prüfung (`268_5a`) | 1 rot: v668::test_herausnehmen_geraet_und_fehler |
| Nr. 6 – am Rand kürzt der Einsatz | ohne Kürzen (`268_5b`) | 2 rot: v668::test_allein_im_einsatz_wandert_der_einsatz, v668::test_herausnehmen_in_der_mitte_luecke_am_rand_kuerzen |
| Nr. 6 – fragt nie | fragt bei neuen Warnungen (`268_5c`) | 1 rot: v668::test_herausnehmen_fragt_nie |
| Nr. 7 – bis zum letzten Tag | nur ein Tag (`268_6a`) | 3 rot: v668::test_api, v668::test_verlaengern_bis_zum_letzten_tag, v668::test_verlaengern_prueft_wie_planen |
| Nr. 7 – ab dem letzten Tag 422 | ohne (`268_6b`) | 1 rot: v668::test_verlaengern_bis_zum_letzten_tag |
| Nr. 7 – prüft wie Planen | fragt nie (`268_6c`) | 2 rot: v668::test_api, v668::test_verlaengern_prueft_wie_planen |
| Nr. 8 – der Einsatz, aus dem sie kam | ohne (`268_7a`) | 1 rot: v668::test_api |
| Nr. 8 – geprüft „leer“ | nie leer (`268_7b`) | 1 rot: v668::test_quelle_wird_leer_fragt |
| Nr. 8 – Prüfen schreibt nichts | Commit statt rollback (`268_7c`) | 3 rot: v668::test_pruefen_schreibt_nichts, v668::test_quelle_wird_leer_fragt, v668::test_umsetzen_auf_eine_karte |

Ohne eigene Gegenprobe: „keine Kolonne“ (Nr. 1) -- die Schemas kennen kein `team_id`, ein mitgeschicktes Feld fällt weg und die Anfrage ist ohne Person und
Gerät 422 (`test_api`); Nr. 9 mit Punkt 3.

## 1.9.269 (Punkt 3): Sperren, Zugehörigkeit, Rolle, Teil-Update, Event-Loop, Rückgängig

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – aufsteigend gesperrt | in der Reihenfolge der Anfrage (`269_1a`) | 2 rot: v669::test_postgresql_umsetzen_ueber_kreuz_ohne_deadlock, v669::test_sperren_aufsteigend |
| Nr. 2 – ab Büro – Auftrag | Umsetzen auch für die Monteurin (`269_2a`) | 1 rot: v669::test_rolle_ab_buero_auftrag |
| Nr. 3 – Einsatz unbekannt 404 | ohne Prüfung (`269_3a`) | 2 rot: v668::test_api, v669::test_rueckgaengig_schritte_pruefen |
| Nr. 3 – nur an ihren Tagen | eine fremde Zeile übergangen (`269_3b`) | 2 rot: v669::test_rueckgaengig_in_einer_transaktion_und_fragt_nie, v669::test_rueckgaengig_schritte_pruefen |
| Nr. 4 – def | Rückgängig async (`269_4a`) | 1 rot: v669::test_endpunkte_ohne_event_loop |
| Nr. 4 – scope="function" | Verlängern ohne (`269_4b`) | 1 rot: v669::test_endpunkte_ohne_event_loop |
| Nr. 5 – nur die Zeilen der Genannten | Tag setzen leert die Notiz (`269_5a`) | 1 rot: v669::test_teil_update_nur_die_genannten |
| Nr. 5 – PUT kennt dazu/weg nicht | im Schema (`269_5c`) | 1 rot: v669::test_teil_update_nur_die_genannten |
| Nr. 6 – eine Transaktion | Commit nach jedem Schritt (`269_6a`) | 1 rot: v669::test_rueckgaengig_in_einer_transaktion_und_fragt_nie |
| Nr. 6 – fragt nie | fragt bei Warnungen (`269_6b`) | 1 rot: v669::test_rueckgaengig_in_einer_transaktion_und_fragt_nie |
| Nr. 7 – nur unverändert | ohne Vergleich (`269_7a`) | 1 rot: v669::test_rueckgaengig_neu_nur_unveraendert |
| Nr. 7 – der Stand mit der Notiz | Notiz nicht im Stand (`269_7b`) | 1 rot: v669::test_rueckgaengig_neu_nur_unveraendert |
| Nr. 8 – gelöscht: kein Rückgängig (Herausnehmen) | trotzdem (`269_8a`) | 1 rot: v669::test_rueckgaengig_herausnehmen_und_verlaengern |
| Nr. 8 – gelöscht: kein Rückgängig (Umsetzen) | trotzdem (`269_8b`) | 1 rot: v669::test_rueckgaengig_nach_umsetzen_mit_geloeschter_quelle |
| Nr. 8 – nichts geändert: kein Rückgängig | eine leere Umkehrung (`269_8c`) | 1 rot: v669::test_rueckgaengig_dazu_und_verlaengert |

Ohne eigene Gegenprobe: Nr. 9 (beschreibt, was bleibt; nichts daran geändert). „Erst zurück, dann am Ziel heraus“ (Umsetzung) ist keine Festlegung -- das Ergebnis
ist in beiden Reihenfolgen dasselbe, nur ohne leeren Zwischenstand.
