"""Version 1.9.178 (L1a-Nachtrag, Punkt 5, Vorgabe Tobias 03.11.2026): Schlechtwetter an einem von Hand eingetragenen betriebsfreien Tag.

Keine stille Annahme mehr (Festlegung 1.9.170 Nr. 7 neu gefasst): der Server fragt wie bei gebuchter Zeit -- 409 mit Warnung, nichts gespeichert,
„Trotzdem eintragen“ (trotzdem) trägt ein. Ein gesetzlicher Feiertag bleibt abgelehnt (422). Fester Tag: Mo 07.12.2026.
"""

from datetime import date, datetime, time
from decimal import Decimal

from app.models import EmployeeAbsence, EmployeeAbsenceRequest, PlanningHoliday, TimeEntry
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v588_schlechtwetter import MO, _als, _eintragen, welt  # noqa: F401  (Fixture)

FREI = "Der 07.12.2026 ist als betriebsfreier Tag eingetragen (Betriebsausflug)"


def _frei(db, aktiv=True):
    db.add(PlanningHoliday(holiday_date=MO, name="Betriebsausflug", active=aktiv))
    db.commit()


def _anzahl(w):
    w["db"].expire_all()
    return w["db"].query(EmployeeAbsenceRequest).count(), w["db"].query(EmployeeAbsence).count()


def test_betriebsfreier_tag_fragt_nach(welt):  # noqa: F811
    _frei(welt["db"])
    client = _als(welt)
    r = _eintragen(client, welt["mia"], welt["tom"])
    assert r.status_code == 409
    assert r.json() == {"detail": FREI + ".", "warnungen": [{"employee_id": None, "art": "betriebsfrei", "text": FREI}]}
    assert _anzahl(welt) == (0, 0)
    r = _eintragen(client, welt["mia"], welt["tom"], trotzdem=True)
    assert (r.status_code, r.json()["genehmigt"]) == (200, True) and _anzahl(welt) == (2, 2)


def test_abgeschalteter_betriebsfreier_tag_fragt_nicht(welt):  # noqa: F811
    _frei(welt["db"], aktiv=False)
    assert _eintragen(_als(welt), welt["mia"]).status_code == 200


def test_betriebsfrei_und_gebucht_in_einer_meldung(welt):  # noqa: F811
    db = welt["db"]
    _frei(db)
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0594"))
    db.add(TimeEntry(employee_id=welt["mia"].id, project_id=order.project_id, order_id=order.id, work_date=MO, entry_type="site",
                     hours=Decimal("3.5"), break_minutes=0, status="booked", started_at=datetime.combine(MO, time(7)),
                     ended_at=datetime.combine(MO, time(10, 30))))
    r = _eintragen(_als(welt), welt["mia"])
    assert r.status_code == 409
    assert r.json()["detail"] == FREI + ". Außerdem ist schon Zeit gebucht: Mia Monteurin 3,50 h gebucht."
    assert [w["art"] for w in r.json()["warnungen"]] == ["betriebsfrei", "gebucht"]


def test_die_monteurin_wird_gefragt(welt):  # noqa: F811
    _frei(welt["db"])
    client = _als(welt, "field", "uwe")
    assert _eintragen(client, welt["uwe"]).status_code == 409
    r = _eintragen(client, welt["uwe"], trotzdem=True)
    assert (r.status_code, r.json()["genehmigt"]) == (200, False)  # ein Antrag für sich


def test_gesetzlicher_feiertag_bleibt_abgelehnt(welt):  # noqa: F811
    r = _eintragen(_als(welt), welt["mia"], tag=date(2026, 12, 25), trotzdem=True)
    assert r.status_code == 422 and "Feiertag" in r.json()["detail"]
