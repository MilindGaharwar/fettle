from src.calculator import eligible_for_discount


def test_large_order_is_eligible():
    assert eligible_for_discount(150)
