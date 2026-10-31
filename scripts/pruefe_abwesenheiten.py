"""Prüfung: passen Kategorie und Art jeder Abwesenheit zusammen? (seit 1.9.153, Stufe 6, R1 Nachrunde, Punkt 4)

Bis 1.9.152 ließ sich eine Abwesenheit als „Krankheit“ mit der Art „Urlaub“ eintragen (Befund Stufe 6, D2); seit 1.9.153 lehnt der Server das beim Anlegen ab, was schon dasteht, bleibt
unverändert. Das Skript zeigt, was davon im Bestand liegt: die Anzahl je Kategorie × Art, die Widersprüche und wie viele Anträge aus der Migration b2c7f4e19a06 stammen (Abwesenheiten, die
vor 1.9.146 direkt auf der Plantafel entstanden). Was zusammenpasst, sagt nur app/absence_requests.py::ist_widerspruch(). Als Widerspruch nennt es Abwesenheiten und offene Anträge: genehmigte
Anträge tragen dieselben Werte wie ihre Abwesenheit, abgelehnte und zurückgezogene wirken nicht.

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung und dem Python des Servers:

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/pruefe_abwesenheiten.py

Nur lesen: die Sitzung ist schreibgeschützt (PostgreSQL: SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY, SQLite: PRAGMA query_only), wird am Ende zurückgerollt und schreibt nichts -- auch
keine Zeile im Änderungsprotokoll.

DATABASE_URL muss gesetzt sein, wie bei alembic und scripts/erstes_konto.py: ohne sie fiele app/database.py still auf eine SQLite-Datei zurück, und das Skript prüfte die falsche Datenbank.

Ausgabe: je Widerspruch ID, Zeitraum, Kategorie und Art -- nie ein Name und nie die Notiz. Rückgabe: 0 keine Widersprüche, 1 Widersprüche, 2 Umgebung fehlt (DATABASE_URL, Datenbank nicht lesbar).
"""

import argparse
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, event, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

# app.* erst nach der Prüfung von DATABASE_URL: app.database baut seine Engine beim ersten Import aus der Umgebung (fehlt sie, still SQLite).


@dataclass
class Widerspruch:
    was: str
    id: int
    von: object
    bis: object
    kategorie: str
    art: str


@dataclass
class Stand:
    abwesenheiten: Counter = field(default_factory=Counter)
    antraege: Counter = field(default_factory=Counter)
    aus_migration: int = 0
    widersprueche: list[Widerspruch] = field(default_factory=list)


def pruefen(db) -> Stand:
    """Liest nur; je Tabelle nur die Spalten, die in die Ausgabe gehören -- ein Name kann so nicht hineingeraten."""
    from app.absence_requests import MIGRATION_VERMERK, ist_widerspruch
    from app.models import EmployeeAbsence, EmployeeAbsenceRequest

    stand = Stand()
    for i, kategorie, art, von, bis in db.execute(select(EmployeeAbsence.id, EmployeeAbsence.absence_category, EmployeeAbsence.absence_type, EmployeeAbsence.start_date,
                                                        EmployeeAbsence.end_date).order_by(EmployeeAbsence.start_date, EmployeeAbsence.id)):
        stand.abwesenheiten[(kategorie, art)] += 1
        if ist_widerspruch(kategorie, art):
            stand.widersprueche.append(Widerspruch("Abwesenheit", i, von, bis, kategorie, art))
    for i, kategorie, art, von, bis, status, vermerk in db.execute(select(
            EmployeeAbsenceRequest.id, EmployeeAbsenceRequest.absence_category, EmployeeAbsenceRequest.absence_type, EmployeeAbsenceRequest.start_date, EmployeeAbsenceRequest.end_date,
            EmployeeAbsenceRequest.status, EmployeeAbsenceRequest.review_notes).order_by(EmployeeAbsenceRequest.start_date, EmployeeAbsenceRequest.id)):
        stand.antraege[(kategorie, art)] += 1
        if (vermerk or "").startswith(MIGRATION_VERMERK):
            stand.aus_migration += 1
        if status == "pending" and ist_widerspruch(kategorie, art):
            stand.widersprueche.append(Widerspruch("Offener Antrag", i, von, bis, kategorie, art))
    return stand


def nur_lesende_sitzung(url: str) -> Session:
    """Eine eigene Sitzung, die nicht schreiben kann -- jede Verbindung schreibgeschützt, bevor die erste Anfrage läuft."""
    engine = create_engine(url, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _schreibschutz(dbapi_verbindung, _eintrag):
        cursor = dbapi_verbindung.cursor()
        if engine.dialect.name == "postgresql":
            cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            dbapi_verbindung.commit()  # psycopg beginnt mit dem SET eine Transaktion; der Schreibschutz gilt für jede folgende
        elif engine.dialect.name == "sqlite":
            cursor.execute("PRAGMA query_only = ON")
        else:
            raise RuntimeError(f"Datenbank {engine.dialect.name} unbekannt -- kein Schreibschutz, keine Prüfung.")
        cursor.close()

    return Session(bind=engine, autoflush=False)


def _tag(wert) -> str:
    return f"{wert:%d.%m.%Y}"


def _zeilen_je_paar(zaehler: Counter, kategorie_name) -> list[str]:
    return [f"  {kategorie_name(k)} × {a}: {n}" for (k, a), n in sorted(zaehler.items(), key=lambda x: (x[0][0] or "", x[0][1] or ""))]


def ausgeben(stand: Stand, ausgabe=print) -> None:
    from app.absence_requests import ABSENCE_CATEGORY_LABELS

    name = lambda k: ABSENCE_CATEGORY_LABELS.get(k, k)  # noqa: E731
    ausgabe(f"Abwesenheiten: {sum(stand.abwesenheiten.values())}")
    for zeile in _zeilen_je_paar(stand.abwesenheiten, name):
        ausgabe(zeile)
    ausgabe(f"Anträge: {sum(stand.antraege.values())}")
    for zeile in _zeilen_je_paar(stand.antraege, name):
        ausgabe(zeile)
    ausgabe(f"Anträge aus der Migration (vor 1.9.146 auf der Plantafel eingetragen): {stand.aus_migration}")
    if not stand.widersprueche:
        ausgabe("Keine Widersprüche.")
        return
    ausgabe(f"Widersprüche: {len(stand.widersprueche)}")
    for w in stand.widersprueche:
        ausgabe(f"  {w.was} {w.id}: {_tag(w.von)}–{_tag(w.bis)}, Kategorie {name(w.kategorie)}, Art {w.art}")


def main(argv=None, *, sitzung=None, umgebung=None, ausgabe=print) -> int:
    """sitzung/umgebung/ausgabe nur für Tests; im Betrieb die nur lesende Sitzung aus DATABASE_URL, os.environ, print."""
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
        stand = pruefen(sitzung)
    except SQLAlchemyError as fehler:
        ausgabe(f"Datenbank nicht lesbar: {type(fehler).__name__}")
        return 2
    finally:
        sitzung.rollback()
        if eigene:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    ausgeben(stand, ausgabe)
    return 1 if stand.widersprueche else 0


if __name__ == "__main__":
    sys.exit(main())
