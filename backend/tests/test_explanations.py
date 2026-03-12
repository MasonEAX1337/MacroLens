from datetime import datetime, timezone

from app.services.explanations import (
    CorrelationEvidence,
    ExplanationContext,
    RulesBasedExplanationProvider,
)


def build_context(correlations: list[CorrelationEvidence]) -> ExplanationContext:
    return ExplanationContext(
        anomaly_id=1,
        dataset_id=10,
        dataset_name="Bitcoin Price",
        timestamp=datetime(2024, 3, 1, tzinfo=timezone.utc),
        severity_score=3.7,
        direction="down",
        detection_method="z_score",
        correlations=correlations,
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
    assert result.evidence["dataset_name"] == "Bitcoin Price"


def test_rules_based_provider_handles_missing_correlations() -> None:
    provider = RulesBasedExplanationProvider()
    result = provider.generate(build_context([]))

    assert "No strong cross-dataset relationship was stored" in result.generated_text
    assert "Confidence is limited" in result.generated_text
