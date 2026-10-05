"""Abnahmeprotokoll als Checkliste (seit 1.8.61, Stufe 2c-2d, Punkt 2) -- Zweck "abnahme".

Herleitung: docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.61". Die Systemfelder stehen in
app/checklist_purposes.py (ACCEPTANCE_SYSTEM_FIELDS); hier die Prüfung bei der Unterschrift des Auftraggebers: was das
Protokoll erklärt, muss in sich stimmig sein und eine Abnahme ergeben, die app/acceptances.py::create_acceptance() annimmt
(1.8.62 legt sie aus dem Protokoll an). Abgelehnt (ValueError, 400) werden

- die drei Widersprüche der Vorgabe: Mängel ohne Vorbehalt, Vorbehalt ohne Mangel, "verweigert" ohne Mangel -- "Mangel"
  heißt ein nicht verworfener Mangel im Feld "Mängel" dieses Protokolls;
- was create_acceptance() ablehnen würde: Teilabnahme ohne Beschreibung, Beschreibung bei der Gesamtabnahme, fehlende
  Vorbehalte bei "abgenommen", Vorbehalte bei "verweigert", eine Dachfläche, die nicht (mehr) zum Objekt gehört oder
  archiviert ist;
- ein anderer Unterzeichner als der Auftraggeber laut Auftrag oder ein Beteiligter des Projekts -- auch wenn die Fassung am
  ORM vorbei einen anderen Unterzeichner trägt (Angriff "falsche Unterzeichner-Art").

Läuft in app/checklists.py::add_attachment() unter der Zeilensperre der Checkliste -- dieselbe Sperre nehmen das Erfassen
und das Verwerfen eines Mangels im Protokoll (app/defects.py), die Zahl der Mängel kann sich also nicht dazwischen ändern.
Rollenlos."""

from sqlalchemy.orm import Session

from .checklist_purposes import (
    ACCEPTANCE_DEFECTS, ACCEPTANCE_PENALTY, ACCEPTANCE_RESULT, ACCEPTANCE_SCOPE, ACCEPTANCE_SCOPE_TEXT,
)
from .checklists import _answer_value, protocol_defects, roof_area_answer_problem

CUSTOMER_SIGNER_KINDS = ("auftraggeber", "beteiligter")


def protocol_values(checklist) -> dict:
    """Antworten der Systemfelder nach Schlüssel (Mängel stehen nicht darin, sie sind eigene Datensätze)."""
    fields = {f.id: f for f in checklist.template_version.fields if f.is_system}
    return {fields[a.template_field_id].field_key: _answer_value(a, fields[a.template_field_id])
            for a in checklist.answers if a.template_field_id in fields}


def open_protocol_defects(checklist) -> list:
    """Die nicht verworfenen Mängel des Protokolls."""
    return [d for d in protocol_defects(checklist) if d.discarded_at is None]


def check_customer_signature(db: Session, checklist, signer: dict) -> None:
    """Prüfung vor der Unterschrift des Auftraggebers -- siehe Moduldocstring. Die Pflichtfelder (Teilnehmer, Umfang,
    Ergebnis) prüft vorher schon missing_required_labels()."""
    if signer.get("signer_kind") not in CUSTOMER_SIGNER_KINDS:
        raise ValueError("Die Unterschrift des Auftraggebers leistet der Auftraggeber laut Auftrag oder ein Beteiligter "
                         "des Projekts.")
    values = protocol_values(checklist)
    scope, scope_text = values.get(ACCEPTANCE_SCOPE), (values.get(ACCEPTANCE_SCOPE_TEXT) or "").strip()
    if scope == "teil" and not scope_text:
        raise ValueError("Bei einer Teilabnahme bitte beschreiben, welcher Teil abgenommen wird.")
    if scope == "gesamt" and scope_text:
        raise ValueError("Eine Beschreibung des abgenommenen Teils gehört nur zur Teilabnahme – bitte leeren.")
    result = values.get(ACCEPTANCE_RESULT)
    defects_reserved, penalty_reserved = values.get(ACCEPTANCE_DEFECTS), values.get(ACCEPTANCE_PENALTY)
    if result == "abgenommen":
        if defects_reserved is None:
            raise ValueError("Bitte beantworten: Behält sich der Auftraggeber Rechte wegen bekannter Mängel vor?")
        if penalty_reserved is None:
            raise ValueError("Bitte beantworten: Behält sich der Auftraggeber die Vertragsstrafe vor?")
    elif defects_reserved is not None or penalty_reserved is not None:
        raise ValueError("Bei einer verweigerten Abnahme gibt es keine Vorbehalte – bitte die Antworten zu den Vorbehalten "
                         "leeren.")
    defects = open_protocol_defects(checklist)
    if result == "abgenommen" and defects and defects_reserved == "nein":
        anzahl = "steht ein Mangel" if len(defects) == 1 else f"stehen {len(defects)} Mängel"
        raise ValueError(f"Im Protokoll {anzahl}, aber kein Vorbehalt wegen Mängeln – bitte den Vorbehalt erklären lassen "
                         "oder die Mängel verwerfen.")
    if defects_reserved == "ja" and not defects:
        raise ValueError("Vorbehalt wegen Mängeln, aber im Protokoll steht kein Mangel – bitte die Mängel erfassen.")
    if result == "verweigert" and not defects:
        raise ValueError("Die Abnahme wird verweigert, aber im Protokoll steht kein Mangel – bitte die Mängel erfassen, "
                         "die zur Verweigerung führen.")
    problem = roof_area_answer_problem(db, checklist)
    if problem:
        raise ValueError(problem)
