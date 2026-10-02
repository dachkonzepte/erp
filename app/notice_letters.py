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

Seit 1.8.41 (Runde 2b-3 Teil 3, Herleitung "Umsetzung 1.8.41"):
- "Beim Auftraggeber angekommen" (delivered_dispatches()) zählt nur ein gesendeter Eintrag, der nicht als
  unzustellbar vermerkt ist und -- bei einer nachgetragenen Zustellung mit Empfängerauswahl -- an den Auftraggeber
  oder einen empfangsbevollmächtigten Beteiligten ging; eine Kopie nur an Beteiligte erledigt nichts. Daran hängen
  "versendet", das Datum im Bezug der Wiederaufnahme, der Zeitstrahl und die Aufgabe "versenden" (erledigt, und
  nach "unzustellbar" ohne andere Zustellung wieder offen).
- Die Anzeige der Wiederaufnahme trägt "i. A." und den Namen des Büro-Kontos, das sie erstellt (signoff), nicht die
  Unterschrift des Abschnitts Wegfall -- die bleibt interner Beleg (Prüfsumme in der Fußzeile).
- Zeitstrahl (notice_timeline()): bekannt seit → Meldung unterschrieben → versendet, mit Abstand.
- Als gegenstandslos abgeschlossen (app/checklists.py::void_checklist()): kein neuer Brief, kein Versand; eine
  schon erstellte Fassung bleibt und lässt sich als zugestellt nachtragen.

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

from .berlin_time import berlin_now, to_berlin
from .checklist_follow_ups import complete_follow_up_tasks, reopen_follow_up_tasks, triggering_signature
from .checklist_purposes import OBSTRUCTION_PURPOSE, OBSTRUCTION_REPORT_SIGNATURE
from .checklists import VOID_STATUS, _load as _load_checklist, attachment_path, check_signature
from .models import (
    Checklist, ChecklistAttachment, Customer, DispatchAuthorization, DispatchOutcome, EmailDispatch, NoticeLetter, Order,
)
from .notice_reservations import printable_reservation, reservation_state
from .project_participants import participant_info, participant_rows

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


VOID_TEXT = "Die Anzeige ist als gegenstandslos abgeschlossen – es wird kein Brief mehr erstellt oder versendet."


def _require_not_void(checklist: Checklist) -> None:
    if checklist.status == VOID_STATUS:
        raise NoticeStateError(VOID_TEXT)


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


def copy_recipients(db: Session, project_id: int) -> list[dict]:
    """Beteiligte mit "Kopie bei Anzeigen" (ohne archivierte Kontakte) -- "Kopie an:" im Brief und Vorbelegung
    von CC."""
    return [info for info in (participant_info(p) for p in participant_rows(db, project_id))
            if info["copy_on_notices"] and not info["archived"]]


def reached_client(dispatch: EmailDispatch, outcome: DispatchOutcome | None, has_authorization: bool) -> bool:
    """Kam dieser Eintrag beim Auftraggeber an? (seit 1.8.41) Gesendet, nicht als unzustellbar vermerkt, und: per
    E-Mail (An ist immer der Auftraggeber), oder nachgetragen an den Auftraggeber, an einen empfangsbevollmächtigten
    Beteiligten (festgehaltene Vollmacht) oder ohne Empfängerauswahl (wie vor 1.8.41)."""
    from .email_dispatch import MANUAL_CHANNELS

    if dispatch.status != "gesendet" or (outcome is not None and outcome.outcome == "unzustellbar"):
        return False
    if dispatch.channel not in MANUAL_CHANNELS:
        return True
    return dispatch.delivered_to_client is not False or has_authorization


def delivered_dispatches(db: Session, kind: str, checklist_id: int) -> list[EmailDispatch]:
    """Die Einträge dieser Briefart, die beim Auftraggeber ankamen (reached_client()), ältester zuerst."""
    rows = db.scalars(select(EmailDispatch).where(
        EmailDispatch.document_type == kind, EmailDispatch.document_id == checklist_id,
        EmailDispatch.status == "gesendet").order_by(EmailDispatch.created_at, EmailDispatch.id)).all()
    if not rows:
        return []
    ids = [r.id for r in rows]
    outcomes = {o.dispatch_id: o for o in db.scalars(select(DispatchOutcome).where(DispatchOutcome.dispatch_id.in_(ids)))}
    authorized = set(db.scalars(select(DispatchAuthorization.dispatch_id).where(DispatchAuthorization.dispatch_id.in_(ids))))
    return [r for r in rows if reached_client(r, outcomes.get(r.id), r.id in authorized)]


def _delivered_on(dispatch: EmailDispatch) -> date:
    """E-Mail: Abschluss in Europe/Berlin; nachgetragene Zustellung: Zustelldatum."""
    return dispatch.delivered_on or to_berlin(dispatch.finished_at or dispatch.created_at).date()


def _sent_on(db: Session, kind: str, checklist_id: int) -> date | None:
    """Tag der ersten Zustellung dieser Briefart beim Auftraggeber (delivered_dispatches())."""
    days = [_delivered_on(d) for d in delivered_dispatches(db, kind, checklist_id)]
    return min(days) if days else None


def letter_was_sent(db: Session, kind: str, checklist_id: int) -> bool:
    """Ist diese Briefart beim Auftraggeber angekommen? (seit 1.8.41 ohne Unzustellbare und ohne reine Kopien)"""
    return bool(delivered_dispatches(db, kind, checklist_id))


def _canonical(content: dict) -> str:
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_letter_content(db: Session, checklist: Checklist, spec: LetterKind, signature: ChecklistAttachment, *,
                         version_no: int | None, letter_date: date, issuer_name: str | None = None) -> dict:
    """Alles, was im Brief steht, außer Briefpapier und Layout (eingefroren beim Erstellen). issuer_name (seit
    1.8.41): das Büro-Konto, das den Brief erstellt -- die Anzeige der Wiederaufnahme trägt "i. A." und diesen Namen
    statt der Unterschrift des Abschnitts Wegfall (signoff); "signature" bleibt als interner Bezug (Prüfsumme)."""
    from .settings import load_general_settings

    order = _order(db, checklist)
    customer = _customer(order)
    general = load_general_settings(db)
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
    signoff = None
    if spec.key == "wiederaufnahme":
        signoff = {"mode": "i_a", "name": (issuer_name or "").strip() or "System"}
    return {
        "signoff": signoff,
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


def preview_pdf(db: Session, checklist_id: int, kind: str, *, user_name: str | None = None) -> bytes:
    """Vorschau mit dem Stand von jetzt, quer "Vorschau – nicht versendet" -- nichts wird abgelegt. user_name: wer
    sie ansieht (bei der Wiederaufnahme der Name hinter "i. A.", wie beim Erstellen durch dieses Konto)."""
    from .audit import current_actor
    from .berlin_time import berlin_today

    spec = letter_kind(kind)
    checklist = _checklist(db, checklist_id)
    _require_not_void(checklist)
    signature = section_signature(checklist, spec)
    if signature is None:
        raise NoticeStateError(spec.waiting_text)
    _require_intact(checklist, signature)
    content = build_letter_content(db, checklist, spec, signature, version_no=None, letter_date=berlin_today(),
                                   issuer_name=user_name or current_actor()[1])
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
    Zwei gleichzeitige Aufrufe ergeben so eine Fassung (zusätzlich der Unique-Schlüssel je Unterschrift).

    Seit 1.8.41: an einer als gegenstandslos abgeschlossenen Anzeige nur noch die vorhandene Fassung (für eine
    nachgetragene Zustellung), keine neue (NoticeStateError). Die Wiederaufnahme trägt "i. A." user_name."""
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
    _require_not_void(checklist)
    _require_intact(checklist, signature)
    if user_id is None and user_name is None:
        user_id, user_name = current_actor()
    user_name = user_name or "System"
    signature_id = signature.id
    version_no = _next_version_no(db, checklist_id, kind)
    content = build_letter_content(db, checklist, spec, signature, version_no=version_no, letter_date=berlin_today(),
                                   issuer_name=user_name)
    canonical = _canonical(content)
    pdf = _render(db, checklist, content)

    checklist = _checklist(db, checklist_id, for_update=True)
    signature = section_signature(checklist, spec)
    if signature is None or signature.id != signature_id:
        db.rollback()
        raise NoticeStateError("Die Unterschrift hat sich inzwischen geändert – bitte die Seite neu laden.")
    if checklist.status == VOID_STATUS:
        db.rollback()
        raise NoticeStateError(VOID_TEXT)
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
    -- die Zeile sagt es dann. Committet nicht (der Aufrufer). Seit 1.8.41 über
    app/email_dispatch.py::freeze_authorization() (gemeinsam mit der nachgetragenen Zustellung)."""
    from .email_dispatch import freeze_authorization

    recipients = {a.strip().lower() for a in f"{dispatch.to_recipients or ''},{dispatch.cc_recipients or ''}".split(",")
                  if a.strip()}
    for p in participant_rows(db, project_id):
        info = participant_info(p)
        if not info["authorized"] or not info["email"] or info["email"].lower() not in recipients:
            continue
        freeze_authorization(db, dispatch, p, recipient_email=info["email"], user_id=user_id, user_name=user_name)
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
    _require_not_void(checklist)  # seit 1.8.41: gegenstandslos -- nichts geht mehr hinaus
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
    """Setzt die offene Aufgabe "Behinderungsanzeige versenden" der Checkliste auf die erste "erledigt"-Spalte
    (seit 1.8.41 über app/checklist_follow_ups.py::complete_follow_up_tasks()). Ein Fehler dort macht den Versand
    nicht ungeschehen. Liefert die Zahl der erledigten Aufgaben."""
    return complete_follow_up_tasks(db, checklist_id, SEND_FOLLOW_UP_KEY)


def dispatch_document_for(db: Session, checklist: Checklist, kind: str):
    """Eintrag für app/dispatch_documents.py (Zustellung nachtragen): die Fassung zur aktuellen Unterschrift
    (beim ersten Mal erstellt, nach "gegenstandslos" nur eine schon erstellte), nach dem Eintrag der
    Behinderungsanzeige die Aufgabe erledigt -- seit 1.8.41 nur, wenn die Zustellung beim Auftraggeber ankam
    (reached_client(): eine Kopie nur an Beteiligte erledigt sie nicht)."""
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

    def after(dispatch: EmailDispatch) -> None:
        authorized = db.scalar(select(DispatchAuthorization.id).where(DispatchAuthorization.dispatch_id == dispatch.id)
                               .limit(1)) is not None
        if reached_client(dispatch, None, authorized):
            complete_send_tasks(db, checklist.id)

    return DispatchDocument(kind, checklist.id, None, f"{spec.label} zu Auftrag {order.order_number}",
                            order.project_id, pdf, after_delivery=after if kind == "behinderungsanzeige" else None)


def after_dispatch_outcome(db: Session, dispatch: EmailDispatch, outcome: DispatchOutcome) -> int:
    """Nachlauf eines Versandergebnisses der Behinderungsanzeige (seit 1.8.41, app/dispatch_documents.py::
    after_outcome()). Festlegung: "unzustellbar" und auf keinem anderen Weg beim Auftraggeber angekommen -- die
    Aufgabe "Behinderungsanzeige versenden" ist wieder offen (die Anzeige muss noch hinaus). Nicht an einer
    gegenstandslosen Anzeige. Liefert die Zahl der wieder geöffneten Aufgaben."""
    if outcome.outcome != "unzustellbar" or dispatch.document_type != "behinderungsanzeige":
        return 0
    checklist = db.get(Checklist, dispatch.document_id)
    if checklist is None or checklist.status == VOID_STATUS:
        return 0
    if letter_was_sent(db, "behinderungsanzeige", checklist.id):
        return 0
    return reopen_follow_up_tasks(db, checklist.id, SEND_FOLLOW_UP_KEY)


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


def gap_text(start: datetime, end: datetime, *, date_only: bool = False) -> dict:
    """Abstand zweier Zeitpunkte für den Zeitstrahl: unter einem Tag in Stunden ("unter 1 Std.", "5 Std."), sonst in
    Tagen und Stunden ("2 Tage 3 Std."); kennt ein Zeitpunkt nur den Tag, in Kalendertagen ("am selben Tag", "1 Tag").
    Rückwärts (Reihenfolge stimmt nicht) mit "vorher"."""
    if date_only:
        days = (end.date() - start.date()).days
        text = "am selben Tag" if days == 0 else f"{abs(days)} {'Tag' if abs(days) == 1 else 'Tage'}"
        return {"text": text + (" vorher" if days < 0 else ""), "minutes": None, "days": days, "negative": days < 0}
    minutes = int((end - start).total_seconds() // 60)
    total = abs(minutes)
    if total < 60:
        text = "unter 1 Std."
    elif total < 24 * 60:
        text = f"{total // 60} Std."
    else:
        days, hours = divmod(total // 60, 24)
        text = f"{days} {'Tag' if days == 1 else 'Tage'}" + (f" {hours} Std." if hours else "")
    return {"text": text + (" vorher" if minutes < 0 else ""), "minutes": minutes, "days": None, "negative": minutes < 0}


def notice_timeline(db: Session, checklist: Checklist) -> list[dict]:
    """Zeitstrahl der Behinderungsanzeige (seit 1.8.41): "Bekannt seit" (Antwort der Meldung, Ortszeit) → "Meldung
    unterschrieben" (gültige Unterschrift des Meldenden) → "Versendet" (erste Zustellung beim Auftraggeber: E-Mail
    mit Uhrzeit, nachgetragen nur mit Tag), je mit Abstand zum vorigen bekannten Schritt. Fehlt "versendet", steht
    dort, seit wann die Meldung wartet (bis jetzt, Europe/Berlin)."""
    from .email_dispatch import CHANNELS, MANUAL_CHANNELS

    known_field = next((f for f in checklist.template_version.fields if f.field_key == B + "bekannt_seit"), None)
    answer = next((a for a in checklist.answers if known_field is not None and a.template_field_id == known_field.id), None)
    known_at = answer.value_datetime if answer is not None else None
    report = triggering_signature(checklist, OBSTRUCTION_REPORT_SIGNATURE)
    report_at = to_berlin(report.created_at) if report is not None and report.created_at else None
    delivered = delivered_dispatches(db, "behinderungsanzeige", checklist.id)
    first = min(delivered, key=_delivered_on, default=None) if delivered else None
    sent_at, sent_date_only, channel = None, False, None
    if first is not None:
        channel = CHANNELS.get(first.channel, first.channel)
        if first.channel in MANUAL_CHANNELS:
            sent_at, sent_date_only = datetime.combine(first.delivered_on, datetime.min.time()), True
        else:
            sent_at = to_berlin(first.finished_at or first.created_at)
    steps = [
        {"key": "bekannt_seit", "label": "Bekannt seit", "at": known_at, "date_only": False},
        {"key": "meldung", "label": "Meldung unterschrieben", "at": report_at, "date_only": False},
        {"key": "versendet", "label": "Versendet" if not sent_date_only else "Zugestellt", "at": sent_at,
         "date_only": sent_date_only, "channel": channel},
    ]
    previous = None
    for step in steps:
        step["gap"] = None
        if step["at"] is not None and previous is not None:
            step["gap"] = gap_text(previous["at"], step["at"], date_only=step["date_only"] or previous["date_only"])
        if step["at"] is not None:
            previous = step
    if sent_at is None and checklist.status != VOID_STATUS and previous is not None:
        steps[-1]["waiting"] = gap_text(previous["at"], berlin_now().replace(tzinfo=None))
    for step in steps:
        at = step.pop("at")
        step["at_local"] = None if at is None else (at.strftime("%Y-%m-%d") if step["date_only"] else at.strftime("%Y-%m-%dT%H:%M"))
    return steps


def _kind_status(db: Session, kind: str, checklist_id: int, ready: bool) -> str:
    """Stand je Briefart (seit 1.8.41): versendet (beim Auftraggeber angekommen) | unzustellbar (gesendet, aber alles
    als unzustellbar vermerkt bzw. nur als Kopie) | bereit | wartet."""
    if letter_was_sent(db, kind, checklist_id):
        return "versendet"
    undeliverable = db.scalar(select(DispatchOutcome.id).join(EmailDispatch, EmailDispatch.id == DispatchOutcome.dispatch_id)
                              .where(EmailDispatch.document_type == kind, EmailDispatch.document_id == checklist_id,
                                     DispatchOutcome.outcome == "unzustellbar").limit(1))
    if undeliverable is not None:
        return "unzustellbar"
    return "bereit" if ready else "wartet"


def notice_state(db: Session, checklist_id: int) -> dict:
    """Alles für die Karte "Anzeige an den Auftraggeber" der Ausfüllseite (nur Büro)."""
    from .contract_basis import contract_basis_label

    checklist = _checklist(db, checklist_id)
    order = _order(db, checklist)
    customer = _customer(order)
    participants = [participant_info(p) for p in participant_rows(db, order.project_id)]
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
            "status": _kind_status(db, spec.key, checklist_id, signature is not None),
            "signoff_text": ("Der Brief trägt „i. A.“ und den Namen des Büro-Kontos, das ihn erstellt – die "
                             "Unterschrift im Abschnitt „Wegfall“ bleibt interner Beleg.") if spec.key == "wiederaufnahme" else None,
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
        "timeline": notice_timeline(db, checklist),
        # seit 1.8.41: als gegenstandslos abgeschlossen -- die Karte zeigt nur noch Stand und Verlauf
        "voided": checklist.status == VOID_STATUS,
    }
