"""Version 1.8.7 -- Einsatzbericht-PDF und Backoffice schneiden Zeitbuchungen nicht mehr still ab.

Bis 1.8.6 zeigte das Einsatzbericht-PDF ab 501 Buchungen am Auftrag nur die neuesten 500
(Vorgabewert von list_entries()); Stundenübersicht, Stundenzettel, CSV- und DATEV-Export im
Backoffice kappten bei 2000 Buchungen im Zeitraum. Ein gemeinsamer Datensatz für alle fünf
Stellen, jeweils genau Grenze+1: 501 Buchungen an Auftrag A, 2001 im Zeitraum. Die älteste
Buchung trägt eine eigene Tätigkeit -- list_entries() sortiert neueste zuerst, genau diese Zeile
fiel bisher hinter die Grenze."""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee, EmployeePayrollSettings, Order, TimeEntry
from app.service_report_pdf import build_service_report_pdf
from app.service_reports import _load as _load_report, create_report, sign_report
from app.time_backoffice import (
    backoffice_summary, build_datev_export, build_time_csv, build_timesheet_pdf, get_or_create_time_settings,
)
from tests.test_v133_invoices import make_order_with_item
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text

OLDEST = "Erste Begehung"
START, END = date(2026, 1, 1), date(2026, 12, 31)


@pytest.fixture(scope="module")
def bookings():
    # Einmal je Modul statt je Test, damit 2001 Buchungen die Suite nicht spürbar verlangsamen.
    # Kein Test ändert Buchungen.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    order_a, _ = make_order_with_item(db)
    order_b = Order(order_number="AUF-TEST-0002", project_id=order_a.project_id, source_quote_id=2,
                    quote_number_snapshot="A-TEST-0002", title="Zweiter Auftrag", customer_name="Test Kunde")
    emp = Employee(employee_number="T-1", first_name="Max", last_name="Muster",
                   employee_group="gewerblich", hourly_wage="25", active=True)
    db.add_all([order_b, emp]); db.commit()
    db.add(EmployeePayrollSettings(employee_id=emp.id, datev_personnel_number="1001", payroll_export_enabled=True))
    get_or_create_time_settings(db).datev_wage_type_site = "1000"

    def booking(order, work_date, activity="Reparatur"):
        return TimeEntry(employee_id=emp.id, project_id=order.project_id, order_id=order.id,
                         work_date=work_date, activity=activity, hours=Decimal("1.00"), status="booked")

    db.add(booking(order_a, START, OLDEST))
    db.add_all(booking(order_a if i < 500 else order_b, START + timedelta(days=1 + i // 10)) for i in range(2000))
    db.commit()

    report = create_report(db, order_a.id, "rapport", description="Dach kontrolliert.")
    sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test",
                customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann")
    yield SimpleNamespace(db=db, report_id=report["id"])
    db.close()
    engine.dispose()


def test_service_report_pdf_lists_all_501_entries_of_order(bookings):
    pdf = build_service_report_pdf(bookings.db, _load_report(bookings.db, bookings.report_id))
    assert OLDEST.encode() in _extract_pdf_text(pdf)


def test_backoffice_summary_counts_all_2001_entries(bookings):
    summary = backoffice_summary(bookings.db, START, END)
    assert summary["entry_count"] == 2001
    assert summary["total_hours"] == Decimal("2001")


def test_timesheet_pdf_sums_all_2001_entries(bookings):
    assert b"2001,00" in _extract_pdf_text(build_timesheet_pdf(bookings.db, START, END))  # Summenzeile


def test_time_csv_contains_all_2001_entries(bookings):
    rows = list(csv.reader(io.StringIO(build_time_csv(bookings.db, START, END).decode("utf-8-sig")), delimiter=";"))
    assert len(rows) == 1 + 2001  # Kopfzeile + jede Buchung
    assert any(OLDEST in row for row in rows)


def test_datev_export_contains_all_2001_hours(bookings):
    content, fmt, warnings = build_datev_export(bookings.db, START, END)
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter=";"))
    assert fmt == "csv" and warnings == []
    assert sum(Decimal(r["Stundenanzahl"].replace(",", ".")) for r in rows) == Decimal("2001")
