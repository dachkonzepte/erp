"""Version 1.9.105 (Stufe 4, R5b Nachrunde, Punkt 6, Festlegungen): Arbeitstage am Antrag und „Abschluss aufheben“.

    Arbeitstage       Montag bis Freitag ohne die gesetzlichen Feiertage in NRW (app/planning.py::automatic_public_holidays("NW")) -- bis
                      1.9.104 ohne Feiertage; nur Anzeige, nirgends gespeichert oder verrechnet
    Abschluss         „Abschluss aufheben“ nur auf ein früheres Monatsende, nicht ganz -- PUT /api/time-backoffice/lock mit None oder einem
                      anderen Tag beim Zurücknehmen 422, auch für den Admin (bis 1.9.104 erlaubt); vorrücken unverändert
"""

from datetime import date

import pytest

from app.models import EmployeeAbsenceRequest, TimeTrackingSettings
from app.routers import time_backoffice as time_backoffice_router
from app.routers import zeiten as zeiten_router
from app.routers.time_backoffice import ABSCHLUSS_NICHT_GANZ, NUR_AUF_MONATSENDE
from app.zeiten import arbeitstage
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)
from tests.test_v518_zeiten_seite import _funktion, _skript


@pytest.mark.parametrize("von, bis, tage", [
    (date(2026, 12, 21), date(2027, 1, 1), 8),     # 25.12. und 1.1. sind Freitage; 24.12., 31.12. Arbeitstage, 26.12. ein Samstag
    (date(2027, 3, 22), date(2027, 4, 2), 8),      # Karfreitag 26.03., Ostermontag 29.03.2027
    (date(2027, 5, 24), date(2027, 5, 28), 4),     # Fronleichnam 27.05.2027 (in NRW Feiertag)
    (date(2027, 11, 1), date(2027, 11, 5), 4),     # Allerheiligen 01.11.2027 (in NRW Feiertag)
    (date(2026, 11, 16), date(2026, 11, 20), 5),   # Buß- und Bettag 18.11.2026 -- nur in Sachsen, in NRW ein Arbeitstag
    (date(2026, 11, 2), date(2026, 11, 6), 5),
    (date(2026, 10, 3), date(2026, 10, 4), 0),     # Tag der Deutschen Einheit 2026 ist ein Samstag
])
def test_arbeitstage_ohne_feiertage_nrw(von, bis, tage):
    assert arbeitstage(von, bis) == tage


def test_antrag_ueber_weihnachten_acht_arbeitstage(welt):  # noqa: F811
    """Angriff (bis 1.9.104: 10): Urlaub Mo 21.12.2026–Fr 01.01.2027 heißt am Antrag 8 Arbeitstage."""
    db = welt["db"]
    db.add(EmployeeAbsenceRequest(employee_id=welt["tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 12, 21),
                                  end_date=date(2027, 1, 1), status="pending"))
    db.commit()
    client = welt["client"](db, zeiten_router.router, role="admin")
    assert [a["arbeitstage"] for a in client.get("/api/zeiten/abwesenheiten").json()["antraege"]] == [8]
    assert [a["arbeitstage"] for a in client.get("/api/zeiten/pruefen").json()["antraege"]] == [8]


def _lock(w, rolle, bis):
    client = w["client"](w["db"], time_backoffice_router.router, role=rolle)
    return client.put("/api/time-backoffice/lock", json={"locked_until": bis.isoformat() if bis else None})


def _abgeschlossen_bis(w):
    w["db"].expire_all()
    return w["db"].get(TimeTrackingSettings, 1).locked_until


def test_abschluss_aufheben_nur_auf_ein_frueheres_monatsende(welt):  # noqa: F811
    """Angriff: der Admin hebt den Abschluss ganz auf -> 422, auf einen Tag mitten im Monat -> 422, nichts geändert (bis 1.9.104 je 200).
    Gegenprobe: auf das Monatsende davor 200; vorrücken auf jeden Tag wie bisher; Büro – Finanzen weiter 403 (vor der Prüfung des Tags)."""
    db = welt["db"]
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 9, 30)
    db.commit()
    ganz = _lock(welt, "admin", None)
    assert (ganz.status_code, ganz.json().get("detail")) == (422, ABSCHLUSS_NICHT_GANZ)
    mitten = _lock(welt, "admin", date(2026, 9, 15))
    assert (mitten.status_code, mitten.json().get("detail")) == (422, NUR_AUF_MONATSENDE)
    assert _abgeschlossen_bis(welt) == date(2026, 9, 30)
    assert _lock(welt, "buero_finanzen", None).status_code == 403
    assert _lock(welt, "buero_finanzen", date(2026, 8, 31)).status_code == 403
    assert _lock(welt, "admin", date(2026, 8, 31)).status_code == 200 and _abgeschlossen_bis(welt) == date(2026, 8, 31)
    assert _lock(welt, "admin", date(2026, 2, 28)).status_code == 200 and _abgeschlossen_bis(welt) == date(2026, 2, 28)
    assert _lock(welt, "buero_finanzen", date(2026, 3, 10)).status_code == 200  # vorrücken auf einen Tag mitten im Monat wie bisher


def test_dialog_ohne_ganz_aufheben():
    """Der Dialog „Abschluss aufheben“ bietet nur die zwölf Monatsenden davor (bis 1.9.104 dazu „nichts – Abschluss ganz aufheben“) und schickt nie
    None."""
    text = _skript()
    assert "label:'nichts" not in text
    oeffnen, aufheben = _funktion(text, "aufhebenOeffnen"), _funktion(text, "aufheben")
    assert "optionen.push({value:''" not in oeffnen and "for(var i=0;m&&i<12;i++)" in oeffnen
    assert "if(!bis)return;" in aufheben and "||null" not in aufheben
