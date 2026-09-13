"""Version 1.3.6 -- Zusammenführung der Layout-Einstellungen: ein gemeinsamer Dokumenttyp
("default") für Briefpapier/Ränder/Bausteine statt je einer eigenen Zeile pro Dokumenttyp.

Deckt ab: den zentralen Rückfall-Helfer (app/document_type_fallback.py), dass er wirklich nur
EINMAL implementiert und von document_layout.py/document_page_margins.py importiert wird (nicht
parallel nachgebaut), die Schutzprüfung an den schreibenden Endpunkten, die Vorschau-Route, und
die Migration selbst (reminder-Zeilen werden zu "default", quote bleibt unberührt)."""

import importlib.util
from decimal import Decimal
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.document_layout import ensure_default_layout, get_background, get_effective_background, set_background
from app.document_page_margins import ensure_default_margins, get_margins
from app.document_type_fallback import SHARED_DOCUMENT_TYPE, resolve_shared_document_type
from app.models import DocumentLayoutBackground, DocumentLayoutBlock, DocumentPageMargins


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# resolve_shared_document_type() -- der zentrale Helfer, einmal implementiert
# ---------------------------------------------------------------------------

def test_resolve_shared_document_type_redirects_when_no_own_row_exists():
    """Seit 1.3.20 (Aufräumen nach dem PDF-Umbau, CLAUDE.md "Gemeinsamer Dokumenttyp"): "quote"
    ist KEIN Sonderfall mehr -- der alte, positionsbasierte Angebots-Renderer, der eigene Zeilen
    brauchte, ist entfernt. "quote" redirected jetzt genau wie jeder andere Dokumenttyp ohne
    eigene Zeile (vorher gab es hier einen eigenen Test, der das Gegenteil belegte)."""
    db = db_session()
    assert resolve_shared_document_type(db, DocumentLayoutBlock, "reminder") == SHARED_DOCUMENT_TYPE
    assert resolve_shared_document_type(db, DocumentLayoutBlock, "order") == SHARED_DOCUMENT_TYPE
    assert resolve_shared_document_type(db, DocumentLayoutBlock, "invoice") == SHARED_DOCUMENT_TYPE
    assert resolve_shared_document_type(db, DocumentLayoutBlock, "quote") == SHARED_DOCUMENT_TYPE


def test_resolve_shared_document_type_prefers_own_row_when_it_exists():
    """Der Escape-Hatch aus Option (a): existiert für einen echten Dokumenttyp bereits eine
    eigene Zeile, bleibt sie maßgeblich -- kein Rückfall trotz vorhandenem geteiltem Satz."""
    db = db_session()
    db.add(DocumentLayoutBlock(
        document_type="reminder", block_type="logo", label="Eigenes Logo",
        x_mm=Decimal(0), y_mm=Decimal(0), width_mm=Decimal(10), height_mm=Decimal(10),
        font_size=Decimal("9.5"), font_weight="normal", text_align="left", visible=True, sort_order=10,
    ))
    db.commit()
    assert resolve_shared_document_type(db, DocumentLayoutBlock, "reminder") == "reminder"
    # "invoice" hat weiterhin keine eigene Zeile -- fällt unabhängig davon zurück.
    assert resolve_shared_document_type(db, DocumentLayoutBlock, "invoice") == SHARED_DOCUMENT_TYPE


def test_resolve_shared_document_type_respects_extra_filters_per_page_type():
    """Margins/Backgrounds sind je page_type eigene Zeilen -- der Escape-Hatch muss pro
    (document_type, page_type)-Paar greifen, nicht pauschal je document_type."""
    db = db_session()
    db.add(DocumentPageMargins(
        document_type="reminder", page_type="first",
        top_mm=Decimal("30"), bottom_mm=Decimal("20"), left_mm=Decimal("18"), right_mm=Decimal("16"),
    ))
    db.commit()
    assert resolve_shared_document_type(
        db, DocumentPageMargins, "reminder", DocumentPageMargins.page_type == "first"
    ) == "reminder"
    assert resolve_shared_document_type(
        db, DocumentPageMargins, "reminder", DocumentPageMargins.page_type == "continuation"
    ) == SHARED_DOCUMENT_TYPE


def test_document_layout_and_page_margins_import_the_same_helper_not_a_copy():
    """Statisch geprüft (per Quelltext), dass beide Module den zentralen Helfer importieren,
    statt die "eigener Typ zuerst, sonst geteilt"-Regel je selbst nachzubauen -- genau die Falle,
    in die build_customer_and_meta_block() mit seinen drei Varianten getappt ist."""
    root = Path(__file__).parents[1] / "app"
    layout_src = (root / "document_layout.py").read_text(encoding="utf-8")
    margins_src = (root / "document_page_margins.py").read_text(encoding="utf-8")
    assert "from .document_type_fallback import" in layout_src
    assert "resolve_shared_document_type" in layout_src
    assert "from .document_type_fallback import" in margins_src
    assert "resolve_shared_document_type" in margins_src


# ---------------------------------------------------------------------------
# Lesen mit Rückfall vs. Schreiben literal (ensure_default_layout/get_margins/get_background)
# ---------------------------------------------------------------------------

def test_ensure_default_layout_reminder_and_order_share_the_same_seeded_rows():
    db = db_session()
    reminder_blocks = ensure_default_layout(db, "reminder")
    order_blocks = ensure_default_layout(db, "order")
    assert {b.id for b in reminder_blocks} == {b.id for b in order_blocks}  # identische Zeilen
    assert all(b.document_type == "default" for b in reminder_blocks)


def test_ensure_default_margins_reminder_uses_shared_top_default():
    """DOCUMENT_TYPE_MARGIN_OVERRIDES ist seit 1.3.6 auf SHARED_DOCUMENT_TYPE umgeschlüsselt --
    eine frische Installation, die "reminder" zuerst anfragt, muss trotzdem den geteilten,
    gegen das echte Briefpapier vermessenen Wert (seit 1.3.19: 25mm, vorher 1.3.2: 42mm) statt
    des generischen 17mm-Werts bekommen, weil sie auf den geteilten Satz zurückfällt."""
    db = db_session()
    margins = ensure_default_margins(db, "reminder", "first")
    assert margins.document_type == "default"
    assert margins.top_mm == Decimal("25.0")


def test_ensure_default_margins_shared_bottom_matches_the_real_letterhead():
    """Seit 1.3.18 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Randkorrektur "default"): der generische
    20mm-Standardwert unterschritt den real bedruckten Fußbereich desselben Briefpapiers, das
    "quote" bereits 1.3.16 auf 32mm korrigiert hat -- eine frische Installation muss für den
    geteilten Satz denselben, gegen das Briefpapier vermessenen Wert bekommen, nicht den
    generischen. Gilt für BEIDE Seitentypen (Logo/Firmenkopf/Fußzeile erscheinen auf jeder
    Seite)."""
    db = db_session()
    for page_type in ("first", "continuation"):
        margins = ensure_default_margins(db, "reminder", page_type)
        assert margins.document_type == "default"
        assert margins.bottom_mm == Decimal("32.0"), page_type


def test_get_background_is_literal_get_effective_background_falls_back():
    db = db_session()
    set_background(db, "default", "geteiltes-briefpapier.jpg", page_type="first")
    assert get_background(db, "reminder", "first") is None  # literal: "reminder" hat keine eigene Zeile
    effective = get_effective_background(db, "reminder", "first")
    assert effective is not None
    assert effective.stored_filename == "geteiltes-briefpapier.jpg"


def test_update_margins_never_silently_touches_the_shared_row():
    """Der vom Nutzer beschriebene Gefahrenfall, jetzt als Regressionstest: ein (hypothetischer,
    an den Endpunkten inzwischen blockierter) Schreibzugriff mit einem echten Dokumenttyp wie
    "invoice" muss eine EIGENE Zeile für "invoice" anlegen/ändern -- niemals die geteilte Zeile,
    die "reminder"/"order" weiterhin über den Rückfall sehen."""
    from app.document_page_margins import update_margins

    db = db_session()
    shared_before = ensure_default_margins(db, "reminder", "first")
    assert shared_before.top_mm == Decimal("25.0")

    update_margins(db, "invoice", "first", top_mm=Decimal("99"), bottom_mm=Decimal("20"), left_mm=Decimal("18"), right_mm=Decimal("16"))

    shared_after = ensure_default_margins(db, "reminder", "first")
    assert shared_after.top_mm == Decimal("25.0")  # unveraendert, NICHT auf 99 geändert
    invoice_row = db.scalar(select(DocumentPageMargins).where(DocumentPageMargins.document_type == "invoice", DocumentPageMargins.page_type == "first"))
    assert invoice_row is not None
    assert invoice_row.top_mm == Decimal("99")


# ---------------------------------------------------------------------------
# Router: Schutzprüfung + Vorschau-Route (siehe auch test_v226_document_frame.py für weitere
# Fälle der Schutzprüfung selbst)
# ---------------------------------------------------------------------------

def test_writable_document_types_endpoint_accepts_only_default(threaded_db_session, router_test_client):
    """Seit 1.3.20 (Aufräumen nach dem PDF-Umbau): "quote" ist nicht mehr eigenständig
    beschreibbar (siehe CLAUDE.md "Gemeinsamer Dokumenttyp") -- nur noch "default"."""
    from app.routers.document_layout import router as document_layout_router

    db = threaded_db_session
    client = router_test_client(db, document_layout_router)
    resp = client.put(
        "/api/document-layout/default/margins/first",
        json={"top_mm": 30, "bottom_mm": 20, "left_mm": 18, "right_mm": 16},
    )
    assert resp.status_code == 200, resp.text
    resp_quote = client.put(
        "/api/document-layout/quote/margins/first",
        json={"top_mm": 30, "bottom_mm": 20, "left_mm": 18, "right_mm": 16},
    )
    assert resp_quote.status_code == 422, resp_quote.text


def test_rollout_status_lists_reminder_as_using_shared_settings(threaded_db_session, router_test_client):
    """Name historisch (seit 1.3.6) -- prüft inzwischen alle fünf bereits umgestellten Renderer
    (Mahnung, Rechnung seit 1.3.7, Auftrag seit 1.3.10, Einsatzbericht seit 1.3.11, Angebot seit
    1.3.13 -- dort zunächst nur der NEUE, parallele Renderer app/quote_framed_pdf.py, der
    produktive Vorschau-/Versand-Pfad läuft bis zur Umstellung weiterhin über den alten
    quote_layout_pdf.py), nicht mehr nur die Mahnung."""
    from app.routers.document_layout import router as document_layout_router

    db = threaded_db_session
    client = router_test_client(db, document_layout_router)
    resp = client.get("/api/document-layout/rollout-status")
    assert resp.status_code == 200
    body = resp.json()
    using = {row["document_type"] for row in body["using_shared_settings"]}
    pending = {row["document_type"] for row in body["not_yet_migrated"]}
    excluded = {row["document_type"] for row in body["excluded"]}
    assert using == {"reminder", "invoice", "order", "service_report", "quote"}
    assert pending == set()
    # "excluded" war bis 1.3.13 hartkodiert {"quote"} -- seit der neue, parallele
    # Angebots-Renderer "quote" selbst registriert, wäre das ein Widerspruch zu "using". Aktuell
    # ist kein Dokumenttyp mehr dauerhaft ausgeschlossen.
    assert excluded == set()


# ---------------------------------------------------------------------------
# render_framed_pdf() lehnt einen nicht registrierten Dokumenttyp ab (Addition 3)
# ---------------------------------------------------------------------------

def test_render_framed_pdf_rejects_document_type_not_in_registry():
    """'order' stand hier ursprünglich als Beispiel für einen noch nicht umgestellten Typ -- seit
    1.3.10 (CLAUDE.md "Gemeinsamer Dokumenttyp") ist der Auftrag selbst umgestellt und damit kein
    Beispiel mehr. 'quote' ersetzte es anschließend, ist aber seit 1.3.13 (neuer, paralleler
    Angebots-Renderer app/quote_framed_pdf.py) ebenfalls registriert -- inzwischen sind ALLE
    fünf echten Dokumenttypen in RENDERERS_USING_SHARED_FRAME, ein frei erfundener Wert prüft den
    Ablehnungspfad jetzt robuster (bleibt korrekt, unabhängig davon, welcher Renderer als
    nächstes umgestellt wird)."""
    from app.document_frame import render_framed_pdf
    from app.document_pdf import build_styles

    db = db_session()
    styles = build_styles()
    try:
        render_framed_pdf(db, document_type="nicht_registrierter_typ", title="Test", content_story=[])
        assert False, "hätte ValueError werfen müssen -- 'nicht_registrierter_typ' steht nicht in RENDERERS_USING_SHARED_FRAME"
    except ValueError as e:
        assert "nicht_registrierter_typ" in str(e)


# ---------------------------------------------------------------------------
# Migration 8567f75a5266: reminder -> default, quote bleibt unberührt
# ---------------------------------------------------------------------------

def _load_migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_shared_layout_settings_reminder_rows_*.py"))
    spec = importlib.util.spec_from_file_location("migration_1306_shared_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration_step(engine, fn):
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        with Operations.context(ops):
            fn()
        conn.commit()


def test_migration_upgrade_moves_reminder_rows_to_default_quote_untouched():
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(DocumentLayoutBlock(
        document_type="reminder", block_type="footer_text", label="Fußzeile",
        x_mm=Decimal(18), y_mm=Decimal(282), width_mm=Decimal(176), height_mm=Decimal(8),
        font_size=Decimal(8), font_weight="normal", text_align="left", visible=True, sort_order=10,
    ))
    db.add(DocumentPageMargins(document_type="reminder", page_type="first", top_mm=Decimal("42.0"), bottom_mm=Decimal("20"), left_mm=Decimal("18"), right_mm=Decimal("16")))
    db.add(DocumentLayoutBackground(document_type="reminder", page_type="first", stored_filename="echtes-briefpapier.jpg", repeat_on_every_page=True))
    db.add(DocumentLayoutBlock(
        document_type="quote", block_type="footer_text", label="Fußzeile",
        x_mm=Decimal(18), y_mm=Decimal(282), width_mm=Decimal(176), height_mm=Decimal(8),
        font_size=Decimal(8), font_weight="normal", text_align="left", visible=True, sort_order=10,
    ))
    db.add(DocumentPageMargins(document_type="quote", page_type="first", top_mm=Decimal("17.0"), bottom_mm=Decimal("20"), left_mm=Decimal("18"), right_mm=Decimal("16")))
    db.commit()
    db.close()

    _run_migration_step(engine, migration.upgrade)

    db = Session()
    block = db.scalar(select(DocumentLayoutBlock).where(DocumentLayoutBlock.block_type == "footer_text", DocumentLayoutBlock.label == "Fußzeile", DocumentLayoutBlock.x_mm == Decimal(18)))
    reminder_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "reminder")).all()
    default_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "default")).all()
    quote_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "quote")).all()
    assert len(reminder_blocks) == 0
    assert len(default_blocks) == 1
    assert len(quote_blocks) == 1  # unberührt

    margins = db.scalars(select(DocumentPageMargins)).all()
    margins_by_type = {m.document_type: m for m in margins}
    assert "reminder" not in margins_by_type
    assert margins_by_type["default"].top_mm == Decimal("42.0")  # erprobter Wert bleibt erhalten
    assert margins_by_type["quote"].top_mm == Decimal("17.0")  # unberührt

    backgrounds = db.scalars(select(DocumentLayoutBackground)).all()
    assert len(backgrounds) == 1
    assert backgrounds[0].document_type == "default"
    assert backgrounds[0].stored_filename == "echtes-briefpapier.jpg"  # die reale Datei-Referenz bleibt erhalten
    db.close()


def test_migration_downgrade_reverses_upgrade():
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(DocumentPageMargins(document_type="reminder", page_type="first", top_mm=Decimal("42.0"), bottom_mm=Decimal("20"), left_mm=Decimal("18"), right_mm=Decimal("16")))
    db.commit()
    db.close()

    _run_migration_step(engine, migration.upgrade)
    _run_migration_step(engine, migration.downgrade)

    db = Session()
    row = db.scalar(select(DocumentPageMargins))
    assert row.document_type == "reminder"
    db.close()
