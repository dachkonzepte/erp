"""Kalender-Modul, Stufe 2 (Outlook-Synchronisation über Microsoft Graph, seit 1.7.1, mit
Nachtrag seit 1.7.2). Siehe CLAUDE.md "Kalender" -> "Stufe 2" für die vollständige Herleitung der
sieben Entscheidungspunkte -- diese Datei deckt jeden davon ab: Zeitzonen inkl. beider
DST-Übergänge (Punkt 3), Projekt-/Angebotsbezug bleibt bei einer eingehenden Änderung
unangetastet, is_private WIRD dagegen bewusst aus Outlooks sensitivity übernommen (Punkt 2 samt
Nachtrag), Serientermine werden übersprungen statt angelegt (Punkt 4), Delta-Query mit
Pagination/gespeichertem delta_link, "letzte Änderung gewinnt" über einen PRO-TERMIN-Merker
(outlook_synced_at, Nachtrag seit 1.7.2 -- ersetzt den ursprünglichen, nachweislich fehlerhaften
postfachweiten last_synced_at-Vergleich), Löschungen beidseitig (Punkt 5), kein Termininhalt in
Protokollen (Punkt 6) -- und jeder Netzwerkzugriff läuft ausschließlich gegen eine Attrappe
(Punkt 7, urllib.request.urlopen wird an keiner Stelle real aufgerufen)."""

import io
import json
import logging
import os
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.calendar_events import (
    create_event, is_redacted_for_viewer, list_events, redact_for_busy,
)
from app.database import Base
from app.email_sending import update_graph_settings
from app.models import AppUser, CalendarEvent, Customer, OutlookCalendarSyncState, OutlookSeriesOccurrence, Project
from app.outlook_calendar_sync import (
    _add_months, _write_sync_bookkeeping, _needs_push, _parse_graph_datetime, diagnostics_enabled,
    get_or_create_sync_state, is_outlook_sync_available, list_series_occurrences,
    push_event_best_effort, series_window, to_berlin, to_utc, try_delete_remote_event,
    update_outlook_sync_settings, sync_user_calendar,
)
from app.project_pipeline_columns import default_pipeline_column_id
from app.routers.calendar_events import router as calendar_router
from app.routers.outlook_sync_settings import router as outlook_settings_router

TOKEN_URL_MARKER = "login.microsoftonline.com"


def _events_url(mailbox: str, suffix: str = "") -> str:
    """Mailbox-Anteil einer erwarteten Graph-URL -- exakt dieselbe Quotierung wie
    app/outlook_calendar_sync.py::_mailbox_events_url() (urllib.parse.quote() kodiert "@" zu
    "%40"), damit die Testerwartung nicht an der echten Implementierung vorbeigeht."""
    return f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(mailbox)}/events{suffix}"


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# Nachtrag "Zweite Untersuchungsrunde" (seit 1.7.4), Punkt 5 -- der Schaukel-Test soll auch gegen
# eine ECHTE PostgreSQL-Instanz laufen können, nicht nur gegen SQLite. Bewusst OPT-IN (Standard-
# Testlauf bleibt SQLite-only, kein externer Dienst wird vorausgesetzt): ERP_TEST_POSTGRES_URL
# in der Umgebung setzen, z. B. gegen die lokale, portable Instanz aus CLAUDE.md
# "PostgreSQL-Umstieg" (Datenbank "spielwiese", bereits per `alembic upgrade head` migriert):
#   ERP_TEST_POSTGRES_URL=postgresql+psycopg://erp@127.0.0.1:5433/spielwiese
# ---------------------------------------------------------------------------

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")

requires_postgres_opt_in = pytest.mark.skipif(
    not PG_TEST_DATABASE_URL,
    reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.",
)


def pg_db_session():
    """Verbindet gegen die in ERP_TEST_POSTGRES_URL angegebene, ECHTE PostgreSQL-Datenbank.
    Base.metadata.create_all() ist idempotent (überspringt bereits vorhandene Tabellen) -- läuft
    also unabhängig davon, ob das Ziel bereits per Alembic migriert ist (Regelfall für
    "spielwiese", siehe CLAUDE.md) oder eine frische, leere Datenbank ist."""
    engine = create_engine(PG_TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)(), engine


def _cleanup_pg_test_data(db, *usernames: str) -> None:
    """Räumt VOR und NACH jedem PostgreSQL-Testlauf ausschließlich die von DIESEM Testmodul unter
    den übergebenen, eindeutigen Benutzernamen angelegten Zeilen auf -- rührt sonst nichts in
    dieser (potenziell von anderen manuellen Prüfungen mitbenutzten, siehe CLAUDE.md
    "Migrations-Workflow") Datenbank an."""
    user_ids = db.scalars(select(AppUser.id).where(AppUser.username.in_(usernames))).all()
    if not user_ids:
        return
    db.execute(delete(CalendarEvent).where(CalendarEvent.owner_user_id.in_(user_ids)))
    db.execute(delete(OutlookSeriesOccurrence).where(OutlookSeriesOccurrence.owner_user_id.in_(user_ids)))
    db.execute(delete(OutlookCalendarSyncState).where(OutlookCalendarSyncState.app_user_id.in_(user_ids)))
    db.execute(delete(AppUser).where(AppUser.id.in_(user_ids)))
    db.commit()


def _make_user(db, *, username="tobias", mailbox="tobias@dachkonzepte.gmbh", role="buero_auftrag"):
    user = AppUser(username=username, display_name=username.capitalize(), role=role, active=True,
                   password_hash=hash_password("Passwort123"), outlook_mailbox=mailbox)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _enable_sync(db):
    update_outlook_sync_settings(db, enabled=True)
    update_graph_settings(db, tenant_id="tenant-1", client_id="client-1", sender_mailbox="buero@dachkonzepte.gmbh", client_secret="s3cr3t")


def _make_event(db, owner, **overrides):
    base = dict(
        title="Besichtigung", start_at=datetime(2026, 5, 4, 9, 0), end_at=datetime(2026, 5, 4, 10, 0),
        all_day=False, location="Musterstraße 1", notes=None, project_id=None, quote_id=None, is_private=False,
    )
    base.update(overrides)
    data = create_event(db, owner_user_id=owner.id, **base)
    return db.get(CalendarEvent, data["id"])


class _FakeResponse:
    def __init__(self, payload):
        self._body = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._body


def _http_error(code, detail="fehlgeschlagen"):
    return urllib.error.HTTPError(url="https://graph.microsoft.com/x", code=code, msg="err", hdrs=None,
                                   fp=io.BytesIO(json.dumps({"error": {"message": detail}}).encode("utf-8")))


def _token_only(calls: list | None = None):
    """Fake-Server, der ausschließlich den Token-Endpunkt bedient -- für Tests, die einen
    fehlschlagenden ZWEITEN Aufruf (Push/Delete/Delta) provozieren wollen."""
    def _fn(req, timeout=None):
        url = req.full_url
        if calls is not None:
            calls.append((req.get_method(), url))
        if TOKEN_URL_MARKER in url:
            return _FakeResponse({"access_token": "faketoken"})
        raise _http_error(403)
    return _fn


# ---------------------------------------------------------------------------
# Nachtrag "Schaukelnder Termin" (seit 1.7.3) -- realistische Graph-Attrappe MIT ECHTEM ZUSTAND.
#
# Jede andere Antwort in dieser Datei ist eine einzelne, handgebaute Momentaufnahme -- genau
# deshalb haben die bisherigen Tests den gemeldeten Fehler nicht gefunden: keiner von ihnen
# bildete den tatsächlich entscheidenden Rundlauf ab, bei dem eine EIGENE, per PATCH/POST
# geschriebene Änderung bei einem SPÄTEREN Delta-Abruf als scheinbar FREMDE Änderung
# zurückkommt (Graph unterscheidet dabei nicht zwischen "von uns" und "von jemand anderem" --
# das ist Sache dieses Moduls). FakeGraphServer führt deshalb echten Zustand: jedes PATCH/POST
# vergibt einen NEUEN lastModifiedDateTime UND einen NEUEN Versionsstempel.
#
# **Korrigiert (seit 1.7.5) -- die Attrappe bildete bis dahin selbst den Fehler ab, den sie
# eigentlich aufdecken sollte.** Sie lieferte `changeKey` in JEDER Zeile mit, auch in delta() --
# die Produktions-Diagnose (Punkt 4 der Anfrage) zeigte aber, dass Microsoft Graph das für
# Delta-Antworten nachweislich NIE tut ($select wird für Kalender-Delta-Abfragen laut Microsoft-
# Dokumentation ignoriert; jede von Microsoft selbst gezeigte Beispiel-Delta-Antwort trägt
# `@odata.etag`, nie `changeKey`). `create()`/`patch()` liefern deshalb weiterhin BEIDE Felder
# (wie ein reales POST/PATCH -- changeKey UND @odata.etag), aber `delta()` liefert NUR NOCH
# `@odata.etag`, kein `changeKey` mehr -- ein Test gegen die alte, zu großzügige Attrappe hätte
# den 1.7.4-Fund (change_key_gespeichert/change_key_eingehend immer None) strukturell nie finden
# können, unabhängig davon, wie viele Läufe er simuliert hätte.
# ---------------------------------------------------------------------------


def _graph_dt(value: datetime) -> dict:
    return {"dateTime": value.strftime("%Y-%m-%dT%H:%M:%S") + ".0000000", "timeZone": "UTC"}


def _fields_from_payload(payload: dict) -> dict:
    return {
        "subject": payload["subject"], "isAllDay": payload["isAllDay"],
        "start": payload["start"], "end": payload["end"], "location": payload["location"],
        "body": {"contentType": "text", "content": payload["body"]["content"]},
        "sensitivity": payload.get("sensitivity", "normal"),
    }


class FakeGraphServer:
    """Ein simuliertes Postfach mit echtem, fortlaufendem Zustand -- siehe Modulkommentar oben.
    Die Uhr startet bewusst bei der tatsächlichen aktuellen Zeit (nicht irgendwann in der
    Vergangenheit), da sonst lastModifiedDateTime-Werte VOR dem lokalen event.updated_at (einem
    echten datetime.utcnow() aus create_event()) lägen und die "wer ist neuer"-Prüfung aus einem
    trivialen Grund (Uhr in der Vergangenheit) unrealistisch entschärft würde."""

    def __init__(self):
        self.events: dict[str, dict] = {}
        self._next_id = 1
        self._seq = 0
        self._clock = datetime.utcnow()
        # Seit 1.7.8 -- Serien, siehe add_series()/calendar_view(). write_requests protokolliert
        # JEDEN schreibenden Aufruf (POST/PATCH/DELETE), damit ein Test "kein einziger Push"
        # direkt am Server-Protokoll prüfen kann, nicht nur an den ERP-Zählern.
        self.series: dict[str, dict] = {}
        self.write_requests: list[tuple[str, str]] = []
        self.calendar_view_requests: list[dict] = []

    def _advance(self) -> tuple[str, str, str]:
        self._seq += 1
        self._clock += timedelta(seconds=1)
        return self._clock.isoformat() + "Z", f"ckey-{self._seq}", f'W/"etag-{self._seq}"'

    def create(self, payload: dict) -> dict:
        new_id = f"graph-{self._next_id}"
        self._next_id += 1
        last_modified, change_key, etag = self._advance()
        self.events[new_id] = {
            "id": new_id, **_fields_from_payload(payload), "type": "singleInstance", "seriesMasterId": None,
            "lastModifiedDateTime": last_modified, "changeKey": change_key,
            "@odata.etag": etag, "_seq": self._seq,
        }
        return dict(self.events[new_id])

    # --- Serien (seit 1.7.8), nachgebildet nach Microsofts v1.0-Dokumentation ------------------
    # * events/delta liefert eine Serie nur als EIN seriesMaster-Objekt (mit recurrence) -- der
    #   Master liegt deshalb in self.events und kommt über delta() wie jedes andere Event.
    # * calendarView liefert singleInstance, occurrence und exception, NIE den seriesMaster; jedes
    #   Vorkommen trägt eigene id, seriesMasterId, originalStart und @odata.etag.
    # * Ein aus der Serie gelöschtes Vorkommen fehlt einfach ("instances ... doesn't include
    #   occurrences canceled from the series"); eine vom Organisator abgesagte Besprechung kann
    #   dagegen mit isCancelled=true erscheinen.
    # * Zeiten kommen mit sieben Nachkommastellen und timeZone "UTC" (ohne 'Z').

    def add_series(self, subject: str, first_start_utc: datetime, *, count: int, every_days: int = 7,
                   duration: timedelta = timedelta(hours=1), sensitivity: str = "normal",
                   location: str = "", body: str = "") -> str:
        master_id = f"series-{self._next_id}"
        self._next_id += 1
        last_modified, change_key, etag = self._advance()
        self.series[master_id] = {
            "subject": subject, "first": first_start_utc, "count": count, "every": timedelta(days=every_days),
            "duration": duration, "sensitivity": sensitivity, "location": location, "body": body,
            "master_seq": self._seq, "exceptions": {}, "deleted": set(), "cancelled_meetings": set(),
        }
        self.events[master_id] = {
            "id": master_id, "type": "seriesMaster", "seriesMasterId": None, "subject": subject,
            "isAllDay": False, "start": _graph_dt(first_start_utc), "end": _graph_dt(first_start_utc + duration),
            "location": {"displayName": location}, "body": {"contentType": "text", "content": body},
            "sensitivity": sensitivity,
            "recurrence": {"pattern": {"type": "daily", "interval": every_days}, "range": {"type": "numbered", "numberOfOccurrences": count}},
            "lastModifiedDateTime": last_modified, "changeKey": change_key, "@odata.etag": etag, "_seq": self._seq,
        }
        return master_id

    def _touch_master(self, master_id: str) -> None:
        last_modified, change_key, etag = self._advance()
        self.series[master_id]["master_seq"] = self._seq
        self.events[master_id].update({"lastModifiedDateTime": last_modified, "changeKey": change_key,
                                       "@odata.etag": etag, "_seq": self._seq})

    def edit_series(self, master_id: str, **changes) -> None:
        """Serie als Ganzes in Outlook ändern (z. B. Betreff) -- alle Vorkommen bekommen neue etags."""
        self.series[master_id].update(changes)
        if "subject" in changes:
            self.events[master_id]["subject"] = changes["subject"]
        self._touch_master(master_id)

    def move_occurrence(self, master_id: str, original_start_utc: datetime, new_start_utc: datetime) -> None:
        """Ein Vorkommen einzeln verschieben -- wird zur exception mit eigenem etag."""
        _, _, etag = self._advance()
        self.series[master_id]["exceptions"][original_start_utc] = {"start": new_start_utc, "etag": etag}
        self._touch_master(master_id)

    def delete_occurrence(self, master_id: str, original_start_utc: datetime) -> None:
        self.series[master_id]["deleted"].add(original_start_utc)
        self._touch_master(master_id)

    def cancel_meeting_occurrence(self, master_id: str, original_start_utc: datetime) -> None:
        self.series[master_id]["cancelled_meetings"].add(original_start_utc)
        self._touch_master(master_id)

    def _instances(self, master_id: str) -> list[dict]:
        s = self.series[master_id]
        result = []
        for k in range(s["count"]):
            original = s["first"] + k * s["every"]
            if original in s["deleted"]:
                continue
            exception = s["exceptions"].get(original)
            start = exception["start"] if exception else original
            result.append({
                "@odata.etag": exception["etag"] if exception else f'W/"etag-{s["master_seq"]}-{original:%Y%m%d%H%M}"',
                "id": f"{master_id}-occ-{original:%Y%m%d%H%M}",
                "type": "exception" if exception else "occurrence",
                "seriesMasterId": master_id,
                "originalStart": original.isoformat() + "Z",
                "subject": s["subject"], "isAllDay": False,
                "start": _graph_dt(start), "end": _graph_dt(start + s["duration"]),
                "location": {"displayName": s["location"]},
                "body": {"contentType": "text", "content": s["body"]},
                "sensitivity": s["sensitivity"],
                "isCancelled": original in s["cancelled_meetings"],
                "_start": start, "_end": start + s["duration"],
            })
        return result

    def calendar_view(self, window_start: datetime, window_end: datetime) -> list[dict]:
        rows = []
        for ev in self.events.values():
            if ev["type"] != "singleInstance":
                continue
            s, e = _parse_graph_datetime(ev["start"]["dateTime"]), _parse_graph_datetime(ev["end"]["dateTime"])
            if s < window_end and e > window_start:
                rows.append({k: v for k, v in ev.items() if k not in ("_seq",)} | {"_start": s})
        for master_id in self.series:
            for inst in self._instances(master_id):
                if inst["_start"] < window_end and inst["_end"] > window_start:
                    rows.append(inst)
        rows.sort(key=lambda r: r["_start"])
        return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]

    def occurrence_ids_in(self, window_start: datetime, window_end: datetime) -> set[str]:
        """Unabhängig vom ERP-Code berechnete Erwartung: welche Vorkommen-IDs MÜSSEN im ERP stehen."""
        return {r["id"] for r in self.calendar_view(window_start, window_end)
                if r.get("type") in ("occurrence", "exception") and not r.get("isCancelled")}

    def patch(self, event_id: str, payload: dict) -> dict:
        last_modified, change_key, etag = self._advance()
        row = self.events[event_id]
        row.update({**_fields_from_payload(payload), "lastModifiedDateTime": last_modified,
                    "changeKey": change_key, "@odata.etag": etag, "_seq": self._seq})
        return dict(row)

    def delta(self, since_seq: int) -> tuple[list[dict], int]:
        # Realistisch (seit 1.7.5, siehe Modulkommentar oben): eine Delta-Zeile trägt niemals
        # changeKey, nur @odata.etag -- genau das musste erst korrigiert werden, damit ein Test
        # gegen diese Attrappe den echten Produktionsfehler überhaupt hätte finden können.
        items = [{k: v for k, v in ev.items() if k not in ("_seq", "changeKey")}
                 for ev in self.events.values() if ev["_seq"] > since_seq]
        max_seq = max((ev["_seq"] for ev in self.events.values()), default=since_seq)
        return items, max_seq


def make_realistic_urlopen(server: FakeGraphServer):
    """Baut die urlopen()-Attrappe für sync_user_calendar() gegen einen FakeGraphServer --
    beantwortet Token/POST(Create)/PATCH(Update)/GET(Delta) konsistent gegen dessen Zustand."""

    def fn(req, timeout=None):
        url = req.full_url
        if TOKEN_URL_MARKER in url:
            return _FakeResponse({"access_token": "faketoken"})
        method = req.get_method()
        if method in ("POST", "PATCH", "DELETE"):
            server.write_requests.append((method, url))
            target = url.rsplit("/", 1)[-1]
            if target in server.series or "-occ-" in target:
                raise AssertionError(f"Schreibzugriff auf eine Serie/ein Vorkommen: {method} {url}")
        if method == "POST" and "/delta" not in url:
            return _FakeResponse(server.create(json.loads(req.data)))
        if method == "PATCH":
            event_id = url.rsplit("/", 1)[-1]
            return _FakeResponse(server.patch(event_id, json.loads(req.data)))
        if method == "GET" and "/calendarView" in url:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            window_start = _parse_graph_datetime(query["startDateTime"][0])
            window_end = _parse_graph_datetime(query["endDateTime"][0])
            page_size = int(query["$top"][0])
            offset = int(query.get("skip", ["0"])[0])
            server.calendar_view_requests.append({"url": url, "prefer": req.get_header("Prefer")})
            rows = server.calendar_view(window_start, window_end)
            page = {"value": rows[offset:offset + page_size]}
            if offset + page_size < len(rows):
                base = url.split("&skip=")[0]
                page["@odata.nextLink"] = f"{base}&skip={offset + page_size}"
            return _FakeResponse(page)
        if method == "GET":
            since = int(url.split("seq=")[1].split("&")[0]) if "seq=" in url else 0
            items, max_seq = server.delta(since)
            return _FakeResponse({"value": items, "@odata.deltaLink": f"https://fake.graph.test/delta?seq={max_seq}"})
        raise AssertionError(f"unerwartete Anfrage in FakeGraphServer: {method} {url}")

    return fn


# ---------------------------------------------------------------------------
# Punkt 3 -- Zeitzonen, inkl. beider DST-Übergänge 2026
# ---------------------------------------------------------------------------


def test_to_utc_winter_offset_is_one_hour():
    assert to_utc(datetime(2026, 1, 15, 10, 0)) == datetime(2026, 1, 15, 9, 0)


def test_to_utc_summer_offset_is_two_hours():
    assert to_utc(datetime(2026, 7, 15, 10, 0)) == datetime(2026, 7, 15, 8, 0)


def test_to_utc_spring_forward_transition_2026_03_29():
    # Vor dem Sprung (02:00->03:00): noch Normalzeit, UTC+1.
    assert to_utc(datetime(2026, 3, 29, 1, 30)) == datetime(2026, 3, 29, 0, 30)
    # Nach dem Sprung: bereits Sommerzeit, UTC+2 -- derselbe Kalendertag, anderer Offset.
    assert to_utc(datetime(2026, 3, 29, 3, 30)) == datetime(2026, 3, 29, 1, 30)


def test_to_utc_fall_back_transition_2026_10_25():
    # Vor dem Rücksprung (03:00->02:00): noch Sommerzeit, UTC+2.
    assert to_utc(datetime(2026, 10, 25, 1, 30)) == datetime(2026, 10, 24, 23, 30)
    # Nach dem Rücksprung: bereits Normalzeit, UTC+1.
    assert to_utc(datetime(2026, 10, 25, 3, 30)) == datetime(2026, 10, 25, 2, 30)


@pytest.mark.parametrize("local", [
    datetime(2026, 1, 15, 10, 0), datetime(2026, 7, 15, 10, 0),
    datetime(2026, 3, 29, 1, 30), datetime(2026, 3, 29, 3, 30),
    datetime(2026, 10, 25, 1, 30), datetime(2026, 10, 25, 3, 30),
])
def test_round_trip_berlin_utc_berlin(local):
    assert to_berlin(to_utc(local)) == local


def test_event_payload_converts_to_utc_for_graph():
    from app.outlook_calendar_sync import _event_payload
    db = db_session()
    owner = _make_user(db)
    event = _make_event(db, owner, start_at=datetime(2026, 7, 10, 9, 0), end_at=datetime(2026, 7, 10, 10, 30))
    payload = _event_payload(event)
    assert payload["start"] == {"dateTime": "2026-07-10T07:00:00", "timeZone": "UTC"}
    assert payload["end"] == {"dateTime": "2026-07-10T08:30:00", "timeZone": "UTC"}
    # Punkt 2: Graph-Payload kennt project_id/quote_id strukturell nicht -- is_private wird
    # (seit 1.7.2) bewusst als "sensitivity" mitgeschickt, siehe test_push_maps_is_private_to_sensitivity.
    assert set(payload.keys()) == {"subject", "isAllDay", "start", "end", "location", "body", "sensitivity"}
    assert "project_id" not in payload and "quote_id" not in payload


# ---------------------------------------------------------------------------
# Nachtrag "Zweite Untersuchungsrunde" (seit 1.7.4), Punkt 1 -- real gefundener, unabhängiger
# Präzisions-Fehler: Graphs typisches 7-stelliges lastModifiedDateTime-Format ("Ticks").
# ---------------------------------------------------------------------------


def test_parse_graph_datetime_handles_seven_digit_fraction_seconds_regardless_of_python_version():
    """Microsofts lastModifiedDateTime/start/end tragen üblicherweise SIEBEN Nachkommastellen
    (100-Nanosekunden-'Ticks'), z. B. '2026-09-26T09:37:34.6472860Z' -- datetime.fromisoformat()
    akzeptiert das erst ab Python 3.11 (vorher: ValueError bei jeder Bruchteilsekundenlänge außer
    0/3/6 Ziffern). _parse_graph_datetime() kürzt deshalb VOR dem Parsen selbst auf sechs Stellen
    -- dieser Test läuft zwar auf JEDER Python-Version identisch grün (auch auf der 3.11+
    verwendet hier), belegt aber, dass das reale Graph-Format tatsächlich korrekt (und mit
    derselben Kürzungs-Konvention wie Pythons eigener 3.11+-Parser: die überzähligen Stellen
    werden abgeschnitten, nicht gerundet) verarbeitet wird -- unabhängig davon, welche
    Python-Version auf dem Produktivserver tatsächlich läuft."""
    assert _parse_graph_datetime("2026-09-26T09:37:34.6472860Z") == datetime(2026, 9, 26, 9, 37, 34, 647286)
    assert _parse_graph_datetime("2019-03-27T11:36:44.0466667Z") == datetime(2019, 3, 27, 11, 36, 44, 46666)
    # Randfälle, die weiterhin funktionieren müssen: kein Bruchteil, exakt sechs Stellen.
    assert _parse_graph_datetime("2026-09-26T09:37:34Z") == datetime(2026, 9, 26, 9, 37, 34)
    assert _parse_graph_datetime("2026-09-26T09:37:34.123456Z") == datetime(2026, 9, 26, 9, 37, 34, 123456)


# ---------------------------------------------------------------------------
# is_outlook_sync_available()
# ---------------------------------------------------------------------------


def test_is_outlook_sync_available_requires_global_switch_and_graph_config_and_mailbox():
    db = db_session()
    user = _make_user(db)
    assert is_outlook_sync_available(db, user) is False  # nichts konfiguriert
    update_outlook_sync_settings(db, enabled=True)
    assert is_outlook_sync_available(db, user) is False  # Graph-Zugangsdaten fehlen noch
    update_graph_settings(db, tenant_id="t", client_id="c", sender_mailbox="x@y.de", client_secret="s")
    assert is_outlook_sync_available(db, user) is True
    user.outlook_mailbox = None
    db.commit()
    assert is_outlook_sync_available(db, user) is False  # kein eigenes Postfach


# ---------------------------------------------------------------------------
# Push (lokal -> Outlook)
# ---------------------------------------------------------------------------


def test_push_creates_event_and_stores_outlook_event_id():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    captured = []

    def fake(req, timeout=None):
        captured.append((req.get_method(), req.full_url, req.data))
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        assert req.get_method() == "POST"
        assert req.full_url == _events_url(owner.outlook_mailbox)
        return _FakeResponse({"id": "graph-event-1"})

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    db.refresh(event)
    assert event.outlook_event_id == "graph-event-1"
    post_calls = [c for c in captured if c[0] == "POST" and TOKEN_URL_MARKER not in c[1]]
    assert len(post_calls) == 1
    body = json.loads(post_calls[0][2])
    assert body["subject"] == "Besichtigung"
    assert "project_id" not in body and "quote_id" not in body


def test_push_updates_existing_event_via_patch():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-existing"
    db.commit()
    captured = []

    def fake(req, timeout=None):
        captured.append((req.get_method(), req.full_url))
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(None)

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    patch_calls = [c for c in captured if c[0] == "PATCH"]
    assert patch_calls == [("PATCH", _events_url(owner.outlook_mailbox, "/graph-existing"))]


def test_push_create_stores_etag_from_graph_response():
    """Seit 1.7.5 (davor fälschlich changeKey, siehe Moduldocstring 'Nachtrag seit 1.7.5') --
    @odata.etag aus der Graph-Antwort wird zusammen mit outlook_event_id gespeichert, damit ein
    späterer Echo-Pull ihn exakt wiedererkennen kann. Die Antwort trägt bewusst BEIDES (wie ein
    echtes Graph-POST es tut) -- gespeichert wird ausschließlich @odata.etag, changeKey wird
    ignoriert."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse({"id": "graph-ck-1", "changeKey": "ckey-erster-push", "@odata.etag": 'W/"etag-erster-push"'})

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    db.refresh(event)
    assert event.outlook_etag == 'W/"etag-erster-push"'


def test_push_patch_stores_etag_from_graph_response_when_present():
    """Wie oben, aber für den Update-Weg (PATCH) -- Graph liefert bei einem erfolgreichen PATCH
    normalerweise die aktualisierte Ressource inkl. neuem @odata.etag zurück."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-existing-ck"
    event.outlook_etag = 'W/"etag-alt"'
    db.commit()

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse({"id": "graph-existing-ck", "changeKey": "ckey-neu-nach-patch", "@odata.etag": 'W/"etag-neu-nach-patch"'})

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    db.refresh(event)
    assert event.outlook_etag == 'W/"etag-neu-nach-patch"'


def test_push_response_with_changekey_but_no_etag_does_not_store_anything():
    """Nachtrag (seit 1.7.5) -- das eigentliche, real gefundene Problem: Graphs Delta-Antworten
    liefern NIE changeKey, nur @odata.etag (siehe Moduldocstring). Diese Zeile härtet die
    Umkehrung ab, damit ein künftiger Rückfall in die alte, falsche Annahme sofort auffällt --
    eine Push-Antwort, die (unrealistisch, aber zur Absicherung) NUR changeKey ohne @odata.etag
    trägt, darf outlook_etag NICHT verändern, auch nicht mit dem changeKey-Wert als Rückfall."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-only-changekey"
    event.outlook_etag = 'W/"etag-bleibt-stehen"'
    db.commit()

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse({"id": "graph-only-changekey", "changeKey": "ckey-ohne-etag"})

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    db.refresh(event)
    assert event.outlook_etag == 'W/"etag-bleibt-stehen"'


def test_push_patch_without_response_body_does_not_crash_and_leaves_etag_unset():
    """Randfall, bewusst offen gehalten (siehe Moduldocstring 'Nachtrag Schaukelnder Termin'):
    liefert Graph auf ein PATCH keinen Body (204-artig, wie im bestehenden
    test_push_updates_existing_event_via_patch simuliert), bleibt outlook_etag auf dem alten
    Stand stehen -- kein Absturz, die Zeitstempel-Logik greift beim nächsten Pull als Rückfall."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-no-body"
    event.outlook_etag = 'W/"etag-bleibt-stehen"'
    db.commit()

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(None)

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)  # darf nicht werfen

    db.refresh(event)
    assert event.outlook_etag == 'W/"etag-bleibt-stehen"'


@pytest.mark.parametrize("is_private,expected_sensitivity", [(True, "private"), (False, "normal")])
def test_push_maps_is_private_to_sensitivity(is_private, expected_sensitivity):
    """Umkehrung von Punkt 1 (Nachtrag seit 1.7.2) -- is_private ist die einzige Ausnahme, die
    ERP-seitig doch in die Graph-Anfrage einfließt, weil Outlook mit sensitivity ein natives
    Äquivalent kennt."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner, is_private=is_private)
    captured_bodies = []

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        captured_bodies.append(json.loads(req.data))
        return _FakeResponse({"id": "graph-sensitivity-1"})

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    assert captured_bodies[0]["sensitivity"] == expected_sensitivity


def test_successful_push_does_not_let_updated_at_drift_and_prevents_a_redundant_second_push():
    """Nachtrag (seit 1.7.2, Mechanismus seit 1.7.6 auf _write_sync_bookkeeping() umgestellt) --
    ein erfolgreicher Push darf updated_at nicht verschieben, outlook_synced_at muss danach exakt
    dem (unveränderten) updated_at entsprechen. Täte er das nicht, würde der Termin sofort wieder
    wie "noch zu übertragen" aussehen -- eine Endlosschleife aus unnötigen Pushes bei jedem
    weiteren Sync-Lauf, obwohl sich am Termin nichts geändert hat."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    original_updated_at = event.updated_at

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=lambda req, timeout=None: (
        _FakeResponse({"access_token": "faketoken"}) if TOKEN_URL_MARKER in req.full_url else _FakeResponse({"id": "graph-nodrift-1"})
    )):
        push_event_best_effort(db, event.id)

    db.refresh(event)
    assert event.updated_at == original_updated_at
    assert event.outlook_synced_at == original_updated_at
    assert _needs_push(event) is False

    with patch("app.outlook_calendar_sync.urllib.request.urlopen") as mocked:
        # Ein erneuter Sync-Lauf darf für diesen unveränderten Termin gar nicht erst versuchen,
        # ihn zu pushen -- sync_user_calendar() bräuchte sonst nur den Token-Aufruf, kein
        # PATCH/POST für diesen einen Termin.
        def fake(req, timeout=None):
            if TOKEN_URL_MARKER in req.full_url:
                return _FakeResponse({"access_token": "faketoken"})
            return _FakeResponse(_delta_page([], delta_link="https://graph.microsoft.com/deltaNoop"))
        mocked.side_effect = fake
        result = sync_user_calendar(db, owner)

    assert result["pushed_created"] == 0 and result["pushed_updated"] == 0


def test_write_sync_bookkeeping_never_changes_updated_at():
    """Nachtrag (seit 1.7.6) -- der eigentliche, empirisch gefundene Mechanismus hinter dem
    gemeldeten Dauer-Push: Column(..., onupdate=datetime.utcnow) greift bei JEDER UPDATE-Anweisung
    gegen calendar_events, sobald updated_at nicht explizit in .values() steht -- ein bloßes
    Weglassen der Spalte reicht NICHT, um sie zu schützen (siehe Moduldocstring "Nachtrag (seit
    1.7.6)"). Auf einer sauberen Zeile (keine andere Dirty-Markierung, exakt die Voraussetzung
    jedes der drei echten Aufrufer) muss die Selbstreferenz-Lösung updated_at exakt (nicht nur
    "meist") unverändert lassen."""
    db = db_session()
    owner = _make_user(db)
    event = _make_event(db, owner, title="Alt")
    original_updated_at = event.updated_at
    assert db.is_modified(event) is False  # Voraussetzung, wie bei jedem echten Aufrufer

    _write_sync_bookkeeping(db, event, outlook_synced_at=original_updated_at, outlook_event_id="graph-bk-1", outlook_etag='W/"bookkeeping-1"')

    db.refresh(event)
    assert event.updated_at == original_updated_at
    assert event.outlook_synced_at == original_updated_at
    assert event.outlook_event_id == "graph-bk-1"
    assert event.outlook_etag == 'W/"bookkeeping-1"'


def test_write_sync_bookkeeping_rejects_a_row_with_unrelated_dirty_state():
    """Zweite, unabhängige Absicherung (siehe _write_sync_bookkeeping()-Docstring) -- die
    Selbstreferenz allein schützt NICHT vor einem vorangehenden Autoflush einer ANDEREN, über
    gewöhnliches setattr() erzeugten Änderung (empirisch bestätigt: genau das erzeugte trotz
    Selbstreferenz einen echten, persistierten Millisekunden-Versatz). Ein Aufrufer, der das
    versehentlich täte, MUSS deshalb sofort und laut scheitern, statt den ursprünglich gemeldeten
    Fehler ein drittes Mal still zu wiederholen."""
    db = db_session()
    owner = _make_user(db)
    event = _make_event(db, owner, title="Alt")
    event.title = "Versehentlich dirty gelassen"  # genau das Muster, das den Fehler auslöste

    with pytest.raises(AssertionError):
        _write_sync_bookkeeping(db, event, outlook_synced_at=event.updated_at)


def test_push_failure_is_best_effort_and_does_not_raise():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)

    def fake(req, timeout=None):
        raise urllib.error.URLError("kein Netzwerk")

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)  # darf nicht werfen

    db.refresh(event)
    assert event.outlook_event_id is None


def test_push_is_noop_when_sync_disabled():
    db = db_session()
    owner = _make_user(db)
    event = _make_event(db, owner)  # _enable_sync() NICHT aufgerufen
    with patch("app.outlook_calendar_sync.urllib.request.urlopen") as mocked:
        push_event_best_effort(db, event.id)
        mocked.assert_not_called()


# ---------------------------------------------------------------------------
# Löschungen beidseitig (Punkt 5) -- ERP -> Outlook
# ---------------------------------------------------------------------------


def test_try_delete_remote_event_calls_graph_delete_and_returns_true():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-to-delete"
    db.commit()
    captured = []

    def fake(req, timeout=None):
        captured.append((req.get_method(), req.full_url))
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(None)

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = try_delete_remote_event(db, event)

    assert result is True
    assert ("DELETE", _events_url(owner.outlook_mailbox, "/graph-to-delete")) in captured


def test_try_delete_remote_event_returns_false_on_failure_without_raising():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-to-delete"
    db.commit()

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=_token_only()):
        result = try_delete_remote_event(db, event)  # Token klappt, DELETE liefert 403 -> False, kein Raise

    assert result is False


def test_try_delete_remote_event_is_noop_without_outlook_id():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)  # nie gepusht
    with patch("app.outlook_calendar_sync.urllib.request.urlopen") as mocked:
        assert try_delete_remote_event(db, event) is True
        mocked.assert_not_called()


# ---------------------------------------------------------------------------
# Pull (Outlook -> lokal), Delta-Abfrage
# ---------------------------------------------------------------------------


def _delta_page(items, *, next_link=None, delta_link=None):
    page = {"value": items}
    if next_link:
        page["@odata.nextLink"] = next_link
    if delta_link:
        page["@odata.deltaLink"] = delta_link
    return page


def test_sync_creates_local_event_from_outlook_without_project_or_quote_link():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    item = {
        "id": "graph-new-1", "subject": "Kundentermin", "isAllDay": False,
        "start": {"dateTime": "2026-06-01T08:00:00Z"}, "end": {"dateTime": "2026-06-01T09:00:00Z"},
        "location": {"displayName": "Beim Kunden"}, "body": {"content": "Notiz aus Outlook"},
        "lastModifiedDateTime": "2026-05-01T00:00:00Z",
    }

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaFinal1"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["created"] == 1
    row = db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == "graph-new-1"))
    assert row is not None
    assert row.external_source == "outlook"
    assert row.project_id is None
    assert row.quote_id is None
    assert row.title == "Kundentermin"
    assert row.start_at == to_berlin(datetime(2026, 6, 1, 8, 0))
    assert row.is_private is False  # keine sensitivity im Item -> nicht privat

    state = get_or_create_sync_state(db, owner)
    assert state.delta_link == "https://graph.microsoft.com/deltaFinal1"
    assert state.last_error_type is None


@pytest.mark.parametrize("sensitivity,expected_is_private", [
    ("private", True), ("confidential", True), ("personal", False), ("normal", False), (None, False),
])
def test_pull_maps_outlook_sensitivity_to_is_private_on_create(sensitivity, expected_is_private):
    """Punkt 1 der Anfrage -- 'private'/'confidential' gelten als vertraulich, 'personal' bewusst
    NICHT (geringere Stufe, in der Anfrage nicht genannt)."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    item = {
        "id": "graph-sens-1", "subject": "Termin", "isAllDay": False,
        "start": {"dateTime": "2026-06-01T08:00:00Z"}, "end": {"dateTime": "2026-06-01T09:00:00Z"},
        "location": {}, "body": {"content": ""}, "lastModifiedDateTime": "2026-05-01T00:00:00Z",
    }
    if sensitivity is not None:
        item["sensitivity"] = sensitivity

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaSens1"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        sync_user_calendar(db, owner)

    row = db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == "graph-sens-1"))
    assert row.is_private is expected_is_private


def test_a_private_synced_event_is_shown_as_busy_to_a_colleague_end_to_end():
    """Punkt 1, Ende-zu-Ende: das eigentliche Ziel ('Kollegen dürfen solche Termine nur als
    belegt sehen') über die bereits in Stufe 1 gebaute, hier unveränderte Privatsphäre-Redaktion
    (app/calendar_events.py) -- kein Sonderfall für Outlook-Termine nötig, sobald is_private
    korrekt gesetzt ist."""
    db = db_session()
    owner = _make_user(db, username="ownerprivate")
    colleague = _make_user(db, username="colleague", mailbox=None, role="buero_finanzen")
    _enable_sync(db)
    item = {
        "id": "graph-sens-2", "subject": "Vertrauliches Gespräch", "isAllDay": False,
        "start": {"dateTime": "2026-06-01T08:00:00Z"}, "end": {"dateTime": "2026-06-01T09:00:00Z"},
        "location": {"displayName": "Chefbüro"}, "body": {"content": ""}, "sensitivity": "confidential",
        "lastModifiedDateTime": "2026-05-01T00:00:00Z",
    }

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaSens2"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        sync_user_calendar(db, owner)

    rows = {row["outlook_event_id"]: row for row in list_events(db)}
    data = rows["graph-sens-2"]
    assert data["is_private"] is True

    # Der Besitzer selbst sieht den Termin weiterhin voll (Muster test_privacy_redaction_own_vs_colleague).
    assert is_redacted_for_viewer(data, owner.id) is False
    # Ein Kollege sieht ihn nur als "Belegt", genau wie einen ERP-eigenen privaten Termin.
    assert is_redacted_for_viewer(data, colleague.id) is True
    reduced = redact_for_busy(data)
    assert reduced["title"] == "Belegt"
    assert "location" not in reduced and "notes" not in reduced


def _seed_project(db):
    customer = Customer(name="Kunde X", last_name="X")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    project = Project(project_number="P-OUT-0001", customer_id=customer.id, name="Testprojekt",
                       pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def test_incoming_newer_change_updates_fields_but_never_touches_project_link():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    project = _seed_project(db)
    event = _make_event(db, owner, title="Alter Titel", project_id=project.id)
    event.outlook_event_id = "graph-existing-2"
    event.updated_at = datetime(2020, 1, 1)  # bewusst alt -- Graph soll gewinnen
    db.commit()

    item = {
        "id": "graph-existing-2", "subject": "Neuer Titel aus Outlook", "isAllDay": False,
        "start": {"dateTime": "2026-06-02T08:00:00Z"}, "end": {"dateTime": "2026-06-02T09:00:00Z"},
        "location": {"displayName": "Neuer Ort"}, "body": {"content": ""}, "sensitivity": "confidential",
        "lastModifiedDateTime": "2026-06-01T12:00:00Z",
    }

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaFinal2"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["updated"] == 1
    db.refresh(event)
    assert event.title == "Neuer Titel aus Outlook"
    assert event.location == "Neuer Ort"
    # Punkt 1 (Nachtrag) -- sensitivity wird auch bei einer eingehenden ÄNDERUNG übernommen, nicht
    # nur beim erstmaligen Anlegen.
    assert event.is_private is True
    # Punkt 2 -- das eigentliche Kernstück dieses Tests:
    assert event.project_id == project.id
    # Nachtrag (seit 1.7.2, Mechanismus seit 1.7.6 auf _write_sync_bookkeeping() umgestellt) --
    # outlook_synced_at übernimmt exakt den TATSÄCHLICH generierten updated_at-Wert, kein Push nötig.
    assert event.outlook_synced_at == event.updated_at
    assert _needs_push(event) is False


def test_delta_item_with_an_etag_we_already_know_is_recognized_as_our_own_echo_and_skipped():
    """Nachtrag 'Schaukelnder Termin' (seit 1.7.3, Feld seit 1.7.5 auf @odata.etag umgestellt),
    Punkt 2 der Anfrage -- der eigentliche, uhrzeitUNABHÄNGIGE Echo-Test: der Delta-Eintrag trägt
    bewusst einen lastModifiedDateTime, der NACH existing.updated_at liegt (genau der Fall, der
    die reine Zeitstempel-Heuristik allein zum Absorbieren bewegen würde -- siehe
    test_incoming_newer_change_updates_fields_but_never_touches_project_link oben). Trägt der
    Eintrag aber EXAKT den @odata.etag, den wir selbst zuletzt gespeichert haben (aus einem
    eigenen Push oder einer bereits absorbierten Änderung), wird er als eigenes Echo erkannt und
    komplett übersprungen -- kein Feld wird angefasst, kein _write_sync_bookkeeping()-Aufruf,
    updated_at/outlook_synced_at bleiben unverändert (seit 1.7.6 zusätzlich strukturell
    abgesichert, siehe test_write_sync_bookkeeping_never_changes_updated_at unten)."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner, title="Unverändert", location="Ursprünglicher Ort")
    event.outlook_event_id = "graph-echo-1"
    event.outlook_etag = 'W/"etag-bereits-bekannt"'
    original_updated_at = datetime.utcnow()
    event.updated_at = original_updated_at
    event.outlook_synced_at = original_updated_at
    db.commit()

    item = {
        # Bewusst KEIN changeKey-Feld -- eine echte Delta-Zeile trägt es nie (siehe
        # Moduldocstring "Nachtrag seit 1.7.5"), ein Test, der es trotzdem mitgäbe, würde eine
        # realistischere Attrappe wieder vortäuschen.
        "id": "graph-echo-1", "@odata.etag": 'W/"etag-bereits-bekannt"', "subject": "GEÄNDERT?!",
        "isAllDay": False,
        "start": {"dateTime": "2026-06-01T08:00:00Z"}, "end": {"dateTime": "2026-06-01T09:00:00Z"},
        "location": {"displayName": "Anderer Ort"}, "body": {"content": ""},
        # Bewusst NEUER als existing.updated_at -- ohne die etag-Prüfung würde bereits die
        # bestehende Zeitstempel-Heuristik allein diesen Eintrag absorbieren.
        "lastModifiedDateTime": (original_updated_at + timedelta(hours=1)).isoformat() + "Z",
    }

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaEcho1"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["updated"] == 0
    db.refresh(event)
    assert event.title == "Unverändert"
    assert event.location == "Ursprünglicher Ort"
    assert event.updated_at == original_updated_at
    assert event.outlook_synced_at == original_updated_at
    assert _needs_push(event) is False


def test_delta_item_carrying_only_changekey_is_not_recognized_as_echo_via_changekey_fallback():
    """Nachtrag (seit 1.7.5) -- die direkte Gegenprobe zum eigentlichen Produktionsfund: eine
    Delta-Zeile, die (unrealistisch, aber zur Absicherung) NUR changeKey trägt und KEIN
    @odata.etag, darf NICHT über einen etwaigen changeKey-Rückfall als Echo erkannt werden --
    der Mechanismus vergleicht ausschließlich @odata.etag, es gibt keinen zweiten,
    changeKey-basierten Vergleichspfad mehr. Ohne @odata.etag greift stattdessen unverändert die
    Zeitstempel-Heuristik; hier bewusst mit einem ÄLTEREN lastModifiedDateTime, damit der Eintrag
    aus einem anderen, unabhängigen Grund (nicht neuer als updated_at) übersprungen wird -- das
    beweist, dass changeKey an dieser Stelle wirkungslos ist, ohne einen dritten, hier nicht
    interessierenden Effekt (eine echte Feldübernahme) ins Spiel zu bringen."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner, title="Unverändert")
    event.outlook_event_id = "graph-changekey-only"
    event.outlook_etag = 'W/"etag-bereits-bekannt"'
    original_updated_at = datetime.utcnow()
    event.updated_at = original_updated_at
    event.outlook_synced_at = original_updated_at
    db.commit()

    item = {
        # changeKey trifft absichtlich exakt das, was frühere (1.7.3) Code-Fassungen verglichen
        # hätten -- kein @odata.etag. Der neue Mechanismus darf das nicht als Echo lesen.
        "id": "graph-changekey-only", "changeKey": "irrelevant-fuer-die-echo-erkennung",
        "subject": "GEÄNDERT?!", "isAllDay": False,
        "start": {"dateTime": "2026-06-01T08:00:00Z"}, "end": {"dateTime": "2026-06-01T09:00:00Z"},
        "location": {"displayName": "Anderer Ort"}, "body": {"content": ""},
        "lastModifiedDateTime": (original_updated_at - timedelta(hours=1)).isoformat() + "Z",
    }

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaChangeKeyOnly"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    # Übersprungen, aber über den Zeitstempel-Rückfall ("Graph nicht neuer"), NICHT über ein
    # (nicht existierendes) changeKey-Echo -- die Zeile bleibt in jedem Fall unverändert.
    assert result["updated"] == 0
    db.refresh(event)
    assert event.title == "Unverändert"
    assert event.outlook_etag == 'W/"etag-bereits-bekannt"'


def test_local_change_wins_over_older_graph_change_and_gets_pushed_instead():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner, title="Lokal aktueller Titel")
    event.outlook_event_id = "graph-existing-3"
    # Bewusst explizit auf "früher schon einmal synchronisiert" gesetzt (nicht NULL) -- sonst
    # würde _needs_push() nur über den outlook_synced_at-is-None-Zweig True liefern, nicht über
    # den hier eigentlich geprüften "updated_at > outlook_synced_at"-Vergleich.
    event.outlook_synced_at = datetime(2020, 1, 1)
    event.updated_at = datetime.utcnow()  # frisch -- lokal soll gewinnen
    db.commit()

    item = {
        "id": "graph-existing-3", "subject": "Veralteter Outlook-Titel", "isAllDay": False,
        "start": {"dateTime": "2026-05-04T07:00:00Z"}, "end": {"dateTime": "2026-05-04T08:00:00Z"},
        "location": {"displayName": "x"}, "body": {"content": ""},
        "lastModifiedDateTime": "2020-01-01T00:00:00Z",  # deutlich älter als event.updated_at
    }
    patch_urls = []

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        if req.get_method() == "PATCH":
            patch_urls.append(req.full_url)
            return _FakeResponse(None)
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaFinal3"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["updated"] == 0  # Graph-Änderung wurde NICHT übernommen
    db.refresh(event)
    assert event.title == "Lokal aktueller Titel"
    # Die lokal gewonnene Zeile wird stattdessen im selben Lauf nach Outlook geschrieben:
    assert result["pushed_updated"] == 1
    assert patch_urls == [_events_url(owner.outlook_mailbox, "/graph-existing-3")]


def test_recurring_series_master_is_skipped_not_created():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    item = {
        "id": "graph-series-1", "subject": "Wöchentliches Jour Fixe", "type": "seriesMaster",
        "recurrence": {"pattern": {"type": "weekly"}},
        "start": {"dateTime": "2026-06-01T08:00:00Z"}, "end": {"dateTime": "2026-06-01T09:00:00Z"},
        "lastModifiedDateTime": "2026-05-01T00:00:00Z",
    }

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaFinal4"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["skipped_recurring"] == 1
    assert result["created"] == 0
    assert db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == "graph-series-1")) is None


def test_removed_delta_entry_deletes_local_event():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-to-be-removed"
    db.commit()
    event_id = event.id

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([{"id": "graph-to-be-removed", "@removed": {"reason": "deleted"}}],
                                          delta_link="https://graph.microsoft.com/deltaFinal5"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["deleted"] == 1
    assert db.get(CalendarEvent, event_id) is None


def test_delta_pagination_follows_next_link_until_delta_link():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    page2_url = "https://graph.microsoft.com/v1.0/users/tobias@dachkonzepte.gmbh/events/delta?%24skiptoken=abc"
    item = {
        "id": "graph-paged-1", "subject": "Termin von Seite 2", "isAllDay": False,
        "start": {"dateTime": "2026-06-03T08:00:00Z"}, "end": {"dateTime": "2026-06-03T09:00:00Z"},
        "location": {}, "body": {"content": ""}, "lastModifiedDateTime": "2026-05-01T00:00:00Z",
    }
    requested_urls = []

    def fake(req, timeout=None):
        requested_urls.append(req.full_url)
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        if req.full_url == page2_url:
            return _FakeResponse(_delta_page([item], delta_link="https://graph.microsoft.com/deltaFinal6"))
        return _FakeResponse(_delta_page([], next_link=page2_url))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["created"] == 1
    assert page2_url in requested_urls
    state = get_or_create_sync_state(db, owner)
    assert state.delta_link == "https://graph.microsoft.com/deltaFinal6"


def test_second_sync_reuses_stored_delta_link_instead_of_full_query():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    requested_urls = []

    def fake(req, timeout=None):
        requested_urls.append(req.full_url)
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([], delta_link="https://graph.microsoft.com/deltaRound1"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        sync_user_calendar(db, owner)

    requested_urls.clear()

    def fake_second(req, timeout=None):
        requested_urls.append(req.full_url)
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        assert req.full_url == "https://graph.microsoft.com/deltaRound1"
        return _FakeResponse(_delta_page([], delta_link="https://graph.microsoft.com/deltaRound2"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake_second):
        sync_user_calendar(db, owner)

    assert "https://graph.microsoft.com/deltaRound1" in requested_urls


def test_sync_is_noop_when_globally_disabled_or_no_mailbox():
    db = db_session()
    owner = _make_user(db, mailbox=None)  # kein Postfach
    with patch("app.outlook_calendar_sync.urllib.request.urlopen") as mocked:
        result = sync_user_calendar(db, owner)
        mocked.assert_not_called()
    assert result["skipped"] is True


def test_sync_failure_is_recorded_on_state_without_raising():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=_token_only()):
        result = sync_user_calendar(db, owner)  # Token ok, Delta-Abfrage liefert 403

    assert result["error"] is True
    assert result["error_type"] == "OutlookSyncError"
    state = get_or_create_sync_state(db, owner)
    assert state.last_error_type == "OutlookSyncError"
    assert state.last_error_at is not None


def test_one_failing_push_does_not_roll_back_a_sibling_rows_successful_push_in_the_same_run():
    """Nachtrag (seit 1.7.2), Fund 1 -- vor der Behebung committete die Push-Phase erst am Ende
    der gesamten Schleife: schlug EIN Termin fehl, riss das äußere except/db.rollback() eine
    bereits erfolgreich zugewiesene outlook_event_id eines FRÜHEREN Termins in DERSELBEN Schleife
    wieder ein -- der nächste Lauf hätte ihn dadurch ein zweites Mal in Outlook angelegt."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    ok_event = _make_event(db, owner, title="OK")
    fails_event = _make_event(db, owner, title="FAILS")

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        if req.get_method() == "POST":
            body = json.loads(req.data)
            if body["subject"] == "FAILS":
                raise _http_error(400, "ungültiges Format")
            return _FakeResponse({"id": "graph-ok-1"})
        return _FakeResponse(_delta_page([], delta_link="https://graph.microsoft.com/deltaRetry1"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["pushed_created"] == 1
    assert result["push_failed"] == 1
    db.refresh(ok_event)
    db.refresh(fails_event)
    # Das eigentliche Kernstück: der erfolgreiche Nachbar-Termin bleibt gepusht, unabhängig davon,
    # dass ein ANDERER Termin in derselben Schleife fehlschlug.
    assert ok_event.outlook_event_id == "graph-ok-1"
    assert fails_event.outlook_event_id is None


def test_a_single_stuck_row_is_still_retried_after_a_later_successful_run_advances_the_mailbox_watermark():
    """Nachtrag (seit 1.7.2), Fund 2 -- das eigentliche Kernstück der Anfrage ('wird ein
    fehlgeschlagener Push beim nächsten Lauf wiederholt?'). Simuliert: ein Termin wurde früher
    bereits erfolgreich synchronisiert (outlook_synced_at gesetzt), dann lokal bearbeitet, dann
    schlägt sein Push in einem Lauf fehl, WÄHREND ein anderer Termin im selben Lauf erfolgreich
    ist und dadurch OutlookCalendarSyncState.last_synced_at vorrückt. Unter der ursprünglichen,
    rein postfachweiten last_synced_at-Prüfung wäre der hängengebliebene Termin damit für immer
    verloren gegangen (sein updated_at liegt VOR dem neuen, vorgerückten last_synced_at) --
    outlook_synced_at (pro Termin) behebt das nachweislich."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    stuck = _make_event(db, owner, title="STUCK")
    stuck.outlook_event_id = "graph-stuck-1"
    stuck.outlook_synced_at = datetime(2020, 1, 1)  # "früher schon einmal synchronisiert"
    stuck.updated_at = datetime(2024, 6, 1)  # danach lokal bearbeitet
    db.commit()
    sibling = _make_event(db, owner, title="SIBLING")

    def fake_run_1(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        if req.get_method() == "PATCH":
            raise _http_error(400, "vorübergehender Fehler")
        if req.get_method() == "POST":
            return _FakeResponse({"id": "graph-sibling-1"})
        return _FakeResponse(_delta_page([], delta_link="https://graph.microsoft.com/deltaRetry2a"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake_run_1):
        result_1 = sync_user_calendar(db, owner)

    assert result_1["push_failed"] == 1
    assert result_1["pushed_created"] == 1
    db.refresh(stuck)
    state = get_or_create_sync_state(db, owner)
    # Die eigentliche Falle: last_synced_at ist jetzt NEUER als stuck.updated_at.
    assert state.last_synced_at > stuck.updated_at
    # ... trotzdem bleibt _needs_push() für "stuck" wahr, weil es pro Termin, nicht postfachweit
    # entscheidet:
    assert _needs_push(stuck) is True

    def fake_run_2(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        if req.get_method() == "PATCH":
            return _FakeResponse(None)  # klappt diesmal
        return _FakeResponse(_delta_page([], delta_link="https://graph.microsoft.com/deltaRetry2b"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake_run_2):
        result_2 = sync_user_calendar(db, owner)

    assert result_2["pushed_updated"] == 1
    db.refresh(stuck)
    assert stuck.outlook_synced_at == stuck.updated_at


def _check_no_oscillation(db, owner, server: "FakeGraphServer | None" = None) -> None:
    """Der eigentliche Regressionstest für das gemeldete Verhalten ('Lauf 1: 1 geändert/0
    gepusht, Lauf 2: 0 geändert/1 gepusht, und so weiter im Wechsel') -- als eigene Funktion, damit
    sie sowohl gegen SQLite (Standard) als auch gegen eine echte PostgreSQL-Instanz laufen kann
    (Nachtrag "Zweite Untersuchungsrunde", Punkt 5 -- siehe die beiden Aufrufer unten UND
    CLAUDE.md "Kalender" -> "Stufe 2"). Läuft gegen FakeGraphServer (echter Zustand, siehe
    Modulkommentar oben) -- KEINE der ursprünglichen, handgebauten Antworten in dieser Datei
    bildete den entscheidenden Rundlauf ab (eigener Push kommt beim nächsten Delta-Abruf als
    scheinbar fremde Änderung zurück). Ohne dass irgendjemand den Termin anfasst, muss ab dem
    ZWEITEN Lauf (der die anfängliche Push-Bestätigung verarbeitet) für JEDEN weiteren Lauf
    gelten: created=updated=deleted=pushed_created=pushed_updated=0 -- über mindestens fünf
    weitere Läufe hinweg, nicht nur einmalig.

    **Nachtrag (seit 1.7.6, auf ausdrücklichen Wunsch)**: jeder Lauf verwendet eine GENUINE NEUE
    Session, gebunden an dieselbe Engine -- nicht mehr die über alle sieben Läufe wiederverwendete
    Session der ursprünglichen Fassung. Simuliert einen neuen Cron-Prozess je Tick
    (scripts/sync_outlook_calendars.py startet tatsächlich als eigener Prozess mit eigener
    Session bei jedem Tick, siehe dortiger Kopfkommentar) -- eine über alle Läufe geteilte Session
    hätte die Identity-Map/Dirty-Zustände zwischen den Läufen künstlich zusammenhalten können,
    was in Produktion nie der Fall ist.

    **Seit 1.7.8**: optional mit einem vorbelegten server (Serien, siehe
    test_no_oscillation_with_series_...) -- die Serienzähler müssen ab Lauf 2 ebenfalls bei 0
    stehen, und der Server darf über alle sieben Läufe genau EINEN Schreibzugriff sehen (den
    POST des einen Einzeltermins aus Lauf 1)."""
    event = _make_event(db, owner)
    event_id = event.id
    owner_id = owner.id
    engine = db.get_bind()
    db.close()
    server = server or FakeGraphServer()
    has_series = bool(server.series)

    def run():
        fresh = sessionmaker(bind=engine)()
        try:
            fresh_owner = fresh.get(AppUser, owner_id)
            with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
                return sync_user_calendar(fresh, fresh_owner)
        finally:
            fresh.close()

    first = run()
    assert first.get("error") is None, f"Lauf 1: error={first.get('error_type')}"
    assert first["created"] == 0
    assert first["updated"] == 0
    assert first["pushed_created"] == 1  # der einzige Lauf, der überhaupt etwas zu tun hat
    assert first["pushed_updated"] == 0
    assert first["series_failed"] == 0
    if has_series:
        assert first["series_created"] > 0

    for lauf in range(2, 8):  # fünf weitere Läufe (2 bis 7 inklusive) -- wie ausdrücklich verlangt
        result = run()
        assert result.get("error") is None, f"Lauf {lauf}: error={result.get('error_type')}"
        for key in ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed",
                    "series_created", "series_updated", "series_deleted", "series_failed"):
            assert result[key] == 0, f"Lauf {lauf}: {key}={result[key]} (erwartet 0)"

    assert [m for m, _ in server.write_requests] == ["POST"], server.write_requests

    final = sessionmaker(bind=engine)()
    try:
        event = final.get(CalendarEvent, event_id)
        assert event.outlook_event_id is not None
        assert event.outlook_etag is not None
        assert event.updated_at == event.outlook_synced_at
    finally:
        final.close()


def test_no_oscillation_all_counters_reach_zero_from_the_second_run_and_stay_zero_for_five_more_runs():
    """Nachtrag 'Schaukelnder Termin' (seit 1.7.3), Punkt 4 der ursprünglichen Anfrage -- siehe
    _check_no_oscillation() für die volle Begründung. Läuft hier gegen SQLite (Standard, schnell,
    keine externe Voraussetzung) -- die PostgreSQL-Variante steht direkt darunter."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    _check_no_oscillation(db, owner)


@requires_postgres_opt_in
def test_no_oscillation_all_counters_reach_zero_from_the_second_run_and_stay_zero_for_five_more_runs_postgresql():
    """Wie oben, aber gegen eine ECHTE, lokale PostgreSQL-Instanz -- Nachtrag "Zweite
    Untersuchungsrunde" (seit 1.7.4), Punkt 5 der Anfrage: "Der Schaukel-Test soll künftig auch
    gegen PostgreSQL laufen können." Nur aktiv, wenn ERP_TEST_POSTGRES_URL gesetzt ist (siehe
    requires_postgres_opt_in oben) -- Standard-Testlauf bleibt SQLite-only, kein externer
    Dienst wird dafür vorausgesetzt."""
    db, engine = pg_db_session()
    try:
        _cleanup_pg_test_data(db, "pgtest_schaukel_1")
        owner = _make_user(db, username="pgtest_schaukel_1", mailbox="pgtest_schaukel_1@dachkonzepte.gmbh")
        _enable_sync(db)
        _check_no_oscillation(db, owner)
    finally:
        _cleanup_pg_test_data(db, "pgtest_schaukel_1")
        db.close()
        engine.dispose()


def _check_no_oscillation_with_genuine_edit(db, owner) -> None:
    """Ergänzung zu _check_no_oscillation() -- prüft, dass die etag-Absicherung (seit 1.7.5,
    davor fälschlich changeKey) eine ECHTE, spätere Änderung durch jemand anderen (direkt in
    Outlook) nicht verschluckt: die muss weiterhin ganz normal als 'updated' absorbiert werden,
    und DANACH muss wieder Ruhe einkehren, unabhängig vom neu gesetzten etag.

    **Nachtrag (seit 1.7.6)**: wie _check_no_oscillation() -- jeder Lauf verwendet eine GENUINE
    NEUE Session, gebunden an dieselbe Engine, statt der ursprünglich wiederverwendeten."""
    _make_event(db, owner)
    owner_id = owner.id
    engine = db.get_bind()
    db.close()
    server = FakeGraphServer()

    def run():
        fresh = sessionmaker(bind=engine)()
        try:
            fresh_owner = fresh.get(AppUser, owner_id)
            with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
                return sync_user_calendar(fresh, fresh_owner)
        finally:
            fresh.close()

    run()  # Lauf 1: pusht die Neuanlage
    run()  # Lauf 2: absorbiert/erkennt das eigene Echo, kommt zur Ruhe

    # Jemand ändert den Termin DIREKT in Outlook (nicht über push_event_best_effort/sync_user_calendar).
    [graph_id] = server.events.keys()
    server.patch(graph_id, {
        "subject": "Von einem Kollegen direkt in Outlook geändert", "isAllDay": False,
        "start": server.events[graph_id]["start"], "end": server.events[graph_id]["end"],
        "location": {"displayName": "Neuer Ort aus Outlook"}, "body": {"content": ""},
    })

    genuine_change_run = run()
    assert genuine_change_run["updated"] == 1
    # NACH owner_user_id mitfiltern, wie die echte sync-Logik es auch tut (outlook_event_id trägt
    # bewusst KEINEN Unique-Constraint, siehe Klassendocstring in app/models.py) -- ohne diese
    # Einschränkung könnte eine Zeile eines ANDEREN Postfachs mit zufällig demselben
    # outlook_event_id (z. B. "graph-1", da FakeGraphServer je Testlauf wieder bei 1 beginnt)
    # zurückgegeben werden. Genau das ist bei der Entwicklung dieses Tests gegen eine geteilte,
    # nicht zwischen Testläufen bereinigte PostgreSQL-Instanz real passiert -- ein Testartefakt,
    # kein Fund im Produktcode, siehe CLAUDE.md "Kalender" -> "Stufe 2" -> "Zweite
    # Untersuchungsrunde" für die vollständige Herleitung.
    verify = sessionmaker(bind=engine)()
    try:
        row = verify.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == graph_id, CalendarEvent.owner_user_id == owner_id))
        assert row.title == "Von einem Kollegen direkt in Outlook geändert"
        assert row.location == "Neuer Ort aus Outlook"
    finally:
        verify.close()

    for lauf in range(1, 4):
        result = run()
        for key in ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed"):
            assert result[key] == 0, f"Lauf nach der echten Änderung, +{lauf}: {key}={result[key]}"


def test_no_oscillation_holds_even_with_a_genuine_later_edit_from_outlook_in_between():
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    _check_no_oscillation_with_genuine_edit(db, owner)


@requires_postgres_opt_in
def test_no_oscillation_holds_even_with_a_genuine_later_edit_from_outlook_in_between_postgresql():
    """PostgreSQL-Variante, wie oben bei der reinen Schaukel-Prüfung."""
    db, engine = pg_db_session()
    try:
        _cleanup_pg_test_data(db, "pgtest_schaukel_2")
        owner = _make_user(db, username="pgtest_schaukel_2", mailbox="pgtest_schaukel_2@dachkonzepte.gmbh")
        _enable_sync(db)
        _check_no_oscillation_with_genuine_edit(db, owner)
    finally:
        _cleanup_pg_test_data(db, "pgtest_schaukel_2")
        db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Punkt 6 -- kein Termininhalt in Protokollen
# ---------------------------------------------------------------------------


def test_no_event_content_ever_appears_in_a_log_record(caplog):
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    secret_marker = "GEHEIMER TERMINTITEL 9f8e7d"
    event = _make_event(db, owner, title=secret_marker, location="Streng vertraulicher Ort")

    with caplog.at_level(logging.DEBUG, logger="app.outlook_calendar_sync"):
        # Erfolgreicher Push.
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=lambda req, timeout=None: (
            _FakeResponse({"access_token": "faketoken"}) if TOKEN_URL_MARKER in req.full_url else _FakeResponse({"id": "graph-logtest"})
        )):
            push_event_best_effort(db, event.id)
        # Fehlschlagender Sync (löst eine Protokollzeile mit Fehlerart aus).
        db.refresh(event)
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=_token_only()):
            sync_user_calendar(db, owner)

    for record in caplog.records:
        message = record.getMessage()
        assert secret_marker not in message
        assert "Streng vertraulicher Ort" not in message


# ---------------------------------------------------------------------------
# Nachtrag "Zweite Untersuchungsrunde" (seit 1.7.4), Punkt 4 -- abschaltbare Diagnosezeile.
# ---------------------------------------------------------------------------


def test_diagnostics_enabled_reads_env_var(monkeypatch):
    monkeypatch.delenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", raising=False)
    assert diagnostics_enabled() is False
    for value in ("1", "true", "True", "yes", "YES"):
        monkeypatch.setenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", value)
        assert diagnostics_enabled() is True
    for value in ("0", "false", "", "nein"):
        monkeypatch.setenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", value)
        assert diagnostics_enabled() is False


def test_diagnostic_logging_is_silent_by_default(monkeypatch, caplog):
    """Ohne ERP_OUTLOOK_SYNC_DIAGNOSTICS entsteht keine einzige Zeile im dedizierten
    Diagnose-Logger -- Standardzustand, kein zusätzlicher Protokollierungsaufwand im Normalbetrieb."""
    monkeypatch.delenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", raising=False)
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    _make_event(db, owner)
    server = FakeGraphServer()

    with caplog.at_level(logging.DEBUG, logger="app.outlook_calendar_sync.diagnostics"):
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
            sync_user_calendar(db, owner)

    diag_records = [r for r in caplog.records if r.name == "app.outlook_calendar_sync.diagnostics"]
    assert diag_records == []


def test_diagnostic_log_line_contains_expected_fields_but_never_title_location_or_notes(monkeypatch, caplog):
    """Punkt 4 der Anfrage wörtlich: ERP-ID, updated_at, outlook_synced_at,
    lastModifiedDateTime roh UND umgerechnet, der Versionsstempel gespeichert/eingehend (seit
    1.7.5: @odata.etag statt changeKey, siehe Moduldocstring 'Nachtrag seit 1.7.5'), die
    getroffene Entscheidung -- und (Punkt 6 bleibt unverändert in Kraft) NIEMALS Titel/Ort/Notiz."""
    monkeypatch.setenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", "1")
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    secret_marker = "GEHEIMER TITEL FÜR DIAGNOSE-TEST"
    _make_event(db, owner, title=secret_marker, location="Streng vertraulicher Ort", notes="Geheime Notiz")
    server = FakeGraphServer()

    with caplog.at_level(logging.INFO, logger="app.outlook_calendar_sync.diagnostics"):
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
            sync_user_calendar(db, owner)  # Lauf 1: Push -- erzeugt bereits eine Diagnosezeile
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
            sync_user_calendar(db, owner)  # Lauf 2: etag-Echo -- die eigentlich interessante Zeile

    diag_records = [r for r in caplog.records if r.name == "app.outlook_calendar_sync.diagnostics"]
    assert len(diag_records) >= 2
    full_text = "\n".join(r.getMessage() for r in diag_records)

    # Nie Termininhalt, unabhängig davon, wie sehr sich das Feld verändert hat.
    assert secret_marker not in full_text
    assert "Streng vertraulicher Ort" not in full_text
    assert "Geheime Notiz" not in full_text

    # Die etag-Echo-Zeile (Lauf 2) trägt alle geforderten Felder. FakeGraphServer vergibt bei
    # diesem einzigen Termin/Push seq=1 -> etag='W/"etag-1"' (siehe _advance()).
    echo_line = next(r.getMessage() for r in diag_records if "etag-Echo" in r.getMessage())
    assert "event_id=" in echo_line
    assert "updated_at=" in echo_line
    assert "outlook_synced_at=" in echo_line
    assert "graph_last_modified_raw=" in echo_line and "graph_last_modified_parsed=" in echo_line
    assert 'etag_gespeichert=W/"etag-1"' in echo_line
    assert 'etag_eingehend=W/"etag-1"' in echo_line
    assert "entscheidung=etag-Echo" in echo_line
    # Der frühere, falsche Feldname darf nirgends mehr auftauchen (Regressionsschutz gegen ein
    # Zurückfallen in die 1.7.3/1.7.4-Fassung, siehe Moduldocstring "Nachtrag seit 1.7.5").
    assert "change_key_gespeichert" not in full_text
    assert "change_key_eingehend" not in full_text


def test_diagnostics_do_not_crash_on_removed_delta_entry(monkeypatch):
    """Regressionstest für einen beim Bauen der Diagnosezeile SELBST gefundenen Fallstrick: das
    Lesen von row.updated_at NACH einem db.delete()+db.commit() löst (expire_on_commit) einen
    Reload eines nicht mehr existierenden Datensatzes aus -> ObjectDeletedError. Die Diagnosezeile
    für den @removed-Zweig wird deshalb VOR dem Löschen aus bereits vorher kopierten, reinen
    Python-Werten aufgebaut, nicht durch einen späteren Attributzugriff auf das gelöschte Objekt."""
    monkeypatch.setenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", "1")
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-to-be-removed-diag"
    db.commit()
    event_id = event.id

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(_delta_page([{"id": "graph-to-be-removed-diag", "@removed": {"reason": "deleted"}}],
                                          delta_link="https://graph.microsoft.com/deltaDiagRemoved"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)  # darf NICHT mit ObjectDeletedError abstürzen

    assert result.get("error") is None
    assert result["deleted"] == 1
    assert db.get(CalendarEvent, event_id) is None


# ---------------------------------------------------------------------------
# Router: Rollen-/Modul-Gate
# ---------------------------------------------------------------------------


def test_field_role_is_rejected_on_sync_outlook_endpoint(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, calendar_router, role="field")
    assert client.post("/api/calendar-events/sync-outlook").status_code == 403


def test_office_role_can_call_sync_outlook_and_gets_skipped_without_mailbox(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, calendar_router, role="buero_auftrag")
    resp = client.post("/api/calendar-events/sync-outlook")
    assert resp.status_code == 200
    assert resp.json()["skipped"] is True


def test_only_admin_can_read_or_change_outlook_sync_settings(threaded_db_session, router_test_client):
    for role in ("field", "buero_auftrag", "buero_finanzen"):
        client = router_test_client(threaded_db_session, outlook_settings_router, role=role)
        assert client.get("/api/outlook-sync-settings").status_code == 403
        assert client.put("/api/outlook-sync-settings", json={"enabled": True}).status_code == 403

    admin_client = router_test_client(threaded_db_session, outlook_settings_router, role="admin")
    assert admin_client.get("/api/outlook-sync-settings").status_code == 200
    put_resp = admin_client.put("/api/outlook-sync-settings", json={"enabled": True})
    assert put_resp.status_code == 200
    assert put_resp.json()["enabled"] is True
    assert put_resp.json()["graph_configured"] is False  # noch keine Graph-Zugangsdaten hinterlegt


# ---------------------------------------------------------------------------
# Serientermine (seit 1.7.8) -- Outlook -> ERP, schreibgeschützt, eigene Tabelle
# ---------------------------------------------------------------------------


def _utc_0800(offset_days: int = 0, base: datetime | None = None) -> datetime:
    b = (base or datetime.utcnow()).replace(hour=8, minute=0, second=0, microsecond=0)
    return b + timedelta(days=offset_days)


def _sync_fresh(engine, owner_id: int, server: FakeGraphServer, now_utc: datetime | None = None, urlopen=None) -> dict:
    fresh = sessionmaker(bind=engine)()
    try:
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=urlopen or make_realistic_urlopen(server)):
            return sync_user_calendar(fresh, fresh.get(AppUser, owner_id), now_utc=now_utc)
    finally:
        fresh.close()


def _local_occurrences(engine, owner_id: int) -> list[OutlookSeriesOccurrence]:
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        return s.scalars(select(OutlookSeriesOccurrence).where(OutlookSeriesOccurrence.owner_user_id == owner_id)).all()
    finally:
        s.close()


def _prepare(db):
    owner = _make_user(db)
    _enable_sync(db)
    owner_id = owner.id
    engine = db.get_bind()
    db.close()
    return engine, owner_id


def test_series_window_is_30_days_back_and_12_months_ahead_anchored_at_berlin_midnight():
    start, end = series_window(datetime(2026, 9, 28, 10, 0))
    assert start == datetime(2026, 8, 28, 22, 0)  # 29.08.2026 00:00 Berlin (Sommerzeit)
    assert end == datetime(2027, 9, 27, 22, 0)    # 28.09.2027 00:00 Berlin
    from datetime import date
    assert _add_months(date(2028, 2, 29), 12) == date(2029, 2, 28)
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_series_occurrences_are_never_pushed_over_seven_runs():
    """Pflicht 1: sieben Läufe mit Serie (inkl. verschobener Ausnahme, aus der Serie gelöschtem
    Vorkommen und abgesagter Besprechung) -- kein einziger Schreibzugriff am Server, kein
    Push-Zähler, keine CalendarEvent-Zeile. Zusätzlich: eine lokale Änderung an einem Vorkommen
    (direkt in der Datenbank, einen anderen Weg gibt es nicht) löst ebenfalls keinen Push aus,
    sondern wird beim nächsten Lauf auf den Outlook-Stand zurückgesetzt."""
    engine, owner_id = _prepare(db_session())
    server = FakeGraphServer()
    master = server.add_series("Jour Fixe", _utc_0800(-70), count=70, every_days=7, location="Büro")
    server.move_occurrence(master, _utc_0800(-70) + timedelta(days=77), _utc_0800(-70) + timedelta(days=78))
    server.delete_occurrence(master, _utc_0800(-70) + timedelta(days=84))
    server.cancel_meeting_occurrence(master, _utc_0800(-70) + timedelta(days=91))

    for lauf in range(1, 8):
        if lauf == 4:
            s = sessionmaker(bind=engine)()
            row = s.scalars(select(OutlookSeriesOccurrence)).first()
            row.title = "Lokal verändert"
            s.commit()
            s.close()
        result = _sync_fresh(engine, owner_id, server)
        assert result.get("error") is None
        assert result["series_failed"] == 0
        for key in ("pushed_created", "pushed_updated", "push_failed"):
            assert result[key] == 0, f"Lauf {lauf}: {key}={result[key]}"
        if lauf == 4:
            assert result["series_updated"] == 1  # Outlook gewinnt, lokal zurückgesetzt

    assert server.write_requests == []
    s = sessionmaker(bind=engine)()
    try:
        assert s.scalar(select(CalendarEvent)) is None
    finally:
        s.close()
    assert "Lokal verändert" not in {r.title for r in _local_occurrences(engine, owner_id)}
    assert {r.outlook_event_id for r in _local_occurrences(engine, owner_id)} == server.occurrence_ids_in(*series_window())


def test_calendar_event_api_and_push_cannot_address_a_series_occurrence(threaded_db_session, router_test_client):
    """Pflicht 1, strukturell: PUT/DELETE /api/calendar-events/{id} und push_event_best_effort()
    arbeiten nur auf CalendarEvent -- die ID eines Vorkommens läuft dort ins Leere, und für
    /api/calendar-series-occurrences existiert überhaupt nur GET."""
    db = threaded_db_session
    owner = _make_user(db)
    _enable_sync(db)
    occ = OutlookSeriesOccurrence(owner_user_id=owner.id, outlook_event_id="series-1-occ-x", series_master_id="series-1",
                                  occurrence_type="occurrence", title="Jour Fixe",
                                  start_at=datetime(2026, 10, 1, 10), end_at=datetime(2026, 10, 1, 11))
    db.add(occ)
    db.commit()
    client = router_test_client(db, calendar_router, role="admin")
    assert client.put(f"/api/calendar-events/{occ.id}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/calendar-events/{occ.id}").status_code == 404
    methods = {m for r in calendar_router.routes if r.path.startswith("/api/calendar-series-occurrences") for m in r.methods}
    assert methods == {"GET"}
    with patch("app.outlook_calendar_sync.urllib.request.urlopen") as mocked:
        push_event_best_effort(db, occ.id)
        mocked.assert_not_called()
    db.refresh(occ)
    assert occ.title == "Jour Fixe"


def test_no_oscillation_with_series_all_counters_reach_zero_from_the_second_run():
    """Pflicht 2: der Schaukel-Test aus 1.7.6, zusätzlich mit einer Serie im Postfach."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    server = FakeGraphServer()
    master = server.add_series("Jour Fixe", _utc_0800(-40), count=80, every_days=7)
    server.move_occurrence(master, _utc_0800(-40) + timedelta(days=49), _utc_0800(-40) + timedelta(days=50))
    _check_no_oscillation(db, owner, server)


@requires_postgres_opt_in
def test_no_oscillation_with_series_all_counters_reach_zero_from_the_second_run_postgresql():
    db, engine = pg_db_session()
    try:
        _cleanup_pg_test_data(db, "pgtest_schaukel_serie")
        owner = _make_user(db, username="pgtest_schaukel_serie", mailbox="pgtest_schaukel_serie@dachkonzepte.gmbh")
        _enable_sync(db)
        server = FakeGraphServer()
        server.add_series("Jour Fixe", _utc_0800(-40), count=80, every_days=7)
        _check_no_oscillation(db, owner, server)
    finally:
        _cleanup_pg_test_data(db, "pgtest_schaukel_serie")
        db.close()
        engine.dispose()


def test_moving_window_neither_duplicates_nor_loses_occurrences():
    """Pflicht 3: das Fenster wandert mit der Zeit. Tägliche Serie, deutlich länger als das
    Fenster; Lauf bei t0, dann bei t0+45 Tagen. Die lokale Menge muss jeweils EXAKT der
    unabhängig berechneten Erwartung des Servers entsprechen -- vorn herausgefallene Vorkommen
    entfernt, hinten neu hereingekommene angelegt, keine Dublette (auch über Seitengrenzen,
    $top=100, hinweg)."""
    engine, owner_id = _prepare(db_session())
    t0 = datetime.utcnow()
    server = FakeGraphServer()
    server.add_series("Täglicher Check", _utc_0800(-100, t0), count=700, every_days=1)

    first = _sync_fresh(engine, owner_id, server, now_utc=t0)
    expected_0 = server.occurrence_ids_in(*series_window(t0))
    ids_0 = [r.outlook_event_id for r in _local_occurrences(engine, owner_id)]
    assert first["series_created"] == len(expected_0) > 300
    assert len(ids_0) == len(set(ids_0)) and set(ids_0) == expected_0
    assert any("skip=" in r["url"] for r in server.calendar_view_requests)  # Paging wurde tatsächlich gebraucht

    t1 = t0 + timedelta(days=45)
    moved = _sync_fresh(engine, owner_id, server, now_utc=t1)
    expected_1 = server.occurrence_ids_in(*series_window(t1))
    ids_1 = [r.outlook_event_id for r in _local_occurrences(engine, owner_id)]
    assert len(ids_1) == len(set(ids_1)) and set(ids_1) == expected_1
    assert moved["series_deleted"] == len(expected_0 - expected_1) > 0
    assert moved["series_created"] == len(expected_1 - expected_0) > 0
    assert moved["series_updated"] == 0

    again = _sync_fresh(engine, owner_id, server, now_utc=t1)
    for key in ("series_created", "series_updated", "series_deleted", "series_failed"):
        assert again[key] == 0


def test_exceptions_moves_and_cancellations_are_reflected():
    engine, owner_id = _prepare(db_session())
    server = FakeGraphServer()
    first = _utc_0800(-14)
    master = server.add_series("Jour Fixe", first, count=10, every_days=7)
    moved_from, moved_to = first + timedelta(days=21), first + timedelta(days=22, hours=2)
    server.move_occurrence(master, moved_from, moved_to)
    server.delete_occurrence(master, first + timedelta(days=28))
    server.cancel_meeting_occurrence(master, first + timedelta(days=35))
    _sync_fresh(engine, owner_id, server)

    rows = {r.outlook_event_id: r for r in _local_occurrences(engine, owner_id)}
    assert len(rows) == 8
    exception_row = rows[f"{master}-occ-{moved_from:%Y%m%d%H%M}"]
    assert exception_row.occurrence_type == "exception"
    assert exception_row.start_at == to_berlin(moved_to)
    assert f"{master}-occ-{first + timedelta(days=28):%Y%m%d%H%M}" not in rows
    assert f"{master}-occ-{first + timedelta(days=35):%Y%m%d%H%M}" not in rows

    # Später in Outlook: ein weiteres Vorkommen gelöscht, ein anderes verschoben.
    server.delete_occurrence(master, first + timedelta(days=42))
    server.move_occurrence(master, first + timedelta(days=49), first + timedelta(days=49, hours=3))
    result = _sync_fresh(engine, owner_id, server)
    assert result["series_deleted"] == 1
    assert result["series_updated"] == 1
    assert result["series_created"] == 0


def test_series_edit_in_outlook_updates_every_local_occurrence():
    engine, owner_id = _prepare(db_session())
    server = FakeGraphServer()
    master = server.add_series("Jour Fixe", _utc_0800(-7), count=5, every_days=7)
    _sync_fresh(engine, owner_id, server)
    server.edit_series(master, subject="Jour Fixe (neu)")
    result = _sync_fresh(engine, owner_id, server)
    assert result["series_updated"] == 5
    assert {r.title for r in _local_occurrences(engine, owner_id)} == {"Jour Fixe (neu)"}


def test_series_fetch_failure_changes_nothing_locally():
    """Ein Fehler auf Seite 2 des calendarView-Abrufs: nichts wird lokal angelegt, geändert oder
    entfernt (der Abgleich schreibt erst nach dem vollständigen Abruf), der Einzeltermin-Sync
    davor bleibt unberührt."""
    engine, owner_id = _prepare(db_session())
    server = FakeGraphServer()
    master = server.add_series("Täglich", _utc_0800(-10), count=200, every_days=1)
    _sync_fresh(engine, owner_id, server)
    before = {r.outlook_event_id for r in _local_occurrences(engine, owner_id)}
    server.delete_occurrence(master, _utc_0800(-10) + timedelta(days=12))

    realistic = make_realistic_urlopen(server)

    def failing_page_two(req, timeout=None):
        if "/calendarView" in req.full_url and "skip=" in req.full_url:
            raise _http_error(503, "vorübergehend")
        return realistic(req, timeout)

    result = _sync_fresh(engine, owner_id, server, urlopen=failing_page_two)
    assert result.get("error") is None
    assert result["series_failed"] == 1
    assert result["series_created"] == result["series_updated"] == result["series_deleted"] == 0
    assert {r.outlook_event_id for r in _local_occurrences(engine, owner_id)} == before


def test_series_request_asks_for_text_body_and_selects_series_fields():
    engine, owner_id = _prepare(db_session())
    server = FakeGraphServer()
    server.add_series("Jour Fixe", _utc_0800(-7), count=3, every_days=7, body="Agenda")
    _sync_fresh(engine, owner_id, server)
    req = server.calendar_view_requests[0]
    assert req["prefer"] == 'outlook.body-content-type="text"'
    assert "seriesMasterId" in req["url"] and "isCancelled" in req["url"]
    assert {r.notes for r in _local_occurrences(engine, owner_id)} == {"Agenda"}


def test_delta_path_rejects_occurrences_and_removes_a_single_event_that_became_a_series():
    """Jede Outlook-ID gehört genau einem Weg: ein Vorkommen/eine Ausnahme im Delta wird nie als
    CalendarEvent angelegt; wird ein bekannter Einzeltermin in Outlook zur Serie, verschwindet
    die lokale Kopie, statt dass eine spätere ERP-Bearbeitung die ganze Serie per PATCH ändert."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    converted = _make_event(db, owner, title="Wird zur Serie")
    converted.outlook_event_id = "graph-converted"
    db.commit()
    converted_id = converted.id
    delta_items = [
        {"id": "graph-converted", "type": "seriesMaster", "recurrence": {"pattern": {"type": "weekly"}},
         "start": {"dateTime": "2026-10-01T08:00:00.0000000"}, "end": {"dateTime": "2026-10-01T09:00:00.0000000"}},
        {"id": "graph-occ-1", "type": "occurrence", "seriesMasterId": "graph-converted",
         "start": {"dateTime": "2026-10-08T08:00:00.0000000"}, "end": {"dateTime": "2026-10-08T09:00:00.0000000"}},
        {"id": "graph-exc-1", "type": "exception", "seriesMasterId": "graph-converted",
         "start": {"dateTime": "2026-10-15T09:00:00.0000000"}, "end": {"dateTime": "2026-10-15T10:00:00.0000000"}},
    ]
    writes = []

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        if req.get_method() != "GET":
            writes.append(req.get_method())
        if "/calendarView" in req.full_url:
            return _FakeResponse({"value": []})
        return _FakeResponse(_delta_page(delta_items, delta_link="https://graph.microsoft.com/deltaSeries"))

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        result = sync_user_calendar(db, owner)

    assert result["deleted"] == 1
    assert result["skipped_recurring"] == 2
    assert result["created"] == 0
    assert writes == []
    assert db.get(CalendarEvent, converted_id) is None
    assert db.scalar(select(CalendarEvent)) is None


def test_private_series_occurrence_is_busy_for_colleagues_and_full_for_owner():
    db = db_session()
    owner = _make_user(db)
    colleague = _make_user(db, username="kollege", mailbox="kollege@dachkonzepte.gmbh")
    _enable_sync(db)
    server = FakeGraphServer()
    server.add_series("Arzttermin", _utc_0800(-7), count=3, every_days=7, sensitivity="private", location="Praxis")
    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
        sync_user_calendar(db, owner)

    rows = list_series_occurrences(db)
    assert len(rows) == 3 and all(r["is_private"] for r in rows)
    assert not is_redacted_for_viewer(rows[0], owner.id)
    assert is_redacted_for_viewer(rows[0], colleague.id)
    busy = redact_for_busy(rows[0])
    assert busy["title"] == "Belegt" and "location" not in busy and "notes" not in busy


def test_series_endpoint_redacts_private_occurrences_and_is_role_and_module_gated(threaded_db_session, router_test_client):
    db = threaded_db_session
    owner = _make_user(db)
    for idx, private in enumerate((True, False)):
        db.add(OutlookSeriesOccurrence(owner_user_id=owner.id, outlook_event_id=f"occ-{idx}", series_master_id="m",
                                       occurrence_type="occurrence", title="Geheim" if private else "Offen",
                                       location="Ort", notes="Notiz", is_private=private,
                                       start_at=datetime(2026, 10, 1 + idx, 10), end_at=datetime(2026, 10, 1 + idx, 11)))
    db.commit()

    assert router_test_client(db, calendar_router, role="field").get("/api/calendar-series-occurrences").status_code == 403

    client = router_test_client(db, calendar_router, role="buero_auftrag")  # nicht der Besitzer
    data = client.get("/api/calendar-series-occurrences?start=2026-09-30T00:00:00&end=2026-10-05T00:00:00").json()
    by_title = {row["title"]: row for row in data}
    assert set(by_title) == {"Belegt", "Offen"}
    assert "location" not in by_title["Belegt"] and "notes" not in by_title["Belegt"]
    assert all(row["series"] is True for row in data)

    from app.modules import set_module_enabled
    set_module_enabled(db, "kalender", False)
    assert client.get("/api/calendar-series-occurrences").status_code == 403


def test_series_diagnostic_lines_cover_decisions_but_never_content(monkeypatch, caplog):
    """Pflicht 5: jede Serienentscheidung (neu, unverändert, aktualisiert, entfernt) erscheint
    als Diagnosezeile -- nie Titel/Ort/Notiz (Punkt 6)."""
    monkeypatch.setenv("ERP_OUTLOOK_SYNC_DIAGNOSTICS", "1")
    engine, owner_id = _prepare(db_session())
    server = FakeGraphServer()
    first = _utc_0800(-7)
    master = server.add_series("GEHEIMER-TITEL-XY", first, count=4, every_days=7,
                               location="GEHEIMER-ORT-XY", body="GEHEIME-NOTIZ-XY")
    caplog.set_level(logging.INFO, logger="app.outlook_calendar_sync.diagnostics")
    _sync_fresh(engine, owner_id, server)
    _sync_fresh(engine, owner_id, server)
    server.move_occurrence(master, first + timedelta(days=7), first + timedelta(days=8))
    server.delete_occurrence(master, first + timedelta(days=14))
    server.cancel_meeting_occurrence(master, first + timedelta(days=21))
    _sync_fresh(engine, owner_id, server)

    series_lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("serie ")]
    for entscheidung in ("neu übernommen", "unverändert", "aktualisiert (in Outlook geändert)",
                         "abgesagt (isCancelled) -> nicht geführt",
                         "nicht mehr im Fenster oder in Outlook entfernt/abgesagt -> entfernt"):
        assert any(f"entscheidung={entscheidung}" in line for line in series_lines), entscheidung
    all_text = " ".join(r.getMessage() for r in caplog.records)
    for secret in ("GEHEIMER-TITEL-XY", "GEHEIMER-ORT-XY", "GEHEIME-NOTIZ-XY"):
        assert secret not in all_text
