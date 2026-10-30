"""Verlauf der Akte (seit 1.9.127, Stufe 5, R2, Punkt 4; Vorlage bildgrundlage/entwurf_stufe5/akte-verlauf.html).

Ein Strom je Projekt aus dem Änderungsprotokoll (AuditLog, project_id) und dem Versandprotokoll (EmailDispatch, Dokumente des Projekts): Änderungen,
Versand, Zahlungen, Berichte, Status, Termine -- mit Filter nach Art und nach Auftrag.

- Eine Aktion, eine Zeile: Einträge mit demselben Konto, derselben Anfrage (Methode und Pfad) und höchstens GRUPPE_SEKUNDEN auseinander bilden eine
  Gruppe; ein Versand gehört zu der Gruppe desselben Kontos, die höchstens GRUPPE_SEKUNDEN daneben liegt (der Versand schreibt am Dokument mit). Die
  Zeile nennt die Hauptsache (Überschrift), die Einzelheiten stehen aufklappbar darunter -- jede Zeile des Protokolls, lesbar (app/verlauf_namen.py).
- Auftrag: jede Gruppe kennt die Aufträge, die sie betrifft (über die Kennung des Datensatzes, nicht über Text); mit gewähltem Auftrag bleiben dessen
  Gruppen und die projektweiten (Projekt, Dateien, Beteiligte, Termine, Angebot ohne Auftrag).
- Nicht im Strom: Zeitbuchungen (eigene Seite „Zeiten“, sie würden den Verlauf füllen) -- NICHT_IM_STROM.
- Seiten: neueste zuerst, `vor` = Zeitpunkt der ältesten gezeigten Gruppe; je Abruf höchstens ZEILEN_JE_ABRUF Protokollzeilen.
- Zahlungen (seit 1.9.139): ein kurzer Satz je Zeile aus dem Schnappschuss des Anlegens (zahlung_text()), derselbe für Akte und Kunde und auch für
  ältere Zeilen -- im Protokoll selbst (/history) bleibt die Bezeichnung wie bisher.

Die Schwärzung nach Rolle (Löhne, Abwesenheiten, Aufgaben) macht der Router vorher, wie für /api/audit-logs (app/routers/audit.py::sichtbar()).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    AuditLog, Checklist, Defect, Finding, Invoice, InvoiceCharge, InvoiceDefaultStart, InvoiceItem, Order, OrderAcceptance, OrderItem,
    OrderRevision, OrderSection, OrderStatusChange, PaymentAllocation, PlanningSlot, Quote, Reminder, ServiceReport, WorkPreparation,
    WorkPreparationDeliveryNote, WorkPreparationEmployee, WorkPreparationMaterial, WorkPreparationTask, WorkPreparationTeamAssignment,
)
from .payments import money

GRUPPE_SEKUNDEN = 5
ZEILEN_JE_ABRUF = 600
GRENZE_HOECHSTENS = 10_000  # seit 1.9.136: so weit wächst eine Seite, wenn eine einzige Aktion über ZEILEN_JE_ABRUF reicht (zeilen_seite())
ARTEN = ("aenderung", "versand", "zahlung", "bericht", "status", "termin")
ART_NAMEN = {"aenderung": "Änderung", "versand": "Versand", "zahlung": "Zahlung", "bericht": "Bericht", "status": "Status", "termin": "Termin"}
ART_JE_TYP = {
    "Zahlungseingang": "zahlung", "Nebenforderung": "zahlung", "Verzugsbeginn": "zahlung",
    "Einsatzbericht": "bericht", "Befund": "bericht", "Checkliste": "bericht", "Checklisten-Unterschrift": "bericht", "Checklisten-Foto": "bericht",
    "Auftragsstatus": "status",
    "Termin": "termin", "Plantafel-Einsatz": "termin", "Plantafel-Kapazität": "termin",
}
NICHT_IM_STROM = {"Zeitbuchung", "Gruppen-Zeitbuchung", "Gruppenbuchungs-Mitglied"}
# Welche Zeile einer Gruppe die Überschrift trägt: die Art weiter vorn; bei gleicher Art „angelegt“ vor „geändert“.
VORRANG = ("Auftragsstatus", "Auftrag", "Rechnung", "Mahnung", "Zahlungseingang", "Nebenforderung", "Verzugsbeginn", "Abnahme", "Mangel",
           "Einsatzbericht", "Befund", "Checkliste", "Checklisten-Unterschrift", "Angebot", "Arbeitsvorbereitung", "Plantafel-Einsatz", "Termin",
           "Projekt", "Projektbeteiligter", "Projektdatei", "Auftragsposition", "Auftrags-LV-Titel", "Rechnungsposition", "Angebotsposition")
AKTION_SATZ = {"angelegt": "angelegt", "gelöscht": "gelöscht", "verworfen": "verworfen"}
DATEI_ARTEN = frozenset({"Kundendokument", "Projektdatei"})  # seit 1.9.149: eine Datei wird hochgeladen, nicht angelegt (nur im Verlauf; das Protokoll bleibt)


def _aktion_satz(z) -> str:
    return "hochgeladen" if z.action == "angelegt" and z.entity_type in DATEI_ARTEN else AKTION_SATZ[z.action]


@dataclass
class Gruppe:
    zeilen: list = field(default_factory=list)  # AuditLogOut (lesbar, geschwärzt), neueste zuerst
    versand: dict | None = None  # Eintrag des Versandprotokolls (dispatch_to_dict)
    auftraege: set = field(default_factory=set)

    @property
    def zeitpunkt(self) -> datetime:
        zeiten = [z.occurred_at for z in self.zeilen] + ([self.versand["created_at"]] if self.versand else [])
        return max(zeiten)


# --- Aufträge je Protokollzeile ---------------------------------------------------------------------------------------------------------

def _paare(db: Session, stmt) -> dict:
    """Erste Spalte -> zweite Spalte einer Abfrage mit zwei Spalten."""
    return {a: b for a, b in db.execute(stmt)}


def _je_kennung(db: Session, modell, spalte, kennungen) -> dict[int, int]:
    ids = sorted({int(k) for k in kennungen if k and str(k).isdigit()})
    if not ids:
        return {}
    return {a: b for a, b in db.execute(select(modell.id, spalte).where(modell.id.in_(ids))) if b is not None}


def auftraege_je_zeile(db: Session, zeilen) -> dict[int, set[int]]:
    """AuditLog-ID -> Aufträge; je Art eine Abfrage. Ohne Auftrag (Projekt, Dateien, Beteiligte, Termine): leere Menge."""
    je_typ: dict[str, list] = {}
    for z in zeilen:
        je_typ.setdefault(z.entity_type, []).append(z.entity_id)
    karte: dict[str, dict[int, int]] = {}

    def k(typ, modell, spalte):
        karte[typ] = _je_kennung(db, modell, spalte, je_typ.get(typ, []))

    karte["Auftrag"] = {int(i): int(i) for i in je_typ.get("Auftrag", []) if i and str(i).isdigit()}
    k("Auftragsposition", OrderItem, OrderItem.order_id)
    k("Auftrags-LV-Titel", OrderSection, OrderSection.order_id)
    k("Auftragsrevision", OrderRevision, OrderRevision.order_id)
    k("Auftragsstatus", OrderStatusChange, OrderStatusChange.order_id)
    k("Rechnung", Invoice, Invoice.order_id)
    k("Abnahme", OrderAcceptance, OrderAcceptance.order_id)
    k("Mangel", Defect, Defect.order_id)
    k("Einsatzbericht", ServiceReport, ServiceReport.order_id)
    k("Checkliste", Checklist, Checklist.order_id)
    k("Checklisten-Unterschrift", Checklist, Checklist.order_id)  # Kennung der Checkliste
    k("Checklisten-Foto", Checklist, Checklist.order_id)
    k("Arbeitsvorbereitung", WorkPreparation, WorkPreparation.order_id)
    k("Angebot", Quote, Quote.id)  # unten über den Auftrag des Angebots
    # über eine Zwischenstufe
    rechnung_je = lambda modell, typ: {a: b for a, b in db.execute(  # noqa: E731
        select(modell.id, Invoice.order_id).join(Invoice, modell.invoice_id == Invoice.id)
        .where(modell.id.in_(sorted({int(x) for x in je_typ.get(typ, []) if x and str(x).isdigit()}) or [-1])))}
    karte["Rechnungsposition"] = rechnung_je(InvoiceItem, "Rechnungsposition")
    karte["Mahnung"] = rechnung_je(Reminder, "Mahnung")
    karte["Nebenforderung"] = rechnung_je(InvoiceCharge, "Nebenforderung")
    karte["Verzugsbeginn"] = rechnung_je(InvoiceDefaultStart, "Verzugsbeginn")
    av = {"AV-Mitarbeiter": WorkPreparationEmployee, "AV-Aufgabe": WorkPreparationTask, "AV-Material": WorkPreparationMaterial,
          "AV-Team": WorkPreparationTeamAssignment, "AV-Lieferschein": WorkPreparationDeliveryNote}
    for typ, modell in av.items():
        ids = sorted({int(x) for x in je_typ.get(typ, []) if x and str(x).isdigit()})
        karte[typ] = {a: b for a, b in db.execute(select(modell.id, WorkPreparation.order_id)
                                                  .join(WorkPreparation, modell.preparation_id == WorkPreparation.id)
                                                  .where(modell.id.in_(ids or [-1])))}
    slot_ids = sorted({int(x) for t in ("Plantafel-Einsatz", "Plantafel-Kapazität") for x in je_typ.get(t, []) if x and str(x).isdigit()})
    slots = {a: b for a, b in db.execute(select(PlanningSlot.id, WorkPreparation.order_id)
                                         .join(WorkPreparation, PlanningSlot.preparation_id == WorkPreparation.id)
                                         .where(PlanningSlot.id.in_(slot_ids or [-1])))}
    karte["Plantafel-Einsatz"] = karte["Plantafel-Kapazität"] = slots
    angebote = {q: o for q, o in db.execute(select(Order.source_quote_id, Order.id).where(Order.source_quote_id.in_(list(karte["Angebot"]) or [-1])))}
    karte["Angebot"] = angebote
    befunde = sorted({int(x) for x in je_typ.get("Befund", []) if x and str(x).isdigit()})
    karte["Befund"] = {a: b for a, b in db.execute(select(Finding.id, ServiceReport.order_id)
                                                   .join(ServiceReport, Finding.service_report_id == ServiceReport.id)
                                                   .where(Finding.id.in_(befunde or [-1])))}
    zahlungen = sorted({int(x) for x in je_typ.get("Zahlungseingang", []) if x and str(x).isdigit()})
    zahlung_je: dict[int, set[int]] = {}
    for pid, oid in db.execute(select(PaymentAllocation.payment_id, Invoice.order_id).join(Invoice, PaymentAllocation.invoice_id == Invoice.id)
                               .where(PaymentAllocation.payment_id.in_(zahlungen or [-1]))):
        zahlung_je.setdefault(pid, set()).add(oid)
    out: dict[int, set[int]] = {}
    for z in zeilen:
        kennung = int(z.entity_id) if z.entity_id and str(z.entity_id).isdigit() else None
        if z.entity_type == "Zahlungseingang":
            out[z.id] = set(zahlung_je.get(kennung, set()))
        else:
            o = karte.get(z.entity_type, {}).get(kennung)
            out[z.id] = {o} if o is not None else set()
    return out


def auftraege_je_versand(db: Session, eintraege: list[dict]) -> dict[int, set[int]]:
    """Versandeintrag -> Aufträge (Auftrag, Vertrag, Angebot, Rechnung, Mahnung, Checkliste und Briefe)."""
    from .models import OrderContract

    def ids(*arten):
        return sorted({e["document_id"] for e in eintraege if e["document_type"] in arten and e["document_id"] is not None}) or [-1]

    rechnung = _paare(db, select(Invoice.id, Invoice.order_id).where(Invoice.id.in_(ids("rechnung"))))
    mahnung = _paare(db, select(Reminder.id, Invoice.order_id).join(Invoice, Reminder.invoice_id == Invoice.id)
                              .where(Reminder.id.in_(ids("mahnung"))))
    vertrag = _paare(db, select(OrderContract.id, OrderContract.order_id).where(OrderContract.id.in_(ids("vertrag"))))
    angebot = _paare(db, select(Order.source_quote_id, Order.id).where(Order.source_quote_id.in_(ids("angebot"))))
    briefe = ("checkliste", "behinderungsanzeige", "wiederaufnahme", "bedenkenanzeige")
    checkliste = _paare(db, select(Checklist.id, Checklist.order_id).where(Checklist.id.in_(ids(*briefe))))
    out = {}
    for e in eintraege:
        d, typ = e["document_id"], e["document_type"]
        o = {"auftrag": d, "rechnung": rechnung.get(d), "mahnung": mahnung.get(d), "vertrag": vertrag.get(d), "angebot": angebot.get(d)}.get(typ)
        if typ in briefe:
            o = checkliste.get(d)
        out[e["id"]] = {o} if o is not None else set()
    return out


# --- Gruppen ------------------------------------------------------------------------------------------------------------------------------

def zeilen_seite(db: Session, stmt, grenze: int | None = None) -> tuple[list, bool]:
    """Die neuesten Protokollzeilen (stmt: neueste zuerst) bis zur Grenze und ob ältere folgen. Reicht eine einzige Aktion über die Grenze, wächst
    die Grenze (×4), bis die Seite mehr als eine Gruppe hat, nichts mehr folgt oder GRENZE_HOECHSTENS erreicht ist -- seit 1.9.136 (Fund beim
    Verlauf des Kunden): bis dahin warf strom() die einzige, vielleicht unvollständige Gruppe weg, und `vor` zeigte immer wieder auf dieselbe
    Stelle („Ältere laden“ brachte nichts mehr)."""
    grenze = grenze or ZEILEN_JE_ABRUF
    while True:
        zeilen = db.scalars(stmt.limit(grenze + 1)).all()
        weitere = len(zeilen) > grenze
        zeilen = zeilen[:grenze]
        if not weitere or grenze >= GRENZE_HOECHSTENS or len(gruppieren(zeilen, {})) > 1:
            return zeilen, weitere
        grenze = min(grenze * 4, GRENZE_HOECHSTENS)


def _gleiche_aktion(a, b) -> bool:
    return (a.request_path is not None and a.request_path == b.request_path and a.request_method == b.request_method
            and (a.actor_user_id, a.actor_name) == (b.actor_user_id, b.actor_name)
            and abs((a.occurred_at - b.occurred_at).total_seconds()) <= GRUPPE_SEKUNDEN)


def gruppieren(zeilen, auftraege: dict[int, set[int]]) -> list[Gruppe]:
    """zeilen: neueste zuerst. Eine Zeile gehört zur laufenden Gruppe, wenn sie zur ersten Zeile der Gruppe dieselbe Aktion ist."""
    gruppen: list[Gruppe] = []
    for z in zeilen:
        if gruppen and _gleiche_aktion(gruppen[-1].zeilen[0], z):
            g = gruppen[-1]
        else:
            g = Gruppe()
            gruppen.append(g)
        g.zeilen.append(z)
        g.auftraege |= auftraege.get(z.id, set())
    return gruppen


# Art des Dokuments im Versandprotokoll -> Art der Zeile im Änderungsprotokoll (für die Zuordnung eines Versands zu seiner Aktion)
VERSAND_ART = {"rechnung": "Rechnung", "mahnung": "Mahnung", "auftrag": "Auftrag", "angebot": "Angebot", "checkliste": "Checkliste",
               "behinderungsanzeige": "Checkliste", "wiederaufnahme": "Checkliste", "bedenkenanzeige": "Checkliste"}


def _betrifft(g: Gruppe, e: dict) -> bool:
    art = VERSAND_ART.get(e["document_type"])
    return art is not None and any(z.entity_type == art and str(z.entity_id) == str(e["document_id"]) for z in g.zeilen)


def versand_zuordnen(gruppen: list[Gruppe], eintraege: list[dict], auftraege: dict[int, set[int]]) -> list[Gruppe]:
    """Jeder Versand kommt zu einer Gruppe desselben Kontos höchstens GRUPPE_SEKUNDEN daneben -- zuerst zu der, die dasselbe Dokument betrifft,
    sonst zur nächsten --, ohne eine solche als eigene Zeile."""
    frei = [g for g in gruppen if g.versand is None]
    for e in eintraege:
        nah = [g for g in frei if g.zeilen and g.zeilen[0].actor_user_id is not None and g.zeilen[0].actor_user_id == e.get("created_by_user_id")
               and abs((g.zeilen[0].occurred_at - e["created_at"]).total_seconds()) <= GRUPPE_SEKUNDEN]
        if nah:
            g = min(nah, key=lambda x: (not _betrifft(x, e), abs((x.zeilen[0].occurred_at - e["created_at"]).total_seconds())))
            frei.remove(g)
        else:
            g = Gruppe()
            gruppen.append(g)
        g.versand = e
        g.auftraege |= auftraege.get(e["id"], set())
    gruppen.sort(key=lambda g: g.zeitpunkt, reverse=True)
    return gruppen


def _hauptzeile(g: Gruppe):
    def rang(z):
        typ = VORRANG.index(z.entity_type) if z.entity_type in VORRANG else len(VORRANG)
        return (typ, 0 if z.action == "angelegt" else 1 if z.action in AKTION_SATZ else 2)
    return min(g.zeilen, key=rang)


def art(g: Gruppe) -> str:
    if g.versand is not None:
        return "versand"
    return ART_JE_TYP.get(_hauptzeile(g).entity_type, "aenderung")


def _wert(v) -> str:
    return v if v not in (None, "") else "—"


# --- Zahlungen: ein Satzbau für Akte und Kunde (seit 1.9.139) -------------------------------------------------------------------------------

BEGRUENDUNG = " – Begründung: "
TEILE_MIT_ART = {"skonto": "Skonto", "einbehalt": "Einbehalt"}


def _schnappschuss(z) -> dict:
    try:
        d = json.loads(z.details or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def _rechnung_aus_bezeichnung(z) -> str:
    """Die Nummer aus der Bezeichnung einer Zuordnung („… an R-2026-0001“, app/audit.py); der Schnappschuss kennt nur die Kennung."""
    teile = (z.entity_label or "").rsplit(" an ", 1)
    nummer = teile[1].strip() if len(teile) == 2 else ""
    return nummer if nummer and "·" not in nummer else "Rechnung"


def _zurueckgenommen(was: str, d: dict) -> str:
    return f"{was} zurückgenommen" + (f"{BEGRUENDUNG}{d['reason']}" if d.get("reason") else "")


def _zahlung_teile(z) -> tuple[str, str] | None:
    """(Satz, Zusatz) einer Protokollzeile zu Zahlungen, sonst None. Der Zusatz steht in der Zeile darunter, wenn der Satz die Aktion anführt."""
    if z.entity_type != "Zahlungseingang" or z.action != "angelegt":
        return None
    d = _schnappschuss(z)
    try:
        betrag = Decimal(d["amount"])
    except (KeyError, TypeError, InvalidOperation):
        return None
    geld = money(abs(betrag))
    if "kind" in d:  # Zuordnung
        rechnung = _rechnung_aus_bezeichnung(z)
        kind = d["kind"]
        if d.get("reverses_allocation_id"):
            return _zurueckgenommen("Zuordnung", d), f"{geld} {'aus' if kind == 'erstattung' else 'auf'} {rechnung}"
        if kind in TEILE_MIT_ART:
            return f"{TEILE_MIT_ART[kind]} {geld} auf {rechnung}", ""
        if kind == "nebenforderung":
            return f"{geld} auf Nebenforderung von {rechnung} zugeordnet", ""
        if kind == "erstattung":
            return f"Erstattung {geld} gebucht", f"aus {rechnung}"
        return f"{geld} auf {rechnung} zugeordnet", ""
    if "received_on" in d:  # Zahlung
        try:
            tag = date.fromisoformat(d["received_on"]).strftime("%d.%m.%Y")
        except (TypeError, ValueError):
            return None
        if d.get("reverses_payment_id"):  # die Gegenbuchung hat den umgekehrten Betrag: positiv nimmt einen Zahlungsausgang zurück
            if betrag > 0:
                return _zurueckgenommen("Erstattung", d), geld
            return _zurueckgenommen("Zahlungseingang", d), f"{geld} vom {tag}"
        if betrag < 0:
            return f"Erstattung {geld} gebucht", ""
        return f"Zahlungseingang {geld} vom {tag}", ""
    return None


def zahlung_text(z) -> str | None:
    """Der kurze Satz einer Protokollzeile zu Zahlungen, wie er unter „Einzelheiten“ für sich steht; None bei jeder anderen Zeile."""
    teile = _zahlung_teile(z)
    return " · ".join(t for t in teile if t) if teile else None


def _weitere_text(weitere: int) -> str:
    return f"und {weitere} weitere Einzelheit{'en' if weitere != 1 else ''}" if weitere > 0 else ""


def _zahlung_ueberschrift(g: Gruppe) -> tuple[str, str] | None:
    """Überschrift einer Gruppe, deren Hauptsache eine Zahlung ist: die Zahlung selbst, sonst die erste Buchung (in der Akte steht nur, was das Projekt
    betrifft: die Zuordnungen). Darunter ihr Zusatz, sonst die übrigen Buchungen (höchstens zwei), danach „und n weitere“."""
    zeilen = sorted((z for z in g.zeilen if _zahlung_teile(z)), key=lambda z: z.id)
    if not zeilen:
        return None
    kopf = next((z for z in zeilen if "received_on" in _schnappschuss(z)), zeilen[0])
    titel, zusatz = _zahlung_teile(kopf)
    if zusatz:
        return titel, " · ".join(t for t in (zusatz, _weitere_text(len(g.zeilen) - 1)) if t)
    darunter = []
    for z in zeilen:
        if z is not kopf and len(darunter) < 2:
            satz, z_zusatz = _zahlung_teile(z)
            darunter.append(z_zusatz if satz == titel and z_zusatz else satz)  # die Erstattung: die Zahlung nennt schon den Betrag, die Zuordnung die Rechnung
    return titel, " · ".join(t for t in (*darunter, _weitere_text(len(g.zeilen) - 1 - len(darunter))) if t)


def ueberschrift(g: Gruppe) -> tuple[str, str]:
    """(Überschrift, Zeile darunter) einer Gruppe."""
    if g.versand is not None:
        e = g.versand
        nummer = e.get("document_number") or ""
        doku = f"{e['document_type_label']} {nummer}".strip()
        if e.get("manual"):
            titel = f"{doku} zugestellt ({e['channel_label']})" + (f" an {e['to_recipients']}" if e.get("to_recipients") else "")
        else:
            titel = f"{doku} per {e['channel_label']} an {e['to_recipients']}"
        unter = [e["status_label"]]
        if e.get("cc_recipients"):
            unter.append(f"CC {e['cc_recipients']}")
        if e.get("sent_document"):
            unter.append("1 Anhang (PDF)")
        return titel, " · ".join(unter)
    h = _hauptzeile(g)
    if h.entity_type == "Zahlungseingang":
        kurz = _zahlung_ueberschrift(g)
        if kurz:
            return kurz
    typ = h.entity_type_label or h.entity_type
    name = h.entity_label or ""
    if name == typ:  # seit 1.9.137: ohne eigenen Namen steht in der Zeile nur die Art („Kundenwissen Kundenwissen angelegt“)
        name = ""
    if h.entity_type == "Zahlungseingang":  # seit 1.9.139: die Bezeichnung nennt die Zahlung schon („Zahlungseingang Zahlung …“)
        typ = ""
    if h.entity_type == "Auftragsstatus":
        titel = name or typ
        try:  # die Begründung steht im Schnappschuss des Anlegens (details)
            grund = (json.loads(h.details or "{}") or {}).get("reason")
        except ValueError:
            grund = None
        return titel, f"Begründung: {grund}" if grund else ""
    if h.action in AKTION_SATZ:
        titel = f"{typ} {name} {_aktion_satz(h)}".replace("  ", " ").strip()
        if h.action == "verworfen" and h.new_value:
            return titel, f"Begründung: {h.new_value}"
    else:
        feld = h.field_label or h.field_name or ""
        einheit = f" {h.einheit}" if getattr(h, "einheit", None) else ""
        titel = f"{typ} {name}".strip() + (f": {feld} {_wert(h.old_value)} → {_wert(h.new_value)}{einheit}" if feld else f" {h.action}")
    weitere = len(g.zeilen) - 1
    return titel, (f"und {weitere} weitere Einzelheit{'en' if weitere != 1 else ''}" if weitere > 0 else "")


# Seit 1.9.129 (Vorlage akte-verlauf.html): wohin eine Zeile führt -- je Art der Hauptzeile die Seite des Datensatzes
ZIEL_JE_TYP = {"Einsatzbericht": ("/service-reports/{}", "Öffnen"), "Rechnung": ("/invoices/{}", "Öffnen"),
               "Angebot": ("/quotes/{}/edit", "Öffnen"), "Checkliste": ("/checklisten/{}", "Öffnen"),
               # seit 1.9.136 (Verlauf des Kunden, app/kunde_verlauf.py)
               "Objekt": ("/properties/{}", "Öffnen"), "Dachfläche": ("/roof-areas/{}", "Öffnen")}


def ziel(g: Gruppe, befund_berichte: dict[int, int]) -> dict | None:
    """Link der Zeile („Öffnen“, beim Befund „Ansehen“ -- der Bericht, in dem er steht); keiner bei Versand (dort „⋮“), Gelöschtem oder
    einer unbekannten Kennung."""
    if g.versand is not None or not g.zeilen:
        return None
    h = _hauptzeile(g)
    if h.action == "gelöscht" or not str(h.entity_id or "").isdigit():
        return None
    kennung = int(h.entity_id)
    if h.entity_type == "Befund":
        bericht = befund_berichte.get(kennung)
        return {"href": f"/service-reports/{bericht}", "text": "Ansehen"} if bericht else None
    vorlage = ZIEL_JE_TYP.get(h.entity_type)
    return {"href": vorlage[0].format(kennung), "text": vorlage[1]} if vorlage else None


def _einzelheit(z) -> dict:
    """Eine Zeile unter „Einzelheiten“. Seit 1.9.139 trägt eine Zeile zu Zahlungen ihren kurzen Satz (`kurz`) statt der langen Bezeichnung."""
    zeile = z.model_dump()
    kurz = zahlung_text(z)
    if kurz:
        zeile.update(kurz=kurz, entity_label=None)
    elif z.action == "angelegt" and z.entity_type in DATEI_ARTEN:  # seit 1.9.149, wie die Überschrift
        zeile.update(kurz=f"{z.entity_type_label or z.entity_type} {z.entity_label or ''} hochgeladen".strip())
    return zeile


def gruppe_dict(g: Gruppe, auftrag_nummern: dict[int, str], befund_berichte: dict[int, int] | None = None) -> dict:
    titel, unter = ueberschrift(g)
    a = art(g)
    erste = g.zeilen[0] if g.zeilen else None
    return {
        "zeitpunkt": g.zeitpunkt, "art": a, "art_label": ART_NAMEN[a], "titel": titel, "unterzeile": unter,
        "konto": (erste.actor_name if erste is not None else g.versand.get("created_by_name")),
        "auftraege": [{"order_id": o, "order_number": auftrag_nummern.get(o)} for o in sorted(g.auftraege)],
        "einzelheiten": [_einzelheit(z) for z in g.zeilen],
        "versand": g.versand,
        "ziel": ziel(g, befund_berichte or {}),
    }


def strom(db: Session, project_id: int, zeilen, versand: list[dict], *, auftrag: int | None = None, arten=None,
          weitere: bool = False) -> dict:
    """zeilen: lesbare, geschwärzte AuditLogOut des Projekts (neueste zuerst, höchstens ZEILEN_JE_ABRUF); versand: Einträge im selben Zeitraum.
    weitere: es gibt ältere Protokollzeilen -- dann fällt die letzte (vielleicht unvollständige) Gruppe weg und `vor` zeigt auf sie."""
    zeilen = [z for z in zeilen if z.entity_type not in NICHT_IM_STROM]
    je_zeile = auftraege_je_zeile(db, zeilen)
    gruppen = gruppieren(zeilen, je_zeile)
    vor = None
    if weitere and len(gruppen) == 1:  # seit 1.9.136: nur nach GRENZE_HOECHSTENS -- die Gruppe bleibt, weiter mit älteren Zeilen
        vor = min(z.occurred_at for z in gruppen[0].zeilen)
        versand = [e for e in versand if e["created_at"] >= vor]
    elif weitere and gruppen:
        letzte = gruppen.pop()
        vor = max(z.occurred_at for z in letzte.zeilen) + timedelta(microseconds=1)  # der nächste Abruf beginnt mit ihr
        versand = [e for e in versand if e["created_at"] >= vor]
    gruppen = versand_zuordnen(gruppen, versand, auftraege_je_versand(db, versand))
    nummern = _paare(db, select(Order.id, Order.order_number).where(Order.project_id == project_id))
    if auftrag is not None:
        gruppen = [g for g in gruppen if not g.auftraege or auftrag in g.auftraege]
    if arten:
        gruppen = [g for g in gruppen if art(g) in arten]
    befunde = {int(h.entity_id) for g in gruppen if g.zeilen and (h := _hauptzeile(g)).entity_type == "Befund"
               and str(h.entity_id or "").isdigit()}
    from .models import Finding
    befund_berichte = _paare(db, select(Finding.id, Finding.service_report_id).where(Finding.id.in_(befunde))) if befunde else {}
    return {"eintraege": [gruppe_dict(g, nummern, befund_berichte) for g in gruppen], "vor": vor}
