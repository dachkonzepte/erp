"""Gleicht ALLE Postfächer mit hinterlegtem Outlook-Sync (AppUser.outlook_mailbox, aktive Konten)
gegen Microsoft Graph ab -- der ALLE-Postfächer-Gegenstück zu POST /api/calendar-events/sync-outlook
(das nur das eigene Postfach beim Öffnen von /kalender synchronisiert), siehe CLAUDE.md
"Kalender" -> "Stufe 2" Punkt 5.

Für den Produktivbetrieb per Cron einzurichten (Muster /home/tobias/backup.sh, siehe CLAUDE.md
"Produktivbetrieb") -- kein In-Process-Scheduler, dieses Projekt hat bewusst keinen (siehe
CLAUDE.md, mehrfach dokumentiert, u. a. bei den Wartungsverträgen). Ein Beispiel-Crontab-Eintrag
(alle 15 Minuten):

    */15 * * * * cd /home/tobias/erp && .venv/bin/python scripts/sync_outlook_calendars.py >> /home/tobias/erp-data/outlook_sync.log 2>&1

Nutzt dieselbe Datenbank wie die Anwendung selbst (DATABASE_URL aus der Umgebung, siehe
scripts/reset_admin_2fa.py für dasselbe Muster). Ein einzelnes fehlschlagendes Postfach bricht
den Lauf NICHT ab (sync_user_calendar() fängt das bereits selbst ab und speichert den Fehler in
OutlookCalendarSyncState) -- der Exit-Code ist 0, solange das Skript selbst durchläuft, auch wenn
einzelne Postfächer Fehler melden (diese stehen dann in den Protokollzeilen, siehe unten).

Protokolliert je Postfach ausschließlich Zähler (Muster app/outlook_calendar_sync.py Punkt 6) --
NIE einen Termintitel/-ort/-notiz, auch nicht bei einem Fehler (nur der Exception-Klassenname)."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.models import AppUser  # noqa: E402
from app.outlook_calendar_sync import is_outlook_sync_available, sync_user_calendar  # noqa: E402

logger = logging.getLogger("scripts.sync_outlook_calendars")


def main() -> int:
    configure_logging()
    db = SessionLocal()
    try:
        if not is_outlook_sync_available(db):
            logger.info("Outlook-Kalendersynchronisation ist deaktiviert oder nicht konfiguriert -- nichts zu tun.")
            return 0

        candidates = db.scalars(
            select(AppUser).where(AppUser.active == True, AppUser.outlook_mailbox.is_not(None))  # noqa: E712
        ).all()
        if not candidates:
            logger.info("Kein aktives Konto mit hinterlegtem Outlook-Postfach -- nichts zu tun.")
            return 0

        for user in candidates:
            result = sync_user_calendar(db, user)
            if result.get("skipped"):
                continue
            if result.get("error"):
                logger.warning("Postfach app_user_id=%s: Fehler (%s).", user.id, result.get("error_type"))
                continue
            logger.info(
                "Postfach app_user_id=%s: %s neu, %s geändert, %s gelöscht, %s Serientermine übersprungen, "
                "%s nach Outlook neu angelegt, %s nach Outlook aktualisiert.",
                user.id, result["created"], result["updated"], result["deleted"],
                result["skipped_recurring"], result["pushed_created"], result["pushed_updated"],
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
