from unittest.mock import MagicMock, patch

import pytest

from tools import weather

GEOCODE_SINGLE = [
    {"name": "Seattle", "state": "Washington", "country": "US", "lat": 47.6, "lon": -122.3},
]

GEOCODE_AMBIGUOUS = [
    {"name": "Springfield", "state": "Illinois", "country": "US", "lat": 1.0, "lon": 1.0},
    {"name": "Springfield", "state": "Massachusetts", "country": "US", "lat": 2.0, "lon": 2.0},
]

# Loosely-related results for a non-ambiguous query: a same-name town in
# another country and an unrelated neighborhood should not trigger
# disambiguation - the first (most relevant) result should just be used.
GEOCODE_LOOSELY_RELATED = [
    {"name": "Seattle", "state": "Washington", "country": "US", "lat": 47.6, "lon": -122.3},
    {"name": "Seattle", "state": "Jalisco", "country": "MX", "lat": 1.0, "lon": 1.0},
    {"name": "Laurelhurst", "state": "Oregon", "country": "US", "lat": 2.0, "lon": 2.0},
]

FORECAST_OK = {
    "cod": "200",
    "city": {"name": "Seattle"},
    "list": [
        {"dt_txt": "2026-06-12 12:00:00", "main": {"temp": 65}, "weather": [{"main": "Rain"}]},
        {"dt_txt": "2026-06-12 15:00:00", "main": {"temp": 70}, "weather": [{"main": "Rain"}]},
        {"dt_txt": "2026-06-13 12:00:00", "main": {"temp": 75}, "weather": [{"main": "Clear"}]},
    ],
}


@pytest.fixture(autouse=True)
def clear_caches():
    weather._geocode_cache.clear()
    weather._forecast_cache.clear()


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(weather, "OPENWEATHER_API_KEY", "test-key")


def _mock_response(json_data):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


def _fake_get_factory(geocode_result, forecast_result=FORECAST_OK):
    def fake_get(url, params, timeout):
        if url == weather.GEOCODING_URL:
            return _mock_response(geocode_result)
        return _mock_response(forecast_result)

    return fake_get


def test_get_weather_success():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory(GEOCODE_SINGLE)):
        result = weather.get_weather("Seattle", "2026-06-12")

    assert result["location"] == "Seattle"
    assert result["date"] == "2026-06-12"
    assert result["condition"] == "Rain"
    assert result["temp_min"] == 65
    assert result["temp_max"] == 70


def test_get_weather_multi_day():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory(GEOCODE_SINGLE)):
        result = weather.get_weather("Seattle", "2026-06-12", "2026-06-13")

    assert result["start_date"] == "2026-06-12"
    assert result["end_date"] == "2026-06-13"
    assert [day["date"] for day in result["days"]] == ["2026-06-12", "2026-06-13"]
    assert result["days"][1]["condition"] == "Clear"


def test_get_weather_no_api_key(monkeypatch):
    monkeypatch.setattr(weather, "OPENWEATHER_API_KEY", "")
    result = weather.get_weather("Seattle", "2026-06-12")
    assert "error" in result


def test_get_weather_proceeds_with_possible_alternates():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory(GEOCODE_AMBIGUOUS)):
        result = weather.get_weather("Springfield", "2026-06-12")

    assert "error" not in result
    assert result["condition"] == "Rain"
    assert len(result["possible_alternates"]) == 1
    assert result["possible_alternates"][0]["state"] == "Massachusetts"


def test_resolve_location_ambiguous():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory(GEOCODE_AMBIGUOUS)):
        result = weather.resolve_location("Springfield")

    assert result["error"] == "ambiguous_location"
    assert len(result["matches"]) == 2


def test_resolve_location_unambiguous():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory(GEOCODE_SINGLE)):
        result = weather.resolve_location("Seattle")

    assert result["resolved"] == "Seattle, Washington, US"


def test_get_weather_ignores_loosely_related_matches():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory(GEOCODE_LOOSELY_RELATED)):
        result = weather.get_weather("Seattle", "2026-06-12")

    assert "error" not in result
    assert result["location"] == "Seattle"


def test_get_weather_location_not_found():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory([])):
        result = weather.get_weather("Nowhereville", "2026-06-12")

    assert "error" in result


def test_get_weather_service_unavailable():
    with patch("tools.weather.requests.get", side_effect=weather.requests.RequestException("boom")):
        result = weather.get_weather("Seattle", "2026-06-12")

    assert "error" in result


def test_get_weather_date_out_of_range():
    with patch("tools.weather.requests.get", side_effect=_fake_get_factory(GEOCODE_SINGLE)):
        result = weather.get_weather("Seattle", "2030-01-01")

    assert "error" in result


def test_get_weather_uses_cache():
    fake_get = _fake_get_factory(GEOCODE_SINGLE)
    with patch("tools.weather.requests.get", side_effect=fake_get) as mock_get:
        weather.get_weather("Seattle", "2026-06-12")
        weather.get_weather("Seattle", "2026-06-12")

    # one geocode + one forecast call, made only once total
    assert mock_get.call_count == 2
