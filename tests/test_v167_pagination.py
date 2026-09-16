from decimal import Decimal
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.document_layout import get_background, set_background, set_background_repeat
from app.models import Customer, Project, Quote, QuoteItem
from app.project_pipeline_columns import default_pipeline_column_id


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Zählt die tatsächlichen Seiten über die PDF-Objektstruktur (/Type/Page,
    aber nicht /Type/Pages, das ist ein anderer, übergeordneter Container) --
    bewusst ohne zusätzliche Bibliothek wie pypdf, die (noch) keine
    Projektabhängigkeit ist. Diese Objektangaben liegen unkomprimiert vor,
    auch wenn reportlab die eigentlichen Seiteninhalte komprimiert."""
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))


def make_quote_with_items(db, item_count=1, vat_rate=Decimal("19.00")):
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    quote = Quote(quote_number="A-TEST-0001", project_id=project.id, title="Testangebot", vat_rate=vat_rate)
    db.add(quote)
    db.flush()
    for i in range(1, item_count + 1):
        db.add(QuoteItem(
            quote_id=quote.id, sort_order=i * 10, position_number=str(i),
            short_text=f"Position {i}: Dachlattung montieren und ausrichten",
            quantity=Decimal("10"), unit="m", unit_price=Decimal("12.50"),
        ))
    db.commit()
    db.refresh(quote)
    return quote


# ---------------------------------------------------------------------------
# repeat_on_every_page (Hintergrund-Wiederholung als Einstellung, seit 1.0.67)
# ---------------------------------------------------------------------------

def test_background_repeat_defaults_to_true():
    db = db_session()
    row = set_background(db, "default", "irgendeine-datei.png")
    assert row.repeat_on_every_page is True


def test_set_background_repeat_updates_existing_row():
    db = db_session()
    set_background(db, "default", "briefbogen.png")
    updated = set_background_repeat(db, "default", False)
    assert updated.repeat_on_every_page is False
    assert get_background(db, "default").repeat_on_every_page is False


def test_set_background_repeat_returns_none_without_existing_background():
    db = db_session()
    assert set_background_repeat(db, "default", False) is None
