"""Version 1.11.50 (W1c Stufe 2, S2-0 b; Bauplan B6, Antwort F5 vom 21.11.2026) -- das Übernehmen hält fest, was es am Objekt setzt.

Stufe 2 soll Ansprechpartner vor Ort und Telefon am Objekt leeren, wenn die Anfrage gelöscht wird, aus der sie stammen -- nur, wenn sie beim Übernehmen gesetzt
wurden und seither unverändert sind. Bis 1.11.49 hielt das Übernehmen das nicht fest. Nur Musterdaten, gegen die Attrappe des Empfangsdienstes.

    gewählt      Objekt gewählt mit „vor Ort übernehmen“: Eingang und Prüfwert der gesetzten Werte am Objekt; ohne Haken nichts (eine frühere Herkunft bleibt)
    neu          neues Objekt mit Ansprechpartner vor Ort: Herkunft gesetzt; ohne Ansprechpartner keine; „Hauptadresse“ keine
    unverändert  vor_ort_unveraendert(): wahr nur mit Herkunft und gleichem Prüfwert -- eine Änderung von Hand an Name oder Telefon macht es falsch
    Prüfwert     SHA-256 über Name und Telefon mit Trennzeichen (aus „ab“+„c“ wird nicht dasselbe wie aus „a“+„bc“), leer wie „“
    Historie     die Herkunft steht in der Änderungshistorie mit Namen, der Prüfwert nicht
    Migration    unter SQLite mit eingeschalteter Prüfung der Fremdschlüssel und Zeilen, die auf properties zeigen: hinauf ohne Neuaufbau, Fremdschlüssel da,
                 Daten bleiben; unter PostgreSQL hinauf und zurück
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app.crm import kunde_anlegen
from app.models import AuditLog, Customer, Inquiry, Property
from app.webanfrage_uebernahme import vor_ort_pruefwert, vor_ort_unveraendert
from scripts.empfangsdienst_attrappe import muster
from tests.test_v777_webanfragen_uebernehmen import _neu, _welt, dienst  # noqa: F401 -- Fixture

ROOT = Path(__file__).resolve().parent.parent
N1, N2 = "R-20261119-0910-0A1B", "R-20261119-0911-0A2C"


def _haus(db, **mehr):
    k = kunde_anlegen(db, {"last_name": "HV Musterhaus"})
    haus = Property(customer_id=k.id, name="Haus", street="Musterweg 1", postal_code="00000", city="Musterstadt", **mehr)
    db.add(haus)
    db.commit()
    return k, haus


def _gewaehlt(c, eingang_id, k, haus, haken):
    body = {"kunde_id": k.id, "objekt": "gewaehlt", "objekt_id": haus.id, "titel": "Rinne", "vor_ort_uebernehmen": haken}
    r = c.post(f"/api/webanfragen/{eingang_id}/uebernehmen", json=body)
    assert r.status_code == 200, r.text


def test_gewaehltes_objekt_mit_haken(dienst, threaded_db_session, router_test_client):  # noqa: F811
    db = threaded_db_session
    k, haus = _haus(db, site_contact_name="Hausmeister")
    c, ids = _welt(dienst, db, router_test_client, muster(N1, rolle="mieter", name="Mia Mieter", hausverwaltung="HV Musterhaus", telefon="0000 333"))
    _gewaehlt(c, ids[N1], k, haus, True)
    db.expire_all()
    haus = db.get(Property, haus.id)
    assert (haus.site_contact_name, haus.site_contact_phone) == ("Mia Mieter", "0000 333")
    assert (haus.vor_ort_aus_webanfrage_id, haus.vor_ort_pruefwert) == (ids[N1], vor_ort_pruefwert("Mia Mieter", "0000 333"))
    assert vor_ort_unveraendert(haus) is True
    haus.site_contact_phone = "0000 999"  # von Hand geändert
    db.commit()
    assert vor_ort_unveraendert(db.get(Property, haus.id)) is False


def test_ohne_haken_nichts_und_eine_fruehere_herkunft_bleibt(dienst, threaded_db_session, router_test_client):  # noqa: F811
    db = threaded_db_session
    k, haus = _haus(db, site_contact_name="Hausmeister")
    c, ids = _welt(dienst, db, router_test_client,
                   muster(N1, rolle="mieter", name="Mia Mieter", hausverwaltung="HV Musterhaus", telefon="0000 333"),
                   muster(N2, rolle="mieter", name="Moritz Mieter", hausverwaltung="HV Musterhaus", telefon="0000 444"))
    _gewaehlt(c, ids[N2], k, haus, False)
    db.expire_all()
    haus = db.get(Property, haus.id)
    assert (haus.site_contact_name, haus.vor_ort_aus_webanfrage_id, haus.vor_ort_pruefwert) == ("Hausmeister", None, None)
    assert vor_ort_unveraendert(haus) is False  # ohne Herkunft: Stufe 2 lässt den Ansprechpartner stehen
    _gewaehlt(c, ids[N1], k, haus, True)
    db.expire_all()
    assert db.get(Property, haus.id).vor_ort_aus_webanfrage_id == ids[N1]


def test_neues_objekt_mit_und_ohne_ansprechpartner(dienst, threaded_db_session, router_test_client):  # noqa: F811
    db = threaded_db_session
    c, ids = _welt(dienst, db, router_test_client, muster(N1, vor_ort={"name": "Erika Muster", "telefon": "0000 111"}), muster(N2))
    v1 = c.get(f"/api/webanfragen/{ids[N1]}/vorschlag").json()
    i1 = c.post(f"/api/webanfragen/{ids[N1]}/uebernehmen", json=_neu(v1)).json()["inquiry_id"]
    v2 = c.get(f"/api/webanfragen/{ids[N2]}/vorschlag").json()
    i2 = c.post(f"/api/webanfragen/{ids[N2]}/uebernehmen", json=_neu(v2)).json()["inquiry_id"]
    db.expire_all()
    mit = db.get(Property, db.get(Inquiry, i1).property_id)
    ohne = db.get(Property, db.get(Inquiry, i2).property_id)
    assert (mit.site_contact_name, mit.vor_ort_aus_webanfrage_id, mit.vor_ort_pruefwert) == ("Erika Muster", ids[N1], vor_ort_pruefwert("Erika Muster", "0000 111"))
    assert (ohne.site_contact_name, ohne.site_contact_phone, ohne.vor_ort_aus_webanfrage_id, ohne.vor_ort_pruefwert) == (None, None, None, None)


def test_hauptadresse_ohne_herkunft(dienst, threaded_db_session, router_test_client):  # noqa: F811
    db = threaded_db_session
    c, ids = _welt(dienst, db, router_test_client, muster(N1, vor_ort={"name": "Erika Muster", "telefon": "0000 111"}))
    v = c.get(f"/api/webanfragen/{ids[N1]}/vorschlag").json()
    r = c.post(f"/api/webanfragen/{ids[N1]}/uebernehmen", json=_neu(v, objekt="hauptadresse", objekt_neu=None))
    assert r.status_code == 200, r.text
    db.expire_all()
    haupt = db.get(Property, db.get(Inquiry, r.json()["inquiry_id"]).property_id)
    assert haupt.is_primary_address and (haupt.vor_ort_aus_webanfrage_id, haupt.vor_ort_pruefwert) == (None, None)


def test_pruefwert():
    assert vor_ort_pruefwert("Mia Mieter", "0000 333") == vor_ort_pruefwert("Mia Mieter", "0000 333")
    assert len(vor_ort_pruefwert("a", "b")) == 64
    assert vor_ort_pruefwert("ab", "c") != vor_ort_pruefwert("a", "bc")
    assert vor_ort_pruefwert(None, None) == vor_ort_pruefwert("", "")
    assert vor_ort_pruefwert("Mia", None) != vor_ort_pruefwert("Mia", "0000")


def test_historie_mit_herkunft_ohne_pruefwert(dienst, threaded_db_session, router_test_client):  # noqa: F811
    db = threaded_db_session
    k, haus = _haus(db)
    c, ids = _welt(dienst, db, router_test_client, muster(N1, rolle="mieter", name="Mia Mieter", hausverwaltung="HV Musterhaus", telefon="0000 333"))
    _gewaehlt(c, ids[N1], k, haus, True)
    felder = {(a.field_name, a.field_label) for a in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Objekt",
                                                                                     AuditLog.entity_id == str(haus.id)))}
    assert ("vor_ort_aus_webanfrage_id", "Ansprechpartner vor Ort aus Anfrage der Webseite") in felder
    assert not any(f == "vor_ort_pruefwert" for f, _ in felder)


# --- Migration ---------------------------------------------------------------------------------------------------------------------------------

def _modul():
    pfad = next((ROOT / "alembic" / "versions").glob("*_vor_ort_herkunft.py"))
    spec = importlib.util.spec_from_file_location("migration_vor_ort_herkunft", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _migration_pruefen(conn, *, zurueck: bool) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    conn.execute(text("CREATE TABLE webanfragen (id INTEGER PRIMARY KEY)"))
    conn.execute(text("CREATE TABLE properties (id INTEGER PRIMARY KEY, name VARCHAR(255), site_contact_name VARCHAR(160))"))
    conn.execute(text("CREATE TABLE inquiries (id INTEGER PRIMARY KEY, property_id INTEGER REFERENCES properties (id))"))
    conn.execute(text("INSERT INTO webanfragen (id) VALUES (1)"))
    conn.execute(text("INSERT INTO properties (id, name, site_contact_name) VALUES (10, 'Haus', 'Hausmeister'), (11, 'Halle', NULL)"))
    conn.execute(text("INSERT INTO inquiries (id, property_id) VALUES (1, 10)"))  # etwas zeigt auf properties
    modul = _modul()
    with Operations.context(MigrationContext.configure(conn)):
        modul.upgrade()
    spalten = {c["name"] for c in inspect(conn).get_columns("properties")}
    assert {"vor_ort_aus_webanfrage_id", "vor_ort_pruefwert"} <= spalten
    fks = [fk for fk in inspect(conn).get_foreign_keys("properties") if fk["constrained_columns"] == ["vor_ort_aus_webanfrage_id"]]
    assert [(fk["referred_table"], fk["referred_columns"]) for fk in fks] == [("webanfragen", ["id"])]
    assert "ix_properties_vor_ort_aus_webanfrage_id" in {i["name"] for i in inspect(conn).get_indexes("properties")}
    assert [tuple(r) for r in conn.execute(text("SELECT id, name, site_contact_name, vor_ort_aus_webanfrage_id, vor_ort_pruefwert FROM properties "
                                                 "ORDER BY id"))] == [(10, "Haus", "Hausmeister", None, None), (11, "Halle", None, None, None)]
    conn.execute(text("UPDATE properties SET vor_ort_aus_webanfrage_id = 1 WHERE id = 10"))  # der Fremdschlüssel nimmt einen Eingang an
    if zurueck:
        conn.execute(text("UPDATE properties SET vor_ort_aus_webanfrage_id = NULL"))
        with Operations.context(MigrationContext.configure(conn)):
            modul.downgrade()
        spalten = {c["name"] for c in inspect(conn).get_columns("properties")}
        assert "vor_ort_aus_webanfrage_id" not in spalten and "vor_ort_pruefwert" not in spalten
        assert [tuple(r) for r in conn.execute(text("SELECT id, name FROM properties ORDER BY id"))] == [(10, "Haus"), (11, "Halle")]


def test_migration_sqlite_mit_fremdschluesseln(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")
    try:
        with engine.begin() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1  # wie jede SQLite-Verbindung der Tests (tests/conftest.py)
            _migration_pruefen(conn, zurueck=False)
            with pytest.raises(Exception, match="FOREIGN KEY"):
                with conn.begin_nested():
                    conn.execute(text("UPDATE properties SET vor_ort_aus_webanfrage_id = 99 WHERE id = 11"))  # kein solcher Eingang
    finally:
        engine.dispose()


def test_migration_postgresql_hinauf_und_zurueck():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_vorort_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.begin() as conn:
            _migration_pruefen(conn, zurueck=True)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_kunde_und_objekt_unberuehrt_ohne_eingang(threaded_db_session):
    """Ohne Übernehmen setzt nichts die Herkunft -- ein Objekt von Hand bleibt leer."""
    db = threaded_db_session
    k = kunde_anlegen(db, {"last_name": "Muster"})
    db.add(Property(customer_id=k.id, name="Haus", site_contact_name="Erika Muster", site_contact_phone="0000 111"))
    db.commit()
    haus = db.scalar(select(Property).where(Property.name == "Haus"))
    assert (haus.vor_ort_aus_webanfrage_id, haus.vor_ort_pruefwert) == (None, None)
    assert db.get(Customer, k.id) is not None


def test_kein_ring_beim_sortieren_der_tabellen():
    """Der Fremdschlüssel schließt den Ring properties -> webanfragen -> inquiries -> properties; ohne use_alter konnte SQLAlchemy die Tabellen nicht
    sortieren (SAWarning, tests/conftest.py legt Vorlagen in dieser Reihenfolge an) -- mit use_alter und Namen keine Warnung."""
    import warnings

    from app.database import Base

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        namen = [t.name for t in Base.metadata.sorted_tables]
    assert {"properties", "webanfragen", "inquiries"} <= set(namen)
    fk = next(fk for fk in Property.__table__.foreign_keys if fk.parent.name == "vor_ort_aus_webanfrage_id")
    assert fk.use_alter and fk.constraint.name == "fk_properties_vor_ort_aus_webanfrage_id"
