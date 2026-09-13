"""Router: auth

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 3 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.

Seit 1.3.34 zweistufig für Administratoren (siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für
Administratoren"): auth_login() prüft weiterhin nur Benutzername/Passwort und setzt das normale
Anmelde-Cookie IMMER, aber für einen Administrator ohne bereits diese Sitzung bestätigten
zweiten Faktor fehlt das separate OTP_COOKIE_NAME-Cookie -- app/main.py's Middleware lässt eine
solche Sitzung dann nur noch an /api/account/2fa/*-Endpunkte (app/routers/account.py) heran, bis
entweder die Ersteinrichtung oder die Code-Abfrage dort abgeschlossen ist.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import login_security
from ..auth import (
    COOKIE_MAX_AGE, COOKIE_NAME, COOKIE_SECURE, OTP_COOKIE_NAME, authenticate, make_cookie, two_factor_required,
    user_from_request, users_exist,
)
from ..database import get_db
from ..schemas import LoginRequest
from ..two_factor import is_configured, remaining_recovery_codes

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/api/auth/status")
def auth_status(request: Request, db: Session = Depends(get_db)):
    configured = users_exist(db)
    user = user_from_request(db, request)
    if user is None:
        return {"configured": configured, "authenticated": False, "user": None}
    otp_ok = getattr(request.state, "otp_ok", True)
    configured_2fa = is_configured(user)
    return {
        "configured": configured,
        "authenticated": True,
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role, "employee_id": user.employee_id},
        "two_factor_required": two_factor_required(user),
        "two_factor_configured": configured_2fa,
        "two_factor_recovery_codes_remaining": remaining_recovery_codes(db, user) if configured_2fa else None,
        "otp_ok": otp_ok,
    }


@router.post("/api/auth/login")
def auth_login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    locked_for = login_security.login_lockout_seconds(db, payload.username, _client_ip(request))
    if locked_for is not None:
        raise HTTPException(status_code=429, detail=f"Zu viele Fehlversuche. Bitte in {locked_for} Sekunden erneut versuchen.")
    user = authenticate(db, payload.username, payload.password, _client_ip(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort ist falsch.")
    response = JSONResponse({
        "id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role,
        "two_factor_required": two_factor_required(user),
        "two_factor_configured": is_configured(user),
    })
    response.set_cookie(COOKIE_NAME, make_cookie(user.id), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    # Jede frische Passwort-Anmeldung verlangt einen frischen Nachweis des zweiten Faktors --
    # ein evtl. noch gültiges OTP-Cookie einer vorherigen Sitzung wird deshalb IMMER entfernt,
    # nicht nur bei fehlendem zweiten Faktor.
    response.delete_cookie(OTP_COOKIE_NAME)
    return response


@router.post("/api/auth/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME)
    response.delete_cookie(OTP_COOKIE_NAME)
    return response
