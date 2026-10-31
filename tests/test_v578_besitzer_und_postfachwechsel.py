"""Version 1.9.160 (Stufe 6, R2, Punkt 4): Besitzer- und Postfachwechsel führen in keinen dauerhaft falschen Zustand.

    Besitzer  der Termin zieht um: raus aus dem alten Postfach, rein ins neue, eine Zeile, Ruhe (Befund XB1–XB6)
              neuer Besitzer ohne Postfach: raus aus dem alten; Löschen erreicht das Postfach, in dem er liegt (XC1)
    Netz      scheitert das Löschen, bleibt ein Auftrag: nichts kommt zurück, der nächste Lauf holt es nach; 403 und 404 geben auf
    Postfach  gewechselt: was das ERP anlegte, zieht um; was aus dem alten stammt, bleibt dort (mit Projekt auch im ERP); umbenannt: nichts doppelt, kein Schreibzugriff
              entfernt: Einzeltermine bleiben, Vorkommen fallen weg; dasselbe zurück: nichts doppelt; an ein anderes Konto: die Termine gehen mit
    404       PATCH auf einen Termin, den das Postfach nicht kennt: neu anlegen statt jeder Lauf ein Fehler
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.models import CalendarEvent, OutlookDeleteOrder, OutlookSeriesOccurrence
from app.outlook_calendar_sync import get_or_create_sync_state, sync_user_calendar, try_delete_remote_event, update_outlook_sync_settings
from app.routers.calendar_events import router as calendar_router
from app.routers.users import router as users_router
from tests.bestand_alt import auftrag
from tests.outlook_attrappe import Microsoft, http_fehler
from tests.test_v297_outlook_calendar_sync import _enable_sync, _make_event, _make_user

URLOPEN = "app.outlook_calendar_sync.urllib.request.urlopen"
ANNA, BEN = "anna@x.de", "ben@x.de"
BEGINN = datetime(2026, 11, 10, 9, 0)
ENDE = BEGINN + timedelta(hours=1)
RUHE = ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed")


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    _enable_sync(db)
    ms = Microsoft()
    for adresse in (ANNA, BEN):
        ms.postfach(adresse)

    class Welt:
        pass

    w = Welt()
    w.db, w.ms = db, ms
    w.anna = _make_user(db, username="anna", mailbox=ANNA)
    w.ben = _make_user(db, username="ben", mailbox=BEN)
    w.client = router_test_client(db, calendar_router, users_router)
    with patch(URLOPEN, side_effect=ms.urlopen):
        yield w


def _termin(w, besitzer, titel="Aufmaß", **werte):
    antwort = w.client.post("/api/calendar-events", json={"title": titel, "start_at": BEGINN.isoformat(), "end_at": ENDE.isoformat(), "owner_user_id": besitzer.id, **werte})
    assert antwort.status_code == 200, antwort.text
    return w.db.get(CalendarEvent, antwort.json()["id"])


def _besitzer(w, termin, konto):
    antwort = w.client.put(f"/api/calendar-events/{termin.id}", json={"owner_user_id": konto.id})
    assert antwort.status_code == 200, antwort.text
    w.db.refresh(termin)


def _ruhig(w, *konten):
    for konto in konten:
        for _ in range(3):
            ergebnis = sync_user_calendar(w.db, konto)
            assert {k: ergebnis[k] for k in RUHE} == dict.fromkeys(RUHE, 0), ergebnis


def _auftraege(w):
    return w.db.scalars(select(OutlookDeleteOrder)).all()


def _zeilen(w):
    return w.db.scalar(select(func.count()).select_from(CalendarEvent))


# --- Besitzer -------------------------------------------------------------------------------------------

def test_besitzerwechsel_zieht_den_termin_um(welt):
    w = welt
    termin = _termin(w, w.anna)
    alt = termin.outlook_event_id
    assert termin.outlook_postfach == ANNA and alt in w.ms.postfach(ANNA).events

    _besitzer(w, termin, w.ben)

    assert termin.outlook_postfach == BEN and termin.outlook_event_id in w.ms.postfach(BEN).events
    assert alt not in w.ms.postfach(ANNA).events
    assert _auftraege(w) == []
    assert _zeilen(w) == 1
    _ruhig(w, w.anna, w.ben)
    assert _zeilen(w) == 1


def test_das_alte_postfach_aendert_den_termin_waehrend_der_umzug_haengt(welt):
    """Befund XB5/XB6: ein zweiter Termin im ERP mit derselben Kennung, weil das alte Postfach weiter lieferte."""
    w = welt
    termin = _termin(w, w.anna)
    alt = termin.outlook_event_id
    sync_user_calendar(w.db, w.anna)
    ursprung = w.ms.vor_antwort

    def alte_kopie_nicht_loeschbar(methode, adresse, weg):
        if methode == "DELETE":
            raise http_fehler(503, "ServiceUnavailable")

    w.ms.vor_antwort = alte_kopie_nicht_loeschbar
    _besitzer(w, termin, w.ben)
    assert [a.outlook_event_id for a in _auftraege(w)] == [alt] and _auftraege(w)[0].last_error_type == "OutlookSyncError"
    w.ms.postfach(ANNA).aendern(alt, subject="Anna ändert in Outlook")

    ergebnis = sync_user_calendar(w.db, w.anna)  # noch gesperrt: der Auftrag bleibt, die Änderung kommt nicht herein

    assert ergebnis["created"] == 0 and _zeilen(w) == 1 and len(_auftraege(w)) == 1
    w.ms.vor_antwort = ursprung
    sync_user_calendar(w.db, w.anna)
    assert _auftraege(w) == [] and alt not in w.ms.postfach(ANNA).events
    _ruhig(w, w.anna, w.ben)
    assert _zeilen(w) == 1 and w.db.get(CalendarEvent, termin.id).title == "Aufmaß"


def test_neuer_besitzer_ohne_postfach(welt):
    w = welt
    cara = _make_user(w.db, username="cara", mailbox=None)
    termin = _termin(w, w.anna)
    alt = termin.outlook_event_id

    _besitzer(w, termin, cara)

    assert alt not in w.ms.postfach(ANNA).events
    assert (termin.outlook_event_id, termin.outlook_postfach, termin.outlook_synced_at) == (None, None, None)
    _ruhig(w, w.anna)
    assert _zeilen(w) == 1


def test_und_zurueck_zum_ersten_besitzer(welt):
    w = welt
    termin = _termin(w, w.anna)
    _besitzer(w, termin, w.ben)
    _besitzer(w, termin, w.anna)
    assert termin.outlook_postfach == ANNA
    assert list(w.ms.postfach(BEN).events) == [] and len(w.ms.postfach(ANNA).events) == 1
    _ruhig(w, w.anna, w.ben)


def test_nur_den_titel_aendern_zieht_nicht_um(welt):
    w = welt
    termin = _termin(w, w.anna)
    kennung = termin.outlook_event_id
    assert w.client.put(f"/api/calendar-events/{termin.id}", json={"title": "Neu"}).status_code == 200
    w.db.refresh(termin)
    assert termin.outlook_event_id == kennung and w.ms.postfach(ANNA).events[kennung]["subject"] == "Neu"
    assert w.ms.schreibend("DELETE") == []


def test_besitzerwechsel_bei_ausgeschaltetem_abgleich_wird_nachgeholt(welt):
    w = welt
    termin = _termin(w, w.anna)
    alt = termin.outlook_event_id
    update_outlook_sync_settings(w.db, enabled=False)
    _besitzer(w, termin, w.ben)
    assert termin.outlook_event_id is None and len(_auftraege(w)) == 1
    assert alt in w.ms.postfach(ANNA).events  # kein Netz, solange aus
    update_outlook_sync_settings(w.db, enabled=True)
    sync_user_calendar(w.db, w.ben)
    w.db.refresh(termin)
    assert termin.outlook_postfach == BEN and alt not in w.ms.postfach(ANNA).events and _auftraege(w) == []


# --- Löschen --------------------------------------------------------------------------------------------

def test_loeschen_erreicht_das_postfach_in_dem_er_liegt(welt):
    """Befund XC1: Besitzer ohne Postfach -- bis 1.9.159 meldete das Fernlöschen Erfolg und ließ den Termin in Outlook."""
    w = welt
    termin = _termin(w, w.anna)
    kennung = termin.outlook_event_id
    w.anna.outlook_mailbox = None  # das Konto verliert das Postfach, die Termine liegen weiter dort
    w.db.commit()
    assert w.client.delete(f"/api/calendar-events/{termin.id}").status_code == 200
    assert kennung not in w.ms.postfach(ANNA).events
    assert _zeilen(w) == 0 and _auftraege(w) == []


def test_ein_gescheitertes_fernloeschen_bringt_den_termin_nicht_zurueck(welt):
    """Das „Resurrection-Risiko“ aus dem Archiv."""
    w = welt
    termin = _termin(w, w.anna)
    kennung = termin.outlook_event_id
    sync_user_calendar(w.db, w.anna)

    def scheitert(methode, adresse, weg):
        if methode == "DELETE":
            raise http_fehler(500, "InternalServerError")

    w.ms.vor_antwort = scheitert
    assert w.client.delete(f"/api/calendar-events/{termin.id}").status_code == 200
    assert _zeilen(w) == 0 and len(_auftraege(w)) == 1
    w.ms.postfach(ANNA).aendern(kennung, subject="noch da")

    assert sync_user_calendar(w.db, w.anna)["created"] == 0
    assert _zeilen(w) == 0 and len(_auftraege(w)) == 1

    w.ms.vor_antwort = None
    assert sync_user_calendar(w.db, w.anna)["created"] == 0
    assert kennung not in w.ms.postfach(ANNA).events and _auftraege(w) == []
    _ruhig(w, w.anna)
    assert _zeilen(w) == 0


def test_wird_er_in_outlook_geloescht_erledigt_sich_der_auftrag(welt):
    w = welt
    termin = _termin(w, w.anna)
    kennung = termin.outlook_event_id
    sync_user_calendar(w.db, w.anna)
    w.ms.vor_antwort = lambda methode, adresse, weg: (_ for _ in ()).throw(http_fehler(500, "InternalServerError")) if methode == "DELETE" else None
    w.client.delete(f"/api/calendar-events/{termin.id}")
    w.ms.postfach(ANNA).loeschen(kennung)
    sync_user_calendar(w.db, w.anna)
    assert _auftraege(w) == []


@pytest.mark.parametrize("status, weg_aus_outlook", [(403, False), (404, True)])
def test_kein_zugriff_oder_schon_weg_gibt_auf(welt, status, weg_aus_outlook):
    """404: schon weg. 403: das wird nicht wieder gut, der Auftrag fällt weg, die Kopie bleibt dort -- das meldet die Funktion auch so."""
    w = welt
    termin = _termin(w, w.anna)
    w.ms.vor_antwort = lambda methode, adresse, weg: (_ for _ in ()).throw(http_fehler(status, "x")) if methode == "DELETE" else None
    assert try_delete_remote_event(w.db, termin) is weg_aus_outlook
    assert _auftraege(w) == []


def test_ein_fehlschlag_nennt_keinen_inhalt(welt, caplog):
    w = welt
    termin = _termin(w, w.anna, titel="Geheimes Aufmaß")
    w.ms.vor_antwort = lambda methode, adresse, weg: (_ for _ in ()).throw(http_fehler(500, "x")) if methode == "DELETE" else None
    with caplog.at_level("WARNING"):
        assert try_delete_remote_event(w.db, termin) is False
    assert "Fernlöschen" in caplog.text and "Geheimes" not in caplog.text and "Klartext" not in caplog.text


# --- Postfach am Konto ------------------------------------------------------------------------------------

NEU = "neu@x.de"


def _postfach(w, konto, adresse):
    antwort = w.client.put(f"/api/users/{konto.id}", json={"username": konto.username, "display_name": konto.display_name, "role": konto.role, "active": True, "outlook_mailbox": adresse})
    assert antwort.status_code == 200, antwort.text


def test_postfachwechsel_was_das_erp_anlegte_zieht_um(welt):
    w = welt
    w.ms.postfach(NEU)
    termin = _termin(w, w.anna)
    alt = termin.outlook_event_id
    sync_user_calendar(w.db, w.anna)

    _postfach(w, w.anna, NEU)
    assert not sync_user_calendar(w.db, w.anna).get("error")

    w.db.refresh(termin)
    assert termin.outlook_postfach == NEU and termin.outlook_event_id in w.ms.postfach(NEU).events
    assert alt not in w.ms.postfach(ANNA).events and _auftraege(w) == []
    _ruhig(w, w.anna)
    assert _zeilen(w) == 1


def test_postfachwechsel_was_aus_dem_alten_stammt_bleibt_dort(welt):
    w = welt
    neues = w.ms.postfach(NEU)
    eigenes_neu = neues.anlegen("Im neuen Postfach", BEGINN, ENDE)
    kennung = w.ms.postfach(ANNA).anlegen("Aus dem alten", BEGINN, ENDE)
    sync_user_calendar(w.db, w.anna)
    assert _zeilen(w) == 1

    _postfach(w, w.anna, NEU)
    ergebnis = sync_user_calendar(w.db, w.anna)

    assert ergebnis["deleted"] == 1 and ergebnis["created"] == 1
    assert kennung in w.ms.postfach(ANNA).events  # nie aus einem fremden Postfach löschen, was das ERP nicht angelegt hat
    assert w.ms.schreibend("DELETE") == [] and w.ms.schreibend("POST") == []
    assert [z.outlook_event_id for z in w.db.scalars(select(CalendarEvent))] == [eigenes_neu]
    _ruhig(w, w.anna)


def test_postfachwechsel_mit_projekt_bleibt_und_geht_ins_neue(welt):
    w = welt
    w.ms.postfach(NEU)
    kennung = w.ms.postfach(ANNA).anlegen("Mit Projekt", BEGINN, ENDE)
    sync_user_calendar(w.db, w.anna)
    zeile = w.db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == kennung))
    projekt = auftrag(w.db, number="1").project_id
    w.client.put(f"/api/calendar-events/{zeile.id}", json={"project_id": projekt})

    _postfach(w, w.anna, NEU)
    sync_user_calendar(w.db, w.anna)

    w.db.refresh(zeile)
    assert zeile.project_id == projekt and zeile.outlook_postfach == NEU and zeile.external_source == "erp"
    assert len(w.ms.postfach(NEU).events) == 1
    assert kennung in w.ms.postfach(ANNA).events
    _ruhig(w, w.anna)
    assert _zeilen(w) == 1


def test_umbenannte_adresse_nichts_doppelt_kein_schreibzugriff(welt):
    """Dasselbe Postfach unter einer neuen Adresse: dieselben Kennungen."""
    w = welt
    termin = _termin(w, w.anna)
    kennung = w.ms.postfach(ANNA).anlegen("Aus Outlook", BEGINN, ENDE)
    sync_user_calendar(w.db, w.anna)
    w.ms.postfaecher[NEU] = w.ms.postfaecher[ANNA]
    w.ms.anfragen.clear()

    _postfach(w, w.anna, NEU)
    sync_user_calendar(w.db, w.anna)

    w.db.refresh(termin)
    assert termin.outlook_postfach == NEU and _zeilen(w) == 2
    assert w.db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == kennung)).outlook_postfach == NEU
    assert w.ms.schreibend() == []
    _ruhig(w, w.anna)


def test_ein_alter_stand_der_neuen_adresse_liest_trotzdem_den_ganzen_kalender(welt):
    """Liegt etwas woanders, beweist nur der ganze Kalender, was davon hier liegt -- auch wenn für die neue Adresse noch ein Link steht, der nichts mehr liefert."""
    w = welt
    termin = _termin(w, w.anna)
    sync_user_calendar(w.db, w.anna)
    w.ms.postfaecher[NEU] = w.ms.postfaecher[ANNA]
    stand = get_or_create_sync_state(w.db, NEU)
    stand.delta_link = get_or_create_sync_state(w.db, ANNA).delta_link
    w.anna.outlook_mailbox = NEU
    w.db.commit()
    w.ms.anfragen.clear()

    sync_user_calendar(w.db, w.anna)

    w.db.refresh(termin)
    assert termin.outlook_postfach == NEU and w.ms.schreibend() == []


def test_irrtum_bei_der_adresse_laesst_das_fremde_postfach_in_ruhe(welt):
    """Eine falsche Adresse (Bens Postfach), dann korrigiert: Bens eigene Termine bleiben in seinem Postfach."""
    w = welt
    w.ben.outlook_mailbox = None
    w.db.commit()
    bens = w.ms.postfach(BEN).anlegen("Bens Termin", BEGINN, ENDE)
    w.ms.postfach(NEU)
    _postfach(w, w.anna, BEN)
    sync_user_calendar(w.db, w.anna)
    assert _zeilen(w) == 1

    _postfach(w, w.anna, NEU)
    sync_user_calendar(w.db, w.anna)

    assert bens in w.ms.postfach(BEN).events and w.ms.schreibend("DELETE") == []
    assert _zeilen(w) == 0 and list(w.ms.postfach(NEU).events) == []


def test_postfach_entfernt_und_dasselbe_zurueck(welt):
    w = welt
    termin = _termin(w, w.anna)
    w.ms.postfach(ANNA).anlegen("Aus Outlook", BEGINN, ENDE)
    w.ms.postfach(ANNA).add_series("Serie", datetime.utcnow() + timedelta(days=1), count=2)
    sync_user_calendar(w.db, w.anna)
    assert w.db.scalar(select(func.count()).select_from(OutlookSeriesOccurrence)) == 2

    _postfach(w, w.anna, "")
    assert w.db.scalar(select(func.count()).select_from(OutlookSeriesOccurrence)) == 0  # niemand zieht sie mehr nach
    assert _zeilen(w) == 2
    assert sync_user_calendar(w.db, w.anna)["skipped"] is True

    w.ms.anfragen.clear()
    _postfach(w, w.anna, ANNA)
    assert get_or_create_sync_state(w.db, ANNA).delta_link is None
    sync_user_calendar(w.db, w.anna)
    assert w.ms.schreibend() == [] and _zeilen(w) == 2
    assert w.db.scalar(select(func.count()).select_from(OutlookSeriesOccurrence)) == 2
    w.db.refresh(termin)
    assert termin.outlook_postfach == ANNA


def test_postfach_an_ein_anderes_konto_die_termine_gehen_mit(welt):
    w = welt
    cara = _make_user(w.db, username="cara", mailbox=None)
    termin = _termin(w, w.anna)
    kennung = w.ms.postfach(ANNA).anlegen("Aus Outlook", BEGINN, ENDE)
    sync_user_calendar(w.db, w.anna)

    _postfach(w, w.anna, "")
    _postfach(w, cara, ANNA)
    sync_user_calendar(w.db, cara)

    w.db.refresh(termin)
    assert termin.owner_user_id == cara.id
    assert w.db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == kennung)).owner_user_id == cara.id
    assert w.ms.schreibend("DELETE") == [] and _zeilen(w) == 2
    _ruhig(w, cara)


def test_vorkommen_des_alten_postfachs_fallen_mit_dem_lauf_weg(welt):
    w = welt
    neues = w.ms.postfach(NEU)
    w.ms.postfach(ANNA).add_series("Alt", datetime.utcnow() + timedelta(days=1), count=2)
    neues.add_series("Neu", datetime.utcnow() + timedelta(days=2), count=1)
    sync_user_calendar(w.db, w.anna)
    _postfach(w, w.anna, NEU)
    sync_user_calendar(w.db, w.anna)
    assert [z.title for z in w.db.scalars(select(OutlookSeriesOccurrence))] == ["Neu"]
    assert {z.outlook_postfach for z in w.db.scalars(select(OutlookSeriesOccurrence))} == {NEU}


# --- 404 ------------------------------------------------------------------------------------------------

def test_kennt_das_postfach_den_termin_nicht_wird_er_neu_angelegt(welt):
    """Stand von vor 1.9.160: eine Kennung, die dort nicht gilt. Bis dahin scheiterte jeder Lauf daran, ohne Ende (Befund XB4)."""
    w = welt
    sync_user_calendar(w.db, w.anna)  # es steht ein Link: dieser Lauf liest nicht den ganzen Kalender
    termin = _make_event(w.db, w.anna, title="Falsch vermerkt", start_at=BEGINN, end_at=ENDE)
    termin.outlook_event_id = "gibt-es-hier-nicht"
    termin.outlook_postfach = ANNA
    termin.title = "Geändert"
    w.db.commit()

    ergebnis = sync_user_calendar(w.db, w.anna)

    assert ergebnis["push_failed"] == 0 and ergebnis["pushed_created"] == 1
    w.db.refresh(termin)
    assert termin.outlook_event_id in w.ms.postfach(ANNA).events
    _ruhig(w, w.anna)


def test_ein_anderer_fehler_beim_aendern_legt_nichts_neu_an(welt):
    w = welt
    termin = _termin(w, w.anna)
    kennung = termin.outlook_event_id
    termin.title = "Geändert"
    w.db.commit()
    sync_user_calendar(w.db, w.anna)
    termin.title = "Noch einmal"
    w.db.commit()

    def scheitert(methode, adresse, weg):
        if methode == "PATCH":
            raise http_fehler(500, "InternalServerError")

    w.ms.vor_antwort = scheitert
    assert sync_user_calendar(w.db, w.anna)["push_failed"] == 1
    w.ms.vor_antwort = None
    assert list(w.ms.postfach(ANNA).events) == [kennung]
