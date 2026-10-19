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

## Strukturtests für Basis-Templates und Makros (1.8.123)

Vorgabe vom 17.10.2026, Stufe 0a des Redesigns (übernommen wie gegeben): „Strukturtests fit machen für Basis-Templates und Makros.
Vorlagen und App-Code bleiben unverändert, nur Tests ändern sich. Die Scanner (vorlagen_js, vorlagen_html, vorlagen_zahlen,
vorlagen_navigation) und die node-Attrappe sollen künftig auch erfassen: 1. Vorlagen in Unterordnern von app/templates/. 2. Seiten mit
{% extends %}: geprüft wird die zusammengesetzte Seite (Basis-Template plus Blöcke der Seite). 3. Makros ({% macro %}, {% import %},
{% from … import %}, {% call %}): das HTML im Makro wird geprüft. 4. Der _speichern-Test akzeptiert das Include auch im Basis-Template
der Seite. 5. Die node-Attrappe bindet auch die Bausteine des Basis-Templates ein, in derselben Reihenfolge wie im Browser. Gegenprobe:
Für jeden Scanner einen Test mit eigenen Fixture-Vorlagen außerhalb von app/templates, der beweist, dass ein Verstoß erkannt wird, wenn
er (a) in einem Makro, (b) in einem Unterordner, (c) in einem Basis-Template steckt. Jede Gegenprobe muss vor der Scanner-Änderung rot
sein. Bestehende Tests bleiben grün ohne geänderte Erwartungen.“ Anlass: der Befund zum Frontend vom selben Tag (kein Basis-Template,
alles CSS und JS inline, 53 Seiten; die Scanner sahen nur die oberste Ebene und nur `{% include %}`).

### Befund

- Die Scanner lasen nur `app/templates/*.html` und setzten nur `{% include "…" %}` ein; `{% extends %}`, `{% import %}` und
  `{{ makro() }}` wurden zu Leerzeichen. Die Listen der Vorlagen in test_v398, test_v399 und test_v400 kamen aus `glob("*.html")`.
- Ein Verstoß, der erst in der zusammengesetzten Seite einer ist, blieb ungesehen: ein Handler im Makro oder im Basis-Template, der eine
  Funktion der Seite ruft; ein Zahlenfeld im Basis-Template, das der Block der Seite roh liest (und umgekehrt); ein Baustein, den nur
  das Basis-Template einbindet (die Attrappe ließ ihn weg -- „fehlerText is not defined“).
- Das Einsetzen las auch Jinja-Kommentare: der Kommentar in `_topbar.html` nennt `{% include "_sidebar.html" %}` wörtlich, die Scanner
  setzten die Seitenleiste dort ein -- in den 42 Seiten mit Topbar stand sie doppelt im Zusammenhang. Jinja setzt in einem Kommentar
  nichts ein. An keinem Fund änderte das etwas (dieselben Stellen, je Stelle einmal gemeldet).
- Die Attrappe ordnete die Bausteine nach der Liste `BAUSTEINE`, nicht nach der Seite.

### Umsetzung 1.8.123

- **Zusammensetzen** (`tests/vorlagen_js.py::zusammensetzen(name, mit_includes=True, wurzel=None)`): die Seite so, wie Jinja sie
  zeichnet -- das Basis-Template (auch über mehrere Stufen) mit den Blöcken der abgeleiteten Vorlagen (nach Namen, verschachtelt,
  `{{ super() }}` über alle Stufen), `{% include %}` (auch ein Include, das selbst erbt), und für `{% import %}`/`{% from … import %}` die
  `{% macro %}`-Blöcke der Datei an der Stelle des Imports (je Datei einmal, ihre eigenen Importe mit). Die Herkunft nennt je Abschnitt
  Datei und Stelle, jede beteiligte Datei mit einer Marke der Länge 0. `vorlage_mit_includes()` und `skript_der_vorlage()` laufen
  darüber. `seitentext()`/`seitenskripte()`: dasselbe ohne eingesetzte Includes -- was die Vorlage selbst samt Basis und Makros
  beiträgt; ohne extends und Import der Dateitext.
- **Was sich nicht auflösen lässt, ist rot** (`VorlagenFehler`): Name aus einer Variablen oder Liste, zweites oder bedingtes extends,
  ein Block zweimal, ein Tag ohne Ende, Schleifen über extends (über include wie bisher `JsFehler` „Include-Schleife“).
- **Listen**: `alle_vorlagen(wurzel)` (auch Unterordner, Namen wie Jinja: „teile/x.html“), `seiten(wurzel)` (keine andere Vorlage
  bindet sie ein, erweitert oder importiert sie, Name nicht mit „_“), `vorlagen_verweise()`, `basis_kette()`, `ort()` (Datei und
  Zeile einer Stelle).
- **vorlagen_html**: `alle_vorlagen()` aus `vorlagen_js`; `zusammenhaenge()` zählt extends und import wie include -- ein
  Basis-Template und eine Makro-Datei werden im Zusammenhang der Seite gelesen, die sie nutzt.
- **vorlagen_zahlen**: der Scanner liest je Vorlage ihren Seitentext (Markup und Skripte samt Basis und Makros), ein Fund nennt die
  Datei und Zeile, in der er steht; `alle_funde()` je Stelle einmal; `ohne_einbindung()` über `seiten()` (neu, auch in test_v414).
- **vorlagen_navigation**: je Vorlage ihr Seitentext; die Stelle eines Handlers in seiner Datei.
- **_speichern-Test** (test_v398): wer `lesen()`/`speichern()` nutzt, bindet den Baustein selbst oder in einem seiner Basis-Templates
  ein; ein Basis-Template darf ihn für eine Vorlage einbinden, die von ihm erbt und ihn nutzt.
- **node-Attrappe** (test_v334): `eingebunden()` aus der zusammengesetzten Seite (ein Include im Kommentar zählt nicht),
  `bausteine_der_seite()` in der Reihenfolge ihrer Skripte in der Seite -- `_links.html` bindet `_weiterleitung.html` vor dem eigenen
  Skript ein, `_weiterleitung.html` läuft zuerst.
- **Wächter** `test_kein_scanner_liest_nur_die_oberste_ebene`: kein `glob("*.html")` in den Scannern und ihren Tests.

#### Festlegungen 1.8.123 (alle bestätigt am 17.10.2026; 1, 6 und 9 mit Ergänzungen, umgesetzt in 1.8.124)

Alle betreffen nur den Testablauf (Regel 28: der Bericht nennt ihre Zahl).

1. **Makros an der Stelle des Imports, nicht je Aufruf**: je importierte Datei einmal ihre `{% macro %}`-Blöcke. Was ein Aufruf
   hineinreicht (`{{ feld(typ="number") }}`), sieht der Scanner nicht (wie jedes `{{ … }}`); geprüft wird das HTML im Makro.
2. **Importe einer abgeleiteten Vorlage außerhalb ihrer Blöcke** stehen vor dem Text des Basis-Templates; was sie sonst außerhalb ihrer
   Blöcke hat, fehlt -- wie bei Jinja.
3. **Jinja-Kommentare zählen nicht**, auch nicht ein Include darin -- wie bei Jinja.
4. **Nicht auflösbar ist rot** (`VorlagenFehler`), nicht still übergangen.
5. **vorlagen_zahlen und vorlagen_navigation lesen den Seitentext** (mit Basis und Makros, ohne Includes -- eine Teilvorlage bleibt wie
   bisher eigene Datei); ein Basis-Template wird zusätzlich für sich gelesen, ein Fund je Stelle einmal gemeldet.
6. **Seite** = keine andere Vorlage bindet sie ein, erweitert oder importiert sie, Name nicht mit „_“; vorlagen_html liest Basis und
   Makro-Datei im Zusammenhang der Seite, die sie nutzt.
7. **_speichern-Test**: Include selbst oder in einem Basis-Template; ein Basis-Template nur, wenn es selbst oder eine Vorlage, die von ihm
   erbt, den Baustein nutzt.
8. **node-Attrappe**: Bausteine in der Reihenfolge ihrer Skripte in der zusammengesetzten Seite, je Baustein einmal.
9. **Die Liste der Vorlagen kommt aus `vorlagen_js.alle_vorlagen()`**, der Wächter in test_v428 verbietet `glob("*.html")` in den
   Scannern und ihren Tests.

#### Nebenbefunde (nur gemeldet)

1. **Weitere Strukturtests lesen nur die oberste Ebene** (`glob("*.html")`): test_v254 (Topbar), test_v313, test_v328 (Links im
   JavaScript), test_v333, test_v390, test_v405, test_v423, test_v424, test_v426 -- eine Vorlage in einem Unterordner prüfen sie nicht.
   **Und Tests, die ein Include wörtlich in der Seite verlangen**: test_v254 (Topbar neben der Seitenleiste), test_v269 und test_v272
   (Monteurs-Kopfzeile), test_v313, test_v333 (`_auswahl.html`), test_v337 (`_unterschrift.html`), test_v390 (`_berlin_date.html`),
   test_v397, test_v401 (`_weiterleitung.html`) -- steht das Include künftig im Basis-Template, melden sie die Seite fälschlich.
   Vorschlag: Stufe 0b vor dem ersten Basis-Template, mit `alle_vorlagen()`, `seiten()` und der Herkunft aus `zusammensetzen()`, je
   mit Gegenprobe.

#### Tests und Prüfung

- Neu `tests/test_v428_strukturtests_basis_und_makros.py` (39 Tests): die Gegenproben unten; das Zusammensetzen gegen echtes Jinja
  (zwei Basis-Templates, verschachtelte Blöcke, `super()` über zwei Stufen, Include im Block, das selbst erbt, Include im Kommentar,
  Text außerhalb der Blöcke -- ohne Kommentare zeichengleich, jede Herkunft zeigt auf ihre Datei); `seitentext()`; Makros an der Stelle
  des Imports (je Datei einmal, Makro ruft Makro einer zweiten Datei, Text außerhalb der Makros fehlt); `seiten()`, Unterordner,
  `basis_kette()`; sieben nicht auflösbare Formen und zwei Schleifen rot.
- **Gegenproben** (je Scanner vier Fälle: „direkt“ in einer Datei -- fand der Scanner schon, die Probe enthält etwas Erkennbares --,
  Makro, Unterordner, Basis-Template; nur Schnittstellen von vor 1.8.123), Lauf vor und nach der Änderung der Scanner:

  | Scanner | direkt | (a) Makro | (b) Unterordner | (c) Basis-Template |
  |---|---|---|---|---|
  | vorlagen_js (Anfrage außerhalb, test_v400) | grün / grün | rot / grün | rot / grün | rot / grün |
  | vorlagen_html (ohne esc(), Jinja im on…) | grün / grün | rot / grün | rot / grün | rot / grün |
  | vorlagen_zahlen (roh, type="number") | grün / grün | rot / grün | rot / grün | rot / grün (beide Richtungen) |
  | vorlagen_navigation | grün / grün | rot / grün | rot / grün | rot / grün (mit `super()`) |

  Dazu, vorher rot und nachher grün: Attrappe mit Baustein nur im Basis-Template („fehlerText is not defined“) und mit Reihenfolge
  („Cannot access 'FEHLER_PRAEFIX' before initialization“); `_speichern.html` im Basis-Template genügt (Seite und Basis); zwei
  Fehlalarme für ein Basis-Template in vorlagen_zahlen (`ohne_einbindung()`, test_v414); der Wächter (sechs Funde: vorlagen_html,
  vorlagen_zahlen, vorlagen_navigation, test_v398, test_v399, test_v400). Vorher und nachher grün (bleiben rot erkannt): Seite ohne
  Include und ohne Basis mit Include, Basis mit Include ohne nutzende Vorlage, Seite im Unterordner ohne Include. Vorher 20 rot und 7 grün,
  nachher 27 grün.
- **Abzug aller Scanner-Ausgaben** über die 74 echten Vorlagen vor und nach dem Umbau (899 Einträge, Skript im Scratchpad): alle Funde
  aller vier Scanner gleich (ungeschützt, Handler, Links, Jinja, Zahlen, ohne Einbindung, Navigationen, Schreibstellen je Stelle,
  Anfragen außerhalb in den Seiten). Unterschiede nur: 43 Vorlagen ohne die zweite Kopie der Seitenleiste aus dem Kommentar (Text,
  Schreibstellen, Elemente -- je Stelle dieselben, nur nicht mehr doppelt); `_topbar.html` für sich ohne `_sidebar.html`; 30 Seiten
  mit anderer Reihenfolge der Bausteine in der Attrappe (dieselbe Menge). Das neue Zusammensetzen gegen das alte: 31 Vorlagen
  zeichengleich, 43 nur ohne den Kommentar-Include anders; `seitentext()` gleich dem Dateitext bei allen 74; `seiten()` = die 53 Seiten.
- **Gegenprobe der Aufbau-Tests** (Plugin im Scratchpad, nichts unter `app/` geändert): `super()` nicht eingesetzt → 2 rot; Kommentare
  nicht ausgeblendet → 1 rot (zuerst grün: der Kommentar stand in der Probe außerhalb der Blöcke, wo Jinja ohnehin nichts zeichnet --
  Test nachgeschärft, Kommentar ins Basis-Template); Makros nicht eingesetzt → 5 rot.
- **Angepasste Tests** (Regel 28) -- nur Aufbau, keine Erwartung:
  - test_v398 `VORLAGEN`, test_v399 `VORLAGEN`, test_v400 `_alle_funde()` -- Aufbau: Liste aus `vorlagen_js.alle_vorlagen()` statt
    `glob("*.html")`.
  - test_v398 `test_templates_using_the_baustein_include_it` -- Aufbau: Include auch im Basis-Template; das Soll für Vorlagen ohne
    extends unverändert (nutzt ⇔ bindet selbst ein), Meldung „… weder selbst noch über ein Basis-Template ein“.
  - test_v334 `eingebunden()`, `seite()` -- Aufbau: aus der zusammengesetzten Seite, Bausteine in Skript-Reihenfolge (neu
    `bausteine_der_seite()`).
  - test_v414 `test_jede_seite_mit_zahlenfeld_bindet_den_baustein_ein` -- Aufbau: über `vorlagen_zahlen.seiten()` statt aller Vorlagen
    ohne „_“.

## Strukturtests, Stufe 0b (1.8.124)

Vorgabe vom 17.10.2026 (übernommen wie gegeben): „Stufe 0b des Redesigns. Nur Tests ändern sich, Vorlagen und App-Code bleiben
unverändert. Festlegungen 1.8.123 sind bestätigt, 1, 6 und 9 mit den Ergänzungen 2 bis 4: 1. Die neun Strukturtests v254, v313, v328,
v333, v390, v405, v423, v424 und v426 auf alle_vorlagen(), seiten() und zusammensetzen() umstellen. Die neun Tests, die ein Include
wörtlich in der Seite verlangen, akzeptieren es auch im Basis-Template (wie bei _speichern). 2. Wächter (zu 9): prüft alle Dateien unter
tests/ statt nur LESER und erkennt jedes Auflisten des Vorlagenordners an alle_vorlagen() vorbei (glob, rglob, iterdir, os.listdir).
3. Seiten-Abgleich (zu 6): Ein Test stellt sicher, dass seiten() genau die Vorlagen enthält, die irgendwo in app/ per TemplateResponse
ausgeliefert werden. 4. Makro-Regel (zu 1): Kein Makro-Parameter darf in type=, on…= oder href= landen. Was die Scanner prüfen, steht
fest im Makro oder wörtlich in der Seite (über {% call %}). Wächter-Test dafür, als neue Festlegung ins Archiv. Gegenprobe: Für 2, 3 und
4 je ein Fixture-Verstoß, der vorher unerkannt blieb und jetzt rot wird. Für 1 ein Vorher/Nachher-Abzug aller Funde der neun Tests an den
echten Vorlagen, der unverändert sein muss. Bestehende Erwartungen bleiben unverändert.“

### Umsetzung 1.8.124

- **Die neun Strukturtests** lesen die Vorlagen über `vorlagen_js.alle_vorlagen()`; je Test liefert eine Hilfsfunktion die Funde, der
  Test prüft dieselbe Erwartung wie bisher: v254 `_seitenleiste_ohne_topbar()` (Seiten aus `seiten()`, Seitenleiste und Topbar in der
  zusammengesetzten Seite), v313 `_seiten_mit_zeitliste()`, v328 `_vorlagen_links()`, v333 `_auswahl_nutzer()`, v390 `_fundstellen()`/
  `_verbotene()`/`_helfer_nutzer()`, v405 `_escaping_funde()`, v423 `_hidden_vorlagen()`, v424 `_vorhanden()`, v426 `_ist_markup()`.
- **Include auch im Basis-Template**: `vorlagen_js.bindet_ein(name, baustein)` -- das Include selbst oder in einem Basis-Template der
  Kette, nach den Tags (ein Include im Kommentar zählt nicht), nicht über eine Teilvorlage (wie bisher). Genutzt in v254 (über die
  zusammengesetzte Seite), v269, v272, v313, v333, v337, v390, v397 und v401 (`_seiten_mit_sicheresziel()`, Vorlagen ohne „_“ im
  Dateinamen).
- **v423**: die Regel `.hidden{display:none}` zählt, wo die Vorlage gezeichnet wird -- in ihrer zusammengesetzten Seite (auch im
  Basis-Template oder einer eingebundenen Teilvorlage), für eine Teilvorlage, ein Basis-Template oder eine Makro-Datei in jeder Seite, die
  sie nutzt. Das CSS wandert mit dem Redesign ins Basis-Template; je Datei hätte der Test dann jede Seite gemeldet.
- **Wächter** (`test_v428::test_kein_scanner_liest_nur_die_oberste_ebene`, `vorlagen_auflistungen()`): jede Datei unter `tests/`, per AST;
  der Vorlagenordner ist ein Text „templates“ bzw. „…/app/templates“, ein Name oder Attribut `TEMPLATES`/`TEMPLATES_DIR`/`templates`
  oder ein Name, dem so etwas zugewiesen wird (in der Datei); gemeldet wird glob, rglob, iterdir, walk, scandir auf ihm oder mit einem
  Muster `*.html`, `os.listdir`/`os.scandir`/`os.walk`, `glob.glob`/`iglob`, `list_templates()` auf ihm -- außer in
  `vorlagen_js.alle_vorlagen()`. Die Liste `LESER` ist weg.
- **Seiten-Abgleich** (`test_v429::test_seiten_sind_genau_die_ausgelieferten_vorlagen`, `ausgelieferte_vorlagen()`): jeder Aufruf von
  `TemplateResponse` unter `app/` per AST, auch als Argument (`run_in_threadpool(templates.TemplateResponse, …)`); der Name aus `name=`,
  sonst das Argument nach `request`; ein Text, `a if b else c`, ein Name über seine Zuweisungen in derselben Funktion -- sonst „nicht
  auflösbar“ (rot). `seiten()` und die ausgelieferten Namen müssen in beide Richtungen gleich sein. Heute 53 = 53.
- **Makro-Regel** (`vorlagen_html.jinja_handler()`, damit in `alle_funde("jinja")` und `test_v407::test_keine_jinja_werte_in_on_attributen`,
  dazu `test_v429::test_kein_makro_parameter_in_type_on_href`): ein kleiner Tag-Leser geht durch den Inhalt jedes Makros (auch
  verschachtelt, `vorlagen_js.makro_bereiche()`).

#### Festlegungen 1.8.124 (alle bestätigt am 17.10.2026)

Alle betreffen nur den Testablauf (Regel 28: der Bericht nennt ihre Zahl).

1. **Makro-Regel** (die neue Festlegung zu 1.8.123 Nr. 1): in einem Makro steht in `type=`, `on…=` und `href=` kein Jinja -- weder
   `{{ … }}` (auch nicht `caller()`) noch `{% … %}` --, an der Stelle eines Attributs kein `{{ … }}` (`<div {{ attrs }}>`), in keinem
   Attributnamen Jinja (`on{{ x }}=`). Ein `{% if %}` um feste Attribute ist erlaubt (sie stehen wörtlich da). Andere Attribute (`id`,
   `class`, `value`, `data-…`) dürfen Parameter tragen. Ein `on…="…{{ … }}…"` meldet wie bisher die Prüfung der on…-Attribute, einmal.
2. **Wächter**: jede Datei unter `tests/`, per AST; Vorlagenordner und gemeldete Aufrufe wie oben; einzige Ausnahme
   `vorlagen_js.alle_vorlagen()`. Ein Name gilt dateiweit als Vorlagenordner, sobald ihm irgendwo einer zugewiesen wird (Über-Annäherung).
3. **Seiten-Abgleich**: die Namen aus `TemplateResponse` wie oben; nicht auflösbar ist rot; Gleichheit in beide Richtungen.
4. **Include auch im Basis-Template** (`bindet_ein()`): selbst oder in der Kette der Basis-Templates, nach den Tags, nicht über eine
   Teilvorlage.
5. **v423**: die Regel `.hidden` zählt, wo die Vorlage gezeichnet wird (zusammengesetzte Seite; für Teilvorlage, Basis und Makro-Datei
   jede Seite, die sie nutzt).
6. **v254**: Seiten aus `seiten()`; Seitenleiste und Topbar in der zusammengesetzten Seite (auch über eine Teilvorlage).
7. **v401**: Vorlagen ohne „_“ im Dateinamen (in Unterordnern der Name der Datei, nicht der Pfad).

#### Nebenbefunde (nur gemeldet)

1. **Vier weitere wörtliche Include-Prüfungen für einzelne Seiten** (die Liste von 1.8.123 war unvollständig): test_v314 (Dashboard →
   `_berlin_date.html`), test_v338 (Auftragsseite → `_fehlertext.html`), test_v340 (Projektmappe → `_fehlertext.html`), test_v418
   (Projektmappe und Kundenakte → `_email_dispatch.html`). Wandert eines dieser Includes ins Basis-Template, werden sie rot -- dann auf
   `bindet_ein()` umstellen.
2. **test_v272** verlangt in den vier Monteursseiten `get_theme().accent_color` im eigenen `:root{`-Block -- wandert der Token-Block ins
   Basis-Template (Stufe 1), ist das eine echte Erwartung, keine Include-Frage.
3. **Zählfehler im Bericht zu 1.8.123, Frage 4**: der Musterabgleich traf in den neun Dateien 11 Stellen, nicht 12 (je eine, in v423 und
   v424 je zwei).

#### Tests und Prüfung

- Neu `tests/test_v429_strukturtests_stufe_0b.py` (27 Tests): Gegenproben Wächter (10 Formen) und Makro-Regel (7 Formen), je ein
  Negativtest; Makro-Regel an den echten Vorlagen; Seiten-Abgleich echt und mit vier Gegenproben samt Negativtest; `bindet_ein()`.
- **Gegenproben** (Fixture-Vorlagen und -Projekte unter tmp_path):
  - Wächter: alle 10 Formen vorher unerkannt (der Wächter von 1.8.123 lief durch: „DID NOT RAISE“), nachher rot mit Datei und Zeile --
    iterdir, os.listdir, rglob, glob außerhalb von LESER, glob über eine Variable, glob.glob, os.scandir, os.walk, list_templates(),
    iterdir in einer LESER-Datei.
  - Makro-Regel: alle 7 Formen vorher unerkannt (`alle_funde("jinja")` leer), nachher gefunden -- type=, href=, on…= mit `{% if %}`,
    `{{ attrs }}`, `on{{ ereignis }}=`, `href="{{ caller() }}"`, type= ohne Anführungszeichen.
  - Seiten-Abgleich: vier Formen (ausgeliefertes Basis-Template, Seite ohne Auslieferung, Name nicht auflösbar, ausgelieferte
    Teilvorlage) nachher rot, je nur dieser eine Befund. Vorher gab es keine solche Prüfung; die volle Suite von 1.8.123 lief in einer
    Wegwerf-Arbeitskopie mit einer verwaisten Seite `app/templates/waise.html` (Marker GEGENPROBE) -- Ergebnis im Bericht --, der neue
    Abgleich an einer Kopie von `app/` mit derselben Seite meldet sie („Seite, die app/ nirgends ausliefert: waise.html“).
- **Abzug aller Funde der neun Tests und der neun Include-Prüfungen** an den echten Vorlagen (Skript im Scratchpad: vorher die
  Berechnungen der Tests von 1.8.123 wörtlich, nachher die neuen Hilfsfunktionen): 16 Einträge, alle gleich. Bei v424 wich zuerst die
  Liste der Leseaufrufe ab -- ein Fehler im Abzugsskript (vorher als Liste mit einer Dublette, der Test nimmt eine Menge); die Menge ist
  gleich (42), die 88 Zahlenfelder ebenso.
- **Wächter am Stand von 1.8.123**: über die neun alten Testdateien findet er die 11 Stellen; über alle Dateien unter `tests/` heute
  keine.
- **Angepasste Tests** (Regel 28) -- nur Aufbau, keine Erwartung:
  - test_v254 `test_every_template_with_sidebar_also_includes_topbar` -- Aufbau: Seiten aus `seiten()`, Seitenleiste und Topbar in der
    zusammengesetzten Seite.
  - test_v313 `test_every_page_listing_time_entries_reads_total_and_shows_truncation_notice` -- Aufbau: `alle_vorlagen()`, Include über
    `bindet_ein()`.
  - test_v328 `_vorlagen_links()`, test_v405 `test_keine_vorlage_und_kein_modul_schaltet_das_escaping_aus`, test_v424
    `test_jedes_feld_und_jeder_leseaufruf_mit_grenzen_steht_genau_einmal_im_abgleich`, test_v426
    `test_keine_ist_menge_hat_eine_untergrenze_ueber_0` -- Aufbau: `alle_vorlagen()` statt `glob("*.html")`.
  - test_v333 `test_jede_seite_mit_auswahloptionen_bindet_den_helfer_ein`, test_v390 (drei Tests über `_vorlagen()`) -- Aufbau:
    `alle_vorlagen()`, Include über `bindet_ein()`.
  - test_v423 `test_jede_vorlage_mit_der_klasse_hidden_blendet_sie_aus` -- Aufbau: `alle_vorlagen()`, Regel in der zusammengesetzten
    Seite bzw. in den nutzenden Seiten.
  - test_v269 (zwei Tests), test_v272, test_v337, test_v397, test_v401 -- Aufbau: Include über `bindet_ein()`.
  - test_v428 `test_kein_scanner_liest_nur_die_oberste_ebene` -- Aufbau: jede Datei unter `tests/`, AST statt Muster über `LESER`.

## Strukturtests, Stufe 0c (1.8.125)

Vorgabe vom 17.10.2026 (übernommen wie gegeben): „Stufe 0c des Redesigns: Restarbeiten am Sicherheitsnetz. Vorlagen und App-Code bleiben
unverändert. 1. Die vier Include-Prüfungen v314, v338, v340 und v418 auf bindet_ein() umstellen. 2. Wächter: Kein Test prüft ein
Include per Textvergleich, nur über bindet_ein(). Gegenprobe mit Fixture; außerdem muss der Wächter die alten Fassungen der vier Tests
finden. 3. Klicktest-Wackler in cdp_klicktest._warte_auf() beheben (TCP-Selbstanschluss, solange Chrome noch nicht lauscht). Nachweis:
Der Fehler lässt sich vorher gezielt erzeugen und tritt danach nicht mehr auf. 4. Am Ende die Festlegungen 1.8.124 wörtlich ausgeben.
Noch nicht als bestätigt markieren.“

### Befund

- Textvergleiche auf ein Include unter `tests/` (der neue Wächter am Stand von 1.8.124): neben den vier genannten drei weitere --
  `test_v398::_bindet_den_baustein_ein()` (`'{% include "_speichern.html" %}' in …`, aus 1.8.123), `test_v269` Zeile 34
  (`_debounce.html` in der Monteurs-Kopfzeile) und `test_v254::test_mobile_header_does_not_include_topbar` (`"_topbar.html" not in …`
  gegen den Text von `_mobile_header.html` und `mobil.html`). Ein Textvergleich sieht ein Include im Basis-Template nicht und hält eines
  in einem Kommentar für echt.
- Klicktest-Wackler: `_freier_port()` band Port 0, das Betriebssystem wählte also aus dem Bereich der kurzlebigen Ports (hier
  49152–65535, `netsh int ipv4 show dynamicport tcp`) -- demselben, aus dem es die Quellports ausgehender Verbindungen nimmt. Fragt
  `_warte_auf()` einen solchen Port ab, solange dort niemand lauscht, und bekommt die Verbindung zufällig ihn als Quellport, verbindet
  sie sich mit sich selbst: die eigene Anfrage kommt als Antwort zurück. Gezielt erzeugt (Quellport = Zielport): roh kommt das Gesendete
  zurück, urllib wirft `http.client.BadStatusLine: GET /json/version HTTP/1.1` -- genau der Fehler aus dem Klicktest; `_warte_auf()` fing
  ihn nicht ab (keine `OSError`).

### Umsetzung 1.8.125

- **Include nur über `bindet_ein()`**: v314 (Dashboard → `_berlin_date.html`), v338 (Auftragsseite → `_fehlertext.html`), v340
  (Projektmappe → `_fehlertext.html`), v418 (Projektmappe und Kundenakte → `_email_dispatch.html`), v269 (`_debounce.html` in der
  Kopfzeile), v254 (keine Topbar: `not bindet_ein(…)` für Kopfzeile und `mobil.html`), v398 (`_bindet_den_baustein_ein()` über
  `bindet_ein(…, nur_selbst=True)`, der Zweig „nutzt“ über `bindet_ein()`). Neu `bindet_ein(…, nur_selbst=True)`: nur die Datei selbst.
- **Wächter** (`test_v430::test_kein_test_prueft_ein_include_per_textvergleich`, `include_textvergleiche()`): jede Datei unter `tests/`,
  per AST -- ein Include-Tag als Text (auch über eine Konstante der Datei) mit `in`/`not in`, als Argument von `count()`, `find()`,
  `index()`, `startswith()` u. a. oder als Muster eines `re`-Aufrufs; ein Vorlagenname („….html“) mit `in`/`not in` gegen eingelesenen
  Text (`read_text()` direkt, über eine Variable der Funktion oder eine Funktion der Datei, die Text aus `read_text()` zurückgibt).
- **Klicktest-Ports** (`scripts/cdp_klicktest.py`): `_kurzlebige_ports()` liest den Bereich (Windows `netsh`, Linux
  `/proc/sys/net/ipv4/ip_local_port_range`, sonst 49152–65535); `_freier_port()` wählt zufällig ab 20000 außerhalb davon und prüft mit
  `bind` (200 Versuche, sonst wählt das Betriebssystem, mit Hinweis). Dort kann eine Verbindung den abgefragten Port nie als Quellport
  bekommen. `_warte_auf()` behandelt `http.client.HTTPException` (BadStatusLine, RemoteDisconnected) als „noch nicht bereit“.

#### Festlegungen 1.8.125 (alle bestätigt am 19.10.2026)

Alle betreffen nur den Testablauf (Regel 28: der Bericht nennt ihre Zahl).

1. **Kein Include per Textvergleich**: was der Wächter als Textvergleich erkennt, wie oben; jede Datei unter `tests/`. Ein Vergleich
   ganzer Ausgaben (`text == '…{% include … %}…'`), Fixture-Vorlagen und Mengen aus der Herkunft sind keiner.
2. **`bindet_ein(…, nur_selbst=True)`** für „die Vorlage selbst bindet ein“ (v398: ein Basis-Template darf den Baustein nur für eine
   nutzende Vorlage einbinden).
3. **v254 „keine Topbar in der Monteursansicht“** heißt jetzt „nicht eingebunden, auch nicht über ein Basis-Template“ statt „nicht
   erwähnt“ (ein Kommentar mit dem Namen zählt nicht mehr).
4. **Klicktest-Ports**: zufällig ab 20000, außerhalb der kurzlebigen Ports, mit `bind` geprüft.
5. **`_warte_auf()`**: eine Antwort, die kein HTTP ist, heißt „noch nicht bereit“.

#### Nebenbefunde (nur gemeldet)

1. **Weitere Ports per Port 0** in Klicktests: `klicktest_anmelden._freier_port()` (auch von `klicktest_fremde_seite` genutzt; dort eine
   „fremde Adresse, an der niemand lauscht“, die Chrome aufruft) und die SMTP-Empfänger in sieben Klicktests (Port gebunden, wieder frei
   gegeben, später neu gebunden). Ein Selbstanschluss ist dort ebenso denkbar (Chrome bzw. die ERP-Instanz als Client), bisher nicht
   beobachtet; nicht geändert (Auftrag: `_warte_auf()`). **Seit 1.8.126 behoben**: alle nehmen `_freier_port()` (Abschnitt
   „Bildgrundlage für das Redesign, Stufe 0d“).

#### Tests und Prüfung

- Neu `tests/test_v430_strukturtests_stufe_0c.py` (18 Tests): Wächter echt, 12 Gegenproben (die vier alten Fassungen wörtlich, `not in`,
  `count()`, Regex, Konstante, Leerraum-Steuerung, Vorlagenname gegen Text direkt, über eine Variable, über eine Hilfsfunktion) und ein
  Negativtest; Selbstanschluss gezielt erzeugt, `_warte_auf()` übersteht ihn, erkennt einen lauschenden Server, `_freier_port()` liegt
  außerhalb der kurzlebigen Ports.
- **Vorher** (vor jeder Änderung): Wächter rot mit acht Stellen -- die sieben oben und sein eigenes Suchmuster (seither zusammengesetzt);
  `test_der_selbstanschluss_laesst_sich_gezielt_erzeugen` grün (der Fehler lässt sich erzeugen), `test_warte_auf_uebersteht_einen_selbstanschluss`
  rot (`http.client.BadStatusLine: GET /json/version HTTP/1.1`), `test_freier_port_liegt_nicht_bei_den_kurzlebigen_ports` rot (Ports
  52550, 52551 … im Bereich 49152–65535). **Nachher**: alle 18 grün.
- **Alte Fassungen** (`a5be287`): der Wächter findet v314:94, v338:430, v340:407, v418:120, dazu v398:320, v269:34, v254:243 und 245; in
  den neuen Fassungen nichts.
- **Vorher/Nachher an den echten Vorlagen**: jeder umgestellte Textvergleich und `bindet_ein()` liefern dasselbe (v398 über alle 74
  Vorlagen, 54 mit Include).
- **Angepasste Tests** (Regel 28) -- nur Aufbau, keine Erwartung:
  - test_v314 `test_dashboard_requests_my_hours_for_the_berlin_month`, test_v338 `test_order_page_includes_the_shared_error_helper`,
    test_v340 `test_reiter_beteiligte_erst_suchen_dann_neu_anlegen`, test_v418 `test_projektmappe_und_kundenakte_zeigen_ihren_versand`,
    test_v269 `test_debounce_helper_included_exactly_once_via_mobile_header` -- Aufbau: Include über `bindet_ein()`.
  - test_v398 `test_templates_using_the_baustein_include_it` -- Aufbau: `bindet_ein()` (selbst: `nur_selbst=True`).
  - test_v254 `test_mobile_header_does_not_include_topbar` -- Aufbau: `not bindet_ein()`; Soll „nicht erwähnt“ wird „nicht eingebunden“
    (Festlegung 3; an den echten Vorlagen dasselbe Ergebnis).

## Bildgrundlage für das Redesign, Stufe 0d (1.8.126)

Vorgabe vom 17.10.2026 (übernommen wie gegeben): „Stufe 0d des Redesigns: Screenshot-Grundlage. Vorlagen und App-Code bleiben
unverändert. Vorab: Festlegungen 1.8.124 sind bestätigt. 1. Werkzeug auf Basis von cdp_klicktest: Testinstanz mit festen Testdaten und
fester Uhr, ganzseitige Screenshots von - jeder Seite aus seiten() (Detailseiten mit Datensätzen aus den Testdaten), dazu Login und
Sperrseite; - Büro-Rolle überall, Monteur-Rolle zusätzlich für die Monteursseiten, die Seiten mit Rollenweiche und den Einsatzbericht;
- je hell und dunkel, je 412 px und 1440 px Breite. Vor jedem Bild: Daten fertig geladen, Schriften bereit, Animationen und Textcursor
aus. 2. Abdeckungstest: Jede Seite aus seiten() steht in der Liste des Werkzeugs. 3. Vergleich zweier Läufe: je Bild die Zahl
abweichender Pixel und ein Differenzbild; Exit-Code ungleich 0 bei Abweichung. 4. Gegenproben: (a) Zwei Läufe auf demselben Commit
ergeben 0 abweichende Pixel. Was wackelt, mit Ursache melden, nicht wegmaskieren. (b) In einer Wegwerfkopie eine winzige CSS-Änderung an
einer einzigen Seite: Der Vergleich meldet genau deren Bilder. 5. Grundlage vom aktuellen Commit erzeugen, außerhalb von Git (Ordner in
.gitignore, Commit im Ordnernamen). Aufruf in CLAUDE.md dokumentieren. 6. klicktest_anmelden._freier_port() auf den Port-Helfer aus
cdp_klicktest umstellen. Bestätigen, dass der Helfer den Port vor der Rückgabe auf Belegung und Windows-Reservierungen prüft; falls
nicht, nachrüsten. Bericht: Anzahl Bilder, Laufzeit, Ordnergröße, Gegenproben, Grenzen (was nicht abgedeckt ist). Am Ende die
Festlegungen 1.8.125 wörtlich ausgeben, nicht als bestätigt markieren. Dann committen.“

### Befund

- **Was zwei Läufe unterscheiden würde**: die Uhr der Klicktests läuft „heute ab HH:MM“ -- jedes Datum auf einer Seite wäre an jedem Tag
  ein anderes; gespeicherte Zeitstempel (`datetime.utcnow()` beim Befüllen) tragen die echte Zeit (Verlauf, „angelegt am“); die
  Versionsnummer in der Seitenleiste und die Changelog-Seite ändern sich mit jedem Commit; `localStorage` (Thema, Seitenleiste);
  Animationen, Übergänge, der blinkende Textcursor, Fokus.
- **Rollenweichen**: `/time-tracking` und `/betriebsmittel/{id}` zeichnen für die Monteurin eine andere Vorlage
  (`time_tracking_field.html`, `operational_asset_field.html`), Checkliste und Checklisten des Auftrags dieselbe Vorlage mit `is_field`,
  `/` leitet sie auf `/mobil` um. Jede Seitenroute mit `_any_role_dep` (Konto, Mobil, Objekt mobil, Stundenzettel, Einsatzbericht,
  Checkliste, Checklisten des Auftrags, Zeiterfassung, Betriebsmittel) öffnet auch die Monteurin. **Nur Admin**: `/address-import`
  (`require_admin`) -- mit der Büro-Rolle wäre das Bild die Sperrseite (so im ersten Lauf, gefunden vom neuen Test).
- **Port-Helfer** (Punkt 6): `_freier_port()` prüfte mit `bind` auf 127.0.0.1. Das erkennt einen an 127.0.0.1 belegten Port (WinError
  10048) und einen von Windows reservierten (10013; hier 2121, 2869, 5357, 8094 und 8884, alle unter 20000 und damit nie Kandidat), aber
  **nicht** einen Port, an dem ein anderer Prozess auf 0.0.0.0 lauscht: daneben gelingt das Binden an 127.0.0.1 unter Windows
  (nachgestellt). `klicktest_anmelden._freier_port()` und die SMTP-Empfänger in sieben Klicktests banden Port 0 wie vor 1.8.125
  (Nebenbefund 1 von 1.8.125).

### Wackelquellen (Gegenprobe a), mit Ursache

Zwei volle Läufe am selben Stand ergaben zuerst 0 abweichende Pixel -- Zufall, wie sich zeigte. Gefunden wurden beide Quellen erst
bei Läufen mit `--nur` und bei Vergleichen über Zwischenstände.

1. **Reihenfolge im Verlauf** (vier Bilder): „Angebot geändert“ und „Projekt geändert“ aus `create_order_from_quote()` tauschten die
   Plätze. Ursache im App-Code: beide Änderungen liegen im selben Flush; `app/audit.py::before_flush` schreibt die Einträge in der
   Reihenfolge von `session.dirty`, das in SQLAlchemy 2.0.52 aus einem `set()` von `InstanceState` kommt (`IdentityMap._modified`) und
   nach Speicheradresse ordnet; der Verlauf ordnet gleich alte Einträge nach ID (`occurred_at desc, id desc`). Nachgestellt nur mit dem
   Befüllen, je Lauf ein neuer Prozess: zufälliger Hash-Seed 6 Läufe, 2:4 verteilt; `PYTHONHASHSEED=0` 6 Läufe, 3:3 -- die
   Adressen (ASLR), nicht der Hash-Seed. **In den Testdaten umgangen, nicht maskiert**: `befuellen()` setzt den Projektstatus vorher in
   einem eigenen Commit, der Flush ändert nur das Angebot (beide Einträge stehen weiter im Verlauf, in fester Reihenfolge); danach
   8 von 8 Läufen dieselbe Folge aller 237 Einträge (Prüfsumme über Art, ID, Aktion und Feld). Die App bleibt, wie sie ist (Vorschlag
   unten); ein künftiger Flush mit zwei geänderten Objekten in den Testdaten brächte die Quelle zurück.
2. **Kantenglättung des Texts** (alle Bilder einer Seite, im ganzen Text): mit `--nur verlauf` wich der Verlauf vom Verlauf eines vollen
   Laufs ab, bei gleichem Layout -- die farbigen Subpixel-Säume (ClearType/LCD-Text) waren anders stark (etwa `(61,154,226)` statt
   `(98,168,226)` an derselben Glyphe). Die Stärke hing davon ab, welche Seiten der Browser vorher gezeichnet hatte: mit dem Kalender
   davor gleich wie im vollen Lauf, als erste Seite anders. Volle Läufe besuchen die Seiten immer in derselben Folge und waren
   untereinander gleich; ein Vergleich mit einem Teillauf (`--nur`) wäre im ganzen Text rot gewesen. **Behoben an der Quelle**: Chrome
   zeichnet für die Bildgrundlage ohne LCD-Text (`--disable-lcd-text`, Graustufen); danach Verlauf allein und Kalender plus Verlauf
   gleich (bis auf Quelle 1, damals noch offen).

### Umsetzung 1.8.126

- **`scripts/bildgrundlage.py`**: `aufnehmen` (Vorgabe) und `vergleichen ALT NEU`. `AUFNAHMEN`: 53 Einträge mit Name, Vorlage, Adresse
  und Rollen -- 48 mit Büro, 10 mit Monteurin, Adressimport mit Admin, Anmeldeseite anonym, Sperrseite als Monteurin auf `/projects`;
  zusammen 60 Bilder je Thema und Breite, 240 je Lauf. Testdaten in `befuellen()`: Kunde mit Objekt und zwei Dachflächen, Projekt mit
  Angebot und Auftrag (Arbeitsvorbereitung, Team, Plantafel heute, Abschlag als Entwurf, Einsatzbericht mit Prüfpunkten und Befund,
  Checkliste, zwei Zeitbuchungen), zweites Projekt mit Angebot, Wartungsvertrag, Prüfvorlage, Betriebsmittel, Leistung, Termin,
  Eingangsrechnung, Betriebskosten, Anfrage, Aufgabe; Projektstatus vor dem Beauftragen (Wackelquelle 1). Danach jeder Zeitstempel
  (Spalte `DateTime`) auf die Uhr, außer `expires_at` (Ablauf der Sitzungen, gegen die echte Zeit geprüft) und Beginn und Ende des
  Termins (`BEWUSST_GESETZT`, aus der stehenden Uhr gesetzt). Chrome mit `--disable-lcd-text` (Wackelquelle 2). Je Bild: Thema über
  `prefers-color-scheme` (Emulation), Fenster 412 px als Mobilgerät bzw. 1440 px, Seite laden, bis keine Anfrage der Seite mehr
  unterwegs ist und seit 0,8 s keine fertig wurde, Schriften geladen; Fokus weg, oben, zwei Frames; Fensterhöhe auf die Seitenhöhe
  (mindestens 900, höchstens 16.000 px), bis sie bleibt; PNG. Bei jedem Laden `localStorage` leer und ein Stil gegen Animationen,
  Übergänge und Textcursor (`Page.addScriptToEvaluateOnNewDocument`). Geprüft je Bild: geladen und Status 200 (Sperrseite 403). Ordner
  `bildgrundlage/<kurzer Hash>` bzw. `…-geaendert`, `bilder.json` mit Seite, Vorlage, Adresse, Rolle, Thema, Breite, Höhe, Status,
  JS-Fehlern, Chrome-Version, Laufzeit.
- **Vergleich**: ein Pixel weicht ab, wenn einer der Kanäle R, G, B, A anders ist (keine Toleranz); bei anderer Größe zählt die Fläche,
  die nur in einem Bild liegt. Differenzbild: das neue Bild blass, Abweichungen rot, in `vergleich_<ALT>_<NEU>` neben NEU (bei gleichen
  Ordnernamen die der übergeordneten Ordner). Fehlende und neue Bilder werden genannt; Rückgabecode 1 bei jeder Abweichung, 0 nur bei
  Gleichheit.
- **Klicktest-Werkzeug** (`scripts/cdp_klicktest.py`): `uhr="JJJJ-MM-TT HH:MM"` ist eine stehende Uhr (Marke `…|fest`,
  `_uhr_einsetzen()` setzt `berlin_time._utc_now` auf den festen Zeitpunkt); `tab.browser_uhr_fest(ms)` lässt `Date` im Browser stehen,
  `k.uhr_ms()` liefert den Zeitpunkt; `KLICKTEST_ANZEIGE` (JSON) gibt der Instanz Versionsnummer und Changelog; `klicktest_main(…,
  zeitlimit_je_schritt=True, umgebung={…}, chrome_argumente=[…])`, `Wachhund.neu_starten()` über `tab.wachhund` -- unter einer
  Gegenprobe gelten die 2 min je Bild statt für den ganzen Lauf. **Port-Helfer**: `_bindbar()` auf 127.0.0.1 und 0.0.0.0,
  `_freier_port()` gibt nur einen Port zurück, der an beiden frei ist; `klicktest_anmelden`, `klicktest_fremde_seite` und die
  SMTP-Empfänger von `klicktest_bedenkenanzeige_versand`, `klicktest_behinderungsanzeige_versand`, `klicktest_protokoll_versand`,
  `klicktest_versandprotokoll`, `klicktest_versandverlauf`, `klicktest_vertrag_abschrift`, `klicktest_vertrag_festschreiben` nehmen ihn.
- `scripts/bildgrundlage_changelog.md` (fester Changelog der Instanz), `.gitignore` `/bildgrundlage/`, CLAUDE.md (Aufruf unter „Testen“).

#### Festlegungen 1.8.126 (alle bestätigt; Nr. 12 und 13 am 19.10.2026, die übrigen am 19.10.2026 mit Runde 1b)

Alle betreffen nur Werkzeug und Testablauf (Regel 28: der Bericht nennt ihre Zahl).

1. **Rollen der Bilder**: Büro – Finanzen für jede Seite mit Büro-Fassung (Büro – Auftrag öffnet die Finanzseiten und den
   Mitarbeiter-Editor nicht); die Monteurin auf jeder Seite, die sie öffnet (vom Test erzwungen, nicht nur Monteursseiten, Rollenweichen
   und Einsatzbericht -- dazu Konto, Checkliste, Checklisten des Auftrags); Admin nur für den Adressimport; anonym die Anmeldeseite; die
   Sperrseite als Monteurin auf `/projects`.
2. **Je Seite eine Fassung**: Detailseiten mit je einem Datensatz der Testdaten, das Stammdaten-Formular als „Mitarbeiterin bearbeiten“,
   die Suche mit `?q=Halle`; Seiten im Zustand nach dem Laden (erster Reiter, nichts aufgeklappt, Entwürfe statt festgeschriebener
   Dokumente).
3. **Feste Zeit**: stehende Uhr 14.10.2026 10:00 (Mittwoch) in Befüllen, Server und Browser; nach dem Befüllen jeder Zeitstempel auf
   diesen einen Zeitpunkt (nicht gestaffelt), außer `expires_at` und den Zeitstempeln, die `befuellen()` bewusst setzt
   (`BEWUSST_GESETZT`: Beginn und Ende des Termins).
4. **Feste Anzeige**: Versionsnummer „Bildgrundlage“ und `scripts/bildgrundlage_changelog.md` statt `VERSION` und `CHANGELOG.md`.
5. **„Fertig“ vor einem Bild**: Dokument geladen, Schriften geladen, keine Anfrage der Seite unterwegs und seit 0,8 s keine fertig, Fokus
   weg, zwei Frames; `localStorage` leer; Animationen, Übergänge und Textcursor per Stil aus. Thema über `prefers-color-scheme`.
6. **Ganzseitig**: Fensterhöhe = Seitenhöhe, mindestens 900, höchstens 16.000 px; 412 px als Mobilgerät, 1440 px als Desktop,
   Pixelfaktor 1.
7. **Abweichung** ohne Toleranz (ein Kanal anders); andere Größe: Fläche außerhalb zählt; fehlende und neue Bilder sind Abweichungen.
8. **Ordner** `bildgrundlage/<kurzer Hash>`, mit geänderter Arbeitskopie `…-geaendert`; ein Zielordner muss leer sein.
9. **Status je Bild**: 200, die Sperrseite 403 -- sonst Rückgabecode 1.
10. **Zeitlimit je Bild** unter einer Gegenprobe (2 min) statt für den ganzen Lauf.
11. **Port-Helfer**: `bind` auf 127.0.0.1 und 0.0.0.0 vor der Rückgabe; jeder Klicktest nimmt ihn, auch für Empfänger im Skript (SMTP),
    kein Klicktest bindet Port 0 selbst (Test).
12. **Text ohne LCD-Kantenglättung** (`--disable-lcd-text`) in der Bildgrundlage -- Graustufen statt farbiger Säume; die Bilder zeigen
    den Text damit etwas anders als ein Browser mit ClearType. **Bestätigt am 19.10.2026.**
13. **Testdaten ohne Flush mit zwei geänderten Objekten**: der Projektstatus wird vor dem Beauftragen gesetzt (Wackelquelle 1); die
    Ursache im App-Code bleibt (siehe Nebenbefunde). **Bestätigt am 19.10.2026.**

#### Nachtrag 1.8.127 (Stufe 1 des Redesigns)

- **Zählung der Aufnahmen**: je Thema und Breite 60 = 48 Büro – Finanzen + 10 Monteurin + 1 Admin (Adressimport) + 1 anonym
  (Anmeldeseite). Die Sperrseite ist eine der 10 Aufnahmen der Monteurin (`/projects`); der Bericht zu 1.8.126 nannte sie zusätzlich als
  eigenen Punkt, daher dort scheinbar 61.
- **Vergleich bricht ab bei verschiedenen Chrome-Versionen** (`bildgrundlage.py vergleichen`, Vorgabe vom 19.10.2026, Punkt 8): stehen
  in beiden `bilder.json` verschiedene Versionen, vergleicht er nicht, sondern endet mit Rückgabecode 2 (`ABBRUCH`) und dem Hinweis, die
  Grundlage auf ihrem Commit mit dem Chrome von heute neu zu erzeugen; fehlt eine `bilder.json`, nur ein Hinweis. Tests in
  `tests/test_v431_bildgrundlage.py` (neu, keine Erwartung geändert). Am 19.10.2026 war Chrome unverändert 155.0.8059.40 -- die Grundlage
  `08b538c` blieb gültig.

#### Grenzen (was die Grundlage nicht abdeckt)

- **Nur der Zustand nach dem Laden**: keine Dialoge, aufgeklappten Menüs, Hover und Fokus, Fehlermeldungen, weiteren Reiter (Projektmappe,
  Einstellungen: nur die erste Ansicht), Zustände per Adresse (`?zweck=`, `?next=`). *Seit 1.8.131 fünf Zustände des Rahmens (Menü,
  eingeklappt, Kontomenü, Leiste ganz unten, Leiste Büro – Auftrag) auf je einer Seite, siehe „Stufe 2a“.*
- **Eine Datenlage**: Rechnung, Checkliste und Einsatzbericht als Entwurf, kein Vertrag, keine Abnahme, keine Mahnung, keine Zahlung --
  Karten, die erst damit erscheinen, sind nicht im Bild; leere Listen nur dort, wo die Testdaten nichts anlegen.
- **Teilläufe** (`--nur`): eine Seite kann davon abhängen, welche Seiten vorher besucht wurden (Wackelquelle 2 war so eine Abhängigkeit,
  über den Browser); verglichen werden sollten volle Läufe.
- **Bereiche mit eigenem Scroll** (Seitenleiste, Zeitachse der Plantafel, breite Tabellen) zeigen nur ihren sichtbaren Teil. *Seit 1.8.131
  die Seitenleiste des Büros auch ganz unten (Startseite, 1440).*
- **Büro – Auftrag** und Büro mit Admin-Rechten (Einstellungen ganz) nicht aufgenommen. *Seit 1.8.131 die Seitenleiste von Büro – Auftrag
  (Startseite, 1440).*
- **Zwei Breiten**: kein Tablet (768/1024 px), kein Querformat. *Seit 1.8.131 die Seiten der Monteurin auch auf dem TerraPad (800 und
  1280 px, hoch und quer); das Büro weiter nur 412 und 1440.*
- **Ein Rechner, ein Browser**: Pixel hängen an Chrome-Version und installierten Schriften (die Seiten nehmen Inter, sonst die
  Systemschrift) -- verglichen wird nur zwischen Läufen auf demselben Rechner mit demselben Chrome (`bilder.json` hält die Version fest).
- **Nicht im Bild**: PDFs, E-Mails, Druckansicht, Seiten über 16.000 px (heute höchstens der Verlauf mit rund 13.000 px).

#### Nebenbefunde (nur gemeldet)

1. **Reihenfolge der Verlaufseinträge eines Flush ist zufällig** (`app/audit.py`, `for obj in list(session.dirty)`): zwei Änderungen im
   selben Commit erscheinen im Verlauf von Lauf zu Lauf in anderer Reihenfolge, auch im Betrieb (für Menschen ohne Folgen, beide haben
   denselben Zeitpunkt). Vorschlag für eine Runde mit App-Code: `session.dirty` vor dem Schreiben fest ordnen (z. B. nach Tabelle und
   Primärschlüssel); dann entfällt die Umgehung in den Testdaten (Festlegung 13).

#### Tests und Prüfung

- Neu `tests/test_v431_bildgrundlage.py` (25 Tests): Abdeckung (genau die Seiten aus `seiten()`), Namen und Rollen, jede Adresse zeichnet
  für jede ihrer Rollen die genannte Vorlage (Sperrseite: 403; mit einem Konto in der Datenbank, sonst öffnet `/users` jeder), jede
  Seitenroute, die die Monteurin öffnet, steht mit ihrer Rolle in der Liste; Vergleich (gleich 0, ein Pixel samt Differenzbild, nur Alpha,
  andere Größe, fehlend und neu, leerer Ordner, Kommandozeile, Name des Differenzordners); Zeitstempel außer `expires_at` und den
  Terminzeiten; stehende Uhr in Server und Browser (node, Regel 36), laufende Uhr unverändert; Wachhund je Schritt; Port-Helfer
  überspringt an 127.0.0.1 und an 0.0.0.0 belegte und reservierte Ports; kein Klicktest mit eigenem Port-Helfer; `/bildgrundlage/` in
  `.gitignore`.
- **Gegenproben der Tests** (Plugin im Speicher, je Variante): Seite aus der Liste genommen → Abdeckung rot; Konto ohne Monteurin →
  Monteur-Test rot; Zeiterfassung der Monteurin mit Büro-Rolle → drei Tests rot; Adressimport mit Büro statt Admin → Namen/Rollen und
  Adressen rot; Zeitstempel samt `expires_at` → Zeitstempel-Test rot; erste Fassung (samt Terminzeiten) → Zeitstempel-Test rot.
  Port-Helfer am Stand 1.8.125: gibt den an 0.0.0.0 belegten Port zurück (danach nicht mehr); der Wächter fände dort
  `klicktest_anmelden` und die sieben SMTP-Klicktests. Statusprüfung im Werkzeug: Adressimport mit Büro-Rolle → vier Bilder „Status 403,
  erwartet 200“, Rückgabecode 1.
- **Gegenprobe (a)**: vor den beiden Korrekturen zwei volle Läufe 0 abweichende Pixel (je 240 Bilder, je 5 min 16 s, 18 MB) -- im
  Nachhinein Zufall (Wackelquelle 1 trifft etwa jeden zweiten Lauf). Nachgestellt und behoben wie oben. Am Commit wiederholt (Bericht).
- **Gegenprobe (b)** vor den Korrekturen -- Wegwerfkopie des Projekts (ohne `.git`, `.venv`, Daten), in `finanzen.html` `.metric` mit
  `padding:12px 17px` statt `16px` (Marker `GEGENPROBE`, das Zeitlimit galt dort je Bild): „236 gleich, 4 abweichend, 0 fehlen, 0 neu“,
  Rückgabecode 1 -- abweichend genau `buero__{hell,dunkel}__{412,1440}__finanzen.png` (4.106 bzw. 5.244 Pixel, die vier Kennzahl-Kästen
  im Differenzbild rot). Am Commit wiederholt über ein Git-Worktree (Bericht).
- **Eigener Fehler, behoben**: die erste Fassung setzte jeden Zeitstempel auf die Uhr, auch Beginn und Ende des Termins (14:00–15:00
  wurde 10:00–10:00 UTC); seither `BEWUSST_GESETZT`, Test und Gegenprobe. Eine Staffelung je Zeile half gegen Wackelquelle 1 nicht (die
  IDs entstehen schon in der Reihenfolge von `session.dirty`) und wurde verworfen.
- **Angepasste Tests** (Regel 28): keine. `test_v413::test_ohne_gegenprobe_und_ohne_angabe_kein_zeitlimit` liest die Zeile
  `wachhund = Wachhund(*min(grenzen)) if grenzen else None` wörtlich -- sie blieb, `je_schritt` wird danach gesetzt.

## Bildgrundlage erweitert, Stufe 2a (1.8.131)

Vorgabe vom 19.10.2026 (Teil B, übernommen wie gegeben): „Teil B – Stufe 2a (Bildgrundlage erweitern) 4. Die Seiten der Monteurin
zusätzlich in 800 und 1280 px Breite (TerraPad hoch und quer), hell und dunkel. 5. Zustände des Rahmens, je hell und dunkel, auf einer
Büro-Seite und, wo es ihn gibt, auf einer Seite der Monteurin: Menü aufgeklappt (412 und 800), Seitenleiste eingeklappt (1440 und 1280),
Kontomenü offen (1440), Seitenleiste ganz nach unten gescrollt (1440), Seitenleiste der Rolle Büro – Auftrag (1440). 6. Abdeckungstest
erweitern. Neue Grundlage auf dem Commit von Teil B, zwei Läufe ohne Abweichung.“

### Befund vor dem Bauen

- **Rahmen**: Seitenleiste `_sidebar.html` und Kopfzeile `_topbar.html`. Unter 1001 px ist die Leiste ausgeblendet und wird über den Knopf
  `#appTopbarMenuBtn` der Kopfzeile geöffnet (`mobile-open`, Hintergrund abgedunkelt); ab 1001 px klappt der Knopf `#appSidebarToggle` unten
  in der Leiste sie ein (`collapsed`, gemerkt in `localStorage`, das die Bildgrundlage vor jedem Laden leert). Das Kontomenü öffnet der
  Knopf mit den Initialen (`#appTopbarAccountBtn`, Menü `#appTopbarAccountMenu`). Die Leiste scrollt selbst, wenn sie nicht ins Fenster passt.
- **Die Monteurin** hat den Rahmen nur auf zwei ihrer Seiten -- Einsatzbericht und Konto; Checkliste und Checklisten des Auftrags wählen für
  sie den Kopf der Monteursansicht (`_mobile_header.html`, ohne Menü und Kontomenü), `/mobil`, Objekt, Stundenzettel, Zeiterfassung und
  Betriebsmittel haben nur ihn, die Sperrseite keinen. Ihre Leiste (Start, Zeiterfassung) passt bei 1440 × 900 ins Fenster -- „ganz nach
  unten gescrollt“ gibt es dort nicht.
- **Ganzseitige Bilder** legen das Fenster auf die Seitenhöhe: die Leiste wird so hoch wie die Seite und scrollt nicht mehr, Menüs am
  Fenster stünden irgendwo -- für die Zustände braucht es das Bild des Fensters.
- **Ein Konto mehr verändert die Verlaufsseite** (AppUser wird protokolliert) -- die bisherigen Bilder blieben nicht gleich.

### Umsetzung 1.8.131

- **`scripts/bildgrundlage.py`**: `TABLET = (800, 1280)`, `GERAETE = (412, 800, 1280)` (als Gerät, `mobile`), `STARTHOEHEN = {800: 1280,
  1280: 800}`. `ZUSTAENDE` (Name, Aktion, Breiten, Rollen): die Aktion klickt den Knopf der Seite und gibt zurück, ob der Zustand
  eingetreten ist; `ZUSTANDSSEITEN`: Büro und Büro – Auftrag die Startseite, die Monteurin der Einsatzbericht. `geplante_bilder()` liefert
  alle Bilder in der Reihenfolge der Aufnahme (zuerst die bisherigen 240 wie bisher, dann 40 TerraPad, dann 24 Zustände = 304);
  `pruefen()` geht sie durch und meldet sich nur beim Wechsel der Rolle neu an. `_bild(…, zustand)`: nach dem Laden die Aktion, Ruhe, Bild
  des Fensters; je Zustand die Prüfung „eingetreten“, beim Kontomenü der Monteurin zusätzlich „Leiste ohne Bildlauf“
  (`LEISTE_OHNE_BILDLAUF`). Dateiname `<rolle>__<thema>__<breite>__<seite>--<zustand>.png`, in `bilder.json` dazu `zustand`. Testdaten: Konto
  „Berta Auftrag“ (Büro – Auftrag) per Core-Insert, ohne Verlaufseintrag.

#### Festlegungen 1.8.131 (Bitte bestätigen)

Alle betreffen nur Werkzeug und Testablauf (Regel 28).

1. **TerraPad**: jede Aufnahme mit der Monteurin (alle zehn, auch die Sperrseite) zusätzlich in 800 px (hoch, Fenster 800 × 1280) und
   1280 px (quer, 1280 × 800), je hell und dunkel; Büro, Admin und anonym bleiben bei 412 und 1440.
2. **Als Gerät**: 412, 800 und 1280 mit `mobile` (Viewport wie auf dem Gerät, Bildlaufleisten über dem Inhalt), Pixelfaktor 1, ohne
   Touch-Emulation; 1440 als Desktop. Ganzseitig wie bisher, Mindesthöhe die Fensterhöhe.
3. **Zustände als Bild des Fensters**, nicht der ganzen Seite (die Leiste und die Menüs hängen am Fenster; ganzseitig gäbe es „ganz unten“
   nicht). Fenster 412 × 900, 800 × 1280, 1280 × 800, 1440 × 900.
4. **Seiten der Zustände**: Büro – Finanzen und Büro – Auftrag auf der Startseite `/`; die Monteurin auf dem Einsatzbericht (eine ihrer
   zwei Seiten mit Seitenleiste und Kopfzeile; Konto wäre die andere).
5. **Zustände**: Menü aufgeklappt 412 und 800 (Knopf ☰ der Kopfzeile), Seitenleiste eingeklappt 1280 und 1440 (Knopf unten in der Leiste),
   Kontomenü offen 1440 (Knopf mit den Initialen), Seitenleiste ganz unten 1440 nur für das Büro (bei der Monteurin passt die Leiste ins
   Fenster -- beim Aufnehmen geprüft), Seitenleiste von Büro – Auftrag 1440 (Startseite nach dem Laden); je hell und dunkel. Herbeigeführt
   per Klick auf den Knopf der Seite, vor dem Bild geprüft, danach Fokus weg.
6. **Konto Büro – Auftrag** in den Testdaten ohne Verlaufseintrag (Core-Insert), damit die bisherigen Bilder gleich bleiben.
7. **Reihenfolge und Namen**: zuerst die bisherigen 240 Bilder in der bisherigen Reihenfolge, dann die TerraPad-Bilder, dann die Zustände;
   `<rolle>__<thema>__<breite>__<seite>--<zustand>.png`; 304 Bilder je Lauf.
8. **Abdeckungstest**: TerraPad-Breiten für jede Seite der Monteurin; Zustände mit genau den vorgegebenen Breiten und Rollen; die Seite
   jeder Rolle zeichnet für sie Seitenleiste, Kopfzeile und die Knöpfe der Aktionen; die Monteurin hat den Rahmen genau auf Einsatzbericht
   und Konto; Dateinamen eindeutig, die bisherigen zuerst; ein Konto je Rolle in den Testdaten.

#### Tests und Prüfung

- `tests/test_v431_bildgrundlage.py`: neu 7 Tests (34 statt 27) -- TerraPad, Zustände wie vorgegeben (24), Dateinamen und Reihenfolge (304,
  die bisherigen 240 zuerst), Teilauswahl, Rahmen je Rolle auf der Seite der Zustände (gerendert, mit den Kennungen aus den Aktionen),
  Monteurin mit Rahmen genau auf Einsatzbericht und Konto, ein Konto je Rolle in den Testdaten. `ROLLE_IM_TEST` um Büro – Auftrag ergänzt.
- **Eigener Fehler, behoben**: die erste Fassung des Tests erwartete 26 Zustandsbilder (306 je Lauf) -- „ganz unten“ zählte für die
  Monteurin mit; richtig 24 (304).
- Probe vor den vollen Läufen (`--nur start --nur einsatzbericht`): 40 Bilder, 66 Prüfungen wie erwartet; angesehen: Menü auf 800 px,
  ganz unten dunkel, Kontomenü der Monteurin, eingeklappt bei 1280 dunkel.
- **Angepasste Tests** (Regel 28): keine Erwartung geändert (die Teil-A-Anpassung von `_mit_konto()` steht unter 1.8.130).
