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
