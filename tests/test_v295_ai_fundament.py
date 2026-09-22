"""Version 1.6.2 -- KI-Fundament: zentrale, anbieter-unabhängige Schnittstelle für künftige
KI-Funktionen (Belegauswertung, Angebotstexte, Berichtszusammenfassung), siehe CLAUDE.md
"KI-Fundament" für die volle Herleitung. Diese Version baut AUSSCHLIESSLICH das Fundament --
keine Fachfunktion nutzt es. Deckt ab: die Typen/Fehlerklassen (app/ai_types.py), den
Mock-Adapter (app/ai_adapters.py -- macht diese Testsuite selbst unabhängig von jedem echten
KI-Aufruf), die Einstellungsverwaltung (app/ai_settings.py, "mock" nie persistierbar), die
zentrale Schnittstelle call_ai()/call_ai_async() (app/ai_service.py, insbesondere das
Sicherheitsnetz-Zeitlimit UNABHÄNGIG vom Adapter-Verhalten, die Fehlerübersetzung, und dass das
Protokoll NIEMALS Anfrage-/Antwortinhalt speichert -- strukturell, nicht nur inhaltlich
geprüft), sowie den abschließend verlangten Angriffstest: buero_finanzen/buero_auftrag/field
kommen an keinen Teil der KI-Einstellungen, ausschließlich admin."""

import asyncio
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai_adapters import MockAIAdapter, _ADAPTERS
from app.ai_service import call_ai, call_ai_async
from app.ai_settings import get_or_create_ai_settings, is_ai_available, update_ai_settings
from app.ai_types import AI_PROVIDERS, AIAttachment, AIProviderError, AIProviderNotConfigured, AIProviderUnavailable, AIRequest
from app.database import Base
from app.models import AICallLog
from app.routers.ai_settings import router as ai_settings_router

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")
FORBIDDEN_KEYS = {"provider", "api_base_url", "has_api_key", "model", "enabled"}


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# --- Typen/Fehlerklassen ---

def test_ai_providers_does_not_include_mock():
    """'mock' ist ausschließlich für Tests gedacht -- nie über die Einstellungen wählbar."""
    assert "mock" not in AI_PROVIDERS
    assert AI_PROVIDERS == ("anthropic", "openai", "azure_openai", "google")


def test_ai_request_supports_attachments_for_future_belegauswertung():
    """Bewusst schon jetzt vorgesehen, auch wenn noch keine Fachfunktion sie befüllt."""
    request = AIRequest(caller="test", prompt="Was steht auf diesem Beleg?", attachments=[
        AIAttachment(mime_type="image/jpeg", data=b"\xff\xd8\xff", filename="beleg.jpg"),
    ])
    assert request.attachments[0].mime_type == "image/jpeg"


def test_ai_provider_unavailable_and_not_configured_are_both_ai_provider_error():
    assert issubclass(AIProviderNotConfigured, AIProviderError)
    assert issubclass(AIProviderUnavailable, AIProviderError)


# --- Mock-Adapter ---

def test_mock_adapter_returns_a_fixed_response_without_any_network():
    settings = get_or_create_ai_settings(db_session())
    adapter = MockAIAdapter(settings)
    response = adapter.complete(AIRequest(caller="test", prompt="Hallo"), timeout=5.0)
    assert response.text.startswith("[Mock-Antwort]")
    assert response.output_tokens == 8


def test_mock_adapter_can_be_configured_to_raise_for_error_path_tests():
    settings = get_or_create_ai_settings(db_session())
    adapter = MockAIAdapter(settings, raise_error=TimeoutError("simuliert"))
    with pytest.raises(TimeoutError):
        adapter.complete(AIRequest(caller="test", prompt="Hallo"), timeout=5.0)


def test_mock_is_registered_but_no_real_provider_has_an_adapter_in_this_round():
    """Betreibervorgabe: kein echter Anbieter-Adapter in dieser Runde."""
    assert "mock" in _ADAPTERS
    for provider in AI_PROVIDERS:
        assert provider not in _ADAPTERS


# --- Einstellungen ---

def test_fresh_settings_default_to_disabled_and_unconfigured():
    db = db_session()
    settings = get_or_create_ai_settings(db)
    assert settings.enabled is False
    assert settings.provider is None
    assert is_ai_available(db) is False


def test_update_ai_settings_rejects_mock_and_unknown_providers():
    db = db_session()
    with pytest.raises(ValueError, match="Anbieter"):
        update_ai_settings(db, enabled=True, provider="mock", api_base_url=None, model=None)
    with pytest.raises(ValueError, match="Anbieter"):
        update_ai_settings(db, enabled=True, provider="chatgpt", api_base_url=None, model=None)


def test_update_ai_settings_accepts_real_providers_and_encrypts_the_key():
    db = db_session()
    updated = update_ai_settings(
        db, enabled=True, provider="anthropic", api_base_url="https://api.anthropic.com",
        model="claude-sonnet-5", api_key="sk-geheim-123",
    )
    assert updated.provider == "anthropic"
    assert updated.api_key_encrypted is not None
    assert "sk-geheim-123" not in updated.api_key_encrypted  # tatsächlich verschlüsselt, kein Klartext
    assert is_ai_available(db) is True


def test_update_ai_settings_none_api_key_leaves_stored_key_unchanged():
    db = db_session()
    update_ai_settings(db, enabled=True, provider="openai", api_base_url=None, model=None, api_key="erstwert")
    stored = get_or_create_ai_settings(db).api_key_encrypted
    update_ai_settings(db, enabled=True, provider="openai", api_base_url="https://x", model="gpt", api_key=None)
    assert get_or_create_ai_settings(db).api_key_encrypted == stored


def test_is_ai_available_requires_both_enabled_and_provider():
    db = db_session()
    update_ai_settings(db, enabled=False, provider="anthropic", api_base_url=None, model=None)
    assert is_ai_available(db) is False
    update_ai_settings(db, enabled=True, provider=None, api_base_url=None, model=None)
    assert is_ai_available(db) is False
    update_ai_settings(db, enabled=True, provider="anthropic", api_base_url=None, model=None)
    assert is_ai_available(db) is True


# --- call_ai(): Normalzustand, Dispatch, Fehlerübersetzung ---

def test_call_ai_raises_not_configured_when_disabled_by_default():
    db = db_session()
    with pytest.raises(AIProviderNotConfigured):
        call_ai(db, AIRequest(caller="test_disabled", prompt="Hallo"))
    log = db.query(AICallLog).one()
    assert log.success is False
    assert log.error_type == "AIProviderNotConfigured"
    assert log.caller == "test_disabled"


def test_call_ai_raises_not_configured_when_provider_chosen_but_no_adapter_exists_yet():
    """Ein Anbieter kann bereits eingetragen sein -- ohne echten Adapter (diese Runde) bleibt
    das Ergebnis dasselbe wie "nicht konfiguriert", nur mit spezifischerer Meldung."""
    db = db_session()
    update_ai_settings(db, enabled=True, provider="anthropic", api_base_url=None, model=None)
    with pytest.raises(AIProviderNotConfigured, match="kein Adapter hinterlegt"):
        call_ai(db, AIRequest(caller="test_no_adapter", prompt="Hallo"))


def test_call_ai_succeeds_via_adapter_override_without_touching_settings():
    db = db_session()
    settings = get_or_create_ai_settings(db)
    response = call_ai(
        db, AIRequest(caller="test_mock_success", prompt="Was ist 2+2?"),
        adapter_override=MockAIAdapter(settings),
    )
    assert response.text.startswith("[Mock-Antwort]")
    log = db.query(AICallLog).one()
    assert log.success is True
    assert log.caller == "test_mock_success"
    assert log.output_tokens == 8


def test_call_ai_maps_an_unexpected_adapter_exception_to_provider_unavailable():
    db = db_session()
    settings = get_or_create_ai_settings(db)
    with pytest.raises(AIProviderUnavailable):
        call_ai(
            db, AIRequest(caller="test_mock_error", prompt="Hallo"),
            adapter_override=MockAIAdapter(settings, raise_error=ConnectionError("kein Netz")),
        )
    log = db.query(AICallLog).one()
    assert log.success is False
    assert log.error_type == "AIProviderUnavailable"


def test_call_ai_never_blocks_beyond_the_timeout_even_if_the_adapter_ignores_it(monkeypatch):
    """Regressionstest für den Fallstrick, der beim Bauen gefunden wurde: ein `with
    ThreadPoolExecutor(...) as executor` würde bei __exit__ IMMER auf den (hier absichtlich
    hängenden) Hintergrund-Thread warten und das Zeitlimit dadurch wirkungslos machen. Nach der
    Korrektur (shutdown(wait=False)) kehrt call_ai() spätestens nach dem konfigurierten
    Zeitlimit zurück, unabhängig davon, wie lange der Adapter tatsächlich braucht."""
    import app.ai_service as ai_service

    monkeypatch.setattr(ai_service, "AI_CALL_TIMEOUT_SECONDS", 0.2)

    class HangingAdapter:
        def complete(self, request, *, timeout):
            time.sleep(2.0)  # deutlich länger als das (verkürzte) Zeitlimit
            return None

        def __call__(self, settings):
            return self

    db = db_session()
    started = time.monotonic()
    with pytest.raises(AIProviderUnavailable, match="Zeitüberschreitung"):
        call_ai(db, AIRequest(caller="test_timeout", prompt="Hallo"), adapter_override=HangingAdapter())
    elapsed = time.monotonic() - started
    assert elapsed < 1.0, f"call_ai() kehrte erst nach {elapsed:.2f}s zurück -- Zeitlimit wirkungslos"
    log = db.query(AICallLog).one()
    assert log.success is False
    assert log.error_type == "AIProviderUnavailable"


def test_call_ai_async_offloads_to_threadpool_and_returns_the_same_result(threaded_db_session):
    """call_ai_async() läuft tatsächlich in einem ANDEREN Thread (Starlettes Threadpool) --
    braucht deshalb dieselbe StaticPool/check_same_thread=False-Verbindung wie echte
    Routen-Tests (siehe tests/conftest.py::threaded_db_session), nicht die einfache
    db_session()-Hilfsfunktion dieser Datei."""
    db = threaded_db_session
    settings = get_or_create_ai_settings(db)

    async def run():
        return await call_ai_async(
            db, AIRequest(caller="test_async", prompt="Hallo"), adapter_override=MockAIAdapter(settings),
        )

    response = asyncio.run(run())
    assert response.text.startswith("[Mock-Antwort]")


# --- Protokoll speichert niemals Anfrage-/Antwortinhalt ---

def test_ai_call_log_table_has_no_column_that_could_hold_request_or_response_content():
    """Strukturelle Garantie, nicht nur eine Verhaltensprüfung: das Modell selbst kennt kein
    Feld für Prompt/Anhang/Antworttext -- es KANN dort gar nicht gespeichert werden."""
    column_names = {c.name for c in AICallLog.__table__.columns}
    assert column_names == {
        "id", "occurred_at", "caller", "success", "error_type",
        "input_tokens", "output_tokens", "cost_estimate", "duration_ms",
    }


def test_a_long_prompt_and_attachment_never_end_up_anywhere_in_the_logged_row():
    db = db_session()
    settings = get_or_create_ai_settings(db)
    secret_prompt = "Vertraulicher Beleginhalt, Kundenname Max Mustermann, Betrag 1234,56 EUR"
    call_ai(
        db, AIRequest(
            caller="test_content_never_logged", prompt=secret_prompt,
            attachments=[AIAttachment(mime_type="application/pdf", data=b"%PDF-1.4 geheim")],
        ),
        adapter_override=MockAIAdapter(settings),
    )
    log = db.query(AICallLog).one()
    for column in AICallLog.__table__.columns:
        value = getattr(log, column.name)
        assert "Mustermann" not in str(value)
        assert "geheim" not in str(value)
        assert "1234,56" not in str(value)


def test_error_type_is_the_exception_class_name_never_its_text():
    """error_type darf nie den Ausnahmentext tragen -- der könnte bei einem echten
    Anbieter-Adapter Teile der Anfrage enthalten (siehe Docstring AICallLog)."""
    db = db_session()
    settings = get_or_create_ai_settings(db)
    secret_in_message = "Fehler beim Verarbeiten von Beleg Kundennummer 99887766"
    with pytest.raises(AIProviderUnavailable):
        call_ai(
            db, AIRequest(caller="test_error_text", prompt="Hallo"),
            adapter_override=MockAIAdapter(settings, raise_error=RuntimeError(secret_in_message)),
        )
    log = db.query(AICallLog).one()
    assert log.error_type == "AIProviderUnavailable"
    assert "99887766" not in (log.error_type or "")


# --- Angriffstest: nur admin sieht/konfiguriert die KI-Einstellungen ---

def test_ai_settings_endpoints_require_admin_only(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role in ALL_ROLES:
        client = router_test_client(db, ai_settings_router, role=role)
        expected = 200 if role == "admin" else 403
        get_resp = client.get("/api/ai-settings")
        assert get_resp.status_code == expected, (role, get_resp.text)
        put_resp = client.put("/api/ai-settings", json={"enabled": True, "provider": "anthropic", "api_base_url": None, "model": None, "api_key": None})
        assert put_resp.status_code == expected, (role, put_resp.text)
        if expected == 403:
            body_keys = set(get_resp.json().keys()) | set(put_resp.json().keys())
            assert not (body_keys & FORBIDDEN_KEYS)


def test_ai_settings_test_endpoint_requires_admin_only(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role in ALL_ROLES:
        client = router_test_client(db, ai_settings_router, role=role)
        resp = client.post("/api/ai-settings/test")
        expected = 400 if role == "admin" else 403  # admin: 400, da noch kein Anbieter konfiguriert
        assert resp.status_code == expected, (role, resp.text)


def test_ai_settings_response_never_returns_the_plaintext_api_key(threaded_db_session, router_test_client):
    db = threaded_db_session
    admin_client = router_test_client(db, ai_settings_router, role="admin")
    put_resp = admin_client.put("/api/ai-settings", json={
        "enabled": True, "provider": "anthropic", "api_base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-5", "api_key": "sk-super-geheim",
    })
    assert put_resp.status_code == 200, put_resp.text
    body = put_resp.json()
    assert "api_key" not in body
    assert body["has_api_key"] is True
    assert "sk-super-geheim" not in str(body)


def test_ai_settings_put_rejects_mock_provider_via_router(threaded_db_session, router_test_client):
    db = threaded_db_session
    admin_client = router_test_client(db, ai_settings_router, role="admin")
    resp = admin_client.put("/api/ai-settings", json={"enabled": True, "provider": "mock", "api_base_url": None, "model": None, "api_key": None})
    assert resp.status_code == 422, resp.text
