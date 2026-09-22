"""Die zentrale KI-Schnittstelle (Fundament, seit 1.6.2) -- call_ai()/call_ai_async() sind die
EINEN Stellen, durch die jeder künftige KI-Aufruf im ERP läuft. Kennt nur "Anfrage rein,
Antwort raus" -- welcher Anbieter dahintersteht, ist ausschließlich eine Frage der
Konfiguration (AISettings), nie im aufrufenden Code verdrahtet. Siehe CLAUDE.md
"KI-Fundament" für die volle Herleitung, insbesondere die Entscheidung
synchron-mit-hartem-Zeitlimit-für-den-Anfang und wo ein künftiger Hintergrund-Ablauf andocken
würde.

**Datenschutz-Zusage, keine Bequemlichkeit**: die Anfrage (Prompt, Anhänge) wird an KEINER
Stelle hier oder im Protokoll (AICallLog) gespeichert -- sie geht an adapter.complete() und
ist danach weg. Nur Metadaten werden festgehalten, siehe _log_call()."""

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .ai_adapters import _ADAPTERS, AIProviderAdapter
from .ai_settings import get_or_create_ai_settings
from .ai_types import AIProviderError, AIProviderNotConfigured, AIProviderUnavailable, AIRequest, AIResponse
from .models import AICallLog

# Fest im Code, NICHT in den Einstellungen editierbar (Muster GRAPH_SEND_TIMEOUT in
# app/email_sending.py) -- verhindert, dass ein zu groß gewählter Wert einen Arbeitsprozess
# unnötig lange belegt. 45s: Betreibervorgabe, innerhalb des vorgeschlagenen Rahmens von
# 30-60s (multimodale Anfragen -- Beleg als Bild/PDF -- brauchen länger als ein reiner
# Text-Call).
AI_CALL_TIMEOUT_SECONDS = 45.0


def call_ai(db: Session, request: AIRequest, *, adapter_override: AIProviderAdapter | None = None) -> AIResponse:
    """Synchron -- ruft adapter.complete() in einem eigenen Hintergrund-Thread auf und
    erzwingt AI_CALL_TIMEOUT_SECONDS unabhängig davon, ob der Adapter sein eigenes Zeitlimit
    tatsächlich respektiert (Sicherheitsnetz, siehe _run_with_timeout()).

    WICHTIG für Aufrufer aus einer async def-Route: call_ai() selbst blockiert den rufenden
    Thread bis zu AI_CALL_TIMEOUT_SECONDS -- direkt aus async-Code aufgerufen würde das die
    Event-Loop blockieren (derselbe Fehlertyp, den CLAUDE.md bei post_service_report_photo()
    dokumentiert, hier für einen KI-Aufruf statt einer Bildverkleinerung). Aus async-Code
    deshalb ausschließlich call_ai_async() (unten) verwenden, aus einer gewöhnlichen
    def-Route (von Starlette automatisch threadgepoolt) call_ai() direkt.

    adapter_override ist ausschließlich für Tests gedacht -- ersetzt die
    Einstellungs-/Registry-Auflösung komplett, ohne AISettings anzufassen."""
    started = time.monotonic()
    try:
        adapter = _resolve_adapter(db, adapter_override)
        response = _run_with_timeout(adapter, request)
    except AIProviderError as e:
        _log_call(db, caller=request.caller, success=False, error_type=type(e).__name__, started=started)
        raise

    _log_call(
        db, caller=request.caller, success=True, started=started,
        input_tokens=response.input_tokens, output_tokens=response.output_tokens,
        cost_estimate=response.cost_estimate,
    )
    return response


async def call_ai_async(
    db: Session, request: AIRequest, *, adapter_override: AIProviderAdapter | None = None,
) -> AIResponse:
    """Empfohlener Einstieg aus einer async def-Route -- reicht call_ai() an Starlettes
    Threadpool weiter, damit die Event-Loop währenddessen frei bleibt (siehe call_ai())."""
    return await run_in_threadpool(call_ai, db, request, adapter_override=adapter_override)


def _resolve_adapter(db: Session, adapter_override: AIProviderAdapter | None) -> AIProviderAdapter:
    if adapter_override is not None:
        return adapter_override
    settings = get_or_create_ai_settings(db)
    if not settings.enabled or not settings.provider:
        raise AIProviderNotConfigured(
            "Keine KI konfiguriert -- der Normalzustand. Diese Funktion arbeitet ohne KI weiter."
        )
    factory = _ADAPTERS.get(settings.provider)
    if factory is None:
        raise AIProviderNotConfigured(
            f"Für den Anbieter '{settings.provider}' ist noch kein Adapter hinterlegt."
        )
    return factory(settings)


def _run_with_timeout(adapter: AIProviderAdapter, request: AIRequest) -> AIResponse:
    """Sicherheitsnetz-Timeout: läuft UNABHÄNGIG davon, ob adapter.complete() sein eigenes
    timeout-Argument tatsächlich beachtet. Fallstrick, der hier bewusst vermieden wird: ein
    `with ThreadPoolExecutor(...) as executor:` würde bei __exit__ IMMER `shutdown(wait=True)`
    aufrufen -- das blockiert den rufenden Thread erneut, bis der (ggf. hängende)
    Hintergrund-Thread fertig ist, und würde den Zweck des Timeouts genau dann zunichtemachen,
    wenn er am nötigsten ist. Deshalb explizit `shutdown(wait=False)` im finally-Block: der
    rufende Thread kehrt spätestens nach AI_CALL_TIMEOUT_SECONDS zurück, der verwaiste
    Hintergrund-Thread darf unabhängig davon zu Ende laufen (oder, im pathologischen Fall
    eines Adapters, der sein eigenes Timeout ignoriert, dauerhaft bestehen bleiben -- ein
    bewusst in Kauf genommener, seltener Rest, kein blockierter Arbeitsprozess)."""
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(adapter.complete, request, timeout=AI_CALL_TIMEOUT_SECONDS)
        return future.result(timeout=AI_CALL_TIMEOUT_SECONDS)
    except FutureTimeoutError:
        raise AIProviderUnavailable("Zeitüberschreitung beim KI-Aufruf.") from None
    except AIProviderError:
        raise
    except Exception as e:
        raise AIProviderUnavailable(f"KI-Anbieter nicht erreichbar: {e}") from e
    finally:
        executor.shutdown(wait=False)


def _log_call(
    db: Session, *, caller: str, success: bool, started: float, error_type: str | None = None,
    input_tokens: int | None = None, output_tokens: int | None = None, cost_estimate: float | None = None,
) -> None:
    """Schreibt AUSSCHLIESSLICH Metadaten -- niemals Prompt, Anhänge oder Antworttext. Das
    gilt auch bei einem Fehler: error_type ist der reine Exception-Klassenname, nie dessen
    Text (der könnte bei einem echten Anbieter-Adapter Teile der Anfrage/Antwort enthalten)."""
    duration_ms = int((time.monotonic() - started) * 1000)
    db.add(AICallLog(
        caller=caller, success=success, error_type=error_type,
        input_tokens=input_tokens, output_tokens=output_tokens, cost_estimate=cost_estimate,
        duration_ms=duration_ms,
    ))
    db.commit()
