"""Version 1.9.176 (L1a-Nachtrag, Punkt 3, Vorgabe Tobias 03.11.2026): Silvester im Arbeitszeitkalender.

    Silvester   31.12., nur Mo–Fr, nur gewerbliche: Sollzeit des Modells, von selbst „Silvester – unbezahlte Freistellung“ (ohne Lohn, Konto
                neutral: Stunden = Sollzeit); Zuordnung AF ohne Lohnart
    Urlaub      liegt der Tag in einem Urlaub, fragt der Dialog: ganzer Urlaubstag (Vorschlag, ersetzt die Freistellung) oder frei -- der Server
                lehnt ohne Antwort mit 409 und rueckfrage ab (nichts gespeichert), auf allen drei Wegen; halbe Tage gibt es dort nicht

Feste Tage: Do 31.12.2026 (Winter 7,50 h), So 31.12.2028.
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.absence_requests import create_request, review_request
from app.arbeitszeitkalender import abwesenheiten, eintraege
from app.lohnarten import kalender as kalender_zuordnung
from app.models import Employee, EmployeeAbsence, EmployeeAbsenceRequest
from app.routers import absence_requests as absence_router
from app.routers import planning as planning_router
from app.routers import schlechtwetter as schlechtwetter_router
from app.routers import zeiten as zeiten_router
from app.sollzeit import abwesenheit_tage, soll
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

D = Decimal
MIGRATION = "2474667579d8"
VORHER = "fcbfd2cea2da"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
FRAGE = {"tage": [{"tag": "2026-12-31", "name": "Silvester", "abwesenheit": "Silvester – unbezahlte Freistellung"}]}
URLAUB = {"absence_category": "urlaub", "start_date": "2026-12-28", "end_date": "2027-01-08"}


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    kim = Employee(employee_number="K-1", first_name="Kim", last_name="Kauffrau", employee_group="kaufmaennisch", active=True)
    db.add(kim)
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "kim": kim, "client": router_test_client}


def _als(w, rolle="admin", wer=None):
    w["db"].commit()
    return w["client"](w["db"], absence_router.router, planning_router.router, zeiten_router.router, schlechtwetter_router.router, role=rolle,
                       employee_id=w[wer].id if wer else None, user_id=9)


def _anzahl(w):
    w["db"].expire_all()
    return w["db"].query(EmployeeAbsenceRequest).count(), w["db"].query(EmployeeAbsence).count()


def _tage(w, emp, kalendertag_urlaub=None, kategorie="urlaub"):
    t = abwesenheit_tage(w["db"], emp.id, date(2026, 12, 28), date(2027, 1, 8), kategorie=kategorie, kalendertag_urlaub=kalendertag_urlaub)
    return t["tage"], t["stunden"]


def test_silvester_ist_vorbelegt(welt):
    db = welt["db"]
    s = next(e for e in eintraege(db) if e.schluessel == "silvester")
    assert (s.monat, s.tag, s.sollzeit, s.abwesenheit, s.bezahlt, s.im_urlaub, s.nur_gewerblich, s.nur_mo_fr, s.aktiv) == (
        12, 31, None, "Silvester – unbezahlte Freistellung", False, "fragen", True, True, True)
    assert kalender_zuordnung(db, "silvester") == {"kennzeichen": "AF", "lohnart": None, "schluessel": "kalender:silvester", "exportiert": False}


def test_sollzeit_und_freistellung(welt):
    db, mia, kim = welt["db"], welt["mia"], welt["kim"]
    assert soll(db, mia.id, date(2026, 12, 31)) == D("7.50")  # der Modellwert
    assert abwesenheiten(db, mia.id, date(2026, 12, 31), date(2026, 12, 31)) == [
        {"tag": date(2026, 12, 31), "schluessel": "silvester", "name": "Silvester", "abwesenheit": "Silvester – unbezahlte Freistellung",
         "stunden": D("7.50"), "bezahlt": False}]
    assert abwesenheiten(db, kim.id, date(2026, 12, 31), date(2026, 12, 31)) == []
    assert abwesenheiten(db, mia.id, date(2028, 12, 31), date(2028, 12, 31)) == []  # Sonntag


@pytest.mark.parametrize("weg", ["einzeln", "sammel", "plantafel"])
def test_ohne_antwort_fragt_der_server(welt, weg):
    client, mia = _als(welt), welt["mia"]
    if weg == "einzeln":
        r = client.post("/api/absence-requests", json={"employee_id": mia.id, **URLAUB})
    elif weg == "sammel":
        r = client.post("/api/absence-requests/sammel", json={"employee_ids": [welt["kim"].id, mia.id], **URLAUB})
    else:
        r = client.post("/api/planning/absences", json={"employee_id": mia.id, **URLAUB})
    assert r.status_code == 409, r.text
    assert r.json() == {"detail": "Im Urlaub liegt der 31.12.2026 („Silvester – unbezahlte Freistellung“): als ganzer Urlaubstag oder frei? Bitte wählen.",
                        "rueckfrage": FRAGE}
    assert _anzahl(welt) == (0, 0)


@pytest.mark.parametrize("antwort, tage, stunden, freistellung", [(True, D("9"), D("67.50"), False), (False, D("8"), D("60.00"), True)],
                         ids=["urlaubstag", "frei"])
def test_antwort_zaehlt(welt, antwort, tage, stunden, freistellung):
    """28.12.2026–08.01.2027: Mo–Do 4 Tage, Fr 01.01. Feiertag, 04.–08.01. 5 Tage; Silvester als Urlaubstag 9, frei 8."""
    db, mia = welt["db"], welt["mia"]
    r = _als(welt).post("/api/absence-requests", json={"employee_id": mia.id, **URLAUB, "kalendertag_urlaub": antwort})
    assert r.status_code == 200 and r.json()["kalendertag_urlaub"] is antwort
    assert _tage(welt, mia, antwort) == (tage, stunden)
    review_request(db, r.json()["id"], decision="approved", reviewed_by_user_id=None)
    assert db.query(EmployeeAbsence).one().kalendertag_urlaub is antwort
    assert bool(abwesenheiten(db, mia.id, date(2026, 12, 31), date(2026, 12, 31))) is freistellung  # „ersetzt die Freistellung“
    d = _als(welt, "buero_finanzen").get("/api/zeiten/abwesenheiten").json()
    assert [(a["arbeitstage"], a["kalendertag_urlaub"]) for a in d["antraege"]] == [(int(tage), antwort)]


def test_ohne_silvester_keine_frage(welt):
    """Kaufmännisch, ein Urlaub ohne den 31.12., Krankheit über Silvester: keine Rückfrage, die Spalte bleibt leer."""
    client = _als(welt)
    kim = client.post("/api/absence-requests", json={"employee_id": welt["kim"].id, **URLAUB})
    vorher = client.post("/api/absence-requests", json={"employee_id": welt["mia"].id, "absence_category": "urlaub", "start_date": "2026-12-14",
                                                        "end_date": "2026-12-18", "kalendertag_urlaub": True})
    krank = client.post("/api/absence-requests", json={"employee_id": welt["tom"].id, **URLAUB, "absence_category": "krankheit"})
    assert [(x.status_code, x.json()["kalendertag_urlaub"]) for x in (kim, vorher, krank)] == [(200, None)] * 3
    assert _tage(welt, welt["kim"]) == (D("9"), D("67.50"))
    assert _tage(welt, welt["tom"], kategorie="krankheit") == (D("8"), D("60.00"))  # die Freistellung gilt


def test_kein_halber_tag_an_silvester(welt):
    r = _als(welt).post("/api/absence-requests", json={"employee_id": welt["mia"].id, "absence_category": "urlaub", "start_date": "2026-12-31",
                                                       "end_date": "2026-12-31", "halber_tag": True, "kalendertag_urlaub": True})
    assert (r.status_code, r.json()["detail"]) == (422, "Am 31.12.2026 gilt „Silvester – unbezahlte Freistellung“ – ein halber Urlaubstag geht dort nicht.")


def test_alter_urlaub_ohne_antwort_gilt_wie_der_vorschlag(welt):
    """Eine Abwesenheit von vor 1.9.176 (kalendertag_urlaub leer) nimmt Silvester als ganzen Urlaubstag -- die Freistellung entfällt."""
    db, mia = welt["db"], welt["mia"]
    db.add(EmployeeAbsence(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 12, 28),
                           end_date=date(2027, 1, 8)))
    db.commit()
    assert abwesenheiten(db, mia.id, date(2026, 12, 31), date(2026, 12, 31)) == []
    assert _tage(welt, mia) == (D("9"), D("67.50"))


def test_die_monteurin_wird_gefragt(welt):
    client = _als(welt, "field", "mia")
    body = {"employee_id": welt["mia"].id, **URLAUB}
    assert client.post("/api/absence-requests", json=body).json()["rueckfrage"] == FRAGE
    r = client.post("/api/absence-requests", json={**body, "kalendertag_urlaub": True})
    assert (r.status_code, r.json()["status"], r.json()["kalendertag_urlaub"]) == (200, "pending", True)


def test_kein_schlechtwetter_an_silvester(welt):
    r = _als(welt, "buero_finanzen").post("/api/schlechtwetter", json={"employee_ids": [welt["mia"].id], "tag": "2026-12-31", "trotzdem": False})
    assert r.status_code == 422 and "„Silvester – unbezahlte Freistellung“" in r.json()["liste"][0]["text"]


def test_seiten():
    from tests import vorlagen_js as vj
    for seite in ("zeiten.html", "mobil_zeiten.html", "planning.html"):
        assert vj.bindet_ein(seite, "_kalendertag_frage.html"), seite
        text = (vj.TEMPLATES / seite).read_text(encoding="utf-8")
        for teil in ('id="adKalenderFrage"', "kalendertag_urlaub:ktWahl(", "ktFrageZeigen(", "f.rueckfrage="):
            assert teil in text, (seite, teil)


# --- Migration 2474667579d8 -----------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        c.execute(text("INSERT INTO employee_absences (employee_id, absence_type, absence_category, start_date, end_date, halber_tag, created_at, "
                       "updated_at) VALUES ((SELECT id FROM employees), 'Urlaub', 'urlaub', '2026-12-28', '2027-01-08', :f, '2026-09-01', '2026-09-01')"),
                  {"f": False})
        c.execute(text("INSERT INTO arbeitszeit_kalendertage (schluessel, name, monat, tag, sollzeit, abwesenheit, created_at, updated_at) "
                       "VALUES ('heiligabend', 'Heiligabend', 12, 24, 7, 'Heiligabend – bezahlte Freistellung', '2026-11-03', '2026-11-03')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        assert c.execute(text("SELECT kalendertag_urlaub FROM employee_absences")).scalars().all() == [None]
        c.execute(text("INSERT INTO arbeitszeit_kalendertage (schluessel, name, monat, tag, abwesenheit, bezahlt, im_urlaub, created_at, updated_at) "
                       "VALUES ('silvester', 'Silvester', 12, 31, 'Silvester – unbezahlte Freistellung', :f, 'fragen', '2026-11-03', '2026-11-03')"),
                  {"f": False})
        c.execute(text("INSERT INTO lohnart_zuordnungen (schluessel, kennzeichen, monatszeile, updated_at) VALUES ('kalender:silvester', 'AF', :f, "
                       "'2026-11-03'), ('kalender:heiligabend', 'BF', :f, '2026-11-03')"), {"f": False})
        c.execute(text("UPDATE employee_absences SET kalendertag_urlaub = :w"), {"w": False})
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert c.execute(text("SELECT schluessel FROM arbeitszeit_kalendertage")).scalars().all() == ["heiligabend"]
        assert c.execute(text("SELECT schluessel FROM lohnart_zuordnungen")).scalars().all() == ["kalender:heiligabend"]
        assert c.execute(text("SELECT count(*) FROM employee_absences")).scalar() == 1
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'silvester.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_silv_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
