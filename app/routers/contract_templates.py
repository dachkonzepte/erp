"""Router: Vertragsvorlagen und Vertragsentwurf am Auftrag (seit 1.8.32, Stufe 2b, Runde 2b-1b Teil 1).

- GET /api/settings/contract-templates: Vorlagen je Vertragsgrundlage samt Platzhalterliste (Büro/Admin).
- PUT /api/settings/contract-templates/{basis_key}: Vorlage speichern -- nur Administratoren, wie die
  Klauseln: die Prüfangabe entscheidet, ob der Vertrag ohne Wasserzeichen gedruckt wird.
- GET /api/orders/{order_id}/contract: Stand des Vertrags am Auftrag (Büro/Admin).
- POST /api/orders/{order_id}/contract: Entwurf von Hand anlegen, etwa für einen Auftrag von vor 1.8.32
  oder nach einer geänderten Vertragsgrundlage (Büro/Admin).
- PUT /api/orders/{order_id}/contract: Fallfelder ändern, Teil-Update (Büro/Admin).
- GET /api/orders/{order_id}/contract/pdf: Vertrags-PDF mit dem Angebot als Anlage (Büro/Admin).

Monteure: kein Zugriff (403), wie auf Auftrag und Angebot als kaufmännische Dokumente.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..contract_basis import CONTRACT_BASES
from ..contract_pdf import build_contract_pdf
from ..contract_templates import (
    contract_state, create_contract_draft, get_order_contract, list_templates, placeholder_list, save_template,
    update_contract_draft,
)
from ..database import get_db
from ..models import AppUser
from ..orders import load_order
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import (
    ContractTemplateOut, ContractTemplatesOverviewOut, ContractTemplateUpdate, OrderContractStateOut,
    OrderContractUpdate,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Verträge und Vertragsvorlagen sind nur für Büro und Administratoren verfügbar."))
_admin_dep = Depends(require_min_role(ROLE_ADMIN, message="Vertragsvorlagen und ihre rechtliche Prüfung pflegen nur Administratoren."))


def _actor_name(request: Request) -> str:
    actor = getattr(request.state, "erp_user", None)
    return getattr(actor, "display_name", None) or getattr(actor, "username", None) or "System"


def _order_or_404(db: Session, order_id: int):
    order = load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return order


@router.get("/api/settings/contract-templates", response_model=ContractTemplatesOverviewOut)
def get_contract_templates(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return {"placeholders": placeholder_list(), "templates": list_templates(db)}


@router.put("/api/settings/contract-templates/{basis_key}", response_model=ContractTemplateOut)
def put_contract_template(
    basis_key: str, payload: ContractTemplateUpdate, request: Request,
    db: Session = Depends(get_db), _role: AppUser = _admin_dep,
):
    if basis_key not in CONTRACT_BASES:
        raise HTTPException(status_code=404, detail="Unbekannte Vertragsgrundlage.")
    try:
        template, review_reset = save_template(
            db, basis_key, title=payload.title, sections=[s.model_dump() for s in payload.sections],
            reviewed_on=payload.reviewed_on, reviewed_by=payload.reviewed_by, actor_name=_actor_name(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**template, "review_reset": review_reset}


@router.get("/api/orders/{order_id}/contract", response_model=OrderContractStateOut)
def get_order_contract_state(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return contract_state(db, _order_or_404(db, order_id))


@router.post("/api/orders/{order_id}/contract", response_model=OrderContractStateOut)
def post_order_contract(order_id: int, request: Request, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    order = _order_or_404(db, order_id)
    try:
        create_contract_draft(db, order, actor_name=_actor_name(request))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return contract_state(db, order)


@router.put("/api/orders/{order_id}/contract", response_model=OrderContractStateOut)
def put_order_contract(
    order_id: int, payload: OrderContractUpdate, request: Request,
    db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    order = _order_or_404(db, order_id)
    contract = get_order_contract(db, order.id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Zu diesem Auftrag gibt es keinen Vertragsentwurf.")
    try:
        update_contract_draft(db, contract, payload.model_dump(exclude_unset=True), actor_name=_actor_name(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return contract_state(db, order)


@router.get("/api/orders/{order_id}/contract/pdf")
def get_order_contract_pdf(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    order = _order_or_404(db, order_id)
    contract = get_order_contract(db, order.id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Zu diesem Auftrag gibt es keinen Vertragsentwurf.")
    try:
        pdf = build_contract_pdf(db, order, contract)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    filename = f"Vertrag_{order.order_number}.pdf".replace("/", "-")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
