"""Version 1.9.162 (Stufe 6, R2, Punkt 6): Einstellungen, je Postfach letzter Lauf, letzter Fehler, wartet auf Senden; für den Admin.

    Stand     Konto und Gerät mit Name, Lauf, Fehler als Satz, Zahl wartend, auch inaktive; „wartet“ deckt sich mit _needs_push()
    Fehler    aus Art und Status: 403 Gruppe, 401 Anmeldung, 404 Adresse; der Text von Microsoft erscheint nie (Regel 18)
    Rechte    nur Admin, Büro und Monteurin 403
    Seite     zeigt es, ordnet zu, entfernt
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import CalendarEvent, OperationalResource, OutlookCalendarSyncState, OutlookDeleteOrder
from app.outlook_calendar_sync import SPERRE_GILT, _needs_push, fehler_text, get_or_create_sync_state, postfach_uebersicht, sync_user_calendar
from app.routers.outlook_sync_settings import router as settings_router
from tests.outlook_attrappe import Microsoft
from tests.test_v297_outlook_calendar_sync import _enable_sync, _make_event, _make_user, db_session
from tests.vorlagen_js import bindet_ein

ROOT = Path(__file__).resolve().parent.parent
URLOPEN = "app.outlook_calendar_sync.urllib.request.urlopen"
ANNA, KRAN = "anna@x.de", "kran@x.de"
BEGINN = datetime(2026, 11, 10, 9)


def _kran(db, postfach=KRAN, aktiv=True, name="Kran 30 m"):
    zeile = OperationalResource(resource_type="Maschine", name=name, outlook_mailbox=postfach, active=aktiv)
    db.add(zeile)
    db.commit()
    return zeile


def _zeile(db, adresse):
    return next(z for z in postfach_uebersicht(db) if z["adresse"] == adresse)


def test_konto_und_geraet_stehen_darin():
    db = db_session()
    anna = _make_user(db, username="anna", mailbox=ANNA)
    kran = _kran(db)
    stand = get_or_create_sync_state(db, ANNA)
    stand.last_synced_at = datetime(2026, 10, 30, 12)
    db.commit()
    zeilen = postfach_uebersicht(db)
    assert [(z["adresse"], z["art"], z["name"], z["besitzer_id"], z["aktiv"]) for z in zeilen] == [(ANNA, "konto", "Anna", anna.id, True), (KRAN, "geraet", "Kran 30 m", kran.id, True)]
    assert zeilen[0]["letzter_lauf"] == datetime(2026, 10, 30, 12) and zeilen[0]["letzter_fehler"] is None
    assert zeilen[1]["letzter_lauf"] is None  # noch kein Lauf, noch kein Stand


def test_auch_inaktive_stehen_darin():
    db = db_session()
    _kran(db, aktiv=False)
    assert _zeile(db, KRAN)["aktiv"] is False


def test_ohne_postfach_steht_niemand_darin():
    db = db_session()
    _make_user(db, username="ohne", mailbox=None)
    _kran(db, postfach=None)
    assert postfach_uebersicht(db) == []


def test_wartet_deckt_sich_mit_dem_lauf():
    db = db_session()
    _enable_sync(db)
    anna = _make_user(db, username="anna", mailbox=ANNA)
    ms = Microsoft()
    ms.postfach(ANNA)
    _make_event(db, anna, title="Neu", start_at=BEGINN, end_at=BEGINN)
    assert _zeile(db, ANNA)["wartet"] == 1
    with patch(URLOPEN, side_effect=ms.urlopen):
        sync_user_calendar(db, anna)
    assert _zeile(db, ANNA)["wartet"] == 0
    zeile = db.scalar(select(CalendarEvent))
    zeile.title = "Geändert"
    db.commit()
    assert _needs_push(zeile) is True and _zeile(db, ANNA)["wartet"] == 1
    with patch(URLOPEN, side_effect=ms.urlopen):
        sync_user_calendar(db, anna)
    assert _needs_push(db.scalar(select(CalendarEvent))) is False and _zeile(db, ANNA)["wartet"] == 0


def test_wartet_zaehlt_auch_was_im_alten_postfach_liegt():
    db = db_session()
    anna = _make_user(db, username="anna", mailbox=ANNA)
    zeile = _make_event(db, anna, title="T", start_at=BEGINN, end_at=BEGINN)
    db.execute(CalendarEvent.__table__.update().where(CalendarEvent.id == zeile.id).values(outlook_event_id="K", outlook_postfach="alt@x.de", outlook_synced_at=datetime(2030, 1, 1)))
    db.commit()
    assert _zeile(db, ANNA)["wartet"] == 1


def test_wartet_auf_loeschen_je_postfach():
    db = db_session()
    _make_user(db, username="anna", mailbox=ANNA)
    db.add_all([OutlookDeleteOrder(postfach=ANNA, outlook_event_id="A"), OutlookDeleteOrder(postfach="anderes@x.de", outlook_event_id="B")])
    db.commit()
    assert _zeile(db, ANNA)["loeschen_offen"] == 1


def test_laeuft_gerade_nur_innerhalb_der_frist():
    db = db_session()
    _make_user(db, username="anna", mailbox=ANNA)
    stand = get_or_create_sync_state(db, ANNA)
    stand.lauf_seit = datetime.utcnow()
    db.commit()
    assert _zeile(db, ANNA)["laeuft_seit"] is not None
    stand.lauf_seit = datetime.utcnow() - SPERRE_GILT - timedelta(minutes=1)
    db.commit()
    assert _zeile(db, ANNA)["laeuft_seit"] is None


@pytest.mark.parametrize("art, status, teil", [
    ("OutlookSyncError", 403, "Gruppe ERP-Zugriff"),
    ("OutlookSyncError", 401, "Zugangsdaten"),
    ("ValueError", None, "Zugangsdaten"),
    ("OutlookSyncError", 404, "Adresse prüfen"),
    ("OutlookSyncError", 503, "Status 503"),
    ("OutlookSyncError", None, "nicht geantwortet"),
    ("KeyError", None, "KeyError"),
])
def test_fehler_als_satz(art, status, teil):
    assert teil in fehler_text(art, status)


def test_kein_fehler_kein_satz():
    assert fehler_text(None, None) is None


def test_der_lauf_merkt_den_status_und_nie_den_text():
    db = db_session()
    _enable_sync(db)
    anna = _make_user(db, username="anna", mailbox=ANNA)
    ms = Microsoft()
    ms.postfach(ANNA)
    ms.gesperrt.add(ANNA)
    with patch(URLOPEN, side_effect=ms.urlopen):
        sync_user_calendar(db, anna)
    zeile = _zeile(db, ANNA)
    assert get_or_create_sync_state(db, ANNA).last_error_status == 403
    assert "Gruppe ERP-Zugriff" in zeile["letzter_fehler"] and zeile["fehler_am"] is not None
    assert "Klartext" not in zeile["letzter_fehler"]
    ms.gesperrt.clear()
    with patch(URLOPEN, side_effect=ms.urlopen):
        sync_user_calendar(db, anna)
    stand = get_or_create_sync_state(db, ANNA)
    assert (stand.last_error_type, stand.last_error_at, stand.last_error_status) == (None, None, None)
    assert _zeile(db, ANNA)["letzter_fehler"] is None


@pytest.mark.parametrize("rolle", ["buero_finanzen", "buero_auftrag", "field"])
@pytest.mark.parametrize("adresse", ["/api/outlook-sync-settings/postfaecher", "/api/outlook-sync-settings/geraete"])
def test_nur_der_admin(threaded_db_session, router_test_client, rolle, adresse):
    assert router_test_client(threaded_db_session, settings_router, role=rolle).get(adresse).status_code == 403


def test_auswahl_nur_aktive_geraete_ohne_postfach(threaded_db_session, router_test_client):
    db = threaded_db_session
    frei = _kran(db, postfach=None, name="Frei")
    _kran(db, postfach=None, aktiv=False, name="Inaktiv")
    _kran(db, name="Vergeben")
    client = router_test_client(db, settings_router)
    assert client.get("/api/outlook-sync-settings/geraete").json() == [{"id": frei.id, "name": "Frei"}]
    antwort = client.get("/api/outlook-sync-settings/postfaecher").json()
    assert [z["name"] for z in antwort] == ["Vergeben"] and antwort[0]["wartet"] == 0


def test_die_seite():
    seite = (ROOT / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "api('/api/outlook-sync-settings/postfaecher')" in seite
    assert "await loadOutlookPostfaecher();" in seite
    assert bindet_ein("settings.html", "_berlin_date.html") and bindet_ein("settings.html", "_aktionen.html") and bindet_ein("settings.html", "_auswahl.html")
