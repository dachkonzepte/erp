"""Router: Vertragsgrundlagen (seit 1.8.21, Stufe 2b, Runde 2b-1a).

- GET /api/contract-bases: Auswahl samt Prüfstand der Klausel, für Angebots-Editor und Auftragsseite
  (Büro/Admin, wie Angebot und Auftrag selbst).
- GET /api/settings/contract-basis-clauses: Klauseltexte in den Einstellungen lesen (Büro/Admin).
- PUT /api/settings/contract-basis-clauses/{key}: Klauseltext und "rechtlich geprüft am, durch"
  speichern -- nur Administratoren: die Prüfangabe entscheidet, ob ein Vertragstext auf Angebot und
  Auftrag gedruckt wird.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..contract_basis import CONTRACT_BASES, contract_basis_options, list_clauses, update_clause
from ..database import get_db
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import ContractBasisClauseOut, ContractBasisClauseUpdate, ContractBasisOptionOut

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Vertragsgrundlagen sind nur für Büro und Administratoren verfügbar."))
_admin_dep = Depends(require_min_role(ROLE_ADMIN, message="Klauseltexte und ihre rechtliche Prüfung pflegen nur Administratoren."))


@router.get("/api/contract-bases", response_model=list[ContractBasisOptionOut])
def get_contract_bases(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return contract_basis_options(db)


@router.get("/api/settings/contract-basis-clauses", response_model=list[ContractBasisClauseOut])
def get_contract_basis_clauses(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return list_clauses(db)


@router.put("/api/settings/contract-basis-clauses/{basis_key}", response_model=ContractBasisClauseOut)
def put_contract_basis_clause(
    basis_key: str, payload: ContractBasisClauseUpdate, request: Request,
    db: Session = Depends(get_db), _role: AppUser = _admin_dep,
):
    if basis_key not in CONTRACT_BASES:
        raise HTTPException(status_code=404, detail="Unbekannte Vertragsgrundlage.")
    actor = getattr(request.state, "erp_user", None)
    actor_name = getattr(actor, "display_name", None) or getattr(actor, "username", None) or "System"
    try:
        clause, review_reset = update_clause(
            db, basis_key, clause_text=payload.clause_text, reviewed_on=payload.reviewed_on,
            reviewed_by=payload.reviewed_by, actor_name=actor_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**clause, "review_reset": review_reset}
