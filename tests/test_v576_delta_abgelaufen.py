"""Version 1.9.158 (Stufe 6, R2, Punkt 2): ein abgelaufener Delta-Link setzt den Abgleich zurück, ohne Doppelte.

    Auslöser    410, oder ein 40X mit syncStateNotFound (auch als innerError); nichts anderes (403, 404 ohne den Code, 500)
    Ablauf      im selben Lauf von vorn: neuer Link, kein Fehler am Postfach, Senden geht weiter
    ohne Doppelte  jede Zeile findet ihren Termin über die Kennung wieder, Projektbezug bleibt
    in der Lücke  neu, geändert, gelöscht: alle drei kommen an; gelöscht nur nach 404 auf die einzelne Nachfrage
    danach      Ruhe; läuft auch der neue Abruf ab, bleibt es ein Fehler dieses Laufs und der nächste geht
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.models import CalendarEvent, OutlookCalendarSyncState
from app.outlook_calendar_sync import get_or_create_sync_state, sync_user_calendar
from tests.bestand_alt import auftrag
from tests.outlook_attrappe import Microsoft
from tests.test_v297_outlook_calendar_sync import PG_TEST_DATABASE_URL, _enable_sync, _make_event, _make_user, db_session, pg_aufraeumen, pg_db_session

URLOPEN = "app.outlook_calendar_sync.urllib.request.urlopen"
ANNA = "anna@dachkonzepte.gmbh"
RUHE = ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed", "delta_reset")


def _welt(db=None):
    db = db or db_session()
    _enable_sync(db)
    konto = _make_user(db, username="anna", mailbox=ANNA)
    ms = Microsoft()
    ms.postfach(ANNA)
    return db, konto, ms


def _lauf(db, konto, ms):
    with patch(URLOPEN, side_effect=ms.urlopen):
        return sync_user_calendar(db, konto)


def _beginn(tag=10):
    return datetime(2026, 11, tag, 9, 0)


def _anzahl(db, kennung=None):
    abfrage = select(func.count()).select_from(CalendarEvent)
    return db.scalar(abfrage.where(CalendarEvent.outlook_event_id == kennung) if kennung else abfrage)


@pytest.mark.parametrize("status, code, inner", [
    (410, "syncStateNotFound", None),
    (410, "somethingElse", None),  # 410 reicht, „Synchronization reset“
    (400, "syncStateNotFound", None),  # „a 40X-series error with error codes such as syncStateNotFound“
    (404, "syncStateNotFound", None),
    (400, "BadRequest", "syncStateInvalid"),  # der genaue Code steckt im innerError
    (400, "resyncRequired", None),
])
def test_abgelaufener_link_setzt_sich_im_selben_lauf_zurueck(status, code, inner):
    db, konto, ms = _welt()
    _lauf(db, konto, ms)
    alt = get_or_create_sync_state(db, ANNA).delta_link
    ms.ablaufen(ANNA, status, code, inner)

    ergebnis = _lauf(db, konto, ms)

    assert not ergebnis.get("error"), ergebnis
    assert ergebnis["delta_reset"] == 1
    stand = get_or_create_sync_state(db, ANNA)
    assert stand.delta_link and "$deltatoken" in stand.delta_link
    assert stand.last_error_type is None and stand.last_error_at is None
    assert alt  # es gab einen Link, der ablief
    aufrufe = [u for m, u in ms.anfragen if m == "GET" and "/delta" in u]
    assert "$deltatoken" in aufrufe[-2] and "$deltatoken" not in aufrufe[-1]  # erst der alte Link, dann von vorn


@pytest.mark.parametrize("status, code", [(403, "ErrorAccessDenied"), (404, "ErrorInvalidUser"), (500, "InternalServerError"), (401, "InvalidAuthenticationToken"), (429, "TooManyRequests")])
def test_andere_fehler_setzen_nichts_zurueck(status, code):
    db, konto, ms = _welt()
    _lauf(db, konto, ms)
    alt = get_or_create_sync_state(db, ANNA).delta_link
    ms.ablaufen(ANNA, status, code)

    ergebnis = _lauf(db, konto, ms)

    assert ergebnis["error"] is True and ergebnis["delta_reset"] == 0
    stand = get_or_create_sync_state(db, ANNA)
    assert stand.delta_link == alt
    assert stand.last_error_type == "OutlookSyncError"


def test_keine_doppelten_und_der_projektbezug_bleibt():
    db, konto, ms = _welt()
    outlook = ms.postfach(ANNA).anlegen("Aus Outlook", _beginn(), _beginn() + timedelta(hours=1))
    erp = _make_event(db, konto, title="Aus dem ERP", start_at=_beginn(11), end_at=_beginn(11) + timedelta(hours=1))
    _lauf(db, konto, ms)
    db.refresh(erp)
    assert _anzahl(db) == 2 and erp.outlook_event_id

    projekt = auftrag(db, number="1").project_id
    zeile = db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == outlook))
    zeile.project_id = projekt
    db.commit()
    _lauf(db, konto, ms)  # das ERP hat gewonnen, Outlook ist auf dem Stand

    ms.ablaufen(ANNA)
    ergebnis = _lauf(db, konto, ms)

    assert ergebnis["delta_reset"] == 1
    assert _anzahl(db) == 2
    assert _anzahl(db, outlook) == 1 and _anzahl(db, erp.outlook_event_id) == 1
    db.refresh(zeile)
    assert zeile.project_id == projekt
    assert len(ms.postfach(ANNA).events) == 2  # auch in Outlook keiner doppelt
    assert ms.schreibend("POST")[1:] == []  # nur der eine Termin aus dem ERP wurde je angelegt


def test_was_in_der_luecke_geschah_kommt_an():
    db, konto, ms = _welt()
    postfach = ms.postfach(ANNA)
    bleibt = postfach.anlegen("Bleibt", _beginn(), _beginn() + timedelta(hours=1))
    weg = postfach.anlegen("Wird gelöscht", _beginn(12), _beginn(12) + timedelta(hours=1))
    anders = postfach.anlegen("Alter Titel", _beginn(13), _beginn(13) + timedelta(hours=1))
    _lauf(db, konto, ms)
    assert _anzahl(db) == 3

    ms.ablaufen(ANNA)
    postfach.loeschen(weg)
    postfach.geloescht.clear()  # abgelaufen: ein @removed kommt für diesen Termin nie mehr
    postfach.aendern(anders, subject="Neuer Titel")
    neu = postfach.anlegen("Neu in der Lücke", _beginn(14), _beginn(14) + timedelta(hours=1))

    ergebnis = _lauf(db, konto, ms)

    assert (ergebnis["created"], ergebnis["updated"], ergebnis["deleted"]) == (1, 1, 1), ergebnis
    assert {z.outlook_event_id for z in db.scalars(select(CalendarEvent))} == {bleibt, anders, neu}
    assert db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == anders)).title == "Neuer Titel"


def test_was_nur_im_abruf_fehlt_bleibt():
    """Der Abruf allein beweist nichts: Graph kennt den Termin noch, also bleibt er."""
    db, konto, ms = _welt()
    postfach = ms.postfach(ANNA)
    kennung = postfach.anlegen("Fehlt nur im Abruf", _beginn(), _beginn() + timedelta(hours=1))
    _lauf(db, konto, ms)
    ms.ablaufen(ANNA)
    original = postfach.delta
    postfach.delta = lambda seit: ([z for z in original(seit)[0] if z["id"] != kennung], original(seit)[1])

    ergebnis = _lauf(db, konto, ms)

    assert ergebnis["deleted"] == 0
    assert _anzahl(db, kennung) == 1


def test_nachfrage_mit_fehler_loescht_nicht():
    db, konto, ms = _welt()
    postfach = ms.postfach(ANNA)
    kennung = postfach.anlegen("Unklar", _beginn(), _beginn() + timedelta(hours=1))
    _lauf(db, konto, ms)
    ms.ablaufen(ANNA)
    original = postfach.delta
    postfach.delta = lambda seit: ([z for z in original(seit)[0] if z["id"] != kennung], original(seit)[1])
    from tests.outlook_attrappe import http_fehler

    def nachfrage_scheitert(methode, adresse, weg):
        if methode == "GET" and len(weg) == 2 and weg[1] == kennung:
            raise http_fehler(503, "ServiceUnavailable")

    ms.vor_antwort = nachfrage_scheitert
    ergebnis = _lauf(db, konto, ms)

    assert ergebnis["deleted"] == 0 and not ergebnis.get("error")
    assert _anzahl(db, kennung) == 1


def test_das_senden_geht_im_selben_lauf_weiter():
    db, konto, ms = _welt()
    _lauf(db, konto, ms)
    ms.ablaufen(ANNA)
    with patch(URLOPEN, side_effect=ms.urlopen):
        termin = _make_event(db, konto, title="Wartet", start_at=_beginn(), end_at=_beginn() + timedelta(hours=1))
        ergebnis = sync_user_calendar(db, konto)
    db.refresh(termin)
    assert ergebnis["pushed_created"] == 1 and termin.outlook_event_id


def test_danach_ist_ruhe():
    db, konto, ms = _welt()
    ms.postfach(ANNA).anlegen("Termin", _beginn(), _beginn() + timedelta(hours=1))
    _make_event(db, konto, title="Aus dem ERP", start_at=_beginn(11), end_at=_beginn(11) + timedelta(hours=1))
    _lauf(db, konto, ms)
    _lauf(db, konto, ms)
    ms.ablaufen(ANNA)
    assert _lauf(db, konto, ms)["delta_reset"] == 1
    for _ in range(5):
        ergebnis = _lauf(db, konto, ms)
        assert {k: ergebnis[k] for k in RUHE} == dict.fromkeys(RUHE, 0), ergebnis
    assert _anzahl(db) == 2


def test_laeuft_auch_der_neue_abruf_ab_bleibt_es_ein_fehler_und_der_naechste_lauf_geht():
    db, konto, ms = _welt()
    _lauf(db, konto, ms)
    ms.ablaufen(ANNA, wie_oft=2)

    ergebnis = _lauf(db, konto, ms)

    assert ergebnis["error"] is True and ergebnis["delta_reset"] == 1
    stand = get_or_create_sync_state(db, ANNA)
    assert stand.delta_link is None and stand.last_error_type == "OutlookSyncError"

    ergebnis = _lauf(db, konto, ms)

    assert not ergebnis.get("error")
    stand = get_or_create_sync_state(db, ANNA)
    assert stand.delta_link and stand.last_error_type is None


def test_ein_erster_abruf_ohne_link_gilt_als_ganzer_kalender():
    """Auch ohne Ablauf: ein Konto ohne Link (nach einem Fehler, ein Postfach kommt zurück) findet heraus, was in der Zwischenzeit gelöscht wurde."""
    db, konto, ms = _welt()
    postfach = ms.postfach(ANNA)
    weg = postfach.anlegen("Weg", _beginn(), _beginn() + timedelta(hours=1))
    _lauf(db, konto, ms)
    get_or_create_sync_state(db, ANNA).delta_link = None
    db.commit()
    postfach.loeschen(weg)

    ergebnis = _lauf(db, konto, ms)

    assert ergebnis["deleted"] == 1 and _anzahl(db) == 0


def test_kein_inhalt_im_protokoll(caplog):
    db, konto, ms = _welt()
    _lauf(db, konto, ms)
    ms.ablaufen(ANNA)
    with caplog.at_level("INFO"):
        _lauf(db, konto, ms)
    assert "Delta-Link abgelaufen" in caplog.text
    assert "im Klartext" not in caplog.text and "deltatoken" not in caplog.text


@pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
def test_rueckstellung_unter_postgresql():
    db, engine = pg_db_session()
    try:
        db, konto, ms = _welt(db)
        ms.postfach(ANNA).anlegen("Termin", _beginn(), _beginn() + timedelta(hours=1))
        _lauf(db, konto, ms)
        ms.ablaufen(ANNA)
        ergebnis = _lauf(db, konto, ms)
        assert ergebnis["delta_reset"] == 1 and not ergebnis.get("error")
        assert _anzahl(db) == 1
        assert db.scalar(select(func.count()).select_from(OutlookCalendarSyncState).where(OutlookCalendarSyncState.delta_link.is_not(None))) == 1
    finally:
        db.close()
        pg_aufraeumen(engine)
