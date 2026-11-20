"""Aufbewahrung, Stufe 1: das Archiv (seit 1.10.11, Stufe W1c; docs/archiv/webseite-und-kundenportal.md, „Umsetzung 1.10.11“).

Ein Vorgang ohne Auftrag geht 6 Monate nach dem letzten Kontakt ins Archiv -- nie von selbst, nur nach Vorschau und Bestätigung im Büro (Admin, Büro –
Finanzen). Im Archiv fehlt er in Listen, Suche, Auswahlen und auf „Start“; über seine Kennung bleibt er lesbar; „Zurückholen“ macht ihn wieder normal.

Einheiten (je mit allem, was an ihnen hängt):
    eingang   ein Eingang der Webseite ohne Übernahme (neu oder verworfen mit Grund „Sonstiges“; Spam, Test, Doppelt löscht 1.10.13)
    anfrage   eine Anfrage ohne Projekt, mit ihrem Eingang
    projekt   ein Projekt ohne Auftrag (keine Zeile in orders, auch keine stornierte), kein Mustervorgang -- mit seiner Anfrage und deren Eingang;
              „archiviert“ ist das vorhandene Projects.archived (seit 1.0.94), dazu Zeitpunkt und Konto
    kunde     nur, wenn nichts mehr an ihm hängt: kein Auftrag, kein Projekt mit Auftrag, kein Wartungsvertrag, keine Rechnung, keine Zahlung, kein
              Mustervorgang, kein Eintrag im Adressbuch, kein Vertrag, keine Checkliste und kein Vorgang eines anderen Kunden an seinen Objekten, jede
              seiner Anfragen und jedes Projekt im Archiv oder mit ihm fällig; nie aus dem Adressimport (Antwort F6). Seine Objekte gehen mit ihm.

Letzter Kontakt = der späteste sichere Zeitpunkt (Tag in Berlin) mit seiner Herkunft: Eingang der Webseite, sonst das Anlegen; vergangene Besichtigung;
Kontaktvermerk; Angebot (nicht Entwurf) mit seinem Datum, versendet, zugestellt, Empfang bestätigt; vergangener Termin am Projekt oder Angebot;
Zurückholen aus dem Archiv. Fällig ab = letzter Kontakt + ARCHIV_NACH_MONATEN Monate (Monatsende: der letzte Tag des Monats).

Jede Mengenabfrage nimmt EXISTS bzw. Mengen in Python -- nie NOT IN über eine Spalte, die leer sein darf (Hinweis des Betriebs, 20.11.2026).
"""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.orm import Session

from .berlin_time import berlin_now, berlin_today, to_berlin, utc_jetzt
from .kontaktvermerke import WEGE
from .models import (
    CalendarEvent, Checklist, Contact, Customer, CustomerProfile, DispatchOutcome, EmailDispatch, Inquiry, Invoice, Kontaktvermerk, MaintenanceContract,
    MaintenanceContractItem, Order, Payment, Project, ProjectDocument, Property, PropertyDocument, Quote, QuoteDocumentMeta, Task, TaskColumn, WebAnfrage,
    WebAnfrageDatei,
)

ARCHIV_NACH_MONATEN = 6  # Stufe 1 fest im Code; Stufe 2 macht daraus eine Einstellung
LOESCHEN_GRUENDE = ("spam", "test", "doppelt")  # verworfen mit diesem Grund: nicht ins Archiv, sondern gelöscht (seit 1.10.13, loeschen())
LOESCHEN_NACH_MONATEN = 6  # nach dem Eingang (Vorgabe W1c, Punkt 4); Stufe 2 macht daraus eine Einstellung
ARTEN = ("eingang", "anfrage", "projekt", "kunde")
ART_NAMEN = {"eingang": "Eingang der Webseite", "anfrage": "Anfrage", "projekt": "Projekt", "kunde": "Kunde"}


class NichtGefunden(LookupError):
    """404."""


class NichtImArchiv(ValueError):
    """Zurückholen, was nicht im Archiv ist -- 409."""


class StandGeaendert(ValueError):
    """Gesammelt bestätigt, aber die Liste ist inzwischen eine andere -- 409."""


def monate_spaeter(tag: date, monate: int) -> date:
    """Derselbe Tag n Monate später; gibt es ihn nicht (31.08. + 6), der letzte Tag des Monats."""
    m = tag.month - 1 + monate
    jahr, monat = tag.year + m // 12, m % 12 + 1
    return date(jahr, monat, min(tag.day, calendar.monthrange(jahr, monat)[1]))


@dataclass(frozen=True)
class Kontakt:
    tag: date
    herkunft: str


def _utc_tag(wert: datetime | None) -> date | None:
    return to_berlin(wert).date() if wert else None


def _spaeter(a: Kontakt | None, b: Kontakt | None) -> Kontakt | None:
    if a is None:
        return b
    if b is None:
        return a
    return b if b.tag > a.tag else a


def _als_dict(k: Kontakt | None) -> dict | None:
    return {"tag": k.tag, "herkunft": k.herkunft} if k else None


@dataclass
class Vorgang:
    art: str
    id: int
    nummer: str
    titel: str
    kunde_id: int | None
    archiviert_am: datetime | None
    archiviert_von_user_id: int | None
    kontakt: Kontakt | None = None
    sperren: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    mit: dict = field(default_factory=dict)
    unbearbeitet: bool = False

    @property
    def faellig_ab(self) -> date | None:
        return monate_spaeter(self.kontakt.tag, ARCHIV_NACH_MONATEN) if self.kontakt else None

    def faellig(self, heute: date) -> bool:
        return self.archiviert_am is None and self.faellig_ab is not None and self.faellig_ab <= heute and not self.sperren

    def als_dict(self, heute: date) -> dict:
        return {"art": self.art, "id": self.id, "nummer": self.nummer, "titel": self.titel, "kunde_id": self.kunde_id,
                "letzter_kontakt": _als_dict(self.kontakt), "faellig_ab": self.faellig_ab, "faellig": self.faellig(heute), "sperren": self.sperren,
                "hinweise": self.hinweise, "mit": self.mit, "unbearbeitet": self.unbearbeitet, "archiviert_am": self.archiviert_am}


@dataclass
class KundeStand:
    id: int
    name: str
    kundennummer: str | None
    ort: str | None
    archiviert_am: datetime | None
    archiviert_von_user_id: int | None
    kontakt: Kontakt | None
    gruende: list[str]  # warum er nicht mitgehen kann (leer = er kann)
    vorgaenge: list[Vorgang]

    @property
    def faellig_ab(self) -> date | None:
        return monate_spaeter(self.kontakt.tag, ARCHIV_NACH_MONATEN) if self.kontakt else None

    def faellig(self, heute: date) -> bool:
        if self.archiviert_am is not None or self.gruende or self.faellig_ab is None or self.faellig_ab > heute:
            return False
        return all(v.archiviert_am is not None or v.faellig(heute) for v in self.vorgaenge)


@dataclass
class Stand:
    heute: date
    eingaenge: list[Vorgang]
    vorgaenge: dict[tuple[str, int], Vorgang]
    kunden: dict[int, KundeStand]


def _offene_aufgabe():
    """EXISTS einer offenen Aufgabe am Projekt: nicht archiviert, Spalte nicht „erledigt“ (eine unbekannte Spalte gilt als offen)."""
    erledigt = exists().where(TaskColumn.key == Task.status, TaskColumn.is_done.is_(True))
    return Task.archived.is_(False) & ~erledigt


def berechnen(db: Session) -> Stand:
    """Der ganze Stand in einer festen Zahl Abfragen -- Grundlage für Vorschau, Archiv und das Bestätigen (dort unter den Sperren neu)."""
    heute, jetzt = berlin_today(), berlin_now()
    ohne_auftrag = ~exists().where(Order.project_id == Project.id)

    projekte = db.execute(select(Project.id, Project.project_number, Project.name, Project.customer_id, Project.created_at, Project.archived,
                                 Project.archiviert_am, Project.archiviert_von_user_id, Project.zurueckgeholt_am)
                          .where(Project.is_template.is_(False), ohne_auftrag).order_by(Project.id)).all()
    p_ids = {p.id for p in projekte}
    p_auswahl = select(Project.id).where(Project.is_template.is_(False), ohne_auftrag)
    anfragen = db.execute(select(Inquiry.id, Inquiry.inquiry_number, Inquiry.title, Inquiry.customer_id, Inquiry.project_id, Inquiry.created_at,
                                 Inquiry.visit_at, Inquiry.archiviert_am, Inquiry.archiviert_von_user_id, Inquiry.zurueckgeholt_am)
                          .where(or_(Inquiry.project_id.is_(None), Inquiry.project_id.in_(p_auswahl))).order_by(Inquiry.id)).all()
    webs = db.execute(select(WebAnfrage.id, WebAnfrage.nummer, WebAnfrage.art_name, WebAnfrage.betreff, WebAnfrage.status, WebAnfrage.verworfen_grund,
                             WebAnfrage.eingang_am, WebAnfrage.abgeholt_am, WebAnfrage.inquiry_id, WebAnfrage.archiviert_am,
                             WebAnfrage.archiviert_von_user_id, WebAnfrage.zurueckgeholt_am).order_by(WebAnfrage.id)).all()
    web_je_anfrage = {w.inquiry_id: w for w in webs if w.inquiry_id is not None}
    vermerke = db.execute(select(Kontaktvermerk.inquiry_id, Kontaktvermerk.project_id, Kontaktvermerk.customer_id, Kontaktvermerk.kontakt_am,
                                 Kontaktvermerk.weg).order_by(Kontaktvermerk.kontakt_am, Kontaktvermerk.id)).all()
    vermerk: dict[tuple[str, int], Kontakt] = {}
    for v in vermerke:
        schluessel = ("anfrage", v.inquiry_id) if v.inquiry_id else ("projekt", v.project_id) if v.project_id else ("kunde", v.customer_id)
        vermerk[schluessel] = _spaeter(vermerk.get(schluessel), Kontakt(v.kontakt_am, f"Kontakt vermerkt ({WEGE.get(v.weg, v.weg)})"))

    # Angebote der Projekte ohne Auftrag: Datum (nicht Entwurf), Versand, Zustellung, Empfang bestätigt, Termine
    angebote = db.execute(select(Quote.id, Quote.project_id, Quote.quote_number, Quote.status, QuoteDocumentMeta.quote_date)
                          .outerjoin(QuoteDocumentMeta, QuoteDocumentMeta.quote_id == Quote.id)
                          .where(Quote.project_id.in_(p_auswahl)).order_by(Quote.id)).all()
    angebot_projekt = {a.id: (a.project_id, a.quote_number) for a in angebote}
    q_auswahl = select(Quote.id).where(Quote.project_id.in_(p_auswahl))
    versand = db.execute(select(EmailDispatch.id, EmailDispatch.document_id, EmailDispatch.channel, EmailDispatch.created_at, EmailDispatch.delivered_on)
                         .where(EmailDispatch.document_type == "angebot", EmailDispatch.status == "gesendet",
                                EmailDispatch.document_id.in_(q_auswahl)).order_by(EmailDispatch.id)).all()
    versand_angebot = {d.id: d.document_id for d in versand}
    empfang = db.execute(select(DispatchOutcome.dispatch_id, DispatchOutcome.outcome_on)
                         .where(DispatchOutcome.outcome == "empfangen", DispatchOutcome.dispatch_id.in_(
                             select(EmailDispatch.id).where(EmailDispatch.document_type == "angebot", EmailDispatch.document_id.in_(q_auswahl))))
                         .order_by(DispatchOutcome.id)).all()
    termine = db.execute(select(CalendarEvent.project_id, CalendarEvent.quote_id, CalendarEvent.start_at)
                         .where(or_(CalendarEvent.project_id.in_(p_auswahl), CalendarEvent.quote_id.in_(q_auswahl)), CalendarEvent.start_at <= jetzt)
                         .order_by(CalendarEvent.id)).all()
    projekt_kontakt: dict[int, Kontakt] = {}

    def _p(pid, k):
        if pid is not None:
            projekt_kontakt[pid] = _spaeter(projekt_kontakt.get(pid), k)

    for a in angebote:
        if a.status != "entwurf" and a.quote_date:
            _p(a.project_id, Kontakt(a.quote_date, f"Angebot {a.quote_number} vom {a.quote_date:%d.%m.%Y}"))
    for d in versand:
        pid, nummer = angebot_projekt.get(d.document_id, (None, ""))
        if d.channel == "email":
            _p(pid, Kontakt(_utc_tag(d.created_at), f"Angebot {nummer} per E-Mail versendet"))
        elif d.delivered_on:
            _p(pid, Kontakt(d.delivered_on, f"Angebot {nummer} zugestellt"))
    for e in empfang:
        pid, nummer = angebot_projekt.get(versand_angebot.get(e.dispatch_id), (None, ""))
        _p(pid, Kontakt(e.outcome_on, f"Empfang des Angebots {nummer} bestätigt"))
    for t in termine:
        pid = t.project_id or angebot_projekt.get(t.quote_id, (None, ""))[0]
        _p(pid, Kontakt(t.start_at.date(), "Termin"))

    # Sperren und Mitgehendes je Projekt
    offene = set(db.scalars(select(Task.project_id).where(Task.project_id.in_(p_auswahl), _offene_aufgabe())).all())
    vorlage = set(db.scalars(select(MaintenanceContract.template_project_id).where(MaintenanceContract.template_project_id.in_(p_auswahl))).all()) | set(
        db.scalars(select(MaintenanceContractItem.template_project_id).where(MaintenanceContractItem.template_project_id.in_(p_auswahl))).all())
    zahl_angebote = dict(db.execute(select(Quote.project_id, func.count(Quote.id)).where(Quote.project_id.in_(p_auswahl)).group_by(Quote.project_id)).all())
    zahl_dateien = dict(db.execute(select(ProjectDocument.project_id, func.count(ProjectDocument.id))
                                   .where(ProjectDocument.project_id.in_(p_auswahl)).group_by(ProjectDocument.project_id)).all())
    zahl_fotos = dict(db.execute(select(PropertyDocument.webanfrage_id, func.count(PropertyDocument.id))
                                 .where(PropertyDocument.webanfrage_id.is_not(None)).group_by(PropertyDocument.webanfrage_id)).all())

    def _basis_anfrage(a) -> Kontakt:
        w = web_je_anfrage.get(a.id)
        if w is not None and (w.eingang_am or w.abgeholt_am):
            return Kontakt(_utc_tag(w.eingang_am or w.abgeholt_am), f"Eingang der Webseite {w.nummer}")
        return Kontakt(_utc_tag(a.created_at), f"Anfrage {a.inquiry_number} angelegt")

    def _kontakt_anfrage(a) -> Kontakt:
        k = _basis_anfrage(a)
        if a.visit_at and a.visit_at <= jetzt:
            k = _spaeter(k, Kontakt(a.visit_at.date(), "Besichtigung"))
        k = _spaeter(k, vermerk.get(("anfrage", a.id)))
        if a.zurueckgeholt_am:
            k = _spaeter(k, Kontakt(_utc_tag(a.zurueckgeholt_am), "aus dem Archiv zurückgeholt"))
        return k

    vorgaenge: dict[tuple[str, int], Vorgang] = {}
    anfrage_je_projekt = {}
    for a in anfragen:
        if a.project_id is not None:
            anfrage_je_projekt[a.project_id] = a
            continue
        w = web_je_anfrage.get(a.id)
        v = Vorgang("anfrage", a.id, a.inquiry_number, a.title, a.customer_id, a.archiviert_am, a.archiviert_von_user_id, _kontakt_anfrage(a))
        v.mit = {"fotos": zahl_fotos.get(w.id, 0) if w else 0}
        vorgaenge[("anfrage", a.id)] = v
    for p in projekte:
        a = anfrage_je_projekt.get(p.id)
        k = _kontakt_anfrage(a) if a is not None else Kontakt(_utc_tag(p.created_at), f"Projekt {p.project_number} angelegt")
        k = _spaeter(k, projekt_kontakt.get(p.id))
        k = _spaeter(k, vermerk.get(("projekt", p.id)))
        if p.zurueckgeholt_am:
            k = _spaeter(k, Kontakt(_utc_tag(p.zurueckgeholt_am), "aus dem Archiv zurückgeholt"))
        im_archiv = p.archiviert_am or (datetime.min if p.archived else None)  # manuell archiviert vor 1.10.11: im Archiv, Zeitpunkt unbekannt
        v = Vorgang("projekt", p.id, p.project_number, p.name, p.customer_id, im_archiv, p.archiviert_von_user_id, k)
        if p.id in offene:
            v.sperren.append("offene Aufgabe am Projekt")
        if p.id in vorlage:
            v.sperren.append("Vorlage eines Wartungsvertrags")
        w = web_je_anfrage.get(a.id) if a is not None else None
        v.mit = {"angebote": zahl_angebote.get(p.id, 0), "dateien": zahl_dateien.get(p.id, 0), "fotos": zahl_fotos.get(w.id, 0) if w else 0}
        vorgaenge[("projekt", p.id)] = v

    eingaenge: list[Vorgang] = []
    for w in webs:
        if w.inquiry_id is not None or w.status not in ("neu", "verworfen") or (w.status == "verworfen" and w.verworfen_grund in LOESCHEN_GRUENDE):
            continue
        k = Kontakt(_utc_tag(w.eingang_am or w.abgeholt_am), "Eingang der Webseite")
        if w.zurueckgeholt_am:
            k = _spaeter(k, Kontakt(_utc_tag(w.zurueckgeholt_am), "aus dem Archiv zurückgeholt"))
        v = Vorgang("eingang", w.id, w.nummer, w.betreff or w.art_name or "", None, w.archiviert_am, w.archiviert_von_user_id, k,
                    unbearbeitet=w.status == "neu")
        v.mit = {"fotos": zahl_fotos.get(w.id, 0)}
        eingaenge.append(v)

    kunden = _kunden(db, heute, vorgaenge, vermerk)
    return Stand(heute, eingaenge, vorgaenge, kunden)


def _kunden(db: Session, heute: date, vorgaenge: dict, vermerk: dict) -> dict[int, KundeStand]:
    """Je Kunde mit einem Vorgang ohne Auftrag (oder ohne jeden Vorgang): kann er mitgehen, und sein letzter Kontakt."""
    mit_auftrag: set[int] = set()
    for abfrage in (select(Order.customer_id).order_by(Order.id), select(MaintenanceContract.customer_id).order_by(MaintenanceContract.id),
                    select(Invoice.customer_id).where(Invoice.customer_id.is_not(None)).order_by(Invoice.id), select(Payment.customer_id).order_by(Payment.id),
                    select(Project.customer_id).where(exists().where(Order.project_id == Project.id)).order_by(Project.id)):
        mit_auftrag |= set(db.scalars(abfrage).all())
    muster = set(db.scalars(select(Project.customer_id).where(Project.is_template.is_(True)).order_by(Project.id)).all())
    adressbuch = set(db.scalars(select(Contact.customer_id).where(Contact.customer_id.is_not(None)).order_by(Contact.id)).all())
    # Objekte: was an ihnen hängt -- Vertrag, Checkliste, ein Vorgang (nicht im Archiv) eines anderen Kunden
    objekt_kunde = dict(db.execute(select(Property.id, Property.customer_id).order_by(Property.id)).all())
    objekt_belegt: dict[int, set[str]] = {}

    def _belege(property_id, grund):
        kid = objekt_kunde.get(property_id)
        if kid is not None:
            objekt_belegt.setdefault(kid, set()).add(grund)

    for pid in db.scalars(select(MaintenanceContract.property_id).where(MaintenanceContract.property_id.is_not(None))
                          .order_by(MaintenanceContract.id)).all():
        _belege(pid, "Wartungsvertrag an einem Objekt")
    for pid in db.scalars(select(Checklist.property_id).where(Checklist.property_id.is_not(None)).order_by(Checklist.id)).all():
        _belege(pid, "Checkliste an einem Objekt")
    for prop, kid in db.execute(select(Project.property_id, Project.customer_id).where(Project.property_id.is_not(None), Project.archived.is_(False))
                                .order_by(Project.id)).all():
        if objekt_kunde.get(prop) not in (None, kid):
            _belege(prop, "Projekt eines anderen Kunden an einem Objekt")
    for prop, kid in db.execute(select(Inquiry.property_id, Inquiry.customer_id).where(Inquiry.property_id.is_not(None),
                                                                                      Inquiry.archiviert_am.is_(None)).order_by(Inquiry.id)).all():
        if objekt_kunde.get(prop) not in (None, kid):
            _belege(prop, "Anfrage eines anderen Kunden an einem Objekt")

    je_kunde: dict[int, list[Vorgang]] = {}
    for v in vorgaenge.values():
        je_kunde.setdefault(v.kunde_id, []).append(v)
    kandidaten = db.execute(select(Customer.id, Customer.name, Customer.city, Customer.created_at, Customer.import_run_id, Customer.legacy_address_number,
                                   Customer.archiviert_am, Customer.archiviert_von_user_id, Customer.zurueckgeholt_am, CustomerProfile.customer_number)
                            .outerjoin(CustomerProfile, CustomerProfile.customer_id == Customer.id).order_by(Customer.id)).all()
    out: dict[int, KundeStand] = {}
    for c in kandidaten:
        if c.id in mit_auftrag:
            continue
        gruende = []
        if c.import_run_id is not None or c.legacy_address_number is not None:
            gruende.append("aus dem Adressimport -- nie automatisch")
        if c.id in muster:
            gruende.append("Kunde eines Mustervorgangs")
        if c.id in adressbuch:
            gruende.append("im Adressbuch verknüpft")
        gruende += sorted(objekt_belegt.get(c.id, ()))
        k = Kontakt(_utc_tag(c.created_at), "Kunde angelegt")
        k = _spaeter(k, vermerk.get(("kunde", c.id)))
        if c.zurueckgeholt_am:
            k = _spaeter(k, Kontakt(_utc_tag(c.zurueckgeholt_am), "aus dem Archiv zurückgeholt"))
        eigene = je_kunde.get(c.id, [])
        for v in eigene:
            if v.kontakt is not None:
                k = _spaeter(k, Kontakt(v.kontakt.tag, f"{ART_NAMEN[v.art]} {v.nummer}: {v.kontakt.herkunft}"))
        out[c.id] = KundeStand(c.id, c.name, c.customer_number, c.city, c.archiviert_am, c.archiviert_von_user_id, k, gruende, eigene)
    return out


def _kunde_dict(kd: KundeStand, heute: date) -> dict:
    return {"id": kd.id, "name": kd.name, "kundennummer": kd.kundennummer, "ort": kd.ort, "letzter_kontakt": _als_dict(kd.kontakt),
            "faellig_ab": kd.faellig_ab, "faellig": kd.faellig(heute), "gruende": kd.gruende, "archiviert_am": kd.archiviert_am}


def _schluessel(stand: Stand) -> list[str]:
    """Was „gesammelt“ archiviert würde -- daraus die Prüfsumme der Vorschau (gesammelt nur genau diese Liste)."""
    heute = stand.heute
    teile = [f"eingang:{v.id}" for v in stand.eingaenge if v.faellig(heute)]
    teile += [f"{v.art}:{v.id}" for v in stand.vorgaenge.values() if v.faellig(heute)]
    teile += [f"kunde:{k.id}" for k in stand.kunden.values() if k.faellig(heute)]
    return sorted(teile)


def stand_summe(stand: Stand) -> str:
    return hashlib.sha256(json.dumps(_schluessel(stand)).encode()).hexdigest()[:16]


def zum_loeschen(db: Session, heute: date | None = None) -> list[dict]:
    """Seit 1.10.13 (Vorgabe W1c, Punkt 4): Eingänge, die als Spam, Test oder Doppelt verworfen sind, 6 Monate nach dem Eingang (ohne Eingangszeit: nach
    dem Abholen) -- nie übernommen und nie mit einem Objektdokument (NOT EXISTS; ein Dokument ohne Eingang zählt nicht). „Sonstiges“ geht ins Archiv."""
    from .webanfragen import VERWERFEN_GRUENDE
    heute = heute or berlin_today()
    zeilen = db.execute(select(WebAnfrage.id, WebAnfrage.nummer, WebAnfrage.betreff, WebAnfrage.verworfen_grund, WebAnfrage.eingang_am,
                               WebAnfrage.abgeholt_am, func.count(WebAnfrageDatei.id).label("dateien"))
                        .outerjoin(WebAnfrageDatei, WebAnfrageDatei.webanfrage_id == WebAnfrage.id)
                        .where(WebAnfrage.status == "verworfen", WebAnfrage.verworfen_grund.in_(LOESCHEN_GRUENDE), WebAnfrage.inquiry_id.is_(None),
                               ~exists().where(PropertyDocument.webanfrage_id == WebAnfrage.id))
                        .group_by(WebAnfrage.id, WebAnfrage.nummer, WebAnfrage.betreff, WebAnfrage.verworfen_grund, WebAnfrage.eingang_am,
                                  WebAnfrage.abgeholt_am)
                        .order_by(WebAnfrage.id)).all()
    out = []
    for z in zeilen:
        eingang = _utc_tag(z.eingang_am or z.abgeholt_am)
        ab = monate_spaeter(eingang, LOESCHEN_NACH_MONATEN)
        if ab <= heute:
            out.append({"art": "eingang", "id": z.id, "nummer": z.nummer, "titel": z.betreff or "", "grund": z.verworfen_grund,
                        "grund_text": VERWERFEN_GRUENDE.get(z.verworfen_grund, z.verworfen_grund), "eingang": eingang, "faellig_ab": ab,
                        "dateien": z.dateien})
    return out


def _summe(teile: list) -> str:
    return hashlib.sha256(json.dumps(teile).encode()).hexdigest()[:16]


def loeschen(db: Session, ids: list[int], user_id: int | None, *, stand: str | None = None) -> dict:
    """Seit 1.10.13: bestätigt löschen -- den Eingang mit seinen Dateien (Zeilen, danach die Dateien im Datenordner), wenn er unter den Sperren noch zum
    Löschen fällig ist; gesammelt (stand gesetzt) nur genau die Liste der Vorschau. Endgültig, kein Zurückholen. Die Historie behält die Zeilen von früher
    (Nummer, Status) und bekommt „gelöscht“ mit Nummer und Grund -- ohne Inhalte."""
    from .audit import record_audit_entry
    from .webanfragen import ART_HISTORIE, datei_pfad
    _sperren(db)
    faellig = {z["id"]: z for z in zum_loeschen(db)}
    if stand is not None:
        if _summe(sorted(faellig)) != stand:
            raise StandGeaendert("Die Liste hat sich geändert – bitte neu laden und noch einmal bestätigen.")
        ids = sorted(faellig)
    geloescht, uebersprungen, pfade = [], [], []
    for wid in sorted(set(ids)):
        z = faellig.get(wid)
        if z is None:
            uebersprungen.append({"art": "eingang", "id": wid, "grund": "nicht (mehr) zum Löschen fällig"})
            continue
        pfade += [datei_pfad(d) for d in db.scalars(select(WebAnfrageDatei).where(WebAnfrageDatei.webanfrage_id == wid).order_by(WebAnfrageDatei.id))]
        db.execute(delete(WebAnfrageDatei).where(WebAnfrageDatei.webanfrage_id == wid))  # zuerst, was auf die Zeile zeigt (Regel 6)
        db.execute(delete(WebAnfrage).where(WebAnfrage.id == wid))
        record_audit_entry(db, action="gelöscht", entity_type=ART_HISTORIE, entity_id=wid, entity_label=z["nummer"], field_name="status",
                           old_value=f"verworfen ({z['grund_text']})", new_value=None, actor_user_id=user_id)
        geloescht.append({"art": "eingang", "id": wid, "nummer": z["nummer"]})
    db.commit()
    for pfad in pfade:
        pfad.unlink(missing_ok=True)
    return {"geloescht": geloescht, "uebersprungen": uebersprungen}


def vorschau(db: Session) -> dict:
    """Was fällig ist (und was zwar die Zeit erreicht hat, aber gesperrt ist), gruppiert je Kunde; Eingänge ohne Übernahme für sich."""
    stand = berechnen(db)
    heute = stand.heute

    def _zeigen(v: Vorgang) -> bool:
        return v.archiviert_am is None and v.faellig_ab is not None and v.faellig_ab <= heute

    eingaenge = [v.als_dict(heute) for v in stand.eingaenge if _zeigen(v)]
    gruppen = []
    for kd in stand.kunden.values():
        eigene = [v.als_dict(heute) for v in kd.vorgaenge if _zeigen(v)]
        if eigene or kd.faellig(heute):
            gruppen.append({**_kunde_dict(kd, heute), "vorgaenge": eigene})
    gruppen.sort(key=lambda g: (g["faellig_ab"] or date.max, g["id"]))
    eingaenge.sort(key=lambda v: (v["faellig_ab"] or date.max, v["id"]))
    zahl = len(_schluessel(stand))
    unbearbeitet = [v for v in stand.eingaenge if v.unbearbeitet and v.faellig(heute)]
    loeschen_liste = zum_loeschen(db, heute)
    return {"heute": heute, "nach_monaten": ARCHIV_NACH_MONATEN, "eingaenge": eingaenge, "kunden": gruppen, "zahl": zahl,
            "unbearbeitet": len(unbearbeitet), "seit": min([v["faellig_ab"] for v in eingaenge if v["faellig"]]
                                                          + [x["faellig_ab"] for g in gruppen for x in g["vorgaenge"] if x["faellig"]]
                                                          + [g["faellig_ab"] for g in gruppen if g["faellig"]], default=None),
            "stand": stand_summe(stand), "loeschen": loeschen_liste, "zahl_loeschen": len(loeschen_liste),
            "stand_loeschen": _summe(sorted(z["id"] for z in loeschen_liste))}


def archiv(db: Session) -> dict:
    """Was im Archiv ist: Eingänge, Anfragen, Projekte, Kunden -- mit Zeitpunkt und Konto."""
    stand = berechnen(db)
    heute = stand.heute
    vorgaenge = [v.als_dict(heute) for v in [*stand.eingaenge, *stand.vorgaenge.values()] if v.archiviert_am is not None]
    for v in vorgaenge:
        if v["archiviert_am"] == datetime.min:
            v["archiviert_am"] = None  # vor 1.10.11 von Hand archiviert
    kunden = [_kunde_dict(k, heute) for k in stand.kunden.values() if k.archiviert_am is not None]
    return {"vorgaenge": sorted(vorgaenge, key=lambda v: (ARTEN.index(v["art"]), v["id"])), "kunden": kunden}


# --- Archivieren und Zurückholen ------------------------------------------------------------------------------------------------------------------

def _einheit_setzen(db: Session, art: str, kennung: int, werte: dict, nur_aktive: bool) -> int:
    """Setzt `werte` an allen Zeilen der Einheit; nur_aktive: nur Zeilen, die noch nicht im Archiv sind (bedingtes UPDATE). Gibt die Zahl der
    geänderten Hauptzeilen zurück."""
    def _upd(modell, bedingung):
        stmt = update(modell).where(bedingung)
        if nur_aktive:
            stmt = stmt.where(modell.archiviert_am.is_(None))
        return db.execute(stmt.values(**werte).execution_options(synchronize_session=False)).rowcount

    if art == "eingang":
        return _upd(WebAnfrage, WebAnfrage.id == kennung)
    if art == "anfrage":
        n = _upd(Inquiry, Inquiry.id == kennung)
        _upd(WebAnfrage, WebAnfrage.inquiry_id == kennung)
        return n
    if art == "projekt":
        projekt = {**werte, "archived": werte["archiviert_am"] is not None}
        stmt = update(Project).where(Project.id == kennung)
        if nur_aktive:
            stmt = stmt.where(Project.archived.is_(False))
        n = db.execute(stmt.values(**projekt).execution_options(synchronize_session=False)).rowcount
        anfrage_ids = db.scalars(select(Inquiry.id).where(Inquiry.project_id == kennung).order_by(Inquiry.id)).all()
        for aid in anfrage_ids:
            _upd(Inquiry, Inquiry.id == aid)
            _upd(WebAnfrage, WebAnfrage.inquiry_id == aid)
        return n
    if art == "kunde":
        return _upd(Customer, Customer.id == kennung)
    raise ValueError(art)


HISTORIE_ART = {"eingang": "Anfrage der Webseite", "anfrage": "Anfrage", "projekt": "Projekt", "kunde": "Kunde"}  # die Arten, die es schon gibt
IM_ARCHIV, AKTIV = "im Archiv", "aktiv"


def _historie(db: Session, art: str, kennung: int, nummer: str, aktion: str) -> None:
    """Eine Zeile je Einheit, ohne Inhalte: Art, Kennung, Nummer, „Archiv: aktiv -> im Archiv“ (bzw. zurück). Unter der Art, die es schon gibt -- so
    stehen sie im Verlauf der Akte (Projekt) und des Kunden (Kunde, Anfrage)."""
    from .audit import record_audit_entry
    gemeinsam = {"entity_type": HISTORIE_ART[art], "entity_id": kennung, "entity_label": nummer, "project_id": kennung if art == "projekt" else None,
                 "field_name": "archiv", "field_label": "Archiv"}
    if aktion == "archiviert":
        record_audit_entry(db, action="archiviert", old_value=AKTIV, new_value=IM_ARCHIV, **gemeinsam)
    else:
        record_audit_entry(db, action="zurückgeholt", old_value=IM_ARCHIV, new_value=AKTIV, **gemeinsam)


def _sperren(db: Session) -> None:
    """Hält die Tabellen der Einheiten, bis bestätigt ist: unter PostgreSQL die Zeilen (FOR UPDATE), unter SQLite schreibt ohnehin nur einer."""
    if db.bind.dialect.name == "postgresql":
        db.execute(select(Project.id).where(Project.is_template.is_(False)).with_for_update())
        db.execute(select(Inquiry.id).with_for_update())
        db.execute(select(WebAnfrage.id).with_for_update())
        db.execute(select(Customer.id).with_for_update())


def archivieren(db: Session, eintraege: list[tuple[str, int]], user_id: int | None, *, stand: str | None = None) -> dict:
    """Bestätigt: archiviert jeden Eintrag, der unter den Sperren noch fällig ist; ein Kunde nimmt seine fälligen Vorgänge mit. Gesammelt (stand gesetzt)
    nur, wenn die Liste dieselbe ist wie in der Vorschau -- sonst StandGeaendert. Gibt {archiviert: [...], uebersprungen: [...]} zurück."""
    _sperren(db)
    s = berechnen(db)
    if stand is not None:
        if stand_summe(s) != stand:
            raise StandGeaendert("Die Liste hat sich geändert – bitte neu laden und noch einmal bestätigen.")
        eintraege = [tuple(x.split(":")) for x in _schluessel(s)]
        eintraege = [(a, int(i)) for a, i in eintraege]
    jetzt = utc_jetzt()
    werte = {"archiviert_am": jetzt, "archiviert_von_user_id": user_id}
    archiviert, uebersprungen = [], []
    eingaenge = {v.id: v for v in s.eingaenge}

    def _vorgang(art, kennung) -> Vorgang | None:
        return eingaenge.get(kennung) if art == "eingang" else s.vorgaenge.get((art, kennung))

    reihe = sorted(set(eintraege), key=lambda e: (ARTEN.index(e[0]) if e[0] in ARTEN else 9, e[1]))
    erledigt: set[tuple[str, int]] = set()
    for art, kennung in reihe:
        if (art, kennung) in erledigt:
            continue
        if art == "kunde":
            kd = s.kunden.get(kennung)
            if kd is None or not kd.faellig(s.heute):
                uebersprungen.append({"art": art, "id": kennung, "grund": _grund_kunde(kd, s.heute)})
                continue
            for v in kd.vorgaenge:
                if v.archiviert_am is None and (v.art, v.id) not in erledigt and _einheit_setzen(db, v.art, v.id, werte, True):
                    _historie(db, v.art, v.id, v.nummer, "archiviert")
                    archiviert.append({"art": v.art, "id": v.id, "nummer": v.nummer})
                    erledigt.add((v.art, v.id))
            if _einheit_setzen(db, "kunde", kennung, werte, True):
                _historie(db, "kunde", kennung, kd.kundennummer or kd.name, "archiviert")
                archiviert.append({"art": "kunde", "id": kennung, "nummer": kd.kundennummer or ""})
            erledigt.add((art, kennung))
            continue
        v = _vorgang(art, kennung)
        if v is None or not v.faellig(s.heute):
            uebersprungen.append({"art": art, "id": kennung, "grund": _grund(v, s.heute)})
            continue
        if _einheit_setzen(db, art, kennung, werte, True):
            _historie(db, art, kennung, v.nummer, "archiviert")
            archiviert.append({"art": art, "id": kennung, "nummer": v.nummer})
        erledigt.add((art, kennung))
    db.commit()
    return {"archiviert": archiviert, "uebersprungen": uebersprungen}


def _grund(v: Vorgang | None, heute: date) -> str:
    if v is None:
        return "nicht gefunden oder hat inzwischen einen Auftrag"
    if v.archiviert_am is not None:
        return "schon im Archiv"
    if v.sperren:
        return "gesperrt: " + ", ".join(v.sperren)
    return f"erst ab {v.faellig_ab:%d.%m.%Y} fällig" if v.faellig_ab else "kein Kontakt bekannt"


def _grund_kunde(kd: KundeStand | None, heute: date) -> str:
    if kd is None:
        return "nicht gefunden oder hat einen Auftrag"
    if kd.archiviert_am is not None:
        return "schon im Archiv"
    if kd.gruende:
        return ", ".join(kd.gruende)
    if kd.faellig_ab and kd.faellig_ab > heute:
        return f"erst ab {kd.faellig_ab:%d.%m.%Y} fällig"
    return "ein Vorgang ist nicht fällig"


def zurueckholen(db: Session, art: str, kennung: int, user_id: int | None) -> dict:
    """Holt eine Einheit aus dem Archiv (bedingt: nur, was im Archiv ist -- sonst NichtImArchiv); ab jetzt zählen wieder 6 Monate. Eine Anfrage oder ein
    Projekt holt ihren Kunden mit, wenn er im Archiv ist."""
    modell = {"eingang": WebAnfrage, "anfrage": Inquiry, "projekt": Project, "kunde": Customer}[art]
    zeile = db.get(modell, kennung, with_for_update=db.bind.dialect.name == "postgresql")
    if zeile is None:
        raise NichtGefunden(f"{ART_NAMEN[art]} nicht gefunden.")
    if art == "anfrage" and zeile.project_id is not None:  # eine Anfrage mit Projekt geht und kommt mit ihrem Projekt
        art, kennung, zeile = "projekt", zeile.project_id, db.get(Project, zeile.project_id)
    im_archiv = zeile.archived if art == "projekt" else zeile.archiviert_am is not None
    if not im_archiv:
        raise NichtImArchiv(f"{ART_NAMEN[art]} ist nicht im Archiv.")
    jetzt = utc_jetzt()
    werte = {"archiviert_am": None, "archiviert_von_user_id": None, "zurueckgeholt_am": jetzt}
    _einheit_zurueck(db, art, kennung, werte)
    nummer = {"eingang": lambda z: z.nummer, "anfrage": lambda z: z.inquiry_number, "projekt": lambda z: z.project_number,
              "kunde": lambda z: z.customer_number or z.name}[art](zeile)
    _historie(db, art, kennung, nummer, "zurückgeholt")
    kunde_id = getattr(zeile, "customer_id", None) if art in ("anfrage", "projekt") else None
    mit_kunde = False
    if kunde_id is not None:
        kunde = db.get(Customer, kunde_id)
        if kunde is not None and kunde.archiviert_am is not None:
            _einheit_zurueck(db, "kunde", kunde_id, werte)
            _historie(db, "kunde", kunde_id, kunde.customer_number or kunde.name, "zurückgeholt")
            mit_kunde = True
    db.commit()
    return {"art": art, "id": kennung, "kunde_mit": mit_kunde}


def _einheit_zurueck(db: Session, art: str, kennung: int, werte: dict) -> None:
    if art == "projekt":
        db.execute(update(Project).where(Project.id == kennung).values(archived=False, **werte).execution_options(synchronize_session=False))
        for aid in db.scalars(select(Inquiry.id).where(Inquiry.project_id == kennung).order_by(Inquiry.id)).all():
            _einheit_setzen(db, "anfrage", aid, werte, False)
        return
    _einheit_setzen(db, art, kennung, werte, False)


def im_archiv(db: Session, art: str, kennung: int) -> bool:
    """Für Kontakt vermerken (409 im Archiv) und die Seiten."""
    if art == "projekt":
        return bool(db.scalar(select(Project.archived).where(Project.id == kennung)))
    modell = {"anfrage": Inquiry, "kunde": Customer, "eingang": WebAnfrage}[art]
    return db.scalar(select(modell.archiviert_am).where(modell.id == kennung)) is not None


def projekt_von_hand(db: Session, project_id: int, archiviert: bool, user_id: int | None) -> None:
    """Archivieren bzw. Entarchivieren über das „⋮“ der Akte (set_project_archived(), seit 1.0.94; dort ist archived schon gesetzt): seit 1.10.11 mit
    Zeitpunkt und Konto; ohne Auftrag gehen Anfrage und Eingang mit; Entarchivieren zählt als Zurückholen und holt einen Kunden im Archiv mit."""
    jetzt = utc_jetzt()
    ohne_auftrag = not db.scalar(select(exists().where(Order.project_id == project_id)))
    if archiviert:
        db.execute(update(Project).where(Project.id == project_id).values(archiviert_am=jetzt, archiviert_von_user_id=user_id)
                   .execution_options(synchronize_session=False))
        if ohne_auftrag:
            for aid in db.scalars(select(Inquiry.id).where(Inquiry.project_id == project_id).order_by(Inquiry.id)).all():
                _einheit_setzen(db, "anfrage", aid, {"archiviert_am": jetzt, "archiviert_von_user_id": user_id}, True)
        return
    werte = {"archiviert_am": None, "archiviert_von_user_id": None, "zurueckgeholt_am": jetzt}
    db.execute(update(Project).where(Project.id == project_id).values(**werte).execution_options(synchronize_session=False))
    for aid in db.scalars(select(Inquiry.id).where(Inquiry.project_id == project_id).order_by(Inquiry.id)).all():
        _einheit_setzen(db, "anfrage", aid, werte, False)
    kunde = db.scalar(select(Customer).join(Project, Project.customer_id == Customer.id).where(Project.id == project_id))
    if kunde is not None and kunde.archiviert_am is not None:
        _einheit_setzen(db, "kunde", kunde.id, werte, False)
        _historie(db, "kunde", kunde.id, kunde.customer_number or kunde.name, "zurückgeholt")
