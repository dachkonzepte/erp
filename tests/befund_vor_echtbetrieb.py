"""Gemeinsames für die Tests zum Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026,
docs/archiv/befund-vor-echtbetrieb.md) -- tests/test_v372_befund_*.py.

befund(): xfail(strict=True, raises=AssertionError) mit Verweis auf den Befund und die Nummer des Fehlers. strict: ist ein Fehler
behoben, wird sein Test rot ("XPASS(strict)"), bis die Markierung fällt -- danach ist er der Abnahmetest der Reparatur.
raises=AssertionError: scheitert ein Test an etwas anderem (Aufbau, Tippfehler, neue Ausnahme), ist er rot statt still "erwartet
fehlgeschlagen". Vorbedingungen deshalb mit vorbedingung() -- sie wirft Vorbedingung, keinen AssertionError.

pg_sitzung(): Sitzung auf einem Wegwerf-Schema der lokalen PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in, sonst skip) mit Tabellen
und Grunddaten -- dasselbe Muster wie die pg-Fixtures in test_v349/test_v369, Fremdschlüssel und Spaltenlängen greifen dort."""

import os
import uuid
from contextlib import contextmanager

import pytest

BEFUND = "Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (docs/archiv/befund-vor-echtbetrieb.md)"


def befund(nr: str, text: str):
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{BEFUND}, {nr}: {text}")


class Vorbedingung(Exception):
    """Aufbau eines Befund-Tests gescheitert -- bewusst kein AssertionError."""


def vorbedingung(ok: bool, text: str = "") -> None:
    if not ok:
        raise Vorbedingung(text)


@contextmanager
def pg_sitzung(name: str):
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import close_all_sessions, sessionmaker

    import app.models  # noqa: F401  (registriert die Tabellen an Base.metadata)
    from app.database import Base
    from app.grunddaten import anlegen

    schema = f"pgtest_{name}_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            anlegen(db)
            db.commit()
            yield db
        finally:
            db.close()
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
