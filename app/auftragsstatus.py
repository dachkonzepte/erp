"""Status des Auftrags (seit 1.9.124, Stufe 5, R2, Punkt 1).

Ein Auftrag hat nur noch vier Status -- die Phase (Angebot, Auftrag, Ausführung, Abnahme, Schlussrechnung) ergibt sich aus den Daten und steht in
keinem Feld (app/akte.py). Bis 1.9.123 war Order.status freier Text mit sechs Werten der Oberfläche, gesetzt über PUT /api/orders/{id} ohne
Prüfung; beauftragt, arbeitsvorbereitung und in_ausfuehrung gehen in „läuft“ auf (Migration 8d3f6a2c91e7).

    laeuft         Vorgabe, keine Sperre
    pausiert       mit Begründung; sperrt nichts -- Hinweis in Akte und Plantafel, Monteure buchen weiter
    abgeschlossen  nach der Schlussrechnung (bzw. abschließenden Rechnung aus Aufwand) oder mit Begründung „ohne Rechnung“; die Monteurin bucht
                   nicht mehr (das Büro weiter), keine neuen Einsätze, nicht mehr in der Plantafel
    storniert      mit Begründung; dazu keine neuen Berichte -- Rechnungen bleiben möglich (Teilleistung), das Büro bucht weiter

Übergänge nur über status_aendern() (POST /api/orders/{id}/status): pausieren und stornieren aus „läuft“ oder „pausiert“, abschließen aus „läuft“
oder „pausiert“, fortsetzen aus „pausiert“ (ohne Begründung) oder „abgeschlossen“ (mit Begründung). Aus „storniert“ führt nur
storno_zuruecknehmen() (seit 1.9.131, R2 Nachrunde, Punkt 2): zurück auf „läuft“, immer mit Begründung -- wer es darf (nur der Admin), entscheidet
der Router; bis 1.9.130 blieb ein stornierter Auftrag storniert. Unter der Sperre der Auftragszeile (wie Rechnungen, Abnahme, Abgleich), Historie
in OrderStatusChange im selben Commit.

Die Abfragen hier sind rollenlos (Architekturentscheidung „Rollenlose Business-Logik“): wer die Sperre trifft (nur die Monteurin beim Buchen),
entscheidet der Router.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Order, OrderStatusChange

LAEUFT = "laeuft"
PAUSIERT = "pausiert"
ABGESCHLOSSEN = "abgeschlossen"
STORNIERT = "storniert"
STATUS = (LAEUFT, PAUSIERT, ABGESCHLOSSEN, STORNIERT)
NAMEN = {LAEUFT: "läuft", PAUSIERT: "pausiert", ABGESCHLOSSEN: "abgeschlossen", STORNIERT: "storniert"}
GESCHLOSSEN = (ABGESCHLOSSEN, STORNIERT)

# Ziel -> erlaubte Ausgangsstatus
UEBERGAENGE = {
    PAUSIERT: (LAEUFT,),
    LAEUFT: (PAUSIERT, ABGESCHLOSSEN),
    ABGESCHLOSSEN: (LAEUFT, PAUSIERT),
    STORNIERT: (LAEUFT, PAUSIERT),
}
# Name der Aktion je Ziel (Knopf, Rückfrage, Verlauf)
AKTIONEN = {PAUSIERT: "Pausieren", LAEUFT: "Fortsetzen", ABGESCHLOSSEN: "Abschließen", STORNIERT: "Stornieren"}
STORNO_ZURUECK = "Storno zurücknehmen"  # seit 1.9.131: storniert -> läuft, nur über storno_zuruecknehmen()

OHNE_RECHNUNG_TEXT = ("Abschließen geht nach der Schlussrechnung (bzw. der abschließenden Rechnung aus Aufwand) – ohne Rechnung nur mit "
                      "Begründung „ohne Rechnung“.")
# Seit 1.9.124 nach dem „Parkplatz vor dem Echtbetrieb“ (docs/archiv/befund-vor-echtbetrieb.md, 13.10.2026): „ohne Rechnung“ nur, solange
# keine Rechnung existiert -- mit Abschlägen fehlt sonst die Schlussrechnung, die sie verrechnet.
RECHNUNG_DA_TEXT = ("Am Auftrag besteht schon eine Rechnung ({nummern}) – abgeschlossen wird er mit der Schlussrechnung bzw. der "
                    "abschließenden Rechnung aus Aufwand, nicht „ohne Rechnung“.")
EINSATZ_GESPERRT = {
    ABGESCHLOSSEN: "Der Auftrag ist abgeschlossen – neue Einsätze gibt es dafür nicht mehr.",
    STORNIERT: "Der Auftrag ist storniert – neue Einsätze gibt es dafür nicht mehr.",
}
BERICHT_GESPERRT = "Der Auftrag ist storniert – neue Einsatzberichte gibt es dafür nicht mehr."


class StatusKonflikt(ValueError):
    """Der Übergang geht von hier nicht (falscher Ausgangsstatus, Abschließen ohne Schlussrechnung und ohne Begründung, Storno zurücknehmen an
    einem Auftrag, der nicht storniert ist) -- 409."""


class BegruendungFehlt(ValueError):
    """Für diesen Übergang fehlt die Begründung (Fortsetzen eines abgeschlossenen Auftrags, Storno zurücknehmen) -- 422 wie die Pflicht im
    Schema."""


class AuftragGeschlossen(ValueError):
    """Am Auftrag geht das in seinem Status nicht (neuer Einsatz, neuer Bericht) -- 409 mit dem Grund."""


def wert(status: str | None) -> str:
    """Der Status, wie ihn die Regeln lesen: klein, ohne Leerraum; leer gilt als „läuft“ (Vorgabe)."""
    return (status or "").strip().lower() or LAEUFT


def name(status: str | None) -> str:
    """Lesbarer Name („läuft“); ein unbekannter Wert erscheint, wie er ist."""
    return NAMEN.get(wert(status), status or "")


def geschlossen(order: Order | None) -> bool:
    return order is not None and wert(order.status) in GESCHLOSSEN


def offen_bedingung():
    """„nicht geschlossen()“ als Bedingung einer Abfrage (seit 1.9.144): die Plantafel filtert im SQL statt jeden Auftrag zu laden."""
    return func.lower(func.trim(func.coalesce(Order.status, ""))).not_in(GESCHLOSSEN)


def storniert(order: Order | None) -> bool:
    return order is not None and wert(order.status) == STORNIERT


def einsatz_gesperrt(order: Order | None) -> str | None:
    """Warum es keinen neuen Einsatz (Plantafel) gibt -- abgeschlossen oder storniert, sonst None."""
    return EINSATZ_GESPERRT.get(wert(order.status)) if order is not None else None


def bericht_gesperrt(order: Order | None) -> str | None:
    """Warum es keinen neuen Einsatzbericht gibt -- storniert (für jede Rolle), sonst None."""
    return BERICHT_GESPERRT if storniert(order) else None


def naechste(order: Order) -> list[str]:
    """Die Ziele, in die der Auftrag von seinem Status aus wechseln kann (in der Reihenfolge der Knöpfe)."""
    jetzt = wert(order.status)
    return [ziel for ziel in (LAEUFT, PAUSIERT, ABGESCHLOSSEN, STORNIERT) if jetzt in UEBERGAENGE[ziel]]


def begruendung_pflicht(order: Order, ziel: str) -> bool:
    """Ob der Übergang eine Begründung braucht -- pausieren, stornieren, fortsetzen aus „abgeschlossen“; abschließen nur ohne Schlussrechnung
    (das entscheidet status_aendern() unter der Sperre, hier nicht)."""
    return ziel in (PAUSIERT, STORNIERT) or (ziel == LAEUFT and wert(order.status) == ABGESCHLOSSEN)


def rechnungen_am_auftrag(invoices) -> list:
    """Rechnungen, die „ohne Rechnung“ ausschließen: jeder Entwurf und jede festgeschriebene, außer stornierten und ihren Stornos."""
    return [i for i in invoices if i.invoice_type != "storno" and i.status in ("entwurf", "versendet")]


def letzter_wechsel(db: Session, order_id: int) -> OrderStatusChange | None:
    return db.scalar(select(OrderStatusChange).where(OrderStatusChange.order_id == order_id)
                     .order_by(OrderStatusChange.changed_at.desc(), OrderStatusChange.id.desc()).limit(1))


def pause_begruendung(db: Session, order: Order) -> str | None:
    """Die Begründung der Pause, solange der Auftrag pausiert ist (Hinweis in Akte und Plantafel), sonst None."""
    if wert(order.status) != PAUSIERT:
        return None
    letzter = letzter_wechsel(db, order.id)
    return letzter.reason if letzter is not None and letzter.new_status == PAUSIERT else None


def pause_begruendungen(db: Session, orders) -> dict[int, str | None]:
    """pause_begruendung() für viele Aufträge in einer Abfrage (seit 1.9.144, Plantafel) -- je Auftrag zählt der letzte Wechsel."""
    ids = [o.id for o in orders if wert(o.status) == PAUSIERT]
    if not ids:
        return {}
    letzte: dict[int, OrderStatusChange] = {}
    for zeile in db.scalars(select(OrderStatusChange).where(OrderStatusChange.order_id.in_(ids))
                            .order_by(OrderStatusChange.changed_at, OrderStatusChange.id)):
        letzte[zeile.order_id] = zeile
    return {i: letzte[i].reason if i in letzte and letzte[i].new_status == PAUSIERT else None for i in ids}


def wechsel(db: Session, order_id: int) -> list[OrderStatusChange]:
    return list(db.scalars(select(OrderStatusChange).where(OrderStatusChange.order_id == order_id)
                           .order_by(OrderStatusChange.changed_at, OrderStatusChange.id)))


def wechsel_dict(row: OrderStatusChange) -> dict:
    return {
        "id": row.id, "order_id": row.order_id, "old_status": row.old_status, "new_status": row.new_status,
        "old_status_label": name(row.old_status), "new_status_label": name(row.new_status),
        "action": STORNO_ZURUECK if row.old_status == STORNIERT else AKTIONEN.get(row.new_status),
        "reason": row.reason, "without_invoice": bool(row.without_invoice), "changed_at": row.changed_at,
        "changed_by_name": row.changed_by_name,
    }


def abschluss_info(db: Session, order: Order) -> dict:
    """Was „Abschließen“ verlangt (ungesperrt gelesen, zum Anzeigen; status_aendern() prüft unter der Sperre neu): mit Schlussrechnung frei,
    ohne nur ohne jede Rechnung und mit Begründung -- dann mit den gebuchten Stunden, die damit nicht abgerechnet werden."""
    from .invoices import closing_invoices  # lokal, siehe status_aendern()
    from .models import Invoice
    from .time_tracking import summarize_entries

    invoices = list(db.scalars(select(Invoice).where(Invoice.order_id == order.id)))
    if closing_invoices(invoices):
        return {"schlussrechnung": True, "ohne_rechnung": False, "grund": None, "stunden_gebucht": None}
    bestehende = rechnungen_am_auftrag(invoices)
    if bestehende:
        return {"schlussrechnung": False, "ohne_rechnung": False, "stunden_gebucht": None,
                "grund": RECHNUNG_DA_TEXT.format(nummern=", ".join(i.invoice_number or "Entwurf" for i in bestehende))}
    summe = summarize_entries(db, order_id=order.id)
    return {"schlussrechnung": False, "ohne_rechnung": True, "grund": None, "stunden_gebucht": summe["total_hours"]}


def status_info(db: Session, order: Order) -> dict:
    """Für die Akte: Status mit Namen, die Übergänge, die der Server gerade erlaubt (mit Pflicht zur Begründung), und der letzte Wechsel.
    Seit 1.9.130 (R2 Nachrunde, Punkt 1) fehlt „Abschließen“, solange eine Rechnung ohne Schlussrechnung besteht (auch ein Entwurf) -- der Grund
    steht in `abschluss.grund`; über die API bleibt der Übergang 409 (status_aendern() prüft unter der Sperre)."""
    letzter = letzter_wechsel(db, order.id)
    ziele = naechste(order)
    abschluss = abschluss_info(db, order) if ABGESCHLOSSEN in ziele else None
    if abschluss is not None and abschluss["grund"]:
        ziele = [z for z in ziele if z != ABGESCHLOSSEN]
    return {
        "status": wert(order.status), "status_label": name(order.status),
        "aktionen": [{"ziel": z, "name": AKTIONEN[z], "begruendung_pflicht": begruendung_pflicht(order, z)} for z in ziele],
        "abschluss": abschluss,
        # seit 1.9.131: ob sich der Storno zurücknehmen lässt (der Auftrag ist storniert) -- rollenlos; den Eintrag zeigt die Seite nur dem Admin
        "storno_zuruecknehmen": wert(order.status) == STORNIERT,
        "letzter_wechsel": wechsel_dict(letzter) if letzter is not None else None,
    }


def status_aendern(db: Session, order_id: int, ziel: str, begruendung: str | None, *, user_id: int | None = None,
                   user_name: str | None = None) -> Order:
    """Der eine Weg, den Status eines Auftrags zu ändern. Unter der Sperre der Auftragszeile (frisch gelesen), prüft Übergang und Begründung,
    schreibt Status und OrderStatusChange in einem Commit. StatusKonflikt (409), BegruendungFehlt (422), ValueError „nicht gefunden“ (404)."""
    from .invoices import closing_invoices, lock_order_invoices  # lokal: app/invoices.py hängt an vielen Modulen

    if ziel not in STATUS:
        raise BegruendungFehlt(f"Unbekannter Status „{ziel}“.")
    text = (begruendung or "").strip() or None
    invoices = lock_order_invoices(db, order_id)
    order = db.get(Order, order_id)
    if order is None:
        db.rollback()
        raise ValueError("Auftrag nicht gefunden.")
    jetzt = wert(order.status)
    if jetzt == ziel:
        db.rollback()
        raise StatusKonflikt(f"Der Auftrag ist bereits {name(ziel)}.")
    if jetzt not in UEBERGAENGE[ziel]:
        db.rollback()
        if jetzt == STORNIERT:
            raise StatusKonflikt("Der Auftrag ist storniert – zurück geht es nur über „Storno zurücknehmen“ (Admin, mit Begründung).")
        raise StatusKonflikt(f"{AKTIONEN[ziel]} geht aus „{name(jetzt)}“ nicht.")
    if begruendung_pflicht(order, ziel) and text is None:
        db.rollback()
        raise BegruendungFehlt(f"{AKTIONEN[ziel]} braucht eine Begründung.")
    ohne_rechnung = False
    if ziel == ABGESCHLOSSEN and not closing_invoices(invoices):
        bestehende = rechnungen_am_auftrag(invoices)
        if bestehende:
            db.rollback()
            raise StatusKonflikt(RECHNUNG_DA_TEXT.format(nummern=", ".join(i.invoice_number or "Entwurf" for i in bestehende)))
        if text is None:
            db.rollback()
            raise StatusKonflikt(OHNE_RECHNUNG_TEXT)
        ohne_rechnung = True
    return _wechsel_schreiben(db, order, jetzt, ziel, text, ohne_rechnung, user_id=user_id, user_name=user_name)


def storno_zuruecknehmen(db: Session, order_id: int, begruendung: str | None, *, user_id: int | None = None,
                         user_name: str | None = None) -> Order:
    """Seit 1.9.131 (R2 Nachrunde, Punkt 2): einen versehentlichen Storno zurücknehmen -- der Auftrag läuft danach wieder (Einsätze, Berichte,
    Buchungen der Monteurin wie vorher). Nur aus „storniert“, immer mit Begründung; unter der Sperre der Auftragszeile, Historie in
    OrderStatusChange (storniert -> läuft) im selben Commit, im Verlauf mit der Begründung. Wer es darf (nur der Admin), entscheidet der Router.
    StatusKonflikt (409), BegruendungFehlt (422), ValueError „nicht gefunden“ (404)."""
    from .invoices import lock_order_invoices  # lokal, siehe status_aendern()

    text = (begruendung or "").strip() or None
    lock_order_invoices(db, order_id)
    order = db.get(Order, order_id)
    if order is None:
        db.rollback()
        raise ValueError("Auftrag nicht gefunden.")
    jetzt = wert(order.status)
    if jetzt != STORNIERT:
        db.rollback()
        raise StatusKonflikt(f"Der Auftrag ist nicht storniert, sondern {name(jetzt)} – da gibt es keinen Storno zurückzunehmen.")
    if text is None:
        db.rollback()
        raise BegruendungFehlt(f"{STORNO_ZURUECK} braucht eine Begründung.")
    return _wechsel_schreiben(db, order, jetzt, LAEUFT, text, False, user_id=user_id, user_name=user_name)


def _wechsel_schreiben(db: Session, order: Order, jetzt: str, ziel: str, text: str | None, ohne_rechnung: bool, *, user_id: int | None,
                       user_name: str | None) -> Order:
    """Status und OrderStatusChange in einem Commit (der Aufrufer hält die Sperre der Auftragszeile und hat geprüft)."""
    from .audit import current_actor  # lokal: app/audit.py lädt viele Modelle

    akteur_id, akteur_name = current_actor()
    db.add(OrderStatusChange(
        order_id=order.id, old_status=jetzt, new_status=ziel, reason=text, without_invoice=ohne_rechnung,
        changed_by_user_id=user_id if user_id is not None else akteur_id,
        changed_by_name=(user_name or akteur_name or "System")[:160],
    ))
    order.status = ziel
    db.commit()
    db.refresh(order)
    return order
