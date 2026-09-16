"""Version 1.3.62 -- Dateiablage je Objekt, Runde 2, Schritt 1: Kategorie-Stammdaten
(DocumentCategory) mit den zwei unabhängigen Schlössern und die dazugehörige Migration
(9137945e8785). Siehe CLAUDE.md "Dateiablage je Objekt" für die volle Herleitung.

Baut NICHT auf der mobilen Objektansicht/der Suche auf -- die sind explizit spätere Runden."""

import importlib.util
from pathlib import Path

from app.document_categories import (
    FALLBACK_CATEGORY_KEY, HARD_LOCKED_CATEGORY_KEYS, create_category, ensure_default_categories,
    field_may_see_category, list_categories, resolve_category_id, set_category_active,
    update_category,
)
from app.models import CustomerDocument, DocumentCategory, ProjectDocument
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def _migration_module():
    path = next(Path(__file__).resolve().parents[1].glob(
        "alembic/versions/9137945e8785_document_categories_foundation.py"
    ))
    spec = importlib.util.spec_from_file_location("migration_1362_document_categories", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Selbst-Seeding ---

def test_ensure_default_categories_seeds_eight_categories_with_correct_flags():
    db = db_session()
    ensure_default_categories(db)
    categories = {c["key"]: c for c in list_categories(db, include_inactive=True)}
    assert len(categories) == 8
    assert categories["Pläne"]["is_field_visible"] is True
    assert categories["Pläne"]["is_sensitive"] is False
    assert categories["Rechnungen / Belege"]["is_sensitive"] is True
    assert categories["Rechnungen / Belege"]["is_field_visible"] is False
    assert categories["Verträge / Freigaben"]["is_sensitive"] is True
    assert categories["Sonstiges"]["is_sensitive"] is False
    assert categories["Sonstiges"]["is_field_visible"] is False


def test_ensure_default_categories_never_touches_an_already_seeded_row():
    db = db_session()
    ensure_default_categories(db)
    plaene = db.query(DocumentCategory).filter_by(key="Pläne").one()
    plaene.label = "Pläne (umbenannt)"
    db.commit()

    ensure_default_categories(db)  # zweiter Aufruf darf die Änderung nicht überschreiben
    db.refresh(plaene)
    assert plaene.label == "Pläne (umbenannt)"
    assert db.query(DocumentCategory).count() == 8  # keine doppelte Erstbefüllung


# --- Schloss 1: is_sensitive/is_field_visible-Validierung ---

def test_create_category_rejects_sensitive_and_field_visible_combination():
    db = db_session()
    try:
        create_category(db, "eigene_kategorie", "Eigene Kategorie", is_sensitive=True, is_field_visible=True)
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "sensib" in str(exc).lower()


def test_create_category_hard_locked_key_must_be_sensitive_and_never_field_visible():
    db = db_session()
    try:
        create_category(db, "Rechnungen / Belege", "Rechnungen / Belege", is_sensitive=False, is_field_visible=False)
        assert False, "sollte ValueError auslösen -- gesperrter Key muss sensibel sein"
    except ValueError as exc:
        assert "gesperrt" in str(exc).lower()

    try:
        create_category(db, "Verträge / Freigaben", "Verträge / Freigaben", is_sensitive=True, is_field_visible=True)
        assert False, "sollte ValueError auslösen (zusätzlich per Kombinationsregel verboten)"
    except ValueError:
        pass


def test_update_category_cannot_unset_sensitive_once_true():
    db = db_session()
    created = create_category(db, "eigene_sensible_kategorie", "Eigene sensible Kategorie", is_sensitive=True, is_field_visible=False)
    assert created["is_sensitive"] is True

    try:
        update_category(db, created["id"], label=created["label"], is_field_visible=False, is_sensitive=False)
        assert False, "sollte ValueError auslösen -- einmal sensibel bleibt sensibel"
    except ValueError as exc:
        assert "nicht-sensibel" in str(exc).lower() or "sensib" in str(exc).lower()

    # unverändert lassen (is_sensitive=None) bleibt möglich, auch für andere Felder.
    updated = update_category(db, created["id"], label="Umbenannt", is_field_visible=False)
    assert updated["label"] == "Umbenannt"
    assert updated["is_sensitive"] is True


def test_update_category_cannot_raise_field_visible_while_sensitive():
    db = db_session()
    created = create_category(db, "eigene_sensible_kategorie_2", "Eigene sensible Kategorie 2", is_sensitive=True, is_field_visible=False)
    try:
        update_category(db, created["id"], label=created["label"], is_field_visible=True)
        assert False, "sollte ValueError auslösen -- sensibel + für Monteure sichtbar bleibt unmöglich"
    except ValueError:
        pass


def test_update_category_on_hard_locked_key_cannot_become_field_visible():
    """Rechnungen / Belege ist bereits als is_sensitive=True gesät -- der Versuch,
    is_field_visible=True zu setzen, greift dieselbe allgemeine Kombinationsregel wie bei jeder
    anderen sensiblen Kategorie (sensibel + für Monteure sichtbar ist grundsätzlich verboten,
    nicht nur für gesperrte Keys). Der eigentliche, key-spezifische Sperrtext greift erst, wenn
    jemand versucht, is_sensitive für einen gesperrten Key auf False zu bringen -- das ist aber
    bereits durch die 'einmal sensibel, immer sensibel'-Regel unabhängig blockiert (siehe
    test_update_category_cannot_unset_sensitive_once_true). Entscheidend hier: die Kombination
    bleibt in jedem Fall abgelehnt, die Kategorie bleibt für Monteure unsichtbar."""
    db = db_session()
    ensure_default_categories(db)
    rechnungen = db.query(DocumentCategory).filter_by(key="Rechnungen / Belege").one()
    try:
        update_category(db, rechnungen.id, label=rechnungen.label, is_field_visible=True)
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    db.refresh(rechnungen)
    assert rechnungen.is_field_visible is False


# --- Schloss 2: field_may_see_category() ist unabhängig von Schloss 1 ---

def test_field_may_see_category_respects_is_field_visible_and_active():
    db = db_session()
    ensure_default_categories(db)
    plaene = db.query(DocumentCategory).filter_by(key="Pläne").one()
    assert field_may_see_category(plaene) is True

    schriftverkehr = db.query(DocumentCategory).filter_by(key="Schriftverkehr").one()
    assert field_may_see_category(schriftverkehr) is False  # is_field_visible=False

    set_category_active(db, plaene.id, False)
    db.refresh(plaene)
    assert field_may_see_category(plaene) is False  # deaktiviert bleibt gesperrt


def test_field_may_see_category_blocks_hard_locked_keys_even_with_tampered_flags():
    """Der eigentliche Nachweis der 'zwei unabhängigen Schlösser': ein DocumentCategory-Objekt
    wird HIER direkt konstruiert, unter komplettem Umgehen von create_category()/
    update_category() (simuliert eine direkte Datenbankmanipulation, z. B. rohes SQL oder ein
    Bug in einer künftigen Änderung) -- is_sensitive=False, is_field_visible=True, active=True
    für einen der beiden fest gesperrten Keys. field_may_see_category() muss trotzdem False
    liefern, weil HARD_LOCKED_CATEGORY_KEYS unabhängig von den beiden Flags geprüft wird."""
    for locked_key in HARD_LOCKED_CATEGORY_KEYS:
        tampered = DocumentCategory(
            key=locked_key, label=locked_key, is_sensitive=False, is_field_visible=True,
            sort_order=1, active=True,
        )
        assert field_may_see_category(tampered) is False, f"{locked_key} darf trotz manipulierter Flags nie sichtbar sein"


# --- Router-Rollenprüfung ---

def test_document_categories_router_rejects_field_role(threaded_db_session, router_test_client):
    from app.routers.document_categories import router as categories_router
    ensure_default_categories(threaded_db_session)

    admin_client = router_test_client(threaded_db_session, categories_router, role="admin")
    resp = admin_client.get("/api/document-categories")
    assert resp.status_code == 200
    assert len(resp.json()) == 8

    field_client = router_test_client(threaded_db_session, categories_router, role="field", employee_id=1)
    resp = field_client.get("/api/document-categories")
    assert resp.status_code == 403

    resp = field_client.post("/api/document-categories", json={"key": "x", "label": "X"})
    assert resp.status_code == 403


def test_document_categories_router_enforces_the_two_locks_end_to_end(threaded_db_session, router_test_client):
    from app.routers.document_categories import router as categories_router
    ensure_default_categories(threaded_db_session)
    client = router_test_client(threaded_db_session, categories_router, role="admin")

    resp = client.post("/api/document-categories", json={
        "key": "y", "label": "Y", "is_sensitive": True, "is_field_visible": True,
    })
    assert resp.status_code == 422

    rechnungen = threaded_db_session.query(DocumentCategory).filter_by(key="Rechnungen / Belege").one()
    resp = client.put(f"/api/document-categories/{rechnungen.id}", json={
        "label": "Rechnungen / Belege", "is_field_visible": True,
    })
    assert resp.status_code == 422


# --- resolve_category_id(): Freitext-Zuordnung ---

def test_resolve_category_id_matches_exact_known_string():
    db = db_session()
    plaene_id = resolve_category_id(db, "Pläne")
    sonstiges_id = resolve_category_id(db, "Sonstiges")
    assert plaene_id != sonstiges_id
    category = db.get(DocumentCategory, plaene_id)
    assert category.key == "Pläne"


def test_resolve_category_id_falls_back_to_sonstiges_for_unknown_or_empty_string():
    db = db_session()
    for unmatched in (None, "", "  ", "Ein völlig unbekannter Kategoriename"):
        category_id = resolve_category_id(db, unmatched)
        category = db.get(DocumentCategory, category_id)
        assert category.key == FALLBACK_CATEGORY_KEY


# --- Regression: die vier angepassten Upload-/Update-Endpunkte setzen category_id ---

def test_customer_document_upload_sets_category_id(threaded_db_session, router_test_client):
    from app.routers.customers import router as customers_router
    db = threaded_db_session
    customer, _prop = make_customer_and_property(db)
    client = router_test_client(db, customers_router, role="admin")

    resp = client.post(
        f"/api/customers/{customer.id}/documents",
        files={"file": ("plan.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"category": "Pläne"},
    )
    assert resp.status_code == 200
    doc_id = resp.json()["id"]
    doc = db.get(CustomerDocument, doc_id)
    assert doc.category == "Pläne"
    assert doc.category_id is not None
    assert db.get(DocumentCategory, doc.category_id).key == "Pläne"


def test_customer_document_update_recomputes_category_id(threaded_db_session, router_test_client):
    from app.routers.customer_documents import router as customer_documents_router
    from app.routers.customers import router as customers_router
    db = threaded_db_session
    customer, _prop = make_customer_and_property(db)
    upload_client = router_test_client(db, customers_router, role="admin")
    resp = upload_client.post(
        f"/api/customers/{customer.id}/documents",
        files={"file": ("plan.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"category": "Pläne"},
    )
    doc_id = resp.json()["id"]

    update_client = router_test_client(db, customer_documents_router, role="admin")
    resp = update_client.put(f"/api/customer-documents/{doc_id}", json={
        "category": "Rechnungen / Belege", "subfolder": None, "description": None, "document_date": None,
    })
    assert resp.status_code == 200
    doc = db.get(CustomerDocument, doc_id)
    assert doc.category_id is not None
    assert db.get(DocumentCategory, doc.category_id).key == "Rechnungen / Belege"


def _make_project(db, customer, prop, number="P-TEST-0001"):
    from app.models import Project
    from app.project_pipeline_columns import default_pipeline_column_id
    project = Project(project_number=number, name="Testprojekt", customer_id=customer.id, property_id=prop.id, status="anfrage", pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.commit()
    return project


def test_project_document_upload_sets_category_id(threaded_db_session, router_test_client):
    from app.routers.projects import router as projects_router
    db = threaded_db_session
    customer, prop = make_customer_and_property(db)
    project = _make_project(db, customer, prop)
    client = router_test_client(db, projects_router, role="admin")

    resp = client.post(
        f"/api/projects/{project.id}/documents",
        files={"file": ("foto.jpg", b"\xff\xd8\xff test", "image/jpeg")},
        data={"category": "Bilder / Fotos"},
    )
    assert resp.status_code == 200
    doc_id = resp.json()["id"]
    doc = db.get(ProjectDocument, doc_id)
    assert doc.category_id is not None
    assert db.get(DocumentCategory, doc.category_id).key == "Bilder / Fotos"


def test_project_document_update_recomputes_category_id(threaded_db_session, router_test_client):
    from app.routers.project_documents import router as project_documents_router
    from app.routers.projects import router as projects_router
    db = threaded_db_session
    customer, prop = make_customer_and_property(db)
    project = _make_project(db, customer, prop, number="P-TEST-0002")
    upload_client = router_test_client(db, projects_router, role="admin")
    resp = upload_client.post(
        f"/api/projects/{project.id}/documents",
        files={"file": ("foto.jpg", b"\xff\xd8\xff test", "image/jpeg")},
        data={"category": "Bilder / Fotos"},
    )
    doc_id = resp.json()["id"]

    update_client = router_test_client(db, project_documents_router, role="admin")
    resp = update_client.put(f"/api/project-documents/{doc_id}", json={
        "category": "Sonstiges", "subfolder": None, "description": None, "document_date": None,
    })
    assert resp.status_code == 200
    doc = db.get(ProjectDocument, doc_id)
    assert doc.category_id is not None
    assert db.get(DocumentCategory, doc.category_id).key == "Sonstiges"


# --- Migration 9137945e8785: Seed- und Backfill-Logik isoliert ---

def test_migration_resolve_category_id_matches_known_key():
    migration = _migration_module()
    category_ids_by_key = {"Pläne": 1, "Sonstiges": 8}
    assert migration._resolve_category_id("Pläne", category_ids_by_key) == 1


def test_migration_resolve_category_id_falls_back_to_sonstiges_for_unknown_or_empty():
    migration = _migration_module()
    category_ids_by_key = {"Pläne": 1, "Sonstiges": 8}
    assert migration._resolve_category_id("Unbekannt", category_ids_by_key) == 8
    assert migration._resolve_category_id(None, category_ids_by_key) == 8
    assert migration._resolve_category_id("", category_ids_by_key) == 8
    assert migration._resolve_category_id("  ", category_ids_by_key) == 8


def test_migration_seed_and_backfill_end_to_end_against_a_real_connection():
    """Baut die drei betroffenen Tabellen über eine eigene, leichte Verbindung nach (kein
    batch_alter_table -- reines Boilerplate, siehe CLAUDE.md 'Testen' zur Begründung, warum nur
    die Befüll-Logik getestet wird, nicht der Schema-Umbau selbst) und prüft Seed + Backfill
    inkl. eines nicht zuordenbaren Strings, der auf 'Sonstiges' fallen muss."""
    import sqlalchemy as sa

    migration = _migration_module()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as bind:
        bind.execute(sa.text(
            "CREATE TABLE document_categories (id INTEGER PRIMARY KEY, key VARCHAR(80), label VARCHAR(120), "
            "is_sensitive BOOLEAN, is_field_visible BOOLEAN, sort_order INTEGER, active BOOLEAN, "
            "created_at DATETIME, updated_at DATETIME)"
        ))
        bind.execute(sa.text(
            "CREATE TABLE customer_documents (id INTEGER PRIMARY KEY, category VARCHAR(120), category_id INTEGER)"
        ))
        bind.execute(sa.text("INSERT INTO customer_documents (id, category) VALUES (1, 'Pläne')"))
        bind.execute(sa.text("INSERT INTO customer_documents (id, category) VALUES (2, 'Ein unbekannter Freitext')"))

        migration._seed_default_categories(bind, __import__("datetime").datetime(2026, 9, 16))
        rows = bind.execute(sa.text("SELECT id, key FROM document_categories")).fetchall()
        assert len(rows) == 8

        table = sa.table('customer_documents', sa.column('id', sa.Integer), sa.column('category', sa.String), sa.column('category_id', sa.Integer))
        migration._backfill_table_category_ids(bind, table)

        result = bind.execute(sa.text("SELECT id, category, category_id FROM customer_documents ORDER BY id")).fetchall()
        category_ids_by_key = {row[1]: row[0] for row in bind.execute(sa.text("SELECT id, key FROM document_categories")).fetchall()}

        assert result[0][2] == category_ids_by_key["Pläne"]
        assert result[1][2] == category_ids_by_key["Sonstiges"]  # unbekannter Freitext faellt auf Sonstiges zurueck
