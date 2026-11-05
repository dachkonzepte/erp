"""Vergebene Personalnummern in die Sperrliste einlesen -- seit 1.9.213 (L1a Stufe 6, Punkt 2, Vorgabe Tobias).

Liest eine Datei mit Personalnummern, die schon vergeben sind (z. B. vom Lohnbüro: auch Personen, die das ERP nie kannte), und merkt jede
Nummer dauerhaft (Tabelle personalnummern_vergeben, wie seit 1.9.177 jede Nummer, die einer Person im ERP einmal gehörte): danach bekommt
sie im ERP keine andere Person. Trägt eine Person im ERP die Nummer heute, wird sie ihr gemerkt (sie behält sie); sonst ohne Person.

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung:

    set -a; source .env; set +a
    .venv/bin/python scripts/personalnummern_einlesen.py /home/tobias/erp-data/personalnummern.txt [--probe]

Die Datei liegt auf dem Server, nie im Projektordner (nie in Git): das Skript lehnt eine Datei unter dem Projektordner ab. Keine echten
Nummern in Code, Tests oder Beispielen.

Aufbau der Datei: je Zeile eine Nummer; steht mehr in der Zeile (CSV), zählt das erste Feld vor „;“, „,“ oder Tabulator. Leere Zeilen und
Zeilen mit „#“ am Anfang zählen nicht. Eine Zeile, deren erstes Feld keine Zahl ist (Überschrift), wird übersprungen und mit ihrer
Zeilennummer genannt (nie mit ihrem Inhalt -- dort kann ein Name stehen). Eine Nummer aus 1 bis 4 Ziffern wird links mit Nullen auf 5
aufgefüllt (wie die Migration 5d2e8a71c4f3; eine Tabellenkalkulation lässt führende Nullen gern weg). Mehr als 5 Ziffern: Abbruch, nichts
gemerkt.

Mehrfach ausführbar: eine schon gemerkte Nummer bleibt, wie sie ist. Das Skript meldet, was neu dazukam und was schon gemerkt war.
--probe: nur melden, nichts schreiben.

DATABASE_URL muss gesetzt sein (wie bei alembic und scripts/erstes_konto.py), sonst schriebe es in die falsche Datenbank.

Rückgabe: 0 eingelesen (oder Probe), 1 nichts gemerkt (eine Zeile mit mehr als 5 Ziffern), 2 Umgebung oder Datei fehlt, Datei im
Projektordner, Datenbank nicht lesbar.
"""

import argparse
import os
import re
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

# app.* erst in main(), nach der Prüfung von DATABASE_URL (wie scripts/erstes_konto.py)

TRENNER = re.compile(r"[;,\t]")
ZIFFERN = re.compile(r"^[0-9]+$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("datei", help="Datei mit den vergebenen Personalnummern, je Zeile eine (außerhalb des Projektordners)")
    parser.add_argument("--probe", action="store_true", help="nur melden, nichts schreiben")
    return parser


def lesen(text: str) -> tuple[list[str], list[int], list[int], int]:
    """(Nummern in der Reihenfolge der Datei ohne Doppelte, übersprungene Zeilen, Zeilen mit mehr als 5 Ziffern, aufgefüllte)."""
    nummern, uebersprungen, zu_lang, aufgefuellt = [], [], [], 0
    for nr, zeile in enumerate(text.splitlines(), 1):
        zeile = zeile.strip().lstrip("﻿")
        if not zeile or zeile.startswith("#"):
            continue
        feld = TRENNER.split(zeile, 1)[0].strip().strip('"')
        if not ZIFFERN.match(feld):
            uebersprungen.append(nr)
            continue
        if len(feld) > 5:
            zu_lang.append(nr)
            continue
        if len(feld) < 5:
            aufgefuellt += 1
        nummer = feld.zfill(5)
        if nummer not in nummern:
            nummern.append(nummer)
    return nummern, uebersprungen, zu_lang, aufgefuellt


def _liste(nummern: list[str]) -> str:
    return ", ".join(nummern) if nummern else "–"


def _zeilen(nrn: list[int]) -> str:
    return ", ".join(map(str, nrn[:30])) + (f" … (insgesamt {len(nrn)})" if len(nrn) > 30 else "")


def einlesen(db, nummern: list[str], *, probe: bool) -> tuple[list[tuple[str, int | None]], list[str]]:
    """Merkt jede Nummer, die noch nicht gemerkt ist -- mit der Person, die sie heute trägt, sonst ohne. (neu mit Person, schon gemerkt).
    Committet nur ohne probe."""
    from app.models import PersonalnummerVergabe
    from app.time_backoffice import personalnummer_halter

    vorhanden = set(db.scalars(select(PersonalnummerVergabe.nummer).where(PersonalnummerVergabe.nummer.in_(nummern)))) if nummern else set()
    neu, schon = [], []
    for nummer in nummern:
        if nummer in vorhanden:
            schon.append(nummer)
            continue
        halter = personalnummer_halter(db, nummer)
        neu.append((nummer, halter.id if halter is not None else None))
        if not probe:
            db.add(PersonalnummerVergabe(nummer=nummer, employee_id=halter.id if halter is not None else None))
    if probe:
        db.rollback()
    else:
        db.commit()
    return neu, schon


def _sitzung():
    from app.database import SessionLocal
    return SessionLocal()


def main(argv=None, *, sitzung=None, umgebung=None, ausgabe=print) -> int:
    """sitzung/umgebung/ausgabe nur für Tests; im Betrieb eigene Sitzung, os.environ, print."""
    args = _parser().parse_args(argv)
    umgebung = os.environ if umgebung is None else umgebung
    datei = Path(args.datei).resolve()
    if datei == PROJEKT or PROJEKT in datei.parents:
        ausgabe(f"Die Datei liegt im Projektordner ({PROJEKT}) -- dort gehört sie nicht hin (nie in Git). Bitte außerhalb ablegen, "
                "z. B. unter /home/tobias/erp-data/, und von dort einlesen. Nichts gemerkt.")
        return 2
    if sitzung is None and not umgebung.get("DATABASE_URL"):
        ausgabe("DATABASE_URL ist nicht gesetzt -- nichts gemerkt. Zuerst die Umgebung laden: set -a; source .env; set +a")
        return 2
    if not datei.is_file():
        ausgabe(f"Datei nicht gefunden: {datei} -- nichts gemerkt.")
        return 2
    nummern, uebersprungen, zu_lang, aufgefuellt = lesen(datei.read_bytes().decode("utf-8", errors="replace"))
    if uebersprungen:
        ausgabe(f"Übersprungen (erstes Feld keine Zahl), Zeile: {_zeilen(uebersprungen)}")
    if zu_lang:
        ausgabe(f"Mehr als 5 Ziffern, Zeile: {_zeilen(zu_lang)} -- nichts gemerkt. Eine Personalnummer hat genau 5 Ziffern.")
        return 1
    db = sitzung if sitzung is not None else _sitzung()
    try:
        try:
            neu, schon = einlesen(db, nummern, probe=args.probe)
        except SQLAlchemyError as fehler:
            db.rollback()
            ausgabe(f"Die Datenbank ist nicht lesbar oder lehnt ab ({type(fehler).__name__}) -- nichts gemerkt. "
                    "Stimmt DATABASE_URL, und sind die Migrationen eingespielt?")
            return 2
    finally:
        if sitzung is None:
            db.close()
    vorsatz = "Probe, nichts geschrieben -- " if args.probe else ""
    ausgabe(f"{vorsatz}Nummern in der Datei: {len(nummern)}" + (f" (davon auf 5 Ziffern aufgefüllt: {aufgefuellt})" if aufgefuellt else ""))
    mit = [f"{n} (Person {eid})" for n, eid in neu if eid is not None]
    ohne = [n for n, eid in neu if eid is None]
    ausgabe(f"{'Würde neu gemerkt' if args.probe else 'Neu gemerkt'}: {len(neu)}" + (f" -- {_liste(mit + ohne)}" if neu else ""))
    if mit:
        ausgabe(f"  davon einer Person im ERP gemerkt, die sie heute trägt: {len(mit)}")
    ausgabe(f"Schon gemerkt: {len(schon)}" + (f" -- {_liste(schon)}" if schon else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
