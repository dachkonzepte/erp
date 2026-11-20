"""Version 1.10.7 (Nachrunde W1b, F4): die Zeitpunkte der Bearbeitung einer Anfrage der Webseite kommen aus app/berlin_time.py::utc_jetzt().

    Anlass    klicktest_webanfragen war seit dem 20.11.2026 rot: „verworfen am“ und „aus der Prüfliste gegeben am“ standen mit datetime.utcnow() (echte
              Uhr) in der Datenbank, die Uhr der Instanz stand auf dem 19.11. -- grün nur am Tag des Baus.
    Regel     abgeholt, gemeldet, letzter Lauf (mit und ohne Verbindung), letzter Erfolg, geprüft, verworfen, übernommen -- von derselben Uhr wie
              berlin_now(), im Betrieb gleich datetime.utcnow(), unter einer festen Uhr stimmig; die Sperre des Abholens bleibt auf der echten Uhr
              (sie gilt über Prozesse und läuft nach SPERRE_GILT ab).
    Prüfung   unter einer festen Uhr an einem anderen Tag (03.03.2025): jeder dieser Zeitpunkte liegt an diesem Tag, die Sperre am echten.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import select

from app import webanfragen as W
from app.models import WebAnfrage, WebanfragenAbholung
from app.routers import webanfragen as router_modul
from scripts.empfangsdienst_attrappe import Attrappe, muster
from tests.uhr import uhr_festhalten

TAG = date(2025, 3, 3)
R1, R2, R3 = "R-20261119-0910-0A1B", "R-20261119-0911-0C2D", "R-20261119-0912-0E3F"


@pytest.fixture
def dienst(monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path / "daten"))
    with Attrappe() as a:
        monkeypatch.setenv(W.ADRESSE_VARIABLE, a.adresse)
        monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, a.schluessel)
        yield a


@pytest.fixture
def fest():
    with uhr_festhalten(tag=TAG):
        yield


def _tag(wert: datetime | None) -> date | None:
    return wert.date() if wert is not None else None


def _abholung(db) -> WebanfragenAbholung:
    db.expire_all()
    return db.get(WebanfragenAbholung, 1)


def test_abholen_und_melden_unter_fester_uhr(dienst, fest, db_session):
    dienst.dazu(muster(R1))
    assert W.abholen(db_session).neu == 1
    z = db_session.scalar(select(WebAnfrage).where(WebAnfrage.nummer == R1))
    assert (_tag(z.abgeholt_am), _tag(z.gemeldet_am)) == (TAG, TAG)
    a = _abholung(db_session)
    assert (_tag(a.letzter_lauf_am), _tag(a.letzter_erfolg_am), a.lauf_seit) == (TAG, TAG, None)


def test_letzter_lauf_ohne_verbindung_unter_fester_uhr(monkeypatch, fest, db_session):
    monkeypatch.delenv(W.ADRESSE_VARIABLE, raising=False)
    monkeypatch.delenv(W.SCHLUESSEL_VARIABLE, raising=False)
    assert W.abholen(db_session).fehler
    assert _tag(_abholung(db_session).letzter_lauf_am) == TAG


def test_bearbeitung_unter_fester_uhr(dienst, fest, threaded_db_session, router_test_client):
    dienst.dazu(muster(R1))
    dienst.dazu(muster(R2, spam=True))
    dienst.dazu(muster(R3))
    db = threaded_db_session
    assert W.abholen(db).neu == 3
    ids = {z.nummer: z.id for z in db.scalars(select(WebAnfrage))}
    c = router_test_client(db, router_modul.router, role="buero_auftrag", user_id=1)
    assert c.post(f"/api/webanfragen/{ids[R1]}/verwerfen", json={"grund": "test"}).status_code == 200
    assert c.post(f"/api/webanfragen/{ids[R2]}/eingang").status_code == 200
    v = c.get(f"/api/webanfragen/{ids[R3]}/vorschlag").json()
    kunde = dict(v["kunde_neu"], is_consumer=True)
    r = c.post(f"/api/webanfragen/{ids[R3]}/uebernehmen", json={"kunde_neu": kunde, "objekt": "keins", "titel": "Rinne"})
    assert r.status_code == 200, r.text
    db.expire_all()
    z1, z2, z3 = (db.get(WebAnfrage, ids[n]) for n in (R1, R2, R3))
    assert (_tag(z1.erledigt_am), _tag(z2.geprueft_am), _tag(z3.erledigt_am)) == (TAG, TAG, TAG)
    assert (_tag(z1.gemeldet_am), _tag(z3.gemeldet_am)) == (TAG, TAG)  # nachgemeldet direkt nach der Aktion


def test_sperre_bleibt_auf_der_echten_uhr(dienst, fest, db_session, monkeypatch):
    genommen = []
    echt = W._sperre_nehmen

    def merken(db, jetzt):
        genommen.append(jetzt)
        return echt(db, jetzt)

    monkeypatch.setattr(W, "_sperre_nehmen", merken)
    dienst.dazu(muster(R1))
    vorher = datetime.utcnow()
    assert W.abholen(db_session).neu == 1
    assert len(genommen) == 1 and genommen[0].date() != TAG and genommen[0] >= vorher.replace(microsecond=0)
