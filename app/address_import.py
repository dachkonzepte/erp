"""Adressimport aus dem Altsystem -- siehe CLAUDE.md "Adressimport aus dem Altsystem" für die
vollständige Herleitung (Spaltenzuordnung, Entscheidungen zu name/last_name, Land, Mobil,
zweiter E-Mail-Adresse, Rückgängigmachen).

Dreistufiger Ablauf, absichtlich ohne Zwischenspeicherung der Rohdatei: Hochladen parst die Datei
sofort vollständig und legt für jede Zeile eine ImportedAddress mit status="previewing" an (ohne
ImportRun -- der entsteht erst bei der Bestätigung). Die Vorschau liest ausschließlich diese
bereits gespeicherten Zeilen zurück. Bestätigen schreibt Customer/Supplier für die entsprechend
klassifizierten Zeilen und setzt status="confirmed". Verwerfen löscht die Vorschau-Zeilen wieder,
ohne dass irgendetwas an anderer Stelle entstanden wäre."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .crm import compose_customer_name, ensure_customer_profile
from .models import Customer, CustomerProfile, ImportedAddress, ImportRun, Property, Supplier

# Exakte Spaltennamen aus dem Altsystem-Export (19 Spalten insgesamt). Kurzname/Name 2/Name 3/
# Bemerkung werden bewusst nicht gelesen -- sie entfallen laut Vorgabe vollständig.
REQUIRED_HEADERS = [
    "Adresse", "Kunde", "Lieferant", "Anrede", "Titel", "Vorname", "Name",
    "Straße", "Land", "PLZ", "Ort", "Telefon", "Fax", "Mobil", "Mail",
]


class AddressImportError(ValueError):
    """Fehler beim Einlesen der Datei selbst (Format/fehlende Spalten) -- betrifft die ganze
    Datei, nicht nur eine Zeile."""


def _decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AddressImportError("Die Datei konnte nicht gelesen werden (unbekannte Zeichenkodierung).")


def _read_csv_rows(data: bytes) -> tuple[list[str], list[list[str | None]]]:
    text = _decode_csv_bytes(data)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), dialect)
    all_rows = [row for row in reader if any((cell or "").strip() for cell in row)]
    if not all_rows:
        raise AddressImportError("Die Datei enthält keine Zeilen.")
    return all_rows[0], all_rows[1:]


def _format_excel_cell(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    text = str(value).strip()
    return text or None


def _read_xlsx_rows(data: bytes) -> tuple[list[str], list[list[str | None]]]:
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    worksheet = workbook.worksheets[0]
    rows_iter = worksheet.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        raise AddressImportError("Die Datei enthält keine Zeilen.")
    headers = [(_format_excel_cell(h) or "").strip() for h in header_row]
    rows: list[list[str | None]] = []
    for raw_row in rows_iter:
        if all(v is None for v in raw_row):
            continue
        rows.append([_format_excel_cell(v) for v in raw_row])
    return headers, rows


def parse_address_file(data: bytes, filename: str) -> list[dict]:
    """Liest CSV oder Excel (.xlsx) anhand der Spaltenüberschriften ein (nicht anhand der
    Spaltenreihenfolge) und liefert je Zeile ein Rohdaten-Dict. Wirft AddressImportError, wenn
    das Format nicht unterstützt wird oder eine benötigte Spalte fehlt -- beides betrifft die
    ganze Datei."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        headers, raw_rows = _read_csv_rows(data)
    elif ext in ("xlsx", "xlsm"):
        headers, raw_rows = _read_xlsx_rows(data)
    else:
        raise AddressImportError("Nicht unterstütztes Dateiformat -- bitte CSV oder Excel (.xlsx) hochladen.")

    headers = [(h or "").strip() for h in headers]
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise AddressImportError("Diese Spalten fehlen in der Datei: " + ", ".join(missing))
    index = {h: i for i, h in enumerate(headers)}

    def cell(row: list, name: str) -> str | None:
        i = index.get(name)
        if i is None or i >= len(row):
            return None
        value = row[i]
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    rows = []
    for row_number, raw_row in enumerate(raw_rows, start=2):  # Zeile 1 ist die Kopfzeile.
        rows.append({
            "row_number": row_number,
            "legacy_address_number": cell(raw_row, "Adresse"),
            "customer_number_raw": cell(raw_row, "Kunde"),
            "supplier_number_raw": cell(raw_row, "Lieferant"),
            "salutation": cell(raw_row, "Anrede"),
            "title": cell(raw_row, "Titel"),
            "first_name": cell(raw_row, "Vorname"),
            "last_name": cell(raw_row, "Name"),
            "street": cell(raw_row, "Straße"),
            "country": cell(raw_row, "Land"),
            "postal_code": cell(raw_row, "PLZ"),
            "city": cell(raw_row, "Ort"),
            "phone": cell(raw_row, "Telefon"),
            "fax": cell(raw_row, "Fax"),
            "mobile": cell(raw_row, "Mobil"),
            "email_raw": cell(raw_row, "Mail"),
        })
    return rows


def split_emails(raw: str | None) -> tuple[str | None, str | None]:
    """Die Spalte "Mail" trägt manchmal zwei durch Komma getrennte Adressen -- beide werden
    übernommen, die zweite in Customer.email_2 (rein informativ, siehe CLAUDE.md)."""
    if not raw:
        return None, None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None, None
    return parts[0], (parts[1] if len(parts) > 1 else None)


def _address_already_imported(db: Session, legacy_address_number: str) -> bool:
    return (
        db.scalar(select(Customer.id).where(Customer.legacy_address_number == legacy_address_number)) is not None
        or db.scalar(select(Supplier.id).where(Supplier.legacy_address_number == legacy_address_number)) is not None
        or db.scalar(
            select(ImportedAddress.id).where(
                ImportedAddress.legacy_address_number == legacy_address_number,
                ImportedAddress.status == "confirmed",
            )
        )
        is not None
    )


def classify_row(db: Session, row: dict, seen_numbers: set[str]) -> tuple[str, list[str]]:
    """Klassifiziert eine Rohzeile und sammelt auffällige Punkte für die Vorschau. seen_numbers
    sammelt bereits in DERSELBEN Datei gesehene Adressnummern (Dublette innerhalb der Datei
    selbst, unabhängig von bereits importierten Adressnummern)."""
    notes: list[str] = []
    number = row["legacy_address_number"]
    if not number:
        notes.append("Keine Adressnummer -- bei einem erneuten Import nicht wiederzuerkennen.")
    elif number in seen_numbers:
        notes.append("Adressnummer kommt mehrfach in dieser Datei vor.")
    if number and _address_already_imported(db, number):
        notes.append("Adressnummer wurde bereits importiert -- wird übersprungen.")
        return "duplicate", notes

    if not row["last_name"] and not row["first_name"]:
        notes.append("Kein Name vorhanden.")
    if not row["street"] and not row["postal_code"] and not row["city"]:
        notes.append("Keine Adresse vorhanden.")

    if row["customer_number_raw"]:
        if db.scalar(select(CustomerProfile.id).where(CustomerProfile.customer_number == row["customer_number_raw"])):
            notes.append(f"Kundennummer {row['customer_number_raw']} ist bereits vergeben.")
        return "customer", notes
    if row["supplier_number_raw"]:
        if db.scalar(select(Supplier.id).where(Supplier.supplier_number == row["supplier_number_raw"])):
            notes.append(f"Lieferantennummer {row['supplier_number_raw']} ist bereits vergeben.")
        return "supplier", notes
    return "unassigned", notes


def create_preview(db: Session, data: bytes, filename: str) -> dict:
    """Parst die Datei, klassifiziert jede Zeile und legt sie als ImportedAddress mit
    status="previewing" ab -- ohne ImportRun (der entsteht erst beim Bestätigen). Eine bereits
    bestehende, nie bestätigte Vorschau wird vorher verworfen, damit stets nur eine "offene"
    Vorschau existiert und Adressnummern aus abgebrochenen Vorschauen nie fälschlich als bereits
    importiert gelten."""
    discard_pending_preview(db)

    rows = parse_address_file(data, filename)
    seen_numbers: set[str] = set()
    created_ids = []
    for row in rows:
        classification, notes = classify_row(db, row, seen_numbers)
        if row["legacy_address_number"]:
            seen_numbers.add(row["legacy_address_number"])
        email, email_2 = split_emails(row["email_raw"])
        entry = ImportedAddress(
            import_run_id=None,
            row_number=row["row_number"],
            legacy_address_number=row["legacy_address_number"],
            customer_number_raw=row["customer_number_raw"],
            supplier_number_raw=row["supplier_number_raw"],
            salutation=row["salutation"],
            title=row["title"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            street=row["street"],
            country=row["country"],
            postal_code=row["postal_code"],
            city=row["city"],
            phone=row["phone"],
            fax=row["fax"],
            mobile=row["mobile"],
            email=email,
            email_2=email_2,
            classification=classification,
            status="previewing",
            validation_notes="; ".join(notes) or None,
        )
        db.add(entry)
        db.flush()
        created_ids.append(entry.id)
    db.commit()

    return summarize_preview(db, created_ids, filename)


def summarize_preview(db: Session, ids: list[int], filename: str) -> dict:
    entries = db.scalars(select(ImportedAddress).where(ImportedAddress.id.in_(ids)).order_by(ImportedAddress.row_number)).all() if ids else []
    counts = {"customer": 0, "supplier": 0, "unassigned": 0, "duplicate": 0}
    for e in entries:
        counts[e.classification] = counts.get(e.classification, 0) + 1
    return {
        "filename": filename,
        "total": len(entries),
        "counts": counts,
        "rows": [_row_to_dict(e) for e in entries],
    }


def get_pending_preview(db: Session) -> dict | None:
    entries = db.scalars(select(ImportedAddress).where(ImportedAddress.status == "previewing").order_by(ImportedAddress.row_number)).all()
    if not entries:
        return None
    counts = {"customer": 0, "supplier": 0, "unassigned": 0, "duplicate": 0}
    for e in entries:
        counts[e.classification] = counts.get(e.classification, 0) + 1
    return {"total": len(entries), "counts": counts, "rows": [_row_to_dict(e) for e in entries]}


def discard_pending_preview(db: Session) -> None:
    pending = db.scalars(select(ImportedAddress).where(ImportedAddress.status == "previewing")).all()
    for entry in pending:
        db.delete(entry)
    if pending:
        db.commit()


def _row_to_dict(e: ImportedAddress) -> dict:
    return {
        "id": e.id,
        "row_number": e.row_number,
        "legacy_address_number": e.legacy_address_number,
        "customer_number_raw": e.customer_number_raw,
        "supplier_number_raw": e.supplier_number_raw,
        "salutation": e.salutation,
        "title": e.title,
        "first_name": e.first_name,
        "last_name": e.last_name,
        "street": e.street,
        "country": e.country,
        "postal_code": e.postal_code,
        "city": e.city,
        "phone": e.phone,
        "fax": e.fax,
        "mobile": e.mobile,
        "email": e.email,
        "email_2": e.email_2,
        "classification": e.classification,
        "validation_notes": e.validation_notes,
        "resolution": e.resolution,
    }


def confirm_import(db: Session, filename: str, employee_id: int | None) -> ImportRun:
    """Schreibt die aktuelle Vorschau tatsächlich: legt für classification="customer"/"supplier"
    die jeweiligen Stammdaten an, lässt "unassigned" als offene Zeile in der Arbeitsliste stehen
    und "duplicate" unverändert (nur als Nachweis, dass diese Adressnummer erneut vorkam)."""
    pending = db.scalars(select(ImportedAddress).where(ImportedAddress.status == "previewing").order_by(ImportedAddress.row_number)).all()
    if not pending:
        raise ValueError("Es liegt keine offene Vorschau vor.")

    run = ImportRun(source_filename=filename, created_by_employee_id=employee_id)
    db.add(run)
    db.flush()

    counts = {"customer": 0, "supplier": 0, "unassigned": 0, "duplicate": 0}
    for entry in pending:
        entry.import_run_id = run.id
        entry.status = "confirmed"
        counts[entry.classification] = counts.get(entry.classification, 0) + 1
        try:
            if entry.classification == "customer":
                customer = _create_customer_from_row(db, entry)
                entry.created_customer_id = customer.id
            elif entry.classification == "supplier":
                supplier = _create_supplier_from_row(db, entry)
                entry.created_supplier_id = supplier.id
        except ValueError as exc:
            db.rollback()
            raise ValueError(f"Zeile {entry.row_number}: {exc}") from exc

    run.row_count_total = len(pending)
    run.row_count_customers = counts["customer"]
    run.row_count_suppliers = counts["supplier"]
    run.row_count_unassigned = counts["unassigned"]
    run.row_count_skipped_duplicates = counts["duplicate"]
    db.commit()
    return run


def _create_customer_from_row(db: Session, entry: ImportedAddress) -> Customer:
    name = compose_customer_name(entry.salutation, entry.title, entry.first_name, entry.last_name or "")
    customer = Customer(
        salutation=entry.salutation, title=entry.title, first_name=entry.first_name,
        last_name=entry.last_name or name or "Unbekannt", name=name or entry.last_name or "Unbekannt",
        street=entry.street, country=entry.country or "Deutschland", postal_code=entry.postal_code,
        city=entry.city, email=entry.email, email_2=entry.email_2, phone=entry.phone,
        mobile=entry.mobile, fax=entry.fax, legacy_address_number=entry.legacy_address_number,
        import_run_id=entry.import_run_id,
    )
    db.add(customer)
    db.flush()
    ensure_customer_profile(db, customer, "Privatkunde", entry.customer_number_raw)
    main_property = Property(
        customer_id=customer.id, name="Hauptadresse", street=customer.street,
        postal_code=customer.postal_code, city=customer.city, country=customer.country,
        notes="Automatisch aus der Kunden-Hauptadresse angelegt.",
        is_primary_address=True,
    )
    db.add(main_property)
    db.flush()
    return customer


def _create_supplier_from_row(db: Session, entry: ImportedAddress) -> Supplier:
    name = compose_customer_name(entry.salutation, entry.title, entry.first_name, entry.last_name or "") or entry.last_name or "Unbekannt"
    supplier = Supplier(
        supplier_number=entry.supplier_number_raw, name=name, street=entry.street,
        postal_code=entry.postal_code, city=entry.city, country=entry.country or "Deutschland",
        phone=entry.phone, email=entry.email, legacy_address_number=entry.legacy_address_number,
        import_run_id=entry.import_run_id,
    )
    db.add(supplier)
    db.flush()
    return supplier


def list_import_runs(db: Session) -> list[dict]:
    runs = db.scalars(select(ImportRun).order_by(ImportRun.created_at.desc())).all()
    return [
        {
            "id": r.id, "source_filename": r.source_filename, "created_at": r.created_at,
            "status": r.status, "reverted_at": r.reverted_at,
            "row_count_total": r.row_count_total, "row_count_customers": r.row_count_customers,
            "row_count_suppliers": r.row_count_suppliers, "row_count_unassigned": r.row_count_unassigned,
            "row_count_skipped_duplicates": r.row_count_skipped_duplicates,
            "can_revert": r.status == "completed" and _run_is_untouched(db, r),
        }
        for r in runs
    ]


def _run_is_untouched(db: Session, run: ImportRun) -> bool:
    """Alles-oder-nichts-Voraussetzung fürs Rückgängigmachen: JEDER durch den Lauf erzeugte
    Kunde/Lieferant darf noch keine eigene Verwendung haben, UND jede seiner offen gebliebenen
    Arbeitslisten-Zeilen darf noch nicht aufgelöst worden sein."""
    from .models import Inquiry, Project

    customers = db.scalars(select(Customer).where(Customer.import_run_id == run.id)).all()
    for customer in customers:
        has_project = db.scalar(select(Project.id).where(Project.customer_id == customer.id)) is not None
        has_inquiry = db.scalar(select(Inquiry.id).where(Inquiry.customer_id == customer.id)) is not None
        if has_project or has_inquiry:
            return False
        extra_properties = [p for p in customer.properties if p.name != "Hauptadresse"]
        if extra_properties:
            return False

    from .models import WorkPreparationDeliveryNote, WorkPreparationMaterialSupplier
    suppliers = db.scalars(select(Supplier).where(Supplier.import_run_id == run.id)).all()
    for supplier in suppliers:
        used = (
            db.scalar(select(WorkPreparationMaterialSupplier.id).where(WorkPreparationMaterialSupplier.supplier_id == supplier.id)) is not None
            or db.scalar(select(WorkPreparationDeliveryNote.id).where(WorkPreparationDeliveryNote.supplier_id == supplier.id)) is not None
        )
        if used:
            return False

    unresolved_but_touched = db.scalar(
        select(ImportedAddress.id).where(
            ImportedAddress.import_run_id == run.id,
            ImportedAddress.classification == "unassigned",
            ImportedAddress.resolution.is_not(None),
        )
    )
    if unresolved_but_touched is not None:
        return False
    return True


def revert_import_run(db: Session, run_id: int) -> None:
    run = db.get(ImportRun, run_id)
    if run is None:
        raise ValueError("Importlauf nicht gefunden.")
    if run.status != "completed":
        raise ValueError("Dieser Lauf ist bereits rückgängig gemacht.")
    if not _run_is_untouched(db, run):
        raise ValueError(
            "Dieser Lauf kann nicht rückgängig gemacht werden -- an mindestens einem dabei "
            "erzeugten Kunden/Lieferanten hängt bereits etwas, oder eine Zeile der Arbeitsliste "
            "wurde bereits bearbeitet."
        )
    customers = db.scalars(select(Customer).where(Customer.import_run_id == run.id)).all()
    for customer in customers:
        db.delete(customer)
    suppliers = db.scalars(select(Supplier).where(Supplier.import_run_id == run.id)).all()
    for supplier in suppliers:
        db.delete(supplier)
    rows = db.scalars(select(ImportedAddress).where(ImportedAddress.import_run_id == run.id)).all()
    for row in rows:
        db.delete(row)
    run.status = "reverted"
    run.reverted_at = datetime.utcnow()
    db.commit()


def list_unassigned(db: Session, search: str | None = None) -> list[dict]:
    """Die Arbeitsliste aus CLAUDE.md "Adressimport aus dem Altsystem": offene, nicht
    zuordenbare Zeilen (resolution ist noch nicht gesetzt)."""
    stmt = select(ImportedAddress).where(
        ImportedAddress.classification == "unassigned",
        ImportedAddress.status == "confirmed",
        ImportedAddress.resolution.is_(None),
    ).order_by(ImportedAddress.id.desc())
    rows = db.scalars(stmt).all()
    if search:
        q = search.strip().lower()
        if q:
            def matches(r: ImportedAddress) -> bool:
                fields = [r.first_name, r.last_name, r.street, r.city, r.postal_code, r.email, r.phone, r.legacy_address_number]
                return any(q in (f or "").lower() for f in fields)
            rows = [r for r in rows if matches(r)]
    return [_row_to_dict(r) for r in rows]


def resolve_as_new_customer(db: Session, entry_id: int) -> Customer:
    entry = _get_open_unassigned(db, entry_id)
    customer = _create_customer_from_row(db, entry)
    entry.resolution = "created_as_customer"
    entry.resolved_at = datetime.utcnow()
    entry.created_customer_id = customer.id
    db.commit()
    return customer


def resolve_as_property(db: Session, entry_id: int, customer_id: int) -> Property:
    entry = _get_open_unassigned(db, entry_id)
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ValueError("Kunde nicht gefunden.")
    name_parts = [p for p in [entry.street] if p]
    property_name = entry.street or f"Objekt aus Adressimport {entry.legacy_address_number or entry.id}"
    prop = Property(
        customer_id=customer.id, name=property_name, street=entry.street,
        postal_code=entry.postal_code, city=entry.city, country=entry.country,
        notes=f"Aus Adressimport übernommen (Altsystem-Adressnummer {entry.legacy_address_number or '–'}).",
    )
    db.add(prop)
    db.flush()
    entry.resolution = "assigned_as_property"
    entry.resolved_at = datetime.utcnow()
    entry.created_property_id = prop.id
    db.commit()
    return prop


def discard_unassigned(db: Session, entry_id: int) -> None:
    entry = _get_open_unassigned(db, entry_id)
    entry.resolution = "discarded"
    entry.resolved_at = datetime.utcnow()
    db.commit()


def _get_open_unassigned(db: Session, entry_id: int) -> ImportedAddress:
    entry = db.get(ImportedAddress, entry_id)
    if entry is None or entry.classification != "unassigned" or entry.resolution is not None:
        raise ValueError("Diese Zeile ist nicht (mehr) offen.")
    return entry
