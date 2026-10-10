"""Rechnungsdatum = Tag des Festschreibens, jeder schreibende Weg an einer Rechnung unter der Sperre (seit 1.8.75; Befund 4a-4c
und Vorgabe 1.8.75 Punkt 1 und 2, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.75").

- Rechnungsdatum: der Tag des Festschreibens in Berliner Zeit (app/invoices.py::finalize_dates()); die Fälligkeit behält das
  Zahlungsziel des Entwurfs und rückt mit, das Skontodatum rechnet ab dem Rechnungsdatum. Im Entwurf zeigt invoice_to_dict(), was
  das Festschreiben heute setzen würde (finalize_dates), danach einen Hinweis, wenn der Versand später liegt (send_hint).
- Sperre: "Rechnung aus Aufwand" anlegen und Positionen, Kopf, Zahlungsbedingung, Steuerschlüssel eines Entwurfs bearbeiten
  laufen unter derselben Sperre wie das Festschreiben (Auftragszeile, _lock_draft()); geändert wird nur, was danach noch Entwurf
  ist, sonst 409. Dazu der Versandnachweis an der Rechnung (email_sent_at/_to) nach dem Senden.

Strukturtest in drei Teilen: (1) jede öffentliche Funktion in app/invoices.py, die schreibt, sperrt vorher (AST, in der
Reihenfolge des Quelltexts, über die Hilfsfunktionen des Moduls); (2) außerhalb von app/invoices.py legt niemand Rechnungen oder
Positionen an und schreibt kein Feld einer Rechnung; (3) ein Rundgang über jeden schreibenden Endpunkt der Rechnungen, bei dem ein
Beobachter an der Sitzung jede geschriebene Rechnung bzw. Position gegen die Sperre ihres Auftrags hält -- ein neuer Endpunkt ohne
Szenario ist rot. Die Gleichzeitigkeit prüfen die Tests mit pg gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in)."""

import ast
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import berlin_time
from app.berlin_time import berlin_today
from app.database import Base
from app.email_sending import update_smtp_settings
from app.invoice_pdf import build_invoice_pdf
from app.invoices import (
    InvoiceBlocked,
    add_invoice_item,
    create_abschlag_pauschal,
    create_invoice_from_time_entries,
    create_schlussrechnung,
    create_storno_draft,
    delete_invoice_draft,
    finalize_and_send_invoice,
    format_payment_terms_sentence,
    invoice_to_dict,
    mark_invoice_paid,
    remove_invoice_item,
    send_hint,
    update_invoice_header,
    update_invoice_item,
    update_invoice_payment_term,
    update_invoice_tax_key,
)
from app.models import Employee, Invoice, InvoiceItem, Order, PaymentTerm, TaxKey, TimeEntry
from app.routers.invoices import router as invoices_router
from app.time_tracking import list_entries
from tests.leistungszeitraum import ZEITRAUM_JSON, festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v231_invoice_item_table_width_and_quantity import _extract_pdf_text
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


@pytest.fixture
def uhr(monkeypatch):
    """uhr(jahr, monat, tag): die Uhr der App steht auf 10:00 Uhr Berliner Zeit dieses Tages (8:00 UTC im Sommer)."""
    def stellen(y, m, d, hour_utc=8) -> date:
        monkeypatch.setattr(berlin_time, "_utc_now", lambda: datetime(y, m, d, hour_utc, 0, tzinfo=timezone.utc))
        return berlin_today()
    return stellen


def _zahlungsbedingung(db, days=14, skonto_days=7):
    term = PaymentTerm(label=f"{days} Tage, {skonto_days} Tage 2 % Skonto", days=days, skonto_percent=Decimal("2"),
                       skonto_days=skonto_days)
    db.add(term)
    db.commit()
    return term


# ---------------------------------------------------------------------------
# 1: Rechnungsdatum = Tag des Festschreibens, Fälligkeit und Skonto ab diesem Tag
# ---------------------------------------------------------------------------

def test_finalizing_later_sets_the_day_and_moves_due_date_and_cash_discount(uhr):
    db = db_session()
    uhr(2026, 7, 15)
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    update_invoice_payment_term(db, entwurf, _zahlungsbedingung(db).id)
    assert (entwurf.invoice_date, entwurf.due_date) == (date(2026, 7, 15), date(2026, 7, 29))
    heute = uhr(2026, 8, 5)
    invoice = festschreiben(db, entwurf)
    assert (invoice.invoice_date, invoice.due_date) == (heute, date(2026, 8, 19))
    assert "bis zum 19.08.2026" in format_payment_terms_sentence(invoice)
    assert "Bei Zahlung bis zum 12.08.2026" in format_payment_terms_sentence(invoice)  # 05.08. + 7
    assert invoice_to_dict(invoice)["is_overdue"] is False


def test_a_due_date_given_by_hand_keeps_its_distance(uhr):
    """Fälligkeit über die API vorgegeben (die Oberfläche tut das nicht): ihr Abstand zum Datum des Entwurfs bleibt."""
    db = db_session()
    uhr(2026, 7, 15)
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order, due_date=date(2026, 8, 14))  # 30 Tage
    uhr(2026, 9, 1)
    assert festschreiben(db, entwurf).due_date == date(2026, 10, 1)


def test_storno_gets_the_day_of_its_finalizing_and_no_due_date(uhr):
    db = db_session()
    uhr(2026, 7, 15)
    order, _ = make_order_with_item(db)
    original = festschreiben(db, create_schlussrechnung(db, order))
    storno = create_storno_draft(db, original)
    heute = uhr(2026, 7, 20)
    storno = finalize_and_send_invoice(db, storno)
    assert (storno.invoice_date, storno.due_date) == (heute, None)
    assert db.get(Invoice, original.id).invoice_date == date(2026, 7, 15)


def test_the_number_and_the_date_have_the_same_year_on_new_years_eve(uhr):
    db = db_session()
    uhr(2026, 12, 31, hour_utc=12)
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    uhr(2026, 12, 31, hour_utc=23)  # in Berlin 01.01.2027, 0 Uhr
    invoice = festschreiben(db, entwurf)
    assert invoice.invoice_date == date(2027, 1, 1) and invoice.invoice_number.startswith("R-2027-")


def test_the_draft_shows_what_finalizing_today_sets_without_writing(uhr):
    db = db_session()
    uhr(2026, 7, 15)
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    update_invoice_payment_term(db, entwurf, _zahlungsbedingung(db, days=10).id)
    uhr(2026, 7, 20)
    data = invoice_to_dict(entwurf)
    assert data["finalize_dates"] == {"invoice_date": date(2026, 7, 20), "due_date": date(2026, 7, 30), "payment_days": 10}
    assert data["send_hint"] is None
    db.expire_all()
    assert (db.get(Invoice, entwurf.id).invoice_date, db.get(Invoice, entwurf.id).due_date) == (date(2026, 7, 15),
                                                                                               date(2026, 7, 25))


def test_send_hint_only_for_a_finalized_invoice_on_a_later_day(uhr):
    db = db_session()
    uhr(2026, 7, 15)
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    update_invoice_payment_term(db, entwurf, _zahlungsbedingung(db).id)
    invoice = festschreiben(db, entwurf)
    assert invoice_to_dict(invoice)["send_hint"] is None and invoice_to_dict(invoice)["finalize_dates"] is None
    uhr(2026, 7, 20)
    assert invoice_to_dict(invoice)["send_hint"] == (
        "Die Rechnung ist vom 15.07.2026 (Tag des Finalisierens), heute ist der 20.07.2026. Fälligkeit (29.07.2026) und "
        "Skontofrist (bis 22.07.2026) rechnen ab dem Rechnungsdatum, nicht ab dem Versand.")
    assert send_hint(invoice, date(2026, 7, 25)).endswith("Die Skontofrist ist schon abgelaufen.")
    assert send_hint(invoice, date(2026, 8, 1)).endswith("Die Fälligkeit ist schon überschritten.")
    mark_invoice_paid(db, invoice)
    assert invoice_to_dict(invoice)["send_hint"] is None


def test_pdf_shows_the_day_of_finalizing(uhr):
    db = db_session()
    uhr(2026, 7, 15)
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    uhr(2026, 8, 5)
    invoice = festschreiben(db, entwurf)
    text = _extract_pdf_text(build_invoice_pdf(db, invoice))
    assert b"05.08.2026" in text and b"15.07.2026" not in text


# ---------------------------------------------------------------------------
# 2: Bearbeiten nur, was nach der Sperre noch Entwurf ist -- sonst 409
# ---------------------------------------------------------------------------

def _term_id(s, invoice: Invoice | None = None):
    """Eine Zahlungsbedingung -- mit invoice eine andere als die der Rechnung (sonst änderte die Wahl nichts)."""
    stmt = select(PaymentTerm.id).order_by(PaymentTerm.id).limit(1)
    if invoice is not None and invoice.payment_terms:
        stmt = stmt.where(PaymentTerm.label != invoice.payment_terms)
    return s.scalar(stmt)


def _tax_key_id(s):
    return s.scalar(select(TaxKey.id).order_by(TaxKey.id.desc()).limit(1))


EDITS = {
    "kopf": lambda s, inv: update_invoice_header(s, inv, intro_text="Geändert"),
    "zeitraum": lambda s, inv: update_invoice_header(s, inv, service_period_end=date(2026, 9, 29)),
    "zahlungsbedingung": lambda s, inv: update_invoice_payment_term(s, inv, _term_id(s, inv)),
    "steuerschluessel": lambda s, inv: update_invoice_tax_key(s, inv, _tax_key_id(s)),
    "position_neu": lambda s, inv: add_invoice_item(s, inv, short_text="Nachtrag", long_text="", unit="Std.",
                                                    unit_price=Decimal("50"), ist_quantity=Decimal("2")),
    "position_aendern": lambda s, inv: update_invoice_item(s, inv, inv.items[0], ist_quantity=Decimal("50")),
    "position_entfernen": lambda s, inv: remove_invoice_item(s, inv, inv.items[0].id),
}


def _stand(invoice: Invoice) -> tuple:
    """Was eine Änderung an der Rechnung sichtbar machen würde."""
    data = invoice_to_dict(invoice)
    return (data["intro_text"], data["service_period_end"], data["payment_terms"], data["tax_key_id"], data["vat_rate"],
            data["net_total"], data["lump_sum_net"], tuple((i["short_text"], i["ist_quantity"]) for i in data["items"]))


@pytest.mark.parametrize("edit", sorted(EDITS))
def test_editing_a_finalized_invoice_is_rejected_with_its_number(edit):
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = festschreiben(db, create_schlussrechnung(db, order))
    vorher = _stand(invoice)
    with pytest.raises(InvoiceBlocked) as exc:
        EDITS[edit](db, invoice)
    assert str(exc.value) == ("Nur Rechnungen im Entwurf können bearbeitet werden. Die Rechnung ist inzwischen festgeschrieben "
                              f"({invoice.invoice_number}).")
    db.expire_all()
    assert _stand(db.get(Invoice, invoice.id)) == vorher


@pytest.mark.parametrize("edit", sorted(EDITS))
def test_editing_a_draft_still_works(edit):
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = mit_zeitraum(db, create_schlussrechnung(db, order))
    vorher = _stand(invoice)
    EDITS[edit](db, invoice)
    db.expire_all()
    assert _stand(db.get(Invoice, invoice.id)) != vorher


def test_editing_a_draft_deleted_meanwhile_is_rejected():
    """Die Rechnung wurde in einer anderen Sitzung gelöscht; diese hält noch ihr Objekt (wie ein Router vor der Sperre)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    andere = sessionmaker(bind=db.get_bind())()
    delete_invoice_draft(andere, andere.get(Invoice, invoice.id))
    andere.close()
    with pytest.raises(InvoiceBlocked, match="^Der Entwurf wurde inzwischen gelöscht.$"):
        update_invoice_header(db, invoice, intro_text="x")


def test_edit_routes_answer_409_for_a_finalized_invoice(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    client = router_test_client(db, invoices_router)
    invoice_id = client.post(f"/api/orders/{order.id}/invoices/schlussrechnung", json={}).json()["id"]
    client.put(f"/api/invoices/{invoice_id}", json=ZEITRAUM_JSON)
    item_id = client.get(f"/api/invoices/{invoice_id}").json()["items"][0]["id"]
    number = client.post(f"/api/invoices/{invoice_id}/send").json()["invoice_number"]
    antworten = {
        "kopf": client.put(f"/api/invoices/{invoice_id}", json={"intro_text": "x"}),
        "zahlungsbedingung": client.put(f"/api/invoices/{invoice_id}/payment-term", json={"payment_term_id": _term_id(db)}),
        "steuerschluessel": client.put(f"/api/invoices/{invoice_id}/tax-key", json={"tax_key_id": _tax_key_id(db)}),
        "position_neu": client.post(f"/api/invoices/{invoice_id}/items", json={
            "short_text": "x", "long_text": "", "unit": "Std.", "unit_price": "1", "ist_quantity": "1"}),
        "position_aendern": client.put(f"/api/invoices/{invoice_id}/items/{item_id}", json={"ist_quantity": "1"}),
        "position_entfernen": client.delete(f"/api/invoices/{invoice_id}/items/{item_id}"),
    }
    assert {k: (r.status_code, number in r.json()["detail"]) for k, r in antworten.items()} == {
        k: (409, True) for k in antworten}


def test_time_based_invoice_is_created_under_the_lock():
    """Rechnung aus Aufwand anlegen nimmt die Sperre (geprüft am Beobachter) -- ohne eigene Regel, auch nach der
    Schlussrechnung (Festlegung 1.8.72 Nr. 3)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    _buchung(db, order)
    with Beobachter(db) as b:
        invoice = create_invoice_from_time_entries(db, db.get(Order, order.id), list_entries(db, order_id=order.id, limit=None), [])
    assert invoice.invoice_type == "aufwand" and b.schreibt >= 1 and b.verstoesse == []


def _buchung(db, order, tag=date(2026, 9, 2)):
    employee = db.scalar(select(Employee).limit(1))
    if employee is None:
        employee = Employee(first_name="Mona", last_name="Monteurin", active=True)
        db.add(employee)
        db.flush()
    db.add(TimeEntry(employee_id=employee.id, project_id=order.project_id, order_id=order.id, work_date=tag,
                     entry_type="site", status="booked", hours=Decimal("4")))
    db.commit()


# ---------------------------------------------------------------------------
# Strukturtest (1): jede öffentliche Funktion in app/invoices.py, die schreibt, sperrt vorher
# ---------------------------------------------------------------------------

LOCKS = {"lock_order_invoices"}
DB_WRITES = {"add", "add_all", "delete", "flush", "commit", "merge"}
WRITING_CALLS = {"issue_number", "mark_document_sent", "setattr", "Invoice", "InvoiceItem"}
# Öffentliche Funktionen, die ohne Sperre schreiben dürfen -- mit Grund; darf nur kürzer werden.
OHNE_SPERRE: dict[str, str] = {}


def _call_name(node: ast.Call) -> str | None:
    return getattr(node.func, "id", None) or getattr(node.func, "attr", None)


def _events(fn: ast.FunctionDef, module_funcs: dict) -> list[tuple[int, int, str, str]]:
    """(Zeile, Spalte, Art, Name) je Sperre, Schreibvorgang und Aufruf einer Hilfsfunktion des Moduls, in Quelltext-Reihenfolge."""
    found = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in LOCKS:
                found.append((node.lineno, node.col_offset, "sperre", name))
            elif isinstance(node.func, ast.Attribute) and name in DB_WRITES and getattr(node.func.value, "id", "") == "db":
                found.append((node.lineno, node.col_offset, "schreibt", f"db.{name}"))
            elif name in WRITING_CALLS:
                found.append((node.lineno, node.col_offset, "schreibt", name))
            elif isinstance(node.func, ast.Attribute) and name == "remove" and getattr(node.func.value, "attr", "") == "items":
                found.append((node.lineno, node.col_offset, "schreibt", ".items.remove"))
            elif isinstance(node.func, ast.Name) and name in module_funcs and name != fn.name:
                found.append((node.lineno, node.col_offset, "ruft", name))
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for t in (target.elts if isinstance(target, ast.Tuple) else [target]):
                    if isinstance(t, ast.Attribute):
                        found.append((node.lineno, node.col_offset, "schreibt", f".{t.attr} ="))
    return sorted(found)


def analyse_invoices_module(source: str) -> dict[str, dict]:
    """Je Funktion: schreibt sie (selbst oder über eine Hilfsfunktion, die nicht selbst zuerst sperrt), sperrt sie, und steht
    vor der ersten Sperre ein Schreibvorgang?"""
    tree = ast.parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    result: dict[str, dict] = {}

    def info(name: str, stack=()) -> dict:
        if name in result:
            return result[name]
        if name in stack:
            return {"schreibt": False, "sperrt": False, "zuerst_geschrieben": None}
        first_lock = first_write = None
        writes = locks = False
        for line, _, kind, what in _events(funcs[name], funcs):
            if kind == "ruft":
                callee = info(what, stack + (name,))
                if callee["sperrt"]:
                    kind = "sperre"
                elif callee["schreibt"]:
                    kind = "schreibt"
                else:
                    continue
            if kind == "sperre":
                locks = True
                first_lock = first_lock or line
            else:
                writes = True
                if first_lock is None and first_write is None:
                    first_write = f"Zeile {line}: {what}"
        data = {"schreibt": writes, "sperrt": locks, "zuerst_geschrieben": first_write}
        result[name] = data
        return data

    for name in funcs:
        info(name)
    return result


def test_every_public_writer_in_invoices_locks_before_it_writes():
    funcs = analyse_invoices_module((APP / "invoices.py").read_text(encoding="utf-8"))
    writers = {name for name, d in funcs.items() if not name.startswith("_") and d["schreibt"]}
    # Die Suche läuft nicht ins Leere: diese schreiben bekanntlich (Stand 1.8.75).
    assert writers >= {
        "create_abschlag_pauschal", "create_abschlag_leistungsstand", "create_schlussrechnung", "create_invoice_from_time_entries",
        "add_invoice_item", "update_invoice_item", "remove_invoice_item", "finalize_and_send_invoice", "mark_invoice_paid",
        "delete_invoice_draft", "create_storno_draft", "update_invoice_header", "update_invoice_payment_term",
        "update_invoice_tax_key", "send_invoice_email",
    }, writers
    ohne = sorted(f"{n}: schreibt ohne Sperre" for n in writers if not funcs[n]["sperrt"] and n not in OHNE_SPERRE)
    zuerst = sorted(f"{n}: {funcs[n]['zuerst_geschrieben']} vor der Sperre" for n in writers
                    if funcs[n]["sperrt"] and funcs[n]["zuerst_geschrieben"] and n not in OHNE_SPERRE)
    assert ohne + zuerst == [], "Schreibende Wege an einer Rechnung ohne die Sperre der Auftragszeile:\n" + "\n".join(ohne + zuerst)
    assert sorted(set(OHNE_SPERRE) - writers) == [], "OHNE_SPERRE ohne Fund -- streichen"


def test_the_analysis_catches_a_write_before_the_lock():
    source = '''
def _hilfe(db, invoice):
    invoice.status = "x"
def ohne(db, invoice):
    _hilfe(db, invoice)
def davor(db, invoice):
    invoice.intro_text = "x"
    lock_order_invoices(db, invoice.order_id)
def danach(db, invoice):
    lock_order_invoices(db, invoice.order_id)
    _hilfe(db, invoice)
    db.commit()
def ueber_hilfe(db, invoice):
    _sperre(db, invoice)
    db.add(InvoiceItem())
def _sperre(db, invoice):
    lock_order_invoices(db, invoice.order_id)
'''
    funcs = analyse_invoices_module(source)
    assert (funcs["ohne"]["schreibt"], funcs["ohne"]["sperrt"]) == (True, False)
    assert funcs["davor"]["zuerst_geschrieben"] == "Zeile 7: .intro_text ="
    assert (funcs["danach"]["sperrt"], funcs["danach"]["zuerst_geschrieben"]) == (True, None)
    assert (funcs["ueber_hilfe"]["sperrt"], funcs["ueber_hilfe"]["zuerst_geschrieben"]) == (True, None)


# ---------------------------------------------------------------------------
# Strukturtest (2): außerhalb von app/invoices.py schreibt niemand eine Rechnung
# ---------------------------------------------------------------------------

INVOICE_FIELDS = {c.key for c in Invoice.__table__.columns} | {c.key for c in InvoiceItem.__table__.columns}
# Dateien, deren "invoice"-Variablen keine Rechnungen (Invoice) sind -- mit Grund.
FREMDE_RECHNUNGEN = {"incoming_invoices.py": "Eingangsrechnungen (IncomingInvoice), Buchhaltung"}


def test_nobody_outside_invoices_creates_or_writes_an_invoice():
    found = []
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP).as_posix()
        if rel in ("invoices.py", "models.py") or rel in FREMDE_RECHNUNGEN:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name in ("Invoice", "InvoiceItem"):
                    found.append(f"{rel}:{node.lineno} {name}(...)")
                if name in ("update", "delete", "insert") and node.args and getattr(node.args[0], "id", "") in (
                        "Invoice", "InvoiceItem"):
                    found.append(f"{rel}:{node.lineno} {name}({node.args[0].id})")
            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    base = getattr(getattr(target, "value", None), "id", "") or ""
                    if isinstance(target, ast.Attribute) and "invoice" in base.lower() and target.attr in INVOICE_FIELDS:
                        found.append(f"{rel}:{node.lineno} {base}.{target.attr} =")
    assert found == [], "Rechnungen nur über app/invoices.py schreiben (dort unter der Sperre):\n" + "\n".join(found)


# ---------------------------------------------------------------------------
# Strukturtest (3): Rundgang über jeden schreibenden Endpunkt der Rechnungen, mit Beobachter an der Sitzung
# ---------------------------------------------------------------------------

class Beobachter:
    """Hält jede geschriebene Rechnung bzw. Position gegen die Sperre ihres Auftrags: die Sperre ist die Abfrage
    "SELECT orders ... FOR UPDATE" (app/acceptances.py::lock_order(), über lock_order_invoices()); sie gilt bis zum Ende der
    Transaktion. Auch unter SQLite sichtbar -- dort wird FOR UPDATE nur nicht gesendet."""

    def __init__(self, session):
        self.session = session
        self.gesperrt: set[int] = set()
        self.verstoesse: list[str] = []
        self.schreibt = 0
        self.route = ""

    def __enter__(self):
        event.listen(self.session, "do_orm_execute", self._ausfuehren)
        event.listen(self.session, "before_flush", self._schreiben)
        for name in ("after_commit", "after_rollback", "after_soft_rollback"):
            event.listen(self.session, name, self._ende)
        return self

    def __exit__(self, *exc):
        event.remove(self.session, "do_orm_execute", self._ausfuehren)
        event.remove(self.session, "before_flush", self._schreiben)
        for name in ("after_commit", "after_rollback", "after_soft_rollback"):
            event.remove(self.session, name, self._ende)

    def _ausfuehren(self, state):
        stmt = state.statement
        if getattr(stmt, "_for_update_arg", None) is None:
            return
        if any(getattr(t, "name", None) == "orders" for t in stmt.get_final_froms()):
            self.gesperrt.update(v for v in stmt.compile().params.values() if isinstance(v, int))

    def _ende(self, session, *args):
        self.gesperrt.clear()

    def _schreiben(self, session, context, instances):
        with session.no_autoflush:
            objekte = [o for o in session.new | session.deleted if isinstance(o, (Invoice, InvoiceItem))]
            objekte += [o for o in session.dirty if isinstance(o, (Invoice, InvoiceItem)) and session.is_modified(o)]
            if not objekte:
                return
            self.schreibt += 1
            for o in objekte:
                if isinstance(o, Invoice):
                    order_id = o.order_id
                else:
                    rechnung = o.invoice or session.get(Invoice, o.invoice_id)
                    order_id = rechnung.order_id if rechnung is not None else None
                if order_id not in self.gesperrt:
                    self.verstoesse.append(f"{self.route}: {type(o).__name__} ohne Sperre des Auftrags {order_id}")


def _welt():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    order, _ = make_order_with_item(db)
    _buchung(db, order)
    order.project.customer.email = "kunde@example.com"
    db.commit()
    update_smtp_settings(db, host="smtp.example.com", port=587, username="buero@example.com", encryption="starttls",
                         sender_email="buero@example.com", sender_name="Test GmbH", password="geheim123")
    return db, order.id


def _entwurf(c, order_id, art="schlussrechnung"):
    invoice_id = c.post(f"/api/orders/{order_id}/invoices/{art}", json={}).json()["id"]
    c.put(f"/api/invoices/{invoice_id}", json=ZEITRAUM_JSON)
    return invoice_id


def _festgeschrieben(c, order_id):
    invoice_id = _entwurf(c, order_id)
    assert c.post(f"/api/invoices/{invoice_id}/send").status_code == 200
    return invoice_id


def _erste_position(c, invoice_id):
    return c.get(f"/api/invoices/{invoice_id}").json()["items"][0]["id"]


def _sz_entwurf(aktion):
    """Szenario an einem Entwurf: aktion(client, invoice_id, db)."""
    def vorbereiten(c, order_id, db):
        invoice_id = _entwurf(c, order_id)
        return lambda: aktion(c, invoice_id, db)
    return vorbereiten


def _sz_fest(aktion):
    def vorbereiten(c, order_id, db):
        invoice_id = _festgeschrieben(c, order_id)
        return lambda: aktion(c, invoice_id, db)
    return vorbereiten


SZENARIEN = {
    ("POST", "/api/orders/{order_id}/invoices/abschlag-pauschal"):
        lambda c, o, db: lambda: c.post(f"/api/orders/{o}/invoices/abschlag-pauschal", json={"lump_sum_net": "100"}),
    ("POST", "/api/orders/{order_id}/invoices/abschlag-leistungsstand"):
        lambda c, o, db: lambda: c.post(f"/api/orders/{o}/invoices/abschlag-leistungsstand", json={}),
    ("POST", "/api/orders/{order_id}/invoices/schlussrechnung"):
        lambda c, o, db: lambda: c.post(f"/api/orders/{o}/invoices/schlussrechnung", json={}),
    ("POST", "/api/orders/{order_id}/invoices/aus-zeitbuchungen"):
        lambda c, o, db: lambda: c.post(f"/api/orders/{o}/invoices/aus-zeitbuchungen", json={}),
    ("PUT", "/api/invoices/{invoice_id}"): _sz_entwurf(lambda c, i, db: c.put(f"/api/invoices/{i}", json={"intro_text": "x"})),
    ("PUT", "/api/invoices/{invoice_id}/payment-term"): _sz_entwurf(
        lambda c, i, db: c.put(f"/api/invoices/{i}/payment-term", json={"payment_term_id": _term_id(db, db.get(Invoice, i))})),
    ("PUT", "/api/invoices/{invoice_id}/tax-key"): _sz_entwurf(
        lambda c, i, db: c.put(f"/api/invoices/{i}/tax-key", json={"tax_key_id": _tax_key_id(db)})),
    ("POST", "/api/invoices/{invoice_id}/items"): _sz_entwurf(lambda c, i, db: c.post(f"/api/invoices/{i}/items", json={
        "short_text": "Nachtrag", "long_text": "", "unit": "Std.", "unit_price": "50", "ist_quantity": "2"})),
    ("PUT", "/api/invoices/{invoice_id}/items/{item_id}"): _sz_entwurf(
        lambda c, i, db: c.put(f"/api/invoices/{i}/items/{_erste_position(c, i)}", json={"ist_quantity": "7"})),
    ("DELETE", "/api/invoices/{invoice_id}/items/{item_id}"): _sz_entwurf(
        lambda c, i, db: c.delete(f"/api/invoices/{i}/items/{_erste_position(c, i)}")),
    ("POST", "/api/invoices/{invoice_id}/send"): _sz_entwurf(lambda c, i, db: c.post(f"/api/invoices/{i}/send")),
    ("POST", "/api/invoices/{invoice_id}/send-email"): _sz_fest(lambda c, i, db: c.post(
        f"/api/invoices/{i}/send-email", json={"dispatch_key": "rundgang-rechnung-1"})),
    ("POST", "/api/invoices/{invoice_id}/mark-paid"): _sz_fest(lambda c, i, db: c.post(f"/api/invoices/{i}/mark-paid", json={})),
    ("POST", "/api/invoices/{invoice_id}/storno"): _sz_fest(lambda c, i, db: c.post(f"/api/invoices/{i}/storno")),
    ("DELETE", "/api/invoices/{invoice_id}"): _sz_entwurf(lambda c, i, db: c.delete(f"/api/invoices/{i}")),
}


def _schreibende_routen():
    return {(m, r.path) for r in invoices_router.routes for m in r.methods if m not in ("GET", "HEAD")}


def test_every_writing_invoice_route_has_a_scenario():
    assert sorted(_schreibende_routen() - set(SZENARIEN)) == [], "neuer schreibender Endpunkt ohne Szenario im Rundgang"
    assert sorted(set(SZENARIEN) - _schreibende_routen()) == [], "Szenario ohne Endpunkt -- streichen"


@pytest.mark.parametrize("route", sorted(SZENARIEN), ids=lambda r: f"{r[0]} {r[1]}")
@patch("app.email_sending.smtplib.SMTP")
def test_every_writing_invoice_route_writes_only_under_the_lock(_smtp, route, router_test_client):
    db, order_id = _welt()
    try:
        client = router_test_client(db, invoices_router)
        aktion = SZENARIEN[route](client, order_id, db)
        with Beobachter(db) as b:
            b.route = f"{route[0]} {route[1]}"
            antwort = aktion()
        assert antwort.status_code == 200, antwort.text
        assert b.schreibt >= 1, "Szenario schreibt keine Rechnung -- prüft nichts"
        assert b.verstoesse == []
    finally:
        db.close()


def test_the_observer_sees_a_write_without_the_lock():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    with Beobachter(db) as b:
        invoice.intro_text = "ohne Sperre"
        db.commit()
    assert b.verstoesse == [f": Invoice ohne Sperre des Auftrags {order.id}"]
    with Beobachter(db) as b:
        update_invoice_header(db, invoice, intro_text="mit Sperre")
    assert (b.schreibt, b.verstoesse) == (1, [])


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL
# ---------------------------------------------------------------------------

def _pg_entwurf(Session, order_id):
    return _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)


def _pg_stand(Session, invoice_id):
    return _vorbereiten(Session, lambda s: _stand(s.get(Invoice, invoice_id)))


@pytest.mark.parametrize("edit", sorted(EDITS))
def test_postgresql_edit_waits_for_finalizing_and_is_rejected(pg, edit):
    """Vorher (bis 1.8.74) wartete die Änderung nicht und schrieb in die eben festgeschriebene Rechnung."""
    Session, order_id = pg
    invoice_id = _pg_entwurf(Session, order_id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number,
                         lambda s: EDITS[edit](s, s.get(Invoice, invoice_id)))
    assert isinstance(second, InvoiceBlocked) and f"inzwischen festgeschrieben ({first})" in str(second), second
    nachher = _vorbereiten(Session, lambda s: (s.get(Invoice, invoice_id).status, _stand(s.get(Invoice, invoice_id))))
    assert nachher[0] == "versendet"


def test_postgresql_finalized_invoice_is_exactly_the_one_after_the_edit(pg):
    """Umgekehrt: das Festschreiben wartet auf eine laufende Änderung und schreibt deren Stand fest."""
    Session, order_id = pg
    invoice_id = _pg_entwurf(Session, order_id)
    vorher = _pg_stand(Session, invoice_id)
    first, second = _run(Session, lambda s: EDITS["position_aendern"](s, s.get(Invoice, invoice_id)) and "geaendert",
                         lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number)
    assert isinstance(second, str), second
    nachher = _pg_stand(Session, invoice_id)
    assert nachher != vorher and nachher[-1][0][1] == Decimal("50")


def test_postgresql_edit_waits_for_the_delete_and_is_rejected(pg):
    Session, order_id = pg
    invoice_id = _pg_entwurf(Session, order_id)
    _, second = _run(Session, lambda s: delete_invoice_draft(s, s.get(Invoice, invoice_id)) or "geloescht",
                     lambda s: EDITS["position_neu"](s, s.get(Invoice, invoice_id)))
    assert isinstance(second, InvoiceBlocked) and str(second) == "Der Entwurf wurde inzwischen gelöscht.", second
    assert _vorbereiten(Session, lambda s: s.scalar(select(InvoiceItem.id).where(InvoiceItem.invoice_id == invoice_id))) is None


def test_postgresql_second_edit_of_a_position_computes_with_the_first(pg):
    """Zwei Änderungen derselben Position: die zweite (nur der Preis) rechnet nach der Sperre mit der Menge der ersten --
    nicht mit der vorher geladenen."""
    Session, order_id = pg
    invoice_id = _pg_entwurf(Session, order_id)

    def preis(s):
        invoice = s.get(Invoice, invoice_id)
        item = invoice.items[0]
        return update_invoice_item(s, invoice, item, unit_price=Decimal("60")).billed_total

    _, second = _run(Session, lambda s: update_invoice_item(s, s.get(Invoice, invoice_id), s.get(Invoice, invoice_id).items[0],
                                                             ist_quantity=Decimal("4")) and "menge", preis)
    assert second == Decimal("240"), second  # 4 x 60, nicht 100 x 60


def test_postgresql_time_based_invoice_waits_for_the_lock(pg):
    """Zeigt nur das Warten -- das täte das Anlegen unter PostgreSQL auch ohne die Sperre (die neue Zeile prüft ihren
    Fremdschlüssel auf die gesperrte Auftragszeile, FOR KEY SHARE gegen FOR UPDATE; Gegenprobe 1.8.75). Dass die Sperre genommen
    wird, prüfen der Strukturtest und test_time_based_invoice_is_created_under_the_lock."""
    Session, order_id = pg
    _vorbereiten(Session, lambda s: _buchung(s, s.get(Order, order_id)))
    invoice_id = _pg_entwurf(Session, order_id)

    def aufwand(s):
        order = s.get(Order, order_id)
        return create_invoice_from_time_entries(s, order, list_entries(s, order_id=order_id, limit=None), []).invoice_type

    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number, aufwand)
    assert second == "aufwand", second


def test_postgresql_lump_sum_edit_waits_for_finalizing(pg):
    """Pauschaler Abschlag: Betrag ändern gegen Festschreiben -- der festgeschriebene Betrag bleibt."""
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_abschlag_pauschal(
        s, s.get(Order, order_id), lump_sum_net=Decimal("1000"))).id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number,
                         lambda s: update_invoice_header(s, s.get(Invoice, invoice_id), lump_sum_net=Decimal("5000")))
    assert isinstance(second, InvoiceBlocked), second
    assert _vorbereiten(Session, lambda s: s.get(Invoice, invoice_id).lump_sum_net) == Decimal("1000")
