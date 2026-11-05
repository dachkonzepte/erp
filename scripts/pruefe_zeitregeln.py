"""Prüfung: wie stehen Zeitregeln, Modelle, Personalnummern und Feiertage für den Lohn? (seit 1.9.172, Lohn L1a, Punkt 7)

Vor dem Probemonat (Dezember 2026) und vor dem ersten echten Export: was auf dem Server eingestellt ist, ohne die Seiten einzeln abzugehen
(Befund L0, R5: Stand des Servers unbekannt). Das Skript liest nur und nennt:

    Rundung               der Zeitregeln (Entscheidung Tobias E6: bleibt, bis das Lohnbüro antwortet)
    Arbeitszeitmodelle    Kürzel, Kalenderwochen, Soll Mo–Fr, Pausenregeln, aktiv, Standardmodell; Startmodelle mit den alten Grundwerten
                          (KW 13–43 und 44–12, beide 8,00 h -- die Migration b7e3c91d4a52 stellt nur diese um); Kalenderwochen, die kein aktives
                          Modell deckt oder zwei decken; Pausenregeln, die nicht 6 h -> 30 min und 9 h -> 45 min sind; Personen je Modell
    Personalnummern       je aktive Person: fehlt (obwohl etwas exportiert wird), doppelt, nicht genau 5 Ziffern (bis 1.9.211: 1 bis 5 ohne führende Null) -- bei
                          „DATEV-Nr. = ERP-Nr.“ die ERP-Nummer; seit 1.9.177 die gemerkten Nummern und ob eine aktive Person die Nummer
                          einer anderen trägt; seit 1.9.212 genau 5 Ziffern und je Kreis gezählt; seit 1.9.213 die eingelesenen ohne Person
    Export-Umfang         Anzahl je alles / nur Abwesenheiten / nichts; Eintritt und Austritt; eigene Sollzeiten
    Feiertage             Bundesland, „Feiertage automatisch“, die gesetzlichen Feiertage dieses und des nächsten Jahres
    von Hand              eingetragene betriebsfreie Tage (sie zählen nicht als Feiertag F)
    Arbeitszeitkalender   seit 1.9.175: Tage, die jedes Jahr anders laufen (Heiligabend …) mit Sollzeit, Abwesenheit, für wen; seit 1.9.184
                          die Urlaubsanträge über einen Tag mit Rückfrage (31.12.) ohne Antwort -- vor 1.9.176 angelegt, sie zählen wie der
                          Vorschlag als ganzer Urlaubstag (Festlegung 1.9.176 Nr. 4); nur gezählt, kein Befund
    Zuordnung             Kennzeichen und Lohnart je Eintrag, was nicht exportiert wird; seit 1.9.203 als Befund eine gespeicherte Zeile für
                          eine Art, die nur zu Schlechtwetter passt („art:schlechtwetter“) -- sie wird übergangen, es gilt die Jahreszeit

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung und dem Python des Servers:

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/pruefe_zeitregeln.py

Nur lesen: die Sitzung ist schreibgeschützt (PostgreSQL: SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY, SQLite: PRAGMA query_only), wird
am Ende zurückgerollt. DATABASE_URL muss gesetzt sein (sonst fiele app/database.py still auf SQLite zurück).

Ausgabe ohne Namen: Personen nur mit ihrer Kennung (Mitarbeiter-ID). Rückgabe: 0 nichts zu klären, 1 etwas zu klären (Personalnummer fehlt,
doppelt, falsch oder seit 1.9.177 die gemerkte einer anderen Person, alte Grundwerte, Kalenderwoche ohne aktives Modell, kein Modell, seit 1.9.203
eine übergangene Zuordnung „art:schlechtwetter“), 2 Umgebung fehlt. Hinweise (Zeilen mit „Hinweis:“)
ändern die Rückgabe nicht.
"""

import argparse
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, event, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

GRUNDWERTE = {"summer": (13, 43, Decimal("8.00")), "winter": (44, 12, Decimal("8.00"))}
PAUSEN_ARBZG = [(Decimal("6"), 30), (Decimal("9"), 45)]


@dataclass
class Stand:
    zeilen: list[str] = field(default_factory=list)
    befunde: list[str] = field(default_factory=list)

    def zeile(self, text: str = "") -> None:
        self.zeilen.append(text)

    def befund(self, text: str) -> None:
        self.befunde.append(text)
        self.zeilen.append("  ! " + text)


def _h(wert) -> str:
    return str(Decimal(str(wert)).quantize(Decimal("0.01"))).replace(".", ",")


def _tag(wert: date) -> str:
    return f"{wert:%d.%m.%Y}"


def _modelle(db, stand: Stand) -> None:
    from app.models import EmployeeWorkTimeModel, TimeBackofficeAdvancedSettings, WorkTimeBreakRule, WorkTimeModel, WorkTimeModelValidity
    from app.work_time_models import week_in_range

    erweitert = db.get(TimeBackofficeAdvancedSettings, 1)
    standard = erweitert.default_work_time_model_id if erweitert else None
    gueltig = {v.model_id: (v.valid_from_week, v.valid_to_week) for v in db.scalars(select(WorkTimeModelValidity))}
    regeln: dict[int, list] = {}
    for r in db.scalars(select(WorkTimeBreakRule).order_by(WorkTimeBreakRule.threshold_hours)):
        regeln.setdefault(r.model_id, []).append((Decimal(str(r.threshold_hours)), int(r.break_minutes or 0)))
    personen = Counter(m for (m,) in db.execute(select(EmployeeWorkTimeModel.model_id)))
    modelle = list(db.scalars(select(WorkTimeModel).order_by(WorkTimeModel.sort_order, WorkTimeModel.id)))
    stand.zeile(f"Arbeitszeitmodelle: {len(modelle)}")
    if not modelle:
        stand.befund("Kein Arbeitszeitmodell -- ohne Modell gibt es keine Sollzeit.")
    for m in modelle:
        von, bis = gueltig.get(m.id, (1, 53))
        pausen = " · ".join(f"über {_h(s)} h -> {p} min" for s, p in regeln.get(m.id, [])) or "keine Pausenregeln"
        stand.zeile(f"  Modell {m.id} „{m.name}“ (Kürzel {m.code or '–'}): KW {von}–{bis}, Soll Mo–Fr {_h(m.daily_target_hours)} h, {pausen}, "
                    f"{'aktiv' if m.active else 'inaktiv'}{', Standardmodell' if m.id == standard else ''}, {personen.get(m.id, 0)} Person(en) zugeordnet")
        alt = GRUNDWERTE.get((m.code or "").strip().lower())
        if alt and (von, bis, Decimal(str(m.daily_target_hours))) == (alt[0], alt[1], alt[2]):
            stand.befund(f"Modell {m.id} trägt noch die alten Grundwerte (KW {von}–{bis}, 8,00 h), nicht den Tarif (KW 18–48 8,00 h, KW 49–17 7,50 h).")
        if m.active and regeln.get(m.id, []) != PAUSEN_ARBZG:
            stand.zeile("    Hinweis: Pausenregeln weichen von 6 h -> 30 min und 9 h -> 45 min ab.")
    if standard is None:
        stand.zeile("  Hinweis: kein Standardmodell -- wer kein Modell zugeordnet hat, bekommt das erste für die Woche gültige.")
    aktive = [m for m in modelle if m.active]
    ohne, mehrere = [], []
    for kw in range(1, 54):
        deckt = [m.id for m in aktive if week_in_range(kw, *gueltig.get(m.id, (1, 53)))]
        if not deckt:
            ohne.append(kw)
        elif len(deckt) > 1:
            mehrere.append(kw)
    if ohne:
        stand.befund(f"Kalenderwochen ohne aktives Modell: {_bereiche(ohne)} -- dort keine Sollzeit nach Tarif.")
    if mehrere:
        stand.zeile(f"  Hinweis: Kalenderwochen mit mehreren aktiven Modellen: {_bereiche(mehrere)} -- es gilt das zugeordnete, sonst das Standardmodell, "
                    "sonst das erste.")


def _bereiche(wochen: list[int]) -> str:
    """[1, 2, 3, 7, 49, 50] -> „1–3, 7, 49–50“."""
    teile, start = [], wochen[0]
    for vorher, kw in zip(wochen, wochen[1:] + [None]):
        if kw is None or kw != vorher + 1:
            teile.append(str(start) if vorher == start else f"{start}–{vorher}")
            start = kw
    return ", ".join(teile)


def _personen(db, stand: Stand, heute: date) -> None:
    from app.models import Employee, EmployeePayrollSettings, EmployeeTargetHours, TimeBackofficeAdvancedSettings
    from app.time_backoffice import EXPORT_UMFAENGE, NUMMERNKREISE, PERSONALNUMMER_FORMAT

    erweitert = db.get(TimeBackofficeAdvancedSettings, 1)
    gleich = bool(erweitert and erweitert.datev_personnel_equals_erp_number)
    lohn = {p.employee_id: p for p in db.scalars(select(EmployeePayrollSettings))}
    aktive = list(db.execute(select(Employee.id, Employee.employee_number, Employee.employee_group).where(Employee.active.is_(True))
                             .order_by(Employee.id)))
    stand.zeile(f"Personen (aktiv): {len(aktive)}; DATEV-Nr. = ERP-Nr.: {'ja' if gleich else 'nein'}")
    umfang = Counter()
    nummern: dict[str, list[int]] = {}
    for eid, erp_nr, _gruppe in aktive:
        p = lohn.get(eid)
        u = (p.export_umfang if p is not None and p.export_umfang else "alles")
        umfang[u] += 1
        nummer = ((erp_nr or "").strip() if gleich else ((p.datev_personnel_number if p else None) or "").strip()) or None
        if nummer:
            nummern.setdefault(nummer, []).append(eid)
            if u != "nichts" and not PERSONALNUMMER_FORMAT.match(nummer):
                stand.befund(f"Person {eid}: Personalnummer „{nummer}“ hat nicht genau 5 Ziffern.")  # seit 1.9.212 (bis 1.9.211: 1 bis 5 ohne führende Null)
        elif u != "nichts":
            stand.befund(f"Person {eid}: keine Personalnummer, Export „{EXPORT_UMFAENGE[u]}“.")
    for nummer, ids in nummern.items():
        if len(ids) > 1:
            stand.befund(f"Personalnummer {nummer} tragen {len(ids)} Personen ({', '.join(map(str, ids))}).")
    # seit 1.9.177 (L1a-Nachtrag, Punkt 4): gemerkte Nummern bleiben gesperrt -- trägt eine aktive Person die Nummer einer anderen, ist das ein Befund
    from app.models import PersonalnummerVergabe
    gemerkt = {n: e for n, e in db.execute(select(PersonalnummerVergabe.nummer, PersonalnummerVergabe.employee_id))}
    for nummer, ids in nummern.items():
        fremd = [eid for eid in ids if nummer in gemerkt and gemerkt[nummer] != eid]
        if fremd and gemerkt[nummer] is None:  # seit 1.9.213: eingelesen ohne Person (scripts/personalnummern_einlesen.py)
            stand.befund(f"Personalnummer {nummer} steht in der eingelesenen Liste (ohne Person), heute trägt sie Person {', '.join(map(str, fremd))}.")
        elif fremd:
            stand.befund(f"Personalnummer {nummer} gehörte Person {gemerkt[nummer]}, heute trägt sie Person {', '.join(map(str, fremd))}.")
    stand.zeile(f"  Personalnummern gemerkt (dauerhaft gesperrt): {len(gemerkt)}, davon bei keiner aktiven Person: "
                f"{sum(1 for n in gemerkt if n not in nummern)}")
    ohne = sum(1 for e in gemerkt.values() if e is None)
    if ohne:  # seit 1.9.213
        stand.zeile(f"    davon eingelesen ohne Person: {ohne}")
    # seit 1.9.212 (L1a Stufe 6, Punkt 1): je Kreis des Lohnbüros, wie viele gültige Nummern aktive Personen tragen -- nur gezählt, kein Befund
    # seit 1.9.219 dazu „außerhalb“: über der obersten genutzten Grenze (00299), ebenfalls kein Befund
    kreise = Counter(next((name for von, bis, name, _b in NUMMERNKREISE if von <= int(n) <= bis), "außerhalb") for n in nummern
                     if PERSONALNUMMER_FORMAT.match(n))
    stand.zeile("  Personalnummern je Kreis: " + ", ".join(f"{name} {kreise.get(name, 0)}" for name in [k[2] for k in NUMMERNKREISE] + ["außerhalb"]))
    stand.zeile("  Export-Umfang: " + ", ".join(f"{EXPORT_UMFAENGE[k]} {umfang.get(k, 0)}" for k in EXPORT_UMFAENGE))
    mit_eintritt = sum(1 for eid, _n, _g in aktive if lohn.get(eid) is not None and lohn[eid].eintritt)
    ausgetreten = [eid for eid, _n, _g in aktive if lohn.get(eid) is not None and lohn[eid].austritt and lohn[eid].austritt < heute]
    stand.zeile(f"  Eintritt eingetragen: {mit_eintritt} von {len(aktive)}" + (f"; aktiv, aber ausgetreten: {', '.join(map(str, ausgetreten))}" if ausgetreten else ""))
    eigene = len({eid for (eid,) in db.execute(select(EmployeeTargetHours.employee_id))})
    stand.zeile(f"  Personen mit eigener Sollzeit: {eigene}")


def _feiertage(db, stand: Stand, heute: date) -> None:
    from app.models import PlanningHoliday, PlanningRegionSettings
    from app.planning import automatic_public_holidays

    region = db.get(PlanningRegionSettings, 1)
    land = ((region.federal_state_code if region else None) or "NW").upper()
    stand.zeile(f"Bundesland {land}, Feiertage automatisch: {'an' if (region is None or region.auto_public_holidays) else 'aus'}")
    for jahr in (heute.year, heute.year + 1):
        tage = automatic_public_holidays(land, [jahr])
        stand.zeile(f"  Gesetzliche Feiertage {jahr}: " + ", ".join(f"{_tag(t)} {n}" for t, n in sorted(tage.items())))
    hand = list(db.execute(select(PlanningHoliday.holiday_date, PlanningHoliday.name, PlanningHoliday.active).order_by(PlanningHoliday.holiday_date)))
    stand.zeile(f"Von Hand eingetragene Tage: {len(hand)} (zählen nicht als Feiertag F)")
    for tag, name, aktiv in hand:
        stand.zeile(f"  {_tag(tag)} {name}{'' if aktiv else ' (inaktiv)'}")


def _kalender(db, stand: Stand) -> None:
    """Seit 1.9.175 (L1a-Nachtrag): die Tage des Arbeitszeitkalenders -- kein Befund."""
    from app.models import ArbeitszeitKalendertag
    tage = list(db.scalars(select(ArbeitszeitKalendertag).order_by(ArbeitszeitKalendertag.monat, ArbeitszeitKalendertag.tag)))
    stand.zeile(f"Arbeitszeitkalender: {len(tage)} Tage")
    for e in tage:
        soll = f"Sollzeit {_h(e.sollzeit)} h" if e.sollzeit is not None else "Sollzeit des Modells"
        stand.zeile(f"  {e.tag:02d}.{e.monat:02d}. {e.name}: {soll}, {e.abwesenheit}, im Urlaub {e.im_urlaub}, "
                    f"{'gewerbliche' if e.nur_gewerblich else 'alle'}{', nur Mo–Fr' if e.nur_mo_fr else ''}{'' if e.aktiv else ' (abgeschaltet)'}")
    _urlaub_ohne_antwort(db, stand, [e for e in tage if e.aktiv and e.im_urlaub == "fragen"])


ANTRAG_STATUS = {"approved": "genehmigt", "pending": "offen", "rejected": "abgelehnt", "cancelled": "zurückgezogen"}


def _urlaub_ohne_antwort(db, stand: Stand, fragen: list) -> None:
    """Seit 1.9.184 (L1a-Korrekturen, Punkt 5): Urlaubsanträge über einen Tag mit Rückfrage (Silvester), für den die Frage heute gestellt würde,
    aber ohne Antwort -- angelegt vor 1.9.176 (seitdem fragt der Server). Sie zählen wie der Vorschlag: ganzer Urlaubstag (Festlegung 1.9.176
    Nr. 4). Nur gezählt, je Status, kein Befund."""
    from app.arbeitszeitkalender import rueckfrage_tage
    from app.models import EmployeeAbsenceRequest
    tage = ", ".join(f"{e.tag:02d}.{e.monat:02d}." for e in fragen) or "–"
    je_status: Counter = Counter()
    for a in db.scalars(select(EmployeeAbsenceRequest).where(EmployeeAbsenceRequest.absence_category == "urlaub",
                                                              EmployeeAbsenceRequest.kalendertag_urlaub.is_(None))):
        if any(_im_zeitraum(a.start_date, a.end_date, e.monat, e.tag) for e in fragen) and rueckfrage_tage(db, a.employee_id, a.start_date, a.end_date):
            je_status[a.status] += 1
    teile = ", ".join(f"{ANTRAG_STATUS.get(s, s)} {n}" for s, n in sorted(je_status.items(), key=lambda x: list(ANTRAG_STATUS).index(x[0])
                                                                                                  if x[0] in ANTRAG_STATUS else 9))
    stand.zeile(f"Urlaubsanträge über {tage} ohne Antwort (vor 1.9.176 angelegt, zählen als ganzer Urlaubstag): {sum(je_status.values())}"
                + (f" ({teile})" if teile else ""))


def _im_zeitraum(start: date, ende: date, monat: int, tag: int) -> bool:
    for jahr in range(start.year, ende.year + 1):
        try:
            if start <= date(jahr, monat, tag) <= ende:
                return True
        except ValueError:  # 29.02. in einem Jahr ohne Schalttag
            continue
    return False


def _zuordnung(db, stand: Stand) -> None:
    from app.lohnarten import kurz, nur_jahreszeit, wirkt
    from app.models import LohnartZuordnung
    zeilen = list(db.scalars(select(LohnartZuordnung).order_by(LohnartZuordnung.schluessel)))
    stand.zeile(f"Zuordnung für den DATEV-Export: {len(zeilen)} Einträge")
    for z in zeilen:
        wert = kurz(z)
        # seit 1.9.215 der Fall wie „Wirkt“ in den Einstellungen (bis 1.9.214 „BF / Lohnart offen“ u. a.); eine übergangene Zeile je Art bei
        # Schlechtwetter wirkt nie -- dort nur der gespeicherte Wert
        uebergangen = nur_jahreszeit(z.schluessel) and (z.kennzeichen or z.lohnart)
        stand.zeile(f"  {z.schluessel}: " + (f"gespeichert {wert} – wird übergangen" if uebergangen else wirkt(z)))
        # seit 1.9.203 (L1a Stufe 4, Punkt 2): für Schlechtwetter gilt die Jahreszeit -- eine gespeicherte Zeile je Art wird übergangen, nicht gelöscht
        if nur_jahreszeit(z.schluessel) and (z.kennzeichen or z.lohnart):
            stand.befund(f"Zuordnung {z.schluessel} ({wert}) wird übergangen: für Schlechtwetter gilt die Jahreszeit (schlechtwetter:winter "
                         "bzw. schlechtwetter:sommer). In den Einstellungen leeren.")


def pruefen(db, heute: date | None = None) -> Stand:
    """Liest nur; Personen nur mit Kennung, nie mit Namen."""
    from app.berlin_time import berlin_today
    from app.models import TimeTrackingSettings
    stand = Stand()
    heute = heute or berlin_today()
    zeit = db.get(TimeTrackingSettings, 1)
    rundung = int(zeit.rounding_minutes or 0) if zeit else 0
    stand.zeile(f"Rundung: {'keine' if not rundung else f'{rundung} Minuten'}; abgeschlossen bis: {_tag(zeit.locked_until) if zeit and zeit.locked_until else '–'}")
    _modelle(db, stand)
    _personen(db, stand, heute)
    _feiertage(db, stand, heute)
    _kalender(db, stand)
    _zuordnung(db, stand)
    return stand


def nur_lesende_sitzung(url: str) -> Session:
    """Eine eigene Sitzung, die nicht schreiben kann -- jede Verbindung schreibgeschützt, bevor die erste Anfrage läuft."""
    engine = create_engine(url, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _schreibschutz(dbapi_verbindung, _eintrag):
        cursor = dbapi_verbindung.cursor()
        if engine.dialect.name == "postgresql":
            cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            dbapi_verbindung.commit()
        elif engine.dialect.name == "sqlite":
            cursor.execute("PRAGMA query_only = ON")
        else:
            raise RuntimeError(f"Datenbank {engine.dialect.name} unbekannt -- kein Schreibschutz, keine Prüfung.")
        cursor.close()

    return Session(bind=engine, autoflush=False)


def main(argv=None, *, sitzung=None, umgebung=None, ausgabe=print, heute: date | None = None) -> int:
    """sitzung/umgebung/ausgabe/heute nur für Tests; im Betrieb die nur lesende Sitzung aus DATABASE_URL, os.environ, print."""
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)
    umgebung = os.environ if umgebung is None else umgebung
    eigene = sitzung is None
    if eigene:
        url = (umgebung.get("DATABASE_URL") or "").strip()
        if not url:
            ausgabe("DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a")
            return 2
        sitzung = nur_lesende_sitzung(url)
    try:
        stand = pruefen(sitzung, heute)
    except SQLAlchemyError as fehler:
        ausgabe(f"Datenbank nicht lesbar: {type(fehler).__name__}")
        return 2
    finally:
        sitzung.rollback()
        if eigene:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    for zeile in stand.zeilen:
        ausgabe(zeile)
    ausgabe(f"Zu klären: {len(stand.befunde)}" if stand.befunde else "Nichts zu klären.")
    return 1 if stand.befunde else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # unter Windows sonst Abbruch an Umlauten
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
