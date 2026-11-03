"""Version 1.9.175 (L1a-Nachtrag, Punkt 2, Vorgabe Tobias 03.11.2026): Arbeitszeitkalender und Heiligabend.

    Kalender      Tage, die jedes Jahr am selben Datum anders laufen (ArbeitszeitKalendertag), in den Einstellungen gepflegt, nicht im Code
    Heiligabend   24.12., nur Mo–Fr, nur gewerbliche: Sollzeit 7,00 h statt Modellwert (auch Teilzeit mit eigener Sollzeit), von selbst
                  „Heiligabend – bezahlte Freistellung“ mit 7,00 h (gebuchte Arbeit mindert sie nicht), kein Urlaubstag, Zuordnung BF ohne
                  Lohnart
    Rechte        lesen ab Büro – Auftrag, ändern Admin und Büro – Finanzen (E10, wie die Sollzeit)

Feste Tage: Dezember 2026 (Do 24.12., Winter 7,50 h), 2027 (Fr), 2028 (So), 2029 (Mo).
"""

import os
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.absence_requests import create_request
from app.arbeitszeitkalender import abwesenheiten, eintraege, kalendertag
from app.lohnarten import kalender as kalender_zuordnung, liste as lohnarten_liste, speichern as lohnart_speichern
from app.models import ArbeitszeitKalendertag, Employee, EmployeePayrollSettings, TimeEntry
from app.routers import absence_requests as absence_router
from app.routers import schlechtwetter as schlechtwetter_router
from app.routers import time_backoffice as time_backoffice_router
from app.routers import zeiten as zeiten_router
from app.sollzeit import abwesenheit_tage, soll, zeile_anlegen
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v380_nummern_eindeutig import _alembic, _ok

D = Decimal
MIGRATION = "fcbfd2cea2da"
VORHER = "f6c3a8e25b19"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
KALENDER = "/api/time-backoffice/arbeitszeitkalender"


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Teilzeit")
    kim = Employee(employee_number="K-1", first_name="Kim", last_name="Kauffrau", employee_group="kaufmaennisch", active=True)
    db.add(kim)
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "kim": kim, "client": router_test_client}


def _als(w, rolle="admin", wer=None):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, absence_router.router, zeiten_router.router, schlechtwetter_router.router,
                       role=rolle, employee_id=w[wer].id if wer else None, user_id=9)


def _eintrag(**mehr):
    return {"name": "Rosenmontag", "monat": 2, "tag": 15, "sollzeit": None, "abwesenheit": "Rosenmontag – frei", "bezahlt": True,
            "im_urlaub": "kein_urlaubstag", "nur_gewerblich": True, "nur_mo_fr": True, "aktiv": True, **mehr}


# --- Vorbelegung ---------------------------------------------------------------------------------------------------------------------------

def test_heiligabend_ist_vorbelegt(welt):
    db = welt["db"]
    e = eintraege(db)[0]  # seit 1.9.176 danach Silvester (tests/test_v592_silvester.py)
    assert (e.schluessel, e.name, e.monat, e.tag, e.sollzeit, e.abwesenheit, e.bezahlt, e.im_urlaub, e.nur_gewerblich, e.nur_mo_fr, e.aktiv) == (
        "heiligabend", "Heiligabend", 12, 24, D("7.00"), "Heiligabend – bezahlte Freistellung", True, "kein_urlaubstag", True, True, True)
    assert kalender_zuordnung(db, "heiligabend") == {"kennzeichen": "BF", "lohnart": None, "schluessel": "kalender:heiligabend", "exportiert": False}
    zeile = next(z for z in lohnarten_liste(db) if z["schluessel"] == "kalender:heiligabend")
    assert (zeile["bezeichnung"], zeile["stunden"], zeile["wirkt"]) == (
        "Heiligabend – bezahlte Freistellung (24.12.)", "7,00 h (Kalender)", "BF / Lohnart offen – nicht exportiert")


def test_der_start_legt_nichts_doppelt_an_und_laesst_geaendertes_stehen(welt):
    from app.grunddaten import anlegen
    db = welt["db"]
    e = eintraege(db)[0]
    e.sollzeit, e.aktiv = D("6.50"), False
    db.commit()
    anlegen(db)
    db.commit()
    assert [(x.schluessel, x.sollzeit, x.aktiv) for x in eintraege(db)] == [("heiligabend", D("6.50"), False), ("silvester", None, True)]


# --- Sollzeit -------------------------------------------------------------------------------------------------------------------------------

def test_sollzeit_an_heiligabend(welt):
    db, mia, kim = welt["db"], welt["mia"], welt["kim"]
    assert soll(db, mia.id, date(2026, 12, 24)) == D("7.00")  # Do, statt 7,50 (Winter)
    assert soll(db, mia.id, date(2026, 12, 23)) == D("7.50")
    assert soll(db, mia.id, date(2027, 12, 24)) == D("7.00")  # Fr
    assert soll(db, mia.id, date(2028, 12, 24)) == D("0.00")  # So: nur Mo–Fr
    assert soll(db, kim.id, date(2026, 12, 24)) == D("7.50")  # nur gewerbliche


def test_sollzeit_auch_fuer_teilzeit_mit_eigener_sollzeit(welt):
    """Vorgabe: „gilt gleich für alle, auch Azubis und Teilzeit mit eigener Sollzeit“ -- Di–Do 3,00 h: Do 24.12.2026 und Mo 24.12.2029 7,00 h."""
    db, tom = welt["db"], welt["tom"]
    zeile_anlegen(db, tom.id, date(2026, 12, 1), {"dienstag": D("3"), "mittwoch": D("3"), "donnerstag": D("3")})
    assert soll(db, tom.id, date(2026, 12, 23)) == D("3.00")
    assert soll(db, tom.id, date(2026, 12, 24)) == D("7.00")
    assert soll(db, tom.id, date(2029, 12, 24)) == D("7.00")


def test_vor_dem_eintritt_kein_heiligabend(welt):
    db, mia = welt["db"], welt["mia"]
    db.add(EmployeePayrollSettings(employee_id=mia.id, eintritt=date(2027, 1, 1)))
    db.commit()
    assert soll(db, mia.id, date(2026, 12, 24)) == D("0.00")
    assert abwesenheiten(db, mia.id, date(2026, 12, 1), date(2026, 12, 31)) == []


# --- Abwesenheit von selbst -----------------------------------------------------------------------------------------------------------------

def test_abwesenheit_von_selbst(welt):
    db, mia, kim = welt["db"], welt["mia"], welt["kim"]
    # seit 1.9.176 nur die Tage von Heiligabend (Silvester: tests/test_v592_silvester.py)
    assert [a for a in abwesenheiten(db, mia.id, date(2026, 12, 1), date(2028, 12, 31)) if a["schluessel"] == "heiligabend"] == [
        {"tag": date(2026, 12, 24), "schluessel": "heiligabend", "name": "Heiligabend", "abwesenheit": "Heiligabend – bezahlte Freistellung",
         "stunden": D("7.00"), "bezahlt": True},
        {"tag": date(2027, 12, 24), "schluessel": "heiligabend", "name": "Heiligabend", "abwesenheit": "Heiligabend – bezahlte Freistellung",
         "stunden": D("7.00"), "bezahlt": True}]  # 2028: Sonntag
    assert abwesenheiten(db, kim.id, date(2026, 12, 1), date(2026, 12, 31)) == []
    assert db.query(ArbeitszeitKalendertag).count() == 2  # nichts gespeichert außer dem Kalender (Heiligabend, seit 1.9.176 Silvester)


def test_gebuchte_arbeit_mindert_die_freistellung_nicht(welt):
    db, mia = welt["db"], welt["mia"]
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0591"))
    db.add(TimeEntry(employee_id=mia.id, project_id=order.project_id, order_id=order.id, work_date=date(2026, 12, 24), entry_type="site",
                     hours=D("4.00"), break_minutes=0, status="booked", started_at=datetime(2026, 12, 24, 7), ended_at=datetime(2026, 12, 24, 11)))
    db.commit()
    (a,) = abwesenheiten(db, mia.id, date(2026, 12, 24), date(2026, 12, 24))
    assert a["stunden"] == D("7.00")


# --- Urlaub, halber Tag, Schlechtwetter -----------------------------------------------------------------------------------------------------

def test_urlaub_ueber_heiligabend_zaehlt_ihn_nicht(welt):
    """Urlaub Mo 21.12.2026–Fr 01.01.2027: gewerblich 7 Tage (24.12. 0, 25.12. und 01.01. Feiertag), kaufmännisch 8."""
    db = welt["db"]
    t = abwesenheit_tage(db, welt["mia"].id, date(2026, 12, 21), date(2027, 1, 1), kategorie="urlaub")
    assert (t["tage"], t["stunden"]) == (D("7"), D("52.50"))
    t = abwesenheit_tage(db, welt["kim"].id, date(2026, 12, 21), date(2027, 1, 1), kategorie="urlaub")
    assert (t["tage"], t["stunden"]) == (D("8"), D("60.00"))
    assert abwesenheit_tage(db, welt["mia"].id, date(2026, 12, 24), date(2026, 12, 24), kategorie="krankheit")["tage"] == D("0")


def test_zeiten_zeigt_die_arbeitstage_und_den_kalender(welt):
    create_request(welt["db"], employee_id=welt["mia"].id, absence_category="urlaub", start_date=date(2026, 12, 21), end_date=date(2027, 1, 1),
                   kalendertag_urlaub=True)  # seit 1.9.176: Silvester als ganzer Urlaubstag
    d = _als(welt, "buero_finanzen").get("/api/zeiten/abwesenheiten").json()
    assert [a["arbeitstage"] for a in d["antraege"]] == [7]
    assert [(k["tag"], k["abwesenheit"], k["fuer"]) for k in d["kalender"]] == [
        ("2026-12-24", "Heiligabend – bezahlte Freistellung", "gewerbliche Mitarbeiter"),
        ("2026-12-31", "Silvester – unbezahlte Freistellung", "gewerbliche Mitarbeiter"),
        ("2027-12-24", "Heiligabend – bezahlte Freistellung", "gewerbliche Mitarbeiter"),
        ("2027-12-31", "Silvester – unbezahlte Freistellung", "gewerbliche Mitarbeiter")]


def test_halber_urlaubstag_an_heiligabend_nur_kaufmaennisch(welt):
    client = _als(welt)
    body = {"absence_category": "urlaub", "start_date": "2026-12-24", "end_date": "2026-12-24", "halber_tag": True}
    r = client.post("/api/absence-requests", json={"employee_id": welt["mia"].id, **body})
    assert r.status_code == 422 and r.json()["detail"] == "Am 24.12.2026 gilt „Heiligabend – bezahlte Freistellung“ – ein halber Urlaubstag geht dort nicht."
    assert client.post("/api/absence-requests", json={"employee_id": welt["kim"].id, **body}).status_code == 200


def test_kein_schlechtwetter_an_heiligabend(welt):
    r = _als(welt, "buero_finanzen").post("/api/schlechtwetter", json={"employee_ids": [welt["mia"].id], "tag": "2026-12-24", "trotzdem": False})
    assert r.status_code == 422
    assert r.json()["liste"] == [{"text": "Mia Monteurin: am 24.12.2026 gilt „Heiligabend – bezahlte Freistellung“ (Arbeitszeitkalender)"}]


# --- Pflege und Rechte ----------------------------------------------------------------------------------------------------------------------

def test_buero_auftrag_liest_nur(welt):
    client = _als(welt, "buero_auftrag")
    d = client.get(KALENDER).json()
    assert [e["name"] for e in d["eintraege"]] == ["Heiligabend", "Silvester"] and [u["value"] for u in d["im_urlaub"]] == ["kein_urlaubstag", "fragen"]
    assert client.post(KALENDER, json=_eintrag()).status_code == 403
    assert client.put(f"{KALENDER}/{d['eintraege'][0]['id']}", json=_eintrag()).status_code == 403


def test_anlegen_aendern_abschalten(welt):
    db, mia = welt["db"], welt["mia"]
    client = _als(welt, "buero_finanzen")
    r = client.post(KALENDER, json=_eintrag())
    assert r.status_code == 200, r.text
    assert [(e["schluessel"], e["datum"]) for e in r.json()["eintraege"]] == [("rosenmontag", "15.02."), ("heiligabend", "24.12."), ("silvester", "31.12.")]
    assert "kalender:rosenmontag" in {z["schluessel"] for z in lohnarten_liste(db)}
    assert abwesenheiten(db, mia.id, date(2027, 2, 15), date(2027, 2, 15))[0]["stunden"] == D("7.50")  # Mo, Sollzeit des Modells
    heiligabend = next(e for e in r.json()["eintraege"] if e["schluessel"] == "heiligabend")
    neu = _eintrag(name="Heiligabend", monat=12, tag=24, sollzeit="6.5", abwesenheit="Heiligabend – bezahlte Freistellung")
    assert client.put(f"{KALENDER}/{heiligabend['id']}", json=neu).status_code == 200
    db.expire_all()
    assert soll(db, mia.id, date(2026, 12, 24)) == D("6.50") and kalendertag(db, mia.id, date(2026, 12, 24)).schluessel == "heiligabend"
    assert client.put(f"{KALENDER}/{heiligabend['id']}", json={**neu, "aktiv": False}).status_code == 200
    db.expire_all()
    assert soll(db, mia.id, date(2026, 12, 24)) == D("7.50") and abwesenheiten(db, mia.id, date(2026, 12, 24), date(2026, 12, 24)) == []


@pytest.mark.parametrize("aenderung, meldung", [
    ({"monat": 12, "tag": 24}, "Für den 24.12. steht schon „Heiligabend“ im Kalender."),
    ({"monat": 2, "tag": 30}, "Diesen Tag gibt es nicht."),
    ({"im_urlaub": "irgendwas"}, "Unbekannte Angabe „Im Urlaub“."),
    ({"name": " "}, "Bitte einen Namen angeben, z. B. Heiligabend."),
    ({"abwesenheit": ""}, "Bitte die Abwesenheit angeben, z. B. „Heiligabend – bezahlte Freistellung“."),
], ids=["doppelt", "kein_tag", "im_urlaub", "ohne_name", "ohne_abwesenheit"])
def test_abgelehnte_eingaben(welt, aenderung, meldung):
    r = _als(welt).post(KALENDER, json=_eintrag(**aenderung))
    assert (r.status_code, r.json()["detail"]) == (422, meldung)
    assert len(eintraege(welt["db"])) == 2  # Heiligabend, seit 1.9.176 Silvester


@pytest.mark.parametrize("feld", ["sollzeit", "aktiv", "im_urlaub"])
def test_jedes_feld_ist_pflicht(welt, feld):
    body = _eintrag()
    del body[feld]
    assert _als(welt).post(KALENDER, json=body).status_code == 422


@pytest.mark.parametrize("wert", ["-1", "24.5"])
def test_sollzeit_zwischen_0_und_24(welt, wert):
    assert _als(welt).post(KALENDER, json=_eintrag(sollzeit=wert)).status_code == 422


def test_zuordnung_des_kalendertags(welt):
    db = welt["db"]
    lohnart_speichern(db, "kalender:heiligabend", "BF", "1234", False)
    assert kalender_zuordnung(db, "heiligabend")["exportiert"] is True
    lohnart_speichern(db, "kalender:heiligabend", "bf", None, False)
    assert kalender_zuordnung(db, "heiligabend") == {"kennzeichen": "BF", "lohnart": None, "schluessel": "kalender:heiligabend", "exportiert": False}
    with pytest.raises(ValueError, match="Zum Kennzeichen gehört eine Lohnart"):
        lohnart_speichern(db, "arbeit", "1", None, False)  # nur am Kalendertag ohne Lohnart
    with pytest.raises(ValueError, match="Unbekannter Eintrag"):
        lohnart_speichern(db, "kalender:gibtsnicht", "AF", None, False)


def test_pruefskript_nennt_den_kalender(welt):
    from tests.test_v590_pruefe_zeitregeln import _skript
    zeilen = []
    _skript().main([], sitzung=welt["db"], ausgabe=zeilen.append, heute=date(2026, 11, 10))  # Rückgabe 1: die Personen haben keine Personalnummer
    assert "Arbeitszeitkalender: 2 Tage" in zeilen  # seit 1.9.176 mit Silvester
    assert ("  24.12. Heiligabend: Sollzeit 7,00 h, Heiligabend – bezahlte Freistellung, im Urlaub kein_urlaubstag, gewerbliche, nur Mo–Fr"
            in zeilen)
    assert "  kalender:heiligabend: BF / Lohnart offen" in zeilen


def test_seiten():
    from tests import vorlagen_js as vj
    einstellungen = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    for teil in ('id="kalenderBlock"', 'id="kalenderDialog"', "api('/api/time-backoffice/arbeitszeitkalender')", "data-klick=\"kalender-oeffnen\""):
        assert teil in einstellungen, teil
    zeiten = (vj.TEMPLATES / "zeiten.html").read_text(encoding="utf-8")
    assert 'id="abwKalender"' in zeiten and "d.kalender||[]" in zeiten


# --- Migration fcbfd2cea2da -----------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        c.execute(text("INSERT INTO employee_absences (employee_id, absence_type, absence_category, start_date, end_date, halber_tag, created_at, "
                       "updated_at) VALUES ((SELECT id FROM employees), 'Urlaub', 'urlaub', '2026-12-21', '2026-12-31', :f, '2026-09-01', '2026-09-01')"),
                  {"f": False})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM arbeitszeit_kalendertage")).scalar() == 0  # die Vorgaben legt der Start an
        assert c.execute(text("SELECT count(*) FROM employee_absences")).scalar() == 1
        c.execute(text("INSERT INTO arbeitszeit_kalendertage (schluessel, name, monat, tag, abwesenheit, created_at, updated_at) "
                       "VALUES ('heiligabend', 'Heiligabend', 12, 24, 'frei', '2026-11-03', '2026-11-03')"))
        assert c.execute(text("SELECT bezahlt, im_urlaub, nur_gewerblich, nur_mo_fr, aktiv FROM arbeitszeit_kalendertage")).one() == (
            True, "kein_urlaubstag", True, True, True)
        c.execute(text("INSERT INTO lohnart_zuordnungen (schluessel, kennzeichen, monatszeile, updated_at) VALUES ('kalender:heiligabend', 'BF', :f, "
                       "'2026-11-03')"), {"f": False})
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM lohnart_zuordnungen WHERE schluessel LIKE 'kalender:%'")).scalar() == 0
        assert c.execute(text("SELECT count(*) FROM employee_absences")).scalar() == 1
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'kalender.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_kal_{uuid.uuid4().hex[:8]}"
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
