"""Zugriff des Portal-Dienstes auf die Datenbank (seit 1.11.2) -- eine eigene Engine mit der Rolle des Portals, nie app.database.

Lesen nur über die Core-Tabellen aus tabellen.py, alles an Link und Sitzung nur über die Funktionen der Datenbank (seit 1.11.3, Nachtrag N1): an sie gehen
nur Prüfwerte (app/portal/pruefwerte.py), nie Link, Code oder Wert des Cookies. Jede Anfrage holt sich eine Verbindung für genau einen Aufruf und gibt sie
sofort zurück -- keine Sitzung über die Anfrage hinweg, keine Sitzungsvariablen. Schreibende Funktionen in einer Transaktion mit Commit (begin()), lesende
(STABLE) ohne Commit -- so schreibt kein GET. Der Pool passt zum einen Arbeitsprozess mit 10 Fäden (Bauplan P1, 1.4): 3 + 3 Verbindungen, 10 Sekunden
warten, dann 503 („ausgelastet“); die Rolle selbst erlaubt höchstens 10.
"""

from __future__ import annotations

from sqlalchemy import create_engine, func, select, text

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

    # --- Funktionen der Datenbank (app/portal/funktionen.py) ----------------------------------------------------------------------------------------

    def _schreibend(self, sql: str, **werte):
        with self.engine.begin() as c:
            return tuple(c.execute(text(sql), werte).one())

    def _lesend(self, sql: str, **werte):
        with self.engine.connect() as c:  # ohne Commit: am Ende zurückgerollt
            return c.execute(text(sql), werte).first()

    def link_oeffnen(self, link: str, anschluss: str, sitzung: str | None, neue_sitzung: str) -> tuple[str, str | None, int | None]:
        return self._schreibend("SELECT ergebnis, email_anzeige, minuten FROM portal_link_oeffnen(:l, :a, :s, :n)",
                                l=link, a=anschluss, s=sitzung, n=neue_sitzung)

    def code_anfordern(self, sitzung: str, anschluss: str) -> tuple[str, int | None]:
        return self._schreibend("SELECT ergebnis, minuten FROM portal_code_anfordern(:s, :a)", s=sitzung, a=anschluss)

    def post_stand(self, sitzung: str) -> str:
        return self._lesend("SELECT portal_post_stand(:s)", s=sitzung)[0]

    def code_pruefen(self, sitzung: str, pruefwert: str, neue_sitzung: str, anschluss: str) -> tuple[str, int | None]:
        return self._schreibend("SELECT ergebnis, zahl FROM portal_code_pruefen(:s, :p, :n, :a)", s=sitzung, p=pruefwert, n=neue_sitzung, a=anschluss)

    def sitzung_weiter(self, sitzung: str) -> str:
        return self._schreibend("SELECT portal_sitzung_weiter(:s)", s=sitzung)[0]

    def abmelden(self, sitzung: str, ueberall: bool) -> str:
        return self._schreibend("SELECT portal_abmelden(:s, :u)", s=sitzung, u=ueberall)[0]

    def willkommen(self, sitzung: str) -> dict | None:
        zeile = self._lesend("SELECT anrede, titel, vorname, nachname, name FROM portal_willkommen(:s)", s=sitzung)
        return dict(zeile._mapping) if zeile is not None else None
