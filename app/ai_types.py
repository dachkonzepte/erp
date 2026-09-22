"""Datentypen und Fehlerklassen für das KI-Fundament (seit 1.6.2) -- noch keine konkrete
KI-Funktion, nur die Schnittstelle, an die sich künftige Funktionen (Belegauswertung,
Angebotstexte, Berichtszusammenfassung) anhängen sollen. Siehe app/ai_service.py::call_ai()
für die zentrale Stelle, die diese Typen verwendet, und CLAUDE.md "KI-Fundament" für die volle
Herleitung.

AIRequest/AIResponse sind bewusst reine Datenklassen ohne jeden Bezug zu einem bestimmten
Anbieter -- ein Adapter (app/ai_adapters.py) übersetzt sie in das jeweilige Anbieterformat und
zurück, der Rest des ERP kennt nur diese beiden Typen, nie den Anbieter selbst."""

from dataclasses import dataclass, field


@dataclass
class AIAttachment:
    """Ein Dokument/Bild zur Anfrage -- vorgesehen für eine künftige Belegauswertung, in
    dieser Runde von keiner Fachfunktion befüllt."""

    mime_type: str
    data: bytes
    filename: str | None = None


@dataclass
class AIRequest:
    caller: str  # z.B. "belegauswertung" -- fließt ins Protokoll (AICallLog.caller), NIE der Inhalt
    prompt: str
    attachments: list[AIAttachment] = field(default_factory=list)
    system: str | None = None


@dataclass
class AIResponse:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_estimate: float | None = None


class AIProviderError(Exception):
    """Basisklasse für jeden Fehler beim KI-Aufruf -- aufrufender Code fängt diese Klasse (oder
    eine der beiden folgenden Unterklassen) ab, nie eine anbieterspezifische Ausnahme."""


class AIProviderNotConfigured(AIProviderError):
    """Der Normalzustand: kein Anbieter gewählt, der Gesamtschalter ist aus, oder für den
    gewählten Anbieter existiert (noch) kein Adapter. Aufrufender Code bietet die KI-Funktion
    in diesem Fall gar nicht erst an (siehe app/ai_settings.py::is_ai_available())."""


class AIProviderUnavailable(AIProviderError):
    """Der Anbieter ist konfiguriert, der Aufruf ist aber gescheitert -- unerreichbar, falscher
    Schlüssel, Kontingent erschöpft, Zeitüberschreitung. Aufrufender Code zeigt eine klare
    Meldung und arbeitet ohne KI weiter (z. B. Belegauswertung: dann tippt man von Hand)."""


AI_PROVIDERS = ("anthropic", "openai", "azure_openai", "google")
"""Feste Code-Werte wie RecurringCost.billing_interval -- die Auswahl bestimmt, welcher Adapter
dispatcht wird (Rechenregel), keine freie Anzeigeliste, deshalb keine Optionsgruppe. In dieser
Runde hat KEINER der vier einen echten Adapter (siehe app/ai_adapters.py) -- call_ai() liefert
dafür AIProviderNotConfigured, unabhängig vom gewählten Wert; ein künftiger, echter Adapter
ist nur ein neuer Eintrag in app/ai_adapters.py::_ADAPTERS, diese Liste hier bleibt unverändert.

'mock' ist bewusst NICHT enthalten -- er ist ausschließlich für die Testsuite gedacht (siehe
app/ai_adapters.py::MockAIAdapter) und darf nie über die Einstellungen wählbar sein.
app/ai_settings.py::update_ai_settings() validiert ausschließlich gegen dieses Tupel."""
