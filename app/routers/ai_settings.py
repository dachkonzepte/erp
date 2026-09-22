"""Router: ai_settings -- Fundament für künftige KI-Funktionen (seit 1.6.2, siehe CLAUDE.md
"KI-Fundament"). Ausschließlich für Administratoren -- Systemkonfiguration, nicht einmal
buero_finanzen (Betreibervorgabe), Muster app/routers/email_settings.py: Schlüssel wird nie im
Klartext zurückgegeben, auch nicht beim Bearbeiten.

/test ruft call_ai() mit einer trivialen Anfrage auf -- solange kein echter Anbieter-Adapter
existiert (siehe app/ai_adapters.py), liefert das immer AIProviderNotConfigured -> 400 mit
einer klaren Meldung, auch wenn bereits ein Anbieter/Schlüssel eingetragen ist. Funktioniert
ohne jede Änderung an dieser Datei, sobald ein künftiger, echter Adapter hinzukommt."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai_service import call_ai
from ..ai_settings import get_or_create_ai_settings, update_ai_settings
from ..ai_types import AIProviderError, AIRequest
from ..database import get_db
from ..deps import require_admin
from ..schemas import AISettingsOut, AISettingsUpdate

router = APIRouter()

_ADMIN_MESSAGE = "Die KI-Einstellungen sind nur für Administratoren verfügbar."


def _to_out(db: Session) -> AISettingsOut:
    s = get_or_create_ai_settings(db)
    return AISettingsOut(
        enabled=s.enabled, provider=s.provider, api_base_url=s.api_base_url, model=s.model,
        has_api_key=bool(s.api_key_encrypted),
    )


@router.get("/api/ai-settings", response_model=AISettingsOut)
def get_ai_settings_endpoint(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    return _to_out(db)


@router.put("/api/ai-settings", response_model=AISettingsOut)
def put_ai_settings(payload: AISettingsUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        update_ai_settings(
            db, enabled=payload.enabled, provider=payload.provider,
            api_base_url=payload.api_base_url, model=payload.model, api_key=payload.api_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_out(db)


@router.post("/api/ai-settings/test")
def post_test_ai_settings(db: Session = Depends(get_db), _admin=Depends(require_admin(_ADMIN_MESSAGE))):
    try:
        call_ai(db, AIRequest(caller="einstellungen_test", prompt="Antworte mit einem einzigen Wort: Test."))
    except AIProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
