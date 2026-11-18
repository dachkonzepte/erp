"""Version 1.9.367 (Urlaubsrunde, Punkt 3): der Hinweis an die Mitarbeiter auf ihren Resturlaub aus dem Vorjahr.

    Hinweis      ab dem 01.01. bis zum Verfall, solange vom Übertrag etwas übrig ist (uebertrag_noch, Übertrag zuerst): „Du hast noch 2,5 Tage Resturlaub aus
                 2026. Bitte bis 31.03.2027 nehmen – danach verfallen sie.“ -- in „Meine Zeiten“, bis „Gelesen“
    Gelesen      POST /api/field-view/urlaub-hinweis-gelesen: immer die eigene Person, jede Rolle; der Zeitpunkt (naives UTC, die Uhr der App) am Anspruch des
                 Jahrs; ein zweites „Gelesen“ behält den ersten; ohne Hinweis 409
    Büro         das Urlaubskonto zeigt, solange der Hinweis gilt, „Hinweis Resturlaub: nicht gelesen“ bzw. „… gelesen am TT.MM.JJJJ HH:MM“ (Berlin)
    Historie     „Hinweis Resturlaub gelesen am“, für Büro – Auftrag geschwärzt
    Migration    e7a3c9d2f518 auf einem Bestand (SQLite und PostgreSQL); downgrade() bricht ab, solange ein Zeitpunkt gespeichert ist
"""

import json
import os
import re
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text

from app.audit import FIELD_LABELS, KONTEN_FIELD_NAMES, reset_audit_context, set_audit_context
from app.meine_zeiten import meine_zeiten
from app.models import AuditLog, EmployeeAbsence, LohnStartwert, Urlaubsanspruch
from app.routers import audit as audit_router
from app.routers import field_view as field_view_router
from app.routers import zeiten as zeiten_router
from app.urlaubskonto import konten, resturlaub_text
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.uhr import uhr_festhalten

D = Decimal
MIGRATION, VORHER = "e7a3c9d2f518", "c5e2f8a1d047"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
FEB = date(2027, 2, 10)
G = "/api/field-view/urlaub-hinweis-gelesen"


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
        with uhr_festhalten(tag=FEB) as start:
            yield {"db": db, "mia": mia, "tom": tom, "client": router_test_client, "start": start}
    finally:
        reset_audit_context(token)


def _als(w, rolle, wer=None):
    w["db"].commit()
    return w["client"](w["db"], field_view_router.router, zeiten_router.router, audit_router.router, role=rolle,
                       employee_id=w[wer].id if wer else None, user_id=9)


def test_text():
    assert resturlaub_text(D("2.5"), 2026, date(2027, 3, 31)) == "Du hast noch 2,5 Tage Resturlaub aus 2026. Bitte bis 31.03.2027 nehmen – danach verfallen sie."
    assert resturlaub_text(D("1"), 2026, date(2027, 3, 31)) == "Du hast noch 1 Tag Resturlaub aus 2026. Bitte bis 31.03.2027 nehmen – danach verfällt er."
    assert resturlaub_text(D("0.5"), 2027, date(2028, 3, 31)).startswith("Du hast noch 0,5 Tage Resturlaub aus 2027.")


@pytest.mark.parametrize("heute, erwartet", [
    (date(2026, 12, 31), None),     # erst ab dem 01.01.
    (date(2027, 1, 1), True),
    (FEB, True),
    (date(2027, 3, 31), True),      # am Verfallstag noch
    (date(2027, 4, 1), None),       # danach nicht mehr (dann „nicht genommen“, Punkt 4)
])
def test_hinweis_ab_dem_01_01_bis_zum_verfall(w, heute, erwartet):
    k = konten(w["db"], 2027, [w["mia"].id], heute=heute)[0]
    text = "Du hast noch 2,5 Tage Resturlaub aus 2026. Bitte bis 31.03.2027 nehmen – danach verfallen sie."
    assert k.resturlaub_hinweis == (text if erwartet else None)


def test_nur_solange_vom_uebertrag_etwas_uebrig_ist(w):
    db = w["db"]
    assert konten(db, 2027, [w["tom"].id], heute=FEB)[0].resturlaub_hinweis is None  # Übertrag 0
    db.add(EmployeeAbsence(employee_id=w["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 3, 1), end_date=date(2027, 3, 3)))
    db.commit()
    assert konten(db, 2027, [w["mia"].id], heute=FEB)[0].resturlaub_hinweis is None  # genehmigt bis zum Verfall: alles verplant
    db.query(EmployeeAbsence).filter(EmployeeAbsence.start_date == date(2027, 3, 1)).delete()
    db.add(Urlaubsanspruch(employee_id=w["mia"].id, jahr=2027, verfall_am=date(2027, 6, 30)))
    db.commit()
    assert "Bitte bis 30.06.2027 nehmen" in konten(db, 2027, [w["mia"].id], heute=FEB)[0].resturlaub_hinweis  # der Verfall am Anspruch


def test_meine_zeiten_bis_gelesen(w):
    db, mia = w["db"], w["mia"]
    urlaub = meine_zeiten(db, mia.id, monat=date(2027, 2, 1), heute=FEB)["urlaub"]
    assert urlaub["resturlaub_hinweis"].startswith("Du hast noch 2,5 Tage Resturlaub aus 2026.") and urlaub["hinweis_gelesen_am"] is None
    c = _als(w, "field", "mia")
    r = c.post(G, json={"jahr": 2027})
    assert r.status_code == 200, r.text
    erst = datetime.fromisoformat(r.json()["hinweis_gelesen_am"])
    assert abs((erst - w["start"].replace(tzinfo=None)).total_seconds()) < 60  # die Uhr der App, naives UTC
    row = db.scalar(select(Urlaubsanspruch).where(Urlaubsanspruch.employee_id == mia.id))
    row.hinweis_gelesen_am = datetime(2027, 1, 5, 7, 0)  # ein früherer erster Klick, eindeutig
    db.commit()
    assert c.post(G, json={"jahr": 2027}).json()["hinweis_gelesen_am"] == "2027-01-05T07:00:00"  # der erste bleibt
    db.expire_all()
    assert meine_zeiten(db, mia.id, monat=date(2027, 2, 1), heute=FEB)["urlaub"]["hinweis_gelesen_am"] is not None
    assert db.scalar(select(Urlaubsanspruch.hinweis_gelesen_am).where(Urlaubsanspruch.employee_id == mia.id)) is not None


def test_gelesen_nur_fuer_sich_und_nur_mit_hinweis(w):
    assert _als(w, "field", "tom").post(G, json={"jahr": 2027}).status_code == 409  # kein Hinweis
    assert _als(w, "buero_finanzen").post(G, json={"jahr": 2027}).status_code == 422  # ohne Mitarbeiter
    assert _als(w, "field", "mia").post(G, json={"jahr": 2026}).status_code == 422
    assert _als(w, "buero_auftrag", "mia").post(G, json={"jahr": 2027, "employee_id": w["tom"].id}).status_code == 200  # immer die eigene Person
    w["db"].expire_all()
    assert w["db"].scalar(select(Urlaubsanspruch).where(Urlaubsanspruch.employee_id == w["tom"].id)) is None


def test_buero_sieht_wer_gelesen_hat(w):
    fin = _als(w, "buero_finanzen")
    k = next(x for x in fin.get("/api/zeiten/urlaubskonto?jahr=2027").json()["konten"] if x["employee_id"] == w["mia"].id)
    assert (k["resturlaub_hinweis"] is not None, k["hinweis_gelesen_am"]) == (True, None)
    _als(w, "field", "mia").post(G, json={"jahr": 2027})
    k = next(x for x in _als(w, "buero_finanzen").get("/api/zeiten/urlaubskonto?jahr=2027").json()["konten"] if x["employee_id"] == w["mia"].id)
    assert k["hinweis_gelesen_am"] is not None


def test_historie_und_geschwaerzt(w):
    db = w["db"]
    _als(w, "field", "mia").post(G, json={"jahr": 2027})
    db.commit()
    felder = {r.field_name for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Urlaubsanspruch je Jahr"))}
    schnappschuss = " ".join(r.details or "" for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Urlaubsanspruch je Jahr")))
    assert "hinweis_gelesen_am" in felder or "hinweis_gelesen_am" in schnappschuss
    ba = [z for z in _als(w, "buero_auftrag", "tom").get("/api/audit-logs?limit=200").json() if z["entity_type"] == "Urlaubsanspruch je Jahr"]
    assert ba and not any(z.get("field_name") == "hinweis_gelesen_am" or "hinweis_gelesen_am" in (z.get("details") or "") for z in ba)
    assert FIELD_LABELS["hinweis_gelesen_am"] == "Hinweis Resturlaub gelesen am" and "hinweis_gelesen_am" in KONTEN_FIELD_NAMES


def test_gelesen_unter_postgresql():
    from app.lohnkonten import hinweis_gelesen
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("resturlaub") as db, uhr_festhalten(tag=FEB):
        mia = make_employee(db, "M-1", "Mia", "Monteurin")
        db.add(LohnStartwert(employee_id=mia.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
        db.commit()
        assert hinweis_gelesen(db, mia.id, 2027)["hinweis_gelesen_am"] is not None


# --- Seiten ---------------------------------------------------------------------------------------------------------------------------------

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


DOM = ("var EL={};function feld(id){return EL[id]||(EL[id]={id:id,hidden:false,textContent:'',dataset:{}})}var el=feld;"
       "function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}")
TEXT = "Du hast noch 2,5 Tage Resturlaub aus 2026. Bitte bis 31.03.2027 nehmen – danach verfallen sie."


def test_meine_zeiten_zeigt_den_hinweis_bis_gelesen():
    text = vj.eigene_skripte("mobil_zeiten.html").text
    js = (DOM + "\n" + _funktion(text, "resturlaubZeichnen")
          + f"\nvar a=[];resturlaubZeichnen({json.dumps({'jahr': 2027, 'resturlaub_hinweis': TEXT, 'hinweis_gelesen_am': None})});"
          "a.push([EL.resturlaub.hidden,EL.resturlaubText.textContent,EL.resturlaubGelesen.dataset.jahr]);"
          f"resturlaubZeichnen({json.dumps({'jahr': 2027, 'resturlaub_hinweis': TEXT, 'hinweis_gelesen_am': '2027-02-10T09:00:00'})});"
          "a.push(EL.resturlaub.hidden);resturlaubZeichnen(null);a.push(EL.resturlaub.hidden);process.stdout.write(JSON.stringify(a));")
    assert node_ausfuehren(js) == [[False, TEXT, 2027], True, True]


def test_buero_sieht_gelesen_oder_nicht():
    text = vj.eigene_skripte("zeiten.html").text
    js = (_baustein("_berlin_date.html") + "\n" + DOM + "\n" + _funktion(text, "ukGelesen")
          + "\nprocess.stdout.write(JSON.stringify([ukGelesen({hinweis_gelesen_am:null}),ukGelesen({hinweis_gelesen_am:'2027-02-10T09:00:00'})]));")
    assert node_ausfuehren(js) == ['<span class="uk-hinweis">Hinweis Resturlaub: nicht gelesen</span>',
                                   '<span class="uk-gelesen">Hinweis Resturlaub gelesen am 10.02.2027 10:00</span>']


def test_seiten_aufbau():
    mobil = vj.seitentext("mobil_zeiten.html")[0]
    assert '<section class="zeiten-karte resturlaub" id="resturlaub" aria-label="Resturlaub" hidden>' in mobil
    assert "resturlaubZeichnen(d.urlaub);" in mobil and "el('resturlaubGelesen').addEventListener('click',resturlaubGelesen);" in mobil
    assert ("speichern('zeiten',()=>api('/api/field-view/urlaub-hinweis-gelesen',{method:'POST',headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({jahr:jahr})}),{neuLaden:laden})") in mobil
    zeiten = vj.seitentext("zeiten.html")[0]
    assert "(k.resturlaub_hinweis?ukGelesen(k):'')" in zeiten


# --- Migration ------------------------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (id, first_name, last_name, active, employee_group, weekly_hours, created_at, updated_at) VALUES (7, 'Ada', 'Test', "
                       "true, 'gewerblich', 40, '2026-11-01', '2026-11-01')"))
        c.execute(text("INSERT INTO urlaubsansprueche (employee_id, jahr, urlaubstage, updated_at) VALUES (7, 2027, 26, '2026-11-01')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        assert c.execute(text("SELECT hinweis_gelesen_am FROM urlaubsansprueche")).scalar() is None  # der Bestand bleibt leer
    with engine.begin() as c:
        c.execute(text("UPDATE urlaubsansprueche SET hinweis_gelesen_am = '2027-02-10 09:00:00'"))
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "Downgrade abgebrochen" in (nein.stdout + nein.stderr)
    with engine.begin() as c:
        c.execute(text("UPDATE urlaubsansprueche SET hinweis_gelesen_am = NULL"))
    _ok(_alembic(url, "downgrade", VORHER))
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'gelesen.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_gelesen_{uuid.uuid4().hex[:8]}"
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
