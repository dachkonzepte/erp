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
