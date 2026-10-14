"""Version 1.8.103 -- Vorweg der Vorgabe vom 14.10.2026 (Korrekturen zu den Festlegungen 1.8.98–1.8.100).

    98-11  "Alle vertrauten Geräte abmelden" beendet auch alle anderen Sitzungen; Rolle und Rechte werden bei jeder Anfrage frisch
           gelesen (Angriffstest: Rolle herabsetzen, die nächste Anfrage der laufenden Sitzung hat die neuen Rechte); ein Administrator
           beendet alle Sitzungen eines Benutzers (POST /api/users/{id}/end-sessions).
    98-12  Feierabend in /mobil beendet die Sitzung auf dem Server wie Abmelden.
    99-6   Eine vom Server abgelehnte abschließende Aktion sperrt keine weitere -- der Test steht seit 1.8.99 in
           tests/test_v399_abschliessen.py (test_a_final_action_refused_by_the_server_does_not_block_another), die Gegenprobe ist in
           1.8.103 gelaufen (docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.103").
    99-10  Änderungen am Vertragsentwurf unter derselben Sperre wie das Festschreiben (app/contract_templates.py::
           update_contract_draft()), Gleichzeitigkeit gegen PostgreSQL.
    Ablauf Läuft die Sitzung beim Speichern ab, meldet der Bereich "Anmeldung abgelaufen", die Eingaben bleiben stehen; nach dem
           Anmelden in einem neuen Tab lässt sich erneut speichern (app/anmeldeschranke.py, app/templates/_speichern.html; Klicktest
           scripts/klicktest_anmeldung_abgelaufen.py).

Alle Sitzungstests über die echte Anmeldeschranke (tests/anmeldung.py, Welt aus tests/test_v402_sitzungen.py)."""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app import sitzungen
from app.anmeldeschranke import ABGELAUFEN_KOPF, ANMELDUNG_ABGELAUFEN
from app.auth import COOKIE_NAME
from app.database import Base
from app.models import UserSession
from app.permissions import require_min_role
from app.routers import account as account_router
from app.routers import auth as auth_router
from app.routers import field_view as field_view_router
from app.routers import users as users_router
from tests.anmeldung import app_mit_schranke, neue_datenbank
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v398_speichern_baustein import _ablauf
from tests.test_v402_sitzungen import PASSWORT, Welt, _status, _wert

nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht gefunden")

_probe = APIRouter()


@_probe.get("/api/probe")
def _api_probe():
    return {"ok": True}


@_probe.get("/api/finanzen-probe")
def _finanzen_lesen(_user=Depends(require_min_role("buero_finanzen"))):
    return {"ok": True}


@_probe.post("/api/finanzen-probe")
def _finanzen_schreiben(_user=Depends(require_min_role("buero_finanzen"))):
    return {"ok": True}


class WeltMitMobil(Welt):
    def __init__(self, make_session):
        super().__init__(make_session)
        self.app = app_mit_schranke(make_session, auth_router.router, account_router.router, users_router.router,
                                    field_view_router.router, _probe)


@pytest.fixture
def welt():
    engine, make_session = neue_datenbank()
    yield WeltMitMobil(make_session)
    engine.dispose()


def _daten(name: str, rolle: str, **mehr) -> dict:
    return {"username": name, "display_name": name, "employee_id": None, "role": rolle, "active": True, "new_password": None,
            **mehr}


# ---------------------------------------------------------------------------
# 98-11: Rolle je Anfrage frisch gelesen (Angriffstest)
# ---------------------------------------------------------------------------

def test_rolle_herabgesetzt_die_naechste_anfrage_hat_die_neuen_rechte(welt):
    """Angriffstest: Bea (Büro Finanzen) hält eine laufende Sitzung; ein Administrator setzt sie auf Monteur herab -- schon die nächste
    Anfrage derselben Sitzung (kein neues Anmelden, kein neuer Cookie-Wert) wird nach der neuen Rolle entschieden, lesend wie
    schreibend. Die Sitzung selbst bleibt (Festlegung 1.8.98: eine Rollenänderung beendet keine Sitzung)."""
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea", "buero_finanzen")
    geraet = welt.angemeldet("bea")
    wert = _wert(geraet)
    assert geraet.get("/api/finanzen-probe").status_code == 200
    assert geraet.post("/api/finanzen-probe").status_code == 200

    assert welt.als(anna).put(f"/api/users/{bea.id}", json=_daten("bea", "field")).status_code == 200
    assert _wert(geraet) == wert
    assert geraet.get("/api/finanzen-probe").status_code == 403
    assert geraet.post("/api/finanzen-probe").status_code == 403
    assert geraet.get("/api/probe").status_code == 200  # weiter angemeldet, nur mit weniger Rechten
    assert welt.sitzungen_von(bea) == 1

    # und wieder herauf: ebenso ab der nächsten Anfrage
    assert welt.als(anna).put(f"/api/users/{bea.id}", json=_daten("bea", "buero_finanzen")).status_code == 200
    assert geraet.post("/api/finanzen-probe").status_code == 200


def test_admin_herabgesetzt_verliert_die_benutzerverwaltung_sofort(welt):
    """Derselbe Angriffstest an einem echten Admin-Endpunkt: Berta (Admin, zweiter Faktor bestätigt) liest die Benutzerliste; Anna
    setzt sie auf Büro Finanzen herab -- Bertas nächste Anfrage bekommt 403, auch das Anlegen eines Benutzers."""
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    berta = welt.benutzer("berta", "admin", zweiter_faktor=True)
    geraet = welt.als(berta)
    assert geraet.get("/api/users").status_code == 200
    assert welt.als(anna).put(f"/api/users/{berta.id}", json=_daten("berta", "buero_finanzen")).status_code == 200
    assert geraet.get("/api/users").status_code == 403
    neu = {"username": "eve", "password": PASSWORT, "display_name": "Eve", "role": "admin", "active": True}
    assert geraet.post("/api/users", json=neu).status_code == 403
    assert geraet.post(f"/api/users/{anna.id}/end-sessions").status_code == 403


# ---------------------------------------------------------------------------
# 98-11: "Alle vertrauten Geräte abmelden" und Administrator beendet Sitzungen
# ---------------------------------------------------------------------------

def test_alle_vertrauten_geraete_abmelden_beendet_die_anderen_sitzungen(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    hier, dort, drittes = welt.als(anna), welt.als(anna), welt.als(anna)
    wert_dort, wert_drittes = _wert(dort), _wert(drittes)
    bea_wert = _wert(welt.angemeldet("bea"))

    antwort = hier.post("/api/account/trusted-devices/revoke-all")
    assert (antwort.status_code, antwort.json()["sitzungen_beendet"]) == (200, 2)
    # Angriffstest: die beiden anderen Werte (wie von jemandem, der sie mitgelesen hat) gelten nicht mehr
    assert _status(welt, wert_dort) == 401
    assert _status(welt, wert_drittes) == 401
    assert hier.get("/api/users").status_code == 200  # dieses Gerät bleibt angemeldet, zweiter Faktor bestätigt
    assert welt.sitzungen_von(anna) == 1
    assert _status(welt, bea_wert) == 200  # andere Benutzer unberührt
    assert welt.sitzungen_von(bea) == 1


def test_administrator_beendet_alle_sitzungen_eines_benutzers(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    a, b = welt.angemeldet("bea"), welt.angemeldet("bea")
    wert_a, wert_b = _wert(a), _wert(b)
    admin = welt.als(anna)

    liste = {u["username"]: u["active_sessions"] for u in admin.get("/api/users").json()}
    assert liste == {"anna": 1, "bea": 2}
    antwort = admin.post(f"/api/users/{bea.id}/end-sessions")
    assert (antwort.status_code, antwort.json()["sitzungen_beendet"]) == (200, 2)
    assert _status(welt, wert_a) == 401
    assert _status(welt, wert_b) == 401
    assert welt.sitzungen_von(bea) == 0
    assert admin.get("/api/users").status_code == 200  # der Administrator bleibt angemeldet
    assert {u["username"]: u["active_sessions"] for u in admin.get("/api/users").json()}["bea"] == 0
    assert _status(welt, _wert(welt.angemeldet("bea"))) == 200  # neu anmelden geht


def test_administrator_beendet_seine_eigenen_dieses_geraet_bleibt(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    hier, dort = welt.als(anna), welt.als(anna)
    wert_hier, wert_dort = _wert(hier), _wert(dort)
    antwort = hier.post(f"/api/users/{anna.id}/end-sessions")
    assert (antwort.status_code, antwort.json()["sitzungen_beendet"]) == (200, 2)
    assert _status(welt, wert_dort) == 401
    assert _status(welt, wert_hier) == 401  # auch der alte Wert dieses Geräts -- es hat einen neuen
    assert _wert(hier) != wert_hier
    assert hier.get("/api/users").status_code == 200  # neue Sitzung, zweiter Faktor bleibt bestätigt


@pytest.mark.parametrize("rolle", ["buero_finanzen", "buero_auftrag", "field"])
def test_sitzungen_beenden_nur_als_administrator(welt, rolle):
    welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    welt.benutzer("eva", rolle)
    bea_wert = _wert(welt.angemeldet("bea"))
    assert welt.angemeldet("eva").post(f"/api/users/{bea.id}/end-sessions").status_code == 403
    assert _status(welt, bea_wert) == 200


def test_sitzungen_beenden_unbekannter_benutzer_404(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    assert welt.als(anna).post("/api/users/9999/end-sessions").status_code == 404


# ---------------------------------------------------------------------------
# 98-12: Feierabend in /mobil beendet die Sitzung auf dem Server
# ---------------------------------------------------------------------------

def test_feierabend_beendet_die_sitzung_auf_dem_server(welt, monkeypatch):
    mia = welt.benutzer("mia", "field")
    geraet, anderes = welt.angemeldet("mia"), welt.angemeldet("mia")
    wert, wert_anderes = _wert(geraet), _wert(anderes)
    feierabend = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=20)
    monkeypatch.setattr(field_view_router, "_now", lambda: feierabend)

    antwort = geraet.get("/api/field-view/today")
    assert (antwort.status_code, antwort.json()["detail"]) == (401, "Feierabend -- bitte erneut anmelden.")
    # Seit 1.8.106 (Korrektur 103-3): der GET meldet nur, /mobil beendet die Sitzung per POST (tests/test_v411_vorweg.py)
    assert geraet.post("/api/field-view/feierabend").status_code == 200
    # Angriffstest: der Wert des Tablets von außen -- die Sitzung ist auf dem Server beendet, nicht nur das Cookie gelöscht
    assert _status(welt, wert) == 401
    assert _status(welt, wert_anderes) == 200  # wie Abmelden: nur diese Sitzung
    assert welt.sitzungen_von(mia) == 1


def test_vor_dem_feierabend_bleibt_die_sitzung(welt, monkeypatch):
    welt.benutzer("mia", "field")
    geraet = welt.angemeldet("mia")
    mittag = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=12)
    monkeypatch.setattr(field_view_router, "_now", lambda: mittag)
    assert geraet.get("/api/field-view/today").status_code != 401
    assert _status(welt, _wert(geraet)) == 200


# ---------------------------------------------------------------------------
# Anmeldung abgelaufen beim Speichern
# ---------------------------------------------------------------------------

def test_abgelaufene_sitzung_antwortet_mit_anmeldung_abgelaufen(welt):
    welt.benutzer("bea")
    geraet = welt.angemeldet("bea")
    with welt.make_session() as db:
        for s in db.query(UserSession).all():
            s.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    antwort = geraet.post("/api/finanzen-probe")
    assert antwort.status_code == 401
    assert antwort.headers.get(ABGELAUFEN_KOPF) == "abgelaufen"
    assert antwort.json() == {"detail": ANMELDUNG_ABGELAUFEN, "anmeldung_abgelaufen": True}
    assert ANMELDUNG_ABGELAUFEN.startswith("Anmeldung abgelaufen")


@pytest.mark.parametrize("art", ["abgemeldet", "beendet"])
def test_beendete_sitzung_ebenso(welt, art):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    geraet = welt.angemeldet("bea")
    wert = _wert(geraet)
    if art == "abgemeldet":
        welt.client(wert).post("/api/auth/logout")  # in einem anderen Tab abgemeldet; dieser Tab hat den Wert noch
    else:
        welt.als(anna).post(f"/api/users/{bea.id}/end-sessions")
    antwort = welt.client(wert).put(f"/api/users/{bea.id}", json=_daten("bea", "admin"))
    assert (antwort.status_code, antwort.headers.get(ABGELAUFEN_KOPF)) == (401, "abgelaufen")


def test_ohne_cookie_kein_abgelaufen(welt):
    welt.benutzer("bea")
    antwort = welt.client().post("/api/finanzen-probe")
    assert antwort.status_code == 401
    assert ABGELAUFEN_KOPF not in antwort.headers
    assert antwort.json() == {"detail": "Bitte zuerst als ERP-Benutzer anmelden."}


def test_seiten_leiten_weiter_auf_die_anmeldung(welt):
    """Eine Seite (kein Speichern) mit abgelaufenem Wert führt wie bisher auf die Anmeldung."""
    welt.benutzer("bea")
    geraet = welt.angemeldet("bea")
    wert = _wert(geraet)
    geraet.post("/api/auth/logout")
    antwort = welt.client(wert).get("/irgendeine-seite", follow_redirects=False)
    assert antwort.status_code in (302, 404)
    assert ABGELAUFEN_KOPF not in antwort.headers


# --- im Baustein ----------------------------------------------------------------------------------------------------------------

_DOKUMENT = """
const _dkEl={};
globalThis.document={body:{prepend(e){_dkEl[e.id]=e;log.push('hinweis da')},appendChild(e){_dkEl[e.id]=e}},
  getElementById:id=>_dkEl[id]||null,
  createElement:()=>({style:{},setAttribute(){},append(){},remove(){delete _dkEl[this.id];log.push('hinweis weg')}})};
"""
_ABGELAUFEN = ("new Response(JSON.stringify({detail:'Anmeldung abgelaufen – x'}),"
               "{status:401,headers:{'X-DK-Anmeldung':'abgelaufen'}})")


@nur_mit_node
def test_baustein_zeigt_den_hinweis_und_nimmt_ihn_nach_gelungenem_speichern_weg():
    """Speichern mit api(), das bei einem Fehler wirft (wie fast jede Seite): Hinweis oben, der Fehler kommt beim Aufrufer an (der
    Bereich meldet ihn, die Seite bleibt); eine abschließende Aktion geht danach nicht hinaus (gescheitertes Speichern, Regel 29);
    nach dem Anmelden in einem neuen Tab gelingt dasselbe Speichern, der Hinweis ist weg, und die abschließende Aktion geht."""
    log = _ablauf("""
        const api=n=>fetch(n).then(async r=>{if(!r.ok)throw new Error((await r.json()).detail);return r.json()});
        const s1=speichern('kunde',()=>api('S1')).catch(e=>log.push('fehler am bereich: '+e.message)); await ruhe();
        await antworte('S1',""" + _ABGELAUFEN + """); await s1;
        log.push('abschliessen: '+await abschliessen('versand',anfrage('V1')).then(()=>'gesendet',e=>e.dkBaustein));
        const s2=speichern('kunde',()=>api('S2')); await ruhe();
        await antworte('S2',new Response('{"ok":true}',{status:200})); await s2;
        const a=abschliessen('versand',anfrage('V2')); await ruhe(); await antworte('V2'); await a;
    """, vorspann=_DOKUMENT)
    assert log == ["gesendet S1", "hinweis da", "fehler am bereich: Anmeldung abgelaufen – x", "abschliessen: abschluss",
                   "gesendet S2", "hinweis weg", "gesendet V2"]


@nur_mit_node
def test_baustein_ohne_api_bekommt_die_antwort_zurueck():
    """Speichern mit fetch() direkt: der Aufrufer bekommt die Antwort (401), der Hinweis steht; ein anderer Fehlerstatus (403) zeigt
    keinen Hinweis."""
    log = _ablauf("""
        const s1=speichern('a',()=>fetch('S1')); await ruhe(); await antworte('S1',""" + _ABGELAUFEN + """);
        log.push('status '+(await s1).status);
        const s2=speichern('b',()=>fetch('S2')); await ruhe(); await antworte('S2',new Response('{}',{status:403}));
        log.push('status '+(await s2).status);
    """, vorspann=_DOKUMENT)
    assert log == ["gesendet S1", "hinweis da", "status 401", "gesendet S2", "status 403"]


@nur_mit_node
def test_401_ohne_kopfzeile_zeigt_keinen_hinweis():
    log = _ablauf("""
        const s=speichern('a',()=>fetch('S1')); await ruhe(); await antworte('S1',new Response('{}',{status:401})); await s;
    """, vorspann=_DOKUMENT)
    assert log == ["gesendet S1"]


# ---------------------------------------------------------------------------
# 99-10: Vertragsentwurf unter der Sperre des Festschreibens (PostgreSQL)
# ---------------------------------------------------------------------------

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture
def pg_vertrag(monkeypatch):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from app.grunddaten import anlegen
    from app.projects import load_quote
    from tests.test_v321_email_dispatch import FakeSMTP
    from tests.test_v325_contract_basis import make_quote
    from tests.test_v335_vertragsvorlagen import beauftragen, save

    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    schema = f"pgtest_vertrag_{uuid.uuid4().hex[:8]}"
    verwaltung = create_engine(PG_TEST_DATABASE_URL)
    with verwaltung.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=6,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            save(setup, reviewed=True)
            quote = make_quote(setup, number="0001", is_consumer=True)
            quote.status = "versendet"
            setup.commit()
            order_id = beauftragen(setup, load_quote(setup, quote.id)).id
        finally:
            setup.close()
        yield Session, order_id
    finally:
        close_all_sessions()
        engine.dispose()
        with verwaltung.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        verwaltung.dispose()


def _gleichzeitig(Session, erste, zweite):
    from tests.test_v375_rechnungen_sperren import _run
    return _run(Session, erste, zweite)


def test_pg_entwurf_aendern_waehrend_des_festschreibens_wartet_und_wird_abgelehnt(pg_vertrag):
    """Das Festschreiben hält die Zeilensperre des Vertrags; eine gleichzeitige Änderung am Entwurf (geladen mit dem alten Stand
    "entwurf", wie der Router) wartet und wird danach abgelehnt -- bis 1.8.102 ging der Text nach der Fassung in den Vertrag."""
    from app.contract_templates import get_order_contract, update_contract_draft
    from app.contract_versions import freeze_contract
    from app.orders import load_order

    Session, order_id = pg_vertrag

    def festschreiben(s):
        return freeze_contract(s, load_order(s, order_id), attachment="aktuell").version_no

    def aendern(s):
        vertrag = get_order_contract(s, order_id)
        assert vertrag.status == "entwurf"  # alter Stand, die Fassung ist noch nicht committet
        update_contract_draft(s, vertrag, {"special_terms": "Nachträglich hineingeschrieben"})
        return "geändert"

    erste, zweite = _gleichzeitig(Session, festschreiben, aendern)
    assert erste == 1
    assert isinstance(zweite, ValueError) and "Nur ein Vertragsentwurf" in str(zweite)
    s = Session()
    try:
        vertrag = get_order_contract(s, order_id)
        assert (vertrag.status, vertrag.special_terms) == ("festgeschrieben", None)
        assert "Nachträglich" not in vertrag.versions[0].frozen_content
    finally:
        s.close()


def test_pg_entwurf_aendern_vor_dem_festschreiben_steht_in_der_fassung(pg_vertrag):
    """Gegenstück: hält die Änderung die Sperre zuerst, wartet das Festschreiben und schreibt ihren Text in die Fassung."""
    from app.contract_templates import get_order_contract, update_contract_draft
    from app.contract_versions import freeze_contract
    from app.orders import load_order

    Session, order_id = pg_vertrag

    def aendern(s):
        update_contract_draft(s, get_order_contract(s, order_id), {"special_terms": "Vorher eingetragen"})
        return "geändert"

    def festschreiben(s):
        return freeze_contract(s, load_order(s, order_id), attachment="aktuell").version_no

    erste, zweite = _gleichzeitig(Session, aendern, festschreiben)
    assert (erste, zweite) == ("geändert", 1)
    s = Session()
    try:
        assert "Vorher eingetragen" in get_order_contract(s, order_id).versions[0].frozen_content
    finally:
        s.close()
