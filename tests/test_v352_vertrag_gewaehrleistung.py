"""Version 1.8.50 -- Stufe 2c-2a, Punkt 2: Platzhalter {gewaehrleistung} in Vertragsvorlagen
(docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.50").

- {gewaehrleistung} setzt den Text der Dauer ein ("5 Jahre", "18 Monate", "2 Jahre und 10 Tage").
- Nutzt die Vorlage ihn, ist Festschreiben gesperrt, solange die Dauer am Auftrag nicht festgelegt ist.
- Danach sind Dauer und Leistungsart gesperrt -- wie der Kundenwechsel bei einem festgeschriebenen Vertrag.

Gegenprobe: eine Vorlage ohne den Platzhalter schreibt ohne Dauer fest und sperrt nichts. Gegen PostgreSQL (opt-in über
ERP_TEST_POSTGRES_URL): Festschreiben und Festlegen der Dauer warten aufeinander."""

import threading
import time
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app.berlin_time import berlin_today
from app.contract_versions import ContractStateError, freeze_contract, frozen_content, start_new_version
from app.database import Base
from app.models import Order
from app.orders import load_order
from app.routers import acceptances as acceptances_router
from app.routers import contract_templates as contract_router
from app.routers import orders as orders_router
from app.warranty import WarrantyLockedError, contract_duration_text, set_order_warranty
from tests.test_v335_vertragsvorlagen import SECTIONS, beauftragen, save, section
from tests.test_v336_vertrag_festschreiben import _freeze, _quote, _versions, world  # noqa: F401  (Fixture)
from tests.test_v349_abnahme_und_gewaehrleistung import PG_TEST_DATABASE_URL, _waits_for

MIT_GEWAEHRLEISTUNG = SECTIONS + [section("Paragraf 5 Gewaehrleistung",
                                          "Die Gewaehrleistung betraegt {gewaehrleistung} ab Abnahme.")]


def _vorlage(db):
    """Die geprüfte Vorlage der Fixture um einen Abschnitt mit {gewaehrleistung} ergänzen -- mit neuem Prüfvermerk:
    ein geänderter Text mit demselben Vermerk setzt die Prüfung bewusst zurück (save_template())."""
    save(db, sections=MIT_GEWAEHRLEISTUNG, reviewed_on=berlin_today(), by="RA Gewaehrleistung")


def _client(db, router_test_client, role="buero_auftrag"):
    return router_test_client(db, contract_router.router, acceptances_router.router, orders_router.router, role=role)


def _dauer(client, order, monate, kind="bauwerk", grund=None):
    return client.put(f"/api/orders/{order.id}/warranty",
                      json={"work_kind": kind, "warranty_months": monate, "warranty_days": 0, "reason": grund})


@pytest.mark.parametrize("monate,tage,text_", [
    (60, 0, "5 Jahre"), (12, 0, "1 Jahr"), (48, 0, "4 Jahre"), (18, 0, "18 Monate"), (1, 0, "1 Monat"),
    (24, 10, "2 Jahre und 10 Tage"), (0, 30, "30 Tage"), (0, 1, "1 Tag"), (None, None, "nicht festgelegt"),
])
def test_contract_duration_text(monate, tage, text_):
    assert contract_duration_text(monate, tage) == text_


def test_placeholder_is_offered_and_filled(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    liste = client.get("/api/settings/contract-templates").json()["placeholders"]
    eintrag = next(p for p in liste if p["placeholder"] == "{gewaehrleistung}")
    assert "5 Jahre" in eintrag["description"]
    _vorlage(db)
    vorlage = next(t for t in client.get("/api/settings/contract-templates").json()["templates"]
                   if t["basis_key"] == "bgb_vob_c_4_5")
    assert vorlage["unknown_placeholders"] == [] and vorlage["has_content"] is True


def test_freeze_is_locked_while_the_duration_is_not_set(world, router_test_client):
    db = world
    _vorlage(db)
    order = beauftragen(db, _quote(db))
    client = _client(db, router_test_client)
    stand = client.get(f"/api/orders/{order.id}/contract").json()
    assert stand["warranty_missing"] is True
    r = _freeze(client, order, attachment="aktuell")
    assert r.status_code == 409 and "{gewaehrleistung}" in r.json()["detail"] and "nicht festgelegt" in r.json()["detail"]
    assert _versions(db, order) == []
    assert _dauer(client, order, 60).status_code == 200  # Vorschlag BGB, Bauwerk
    assert client.get(f"/api/orders/{order.id}/contract").json()["warranty_missing"] is False
    r = _freeze(client, order, attachment="aktuell")
    assert r.status_code == 200, r.text
    [version] = _versions(db, order)
    content = frozen_content(version)
    assert content["placeholders"]["{gewaehrleistung}"] == "5 Jahre" and "{gewaehrleistung}" in content["used_placeholders"]
    assert any("betraegt 5 Jahre ab Abnahme" in s["text"] for s in content["sections"])


def test_after_freezing_duration_and_work_kind_are_locked(world, router_test_client):
    db = world
    _vorlage(db)
    order = beauftragen(db, _quote(db))
    client = _client(db, router_test_client)
    _dauer(client, order, 60)
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    for monate, kind, grund in ((48, "bauwerk", "doch 4 Jahre"), (24, "sonstige", None), (60, "sonstige", "x")):
        r = _dauer(client, order, monate, kind, grund)
        assert r.status_code == 409 and "Fassung 1" in r.json()["detail"], r.text
    r = client.get(f"/api/orders/{order.id}/warranty-preview",
                   params={"work_kind": "bauwerk", "warranty_months": 48, "warranty_days": 0})
    assert r.status_code == 409
    o = client.get(f"/api/orders/{order.id}").json()
    assert o["warranty_months"] == 60 and o["work_kind"] == "bauwerk" and "Fassung 1" in o["warranty_lock_text"]
    # Auch eine neue Fassung (wieder Entwurf) hebt die Sperre nicht auf -- wie beim Kundenwechsel.
    start_new_version(db, load_order(db, order.id), user_name="Test")
    assert _dauer(client, order, 48, grund="neu verhandelt").status_code == 409
    with pytest.raises(WarrantyLockedError):
        set_order_warranty(db, load_order(db, order.id), work_kind="bauwerk", warranty_months=48, warranty_days=0,
                           reason="direkt")


def test_template_without_the_placeholder_locks_nothing(world, router_test_client):
    """Gegenprobe: die Vorlage nutzt {gewaehrleistung} nicht -- Festschreiben ohne Dauer, danach frei änderbar."""
    db = world
    order = beauftragen(db, _quote(db))
    client = _client(db, router_test_client)
    assert client.get(f"/api/orders/{order.id}/contract").json()["warranty_missing"] is False
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    assert _dauer(client, order, 60).status_code == 200
    assert _dauer(client, order, 48, grund="vereinbart").status_code == 200
    assert client.get(f"/api/orders/{order.id}").json()["warranty_lock_text"] is None


def test_draft_shows_not_set_and_business_function_refuses(world):
    db = world
    _vorlage(db)
    order = beauftragen(db, _quote(db))
    from app.contract_templates import contract_content, get_order_contract
    content = contract_content(db, order, get_order_contract(db, order.id))
    assert any("betraegt nicht festgelegt ab Abnahme" in s["text"] for s in content["sections"])
    with pytest.raises(ContractStateError, match="nicht festgelegt"):
        freeze_contract(db, order, attachment="aktuell", user_name="Test")


def test_order_page_shows_the_lock():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "app" / "templates" / "_abnahme.html").read_text(encoding="utf-8")
    assert "warranty_lock_text" in source


# ---------------------------------------------------------------------------
# PostgreSQL: Festschreiben und Festlegen der Dauer warten aufeinander
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from app import sent_documents as sent_documents_module
    monkeypatch.setattr(sent_documents_module, "SENT_DOCUMENT_ROOT", tmp_path / "ablage")
    schema = f"pgtest_vertrag_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=5,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        from app.grunddaten import anlegen
        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            save(setup, sections=MIT_GEWAEHRLEISTUNG, reviewed=True)
            from tests.test_v325_contract_basis import make_quote
            order = beauftragen(setup, make_quote(setup, number="0352", is_consumer=True), order_date=date(2026, 10, 1))
            order_id = order.id
        finally:
            setup.close()
        yield Session, order_id
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _paused(db, release, ready):
    commit = db.commit

    def angehalten():
        db.flush()
        ready.set()
        release.wait(timeout=30)
        commit()
    db.commit = angehalten


def test_postgresql_duration_waits_for_a_running_freeze(pg):
    """Festschreiben läuft (Fassung geschrieben, noch nicht committet) -- eine gleichzeitige Änderung der Dauer wartet
    und wird danach abgelehnt (409), statt den festgeschriebenen Text zu überholen."""
    Session, order_id = pg
    setup = Session()
    set_order_warranty(setup, setup.get(Order, order_id), work_kind="bauwerk", warranty_months=60, warranty_days=0,
                       reason=None)
    setup.close()
    holder, ready = Session(), threading.Event()

    def hold(release):
        def run():
            _paused(holder, release, ready)
            freeze_contract(holder, load_order(holder, order_id), attachment="aktuell", user_name="A")
        threading.Thread(target=run).start()
        ready.wait(timeout=10)

    def second():
        db = Session()
        try:
            return set_order_warranty(db, db.get(Order, order_id), work_kind="bauwerk", warranty_months=48,
                                      warranty_days=0, reason="B")
        finally:
            db.close()
    done = _waits_for(hold, second)
    time.sleep(0.2)
    holder.close()
    assert isinstance(done["result"], WarrantyLockedError) and done["seconds"] >= 0.9


def test_postgresql_freeze_waits_for_a_running_duration_change(pg):
    """Die Dauer wird gerade geändert (noch nicht committet) -- ein gleichzeitiges Festschreiben wartet und schreibt
    danach den NEUEN Wert fest, nicht den beim Laden gelesenen."""
    Session, order_id = pg
    setup = Session()
    set_order_warranty(setup, setup.get(Order, order_id), work_kind="bauwerk", warranty_months=60, warranty_days=0,
                       reason=None)
    setup.close()
    freezer = Session()
    order_vorher = load_order(freezer, order_id)  # vor der Änderung geladen, wie im Router
    assert order_vorher.warranty_months == 60
    holder, ready = Session(), threading.Event()

    def hold(release):
        def run():
            _paused(holder, release, ready)
            set_order_warranty(holder, holder.get(Order, order_id), work_kind="bauwerk", warranty_months=48,
                               warranty_days=0, reason="4 Jahre vereinbart")
        threading.Thread(target=run).start()
        ready.wait(timeout=10)
    done = _waits_for(hold, lambda: freeze_contract(freezer, order_vorher, attachment="aktuell", user_name="B"))
    time.sleep(0.2)
    holder.close()
    try:
        assert done["seconds"] >= 0.9 and not isinstance(done["result"], Exception), done["result"]
        assert frozen_content(done["result"])["placeholders"]["{gewaehrleistung}"] == "4 Jahre"
    finally:
        freezer.close()
