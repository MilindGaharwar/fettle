from src.app import classify


def test_classify_positive() -> None:
    assert classify(1) == "positive"


def test_classify_non_positive() -> None:
    assert classify(0) == "non-positive"
