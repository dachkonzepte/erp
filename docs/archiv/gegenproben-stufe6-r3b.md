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
