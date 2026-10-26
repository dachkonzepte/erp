"""Version 1.9.91 (Stufe 4, R5a, Punkt 4): Abschließen nur ohne laufende Zeiten und ohne Tage mit unpassender Pause bis zum Datum.

    sperrt       jede laufende Zeit mit Tag bis zum Datum (auch eine seit früher offene), jeder Tag mit unpassender Pause (pausen_vorschau():
                 neu rechnen würde etwas ändern) ab dem Tag nach dem bisherigen Abschluss, ohne bisherigen Abschluss im Monat des Datums --
                 409 mit Meldung und Liste, nichts gespeichert; auch für den Admin
    sperrt nicht Personalnummer, Lohnart, Berater- und Mandantennummer (sie sperren den DATEV-Export, 1.9.92); Zurücknehmen (Admin)
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest

from app.models import TimeTrackingSettings
from app.routers import time_backoffice as time_backoffice_router
from app.routers import time_tracking as time_tracking_router
from app.time_tracking import create_manual_entry, delete_entry, start_timer, stop_timer
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)


def _als(w, rolle="buero_finanzen"):
    return w["client"](w["db"], time_backoffice_router.router, time_tracking_router.router, role=rolle)


def _abschliessen(w, tag, rolle="buero_finanzen"):
    return _als(w, rolle).put("/api/time-backoffice/lock", json={"locked_until": tag.isoformat() if tag else None})


def _abgeschlossen_bis(w):
    w["db"].expire_all()
    return w["db"].get(TimeTrackingSettings, 1).locked_until


def _zeit(w, emp, von, bis, tag):
    row = start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis))


def _pause_passt_nicht(w, emp, tag):
    """07:00–12:00 und 12:00–16:15 (45 min bei der zweiten), die erste gelöscht -- abgezogen 45, nach Zeitregel 0."""
    erste = _zeit(w, emp, time(7), time(12), tag)
    zweite = _zeit(w, emp, time(12), time(16, 15), tag)
    delete_entry(w["db"], erste.id)
    return zweite


@pytest.mark.parametrize("rolle", ["buero_finanzen", "admin"])
def test_laufende_zeit_sperrt_den_abschluss(welt, rolle):  # noqa: F811
    """Angriff: Toms Zeit läuft seit gestern 06:45 -- Abschluss bis gestern 409 mit Liste, nichts gespeichert (auch der Admin). Gegenprobe:
    Ende nachgetragen -> abgeschlossen."""
    row = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id,
                      started_at=datetime.combine(welt["gestern"], time(6, 45)))
    antwort = _abschliessen(welt, welt["gestern"], rolle)
    assert antwort.status_code == 409, antwort.text
    text = f"Tom Monteur: Zeit läuft seit {welt['gestern']:%d.%m.%Y}, 06:45"
    assert antwort.json() == {"detail": f"Abschließen geht noch nicht: 1 Zeit läuft noch – {text}.",
                              "liste": [{"art": "laeuft", "employee_id": welt["tom"].id, "name": "Tom Monteur",
                                         "tag": welt["gestern"].isoformat(), "entry_id": row.id, "text": text}]}
    assert _abgeschlossen_bis(welt) is None
    assert _als(welt, "admin").post(f"/api/time-entries/{row.id}/ende-nachtragen",
                                    json={"ende": f"{welt['gestern'].isoformat()}T16:00", "pause_minuten": 0}).status_code == 200
    assert _abschliessen(welt, welt["gestern"], rolle).status_code == 200
    assert _abgeschlossen_bis(welt) == welt["gestern"]


def test_heute_laufende_zeit_sperrt_nur_einen_abschluss_bis_heute(welt):  # noqa: F811
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    assert _abschliessen(welt, welt["heute"]).status_code == 409
    assert _abschliessen(welt, welt["gestern"]).status_code == 200


def test_unpassende_pause_sperrt_den_abschluss(welt):  # noqa: F811
    """Angriff: Mias Tag gestern passt nicht (abgezogen 45, nach Zeitregel 0) -> 409 mit dem Tag. Gegenprobe: Pausen neu gerechnet -> 200."""
    zweite = _pause_passt_nicht(welt, welt["mia"], welt["gestern"])
    antwort = _abschliessen(welt, welt["gestern"])
    assert antwort.status_code == 409
    eintrag = antwort.json()["liste"]
    assert [(x["art"], x["name"], x["tag"]) for x in eintrag] == [("pause", "Mia Monteurin", welt["gestern"].isoformat())]
    assert eintrag[0]["text"] == f"Mia Monteurin, {welt['gestern']:%d.%m.%Y}: Pause abgezogen 45 min, nach Zeitregel 0 min"
    assert "1 Tag mit unpassender Pause" in antwort.json()["detail"]
    assert _als(welt).post("/api/time-entries/pausen-neu-rechnen", json={"work_date": welt["gestern"].isoformat(), "employee_id": welt["mia"].id,
                                                                     "buchungen": [{"id": zweite.id, "pause": 0}]}).status_code == 200
    assert _abschliessen(welt, welt["gestern"]).status_code == 200


def test_beides_in_einer_liste(welt):  # noqa: F811
    _pause_passt_nicht(welt, welt["mia"], welt["gestern"])
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(6, 45)))
    antwort = _abschliessen(welt, welt["gestern"])
    assert [x["art"] for x in antwort.json()["liste"]] == ["laeuft", "pause"]
    assert antwort.json()["detail"].startswith("Abschließen geht noch nicht: 1 Zeit läuft noch, 1 Tag mit unpassender Pause – ")


def test_personalnummer_lohnart_datev_nummern_sperren_nicht(welt):  # noqa: F811
    """Gegenprobe: Buchungen ohne Personalnummer, ohne Lohnart, ohne Berater- und Mandantennummer -- der Abschluss geht."""
    create_manual_entry(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=welt["gestern"], hours=Decimal("4"))
    s = welt["db"].get(TimeTrackingSettings, 1)
    s.datev_wage_type_site = s.datev_wage_type_other = None
    welt["db"].commit()
    assert _abschliessen(welt, welt["gestern"]).status_code == 200


def test_nur_ab_dem_bisherigen_abschluss(welt):  # noqa: F811
    """Ein Tag mit unpassender Pause vor dem bisherigen Abschluss sperrt das Vorrücken nicht (er ist abgerechnet); einer danach schon."""
    vorgestern = welt["gestern"] - timedelta(days=1)
    _pause_passt_nicht(welt, welt["mia"], vorgestern)
    welt["db"].get(TimeTrackingSettings, 1).locked_until = vorgestern
    welt["db"].commit()
    assert _abschliessen(welt, welt["gestern"]).status_code == 200
    _pause_passt_nicht(welt, welt["tom"], welt["heute"])
    assert _abschliessen(welt, welt["heute"]).status_code == 409


def test_ohne_bisherigen_abschluss_der_monat_des_datums(welt):  # noqa: F811
    """Ohne bisherigen Abschluss prüft der erste Abschluss den Monat des Datums -- ein Tag im Vormonat sperrt nicht (Altbestand vor der
    Pausenregel je Tag, 1.9.48), einer im Monat schon."""
    vormonat = welt["heute"].replace(day=1) - timedelta(days=3)
    _pause_passt_nicht(welt, welt["mia"], vormonat)
    assert _abschliessen(welt, welt["heute"]).status_code == 200
    welt["db"].get(TimeTrackingSettings, 1).locked_until = None
    welt["db"].commit()
    _pause_passt_nicht(welt, welt["tom"], welt["heute"].replace(day=1))
    assert _abschliessen(welt, welt["heute"]).status_code == 409


def test_zuruecknehmen_wird_nicht_geprueft(welt):  # noqa: F811
    """Der Admin nimmt einen Abschluss zurück -- auch mit laufender Zeit davor; geprüft wird nur das Vorrücken."""
    welt["db"].get(TimeTrackingSettings, 1).locked_until = welt["gestern"]
    welt["db"].commit()
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id,
                started_at=datetime.combine(welt["gestern"] - timedelta(days=2), time(7)))
    assert _abschliessen(welt, welt["gestern"] - timedelta(days=5), "admin").status_code == 200
    assert _abschliessen(welt, None, "admin").status_code == 200
