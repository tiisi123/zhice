from packages.normalizers.market_fields import normalize_change_rate


def test_normalize_change_rate_keeps_percentage_points():
    assert normalize_change_rate(10.0) == 10.0
    assert normalize_change_rate("9.98") == 9.98


def test_normalize_change_rate_converts_ratio_values():
    assert normalize_change_rate(0.1) == 10.0
    assert normalize_change_rate("-0.075") == -7.5


def test_normalize_change_rate_handles_empty_values():
    assert normalize_change_rate(None) == 0.0
    assert normalize_change_rate("--") == 0.0
