from app.services.propagation import get_propagation_tolerance_days


def test_propagation_tolerance_days_are_frequency_aware() -> None:
    assert get_propagation_tolerance_days("daily") == 7
    assert get_propagation_tolerance_days("weekly") == 14
    assert get_propagation_tolerance_days("monthly") == 21
