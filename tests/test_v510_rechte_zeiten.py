"""Version 1.9.89 (Stufe 4, R5a, Punkt 1, Entscheidungen Tobias): die Rechte an den Zeiten -- eine Regel je Recht in app/permissions.py.

    Zeiten anderer  buchen, starten, stoppen, ändern, löschen, „Ende nachtragen“, „Pausen neu rechnen“, Kolonne: Admin und Büro – Finanzen
                    (darf_zeit_fuer_andere_buchen(), bis 1.9.88 nur Admin); im abgeschlossenen Zeitraum weiter nur der Admin
    Büro – Auftrag  liest die Zeiten aller (Liste, laufende Zeit, Pause des Tags, Kontext) und ändert nichts, auch keine eigenen -- 403 mit
                    ZEITEN_NUR_LESEN, in der Datenbank ändert sich nichts (darf_zeit_buchen(), require_zeit_buchen)
    Lohndaten       Stundenzettel aller, Stundendaten als CSV, DATEV-Export, Abschließen: Admin und Büro – Finanzen (darf_lohndaten(),
                    require_lohndaten); einen Abschluss aufheben nur der Admin; die Übersicht liest jedes Büro
    Schlüssel       Büro – Auftrag bekommt in keiner Antwort eines GET-Endpunkts einen Lohnsatz (Rundgang aus test_v326; Gegenprobe: als
                    Büro – Finanzen findet derselbe Rundgang sie)
"""

import re
from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AppUser, TimeEntry, TimeEntryGroup
from app.permissions import (
    NUR_LOHNDATEN, ZEITEN_NUR_LESEN, darf_lohndaten, darf_zeit_buchen, darf_zeit_fuer_andere_buchen,
)
from app.routers import time_backoffice as time_backoffice_router
from app.routers import time_tracking as time_tracking_router
from app.time_backoffice import set_time_lock
from app.time_tracking import create_manual_entry, delete_entry, start_timer, stop_timer
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)
from tests.uhr import uhr_festhalten


def _als(w, rolle, emp=None):
    return w["client"](w["db"], time_tracking_router.router, time_backoffice_router.router, role=rolle,
                       employee_id=emp.id if emp is not None else None)


def _anzahl(w):
    w["db"].expire_all()
    return w["db"].scalar(select(func.count()).select_from(TimeEntry))


def _zeit(w, emp, von, bis, tag=None):
    tag = tag or w["heute"]
    row = start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis))


# --- die Regeln ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle, andere, buchen, lohn", [
    ("admin", True, True, True), ("buero_finanzen", True, True, True), ("buero_auftrag", False, False, False),
    ("field", False, True, False),
])
def test_regeln_je_rolle(rolle, andere, buchen, lohn):
    konto = AppUser(username="x", role=rolle)
    assert (darf_zeit_fuer_andere_buchen(konto), darf_zeit_buchen(konto), darf_lohndaten(konto)) == (andere, buchen, lohn)


# --- Zeiten anderer: Büro – Finanzen ja, Büro – Auftrag nein -------------------------------------------------------------------------

def _nachtrag(client, w, emp, **werte):
    return client.post("/api/time-entries", json={"employee_id": emp.id, "order_id": w["order"].id,
                                                  "work_date": w["heute"].isoformat(), **(werte or {"hours": "2"})})


def test_finanzen_bucht_aendert_und_loescht_fuer_andere(welt):  # noqa: F811
    """Gegenprobe: Büro – Finanzen ohne eigenen Mitarbeiter trägt für Tom nach, ändert und löscht."""
    client = _als(welt, "buero_finanzen")
    neu = _nachtrag(client, welt, welt["tom"])
    assert neu.status_code == 200, neu.text
    assert neu.json()["employee_id"] == welt["tom"].id
    assert Decimal(client.put(f"/api/time-entries/{neu.json()['id']}", json={"hours": "3"}).json()["hours"]) == Decimal("3")
    assert client.delete(f"/api/time-entries/{neu.json()['id']}").status_code == 200
    assert _anzahl(welt) == 0


def test_buero_auftrag_bucht_nichts_auch_nicht_fuer_sich(welt):  # noqa: F811
    """Angriff: Büro – Auftrag (mit eigenem Mitarbeiter Mia) -- Nachtrag für Tom und für sich, Ändern, Löschen, Start: je 403 mit der
    Meldung, nichts geändert. Bis 1.9.88 buchte es für sich (eigene offene Zeit 200)."""
    eigene = create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=welt["heute"],
                                 hours=Decimal("2"))
    client = _als(welt, "buero_auftrag", welt["mia"])
    vorher = _anzahl(welt)
    antworten = [
        _nachtrag(client, welt, welt["tom"]), _nachtrag(client, welt, welt["mia"]),
        client.put(f"/api/time-entries/{eigene.id}", json={"hours": "3"}),
        client.delete(f"/api/time-entries/{eigene.id}"),
        client.post("/api/time-entries/start", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id}),
        client.post("/api/time-entry-groups", json={"employee_ids": [welt["mia"].id, welt["tom"].id], "team_id": welt["team"].id,
                                                    "order_id": welt["order"].id, "work_date": welt["heute"].isoformat(), "hours": "2"}),
        client.get("/api/time-entries/nachtrag-vorschau", params={"work_date": welt["heute"].isoformat(), "von": "07:00", "bis": "09:00"}),
    ]
    assert [(a.status_code, a.json()["detail"]) for a in antworten] == [(403, ZEITEN_NUR_LESEN)] * len(antworten)
    assert _anzahl(welt) == vorher
    assert welt["db"].get(TimeEntry, eigene.id).hours == Decimal("2")


def test_finanzen_startet_und_stoppt_fuer_andere(welt):  # noqa: F811
    client = _als(welt, "buero_finanzen")
    heute = welt["heute"].isoformat()
    start = client.post("/api/time-entries/start", json={"employee_id": welt["tom"].id, "order_id": welt["order"].id,
                                                         "started_at": f"{heute}T07:00:00"})
    assert start.status_code == 200, start.text
    assert client.get("/api/time-entries/active", params={"employee_id": welt["tom"].id}).json()["id"] == start.json()["id"]
    stopp = client.post(f"/api/time-entries/{start.json()['id']}/stop", json={"ended_at": f"{heute}T09:00:00"})
    assert (stopp.status_code, stopp.json().get("status")) == (200, "booked"), stopp.text


def test_finanzen_bucht_fuer_die_kolonne_ohne_mitglied_zu_sein(welt):  # noqa: F811
    """Wie bis dahin nur der Admin: für Mitglieder eines Teams buchen, ohne selbst darin zu sein (_group_actor())."""
    client = _als(welt, "buero_finanzen")
    antwort = client.post("/api/time-entry-groups", json={"employee_ids": [welt["mia"].id, welt["tom"].id], "team_id": welt["team"].id,
                                                          "order_id": welt["order"].id, "work_date": welt["heute"].isoformat(), "hours": "2"})
    assert antwort.status_code == 200, antwort.text
    gruppe = welt["db"].get(TimeEntryGroup, antwort.json()["id"])
    assert client.delete(f"/api/time-entry-groups/{gruppe.id}").status_code == 200


@pytest.mark.parametrize("rolle, status", [("buero_finanzen", 200), ("buero_auftrag", 403)])
def test_ende_nachtragen_fuer_andere(welt, rolle, status):  # noqa: F811
    row = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id,
                      started_at=datetime.combine(welt["gestern"], time(6, 45)))
    antwort = _als(welt, rolle).post(f"/api/time-entries/{row.id}/ende-nachtragen",
                                     json={"ende": f"{welt['gestern'].isoformat()}T16:00", "pause_minuten": 0})
    assert antwort.status_code == status, antwort.text
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, row.id).status == ("booked" if status == 200 else "running")


@pytest.mark.parametrize("rolle, status", [("buero_finanzen", 200), ("buero_auftrag", 403)])
def test_pausen_neu_rechnen_fuer_andere(welt, rolle, status):  # noqa: F811
    """Toms Tag: 07:00–12:00 und 12:00–16:15 (45 min), die erste gelöscht -- die Pause passt nicht mehr. Büro – Finanzen rechnet sie neu,
    Büro – Auftrag liest sie (tagespause) und rechnet nichts."""
    erste = _zeit(welt, welt["tom"], time(7), time(12))
    zweite = _zeit(welt, welt["tom"], time(12), time(16, 15))
    delete_entry(welt["db"], erste.id)
    client = _als(welt, rolle)
    tag = client.get("/api/time-entries/tagespause", params={"work_date": welt["heute"].isoformat(), "employee_id": welt["tom"].id})
    assert (tag.status_code, tag.json()["passt"]) == (200, False)
    antwort = client.post("/api/time-entries/pausen-neu-rechnen", json={"work_date": welt["heute"].isoformat(), "employee_id": welt["tom"].id,
                                                                        "buchungen": [{"id": zweite.id, "pause": 0}]})
    assert antwort.status_code == status, antwort.text
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, zweite.id).break_minutes == (0 if status == 200 else 45)


def test_im_abgeschlossenen_zeitraum_nur_der_admin(welt):  # noqa: F811
    """Büro – Finanzen ändert eine fremde Zeit im abgeschlossenen Zeitraum nicht (403), der Admin schon."""
    row = create_manual_entry(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=welt["gestern"], hours=Decimal("2"))
    set_time_lock(welt["db"], welt["gestern"], user_id=None)
    antwort = _als(welt, "buero_finanzen").put(f"/api/time-entries/{row.id}", json={"hours": "3"})
    assert antwort.status_code == 403 and "abgeschlossen" in antwort.json()["detail"]
    assert _als(welt, "admin").put(f"/api/time-entries/{row.id}", json={"hours": "3"}).status_code == 200


def test_buero_auftrag_liest_die_zeiten_aller(welt):  # noqa: F811
    """Liste, laufende Zeit und Kontext jeder Person -- auch ohne eigenen Mitarbeiter (der Kontext bis 1.9.88 403)."""
    row = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    client = _als(welt, "buero_auftrag")
    assert [e["id"] for e in client.get("/api/time-entries", params={"employee_id": welt["tom"].id}).json()] == [row.id]
    assert client.get("/api/time-entries/active", params={"employee_id": welt["tom"].id}).json()["id"] == row.id
    kontext = client.get("/api/time-tracking/context", params={"employee_id": welt["tom"].id}).json()
    assert (kontext["current_employee_id"], kontext["zeit_buchen"], kontext["zeit_fuer_andere"]) == (welt["tom"].id, False, False)
    assert {e["id"] for e in kontext["employees"]} >= {welt["mia"].id, welt["tom"].id}


# --- Lohndaten -------------------------------------------------------------------------------------------------------------------

LOHNDATEN = ["/api/time-backoffice/timesheet.pdf", "/api/time-backoffice/timesheet.csv", "/api/time-backoffice/datev-export"]


@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen", "buero_auftrag"])
def test_lohndaten_nur_admin_und_finanzen(welt, rolle):  # noqa: F811
    """Angriff Büro – Auftrag: Stundenzettel aller als PDF, CSV, DATEV-Export, Abschließen -- je 403 mit der Meldung, kein Abschluss.
    Gegenprobe Admin und Büro – Finanzen: je 200. Die Übersicht (Stunden je Mitarbeiter) liest jedes Büro."""
    create_manual_entry(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=welt["gestern"], hours=Decimal("2"))
    client = _als(welt, rolle)
    zeitraum = {"start_date": (welt["heute"] - timedelta(days=30)).isoformat(), "end_date": welt["heute"].isoformat()}
    antworten = [client.get(pfad, params=zeitraum) for pfad in LOHNDATEN]
    antworten.append(client.put("/api/time-backoffice/lock", json={"locked_until": welt["gestern"].isoformat()}))
    if rolle == "buero_auftrag":
        assert [(a.status_code, a.json()["detail"]) for a in antworten] == [(403, NUR_LOHNDATEN)] * 4
        assert client.get("/api/time-backoffice/settings").json()["locked_until"] is None
    else:
        # seit 1.9.92 lehnt der DATEV-Export den nicht abgeschlossenen Zeitraum ab (409, nicht 403 -- die Rolle darf)
        assert [a.status_code for a in antworten] == [200, 200, 409, 200]
        assert antworten[0].content.startswith(b"%PDF")
        assert "nur für abgeschlossene Zeiträume" in antworten[2].json()["detail"]
    assert client.get("/api/time-backoffice/summary", params=zeitraum).status_code == 200


def test_abschluss_aufheben_nur_der_admin(welt):  # noqa: F811
    set_time_lock(welt["db"], welt["gestern"], user_id=None)
    assert _als(welt, "buero_finanzen").put("/api/time-backoffice/lock", json={"locked_until": None}).status_code == 403
    assert _als(welt, "admin").put("/api/time-backoffice/lock", json={"locked_until": None}).status_code == 200


# --- Schlüssel: Büro – Auftrag bekommt keine Lohnsätze ---------------------------------------------------------------------------

# Ein Lohnsatz: Stundenlohn, Gehalt, Vergütung (und ihre Art). Die DATEV-Lohnart (datev_wage_type_*) ist ein Buchungsschlüssel, kein Betrag.
LOHNSATZ = re.compile(r"wage(?!_type)|salary|gehalt|stundenlohn|lohnsatz|verguetung|compensation")


def _lohnsaetze(antworten) -> set[str]:
    from tests.test_v326_monteur_datengrenze import _schluessel
    return {f"{a['route']}  {pfad}.{key}" for a in antworten if a["body"] is not None
            for pfad, key in _schluessel(a["body"]) if LOHNSATZ.search(key.lower())}


@pytest.fixture(scope="module")
def rundgaenge():
    """Der Rundgang aus test_v326 (jeder GET-Endpunkt unter /api/, Testdaten der Büro-Welt) als Büro – Auftrag und als Büro – Finanzen."""
    from tests.test_v326_monteur_datengrenze import _buero_welt, _durchlauf, _routers_in_betriebsreihenfolge
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        with uhr_festhalten():
            welt = _buero_welt(db)
            konten = {}
            for rolle in ("buero_auftrag", "buero_finanzen"):
                konto = AppUser(username=rolle, password_hash="x", display_name=rolle, role=rolle, active=True)
                db.add(konto)
                db.commit()
                konten[rolle] = konto.id
            routers = _routers_in_betriebsreihenfolge()
            yield {rolle: _durchlauf(db, welt, routers, user_id=konto_id) for rolle, konto_id in konten.items()}
    finally:
        db.close()
        engine.dispose()


def test_buero_auftrag_bekommt_keine_lohnsaetze(rundgaenge):
    antworten = rundgaenge["buero_auftrag"]["antworten"]
    assert sum(1 for a in antworten if a["status"] == 200) > 100  # der Rundgang hat Inhalt gelesen
    assert _lohnsaetze(antworten) == set()


def test_gegenprobe_finanzen_bekommt_lohnsaetze(rundgaenge):
    """Derselbe Rundgang als Büro – Finanzen findet die Vergütung am Mitarbeiter -- der Scan sieht sie, wo sie steht."""
    gefunden = _lohnsaetze(rundgaenge["buero_finanzen"]["antworten"])
    assert any(z.startswith("/api/employees  ") and z.endswith(".hourly_wage") for z in gefunden), sorted(gefunden)[:20]
