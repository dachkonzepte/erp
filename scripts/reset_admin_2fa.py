"""Notfall: setzt den zweiten Faktor (TOTP) eines Administrator-Kontos vollständig zurück.

Aufruf direkt auf dem Server, im Projektverzeichnis, mit aktivierter virtueller Umgebung:

    python scripts/reset_admin_2fa.py <benutzername>

Nutzt dieselbe Datenbank wie die Anwendung selbst (DATABASE_URL/ERP_DATA_DIR aus der Umgebung,
genau wie beim normalen Start) -- kein zusätzlicher Konfigurationsweg. Fragt vor dem
Zurücksetzen nach Bestätigung (Tippen des Benutzernamens); mit --yes läuft es ohne Rückfrage
(z. B. für ein automatisiertes Notfall-Runbook).

Wann benutzen: wenn ein Administrator sowohl das Smartphone mit der Authenticator-App als auch
alle ausgedruckten Wiederherstellungscodes verloren hat -- der einzige verbleibende Weg, siehe
CLAUDE.md "Zwei-Faktor-Authentifizierung für Administratoren". Ist noch ein ANDERER aktiver
Administrator vorhanden, kann dieser den zweiten Faktor stattdessen direkt in der
Benutzerverwaltung (/users, "Zweiten Faktor zurücksetzen") zurücksetzen -- ohne Server-Zugriff.

Danach: der Benutzer wird beim nächsten Login zur vollständigen Neueinrichtung des zweiten
Faktors aufgefordert (QR-Code, Bestätigungscode, neue Wiederherstellungscodes) -- genau wie bei
der allerersten Einrichtung.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import two_factor  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.models import AppUser  # noqa: E402

logger = logging.getLogger("scripts.reset_admin_2fa")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("username", help="Benutzername des Kontos, dessen zweiter Faktor zurückgesetzt werden soll")
    parser.add_argument("--yes", action="store_true", help="Ohne Rückfrage ausführen")
    args = parser.parse_args()

    configure_logging()
    db = SessionLocal()
    try:
        user = db.scalar(select(AppUser).where(AppUser.username == args.username.strip()))
        if user is None:
            print(f"Kein ERP-Benutzer mit dem Benutzernamen '{args.username}' gefunden.")
            return 1

        print(f"Benutzer: {user.display_name} ({user.username}), Rolle: {user.role}")
        print(f"Zweiter Faktor aktuell eingerichtet: {'ja' if two_factor.is_configured(user) else 'nein'}")
        if two_factor.is_configured(user):
            print(f"Verbleibende Wiederherstellungscodes: {two_factor.remaining_recovery_codes(db, user)}")

        if not args.yes:
            confirm = input(f"\nZum Bestätigen den Benutzernamen '{user.username}' erneut eintippen: ")
            if confirm.strip() != user.username:
                print("Abgebrochen -- Eingabe stimmt nicht mit dem Benutzernamen überein.")
                return 1

        two_factor.reset(db, user)
        logger.warning(
            "Zweiter Faktor per Notfallskript zurückgesetzt für Benutzer '%s' (id=%s).", user.username, user.id,
        )
        print(f"\nZweiter Faktor für '{user.username}' zurückgesetzt. Der Benutzer wird beim nächsten "
              f"Login zur vollständigen Neueinrichtung aufgefordert.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
