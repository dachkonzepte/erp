from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.company_logo import LOGO_ROOT, delete_logo, logo_path, replace_logo
from app.database import Base
from app.document_layout import (
    DEFAULT_SHARED_LAYOUT,
    ensure_default_layout,
    get_background,
    list_layout_blocks,
    remove_background,
    reset_layout_to_default,
    set_background,
    update_layout_block,
)
from app.models import DocumentLayoutBlock


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# ensure_default_layout / list_layout_blocks
# ---------------------------------------------------------------------------

def test_ensure_default_layout_seeds_shared_defaults_for_every_document_type():
    """Vorher (bis 1.3.19) mehrfach angepasst, aus demselben Grund: 'welche Dokumenttypen werden
    geseedet' ist offenbar keine stabile Eigenschaft, sondern ändert sich mit jeder
    Rollout-Entscheidung. Seit 1.3.20 (Aufräumen nach dem PDF-Umbau, CLAUDE.md "Gemeinsamer
    Dokumenttyp") ist 'quote' KEIN Sonderfall mehr -- der alte, positionsbasierte Renderer, der
    eigene Bausteine brauchte, ist entfernt. Ausnahmslos jeder Dokumenttyp fällt jetzt auf
    denselben geteilten Satz zurück, sobald er keine eigene Zeile hat."""
    db = db_session()
    expected_block_types = {row[0] for row in DEFAULT_SHARED_LAYOUT}
    for doc_type in ("order", "invoice", "reminder", "service_report", "quote"):
        blocks = ensure_default_layout(db, doc_type)
        assert {b.block_type for b in blocks} == expected_block_types
        assert all(b.document_type == "default" for b in blocks)


def test_ensure_default_layout_logo_hidden_by_default():
    """Es gibt beim Start kein hochgeladenes Logo -- der Logo-Baustein muss
    deshalb unsichtbar vorbelegt sein, sonst zeichnet der spätere Renderer
    eine leere Fläche."""
    db = db_session()
    blocks = ensure_default_layout(db, "default")
    logo_block = [b for b in blocks if b.block_type == "logo"][0]
    assert logo_block.visible is False


def test_ensure_default_layout_rejects_unknown_document_type():
    db = db_session()
    try:
        ensure_default_layout(db, "gutschrift")
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_ensure_default_layout_does_not_duplicate_on_second_call():
    db = db_session()
    ensure_default_layout(db, "default")
    ensure_default_layout(db, "default")
    assert len(list_layout_blocks(db, "default")) == len(DEFAULT_SHARED_LAYOUT)


def test_ensure_default_layout_preserves_existing_edits():
    db = db_session()
    blocks = ensure_default_layout(db, "default")
    header = [b for b in blocks if b.block_type == "company_header"][0]
    update_layout_block(
        db, header, x_mm=Decimal("20"), y_mm=Decimal("20"), width_mm=Decimal("170"), height_mm=Decimal("30"),
        content=None, font_size=Decimal("11"), font_weight="bold", text_align="center", visible=True,
    )
    ensure_default_layout(db, "default")  # darf die Bearbeitung nicht zurücksetzen
    reloaded = [b for b in list_layout_blocks(db, "default") if b.block_type == "company_header"][0]
    assert reloaded.x_mm == Decimal("20")
    assert reloaded.font_weight == "bold"


# ---------------------------------------------------------------------------
# update_layout_block
# ---------------------------------------------------------------------------

def test_update_layout_block_changes_position_and_style():
    db = db_session()
    blocks = ensure_default_layout(db, "default")
    footer = [b for b in blocks if b.block_type == "footer_text"][0]
    updated = update_layout_block(
        db, footer, x_mm=Decimal("50"), y_mm=Decimal("200"), width_mm=Decimal("100"), height_mm=Decimal("15"),
        content=None, font_size=Decimal("10"), font_weight="bold", text_align="right", visible=False,
    )
    assert updated.x_mm == Decimal("50")
    assert updated.visible is False
    assert updated.text_align == "right"


def test_update_layout_block_ignores_content_for_predefined_blocks():
    """content ist nur bei custom_text gedacht (bis 1.3.20, seither entfernt, siehe CLAUDE.md
    "Gemeinsamer Dokumenttyp"/Aufräumen nach dem PDF-Umbau) -- bei vordefinierten Bausteinen
    (deren Inhalt aus den echten Dokumentdaten kommt) darf ein versehentlich mitgeschickter
    content-Wert nichts bewirken."""
    db = db_session()
    blocks = ensure_default_layout(db, "default")
    header = [b for b in blocks if b.block_type == "company_header"][0]
    updated = update_layout_block(
        db, header, x_mm=header.x_mm, y_mm=header.y_mm, width_mm=header.width_mm, height_mm=header.height_mm,
        content="Das sollte ignoriert werden", font_size=header.font_size, font_weight=header.font_weight,
        text_align=header.text_align, visible=True,
    )
    assert updated.content is None


# ---------------------------------------------------------------------------
# reset_layout_to_default
# ---------------------------------------------------------------------------

def test_reset_layout_restores_defaults_after_an_edit():
    """Bis 1.3.20 zusätzlich ein Nachweis, dass eigene custom_text-Bausteine beim Zurücksetzen
    mitgelöscht werden -- die custom_text-Funktion selbst ist beim Aufräumen nach dem PDF-Umbau
    entfernt worden (CLAUDE.md "Gemeinsamer Dokumenttyp"), bleibt deshalb hier auf den
    predefined-Bausteinen selbst geprüft."""
    db = db_session()
    blocks = ensure_default_layout(db, "default")
    header = [b for b in blocks if b.block_type == "company_header"][0]
    update_layout_block(
        db, header, x_mm=Decimal("99"), y_mm=Decimal("99"), width_mm=Decimal("50"), height_mm=Decimal("10"),
        content=None, font_size=Decimal("14"), font_weight="bold", text_align="center", visible=False,
    )

    reset_blocks = reset_layout_to_default(db, "default")
    assert len(reset_blocks) == len(DEFAULT_SHARED_LAYOUT)
    assert {b.block_type for b in reset_blocks} == {row[0] for row in DEFAULT_SHARED_LAYOUT}
    header_after = [b for b in reset_blocks if b.block_type == "company_header"][0]
    assert header_after.x_mm == Decimal("18")  # zurück auf den Standardwert
    assert header_after.visible is False  # company_header-Standard seit 1.3.2


# ---------------------------------------------------------------------------
# Firmenlogo-Speicherung
# ---------------------------------------------------------------------------

def test_replace_logo_stores_file_and_removes_previous(tmp_path, monkeypatch):
    import app.company_logo as company_logo
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")

    stored1 = company_logo.replace_logo(None, "Logo.png", b"erste Version")
    path1 = company_logo.logo_path(stored1)
    assert path1.is_file()
    assert path1.read_bytes() == b"erste Version"

    stored2 = company_logo.replace_logo(stored1, "NeuesLogo.PNG", b"zweite Version")
    assert not path1.exists()  # altes Logo entfernt
    path2 = company_logo.logo_path(stored2)
    assert path2.is_file()
    assert path2.read_bytes() == b"zweite Version"
    assert path2.suffix == ".png"  # kleingeschrieben, unabhängig vom Original


def test_delete_logo_removes_file(tmp_path, monkeypatch):
    import app.company_logo as company_logo
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    stored = company_logo.replace_logo(None, "Logo.png", b"Inhalt")
    path = company_logo.logo_path(stored)
    assert path.is_file()
    company_logo.delete_logo(stored)
    assert not path.exists()


def test_general_settings_model_has_logo_filename_column():
    src = Path("app/models.py").read_text(encoding="utf-8")
    body_start = src.index("class GeneralSettings(Base):")
    body_end = src.index("\n\nclass ", body_start)
    body = src[body_start:body_end]
    assert "logo_filename: Mapped[str | None]" in body


# ---------------------------------------------------------------------------
# Statische Prüfungen: Router-Registrierung
# ---------------------------------------------------------------------------

def test_document_layout_router_registered():
    """Seit 1.3.20 (Aufräumen nach dem PDF-Umbau) ohne die custom_text-ANLEGEN/LÖSCHEN-Endpunkte
    (POST .../blocks, DELETE .../blocks/{block_id}) -- custom_text selbst ist entfernt, siehe
    CLAUDE.md "Gemeinsamer Dokumenttyp". PUT .../blocks/{block_id} bleibt bestehen: er aktualisiert
    generisch Position/Sichtbarkeit JEDES Bausteins, nicht nur custom_text, und wird aktiv von
    den "Gezeichnete Bausteine"-Kontrollkästchen in settings.html genutzt (Logo/Firmenkopf/
    Fußzeile/Wiederholungszeile ein-/ausschalten, Position der Wiederholungszeile ändern)."""
    root = Path(__file__).parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    router_src = (root / "app" / "routers" / "document_layout.py").read_text(encoding="utf-8")
    assert "app.include_router(document_layout.router)" in main
    for path in [
        '@router.get("/api/document-layout/{document_type}"',
        '@router.put("/api/document-layout/blocks/{block_id}"',
        '@router.post("/api/document-layout/{document_type}/reset"',
    ]:
        assert path in router_src, f"fehlt: {path}"
    for path in [
        '@router.post("/api/document-layout/{document_type}/blocks"',
        '@router.delete("/api/document-layout/blocks/{block_id}"',
    ]:
        assert path not in router_src, f"haette entfernt sein sollen: {path}"


def test_logo_endpoints_registered_in_settings_router():
    src = (Path(__file__).parents[1] / "app" / "routers" / "settings.py").read_text(encoding="utf-8")
    for path in [
        '@router.post("/api/settings/general/logo"',
        '@router.get("/api/settings/general/logo")',
        '@router.delete("/api/settings/general/logo"',
    ]:
        assert path in src, f"fehlt: {path}"


# ---------------------------------------------------------------------------
# Briefbogen-Hintergrund (seit 1.0.61)
# ---------------------------------------------------------------------------

def test_replace_background_stores_file_and_removes_previous(tmp_path, monkeypatch):
    import app.document_layout_background as background_storage
    monkeypatch.setattr(background_storage, "BACKGROUND_ROOT", tmp_path / "layout_backgrounds")

    stored1 = background_storage.replace_background(None, "Briefbogen.png", b"erste Version")
    path1 = background_storage.background_path(stored1)
    assert path1.is_file()
    assert path1.read_bytes() == b"erste Version"

    stored2 = background_storage.replace_background(stored1, "NeuerBriefbogen.PNG", b"zweite Version")
    assert not path1.exists()  # alter Hintergrund entfernt
    path2 = background_storage.background_path(stored2)
    assert path2.is_file()
    assert path2.read_bytes() == b"zweite Version"


def test_delete_background_file_removes_file(tmp_path, monkeypatch):
    import app.document_layout_background as background_storage
    monkeypatch.setattr(background_storage, "BACKGROUND_ROOT", tmp_path / "layout_backgrounds")
    stored = background_storage.replace_background(None, "Briefbogen.png", b"Inhalt")
    path = background_storage.background_path(stored)
    assert path.is_file()
    background_storage.delete_background_file(stored)
    assert not path.exists()


def test_background_db_row_get_set_remove_roundtrip():
    db = db_session()
    assert get_background(db, "quote") is None

    row = set_background(db, "quote", "abc123.png")
    assert row.document_type == "quote"
    assert row.stored_filename == "abc123.png"
    assert get_background(db, "quote").stored_filename == "abc123.png"

    # erneutes Setzen aktualisiert dieselbe Zeile statt eine zweite anzulegen
    set_background(db, "quote", "def456.png")
    assert get_background(db, "quote").stored_filename == "def456.png"

    remove_background(db, "quote")
    assert get_background(db, "quote") is None


def test_background_scoped_per_document_type():
    db = db_session()
    set_background(db, "quote", "quote-bg.png")
    assert get_background(db, "order") is None  # unabhängig von 'quote'


def test_document_layout_background_router_endpoints_registered():
    src = (Path(__file__).parents[1] / "app" / "routers" / "document_layout.py").read_text(encoding="utf-8")
    for path in [
        '@router.get("/api/document-layout/{document_type}/background"',
        '@router.get("/api/document-layout/{document_type}/background/file")',
        '@router.post("/api/document-layout/{document_type}/background"',
        '@router.delete("/api/document-layout/{document_type}/background"',
    ]:
        assert path in src, f"fehlt: {path}"


def test_document_layout_block_docstring_matches_actual_block_types():
    """Regressionstest für einen früher gefundenen veralteten Docstring-Kommentar -- listet die
    tatsächlich in DEFAULT_SHARED_LAYOUT verwendeten block_type-Werte, keine erfundenen (z.B. das
    frühere, nie tatsächlich genutzte 'outro_texts', oder seit 1.3.20 die mit dem alten Renderer
    entfernten quote-spezifischen Bausteine wie 'items_table'/'meta_table')."""
    body = (Path(__file__).parents[1] / "app" / "models.py").read_text(encoding="utf-8")
    body = body[body.index("class DocumentLayoutBlock(Base):"):]
    body = body[:body.index("\n\nclass ")]
    assert "customer_meta" not in body
    assert "outro_texts" not in body
    for block_type, *_ in DEFAULT_SHARED_LAYOUT:
        assert block_type in body, f"{block_type} fehlt im Docstring"
