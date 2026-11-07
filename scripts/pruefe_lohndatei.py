"""Prüfung: die Lohndatei des ERP gegen die Datei aus Time 4 (seit 1.9.227, Lohn L1b, Punkt 4; Prüfweg aus dem L0-Befund, Abschnitt 6).

Für den Probemonat: zwei Dateien desselben Monats, je Person und Tag verglichen, nie Zeile für Zeile. Nur lesend, keine Datenbank, kein Netz.

    .venv/bin/python scripts/pruefe_lohndatei.py ERP.txt TIME4.txt [--azubis 00291,00202] [--gleich 91008=91016] [--pausen 6:30,9:45]

Schritte:
  1  Form beider Dateien: ASCII, CRLF auch nach der letzten Zeile, Kopf Berater;Mandant;MM/JJJJ, jede Zeile 11 Felder; Tageszeile
     Personalnummer;Tag;Kennzeichen;Lohnart;Stunden;;;;;; (Tag im Monat, Kennzeichen 1–2 Zeichen 0–9/A–Z, Lohnart Ziffern oder leer, Stunden mit
     Komma und zwei Stellen), Monatszeile Personalnummer;;;Lohnart;;;Stunden;;;; -- ein Formfehler ist sofort rot (Rückgabe 2).
  2  Köpfe: Berater, Mandant, Monat.
  3  Je Person und Tag die Kennzeichen beider Seiten; Personen über die Nummer mit führenden Nullen auf 5 Stellen (9005 = 09005), --gleich ordnet
     eine Nummer aus Time 4 einer anderen im ERP zu (Nummernwechsel).
  4  Monatszeilen (8110) gegen die Tageszeilen Schlechtwetter des ERP (WA).
  5  Summen je Person und Kennzeichen.

Jede Abweichung bekommt eine Klasse. Als „erklärt“ gelten die erwarteten Abweichungen aus dem L1b-Befund, Abschnitt 3, und die Rundung:
  Rundung          die Arbeit des ERP ist die von Time 4, je Tag kaufmännisch auf 0,25 h (1.9.223)
  Pause            die Arbeit des ERP ist die Anwesenheit nach Time 4 (Arbeit + abgezogene feste Pause, 0/30/45 min oder ein Teil davon) mit der
                   gesetzlichen Pause nach Lesart A, je Tag auf 0,25 h -- Samstag und ohne Zeitmodell (Time 4 ohne Pause), Winter-Zeitmodell
                   über 9:00 h, unter 6:00 h über die Mittagspause, eine Lücke über der festen Pause (Befund 3.8 a–e)
  Schlechtwetter   die Monatszeile 8110 von Time 4 gegen die Tageszeilen WA des ERP derselben Person, gleiche Summe (3.1)
  Heiligabend      am 24.12. FR im ERP, in Time 4 Arbeit mit der Sollzeit (3.2)
  Silvester        am 31.12. UU im ERP, in Time 4 Urlaub (3.3)
  Berufsschule     FE nur im ERP (3.4)
  Mehrarbeit       AA nur im ERP; am Tag zählen Arbeit und Mehrarbeit des ERP zusammen gegen die Arbeit von Time 4 (3.5)
  Nummer           dieselbe Person mit 4 und 5 Stellen (3.6)
  Azubi            eine Zeile nur im ERP für eine Person aus --azubis (Time 4 gab Azubis nur mit U und K aus, 3.7)
Alles andere ist „zu klären“: Kennzeichen nur auf einer Seite, andere Lohnart, andere Stunden ohne Erklärung, eine Monatszeile mit anderer Summe.

Rückgabe: 0 nur Erklärtes, 1 etwas zu klären, 2 eine Datei nicht lesbar oder mit Formfehler.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rounding import round_quarter_hours  # noqa: E402
from app.work_time_models import pflichtpause  # noqa: E402

KOPF = re.compile(r"^(\d+);(\d+);(0[1-9]|1[0-2])/(\d{4})$")
KENNZEICHEN = re.compile(r"^[0-9A-Z]{1,2}$")
LOHNART = re.compile(r"^[0-9]{0,4}$")
STUNDEN = re.compile(r"^\d+,\d\d$")
NUMMER = re.compile(r"^\d{1,5}$")
NULL = Decimal("0")


class Formfehler(Exception):
    pass


@dataclass
class Datei:
    name: str
    berater: str
    mandant: str
    monat: date
    tage: dict = field(default_factory=lambda: defaultdict(dict))  # (Nummer, Tag) -> {Kennzeichen: (Lohnart, Stunden)}
    monatszeilen: dict = field(default_factory=lambda: defaultdict(Decimal))  # (Nummer, Lohnart) -> Stunden
    roh: dict = field(default_factory=dict)  # Nummer (5 Stellen) -> wie in der Datei
    zeilen: int = 0


def _stunden(text: str) -> Decimal:
    return Decimal(text.replace(",", "."))


def lesen(pfad: Path, name: str, gleich: dict[str, str] | None = None) -> Datei:
    """Liest und prüft die Form; Formfehler mit Zeile."""
    try:
        roh = pfad.read_bytes()
    except OSError as exc:
        raise Formfehler(f"{name}: nicht lesbar ({type(exc).__name__})") from exc
    try:
        text = roh.decode("ascii")
    except UnicodeDecodeError as exc:
        raise Formfehler(f"{name}: kein ASCII (Byte {exc.start})") from exc
    if not text.endswith("\r\n") or "\n" in text.replace("\r\n", "") or "\r" in text.replace("\r\n", ""):
        raise Formfehler(f"{name}: Zeilenende nicht durchgehend CRLF (auch nach der letzten Zeile)")
    zeilen = text.split("\r\n")[:-1]
    if not zeilen:
        raise Formfehler(f"{name}: leer")
    k = KOPF.match(zeilen[0])
    if not k:
        raise Formfehler(f"{name}, Zeile 1: Kopf nicht Berater;Mandant;MM/JJJJ: {zeilen[0]!r}")
    d = Datei(name, k.group(1), k.group(2), date(int(k.group(4)), int(k.group(3)), 1))
    for nr, z in enumerate(zeilen[1:], start=2):
        f = z.split(";")
        if len(f) != 11:
            raise Formfehler(f"{name}, Zeile {nr}: {len(f)} statt 11 Felder: {z!r}")
        if not NUMMER.match(f[0]):
            raise Formfehler(f"{name}, Zeile {nr}: Personalnummer {f[0]!r}")
        nummer = (gleich or {}).get(f[0], f[0]).zfill(5)
        d.roh.setdefault(nummer, f[0])
        if f[1] == "":  # Monatszeile
            if f[2] or f[4] or any(f[i] for i in (5, 7, 8, 9, 10)) or not re.match(r"^\d{1,4}$", f[3]) or not STUNDEN.match(f[6]):
                raise Formfehler(f"{name}, Zeile {nr}: Monatszeile nicht Personalnummer;;;Lohnart;;;Stunden;;;;: {z!r}")
            d.monatszeilen[(nummer, f[3])] += _stunden(f[6])
        else:
            if any(f[5:]):
                raise Formfehler(f"{name}, Zeile {nr}: Felder 6 bis 11 nicht leer: {z!r}")
            try:
                tag = d.monat.replace(day=int(f[1]))
            except ValueError as exc:
                raise Formfehler(f"{name}, Zeile {nr}: Tag {f[1]!r} nicht im Monat") from exc
            if f[1] != str(tag.day) or not KENNZEICHEN.match(f[2]) or not LOHNART.match(f[3]) or not STUNDEN.match(f[4]):
                raise Formfehler(f"{name}, Zeile {nr}: Tageszeile nicht Personalnummer;Tag;Kennzeichen;Lohnart;Stunden;;;;;;: {z!r}")
            alt = d.tage[(nummer, tag)].get(f[2])
            d.tage[(nummer, tag)][f[2]] = (f[3], (alt[1] if alt else NULL) + _stunden(f[4]))
        d.zeilen += 1
    return d


@dataclass
class Befund:
    nummer: str
    tag: date | None
    text: str
    erklaert: bool


def _pause_erklaert(erp: Decimal, t4: Decimal, regeln) -> str | None:
    """Ist die Arbeit des ERP die Anwesenheit nach Time 4 mit der gesetzlichen Pause nach Lesart A, je Tag auf 0,25 h? Die Anwesenheit ist die Arbeit
    von Time 4 plus die abgezogene feste Pause: 0, 30, 45 min oder ein Teil davon (Lücke über der festen Pause)."""
    t4_minuten = int((t4 * 60).to_integral_value())
    for p in [0, 30, 45] + [m for m in range(1, 46) if m not in (30, 45)]:
        anwesend = Decimal(t4_minuten + p) / 60
        if round_quarter_hours(anwesend - Decimal(pflichtpause(regeln, anwesend)) / 60) == erp:
            if p == 0:
                return "Pause: Time 4 ohne Pause (Samstag oder ohne Zeitmodell), das ERP die gesetzliche nach Lesart A"
            if p in (30, 45):
                return f"Pause: Time 4 {p} min feste Pause, das ERP die gesetzliche nach Lesart A ({_h(anwesend)} h anwesend)"
            return f"Pause: Time 4 zog {p} min ab (feste Pause nur zum Teil überdeckt), das ERP die gesetzliche nach Lesart A"
    return None


def _h(wert: Decimal) -> str:
    return f"{wert.quantize(Decimal('0.01')):.2f}".replace(".", ",")


def vergleichen(erp: Datei, t4: Datei, *, azubis: set[str], regeln) -> tuple[list[str], list[Befund]]:
    kopf, befunde = [], []
    for was, a, b in (("Berater", erp.berater, t4.berater), ("Mandant", erp.mandant, t4.mandant), ("Monat", f"{erp.monat:%m/%Y}", f"{t4.monat:%m/%Y}")):
        if a != b:
            befunde.append(Befund("", None, f"Kopf: {was} ERP {a}, Time 4 {b}", False))
    for nummer in sorted(set(erp.roh) & set(t4.roh)):
        if erp.roh[nummer] != t4.roh[nummer]:
            grund = "dieselbe Person mit 5 Stellen" if erp.roh[nummer].zfill(5) == t4.roh[nummer].zfill(5) else "Nummernwechsel (--gleich)"
            befunde.append(Befund(nummer, None, f"Nummer: ERP {erp.roh[nummer]}, Time 4 {t4.roh[nummer]} -- {grund}", True))
    # Schlechtwetter: Monatszeile von Time 4 gegen die Tageszeilen WA des ERP
    wa_tage: dict[str, list[date]] = defaultdict(list)
    for (nummer, tag), kz in erp.tage.items():
        if "WA" in kz:
            wa_tage[nummer].append(tag)
    wa_erklaert: set[str] = set()
    for (nummer, lohnart), stunden in sorted(t4.monatszeilen.items()):
        erp_monat = erp.monatszeilen.get((nummer, lohnart))
        if erp_monat is not None:
            if erp_monat != stunden:
                befunde.append(Befund(nummer, None, f"Monatszeile {lohnart}: ERP {_h(erp_monat)}, Time 4 {_h(stunden)}", False))
            continue
        wa = sum((erp.tage[(nummer, t)]["WA"][1] for t in wa_tage.get(nummer, [])), NULL)
        gleich = wa == stunden and wa > 0
        if gleich:
            wa_erklaert.add(nummer)
        befunde.append(Befund(nummer, None, f"Monatszeile {lohnart} (Time 4) {_h(stunden)} h, im ERP WA je Tag {_h(wa)} h an "
                                            f"{len(wa_tage.get(nummer, []))} Tagen" + ("" if gleich else " -- Summe abweichend"), gleich))
    for (nummer, lohnart), stunden in sorted(erp.monatszeilen.items()):
        if (nummer, lohnart) not in t4.monatszeilen:
            befunde.append(Befund(nummer, None, f"Monatszeile {lohnart} nur im ERP: {_h(stunden)} h", False))
    # je Person und Tag
    for nummer, tag in sorted(set(erp.tage) | set(t4.tage)):
        e, t = erp.tage.get((nummer, tag), {}), t4.tage.get((nummer, tag), {})
        azubi = nummer in azubis
        offen_e, offen_t = dict(e), dict(t)
        for kz in set(e) & set(t):
            if e[kz] == t[kz]:
                offen_e.pop(kz), offen_t.pop(kz)
            elif e[kz][0] != t[kz][0]:
                befunde.append(Befund(nummer, tag, f"{kz}: Lohnart ERP {e[kz][0] or 'leer'}, Time 4 {t[kz][0] or 'leer'}", False))
                offen_e.pop(kz), offen_t.pop(kz)
        # Arbeit (1) und Mehrarbeit (AA) des ERP zusammen gegen die Arbeit von Time 4
        if "1" in offen_t or ("1" in t and "AA" in offen_e):
            erp_arbeit = sum((e[k][1] for k in ("1", "AA") if k in e), NULL)
            t4_arbeit = t["1"][1]
            mit_aa = " (Arbeit und Mehrarbeit des ERP zusammen)" if "AA" in e else ""
            if erp_arbeit == t4_arbeit:
                grund = "Mehrarbeit Azubi (AA / 1900), zusammen wie die Arbeit von Time 4" if "AA" in e else None
            elif "1" in e or "AA" in e:
                grund = ("Rundung: die Arbeit des Tags auf 0,25 h" if round_quarter_hours(t4_arbeit) == erp_arbeit
                         else _pause_erklaert(erp_arbeit, t4_arbeit, regeln))
            elif tag.month == 12 and tag.day == 24 and "FR" in e:
                grund = "Heiligabend: Time 4 Arbeitstag, das ERP FR / 1080 (Arbeitszeitkalender)"
            else:
                grund = None
            if not (erp_arbeit == t4_arbeit and "AA" not in e):
                befunde.append(Befund(nummer, tag, f"1: ERP {_h(erp_arbeit)}{mit_aa}, Time 4 {_h(t4_arbeit)}" + (f" -- {grund}" if grund else ""),
                                      grund is not None))
            offen_t.pop("1", None)
            offen_e.pop("1", None)
            offen_e.pop("AA", None)
        for kz, (la, h) in sorted(offen_e.items()):
            if kz == "AA":
                grund = "Mehrarbeit Azubi (AA / 1900)"
            elif kz == "FE":
                grund = "Berufsschule (FE), in Time 4 nicht ausgegeben"
            elif kz == "FR" and (tag.month, tag.day) == (12, 24):
                grund = "Heiligabend (FR / 1080)"
            elif kz == "UU" and (tag.month, tag.day) == (12, 31):
                grund = "Silvester (UU), in Time 4 Urlaub" if "U" in offen_t else "Silvester (UU)"
            elif kz == "WA" and nummer in wa_erklaert:
                grund = "Schlechtwetter je Tag (WA / 8195) statt Monatszeile 8110"
            elif azubi:
                grund = "Azubi: Time 4 gab nur U und K aus"
            else:
                grund = None
            befunde.append(Befund(nummer, tag, f"{kz}{' / ' + la if la else ''} {_h(h)} nur im ERP" + (f" -- {grund}" if grund else ""), grund is not None))
        for kz, (la, h) in sorted(offen_t.items()):
            grund = "Silvester: das ERP UU (Antwort im Urlaub „frei“)" if kz == "U" and (tag.month, tag.day) == (12, 31) and "UU" in e else None
            befunde.append(Befund(nummer, tag, f"{kz} / {la} {_h(h)} nur in Time 4" + (f" -- {grund}" if grund else ""), grund is not None))
    kopf.append(f"Kopf ERP {erp.berater};{erp.mandant};{erp.monat:%m/%Y}, Time 4 {t4.berater};{t4.mandant};{t4.monat:%m/%Y}. "
                f"{len(set(erp.roh) | set(t4.roh))} Personen, {erp.zeilen} Zeilen ERP, {t4.zeilen} Time 4.")
    return kopf, befunde


def summen(erp: Datei, t4: Datei) -> list[str]:
    def je(d: Datei):
        s = defaultdict(lambda: defaultdict(Decimal))
        for (nummer, _tag), kz in d.tage.items():
            for k, (_la, h) in kz.items():
                s[nummer][k] += h
        for (nummer, la), h in d.monatszeilen.items():
            s[nummer][f"M{la}"] += h
        return s

    a, b = je(erp), je(t4)
    zeilen = ["Summen je Person (ERP/Time 4):"]
    for nummer in sorted(set(a) | set(b)):
        kz = sorted(set(a[nummer]) | set(b[nummer]), key=lambda k: (k != "1", k))
        zeilen.append(f"  {nummer}  " + "  ".join(f"{k} {_h(a[nummer][k])}/{_h(b[nummer][k])}" for k in kz))
    return zeilen


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Lohndatei des ERP gegen die Datei aus Time 4")
    parser.add_argument("erp", type=Path)
    parser.add_argument("time4", type=Path)
    parser.add_argument("--azubis", default="", help="Personalnummern der Azubis, mit Komma (Time 4 gab sie nur mit U und K aus)")
    parser.add_argument("--gleich", action="append", default=[], help="Nummer in Time 4 = Nummer im ERP (Nummernwechsel), z. B. 91008=91016")
    parser.add_argument("--pausen", default="6:30,9:45", help="Pausenregeln Schwelle:Minuten (Vorgabe 6:30,9:45 wie § 4 ArbZG)")
    args = parser.parse_args(argv)
    try:
        regeln = [(Decimal(s), int(m)) for s, m in (r.split(":") for r in args.pausen.split(","))]
        gleich = dict(g.split("=", 1) for g in args.gleich)
        erp, t4 = lesen(args.erp, "ERP"), lesen(args.time4, "Time 4", gleich)
    except Formfehler as exc:
        print(f"Formfehler: {exc}")
        return 2
    except ValueError as exc:
        print(f"Aufruf: {exc}")
        return 2
    kopf, befunde = vergleichen(erp, t4, azubis={n.strip().zfill(5) for n in args.azubis.split(",") if n.strip()}, regeln=regeln)
    print("\n".join(kopf))
    for b in befunde:
        wo = f"{b.nummer}  {b.tag:%d.%m.}" if b.tag else (b.nummer or "-")
        print(f"  {'erklärt   ' if b.erklaert else 'zu klären '} {wo}  {b.text}")
    offen = sum(1 for b in befunde if not b.erklaert)
    print("\n".join(summen(erp, t4)))
    print(f"{len(befunde)} Abweichungen, davon {offen} zu klären." if befunde else "Keine Abweichung.")
    return 1 if offen else 0


if __name__ == "__main__":
    sys.exit(main())
