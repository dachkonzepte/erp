"""Version 1.9.318 (Nachrunde L2b, Punkt B): „Meine Zeiten“ ohne Startwert.

    Konto         fehlt der Startwert (2027), trägt das eigene Konto den Hinweis „ohne Übertrag – Startwert folgt“ -- „Meine Zeiten“ zeigt ihn mit den übrigen
    danach Rest   dazu „ · ohne Übertrag – Startwert folgt“, wenn in einem der Jahre des Urlaubs der Startwert fehlt -- überall, wo „danach Rest“ steht
                  (Antrag in „Meine Zeiten“, unter „Zeiten“, auf der Plantafel, an offenen Anträgen); mit Startwert nicht; ab 2028 nicht
Stehende Uhr 10.11.2026 (fester_tag).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.meine_zeiten import meine_zeiten
from app.models import LohnStartwert
from app.routers import absence_requests as antraege_router
from app.urlaubskonto import OHNE_STARTWERT, rest_danach
from tests.test_v224_field_view import make_employee

D = Decimal
H = " · ohne Übertrag – Startwert folgt"


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    ada, bo = make_employee(db, "M-1", "Ada", "Monteurin"), make_employee(db, "M-2", "Bo", "Monteur")
    db.add(LohnStartwert(employee_id=ada.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
    db.commit()
    return {"db": db, "ada": ada, "bo": bo, "client": router_test_client}


def test_konto_in_meine_zeiten_mit_dem_hinweis(w):
    eigen = meine_zeiten(w["db"], w["bo"].id, monat=date(2026, 11, 1), heute=date(2026, 11, 10))["urlaub"]
    assert (eigen["jahr"], eigen["uebertrag"], eigen["hinweise"]) == (2027, D("0.0"), [OHNE_STARTWERT])
    assert meine_zeiten(w["db"], w["ada"].id, monat=date(2026, 11, 1), heute=date(2026, 11, 10))["urlaub"]["hinweise"] == []


def test_danach_rest_mit_dem_hinweis(w):
    db, ada, bo = w["db"], w["ada"], w["bo"]
    d = rest_danach(db, bo.id, date(2027, 3, 1), date(2027, 3, 5))
    assert (d["text"], d["jahre"][0]["ohne_startwert"]) == ("danach Rest 25 Tage" + H, True)
    assert rest_danach(db, ada.id, date(2027, 3, 1), date(2027, 3, 5))["text"] == "danach Rest 29,5 Tage"  # mit Startwert ohne Hinweis
    assert rest_danach(db, bo.id, date(2028, 3, 6), date(2028, 3, 10))["text"] == "danach Rest 25 Tage"  # 2028: der Übertrag ist kein Startwert
    over = rest_danach(db, bo.id, date(2027, 12, 27), date(2028, 1, 7))  # über den Jahreswechsel: der Hinweis einmal am Ende
    assert over["text"] == "danach Rest 2027: 25 Tage · 2028: 25 Tage" + H and [x["ohne_startwert"] for x in over["jahre"]] == [True, False]


def test_im_antrag_von_meine_zeiten(w):
    db, bo = w["db"], w["bo"]
    c = w["client"](db, antraege_router.router, role="field", employee_id=bo.id)
    r = c.get(f"/api/absence-requests/rest-danach?employee_id={bo.id}&von=2027-03-01&bis=2027-03-05").json()
    assert (r["tage_text"], r["text"]) == ("5 Urlaubstage", "danach Rest 25 Tage" + H)
