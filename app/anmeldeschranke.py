"""Anmeldeschranke: Identität, Anmeldepflicht, zweiter Faktor und Cache-Verbot für jede Anfrage (seit 1.8.98 aus app/main.py hierher).

app/main.py bindet middleware(SessionLocal) als HTTP-Middleware ein; Tests binden dieselbe Funktion mit ihrer eigenen Sitzungsfabrik
ein, statt sie nachzubauen (bis 1.8.97 hatten vier Testdateien je eine Nachbildung, die vom Original abweichen konnte).

Seit 1.8.98:
- Die Identität kommt aus einer Sitzung auf dem Server (app/sitzungen.py), der zweite Faktor aus derselben Sitzung.
- Jede Antwort an eine angemeldete Sitzung trägt "Cache-Control: no-store", auch PDFs und Dateien (eine eigene Angabe des Endpunkts
  wird ersetzt), ebenso eine Antwort, die eine Sitzung setzt (Anmeldung). Ohne das zeigte "Zurück" nach dem Abmelden die Seite samt
  Daten aus dem Back-Forward- oder dem HTTP-Cache -- auf dem Fahrzeug-Tablet mit mehreren Monteuren.

Die Entscheidungsregeln (_request_requires_login(), _page_requires_login(), _blocked_pending_two_factor()) sind unverändert und werden
von app/main.py weiter angeboten (ältere Tests importieren sie dort)."""

from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import sitzungen
from .audit import reset_audit_context, set_audit_context
from .auth import COOKIE_NAME, users_exist

logger = logging.getLogger(__name__)

CACHE_VERBOT = "no-store"


def _request_requires_login(has_users: bool, method: str, path: str) -> bool:
    """Ermittelt, ob für diese Anfrage ein angemeldeter ERP-Benutzer nötig ist.

    Greift erst, sobald mindestens ein ERP-Benutzer existiert (der Bootstrap-Fall
    zum Anlegen des allerersten Admin-Kontos bleibt ausgenommen). Die Login-
    Endpunkte selbst (/api/auth/...) bleiben immer erreichbar. Schreibende
    Zugriffe waren bereits zuvor geschützt; seit 1.0.6 zusätzlich lesende API-
    Zugriffe (GET /api/...), da darüber z. B. Mitarbeiterlöhne
    (EmployeeOut.effective_hourly_wage / .annual_gross_wage) und
    Kalkulationsgrundlagen ohne Anmeldung auslesbar waren.
    """
    if not has_users or path.startswith("/api/auth/"):
        return False
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return True
    return method == "GET" and path.startswith("/api/")


# Bleiben ohne Anmeldung erreichbar, obwohl sie keine /api/-Endpunkte sind: /login naturgemäß
# (sonst könnte sich niemand anmelden), /health für externe Überwachung (bereits zuvor
# ungated), /manifest.json als reine PWA-Ressource der Monteursansicht (wird ohnehin nur von
# der bereits angemeldeten Seite /mobil aus verlinkt, siehe app/routers/field_view.py).
_PUBLIC_PAGE_PATHS = {"/login", "/health", "/manifest.json"}


def _page_requires_login(has_users: bool, method: str, path: str) -> bool:
    """Seit 1.3.47: ohne Anmeldung führte jede Seite bisher zu einem stillen Rendern des
    Seiten-Gerüsts (kein Redirect, kein Fehler) -- ob überhaupt etwas nutzbar ist, entschied
    rein die clientseitige JS jeder Seite. Diese Funktion entscheidet stattdessen serverseitig,
    ob eine HTML-Seitenanfrage ohne angemeldeten Benutzer auf /login umgeleitet wird.

    Bewusst getrennt von _request_requires_login() oben, nicht darin verschmolzen: eine
    /api/-Anfrage soll bei fehlender Anmeldung weiterhin die dortige 401-JSON-Antwort bekommen,
    nie einen Redirect auf eine HTML-Seite -- ein API-Client würde eine Login-Seite als Antwort
    nicht sinnvoll verarbeiten können. Bewusst nur GET: Seiten kennen ohnehin kein POST/PUT/....
    """
    if not has_users or method != "GET" or path.startswith("/api/"):
        return False
    return path not in _PUBLIC_PAGE_PATHS


# Diese Endpunkte bleiben für einen Administrator erreichbar, dessen Sitzung das Passwort
# bereits bestätigt hat, aber noch keinen zweiten Faktor -- alles andere unter /api/ ist
# solange blockiert (seit 1.3.34, siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für
# Administratoren"). /api/auth/* ist bereits über _request_requires_login() immer erreichbar,
# taucht hier nicht zusätzlich auf.
_TWO_FACTOR_SETUP_PATHS = {
    "/api/account/2fa/setup/start",
    "/api/account/2fa/setup/confirm",
    "/api/account/2fa/verify",
}


def _blocked_pending_two_factor(path: str) -> bool:
    if not path.startswith("/api/") or path.startswith("/api/auth/"):
        return False
    return path not in _TWO_FACTOR_SETUP_PATHS


def _setzt_sitzung(response) -> bool:
    """Ob die Antwort das Anmelde-Cookie setzt oder löscht (Anmeldung, Abmeldung)."""
    return any(name == b"set-cookie" and value.startswith(COOKIE_NAME.encode() + b"=") for name, value in response.raw_headers)


ANMELDUNG_ABGELAUFEN = ("Anmeldung abgelaufen – bitte in einem neuen Tab anmelden und danach hier erneut speichern. "
                        "Die Eingaben auf dieser Seite bleiben stehen.")
ABGELAUFEN_KOPF = "X-DK-Anmeldung"


def middleware(session_factory):
    """Die Middleware-Funktion (request, call_next) mit session_factory für die eigene, kurzlebige Datenbanksitzung."""

    async def identitaet_und_audit(request: Request, call_next):
        db = session_factory()
        user = None
        sitzung_id = None
        otp_ok = True
        has_users = False
        try:
            has_users = users_exist(db)
            user, sitzung = sitzungen.anmeldung(db, request)
            if user is not None:
                sitzung_id = sitzung.id
                if user.role == "admin":
                    otp_ok = sitzung.second_factor_at is not None
        finally:
            db.close()
        tokens = set_audit_context(user=user, request=request)
        request.state.erp_user = user
        request.state.erp_sitzung_id = sitzung_id
        request.state.otp_ok = otp_ok
        try:
            response = await _weiter(request, call_next, user, has_users, otp_ok)
            if user is not None or _setzt_sitzung(response):
                response.headers["Cache-Control"] = CACHE_VERBOT
            return response
        finally:
            reset_audit_context(tokens)

    return identitaet_und_audit


async def _weiter(request: Request, call_next, user, has_users: bool, otp_ok: bool):
    # Sobald ERP-Benutzer eingerichtet sind, sind schreibende Vorgänge und lesende
    # API-Zugriffe nur angemeldet erlaubt (siehe _request_requires_login).
    if user is None and _request_requires_login(has_users, request.method, request.url.path):
        if request.cookies.get(COOKIE_NAME):
            # Seit 1.8.103: ein Anmelde-Cookie ohne gültige Sitzung (abgelaufen, abgemeldet, beendet) -- die Seite sagt das so und
            # lässt die Eingaben stehen (_speichern.html); nach dem Anmelden in einem neuen Tab geht derselbe Klick wieder.
            return JSONResponse(status_code=401, headers={ABGELAUFEN_KOPF: "abgelaufen"},
                                content={"detail": ANMELDUNG_ABGELAUFEN, "anmeldung_abgelaufen": True})
        return JSONResponse(status_code=401, content={"detail": "Bitte zuerst als ERP-Benutzer anmelden."})
    if user is None and _page_requires_login(has_users, request.method, request.url.path):
        # Dieselbe ?next=<Pfad>-Konvention wie bei den bestehenden Abmelden-Links
        # (_sidebar.html/_topbar.html/_mobile_header.html/vor_ort.html: location.href=
        # '/login?next='+encodeURIComponent(location.pathname)) -- login.html liest und
        # honoriert next bereits (siehe dort), nur der Query-String selbst wird bewusst
        # nicht mitgegeben, exakt wie bei jenen Links.
        next_target = quote(request.url.path, safe="")
        return RedirectResponse(url=f"/login?next={next_target}", status_code=302)
    if user is not None and not otp_ok and _blocked_pending_two_factor(request.url.path):
        return JSONResponse(status_code=401, content={"detail": "Zwei-Faktor-Bestätigung ausstehend.", "two_factor_pending": True})
    try:
        return await call_next(request)
    except Exception:
        # Nur protokollieren, nicht abfangen: dieselbe Exception wird
        # unverändert weitergereicht, sodass sich am Antwortverhalten
        # nichts ändert -- neu ist ausschließlich der Log-Eintrag mit
        # vollständigem Traceback (seit 1.0.8 dauerhaft in data/erp.log
        # statt nur in der Konsole).
        logger.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
        raise
