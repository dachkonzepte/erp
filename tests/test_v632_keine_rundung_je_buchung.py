"""Version 1.9.231 (Stufe 6, R3a, Punkt 0b, Festlegung 1.9.223 Nr. 6): die Rundung je Buchung entfällt, gerundet wird nur die Arbeit eines Tags
im Lohn (arbeit_des_tags(), 0,25 h).

    Buchungen     jede neue Buchung bleibt minutengenau -- auch mit der alten Spalte rounding_minutes auf 15 (Wege: tests/test_v466_rundung_gruppen.py)
    Zeitregeln    keine Einstellung „Rundung“ mehr: nicht in der Antwort, ein mitgeschickter Wert wird nicht übernommen, die Seite hat keine Auswahl
    Lohn          der Tag wird weiter auf 0,25 h gerundet (unverändert seit 1.9.223)
    Texte         keine Seite sagt mehr „Pause und Rundung je Person“
"""

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from app.models import TimeEntry, TimeTrackingSettings
from app.routers import time_backoffice as backoffice_router
from app.time_tracking import arbeit_des_tags, dauer_vorschau, gebucht_nach_zeitregel, kolonne_rechnen
from tests.test_v224_field_view import make_employee

ROOT = Path(__file__).resolve().parent.parent


def _rundung_alt(db, minuten=15):
    db.get(TimeTrackingSettings, 1).rounding_minutes = minuten
    db.commit()


def test_gebucht_bleibt_minutengenau(threaded_db_session):
    db = threaded_db_session
    _rundung_alt(db)
    assert [gebucht_nach_zeitregel(db, h) for h in ("5.1167", "4.1667", "0.0167", "7.9")] == [
        Decimal("5.1167"), Decimal("4.1667"), Decimal("0.0167"), Decimal("7.9")]


def test_dauer_vorschau_rundet_nicht(threaded_db_session):
    db = threaded_db_session
    _rundung_alt(db)
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    neu = dauer_vorschau(db, employee_id=mia.id, work_date=date(2026, 12, 1), hours=Decimal("7.9"), break_minutes=30)
    assert neu["gebucht"] == Decimal("7.9")


def test_kolonne_rechnet_minutengenau(threaded_db_session):
    db = threaded_db_session
    _rundung_alt(db)
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    werte = kolonne_rechnen(db, [(mia.id, "Mia", None, 0), (tom.id, "Tom", None, 0)], work_date=date(2026, 12, 1), von=time(7), bis=time(12, 10))
    assert {k: v["gebucht"] for k, v in werte.items()} == {mia.id: Decimal("5.1667"), tom.id: Decimal("5.1667")}


def test_der_tag_im_lohn_bleibt_auf_der_viertelstunde():
    """Unverändert seit 1.9.223: zwei minutengenaue Buchungen 5,1167 + 2,9667 = 8,0834 h -> 8,00 h."""
    tag = date(2026, 12, 1)
    rows = [TimeEntry(work_date=tag, hours=Decimal("5.1167"), status="booked"), TimeEntry(work_date=tag, hours=Decimal("2.9667"), status="booked")]
    assert arbeit_des_tags(rows) == Decimal("8.00")


def test_zeitregeln_ohne_rundung(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, backoffice_router.router)
    stand = client.get("/api/time-backoffice/settings").json()
    assert "rounding_minutes" not in stand
    r = client.put("/api/time-backoffice/settings", json={**stand, "rounding_minutes": 15})
    assert r.status_code == 200, r.text
    assert "rounding_minutes" not in r.json()
    db.expire_all()
    assert db.get(TimeTrackingSettings, 1).rounding_minutes == 0


def test_seiten_ohne_rundung():
    einstellungen = (ROOT / "app/templates/settings.html").read_text(encoding="utf-8")
    assert 'id="rounding"' not in einstellungen and "rounding_minutes" not in einstellungen
    for name in ("zeiten.html", "mobil_zeiten.html"):
        assert "Pause und Rundung" not in (ROOT / "app/templates" / name).read_text(encoding="utf-8"), name
