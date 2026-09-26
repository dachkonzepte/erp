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
Kollegentermine anzeigt (Stufe 1).

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

**Punkt 4 -- Serientermine, nur ein Vorschlag, NICHT implementiert:** CalendarEvent kennt keine
Wiederholungsregel. Ein wiederkehrender Outlook-Termin erscheint in der events/delta-Antwort als
EIN einzelnes "seriesMaster"-Objekt (Graph expandiert Einzeltermine nur über calendarView mit
Datumsfenster, nicht über die hier genutzte events/delta) -- _is_recurring() erkennt das und
_apply_delta_change() überspringt solche Zeilen vollständig (gezählt, nie angelegt/geändert).
Ein künftiger Ausbau müsste auf calendarView/delta mit einem festen Zeitfenster wechseln und
jede Instanz als eigene, entkoppelte CalendarEvent-Zeile führen -- eine größere Modelländerung,
hier bewusst nicht gebaut.

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
"""

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from .email_sending import get_graph_access_token, get_or_create_smtp_settings
from .models import AppUser, CalendarEvent, OutlookCalendarSyncState, OutlookSyncSettings

logger = logging.getLogger("app.outlook_calendar_sync")
# Eigener Logger-Name für die abschaltbare Diagnosezeile (seit 1.7.4) -- getrennt vom
# Warn-Logger oben, damit sie sich unabhängig davon per Logging-Konfiguration UND per
# ERP_OUTLOOK_SYNC_DIAGNOSTICS gezielt ein-/ausschalten lässt.
diag_logger = logging.getLogger("app.outlook_calendar_sync.diagnostics")

BERLIN = ZoneInfo("Europe/Berlin")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_TIMEOUT = 30

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
    enthalten (siehe Punkt 6) und darf deshalb NIE geloggt werden, nur type(exc).__name__."""


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


def get_or_create_outlook_sync_settings(db: Session) -> OutlookSyncSettings:
    settings = db.get(OutlookSyncSettings, 1)
    if settings is None:
        settings = OutlookSyncSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_outlook_sync_settings(db: Session, *, enabled: bool) -> OutlookSyncSettings:
    settings = get_or_create_outlook_sync_settings(db)
    settings.enabled = enabled
    db.commit()
    db.refresh(settings)
    return settings


def is_outlook_sync_available(db: Session, user: AppUser | None = None) -> bool:
    """Gesamtschalter an UND Graph-Zugangsdaten vorhanden (dieselben wie beim E-Mail-Versand,
    siehe OutlookSyncSettings-Klassendocstring) -- prüft, wenn user übergeben wird, zusätzlich
    dessen eigenes outlook_mailbox. Reicht als schnelle Vorprüfung (Muster
    app/modules.py::is_module_enabled()), ohne selbst schon Netzwerkzugriff auszulösen."""
    settings = get_or_create_outlook_sync_settings(db)
    if not settings.enabled:
        return False
    smtp = get_or_create_smtp_settings(db)
    if not (smtp.graph_tenant_id and smtp.graph_client_id and smtp.graph_client_secret_encrypted):
        return False
    if user is not None and not user.outlook_mailbox:
        return False
    return True


def get_or_create_sync_state(db: Session, user: AppUser) -> OutlookCalendarSyncState:
    state = db.scalar(select(OutlookCalendarSyncState).where(OutlookCalendarSyncState.app_user_id == user.id))
    if state is None:
        state = OutlookCalendarSyncState(app_user_id=user.id)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


# ---------------------------------------------------------------------------
# Low-level Graph-Zugriff
# ---------------------------------------------------------------------------


def _graph_call(token: str, url: str, *, method: str = "GET", payload: dict | None = None) -> dict | None:
    """Ein einzelner Graph-Aufruf -- gibt das geparste JSON zurück (None bei 204 No Content, z.
    B. nach DELETE). Wirft OutlookSyncError bei jedem Fehler; die Nachricht selbst wird NIE
    geloggt (siehe Moduldocstring Punkt 6), nur an den Aufrufer zur Anzeige durchgereicht, falls
    dieser sie einem Menschen zeigen will (z. B. "Verbindung testen")."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=GRAPH_TIMEOUT) as resp:
            body = resp.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        hint = " Häufigste Ursache: das Postfach ist der Anwendung nicht über eine Exchange-RBAC-Zugriffsrichtlinie freigegeben (siehe CLAUDE.md \"Kalender\" -> \"Stufe 2\")." if e.code == 403 else ""
        raise OutlookSyncError(f"Microsoft-Graph-Aufruf fehlgeschlagen ({e.code}): {detail}{hint}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise OutlookSyncError(f"Verbindung zu Microsoft Graph fehlgeschlagen: {e}") from e


def _mailbox_events_url(mailbox: str) -> str:
    return f"{GRAPH_BASE}/users/{urllib.parse.quote(mailbox)}/events"


def _event_payload(event: CalendarEvent) -> dict:
    body_text = event.notes or ""
    return {
        "subject": event.title,
        "isAllDay": event.all_day,
        "start": {"dateTime": to_utc(event.start_at).isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": to_utc(event.end_at).isoformat(), "timeZone": "UTC"},
        "location": {"displayName": event.location or ""},
        "body": {"contentType": "Text", "content": body_text},
        "sensitivity": _outgoing_sensitivity(event.is_private),
    }


def _mark_synced(db: Session, row: CalendarEvent, at: datetime) -> None:
    """Setzt updated_at UND outlook_synced_at explizit auf DENSELBEN Zeitpunkt -- sonst würde
    SQLAlchemys onupdate=datetime.utcnow bei dieser reinen Sync-Buchhaltung updated_at
    unbeabsichtigt weiterschieben (siehe Moduldocstring "Nachtrag (seit 1.7.2)"), was den Termin
    sofort wieder als "noch zu übertragen" erscheinen ließe.

    **Fallstrick, real aufgetreten, deshalb per Core-UPDATE gelöst statt per ORM-Attribut:** ein
    naives `row.updated_at = at` (mit `at == row.updated_at`, also scheinbar ein No-op) reicht
    dafür NICHT -- SQLAlchemys Dirty-Tracking vergleicht den neuen gegen den bereits geladenen
    Wert und verwirft eine Zuweisung ohne echte Änderung wieder aus dem "dirty"-Zustand; die
    Spalte landet dann NICHT in der UPDATE-Anweisung, wodurch der onupdate-Callable trotzdem
    greift (per Test nachgewiesen: ein paar Millisekunden Drift zwischen dem eigentlich
    beabsichtigten Wert und dem tatsächlich gespeicherten). db.execute(update(...).values(...))
    auf Core-Ebene schließt eine angegebene Spalte dagegen IMMER in die UPDATE-Anweisung ein,
    unabhängig davon, ob sich ihr Wert ändert, und unterdrückt onupdate zuverlässig dafür. Muss
    NACH allen anderen Änderungen an `row` in diesem Umlauf aufgerufen werden -- ein davor
    ausgelöstes Autoflush holt einen etwaigen onupdate-Bump ab, dieser Aufruf überschreibt ihn
    zuverlässig mit `at`."""
    db.execute(sa_update(CalendarEvent).where(CalendarEvent.id == row.id).values(updated_at=at, outlook_synced_at=at))
    row.updated_at = at
    row.outlook_synced_at = at


def _needs_push(row: CalendarEvent) -> bool:
    if row.outlook_event_id is None:
        return True
    return row.outlook_synced_at is None or row.updated_at > row.outlook_synced_at


def _is_recurring(item: dict) -> bool:
    return bool(item.get("recurrence")) or item.get("type") == "seriesMaster"


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
    user = event.owner
    if not is_outlook_sync_available(db, user):
        return
    diag = diagnostics_enabled()
    old_etag = event.outlook_etag  # vor jeder Mutation erfasst, für die Diagnosezeile
    try:
        smtp = get_or_create_smtp_settings(db)
        token = get_graph_access_token(smtp)
        version_to_sync = event.updated_at  # VOR jeder eigenen Mutation erfasst, siehe _mark_synced()
        if diag:
            _diag(event.id, updated_at=version_to_sync, outlook_synced_at=event.outlook_synced_at,
                  graph_last_modified_raw=None, graph_last_modified_parsed=None,
                  etag_gespeichert=old_etag, etag_eingehend=None,
                  entscheidung="push versucht (best effort, nach create_event()/update_event())")
        if event.outlook_event_id:
            response = _graph_call(token, f"{_mailbox_events_url(user.outlook_mailbox)}/{event.outlook_event_id}", method="PATCH", payload=_event_payload(event))
        else:
            response = _graph_call(token, _mailbox_events_url(user.outlook_mailbox), method="POST", payload=_event_payload(event))
            event.outlook_event_id = response["id"]
        # Seit 1.7.5 (siehe Moduldocstring "Nachtrag") -- @odata.etag statt changeKey: Graph liefert
        # es bei JEDER erfolgreichen Schreiboperation mit zurück, anders als changeKey ist es
        # außerdem dieselbe Annotation, die auch eine spätere Delta-Zeile trägt (dort KOMMT
        # changeKey nachweislich nie an, $select wird für Kalender-Delta ignoriert). Ohne einen
        # neuen Wert (z. B. ein PATCH ohne Body) bleibt outlook_etag auf dem alten Stand stehen und
        # die Zeitstempel-Logik greift beim nächsten Pull als Rückfall.
        new_etag = response.get("@odata.etag") if response is not None else None
        if new_etag:
            event.outlook_etag = new_etag
        _mark_synced(db, event, version_to_sync)
        db.commit()
        if diag:
            # event.outlook_etag ist HIER der tatsächlich jetzt gespeicherte Wert (new_etag, falls
            # gesetzt, sonst unverändert old_etag) -- NICHT old_etag: eine frühere Fassung
            # protokollierte hier fälschlich den Wert VOR dem Push, siehe Moduldocstring
            # "Nachtrag seit 1.7.5", Punkt 3.
            _diag(event.id, updated_at=version_to_sync, outlook_synced_at=version_to_sync,
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


def try_delete_remote_event(db: Session, event: CalendarEvent) -> bool:
    """Vor dem lokalen Löschen (app/routers/calendar_events.py) aufgerufen, wenn der Termin
    bereits einen outlook_event_id trägt. Best effort (gibt True/False zurück, wirft nie) --
    schlägt die Fernlöschung fehl (z. B. Graph kurzzeitig nicht erreichbar), wird trotzdem lokal
    gelöscht (Nutzerabsicht hat Vorrang); ein bewusst akzeptiertes, seltenes Restrisiko bleibt
    dabei bestehen, siehe CLAUDE.md "Kalender" -> "Stufe 2" -> "Bekannte, bewusst offene
    Punkte": der Outlook-Termin kann dann bei einem späteren Sync-Lauf fälschlich als neu
    erkannt und lokal wiederhergestellt werden."""
    if not event.outlook_event_id:
        return True
    user = event.owner
    if not is_outlook_sync_available(db, user):
        return True
    try:
        smtp = get_or_create_smtp_settings(db)
        token = get_graph_access_token(smtp)
        _graph_call(token, f"{_mailbox_events_url(user.outlook_mailbox)}/{event.outlook_event_id}", method="DELETE")
        return True
    except Exception as exc:  # noqa: BLE001 -- best effort, siehe Docstring
        logger.warning("Fernlöschen in Outlook fehlgeschlagen (event_id=%s, Fehlerart=%s).", event.id, type(exc).__name__)
        return False


# ---------------------------------------------------------------------------
# Pull: Outlook-Änderungen -> lokal (Delta-Abfrage)
# ---------------------------------------------------------------------------


def _fetch_delta_pages(token: str, start_url: str) -> tuple[list[dict], str]:
    """Folgt @odata.nextLink, bis @odata.deltaLink kommt -- gibt alle gesammelten Zeilen plus
    den neuen deltaLink zurück (zum Speichern in OutlookCalendarSyncState.delta_link)."""
    items: list[dict] = []
    url = start_url
    while True:
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


def _apply_delta_change(db: Session, user: AppUser, item: dict, counters: dict) -> int | None:
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
    existing = db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == item["id"], CalendarEvent.owner_user_id == user.id))
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

    if "@removed" in item:
        if existing is not None:
            log("gelöscht (@removed)")  # VOR dem Löschen protokollieren, siehe Fallstrick oben
            db.delete(existing)
            db.commit()
            counters["deleted"] += 1
        else:
            log("gelöscht (@removed), lokal bereits unbekannt")
        return None

    if _is_recurring(item):
        counters["skipped_recurring"] += 1
        log("Serientermin übersprungen")
        return None

    start = item.get("start") or {}
    end = item.get("end") or {}
    if not start.get("dateTime") or not end.get("dateTime"):
        # Ganztägige Termine tragen bei Graph ebenfalls start/end.dateTime (Mitternacht) -- ein
        # gänzlich fehlendes Feld ist kein sinnvoll übernehmbares Ereignis.
        counters["skipped_invalid"] += 1
        log("ungültig übersprungen (start/end fehlt)")
        return None

    incoming_fields = {
        "title": item.get("subject") or "(ohne Titel)",
        "start_at": to_berlin(_parse_graph_datetime(start["dateTime"])),
        "end_at": to_berlin(_parse_graph_datetime(end["dateTime"])),
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
            owner_user_id=user.id, outlook_event_id=item["id"], external_source="outlook",
            outlook_etag=incoming_etag,
            project_id=None, quote_id=None,
            created_at=now, updated_at=now, outlook_synced_at=now,
            **incoming_fields,
        )
        db.add(row)
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

    # "Letzte Änderung gewinnt" (Punkt 5): nur anwenden, wenn Graphs Stand nachweislich neuer ist
    # als unser eigener updated_at -- sonst gewinnt die lokale Zeile und wird stattdessen in der
    # anschließenden Push-Phase nach Outlook geschrieben.
    if graph_modified is not None and graph_modified <= existing.updated_at:
        log("Graph nicht neuer (übersprungen)")
        return None
    for key, value in incoming_fields.items():
        setattr(existing, key, value)
    existing.outlook_etag = incoming_etag
    # Diese Zeile stimmt jetzt (wieder) mit Outlook überein -- _mark_synced() verhindert, dass
    # updated_at und outlook_synced_at durch getrennte onupdate-/Zuweisungszeitpunkte auseinanderlaufen.
    new_synced_at = datetime.utcnow()
    _mark_synced(db, existing, new_synced_at)
    db.commit()
    counters["updated"] += 1
    # Werte NACH der Übernahme explizit übergeben (nicht existing.* nach db.commit() erneut
    # lesen -- derselbe Fallstrick wie oben, hier zwar kein ObjectDeletedError, aber ein
    # überflüssiger Reload; die Werte sind durch _mark_synced() ohnehin schon bekannt).
    log("übernommen (Graph war neuer)", updated_at=new_synced_at, outlook_synced_at=new_synced_at,
        etag_gespeichert=incoming_etag)
    return existing.id


def sync_user_calendar(db: Session, user: AppUser) -> dict:
    """Vollständiger Pull-dann-Push-Zyklus für GENAU EIN Postfach (das eigene des übergebenen
    AppUser). Gibt ein reines Zähler-Dict zurück (nie Termininhalt, Punkt 6) -- der Aufrufer
    (Router bzw. scripts/sync_outlook_calendars.py) entscheidet, wie er das protokolliert/
    anzeigt."""
    counters = {"created": 0, "updated": 0, "deleted": 0, "skipped_recurring": 0, "skipped_invalid": 0, "pushed_created": 0, "pushed_updated": 0, "push_failed": 0}
    if not is_outlook_sync_available(db, user):
        return {"skipped": True, **counters}

    state = get_or_create_sync_state(db, user)
    smtp = get_or_create_smtp_settings(db)
    just_synced_ids: set[int] = set()
    diag = diagnostics_enabled()

    try:
        token = get_graph_access_token(smtp)
        start_url = state.delta_link or (
            f"{_mailbox_events_url(user.outlook_mailbox)}/delta?$select={_EVENT_SELECT}"
        )
        items, new_delta_link = _fetch_delta_pages(token, start_url)
        for item in items:
            changed_id = _apply_delta_change(db, user, item, counters)
            if changed_id is not None:
                just_synced_ids.add(changed_id)

        # Nachtrag (seit 1.7.2): Push-Fälligkeit über _needs_push() (pro Termin,
        # CalendarEvent.outlook_synced_at) statt eines einzelnen, postfachweiten Zeitstempels --
        # siehe Moduldocstring für die beiden damit behobenen Fehler. Jeder Termin committet
        # SOFORT nach einem erfolgreichen Push UND wird bei einem Fehlschlag EINZELN abgefangen
        # (eigenes try/except je Zeile) -- ein kaputter Termin blockiert weder die übrigen Termine
        # in dieser Schleife noch das Fortschreiben von delta_link/last_synced_at am Ende.
        local_rows = db.scalars(select(CalendarEvent).where(CalendarEvent.owner_user_id == user.id)).all()
        for row in local_rows:
            if row.id in just_synced_ids or not _needs_push(row):
                continue
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
                version_to_sync = row.updated_at  # VOR jeder eigenen Mutation erfasst, siehe _mark_synced()
                if row.outlook_event_id is None:
                    response = _graph_call(token, _mailbox_events_url(user.outlook_mailbox), method="POST", payload=_event_payload(row))
                    row.outlook_event_id = response["id"]
                    counters["pushed_created"] += 1
                else:
                    response = _graph_call(token, f"{_mailbox_events_url(user.outlook_mailbox)}/{row.outlook_event_id}", method="PATCH", payload=_event_payload(row))
                    counters["pushed_updated"] += 1
                # Seit 1.7.5 (siehe push_event_best_effort() für dieselbe Begründung) -- @odata.etag
                # statt changeKey, das in einer späteren Delta-Zeile nachweislich nie ankommt.
                new_etag = response.get("@odata.etag") if response is not None else None
                if new_etag:
                    row.outlook_etag = new_etag
                _mark_synced(db, row, version_to_sync)
                db.commit()
                if diag:
                    # row.outlook_etag ist der tatsächlich jetzt gespeicherte Wert -- NICHT
                    # old_etag, siehe push_event_best_effort() für denselben, dort zuerst
                    # gefundenen Diagnose-Anzeigefehler (Moduldocstring "Nachtrag seit 1.7.5").
                    _diag(row.id, updated_at=version_to_sync, outlook_synced_at=version_to_sync,
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

        state.delta_link = new_delta_link
        state.last_synced_at = datetime.utcnow()
        state.last_error_type = None
        state.last_error_at = None
        db.commit()
        return counters
    except Exception as exc:  # noqa: BLE001 -- ein fehlschlagendes Postfach darf den Cron-Lauf für andere nicht abbrechen
        db.rollback()
        state = get_or_create_sync_state(db, user)
        state.last_error_type = type(exc).__name__
        state.last_error_at = datetime.utcnow()
        db.commit()
        logger.warning("Outlook-Kalendersynchronisation fehlgeschlagen (app_user_id=%s, Fehlerart=%s).", user.id, type(exc).__name__)
        return {"error": True, "error_type": type(exc).__name__, **counters}
