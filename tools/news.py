from datetime import datetime, timezone

import requests

from config import NEWSAPI_API_KEY

EVERYTHING_URL = "https://newsapi.org/v2/everything"

# Weather conditions severe enough to plausibly cause travel disruptions.
# If the current condition isn't in this set, the news search is skipped
# entirely (no API call made).
DISRUPTIVE_CONDITIONS = {
    "thunderstorm", "snow", "tornado", "squall", "ash", "hurricane", "rain",
}

# Simple in-memory cache so repeated lookups for the same location/condition
# within a session don't re-hit the API.
_news_cache: dict[tuple[str, str], dict] = {}


def _days_ago(published_at: str) -> int | None:
    """How many days ago an article was published, for the LLM to judge
    whether a headline still reflects current conditions."""
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - published).days


def get_weather_news(location: str, condition: str) -> dict:
    """Search recent news for weather-related advisories or travel
    disruptions affecting a location (e.g. storms, flight delays).

    Only performs the search if `condition` (the weather condition
    returned by get_weather) indicates weather severe enough to plausibly
    cause disruptions. Otherwise returns immediately without calling the
    news API.
    """
    cache_key = (location.lower().strip(), condition.lower().strip())
    if cache_key in _news_cache:
        return _news_cache[cache_key]

    if condition.lower().strip() not in DISRUPTIVE_CONDITIONS:
        result = {
            "skipped": True,
            "reason": (
                f"'{condition}' conditions are unlikely to cause travel "
                "disruptions, so a news check was not needed."
            ),
        }
        _news_cache[cache_key] = result
        return result

    if not NEWSAPI_API_KEY:
        return {"error": "NewsAPI key is not configured."}

    params = {
        "q": f"{location} AND ({condition} OR flight delay OR travel advisory OR cancellation)",
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 5,
        "apiKey": NEWSAPI_API_KEY,
    }

    try:
        response = requests.get(EVERYTHING_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return {"error": f"News service unavailable: {exc}"}

    if data.get("status") != "ok":
        return {"error": data.get("message", "Unknown error from news service.")}

    articles = data.get("articles", [])
    if not articles:
        result = {"location": location, "headlines": []}
        _news_cache[cache_key] = result
        return result

    headlines = [
        {
            "title": article["title"],
            "source": article["source"]["name"],
            "published_at": article["publishedAt"],
            "days_ago": _days_ago(article["publishedAt"]),
        }
        for article in articles
    ]
    result = {"location": location, "headlines": headlines}
    _news_cache[cache_key] = result
    return result
