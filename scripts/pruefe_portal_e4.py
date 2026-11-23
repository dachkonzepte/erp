"""Nachweis E4 für das Kundenportal (seit 1.11.3, Server-Schritt S8 im Bauplan P1): sieht das Portal die Adresse des Geräts oder die von nginx?

Das Portal zählt jedes Öffnen eines Links je Anschluss (portal_bremsen, Schlüssel „link:a:<Prüfwert des Anschlusses>“, F14). Sieht es statt des Geräts
die Adresse von nginx (127.0.0.1 -- X-Forwarded-For nicht weitergereicht oder nicht ausgewertet), haben alle Aufrufe denselben Anschluss. Vorgehen (S8):
von zwei Anschlüssen (Handy im Mobilnetz, Büro) je zweimal einen erfundenen Link öffnen, dann dieses Skript: es zählt die Anschlüsse im laufenden und im
vorigen Stundenfenster. Erwartet: 2. Steht dort 1, wertet das Portal X-Forwarded-For nicht aus -- nginx (proxy_set_header) und gunicorn
(--forwarded-allow-ips, Vorgabe 127.0.0.1) prüfen.

Läuft als Benutzer des ERP (seit dem Nachtrag N1 liest der Benutzer des Portals keine Tabelle):

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/pruefe_portal_e4.py

Nur lesen wie scripts/pruefe_stornos.py (schreibgeschützte Sitzung, am Ende zurückgerollt). Die Ausgabe nennt nur Zahlen -- nie eine Adresse, nie einen
Prüfwert. Rückgabe: 0 bei mindestens zwei Anschlüssen, 1 sonst, 2 Umgebung fehlt oder Datenbank nicht lesbar.
"""

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from pruefe_stornos import nur_lesende_sitzung  # noqa: E402

PRAEFIX = "link:a:"


def fenster_seit(jetzt):
    """Beginn des vorigen Stundenfensters (die Bremse zählt in vollen Stunden, UTC) -- naiv UTC wie fenster_beginn."""
    return jetzt.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


def zaehlen(db, seit) -> tuple[int, int]:
    """(Zahl der Anschlüsse, Zahl der Aufrufe) mit „Link geöffnet“ seit dem Zeitpunkt."""
    from app.models import PortalBremse  # lokal: erst nach der Prüfung von DATABASE_URL (siehe pruefe_stornos.py)
    from app.suchmuster import ESCAPE, beginnt_mit
    bedingung = (PortalBremse.schluessel.like(beginnt_mit(PRAEFIX), escape=ESCAPE), PortalBremse.fenster_beginn >= seit)
    anschluesse = db.scalar(select(func.count(func.distinct(PortalBremse.schluessel))).where(*bedingung))
    aufrufe = db.scalar(select(func.coalesce(func.sum(PortalBremse.zaehler), 0)).where(*bedingung))
    return int(anschluesse or 0), int(aufrufe or 0)


def main(argv=None, *, sitzung=None, umgebung=None, ausgabe=print, jetzt=None) -> int:
    """sitzung/umgebung/ausgabe/jetzt nur für Tests; im Betrieb die nur lesende Sitzung aus DATABASE_URL, os.environ, print, die Uhr (UTC)."""
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)
    umgebung = os.environ if umgebung is None else umgebung
    eigene = sitzung is None
    if eigene:
        url = (umgebung.get("DATABASE_URL") or "").strip()
        if not url:
            ausgabe("DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a")
            return 2
        sitzung = nur_lesende_sitzung(url)
    if jetzt is None:
        from app.berlin_time import utc_jetzt
        jetzt = utc_jetzt()
    seit = fenster_seit(jetzt)
    try:
        anschluesse, aufrufe = zaehlen(sitzung, seit)
    except SQLAlchemyError as fehler:
        ausgabe(f"Datenbank nicht lesbar: {type(fehler).__name__}")
        return 2
    finally:
        sitzung.rollback()
        if eigene:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    ausgabe(f"Link geöffnet seit {seit:%H:%M} Uhr (UTC): {anschluesse} Anschlüsse, {aufrufe} Aufrufe.")
    if anschluesse >= 2:
        ausgabe("Erwartet nach dem Nachweis mit zwei Geräten: 2 -- das Portal unterscheidet die Anschlüsse.")
        return 0
    if anschluesse == 0:
        ausgabe("Noch kein Aufruf -- erst von zwei Anschlüssen (Handy im Mobilnetz, Büro) je zweimal einen erfundenen Link öffnen.")
    else:
        ausgabe("Nur ein Anschluss: kamen beide Geräte an? Wenn ja, sieht das Portal die Adresse von nginx -- X-Forwarded-For in nginx und "
                "--forwarded-allow-ips in gunicorn prüfen.")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
