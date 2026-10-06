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
Seit 1.8.63 ruft die Prüfung zum Schluss dieselbe Prüffunktion wie das Erfassen von Hand (app/acceptances.py::
check_acceptance()) -- so lehnt sie auch ab, was dort zusätzlich gilt (z. B. Länge der Texte).

Seit 1.8.63 (Stufe 2c-2d Teil 2, Punkt 3) die Folge "Abnahme am Auftrag anlegen" nach der Unterschrift des Auftraggebers
(acceptance_from_protocol(), Folge mit per_signature in app/checklist_purposes.py): je Unterschrift höchstens eine Abnahme
(UNIQUE an order_acceptances.checklist_attachment_id), angelegt über app/acceptances.py::create_acceptance() mit dem Nachweis
"Protokoll" (ProtocolSource) -- Art förmlich, Datum = Tag der Unterschrift in Europe/Berlin, Umfang, Ergebnis, Vorbehalte,
Einwendungen und Dachflächen aus der versiegelten Kopie der Unterschrift (nur wenn sie noch zu ihrer Prüfsumme passt), der
Erklärende aus der Unterschrift samt eingefrorener Vollmacht. Im selben Commit bekommen die Mängel der Kopie die Abnahme
(bedingtes UPDATE: von leer oder von einer verworfenen Abnahme) und die nicht verworfenen ihre Aufgabe; erst dann sind Haltung,
Freigabe und Status möglich. Alles unter der Zeilensperre der Checkliste -- auch das Verwerfen der Unterschrift
(app/checklists.py::discard_signatures() lehnt ab, solange eine Abnahme aus ihr gilt). Eine neue Abnahme aus demselben
Protokoll entsteht nur über eine neue Unterschrift, nachdem Abnahme und alte Unterschrift verworfen sind.
pending_protocol_acceptances(): ausstehende Abnahmen für den Hinweis am Auftrag, mit dem Grund, falls sie nicht angelegt
werden kann (protocol_acceptance_problem(), prüft ohne zu schreiben).

Rollenlos."""

import json

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .acceptances import ProtocolSource, check_acceptance
from .berlin_time import berlin_today, to_berlin
from .checklist_purposes import (
    ACCEPTANCE_CUSTOMER_SIGNATURE, ACCEPTANCE_DEFECTS, ACCEPTANCE_OBJECTIONS, ACCEPTANCE_PENALTY, ACCEPTANCE_PURPOSE,
    ACCEPTANCE_RESULT, ACCEPTANCE_ROOF_AREAS, ACCEPTANCE_SCOPE, ACCEPTANCE_SCOPE_TEXT,
)
from .checklists import _answer_value, protocol_defects, roof_area_answer_problem
from .models import Checklist, ChecklistTemplateVersion, Defect, Order, OrderAcceptance

CUSTOMER_SIGNER_KINDS = ("auftraggeber", "beteiligter")
_YES_NO = {"ja": True, "nein": False}


class SignatureNotValid(LookupError):
    """Die Unterschrift des Auftraggebers ist (nicht mehr) gültig -- keine Abnahme (Folge: fehlgeschlagen, entfällt dann)."""


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
    # Seit 1.8.63 zum Schluss dieselbe Prüfung wie beim Erfassen von Hand und bei der Abnahme aus dem Protokoll -- was sie
    # ablehnte, scheiterte sonst erst nach der Unterschrift (z. B. eine Beschreibung des Teils über 2.000 Zeichen).
    roof = values.get(ACCEPTANCE_ROOF_AREAS) or []
    source = ProtocolSource(checklist_id=checklist.id, signature_id=None, seal_sha256=None,
                            declared_name=signer.get("signer_name") or "", declared_role=signer.get("signer_role"),
                            person=signer.get("signer_person"), function=signer.get("signer_function"),
                            roof_area_names={r["id"]: r["name"] for r in roof})
    check_acceptance(db, db.get(Order, checklist.order_id),
                     acceptance_data(values, accepted_on=berlin_today(), declared_by=signer["signer_kind"],
                                     participant_id=signer.get("signer_participant_id")), protocol=source)


def acceptance_data(values: dict, *, accepted_on, declared_by: str, participant_id: int | None) -> dict:
    """Die Felder einer Abnahme (wie OrderAcceptanceCreate) aus den Antworten des Protokolls nach Schlüssel -- vor der
    Unterschrift aus den aktuellen Antworten, danach aus der versiegelten Kopie (seit 1.8.63)."""
    return {
        "kind": "foermlich", "accepted_on": accepted_on, "scope": values.get(ACCEPTANCE_SCOPE),
        "scope_description": values.get(ACCEPTANCE_SCOPE_TEXT), "result": values.get(ACCEPTANCE_RESULT),
        "reservation_defects": _YES_NO.get(values.get(ACCEPTANCE_DEFECTS)),
        "reservation_penalty": _YES_NO.get(values.get(ACCEPTANCE_PENALTY)),
        "contractor_objections": values.get(ACCEPTANCE_OBJECTIONS), "conduct_reason": None,
        "declared_by": declared_by, "participant_id": participant_id,
        "roof_area_ids": [r["id"] for r in values.get(ACCEPTANCE_ROOF_AREAS) or []],
    }


# ---------------------------------------------------------------------------
# Abnahme aus dem Protokoll (seit 1.8.63)
# ---------------------------------------------------------------------------

def sealed_values(signature) -> dict:
    """Die Antworten der versiegelten Kopie nach Feldschlüssel (Mängel stehen als "defects" darin, nicht als Wert)."""
    return {e["field_key"]: e.get("value") for e in json.loads(signature.sealed_content)["fields"]}


def protocol_acceptance_input(db: Session, checklist, signature) -> tuple[dict, ProtocolSource]:
    """(Daten, Nachweis) der Abnahme aus dieser Unterschrift des Auftraggebers -- nur aus der versiegelten Kopie, und nur,
    wenn sie noch zu ihrer Prüfsumme passt. Das Datum ist der Tag der Unterschrift in Europe/Berlin, nie der Tag, an dem die
    Folge läuft. ValueError mit lesbarem Grund."""
    from .checklists import check_signature, read_signer_poa

    if signature.sealed_content is None or check_signature(checklist, signature)["status"] != "unveraendert":
        raise ValueError("Die Unterschrift des Auftraggebers passt nicht mehr zu ihrer Prüfsumme – aus ihr entsteht keine "
                         "Abnahme. Bitte das Protokoll prüfen.")
    if signature.signer_kind not in CUSTOMER_SIGNER_KINDS:
        raise ValueError("Die Unterschrift des Auftraggebers stammt nicht vom Auftraggeber laut Auftrag oder einem "
                         "Beteiligten – keine Abnahme.")
    poa = None
    if signature.signer_poa_sha256:
        try:
            poa = read_signer_poa(signature)
        except (LookupError, ValueError) as exc:
            raise ValueError(f"Die beim Unterschreiben eingefrorene Vollmacht ist nicht lesbar ({exc}) – keine Abnahme.") \
                from exc
    values = sealed_values(signature)
    roof = values.get(ACCEPTANCE_ROOF_AREAS) or []
    source = ProtocolSource(checklist_id=checklist.id, signature_id=signature.id, seal_sha256=signature.content_sha256,
                            declared_name=signature.signer_name or "", declared_role=signature.signer_role,
                            person=signature.signer_person, function=signature.signer_function, poa=poa,
                            roof_area_names={r["id"]: r["name"] for r in roof})
    data = acceptance_data(values, accepted_on=to_berlin(signature.created_at).date(),
                           declared_by=signature.signer_kind, participant_id=signature.signer_participant_id)
    return data, source


def acceptance_for_signature(db: Session, signature_id: int) -> OrderAcceptance | None:
    return db.scalar(select(OrderAcceptance).where(OrderAcceptance.checklist_attachment_id == signature_id))


def customer_signature(checklist):
    from .checklist_follow_ups import triggering_signature  # lokal: die Folgen importieren die Zwecke

    return triggering_signature(checklist, ACCEPTANCE_CUSTOMER_SIGNATURE)


def acceptance_from_protocol(db: Session, checklist_id: int, *, signature_id: int | None = None,
                             user_id: int | None = None, user_name: str | None = None) -> OrderAcceptance:
    """Die Abnahme aus der gültigen Unterschrift des Auftraggebers (siehe Moduldocstring) -- idempotent: gibt es zu dieser
    Unterschrift schon eine (auch eine verworfene), ist das die Antwort. signature_id: die Unterschrift, für die die Folge
    fällig wurde; ist sie inzwischen eine andere oder keine, SignatureNotValid. ValueError, wenn create_acceptance() ablehnt
    oder die Kopie nicht mehr passt -- dann ist nichts gespeichert."""
    from .acceptances import create_acceptance, remove_stored_files, stored_filenames
    from .checklists import _load

    checklist = _load(db, checklist_id, for_update=True)
    if checklist is None:
        db.rollback()
        raise LookupError("Checkliste nicht gefunden.")
    if checklist.template_version.purpose != ACCEPTANCE_PURPOSE or checklist.order_id is None:
        db.rollback()
        raise ValueError("Diese Checkliste ist kein Abnahmeprotokoll zu einem Auftrag.")
    signature = customer_signature(checklist)
    if signature is None or (signature_id is not None and signature.id != signature_id):
        db.rollback()
        raise SignatureNotValid("Die Unterschrift des Auftraggebers ist nicht (mehr) gültig – daraus entsteht keine Abnahme.")
    existing = acceptance_for_signature(db, signature.id)
    if existing is not None:
        db.rollback()
        return existing
    order = db.get(Order, checklist.order_id)
    try:
        data, source = protocol_acceptance_input(db, checklist, signature)
    except ValueError:
        db.rollback()
        raise
    signature_key = signature.id
    try:
        acceptance = create_acceptance(db, order, data, [], user_id=user_id, user_name=user_name, protocol=source,
                                       commit=False)
    except IntegrityError:  # gleichzeitig schon angelegt (UNIQUE) -- create_acceptance hat zurückgerollt und aufgeräumt
        existing = acceptance_for_signature(db, signature_key)
        if existing is None:
            raise
        return existing
    stored = stored_filenames(acceptance)
    try:
        _attach_defects(db, checklist, signature, acceptance, order, user_id=user_id, user_name=user_name)
        db.commit()
    except IntegrityError:
        db.rollback()
        remove_stored_files(stored)
        existing = acceptance_for_signature(db, signature_key)
        if existing is None:
            raise
        return existing
    except Exception:
        db.rollback()
        remove_stored_files(stored)
        raise
    db.refresh(acceptance)
    return acceptance


def _attach_defects(db: Session, checklist, signature, acceptance: OrderAcceptance, order: Order, *,
                    user_id: int | None, user_name: str | None) -> None:
    """Jeder Mangel in der Kopie der Unterschrift bekommt die Abnahme -- auch ein danach verworfener (er steht im Protokoll),
    ein vorher verworfener nicht. Bedingtes UPDATE an der ORM-Sperre vorbei, nur von leer oder von einer verworfenen Abnahme
    aus (neue Unterschrift nach verworfener Abnahme -- dann mit Eintrag in der Änderungshistorie). Ein nicht verworfener
    Mangel ohne Aufgabe bekommt sie jetzt (wie beim Erfassen an der Abnahme: im Büro-Eingang, fällig zur Frist). Der
    gebundene Inhalt des Mangels ändert sich nicht (Festlegung 1.8.60 Nr. 4)."""
    from .audit import record_audit_entry
    from .checklists import sealed_defect_ids
    from .defects import ENTITY_TYPE, _new_task, defect_label

    ids = sealed_defect_ids(signature.sealed_content) or set()
    discarded = select(OrderAcceptance.id).where(OrderAcceptance.discarded_at.is_not(None)).scalar_subquery()
    for defect in protocol_defects(checklist):
        if defect.id not in ids or defect.acceptance_id == acceptance.id:
            continue
        previous, task_id = defect.acceptance_id, defect.task_id
        if defect.discarded_at is None and task_id is None:
            task = _new_task(db, order, acceptance, place=defect.roof_area_name or defect.location,
                             description=defect.description, due=defect.remedy_due_on, user_id=user_id,
                             user_name=defect.created_by_name)
            if task is not None:
                task.source_url = f"/orders/{order.id}#mangel-{defect.id}"
                task_id = task.id
        done = db.execute(
            update(Defect).where(Defect.id == defect.id, Defect.checklist_id == checklist.id,
                                 or_(Defect.acceptance_id.is_(None), Defect.acceptance_id.in_(discarded)))
            .values(acceptance_id=acceptance.id, task_id=task_id).execution_options(synchronize_session=False)
        ).rowcount
        if done != 1:
            raise ValueError(f"Mangel Nr. {defect.id} hängt schon an einer gültigen Abnahme – keine zweite.")
        if previous is not None:
            record_audit_entry(db, action="geändert", entity_type=ENTITY_TYPE, entity_id=defect.id,
                               entity_label=defect_label(defect, order), project_id=order.project_id,
                               field_name="acceptance_id", old_value=str(previous), new_value=str(acceptance.id),
                               actor_user_id=user_id, actor_name=(user_name or "System")[:160])


def protocol_acceptance_problem(db: Session, checklist, signature) -> str | None:
    """Warum aus dieser Unterschrift keine Abnahme entsteht -- dieselben Prüfungen wie beim Anlegen, ohne zu schreiben.
    None = sie ließe sich anlegen."""
    order = db.get(Order, checklist.order_id)
    try:
        data, source = protocol_acceptance_input(db, checklist, signature)
        check_acceptance(db, order, data, protocol=source)
    except ValueError as exc:
        return str(exc)
    return None


def pending_protocol_acceptances(db: Session, order: Order) -> list[dict]:
    """Abnahmeprotokolle dieses Auftrags mit gültiger Unterschrift des Auftraggebers, aus der noch keine Abnahme entstanden
    ist -- für den Hinweis am Auftrag mit "Nachholen", samt Grund, falls das Anlegen scheitern würde. Liest nur."""
    from .checklists import _load, signer_text

    ids = db.scalars(select(Checklist.id).join(ChecklistTemplateVersion,
                                               Checklist.template_version_id == ChecklistTemplateVersion.id)
                     .where(Checklist.order_id == order.id, ChecklistTemplateVersion.purpose == ACCEPTANCE_PURPOSE)
                     .order_by(Checklist.id)).all()
    result = []
    for checklist_id in ids:
        checklist = _load(db, checklist_id)
        signature = customer_signature(checklist)
        if signature is None or acceptance_for_signature(db, signature.id) is not None:
            continue
        signed = to_berlin(signature.created_at)
        result.append({
            "checklist_id": checklist.id, "label": checklist.template_label_snapshot, "url": f"/checklists/{checklist.id}",
            "signature_id": signature.id, "signed_at_local": signed, "signed_on": signed.date() if signed else None,
            "signer_name": signature.signer_name, "signer_text": signer_text(signature, ACCEPTANCE_PURPOSE),
            "problem": protocol_acceptance_problem(db, checklist, signature),
        })
    return result
