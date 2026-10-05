"""Leistungsart und Gewährleistungsdauer am Auftrag, Gewährleistungsende aus der Abnahme (seit 1.8.46, Stufe 2c-1).

- Leistungsart (`Order.work_kind`): "bauwerk" oder "sonstige" (sonstige Arbeiten: Herstellung, Wartung oder Veränderung
  einer Sache ohne Bauwerk). Schlüssel stehen in der Datenbank und werden nie umbenannt.
- Gewährleistungsdauer (`Order.warranty_months`/`warranty_days`): leer = "nicht festgelegt". Der Vorschlag hängt an
  Vertragsgrundlage und Leistungsart (PROPOSALS, mit Fundstelle als Hinweis) und wird nur bewusst übernommen
  (set_order_warranty()); eine andere Dauer nur mit Begründung. Jede Festlegung steht in OrderWarrantyChange mit dem
  Vorschlag dieses Zeitpunkts. Ändert sich später die Vertragsgrundlage, bleibt die Dauer stehen -- die Auftragsseite
  zeigt dann, dass sie vom heutigen Vorschlag abweicht.
- Seit 1.8.47: nach der ersten nicht verworfenen Abnahme ändern sich Leistungsart oder Dauer nur noch mit Begründung
  (auch beim Vorschlag); warranty_change_preview() zeigt vorher, welche Gewährleistungsenden sich verschieben, die
  Festlegung hält sie fest (acceptance_shifts). Die erste Festlegung nach einer Abnahme verschiebt nichts (vorher gab es
  kein Ende) und braucht keine Begründung, die Vorschau zeigt die entstehenden Enden.
- Gewährleistungsende: nie gespeichert, immer abgeleitet -- Datum einer Abnahme plus Dauer (warranty_end()).

Rollenlos wie jede Geschäftslogik; wer festlegen darf, entscheidet der Router.
"""

import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .contract_basis import CONTRACT_BASES, contract_basis_label
from .date_utils import add_months
from .models import Order, OrderWarrantyChange

WORK_KINDS: dict[str, str] = {"bauwerk": "Bauwerk", "sonstige": "sonstige Arbeiten"}

# (Vertragsgrundlage, Leistungsart) -> (Monate, Tage, Fundstelle). Nur ein Vorschlag: eine im Vertrag vereinbarte
# Dauer geht vor, deshalb wird nichts davon von selbst übernommen.
_VOB_B_BAUWERK = "§ 13 Abs. 4 Nr. 1 VOB/B – Bauwerke: 4 Jahre"
_VOB_B_SONSTIGE = "§ 13 Abs. 4 Nr. 1 VOB/B – andere Werke (Herstellung, Wartung oder Veränderung einer Sache): 2 Jahre"
_BGB_BAUWERK = "§ 634a Abs. 1 Nr. 2 BGB – Bauwerk: 5 Jahre"
_BGB_SONSTIGE = "§ 634a Abs. 1 Nr. 1 BGB – Herstellung, Wartung oder Veränderung einer Sache: 2 Jahre"
PROPOSALS: dict[tuple[str, str], tuple[int, int, str]] = {
    ("vob_b", "bauwerk"): (48, 0, _VOB_B_BAUWERK),
    ("vob_b", "sonstige"): (24, 0, _VOB_B_SONSTIGE),
    ("bgb_vob_c_4_5", "bauwerk"): (60, 0, _BGB_BAUWERK),
    ("bgb_vob_c_4_5", "sonstige"): (24, 0, _BGB_SONSTIGE),
    ("bgb", "bauwerk"): (60, 0, _BGB_BAUWERK),
    ("bgb", "sonstige"): (24, 0, _BGB_SONSTIGE),
}
assert {basis for basis, _ in PROPOSALS} == set(CONTRACT_BASES), "jede Vertragsgrundlage braucht einen Vorschlag"

MAX_MONTHS = 360  # 30 Jahre
MAX_DAYS = 366
MAX_REASON_LENGTH = 2000
NOT_SET_TEXT = "nicht festgelegt"
END_RULE_TEXT = ("Abnahmetag zählt nicht mit (§ 187 Abs. 1 BGB); Ende am Tag mit derselben Zahl im letzten Monat, "
                 "fehlt er, am Monatsletzten (§ 188 Abs. 2 und 3 BGB)")


def work_kind_label(key: str | None) -> str | None:
    return WORK_KINDS.get(key, key) if key else None


def duration_text(months: int | None, days: int | None) -> str:
    """"60 Monate (5 Jahre)", "1 Monat", "24 Monate und 10 Tage", "1 Tag"; leer -> "nicht festgelegt"."""
    if months is None or days is None:
        return NOT_SET_TEXT
    parts = []
    if months:
        parts.append(f"{months} Monat" + ("e" if months != 1 else ""))
    if days:
        parts.append(f"{days} Tag" + ("e" if days != 1 else ""))
    text = " und ".join(parts) or "0 Tage"
    if months and not days and months % 12 == 0:
        years = months // 12
        text += f" ({years} Jahr{'e' if years != 1 else ''})"
    return text


def warranty_proposal(contract_basis: str | None, work_kind: str | None) -> dict | None:
    entry = PROPOSALS.get((contract_basis, work_kind))
    if entry is None:
        return None
    months, days, citation = entry
    return {"months": months, "days": days, "text": duration_text(months, days), "citation": citation}


def warranty_end(accepted_on: date, months: int, days: int) -> date:
    """Letzter Tag der Gewährleistung nach einer Abnahme am `accepted_on`.

    § 187 Abs. 1 BGB: die Abnahme ist ein Ereignis, ihr Tag zählt nicht mit. § 188 Abs. 2 BGB: eine Frist nach Monaten
    endet mit dem Ablauf des Tages im letzten Monat, der durch seine Zahl dem Abnahmetag entspricht; § 188 Abs. 3 BGB:
    fehlt dieser Tag im letzten Monat (29.–31.), mit dem Ablauf des letzten Tages dieses Monats -- genau das tut
    add_months(). Tage nach § 188 Abs. 1 BGB, gezählt NACH den Monaten (Festlegung 1.8.46). § 193 BGB (Wochenende,
    Feiertag) wird nicht angewandt."""
    return add_months(accepted_on, months) + timedelta(days=days)


def order_warranty_info(order: Order) -> dict:
    """Für order_to_dict(): Stand am Auftrag und der Vorschlag je Leistungsart für die heutige Vertragsgrundlage."""
    is_set = order.warranty_months is not None and order.warranty_days is not None
    proposal = warranty_proposal(order.contract_basis, order.work_kind)
    follows = None
    if is_set and proposal is not None:
        follows = (order.warranty_months, order.warranty_days) == (proposal["months"], proposal["days"])
    return {
        "work_kind": order.work_kind,
        "work_kind_label": work_kind_label(order.work_kind),
        "warranty_months": order.warranty_months,
        "warranty_days": order.warranty_days,
        "warranty_set": is_set,
        "warranty_text": duration_text(order.warranty_months, order.warranty_days),
        "warranty_follows_proposal": follows,
        "warranty_proposals": {kind: warranty_proposal(order.contract_basis, kind) for kind in WORK_KINDS},
    }


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _check_values(order: Order, work_kind: str, warranty_months: int, warranty_days: int) -> dict:
    """Prüft die Eingabe, liefert den Vorschlag für Vertragsgrundlage und Leistungsart."""
    if work_kind not in WORK_KINDS:
        raise ValueError(f"Unbekannte Leistungsart: {work_kind!r}.")
    if not 0 <= warranty_months <= MAX_MONTHS:
        raise ValueError(f"Die Monate müssen zwischen 0 und {MAX_MONTHS} liegen.")
    if not 0 <= warranty_days <= MAX_DAYS:
        raise ValueError(f"Die Tage müssen zwischen 0 und {MAX_DAYS} liegen.")
    if warranty_months == 0 and warranty_days == 0:
        raise ValueError("Eine Gewährleistungsdauer von 0 Monaten und 0 Tagen ist keine Festlegung.")
    proposal = warranty_proposal(order.contract_basis, work_kind)
    if proposal is None:
        raise ValueError(f"Für die Vertragsgrundlage {order.contract_basis!r} gibt es keinen Vorschlag.")
    return proposal


def _is_set(order: Order) -> bool:
    return order.work_kind is not None or order.warranty_months is not None or order.warranty_days is not None


def warranty_shifts(db: Session, order: Order, warranty_months: int, warranty_days: int) -> list[dict]:
    """Je nicht verworfene, abgenommene Abnahme des Auftrags: Gewährleistungsende bisher (None, wenn die Dauer noch
    nicht festgelegt war) und mit der neuen Dauer -- beide aus acceptance_warranty(), mit Prüfstatus (seit 1.8.48)."""
    from .acceptances import SCOPES, acceptance_warranty, verify_acceptance
    from .models import OrderAcceptance

    rows = db.scalars(
        select(OrderAcceptance)
        .where(OrderAcceptance.order_id == order.id, OrderAcceptance.discarded_at.is_(None),
               OrderAcceptance.result == "abgenommen")
        .order_by(OrderAcceptance.accepted_on, OrderAcceptance.id)
    ).all()
    shifts = []
    for a in rows:
        check = verify_acceptance(a)
        old = acceptance_warranty(a, order, check)["end"]
        new = acceptance_warranty(a, order, check, duration=(warranty_months, warranty_days))
        shifts.append({"acceptance_id": a.id, "accepted_on": a.accepted_on.isoformat(),
                       "scope_label": SCOPES.get(a.scope, a.scope), "scope_description": a.scope_description,
                       "old_end": old.isoformat() if old else None, "new_end": new["end"].isoformat(),
                       "check": new["check"]})
    return shifts


def _reason_needed_after_acceptance(db: Session, order: Order) -> bool:
    from .acceptances import has_active_acceptance

    return has_active_acceptance(db, order.id)


def warranty_change_preview(db: Session, order: Order, *, work_kind: str, warranty_months: int,
                            warranty_days: int) -> dict:
    """Was eine Festlegung bewirken würde (seit 1.8.47) -- liest nur: Vorschlag, ob eine Begründung nötig ist und
    welche Gewährleistungsenden sich verschieben (bzw. bei der ersten Festlegung entstehen)."""
    proposal = _check_values(order, work_kind, warranty_months, warranty_days)
    follows = (warranty_months, warranty_days) == (proposal["months"], proposal["days"])
    after_acceptance = _reason_needed_after_acceptance(db, order)
    change_after_acceptance = after_acceptance and _is_set(order)
    return {
        "work_kind": work_kind, "work_kind_label": work_kind_label(work_kind),
        "warranty_text": duration_text(warranty_months, warranty_days),
        "proposal": proposal, "follows_proposal": follows,
        "after_acceptance": after_acceptance,
        "reason_required": (not follows) or change_after_acceptance,
        "reason_why": [why for why, needed in (
            ("weicht vom Vorschlag ab", not follows),
            ("Änderung nach einer Abnahme", change_after_acceptance)) if needed],
        "unchanged": (order.work_kind, order.warranty_months, order.warranty_days)
                     == (work_kind, warranty_months, warranty_days),
        "shifts": warranty_shifts(db, order, warranty_months, warranty_days),
    }


def set_order_warranty(
    db: Session, order: Order, *, work_kind: str, warranty_months: int, warranty_days: int, reason: str | None,
    actor_name: str = "System",
) -> OrderWarrantyChange:
    """Leistungsart und Gewährleistungsdauer festlegen. Entspricht die Dauer dem Vorschlag für die Vertragsgrundlage
    des Auftrags und die Leistungsart, ist das die bewusste Übernahme; sonst ist die Begründung Pflicht. Seit 1.8.47
    ebenso, wenn schon eine nicht verworfene Abnahme besteht und Leistungsart oder Dauer bereits festgelegt waren; die
    verschobenen Enden stehen dann in der Historie. Sperrt die Zeile des Auftrags wie das Erfassen einer Abnahme."""
    from .acceptances import lock_order

    proposal = _check_values(order, work_kind, warranty_months, warranty_days)
    text = _clean(reason)
    if text is not None and len(text) > MAX_REASON_LENGTH:
        raise ValueError(f"Die Begründung darf höchstens {MAX_REASON_LENGTH} Zeichen lang sein.")
    follows = (warranty_months, warranty_days) == (proposal["months"], proposal["days"])
    if not follows and text is None:
        raise ValueError(
            f"Die Dauer weicht vom Vorschlag ab ({proposal['text']}, {proposal['citation']}) – bitte eine Begründung "
            "angeben (z. B. im Vertrag vereinbart)."
        )
    lock_order(db, order.id)
    db.refresh(order)
    after_acceptance = _reason_needed_after_acceptance(db, order)
    problem = None
    if (order.work_kind, order.warranty_months, order.warranty_days) == (work_kind, warranty_months, warranty_days):
        problem = "Leistungsart und Gewährleistungsdauer sind bereits so festgelegt."
    elif after_acceptance and _is_set(order) and text is None:
        problem = ("Zu diesem Auftrag ist eine Abnahme erfasst – Leistungsart oder Gewährleistungsdauer nur mit "
                   "Begründung ändern (die Gewährleistungsenden verschieben sich).")
    if problem:
        db.rollback()  # Sperre der Auftragszeile freigeben
        raise ValueError(problem)
    shifts = warranty_shifts(db, order, warranty_months, warranty_days) if after_acceptance else None
    change = OrderWarrantyChange(
        order_id=order.id, work_kind=work_kind, warranty_months=warranty_months, warranty_days=warranty_days,
        contract_basis=order.contract_basis, proposal_months=proposal["months"], proposal_days=proposal["days"],
        follows_proposal=follows, reason=text, changed_by_name=actor_name or "System",
        acceptance_shifts=json.dumps(shifts, ensure_ascii=False) if shifts is not None else None,
    )
    db.add(change)
    order.work_kind = work_kind
    order.warranty_months = warranty_months
    order.warranty_days = warranty_days
    db.commit()
    db.refresh(change)
    return change


def warranty_change_to_dict(change: OrderWarrantyChange) -> dict:
    return {
        "id": change.id,
        "order_id": change.order_id,
        "work_kind": change.work_kind,
        "work_kind_label": work_kind_label(change.work_kind),
        "warranty_months": change.warranty_months,
        "warranty_days": change.warranty_days,
        "warranty_text": duration_text(change.warranty_months, change.warranty_days),
        "contract_basis": change.contract_basis,
        "contract_basis_label": contract_basis_label(change.contract_basis),
        "proposal_text": duration_text(change.proposal_months, change.proposal_days),
        "follows_proposal": change.follows_proposal,
        "reason": change.reason,
        "acceptance_shifts": json.loads(change.acceptance_shifts) if change.acceptance_shifts else None,
        "changed_by_name": change.changed_by_name,
        "changed_at": change.changed_at,
    }


def list_warranty_changes(db: Session, order_id: int) -> list[dict]:
    rows = db.scalars(
        select(OrderWarrantyChange).where(OrderWarrantyChange.order_id == order_id).order_by(OrderWarrantyChange.id.desc())
    ).all()
    return [warranty_change_to_dict(r) for r in rows]
