# Gegenproben der Urlaubsrunde (ab 1.9.365)

Je Festlegung mindestens eine Gegenprobe (Regel 24): eine Ersetzung im Code mit Marker `GEGENPROBE`, die genannten Tests laufen, nur FAILED zählt; danach jede
Datei byte-gleich zurück (SHA-256), kein Marker unter `app/`. „Grund“ = die Meldung des roten Tests, geprüft.

## 1.9.365 (Punkt 1): anteiliger Anspruch als Vorschlag

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – volle Monate ab dem Eintrittstag | `monatsende(…) < bis` statt `<=` (`365_1`) | 11 rot: volle Monate (vier Fälle), Rechnung, Vorschlag, Übernehmen, von Hand, Historie, Rechte, PostgreSQL |
| Nr. 2 – halbe Tage, Mitte nach oben | ganze Tage (`365_2`) | 6 rot: Rundung (drei Fälle), Rechnung, Vorschlag, Übernehmen |
| Nr. 2 – an einer Stelle | das Übernehmen rundet selbst (`365_2b`) | 1 rot: „je an einer Stelle“ |
| Nr. 3 – die Rechnung | ohne das Ungerundete (`365_3`) | 3 rot: Rechnung, Vorschlag, Hinweis nach dem Übernehmen |
| Nr. 4 – nur, solange er abweicht | „Anspruch prüfen“ immer (`365_4`) | 2 rot: ganzes Jahr ohne Hinweis, nach dem Übernehmen |
| Nr. 5 – nie von selbst | das Konto setzt beim Lesen den Vorschlag (`365_5`) | 1 rot: „Lesen schreibt nichts“ (geänderte Zeile in der Sitzung) |
| Nr. 5 – der Server rechnet neu | Vergleich mit dem angezeigten Wert aus (`365_5b`) | 1 rot: veralteter Wert 200 statt 409 |
| Nr. 6 – der Jahresanspruch gemerkt | `anteilig_aus` nicht gesetzt (`365_6`) | 4 rot: Übernehmen (der nächste Vorschlag), von Hand, Historie, PostgreSQL |
| Nr. 6 – von Hand leert ihn | nicht geleert (`365_6b`) | 1 rot: „von Hand gilt der Wert von Hand“ |
| Nr. 7 – nur Admin und Büro – Finanzen | Route ab Büro – Auftrag (`365_7`) | 1 rot: Rechte (200 statt 403) |
| Nr. 7 – der Knopf nach dem Recht | `rechte.anspruch_setzen` immer wahr (`365_7b`) | 1 rot: Rechte |
| Nr. 8 – geschwärzt | `anteilig_aus` nicht in `KONTEN_FIELD_NAMES` (`365_8`) | 1 rot: Büro – Auftrag sieht das Feld in der Historie |
| Nr. 9 – die Karte | der Knopf auch ohne Recht (`365_9`, Vorlage) | 1 rot: Zeile der Karte in node |
| Nr. 10 – downgrade bricht ab | ohne Abbruch (`365_10`) | 2 rot: Migration unter SQLite und PostgreSQL |

14 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück. `365_8` lief zuerst gegen einen Test, der vorab nur prüfte, ob das Feld in der
Liste steht -- rot, aber nicht am Verhalten; der Test prüft jetzt zuerst die Historie, wiederholt: rot an „Büro – Auftrag sieht das Feld“.

## 1.9.366 (Punkt 2): Übertrag zuerst

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – nur Urlaub bis zum Verfall | jeder Urlaub nimmt den Übertrag (`366_1`) | 1 rot: „Urlaub bis zum Verfall nimmt zuerst den Übertrag“ (noch 0 statt 2,5) |
| Nr. 1 – einschließlich | am Verfallstag zählt nicht (`366_1b`) | 1 rot: halber Tag am 31.03. (2,5 statt 2) |
| Nr. 2 – nie unter 0 | ohne `max` (`366_2`) | 1 rot: -3 statt 0 |
| Nr. 3 – ohne Verfall jeder Urlaub | ohne Verfall nimmt keiner (`366_3`) | 1 rot: „ohne Verfall …“ (4,5 statt 2,5) |
| Nr. 4 – am Anspruch zuerst | nur die Vorgabe (`366_4`) | 1 rot: Verfall am Anspruch |
| Nr. 5 – vor und nach dem Verfall | immer „davon …, verfällt am“ (`366_5`) | 1 rot: „nach dem Verfall nicht genommen“ |
| Nr. 6 – der Rest bleibt | Rest aus `uebertrag_noch` (`366_6`) | 3 rot: Rest im Konto, nach dem Verfall, „danach Rest“ |
| Nr. 7 – „danach Rest“ nennt den Übertrag | Satz weg (`366_7`) | 1 rot: „danach Rest …“ |
| Nr. 7 – nur, wenn etwas bleibt | auch bei 0 (`366_7b`) | 1 rot: „alles verbraucht“ |
| Nr. 7 – nur bis zum Verfall | auch danach (`366_7c`) | 1 rot: „danach Rest“ nach dem Verfall |
| Nr. 8 – ausgeliefert 31.03. | Modell ohne Vorgabe (`366_8`) | 4 rot: Vorgabe, Übertrag zuerst, nach dem Verfall, „danach Rest“ |
| Nr. 8 – die Migration nur, wo leer | jede Zeile auf 31.03. (`366_8b`) | 1 rot: Migration mit eigenem Wert „30.06.“ |
| Nr. 9 – „nur vorgemerkt“ entfällt | der alte Satz zurück (`366_9`, Vorlage) | 1 rot: Einstellungen |

13 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück. Nr. 8 „downgrade ändert nichts“ ohne eigene Gegenprobe im Code: der Test prüft
nach dem downgrade denselben Wert -- eine Gegenprobe wäre ein downgrade, das zurücksetzt; das prüft derselbe Test (`assert … == nachher`).

## 1.9.367 (Punkt 3): Hinweis auf den Resturlaub in „Meine Zeiten“

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – ab dem 01.01. | ohne die untere Grenze (`367_1`) | 1 rot: 31.12.2026 mit Hinweis |
| Nr. 1 – bis einschließlich zum Verfall | `heute < verfall` (`367_1b`) | 1 rot: 31.03.2027 ohne Hinweis |
| Nr. 1 – nur, solange etwas übrig ist | `uebertrag` statt `uebertrag_noch` (`367_1c`) | 1 rot: „noch 0 Tage“ |
| Nr. 2 – Einzahl | immer „verfallen sie“ (`367_2`) | 1 rot: Text |
| Nr. 3 – jede Rolle | Route ab Büro – Auftrag (`367_3`) | 4 rot: die Monteurin bekommt 403 |
| Nr. 3 – immer die eigene Person | keine Gegenprobe im Code: die Route hat keinen Parameter für eine andere Person; der Test schickt `employee_id` mit, es bewirkt nichts | – |
| Nr. 4 – die Uhr der App | `datetime.utcnow()` (`367_4b`) | 1 rot: der Zeitpunkt weicht um Monate ab |
| Nr. 5 – der erste bleibt | immer neu gesetzt (`367_5`) | 1 rot: „der erste bleibt“ |
| Nr. 3 – ohne Hinweis 409 | ohne die Prüfung (`367_6`) | 1 rot: 200 statt 409 |
| Nr. 6 – bis gelesen | „Meine Zeiten“ zeigt ihn auch gelesen (`367_7`, Vorlage) | 1 rot: node |
| Nr. 7 – in Berlin | der Zeitpunkt roh (`367_8`, Vorlage) | 1 rot: node |
| Nr. 8 – geschwärzt | nicht in `KONTEN_FIELD_NAMES` (`367_9`) | 1 rot: Büro – Auftrag sieht das Feld |
| Nr. 9 – downgrade bricht ab | ohne Abbruch (`367_10`) | 2 rot: Migration unter SQLite und PostgreSQL |

12 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück. Selbst falsch gebaut: `367_4` (`datetime.utcnow()` ohne Import in
`app/lohnkonten.py`) -- rot am NameError, nicht am Zeitpunkt; wiederholt als `367_4b` mit gültigem Ersatz. Vor der Gegenprobe zu Nr. 5 den Test eindeutig
gemacht: zwei „Gelesen“ in derselben Sekunde hätten auch ohne Schutz denselben Zeitpunkt -- der Test setzt den ersten jetzt vorher auf einen früheren Tag.

## 1.9.368 (Punkt 4): Verfall buchen

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – erst nach dem Verfall | `heute >= verfall` (`368_1`) | 2 rot: am 31.03. offen, Buchen am 31.03. 200 statt 409 |
| Nr. 2 – nichts von selbst | das Lesen bucht (`368_2`) | 3 rot: „Lesen bucht nichts“ (geänderte Zeile in der Sitzung), dazu Rechte und Historie |
| Nr. 3 – nur der angezeigte Wert | Vergleich aus (`368_3`) | 1 rot: 2 statt 2,5 Tage 200 statt 409 |
| Nr. 4 – Rest ohne den Verfall | Rest ohne `verfallen` (`368_4`) | 2 rot: Buchen (Rest 32,5 statt 30), automatischer Übertrag |
| Nr. 5 – „Verfall prüfen“ | Hinweis aus (`368_5`) | 1 rot |
| Nr. 6 – buchen Admin und Büro – Finanzen | Route ab Büro – Auftrag (`368_6`) | 1 rot: 200 statt 403 |
| Nr. 6 – zurücknehmen nur der Admin | Route für Büro – Finanzen (`368_6b`) | 1 rot: 200 statt 403 |
| Nr. 7 – Zeilensperre | ohne `with_for_update()` (`368_7`) | 1 rot: unter PostgreSQL kein FOR UPDATE |
| Nr. 8 – wer | ohne Namen (`368_8`) | 1 rot |
| Nr. 8 – wann (Uhr der App) | `datetime.utcnow()` (`368_8b`) | 1 rot: Zeitpunkt weicht um Monate ab |
| Nr. 9 – geschwärzt | Felder nicht in `KONTEN_FIELD_NAMES` (`368_9`) | 1 rot: Büro – Auftrag sieht sie |
| Nr. 10 – „Verfall buchen“ nur mit Recht | Knopf immer (`368_10`, Vorlage) | 1 rot: node |
| Nr. 10 – abschließend | `speichern()` statt `abschliessen()` (`368_11`, Vorlage) | 2 rot: Aufbau, `test_v399` |
| Nr. 11 – downgrade bricht ab | ohne Abbruch (`368_12`) | 2 rot: Migration unter SQLite und PostgreSQL |

14 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück. Zwei zuerst unvollständig: `368_2` machte „Lesen bucht nichts“ nicht rot -- im
Test hatte Mia keine Anspruchszeile, die Gegenprobe konnte nichts schreiben; der Test legt jetzt eine an, wiederholt: rot. `368_8` änderte Zeitpunkt und Namen
zugleich, rot wurde nur der Name; der Zeitpunkt in `368_8b` für sich: rot.

## 1.9.369 (Punkt 5): Aufgabe nur an jemanden, der sie sieht

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – dieselbe Regel wie das Lesen | nur `has_min_role()` statt `task_visible_for_user()` (`369_1`) | 1 rot: das Monteur-Konto gilt als „sieht sie“ |
| Nr. 1 – nur aktive Konten | ohne Filter `active` (`369_1b`) | 1 rot: ein inaktives Konto zählt |
| Nr. 2 – der Grund | allgemeiner Text (`369_2`) | 3 rot: Regel, Anlegen, Zuweisen |
| Nr. 3 – von Hand anlegen 422 | der Endpunkt übergibt nicht „ablehnen“ (`369_3`) | 2 rot: 200 statt 422, Wächter „nur der Endpunkt“ |
| Nr. 3 – von Hand zuweisen 422 | `update_task()` prüft nicht (`369_3b`) | 1 rot: 200 statt 422 |
| Nr. 4 – Module in den Eingang | die Zuweisung bleibt (`369_4`) | 1 rot |
| Nr. 5 – nur der Endpunkt lehnt ab | ein Modul (Bedenkenanzeige) übergibt „ablehnen“ (`369_5`) | 1 rot: Wächter |
| Nr. 6 – ohne Namen und Titel | das Skript nennt den Titel (`369_6`) | 1 rot |
| Nr. 6 – nur lesend | keine Gegenprobe im Code: die Sitzung ist schreibgeschützt (`nur_lesende_sitzung()` aus `pruefe_stornos.py`, dort geprüft) und das Skript schreibt nicht | – |
| Nr. 7 – Kommentar und Docstrings | keine: reine Doku (der Test prüft nur, dass der falsche Satz weg ist) | – |

8 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück. `369_3` und `369_3b` scheiterten zuerst an einem KeyError (die Antwort 200 hatte
kein `detail`) -- der Test prüft jetzt zuerst den Status, wiederholt: rot am Status. `369_6` zuerst mit einem undefinierten Namen gebaut (wäre am NameError rot
gewesen) und vor dem Lauf durch eine gültige Ersetzung ersetzt.

## Nachrunde 1.9.370 (Punkt 1): Hinweis auf den gesetzlichen Mindesturlaub

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – × 4 | × 5 (`370_1`) | 7 rot: Regel und jeder Fall mit Mindesturlaub |
| Nr. 2 – nur zweite Jahreshälfte | ab dem 01.01. (`370_2`) | 1 rot: Austritt 30.06. mit Hinweis |
| Nr. 3 – nur nach erfüllter Wartezeit | ohne Prüfung (`370_3`) | 2 rot: 5 Monate mit Hinweis; dazu „eine Stelle“ (der Aufruf von `volle_monate()` fehlt) |
| Nr. 3 – ohne Eintritt erfüllt | ohne Eintritt nicht erfüllt (`370_3b`) | 1 rot |
| Nr. 4 – eigene Arbeitstage | immer 5 (`370_4`) | 1 rot: Teilzeit 20 statt 12 |
| Nr. 5 – nur darunter | auch gleich (`370_5`) | 1 rot: genau 20 mit Hinweis |
| Nr. 6 – nichts von selbst | das Lesen setzt den Anspruch auf den Mindesturlaub (`370_6`) | 2 rot: beim nächsten Lesen 20 statt 26; Übernehmen 409 |
| Nr. 1 – an einer Stelle | eine zweite `mindesturlaub()` in `app/lohnkonten.py` (`370_7`) | 1 rot |
| Nr. 7 – auch nach dem Übernehmen | nur ohne Übernahme (`370_8`) | 1 rot |

9 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück. Für `370_6` vorher im Test ein zweites Lesen ergänzt -- im selben Aufruf hätte
der Anspruch noch 26 gezeigt.

## Nachrunde 1.9.371 (Punkt 2): Aufgabe nur an jemanden, der sie sieht, auch ohne Mindestrolle

| Festlegung – Aussage | Gegenprobe | Ergebnis |
|---|---|---|
| Nr. 1 – auch ohne Mindestrolle | wieder nur mit (`371_1`) | 4 rot: Regel, von Hand, Module, Prüfskript |
| Nr. 1 – ohne Mindestrolle nur das Büro | Rollen im Grund ohne die Bürogrenze (`371_1b`) | 2 rot: „Monteur, Büro – Auftrag, …“ im Grund |
| Nr. 3 – von Hand anlegen 422 | ablehnen nur mit Mindestrolle (`371_2`) | 2 rot: POST 200 statt 422; `zuweisung="ablehnen"` wirft nicht |
| Nr. 3 – von Hand zuweisen 422 | PUT prüft nur mit Mindestrolle (`371_2b`) | 1 rot: PUT 200 statt 422 |
| Nr. 4 – Module in den Eingang | ohne Mindestrolle bleibt die Zuweisung (`371_3`) | 1 rot: die Aufgabe hat den Monteur |
| Nr. 5 – nur aktive Konten | auch inaktive (`371_4`) | 2 rot: Otto mit inaktivem Konto „sieht“ sie (auch der Test aus 1.9.369) |
| Nr. 6 – jede zugewiesene Aufgabe gezählt | wieder nur mit Mindestrolle (`371_5`) | 1 rot: „2 von 3“ statt „3 von 5“ |
| Nr. 6 – „Mindestrolle keine“ | „-“ (`371_5b`) | 1 rot |
| Nr. 7 – nur eine neue Zuweisung geprüft | jede mitgeschickte (`371_7`) | 1 rot: der Bestand an den Monteur 422 statt 200 |
| Nr. 2 – der Grund | (geprüft über `371_1b` und die Texte in den Tests zu Nr. 3) | -- |

9 Gegenproben, alle rot aus dem geprüften Grund; alle Dateien byte-gleich zurück. `371_2` und `371_2b` waren im ersten Lauf rot über einen KeyError (der Test
las `detail` vor dem Status) -- der Test prüft jetzt zuerst den Status, beide noch einmal: rot über „200 statt 422“. Nach dem Test zu Nr. 7 `371_2b` ein
drittes Mal: 2 rot (auch die neue Zuweisung im Bestandstest 200 statt 422).
