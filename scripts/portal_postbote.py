"""Der Postbote des Kundenportals (seit 1.11.6, Stufe P1c; app/portal_postbote.py) -- als Dienst erp-portalpost (scripts/server/erp-portalpost.service).

Läuft dauerhaft unter dem Benutzer des ERP; die Einheit lädt vorher .env (DATABASE_URL, Zugang zu Microsoft 365 aus den Einstellungen):

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/portal_postbote.py

Ohne DATABASE_URL oder mit einer anderen Datenbank als PostgreSQL bricht das Skript ab (Rückgabe 2) -- app/database.py fiele sonst still auf SQLite
zurück (Vorfall 1), und LISTEN, SKIP LOCKED und die Funktionen des Portals gibt es nur unter PostgreSQL. Läuft schon ein Postbote: Rückgabe 3 (systemd
startet nach 5 Sekunden neu, Restart=always). Ein Fehler der Datenbank beendet die Schleife (Rückgabe 1) -- ebenso neu gestartet. Protokolliert nur
Nummern der Aufträge, Zähler und Namen von Ausnahmen -- nie einen Code, einen Link oder eine Adresse.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("scripts.portal_postbote")


def main(*, umgebung=os.environ, ausgabe=lambda s: print(s, file=sys.stderr)) -> int:
    url = umgebung.get("DATABASE_URL", "")
    if not url:
        ausgabe("DATABASE_URL fehlt -- .env laden (set -a; source .env; set +a). Der Postbote startet nicht.")
        return 2
    if not url.startswith("postgresql"):
        ausgabe("Der Postbote läuft nur mit PostgreSQL (LISTEN, SKIP LOCKED, Funktionen des Portals). Er startet nicht.")
        return 2
    from sqlalchemy import create_engine

    from app.logging_config import configure_logging
    from app.portal_postbote import AndererPostbote, laufen

    configure_logging()
    # genau die geprüfte Verbindung -- nicht app.database.engine (die läse DATABASE_URL noch einmal selbst); zwei Verbindungen reichen (LISTEN, Arbeit)
    engine = create_engine(url, future=True, pool_pre_ping=True, pool_size=2, max_overflow=1)
    try:
        laufen(engine)
    except AndererPostbote:
        logger.warning("Es läuft schon ein Postbote -- dieser startet nicht.")
        return 3
    except Exception as e:  # noqa: BLE001 -- nur der Name, nie der Text (er könnte Daten enthalten)
        logger.error("Postbote beendet (%s)", type(e).__name__)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
