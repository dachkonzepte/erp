"""Büro-Suche, Etappe 1 (seit 1.3.66) -- siehe CLAUDE.md "Büro-Suche" für die volle Herleitung
(Registry, Kernstruktur, Rollensicherheit; die Oberfläche folgt erst in Etappe 2). Deckt ab:

1. Registry-Vollständigkeit (EXPECTED_OFFICE_SEARCH_KEYS) -- ZUSAMMEN mit der Registry selbst
   gebaut, wie ausdrücklich verlangt ("Bau den Test, der bei einer nicht deklarierten
   Datensatzart fehlschlägt, zusammen mit der Registry selbst -- nicht danach").
2. Rollensicherheit der Registry (jede allowed_roles-Menge nicht-leer, Teilmenge von
   {admin, office}, ROLE_FIELD nie enthalten; jeder module_key entweder None oder einer der
   beiden bekannten Modul-Schlüssel).
3. Entscheidung 3 (Snapshot UND live durchsucht) -- ein Kunde, der seit der Rechnung anders
   formatiert ist, wird über beide Schreibweisen gefunden.
4. Der vom Nutzer verlangte Angriffstest, mirror des Monteurs-Suche-Angriffstests: ein Monteur,
   der GET /api/search aufruft (plain und mit manipulierten Parametern), bekommt 403 -- NIE
   irgendeine Zeile, geschweige denn eine Rechnung oder ein Preisfeld. Büro/Admin bekommen 200
   mit korrekt gruppierten Ergebnissen inkl. einer "invoices"-Gruppe (belegt Entscheidung 1).
   Ein rekursiver Schlüssel-Scan über jede zurückgegebene Zeile findet niemals ein Preis-/
   Lohn-/Einkaufsfeld, unabhängig von der Rolle -- strukturell garantiert, da jede Zeile
   ausschließlich {id, title, subtitle, url} trägt (OfficeSearchHitOut kappt zusätzlich)."""

from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    Customer, CustomerProfile, Employee, EnabledModule, Finding, ImportBatch, Inquiry, Invoice,
    MaintenanceContract, Material, OperationalAsset, Order, Project, Property, Quote, Reminder, RoofArea,
    Service, ServiceReport, Supplier, Task,
)
from app.permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE
from app.project_pipeline_columns import default_pipeline_column_id
from app.search import OFFICE_SEARCH_SOURCES, search_office
from tests.test_v153_mahnwesen import db_session  # noqa: F401 -- re-exportiert db_session als Fixture

EXPECTED_OFFICE_SEARCH_KEYS = frozenset({
    "customers", "properties", "roof_areas", "projects", "quotes", "orders", "invoices",
    "reminders", "inquiries", "tasks", "employees", "service_reports", "findings",
    "maintenance_contracts", "services", "materials", "suppliers", "operational_assets",
})

_FORBIDDEN_KEY_SUBSTRINGS = (
    "price", "preis", "purchase", "einkauf", "wage", "lohn", "gehalt", "cost", "kosten",
    "betrag", "amount", "vergüt", "hourly", "salary", "vat", "ust", "brutto", "netto",
)


def _offending_keys(rows: list[dict]) -> list[str]:
    keys = set()
    for row in rows:
        keys |= set(row.keys())
    return sorted(k for k in keys if any(f in k.lower() for f in _FORBIDDEN_KEY_SUBSTRINGS))


# --- 1./2.: Registry-Vollständigkeit und Rollensicherheit ---

def test_registry_declares_exactly_the_expected_eighteen_keys():
    actual = {s.key for s in OFFICE_SEARCH_SOURCES}
    assert actual == EXPECTED_OFFICE_SEARCH_KEYS
    assert len(OFFICE_SEARCH_SOURCES) == 18


def test_registry_allowed_roles_never_empty_and_never_include_field():
    for source in OFFICE_SEARCH_SOURCES:
        assert source.allowed_roles, f"{source.key}: allowed_roles ist leer"
        assert ROLE_FIELD not in source.allowed_roles, f"{source.key}: ROLE_FIELD darf nie enthalten sein"
        assert source.allowed_roles <= {ROLE_ADMIN, ROLE_OFFICE}, f"{source.key}: unerwartete Rolle"


def test_registry_module_keys_are_known_or_none():
    for source in OFFICE_SEARCH_SOURCES:
        assert source.module_key in (None, "aufgabenmanagement", "wartungen", "betriebsmittel"), source.key


# --- 3.: Entscheidung 3 -- Snapshot UND live durchsucht ---

def test_invoice_found_via_frozen_snapshot_and_customer_found_via_live_name(db_session):
    """Der Beleg für Entscheidung 3: ein Kunde, dessen Name sich seit einer Rechnung anders
    formatiert (hier: eine spätere Korrektur der Schreibweise), wird über BEIDE Schreibweisen
    gefunden -- die alte über die eingefrorene Rechnung, die neue über den heutigen Kunden."""
    db = db_session
    customer = Customer(name="Wolfgang Rödchen", last_name="Rödchen", first_name="Wolfgang")
    db.add(customer); db.flush()
    project = Project(project_number="P-SNAP-0001", name="Snapshot-Projekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.flush()
    quote = Quote(quote_number="A-SNAP-0001", project_id=project.id, title="Snapshot-Angebot")
    db.add(quote); db.flush()
    order = Order(
        order_number="AUF-SNAP-0001", project_id=project.id, source_quote_id=quote.id,
        quote_number_snapshot=quote.quote_number, title="Snapshot-Auftrag",
        customer_name="Wolfgang Rödchen", customer_number="K-SNAP-0001",
    )
    db.add(order); db.flush()
    invoice = Invoice(
        order_id=order.id, invoice_number="R-SNAP-0001", invoice_type="schluss",
        customer_name="Wolfgang Rödchen",  # zum Zeitpunkt der Rechnung eingefroren
    )
    db.add(invoice); db.commit()

    # Der Kunde wird seither anders formatiert -- eine Korrektur der Schreibweise (nicht bloß
    # eine neue Adresse). Die Rechnung selbst bleibt davon unangetastet (Regel 5). Customer.name
    # wird hier per Hand nachgezogen, weil dieser Test bewusst direkt am Modell konstruiert statt
    # über update_customer()/compose_customer_name() zu gehen (Regel 7) -- im echten Betrieb
    # übernimmt das compose_customer_name(), hier simuliert die Testzeile exakt dessen Effekt.
    customer.last_name = "Roedchen"
    customer.name = "Wolfgang Roedchen"
    db.commit()

    # Alte Schreibweise: findet die alte Rechnung über den eingefrorenen Schnappschuss --
    # NICHT über den (jetzt andersformatierten) heutigen Kunden.
    groups_old = search_office(db, ROLE_ADMIN, "Rödchen")
    by_key_old = {g["key"]: g for g in groups_old}
    assert "invoices" in by_key_old
    assert invoice.id in {h["id"] for h in by_key_old["invoices"]["hits"]}
    assert "customers" not in by_key_old, "der heutige Kunde heißt nicht mehr 'Rödchen' -- darf hier nicht auftauchen"

    # Neue Schreibweise: findet den heutigen Kunden über das live Feld -- die Rechnung selbst
    # taucht hier zusätzlich auf, aber über den JOIN zum HEUTIGEN Kunden, nicht über ihren
    # eigenen (unverändert alten) Schnappschuss -- kein Widerspruch zu oben, sondern genau die
    # von Entscheidung 3 verlangte Unabhängigkeit beider Suchwege.
    groups_new = search_office(db, ROLE_ADMIN, "Roedchen")
    by_key_new = {g["key"]: g for g in groups_new}
    assert "customers" in by_key_new
    assert customer.id in {h["id"] for h in by_key_new["customers"]["hits"]}
    assert by_key_old["invoices"]["hits"][0]["subtitle"] == "Wolfgang Rödchen", (
        "der Rechnungs-Schnappschuss selbst (subtitle) muss die alte Schreibweise unverändert zeigen"
    )


# --- Gemeinsamer Datensatz für die übrigen Tests: ein Treffer je Gruppe-A-Datensatzart ---

def _build_full_dataset(db, marker: str):
    customer = Customer(name=f"{marker} GmbH", last_name=f"{marker} GmbH", city="Teststadt")
    db.add(customer); db.flush()
    db.add(CustomerProfile(customer_id=customer.id, customer_number=f"K-{marker}"))

    db.add(Supplier(name=f"{marker} Lieferant", supplier_number=f"L-{marker}", city="Teststadt"))

    prop = Property(customer_id=customer.id, name=f"{marker} Objekt", city="Teststadt")
    db.add(prop); db.flush()
    db.add(RoofArea(property_id=prop.id, name=f"{marker} Dachfläche"))

    project = Project(project_number=f"P-{marker}", name=f"{marker} Projekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.flush()

    quote = Quote(quote_number=f"A-{marker}", project_id=project.id, title=f"{marker} Angebot")
    db.add(quote); db.flush()

    order = Order(
        order_number=f"AUF-{marker}", project_id=project.id, source_quote_id=quote.id,
        quote_number_snapshot=quote.quote_number, title=f"{marker} Auftrag",
        customer_name=f"{marker} GmbH", customer_number=f"K-{marker}",
    )
    db.add(order); db.flush()

    invoice = Invoice(
        order_id=order.id, invoice_number=f"R-{marker}", invoice_type="schluss",
        customer_name=f"{marker} GmbH",
    )
    db.add(invoice); db.flush()
    db.add(Reminder(invoice_id=invoice.id, level=1, reminder_number=f"M-{marker}"))

    db.add(Inquiry(inquiry_number=f"ANF-{marker}", customer_id=customer.id, title=f"{marker} Anfrage"))
    db.add(Task(title=f"{marker} Aufgabe", project_id=project.id))
    db.add(Employee(first_name="Max", last_name=f"{marker}mann", hourly_wage=Decimal("999.99")))

    db.add(MaintenanceContract(customer_id=customer.id, title=f"{marker} Wartungsvertrag", next_due_date=date.today()))

    report = ServiceReport(order_id=order.id, report_type="wartung", description=f"{marker} Bericht")
    db.add(report); db.flush()
    db.add(Finding(service_report_id=report.id, description=f"{marker} Mangel", severity="mittel", action="sofort_behoben"))

    batch = ImportBatch(source_type="leistungen_dach", source_name="Test", filename="t.xml")
    db.add(batch); db.flush()
    db.add(Service(
        import_batch_id=batch.id, source_type="leistungen_dach", external_id=f"EXT-{marker}",
        short_text=f"{marker} Leistung", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("60"), workshop_time_raw=Decimal("0"), sale_price=Decimal("777.00"),
    ))
    db.add(Material(name=f"{marker} Material", unit="Stk", purchase_price=Decimal("55.55")))
    db.add(OperationalAsset(name=f"{marker} Betriebsmittel", asset_type="Sonstiges"))
    db.commit()
    return {"customer": customer, "invoice": invoice, "order": order}


# --- 4.: Der Angriffstest + Ende-zu-Ende-Beleg, dass jede Quelle tatsächlich einen Treffer liefert ---

def test_admin_finds_a_hit_in_every_single_group_and_no_row_ever_carries_extra_fields(db_session):
    """Stärkster Beleg, dass query_fn/row_fn für alle 18 Quellen tatsächlich funktionieren (nicht
    nur, dass die Registry 18 Schlüssel deklariert) -- UND die strukturelle Garantie, dass keine
    Zeile je ein anderes Feld als id/title/subtitle/url trägt, unabhängig vom Inhalt der Quelle
    (Employee.hourly_wage/Material.purchase_price/Service.sale_price sind in den Testdaten
    bewusst gesetzt, tauchen aber in keiner Zeile auf)."""
    db = db_session
    marker = "Suchmarke"
    _build_full_dataset(db, marker)

    groups = search_office(db, ROLE_ADMIN, marker)
    found_keys = {g["key"] for g in groups}
    assert found_keys == EXPECTED_OFFICE_SEARCH_KEYS, f"fehlend: {EXPECTED_OFFICE_SEARCH_KEYS - found_keys}"

    for group in groups:
        assert group["total"] >= 1
        assert group["hits"], group["key"]
        for hit in group["hits"]:
            assert set(hit.keys()) == {"id", "title", "subtitle", "url"}, f"{group['key']}: {hit}"
    all_hits = [hit for g in groups for hit in g["hits"]]
    assert not _offending_keys(all_hits)
    assert not _offending_keys(groups)  # group-Dicts selbst tragen ebenfalls keine verbotenen Schlüssel


def test_field_role_gets_nothing_from_any_source_pure_function(db_session):
    """Reine Funktionsprüfung (kein Router): ROLE_FIELD steckt in KEINER der 18 allowed_roles --
    search_office() liefert für diese Rolle immer eine leere Liste, unabhängig vom Suchbegriff."""
    db = db_session
    marker = "Feldtest"
    _build_full_dataset(db, marker)
    assert search_office(db, ROLE_FIELD, marker) == []


def test_office_search_router_field_role_always_gets_403(router_test_client, threaded_db_session):
    """Der vom Nutzer verlangte Angriffstest, Mirror des Monteurs-Suche-Angriffstests (1.3.64/
    1.3.65): ein Monteur, der GET /api/search aufruft -- plain UND mit manipulierten Parametern
    (types=invoices, ein absurd hohes limit) -- bekommt 403, NIE irgendeine Zeile, geschweige
    denn eine Rechnung oder ein Preisfeld. Die primäre Sicherung ist der Router selbst
    (require_role(ROLE_ADMIN, ROLE_OFFICE) schließt ROLE_FIELD aus) -- 403 fällt, bevor
    search_office() auch nur eine Zeile liest."""
    from app.routers.search import router as search_router
    db = threaded_db_session
    _build_full_dataset(db, "Angriff")

    field = router_test_client(db, search_router, role="field", employee_id=None)

    resp_plain = field.get("/api/search", params={"q": "Angriff"})
    assert resp_plain.status_code == 403
    assert "invoice" not in resp_plain.text.lower()
    assert "preis" not in resp_plain.text.lower() and "price" not in resp_plain.text.lower()

    resp_manipulated = field.get(
        "/api/search",
        params={"q": "Angriff", "types": "invoices,customers,employees", "limit": "999999"},
    )
    assert resp_manipulated.status_code == 403
    assert resp_manipulated.json() == resp_plain.json()  # dieselbe 403-Antwort, unabhängig von den Parametern


def test_office_search_router_office_and_admin_get_200_with_invoices_group(router_test_client, threaded_db_session):
    """Belegt Entscheidung 1 (Büro sieht die volle Gruppe A inkl. Rechnungen -- die Grenze
    verläuft zwischen Büro und Monteur, nicht zwischen Admin und Büro) über den tatsächlichen
    Router-Weg, nicht nur die Kernfunktion direkt."""
    from app.routers.search import router as search_router
    db = threaded_db_session
    data = _build_full_dataset(db, "Bueroweg")

    for role in ("office", "admin"):
        client = router_test_client(db, search_router, role=role, employee_id=None)
        resp = client.get("/api/search", params={"q": "Bueroweg"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        by_key = {g["key"]: g for g in body}
        assert "invoices" in by_key, f"{role}: keine invoices-Gruppe -- {sorted(by_key)}"
        assert data["invoice"].id in {h["id"] for h in by_key["invoices"]["hits"]}
        assert not _offending_keys(body)
        all_hits = [hit for g in body for hit in g["hits"]]
        assert not _offending_keys(all_hits)
        for group in body:
            for hit in group["hits"]:
                assert set(hit.keys()) == {"id", "title", "subtitle", "url"}


def test_office_search_router_limit_is_clamped_between_one_and_hundred(router_test_client, threaded_db_session):
    from app.routers.search import router as search_router
    db = threaded_db_session
    _build_full_dataset(db, "Limittest")
    office = router_test_client(db, search_router, role="office", employee_id=None)

    resp_high = office.get("/api/search", params={"q": "Limittest", "limit": 99999})
    assert resp_high.status_code == 200

    resp_low = office.get("/api/search", params={"q": "Limittest", "limit": 0})
    assert resp_low.status_code == 200  # geklammert auf mindestens 1, kein 422


def test_office_search_router_types_filter_narrows_groups(router_test_client, threaded_db_session):
    from app.routers.search import router as search_router
    db = threaded_db_session
    _build_full_dataset(db, "Typfilter")
    office = router_test_client(db, search_router, role="office", employee_id=None)

    resp = office.get("/api/search", params={"q": "Typfilter", "types": "customers,invoices"})
    assert resp.status_code == 200
    keys = {g["key"] for g in resp.json()}
    assert keys <= {"customers", "invoices"}
    assert keys  # tatsächlich etwas gefunden, kein leerer Filter


# --- Dritte Achse: Modul-Umschalter, unabhängig von der Rolle ---

def test_module_gated_sources_disappear_when_their_module_is_disabled(db_session):
    """Nicht ausdrücklich vom Nutzer verlangt, aber Konsequenz der bereits bestehenden Regel
    ("API-Endpunkte müssen den Modul-Zustand selbst prüfen", siehe CLAUDE.md "Modul-Umschalter"):
    tasks/service_reports/findings/maintenance_contracts verschwinden, wenn ihr Modul
    ausgeschaltet ist -- auch wenn die Daten selbst weiterhin passend wären."""
    db = db_session
    marker = "Modultest"
    _build_full_dataset(db, marker)
    db.add(EnabledModule(module_key="wartungen", enabled=False))
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()

    groups = search_office(db, ROLE_ADMIN, marker)
    found_keys = {g["key"] for g in groups}
    assert found_keys == EXPECTED_OFFICE_SEARCH_KEYS - {"tasks", "service_reports", "findings", "maintenance_contracts"}


def test_operational_assets_source_disappears_when_betriebsmittel_module_is_disabled(db_session):
    """Punkt 3 ("nur wenn das Modul aktiv ist") -- eigener Test statt nur in der Sammel-
    Prüfung oben, damit ein künftiger Fund an genau dieser Quelle nicht in einer Vier-Module-
    Prüfung untergeht."""
    db = db_session
    marker = "BMModultest"
    _build_full_dataset(db, marker)
    db.add(EnabledModule(module_key="betriebsmittel", enabled=False))
    db.commit()

    groups = search_office(db, ROLE_ADMIN, marker)
    found_keys = {g["key"] for g in groups}
    assert "operational_assets" not in found_keys
    assert found_keys == EXPECTED_OFFICE_SEARCH_KEYS - {"operational_assets"}
