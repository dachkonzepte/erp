"""Version 1.9.167 (Lohn L1a, Punkt 2, Entscheidungen Tobias E3, E4 und E10): Sollzeit einer Person an einem Tag.

    Tarif         Montag bis Freitag das Arbeitszeitmodell des Tags: Sommer KW 18–48 8,00 h, Winter KW 49–17 7,50 h (ISO), Sa und So 0
    eigene Werte  je Person ab einem Tag, Montag bis Sonntag; eine Zeile ohne Werte heißt „wieder Tarif“; nie in einen abgeschlossenen Zeitraum
    Eintritt      davor und danach 0
    Rechte        Modelle, Pausenregeln, Zuordnung, Zeitregeln, Personalnummern, Eintritt, Austritt und Sollzeiten ändern nur Admin und
                  Büro – Finanzen; Büro – Auftrag liest
    Migration     b7e3c91d4a52 stellt die Startmodelle auf den Tarif um, nur wenn sie noch den Grundwerten entsprechen

Feste Tage (Fixture fester_tag), nicht relativ zu heute.
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.models import EmployeePayrollSettings, TimeTrackingSettings, WorkTimeModel
from app.routers import time_backoffice as time_backoffice_router
from app.sollzeit import soll, soll_zeitraum, zeile_anlegen
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

D = Decimal
MIGRATION = "b7e3c91d4a52"
VORHER = "f1b9d2c6a470"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    db.commit()
    return {"db": db, "mia": mia, "client": router_test_client}


def _als(w, rolle="buero_finanzen"):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, role=rolle)


# --- Tarif ------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tag, stunden", [
    (date(2026, 4, 24), "7.50"),   # Fr, KW 17: Winter (LIESMICH 7.: 7,50 bis Fr 24.04.2026)
    (date(2026, 4, 27), "8.00"),   # Mo, KW 18: Sommer (8,00 ab Mo 27.04.2026)
    (date(2026, 11, 27), "8.00"),  # Fr, KW 48
    (date(2026, 11, 30), "7.50"),  # Mo, KW 49
    (date(2026, 11, 28), "0"),     # Sa
    (date(2026, 11, 29), "0"),     # So
    (date(2026, 12, 31), "7.50"),  # Do, KW 53
    (date(2027, 1, 4), "7.50"),    # Mo, KW 1
    (date(2026, 5, 1), "8.00"),    # Feiertag: die Sollzeit des Wochentags (F trägt sie, E3)
], ids=["fr_kw17", "mo_kw18", "fr_kw48", "mo_kw49", "sa", "so", "kw53", "kw1", "feiertag"])
def test_tarif_nach_kalenderwoche(welt, tag, stunden):
    assert soll(welt["db"], welt["mia"].id, tag) == D(stunden)


def test_startmodelle_sind_der_tarif(welt):
    """Neue Installation (Grunddaten): Sommer KW 18–48 8,00 h, Winter KW 49–17 7,50 h."""
    from app.work_time_models import list_models
    modelle = {m["code"]: (m["valid_from_week"], m["valid_to_week"], D(str(m["daily_target_hours"]))) for m in list_models(welt["db"])}
    assert modelle == {"summer": (18, 48, D("8.00")), "winter": (49, 17, D("7.50"))}


# --- eigene Werte, Eintritt, Austritt -------------------------------------------------------------------------------------------------

def test_teilzeit_di_bis_do_und_zurueck_zum_tarif(welt):
    db, mia = welt["db"], welt["mia"]
    zeile_anlegen(db, mia.id, date(2026, 12, 1), {"dienstag": D("3"), "mittwoch": D("3"), "donnerstag": D("3")})
    zeile_anlegen(db, mia.id, date(2027, 1, 1), None)
    tage = soll_zeitraum(db, mia.id, date(2026, 11, 30), date(2026, 12, 7))
    assert [str(tage[t]) for t in sorted(tage)] == ["7.50", "3.00", "3.00", "3.00", "0.00", "0.00", "0.00", "0.00"]
    assert soll(db, mia.id, date(2027, 1, 4)) == D("7.50")


def test_eintritt_und_austritt(welt):
    db, mia = welt["db"], welt["mia"]
    db.add(EmployeePayrollSettings(employee_id=mia.id, payroll_export_enabled=True, eintritt=date(2026, 11, 5), austritt=date(2026, 11, 20)))
    db.commit()
    assert [soll(db, mia.id, t) for t in (date(2026, 11, 4), date(2026, 11, 5), date(2026, 11, 20), date(2026, 11, 23))] == [
        D("0"), D("8.00"), D("8.00"), D("0")]


# --- Schnittstelle -----------------------------------------------------------------------------------------------------------------------

def test_sollzeit_anlegen_lesen_loeschen(welt):
    client, mia = _als(welt), welt["mia"]
    r = client.post(f"/api/time-backoffice/sollzeiten/{mia.id}", json={"valid_from": "2026-12-01", "werte": {"dienstag": "3", "mittwoch": "3"}})
    assert r.status_code == 200, r.text
    z = r.json()
    assert (z["tarif"], z["text"]) == (False, "Di 3,00 · Mi 3,00 h")
    tarif = client.post(f"/api/time-backoffice/sollzeiten/{mia.id}", json={"valid_from": "2027-01-01", "werte": None}).json()
    assert (tarif["tarif"], tarif["text"]) == (True, "Tarif")
    liste = _als(welt, "buero_auftrag").get(f"/api/time-backoffice/sollzeiten/{mia.id}")
    assert (liste.status_code, [x["valid_from"] for x in liste.json()]) == (200, ["2026-12-01", "2027-01-01"])
    zeile = [x for x in _als(welt).get("/api/time-backoffice/payroll-employees").json() if x["employee_id"] == mia.id][0]
    assert [x["text"] for x in zeile["sollzeiten"]] == ["Di 3,00 · Mi 3,00 h", "Tarif"]
    assert client.delete(f"/api/time-backoffice/sollzeiten/zeile/{z['id']}").status_code == 200
    assert soll(welt["db"], mia.id, date(2026, 12, 1)) == D("7.50")


@pytest.mark.parametrize("werte, teil", [({"montag": "25"}, "zwischen 0 und 24"), ({"feiertag": "2"}, "Unbekannter Wochentag"),
                                         ({"montag": "-1"}, "zwischen 0 und 24")])
def test_sollzeit_falsche_werte_422(welt, werte, teil):
    r = _als(welt).post(f"/api/time-backoffice/sollzeiten/{welt['mia'].id}", json={"valid_from": "2026-12-01", "werte": werte})
    assert r.status_code == 422 and teil in r.text


def test_sollzeit_nie_im_abgeschlossenen_zeitraum(welt):
    """Angriff: „gültig ab“ am oder vor „Abgeschlossen bis“ -> 409, nichts gespeichert; eine Zeile, die dort schon gilt, lässt sich nicht
    löschen. Gegenprobe: am Tag danach geht es."""
    db, mia = welt["db"], welt["mia"]
    alt = zeile_anlegen(db, mia.id, date(2026, 10, 1), {"montag": D("4")})
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 10, 31)
    client = _als(welt)
    r = client.post(f"/api/time-backoffice/sollzeiten/{mia.id}", json={"valid_from": "2026-10-31", "werte": {"montag": "5"}})
    assert r.status_code == 409 and "abgeschlossen bis 31.10.2026" in r.json()["detail"]
    assert client.delete(f"/api/time-backoffice/sollzeiten/zeile/{alt.id}").status_code == 409
    assert client.post(f"/api/time-backoffice/sollzeiten/{mia.id}", json={"valid_from": "2026-11-01", "werte": {"montag": "5"}}).status_code == 200
    assert soll(db, mia.id, date(2026, 10, 26)) == D("4.00") and soll(db, mia.id, date(2026, 11, 2)) == D("5.00")


def test_lohnstammdaten_teil_update(welt):
    """Seit 1.9.167 ein Teil-Update: nur der Eintritt -> Personalnummer und Export bleiben (bis 1.9.166 hieß ein fehlendes Feld „Export an“
    und „keine Nummer“). Austritt vor Eintritt 422."""
    client, mia = _als(welt), welt["mia"]
    assert client.put(f"/api/time-backoffice/payroll-employees/{mia.id}", json={"datev_personnel_number": "91001",
                                                                                "payroll_export_enabled": False}).status_code == 200
    r = client.put(f"/api/time-backoffice/payroll-employees/{mia.id}", json={"eintritt": "2026-11-05"})
    assert r.status_code == 200, r.text
    assert (r.json()["datev_personnel_number"], r.json()["payroll_export_enabled"], r.json()["eintritt"]) == ("91001", False, "2026-11-05")
    falsch = client.put(f"/api/time-backoffice/payroll-employees/{mia.id}", json={"austritt": "2026-11-01"})
    assert falsch.status_code == 422 and "vor dem Eintritt" in falsch.text


# --- Rechte (E10) ------------------------------------------------------------------------------------------------------------------------

def _schreibende(w):
    modell = w["db"].query(WorkTimeModel).filter_by(code="summer").one()
    koerper = {"name": "Sommermodell", "code": "summer", "daily_target_hours": "8", "valid_from_week": 18, "valid_to_week": 48,
               "active": True, "sort_order": 10,
               "break_rules": [{"id": r.id, "threshold_hours": str(r.threshold_hours), "break_minutes": r.break_minutes} for r in modell.break_rules]}
    mia = w["mia"].id
    return [
        ("put", f"/api/time-backoffice/work-time-models/{modell.id}", koerper),
        ("post", "/api/time-backoffice/work-time-models", {**koerper, "name": "Teilzeit", "code": None,
                                                           "break_rules": [{"threshold_hours": "6", "break_minutes": 30}]}),
        ("put", f"/api/time-backoffice/work-time-assignments/{mia}", {"model_id": modell.id}),
        ("post", "/api/time-backoffice/work-time-assignments/bulk", {"employee_ids": [mia], "model_id": modell.id}),
        ("put", f"/api/time-backoffice/payroll-employees/{mia}", {"eintritt": "2026-11-05"}),
        ("post", f"/api/time-backoffice/sollzeiten/{mia}", {"valid_from": "2026-12-01", "werte": {"montag": "4"}}),
        ("put", "/api/time-backoffice/settings", {"allow_manual_entries": True, "allow_group_bookings": True,
                                                  "require_order_item": False, "require_activity": False}),
    ]


def test_buero_auftrag_liest_nur(welt):
    """Angriff: Büro – Auftrag ändert nichts (403 mit der Meldung), liest aber Modelle, Zuordnung, Personalnummern und Sollzeiten."""
    client = _als(welt, "buero_auftrag")
    for methode, pfad, koerper in _schreibende(welt):
        r = getattr(client, methode)(pfad, json=koerper)
        assert r.status_code == 403 and "du kannst sie lesen" in r.json()["detail"], (pfad, r.status_code, r.text)
    for pfad in ("/api/time-backoffice/work-time-models", "/api/time-backoffice/work-time-assignments", "/api/time-backoffice/payroll-employees",
                 f"/api/time-backoffice/sollzeiten/{welt['mia'].id}", "/api/time-backoffice/settings"):
        assert client.get(pfad).status_code == 200, pfad


@pytest.mark.parametrize("rolle", ["buero_finanzen", "admin"])
def test_finanzen_und_admin_aendern(welt, rolle):
    client = _als(welt, rolle)
    for methode, pfad, koerper in _schreibende(welt):
        r = getattr(client, methode)(pfad, json=koerper)
        assert r.status_code == 200, (pfad, r.status_code, r.text)


def test_seite_liest_nur_ohne_lohnregeln():
    """Die Einstellungen sperren den Bereich „Zeitregeln und DATEV“ ohne darf_lohnregeln(): Hinweis aus der Seitenroute, Felder gesperrt,
    Knöpfe mit data-lohnregeln-knopf ausgeblendet -- nach jedem Zeichnen."""
    from tests import vorlagen_js as vj
    html = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert "{% if not lohnregeln %}<div class=\"hint\" data-lohnregeln-hinweis>{{ lohnregeln_nur_lesen }}</div>{% endif %}" in html
    text = vj.eigene_skripte("settings.html").text
    assert text.count("lohnregelnNurLesen()") >= 4  # Zeitregeln, Modelle, Zuordnung, Personalnummern
    for knopf in ("saveTimeRules()\" data-lohnregeln-knopf", "newModel()\" data-lohnregeln-knopf", "assignBulkModel()\" data-lohnregeln-knopf"):
        assert knopf in html, knopf
    for knopf in ('data-klick="lohn-speichern" data-mitarbeiter="${p.employee_id}" data-lohnregeln-knopf',
                  'data-klick="sollzeit-oeffnen" data-mitarbeiter="${p.employee_id}" data-lohnregeln-knopf',
                  'data-klick="modell-bearbeiten" data-id="${m.id}" data-lohnregeln-knopf'):
        assert knopf in text, knopf


# --- Migration b7e3c91d4a52 ---------------------------------------------------------------------------------------------------------------

def _bestand(engine) -> None:
    """Stand f1b9d2c6a470: Sommer mit den Grundwerten, Winter von Hand auf 7,75 h geändert, ein drittes Modell ohne Kürzel."""
    with engine.begin() as c:
        def modell(name, code, stunden, von, bis):
            c.execute(text("INSERT INTO work_time_models (name, code, daily_target_hours, active, sort_order, created_at, updated_at) "
                           "VALUES (:n, :c, :h, :a, 10, '2026-09-01 08:00:00', '2026-09-01 08:00:00')"), {"n": name, "c": code, "h": stunden, "a": True})
            mid = c.execute(text("SELECT max(id) FROM work_time_models")).scalar()
            c.execute(text("INSERT INTO work_time_model_validities (model_id, valid_from_week, valid_to_week, updated_at) "
                           "VALUES (:m, :v, :b, '2026-09-01 08:00:00')"), {"m": mid, "v": von, "b": bis})
        modell("Sommermodell", "summer", "8.00", 13, 43)
        modell("Wintermodell", "winter", "7.75", 44, 12)
        modell("Teilzeit", None, "8.00", 13, 43)


def _modelle(engine) -> list[tuple]:
    with engine.connect() as c:
        return [(n, int(v), int(b), str(D(str(h)).quantize(D("0.01")))) for n, v, b, h in c.execute(text(
            "SELECT m.name, v.valid_from_week, v.valid_to_week, m.daily_target_hours FROM work_time_models m "
            "JOIN work_time_model_validities v ON v.model_id = m.id ORDER BY m.id"))]


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine)
    vorher = _modelle(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _modelle(engine) == [("Sommermodell", 18, 48, "8.00"), ("Wintermodell", 44, 12, "7.75"), ("Teilzeit", 13, 43, "8.00")]
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        mia = c.execute(text("SELECT id FROM employees")).scalar()
        c.execute(text("INSERT INTO employee_target_hours (employee_id, valid_from, dienstag, created_at, updated_at) "
                       "VALUES (:e, '2026-12-01', 3, '2026-11-02', '2026-11-02')"), {"e": mia})
        c.execute(text("INSERT INTO employee_payroll_settings (employee_id, payroll_export_enabled, eintritt, updated_at) "
                       "VALUES (:e, :a, '2026-11-05', '2026-11-02')"), {"e": mia, "a": True})
    _ok(_alembic(url, "downgrade", VORHER))
    assert _modelle(engine) == vorher
    _ok(_alembic(url, "upgrade", "head"))
    assert _modelle(engine)[0] == ("Sommermodell", 18, 48, "8.00")


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'sollzeit.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_soll_{uuid.uuid4().hex[:8]}"
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
