"""Seit 1.9.329 (Lohn L2c-2, Punkt 2; Befund D.2 und D.3 Nr. 3): „Nach dem Versand geändert“ -- je Person und Tag der Unterschied zwischen der
abgelegten Lohndatei, die als Bezug gilt, und der Rechnung von heute (app/lohndatei.py::berechnen()), mit dem Grund aus der Änderungshistorie. Grundlage
fürs Telefonat mit dem Steuerbüro (DATEV führt das Konto, Korrekturen laufen telefonisch). Nur lesend, nichts wird gespeichert.

Bezug (Antworten 1 und 2 des Betriebs zum Befund D): die als gesendet vermerkte Datei des Monats (1.9.328) -- oder, wenn danach „Besprochen“ eine
Abgleich-Zeile abgelegt hat (1.9.330), die jüngste davon. Ohne gesendete Datei keine Liste: „noch nichts versendet“.

Vergleich: beide Seiten in derselben Form -- je Person und Tag die Zeilen (Kennzeichen, Lohnart, Stunden), die Monatszeilen je Person für sich. Eine
Person der Datei findet ihre Person über die Personalnummer, auch über eine frühere (PersonalnummerVergabe); eine Nummer ohne Person bleibt für sich.

Grund (D.3 Nr. 3): die Einträge der Änderungshistorie seit dem Erzeugen des Bezugs -- je Tag die zu Person und Tag (Zeitbuchung, Abwesenheit samt
Ausfalltag), je Person die zur Person (Lohnstammdaten, eigene Sollzeit, Arbeitszeitmodell der Person), und was viele zugleich trifft (Zuordnung,
Arbeitszeitkalender, Arbeitszeitmodell, Feiertage, Bundesland) als ein Satz oben (`allgemein`). Ohne passenden Eintrag: „kein Eintrag in der
Änderungshistorie“."""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

KEIN_VERSAND = "Noch nichts versendet – vermerke an der Datei „An das Steuerbüro gesendet“."
NICHTS_ZU_BESPRECHEN = "Keine Änderung nach dem Versand – nichts zu besprechen."  # seit 1.9.330
OHNE_GRUND = "kein Eintrag in der Änderungshistorie"
NULL = Decimal("0")

# Einträge der Änderungshistorie, die eine Zeile der Lohndatei ändern können -- je Tag, je Person, für viele zugleich
JE_TAG = {"Zeitbuchung": "Zeitbuchung", "Mitarbeiter-Abwesenheit": "Abwesenheit"}
JE_PERSON = {"DATEV-Mitarbeitereinstellung": "Lohnstammdaten", "Eigene Sollzeit": "Eigene Sollzeit",
             "Mitarbeiter-Arbeitszeitmodell": "Arbeitszeitmodell der Person"}
ALLGEMEIN = {"Zuordnung DATEV-Export": "Zuordnung DATEV-Export", "Arbeitszeitkalender": "Arbeitszeitkalender", "Arbeitszeitmodell": "Arbeitszeitmodell",
             "Arbeitszeitmodell-Pausenregel": "Pausenregel", "Feiertag / betriebsfreier Tag": "Feiertage", "Plantafel-Region": "Bundesland"}
TAG_FELDER = {"work_date", "start_date", "end_date"}


@dataclass
class Seite:
    """Eine Seite des Vergleichs: je (Person, Tag) {(Kennzeichen, Lohnart): Stunden}; Tag None = Monatszeile."""
    zeilen: dict = field(default_factory=lambda: defaultdict(dict))
    nummer: dict = field(default_factory=dict)  # Person -> Personalnummer auf dieser Seite


def _stunden(text: str) -> Decimal:
    return Decimal(text.replace(",", "."))


def _h(wert: Decimal) -> str:
    return f"{wert:.2f}".replace(".", ",")


def datei_lesen(inhalt: bytes, monat: date, person_zu) -> Seite:
    """Die Zeilen einer abgelegten Datei (Format von app/lohndatei.py::datei()); person_zu(nummer) gibt die Person (employee_id) oder ("pnr", nummer)."""
    s = Seite()
    for z in inhalt.decode("ascii").split("\r\n")[1:]:
        if not z:
            continue
        f = z.split(";")
        wer = person_zu(f[0])
        s.nummer[wer] = f[0]
        if f[1] == "":  # Monatszeile
            key, eintrag, stunden = (wer, None), (None, f[3] or None), _stunden(f[6])
        else:
            key, eintrag, stunden = (wer, monat.replace(day=int(f[1]))), (f[2], f[3] or None), _stunden(f[4])
        s.zeilen[key][eintrag] = s.zeilen[key].get(eintrag, NULL) + stunden
    return s


def heute_lesen(personen) -> Seite:
    """Die Zeilen, die die Datei heute hätte -- nur Personen mit Zeilen (wie app/lohndatei.py::datei())."""
    s = Seite()
    for p in personen:
        if not p.zeilen:
            continue
        s.nummer[p.employee_id] = p.personalnummer
        for z in p.zeilen:
            key, eintrag = (p.employee_id, z.tag), (z.kennzeichen, z.lohnart)
            s.zeilen[key][eintrag] = s.zeilen[key].get(eintrag, NULL) + z.stunden
    return s


def eintrag_text(eintrag: tuple, stunden: Decimal) -> str:
    kennzeichen, lohnart = eintrag
    if kennzeichen is None:
        return f"Monatszeile {lohnart} {_h(stunden)} h"
    return f"{kennzeichen}/{lohnart} {_h(stunden)} h" if lohnart else f"{kennzeichen} {_h(stunden)} h"


def _texte(zeilen: dict) -> list[str]:
    return [eintrag_text(e, h) for e, h in sorted(zeilen.items(), key=lambda x: (x[0][0] or "", x[0][1] or ""))]


def bezug(db: Session, erster: date):
    """(gesendete Datei, Bezug) des Monats -- der Bezug ist die jüngste Abgleich-Zeile, die nach der gesendeten Datei erzeugt wurde, sonst diese; ohne
    gesendete Datei (None, None)."""
    from .models import Lohndatei
    gesendet = db.scalar(select(Lohndatei).where(Lohndatei.monat == erster, Lohndatei.art == "datei", Lohndatei.versendet_am.is_not(None)))
    if gesendet is None:
        return None, None
    abgleich = db.scalar(select(Lohndatei).where(Lohndatei.monat == erster, Lohndatei.art == "abgleich", Lohndatei.erzeugt_am >= gesendet.erzeugt_am)
                         .order_by(Lohndatei.erzeugt_am.desc(), Lohndatei.id.desc()).limit(1))
    return gesendet, abgleich or gesendet


def _tage(von: date, bis: date) -> set[date]:
    return {von + timedelta(days=i) for i in range((bis - von).days + 1)} if von and bis and von <= bis else set()


def _datum(text) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10]) if text else None
    except ValueError:
        return None


def gruende(db: Session, seit, monat_von: date, monat_bis: date) -> tuple[dict, dict, list[str]]:
    """Die Einträge der Änderungshistorie seit `seit` (naives UTC): ({(Person, Tag): [Text]}, {Person: [Text]}, [Text allgemein]). Ein Text je Datensatz
    und Aktion: „Zeitbuchung geändert · 12.01.2027 10:15 · Anna Admin“. Person und Tage aus dem Schnappschuss (angelegt, gelöscht) oder dem Datensatz
    von heute, dazu alte und neue Werte der Felder für den Tag."""
    from .berlin_time import to_berlin
    from .models import AuditLog, EmployeeAbsence, EmployeePayrollSettings, EmployeeTargetHours, EmployeeWorkTimeModel, TimeEntry

    arten = set(JE_TAG) | set(JE_PERSON) | set(ALLGEMEIN)
    rows = list(db.scalars(select(AuditLog).where(AuditLog.occurred_at >= seit, AuditLog.entity_type.in_(arten)).order_by(AuditLog.id)))
    modelle = {"Zeitbuchung": TimeEntry, "Mitarbeiter-Abwesenheit": EmployeeAbsence, "DATEV-Mitarbeitereinstellung": EmployeePayrollSettings,
               "Eigene Sollzeit": EmployeeTargetHours, "Mitarbeiter-Arbeitszeitmodell": EmployeeWorkTimeModel}
    # je Datensatz: Person und Tage aus einem Schnappschuss, sonst aus dem Datensatz von heute (eine Abfrage je Art)
    schnapp: dict[tuple, dict] = {}
    for r in rows:
        if r.details and r.entity_type in modelle:
            try:
                schnapp[(r.entity_type, r.entity_id)] = json.loads(r.details)
            except ValueError:
                pass
    fehlen: dict[str, set[int]] = defaultdict(set)
    for r in rows:
        if r.entity_type in modelle and (r.entity_type, r.entity_id) not in schnapp and (r.entity_id or "").isdigit():
            fehlen[r.entity_type].add(int(r.entity_id))
    for art, ids in fehlen.items():
        m = modelle[art]
        for obj in db.scalars(select(m).where(m.id.in_(ids))):
            schnapp[(art, str(obj.id))] = {k: (str(v) if isinstance(v, date) else v) for k, v in
                                           (("employee_id", obj.employee_id), ("work_date", getattr(obj, "work_date", None)),
                                            ("start_date", getattr(obj, "start_date", None)), ("end_date", getattr(obj, "end_date", None)))}
    je_tag: dict[tuple, list[str]] = defaultdict(list)
    je_person: dict[int, list[str]] = defaultdict(list)
    allgemein: list[str] = []
    gesehen: set[tuple] = set()
    for r in rows:
        text = f"{(JE_TAG | JE_PERSON | ALLGEMEIN)[r.entity_type]} {r.action} · {to_berlin(r.occurred_at):%d.%m.%Y %H:%M} · {r.actor_name or 'System'}"
        if r.entity_type in ALLGEMEIN:
            if (None, text) not in gesehen:
                gesehen.add((None, text))
                allgemein.append(text)
            continue
        s = schnapp.get((r.entity_type, r.entity_id)) or {}
        try:
            person = int(s.get("employee_id"))
        except (TypeError, ValueError):
            continue
        if r.entity_type in JE_PERSON:
            if (person, text) not in gesehen:
                gesehen.add((person, text))
                je_person[person].append(text)
            continue
        tage = {_datum(s.get("work_date"))} | _tage(_datum(s.get("start_date")), _datum(s.get("end_date")))
        if r.field_name in TAG_FELDER:
            tage |= {_datum(r.old_value), _datum(r.new_value)}
            if r.entity_type == "Mitarbeiter-Abwesenheit":  # ein geänderter Rand verschiebt den Zeitraum: alter und neuer Zeitraum
                tage |= _tage(_datum(r.old_value) if r.field_name == "start_date" else _datum(s.get("start_date")),
                              _datum(r.old_value) if r.field_name == "end_date" else _datum(s.get("end_date")))
        for tag in sorted(t for t in tage if t and monat_von <= t <= monat_bis):
            if (person, tag, text) not in gesehen:
                gesehen.add((person, tag, text))
                je_tag[(person, tag)].append(text)
    return je_tag, je_person, allgemein


def nach_dem_versand(db: Session, erster: date) -> dict:
    """Die Liste „Nach dem Versand geändert“ des Monats (Admin, Büro – Finanzen; der Router prüft):
    {stand: „nichts_versendet“ | „gleich“ | „geaendert“, text, bezug {id, art, erzeugt_am, versendet_am, notiz}, zeilen [...], allgemein [...]}.
    Je Zeile: Person (employee_id oder None, Name, Personalnummer), Tag (None = Monatszeilen bzw. die Nummer), vorher und jetzt (Texte), Gründe."""
    from .lohndatei import abgelegt_dict, berechnen, lesen, monat_ende
    from .models import Employee, PersonalnummerVergabe
    from .time_tracking import employee_name

    erster = erster.replace(day=1)
    gesendet, b = bezug(db, erster)
    if gesendet is None:
        return {"stand": "nichts_versendet", "text": KEIN_VERSAND, "bezug": None, "zeilen": [], "allgemein": [], "anzahl": 0}
    personen = berechnen(db, erster)
    heute = heute_lesen(personen)
    nummern = {p.personalnummer: p.employee_id for p in personen if p.personalnummer}
    frueher = {n: e for n, e in db.execute(select(PersonalnummerVergabe.nummer, PersonalnummerVergabe.employee_id)
                                           .where(PersonalnummerVergabe.employee_id.is_not(None)))}

    def person_zu(nummer: str):
        return nummern.get(nummer) or frueher.get(nummer) or ("pnr", nummer)

    vorher = datei_lesen(lesen(b), erster, person_zu)
    namen = {p.employee_id: p.name for p in personen}
    fehlt = {w for w in vorher.nummer if isinstance(w, int) and w not in namen}
    if fehlt:
        for emp in db.scalars(select(Employee).where(Employee.id.in_(fehlt))):
            namen[emp.id] = employee_name(emp) or f"#{emp.id}"
    je_tag, je_person, allgemein = gruende(db, b.erzeugt_am, erster, monat_ende(erster))

    zeilen = []
    personen_mit = set(vorher.nummer) | set(heute.nummer)
    for wer in personen_mit:
        alt_nr, neu_nr = vorher.nummer.get(wer), heute.nummer.get(wer)
        name = namen.get(wer) if isinstance(wer, int) else None
        kopf = {"employee_id": wer if isinstance(wer, int) else None, "name": name or f"Personalnummer {alt_nr or neu_nr}",
                "personalnummer": neu_nr or alt_nr}
        eigene = []
        if alt_nr and neu_nr and alt_nr != neu_nr:
            eigene.append({**kopf, "tag": None, "art": "nummer", "vorher": [f"Personalnummer {alt_nr}"], "jetzt": [f"Personalnummer {neu_nr}"]})
        tage = {t for (w, t) in set(vorher.zeilen) | set(heute.zeilen) if w == wer}
        for tag in sorted(tage, key=lambda t: (t is None, t or erster)):
            a, n = vorher.zeilen.get((wer, tag), {}), heute.zeilen.get((wer, tag), {})
            if a != n:
                eigene.append({**kopf, "tag": tag, "art": "monat" if tag is None else "tag", "vorher": _texte(a), "jetzt": _texte(n)})
        for z in eigene:
            g = (je_tag.get((wer, z["tag"]), []) if z["tag"] else []) + (je_person.get(wer, []) if isinstance(wer, int) else [])
            z["gruende"] = g or [OHNE_GRUND]
        zeilen += eigene
    zeilen.sort(key=lambda z: (z["name"].casefold(), z["personalnummer"] or "", z["art"] != "nummer", z["tag"] is None, z["tag"] or erster))
    # seit 1.9.330: ist der Bezug eine Abgleich-Zeile („Besprochen“), zählt die Liste ab dort
    seit = "seit „Besprochen“" if b.art == "abgleich" else "nach dem Versand"
    return {"stand": "geaendert" if zeilen else "gleich",
            "text": (f"{len(zeilen)} {'Änderung' if len(zeilen) == 1 else 'Änderungen'} {seit}" if zeilen else f"Keine Änderung {seit}."),
            "bezug": {**abgelegt_dict(b), "gesendet_id": gesendet.id},
            "zeilen": zeilen, "allgemein": allgemein if zeilen else [], "anzahl": len(zeilen)}
