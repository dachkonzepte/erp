"""Version 1.8.84 -- kein Lesepfad legt an (Regel 23 als Muster, Vorgabe R4b "Vorweg" 1).

Bis 1.8.83 füllten fünf GET-Wege beim Lesen eine Lücke und committeten: Mitarbeiterprofile (GET /api/employees, /caseworkers,
/{id}; zwei gleichzeitige Aufrufe der Auftragsseite kollidierten an employee_profiles.employee_id -- Nebenbefund 4 aus 1.8.83),
Kopf und Positionslayout eines Angebots (GET /api/quotes, /api/quotes/{id}, /api/projects/{id}/quotes, Auftragsseite über den
Abgleich-Status), die Kalkulation einer Katalogposition (GET .../calculation), die Arbeitsvorbereitung samt Materialbedarf (GET
/api/orders/{id}/work-preparation -- danach war der Abgleich mit dem Angebot gesperrt, obwohl nur jemand die Seite angesehen
hatte) und die Lohnstammdaten (Lohnliste, DATEV-Export, Stundenzettel). Seither lesen diese Wege nur und zeigen die Vorgabe, die
das Anlegen ergäbe; angelegt wird beim Anlegen des Datensatzes bzw. im ersten Schreibweg. Der Strukturtest über alle
GET-Endpunkte (auch mit Lücken in den Testdaten) steht in test_v326_monteur_datengrenze.py::test_kein_get_schreibt."""

import re
import threading
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import (
    AppUser, Customer, Employee, EmployeeFunction, EmployeePayrollSettings, EmployeeProfile, Project, Quote,
    QuoteDocumentMeta, QuoteItem, QuoteItemCalculation, QuoteItemLayout, QuoteItemMaterialCalculation, WorkPreparation,
)
from app.orders import sync_block_reasons
from app.project_pipeline_columns import default_pipeline_column_id
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.test_v080_work_preparation import setup_order

_SCHREIBEN = re.compile(r'^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"?(\w+)', re.I)


def _schreibt(engine):
    gefunden = []

    def merken(conn, cursor, statement, params, context, executemany):
        treffer = _SCHREIBEN.match(statement)
        if treffer:
            gefunden.append(treffer.group(1))
    event.listen(engine, "before_cursor_execute", merken)
    return gefunden, lambda: event.remove(engine, "before_cursor_execute", merken)


def _routers():
    from app.routers.employees import router as employees
    from app.routers.inquiries import router as inquiries
    from app.routers.orders import router as orders
    from app.routers.projects import router as projects
    from app.routers.quotes import router as quotes
    from app.routers.time_backoffice import router as time_backoffice
    from app.routers.work_preparation import router as work_preparation
    return employees, inquiries, orders, projects, quotes, time_backoffice, work_preparation


def _mitarbeiter_ohne_profil(db) -> list[Employee]:
    leute = [Employee(first_name="Alt", last_name="Bestand", job_title="Eigene Altfunktion", employee_group="gewerblich",
                      hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True),
             Employee(first_name="Ohne", last_name="Titel", employee_group="kaufmaennisch", hourly_wage=Decimal("20"),
                      weekly_hours=Decimal("40"), active=True)]
    db.add_all(leute)
    db.commit()
    return leute


def _welt_mit_luecken(db) -> dict:
    """Auftrag aus einem Katalogangebot (Kalkulation mit Material) ohne Arbeitsvorbereitung, ein Angebot ohne Kopf und Layout
    mit einer Katalogposition ohne Kalkulation, zwei Mitarbeiter ohne Profil und Lohnstammdaten."""
    order = setup_order(db)
    quote = db.get(Quote, order.source_quote_id)
    item = quote.items[0]
    db.execute(delete(QuoteItemMaterialCalculation).where(QuoteItemMaterialCalculation.calculation_id.in_(
        select(QuoteItemCalculation.id).where(QuoteItemCalculation.quote_item_id == item.id))))
    db.execute(delete(QuoteItemCalculation).where(QuoteItemCalculation.quote_item_id == item.id))
    db.execute(delete(QuoteItemLayout))
    db.execute(delete(QuoteDocumentMeta))
    db.execute(delete(WorkPreparation))
    db.commit()
    leute = _mitarbeiter_ohne_profil(db)
    db.expire_all()
    return {"order_id": order.id, "project_id": order.project_id, "quote_id": quote.id, "item_id": item.id,
            "employee_id": leute[0].id}


def _zaehlen(db) -> dict:
    return {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in (
        EmployeeProfile, EmployeeFunction, EmployeePayrollSettings, QuoteDocumentMeta, QuoteItemLayout, QuoteItemCalculation,
        WorkPreparation)}


GET_WEGE = [
    "/api/employees", "/api/employees/caseworkers", "/api/employees/{employee_id}", "/api/quotes",
    "/api/quotes/{quote_id}", "/api/projects/{project_id}/quotes", "/api/projects/{project_id}/orders",
    "/api/orders/{order_id}", "/api/quotes/{quote_id}/order", "/api/quotes/{quote_id}/items/{item_id}/calculation",
    "/api/orders/{order_id}/work-preparation", "/api/time-backoffice/payroll-employees",
    "/api/time-backoffice/datev-export?start_date=2026-01-01&end_date=2026-12-31",
]


def test_die_lesewege_legen_nichts_an_und_zeigen_die_vorgaben(threaded_db_session, router_test_client):
    db = threaded_db_session
    welt = _welt_mit_luecken(db)
    vorher = _zaehlen(db)
    client = router_test_client(db, *_routers())
    gefunden, aus = _schreibt(db.get_bind())
    try:
        antworten = {pfad: client.get(pfad.format(**welt)) for pfad in GET_WEGE}
    finally:
        aus()
    assert {p: r.status_code for p, r in antworten.items() if r.status_code != 200} == {}
    assert gefunden == []
    assert _zaehlen(db) == vorher
    # Was das Lesen zeigt -- die Vorgabe, die bis 1.8.83 angelegt worden wäre.
    mitarbeiter = {(m["first_name"], m["job_title"], m["function_id"]) for m in antworten["/api/employees"].json()}
    kaufm = db.scalar(select(EmployeeFunction.id).where(EmployeeFunction.name == "Kaufmännischer Mitarbeiter"))
    assert mitarbeiter == {("Alt", "Eigene Altfunktion", None), ("Ohne", "Kaufmännischer Mitarbeiter", kaufm)}
    meta = antworten["/api/quotes/{quote_id}"].json()["document_meta"]
    assert meta["id"] is None and meta["valid_until"] is not None and meta["contract_basis"]
    kalkulation = antworten["/api/quotes/{quote_id}/items/{item_id}/calculation"].json()
    assert kalkulation["materials"] and all(m["id"] is None for m in kalkulation["materials"])
    av = antworten["/api/orders/{order_id}/work-preparation"].json()
    assert av["id"] is None and av["material_count"] >= 4 and all(m["id"] is None for m in av["materials"])
    lohn = antworten["/api/time-backoffice/payroll-employees"].json()
    assert {r["payroll_export_enabled"] for r in lohn} == {True}


def test_ansehen_der_arbeitsvorbereitung_sperrt_den_abgleich_nicht_mehr(threaded_db_session, router_test_client):
    """Bis 1.8.83 legte das Öffnen der Seite die Arbeitsvorbereitung samt Material an -- danach war der Abgleich mit dem Angebot
    gesperrt ("Material der Arbeitsvorbereitung"). Jetzt erst nach dem Anlegen (Knopf oder erste Änderung)."""
    db = threaded_db_session
    welt = _welt_mit_luecken(db)
    client = router_test_client(db, *_routers())
    from app.models import Order
    assert client.get(f"/api/orders/{welt['order_id']}/work-preparation").status_code == 200
    assert not any("Arbeitsvorbereitung" in r for r in sync_block_reasons(db, db.get(Order, welt["order_id"])))
    angelegt = client.post(f"/api/orders/{welt['order_id']}/work-preparation")
    assert angelegt.status_code == 200 and angelegt.json()["id"] is not None
    assert angelegt.json()["material_count"] >= 4 and all(m["id"] for m in angelegt.json()["materials"])
    zweimal = client.post(f"/api/orders/{welt['order_id']}/work-preparation")  # eine vorhandene bleibt
    assert zweimal.json()["id"] == angelegt.json()["id"]
    assert db.scalar(select(func.count()).select_from(WorkPreparation)) == 1
    assert any("Arbeitsvorbereitung" in r for r in sync_block_reasons(db, db.get(Order, welt["order_id"])))


def test_erste_aenderung_legt_die_arbeitsvorbereitung_an(threaded_db_session, router_test_client):
    db = threaded_db_session
    welt = _welt_mit_luecken(db)
    client = router_test_client(db, *_routers())
    antwort = client.put(f"/api/orders/{welt['order_id']}/work-preparation",
                         json={"status": "in_planung", "planned_start": None, "planned_end": None, "site_notes": "Gerüst",
                               "material_notes": None})
    assert antwort.status_code == 200 and antwort.json()["id"] is not None and antwort.json()["site_notes"] == "Gerüst"


def test_kalkulation_speichern_legt_an_und_nimmt_die_materialzeilen_der_vorschau(threaded_db_session, router_test_client):
    db = threaded_db_session
    welt = _welt_mit_luecken(db)
    client = router_test_client(db, *_routers())
    pfad = "/api/quotes/{quote_id}/items/{item_id}/calculation".format(**welt)
    vorschau = client.get(pfad).json()
    felder = ("site_time_minutes", "workshop_time_minutes", "labor_rate", "material_markup_pct", "equipment_cost",
              "subcontractor_cost", "other_cost", "overhead_pct", "risk_profit_pct", "manual_sale_price", "notes")
    payload = {k: vorschau[k] for k in felder}
    payload["materials"] = [{"id": None, "quantity": str(Decimal(m["quantity"]) + 1), "waste_pct": m["waste_pct"],
                             "purchase_price": m["purchase_price"], "price_basis": m["price_basis"]}
                            for m in vorschau["materials"]]
    gespeichert = client.put(pfad, json=payload)
    assert gespeichert.status_code == 200, gespeichert.text
    assert all(m["id"] for m in gespeichert.json()["materials"])
    assert [Decimal(m["quantity"]) for m in gespeichert.json()["materials"]] == [
        Decimal(m["quantity"]) + 1 for m in vorschau["materials"]]
    assert db.scalar(select(func.count()).select_from(QuoteItemCalculation)
                     .where(QuoteItemCalculation.quote_item_id == welt["item_id"])) == 1


def test_angebot_anlegen_legt_den_kopf_an(threaded_db_session, router_test_client):
    """Seit 1.8.84 entsteht die Kopfzeile beim Anlegen (Angebot zum Projekt, Anfrage in Projekt umwandeln) -- vorher erst beim
    ersten Lesen."""
    db = threaded_db_session
    customer = Customer(name="K", last_name="K")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-1", name="x", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.commit()
    client = router_test_client(db, *_routers())
    neu = client.post(f"/api/projects/{project.id}/quotes", json={"title": "Neu"})
    assert neu.status_code == 200 and neu.json()["document_meta"]["id"] is not None
    from app.models import Inquiry
    anfrage = Inquiry(inquiry_number="AF-1", customer_id=customer.id, title="Anfrage", status="neu")
    db.add(anfrage)
    db.commit()
    umgewandelt = client.post(f"/api/inquiries/{anfrage.id}/convert",
                              json={"project_name": "Aus Anfrage", "create_quote": True, "quote_title": "A"})
    assert umgewandelt.status_code == 200, umgewandelt.text
    assert umgewandelt.json()["quote"]["document_meta"]["id"] is not None


def test_lohnstammdaten_entstehen_erst_beim_speichern(threaded_db_session, router_test_client):
    db = threaded_db_session
    leute = _mitarbeiter_ohne_profil(db)
    client = router_test_client(db, *_routers())
    assert client.get("/api/time-backoffice/payroll-employees").status_code == 200
    assert db.scalar(select(func.count()).select_from(EmployeePayrollSettings)) == 0
    gespeichert = client.put(f"/api/time-backoffice/payroll-employees/{leute[0].id}",
                             json={"datev_personnel_number": "77", "payroll_export_enabled": True})
    assert gespeichert.status_code == 200, gespeichert.text
    assert db.scalar(select(EmployeePayrollSettings.datev_personnel_number)) == "77"


def test_pg_gleichzeitige_lesewege_ohne_fehler_und_ohne_schreiben():
    """Gegen PostgreSQL, jede Anfrage mit eigener Verbindung, je Weg zwei Aufrufe gleichzeitig: alle 200, nichts geschrieben.
    Bis 1.8.83 scheiterte hier GET /api/employees am zweiten Anlegen desselben Profils (UNIQUE employee_profiles.employee_id)."""
    with pg_sitzung("lesewege") as db:
        welt = _welt_mit_luecken(db)
        admin = AppUser(username="admin", display_name="Admin", role="admin", active=True, password_hash="x")
        db.add(admin)
        db.commit()
        engine = db.get_bind()
        Session = sessionmaker(bind=engine)
        app = FastAPI()
        for router in _routers():
            app.include_router(router)

        @app.middleware("http")
        async def _admin(request, call_next):
            request.state.erp_user = admin
            return await call_next(request)

        def _session():
            with Session() as session:
                yield session
        app.dependency_overrides[get_db] = _session
        vorher = _zaehlen(db)
        gefunden, aus = _schreibt(engine)
        ergebnisse = {}
        try:
            barriere = threading.Barrier(2 * len(GET_WEGE))

            def aufruf(pfad, i):
                with TestClient(app, raise_server_exceptions=False) as client:
                    barriere.wait(timeout=60)
                    ergebnisse[(pfad, i)] = client.get(pfad.format(**welt)).status_code
            threads = [threading.Thread(target=aufruf, args=(pfad, i)) for pfad in GET_WEGE for i in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=120)
        finally:
            aus()
        assert {k: v for k, v in ergebnisse.items() if v != 200} == {}
        assert len(ergebnisse) == 2 * len(GET_WEGE)
        assert gefunden == []
        db.expire_all()
        assert _zaehlen(db) == vorher
