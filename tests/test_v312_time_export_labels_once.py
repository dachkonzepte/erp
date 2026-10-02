"""Version 1.8.8 -- Stundenzettel und CSV-Export laden die Bezeichnungen der Zeitarten einmal je Lauf.

Bis 1.8.7 übersetzte _entry_type_label() die Zeitart je Zeile und lud dafür jedes Mal die
Optionsgruppe neu (get_option_group() -> ensure_default_option_groups(), fünf Abfragen je
Buchung); seit 1.8.7 ohne Kappung wuchs das mit dem Zeitraum. Zwei sonst gleiche Datenbanken mit
10 und 2001 Buchungen, jede Zeitart in beiden. Jeder Lauf in einer frischen Session, damit die
Identity Map keinen der beiden bevorzugt. Die Standardgruppen sind vorab gesät: gemessen wird der
Normalbetrieb, nicht das einmalige Anlegen.

Seit 1.8.42 legt der Start die Standardgruppen an (app/grunddaten.py, in Tests create_all()), kein
Lesepfad mehr -- der Lauf schreibt nichts, statt höchstens einmal anzulegen."""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee, SettingOption, SettingOptionGroup, TimeEntry
from app.time_backoffice import build_time_csv, build_timesheet_pdf
from tests.test_v133_invoices import make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text

START, END = date(2026, 1, 1), date(2026, 12, 31)
ENTRY_TYPES = ["site", "travel", "workshop", "other", "weather_winter", "weather_summer"]
EXPECTED_LABELS = {
    "Baustelle Dach", "Fahrzeit", "Werkstattzeit", "Sonstige Arbeitszeit",
    "Schlechtwetter Winter", "Schlechtwetter Sommer",
}


def _database(count):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    order, item = make_order_with_item(db)
    emp = Employee(employee_number="T-1", first_name="Max", last_name="Muster",
                   employee_group="gewerblich", hourly_wage="25", active=True)
    db.add(emp); db.commit()
    # Umbenannt, damit die Tests die Optionsgruppe sehen und nicht die gleichlautenden Rückfallwerte.
    db.scalar(select(SettingOption).join(SettingOptionGroup).where(
        SettingOptionGroup.group_key == "time_entry_types", SettingOption.value == "site",
    )).label = "Baustelle Dach"
    db.add_all(
        TimeEntry(employee_id=emp.id, project_id=order.project_id, order_id=order.id, order_item_id=item.id,
                  work_date=START + timedelta(days=i % 365), entry_type=ENTRY_TYPES[i % len(ENTRY_TYPES)],
                  activity="Reparatur", hours=Decimal("1.00"), status="booked")
        for i in range(count)
    )
    db.commit(); db.close()
    return engine


@pytest.fixture(scope="module")
def engines():
    # Einmal je Modul statt je Test, damit 2001 Buchungen die Suite nicht spürbar verlangsamen.
    # Kein Test ändert Daten.
    engines = {count: _database(count) for count in (10, 2001)}
    yield engines
    for engine in engines.values():
        engine.dispose()


def _run(engine, build):
    """Ein Lauf in frischer Session: Zahl der Abfragen, Zahl der schreibenden davon."""
    queries = []

    def count(conn, cursor, statement, *args):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    db = sessionmaker(bind=engine)()
    try:
        build(db, START, END)
    finally:
        db.close()
        event.remove(engine, "before_cursor_execute", count)
    writes = [q for q in queries if q.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    return len(queries), len(writes)


@pytest.mark.parametrize("build", [build_timesheet_pdf, build_time_csv], ids=["stundenzettel", "csv"])
def test_query_count_same_for_10_and_2001_entries(engines, build):
    few_queries, few_writes = _run(engines[10], build)
    many_queries, many_writes = _run(engines[2001], build)
    assert few_queries == many_queries
    assert few_writes == many_writes == 0


def test_labels_come_from_option_group(engines):
    db = sessionmaker(bind=engines[10])()
    try:
        rows = csv.DictReader(io.StringIO(build_time_csv(db, START, END).decode("utf-8-sig")), delimiter=";")
        assert {row["Zeitart"] for row in rows} == EXPECTED_LABELS
        text = _extract_pdf_text(build_timesheet_pdf(db, START, END))
        assert all(label.encode() in text for label in EXPECTED_LABELS)
    finally:
        db.close()
