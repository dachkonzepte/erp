"""Version 1.9.171 (Lohn L1a, Punkt 6, Entscheidungen Tobias E9 und „Halbe Tage“): Sammeleintrag und halbe Urlaubstage.

    halber Tag    Urlaub an einem Tag als halber Tag: halbe Sollzeit, zählt 0,5 Tag; sonst 422
    24.12./31.12. 1.9.171–1.9.173 zählte Urlaub an diesen Tagen je 0,5 Tag; seit 1.9.174 (L1a-Nachtrag, Punkt 1) ein ganzer Tag
    Tage          nach der Sollzeit der Person (app/sollzeit.py::abwesenheit_tage()): ohne Tage ohne Soll und gesetzliche Feiertage
    Sammeleintrag POST /api/absence-requests/sammel -- Admin gleich genehmigt, Büro – Finanzen Anträge, sonst 403; alles oder nichts

Feste Tage: Dezember 2026 (Winter, Soll 7,50 h).
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.absence_requests import create_request, review_request
from app.models import EmployeeAbsence, EmployeeAbsenceRequest, TeamEmployee
from app.routers import absence_requests as absence_router
from app.routers import zeiten as zeiten_router
from app.sollzeit import abwesenheit_tage, zeile_anlegen
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v380_nummern_eindeutig import _alembic, _ok

D = Decimal
MIGRATION = "f6c3a8e25b19"
VORHER = "e4b7d1a93c56"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom, kai = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur"), make_employee(db, "M-3", "Kai", "Kolonne")
    team = make_team(db, "K-1", "Kolonne 1")
    db.add_all([TeamEmployee(team_id=team.id, employee_id=mia.id), TeamEmployee(team_id=team.id, employee_id=tom.id)])
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "kai": kai, "team": team, "client": router_test_client}


def _als(w, rolle="admin", wer=None):
    w["db"].commit()
    return w["client"](w["db"], absence_router.router, zeiten_router.router, role=rolle, employee_id=w[wer].id if wer else None, user_id=9)


def _tage(w, emp, von, bis, kategorie="urlaub", halber_tag=False):
    t = abwesenheit_tage(w["db"], emp.id, von, bis, kategorie=kategorie, halber_tag=halber_tag)
    return t["tage"], t["stunden"]


# --- halber Tag, 24.12. und 31.12. -----------------------------------------------------------------------------------------------------

def test_halber_urlaubstag(welt):
    db, mia = welt["db"], welt["mia"]
    antrag = create_request(db, employee_id=mia.id, absence_category="urlaub", start_date=date(2026, 12, 7), end_date=date(2026, 12, 7),
                            halber_tag=True)
    review_request(db, antrag.id, decision="approved", reviewed_by_user_id=None)
    abw = db.query(EmployeeAbsence).one()
    assert abw.halber_tag is True
    assert _tage(welt, mia, date(2026, 12, 7), date(2026, 12, 7), halber_tag=True) == (D("0.5"), D("3.75"))


@pytest.mark.parametrize("kategorie, von, bis", [("krankheit", date(2026, 12, 7), date(2026, 12, 7)),
                                                 ("urlaub", date(2026, 12, 7), date(2026, 12, 8))], ids=["krankheit", "zwei_tage"])
def test_halber_tag_nur_urlaub_an_einem_tag(welt, kategorie, von, bis):
    r = _als(welt).post("/api/absence-requests", json={"employee_id": welt["mia"].id, "absence_category": kategorie, "start_date": von.isoformat(),
                                                       "end_date": bis.isoformat(), "halber_tag": True})
    assert r.status_code == 422 and "halber Tag geht nur bei Urlaub" in r.json()["detail"]


def test_weihnachten_und_silvester_ganze_tage(welt):
    """Seit 1.9.174 (Festlegung 1.9.171 Nr. 2 zurückgezogen) keine Halbierung mehr; seit 1.9.175 ist der 24.12. für gewerbliche Mitarbeiter
    Heiligabend im Arbeitszeitkalender (bezahlte Freistellung, kein Urlaubstag): 21.12.–31.12.2026: Mo–Mi je 1, Do 24.12. 0, Fr 25.12.
    Feiertag, Mo–Do je 1 -> 7 Tage, 52,50 h (1.9.174: 8 Tage, 60,00 h; 1.9.171–1.9.173: 24.12. und 31.12. je 0,5)."""
    assert _tage(welt, welt["mia"], date(2026, 12, 21), date(2026, 12, 31)) == (D("7"), D("52.50"))
    assert _tage(welt, welt["mia"], date(2026, 12, 24), date(2026, 12, 24)) == (D("0"), D("0.00"))
    assert _tage(welt, welt["mia"], date(2027, 12, 31), date(2027, 12, 31)) == (D("1"), D("7.50"))  # Freitag
    assert _tage(welt, welt["mia"], date(2026, 12, 24), date(2026, 12, 24), kategorie="krankheit") == (D("0"), D("0.00"))
    # ein halber Tag bleibt eine Funktion, auch kurz vor Weihnachten
    assert _tage(welt, welt["mia"], date(2026, 12, 23), date(2026, 12, 23), halber_tag=True) == (D("0.5"), D("3.75"))


def test_tage_nach_sollzeit(welt):
    """Teilzeit Di–Do 3,00 h: eine Woche Urlaub zählt 3 Tage und 9 h; vor dem Eintritt nichts."""
    zeile_anlegen(welt["db"], welt["tom"].id, date(2026, 12, 1), {"dienstag": D("3"), "mittwoch": D("3"), "donnerstag": D("3")})
    assert _tage(welt, welt["tom"], date(2026, 12, 7), date(2026, 12, 11)) == (D("3"), D("9.00"))


def test_zeiten_zeigt_halbe_tage(welt):
    db, mia = welt["db"], welt["mia"]
    create_request(db, employee_id=mia.id, absence_category="urlaub", start_date=date(2026, 12, 7), end_date=date(2026, 12, 7), halber_tag=True)
    create_request(db, employee_id=mia.id, absence_category="urlaub", start_date=date(2026, 12, 21), end_date=date(2026, 12, 31),
                   kalendertag_urlaub=True)  # seit 1.9.176: Silvester als ganzer Urlaubstag
    a = _als(welt, "buero_finanzen").get("/api/zeiten/abwesenheiten").json()["antraege"]
    assert sorted((x["start_date"], x["halber_tag"], D(str(x["arbeitstage"]))) for x in a) == [
        ("2026-12-07", True, D("0.5")), ("2026-12-21", False, D("7"))]  # seit 1.9.175 ohne Heiligabend (1.9.174: 8; 1.9.171–1.9.173: 7)


# --- Sammeleintrag ------------------------------------------------------------------------------------------------------------------------

def _sammel(client, *leute, **mehr):
    return client.post("/api/absence-requests/sammel", json={"employee_ids": [p.id for p in leute], "absence_category": "urlaub",
                                                             "start_date": "2026-12-28", "end_date": "2026-12-30", **mehr})


def test_admin_traegt_fuer_alle_ein(welt):
    r = _sammel(_als(welt), welt["mia"], welt["tom"], welt["kai"])
    assert r.status_code == 200, r.text
    assert [x["status"] for x in r.json()] == ["approved"] * 3
    assert welt["db"].query(EmployeeAbsence).count() == 3


def test_buero_finanzen_stellt_antraege(welt):
    r = _sammel(_als(welt, "buero_finanzen"), welt["mia"], welt["tom"])
    assert (r.status_code, [x["status"] for x in r.json()]) == (200, ["pending", "pending"])
    assert welt["db"].query(EmployeeAbsence).count() == 0


@pytest.mark.parametrize("rolle, wer", [("buero_auftrag", None), ("field", "mia")])
def test_andere_rollen_403(welt, rolle, wer):
    assert _sammel(_als(welt, rolle, wer), welt["mia"]).status_code == 403


def test_alles_oder_nichts(welt):
    """Tom hat am 29.12. schon einen offenen Antrag -- für niemanden eingetragen, die Meldung nennt Tom."""
    create_request(welt["db"], employee_id=welt["tom"].id, absence_category="krankheit", start_date=date(2026, 12, 29), end_date=date(2026, 12, 29))
    vorher = welt["db"].query(EmployeeAbsenceRequest).count()
    r = _sammel(_als(welt), welt["mia"], welt["tom"], welt["kai"])
    assert r.status_code == 422
    # seit 1.9.205 aus belegt(), mit dem Tag (bis 1.9.204 „Tom Monteur: Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“)
    assert [x["text"] for x in r.json()["liste"]] == ["Tom Monteur: am 29.12.2026 bereits ein offener Antrag"]
    welt["db"].expire_all()
    assert welt["db"].query(EmployeeAbsenceRequest).count() == vorher and welt["db"].query(EmployeeAbsence).count() == 0


def test_sammel_halber_tag_und_schlechtwetter(welt):
    client = _als(welt)
    r = _sammel(client, welt["mia"], welt["tom"], start_date="2026-12-23", end_date="2026-12-23", halber_tag=True)
    assert r.status_code == 200 and all(x["halber_tag"] for x in r.json())
    assert _sammel(client, welt["mia"], absence_category="schlechtwetter").status_code == 422


def test_kolonnen_fuer_den_sammeleintrag(welt):
    finanzen = _als(welt, "buero_finanzen").get("/api/zeiten/abwesenheiten").json()["kolonnen"]
    assert [(k["name"], sorted(k["mitglieder"])) for k in finanzen] == [("Kolonne 1", sorted([welt["mia"].id, welt["tom"].id]))]
    assert _als(welt, "buero_auftrag", "kai").get("/api/zeiten/abwesenheiten").json()["kolonnen"] == []


def test_seiten():
    from tests import vorlagen_js as vj
    zeiten = (vj.TEMPLATES / "zeiten.html").read_text(encoding="utf-8")
    for teil in ('id="adMehrere"', 'id="adKolonne"', 'id="adPersonen"', 'id="adHalb"', "'/api/absence-requests/sammel'", "halber_tag:el('adHalb').checked"):
        assert teil in zeiten, teil
    mobil = (vj.TEMPLATES / "mobil_zeiten.html").read_text(encoding="utf-8")
    assert 'id="adHalb"' in mobil and "halber_tag:el('adHalb').checked" in mobil


# --- Migration f6c3a8e25b19 -----------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        c.execute(text("INSERT INTO employee_absences (employee_id, absence_type, absence_category, start_date, end_date, created_at, updated_at) "
                       "VALUES ((SELECT id FROM employees), 'Urlaub', 'urlaub', '2026-12-07', '2026-12-07', '2026-09-01', '2026-09-01')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        assert [bool(x) for x in c.execute(text("SELECT halber_tag FROM employee_absences")).scalars()] == [False]
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM employee_absences")).scalar() == 1
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'halb.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_halb_{uuid.uuid4().hex[:8]}"
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
