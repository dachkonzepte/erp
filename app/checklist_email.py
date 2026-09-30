"""Checkliste per E-Mail versenden (seit 1.8.20, Stufe 2, Runde 2a-3b).

Nur abgeschlossene Checklisten; über app/email_dispatch.py wie jedes andere Dokument (Protokoll,
Ablage, Sperre gegen Doppelversand, mehrere Empfänger/CC, Regel 21). Angehängt wird das Versand-PDF
mit verkleinerten Fotos (app/checklist_pdf.py::build_checklist_email_pdf(), höchstens 3.000.000
Bytes) -- genau das landet in der Ablage. Die Fotos in der Checkliste bleiben unverändert.

Vorbelegter Empfänger: im Kontext Auftrag die E-Mail des Kunden am Projekt, im Kontext Objekt die des
Objekt-Kunden, sonst keiner. Betreff/Text aus der E-Mail-Vorlage "checklist" (Einstellungen →
E-Mail-Vorlagen), sonst der eingebaute Standard. Rollenlos; wer senden darf, entscheidet der Router.
"""

from sqlalchemy.orm import Session

from .models import Checklist, Customer, Order, Property

DEFAULT_CHECKLIST_EMAIL_SUBJECT = "{checkliste} – Checkliste Nr. {checklistennummer}"
DEFAULT_CHECKLIST_EMAIL_BODY = (
    "Sehr geehrte Damen und Herren,\n\n"
    "anbei erhalten Sie die Checkliste „{checkliste}“ (Nr. {checklistennummer}, {bezug}). "
    "Alle Angaben entnehmen Sie bitte dem beigefügten PDF.\n\n"
    "Mit freundlichen Grüßen"
)
CONTEXT_LABELS = {"auftrag": "Auftrag", "objekt": "Objekt", "betriebsmittel": "Betriebsmittel", "betrieb": "Betrieb"}


def _customer(db: Session, checklist: Checklist) -> Customer | None:
    if checklist.context_type == "auftrag" and checklist.order_id:
        order = db.get(Order, checklist.order_id)
        return order.project.customer if order and order.project else None
    if checklist.context_type == "objekt" and checklist.property_id:
        prop = db.get(Property, checklist.property_id)
        return db.get(Customer, prop.customer_id) if prop else None
    return None


def get_checklist_recipient_email(db: Session, checklist: Checklist) -> str | None:
    """Live nachgeschlagen wie bei Rechnung/Mahnung; ändert nie die Stammdaten."""
    customer = _customer(db, checklist)
    return (customer.email or None) if customer else None


def _placeholders(db: Session, checklist: Checklist) -> dict[str, str]:
    order = db.get(Order, checklist.order_id) if checklist.context_type == "auftrag" and checklist.order_id else None
    if order is not None:
        reference = f"Auftrag {order.order_number}"
    else:
        label = " – ".join(x for x in (checklist.context_label_snapshot, checklist.context_detail_snapshot) if x)
        context = CONTEXT_LABELS.get(checklist.context_type, checklist.context_type)
        reference = f"{context} {label}" if label else context
    customer = _customer(db, checklist)
    return {
        "{checkliste}": checklist.template_label_snapshot, "{checklistennummer}": str(checklist.id),
        "{bezug}": reference, "{kundenname}": (order.customer_name if order else None) or (customer.name if customer else ""),
    }


def send_checklist_email(
    db: Session, checklist: Checklist, *, to_email: str | None = None, cc_email: str | None = None,
    dispatch_key: str | None = None, user=None,
):
    """Versendet eine abgeschlossene Checkliste. Gibt das DispatchResult zurück (die Checkliste hat
    keine eigenen Versandfelder -- der Verlauf steht im Protokoll). Wirft ValueError (400) und
    DispatchConflict (409)."""
    from .checklist_pdf import build_checklist_email_pdf
    from .document_email_templates import get_email_template
    from .email_dispatch import actor_of, dispatch_email, new_dispatch_key

    if checklist.status != "abgeschlossen":
        raise ValueError("Nur abgeschlossene Checklisten können per E-Mail versendet werden.")
    recipient = (to_email or "").strip() or get_checklist_recipient_email(db, checklist)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")
    template = get_email_template(db, "checklist")
    subject = (template.subject_template if template else None) or DEFAULT_CHECKLIST_EMAIL_SUBJECT
    body = (template.body_template if template else None) or DEFAULT_CHECKLIST_EMAIL_BODY
    for placeholder, value in _placeholders(db, checklist).items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)

    pdf_bytes = build_checklist_email_pdf(db, checklist)
    user_id, user_name = actor_of(user)
    return dispatch_email(
        db, dispatch_key=dispatch_key or new_dispatch_key("checkliste"), document_type="checkliste",
        document_id=checklist.id, document_number=f"Nr. {checklist.id}", to=recipient, cc=cc_email,
        subject=subject, body_text=body, attachment_bytes=pdf_bytes,
        attachment_filename=f"Checkliste-{checklist.id}.pdf", user_id=user_id, user_name=user_name,
    )
