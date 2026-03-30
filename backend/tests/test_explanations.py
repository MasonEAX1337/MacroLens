from datetime import datetime, timezone

from app.services.explanations import (
    CorrelationEvidence,
    ExplanationContext,
    FallbackExplanationProvider,
    GeminiExplanationProvider,
    NewsContextEvidence,
    build_openai_input,
    OpenAIExplanationProvider,
    RulesBasedExplanationProvider,
)


def build_context(
    correlations: list[CorrelationEvidence],
    news_context: list[NewsContextEvidence] | None = None,
) -> ExplanationContext:
    return ExplanationContext(
        anomaly_id=1,
        dataset_id=10,
        dataset_name="Bitcoin Price",
        dataset_symbol="BTC",
        dataset_frequency="daily",
        timestamp=datetime(2024, 3, 1, tzinfo=timezone.utc),
        severity_score=3.7,
        direction="down",
        detection_method="z_score",
        cluster_span_days=0,
        cluster_anomaly_count=1,
        cluster_dataset_count=1,
        cluster_frequency_mix="daily_only",
        cluster_episode_kind="isolated_signal",
        cluster_quality_band="low",
        correlations=correlations,
        news_context=news_context or [],
    )


def test_rules_based_provider_mentions_top_correlation() -> None:
    provider = RulesBasedExplanationProvider()
    context = build_context(
        [
            CorrelationEvidence(
                related_dataset_id=20,
                related_dataset_name="S&P 500",
                correlation_score=0.62,
                lag_days=2,
                method="pearson_pct_change",
            )
        ]
    )

    result = provider.generate(context)

    assert result.provider == "rules_based"
    assert "Bitcoin Price" in result.generated_text
    assert "S&P 500" in result.generated_text
    assert "correlation 0.62" in result.generated_text
    assert "low quality" in result.generated_text
    assert result.evidence["dataset_name"] == "Bitcoin Price"


def test_rules_based_provider_handles_missing_correlations() -> None:
    provider = RulesBasedExplanationProvider()
    result = provider.generate(build_context([]))

    assert "No strong cross-dataset relationship was stored" in result.generated_text
    assert "Confidence is limited" in result.generated_text


def test_rules_based_provider_mentions_household_news_provider_limits_when_empty() -> None:
    provider = RulesBasedExplanationProvider()
    context = ExplanationContext(
        anomaly_id=2,
        dataset_id=20,
        dataset_name="Real Disposable Personal Income Per Capita",
        dataset_symbol="A229RX0",
        dataset_frequency="monthly",
        timestamp=datetime(2021, 3, 1, tzinfo=timezone.utc),
        severity_score=2.8,
        direction="up",
        detection_method="z_score",
        cluster_span_days=30,
        cluster_anomaly_count=2,
        cluster_dataset_count=1,
        cluster_frequency_mix="monthly_only",
        cluster_episode_kind="single_dataset_wave",
        cluster_quality_band="low",
        correlations=[],
        news_context=[],
    )

    result = provider.generate(context)

    assert "broad household macro topics are still weak with the current news provider" in result.generated_text


def test_rules_based_provider_mentions_news_context_when_available() -> None:
    provider = RulesBasedExplanationProvider()
    result = provider.generate(
        build_context(
            [],
            news_context=[
                NewsContextEvidence(
                    provider="gdelt",
                    article_url="https://example.com/article",
                    title="Bitcoin Selloff Deepens as Risk Assets Weaken",
                    domain="example.com",
                    language="English",
                    source_country="United States",
                    published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
                    search_query='("bitcoin") sourcelang:english',
                    relevance_rank=1,
                    retrieval_scope="episode",
                    timing_relation="during",
                    context_window_start=datetime(2024, 2, 28, tzinfo=timezone.utc),
                    context_window_end=datetime(2024, 3, 2, tzinfo=timezone.utc),
                    event_themes=["market_stress"],
                    primary_theme="market_stress",
                    context_score=0.71,
                )
            ],
        )
    )

    assert "Likely real-world context" in result.generated_text
    assert "market stress" in result.generated_text
    assert "Bitcoin Selloff Deepens as Risk Assets Weaken" in result.generated_text
    assert "example.com" in result.generated_text


def test_rules_based_provider_prefers_macro_timeline_as_primary_driver_context() -> None:
    provider = RulesBasedExplanationProvider()
    result = provider.generate(
        build_context(
            [],
            news_context=[
                NewsContextEvidence(
                    provider="gdelt",
                    article_url="https://example.com/article",
                    title="Oil prices jump as traders react",
                    domain="example.com",
                    language="English",
                    source_country="United States",
                    published_at=datetime(2022, 3, 4, tzinfo=timezone.utc),
                    search_query='("oil prices") sourcelang:english',
                    relevance_rank=1,
                    retrieval_scope="episode",
                    timing_relation="during",
                    context_window_start=datetime(2022, 3, 1, tzinfo=timezone.utc),
                    context_window_end=datetime(2022, 3, 4, tzinfo=timezone.utc),
                    event_themes=["energy_shock"],
                    primary_theme="energy_shock",
                ),
                NewsContextEvidence(
                    provider="macro_timeline",
                    article_url="https://www.imf.org/en/Blogs/Articles/2022/03/15/how-war-in-ukraine-is-reverberating-across-worlds-regions",
                    title="IMF Blog: How War in Ukraine Is Reverberating Across World's Regions",
                    domain="imf.org",
                    language="English",
                    source_country="United States",
                    published_at=datetime(2022, 3, 15, tzinfo=timezone.utc),
                    search_query="macro_timeline:ukraine_war_energy_inflation_2022",
                    relevance_rank=1,
                    retrieval_scope="curated_timeline",
                    timing_relation="during",
                    context_window_start=datetime(2022, 3, 1, tzinfo=timezone.utc),
                    context_window_end=datetime(2022, 3, 4, tzinfo=timezone.utc),
                    event_themes=["geopolitics", "energy_shock"],
                    primary_theme="geopolitics",
                    source_kind="historical_event_registry",
                    historical_event_id="ukraine_war_energy_inflation_2022",
                    historical_event_summary="Russia's invasion of Ukraine intensified a geopolitical shock that pushed up energy and inflation pressures while reshaping global risk sentiment and policy expectations.",
                    historical_event_type="geopolitical_shock",
                    historical_event_regions=["Global", "Europe", "United States"],
                    historical_event_confidence=0.95,
                    context_score=0.94,
                ),
            ],
        )
    )

    assert "broader historical backdrop" in result.generated_text
    assert "How War in Ukraine Is Reverberating Across World's Regions" in result.generated_text
    assert "Russia's invasion of Ukraine intensified a geopolitical shock" in result.generated_text


def test_rules_based_provider_prefers_higher_scored_context_even_when_provider_is_weaker() -> None:
    provider = RulesBasedExplanationProvider()
    result = provider.generate(
        build_context(
            [],
            news_context=[
                NewsContextEvidence(
                    provider="macro_timeline",
                    article_url="https://example.com/timeline",
                    title="Broad regime background",
                    domain="example.com",
                    language="English",
                    source_country="United States",
                    published_at=datetime(2022, 3, 15, tzinfo=timezone.utc),
                    search_query="macro_timeline:test",
                    relevance_rank=1,
                    retrieval_scope="curated_timeline",
                    timing_relation="after",
                    context_window_start=datetime(2022, 3, 1, tzinfo=timezone.utc),
                    context_window_end=datetime(2022, 3, 4, tzinfo=timezone.utc),
                    event_themes=["geopolitics"],
                    primary_theme="geopolitics",
                    source_kind="historical_event_registry",
                    historical_event_id="test_regime",
                    historical_event_summary="Very broad regime context.",
                    historical_event_type="regime",
                    historical_event_regions=["Global"],
                    historical_event_confidence=0.4,
                    context_score=0.55,
                ),
                NewsContextEvidence(
                    provider="gdelt",
                    article_url="https://example.com/live",
                    title="Fed weighs response to banking stress",
                    domain="example.com",
                    language="English",
                    source_country="United States",
                    published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
                    search_query='("federal reserve" AND "banking stress")',
                    relevance_rank=1,
                    retrieval_scope="episode",
                    timing_relation="during",
                    context_window_start=datetime(2024, 3, 1, tzinfo=timezone.utc),
                    context_window_end=datetime(2024, 3, 2, tzinfo=timezone.utc),
                    event_themes=["banking_stress", "fed_policy"],
                    primary_theme="banking_stress",
                    context_score=0.89,
                ),
            ],
        )
    )

    assert "Fed weighs response to banking stress" in result.generated_text


def test_openai_provider_builds_responses_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "id": "resp_test_123",
                "output_text": "Bitcoin moved sharply lower and the strongest stored evidence points to adjacent cross-market stress. The correlation evidence is suggestive rather than causal.",
            }

    def mock_post(url, headers, json, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return MockResponse()

    monkeypatch.setattr("app.services.explanations.httpx.post", mock_post)

    provider = OpenAIExplanationProvider(
        api_key="test-key",
        model_name="gpt-4.1-mini",
        base_url="https://api.openai.com/v1",
        timeout_seconds=15.0,
    )
    result = provider.generate(build_context([]))

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "gpt-4.1-mini"
    assert "supplied evidence" in captured["json"]["instructions"]
    assert '"dataset_name": "Bitcoin Price"' in captured["json"]["input"]
    assert captured["timeout"] == 15.0
    assert result.provider == "openai"
    assert result.model == "gpt-4.1-mini"
    assert result.evidence["provider_response_id"] == "resp_test_123"


def test_fallback_provider_uses_rules_based_when_primary_fails(monkeypatch) -> None:
    class FailingProvider:
        provider_name = "openai"
        model_name = "gpt-4.1-mini"

        def generate(self, context):  # noqa: ANN001
            raise RuntimeError("provider unavailable")

    fallback = RulesBasedExplanationProvider()
    provider = FallbackExplanationProvider(FailingProvider(), fallback)

    result = provider.generate(build_context([]))

    assert result.provider == "rules_based"
    assert result.evidence["fallback"]["requested_provider"] == "openai"
    assert result.evidence["fallback"]["reason"] == "RuntimeError"


def test_fallback_provider_handles_missing_openai_key() -> None:
    provider = FallbackExplanationProvider(
        OpenAIExplanationProvider(
            api_key="",
            model_name="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
            timeout_seconds=15.0,
        ),
        RulesBasedExplanationProvider(),
    )

    result = provider.generate(build_context([]))

    assert result.provider == "rules_based"
    assert result.evidence["fallback"]["reason"] == "ValueError"


def test_gemini_provider_builds_generate_content_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Bitcoin moved sharply lower and the strongest stored evidence points to adjacent cross-market stress. The correlation evidence is suggestive rather than causal.",
                                }
                            ]
                        }
                    }
                ],
                "responseId": "gemini_resp_123",
                "modelVersion": "gemini-3.1-flash-lite-preview",
                "usageMetadata": {"promptTokenCount": 123, "candidatesTokenCount": 44},
            }

    def mock_post(url, headers, json, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return MockResponse()

    monkeypatch.setattr("app.services.explanations.httpx.post", mock_post)

    provider = GeminiExplanationProvider(
        api_key="gemini-key",
        model_name="gemini-3.1-flash-lite-preview",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds=12.0,
    )
    result = provider.generate(build_context([]))

    assert (
        captured["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "gemini-key"
    assert captured["json"]["system_instruction"]["parts"][0]["text"].startswith("Explain the supplied economic anomaly")
    assert captured["json"]["contents"][0]["role"] == "user"
    assert '"dataset_name": "Bitcoin Price"' in captured["json"]["contents"][0]["parts"][0]["text"]
    assert captured["timeout"] == 12.0
    assert result.provider == "gemini"
    assert result.model == "gemini-3.1-flash-lite-preview"
    assert result.evidence["provider_response_id"] == "gemini_resp_123"


def test_fallback_provider_handles_missing_gemini_key() -> None:
    provider = FallbackExplanationProvider(
        GeminiExplanationProvider(
            api_key="",
            model_name="gemini-3.1-flash-lite-preview",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            timeout_seconds=12.0,
        ),
        RulesBasedExplanationProvider(),
    )

    result = provider.generate(build_context([]))

    assert result.provider == "rules_based"
    assert result.evidence["fallback"]["reason"] == "ValueError"


def test_hosted_provider_input_includes_explicit_lag_interpretation() -> None:
    context = build_context(
        [
            CorrelationEvidence(
                related_dataset_id=20,
                related_dataset_name="WTI Oil Price",
                correlation_score=-0.65,
                lag_days=29,
                method="pearson_pct_change",
            )
        ]
    )

    payload = build_openai_input(context)

    assert '"lag_days": 29' in payload
    assert '"timing_class": "lagging"' in payload
    assert '"lag_interpretation": "moved about 29 day(s) after the anomaly"' in payload
    assert "Respect the supplied lag interpretation exactly." in payload
    assert "Do not present lagging evidence as a likely cause of the anomaly." in payload
    assert "If cluster_quality_band is low, describe the episode context as limited rather than broad." in payload


def test_hosted_provider_input_includes_news_context() -> None:
    payload = build_openai_input(
        build_context(
            [],
            news_context=[
                NewsContextEvidence(
                    provider="gdelt",
                    article_url="https://example.com/cpi",
                    title="Inflation Pressures Remain Elevated",
                    domain="example.com",
                    language="English",
                    source_country="United States",
                    published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
                    search_query='("inflation" OR "consumer price index") sourcelang:english',
                    relevance_rank=1,
                    retrieval_scope="episode",
                    timing_relation="during",
                    context_window_start=datetime(2024, 3, 1, tzinfo=timezone.utc),
                    context_window_end=datetime(2024, 3, 3, tzinfo=timezone.utc),
                    event_themes=["inflation"],
                    primary_theme="inflation",
                )
            ],
        )
    )

    assert '"news_context": [' in payload
    assert '"title": "Inflation Pressures Remain Elevated"' in payload
    assert '"provider": "gdelt"' in payload
    assert '"timing_class": "concurrent"' in payload
    assert '"timing_interpretation": "on the same day as the anomaly"' in payload
    assert '"retrieval_scope": "episode"' in payload
    assert '"timing_relation": "during"' in payload
    assert '"primary_theme": "inflation"' in payload


def test_hosted_provider_input_treats_macro_timeline_as_context_not_primary_driver() -> None:
    payload = build_openai_input(
        build_context(
            [
                CorrelationEvidence(
                    related_dataset_id=20,
                    related_dataset_name="30-Year Fixed Rate Mortgage Average in the United States",
                    correlation_score=-0.91,
                    lag_days=-6,
                    method="pearson_pct_change",
                )
            ],
            news_context=[
                NewsContextEvidence(
                    provider="macro_timeline",
                    article_url="https://www.irs.gov/newsroom/economic-impact-payments-what-you-need-to-know",
                    title="IRS: Economic impact payments: What you need to know",
                    domain="irs.gov",
                    language="English",
                    source_country="United States",
                    published_at=datetime(2020, 3, 30, tzinfo=timezone.utc),
                    search_query="macro_timeline:economic_impact_payments_2020",
                    relevance_rank=1,
                    retrieval_scope="curated_timeline",
                    timing_relation="during",
                    context_window_start=datetime(2020, 3, 1, tzinfo=timezone.utc),
                    context_window_end=datetime(2020, 4, 1, tzinfo=timezone.utc),
                    event_themes=["fiscal_policy"],
                    primary_theme="fiscal_policy",
                    source_kind="historical_event_registry",
                    historical_event_id="economic_impact_payments_2020",
                    historical_event_summary="Pandemic relief payments temporarily boosted household disposable income during the first COVID shock.",
                    historical_event_type="fiscal_support",
                    historical_event_regions=["United States"],
                    historical_event_confidence=0.95,
                )
            ],
        )
    )

    assert '"provider": "macro_timeline"' in payload
    assert '"source_kind": "historical_event_registry"' in payload
    assert '"historical_event_id": "economic_impact_payments_2020"' in payload
    assert "Lead with likely real-world context when the supplied news or timeline evidence is credible." in payload
    assert "Treat macro_timeline items as historical regime context, not as the primary driver unless no stronger structured evidence exists." in payload
