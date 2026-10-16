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

#### Festlegungen 1.8.108 (alle bestätigt am 15.10.2026)

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

#### Nachtrag 1.8.108 (2): Verklemmung im Testhelfer `_run` (Befund der Endläufe auf `bc2dcad`)

Der erste Suite-Lauf der Endläufe auf `bc2dcad` blieb bei 99 % stehen. In der Spielwiese wartete ein `INSERT INTO order_revisions` auf
eine Sitzung, die seit 23 min "idle in transaction" war, beide im Schema eines Arbeitsprozesses (Kennung am Schema, PID über den
Client-Port bestätigt). Der Stapel des Arbeitsprozesses (py-spy, nur im Scratchpad) zeigte
`test_v383_nebenforderungen_pg::test_pg_client_change_waits_for_ordering_and_asks_for_a_reason` in `_run` aus
`tests/test_v375_rechnungen_sperren.py`: die erste Aktion (`create_order_from_quote`) committet nach der Freigabe ein zweites Mal
(Revision) und wartete dabei mit der Prüfung des Fremdschlüssels auf die Sperre der Auftragszeile, die die zweite Aktion (Kundenwechsel,
abgelehnt mit "Begründung") noch hielt; `_run` rief zuerst `holder.close()` -- das wartete auf die Verbindung der ersten Aktion --
und hätte die zweite Sitzung erst danach geschlossen. Derselbe Test hing schon am 12.10.2026 (damals zwei Läufe nebeneinander); seit 1.8.87
schließt `_run` die zweite Sitzung, aber in der falschen Reihenfolge. Unter Last trifft die zweite Aktion die Sperre öfter vor dem zweiten
Commit der ersten.

Korrektur in `_run` (von zehn Testdateien benutzt): zuerst die Sitzung der zweiten Aktion schließen, dann auf die erste warten; hängt die
erste trotzdem, wird der Test rot ("die erste Aktion hängt …") statt den Lauf anzuhalten. Prüfungen unverändert. Nachbau (Scratchpad,
kurz unter `tests/` ausgeführt und wieder entfernt): erste Aktion committet zweimal, die zweite sperrt die Auftragszeile und lehnt ab --
mit dem alten `_run` nach 90 s noch hängend, mit dem neuen fertig. Der Endlauf wurde über die eigenen PIDs beendet; das liegen gebliebene
Schema seines Arbeitsprozesses hat der nächste Testlauf beim Start gelöscht (Punkt 4 im Ernstfall).

**Nebenbefund 5 (nur gemeldet)**: `_run` in `tests/test_v363_zweck_abnahme.py` und `tests/test_v365_abnahme_aus_protokoll.py` (eigene
Kopien) schließen die Sitzung der zweiten Aktion gar nicht -- dieselbe Verklemmung wäre dort möglich, wenn die erste Aktion nach der
Freigabe noch eine Sperre der zweiten braucht; nicht beobachtet. Eine Zeitgrenze je Test (pytest-timeout oder `faulthandler_timeout`) gibt
es nicht -- ein hängender Test hält den ganzen Lauf an.

#### Nachtrag 1.8.108 (3): Befunde der Endläufe auf `b8ddb1c` (nachgetragen am 15.10.2026)

Aus den Endläufen auf `b8ddb1c`, im Bericht gemeldet, hier erst mit der nächsten Runde nachgetragen (ein Doku-Commit hätte damals Regel 26
neu ausgelöst -- seit 15.10.2026 nicht mehr, siehe Regel 26):

1. **Wettlauf in der Anwendung**: `app/orders.py::create_order_revision()` vergab `max(revision_number) + 1` ohne Sperre und nach dem
   Commit der Änderung -- zwei gleichzeitige Nachträge, der zweite 500 (`uq_order_revision_number`), sein Nachtrag schon gespeichert.
   Gefunden von `test_v386::test_postgresql_two_addenda_at_once_get_two_numbers` (einer von vier Läufen). Vorgabe vom 15.10.2026 Punkt 5
   (`docs/archiv/befund-vor-echtbetrieb.md`, "Vor dem Abnahmetest").
2. **`klicktest_zeitbuchungen_liste` zwischen 0 und 2 Uhr rot** ("Liste gekürzt" der Monteurin fehlte): das Befüllen legte das
   14-Tage-Fenster relativ zum UTC-Tag an, die Seite rechnet seit 1.8.87 in Berlin. Vorgabe vom 15.10.2026 Punkt 6.
3. Nebenbefunde 4 und 5 oben (taskkill ohne Zeitlimit, `_run`-Kopien, keine Zeitgrenze je Test): Vorgabe vom 15.10.2026 Punkt 7.

Die Festlegungen 1.8.108 Nr. 1–16 sind am 15.10.2026 bestätigt. Regel 26 ist am selben Tag ergänzt: ein Commit, der nur `docs/` ändert,
löst keinen neuen Endlauf aus.

## Vor dem Abnahmetest: Klicktest nachts, Zeitgrenze je Test, `_run`, taskkill (1.8.111)

Vorgabe vom 15.10.2026, Punkte 6 und 7 (Wortlaut der ganzen Vorgabe: `docs/archiv/befund-vor-echtbetrieb.md`, "Vor dem Abnahmetest:
Zahleneingaben, lesbare Fehler, Revisionsnummer, Testablauf"):

> 6. klicktest_zeitbuchungen_liste zwischen 0 und 2 Uhr: mit fester Uhr klären, ob der Test oder die Anwendung falsch rechnet; liegt es
>    an der Anwendung, beheben.
> 7. Testablauf: Zeitgrenze je Test; die _run-Kopien in test_v363 und test_v365 schließen ihre Sitzungen; taskkill in beenden() mit
>    Zeitlimit.

Vorweg (gleiche Vorgabe): alle 16 Festlegungen 1.8.108 bestätigt; Regel 26 ergänzt -- ein Commit, der nur `docs/` ändert, löst keinen
neuen Endlauf aus.

### Umsetzung 1.8.111

#### Punkt 6: der Test rechnete falsch, nicht die Anwendung

- **Geklärt mit fester Uhr**: Instanz und Browser auf heute 00:30 Uhr Berliner Zeit (in UTC noch gestern). Die Monteur-Zeiterfassung
  bildet ihr Fenster `berlinAddDays(berlinToday(), -14)` bis `berlinToday()` (`time_tracking_field.html`, seit 1.8.87, Regel 20), der
  Server liefert genau dieses Fenster. Das Befüllen legte die 501 Buchungen der Monteurin über die letzten 15 Tage relativ zum UTC-Tag an
  und zählte das Soll im UTC-Fenster ("die Monteur-Seite bildet ihr Fenster in UTC" -- seit 1.8.87 veraltet): nachts lag das Fenster des
  Tests einen Tag neben dem der Seite, 467 statt 501 Buchungen, kein "Liste gekürzt". Die übrigen Seiten des Klicktests rechnen ebenfalls
  in Berlin, der Test dort mit `date.today()` (Ortszeit des Rechners, zufällig richtig).
- **Behoben im Test**: alle Daten aus dem Berliner Tag der Instanz (`berlin_today()`), und der Klicktest läuft jetzt immer im Nachtfenster:
  `klicktest_main(…, uhr="00:30")` und der Browser auf derselben Uhr.
- **Browser-Uhr im Werkzeug** (`scripts/cdp_klicktest.py`, Opt-in): `Werkzeug.uhr_versatz_ms()` im Befüllen (Vorsprung der festen Uhr der
  Instanz vor der echten), `Tab.browser_uhr(versatz)` vor dem ersten Laden -- `new Date()` ohne Argument und `Date.now()` laufen um den
  Versatz verschoben weiter (`BROWSER_UHR`, per `Page.addScriptToEvaluateOnNewDocument`). Ohne den Browser sähe der Klicktest einen
  Rückfall einer Seite auf UTC nicht: die echte Uhr am Tag ist in Berlin wie in UTC derselbe Tag.

#### Punkt 7: Testablauf

- **Zeitgrenze je Test** (`tests/zeitgrenze.py`, eingebunden in `tests/conftest.py`): je Test eine Uhr in einem eigenen Thread über Aufbau,
  Test und Abbau (`pytest_runtest_protocol`); läuft sie ab, schreibt sie an der Ausgabe-Umleitung von pytest vorbei "ZEITGRENZE: <Test>
  läuft länger als N s …" und den Stapel aller Threads (faulthandler) und beendet den Testprozess (`os._exit(3)` -- ein Thread, der in C an
  einer Sperre oder einem Socket wartet, lässt sich nicht anders unterbrechen). Vorgabe 300 s, je Test `@pytest.mark.zeitgrenze(n)`, für
  den Lauf `--zeitgrenze SEK`, 0 schaltet ab. Ohne `-n` endet der Lauf dort (Rückgabecode 3); im parallelen Lauf meldet xdist den Test als
  abgestürzt ("worker … crashed while running …") und ersetzt den Arbeitsprozess.
- **Befund dabei**: mit `--dist loadfile` gibt xdist nach dem Absturz die ganze Datei zurück -- einschließlich des abgestürzten Tests. Er
  lief wieder bis zur Grenze, bis xdist keine Arbeitsprozesse mehr ersetzte (gemessen: achtmal in Folge, der übrige Test der Datei lief nie;
  mit 16 Arbeitsprozessen wären es bis zu 64 × 5 min). Deshalb schreibt die Uhr den Test vor dem Beenden in eine Datei des Laufs
  (`%TEMP%/erp_pytest_zeitgrenze_<PYTEST_XDIST_TESTRUNUID>.txt`); `pytest_runtest_setup` meldet ihn beim nächsten Versuch sofort als Fehler
  ("… hat seine Zeitgrenze in diesem Lauf schon überschritten … nicht noch einmal ausgeführt"), der Rest der Datei läuft.
- **`_run` in `tests/test_v363_zweck_abnahme.py` und `tests/test_v365_abnahme_aus_protokoll.py`** (Nebenbefund 5): wie
  `tests/test_v375_rechnungen_sperren.py::_run` seit dem Nachtrag 2 -- die Sitzung der zweiten Aktion wird eigens angelegt und geschlossen,
  sobald die zweite Aktion fertig ist, bevor auf die erste gewartet wird; hängt eine der beiden, wird der Test rot ("die zweite Aktion
  hängt" bzw. "die erste Aktion hängt …") statt den Lauf anzuhalten.
- **taskkill mit Zeitlimit** (Nebenbefund 4): `scripts/cdp_klicktest.py::beenden()` ruft taskkill ohne Ausgabe (`DEVNULL` statt
  `capture_output`) und mit `TASKKILL_SEKUNDEN` = 30; läuft es länger, wird taskkill selbst beendet und eine Hinweiszeile mit der PID
  gedruckt, der Klicktest endet trotzdem. Dasselbe für `scripts/klicktest_alle.py::_baum_beenden()`.

#### Messung

Laufzeiten im parallelen Lauf (`-n 16 --dist loadfile`, Stand `b8ddb1c`, 5276 Tests, 8:00): längster Test 32,3 s
(`test_v380::test_pg_migration_refuses_with_a_list_of_duplicates_and_changes_nothing`), längster Aufbau 24,4 s (Modul-Fixture in
`test_v324`); die zehn längsten Tests alle Migrationsproben gegen PostgreSQL. 300 s je Test ist rund das Neunfache des längsten.

#### Festlegungen 1.8.111 (Bitte bestätigen)

Alle betreffen nur Werkzeug und Testablauf (Regel 28: der Bericht nennt ihre Zahl).

1. **Zeitgrenze 300 s je Test** (Aufbau, Test und Abbau zusammen), für einen Test `@pytest.mark.zeitgrenze(n)`, für den Lauf `--zeitgrenze SEK`, 0 = aus.
2. **Eigene Umsetzung (Thread, faulthandler, `os._exit(3)`) statt pytest-timeout** -- keine neue Abhängigkeit; dieselbe Wirkung wie dessen Methode "thread" unter Windows.
3. **Ein Test, dessen Zeitgrenze im parallelen Lauf abgelaufen ist, läuft im selben Lauf nicht noch einmal** (Datei je Lauf im Temp-Ordner, bleibt dort liegen -- einige Bytes je Lauf mit Abbruch).
4. **taskkill mit 30 s Zeitlimit und ohne Ausgabe**, Hinweiszeile statt Abbruch -- in `beenden()` und ebenso in `klicktest_alle.py::_baum_beenden()`.
5. **`klicktest_zeitbuchungen_liste` läuft immer bei 00:30 Uhr** (Instanz und Browser) -- im Fenster, in dem Berlin und UTC verschiedene Tage haben.
6. **Die Browser-Uhr ist ein Opt-in** (`uhr_versatz_ms()`/`browser_uhr()`); die übrigen Klicktests mit fester Uhr behalten die echte Uhr im Browser.
7. **Die `_run`-Kopien bleiben in ihren Dateien** (sie geben anderes zurück als `test_v375::_run`), mit denselben zwei Regeln: zweite Sitzung zuerst schließen, Hängen als rote Prüfung.

#### Tests und Prüfung

- Neu `tests/test_v416_testablauf.py` (11 und 3 Proben, die nur im Unterprozess laufen; davon 3 gegen PostgreSQL): ein hängender Test beendet
  den Lauf mit Stapel ("ZEITGRENZE: …", der Stapel nennt die Probe) nach 3 s statt zu hängen; im parallelen Lauf ein Absturz, der Test kein
  zweites Mal, der andere läuft ("1 passed"); eigene Grenze je Test; `--zeitgrenze 0` schaltet ab; taskkill, das hängt, bricht nach 1 s ab
  (beide Skripte); **gegen PostgreSQL die Verklemmung vom 15.10.2026 mit allen drei `_run`**: die erste Aktion sperrt Zeile 1, committet
  (angehalten), braucht danach Zeile 2; die zweite sperrt Zeile 2, wartet auf Zeile 1 und wird abgelehnt, ohne zurückzurollen -- jedes `_run`
  endet (bis 1.8.110 hingen die Kopien in v363 und v365).
- Klicktest `klicktest_zeitbuchungen_liste` bei 00:30 Uhr: 24 von 24.
- Gegenproben (Regel 24): 8 von 8 rot -- Klicktest mit dem Fenster der Monteurin in UTC wie bis 1.8.110 ("Liste gekürzt: 500 von 502"
  erwartet, fehlt), Monteur-Zeiterfassung mit "heute" in UTC wie bis 1.8.86 (fehlt -- nur sichtbar, weil der Browser mit auf 00:30
  steht), keine Uhr (der hängende Test läuft durch), Test im parallelen Lauf noch einmal ausgeführt (achtmal abgestürzt, der andere Test
  lief nie), `_run` in v363 und v365 wie bis 1.8.110 (hängt, die Prüfung bricht nach 60 s ab), taskkill ohne Zeitlimit in beiden
  Skripten (60 s statt 1 s). Jede Datei byte-genau zurück (SHA-256).
- **Angepasste Erwartungen** (Regel 28): `klicktest_zeitbuchungen_liste` -- Soll "Monteurin Zeiterfassung: Hinweis" aus dem Berliner Tag statt
  dem UTC-Tag (altes Soll nachts veraltet seit 1.8.87); Aufbau: feste Uhr 00:30 und Browser-Uhr, `heute_utc` entfällt, `anna_tag` nur ≠ heute.


## Verbindungsprotokoll je Instanz, Ausgang hängender Anfragen (1.8.115)

Vorgabe vom 16.10.2026, Punkt 2: Klicktest-Werkzeug -- Verbindungsprotokoll von uvicorn (trace) je Instanz; Ausgang hängender Anfragen
(`loadingFailed`) im Netzprotokoll.

### Umsetzung 1.8.115

- **Verbindungsprotokoll** (`scripts/cdp_klicktest.py::log_konfiguration()`): jede Klicktest-Instanz startet uvicorn mit
  `--log-level trace` und einer eigenen Log-Konfiguration (`uvicorn-log.json` im Arbeitsordner). Die Spur -- „HTTP connection
  made/lost“ aus `uvicorn.error`, jede ASGI-Nachricht aus `uvicorn.asgi` (Start mit Methode und Pfad, Antwort-Kopf mit Status, Körper
  nur als `<n bytes>`, `http.disconnect`, Ende oder Ausnahme) und das Zugriffsprotokoll -- steht mit Zeitstempel in Sekunden seit 1970
  in `verbindungen.log`; Meldungen ab INFO bleiben in `server.err.log`, das Zugriffsprotokoll zusätzlich in `server.out.log`. Kopfzeilen
  (Cookies) und Inhalte ersetzt uvicorn selbst durch Platzhalter. Beide Startwege (mit fester Uhr im eigenen Prozess, sonst
  `python -m uvicorn`) nehmen sie.
- **Abgleich** (`Netzprotokoll.server_stand()`, `verbindungsprotokoll_lesen()`): unter jeder Anfrage eines Berichts (offen, beim
  Wechsel offen geblieben, fehlgeschlagen, Ausgang) steht, wo sie auf dem Server steht -- „Server: [41] angekommen +0,0 s, Antwort-Kopf
  200 +0,2 s, Körper gesendet +0,2 s, fertig +0,2 s“, „noch ohne Antwort-Kopf“, „Browser hat abgebrochen“, „Verbindung beendet“
  (vor dem Ende der Antwort) oder „nicht angekommen“. Zugeordnet wird die erste ASGI-Aufgabe mit derselben Methode und demselben Pfad,
  die frühestens 0,25 s vor dem Start im Browser begann (dieselbe Uhr) und vor dem Start der nächsten gleichen Anfrage im Browser -- im
  ersten Lauf des neuen Klicktests bekam eine nie gesendete, im Netz angehaltene Statusabfrage die Serverzeile der gleichen Abfrage der
  danach geöffneten Seite. Die Datei wird nur neu gelesen, wenn sie gewachsen ist. Am Ende eines nicht erfolgreichen Laufs nennt das
  Werkzeug ihren Pfad.
- **Ausgang** (`Netzprotokoll.ausgang_bericht()`): jede Anfrage, die ein Bericht als offen (oder beim Wechsel offen geblieben) gemeldet
  hat, bekommt ihren Ausgang nachgetragen, sobald der Browser ihn meldet -- „fertig, Status 200 nach 61,2 s“ oder „fehlgeschlagen:
  net::ERR_ABORTED (abgebrochen) nach 3,1 s“ (`Network.loadingFailed`, Dauer aus den Zeitstempeln des Browsers) -- in der nächsten
  Meldung (ein neuer Ausgang gilt als Änderung, die Meldung kommt nicht als „unverändert“) und am Ende jedes Laufs, auch eines
  erfolgreichen, dort mit den bis dahin offenen („noch offen nach …“). Jeder Ausgang einmal.

#### Festlegungen 1.8.115 (Bitte bestätigen)

Alle betreffen nur Werkzeug und Testablauf (Regel 28: der Bericht nennt ihre Zahl).

1. **Die Spur läuft in jedem Klicktest mit** (nicht nur auf Wunsch): `verbindungen.log` je Instanz im Arbeitsordner, mit Zeitstempel in Sekunden seit 1970.
2. **Meldungen ab INFO bleiben in `server.err.log`**, die Spur steht nur in `verbindungen.log`; das Zugriffsprotokoll in beiden.
3. **Zuordnung über Methode und Pfad: die erste ASGI-Aufgabe ab 0,25 s vor dem Start im Browser und vor dem Start der nächsten gleichen Anfrage im Browser** -- bei zwei gleichen Anfragen im selben Augenblick kann sie die andere treffen.
4. **„Verbindung beendet“ nur, wenn die Verbindung vor dem Ende der Antwort endete.**
5. **Ausgang nur für Anfragen, die ein Bericht als offen gemeldet hat** -- nicht für jede fehlgeschlagene; am Ende jedes Laufs (auch eines erfolgreichen) samt der noch offenen.

#### Nebenbefunde (nur gemeldet)

1. **Chrome meldet für eine im Netz angehaltene Anfrage (Fetch, Stufe Request) beim Wechsel des Dokuments kein Ende** -- weder
   `loadingFailed` noch `loadingFinished`; sie bleibt im Netzprotokoll „beim Wechsel offen geblieben“ und heißt am Ende „noch offen“. Das
   Werkzeug sagt das so, statt einen Ausgang zu erfinden.
2. **`klicktest_versandprotokoll` scheiterte im Endlauf von 1.8.114 am Binden seines SMTP-Testservers** („Socketadresse wird schon
   verwendet“): der Port wird beim Befüllen gewählt und erst in `pruefen()` belegt -- dazwischen kann ihn ein anderer Prozess nehmen (dort
   liefen drei Klicktests und ein Testlauf daneben). Einzeln nachgelaufen 45 von 45. Dasselbe Muster haben vermutlich die übrigen Klicktests
   mit SMTP-Empfänger im Skript.

#### Tests und Prüfung

- Neu `tests/test_v420_klicktest_verbindungen.py` (11 Tests): ein echter uvicorn (Kindprozess, kleine ASGI-App) mit der Log-Konfiguration des
  Werkzeugs -- die Spur steht mit Zeitstempel in der Datei, ohne Körper und Kopfzeilen, INFO weiter auf stderr; eine fertige und eine
  nach 0,5 s verlassene Anfrage gelesen; `server_stand()` für fertig, verlassen („Verbindung beendet“) und nicht angekommen; ein Bericht
  mit Serverzeile unter der offenen Anfrage; Ausgang nach `loadingFailed` (einmal), spät fertig mit Status und Dauer, nie gemeldet ohne
  Ausgang, Ende des Laufs mit noch offenen, neuer Ausgang ändert die Meldung; Start der Instanz mit trace auf beiden Wegen.
- Gegenproben (Regel 24): Start ohne trace, ASGI-Spur nicht in der Datei, offene Anfragen nie vorgemerkt -- alle erwarteten Prüfungen
  rot, jede Datei byte-genau zurück (SHA-256).
- Neu Klicktest `scripts/klicktest_verbindungsprotokoll.py` (15 Prüfungen, echter Chrome und uvicorn): `verbindungen.log` im
  Arbeitsordner; Statusabfrage der Kundenakte im Netz angehalten -- im Bericht offen, nicht gesendet, „Server: nicht angekommen“;
  fortgesetzt -- Ausgang „fertig, Status 200“ mit Serverzeile (angekommen, Antwort-Kopf 200, fertig), einmal; am Netz gescheitert
  (`Fetch.failRequest`) -- Ausgang „fehlgeschlagen: net::ERR_CONNECTION_RESET“ (`loadingFailed`), nie angekommen, auch nicht über die
  gleiche Anfrage der nächsten Seite; Seitenwechsel während angehalten -- am Ende „noch offen“. Der erste Lauf fand die falsche Zuordnung
  (oben) und dass Chrome für eine im Netz angehaltene Anfrage beim Seitenwechsel kein Ende meldet (Nebenbefund 1). 15 von 15; dazu
  `klicktest_anmelden` mit dem neuen Werkzeug 69 von 69, `verbindungen.log` mit 2431 Zeilen.
- Ein vierter Gegenprobenfall (Zuordnung ohne Obergrenze) ist rot wie erwartet; zusammen 4 Fälle, 12 erwartete rote Prüfungen.
- **Angepasste Erwartungen** (Regel 28): `test_v400::test_a_document_change_keeps_the_open_requests_of_the_old_document_until_the_next_one`
  -- altes Soll: nach dem späten Ende der beim Wechsel offen gebliebenen Abmeldung nur „keine offenen Anfragen“ und der Fehlschlag; neues
  Soll: dazu einmal „Ausgang zuvor als offen gemeldeter Anfragen: 1 … -> fertig, Status 200 nach 0,6 s“, beim nächsten Bericht wie bisher.


## JS-Ausnahmen in node-Tests, Planungsvorschlag mit echtem Dienst (1.8.116)

Vorgabe vom 16.10.2026, Punkt 5: `test_v405` (Planungsvorschlag) prüft nichts -- Testattrappe wie der echte Dienst, mit Gegenprobe.
Muster: eine JS-Ausnahme in einem node-Test lässt den Test scheitern; was dadurch rot wird, ist ein Befund und wird behoben.

### Befund

`test_namen_im_planungsvorschlag_bleiben_text` war grün, ohne etwas zu prüfen: die Attrappe (`FAKE_DOM` in `tests/test_v334_auswahl_restfaelle.py`)
kannte `element.remove()` nicht; `speichern()` nimmt nach jedem gelungenen Speichern den Hinweis „Anmeldung abgelaufen“ weg
(`_dkAnmeldungAbgelaufen(false)`) und scheiterte mit „TypeError: el.remove is not a function“; `calculateSuggestion()` fing die Ausnahme und
schrieb ihren Text in den Hinweis -- darin stand kein `<img`, der Test war grün. Die Antwort des Dienstes war zudem erfunden.

### Umsetzung 1.8.116

- **Fänger** (`tests/node_lauf.py`): jeder node-Lauf eines Tests bekommt einen Vorspann -- ein Worker-Thread verbindet sich mit dem
  Inspector des Hauptthreads (`inspector.Session.connectToMainThread()`), hält bei jeder Ausnahme an, auch einer gefangenen
  (`Debugger.setPauseOnExceptions` „all“), merkt sie sich in einem gemeinsamen Speicher und lässt weiterlaufen. Am Ende meldet der Vorspann
  jeden Programmfehler (TypeError, ReferenceError, SyntaxError, RangeError, URIError, EvalError) auf stderr, der Test scheitert mit
  `JsAusnahme` (Klasse, Funktion, Zeile, Text). Eine gewollte Ausnahme der Seite ist ein `Error` und bleibt erlaubt; Ausnahmen in node
  selbst zählen nicht. `_node()` (test_v314) und test_v338 laufen darüber; `test_jeder_node_lauf_geht_ueber_node_lauf` hält das per AST fest
  (Ausnahme: die reine Syntaxprüfung in test_v398).
- **Was dadurch rot wurde** (Befunde, behoben): fünf Tests in drei Dateien. (1) Die Attrappe kannte `remove()` nicht (Planungsvorschlag);
  jetzt entfernt `remove()` das Element wie im Browser. (2) `seite()` band immer dieselben sechs Bausteine ein und nie `_fehlertext.html`:
  jede Seite, die `fehlerText()` nutzt, scheiterte im Test bei jeder abgelehnten Antwort an „fehlerText is not defined“ (Kundenakte,
  `test_kunden_kategorie_ohne_still_vorgewaehlte_vorgabe`) -- jetzt genau die Bausteine, die die Seite selbst einbindet (`eingebunden()`,
  auch über Teilvorlagen), wie im Browser. (3) `istLokalesZiel()` fängt bei kaputter Prozentkodierung absichtlich den `URIError` von
  `decodeURIComponent` (Angriffstabelle in test_v401) -- erlaubt mit Grund. (4) Der Netzfehler „TypeError: Failed to fetch“ (so meldet ihn
  `fetch()`, und der Baustein beim Hochladen ebenso) -- erlaubt mit Grund (test_v404). (5) Die Attrappe in test_v338 wirft absichtlich
  einen SyntaxError (Antwort ohne JSON) -- dort erlaubt.
- **Planungsvorschlag** (`test_v405::test_namen_im_planungsvorschlag_bleiben_text`): die Antwort kommt vom echten Dienst
  (`POST /api/planning/suggestion` mit einer abwesenden Mitarbeiterin und einem Feiertag, beide mit `<img onerror>` im Namen); der Test
  setzt die Felder der Seite, prüft, dass die Seite genau diese Werte schickt, dass der Hinweis gezeichnet ist (Name und Feiertag als
  Text), kein `<img`, und dass das vorgeschlagene Ende übernommen ist.

#### Festlegungen 1.8.116 (Bitte bestätigen)

Alle betreffen nur den Testablauf (Regel 28: der Bericht nennt ihre Zahl).

1. **Programmfehler sind TypeError, ReferenceError, SyntaxError, RangeError, URIError, EvalError -- auch gefangen**; ein `Error` (api() bei 4xx/5xx, zahlLesen(), Zeitlimit) bleibt erlaubt.
2. **Erlaubt sind nur Fälle mit Grund**: `istLokalesZiel`/URIError, „TypeError: Failed to fetch“ überall, je Test eine Attrappe, die absichtlich wirft (`erlaubt=`).
3. **`seite()` bindet genau die Bausteine ein, die die Seite einbindet** (auch über Teilvorlagen), aus `BAUSTEINE` samt `_fehlertext.html`.
4. **Die Attrappe entfernt ein Element mit `remove()`**; ein späteres `getElementById` legt es wie bisher neu an.
5. **Der Fänger läuft über den Inspector in einem Worker-Thread**, als Vorspann vor jedem Skript, Rückgabecode 97 -- kein npm-Paket.

#### Nebenbefunde (nur gemeldet)

1. **Planungsvorschlag für Büro – Auftrag zeigt „Name (undefined)“**: der Server entfernt für diese Rolle `type` aus den Abwesenheiten
   (`app/routers/planning.py::_redact_suggestion_absences()`), `planning.html::calculateSuggestion()` hängt ihn trotzdem an.

#### Tests und Prüfung

- Neu `tests/test_v421_node_ausnahmen.py` (9 Tests): gefangener TypeError, ReferenceError im async-Ablauf, ungefangener Fehler scheitern
  mit Klasse, Funktion und Zeile; ein Error bleibt erlaubt, ein URIError außerhalb von `istLokalesZiel` nicht; die erlaubten Fälle mit
  Grund; `require` eines fehlenden Moduls (node intern) zählt nicht; die Ausgabe bleibt unverändert; jeder node-Lauf über
  `tests/node_lauf.py` (AST) samt Probe des Scanners.
- Alle 1158 node-basierten Tests (23 Dateien) mit dem Fänger grün, nachdem die fünf Befunde behoben bzw. mit Grund erlaubt sind.
- Gegenproben (Regel 24): 4 Fälle, alle erwarteten Prüfungen rot, jede Datei byte-genau zurück (SHA-256) -- Attrappe ohne `remove()`
  (Planungsvorschlag rot mit „JS-Ausnahme … TypeError in _dkAnmeldungAbgelaufen“), Planungsvorschlag ohne `esc()` (rot: `<img` im
  Hinweis), Fänger aus (fünf Tests in test_v421 rot), die sechs Bausteine von bisher ohne `_fehlertext.html` (Kundenkategorie rot mit
  „ReferenceError … fehlerText is not defined“).
- **Angepasste Erwartungen** (Regel 28):
  - `test_v405::test_namen_im_planungsvorschlag_bleiben_text` -- altes Soll „kein `<img` im Hinweis“ (mit erfundener Antwort, ohne Felder);
    neues Soll „Antwort vom echten Dienst, die Seite schickt die Werte der Felder, Hinweis gezeichnet mit Name und Feiertag als Text, kein
    `<img`, Ende übernommen“.
  - `test_v334::seite()` -- Aufbau: die eingebundenen Bausteine statt fester sechs; `FAKE_DOM` mit `remove()`.
  - `test_v314::_node()`, `test_v338::_messages()` (node-Lauf) -- Aufbau: über `tests/node_lauf.py`; test_v338 erlaubt den SyntaxError
    seiner Attrappe.
