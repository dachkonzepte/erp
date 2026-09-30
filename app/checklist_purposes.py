"""Zwecke von Checklisten-Vorlagen (seit 1.8.16, Stufe 2, Runde 2a-2, Modul "checklisten").

Herleitung: docs/archiv/modul-checklisten.md, "Umsetzung 1.8.16".

Ein Zweck legt fest,
- in welchen Kontexten eine Vorlage dieses Zwecks ausgefüllt werden darf (die drei fachlichen
  Zwecke nur am Auftrag),
- welche Systemfelder sie tragen muss -- fester Schlüssel und Typ, dazu fest: Pflicht, "entfällt",
  Mehrfach, Mindestanzahl und die Optionen. Beschriftung, Hilfetext, Abschnitt und Reihenfolge
  bleiben frei; löschen lässt sich ein Systemfeld nicht. Folgelogik liest Antworten nach
  Schlüssel, nie nach Beschriftung,
- welche Folgen der Abschluss auslöst (app/checklist_follow_ups.py).

Der Zweck steht an der Vorlage (ChecklistTemplate.purpose, änderbar bis zur ersten
Veröffentlichung) und wird beim Veröffentlichen an der Fassung eingefroren
(ChecklistTemplateVersion.purpose). Eine Checkliste nutzt immer den Zweck ihrer Fassung.

Die Registry steht bewusst im Code, nicht in der Datenbank: Systemfelder und Folgen sind
Programmlogik. Abnahme, Behinderungs- und Bedenkenanzeige tragen noch keine Systemfelder und
Folgen (kommen in den Runden 2b/2c); Tests tragen einen eigenen Zweck per monkeypatch in
PURPOSES ein.

Bewusst ohne Import aus app.checklist_templates (das importiert von hier)."""

from dataclasses import dataclass
from typing import Callable

DEFAULT_PURPOSE = "allgemein"
ALL_CONTEXTS = ("auftrag", "objekt", "betriebsmittel", "betrieb")


@dataclass(frozen=True)
class SystemField:
    """Vorgabe eines Systemfelds. Die hier stehenden Eigenschaften außer label sind am Feld
    nicht änderbar (app/checklist_templates.py::SYSTEM_LOCKED_ATTRIBUTES); label ist nur der
    Vorschlag beim Anlegen."""
    key: str
    field_type: str
    label: str
    required: bool = False
    allow_na: bool = False
    multiple: bool = False
    min_count: int | None = None
    options: tuple[tuple[str, str], ...] = ()  # (option_key, Beschriftung)


@dataclass(frozen=True)
class FollowUp:
    """Folge des Abschlusses. handler(db, checklist) legt an, was die Folge ausmacht, und
    liefert das Ziel als (target_type, target_id) oder None (nichts anzulegen). Er darf selbst
    committen (wie app/tasks.py::create_task()). module: ohne dieses Modul bleibt die Folge
    "modul_aus" und ist nachholbar (wie Betreiberentscheidung C bei den Regeln)."""
    key: str
    label: str
    handler: Callable
    module: str | None = None


@dataclass(frozen=True)
class ChecklistPurpose:
    key: str
    label: str
    contexts: tuple[str, ...]
    system_fields: tuple[SystemField, ...] = ()
    follow_ups: tuple[FollowUp, ...] = ()


PURPOSES: dict[str, ChecklistPurpose] = {p.key: p for p in (
    ChecklistPurpose(DEFAULT_PURPOSE, "Allgemein", ALL_CONTEXTS),
    ChecklistPurpose("abnahme", "Abnahme", ("auftrag",)),
    ChecklistPurpose("behinderungsanzeige", "Behinderungsanzeige", ("auftrag",)),
    ChecklistPurpose("bedenkenanzeige", "Bedenkenanzeige", ("auftrag",)),
)}


def get_purpose(key: str | None) -> ChecklistPurpose | None:
    """None bei unbekanntem Schlüssel -- wer darauf reagiert, entscheidet selbst (Anlegen einer
    Checkliste lehnt ab, Folgen laufen keine)."""
    return PURPOSES.get(key or DEFAULT_PURPOSE)


def purpose_label(key: str | None) -> str:
    purpose = get_purpose(key)
    return purpose.label if purpose else (key or DEFAULT_PURPOSE)


def purpose_to_dict(purpose: ChecklistPurpose) -> dict:
    """Für den Vorlagen-Editor (Büro) -- ohne Folgen, die sind Programmlogik."""
    return {
        "key": purpose.key, "label": purpose.label, "contexts": list(purpose.contexts),
        "system_fields": [{"key": s.key, "field_type": s.field_type, "label": s.label} for s in purpose.system_fields],
    }


def list_purposes() -> list[dict]:
    return [purpose_to_dict(p) for p in PURPOSES.values()]
