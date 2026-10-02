"""Version 1.8.21 -- Stufe 2b, Runde 2b-1a: Verbraucher-Merkmal und Vertragsgrundlage.

Punkt 1 Kunde (is_consumer, Migration nach Kategorie), Punkt 2 Vertragsgrundlage am Angebot
(Vorgabe aus dem Kunden, Bestand bgb), Punkt 3 Klauseltext mit rechtlicher Prüfung (nur geprüft im
PDF), Punkt 4 Übernahme in den Auftrag, Ändern nur mit Begründung, Abgleich überschreibt eine so
geänderte nicht. Punkt 5 (Feldliste Angebot/Auftrag) steht in test_v325_quote_order_copy_fields.py.
"""

import importlib.util
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.berlin_time import berlin_today
from app.contract_basis import (
    change_order_contract_basis, default_contract_basis_for_customer, printable_clause_text, update_clause,
)
from app.database import Base
from app.models import (
    ContractBasisClause, Customer, CustomerProfile, Order, OrderContractBasisChange, PaymentTerm, Project,
    Quote, QuoteDocumentMeta, QuoteItem,
)
from app.order_pdf import build_order_pdf
from app.orders import create_order_from_quote, load_order, order_matches_source_quote, order_to_dict, sync_order_from_source_quote
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import duplicate_project, ensure_quote_structure, load_project, load_quote, quote_to_dict
from app.quote_framed_pdf import build_quote_framed_pdf
from tests.test_v153_mahnwesen import db_session
from tests.test_v230_invoice_pdf_shared_frame import _page_text
from tests.grunddaten_schalter import ohne_grunddaten

CLAUSE = "Es gilt die VOB Teil B in der bei Vertragsschluss gueltigen Fassung."


def make_quote(db, *, is_consumer=True, number="0001"):
    customer = Customer(name=f"Kunde {number}", last_name=f"Kunde {number}", is_consumer=is_consumer,
                        street="Dachweg 1", postal_code="52531", city="Uebach")
    db.add(customer); db.flush()
    project = Project(project_number=f"P-{number}", name="Dach", customer_id=customer.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.flush()
    quote = Quote(quote_number=f"A-{number}", project_id=project.id, title="Dachsanierung", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"),
                     unit="m2", unit_price=Decimal("50")))
    db.commit()
    return load_quote(db, quote.id)


def beauftragen(db, quote):
    return create_order_from_quote(
        db, quote.id, order_date=date(2026, 9, 30), execution_start=None, execution_end=None,
        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None,
    )


def meta_of(db, quote):
    return ensure_quote_structure(db, quote)[0]


def pdf_text(pdf_bytes):
    import pypdfium2 as pdfium
    count = len(pdfium.PdfDocument(pdf_bytes))
    return "\n".join(_page_text(pdf_bytes, i) for i in range(count))


def review(db, key="vob_b", text_value=CLAUSE):
    return update_clause(db, key, clause_text=text_value, reviewed_on=berlin_today(), reviewed_by="RA Beispiel")


# --- Migration (Punkt 1 und 2): echte upgrade()/downgrade() auf einem Vorzustand ----------------

def _migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_vertragsgrundlage.py"))
    spec = importlib.util.spec_from_file_location("migration_1821_vertragsgrundlage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pre_migration_engine():
    """Schema von heute, dann alles entfernt, was die Migration anlegt -- der Stand davor."""
    engine = create_engine("sqlite:///:memory:")
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE order_contract_basis_changes"))
        conn.execute(text("DROP TABLE contract_basis_clauses"))
        conn.execute(text("ALTER TABLE customers DROP COLUMN is_consumer"))
        conn.execute(text("ALTER TABLE orders DROP COLUMN contract_basis"))
        conn.execute(text("ALTER TABLE orders DROP COLUMN contract_basis_manual"))
        conn.execute(text("ALTER TABLE quote_document_meta DROP COLUMN contract_basis"))
    return engine


def _run(engine, fn_name):
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def _seed_pre_migration(engine):
    categories = {
        "privat": "Privatkunde", "gewerbe": "Gewerbekunde", "oeffentlich": "Öffentlicher Auftraggeber",
        "architekt": "Architekt / Planer", "architekt2": "Architekt/Planer", "versicherung": "Versicherung",
        "hausverwaltung": "Hausverwaltung", "sonstige": "Sonstige", "ohne_profil": None,
    }
    ids = {}
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO payment_terms (label, days, is_default, archived, sort_order, created_at) "
                          "VALUES ('14 Tage netto', 14, :t, :f, 10, '2026-01-01 00:00:00')"), {"t": True, "f": False})
        for key, category in categories.items():
            cid = conn.execute(text("INSERT INTO customers (name, last_name, country, created_at) "
                                    "VALUES (:n, :n, 'Deutschland', '2026-01-01 00:00:00') RETURNING id"), {"n": key}).scalar()
            ids[key] = cid
            if category:
                conn.execute(text("INSERT INTO customer_profiles (customer_id, customer_number, category, created_at, updated_at) "
                                  "VALUES (:c, :no, :cat, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"),
                             {"c": cid, "no": f"K-{cid}", "cat": category})
        conn.execute(text("INSERT INTO project_pipeline_columns (id, key, label, sort_order, created_at) "
                          "VALUES (1, 'neu', 'Neu', 10, '2026-01-01 00:00:00')"))
        pid = conn.execute(text("INSERT INTO projects (project_number, name, customer_id, status, pipeline_column_id, is_template, archived, created_at) "
                                "VALUES ('P-1', 'Alt', :c, 'angebot', 1, :f, :f, '2026-01-01 00:00:00') RETURNING id"),
                           {"c": ids["gewerbe"], "f": False}).scalar()
        with_meta = conn.execute(text("INSERT INTO quotes (quote_number, project_id, title, status, vat_rate, source_format, created_at, updated_at) "
                                      "VALUES ('A-1', :p, 'Mit Kopf', 'beauftragt', 19, 'manual', '2026-02-01 10:00:00', '2026-02-01 10:00:00') RETURNING id"),
                                 {"p": pid}).scalar()
        conn.execute(text("INSERT INTO quote_document_meta (quote_id, quote_date, updated_at) VALUES (:q, '2026-02-01', '2026-02-01 10:00:00')"),
                     {"q": with_meta})
        # 23:30 UTC am 1. März ist in Berlin schon der 2. März.
        without_meta = conn.execute(text("INSERT INTO quotes (quote_number, project_id, title, status, vat_rate, source_format, created_at, updated_at) "
                                         "VALUES ('A-2', :p, 'Ohne Kopf', 'entwurf', 19, 'manual', '2026-03-01 23:30:00', '2026-03-01 23:30:00') RETURNING id"),
                                    {"p": pid}).scalar()
        conn.execute(text("INSERT INTO orders (order_number, project_id, source_quote_id, quote_number_snapshot, title, status, vat_rate, customer_name, order_date, created_at, updated_at) "
                          "VALUES ('AU-1', :p, :q, 'A-1', 'Alt', 'beauftragt', 19, 'gewerbe', '2026-02-02', '2026-02-02 00:00:00', '2026-02-02 00:00:00')"),
                     {"p": pid, "q": with_meta})
    return ids, with_meta, without_meta


def test_migration_sets_consumer_flag_by_category_and_bgb_for_existing_documents():
    engine = _pre_migration_engine()
    ids, with_meta, without_meta = _seed_pre_migration(engine)
    _run(engine, "upgrade")
    with engine.connect() as conn:
        flags = {cid: bool(flag) for cid, flag in conn.execute(text("SELECT id, is_consumer FROM customers"))}
        metas = {row.quote_id: row for row in conn.execute(text("SELECT * FROM quote_document_meta"))}
        order_basis = conn.execute(text("SELECT contract_basis, contract_basis_manual FROM orders")).one()
    for key in ("gewerbe", "oeffentlich", "architekt", "architekt2", "versicherung"):
        assert flags[ids[key]] is False, key
    for key in ("privat", "hausverwaltung", "sonstige", "ohne_profil"):
        assert flags[ids[key]] is True, key
    assert metas[with_meta].contract_basis == "bgb"
    added = metas[without_meta]
    assert added.contract_basis == "bgb"
    assert str(added.quote_date) == "2026-03-02"
    assert str(added.valid_until) == "2026-04-01"
    assert added.payment_terms == "14 Tage netto"
    assert order_basis.contract_basis == "bgb" and not order_basis.contract_basis_manual

    # Das bisher kopflose Angebot bekommt beim Öffnen nicht mehr die Vorgabe für neue Angebote.
    db = sessionmaker(bind=engine)()
    quote = load_quote(db, without_meta)
    assert quote_to_dict(quote)["document_meta"]["contract_basis"] == "bgb"


def test_migration_downgrade_removes_everything_and_refuses_when_data_would_be_lost():
    engine = _pre_migration_engine()
    ids, _, _ = _seed_pre_migration(engine)
    _run(engine, "upgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE customers SET is_consumer = :f WHERE id = :c"), {"f": False, "c": ids["privat"]})
    with pytest.raises(RuntimeError, match="1 Kunden"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE customers SET is_consumer = :t WHERE id = :c"), {"t": True, "c": ids["privat"]})
    _run(engine, "downgrade")
    insp = inspect(engine)
    assert "is_consumer" not in {c["name"] for c in insp.get_columns("customers")}
    assert "contract_basis" not in {c["name"] for c in insp.get_columns("orders")}
    assert "contract_basis" not in {c["name"] for c in insp.get_columns("quote_document_meta")}
    assert "contract_basis_clauses" not in insp.get_table_names()


# --- Punkt 1: Kunde ----------------------------------------------------------------------------

def test_customer_consumer_flag_defaults_to_yes_and_update_without_field_keeps_it(threaded_db_session, router_test_client):
    from app.routers import customers
    client = router_test_client(threaded_db_session, customers.router)
    created = client.post("/api/customers", json={"last_name": "Privat"}).json()
    assert created["is_consumer"] is True
    firm = client.post("/api/customers", json={"last_name": "Firma GmbH", "category": "Gewerbekunde", "is_consumer": False}).json()
    assert firm["is_consumer"] is False
    # Ein Aufrufer ohne das Feld (ältere Oberfläche) setzt es nicht zurück ...
    kept = client.put(f"/api/customers/{firm['id']}", json={"last_name": "Firma GmbH", "category": "Gewerbekunde"}).json()
    assert kept["is_consumer"] is False
    # ... ausdrücklich gesetzt wird es übernommen.
    changed = client.put(f"/api/customers/{firm['id']}", json={"last_name": "Firma GmbH", "is_consumer": True}).json()
    assert changed["is_consumer"] is True


# --- Punkt 2: Angebot --------------------------------------------------------------------------

def test_new_quote_gets_default_from_customer():
    db = db_session()
    consumer = make_quote(db, is_consumer=True, number="0001")
    business = make_quote(db, is_consumer=False, number="0002")
    assert quote_to_dict(consumer)["document_meta"]["contract_basis"] == "bgb_vob_c_4_5"
    assert quote_to_dict(business)["document_meta"]["contract_basis"] == "vob_b"
    assert default_contract_basis_for_customer(None) == "bgb_vob_c_4_5"


def test_quote_editor_can_change_contract_basis_and_omitting_it_keeps_it(threaded_db_session, router_test_client):
    from app.routers import quotes
    quote = make_quote(threaded_db_session, is_consumer=False)
    client = router_test_client(threaded_db_session, quotes.router)
    base = {"quote_date": "2026-09-30"}
    res = client.put(f"/api/quotes/{quote.id}/document-meta", json={**base, "contract_basis": "bgb"})
    assert res.status_code == 200 and res.json()["document_meta"]["contract_basis"] == "bgb"
    assert res.json()["document_meta"]["contract_basis_label"] == "BGB (ohne VOB)"
    res = client.put(f"/api/quotes/{quote.id}/document-meta", json=base)
    assert res.json()["document_meta"]["contract_basis"] == "bgb"
    bad = client.put(f"/api/quotes/{quote.id}/document-meta", json={**base, "contract_basis": "vob_a"})
    assert bad.status_code == 422
    assert client.get(f"/api/quotes/{quote.id}").json()["document_meta"]["contract_basis"] == "bgb"


def test_copied_quote_gets_default_of_customer_not_choice_of_source():
    db = db_session()
    quote = make_quote(db, is_consumer=False)
    meta_of(db, quote).contract_basis = "bgb"
    db.commit()
    copy = duplicate_project(db, load_project(db, quote.project_id), as_template=False)
    new_quote = max(copy.quotes, key=lambda q: q.id)
    assert meta_of(db, new_quote).contract_basis == "vob_b"


# --- Punkt 3: Klausel nur geprüft im PDF ----------------------------------------------------------

def test_clause_is_printed_only_when_reviewed_on_quote_and_order():
    db = db_session()
    quote = make_quote(db, is_consumer=False)
    order = beauftragen(db, quote)
    update_clause(db, "vob_b", clause_text=CLAUSE, reviewed_on=None, reviewed_by=None)
    assert printable_clause_text(db, "vob_b") is None
    assert CLAUSE not in pdf_text(build_quote_framed_pdf(db, load_quote(db, quote.id)))
    assert CLAUSE not in pdf_text(build_order_pdf(db, load_order(db, order.id)))
    assert quote_to_dict(load_quote(db, quote.id))["document_meta"]["contract_basis_clause_reviewed"] is False
    assert order_to_dict(load_order(db, order.id), db)["contract_basis_clause_reviewed"] is False

    review(db)
    assert CLAUSE in pdf_text(build_quote_framed_pdf(db, load_quote(db, quote.id)))
    assert CLAUSE in pdf_text(build_order_pdf(db, load_order(db, order.id)))
    assert quote_to_dict(load_quote(db, quote.id))["document_meta"]["contract_basis_clause_reviewed"] is True
    assert order_to_dict(load_order(db, order.id), db)["contract_basis_clause_reviewed"] is True

    # Eine geprüfte Klausel einer ANDEREN Grundlage erscheint nicht.
    meta_of(db, load_quote(db, quote.id)).contract_basis = "bgb"
    db.commit()
    assert CLAUSE not in pdf_text(build_quote_framed_pdf(db, load_quote(db, quote.id)))


def test_changing_the_text_without_new_review_drops_the_review():
    db = db_session()
    clause, reset = review(db)
    assert clause["reviewed"] is True and reset is False
    reviewed_on = clause["reviewed_on"]
    clause, reset = update_clause(db, "vob_b", clause_text=CLAUSE + " Ergaenzt.", reviewed_on=reviewed_on, reviewed_by="RA Beispiel")
    assert reset is True and clause["reviewed"] is False and clause["reviewed_on"] is None
    assert printable_clause_text(db, "vob_b") is None
    # Neuer Text mit neuer Prüfangabe bleibt geprüft; unveränderter Text mit denselben Angaben auch.
    clause, reset = update_clause(db, "vob_b", clause_text=CLAUSE, reviewed_on=berlin_today(), reviewed_by="RA Zwei")
    assert reset is False and clause["reviewed"] is True
    clause, reset = update_clause(db, "vob_b", clause_text=CLAUSE, reviewed_on=berlin_today(), reviewed_by="RA Zwei")
    assert reset is False and clause["reviewed"] is True


@pytest.mark.parametrize("kwargs,message", [
    ({"clause_text": CLAUSE, "reviewed_on": date(2026, 9, 1), "reviewed_by": None}, "gemeinsam"),
    ({"clause_text": CLAUSE, "reviewed_on": None, "reviewed_by": "RA"}, "gemeinsam"),
    ({"clause_text": None, "reviewed_on": date(2026, 9, 1), "reviewed_by": "RA"}, "Ohne Klauseltext"),
])
def test_clause_review_validation(kwargs, message):
    db = db_session()
    with pytest.raises(ValueError, match=message):
        update_clause(db, "bgb", **kwargs)


def test_review_date_in_the_future_is_rejected():
    db = db_session()
    with pytest.raises(ValueError, match="Zukunft"):
        update_clause(db, "bgb", clause_text=CLAUSE, reviewed_on=berlin_today() + timedelta(days=1), reviewed_by="RA")


def test_only_admin_may_save_clause_texts(threaded_db_session, router_test_client):
    from app.routers import contract_basis
    office = router_test_client(threaded_db_session, contract_basis.router, role="buero_finanzen")
    assert office.get("/api/settings/contract-basis-clauses").status_code == 200
    assert office.get("/api/contract-bases").status_code == 200
    assert office.put("/api/settings/contract-basis-clauses/vob_b", json={"clause_text": CLAUSE}).status_code == 403
    field = router_test_client(threaded_db_session, contract_basis.router, role="field")
    assert field.get("/api/contract-bases").status_code == 403
    admin = router_test_client(threaded_db_session, contract_basis.router)
    res = admin.put("/api/settings/contract-basis-clauses/vob_b", json={
        "clause_text": CLAUSE, "reviewed_on": berlin_today().isoformat(), "reviewed_by": "RA Beispiel"})
    assert res.status_code == 200 and res.json()["reviewed"] is True
    assert admin.put("/api/settings/contract-basis-clauses/vob_a", json={"clause_text": CLAUSE}).status_code == 404
    options = {o["key"]: o["clause_reviewed"] for o in admin.get("/api/contract-bases").json()}
    assert options == {"vob_b": True, "bgb_vob_c_4_5": False, "bgb": False}


# --- Punkt 4: Auftrag ----------------------------------------------------------------------------

def test_order_takes_contract_basis_from_quote():
    db = db_session()
    quote = make_quote(db, is_consumer=True)
    order = beauftragen(db, quote)
    assert order.contract_basis == "bgb_vob_c_4_5" and order.contract_basis_manual is False
    assert order_matches_source_quote(db, order)


def test_changing_order_basis_needs_reason_and_is_recorded():
    db = db_session()
    order = beauftragen(db, make_quote(db, is_consumer=True))
    with pytest.raises(ValueError, match="Begründung"):
        change_order_contract_basis(db, order, contract_basis="vob_b", reason="   ")
    with pytest.raises(ValueError, match="bereits"):
        change_order_contract_basis(db, order, contract_basis="bgb_vob_c_4_5", reason="gleich")
    with pytest.raises(ValueError, match="Unbekannte"):
        change_order_contract_basis(db, order, contract_basis="vob_a", reason="x")
    assert db.scalar(select(OrderContractBasisChange)) is None and order.contract_basis_manual is False

    change_order_contract_basis(db, order, contract_basis="vob_b", reason="Kunde ist Unternehmer", actor_name="Tobias")
    order = load_order(db, order.id)
    assert order.contract_basis == "vob_b" and order.contract_basis_manual is True
    change = db.scalar(select(OrderContractBasisChange))
    assert (change.old_basis, change.new_basis, change.reason, change.changed_by_name) == (
        "bgb_vob_c_4_5", "vob_b", "Kunde ist Unternehmer", "Tobias")


def test_sync_follows_quote_basis_until_changed_on_the_order():
    db = db_session()
    quote = make_quote(db, is_consumer=True)
    order = beauftragen(db, quote)

    # Nicht am Auftrag geändert: Angebotsänderung ist eine Abweichung und wird übernommen.
    meta_of(db, load_quote(db, quote.id)).contract_basis = "bgb"
    db.commit()
    assert not order_matches_source_quote(db, load_order(db, order.id))
    order = sync_order_from_source_quote(db, load_order(db, order.id))
    assert order.contract_basis == "bgb"

    # Am Auftrag geändert: der Abgleich überschreibt sie nicht, auch nicht beim Übernehmen
    # anderer Änderungen, und sie zählt nicht als Abweichung.
    change_order_contract_basis(db, order, contract_basis="vob_b", reason="VOB/B ausdrücklich vereinbart")
    meta_of(db, load_quote(db, quote.id)).contract_basis = "bgb_vob_c_4_5"
    db.commit()
    assert order_matches_source_quote(db, load_order(db, order.id))
    quote = load_quote(db, quote.id)
    quote.title = "Dachsanierung geändert"
    db.commit()
    assert not order_matches_source_quote(db, load_order(db, order.id))
    order = sync_order_from_source_quote(db, load_order(db, order.id))
    assert order.title == "Dachsanierung geändert"
    assert order.contract_basis == "vob_b" and order.contract_basis_manual is True


def test_order_routes_change_basis_only_with_reason(threaded_db_session, router_test_client):
    from app.routers import orders
    order = beauftragen(threaded_db_session, make_quote(threaded_db_session, is_consumer=False))
    client = router_test_client(threaded_db_session, orders.router)
    # Über das normale Speichern der Auftragsdaten geht es nicht (kein Feld, wird ignoriert).
    client.put(f"/api/orders/{order.id}", json={"title": "Neu", "order_date": "2026-09-30", "contract_basis": "bgb"})
    assert client.get(f"/api/orders/{order.id}").json()["contract_basis"] == "vob_b"
    assert client.put(f"/api/orders/{order.id}/contract-basis", json={"contract_basis": "bgb", "reason": ""}).status_code == 422
    assert client.put(f"/api/orders/{order.id}/contract-basis", json={"contract_basis": "bgb", "reason": " "}).status_code == 422
    res = client.put(f"/api/orders/{order.id}/contract-basis", json={"contract_basis": "bgb", "reason": "Rücksprache"})
    assert res.status_code == 200
    assert res.json()["contract_basis"] == "bgb" and res.json()["contract_basis_manual"] is True
    history = client.get(f"/api/orders/{order.id}/contract-basis-changes").json()
    assert [(h["old_label"], h["new_label"], h["reason"]) for h in history] == [("VOB/B", "BGB (ohne VOB)", "Rücksprache")]
    field = router_test_client(threaded_db_session, orders.router, role="field")
    assert field.put(f"/api/orders/{order.id}/contract-basis", json={"contract_basis": "vob_b", "reason": "x"}).status_code == 403
