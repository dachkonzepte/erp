"""Version 1.3.31 -- Adressimport aus dem Altsystem, siehe CLAUDE.md "Adressimport aus dem
Altsystem" für die vollständige Herleitung. Deckt ab: Einlesen (CSV + Excel), Klassifikation
(Kunde/Lieferant/unzugeordnet/bereits importiert), den dreistufigen Ablauf (Vorschau -> Verwerfen
oder Bestätigen), die Arbeitsliste für unzugeordnete Adressen mit ihren drei Aktionen, und das
Rückgängigmachen eines Importlaufs (Alles-oder-nichts, nur solange nichts an den erzeugten Kunden/
Lieferanten hängt)."""

import io

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import address_import as ai
from app.database import Base
from app.models import Customer, CustomerProfile, ImportedAddress, ImportRun, Project, Property, Supplier


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


CSV_HEADER = "Adresse;Kunde;Lieferant;Kurzname;Anrede;Titel;Vorname;Name;Name 2;Name 3;Straße;Land;PLZ;Ort;Telefon;Fax;Mobil;Mail;Bemerkung"


def make_csv(rows: list[str]) -> bytes:
    return ("﻿" + "\n".join([CSV_HEADER, *rows])).encode("utf-8")


def customer_row(addr="A-1", kunde="K-1", name="Mustermann", vorname="Max", ort="Aachen", mail="") -> str:
    return f"{addr};{kunde};;Kurz;Herr;;{vorname};{name};;;Musterstr. 1;Deutschland;52070;{ort};02404 66953;;0171 1234567;{mail};"


def supplier_row(addr="A-2", lieferant="L-1", name="Dachbaustoffe GmbH") -> str:
    return f"{addr};;{lieferant};Kurz;Firma;;;{name};;;Lieferweg 2;Deutschland;52070;Aachen;;;;lieferant@example.de;"


def unassigned_row(addr="A-3", name="Interessent", ort="Würselen") -> str:
    return f"{addr};;;Kurz;Frau;;Erika;{name};;;Feldweg 3;Deutschland;52146;{ort};;;;;"


# ---------------------------------------------------------------------------
# Einlesen: CSV und Excel
# ---------------------------------------------------------------------------

def test_parse_csv_reads_required_columns_by_header_name_not_position():
    data = make_csv([customer_row()])
    rows = ai.parse_address_file(data, "adressen.csv")
    assert len(rows) == 1
    r = rows[0]
    assert r["legacy_address_number"] == "A-1"
    assert r["customer_number_raw"] == "K-1"
    assert r["last_name"] == "Mustermann"
    assert r["first_name"] == "Max"
    assert r["city"] == "Aachen"
    assert r["phone"] == "02404 66953"


def test_parse_csv_missing_required_column_raises():
    bad_header = CSV_HEADER.replace("Name;", "")  # entfernt die Spalte "Name"
    data = (bad_header + "\n" + customer_row()).encode("utf-8")
    with pytest.raises(ai.AddressImportError, match="Name"):
        ai.parse_address_file(data, "kaputt.csv")


def test_parse_csv_preserves_broken_phone_numbers_unchanged():
    """Der Excel-Export verliert bei vielen Nummern die führende Null -- der Import darf nichts
    reparieren oder erraten, siehe CLAUDE.md."""
    # Adresse, Kunde, Lieferant, Kurzname, Anrede, Titel, Vorname, Name, Name 2, Name 3, Straße,
    # Land, PLZ, Ort, Telefon, Fax, Mobil, Mail, Bemerkung
    fields = ["A-9", "K-9", "", "", "", "", "", "Kaputt", "", "", "Str. 1", "Deutschland", "52070", "Aachen", "240466953", "", "-373367", "", ""]
    assert len(fields) == len(CSV_HEADER.split(";"))
    data = make_csv([";".join(fields)])
    rows = ai.parse_address_file(data, "adressen.csv")
    assert rows[0]["phone"] == "240466953"
    assert rows[0]["mobile"] == "-373367"


def test_parse_xlsx_reads_same_fields_as_csv():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CSV_HEADER.split(";"))
    ws.append(customer_row().split(";"))
    buf = io.BytesIO()
    wb.save(buf)
    rows = ai.parse_address_file(buf.getvalue(), "adressen.xlsx")
    assert rows[0]["legacy_address_number"] == "A-1"
    assert rows[0]["last_name"] == "Mustermann"


def test_parse_xlsx_formats_whole_number_floats_without_trailing_zero():
    """openpyxl liefert eine Zahlenzelle als float -- '02404 66953' als reine Zahl importiert
    ergibt sonst '2404669530.0' statt '2404669530'."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CSV_HEADER.split(";"))
    row = customer_row().split(";")
    row[14] = 2404669530.0  # Telefon-Spalte als echte Zahl (float, wie openpyxl Zahlenzellen liest)
    ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    rows = ai.parse_address_file(buf.getvalue(), "adressen.xlsx")
    assert rows[0]["phone"] == "2404669530"


def test_unsupported_extension_raises():
    with pytest.raises(ai.AddressImportError):
        ai.parse_address_file(b"irrelevant", "adressen.txt")


# ---------------------------------------------------------------------------
# Klassifikation
# ---------------------------------------------------------------------------

def test_classify_customer_supplier_and_unassigned_rows():
    db = db_session()
    seen = set()
    c, notes_c = ai.classify_row(db, ai.parse_address_file(make_csv([customer_row()]), "x.csv")[0], seen)
    s, notes_s = ai.classify_row(db, ai.parse_address_file(make_csv([supplier_row()]), "x.csv")[0], seen)
    u, notes_u = ai.classify_row(db, ai.parse_address_file(make_csv([unassigned_row()]), "x.csv")[0], seen)
    assert c == "customer" and notes_c == []
    assert s == "supplier" and notes_s == []
    assert u == "unassigned"


def test_classify_flags_missing_name_and_missing_address():
    db = db_session()
    row = ";".join(["A-5"] + [""] * 18)
    assert len(row.split(";")) == len(CSV_HEADER.split(";"))
    parsed = ai.parse_address_file(make_csv([row]), "x.csv")[0]
    classification, notes = ai.classify_row(db, parsed, set())
    assert classification == "unassigned"
    assert any("Kein Name" in n for n in notes)
    assert any("Keine Adresse" in n for n in notes)


def test_classify_flags_duplicate_number_within_same_file():
    db = db_session()
    seen = {"A-1"}
    parsed = ai.parse_address_file(make_csv([customer_row(addr="A-1")]), "x.csv")[0]
    _, notes = ai.classify_row(db, parsed, seen)
    assert any("mehrfach" in n for n in notes)


def test_classify_flags_already_assigned_customer_number():
    db = db_session()
    fn = db.scalars(select(Customer)).all()
    existing = Customer(name="Bestand", last_name="Bestand")
    db.add(existing); db.flush()
    db.add(CustomerProfile(customer_id=existing.id, customer_number="K-1")); db.commit()
    parsed = ai.parse_address_file(make_csv([customer_row(kunde="K-1")]), "x.csv")[0]
    classification, notes = ai.classify_row(db, parsed, set())
    assert classification == "customer"
    assert any("bereits vergeben" in n for n in notes)


# ---------------------------------------------------------------------------
# Dreistufiger Ablauf: Vorschau -> Verwerfen/Bestätigen
# ---------------------------------------------------------------------------

def test_preview_then_discard_writes_nothing():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row(), supplier_row(), unassigned_row()]), "adressen.csv")
    assert db.scalar(select(ImportedAddress.id)) is not None
    ai.discard_pending_preview(db)
    assert db.scalar(select(ImportedAddress.id)) is None
    assert db.scalar(select(Customer.id)) is None


def test_preview_then_confirm_creates_customer_supplier_and_leaves_unassigned_open():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row(), supplier_row(), unassigned_row()]), "adressen.csv")
    run = ai.confirm_import(db, "adressen.csv", employee_id=None)
    assert run.row_count_customers == 1
    assert run.row_count_suppliers == 1
    assert run.row_count_unassigned == 1

    customer = db.scalar(select(Customer).where(Customer.legacy_address_number == "A-1"))
    assert customer is not None
    assert customer.name == "Herr Max Mustermann"
    assert customer.import_run_id == run.id
    assert customer.profile.customer_number == "K-1"
    main_property = db.scalar(select(Property).where(Property.customer_id == customer.id, Property.name == "Hauptadresse"))
    assert main_property is not None
    assert main_property.is_primary_address is True

    supplier = db.scalar(select(Supplier).where(Supplier.legacy_address_number == "A-2"))
    assert supplier is not None
    assert supplier.supplier_number == "L-1"

    open_rows = ai.list_unassigned(db)
    assert len(open_rows) == 1
    assert open_rows[0]["legacy_address_number"] == "A-3"


def test_second_email_is_split_and_stored_informationally():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row(mail="a@example.de,b@example.de")]), "adressen.csv")
    ai.confirm_import(db, "adressen.csv", employee_id=None)
    customer = db.scalar(select(Customer).where(Customer.legacy_address_number == "A-1"))
    assert customer.email == "a@example.de"
    assert customer.email_2 == "b@example.de"


def test_reimporting_the_same_file_skips_already_imported_rows():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row()]), "adressen.csv")
    ai.confirm_import(db, "adressen.csv", employee_id=None)
    assert db.scalar(select(Customer.id).where(Customer.legacy_address_number == "A-1")) is not None

    preview = ai.create_preview(db, make_csv([customer_row()]), "adressen.csv")
    assert preview["counts"]["duplicate"] == 1
    assert preview["counts"]["customer"] == 0
    # Bestaetigen einer reinen Duplikat-Vorschau legt nichts doppelt an.
    run = ai.confirm_import(db, "adressen.csv", employee_id=None)
    assert run.row_count_skipped_duplicates == 1
    assert db.scalar(select(Customer.id)) is not None
    count = len(db.scalars(select(Customer)).all())
    assert count == 1


def test_starting_a_new_preview_discards_a_never_confirmed_one_without_blocking_the_number():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row()]), "adressen_v1.csv")
    # Nie bestaetigt -- ein zweiter Upload derselben Adressnummer darf NICHT als Duplikat gelten.
    preview = ai.create_preview(db, make_csv([customer_row()]), "adressen_v2.csv")
    assert preview["counts"]["customer"] == 1
    assert preview["counts"]["duplicate"] == 0


# ---------------------------------------------------------------------------
# Arbeitsliste
# ---------------------------------------------------------------------------

def test_worklist_search_filters_by_name_and_city():
    db = db_session()
    ai.create_preview(db, make_csv([unassigned_row(addr="A-3", name="Interessent", ort="Würselen"), unassigned_row(addr="A-4", name="Anders", ort="Stolberg")]), "adressen.csv")
    ai.confirm_import(db, "adressen.csv", employee_id=None)
    assert len(ai.list_unassigned(db)) == 2
    assert len(ai.list_unassigned(db, "würselen")) == 1
    assert len(ai.list_unassigned(db, "stolberg")) == 1
    assert len(ai.list_unassigned(db, "nirgendwo")) == 0


def test_worklist_row_can_be_created_as_new_customer():
    db = db_session()
    ai.create_preview(db, make_csv([unassigned_row()]), "adressen.csv")
    ai.confirm_import(db, "adressen.csv", employee_id=None)
    entry = ai.list_unassigned(db)[0]
    customer = ai.resolve_as_new_customer(db, entry["id"])
    assert customer.last_name == "Interessent"
    assert ai.list_unassigned(db) == []


def test_worklist_row_can_be_assigned_as_property_of_existing_customer():
    db = db_session()
    existing = Customer(name="Bestandskunde", last_name="Bestandskunde")
    db.add(existing); db.commit()
    ai.create_preview(db, make_csv([unassigned_row()]), "adressen.csv")
    ai.confirm_import(db, "adressen.csv", employee_id=None)
    entry = ai.list_unassigned(db)[0]
    prop = ai.resolve_as_property(db, entry["id"], existing.id)
    assert prop.customer_id == existing.id
    assert prop.street == "Feldweg 3"
    assert ai.list_unassigned(db) == []


def test_worklist_row_can_be_discarded():
    db = db_session()
    ai.create_preview(db, make_csv([unassigned_row()]), "adressen.csv")
    ai.confirm_import(db, "adressen.csv", employee_id=None)
    entry = ai.list_unassigned(db)[0]
    ai.discard_unassigned(db, entry["id"])
    assert ai.list_unassigned(db) == []
    assert db.scalar(select(Customer.id)) is None  # nichts angelegt


# ---------------------------------------------------------------------------
# Rückgängig machen
# ---------------------------------------------------------------------------

def test_revert_deletes_untouched_customers_and_suppliers():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row(), supplier_row()]), "adressen.csv")
    run = ai.confirm_import(db, "adressen.csv", employee_id=None)
    runs = ai.list_import_runs(db)
    assert runs[0]["can_revert"] is True

    ai.revert_import_run(db, run.id)
    assert db.scalar(select(Customer.id)) is None
    assert db.scalar(select(Supplier.id)) is None
    reverted = db.get(ImportRun, run.id)
    assert reverted.status == "reverted"
    assert reverted.reverted_at is not None


def test_revert_refused_when_a_created_customer_already_has_a_project():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row()]), "adressen.csv")
    run = ai.confirm_import(db, "adressen.csv", employee_id=None)
    customer = db.scalar(select(Customer).where(Customer.import_run_id == run.id))
    db.add(Project(customer_id=customer.id, project_number="P-TEST-1", name="Dachsanierung")); db.commit()

    runs = ai.list_import_runs(db)
    assert runs[0]["can_revert"] is False
    with pytest.raises(ValueError):
        ai.revert_import_run(db, run.id)
    # Nichts geloescht.
    assert db.scalar(select(Customer.id)) is not None


def test_revert_refused_when_a_worklist_row_from_the_run_was_already_resolved():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row(), unassigned_row()]), "adressen.csv")
    run = ai.confirm_import(db, "adressen.csv", employee_id=None)
    entry = ai.list_unassigned(db)[0]
    ai.resolve_as_new_customer(db, entry["id"])

    assert ai.list_import_runs(db)[0]["can_revert"] is False
    with pytest.raises(ValueError):
        ai.revert_import_run(db, run.id)


def test_reverted_run_frees_the_legacy_address_number_for_a_future_import():
    db = db_session()
    ai.create_preview(db, make_csv([customer_row()]), "adressen.csv")
    run = ai.confirm_import(db, "adressen.csv", employee_id=None)
    ai.revert_import_run(db, run.id)

    preview = ai.create_preview(db, make_csv([customer_row()]), "adressen.csv")
    assert preview["counts"]["customer"] == 1
    assert preview["counts"]["duplicate"] == 0


# ---------------------------------------------------------------------------
# Echte Routen (Upload/Vorschau/Bestätigen/Rückgängig), über router_test_client()
# ---------------------------------------------------------------------------

def test_upload_preview_confirm_and_revert_over_real_routes(threaded_db_session, router_test_client):
    from app.routers.address_import import router as address_import_router

    db = threaded_db_session
    client = router_test_client(db, address_import_router)

    files = {"file": ("adressen.csv", make_csv([customer_row()]), "text/csv")}
    preview = client.post("/api/address-import/upload", files=files).json()
    assert preview["counts"]["customer"] == 1

    confirmed = client.post("/api/address-import/confirm", params={"filename": "adressen.csv"}).json()
    assert confirmed["row_count_customers"] == 1

    runs = client.get("/api/address-import/runs").json()
    assert len(runs) == 1 and runs[0]["can_revert"] is True

    reverted = client.post(f"/api/address-import/runs/{runs[0]['id']}/revert")
    assert reverted.status_code == 200
    assert db.scalar(select(Customer.id)) is None
