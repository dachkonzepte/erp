# Testablauf und Klicktest-Werkzeug (ab 1.8.108)

Archiv für Runden, die nur das Werkzeug betreffen: volle Suite, Klicktests (`scripts/klicktest_alle.py`, `scripts/cdp_klicktest.py`),
die lokale PostgreSQL-Testinstanz, der Ablauf vor Commit und Bericht. Seit 1.8.108 (Regel 28) stehen hier auch die Festlegungen, die
nur Klicktest-Werkzeug und Testablauf betreffen -- je in einer Zeile mit "Bitte bestätigen"; der Bericht nennt nur ihre Zahl. Die
Bedienung selbst steht in CLAUDE.md ("Testen", Regeln 15, 24, 26–28).

## Parallele Testläufe (1.8.108)

### Vorgabe vom 14.10.2026 (übernommen wie gegeben)

> Werkzeug-Runde; an der Anwendung unter app/ ändert sich nichts. Ziel: kürzere Wartezeit bei gleicher Prüfstrenge.
> 1. Volle Suite parallel mit dynamischer Verteilung (pytest-xdist o. ä.), PostgreSQL-Tests je Worker in eigenen Schemas, Regel 27
>    bleibt. Ist „Shared Memory aufgebraucht“ eine Einstellung der Testinstanz (max_locks_per_transaction o. ä.), diese erhöhen. Ziel:
>    unter 10 min.
> 2. klicktest_alle mit Option für drei bis vier gleichzeitige Klicktests; zeitkritische laufen allein. Ziel: unter 7 min.
> 3. Klicktests in Gegenproben brechen nach 2 min ab.
> 4. Zu Beginn eines Testlaufs werden liegen gebliebene pgtest_*-Schemas in spielwiese gelöscht, nur solche, deren Lauf nicht mehr
>    läuft, nie public.
> 5. Vor jedem Commit läuft die volle Suite parallel statt gezielter Teilläufe; Regel 26 bleibt unverändert.
> 6. Regel 28: Festlegungen, die nur Klicktest-Werkzeug und Testablauf betreffen, stehen im Archiv; der Bericht nennt ihre Zahl.
>
> Nachweis: Messung vorher und nachher. Die Zahl der gelaufenen Tests und Klicktests stimmt mit dem Lauf nacheinander überein. Danach
> drei volle Läufe von Suite und Klicktests hintereinander ohne Ausreißer; jeder Ausreißer ist ein Befund.
>
> Eigene Festlegungen mit „Bitte bestätigen“, je in einer Zeile. Nebenbefunde nur melden. Commit nach Regel 13, Bericht kurz.

### Umsetzung 1.8.108

#### Was gebaut ist

- **Punkt 1, Suite parallel** (pytest-xdist, `requirements.txt`): `.venv\Scripts\python.exe -m pytest -q -n 16 --dist loadfile`.
  `loadfile` verteilt dynamisch je Datei -- ein freier Arbeitsprozess holt sich die nächste Datei, die mit den meisten Tests zuerst
  (Vorgabe von xdist); innerhalb einer Datei bleibt die Reihenfolge wie nacheinander, Modul-Fixtures laufen einmal. Jeder Arbeitsprozess
  hat seine eigene Wegwerf-Datenbank und seinen eigenen Datenordner (`tests/conftest.py`, je Prozess), die Tests gegen PostgreSQL legen
  wie bisher je Test ein eigenes Schema `pgtest_<name>_<zufall>` an (Regel 27 unverändert). `pytest` ohne `-n` läuft wie bisher
  nacheinander (keine Vorgabe in `pytest.ini`), damit ein einzelner Test nicht 16 Prozesse startet.
- **Punkt 1, Testinstanz**: „Shared Memory aufgebraucht“ war die Sperrtabelle der Spielwiese -- `max_locks_per_transaction` 64 ×
  (100 Verbindungen + 3) = rund 6600 Sperren für alle Transaktionen zusammen; ein `DROP SCHEMA … CASCADE` eines Testschemas (190 Tabellen,
  753 Indizes, 173 Sequenzen) braucht allein über 1100, ein `create_all()` ähnlich viele. Im Serverprotokoll der Spielwiese stehen sechs
  solche Abbrüche (30.09., 02.10., 14.10. 15:44 -- dieser ließ drei Schemas `pgtest_rechnungen_*` liegen). Jetzt
  `max_locks_per_transaction = 1024` in `%LOCALAPPDATA%\pgportable\data\postgresql.conf` (nicht im Repo; Kommentar an der Zeile),
  Neustart über `pg_ctl restart`.
- **Punkt 4, liegen gebliebene Schemas** (`tests/pg_schutz.py`): der Wächter hängt an jedes `CREATE SCHEMA pgtest_…` eines Testprozesses
  im selben Cursor (also in derselben Transaktion) `COMMENT ON SCHEMA … IS 'erp-pytest host=<rechner> pid=<pid> start=<startzeit>'`.
  `liegen_gebliebene_schemas_loeschen()` liest alle `pgtest_*` (`LIKE 'pgtest\_%'`, nur Namen aus `[a-z0-9_]`) über eine Verbindung mit
  `search_path=pg_catalog` und löscht je Schema in eigener Transaktion (`lock_timeout` 10 s) nur, wenn der Prozess der Kennung auf diesem
  Rechner nicht mehr läuft -- PID und Startzeit (Windows: `GetProcessTimes`, sonst `/proc/<pid>/stat`), eine neu vergebene PID zählt
  nicht. Stehen bleiben: Schemas laufender Prozesse, ohne Kennung (Stand vor 1.8.108 oder nicht aus einem Test), mit Kennung eines anderen
  Rechners. `tests/conftest.py::pytest_sessionstart` ruft es zu Beginn jedes Laufs im Hauptprozess auf (nicht in den Arbeitsprozessen von
  xdist) und meldet eine Zeile je Art, wenn es etwas gibt; ist PostgreSQL nicht erreichbar, eine Zeile und der Lauf geht weiter. Die drei
  liegen gebliebenen Schemas vom 14.10. (ohne Kennung) einmal von Hand gelöscht, als kein Lauf ging.
- **Punkt 2, Klicktests zugleich** (`scripts/klicktest_alle.py --gleichzeitig N`, Vorgabe 1 = nacheinander wie bisher): zuerst die
  Klicktests mit `ALLEIN = "<Grund>"` nacheinander, während kein anderer läuft, danach die übrigen zu N zugleich, die längsten zuerst
  (`KLICKTEST_DAUERN`, Laufzeiten nacheinander aus der Messung vorher). Jeder Klicktest hat wie bisher eigene Ports, eigenen Arbeitsordner
  und eigene Wegwerf-Datenbank. Zeitkritisch heißt: ein Fenster, in dem etwas NICHT geschehen darf (`warten("false", …, melden=False)`) --
  unter Last zu kurz, um eine falsche Seite zu erwischen, die Prüfung würde still schwächer --, ein Zeitlimit über `window.__dkZeitlimit`
  oder gedrosseltes Netz: `klicktest_abschliessen`, `klicktest_anmelden`, `klicktest_feierabend`, `klicktest_fremde_seite`,
  `klicktest_hochladen`, `klicktest_veraltete_antworten`. `tests/test_v413_testlauf_parallel.py` verlangt `ALLEIN` für jedes Skript mit
  einem dieser Merkmale.
- **Punkt 3, Gegenprobe** (`scripts/cdp_klicktest.py`): steht `GEGENPROBE` irgendwo unter `app/` (dieselbe Suche wie test_v357), startet
  `klicktest_main()` einen Wachhund (Thread) mit 120 s; läuft er ab, druckt er „ABBRUCH: Zeitlimit …“, beendet die eigenen Kindprozesse
  (Befüllen, Instanz, Chrome) über ihre PID samt Baum und den Prozess mit Rückgabecode 3. Neu dazu `--zeitlimit SEK` für jeden Klicktest;
  in einer Gegenprobe gilt das kleinere. `klicktest_alle.py` führt Rückgabecode 3 als „Zeitlimit“.
- **Punkt 5** steht in Regel 15, **Punkt 6** in Regel 28 (CLAUDE.md); Regel 26 unverändert.

#### Messung

Gleicher Rechner (20 Kerne, 28 Threads, 30 GB), PostgreSQL-Tests eingeschlossen (`ERP_TEST_POSTGRES_URL` gesetzt), jeweils nichts
anderes nebenher.

| Lauf | Stand | Dauer | Ergebnis |
|---|---|---|---|
| Suite nacheinander (vorher) | 1.8.107 `40d878e`, saubere Arbeitskopie | 41:23 | 5258 grün |
| Suite `-n 16 --dist loadfile` | Arbeitsstand 1.8.108 | 7:11 | 5276 grün (5258 + 18 neue in test_v413) |
| Suite `-n 12` | Arbeitsstand 1.8.108 | 7:36 | 5276 grün |
| Suite `-n 24` | Arbeitsstand 1.8.108 | 7:42 | 5276 grün |
| Klicktests nacheinander (vorher) | 1.8.107 `40d878e`, saubere Arbeitskopie | 16:00 | 67 von 68, 1618 Prüfungen (rot `klicktest_anmelden` ohne rote Prüfung, Nebenbefund 1) |
| Klicktests `--gleichzeitig 4` | Arbeitsstand 1.8.108 | 6:20 | 68 von 68, 1618 Prüfungen |

Abgleich (JUnit-XML je Test-ID): die parallelen Läufe haben dieselben 5258 Test-IDs mit demselben Ergebnis wie der Lauf nacheinander,
dazu die 18 neuen; die Klicktests dieselben 68 mit denselben Prüfungen je Test. Mehr als 16 Arbeitsprozesse helfen nicht: unter Last
dauert jeder Test im Mittel länger (Summe der Testzeiten 2471 s nacheinander, 4847 s bei 12, 5845 s bei 16, 8906 s bei 24), bei
PostgreSQL-Tests und den übrigen gleich stark -- der Engpass ist der Rechner, nicht die Spielwiese. Am Ende eines Laufs stehen die
meisten Arbeitsprozesse rund 50 s leer, während die Migrationsproben laufen (wenige Tests je Datei, xdist reiht nach der Zahl der
Tests). Spitze in der Spielwiese bei 16: 34 Verbindungen, 27 814 Sperren, 10 Schemas zugleich (bei 24: 38, 35 795, 10) -- mit der
alten Grenze (rund 6600 Sperren) wäre der Lauf abgebrochen. Die Läufe auf dem Commit nach Regel 26: im Bericht.

#### Festlegungen 1.8.108 (Bitte bestätigen)

Alle betreffen nur Werkzeug und Testablauf (Regel 28 seit 1.8.108: der Bericht nennt ihre Zahl), außer Nr. 1.

1. **`pytest-xdist` steht in `requirements.txt`** wie `pytest` und `httpx` -- `update.sh` installiert es auf dem Server mit (nur Tests, vom Dienst nie geladen).
2. **Parallel heißt `-n 16 --dist loadfile`**: je Testdatei ein Arbeitsprozess (Reihenfolge und Modul-Fixtures in einer Datei wie nacheinander), keine Verteilung einzelner Tests (`worksteal`) -- 16 gemessen als schnellste Zahl auf diesem Rechner.
3. **`pytest` ohne `-n` bleibt nacheinander** (nichts in `pytest.ini`): ein einzelner Test startet keine 16 Prozesse; die volle Suite gibt `-n 16 --dist loadfile` ausdrücklich an.
4. **Spielwiese `max_locks_per_transaction = 1024`** (in `postgresql.conf` der lokalen Instanz, nicht im Repo, Kommentar an der Zeile); `max_connections` bleibt 100 (Spitze 38).
5. **Kennung am Schema** ist ein Kommentar `erp-pytest host=<rechner> pid=<pid> start=<startzeit>` des Prozesses, der `CREATE SCHEMA pgtest_…` ausführt (bei xdist der Arbeitsprozess), gesetzt vom Wächter in derselben Transaktion -- kein Test muss dafür etwas tun.
6. **"Lauf läuft nicht mehr"** heißt: der Prozess der Kennung läuft auf diesem Rechner nicht mehr, verglichen über PID und Startzeit (eine neu vergebene PID zählt nicht); ein Prozess, den dieser Benutzer nicht öffnen darf, gilt als nicht mehr laufend.
7. **Ohne Kennung oder mit Kennung eines anderen Rechners wird nicht gelöscht**, nur genannt -- auch Schemas eines Stands vor 1.8.108, die dann von Hand zu löschen sind (nur, wenn kein Lauf geht).
8. **Aufgeräumt wird zu Beginn jedes Laufs im Hauptprozess**, je Schema in eigener Transaktion mit `lock_timeout` 10 s; Fehlschlag und nicht erreichbare Instanz nur gemeldet, der Lauf geht weiter. Eine Zeile je Art erscheint nur, wenn es etwas gibt (höchstens fünf Namen).
9. **`klicktest_alle.py --gleichzeitig N`, Vorgabe 1** (nacheinander, alphabetisch wie bisher); 4 gemessen und in CLAUDE.md genannt; der Bericht nach Regel 26 nimmt 4.
10. **Zeitkritisch** (`ALLEIN`) ist ein Klicktest mit `warten("false", …)` (Fenster, in dem nichts geschehen darf), `window.__dkZeitlimit` oder gedrosseltem Netz/CPU -- heute sechs; ein Test verlangt es. Kurze feste Pausen vor einem Bildschirmfoto zählen nicht.
11. **Die Klicktests mit `ALLEIN` laufen zuerst**, einzeln, bevor die übrigen zu viert beginnen.
12. **Reihenfolge der übrigen: die längsten zuerst** nach `KLICKTEST_DAUERN` (Laufzeiten nacheinander vom 14.10.2026, fest im Skript); ein neuer Klicktest ohne Eintrag läuft vorn, ein veralteter Wert kostet nur Zeit.
13. **Gegenprobe erkannt am Marker `GEGENPROBE` irgendwo unter `app/`** (dieselbe Suche wie test_v357), Grenze 120 s ab Start des Klicktests einschließlich Befüllen; `--zeitlimit` kann sie nur verkürzen.
14. **Abbruch über einen Wachhund-Thread**: beendet Befüllen, Instanz und Chrome über ihre PID samt Baum (Regel 12), Rückgabecode 3, `klicktest_alle.py` führt 3 als "Zeitlimit"; kein Netzprotokoll beim Abbruch (die Ereignisschleife kann hängen).
15. **`--zeitlimit SEK` gibt es für jeden Klicktest**, ohne Angabe und ohne Gegenprobe kein Limit (wie bisher; `klicktest_alle.py` behält seine 900 s je Test).
16. **Punkt 5 steht in Regel 15** (Testläufe), Regel 26 unverändert; **Punkt 6 in Regel 28**, das Archiv dafür ist diese Datei.

#### Tests und Prüfung

- Neu `tests/test_v413_testlauf_parallel.py` (18, davon 3 gegen PostgreSQL): Startzeit und Kennung eines laufenden und eines beendeten
  Prozesses, dieselbe PID mit anderer Startzeit, anderer Rechner, ungültige Kennung; gegen PostgreSQL ein angelegtes Schema trägt die
  Kennung, das Aufräumen löscht nur das Schema eines beendeten Prozesses (laufend, ohne Kennung, anderer Rechner, `pgtestauf_…` ohne
  Unterstrich und `public` bleiben), und ein Testlauf im Unterprozess räumt zu Beginn auf und nennt es; jeder zeitkritische Klicktest hat
  `ALLEIN`; `ALLEIN` wird gelesen, nicht importiert; Reihenfolge (allein zuerst, dann die längsten); mit Schein-Klicktests höchstens N
  zugleich und die mit `ALLEIN` ohne andere, nacheinander wie bisher, Zeitlimit und Rückgabecode 3 als "Zeitlimit"; die Suche nach dem
  Marker; Ende zu Ende ein hängender Klicktest bricht in der Gegenprobe nach dem Limit ab, beendet sein Befüllen, `--zeitlimit` verkürzt
  und verlängert nicht.
- Gegenproben 14 von 14 rot, jede aus dem erwarteten Grund (Startzeit ignoriert, ohne Kennung bzw. laufende gelöscht, keine Kennung
  angehängt, Muster und Namensprüfung ohne Unterstrich, kein Aufräumen beim Start, einer mehr zugleich, `ALLEIN` nicht gelesen,
  `klicktest_hochladen` ohne `ALLEIN`, Kinder nicht beendet, Wachhund nicht abgewartet, Hand-Limit verlängert die Gegenprobe, Marker nicht
  gesucht, Rückgabecode 3 nicht als Zeitlimit). Jede Datei byte-genau zurück (Prüfsummen). Der erste Durchgang war für acht Fälle wertlos
  (rot an einem fehlenden `--basetemp`-Ordner, nicht an der Prüfung) -- wiederholt, danach mit Grund je Fall.
- Angepasste Erwartungen (Regel 28): keine.
- Volle Suite und alle Klicktests auf dem Commit, nacheinander und dreimal parallel: im Bericht (Regel 26).

#### Nebenbefunde (nur gemeldet)

1. **`klicktest_anmelden` rot ohne rote Prüfung** (Lauf nacheinander auf 1.8.107, 69/69): im Teil "Zwei Faktoren" öffnet der Test
   `/projects`, während `/account` gerade `POST /api/account/2fa/setup/start` sendet -- Chrome fragt "Seite verlassen?", das Werkzeug
   zählt den Dialog als nicht wie erwartet. Ein Wettlauf im Klicktest (vor der Navigation fehlt `warte_auf_ruhe()`), schon auf 1.8.107;
   im parallelen Lauf grün (er läuft dort allein wie nacheinander).
2. **Am Ende eines parallelen Laufs stehen die meisten Arbeitsprozesse rund 50 s leer**: xdist reiht die Dateien nach der Zahl ihrer
   Tests, die Migrationsproben (wenige, lange Tests) kommen zuletzt. Eine Reihung nach Laufzeit bräuchte eine gepflegte Liste je Datei --
   nicht gebaut.
3. **Der Benutzer `erp` darf die Konfiguration der Spielwiese nicht lesen** (`config_file` nur mit `pg_read_all_settings`) und kein
   `ALTER SYSTEM` -- die Einstellung ist deshalb direkt in `postgresql.conf` geändert.

#### Nachtrag 1.8.108: drei Wettläufe in Klicktests (Befund der Endläufe auf `a412761`)

Endläufe nach Regel 26 auf `a412761` (saubere Arbeitskopie): Suite parallel dreimal 5276 grün (7:27, 7:25, 7:10); Klicktests zu viert
Lauf 1 68 von 68 (6:24), Lauf 2 66 von 68 (6:14), Lauf 3 66 von 68 (6:45) -- rot je `klicktest_anmelden` und
`klicktest_behinderungsanzeige_versand`. Der Lauf nacheinander danach wurde abgebrochen (nach der Korrektur ohnehin zu wiederholen).
Die Ursache steckt in den Klicktests selbst, nicht im parallelen Lauf: jedes Mal wartete der Test nicht auf das, was die Seite noch tat,
und las sie zu früh -- unter Last öfter. Befunde (die Ausreißer):

1. **`klicktest_anmelden`, "Zwei Faktoren"** (auch auf 1.8.107 nacheinander, Nebenbefund 1 oben): `/account` startet beim Laden die
   Einrichtung des zweiten Faktors (`POST /api/account/2fa/setup/start` über `speichern()`); der Test öffnete `/projects`, während sie
   unterwegs war -- "Seite verlassen?", das Werkzeug zählt den Dialog als nicht wie erwartet. Jetzt `warte_auf_ruhe()` davor.
2. **`klicktest_anmelden`, "Angriff über das Formular"** (Lauf 3, drei Prüfungen `/login` statt `/projects`): die Wartebedingung nach dem
   Anmelden enthielt `location.href.includes('fremd')` -- "fremd" steht schon in `/login?next=…fremd`, die Bedingung war sofort erfüllt,
   die Prüfung las die Seite, während die Anmeldung noch unterwegs war. Seit 1.8.98 so; nacheinander meist noch rechtzeitig. Jetzt wartet
   sie auf `/projects` oder eine Adresse außerhalb des ERP (`!location.href.startsWith(<ERP>/)`) -- was die Prüfung schon immer meinte.
3. **`klicktest_behinderungsanzeige_versand`, "Wiederaufnahme: Einschreiben nachgetragen"**: nach "Brief erstellen" lädt die Karte den
   Versandverlauf neu, `_dhZeichnen()` zeichnet den Container samt Formular "Zustellung nachtragen" neu; kam das unter Last erst nach dem
   Öffnen des Formulars und dem Eintragen der Notiz, war die Notiz weg, "Zustellung speichern" sendete nichts (keine offene Anfrage), die
   Zeile erschien nie. Jetzt `warte_auf_ruhe()` vor dem Öffnen; dieselbe Stelle in `klicktest_behinderungsanzeige_abschluss` (bisher grün)
   ebenso.

Nachweis unter Überlast (22 CPU-Brenner auf 28 Threads, je Klicktest drei Kopien gleichzeitig): vorher `klicktest_anmelden` 3 von 3 rot
(Dialog und `/login`, wie in den Endläufen); mit der Korrektur `klicktest_anmelden` 3× 69/69, `klicktest_behinderungsanzeige_versand` 3×
42/42, `klicktest_behinderungsanzeige_abschluss` 3× 43/43, in einer zweiten Überlast-Probe ebenso. Prüfungen und Soll unverändert (nur
Warten; Nr. 2 prüft jetzt, was sie vorgab). Angepasste Erwartungen (Regel 28): keine. Endläufe auf dem Nachtrag: im Bericht (Regel 26).

**Nebenbefund 4 (nur gemeldet)**: in der Überlast-Probe mit neun gleichzeitig endenden Klicktests endete einer nach "42 von 42" nicht
mehr (in allen drei Proben mit dieser Mischung, immer die erste Kopie von `klicktest_behinderungsanzeige_versand`; nicht in einer Probe nur mit ihm): der Stapel (faulthandler) zeigt ihn in
`cdp_klicktest.beenden()` -- `subprocess.run(["taskkill", "/PID", …, "/T", "/F"], capture_output=True)` wartet ohne Zeitlimit auf die
Ausgabe von `taskkill` (Chrome). In keinem der Läufe zu viert (rund 200 Klicktests) aufgetreten; `klicktest_alle.py` bricht nach 900 s
ab. Ein Zeitlimit an `taskkill` wäre die Abhilfe -- nicht gebaut.
