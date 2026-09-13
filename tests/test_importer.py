from pathlib import Path
from decimal import Decimal
from app.importers.leistungen_dach import parse_leistungen_dach_xml


def test_real_sample_file():
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    project = parse_leistungen_dach_xml(sample.read_bytes())

    assert project.source_name == "Leistungen Dach"
    assert project.source_version == "3"
    assert project.title_count == 1
    assert len(project.services) == 22
    assert project.material_item_count == 59

    first = project.services[0]
    assert first.external_id == "L200219202015"
    assert first.quantity == Decimal("1.0000000000")
    assert first.site_time_raw == Decimal("2.00")
    assert first.sale_price == Decimal("184.20400000000000000000000000")
    assert len(first.materials) == 2
