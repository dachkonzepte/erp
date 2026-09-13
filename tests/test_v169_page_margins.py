from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.document_page_margins import (
    DEFAULT_MARGINS,
    PAGE_TYPES,
    ensure_default_margins,
    get_margins,
    reset_margins_to_default,
    update_margins,
)


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# Geschäftslogik
# ---------------------------------------------------------------------------
#
# Seit 1.3.20 (Aufräumen nach dem PDF-Umbau, CLAUDE.md "Gemeinsamer Dokumenttyp") gegen "default"
# statt "quote" geprüft: "quote" ist kein eigenständig beschreibbarer Dokumenttyp mehr (der alte
# Renderer, der eigene Randwerte brauchte, ist entfernt) -- "default" ist seither der einzige
# Dokumenttyp, an dem sich diese generische Geschäftslogik noch isoliert (ohne Rückfall)
# beobachten lässt. test_ensure_default_margins_matches_previous_hardcoded_values ist ersatzlos
# entfallen: es gibt seit 1.3.20 keinen Dokumenttyp mehr, der die REIN generischen, unüberschriebenen
# DEFAULT_MARGINS-Werte bekäme -- jeder Typ ohne eigene Zeile fällt auf "default" zurück, und
# "default" selbst trägt eigene, gegen das echte Briefpapier vermessene Überschreibungen
# (DOCUMENT_TYPE_MARGIN_OVERRIDES, siehe CLAUDE.md "Randkorrektur 'default'").

def test_ensure_default_margins_does_not_duplicate_on_second_call():
    db = db_session()
    ensure_default_margins(db, "default", "first")
    ensure_default_margins(db, "default", "first")
    from app.models import DocumentPageMargins
    rows = db.query(DocumentPageMargins).filter_by(document_type="default", page_type="first").all()
    assert len(rows) == 1


def test_ensure_default_margins_rejects_unknown_page_type():
    db = db_session()
    try:
        ensure_default_margins(db, "default", "zweite_seite")
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_update_margins_changes_values_independently_per_page_type():
    db = db_session()
    update_margins(db, "default", "first", top_mm=Decimal("25"), bottom_mm=Decimal("30"), left_mm=Decimal("20"), right_mm=Decimal("20"))
    first = get_margins(db, "default", "first")
    cont = get_margins(db, "default", "continuation")
    assert first.top_mm == Decimal("25")
    assert cont.top_mm == Decimal("40.0")  # unabhängig von Seite 1, unverändert Standard ("default")


def test_reset_margins_restores_defaults():
    db = db_session()
    update_margins(db, "default", "first", top_mm=Decimal("99"), bottom_mm=Decimal("99"), left_mm=Decimal("99"), right_mm=Decimal("99"))
    reset = reset_margins_to_default(db, "default", "first")
    assert reset.top_mm == Decimal("25.0")  # "default"-Standard, siehe DOCUMENT_TYPE_MARGIN_OVERRIDES


def test_page_types_covers_first_and_continuation():
    assert PAGE_TYPES == {"first", "continuation"}


def test_default_margins_defined_for_both_page_types():
    assert set(DEFAULT_MARGINS.keys()) == {"first", "continuation"}


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_margins_router_endpoints_registered():
    src = (Path(__file__).parents[1] / "app" / "routers" / "document_layout.py").read_text(encoding="utf-8")
    for path in [
        '@router.get("/api/document-layout/{document_type}/margins/{page_type}"',
        '@router.put("/api/document-layout/{document_type}/margins/{page_type}"',
        '@router.post("/api/document-layout/{document_type}/margins/{page_type}/reset"',
    ]:
        assert path in src, f"fehlt: {path}"
