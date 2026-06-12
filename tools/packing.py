from config import ACTIVITY_ADDITIONS, PACKING_RULES


def get_packing_recommendation(
    condition: str,
    activity_type: str = "general",
    temp_max: float | None = None,
    temp_min: float | None = None,
) -> dict:
    """Recommend items to bring based on weather condition, activity type,
    and (optionally) the expected temperature range."""
    condition_key = condition.lower().strip()
    items = list(PACKING_RULES.get(condition_key, PACKING_RULES["default"]))

    if temp_max is not None and temp_max >= 85:
        items += PACKING_RULES["extreme_heat"]
    if temp_min is not None and temp_min <= 32:
        items += PACKING_RULES["extreme_cold"]

    items += ACTIVITY_ADDITIONS.get(activity_type, [])

    # de-duplicate while preserving order
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)

    return {
        "condition": condition,
        "activity_type": activity_type,
        "recommended_items": unique_items,
    }
