"""Verwaltung der KI-Einstellungen (Fundament, seit 1.6.2) -- Muster app/email_sending.py::
load_smtp_settings()/update_smtp_settings() (Singleton mit verschlüsseltem Schlüssel,
"None beim Schreiben = unverändert lassen"). Nur für Administratoren zugänglich (siehe
app/routers/ai_settings.py) -- Systemkonfiguration, nicht einmal buero_finanzen
(Betreibervorgabe)."""

from sqlalchemy.orm import Session

from .grunddaten import einzelzeile
from .ai_types import AI_PROVIDERS
from .crypto import encrypt_secret
from .models import AISettings


def load_ai_settings(db: Session) -> AISettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, AISettings)


def update_ai_settings(
    db: Session, *, enabled: bool, provider: str | None, api_base_url: str | None,
    model: str | None, api_key: str | None = None,
) -> AISettings:
    """api_key=None bedeutet "unverändert lassen" (Muster update_smtp_settings()) -- das
    bereits gespeicherte, verschlüsselte Feld bleibt dann unangetastet. provider wird
    ausschließlich gegen die vier echten Anbieter (AI_PROVIDERS) geprüft -- "mock" kann über
    diesen Weg nie persistiert werden, unabhängig davon, was ein Aufrufer schickt."""
    if provider is not None and provider not in AI_PROVIDERS:
        raise ValueError(f"Unbekannter Anbieter: {provider}")
    settings = load_ai_settings(db)
    settings.enabled = enabled
    settings.provider = provider
    settings.api_base_url = api_base_url
    settings.model = model
    if api_key:
        settings.api_key_encrypted = encrypt_secret(api_key)
    db.commit()
    db.refresh(settings)
    return settings


def is_ai_available(db: Session) -> bool:
    """Für aufrufenden Code (künftige Fachfunktionen): true nur, wenn der Gesamtschalter an
    UND ein Anbieter gewählt ist -- prüft NICHT, ob dafür bereits ein echter Adapter existiert
    (das entscheidet sich erst beim tatsächlichen Aufruf, siehe app/ai_service.py::call_ai()).
    Reicht als schnelle Vorprüfung, ob eine KI-Funktion in der Oberfläche überhaupt angeboten
    werden sollte (Muster app/modules.py::is_module_enabled())."""
    settings = load_ai_settings(db)
    return bool(settings.enabled and settings.provider)
