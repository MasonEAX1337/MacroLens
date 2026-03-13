from datetime import datetime, timezone

import httpx

from app.services.news_context import (
    GDELTNewsContextProvider,
    NewsContextRequest,
    build_news_query,
)


def test_build_news_query_uses_dataset_specific_terms() -> None:
    request = NewsContextRequest(
        anomaly_id=1,
        dataset_name="Bitcoin Price",
        dataset_symbol="BTC",
        timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    query = build_news_query(request, "English")

    assert '"bitcoin"' in query
    assert "btc" in query
    assert "sourcelang:english" in query


def test_gdelt_provider_builds_expected_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "articles": [
                    {
                        "url": "https://example.com/article",
                        "title": "Bitcoin volatility jumps",
                        "seendate": "20260301T120000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                        "socialimage": "https://example.com/image.jpg",
                        "url_mobile": "https://m.example.com/article",
                    }
                ]
            }

    def mock_get(url, params, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return MockResponse()

    monkeypatch.setattr("app.services.news_context.httpx.get", mock_get)

    provider = GDELTNewsContextProvider(
        base_url="https://api.gdeltproject.org/api/v2/doc",
        window_days=7,
        max_articles=3,
        language="English",
        timeout_seconds=11.0,
    )
    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=1,
            dataset_name="Bitcoin Price",
            dataset_symbol="BTC",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert captured["url"] == "https://api.gdeltproject.org/api/v2/doc/doc"
    assert captured["params"]["mode"] == "ArtList"
    assert captured["params"]["maxrecords"] == 3
    assert captured["timeout"] == 11.0
    assert articles[0].title == "Bitcoin volatility jumps"
    assert articles[0].provider == "gdelt"
    assert articles[0].published_at == datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def test_gdelt_provider_filters_duplicates_and_off_topic_titles(monkeypatch) -> None:
    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "articles": [
                    {
                        "url": "https://example.com/one",
                        "title": "Bitcoin volatility jumps on market stress",
                        "seendate": "20260301T120000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                    {
                        "url": "https://example.com/two",
                        "title": "Bitcoin volatility jumps on market stress",
                        "seendate": "20260301T130000Z",
                        "domain": "example.net",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                    {
                        "url": "https://example.com/three",
                        "title": "Trump addresses reporters on trade",
                        "seendate": "20260301T110000Z",
                        "domain": "example.org",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                ]
            }

    monkeypatch.setattr(
        "app.services.news_context.httpx.get",
        lambda url, params, timeout: MockResponse(),  # noqa: ARG005
    )

    provider = GDELTNewsContextProvider(
        base_url="https://api.gdeltproject.org/api/v2/doc",
        window_days=7,
        max_articles=5,
        language="English",
        timeout_seconds=11.0,
    )
    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=1,
            dataset_name="Bitcoin Price",
            dataset_symbol="BTC",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert len(articles) == 1
    assert articles[0].title == "Bitcoin volatility jumps on market stress"


def test_gdelt_provider_filters_articles_outside_requested_window(monkeypatch) -> None:
    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "articles": [
                    {
                        "url": "https://example.com/late",
                        "title": "Bitcoin sinks again",
                        "seendate": "20260312T120000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    }
                ]
            }

    monkeypatch.setattr(
        "app.services.news_context.httpx.get",
        lambda url, params, timeout: MockResponse(),  # noqa: ARG005
    )

    provider = GDELTNewsContextProvider(
        base_url="https://api.gdeltproject.org/api/v2/doc",
        window_days=3,
        max_articles=5,
        language="English",
        timeout_seconds=11.0,
    )
    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=1,
            dataset_name="Bitcoin Price",
            dataset_symbol="BTC",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert articles == []


def test_gdelt_provider_returns_empty_list_after_rate_limit(monkeypatch) -> None:
    class MockResponse:
        status_code = 429
        text = "Too many requests"

        def raise_for_status(self) -> None:
            request = httpx.Request("GET", "https://api.gdeltproject.org/api/v2/doc/doc")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    def mock_get(url, params, timeout):  # noqa: ANN001, ARG001
        return MockResponse()

    monkeypatch.setattr("app.services.news_context.httpx.get", mock_get)
    monkeypatch.setattr("app.services.news_context.time.sleep", lambda *_args, **_kwargs: None)

    provider = GDELTNewsContextProvider(
        base_url="https://api.gdeltproject.org/api/v2/doc",
        window_days=7,
        max_articles=3,
        language="English",
        timeout_seconds=11.0,
    )

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=1,
            dataset_name="Bitcoin Price",
            dataset_symbol="BTC",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert articles == []
