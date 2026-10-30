"""Verlauf des Kunden (seit 1.9.136, Stufe 5, R3, Punkt 1; wie der Verlauf der Akte, app/akte_verlauf.py; Vorlage kunde-zuordnung.html).

Ein Strom je Kunde aus dem Änderungsprotokoll (AuditLog) und dem Versandprotokoll (EmailDispatch): Änderungen am Kunden (Stammdaten samt
Kundennummer, Kategorie, Zahlungsbedingung -- CustomerProfile steht als „Kunde“ im Protokoll), an „Kontakte & Kundenwissen“ (CustomerExtraInfo), an
seinen Objekten und deren Dachflächen, an seinen Anfragen, an seinen Dokumenten (seit 1.9.140: Hochladen, Angaben ändern, Löschen); seine Zahlungen (Eingang, Zuordnung, Erstattung, Zurücknahme); der Versand seiner
Dokumente (aus seinen Projekten und an seinen Objekten, wie /versandprotokoll?kunde=). Eine Zeile je Aktion, Überschrift, Einzelheiten und Seiten
wie in der Akte -- dieselben Funktionen (zeilen_seite(), gruppieren(), gruppe_dict()). Anders als in der Akte steht ein Versand immer als eigene
Zeile: die Zeilen des Dokuments selbst (Rechnung, Angebot …) gehören nicht zum Strom des Kunden, und die nächste Aktion desselben Kontos (etwa eine
Zahlungsbuchung) ist eine andere Sache.

Das Änderungsprotokoll trägt keinen Kunden je Zeile. Eine Zeile gehört zum Kunden über ihre Kennung: der Kunde selbst, die Datensätze, die ihm heute
gehören, und gelöschte, deren Schnappschuss beim Anlegen oder Löschen (details) seine Kennung trägt („customer_id“ bzw. bei Dachflächen
„property_id“ eines seiner Objekte). Wurde eine Kennung einmal gelöscht, gilt sie nur im Zeitfenster des Datensatzes beim Kunden (vom Anlegen bis
zum Löschen): SQLite vergibt die höchste Kennung nach dem Löschen neu -- sonst stünde die Zeile eines anderen Kunden mit derselben Kennung hier (Fund
beim Bau 1.9.136; PostgreSQL vergibt Kennungen nicht neu).
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from . import akte_verlauf
from .akte_verlauf import Gruppe
from .models import AuditLog, CustomerDocument, CustomerExtraInfo, Inquiry, Payment, Property, RoofArea

ARTEN = ("aenderung", "versand", "zahlung")
# Art im Änderungsprotokoll -> (Modell, Spalte mit dem Kunden)
TYPEN = {"Kundenwissen": (CustomerExtraInfo, "customer_id"), "Kundendokument": (CustomerDocument, "customer_id"), "Objekt": (Property, "customer_id"),
         "Anfrage": (Inquiry, "customer_id"), "Zahlungseingang": (Payment, "customer_id")}


def _aus_schnappschuss(db: Session, typ: str, spalte: str, werte) -> dict[str, dict]:
    """Kennung -> {"angelegt": frühester, "gelöscht": spätester Zeitpunkt} der Zeilen `typ`, deren Schnappschuss `"spalte": "<wert>"` trägt --
    auch gelöschte Datensätze."""
    werte = [str(w) for w in werte]
    if not werte:
        return {}
    muster = or_(*[AuditLog.details.like(f'%"{spalte}": "{w}"%') for w in werte])
    out: dict[str, dict] = {}
    for kennung, aktion, zeit in db.execute(select(AuditLog.entity_id, AuditLog.action, AuditLog.occurred_at).where(
            AuditLog.entity_type == typ, AuditLog.action.in_(("angelegt", "gelöscht")), muster)):
        if not kennung:
            continue
        d = out.setdefault(kennung, {})
        d[aktion] = (min if aktion == "angelegt" else max)(d.get(aktion, zeit), zeit)
    return out


def _fenster(db: Session, typ: str, heute: set[str], schnapp: dict[str, dict]) -> dict[str, tuple]:
    """Kennung -> (von, bis): (None, None), wenn die Kennung nie gelöscht wurde; sonst vom Anlegen beim Kunden bis zum Löschen (ein Datensatz von
    heute ohne Ende)."""
    alle = heute | set(schnapp)
    je_geloescht = set(db.scalars(select(AuditLog.entity_id).where(AuditLog.entity_type == typ, AuditLog.action == "gelöscht",
                                                                  AuditLog.entity_id.in_(sorted(alle) or ["-"])).distinct()))
    out = {}
    for kennung in alle:
        if kennung not in je_geloescht:
            out[kennung] = (None, None)
        else:
            s = schnapp.get(kennung, {})
            out[kennung] = (s.get("angelegt"), None if kennung in heute else s.get("gelöscht"))
    return out


def kennungen(db: Session, customer_id: int) -> dict[str, dict[str, tuple]]:
    """Art im Änderungsprotokoll -> Kennung -> Zeitfenster (von, bis; None = offen), die zum Kunden gehören."""
    out = {"Kunde": {str(customer_id): (None, None)}}
    objekte_heute: set[str] = set()
    for typ, (modell, spalte) in TYPEN.items():
        heute = {str(i) for i in db.scalars(select(modell.id).where(getattr(modell, spalte) == customer_id))}
        out[typ] = _fenster(db, typ, heute, _aus_schnappschuss(db, typ, spalte, [customer_id]))
        if typ == "Objekt":
            objekte_heute = heute
    objekte = sorted(int(i) for i in out["Objekt"] if i.isdigit())
    flaechen = {str(i) for i in db.scalars(select(RoofArea.id).where(RoofArea.property_id.in_(sorted(int(i) for i in objekte_heute) or [-1])))}
    out["Dachfläche"] = _fenster(db, "Dachfläche", flaechen, _aus_schnappschuss(db, "Dachfläche", "property_id", objekte))
    return out


def zeilen_bedingung(db: Session, customer_id: int):
    """Die WHERE-Bedingung für die Zeilen des Kunden im Änderungsprotokoll: je Art die Kennungen ohne Fenster in einem IN, die mit Fenster einzeln."""
    teile = []
    for typ, fenster in kennungen(db, customer_id).items():
        offen = sorted(k for k, f in fenster.items() if f == (None, None))
        if offen:
            teile.append(and_(AuditLog.entity_type == typ, AuditLog.entity_id.in_(offen)))
        for kennung, (von, bis) in sorted(fenster.items()):
            if (von, bis) == (None, None):
                continue
            bedingung = [AuditLog.entity_type == typ, AuditLog.entity_id == kennung]
            if von is not None:
                bedingung.append(AuditLog.occurred_at >= von)
            if bis is not None:
                bedingung.append(AuditLog.occurred_at <= bis)
            teile.append(and_(*bedingung))
    return or_(*teile)


def strom(zeilen, versand: list[dict], *, arten=None, weitere: bool = False) -> dict:
    """zeilen: lesbare, geschwärzte AuditLogOut des Kunden (neueste zuerst, höchstens akte_verlauf.ZEILEN_JE_ABRUF); versand: Einträge im selben
    Zeitraum. weitere: es gibt ältere Protokollzeilen -- dann fällt die letzte (vielleicht unvollständige) Gruppe weg und `vor` zeigt auf sie."""
    gruppen = akte_verlauf.gruppieren(zeilen, {})
    vor = None
    if weitere and len(gruppen) == 1:  # nur nach akte_verlauf.GRENZE_HOECHSTENS -- die Gruppe bleibt, weiter mit älteren Zeilen
        vor = min(z.occurred_at for z in gruppen[0].zeilen)
        versand = [e for e in versand if e["created_at"] >= vor]
    elif weitere and gruppen:
        letzte = gruppen.pop()
        vor = max(z.occurred_at for z in letzte.zeilen) + timedelta(microseconds=1)  # der nächste Abruf beginnt mit ihr
        versand = [e for e in versand if e["created_at"] >= vor]
    gruppen += [Gruppe(versand=e) for e in versand]
    gruppen.sort(key=lambda g: g.zeitpunkt, reverse=True)
    if arten:
        gruppen = [g for g in gruppen if akte_verlauf.art(g) in arten]
    return {"eintraege": [akte_verlauf.gruppe_dict(g, {}) for g in gruppen], "vor": vor}
