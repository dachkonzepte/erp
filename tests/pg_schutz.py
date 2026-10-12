"""Kein Test gegen PostgreSQL läuft im Schema public der Spielwiese (seit 1.8.81, Vorgabe Z2b "Vorweg" 3, CLAUDE.md Regel 27).

Anlass: test_v297 (Outlook) lief bis 1.8.80 in public der lokalen Spielwiese; dort fehlte eine neue Spalte (create_all() zieht
bestehende Tabellen nicht nach), drei Tests wurden rot -- und jeder solche Lauf hinterlässt Tabellen und Zeilen in public.

Zwei Teile, beide von tests/test_v384_pg_nicht_public.py erzwungen:
- schema_waechter_einrichten() (in tests/conftest.py, für den ganzen Testprozess): jede neue PostgreSQL-Verbindung merkt sich ihr
  Schema (current_schema()); läuft auf einer Verbindung in public etwas anderes als Verwaltung (CREATE/DROP SCHEMA,
  pg_terminate_backend, die Anfragen des Treibers beim Verbinden), bricht der Test mit SchemaPublicVerboten ab.
- pg_url_pruefen(url): für Kindprozesse (alembic, ein Start von app.main), die der Wächter nicht sieht -- eine PostgreSQL-URL
  braucht ein eigenes search_path (Wegwerf-Schema), nicht public. Jede Funktion unter tests/, die DATABASE_URL an einen
  Kindprozess gibt, ruft sie auf.
"""

import re
from urllib.parse import parse_qs, unquote, urlsplit

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

# Was auf einer Verbindung in public erlaubt ist: Schemas anlegen und löschen, eigene Verbindungen beenden, und was der Treiber
# bzw. SQLAlchemy beim Verbinden selbst fragt.
VERWALTUNG = re.compile(
    r"^\s*(CREATE\s+SCHEMA\b|DROP\s+SCHEMA\b|SELECT\s+pg_terminate_backend\b|select\s+pg_catalog\.version\(\)"
    r"|select\s+current_schema\(\)|show\s+standard_conforming_strings|SELECT\s+1\s*$|BEGIN\b|COMMIT\b|ROLLBACK\b)",
    re.IGNORECASE)


class SchemaPublicVerboten(RuntimeError):
    """Ein Test führt gegen PostgreSQL etwas im Schema public aus -- verboten (Regel 27)."""


def _ist_psycopg(dbapi_connection) -> bool:
    return type(dbapi_connection).__module__.startswith("psycopg")


def _schema_merken(dbapi_connection, connection_record):
    if not _ist_psycopg(dbapi_connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("select current_schema()")
        row = cursor.fetchone()
        connection_record.info["erp_schema"] = row[0] if row else None
    finally:
        cursor.close()
    dbapi_connection.rollback()  # keine offene Transaktion zurücklassen (Isolationsstufe setzt SQLAlchemy danach)


def _anweisung_pruefen(conn, cursor, statement, parameters, context, executemany):
    if conn.dialect.name != "postgresql":
        return
    if conn.info.get("erp_schema") == "public" and not VERWALTUNG.match(statement or ""):
        kurz = " ".join(str(statement).split())[:160]
        raise SchemaPublicVerboten(
            "Test gegen PostgreSQL im Schema public der Spielwiese -- verboten (CLAUDE.md Regel 27). Ein Wegwerf-Schema nehmen "
            f"(connect_args options=-csearch_path=<schema>, tests/befund_vor_echtbetrieb.py::pg_sitzung()). Anweisung: {kurz}")


def schema_waechter_einrichten() -> None:
    """Für alle Engines des Testprozesses (Ereignisse an den Klassen Pool und Engine, auch für Engines von alembic im selben
    Prozess). Mehrfacher Aufruf schadet nicht."""
    if not event.contains(Pool, "connect", _schema_merken):
        event.listen(Pool, "connect", _schema_merken)
    if not event.contains(Engine, "before_cursor_execute", _anweisung_pruefen):
        event.listen(Engine, "before_cursor_execute", _anweisung_pruefen)


def waechter_aktiv() -> bool:
    return event.contains(Pool, "connect", _schema_merken) and event.contains(Engine, "before_cursor_execute",
                                                                             _anweisung_pruefen)


def pg_url_pruefen(url: str) -> str:
    """Eine URL für einen Kindprozess: SQLite unverändert; PostgreSQL nur mit eigenem search_path, nicht public -- sonst
    SchemaPublicVerboten. Gibt die URL zurück."""
    if not str(url).startswith("postgresql"):
        return url
    options = parse_qs(urlsplit(str(url)).query).get("options", [])
    paths = [m.group(1) for o in options for m in re.finditer(r"-csearch_path=([^\s&]+)", unquote(o))]
    if not paths or any(p.split(",")[0].strip('"').lower() in ("public", "$user") for p in paths):
        raise SchemaPublicVerboten("Kindprozess gegen PostgreSQL ohne eigenes Schema (search_path) -- verboten (CLAUDE.md Regel 27). "
                                   f"URL: {str(url).split('@')[-1]}")
    return url
