from tools.packing import get_packing_recommendation


def test_rain_commute():
    result = get_packing_recommendation("Rain", "commute")
    assert "umbrella" in result["recommended_items"]
    assert "waterproof jacket" in result["recommended_items"]


def test_unknown_condition_falls_back_to_default():
    result = get_packing_recommendation("Hurricane", "general")
    assert result["recommended_items"] == ["check the forecast again closer to the date"]


def test_tornado_gives_safety_advice():
    result = get_packing_recommendation("Tornado", "general")
    assert "seek sturdy shelter immediately" in result["recommended_items"]


def test_extreme_heat_adds_items():
    result = get_packing_recommendation("Clear", "outdoor_activity", temp_max=90)
    for item in ("sunscreen", "water bottle", "hat", "sunglasses", "extra water"):
        assert item in result["recommended_items"]


def test_extreme_cold_adds_items():
    result = get_packing_recommendation("Snow", "commute", temp_min=20)
    for item in ("heavy coat", "thermal layers", "gloves", "winter coat", "boots", "scarf"):
        assert item in result["recommended_items"]


def test_deduplicates_items():
    result = get_packing_recommendation("Snow", "commute", temp_min=20)
    assert len(result["recommended_items"]) == len(set(result["recommended_items"]))


def test_normal_temps_skip_extreme_additions():
    result = get_packing_recommendation("Clear", "general", temp_max=70, temp_min=50)
    assert "sunscreen" not in result["recommended_items"]
    assert "heavy coat" not in result["recommended_items"]
