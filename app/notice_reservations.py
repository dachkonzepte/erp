"""Vorbehalt in Briefen an den Auftraggeber (seit 1.8.40, Stufe 2b, Runde 2b-3 Teil 2).

Ein Textbaustein je Briefart (app/notice_letters.py::LETTER_KINDS -- Behinderungsanzeige, Anzeige der
Wiederaufnahme) und Gruppe der Vertragsgrundlage: "vob_b" (VOB/B) und "bgb" (BGB, auch mit VOB/C
Abschnitt 4 und 5 -- ein BGB-Bauvertrag, die VOB/C regelt nur das Technische). Gepflegt in den
Einstellungen, mit "rechtlich geprüft am, durch" wie die Klauseln der Vertragsgrundlage
(app/contract_basis.py) und nach denselben Regeln: Datum und Name nur gemeinsam, Datum nicht in der
Zukunft, ohne Text keine Prüfangabe; ändert sich der Text und kommen dieselben Prüfangaben wie bisher mit,
fallen sie weg (review_reset). Kein Seeding und keine vorgegebenen Texte -- Rechtstexte gehören geprüft,
nicht vom ERP erfunden.

Gedruckt wird nur ein geprüfter Vorbehalt (printable_reservation()). Ungeprüft fehlt er im Brief, der
Versand bleibt aber möglich -- eine Behinderung ist unverzüglich anzuzeigen; die Seite warnt deutlich.

Rollenlos wie jede Geschäftslogik; speichern dürfen nur Administratoren (app/routers/notice_letters.py).
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .models import NoticeReservation

# Briefarten, für die es einen Vorbehalt gibt -- dieselben Schlüssel wie app/notice_letters.py::LETTER_KINDS
# (hier ohne Import, das Briefmodul importiert von hier).
RESERVATION_LETTER_KINDS: dict[str, str] = {
    "behinderungsanzeige": "Behinderungsanzeige",
    "wiederaufnahme": "Anzeige der Wiederaufnahme",
    "bedenkenanzeige": "Bedenkenanzeige",  # seit 1.8.44
}
BASIS_GROUPS: dict[str, str] = {
    "vob_b": "VOB/B",
    "bgb": "BGB (auch mit VOB/C Abschnitt 4 und 5)",
}
MAX_TEXT_LENGTH = 20_000


def basis_group_for(contract_basis: str | None) -> str:
    """Gruppe zur Vertragsgrundlage des Auftrags: VOB/B für "vob_b", sonst BGB (auch "bgb_vob_c_4_5"
    und der Bestand "bgb")."""
    return "vob_b" if contract_basis == "vob_b" else "bgb"


def _check_keys(letter_kind: str, basis_group: str) -> None:
    if letter_kind not in RESERVATION_LETTER_KINDS:
        raise LookupError("Unbekannte Briefart.")
    if basis_group not in BASIS_GROUPS:
        raise LookupError("Unbekannte Vertragsgrundlage.")


def _row(db: Session, letter_kind: str, basis_group: str) -> NoticeReservation | None:
    return db.scalar(select(NoticeReservation).where(
        NoticeReservation.letter_kind == letter_kind, NoticeReservation.basis_group == basis_group))


def reservation_is_reviewed(row: NoticeReservation | None) -> bool:
    return bool(
        row is not None and (row.reservation_text or "").strip()
        and row.reviewed_on is not None and (row.reviewed_by or "").strip()
    )


def reservation_to_dict(letter_kind: str, basis_group: str, row: NoticeReservation | None) -> dict:
    return {
        "letter_kind": letter_kind, "letter_label": RESERVATION_LETTER_KINDS[letter_kind],
        "basis_group": basis_group, "basis_label": BASIS_GROUPS[basis_group],
        "reservation_text": row.reservation_text if row else None,
        "reviewed_on": row.reviewed_on if row else None, "reviewed_by": row.reviewed_by if row else None,
        "reviewed": reservation_is_reviewed(row), "has_text": bool(row and (row.reservation_text or "").strip()),
        "updated_at": row.updated_at if row else None, "updated_by_name": row.updated_by_name if row else None,
    }


def list_reservations(db: Session) -> list[dict]:
    rows = {(r.letter_kind, r.basis_group): r for r in db.scalars(select(NoticeReservation)).all()}
    return [reservation_to_dict(kind, group, rows.get((kind, group)))
            for kind in RESERVATION_LETTER_KINDS for group in BASIS_GROUPS]


def reservation_state(db: Session, letter_kind: str, contract_basis: str | None) -> dict:
    """Der Vorbehalt, der für einen Brief dieser Art zu einem Auftrag mit dieser Vertragsgrundlage gilt."""
    group = basis_group_for(contract_basis)
    _check_keys(letter_kind, group)
    return reservation_to_dict(letter_kind, group, _row(db, letter_kind, group))


def printable_reservation(db: Session, letter_kind: str, contract_basis: str | None) -> str | None:
    """Der Vorbehaltstext für den Brief -- nur, wenn rechtlich geprüft, sonst None (nichts drucken)."""
    group = basis_group_for(contract_basis)
    row = _row(db, letter_kind, group)
    return row.reservation_text.strip() if reservation_is_reviewed(row) else None


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def update_reservation(
    db: Session, letter_kind: str, basis_group: str, *, reservation_text: str | None, reviewed_on: date | None,
    reviewed_by: str | None, actor_name: str = "System",
) -> tuple[dict, bool]:
    """Speichert Text und Prüfangaben. Rückgabe: (Vorbehalt, review_reset). Regeln wie
    app/contract_basis.py::update_clause() (siehe Moduldocstring). LookupError: unbekannte Briefart oder
    Gruppe; ValueError: Eingabe."""
    _check_keys(letter_kind, basis_group)
    text = _clean(reservation_text)
    by = _clean(reviewed_by)
    if text is not None and len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Der Text darf höchstens {MAX_TEXT_LENGTH} Zeichen lang sein.")
    if (reviewed_on is None) != (by is None):
        raise ValueError("„Rechtlich geprüft am“ und „durch“ bitte gemeinsam angeben oder beide leer lassen.")
    if reviewed_on is not None and reviewed_on > berlin_today():
        raise ValueError("„Rechtlich geprüft am“ darf nicht in der Zukunft liegen.")
    if text is None and reviewed_on is not None:
        raise ValueError("Ohne Text gibt es nichts, das geprüft sein könnte.")

    row = _row(db, letter_kind, basis_group)
    if row is None:
        row = NoticeReservation(letter_kind=letter_kind, basis_group=basis_group)
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            # Gleichzeitig zum ersten Mal gespeichert -- die andere Zeile übernehmen (CLAUDE.md,
            # "Self-Seeding gegen gleichzeitigen ersten Zugriff absichern").
            row = _row(db, letter_kind, basis_group)

    review_reset = False
    text_changed = (row.reservation_text or None) != text
    if text_changed and reviewed_on is not None and reviewed_on == row.reviewed_on and by == row.reviewed_by:
        reviewed_on, by = None, None
        review_reset = True
    row.reservation_text = text
    row.reviewed_on = reviewed_on
    row.reviewed_by = by
    row.updated_by_name = actor_name or "System"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return reservation_to_dict(letter_kind, basis_group, row), review_reset
