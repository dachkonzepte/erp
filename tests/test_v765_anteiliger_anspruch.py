"""Version 1.9.365 (Urlaubsrunde, Punkt 1): der anteilige Anspruch bei Eintritt oder Austritt im Jahr.

    Vorschlag   Jahresanspruch ÷ 12 × volle Beschäftigungsmonate (gezählt ab dem Eintrittstag, § 187 Abs. 2 / § 188 BGB), auf den nächsten halben Tag
                gerundet (die Mitte nach oben), mit der Rechnung „26 ÷ 12 × 5 = 10,8 → 11“ -- Zählen und Rundung stehen je an einer Stelle
                (app/urlaubskonto.py::volle_monate(), anteil_runden()); die Rundung bestätigt das Steuerbüro noch
    Hinweis     „Anspruch prüfen“, solange der Vorschlag vom Anspruch abweicht
    Übernehmen  nur per Klick (POST …/anteilig, Admin und Büro – Finanzen), nie von selbst; der Server rechnet neu, ein veralteter Vorschlag 409;
                gemerkt wird der Jahresanspruch (anteilig_aus), eine Änderung von Hand leert ihn
    Historie    „Anteilig aus Jahresanspruch“; für Büro – Auftrag geschwärzt
    Migration   a4d1e6c93b20 auf einem Bestand (SQLite und PostgreSQL); downgrade() bricht ab, solange ein Wert gesetzt ist
Stehende Uhr 10.11.2026 (fester_tag).
"""

import ast
import json
import os
import re
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text

from app.audit import FIELD_LABELS, KONTEN_FIELD_NAMES, reset_audit_context, set_audit_context
from app.models import AuditLog, EmployeePayrollSettings, Urlaubsanspruch
from app.routers import audit as audit_router
from app.routers import time_backoffice as backoffice_router
from app.routers import zeiten as zeiten_router
from app.urlaubskonto import ANSPRUCH_PRUEFEN, anteil_runden, konten, volle_monate, vorschlag_anteilig
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

D = Decimal
ROOT = Path(__file__).resolve().parent.parent
K = "/api/time-backoffice/konten"
MIGRATION, VORHER = "a4d1e6c93b20", "9e4b2c7d1a35"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


class _Konto:
    id = None
    role = "admin"
    display_name = "Anna Admin"
    username = "anna"


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    neu = make_employee(db, "M-1", "Nea", "Neu")          # Eintritt 01.08.2027, Helfer: 26 Tage
    weg = make_employee(db, "M-2", "Wim", "Weg")          # Austritt 31.05.2027, Vorgabe 30
    voll = make_employee(db, "M-3", "Vio", "Voll")        # Eintritt 01.01.2027: ganzes Jahr
    bea = make_employee(db, "B-1", "Bea", "Büro")
    db.add_all([EmployeePayrollSettings(employee_id=neu.id, eintritt=date(2027, 8, 1)),
                EmployeePayrollSettings(employee_id=weg.id, eintritt=date(2020, 4, 1), austritt=date(2027, 5, 31)),
                EmployeePayrollSettings(employee_id=voll.id, eintritt=date(2027, 1, 1)),
                Urlaubsanspruch(employee_id=neu.id, jahr=2027, urlaubstage=D("26"))])
    db.commit()
    token = set_audit_context(_Konto(), None)
    try:
        yield {"db": db, "neu": neu, "weg": weg, "voll": voll, "bea": bea, "client": router_test_client}
    finally:
        reset_audit_context(token)


def _als(w, rolle="buero_finanzen", wer=None):
    w["db"].commit()
    return w["client"](w["db"], backoffice_router.router, zeiten_router.router, audit_router.router, role=rolle,
                       employee_id=w[wer].id if wer else None, user_id=9, display_name={"buero_finanzen": "Fin Finanzen"}.get(rolle, rolle))


def _konto(w, emp, jahr=2027):
    return konten(w["db"], jahr, [emp.id])[0]


# --- Zählen und Runden ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("von, bis, monate", [
    (date(2027, 8, 1), date(2027, 12, 31), 5),    # Eintritt am Monatsersten
    (date(2027, 8, 15), date(2027, 12, 31), 4),   # 15.12.–14.01. ist kein voller Monat im Jahr
    (date(2027, 1, 1), date(2027, 5, 31), 5),     # Austritt am Monatsletzten
    (date(2027, 1, 1), date(2027, 5, 30), 4),
    (date(2027, 3, 15), date(2027, 9, 14), 6),    # ab Eintrittstag gezählt (Kalendermonate wären 5)
    (date(2027, 1, 31), date(2027, 12, 31), 11),  # 31.01.–28.02. (§ 188 Abs. 3), …, 31.11.→30.12.
    (date(2027, 1, 1), date(2027, 12, 31), 12),
    (date(2027, 3, 15), date(2027, 4, 13), 0),
    (date(2027, 6, 1), date(2027, 5, 31), 0),     # Austritt vor Eintritt
])
def test_volle_monate_ab_dem_eintrittstag(von, bis, monate):
    assert volle_monate(von, bis) == monate


@pytest.mark.parametrize("wert, gerundet", [
    (D(26) / 12 * 5, D("11")), (D(26) / 12 * 7, D("15")), (D("15.25"), D("15.5")), (D("17.5"), D("17.5")), (D("12.75"), D("13")),
    (D("12.74"), D("12.5")), (D("0"), D("0")),
])
def test_rundung_auf_den_naechsten_halben_tag(wert, gerundet):
    assert anteil_runden(wert) == gerundet


def test_rechnung_als_text():
    assert vorschlag_anteilig(D(26), date(2027, 8, 1), date(2027, 12, 31))["rechnung"] == "26 ÷ 12 × 5 = 10,8 → 11"
    assert vorschlag_anteilig(D(30), date(2027, 1, 1), date(2027, 6, 30))["rechnung"] == "30 ÷ 12 × 6 = 15 → 15"
    assert vorschlag_anteilig(D("26.5"), date(2027, 3, 15), date(2027, 9, 14))["rechnung"] == "26,5 ÷ 12 × 6 = 13,3 → 13,5"


def _aufrufe(baum, name):
    f = next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef) and n.name == name)
    return {(c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", "")) for c in ast.walk(f) if isinstance(c, ast.Call)}


def test_zaehlen_und_runden_je_an_einer_stelle():
    """Die Rundung bestätigt das Steuerbüro noch: sie steht nur in anteil_runden(), das Zählen nur in volle_monate(); der Vorschlag nimmt beide, das
    Übernehmen nimmt den Vorschlag des Kontos (keine eigene Rechnung)."""
    konto = ast.parse((ROOT / "app" / "urlaubskonto.py").read_text(encoding="utf-8"))
    assert {"anteil_runden", "volle_monate"} <= _aufrufe(konto, "vorschlag_anteilig")
    assert "vorschlag_anteilig" in _aufrufe(konto, "konten")
    pflege = ast.parse((ROOT / "app" / "lohnkonten.py").read_text(encoding="utf-8"))
    assert not {"anteil_runden", "volle_monate", "round_half_up", "vorschlag_anteilig"} & _aufrufe(pflege, "anteilig_uebernehmen")
    definiert = [p for p in (ROOT / "app").rglob("*.py") if re.search(r"^def (anteil_runden|volle_monate)\(", p.read_text(encoding="utf-8"), re.M)]
    assert [p.name for p in definiert] == ["urlaubskonto.py"]


# --- Vorschlag im Konto ---------------------------------------------------------------------------------------------------------------------

def test_vorschlag_bei_eintritt_und_austritt(w):
    neu = _konto(w, w["neu"])
    assert neu.anteilig["vorschlag"] == D("11") and neu.anteilig["monate"] == 5 and neu.anteilig["rechnung"] == "26 ÷ 12 × 5 = 10,8 → 11"
    assert (neu.anteilig["von"], neu.anteilig["bis"], neu.anteilig["uebernommen"]) == (date(2027, 8, 1), date(2027, 12, 31), False)
    assert ANSPRUCH_PRUEFEN in neu.hinweise and neu.anspruch == D("26")  # nichts übernommen
    weg = _konto(w, w["weg"])
    assert weg.anteilig["rechnung"] == "30 ÷ 12 × 5 = 12,5 → 12,5" and ANSPRUCH_PRUEFEN in weg.hinweise  # Vorgabe 30
    voll = _konto(w, w["voll"])
    assert voll.anteilig["vorschlag"] == voll.anspruch == D("30") and ANSPRUCH_PRUEFEN not in voll.hinweise  # ganzes Jahr: nichts zu prüfen
    assert _konto(w, w["bea"]).anteilig is None  # kein Eintritt, kein Austritt im Jahr
    d = neu.als_dict()["anteilig"]
    assert (d["basis"], d["roh"], d["vorschlag"]) == (D("26.0"), D("10.8"), D("11.0"))


def test_lesen_schreibt_nichts(w):
    """Nie von selbst: das Lesen des Kontos (mit offenen Vorschlägen) schreibt keine Anweisung und lässt nichts geändert in der Sitzung."""
    from sqlalchemy import event
    vorher = [(a.employee_id, a.jahr, a.urlaubstage, a.anteilig_aus) for a in w["db"].scalars(select(Urlaubsanspruch).order_by(Urlaubsanspruch.id))]
    c = _als(w)
    schreibend = []
    engine = w["db"].get_bind()

    def merken(conn, cursor, statement, *args):
        if statement.lstrip().split(" ", 1)[0].upper() in ("INSERT", "UPDATE", "DELETE"):
            schreibend.append(statement)
    event.listen(engine, "before_cursor_execute", merken)
    try:
        antwort = c.get("/api/zeiten/urlaubskonto?jahr=2027")
    finally:
        event.remove(engine, "before_cursor_execute", merken)
    assert antwort.status_code == 200 and antwort.json()["rechte"] == {"anspruch_setzen": True}
    assert any(k["anteilig"] and k["anteilig"]["vorschlag"] != k["anspruch"] for k in antwort.json()["konten"])  # es gibt offene Vorschläge
    assert schreibend == [] and not w["db"].dirty and not w["db"].new
    w["db"].expire_all()
    assert [(a.employee_id, a.jahr, a.urlaubstage, a.anteilig_aus) for a in w["db"].scalars(select(Urlaubsanspruch).order_by(Urlaubsanspruch.id))] == vorher


# --- Übernehmen -----------------------------------------------------------------------------------------------------------------------------

def test_vorschlag_uebernehmen_nur_per_klick(w):
    db, neu, weg = w["db"], w["neu"], w["weg"]
    c = _als(w)
    r = c.post(f"{K}/{neu.id}/anspruch/2027/anteilig", json={"vorschlag": 11})
    assert r.status_code == 200, r.text
    assert r.json()["anspruch"] == 11 and ANSPRUCH_PRUEFEN not in r.json()["hinweise"]
    assert "Anspruch anteilig: 26 ÷ 12 × 5 = 10,8 → 11" in r.json()["hinweise"]
    db.expire_all()
    row = db.scalar(select(Urlaubsanspruch).where(Urlaubsanspruch.employee_id == neu.id, Urlaubsanspruch.jahr == 2027))
    assert (row.urlaubstage, row.anteilig_aus) == (D("11"), D("26"))
    k = _konto(w, neu)
    assert k.anteilig["basis"] == D("26") and k.anteilig["uebernommen"]  # der nächste Vorschlag rechnet aus 26, nicht aus 11
    assert c.post(f"{K}/{neu.id}/anspruch/2027/anteilig", json={"vorschlag": 11}).status_code == 409  # schon übernommen
    # ein veralteter Wert: 409, nichts geändert (Wim hat noch keine Zeile)
    r = c.post(f"{K}/{weg.id}/anspruch/2027/anteilig", json={"vorschlag": 12})
    assert r.status_code == 409 and "12,5" in r.json()["detail"]
    assert db.scalar(select(Urlaubsanspruch).where(Urlaubsanspruch.employee_id == weg.id)) is None
    assert c.post(f"{K}/{weg.id}/anspruch/2027/anteilig", json={"vorschlag": "12.5"}).status_code == 200
    assert c.post(f"{K}/{w['bea'].id}/anspruch/2027/anteilig", json={"vorschlag": 30}).status_code == 409  # kein Vorschlag
    assert c.post(f"{K}/{neu.id}/anspruch/2026/anteilig", json={"vorschlag": 11}).status_code == 422  # vor dem Konto
    assert c.post(f"{K}/999999/anspruch/2027/anteilig", json={"vorschlag": 11}).status_code == 404


def test_rechte(w):
    neu = w["neu"]
    assert _als(w, "buero_auftrag", "bea").post(f"{K}/{neu.id}/anspruch/2027/anteilig", json={"vorschlag": 11}).status_code == 403
    assert _als(w, "field", "neu").post(f"{K}/{neu.id}/anspruch/2027/anteilig", json={"vorschlag": 11}).status_code == 403
    assert _als(w, "buero_auftrag", "bea").get("/api/zeiten/urlaubskonto?jahr=2027").json()["rechte"] == {"anspruch_setzen": False}
    assert _als(w, "admin").post(f"{K}/{neu.id}/anspruch/2027/anteilig", json={"vorschlag": 11}).status_code == 200


def test_von_hand_gilt_der_wert_von_hand(w):
    db, neu = w["db"], w["neu"]
    c = _als(w)
    assert c.post(f"{K}/{neu.id}/anspruch/2027/anteilig", json={"vorschlag": 11}).status_code == 200
    assert c.put(f"{K}/{neu.id}/anspruch/2027", json={"notiz": "geprüft"}).status_code == 200  # andere Felder lassen ihn stehen
    db.expire_all()
    assert db.scalar(select(Urlaubsanspruch.anteilig_aus).where(Urlaubsanspruch.employee_id == neu.id)) == D("26")
    assert c.put(f"{K}/{neu.id}/anspruch/2027", json={"urlaubstage": 12}).status_code == 200
    db.expire_all()
    assert db.scalar(select(Urlaubsanspruch.anteilig_aus).where(Urlaubsanspruch.employee_id == neu.id)) is None
    k = _konto(w, neu)
    assert k.anspruch == D("12") and k.anteilig["basis"] == D("12") and not k.anteilig["uebernommen"]


def test_historie_und_geschwaerzt(w):
    db, neu = w["db"], w["neu"]
    c = _als(w)
    assert c.post(f"{K}/{neu.id}/anspruch/2027/anteilig", json={"vorschlag": 11}).status_code == 200
    db.commit()
    felder = {r.field_name for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Urlaubsanspruch je Jahr"))}
    assert {"urlaubstage", "anteilig_aus"} <= felder
    ba = [z for z in _als(w, "buero_auftrag", "bea").get("/api/audit-logs?limit=200").json() if z["entity_type"] == "Urlaubsanspruch je Jahr"]
    assert ba and not any(z.get("field_name") in ("anteilig_aus", "urlaubstage") for z in ba)
    assert FIELD_LABELS["anteilig_aus"] == "Anteilig aus Jahresanspruch" and "anteilig_aus" in KONTEN_FIELD_NAMES


def test_uebernehmen_unter_postgresql():
    from app.lohnkonten import anteilig_uebernehmen
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("anteilig") as db:
        neu = make_employee(db, "M-1", "Nea", "Neu")
        db.add_all([EmployeePayrollSettings(employee_id=neu.id, eintritt=date(2027, 8, 1)),
                    Urlaubsanspruch(employee_id=neu.id, jahr=2027, urlaubstage=D("26"))])
        db.commit()
        assert anteilig_uebernehmen(db, neu.id, 2027, "11")["anspruch"] == D("11")
        assert db.scalar(select(Urlaubsanspruch.anteilig_aus).where(Urlaubsanspruch.employee_id == neu.id)) == D("26")


# --- Seite ----------------------------------------------------------------------------------------------------------------------------------

def _funktion(text: str, name: str) -> str:
    i = text.index("function " + name + "(")
    tiefe, j = 0, text.index("{", text.index(")", i))
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _baustein(name: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (vj.TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S))


DOM = "function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}"
KONTO = {"employee_id": 4, "name": "Nea Neu", "active": True, "jahr": 2027, "anspruch": 26.0, "anspruch_vorgabe": False, "uebertrag": 0.0,
         "genehmigt": 0.0, "vorbei": 0.0, "kuenftig": 0.0, "beantragt": 0.0, "rest": 26.0, "rest_nach_antraegen": 26.0, "hinweise": ["Anspruch prüfen"],
         "anteilig": {"basis": 26.0, "monate": 5, "von": "2027-08-01", "bis": "2027-12-31", "roh": 10.8, "vorschlag": 11.0,
                      "rechnung": "26 ÷ 12 × 5 = 10,8 → 11", "uebernommen": False}}


def _zeile(konto, rechte):
    text = vj.eigene_skripte("zeiten.html").text
    js = (_baustein("_zahl.html") + "\n" + DOM + f"\nvar UK={json.dumps({'rechte': rechte})};\n"
          + "\n".join(_funktion(text, f) for f in ("ukDatum", "ukAnteilig", "ukZeile"))
          + f"\nprocess.stdout.write(JSON.stringify(ukZeile({json.dumps(konto)})));")
    return node_ausfuehren(js)


def test_karte_zeigt_vorschlag_und_knopf():
    html = _zeile(KONTO, {"anspruch_setzen": True})
    assert ('<span class="uk-hinweis">Anspruch prüfen</span><span class="uk-vorschlag">Vorschlag 11 Tage: 26 ÷ 12 × 5 = 10,8 → 11 · 5 volle Monate '
            '(01.08.2027–31.12.2027)</span><button type="button" class="knopf knopf-neutral uk-knopf" data-aktion="uk-anteilig" data-id="4" '
            'data-jahr="2027" data-vorschlag="11">Vorschlag übernehmen</button></td>') in html
    assert "Vorschlag übernehmen" not in _zeile(KONTO, {"anspruch_setzen": False})  # Büro – Auftrag: der Vorschlag ohne Knopf
    assert "Vorschlag 11 Tage" in _zeile(KONTO, {"anspruch_setzen": False})
    gleich = dict(KONTO, anspruch=11.0, hinweise=["Anspruch anteilig: 26 ÷ 12 × 5 = 10,8 → 11"], anteilig=dict(KONTO["anteilig"], uebernommen=True))
    assert "uk-vorschlag" not in _zeile(gleich, {"anspruch_setzen": True})  # übernommen: nur der Hinweis


def test_seite_aufbau():
    zeiten = vj.seitentext("zeiten.html")[0]
    assert "else if(a==='uk-anteilig')ukAnteiligUebernehmen(b.dataset.id,b.dataset.jahr,b.dataset.vorschlag,b);" in zeiten
    assert ("speichern('urlaubskonto',()=>api('/api/time-backoffice/konten/'+id+'/anspruch/'+jahr+'/anteilig',{method:'POST',"
            "headers:{'Content-Type':'application/json'},body:JSON.stringify({vorschlag:vorschlag})}),{neuLaden:urlaubskontoLaden})") in zeiten


# --- Migration ------------------------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (id, first_name, last_name, active, employee_group, weekly_hours, created_at, updated_at) VALUES (7, 'Ada', 'Test', "
                       "true, 'gewerblich', 40, '2026-11-01', '2026-11-01')"))
        c.execute(text("INSERT INTO urlaubsansprueche (employee_id, jahr, urlaubstage, updated_at) VALUES (7, 2027, 26, '2026-11-01')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        tage, aus = c.execute(text("SELECT urlaubstage, anteilig_aus FROM urlaubsansprueche")).one()
        assert (D(str(tage)), aus) == (D("26"), None)  # der Bestand bleibt, nichts übernommen
    with engine.begin() as c:
        c.execute(text("UPDATE urlaubsansprueche SET urlaubstage = 11, anteilig_aus = 26"))
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "Downgrade abgebrochen" in (nein.stdout + nein.stderr)
    with engine.begin() as c:
        c.execute(text("UPDATE urlaubsansprueche SET anteilig_aus = NULL"))
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert D(str(c.execute(text("SELECT urlaubstage FROM urlaubsansprueche")).scalar())) == D("11")  # die Zeile bleibt
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'anteilig.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_anteilig_{uuid.uuid4().hex[:8]}"
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
