from decimal import Decimal

from app.calculation import build_calculation


def test_time_relationship_from_sample_catalog():
    # Fachlicher Plausibilitätsanker aus der Beispieldatei:
    # 6 Minuten × 81,52 €/h / 60 = 8,152 €.
    assert Decimal("6") / Decimal("60") * Decimal("81.52") == Decimal("8.152")
