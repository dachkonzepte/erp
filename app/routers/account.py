"""Router: account -- Selbstbedienung "Mein Konto" (seit 1.3.34).

Jeder angemeldete Benutzer kann hier sein eigenes Passwort ändern -- vorher gab es dafür
keinen Weg, nur ein Administrator konnte das Passwort eines ANDEREN Kontos setzen
(routers/users.py). Zusätzlich richten Administratoren hier ihren zweiten Faktor ein
(Ersteinrichtung mit QR-Code + Bestätigungscode + einmalige Wiederherstellungscodes) und geben
ihn bei jeder Anmeldung erneut ein (2fa/verify) -- optional mit "Diesem Gerät vertrauen" (seit
1.5.11, app/device_trust.py), das die Code-Abfrage für 30 Tage auf diesem Gerät erspart, ohne
das Passwort zu betreffen. Siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für Administratoren"
für den vollständigen Ablauf inkl. der beiden Sicherheitsfragen.

Die drei 2fa/*-Endpunkte sind bewusst NICHT über require_admin() geschützt (das würde bereits
otp_ok voraussetzen, das hier gerade erst hergestellt wird) -- sie prüfen role=="admin" selbst
und sind in app/main.py's Middleware explizit von der otp_ok-Sperre ausgenommen, damit ein
Administrator ohne bestätigten zweiten Faktor GENAU diese drei Endpunkte noch erreichen kann."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import device_trust
from .. import login_security
from .. import two_factor
from ..auth import COOKIE_MAX_AGE, COOKIE_SECURE, OTP_COOKIE_NAME, hash_password, make_otp_ok_cookie, verify_password
from ..database import get_db
from ..models import AppUser
from ..schemas import ChangePasswordRequest, TwoFactorCodeRequest, TwoFactorVerifyRequest

router = APIRouter()


def _current_user(request: Request, db: Session) -> AppUser:
    """request.state.erp_user wurde von der Middleware über eine EIGENE, bereits wieder
    geschlossene Session geladen -- ein Objekt daraus zu mutieren und über die Session dieses
    Endpunkts (Depends(get_db), eine andere Session) zu committen würde die Änderung
    stillschweigend NICHT persistieren (real aufgetreten, per Smoke-Test gegen eine echte
    Serverinstanz gefunden, siehe CLAUDE.md). Deshalb hier immer über db.get() neu laden."""
    raw = getattr(request.state, "erp_user", None)
    if raw is None:
        raise HTTPException(status_code=401, detail="Bitte zuerst als ERP-Benutzer anmelden.")
    user = db.get(AppUser, raw.id)
    if user is None:
        raise HTTPException(status_code=401, detail="Bitte zuerst als ERP-Benutzer anmelden.")
    return user


@router.post("/api/account/change-password")
def change_password(payload: ChangePasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Aktuelles Passwort ist falsch.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    # Erst das Passwort ändern, dann alle vertrauten Geräte widerrufen -- ein zuvor vertrautes
    # Gerät ist ab jetzt wertlos, siehe CLAUDE.md und TrustedDevice-Klassendocstring.
    device_trust.revoke_all(db, user)
    return {"ok": True}


@router.post("/api/account/2fa/setup/start")
def start_two_factor_setup(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Der zweite Faktor ist nur für Administratoren vorgesehen.")
    if two_factor.is_configured(user):
        raise HTTPException(status_code=409, detail="Der zweite Faktor ist bereits eingerichtet.")
    return two_factor.start_setup(db, user)


@router.post("/api/account/2fa/setup/confirm")
def confirm_two_factor_setup(payload: TwoFactorCodeRequest, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Der zweite Faktor ist nur für Administratoren vorgesehen.")
    if two_factor.is_configured(user):
        raise HTTPException(status_code=409, detail="Der zweite Faktor ist bereits eingerichtet.")
    recovery_codes = two_factor.confirm_setup(db, user, payload.code)
    if recovery_codes is None:
        raise HTTPException(status_code=401, detail="Code ist ungültig. Bitte erneut versuchen.")
    response = JSONResponse({"ok": True, "recovery_codes": recovery_codes})
    response.set_cookie(OTP_COOKIE_NAME, make_otp_ok_cookie(user.id), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    return response


@router.post("/api/account/2fa/verify")
def verify_two_factor(payload: TwoFactorVerifyRequest, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Der zweite Faktor ist nur für Administratoren vorgesehen.")
    if not two_factor.is_configured(user):
        raise HTTPException(status_code=409, detail="Der zweite Faktor ist noch nicht eingerichtet.")
    locked_for = login_security.two_factor_lockout_seconds(db, user.username)
    if locked_for is not None:
        raise HTTPException(status_code=429, detail=f"Zu viele Fehlversuche. Bitte in {locked_for} Sekunden erneut versuchen.")
    if not two_factor.verify_login_code(db, user, payload.code):
        login_security.register_failed_two_factor_attempt(db, user.username)
        raise HTTPException(status_code=401, detail="Code ist ungültig.")
    login_security.clear_failed_two_factor_attempts(db, user.username)
    response = JSONResponse({"ok": True})
    response.set_cookie(OTP_COOKIE_NAME, make_otp_ok_cookie(user.id), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    # Nur bei der ROUTINE-Bestätigung wählbar (dieser Endpunkt) -- niemals bei der
    # Ersteinrichtung (setup/confirm nutzt weiterhin TwoFactorCodeRequest ohne dieses Feld),
    # siehe CLAUDE.md.
    if payload.trust_device:
        trust_cookie_value = device_trust.create_trust(db, user)
        response.set_cookie(
            device_trust.TRUST_COOKIE_NAME, trust_cookie_value, max_age=device_trust.TRUST_MAX_AGE,
            httponly=True, samesite="lax", secure=COOKIE_SECURE,
        )
    return response


@router.post("/api/account/trusted-devices/revoke-all")
def revoke_all_trusted_devices(request: Request, db: Session = Depends(get_db)):
    """"Alle vertrauten Geräte abmelden" -- Selbstbedienung wie change_password(), für jede Rolle
    erreichbar (nur Administratoren haben heute je ein vertrautes Gerät, aber die Funktion ist
    für den eigenen Account gedacht, keine gesonderte Rollenprüfung nötig, siehe CLAUDE.md)."""
    user = _current_user(request, db)
    device_trust.revoke_all(db, user)
    response = JSONResponse({"ok": True})
    response.delete_cookie(device_trust.TRUST_COOKIE_NAME)
    return response
