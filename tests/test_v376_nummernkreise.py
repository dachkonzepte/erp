"""Nummernvergabe atomar je Nummernkreis, Entwurf löschen unter der Sperre (seit 1.8.73; Nebenbefunde 1 und 2 aus 1.8.72,
docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.73").

- app/settings.py::issue_number() sperrt die Zeile des Nummernkreises bis zum Commit (_lock_sequence(): UPDATE ohne Änderung --
  Zeilensperre unter PostgreSQL, Schreibsperre unter SQLite). Alle sieben Nummernkreise vergeben darüber; Kunde, Anfrage,
  Projekt und Angebot nahmen bis 1.8.72 nur die Vorschau.
- Rechnungs- und Mahnungsentwurf löschen unter derselben Sperre wie das Festschreiben (Auftragszeile): gelöscht wird nur, was
  danach noch Entwurf ist, sonst 409; ein gleichzeitig gelöschter Entwurf wird nicht mehr festgeschrieben.

Die Gleichzeitigkeit prüfen die Tests mit pg gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in) und die mit
sqlite_datei gegen eine SQLite-Datei mit zwei Verbindungen: die erste Aktion hält ihren Commit eine Sekunde an, die zweite
startet währenddessen, wartet und findet danach den Stand der ersten."""

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.invoices import (
    InvoiceBlocked,
    create_schlussrechnung,
    delete_invoice_draft,
    finalize_and_send_invoice,
)
from app.models import Invoice, NumberSequence, Order, Reminder
from app.projects import next_project_number, next_quote_number
from app.reminders import create_reminder, delete_reminder_draft, finalize_and_send_reminder
from app.routers.invoices import router as invoices_router
from app.routers.reminders import router as reminders_router
from app.settings import DEFAULT_SEQUENCES, issue_number, load_sequence
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)
from tests.leistungszeitraum import festschreiben, mit_zeitraum

ROOT = Path(__file__).resolve().parent.parent


def _next_value(Session, key):
    return _vorbereiten(Session, lambda s: s.scalar(select(NumberSequence.next_value)
                                                     .where(NumberSequence.sequence_key == key)))


def _gesperrt(fn, *args, **kwargs) -> str:
    with pytest.raises(InvoiceBlocked) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


# ---------------------------------------------------------------------------
# Vergabe: Hochzählen, Rückrollen, alle Nummernkreise über issue_number()
# ---------------------------------------------------------------------------

def test_project_and_quote_numbers_are_issued_not_previewed():
    """Bis 1.8.72 gaben zwei Aufrufe ohne Anlegen dazwischen dieselbe Nummer (Vorschau) -- jetzt zwei verschiedene."""
    db = db_session()
    from app.grunddaten import anlegen
    anlegen(db)
    db.commit()
    assert next_project_number(db) != next_project_number(db)
    assert next_quote_number(db) != next_quote_number(db)


def test_a_rolled_back_number_is_not_used_up():
    db = db_session()
    from app.grunddaten import anlegen
    anlegen(db)
    db.commit()
    erste = issue_number(db, "invoice")
    db.rollback()
    assert issue_number(db, "invoice") == erste


def test_nothing_issues_numbers_through_the_preview():
    """preview_number() ist nur Anzeige: aufgerufen nur in den Vorschau-Funktionen und den Einstellungs-Routen -- eine neue
    Vergabe über die Vorschau fiele hier auf (so liefen Kunde, Anfrage, Projekt und Angebot bis 1.8.72)."""
    erlaubt = {("app/crm.py", "customer_number_preview"), ("app/routers/settings.py", "list_number_sequences"),
               ("app/routers/settings.py", "put_number_sequence"), ("app/routers/settings.py", "get_number_preview")}
    gefunden = set()
    for path in (ROOT / "app").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name != "preview_number":
                for node in ast.walk(fn):
                    if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "preview_number":
                        gefunden.add((rel, fn.name))
    assert gefunden == erlaubt


# ---------------------------------------------------------------------------
# Entwurf löschen: nur, was noch Entwurf ist (409)
# ---------------------------------------------------------------------------

def test_deleting_a_finalized_invoice_or_reminder_is_409_with_its_number(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice = make_sent_overdue_invoice(db)
    mahnung = finalize_and_send_reminder(db, create_reminder(db, invoice, 1))
    client = router_test_client(db, invoices_router, reminders_router)
    antwort = client.delete(f"/api/invoices/{invoice.id}")
    assert antwort.status_code == 409 and antwort.json()["detail"] == (
        f"Nur Rechnungen im Entwurf können gelöscht werden. Die Rechnung ist inzwischen festgeschrieben "
        f"({invoice.invoice_number}).")
    antwort = client.delete(f"/api/reminders/{mahnung.id}")
    assert antwort.status_code == 409 and mahnung.reminder_number in antwort.json()["detail"]
    db.expire_all()
    assert db.get(Invoice, invoice.id) is not None and db.get(Reminder, mahnung.id) is not None


def test_deleting_drafts_still_works():
    db = db_session()
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    delete_invoice_draft(db, entwurf)
    assert db.scalar(select(func.count()).select_from(Invoice)) == 0
    invoice = make_sent_overdue_invoice(db, suffix="0002")
    mahnung = create_reminder(db, invoice, 1)
    delete_reminder_draft(db, mahnung)
    assert db.scalar(select(func.count()).select_from(Reminder)) == 0


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL
# ---------------------------------------------------------------------------

def _nummer(key, vorher_geladen=False):
    """Nummer ziehen und committen -- wie jeder Aufrufer, der den Datensatz danach speichert. vorher_geladen: die Sitzung
    hält den Nummernkreis schon (alter Stand) -- dann muss die Vergabe ihn nach der Sperre frisch lesen."""
    def action(s):
        # festgehalten: die Sitzung hält unveränderte Objekte nur schwach -- ohne Referenz wäre es weggeräumt und neu geladen
        alt = load_sequence(s, key) if vorher_geladen else None
        number = issue_number(s, key)
        s.commit()
        assert alt is None or alt.sequence_key == key
        return number
    return action


@pytest.mark.parametrize("key", sorted(DEFAULT_SEQUENCES))
def test_postgresql_two_numbers_of_one_sequence_at_once_differ(pg, key):
    Session, _ = pg
    vorher = _next_value(Session, key)
    first, second = _run(Session, _nummer(key), _nummer(key, vorher_geladen=True))
    assert isinstance(second, str) and second != first, (first, second)
    assert _next_value(Session, key) == vorher + 2


def _zweiter_auftrag(Session):
    from tests.test_v325_contract_basis import beauftragen, make_quote
    return _vorbereiten(Session, lambda s: beauftragen(s, make_quote(s, is_consumer=False, number="0002")).id)


def test_postgresql_two_orders_finalized_at_once_get_different_numbers(pg):
    """Der Nachweis aus 1.8.72 (Nebenbefund 1): vorher beide R-2026-0001."""
    Session, order_id = pg
    zweiter = _zweiter_auftrag(Session)
    ids = [_vorbereiten(Session, lambda s, o=o: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, o))).id)
           for o in (order_id, zweiter)]
    first, second = _run(Session, lambda s: festschreiben(s, s.get(Invoice, ids[0])).invoice_number,
                         lambda s: festschreiben(s, s.get(Invoice, ids[1])).invoice_number)
    assert isinstance(second, str) and first != second, (first, second)
    nummern = _vorbereiten(Session, lambda s: sorted(s.scalars(select(Invoice.invoice_number)).all()))
    assert nummern == sorted([first, second])


def test_postgresql_delete_waits_for_finalizing_and_is_rejected(pg):
    """Der Nachweis aus 1.8.72 (Nebenbefund 2): vorher löschte das DELETE die eben festgeschriebene Rechnung."""
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, lambda s: festschreiben(s, s.get(Invoice, invoice_id)).invoice_number,
                         lambda s: delete_invoice_draft(s, s.get(Invoice, invoice_id)))
    assert isinstance(second, InvoiceBlocked) and f"inzwischen festgeschrieben ({first})" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Invoice, invoice_id).invoice_number) == first


def test_postgresql_finalizing_waits_for_the_delete_and_uses_no_number(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    vorher = _next_value(Session, "invoice")
    _, second = _run(Session, lambda s: delete_invoice_draft(s, s.get(Invoice, invoice_id)) or "geloescht",
                     lambda s: festschreiben(s, s.get(Invoice, invoice_id)))
    assert isinstance(second, InvoiceBlocked) and str(second) == "Der Entwurf wurde inzwischen gelöscht.", second
    assert _vorbereiten(Session, lambda s: s.get(Invoice, invoice_id)) is None
    assert _next_value(Session, "invoice") == vorher


def _mahnungsentwurf(Session, order_id):
    def build(s):
        schluss = create_schlussrechnung(s, s.get(Order, order_id), due_date=date.today() - timedelta(days=20))
        return create_reminder(s, festschreiben(s, schluss), 1).id
    return _vorbereiten(Session, build)


def test_postgresql_reminder_delete_waits_for_finalizing_and_is_rejected(pg):
    Session, order_id = pg
    reminder_id = _mahnungsentwurf(Session, order_id)
    first, second = _run(Session, lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)).reminder_number,
                         lambda s: delete_reminder_draft(s, s.get(Reminder, reminder_id)))
    assert isinstance(second, InvoiceBlocked) and first in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Reminder, reminder_id).reminder_number) == first


def test_postgresql_reminder_finalizing_waits_for_the_delete_and_uses_no_number(pg):
    Session, order_id = pg
    reminder_id = _mahnungsentwurf(Session, order_id)
    vorher = _next_value(Session, "reminder")
    _, second = _run(Session, lambda s: delete_reminder_draft(s, s.get(Reminder, reminder_id)) or "geloescht",
                     lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)))
    assert isinstance(second, InvoiceBlocked) and str(second) == "Der Mahnungsentwurf wurde inzwischen gelöscht.", second
    assert _next_value(Session, "reminder") == vorher


# ---------------------------------------------------------------------------
# Gleichzeitig: SQLite-Datei (Entwicklung) -- dieselbe Sperre über die Schreibsperre der Datenbank
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_datei(tmp_path):
    from app.grunddaten import anlegen

    engine = create_engine(f"sqlite:///{tmp_path / 'nummern.db'}", connect_args={"check_same_thread": False, "timeout": 15})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    anlegen(s)
    s.commit()
    s.close()
    yield Session
    engine.dispose()


@pytest.mark.parametrize("key", ["invoice", "project"])
def test_sqlite_two_numbers_of_one_sequence_at_once_differ(sqlite_datei, key):
    Session = sqlite_datei
    vorher = _next_value(Session, key)
    first, second = _run(Session, _nummer(key), _nummer(key, vorher_geladen=True))
    assert isinstance(second, str) and second != first, (first, second)
    assert _next_value(Session, key) == vorher + 2
    assert second.endswith(str(vorher + 1).zfill(4)), second
