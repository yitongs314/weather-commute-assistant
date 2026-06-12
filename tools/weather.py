import requests

from config import OPENWEATHER_API_KEY

GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Simple in-memory caches so repeated lookups for the same location/date(s)
# within a session don't re-hit the APIs.
_geocode_cache: dict[str, list] = {}
_forecast_cache: dict[tuple[str, str, str], dict] = {}


def _geocode(location: str) -> list:
    """Resolve a location name to one or more candidate places."""
    key = location.lower().strip()
    if key in _geocode_cache:
        return _geocode_cache[key]

    params = {"q": location, "limit": 5, "appid": OPENWEATHER_API_KEY}
    response = requests.get(GEOCODING_URL, params=params, timeout=10)
    response.raise_for_status()
    results = response.json()
    _geocode_cache[key] = results
    return results


def _format_place(place: dict) -> dict:
    return {"name": place["name"], "state": place.get("state", ""), "country": place["country"]}


def _resolve_candidates(location: str) -> dict:
    """Geocode `location` and pick the best match plus any same-country
    alternates with the same name (e.g. other states' Springfields).

    Returns {"best": <place>, "alternates": [<place>, ...]}, or
    {"error": ...} if the location can't be found at all.
    """
    if not OPENWEATHER_API_KEY:
        return {"error": "OpenWeatherMap API key is not configured."}

    try:
        geo_results = _geocode(location)
    except requests.RequestException as exc:
        return {"error": f"Weather service unavailable: {exc}"}

    if not geo_results:
        return {"error": f"Could not find a location matching '{location}'."}

    # The geocoding API can return loosely-related results (e.g. a
    # differently-named neighborhood, or a tiny same-name town in another
    # country). Only consider results with the *same name* in the *same
    # country* as the top match as potential alternates (e.g. Springfield,
    # IL vs Springfield, MA).
    query_name = location.split(",")[0].strip().lower()
    exact_matches = [r for r in geo_results if r["name"].lower() == query_name]
    candidates = exact_matches or geo_results

    best = candidates[0]
    alternates = [
        r
        for r in candidates
        if r["country"] == best["country"]
        and (r["name"], r.get("state", "")) != (best["name"], best.get("state", ""))
    ]
    return {"best": best, "alternates": alternates}


def resolve_location(location: str) -> dict:
    """Resolve a location name to a single, unambiguous place.

    Returns either {"resolved": "City, State, Country", "lat": ..., "lon": ...}
    or, if the name matches multiple distinct places in the same country
    (e.g. "Springfield"), {"error": "ambiguous_location", "matches": [...]}.

    This is the strict/blocking check - use it before saving a location as a
    persistent default (e.g. the user's home base), where guessing wrong
    would be sticky. For one-off weather lookups, get_weather resolves
    ambiguity non-destructively instead.
    """
    result = _resolve_candidates(location)
    if "error" in result:
        return result

    best, alternates = result["best"], result["alternates"]
    if alternates:
        return {
            "error": "ambiguous_location",
            "message": (
                f"'{location}' matches multiple places. Ask the user which one "
                "they mean, then retry with a more specific location (e.g. "
                "'Springfield, IL, US')."
            ),
            "matches": [_format_place(best)] + [_format_place(r) for r in alternates],
        }

    parts = [best["name"]]
    if best.get("state"):
        parts.append(best["state"])
    parts.append(best["country"])

    return {"resolved": ", ".join(parts), "lat": best["lat"], "lon": best["lon"]}


def get_weather(location: str, date: str, end_date: str | None = None) -> dict:
    """Get the weather forecast for a location.

    If `end_date` is given, returns a per-day breakdown for every date from
    `date` to `end_date` (inclusive, YYYY-MM-DD). Otherwise returns a single
    summary for `date`.

    Uses OpenWeatherMap's geocoding + 5-day/3-hour forecast endpoints, so
    dates more than ~5 days out will not have data available. If `location`
    name is shared by multiple places (e.g. "San Diego" also exists in
    Texas), this proceeds with the most likely match and includes a
    "possible_alternates" list so the response can mention them. If the
    location can't be found at all, returns an "error".
    """
    if not OPENWEATHER_API_KEY:
        return {"error": "OpenWeatherMap API key is not configured."}

    end_date = end_date or date

    cache_key = (location.lower().strip(), date, end_date)
    if cache_key in _forecast_cache:
        return _forecast_cache[cache_key]

    candidates_result = _resolve_candidates(location)
    if "error" in candidates_result:
        return candidates_result

    best, alternates = candidates_result["best"], candidates_result["alternates"]

    params = {
        "lat": best["lat"],
        "lon": best["lon"],
        "appid": OPENWEATHER_API_KEY,
        "units": "imperial",
    }

    try:
        response = requests.get(FORECAST_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return {"error": f"Weather service unavailable: {exc}"}

    if str(data.get("cod")) != "200":
        return {"error": data.get("message", "Unknown error from weather service.")}

    location_name = data.get("city", {}).get("name", location)

    by_day: dict[str, list] = {}
    for entry in data.get("list", []):
        entry_date = entry["dt_txt"][:10]
        if date <= entry_date <= end_date:
            by_day.setdefault(entry_date, []).append(entry)

    if not by_day:
        return {
            "error": (
                f"No forecast available for {date}"
                + (f" to {end_date}" if end_date != date else "")
                + ". This service only provides forecasts up to about 5 days ahead."
            )
        }

    days = []
    for day in sorted(by_day):
        entries = by_day[day]
        temps = [entry["main"]["temp"] for entry in entries]
        conditions = [entry["weather"][0]["main"] for entry in entries]
        days.append(
            {
                "date": day,
                "temp_min": min(temps),
                "temp_max": max(temps),
                "condition": max(set(conditions), key=conditions.count),
                "conditions_seen": sorted(set(conditions)),
            }
        )

    if len(days) == 1:
        result = {"location": location_name, **days[0]}
    else:
        result = {
            "location": location_name,
            "start_date": date,
            "end_date": end_date,
            "days": days,
        }

    if alternates:
        result["possible_alternates"] = [_format_place(r) for r in alternates]

    _forecast_cache[cache_key] = result
    return result
