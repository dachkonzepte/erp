"""Vertrag festschreiben und versenden (seit 1.8.33, Stufe 2b, Runde 2b-1b Teil 2, Punkte 1–3).

Festschreiben (freeze_contract()): der Inhalt des Entwurfs -- Vorlagentext mit eingesetzten
Platzhaltern, Verbraucher-Merkmal, Fallfelder, die Werte aller Platzhalter
(app/contract_templates.py::contract_content()) -- wird als kanonisches JSON eingefroren
(OrderContractVersion.frozen_content, Prüfsumme content_sha256), das PDF samt Anlage einmal gerendert
und unveränderlich in der Ablage abgelegt (app/sent_documents.py, Art "vertrag", mit SHA-256).
Danach ist der Entwurf gesperrt; Änderungen nur als neue Fassung (start_new_version()), die alte
bleibt sichtbar und wird beim nächsten Festschreiben als abgelöst markiert. Nie neu gerendert: wer die
Fassung abruft, versendet oder zustellt, bekommt die abgelegten Bytes. Festgeschrieben wird nur eine
rechtlich geprüfte Vorlage -- eine Fassung mit "Entwurf – Vertragstext nicht geprüft" auf jeder
Seite gehört nicht zum Kunden.

Anlage (Punkt 2): die zuletzt versendete Fassung des Angebots aus der Ablage (ein Versand mit Status
"gesendet", E-Mail oder nachgetragene Zustellung). Ob der heutige Stand davon abweicht, entscheidet
der Text beider PDFs (pdf_plain_text()): das Angebot wird dafür neu gerendert und mit der abgelegten
Fassung verglichen. Gleich -> sie wird ohne Rückfrage angehängt. Weicht er ab, gibt es keine
versendete Fassung oder ist sie in der Ablage beschädigt, wählt das Büro bewusst ("versendet" mit der
ID der Fassung oder "aktuell"); ohne Wahl wird nicht festgeschrieben -- nie still.

Versand (Punkt 3): send_contract_email() über dispatch_email() (Regel 21), An vorbelegt mit dem
Auftraggeber, immer die festgeschriebene Fassung aus der Ablage (archived_document, keine zweite
Datei). Eine Fassung, die nicht mehr zum Auftrag passt (version_differences(): Vertragsgrundlage,
Verbraucher-Merkmal oder der Wert eines Platzhalters, den die Vorlage nutzt, hat sich seit dem
Festschreiben geändert), wird weder versendet noch zugestellt -- dann eine neue Fassung festschreiben.

Unterschrift (seit 1.8.34, app/contract_signatures.py): status "unterschrieben". Danach keine neue Fassung
mehr; die unterschriebene Fassung bleibt abrufbar und versendbar, auch wenn sich der Auftrag später ändert --
die Abweichungen zeigt die Karte nur noch als Hinweis. Seit 1.8.35 gehen Versand und Zustellung dann mit der
unterschriebenen Abschrift hinaus (Fassung + Unterschriftsblatt bzw. Scan, deliverable_document()), nicht
mehr mit der Fassung allein.

Rollenlos wie jede Geschäftslogik; wer was darf, entscheidet app/routers/contract_templates.py.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime

import pypdfium2 as pdfium
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .berlin_time import berlin_today, to_berlin
from .contract_basis import contract_basis_label
from .contract_templates import (
    CASE_FIELDS, CONTRACT_PLACEHOLDERS, contract_content, contract_placeholder_values, contract_state as draft_state,
    get_order_contract, order_customer_is_consumer,
)
from .models import EmailDispatch, Order, OrderContract, OrderContractVersion, SentDocument
from .sent_documents import ArchiveFileError, read_sent_document, sent_document_to_dict, store_sent_document

CONTRACT_ENTITY_TYPE = "Vertrag"  # Änderungshistorie (app/audit.py)
# Status mit einer gültigen Fassung: festgeschrieben oder (seit 1.8.34) unterschrieben.
FROZEN_STATUSES = ("festgeschrieben", "unterschrieben")

DEFAULT_CONTRACT_EMAIL_SUBJECT = "Vertrag zu Auftrag {auftragsnummer}"
DEFAULT_CONTRACT_EMAIL_BODY = (
    "Sehr geehrte Damen und Herren,\n\n"
    "anbei erhalten Sie den Vertrag zu Auftrag {auftragsnummer} (Fassung {fassung}) mit unserem Angebot "
    "als Anlage.\n\n"
    "Mit freundlichen Grüßen"
)


class ContractStateError(ValueError):
    """Der Vertrag ist nicht in dem Zustand, den die Aktion braucht -- Router: 409."""


# --- Hilfen -----------------------------------------------------------------------------------------

def canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def pdf_plain_text(pdf: bytes) -> str:
    """Der Text aller Seiten, Leerraum vereinheitlicht -- für den Vergleich "weicht der heutige Stand
    des Angebots von der versendeten Fassung ab?" (zwei Renderläufe derselben Daten ergeben denselben
    Text, die Bytes unterscheiden sich schon durch Zeitstempel und Kennungen im PDF)."""
    doc = pdfium.PdfDocument(pdf)
    try:
        pages = []
        for index in range(len(doc)):
            page = doc[index]
            textpage = page.get_textpage()
            try:
                pages.append(" ".join(textpage.get_text_range(0, textpage.count_chars()).split()))
            finally:
                textpage.close()
                page.close()
        return "\f".join(pages)
    finally:
        doc.close()


def contract_document_number(order_number: str, version_no: int) -> str:
    return f"{order_number} · Fassung {version_no}"


def contract_filename(order_number: str, version_no: int) -> str:
    return f"Vertrag_{order_number}_Fassung_{version_no}.pdf".replace("/", "-").replace("\\", "-")


def _locked_contract(db: Session, order_id: int) -> OrderContract | None:
    """Vertrag mit Zeilensperre (PostgreSQL; SQLite ignoriert sie), frisch aus der Datenbank."""
    return db.scalar(
        select(OrderContract).where(OrderContract.order_id == order_id)
        .with_for_update(of=OrderContract).execution_options(populate_existing=True)
    )


def current_version(contract: OrderContract | None) -> OrderContractVersion | None:
    """Die jüngste Fassung (die einzige ohne superseded_at)."""
    if contract is None or not contract.versions:
        return None
    return max(contract.versions, key=lambda v: v.version_no)


def frozen_content(version: OrderContractVersion) -> dict:
    return json.loads(version.frozen_content)


# --- Anlage (Punkt 2) -------------------------------------------------------------------------------

def last_sent_quote_document(db: Session, quote_id: int | None) -> SentDocument | None:
    """Die zuletzt versendete Fassung des Angebots: das jüngste abgelegte PDF, auf das ein Versand mit
    Status "gesendet" verweist (E-Mail oder nachgetragene Zustellung; Belege zählen nicht, sie hängen
    an receipt_document_id). Fehlgeschlagene und hängende Versände zählen nicht -- ob ein hängender
    hinausging, klärt das Büro im Versandprotokoll."""
    if quote_id is None:
        return None
    sent = select(EmailDispatch.id).where(
        EmailDispatch.sent_document_id == SentDocument.id, EmailDispatch.status == "gesendet",
    ).exists()
    return db.scalar(
        select(SentDocument)
        .where(SentDocument.document_type == "angebot", SentDocument.document_id == quote_id, sent)
        .order_by(SentDocument.created_at.desc(), SentDocument.id.desc())
        .limit(1)
    )


def _sending_of(db: Session, doc: SentDocument) -> tuple[date, str]:
    """Wann und wie die Fassung hinausging (der erste Versand mit Status "gesendet")."""
    dispatch = db.scalar(
        select(EmailDispatch).where(EmailDispatch.sent_document_id == doc.id, EmailDispatch.status == "gesendet")
        .order_by(EmailDispatch.id).limit(1)
    )
    if dispatch is None:
        return to_berlin(doc.created_at).date(), "versendet"
    if dispatch.delivered_on is not None:
        from .email_dispatch import MANUAL_CHANNELS
        return dispatch.delivered_on, MANUAL_CHANNELS.get(dispatch.channel, dispatch.channel)
    return to_berlin(dispatch.finished_at or dispatch.created_at).date(), f"per E-Mail an {dispatch.to_recipients}"


@dataclass
class AttachmentSituation:
    quote_available: bool
    last: SentDocument | None
    last_bytes: bytes | None
    last_problem: str | None
    current_bytes: bytes | None
    matches: bool | None  # None: nicht vergleichbar (keine oder beschädigte Fassung, kein Angebot)


def attachment_situation(db: Session, order: Order) -> AttachmentSituation:
    """Rendert den heutigen Stand des Angebots und vergleicht ihn mit der zuletzt versendeten Fassung."""
    from .projects import load_quote
    from .quote_framed_pdf import build_quote_framed_pdf

    quote = load_quote(db, order.source_quote_id)
    current = build_quote_framed_pdf(db, quote) if quote is not None else None
    last = last_sent_quote_document(db, order.source_quote_id)
    last_bytes = problem = None
    if last is not None:
        try:
            last_bytes = read_sent_document(last)
        except ArchiveFileError as e:
            problem = str(e)
    matches = None
    if last_bytes is not None and current is not None:
        matches = pdf_plain_text(last_bytes) == pdf_plain_text(current)
    return AttachmentSituation(quote is not None, last, last_bytes, problem, current, matches)


def attachment_options(db: Session, order: Order) -> dict:
    """Für die Auftragsseite: welche Anlage, und ob das Büro wählen muss."""
    situation = attachment_situation(db, order)
    last = None
    if situation.last is not None:
        sent_on, how = _sending_of(db, situation.last)
        last = {
            "sent_document_id": situation.last.id, "filename": situation.last.filename,
            "sha256": situation.last.sha256, "size_bytes": situation.last.size_bytes,
            "sent_on": sent_on, "how": how, "intact": situation.last_bytes is not None,
            "problem": situation.last_problem,
        }
    automatic = situation.last_bytes is not None and situation.matches is True
    return {
        "quote_number": order.quote_number_snapshot,
        "quote_available": situation.quote_available,
        "last_sent": last,
        "matches_current": situation.matches,
        "choice_required": not automatic,
        "default": "versendet" if automatic else None,
    }


def _choose_attachment(
    order: Order, situation: AttachmentSituation, attachment: str | None, attachment_document_id: int | None,
) -> tuple[str, bytes, SentDocument | None]:
    quote_number = order.quote_number_snapshot
    last = situation.last
    if attachment is None:
        if situation.last_bytes is not None and situation.matches:
            return "versendet", situation.last_bytes, last
        if last is None:
            reason = f"Das Angebot {quote_number} wurde nie versendet"
        elif situation.last_bytes is None:
            reason = f"Die versendete Fassung des Angebots {quote_number} ist in der Ablage nicht mehr unversehrt ({situation.last_problem})"
        else:
            reason = f"Der heutige Stand des Angebots {quote_number} weicht von der versendeten Fassung ab"
        raise ContractStateError(f"{reason} – bitte bewusst wählen, welche Fassung als Anlage festgeschrieben wird.")
    if attachment == "versendet":
        if last is None:
            raise ContractStateError(f"Vom Angebot {quote_number} gibt es keine versendete Fassung.")
        if attachment_document_id != last.id:
            raise ContractStateError(
                f"Inzwischen ist eine andere Fassung des Angebots {quote_number} die zuletzt versendete. "
                "Bitte die Seite neu laden und erneut wählen."
            )
        if situation.last_bytes is None:
            raise ContractStateError(f"Die versendete Fassung ist in der Ablage nicht mehr unversehrt: {situation.last_problem}")
        return "versendet", situation.last_bytes, last
    if attachment == "aktuell":
        if situation.current_bytes is None:
            raise ContractStateError(f"Das Angebot {quote_number} ist nicht mehr vorhanden.")
        return "aktuell", situation.current_bytes, None
    raise ValueError("Unbekannte Anlage.")


# --- Festschreiben (Punkt 1) ------------------------------------------------------------------------

def freeze_contract(
    db: Session, order: Order, *, attachment: str | None = None, attachment_document_id: int | None = None,
    user_id: int | None = None, user_name: str | None = None,
) -> OrderContractVersion:
    """Schreibt den Entwurf als neue Fassung fest. Wirft LookupError (kein Vertrag), ContractStateError
    (kein Entwurf, keine oder ungeprüfte Vorlage, Anlage nicht gewählt oder überholt, seit 1.8.50: die Vorlage nutzt
    {gewaehrleistung} und die Dauer ist am Auftrag nicht festgelegt). Sperrt Vertrag und dann Auftrag (wie das Festlegen
    der Dauer, app/warranty.py) und liest den Auftrag danach frisch -- eine gleichzeitig festgelegte Dauer steht so im
    Vertrag, nicht der beim Laden gelesene Stand."""
    from .audit import record_audit_entry
    from .contract_pdf import render_contract_pdf

    user_name = user_name or "System"
    contract = _locked_contract(db, order.id)
    if contract is None:
        raise LookupError("Zu diesem Auftrag gibt es keinen Vertragsentwurf.")
    if contract.status == "unterschrieben":
        raise ContractStateError("Der Vertrag ist unterschrieben – es gibt keine neue Fassung mehr.")
    if contract.status != "entwurf":
        raise ContractStateError("Der Vertrag ist bereits festgeschrieben – Änderungen nur als neue Fassung.")
    from .acceptances import lock_order
    from .warranty import CONTRACT_PLACEHOLDER as WARRANTY_PLACEHOLDER

    lock_order(db, order.id)
    db.refresh(order)
    try:
        content = contract_content(db, order, contract)
    except ValueError as e:
        raise ContractStateError(str(e)) from e
    if not content["template"]["reviewed"]:
        raise ContractStateError(
            f"Die Vertragsvorlage für „{content['basis_label']}“ ist nicht rechtlich geprüft (Einstellungen → "
            "Vertragsvorlagen). Festgeschrieben wird nur ein geprüfter Vertragstext."
        )
    if WARRANTY_PLACEHOLDER in content["used_placeholders"] and (order.warranty_months is None
                                                                  or order.warranty_days is None):
        raise ContractStateError(
            "Die Vertragsvorlage nutzt {gewaehrleistung}, die Gewährleistungsdauer ist am Auftrag aber nicht festgelegt "
            "– bitte zuerst in der Karte „Gewährleistung“ festlegen."
        )
    situation = attachment_situation(db, order)
    kind, attachment_bytes, attachment_doc = _choose_attachment(order, situation, attachment, attachment_document_id)

    # Zuerst den Entwurf belegen (bedingtes UPDATE): von zwei gleichzeitigen Klicks schreibt genau
    # einer fest; der Unique-Schlüssel (contract_id, version_no) fängt den Rest.
    now = datetime.utcnow()
    claimed = db.execute(
        update(OrderContract).where(OrderContract.id == contract.id, OrderContract.status == "entwurf")
        .values(status="festgeschrieben", updated_at=now, updated_by_name=user_name)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise ContractStateError("Diesen Entwurf hat inzwischen jemand anderes festgeschrieben.")

    version_no = (db.scalar(select(func.max(OrderContractVersion.version_no))
                            .where(OrderContractVersion.contract_id == contract.id)) or 0) + 1
    stand = berlin_today()
    sent_on = _sending_of(db, attachment_doc) if attachment_doc is not None else None
    content.update({
        "contract_id": contract.id,
        "version_no": version_no,
        "stand": stand.isoformat(),
        "attachment": {
            "kind": kind,
            "quote_id": order.source_quote_id,
            "quote_number": order.quote_number_snapshot,
            "sha256": hashlib.sha256(attachment_bytes).hexdigest(),
            "sent_document_id": attachment_doc.id if attachment_doc is not None else None,
            "sent_on": sent_on[0].isoformat() if sent_on else None,
            "sent_how": sent_on[1] if sent_on else None,
        },
    })
    frozen = canonical_json(content)
    try:
        pdf = render_contract_pdf(db, content, attachment_pdf=attachment_bytes, version_label=str(version_no), stand=stand)
        document = store_sent_document(
            db, document_type="vertrag", document_id=contract.id,
            document_number=contract_document_number(order.order_number, version_no),
            filename=contract_filename(order.order_number, version_no), content=pdf,
            user_id=user_id, user_name=user_name,
        )
        for older in db.scalars(select(OrderContractVersion).where(
            OrderContractVersion.contract_id == contract.id, OrderContractVersion.superseded_at.is_(None),
        )).all():
            older.superseded_at = now
        version = OrderContractVersion(
            contract_id=contract.id, version_no=version_no, basis_key=content["basis_key"],
            is_consumer=content["is_consumer"], frozen_content=frozen, content_sha256=sha256_text(frozen),
            sent_document_id=document.id, attachment_kind=kind,
            attachment_document_id=attachment_doc.id if attachment_doc is not None else None,
            created_at=now, created_by_user_id=user_id, created_by_name=user_name,
        )
        db.add(version)
        record_audit_entry(
            db, action="geändert", entity_type=CONTRACT_ENTITY_TYPE, entity_id=contract.id,
            entity_label=f"Vertrag zu Auftrag {order.order_number}", project_id=order.project_id,
            field_name="status", field_label="Vertrag festgeschrieben", old_value="Entwurf",
            new_value=f"Fassung {version_no} · PDF-Prüfsumme {document.sha256}",
            actor_user_id=user_id, actor_name=user_name,
        )
        db.commit()
    except Exception:
        # Eine schon geschriebene Datei bleibt ohne Eintrag liegen -- die Ablage löscht nie.
        db.rollback()
        raise
    db.refresh(version)
    return version


def start_new_version(db: Session, order: Order, *, user_id: int | None = None, user_name: str | None = None) -> OrderContract:
    """Macht aus dem festgeschriebenen Vertrag wieder einen Entwurf (mit den Fallfeldern der letzten
    Fassung). Die festgeschriebenen Fassungen bleiben; die bisher gültige wird abgelöst, sobald die
    neue festgeschrieben ist."""
    from .audit import record_audit_entry

    user_name = user_name or "System"
    contract = _locked_contract(db, order.id)
    if contract is None:
        raise LookupError("Zu diesem Auftrag gibt es keinen Vertrag.")
    if contract.status == "unterschrieben":
        raise ContractStateError(
            "Der Vertrag ist unterschrieben – eine neue Fassung gibt es danach nicht. Änderungen am Auftrag "
            "(z. B. Nachträge) lassen den unterschriebenen Vertrag gültig."
        )
    if contract.status != "festgeschrieben":
        raise ContractStateError("Eine neue Fassung gibt es nur zu einem festgeschriebenen Vertrag.")
    claimed = db.execute(
        update(OrderContract).where(OrderContract.id == contract.id, OrderContract.status == "festgeschrieben")
        .values(status="entwurf", updated_at=datetime.utcnow(), updated_by_name=user_name)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise ContractStateError("Der Vertrag wurde inzwischen geändert. Bitte die Seite neu laden.")
    latest = current_version(contract)
    record_audit_entry(
        db, action="geändert", entity_type=CONTRACT_ENTITY_TYPE, entity_id=contract.id,
        entity_label=f"Vertrag zu Auftrag {order.order_number}", project_id=order.project_id,
        field_name="status", field_label="Neue Fassung begonnen",
        old_value=f"Fassung {latest.version_no} festgeschrieben" if latest else "festgeschrieben", new_value="Entwurf",
        actor_user_id=user_id, actor_name=user_name,
    )
    db.commit()
    db.refresh(contract)
    return contract


# --- Passt die Fassung noch zum Auftrag? -----------------------------------------------------------

def _short(value: str, limit: int = 80) -> str:
    value = " ".join(str(value or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


_CASE_PLACEHOLDERS = {ph: label for ph, label in CASE_FIELDS.values()}
_PLACEHOLDER_LABELS = {
    ph: _CASE_PLACEHOLDERS.get(ph) or desc.split(" (")[0].split(",")[0] for ph, desc in CONTRACT_PLACEHOLDERS
}


def version_differences(db: Session, order: Order, version: OrderContractVersion) -> list[str]:
    """Was sich seit dem Festschreiben am Auftrag geändert hat und in der Fassung anders steht: die
    Vertragsgrundlage, das Verbraucher-Merkmal des Kunden (entscheidet über die Verbraucher-Abschnitte)
    und der Wert jedes Platzhalters, den die Vorlage nutzt. Eine Änderung an der Vorlage selbst gehört
    nicht dazu -- vereinbart ist der festgeschriebene Text."""
    content = frozen_content(version)
    differences = []
    if order.contract_basis != version.basis_key:
        differences.append(
            f"Vertragsgrundlage: festgeschrieben „{contract_basis_label(version.basis_key)}“, am Auftrag jetzt "
            f"„{contract_basis_label(order.contract_basis)}“"
        )
    consumer_now = order_customer_is_consumer(order)
    if consumer_now != version.is_consumer:
        yes_no = lambda b: "Verbraucher" if b else "kein Verbraucher"  # noqa: E731
        differences.append(f"Kunde: festgeschrieben {yes_no(version.is_consumer)}, jetzt {yes_no(consumer_now)}")
    current = contract_placeholder_values(db, order, get_order_contract(db, order.id))
    for placeholder in content["used_placeholders"]:
        old, new = content["placeholders"].get(placeholder, ""), current.get(placeholder, "")
        if old != new:
            differences.append(
                f"{_PLACEHOLDER_LABELS.get(placeholder, placeholder)}: festgeschrieben „{_short(old)}“, jetzt „{_short(new)}“"
            )
    return differences


# --- Anzeige ----------------------------------------------------------------------------------------

def version_to_dict(version: OrderContractVersion) -> dict:
    from .contract_pdf import attachment_line
    from .email_sending import MAX_ATTACHMENT_BYTES

    content = frozen_content(version)
    return {
        "id": version.id, "version_no": version.version_no, "basis_key": version.basis_key,
        "basis_label": contract_basis_label(version.basis_key), "is_consumer": version.is_consumer,
        "content_sha256": version.content_sha256, "document": sent_document_to_dict(version.sent_document),
        "attachment_kind": version.attachment_kind, "attachment_label": attachment_line(content),
        "case_fields": content.get("case_fields") or {},
        "created_at_local": to_berlin(version.created_at), "created_by_name": version.created_by_name,
        "superseded_at_local": to_berlin(version.superseded_at), "current": version.superseded_at is None,
        "too_large": version.sent_document.size_bytes > MAX_ATTACHMENT_BYTES,
        "checkboxes": checkbox_sections(content),
    }


def checkbox_sections(content: dict) -> list[dict]:
    """Die Ankreuzfelder einer Fassung (seit 1.8.34): Abschnitte mit Ankreuzfeld aus dem eingefrorenen
    Inhalt, mit Schlüssel, Überschrift, Text und dem Kennzeichen "vorzeitiger Beginn" (Fassungen von vor
    1.8.34 haben es nicht: dann falsch)."""
    return [
        {"key": s["key"], "heading": s["heading"], "text": s["text"], "consumer_only": bool(s.get("consumer_only")),
         "early_start": bool(s.get("early_start"))}
        for s in content.get("sections", []) if s.get("with_checkbox")
    ]


def contract_state(db: Session, order: Order) -> dict:
    """Die Karte "Vertrag" der Auftragsseite: Entwurfsstand (app/contract_templates.py) plus Fassungen,
    bei einem festgeschriebenen oder unterschriebenen Vertrag die Abweichungen der gültigen Fassung, der
    Empfänger und (seit 1.8.34) die Unterschrift samt Widerrufsfrist."""
    from .contract_signatures import signature_to_dict
    from .orders import get_order_recipient_email

    state = draft_state(db, order)
    contract = get_order_contract(db, order.id)
    if contract is not None:
        versions = sorted(contract.versions, key=lambda v: v.version_no, reverse=True)
        latest = versions[0] if versions else None
        state["contract"]["versions"] = [version_to_dict(v) for v in versions]
        state["contract"]["differences"] = (
            version_differences(db, order, latest) if contract.status in FROZEN_STATUSES and latest else []
        )
        state["contract"]["recipient_email"] = get_order_recipient_email(order)
        state["contract"]["signature"] = signature_to_dict(contract.signature) if contract.signature else None
    return state


def frozen_pdf(contract: OrderContract) -> tuple[bytes, OrderContractVersion]:
    """Die abgelegten Bytes der gültigen Fassung -- nur mit stimmender Prüfsumme (ArchiveFileError)."""
    version = current_version(contract)
    if contract.status not in FROZEN_STATUSES or version is None:
        raise ContractStateError("Der Vertrag ist nicht festgeschrieben.")
    return read_sent_document(version.sent_document), version


def deliverable_version(db: Session, order: Order, contract: OrderContract | None) -> OrderContractVersion:
    """Die Fassung, die versendet oder zugestellt werden darf: festgeschrieben und passend zum Auftrag --
    oder (seit 1.8.34) unterschrieben: dann gilt sie, auch wenn sich der Auftrag seither geändert hat."""
    if contract is None:
        raise ContractStateError("Zu diesem Auftrag gibt es keinen Vertrag.")
    version = current_version(contract)
    if contract.status not in FROZEN_STATUSES or version is None:
        raise ContractStateError("Versendet wird nur ein festgeschriebener Vertrag – bitte zuerst festschreiben.")
    if contract.status == "unterschrieben":
        return version
    differences = version_differences(db, order, version)
    if differences:
        raise ContractStateError(
            f"Fassung {version.version_no} passt nicht mehr zum Auftrag ({'; '.join(differences)}). "
            "Bitte eine neue Fassung festschreiben."
        )
    return version


def deliverable_document(
    db: Session, order: Order, contract: OrderContract | None, *, user_id: int | None = None, user_name: str | None = None,
) -> tuple[OrderContractVersion, SentDocument]:
    """Was Versand und Zustellung hinausgeben: die festgeschriebene Fassung -- nach der Unterschrift (seit
    1.8.35) die unterschriebene Abschrift (bei einer Unterschrift von vor 1.8.35 hier einmal nachgeholt,
    committet). Wirft ContractStateError."""
    version = deliverable_version(db, order, contract)
    if contract.status != "unterschrieben":
        return version, version.sent_document
    from .contract_signatures import ensure_signed_copy

    return version, ensure_signed_copy(db, order, contract, user_id=user_id, user_name=user_name)


# --- Versand (Punkt 3) ------------------------------------------------------------------------------

def send_contract_email(
    db: Session, order: Order, *, to_email: str | None = None, cc_email: str | None = None,
    dispatch_key: str | None = None, user=None,
):
    """Versendet die gültige festgeschriebene Fassung, nach der Unterschrift die unterschriebene Abschrift
    (Regel 21: über dispatch_email(), das PDF liegt schon in der Ablage und wird nur verwiesen). An:
    vorbelegt mit dem Auftraggeber (aktuelle Kunden-E-Mail wie bei Angebot und Auftrag). Wirft
    ContractStateError (Zustand, Router 409), ValueError (Eingabe/Versand, 400), DispatchConflict (409)."""
    from .document_email_templates import get_email_template
    from .email_dispatch import actor_of, dispatch_email, new_dispatch_key
    from .orders import get_order_recipient_email
    from .placeholders import apply_placeholders

    user_id, user_name = actor_of(user)
    contract = get_order_contract(db, order.id)
    deliverable_version(db, order, contract)  # Zustand zuerst (409), vor dem Empfänger und dem Nachholen der Abschrift
    recipient = (to_email or "").strip() or get_order_recipient_email(order)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")
    version, document = deliverable_document(db, order, contract, user_id=user_id, user_name=user_name)
    try:
        pdf = read_sent_document(document)
    except ArchiveFileError as e:
        what = "unterschriebene Abschrift" if document.id != version.sent_document_id else "festgeschriebene Fassung"
        raise ContractStateError(
            f"Die {what} in der Ablage ist nicht mehr unversehrt: {e} Es wurde nichts versendet."
        ) from e
    placeholders = {
        "{auftragsnummer}": order.order_number, "{kundenname}": order.customer_name,
        "{fassung}": str(version.version_no), "{vertragsgrundlage}": contract_basis_label(version.basis_key),
    }
    template = get_email_template(db, "contract")
    subject = apply_placeholders((template.subject_template if template else None) or DEFAULT_CONTRACT_EMAIL_SUBJECT, placeholders)
    body = apply_placeholders((template.body_template if template else None) or DEFAULT_CONTRACT_EMAIL_BODY, placeholders)
    return dispatch_email(
        db, dispatch_key=dispatch_key or new_dispatch_key("vertrag"), document_type="vertrag",
        document_id=contract.id, document_number=document.document_number, to=recipient, cc=cc_email,
        subject=subject, body_text=body, attachment_bytes=pdf, attachment_filename=document.filename,
        archived_document=document, user_id=user_id, user_name=user_name,
    )
