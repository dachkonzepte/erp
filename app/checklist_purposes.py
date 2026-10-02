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
Programmlogik. Tests tragen einen eigenen Zweck per monkeypatch in PURPOSES ein.

Seit 1.8.38 (Stufe 2b, Runde 2b-3 Teil 1) trägt die Behinderungsanzeige Systemfelder in drei
Abschnitten (Meldung, Anzeige, Wegfall) und ihre erste Folge; Herleitung in
docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.38". Dazu kamen:
- SystemField.section: Abschnitt. Beim Anlegen der Vorschlag für den Abschnittsnamen; beim
  Veröffentlichen geprüft, dass die Abschnitte in der vorgegebenen Reihenfolge stehen und jede
  Unterschrift am Ende ihres Abschnitts (sonst versiegelte die Unterschrift der Meldung nicht die
  Meldung, und die Folge danach liefe auf einem halben Stand).
- SystemField.office_only: nur das Büro füllt das Feld aus bzw. unterschreibt (der Router weist
  einen Monteur mit 403 ab).
- SystemField.option_hints: ein Hinweis, der beim Wählen einer Option erscheint.
- FollowUp.after_signature: die Folge läuft nach der Unterschrift in diesem Systemfeld statt
  nach dem Abschluss.
Abnahme und Bedenkenanzeige tragen noch keine Systemfelder und Folgen.

Bewusst ohne Import aus app.checklist_templates (das importiert von hier); die Handler der Folgen
importieren ihre Module erst beim Aufruf."""

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
    # Seit 1.8.38, siehe Moduldocstring. section, multiline und signer_label sind wie label nur
    # Vorschläge beim Anlegen (Abschnittsname, mehrzeilig, Rollenbeschriftung der Unterschrift);
    # die Reihenfolge der Abschnitte prüft das Veröffentlichen.
    section: str | None = None
    office_only: bool = False
    option_hints: tuple[tuple[str, str], ...] = ()  # (option_key, Hinweis beim Wählen)
    multiline: bool = False
    signer_label: str | None = None


@dataclass(frozen=True)
class FollowUp:
    """Folge des Abschlusses -- oder seit 1.8.38 der Unterschrift in einem bestimmten
    Systemfeld (after_signature = dessen Schlüssel). handler(db, checklist) legt an, was die
    Folge ausmacht, und liefert das Ziel als (target_type, target_id) oder None (nichts
    anzulegen). Er darf selbst committen (wie app/tasks.py::create_task()). module: ohne dieses
    Modul bleibt die Folge "modul_aus" und ist nachholbar (wie Betreiberentscheidung C bei den
    Regeln)."""
    key: str
    label: str
    handler: Callable
    module: str | None = None
    after_signature: str | None = None


@dataclass(frozen=True)
class ChecklistPurpose:
    key: str
    label: str
    contexts: tuple[str, ...]
    system_fields: tuple[SystemField, ...] = ()
    follow_ups: tuple[FollowUp, ...] = ()


# --- Behinderungsanzeige (seit 1.8.38) -------------------------------------------------------

OBSTRUCTION_PURPOSE = "behinderungsanzeige"
_B = OBSTRUCTION_PURPOSE + "."
OBSTRUCTION_REPORT_SIGNATURE = _B + "unterschrift_meldung"
WEATHER_HINT = "Übliche Witterung ist nach § 6 Abs. 2 VOB/B keine Behinderung."


def _obstruction_send_task(db, checklist):
    from .obstruction_notices import create_send_task  # erst beim Aufruf, siehe Moduldocstring
    return create_send_task(db, checklist)


OBSTRUCTION_SYSTEM_FIELDS = (
    # Meldung -- erfasst und unterschreibt, wer die Behinderung bemerkt (in der Regel der Monteur).
    SystemField(_B + "bekannt_seit", "datum_uhrzeit", "Bekannt seit", required=True, section="Meldung"),
    SystemField(_B + "beschreibung", "text", "Beschreibung", required=True, section="Meldung", multiline=True),
    SystemField(_B + "fotos", "foto", "Fotos", section="Meldung"),
    SystemField(OBSTRUCTION_REPORT_SIGNATURE, "unterschrift", "Unterschrift des Meldenden", required=True,
                section="Meldung", signer_label="Meldender"),
    # Anzeige -- das Büro.
    SystemField(_B + "ursache", "auswahl", "Ursache", required=True, section="Anzeige", office_only=True, options=(
        ("vorleistung", "fehlende Vorleistung eines anderen Gewerks"),
        ("plaene_freigaben", "fehlende Pläne oder Freigaben"),
        ("zugang_geruest", "Zugang oder Gerüst"),
        ("material_ag", "vom Auftraggeber zu lieferndes Material"),
        ("witterung", "außergewöhnliche Witterung"),
        ("sonstiges", "Sonstiges"),
    ), option_hints=(("witterung", WEATHER_HINT),)),
    SystemField(_B + "ursache_beschreibung", "text", "Beschreibung der Ursache", required=True, section="Anzeige",
                office_only=True, multiline=True),
    SystemField(_B + "betroffene_leistungen", "text", "Betroffene Leistungen", required=True, section="Anzeige",
                office_only=True, multiline=True),
    SystemField(_B + "beginn", "datum", "Beginn der Behinderung", required=True, section="Anzeige", office_only=True),
    SystemField(_B + "dauer", "text", "Voraussichtliche Dauer", section="Anzeige", office_only=True),
    SystemField(_B + "unterschrift_buero", "unterschrift", "Unterschrift Büro", required=True, section="Anzeige",
                office_only=True, signer_label="Büro"),
    # Wegfall -- Monteur oder Büro.
    SystemField(_B + "beendet_am", "datum", "Behinderung beendet am", required=True, section="Wegfall"),
    SystemField(_B + "wieder_aufgenommen_am", "datum", "Arbeit wieder aufgenommen am", required=True, section="Wegfall"),
    SystemField(_B + "unterschrift_wegfall", "unterschrift", "Unterschrift", required=True, section="Wegfall",
                signer_label="Monteur/Büro"),
)


PURPOSES: dict[str, ChecklistPurpose] = {p.key: p for p in (
    ChecklistPurpose(DEFAULT_PURPOSE, "Allgemein", ALL_CONTEXTS),
    ChecklistPurpose("abnahme", "Abnahme", ("auftrag",)),
    ChecklistPurpose(OBSTRUCTION_PURPOSE, "Behinderungsanzeige", ("auftrag",), OBSTRUCTION_SYSTEM_FIELDS, (
        FollowUp(_B + "versenden", "Aufgabe „Behinderungsanzeige versenden“", _obstruction_send_task,
                 module="aufgabenmanagement", after_signature=OBSTRUCTION_REPORT_SIGNATURE),
    )),
    ChecklistPurpose("bedenkenanzeige", "Bedenkenanzeige", ("auftrag",)),
)}


def get_purpose(key: str | None) -> ChecklistPurpose | None:
    """None bei unbekanntem Schlüssel -- wer darauf reagiert, entscheidet selbst (Anlegen einer
    Checkliste lehnt ab, Folgen laufen keine)."""
    return PURPOSES.get(key or DEFAULT_PURPOSE)


def purpose_label(key: str | None) -> str:
    purpose = get_purpose(key)
    return purpose.label if purpose else (key or DEFAULT_PURPOSE)


def system_field_spec(purpose_key: str | None, field_key: str) -> SystemField | None:
    """Vorgabe des Systemfelds mit diesem Schlüssel im Zweck -- None, wenn der Zweck es nicht
    kennt. Wer fragt, prüft selbst, ob das Feld als Systemfeld markiert ist (is_system)."""
    purpose = get_purpose(purpose_key)
    return next((s for s in purpose.system_fields if s.key == field_key), None) if purpose else None


def section_order_problem(purpose: ChecklistPurpose, system_keys_in_order: list[str]) -> str | None:
    """Stehen die Systemfelder in der Reihenfolge ihrer Abschnitte, jede Unterschrift am Ende ihres
    Abschnitts? (seit 1.8.38) Frei bleiben die Reihenfolge innerhalb eines Abschnitts und die Lage
    gewöhnlicher Felder. None = in Ordnung oder der Zweck kennt keine Abschnitte."""
    sections = list(dict.fromkeys(s.section for s in purpose.system_fields if s.section))
    if not sections:
        return None
    rank = {s.key: (sections.index(s.section), s.field_type == "unterschrift")
            for s in purpose.system_fields if s.section}
    sequence = [rank[key] for key in system_keys_in_order if key in rank]
    if sequence == sorted(sequence):
        return None
    return (f"Die Systemfelder stehen nicht in der vorgegebenen Reihenfolge der Abschnitte ({', '.join(sections)}; "
            f"die Unterschrift jeweils am Ende ihres Abschnitts).")


def purpose_to_dict(purpose: ChecklistPurpose) -> dict:
    """Für den Vorlagen-Editor (Büro) -- ohne Folgen, die sind Programmlogik."""
    return {
        "key": purpose.key, "label": purpose.label, "contexts": list(purpose.contexts),
        "system_fields": [{"key": s.key, "field_type": s.field_type, "label": s.label, "section": s.section,
                           "office_only": s.office_only} for s in purpose.system_fields],
    }


def list_purposes() -> list[dict]:
    return [purpose_to_dict(p) for p in PURPOSES.values()]
