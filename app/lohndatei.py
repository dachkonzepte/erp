"""Die Lohndatei für DATEV Lohn und Gehalt -- seit 1.9.224 (Lohn L1b, Punkt 1; ersetzt die Formate „Lohn und Gehalt“ (CSV) und LODAS, E8).

Format wie die Dateien, die Time 4 an das Lohnbüro gab (Muster in bildgrundlage/lohn, nicht in Git): ASCII, CRLF auch nach der letzten Zeile,
jede Zeile 11 Felder, getrennt durch Semikolon.

    Kopf          Beraternummer;Mandantennummer;MM/JJJJ          (aus den Einstellungen, nur der Admin trägt sie ein)
    Tageszeile    Personalnummer;Tag;Kennzeichen;Lohnart;Stunden;;;;;;   (Tag ohne führende Null, Stunden mit Komma und zwei Stellen;
                                                                          ohne Lohnart bleibt das Feld leer: 00291;31;UU;;7,50;;;;;;)
    Monatszeile   Personalnummer;;;Lohnart;;;Stunden;;;;          (nur eine Zeile der Zuordnung mit „Monatszeile“, heute keine)

Ein Monat. Personen aufsteigend nach Personalnummer, je Person die Tage aufsteigend, im Tag Arbeit, Mehrarbeit, Feiertag, Kalendertag,
Abwesenheit, Schlechtwetter; die Monatszeilen der Person zuletzt. Mehrere Zeilen je Person und Tag sind erlaubt (Steuerbüro, 05.11.2026).
Eine Zeile mit 0,00 Stunden entfällt.

Was je Person und Tag hineinkommt (Kennzeichen und Lohnart aus der Zuordnung, app/lohnarten.py -- ohne Kennzeichen keine Zeile):
    Arbeit         die Arbeit des Tags im Lohn (app/time_tracking.py::arbeit_des_tags(), auf 0,25 h) -- nur beim Umfang „alles“
    Mehrarbeit     nur Azubis (EmployeePayrollSettings.azubi): was die Arbeit über die Sollzeit des Tags bringt, zusammen mit den übrigen Stunden des
                   Tags (Feiertag, Kalendertag, Abwesenheit, Schlechtwetter) -- höchstens die Arbeit; diese Stunden stehen dann unter der
                   Mehrarbeit (AA / 1900), nicht unter der Arbeit. Ohne Kennzeichen der Mehrarbeit bleibt alles unter der Arbeit.
    Feiertag       gesetzlicher Feiertag (Bundesland der Planung) mit Sollzeit, nur beim Umfang „alles“ (E3); geht einem Kalendertag vor
    Kalendertag    die Abwesenheit des Arbeitszeitkalenders (Heiligabend, Silvester), Stunden = Sollzeit des Tags (app/arbeitszeitkalender.py)
    Abwesenheit    jede genehmigte Abwesenheit außer Schlechtwetter, je Tag mit Sollzeit × Anteil (app/sollzeit.py::abwesenheit_tage())
    Schlechtwetter je Ausfalltag Sollzeit minus Arbeit (app/schlechtwetter.py::ausfall()), Winter oder Sommer nach dem Tag
Umfang „nur Abwesenheiten“: Kalendertag, Abwesenheit, Schlechtwetter -- keine Arbeit, keine Mehrarbeit, kein Feiertag. Umfang „nichts“: keine
Zeile. Vor dem Eintritt und nach dem Austritt nichts (die Sollzeit ist dort 0; gebuchte Arbeit dort geht nicht in die Datei).

Was nicht in die Datei geht (seit 1.9.225, Lohn L1b, Punkt 2), je Person mit Grund (Person.nicht, „Monat & Lohn“ über dem Knopf): Arbeit, Mehrarbeit
und Feiertage beim Umfang „nur Abwesenheiten“; gebuchte Arbeit und eingetragene Abwesenheiten beim Umfang „nichts“ (Feiertage und Kalendertage einer
Person ohne Export nennt die Liste nicht); jede Zeile ohne Kennzeichen in der Zuordnung; Arbeit vor dem Eintritt oder nach dem Austritt. Je Art und
Grund die Zahl der Tage und die Stunden. Zeilen mit 0,00 Stunden fehlen nicht -- es gibt nichts.

Seit 1.9.308 (Lohn L2a, Punkt 1) rechnet berechnen() über die Tagesbilanz (app/tagesbilanz.py): Sollzeit, Arbeit, Feiertag, Kalendertag, Abwesenheit
und Schlechtwetter je Person und Tag kommen von dort; hier gelten nur noch Export-Umfang, Zuordnung, Mehrarbeit der Azubis und das Format. Die
Dateien bleiben Byte für Byte gleich (Nachweis: die Vorprobe September und Oktober).

Rollenlos und nur lesend; wer ausgeben darf und ob der Monat abgeschlossen und vollständig ist, prüfen app/time_backoffice.py und der Router.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .rounding import round_hours

NULL = Decimal("0")
# Reihenfolge der Zeilen eines Tags
REIHE = ("arbeit", "mehrarbeit", "feiertag", "kalender", "abwesenheit", "schlechtwetter")
UMFANG_NICHTS = "Export-Umfang „nichts“"
UMFANG_ABWESENHEITEN = "Export-Umfang „nur Abwesenheiten“"
OHNE_KENNZEICHEN = "ohne Kennzeichen in der Zuordnung"
AUSSERHALB = "vor dem Eintritt oder nach dem Austritt"


@dataclass
class Zeile:
    tag: date | None  # None: Monatszeile
    kennzeichen: str | None
    lohnart: str | None
    stunden: Decimal
    quelle: str  # eins aus REIHE


@dataclass
class Person:
    employee_id: int
    name: str
    personalnummer: str | None
    umfang: str
    azubi: bool
    nachname: str = ""
    zeilen: list[Zeile] = field(default_factory=list)
    # seit 1.9.225: was nicht in die Datei geht -- je (Art, Grund) {"was", "grund", "tage", "stunden"}
    nicht: list[dict] = field(default_factory=list)
    # seit 1.9.313 (Lohn L2b, Punkt 1): je Kategorie die Tage einer Abwesenheit ohne Kennzeichen in der Zuordnung („Vor dem Abschluss“, ohne_zuordnung())
    ohne_zuordnung: dict[str, set] = field(default_factory=dict)

    def nicht_merken(self, was: str, grund: str, tag: date, stunden: Decimal) -> None:
        for n in self.nicht:
            if (n["was"], n["grund"]) == (was, grund):
                n["tage"].add(tag)
                n["stunden"] += stunden
                return
        self.nicht.append({"was": was, "grund": grund, "tage": {tag}, "stunden": stunden})

    def nicht_texte(self) -> list[str]:
        """„Arbeit: 2 Tage, 15,50 h – Export-Umfang „nur Abwesenheiten““ je Art und Grund."""
        return [f"{n['was']}: {len(n['tage'])} {'Tag' if len(n['tage']) == 1 else 'Tage'}, {_stunden_text(n['stunden'])} h – {n['grund']}"
                for n in self.nicht]


def monat_ende(erster: date) -> date:
    return (erster.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _stunden_text(wert: Decimal) -> str:
    return f"{round_hours(wert):.2f}".replace(".", ",")


def berechnen(db: Session, erster: date) -> list[Person]:
    """Je Person, die im Monat aktiv ist oder Buchungen bzw. Abwesenheiten hat, ihre Zeilen (sortiert wie in der Datei); Personen mit Umfang
    „nichts“ ohne Zeilen. Reihenfolge der Personen: nach Personalnummer, ohne Nummer nach Namen dahinter. Seit 1.9.308 über die Tagesbilanz
    (app/tagesbilanz.py::bilanz()) -- dieselben Personen, Tage und Stunden wie bis 1.9.307, hier nur Umfang, Zuordnung und Mehrarbeit."""
    from .lohnarten import _alle, fest, kalender, zuordnung
    from .schlechtwetter import SCHLECHTWETTER
    from .tagesbilanz import bilanz
    from .time_backoffice import effective_datev_personnel_number, export_umfang, load_employee_payroll
    from .time_tracking import employee_name

    ende = monat_ende(erster)
    b = bilanz(db, erster, ende)
    alle = _alle(db)
    z_arbeit, z_mehr, z_feiertag = fest(db, "arbeit", alle=alle), fest(db, "mehrarbeit_azubi", alle=alle), fest(db, "feiertag", alle=alle)

    ergebnis: list[Person] = []
    for emp in b.personen:
        p = b.payrolls.get(emp.id) or load_employee_payroll(db, emp.id)
        umfang = export_umfang(p)
        person = Person(emp.id, employee_name(emp) or f"#{emp.id}", effective_datev_personnel_number(db, emp, p), umfang, bool(getattr(p, "azubi", False)),
                        emp.last_name or "")
        ergebnis.append(person)
        alles, nichts = umfang == "alles", umfang == "nichts"
        monat: dict[str, Decimal] = {}
        for tag, t in b.tage[emp.id].items():
            # (Quelle, Stunden, Zuordnung, Bezeichnung) außer der Arbeit; Feiertag und Kalendertag nur für eine Person mit Export (seit 1.9.225 der
            # Feiertag auch bei „nur Abwesenheiten“ -- er steht dann unter „Nicht in der Datei“)
            # seit 1.9.313 dazu die Kategorie einer Abwesenheit (sonst None) -- für ohne_zuordnung
            posten: list[tuple[str, Decimal, dict | None, str, str | None]] = []
            for x in t.posten:
                if x.quelle == "feiertag":
                    if not nichts:
                        posten.append(("feiertag", x.stunden, z_feiertag, x.bezeichnung, None))
                elif x.quelle == "kalender":
                    if not nichts:
                        z = kalender(db, x.kategorie, alle=alle)
                        posten.append(("kalender", x.stunden, z if z and z["exportiert"] else None, x.bezeichnung, None))
                elif x.quelle == "schlechtwetter":
                    posten.append(("schlechtwetter", x.stunden, zuordnung(db, SCHLECHTWETTER, None, tag, alle=alle), x.bezeichnung, None))
                else:
                    posten.append(("abwesenheit", x.stunden, zuordnung(db, x.kategorie, x.art, tag, alle=alle), x.bezeichnung, x.kategorie))
            if t.gebucht:
                arbeit = t.arbeit
                if not t.beschaeftigt:
                    if arbeit > 0:
                        person.nicht_merken("Arbeit", AUSSERHALB, tag, arbeit)
                elif not alles:
                    posten = [("arbeit", arbeit, z_arbeit, "Arbeit", None)] + posten
                else:
                    mehr = NULL
                    if person.azubi and z_mehr is not None:
                        mehr = min(arbeit, max(NULL, arbeit + sum((h for _q, h, _z, _w, _k in posten), NULL) - t.soll))
                    posten = [("arbeit", arbeit - mehr, z_arbeit, "Arbeit", None), ("mehrarbeit", mehr, z_mehr, "Mehrarbeit", None)] + posten
            for quelle, stunden, z, was, kategorie in sorted(posten, key=lambda x: REIHE.index(x[0])):
                if stunden <= 0:
                    continue
                grund = (UMFANG_NICHTS if nichts else UMFANG_ABWESENHEITEN if not alles and quelle in ("arbeit", "mehrarbeit", "feiertag")
                         else OHNE_KENNZEICHEN if z is None else None)
                if grund:
                    person.nicht_merken(was, grund, tag, stunden)
                    if grund == OHNE_KENNZEICHEN and kategorie:  # seit 1.9.313
                        person.ohne_zuordnung.setdefault(kategorie, set()).add(tag)
                    continue
                if z.get("monatszeile"):
                    monat[z["lohnart"]] = monat.get(z["lohnart"], NULL) + stunden
                    continue
                person.zeilen.append(Zeile(tag, z["kennzeichen"], z["lohnart"], round_hours(stunden), quelle))
        for lohnart in sorted(monat):
            person.zeilen.append(Zeile(None, None, lohnart, round_hours(monat[lohnart]), "schlechtwetter"))
    ergebnis.sort(key=lambda x: (x.personalnummer is None, x.personalnummer or "", x.name.casefold()))
    return ergebnis


# Seit 1.9.313 (Lohn L2b, Punkt 1): ohne Zuordnung bewusst leer (LB1) -- „Vor dem Abschluss“ nennt sie nicht
BEWUSST_LEER = ("unbezahlt", "freizeitausgleich")


KEINE_LOHNDATEI = " – keine Lohndatei, bis die Zuordnung steht"


def ohne_zuordnung(personen: list[Person]) -> list[dict]:
    """Seit 1.9.313 (Lohn L2b, Punkt 1, Entscheidung 11.11.2026): je Kategorie, deren Abwesenheiten im Monat ohne Kennzeichen in der Zuordnung nicht in
    die Lohndatei gehen, eine Zeile -- „Sonderurlaub ohne Zuordnung: 2 Tage nicht in der Lohndatei – keine Lohndatei, bis die Zuordnung steht“ (Tage aller
    Personen zusammen, ohne Namen: „Prüfen“ sieht auch Büro – Auftrag). Ohne Unbezahlt und Freizeitausgleich (BEWUSST_LEER); wer den Export-Umfang „nichts“
    hat, zählt nicht. Seit 1.9.317 (Nachrunde L2b, Punkt A) sperrt sie die Lohndatei wie eine fehlende Personalnummer: die Zeilen gehören zu
    app/time_backoffice.py::datev_fehlt() (bis 1.9.316 nur ein Hinweis in „Vor dem Abschluss“); den Abschluss sperren sie nicht."""
    from .absence_requests import ABSENCE_CATEGORIES, ABSENCE_CATEGORY_LABELS
    tage: dict[str, int] = {}
    for p in personen:
        for kategorie, je in p.ohne_zuordnung.items():
            if kategorie not in BEWUSST_LEER:
                tage[kategorie] = tage.get(kategorie, 0) + len(je)
    reihe = list(ABSENCE_CATEGORIES)
    return [{"art": "zuordnung", "kategorie": k,
             "text": f"{ABSENCE_CATEGORY_LABELS.get(k, k)} ohne Zuordnung: {n} {'Tag' if n == 1 else 'Tage'} nicht in der Lohndatei{KEINE_LOHNDATEI}"}
            for k, n in sorted(tage.items(), key=lambda x: reihe.index(x[0]) if x[0] in reihe else len(reihe))]


def zeile_text(pnr: str, z: Zeile) -> str:
    if z.tag is None:
        return f"{pnr};;;{z.lohnart};;;{_stunden_text(z.stunden)};;;;"
    return f"{pnr};{z.tag.day};{z.kennzeichen};{z.lohnart or ''};{_stunden_text(z.stunden)};;;;;;"


def datei(beraternummer: str, mandantennummer: str, erster: date, personen: list[Person]) -> bytes:
    """Die Datei: Kopf, dann je Person mit Zeilen ihre Zeilen. Jede Person mit Zeilen braucht eine Personalnummer mit genau 5 Ziffern (prüft der
    Aufrufer über datev_fehlt(); seit 1.9.230 lehnt die Datei selbst jede andere ab -- ValueError, keine Datei)."""
    from .time_backoffice import personalnummer_gueltig
    falsch = [p.personalnummer or "ohne" for p in personen if p.zeilen and not personalnummer_gueltig(p.personalnummer)]
    if falsch:
        raise ValueError("Keine Lohndatei: Personalnummer ohne genau 5 Ziffern (" + ", ".join(falsch) + ").")
    zeilen = [f"{beraternummer};{mandantennummer};{erster:%m/%Y}"]
    for p in personen:
        zeilen += [zeile_text(p.personalnummer, z) for z in p.zeilen]
    return ("\r\n".join(zeilen) + "\r\n").encode("ascii")


# --- Ablage (seit 1.9.226, Lohn L1b, Punkt 3) -------------------------------------------------------------------------------------------------

class LohndateiVeraendert(ValueError):
    """Die abgelegten Bytes passen nicht zu ihrer Prüfsumme -- ausgeliefert wird dann nichts (409)."""


def ablegen(db: Session, erster: date, inhalt: bytes, dateiname: str, *, user_id: int | None, user_name: str | None):
    """Legt eine erzeugte Datei ab (flush, kein Commit -- der Aufrufer committet). Jede erzeugte Datei, auch eine zweite für denselben Monat."""
    import hashlib

    from .models import Lohndatei

    row = Lohndatei(monat=erster.replace(day=1), dateiname=dateiname, inhalt=inhalt, sha256=hashlib.sha256(inhalt).hexdigest(), groesse=len(inhalt),
                    erzeugt_von_user_id=user_id, erzeugt_von_name=user_name or "System")
    db.add(row)
    db.flush()
    return row


def abgelegte(db: Session, erster: date | None = None) -> list:
    """Die abgelegten Dateien (eines Monats), die jüngste zuerst."""
    from .models import Lohndatei

    abfrage = select(Lohndatei).order_by(Lohndatei.erzeugt_am.desc(), Lohndatei.id.desc())
    if erster is not None:
        abfrage = abfrage.where(Lohndatei.monat == erster.replace(day=1))
    return list(db.scalars(abfrage))


def lesen(row) -> bytes:
    """Die abgelegten Bytes -- nur, wenn sie zur Prüfsumme passen."""
    import hashlib

    if hashlib.sha256(row.inhalt).hexdigest() != row.sha256:
        raise LohndateiVeraendert("Die abgelegte Lohndatei passt nicht zu ihrer Prüfsumme – sie wird nicht ausgeliefert.")
    return row.inhalt


def personalnummern_der_ablage(db: Session) -> dict[str, str]:
    """{Personalnummer: „MM/JJJJ“ der ältesten abgelegten Datei, in der sie steht} -- eine solche Nummer bleibt gesperrt (Notiz zu 1.9.181)."""
    from .models import Lohndatei

    ergebnis: dict[str, str] = {}
    for monat, inhalt in db.execute(select(Lohndatei.monat, Lohndatei.inhalt).order_by(Lohndatei.monat, Lohndatei.id)):
        for zeile in inhalt.decode("ascii", errors="replace").split("\r\n")[1:]:
            nummer = zeile.split(";", 1)[0]
            if nummer:
                ergebnis.setdefault(nummer, f"{monat:%m/%Y}")
    return ergebnis


def abgelegt_dict(row) -> dict:
    return {"id": row.id, "monat": row.monat, "dateiname": row.dateiname, "sha256": row.sha256, "groesse": row.groesse, "erzeugt_am": row.erzeugt_am,
            "erzeugt_von_name": row.erzeugt_von_name}
