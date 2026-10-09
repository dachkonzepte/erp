"""Kopie an die im Dokument eingefrorenen Personen (seit 1.8.69, Nacharbeit zu Stufe 2c-2).

Herleitung: docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.69". Wo ein PDF "Kopie an:" zeigt -- die Briefe der
Behinderungs- und Bedenkenanzeige (app/notice_letter_pdf.py) und das Abnahmeprotokoll (app/checklist_pdf.py) --, gehen die Mails
genau an diese Empfänger. Beide versenden über app/notice_letters.py::dispatch_to_client(), das CC nur hieraus bildet (cc_of());
der Strukturtest tests/test_v371_kopien_an_personen.py hält das fest.

- Eingefroren werden beim Erstellen des Dokuments die Empfänger als Personen (freeze(): Beteiligter, Kontakt, Name und Rolle wie im
  PDF, dazu die Adresse von damals -- nur für den Hinweis), nicht ihre Adressen. Die Kopie geht an die heutige Adresse des Kontakts
  (resolve(); bei einem Eintrag mit Verweis aus dem Kunden- bzw. Lieferantenstamm) -- auch wenn er seither keine "Kopie bei
  Anzeigen" mehr hat, aus dem Projekt entfernt oder archiviert ist: er steht im PDF.
- Keine Mail bekommt, wer heute keine oder keine gültige Adresse hat oder nicht mehr im Adressbuch steht. Der Versand geht trotzdem;
  das Versandprotokoll hält je Person fest, an welche Adresse die Kopie ging oder warum keine Mail (record(), DispatchCopy).
- changes(): was sich seit dem Dokument geändert hat -- alte und neue Adresse, keine Adresse mehr, nicht mehr im Adressbuch, keine
  "Kopie bei Anzeigen" mehr, anderer Name oder andere Rolle, seither neu mit "Kopie bei Anzeigen". Hinweis vor dem Versand, keine
  Sperre.

Dokumente von vor 1.8.69 tragen in "Kopie an:" nur den Beteiligten (Briefe seit 1.8.40) bzw. dazu die Adresse (Protokoll 1.8.68):
dann die Person über den Beteiligten desselben Projekts; ist er entfernt, gilt sie als nicht mehr auffindbar. Vorher war beim
Protokoll die Adresse eingefroren (1.8.68), bei den Briefen CC frei vorbelegt (1.8.40). Rollenlos."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Contact, DispatchCopy, EmailDispatch, ProjectParticipant
from .project_participants import participant_info, participant_rows

NOT_IN_ADDRESS_BOOK = "nicht mehr im Adressbuch"
NO_ADDRESS = "keine E-Mail-Adresse"


def copy_recipients(db: Session, project_id: int) -> list[dict]:
    """Beteiligte mit "Kopie bei Anzeigen" (ohne archivierte Kontakte) -- wer beim Erstellen unter "Kopie an:" kommt (seit 1.8.40
    in app/notice_letters.py, seit 1.8.69 hier)."""
    return [info for info in (participant_info(p) for p in participant_rows(db, project_id))
            if info["copy_on_notices"] and not info["archived"]]


def freeze(db: Session, project_id: int) -> list[dict]:
    """"Kopie an:" beim Erstellen eines Dokuments: je Empfänger Beteiligter, Kontakt (die Person), Name und Rolle wie im PDF und
    die Adresse von jetzt -- die nur für den Hinweis, wenn sie sich bis zum Versand ändert."""
    return [{"participant_id": c["participant_id"], "contact_id": c["contact_id"], "name": c["name"],
             "role_label": c["role_label"], "email": c["email"]} for c in copy_recipients(db, project_id)]


def _person(db: Session, entry: dict, project_id: int) -> Contact | None:
    if entry.get("contact_id") is not None:
        return db.get(Contact, entry["contact_id"])
    # Vor 1.8.69 nur der Beteiligte: seine Person, solange er im selben Projekt steht.
    row = db.get(ProjectParticipant, entry["participant_id"])
    return row.contact if row is not None and row.project_id == project_id else None


def _today_address(contact: Contact) -> tuple[str | None, str | None]:
    """(Adresse von heute, Grund ohne Mail) -- mehrere Adressen im Feld werden alle genommen, eine ungültige sperrt nichts."""
    from .contacts import contact_values
    from .email_dispatch import parse_recipients

    raw = (contact_values(contact)["email"] or "").strip()
    if not raw:
        return None, NO_ADDRESS
    try:
        addresses = parse_recipients(raw, label="Adresse")
    except ValueError:
        return None, f"E-Mail-Adresse „{raw[:150]}“ ungültig"
    return (", ".join(addresses), None) if addresses else (None, NO_ADDRESS)


def resolve(db: Session, copy_to: list[dict], project_id: int) -> list[dict]:
    """Die eingefrorenen Empfänger mit ihrer Adresse von heute: je Eintrag Name und Rolle wie im PDF, email (heute; leer = keine
    Mail), no_mail (warum keine), email_then (beim Erstellen; then_known falsch bei Dokumenten ohne festgehaltene Adresse),
    archived."""
    copies = []
    for entry in copy_to:
        contact = _person(db, entry, project_id)
        if contact is None:
            email, no_mail = None, NOT_IN_ADDRESS_BOOK
        else:
            email, no_mail = _today_address(contact)
        copies.append({
            "participant_id": entry["participant_id"],
            "contact_id": contact.id if contact is not None else entry.get("contact_id"),
            "name": entry["name"], "role_label": entry["role_label"], "email": email, "no_mail": no_mail,
            "email_then": (entry.get("email") or "").strip() or None, "then_known": "email" in entry,
            "archived": bool(contact is not None and contact.archived),
        })
    return copies


def _addresses(text: str | None) -> list[str]:
    return [a.strip() for a in (text or "").split(",") if a.strip()]


def cc_of(copies: list[dict], ag_email: str | None) -> list[str]:
    """CC aus den eingefrorenen Empfängern: ihre Adressen von heute, jede einmal, ohne die des Auftraggebers (der steht in An)."""
    seen = {ag_email.strip().lower()} if ag_email else set()
    cc = []
    for c in copies:
        for address in _addresses(c["email"]):
            if address.lower() not in seen:
                seen.add(address.lower())
                cc.append(address)
    return cc


def _same(a: str | None, b: str | None) -> bool:
    return sorted(x.lower() for x in _addresses(a)) == sorted(x.lower() for x in _addresses(b))


def changes(db: Session, project_id: int, copies: list[dict]) -> list[str]:
    """Was sich seit dem Dokument an den Empfängern geändert hat -- je Änderung ein Satz, leer wenn nichts. Nur Hinweis: die Kopie
    geht an die Personen im PDF, an ihre Adresse von heute."""
    def label(c):
        return f"{c['name']} ({c['role_label']})"

    today = copy_recipients(db, project_id)
    by_participant = {c["participant_id"]: c for c in today}
    lines = []
    for c in copies:
        if c["no_mail"] == NOT_IN_ADDRESS_BOOK:
            lines.append(f"{label(c)} steht nicht mehr im Adressbuch – keine Mail; die Kopie bitte auf anderem Weg zustellen.")
            continue
        if c["then_known"] and not _same(c["email_then"], c["email"]):
            if c["email"]:
                lines.append(f"{label(c)}: E-Mail-Adresse heute {c['email']} statt {c['email_then'] or 'keine'} – die Kopie "
                             f"geht an {c['email']}.")
            else:
                lines.append(f"{label(c)}: heute {c['no_mail']} statt {c['email_then']} – keine Mail; die Kopie bitte auf "
                             "anderem Weg zustellen.")
        now = by_participant.get(c["participant_id"])
        if now is None:
            lines.append(f"{label(c)} hat heute keine „Kopie bei Anzeigen“ mehr (entfernt, archiviert oder abgewählt) – steht "
                         "aber im PDF unter „Kopie an:“ und bleibt Empfänger der Kopie.")
        elif (now["name"], now["role_label"]) != (c["name"], c["role_label"]):
            lines.append(f"{label(c)} heißt heute {label(now)}.")
    frozen_participants = {c["participant_id"] for c in copies}
    frozen_contacts = {c["contact_id"] for c in copies if c["contact_id"] is not None}
    lines += [f"{label(now)} hat seither „Kopie bei Anzeigen“ und steht nicht unter „Kopie an:“ – keine Mail; weitere "
              "Empfänger: PDF auf anderem Weg zustellen und unter „Zustellung nachtragen“ festhalten."
              for now in today if now["participant_id"] not in frozen_participants and now["contact_id"] not in frozen_contacts]
    return lines


def record(db: Session, dispatch: EmailDispatch, copies: list[dict]) -> None:
    """Vor dem Senden (dispatch_email(before_send=…)): je eingefrorenem Empfänger eine Zeile -- die Adressen, an die die Kopie
    tatsächlich geht (aus An und CC des Eintrags), oder keine Mail und warum. Committet nicht."""
    sent_to = {a.lower() for a in _addresses(dispatch.to_recipients) + _addresses(dispatch.cc_recipients)}
    for c in copies:
        used = [a for a in _addresses(c["email"]) if a.lower() in sent_to]
        note = None if used else (c["no_mail"] or "nicht unter den Empfängern des Versands")
        if used and any(a.lower() in {t.lower() for t in _addresses(dispatch.to_recipients)} for a in used):
            note = "dieselbe Adresse wie der Auftraggeber (An)"
        db.add(DispatchCopy(
            dispatch_id=dispatch.id, participant_id=c["participant_id"], contact_id=c["contact_id"],
            contact_name=c["name"][:255], role_label=c["role_label"][:80], email=", ".join(used)[:255] or None,
            note=note[:255] if note else None,
        ))
    db.flush()


def copy_to_dict(row: DispatchCopy) -> dict:
    return {"participant_id": row.participant_id, "contact_id": row.contact_id, "contact_name": row.contact_name,
            "role_label": row.role_label, "email": row.email, "note": row.note}


def dispatch_copies(db: Session, dispatch_ids: list[int]) -> dict[int, list[dict]]:
    """Festgehaltene Kopien je Versand, für mehrere Einträge in einer Abfrage."""
    if not dispatch_ids:
        return {}
    result: dict[int, list[dict]] = {}
    for row in db.scalars(select(DispatchCopy).where(DispatchCopy.dispatch_id.in_(dispatch_ids)).order_by(DispatchCopy.id)):
        result.setdefault(row.dispatch_id, []).append(copy_to_dict(row))
    return result
