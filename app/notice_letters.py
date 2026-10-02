"""Briefe an den Auftraggeber zu einer Behinderungsanzeige (seit 1.8.40, Stufe 2b, Runde 2b-3 Teil 2).

Herleitung: docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.40". Die Behinderungsanzeige ist
eine Checkliste mit Zweck "behinderungsanzeige" (app/checklist_purposes.py, 1.8.38). Aus ihr entstehen zwei
Briefe (LETTER_KINDS):

- "behinderungsanzeige": nach der "Unterschrift Büro" im Abschnitt Anzeige -- Inhalt aus den Abschnitten
  Meldung und Anzeige, Fotos verkleinert als Anlage;
- "wiederaufnahme" (Anzeige der Wiederaufnahme): nach der Unterschrift im Abschnitt Wegfall -- Bezug auf die
  Behinderungsanzeige und den Beginn der Behinderung, dazu der Abschnitt Wegfall.

Fassung (NoticeLetter): je Briefart und Unterschrift genau eine. Der Inhalt kommt aus der versiegelten Kopie
dieser Unterschrift (ChecklistAttachment.sealed_content), nicht aus den Antworten -- der Brief zeigt, was
unterschrieben wurde, und entsteht nur, solange der aktuelle Inhalt noch zur Prüfsumme passt. Empfänger
(Auftraggeber = Kunde des Projekts, Anrede), Betreff (Bauvorhaben, Auftragsnummer), Vorbehalt
(app/notice_reservations.py, nur geprüft gedruckt), "Kopie an:" (Beteiligte mit "Kopie bei Anzeigen") und
Datum werden beim Erstellen eingefroren: kanonisches JSON mit Prüfsumme, das PDF in der Ablage. Erstellt wird
die Fassung beim ersten Versand oder ausdrücklich ("Brief erstellen", für Post und Fax); Versand, Download und
nachgetragene Zustellung verwenden danach nur dieses PDF. Wird die Unterschrift verworfen und neu geleistet,
entsteht beim nächsten Versand eine neue Fassung; die alten bleiben als Nachweis.

Versand (Regel 21, über dispatch_email()): An ist immer der Auftraggeber -- die API nimmt keine An-Adresse
entgegen; CC vorbelegt mit den Beteiligten "Kopie bei Anzeigen", doppelte Adressen fallen weg (auch eine CC
gleich dem Auftraggeber). Geht die Mail an einen empfangsbevollmächtigten Beteiligten (An oder CC), wird seine
Vollmacht vor dem Senden mit Prüfsumme in die Ablage kopiert (DispatchAuthorization) -- ersetzt das Büro sie
später, bleibt diese Kopie. Nach dem Versand der Behinderungsanzeige -- per E-Mail oder als nachgetragene
Zustellung -- ist die Aufgabe "Behinderungsanzeige versenden" (Folge der Meldung, 1.8.38) erledigt.

Rollenlos wie jede Geschäftslogik; nur das Büro (app/routers/notice_letters.py). Der PDF-Renderer
(app/notice_letter_pdf.py) wird lokal importiert (Regel 3).
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .berlin_time import to_berlin
from .checklist_follow_ups import triggering_signature
from .checklist_purposes import OBSTRUCTION_PURPOSE
from .checklists import _load as _load_checklist, attachment_path, check_signature
from .models import (
    Checklist, ChecklistAttachment, ChecklistFollowUp, Contact, Customer, EmailDispatch, NoticeLetter, Order,
    ProjectParticipant, SentDocument, Task, TaskColumn,
)
from .notice_reservations import printable_reservation, reservation_state

logger = logging.getLogger(__name__)

B = OBSTRUCTION_PURPOSE + "."
SEND_FOLLOW_UP_KEY = B + "versenden"  # Folge der Meldung (app/checklist_purposes.py)
PREVIEW_WATERMARK = "Vorschau – nicht versendet"
YES_NO = {"ja": "Ja", "nein": "Nein", "entfaellt": "Entfällt"}


class NoticeStateError(Exception):
    """Der Brief ist in diesem Zustand nicht möglich (Abschnitt nicht unterschrieben, Inhalt weicht von
    der Unterschrift ab, Ablage beschädigt) -- Router: 409."""


@dataclass(frozen=True)
class LetterKind:
    key: str
    label: str
    signature_field: str  # nach dieser Unterschrift ist der Brief möglich
    starts_after: str | None  # Inhalt: Felder nach diesem Unterschriftsfeld (None: von Anfang an)
    requires: tuple[str, ...]  # weitere Unterschriften, die gültig sein müssen
    reference_fields: tuple[str, ...]  # Angaben aus früheren Abschnitten, die der Brief als Bezug nennt
    waiting_text: str


LETTER_KINDS: dict[str, LetterKind] = {k.key: k for k in (
    LetterKind("behinderungsanzeige", "Behinderungsanzeige", B + "unterschrift_buero", None, (), (),
               "Möglich nach der „Unterschrift Büro“ im Abschnitt „Anzeige“."),
    LetterKind("wiederaufnahme", "Anzeige der Wiederaufnahme", B + "unterschrift_wegfall", B + "unterschrift_buero",
               (B + "unterschrift_buero",), (B + "beginn",),
               "Möglich nach der Unterschrift im Abschnitt „Wegfall“ (und der „Unterschrift Büro“ im Abschnitt „Anzeige“)."),
)}

INTRO = {
    "behinderungsanzeige": ("hiermit zeigen wir Ihnen an, dass wir bei der Ausführung unserer Leistungen zum oben "
                            "genannten Auftrag behindert sind. Im Einzelnen:"),
    "wiederaufnahme": ("die {bezug} Behinderung bei der Ausführung unserer Leistungen zum oben genannten Auftrag ist "
                       "weggefallen; wir haben die Arbeiten wieder aufgenommen. Im Einzelnen:"),
}
DEFAULT_EMAIL_SUBJECT = {
    "behinderungsanzeige": "Behinderungsanzeige – Auftrag {auftragsnummer}",
    "wiederaufnahme": "Anzeige der Wiederaufnahme – Auftrag {auftragsnummer}",
}
DEFAULT_EMAIL_BODY = {
    "behinderungsanzeige": ("{anrede}\n\nanbei erhalten Sie unsere Behinderungsanzeige zum Auftrag {auftragsnummer} "
                            "(Bauvorhaben {bauvorhaben}).\n\nMit freundlichen Grüßen"),
    "wiederaufnahme": ("{anrede}\n\nanbei erhalten Sie unsere Anzeige der Wiederaufnahme der Arbeiten zum Auftrag "
                       "{auftragsnummer} (Bauvorhaben {bauvorhaben}).\n\nMit freundlichen Grüßen"),
}
EMAIL_PLACEHOLDERS = ("{anrede}", "{auftragsnummer}", "{kundenname}", "{bauvorhaben}", "{checklistennummer}")


# --- Laden und Zustand ------------------------------------------------------------------------

def letter_kind(key: str) -> LetterKind:
    spec = LETTER_KINDS.get(key)
    if spec is None:
        raise LookupError("Unbekannte Briefart.")
    return spec


def _checklist(db: Session, checklist_id: int, *, for_update: bool = False) -> Checklist:
    checklist = _load_checklist(db, checklist_id, for_update=for_update)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    if checklist.template_version.purpose != OBSTRUCTION_PURPOSE or checklist.order_id is None:
        raise LookupError("Diese Checkliste ist keine Behinderungsanzeige am Auftrag.")
    return checklist


def _order(db: Session, checklist: Checklist) -> Order:
    order = db.get(Order, checklist.order_id)
    if order is None:
        raise LookupError("Auftrag nicht gefunden.")
    return order


def _customer(order: Order) -> Customer | None:
    return order.project.customer if order.project is not None else None


def section_signature(checklist: Checklist, spec: LetterKind) -> ChecklistAttachment | None:
    """Die gültige Unterschrift, nach der der Brief möglich ist -- None, solange sie (oder eine geforderte
    frühere) fehlt oder verworfen ist."""
    if any(triggering_signature(checklist, key) is None for key in spec.requires):
        return None
    return triggering_signature(checklist, spec.signature_field)


def _require_intact(checklist: Checklist, signature: ChecklistAttachment) -> None:
    seal = check_signature(checklist, signature)
    if seal["status"] != "unveraendert" or signature.sealed_content is None:
        raise NoticeStateError(
            f"{seal['text']} Der Brief wird nicht erstellt – das Büro kann die Unterschrift mit Begründung "
            "verwerfen und neu unterschreiben lassen."
        )


# --- Inhalt -----------------------------------------------------------------------------------

def salutation_line(customer: Customer | None) -> str:
    """"Sehr geehrter Herr …," / "Sehr geehrte Frau …," aus der Anrede des Kunden, sonst "Sehr geehrte Damen
    und Herren," (auch bei "Firma"). Festlegung: "Divers" mit "Guten Tag <Vorname Nachname>,"."""
    if customer is None or not customer.last_name:
        return "Sehr geehrte Damen und Herren,"
    salutation = (customer.salutation or "").strip()
    with_title = " ".join(x for x in (customer.title, customer.last_name) if x)
    if salutation == "Herr":
        return f"Sehr geehrter Herr {with_title},"
    if salutation == "Frau":
        return f"Sehr geehrte Frau {with_title},"
    if salutation == "Divers":
        return f"Guten Tag {' '.join(x for x in (customer.title, customer.first_name, customer.last_name) if x)},"
    return "Sehr geehrte Damen und Herren,"


def _recipient_lines(customer: Customer | None, order: Order) -> list[str]:
    """Anschrift des Auftraggebers -- aus dem Kundenstamm (der Brief geht heute hinaus, nicht beim
    Beauftragen), ohne Kunden der Schnappschuss am Auftrag."""
    if customer is None:
        return [order.customer_name] + (order.customer_address.split(", ", 1) if order.customer_address else [])
    lines = [customer.name, customer.street, " ".join(x for x in (customer.postal_code, customer.city) if x)]
    if customer.country and customer.country.strip().lower() not in ("deutschland", "de", "germany"):
        lines.append(customer.country)
    return [x for x in lines if x]


def construction_project(order: Order) -> str:
    """Bauvorhaben für Betreff und E-Mail: Objekt und Anschrift aus dem Auftrag (Schnappschuss)."""
    parts = [order.property_name] + [x for x in str(order.property_address or "").splitlines() if x.strip()]
    return ", ".join(x.strip() for x in parts if x and x.strip()) or (order.title or order.order_number)


def _format_value(field, value) -> str | None:
    """Wert aus der versiegelten Kopie (kanonisch) als Text -- dieselbe Lesart wie Seite und PDF der Checkliste."""
    if value in (None, "", []):
        return None
    t = field.field_type
    if t == "ja_nein":
        return YES_NO.get(value, str(value))
    if t == "auswahl":
        labels = {o.option_key: o.label for o in field.options}
        return ", ".join(labels.get(k, k) for k in (value if isinstance(value, list) else [value]))
    if t == "zahl":
        text = str(value).replace(".", ",")
        return f"{text} {field.unit}" if field.unit else text
    if t == "datum":
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    if t == "uhrzeit":
        return f"{value} Uhr"
    if t == "datum_uhrzeit":
        return datetime.fromisoformat(value).strftime("%d.%m.%Y, %H:%M Uhr")
    return str(value)


def _letter_fields(checklist: Checklist, spec: LetterKind, signature: ChecklistAttachment) -> tuple[list[dict], list[dict]]:
    """(Angaben, Fotos) des Briefs aus der versiegelten Kopie der Unterschrift: die Felder ihres Abschnitts
    (nach spec.starts_after bis zur Unterschrift), davor die Bezugsangaben (spec.reference_fields). Leere
    Angaben fehlen; Fotos mit der Prüfsumme aus der Kopie."""
    sealed = {e["field_key"]: e for e in json.loads(signature.sealed_content)["fields"]}
    fields = checklist.template_version.fields
    position = {f.field_key: i for i, f in enumerate(fields)}
    start = position[spec.starts_after] + 1 if spec.starts_after in position else 0
    end = position[spec.signature_field]
    items, photos = [], []
    for field in fields:
        if field.field_key in spec.reference_fields and position[field.field_key] < start:
            value = _format_value(field, sealed.get(field.field_key, {}).get("value"))
            if value:
                items.append({"field_key": field.field_key, "label": field.label, "value": value})
    for field in fields[start:end]:
        entry = sealed.get(field.field_key)
        if entry is None or field.field_type in ("hinweis", "unterschrift"):
            continue
        if field.field_type == "foto":
            photos += [{"id": p["id"], "field_key": field.field_key, "label": field.label, "sha256": p["sha256"]}
                       for p in entry.get("photos", [])]
            continue
        value = _format_value(field, entry.get("value"))
        if value:
            items.append({"field_key": field.field_key, "label": field.label, "value": value})
    return items, photos


def _participant_rows(db: Session, project_id: int) -> list[ProjectParticipant]:
    from .project_participants import ROLES

    rows = db.scalars(
        select(ProjectParticipant).where(ProjectParticipant.project_id == project_id)
        .options(selectinload(ProjectParticipant.contact).selectinload(Contact.customer),
                 selectinload(ProjectParticipant.contact).selectinload(Contact.supplier))
    ).all()
    order = {key: i for i, key in enumerate(ROLES)}
    return sorted(rows, key=lambda p: (order.get(p.role, len(order)), p.id))


def _participant_info(p: ProjectParticipant) -> dict:
    from .contacts import contact_display_name, contact_values
    from .project_participants import role_label

    return {
        "participant_id": p.id, "name": contact_display_name(p.contact), "role": p.role,
        "role_label": role_label(p.role), "email": (contact_values(p.contact)["email"] or "").strip() or None,
        "copy_on_notices": p.copy_on_notices, "authorized": p.authorized_recipient,
        "has_poa": bool(p.poa_stored_filename), "archived": p.contact.archived,
    }


def copy_recipients(db: Session, project_id: int) -> list[dict]:
    """Beteiligte mit "Kopie bei Anzeigen" (ohne archivierte Kontakte) -- "Kopie an:" im Brief und Vorbelegung
    von CC."""
    return [info for info in (_participant_info(p) for p in _participant_rows(db, project_id))
            if info["copy_on_notices"] and not info["archived"]]


def _sent_on(db: Session, kind: str, checklist_id: int) -> date | None:
    """Tag des ersten erfolgreichen Versands dieser Briefart (E-Mail: Abschluss in Europe/Berlin,
    nachgetragene Zustellung: Zustelldatum)."""
    rows = db.execute(select(EmailDispatch.finished_at, EmailDispatch.delivered_on).where(
        EmailDispatch.document_type == kind, EmailDispatch.document_id == checklist_id,
        EmailDispatch.status == "gesendet")).all()
    days = [delivered or (to_berlin(finished).date() if finished else None) for finished, delivered in rows]
    days = [d for d in days if d is not None]
    return min(days) if days else None


def letter_was_sent(db: Session, kind: str, checklist_id: int) -> bool:
    return db.scalar(select(EmailDispatch.id).where(
        EmailDispatch.document_type == kind, EmailDispatch.document_id == checklist_id,
        EmailDispatch.status == "gesendet").limit(1)) is not None


def _canonical(content: dict) -> str:
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_letter_content(db: Session, checklist: Checklist, spec: LetterKind, signature: ChecklistAttachment, *,
                         version_no: int | None, letter_date: date) -> dict:
    """Alles, was im Brief steht, außer Briefpapier und Layout (eingefroren beim Erstellen)."""
    from .settings import get_or_create_general_settings

    order = _order(db, checklist)
    customer = _customer(order)
    general = get_or_create_general_settings(db)
    items, photos = _letter_fields(checklist, spec, signature)
    reservation_text = printable_reservation(db, spec.key, order.contract_basis)
    signature_field = next(f for f in checklist.template_version.fields if f.id == signature.template_field_id)
    signed_at = to_berlin(signature.created_at)
    bezug = ""
    if spec.key == "wiederaufnahme":
        sent_on = _sent_on(db, "behinderungsanzeige", checklist.id)
        bezug = f"mit unserer Behinderungsanzeige vom {sent_on.strftime('%d.%m.%Y')} angezeigte" if sent_on else "angezeigte"
    sender_parts = [general.company_name, general.street, " ".join(x for x in (general.postal_code, general.city) if x)]
    project = construction_project(order)
    return {
        "v": 1, "kind": spec.key, "kind_label": spec.label, "checklist_id": checklist.id, "version_no": version_no,
        "order_id": order.id, "order_number": order.order_number,
        "customer_number": customer.customer_number if customer is not None else order.customer_number,
        "contract_basis": order.contract_basis, "letter_date": letter_date.isoformat(),
        "sender_line": " - ".join(x for x in sender_parts if x),
        "recipient": {"customer_id": customer.id if customer is not None else None,
                      "lines": _recipient_lines(customer, order)},
        "salutation": salutation_line(customer), "construction_project": project,
        "subject": spec.label, "subject_line": f"Bauvorhaben: {project} · Auftrag {order.order_number}",
        "intro": INTRO[spec.key].format(bezug=bezug),
        "items": items,
        "reservation": {"text": reservation_text, "printed": reservation_text is not None},
        "closing": "Mit freundlichen Grüßen", "company_name": general.company_name,
        "signature": {
            "attachment_id": signature.id, "field_key": signature_field.field_key, "signer_name": signature.signer_name,
            "signer_label": signature_field.signer_label, "signed_at": signed_at.strftime("%Y-%m-%dT%H:%M") if signed_at else None,
            "content_sha256": signature.content_sha256,
            "image_sha256": _file_sha256(attachment_path(signature)),
        },
        "copy_to": [{"participant_id": c["participant_id"], "name": c["name"], "role_label": c["role_label"]}
                    for c in copy_recipients(db, order.project_id)],
        "photos": photos,
    }


def _file_sha256(path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _render(db: Session, checklist: Checklist, content: dict, *, watermark: str | None = None) -> bytes:
    from .notice_letter_pdf import build_notice_letter_pdf  # lokal, Regel 3

    attachments = {a.id: a for a in checklist.attachments}
    photo_paths = [attachment_path(attachments[p["id"]]) for p in content["photos"]]
    return build_notice_letter_pdf(db, content, signature_path=attachment_path(attachments[content["signature"]["attachment_id"]]),
                                   photo_paths=photo_paths, watermark=watermark)


# --- Fassung ----------------------------------------------------------------------------------

def _letters(db: Session, checklist_id: int, kind: str | None = None) -> list[NoticeLetter]:
    query = select(NoticeLetter).where(NoticeLetter.checklist_id == checklist_id)
    if kind is not None:
        query = query.where(NoticeLetter.kind == kind)
    return list(db.scalars(query.options(selectinload(NoticeLetter.sent_document))
                          .order_by(NoticeLetter.kind, NoticeLetter.version_no.desc())).all())


def _letter_for(db: Session, checklist_id: int, kind: str, signature_id: int) -> NoticeLetter | None:
    return db.scalar(select(NoticeLetter).where(NoticeLetter.checklist_id == checklist_id, NoticeLetter.kind == kind,
                                                NoticeLetter.signature_id == signature_id))


def preview_pdf(db: Session, checklist_id: int, kind: str) -> bytes:
    """Vorschau mit dem Stand von jetzt, quer "Vorschau – nicht versendet" -- nichts wird abgelegt."""
    from .berlin_time import berlin_today

    spec = letter_kind(kind)
    checklist = _checklist(db, checklist_id)
    signature = section_signature(checklist, spec)
    if signature is None:
        raise NoticeStateError(spec.waiting_text)
    _require_intact(checklist, signature)
    content = build_letter_content(db, checklist, spec, signature, version_no=None, letter_date=berlin_today())
    return _render(db, checklist, content, watermark=PREVIEW_WATERMARK)


def _next_version_no(db: Session, checklist_id: int, kind: str) -> int:
    return (db.scalar(select(func.max(NoticeLetter.version_no)).where(
        NoticeLetter.checklist_id == checklist_id, NoticeLetter.kind == kind)) or 0) + 1


def ensure_letter(db: Session, checklist_id: int, kind: str, *, user_id: int | None = None,
                  user_name: str | None = None) -> NoticeLetter:
    """Die Fassung zur aktuellen Unterschrift des Abschnitts -- vorhanden oder jetzt erstellt (Inhalt
    einfrieren, PDF rendern und ablegen, Historie). Committet.

    Zwei Schritte: Inhalt und PDF entstehen OHNE Sperre -- das Rendern legt beim allerersten Mal
    Grundeinstellungen (Briefpapier-Bausteine, Ränder) an und committet dabei; unter einer Zeilensperre
    verklemmten sich so zwei gleichzeitige Aufrufe (gegen PostgreSQL gefunden). Danach unter der Zeilensperre
    der Checkliste: dieselbe Unterschrift noch gültig, noch keine Fassung dazu, dieselbe Nummer -- dann ablegen.
    Zwei gleichzeitige Aufrufe ergeben so eine Fassung (zusätzlich der Unique-Schlüssel je Unterschrift)."""
    from .audit import current_actor, record_audit_entry
    from .berlin_time import berlin_today
    from .sent_documents import store_sent_document

    spec = letter_kind(kind)
    checklist = _checklist(db, checklist_id)
    signature = section_signature(checklist, spec)
    if signature is None:
        raise NoticeStateError(spec.waiting_text)
    existing = _letter_for(db, checklist_id, kind, signature.id)
    if existing is not None:
        return existing
    _require_intact(checklist, signature)
    if user_id is None and user_name is None:
        user_id, user_name = current_actor()
    user_name = user_name or "System"
    signature_id = signature.id
    version_no = _next_version_no(db, checklist_id, kind)
    content = build_letter_content(db, checklist, spec, signature, version_no=version_no, letter_date=berlin_today())
    canonical = _canonical(content)
    pdf = _render(db, checklist, content)

    checklist = _checklist(db, checklist_id, for_update=True)
    signature = section_signature(checklist, spec)
    if signature is None or signature.id != signature_id:
        db.rollback()
        raise NoticeStateError("Die Unterschrift hat sich inzwischen geändert – bitte die Seite neu laden.")
    existing = _letter_for(db, checklist_id, kind, signature_id)
    if existing is not None:
        db.commit()  # Zeilensperre freigeben -- ein gleichzeitiger Aufruf war schneller, seine Fassung gilt
        return existing
    if _next_version_no(db, checklist_id, kind) != version_no:
        db.rollback()
        raise NoticeStateError("Inzwischen ist eine andere Fassung entstanden – bitte die Seite neu laden.")
    order = _order(db, checklist)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{'Behinderungsanzeige' if kind == 'behinderungsanzeige' else 'Wiederaufnahme'}_"
                  f"{order.order_number}_Fassung_{version_no}")
    document = store_sent_document(
        db, document_type=kind, document_id=checklist.id, document_number=f"{order.order_number} · Fassung {version_no}"[:80],
        filename=f"{stem}.pdf", content=pdf, user_id=user_id, user_name=user_name,
    )
    letter = NoticeLetter(
        checklist_id=checklist.id, kind=kind, version_no=version_no, signature_id=signature.id,
        signature_sha256=signature.content_sha256, content=canonical,
        content_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(), sent_document_id=document.id,
        reservation_printed=content["reservation"]["printed"], created_by_user_id=user_id, created_by_name=user_name,
    )
    try:
        with db.begin_nested():
            db.add(letter)
            db.flush()
    except IntegrityError:
        # Ein gleichzeitiger Aufruf war schneller (unter SQLite ohne Zeilensperre möglich) -- seine Fassung
        # gilt; die schon abgelegte Datei bleibt ohne Eintrag liegen (die Ablage löscht nie, wie 1.8.20).
        db.rollback()
        existing = _letter_for(db, checklist_id, kind, signature.id)
        if existing is None:
            raise
        return existing
    record_audit_entry(
        db, action="geändert", entity_type="Checkliste", entity_id=checklist.id,
        entity_label=f"Nr. {checklist.id} {checklist.template_label_snapshot} · {checklist.context_label_snapshot or ''}",
        project_id=order.project_id, field_name="notice_letter", field_label=f"{spec.label} als Brief erstellt",
        new_value=f"Fassung {version_no} · PDF-Prüfsumme {document.sha256}"
                  + ("" if content["reservation"]["printed"] else " · ohne Vorbehalt (nicht geprüft)"),
        actor_user_id=user_id, actor_name=user_name,
    )
    db.commit()
    db.refresh(letter)
    return letter


def letter_document(letter: NoticeLetter) -> bytes:
    """Das abgelegte PDF der Fassung -- nur mit stimmender Prüfsumme (sonst NoticeStateError)."""
    from .sent_documents import ArchiveFileError, read_sent_document

    try:
        return read_sent_document(letter.sent_document)
    except ArchiveFileError as e:
        raise NoticeStateError(f"Der Brief in der Ablage ist nicht mehr unversehrt: {e} Es wurde nichts versendet.") from e


# --- Versand ----------------------------------------------------------------------------------

def _authorized_snapshot(db: Session, dispatch: EmailDispatch, *, kind: str, checklist_id: int, project_id: int,
                         user_id: int | None, user_name: str) -> None:
    """Hook vor dem Senden (dispatch_email(before_send=…)): je empfangsbevollmächtigtem Beteiligten, an dessen
    Adresse die Mail geht, die Vollmacht als Kopie in die Ablage und eine DispatchAuthorization-Zeile. Eine
    fehlende oder veränderte Vollmacht-Datei hält den Versand nicht auf (die Anzeige muss unverzüglich hinaus)
    -- die Zeile sagt es dann. Committet nicht (der Aufrufer)."""
    from .models import DispatchAuthorization
    from .project_participants import power_of_attorney_path
    from .sent_documents import CONTENT_TYPE_SUFFIXES, store_sent_document

    recipients = {a.strip().lower() for a in f"{dispatch.to_recipients or ''},{dispatch.cc_recipients or ''}".split(",")
                  if a.strip()}
    for p in _participant_rows(db, project_id):
        info = _participant_info(p)
        if not info["authorized"] or not info["email"] or info["email"].lower() not in recipients:
            continue
        document, note = None, None
        if not p.poa_stored_filename:
            note = "Keine Vollmacht hinterlegt."
        else:
            try:
                data = power_of_attorney_path(p.poa_stored_filename).read_bytes()
            except (FileNotFoundError, NotADirectoryError):
                data = None
            if data is None or hashlib.sha256(data).hexdigest() != p.poa_sha256 \
                    or p.poa_content_type not in CONTENT_TYPE_SUFFIXES:
                note = "Vollmacht-Datei fehlt oder passt nicht zu ihrer Prüfsumme – nicht festgehalten."
            else:
                document = db.scalar(select(SentDocument).where(
                    SentDocument.document_type == kind, SentDocument.document_id == checklist_id,
                    SentDocument.sha256 == p.poa_sha256).limit(1))
                if document is None:
                    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", f"Vollmacht_{info['name']}")[:80]
                    document = store_sent_document(
                        db, document_type=kind, document_id=checklist_id, document_number=dispatch.document_number,
                        filename=f"{stem}{CONTENT_TYPE_SUFFIXES[p.poa_content_type]}", content=data, user_id=user_id,
                        user_name=user_name, content_type=p.poa_content_type,
                    )
        db.add(DispatchAuthorization(
            dispatch_id=dispatch.id, participant_id=p.id, contact_name=info["name"][:255], role=p.role,
            recipient_email=info["email"][:255], sent_document_id=document.id if document else None,
            poa_sha256=document.sha256 if document else None, note=note,
        ))
    db.flush()


def _email_texts(db: Session, kind: str, checklist: Checklist, order: Order) -> tuple[str, str]:
    from .document_email_templates import get_email_template
    from .placeholders import apply_placeholders

    customer = _customer(order)
    values = {"{anrede}": salutation_line(customer), "{auftragsnummer}": order.order_number,
              "{kundenname}": customer.name if customer is not None else order.customer_name,
              "{bauvorhaben}": construction_project(order), "{checklistennummer}": str(checklist.id)}
    template = get_email_template(db, kind)
    subject = (template.subject_template if template else None) or DEFAULT_EMAIL_SUBJECT[kind]
    body = (template.body_template if template else None) or DEFAULT_EMAIL_BODY[kind]
    return apply_placeholders(subject, values), apply_placeholders(body, values)


def send_notice_letter(db: Session, checklist_id: int, kind: str, *, cc_email: str | None = None,
                       dispatch_key: str | None = None, user=None):
    """Versendet die Fassung zur aktuellen Unterschrift (erstellt sie beim ersten Mal) an den Auftraggeber.
    Wirft NoticeStateError (Zustand, 409), ValueError (Eingabe/Versand, 400), DispatchConflict (409)."""
    from .email_dispatch import actor_of, dispatch_email, new_dispatch_key

    spec = letter_kind(kind)
    user_id, user_name = actor_of(user)
    checklist = _checklist(db, checklist_id)
    if section_signature(checklist, spec) is None:
        raise NoticeStateError(spec.waiting_text)  # Zustand zuerst, vor Empfänger und Fassung
    order = _order(db, checklist)
    customer = _customer(order)
    to = (customer.email or "").strip() if customer is not None else ""
    if not to:
        raise ValueError("Der Auftraggeber hat keine E-Mail-Adresse. Bitte im Kundenstamm ergänzen oder den Brief "
                         "auf anderem Weg zustellen und unter „Zustellung nachtragen“ festhalten.")
    letter = ensure_letter(db, checklist_id, kind, user_id=user_id, user_name=user_name)
    pdf = letter_document(letter)
    subject, body = _email_texts(db, kind, checklist, order)
    project_id = order.project_id

    def freeze(session: Session, dispatch: EmailDispatch) -> None:
        _authorized_snapshot(session, dispatch, kind=kind, checklist_id=checklist_id, project_id=project_id,
                             user_id=user_id, user_name=user_name or "System")

    result = dispatch_email(
        db, dispatch_key=dispatch_key or new_dispatch_key(kind), document_type=kind, document_id=checklist_id,
        document_number=letter.sent_document.document_number, to=to, cc=cc_email, subject=subject, body_text=body,
        attachment_bytes=pdf, attachment_filename=letter.sent_document.filename, archived_document=letter.sent_document,
        user_id=user_id, user_name=user_name, before_send=freeze,
    )
    if result.newly_sent and kind == "behinderungsanzeige":
        complete_send_tasks(db, checklist_id)
    return result


def complete_send_tasks(db: Session, checklist_id: int) -> int:
    """Setzt die offene Aufgabe "Behinderungsanzeige versenden" der Checkliste auf die erste "erledigt"-Spalte.
    Ein Fehler hier macht den Versand nicht ungeschehen -- nur Klassenname im Protokoll (Regel 18). Liefert die
    Zahl der erledigten Aufgaben."""
    from .tasks import update_task

    done = 0
    try:
        task_ids = list(db.scalars(select(ChecklistFollowUp.target_id).where(
            ChecklistFollowUp.checklist_id == checklist_id, ChecklistFollowUp.follow_up_key == SEND_FOLLOW_UP_KEY,
            ChecklistFollowUp.target_type == "task", ChecklistFollowUp.target_id.is_not(None))).all())
        done_key = db.scalar(select(TaskColumn.key).where(TaskColumn.is_done == True)  # noqa: E712
                             .order_by(TaskColumn.sort_order, TaskColumn.id).limit(1))
        done_keys = set(db.scalars(select(TaskColumn.key).where(TaskColumn.is_done == True)).all())  # noqa: E712
        for task_id in task_ids:
            task = db.get(Task, task_id)
            if task is None or task.status in done_keys or done_key is None:
                continue
            update_task(db, task_id, status=done_key)
            done += 1
    except Exception as exc:  # noqa: BLE001 -- der Versand ist geschehen, die Aufgabe bleibt dann offen
        db.rollback()
        logger.warning("Aufgabe zur Behinderungsanzeige %s nicht erledigt (%s)", checklist_id, type(exc).__name__)
    return done


def dispatch_document_for(db: Session, checklist: Checklist, kind: str):
    """Eintrag für app/dispatch_documents.py (Zustellung nachtragen): die Fassung zur aktuellen Unterschrift
    (beim ersten Mal erstellt), nach dem Eintrag der Behinderungsanzeige die Aufgabe erledigt."""
    from .dispatch_documents import DispatchDocument
    from .sent_documents import DocumentPdf

    spec = letter_kind(kind)
    checklist = _checklist(db, checklist.id)
    if section_signature(checklist, spec) is None:
        raise ValueError(f"{spec.label}: {spec.waiting_text}")
    order = _order(db, checklist)

    def pdf() -> DocumentPdf:
        try:
            letter = ensure_letter(db, checklist.id, kind)
            return DocumentPdf(letter_document(letter), letter.sent_document.filename, letter.sent_document)
        except NoticeStateError as e:
            raise ValueError(str(e)) from e

    after = (lambda: complete_send_tasks(db, checklist.id)) if kind == "behinderungsanzeige" else None
    return DispatchDocument(kind, checklist.id, None, f"{spec.label} zu Auftrag {order.order_number}",
                            order.project_id, pdf, after_delivery=after)


# --- Zustand für die Seite --------------------------------------------------------------------

def _letter_dict(letter: NoticeLetter, current_signature_id: int | None) -> dict:
    from .sent_documents import sent_document_to_dict

    content = json.loads(letter.content)
    return {
        "id": letter.id, "kind": letter.kind, "version_no": letter.version_no, "signature_id": letter.signature_id,
        "current": letter.signature_id == current_signature_id, "letter_date": content["letter_date"],
        "created_at_local": to_berlin(letter.created_at), "created_by_name": letter.created_by_name,
        "content_sha256": letter.content_sha256, "reservation_printed": letter.reservation_printed,
        "copy_to": content["copy_to"], "photo_count": len(content["photos"]),
        "sent_document": sent_document_to_dict(letter.sent_document),
    }


def notice_state(db: Session, checklist_id: int) -> dict:
    """Alles für die Karte "Anzeige an den Auftraggeber" der Ausfüllseite (nur Büro)."""
    from .contract_basis import contract_basis_label

    checklist = _checklist(db, checklist_id)
    order = _order(db, checklist)
    customer = _customer(order)
    participants = [_participant_info(p) for p in _participant_rows(db, order.project_id)]
    ag_email = ((customer.email or "").strip() if customer is not None else "") or None
    seen = {ag_email.lower()} if ag_email else set()
    cc = []
    for info in participants:
        if info["copy_on_notices"] and not info["archived"] and info["email"] and info["email"].lower() not in seen:
            seen.add(info["email"].lower())
            cc.append(info["email"])
    letters = _letters(db, checklist_id)
    kinds = []
    for spec in LETTER_KINDS.values():
        signature = section_signature(checklist, spec)
        seal = check_signature(checklist, signature) if signature is not None else None
        own = [l for l in letters if l.kind == spec.key]
        kinds.append({
            "kind": spec.key, "label": spec.label, "ready": signature is not None, "waiting_text": spec.waiting_text,
            "signature": None if signature is None else {
                "id": signature.id, "signer_name": signature.signer_name,
                "signed_at_local": to_berlin(signature.created_at), "content_sha256": signature.content_sha256,
            },
            "seal": seal, "blocked": seal is not None and seal["status"] != "unveraendert",
            "reservation": reservation_state(db, spec.key, order.contract_basis),
            "letters": [_letter_dict(l, signature.id if signature else None) for l in own],
            "sent": letter_was_sent(db, spec.key, checklist_id),
        })
    return {
        "checklist_id": checklist_id, "order_id": order.id, "order_number": order.order_number,
        "contract_basis": order.contract_basis, "contract_basis_label": contract_basis_label(order.contract_basis),
        "recipient": {"name": customer.name if customer is not None else order.customer_name, "email": ag_email,
                      "customer_id": customer.id if customer is not None else None},
        "cc_prefill": ", ".join(cc),
        "copies": [p for p in participants if p["copy_on_notices"]],
        "authorized": [p for p in participants if p["authorized"]],
        "kinds": kinds,
    }
