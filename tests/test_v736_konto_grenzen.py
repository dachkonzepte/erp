"""Version 1.9.336 (Lohn L2c-3, Punkt 3; Antwort B9): Grenzen des Arbeitszeitkontos.

    Zeitregeln  „Hinweis ab Plus … h“ und „Hinweis ab Minus … h“ (TimeTrackingSettings.konto_hinweis_plus/_minus, Migration 7c2e4a9b1d53): leer = kein Hinweis,
                sonst ein Betrag größer 0 (höchstens 9.999,99), gespeichert über PUT /api/time-backoffice/konten/vorgaben (darf_lohnregeln())
    Hinweis     ab der Plus-Grenze (Stand ≥ Plus) bzw. ab der Minus-Grenze (Stand ≤ −Minus): „Stand +42,50 h – Hinweis ab Plus 40,00 h“; ohne Startwert keiner
    Prüfen      Karte „Arbeitszeitkonto an der Grenze“ (Stand bis gestern) -- nur Admin und Büro – Finanzen; ohne Grenze keine Rechnung; keine Sperre
    Person      in „Monat & Lohn“ an der Person (Stand am Monatsende bzw. bis gestern), Schlüssel grenze in GET /api/zeiten/arbeitszeitkonto
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.arbeitszeitkonto import grenze_text, grenzen_hinweise
from app.lohnkonten import grenze_wert, vorgaben
from app.models import EmployeePayrollSettings, LohnStartwert, TimeTrackingSettings
from app.routers import time_backoffice as backoffice_router
from app.routers import zeiten as zeiten_router
from tests import vorlagen_js as vj
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.uhr import uhr_festhalten

MIGRATION, VORHER = "7c2e4a9b1d53", "517c94f6dbcf"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
HEUTE = date(2027, 1, 5)  # gezählt bis 04.01.: Neujahr neutral, der 04.01. ohne Eintrag −7,50


@pytest.fixture
def w(threaded_db_session, router_test_client):
    db = threaded_db_session
    leute = {}
    for nr, vor, start in (("M-1", "Plus", Decimal("50")), ("M-2", "Minus", Decimal("-15")), ("M-3", "Ohne", None), ("M-4", "Mitte", Decimal("10"))):
        e = make_employee(db, nr, vor, "Person")
        e.employee_group = "gewerblich"
        db.add(EmployeePayrollSettings(employee_id=e.id, export_umfang="alles", payroll_export_enabled=True, eintritt=date(2020, 1, 1)))
        if start is not None:
            db.add(LohnStartwert(employee_id=e.id, stichtag=date(2026, 12, 31), saldo_stunden=start))
        leute[vor] = e
    db.commit()
    return {"db": db, "leute": leute, "client": lambda rolle="buero_finanzen", *routers: router_test_client(
        db, *(routers or (zeiten_router.router, backoffice_router.router)), role=rolle, user_id=7, display_name="Fin Finanzen")}


def _grenzen(db, plus, minus):
    s = db.get(TimeTrackingSettings, 1)
    s.konto_hinweis_plus, s.konto_hinweis_minus = plus, minus
    db.commit()


def test_grenze_wert():
    assert grenze_wert(None, "x") is None and grenze_wert("", "x") is None
    assert grenze_wert("40", "x") == Decimal("40.00") and grenze_wert(Decimal("0.125"), "x") == Decimal("0.13")
    for falsch in (0, "-5", "10000", "abc"):
        with pytest.raises(ValueError):
            grenze_wert(falsch, "Hinweis ab Plus")


def test_grenze_text():
    p, m = Decimal("40"), Decimal("20")
    assert grenze_text(Decimal("40"), p, m) == "Stand +40,00 h – Hinweis ab Plus 40,00 h"
    assert grenze_text(Decimal("39.75"), p, m) is None and grenze_text(Decimal("-19.75"), p, m) is None
    assert grenze_text(Decimal("-20"), p, m) == "Stand -20,00 h – Hinweis ab Minus 20,00 h"
    assert grenze_text(Decimal("100"), None, None) is None and grenze_text(Decimal("-100"), p, None) is None


def test_vorgaben_speichern_und_leer(w):
    c = w["client"]()
    r = c.put("/api/time-backoffice/konten/vorgaben", json={"konto_hinweis_plus": "40", "konto_hinweis_minus": 20})
    assert r.status_code == 200, r.text
    assert (r.json()["konto_hinweis_plus"], r.json()["konto_hinweis_minus"]) == ("40.00", "20.00")
    assert c.put("/api/time-backoffice/konten/vorgaben", json={"konto_hinweis_plus": None}).json()["konto_hinweis_plus"] is None
    assert vorgaben(w["db"])["konto_hinweis_minus"] == Decimal("20.00")  # nicht gesendet: bleibt (Teil-Update)
    r = c.put("/api/time-backoffice/konten/vorgaben", json={"konto_hinweis_minus": 0})
    assert r.status_code == 422 and r.json()["detail"].startswith("Hinweis ab Minus: größer als 0")
    assert w["client"]("buero_auftrag").put("/api/time-backoffice/konten/vorgaben", json={"konto_hinweis_plus": 1}).status_code == 403


def test_hinweise_in_pruefen(w):
    db = w["db"]
    assert grenzen_hinweise(db, HEUTE) == []  # ohne Grenze
    _grenzen(db, Decimal("40"), Decimal("5"))
    texte = [x["text"] for x in grenzen_hinweise(db, HEUTE)]
    # Stand bis 04.01.: Startwert − 7,50 (der 04.01. ohne Eintrag): Plus 42,50, Minus −22,50, Mitte 2,50; „Ohne“ stünde bei −7,50 (unter −5), hat aber
    # keinen Startwert -- kein Hinweis
    assert texte == ["Minus Person: Stand -22,50 h – Hinweis ab Minus 5,00 h", "Plus Person: Stand +42,50 h – Hinweis ab Plus 40,00 h"]
    assert grenzen_hinweise(db, date(2026, 12, 20)) == []  # vor dem Kontobeginn
    with uhr_festhalten(tag=HEUTE):
        for rolle, n in (("buero_finanzen", 2), ("admin", 2), ("buero_auftrag", 0)):
            r = w["client"](rolle).get("/api/zeiten/pruefen")
            assert r.status_code == 200 and len(r.json()["konto_grenzen"]) == n, rolle


def test_an_der_person(w):
    db = w["db"]
    _grenzen(db, Decimal("40"), None)
    with uhr_festhalten(tag=HEUTE):
        d = w["client"]().get("/api/zeiten/arbeitszeitkonto", params={"monat": "2027-01"}).json()
    je = {k["name"]: k["grenze"] for k in d["konten"]}
    assert je == {"Minus Person": None, "Mitte Person": None, "Ohne Person": None, "Plus Person": "Stand +42,50 h – Hinweis ab Plus 40,00 h"}
    assert d["grenzen"] == {"plus": 40, "minus": None}
    _grenzen(db, None, Decimal("5"))  # „Ohne“ stünde bei −7,50 unter −5 -- ohne Startwert trotzdem kein Hinweis
    with uhr_festhalten(tag=HEUTE):
        d = w["client"]().get("/api/zeiten/arbeitszeitkonto", params={"monat": "2027-01"}).json()
    je = {k["name"]: k["grenze"] for k in d["konten"]}
    assert je["Minus Person"] == "Stand -22,50 h – Hinweis ab Minus 5,00 h" and je["Ohne Person"] is None and je["Plus Person"] is None


def test_seite():
    z = vj.seitentext("zeiten.html")[0]
    assert '<section class="karte" id="grenzeKarte" aria-labelledby="grenzeTitel" hidden>' in z
    assert "var kg=d.konto_grenzen||[];" in z and "el('grenzeKarte').hidden=!kg.length;" in z
    assert "+(k.grenze?'<span class=\"konto-grenze\" data-grenze>'+esc(k.grenze.replace(/^Stand [^–]*– /,''))+'</span>':'')" in z
    s = vj.seitentext("settings.html")[0]
    assert '<input id="kvPlus" type="text" inputmode="decimal" data-zahl data-stellen="2" data-feld="Hinweis ab Plus" placeholder="z. B. 40">' in s
    assert "konto_hinweis_plus:zahlFeld('kvPlus'),konto_hinweis_minus:zahlFeld('kvMinus')" in s


def _zeitregeln_anlegen(engine) -> None:
    """Eine Zeile der Zeitregeln im Stand vor der Migration -- jede Pflichtspalte ohne Vorgabe mit einem leeren Wert ihres Typs."""
    from sqlalchemy import inspect as sa_inspect
    spalten = [s for s in sa_inspect(engine).get_columns("time_tracking_settings") if not s["nullable"] and s.get("default") is None
               and s["name"] != "id"]
    werte = {}
    for s in spalten:
        typ = str(s["type"]).upper()
        werte[s["name"]] = (False if "BOOL" in typ else 0 if any(x in typ for x in ("INT", "NUMERIC", "DECIMAL", "FLOAT"))
                            else "2026-01-01 00:00:00" if "TIME" in typ else "")
    namen = ", ".join(["id"] + list(werte))
    platz = ", ".join([":id"] + [f":{n}" for n in werte])
    with engine.begin() as c:
        if not c.execute(text("SELECT count(*) FROM time_tracking_settings")).scalar():
            c.execute(text(f"INSERT INTO time_tracking_settings ({namen}) VALUES ({platz})"), {"id": 1, **werte})


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _zeitregeln_anlegen(engine)  # der Bestand: Zeitregeln ohne Grenzen
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        assert tuple(c.execute(text("SELECT konto_hinweis_plus, konto_hinweis_minus FROM time_tracking_settings")).one()) == (None, None)
    with engine.begin() as c:
        c.execute(text("UPDATE time_tracking_settings SET konto_hinweis_plus = 40"))
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "Downgrade abgebrochen" in (nein.stdout + nein.stderr)
    with engine.begin() as c:
        c.execute(text("UPDATE time_tracking_settings SET konto_hinweis_plus = NULL"))
    _ok(_alembic(url, "downgrade", VORHER))
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'konto_grenzen.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_kontogrenzen_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
