"""Version 1.9.310 (Lohn L2a, Punkt 3; Antworten 11 und 12 des Befunds L2): Tabellen und Migration für Urlaubsanspruch und Startwerte (app/lohnkonten.py).

    Vorgaben    Zeitregeln: Urlaubsanspruch je Jahr (30 Tage, halbe erlaubt), Übertrag ins Folgejahr (von Hand | automatisch), Verfall „TT.MM.“ -- Teil-Update
    Anspruch    je Person und Jahr: Urlaubstage (leer = die Vorgabe), Übertrag (auch negativ), Verfallsdatum im Jahr des Anspruchs, Notiz -- Teil-Update
    Startwert   je Person: Stichtag 31.12.2026, Resturlaub in halben Tagen, Saldo in Stunden mit zwei Stellen (auch negativ), Herkunft, geprüft am / durch --
                ändert sich ein Wert ohne neue Prüfung, fällt sie weg; nach dem Abschluss des Januars 2027 nur der Admin
    Rechte      lesen: Admin und Büro – Finanzen alle, alle anderen nur die eigenen; ändern: Admin und Büro – Finanzen (darf_lohnregeln())
    Historie    Urlaubsanspruch und Startwert der Konten mit Namen; für Büro – Auftrag ohne die Werte (geschwärzt)
    Migration   562f81626c3b auf einem Bestand (SQLite und PostgreSQL): Vorgaben 30 / von Hand / leer; downgrade() bricht ab, solange etwas eingetragen ist
Stehende Uhr 10.11.2026 (fester_tag).
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text

from app.audit import reset_audit_context, set_audit_context
from app.models import AuditLog, LohnStartwert, TimeTrackingSettings, Urlaubsanspruch
from app.routers import audit as audit_router
from app.routers import time_backoffice as backoffice_router
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

D = Decimal
MIGRATION, VORHER = "562f81626c3b", "84ee228b331e"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
K = "/api/time-backoffice/konten"


class _Konto:
    id = None
    role = "admin"
    display_name = "Anna Admin"
    username = "anna"


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    ada, bea = make_employee(db, "M-1", "Ada", "Monteurin"), make_employee(db, "B-1", "Bea", "Büro")
    db.commit()
    token = set_audit_context(_Konto(), None)
    try:
        yield {"db": db, "ada": ada, "bea": bea, "client": router_test_client}
    finally:
        reset_audit_context(token)


def _als(w, rolle="admin", wer=None):
    w["db"].commit()
    return w["client"](w["db"], backoffice_router.router, audit_router.router, role=rolle, employee_id=w[wer].id if wer else None, user_id=9,
                       display_name={"admin": "Anna Admin", "buero_finanzen": "Fin Finanzen"}.get(rolle, rolle))


def _person(antwort, emp) -> dict:
    return next(p for p in antwort["personen"] if p["employee_id"] == emp.id)


# --- Vorgaben -------------------------------------------------------------------------------------------------------------------------------

def test_vorgaben_lesen_und_teil_update(w):
    c = _als(w, "buero_finanzen")
    r = c.get(K).json()
    assert r["vorgaben"] == {"urlaub_vorgabe_tage": "30.0", "urlaub_uebertrag": "von_hand", "urlaub_verfall": None}
    assert (r["stichtag"], r["jahr"], r["darf_aendern"], r["startwert_gesperrt"]) == ("2026-12-31", 2027, True, False)
    assert c.put(f"{K}/vorgaben", json={"urlaub_verfall": "31.3"}).json() == {"urlaub_vorgabe_tage": "30.0", "urlaub_uebertrag": "von_hand",
                                                                               "urlaub_verfall": "31.03."}
    assert c.put(f"{K}/vorgaben", json={"urlaub_vorgabe_tage": 28.5, "urlaub_uebertrag": "automatisch"}).json()["urlaub_verfall"] == "31.03."
    for body, meldung in (({"urlaub_vorgabe_tage": 28.3}, "in halben Tagen"), ({"urlaub_uebertrag": "immer"}, "„von Hand“ oder „automatisch“"),
                          ({"urlaub_verfall": "29.02."}, "nicht der 29.02."), ({"urlaub_verfall": "31.04."}, "TT.MM."),
                          ({"urlaub_vorgabe_tage": None}, "Darf nicht leer sein")):
        a = c.put(f"{K}/vorgaben", json=body)
        assert a.status_code == 422 and meldung in a.text, (body, a.text)
    w["db"].expire_all()
    s = w["db"].get(TimeTrackingSettings, 1)
    assert (s.urlaub_vorgabe_tage, s.urlaub_uebertrag, s.urlaub_verfall) == (D("28.5"), "automatisch", "31.03.")


# --- Anspruch -------------------------------------------------------------------------------------------------------------------------------

def test_anspruch_je_jahr(w):
    db, ada = w["db"], w["ada"]
    c = _als(w, "buero_finanzen")
    leer = _person(c.get(K).json(), ada)
    assert (leer["ansprueche"], leer["startwert"]) == ([], None)
    assert db.query(Urlaubsanspruch).count() == 0  # ein Lesepfad legt nichts an (Regel 23)
    # seit 1.9.312: der Übertrag 2027 ist der Startwert „Resturlaub“ -- am Anspruch 2027 abgelehnt; von Hand ab 2028 (Vorgabe „von Hand“)
    r = c.put(f"{K}/{ada.id}/anspruch/2027", json={"uebertrag": -1.5, "notiz": "Teilzeit 4 Tage"})
    assert (r.status_code, r.json()["detail"]) == (422, "Für 2027 ist der Übertrag der Startwert „Resturlaub“ – bitte dort eintragen.")
    p = c.put(f"{K}/{ada.id}/anspruch/2027", json={"notiz": "Teilzeit 4 Tage"}).json()
    assert p["ansprueche"] == [{"jahr": 2027, "urlaubstage": None, "urlaubstage_wirksam": "30.0", "vorgabe": True, "uebertrag": None,
                                "verfall_am": None, "notiz": "Teilzeit 4 Tage", "uebertrag_quelle": "startwert", "uebertrag_doppelt": False}]
    p = c.put(f"{K}/{ada.id}/anspruch/2027", json={"urlaubstage": 24, "verfall_am": "2027-03-31"}).json()  # Teil-Update: die Notiz bleibt
    assert p["ansprueche"][0] | {} == {"jahr": 2027, "urlaubstage": "24.0", "urlaubstage_wirksam": "24.0", "vorgabe": False, "uebertrag": None,
                                       "verfall_am": "2027-03-31", "notiz": "Teilzeit 4 Tage", "uebertrag_quelle": "startwert", "uebertrag_doppelt": False}
    p = c.put(f"{K}/{ada.id}/anspruch/2028", json={"urlaubstage": 30.5, "uebertrag": -1.5}).json()
    assert p["ansprueche"][1] == {"jahr": 2028, "urlaubstage": "30.5", "urlaubstage_wirksam": "30.5", "vorgabe": False, "uebertrag": "-1.5",
                                  "verfall_am": None, "notiz": None, "uebertrag_quelle": "von_hand", "uebertrag_doppelt": False}
    assert [a["jahr"] for a in _person(c.get(K).json(), ada)["ansprueche"]] == [2027, 2028]
    for jahr, body, status, meldung in ((2027, {"urlaubstage": 24.25}, 422, "in halben Tagen"), (2027, {"urlaubstage": -1}, 422, "zwischen 0"),
                                        (2027, {"verfall_am": "2028-03-31"}, 422, "im Jahr des Anspruchs (2027)"), (2101, {"urlaubstage": 1}, 422, "2100"),
                                        (2027, {"urlaubstage": "x"}, 422, None)):
        a = c.put(f"{K}/{ada.id}/anspruch/{jahr}", json=body)
        assert a.status_code == status and (meldung is None or meldung in a.text), (body, a.text)
    assert c.put(f"{K}/999999/anspruch/2027", json={"urlaubstage": 1}).status_code == 404


# --- Startwert ------------------------------------------------------------------------------------------------------------------------------

def test_startwert_mit_herkunft_und_pruefung(w):
    ada = w["ada"]
    c = _als(w, "buero_finanzen")
    p = c.put(f"{K}/{ada.id}/startwert", json={"resturlaub_tage": 4.5, "saldo_stunden": -12.25}).json()
    assert p["startwert"] == {"stichtag": "2026-12-31", "resturlaub_tage": "4.5", "saldo_stunden": "-12.25", "herkunft": "steuerbuero",
                              "herkunft_text": "Steuerbüro", "herkunft_notiz": None, "geprueft_am": None, "geprueft_von": None}
    p = c.put(f"{K}/{ada.id}/startwert", json={"herkunft_notiz": "Liste vom 30.12.2026", "geprueft": True}).json()["startwert"]
    assert (p["geprueft_am"], p["geprueft_von"], p["resturlaub_tage"]) == ("2026-11-10", "Fin Finanzen", "4.5")
    # derselbe Wert noch einmal: die Prüfung bleibt; ein anderer Wert ohne neue Prüfung: sie fällt weg
    assert c.put(f"{K}/{ada.id}/startwert", json={"resturlaub_tage": 4.5}).json()["startwert"]["geprueft_am"] == "2026-11-10"
    p = c.put(f"{K}/{ada.id}/startwert", json={"saldo_stunden": 3}).json()["startwert"]
    assert (p["saldo_stunden"], p["geprueft_am"], p["geprueft_von"]) == ("3.00", None, None)
    p = c.put(f"{K}/{ada.id}/startwert", json={"herkunft": "time4", "geprueft": True}).json()["startwert"]
    assert (p["herkunft_text"], p["geprueft_von"]) == ("Time 4", "Fin Finanzen")
    assert c.put(f"{K}/{ada.id}/startwert", json={"geprueft": False}).json()["startwert"]["geprueft_am"] is None
    for body, meldung in (({"resturlaub_tage": 4.4}, "in halben Tagen"), ({"saldo_stunden": 1.005}, "zwei Nachkommastellen"),
                          ({"saldo_stunden": 10000}, "9.999,99"), ({"herkunft": "excel"}, "Steuerbüro, Time 4 oder Sonstiges"),
                          ({"herkunft": None}, "Darf nicht leer sein"), ({"stichtag": None}, "Darf nicht leer sein")):
        a = c.put(f"{K}/{ada.id}/startwert", json=body)
        assert a.status_code == 422 and meldung in a.text, (body, a.text)


def test_startwert_nach_dem_januar_nur_der_admin(w):
    db, ada = w["db"], w["ada"]
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 12, 31)
    db.commit()
    assert _als(w, "buero_finanzen").put(f"{K}/{ada.id}/startwert", json={"resturlaub_tage": 2}).status_code == 200  # Dezember abgeschlossen: noch frei
    db.get(TimeTrackingSettings, 1).locked_until = date(2027, 1, 31)
    db.commit()
    fin = _als(w, "buero_finanzen")
    r = fin.put(f"{K}/{ada.id}/startwert", json={"resturlaub_tage": 3})
    assert (r.status_code, r.json()["detail"]) == (403, "Die Zeiterfassung ist bis 31.01.2027 abgeschlossen. Den Startwert ändert jetzt nur ein Administrator.")
    assert fin.get(K).json()["startwert_gesperrt"] is True and _als(w, "admin").get(K).json()["startwert_gesperrt"] is False
    assert fin.put(f"{K}/{ada.id}/anspruch/2027", json={"urlaubstage": 25}).status_code == 200  # der Anspruch bleibt änderbar
    assert _als(w, "admin").put(f"{K}/{ada.id}/startwert", json={"resturlaub_tage": 3}).json()["startwert"]["resturlaub_tage"] == "3.0"


# --- Rechte ---------------------------------------------------------------------------------------------------------------------------------

def test_wer_sieht_und_aendert_was(w):
    ada, bea = w["ada"], w["bea"]
    _als(w, "admin").put(f"{K}/{ada.id}/startwert", json={"resturlaub_tage": 1})
    _als(w, "admin").put(f"{K}/{bea.id}/startwert", json={"resturlaub_tage": 2})
    for rolle in ("admin", "buero_finanzen"):
        assert {p["employee_id"] for p in _als(w, rolle).get(K).json()["personen"]} >= {ada.id, bea.id}
    ba = _als(w, "buero_auftrag", "bea").get(K).json()
    assert ([p["employee_id"] for p in ba["personen"]], ba["darf_aendern"]) == ([bea.id], False)
    assert _als(w, "buero_auftrag").get(K).json()["personen"] == []  # ohne eigenen Mitarbeiter: keine
    assert _als(w, "field", "ada").get(K).status_code == 403
    for pfad, body in ((f"{K}/vorgaben", {"urlaub_vorgabe_tage": 1}), (f"{K}/{bea.id}/anspruch/2027", {"urlaubstage": 1}),
                       (f"{K}/{bea.id}/startwert", {"resturlaub_tage": 1})):
        assert _als(w, "buero_auftrag", "bea").put(pfad, json=body).status_code == 403, pfad


# --- Historie -------------------------------------------------------------------------------------------------------------------------------

def test_historie_mit_namen_und_fuer_buero_auftrag_geschwaerzt(w):
    db, ada = w["db"], w["ada"]
    c = _als(w, "admin")
    c.put(f"{K}/{ada.id}/anspruch/2027", json={"urlaubstage": 24})
    c.put(f"{K}/{ada.id}/startwert", json={"resturlaub_tage": 4.5, "saldo_stunden": 7})
    c.put(f"{K}/{ada.id}/startwert", json={"saldo_stunden": 8})
    db.commit()
    arten = {r.entity_type for r in db.scalars(select(AuditLog))}
    assert {"Urlaubsanspruch je Jahr", "Startwert der Konten"} <= arten
    admin = [z for z in c.get("/api/audit-logs?limit=200").json() if z["entity_type"] in ("Urlaubsanspruch je Jahr", "Startwert der Konten")]
    assert any(z.get("field_name") == "saldo_stunden" for z in admin) and any("4.5" in (z.get("details") or "") for z in admin)
    ba = [z for z in _als(w, "buero_auftrag", "bea").get("/api/audit-logs?limit=200").json()
          if z["entity_type"] in ("Urlaubsanspruch je Jahr", "Startwert der Konten")]
    assert ba, "Büro – Auftrag sieht, dass es Einträge gibt"
    assert not any(z.get("field_name") in ("saldo_stunden", "resturlaub_tage", "urlaubstage") for z in ba)
    assert not any(any(s in (z.get("details") or "") for s in ("4.5", "saldo_stunden", "urlaubstage")) for z in ba)


# --- Migration ------------------------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO time_tracking_settings (id, rounding_minutes, default_break_minutes, allow_manual_entries, allow_group_bookings, "
                       "require_order_item, require_activity, datev_target, updated_at) VALUES (1, 0, 0, true, true, false, false, 'lohn_gehalt', "
                       "'2026-11-01')"))
        c.execute(text("INSERT INTO employees (id, first_name, last_name, active, employee_group, weekly_hours, created_at, updated_at) VALUES (7, 'Ada', 'Test', "
                       "true, 'gewerblich', 40, '2026-11-01', '2026-11-01')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        tage, uebertrag, verfall = c.execute(text("SELECT urlaub_vorgabe_tage, urlaub_uebertrag, urlaub_verfall FROM time_tracking_settings")).one()
        assert (D(str(tage)), uebertrag, verfall) == (D("30"), "von_hand", None)  # der Bestand bekommt die Vorgaben
        assert c.execute(text("SELECT count(*) FROM urlaubsansprueche")).scalar() == 0
    with engine.begin() as c:
        c.execute(text("INSERT INTO lohn_startwerte (employee_id, stichtag, resturlaub_tage, updated_at) VALUES (7, '2026-12-31', 4.5, '2026-11-01')"))
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "Downgrade abgebrochen" in (nein.stdout + nein.stderr)
    with engine.connect() as c:
        assert c.execute(text("SELECT herkunft FROM lohn_startwerte")).scalar() == "steuerbuero"  # server_default
    with engine.begin() as c:
        c.execute(text("DELETE FROM lohn_startwerte"))
    _ok(_alembic(url, "downgrade", VORHER))
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'urlaub_startwerte.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_urlaubstart_{uuid.uuid4().hex[:8]}"
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


def test_modelle():
    assert {c.name for c in Urlaubsanspruch.__table__.columns} == {"id", "employee_id", "jahr", "urlaubstage", "uebertrag", "verfall_am", "notiz", "updated_at"}
    assert {c.name for c in LohnStartwert.__table__.columns} == {"id", "employee_id", "stichtag", "resturlaub_tage", "saldo_stunden", "herkunft",
                                                                 "herkunft_notiz", "geprueft_am", "geprueft_von", "updated_at"}


# --- Seite ----------------------------------------------------------------------------------------------------------------------------------

def test_seite_block_und_dialog():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "app/templates/settings.html").read_text(encoding="utf-8")
    assert '<div class="block" id="kontenBlock">' in text and '<dialog id="kontenDialog" class="modal">' in text
    assert text.index('id="payrollRollen"') < text.index('id="kontenBlock"')  # unter den Lohnstammdaten
    assert "ladeKonten().catch(" in text and "aktion('konten-oeffnen',el=>kontenOeffnen(Number(el.dataset.mitarbeiter)));" in text
    # „geprüft“ geht nur mit, wenn sich etwas tut (seit 1.9.312, test_v712) -- sonst entscheidet der Server (ein geänderter Wert verliert die Prüfung)
    assert "if(haken&&(!kdGeprueftVorher||geaendert))werte.geprueft=true;else if(!haken&&kdGeprueftVorher)werte.geprueft=false;" in text
    # ändern nur, wer darf; den Startwert nicht, wenn er für das Konto gesperrt ist
    assert "const darf=!!konten.darf_aendern,zu=!darf||konten.startwert_gesperrt;" in text
