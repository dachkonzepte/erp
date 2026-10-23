"""Seit 1.9.60 (Stufe 4, R3, Punkt 3): eine reine Dauer trägt nur das Büro ein -- die Monteurin trägt nach und ändert nur mit Von und Bis
(dann gilt die Pausenregel des Tages). Die eine Regel: app/permissions.py::zeit_nur_mit_von_bis().

    Nachtrag   POST /api/time-entries mit Stunden als Monteurin 422 (Meldung aus app/meldungen.py), mit Von/Bis gebucht; als Büro wie bisher
    Ändern     PUT /api/time-entries/{id} mit Stunden als Monteurin 422, mit Von/Bis neu gerechnet, nur Notiz geht; als Büro wie bisher
    Einsatzbericht  die Karte „Erfasste Zeiten“ zeigt der Monteurin Von und Bis statt „Stunden“, dem Büro die Stunden
Im Browser: scripts/klicktest_monteur_dachflaechen.py (Monteur bucht mit Von/Bis, Büro mit Stunden), scripts/klicktest_meine_zeiten.py.
"""

import re
from datetime import time, timedelta
from decimal import Decimal

from app.meldungen import NUR_VON_BIS
from app.models import TimeEntry
from app.permissions import zeit_nur_mit_von_bis
from app.routers import pages as pages_router
from app.time_tracking import create_manual_entry
from tests.test_v471_heute_server import _als, _einsatz, welt  # noqa: F401  (Fixture)
from app.routers import time_tracking as time_tracking_router


def _monteurin(w):
    _einsatz(w, w["order"], [(w["heute"] - timedelta(days=7), w["heute"])], [w["mia"]])
    return _als(w, w["mia"])


def _buero(w):
    return w["client"](w["db"], time_tracking_router.router, role="buero_auftrag", employee_id=w["tom"].id)


def _neu(emp, w, **mehr):
    return {"employee_id": emp.id, "order_id": w["order"].id, "work_date": w["heute"].isoformat(), **mehr}


def test_regel_nur_fuer_die_monteurin():
    class U:
        def __init__(self, rolle):
            self.role = rolle
    assert [zeit_nur_mit_von_bis(U(r)) for r in ("field", "buero_auftrag", "buero_finanzen", "admin")] == [True, False, False, False]
    assert zeit_nur_mit_von_bis(None) is False


def test_nachtrag_mit_stunden_als_monteurin_abgelehnt(welt):  # noqa: F811
    """Angriff: reine Dauer als Monteurin -> 422, nichts gebucht; Gegenprobe: mit Von/Bis gebucht (Pause aus der Regel)."""
    client = _monteurin(welt)
    r = client.post("/api/time-entries", json=_neu(welt["mia"], welt, hours=4))
    assert (r.status_code, r.json()["detail"]) == (422, NUR_VON_BIS)
    assert welt["db"].query(TimeEntry).count() == 0
    r = client.post("/api/time-entries", json=_neu(welt["mia"], welt, von="07:00", bis="11:00"))
    assert r.status_code == 200, r.text
    assert Decimal(str(r.json()["hours"])) == Decimal("4")


def test_nachtrag_mit_stunden_als_buero_wie_bisher(welt):  # noqa: F811
    r = _buero(welt).post("/api/time-entries", json=_neu(welt["tom"], welt, hours=4))
    assert r.status_code == 200, r.text
    assert Decimal(str(r.json()["hours"])) == Decimal("4")


def test_aendern_mit_stunden_als_monteurin_abgelehnt(welt):  # noqa: F811
    client = _monteurin(welt)
    row = create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=welt["heute"], hours=Decimal("4"))
    r = client.put(f"/api/time-entries/{row.id}", json={"hours": 6})
    assert (r.status_code, r.json()["detail"]) == (422, NUR_VON_BIS)
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, row.id).hours == Decimal("4")
    # mit Von/Bis neu gerechnet; nur die Notiz geht ohne Zeiten
    assert client.put(f"/api/time-entries/{row.id}", json={"von": "07:00", "bis": "13:00"}).status_code == 200
    assert client.put(f"/api/time-entries/{row.id}", json={"notes": "Rinne"}).status_code == 200
    welt["db"].expire_all()
    neu = welt["db"].get(TimeEntry, row.id)
    assert (neu.hours, neu.notes, neu.started_at.time(), neu.ended_at.time()) == (Decimal("6"), "Rinne", time(7), time(13))


def test_aendern_mit_stunden_als_buero_wie_bisher(welt):  # noqa: F811
    row = create_manual_entry(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=welt["heute"], hours=Decimal("4"))
    r = _buero(welt).put(f"/api/time-entries/{row.id}", json={"hours": 6})
    assert r.status_code == 200, r.text
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, row.id).hours == Decimal("6")


def test_einsatzbericht_zeigt_der_monteurin_von_und_bis(welt):  # noqa: F811
    def seite(rolle):
        text = welt["client"](welt["db"], pages_router.router, role=rolle).get(f"/orders/{welt['order'].id}/service-reports").text
        return {name: bool(re.search(rf'id="{name}"[^>]* hidden', text)) for name in ("teHoursField", "teVonField", "teBisField")}
    assert seite("field") == {"teHoursField": True, "teVonField": False, "teBisField": False}
    assert seite("buero_auftrag") == {"teHoursField": False, "teVonField": True, "teBisField": True}
