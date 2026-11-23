"""Zugriff des Portal-Dienstes auf die Datenbank (seit 1.11.2) -- eine eigene Engine mit der Rolle des Portals, nie app.database.

Lesen nur über die Core-Tabellen aus tabellen.py, alles an Link und Sitzung nur über die Funktionen der Datenbank (ab 1.11.3, aufrufen()). Jede Anfrage
holt sich eine Verbindung für genau einen Aufruf und gibt sie sofort zurück -- keine Sitzung über die Anfrage hinweg. Der Pool passt zum einen
Arbeitsprozess mit 10 Fäden (Bauplan P1, 1.4): 3 + 3 Verbindungen, 10 Sekunden warten, dann 503 („ausgelastet“); die Rolle selbst erlaubt höchstens 10.
"""

from __future__ import annotations

from sqlalchemy import create_engine, func, select

from .tabellen import alembic_version, general_settings

POOL_GROESSE, POOL_UEBERLAUF, POOL_WARTEN = 3, 3, 10


def engine_erzeugen(url: str):
    return create_engine(url, pool_size=POOL_GROESSE, max_overflow=POOL_UEBERLAUF, pool_timeout=POOL_WARTEN, pool_pre_ping=True)


class Datenbank:
    def __init__(self, engine):
        self.engine = engine

    def erreichbar(self) -> bool:
        with self.engine.connect() as c:
            return c.execute(select(1)).scalar() == 1

    def kontakt(self) -> dict | None:
        """Die Firmendaten aus den Einstellungen (Zeile 1) -- öffentliche Angaben für „Willkommen“ und die Fehlerseite (P1-14)."""
        with self.engine.connect() as c:
            zeile = c.execute(select(general_settings).where(general_settings.c.id == 1)).mappings().first()
        return dict(zeile) if zeile else None

    def revision(self) -> str | None:
        with self.engine.connect() as c:
            return c.execute(select(alembic_version.c.version_num)).scalar()

    def benutzer(self) -> str:
        with self.engine.connect() as c:
            return c.execute(select(func.current_user())).scalar()
