"""Router: users

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 4 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import two_factor
from ..auth import hash_password, user_from_request, users_exist
from ..database import get_db
from ..deps import require_admin
from ..models import AppUser, Employee
from ..schemas import AppUserCreate, AppUserOut, AppUserUpdate

router = APIRouter()

@router.get("/api/users", response_model=list[AppUserOut])
def list_app_users(db: Session = Depends(get_db)):
    return db.scalars(select(AppUser).order_by(AppUser.display_name)).all()


@router.post("/api/users", response_model=AppUserOut)
def create_app_user(payload: AppUserCreate, request: Request, db: Session = Depends(get_db)):
    configured = users_exist(db)
    current = user_from_request(db, request)
    if configured and (current is None or current.role != "admin"):
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen ERP-Benutzer anlegen.")
    if db.scalar(select(AppUser).where(AppUser.username == payload.username.strip())):
        raise HTTPException(status_code=409, detail="Benutzername ist bereits vergeben.")
    if payload.employee_id is not None and db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=422, detail="Mitarbeiter wurde nicht gefunden.")
    user = AppUser(username=payload.username.strip(), password_hash=hash_password(payload.password), display_name=payload.display_name.strip(), employee_id=payload.employee_id, role=("admin" if not configured else payload.role), active=payload.active)
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.put("/api/users/{user_id}", response_model=AppUserOut)
def update_app_user(user_id: int, payload: AppUserUpdate, db: Session = Depends(get_db), current: AppUser = Depends(require_admin("Nur Administratoren dürfen ERP-Benutzer ändern."))):
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="ERP-Benutzer nicht gefunden.")
    username = payload.username.strip()
    duplicate = db.scalar(select(AppUser).where(AppUser.username == username, AppUser.id != user_id))
    if duplicate:
        raise HTTPException(status_code=409, detail="Benutzername ist bereits vergeben.")
    if payload.employee_id is not None and db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=422, detail="Mitarbeiter wurde nicht gefunden.")

    active_admins = db.scalars(select(AppUser).where(AppUser.role == "admin", AppUser.active == True)).all()
    removes_active_admin = user.role == "admin" and user.active and (payload.role != "admin" or not payload.active)
    if removes_active_admin and len(active_admins) <= 1:
        raise HTTPException(status_code=409, detail="Der letzte aktive Administrator kann nicht deaktiviert oder herabgestuft werden.")
    if user.id == current.id and (payload.role != "admin" or not payload.active):
        raise HTTPException(status_code=409, detail="Das aktuell angemeldete Administratorkonto kann sich nicht selbst deaktivieren oder herabstufen.")

    user.username = username
    user.display_name = payload.display_name.strip()
    user.employee_id = payload.employee_id
    user.role = payload.role
    user.active = payload.active
    if payload.new_password:
        user.password_hash = hash_password(payload.new_password)
    db.commit(); db.refresh(user)
    return user


@router.post("/api/users/{user_id}/reset-two-factor")
def reset_user_two_factor(user_id: int, db: Session = Depends(get_db), current: AppUser = Depends(require_admin("Nur Administratoren dürfen den zweiten Faktor zurücksetzen."))):
    """Setzt den zweiten Faktor eines ANDEREN Administrators zurück (verlorenes/neues Telefon) --
    bewusst nicht für das eigene Konto (siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für
    Administratoren"): sonst ließe sich die Pflicht zum zweiten Faktor über die eigene
    Benutzerverwaltung wieder abschalten. Existiert nur ein einziger aktiver Administrator, gibt
    es keinen ANDEREN, der das hier tun könnte -- dann bleiben nur die eigenen
    Wiederherstellungscodes oder scripts/reset_admin_2fa.py auf dem Server."""
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="ERP-Benutzer nicht gefunden.")
    if user.id == current.id:
        raise HTTPException(status_code=409, detail="Der eigene zweite Faktor kann hier nicht zurückgesetzt werden -- dafür sind die eigenen Wiederherstellungscodes oder das Notfallskript auf dem Server nötig.")
    two_factor.reset(db, user)
    return {"ok": True}


@router.delete("/api/users/{user_id}")
def delete_app_user(user_id: int, db: Session = Depends(get_db), current: AppUser = Depends(require_admin("Nur Administratoren dürfen ERP-Benutzer löschen."))):
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="ERP-Benutzer nicht gefunden.")
    if user.id == current.id:
        raise HTTPException(status_code=409, detail="Das aktuell angemeldete Benutzerkonto kann nicht gelöscht werden.")
    if user.role == "admin" and user.active:
        active_admins = db.scalars(select(AppUser).where(AppUser.role == "admin", AppUser.active == True)).all()
        if len(active_admins) <= 1:
            raise HTTPException(status_code=409, detail="Der letzte aktive Administrator kann nicht gelöscht werden.")
    db.delete(user)
    db.commit()
    return {"ok": True}
