"""Ersteinrichtung: legt das erste Administrator-Konto an -- nur so, nie über die Oberfläche (seit 1.8.130).

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung:

    set -a; source .env; set +a
    .venv/bin/python scripts/erstes_konto.py <benutzername> [--anzeigename "Vorname Nachname"]

Das Passwort fragt das Skript verdeckt ab (zweimal), nie als Argument -- ein Argument stünde in der Prozessliste und im
Verlauf der Shell. Ohne Terminal bricht es ab, statt das Passwort sichtbar zu lesen.

Solange es kein Konto gibt, hält die Anmeldeschranke die App geschlossen (app/anmeldeschranke.py::ersteinrichtung_antwort():
durch kommen nur /health und die Design-Dateien, Seiten zeigen diesen Befehl, alles andere bekommt 503). Gibt es schon ein
Konto, legt das Skript nichts an -- weitere Konten legt ein Administrator unter /users an. Beim ersten Anmelden richtet das
neue Konto den zweiten Faktor ein (Pflicht für Administratoren).

DATABASE_URL muss gesetzt sein, wie bei alembic (CLAUDE.md, "Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41", Vorfall 1):
ohne sie fiele app/database.py still auf eine SQLite-Datei zurück, das Konto entstünde in der falschen Datenbank und die
App bliebe geschlossen.

Rückgabe: 0 angelegt, 1 nichts angelegt (Konto vorhanden, Eingaben verschieden oder ungültig), 2 Umgebung fehlt (DATABASE_URL,
Terminal, Datenbank nicht lesbar).
"""

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

# app.* erst in main(), nach der Prüfung von DATABASE_URL: app.database baut seine Engine beim ersten Import aus der Umgebung
# (fehlt sie, still SQLite; ist sie leer, bricht der Import ab, bevor das Skript etwas Verständliches sagen kann).

logger = logging.getLogger("scripts.erstes_konto")

FELDNAMEN = {"username": "Benutzername", "password": "Passwort", "display_name": "Anzeigename"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("benutzername", help="Benutzername des ersten Administrator-Kontos (3 bis 80 Zeichen)")
    parser.add_argument("--anzeigename", help="Angezeigter Name (Vorgabe: der Benutzername)")
    return parser


def _fehlertext(fehler: ValidationError) -> str:
    """Nur Feld und Regel, nie der eingegebene Wert -- in einer Meldung zum Passwort stünde sonst das Passwort."""
    teile = []
    for e in fehler.errors():
        feld = FELDNAMEN.get(str(e["loc"][0]) if e.get("loc") else "", "Eingabe")
        ctx = e.get("ctx") or {}
        if e["type"] == "string_too_short":
            teile.append(f"{feld}: mindestens {ctx.get('min_length')} Zeichen")
        elif e["type"] == "string_too_long":
            teile.append(f"{feld}: höchstens {ctx.get('max_length')} Zeichen")
        else:
            teile.append(f"{feld}: ungültig")
    return "; ".join(teile)


def _sitzung():
    from app.database import SessionLocal
    return SessionLocal()


def _sperren(db) -> None:
    """Unter PostgreSQL bis zum Commit keine zweite Anlage daneben (zwei gleichzeitige Aufrufe ergäben sonst zwei Konten);
    Lesen bleibt frei. Unter SQLite (nur lokal) ohne Sperre."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("LOCK TABLE app_users IN SHARE ROW EXCLUSIVE MODE"))


def main(argv=None, *, eingabe=None, sitzung=None, umgebung=None, ausgabe=print) -> int:
    """eingabe/sitzung/umgebung/ausgabe nur für Tests; im Betrieb getpass, eigene Sitzung, os.environ, print."""
    args = _parser().parse_args(argv)
    umgebung = os.environ if umgebung is None else umgebung
    if sitzung is None and not umgebung.get("DATABASE_URL"):
        ausgabe("DATABASE_URL ist nicht gesetzt -- nichts angelegt. Zuerst die Umgebung laden: set -a; source .env; set +a")
        return 2
    if eingabe is None:
        if not sys.stdin.isatty():
            ausgabe("Kein Terminal -- das Passwort lässt sich nur im Terminal verdeckt eingeben. Nichts angelegt.")
            return 2
        eingabe = getpass.getpass

    from app.auth import hash_password, users_exist
    from app.models import AppUser
    from app.schemas import AppUserCreate

    benutzername = args.benutzername.strip()
    anzeigename = (args.anzeigename if args.anzeigename is not None else benutzername).strip()
    if sitzung is None:
        from app.logging_config import configure_logging
        configure_logging()
    db = sitzung if sitzung is not None else _sitzung()
    try:
        try:
            vorhanden = users_exist(db)
        except SQLAlchemyError as fehler:
            ausgabe(f"Die Datenbank ist nicht lesbar ({type(fehler).__name__}) -- nichts angelegt. "
                    "Stimmt DATABASE_URL, und sind die Migrationen eingespielt?")
            return 2
        if vorhanden:
            ausgabe("Es gibt schon ein ERP-Konto -- nichts angelegt. Weitere Konten legt ein Administrator unter /users an.")
            return 1

        passwort = eingabe("Passwort (mindestens 8 Zeichen): ")
        wiederholung = eingabe("Passwort wiederholen: ")
        if passwort != wiederholung:
            ausgabe("Die beiden Eingaben stimmen nicht überein -- nichts angelegt.")
            return 1
        try:
            daten = AppUserCreate(username=benutzername, password=passwort, display_name=anzeigename, role="admin")
        except ValidationError as fehler:
            ausgabe(f"Ungültige Eingabe -- nichts angelegt. {_fehlertext(fehler)}")
            return 1

        _sperren(db)
        if users_exist(db):
            db.rollback()
            ausgabe("Es gibt inzwischen ein ERP-Konto -- nichts angelegt.")
            return 1
        user = AppUser(username=daten.username.strip(), password_hash=hash_password(daten.password),
                       display_name=daten.display_name.strip(), role="admin", active=True)
        db.add(user)
        db.commit()
        logger.warning("Erstes Administrator-Konto per Befehl angelegt: '%s' (id=%s).", user.username, user.id)
        ausgabe(f"Administrator-Konto '{user.username}' angelegt. Beim ersten Anmelden richtet es den zweiten Faktor ein.")
        return 0
    finally:
        if sitzung is None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
