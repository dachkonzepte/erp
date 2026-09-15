"""Router: dashboard (seit 1.0.102) -- Layout-Endpunkte für das
personalisierbare Start-Dashboard. Die eigentlichen Widget-Inhalte (Aufgaben,
Kennzahlen, Projektübersicht) laufen über bereits bestehende Endpunkte und
werden hier nicht dupliziert."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..dashboard import get_widget_layout, save_widget_layout
from ..database import get_db
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..schemas import DashboardWidgetLayoutUpdate, DashboardWidgetOut

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): das eigene Dashboard-Layout ist Selbstbedienung für
# JEDE Rolle -- rein per user.id isoliert, keine büro-spezifischen Daten.
_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))


def _require_login(request: Request):
    user = getattr(request.state, "erp_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Bitte zuerst als ERP-Benutzer anmelden.")
    return user


@router.get("/api/dashboard/widgets", response_model=list[DashboardWidgetOut])
def get_dashboard_widgets(request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    user = _require_login(request)
    return get_widget_layout(db, user.id)


@router.put("/api/dashboard/widgets", response_model=list[DashboardWidgetOut])
def update_dashboard_widgets(payload: DashboardWidgetLayoutUpdate, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    user = _require_login(request)
    return save_widget_layout(db, user.id, [w.model_dump() for w in payload.widgets])
