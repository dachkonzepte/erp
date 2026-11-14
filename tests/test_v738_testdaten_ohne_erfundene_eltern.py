"""Version 1.9.338 (Runde V1, Punkt 1): Testdaten ohne erfundene Eltern, der Leistungsimport behält seinen Importlauf.

Befund SQLite/PostgreSQL (13.11.2026): 111 rote Tests unter PostgreSQL waren Testartefakte -- Aufträge ohne ihr Angebot, ein angenommenes Konto ohne
AppUser, erfundene IDs in Testdaten und Migrationsproben, SQLite-Fassungen. Dazu N1: in der Test-SQLite (eine Verbindung) rollte eine Spaltenprüfung
über die Engine die Transaktion des Leistungsimports zurück. Dieser Test hält fest:

- ein Auftrag der Testdaten hat sein echtes Angebot (tests/quellangebot.py), und kein Order(...) unter tests/ setzt eine erfundene source_quote_id;
- router_test_client legt ein Konto mit ID auch in der Datenbank an;
- der Leistungsimport behält seinen Importlauf (N1).
"""

import ast
import re
from pathlib import Path

from sqlalchemy import func, select

from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.models import AppUser, ImportBatch, Order, Quote, Service
from app.routers.tasks import router as tasks_router
from app.service import persist_project
from tests.test_v133_invoices import db_session, make_order_with_item

ROOT = Path(__file__).resolve().parents[1]
# Was als source_quote_id gilt: ein Aufruf von quell_angebot() oder die ID eines echten Angebots (quote.id, angebot.id, quotes[0].id …)
ECHT = re.compile(r"^quell_angebot\(|(quote|angebot|quelle|q)\b[\w\[\]\"']*\.id$|quotes\[\d\]\.id$")


def test_ein_auftrag_der_testdaten_hat_sein_angebot():
    db = db_session()
    order, _item = make_order_with_item(db)
    quote = db.get(Quote, order.source_quote_id)
    assert quote is not None
    assert (quote.quote_number, quote.project_id, quote.status) == ("Q-AUF-TEST-0001", order.project_id, "beauftragt")


def test_kein_order_unter_tests_mit_erfundenem_angebot():
    erfunden = []
    for datei in sorted((ROOT / "tests").rglob("*.py")):
        text = datei.read_text(encoding="utf-8")
        if "source_quote_id" not in text:
            continue
        for k in ast.walk(ast.parse(text)):
            if not (isinstance(k, ast.Call) and getattr(k.func, "id", getattr(k.func, "attr", None)) == "Order"):
                continue
            for kw in k.keywords:
                if kw.arg == "source_quote_id" and not ECHT.search(ast.get_source_segment(text, kw.value)):
                    erfunden.append(f"{datei.relative_to(ROOT).as_posix()}:{k.lineno} {ast.get_source_segment(text, kw.value)}")
    assert erfunden == [], "Auftrag mit erfundenem Quell-Angebot (tests/quellangebot.py nehmen): " + "; ".join(erfunden)


def test_router_test_client_legt_das_konto_an(threaded_db_session, router_test_client):
    db = threaded_db_session
    vorher = db.scalar(select(func.count()).select_from(AppUser))
    router_test_client(db, tasks_router)  # ohne ID: kein Konto
    assert db.scalar(select(func.count()).select_from(AppUser)) == vorher
    router_test_client(db, tasks_router, role="buero_finanzen", user_id=7)
    konto = db.get(AppUser, 7)
    assert (konto.username, konto.role, konto.active) == ("test-konto-7", "buero_finanzen", True)
    router_test_client(db, tasks_router, user_id=7)  # dasselbe Konto ein zweites Mal: nichts doppelt
    assert db.scalar(select(func.count()).select_from(AppUser)) == vorher + 1


def test_leistungsimport_behaelt_seinen_importlauf():
    """N1: die Testsitzung hat eine Verbindung; bis 1.9.337 rollte die Spaltenprüfung über die Engine nach dem Flush des Importlaufs die
    Transaktion zurück -- danach gab es keinen Importlauf, aber Leistungen mit seiner ID."""
    db = db_session()
    sample = ROOT / "sample_data" / "Thiefes.xml"
    persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    laeufe = db.scalars(select(ImportBatch.id)).all()
    assert len(laeufe) == 1
    ids = set(db.scalars(select(Service.import_batch_id)).all())
    assert ids == set(laeufe)
