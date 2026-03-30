from datetime import datetime, timezone

import httpx

from app.services.news_context import (
    GDELTNewsContextProvider,
    MacroTimelineNewsContextProvider,
    NewsContextRequest,
    NewsArticleRecord,
    article_match_score,
    build_news_query,
    build_news_queries,
    compute_context_score,
    extract_event_themes,
    get_context_window,
    get_fetch_record_limit,
    get_effective_window_days,
    get_active_news_context_provider_names,
    get_news_context_provider_names,
    get_news_context_status,
    should_query_gdelt,
)


def test_build_news_query_uses_dataset_specific_terms() -> None:
    request = NewsContextRequest(
        anomaly_id=1,
        dataset_name="Bitcoin Price",
        dataset_symbol="BTC",
        dataset_frequency="daily",
        timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    query = build_news_query(request, "English")

    assert '"bitcoin"' in query
    assert "btc" in query
    assert "sourcelang:english" in query


def test_build_news_query_uses_household_macro_terms() -> None:
    request = NewsContextRequest(
        anomaly_id=2,
        dataset_name="30-Year Fixed Rate Mortgage Average in the United States",
        dataset_symbol="MORTGAGE30US",
        dataset_frequency="weekly",
        timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    query = build_news_query(request, "English")

    assert '"mortgage rates"' in query
    assert "affordability" in query
    assert "sourcelang:english" in query


def test_build_news_query_adds_episode_hint_terms_for_clustered_request() -> None:
    request = NewsContextRequest(
        anomaly_id=3,
        dataset_name="Consumer Price Index",
        dataset_symbol="CPIAUCSL",
        dataset_frequency="monthly",
        timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        cluster_id=11,
        cluster_start_timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
        cluster_end_timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        cluster_episode_kind="cross_dataset_episode",
        cluster_dataset_symbols=("CPIAUCSL", "FEDFUNDS", "DCOILWTICO"),
    )

    query = build_news_query(request, "English")

    assert "federal reserve" in query.lower()
    assert "energy" in query.lower() or "oil" in query.lower()


def test_build_news_query_keeps_override_query_when_episode_hints_exist() -> None:
    request = NewsContextRequest(
        anomaly_id=33,
        dataset_name="Consumer Price Index",
        dataset_symbol="CPIAUCSL",
        dataset_frequency="monthly",
        timestamp=datetime(2022, 8, 1, tzinfo=timezone.utc),
        cluster_id=21,
        cluster_start_timestamp=datetime(2022, 7, 1, tzinfo=timezone.utc),
        cluster_end_timestamp=datetime(2022, 8, 1, tzinfo=timezone.utc),
        cluster_episode_kind="cross_dataset_episode",
        cluster_dataset_symbols=("CPIAUCSL", "FEDFUNDS", "DCOILWTICO"),
    )

    query = build_news_query(request, "English")

    assert '"consumer price index"' in query.lower()
    assert "price pressures" in query.lower()
    assert " OR ((" in query
    assert "interest rates" in query.lower() or "oil" in query.lower()


def test_build_news_queries_adds_dataset_specific_fallbacks() -> None:
    request = NewsContextRequest(
        anomaly_id=34,
        dataset_name="WTI Oil Price",
        dataset_symbol="DCOILWTICO",
        dataset_frequency="daily",
        timestamp=datetime(2025, 4, 4, tzinfo=timezone.utc),
    )

    queries = build_news_queries(request, "English")

    assert len(queries) >= 2
    assert "opec+" in queries[0].lower()
    assert "brent" in queries[1].lower()


def test_get_context_window_uses_episode_span_for_non_isolated_clusters() -> None:
    request = NewsContextRequest(
        anomaly_id=4,
        dataset_name="Consumer Price Index",
        dataset_symbol="CPIAUCSL",
        dataset_frequency="monthly",
        timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        cluster_id=12,
        cluster_start_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cluster_end_timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        cluster_episode_kind="cross_dataset_episode",
    )

    scope, start, end = get_context_window(request)

    assert scope == "episode"
    assert start == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 3, 1, tzinfo=timezone.utc)


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
            dataset_frequency="daily",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert captured["url"] == "https://api.gdeltproject.org/api/v2/doc/doc"
    assert captured["params"]["mode"] == "ArtList"
    assert captured["params"]["maxrecords"] == 15
    assert captured["timeout"] == 11.0
    assert articles[0].title == "Bitcoin volatility jumps"
    assert articles[0].provider == "gdelt"
    assert articles[0].published_at == datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def test_gdelt_provider_uses_episode_window_for_clustered_requests(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"articles": []}

    def mock_get(url, params, timeout):  # noqa: ANN001
        captured["params"] = params
        return MockResponse()

    monkeypatch.setattr("app.services.news_context.httpx.get", mock_get)

    provider = GDELTNewsContextProvider(
        base_url="https://api.gdeltproject.org/api/v2/doc",
        window_days=7,
        max_articles=3,
        language="English",
        timeout_seconds=11.0,
    )
    provider.fetch(
        NewsContextRequest(
            anomaly_id=1,
            dataset_name="Consumer Price Index",
            dataset_symbol="CPIAUCSL",
            dataset_frequency="monthly",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            cluster_id=2,
            cluster_start_timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            cluster_end_timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            cluster_episode_kind="cross_dataset_episode",
            cluster_dataset_symbols=("CPIAUCSL", "FEDFUNDS"),
        )
    )

    assert captured["params"]["startdatetime"] == "20260111000000"
    assert captured["params"]["enddatetime"] == "20260322235959"


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
            dataset_frequency="daily",
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
            dataset_frequency="daily",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert articles == []


def test_gdelt_provider_retries_with_fallback_query_for_oil_when_primary_returns_empty(monkeypatch) -> None:
    captured_queries: list[str] = []

    class MockResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    def mock_get(url, params, timeout):  # noqa: ANN001, ARG001
        query = params["query"]
        captured_queries.append(query)
        if len(captured_queries) == 1:
            return MockResponse({"articles": []})
        return MockResponse(
            {
                "articles": [
                    {
                        "url": "https://example.com/oil",
                        "title": "Oil prices slide as OPEC+ output and demand fears hit markets",
                        "seendate": "20250404T120000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    }
                ]
            }
        )

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
            anomaly_id=35,
            dataset_name="WTI Oil Price",
            dataset_symbol="DCOILWTICO",
            dataset_frequency="daily",
            timestamp=datetime(2025, 4, 4, tzinfo=timezone.utc),
        )
    )

    assert len(captured_queries) == 2
    assert "brent" in captured_queries[1].lower()
    assert len(articles) == 1
    assert "opec+" in articles[0].title.lower()


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
            dataset_frequency="daily",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert articles == []


def test_gdelt_provider_returns_empty_list_after_transport_timeout(monkeypatch) -> None:
    def mock_get(url, params, timeout):  # noqa: ANN001, ARG001
        request = httpx.Request("GET", "https://api.gdeltproject.org/api/v2/doc/doc")
        raise httpx.ConnectTimeout("handshake timed out", request=request)

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
            dataset_frequency="daily",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )

    assert articles == []


def test_income_titles_can_match_broader_relief_language() -> None:
    request = NewsContextRequest(
        anomaly_id=210,
        dataset_name="Real Disposable Personal Income Per Capita",
        dataset_symbol="A229RX0",
        dataset_frequency="monthly",
        timestamp=datetime(2021, 3, 1, tzinfo=timezone.utc),
    )

    score = article_match_score(
        NewsArticleRecord(
            provider="gdelt",
            article_url="https://example.com/stimulus",
            title="When to expect stimulus checks and other benefits from relief package",
            domain="example.com",
            language="English",
            source_country="United States",
            published_at=datetime(2021, 3, 9, tzinfo=timezone.utc),
            search_query="",
            relevance_rank=1,
            metadata={},
        ),
        request,
    )

    assert score >= 2


def test_extract_event_themes_finds_macro_driver_tags() -> None:
    request = NewsContextRequest(
        anomaly_id=8,
        dataset_name="Federal Funds Rate",
        dataset_symbol="FEDFUNDS",
        dataset_frequency="monthly",
        timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    themes = extract_event_themes(
        NewsArticleRecord(
            provider="gdelt",
            article_url="https://example.com/fed",
            title="Federal Reserve signals rate cut after banking stress spreads",
            domain="example.com",
            language="English",
            source_country="United States",
            published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
            search_query="",
            relevance_rank=1,
            metadata={},
        ),
        request,
    )

    assert "fed_policy" in themes
    assert "banking_stress" in themes


def test_context_score_prefers_thematic_registry_context_over_generic_article() -> None:
    request = NewsContextRequest(
        anomaly_id=9,
        dataset_name="Federal Funds Rate",
        dataset_symbol="FEDFUNDS",
        dataset_frequency="monthly",
        timestamp=datetime(2022, 3, 1, tzinfo=timezone.utc),
        cluster_id=7,
        cluster_start_timestamp=datetime(2022, 3, 1, tzinfo=timezone.utc),
        cluster_end_timestamp=datetime(2022, 3, 4, tzinfo=timezone.utc),
        cluster_episode_kind="cross_dataset_episode",
        cluster_dataset_symbols=("FEDFUNDS", "DCOILWTICO", "SP500"),
    )

    generic_article = NewsArticleRecord(
        provider="gdelt",
        article_url="https://example.com/article",
        title="Markets move as investors react",
        domain="example.com",
        language="English",
        source_country="United States",
        published_at=datetime(2022, 3, 2, tzinfo=timezone.utc),
        search_query="markets",
        relevance_rank=1,
        metadata={},
    )
    registry_article = NewsArticleRecord(
        provider="macro_timeline",
        article_url="https://example.com/timeline",
        title="IMF Blog: How War in Ukraine Is Reverberating Across World's Regions",
        domain="imf.org",
        language="English",
        source_country="United States",
        published_at=datetime(2022, 3, 15, tzinfo=timezone.utc),
        search_query="macro_timeline:ukraine_war_energy_inflation_2022",
        relevance_rank=1,
        metadata={
            "source_kind": "historical_event_registry",
            "historical_event_summary": "Russia's invasion of Ukraine intensified a geopolitical shock.",
            "event_themes": ["geopolitics", "energy_shock", "inflation"],
        },
    )

    generic_score = compute_context_score(generic_article, request, event_themes=[])
    registry_score = compute_context_score(
        registry_article,
        request,
        event_themes=["geopolitics", "energy_shock", "inflation"],
    )

    assert registry_score > generic_score


def test_household_macro_uses_wider_frequency_aware_windows() -> None:
    monthly_request = NewsContextRequest(
        anomaly_id=210,
        dataset_name="Real Disposable Personal Income Per Capita",
        dataset_symbol="A229RX0",
        dataset_frequency="monthly",
        timestamp=datetime(2021, 3, 1, tzinfo=timezone.utc),
    )
    weekly_request = NewsContextRequest(
        anomaly_id=189,
        dataset_name="30-Year Fixed Rate Mortgage Average in the United States",
        dataset_symbol="MORTGAGE30US",
        dataset_frequency="weekly",
        timestamp=datetime(2016, 11, 17, tzinfo=timezone.utc),
    )

    assert get_effective_window_days(monthly_request, 7) == 21
    assert get_effective_window_days(weekly_request, 7) == 14


def test_fetch_record_limit_requests_deeper_raw_pool() -> None:
    assert get_fetch_record_limit(3) == 15
    assert get_fetch_record_limit(5) == 25


def test_macro_timeline_provider_returns_curated_household_context() -> None:
    provider = MacroTimelineNewsContextProvider(max_articles=5)

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=209,
            dataset_name="Real Disposable Personal Income Per Capita",
            dataset_symbol="A229RX0",
            dataset_frequency="monthly",
            timestamp=datetime(2020, 4, 1, tzinfo=timezone.utc),
        )
    )

    assert any("Economic impact payments" in article.title for article in articles)
    assert articles[0].provider == "macro_timeline"
    assert any(article.domain == "irs.gov" for article in articles)


def test_macro_timeline_provider_returns_1991_gulf_war_backdrop_for_cpi() -> None:
    provider = MacroTimelineNewsContextProvider(max_articles=5)

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=302,
            dataset_name="Consumer Price Index",
            dataset_symbol="CPIAUCSL",
            dataset_frequency="monthly",
            timestamp=datetime(1991, 2, 1, tzinfo=timezone.utc),
        )
    )

    assert len(articles) == 1
    assert "Out of the Ballpark" in articles[0].title
    assert articles[0].domain == "imf.org"
    assert articles[0].metadata["historical_event_id"] == "gulf_war_oil_recession_1990_1991"
    assert articles[0].metadata["historical_event_type"] == "oil_recession_shock"
    assert articles[0].metadata["source_kind"] == "historical_event_registry"
    assert articles[0].metadata["event_themes"][0] == "geopolitics"


def test_macro_timeline_provider_returns_inflation_build_up_backdrop_for_1965_fed() -> None:
    provider = MacroTimelineNewsContextProvider(max_articles=5)

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=304,
            dataset_name="Federal Funds Rate",
            dataset_symbol="FEDFUNDS",
            dataset_frequency="monthly",
            timestamp=datetime(1965, 12, 1, tzinfo=timezone.utc),
        )
    )

    assert len(articles) == 1
    assert articles[0].metadata["historical_event_id"] == "great_inflation_build_up_1964_1978"
    assert articles[0].metadata["historical_event_type"] == "inflation_regime"
    assert "buildup" in articles[0].metadata["historical_event_summary"].lower()


def test_macro_timeline_provider_returns_housing_boom_backdrop_for_case_shiller() -> None:
    provider = MacroTimelineNewsContextProvider(max_articles=5)

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=303,
            dataset_name="Case-Shiller U.S. National Home Price Index",
            dataset_symbol="CSUSHPISA",
            dataset_frequency="monthly",
            timestamp=datetime(2003, 8, 1, tzinfo=timezone.utc),
        )
    )

    assert len(articles) == 1
    assert "Great Recession and Its Aftermath" in articles[0].title
    assert articles[0].domain == "federalreservehistory.org"
    assert "housing expansion" in articles[0].metadata["historical_event_summary"].lower()


def test_macro_timeline_provider_can_match_cluster_context_not_just_primary_dataset() -> None:
    provider = MacroTimelineNewsContextProvider(max_articles=5)

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=301,
            dataset_name="Bitcoin Price",
            dataset_symbol="BTC",
            dataset_frequency="daily",
            timestamp=datetime(2022, 3, 4, tzinfo=timezone.utc),
            cluster_id=50,
            cluster_start_timestamp=datetime(2022, 3, 1, tzinfo=timezone.utc),
            cluster_end_timestamp=datetime(2022, 3, 4, tzinfo=timezone.utc),
            cluster_episode_kind="cross_dataset_episode",
            cluster_dataset_symbols=("BTC", "DCOILWTICO", "SP500"),
        )
    )

    assert len(articles) >= 1
    assert any("Ukraine" in article.title for article in articles)


def test_macro_timeline_provider_returns_reopening_backdrop_for_2020_cpi() -> None:
    provider = MacroTimelineNewsContextProvider(max_articles=5)

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=305,
            dataset_name="Consumer Price Index",
            dataset_symbol="CPIAUCSL",
            dataset_frequency="monthly",
            timestamp=datetime(2020, 7, 1, tzinfo=timezone.utc),
        )
    )

    assert len(articles) >= 1
    matching_article = next(
        article
        for article in articles
        if article.metadata["historical_event_id"] == "post_pandemic_inflation_and_tightening_2021_2023"
    )
    assert "reopening" in matching_article.metadata["historical_event_summary"].lower()


def test_macro_timeline_provider_returns_april_2025_oil_backdrop() -> None:
    provider = MacroTimelineNewsContextProvider(max_articles=5)

    articles = provider.fetch(
        NewsContextRequest(
            anomaly_id=306,
            dataset_name="WTI Oil Price",
            dataset_symbol="DCOILWTICO",
            dataset_frequency="daily",
            timestamp=datetime(2025, 4, 4, tzinfo=timezone.utc),
            cluster_id=60,
            cluster_start_timestamp=datetime(2025, 4, 4, tzinfo=timezone.utc),
            cluster_end_timestamp=datetime(2025, 4, 4, tzinfo=timezone.utc),
            cluster_episode_kind="cross_dataset_episode",
            cluster_dataset_symbols=("DCOILWTICO", "SP500"),
        )
    )

    assert len(articles) >= 1
    matching_article = next(
        article
        for article in articles
        if article.metadata["historical_event_id"] == "trade_war_and_opec_supply_shock_2025"
    )
    assert "opec" in matching_article.metadata["historical_event_summary"].lower()
    assert matching_article.domain == "eia.gov"


def test_all_series_use_hybrid_provider_names_by_default() -> None:
    request = NewsContextRequest(
        anomaly_id=183,
        dataset_name="Case-Shiller U.S. National Home Price Index",
        dataset_symbol="CSUSHPISA",
        dataset_frequency="monthly",
        timestamp=datetime(2010, 2, 1, tzinfo=timezone.utc),
    )

    provider_names = get_news_context_provider_names(request)

    assert provider_names == ["gdelt", "macro_timeline"]


def test_non_household_series_also_use_hybrid_provider_names_by_default() -> None:
    request = NewsContextRequest(
        anomaly_id=91,
        dataset_name="Bitcoin Price",
        dataset_symbol="BTC",
        dataset_frequency="daily",
        timestamp=datetime(2026, 2, 6, tzinfo=timezone.utc),
    )

    provider_names = get_news_context_provider_names(request)

    assert provider_names == ["gdelt", "macro_timeline"]


def test_old_non_household_series_skip_gdelt_execution(monkeypatch) -> None:
    request = NewsContextRequest(
        anomaly_id=100,
        dataset_name="Federal Funds Rate",
        dataset_symbol="FEDFUNDS",
        dataset_frequency="monthly",
        timestamp=datetime(1965, 12, 1, tzinfo=timezone.utc),
    )

    monkeypatch.setattr("app.services.news_context.settings.gdelt_max_anomaly_age_days", 3650)

    assert should_query_gdelt(request) is False
    assert get_active_news_context_provider_names(request) == ["macro_timeline"]


def test_old_household_series_fall_back_to_macro_timeline_provider(monkeypatch) -> None:
    request = NewsContextRequest(
        anomaly_id=183,
        dataset_name="Case-Shiller U.S. National Home Price Index",
        dataset_symbol="CSUSHPISA",
        dataset_frequency="monthly",
        timestamp=datetime(2010, 2, 1, tzinfo=timezone.utc),
    )

    monkeypatch.setattr("app.services.news_context.settings.gdelt_max_anomaly_age_days", 3650)

    assert should_query_gdelt(request) is False
    assert get_active_news_context_provider_names(request) == ["macro_timeline"]


def test_news_context_status_reports_hybrid_provider_label_for_household_series() -> None:
    status = get_news_context_status(
        dataset_symbol="A229RX0",
        dataset_frequency="monthly",
        has_articles=False,
        attempted_provider_names=["gdelt", "macro_timeline"],
    )

    assert status["provider"] == "gdelt+macro_timeline"
    assert status["status"] == "limited_coverage"


def test_news_context_status_reports_actual_article_provider_when_available() -> None:
    status = get_news_context_status(
        dataset_symbol="A229RX0",
        dataset_frequency="monthly",
        has_articles=True,
        attempted_provider_names=["gdelt", "macro_timeline"],
        article_provider_names=["macro_timeline"],
    )

    assert status["provider"] == "macro_timeline"
    assert status["note"] == "Stored citations are available from the curated macro timeline."
