"""Verlauf der Akte (seit 1.9.127, Stufe 5, R2, Punkt 4; app/akte_verlauf.py, Vorlage bildgrundlage/entwurf_stufe5/akte-verlauf.html).

- Ein Strom je Projekt: Änderungen, Versand, Zahlungen, Berichte, Status, Termine; Zeitbuchungen nicht (eigene Seite „Zeiten“).
- Einträge einer Aktion (gleiches Konto, gleiche Anfrage, höchstens 5 s) als eine Zeile mit allen Einzelheiten; der Versand derselben Aktion in
  derselben Zeile.
- Filter nach Art und Auftrag (über die Kennung des Datensatzes): mit gewähltem Auftrag dessen Zeilen und die projektweiten.
- Seiten über `vor`, nichts doppelt und nichts verloren; Büro – Auftrag ohne Lohnfelder (wie /api/audit-logs), die Monteurin 403."""

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

import app.akte_verlauf as akte_verlauf
from app.audit import reset_audit_context, set_audit_context
from app.auftragsstatus import status_aendern
from app.models import AuditLog, EmailDispatch, Invoice, Order, OrderItem, Project
from app.routers import projects as projects_router
from app.time_tracking import create_manual_entry
from tests.leistungszeitraum import festschreiben
from tests.test_v381_zahlungen import _auftrag, _buchen

D = Decimal


class _Anfrage:
    def __init__(self, konto_id, name, methode, pfad):
        self.konto = SimpleNamespace(id=konto_id, display_name=name)
        self.anfrage = SimpleNamespace(url=SimpleNamespace(path=pfad), method=methode)

    def __enter__(self):
        self.t = set_audit_context(self.konto, self.anfrage)

    def __exit__(self, *a):
        reset_audit_context(self.t)


def _zweiter_auftrag(db, order):
    """Ein zweiter Auftrag im selben Projekt."""
    o = Order(order_number=f"{order.order_number}-B", project_id=order.project_id, source_quote_id=order.source_quote_id + 10_000,
              quote_number_snapshot="A-B", title="PV", vat_rate=D("19.00"), customer_name=order.customer_name)
    db.add(o)
    db.flush()
    db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Modul", quantity=D("1"), unit="Stk", unit_price=D("100")))
    db.commit()
    return o


def _strom(client, project_id, **abfrage):
    antwort = client.get(f"/api/projects/{project_id}/verlauf", params=abfrage)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _welt(router_test_client, db):
    """db: threaded_db_session (TestClient), mit den Grunddaten wie in _db()."""
    from app.grunddaten import anlegen
    anlegen(db)
    db.commit()
    order = _auftrag(db)
    zweiter = _zweiter_auftrag(db, order)
    with _Anfrage(7, "Olga Office", "PUT", f"/api/orders/{order.id}/items/{order.items[0].id}"):
        item = db.get(OrderItem, order.items[0].id)
        item.quantity = D("120")
        item.short_text = "Dacheindeckung neu"
        db.commit()
    with _Anfrage(7, "Olga Office", "POST", f"/api/orders/{zweiter.id}/status"):
        status_aendern(db, zweiter.id, "pausiert", "Wechselrichter erst ab KW 47", user_id=7, user_name="Olga Office")
    with _Anfrage(8, "Fin Finanzen", "PUT", f"/api/projects/{order.project_id}"):
        p = db.get(Project, order.project_id)
        p.name = "Dach neu"
        db.commit()
    client = router_test_client(db, projects_router.router)
    return {"db": db, "order": db.get(Order, order.id), "zweiter": db.get(Order, zweiter.id), "client": client}


def test_eine_aktion_eine_zeile_mit_einzelheiten(router_test_client, threaded_db_session):
    w = _welt(router_test_client, threaded_db_session)
    strom = _strom(w["client"], w["order"].project_id)["eintraege"]
    position = next(e for e in strom if "Dacheindeckung" in e["titel"] or "Menge" in e["titel"])
    felder = {z["field_name"] for z in position["einzelheiten"]}
    assert {"quantity", "short_text"} <= felder  # zwei Änderungen derselben Anfrage, eine Zeile
    assert position["konto"] == "Olga Office" and position["art"] == "aenderung"
    assert [a["order_id"] for a in position["auftraege"]] == [w["order"].id]


def test_status_mit_begruendung_und_filter_nach_art(router_test_client, threaded_db_session):
    w = _welt(router_test_client, threaded_db_session)
    strom = _strom(w["client"], w["order"].project_id, art="status")["eintraege"]
    assert len(strom) == 1
    assert "pausiert" in strom[0]["titel"] and strom[0]["unterzeile"] == "Begründung: Wechselrichter erst ab KW 47"
    assert strom[0]["art_label"] == "Status"


def test_filter_nach_auftrag_behaelt_projektweite_zeilen(router_test_client, threaded_db_session):
    w = _welt(router_test_client, threaded_db_session)
    pid = w["order"].project_id
    alle = _strom(w["client"], pid)["eintraege"]
    erster = _strom(w["client"], pid, auftrag=w["order"].id)["eintraege"]
    zweiter = _strom(w["client"], pid, auftrag=w["zweiter"].id)["eintraege"]
    projekt = [e for e in alle if not e["auftraege"]]
    assert projekt and all(e in erster and e in zweiter for e in projekt)  # die Änderung am Projekt in beiden
    assert not any(w["zweiter"].id in [a["order_id"] for a in e["auftraege"]] for e in erster)
    assert any("pausiert" in e["titel"] for e in zweiter) and not any("pausiert" in e["titel"] for e in erster)


def test_zeitbuchungen_nicht_im_strom(router_test_client, threaded_db_session):
    w = _welt(router_test_client, threaded_db_session)
    from app.models import Employee
    e = Employee(employee_number="MA-V1", first_name="Mia", last_name="M", employee_group="gewerblich", hourly_wage=D("20"),
                 weekly_hours=D("40"), active=True)
    w["db"].add(e)
    w["db"].commit()
    create_manual_entry(w["db"], employee_id=e.id, order_id=w["order"].id, work_date=datetime(2026, 9, 7).date(), hours=D("2"), entry_type="site")
    assert w["db"].scalar(select(AuditLog.id).where(AuditLog.entity_type == "Zeitbuchung", AuditLog.project_id == w["order"].project_id))
    strom = _strom(w["client"], w["order"].project_id)["eintraege"]
    assert not any(z["entity_type"] == "Zeitbuchung" for e in strom for z in e["einzelheiten"])


def test_versand_und_zahlung(router_test_client, threaded_db_session):
    w = _welt(router_test_client, threaded_db_session)
    db, order = w["db"], w["order"]
    from tests.test_v381_zahlungen import _abschlag
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/invoices/x/send"):
        rechnung = _abschlag(db, order)
    jetzt = db.get(AuditLog, db.scalar(select(AuditLog.id).where(AuditLog.entity_type == "Rechnung").order_by(AuditLog.id.desc()))).occurred_at
    db.add(EmailDispatch(dispatch_key="verlauf-1", message_ref="m-verlauf-1", status="gesendet", channel="smtp", document_type="rechnung",
                         document_id=rechnung.id, document_number=rechnung.invoice_number, to_recipients="buchhaltung@example.com",
                         subject="Rechnung", created_at=jetzt + timedelta(seconds=2), created_by_user_id=8, created_by_name="Fin Finanzen"))
    db.commit()
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/payments"):
        _buchen(db, rechnung, "100")
    strom = _strom(w["client"], order.project_id)["eintraege"]
    versand = [e for e in strom if e["art"] == "versand"]
    assert len(versand) == 1 and "buchhaltung@example.com" in versand[0]["titel"]
    assert any(z["entity_type"] == "Rechnung" for z in versand[0]["einzelheiten"])  # dieselbe Aktion, eine Zeile
    assert versand[0]["versand"]["document_type"] == "rechnung" and [a["order_id"] for a in versand[0]["auftraege"]] == [order.id]
    zahlungen = _strom(w["client"], order.project_id, art="zahlung")["eintraege"]
    assert zahlungen and all(e["art"] == "zahlung" for e in zahlungen)
    assert [a["order_id"] for a in zahlungen[0]["auftraege"]] == [order.id]


def test_gruppe_nur_mit_gleichem_konto_pfad_und_zeit():
    t = datetime(2026, 10, 1, 10, 0, 0)

    def z(i, sek, konto=1, pfad="/a"):
        return SimpleNamespace(id=i, occurred_at=t - timedelta(seconds=sek), actor_user_id=konto, actor_name=f"K{konto}", request_path=pfad,
                               request_method="PUT")
    gruppen = akte_verlauf.gruppieren([z(1, 0), z(2, 2), z(3, 9), z(4, 10, konto=2), z(5, 11, pfad="/b"), z(6, 12, pfad=None),
                                       z(7, 12, pfad=None)], {})
    assert [[x.id for x in g.zeilen] for g in gruppen] == [[1, 2], [3], [4], [5], [6], [7]]


def test_seiten_ohne_luecke_und_doppel(router_test_client, monkeypatch, threaded_db_session):
    w = _welt(router_test_client, threaded_db_session)
    db, order = w["db"], w["order"]
    for i in range(12):  # zwölf Aktionen, je zwei Zeilen
        with _Anfrage(7, "Olga Office", "PUT", f"/api/orders/{order.id}/r{i}"):
            o = db.get(Order, order.id)
            o.remarks = f"Bemerkung {i}"
            o.execution_period = f"KW {i}"
            db.commit()
    alle = _strom(w["client"], order.project_id)["eintraege"]
    monkeypatch.setattr(akte_verlauf, "ZEILEN_JE_ABRUF", 5)
    gesehen, vor = [], None
    for _ in range(30):
        seite = _strom(w["client"], order.project_id, **({"vor": vor} if vor else {}))
        gesehen += seite["eintraege"]
        vor = seite["vor"]
        if not vor:
            break
    assert [(e["zeitpunkt"], e["titel"]) for e in gesehen] == [(e["zeitpunkt"], e["titel"]) for e in alle]


def test_rollen(router_test_client, threaded_db_session):
    w = _welt(router_test_client, threaded_db_session)
    db, pid = w["db"], w["order"].project_id
    assert router_test_client(db, projects_router.router, role="buero_auftrag").get(f"/api/projects/{pid}/verlauf").status_code == 200
    assert router_test_client(db, projects_router.router, role="field").get(f"/api/projects/{pid}/verlauf").status_code == 403
    assert router_test_client(db, projects_router.router).get("/api/projects/999999/verlauf").status_code == 404
    assert router_test_client(db, projects_router.router).get(f"/api/projects/{pid}/verlauf", params={"art": "unsinn"}).status_code == 422
