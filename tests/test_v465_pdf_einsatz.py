"""Seit 1.9.37 (Stufe 4, R1, Punkt 4): das PDF des Einsatzberichts zeigt nur die Zeiten dieses Einsatzes.

    Einsatz        die Abschnitte der Plantafel zum Auftrag, deren Zeitraum den Tag des Berichts umfasst
                   (app/service_reports.py::einsaetze_des_berichts()), je mit den eingeteilten Personen: Besetzung der Team-Zuweisung
                   (Schnappschuss) und Einzelzuweisungen an der Arbeitsvorbereitung
    Zeiten         dieser Auftrag, Tag im Zeitraum des Einsatzes, Person dort eingeteilt (zeit_gehoert_zum_einsatz()); bis 1.9.36 jede
                   Zeit des Auftrags
    ohne Bezug     umfasst kein Abschnitt den Tag des Berichts, bleibt es bei allen Zeiten des Auftrags (offen, Festlegungen 1.9.37)
"""

from datetime import date
from decimal import Decimal

from app.models import (
    PlanningSlot, WorkPreparation, WorkPreparationEmployee, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee,
)
from app.service_report_pdf import build_service_report_pdf
import pytest

from app import service_reports as service_reports_module
from app.service_reports import create_report, einsaetze_des_berichts, get_report_row, sign_report
from app.time_tracking import create_manual_entry
from tests.test_v153_mahnwesen import db_session
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text, _make_order_for_report
from tests.test_v224_field_view import make_employee, make_team

A_BEGINN, A_ENDE = date(2026, 10, 5), date(2026, 10, 7)
B_BEGINN, B_ENDE = date(2026, 10, 12), date(2026, 10, 13)


@pytest.fixture(autouse=True)
def _ablage(tmp_path, monkeypatch):
    """Unterschriften in den Testordner -- ein PDF gibt es nur für unterschriebene Berichte."""
    monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")


def _unterschrieben(db, report_id):
    sign_report(db, report_id, installer_signature_png_bytes=TINY_PNG, installer_signature_name="Mia Monteurin",
                customer_signature_png_bytes=TINY_PNG, customer_signature_name="Bernd Bauherr")
    return get_report_row(db, report_id)


def _welt():
    """Ein Auftrag, zwei Einsätze: A (5.–7.10.) mit Kolonne A (Mia), B (12.–13.10.) mit Kolonne B (Tom)."""
    db = db_session()
    order = _make_order_for_report(db)
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    prep = WorkPreparation(order_id=order.id, status="offen")
    db.add(prep); db.flush()
    for team, emp, beginn, ende in ((make_team(db, "K-A", "Kolonne A"), mia, A_BEGINN, A_ENDE),
                                     (make_team(db, "K-B", "Kolonne B"), tom, B_BEGINN, B_ENDE)):
        zuweisung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
        db.add(zuweisung); db.flush()
        db.add(WorkPreparationTeamEmployee(assignment_id=zuweisung.id, employee_id=emp.id,
                                           employee_name_snapshot=f"{emp.first_name} {emp.last_name}"))
        db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuweisung.id, start_date=beginn, end_date=ende))
    db.commit()
    for emp, tag, stunden in ((mia, date(2026, 10, 6), "3.25"),   # Einsatz A
                              (tom, date(2026, 10, 12), "4.75"),  # Einsatz B
                              (tom, date(2026, 10, 6), "2.5"),    # Tag von A, aber Tom ist dort nicht eingeteilt
                              (mia, date(2026, 10, 12), "1.5")):  # Mia, aber an einem Tag von B
        create_manual_entry(db, employee_id=emp.id, order_id=order.id, work_date=tag, hours=Decimal(stunden), activity="Abdichtung")
    return db, order, mia, tom, prep


def _pdf_text(db, order, tag):
    r = create_report(db, order.id, "rapport", performed_at=tag, description="Dach abgedichtet")
    return _extract_pdf_text(build_service_report_pdf(db, _unterschrieben(db, r["id"])))


def test_einsatz_des_berichts():
    db, order, mia, tom, prep = _welt()
    r = create_report(db, order.id, "rapport", performed_at=date(2026, 10, 6))
    assert einsaetze_des_berichts(db, get_report_row(db, r["id"])) == [(A_BEGINN, A_ENDE, {mia.id})]


def test_pdf_einsatz_a_ohne_zeiten_von_einsatz_b():
    """Angriff: bis 1.9.36 standen im PDF von Einsatz A auch Toms Zeit aus Einsatz B und alle anderen Zeiten des Auftrags."""
    db, order, *_ = _welt()
    text = _pdf_text(db, order, date(2026, 10, 6))
    assert b"Erfasste Zeiten" in text and b"3,25" in text
    assert [s in text for s in (b"4,75", b"2,50", b"1,50", b"12.10.2026")] == [False] * 4


def test_pdf_einsatz_b_nur_mit_seiner_zeit():
    """Gegenprobe: das PDF von Einsatz B zeigt Toms Zeit am 12.10., nichts aus Einsatz A."""
    db, order, *_ = _welt()
    text = _pdf_text(db, order, date(2026, 10, 13))
    assert b"4,75" in text and [s in text for s in (b"3,25", b"2,50", b"1,50")] == [False] * 3


def test_einzelzuweisung_zaehlt_fuer_jeden_einsatz_der_arbeitsvorbereitung():
    """Wer an der Arbeitsvorbereitung selbst eingeteilt ist (nicht über die Kolonne), gehört zu jedem ihrer Einsätze."""
    db, order, mia, tom, prep = _welt()
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=tom.id))
    db.commit()
    text = _pdf_text(db, order, date(2026, 10, 6))
    assert b"3,25" in text and b"2,50" in text and b"4,75" not in text


def test_ohne_einsatz_bezug_alle_zeiten_des_auftrags():
    """Kein Abschnitt umfasst den Tag (z. B. ungeplanter Einsatz): wie bis 1.9.36 alle Zeiten des Auftrags -- offen, nicht geraten."""
    db, order, *_ = _welt()
    r = create_report(db, order.id, "rapport", performed_at=date(2026, 10, 20))
    assert einsaetze_des_berichts(db, get_report_row(db, r["id"])) is None
    text = _extract_pdf_text(build_service_report_pdf(db, _unterschrieben(db, r["id"])))
    assert [s in text for s in (b"3,25", b"4,75", b"2,50", b"1,50")] == [True] * 4
