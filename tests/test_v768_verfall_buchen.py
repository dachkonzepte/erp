"""Version 1.9.368 (Urlaubsrunde, Punkt 4): Verfall buchen.

    nach dem Verfall  das Urlaubskonto nennt den nicht genommenen Übertrag (verfall_offen, Hinweis „Übertrag nicht genommen: …“) -- nichts verfällt von selbst
    buchen            POST …/anspruch/{Jahr}/verfall (Admin, Büro – Finanzen) mit dem angezeigten Wert; der Server rechnet neu (409 bei Abweichung, vor dem Verfall,
                      ohne Übertrag, schon gebucht), unter der Zeilensperre des Anspruchs; gemerkt Tage, Zeitpunkt (Uhr der App), wer
    danach            Rest = Anspruch + Übertrag − verfallen − genehmigt; Hinweis „Übertrag verfallen: …“; weicht der nicht genommene Übertrag später ab, „Verfall prüfen“
    zurücknehmen      DELETE (nur der Admin), danach wieder zu buchen
    Historie          jede Buchung und jedes Zurücknehmen; für Büro – Auftrag geschwärzt
    Migration         f8b4d0e3a629 auf einem Bestand (SQLite und PostgreSQL); downgrade() bricht ab, solange ein Verfall gebucht ist
"""

import json
import os
import re
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, select, text

from app.audit import FIELD_LABELS, KONTEN_FIELD_NAMES, reset_audit_context, set_audit_context
from app.models import AuditLog, EmployeeAbsence, LohnStartwert, TimeTrackingSettings, Urlaubsanspruch
from app.routers import audit as audit_router
from app.routers import time_backoffice as backoffice_router
from app.routers import zeiten as zeiten_router
from app.urlaubskonto import konten
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.uhr import uhr_festhalten

D = Decimal
MIGRATION, VORHER = "f8b4d0e3a629", "e7a3c9d2f518"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
APRIL = date(2027, 4, 6)
K = "/api/time-backoffice/konten"


class _Konto:
    id = None
    role = "admin"
    display_name = "Anna Admin"
    username = "anna"


@pytest.fixture
def w(threaded_db_session, router_test_client):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.add_all([LohnStartwert(employee_id=mia.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"),
                LohnStartwert(employee_id=tom.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("0"), saldo_stunden=D("0"), herkunft="steuerbuero"),
                EmployeeAbsence(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 2, 1), end_date=date(2027, 2, 2))])
    db.commit()
    token = set_audit_context(_Konto(), None)
    try:
        with uhr_festhalten(tag=APRIL) as start:
            yield {"db": db, "mia": mia, "tom": tom, "client": router_test_client, "start": start}
    finally:
        reset_audit_context(token)


def _als(w, rolle="buero_finanzen", wer=None):
    w["db"].commit()
    return w["client"](w["db"], backoffice_router.router, zeiten_router.router, audit_router.router, role=rolle,
                       employee_id=w[wer].id if wer else None, user_id=9, display_name={"buero_finanzen": "Fin Finanzen", "admin": "Anna Admin"}.get(rolle, rolle))


def _konto(w, heute=APRIL, wer="mia", jahr=2027):
    return konten(w["db"], jahr, [w[wer].id], heute=heute)[0]


def test_nach_dem_verfall_offen_nichts_von_selbst(w):
    assert _konto(w, heute=date(2027, 3, 31)).verfall_offen is None  # am Verfallstag noch nicht
    k = _konto(w)
    assert (k.verfall_offen, k.verfallen, k.rest) == (D("2.5"), D("0"), D("32.5"))
    assert k.hinweise == ["Übertrag nicht genommen: 2,5 Tage – Verfall am 31.03.2027, nichts verfällt von selbst"]
    assert _konto(w, wer="tom").verfall_offen is None  # ohne Übertrag nichts


def test_lesen_bucht_nichts(w):
    w["db"].add(Urlaubsanspruch(employee_id=w["mia"].id, jahr=2027, notiz="Zeile vorhanden"))  # mit Zeile: ein Lesen könnte dort buchen
    w["db"].commit()
    c = _als(w)
    schreibend, engine = [], w["db"].get_bind()

    def merken(conn, cursor, statement, *args):
        if statement.lstrip().split(" ", 1)[0].upper() in ("INSERT", "UPDATE", "DELETE"):
            schreibend.append(statement)
    event.listen(engine, "before_cursor_execute", merken)
    try:
        d = c.get("/api/zeiten/urlaubskonto?jahr=2027").json()
    finally:
        event.remove(engine, "before_cursor_execute", merken)
    mia = next(k for k in d["konten"] if k["employee_id"] == w["mia"].id)
    assert (D(str(mia["verfall_offen"])), D(str(mia["verfallen"]))) == (D("2.5"), D("0"))
    assert schreibend == [] and not w["db"].dirty and not w["db"].new
    assert d["rechte"] == {"anspruch_setzen": True, "verfall_buchen": True, "verfall_zuruecknehmen": False}


def test_buchen(w):
    db, mia = w["db"], w["mia"]
    r = _als(w).post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"})
    assert r.status_code == 200, r.text
    k = _konto(w)
    assert (k.verfallen, k.verfall_offen, k.uebertrag_noch, k.rest) == (D("2.5"), None, D("0"), D("30"))
    assert k.hinweise == ["Übertrag verfallen: 2,5 Tage am 31.03.2027"]
    assert k.verfall_gebucht_von == "Fin Finanzen"
    assert abs((k.verfall_gebucht_am - w["start"].replace(tzinfo=None)).total_seconds()) < 60  # die Uhr der App
    assert _als(w).post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 409  # schon gebucht


def test_nur_der_angezeigte_wert_und_nur_nach_dem_verfall(w):
    db, mia = w["db"], w["mia"]
    r = _als(w).post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2"})
    assert r.status_code == 409 and "2,5" in r.json()["detail"]
    assert _als(w).post(f"{K}/{w['tom'].id}/anspruch/2027/verfall", json={"tage": "0"}).status_code == 409  # ohne Übertrag
    with uhr_festhalten(tag=date(2027, 3, 31)):
        assert _als(w).post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 409  # vor dem Verfall
    db.expire_all()
    assert db.scalar(select(Urlaubsanspruch.verfall_tage).where(Urlaubsanspruch.employee_id == mia.id)) is None
    assert _als(w).post(f"{K}/{mia.id}/anspruch/2026/verfall", json={"tage": "2.5"}).status_code == 422
    assert _als(w).post(f"{K}/999999/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 404


def test_rechte_und_zuruecknehmen(w):
    mia = w["mia"]
    assert _als(w, "buero_auftrag", "tom").post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 403
    assert _als(w, "field", "mia").post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 403
    assert _als(w, "admin").post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 200
    assert _als(w).delete(f"{K}/{mia.id}/anspruch/2027/verfall").status_code == 403  # zurück nimmt nur der Admin
    r = _als(w, "admin").delete(f"{K}/{mia.id}/anspruch/2027/verfall")
    assert r.status_code == 200 and D(str(r.json()["verfall_offen"])) == D("2.5")  # wieder zu buchen
    assert _als(w, "admin").delete(f"{K}/{mia.id}/anspruch/2027/verfall").status_code == 409
    assert _als(w, "admin").get("/api/zeiten/urlaubskonto?jahr=2027").json()["rechte"]["verfall_zuruecknehmen"] is True


def test_verfall_pruefen_wenn_spaeter_abweichend(w):
    db, mia = w["db"], w["mia"]
    assert _als(w).post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 200
    db.add(EmployeeAbsence(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 3, 15), end_date=date(2027, 3, 15)))
    db.commit()  # ein Urlaub vor dem Verfall, erst danach eingetragen
    assert _konto(w).hinweise == ["Übertrag verfallen: 2,5 Tage am 31.03.2027", "Verfall prüfen: gebucht 2,5 Tage, nicht genommen jetzt 1,5 Tage"]


def test_automatischer_uebertrag_nach_dem_verfall(w):
    db, mia = w["db"], w["mia"]
    db.get(TimeTrackingSettings, 1).urlaub_uebertrag = "automatisch"
    db.commit()
    assert _als(w).post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"}).status_code == 200
    assert konten(db, 2028, [mia.id], heute=date(2028, 1, 10))[0].uebertrag == D("30")  # 30 + 4,5 − 2,5 − 2


def test_sperre_der_zeile_unter_postgresql():
    """Buchen nimmt den Anspruch unter FOR UPDATE -- zwei gleichzeitige Buchungen warten aufeinander, die zweite sieht die erste (409)."""
    from app.lohnkonten import VerfallNichtMoeglich, verfall_buchen
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("verfall") as db, uhr_festhalten(tag=APRIL):
        mia = make_employee(db, "M-1", "Mia", "Monteurin")
        db.add(LohnStartwert(employee_id=mia.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
        db.commit()
        anweisungen = []
        event.listen(db.get_bind(), "before_cursor_execute", lambda c, cur, s, *a: anweisungen.append(s))
        assert verfall_buchen(db, mia.id, 2027, "4.5", von="Fin")["verfallen"] == D("4.5")
        assert any("FROM urlaubsansprueche" in s and "FOR UPDATE" in s for s in anweisungen)
        with pytest.raises(VerfallNichtMoeglich):
            verfall_buchen(db, mia.id, 2027, "4.5", von="Fin")


def test_historie_und_geschwaerzt(w):
    db, mia = w["db"], w["mia"]
    _als(w).post(f"{K}/{mia.id}/anspruch/2027/verfall", json={"tage": "2.5"})
    _als(w, "admin").delete(f"{K}/{mia.id}/anspruch/2027/verfall")
    db.commit()
    zeilen = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "Urlaubsanspruch je Jahr").order_by(AuditLog.id)))
    werte = [(r.field_name, r.new_value) for r in zeilen if r.field_name == "verfall_tage"]
    assert [w_[1] not in (None, "", "None") for w_ in werte] == [True, False]  # gebucht, zurückgenommen
    ba = [z for z in _als(w, "buero_auftrag", "tom").get("/api/audit-logs?limit=200").json() if z["entity_type"] == "Urlaubsanspruch je Jahr"]
    assert ba and not any(z.get("field_name") in ("verfall_tage", "verfall_gebucht_am", "verfall_gebucht_von") for z in ba)
    assert FIELD_LABELS["verfall_tage"] == "Verfall gebucht (Tage)" and {"verfall_tage", "verfall_gebucht_am", "verfall_gebucht_von"} <= KONTEN_FIELD_NAMES


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
OFFEN = {"employee_id": 4, "jahr": 2027, "verfall_offen": 2.5, "verfallen": 0, "hinweis_gelesen_am": None}
GEBUCHT = {"employee_id": 4, "jahr": 2027, "verfall_offen": None, "verfallen": 2.5, "verfall_gebucht_am": "2027-04-06T08:00:00",
           "verfall_gebucht_von": "Fin Finanzen", "hinweis_gelesen_am": "2027-02-10T09:00:00"}


def _verfall(konto, rechte, zurueck=None):
    text = vj.eigene_skripte("zeiten.html").text
    js = (_baustein("_berlin_date.html") + "\n" + DOM + f"\nvar UK={json.dumps({'rechte': rechte})};var UK_ZURUECK={json.dumps(zurueck)};\n"
          + "\n".join(_funktion(text, f) for f in ("ukGelesen", "ukVerfall"))
          + f"\nprocess.stdout.write(JSON.stringify(ukVerfall({json.dumps(konto)})));")
    return node_ausfuehren(js)


def test_karte_verfall_buchen_und_gebucht():
    fin = {"verfall_buchen": True, "verfall_zuruecknehmen": False}
    assert _verfall(OFFEN, fin) == ('<span class="uk-hinweis">Hinweis Resturlaub: nicht gelesen</span><button type="button" class="knopf knopf-neutral uk-knopf" '
                                     'data-aktion="uk-verfall" data-id="4" data-jahr="2027" data-tage="2.5">Verfall buchen</button>')
    assert "Verfall buchen" not in _verfall(OFFEN, {"verfall_buchen": False})
    assert _verfall(GEBUCHT, fin) == '<span class="uk-gelesen">Verfall gebucht am 06.04.2027 10:00 von Fin Finanzen</span>'
    admin = {"verfall_buchen": True, "verfall_zuruecknehmen": True}
    assert 'data-aktion="uk-verfall-fragen" data-id="4">Verfall zurücknehmen</button>' in _verfall(GEBUCHT, admin)
    assert ('<span class="rueckfrage">Verfall zurücknehmen?</span>' in _verfall(GEBUCHT, admin, "4")
            and 'data-aktion="uk-verfall-zurueck" data-id="4" data-jahr="2027">Zurücknehmen</button>' in _verfall(GEBUCHT, admin, "4"))
    gelesen = dict(OFFEN, hinweis_gelesen_am="2027-02-10T09:00:00")
    assert _verfall(gelesen, fin).startswith('<span class="uk-gelesen">Hinweis Resturlaub gelesen am 10.02.2027 10:00</span>')


def test_seite_aufbau():
    zeiten = vj.seitentext("zeiten.html")[0]
    assert "else if(a==='uk-verfall')ukVerfallBuchen(b.dataset.id,b.dataset.jahr,b.dataset.tage,b);" in zeiten
    assert ("abschliessen('urlaubskonto',()=>api('/api/time-backoffice/konten/'+id+'/anspruch/'+jahr+'/verfall',{method:'POST',"
            "headers:{'Content-Type':'application/json'},body:JSON.stringify({tage:tage})}),{neuLaden:urlaubskontoLaden})") in zeiten
    assert "speichern('urlaubskonto',()=>api('/api/time-backoffice/konten/'+id+'/anspruch/'+jahr+'/verfall',{method:'DELETE'}),{neuLaden:urlaubskontoLaden})" in zeiten


# --- Migration ------------------------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (id, first_name, last_name, active, employee_group, weekly_hours, created_at, updated_at) VALUES (7, 'Ada', 'Test', "
                       "true, 'gewerblich', 40, '2026-11-01', '2026-11-01')"))
        c.execute(text("INSERT INTO urlaubsansprueche (employee_id, jahr, urlaubstage, updated_at) VALUES (7, 2027, 26, '2026-11-01')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        assert c.execute(text("SELECT verfall_tage, verfall_gebucht_am, verfall_gebucht_von FROM urlaubsansprueche")).one() == (None, None, None)
    with engine.begin() as c:
        c.execute(text("UPDATE urlaubsansprueche SET verfall_tage = 2.5, verfall_gebucht_am = '2027-04-06 08:00:00', verfall_gebucht_von = 'Fin'"))
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "Downgrade abgebrochen" in (nein.stdout + nein.stderr)
    with engine.begin() as c:
        c.execute(text("UPDATE urlaubsansprueche SET verfall_tage = NULL, verfall_gebucht_am = NULL, verfall_gebucht_von = NULL"))
    _ok(_alembic(url, "downgrade", VORHER))
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'verfall_buchen.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_verfallb_{uuid.uuid4().hex[:8]}"
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
