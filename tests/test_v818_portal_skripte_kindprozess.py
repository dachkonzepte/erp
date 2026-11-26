"""Version 1.11.25 (Frage F1 aus 1.11.21, bestätigt 25.11.2026): pruefe_portal_e4.py und der Postbote als Kindprozess gegen PostgreSQL -- so, wie sie
auf dem Server laufen (S6, S8): Python aus .venv, im Repo-Ordner, DATABASE_URL aus der Umgebung, in einem Wegwerf-Schema, das alembic upgrade head anlegt.
Bis dahin liefen beide in Tests nur im Testprozess bzw. ohne Datenbank -- dieselbe Lücke, durch die portal_rechte.py --setzen in S5 abbrach (1.11.21).

    e4          ohne Aufruf Rückgabe 1 „0 Anschlüsse, 0 Aufrufe“ und „Noch kein Aufruf“; mit zwei erfundenen Anschlüssen (je zwei Aufrufe in der Bremse
                des Links) Rückgabe 0 „2 Anschlüsse, 4 Aufrufe“ und „Erwartet nach dem Nachweis mit zwei Geräten: 2“
    Postbote    „Postbote bereit (LISTEN portal_post, portal_freigabe)“ (seit 1.11.33 auch der Weckruf der Kopien) und „aufgeräumt“; ein zweiter daneben endet mit Rückgabe 3 („Es läuft schon ein Postbote“); der erste
                wird über seine eigene PID beendet (Regel 12)
    Kopien      (seit 1.11.33) mit PORTAL_DATEIEN legt der Postbote zu einer Freigabe die Kopie an -- PDF byte-gleich, Zeile bereit, Kennung des Ordners;
                ohne Weckruf schon im ersten vollen Lauf
    beide       keine Ausgabe nennt die Verbindungszeichenfolge
"""

import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.pg_schutz import pg_url_pruefen

ROOT = Path(__file__).resolve().parents[1]
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture(scope="module")
def schema_von_alembic(tmp_path_factory):
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_kind_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    umgebung = dict(os.environ, DATABASE_URL=pg_url_pruefen(url), PYTHONIOENCODING="utf-8", ERP_DATA_DIR=str(tmp_path_factory.mktemp("daten")),
                    ERP_SECRET_KEY="kindprozess-" + "x" * 40)
    try:
        r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600, env=umgebung)
        assert r.returncode == 0, r.stdout + r.stderr
        yield engine, umgebung
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _ohne_verbindung(*ausgaben: str) -> None:
    for a in ausgaben:
        assert "postgresql" not in a.lower() and "password" not in a.lower(), a


def _e4(umgebung) -> subprocess.CompletedProcess:
    """Wie in S8: .venv/bin/python scripts/pruefe_portal_e4.py, im Repo-Ordner, DATABASE_URL aus der Umgebung."""
    return subprocess.run([sys.executable, "scripts/pruefe_portal_e4.py"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120, env=umgebung)


def test_pg_pruefe_portal_e4_als_kindprozess(schema_von_alembic):
    engine, umgebung = schema_von_alembic
    leer = _e4(umgebung)
    assert leer.returncode == 1 and ": 0 Anschlüsse, 0 Aufrufe." in leer.stdout and "Noch kein Aufruf" in leer.stdout and leer.stderr == "", leer
    with engine.begin() as c:  # zwei Anschlüsse, je zwei Aufrufe -- wie zwei Geräte, die den erfundenen Link je zweimal öffnen (S8)
        for anschluss in ("a", "b"):
            c.execute(text("INSERT INTO portal_bremsen (schluessel, fenster_beginn, zaehler) "
                           "VALUES (:k, date_trunc('hour', now() at time zone 'utc'), 2)"), {"k": "link:a:" + anschluss * 64})
    zwei = _e4(umgebung)
    assert zwei.returncode == 0 and ": 2 Anschlüsse, 4 Aufrufe." in zwei.stdout and "Erwartet nach dem Nachweis mit zwei Geräten: 2" in zwei.stdout, zwei
    assert zwei.stderr == ""
    _ohne_verbindung(leer.stdout, zwei.stdout)


def _bis(bedingung, was: str, prozess: subprocess.Popen, zeilen: list[str], sicherheitsnetz: float = 120.0) -> None:
    ende = time.monotonic() + sicherheitsnetz
    while not bedingung():
        assert prozess.poll() is None, (f"der Postbote endete ({prozess.returncode}), bevor {was}", zeilen[-10:])
        assert time.monotonic() < ende, (f"nach {sicherheitsnetz:.0f} s nicht: {was}", zeilen[-10:])
        time.sleep(0.05)


def _freigabe_mit_datei(engine, umgebung) -> tuple[int, bytes]:
    """Ein Kunde mit einem Dokument (PDF in customer_files unter ERP_DATA_DIR) und dessen Freigabe ohne Kopie -- wie das ERP es ablegt."""
    pdf = b"%PDF-1.4\n% erfunden fuer den Kindprozess\n%%EOF\n"
    stored = uuid.uuid4().hex + ".pdf"
    with engine.begin() as c:
        kid = c.execute(text("INSERT INTO customers (name, last_name, created_at) VALUES ('Muster Kind', 'Muster', now()) RETURNING id")).scalar()
        kat = c.execute(text("INSERT INTO document_categories (key, label, created_at, updated_at) VALUES (:k, 'Sonstiges', now(), now()) RETURNING id"),
                        {"k": f"kind-{uuid.uuid4().hex[:8]}"}).scalar()
        did = c.execute(text("INSERT INTO customer_documents (customer_id, category, category_id, original_filename, stored_filename, file_size, uploaded_at) "
                             "VALUES (:k, 'Sonstiges', :c, 'plan.pdf', :s, :g, now()) RETURNING id"), {"k": kid, "c": kat, "s": stored, "g": len(pdf)}).scalar()
        fid = c.execute(text("INSERT INTO portal_freigaben (customer_id, art, quelle, quelle_id, titel, datum, freigegeben_am, freigegeben_von_name) "
                             "VALUES (:k, 'dokument', 'customer_documents', :d, 'Plan', DATE '2026-11-26', now(), 'Büro') RETURNING id"),
                        {"k": kid, "d": did}).scalar()
    ordner = Path(umgebung["ERP_DATA_DIR"]) / "customer_files" / str(kid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / stored).write_bytes(pdf)
    return fid, pdf


def test_pg_postbote_als_kindprozess(schema_von_alembic, tmp_path):
    engine, umgebung = schema_von_alembic
    kopien = tmp_path / "kopien"
    kopien.mkdir()
    umgebung = dict(umgebung, PORTAL_DATEIEN=str(kopien))
    fid, pdf = _freigabe_mit_datei(engine, umgebung)
    zeilen: list[str] = []
    erster = subprocess.Popen([sys.executable, "scripts/portal_postbote.py"], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace", env=umgebung)
    leser = threading.Thread(target=lambda: zeilen.extend(z.rstrip() for z in erster.stdout), daemon=True)
    leser.start()
    try:
        _bis(lambda: any("Postbote bereit (LISTEN portal_post, portal_freigabe)" in z for z in zeilen), "„Postbote bereit“", erster, zeilen)
        _bis(lambda: any("Postbote: aufgeräumt" in z for z in zeilen), "„aufgeräumt“", erster, zeilen)
        _bis(lambda: any("Postbote: Kopien angelegt 1" in z for z in zeilen), "„Kopien angelegt 1“", erster, zeilen)
        with engine.connect() as c:
            name, bereit = c.execute(text("SELECT kopie_name, kopie_bereit_am FROM portal_freigaben WHERE id = :i"), {"i": fid}).one()
        assert bereit is not None and (kopien / name).read_bytes() == pdf and (kopien / ".datenbank").exists()
        zweiter = subprocess.run([sys.executable, "scripts/portal_postbote.py"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=120, env=umgebung)
        assert zweiter.returncode == 3 and "Es läuft schon ein Postbote" in zweiter.stderr, zweiter
        assert erster.poll() is None, "der erste Postbote läuft weiter"
    finally:
        erster.terminate()  # nur der eigene Prozess, über seine PID (Regel 12)
        erster.wait(timeout=30)
        leser.join(timeout=10)
    _ohne_verbindung("\n".join(zeilen), zweiter.stdout, zweiter.stderr)
