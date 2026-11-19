from app.nutrition import (
    is_suspicious,
    kj_to_kcal,
    parse_count_unit,
    parse_serving_grams,
    scale,
    sum_known,
    to_float,
)


def test_to_float_handles_messy_input():
    assert to_float("12,5") == 12.5
    assert to_float(7) == 7.0
    assert to_float(None) is None
    assert to_float("") is None
    assert to_float("abc") is None
    assert to_float(-3) is None
    assert to_float(True) is None


def test_kj_to_kcal_divides():
    assert round(kj_to_kcal(1950)) == 466  # not 8159!
    assert kj_to_kcal(None) is None


def test_scale_keeps_unknown_as_unknown():
    per100 = {"kcal": 539, "protein": 6.3, "fibre": None}
    assert scale(per100, 15) == {"kcal": 80.8, "protein": 0.9, "fibre": None}


def test_sum_known_reports_completeness():
    assert sum_known([1, 2, None]) == (3, False)
    assert sum_known([1.25, 2]) == (3.2, True)


def test_suspicious():
    assert is_suspicious(8159)
    assert is_suspicious(400, protein=60, carbs=50, fat=10)
    assert not is_suspicious(539, 6.3, 57.5, 30.9)
    assert not is_suspicious(None)


def test_serving_parsing():
    assert parse_serving_grams("15 g") == 15
    assert parse_serving_grams("2 biscuits (25g)") == 25
    assert parse_serving_grams("330 ml") == 330
    assert parse_serving_grams("a bowl") is None
    assert parse_count_unit("2 biscuits (25g)") == (2, "biscuit")
    assert parse_count_unit("15 g") is None
