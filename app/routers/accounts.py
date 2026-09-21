"""Router: accounts -- Kontenstamm (Buchhaltung Stufe 2, erster Teil), Teil des Moduls
"buchhaltung" (siehe app/modules.py). Jeder Endpunkt prüft is_module_enabled() -- 403 bei
deaktiviertem Modul, unabhängig von der Rolle, Muster app/routers/incoming_invoices.py.

Ausnahmslos require_min_role(ROLE_OFFICE_FINANZEN) -- derselbe Finanzen-Abschnitt wie
Eingangsrechnungen/Betriebskosten-Übersicht/Kalkulationsgrundlagen."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..accounts import create_account, get_account, list_accounts, update_account
from ..database import get_db
from ..incoming_invoices import MODULE_KEY
from ..models import AppUser
from ..modules import is_module_enabled
from ..permissions import ROLE_OFFICE_FINANZEN, require_min_role
from ..schemas import AccountCreate, AccountOut, AccountUpdate

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_FINANZEN))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Buchhaltung ist deaktiviert.")


@router.get("/api/accounts", response_model=list[AccountOut])
def get_accounts(include_inactive: bool = True, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_accounts(db, include_inactive=include_inactive)


@router.get("/api/accounts/{account_id}", response_model=AccountOut)
def get_account_endpoint(account_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = get_account(db, account_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden.")
    return result


@router.post("/api/accounts", response_model=AccountOut)
def post_account(payload: AccountCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_account(
            db, account_number=payload.account_number, label=payload.label,
            default_tax_rate_pct=payload.default_tax_rate_pct, active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/api/accounts/{account_id}", response_model=AccountOut)
def put_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_account(
            db, account_id, account_number=payload.account_number, label=payload.label,
            default_tax_rate_pct=payload.default_tax_rate_pct, active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden.")
    return result
