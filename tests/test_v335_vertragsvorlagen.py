"""Version 1.8.32 -- Stufe 2b, Runde 2b-1b Teil 1: Vertragsvorlagen und Vertragsentwurf.

Punkt 1 Vorlagen je Vertragsgrundlage (Abschnitte, Platzhalter über app/placeholders.py, "nur bei
Verbrauchern", Prüfangaben wie bei den Klauseln, Textänderung setzt sie zurück, speichern nur Admin, keine
vorgegebenen Texte). Punkt 2 Entwurf beim Beauftragen mit Fallfeldern. Punkt 3 Ausführungszeitraum aus dem
Angebot (Feldliste: test_v325_quote_order_copy_fields.py). Punkt 4 PDF "contract" im gemeinsamen Rahmen mit
dem Angebot als Anlage, Wasserzeichen bei ungeprüfter Vorlage. Punkt 5 Monteure 403 (Datengrenze:
test_v326_monteur_datengrenze.py::test_vertragsrouten_im_durchlauf_fuer_monteure_gesperrt).
"""

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.berlin_time import berlin_today
from app.contract_pdf import build_contract_pdf
from app.contract_templates import (
    CONTRACT_WATERMARK_TEXT, KNOWN_PLACEHOLDERS, contract_placeholder_values, get_order_contract, list_templates,
    save_template, update_contract_draft,
)
from app.database import Base
from app.models import ContractTemplate, OrderContract
from app.order_pdf import build_order_pdf
from app.orders import create_order_from_quote, load_order
from app.placeholders import apply_placeholders, placeholders_in, unknown_placeholders
from app.projects import ensure_quote_structure, load_quote
from tests.test_v153_mahnwesen import db_session
from tests.test_v230_invoice_pdf_shared_frame import _page_text
from tests.test_v325_contract_basis import make_quote, pdf_text

CONSUMER_TEXT = "WIDERRUFSBELEHRUNG-NUR-FUER-VERBRAUCHER"
ALWAYS_TEXT = "VERTRAGSGEGENSTAND-IMMER"


def section(heading=None, body=None, *, consumer_only=False, with_checkbox=False) -> dict:
    return {"heading": heading, "body_text": body, "consumer_only": consumer_only, "with_checkbox": with_checkbox}


SECTIONS = [
    section("Paragraf 1 Parteien", "Zwischen {firmenname} und {kundenname} ({kundennummer})."),
    section("Paragraf 2 Gegenstand", ALWAYS_TEXT + " {auftragstitel}, Summe {auftragssumme_brutto}."),
    section("Paragraf 3 Zeit", "Ausfuehrung: {ausfuehrungszeitraum}"),
    section("Paragraf 4 Zahlung", "Abschlaege: {abschlagsplan} / Besonderes: {besonderheiten}"),
    section("Widerruf", CONSUMER_TEXT, consumer_only=True),
    section(None, "Ich verlange den vorzeitigen Beginn.", consumer_only=True, with_checkbox=True),
]


def save(db, key="bgb_vob_c_4_5", *, sections=None, title="Bauvertrag {auftragsnummer}", reviewed=False, reviewed_on=None, by=None):
    if reviewed:
        reviewed_on, by = berlin_today(), "RA Beispiel"
    return save_template(db, key, title=title, sections=SECTIONS if sections is None else sections,
                         reviewed_on=reviewed_on, reviewed_by=by)


def beauftragen(db, quote, **kwargs):
    values = dict(order_date=date(2026, 10, 1), execution_start=None, execution_end=None, caseworker_employee_id=None,
                  project_manager_employee_id=None, payment_terms=None, remarks=None)
    values.update(kwargs)
    return load_order(db, create_order_from_quote(db, quote.id, **values).id)


def contract_pdf(db, order) -> bytes:
    order = load_order(db, order.id)
    return build_contract_pdf(db, order, get_order_contract(db, order.id))


def page_texts(pdf: bytes) -> list[str]:
    count = len(pdfium.PdfDocument(pdf))
    return [_page_text(pdf, i) for i in range(count)]


# --- Platzhalter-Modul ---------------------------------------------------------------------------

def test_placeholders_are_replaced_in_one_pass_and_unknown_ones_stay():
    values = {"{a}": "Wert {b}", "{b}": "B", "{ab}": "AB"}
    assert apply_placeholders("{a} {b} {ab} {c}", values) == "Wert {b} B AB {c}"  # {b} im Wert bleibt
    assert apply_placeholders("{x}", {"{x}": None}) == ""
    assert placeholders_in("{b} {a} {b} {A}") == ["{b}", "{a}"]
    assert unknown_placeholders("{kundenname} {kundename}", KNOWN_PLACEHOLDERS) == ["{kundename}"]


def test_every_listed_placeholder_has_a_value():
    db = db_session()
    order = beauftragen(db, make_quote(db))
    assert list(contract_placeholder_values(db, order, None)) == KNOWN_PLACEHOLDERS


# --- Punkt 1: Vorlagen ---------------------------------------------------------------------------

def test_no_default_texts_and_no_template_rows_without_saving():
    db = db_session()
    templates = list_templates(db)
    assert [t["basis_key"] for t in templates] == ["vob_b", "bgb_vob_c_4_5", "bgb"]
    assert all(not t["has_content"] and t["title"] is None and t["sections"] == [] for t in templates)
    assert db.query(ContractTemplate).count() == 0


@pytest.mark.parametrize("kwargs, message", [
    ({"reviewed_on": date(2026, 9, 1), "by": None}, "gemeinsam"),
    ({"reviewed_on": None, "by": "RA"}, "gemeinsam"),
    ({"reviewed_on": date(2026, 9, 1), "by": "RA", "sections": []}, "Ohne Abschnitte"),
])
def test_review_rules(kwargs, message):
    db = db_session()
    with pytest.raises(ValueError, match=message):
        save(db, **kwargs)


def test_review_date_in_the_future_is_rejected():
    db = db_session()
    with pytest.raises(ValueError, match="Zukunft"):
        save(db, reviewed_on=berlin_today() + timedelta(days=1), by="RA")


def test_text_change_resets_the_review():
    db = db_session()
    first, reset = save(db, reviewed=True)
    assert first["reviewed"] and not reset
    # Gegenprobe: unverändert mit denselben Prüfangaben gespeichert -- die Prüfung bleibt.
    again, reset = save(db, reviewed=True)
    assert again["reviewed"] and not reset
    changed = [dict(s) for s in SECTIONS]
    changed[1]["body_text"] += " Nachtrag."
    after, reset = save(db, sections=changed, reviewed=True)
    assert reset and not after["reviewed"] and after["reviewed_on"] is None and after["reviewed_by"] is None
    # Mit neuen Prüfangaben (anderer Name) bleibt die Prüfung trotz geänderten Texts.
    renewed, reset = save(db, sections=[dict(s, body_text=(s["body_text"] or "") + "!") for s in changed],
                          reviewed_on=berlin_today(), by="RA Neu")
    assert renewed["reviewed"] and not reset


@pytest.mark.parametrize("change", ["title", "consumer_only", "with_checkbox", "order", "removed"])
def test_every_content_change_counts_as_text_change(change):
    db = db_session()
    save(db, reviewed=True)
    sections, title = [dict(s) for s in SECTIONS], "Bauvertrag {auftragsnummer}"
    if change == "title":
        title = "Werkvertrag"
    elif change == "consumer_only":
        sections[0]["consumer_only"] = True
    elif change == "with_checkbox":
        sections[0]["with_checkbox"] = True
    elif change == "order":
        sections[0], sections[1] = sections[1], sections[0]
    else:
        sections.pop()
    result, reset = save(db, sections=sections, title=title, reviewed=True)
    assert reset and not result["reviewed"]


def test_empty_sections_are_dropped_and_warnings_are_reported():
    db = db_session()
    result, _ = save(db, "vob_b", sections=[section(None, "   "), section("Nur {kundename}", "Text")])
    assert len(result["sections"]) == 1
    assert result["unknown_placeholders"] == ["{kundename}"]
    assert {f["placeholder"] for f in result["unused_case_fields"]} == {"{ausfuehrungszeitraum}", "{abschlagsplan}", "{besonderheiten}"}
    full, _ = save(db, "bgb")
    assert full["unknown_placeholders"] == [] and full["unused_case_fields"] == []


def test_only_admin_saves_templates_and_monteur_sees_nothing(threaded_db_session, router_test_client):
    from app.routers import contract_templates
    db = threaded_db_session
    payload = {"title": "Vertrag", "sections": [section("A", "Text")], "reviewed_on": None, "reviewed_by": None}
    office = router_test_client(db, contract_templates.router, role="buero_auftrag")
    assert office.get("/api/settings/contract-templates").status_code == 200
    assert office.put("/api/settings/contract-templates/vob_b", json=payload).status_code == 403
    finance = router_test_client(db, contract_templates.router, role="buero_finanzen")
    assert finance.put("/api/settings/contract-templates/vob_b", json=payload).status_code == 403
    field = router_test_client(db, contract_templates.router, role="field")
    assert field.get("/api/settings/contract-templates").status_code == 403
    assert field.put("/api/settings/contract-templates/vob_b", json=payload).status_code == 403
    admin = router_test_client(db, contract_templates.router)
    res = admin.put("/api/settings/contract-templates/vob_b", json=payload)
    assert res.status_code == 200 and res.json()["has_content"] is True
    assert admin.put("/api/settings/contract-templates/vob_a", json=payload).status_code == 404
    # Regel 22: jedes Feld Pflicht -- ein Aufrufer ohne "sections" leert die Vorlage nicht still.
    assert admin.put("/api/settings/contract-templates/vob_b", json={"title": "X", "reviewed_on": None,
                                                                     "reviewed_by": None}).status_code == 422
    overview = admin.get("/api/settings/contract-templates").json()
    assert [p["placeholder"] for p in overview["placeholders"]] == KNOWN_PLACEHOLDERS
    assert overview["templates"][0]["sections"][0]["body_text"] == "Text"


# --- Punkt 2 und 3: Entwurf beim Beauftragen, Ausführungszeitraum ----------------------------------

def test_beauftragen_creates_a_draft_only_when_a_template_exists_for_the_basis():
    db = db_session()
    assert get_order_contract(db, beauftragen(db, make_quote(db, number="0001")).id) is None  # keine Vorlage
    save(db, "vob_b")
    consumer_order = beauftragen(db, make_quote(db, number="0002", is_consumer=True))  # bgb_vob_c_4_5
    assert consumer_order.contract_basis == "bgb_vob_c_4_5"
    assert get_order_contract(db, consumer_order.id) is None
    business_order = beauftragen(db, make_quote(db, number="0003", is_consumer=False))  # vob_b
    draft = get_order_contract(db, business_order.id)
    assert draft is not None and draft.status == "entwurf"
    # Eine Vorlage ohne Inhalt zählt nicht.
    save(db, "bgb_vob_c_4_5", sections=[section(None, "  ")])
    assert get_order_contract(db, beauftragen(db, make_quote(db, number="0004", is_consumer=True)).id) is None


def test_execution_period_of_the_quote_arrives_in_order_draft_and_pdfs():
    db = db_session()
    save(db)
    quote = make_quote(db)
    ensure_quote_structure(db, quote)[0].execution_period = "KW 42 bis 44 nach Witterung"
    db.commit()
    order = beauftragen(db, load_quote(db, quote.id), execution_start=date(2026, 10, 12))
    assert order.execution_period == "KW 42 bis 44 nach Witterung"
    assert "KW 42 bis 44 nach Witterung" in pdf_text(build_order_pdf(db, order))
    draft = get_order_contract(db, order.id)
    assert draft.execution_period == "12.10.2026 – KW 42 bis 44 nach Witterung"
    assert "Ausfuehrung: 12.10.2026" in pdf_text(contract_pdf(db, order))
    assert "KW 42 bis 44 nach Witterung" in pdf_text(contract_pdf(db, order))


def test_order_put_without_execution_period_keeps_it(threaded_db_session, router_test_client):
    """Regel 22: der Auftrags-PUT ist seit 1.8.32 ein Teil-Update."""
    from app.routers import orders
    db = threaded_db_session
    quote = make_quote(db)
    ensure_quote_structure(db, quote)[0].execution_period = "KW 42"
    db.commit()
    order = beauftragen(db, load_quote(db, quote.id))
    client = router_test_client(db, orders.router)
    assert client.put(f"/api/orders/{order.id}", json={"title": "Neu"}).status_code == 200
    db.expire_all()
    assert load_order(db, order.id).execution_period == "KW 42"
    assert load_order(db, order.id).title == "Neu"
    res = client.put(f"/api/orders/{order.id}", json={"execution_period": "KW 43"})
    assert res.status_code == 200 and res.json()["execution_period"] == "KW 43"
    assert client.put(f"/api/orders/{order.id}", json={"title": None}).status_code == 422


def test_case_fields_save_only_what_was_sent(threaded_db_session, router_test_client):
    from app.routers import contract_templates
    db = threaded_db_session
    save(db)
    order = beauftragen(db, make_quote(db))
    client = router_test_client(db, contract_templates.router, role="buero_auftrag")
    state = client.put(f"/api/orders/{order.id}/contract", json={"execution_period": "KW 1", "payment_plan": "30/70"}).json()
    assert state["contract"]["payment_plan"] == "30/70"
    state = client.put(f"/api/orders/{order.id}/contract", json={"special_terms": "Gerüst stellt der Kunde"}).json()
    assert state["contract"]["execution_period"] == "KW 1" and state["contract"]["payment_plan"] == "30/70"
    assert state["contract"]["special_terms"] == "Gerüst stellt der Kunde"
    text_ = pdf_text(client.get(f"/api/orders/{order.id}/contract/pdf").content)
    assert "Abschlaege: 30/70" in text_ and "KW 1" in text_


def test_draft_by_hand_for_old_orders_and_after_basis_change(threaded_db_session, router_test_client):
    from app.contract_basis import change_order_contract_basis
    from app.routers import contract_templates
    db = threaded_db_session
    order = beauftragen(db, make_quote(db))  # keine Vorlage -> kein Entwurf
    client = router_test_client(db, contract_templates.router, role="buero_auftrag")
    state = client.get(f"/api/orders/{order.id}/contract").json()
    assert state["contract"] is None and state["template_available"] is False
    assert client.post(f"/api/orders/{order.id}/contract").status_code == 409
    save(db)
    state = client.post(f"/api/orders/{order.id}/contract").json()
    assert state["contract"]["status"] == "entwurf" and state["template_reviewed"] is False
    assert client.post(f"/api/orders/{order.id}/contract").status_code == 409  # höchstens einer
    change_order_contract_basis(db, load_order(db, order.id), contract_basis="bgb", reason="Kunde wünscht BGB")
    assert client.get(f"/api/orders/{order.id}/contract").json()["template_available"] is False
    assert client.get(f"/api/orders/{order.id}/contract/pdf").status_code == 409


def test_finished_contract_is_not_editable():
    db = db_session()
    save(db)
    order = beauftragen(db, make_quote(db))
    draft = get_order_contract(db, order.id)
    draft.status = "festgeschrieben"
    db.commit()
    with pytest.raises(ValueError, match="Nur ein Vertragsentwurf"):
        update_contract_draft(db, draft, {"payment_plan": "neu"})


# --- Punkt 4: PDF ----------------------------------------------------------------------------------

def test_consumer_sections_only_for_consumers():
    db = db_session()
    for key in ("vob_b", "bgb_vob_c_4_5"):
        save(db, key)
    consumer = contract_pdf(db, beauftragen(db, make_quote(db, number="0001", is_consumer=True)))
    business = contract_pdf(db, beauftragen(db, make_quote(db, number="0002", is_consumer=False)))
    assert CONSUMER_TEXT in pdf_text(consumer) and "vorzeitigen Beginn" in pdf_text(consumer)
    assert CONSUMER_TEXT not in pdf_text(business) and "vorzeitigen Beginn" not in pdf_text(business)
    # Gegenprobe: der Abschnitt für alle steht in beiden.
    assert ALWAYS_TEXT in pdf_text(consumer) and ALWAYS_TEXT in pdf_text(business)


def test_watermark_on_every_page_only_while_unreviewed():
    db = db_session()
    long_sections = SECTIONS + [section(f"Paragraf {n}", "Langer Text. " * 120) for n in range(5, 9)]
    save(db, sections=long_sections)
    order = beauftragen(db, make_quote(db))
    pages = page_texts(contract_pdf(db, order))
    assert len(pages) >= 3
    assert "Angebotssumme brutto" in pages[-1]  # das Angebot als Anlage, auf der letzten Seite
    assert "Anlage: Angebot A-0001" in "\n".join(pages)
    assert all(CONTRACT_WATERMARK_TEXT in p for p in pages), [i for i, p in enumerate(pages) if CONTRACT_WATERMARK_TEXT not in p]
    # Gegenprobe: geprüft -> auf keiner Seite.
    save(db, sections=long_sections, reviewed=True)
    reviewed_pages = page_texts(contract_pdf(db, order))
    assert len(reviewed_pages) == len(pages)
    assert not any(CONTRACT_WATERMARK_TEXT in p for p in reviewed_pages)


def test_contract_pdf_replaces_placeholders_and_uses_the_shared_frame():
    from app.document_frame import RENDERERS_USING_SHARED_FRAME
    from app.document_layout import DOCUMENT_TYPES
    assert "contract" in RENDERERS_USING_SHARED_FRAME and "contract" in DOCUMENT_TYPES
    db = db_session()
    save(db)
    order = beauftragen(db, make_quote(db))
    first = page_texts(contract_pdf(db, order))[0]
    assert f"Bauvertrag {order.order_number}" in first
    assert "Kunde 0001" in first and "595,00 EUR" in first
    assert "{" not in first  # kein Platzhalter unaufgelöst
    assert "Auftragsnr." in first and order.order_number in first  # Kopfbereich wie beim Auftrag


# --- Punkt 5: Monteure ------------------------------------------------------------------------------

def test_monteur_gets_403_on_every_contract_route(threaded_db_session, router_test_client):
    from app.routers import contract_templates
    db = threaded_db_session
    save(db)
    order = beauftragen(db, make_quote(db))
    field = router_test_client(db, contract_templates.router, role="field")
    assert field.get(f"/api/orders/{order.id}/contract").status_code == 403
    assert field.post(f"/api/orders/{order.id}/contract").status_code == 403
    assert field.put(f"/api/orders/{order.id}/contract", json={"payment_plan": "x"}).status_code == 403
    assert field.get(f"/api/orders/{order.id}/contract/pdf").status_code == 403
    office = router_test_client(db, contract_templates.router, role="buero_auftrag")
    assert office.get(f"/api/orders/{order.id}/contract").status_code == 200
    assert office.get(f"/api/orders/{order.id}/contract/pdf").status_code == 200


# --- Migration ------------------------------------------------------------------------------------

def _migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_vertragsvorlagen.py"))
    spec = importlib.util.spec_from_file_location("migration_1832_vertragsvorlagen", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn_name):
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def test_migration_downgrade_refuses_while_data_would_be_lost_and_upgrade_restores():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO contract_templates (basis_key, updated_at) VALUES ('vob_b', '2026-10-01 00:00:00')"))
    with pytest.raises(RuntimeError, match="1 Vertragsvorlagen"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM contract_templates"))
    _run(engine, "downgrade")
    insp = inspect(engine)
    assert not {"contract_templates", "contract_template_sections", "order_contracts"} & set(insp.get_table_names())
    assert "execution_period" not in {c["name"] for c in insp.get_columns("orders")}
    _run(engine, "upgrade")
    insp = inspect(engine)
    assert {"contract_templates", "contract_template_sections", "order_contracts"} <= set(insp.get_table_names())
    assert "execution_period" in {c["name"] for c in insp.get_columns("orders")}


def test_deleting_an_order_takes_its_draft_along():
    db = db_session()
    save(db)
    order = beauftragen(db, make_quote(db))
    assert db.query(OrderContract).count() == 1
    db.delete(load_order(db, order.id))
    db.commit()
    assert db.query(OrderContract).count() == 0
