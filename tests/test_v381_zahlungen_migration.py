"""Migration c7d41e9a2b63 (Zahlungsstufe Z1, seit 1.8.78): Zahlungstabellen und Übernahme des Status "bezahlt".

Je Rechnung mit "bezahlt" eine Zahlung über das Brutto zum bezahlt-Datum (fehlt es: Rechnungsdatum), Herkunft "uebernommen",
ganz ihr zugeordnet; die Rechnung steht danach auf "versendet" und ist abgeleitet bezahlt. Eine Stornorechnung mit "bezahlt"
bekommt keine Zahlung; eine stornierte Rechnung mit bezahlt-Datum bleibt, wie sie ist. Rückweg: stellt "bezahlt" wieder her --
verweigert, sobald etwas erfasst ist, das er verlöre. Bestand auf einer Wegwerf-SQLite und (opt-in) einem Wegwerf-Schema der
lokalen PostgreSQL; das Brutto der Migration ist das der App (eigene Kopie in der Migration, hier gleich gehalten)."""

import importlib.util
import os
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, insert, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.grunddaten import anlegen
from app.invoices import compute_invoice_totals, create_abschlag_leistungsstand, create_abschlag_pauschal, \
    create_storno_draft, update_invoice_item
from app.models import Invoice, InvoiceItem, Order, Payment, PaymentAllocation
from app.payments import Line, book_payment, payable_gross, payment_state
from tests.leistungszeitraum import festschreiben
from tests.test_v133_invoices import db_session
from tests.bestand_alt import auftrag
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v380_nummern_eindeutig import _alembic, _ok

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = "c7d41e9a2b63"
VORHER = "f3a8c2d6b190"
BIS = "3e9b7c41d2a8"  # seit 1.9.124: die jüngste Migration, über die der Rückweg mit Aufträgen im Bestand geht (vor 8d3f6a2c91e7)
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
D = Decimal


def _migration():
    path = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_1878_zahlungen", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _brutto_der_migration(invoice: Invoice) -> Decimal:
    return _migration().brutto(invoice.invoice_type, invoice.rounding_rule, invoice.vat_rate, invoice.lump_sum_net,
                               [i.billed_total for i in invoice.items])


def test_the_migration_computes_the_same_gross_as_the_app(monkeypatch):
    # Der zweite Abschlag (Ist 3 nach 4) lautet negativ -- seit 1.8.83 (R4a Punkt 4) nicht mehr festschreibbar, im Altbestand
    # aber möglich, und die Migration muss ihn rechnen: hier festgeschrieben wie vor 1.8.83.
    import app.invoices as invoices_module
    monkeypatch.setattr(invoices_module, "amount_block_reason", lambda invoice: None)  # seit 1.8.85 (vorher negative_progress_reason)
    # Altbestand mit anderem Preis als der Auftrag -- seit 1.8.85 (R4b Punkt 3) nicht mehr festschreibbar.
    monkeypatch.setattr(invoices_module, "order_deviation_reason", lambda invoice: None)
    db = db_session()
    anlegen(db)
    db.commit()
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0001"))
    rechnungen = []
    for ist, price in (("4", None), ("3", "10.0042"), ("7", "33.333")):
        invoice = create_abschlag_leistungsstand(db, db.get(Order, order.id))
        if price:
            invoice.items[0].unit_price = D(price)
        update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
        rechnungen.append(festschreiben(db, invoice))
    rechnungen.append(festschreiben(db, create_abschlag_pauschal(db, db.get(Order, order.id), lump_sum_net=D("1234.565"))))
    storno = festschreiben(db, create_storno_draft(db, rechnungen[0]))
    for invoice in rechnungen + [storno]:
        for rule in ("half_up", None):  # ab 1.8.11 und Altbestand davor
            invoice.rounding_rule = rule
            assert _brutto_der_migration(invoice) == payable_gross(invoice), (invoice.id, rule,
                                                                              compute_invoice_totals(invoice))
    db.rollback()


# ---------------------------------------------------------------------------
# Probe auf einem Bestand: hoch, Zahlstand, runter (stellt "bezahlt" her), hoch, verweigerter Rückweg
# ---------------------------------------------------------------------------

def _rechnung(db, order, *, status, invoice_type="abschlag_leistungsstand", net="200", rule="half_up", paid_date=None,
              storno_of=None, invoice_date=date(2026, 9, 1)):
    """Rechnung wie im Altbestand, direkt angelegt (die App-Wege prüfen seit 1.8.78 Zuordnungen, deren Tabelle vor der
    Migration fehlt). net = Positionsbetrag (abgerechnet), bei abschlag_pauschal der Pauschalbetrag."""
    sign = -1 if invoice_type == "storno" else 1
    # Seit 1.8.79 als Core-Insert mit genau diesen Spalten: das ORM schriebe jede Spalte des heutigen Modells (auch
    # invoices.customer_id), die es auf dem Stand vor der Migration noch nicht gibt.
    invoice_id = db.execute(insert(Invoice.__table__).values(
        order_id=order.id, invoice_type=invoice_type, status=status, invoice_date=invoice_date, due_date=invoice_date,
        paid_date=paid_date, customer_name=order.customer_name, vat_rate=D("19"), storno_of_invoice_id=storno_of,
        lump_sum_net=D(net) if invoice_type == "abschlag_pauschal" else None,
        invoice_number=f"R-ALT-{uuid.uuid4().hex[:6]}", rounding_rule=rule,
    )).inserted_primary_key[0]
    # Seit 1.9.115 auch die Position als Core-Insert: Rechnungspositionen stehen im Änderungsprotokoll, und dessen Bezeichnung lädt die Rechnung
    # über das ORM -- mit invoices.customer_id, die es auf diesem Stand noch nicht gibt.
    db.execute(insert(InvoiceItem.__table__).values(
        invoice_id=invoice_id, source_order_item_id=None, sort_order=10, position_number="1", short_text="Dach", long_text="", unit="m2",
        unit_price=D(net), soll_quantity=D("1"), ist_quantity=D("1"), billed_quantity=D(sign), billed_total=D(net) * sign))
    db.commit()
    return invoice_id


def _status(db, invoice_id):
    return db.execute(text("SELECT status, paid_date FROM invoices WHERE id = :i"), {"i": invoice_id}).one()


def _paid_date(value):
    return value if value is None or isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _migrationsprobe(url: str, engine, Session) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    db = Session()
    try:
        # Seit 1.8.80 ohne Grunddaten und ORM: der Bestand dieses Stands kennt Spalten des heutigen Modells noch nicht
        # (tests/bestand_alt.py).
        order = auftrag(db, number="0001")
        fremd = auftrag(db, number="0002")  # anderer Kunde
        ids = {
            "bezahlt": _rechnung(db, order, status="bezahlt", net="2000", paid_date=date(2026, 9, 30)),
            "alt": _rechnung(db, fremd, status="bezahlt", net="400.168", rule=None, paid_date=date(2026, 9, 29)),
            "ohne_datum": _rechnung(db, order, status="bezahlt", invoice_type="abschlag_pauschal", net="1000"),
            "offen": _rechnung(db, order, status="versendet", net="300"),
            "storniert": _rechnung(db, order, status="storniert", net="100", paid_date=date(2026, 9, 15)),
        }
        ids["storno"] = _rechnung(db, order, status="bezahlt", invoice_type="storno", net="100",
                                  paid_date=date(2026, 9, 20), storno_of=ids["storniert"])
        kunde, kunde_fremd = order.customer_id, fremd.customer_id
        vorher = {k: tuple(_status(db, i)) for k, i in ids.items()}
        db.close()

        _ok(_alembic(url, "upgrade", MIGRATION))
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        # Seit 1.8.79 folgen weitere Migrationen; das ORM liest den heutigen Stand (invoices.customer_id) -- also bis zur jüngsten, über die
        # der Rückweg mit diesem Bestand geht: seit 1.9.124 verweigert 8d3f6a2c91e7 ihn für jeden Bestand mit Auftrag („läuft“), bis 1.9.123
        # ging die Probe bis head.
        _ok(_alembic(url, "upgrade", BIS))
        db = Session()
        payments = {p.id: p for p in db.scalars(select(Payment))}
        allocations = list(db.scalars(select(PaymentAllocation).order_by(PaymentAllocation.invoice_id)))
        assert sorted((a.invoice_id, a.kind, a.amount) for a in allocations) == sorted([
            (ids["bezahlt"], "zahlung", D("2380.00")), (ids["alt"], "zahlung", D("476.20")),
            (ids["ohne_datum"], "zahlung", D("1190.00"))])
        by_invoice = {a.invoice_id: payments[a.payment_id] for a in allocations}
        assert {k: (by_invoice[ids[k]].customer_id, by_invoice[ids[k]].received_on, by_invoice[ids[k]].amount)
                for k in ("bezahlt", "alt", "ohne_datum")} == {
            "bezahlt": (kunde, date(2026, 9, 30), D("2380.00")), "alt": (kunde_fremd, date(2026, 9, 29), D("476.20")),
            "ohne_datum": (kunde, date(2026, 9, 1), D("1190.00"))}
        assert all(p.origin == "uebernommen" and p.note.startswith("Übernommen aus dem Status") for p in payments.values())
        assert {k: _status(db, i).status for k, i in ids.items()} == {
            "bezahlt": "versendet", "alt": "versendet", "ohne_datum": "versendet", "offen": "versendet",
            "storniert": "storniert", "storno": "versendet"}
        states = {k: payment_state(db, db.get(Invoice, i)) for k, i in ids.items()}
        assert {k: (s.state, s.paid_on) if s else None for k, s in states.items()} == {
            "bezahlt": ("bezahlt", date(2026, 9, 30)), "alt": ("bezahlt", date(2026, 9, 29)),
            "ohne_datum": ("bezahlt", date(2026, 9, 1)), "offen": ("offen", None), "storniert": None, "storno": None}
        db.close()

        # Rückweg ohne Erfasstes: "bezahlt" exakt wie vorher, Tabellen weg (die späteren Migrationen zuerst zurück).
        _ok(_alembic(url, "downgrade", MIGRATION))
        _ok(_alembic(url, "downgrade", "-1"))
        engine.dispose()
        db = Session()
        assert {k: (s, _paid_date(d)) for k, (s, d) in ((k, tuple(_status(db, i))) for k, i in ids.items())} == {
            k: (s, _paid_date(d)) for k, (s, d) in vorher.items()}
        assert "payments" not in inspect(engine).get_table_names()
        db.close()

        # Wieder hoch, eine Zahlung erfassen -> der Rückweg verweigert und ändert nichts.
        _ok(_alembic(url, "upgrade", BIS))
        engine.dispose()
        db = Session()
        offen = db.get(Invoice, ids["offen"])
        book_payment(db, customer_id=kunde, received_on=date(2026, 10, 1), amount=D("100"), note=None,
                     lines=[Line(offen.id, zahlung=D("100"))])
        db.close()
        _ok(_alembic(url, "downgrade", MIGRATION))
        lauf = _alembic(url, "downgrade", "-1")
        ausgabe = lauf.stdout + lauf.stderr
        assert lauf.returncode != 0 and "Downgrade verweigert: 1 erfasste Zahlungen" in ausgabe, ausgabe[-1500:]
        assert MIGRATION in _ok(_alembic(url, "current")).stdout
        engine.dispose()
        db = Session()
        assert db.execute(text("SELECT COUNT(*) FROM payments")).scalar() == 4  # roh: das ORM kennt invoices.customer_id
        assert _status(db, ids["bezahlt"]).status == "versendet"
    finally:
        db.close()
        engine.dispose()


def test_migration_takes_over_paid_invoices_and_the_way_back_restores_them(tmp_path):
    url = f"sqlite:///{(tmp_path / 'zahlungen.db').as_posix()}"
    engine = create_engine(url)
    _migrationsprobe(url, engine, sessionmaker(bind=engine))


def test_pg_migration_takes_over_paid_invoices_and_the_way_back_restores_them():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_zl_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _migrationsprobe(url, engine, sessionmaker(bind=engine))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
