"""Das Urlaubskonto je Person und Jahr -- seit 1.9.315 (Lohn L2b, Punkt 3; Antworten 1, 3, 4 und 5 des Befunds L2).

Je Person und Jahr (ab ERSTES_JAHR, 2027; app/lohnkonten.py):

    anspruch      die Urlaubstage des Jahrs (Urlaubsanspruch je Jahr, leer = die Vorgabe der Zeitregeln) -- der Betrieb trägt sie je Person ein
                  (Antwort 1: Fachkräfte 30, Helfer und Azubis 26; Teilzeit in Tagen der eigenen Woche); anteilig bei Eintritt oder Austritt
                  rechnet das ERP nicht -- dann der Hinweis „Anspruch prüfen“
    uebertrag     2027 der Startwert „Resturlaub“ (fehlt er: 0 und der Hinweis „ohne Übertrag – Startwert folgt“); ab 2028 nach der Vorgabe
                  „Übertrag ins Folgejahr“: „von Hand“ der Wert am Anspruch (leer = 0), „automatisch“ der Rest des Vorjahres
                  (app/lohnkonten.py::uebertrag_quelle()); ein Übertrag am Anspruch, wo er nicht gilt, zählt nicht -- Hinweis „Übertrag doppelt – prüfen“
    genehmigt     die genehmigten Urlaubstage des Jahrs, davon vorbei (bis heute) und künftig -- nur die Kategorie Urlaub (Antwort 3: Sonderurlaub
                  und alles andere zählt nicht), nur an Tagen mit Sollzeit der eigenen Woche, ein halber Tag mit seinem Anteil, ohne gesetzliche
                  Feiertage und Tage des Arbeitszeitkalenders (außer Silvester als ganzer Urlaubstag) -- die Posten der Tagesbilanz
                  (app/tagesbilanz.py); ein von Hand eingetragener betriebsfreier Tag zählt (Antwort 4, Befund 7.2)
    beantragt     die Tage der offenen Anträge auf Urlaub im Jahr, nach derselben Regel (Antwort 5)
    rest          Anspruch + Übertrag − genehmigt; rest_nach_antraegen = rest − beantragt
    hinweise      nur Hinweise, keine Sperre: „ohne Übertrag – Startwert folgt“, „Übertrag doppelt – prüfen“, „Anspruch prüfen“ (Eintritt oder
                  Austritt im Jahr), der vorgemerkte Verfall des Übertrags (nichts verfällt von selbst), „Rest unter 0“

Für viele Personen in einer festen Zahl Abfragen (die Tagesbilanz über alle Jahre ab 2027 bis zum Jahr, Ansprüche, Startwerte, Vorgaben, offene
Anträge), unabhängig von der Zahl der Personen, Tage und Anträge. Rollenlos und nur lesend -- wer welches Konto sieht, entscheidet der Router
(app/permissions.py::darf_konten_aller()).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

NULL = Decimal("0")
ZEHNTEL = Decimal("0.1")
URLAUB = "urlaub"
OHNE_STARTWERT = "ohne Übertrag – Startwert folgt"
DOPPELT = "Übertrag doppelt – prüfen"
ANSPRUCH_PRUEFEN = "Anspruch prüfen"


@dataclass
class Konto:
    employee_id: int
    name: str
    active: bool
    jahr: int
    anspruch: Decimal
    anspruch_vorgabe: bool
    uebertrag: Decimal
    uebertrag_quelle: str
    genehmigt: Decimal = NULL
    vorbei: Decimal = NULL
    kuenftig: Decimal = NULL
    beantragt: Decimal = NULL
    hinweise: list[str] = field(default_factory=list)

    @property
    def rest(self) -> Decimal:
        return self.anspruch + self.uebertrag - self.genehmigt

    @property
    def rest_nach_antraegen(self) -> Decimal:
        return self.rest - self.beantragt

    def als_dict(self) -> dict:
        """Tage mit einer Stelle (halbe Tage), wie die Eingaben."""
        from .rounding import round_half_up
        t = lambda w: round_half_up(w, ZEHNTEL)  # noqa: E731
        return {"employee_id": self.employee_id, "name": self.name, "active": self.active, "jahr": self.jahr, "anspruch": t(self.anspruch),
                "anspruch_vorgabe": self.anspruch_vorgabe, "uebertrag": t(self.uebertrag), "uebertrag_quelle": self.uebertrag_quelle,
                "genehmigt": t(self.genehmigt), "vorbei": t(self.vorbei), "kuenftig": t(self.kuenftig), "beantragt": t(self.beantragt),
                "rest": t(self.rest), "rest_nach_antraegen": t(self.rest_nach_antraegen), "hinweise": list(self.hinweise)}


def _verfall(anspruch_row, vorgabe_verfall: str | None, jahr: int) -> date | None:
    """Das vorgemerkte Verfallsdatum des Übertrags im Jahr: am Anspruch, sonst die Vorgabe „TT.MM.“ (leer = nie)."""
    if anspruch_row is not None and anspruch_row.verfall_am is not None:
        return anspruch_row.verfall_am
    if vorgabe_verfall:
        tag, monat = vorgabe_verfall.rstrip(".").split(".")[:2]
        return date(jahr, int(monat), int(tag))
    return None


def _tage_text(wert: Decimal) -> str:
    from .rounding import round_half_up
    text = f"{round_half_up(wert, ZEHNTEL):f}".replace(".", ",")
    return text[:-2] if text.endswith(",0") else text


def konten(db: Session, jahr: int, employee_ids=None, *, heute: date | None = None) -> list[Konto]:
    """Das Urlaubskonto im Jahr je Person -- employee_ids: genau diese; ohne Angabe die Personen der Tagesbilanz des Jahrs (aktiv oder mit
    Buchungen bzw. Abwesenheiten im Jahr). heute: Grenze zwischen vorbei und künftig (Vorgabe Berlin). ValueError vor 2027."""
    from .berlin_time import berlin_today
    from .lohnkonten import ERSTES_JAHR, uebertrag_quelle
    from .models import EmployeeAbsenceRequest, LohnStartwert, TimeTrackingSettings, Urlaubsanspruch
    from .sollzeit import abwesenheit_tage
    from .tagesbilanz import bilanz
    from .time_tracking import employee_name

    if jahr < ERSTES_JAHR:
        raise ValueError(f"Das Urlaubskonto beginnt {ERSTES_JAHR}.")
    heute = heute or berlin_today()
    einstellungen = db.get(TimeTrackingSettings, 1)
    vorgabe, modus, vorgabe_verfall = einstellungen.urlaub_vorgabe_tage, einstellungen.urlaub_uebertrag, einstellungen.urlaub_verfall
    # Bei „automatisch“ trägt jedes Jahr den Rest des Vorjahres -- die Tagesbilanz dann ab 2027 (eine Rechnung über alle Jahre)
    erstes = ERSTES_JAHR if modus == "automatisch" else jahr
    b = bilanz(db, date(erstes, 1, 1), date(jahr, 12, 31), employee_ids)
    # ohne Angabe: wer aktiv ist oder im Jahr Buchungen bzw. Abwesenheiten hat (bei „automatisch“ reicht die Tagesbilanz über mehrere Jahre) --
    # Feiertage und Kalendertage zählen dafür nicht: eine inaktive Person ohne Austritt hat Sollzeit und damit jedes Jahr solche Posten
    personen = list(b.personen) if employee_ids is not None else [e for e in b.personen if e.active or any(
        t.gebucht or any(x.quelle in ("abwesenheit", "schlechtwetter") for x in t.posten) for t in b.tage[e.id].values() if t.tag.year == jahr)]
    ids = [e.id for e in personen] or [0]
    ansprueche = {(a.employee_id, a.jahr): a for a in db.scalars(select(Urlaubsanspruch).where(
        Urlaubsanspruch.employee_id.in_(ids), Urlaubsanspruch.jahr >= erstes, Urlaubsanspruch.jahr <= jahr))}
    startwerte = {s.employee_id: s for s in db.scalars(select(LohnStartwert).where(LohnStartwert.employee_id.in_(ids)))}
    offen: dict[int, list] = {}
    for r in db.scalars(select(EmployeeAbsenceRequest).where(
            EmployeeAbsenceRequest.employee_id.in_(ids), EmployeeAbsenceRequest.status == "pending", EmployeeAbsenceRequest.absence_category == URLAUB,
            EmployeeAbsenceRequest.start_date <= date(jahr, 12, 31), EmployeeAbsenceRequest.end_date >= date(jahr, 1, 1))):
        offen.setdefault(r.employee_id, []).append(r)

    ergebnis = []
    for emp in sorted(personen, key=lambda e: (not e.active, (e.last_name or "").casefold(), (e.first_name or "").casefold())):
        tage = b.tage[emp.id]
        soll = {t: x.soll for t, x in tage.items()}
        p = b.payrolls.get(emp.id)
        rest_vorjahr = None
        for j in range(erstes, jahr + 1):
            a = ansprueche.get((emp.id, j))
            quelle = uebertrag_quelle(j, modus)
            k = Konto(emp.id, employee_name(emp) or f"#{emp.id}", bool(emp.active), j,
                      a.urlaubstage if a is not None and a.urlaubstage is not None else vorgabe, a is None or a.urlaubstage is None, NULL, quelle)
            if quelle == "startwert":
                s = startwerte.get(emp.id)
                if s is None or s.resturlaub_tage is None:
                    k.hinweise.append(OHNE_STARTWERT)
                else:
                    k.uebertrag = s.resturlaub_tage
            elif quelle == "automatisch":
                k.uebertrag = rest_vorjahr if rest_vorjahr is not None else NULL
            elif a is not None and a.uebertrag is not None:
                k.uebertrag = a.uebertrag
            if a is not None and a.uebertrag is not None and quelle != "von_hand":
                k.hinweise.append(DOPPELT)
            for t, x in tage.items():
                if t.year != j:
                    continue
                for posten in x.posten:
                    if posten.quelle == "abwesenheit" and posten.kategorie == URLAUB:
                        k.genehmigt += posten.anteil
                        if t <= heute:
                            k.vorbei += posten.anteil
                        else:
                            k.kuenftig += posten.anteil
            if j == jahr:
                for r in offen.get(emp.id, []):
                    k.beantragt += abwesenheit_tage(db, emp.id, max(r.start_date, date(j, 1, 1)), min(r.end_date, date(j, 12, 31)), kategorie=URLAUB,
                                                    halber_tag=bool(r.halber_tag), feiertage=b.feiertage, kalendertag_urlaub=r.kalendertag_urlaub,
                                                    soll=soll, kalender=b.kalender.get(emp.id, {}))["tage"]
                if p is not None and any(d is not None and d.year == j for d in (p.eintritt, p.austritt)):
                    k.hinweise.append(ANSPRUCH_PRUEFEN)
                verfall = _verfall(a, vorgabe_verfall, j)
                if verfall is not None and k.uebertrag > 0:
                    k.hinweise.append(f"Verfall des Übertrags vorgemerkt am {verfall:%d.%m.%Y} – nichts verfällt von selbst")
                if k.rest < 0:
                    k.hinweise.append(f"Rest unter 0 ({_tage_text(k.rest)} Tage)")
                ergebnis.append(k)
            rest_vorjahr = k.rest
    return ergebnis

def tage_wort(wert: Decimal) -> str:
    """Seit 1.9.316: „1 Tag“, „0,5 Tage“, „21,5 Tage“, „-2 Tage“."""
    return f"{_tage_text(wert)} {'Tag' if wert == 1 else 'Tage'}"


def rest_danach(db: Session, employee_id: int, von: date, bis: date, *, halber_tag: bool = False, kalendertag_urlaub: bool | None = None,
                heute: date | None = None) -> dict | None:
    """Seit 1.9.316 (Lohn L2b, Punkt 4): was ein Urlaub von von bis bis zählt und der Rest danach -- beim Stellen und beim Genehmigen dieselbe
    Rechnung: der Rest des Kontos (Anspruch + Übertrag − genehmigt) minus die Tage dieses Urlaubs; andere offene Anträge zählen nicht mit (die
    zeigt das Konto unter „nach den offenen Anträgen“). Je Jahr ab 2027 {jahr, tage, rest_danach}; ein Urlaub über den Jahreswechsel nennt beide
    Jahre. None, wenn kein Tag in einem Jahr ab 2027 liegt. text: „danach Rest 21,5 Tage“ bzw. „danach Rest 2027: 1 Tag · 2028: 29 Tage“;
    tage_text: „5 Urlaubstage“. Seit 1.9.318 (Nachrunde L2b, Punkt B): fehlt in einem dieser Jahre der Startwert (2027), dazu „ · ohne Übertrag – Startwert
    folgt“ (ohne_startwert je Jahr) -- überall, wo „danach Rest“ steht."""
    from .lohnkonten import ERSTES_JAHR
    from .planning import automatic_public_holidays
    from .sollzeit import abwesenheit_tage
    from .zeiten import feiertage_bundesland

    # das Bundesland wie die Tagesbilanz: die Einstellung der Plantafel, ohne sie Nordrhein-Westfalen (abwesenheit_tage() läse sie ohne Rückfall)
    feiertage = automatic_public_holidays(feiertage_bundesland(db), range(von.year, bis.year + 1))
    jahre = []
    for j in range(max(von.year, ERSTES_JAHR), bis.year + 1):
        k = konten(db, j, [employee_id], heute=heute)
        if not k:
            continue
        tage = abwesenheit_tage(db, employee_id, max(von, date(j, 1, 1)), min(bis, date(j, 12, 31)), kategorie=URLAUB, halber_tag=halber_tag,
                                feiertage=feiertage, kalendertag_urlaub=kalendertag_urlaub)["tage"]
        jahre.append({"jahr": j, "tage": tage, "rest_danach": k[0].rest - tage, "ohne_startwert": OHNE_STARTWERT in k[0].hinweise})
    if not jahre:
        return None
    summe = sum((x["tage"] for x in jahre), NULL)
    text = "danach Rest " + (tage_wort(jahre[0]["rest_danach"]) if len(jahre) == 1 else
                             " · ".join(f"{x['jahr']}: {tage_wort(x['rest_danach'])}" for x in jahre))
    if any(x["ohne_startwert"] for x in jahre):  # seit 1.9.318
        text += " · " + OHNE_STARTWERT
    return {"jahre": jahre, "tage": summe, "tage_text": f"{_tage_text(summe)} {'Urlaubstag' if summe == 1 else 'Urlaubstage'}", "text": text}


def rest_danach_je_antrag(db: Session, antraege) -> dict[int, str]:
    """Seit 1.9.316: je offenem Antrag auf Urlaub „danach Rest …“ (rest_danach()) -- für die Liste, in der genehmigt wird. Andere Anträge fehlen."""
    ergebnis = {}
    for r in antraege:
        if r.status == "pending" and r.absence_category == URLAUB:
            d = rest_danach(db, r.employee_id, r.start_date, r.end_date, halber_tag=bool(r.halber_tag), kalendertag_urlaub=r.kalendertag_urlaub)
            if d is not None:
                ergebnis[r.id] = d["text"]
    return ergebnis
