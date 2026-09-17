from decimal import Decimal
from pathlib import Path

from app.models import (
    Customer, Project, ProjectProfile, Quote, QuoteDocumentMeta, QuoteItem,
    QuoteItemCalculation, QuoteItemLayout, QuoteItemMaterialCalculation, QuoteSection,
)
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import duplicate_project, load_project
from tests.test_v153_mahnwesen import db_session


def make_full_project(db, *, category="Sanierung", project_number="P-TEST-0001", quote_number="A-TEST-0001"):
    """Projekt mit vollständig ausgebautem Angebot -- zwei Sections (eine
    Eltern-, eine Kind-Section, um die zweistufige Gliederung zu prüfen),
    zwei Positionen (eine mit vollständiger Kalkulation inkl. Material,
    eine ohne), Dokumenten-Meta. Bewusst OHNE QuoteEmployeeAssignment (die
    ist optional und würde nur unnötig einen Employee-Datensatz erfordern).

    project_number/quote_number als Parameter (mit dem bisherigen fest
    verdrahteten Wert als Standard) -- nötig, sobald ein Test diese
    Funktion mehrfach in derselben Session aufruft (project_number/
    quote_number tragen beide eine UNIQUE-Constraint)."""
    customer = Customer(name="Ursprungskunde", last_name="Ursprungskunde", email="ursprung@example.com")
    db.add(customer)
    db.flush()
    project = Project(project_number=project_number, name="Dachsanierung Musterweg", customer_id=customer.id, status="beauftragt", pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    db.add(ProjectProfile(project_id=project.id, category=category))

    quote = Quote(quote_number=quote_number, project_id=project.id, title="Dachsanierung", status="versendet", vat_rate=Decimal("19.00"), intro_text="Sehr geehrte Damen und Herren")
    db.add(quote)
    db.flush()
    db.add(QuoteDocumentMeta(quote_id=quote.id, contact_person="Herr Test"))

    parent = QuoteSection(quote_id=quote.id, title="Dacharbeiten", sort_order=10, section_number="01")
    db.add(parent)
    db.flush()
    child = QuoteSection(quote_id=quote.id, parent_id=parent.id, title="Eindeckung", sort_order=10, section_number="01.01")
    db.add(child)
    db.flush()

    item_with_calc = QuoteItem(
        quote_id=quote.id, sort_order=10, position_number="1", short_text="Dacheindeckung erneuern",
        quantity=Decimal("120"), unit="m²", unit_price=Decimal("85.00"),
    )
    db.add(item_with_calc)
    db.flush()
    db.add(QuoteItemLayout(quote_item_id=item_with_calc.id, section_id=child.id, sort_order=10, include_in_total=True))
    calc = QuoteItemCalculation(
        quote_item_id=item_with_calc.id, site_time_minutes=Decimal("45"), workshop_time_minutes=Decimal("5"),
        labor_rate=Decimal("42.50"), material_markup_pct=Decimal("15"), overhead_pct=Decimal("10"), risk_profit_pct=Decimal("8"),
    )
    db.add(calc)
    db.flush()
    db.add(QuoteItemMaterialCalculation(
        calculation_id=calc.id, name="Dachziegel Frankfurter Pfanne", unit="Stk", source_quantity=Decimal("12"),
        quantity=Decimal("13.2"), waste_pct=Decimal("10"), source_purchase_price=Decimal("1.20"), purchase_price=Decimal("1.20"),
    ))

    item_without_calc = QuoteItem(
        quote_id=quote.id, sort_order=20, position_number="2", short_text="Baustelle einrichten",
        quantity=Decimal("1"), unit="psch", unit_price=Decimal("450.00"),
    )
    db.add(item_without_calc)
    db.commit()
    return load_project(db, project.id)


# ---------------------------------------------------------------------------
# duplicate_project() -- Projekt-Grunddaten
# ---------------------------------------------------------------------------

def test_duplicate_gets_new_project_number_and_starts_at_anfrage():
    db = db_session()
    source = make_full_project(db)
    copy = duplicate_project(db, source, as_template=False)
    assert copy.id != source.id
    assert copy.project_number != source.project_number
    assert copy.status == "anfrage"  # unabhängig vom Status des Quellprojekts


def test_duplicate_copies_customer_property_and_category():
    db = db_session()
    source = make_full_project(db, category="Neubau")
    copy = duplicate_project(db, source, as_template=False)
    assert copy.customer_id == source.customer_id
    assert copy.property_id == source.property_id
    assert copy.profile.category == "Neubau"


def test_duplicate_as_template_sets_flag_normal_copy_does_not():
    db = db_session()
    source = make_full_project(db)
    template = duplicate_project(db, source, as_template=True)
    normal_copy = duplicate_project(db, source, as_template=False)
    assert template.is_template is True
    assert normal_copy.is_template is False
    assert source.is_template is False  # Quellprojekt selbst bleibt unverändert


def test_duplicate_source_can_itself_be_a_template():
    """Ein Muster kann selbst wieder dupliziert werden (z.B. Muster -> Muster,
    oder Muster -> echtes Projekt bei 'neuen Vorgang aus Muster erstellen')."""
    db = db_session()
    source = make_full_project(db)
    template = duplicate_project(db, source, as_template=True)
    real_project = duplicate_project(db, template, as_template=False)
    assert real_project.is_template is False
    assert real_project.quotes[0].title == source.quotes[0].title


# ---------------------------------------------------------------------------
# duplicate_project() -- Angebots-Struktur
# ---------------------------------------------------------------------------

def test_duplicate_creates_new_quote_with_new_number_and_draft_status():
    db = db_session()
    source = make_full_project(db)
    copy = duplicate_project(db, source, as_template=False)
    assert len(copy.quotes) == 1
    new_quote = copy.quotes[0]
    assert new_quote.quote_number != source.quotes[0].quote_number
    assert new_quote.status == "entwurf"  # unabhängig davon, dass das Quellangebot 'versendet' war
    assert new_quote.title == source.quotes[0].title
    assert new_quote.intro_text == source.quotes[0].intro_text


def test_duplicate_copies_both_items_with_correct_amounts():
    db = db_session()
    source = make_full_project(db)
    copy = duplicate_project(db, source, as_template=False)
    new_items = sorted(copy.quotes[0].items, key=lambda i: i.sort_order)
    assert len(new_items) == 2
    assert new_items[0].short_text == "Dacheindeckung erneuern"
    assert new_items[0].quantity == Decimal("120")
    assert new_items[0].unit_price == Decimal("85.00")
    assert new_items[1].short_text == "Baustelle einrichten"


def test_duplicate_preserves_section_hierarchy_and_item_assignment():
    """Kernprüfung der id-Neuzuordnung: die kopierte Position muss auf die
    KOPIERTE Kind-Section verweisen (neue id), nicht auf die alte -- und
    die Kind-Section muss weiterhin auf die kopierte Eltern-Section zeigen."""
    from sqlalchemy import select
    db = db_session()
    source = make_full_project(db)
    copy = duplicate_project(db, source, as_template=False)
    new_quote = copy.quotes[0]

    new_sections = db.scalars(select(QuoteSection).where(QuoteSection.quote_id == new_quote.id)).all()
    assert len(new_sections) == 2
    new_parent = next(s for s in new_sections if s.parent_id is None)
    new_child = next(s for s in new_sections if s.parent_id is not None)
    assert new_parent.title == "Dacharbeiten"
    assert new_child.title == "Eindeckung"
    assert new_child.parent_id == new_parent.id  # zeigt auf die NEUE Eltern-id, nicht die alte

    new_item = next(i for i in new_quote.items if i.short_text == "Dacheindeckung erneuern")
    new_layout = db.scalar(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id == new_item.id))
    assert new_layout is not None
    assert new_layout.section_id == new_child.id  # zeigt auf die NEUE Kind-Section, nicht die alte


def test_duplicate_copies_calculation_and_material_line():
    """Kernwert des Features: ohne mitkopierte Kalkulation müsste jede
    Position für den neuen Vorgang komplett neu kalkuliert werden."""
    from sqlalchemy import select
    db = db_session()
    source = make_full_project(db)
    copy = duplicate_project(db, source, as_template=False)
    new_quote = copy.quotes[0]

    new_item = next(i for i in new_quote.items if i.short_text == "Dacheindeckung erneuern")
    new_calc = db.scalar(select(QuoteItemCalculation).where(QuoteItemCalculation.quote_item_id == new_item.id))
    assert new_calc is not None
    assert new_calc.site_time_minutes == Decimal("45")
    assert new_calc.labor_rate == Decimal("42.50")

    new_materials = db.scalars(select(QuoteItemMaterialCalculation).where(QuoteItemMaterialCalculation.calculation_id == new_calc.id)).all()
    assert len(new_materials) == 1
    assert new_materials[0].name == "Dachziegel Frankfurter Pfanne"
    assert new_materials[0].quantity == Decimal("13.2")


def test_duplicate_item_without_calculation_stays_without_calculation():
    from sqlalchemy import select
    db = db_session()
    source = make_full_project(db)
    copy = duplicate_project(db, source, as_template=False)
    new_item = next(i for i in copy.quotes[0].items if i.short_text == "Baustelle einrichten")
    new_calc = db.scalar(select(QuoteItemCalculation).where(QuoteItemCalculation.quote_item_id == new_item.id))
    assert new_calc is None


def test_duplicate_does_not_carry_over_valid_until_but_sets_todays_date():
    from sqlalchemy import select
    from datetime import date
    db = db_session()
    source = make_full_project(db)
    source_meta = db.scalar(select(QuoteDocumentMeta).where(QuoteDocumentMeta.quote_id == source.quotes[0].id))
    source_meta.valid_until = date(2020, 1, 1)
    db.commit()

    copy = duplicate_project(db, source, as_template=False)
    new_meta = db.scalar(select(QuoteDocumentMeta).where(QuoteDocumentMeta.quote_id == copy.quotes[0].id))
    assert new_meta.valid_until is None
    assert new_meta.quote_date == date.today()
    assert new_meta.contact_person == "Herr Test"  # sonstige Angaben bleiben erhalten


def test_duplicate_never_copies_orders():
    """Ein bestehender Auftrag (unveränderlicher LV-Snapshot) darf nie
    mitkopiert werden -- die Kopie startet immer wieder im Angebotsstadium."""
    from decimal import Decimal as D
    from app.models import Order
    db = db_session()
    source = make_full_project(db)
    order = Order(
        order_number="AUF-TEST-0001", project_id=source.id, source_quote_id=source.quotes[0].id,
        quote_number_snapshot=source.quotes[0].quote_number, title="Dachsanierung", vat_rate=D("19.00"),
        customer_name="Ursprungskunde", customer_number="K-0001",
    )
    db.add(order)
    db.commit()

    copy = duplicate_project(db, source, as_template=False)
    assert len(copy.orders) == 0


def test_duplicate_project_without_any_quote_still_works():
    """Randfall: ein Projekt ganz ohne Angebot muss trotzdem kopierbar
    sein (z.B. ein frisch angelegtes Projekt, das noch kein Angebot hat)."""
    db = db_session()
    customer = Customer(name="Kunde ohne Angebot", last_name="Kunde ohne Angebot")
    db.add(customer)
    db.flush()
    empty_project = Project(project_number="P-TEST-0002", name="Noch ohne Angebot", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(empty_project)
    db.commit()
    empty_project = load_project(db, empty_project.id)

    copy = duplicate_project(db, empty_project, as_template=False)
    assert copy.id != empty_project.id
    assert len(copy.quotes) == 0


def test_duplicate_with_multiple_quotes_copies_only_the_latest():
    db = db_session()
    source = make_full_project(db)
    second_quote = Quote(quote_number="A-TEST-0002", project_id=source.id, title="Zweites, neueres Angebot", status="entwurf", vat_rate=Decimal("19.00"))
    db.add(second_quote)
    db.commit()
    source = load_project(db, source.id)

    copy = duplicate_project(db, source, as_template=False)
    assert len(copy.quotes) == 1
    assert copy.quotes[0].title == "Zweites, neueres Angebot"


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_projects_router_has_template_endpoints():
    src = (Path(__file__).parents[1] / "app" / "routers" / "projects.py").read_text(encoding="utf-8")
    assert '@router.get("/api/project-templates"' in src
    assert '@router.post("/api/projects/{project_id}/duplicate"' in src


def test_projects_list_endpoint_filters_out_templates():
    src = (Path(__file__).parents[1] / "app" / "routers" / "projects.py").read_text(encoding="utf-8")
    assert "is_template=False" in src
    assert "is_template=True" in src


def test_projects_page_has_duplicate_and_template_actions():
    html = (Path(__file__).parents[1] / "app" / "templates" / "projects.html").read_text(encoding="utf-8")
    assert "duplicateProject" in html
    assert "Als Mustervorgang speichern" in html
    # Seit "Runde 2 der Projektliste" (siehe CLAUDE.md) kein eigener Reiter mehr --
    # Mustervorgänge bleiben stattdessen über einen Filter in derselben Liste sichtbar.
    assert "onlyTemplates" in html
    assert "Nur Mustervorgänge" in html
    assert "/api/project-templates" in html


def test_project_folder_page_has_duplicate_and_template_actions():
    html = (Path(__file__).parents[1] / "app" / "templates" / "project_folder.html").read_text(encoding="utf-8")
    assert "duplicateProjectHere" in html
    assert "Als Mustervorgang speichern" in html
