"""Router: outlook_sync_settings -- Gesamtschalter der Outlook-Kalendersynchronisation
(Kalender-Modul, Stufe 2, seit 1.7.1, siehe CLAUDE.md "Kalender" -> "Stufe 2"). Ausschließlich
für Administratoren -- Systemkonfiguration, nicht einmal buero_finanzen (Muster
app/routers/ai_settings.py). Die Graph-Zugangsdaten selbst (Mandant/Client/Secret) werden
weiterhin unter Einstellungen -> E-Mail-Versand gepflegt (app/routers/email_settings.py) --
dieser Router trägt nur den Ein-/Ausschalter plus eine reine Anzeige, ob diese Zugangsdaten
überhaupt vollständig hinterlegt sind."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..email_sending import load_smtp_settings
from ..models import OperationalResource
from ..outlook_calendar_sync import PostfachVergeben, load_outlook_sync_settings, postfach_gewechselt, postfach_pruefen, update_outlook_sync_settings
from ..schemas import GeraetPostfachUpdate, OutlookSyncSettingsOut, OutlookSyncSettingsUpdate

router = APIRouter()

_ADMIN_MESSAGE = "Die Outlook-Kalendersynchronisation ist nur für Administratoren verfügbar."


def _to_out(db: Session) -> OutlookSyncSettingsOut:
    s = load_outlook_sync_settings(db)
    smtp = load_smtp_settings(db)
    graph_configured = bool(smtp.graph_tenant_id and smtp.graph_client_id and smtp.graph_client_secret_encrypted)
    return OutlookSyncSettingsOut(enabled=s.enabled, graph_configured=graph_configured)


@router.get("/api/outlook-sync-settings", response_model=OutlookSyncSettingsOut)
def get_outlook_sync_settings_endpoint(db: Session = Depends(get_db, scope="function"), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    return _to_out(db)


@router.put("/api/outlook-sync-settings", response_model=OutlookSyncSettingsOut)
def put_outlook_sync_settings(payload: OutlookSyncSettingsUpdate, db: Session = Depends(get_db, scope="function"), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    update_outlook_sync_settings(db, enabled=payload.enabled)
    return _to_out(db)


@router.put("/api/outlook-sync-settings/geraete/{resource_id}")
def put_geraet_postfach(resource_id: int, payload: GeraetPostfachUpdate, db: Session = Depends(get_db, scope="function"), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    """Seit 1.9.161: das Postfach eines Geräts (Kran-Kalender); leer nimmt es weg. Wie am Konto: eine Adresse gehört genau einem, 409 mit dem Namen."""
    geraet = db.get(OperationalResource, resource_id)
    if geraet is None:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    try:
        adresse = postfach_pruefen(db, payload.outlook_mailbox, geraet_id=resource_id)
    except PostfachVergeben as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    postfach_gewechselt(db, geraet_id=resource_id, alt=geraet.outlook_mailbox, neu=adresse)
    geraet.outlook_mailbox = adresse
    db.commit()
    return {"id": geraet.id, "outlook_mailbox": geraet.outlook_mailbox}
