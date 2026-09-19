"""Version 1.4.1 -- Betriebsmittelverwaltung, Stufe 2 (siehe CLAUDE.md
"Betriebsmittelverwaltung" -> Stufe 2): Artikelnummer/Produktlink (Beschaffung, Büro/Admin-only),
Bedienungshinweise (das einzige Freitextfeld, das ein Monteur sieht), der QR-Code-Etikett-Weg
(app/qr_codes.py, GET /api/operational-assets/{id}/qr-code.png) und die rollenabhängige
Betriebsmittelseite (operational_asset.html für Büro/Admin, operational_asset_field.html für
`field`, beide unter derselben URL /betriebsmittel/{id} -- die Weiche hängt an der Rolle, nicht
am Weg, exakt wie bei time_tracking_page()).

Deckt ab: die http(s)-Validierung von product_url/public_base_url (Pydantic-Feldvalidator),
die reduzierte Ansicht (asset_field_dict()/OperationalAssetFieldOut) inkl. rekursivem
Schlüssel-Scan (Fehlerklasse "purchase_price", siehe CLAUDE.md Rechtekonzept), das QR-Code-
Rollen-/Modul-Gate, und die Seiten-Template-Auswahl je Rolle."""

import io

import pytest
from PIL import Image
from pydantic import ValidationError

from app.database import Base
from app.models import EnabledModule, OperationalAsset
from app.operational_assets import asset_field_dict, asset_qr_target_url, create_asset, update_asset
from app.schemas import GeneralSettingsUpdate, OperationalAssetCreate
from app.settings import get_or_create_general_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# --- http(s)-Validierung (Punkt 1: "nur http- und https-Adressen zulassen") ---

def test_product_url_validator_rejects_non_http_schemes():
    with pytest.raises(ValidationError, match="http"):
        OperationalAssetCreate(name="Kran", product_url="javascript:alert(1)")
    with pytest.raises(ValidationError, match="http"):
        OperationalAssetCreate(name="Kran", product_url="not-a-url")
    with pytest.raises(ValidationError, match="http"):
        OperationalAssetCreate(name="Kran", product_url="ftp://example.test/kran")


def test_product_url_validator_accepts_https_and_normalizes_blank_to_none():
    ok = OperationalAssetCreate(name="Kran", product_url="https://shop.example.test/kran")
    assert ok.product_url == "https://shop.example.test/kran"
    assert OperationalAssetCreate(name="Kran", product_url="   ").product_url is None
    assert OperationalAssetCreate(name="Kran", product_url=None).product_url is None


def test_public_base_url_validator_rejects_javascript_scheme_and_accepts_https():
    with pytest.raises(ValidationError, match="http"):
        GeneralSettingsUpdate(company_name="Test", public_base_url="javascript:alert(1)")
    ok = GeneralSettingsUpdate(company_name="Test", public_base_url="https://app.example.test")
    assert ok.public_base_url == "https://app.example.test"


# --- Business-Logik: Persistenz der drei neuen Felder ---

def test_create_and_update_asset_persist_procurement_and_usage_fields():
    db = db_session()
    created = create_asset(db, {
        "name": "Kran", "article_number": "ART-1", "product_url": "https://shop.example.test/kran",
        "usage_notes": "Vor Gebrauch Standfestigkeit prüfen.",
    })
    assert created["article_number"] == "ART-1"
    assert created["product_url"] == "https://shop.example.test/kran"
    assert created["usage_notes"] == "Vor Gebrauch Standfestigkeit prüfen."

    updated = update_asset(db, created["id"], {
        "name": "Kran", "article_number": "ART-2", "product_url": None, "usage_notes": None,
    })
    assert updated["article_number"] == "ART-2"
    assert updated["product_url"] is None
    assert updated["usage_notes"] is None


# --- Reduzierte Ansicht (Punkt 3: "Ein Monteur sieht die reduzierte Ansicht") ---

def _make_full_asset(db) -> dict:
    """Seit "Betriebsmittel-Kosten fest als Kostenposten" erzeugt eine laufende Rate nur noch
    über sync_asset_recurring_cost() einen verknüpften RecurringCost, nicht mehr über
    create_asset() selbst -- siehe tests/test_v289_asset_recurring_cost_link.py."""
    from app.models import OperationalAsset
    from app.operational_assets import sync_asset_recurring_cost
    from decimal import Decimal

    created = create_asset(db, {
        "name": "Kran", "asset_type": "Kran", "manufacturer": "Böcker", "model": "AHK36",
        "identifier": "X-123", "asset_number": "BM-001", "notes": "interne Beschaffungsnotiz",
        "usage_notes": "Vor Gebrauch Standfestigkeit prüfen.", "article_number": "ART-1",
        "product_url": "https://shop.example.test/kran",
        "acquisition_cost": "5000.00",
    })
    sync_asset_recurring_cost(db, db.get(OperationalAsset, created["id"]), Decimal("50.00"))
    return created


def test_asset_field_dict_contains_only_the_five_allowed_keys():
    db = db_session()
    created = _make_full_asset(db)
    row = db.get(OperationalAsset, created["id"])
    reduced = asset_field_dict(row)
    assert set(reduced) == {"id", "name", "asset_type", "manufacturer", "model", "usage_notes"}
    assert reduced["name"] == "Kran"
    assert reduced["usage_notes"] == "Vor Gebrauch Standfestigkeit prüfen."


_FORBIDDEN_KEYS = {
    "cost", "cost_notes", "acquisition_date", "acquisition_cost", "recurring_cost_per_month",
    "recurring_cost_id", "article_number", "product_url", "resource_id", "resource_number",
    "identifier", "asset_number", "notes", "inspections", "is_due", "is_overdue", "next_due_date",
}


def test_field_role_gets_reduced_schema_via_router_never_full_asset_data(threaded_db_session, router_test_client):
    """Rekursiver Schlüssel-Scan, Fehlerklasse "purchase_price" (siehe CLAUDE.md
    Rechtekonzept): ein Feld, das in der Antwort steht, aber nicht in der Oberfläche, ist
    trotzdem sichtbar -- deshalb wird die tatsächliche HTTP-Antwort geprüft, nicht nur die
    reine Business-Funktion."""
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="buero_auftrag")
    created = office.post("/api/operational-assets", json={
        "name": "Kran", "asset_type": "Kran", "manufacturer": "Böcker", "model": "AHK36",
        "identifier": "X-123", "asset_number": "BM-001", "notes": "interne Beschaffungsnotiz",
        "usage_notes": "Vor Gebrauch Standfestigkeit prüfen.", "article_number": "ART-1",
        "product_url": "https://shop.example.test/kran",
        "acquisition_cost": "5000.00",
    }).json()
    finanzen = router_test_client(db, assets_router, role="buero_finanzen")
    finanzen.put(f"/api/operational-assets/{created['id']}/recurring-cost", json={"net_amount": "50.00"})

    field = router_test_client(db, assets_router, role="field")
    r = field.get(f"/api/operational-assets/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "name", "asset_type", "manufacturer", "model", "usage_notes"}
    assert body["usage_notes"] == "Vor Gebrauch Standfestigkeit prüfen."
    assert not (set(body) & _FORBIDDEN_KEYS)


def test_office_role_still_gets_the_full_schema_via_router(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="buero_auftrag")
    created = office.post("/api/operational-assets", json={
        "name": "Kran", "article_number": "ART-1", "product_url": "https://shop.example.test/kran",
        "usage_notes": "Vor Gebrauch Standfestigkeit prüfen.",
    }).json()
    r = office.get(f"/api/operational-assets/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["article_number"] == "ART-1"
    assert body["product_url"] == "https://shop.example.test/kran"
    assert body["usage_notes"] == "Vor Gebrauch Standfestigkeit prüfen."
    assert "inspections" in body  # volle Ansicht bleibt unverändert vollständig


def test_module_disabled_returns_403_for_field_on_single_asset_endpoint(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="buero_auftrag")
    created = office.post("/api/operational-assets", json={"name": "Kran"}).json()
    db.add(EnabledModule(module_key="betriebsmittel", enabled=False))
    db.commit()
    field = router_test_client(db, assets_router, role="field")
    r = field.get(f"/api/operational-assets/{created['id']}")
    assert r.status_code == 403


# --- QR-Code (Punkt 2) ---

def test_asset_qr_target_url_builds_the_full_path_with_or_without_trailing_slash():
    assert asset_qr_target_url("https://app.example.test", 42) == "https://app.example.test/betriebsmittel/42"
    assert asset_qr_target_url("https://app.example.test/", 42) == "https://app.example.test/betriebsmittel/42"


def test_qr_code_endpoint_returns_a_valid_png_for_office_role(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="buero_auftrag")
    created = office.post("/api/operational-assets", json={"name": "Kran"}).json()
    r = office.get(f"/api/operational-assets/{created['id']}/qr-code.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(r.content))
    assert img.format == "PNG"


def test_qr_code_endpoint_is_403_for_field_role_printing_is_a_buero_vorgang(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="buero_auftrag")
    created = office.post("/api/operational-assets", json={"name": "Kran"}).json()
    field = router_test_client(db, assets_router, role="field")
    assert field.get(f"/api/operational-assets/{created['id']}/qr-code.png").status_code == 403


def test_qr_code_content_changes_when_public_base_url_is_configured(threaded_db_session, router_test_client):
    """Beweist indirekt, dass GeneralSettings.public_base_url tatsächlich gelesen wird -- ohne
    QR-Decoder verglichen: zwei unterschiedlich kodierte Ziel-URLs ergeben nie identische
    PNG-Bytes."""
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="buero_auftrag")
    created = office.post("/api/operational-assets", json={"name": "Kran"}).json()

    without_override = office.get(f"/api/operational-assets/{created['id']}/qr-code.png").content

    settings = get_or_create_general_settings(db)
    settings.public_base_url = "https://app.example.test"
    db.commit()

    with_override = office.get(f"/api/operational-assets/{created['id']}/qr-code.png").content
    assert without_override != with_override


# --- Rollenabhängige Seite (Punkt 3: "Die Rolle entscheidet, nicht der Weg") ---

def test_operational_asset_page_renders_reduced_template_for_field(threaded_db_session, router_test_client):
    from app.routers.pages import router as pages_router

    db = threaded_db_session
    field = router_test_client(db, pages_router, role="field")
    r = field.get("/betriebsmittel/1")
    assert r.status_code == 200
    assert "Etikett drucken" not in r.text
    assert "deleteAssetNow" not in r.text


def test_operational_asset_page_renders_full_template_for_office(threaded_db_session, router_test_client):
    from app.routers.pages import router as pages_router

    db = threaded_db_session
    office = router_test_client(db, pages_router, role="buero_auftrag")
    r = office.get("/betriebsmittel/1")
    assert r.status_code == 200
    assert "Etikett drucken" in r.text
