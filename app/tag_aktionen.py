"""Seit 1.9.267 (Stufe 6, R5b): die Tag-Aktionen der Plantafel -- eine Person, eine Kolonne oder ein Gerät für einzelne Tage an einen Auftrag setzen.

Grundlage: Befund R5 (Abschnitt D) und die Antworten von Tobias (Archiv „Kalender und Outlook-Sync“, „Stufe 6, R5“), Zeichnung
bildgrundlage/entwurf-stufe6/plantafel-auftraege-regeln.html.

Tag setzen (Punkt 1)
    Ziel     auf einer Karte (slot_id, Antwort 6): dieser Einsatz -- eine Kolonne nur in den Einsatz derselben Kolonne, sonst ein eigener (Antwort 8); auf
             freier Fläche: hat der Auftrag an dem Tag einen Einsatz, kommt sie dazu (Kolonne: der derselben Kolonne; Person oder Gerät: der ohne
             Kolonne, sonst der früheste); schließt der Tag direkt an einen Einsatz an (kein Arbeitstag dazwischen, Antwort 7: Fr -> Mo), wird er
             verlängert, der vordere zuerst; sonst entsteht ein neuer (vorläufig, Art wie der letzte Einsatz des Auftrags, Stunden = Rest).
    Kran     eine Kolonne nie in eine Kranvermietung („bitte einzelne Bediener ziehen“); eine Person allein nicht an einen Tag ohne Einsatz einer
             Kranvermietung („zuerst den Kran ziehen“) -- Antwort 8.
    Falle    verlängert wird über update_slot(alle_tage_mitnehmen=False): wer „alle Tage“ hatte, steht danach an genau den bisherigen Tagen -- nur die
             gezogene Person (Kolonne, Gerät) steht am neuen Tag.
    Fragen   nur bei einer Warnung, die die Aktion neu bringt (eine neue Warnung oder ein neuer Tag einer bestehenden); was vorher schon da war, fragt
             nicht. Ganze Kolonne: eine Rückfrage für alle. Hinweise fragen nie.
    Prüfen   derselbe Weg ohne Schreiben (rollback): was geschähe (dazu, verlängert, neu), die Warnungen, die fragen würden, die Hinweise.
Alles in einer Transaktion unter der Sperre der Arbeitsvorbereitung des Auftrags.

Umsetzen, Herausnehmen, Verlängern (Punkt 2, seit 1.9.268) -- für eine Person oder ein Gerät, keine Kolonne
    Umsetzen       aus einer Zelle auf einen anderen Auftrag oder Tag: erst setzen (Regeln wie oben, die Tage um gleich viele Kalendertage), dann am alten Platz
                   herausnehmen -- im selben Einsatz nur die Tage, die sie nicht behält; beide Arbeitsvorbereitungen aufsteigend gesperrt; der alte Platz fragt
                   nicht (er ist danach frei), eine neue Warnung am Ziel schon
    Herausnehmen   für Tage oder alle; am Rand kürzt der Einsatz, in der Mitte bleibt eine Lücke; wird er ganz leer, die Rückfrage „Der Einsatz hat dann niemanden
                   mehr.“ (Antwort 3, wenn_leer); fragt sonst nie
    Verlängern     ab einem ihrer Tage bis zum letzten Tag des Einsatzes; prüft wie Planen"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import kran_kalender
from .auftragsstatus import AuftragGeschlossen, einsatz_gesperrt
from .models import Order, PlanningSlot, WorkPreparation
from .planning import (BesetzungUngueltig, PlanungsWarnung, _besetzte_tage, _combined_holiday_map, _create_slot, _einsatz_abfrage, _is_workday,
                       _kolonne_schlaegt_geraete_vor, _kolonne_schlaegt_vor, _load_slot, _load_team, _tage_der_zeile, _update_slot, einsatz_konflikte,
                       load_planning_settings)
from .zugehoerigkeit import IdNichtGefunden

KRAN_KOLONNE = "Eine Kranvermietung hat keine Kolonne – bitte einzelne Bediener ziehen."
KRAN_ZUERST = "An diesem Tag hat die Kranvermietung keinen Einsatz – zuerst den Kran ziehen."
KOLONNE_LEER = "Die Kolonne schlägt niemanden vor."
NICHT_AM_TAG = "Der Einsatz liegt nicht an diesem Tag."
GENAU_EINS = "Bitte genau eine Person, eine Kolonne oder ein Gerät nennen."
MAX_LUECKE = 31  # „direkt anschließend“ prüft höchstens so viele Tage dazwischen


@dataclass(frozen=True)
class Wer:
    """Wen eine Tag-Aktion setzt: eine Person, eine Kolonne oder ein Gerät."""
    art: str  # "person" | "kolonne" | "geraet"
    id: int


def wer_aus(employee_id: int | None = None, team_id: int | None = None, resource_id: int | None = None) -> Wer:
    gesetzt = [(a, i) for a, i in (("person", employee_id), ("kolonne", team_id), ("geraet", resource_id)) if i is not None]
    if len(gesetzt) != 1:
        raise BesetzungUngueltig(GENAU_EINS)
    return Wer(gesetzt[0][0], int(gesetzt[0][1]))


def _team(slot: PlanningSlot) -> int | None:
    return slot.team_assignment.team_id if slot.team_assignment is not None else None


def _arbeitstag(db: Session, von: date, bis: date):
    """Arbeitstag der Planung (Wochentag und kein Feiertag oder betriebsfreier Tag), für die Tage um den Zeitraum."""
    settings = load_planning_settings(db)
    feiertage = set(_combined_holiday_map(db, von - timedelta(days=MAX_LUECKE + 1), bis + timedelta(days=MAX_LUECKE + 1))[0])
    return lambda t: _is_workday(t, settings, feiertage)


def anschliessend(vorher: date, nachher: date, arbeitstag) -> bool:
    """nachher folgt direkt auf vorher: kein Arbeitstag dazwischen (Antwort 7 -- Fr -> Mo über das Wochenende)."""
    luecke = (nachher - vorher).days
    if luecke <= 0 or luecke > MAX_LUECKE:
        return False
    return not any(arbeitstag(vorher + timedelta(days=n)) for n in range(1, luecke))


def _sperren(db: Session, prep_ids) -> None:
    """Die Arbeitsvorbereitungen in fester Reihenfolge sperren (aufsteigende ID) -- wie update_slot()/delete_slot() je eine; mehrere nie in anderer
    Reihenfolge, sonst warten zwei Aktionen über Kreuz aufeinander (Deadlock unter PostgreSQL)."""
    for prep_id in sorted({p for p in prep_ids if p is not None}):
        db.execute(select(WorkPreparation.id).where(WorkPreparation.id == prep_id).with_for_update())


def _prep_id(db: Session, order_id: int) -> int | None:
    return db.scalar(select(WorkPreparation.id).where(WorkPreparation.order_id == order_id))


def _einsaetze(db: Session, prep_id: int | None) -> list[PlanningSlot]:
    if prep_id is None:
        return []
    return list(db.scalars(_einsatz_abfrage().where(PlanningSlot.preparation_id == prep_id).execution_options(populate_existing=True)))


def _auftrag(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise IdNichtGefunden("Auftrag wurde nicht gefunden.")
    gesperrt = einsatz_gesperrt(order)
    if gesperrt:
        raise AuftragGeschlossen(gesperrt)
    return order


def _karte(db: Session, order: Order, slot_id: int | None, tage: list[date]) -> PlanningSlot | None:
    """Antwort 6: die Karte, auf die gezogen wurde -- ein Einsatz dieses Auftrags (fremd wie unbekannt 404, Regel 25) an diesem Tag (sonst 422)."""
    if slot_id is None:
        return None
    karte = db.get(PlanningSlot, slot_id)
    if karte is None or karte.preparation.order_id != order.id:
        raise IdNichtGefunden("Einsatz wurde nicht gefunden.")
    if karte.start_date > max(tage) or karte.end_date < min(tage):
        raise BesetzungUngueltig(NICHT_AM_TAG)
    return karte


def _art_des_auftrags(slots: list[PlanningSlot]) -> str:
    """Die Art eines neuen Einsatzes: die des letzten Einsatzes des Auftrags, ohne Einsatz „baustelle“ (Befund D d)."""
    return max(slots, key=lambda s: (s.start_date, s.id)).art if slots else "baustelle"


def ziel_finden(slots: list[PlanningSlot], wer: Wer, tage: list[date], arbeitstag, karte: PlanningSlot | None = None) -> tuple[PlanningSlot | None, str]:
    """Wohin die Tage kommen -- (Einsatz, "dazu" | "verlaengert") oder (None, "neu"). Regeln im Kopf des Moduls; die Kran-Regeln prüft _kran_pruefen()."""
    von, bis = min(tage), max(tage)
    if karte is not None:
        if wer.art != "kolonne" or _team(karte) == wer.id:
            return karte, "dazu"
        # Antwort 8: eine Kolonne auf dem Einsatz einer anderen Kolonne (oder ohne Kolonne) bekommt einen eigenen
    kandidaten = [s for s in slots if _team(s) == wer.id] if wer.art == "kolonne" else slots
    reihenfolge = (lambda s: (s.start_date, s.id)) if wer.art == "kolonne" else (lambda s: (_team(s) is not None, s.start_date, s.id))
    deckend = [s for s in kandidaten if s.start_date <= bis and s.end_date >= von]
    if deckend:
        return min(deckend, key=reihenfolge), "dazu"
    vorne = [s for s in kandidaten if anschliessend(s.end_date, von, arbeitstag)]
    hinten = [s for s in kandidaten if anschliessend(bis, s.start_date, arbeitstag)]
    for liste in (vorne, hinten):  # der vordere zuerst (Befund D b), nie zusammenlegen
        if liste:
            return min(liste, key=reihenfolge), "verlaengert"
    return None, "neu"


def _kran_pruefen(wer: Wer, ziel: PlanningSlot | None, aktion: str, karte: PlanningSlot | None, slots: list[PlanningSlot]) -> str:
    """Antwort 8; gibt die Art eines neuen Einsatzes zurück."""
    if wer.art == "kolonne" and karte is not None and karte.art == "kranvermietung":
        raise BesetzungUngueltig(KRAN_KOLONNE)
    art = ziel.art if ziel is not None else _art_des_auftrags(slots)
    if art == "kranvermietung":
        if wer.art == "kolonne":
            raise BesetzungUngueltig(KRAN_KOLONNE)
        if wer.art == "person" and aktion != "dazu":
            raise BesetzungUngueltig(KRAN_ZUERST)
    return art


def _eintraege(db: Session, wer: Wer, tage: list[date]) -> list[dict]:
    """Was an den Tagen dazukommt: die Person, das Gerät -- oder die Kolonne mit ihren Mitgliedern ohne „nicht zeigen“ und ihren Geräten (Antwort 9)."""
    if wer.art == "person":
        return [{"employee_id": wer.id, "tage": tage}]
    if wer.art == "geraet":
        return [{"resource_id": wer.id, "tage": tage}]
    team = _load_team(db, wer.id)
    if team is None or not team.active:
        raise BesetzungUngueltig("Kolonne / Team wurde nicht gefunden oder ist inaktiv.")
    eintraege = [{"employee_id": eid, "tage": tage} for eid in _kolonne_schlaegt_vor(db, wer.id)]
    eintraege += [{"resource_id": g["resource_id"], "tage": tage} for g in _kolonne_schlaegt_geraete_vor(db, wer.id)]
    if not eintraege:
        raise BesetzungUngueltig(KOLONNE_LEER)
    return eintraege


def _schluessel(w: dict) -> tuple:
    """Eine Warnung, unabhängig davon, an welchem der beiden Einsätze sie steht: Art, Text, wen sie betrifft, der andere Einsatz. Ihre Tage zählen
    getrennt (_tage_der_warnung()) -- seit 1.9.268: weniger Tage machen eine Warnung nicht neu (bis 1.9.267 waren die Tage Teil des Schlüssels)."""
    return (w["type"], w.get("label"), w.get("employee_id"), w.get("resource_id"), w.get("other_slot_id"))


def _tage_der_warnung(w: dict) -> set[str]:
    """Die Tage einer Warnung: ihre Tage (Person, Gerät doppelt) oder ihr Tag."""
    return {str(t) for t in w.get("tage") or ()} or {str(w.get("date"))}


def _warnungen(db: Session, slots: list[PlanningSlot]) -> dict[tuple, set[str]]:
    """Die Warnungen dieser Einsätze vor der Aktion -- je Warnung ihre Tage."""
    vorher: dict[tuple, set[str]] = {}
    for s in slots:
        for w in einsatz_konflikte(db, s)["warnungen"]:
            vorher.setdefault(_schluessel(w), set()).update(_tage_der_warnung(w))
    return vorher


def setzen_offen(db: Session, order: Order, wer: Wer, tage: list[date], *, karte: PlanningSlot | None = None) -> tuple[PlanningSlot, str]:
    """Setzt wer an diese Tage dieses Auftrags (ohne Commit, ohne Warnungen; der Aufrufer hält die Sperre). Gibt Einsatz und Aktion zurück."""
    prep_id = _prep_id(db, order.id)
    slots = _einsaetze(db, prep_id)
    ziel, aktion = ziel_finden(slots, wer, tage, _arbeitstag(db, min(tage), max(tage)), karte)
    art = _kran_pruefen(wer, ziel, aktion, karte, slots)
    eintraege = _eintraege(db, wer, tage)
    if ziel is None:  # neu: vorläufig, Stunden = Rest (wie das Anlegen), mit Kolonne nur, wenn eine Kolonne gezogen wurde
        einzeln = None if len(tage) == (max(tage) - min(tage)).days + 1 else tage
        slot = _create_slot(db, order_id=order.id, team_id=wer.id if wer.art == "kolonne" else None, start_date=min(tage), end_date=max(tage), art=art,
                            besetzung=[{"employee_id": wer.id, "tage": einzeln}] if wer.art == "person" else None,
                            geraete=[{"resource_id": wer.id, "tage": einzeln}] if wer.art == "geraet" else None, trotzdem_planen=True, _offen=True)
        return slot, "neu"
    slot = _update_slot(db, ziel.id, start_date=min(ziel.start_date, min(tage)), end_date=max(ziel.end_date, max(tage)), alle_tage_mitnehmen=False,
                        dazu=eintraege, trotzdem_planen=True, _offen=True)
    return slot, aktion


def tage_von(slot: PlanningSlot, wer: Wer) -> list[str]:
    """Die Tage der Person bzw. des Geräts am Einsatz (alle einzeln); bei einer Kolonne leer (ihre Mitglieder haben je ihre Tage)."""
    if wer.art == "kolonne":
        return []
    zeilen = [x for x in slot.besetzung if x.employee_id == wer.id] if wer.art == "person" else [x for x in slot.geraete if x.resource_id == wer.id]
    tage: set[date] = set()
    for x in zeilen:
        tage |= _tage_der_zeile(slot, x)
    return [t.isoformat() for t in sorted(tage)]


def neue_warnungen(db: Session, beruehrt: list[PlanningSlot], vorher: dict[tuple, set[str]]) -> list[dict]:
    """Die Warnungen, die die Aktion neu bringt -- eine Warnung, die es vorher nicht gab, oder ein Tag, den sie vorher nicht hatte (vorher: _warnungen() vor
    der Aktion). Hat eine Warnung danach nur weniger Tage (Herausnehmen, Umsetzen), ist sie nicht neu. Jede einmal, auch wenn sie an zwei berührten
    Einsätzen steht. Hinweise fragen nie."""
    neue, gesehen = [], set()
    for s in beruehrt:
        for w in einsatz_konflikte(db, s)["warnungen"]:
            k, tage = _schluessel(w), _tage_der_warnung(w)
            if (k not in vorher or not tage <= vorher[k]) and (k, frozenset(tage)) not in gesehen:
                gesehen.add((k, frozenset(tage)))
                neue.append(w)
    return neue


def abschliessen(db: Session, beruehrt: list[PlanningSlot], vorher: dict[tuple, set[str]], *, trotzdem_planen: bool) -> list[int]:
    """Nach dem Flush: fragt bei neuen Warnungen (PlanungsWarnung, alles zurück -- eine Rückfrage für alle), sonst Kran-Kalender abgleichen, Commit,
    Termine senden. beruehrt: die Einsätze, die es nach der Aktion noch gibt (das Ziel zuerst)."""
    if not trotzdem_planen:
        neue = neue_warnungen(db, beruehrt, vorher)
        if neue:
            hinweise = einsatz_konflikte(db, beruehrt[0])["hinweise"] if beruehrt else []
            db.rollback()
            raise PlanungsWarnung(neue, hinweise)
    zu_senden: list[int] = []
    for s in beruehrt:
        zu_senden += kran_kalender.abgleichen(db, _load_slot(db, s.id, frisch=True))
    db.commit()
    kran_kalender.senden(db, zu_senden)
    return [s.id for s in beruehrt]


def pruefung(db: Session, beruehrt: list[PlanningSlot], vorher: dict[tuple, set[str]]) -> dict:
    """Prüfen ohne Schreiben: die Warnungen, die fragen würden, und die Hinweise am Ziel (der Aufrufer nimmt danach alles zurück)."""
    neue = neue_warnungen(db, beruehrt, vorher)
    hinweise = einsatz_konflikte(db, beruehrt[0])["hinweise"] if beruehrt else []
    return {"warnungen": neue, "hinweise": hinweise, "fragt": bool(neue)}


def tag_setzen(db: Session, *, order_id: int, tag: date, employee_id: int | None = None, team_id: int | None = None, resource_id: int | None = None,
               slot_id: int | None = None, trotzdem_planen: bool = False, pruefen: bool = False) -> dict:
    """Aus der Liste (Punkt 1): eine Person, eine Kolonne oder ein Gerät für diesen Tag an diesen Auftrag -- dazu, verlängert oder neu. Ergebnis:
    aktion, slot_id, tage (der Gesetzten am Einsatz), bis (letzter Tag des Einsatzes); mit pruefen dazu warnungen, hinweise, fragt -- und nichts bleibt."""
    try:
        wer = wer_aus(employee_id, team_id, resource_id)
        order = _auftrag(db, order_id)
        prep_id = _prep_id(db, order.id)
        _sperren(db, [prep_id])
        vorher = _warnungen(db, _einsaetze(db, prep_id))
        karte = _karte(db, order, slot_id, [tag])
        slot, aktion = setzen_offen(db, order, wer, [tag], karte=karte)
        ergebnis = {"aktion": aktion, "slot_id": slot.id if aktion != "neu" or not pruefen else None, "tage": tage_von(slot, wer),
                    "bis": slot.end_date.isoformat()}
        if pruefen:
            ergebnis.update(pruefung(db, [slot], vorher))
            db.rollback()
            return ergebnis
        abschliessen(db, [slot], vorher, trotzdem_planen=trotzdem_planen)
        return ergebnis
    except Exception:
        db.rollback()
        raise


# --- seit 1.9.268 (Punkt 2): Umsetzen, Herausnehmen, Verlängern -------------------------------------------------------------------------------

TAGE_ODER_ALLE = "Bitte die Tage nennen oder „alle“, nicht beides."
NICHTS_ZU_VERLAENGERN = "Der Tag ist schon der letzte Tag des Einsatzes."


def _person_oder_geraet(employee_id: int | None, resource_id: int | None) -> Wer:
    """Umsetzen, Herausnehmen und Verlängern nehmen eine Person oder ein Gerät -- keine Kolonne (ihre Mitglieder haben je ihre Tage)."""
    return wer_aus(employee_id, None, resource_id)


def _einsatz(db: Session, slot_id: int) -> PlanningSlot:
    slot = db.get(PlanningSlot, slot_id)
    if slot is None:
        raise IdNichtGefunden("Einsatz wurde nicht gefunden.")
    return slot


def _feld(wer: Wer) -> str:
    return "employee_id" if wer.art == "person" else "resource_id"


def _seine_tage(slot: PlanningSlot, wer: Wer) -> set[date] | None:
    """Die Tage der Person bzw. des Geräts an diesem Einsatz; None, wenn sie gar nicht daran steht."""
    zeilen = slot.besetzung if wer.art == "person" else slot.geraete
    zeile = next((x for x in zeilen if getattr(x, _feld(wer)) == wer.id), None)
    return _tage_der_zeile(slot, zeile) if zeile is not None else None


def _an_den_tagen(slot: PlanningSlot, wer: Wer, tage: list[date]) -> None:
    """Die Person bzw. das Gerät steht am Einsatz -- an allen genannten Tagen (sonst 422)."""
    seine = _seine_tage(slot, wer)
    if seine is None or not set(tage) <= seine:
        raise BesetzungUngueltig(("Die Person" if wer.art == "person" else "Das Gerät") + " steht an diesen Tagen nicht am Einsatz.")


def _leer_frage(wenn_leer: str | None, pruefen: bool) -> str | None:
    """Prüfen fragt nicht nach „niemand mehr“, es sagt es (leer); beim Speichern fragt _update_slot() ohne wenn_leer zurück (EinsatzWirdLeer)."""
    return wenn_leer if wenn_leer is not None or not pruefen else "behalten"


def umsetzen(db: Session, *, slot_id: int, tage: list[date], ziel_tag: date, employee_id: int | None = None, resource_id: int | None = None,
             ziel_order_id: int | None = None, ziel_slot_id: int | None = None, trotzdem_planen: bool = False, wenn_leer: str | None = None,
             pruefen: bool = False) -> dict:
    """Aus einer Zelle (Punkt 2): eine Person oder ein Gerät für diese Tage auf einen anderen Auftrag oder Tag -- setzen und herausnehmen in einer
    Transaktion. Die Tage wandern um gleich viele Kalendertage (der erste auf ziel_tag); das Ziel nach den Regeln von Tag setzen (Karte = ziel_slot_id,
    Antwort 6). Beide Arbeitsvorbereitungen werden aufsteigend gesperrt. Wird der Einsatz, aus dem sie kommt, leer: Rückfrage (Antwort 3), wenn_leer."""
    try:
        wer = _person_oder_geraet(employee_id, resource_id)
        quelle = _einsatz(db, slot_id)
        tage = sorted(set(tage))
        if not tage:
            raise BesetzungUngueltig("Bitte mindestens einen Tag nennen.")
        ziel_tage = [t + (ziel_tag - tage[0]) for t in tage]
        ziel_order = _auftrag(db, ziel_order_id if ziel_order_id is not None else quelle.preparation.order_id)
        q_prep, z_prep = quelle.preparation_id, _prep_id(db, ziel_order.id)
        _sperren(db, [q_prep, z_prep])
        quelle = _load_slot(db, slot_id, frisch=True)
        _an_den_tagen(quelle, wer, tage)
        vorher = _warnungen(db, _einsaetze(db, q_prep) + ([] if z_prep in (None, q_prep) else _einsaetze(db, z_prep)))
        karte = _karte(db, ziel_order, ziel_slot_id, ziel_tage)
        ziel, aktion = setzen_offen(db, ziel_order, wer, ziel_tage, karte=karte)
        ziel_id, quelle_id = ziel.id, quelle.id
        weg = [t for t in tage if t not in ziel_tage] if ziel_id == quelle_id else tage  # im selben Einsatz bleiben die Tage, die sie behält
        danach = (_update_slot(db, quelle_id, weg=[{_feld(wer): wer.id, "tage": weg}], wenn_leer=_leer_frage(wenn_leer, pruefen), trotzdem_planen=True,
                               _offen=True) if weg else _load_slot(db, quelle_id, frisch=True))
        ziel = _load_slot(db, ziel_id, frisch=True)
        leer = ziel_id != quelle_id and (danach is None or not _besetzte_tage(danach))
        beruehrt = [ziel] + ([danach] if danach is not None and danach.id != ziel_id else [])
        ergebnis = {"aktion": "umgesetzt", "ziel_aktion": aktion, "slot_id": ziel_id if aktion != "neu" or not pruefen else None, "quelle_id": quelle_id,
                    "quelle_geloescht": danach is None, "tage": tage_von(ziel, wer), "bis": ziel.end_date.isoformat()}
        if pruefen:
            ergebnis.update(pruefung(db, beruehrt, vorher), leer=leer)
            db.rollback()
            return ergebnis
        abschliessen(db, beruehrt, vorher, trotzdem_planen=trotzdem_planen)
        return ergebnis
    except Exception:
        db.rollback()
        raise


def herausnehmen(db: Session, *, slot_id: int, employee_id: int | None = None, resource_id: int | None = None, tage: list[date] | None = None,
                 alle: bool = False, wenn_leer: str | None = None, pruefen: bool = False) -> dict:
    """Eine Person oder ein Gerät für diese Tage (oder alle) aus dem Einsatz nehmen (Punkt 2). Am Rand kürzt der Einsatz, in der Mitte bleibt eine Lücke;
    wird er ganz leer: Rückfrage „Der Einsatz hat dann niemanden mehr.“ (Antwort 3), wenn_leer. Herausnehmen bringt keine neue Warnung und fragt nicht."""
    try:
        wer = _person_oder_geraet(employee_id, resource_id)
        if (tage is None) == (not alle):
            raise BesetzungUngueltig(TAGE_ODER_ALLE)
        slot = _einsatz(db, slot_id)
        _sperren(db, [slot.preparation_id])
        slot = _load_slot(db, slot_id, frisch=True)
        _an_den_tagen(slot, wer, [] if alle else tage)
        vorher = _warnungen(db, _einsaetze(db, slot.preparation_id))
        danach = _update_slot(db, slot.id, weg=[{_feld(wer): wer.id, "tage": None if alle else tage}], wenn_leer=_leer_frage(wenn_leer, pruefen),
                              trotzdem_planen=True, _offen=True)
        leer = danach is None or not _besetzte_tage(danach)
        ergebnis = {"aktion": "herausgenommen", "slot_id": danach.id if danach is not None else None, "geloescht": danach is None,
                    "tage": tage_von(danach, wer) if danach is not None else [], "bis": danach.end_date.isoformat() if danach is not None else None}
        if pruefen:
            ergebnis.update(pruefung(db, [danach] if danach is not None else [], vorher), leer=leer)
            db.rollback()
            return ergebnis
        abschliessen(db, [danach] if danach is not None else [], vorher, trotzdem_planen=True)
        return ergebnis
    except Exception:
        db.rollback()
        raise


def verlaengern(db: Session, *, slot_id: int, ab_tag: date, employee_id: int | None = None, resource_id: int | None = None,
                trotzdem_planen: bool = False, pruefen: bool = False) -> dict:
    """„bis <letzter Tag des Einsatzes> verlängern“ (Punkt 2): die Person bzw. das Gerät steht an ab_tag und danach an jedem Tag bis zum Ende des Einsatzes.
    Prüft wie Planen (Rückfrage bei neuen Warnungen)."""
    try:
        wer = _person_oder_geraet(employee_id, resource_id)
        slot = _einsatz(db, slot_id)
        _sperren(db, [slot.preparation_id])
        slot = _load_slot(db, slot_id, frisch=True)
        _an_den_tagen(slot, wer, [ab_tag])
        neue_tage = [ab_tag + timedelta(days=n) for n in range(1, (slot.end_date - ab_tag).days + 1)]
        if not neue_tage:
            raise BesetzungUngueltig(NICHTS_ZU_VERLAENGERN)
        vorher = _warnungen(db, _einsaetze(db, slot.preparation_id))
        danach = _update_slot(db, slot.id, dazu=[{_feld(wer): wer.id, "tage": neue_tage}], trotzdem_planen=True, _offen=True)
        ergebnis = {"aktion": "verlaengert", "slot_id": danach.id, "tage": tage_von(danach, wer), "bis": danach.end_date.isoformat()}
        if pruefen:
            ergebnis.update(pruefung(db, [danach], vorher))
            db.rollback()
            return ergebnis
        abschliessen(db, [danach], vorher, trotzdem_planen=trotzdem_planen)
        return ergebnis
    except Exception:
        db.rollback()
        raise
