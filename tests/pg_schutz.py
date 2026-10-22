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

Seit 1.8.108 (Testläufe parallel, tests/test_v413_testlauf_parallel.py): jedes Schema pgtest_*, das ein Testprozess anlegt, trägt
als Kommentar die Kennung dieses Prozesses (Rechner, PID, Startzeit -- schema_waechter_einrichten() hängt sie an jedes CREATE SCHEMA
an, in derselben Transaktion). Zu Beginn eines Testlaufs löscht liegen_gebliebene_schemas_loeschen() (aus tests/conftest.py, nur im
Hauptprozess) jedes pgtest_*-Schema, dessen Prozess nicht mehr läuft -- nie eines eines laufenden Prozesses, nie eines ohne Kennung
(von einem Stand vor 1.8.108 oder nicht aus einem Testlauf; es wird nur genannt), nie public oder ein anderes Schema.

Seit 1.9.31: ERP_TEST_RECHNER ersetzt den Rechnernamen in der Kennung (nur Tests). Ein Test, der ein liegen gebliebenes Schema
nachstellt, gibt ihm einen eigenen Rechnernamen: für jeden anderen Testlauf ist es ein Schema eines anderen Rechners und bleibt stehen,
nur ein Lauf mit demselben Namen räumt es auf (bis dahin konnte ein gleichzeitig startender Lauf es vorher löschen, Runde 9).
"""

import os
import re
import socket
from pathlib import Path
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
    if not event.contains(Engine, "after_cursor_execute", _schema_kennzeichnen):
        event.listen(Engine, "after_cursor_execute", _schema_kennzeichnen)


def waechter_aktiv() -> bool:
    return event.contains(Pool, "connect", _schema_merken) and event.contains(Engine, "before_cursor_execute",
                                                                             _anweisung_pruefen) \
        and event.contains(Engine, "after_cursor_execute", _schema_kennzeichnen)


# ---------------------------------------------------------------------------------------------------------------------------
# Kennung des Testprozesses an jedem Testschema, Aufräumen liegen gebliebener Schemas (seit 1.8.108)
# ---------------------------------------------------------------------------------------------------------------------------

SCHEMA_PRAEFIX = "pgtest_"
_KENNUNG = re.compile(r"^erp-pytest host=(?P<host>[A-Za-z0-9._-]+) pid=(?P<pid>\d+) start=(?P<start>\d+)$")
_CREATE_SCHEMA = re.compile(r'^\s*CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>"pgtest_[A-Za-z0-9_]+"|pgtest_[A-Za-z0-9_]+)\s*;?\s*$',
                            re.IGNORECASE)


def prozess_start(pid: int) -> int | None:
    """Startzeit des Prozesses pid (Windows: FILETIME der Erzeugung, sonst Startzeit aus /proc), None, wenn er nicht läuft. Mit der
    PID zusammen eindeutig: eine später neu vergebene PID hat eine andere Startzeit. Ein Prozess, den dieser Benutzer nicht öffnen
    darf, gilt als nicht laufend -- ein Testprozess läuft immer unter demselben Benutzer, die PID gehört dann einem anderen."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
                return None
            zeiten = [wintypes.FILETIME() for _ in range(4)]
            if not kernel32.GetProcessTimes(handle, *(ctypes.byref(z) for z in zeiten)):
                return None
            return (zeiten[0].dwHighDateTime << 32) | zeiten[0].dwLowDateTime
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return None
    try:  # Feld 22 (starttime); der Name in Feld 2 kann Leerzeichen und Klammern enthalten
        return int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        return 0


def _rechner() -> str:
    """Name dieses Rechners in der Kennung -- seit 1.9.31 ersetzt ERP_TEST_RECHNER ihn (siehe Kopf)."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", os.environ.get("ERP_TEST_RECHNER") or socket.gethostname()) or "unbekannt"


def lauf_kennung(pid: int | None = None) -> str:
    """Kennung eines laufenden Testprozesses, wie sie am Schema steht: "erp-pytest host=<rechner> pid=<pid> start=<startzeit>"."""
    pid = os.getpid() if pid is None else pid
    start = prozess_start(pid)
    if start is None:
        raise ValueError(f"Prozess {pid} läuft nicht")
    return f"erp-pytest host={_rechner()} pid={pid} start={start}"


def lauf_laeuft(kennung: str | None) -> bool | None:
    """True: der Prozess der Kennung läuft noch. False: er läuft nicht mehr (auf diesem Rechner beendet oder die PID gehört einem
    anderen Prozess). None: nicht zu entscheiden -- keine oder keine lesbare Kennung, oder ein anderer Rechner."""
    m = _KENNUNG.match(kennung or "")
    if not m or m["host"] != _rechner():
        return None
    return prozess_start(int(m["pid"])) == int(m["start"])


def _schema_kennzeichnen(conn, cursor, statement, parameters, context, executemany):
    """Nach jedem CREATE SCHEMA pgtest_… dieses Testprozesses: die Kennung als Kommentar, auf demselben Cursor und damit in
    derselben Transaktion -- ein angelegtes Schema hat sie immer. Die Kennung besteht nur aus [A-Za-z0-9._= -]."""
    if conn.dialect.name != "postgresql":
        return
    m = _CREATE_SCHEMA.match(statement or "")
    if m:
        cursor.execute(f"COMMENT ON SCHEMA {m['name']} IS '{lauf_kennung()}'")


def liegen_gebliebene_schemas_loeschen(url: str) -> dict[str, list[str]]:
    """Zu Beginn eines Testlaufs (tests/conftest.py): löscht in der Datenbank von url jedes Schema pgtest_*, dessen Kennung einen
    Prozess nennt, der nicht mehr läuft -- je Schema in eigener Transaktion (alle zusammen bräuchten mehr Sperren, als die Instanz
    hat). Stehen bleiben die Schemas laufender Prozesse ("laufend"), ohne Kennung ("ohne_kennung") und anderer Rechner
    ("fremder_rechner"). Liest und löscht über eine Verbindung mit search_path pg_catalog (nicht public, Regel 27).

    Rückgabe: {"geloescht", "laufend", "ohne_kennung", "fremder_rechner", "fehler"} -> Schemanamen (bei "fehler" mit Grund)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    ergebnis: dict[str, list[str]] = {"geloescht": [], "laufend": [], "ohne_kennung": [], "fremder_rechner": [], "fehler": []}
    engine = create_engine(url, poolclass=NullPool, connect_args={
        "options": "-csearch_path=pg_catalog", "application_name": "pgtest-aufraeumen", "connect_timeout": 5})
    try:
        with engine.connect() as conn:
            zeilen = conn.execute(text(
                "SELECT nspname, obj_description(oid, 'pg_namespace') FROM pg_namespace "
                "WHERE nspname LIKE 'pgtest\\_%' ORDER BY nspname")).all()
        for name, kommentar in zeilen:
            if not name.startswith(SCHEMA_PRAEFIX) or not re.fullmatch(r"[a-z0-9_]+", name):
                continue  # nur, was der Test selbst so anlegt -- nie public, nie ein anderes Schema
            laeuft = lauf_laeuft(kommentar)
            if laeuft is None:
                ergebnis["ohne_kennung" if not _KENNUNG.match(kommentar or "") else "fremder_rechner"].append(name)
                continue
            if laeuft:
                ergebnis["laufend"].append(name)
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text("SET LOCAL lock_timeout = '10s'"))
                    conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                      "WHERE application_name = :n AND pid <> pg_backend_pid()"), {"n": name})
                    conn.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
                ergebnis["geloescht"].append(name)
            except Exception as exc:  # z. B. Sperre nicht bekommen -- nächster Lauf versucht es wieder
                ergebnis["fehler"].append(f"{name} ({type(exc).__name__})")
    finally:
        engine.dispose()
    return ergebnis


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
