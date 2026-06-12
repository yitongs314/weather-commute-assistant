from unittest.mock import MagicMock, patch

import pytest

from tools import news


@pytest.fixture(autouse=True)
def clear_cache():
    news._news_cache.clear()


def _mock_response(json_data):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


def test_skips_non_disruptive_condition():
    result = news.get_weather_news("Seattle", "Clear")
    assert result["skipped"] is True


def test_calls_api_for_disruptive_condition(monkeypatch):
    monkeypatch.setattr(news, "NEWSAPI_API_KEY", "test-key")

    response_data = {
        "status": "ok",
        "articles": [
            {
                "title": "Storm hits Seattle",
                "source": {"name": "Example News"},
                "publishedAt": "2026-06-12T00:00:00Z",
            }
        ],
    }

    with patch("tools.news.requests.get", return_value=_mock_response(response_data)) as mock_get:
        result = news.get_weather_news("Seattle", "Rain")

    mock_get.assert_called_once()
    assert result["headlines"][0]["title"] == "Storm hits Seattle"
    assert isinstance(result["headlines"][0]["days_ago"], int)
    assert result["headlines"][0]["days_ago"] >= 0


def test_headline_days_ago_handles_invalid_timestamp(monkeypatch):
    monkeypatch.setattr(news, "NEWSAPI_API_KEY", "test-key")

    response_data = {
        "status": "ok",
        "articles": [
            {
                "title": "Storm hits Seattle",
                "source": {"name": "Example News"},
                "publishedAt": "not-a-timestamp",
            }
        ],
    }

    with patch("tools.news.requests.get", return_value=_mock_response(response_data)):
        result = news.get_weather_news("Seattle", "Rain")

    assert result["headlines"][0]["days_ago"] is None


def test_no_api_key(monkeypatch):
    monkeypatch.setattr(news, "NEWSAPI_API_KEY", "")
    result = news.get_weather_news("Seattle", "Snow")
    assert "error" in result


def test_news_service_unavailable(monkeypatch):
    monkeypatch.setattr(news, "NEWSAPI_API_KEY", "test-key")

    with patch("tools.news.requests.get", side_effect=news.requests.RequestException("boom")):
        result = news.get_weather_news("Seattle", "Snow")

    assert "error" in result


def test_caches_successful_result(monkeypatch):
    monkeypatch.setattr(news, "NEWSAPI_API_KEY", "test-key")

    response_data = {"status": "ok", "articles": []}

    with patch("tools.news.requests.get", return_value=_mock_response(response_data)) as mock_get:
        news.get_weather_news("Seattle", "Snow")
        news.get_weather_news("Seattle", "Snow")

    mock_get.assert_called_once()


def test_caches_skip_result_without_api_call(monkeypatch):
    monkeypatch.setattr(news, "NEWSAPI_API_KEY", "test-key")

    with patch("tools.news.requests.get") as mock_get:
        news.get_weather_news("Seattle", "Clear")
        news.get_weather_news("Seattle", "Clear")

    mock_get.assert_not_called()
