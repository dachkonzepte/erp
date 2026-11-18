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
