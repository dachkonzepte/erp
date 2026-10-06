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
Seit 1.8.41 lassen sich Behinderungs- und Bedenkenanzeige "als gegenstandslos abschließen"
(ChecklistPurpose.voidable). Seit 1.8.43 (Runde 2b-4) trägt die Bedenkenanzeige Systemfelder nach dem Muster der
Behinderungsanzeige -- Meldung, Anzeige (Büro), Entscheidung des Auftraggebers (Büro) -- und drei Folgen: nach der
Meldung "versenden", nach dem Versand (FollowUp.after_letter) "Antwort prüfen", nach der Unterschrift der
Entscheidung diese Aufgabe erledigen. Herleitung in docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung
1.8.43". Seit 1.8.45 ist "Antwort als Beleg" ein Feld vom Typ "beleg" (PDF oder Foto).

Seit 1.8.61 (Stufe 2c-2d, Punkt 2) das Abnahmeprotokoll: Zweck "abnahme" mit Systemfeldern in drei Abschnitten (Befund,
Erklärungen des Auftraggebers, Schluss), Herleitung in docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.61".
Dazu kamen:
- SystemField.signer_mode: der Unterzeichner eines Unterschrifts-Systemfelds, fest wie der Typ (None = frei wählbar wie
  bisher bei Behinderungs- und Bedenkenanzeige).
- ChecklistPurpose.office_only: Checklisten dieses Zwecks nur fürs Büro -- der Monteur sieht sie nicht, startet sie nicht,
  auch nicht in /mobil (Router 403).
- ChecklistPurpose.signature_checks: (Schlüssel eines Unterschriftsfelds, Prüfung) -- die Prüfung läuft vor dem Speichern
  der Unterschrift unter der Zeilensperre der Checkliste und lehnt mit ValueError ab (app/acceptance_protocol.py).
Seit 1.8.63 die Folge "Abnahme am Auftrag anlegen" nach der Unterschrift des Auftraggebers -- FollowUp.per_signature: je
Unterschrift, nicht je Checkliste.

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
    signer_mode: str | None = None  # seit 1.8.61, siehe Moduldocstring


@dataclass(frozen=True)
class FollowUp:
    """Folge des Abschlusses -- oder seit 1.8.38 der Unterschrift in einem bestimmten
    Systemfeld (after_signature = dessen Schlüssel). handler(db, checklist) legt an, was die
    Folge ausmacht, und liefert das Ziel als (target_type, target_id) oder None (nichts
    anzulegen). Er darf selbst committen (wie app/tasks.py::create_task()). module: ohne dieses
    Modul bleibt die Folge "modul_aus" und ist nachholbar (wie Betreiberentscheidung C bei den
    Regeln). after_letter (seit 1.8.43): die Folge läuft, sobald der Brief dieser Art beim Auftraggeber
    angekommen ist (app/notice_letters.py::letter_was_sent()) -- nach der Bedenkenanzeige "Antwort prüfen". per_signature
    (seit 1.8.63, nur mit after_signature): die Folge gilt je auslösender Unterschrift, nicht je Checkliste -- wird die
    Unterschrift verworfen und neu geleistet, ist sie für die neue wieder fällig; der Handler bekommt dann
    handler(db, checklist, signature_id=…, actor=(Konto-ID, Name) oder None)."""
    key: str
    label: str
    handler: Callable
    module: str | None = None
    after_signature: str | None = None
    after_letter: str | None = None
    per_signature: bool = False


@dataclass(frozen=True)
class ChecklistPurpose:
    """voidable (seit 1.8.41): das Büro kann eine Checkliste dieses Zwecks mit Begründung "als gegenstandslos
    abschließen" (app/checklists.py::void_checklist()) -- Behinderungs- und Bedenkenanzeige. office_only und
    signature_checks seit 1.8.61, siehe Moduldocstring."""
    key: str
    label: str
    contexts: tuple[str, ...]
    system_fields: tuple[SystemField, ...] = ()
    follow_ups: tuple[FollowUp, ...] = ()
    voidable: bool = False
    office_only: bool = False
    signature_checks: tuple[tuple[str, Callable], ...] = ()


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


# --- Bedenkenanzeige (seit 1.8.43) -------------------------------------------------------------

CONCERN_PURPOSE = "bedenkenanzeige"
_K = CONCERN_PURPOSE + "."
CONCERN_REPORT_SIGNATURE = _K + "unterschrift_meldung"
CONCERN_DECISION_SIGNATURE = _K + "unterschrift_entscheidung"
CONCERN_DEADLINE = _K + "entscheidung_bis"


def _concern_send_task(db, checklist):
    from .concern_notices import create_send_task  # erst beim Aufruf, siehe Moduldocstring
    return create_send_task(db, checklist)


def _concern_answer_task(db, checklist):
    from .concern_notices import create_answer_task
    return create_answer_task(db, checklist)


def _concern_answer_done(db, checklist):
    from .concern_notices import complete_answer_tasks
    return complete_answer_tasks(db, checklist)


CONCERN_SYSTEM_FIELDS = (
    # Meldung -- wer die Bedenken hat (meist der Monteur).
    SystemField(_K + "bekannt_seit", "datum_uhrzeit", "Bekannt seit", required=True, section="Meldung"),
    SystemField(_K + "beschreibung", "text", "Beschreibung", required=True, section="Meldung", multiline=True),
    SystemField(_K + "fotos", "foto", "Fotos", section="Meldung"),
    SystemField(CONCERN_REPORT_SIGNATURE, "unterschrift", "Unterschrift des Meldenden", required=True,
                section="Meldung", signer_label="Meldender"),
    # Anzeige -- das Büro.
    SystemField(_K + "bedenken_gegen", "auswahl", "Bedenken gegen", required=True, multiple=True, section="Anzeige",
                office_only=True, options=(
                    ("art_der_ausfuehrung", "vorgesehene Art der Ausführung"),
                    ("stoffe_bauteile", "vom Auftraggeber gelieferte Stoffe oder Bauteile"),
                    ("leistungen_anderer", "Leistungen anderer Unternehmer"),
                )),
    SystemField(_K + "begruendung", "text", "Begründung", required=True, section="Anzeige", office_only=True,
                multiline=True),
    SystemField(_K + "moegliche_folgen", "text", "Mögliche Folgen", required=True, section="Anzeige",
                office_only=True, multiline=True),
    SystemField(_K + "vorschlag_abhilfe", "text", "Vorschlag zur Abhilfe", section="Anzeige", office_only=True,
                multiline=True),
    SystemField(CONCERN_DEADLINE, "datum", "Entscheidung erbeten bis", required=True, section="Anzeige",
                office_only=True),
    SystemField(_K + "unterschrift_buero", "unterschrift", "Unterschrift Büro", required=True, section="Anzeige",
                office_only=True, signer_label="Büro"),
    # Entscheidung des Auftraggebers -- das Büro.
    SystemField(_K + "eingegangen_am", "datum", "Eingegangen am", section="Entscheidung", office_only=True),
    SystemField(_K + "entscheidung", "auswahl", "Entscheidung", required=True, section="Entscheidung",
                office_only=True, options=(
                    ("bedenken_gefolgt", "Bedenken gefolgt"),
                    ("trotz_bedenken", "Ausführung trotz Bedenken angeordnet"),
                    ("keine_antwort", "keine Antwort"),
                    ("sonstiges", "Sonstiges"),
                )),
    # Seit 1.8.45 Typ "beleg" (PDF oder Foto) statt "foto" -- die Antwort kommt oft als PDF.
    SystemField(_K + "antwort_beleg", "beleg", "Antwort als Beleg", section="Entscheidung", office_only=True),
    SystemField(_K + "notiz", "text", "Notiz", section="Entscheidung", office_only=True, multiline=True),
    SystemField(CONCERN_DECISION_SIGNATURE, "unterschrift", "Unterschrift", required=True, section="Entscheidung",
                office_only=True, signer_label="Büro"),
)


# --- Abnahmeprotokoll (seit 1.8.61) -------------------------------------------------------------

ACCEPTANCE_PURPOSE = "abnahme"
_A = ACCEPTANCE_PURPOSE + "."
ACCEPTANCE_SCOPE = _A + "umfang"
ACCEPTANCE_SCOPE_TEXT = _A + "umfang_beschreibung"
ACCEPTANCE_ROOF_AREAS = _A + "dachflaechen"
ACCEPTANCE_DEFECTS_FIELD = _A + "maengel"
ACCEPTANCE_OBJECTIONS = _A + "einwendungen"
ACCEPTANCE_RESULT = _A + "ergebnis"
ACCEPTANCE_DEFECTS = _A + "vorbehalt_maengel"
ACCEPTANCE_PENALTY = _A + "vorbehalt_vertragsstrafe"
ACCEPTANCE_CUSTOMER_SIGNATURE = _A + "unterschrift_auftraggeber"
ACCEPTANCE_CONTRACTOR_SIGNATURE = _A + "unterschrift_auftragnehmer"


ACCEPTANCE_FOLLOW_UP = _A + "abnahme_anlegen"


def _acceptance_customer_check(db, checklist, signer):
    from .acceptance_protocol import check_customer_signature  # erst beim Aufruf, siehe Moduldocstring
    return check_customer_signature(db, checklist, signer)


def _acceptance_from_protocol(db, checklist, *, signature_id, actor):
    from .acceptance_protocol import acceptance_from_protocol  # seit 1.8.63
    user_id, user_name = actor or (None, None)
    acceptance = acceptance_from_protocol(db, checklist.id, signature_id=signature_id, user_id=user_id,
                                          user_name=user_name)
    return "abnahme", acceptance.id


# Ohne Vorgabe der Antworten (keine Vorauswahl, wie der Abnahme-Dialog seit 1.8.46). Bedingte Pflicht (Beschreibung bei der
# Teilabnahme, Vorbehalte bei "abgenommen") prüft die Unterschrift des Auftraggebers, nicht das Pflicht-Kennzeichen.
ACCEPTANCE_SYSTEM_FIELDS = (
    # Befund
    SystemField(_A + "teilnehmer", "text", "Teilnehmer", required=True, section="Befund", multiline=True),
    SystemField(ACCEPTANCE_SCOPE, "auswahl", "Umfang", required=True, section="Befund", options=(
        ("gesamt", "Gesamtabnahme"),
        ("teil", "Teilabnahme"),
    )),
    SystemField(ACCEPTANCE_SCOPE_TEXT, "text", "Abgenommener Teil", section="Befund", multiline=True),
    SystemField(ACCEPTANCE_ROOF_AREAS, "dachflaechen", "Dachflächen", section="Befund"),
    SystemField(ACCEPTANCE_DEFECTS_FIELD, "maengel", "Mängel", section="Befund"),
    SystemField(ACCEPTANCE_OBJECTIONS, "text", "Einwendungen des Auftragnehmers", section="Befund", multiline=True),
    # Erklärungen des Auftraggebers
    SystemField(ACCEPTANCE_RESULT, "auswahl", "Ergebnis", required=True, section="Erklärungen des Auftraggebers",
                options=(("abgenommen", "Abnahme erklärt"), ("verweigert", "Abnahme verweigert"))),
    SystemField(ACCEPTANCE_DEFECTS, "ja_nein", "Vorbehalt wegen bekannter Mängel", section="Erklärungen des Auftraggebers"),
    SystemField(ACCEPTANCE_PENALTY, "ja_nein", "Vorbehalt der Vertragsstrafe", section="Erklärungen des Auftraggebers"),
    SystemField(ACCEPTANCE_CUSTOMER_SIGNATURE, "unterschrift", "Unterschrift Auftraggeber", required=True,
                section="Erklärungen des Auftraggebers", signer_label="Auftraggeber",
                signer_mode="ag_oder_beteiligter"),
    # Schluss
    SystemField(ACCEPTANCE_CONTRACTOR_SIGNATURE, "unterschrift", "Unterschrift Auftragnehmer", required=True,
                section="Schluss", signer_label="Auftragnehmer", signer_mode="konto"),
)


PURPOSES: dict[str, ChecklistPurpose] = {p.key: p for p in (
    ChecklistPurpose(DEFAULT_PURPOSE, "Allgemein", ALL_CONTEXTS),
    ChecklistPurpose(ACCEPTANCE_PURPOSE, "Abnahme", ("auftrag",), ACCEPTANCE_SYSTEM_FIELDS, (
        # seit 1.8.63: die Abnahme am Auftrag -- je Unterschrift des Auftraggebers höchstens eine (app/acceptance_protocol.py)
        FollowUp(ACCEPTANCE_FOLLOW_UP, "Abnahme am Auftrag anlegen", _acceptance_from_protocol,
                 after_signature=ACCEPTANCE_CUSTOMER_SIGNATURE, per_signature=True),
    ), office_only=True, signature_checks=((ACCEPTANCE_CUSTOMER_SIGNATURE, _acceptance_customer_check),)),
    ChecklistPurpose(OBSTRUCTION_PURPOSE, "Behinderungsanzeige", ("auftrag",), OBSTRUCTION_SYSTEM_FIELDS, (
        FollowUp(_B + "versenden", "Aufgabe „Behinderungsanzeige versenden“", _obstruction_send_task,
                 module="aufgabenmanagement", after_signature=OBSTRUCTION_REPORT_SIGNATURE),
    ), voidable=True),
    ChecklistPurpose(CONCERN_PURPOSE, "Bedenkenanzeige", ("auftrag",), CONCERN_SYSTEM_FIELDS, (
        FollowUp(_K + "versenden", "Aufgabe „Bedenkenanzeige versenden“", _concern_send_task,
                 module="aufgabenmanagement", after_signature=CONCERN_REPORT_SIGNATURE),
        FollowUp(_K + "antwort_pruefen", "Aufgabe „Antwort des Auftraggebers prüfen“", _concern_answer_task,
                 module="aufgabenmanagement", after_letter=CONCERN_PURPOSE),
        FollowUp(_K + "entscheidung", "Aufgabe „Antwort des Auftraggebers prüfen“ erledigen", _concern_answer_done,
                 module="aufgabenmanagement", after_signature=CONCERN_DECISION_SIGNATURE),
    ), voidable=True),
)}


def get_purpose(key: str | None) -> ChecklistPurpose | None:
    """None bei unbekanntem Schlüssel -- wer darauf reagiert, entscheidet selbst (Anlegen einer
    Checkliste lehnt ab, Folgen laufen keine)."""
    return PURPOSES.get(key or DEFAULT_PURPOSE)


def purpose_office_only(key: str | None) -> bool:
    """Checklisten dieses Zwecks nur fürs Büro? (seit 1.8.61, Abnahmeprotokoll)"""
    purpose = get_purpose(key)
    return bool(purpose and purpose.office_only)


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
        "office_only": purpose.office_only,  # seit 1.8.61
        "system_fields": [{"key": s.key, "field_type": s.field_type, "label": s.label, "section": s.section,
                           "office_only": s.office_only, "signer_mode": s.signer_mode} for s in purpose.system_fields],
    }


def list_purposes() -> list[dict]:
    return [purpose_to_dict(p) for p in PURPOSES.values()]
