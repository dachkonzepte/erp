"""Das Arbeitszeitkonto -- seit 1.9.321 (Lohn L2c-1, Punkt 1; Befund L2c, Abschnitte 2 und 11; Antworten B1–B8, B11, B16 des Betriebs, 12.11.2026).

Eine Vorschau: DATEV führt das Arbeitszeitkonto (Entscheidung L0, bestätigt vom Steuerbüro im Nachtrag vom 12.11.2026) -- die Lohndatei schickt nur
Ist-Stunden je Tag, nie eine Sollzeit oder einen Stand; den Stand schickt das Steuerbüro künftig als Datei zurück (Format offen, L2c-4). Bis dahin heißt
die Rechnung hier „vorläufig – maßgeblich ist die Lohnabrechnung“ (VORLAEUFIG). Je Person und Tag aus der Tagesbilanz (app/tagesbilanz.py; die Sollzeit
wechselt wie in DATEV nach Kalenderwoche, KW 18–48 8,00 h, KW 49–17 7,50 h):

    soll        die Sollzeit des Tags (app/sollzeit.py; vor dem Eintritt und nach dem Austritt 0)
    arbeit      die Arbeit des Tags im Lohn: alle Zeitarten, auch Fahrzeit (Antwort 7 aus L2b), je Tag auf 0,25 h -- nur zwischen Eintritt und Austritt
    gutschrift  die Stunden der Posten, die die Regel gutschreibt (REGEL)
    ist         arbeit + gutschrift
    saldo       ist − soll
Je Monat die Summen; Stand = Startwert (LohnStartwert.saldo_stunden, Stand nach dem 31.12.2026) + die Salden ab dem 01.01.2027 (KONTOBEGINN).

Die Regel (REGEL, Antwort B1, seit 1.9.323 nach den Antworten des Steuerbüros) -- was ein Posten der Tagesbilanz im Konto tut:
    gutschrift  zählt mit seinen Stunden zum Ist: der Tag ist neutral, Arbeit daneben ein Plus (B4)
    keine       zählt nicht: die Sollzeit bleibt offen, ein Minus
Wie DATEV: gutgeschrieben wird, was in der Lohndatei eine Zeile hat; ein Tag ohne Zeile ist ein Minus (Steuerbüro, Nachtrag 12.11.2026). Gutgeschrieben:
Feiertag, Tag des Arbeitszeitkalenders (Heiligabend FR, Silvester UU), Urlaub, Sonderurlaub (U/8000, trägt der Betrieb ein), Krankheit, Fortbildung (Arten
Weiterbildung und Berufsschule), Schlechtwetter Winter (WA, Sollzeit − Arbeit -- neutral mit Vermerk: DATEV löst ein Guthaben selbst auf, VERMERK). Ein Minus:
Freizeitausgleich (B3), Unbezahlt (bis 1.9.322 neutral, B2), Schlechtwetter Sommer (bis 1.9.322 neutral, B7), der Altbestand ohne Kategorie -- keine Zeile.
Die Mehrarbeit der Azubis (AA/1900) geht aufs Konto: sie ist Arbeit wie jede andere. Ein betriebsfreier Tag ist kein Posten: ohne Urlaub und ohne Arbeit ein
Minus (B5). Eine neue Kategorie oder Quelle der Tagesbilanz braucht hier eine Zeile (tests/test_v721_arbeitszeitkonto.py); dass die Regel zur Lohndatei
passt, prüft tests/test_v723_arbeitszeitkonto_nachtrag.py an der ausgelieferten Zuordnung.

Wer und wann: nur gewerbliche Mitarbeiter (Employee.employee_group, B8 -- auch Azubis), nur Tage zwischen Eintritt und Austritt, nur Tage vor heute (der
laufende Tag ist nicht fertig). „ohne Startwert – Startwert folgt“ nur, wer am 31.12.2026 beschäftigt war und keinen Saldo hat
(app/lohnkonten.py::am_stichtag_beschaeftigt(), 1.9.320); wer danach eintritt, startet mit 0.

Für viele Personen in einer festen Zahl Abfragen (die Tagesbilanz ab dem Kontobeginn, die Startwerte), unabhängig von Personen, Tagen, Buchungen und
Abwesenheiten. Rollenlos und nur lesend -- wer es sieht, entscheidet der Router (Admin und Büro – Finanzen, B11; „Meine Zeiten“ erst mit L2c-4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

NULL = Decimal("0")
KONTOBEGINN = date(2027, 1, 1)  # der Tag nach dem Stichtag der Startwerte (app/lohnkonten.py::STICHTAG)
GEWERBLICH = "gewerblich"
GUTSCHRIFT, KEINE = "gutschrift", "keine"
OHNE_STARTWERT = "ohne Startwert – Startwert folgt"
VORLAEUFIG = "vorläufig – maßgeblich ist die Lohnabrechnung"  # seit 1.9.323 (bis 1.9.322 „Übersicht -- maßgeblich ist der Stand laut Lohnabrechnung (DATEV).“)
WINTER_VERMERK = "in der Vorschau neutral – DATEV löst ein Guthaben selbst auf"
WINTER_HINWEIS = "Schlechtwetter Winter neutral gerechnet – DATEV löst ein Guthaben selbst auf"

# Die Regel je Quelle der Tagesbilanz, Schlechtwetter je Jahreszeit („schlechtwetter:winter|sommer“ wie die Zuordnung), eine Abwesenheit je Kategorie
# („abwesenheit:<kategorie>“). Seit 1.9.323: gutgeschrieben, was in der Lohndatei eine Zeile hat (Steuerbüro, Nachtrag 12.11.2026)
REGEL = {
    "feiertag": GUTSCHRIFT,  # F / 1012
    "kalender": GUTSCHRIFT,  # Heiligabend FR / 1080, Silvester UU (unbezahlt frei, „Arbeitszeitkonto neutral“ seit 1.9.176)
    "schlechtwetter:winter": GUTSCHRIFT,  # WA / 8195, Ausfall = Sollzeit − Arbeit -- neutral mit Vermerk (DATEV löst ein Guthaben selbst auf)
    "schlechtwetter:sommer": KEINE,  # seit 1.9.323 ein Minus: keine Zeile (bis 1.9.322 neutral, B7)
    "abwesenheit:urlaub": GUTSCHRIFT,  # U / 8000
    "abwesenheit:sonderurlaub": GUTSCHRIFT,  # U / 8000 (Steuerbüro; trägt der Betrieb in der Zuordnung ein -- bis dahin sperrt er die Lohndatei)
    "abwesenheit:krankheit": GUTSCHRIFT,  # K / 1650
    "abwesenheit:fortbildung": GUTSCHRIFT,  # Weiterbildung 1 / 1000, Berufsschule FE (jede andere Art sperrt die Lohndatei)
    "abwesenheit:unbezahlt": KEINE,  # seit 1.9.323 ein Minus: keine Zeile (bis 1.9.322 neutral, B2)
    "abwesenheit:freizeitausgleich": KEINE,  # B3: baut das Konto ab (L0), keine Zeile
    "abwesenheit:unbekannt": KEINE,  # Altbestand ohne Kategorie (vor 1.9.153, nur über die Migration): keine Zeile (bis 1.9.322 gutgeschrieben)
}
VERMERK = {"schlechtwetter:winter": WINTER_VERMERK}


def regel_schluessel(posten, tag: date) -> str:
    from .lohnarten import schlechtwetter_schluessel
    if posten.quelle == "abwesenheit":
        return f"abwesenheit:{posten.kategorie}"
    if posten.quelle == "schlechtwetter":
        return schlechtwetter_schluessel(tag)  # dieselbe Jahreszeit wie die Lohndatei (Dezember bis März Winter)
    return posten.quelle


def wirkung(posten, tag: date) -> str:
    """GUTSCHRIFT oder KEINE für einen Posten der Tagesbilanz an seinem Tag (REGEL)."""
    return REGEL[regel_schluessel(posten, tag)]


@dataclass
class TagSaldo:
    tag: date
    soll: Decimal
    arbeit: Decimal
    gutschrift: Decimal
    posten: list[dict] = field(default_factory=list)  # je Posten: bezeichnung, stunden, gutgeschrieben

    @property
    def ist(self) -> Decimal:
        return self.arbeit + self.gutschrift

    @property
    def saldo(self) -> Decimal:
        return self.ist - self.soll

    def als_dict(self) -> dict:
        return {"tag": self.tag, "soll": self.soll, "arbeit": self.arbeit, "gutschrift": self.gutschrift, "ist": self.ist, "saldo": self.saldo,
                "posten": self.posten}


@dataclass
class MonatSaldo:
    monat: date  # der Erste des Monats
    soll: Decimal = NULL
    arbeit: Decimal = NULL
    gutschrift: Decimal = NULL
    stand: Decimal = NULL  # am Ende des Monats (bzw. am letzten gezählten Tag)

    @property
    def saldo(self) -> Decimal:
        return self.arbeit + self.gutschrift - self.soll

    def als_dict(self) -> dict:
        return {"monat": self.monat.strftime("%Y-%m"), "soll": self.soll, "arbeit": self.arbeit, "gutschrift": self.gutschrift,
                "ist": self.arbeit + self.gutschrift, "saldo": self.saldo, "stand": self.stand}


@dataclass
class Konto:
    employee_id: int
    name: str
    aktiv: bool
    startwert: Decimal | None
    stand_vorher: Decimal = NULL  # vor dem ersten Tag des Zeitraums
    stand: Decimal = NULL  # am letzten gezählten Tag des Zeitraums
    monate: list[MonatSaldo] = field(default_factory=list)
    tage: list[TagSaldo] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    def als_dict(self, *, tage: bool = True) -> dict:
        d = {"employee_id": self.employee_id, "name": self.name, "aktiv": self.aktiv, "startwert": self.startwert, "stand_vorher": self.stand_vorher,
             "stand": self.stand, "monate": [m.als_dict() for m in self.monate], "hinweise": list(self.hinweise)}
        if tage:
            d["tage"] = [t.als_dict() for t in self.tage]
        return d


def _monate(von: date, bis: date) -> list[date]:
    erster, liste = von.replace(day=1), []
    while erster <= bis:
        liste.append(erster)
        erster = (erster + timedelta(days=32)).replace(day=1)
    return liste


def tag_saldo(t) -> TagSaldo:
    """Ein Tag der Tagesbilanz im Konto: Arbeit nur zwischen Eintritt und Austritt, Gutschrift nach der Regel."""
    arbeit = t.arbeit if t.beschaeftigt else NULL
    posten, gutschrift = [], NULL
    for p in t.posten:
        schluessel = regel_schluessel(p, t.tag)
        gut = REGEL[schluessel] == GUTSCHRIFT
        posten.append({"bezeichnung": p.bezeichnung, "stunden": p.stunden, "gutgeschrieben": gut, "vermerk": VERMERK.get(schluessel)})
        if gut:
            gutschrift += p.stunden
    return TagSaldo(t.tag, t.soll, arbeit, gutschrift, posten)


def gezaehlt_bis(heute: date) -> date:
    """Der letzte Tag, der zählt: gestern -- der laufende Tag ist nicht fertig."""
    return heute - timedelta(days=1)


def konten(db: Session, von: date, bis: date, employee_ids=None, *, heute: date | None = None) -> list[Konto]:
    """Die Konten der gewerblichen Personen für den Zeitraum von bis bis (Tage und Monate darin), der Stand ab dem Startwert. Gezählt werden nur Tage
    ab dem Kontobeginn und vor heute. employee_ids: genau diese Personen (nur gewerbliche); ohne Angabe wie die Tagesbilanz (aktiv oder mit
    Buchungen bzw. Abwesenheiten), nach Namen."""
    from .berlin_time import berlin_today
    from .lohnkonten import am_stichtag_beschaeftigt
    from .models import LohnStartwert
    from .tagesbilanz import bilanz
    from .time_tracking import employee_name

    heute = heute or berlin_today()
    von = max(von, KONTOBEGINN)
    bis = max(bis, von)
    ende = min(bis, gezaehlt_bis(heute))  # der letzte gezählte Tag (vor KONTOBEGINN: keiner)
    b = bilanz(db, KONTOBEGINN, max(bis, KONTOBEGINN), employee_ids)
    personen = [e for e in b.personen if e.employee_group == GEWERBLICH]
    startwerte = {s.employee_id: s for s in db.scalars(select(LohnStartwert).where(LohnStartwert.employee_id.in_([e.id for e in personen] or [0])))}

    ergebnis = []
    for emp in sorted(personen, key=lambda e: (not e.active, (e.last_name or "").casefold(), (e.first_name or "").casefold(), e.id)):
        s = startwerte.get(emp.id)
        start = s.saldo_stunden if s is not None else None
        k = Konto(emp.id, employee_name(emp) or f"#{emp.id}", bool(emp.active), start)
        if start is None and am_stichtag_beschaeftigt(b.payrolls.get(emp.id)):
            k.hinweise.append(OHNE_STARTWERT)
        vorher = stand = start or NULL
        monate = {m: MonatSaldo(m) for m in _monate(von, bis)}
        for t, tag in sorted(b.tage[emp.id].items()):
            if t > ende:
                break
            ts = tag_saldo(tag)
            stand += ts.saldo
            if t < von:
                vorher = stand
                continue
            k.tage.append(ts)
            m = monate[t.replace(day=1)]
            m.soll, m.arbeit, m.gutschrift = m.soll + ts.soll, m.arbeit + ts.arbeit, m.gutschrift + ts.gutschrift
        k.stand_vorher, k.stand = vorher, stand
        if any(p["vermerk"] == WINTER_VERMERK and p["stunden"] > 0 for ts in k.tage for p in ts.posten):  # seit 1.9.323
            k.hinweise.append(WINTER_HINWEIS)
        laufend = vorher
        for m in monate.values():
            laufend += m.saldo
            m.stand = laufend
        k.monate = list(monate.values())
        ergebnis.append(k)
    return ergebnis
