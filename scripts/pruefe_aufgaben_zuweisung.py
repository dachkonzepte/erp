"""Prüfung: welche Aufgaben sind jemandem zugewiesen, der sie nicht sieht? (seit 1.9.369, F2 c aus dem Bericht 1.9.364; seit 1.9.371 auch ohne Mindestrolle)

Seit 1.9.369 lehnt die Zuweisung von Hand eine solche Person ab (422), ein Modul legt die Aufgabe dann empfängerlos in den Büro-Eingang; seit 1.9.371 auch
bei einer Aufgabe ohne Mindestrolle (Aufgaben sieht nur das Büro -- ein Monteur oder eine Person ohne Konto sähe sie nie). Was vorher so
zugewiesen wurde, bleibt, wie es ist (Vorgabe Tobias 18.11.2026: nur zählen und berichten, nichts ändern). Das Skript zählt diese Aufgaben -- nach derselben
Regel wie die Prüfung beim Zuweisen (app/tasks.py::zuweisung_grund(): kein aktives Konto der Person sähe die Aufgabe).

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung und dem Python des Servers:

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/pruefe_aufgaben_zuweisung.py

Nur lesen wie scripts/pruefe_stornos.py (schreibgeschützte Sitzung, am Ende zurückgerollt). Ausgabe ohne Namen und Titel: die Zahl, je Mindestrolle die Zahl,
je Treffer die Nummer der Aufgabe, ihre Mindestrolle, ob archiviert, und was die Person hat („kein Konto“ bzw. die Rollen ihrer aktiven Konten). Rückgabe: 0
ohne Treffer, 1 mit Treffer, 2 Umgebung fehlt.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from pruefe_stornos import nur_lesende_sitzung  # noqa: E402


KEINE = "keine"  # seit 1.9.371: eine Aufgabe ohne Mindestrolle


def pruefen(db) -> tuple[int, list[tuple[int, str, bool, str]]]:
    """(Zahl der zugewiesenen Aufgaben, Treffer als (Nummer, Mindestrolle oder „keine“, archiviert, was die Person hat)). Seit 1.9.371 jede zugewiesene
    Aufgabe, auch ohne Mindestrolle (bis 1.9.370 nur mit)."""
    from app.models import AppUser, Task  # lokal: erst nach der Prüfung von DATABASE_URL (siehe pruefe_stornos.py)
    from app.permissions import ROLE_LABELS
    from app.tasks import zuweisung_grund
    aufgaben = list(db.scalars(select(Task).where(Task.assigned_employee_id.is_not(None)).order_by(Task.id)))
    treffer = []
    for t in aufgaben:
        if zuweisung_grund(db, t.assigned_employee_id, t.min_visible_role) is None:
            continue
        rollen = sorted({ROLE_LABELS.get(k.role, k.role) for k in db.scalars(select(AppUser).where(
            AppUser.employee_id == t.assigned_employee_id, AppUser.active.is_(True)).order_by(AppUser.id))})
        rolle = KEINE if t.min_visible_role is None else ROLE_LABELS.get(t.min_visible_role, t.min_visible_role)
        treffer.append((t.id, rolle, bool(t.archived), ", ".join(rollen) or "kein Konto"))
    return len(aufgaben), treffer


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
        ausgabe(f"Alle {anzahl} zugewiesenen Aufgaben sieht ihre Person." if anzahl else "Keine zugewiesene Aufgabe -- nichts zu prüfen.")
        return 0
    ausgabe(f"{len(treffer)} von {anzahl} zugewiesenen Aufgaben sieht ihre Person nicht:")
    je_rolle = {}
    for _, rolle, _, _ in treffer:
        je_rolle[rolle] = je_rolle.get(rolle, 0) + 1
    for rolle, zahl in sorted(je_rolle.items()):
        ausgabe(f"  Mindestrolle {rolle}: {zahl}")
    for nummer, rolle, archiviert, hat in treffer:
        ausgabe(f"  Aufgabe Nr. {nummer}: Mindestrolle {rolle}, Person: {hat}" + (" (archiviert)" if archiviert else ""))
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
