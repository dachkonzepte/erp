"""Version 1.9.170 (Lohn L1a, Punkt 5, Entscheidung Tobias E5): Ausfalltag Schlechtwetter.

    Kategorie    schlechtwetter an EmployeeAbsence, je Person und Tag; Winter/Sommer nach Datum (app/lohnarten.py)
    eintragen    Admin, Büro – Finanzen, Kolonnenführer, Vorarbeiter für jeden gewerblichen Mitarbeiter -- gilt sofort; jede andere Person für
                 sich -- ein Antrag, den Kolonnenführer, Vorarbeiter oder Admin bestätigt (Büro – Finanzen nicht)
    abgelehnt    Sa, So, gesetzlicher Feiertag, Tag ohne Sollzeit, nicht gewerblich -- alles oder nichts, 422 mit Liste
    Warnung      gebuchte oder laufende Zeit an dem Tag -- 409, gespeichert erst mit „trotzdem“
    Zeitarten    weather_* inaktiv (Migration e4b7d1a93c56), keine Kachel mehr; Gebuchtes bleibt lesbar
    Vorarbeiter  Kennzeichen am Mitarbeiter (vorher nur Text)

Feste Tage: Dezember 2026 (Winter), fester Tag der Uhr 10.11.2026.
"""

import os
import uuid
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text

from app.models import (EmployeeAbsence, EmployeeAbsenceRequest, EmployeeRoleSettings, SettingOption, SettingOptionGroup, TeamEmployee,
                        TimeEntry)
from app.routers import absence_requests as absence_router
from app.routers import employees as employees_router
from app.routers import schlechtwetter as schlechtwetter_router
from app.sollzeit import zeile_anlegen
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MO, SA, SO, WEIHNACHTEN = date(2026, 12, 7), date(2026, 12, 5), date(2026, 12, 6), date(2026, 12, 25)
MIGRATION = "e4b7d1a93c56"
VORHER = "d8f2a6c4e913"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom, kai = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur"), make_employee(db, "M-3", "Kai", "Kolonne")
    uwe, vera = make_employee(db, "M-4", "Uwe", "Ohnekolonne"), make_employee(db, "M-5", "Vera", "Vorarbeiterin")
    bea = make_employee(db, "B-1", "Bea", "Buero")
    bea.employee_group = "kaufmaennisch"
    team = make_team(db, "K-1", "Kolonne 1")
    db.add_all([TeamEmployee(team_id=team.id, employee_id=kai.id, is_crew_leader=True), TeamEmployee(team_id=team.id, employee_id=mia.id),
                TeamEmployee(team_id=team.id, employee_id=tom.id), EmployeeRoleSettings(employee_id=vera.id, vorarbeiter=True)])
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "kai": kai, "uwe": uwe, "vera": vera, "bea": bea, "team": team, "client": router_test_client}


def _als(w, rolle="admin", wer=None, user_id=7):
    w["db"].commit()
    return w["client"](w["db"], schlechtwetter_router.router, absence_router.router, employees_router.router, role=rolle,
                       employee_id=w[wer].id if wer else None, user_id=user_id)


def _eintragen(client, *leute, tag=MO, trotzdem=False):
    return client.post("/api/schlechtwetter", json={"employee_ids": [p.id for p in leute], "tag": tag.isoformat(), "trotzdem": trotzdem})


def _abwesenheiten(w):
    w["db"].expire_all()
    return sorted((a.employee_id, a.start_date, a.end_date, a.absence_category, a.absence_type) for a in w["db"].query(EmployeeAbsence))


# --- eintragen: wer, gilt sofort -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle, wer", [("admin", None), ("buero_finanzen", None), ("field", "kai"), ("field", "vera")],
                         ids=["admin", "buero_finanzen", "kolonnenfuehrer", "vorarbeiterin"])
def test_eintragen_gilt_sofort(welt, rolle, wer):
    """Für jeden gewerblichen Mitarbeiter, auch außerhalb der eigenen Kolonne (Uwe) -- genehmigt, ein Tag, Art „Schlechtwetter“."""
    r = _eintragen(_als(welt, rolle, wer), welt["mia"], welt["uwe"])
    assert r.status_code == 200, r.text
    assert (r.json()["genehmigt"], [a["status"] for a in r.json()["antraege"]]) == (True, ["approved", "approved"])
    assert _abwesenheiten(welt) == sorted([(welt["mia"].id, MO, MO, "schlechtwetter", "Schlechtwetter"),
                                           (welt["uwe"].id, MO, MO, "schlechtwetter", "Schlechtwetter")])


def test_monteurin_beantragt_fuer_sich(welt):
    """Tom ohne Kennzeichen: für sich ein Antrag (offen, keine Abwesenheit); für Mia 403."""
    client = _als(welt, "field", "tom")
    r = _eintragen(client, welt["tom"])
    assert r.status_code == 200, r.text
    assert (r.json()["genehmigt"], r.json()["antraege"][0]["status"]) == (False, "pending")
    assert _abwesenheiten(welt) == []
    fremd = _eintragen(client, welt["mia"])
    assert fremd.status_code == 403 and "für dich" in fremd.json()["detail"]


@pytest.mark.parametrize("rolle, wer, darf", [("field", "kai", True), ("field", "vera", True), ("admin", None, True),
                                              ("buero_finanzen", None, False), ("field", "mia", False)],
                         ids=["kolonnenfuehrer", "vorarbeiterin", "admin", "buero_finanzen", "monteurin"])
def test_antrag_bestaetigen(welt, rolle, wer, darf):
    _eintragen(_als(welt, "field", "tom"), welt["tom"])
    antrag = welt["db"].scalar(select(EmployeeAbsenceRequest.id))
    r = _als(welt, rolle, wer).post(f"/api/schlechtwetter/{antrag}/entscheiden", json={"decision": "approved"})
    if not darf:
        assert r.status_code == 403 and _abwesenheiten(welt) == []
        return
    assert (r.status_code, r.json()["status"]) == (200, "approved")
    assert _abwesenheiten(welt) == [(welt["tom"].id, MO, MO, "schlechtwetter", "Schlechtwetter")]


def test_antrag_ablehnen(welt):
    _eintragen(_als(welt, "field", "tom"), welt["tom"])
    antrag = welt["db"].scalar(select(EmployeeAbsenceRequest.id))
    r = _als(welt, "field", "kai").post(f"/api/schlechtwetter/{antrag}/entscheiden", json={"decision": "rejected"})
    assert (r.status_code, r.json()["status"], _abwesenheiten(welt)) == (200, "rejected", [])


# --- abgelehnte Tage, alles oder nichts ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tag, teil", [(SA, "Samstag 05.12.2026 ist kein Arbeitstag"), (SO, "Sonntag 06.12.2026 ist kein Arbeitstag"),
                                       (WEIHNACHTEN, "25.12.2026 ist ein Feiertag (1. Weihnachtstag)")], ids=["sa", "so", "feiertag"])
def test_kein_arbeitstag(welt, tag, teil):
    r = _eintragen(_als(welt), welt["mia"], tag=tag)
    assert r.status_code == 422 and teil in r.json()["detail"], r.text
    assert _abwesenheiten(welt) == []


def test_tag_ohne_soll_und_nicht_gewerblich_nichts_gespeichert(welt):
    """Mia hat montags keine Sollzeit (eigene Werte), Bea ist kaufmännisch -- Tom wäre gültig, trotzdem wird keiner eingetragen."""
    zeile_anlegen(welt["db"], welt["mia"].id, date(2026, 12, 1), {"dienstag": Decimal("4")})
    r = _eintragen(_als(welt), welt["tom"], welt["mia"], welt["bea"])
    assert r.status_code == 422
    texte = [x["text"] for x in r.json()["liste"]]
    assert texte == ["Mia Monteurin: am 07.12.2026 keine Sollzeit", "Bea Buero: Schlechtwetter nur für gewerbliche Mitarbeiter"]
    assert _abwesenheiten(welt) == [] and welt["db"].query(EmployeeAbsenceRequest).count() == 0


def test_schon_abwesend(welt):
    client = _als(welt)
    assert _eintragen(client, welt["mia"]).status_code == 200
    r = _eintragen(client, welt["mia"], welt["tom"])
    assert r.status_code == 422 and "bereits" in r.json()["detail"]
    assert [a[0] for a in _abwesenheiten(welt)] == [welt["mia"].id]


def test_gebuchte_zeit_warnung_und_trotzdem(welt):
    db = welt["db"]
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0588"))
    db.add(TimeEntry(employee_id=welt["mia"].id, project_id=order.project_id, order_id=order.id, work_date=MO, entry_type="site",
                     hours=Decimal("3.5"), break_minutes=0, status="booked", started_at=datetime.combine(MO, time(7)),
                     ended_at=datetime.combine(MO, time(10, 30))))
    client = _als(welt)
    r = _eintragen(client, welt["mia"], welt["tom"])
    assert r.status_code == 409 and [w["text"] for w in r.json()["warnungen"]] == ["Mia Monteurin 3,50 h gebucht"]
    assert _abwesenheiten(welt) == []
    assert _eintragen(client, welt["mia"], welt["tom"], trotzdem=True).status_code == 200
    assert len(_abwesenheiten(welt)) == 2


def test_allgemeiner_weg_laesst_schlechtwetter_nicht_zu(welt):
    r = _als(welt).post("/api/absence-requests", json={"employee_id": welt["mia"].id, "absence_category": "schlechtwetter",
                                                       "start_date": MO.isoformat(), "end_date": MO.isoformat()})
    assert r.status_code == 422


# --- Kontext ------------------------------------------------------------------------------------------------------------------------------

def test_kontext(welt):
    _eintragen(_als(welt, "field", "tom"), welt["tom"])
    fuehrung = _als(welt, "field", "kai").get("/api/schlechtwetter/kontext").json()
    assert (fuehrung["fuer_andere"], fuehrung["bestaetigen"]) == (True, True)
    assert {p["name"] for p in fuehrung["personen"]} == {"Mia Monteurin", "Tom Monteur", "Kai Kolonne", "Uwe Ohnekolonne", "Vera Vorarbeiterin"}
    assert [(k["name"], sorted(k["mitglieder"])) for k in fuehrung["kolonnen"]] == [("Kolonne 1", sorted([welt["kai"].id, welt["mia"].id, welt["tom"].id]))]
    assert [(a["name"], a["tag"]) for a in fuehrung["antraege_offen"]] == [("Tom Monteur", MO.isoformat())]
    selbst = _als(welt, "field", "mia").get("/api/schlechtwetter/kontext").json()
    assert (selbst["fuer_andere"], selbst["bestaetigen"], selbst["personen"], selbst["kolonnen"], selbst["antraege_offen"]) == (
        False, False, [{"id": welt["mia"].id, "name": "Mia Monteurin"}], [], [])
    finanzen = _als(welt, "buero_finanzen").get("/api/schlechtwetter/kontext").json()
    assert (finanzen["fuer_andere"], finanzen["bestaetigen"], finanzen["antraege_offen"]) == (True, False, [])


def test_kolonnenfuehrer_einer_abgeschalteten_kolonne_ist_keiner(welt):
    welt["team"].active = False
    r = _eintragen(_als(welt, "field", "kai"), welt["mia"])
    assert r.status_code == 403


# --- Vorarbeiter am Mitarbeiter, Zeitarten, Ist-Wert ---------------------------------------------------------------------------------------

def test_vorarbeiter_im_mitarbeiterformular(welt):
    client = _als(welt, "buero_finanzen")
    stand = client.get(f"/api/employees/{welt['tom'].id}").json()
    assert stand["vorarbeiter"] is False
    koerper = {k: v for k, v in stand.items() if k not in ("id", "function_name", "effective_hourly_wage", "annual_gross_wage")}
    assert client.put(f"/api/employees/{welt['tom'].id}", json={**koerper, "vorarbeiter": True}).json()["vorarbeiter"] is True
    ohne = {k: v for k, v in koerper.items() if k != "vorarbeiter"}
    assert client.put(f"/api/employees/{welt['tom'].id}", json=ohne).json()["vorarbeiter"] is True  # weggelassen = unverändert
    assert _eintragen(_als(welt, "field", "tom"), welt["mia"]).json()["genehmigt"] is True


def test_zeitarten_schlechtwetter_inaktiv_bei_neuer_installation(welt):
    from app.heute import zeitarten
    db = welt["db"]
    gruppe = db.scalar(select(SettingOptionGroup).where(SettingOptionGroup.group_key == "time_entry_types"))
    inaktiv = {o.value for o in db.scalars(select(SettingOption).where(SettingOption.group_id == gruppe.id, SettingOption.active.is_(False)))}
    assert inaktiv == {"weather_winter", "weather_summer"}
    assert not {"weather_winter", "weather_summer"} & {z["value"] for z in zeitarten(db)}


def test_ist_wert_zaehlt_ausfalltage(welt):
    from app.productive_hours import weather_days_actual
    vorher = weather_days_actual(welt["db"], today=date(2027, 1, 15))["total_hours"]
    _eintragen(_als(welt), welt["mia"], welt["tom"])
    nachher = weather_days_actual(welt["db"], today=date(2027, 1, 15))["total_hours"]
    assert Decimal(str(nachher)) - Decimal(str(vorher or 0)) == 2 * Decimal(str(weather_days_actual(welt["db"])["daily_hours_used"]))


def test_baustein_in_beiden_seiten():
    from tests import vorlagen_js as vj
    for vorlage in ("zeiten.html", "mobil_zeiten.html"):
        assert vj.bindet_ein(vorlage, "_schlechtwetter.html"), vorlage
        assert "schlechtwetter:'Schlechtwetter'" in (vj.TEMPLATES / vorlage).read_text(encoding="utf-8"), vorlage


# --- Migration e4b7d1a93c56 ------------------------------------------------------------------------------------------------------------------

def _bestand(engine) -> None:
    with engine.begin() as c:
        c.execute(text("INSERT INTO setting_option_groups (group_key, label, sort_order, created_at, updated_at) "
                       "VALUES ('time_entry_types', 'Zeitarten', 1, '2026-09-01', '2026-09-01')"))
        gid = c.execute(text("SELECT id FROM setting_option_groups WHERE group_key = 'time_entry_types'")).scalar()
        for i, (label, wert) in enumerate((("Baustellenzeit", "site"), ("Schlechtwetter Winter", "weather_winter"), ("Schlechtwetter Sommer", "weather_summer"))):
            c.execute(text("INSERT INTO setting_options (group_id, label, value, sort_order, active, is_default, created_at, updated_at) "
                           "VALUES (:g, :l, :v, :s, :a, :d, '2026-09-01', '2026-09-01')"),
                      {"g": gid, "l": label, "v": wert, "s": i, "a": True, "d": False})
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        c.execute(text("INSERT INTO employee_role_settings (employee_id, available_as_caseworker, updated_at) VALUES "
                       "((SELECT id FROM employees), :f, '2026-09-01')"), {"f": False})


def _aktiv(engine) -> dict:
    with engine.connect() as c:
        return {v: bool(a) for v, a in c.execute(text("SELECT value, active FROM setting_options"))}


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _aktiv(engine) == {"site": True, "weather_winter": False, "weather_summer": False}
    with engine.connect() as c:
        assert [bool(x) for x in c.execute(text("SELECT vorarbeiter FROM employee_role_settings")).scalars()] == [False]
    _ok(_alembic(url, "downgrade", VORHER))
    assert _aktiv(engine) == {"site": True, "weather_winter": True, "weather_summer": True}
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'schlechtwetter.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_wetter_{uuid.uuid4().hex[:8]}"
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
