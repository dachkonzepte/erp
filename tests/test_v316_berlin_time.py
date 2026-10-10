"""Version 1.8.12 -- Geschäftsdatum und Uhrzeiten ausdrücklich in Europe/Berlin (app/berlin_time.py).

Der Server läuft in UTC, der Entwicklungsrechner in deutscher Zeit; die Fehler dieser Klasse
fallen lokal deshalb nicht auf. Die Tests hier hängen nicht von der Zeitzone des Rechners ab:
Die Uhr steht fest auf einem UTC-Zeitpunkt (app.berlin_time._utc_now), gespeicherte Zeitstempel
werden als naive UTC gesetzt. Die Fixture utc_server stellt zusätzlich die Uhr eines Servers in
UTC nach (date.today()/datetime.now() liefern dort die UTC-Wanduhr) -- nur damit die Gegenprobe
gegen den alten Code aus dem richtigen Grund rot wird.

Textprüfung der PDFs nur mit ASCII-Teilstrings (_extract_pdf_text, siehe test_v213)."""

import ast
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app import berlin_time
from app.berlin_time import berlin_now, berlin_today, to_berlin
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v305_checklist_filling import world  # noqa: F401  (Fixture)

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
SILVESTER_UTC = datetime(2026, 12, 31, 23, 30)  # in Berlin schon 01.01.2027, 0:30 Uhr


@pytest.fixture
def utc_server(monkeypatch):
    """utc_server(zeitpunkt_utc, *module): Uhr fest auf den naiven UTC-Zeitpunkt stellen. In den
    genannten Modulen liefern date.today()/datetime.now() dazu die UTC-Wanduhr, wie auf dem VPS
    (Etc/UTC). Der neue Code ruft beides nicht mehr auf; die Module braucht nur die Gegenprobe."""
    def set_clock(utc_naive: datetime, *modules) -> None:
        monkeypatch.setattr(berlin_time, "_utc_now", lambda: utc_naive.replace(tzinfo=timezone.utc))

        class ServerDate(date):
            @classmethod
            def today(cls):
                return utc_naive.date()

        class ServerDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_naive if tz is None else utc_naive.replace(tzinfo=timezone.utc).astimezone(tz)

        for module in modules:
            if isinstance(getattr(module, "date", None), type):
                monkeypatch.setattr(module, "date", ServerDate)
            if isinstance(getattr(module, "datetime", None), type):
                monkeypatch.setattr(module, "datetime", ServerDatetime)
    return set_clock


# ---------------------------------------------------------------------------
# 1. Kein date.today()/datetime.now() ohne Zeitzone unter app/
# ---------------------------------------------------------------------------

def _clock_class_resolver(tree):
    """Funktion expr -> "date"/"datetime"/None, mit den Aliassen der Datei (from datetime import date as
    _date, import datetime as dt)."""
    classes, modules = {"date": "date", "datetime": "datetime"}, {"datetime"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for alias in node.names:
                if alias.name in ("date", "datetime"):
                    classes[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "datetime"}

    def clock_class(expr) -> str | None:
        if isinstance(expr, ast.Name):
            return classes.get(expr.id)
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id in modules:
            return expr.attr if expr.attr in ("date", "datetime") else None
        return None
    return clock_class


def _reads_local_clock(cls: str | None, attr: str) -> bool:
    return cls is not None and (attr == "today" or (attr == "now" and cls == "datetime"))


def local_clock_calls(source: str, filename: str = "<quelle>") -> list[int]:
    """Zeilen aller Aufrufe, die die Uhr des Rechners lesen: date.today(), datetime.today(),
    datetime.now() ohne tz -- auch über Aliasse (from datetime import date as _date,
    import datetime as dt). datetime.utcnow() bleibt erlaubt, es liefert UTC."""
    tree = ast.parse(source, filename)
    clock_class = _clock_class_resolver(tree)
    lines = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        cls, attr = clock_class(node.func.value), node.func.attr
        if cls is None:
            continue
        has_tz = bool(node.args) or any(k.arg == "tz" for k in node.keywords)
        if attr == "today" or (attr == "now" and cls == "datetime" and not has_tz):
            lines.append(node.lineno)
    return sorted(lines)


def local_clock_references(source: str, filename: str = "<quelle>") -> list[tuple[int, str]]:
    """Seit 1.8.46: date.today, datetime.today und datetime.now als Verweis ohne Aufruf -- vor allem als
    Spaltenvorgabe (default=date.today, onupdate=datetime.now) oder default_factory im Schema. Sie lesen
    die Uhr erst beim Anlegen einer Zeile und liefern auf dem Server (UTC) zwischen 0 und 2 Uhr den
    Vortag; local_clock_calls() sieht sie nicht, weil hier niemand die Klammern schreibt. Ein Aufruf in
    einer lambda (default=lambda: date.today()) ist ein Aufruf und gehört zu local_clock_calls().
    Rückgabe (Zeile, Ort): Ort "Klasse.feld", sonst die umgebende Funktion bzw. Zuweisung."""
    tree = ast.parse(source, filename)
    clock_class = _clock_class_resolver(tree)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    called = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}

    def where(node) -> str:
        target, scope = None, None
        while node in parents:
            node = parents[node]
            if target is None and isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target = node.target.id
            elif target is None and isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                target = node.targets[0].id
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = node.name
                break
        return ".".join(part for part in (scope, target) if part) or "<modul>"

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and id(node) not in called \
                and _reads_local_clock(clock_class(node.value), node.attr):
            found.append((node.lineno, where(node)))
    return sorted(found)


def test_no_local_clock_in_app():
    found, scanned = [], set()
    for path in sorted(APP.rglob("*.py")):
        scanned.add(path.relative_to(APP).as_posix())
        found += [f"{path.relative_to(ROOT).as_posix()}:{line}"
                  for line in local_clock_calls(path.read_text(encoding="utf-8"), str(path))]
    assert len(scanned) > 100 and "berlin_time.py" in scanned, "Suche läuft ins Leere: app/ nicht erfasst"
    assert not found, ("date.today()/datetime.now() liefern die Zeit des Rechners, auf dem Server UTC. "
                       "app/berlin_time.py nehmen (berlin_today/berlin_now, to_berlin für Zeitstempel): "
                       + ", ".join(found))


def test_search_catches_local_clock_also_via_aliases():
    source = '''
from datetime import date, datetime, timezone
from datetime import date as _date, datetime as _datetime
import datetime as dt
a = date.today()
b = datetime.now()
c = datetime.now(timezone.utc)
d = datetime.now(tz=timezone.utc)
e = _date.today()
f = _datetime.now().replace(microsecond=0)
g = dt.date.today()
h = dt.datetime.now(
)
i = datetime.today()
j = datetime.utcnow()
k = "date.today()"  # nur Text
# l = datetime.now()
m = order.date.today()
'''
    assert local_clock_calls(source) == [5, 6, 9, 10, 11, 12, 14]


# Spaltenvorgaben und default_factory, die beim Einführen der Suche (1.8.46, Befund Stufe 2c, Widerspruch 2)
# schon da waren. Darf nur kürzer werden: ein neuer Fund ist rot, ein Eintrag ohne Fund auch (dann streichen).
# Abhilfe je Fall: Vorgabe weg und das Datum beim Anlegen ausdrücklich mit berlin_today() setzen.
_UTC_DATUM = ("Datum beim Anlegen aus der Uhr des Rechners -- auf dem Server UTC, zwischen 0 und 2 Uhr der Vortag "
              "(Befund Stufe 2c, 03.10.2026)")
BEKANNTE_VORGABEN = {
    "app/models.py::QuoteDocumentMeta.quote_date": _UTC_DATUM + "; neue Angebote setzen es aus created_at in "
                                                               "Europe/Berlin (ensure_quote_structure)",
    "app/models.py::Order.order_date": _UTC_DATUM,
    "app/models.py::Invoice.invoice_date": _UTC_DATUM + "; Rechnungsdatum = Tag des Entwurfs, beim Versand nicht "
                                                        "erneuert",
    "app/models.py::Reminder.reminder_date": _UTC_DATUM,
    "app/models.py::ServiceReport.performed_at": _UTC_DATUM,
    # app/schemas.py::OrderCreateFromQuote.order_date seit 1.8.71 aus berlin_today() (Befund 4d)
}


def test_no_local_clock_as_column_default_in_app():
    found, scanned = {}, set()
    for path in sorted(APP.rglob("*.py")):
        scanned.add(path.relative_to(APP).as_posix())
        for line, where in local_clock_references(path.read_text(encoding="utf-8"), str(path)):
            found.setdefault(f"{path.relative_to(ROOT).as_posix()}::{where}", line)
    assert len(scanned) > 100 and "models.py" in scanned, "Suche läuft ins Leere: app/ nicht erfasst"
    neu = sorted(f"{key} (Zeile {line})" for key, line in found.items() if key not in BEKANNTE_VORGABEN)
    assert not neu, ("date.today/datetime.now als Vorgabe lesen die Uhr des Rechners, auf dem Server UTC. "
                     "Datum beim Anlegen ausdrücklich mit app/berlin_time.py setzen: " + ", ".join(neu))
    veraltet = sorted(set(BEKANNTE_VORGABEN) - set(found))
    assert not veraltet, "BEKANNTE_VORGABEN ohne Fund -- streichen: " + ", ".join(veraltet)


def test_search_catches_clock_references_as_defaults():
    source = '''
from datetime import date, datetime
from datetime import date as _d
import datetime as dt
from pydantic import Field
from sqlalchemy.orm import mapped_column
class Rechnung:
    datum = mapped_column(Date, default=date.today)
    zeit = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    tag: date = Field(default_factory=_d.today)
    modul = mapped_column(Date, default=dt.date.today)
    jetzt = mapped_column(DateTime, default=dt.datetime.today)
    utc = mapped_column(DateTime, default=datetime.utcnow)
    aufruf = mapped_column(Date, default=lambda: date.today())
    text = "default=date.today"
    fremd = mapped_column(Date, default=order.date.today)
def sortieren(xs):
    return sorted(xs, key=datetime.today)
vorgabe = date.today
'''
    assert local_clock_references(source) == [
        (8, "Rechnung.datum"), (9, "Rechnung.zeit"), (9, "Rechnung.zeit"), (10, "Rechnung.tag"),
        (11, "Rechnung.modul"), (12, "Rechnung.jetzt"), (18, "sortieren"), (19, "vorgabe"),
    ]
    assert local_clock_calls(source) == [14]  # die lambda ruft auf -- der andere Test findet sie


# ---------------------------------------------------------------------------
# 2. Helfer
# ---------------------------------------------------------------------------

def test_to_berlin_summer_and_winter_and_day_boundary():
    assert to_berlin(datetime(2026, 7, 15, 12, 0)) == datetime(2026, 7, 15, 14, 0)  # MESZ, +2
    assert to_berlin(datetime(2026, 1, 15, 12, 0)) == datetime(2026, 1, 15, 13, 0)  # MEZ, +1
    assert to_berlin(SILVESTER_UTC) == datetime(2027, 1, 1, 0, 30)
    assert to_berlin(datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)) == datetime(2026, 7, 15, 14, 0)
    assert to_berlin(None) is None


def test_now_and_today_follow_the_fixed_utc_clock(utc_server):
    utc_server(datetime(2026, 12, 31, 23, 30, 15, 123456))
    assert berlin_now() == datetime(2027, 1, 1, 0, 30, 15)  # naiv, ohne Mikrosekunden
    assert berlin_now().tzinfo is None
    assert berlin_today() == date(2027, 1, 1)
    utc_server(datetime(2026, 3, 29, 0, 59))  # letzte Minute MEZ vor der Umstellung
    assert berlin_now() == datetime(2026, 3, 29, 1, 59)
    utc_server(datetime(2026, 3, 29, 1, 0))
    assert berlin_now() == datetime(2026, 3, 29, 3, 0)


# ---------------------------------------------------------------------------
# 3. Unterschriftszeitpunkte in den PDFs: 12:00 UTC im Sommer steht als 14:00 im PDF
# ---------------------------------------------------------------------------

def _signed_report(db, tmp_path, monkeypatch):
    from app import service_reports as service_reports_module
    from app.service_reports import _load as load_report, create_report, sign_report
    from tests.test_v133_invoices import make_order_with_item
    from tests.test_v213_inspection_items import TINY_PNG

    monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "wartung", description="Dach kontrolliert.")
    sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Meier",
                customer_signature_png_bytes=TINY_PNG, customer_signature_name="Kundin")
    return load_report(db, report["id"])


def test_service_report_pdf_prints_signatures_in_berlin_time(tmp_path, monkeypatch):
    from app.service_report_pdf import build_service_report_pdf
    from tests.test_v133_invoices import db_session

    db = db_session()
    row = _signed_report(db, tmp_path, monkeypatch)
    row.installer_signed_at = datetime(2026, 7, 15, 11, 45)  # gespeichert: naive UTC
    row.signed_at = datetime(2026, 7, 15, 12, 0)
    db.commit()

    text = _extract_pdf_text(build_service_report_pdf(db, row))
    assert b"15.07.2026 13:45 Uhr" in text  # Monteur
    assert b"15.07.2026 14:00 Uhr" in text  # Kunde
    assert b"12:00 Uhr" not in text and b"11:45 Uhr" not in text


def test_service_report_pdf_single_signature_branch_uses_berlin_time(tmp_path, monkeypatch):
    """Alter Ein-Block-Zweig (vor 1.3.0 unterschrieben, ohne Monteursunterschrift), Winterzeit."""
    from app.service_report_pdf import build_service_report_pdf
    from tests.test_v133_invoices import db_session

    db = db_session()
    row = _signed_report(db, tmp_path, monkeypatch)
    row.installer_signature_path = None
    row.signed_at = datetime(2026, 1, 15, 12, 0)
    db.commit()

    text = _extract_pdf_text(build_service_report_pdf(db, row))
    assert b"15.01.2026 13:00 Uhr" in text and b"12:00 Uhr" not in text


def test_checklist_pdf_prints_completion_and_signature_in_berlin_time(world, router_test_client):
    """Abschluss und Unterschrift in Ortszeit; um 23:30 UTC steht schon der Folgetag im Kopf. Seit 1.8.66 liefert der
    PDF-Knopf die feste Fassung des Abschlusses (nie neu erzeugt) -- die nachträglich gesetzten Zeitpunkte prüft deshalb der
    Renderer selbst."""
    from app.checklist_pdf import build_checklist_pdf
    from app.checklists import get_checklist_row
    from app.models import Checklist
    from tests.test_v305_checklist_filling import _client
    from tests.test_v308_checklist_pdf import _completed_order_checklist

    a = _client(world, router_test_client, "a")
    c = _completed_order_checklist(world, a)
    db = world["db"]
    checklist = db.get(Checklist, c["id"])
    checklist.completed_at = datetime(2026, 7, 15, 12, 0)
    # Rohes UPDATE -- seit 1.8.57 lehnt das ORM jede Änderung an einer Unterschrift ab.
    from sqlalchemy import update
    from app.models import ChecklistAttachment
    db.execute(update(ChecklistAttachment).where(ChecklistAttachment.checklist_id == c["id"])
               .values(created_at=datetime(2026, 7, 15, 11, 50)))
    db.commit()

    text = _extract_pdf_text(build_checklist_pdf(db, get_checklist_row(db, c["id"])))
    assert b"abgeschlossen am 15.07.2026 14:00 Uhr" in text
    assert b"Anna Alpha, 15.07.2026 13:50 Uhr" in text
    assert b"12:00 Uhr" not in text and b"11:50 Uhr" not in text

    checklist.completed_at = datetime(2026, 7, 15, 23, 30)
    db.commit()
    db.expire_all()
    text = _extract_pdf_text(build_checklist_pdf(db, get_checklist_row(db, c["id"])))
    assert b"abgeschlossen am 16.07.2026 01:30 Uhr" in text
    assert text.count(b"16.07.2026") >= 2  # auch die Kopfzeile "Abgeschlossen"


# ---------------------------------------------------------------------------
# 4. Server in UTC, Silvester 23:30 UTC: in Berlin schon das neue Jahr
# ---------------------------------------------------------------------------

def test_number_sequence_starts_new_year_at_silvester_2330_utc(utc_server):
    from app import settings as settings_module
    from app.settings import load_sequence, issue_number
    from tests.test_v133_invoices import db_session

    db = db_session()
    sequence = load_sequence(db, "invoice")  # R-{YYYY}-{NNNN}, jährlich neu
    sequence.last_year, sequence.next_value = 2026, 57
    db.commit()

    utc_server(SILVESTER_UTC, settings_module)
    assert issue_number(db, "invoice") == "R-2027-0001"
    assert issue_number(db, "invoice") == "R-2027-0002"
    assert load_sequence(db, "invoice").last_year == 2027


def test_timer_books_new_year_at_silvester_2330_utc(utc_server):
    from app import time_tracking as time_tracking_module
    from app.time_tracking import start_timer, stop_timer
    from tests.test_v100_time_tracking import add_employee
    from tests.test_v133_invoices import db_session, make_order_with_item

    db = db_session()
    order, _ = make_order_with_item(db)
    employee = add_employee(db)

    utc_server(SILVESTER_UTC, time_tracking_module)
    row = start_timer(db, employee_id=employee.id, order_id=order.id)
    assert row.work_date == date(2027, 1, 1)
    assert row.started_at == datetime(2027, 1, 1, 0, 30)

    utc_server(datetime(2027, 1, 1, 1, 15), time_tracking_module)
    row = stop_timer(db, row.id)
    assert row.ended_at == datetime(2027, 1, 1, 2, 15)
    assert row.hours == Decimal("1.75")


def test_shift_end_logout_in_berlin_time(utc_server):
    """Feierabend 19:00: um 17:30 UTC im Sommer ist es in Berlin 19:30."""
    from app import mobile_settings as mobile_settings_module
    from app.mobile_settings import is_past_shift_end
    from app.models import MobileSettings

    settings = MobileSettings(shift_end_time=time(19, 0))
    utc_server(datetime(2026, 7, 15, 17, 30), mobile_settings_module)
    assert is_past_shift_end(settings) is True
    utc_server(datetime(2026, 7, 15, 16, 30), mobile_settings_module)  # 18:30 in Berlin
    assert is_past_shift_end(settings) is False


def test_quote_date_from_created_at_is_berlin_date():
    """Angebotsdatum neuer Angebote aus created_at (UTC): 23:30 UTC ist in Berlin der Folgetag."""
    from app.models import Order, Quote
    from app.projects import ensure_quote_structure
    from tests.test_v133_invoices import db_session, make_order_with_item

    db = db_session()
    order, _ = make_order_with_item(db)
    quote = Quote(quote_number="A-2027-0001", project_id=db.get(Order, order.id).project_id, title="Silvester",
                  created_at=SILVESTER_UTC)
    db.add(quote)
    db.commit()
    meta, _, _ = ensure_quote_structure(db, quote)
    assert meta.quote_date == date(2027, 1, 1)
    assert meta.valid_until == date(2027, 1, 31)
