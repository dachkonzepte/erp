"""Version 1.3.48 -- zwei reale, auf dem Produktivserver beobachtete Fehler in der
1.3.46/1.3.47-Anmelde-Umleitung behoben.

FEHLER 1: /login leitete eine bereits vollständig angemeldete Person (zweiter Faktor
bestätigt) nicht auf next weiter, sondern immer aufs Dashboard -- login_page() (app/routers/
pages.py) ignorierte next bisher komplett. Zusätzlich, als eigentliche Ursache des konkret
gemeldeten Symptoms ("Anmeldemaske erscheint erneut"): account.html's "Zur Startseite"-Link
nutzte history.back(), wenn document.referrer gesetzt war -- während der Zwei-Faktor-Pflicht
zeigte dieser Referrer auf /login, ein Klick sprang deshalb über den Browser-Verlauf (ggf.
aus dem bfcache, ohne jede Serveranfrage) zurück auf die zu diesem Zeitpunkt noch
unangemeldete Login-Ansicht. Behoben: login_page() honoriert next jetzt (mit
_safe_next_target()-Absicherung gegen offene Redirects), der Link ist jetzt ein einfacher
href="/".

FEHLER 2: nach Bestätigung des Codes landete man auf /account (Passwort ändern, Zwei-Faktor-
Status) statt auf dem eigentlichen Ziel. account.html::verifyCode() rief nach einer
erfolgreichen ROUTINEN-Bestätigung (zweiter Faktor war schon eingerichtet) nur load() auf,
was lediglich die Kontoseite selbst neu zeichnete. Behoben: verifyCode() leitet danach auf
next bzw. das Dashboard weiter. Die ERSTEINRICHTUNG (confirmSetup()/finishSetup()) bleibt
unverändert auf /account -- dort müssen erst die einmalig angezeigten
Wiederherstellungscodes gesehen werden, /account ist dort das tatsächliche Ziel. Damit next
über den Zwischenschritt /account hinweg erhalten bleibt, hängt login.html die aktuelle
Query-String jetzt unverändert an die /account-Weiterleitung an.

Zusätzlich geprüft (auf Nachfrage): request.state.otp_ok wird nirgends sonst falsch oder gar
nicht gelesen -- grep über app/ bestätigt genau drei Lesestellen (app/main.py selbst,
app/routers/auth.py::auth_status(), app/routers/pages.py::login_page()), alle drei mit
getattr()-Rückfall bzw. als direkter Empfänger des in main.py gesetzten Werts. Kein weiterer
Fund.

Testaufbau wie in test_v256_login_wall_for_pages.py/test_v250_two_factor_auth.py (eigene,
throwaway In-Memory-SQLite-Engine, eigene, aus den echten Funktionen nachgebaute Middleware,
echter TestClient/echte Cookies) -- hier zusätzlich account_router_module, um die komplette
Zwei-Faktor-Reise (Einrichtung UND Routine-Bestätigung) tatsächlich durchzuspielen. Die
eigentliche JS-Navigation (location.href in login.html/account.html) lässt sich ohne echten
Browser nicht ausführen (dieselbe, wiederholt dokumentierte Werkzeug-Einschränkung dieser
Umgebung) -- geprüft wird deshalb der vollständige SERVERSEITIGE Anteil (welche Antwort/
welches Cookie welchen Redirect nach sich zieht) sowie strukturell, dass die Template-Quellen
tatsächlich die erwartete next-Weitergabe/den erwarteten Redirect-Aufruf enthalten."""

from urllib.parse import quote

import pyotp
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password, otp_ok_for_user, user_from_request, users_exist
from app.database import Base, get_db
from app.main import _blocked_pending_two_factor, _page_requires_login, _request_requires_login
from app.models import AppUser
from app.routers import account as account_router_module
from app.routers import auth as auth_router_module
from app.routers import pages as pages_router_module
from app.routers.pages import _safe_next_target

PASSWORD = "RichtigesPasswort123"


def make_user(db, username="user.test", role="user"):
    user = AppUser(username=username, display_name=username, role=role, active=True,
                    password_hash=hash_password(PASSWORD))
    db.add(user); db.commit()
    return user


def make_valid_code(secret: str) -> str:
    return pyotp.TOTP(secret).now()


def _make_test_app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(pages_router_module.router)
    app.include_router(auth_router_module.router)
    app.include_router(account_router_module.router)
    app.dependency_overrides[get_db] = lambda: make_session()

    @app.middleware("http")
    async def _identity_gate(request: Request, call_next):
        mw_db = make_session()
        try:
            has_users = users_exist(mw_db)
            user = user_from_request(mw_db, request)
        finally:
            mw_db.close()
        request.state.erp_user = user
        otp_ok = True
        if user is not None and user.role == "admin":
            otp_ok = otp_ok_for_user(request, user.id)
        request.state.otp_ok = otp_ok
        if user is None and _request_requires_login(has_users, request.method, request.url.path):
            return JSONResponse(status_code=401, content={"detail": "Bitte zuerst als ERP-Benutzer anmelden."})
        if user is None and _page_requires_login(has_users, request.method, request.url.path):
            return RedirectResponse(url=f"/login?next={quote(request.url.path, safe='')}", status_code=302)
        if user is not None and not otp_ok and _blocked_pending_two_factor(request.url.path):
            return JSONResponse(status_code=401, content={"detail": "Zwei-Faktor-Bestätigung ausstehend.", "two_factor_pending": True})
        return await call_next(request)

    return TestClient(app), make_session


# ---------------------------------------------------------------------------
# _safe_next_target() isoliert -- kein offener Redirect über einen von aussen
# mitgegebenen next-Wert.
# ---------------------------------------------------------------------------

def test_safe_next_target_accepts_a_plain_internal_path():
    assert _safe_next_target("/tasks") == "/tasks"


def test_safe_next_target_rejects_missing_or_empty():
    assert _safe_next_target(None) is None
    assert _safe_next_target("") is None


def test_safe_next_target_rejects_absolute_and_protocol_relative_urls():
    assert _safe_next_target("https://evil.example/phish") is None
    assert _safe_next_target("//evil.example/phish") is None
    assert _safe_next_target("evil.example/phish") is None


# ---------------------------------------------------------------------------
# FEHLER 1: GET /login bei bestehender vollständiger Anmeldung (otp_ok) --
# vier Kombinationen (next: ja/nein, zweiter Faktor bereits eingerichtet: ja/nein
# -- Letzteres wirkt sich hier NICHT unterschiedlich aus, siehe Test unten, das ist
# der Punkt: solange otp_ok wahr ist, ist es fuer diese Entscheidung gleich).
# ---------------------------------------------------------------------------

def test_login_page_redirects_authenticated_otp_ok_user_to_next():
    client, make_session = _make_test_app()
    make_user(make_session())  # kein Admin -- otp_ok ist fuer Nicht-Admins immer wahr
    client.post("/api/auth/login", json={"username": "user.test", "password": PASSWORD})
    resp = client.get("/login?next=%2Ftasks", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/tasks"


def test_login_page_redirects_authenticated_otp_ok_user_to_dashboard_without_next():
    client, make_session = _make_test_app()
    make_user(make_session())
    client.post("/api/auth/login", json={"username": "user.test", "password": PASSWORD})
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_login_page_redirects_admin_with_confirmed_otp_to_next_not_account():
    """Exakt der gemeldete Fehler: ein Administrator, der den zweiten Faktor bereits
    bestätigt hat, muss auf next landen -- NICHT auf /account und NICHT auf die Anmeldemaske."""
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    setup = client.post("/api/account/2fa/setup/start")
    secret = setup.json()["secret"]
    confirm = client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret)})
    assert confirm.status_code == 200  # otp_ok ist ab hier wahr

    resp = client.get("/login?next=%2Ftasks", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/tasks"


def test_login_page_redirects_admin_with_confirmed_otp_to_dashboard_without_next():
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    setup = client.post("/api/account/2fa/setup/start")
    secret = setup.json()["secret"]
    client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret)})

    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_login_page_redirects_admin_pending_setup_to_account_with_next():
    """Zweiter Faktor NOCH NICHT eingerichtet -- geht weiterhin nach /account, next bleibt
    dabei als Query-Parameter erhalten (damit account.html nach der Einrichtung weiss, wohin
    es als naechstes gehen soll -- siehe login.html)."""
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})

    resp = client.get("/login?next=%2Ftasks", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/account?next=%2Ftasks"


def test_login_page_redirects_admin_pending_setup_to_account_without_next():
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})

    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/account"


def test_login_page_redirects_admin_pending_verify_to_account_with_next():
    """Zweiter Faktor BEREITS eingerichtet (aus einer frueheren Sitzung), diese Sitzung hat
    ihn nur noch nicht bestaetigt -- verhaelt sich identisch zum Noch-nicht-eingerichtet-Fall
    oben (das ist der Punkt: login_page() unterscheidet hier nicht, account.html tut das)."""
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    setup = client.post("/api/account/2fa/setup/start")
    secret = setup.json()["secret"]
    client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret)})
    # Neue "Sitzung" ohne OTP-Cookie simulieren, aber weiterhin angemeldet (Login-Cookie bleibt):
    client.cookies.delete("dk_erp_otp_ok")

    resp = client.get("/login?next=%2Ftasks", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/account?next=%2Ftasks"


def test_login_page_redirects_admin_pending_verify_to_account_without_next():
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    setup = client.post("/api/account/2fa/setup/start")
    secret = setup.json()["secret"]
    client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret)})
    client.cookies.delete("dk_erp_otp_ok")

    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/account"


def test_login_page_rejects_unsafe_next_and_falls_back_to_dashboard():
    client, make_session = _make_test_app()
    make_user(make_session())
    client.post("/api/auth/login", json={"username": "user.test", "password": PASSWORD})
    resp = client.get("/login?next=https://evil.example/phish", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


# ---------------------------------------------------------------------------
# FEHLER 2, serverseitiger Anteil: der vollständige Anmelde-Rundweg (mit next/ohne next,
# 2FA nicht eingerichtet -> Einrichtung / 2FA bereits eingerichtet -> Routine-Bestätigung)
# muss otp_ok am Ende korrekt setzen, sodass ein anschliessender Aufruf tatsächlich zum
# eigentlichen Ziel führt statt zurück nach /account.
# ---------------------------------------------------------------------------

def test_round_trip_without_two_factor_leads_to_next():
    client, make_session = _make_test_app()
    make_user(make_session())
    login = client.post("/api/auth/login", json={"username": "user.test", "password": PASSWORD})
    assert login.json()["two_factor_required"] is False
    resp = client.get("/login?next=%2Ftasks", follow_redirects=False)
    assert resp.headers["location"] == "/tasks"


def test_round_trip_through_first_time_setup_leads_to_next_afterwards():
    """2FA war noch nicht eingerichtet -- nach abgeschlossener Einrichtung (Code bestätigt,
    Wiederherstellungscodes einmalig erhalten) fuehrt ein weiterer Aufruf zum eigentlichen
    Ziel, nicht mehr zurueck nach /account."""
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    login = client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    assert login.json()["two_factor_configured"] is False

    setup = client.post("/api/account/2fa/setup/start")
    secret = setup.json()["secret"]
    confirm = client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret)})
    assert len(confirm.json()["recovery_codes"]) > 0

    resp = client.get("/login?next=%2Ftasks", follow_redirects=False)
    assert resp.headers["location"] == "/tasks"


def test_round_trip_through_routine_verify_leads_to_next_afterwards():
    """2FA war schon eingerichtet (aus einer frueheren Sitzung) -- nach der Routine-
    Bestaetigung des Codes dieser Sitzung fuehrt ein weiterer Aufruf zum eigentlichen Ziel,
    nicht zurueck nach /account (das war exakt Fehler 2)."""
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    setup = client.post("/api/account/2fa/setup/start")
    secret = setup.json()["secret"]
    client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret)})

    # Neue "Sitzung" ohne OTP-Cookie, aber weiterhin angemeldet -- wie beim naechsten Login-Tag:
    client.cookies.delete("dk_erp_otp_ok")
    login = client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    assert login.json()["two_factor_configured"] is True

    verify = client.post("/api/account/2fa/verify", json={"code": make_valid_code(secret)})
    assert verify.status_code == 200

    resp = client.get("/login?next=%2Ftasks", follow_redirects=False)
    assert resp.headers["location"] == "/tasks"


# ---------------------------------------------------------------------------
# Strukturprüfung der Templates -- die eigentliche JS-Navigation lässt sich ohne
# echten Browser nicht ausführen, siehe Moduldocstring.
# ---------------------------------------------------------------------------

def test_login_html_forwards_the_query_string_to_account():
    from pathlib import Path
    html = (Path(__file__).parents[1] / "app" / "templates" / "login.html").read_text(encoding="utf-8")
    assert "'/account'+location.search" in html


def test_account_html_verify_code_redirects_via_next_instead_of_reloading():
    from pathlib import Path
    html = (Path(__file__).parents[1] / "app" / "templates" / "account.html").read_text(encoding="utf-8")
    verify_start = html.index("async function verifyCode()")
    verify_end = html.index("\n}", verify_start)
    verify_fn = html[verify_start:verify_end]
    assert "URLSearchParams(location.search).get('next')" in verify_fn
    assert "await load()" not in verify_fn


def test_account_html_setup_flow_still_stays_on_account():
    """Die Ersteinrichtung bleibt unverändert -- die Wiederherstellungscodes müssen erst
    gesehen werden, bevor es weitergeht."""
    from pathlib import Path
    html = (Path(__file__).parents[1] / "app" / "templates" / "account.html").read_text(encoding="utf-8")
    finish_start = html.index("async function finishSetup()")
    finish_end = html.index("\n", finish_start)
    assert "await load()" in html[finish_start:finish_end]


def test_account_html_back_link_has_no_history_back_shortcut():
    from pathlib import Path
    html = (Path(__file__).parents[1] / "app" / "templates" / "account.html").read_text(encoding="utf-8")
    link_start = html.index('class="back no-print"')
    link_end = html.index("</a>", link_start)
    link = html[link_start:link_end]
    assert "history.back" not in link
    assert 'href="/"' in link
