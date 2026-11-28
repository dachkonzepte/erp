"""Version 1.11.51 (W1c Stufe 2, S2-0 c; Antwort W2-3 vom 28.11.2026) -- „Portal aus seit“ am Kunden.

6 Monate nach „Portal aus“ geht der Zugang eines Kunden (nach Vorschau und Bestätigung, Stufe 2). Bis 1.11.50 stand der Zeitpunkt nur in der
Änderungshistorie.

    Schalter   an -> aus setzt den Zeitpunkt (die Zeit des Ausschaltens), aus -> an leert ihn; ein zweites „aus“ lässt ihn stehen; „aus“ an einem Kunden,
               an dem das Portal nie an war, setzt nichts
    Historie   der Zeitpunkt steht mit Namen in der Änderungshistorie
    Migration  Bestand aus der Änderungshistorie: je Kunde mit ausgeschaltetem Portal der jüngste Eintrag „Kundenportal an: Nein“; nie an, wieder an oder ohne
               Eintrag: leer; unter SQLite (Prüfung der Fremdschlüssel an, Zeilen zeigen auf customers) und PostgreSQL, hinauf und zurück
"""

import importlib.util
import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app.models import AuditLog, Customer
from tests.test_v809_kundenportal_karte_server import _url, graph, welt  # noqa: F401 -- Fixtures

ROOT = Path(__file__).resolve().parent.parent


def _schalten(client, kunde, an: bool):
    r = client.post(_url(kunde, "/schalter"), json={"an": an})
    assert r.status_code == 200, r.text


def test_an_aus_an(welt):  # noqa: F811
    db, kunde, client, _graph = welt
    _schalten(client, kunde, False)  # nie an gewesen: nichts
    db.expire_all()
    assert db.get(Customer, kunde.id).portal_aus_seit is None
    _schalten(client, kunde, True)
    db.expire_all()
    assert db.get(Customer, kunde.id).portal_aus_seit is None
    vorher = datetime.utcnow().replace(microsecond=0)
    _schalten(client, kunde, False)
    db.expire_all()
    aus_seit = db.get(Customer, kunde.id).portal_aus_seit
    assert aus_seit is not None and vorher <= aus_seit <= datetime.utcnow()
    _schalten(client, kunde, False)  # ein zweites „aus“ lässt den Zeitpunkt stehen
    db.expire_all()
    assert db.get(Customer, kunde.id).portal_aus_seit == aus_seit
    _schalten(client, kunde, True)
    db.expire_all()
    assert db.get(Customer, kunde.id).portal_aus_seit is None


def test_historie_mit_namen(welt):  # noqa: F811
    db, kunde, client, _graph = welt
    _schalten(client, kunde, True)
    _schalten(client, kunde, False)
    labels = {a.field_label for a in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Kunde", AuditLog.entity_id == str(kunde.id),
                                                                      AuditLog.field_name == "portal_aus_seit"))}
    assert labels == {"Kundenportal aus seit"}


# --- Migration ---------------------------------------------------------------------------------------------------------------------------------

def _modul():
    pfad = next((ROOT / "alembic" / "versions").glob("*_portal_aus_seit.py"))
    spec = importlib.util.spec_from_file_location("migration_portal_aus_seit", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# Kunde: (Portal an, [(Zeitpunkt, neuer Wert) der Historie zu portal_aktiv]) -> erwartet
KUNDEN = {
    1: (False, [("2026-11-25 08:00:00", "Ja"), ("2026-11-26 09:00:00", "Nein")], "2026-11-26 09:00:00"),       # an, dann aus
    2: (False, [("2026-11-25 08:00:00", "Ja"), ("2026-11-26 09:00:00", "Nein"), ("2026-11-27 10:00:00", "Ja"),
                ("2026-11-27 11:00:00", "Nein")], "2026-11-27 11:00:00"),                                          # zweimal aus: das jüngste
    3: (True, [("2026-11-25 08:00:00", "Ja")], None),                                                              # an
    4: (False, [], None),                                                                                          # nie an
    5: (True, [("2026-11-25 08:00:00", "Ja"), ("2026-11-26 09:00:00", "Nein"), ("2026-11-27 10:00:00", "Ja")], None),  # wieder an
    6: (False, [("2026-11-25 08:00:00", "Ja"), ("2026-11-26 09:00:00", "Nein")], "2026-11-26 09:00:00"),  # danach „Nein“ in einem anderen Feld
}
ANDERE_FELDER = [(4, "2026-11-28 07:00:00"), (6, "2026-11-28 07:00:00")]  # Feld name, neuer Wert „Nein“ -- zählt nicht


def _migration_pruefen(conn) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(255), portal_aktiv BOOLEAN NOT NULL DEFAULT FALSE)"))
    conn.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers (id))"))
    conn.execute(text("CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, occurred_at TIMESTAMP NOT NULL, entity_type VARCHAR(80), entity_id VARCHAR(40), "
                      "field_name VARCHAR(120), new_value TEXT)"))
    n = 0
    for kid, (an, historie, _soll) in KUNDEN.items():
        conn.execute(text("INSERT INTO customers (id, name, portal_aktiv) VALUES (:i, :n, :a)"), {"i": kid, "n": f"Erfunden {kid}", "a": an})
        conn.execute(text("INSERT INTO projects (id, customer_id) VALUES (:i, :i)"), {"i": kid})  # etwas zeigt auf customers
        for zeit, wert in historie:
            n += 1
            conn.execute(text("INSERT INTO audit_logs (id, occurred_at, entity_type, entity_id, field_name, new_value) VALUES (:i, :t, 'Kunde', :k, "
                              "'portal_aktiv', :w)"), {"i": n, "t": datetime.fromisoformat(zeit), "k": str(kid), "w": wert})
    for kid, zeit in ANDERE_FELDER:  # ein Eintrag zu einem anderen Feld zählt nicht
        n += 1
        conn.execute(text("INSERT INTO audit_logs (id, occurred_at, entity_type, entity_id, field_name, new_value) VALUES (:i, :t, 'Kunde', :k, 'name', "
                          "'Nein')"), {"i": n, "t": datetime.fromisoformat(zeit), "k": str(kid)})
    modul = _modul()
    with Operations.context(MigrationContext.configure(conn)):
        modul.upgrade()
    ist = {kid: wert for kid, wert in conn.execute(text("SELECT id, portal_aus_seit FROM customers ORDER BY id"))}
    soll = {kid: (datetime.fromisoformat(s) if s else None) for kid, (_a, _h, s) in KUNDEN.items()}
    assert {k: (datetime.fromisoformat(v) if isinstance(v, str) else v) for k, v in ist.items()} == soll
    with Operations.context(MigrationContext.configure(conn)):
        modul.downgrade()
    assert "portal_aus_seit" not in {c["name"] for c in inspect(conn).get_columns("customers")}
    assert conn.execute(text("SELECT count(*) FROM customers")).scalar() == len(KUNDEN)


def test_migration_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")
    try:
        with engine.begin() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
            _migration_pruefen(conn)
    finally:
        engine.dispose()


def test_migration_postgresql():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_portalaus_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.begin() as conn:
            _migration_pruefen(conn)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
