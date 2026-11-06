# Gegenproben der Runde Stufe 6, R3b (ab 1.9.238)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R3a (`docs/archiv/gegenproben-stufe6-r3a.md`): in
einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Migration, Skript) mit dem Marker `GEGENPROBE` ändern, die genannten
Tests laufen lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an (FAILED, kein Sammelfehler).

## 1.9.238 (Punkt 0a): Beleg der Eingangsrechnung hochladen und entfernen unter der Sperre

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – Hochladen und Entfernen sperren die Zeile | `db.get` statt `with_for_update` (`238_1a`) | 2 rot: v638 (Hochladen und Entfernen während des Löschens) |
| Nr. 1 – keine Datei bleibt liegen | gelöschte Rechnung: neue Datei nicht entfernt (`238_1b`) | 1 rot: v638::test_pg_hochladen_waehrend_des_loeschens_404_und_keine_datei |
| Nr. 2 – Antwort vor dem Commit | Antwort nach dem Commit (`238_2`) | 3 rot: v638 (Hochladen dann Löschen; die beiden Fehlerfälle, weil die Antwort dann erst nach dem Commit scheitert) |
| Nr. 3 – alter Beleg erst nach dem Commit | alter Beleg vor dem Speichern gelöscht (`238_3a`) | 1 rot: v638::test_scheitert_das_hochladen_bleibt_der_alte_beleg |
| Nr. 3 – scheitert es, fällt der neue weg | neue Datei beim Scheitern nicht entfernt (`238_3b`) | 1 rot: dito |
| Nr. 3 – Entfernen: Datei erst nach dem Commit | Datei vor dem Speichern gelöscht (`238_3c`) | 1 rot: v638::test_scheitert_das_entfernen_bleibt_der_beleg |

Ohne eigene Gegenprobe: die Prüfung „gibt es die Rechnung?“ vor dem Ablegen ist nur eine Abkürzung (keine Datei für eine unbekannte ID); dasselbe
Ergebnis sichert `238_1b`. Kein Marker unter `app/` nach den Läufen.

## 1.9.239 (Punkt 0b): Lohndatei statt LODAS in den Einstellungen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – der Hinweis nennt die Lohndatei | alter Text zurück in `settings.html` (`239_1a`) | 2 rot: v639 (Hinweis, keine Vorlage) |
| Nr. 1 – keine Vorlage nennt LODAS | „LODAS“ in einem Kommentar einer anderen Vorlage (`239_1b`) | 1 rot: v639::test_keine_vorlage_nennt_lodas |

Ohne Gegenprobe: der Stand des Steuerbüros und die Bestätigungen (reine Doku); 0c (nur lokal, kein Code).

## 1.9.240 (Punkte 1 und 2): Kranvermietung als Art des Einsatzes

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ohne Angabe Baustelle (Geschäftsfunktion) | Vorgabe „kranvermietung“ in `create_slot()` (`240_1a`) | 1 rot: v640::test_geschaeftsfunktion_prueft_selbst |
| Nr. 1 – ohne Angabe Baustelle (Schema) | Vorgabe „kranvermietung“ im Schema (`240_1c`) | 3 rot: v640 (Baustelle braucht Auftrag, Baustelle ohne Kolonne, Warnung) |
| Nr. 1 – jeder andere Wert 422 | Prüfung der Art weg (`240_1b`) | 1 rot: v640::test_geschaeftsfunktion_prueft_selbst |
| Nr. 2 – Position „Kranvermietung nach Aufwand“ | Text „Kranvermietung“ (`240_2a`) | 1 rot: v640::test_mit_kunde_… |
| Nr. 2 – Titel wahlweise | Titel immer „Kranvermietung“ (`240_2b`) | 1 rot: v640::test_mit_titel_und_bediener |
| Nr. 2 – Ausführungsbeginn der erste Tag | ohne Ausführungsbeginn (`240_2c`) | 1 rot: v640::test_mit_kunde_… |
| Nr. 2 – fremdes Objekt nur mit Bestätigung | immer bestätigt (`240_2d`) | 1 rot: v640::test_unbekannter_kunde_und_fremdes_objekt |
| Nr. 2 – 409 und 404 vom Router | Fänger für Objekt und Kunde weg (`240_11`) | 1 rot: dito |
| Nr. 3 – in der Transaktion des Einsatzes | Projekt und Auftrag mit Commit (`240_3`) | 2 rot: v640 (Warnung, Ablehnung lassen nichts zurück) |
| Nr. 4 – Auftrag oder Kunde, nicht beides | Prüfung nur „keins“ (`240_4`) | 1 rot: v640::test_geschaeftsfunktion_prueft_selbst |
| Nr. 5 – keine Kolonne beim Anlegen | Prüfung weg (`240_5a`) | 1 rot: v640::test_geschaeftsfunktion_prueft_selbst |
| Nr. 5 – keine Kolonne beim Ändern | Prüfung weg (`240_5b`) | Runde 1 **grün** (die Kolonne ohne Gerät nahm den Kran weg -- „mindestens ein Gerät“ lehnte ab) -> Test mit dem Kran in derselben Anfrage; Runde 2: rot, v640::test_aendern_einer_kranvermietung |
| Nr. 5 – mindestens ein Gerät beim Anlegen | Prüfung weg (`240_5c`) | 1 rot: v640::test_geschaeftsfunktion_prueft_selbst |
| Nr. 5 – mindestens ein Gerät beim Ändern | Prüfung weg (`240_5d`) | 1 rot: v640::test_aendern_einer_kranvermietung |
| Nr. 5 – Bediener auch keine (Ändern) | „ohne Kolonne mindestens eine Person“ auch für die Kranvermietung (`240_5e`) | 1 rot: dito |
| Nr. 5 – Bediener auch keine (Anlegen) | dito beim Anlegen (`240_5f`) | 5 rot: v640 |
| Nr. 6 – Baustelle braucht einen Auftrag (Geschäftsfunktion) | Prüfung weg (`240_6a`) | 1 rot: v640::test_geschaeftsfunktion_prueft_selbst |
| Nr. 6 – Kunde, Objekt, Titel nur zur Kranvermietung (Schema) | Prüfung nur „ohne Auftrag“ (`240_6b`) | 1 rot: v640::test_schema_fuer_sich |
| Nr. 7 – keine Beträge | Position 1,00 € (`240_7`) | 1 rot: v640::test_mit_kunde_… |
| Nr. 8 – Anlegen nimmt bei Ablehnung zurück | ohne rollback (`240_8a`) | 1 rot: v640::test_abgelehnt_bleibt_nichts |
| Nr. 8 – Ändern nimmt bei Ablehnung zurück | ohne rollback (`240_8b`) | 1 rot: v640::test_aendern_einer_kranvermietung |
| Nr. 9 – nicht am Modul „Wartungen“ | Modul geprüft (`240_10`) | 1 rot: v640::test_nicht_an_das_modul_wartungen_gebunden |
| Nr. 10 – Migration: bestehende sind Baustelle | `server_default` „kranvermietung“ (`240_9`) | 2 rot: v640 Migration SQLite und PostgreSQL |

Kein Marker unter `app/` nach den Läufen; jede rote nennt einen gescheiterten Test, keinen Sammelfehler.

## 1.9.241 (Punkt 3): Plantafel -> Kran-Kalender

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – je Folge von Tagen ein Termin | jeder Tag ein eigener Termin (`241_1a`) | 11 rot: v641 |
| Nr. 1 – nur aktive Geräte | auch inaktive (`241_1b`) | 1 rot: v641::test_ohne_postfach_oder_inaktiv_kein_termin |
| Nr. 1 – ganztägig | nicht ganztägig (`241_1c`) | 6 rot: v641 |
| Nr. 2 – „vorläufig:“ im Titel | ohne (`241_10`) | 3 rot: v641 |
| Nr. 3 – Anlegen gleicht ab | kein Abgleich beim Anlegen (`241_2a`) | 11 rot: v641 |
| Nr. 3 – Ändern verschiebt denselben Termin | löschen und neu anlegen (`241_2b`) | 1 rot: v641::test_aendern_verschiebt_den_termin |
| Nr. 3 – Löschen nimmt ihn heraus | ohne `entfernen()` (`241_2c`) | 1 rot: v641::test_loeschen_nimmt_den_termin_aus_outlook |
| Nr. 3 – geht sofort hinaus | nichts gesendet (`241_2d`) | 9 rot: v641 |
| Nr. 4 – geschlossener Auftrag ohne Termine | `geschlossen()` übergangen (`241_3a`) | 1 rot: v641::test_geschlossener_auftrag_hat_keinen_termin |
| Nr. 4 – der Statuswechsel gleicht ab | ohne `auftrag_abgleichen()` (`241_3b`) | 1 rot: dito |
| Nr. 5 – Änderung in Outlook überschrieben | Änderung übernommen (`241_4a`) | 1 rot: v641::test_in_outlook_geaendert_ueberschreibt_der_abgleich |
| Nr. 5 – in Outlook gelöscht -> neu | im ERP gelöscht (`241_4b`) | Runde 1 rot **aus dem falschen Grund** (mein Marker als Kommentar schnitt den Rest der Zeile ab: Sammelfehler); Runde 2 (Marker als Zeichenkette): rot, v641::test_in_outlook_geloescht_legt_der_abgleich_neu_an |
| Nr. 5 – auch beim Abruf des ganzen Kalenders | 404 löscht (`241_4c`) | 1 rot: v641::test_ganzer_kalender_ohne_den_termin_legt_ihn_neu_an |
| Nr. 6 – Büro-Kalender 409 | Prüfung weg (`241_5`) | 1 rot: v641::test_buero_kalender_aendert_ihn_nicht |
| Nr. 7 – eigener Termin keine Belegung | Termine der Einsätze mitgezählt (`241_6`) | 4 rot: v641 |
| Nr. 8 – der Termin wird der Termin des Einsatzes | nicht verknüpft (`241_7a`) | 3 rot: v641 |
| Nr. 8 – Notiz außer privat | auch privat (`241_7b`) | 1 rot: v641::test_uebernehmen_ablehnungen |
| Nr. 8 – nicht schon übernommen | Prüfung weg (`241_7c`) | Runde 1 **grün** (der zweite Versuch scheiterte an der Warnung „Gerät doppelt“, nicht an der Regel) -> Test mit „trotzdem planen“ und Meldungstext; Runde 2: rot, v641::test_termin_aus_outlook_als_kranvermietung_uebernehmen |
| Nr. 8 – bis zum Tag vor einem Ende um Mitternacht | Tag des Endes (`241_7d`) | 1 rot: v641::test_uebernehmen_bis_mitternacht_ist_ein_tag |
| Nr. 9 – Abgleich zieht nach | ohne `nachziehen()` (`241_8a`) | 1 rot: v641::test_postfach_nach_der_planung_zieht_der_abgleich_nach |
| Nr. 9 – nur heute oder später endende | auch vergangene (`241_8b`) | Runde 1 rot **aus dem falschen Grund** (dito, Kommentar schnitt die Zeile ab); Runde 2: rot, dito |
| Nr. 10 – nach der Planung inaktiv: Termin fällt weg | siehe `241_1b` | dito |
| Nr. 11 – downgrade löscht die Termine der Einsätze | ohne DELETE (`241_9`) | 2 rot: v641 Migration SQLite und PostgreSQL |

Kein Marker unter `app/` nach den Läufen. Nach `241_4b`/`241_8b` alle Läufe geprüft: jede andere rote nennt einen gescheiterten Test.

## 1.9.242 (Punkt 4): „Heute“ nach heute-einsatz.html

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – vorläufig, wenn einer vorläufig ist | immer „fest“ (`242_1`) | 1 rot: v642::test_geraet_an_einzelnen_tagen |
| Nr. 2 – „Mit dir“ ohne die Abwesenden | Abwesende auch unter „Mit dir“ (`242_2a`) | 1 rot: v642::test_wer_fehlt_ist_nicht_da_nie_die_art |
| Nr. 2 – nie mit der Art | Art hinter dem Namen (`242_2b`) | 2 rot: v642 (wer fehlt, eigene Abwesenheit) |
| Nr. 2 – ohne sie selbst | sie selbst mitgezählt (`242_2c`) | 2 rot: v642 (Karte, wer fehlt) |
| Nr. 3 – Geräte nur an ihren Tagen | an jedem Tag des Einsatzes (`242_3a`) | 1 rot: v642::test_geraet_an_einzelnen_tagen |
| Nr. 3 – „nur heute“ / „auch …“ | ohne Zusatz (`242_3b`) | 2 rot: v642 (Gerät an einzelnen Tagen, Karte) |
| Nr. 4 – Notiz des Einsatzes | ohne Notiz (`242_4a`) | 1 rot: v642::test_karte_mit_besetzung_geraeten_notiz_baustelle |
| Nr. 4 – Baustellenhinweise der AV | ohne (`242_4b`) | 1 rot: dito |
| Nr. 5 – nur an Arbeitstagen | Wochenende und Feiertag zählen (`242_5a`) | 4 rot: v471 (Nächste Tage), v642 (kein Arbeitstag, Nächste Tage, `Tage`) |
| Nr. 5 – nicht bei eigener Abwesenheit | Abwesenheit übergangen (`242_5b`) | 1 rot: v642::test_eigene_abwesenheit_keine_karte |
| Nr. 5 – „Heute“ sagt, warum | kein Grund „kein Arbeitstag“ (`242_5c`) | 1 rot: v642::test_kein_arbeitstag_keine_karte |
| Nr. 6 – Zusatz „weiter“ | nie „weiter“ (`242_6a`) | 3 rot: v471 (zwei), v642 (Nächste Tage) |
| Nr. 6 – „weiter“ nur ab morgen | auch für heute (`242_6b`) | 1 rot: v471::test_offene_zeit_von_frueher_zeigt_heute_als_eigene_zeile |
| Nr. 6 – Zusatz „vorläufig“ | ohne (`242_6c`) | 3 rot: v471 (zwei), v642 (Nächste Tage) |
| Nr. 6 – je Auftrag und Zusatz eine Folge | je Tag eine Zeile (`242_6d`) | 11 rot: v471 (fünf), v642 (sechs) |
| Nr. 7 – eigene genehmigte Abwesenheit als Zeile | ohne (`242_7a`) | 1 rot: v642::test_naechste_tage_je_einsatz_ohne_wochenende_mit_urlaub |
| Nr. 7 – eigener offener Antrag als Zeile | ohne (`242_7b`) | 1 rot: dito |
| Nr. 8 – Schlüssel `angaben` | Schlüssel „einsatz“ (`242_8`) | 7 rot: v326 (Datengrenze, drei), v642 (vier) |
| Nr. 2 (Seite) – „ist nicht da“ | Seite schreibt „hat Urlaub“ (`242_9a`) | 1 rot: v642::test_seite_zeichnet_die_angaben (nach der Änderung an `angabeZeile()` noch einmal: rot) |
| Regel 32 (Seite) – Namen über esc() | „Mit dir“ ohne esc() (`242_9b`) | Runde 1 rot **aus dem falschen Grund**: v407 war schon ohne Gegenprobe rot (die Zeile baute eine verschachtelte Funktion `zeile()`, deren Aufrufstellen der Scanner nicht verfolgt -- Fund der vollen Suite) -> `angabeZeile()` auf der obersten Ebene der Seite, v407 ohne Gegenprobe grün; Runde 2: rot, v407::test_kein_wert_ohne_esc_im_html |
| Werkzeug Nr. 1 – pytest-Uhr am nächsten Arbeitstag | heute ohne Verschieben (`242_W1a`) | 1 rot: v642::test_feste_uhr_beginnt_an_einem_arbeitstag |
| Werkzeug Nr. 1 – Klicktest-Uhr am nächsten Arbeitstag | dito in `cdp_klicktest._arbeitstag_ab()` (`242_W1b`) | 1 rot: v642::test_klicktest_uhr_beginnt_an_einem_arbeitstag |

Ohne eigene Gegenprobe: Werkzeug Nr. 2 (`--wanduhr` mit Datum, `ERP_KLICKTEST_HEUTE`) ist das Mittel der Gegenproben `W1a`/`W1b` und der Samstags-Probe
(Bericht), keine Regel im Betrieb. Alle roten nennen einen gescheiterten Test, keinen Sammelfehler; jede Datei byte-genau zurück, kein Marker unter
`app/`.
