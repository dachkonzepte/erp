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
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.calendar_events import (
    create_event, is_redacted_for_viewer, list_events, redact_for_busy,
)
from app.database import Base
from app.email_sending import update_graph_settings
from app.models import AppUser, CalendarEvent, Customer, Project
from app.outlook_calendar_sync import (
    _mark_synced, _needs_push, get_or_create_sync_state, is_outlook_sync_available,
    push_event_best_effort, to_berlin, to_utc, try_delete_remote_event,
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
# vergibt einen NEUEN lastModifiedDateTime UND einen NEUEN changeKey (wie Microsoft Graph es
# tatsächlich tut, changeKey ist Graphs ETag-Äquivalent), delta() liefert alles zurück, was sich
# seit dem zuletzt zurückgegebenen Cursor geändert hat -- ausdrücklich AUCH die eigenen Echos.
# ---------------------------------------------------------------------------


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

    def _advance(self) -> tuple[str, str]:
        self._seq += 1
        self._clock += timedelta(seconds=1)
        return self._clock.isoformat() + "Z", f"ckey-{self._seq}"

    def create(self, payload: dict) -> dict:
        new_id = f"graph-{self._next_id}"
        self._next_id += 1
        last_modified, change_key = self._advance()
        self.events[new_id] = {
            "id": new_id, **_fields_from_payload(payload),
            "lastModifiedDateTime": last_modified, "changeKey": change_key, "_seq": self._seq,
        }
        return dict(self.events[new_id])

    def patch(self, event_id: str, payload: dict) -> dict:
        last_modified, change_key = self._advance()
        row = self.events[event_id]
        row.update({**_fields_from_payload(payload), "lastModifiedDateTime": last_modified,
                    "changeKey": change_key, "_seq": self._seq})
        return dict(row)

    def delta(self, since_seq: int) -> tuple[list[dict], int]:
        items = [{k: v for k, v in ev.items() if k != "_seq"} for ev in self.events.values() if ev["_seq"] > since_seq]
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
        if method == "POST" and "/delta" not in url:
            return _FakeResponse(server.create(json.loads(req.data)))
        if method == "PATCH":
            event_id = url.rsplit("/", 1)[-1]
            return _FakeResponse(server.patch(event_id, json.loads(req.data)))
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


def test_push_create_stores_change_key_from_graph_response():
    """Nachtrag (seit 1.7.3) -- der changeKey aus der Graph-Antwort wird zusammen mit
    outlook_event_id gespeichert, damit ein späterer Echo-Pull ihn exakt wiedererkennen kann."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse({"id": "graph-ck-1", "changeKey": "ckey-erster-push"})

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    db.refresh(event)
    assert event.outlook_change_key == "ckey-erster-push"


def test_push_patch_stores_change_key_from_graph_response_when_present():
    """Wie oben, aber für den Update-Weg (PATCH) -- Graph liefert bei einem erfolgreichen PATCH
    normalerweise die aktualisierte Ressource inkl. neuem changeKey zurück."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-existing-ck"
    event.outlook_change_key = "ckey-alt"
    db.commit()

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse({"id": "graph-existing-ck", "changeKey": "ckey-neu-nach-patch"})

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)

    db.refresh(event)
    assert event.outlook_change_key == "ckey-neu-nach-patch"


def test_push_patch_without_response_body_does_not_crash_and_leaves_change_key_unset():
    """Randfall, bewusst offen gehalten (siehe Moduldocstring 'Nachtrag Schaukelnder Termin'):
    liefert Graph auf ein PATCH keinen Body (204-artig, wie im bestehenden
    test_push_updates_existing_event_via_patch simuliert), bleibt outlook_change_key auf dem
    alten Stand stehen -- kein Absturz, die Zeitstempel-Logik greift beim nächsten Pull als
    Rückfall."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    event.outlook_event_id = "graph-no-body"
    event.outlook_change_key = "ckey-bleibt-stehen"
    db.commit()

    def fake(req, timeout=None):
        if TOKEN_URL_MARKER in req.full_url:
            return _FakeResponse({"access_token": "faketoken"})
        return _FakeResponse(None)

    with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=fake):
        push_event_best_effort(db, event.id)  # darf nicht werfen

    db.refresh(event)
    assert event.outlook_change_key == "ckey-bleibt-stehen"


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
    """Nachtrag (seit 1.7.2) -- _mark_synced() muss updated_at UND outlook_synced_at auf
    DENSELBEN Wert setzen. Täte sie das nicht, würde SQLAlchemys onupdate=datetime.utcnow
    updated_at bei dieser reinen Buchhaltungsschreiboperation unbeabsichtigt weiterschieben und
    der Termin sähe sofort wieder wie "noch zu übertragen" aus -- eine Endlosschleife aus
    unnötigen Pushes bei jedem weiteren Sync-Lauf, obwohl sich am Termin nichts geändert hat."""
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
    # Nachtrag (seit 1.7.2) -- _mark_synced() hält beide Zeitstempel synchron, kein Push nötig.
    assert event.outlook_synced_at == event.updated_at
    assert _needs_push(event) is False


def test_delta_item_with_a_changekey_we_already_know_is_recognized_as_our_own_echo_and_skipped():
    """Nachtrag 'Schaukelnder Termin' (seit 1.7.3), Punkt 2 der Anfrage -- der eigentliche,
    uhrzeitUNABHÄNGIGE Echo-Test: der Delta-Eintrag trägt bewusst einen lastModifiedDateTime, der
    NACH existing.updated_at liegt (genau der Fall, der die reine Zeitstempel-Heuristik allein
    zum Absorbieren bewegen würde -- siehe test_incoming_newer_change_updates_fields_but_never_
    touches_project_link oben). Trägt der Eintrag aber EXAKT den changeKey, den wir selbst
    zuletzt gespeichert haben (aus einem eigenen Push oder einer bereits absorbierten Änderung),
    wird er als eigenes Echo erkannt und komplett übersprungen -- kein Feld wird angefasst, kein
    _mark_synced()-Aufruf, updated_at/outlook_synced_at bleiben unverändert."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner, title="Unverändert", location="Ursprünglicher Ort")
    event.outlook_event_id = "graph-echo-1"
    event.outlook_change_key = "ckey-bereits-bekannt"
    original_updated_at = datetime.utcnow()
    event.updated_at = original_updated_at
    event.outlook_synced_at = original_updated_at
    db.commit()

    item = {
        "id": "graph-echo-1", "changeKey": "ckey-bereits-bekannt", "subject": "GEÄNDERT?!",
        "isAllDay": False,
        "start": {"dateTime": "2026-06-01T08:00:00Z"}, "end": {"dateTime": "2026-06-01T09:00:00Z"},
        "location": {"displayName": "Anderer Ort"}, "body": {"content": ""},
        # Bewusst NEUER als existing.updated_at -- ohne die changeKey-Prüfung würde bereits die
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


def test_no_oscillation_all_counters_reach_zero_from_the_second_run_and_stay_zero_for_five_more_runs():
    """Nachtrag 'Schaukelnder Termin' (seit 1.7.3), Punkt 4 der Anfrage -- der eigentliche
    Regressionstest für das gemeldete Verhalten ('Lauf 1: 1 geändert/0 gepusht, Lauf 2: 0
    geändert/1 gepusht, und so weiter im Wechsel'). Läuft gegen FakeGraphServer (echter Zustand,
    siehe Modulkommentar oben) -- KEINE der bisherigen, handgebauten Antworten in dieser Datei
    bildete den entscheidenden Rundlauf ab (eigener Push kommt beim nächsten Delta-Abruf als
    scheinbar fremde Änderung zurück), weshalb die bisherigen Tests den Fehler nicht gefunden
    hätten. Ohne dass irgendjemand den Termin anfasst, muss ab dem ZWEITEN Lauf (der die
    anfängliche Push-Bestätigung verarbeitet) für JEDEN weiteren Lauf gelten:
    created=updated=deleted=pushed_created=pushed_updated=0 -- über mindestens fünf weitere
    Läufe hinweg, nicht nur einmalig."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    event = _make_event(db, owner)
    server = FakeGraphServer()

    def run():
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
            return sync_user_calendar(db, owner)

    first = run()
    assert first.get("error") is None
    assert first["created"] == 0
    assert first["updated"] == 0
    assert first["pushed_created"] == 1  # der einzige Lauf, der überhaupt etwas zu tun hat
    assert first["pushed_updated"] == 0

    for lauf in range(2, 8):  # fünf weitere Läufe (2 bis 7 inklusive) -- wie ausdrücklich verlangt
        result = run()
        assert result.get("error") is None, f"Lauf {lauf}: error={result.get('error_type')}"
        for key in ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed"):
            assert result[key] == 0, f"Lauf {lauf}: {key}={result[key]} (erwartet 0)"

    db.refresh(event)
    assert event.outlook_event_id is not None
    assert event.outlook_change_key is not None
    assert event.updated_at == event.outlook_synced_at


def test_no_oscillation_holds_even_with_a_genuine_later_edit_from_outlook_in_between():
    """Ergänzung zum Test oben -- prüft, dass die changeKey-Absicherung eine ECHTE, spätere
    Änderung durch jemand anderen (direkt in Outlook) nicht verschluckt: die muss weiterhin ganz
    normal als 'updated' absorbiert werden, und DANACH muss wieder Ruhe einkehren, unabhängig vom
    neu gesetzten changeKey."""
    db = db_session()
    owner = _make_user(db)
    _enable_sync(db)
    _make_event(db, owner)
    server = FakeGraphServer()

    def run():
        with patch("app.outlook_calendar_sync.urllib.request.urlopen", side_effect=make_realistic_urlopen(server)):
            return sync_user_calendar(db, owner)

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
    row = db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == graph_id))
    assert row.title == "Von einem Kollegen direkt in Outlook geändert"
    assert row.location == "Neuer Ort aus Outlook"

    for lauf in range(1, 4):
        result = run()
        for key in ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed"):
            assert result[key] == 0, f"Lauf nach der echten Änderung, +{lauf}: {key}={result[key]}"


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
