import os
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import telefonbuch  # seit 1.9.353: telefonbuch() an jeder SQLite-Verbindung (Ereignis „connect“ an der Klasse Engine)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dachkonzepte_erp.db")

# Seit 1.8.114 (Vorgabe vom 16.10.2026, Punkt 1d): der Verbindungspool unter PostgreSQL, passend zu Threadpool und Arbeitsprozessen.
#
# - Threadpool: jeder Arbeitsprozess führt synchrone Endpunkte, das Lesen der Anmeldeschranke und das Lesen von Dateien in Starlettes
#   Threadpool aus -- 40 Plätze (Vorgabe von anyio, THREADPOOL). Eine Anfrage hält höchstens eine Verbindung zugleich (seit 1.8.114:
#   die Schranke liest in einem eigenen Schritt, die Jinja-Globals lesen nichts mehr, get_db gibt die Verbindung vor dem Senden frei).
# - Poolgröße: POOL_SIZE + MAX_OVERFLOW = 40 = THREADPOOL. So wartet ein Thread im Normalbetrieb nie auf eine Verbindung, die ein
#   anderer Thread desselben Prozesses gerade nicht braucht. Dauerhaft offen bleiben nur POOL_SIZE = 5 je Prozess (die übrigen schließt
#   der Pool nach Gebrauch wieder) -- auf dem Server mit 4 GB zählt jede ruhende Verbindung (ein PostgreSQL-Prozess je Verbindung).
# - Arbeitsprozesse: 2 (gunicorn -w 2) × 40 = 80 Verbindungen höchstens, bei max_connections = 100 (Vorgabe von PostgreSQL, davon 3 für
#   den Superuser): bleiben 17 für Sicherung, update.sh mit der Probe gegen die Spielwiese, den Outlook-Abgleich per Cron und psql.
# - POOL_TIMEOUT = 10 s statt 30: wartet ein Thread länger auf eine Verbindung, ist der Prozess überlastet -- die Anfrage endet dann mit
#   503 und der Thread wird frei (app/anmeldeschranke.py), lange bevor der Baustein der Seite nach 60 s aufgibt und Nginx nach 60 s
#   abbricht. Eine Anfrage, die eine Verbindung hält, wartet nach dem Endpunkt noch auf einen Thread zum Serialisieren -- sind alle
#   Threads mit Warten auf Verbindungen belegt, löst erst dieses Zeitlimit den Stau.
# - pool_pre_ping: prüft eine Verbindung vor jeder Ausgabe (ein SELECT 1) -- nach einem Neustart von PostgreSQL oder einer beendeten
#   Verbindung bekommt die nächste Anfrage eine neue statt einen Fehler.
#
# Abweichende Werte über ERP_DB_POOL_SIZE, ERP_DB_MAX_OVERFLOW, ERP_DB_POOL_TIMEOUT (siehe .env.example; der Angriffstest unter Last nimmt
# einen kleinen Pool). Unter SQLite (lokaler Schnelleinstieg, Tests) bleibt der Pool von SQLAlchemy unverändert.
THREADPOOL = 40
POOL_SIZE = 5
MAX_OVERFLOW = 35
POOL_TIMEOUT = 10


def _zahl(name: str, vorgabe: int, minimum: int) -> int:
    wert = os.getenv(name)
    if wert is None or not wert.strip():
        return vorgabe
    try:
        zahl = int(wert)
    except ValueError:
        raise ValueError(f"{name} muss eine ganze Zahl sein, ist {wert!r}") from None
    if zahl < minimum:
        raise ValueError(f"{name} muss mindestens {minimum} sein, ist {zahl}")
    return zahl


def engine_optionen(url: str) -> dict:
    """Die Optionen für create_engine() zu url (seit 1.8.114, siehe oben)."""
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_pre_ping": True,
        "pool_size": _zahl("ERP_DB_POOL_SIZE", POOL_SIZE, 1),
        "max_overflow": _zahl("ERP_DB_MAX_OVERFLOW", MAX_OVERFLOW, 0),
        "pool_timeout": _zahl("ERP_DB_POOL_TIMEOUT", POOL_TIMEOUT, 1),
    }


engine = create_engine(DATABASE_URL, future=True, **engine_optionen(DATABASE_URL))


def fremdschluessel_pruefen() -> bool:
    """Seit 1.9.363 (Runde V3, Punkt 3): ERP_TEST_FREMDSCHLUESSEL=1 schaltet unter SQLite die Prüfung der Fremdschlüssel ein (PRAGMA
    foreign_keys=ON) -- nur für Test-Instanzen (ERP_ENV development oder test: Klicktests, Bildgrundlage), nie im Betrieb (production, ohne ERP_ENV).
    PostgreSQL prüft ohnehin. Bis dahin prüfte nur die Suite (tests/conftest.py, seit 1.9.339); eine Klicktest-Instanz nahm einen Auftrag ohne sein
    Angebot still an."""
    return os.getenv("ERP_TEST_FREMDSCHLUESSEL") == "1" and os.getenv("ERP_ENV") in ("development", "test")


if DATABASE_URL.startswith("sqlite") and fremdschluessel_pruefen():
    @event.listens_for(engine, "connect")
    def _fremdschluessel_an(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


# Seit 1.9.353: nach jedem create_all() unter PostgreSQL die Funktion telefonbuch() (Testschemas, lokale Entwicklung); auf dem Server legt
# sie die Migration 9e4b2c7d1a35 an. Siehe app/telefonbuch.py.
event.listen(Base.metadata, "after_create", telefonbuch.pg_anlegen)
# Seit 1.11.1: ebenso die Funktionen der Datenbank für Link und Sitzung des Kundenportals (app/portal/funktionen.py, Migration b5d1e8a3c247).
from .portal import funktionen as portal_funktionen  # noqa: E402
event.listen(Base.metadata, "after_create", portal_funktionen.pg_anlegen)
# Seit 1.11.31 (P2a): die Funktionen für die Unterlagen (app/portal/unterlagen.py, Migration e5c8a1f3b9d2) -- nach denen für Link und Sitzung.
from .portal import unterlagen as portal_unterlagen  # noqa: E402
event.listen(Base.metadata, "after_create", portal_unterlagen.pg_anlegen)
# Seit 1.11.33 (P2b): der Weckruf für den Postboten an portal_freigaben (app/portal/weckruf.py, Migration a7c3e9f1d2b4).
from .portal import weckruf as portal_weckruf  # noqa: E402
event.listen(Base.metadata, "after_create", portal_weckruf.pg_anlegen)


def get_db():
    """Die Sitzung eines Endpunkts. Seit 1.8.114 (Punkt 1b) bindet jeder Endpunkt sie mit Depends(get_db, scope="function") ein: FastAPI
    schließt sie dann, sobald der Endpunkt zurück und seine Antwort serialisiert ist -- vor dem Senden. Bis 1.8.113 hielt eine Datei
    ihre Verbindung (samt offener Transaktion, "idle in transaction") bis zum letzten Byte der Übertragung; drei langsame Downloads
    leerten so einen Pool. tests/test_v419_verbindungen.py prüft jede Route."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
