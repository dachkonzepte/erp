"""Outlook-Kalendersynchronisation (Kalender-Modul, Stufe 2, seit 1.7.1) -- gleicht die eigenen
CalendarEvent-Zeilen einer Person mit ihrem Postfach (AppUser.outlook_mailbox) über Microsoft
Graph ab. Siehe CLAUDE.md "Kalender" -> "Stufe 2" für die vollständige Herleitung der sieben
Entscheidungspunkte, hier nur die Kurzfassung je Punkt als Modulkommentar.

**Bewusst getrennt von app/calendar_events.py** -- die reine Geschäftslogik (create_event()/
update_event()/delete_event(), Privatsphäre-Redaktion) bleibt vollständig frei von jeder
Outlook-Kenntnis, genau wie in Stufe 1 dokumentiert. Die Orchestrierung (nach dem Speichern
pushen, vor dem Löschen fernlöschen) sitzt in app/routers/calendar_events.py -- derselbe Ort, der
auch sonst mehrere Fachmodule zusammenführt, keine Kopplung der beiden Business-Module
untereinander (keine Zirkel-Import-Gefahr, siehe CLAUDE.md Regel 3).

**Punkt 1 -- Zuordnung ERP-Nutzer zu Postfach:** AppUser.outlook_mailbox (app/models.py),
admin-gepflegt über /users. Jede Synchronisation läuft ausschließlich für das EIGENE Postfach
des jeweiligen AppUser -- nie für das eines Kollegen, auch wenn die Kalenderansicht selbst
Kollegentermine anzeigt (Stufe 1). Seit 1.9.161 kann ein Postfach auch einem Gerät gehören
(OperationalResource.outlook_mailbox, Kran-Kalender, siehe Postfach unten): dessen Termine hängen
am Gerät, sie gleichen in beiden Richtungen ab und laufen nur mit dem Cron.

**Punkt 2 -- Projekt-/Angebotsbezug nie durch Outlook-Änderung überschreiben:**
_apply_delta_change() unten baut das Update-Dict für eine eingehende Änderung IMMER nur aus den
syncbaren Feldern (title/start_at/end_at/all_day/location/notes/is_private) --
project_id/quote_id/owner_user_id sind darin STRUKTURELL nie enthalten, unabhängig davon, was
Graph liefert (Graph kennt dieses Konzept ohnehin nicht). Ein aus Outlook neu angelegtes
CalendarEvent startet mit project_id=quote_id=None -- die Zuordnung bleibt danach ausschließlich
Sache eines Menschen in der ERP-Oberfläche.

**is_private ist seit 1.7.2 bewusst die EINE Ausnahme von "project_id/quote_id/is_private bleiben
außen vor"** (Nachtrag, siehe CLAUDE.md "Kalender" -> "Stufe 2" -> "Nachtrag (seit 1.7.2)"): anders
als project_id/quote_id hat Outlook mit `sensitivity` ein eigenes, natives Äquivalent --
_is_private_sensitivity()/_outgoing_sensitivity() unten übersetzen bidirektional
("private"/"confidential" <-> is_private=True). Ein aus Outlook gezogener Termin mit
sensitivity="private" landet dadurch schon beim Import mit is_private=True in der ERP-Ansicht --
Kollegen sehen ihn (über die bereits in Stufe 1 gebaute, hier unveränderte Redaktion,
app/calendar_events.py::redact_for_busy()) nur als "Belegt", ohne dass dafür irgendetwas in der
Privatsphäre-Logik selbst angefasst werden musste.

**Punkt 3 -- Zeitzonen:** CalendarEvent.start_at/end_at sind naive Zeitstempel in
EUROPE/BERLIN-Ortszeit (so, wie sie in der Kalenderoberfläche eingegeben werden, siehe
CalendarEvent-Klassendocstring/calendar.html::toLocalIso() -- KEIN UTC, anders als
created_at/updated_at). Graph erwartet/liefert dateTime-Werte mit einer expliziten timeZone;
dieses Modul rechnet bewusst IMMER selbst in/aus UTC um (to_utc()/to_berlin() unten, per
zoneinfo) und sendet/erwartet ausschließlich "timeZone": "UTC" -- vermeidet jede Mehrdeutigkeit
zwischen Windows- und IANA-Zeitzonennamen, die Graphs timeZone-Feld sonst zulässt.

**Punkt 4 -- Serientermine (seit 1.7.8 schreibgeschützt übernommen, siehe Abschnitt
"Serientermine" direkt vor sync_series_occurrences()):** der Delta-Weg (events/delta) liefert eine
Serie nur als EIN "seriesMaster"-Objekt -- _apply_delta_change() überspringt Master, Vorkommen und
Ausnahmen weiterhin vollständig. Die einzelnen Vorkommen kommen ausschließlich über einen
separaten calendarView-Schnappschuss in die eigene Tabelle OutlookSeriesOccurrence, nie als
CalendarEvent -- jede Outlook-ID gehört damit genau einem der beiden Wege.

**Punkt 5 -- Delta-Abfrage, Cron plus beim Öffnen, letzte Änderung gewinnt, Löschungen
beidseitig:** sync_user_calendar() ist der vollständige Pull-dann-Push-Zyklus für eine Person,
aufgerufen sowohl von scripts/sync_outlook_calendars.py (Cron, alle Postfächer) als auch von
POST /api/calendar-events/sync-outlook (beim Öffnen von /kalender, nur das eigene Postfach).
OutlookCalendarSyncState.delta_link erspart dabei jedem Lauf außer dem ersten die vollständige
Kalenderabfrage. "Letzte Änderung gewinnt" beim PULL: _apply_delta_change() vergleicht Graphs
lastModifiedDateTime gegen CalendarEvent.updated_at -- nur wenn Graph NEUER ist, werden die
lokalen Felder überschrieben, sonst gewinnt die lokale Zeile (und wird in der anschließenden
Push-Phase nach Outlook geschrieben). Löschungen beidseitig: ein "@removed"-Delta-Eintrag löscht
die lokale Zeile hart (_apply_delta_change()); eine lokale Löschung stößt best-effort eine
Graph-Löschung an (try_delete_remote_event(), aufgerufen vom Router VOR delete_event()).

**Nachtrag (seit 1.7.2) -- Push-Wiederholung braucht einen PRO-TERMIN-Merker, nicht nur den
globalen Postfach-Zeitstempel:** die ursprüngliche 1.7.1-Fassung entschied "braucht Outlook
diesen Termin?" über CalendarEvent.updated_at > OutlookCalendarSyncState.last_synced_at (ein
einzelner Zeitstempel PRO POSTFACH). Zwei damit zusammenhängende, beim Nachbau der
Push-Wiederholung gefundene Fehler, beide behoben:

1. Der Push-Abschnitt von sync_user_calendar() commitete `row.outlook_event_id` nach einem
   erfolgreichen POST NICHT sofort -- schlug ein SPÄTERER Termin in DERSELBEN Schleife fehl, riss
   das äußere except-db.rollback() die bereits erfolgreich anglegte Outlook-Zuordnung für den
   FRÜHEREN Termin wieder ein. Der nächste Lauf hätte diesen Termin dadurch ein zweites Mal in
   Outlook angelegt (Dublette). Behoben: jeder Termin committet jetzt EINZELN, ein
   fehlschlagender Termin blockiert die übrigen nicht mehr (eigenes try/except je Zeile, Muster
   "ein Postfach darf den Cron-Lauf für andere nicht abbrechen", hier eine Ebene tiefer
   angewendet).
2. Selbst mit sofortigem Commit hätte der GLOBALE last_synced_at-Vergleich einen genau EINEN
   fehlgeschlagenen Termin beim NÄCHSTEN Lauf verloren, sobald dieser Lauf für ALLE ANDEREN
   Termine erfolgreich war: last_synced_at rückt dann trotzdem vor, und
   `updated_at > last_synced_at` wird für den einen liegen gebliebenen Termin FALSCH, weil sein
   updated_at vor diesem neuen, vorgerückten last_synced_at liegt. CalendarEvent.outlook_synced_at
   (neu, siehe Klassendocstring-Korrektur app/models.py) ersetzt diesen Vergleich durch einen
   PRO-TERMIN-Merker -- Push ist fällig, wenn outlook_event_id fehlt ODER outlook_synced_at fehlt
   ODER updated_at > outlook_synced_at, unabhängig vom Postfach-weiten last_synced_at (das bleibt
   als reine Diagnose-/Anzeigeinformation bestehen, ist aber nicht mehr Teil der
   Push-Entscheidung).

_mark_synced() unten setzt updated_at UND outlook_synced_at explizit auf denselben Zeitpunkt --
sonst würde SQLAlchemys onupdate=datetime.utcnow bei JEDER Schreiboperation (auch der reinen
Sync-Buchhaltung selbst) updated_at unbeabsichtigt weiterschieben und dadurch einen frisch
erfolgreich gepushten/gezogenen Termin sofort wieder als "noch zu übertragen" erscheinen lassen.

**Nachtrag "Schaukelnder Termin" (seit 1.7.3) -- Echo-Erkennung exakt statt heuristisch, per
changeKey:** gemeldet wurde ein Termin, der über mehrere Läufe hinweg abwechselnd als "1
geändert" (Pull) und "1 nach Outlook aktualisiert" (Push) auftauchte, OHNE dass jemand ihn
angefasst hat. Vor jeder Änderung wurde das geprüft, nicht angenommen: ein direkter Test gegen
`_mark_synced()` (isoliert UND über einen kompletten Session-Neustart hinweg, der einen neuen
Cron-Prozess simuliert) bestätigt, dass updated_at/outlook_synced_at korrekt synchron bleiben,
auch nach dem in ihrem Docstring beschriebenen Autoflush-Fallstrick. Ein voller Rundlauf gegen
eine Graph-Attrappe MIT ECHTEM ZUSTAND (PATCH/POST vergibt tatsächlich einen neuen
lastModifiedDateTime, ein späterer Delta-Abruf liefert die eigene Änderung als scheinbar fremde
zurück -- genau der Fall, den die bisherigen, rein statischen Testantworten dieser Datei nie
abgebildet hatten) zeigt: der einfache Fall (ein Termin, ein Push, ein späterer Echo-Pull) wird
von der Zeitstempel-Logik bereits korrekt EINMALIG absorbiert und kommt danach zur Ruhe -- ein
tatsächliches, unbegrenztes Schaukeln ließ sich mit den hier verfügbaren Mitteln (kein Zugriff
auf echte Graph-Protokolle) nicht reproduzieren.

Die Zeitstempel-Logik (`graph_modified <= existing.updated_at`) bleibt aber eine reine
HEURISTIK -- sie beantwortet "wer ist neuer", nicht "ist das exakt meine eigene, bereits bekannte
Version". Sie kann durch Uhrenabweichung zwischen dem ERP-Server und Microsofts eigenen Servern
oder durch eine von Graph beim Roundtrip abweichend formatierte Antwort (dokumentiert z. B. für
Event-Bodies) getäuscht werden -- beides mit den hier verfügbaren Mitteln weder aus- noch
nachweisbar. Deshalb: `changeKey` (Graphs eigener, bei JEDER Schreiboperation neu vergebener
Versionsstempel, wie ein ETag) wird jetzt zusätzlich in `_EVENT_SELECT` abgefragt, nach jedem
erfolgreichen Push aus der Graph-Antwort in `CalendarEvent.outlook_change_key` gespeichert, und
`_apply_delta_change()` erkennt einen eingehenden Delta-Eintrag, dessen changeKey exakt mit dem
zuletzt gespeicherten übereinstimmt, ALS EIGENES ECHO -- unabhängig von jeder Uhr, ohne
Feldübernahme, ohne `_mark_synced()`-Aufruf, da nichts zu synchronisieren ist. Das ist eine
ZUSÄTZLICHE, keine ERSETZENDE Absicherung: liefert Graph auf ein PATCH keinen Body mit changeKey
zurück (bleibt dann als bewusst offener Randfall bestehen), greift die unveränderte
Zeitstempel-Logik als Rückfall -- genau wie zuvor. Ein neuer, gezielter Test
(tests/test_v297_outlook_calendar_sync.py) lässt eine Attrappe mit echtem Zustand über sieben
aufeinanderfolgende Läufe ohne jede Nutzeränderung laufen und verlangt, dass ab dem zweiten Lauf
JEDER Zähler bei null steht und bleibt.

**Punkt 6 -- kein Termininhalt in Protokollen:** logger unten protokolliert ausschließlich
Zähler (erstellt/aktualisiert/gelöscht/übersprungen), Zeitdauer und im Fehlerfall den reinen
Exception-Klassennamen (nie str(exc)) -- dieselbe Zurückhaltung wie bei AICallLog.error_type,
aus demselben Grund: eine Graph-Fehlermeldung kann Teile der fehlgeschlagenen Anfrage (Titel,
Ort) im Klartext zurückspiegeln. Kein Log-Aufruf in diesem Modul reicht je title/location/notes/
den rohen Graph-Response-Body weiter.

**Punkt 7 -- Tests nur gegen Attrappe:** siehe tests/test_v297_outlook_calendar_sync.py -- jeder
Test patcht urllib.request.urlopen an dieser Stelle (app.outlook_calendar_sync.urllib.request.urlopen),
niemals ein echter Netzwerkaufruf.

**Zweite Untersuchungsrunde -- der changeKey-Nachtrag (1.7.3) hat das gemeldete Schaukeln auf dem
Produktivserver NICHT beendet, weiterhin dasselbe Wechselmuster.** Vier gezielt vorgegebene
Prüfungen, siehe CLAUDE.md "Kalender" -> "Stufe 2" -> "Zweite Untersuchungsrunde (seit 1.7.4)" für
die vollständige Herleitung, hier die Kurzfassung:

1. **`updated_at`/`outlook_synced_at` werden ausschließlich Python-seitig gesetzt**
   (`datetime.utcnow()`, NIE ein DB-`server_default`/Trigger), bleiben naiv-UTC durchgängig (nie
   `to_utc()`/`to_berlin()`, die sind ausschließlich für `start_at`/`end_at` reserviert) und
   round-trippen unter PostgreSQL (`TIMESTAMP WITHOUT TIME ZONE`, empirisch per psql-Tabellenbefehl
   bestätigt -- keine Zeitzonen-Wandlung, da diese Spaltenart sie nicht kennt) nachweislich bis auf die
   Mikrosekunde exakt, auch über einen frischen Session-/Prozess-Neustart hinweg. Kein
  Postgres-spezifischer Unterschied an DIESER Stelle gefunden.
2. **Der Schaukel-Test lief gegen die echte, lokale PostgreSQL-Instanz** (mit frischen Sessions je
   Lauf, also einen eigenen Prozess je Cron-Tick simulierend) -- sowohl MIT als auch (testweise)
   OHNE changeKey in der Graph-Antwort. Beide Varianten kommen nach dem einmaligen Echo-Zyklus
   zur Ruhe, kein Unterschied zu SQLite. Die Ursache liegt damit NICHT in einem SQLite-vs-
   PostgreSQL-Unterschied bei Datumswerten, den sich mit den hier verfügbaren Mitteln reproduzieren
   ließe.
3. **Ein real gefundener, unabhängiger Präzisions-Fehler in `_parse_graph_datetime()`**: Microsofts
   `lastModifiedDateTime` trägt üblicherweise SIEBEN Nachkommastellen (100-Nanosekunden-"Ticks",
   z. B. `"2026-09-26T09:37:34.6472860Z"`). `datetime.fromisoformat()` akzeptiert das nur ab
   **Python 3.11** (vorher: ValueError bei jeder Bruchteilsekundenlänge außer 0/3/6 Ziffern) --
   welcher Python auf dem Produktivserver tatsächlich läuft, ist hier nicht dokumentiert und nicht
   geprüft worden. Bei einer ValueError wäre allerdings der GESAMTE Lauf mit `error: True`
   markiert, nicht das gemeldete, unauffällige 1-zu-1-Wechselmuster -- deshalb vermutlich NICHT
   die alleinige Ursache, aber ein eigenständiger, real gefundener Härtungsbedarf.
4. **Ob Graphs Delta-Antwort `changeKey` tatsächlich mitliefert, ließ sich ohne Zugriff auf den
   echten Tenant NICHT verifizieren.** Genau dafür die neue Diagnosezeile unten.

**Abschaltbare Diagnosezeile (seit 1.7.4)**: `ERP_OUTLOOK_SYNC_DIAGNOSTICS=1` in der Umgebung
(`.env`, vom Cron-Skript bei jedem Lauf neu geladen, siehe scripts/sync_outlook_calendars.py)
schaltet je verarbeitetem Delta-Eintrag UND je Push-Versuch eine zusätzliche, strukturierte
Protokollzeile frei -- ERP-ID, `updated_at`, `outlook_synced_at`, `lastModifiedDateTime` ROH (der
unveränderte String aus der Graph-Antwort) UND umgerechnet (das Ergebnis von
`_parse_graph_datetime()`), der Versionsstempel gespeichert/eingehend (seit 1.7.5: `@odata.etag`,
siehe Nachtrag unten -- vorher fälschlich `changeKey`), die getroffene Entscheidung. Bewusst NIE
Titel/Ort/Notiz (Punkt 6 bleibt unverändert in Kraft) -- der Versionsstempel selbst ist ein
bedeutungsloser, von Graph vergebener Wert, kein Termininhalt. Diese Diagnosezeile lief noch nie
gegen einen echten Tenant -- sie ist das Werkzeug, mit dem der Betreiber das auf dem
Produktivserver selbst nachvollziehen kann, siehe Moduldocstring-Abschnitt oben Punkt 3/4.

**Nachtrag (seit 1.7.5) -- die Diagnosezeile aus 1.7.4 hat funktioniert: `change_key_gespeichert`
UND `change_key_eingehend` standen auf dem Produktivserver in JEDER Zeile auf `None`, auch direkt
nach einem als "push erfolgreich" protokollierten Push.** Drei konkrete Prüfungen, wie vom
Betreiber vorgegeben, diesmal NICHT nur im Gedächtnis nachgeschlagen, sondern direkt anhand der
Microsoft-Graph-Dokumentation (Microsoft Learn, `event: delta`/`delta-query-events`/`event`-
Ressourcenseite, WebFetch/WebSearch):

1. **Fordert der Delta-Aufruf `changeKey` per `$select` an?** Ja, `_EVENT_SELECT` enthielt es
   (Zeile weiter unten, bis 1.7.4) -- aber Microsoft dokumentiert für Kalender-Delta-Abfragen
   ausdrücklich: *"Expect a delta function call on a calendarView to return the same properties
   you'd normally get from a GET /calendarView request. You cannot use $select to get only a
   subset of those properties."* -- **`$select` wird für Delta-Abfragen auf Kalenderdaten schlicht
   ignoriert**, unabhängig davon, was in der URL steht.
2. **Liefert Graph `changeKey` im Delta überhaupt, oder nur `@odata.etag`?** Jede von Microsoft
   selbst in der Dokumentation gezeigte Beispiel-Delta-Antwort (mehrere Beispiele auf der Seite
   "Get incremental changes to events in a calendar view", inkl. geänderter UND neu
   hinzugekommener Einträge) zeigt durchgängig ein `@odata.etag`-Feld -- **niemals ein
   `changeKey`-Feld**, obwohl andere, deutlich weniger zentrale Felder (`subject`, `body`,
   `attendees`, `organizer`) jeweils vollständig gezeigt werden. `changeKey` ist damit für
   Delta-Zeilen strukturell nicht erreichbar, kein Zufall dieser einen Installation.
3. **Wird es aus der Antwort auf POST/PATCH übernommen?** Die Extraktion selbst
   (`response.get("changeKey")`) war korrekt -- aber ein zweiter, unabhängiger Fund: die
   "push erfolgreich"-Diagnosezeile protokollierte für `change_key_gespeichert` den WERT VOR DEM
   PUSH (`old_change_key`), nicht den gerade frisch gespeicherten neuen Wert -- ein reiner
   Diagnose-Anzeigefehler, der auf dem allerersten Push für einen Termin (kein vorheriger Wert)
   zusätzlich zur eigentlichen Ursache "None" zeigte, unabhängig davon, ob der Push selbst
   erfolgreich einen neuen Wert extrahiert hatte. Behoben, siehe unten.

**Die Lösung wechselt den kompletten Mechanismus von `changeKey` auf `@odata.etag`** --
`@odata.etag` ist eine protokollweite OData-Annotation, die laut Microsofts eigener
Ressourcen-Dokumentation UND allen gezeigten Beispielantworten JEDE Entitätsdarstellung begleitet
(ein einfaches `GET /events/{id}` ebenso wie die Antwort auf `POST`/`PATCH` UND jede einzelne
Delta-Zeile) -- unabhängig von `$select`, weil sie kein regulär selektierbares
Entitäts-Property ist, sondern ein Protokoll-Header-Äquivalent auf JSON-Ebene. Sie steht deshalb
zuverlässig auf BEIDEN Seiten des Vergleichs zur Verfügung: beim Speichern nach einem eigenen
Push (aus der POST-/PATCH-Antwort) UND beim Abgleich gegen einen eingehenden Delta-Eintrag. Die
Spalte `CalendarEvent.outlook_change_key` heißt seither `outlook_etag` (Migration, siehe
app/models.py-Klassendocstring "Korrektur" für die vollständige Begründung) -- die
Echo-Erkennung selbst (exakter Wertevergleich, zusätzliche statt ersetzende Absicherung neben der
unveränderten Zeitstempel-Heuristik) ist inhaltlich unverändert, nur das verglichene Feld hat
sich geändert. `_EVENT_SELECT` verzichtet seither auf `changeKey` -- es wurde ohnehin nie
geliefert, ein Weglassen ändert am Verhalten nichts, macht die Anfrage aber ehrlich.

`FakeGraphServer` (`tests/test_v297_outlook_calendar_sync.py`) bildete bis 1.7.4 GENAU diesen
falschen Zustand nach: `delta()` lieferte `changeKey` in JEDER Zeile mit, `create()`/`patch()`
ebenfalls -- ein Test gegen diese Attrappe konnte den echten Fehler deshalb strukturell nie
finden, unabhängig davon, wie viele Läufe er simulierte. Seit 1.7.5 liefert `delta()` NUR NOCH
`@odata.etag` (kein `changeKey` mehr, genau wie die echten Microsoft-Beispielantworten),
`create()`/`patch()` liefern weiterhin BEIDE Felder (wie ein reales POST/PATCH es tut) --
`app/outlook_calendar_sync.py` darf sich für die Echo-Erkennung nur noch auf das verlassen, was
tatsächlich auf beiden Seiten ankommt.

**Nachtrag (seit 1.7.6) -- die reine Sync-Buchhaltung selbst konnte `updated_at` verschieben,
EIGENTLICHE Ursache jetzt gefunden UND nachweislich behoben.** Die vom Betreiber vorgelegte
Produktions-Diagnose zeigte für "etag-Echo (übersprungen)"/"Graph nicht neuer (übersprungen)"
Zeilen mit bereits VOR der eigentlichen Verarbeitung divergiertem `updated_at`/`outlook_synced_at`
(Beispiel: `updated_at=13:01:57.632772` gegen `outlook_synced_at=13:01:50.714899`, gefolgt von
"push angestoßen"), sowie einen Fall, in dem `updated_at` 3,7 ms NACH `_mark_synced()` noch von
`outlook_synced_at` abwich. Drei geforderte Punkte:

1. **Empirisch nachgebaut, nicht angenommen** (`sqlalchemy.create_engine(..., echo=True)`, sowohl
   gegen SQLite als auch gegen eine echte, lokale PostgreSQL-Instanz) -- UND dabei zweimal die
   eigene Zwischenannahme widerlegt, bevor die tatsächliche Ursache feststand:
   - Erste Vermutung (widerlegt): `session.execute()` autoflusht vor der eigenen Anweisung jede
     andere, noch offene Dirty-Markierung -- war `row` bereits über `setattr()` dirty (wie
     `push_event_best_effort()`/die Push-Schleife es bis dahin mit `outlook_event_id`/
     `outlook_etag` VOR dem alten `_mark_synced()`-Aufruf taten), erzeugte dieser Autoflush eine
     GEWÖHNLICHE ORM-UPDATE-Anweisung samt `onupdate=datetime.utcnow`-Bump. Ein erster Fix-Entwurf
     entfernte deshalb nur das vorherige `setattr()` (die Felder wandern stattdessen direkt in
     `.values()`) -- **das reichte NICHT**: der bereits bestehende Test
     `test_successful_push_does_not_let_updated_at_drift_and_prevents_a_redundant_second_push`
     schlug mit genau diesem "Fix" weiterhin fehl, per SQL-Mitschnitt bestätigt mit
     `UPDATE calendar_events SET outlook_event_id=?, outlook_synced_at=?, updated_at=?` --
     `updated_at` erschien in der SET-Klausel, OBWOHL kein `updated_at`-Parameter in `.values()`
     übergeben wurde.
   - **Tatsächliche Ursache**: `Column(..., onupdate=datetime.utcnow)` ist eine
     COLUMN-Eigenschaft, keine reine ORM-Mapper-Eigenschaft -- sie greift bei JEDER
     `UPDATE`-Anweisung gegen diese Tabelle, ob über die ORM-Klasse (`update(CalendarEvent)`)
     ODER das rohe Core-`Table`-Objekt (`update(CalendarEvent.__table__)`) abgesetzt (beides
     empirisch geprüft, beide Varianten zeigten denselben, unerwünschten Bump), SOBALD
     `updated_at` NICHT explizit in `.values()` auftaucht. Ein bloßes Weglassen der Spalte
     schützt sie also NICHT vor `onupdate` -- unabhängig von Autoflush-Timing, Dirty-Zustand
     oder Ausführungsreihenfolge. Das erklärt sowohl das ursprüngliche `_mark_synced()`-Muster
     (funktionierte NUR, weil es `updated_at=at` explizit mitgab) als auch, warum der erste
     1.7.6-Fix-Entwurf trotz "sauberer" Reihenfolge weiterhin fehlschlug.
   - **Die tatsächlich wirksame Lösung**: `updated_at` wird in JEDEM `_write_sync_bookkeeping()`-
     Aufruf IMMER explizit auf eine SELBSTREFERENZ gesetzt (`updated_at=CalendarEvent.updated_at`,
     kompiliert zu `SET updated_at = calendar_events.updated_at`) -- ein explizit gegebener Wert
     unterdrückt `onupdate` zuverlässig (das nur greift, wenn für die Spalte KEIN Wert übergeben
     wurde), ohne dass der aktuelle Wert vorher in Python bekannt sein müsste: die Datenbank
     liest ihn atomar aus derselben Zeile. Per direktem Vorher/Nachher-Vergleich bestätigt:
     `DRIFT = 0:00:00`, exakt.
   - **Ehrlich festgehalten**: ein exakter, deterministischer Nachbau der in der Produktions-
     Diagnose gezeigten PERSISTIERTEN Zahlenwerte (mit mehreren Sekunden Abstand bzw. dem
     3,7-ms-Versatz) gelang trotz umfangreicher Versuche (Einzelsession, Session-pro-Lauf nach
     dem Vorbild eines neuen Cron-Prozesses, SQLite UND PostgreSQL) mit dem VORHERIGEN
     `_mark_synced()`-Mechanismus NICHT -- dessen `updated_at=at`-Parameter unterdrückte
     `onupdate` für DIESE eine Anweisung bereits korrekt (siehe oben), das Risiko lag dort in der
     Kombination aus zwei Schreibvorgängen mit einem zwischenzeitlich falschen Wert. Der jetzt
     tatsächlich gefundene und behobene Fehler (Spalte weglassen schützt NICHT vor `onupdate`)
     trat ausschließlich in einem ZWISCHENSCHRITT des eigenen Reparaturversuchs auf, nicht in der
     ursprünglich ausgelieferten 1.7.1-1.7.5-Fassung -- die genaue Abfolge, die in Produktion zu
     einem beobachteten Versatz geführt hat, bleibt damit weiterhin nicht abschließend bewiesen.
     Der jetzt gewählte, endgültige Mechanismus (explizite Selbstreferenz) ist aber unabhängig
     davon nachweislich korrekt und macht das gesamte Risiko strukturell unmöglich, statt sich auf
     eine bestimmte Zwischenzustands-Reihenfolge zu verlassen.
2. **Überspringen verändert die Zeile gar nicht** -- bereits vor diesem Nachtrag der Fall (die
   beiden Skip-Zweige in `_apply_delta_change()` riefen nie eine Schreibfunktion auf, geprüft
   erneut anhand des Quelltexts) und durch einen eigenen Test (`test_delta_item_with_an_etag_we_
   already_know_is_recognized_as_our_own_echo_and_skipped`, bereits seit 1.7.3 bestehend) mit
   einer exakten `updated_at`-Gleichheitsprüfung abgesichert.
3. **Jeder reine Sync-Buchhaltungs-Schreibvorgang läuft seither über `_write_sync_bookkeeping()`**
   (siehe dortiger Docstring für den vollständigen Mechanismus) -- `updated_at` wird dort IMMER
   auf die beschriebene Selbstreferenz gesetzt, kann sich also durch keinen Aufruf dieser
   Funktion je ändern, unabhängig von Autoflush-Timing, Dirty-Zustand oder Dialekt.
   `push_event_best_effort()` und die Push-Schleife in `sync_user_calendar()` setzen
   `outlook_event_id`/`outlook_etag` seither NICHT MEHR per `setattr()` vor dem
   Buchhaltungsaufruf, sondern als Teil DERSELBEN Anweisung -- unabhängig von der Selbstreferenz-
   Lösung eine zusätzliche, saubere Vereinfachung. `_apply_delta_change()`s "übernommen"-Zweig
   trennt ECHTE inhaltliche Änderungen (title/location/... -- die SOLLEN `updated_at` ganz normal
   über `onupdate` bumpen, das ist eine echte Änderung) von der reinen Buchhaltung
   (`outlook_etag`/`outlook_synced_at`): erst `db.flush()` der inhaltlichen Felder, dann wird der
   TATSÄCHLICH generierte `updated_at`-Wert ausgelesen und unverändert als `outlook_synced_at` in
   die separate Buchhaltungsanweisung übergeben -- kein separat erfasster `datetime.utcnow()`
   mehr, der vom tatsächlich gespeicherten Wert abweichen könnte. Tests:
   `tests/test_v297_outlook_calendar_sync.py::test_write_sync_bookkeeping_never_changes_updated_at`
   (reproduziert exakt den unter Punkt 1 nachgebauten `onupdate`-Mechanismus direkt gegen
   `_write_sync_bookkeeping()` und beweist die Selbstreferenz-Lösung) und
   `test_write_sync_bookkeeping_rejects_a_row_with_unrelated_dirty_state` (die zweite,
   unabhängige Absicherung, siehe dortiger Docstring) sowie die auf ECHTE, frische Sessions je
   Lauf umgestellte `_check_no_oscillation()` (simuliert einen neuen Cron-Prozess je Tick, wie
   ausdrücklich verlangt, statt einer über alle sieben Läufe wiederverwendeten Session)."""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete as sa_delete, func, or_, select, update as sa_update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .calendar_events import zeitraum_berlin
from .grunddaten import einzelzeile
from .auth import resolve_account_display
from .email_sending import get_graph_access_token, load_smtp_settings
from .models import AppUser, CalendarEvent, OperationalResource, OutlookCalendarSyncState, OutlookDeleteOrder, OutlookSeriesOccurrence, OutlookSyncSettings

logger = logging.getLogger("app.outlook_calendar_sync")
# Eigener Logger-Name für die abschaltbare Diagnosezeile (seit 1.7.4) -- getrennt vom
# Warn-Logger oben, damit sie sich unabhängig davon per Logging-Konfiguration UND per
# ERP_OUTLOOK_SYNC_DIAGNOSTICS gezielt ein-/ausschalten lässt.
diag_logger = logging.getLogger("app.outlook_calendar_sync.diagnostics")

BERLIN = ZoneInfo("Europe/Berlin")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_TIMEOUT = 30
GANZTAG_ZEITZONE = "Europe/Berlin"  # steht in Microsofts Liste (dateTimeTimeZone, „Additional time zones“)

# changeKey war bis 1.7.5 Teil dieser Liste -- $select wird von Graph für Kalender-Delta-Abfragen
# nachweislich ignoriert (siehe Moduldocstring "Nachtrag seit 1.7.5"), changeKey kam über diesen
# Weg nie an. Entfernt, damit die Anfrage nicht etwas verspricht, das sie nicht liefert -- die
# Echo-Erkennung läuft seither über @odata.etag, das unabhängig von $select immer mitkommt.
_EVENT_SELECT = "id,subject,start,end,isAllDay,location,body,lastModifiedDateTime,recurrence,type,sensitivity"


def diagnostics_enabled() -> bool:
    """ERP_OUTLOOK_SYNC_DIAGNOSTICS=1 (o. ä.) in der Umgebung -- wird bei JEDEM Aufruf frisch
    gelesen (kein Modul-Konstante-Caching), da scripts/sync_outlook_calendars.py bei jedem
    Cron-Tick ohnehin ein komplett neuer Prozess ist, der .env neu lädt (siehe dortiger
    Kopfkommentar) -- ein Umschalten in .env wirkt dadurch bereits beim nächsten Lauf, ohne den
    laufenden Webserver neu starten zu müssen."""
    return os.getenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", "").strip().lower() in ("1", "true", "yes")


def _diag(event_id, *, updated_at, outlook_synced_at, graph_last_modified_raw, graph_last_modified_parsed,
           etag_gespeichert, etag_eingehend, entscheidung: str) -> None:
    """Die EINE Stelle, die die Diagnosezeile formatiert -- bewusst nie Titel/Ort/Notiz (Punkt 6
    bleibt unverändert in Kraft), der Versionsstempel ist ein bedeutungsloser, von Graph
    vergebener Wert, kein Termininhalt. Aufrufer prüfen diagnostics_enabled() VORHER, damit im
    Normalbetrieb nicht einmal die String-Formatierung anfällt.

    **Feldname seit 1.7.5 geändert** (change_key_gespeichert/change_key_eingehend ->
    etag_gespeichert/etag_eingehend, siehe Moduldocstring "Nachtrag seit 1.7.5") -- ein
    Betreiber, der nach den alten Feldnamen filtert/grep't, findet sie nicht mehr, das ist
    beabsichtigt: die alten Namen versprachen einen Wert (Graphs changeKey), den die Delta-
    Antwort nachweislich nie geliefert hat."""
    diag_logger.info(
        "event_id=%s updated_at=%s outlook_synced_at=%s graph_last_modified_raw=%s "
        "graph_last_modified_parsed=%s etag_gespeichert=%s etag_eingehend=%s entscheidung=%s",
        event_id, updated_at, outlook_synced_at, graph_last_modified_raw, graph_last_modified_parsed,
        etag_gespeichert, etag_eingehend, entscheidung,
    )

# Outlooks sensitivity-Werte, die als "privat" gelten (Muster Nachtrag Punkt 2 im Moduldocstring)
# -- "personal" bleibt bewusst AUSSEN VOR: eine geringere Vertraulichkeitsstufe als
# "private"/"confidential", die Anfrage nannte ausdrücklich nur "privat"/"vertraulich".
_PRIVATE_SENSITIVITIES = frozenset({"private", "confidential"})


def _is_private_sensitivity(value: str | None) -> bool:
    return value in _PRIVATE_SENSITIVITIES


def _outgoing_sensitivity(is_private: bool) -> str:
    return "private" if is_private else "normal"


class OutlookSyncError(Exception):
    """Wird von den low-level Graph-Aufrufen unten geworfen -- str(exc) kann Teile der Anfrage
    enthalten (siehe Punkt 6) und darf deshalb NIE geloggt werden, nur type(exc).__name__.
    status und codes (seit 1.9.158) sagen dem Aufrufer, was geschehen ist: HTTP-Status und Graphs Fehlercodes, klein geschrieben, ohne Inhalt."""

    def __init__(self, nachricht: str, *, status: int | None = None, codes: frozenset[str] = frozenset()):
        super().__init__(nachricht)
        self.status = status
        self.codes = codes


# Seit 1.9.158: laut Microsoft („Token duration“, „Synchronization reset“) laufen Delta-Links bei Outlook ohne feste Frist ab, sobald der Zwischenspeicher voll ist: 410 oder „a 40X-series error with
# error codes such as syncStateNotFound“. Dann gehört alles von vorn eingelesen.
_DELTA_ABGELAUFEN_CODES = frozenset({"syncstatenotfound", "syncstateinvalid", "resyncrequired", "errorinvalidsyncstatedata"})


def _delta_abgelaufen(exc: OutlookSyncError) -> bool:
    if exc.status == 410:
        return True
    return exc.status is not None and 400 <= exc.status < 500 and bool(exc.codes & _DELTA_ABGELAUFEN_CODES)


def _fehlercodes(antwort: str) -> frozenset[str]:
    """Alle Fehlercodes einer Graph-Antwort, auch die verschachtelten („innerError“): Microsoft nennt den genauesten oft dort."""
    try:
        fehler = json.loads(antwort).get("error")
    except (ValueError, AttributeError):
        return frozenset()
    codes = set()
    while isinstance(fehler, dict):
        if isinstance(fehler.get("code"), str):
            codes.add(fehler["code"].lower())
        fehler = fehler.get("innerError") or fehler.get("innererror")
    return frozenset(codes)


# ---------------------------------------------------------------------------
# Zeitzonen (Punkt 3)
# ---------------------------------------------------------------------------


def to_utc(local_naive: datetime) -> datetime:
    """CalendarEvent.start_at/end_at (naive Europe/Berlin-Ortszeit) -> naive UTC, für Graph."""
    return local_naive.replace(tzinfo=BERLIN).astimezone(timezone.utc).replace(tzinfo=None)


def to_berlin(utc_naive: datetime) -> datetime:
    """Umkehrung von to_utc() -- naive UTC (aus Graph) -> naive Europe/Berlin-Ortszeit, fürs
    Speichern in CalendarEvent.start_at/end_at."""
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(BERLIN).replace(tzinfo=None)


_OVERLONG_FRACTION_RE = re.compile(r"(\.\d{6})\d+")


def _parse_graph_datetime(value: str) -> datetime:
    """Graph liefert ISO-8601 mit Sekundenbruchteilen und optionalem 'Z'/Offset -- wir haben nie
    einen anderen als UTC angefragt (siehe Moduldocstring Punkt 3), interpretieren aber auch ein
    mitgeliefertes Offset korrekt, statt es zu ignorieren.

    **Zweite Untersuchungsrunde (seit 1.7.4), real gefundener, unabhängiger Präzisions-Fehler**:
    Microsofts lastModifiedDateTime/start/end tragen üblicherweise SIEBEN Nachkommastellen
    (100-Nanosekunden-"Ticks", z. B. "2026-09-26T09:37:34.6472860Z") --
    `datetime.fromisoformat()` akzeptiert das erst ab Python 3.11 (vorher: ValueError bei jeder
    Bruchteilsekundenlänge außer 0/3/6 Ziffern -- ein sehr verbreiteter, dokumentierter Stolperstein
    beim Arbeiten mit der Graph-API). Welcher Python auf dem Produktivserver tatsächlich läuft, war
    hier nicht geprüft/dokumentiert -- statt uns auf eine Mindestversion zu verlassen, kürzen wir
    Bruchteilsekunden VOR dem Parsen selbst auf maximal sechs Stellen (Mikrosekunden-Auflösung,
    reine Kürzung wie Pythons eigener 3.11+-Parser es an dieser Stelle ebenfalls tut, siehe
    tests/test_v297_outlook_calendar_sync.py) -- macht das Verhalten unabhängig von der
    Python-Version. Nicht als bewiesene Ursache des gemeldeten Schaukelns behauptet (siehe
    Moduldocstring "Zweite Untersuchungsrunde"), aber ein eigenständiger, real gefundener
    Härtungsbedarf."""
    text = _OVERLONG_FRACTION_RE.sub(r"\1", value.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Einstellungen (Singleton, Muster app/ai_settings.py)
# ---------------------------------------------------------------------------


def load_outlook_sync_settings(db: Session) -> OutlookSyncSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, OutlookSyncSettings)


def update_outlook_sync_settings(db: Session, *, enabled: bool) -> OutlookSyncSettings:
    settings = load_outlook_sync_settings(db)
    settings.enabled = enabled
    db.commit()
    db.refresh(settings)
    return settings


def is_outlook_sync_available(db: Session, user: AppUser | None = None) -> bool:
    """Gesamtschalter an UND Graph-Zugangsdaten vorhanden (dieselben wie beim E-Mail-Versand,
    siehe OutlookSyncSettings-Klassendocstring) -- prüft, wenn user übergeben wird, zusätzlich
    dessen eigenes outlook_mailbox. Reicht als schnelle Vorprüfung (Muster
    app/modules.py::is_module_enabled()), ohne selbst schon Netzwerkzugriff auszulösen."""
    settings = load_outlook_sync_settings(db)
    if not settings.enabled:
        return False
    smtp = load_smtp_settings(db)
    if not (smtp.graph_tenant_id and smtp.graph_client_id and smtp.graph_client_secret_encrypted):
        return False
    if user is not None and not user.outlook_mailbox:
        return False
    return True


def postfach_normal(adresse: str | None) -> str | None:
    """Eine Adresse, wie sie in der Datenbank steht (seit 1.9.159): klein, ohne Leerzeichen, leer ist keine. Microsoft unterscheidet Groß und Klein hier nicht, ein eindeutiger Index schon."""
    return (adresse or "").strip().lower() or None


@dataclass(frozen=True)
class Postfach:
    """Ein Postfach und wem es gehört: einem Konto oder einem Gerät, genau einem von beiden (seit 1.9.161). Was ein Lauf an einer Zeile setzt und wonach er Zeilen sucht, kommt nur von hier."""
    adresse: str
    konto: AppUser | None = None
    geraet: OperationalResource | None = None

    @property
    def besitzer(self) -> dict:
        return {"owner_user_id": self.konto.id if self.konto else None, "resource_id": self.geraet.id if self.geraet else None}

    @property
    def im_protokoll(self) -> str:
        return f"app_user_id={self.konto.id}" if self.konto else f"resource_id={self.geraet.id}"

    def gehoert(self, modell):
        """Bedingung auf CalendarEvent oder OutlookSeriesOccurrence."""
        return modell.owner_user_id == self.konto.id if self.konto else modell.resource_id == self.geraet.id


def postfach_des_kontos(konto: AppUser) -> Postfach | None:
    adresse = postfach_normal(konto.outlook_mailbox)
    return Postfach(adresse, konto=konto) if adresse else None


def postfach_des_geraets(geraet: OperationalResource) -> Postfach | None:
    adresse = postfach_normal(geraet.outlook_mailbox)
    return Postfach(adresse, geraet=geraet) if adresse else None


def alle_postfaecher(db: Session, *, nur_aktive: bool = True) -> list[Postfach]:
    """Was der Cron abgleicht: aktive Konten und aktive Geräte mit einem Postfach. Die Übersicht in den Einstellungen nennt auch die inaktiven."""
    konten = select(AppUser).where(AppUser.outlook_mailbox.is_not(None)).order_by(AppUser.id)
    geraete = select(OperationalResource).where(OperationalResource.outlook_mailbox.is_not(None)).order_by(OperationalResource.id)
    if nur_aktive:
        konten, geraete = konten.where(AppUser.active.is_(True)), geraete.where(OperationalResource.active.is_(True))
    return [p for p in [*map(postfach_des_kontos, db.scalars(konten).all()), *map(postfach_des_geraets, db.scalars(geraete).all())] if p is not None]


def ziel_postfach(event: CalendarEvent) -> str | None:
    """Wohin ein Termin gehört: ins Postfach seines Besitzers, Konto oder Gerät."""
    besitzer = event.owner or event.resource
    return postfach_normal(besitzer.outlook_mailbox) if besitzer is not None else None


class PostfachVergeben(ValueError):
    """Ein Postfach gehört einem Konto oder einem Gerät (seit 1.9.159, Gerät seit 1.9.161); der Text nennt, wem."""


def postfach_pruefen(db: Session, adresse: str | None, *, konto_id: int | None = None, geraet_id: int | None = None) -> str | None:
    """Die Adresse für ein Konto oder Gerät, vor dem Speichern -- wirft PostfachVergeben, wenn sie schon jemand anderem gehört. Zwei am selben Postfach legten sonst jeden Termin zweimal an. Die
    eindeutigen Spalten sichern je Tabelle ab, die Prüfung über beide Tabellen steht nur hier."""
    adresse = postfach_normal(adresse)
    if adresse is None:
        return None
    konto = db.scalar(select(AppUser).where(AppUser.outlook_mailbox == adresse))
    if konto is not None and konto.id != konto_id:
        raise PostfachVergeben(f"Dieses Postfach gehört schon dem Konto „{konto.username}“.")
    geraet = db.scalar(select(OperationalResource).where(OperationalResource.outlook_mailbox == adresse))
    if geraet is not None and geraet.id != geraet_id:
        raise PostfachVergeben(f"Dieses Postfach gehört schon dem Gerät „{geraet.name}“.")
    return adresse


def postfach_gewechselt(db: Session, *, konto_id: int | None = None, geraet_id: int | None = None, alt: str | None, neu: str | None) -> None:
    """Ein Konto oder Gerät bekommt ein anderes oder kein Postfach (seit 1.9.160), im selben Commit wie die Änderung, ohne Netz. Wer ein Postfach neu bekommt, liest es ganz: Termine, die schon im ERP stehen,
    gehören ihm erst, wenn der Abruf sie sieht. Ohne Postfach fallen die Serienvorkommen weg, sie sind ein Schnappschuss, den niemand mehr nachzieht. Die Einzeltermine bleiben im ERP und behalten
    ihre Kennung: kommt dasselbe Postfach zurück, finden sie sich wieder, und Löschen erreicht es weiter."""
    if alt == neu:
        return
    if neu is None:
        db.execute(sa_delete(OutlookSeriesOccurrence).where(OutlookSeriesOccurrence.owner_user_id == konto_id if konto_id is not None else OutlookSeriesOccurrence.resource_id == geraet_id))
        return
    db.execute(sa_update(OutlookCalendarSyncState).where(OutlookCalendarSyncState.postfach == neu).values(delta_link=None))


def get_or_create_sync_state(db: Session, postfach: str) -> OutlookCalendarSyncState:
    """Der Stand eines Postfachs. Zwei Prozesse können ihn zugleich anlegen: der zweite läuft in den eindeutigen Schlüssel und nimmt die Zeile des ersten."""
    postfach = postfach_normal(postfach)
    state = db.scalar(select(OutlookCalendarSyncState).where(OutlookCalendarSyncState.postfach == postfach))
    if state is not None:
        return state
    try:
        with db.begin_nested():
            state = OutlookCalendarSyncState(postfach=postfach)
            db.add(state)
            db.flush()
    except IntegrityError:
        state = db.scalar(select(OutlookCalendarSyncState).where(OutlookCalendarSyncState.postfach == postfach))
    db.commit()
    return state


# ---------------------------------------------------------------------------
# Sperre je Postfach (seit 1.9.159)
# ---------------------------------------------------------------------------
#
# Cron, das Öffnen von /kalender und das Senden beim Speichern laufen in verschiedenen Prozessen (zwei gunicorn-Arbeitsprozesse, ein Cron-Prozess). Zwei gleichzeitig konnten denselben Termin
# zweimal nach Outlook legen (zwei POST, die zweite Kennung überschreibt die erste, der Termin der ersten kommt beim nächsten Abruf als neu zurück) und einen neuen Outlook-Termin zweimal im ERP
# anlegen. Eine Zeilensperre scheidet aus: sie hielte über Minuten eine Datenbankverbindung und eine Transaktion, und der Lauf committet je Termin (Regel 35). Deshalb eine Belegung in der Zeile
# des Postfachs: ein bedingtes UPDATE entscheidet, unter PostgreSQL wie unter SQLite, über Prozesse hinweg. Stirbt ein Prozess, läuft sie nach SPERRE_GILT ab; ein lebender Lauf erneuert sie.
# Fernlöschen braucht sie nicht: es legt nichts an.

SPERRE_GILT = timedelta(minutes=10)
_SPERRE_ERNEUERN_ALLE = 60  # Sekunden


class SperreVerloren(OutlookSyncError):
    """Der Lauf stand länger als SPERRE_GILT still, ein anderer hat das Postfach übernommen -- dieser hört auf."""


class _Sperre:
    def __init__(self, db: Session, state_id: int, kennung: str):
        self.db, self.state_id, self.kennung = db, state_id, kennung
        self._zuletzt = time.monotonic()

    def _bedingung(self):
        return (OutlookCalendarSyncState.id == self.state_id, OutlookCalendarSyncState.lauf_kennung == self.kennung)

    def halten(self) -> None:
        """Vor jedem Netzaufruf eines Laufs; schreibt höchstens einmal je Minute. Nie mit offenen Änderungen aufrufen (committet)."""
        if time.monotonic() - self._zuletzt < _SPERRE_ERNEUERN_ALLE:
            return
        treffer = self.db.execute(sa_update(OutlookCalendarSyncState).where(*self._bedingung()).values(lauf_seit=datetime.utcnow())).rowcount
        self.db.commit()
        self._zuletzt = time.monotonic()
        if treffer != 1:
            raise SperreVerloren("Ein anderer Lauf hat dieses Postfach übernommen.")

    def freigeben(self) -> None:
        """Nur die eigene Belegung. Was ein Fehler offen ließ, geht vorher zurück; eine Freigabe, die scheitert, läuft nach SPERRE_GILT von selbst ab."""
        try:
            self.db.rollback()
            self.db.execute(sa_update(OutlookCalendarSyncState).where(*self._bedingung()).values(lauf_kennung=None, lauf_seit=None))
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.warning("Sperre des Postfachs nicht freigegeben (Stand %s, Fehlerart=%s).", self.state_id, type(exc).__name__)


def _sperre_nehmen(db: Session, postfach: str) -> _Sperre | None:
    """Die Belegung des Postfachs -- None, solange ein anderer Lauf sie hält."""
    state = get_or_create_sync_state(db, postfach)
    state_id = state.id
    jetzt = datetime.utcnow()
    kennung = uuid.uuid4().hex
    treffer = db.execute(sa_update(OutlookCalendarSyncState).where(
        OutlookCalendarSyncState.id == state_id,
        or_(OutlookCalendarSyncState.lauf_seit.is_(None), OutlookCalendarSyncState.lauf_seit < jetzt - SPERRE_GILT),
    ).values(lauf_kennung=kennung, lauf_seit=jetzt)).rowcount
    db.commit()
    return _Sperre(db, state_id, kennung) if treffer == 1 else None


# ---------------------------------------------------------------------------
# Low-level Graph-Zugriff
# ---------------------------------------------------------------------------


def _graph_call(token: str, url: str, *, method: str = "GET", payload: dict | None = None,
                extra_headers: dict | None = None) -> dict | None:
    """Ein einzelner Graph-Aufruf -- gibt das geparste JSON zurück (None bei 204 No Content, z.
    B. nach DELETE). Wirft OutlookSyncError bei jedem Fehler; die Nachricht selbst wird NIE
    geloggt (siehe Moduldocstring Punkt 6), nur an den Aufrufer zur Anzeige durchgereicht, falls
    dieser sie einem Menschen zeigen will (z. B. "Verbindung testen")."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        **(extra_headers or {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=GRAPH_TIMEOUT) as resp:
            body = resp.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        hint = " Häufigste Ursache: das Postfach ist der Anwendung nicht über eine Exchange-RBAC-Zugriffsrichtlinie freigegeben -- das Postfach in die Gruppe ERP-Zugriff aufnehmen." if e.code == 403 else ""
        raise OutlookSyncError(f"Microsoft-Graph-Aufruf fehlgeschlagen ({e.code}): {detail}{hint}", status=e.code, codes=_fehlercodes(detail)) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise OutlookSyncError(f"Verbindung zu Microsoft Graph fehlgeschlagen: {e}") from e


def _mailbox_events_url(mailbox: str) -> str:
    return f"{GRAPH_BASE}/users/{urllib.parse.quote(mailbox)}/events"


def _zeiten_an_graph(event: CalendarEvent) -> dict:
    """Beginn und Ende für Graph. Ganztägig (seit 1.9.157): Microsoft verlangt Mitternacht in derselben Zeitzone („isAllDay“), und das Ende ist der Tag NACH dem letzten; im ERP ist
    end_at der letzte Tag selbst. Bis 1.9.156 ging auch das in UTC hinaus: 23:00 des Vortags, Beginn gleich Ende."""
    if not event.all_day:
        return {"start": {"dateTime": to_utc(event.start_at).isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": to_utc(event.end_at).isoformat(), "timeZone": "UTC"}}
    erster = event.start_at.date()
    letzter = max(erster, event.end_at.date())
    return {"start": {"dateTime": f"{erster.isoformat()}T00:00:00", "timeZone": GANZTAG_ZEITZONE},
            "end": {"dateTime": f"{(letzter + timedelta(days=1)).isoformat()}T00:00:00", "timeZone": GANZTAG_ZEITZONE}}


def _ganztag_tag(wert: dict) -> date:
    """Der Tag aus einem Beginn oder Ende eines ganztägigen Termins. Graph liefert Mitternacht und nennt dazu „UTC“, auch für einen Termin, der in Berlin angelegt wurde: das ist ein Kalendertag,
    kein Zeitpunkt, der Datumsteil gilt. Kommt doch eine andere Uhrzeit (23:00 des Vortags), war es Mitternacht in Berlin."""
    zeit = _parse_graph_datetime(wert["dateTime"])
    return zeit.date() if zeit.time() == datetime.min.time() else to_berlin(zeit).date()


def _zeiten_aus_graph(item: dict) -> tuple[datetime, datetime]:
    """start_at und end_at aus einer Graph-Zeile, beide Wege (Delta, Serien). Ganztägig (seit 1.9.157): je Mitternacht, end_at der letzte Tag -- wie der Dialog im Kalender. Bis 1.9.156 wurde
    auch das umgerechnet: der 10.11. kam als 10.11. 01:00 bis 11.11. 01:00 an und stand an zwei Tagen."""
    if not item.get("isAllDay"):
        return to_berlin(_parse_graph_datetime(item["start"]["dateTime"])), to_berlin(_parse_graph_datetime(item["end"]["dateTime"]))
    erster = _ganztag_tag(item["start"])
    letzter = max(erster, _ganztag_tag(item["end"]) - timedelta(days=1))
    return datetime.combine(erster, datetime.min.time()), datetime.combine(letzter, datetime.min.time())


def _event_payload(event: CalendarEvent) -> dict:
    body_text = event.notes or ""
    return {
        "subject": event.title,
        "isAllDay": event.all_day,
        **_zeiten_an_graph(event),
        "location": {"displayName": event.location or ""},
        "body": {"contentType": "Text", "content": body_text},
        "sensitivity": _outgoing_sensitivity(event.is_private),
    }


def _write_sync_bookkeeping(db: Session, row: CalendarEvent, *, outlook_synced_at: datetime, **extra_columns) -> None:
    """Die EINE Stelle für reine Sync-Buchhaltung (outlook_event_id/outlook_etag/
    outlook_synced_at) -- **löst `_mark_synced()` ab (seit 1.7.6), siehe Moduldocstring
    "Nachtrag (seit 1.7.6)" für die vollständige Herleitung.**

    **Der eigentliche, empirisch nachgewiesene Mechanismus, den diese Funktion beseitigt** (per
    `echo=True`-Mitschnitt gegen SQLite UND eine echte PostgreSQL-Instanz bestätigt, siehe
    Moduldocstring): `Column(..., onupdate=datetime.utcnow)` ist eine COLUMN-, nicht eine
    ORM-Mapper-Eigenschaft -- sie greift bei JEDER `UPDATE`-Anweisung gegen diese Tabelle, egal ob
    sie über die ORM-Klasse (`update(CalendarEvent)`) oder das rohe Core-`Table`-Objekt
    (`update(CalendarEvent.__table__)`) abgesetzt wird, SOBALD `updated_at` NICHT explizit in
    `.values()` auftaucht -- ein bloßes Weglassen der Spalte reicht deshalb NICHT aus, um sie vor
    `onupdate` zu schützen (ein erster Entwurf dieser Funktion ging genau davon aus und wurde durch
    einen bereits bestehenden Test, `test_successful_push_does_not_let_updated_at_drift_...`,
    widerlegt -- ein `UPDATE calendar_events SET outlook_event_id=?, outlook_synced_at=?,
    updated_at=?` erschien trotz fehlendem `updated_at`-Parameter in der erzeugten SQL). Die
    tatsächlich wirksame Absicherung: `updated_at` wird IMMER explizit auf eine SELBSTREFERENZ
    gesetzt (`CalendarEvent.updated_at`, kompiliert zu `SET updated_at = calendar_events.
    updated_at`) -- ein EXPLIZIT gegebener Wert unterdrückt `onupdate` (das laut SQLAlchemy nur
    greift, wenn für die Spalte KEIN Wert übergeben wurde), ohne dass der aktuelle Wert vorher in
    Python bekannt sein müsste (die Datenbank liest ihn sich selbst aus derselben Zeile, atomar,
    unabhängig von jeder Autoflush-Reihenfolge). Per direktem Vorher/Nachher-Vergleich bestätigt:
    `DRIFT = 0:00:00`, exakt, nicht nur "meist richtig".

    `extra_columns` wird zusätzlich explizit gegen ein versehentlich mitgegebenes `updated_at`
    geprüft (würde sonst von der oben stehenden Selbstreferenz stillschweigend überschrieben,
    ein Fehler soll hier aber laut statt still bleiben).

    **Zweite, unabhängige Absicherung**: die Selbstreferenz schützt nur VOR der EIGENEN Anweisung
    -- trägt `row` beim Aufruf bereits eine ANDERE, über gewöhnliches `setattr()` erzeugte
    Dirty-Markierung (z. B. ein Aufrufer, der versehentlich wieder `row.outlook_etag = x` VOR
    diesem Aufruf setzt, statt es als `extra_columns` zu übergeben), autoflusht `db.execute()`
    diese Markierung ZUERST über eine GEWÖHNLICHE ORM-UPDATE-Anweisung -- und DIESE bezieht
    `onupdate` mit ein, BEVOR die Selbstreferenz greifen kann (empirisch bestätigt: ein
    `event.title = "..."` unmittelbar vor diesem Aufruf erzeugt trotz Selbstreferenz einen
    echten, persistierten Millisekunden-Versatz). `db.is_modified(row)` prüft das deshalb VORAB
    und bricht mit einer klaren Fehlermeldung ab, statt den Fehler dieser Datei ein drittes Mal
    still zu wiederholen -- jeder der drei Aufrufer unten flusht/committet eine echte inhaltliche
    Änderung deshalb IMMER VOR diesem Aufruf, nie danach."""
    if "updated_at" in extra_columns:
        raise AssertionError("Sync-Buchhaltung darf updated_at nie beruehren -- siehe Moduldocstring \"Nachtrag (seit 1.7.6)\".")
    if db.is_modified(row):
        raise AssertionError(
            "_write_sync_bookkeeping() auf einer bereits dirty Zeile aufgerufen -- der davor "
            "ausgelöste Autoflush würde onupdate=datetime.utcnow trotz Selbstreferenz bumpen, "
            "siehe Docstring \"Zweite, unabhängige Absicherung\". Echte inhaltliche Änderungen "
            "zuerst db.flush()/db.commit()."
        )
    db.execute(sa_update(CalendarEvent).where(CalendarEvent.id == row.id).values(
        outlook_synced_at=outlook_synced_at, updated_at=CalendarEvent.updated_at, **extra_columns,
    ))
    db.commit()
    db.refresh(row)


def fehler_text(art: str | None, status: int | None) -> str | None:
    """Was der letzte Fehler eines Postfachs bedeutet und was zu tun ist (seit 1.9.162). Nur aus Art und Status: den Text von Microsoft zeigt nichts an, er kann Inhalte tragen (Regel 18). 403 heißt
    bei uns „nicht in der Gruppe“, nicht „Zugangsdaten falsch“ (Regel 17). Anmelden scheitert in app/email_sending.py::get_graph_access_token() mit ValueError."""
    if not art:
        return None
    if status == 403:
        return "Postfach nicht freigegeben: in Microsoft 365 in die Gruppe ERP-Zugriff aufnehmen. Eine Änderung dort wirkt nach bis zu zwei Stunden."
    if status == 401 or art == "ValueError":
        return "Microsoft lehnt die Anmeldung ab: Zugangsdaten unter „E-Mail und Microsoft 365“ prüfen."
    if status == 404:
        return "Microsoft kennt dieses Postfach nicht: Adresse prüfen."
    if art == "OutlookSyncError":
        return f"Microsoft hat nicht geantwortet{f' (Status {status})' if status else ''}. Der nächste Lauf versucht es wieder."
    return f"Der Abgleich ist gescheitert ({art}). Der nächste Lauf versucht es wieder."


def postfach_uebersicht(db: Session) -> list[dict]:
    """Der Stand je Postfach für die Einstellungen (seit 1.9.162, nur Admin). Liest nur, fragt Microsoft nicht. „wartet“ zählt, was der nächste Lauf sendet, dieselbe Bedingung wie _needs_push(), dazu
    Termine, die nach einem Wechsel noch im alten Postfach liegen. Eine je Postfach: es sind wenige."""
    jetzt = datetime.utcnow()
    staende = {s.postfach: s for s in db.scalars(select(OutlookCalendarSyncState))}
    zeilen = []
    for postfach in alle_postfaecher(db, nur_aktive=False):
        stand = staende.get(postfach.adresse)
        wartet = db.scalar(select(func.count()).select_from(CalendarEvent).where(postfach.gehoert(CalendarEvent), or_(
            CalendarEvent.outlook_event_id.is_(None), CalendarEvent.outlook_synced_at.is_(None), CalendarEvent.updated_at > CalendarEvent.outlook_synced_at,
            and_(CalendarEvent.outlook_postfach.is_not(None), CalendarEvent.outlook_postfach != postfach.adresse))))
        loeschen = db.scalar(select(func.count()).select_from(OutlookDeleteOrder).where(OutlookDeleteOrder.postfach == postfach.adresse))
        besitzer = postfach.konto or postfach.geraet
        zeilen.append({
            "adresse": postfach.adresse, "art": "konto" if postfach.konto else "geraet", "besitzer_id": besitzer.id,
            "name": resolve_account_display(db, postfach.konto)["full_name"] if postfach.konto else postfach.geraet.name, "aktiv": bool(besitzer.active),
            "letzter_lauf": stand.last_synced_at if stand else None,
            "letzter_fehler": fehler_text(stand.last_error_type, stand.last_error_status) if stand else None,
            "fehler_am": stand.last_error_at if stand else None,
            "laeuft_seit": stand.lauf_seit if stand and stand.lauf_seit and stand.lauf_seit >= jetzt - SPERRE_GILT else None,
            "wartet": wartet, "loeschen_offen": loeschen,
        })
    return zeilen


def _termin_senden(token: str, adresse: str, event: CalendarEvent) -> tuple[dict | None, dict, bool]:
    """PATCH oder POST in das Postfach -- gibt Antwort, Spalten für die Buchhaltung und „neu angelegt“ zurück, die eine Stelle für Speichern und Lauf. Seit 1.9.160: kennt das Postfach den Termin nicht
    (404), legt der Lauf ihn dort neu an; der Abruf davor hätte ein Löschen in Outlook gemeldet. Bis 1.9.159 scheiterte so jeder Lauf am selben Termin, ohne Ende (Befund XB4)."""
    if event.outlook_event_id:
        try:
            antwort = _graph_call(token, f"{_mailbox_events_url(adresse)}/{event.outlook_event_id}", method="PATCH", payload=_event_payload(event))
            return antwort, {"outlook_postfach": adresse}, False
        except OutlookSyncError as exc:
            if exc.status != 404:
                raise
    antwort = _graph_call(token, _mailbox_events_url(adresse), method="POST", payload=_event_payload(event))
    return antwort, {"outlook_postfach": adresse, "outlook_event_id": antwort["id"]}, True


def _needs_push(row: CalendarEvent) -> bool:
    if row.outlook_event_id is None:
        return True
    return row.outlook_synced_at is None or row.updated_at > row.outlook_synced_at


def _is_recurring(item: dict) -> bool:
    return bool(item.get("recurrence")) or item.get("type") == "seriesMaster"


def _is_series_instance(item: dict) -> bool:
    """Vorkommen oder Ausnahme einer Serie -- gehört ausschließlich dem calendarView-Weg
    (sync_series_occurrences()), nie dem Delta-Weg."""
    return item.get("type") in ("occurrence", "exception") or bool(item.get("seriesMasterId"))


def _plain_text_body(item: dict) -> str | None:
    body = item.get("body") or {}
    content = body.get("content")
    return content.strip() or None if content else None


# ---------------------------------------------------------------------------
# Push: lokale Änderung -> Outlook
# ---------------------------------------------------------------------------


def push_event_best_effort(db: Session, event_id: int) -> None:
    """Nach create_event()/update_event() in app/routers/calendar_events.py aufgerufen -- best
    effort: ein Graph-Fehler darf den bereits erfolgreich gespeicherten lokalen Termin nicht
    rückwirkend als Fehler erscheinen lassen (Muster app/tasks.py::notify_task_assignment()),
    deshalb kein Reraise, nur Protokollierung (Klassenname, kein Text, Punkt 6).

    Schlägt der Push fehl, bleibt outlook_synced_at unverändert (älter als updated_at bzw. ganz
    NULL) -- der nächste sync_user_calendar()-Lauf (Cron ODER nächstes Öffnen von /kalender)
    erkennt diesen Termin über _needs_push() dadurch zuverlässig erneut als "noch zu
    übertragen", siehe Moduldocstring "Nachtrag (seit 1.7.2)"."""
    event = db.get(CalendarEvent, event_id)
    if event is None:
        return
    adresse = ziel_postfach(event)
    if adresse is None or not is_outlook_sync_available(db):
        return
    diag = diagnostics_enabled()
    old_etag = event.outlook_etag  # vor jeder Mutation erfasst, für die Diagnosezeile
    if event.outlook_event_id and event.outlook_postfach and event.outlook_postfach != adresse:
        return  # das Postfach des Kontos wurde gewechselt: das klärt der nächste Lauf (_postfach_wechsel_aufloesen())
    # Seit 1.9.159: läuft gerade ein Abgleich dieses Postfachs, bleibt der Termin wartend und geht mit dem nächsten Lauf -- zwei gleichzeitige POST ergäben ihn zweimal.
    sperre = _sperre_nehmen(db, adresse)
    if sperre is None:
        if diag:
            _diag(event_id, updated_at=None, outlook_synced_at=None, graph_last_modified_raw=None, graph_last_modified_parsed=None,
                  etag_gespeichert=old_etag, etag_eingehend=None, entscheidung="push übersprungen (Postfach belegt, geht mit dem nächsten Lauf)")
        return
    try:
        smtp = load_smtp_settings(db)
        token = get_graph_access_token(smtp)
        # Seit 1.7.6 (siehe Moduldocstring "Nachtrag"): bleibt UNVERÄNDERT -- reines Pushen ändert
        # am lokalen Termin selbst nichts, nur an Outlooks Kopie davon. outlook_event_id/
        # outlook_etag werden deshalb NICHT mehr per setattr() vorab gesetzt (das hätte diese
        # Zeile für den gleich folgenden _write_sync_bookkeeping()-Aufruf unnötig dirty gemacht),
        # sondern als Teil DERSELBEN Buchhaltungs-Anweisung übergeben.
        version_to_sync = event.updated_at
        if diag:
            _diag(event.id, updated_at=version_to_sync, outlook_synced_at=event.outlook_synced_at,
                  graph_last_modified_raw=None, graph_last_modified_parsed=None,
                  etag_gespeichert=old_etag, etag_eingehend=None,
                  entscheidung="push versucht (best effort, nach create_event()/update_event())")
        response, bookkeeping, _neu = _termin_senden(token, adresse, event)
        # Seit 1.7.5 (siehe Moduldocstring "Nachtrag") -- @odata.etag statt changeKey: Graph liefert
        # es bei JEDER erfolgreichen Schreiboperation mit zurück, anders als changeKey ist es
        # außerdem dieselbe Annotation, die auch eine spätere Delta-Zeile trägt (dort KOMMT
        # changeKey nachweislich nie an, $select wird für Kalender-Delta ignoriert). Ohne einen
        # neuen Wert (z. B. ein PATCH ohne Body) bleibt outlook_etag auf dem alten Stand stehen und
        # die Zeitstempel-Logik greift beim nächsten Pull als Rückfall.
        new_etag = response.get("@odata.etag") if response is not None else None
        if new_etag:
            bookkeeping["outlook_etag"] = new_etag
        _write_sync_bookkeeping(db, event, outlook_synced_at=version_to_sync, **bookkeeping)
        if diag:
            # event.* ist HIER (nach _write_sync_bookkeeping()s db.refresh()) der tatsächlich
            # jetzt gespeicherte Wert -- eine frühere Fassung protokollierte hier fälschlich den
            # Wert VOR dem Push, siehe Moduldocstring "Nachtrag seit 1.7.5", Punkt 3.
            _diag(event.id, updated_at=event.updated_at, outlook_synced_at=event.outlook_synced_at,
                  graph_last_modified_raw=None, graph_last_modified_parsed=None,
                  etag_gespeichert=event.outlook_etag, etag_eingehend=None,
                  entscheidung="push erfolgreich")
    except Exception as exc:  # noqa: BLE001 -- best effort, siehe Docstring
        db.rollback()
        logger.warning("Push nach Outlook fehlgeschlagen (event_id=%s, Fehlerart=%s).", event_id, type(exc).__name__)
        if diag:
            _diag(event_id, updated_at=None, outlook_synced_at=None, graph_last_modified_raw=None,
                  graph_last_modified_parsed=None, etag_gespeichert=old_etag, etag_eingehend=None,
                  entscheidung=f"push fehlgeschlagen ({type(exc).__name__})")
    finally:
        sperre.freigeben()


# ---------------------------------------------------------------------------
# Fernlöschen und Umzug (seit 1.9.160)
# ---------------------------------------------------------------------------
#
# Wo ein Termin in Outlook liegt, steht an ihm (outlook_postfach), nicht am Besitzer: der kann längst ein anderer sein oder kein Postfach haben (Befund XC1). Gelöscht wird über einen Auftrag: er
# überlebt ein gescheitertes Netz, der nächste Lauf versucht es wieder, und solange er steht, nimmt der Abruf die Kennung nicht wieder auf (bis 1.9.159 kam der Termin als neu zurück). 404 heißt:
# schon weg. 403 heißt: das Postfach ist nicht mehr freigegeben (Regel 17), das wird nicht wieder gut; der Auftrag fällt weg, die Kopie bleibt dort, das steht im Protokoll.


def _loeschauftrag(db: Session, postfach: str, kennung: str) -> None:
    """Ohne Commit, mehrfach unschädlich."""
    if db.scalar(select(OutlookDeleteOrder).where(OutlookDeleteOrder.postfach == postfach, OutlookDeleteOrder.outlook_event_id == kennung)) is None:
        db.add(OutlookDeleteOrder(postfach=postfach, outlook_event_id=kennung))


def _loeschauftraege_abarbeiten(db: Session, token: str) -> bool:
    """Alle offenen Aufträge, jeder für sich. Gibt zurück, ob die Termine aus Outlook weg sind; bei 403 fällt der Auftrag weg, die Kopie bleibt: das ist kein Erfolg."""
    alle_erledigt = True
    for auftrag in db.scalars(select(OutlookDeleteOrder).order_by(OutlookDeleteOrder.id)).all():
        auftrag_id = auftrag.id
        try:
            _graph_call(token, f"{_mailbox_events_url(auftrag.postfach)}/{auftrag.outlook_event_id}", method="DELETE")
        except OutlookSyncError as exc:
            if exc.status not in (403, 404):
                auftrag.last_error_type = type(exc).__name__
                auftrag.last_error_at = datetime.utcnow()
                db.commit()
                alle_erledigt = False
                logger.warning("Fernlöschen in Outlook fehlgeschlagen (Auftrag %s, Fehlerart=%s, Status=%s).", auftrag_id, type(exc).__name__, exc.status)
                continue
            if exc.status == 403:
                alle_erledigt = False
                logger.warning("Fernlöschen aufgegeben: das Postfach ist nicht freigegeben (Auftrag %s).", auftrag_id)
        db.delete(auftrag)
        db.commit()
    return alle_erledigt


def loeschauftraege_best_effort(db: Session) -> bool:
    """Nach dem Speichern oder Löschen und am Ende des Cron-Laufs. Wirft nie; was offen bleibt, versucht der nächste Lauf."""
    if not is_outlook_sync_available(db) or db.scalar(select(OutlookDeleteOrder.id).limit(1)) is None:
        return True
    try:
        return _loeschauftraege_abarbeiten(db, get_graph_access_token(load_smtp_settings(db)))
    except Exception as exc:  # noqa: BLE001 -- best effort, siehe Docstring
        db.rollback()
        logger.warning("Fernlöschen in Outlook fehlgeschlagen (Fehlerart=%s).", type(exc).__name__)
        return False


def wo_er_liegt(event: CalendarEvent) -> str | None:
    """Das Postfach eines Termins mit Kennung: vermerkt, sonst (Stand von vor 1.9.159) das seines Besitzers."""
    return event.outlook_postfach or ziel_postfach(event)


def besitzer_gewechselt(db: Session, event_id: int, *, alte_lage: str | None) -> None:
    """Der Termin hat einen anderen Besitzer (seit 1.9.160): er zieht um. Die Kopie im alten Postfach kommt als Auftrag weg, der Termin verliert seine Kennung und geht als neuer in das Postfach des
    neuen Besitzers; hat der keins, liegt er danach nur im ERP. Ohne Netz, auch bei ausgeschaltetem Abgleich. Bis 1.9.159 ging das PATCH mit der alten Kennung ans neue Postfach: 404, ohne Ende."""
    event = db.get(CalendarEvent, event_id)
    if event is None or event.outlook_event_id is None:
        return
    if alte_lage is not None:
        _loeschauftrag(db, alte_lage, event.outlook_event_id)
        db.flush()
    _write_sync_bookkeeping(db, event, outlook_synced_at=None, outlook_event_id=None, outlook_postfach=None, outlook_etag=None)


def try_delete_remote_event(db: Session, event: CalendarEvent) -> bool:
    """Vor dem lokalen Löschen (app/routers/calendar_events.py) aufgerufen, wenn der Termin
    bereits einen outlook_event_id trägt. Best effort (gibt True/False zurück, wirft nie) --
    schlägt die Fernlöschung fehl (z. B. Graph kurzzeitig nicht erreichbar), wird trotzdem lokal
    gelöscht (Nutzerabsicht hat Vorrang). Seit 1.9.160 bleibt dafür der Auftrag stehen, siehe oben."""
    if not event.outlook_event_id:
        return True
    ort = wo_er_liegt(event)
    if ort is None:
        return True  # liegt nirgends, wo das ERP hinkommt
    _loeschauftrag(db, ort, event.outlook_event_id)
    db.commit()
    return loeschauftraege_best_effort(db)


# ---------------------------------------------------------------------------
# Pull: Outlook-Änderungen -> lokal (Delta-Abfrage)
# ---------------------------------------------------------------------------


def _fetch_delta_pages(token: str, start_url: str, sperre: _Sperre | None = None) -> tuple[list[dict], str]:
    """Folgt @odata.nextLink, bis @odata.deltaLink kommt -- gibt alle gesammelten Zeilen plus
    den neuen deltaLink zurück (zum Speichern in OutlookCalendarSyncState.delta_link)."""
    items: list[dict] = []
    url = start_url
    while True:
        if sperre is not None:
            sperre.halten()
        page = _graph_call(token, url, method="GET")
        items.extend(page.get("value", []))
        next_link = page.get("@odata.nextLink")
        delta_link = page.get("@odata.deltaLink")
        if delta_link:
            return items, delta_link
        if not next_link:
            # Sollte laut Graph-Vertrag nicht vorkommen (jede Seite trägt entweder nextLink oder
            # deltaLink) -- Verteidigung in der Tiefe statt einer Endlosschleife.
            raise OutlookSyncError("Graph-Delta-Antwort ohne @odata.nextLink/@odata.deltaLink.")
        url = next_link


def _delta_holen(db: Session, state: OutlookCalendarSyncState, token: str, basis_url: str, counters: dict, sperre: _Sperre) -> tuple[list[dict], str, bool]:
    """Der Abruf eines Laufs -- gibt Zeilen, neuen Link und „das war der ganze Kalender“ zurück. Seit 1.9.158 setzt er sich selbst zurück, wenn der gespeicherte Link abgelaufen ist; bis dahin endete
    jeder weitere Lauf mit demselben Fehler und nichts kam mehr aus Outlook. Läuft auch der neue Abruf ab, bleibt es ein Fehler dieses Laufs, der Link ist schon weg."""
    voll = state.delta_link is None
    try:
        items, link = _fetch_delta_pages(token, state.delta_link or basis_url, sperre)
        return items, link, voll
    except OutlookSyncError as exc:
        if not _delta_abgelaufen(exc):
            raise
    state.delta_link = None
    db.commit()
    counters["delta_reset"] = 1
    logger.warning("Delta-Link abgelaufen, der Kalender wird neu eingelesen (Stand %s).", state.id)
    if diagnostics_enabled():
        diag_logger.info("delta stand=%s entscheidung=Link abgelaufen -> neu einlesen", state.id)
    items, link = _fetch_delta_pages(token, basis_url, sperre)
    return items, link, True


def _weggefallene_entfernen(db: Session, postfach: Postfach, token: str, items: list[dict], counters: dict, sperre: _Sperre) -> None:
    """Nach einem Abruf des ganzen Kalenders (seit 1.9.158): was dort fehlt, kann in der Zwischenzeit gelöscht worden sein -- „Resources that were deleted before the initial delta query aren't
    returned“, ein @removed kommt dafür nie. Gelöscht wird nur, was Graph einzeln mit 404 beantwortet: der Abruf selbst beweist nichts, events/delta ist für v1.0 nicht dokumentiert."""
    gesehen = {item.get("id") for item in items}
    zeilen = db.scalars(select(CalendarEvent).where(postfach.gehoert(CalendarEvent), CalendarEvent.outlook_event_id.is_not(None),
                                                    or_(CalendarEvent.outlook_postfach == postfach.adresse, CalendarEvent.outlook_postfach.is_(None)))).all()
    for zeile in zeilen:
        if zeile.outlook_event_id in gesehen:
            continue
        kennung = zeile.id
        sperre.halten()
        try:
            _graph_call(token, f"{_mailbox_events_url(postfach.adresse)}/{zeile.outlook_event_id}", method="GET")
        except OutlookSyncError as exc:
            if exc.status == 404 and zeile.planning_slot_id is not None:
                # seit 1.9.241: ein Termin der Plantafel kommt neu hinaus statt wegzufallen (Plantafel führend)
                _write_sync_bookkeeping(db, zeile, outlook_synced_at=None, outlook_event_id=None, outlook_postfach=None, outlook_etag=None)
                counters["plantafel"] += 1
            elif exc.status == 404:
                db.delete(zeile)
                db.commit()
                counters["deleted"] += 1
            else:
                logger.warning("Prüfen eines fehlenden Termins fehlgeschlagen (event_id=%s, Fehlerart=%s).", kennung, type(exc).__name__)


def _liegt_woanders(db: Session, postfach: Postfach) -> list[CalendarEvent]:
    return db.scalars(select(CalendarEvent).where(postfach.gehoert(CalendarEvent), CalendarEvent.outlook_event_id.is_not(None), CalendarEvent.outlook_postfach.is_not(None),
                                                  CalendarEvent.outlook_postfach != postfach.adresse)).all()


def _postfach_wechsel_aufloesen(db: Session, postfach: Postfach, counters: dict) -> None:
    """Termine dieses Kontos, die nach dem Abruf des ganzen neuen Postfachs noch im alten liegen (seit 1.9.160). Was das ERP angelegt hat, zieht um. Was aus dem alten Postfach stammt, gehört dorthin:
    im ERP fällt es weg, dort bleibt es -- hängt es an einem Projekt oder Angebot, bleibt es auch im ERP und geht als Termin des ERP ins neue Postfach. Aus dem alten Postfach gelöscht wird nur, was
    das ERP selbst dort angelegt hat: das alte kann längst jemand anderem gehören, oder die Adresse war ein Irrtum."""
    for zeile in _liegt_woanders(db, postfach):
        aus_outlook = zeile.external_source == "outlook"
        if aus_outlook and zeile.project_id is None and zeile.quote_id is None:
            db.delete(zeile)
            db.commit()
            counters["deleted"] += 1
            continue
        if not aus_outlook:
            _loeschauftrag(db, zeile.outlook_postfach, zeile.outlook_event_id)
            db.flush()
        _write_sync_bookkeeping(db, zeile, outlook_synced_at=None, outlook_event_id=None, outlook_postfach=None, outlook_etag=None, external_source="erp")


def _termin_im_postfach(db: Session, postfach: Postfach, kennung: str) -> CalendarEvent | None:
    """Der Termin zu einer Outlook-Kennung: die Kennung gilt nur in ihrem Postfach. Ersatzweise einer desselben Besitzers, der noch anderswo vermerkt ist (Adresse umbenannt, Stand von vor 1.9.159):
    Microsoft kennt ihn hier, also liegt er hier."""
    zeile = db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_postfach == postfach.adresse, CalendarEvent.outlook_event_id == kennung))
    if zeile is not None:
        return zeile
    zeile = db.scalar(select(CalendarEvent).where(postfach.gehoert(CalendarEvent), CalendarEvent.outlook_event_id == kennung))
    if zeile is not None:
        _write_sync_bookkeeping(db, zeile, outlook_synced_at=zeile.outlook_synced_at, outlook_postfach=postfach.adresse)
    return zeile


def _apply_delta_change(db: Session, postfach: Postfach, item: dict, counters: dict) -> int | None:
    """Verarbeitet EINE Delta-Zeile -- gibt die lokale CalendarEvent.id zurück, wenn eine
    Änderung angewendet wurde (damit die Push-Phase diese Zeile im selben Lauf nicht erneut
    anfasst), sonst None."""
    diag = diagnostics_enabled()  # einmal je Zeile geprüft, siehe diagnostics_enabled()-Docstring
    raw_last_modified = item.get("lastModifiedDateTime")
    # Seit 1.7.5 (siehe Moduldocstring "Nachtrag"): @odata.etag statt changeKey -- Graph liefert
    # changeKey in Delta-Zeilen nachweislich NIE (auch nicht über $select, das für Kalender-Delta
    # dokumentiert ignoriert wird), @odata.etag begleitet dagegen JEDE Entitätsdarstellung.
    incoming_etag = item.get("@odata.etag")
    graph_modified = _parse_graph_datetime(raw_last_modified) if raw_last_modified else None
    # Vorab, für die Diagnosezeile jeder Entscheidung nutzbar -- existiert die Zeile noch nicht
    # (Neuanlage) ODER handelt es sich um @removed/Serientermin/ungültig, bleibt sie None bzw.
    # wird gleich (Neuanlage-Zweig) ergänzt.
    auftrag = db.scalar(select(OutlookDeleteOrder).where(OutlookDeleteOrder.postfach == postfach.adresse, OutlookDeleteOrder.outlook_event_id == item["id"]))
    if auftrag is not None:
        # Seit 1.9.160: im ERP schon gelöscht oder umgezogen, das Löschen in Outlook steht noch aus -- die Kennung kommt nicht wieder herein.
        if "@removed" in item:
            db.delete(auftrag)
            db.commit()
        return None
    existing = _termin_im_postfach(db, postfach, item["id"])
    if existing is not None and (existing.owner_user_id, existing.resource_id) != (postfach.besitzer["owner_user_id"], postfach.besitzer["resource_id"]):
        # Seit 1.9.160: das Postfach gehört inzwischen jemand anderem, ein Besitzerwechsel im Dialog hätte die Kennung gelöst.
        _write_sync_bookkeeping(db, existing, outlook_synced_at=existing.outlook_synced_at, **postfach.besitzer)
    # Fallstrick, beim Bauen selbst gefunden: NIE Attribute eines ORM-Objekts NACH einem
    # db.delete()+db.commit() lesen (expire_on_commit löst dann einen Reload eines nicht mehr
    # existierenden Datensatzes aus -> ObjectDeletedError). Deshalb werden die Werte HIER, VOR
    # jeder Mutation, einmalig in reine Python-Variablen kopiert -- log() liest nur noch daraus.
    diag_id = existing.id if existing is not None else None
    diag_updated_at = existing.updated_at if existing is not None else None
    diag_outlook_synced_at = existing.outlook_synced_at if existing is not None else None
    diag_etag_stored = existing.outlook_etag if existing is not None else None

    _unset = object()  # Sentinel, NICHT None -- ein Override auf explizit None (z. B. "der neue
    # etag ist None") muss von "kein Override übergeben" unterscheidbar bleiben, sonst würde die
    # Diagnosezeile in genau diesem Fall fälschlich den ALTEN, nicht mehr aktuellen Wert zeigen.

    def log(entscheidung: str, *, event_id=_unset, updated_at=_unset, outlook_synced_at=_unset, etag_gespeichert=_unset) -> None:
        if not diag:
            return
        _diag(
            event_id if event_id is not _unset else diag_id,
            updated_at=updated_at if updated_at is not _unset else diag_updated_at,
            outlook_synced_at=outlook_synced_at if outlook_synced_at is not _unset else diag_outlook_synced_at,
            graph_last_modified_raw=raw_last_modified, graph_last_modified_parsed=graph_modified,
            etag_gespeichert=etag_gespeichert if etag_gespeichert is not _unset else diag_etag_stored,
            etag_eingehend=incoming_etag, entscheidung=entscheidung,
        )

    if existing is not None and existing.planning_slot_id is not None and ("@removed" in item or _is_recurring(item) or _is_series_instance(item)):
        # Seit 1.9.241 (Stufe 6, R3b, Punkt 3): ein Termin der Plantafel -- die Plantafel ist führend. In Outlook gelöscht (oder zur Serie gemacht):
        # er verliert seine Kennung und geht in der Push-Phase desselben Laufs als neuer hinaus.
        log("Plantafel führend: in Outlook gelöscht -> neu angelegt")
        _write_sync_bookkeeping(db, existing, outlook_synced_at=None, outlook_event_id=None, outlook_postfach=None, outlook_etag=None)
        counters["plantafel"] += 1
        return None

    if "@removed" in item:
        if existing is not None:
            log("gelöscht (@removed)")  # VOR dem Löschen protokollieren, siehe Fallstrick oben
            db.delete(existing)
            db.commit()
            counters["deleted"] += 1
        else:
            log("gelöscht (@removed), lokal bereits unbekannt")
        return None

    if _is_recurring(item) or _is_series_instance(item):
        if existing is not None:
            # Ein bekannter Einzeltermin wurde in Outlook zur Serie gemacht -- die lokale Kopie
            # muss weg, sonst würde eine spätere ERP-Bearbeitung per PATCH die GANZE Serie ändern.
            # Die Vorkommen kommen danach über sync_series_occurrences() (schreibgeschützt).
            log("Einzeltermin in Outlook zur Serie geworden -> lokale Kopie entfernt")
            db.delete(existing)
            db.commit()
            counters["deleted"] += 1
            return None
        counters["skipped_recurring"] += 1
        log("Serientermin übersprungen (läuft über den Serien-Abgleich)")
        return None

    start = item.get("start") or {}
    end = item.get("end") or {}
    if not start.get("dateTime") or not end.get("dateTime"):
        # Ganztägige Termine tragen bei Graph ebenfalls start/end.dateTime (Mitternacht) -- ein
        # gänzlich fehlendes Feld ist kein sinnvoll übernehmbares Ereignis.
        counters["skipped_invalid"] += 1
        log("ungültig übersprungen (start/end fehlt)")
        return None

    beginn, ende = _zeiten_aus_graph(item)
    incoming_fields = {
        "title": item.get("subject") or "(ohne Titel)",
        "start_at": beginn,
        "end_at": ende,
        "all_day": bool(item.get("isAllDay")),
        "location": (item.get("location") or {}).get("displayName") or None,
        "notes": _plain_text_body(item),
        # Punkt 2 -- Nachtrag (seit 1.7.2): is_private ist die EINE Ausnahme, die doch aus Graph
        # übernommen wird (Outlooks sensitivity ist ihr natives Äquivalent), siehe Moduldocstring.
        "is_private": _is_private_sensitivity(item.get("sensitivity")),
    }

    if existing is None:
        now = datetime.utcnow()
        row = CalendarEvent(
            **postfach.besitzer, outlook_event_id=item["id"], outlook_postfach=postfach.adresse, external_source="outlook",
            outlook_etag=incoming_etag,
            project_id=None, quote_id=None,
            created_at=now, updated_at=now, outlook_synced_at=now,
            **incoming_fields,
        )
        # Seit 1.9.159: der Index schließt Doppelte aus, auch wenn eine Sperre abgelaufen ist und zwei Läufe sich treffen -- dann gilt die Zeile des ersten.
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            db.commit()
            log("schon angelegt (ein anderer Lauf war schneller)")
            return None
        db.commit()
        db.refresh(row)
        counters["created"] += 1
        log("neu angelegt", event_id=row.id, updated_at=now, outlook_synced_at=now, etag_gespeichert=incoming_etag)
        return row.id

    # Nachtrag (seit 1.7.3, Feld seit 1.7.5 auf @odata.etag umgestellt) -- EXAKTE Echo-Erkennung
    # vor der Zeitstempel-Heuristik: ein etag-Treffer bedeutet zweifelsfrei "diese Version kenne
    # ich bereits" (aus einem eigenen Push ODER einer bereits absorbierten Änderung), unabhängig
    # von jeder Uhr. Kein Feldabgleich, kein _mark_synced()-Aufruf -- es gibt nichts zu
    # synchronisieren, wir sind bereits exakt auf diesem Stand. Siehe Moduldocstring "Nachtrag
    # 'Schaukelnder Termin'" bzw. "Nachtrag seit 1.7.5" für die Umstellung von changeKey auf etag.
    if incoming_etag is not None and incoming_etag == existing.outlook_etag:
        log("etag-Echo (übersprungen)")
        return None

    if existing.planning_slot_id is not None:
        # Seit 1.9.241: in Outlook geändert, aber die Plantafel ist führend -- nichts übernehmen; als „nicht übertragen“ markiert, überschreibt die
        # Push-Phase desselben Laufs die Änderung mit dem Stand der Plantafel.
        _write_sync_bookkeeping(db, existing, outlook_synced_at=None, outlook_etag=incoming_etag)
        counters["plantafel"] += 1
        log("Plantafel führend: Änderung in Outlook wird überschrieben", outlook_synced_at=None, etag_gespeichert=incoming_etag)
        return None

    # "Letzte Änderung gewinnt" (Punkt 5): nur anwenden, wenn Graphs Stand nachweislich neuer ist
    # als unser eigener updated_at -- sonst gewinnt die lokale Zeile und wird stattdessen in der
    # anschließenden Push-Phase nach Outlook geschrieben.
    if graph_modified is not None and graph_modified <= existing.updated_at:
        log("Graph nicht neuer (übersprungen)")
        return None
    # Seit 1.7.6 (siehe Moduldocstring "Nachtrag"): die INHALTLICHEN Felder werden zuerst,
    # GETRENNT von der reinen Sync-Buchhaltung, geflusht -- das ist eine ECHTE Änderung, updated_at
    # SOLL hier ganz normal über onupdate=datetime.utcnow bumpen. outlook_etag ist dagegen reine
    # Buchhaltung (Graphs Versionsstempel FÜR diese neue Version) und wandert deshalb NICHT in
    # diesen setattr()-Block, sondern in den anschließenden, strukturell nie updated_at
    # berührenden _write_sync_bookkeeping()-Aufruf.
    for key, value in incoming_fields.items():
        setattr(existing, key, value)
    db.flush()
    new_updated_at = existing.updated_at  # der TATSÄCHLICH gerade generierte Wert -- kein separat
    # erfasster datetime.utcnow(): outlook_synced_at muss exakt diesem Wert entsprechen, sonst
    # hielte existing.updated_at > existing.outlook_synced_at fälschlich fest, es sei "noch zu
    # übertragen" (siehe Moduldocstring "Nachtrag, seit 1.7.6").
    _write_sync_bookkeeping(db, existing, outlook_etag=incoming_etag, outlook_synced_at=new_updated_at)
    counters["updated"] += 1
    log("übernommen (Graph war neuer)", updated_at=existing.updated_at, outlook_synced_at=existing.outlook_synced_at,
        etag_gespeichert=existing.outlook_etag)
    return existing.id


# ---------------------------------------------------------------------------
# Serientermine (seit 1.7.8): Outlook -> ERP, ausschließlich lesend
# ---------------------------------------------------------------------------
#
# Bewusst KEIN Delta für Serien: bei calendarView/delta werden startDateTime/endDateTime in den
# Delta-Token kodiert und sind danach eingefroren -- ein mit der Zeit wanderndes Fenster erzwingt
# regelmäßig eine neue Runde (voller Neuabzug), und für Vorkommen, die nur durch das Vorrücken
# der Zeit aus dem Fenster fallen, liefert Delta kein @removed (das gibt es laut Microsoft nur für
# Änderungen). Stattdessen holt jeder Lauf den VOLLSTÄNDIGEN calendarView-Schnappschuss des
# aktuellen Fensters und gleicht OutlookSeriesOccurrence exakt dagegen ab: anlegen, ändern,
# entfernen, in EINER Transaktion und erst nachdem alle Seiten vollständig geholt sind -- ein
# Abruffehler ändert lokal nichts. Schlüssel (owner_user_id, outlook_event_id) mit
# UNIQUE-Constraint: kein Vorkommen doppelt, keines fehlt.
#
# Graph-Verhalten (Microsoft-Dokumentation, "List calendarView"/"event"-Ressource, v1.0):
# calendarView liefert singleInstance, occurrence und exception, nie den seriesMaster; aus der
# Serie gelöschte Vorkommen fehlen einfach ("instances ... doesn't include occurrences canceled
# from the series"); abgesagte Besprechungen können mit isCancelled=true erscheinen und werden
# hier wie fehlende behandelt. Der Body kommt ohne Prefer-Header als HTML.

SERIES_WINDOW_PAST_DAYS = 30
SERIES_WINDOW_FUTURE_MONTHS = 12
_SERIES_SELECT = "id,subject,start,end,isAllDay,location,body,sensitivity,type,seriesMasterId,isCancelled"
_SERIES_PAGE_SIZE = 100


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


def series_window(now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """Fenster als naive UTC-Zeitpunkte, verankert an Mitternacht Europe/Berlin des heutigen
    Tages -- innerhalb eines Tages bleibt es dadurch stabil, statt sich bei jedem Lauf minimal zu
    verschieben."""
    today = to_berlin(now_utc or datetime.utcnow()).date()
    start_local = datetime.combine(today - timedelta(days=SERIES_WINDOW_PAST_DAYS), datetime.min.time())
    end_local = datetime.combine(_add_months(today, SERIES_WINDOW_FUTURE_MONTHS), datetime.min.time())
    return to_utc(start_local), to_utc(end_local)


def _series_fields(item: dict) -> dict:
    beginn, ende = _zeiten_aus_graph(item)
    return {
        "title": item.get("subject") or "(ohne Titel)",
        "start_at": beginn,
        "end_at": ende,
        "all_day": bool(item.get("isAllDay")),
        "location": (item.get("location") or {}).get("displayName") or None,
        "notes": _plain_text_body(item),
        "is_private": _is_private_sensitivity(item.get("sensitivity")),
        "occurrence_type": item.get("type") or "occurrence",
        "series_master_id": item.get("seriesMasterId"),
    }


def _diag_series(occurrence_id, *, typ, etag_gespeichert, etag_eingehend, entscheidung: str) -> None:
    """Diagnosezeile für Serienentscheidungen -- wie _diag() nie Titel/Ort/Notiz (Punkt 6)."""
    diag_logger.info(
        "serie occurrence_id=%s typ=%s etag_gespeichert=%s etag_eingehend=%s entscheidung=%s",
        occurrence_id, typ, etag_gespeichert, etag_eingehend, entscheidung,
    )


def _fetch_all_pages(token: str, url: str, extra_headers: dict) -> list[dict]:
    items: list[dict] = []
    while url:
        page = _graph_call(token, url, extra_headers=extra_headers)
        items.extend(page.get("value", []))
        url = page.get("@odata.nextLink")
    return items


def sync_series_occurrences(db: Session, postfach: Postfach, token: str, counters: dict, *,
                            now_utc: datetime | None = None) -> None:
    """Vollständiger Abgleich der Serienvorkommen EINES Postfachs gegen das aktuelle Fenster,
    siehe Abschnittskommentar oben. Wirft bei einem Abruffehler, BEVOR irgendetwas geschrieben
    wurde; der Aufrufer rollt zurück."""
    diag = diagnostics_enabled()
    adresse = postfach.adresse
    window_start, window_end = series_window(now_utc)
    query = urllib.parse.urlencode({
        "startDateTime": window_start.isoformat() + "Z",
        "endDateTime": window_end.isoformat() + "Z",
        "$select": _SERIES_SELECT,
        "$top": _SERIES_PAGE_SIZE,
    }, safe="$,:")
    url = f"{GRAPH_BASE}/users/{urllib.parse.quote(adresse)}/calendarView?{query}"
    items = _fetch_all_pages(token, url, {"Prefer": 'outlook.body-content-type="text"'})

    existing = {
        row.outlook_event_id: row
        for row in db.scalars(select(OutlookSeriesOccurrence).where(or_(postfach.gehoert(OutlookSeriesOccurrence), OutlookSeriesOccurrence.outlook_postfach == adresse))).all()
    }
    seen: set[str] = set()
    for item in items:
        if not _is_series_instance(item):
            continue  # Einzeltermin -- gehört ausschließlich dem Delta-Weg
        outlook_id = item.get("id")
        if not outlook_id or outlook_id in seen:
            continue
        row = existing.get(outlook_id)
        incoming_etag = item.get("@odata.etag")
        stored_etag = row.outlook_etag if row is not None else None

        def log(entscheidung: str, occurrence_id=None) -> None:
            if diag:
                _diag_series(occurrence_id if occurrence_id is not None else (row.id if row is not None else None),
                             typ=item.get("type"), etag_gespeichert=stored_etag,
                             etag_eingehend=incoming_etag, entscheidung=entscheidung)

        if item.get("isCancelled"):
            log("abgesagt (isCancelled) -> nicht geführt")
            continue
        if not (item.get("start") or {}).get("dateTime") or not (item.get("end") or {}).get("dateTime"):
            log("ungültig (start/end fehlt) -> nicht geführt")
            continue
        seen.add(outlook_id)
        fields = _series_fields(item)
        if row is None:
            new_row = OutlookSeriesOccurrence(**postfach.besitzer, outlook_postfach=adresse, outlook_event_id=outlook_id,
                                              outlook_etag=incoming_etag, **fields)
            db.add(new_row)
            db.flush()
            counters["series_created"] += 1
            log("neu übernommen", occurrence_id=new_row.id)
        elif any(getattr(row, key) != value for key, value in {**fields, **postfach.besitzer, "outlook_postfach": adresse}.items()):
            for key, value in {**fields, **postfach.besitzer, "outlook_postfach": adresse}.items():
                setattr(row, key, value)
            row.outlook_etag = incoming_etag
            counters["series_updated"] += 1
            log("aktualisiert (in Outlook geändert)")
        else:
            if incoming_etag and incoming_etag != row.outlook_etag:
                row.outlook_etag = incoming_etag
            log("unverändert")

    for outlook_id, row in existing.items():
        if outlook_id in seen:
            continue
        if diag:
            _diag_series(row.id, typ=row.occurrence_type, etag_gespeichert=row.outlook_etag, etag_eingehend=None,
                         entscheidung="nicht mehr im Fenster oder in Outlook entfernt/abgesagt -> entfernt")
        db.delete(row)
        counters["series_deleted"] += 1
    db.commit()


def list_series_occurrences(db: Session, *, start: datetime | None = None, end: datetime | None = None) -> list[dict]:
    """Reine Datenbeschaffung wie app/calendar_events.py::list_events() -- die
    Privatsphäre-Redaktion entscheidet der Router je Zeile mit denselben Funktionen."""
    start, end = zeitraum_berlin(start), zeitraum_berlin(end)  # seit 1.9.148 (P6)
    stmt = select(OutlookSeriesOccurrence).order_by(OutlookSeriesOccurrence.start_at)
    if start is not None:
        stmt = stmt.where(OutlookSeriesOccurrence.end_at >= start)
    if end is not None:
        stmt = stmt.where(OutlookSeriesOccurrence.start_at <= end)
    owner_names: dict[int, str | None] = {}
    result = []
    for row in db.scalars(stmt).all():
        if row.owner_user_id not in owner_names:
            owner_names[row.owner_user_id] = resolve_account_display(db, row.owner)["full_name"] if row.owner else None
        result.append({
            "id": row.id, "title": row.title, "start_at": row.start_at, "end_at": row.end_at,
            "all_day": row.all_day, "location": row.location, "notes": row.notes,
            "owner_user_id": row.owner_user_id, "owner_name": owner_names[row.owner_user_id],
            "resource_id": row.resource_id, "resource_name": row.resource.name if row.resource else None,
            "is_private": row.is_private, "occurrence_type": row.occurrence_type,
        })
    return result


_ZAEHLER = ("created", "updated", "deleted", "skipped_recurring", "skipped_invalid", "pushed_created", "pushed_updated", "push_failed",
            "series_created", "series_updated", "series_deleted", "series_failed", "delta_reset", "plantafel")  # plantafel seit 1.9.241


def sync_user_calendar(db: Session, user: AppUser, *, now_utc: datetime | None = None) -> dict:
    """Vollständiger Pull-dann-Push-Zyklus für GENAU EIN Postfach (das eigene des übergebenen
    AppUser), danach der Serien-Abgleich (seit 1.7.8). Gibt ein reines Zähler-Dict zurück (nie
    Termininhalt, Punkt 6) -- der Aufrufer (Router bzw. scripts/sync_outlook_calendars.py)
    entscheidet, wie er das protokolliert/anzeigt. now_utc nur für Tests (wanderndes Fenster)."""
    counters = dict.fromkeys(_ZAEHLER, 0)
    if not is_outlook_sync_available(db, user):
        return {"skipped": True, **counters}
    return sync_postfach(db, postfach_des_kontos(user), now_utc=now_utc, counters=counters)


def sync_postfach(db: Session, postfach: Postfach, *, now_utc: datetime | None = None, counters: dict | None = None) -> dict:
    """Ein Postfach, Konto oder Gerät (seit 1.9.161): Belegen, abgleichen, freigeben."""
    counters = counters if counters is not None else dict.fromkeys(_ZAEHLER, 0)
    sperre = _sperre_nehmen(db, postfach.adresse)
    if sperre is None:
        logger.info("Abgleich übersprungen: das Postfach wird gerade abgeglichen (%s).", postfach.im_protokoll)
        return {"skipped": True, "busy": True, **counters}
    try:
        return _postfach_abgleichen(db, postfach, sperre, counters, now_utc)
    finally:
        sperre.freigeben()


def _postfach_abgleichen(db: Session, postfach: Postfach, sperre: _Sperre, counters: dict, now_utc: datetime | None) -> dict:
    """Ein Lauf unter der Sperre des Postfachs."""
    adresse = postfach.adresse
    state = get_or_create_sync_state(db, adresse)
    smtp = load_smtp_settings(db)
    just_synced_ids: set[int] = set()
    diag = diagnostics_enabled()

    try:
        if postfach.geraet is not None:
            # seit 1.9.241: die Termine der Einsätze mit diesem Gerät nachziehen (ein Postfach, das erst nach der Planung kam; ein geänderter Auftrag)
            from .kran_kalender import nachziehen  # lokal: app/kran_kalender.py liest die Plantafel
            nachziehen(db, postfach.geraet)
            db.commit()
        if _liegt_woanders(db, postfach):
            state.delta_link = None  # seit 1.9.160: erst der ganze Kalender sagt, was davon hier liegt (eine umbenannte Adresse) und was wirklich woanders
            db.commit()
        token = get_graph_access_token(smtp)
        basis_url = f"{_mailbox_events_url(adresse)}/delta?$select={_EVENT_SELECT}"
        items, new_delta_link, ganzer_kalender = _delta_holen(db, state, token, basis_url, counters, sperre)
        for item in items:
            changed_id = _apply_delta_change(db, postfach, item, counters)
            if changed_id is not None:
                just_synced_ids.add(changed_id)
        if ganzer_kalender:
            _postfach_wechsel_aufloesen(db, postfach, counters)
            _weggefallene_entfernen(db, postfach, token, items, counters, sperre)

        # Nachtrag (seit 1.7.2): Push-Fälligkeit über _needs_push() (pro Termin,
        # CalendarEvent.outlook_synced_at) statt eines einzelnen, postfachweiten Zeitstempels --
        # siehe Moduldocstring für die beiden damit behobenen Fehler. Jeder Termin committet
        # SOFORT nach einem erfolgreichen Push UND wird bei einem Fehlschlag EINZELN abgefangen
        # (eigenes try/except je Zeile) -- ein kaputter Termin blockiert weder die übrigen Termine
        # in dieser Schleife noch das Fortschreiben von delta_link/last_synced_at am Ende.
        local_rows = db.scalars(select(CalendarEvent).where(postfach.gehoert(CalendarEvent))).all()
        for row in local_rows:
            if row.id in just_synced_ids or not _needs_push(row):
                continue
            sperre.halten()
            old_etag = row.outlook_etag  # vor jeder Mutation erfasst
            if row.outlook_event_id is None:
                push_reason = "outlook_event_id fehlt (Neuanlage)"
            elif row.outlook_synced_at is None:
                push_reason = "outlook_synced_at fehlt (noch nie synchronisiert)"
            else:
                push_reason = f"updated_at ({row.updated_at}) > outlook_synced_at ({row.outlook_synced_at})"
            if diag:
                _diag(row.id, updated_at=row.updated_at, outlook_synced_at=row.outlook_synced_at,
                      graph_last_modified_raw=None, graph_last_modified_parsed=None,
                      etag_gespeichert=old_etag, etag_eingehend=None,
                      entscheidung=f"push angestoßen ({push_reason})")
            try:
                # Seit 1.7.6 (siehe Moduldocstring "Nachtrag" bzw. push_event_best_effort() für
                # dieselbe Begründung): bleibt UNVERÄNDERT, reines Pushen ändert lokal nichts.
                # outlook_event_id/outlook_etag werden NICHT mehr per setattr() vorab gesetzt,
                # sondern als Teil DERSELBEN Buchhaltungs-Anweisung übergeben.
                version_to_sync = row.updated_at
                response, bookkeeping, neu_angelegt = _termin_senden(token, adresse, row)
                counters["pushed_created" if neu_angelegt else "pushed_updated"] += 1
                # Seit 1.7.5 (siehe push_event_best_effort() für dieselbe Begründung) -- @odata.etag
                # statt changeKey, das in einer späteren Delta-Zeile nachweislich nie ankommt.
                new_etag = response.get("@odata.etag") if response is not None else None
                if new_etag:
                    bookkeeping["outlook_etag"] = new_etag
                _write_sync_bookkeeping(db, row, outlook_synced_at=version_to_sync, **bookkeeping)
                if diag:
                    # row.* ist HIER (nach _write_sync_bookkeeping()s db.refresh()) der tatsächlich
                    # jetzt gespeicherte Wert -- siehe push_event_best_effort() für denselben, dort
                    # zuerst gefundenen Diagnose-Anzeigefehler (Moduldocstring "Nachtrag seit 1.7.5").
                    _diag(row.id, updated_at=row.updated_at, outlook_synced_at=row.outlook_synced_at,
                          graph_last_modified_raw=None, graph_last_modified_parsed=None,
                          etag_gespeichert=row.outlook_etag, etag_eingehend=None,
                          entscheidung="push erfolgreich")
            except Exception as exc:  # noqa: BLE001 -- ein Termin darf die übrigen nicht blockieren
                db.rollback()
                counters["push_failed"] += 1
                logger.warning("Push nach Outlook fehlgeschlagen (event_id=%s, Fehlerart=%s).", row.id, type(exc).__name__)
                if diag:
                    _diag(row.id, updated_at=None, outlook_synced_at=None, graph_last_modified_raw=None,
                          graph_last_modified_parsed=None, etag_gespeichert=old_etag, etag_eingehend=None,
                          entscheidung=f"push fehlgeschlagen ({type(exc).__name__})")

        _loeschauftraege_abarbeiten(db, token)

        state.delta_link = new_delta_link
        state.last_synced_at = datetime.utcnow()
        state.last_error_type = None
        state.last_error_at = None
        state.last_error_status = None
        db.commit()

        # Eigener Fehlerbereich: ein fehlschlagender Serien-Abgleich darf den bereits
        # abgeschlossenen Einzeltermin-Sync (inkl. delta_link) nicht zurückrollen.
        try:
            sperre.halten()
            sync_series_occurrences(db, postfach, token, counters, now_utc=now_utc)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            for key in ("series_created", "series_updated", "series_deleted"):
                counters[key] = 0
            counters["series_failed"] = 1
            logger.warning("Serien-Abgleich fehlgeschlagen (%s, Fehlerart=%s).", postfach.im_protokoll, type(exc).__name__)
            if diagnostics_enabled():
                _diag_series(None, typ=None, etag_gespeichert=None, etag_eingehend=None,
                             entscheidung=f"Serien-Abgleich fehlgeschlagen ({type(exc).__name__}) -> nichts verändert")
        return counters
    except Exception as exc:  # noqa: BLE001 -- ein fehlschlagendes Postfach darf den Cron-Lauf für andere nicht abbrechen
        db.rollback()
        state = get_or_create_sync_state(db, adresse)
        state.last_error_type = type(exc).__name__
        state.last_error_at = datetime.utcnow()
        state.last_error_status = getattr(exc, "status", None)
        db.commit()
        logger.warning("Outlook-Kalendersynchronisation fehlgeschlagen (%s, Fehlerart=%s).", postfach.im_protokoll, type(exc).__name__)
        return {"error": True, "error_type": type(exc).__name__, **counters}
