"""Version 1.8.98 -- Sitzungen auf dem Server (Vorgabe vom 14.10.2026, Punkt 2).

Bis 1.8.97 war das Anmelde-Cookie zustandslos (Benutzer-ID, Ablauf, HMAC): Abmelden löschte nur das Cookie im Browser, der alte Wert
bekam bis zum Ablauf (12 h) weiter 200, und weder ein neues Passwort noch ein Deaktivieren beendete eine Sitzung (Nebenbefund 3 aus
1.8.97). Der bestätigte zweite Faktor stand in einem eigenen, an den Benutzer gebundenen Cookie -- es ließ sich in eine neue Anmeldung
mitnehmen.

Jetzt app/sitzungen.py (Tabelle user_sessions): Abmelden beendet die Sitzung, Passwort- und 2FA-Änderung sowie das Deaktivieren beenden
alle Sitzungen des Benutzers, der zweite Faktor gilt je Sitzung. Alle Tests über die echte Anmeldeschranke (tests/anmeldung.py), die
Angriffstests mit dem Cookie-Wert von vorher, wie ihn jemand hätte, der ihn mitgelesen hat. Die wichtigsten Fälle zusätzlich gegen
PostgreSQL (Wegwerf-Schema, Regel 27)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime, timedelta

import pyotp
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from app import sitzungen, two_factor
from app.auth import COOKIE_NAME, OTP_COOKIE_NAME, hash_password, secret_key
from app.database import Base
from app.models import AppUser, UserSession
from app.routers import account as account_router
from app.routers import auth as auth_router
from app.routers import users as users_router
from tests.anmeldung import app_mit_schranke, browser_client, neue_datenbank

PASSWORT = "RichtigesPasswort123"
NEU = "NeuesPasswort456"

_probe = APIRouter()


@_probe.get("/api/probe")
def _api_probe():
    return {"ok": True}


@_probe.get("/seite")
def _seiten_probe():
    return {"ok": True}


ROUTER = (auth_router.router, account_router.router, users_router.router, _probe)


class Welt:
    """Eine Datenbank mit der echten Anmeldeschranke; je client() ein eigenes Gerät (eigene Cookies)."""

    def __init__(self, make_session):
        self.make_session = make_session
        self.app = app_mit_schranke(make_session, *ROUTER)

    def benutzer(self, name: str, rolle: str = "buero_auftrag", zweiter_faktor: bool = False) -> AppUser:
        with self.make_session() as db:
            user = AppUser(username=name, display_name=name, role=rolle, active=True, password_hash=hash_password(PASSWORT))
            db.add(user)
            db.commit()
            if zweiter_faktor:
                setup = two_factor.start_setup(db, user)
                two_factor.confirm_setup(db, user, pyotp.TOTP(setup["secret"]).now())
                user.__dict__["_geheimnis"] = setup["secret"]
            db.refresh(user)
            db.expunge(user)
            return user

    def client(self, cookie: str | None = None) -> TestClient:
        c = browser_client(self.app)
        if cookie is not None:
            c.cookies.set(COOKIE_NAME, cookie, domain="testserver.local")  # wie ein vom Server gesetztes
        return c

    def angemeldet(self, name: str, passwort: str = PASSWORT) -> TestClient:
        c = self.client()
        assert c.post("/api/auth/login", json={"username": name, "password": passwort}).status_code == 200
        return c

    def als(self, user: AppUser, zweiter_faktor: bool = True) -> TestClient:
        """Ein Gerät mit einer frischen Sitzung (z. B. ein Administrator mit bestätigtem zweitem Faktor)."""
        with self.make_session() as db:
            wert = sitzungen.neue_sitzung(db, db.get(AppUser, user.id), zweiter_faktor=zweiter_faktor)
            db.commit()
        return self.client(wert)

    def sitzungen_von(self, user: AppUser) -> int:
        with self.make_session() as db:
            return len(db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all())


def _wert(client: TestClient) -> str:
    return client.cookies.get(COOKIE_NAME)


def _status(welt: Welt, wert: str, pfad: str = "/api/probe") -> int:
    """Eine Anfrage nur mit diesem Cookie-Wert (ein anderes Gerät, z. B. wer den Wert mitgelesen hat)."""
    return welt.client(wert).get(pfad, follow_redirects=False).status_code


@pytest.fixture
def welt():
    engine, make_session = neue_datenbank()
    yield Welt(make_session)
    engine.dispose()


# ---------------------------------------------------------------------------
# Abmelden
# ---------------------------------------------------------------------------

def test_abmelden_beendet_die_sitzung_auf_dem_server(welt):
    bea = welt.benutzer("bea")
    geraet = welt.angemeldet("bea")
    vorher = _wert(geraet)
    assert _status(welt, vorher) == 200
    assert geraet.post("/api/auth/logout").status_code == 200
    # Angriffstest: der alte Wert von einem anderen Gerät aus -- API 401, Seite auf die Anmeldung.
    assert _status(welt, vorher) == 401
    antwort = welt.client(vorher).get("/seite", follow_redirects=False)
    assert (antwort.status_code, antwort.headers["location"]) == (302, "/login?next=%2Fseite")
    assert welt.sitzungen_von(bea) == 0


def test_abmelden_beendet_nur_die_eigene_sitzung(welt):
    welt.benutzer("bea")
    a, b = welt.angemeldet("bea"), welt.angemeldet("bea")
    wert_a, wert_b = _wert(a), _wert(b)
    b.post("/api/auth/logout")
    assert _status(welt, wert_b) == 401
    assert _status(welt, wert_a) == 200


def test_abmelden_ohne_gueltige_sitzung_geht(welt):
    welt.benutzer("bea")
    assert welt.client().post("/api/auth/logout").status_code == 200
    assert welt.client("kein-gueltiger-wert").post("/api/auth/logout").status_code == 200


# ---------------------------------------------------------------------------
# Der Cookie-Wert
# ---------------------------------------------------------------------------

def test_anmeldung_vergibt_einen_neuen_wert_und_beendet_den_mitgeschickten(welt):
    """Sitzungsfixierung: ein vorher gesetzter (oder alter) Wert gilt nach der Anmeldung nicht."""
    welt.benutzer("bea")
    vorher = welt.angemeldet("bea")
    alter_wert = _wert(vorher)
    vorher.post("/api/auth/login", json={"username": "bea", "password": PASSWORT})
    assert _wert(vorher) != alter_wert
    assert _status(welt, alter_wert) == 401
    assert _status(welt, _wert(vorher)) == 200

    untergeschoben = welt.client("vom-angreifer-gesetzt-" + uuid.uuid4().hex)
    gesetzt = _wert(untergeschoben)
    untergeschoben.post("/api/auth/login", json={"username": "bea", "password": PASSWORT})
    assert _wert(untergeschoben) != gesetzt
    assert _status(welt, gesetzt) == 401


def test_gespeichert_ist_nur_der_hash(welt):
    welt.benutzer("bea")
    wert = _wert(welt.angemeldet("bea"))
    with welt.make_session() as db:
        zeilen = db.scalars(select(UserSession)).all()
        assert [z.token_hash for z in zeilen] == [hashlib.sha256(wert.encode()).hexdigest()]
        roh = db.execute(text("SELECT * FROM user_sessions")).all()
    assert wert not in repr(roh)
    assert len(wert) >= 40  # token_urlsafe(32)


@pytest.mark.parametrize("wert", ["", "x", "a" * 43, "a" * 10_000, "%00", "%C3%A4" * 10, "a;b=c"])
def test_erfundener_oder_kaputter_wert_gilt_nicht(welt, wert):
    welt.benutzer("bea")
    welt.angemeldet("bea")
    assert _status(welt, wert) == 401


def test_zustandsloses_cookie_von_frueher_gilt_nicht_mehr(welt):
    """Ein bis 1.8.97 gültiger Wert (Benutzer-ID, Ablauf, HMAC über secret_key()) -- wer secret_key() kennt, konnte sich damit
    jede Sitzung selbst ausstellen."""
    bea = welt.benutzer("bea")
    payload = f"{bea.id}:{int(time.time()) + 3600}"
    sig = hmac.new(secret_key(), payload.encode(), hashlib.sha256).hexdigest()
    alt = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
    assert _status(welt, alt) == 401


def test_abgelaufene_sitzung_gilt_nicht_und_die_anmeldung_raeumt_auf(welt):
    bea = welt.benutzer("bea")
    wert = _wert(welt.angemeldet("bea"))
    with welt.make_session() as db:
        db.execute(UserSession.__table__.update().values(expires_at=datetime.utcnow() - timedelta(seconds=1)))
        db.commit()
    assert _status(welt, wert) == 401
    assert welt.sitzungen_von(bea) == 1  # Lesen schreibt nicht (Regel 23)
    welt.angemeldet("bea")
    assert welt.sitzungen_von(bea) == 1  # die abgelaufene ist weg, die neue da


def test_sitzung_eines_inaktiven_benutzers_gilt_nicht(welt):
    bea = welt.benutzer("bea")
    wert = _wert(welt.angemeldet("bea"))
    with welt.make_session() as db:
        db.get(AppUser, bea.id).active = False
        db.commit()
    assert _status(welt, wert) == 401


def test_lesen_schreibt_nicht(welt):
    """Die Schranke liest die Sitzung, schreibt sie nie (keine gleitende Verlängerung, Regel 23)."""
    welt.benutzer("bea")
    geraet = welt.angemeldet("bea")
    bind = welt.make_session().get_bind()
    geschrieben = []

    def _merken(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().split(" ", 1)[0].upper() in ("INSERT", "UPDATE", "DELETE"):
            geschrieben.append(statement)

    event.listen(bind, "before_cursor_execute", _merken)
    try:
        for _ in range(3):
            assert geraet.get("/api/probe").status_code == 200
            assert geraet.get("/api/auth/status").status_code == 200
    finally:
        event.remove(bind, "before_cursor_execute", _merken)
    assert geschrieben == []


def test_benutzer_loeschen_nimmt_seine_sitzungen_mit(welt):
    """Unter SQLite ohne erzwungene Fremdschlüssel -- und SQLite vergibt die höchste ID nach dem Löschen neu: eine liegen gebliebene
    Sitzung gehörte sonst dem nächsten neuen Benutzer."""
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    weg = welt.benutzer("weg")
    wert = _wert(welt.angemeldet("weg"))
    assert welt.als(anna).delete(f"/api/users/{weg.id}").status_code == 200
    with welt.make_session() as db:
        assert db.scalars(select(UserSession).where(UserSession.user_id == weg.id)).all() == []
    neu = welt.benutzer("neu")
    assert neu.id == weg.id  # dieselbe ID -- genau der Fall
    assert _status(welt, wert) == 401


# ---------------------------------------------------------------------------
# Passwort, zweiter Faktor, Deaktivieren: alle Sitzungen des Benutzers enden
# ---------------------------------------------------------------------------

def test_eigenes_passwort_beendet_alle_sitzungen_dieses_geraet_bleibt(welt):
    bea = welt.benutzer("bea")
    hier, dort = welt.angemeldet("bea"), welt.angemeldet("bea")
    hier_vorher, dort_vorher = _wert(hier), _wert(dort)
    antwort = hier.post("/api/account/change-password", json={"current_password": PASSWORT, "new_password": NEU})
    assert antwort.status_code == 200
    assert _status(welt, dort_vorher) == 401
    assert dort.get("/api/probe").status_code == 401
    assert _status(welt, hier_vorher) == 401        # auch der alte Wert dieses Geräts
    assert hier.get("/api/probe").status_code == 200  # dieses Gerät hat einen neuen
    assert _wert(hier) != hier_vorher
    assert welt.sitzungen_von(bea) == 1


def test_falsches_aktuelles_passwort_beendet_nichts(welt):
    welt.benutzer("bea")
    hier, dort = welt.angemeldet("bea"), welt.angemeldet("bea")
    assert hier.post("/api/account/change-password", json={"current_password": "falsch-falsch", "new_password": NEU}).status_code == 401
    assert dort.get("/api/probe").status_code == 200


def test_administrator_setzt_passwort_beendet_alle_sitzungen_des_benutzers(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    admin = welt.als(anna)
    a, b = _wert(welt.angemeldet("bea")), _wert(welt.angemeldet("bea"))
    antwort = admin.put(f"/api/users/{bea.id}", json={"username": "bea", "display_name": "bea", "employee_id": None,
                                                      "role": "buero_auftrag", "active": True, "new_password": NEU})
    assert antwort.status_code == 200
    assert (_status(welt, a), _status(welt, b)) == (401, 401)
    assert admin.get("/api/probe").status_code == 200  # der Administrator selbst bleibt
    assert welt.sitzungen_von(bea) == 0


def test_administrator_setzt_sein_eigenes_passwort_bleibt_angemeldet(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    welt.benutzer("zweite", "admin", zweiter_faktor=True)
    admin, anderes_geraet = welt.als(anna), welt.als(anna)
    vorher = _wert(admin)
    antwort = admin.put(f"/api/users/{anna.id}", json={"username": "anna", "display_name": "anna", "employee_id": None,
                                                       "role": "admin", "active": True, "new_password": NEU})
    assert antwort.status_code == 200
    assert _status(welt, vorher) == 401
    assert anderes_geraet.get("/api/probe").status_code == 401
    assert admin.get("/api/probe").status_code == 200  # neue Sitzung, zweiter Faktor bleibt bestätigt


def test_deaktivieren_beendet_alle_sitzungen_auch_nach_dem_reaktivieren(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    admin = welt.als(anna)
    wert = _wert(welt.angemeldet("bea"))
    daten = {"username": "bea", "display_name": "bea", "employee_id": None, "role": "buero_auftrag", "new_password": None}
    assert admin.put(f"/api/users/{bea.id}", json={**daten, "active": False}).status_code == 200
    assert welt.sitzungen_von(bea) == 0
    assert admin.put(f"/api/users/{bea.id}", json={**daten, "active": True}).status_code == 200
    assert _status(welt, wert) == 401  # reaktiviert -- die alte Sitzung lebt nicht wieder auf


def test_andere_aenderungen_lassen_die_sitzungen(welt):
    """Gegenstück: Name oder Rolle ändern beendet keine Sitzung (die Rolle wird je Anfrage frisch gelesen)."""
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    wert = _wert(welt.angemeldet("bea"))
    antwort = welt.als(anna).put(f"/api/users/{bea.id}", json={"username": "bea", "display_name": "Bea B.", "employee_id": None,
                                                              "role": "buero_finanzen", "active": True, "new_password": None})
    assert antwort.status_code == 200
    assert _status(welt, wert) == 200


def test_zweiter_faktor_zuruecksetzen_beendet_alle_sitzungen(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    berta = welt.benutzer("berta", "admin", zweiter_faktor=True)
    bestaetigt, offen = welt.als(berta, zweiter_faktor=True), welt.als(berta, zweiter_faktor=False)
    assert welt.als(anna).post(f"/api/users/{berta.id}/reset-two-factor").status_code == 200
    assert bestaetigt.get("/api/probe").status_code == 401
    assert offen.get("/api/account/2fa/setup/start").status_code == 401
    assert welt.sitzungen_von(berta) == 0


def test_notfallskript_beendet_alle_sitzungen(welt):
    """scripts/reset_admin_2fa.py ruft two_factor.reset() -- dieselbe Stelle."""
    berta = welt.benutzer("berta", "admin", zweiter_faktor=True)
    geraet = welt.als(berta)
    with welt.make_session() as db:
        two_factor.reset(db, db.get(AppUser, berta.id))
    assert geraet.get("/api/probe").status_code == 401


def test_ersteinrichtung_beendet_die_anderen_sitzungen(welt):
    anna = welt.benutzer("anna", "admin")
    hier, dort = welt.angemeldet("anna"), welt.angemeldet("anna")
    hier_vorher = _wert(hier)
    geheimnis = hier.post("/api/account/2fa/setup/start").json()["secret"]
    antwort = hier.post("/api/account/2fa/setup/confirm", json={"code": pyotp.TOTP(geheimnis).now()})
    assert antwort.status_code == 200
    assert dort.get("/api/account/2fa/setup/start").status_code == 401  # Sitzung beendet, nicht nur "zweiter Faktor offen"
    assert dort.get("/api/auth/status").json()["authenticated"] is False
    assert _status(welt, hier_vorher) == 401
    assert hier.get("/api/probe").status_code == 200
    assert welt.sitzungen_von(anna) == 1


def test_bestaetigung_des_zweiten_faktors_gibt_einen_neuen_wert(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    geraet = welt.angemeldet("anna")
    vorher = _wert(geraet)
    assert geraet.get("/api/probe").json()["two_factor_pending"] is True
    code = pyotp.TOTP(anna.__dict__["_geheimnis"]).now()
    assert geraet.post("/api/account/2fa/verify", json={"code": code}).status_code == 200
    assert geraet.get("/api/probe").status_code == 200
    assert _wert(geraet) != vorher
    assert _status(welt, vorher) == 401  # wer den Wert vor der Bestätigung kannte, hat nichts davon


def test_zweiter_faktor_gilt_je_sitzung(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    a = welt.angemeldet("anna")
    a.post("/api/account/2fa/verify", json={"code": pyotp.TOTP(anna.__dict__["_geheimnis"]).now()})
    b = welt.angemeldet("anna")
    assert a.get("/api/probe").status_code == 200
    antwort = b.get("/api/probe")
    assert (antwort.status_code, antwort.json().get("two_factor_pending")) == (401, True)


def test_altes_cookie_des_zweiten_faktors_hilft_nicht(welt):
    """Angriff bis 1.8.97: das Cookie dk_erp_otp_ok war an den Benutzer gebunden, nicht an die Sitzung -- wer es aus einer früheren
    Sitzung hatte (12 h gültig), sparte sich bei einer neuen Anmeldung mit dem Passwort den zweiten Faktor."""
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    payload = f"{anna.id}:{int(time.time()) + 3600}"
    sig = hmac.new(secret_key(), ("otp:" + payload).encode(), hashlib.sha256).hexdigest()
    otp_alt = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
    geraet = welt.client()
    geraet.cookies.set(OTP_COOKIE_NAME, otp_alt, domain="testserver.local")
    assert geraet.post("/api/auth/login", json={"username": "anna", "password": PASSWORT}).json()["otp_ok"] is False
    geraet.cookies.set(OTP_COOKIE_NAME, otp_alt, domain="testserver.local")  # die Anmeldung löscht es -- ein Angreifer schickt es trotzdem
    antwort = geraet.get("/api/probe")
    assert (antwort.status_code, antwort.json().get("two_factor_pending")) == (401, True)


# ---------------------------------------------------------------------------
# Gegen PostgreSQL (Regel 27: Wegwerf-Schema)
# ---------------------------------------------------------------------------

@pytest.fixture
def pg_welt():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from sqlalchemy.orm import close_all_sessions
    from sqlalchemy.pool import NullPool

    schema = f"pgtest_sitzung_{uuid.uuid4().hex[:8]}"
    verwaltung = create_engine(url, poolclass=NullPool)
    with verwaltung.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, poolclass=NullPool, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        yield Welt(sessionmaker(bind=engine))
    finally:
        close_all_sessions()
        engine.dispose()
        with verwaltung.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        verwaltung.dispose()


def test_pg_abmelden_passwort_deaktivieren(pg_welt):
    welt = pg_welt
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bea = welt.benutzer("bea")
    geraet = welt.angemeldet("bea")
    vorher = _wert(geraet)
    geraet.post("/api/auth/logout")
    assert _status(welt, vorher) == 401

    hier, dort = welt.angemeldet("bea"), welt.angemeldet("bea")
    dort_vorher = _wert(dort)
    assert hier.post("/api/account/change-password", json={"current_password": PASSWORT, "new_password": NEU}).status_code == 200
    assert _status(welt, dort_vorher) == 401
    assert hier.get("/api/probe").status_code == 200

    wert = _wert(welt.angemeldet("bea", NEU))
    daten = {"username": "bea", "display_name": "bea", "employee_id": None, "role": "buero_auftrag", "new_password": None}
    assert welt.als(anna).put(f"/api/users/{bea.id}", json={**daten, "active": False}).status_code == 200
    assert _status(welt, wert) == 401
    assert welt.sitzungen_von(bea) == 0


def test_pg_benutzer_loeschen_mit_sitzung(pg_welt):
    """ON DELETE CASCADE und die ORM-Beziehung: Löschen eines Benutzers mit Sitzungen scheitert nicht am Fremdschlüssel."""
    welt = pg_welt
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    weg = welt.benutzer("weg")
    welt.angemeldet("weg")
    assert welt.als(anna).delete(f"/api/users/{weg.id}").status_code == 200
    assert welt.sitzungen_von(weg) == 0
