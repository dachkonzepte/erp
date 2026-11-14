"""Version 1.9.245 (Stufe 6, R4, Punkt 0c; Befund R3b 5b): der Schnellauftrag in einer Transaktion wie die Kranvermietung.

    ein Commit   Projekt, Angebot, Position und Auftrag mit einem Commit am Ende (bis 1.9.244 dreimal unterwegs)
    Fehler       scheitert ein Schritt, nimmt die Sitzung alles zurück: kein Projekt, kein Angebot, keine Position, keine Nummer verbraucht
    Aufrufer     Folgeauftrag aus einem Befund und „Wartung durchführen“ committen den Schnellauftrag mit ihrer eigenen Änderung (Verweis am Befund,
                 Vertrag am Projekt) -- ein Commit, scheitert etwas, bleibt nichts zurück
"""

from datetime import date

import pytest
from sqlalchemy import event, func, select

import app.quick_service_orders as schnell
from app.findings import create_finding, create_follow_up_project_for_task
from app.maintenance_contracts import create_contract, create_maintenance_visit
from app.models import Finding, Order, Project, ProjectProfile, Quote, QuoteItem
from app.quick_service_orders import create_quick_service_order
from app.service_reports import create_report
from app.settings import preview_number
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v214_findings_and_photos import _build_extra_order


def _commits(db):
    zaehler = {"n": 0}

    def gezaehlt(_session):
        zaehler["n"] += 1
    event.listen(db, "after_commit", gezaehlt)
    return zaehler


def _anzahl(db):
    return tuple(db.scalar(select(func.count()).select_from(m)) for m in (Project, Quote, QuoteItem, Order))


def _scheitert(monkeypatch):
    def kaputt(*_a, **_k):
        raise RuntimeError("Auftrag scheitert")
    monkeypatch.setattr(schnell, "create_order_from_quote", kaputt)


def test_ein_commit_fuer_die_ganze_kette():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    commits = _commits(db)
    r = create_quick_service_order(db, customer_id=customer.id, property_id=prop.id, order_type="reparatur", title="Rinne")
    assert commits["n"] == 1
    assert db.get(Order, r["order_id"]).items[0].short_text == "Reparatur nach Aufwand"


def test_scheitert_der_auftrag_bleibt_nichts(monkeypatch):
    db = db_session()
    customer, prop = make_customer_and_property(db)
    vorher, projekt_nr, angebot_nr = _anzahl(db), preview_number(db, "project"), preview_number(db, "quote")
    _scheitert(monkeypatch)
    commits = _commits(db)
    with pytest.raises(RuntimeError):
        create_quick_service_order(db, customer_id=customer.id, property_id=prop.id, order_type="reparatur", title="Rinne")
    assert commits["n"] == 0
    assert _anzahl(db) == vorher
    assert (preview_number(db, "project"), preview_number(db, "quote")) == (projekt_nr, angebot_nr)  # keine Nummer verbraucht
    monkeypatch.undo()
    r = create_quick_service_order(db, customer_id=customer.id, property_id=prop.id, order_type="reparatur", title="Rinne")
    assert db.get(Project, r["project_id"]).project_number == projekt_nr  # die Sitzung ist danach wieder nutzbar


def test_folgeauftrag_aus_einem_befund_ein_commit_und_bei_fehler_nichts(monkeypatch):
    db = db_session()
    order, _customer, _project = _build_extra_order(db, "9101")
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Ziegel gebrochen", "dringend", "buero_pruefen")
    vorher = _anzahl(db)
    _scheitert(monkeypatch)
    with pytest.raises(RuntimeError):
        create_follow_up_project_for_task(db, finding["follow_up_task_id"])
    assert _anzahl(db) == vorher
    f = db.get(Finding, finding["id"])
    assert (f.follow_up_order_id, f.follow_up_project_id) == (None, None)
    monkeypatch.undo()
    commits = _commits(db)
    r = create_follow_up_project_for_task(db, finding["follow_up_task_id"])
    assert commits["n"] == 1
    assert db.get(Finding, finding["id"]).follow_up_order_id == r["order_id"]


def test_wartung_durchfuehren_vorgang_und_vertrag_in_einem_commit(monkeypatch):
    """Scheitert der Verweis auf den Vertrag (nach dem Schnellauftrag), bleibt auch der Vorgang nicht stehen -- bis 1.9.244 war er da schon festgeschrieben."""
    import app.maintenance_contracts as wartung
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Wartungsvertrag", 12, date(2026, 11, 10))
    vorher = _anzahl(db)

    def kaputt(*_a, **_k):
        raise RuntimeError("Profil scheitert")
    monkeypatch.setattr(wartung, "get_or_create_project_profile", kaputt)
    with pytest.raises(RuntimeError):
        create_maintenance_visit(db, contract["id"])
    assert _anzahl(db) == vorher
    monkeypatch.undo()
    r = create_maintenance_visit(db, contract["id"])
    profil = db.scalar(select(ProjectProfile).where(ProjectProfile.project_id == r["project_id"]))
    assert profil.source_maintenance_contract_id == contract["id"]
