"""Holt die Anfragen der Webseite in den Eingang des ERP (seit 1.10.0, Stufe W1a; docs/archiv/webseite-und-kundenportal.md).

Ein Lauf von app/webanfragen.py::abholen() -- derselbe wie der Knopf „Jetzt abholen“, nur mit mehr Anfragen je Lauf. Auf dem Server über den
systemd-Timer scripts/server/erp-webanfragen.timer (alle 5 Minuten); die Einheit lädt vorher .env (DATABASE_URL, DK_ANFRAGE_SCHLUESSEL …).

Ohne DATABASE_URL bricht das Skript ab (Rückgabe 2) -- app/database.py fiele sonst still auf eine SQLite-Datei zurück (Vorfall 1 in CLAUDE.md,
„Produktivbetrieb“). Rückgabe 0: gelaufen, nichts eingerichtet oder ein anderer Lauf belegt; 1: der Lauf endete mit einem Fehler (der feste Text steht
im Protokoll und auf der Seite). Protokolliert nur Zähler und feste Texte -- nie Inhalte, nie den Schlüssel.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("scripts.webanfragen_abholen")


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL fehlt -- .env laden (set -a; source .env; set +a). Nichts abgeholt.", file=sys.stderr)
        return 2
    from app.database import SessionLocal
    from app.logging_config import configure_logging
    from app.webanfragen import NICHT_EINGERICHTET, abholen

    configure_logging()
    db = SessionLocal()
    try:
        erg = abholen(db)
    finally:
        db.close()
    if erg.laeuft_schon:
        logger.info("Ein anderer Lauf holt gerade ab -- nichts zu tun.")
        return 0
    if erg.fehler == NICHT_EINGERICHTET:
        logger.info("Schnittstelle nicht eingerichtet (DK_ANFRAGE_SCHLUESSEL fehlt) -- nichts zu tun.")
        return 0
    return 1 if erg.fehler else 0


if __name__ == "__main__":
    sys.exit(main())
