"""Seit 1.9.81 (Stufe 4, R4 Nachtrag 3, B, Entscheidung Tobias): die Monteurin bucht nicht auf abgeschlossene oder stornierte Aufträge.

    gesperrt   Start, Nachtrag, Ändern (eine Buchung dorthin verschieben, dort ändern, von dort wegschieben), Löschen, Kolonne (Nachtrag,
               Start, Ändern, Löschen), „Zeitart wechseln“, „Pausen neu rechnen“ an einer Buchung dort -- 403 mit „Der Auftrag ist
               abgeschlossen – Zeiten dafür trägt das Büro ein.“ (storniert: „Der Auftrag ist storniert – …“), nichts gebucht
    frei       eine laufende Zeit beendet sie immer (Stopp, Gruppen-Stopp, Ende nachtragen), auch wenn der Auftrag inzwischen abgeschlossen ist;
               das Büro bucht wie bisher
"""

from datetime import datetime, time, timedelta

import pytest

from app.meldungen import AUFTRAG_ABGESCHLOSSEN_ZEITEN, AUFTRAG_STORNIERT_ZEITEN
from app.models import TimeEntry, TimeEntryGroup
from app.routers import time_tracking as time_tracking_router
from app.time_tracking import auftrag_zeiten_gesperrt, create_group_manual_entry, start_group_timer, start_timer, stop_timer
from tests.test_v224_field_view import make_employee
from tests.test_v471_heute_server import _als, _einsatz, _zweiter_auftrag, welt  # noqa: F401  (Fixture)

MELDUNG = {"abgeschlossen": AUFTRAG_ABGESCHLOSSEN_ZEITEN, "storniert": AUFTRAG_STORNIERT_ZEITEN}


def _vorbereiten(w):
    """Mia und Tom eingeplant am Auftrag (Mia Kolonnenführerin) und an einem zweiten, offenen Auftrag -- der Zugang steht, gesperrt ist
    nur, was am Status des Auftrags hängt."""
    w["offen"] = _zweiter_auftrag(w)
    for order in (w["order"], w["offen"]):
        _einsatz(w, order, [(w["heute"] - timedelta(days=7), w["heute"])], [w["mia"], w["tom"]])
    return _als(w, w["mia"])


def _schliessen(w, status):
    w["order"].status = status
    w["db"].commit()


def _zeit(w, emp, von, bis, tag, order=None):
    row = start_timer(w["db"], employee_id=emp.id, order_id=(order or w["order"]).id, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis))


def _abgelehnt(antwort, status):
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["detail"] == MELDUNG[status]


def _buero(w, emp=None):
    """Das Büro: Büro – Auftrag mit eigenem Mitarbeiter (bucht für sich), ohne emp ein Admin (bucht auch für andere)."""
    if emp is None:
        return w["client"](w["db"], time_tracking_router.router, role="admin")
    return w["client"](w["db"], time_tracking_router.router, role="buero_auftrag", employee_id=emp.id)


def _anzahl(w):
    w["db"].expire_all()
    return w["db"].query(TimeEntry).count(), w["db"].query(TimeEntryGroup).count()


def test_meldung_je_status():
    class A:
        status = None
    for status, soll in (("abgeschlossen", AUFTRAG_ABGESCHLOSSEN_ZEITEN), (" Storniert ", AUFTRAG_STORNIERT_ZEITEN), ("beauftragt", None),
                         (None, None)):
        A.status = status
        assert auftrag_zeiten_gesperrt(A) == soll
    assert auftrag_zeiten_gesperrt(None) is None


@pytest.mark.parametrize("status", ["abgeschlossen", "storniert"])
def test_start_und_nachtrag_abgelehnt_buero_bucht(welt, status):  # noqa: F811
    """Angriff: Start und Nachtrag (Von/Bis) der Monteurin auf den geschlossenen Auftrag -> 403 mit der Meldung, nichts gebucht. Gegenprobe:
    derselbe Nachtrag auf den offenen Auftrag geht; das Büro (Büro – Auftrag für sich) startet und trägt auf den geschlossenen nach."""
    mia = _vorbereiten(welt)
    _schliessen(welt, status)
    gestern = welt["gestern"].isoformat()
    vorher = _anzahl(welt)
    _abgelehnt(mia.post("/api/time-entries/start", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id}), status)
    _abgelehnt(mia.post("/api/time-entries", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id, "work_date": gestern,
                                                   "von": "07:00", "bis": "12:00"}), status)
    assert _anzahl(welt) == vorher
    offen = mia.post("/api/time-entries", json={"employee_id": welt["mia"].id, "order_id": welt["offen"].id, "work_date": gestern,
                                                "von": "07:00", "bis": "12:00"})
    assert offen.status_code == 200, offen.text
    bea = make_employee(welt["db"], "B-504", "Bea", "Büro")
    buero = _buero(welt, bea)
    b1 = buero.post("/api/time-entries", json={"employee_id": bea.id, "order_id": welt["order"].id, "work_date": gestern, "hours": "2"})
    assert b1.status_code == 200, b1.text
    b2 = buero.post("/api/time-entries/start", json={"employee_id": bea.id, "order_id": welt["order"].id})
    assert b2.status_code == 200, b2.text


def test_aendern_dorthin_dort_und_weg_abgelehnt_buero_aendert(welt):  # noqa: F811
    """Angriff: eine Buchung auf dem offenen Auftrag dorthin verschieben, eine Buchung dort ändern, von dort wegschieben -> 403, nichts
    geändert. Gegenprobe: dieselbe Buchung auf dem offenen Auftrag ändern geht; der Admin ändert die Buchung dort."""
    mia = _vorbereiten(welt)
    gestern = welt["gestern"]
    hier = _zeit(welt, welt["mia"], time(7), time(12), gestern, order=welt["offen"])
    dort = _zeit(welt, welt["mia"], time(12, 30), time(15), gestern)
    _schliessen(welt, "abgeschlossen")
    _abgelehnt(mia.put(f"/api/time-entries/{hier.id}", json={"order_id": welt["order"].id}), "abgeschlossen")
    _abgelehnt(mia.put(f"/api/time-entries/{dort.id}", json={"von": "12:30", "bis": "16:00"}), "abgeschlossen")
    _abgelehnt(mia.put(f"/api/time-entries/{dort.id}", json={"notes": "nur eine Notiz"}), "abgeschlossen")
    _abgelehnt(mia.put(f"/api/time-entries/{dort.id}", json={"order_id": welt["offen"].id}), "abgeschlossen")
    welt["db"].expire_all()
    assert (welt["db"].get(TimeEntry, hier.id).order_id, welt["db"].get(TimeEntry, dort.id).order_id) == (welt["offen"].id, welt["order"].id)
    assert welt["db"].get(TimeEntry, dort.id).notes is None
    ok = mia.put(f"/api/time-entries/{hier.id}", json={"notes": "Rinne"})
    assert ok.status_code == 200, ok.text
    buero = _buero(welt).put(f"/api/time-entries/{dort.id}", json={"notes": "vom Büro"})
    assert buero.status_code == 200, buero.text


def test_loeschen_abgelehnt_buero_loescht(welt):  # noqa: F811
    """Angriff: eine eigene Buchung des geschlossenen Auftrags löschen -> 403, sie bleibt; der Admin löscht sie."""
    mia = _vorbereiten(welt)
    dort = _zeit(welt, welt["mia"], time(7), time(12), welt["gestern"])
    _schliessen(welt, "storniert")
    _abgelehnt(mia.delete(f"/api/time-entries/{dort.id}"), "storniert")
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, dort.id) is not None
    assert _buero(welt).delete(f"/api/time-entries/{dort.id}").status_code == 200


def test_kolonne_abgelehnt_buero_bucht(welt):  # noqa: F811
    """Angriff: die Kolonnenführerin trägt für die Kolonne nach, startet sie, ändert und löscht eine Kolonnenbuchung des geschlossenen
    Auftrags -> 403, nichts gebucht oder geändert. Gegenprobe: der Admin trägt für die Kolonne nach."""
    mia = _vorbereiten(welt)
    g = welt["gestern"]
    gruppe = create_group_manual_entry(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                                       actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id, work_date=g,
                                       entry_type="site", von=time(7), bis=time(11))
    _schliessen(welt, "abgeschlossen")
    vorher = _anzahl(welt)
    koerper = {"employee_ids": [welt["mia"].id, welt["tom"].id], "team_id": welt["team"].id, "order_id": welt["order"].id}
    _abgelehnt(mia.post("/api/time-entry-groups", json={**koerper, "work_date": g.isoformat(), "von": "12:00", "bis": "15:00"}), "abgeschlossen")
    _abgelehnt(mia.post("/api/time-entry-groups/start", json=koerper), "abgeschlossen")
    _abgelehnt(mia.put(f"/api/time-entry-groups/{gruppe.id}", json={"notes": "geändert"}), "abgeschlossen")
    _abgelehnt(mia.put(f"/api/time-entry-groups/{gruppe.id}", json={"order_id": welt["offen"].id}), "abgeschlossen")
    _abgelehnt(mia.delete(f"/api/time-entry-groups/{gruppe.id}"), "abgeschlossen")
    assert _anzahl(welt) == vorher
    welt["db"].expire_all()
    assert (welt["db"].get(TimeEntryGroup, gruppe.id).order_id, welt["db"].get(TimeEntryGroup, gruppe.id).notes) == (welt["order"].id, None)
    buero = _buero(welt).post("/api/time-entry-groups", json={**koerper, "work_date": g.isoformat(), "von": "12:00", "bis": "15:00"})
    assert buero.status_code == 200, buero.text


def test_zeitart_wechseln_abgelehnt_beenden_geht(welt):  # noqa: F811
    """Angriff: die laufende Zeit, Auftrag inzwischen abgeschlossen -> „Zeitart wechseln“ 403 (die neue Zeit wäre dort), sie läuft weiter.
    Gegenprobe: „Feierabend“ (Stopp) beendet sie."""
    mia = _vorbereiten(welt)
    laeuft = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    _schliessen(welt, "abgeschlossen")
    _abgelehnt(mia.post(f"/api/time-entries/{laeuft.id}/zeitart-wechseln", json={"entry_type": "travel"}), "abgeschlossen")
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, laeuft.id).status == "running"
    stopp = mia.post(f"/api/time-entries/{laeuft.id}/stop", json={"break_minutes": 0})
    assert stopp.status_code == 200, stopp.text
    assert stopp.json()["status"] == "booked"


def test_ende_nachtragen_geht_auf_abgeschlossenem(welt):  # noqa: F811
    """Die Zeit läuft seit gestern (vergessener Feierabend), der Auftrag ist inzwischen abgeschlossen -> „Ende nachtragen“ schließt sie."""
    mia = _vorbereiten(welt)
    laeuft = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id,
                         started_at=datetime.combine(welt["gestern"], time(7)))
    _schliessen(welt, "abgeschlossen")
    ende = mia.post(f"/api/time-entries/{laeuft.id}/ende-nachtragen", json={"ende": f"{welt['gestern'].isoformat()}T15:00", "pause_minuten": 0})
    assert ende.status_code == 200, ende.text
    assert ende.json()["status"] == "booked"


def test_gruppenzeit_stoppen_geht_auf_abgeschlossenem(welt):  # noqa: F811
    """Die Gruppenzeit läuft, der Auftrag ist inzwischen storniert -> die Kolonnenführerin stoppt sie (für alle)."""
    mia = _vorbereiten(welt)
    gruppe = start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                               actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id,
                               started_at=datetime.combine(welt["heute"], time(7)))
    _schliessen(welt, "storniert")
    stopp = mia.post(f"/api/time-entry-groups/{gruppe.id}/stop", json={"break_minutes": 0})
    assert stopp.status_code == 200, stopp.text
    assert stopp.json()["status"] == "booked"


def test_pausen_neu_rechnen_an_buchung_dort_abgelehnt_buero_rechnet(welt):  # noqa: F811
    """Angriff: 07:00–12:00 und 12:00–16:15 (45 min) am geschlossenen Auftrag, die erste vorher gelöscht -> „Pausen neu rechnen“ würde die
    zweite ändern: 403, sie behält 45 min. Gegenprobe: der Admin rechnet für Mia genau diese Vorschau."""
    mia = _vorbereiten(welt)
    tag = welt["heute"]
    erste = _zeit(welt, welt["mia"], time(7), time(12), tag)
    zweite = _zeit(welt, welt["mia"], time(12), time(16, 15), tag)
    assert mia.delete(f"/api/time-entries/{erste.id}").status_code == 200
    _schliessen(welt, "abgeschlossen")
    koerper = {"work_date": tag.isoformat(), "buchungen": [{"id": zweite.id, "pause": 0}]}
    _abgelehnt(mia.post("/api/time-entries/pausen-neu-rechnen", json=koerper), "abgeschlossen")
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, zweite.id).break_minutes == 45
    buero = _buero(welt).post("/api/time-entries/pausen-neu-rechnen", json={**koerper, "employee_id": welt["mia"].id})
    assert buero.status_code == 200, buero.text
