from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee
from app.time_backoffice import (
    get_or_create_time_settings, time_settings_dict, get_employee_payroll,
    backoffice_summary, build_timesheet_pdf, build_time_csv, build_datev_export,
)
from app.time_tracking import create_manual_entry
from tests.test_v100_time_tracking import setup_order


def db_session():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_backoffice_summary_pdf_csv_and_datev_export():
    db=db_session();order=setup_order(db)
    emp=Employee(employee_number="MA-10",first_name="Max",last_name="Lohn",employee_group="gewerblich",hourly_wage=Decimal("22"),weekly_hours=Decimal("40"),active=True)
    db.add(emp);db.commit();db.refresh(emp)
    create_manual_entry(db,employee_id=emp.id,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("8"),entry_type="site",activity="Dacharbeiten")
    create_manual_entry(db,employee_id=emp.id,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("1"),entry_type="travel",activity="Anfahrt")
    s=backoffice_summary(db,date(2026,9,1),date(2026,9,30))
    assert s["total_hours"]==Decimal("9.00") and s["travel_hours"]==Decimal("1.00")
    assert build_timesheet_pdf(db,date(2026,9,1),date(2026,9,30)).startswith(b"%PDF")
    assert b"Mitarbeiter" in build_time_csv(db,date(2026,9,1),date(2026,9,30))
    p=get_employee_payroll(db,emp.id);p.datev_personnel_number="14";db.commit()
    ts=get_or_create_time_settings(db);ts.datev_target="lohn_gehalt";ts.datev_wage_type_site="200";ts.datev_wage_type_travel="201";db.commit()
    data,ext,warnings=build_datev_export(db,date(2026,9,1),date(2026,9,30))
    text=data.decode("utf-8-sig")
    assert ext=="csv" and "Personalnummer" in text and ";14;" not in text  # number is first field on data row
    assert "14;Max Lohn" in text and not warnings


def test_time_settings_default_and_backoffice_ui_structure():
    db=db_session();row=get_or_create_time_settings(db);d=time_settings_dict(row)
    assert d["allow_manual_entries"] is True and d["allow_group_bookings"] is True
    root=Path(__file__).parents[1]
    html=(root/"app/templates/time_backoffice.html").read_text(encoding="utf-8")
    settings_html=(root/"app/templates/settings.html").read_text(encoding="utf-8")
    main=(root/"app/main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root/"app/routers").glob("*.py")))
    assert "Zeiterfassungs-Backoffice" in html and "DATEV / Lohn" in html and "Stundenzettel" in html
    assert "/api/time-backoffice/datev-export" in main and "Nur Administratoren" in main
    assert "Zeiterfassungs-Backoffice" in settings_html
    assert re.match(r"^\d+\.\d+\.\d+$", (root/"VERSION").read_text(encoding="utf-8").strip())
