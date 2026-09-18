"""Version "Dateiablage je Objekt", Schritt 2 (nach 1.3.62) -- mobile Objektansicht für
Monteure. Ab hier gilt eine ANDERE Zugriffsregel als der Rest des Rechtekonzepts: ein Monteur
erreicht JEDES Objekt über seine ID, nicht nur die eigenen -- die Sperre sitzt ausschließlich im
INHALT: harmlose Objektfelder (PropertyAccessOut), nur für Monteure freigegebene, nicht gesperrte
Dokumentkategorien (field_may_see_category(), beide Schlösser aus 1.3.62), das bereits etablierte
reduzierte Wartungshistorie-Schema. Siehe CLAUDE.md "Dateiablage je Objekt"."""

from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

from app.document_categories import ensure_default_categories
from app.models import Customer, DocumentCategory, Employee, Order, OrderItem, Project, Property, PropertyDocument, ProjectDocument
from app.project_pipeline_columns import default_pipeline_column_id
from tests.test_v153_mahnwesen import db_session  # noqa: F401 -- re-exportiert db_session als Fixture


@pytest.fixture(autouse=True)
def _patch_storage_roots(tmp_path):
    """Muster tests/test_v154_document_management.py -- Datei-Uploads dieser Tests landen in
    einem Wegwerfordner statt im echten data/-Verzeichnis."""
    import app.project_documents as project_documents_module
    import app.property_documents as property_documents_module
    property_documents_module.PROPERTY_ROOT = tmp_path / "property_files"
    project_documents_module.PROJECT_ROOT = tmp_path / "project_files"


def _tiny_jpeg_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (10, 10), color=(200, 50, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def _employee(db, number, first, last):
    emp = Employee(employee_number=number, first_name=first, last_name=last,
                    employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def _customer_and_property(db, name="Objekt Nord"):
    customer = Customer(name="Testkunde GmbH", last_name="Testkunde GmbH")
    db.add(customer); db.flush()
    prop = Property(
        customer_id=customer.id, name=name, street="Teststr. 1", postal_code="52222", city="Teststadt",
        notes="Büro-interner Vermerk, nicht für den Monteur", access_notes="Schlüssel beim Hausmeister",
        site_contact_name="Frau Muster", site_contact_phone="0123 456789",
    )
    db.add(prop); db.commit()
    return customer, prop


def _project(db, customer, prop, number="P-TEST-0001", archived=False):
    project = Project(project_number=number, name="Testprojekt", customer_id=customer.id, property_id=prop.id, archived=archived, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.commit()
    return project


def _order(db, project, customer, prop, number="AUF-0001"):
    order = Order(
        order_number=number, project_id=project.id, source_quote_id=int(number.rsplit("-", 1)[-1]),
        quote_number_snapshot=f"A-{number}", title="Testauftrag", customer_name=customer.name,
        customer_number="K-0001", property_name=prop.name,
    )
    db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                      quantity=Decimal("100"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    return order


def _category(db, key):
    return db.query(DocumentCategory).filter_by(key=key).one()


def _project_document(db, project, category_key, filename="plan.pdf"):
    category = _category(db, category_key)
    doc = ProjectDocument(
        project_id=project.id, category=category_key, category_id=category.id, original_filename=filename,
        stored_filename=f"stored-{project.id}-{category.id}-{filename}", content_type="application/pdf", file_size=10,
    )
    db.add(doc); db.commit()
    return doc


def _property_document(db, prop, category_key, filename="foto.jpg"):
    category = _category(db, category_key)
    doc = PropertyDocument(
        property_id=prop.id, category_id=category.id, original_filename=filename,
        stored_filename=f"stored-{prop.id}-{category.id}-{filename}", content_type="image/jpeg", file_size=10,
    )
    db.add(doc); db.commit()
    return doc


def _keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _keys(value)


_FORBIDDEN_SUBSTRINGS = (
    "price", "preis", "purchase", "einkauf", "wage", "lohn", "gehalt", "cost", "kosten",
    "betrag", "amount", "vergüt", "customer_note", "property_note", "notiz",
)


def _offending_keys(payload):
    return sorted({k for k in _keys(payload) if any(f in k.lower() for f in _FORBIDDEN_SUBSTRINGS)})


# --- Punkt 3: harmlose Objektfelder, unbeschränkter Zugriff auf JEDES Objekt ---

def test_field_can_open_any_property_but_only_harmless_fields(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    customer, prop = _customer_and_property(db)
    monteur = _employee(db, "T-D1", "Klaus", "Keiner")
    # Bewusst KEINE Zuordnung ueber die Arbeitsvorbereitung -- Punkt 3: "Ein Monteur erreicht
    # JEDES Objekt, nicht nur seine eigenen."
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    resp = field.get(f"/api/field-view/properties/{prop.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"id", "name", "street", "postal_code", "city", "access_notes", "site_contact_name", "site_contact_phone"}
    assert body["name"] == prop.name
    assert body["access_notes"] == "Schlüssel beim Hausmeister"
    assert "notes" not in body
    assert "customer_id" not in body
    assert "is_primary_address" not in body


def test_field_unknown_property_id_is_404(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    monteur = _employee(db, "T-D1b", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    assert field.get("/api/field-view/properties/999999").status_code == 404


# --- Punkt 1 + Kategorie-Sperren: zusammengeführte, gefilterte Dokumentliste ---

def test_field_document_list_excludes_sensitive_and_hard_locked_categories(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    project = _project(db, customer, prop)
    _project_document(db, project, "Pläne")
    _project_document(db, project, "Rechnungen / Belege")
    _property_document(db, prop, "Bilder / Fotos")
    _property_document(db, prop, "Sonstiges")

    monteur = _employee(db, "T-D2", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    resp = field.get(f"/api/field-view/properties/{prop.id}/documents")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert {i["category_key"] for i in items} == {"Pläne", "Bilder / Fotos"}
    assert len(items) == 2


def test_field_document_list_excludes_archived_project_documents(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    active_project = _project(db, customer, prop, number="P-A-0001", archived=False)
    archived_project = _project(db, customer, prop, number="P-A-0002", archived=True)
    _project_document(db, active_project, "Pläne", filename="aktiv.pdf")
    _project_document(db, archived_project, "Pläne", filename="archiviert.pdf")

    monteur = _employee(db, "T-D3", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    items = field.get(f"/api/field-view/properties/{prop.id}/documents").json()
    assert [i["original_filename"] for i in items] == ["aktiv.pdf"]


# --- Der kritischste Punkt: Datei-Abruf prüft field_may_see_category() erneut ---

def test_field_cannot_download_hard_locked_category_document_via_guessed_id(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    project = _project(db, customer, prop)
    locked_doc = _project_document(db, project, "Rechnungen / Belege")

    monteur = _employee(db, "T-D4", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    assert field.get(f"/api/field-view/properties/{prop.id}/documents/project/{locked_doc.id}/download").status_code == 404
    assert field.get(f"/api/field-view/properties/{prop.id}/documents/project/{locked_doc.id}/view").status_code == 404


def test_field_cannot_download_document_belonging_to_a_different_property(router_test_client, threaded_db_session):
    from app.project_documents import document_path as project_doc_path
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop_a = _customer_and_property(db, "Objekt A")
    _, prop_b = _customer_and_property(db, "Objekt B")
    project_a = _project(db, customer, prop_a)
    doc = _project_document(db, project_a, "Pläne")
    path = project_doc_path(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 test")

    monteur = _employee(db, "T-D5", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    ok = field.get(f"/api/field-view/properties/{prop_a.id}/documents/project/{doc.id}/download")
    assert ok.status_code == 200
    wrong = field.get(f"/api/field-view/properties/{prop_b.id}/documents/project/{doc.id}/download")
    assert wrong.status_code == 404


def test_field_cannot_download_document_of_archived_project_via_guessed_id(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    archived_project = _project(db, customer, prop, number="P-A-0003", archived=True)
    doc = _project_document(db, archived_project, "Pläne")

    monteur = _employee(db, "T-D5b", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    assert field.get(f"/api/field-view/properties/{prop.id}/documents/project/{doc.id}/download").status_code == 404


def test_download_blocked_even_if_category_row_is_tampered_to_look_visible(router_test_client, threaded_db_session):
    """Dasselbe Prinzip wie test_field_may_see_category_blocks_hard_locked_keys_even_with_tampered_flags
    (tests/test_v266_document_categories.py) -- hier am tatsächlichen Datei-Ausliefer-Endpunkt
    nachgewiesen, nicht nur an der reinen Funktion. HARD_LOCKED_CATEGORY_KEYS greift unabhängig
    von einer direkt in der Datenbank manipulierten is_field_visible/is_sensitive-Kombination."""
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    project = _project(db, customer, prop)
    locked = _category(db, "Rechnungen / Belege")
    locked.is_field_visible = True
    locked.is_sensitive = False
    db.commit()
    doc = _project_document(db, project, "Rechnungen / Belege")

    from app.routers.field_view import router as field_router
    monteur = _employee(db, "T-D13", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    assert field.get(f"/api/field-view/properties/{prop.id}/documents/project/{doc.id}/download").status_code == 404
    assert field.get(f"/api/field-view/properties/{prop.id}/documents").json() == []


# --- Eigene Uploads: serverseitige Kategorie-Sperre, nicht nur die UI-Vorauswahl ---

def test_field_upload_rejects_non_field_visible_category(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    sonstiges = _category(db, "Sonstiges")
    monteur = _employee(db, "T-D6", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    resp = field.post(
        f"/api/field-view/properties/{prop.id}/documents",
        files={"file": ("foto.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
        data={"category_id": str(sonstiges.id)},
    )
    assert resp.status_code == 422, resp.text


def test_field_upload_rejects_hard_locked_category(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    locked = _category(db, "Rechnungen / Belege")
    monteur = _employee(db, "T-D7", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    resp = field.post(
        f"/api/field-view/properties/{prop.id}/documents",
        files={"file": ("rechnung.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"category_id": str(locked.id)},
    )
    assert resp.status_code == 422, resp.text


def test_field_upload_without_employee_link_is_rejected(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    plaene = _category(db, "Pläne")
    field = router_test_client(db, field_router, role="field", employee_id=None)
    resp = field.post(
        f"/api/field-view/properties/{prop.id}/documents",
        files={"file": ("plan.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"category_id": str(plaene.id)},
    )
    assert resp.status_code == 422, resp.text


def test_field_upload_succeeds_resizes_image_and_sets_uploader(router_test_client, threaded_db_session):
    from app.models import PropertyDocument as PD
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    fotos = _category(db, "Bilder / Fotos")
    monteur = _employee(db, "T-D8", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    resp = field.post(
        f"/api/field-view/properties/{prop.id}/documents",
        files={"file": ("foto.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
        data={"category_id": str(fotos.id)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "property"
    doc = db.get(PD, body["id"])
    assert doc.uploaded_by_employee_id == monteur.id
    assert doc.stored_filename.endswith(".jpg")


# --- Punkt 2: Büro sieht die Monteur-Uploads ---

def test_office_can_see_and_manage_property_documents_uploaded_by_field(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    from app.routers.property_documents import router as prop_doc_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    fotos = _category(db, "Bilder / Fotos")
    monteur = _employee(db, "T-D12", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    upload = field.post(
        f"/api/field-view/properties/{prop.id}/documents",
        files={"file": ("foto.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
        data={"category_id": str(fotos.id)},
    )
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]

    office = router_test_client(db, prop_doc_router, role="buero_auftrag")
    listing = office.get(f"/api/properties/{prop.id}/documents")
    assert listing.status_code == 200
    assert any(d["id"] == doc_id and d["source"] == "property" for d in listing.json())

    field_no_employee = router_test_client(db, prop_doc_router, role="field", employee_id=monteur.id)
    assert field_no_employee.get(f"/api/properties/{prop.id}/documents").status_code == 403


# --- Wartungsberichte: reduziertes Schema, objektbezogen ---

def test_field_maintenance_history_is_property_scoped_and_reduced(router_test_client, threaded_db_session):
    from app.findings import create_finding
    from app.materials import create_manual_material
    from app.models import ServiceReport
    from app.routers.field_view import router as field_router
    from app.service_reports import add_inspection_item, add_material, create_report, update_inspection_item
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    project = _project(db, customer, prop, number="P-D-0001")
    order = _order(db, project, customer, prop, number="AUF-D-0001")
    report_id = create_report(db, order.id, "wartung", description="Interner Beschreibungstext")["id"]
    material = create_manual_material(db, name="Dachziegel", unit="Stk", purchase_price=Decimal("12.50"))
    add_material(db, report_id, material_id=material.id, quantity=Decimal("2"))
    item = add_inspection_item(db, report_id, "Gully Nordost", "ja_nein", group_name="Entwässerung")
    update_inspection_item(db, item["id"], {"result": "nok", "notes": "Laub, gereinigt"})
    create_finding(db, report_id, "Gully verstopft", "mittel", "sofort_behoben", inspection_item_id=item["id"])
    db.get(ServiceReport, report_id).status = "unterschrieben"; db.commit()

    monteur = _employee(db, "T-D10", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)
    resp = field.get(f"/api/field-view/properties/{prop.id}/maintenance-history")
    assert resp.status_code == 200, resp.text
    history = resp.json()
    assert [r["id"] for r in history] == [report_id]
    entry = history[0]
    assert set(entry) == {
        "id", "order_number", "order_title", "report_type", "report_type_label", "performed_at",
        "created_by_employee_name", "roof_areas", "inspection_items", "findings",
    }
    assert "description" not in entry
    assert _offending_keys(history) == []


# --- Übergreifend: kein Endpunkt dieser Runde liefert Preis-/Kosten-/interne Felder ---

def test_no_field_view_property_endpoint_leaks_price_or_internal_fields(router_test_client, threaded_db_session):
    """Fehlerklasse purchase_price (siehe CLAUDE.md "Rechtekonzept", 1.3.53): ein Feld, das in
    der Antwort steht, aber in der Oberfläche fehlt, ist trotzdem sichtbar -- rekursiver
    Schlüssel-Scan über jeden neuen Endpunkt dieser Runde."""
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    ensure_default_categories(db)
    customer, prop = _customer_and_property(db)
    project = _project(db, customer, prop)
    _project_document(db, project, "Pläne")
    _property_document(db, prop, "Bilder / Fotos")
    monteur = _employee(db, "T-D11", "Klaus", "Keiner")
    field = router_test_client(db, field_router, role="field", employee_id=monteur.id)

    endpoints = [
        f"/api/field-view/properties/{prop.id}",
        f"/api/field-view/properties/{prop.id}/documents",
        "/api/field-view/document-categories",
        f"/api/field-view/properties/{prop.id}/maintenance-history",
    ]
    offending = []
    for url in endpoints:
        resp = field.get(url)
        assert resp.status_code == 200, (url, resp.text)
        offending += [(url, k) for k in _offending_keys(resp.json())]
    assert offending == [], offending
