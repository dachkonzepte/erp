"""Router: auth

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 3 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..auth import COOKIE_MAX_AGE, COOKIE_NAME, COOKIE_SECURE, authenticate, is_login_locked, make_cookie, user_from_request, users_exist
from ..database import get_db
from ..schemas import LoginRequest

router = APIRouter()

@router.get("/api/auth/status")
def auth_status(request: Request, db: Session = Depends(get_db)):
    configured = users_exist(db)
    user = user_from_request(db, request)
    return {"configured": configured, "authenticated": user is not None, "user": ({"id":user.id,"username":user.username,"display_name":user.display_name,"role":user.role,"employee_id":user.employee_id} if user else None)}


@router.post("/api/auth/login")
def auth_login(payload: LoginRequest, db: Session = Depends(get_db)):
    locked_for = is_login_locked(payload.username)
    if locked_for is not None:
        raise HTTPException(status_code=429, detail=f"Zu viele Fehlversuche. Bitte in {locked_for} Sekunden erneut versuchen.")
    user = authenticate(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort ist falsch.")
    response = JSONResponse({"id":user.id,"username":user.username,"display_name":user.display_name,"role":user.role})
    response.set_cookie(COOKIE_NAME, make_cookie(user.id), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    return response


@router.post("/api/auth/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME)
    return response
