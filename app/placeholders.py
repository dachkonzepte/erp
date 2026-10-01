"""Platzhalter in Textvorlagen ersetzen (seit 1.8.32) -- gemeinsam für Mahnungen, E-Mail-Vorlagen und
Vertragsvorlagen.

Hervorgegangen aus app/reminders.py::_apply_placeholders(): ein Platzhalter ist ein Schlüssel wie
"{kundenname}", der Aufrufer liefert ein Wörterbuch Platzhalter -> Wert. Ein unbekannter Platzhalter
bleibt stehen, kein Fehler (wie bisher bei Mahnungen).

Ein Unterschied zur alten Schleife (je Platzhalter ein str.replace() über den ganzen Text): ersetzt
wird in EINEM Durchgang. Vorher wurde ein eingesetzter Wert, der selbst wie ein Platzhalter aussieht,
von einem späteren Schlüssel noch einmal ersetzt -- bei Mahnbeträgen und Daten kam das nie vor, bei
Freitext im Vertrag (Besonderheiten, Kundenname) schon.
"""

import re
from collections.abc import Iterable

# Wie ein Platzhalter aussieht -- nur für die Suche nach unbekannten Platzhaltern in einer Vorlage.
# Ersetzt wird genau, was der Aufrufer übergibt (auch Schlüssel, die diesem Muster nicht folgen).
PLACEHOLDER_PATTERN = re.compile(r"\{[a-z0-9_]+\}")


def apply_placeholders(text: str, replacements: dict[str, str]) -> str:
    if not text or not replacements:
        return text or ""
    keys = sorted(replacements, key=len, reverse=True)  # längster zuerst, falls einer Präfix eines anderen ist
    pattern = re.compile("|".join(re.escape(k) for k in keys))
    return pattern.sub(lambda m: str(replacements[m.group(0)] if replacements[m.group(0)] is not None else ""), text)


def placeholders_in(text: str | None) -> list[str]:
    """Alle Platzhalter im Text, in der Reihenfolge ihres ersten Auftretens, ohne Doppelte."""
    seen: list[str] = []
    for match in PLACEHOLDER_PATTERN.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen


def unknown_placeholders(text: str | None, known: Iterable[str]) -> list[str]:
    """Platzhalter im Text, die nicht in known stehen -- z. B. ein Tippfehler in einer Vorlage, der
    sonst unaufgelöst im Dokument landet."""
    known_set = set(known)
    return [p for p in placeholders_in(text) if p not in known_set]
