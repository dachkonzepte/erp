"""Router: quick_service_orders (seit 1.2.12) -- Schnellauftrag für Reparatur/Wartung,
Teil des Moduls "wartungen" (siehe app/modules.py). Prüft is_module_enabled() -- 403 bei
deaktiviertem Modul, gleiches Muster wie app/routers/maintenance_contracts.py."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser
from ..modules import is_module_enabled
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..quick_service_orders import create_quick_service_order
from ..schemas import QuickServiceOrderCreate, QuickServiceOrderOut

router = APIRouter()

MODULE_KEY = "wartungen"

# Seit "Rechtekonzept" (siehe CLAUDE.md): Schnellauftrag ist Büro-/Admin-Bereich (Formular auf
# maintenance_contracts.html) -- kein Endpunkt dieser Datei wird von einer Monteur-Vorlage
# aufgerufen.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Wartungen & Reparaturen ist deaktiviert.")


@router.post("/api/quick-service-orders", response_model=QuickServiceOrderOut)
def post_quick_service_order(payload: QuickServiceOrderCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_quick_service_order(
            db, customer_id=payload.customer_id, property_id=payload.property_id,
            order_type=payload.order_type, title=payload.title, description=payload.description,
            caseworker_employee_id=payload.caseworker_employee_id, execution_start=payload.execution_start,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
