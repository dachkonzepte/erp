"""Sortierung nach Namen wie im Telefonbuch (seit 1.9.353, F6, Runde V2b Punkt 1; Entscheidung Tobias 14.11.2026, Runde 17.11.2026).

Listen nach Namen sortieren ohne Groß- und Kleinschreibung, Umlaute beim Grundbuchstaben (Ä wie A, ß wie ss), Akzente ebenso (é wie e, ł wie l) --
unter SQLite und PostgreSQL gleich und unabhängig von der Kollation des Servers (live C.UTF-8, lokal German_Germany.1252). Bis 1.9.352 sortierte SQLite
binär (Großbuchstaben vor Kleinbuchstaben, Umlaute ans Ende), PostgreSQL nach seiner Kollation (Befund 13.11.2026, P4).

Der Weg: ein Sortierschlüssel je Name, gerechnet von einer Funktion `telefonbuch(text)` in der Datenbank --

    1. Leerzeichen am Anfang und Ende weg (nur das Leerzeichen, wie btrim(t, ' ')),
    2. Zeichen für Zeichen nach ZEICHEN: A–Z auf a–z, jeder Buchstabe mit Umlaut oder Akzent auf seinen Grundbuchstaben (klein),
    3. ERSETZEN: ß und ẞ zu ss, Æ/æ zu ae, Œ/œ zu oe,
    4. leer -> NULL (ein leerer Name sortiert wie kein Name: ans Ende, `nulls_last()`).

Kein lower()/upper() der Datenbank: unter PostgreSQL hängt es an der Zeichenklassifizierung (ctype) des Servers. Der Schlüssel selbst wird unter
PostgreSQL mit COLLATE "C" verglichen (byteweise, wie SQLite) -- sonst ordnete eine deutsche Kollation „a-c“ vor „ab“ (Bindestrich übergangen).

    SQLite      die Python-Funktion schluessel() an jeder Verbindung (Ereignis „connect“ an der Klasse Engine, wie das PRAGMA der Tests)
    PostgreSQL  eine SQL-Funktion aus derselben Tabelle: angelegt von der Migration 9e4b2c7d1a35 (Server) und nach jedem create_all()
                (Testschemas, lokale Entwicklung) -- pg_sql() ist der Text; die Migration trägt ihn wörtlich, tests/test_v753_telefonbuch.py
                vergleicht beide (eine geänderte Tabelle braucht eine neue Migration)

Im Code: `.order_by(*nach_namen(Customer.name), Customer.id)` statt `.order_by(Customer.name)`; in Python `sorted(…, key=lambda x:
sortierwert(x.name))` statt casefold()/lower(). Der Wächter tests/test_v753_telefonbuch.py findet jede Sortierung nach einer Namensspalte an
beidem vorbei.
"""

from __future__ import annotations

import sqlite3

from sqlalchemy import String, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

# Grundbuchstabe (klein) -> Zeichen, die darauf fallen. Nur Zeichen, die eins zu eins gehen; was zu zwei Buchstaben wird, steht in ERSETZEN.
GRUNDBUCHSTABEN = {
    "a": "AÀÁÂÃÄÅĀĂĄàáâãäåāăą",
    "b": "B", "c": "CÇĆČçćč", "d": "DĎĐďđ",
    "e": "EÈÉÊËĒĖĘĚèéêëēėęě",
    "f": "F", "g": "GĞĢğģ", "h": "H",
    "i": "IÌÍÎÏĪĮİìíîïīįı",
    "j": "J", "k": "KĶķ", "l": "LĹĻĽŁĺļľł", "m": "M",
    "n": "NÑŃŅŇñńņň",
    "o": "OÒÓÔÕÖØŌŐòóôõöøōő",
    "p": "P", "q": "Q", "r": "RŔŘŕř",
    "s": "SŚŞŠȘśşšș", "t": "TŢŤȚţťț",
    "u": "UÙÚÛÜŪŮŰŲùúûüūůűų",
    "v": "V", "w": "W", "x": "X", "y": "YÝŸýÿ", "z": "ZŹŻŽźżž",
}
VON = "".join(zeichen for _g, zeichen in GRUNDBUCHSTABEN.items())
NACH = "".join(g * len(zeichen) for g, zeichen in GRUNDBUCHSTABEN.items())
ERSETZEN = (("ß", "ss"), ("ẞ", "ss"), ("Æ", "ae"), ("æ", "ae"), ("Œ", "oe"), ("œ", "oe"))

assert len(VON) == len(NACH) and len(set(VON)) == len(VON), "jedes Zeichen genau einmal"
assert not set(VON) & {alt for alt, _neu in ERSETZEN}
assert all("'" not in s for s in (VON, NACH, *(a + n for a, n in ERSETZEN)))

_TABELLE = str.maketrans(VON, NACH)


def schluessel(text) -> str | None:
    """Der Sortierschlüssel eines Namens -- dieselbe Rechnung wie telefonbuch() in der Datenbank; None für keinen oder einen leeren Namen."""
    if text is None:
        return None
    s = str(text).strip(" ").translate(_TABELLE)
    for alt, neu in ERSETZEN:
        s = s.replace(alt, neu)
    return s or None


def listen_name(nachname, vorname) -> str:
    """Name einer Person in einer Liste, die nach Nachname, dann Vorname sortiert (seit 1.9.360, Kundenliste): „Nachname, Vorname“ -- ohne Anrede und
    Titel (die stehen in der Akte). Ohne Vorname nur der Nachname: eine Firma trägt ihren Namen im Nachnamen und steht unverändert da (auch mit der
    Anrede „Firma“ -- eine Anrede, die nur die Akte zeigt). So passen Anzeige und Sortierung (nach_namen(Nachname, Vorname)) zusammen."""
    teile = [str(t).strip() for t in (nachname, vorname) if t is not None and str(t).strip()]
    return ", ".join(teile)


def sortierwert(text) -> tuple[bool, str]:
    """Schlüssel für sorted()/sort() in Python: leer ans Ende, sonst nach schluessel() -- wie nach_namen() in der Datenbank."""
    k = schluessel(text)
    return (k is None, k or "")


def pg_sql() -> str:
    """Die Funktion für PostgreSQL. Die Migration 9e4b2c7d1a35 trägt diesen Text wörtlich."""
    ausdruck = f"translate(btrim(t, ' '), '{VON}', '{NACH}')"
    for alt, neu in ERSETZEN:
        ausdruck = f"replace({ausdruck}, '{alt}', '{neu}')"
    return ("CREATE OR REPLACE FUNCTION telefonbuch(t text) RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$ "
            f"SELECT NULLIF({ausdruck}, '') $$")


class telefonbuch(FunctionElement):  # noqa: N801 -- heißt wie die Funktion in der Datenbank
    """telefonbuch(spalte) -- der Sortierschlüssel in SQL; unter PostgreSQL mit COLLATE "C"."""
    name = "telefonbuch"
    type = String()
    inherit_cache = True


@compiles(telefonbuch)
def _telefonbuch(element, compiler, **kw):
    return f"telefonbuch({compiler.process(element.clauses, **kw)})"


@compiles(telefonbuch, "postgresql")
def _telefonbuch_pg(element, compiler, **kw):
    return f'telefonbuch({compiler.process(element.clauses, **kw)}) COLLATE "C"'


def nach_namen(*spalten) -> tuple:
    """Sortierung nach einer oder mehreren Namensspalten wie im Telefonbuch, leere Namen ans Ende: `.order_by(*nach_namen(a, b), X.id)`."""
    return tuple(telefonbuch(s).nulls_last() for s in spalten)


@event.listens_for(Engine, "connect")
def _sqlite_funktion(dbapi_connection, connection_record):
    """Jede SQLite-Verbindung kennt telefonbuch() -- an der Klasse Engine gilt das für jede Engine, auch eine schon angelegte."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("telefonbuch", 1, schluessel, deterministic=True)


def pg_anlegen(target, connection, **kw):
    """Nach jedem create_all() unter PostgreSQL (Testschemas, lokale Entwicklung) -- auf dem Server legt die Migration sie an."""
    if connection.dialect.name == "postgresql":
        connection.exec_driver_sql(pg_sql())
