"""Version 1.11.21 (P1f, S5 auf dem Server am 25.11.2026): scripts/portal_rechte.py --setzen brach ab, nichts gesetzt --
„This connection has already initialized a SQLAlchemy Transaction() object via begin() or autobegin“. Das Skript las den Namen der Datenbank, bevor es
die Transaktion öffnete; SQLAlchemy 2 beginnt sie mit der ersten Anweisung selbst (autobegin), das folgende conn.begin() scheiterte. Die Tests riefen bis
dahin nur rechte.setzen() in einer eigenen Transaktion auf, das Skript selbst nur ohne Datenbank (Rückgabe 2).

    Kindprozess   das Skript wie in S5 und update.sh: Python aus .venv, im Repo-Ordner, DATABASE_URL aus der Umgebung -- --setzen, dann --pruefen; gegen
                  PostgreSQL in einem Wegwerf-Schema, das alembic upgrade head anlegt (wie auf dem Server), mit der Testrolle ohne Rechte im Schema.
                  Zur Abgrenzung zusätzlich --rolle und --schema (auf dem Server die Vorgaben dkportal und public).
    vorher        die Rolle hat im Schema kein Recht (0 Spalten, 0 Funktionen), --pruefen meldet Abweichungen (Rückgabe 1)
    setzen        Rückgabe 0, „Rechte für … gesetzt: 2 Tabellen (nur Lesen), 8 Funktionen, n Anweisungen.“
    pruefen       Rückgabe 0, „Rechte für … stimmen.“; danach 9 Spalten (8 der Firmendaten, 1 der Revision) und 8 Funktionen wie in S5 erwartet
    zweimal       --setzen und --pruefen noch einmal (update.sh bei jedem Einspielen): dasselbe Ergebnis
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.pg_schutz import pg_url_pruefen
from tests.test_v800_portal_funktionen import TESTROLLE

ROOT = Path(__file__).resolve().parents[1]
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture(scope="module")
def schema_von_alembic():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_rechte_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": TESTROLLE}).first() is None:
                pytest.skip(f"Testrolle {TESTROLLE} fehlt (siehe tests/test_v799_portal_rechte.py)")
        r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600, env=dict(os.environ, DATABASE_URL=pg_url_pruefen(url), PYTHONIOENCODING="utf-8"))
        assert r.returncode == 0, r.stdout + r.stderr
        yield url, engine, schema
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _skript(url: str, schema: str, art: str) -> subprocess.CompletedProcess:
    """Wie in S5: .venv/bin/python scripts/portal_rechte.py --setzen bzw. --pruefen, im Repo-Ordner, DATABASE_URL aus der Umgebung."""
    return subprocess.run([sys.executable, "scripts/portal_rechte.py", art, "--rolle", TESTROLLE, "--schema", schema], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                          env=dict(os.environ, DATABASE_URL=pg_url_pruefen(url), PYTHONIOENCODING="utf-8"))


def _rechte(engine, schema: str) -> tuple[int, int]:
    """Wie die Abfrage in S5: Spalten und Funktionen, auf die die Rolle ein Recht hat -- hier nur im Wegwerf-Schema."""
    with engine.connect() as c:
        spalten = c.execute(text("SELECT count(*) FROM information_schema.column_privileges WHERE grantee = :r AND table_schema = :s"),
                            {"r": TESTROLLE, "s": schema}).scalar()
        funktionen = c.execute(text("SELECT count(*) FROM information_schema.routine_privileges WHERE grantee = :r AND routine_schema = :s"),
                               {"r": TESTROLLE, "s": schema}).scalar()
    return spalten, funktionen


def test_pg_skript_als_kindprozess_setzen_dann_pruefen(schema_von_alembic):
    url, engine, schema = schema_von_alembic
    assert _rechte(engine, schema) == (0, 0)  # die Rolle hat im Schema noch kein Recht
    vorher = _skript(url, schema, "--pruefen")
    assert vorher.returncode == 1 and f"Rechte für {TESTROLLE}: " in vorher.stdout and "Abweichungen" in vorher.stdout, vorher.stdout + vorher.stderr

    for _ in range(2):  # update.sh setzt und prüft bei jedem Einspielen
        gesetzt = _skript(url, schema, "--setzen")
        assert gesetzt.returncode == 0, gesetzt.stdout + gesetzt.stderr
        assert gesetzt.stdout.startswith(f"Rechte für {TESTROLLE} gesetzt: 2 Tabellen (nur Lesen), 8 Funktionen, "), gesetzt.stdout
        assert gesetzt.stderr == ""
        geprueft = _skript(url, schema, "--pruefen")
        assert (geprueft.returncode, geprueft.stdout, geprueft.stderr) == (0, f"Rechte für {TESTROLLE} stimmen.\n", "")
        assert _rechte(engine, schema) == (9, 8)
    for ausgabe in (vorher, gesetzt, geprueft):
        assert "postgresql" not in ausgabe.stdout + ausgabe.stderr  # nie die Verbindungszeichenfolge
