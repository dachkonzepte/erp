"""Prüfung: passt der gespeicherte Projektstatus zum abgeleiteten? (seit 1.9.125, Stufe 5, R2, Punkt 1)

Bis 1.9.124 setzte man den Status eines Projekts von Hand (Projektmappe, „Neues Projekt“), dazu automatisch beim Anlegen („anfrage“), bei der
Umwandlung einer Anfrage („angebot“) und bei jeder Beauftragung („beauftragt“, auch aus „abgeschlossen“). Seit 1.9.125 ergibt er sich aus den Daten
(app/akte.py::projekt_status_alle(): Anfrage, Angebot, Phase des Auftrags, Abgeschlossen, Storniert); die Spalte projects.status liest niemand mehr. Das
Skript nennt jedes Projekt, dessen gespeicherter Wert nicht zur Ableitung passt -- etwa „beauftragt“ ohne Auftrag.

Passend gilt (gespeichert -> abgeleitet): anfrage -> Anfrage; angebot -> Angebot; planung -> Angebot oder Auftrag; beauftragt -> Auftrag,
Ausführung, Abnahme oder Schlussrechnung; ausfuehrung -> Ausführung oder Abnahme; abgeschlossen -> Schlussrechnung, Abgeschlossen oder
Storniert. Jeder andere gespeicherte Wert passt nie.

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung und dem Python des Servers:

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/pruefe_projektstatus.py

Nur lesen wie scripts/pruefe_stornos.py (schreibgeschützte Sitzung, am Ende zurückgerollt). Mustervorgänge zählen nicht (sie haben keinen
Status im Ablauf). Ausgabe: je Treffer Projektnummer, Bezeichnung, gespeichert, abgeleitet und was am Projekt hängt; ohne Treffer „Alle n Projekte
passen.“ Rückgabe: 0 ohne Treffer, 1 mit Treffer, 2 Umgebung fehlt.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from pruefe_stornos import nur_lesende_sitzung  # noqa: E402

PASST = {
    "anfrage": {"anfrage"},
    "angebot": {"angebot"},
    "planung": {"angebot", "auftrag"},
    "beauftragt": {"auftrag", "ausfuehrung", "abnahme", "schlussrechnung"},
    "ausfuehrung": {"ausfuehrung", "abnahme"},
    "abgeschlossen": {"schlussrechnung", "abgeschlossen", "storniert"},
}


def pruefen(db) -> tuple[int, list[str]]:
    from app.akte import PROJEKTSTATUS_NAMEN, projekt_status_alle  # lokal: erst nach der Prüfung von DATABASE_URL (siehe pruefe_stornos.py)
    from app.models import Order, Project, Quote

    projekte = list(db.scalars(select(Project).where(Project.is_template.is_(False)).order_by(Project.project_number)))
    abgeleitet = projekt_status_alle(db, [p.id for p in projekte])
    angebote = dict(db.execute(select(Quote.project_id, func.count()).group_by(Quote.project_id)).all())
    auftraege = dict(db.execute(select(Order.project_id, func.count()).group_by(Order.project_id)).all())
    treffer = []
    for p in projekte:
        gespeichert = (p.status or "").strip().lower()
        neu = abgeleitet[p.id]
        if neu in PASST.get(gespeichert, set()):
            continue
        anhang = f"{angebote.get(p.id, 0)} Angebot(e), {auftraege.get(p.id, 0)} Auftrag/Aufträge" + (", archiviert" if p.archived else "")
        treffer.append(f"{p.project_number} {p.name}: gespeichert „{p.status}“, abgeleitet „{PROJEKTSTATUS_NAMEN.get(neu, neu)}“ ({anhang})")
    return len(projekte), treffer


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
        anzahl, treffer = pruefen(sitzung)
    except SQLAlchemyError as fehler:
        ausgabe(f"Datenbank nicht lesbar: {type(fehler).__name__}")
        return 2
    finally:
        sitzung.rollback()
        if eigene:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    if not treffer:
        ausgabe(f"Alle {anzahl} Projekte passen." if anzahl else "Kein Projekt -- nichts zu prüfen.")
        return 0
    ausgabe(f"{len(treffer)} von {anzahl} Projekten passen nicht zur Ableitung:")
    for zeile in treffer:
        ausgabe("  " + zeile)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
