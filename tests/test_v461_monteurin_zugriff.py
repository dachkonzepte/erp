"""Seit 1.9.33 (Stufe 4, R1, Punkt 1): die heutigen Einsätze und der Feierabend nur für die Rollen der Monteursansicht.

    today          GET /api/field-view/today: Rollen aus app/permissions.py::MOBIL_ROLLEN (heute nur die Monteurin) 200, jede andere 403 --
                   vor der Feierabend-Uhrzeit geprüft
    Feierabend     das Büro wird auf /mobil nach 19 Uhr nicht mehr abgemeldet: der GET meldet ihm nie "feierabend", der POST lehnt es ab
                   (bis 1.9.32 meldete der GET jeder Rolle ab 19 Uhr "feierabend", /mobil beendete dann die Sitzung -- Befund Stufe 4)

Über die echte Anmeldeschranke (tests/anmeldung.py, Welt aus tests/test_v408_vorweg.py).
"""

from datetime import datetime, timedelta

import pytest

from app.models import AppUser, Employee
from app.permissions import MOBIL_ROLLEN, NUR_MONTEURSANSICHT, ROLE_FIELD
from app.routers import field_view as field_view_router
from tests.test_v402_sitzungen import _status, _wert
from tests.test_v408_vorweg import WeltMitMobil, neue_datenbank


@pytest.fixture
def welt():
    engine, make_session = neue_datenbank()
    yield WeltMitMobil(make_session)
    engine.dispose()


def _mit_mitarbeiter(welt, user: AppUser) -> None:
    with welt.make_session() as db:
        emp = Employee(first_name=user.username.title(), last_name="Test", active=True)
        db.add(emp)
        db.flush()
        db.get(AppUser, user.id).employee_id = emp.id
        db.commit()


def _uhr(monkeypatch, stunde: int) -> None:
    jetzt = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=stunde)
    monkeypatch.setattr(field_view_router, "_now", lambda: jetzt)


def test_rollen_der_monteursansicht():
    assert MOBIL_ROLLEN == frozenset({ROLE_FIELD})


@pytest.mark.parametrize("rolle", ["buero_auftrag", "buero_finanzen", "admin"])
def test_buero_bekommt_heute_403(welt, monkeypatch, rolle):
    """Angriff: jede Rolle außerhalb der Monteursansicht -- 403 mit lesbarer Meldung, auch mit verknüpftem Mitarbeiter."""
    _uhr(monkeypatch, 10)
    user = welt.benutzer("bea", rolle, zweiter_faktor=rolle == "admin")
    _mit_mitarbeiter(welt, user)
    geraet = welt.als(user)
    antwort = geraet.get("/api/field-view/today")
    assert (antwort.status_code, antwort.json()["detail"]) == (403, NUR_MONTEURSANSICHT)


def test_monteurin_bekommt_heute_200(welt, monkeypatch):
    """Gegenprobe: die Monteurin mit Mitarbeiter bekommt ihre Einsätze."""
    _uhr(monkeypatch, 10)
    mia = welt.benutzer("mia", "field")
    _mit_mitarbeiter(welt, mia)
    antwort = welt.angemeldet("mia").get("/api/field-view/today")
    assert antwort.status_code == 200
    assert set(antwort.json()) >= {"assignments", "draft_reports"}


def test_buero_wird_nach_feierabend_nicht_abgemeldet(welt, monkeypatch):
    """Angriff: das Büro öffnet /mobil um 20 Uhr -- der GET meldet kein "feierabend" (403), der POST beendet keine Sitzung (403), die
    Sitzung gilt weiter."""
    _uhr(monkeypatch, 20)
    bea = welt.benutzer("bea", "buero_auftrag")
    _mit_mitarbeiter(welt, bea)
    geraet = welt.angemeldet("bea")
    antwort = geraet.get("/api/field-view/today")
    assert antwort.status_code == 403 and "feierabend" not in antwort.json()
    assert geraet.post("/api/field-view/feierabend").status_code == 403
    assert _status(welt, _wert(geraet)) == 200
    assert welt.sitzungen_von(bea) == 1


def test_monteurin_wird_nach_feierabend_weiter_abgemeldet(welt, monkeypatch):
    """Gegenprobe: für die Monteurin bleibt der Feierabend, wie er war (401 "feierabend", POST beendet die Sitzung)."""
    _uhr(monkeypatch, 20)
    mia = welt.benutzer("mia", "field")
    _mit_mitarbeiter(welt, mia)
    geraet = welt.angemeldet("mia")
    antwort = geraet.get("/api/field-view/today")
    assert antwort.status_code == 401 and antwort.json()["feierabend"] is True
    assert geraet.post("/api/field-view/feierabend").status_code == 200
    assert welt.sitzungen_von(mia) == 0
