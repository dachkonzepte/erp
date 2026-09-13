"""Router: email_settings (seit 1.0.74, um Microsoft 365/OAuth 2.0 seit
1.0.79 erweitert).

Konfiguration für den allgemeinen E-Mail-Versand -- bewusst eigenständig,
nicht dem Mahnwesen-Router zugeordnet, da künftig für alle Vorgänge
(Angebot/Auftrag/Rechnung/Mahnung) dieselbe Konfiguration gilt. Zwei
wählbare Versandwege: klassisches SMTP oder Microsoft Graph mit OAuth 2.0
(für Microsoft 365, wo SMTP AUTH zunehmend deaktiviert ist).

Nur für Administratoren zugänglich (siehe require_admin in app/deps.py) --
wichtig, sobald mehrere Personen Zugriff auf das ERP haben. Passwort/Secret
werden nie im Klartext zurückgegeben, auch nicht beim Bearbeiten.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..email_sending import (
    check_smtp_connection, get_or_create_smtp_settings, is_smtp_configured,
    set_send_method, update_graph_settings, update_smtp_settings,
)
from ..schemas import GraphSettingsUpdate, SendMethodUpdate, SmtpSettingsOut, SmtpSettingsUpdate

router = APIRouter()

_ADMIN_MESSAGE = "Die E-Mail-Einstellungen sind nur für Administratoren verfügbar."


def _to_out(db: Session) -> SmtpSettingsOut:
    s = get_or_create_smtp_settings(db)
    return SmtpSettingsOut(
        configured=is_smtp_configured(db), send_method=s.send_method,
        host=s.host, port=s.port, username=s.username,
        encryption=s.encryption, sender_email=s.sender_email, sender_name=s.sender_name,
        has_password=bool(s.password_encrypted),
        graph_tenant_id=s.graph_tenant_id, graph_client_id=s.graph_client_id, graph_sender_mailbox=s.graph_sender_mailbox,
        has_graph_client_secret=bool(s.graph_client_secret_encrypted),
    )


@router.get("/api/email-settings", response_model=SmtpSettingsOut)
def get_email_settings(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    return _to_out(db)


@router.put("/api/email-settings/method", response_model=SmtpSettingsOut)
def put_email_send_method(payload: SendMethodUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    set_send_method(db, payload.send_method)
    return _to_out(db)


@router.put("/api/email-settings", response_model=SmtpSettingsOut)
def put_email_settings(payload: SmtpSettingsUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    update_smtp_settings(
        db, host=payload.host, port=payload.port, username=payload.username, encryption=payload.encryption,
        sender_email=payload.sender_email, sender_name=payload.sender_name, password=payload.password,
    )
    return _to_out(db)


@router.put("/api/email-settings/graph", response_model=SmtpSettingsOut)
def put_email_graph_settings(payload: GraphSettingsUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    update_graph_settings(
        db, tenant_id=payload.tenant_id, client_id=payload.client_id,
        sender_mailbox=payload.sender_mailbox, client_secret=payload.client_secret,
    )
    return _to_out(db)


@router.post("/api/email-settings/test")
def post_test_email_settings(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        check_smtp_connection(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
