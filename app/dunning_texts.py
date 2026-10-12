"""Rechtstexte zu Verzug, Verzugszinsen und Pauschale (seit 1.8.81, Zahlungsstufe Z2b Punkt 9, docs/archiv/zahlungen.md).

Drei feste Schlüssel (DunningLegalText.text_key) -- nie umbenennen. Gepflegt in Einstellungen → Mahnstufen, nur Admin, mit
"geprüft am/durch" wie die Klauseln der Vertragsgrundlagen (app/contract_basis.py): ändert sich der Text ohne neue Prüfangabe,
fällt die Prüfung weg. Keine vorgegebenen Texte.

Die Mahnung druckt einen Text nur geprüft und nur, wenn sie sein Thema nennt (texts_for()): "verzug", wenn ein Verzugsbeginn
bestätigt ist und am Mahndatum gilt; "zinsen", wenn die Aufstellung Verzugszinsen zeigt; "pauschale", wenn sie die Pauschale zeigt.
Ungeprüft wird nichts gedruckt -- der Entwurf zeigt eine Warnung. Beim Festschreiben stehen die gedruckten Texte (Platzhalter
eingesetzt) in der Aufstellung der Mahnung (Format 3) und bleiben so, auch wenn der Text später geändert wird.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .models import DunningLegalText
from .placeholders import apply_placeholders, unknown_placeholders

LEGAL_TEXT_KEYS = ("verzug", "zinsen", "pauschale")
LEGAL_TEXT_LABELS = {"verzug": "Verzug", "zinsen": "Verzugszinsen", "pauschale": "Pauschale nach § 288 Abs. 5 BGB"}
PLACEHOLDERS = {
    "verzug": {"{verzugsbeginn}": "erster Tag im Verzug (bestätigter Verzugsbeginn)"},
    "zinsen": {"{prozentpunkte}": "Zuschlag über dem Basiszinssatz (5 bzw. 9)",
               "{zinsen_von}": "Beginn des Zinszeitraums dieser Mahnung", "{zinsen_bis}": "Ende des Zinszeitraums"},
    "pauschale": {"{pauschale}": "Betrag der Pauschale (40,00 €)"},
}
MAX_LENGTH = 5000


def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def is_reviewed(row: DunningLegalText | None) -> bool:
    return bool(row is not None and (row.body or "").strip() and row.reviewed_on is not None
                and (row.reviewed_by or "").strip())


def _row(db: Session, key: str) -> DunningLegalText | None:
    return db.scalar(select(DunningLegalText).where(DunningLegalText.text_key == key))


def text_to_dict(key: str, row: DunningLegalText | None) -> dict:
    return {"text_key": key, "label": LEGAL_TEXT_LABELS[key], "body": row.body if row else None,
            "reviewed_on": row.reviewed_on if row else None, "reviewed_by": row.reviewed_by if row else None,
            "reviewed": is_reviewed(row), "placeholders": [{"key": k, "label": v} for k, v in PLACEHOLDERS[key].items()],
            "unknown_placeholders": unknown_placeholders(row.body if row else None, PLACEHOLDERS[key]),
            "updated_at": row.updated_at if row else None, "updated_by_name": row.updated_by_name if row else None}


def list_texts(db: Session) -> list[dict]:
    rows = {r.text_key: r for r in db.scalars(select(DunningLegalText))}
    return [text_to_dict(key, rows.get(key)) for key in LEGAL_TEXT_KEYS]


def validate_key(key: str) -> str:
    if key not in LEGAL_TEXT_KEYS:
        raise ValueError(f"Unbekannter Rechtstext: {key!r}.")
    return key


def update_text(db: Session, key: str, *, body: str | None, reviewed_on: date | None, reviewed_by: str | None,
                actor_name: str = "System") -> tuple[dict, bool]:
    """Text und Prüfangaben speichern. Rückgabe: (Text, review_reset). Regeln wie update_clause(): "geprüft am" und "durch" nur
    zusammen, nicht in der Zukunft, ohne Text keine Prüfangabe; geänderter Text mit den alten Prüfangaben -> sie fallen weg."""
    key = validate_key(key)
    text = _clean(body)
    by = _clean(reviewed_by)
    if text is not None and len(text) > MAX_LENGTH:
        raise ValueError(f"Der Rechtstext darf höchstens {MAX_LENGTH} Zeichen lang sein.")
    if (reviewed_on is None) != (by is None):
        raise ValueError("„Geprüft am“ und „durch“ bitte gemeinsam angeben oder beide leer lassen.")
    if reviewed_on is not None and reviewed_on > berlin_today():
        raise ValueError("„Geprüft am“ darf nicht in der Zukunft liegen.")
    if text is None and reviewed_on is not None:
        raise ValueError("Ohne Text gibt es nichts, das geprüft sein könnte.")
    row = _row(db, key)
    if row is None:
        row = DunningLegalText(text_key=key)
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            # Gleichzeitig zum ersten Mal gespeichert -- die andere Zeile übernehmen (wie bei den Klauseln).
            row = _row(db, key)
    review_reset = False
    if (row.body or None) != text and reviewed_on is not None and reviewed_on == row.reviewed_on and by == row.reviewed_by:
        reviewed_on, by = None, None
        review_reset = True
    row.body, row.reviewed_on, row.reviewed_by = text, reviewed_on, by
    row.updated_by_name, row.updated_at = actor_name or "System", datetime.utcnow()
    db.commit()
    db.refresh(row)
    return text_to_dict(key, row), review_reset


def texts_for(db: Session, topics: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Die zu druckenden Texte und die Warnungen für eine Mahnung. topics: je genanntem Thema die Werte der Platzhalter, z. B.
    {"verzug": {"{verzugsbeginn}": "01.03.2026"}, "zinsen": {...}}. Ergebnis: ([{"key", "title", "text"}], [Warnung])."""
    rows = {r.text_key: r for r in db.scalars(select(DunningLegalText))}
    printed, warnings = [], []
    for key in LEGAL_TEXT_KEYS:
        if key not in topics:
            continue
        row = rows.get(key)
        label = LEGAL_TEXT_LABELS[key]
        if not is_reviewed(row):
            state = "fehlt" if row is None or not (row.body or "").strip() else "ist nicht geprüft"
            warnings.append(f"Der Rechtstext „{label}“ {state} – er wird nicht gedruckt (Einstellungen → Mahnstufen, nur "
                            "Administratoren).")
            continue
        printed.append({"key": key, "title": label, "text": apply_placeholders(row.body.strip(), topics[key])})
    return printed, warnings
