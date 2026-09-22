"""Anbieter-Adapter für das KI-Fundament (seit 1.6.2) -- EIN Protokoll, das jeder künftige
Anbieter (Anthropic, OpenAI, Azure OpenAI, Google) erfüllen muss, plus ein Mock-Adapter für
die Testsuite. Siehe app/ai_service.py::call_ai() (der einzige Aufrufer von _ADAPTERS) und
CLAUDE.md "KI-Fundament" für die volle Herleitung.

Bewusst KEIN echter Anbieter-Adapter in dieser Runde (Betreibervorgabe: "kein Anbieter
festgelegt") -- _ADAPTERS enthält deshalb ausschließlich den Mock. Ein künftiger, echter
Adapter ist eine neue, kleine Klasse hier (oder in einer eigenen Datei, falls mehrere
entstehen) plus ein neuer Eintrag in _ADAPTERS, unter dem jeweiligen Wert aus
app/ai_types.py::AI_PROVIDERS -- app/ai_service.py::call_ai() selbst muss dafür nicht
angefasst werden.

Jeder Adapter bekommt sein eigenes Zeitlimit als Parameter (timeout) und MUSS es an seinen
eigenen HTTP-Client durchreichen (Muster app/email_sending.py: urlopen(..., timeout=...)) --
call_ai() setzt zusätzlich einen eigenen, vom Adapter unabhängigen Sicherheitsnetz-Timeout,
aber ein Adapter, der sein eigenes Zeitlimit ignoriert, hinterlässt trotzdem einen blockierten
Hintergrund-Thread für die Dauer des tatsächlichen Netzwerkaufrufs -- das eigene Timeout ist
deshalb kein optionaler Programmierstil, sondern Pflicht."""

from typing import Protocol

from .ai_types import AIRequest, AIResponse
from .models import AISettings


class AIProviderAdapter(Protocol):
    def complete(self, request: AIRequest, *, timeout: float) -> AIResponse: ...


class MockAIAdapter:
    """Feste Testantwort ohne jeden Netzwerkzugriff -- macht die Testsuite unabhängig von
    externen Diensten (Betreibervorgabe: "eine Testsuite darf nie einen echten KI-Aufruf
    machen"). NIE über die Einstellungen wählbar (siehe AI_PROVIDERS in app/ai_types.py) --
    nur erreichbar, wenn ein Test AISettings.provider direkt (unter Umgehung von
    update_ai_settings()) auf "mock" setzt, oder über call_ai()s adapter_override-Parameter.

    raise_error erlaubt Tests, gezielt einen Fehlerpfad zu erzwingen (z. B. eine
    Zeitüberschreitung oder einen Anbieterfehler), ohne call_ai()s Dispatch-/Timeout-/
    Protokoll-Logik selbst zu verändern -- über einen monkeypatch der Fabrik in _ADAPTERS oder
    direkt über adapter_override, nicht über einen Parameter an complete() selbst."""

    def __init__(self, settings: AISettings, *, raise_error: Exception | None = None):
        self._raise_error = raise_error

    def complete(self, request: AIRequest, *, timeout: float) -> AIResponse:
        if self._raise_error is not None:
            raise self._raise_error
        return AIResponse(
            text=f"[Mock-Antwort] {request.prompt[:120]}",
            input_tokens=max(1, len(request.prompt.split())),
            output_tokens=8,
            cost_estimate=None,
        )


_ADAPTERS = {
    "mock": MockAIAdapter,
}
