"""Version 1.9.351 -- Adressimport prüft jede Zeile (Runde V2a, Punkt 2; F7, Entscheidung Tobias 14.11.2026).

Eine Zeile mit einem zu langen Wert wird abgelehnt, nicht gekürzt; die übrigen gehen durch. Die Antwort nennt je zu langer Zelle Zeilennummer, Feld,
Grenze und Länge (`abgelehnt`), die Vorschau zeigt die Zeile als „abgelehnt“, Bestätigen übernimmt sie nie. Die Grenze einer Datei-Spalte ist die
kürzeste Spalte, in die ihr Wert geht (`app/address_import.py::zellen_grenzen()`). Bis 1.9.350 nahm SQLite einen zu langen Wert still an, unter
PostgreSQL scheiterte die ganze Datei mit 500 (Befund P11) -- die Fälle unten waren vorher rot."""

import csv
import io
import os
import uuid

import pytest
from sqlalchemy import String, create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker

from app.address_import import NAME_ZUSAMMEN, REQUIRED_HEADERS, confirm_import, create_preview, zellen_grenzen
from app.database import Base
from app.grunddaten import anlegen
from app.models import Customer, ImportedAddress, Property, Supplier
from app.routers.address_import import router as import_router

PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _csv(*zeilen: dict) -> bytes:
    puffer = io.StringIO()
    w = csv.DictWriter(puffer, fieldnames=REQUIRED_HEADERS, delimiter=";", lineterminator="\r\n")
    w.writeheader()
    for z in zeilen:
        w.writerow({h: z.get(h, "") for h in REQUIRED_HEADERS})
    return puffer.getvalue().encode("utf-8")


KUNDE = {"Adresse": "A-1", "Kunde": "K-1", "Name": "Muster Bau", "Straße": "Hauptstraße 1", "PLZ": "12345", "Ort": "Musterstadt"}
LIEFERANT = {"Adresse": "A-3", "Lieferant": "L-1", "Name": "Holz Probe", "PLZ": "54321", "Ort": "Probedorf"}


def _hochladen(client, daten: bytes):
    return client.post("/api/address-import/upload", files={"file": ("adressen.csv", daten, "text/csv")})


def test_zu_lange_zeile_abgelehnt_die_uebrigen_gehen_durch(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, import_router)
    zu_lang = {**KUNDE, "Adresse": "A-2", "Kunde": "K-2", "Name": "Zu Lang", "PLZ": "1" * 21}
    r = _hochladen(client, _csv(KUNDE, zu_lang, LIEFERANT))
    assert r.status_code == 200, r.text
    vorschau = r.json()
    assert vorschau["abgelehnt"] == [{"zeile": 3, "feld": "PLZ", "grenze": 20, "laenge": 21}]
    assert {k: vorschau["counts"][k] for k in ("customer", "supplier", "abgelehnt")} == {"customer": 1, "supplier": 1, "abgelehnt": 1}
    zeile = next(z for z in vorschau["rows"] if z["row_number"] == 3)
    assert (zeile["classification"], zeile["postal_code"], zeile["last_name"]) == ("abgelehnt", None, "Zu Lang")  # nicht gekürzt, nichts Zu Langes
    assert zeile["validation_notes"] == "Zeile abgelehnt – PLZ hat 21 Zeichen, höchstens 20."
    # auch nach dem Neuladen der Seite
    assert client.get("/api/address-import/preview").json()["abgelehnt"] == vorschau["abgelehnt"]
    bestaetigt = client.post("/api/address-import/confirm?filename=adressen.csv")
    assert bestaetigt.status_code == 200, bestaetigt.text
    db.expire_all()
    assert sorted(c.legacy_address_number for c in db.scalars(select(Customer))) == ["A-1"]
    assert [s.legacy_address_number for s in db.scalars(select(Supplier))] == ["A-3"]
    assert db.scalar(select(ImportedAddress.status).where(ImportedAddress.row_number == 3)) == "confirmed"  # Nachweis im Lauf


def test_mehrere_zellen_einer_zeile_und_die_zweite_mail(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, import_router)
    zeile = {**KUNDE, "Ort": "o" * 121, "Telefon": "1" * 81, "Mail": "a@example.com, " + "b" * 250 + "@example.com"}
    abgelehnt = _hochladen(client, _csv(zeile)).json()["abgelehnt"]
    assert abgelehnt == [{"zeile": 2, "feld": "Ort", "grenze": 120, "laenge": 121}, {"zeile": 2, "feld": "Telefon", "grenze": 80, "laenge": 81},
                         {"zeile": 2, "feld": "Mail (zweite Adresse)", "grenze": 255, "laenge": 262}]


def test_zusammengesetzter_name(threaded_db_session, router_test_client):
    """Customer.name = Anrede, Titel, Vorname und Name -- jeder Teil passt, zusammen zu lang."""
    client = router_test_client(threaded_db_session, import_router)
    grenze = zellen_grenzen()["Name"][1]
    genau = {**KUNDE, "Anrede": "Herr", "Vorname": "v" * 100, "Name": "n" * (grenze - len("Herr ") - 101)}
    zu_lang = {**genau, "Adresse": "A-2", "Kunde": "K-2", "Name": genau["Name"] + "n"}
    assert _hochladen(client, _csv(genau, zu_lang)).json()["abgelehnt"] == [{"zeile": 3, "feld": NAME_ZUSAMMEN, "grenze": grenze, "laenge": grenze + 1}]


def _streng(db):
    """Wie PostgreSQL: ein Text länger als seine Spalte String(n) bricht den Flush ab (SQLite nähme ihn still an)."""
    zu_lang = []

    @event.listens_for(db, "before_flush")
    def pruefen(session, _ctx, _inst):
        for obj in list(session.new) + list(session.dirty):
            for attr in obj.__mapper__.column_attrs:
                spalte = attr.columns[0]
                wert = getattr(obj, attr.key, None)
                if isinstance(spalte.type, String) and spalte.type.length and isinstance(wert, str) and len(wert) > spalte.type.length:
                    zu_lang.append(f"{spalte.table.name}.{spalte.name}: {len(wert)} > {spalte.type.length}")
        assert not zu_lang, zu_lang
    return zu_lang


def test_jede_zelle_genau_an_der_grenze_geht_bis_in_kunde_lieferant_und_objekt(threaded_db_session):
    """Der Wächter für die Grenzen: jede Zelle mit genau ihrer Grenze (Name kurz, damit der zusammengesetzte Name passt) -- kein Wert ist danach in
    irgendeiner Spalte zu lang, weder in der Vorschau noch in Kunde, Lieferant, Objekt oder Kundennummer. Fehlte eine Zielspalte in
    zellen_grenzen(), wäre ihre Grenze zu groß, und dieser Test bräche ab."""
    db = threaded_db_session
    zu_lang = _streng(db)
    g = {feld: grenze for feld, (_k, grenze) in zellen_grenzen().items()}
    voll = {feld: "x" * g[feld] for feld in g if feld not in ("Anrede", "Titel", "Vorname", "Name", "Kunde", "Lieferant", "Adresse")}
    kunde = {**voll, "Adresse": "a" * g["Adresse"], "Kunde": "k" * g["Kunde"], "Name": "Muster", "Mail": "m" * 240 + "@example.com"}
    lieferant = {**voll, "Adresse": "b" * g["Adresse"], "Lieferant": "l" * g["Lieferant"], "Name": "Holz"}
    vorschau = create_preview(db, _csv(kunde, lieferant), "adressen.csv")
    assert vorschau["abgelehnt"] == [] and vorschau["counts"]["customer"] == 1 and vorschau["counts"]["supplier"] == 1
    confirm_import(db, "adressen.csv", None)
    assert zu_lang == []
    assert db.scalar(select(func.count()).select_from(Property)) == 1  # die Hauptadresse des Kunden


def test_upload_unter_postgresql_nennt_die_zeile_statt_500():
    """Befund P11: unter PostgreSQL scheiterte bis 1.9.350 die ganze Datei an einer PLZ aus 25 Zeichen."""
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_adressimport_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            anlegen(db)
            db.commit()
            vorschau = create_preview(db, _csv(KUNDE, {**KUNDE, "Adresse": "A-2", "Kunde": "K-2", "PLZ": "1" * 25}), "adressen.csv")
            assert vorschau["abgelehnt"] == [{"zeile": 3, "feld": "PLZ", "grenze": 20, "laenge": 25}]
            confirm_import(db, "adressen.csv", None)
            assert [c.legacy_address_number for c in db.scalars(select(Customer))] == ["A-1"]
        finally:
            db.close()
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
