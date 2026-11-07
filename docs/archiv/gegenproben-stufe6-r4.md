# Gegenproben der Runde Stufe 6, R4 (ab 1.9.243)

Regel 24: jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, je Aussage. Ablauf wie in R3a und R3b
(`docs/archiv/gegenproben-stufe6-r3a.md`, `-r3b.md`): in einer eigenen Arbeitskopie auf dem Stand der Version die Stelle in `app/` (bzw. Vorlage, Skript)
mit dem Marker `GEGENPROBE` ändern, die genannten Tests laufen lassen, die Datei byte-genau zurück (Prüfsumme). „rot“ = mindestens ein Test schlägt an
(FAILED, kein Sammelfehler).

## 1.9.243 (Punkt 0a): „Nächste Tage“ ohne Abwesende im „mit …“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – wer abwesend ist, fehlt | alle der Besetzung im „mit …“ (`243_1a`) | 3 rot: v643 (abwesend an einem Tag, alle weg, Freistellung) |
| Nr. 1 – auch die Freistellung | nur gespeicherte Abwesenheiten, ohne Arbeitszeitkalender (`243_1b`) | 1 rot: v643::test_freistellung_des_arbeitszeitkalenders_fehlt_wie_abwesend |
| Nr. 2 – offener Antrag zählt nicht | offene Anträge als abwesend (`243_2`) | 1 rot: v643::test_offener_antrag_zaehlt_nicht |
| Nr. 3 – je Tag, die Zeile teilt sich | abwesend nur am ersten Tag des Einsatzes gelesen (`243_3`) | 3 rot: v643 (abwesend an einem Tag, alle weg, Freistellung) |
| Nr. 4 – „weiter“ teilt sich nicht | „weiter ohne“, wenn jemand fehlt (`243_4`) | 1 rot: v643::test_weiter_bleibt_weiter |

Kein Marker unter `app/` nach den Läufen.

## 1.9.244 (Punkt 0b): Tests und Doku ohne echte Personalnummern

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – keine echte Nummer in einer versionierten Datei | eine echte Nummer zurück in `tests/test_v626_lohndatei.py` (`244_1`) | 1 rot: v644::test_keine_echte_personalnummer_in_einer_versionierten_datei |
| Nr. 1 – auch das LIESMICH zählt | LIESMICH nicht gelesen (`244_1b`) | 1 rot: v644::test_echte_nummern_aus_den_dateien |
| Nr. 2 – nie die Nummer, nur Datei, Zeile, Kennung | Fundstelle mit der Nummer statt der Kennung (`244_2`) | 1 rot: v644::test_fundstellen_nennen_nie_die_nummer |

Ohne Gegenprobe: Nr. 2 „nur lokal“ (ohne den Ordner übersprungen -- das zeigt der Lauf auf einem Rechner ohne `lohn_echt`), Nr. 3 (Arbeitsweise), 0e
(reine Doku). Kein Marker unter `app/` nach den Läufen.

## 1.9.245 (Punkt 0c): Schnellauftrag in einer Transaktion

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ein Commit | `auftrag_nach_aufwand()` wieder mit Commit unterwegs (`245_1a`) | 4 rot: v645 (ein Commit, Auftrag scheitert, Folgeauftrag, Wartung) |
| Nr. 1 – bei einem Fehler bleibt nichts | ohne `rollback()` beim Fehler (`245_1b`) | 1 rot: v645::test_scheitert_der_auftrag_bleibt_nichts |
| Nr. 2 – Folgeauftrag mit dem Verweis am Befund | Schnellauftrag dort für sich festgeschrieben (`245_2a`) | 1 rot: v645::test_folgeauftrag_aus_einem_befund_ein_commit_und_bei_fehler_nichts |
| Nr. 2 – Wartung durchführen mit dem Vertrag | Schnellauftrag dort für sich festgeschrieben (`245_2b`) | 1 rot: v645::test_wartung_durchfuehren_vorgang_und_vertrag_in_einem_commit |

Kein Marker unter `app/` nach den Läufen.

## 1.9.246 (Punkt 0d): test_v224 auf den Tag der App-Uhr

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Werkzeug Nr. 1 – Daten auf „heute“ der App über `berlin_today()` | ein Einsatz wieder auf `date.today()`, Lauf mit `--wanduhr "2026-11-10 10:00"` (`246_1`) | 1 rot: v224::test_individual_path_returns_todays_assignment (mit --wanduhr "2026-11-10 10:00") |

Kein Marker unter `app/` nach den Läufen (die Gegenprobe ändert nur den Test).
