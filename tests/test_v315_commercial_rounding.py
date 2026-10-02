"""Version 1.8.11 -- kaufmännisches Runden (ROUND_HALF_UP) überall.

Decimal.quantize() ohne rounding= und f"{x:.2f}" runden halb-gerade (0,125 -> 0,12). Jetzt:

1. Unter app/ gibt es keinen quantize()-Aufruf ohne Rundungsart (AST-Suche, auch über mehrere
   Zeilen), mit Selbsttest der Suche.
2. Die zentralen Helfer in app/rounding.py.
3. Je Geldstelle ein Halbcent-Fall, jeweils mit dem alten Wert im Kommentar: Rechnung
   (Positionsbetrag, USt, Brutto, Pauschalbetrag, Rechnung aus Aufwand, PDF), Skonto, Mahnung,
   Eingangsrechnung, Betriebskosten, dazu die Stunden (DATEV-Export, Summen, PDFs).
4. Eine vor 1.8.11 versendete Rechnung (rounding_rule leer) rechnet unverändert, samt ihrem
   Storno und ihrer Mahnung -- sonst ergäbe ihr Nachdruck einen anderen Betrag (Regel 5).
5. Die Migration setzt nur offene Entwürfe (ohne Storno-Entwürfe) auf "half_up".
"""

import ast
import importlib.util
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.calculation import load_calculation_settings
from app.incoming_invoices import gross_amount as incoming_gross_amount, invoice_gross_amount
from app.invoice_pdf import build_invoice_pdf
from app.invoices import (
    add_invoice_item, compute_invoice_totals, create_abschlag_pauschal, create_invoice_from_time_entries,
    create_schlussrechnung, create_storno_draft, finalize_and_send_invoice, format_payment_terms_sentence,
    invoice_to_dict,
)
from app.models import Employee, IncomingInvoice, IncomingInvoiceItem, Invoice, TimeEntry
from app.recurring_costs import create_cost, gross_amount as cost_gross_amount, overview_summary
from app.reminders import create_reminder, ensure_default_reminder_levels, format_reminder_text, reminder_to_dict
from app.rounding import round_half_up, round_hours, round_money
from app.time_backoffice import backoffice_summary, build_datev_export, get_employee_payroll, load_time_settings
from app.time_tracking import create_manual_entry, summarize_entries
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v283_recurring_costs import _base_payload

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
DUE = date.today() + timedelta(days=14)


# ---------------------------------------------------------------------------
# 1. Kein quantize() ohne Rundungsart unter app/
# ---------------------------------------------------------------------------

def quantize_calls(source: str, filename: str = "<quelle>") -> tuple[int, list[int]]:
    """(Zahl aller quantize()-Aufrufe, Zeilen der Aufrufe ohne Rundungsart). Rundungsart heißt
    rounding=... oder das zweite Positionsargument (quantize(exp, rounding, context))."""
    total, bare = 0, []
    for node in ast.walk(ast.parse(source, filename)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "quantize":
            total += 1
            if len(node.args) < 2 and not any(k.arg == "rounding" for k in node.keywords):
                bare.append(node.lineno)
    return total, bare


def test_no_quantize_without_rounding_in_app():
    found, per_file = [], {}
    for path in sorted(APP.rglob("*.py")):
        count, bare = quantize_calls(path.read_text(encoding="utf-8"), str(path))
        per_file[path.relative_to(APP).as_posix()] = count
        found += [f"{path.relative_to(ROOT).as_posix()}:{line}" for line in bare]
    assert len(per_file) > 100 and per_file.get("rounding.py"), "Suche läuft ins Leere: app/rounding.py nicht erfasst"
    assert not found, ("quantize() ohne Rundungsart rundet halb-gerade (0,125 -> 0,12). "
                       "app/rounding.py nehmen (round_money/round_hours/round_half_up) oder rounding= angeben: "
                       + ", ".join(found))


def test_search_catches_bare_quantize_also_across_lines():
    source = '''
from decimal import ROUND_HALF_UP, Decimal
CENT = Decimal("0.01")
a = Decimal("0.125").quantize(CENT)
b = (Decimal("1") + Decimal("0.125")).quantize(
    Decimal("0.01")
)
c = Decimal("0.125").quantize(CENT, rounding=ROUND_HALF_UP)
d = Decimal("0.125").quantize(CENT, ROUND_HALF_UP)
e = "x.quantize(CENT)"  # nur Text
# f = y.quantize(CENT)
'''
    assert quantize_calls(source) == (4, [4, 5])


# ---------------------------------------------------------------------------
# 2. Helfer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    (Decimal("0.125"), Decimal("0.13")),   # halb-gerade: 0.12
    (Decimal("0.135"), Decimal("0.14")),
    (Decimal("-0.125"), Decimal("-0.13")),  # vom Nullpunkt weg, wie PostgreSQL NUMERIC
    (Decimal("0.1249"), Decimal("0.12")),
    (0.285, Decimal("0.29")),               # float über seinen Text, nicht 0.28499999...
    ("2.675", Decimal("2.68")),
    (None, Decimal("0.00")),
])
def test_round_money(value, expected):
    assert round_money(value) == expected
    assert str(round_money(value)) == str(expected)


def test_round_hours_and_other_precisions():
    assert round_hours(Decimal("1.125")) == Decimal("1.13")
    assert round_hours(Decimal("7.4450")) == Decimal("7.45")
    assert round_half_up(Decimal("12.25"), Decimal("0.1")) == Decimal("12.3")      # Auslastung in %
    assert round_half_up(Decimal("1.00005"), Decimal("0.0001")) == Decimal("1.0001")  # gespeicherte Stunden


# ---------------------------------------------------------------------------
# 3. Je Geldstelle ein Halbcent-Fall
# ---------------------------------------------------------------------------

def _invoice(db, quantity, unit_price, vat_rate=Decimal("19.00"), finalize=False):
    order, _ = make_order_with_item(db, quantity=Decimal(quantity), unit_price=Decimal(unit_price), vat_rate=Decimal(vat_rate))
    invoice = create_schlussrechnung(db, order, due_date=DUE)
    return finalize_and_send_invoice(db, invoice) if finalize else invoice


def _pdf(db, invoice) -> bytes:
    return _extract_pdf_text(build_invoice_pdf(db, invoice))


def test_invoice_vat_half_cent_rounds_up_in_totals_api_and_pdf():
    db = db_session()
    invoice = _invoice(db, "1", "1.50")                 # USt 19 % von 1,50 = 0,285
    assert invoice.rounding_rule == "half_up"
    assert compute_invoice_totals(invoice) == {"net_total": Decimal("1.50"), "vat_total": Decimal("0.29"),
                                               "gross_total": Decimal("1.79")}  # alt: 0,285 / 1,785, im PDF 0,28 / 1,78
    data = invoice_to_dict(invoice)
    assert (data["vat_total"], data["gross_total"]) == (Decimal("0.29"), Decimal("1.79"))
    text_ = _pdf(db, invoice)
    assert b"0,29 EUR" in text_ and b"1,79 EUR" in text_
    assert b"0,28 EUR" not in text_ and b"1,78 EUR" not in text_


def test_invoice_line_total_half_cent_rounds_up_and_totals_add_up():
    """Positionsbetrag 2,5 x 0,85 = 2,125. Alt stand im PDF 2,12 (Position und Netto), USt 0,40 und
    Brutto 2,53 -- Netto + USt ergab nicht Brutto. Jetzt 2,13 + 0,40 = 2,53."""
    db = db_session()
    invoice = _invoice(db, "2.5", "0.85")
    assert invoice.items[0].billed_total == Decimal("2.125")   # gespeichert bleibt der genaue Wert
    totals = compute_invoice_totals(invoice)
    assert totals == {"net_total": Decimal("2.13"), "vat_total": Decimal("0.40"), "gross_total": Decimal("2.53")}
    assert totals["net_total"] + totals["vat_total"] == totals["gross_total"]
    assert invoice_to_dict(invoice)["items"][0]["billed_total"] == Decimal("2.13")
    text_ = _pdf(db, invoice)
    assert b"2,13" in text_ and b"2,12" not in text_


def test_invoice_several_lines_net_is_sum_of_rounded_line_totals():
    """Zwei Positionen zu je 0,125: je 0,13, Netto 0,26 (ungerundet summiert wären es 0,25)."""
    db = db_session()
    invoice = _invoice(db, "1", "0.125", vat_rate="0")
    add_invoice_item(db, invoice, short_text="Kleinteil", long_text="", unit="Stk", unit_price=Decimal("0.125"), ist_quantity=Decimal("1"))
    db.refresh(invoice)
    assert [row["billed_total"] for row in invoice_to_dict(invoice)["items"]] == [Decimal("0.13"), Decimal("0.13")]
    assert compute_invoice_totals(invoice)["net_total"] == Decimal("0.26")


def test_lump_sum_invoice_vat_half_cent():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1.50"), progress_description="Abschlag", due_date=DUE)
    totals = compute_invoice_totals(invoice)
    assert (totals["vat_total"], totals["gross_total"]) == (Decimal("0.29"), Decimal("1.79"))  # alt 0,285 / 1,785


def test_invoice_from_time_entries_hours_times_rate_half_cent():
    """1,2525 Std. x 50,00 = 62,625 -- auf der Rechnung aus Aufwand jetzt 62,63 (alt im PDF 62,62)."""
    db = db_session()
    order, _ = make_order_with_item(db, vat_rate=Decimal("0"))
    load_calculation_settings(db).labor_rate = Decimal("50.00"); db.commit()
    emp = Employee(employee_number="E-1", first_name="Paul", last_name="Aufwand", employee_group="gewerblich", active=True)
    db.add(emp); db.commit()
    entry = create_manual_entry(db, employee_id=emp.id, order_id=order.id, work_date=date.today(), hours=Decimal("1.2525"), activity="Reparatur")
    invoice = create_invoice_from_time_entries(db, order, [entry], [], due_date=DUE)
    assert invoice_to_dict(invoice)["items"][0]["billed_total"] == Decimal("62.63")
    assert compute_invoice_totals(invoice)["gross_total"] == Decimal("62.63")


def test_skonto_half_cent_rounds_up():
    db = db_session()
    invoice = _invoice(db, "1", "10.25", vat_rate="0")
    invoice.skonto_percent, invoice.skonto_days = Decimal("2.00"), 10
    db.commit()
    sentence = format_payment_terms_sentence(invoice)       # 2 % von 10,25 = 0,205
    assert "das entspricht 0,21 €." in sentence, sentence   # alt: 0,20 €
    invoice.payment_terms_text_template = "Skonto {skontobetrag} €"
    assert format_payment_terms_sentence(invoice) == "Skonto 0,21 €"


def test_reminder_takes_rounded_gross_and_rounds_its_total_up():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = _invoice(db, "1", "1.50", finalize=True)
    reminder = create_reminder(db, invoice, 1)
    assert reminder.outstanding_amount == Decimal("1.79")    # alt 1,785 gespeichert
    reminder.fee_amount = Decimal("2.515"); db.commit()     # 1,79 + 2,515 = 4,305
    assert reminder_to_dict(reminder)["total_amount"] == Decimal("4.31")  # alt 4,30
    reminder.text = "Offen {offener_betrag}, gesamt {gesamtbetrag}"
    assert format_reminder_text(reminder) == "Offen 1,79 €, gesamt 4,31 €"


def test_incoming_invoice_gross_half_cent():
    assert incoming_gross_amount(Decimal("1.50"), Decimal("19.00")) == Decimal("1.79")   # alt 1,78
    single = IncomingInvoice(net_amount=Decimal("1.50"), tax_rate_pct=Decimal("19.00"))
    assert invoice_gross_amount(single) == Decimal("1.79")
    mixed = IncomingInvoice(net_amount=Decimal("3.00"), tax_rate_pct=Decimal("19.00"), items=[
        IncomingInvoiceItem(description="A", net_amount=Decimal("1.50"), tax_rate_pct=Decimal("19.00")),
        IncomingInvoiceItem(description="B", net_amount=Decimal("1.50"), tax_rate_pct=Decimal("19.00")),
    ])
    assert invoice_gross_amount(mixed) == Decimal("3.58")   # je Position 1,79; alt 3,56


def test_recurring_cost_gross_and_monthly_total_half_cent():
    db = db_session()
    assert cost_gross_amount(Decimal("1.50"), Decimal("19.00")) == Decimal("1.79")   # alt 1,78
    create_cost(db, _base_payload(net_amount="1.26", billing_interval="jaehrlich"))
    summary = overview_summary(db)
    assert summary["annual_total"] == Decimal("1.26")
    assert summary["monthly_total"] == Decimal("0.11")   # 1,26 / 12 = 0,105; alt 0,10


def _hours_setup(db, hours):
    order, _ = make_order_with_item(db)
    emp = Employee(employee_number="MA-10", first_name="Max", last_name="Lohn", employee_group="gewerblich", active=True)
    db.add(emp); db.commit()
    create_manual_entry(db, employee_id=emp.id, order_id=order.id, work_date=date(2026, 9, 7), hours=Decimal(hours), activity="Dach")
    return emp


def test_datev_export_hours_half_hundredth_round_up():
    """DATEV trägt Stunden, keine Beträge -- aber die Lohnabrechnung rechnet mit ihnen."""
    db = db_session()
    emp = _hours_setup(db, "1.125")
    get_employee_payroll(db, emp.id).datev_personnel_number = "14"
    settings = load_time_settings(db)
    settings.datev_target, settings.datev_wage_type_site, settings.rounding_minutes = "lohn_gehalt", "200", 0
    db.commit()
    data, _, warnings = build_datev_export(db, date(2026, 9, 1), date(2026, 9, 30))
    text_ = data.decode("utf-8-sig")
    assert not warnings and ";1,13;" in text_ and "1,12" not in text_, text_   # alt 1,12
    settings.datev_target = "lodas"; db.commit()
    assert ";1,13;" in build_datev_export(db, date(2026, 9, 1), date(2026, 9, 30))[0].decode("utf-8-sig")


def test_hour_sums_half_hundredth_round_up():
    db = db_session()
    _hours_setup(db, "1.125")
    assert summarize_entries(db)["total_hours"] == Decimal("1.13")                           # alt 1,12
    assert backoffice_summary(db, date(2026, 9, 1), date(2026, 9, 30))["total_hours"] == Decimal("1.13")


def test_hours_in_service_report_and_field_timesheet_pdfs_round_up(tmp_path, monkeypatch):
    """Beide PDFs formatierten die mit vier Stellen gespeicherten Stunden per ":.2f" (alt 1,12)."""
    from app import service_reports
    from app.field_timesheet_pdf import build_field_timesheet_pdf
    from app.models import ServiceReport
    from app.service_report_pdf import build_service_report_pdf
    from tests.test_v203_service_reports import sign_report_for_test

    monkeypatch.setattr(service_reports, "SIGNATURE_ROOT", tmp_path / "sigs")
    db = db_session()
    emp = _hours_setup(db, "1.125")
    order_id = db.query(TimeEntry).one().order_id
    report = service_reports.create_report(db, order_id, "rapport", description="Reparatur")
    sign_report_for_test(db, report["id"])
    for pdf in (build_service_report_pdf(db, db.get(ServiceReport, report["id"])), build_field_timesheet_pdf(db, emp.id, 2026, 9)):
        text_ = _extract_pdf_text(pdf)
        assert b"1,13" in text_ and b"1,12" not in text_


# ---------------------------------------------------------------------------
# 4. Rechnungen von vor 1.8.11 rechnen unverändert
# ---------------------------------------------------------------------------

def _legacy(db, quantity, unit_price, vat_rate="19.00"):
    invoice = _invoice(db, quantity, unit_price, vat_rate=vat_rate, finalize=True)
    invoice.rounding_rule = None     # so steht sie nach der Migration in der Datenbank
    db.commit(); db.refresh(invoice)
    return invoice


def test_legacy_invoice_keeps_old_amounts_in_api_and_pdf():
    db = db_session()
    invoice = _legacy(db, "1", "1.50")
    assert compute_invoice_totals(invoice) == {"net_total": Decimal("1.50"), "vat_total": Decimal("0.285"),
                                               "gross_total": Decimal("1.785")}
    text_ = _pdf(db, invoice)
    assert b"0,28 EUR" in text_ and b"1,78 EUR" in text_
    line = _legacy(db_session(), "2.5", "0.85")
    assert invoice_to_dict(line)["items"][0]["billed_total"] == Decimal("2.125")


def test_legacy_invoice_keeps_old_skonto():
    db = db_session()
    invoice = _legacy(db, "1", "10.25", vat_rate="0")
    invoice.skonto_percent, invoice.skonto_days = Decimal("2.00"), 10
    db.commit()
    assert "das entspricht 0,20 €." in format_payment_terms_sentence(invoice)


def test_legacy_invoice_storno_inherits_rule_and_mirrors_exactly():
    db = db_session()
    legacy = _legacy(db, "1", "1.50")
    storno = create_storno_draft(db, legacy)
    assert storno.rounding_rule is None
    assert compute_invoice_totals(storno)["vat_total"] == -compute_invoice_totals(legacy)["vat_total"]
    assert b"-0,28 EUR" in _pdf(db, storno)

    db_new = db_session()
    storno_new = create_storno_draft(db_new, _invoice(db_new, "1", "1.50", finalize=True))
    assert storno_new.rounding_rule == "half_up"
    assert compute_invoice_totals(storno_new)["vat_total"] == Decimal("-0.29")


def test_legacy_invoice_reminder_total_keeps_half_even():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = _legacy(db, "1", "1.50")
    reminder = create_reminder(db, invoice, 1)
    reminder.fee_amount = Decimal("2.50"); db.commit()
    assert reminder_to_dict(reminder)["total_amount"] == Decimal("4.28")   # 1,785 + 2,50 = 4,285, halb-gerade


# ---------------------------------------------------------------------------
# 5. Migration
# ---------------------------------------------------------------------------

def _migration():
    path = next((ROOT / "alembic" / "versions").glob("*_rechnung_rundungsregel.py"))
    spec = importlib.util.spec_from_file_location("rechnung_rundungsregel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_marks_only_open_non_storno_drafts():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    order, _ = make_order_with_item(db)
    rows = {}
    for key, status, invoice_type in (("entwurf", "entwurf", "schluss"), ("pauschal", "entwurf", "abschlag_pauschal"),
                                      ("versendet", "versendet", "schluss"), ("bezahlt", "bezahlt", "schluss"),
                                      ("storniert", "storniert", "schluss"), ("storno_entwurf", "entwurf", "storno"),
                                      ("storno_versendet", "versendet", "storno")):
        rows[key] = Invoice(order_id=order.id, invoice_type=invoice_type, status=status, customer_name="Test Kunde")
    db.add_all(rows.values()); db.commit()
    with engine.begin() as conn:
        conn.execute(text("UPDATE invoices SET rounding_rule = NULL"))   # Stand direkt nach add_column
        assert _migration().mark_open_drafts(conn) == 2
    db.expire_all()
    assert {k: v.rounding_rule for k, v in rows.items()} == {
        "entwurf": "half_up", "pauschal": "half_up", "versendet": None, "bezahlt": None,
        "storniert": None, "storno_entwurf": None, "storno_versendet": None}
