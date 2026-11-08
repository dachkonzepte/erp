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
