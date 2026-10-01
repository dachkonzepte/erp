"""Vertragsvorlagen und Vertragsentwurf am Auftrag (seit 1.8.32, Stufe 2b, Runde 2b-1b Teil 1).

Vorlage: eine je Vertragsgrundlage (app/contract_basis.py), Titel und Abschnitte mit Text und
Platzhaltern (app/placeholders.py). Ein Abschnitt kann "nur bei Verbrauchern" sein (Widerrufsbelehrung,
Muster-Widerrufsformular, Verlangen des vorzeitigen Beginns) und ein Ankreuzfeld tragen; seit 1.8.34 lässt
sich genau ein solches Ankreuzfeld als "Verlangen des vorzeitigen Beginns" kennzeichnen (early_start) --
daraus der Vermerk bei der Widerrufsfrist nach der Unterschrift (app/contract_signatures.py). Wie bei den
Klauseln (1.8.21) bewusst keine vorgegebenen Texte und eine rechtliche Prüfung mit Datum und Name;
ohne sie trägt jede Seite des Vertrags-PDFs das Wasserzeichen CONTRACT_WATERMARK_TEXT.

Entwurf: entsteht beim Beauftragen, wenn es für die Vertragsgrundlage des Auftrags eine Vorlage mit
Inhalt gibt (create_contract_draft_if_template(), aus app/orders.py::create_order_from_quote(); seit
1.8.33 nicht beim Schnellauftrag), sonst von Hand auf der Auftragsseite. Er trägt nur die Fallfelder;
Vorlagentext, Kunde, Summen und die Vertragsgrundlage liest das Entwurfs-PDF live -- über
contract_content(), denselben Inhalt, den das Festschreiben (seit 1.8.33, app/contract_versions.py)
einfriert. Ein Entwurf folgt damit bis zum Festschreiben jeder Änderung der Vertragsgrundlage.

Rollenlos wie jede Geschäftslogik -- wer was darf, entscheidet app/routers/contract_templates.py.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .contract_basis import CONTRACT_BASES, contract_basis_label, validate_contract_basis
from .document_pdf import money, qty
from .models import ContractTemplate, ContractTemplateSection, Order, OrderContract, QuoteDocumentMeta
from .orders import execution_period_text, order_to_dict
from .placeholders import apply_placeholders, unknown_placeholders
from .settings import get_or_create_general_settings

CONTRACT_WATERMARK_TEXT = "Entwurf – Vertragstext nicht geprüft"
DEFAULT_CONTRACT_TITLE = "Vertrag"

MAX_SECTIONS = 100
MAX_HEADING_LENGTH = 255
MAX_BODY_LENGTH = 50_000
MAX_CASE_FIELD_LENGTH = 20_000

# Platzhalter -> Bedeutung, in dieser Reihenfolge in der Oberfläche (Einstellungen → Vertragsvorlagen).
CONTRACT_PLACEHOLDERS: list[tuple[str, str]] = [
    ("{firmenname}", "Name des eigenen Betriebs (Einstellungen → Unternehmen)"),
    ("{firmenanschrift}", "Anschrift des eigenen Betriebs"),
    ("{kundenname}", "Name des Kunden, Stand bei Beauftragung"),
    ("{kundenanschrift}", "Anschrift des Kunden, Stand bei Beauftragung"),
    ("{kundennummer}", "Kundennummer"),
    ("{objekt}", "Bezeichnung des Objekts (Einsatzort)"),
    ("{objektanschrift}", "Anschrift des Objekts"),
    ("{auftragsnummer}", "Nummer des Auftrags"),
    ("{auftragsdatum}", "Datum des Auftrags"),
    ("{auftragstitel}", "Bezeichnung des Auftrags"),
    ("{angebotsnummer}", "Nummer des zugrunde liegenden Angebots (Anlage des Vertrags)"),
    ("{angebotsdatum}", "Datum des Angebots"),
    ("{projektnummer}", "Nummer des Vorgangs"),
    ("{vertragsgrundlage}", "Bezeichnung der Vertragsgrundlage des Auftrags, z. B. VOB/B"),
    ("{auftragssumme_netto}", "Auftragssumme netto"),
    ("{umsatzsteuersatz}", "Umsatzsteuersatz des Auftrags in Prozent"),
    ("{umsatzsteuer}", "Umsatzsteuer auf die Auftragssumme"),
    ("{auftragssumme_brutto}", "Auftragssumme brutto"),
    ("{zahlungsbedingungen}", "Zahlungsbedingungen des Auftrags"),
    ("{ausfuehrungszeitraum}", "Fallfeld am Vertragsentwurf (Vorgabe aus dem Auftrag)"),
    ("{abschlagsplan}", "Fallfeld am Vertragsentwurf"),
    ("{besonderheiten}", "Fallfeld am Vertragsentwurf"),
]
KNOWN_PLACEHOLDERS = [p for p, _ in CONTRACT_PLACEHOLDERS]
# Fallfeld am Entwurf -> sein Platzhalter. Ein Fallfeld, dessen Platzhalter die Vorlage nicht nutzt,
# erscheint nicht im Vertrag -- Einstellungen und Auftragsseite sagen das dazu.
CASE_FIELDS: dict[str, tuple[str, str]] = {
    "execution_period": ("{ausfuehrungszeitraum}", "Ausführungszeitraum"),
    "payment_plan": ("{abschlagsplan}", "Abschlagsplan"),
    "special_terms": ("{besonderheiten}", "Besonderheiten"),
}


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


# --- Vorlage --------------------------------------------------------------------------------------

def get_template_row(db: Session, key: str | None) -> ContractTemplate | None:
    if not key:
        return None
    return db.scalar(select(ContractTemplate).where(ContractTemplate.basis_key == key))


def _sorted_sections(row: ContractTemplate | None) -> list[ContractTemplateSection]:
    return sorted(row.sections, key=lambda s: (s.sort_order, s.id or 0)) if row is not None else []


def template_has_content(row: ContractTemplate | None) -> bool:
    """Eine Vorlage "existiert", sobald ein Abschnitt Text oder Überschrift hat -- eine nur
    angelegte, leere Zeile erzeugt keinen Entwurf."""
    return any((s.heading or "").strip() or (s.body_text or "").strip() for s in _sorted_sections(row))


def template_is_reviewed(row: ContractTemplate | None) -> bool:
    return bool(
        template_has_content(row) and row.reviewed_on is not None and (row.reviewed_by or "").strip()
    )


def _template_texts(row: ContractTemplate | None) -> list[str]:
    if row is None:
        return []
    return [row.title or ""] + [t for s in _sorted_sections(row) for t in (s.heading or "", s.body_text or "")]


def unused_case_fields(row: ContractTemplate | None) -> list[dict]:
    """Fallfelder, deren Platzhalter die Vorlage nirgends nutzt -- ihr Inhalt käme nicht in den Vertrag."""
    joined = "\n".join(_template_texts(row))
    return [{"field": field, "label": label, "placeholder": ph}
            for field, (ph, label) in CASE_FIELDS.items() if ph not in joined]


def section_to_dict(section: ContractTemplateSection) -> dict:
    return {
        "id": section.id, "sort_order": section.sort_order, "heading": section.heading,
        "body_text": section.body_text, "consumer_only": bool(section.consumer_only),
        "with_checkbox": bool(section.with_checkbox), "early_start": bool(section.early_start),
    }


def template_to_dict(key: str, row: ContractTemplate | None) -> dict:
    unknown: list[str] = []
    for text in _template_texts(row):
        for p in unknown_placeholders(text, KNOWN_PLACEHOLDERS):
            if p not in unknown:
                unknown.append(p)
    return {
        "basis_key": key,
        "label": CONTRACT_BASES[key],
        "title": row.title if row else None,
        "sections": [section_to_dict(s) for s in _sorted_sections(row)],
        "reviewed_on": row.reviewed_on if row else None,
        "reviewed_by": row.reviewed_by if row else None,
        "reviewed": template_is_reviewed(row),
        "has_content": template_has_content(row),
        "unknown_placeholders": unknown,
        "unused_case_fields": unused_case_fields(row) if template_has_content(row) else [],
        "updated_at": row.updated_at if row else None,
        "updated_by_name": row.updated_by_name if row else None,
    }


def list_templates(db: Session) -> list[dict]:
    rows = {r.basis_key: r for r in db.scalars(select(ContractTemplate)).all()}
    return [template_to_dict(key, rows.get(key)) for key in CONTRACT_BASES]


def placeholder_list() -> list[dict]:
    return [{"placeholder": p, "description": d} for p, d in CONTRACT_PLACEHOLDERS]


def _normalize_sections(sections: list[dict]) -> list[dict]:
    """Leere Abschnitte (weder Überschrift noch Text) fallen weg; Reihenfolge wie übergeben. "Vorzeitiger
    Beginn" (seit 1.8.34) nur an einem Ankreuzfeld "nur bei Verbrauchern", höchstens einmal."""
    result = []
    for raw in sections:
        heading = _clean(raw.get("heading"))
        body = (raw.get("body_text") or "").strip("\n").rstrip() or None
        if heading is None and body is None:
            continue
        if heading is not None and len(heading) > MAX_HEADING_LENGTH:
            raise ValueError(f"Eine Abschnittsüberschrift darf höchstens {MAX_HEADING_LENGTH} Zeichen lang sein.")
        if body is not None and len(body) > MAX_BODY_LENGTH:
            raise ValueError(f"Ein Abschnittstext darf höchstens {MAX_BODY_LENGTH} Zeichen lang sein.")
        early_start = bool(raw.get("early_start"))
        if early_start and not (raw.get("with_checkbox") and raw.get("consumer_only")):
            raise ValueError(
                "„Verlangen des vorzeitigen Beginns“ geht nur an einem Abschnitt mit Ankreuzfeld und "
                "„nur bei Verbrauchern“."
            )
        result.append({
            "heading": heading, "body_text": body,
            "consumer_only": bool(raw.get("consumer_only")), "with_checkbox": bool(raw.get("with_checkbox")),
            "early_start": early_start,
        })
    if len(result) > MAX_SECTIONS:
        raise ValueError(f"Eine Vorlage darf höchstens {MAX_SECTIONS} Abschnitte haben.")
    if sum(s["early_start"] for s in result) > 1:
        raise ValueError("Nur ein Ankreuzfeld kann das Verlangen des vorzeitigen Beginns sein.")
    return result


def _content_signature(title: str | None, sections: list[dict]) -> tuple:
    """Was den Vertrag verändert. Das Kennzeichen "vorzeitiger Beginn" (seit 1.8.34) bewusst nicht: es
    ändert keinen Text im Vertrag, nur den Vermerk bei der Widerrufsfrist -- eine geprüfte Vorlage lässt
    sich ohne neue Prüfung kennzeichnen."""
    return (title or None, tuple(
        (s["heading"], s["body_text"], bool(s["consumer_only"]), bool(s["with_checkbox"])) for s in sections
    ))


def save_template(
    db: Session, key: str, *, title: str | None, sections: list[dict], reviewed_on: date | None,
    reviewed_by: str | None, actor_name: str = "System",
) -> tuple[dict, bool]:
    """Speichert Titel, Abschnitte und Prüfangaben einer Vorlage. Rückgabe: (Vorlage, review_reset).

    Regeln wie bei den Klauseln (app/contract_basis.py::update_clause()): "geprüft am" und "durch" nur
    zusammen, das Datum nicht in der Zukunft, ohne Inhalt keine Prüfangabe. Ändert sich der Inhalt
    (Titel, Überschrift, Text, Reihenfolge, "nur bei Verbrauchern", Ankreuzfeld -- alles, was den Vertrag
    verändert) und kommen dieselben Prüfangaben wie bisher mit, fallen sie weg: die Prüfung galt dem
    alten Text. Mit neuem Datum oder Namen bleibt sie."""
    key = validate_contract_basis(key)
    title = _clean(title)
    if title is not None and len(title) > MAX_HEADING_LENGTH:
        raise ValueError(f"Der Titel darf höchstens {MAX_HEADING_LENGTH} Zeichen lang sein.")
    new_sections = _normalize_sections(sections)
    by = _clean(reviewed_by)
    if (reviewed_on is None) != (by is None):
        raise ValueError("„Rechtlich geprüft am“ und „durch“ bitte gemeinsam angeben oder beide leer lassen.")
    if reviewed_on is not None and reviewed_on > berlin_today():
        raise ValueError("„Rechtlich geprüft am“ darf nicht in der Zukunft liegen.")
    if not new_sections and reviewed_on is not None:
        raise ValueError("Ohne Abschnitte gibt es nichts, das geprüft sein könnte.")

    row = get_template_row(db, key)
    if row is None:
        row = ContractTemplate(basis_key=key)
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            # Gleichzeitig zum ersten Mal gespeichert -- die andere Zeile übernehmen (CLAUDE.md,
            # "Self-Seeding gegen gleichzeitigen ersten Zugriff absichern").
            row = get_template_row(db, key)

    old_sections = [section_to_dict(s) for s in _sorted_sections(row)]
    changed = _content_signature(row.title, old_sections) != _content_signature(title, new_sections)
    review_reset = False
    if changed and reviewed_on is not None and reviewed_on == row.reviewed_on and by == row.reviewed_by:
        reviewed_on, by = None, None
        review_reset = True

    row.title = title
    row.sections = [
        ContractTemplateSection(sort_order=(i + 1) * 10, **s) for i, s in enumerate(new_sections)
    ]
    row.reviewed_on = reviewed_on
    row.reviewed_by = by
    row.updated_by_name = actor_name or "System"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return template_to_dict(key, row), review_reset


def visible_sections(row: ContractTemplate | None, *, is_consumer: bool) -> list[ContractTemplateSection]:
    """Die Abschnitte, die in den Vertrag kommen: "nur bei Verbrauchern" nur, wenn der Kunde einer ist."""
    return [
        s for s in _sorted_sections(row)
        if ((s.heading or "").strip() or (s.body_text or "").strip()) and (is_consumer or not s.consumer_only)
    ]


# --- Entwurf am Auftrag ---------------------------------------------------------------------------

def order_customer_is_consumer(order: Order) -> bool:
    """Live vom Kunden des Vorgangs -- der Auftrag hält das Merkmal nicht als Schnappschuss. Ohne
    Kunden die Vorgabe des Felds (Verbraucher), wie default_contract_basis_for_customer()."""
    customer = order.project.customer if order.project else None
    return True if customer is None or customer.is_consumer is None else bool(customer.is_consumer)


def get_order_contract(db: Session, order_id: int) -> OrderContract | None:
    return db.scalar(select(OrderContract).where(OrderContract.order_id == order_id))


def create_contract_draft(db: Session, order: Order, *, actor_name: str = "System", commit: bool = True) -> OrderContract:
    """Legt den Vertragsentwurf an. Wirft ValueError, wenn es schon einen gibt oder für die
    Vertragsgrundlage des Auftrags keine Vorlage mit Inhalt existiert. Ausführungszeitraum: Vorgabe
    aus dem Auftrag (Freitext aus dem Angebot und/oder Beginn/Ende)."""
    if get_order_contract(db, order.id) is not None:
        raise ValueError("Zu diesem Auftrag gibt es bereits einen Vertragsentwurf.")
    if not template_has_content(get_template_row(db, order.contract_basis)):
        raise ValueError(
            f"Für die Vertragsgrundlage „{contract_basis_label(order.contract_basis)}“ gibt es keine "
            "Vertragsvorlage (Einstellungen → Vertragsvorlagen)."
        )
    contract = OrderContract(
        order_id=order.id, status="entwurf", execution_period=execution_period_text(order),
        created_by_name=actor_name or "System",
    )
    db.add(contract)
    if commit:
        db.commit()
        db.refresh(contract)
    else:
        db.flush()
    return contract


def create_contract_draft_if_template(db: Session, order: Order, *, actor_name: str = "System") -> OrderContract | None:
    """Beim Beauftragen: Entwurf nur, wenn es eine Vorlage gibt -- ohne Commit, das macht die
    Beauftragung selbst (eine Transaktion)."""
    if get_order_contract(db, order.id) is not None:
        return None
    if not template_has_content(get_template_row(db, order.contract_basis)):
        return None
    return create_contract_draft(db, order, actor_name=actor_name, commit=False)


def update_contract_draft(db: Session, contract: OrderContract, values: dict, *, actor_name: str = "System") -> OrderContract:
    """Ändert die Fallfelder -- nur die übergebenen (Regel 22), nur solange der Vertrag ein Entwurf ist
    (seit 1.8.33: festgeschrieben ist er gesperrt, Änderungen nur als neue Fassung)."""
    if contract.status != "entwurf":
        raise ValueError("Nur ein Vertragsentwurf kann geändert werden – ein festgeschriebener Vertrag nur als neue Fassung.")
    for field, value in values.items():
        if field not in CASE_FIELDS:
            raise ValueError(f"Unbekanntes Feld: {field}")
        text = (value or "").strip("\n").rstrip() or None
        if text is not None and len(text) > MAX_CASE_FIELD_LENGTH:
            raise ValueError(f"{CASE_FIELDS[field][1]}: höchstens {MAX_CASE_FIELD_LENGTH} Zeichen.")
        setattr(contract, field, text)
    contract.updated_by_name = actor_name or "System"
    contract.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contract)
    return contract


def contract_state(db: Session, order: Order) -> dict:
    """Alles, was die Auftragsseite für die Karte "Vertrag" braucht."""
    row = get_template_row(db, order.contract_basis)
    contract = get_order_contract(db, order.id)
    return {
        "order_id": order.id,
        "basis_key": order.contract_basis,
        "basis_label": contract_basis_label(order.contract_basis),
        "template_available": template_has_content(row),
        "template_reviewed": template_is_reviewed(row),
        "unused_case_fields": unused_case_fields(row) if template_has_content(row) else [],
        "is_consumer": order_customer_is_consumer(order),
        "contract": None if contract is None else {
            "id": contract.id, "order_id": contract.order_id, "status": contract.status,
            "execution_period": contract.execution_period, "payment_plan": contract.payment_plan,
            "special_terms": contract.special_terms, "created_by_name": contract.created_by_name,
            "created_at": contract.created_at, "updated_by_name": contract.updated_by_name,
            "updated_at": contract.updated_at,
        },
    }


def _date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def contract_placeholder_values(db: Session, order: Order, contract: OrderContract | None, *, data: dict | None = None) -> dict[str, str]:
    """Die Werte für jeden Platzhalter aus CONTRACT_PLACEHOLDERS -- live aus Auftrag, Angebot und
    Betrieb, die Fallfelder aus dem Entwurf. Kunde und Objekt sind der Schnappschuss am Auftrag."""
    data = data if data is not None else order_to_dict(order, db, include_sync_state=False)
    general = get_or_create_general_settings(db)
    meta = db.scalar(select(QuoteDocumentMeta).where(QuoteDocumentMeta.quote_id == order.source_quote_id))
    company_city = " ".join(x for x in (general.postal_code, general.city) if x)
    values = {
        "{firmenname}": general.company_name or "",
        "{firmenanschrift}": ", ".join(x for x in (general.street, company_city) if x),
        "{kundenname}": order.customer_name or "",
        "{kundenanschrift}": order.customer_address or "",
        "{kundennummer}": order.customer_number or "",
        "{objekt}": order.property_name or "",
        "{objektanschrift}": order.property_address or "",
        "{auftragsnummer}": order.order_number or "",
        "{auftragsdatum}": _date(order.order_date),
        "{auftragstitel}": order.title or "",
        "{angebotsnummer}": order.quote_number_snapshot or "",
        "{angebotsdatum}": _date(meta.quote_date) if meta else "",
        "{projektnummer}": data.get("project_number") or "",
        "{vertragsgrundlage}": contract_basis_label(order.contract_basis) or "",
        "{auftragssumme_netto}": money(data["net_total"]),
        "{umsatzsteuersatz}": f"{qty(data['vat_rate'])} %",
        "{umsatzsteuer}": money(data["vat_total"]),
        "{auftragssumme_brutto}": money(data["gross_total"]),
        "{zahlungsbedingungen}": order.payment_terms or "",
        "{ausfuehrungszeitraum}": (contract.execution_period if contract else None) or "",
        "{abschlagsplan}": (contract.payment_plan if contract else None) or "",
        "{besonderheiten}": (contract.special_terms if contract else None) or "",
    }
    return values  # test_v335: jeder Platzhalter aus CONTRACT_PLACEHOLDERS hat hier einen Wert


def fill(text: str | None, values: dict[str, str]) -> str:
    return apply_placeholders(text or "", values)


def contract_content(db: Session, order: Order, contract: OrderContract | None) -> dict:
    """Alles, was im Vertrags-PDF steht (außer Briefpapier und Layout), als einfache Datenstruktur:
    Titel und sichtbare Abschnitte mit eingesetzten Platzhaltern, Kopf- und Anschriftenangaben,
    Vertragsgrundlage, Verbraucher-Merkmal, Fallfelder, die Werte aller Platzhalter und welche davon
    die Vorlage nutzt. Das Entwurfs-PDF rendert daraus live, das Festschreiben friert genau diese
    Struktur ein (app/contract_versions.py). Wirft ValueError ohne Vorlage für die (heutige)
    Vertragsgrundlage."""
    template = get_template_row(db, order.contract_basis)
    if not template_has_content(template):
        raise ValueError(
            f"Für die Vertragsgrundlage „{contract_basis_label(order.contract_basis)}“ gibt es keine "
            "Vertragsvorlage (Einstellungen → Vertragsvorlagen)."
        )
    is_consumer = order_customer_is_consumer(order)
    data = order_to_dict(order, db, include_sync_state=False)
    values = contract_placeholder_values(db, order, contract, data=data)
    sections = visible_sections(template, is_consumer=is_consumer)
    general = get_or_create_general_settings(db)
    raw_texts = [template.title or ""] + [t for s in sections for t in (s.heading or "", s.body_text or "")]
    used = [p for p in KNOWN_PLACEHOLDERS if any(p in t for t in raw_texts)]
    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    return {
        "v": 1,
        "order_id": order.id,
        "order_number": order.order_number,
        "order_date": order.order_date.isoformat() if order.order_date else None,
        "quote_id": order.source_quote_id,
        "quote_number": order.quote_number_snapshot,
        "quote_date": values["{angebotsdatum}"],
        "project_number": data.get("project_number"),
        "customer_number": order.customer_number,
        "basis_key": order.contract_basis,
        "basis_label": contract_basis_label(order.contract_basis),
        "is_consumer": is_consumer,
        "template": {
            "title": template.title,
            "reviewed_on": template.reviewed_on.isoformat() if template.reviewed_on else None,
            "reviewed_by": template.reviewed_by,
            "reviewed": template_is_reviewed(template),
        },
        "title": fill(template.title, values).strip() or DEFAULT_CONTRACT_TITLE,
        "sections": [
            {
                "key": f"abschnitt-{i}",
                "heading": fill(s.heading, values).strip(),
                "text": fill(s.body_text, values).strip("\n").rstrip(),
                "consumer_only": bool(s.consumer_only),
                "with_checkbox": bool(s.with_checkbox),
                "early_start": bool(s.early_start),  # seit 1.8.34; ältere Fassungen haben den Schlüssel nicht
            }
            for i, s in enumerate(sections, start=1)
        ],
        "case_fields": {field: getattr(contract, field, None) if contract else None for field in CASE_FIELDS},
        "placeholders": values,
        "used_placeholders": used,
        "sender_line": " - ".join(x for x in sender_parts if x),
        # Schnappschuss am Auftrag "Straße, PLZ Ort" -- wie order_pdf.py an der bekannten Fuge geteilt.
        "recipient_lines": [order.customer_name] + (order.customer_address.split(", ", 1) if order.customer_address else []),
        "property_name": order.property_name,
        "property_lines": [x for x in str(order.property_address or "").splitlines() if x],
    }
