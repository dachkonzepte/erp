"""Version 1.10.9 (Stufe W1c): ein Objektdokument zeigt auf den Eingang der Webseite -- nur Musterdaten, gegen die Attrappe des Empfangsdienstes.

    Übernehmen  jede Fotokopie am Objekt trägt den Eingang (webanfrage_id); Beschreibung und Dateiname bleiben wie seit 1.10.5
    Upload      ein von Hand hochgeladenes Objektdokument trägt nie einen Eingang
    Migration   der Bestand wird nur bei allen drei Merkmalen verknüpft (Beschreibung genau, Dateiname „<Nummer>-“, Objekt der übernommenen
                Anfrage) -- leere Beschreibung, leeres Objekt, fremdes Objekt, nicht übernommener Eingang, Platzhalter im Text bleiben leer;
                unter SQLite und PostgreSQL; downgrade() lässt alles andere stehen
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app.models import Inquiry, PropertyDocument
from app.property_documents import create_property_document
from tests.test_v777_webanfragen_uebernehmen import _neu, _welt, dienst  # noqa: F401 -- Fixture
from scripts.empfangsdienst_attrappe import muster

ROOT = Path(__file__).resolve().parent.parent
N1, N2, N3 = "R-20261119-0910-0A1B", "R-20261119-0911-0A2C", "R-20261119-0912-0A3D"
TEXT = "Foto der Anfrage der Webseite "


def test_uebernehmen_setzt_den_eingang(dienst, threaded_db_session, router_test_client):  # noqa: F811
    db = threaded_db_session
    c, ids = _welt(dienst, db, router_test_client, muster(N1, fotos=2))
    v = c.get(f"/api/webanfragen/{ids[N1]}/vorschlag").json()
    r = c.post(f"/api/webanfragen/{ids[N1]}/uebernehmen", json=_neu(v))
    assert r.status_code == 200, r.text
    db.expire_all()
    fotos = db.scalars(select(PropertyDocument).order_by(PropertyDocument.id)).all()
    assert len(fotos) == 2
    assert [(f.webanfrage_id, f.description, f.original_filename.startswith(N1 + "-")) for f in fotos] == [(ids[N1], TEXT + N1, True)] * 2


def test_upload_traegt_keinen_eingang(dienst, threaded_db_session, router_test_client):  # noqa: F811
    db = threaded_db_session
    c, ids = _welt(dienst, db, router_test_client, muster(N1, fotos=1))
    v = c.get(f"/api/webanfragen/{ids[N1]}/vorschlag").json()
    objekt_id = db.get(Inquiry, c.post(f"/api/webanfragen/{ids[N1]}/uebernehmen", json=_neu(v)).json()["inquiry_id"]).property_id
    kategorie = db.scalars(select(PropertyDocument.category_id)).first()
    doc = create_property_document(db, objekt_id, category_id=kategorie, file_data=b"%PDF-1.4\n", original_filename=f"{N1}-foto-9.pdf",
                                   description=TEXT + N1)  # selbst mit demselben Text: ein Upload ist keine Kopie
    assert doc.webanfrage_id is None


# --- Migration ---------------------------------------------------------------------------------------------------------------------------------

def _modul():
    pfad = next((ROOT / "alembic" / "versions").glob("*_objektdokument_webanfrage.py"))
    spec = importlib.util.spec_from_file_location("migration_objektdokument_webanfrage", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# (Objekt, Dateiname, Beschreibung) -> erwarteter Eingang
DOKUMENTE = [
    (10, f"{N1}-foto-1.jpg", TEXT + N1, 1),           # alle drei Merkmale
    (10, f"{N1}-foto-2.jpg", TEXT + N1, 1),
    (11, f"{N1}-foto-1.jpg", TEXT + N1, None),        # fremdes Objekt
    (10, "foto.jpg", TEXT + N1, None),                # Dateiname ohne Nummer
    (10, f"{N2}-foto-1.jpg", TEXT + N2, None),        # Eingang nicht übernommen (inquiry_id leer)
    (10, f"{N1}-foto-3.jpg", None, None),             # Beschreibung leer
    (10, f"{N1}-foto-4.jpg", TEXT + N1 + " (Kopie)", None),  # nicht genau
    (10, f"{N3}-foto-1.jpg", TEXT + N3, None),        # Anfrage ohne Objekt
    (10, "%-foto.jpg", TEXT + "%", None),             # Platzhalter gilt wörtlich
]


def _bestand_pruefen(conn) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    conn.execute(text("CREATE TABLE inquiries (id INTEGER PRIMARY KEY, property_id INTEGER)"))
    conn.execute(text("CREATE TABLE webanfragen (id INTEGER PRIMARY KEY, nummer VARCHAR(40) NOT NULL, inquiry_id INTEGER)"))
    conn.execute(text("CREATE TABLE property_documents (id INTEGER PRIMARY KEY, property_id INTEGER NOT NULL, "
                      "original_filename VARCHAR(255) NOT NULL, description TEXT)"))
    conn.execute(text("INSERT INTO inquiries (id, property_id) VALUES (1, 10), (2, NULL)"))
    conn.execute(text("INSERT INTO webanfragen (id, nummer, inquiry_id) VALUES (1, :a, 1), (2, :b, NULL), (3, :c, 2)"), {"a": N1, "b": N2, "c": N3})
    for i, (objekt, name, beschreibung, _) in enumerate(DOKUMENTE, start=1):
        conn.execute(text("INSERT INTO property_documents (id, property_id, original_filename, description) VALUES (:i, :o, :n, :b)"),
                     {"i": i, "o": objekt, "n": name, "b": beschreibung})
    modul = _modul()
    with Operations.context(MigrationContext.configure(conn)):
        modul.upgrade()
    werte = conn.execute(text("SELECT webanfrage_id FROM property_documents ORDER BY id")).scalars().all()
    assert werte == [d[3] for d in DOKUMENTE]
    modul.verknuepfen(conn)  # ein zweiter Lauf ändert nichts
    assert conn.execute(text("SELECT webanfrage_id FROM property_documents ORDER BY id")).scalars().all() == werte
    with Operations.context(MigrationContext.configure(conn)):
        modul.downgrade()
    assert "webanfrage_id" not in {c["name"] for c in inspect(conn).get_columns("property_documents")}
    rest = conn.execute(text("SELECT property_id, original_filename, description FROM property_documents ORDER BY id")).all()
    assert [tuple(r) for r in rest] == [d[:3] for d in DOKUMENTE]


def test_migration_bestand_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")
    try:
        with engine.begin() as conn:
            _bestand_pruefen(conn)
    finally:
        engine.dispose()


def test_migration_bestand_postgresql():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_w1c_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.begin() as conn:
            _bestand_pruefen(conn)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
