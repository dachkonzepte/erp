"""Router: outlook_sync_settings -- Gesamtschalter der Outlook-Kalendersynchronisation
(Kalender-Modul, Stufe 2, seit 1.7.1, siehe CLAUDE.md "Kalender" -> "Stufe 2"). Ausschließlich
für Administratoren -- Systemkonfiguration, nicht einmal buero_finanzen (Muster
app/routers/ai_settings.py). Die Graph-Zugangsdaten selbst (Mandant/Client/Secret) werden
weiterhin unter Einstellungen -> E-Mail-Versand gepflegt (app/routers/email_settings.py) --
dieser Router trägt nur den Ein-/Ausschalter plus eine reine Anzeige, ob diese Zugangsdaten
überhaupt vollständig hinterlegt sind."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..email_sending import get_or_create_smtp_settings
from ..outlook_calendar_sync import get_or_create_outlook_sync_settings, update_outlook_sync_settings
from ..schemas import OutlookSyncSettingsOut, OutlookSyncSettingsUpdate

router = APIRouter()

_ADMIN_MESSAGE = "Die Outlook-Kalendersynchronisation ist nur für Administratoren verfügbar."


def _to_out(db: Session) -> OutlookSyncSettingsOut:
    s = get_or_create_outlook_sync_settings(db)
    smtp = get_or_create_smtp_settings(db)
    graph_configured = bool(smtp.graph_tenant_id and smtp.graph_client_id and smtp.graph_client_secret_encrypted)
    return OutlookSyncSettingsOut(enabled=s.enabled, graph_configured=graph_configured)


@router.get("/api/outlook-sync-settings", response_model=OutlookSyncSettingsOut)
def get_outlook_sync_settings_endpoint(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    return _to_out(db)


@router.put("/api/outlook-sync-settings", response_model=OutlookSyncSettingsOut)
def put_outlook_sync_settings(payload: OutlookSyncSettingsUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    update_outlook_sync_settings(db, enabled=payload.enabled)
    return _to_out(db)
