"""Router: Vertragsvorlagen und Vertrag am Auftrag (seit 1.8.32, Stufe 2b, Runde 2b-1b; Festschreiben und
Versand seit 1.8.33).

- GET /api/settings/contract-templates: Vorlagen je Vertragsgrundlage samt Platzhalterliste (Büro/Admin).
- PUT /api/settings/contract-templates/{basis_key}: Vorlage speichern -- nur Administratoren, wie die
  Klauseln: die Prüfangabe entscheidet, ob der Vertrag ohne Wasserzeichen gedruckt wird.
- GET /api/orders/{order_id}/contract: Stand des Vertrags am Auftrag samt Fassungen (Büro/Admin).
- POST /api/orders/{order_id}/contract: Entwurf von Hand anlegen, etwa für einen Auftrag von vor 1.8.32,
  einen Schnellauftrag oder nach einer geänderten Vertragsgrundlage (Büro/Admin).
- PUT /api/orders/{order_id}/contract: Fallfelder ändern, Teil-Update, nur im Entwurf (Büro/Admin).
- GET /api/orders/{order_id}/contract/pdf: im Entwurf das Entwurfs-PDF (live, mit Wasserzeichen bei
  ungeprüfter Vorlage), festgeschrieben die gültige Fassung aus der Ablage (Büro/Admin).
- GET /api/orders/{order_id}/contract/attachment-options: welche Fassung des Angebots angehängt würde
  und ob das Büro wählen muss (seit 1.8.33).
- POST /api/orders/{order_id}/contract/freeze: festschreiben (seit 1.8.33).
- POST /api/orders/{order_id}/contract/new-version: festgeschriebenen Vertrag wieder zum Entwurf machen,
  die Fassungen bleiben (seit 1.8.33).
- POST /api/orders/{order_id}/contract/send-email: die gültige Fassung versenden (seit 1.8.33, Regel 21).
- POST /api/orders/{order_id}/contract/sign: Unterschrift von Kunde und Betrieb auf dem Gerät (seit 1.8.34).
- POST /api/orders/{order_id}/contract/sign-paper: Scan des unterschriebenen Papiers (seit 1.8.34).
Ältere Fassungen, Unterschriftsblatt und Scan liefert /api/sent-documents/{id}/file (Ablage, nur mit
stimmender Prüfsumme).

Monteure: kein Zugriff (403), wie auf Auftrag und Angebot als kaufmännische Dokumente.
"""

import base64
import binascii
import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..contract_basis import CONTRACT_BASES
from ..contract_pdf import build_contract_pdf
from ..contract_signatures import MAX_SCAN_BYTES, record_paper_signature, sign_contract_on_device
from ..contract_templates import (
    create_contract_draft, get_order_contract, list_templates, placeholder_list, save_template, update_contract_draft,
)
from ..contract_versions import (
    ContractStateError, attachment_options, contract_state, freeze_contract, frozen_pdf, send_contract_email,
    start_new_version,
)
from ..database import get_db
from ..email_dispatch import DispatchConflict, actor_of
from ..models import AppUser
from ..orders import load_order
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import (
    ContractAttachmentOptionsOut, ContractTemplateOut, ContractTemplatesOverviewOut, ContractTemplateUpdate,
    OrderContractFreeze, OrderContractSignOnDevice, OrderContractStateOut, OrderContractUpdate, OrderEmailSend,
)
from ..sent_documents import ArchiveFileError

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
    headers = {}
    if contract.status == "entwurf":
        try:
            pdf = build_contract_pdf(db, order, contract)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        filename = f"Vertrag_{order.order_number}_Entwurf.pdf".replace("/", "-")
    else:
        # Festgeschrieben: die abgelegten Bytes, nie neu gerendert; beschädigt -> 409/410 wie die Ablage.
        try:
            pdf, version = frozen_pdf(contract)
        except ArchiveFileError as exc:
            raise HTTPException(status_code=410 if exc.status == "fehlt" else 409,
                                detail=f"Die festgeschriebene Fassung in der Ablage ist nicht mehr unversehrt: {exc}") from exc
        filename = version.sent_document.filename
        headers["X-DK-Ablage"] = str(version.sent_document_id)
    headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return Response(content=pdf, media_type="application/pdf", headers=headers)


@router.get("/api/orders/{order_id}/contract/attachment-options", response_model=ContractAttachmentOptionsOut)
def get_contract_attachment_options(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Gewöhnliche def-Route: rendert das Angebot zum Vergleich (Threadpool, nicht die Event-Loop)."""
    order = _order_or_404(db, order_id)
    if get_order_contract(db, order.id) is None:
        raise HTTPException(status_code=404, detail="Zu diesem Auftrag gibt es keinen Vertragsentwurf.")
    return attachment_options(db, order)


@router.post("/api/orders/{order_id}/contract/freeze", response_model=OrderContractStateOut)
def post_freeze_contract(
    order_id: int, payload: OrderContractFreeze, db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    order = _order_or_404(db, order_id)
    user_id, user_name = actor_of(user)
    try:
        freeze_contract(db, order, attachment=payload.attachment, attachment_document_id=payload.attachment_document_id,
                        user_id=user_id, user_name=user_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContractStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return contract_state(db, _order_or_404(db, order_id))


@router.post("/api/orders/{order_id}/contract/new-version", response_model=OrderContractStateOut)
def post_contract_new_version(order_id: int, db: Session = Depends(get_db), user: AppUser = _role_dep):
    order = _order_or_404(db, order_id)
    user_id, user_name = actor_of(user)
    try:
        start_new_version(db, order, user_id=user_id, user_name=user_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContractStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return contract_state(db, _order_or_404(db, order_id))


@router.post("/api/orders/{order_id}/contract/send-email", response_model=OrderContractStateOut)
def post_send_contract_email(
    order_id: int, payload: OrderEmailSend, db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    order = _order_or_404(db, order_id)
    try:
        send_contract_email(db, order, to_email=payload.to_email, cc_email=payload.cc_email,
                            dispatch_key=payload.dispatch_key, user=user)
    except (ContractStateError, DispatchConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return contract_state(db, _order_or_404(db, order_id))


def _png_from_base64(raw: str) -> bytes:
    raw = (raw or "").strip()
    if raw.lower().startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Ungültige Unterschrift (kein gültiges Base64-PNG).") from exc


def _signature_errors(call):
    try:
        return call()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContractStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/orders/{order_id}/contract/sign", response_model=OrderContractStateOut)
def post_sign_contract(
    order_id: int, payload: OrderContractSignOnDevice, db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    """Gewöhnliche def-Route: prüft die Bilder und rendert das Unterschriftsblatt (Threadpool)."""
    order = _order_or_404(db, order_id)
    customer_png = _png_from_base64(payload.customer_signature_png_base64)
    company_png = _png_from_base64(payload.company_signature_png_base64)
    user_id, user_name = actor_of(user)
    _signature_errors(lambda: sign_contract_on_device(
        db, order, version_id=payload.version_id, pdf_sha256=payload.pdf_sha256, checkboxes=payload.checkboxes,
        customer_name=payload.customer_name, customer_png=customer_png, company_name=payload.company_name,
        company_png=company_png, user_id=user_id, user_name=user_name,
    ))
    return contract_state(db, _order_or_404(db, order_id))


@router.post("/api/orders/{order_id}/contract/sign-paper", response_model=OrderContractStateOut)
def post_sign_contract_paper(
    order_id: int, version_id: int = Form(...), pdf_sha256: str = Form(...), signed_on: date = Form(...),
    checkboxes: str = Form("{}"), scan: UploadFile = File(...), db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    """Scan des unterschriebenen Papiers; checkboxes als JSON-Objekt {Schlüssel: true/false}."""
    order = _order_or_404(db, order_id)
    try:
        values = json.loads(checkboxes or "{}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Die Ankreuzfelder sind kein gültiges JSON.") from exc
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="Die Ankreuzfelder müssen ein Objekt {Schlüssel: true/false} sein.")
    scan_bytes = scan.file.read(MAX_SCAN_BYTES + 1)
    user_id, user_name = actor_of(user)
    _signature_errors(lambda: record_paper_signature(
        db, order, version_id=version_id, pdf_sha256=pdf_sha256, signed_on=signed_on, checkboxes=values,
        scan_bytes=scan_bytes, user_id=user_id, user_name=user_name,
    ))
    return contract_state(db, _order_or_404(db, order_id))
