"""Router: modules (seit 1.0.103) -- Ein-/Ausschalter für optionale ERP-Module.

GET ist für jeden eingeloggten Benutzer erreichbar (Sidebar, Dashboard und die
jeweilige Modul-Seite müssen den Zustand clientseitig prüfen können), PUT nur für
Admins."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import AppUser
from ..modules import list_module_states, set_module_enabled
from ..permissions import ROLE_FIELD, require_min_role
from ..schemas import ModuleStateOut, ModuleStateUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): GET bleibt wie im Moduldocstring oben beschrieben für
# jede Rolle offen (Sidebar/Dashboard/Modul-Seiten prüfen den Zustand clientseitig, auch auf
# Monteur-Seiten) -- reiner Ein/Aus-Zustand, keine sensiblen Daten. PUT bleibt admin-only.
_any_role_dep = Depends(require_min_role(ROLE_FIELD))


@router.get("/api/modules", response_model=list[ModuleStateOut])
def get_modules(db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    return list_module_states(db)


@router.put("/api/modules/{module_key}", response_model=ModuleStateOut)
def update_module(module_key: str, payload: ModuleStateUpdate, db: Session = Depends(get_db),
                   _admin=Depends(require_admin("Nur Administratoren dürfen Module ein- oder ausschalten."))):
    try:
        return set_module_enabled(db, module_key, payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
