import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.news_context import HOUSEHOLD_NEWS_SYMBOLS


@dataclass(frozen=True)
class CorrelationEvidence:
    related_dataset_id: int
    related_dataset_name: str
    correlation_score: float
    lag_days: int
    method: str


@dataclass(frozen=True)
class NewsContextEvidence:
    provider: str
    article_url: str
    title: str
    domain: str | None
    language: str | None
    source_country: str | None
    published_at: datetime | None
    search_query: str
    relevance_rank: int
    retrieval_scope: str | None = None
    timing_relation: str | None = None
    context_window_start: datetime | None = None
    context_window_end: datetime | None = None
    event_themes: list[str] = None
    primary_theme: str | None = None
    source_kind: str | None = None
    historical_event_id: str | None = None
    historical_event_summary: str | None = None
    historical_event_type: str | None = None
    historical_event_regions: list[str] = None
    historical_event_confidence: float | None = None
    context_score: float | None = None


@dataclass(frozen=True)
class ExplanationContext:
    anomaly_id: int
    dataset_id: int
    dataset_name: str
    dataset_symbol: str
    dataset_frequency: str
    timestamp: datetime
    severity_score: float
    direction: str | None
    detection_method: str
    cluster_span_days: int
    cluster_anomaly_count: int
    cluster_dataset_count: int
    cluster_frequency_mix: str
    cluster_episode_kind: str
    cluster_quality_band: str
    correlations: list[CorrelationEvidence]
    news_context: list[NewsContextEvidence]


@dataclass(frozen=True)
class GeneratedExplanation:
    provider: str
    model: str
    generated_text: str
    evidence: dict[str, object]


class ExplanationProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        ...


def build_explanation_evidence(context: ExplanationContext) -> dict[str, object]:
    return {
        "dataset_name": context.dataset_name,
        "dataset_symbol": context.dataset_symbol,
        "dataset_frequency": context.dataset_frequency,
        "timestamp": context.timestamp.isoformat(),
        "severity_score": context.severity_score,
        "direction": context.direction,
        "detection_method": context.detection_method,
        "episode_context": {
            "cluster_span_days": context.cluster_span_days,
            "cluster_anomaly_count": context.cluster_anomaly_count,
            "cluster_dataset_count": context.cluster_dataset_count,
            "cluster_frequency_mix": context.cluster_frequency_mix,
            "cluster_episode_kind": context.cluster_episode_kind,
            "cluster_quality_band": context.cluster_quality_band,
        },
        "correlations": [
            {
                "related_dataset_id": item.related_dataset_id,
                "related_dataset_name": item.related_dataset_name,
                "correlation_score": item.correlation_score,
                "lag_days": item.lag_days,
                "method": item.method,
            }
            for item in context.correlations
        ],
        "news_context": [
            {
                "provider": item.provider,
                "article_url": item.article_url,
                "title": item.title,
                "domain": item.domain,
                "language": item.language,
                "source_country": item.source_country,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "timing_class": classify_article_timing(item.published_at, context.timestamp),
                "timing_interpretation": describe_article_timing(item.published_at, context.timestamp),
                "search_query": item.search_query,
                "relevance_rank": item.relevance_rank,
                "retrieval_scope": item.retrieval_scope,
                "timing_relation": item.timing_relation,
                "context_window_start": item.context_window_start.isoformat() if item.context_window_start else None,
                "context_window_end": item.context_window_end.isoformat() if item.context_window_end else None,
                "event_themes": item.event_themes or [],
                "primary_theme": item.primary_theme,
                "source_kind": item.source_kind,
                "historical_event_id": item.historical_event_id,
                "historical_event_summary": item.historical_event_summary,
                "historical_event_type": item.historical_event_type,
                "historical_event_regions": item.historical_event_regions or [],
                "historical_event_confidence": item.historical_event_confidence,
                "context_score": item.context_score,
            }
            for item in context.news_context
        ],
    }


def describe_lag_days(lag_days: int) -> str:
    if lag_days == 0:
        return "moved on the same day as the anomaly"
    if lag_days > 0:
        return f"moved about {lag_days} day(s) after the anomaly"
    return f"moved about {abs(lag_days)} day(s) before the anomaly"


def classify_lag_days(lag_days: int) -> str:
    if lag_days == 0:
        return "concurrent"
    if lag_days > 0:
        return "lagging"
    return "leading"


def describe_article_timing(published_at: datetime | None, anomaly_timestamp: datetime) -> str:
    if published_at is None:
        return "at an unknown time relative to the anomaly"

    day_offset = (published_at.date() - anomaly_timestamp.date()).days
    if day_offset == 0:
        return "on the same day as the anomaly"
    if day_offset > 0:
        return f"about {day_offset} day(s) after the anomaly"
    return f"about {abs(day_offset)} day(s) before the anomaly"


def classify_article_timing(published_at: datetime | None, anomaly_timestamp: datetime) -> str:
    if published_at is None:
        return "unknown"

    day_offset = (published_at.date() - anomaly_timestamp.date()).days
    if day_offset == 0:
        return "concurrent"
    if day_offset > 0:
        return "lagging"
    return "leading"


def choose_primary_context_item(context: ExplanationContext) -> NewsContextEvidence | None:
    if not context.news_context:
        return None

    def sort_key(item: NewsContextEvidence) -> tuple[float, int, int, int, int]:
        timing_relation = item.timing_relation or "unknown"
        if timing_relation == "during":
            timing_rank = 0
        elif timing_relation == "before":
            timing_rank = 1
        elif timing_relation == "after":
            timing_rank = 3
        else:
            timing_rank = 4
        provider_rank = 2
        if item.provider == "macro_timeline":
            provider_rank = 0
        elif item.provider == "gdelt":
            provider_rank = 1
        theme_rank = 0 if item.primary_theme else 1
        relevance_rank = item.relevance_rank if item.relevance_rank > 0 else 999
        context_score = -(item.context_score if item.context_score is not None else 0.0)
        return (context_score, timing_rank, provider_rank, theme_rank, relevance_rank)

    return sorted(context.news_context, key=sort_key)[0]


def describe_context_timing(item: NewsContextEvidence, context: ExplanationContext) -> str:
    if item.timing_relation == "before":
        return "before the episode window"
    if item.timing_relation == "during":
        return "during the episode window"
    if item.timing_relation == "after":
        return "after the episode window"
    return describe_article_timing(item.published_at, context.timestamp)


def format_primary_theme(theme: str | None) -> str | None:
    if not theme:
        return None
    return theme.replace("_", " ")


class RulesBasedExplanationProvider:
    provider_name = "rules_based"

    def __init__(self, model_name: str = "macro-template-v1") -> None:
        self.model_name = model_name

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        event_date = context.timestamp.strftime("%B %d, %Y")
        move_word = "increase" if context.direction == "up" else "decline" if context.direction == "down" else "move"
        primary_context = choose_primary_context_item(context)
        if context.cluster_episode_kind == "cross_dataset_episode":
            episode_text = (
                f"This anomaly sits inside a broader cross-dataset episode spanning about {context.cluster_span_days + 1} day(s) "
                f"across {context.cluster_dataset_count} dataset(s)."
            )
        elif context.cluster_episode_kind == "single_dataset_wave":
            episode_text = (
                f"This anomaly is part of a single-dataset wave spanning about {context.cluster_span_days + 1} day(s)."
            )
        else:
            episode_text = "This is currently an isolated stored signal rather than a broader cross-dataset episode."
        if context.cluster_quality_band == "low":
            episode_quality_text = (
                "The stored episode context is low quality, so broad macro interpretation should be treated cautiously."
            )
        elif context.cluster_quality_band == "medium":
            episode_quality_text = (
                "The stored episode context is moderate, which gives broader context without making this a strong regime-level episode."
            )
        else:
            episode_quality_text = "The stored episode context is relatively broad for the current evidence graph."

        if primary_context:
            primary_theme = format_primary_theme(primary_context.primary_theme)
            if primary_context.provider == "macro_timeline":
                historical_summary = primary_context.historical_event_summary
                context_text = (
                    f"Likely real-world context around this episode includes the broader historical backdrop "
                    f"'{primary_context.title}'. "
                    f"{historical_summary if historical_summary else 'This provides broader regime context for the move.'} "
                    f"{f'The strongest registry theme here is {primary_theme}. ' if primary_theme else ''}"
                    f"This context was matched {describe_context_timing(primary_context, context)}."
                )
            else:
                context_text = (
                    f"Likely real-world context around this episode points to"
                    f"{f' {primary_theme}' if primary_theme else ' broader macro developments'}, "
                    f"with reporting such as "
                    f"'{primary_context.title}'"
                    f"{f' from {primary_context.domain}' if primary_context.domain else ''}, "
                    f"appearing {describe_context_timing(primary_context, context)}."
                )
        else:
            context_text = ""

        if context.correlations:
            top = context.correlations[0]
            lag_phrase = "the same time" if top.lag_days == 0 else f"about {abs(top.lag_days)} day(s) later" if top.lag_days > 0 else f"about {abs(top.lag_days)} day(s) earlier"
            relationship = "moved in the same direction as" if top.correlation_score >= 0 else "moved opposite to"
            correlation_text = (
                f"Supporting market structure included {top.related_dataset_name}, which {relationship} "
                f"{context.dataset_name} around {lag_phrase} "
                f"(correlation {top.correlation_score:.2f})."
            )
            uncertainty = (
                "This is a correlation-based explanation rather than proof of causality, so it should be read as supporting evidence."
            )
        else:
            correlation_text = (
                "No strong cross-dataset relationship was stored for this anomaly, so the explanation is based only on the detected move itself."
            )
            uncertainty = "Confidence is limited because the event does not yet have strong supporting correlations."

        if not context.news_context:
            if context.dataset_symbol in HOUSEHOLD_NEWS_SYMBOLS:
                news_text = (
                    "No supporting news context was stored for this anomaly, and broad household macro topics are still weak with the current news provider."
                )
            elif context.dataset_frequency in {"weekly", "monthly"}:
                news_text = (
                    "No supporting news context was stored for this anomaly, which is common for slower weekly and monthly series."
                )
            else:
                news_text = "No supporting news context was stored for this anomaly."
        else:
            news_text = ""

        generated_text = (
            f"{context.dataset_name} showed an unusual {move_word} on {event_date} "
            f"with a severity score of {context.severity_score:.2f} using {context.detection_method} detection. "
            f"{context_text} {episode_text} {episode_quality_text} {correlation_text} {news_text} {uncertainty}"
        )
        return GeneratedExplanation(
            provider=self.provider_name,
            model=self.model_name,
            generated_text=generated_text,
            evidence=build_explanation_evidence(context),
        )


def build_openai_instructions() -> str:
    return (
        "You explain macroeconomic anomalies using only the supplied evidence. "
        "Write 3 to 4 concise sentences. "
        "Do not claim causality as certainty. "
        "Do not introduce outside facts that are not present in the evidence. "
        "If the evidence is weak or correlations are sparse, say so clearly. "
        "If credible real-world context exists, lead with it before discussing market relationships. "
        "Do not describe lagging evidence as a likely driver of the anomaly. "
        "If the supplied cluster_quality_band is low, do not frame the anomaly as part of a broad macro episode. "
        "Treat macro_timeline items as broad historical background, not as the strongest direct evidence. "
        "Avoid phrases like statistically significant, impossible to identify, or may be associated with unless the supplied evidence directly supports them."
    )


def build_openai_input(context: ExplanationContext) -> str:
    move_direction = context.direction or "unknown"
    payload = {
        "task": "Explain the likely drivers of this economic anomaly using only the supplied evidence.",
        "event": {
            "dataset_name": context.dataset_name,
            "timestamp": context.timestamp.isoformat(),
            "severity_score": context.severity_score,
            "direction": move_direction,
            "detection_method": context.detection_method,
        },
        "episode_context": {
            "cluster_span_days": context.cluster_span_days,
            "cluster_anomaly_count": context.cluster_anomaly_count,
            "cluster_dataset_count": context.cluster_dataset_count,
            "cluster_frequency_mix": context.cluster_frequency_mix,
            "cluster_episode_kind": context.cluster_episode_kind,
            "cluster_quality_band": context.cluster_quality_band,
        },
        "correlations": [
            {
                "related_dataset_name": item.related_dataset_name,
                "correlation_score": round(item.correlation_score, 6),
                "lag_days": item.lag_days,
                "timing_class": classify_lag_days(item.lag_days),
                "lag_interpretation": describe_lag_days(item.lag_days),
                "method": item.method,
            }
            for item in context.correlations
        ],
        "news_context": [
            {
                "title": item.title,
                "domain": item.domain,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "timing_class": classify_article_timing(item.published_at, context.timestamp),
                "timing_interpretation": describe_article_timing(item.published_at, context.timestamp),
                "timing_relation": item.timing_relation,
                "retrieval_scope": item.retrieval_scope,
                "context_window_start": item.context_window_start.isoformat() if item.context_window_start else None,
                "context_window_end": item.context_window_end.isoformat() if item.context_window_end else None,
                "event_themes": item.event_themes or [],
                "primary_theme": item.primary_theme,
                "source_kind": item.source_kind,
                "historical_event_id": item.historical_event_id,
                "historical_event_summary": item.historical_event_summary,
                "historical_event_type": item.historical_event_type,
                "historical_event_regions": item.historical_event_regions or [],
                "historical_event_confidence": item.historical_event_confidence,
                "context_score": item.context_score,
                "language": item.language,
                "source_country": item.source_country,
                "search_query": item.search_query,
                "provider": item.provider,
                "article_url": item.article_url,
            }
            for item in context.news_context
        ],
        "output_requirements": [
            "Use plain English.",
            "Lead with likely real-world context when the supplied news or timeline evidence is credible.",
            "State uncertainty when evidence is limited.",
            "Do not mention unavailable news or events.",
            "Respect the supplied lag interpretation exactly.",
            "Do not present lagging evidence as a likely cause of the anomaly.",
            "Use correlations as supporting structure rather than the main driver when context exists.",
            "If cluster_quality_band is low, describe the episode context as limited rather than broad.",
            "If stored news context exists, use it as contextual evidence and cite it by title or source.",
            "Treat lagging news context as retrospective context, not proof of the original driver.",
            "Treat macro_timeline items as historical regime context, not as the primary driver unless no stronger structured evidence exists.",
        ],
    }
    return json.dumps(payload, indent=2)


def extract_openai_output_text(payload: dict[str, object]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = payload.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                if content_item.get("type") == "output_text":
                    text_value = content_item.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        chunks.append(text_value.strip())
        if chunks:
            return "\n".join(chunks)

    raise ValueError("OpenAI response did not contain output text.")


def build_gemini_system_instruction() -> str:
    return (
        "Explain the supplied economic anomaly using only the provided evidence. "
        "Write 3 to 4 concise sentences. "
        "Lead with likely real-world context when credible contextual evidence exists. "
        "Do not invent external events or facts. "
        "Do not claim causality as certainty. "
        "If the evidence is weak, state that clearly. "
        "Do not describe lagging evidence as a likely driver of the anomaly. "
        "If the supplied cluster_quality_band is low, do not frame the anomaly as part of a broad macro episode. "
        "Treat macro_timeline items as broad historical background, not as the strongest direct evidence. "
        "Avoid phrases like statistically significant, impossible to identify, or may be associated with unless the supplied evidence directly supports them."
    )


def extract_gemini_output_text(payload: dict[str, object]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response did not contain candidates.")

    texts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text_value = part.get("text")
            if isinstance(text_value, str) and text_value.strip():
                texts.append(text_value.strip())

    if texts:
        return "\n".join(texts)

    raise ValueError("Gemini response did not contain text output.")


class OpenAIExplanationProvider:
    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI explanation provider.")
        response = httpx.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "instructions": build_openai_instructions(),
                "input": build_openai_input(context),
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        generated_text = extract_openai_output_text(payload)
        evidence = build_explanation_evidence(context)
        evidence["generation_mode"] = "llm"
        evidence["provider_response_id"] = payload.get("id")

        return GeneratedExplanation(
            provider=self.provider_name,
            model=self.model_name,
            generated_text=generated_text,
            evidence=evidence,
        )


class GeminiExplanationProvider:
    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini explanation provider.")

        response = httpx.post(
            f"{self.base_url}/models/{self.model_name}:generateContent",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "system_instruction": {
                    "parts": [
                        {
                            "text": build_gemini_system_instruction(),
                        }
                    ]
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": build_openai_input(context),
                            }
                        ],
                    }
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        generated_text = extract_gemini_output_text(payload)
        evidence = build_explanation_evidence(context)
        evidence["generation_mode"] = "llm"
        evidence["provider_response_id"] = payload.get("responseId")
        evidence["provider_model_version"] = payload.get("modelVersion")
        evidence["usage_metadata"] = payload.get("usageMetadata")

        return GeneratedExplanation(
            provider=self.provider_name,
            model=self.model_name,
            generated_text=generated_text,
            evidence=evidence,
        )


class FallbackExplanationProvider:
    def __init__(self, primary: ExplanationProvider, fallback: ExplanationProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.provider_name = primary.provider_name
        self.model_name = primary.model_name

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        try:
            return self.primary.generate(context)
        except Exception as exc:  # noqa: BLE001
            fallback_result = self.fallback.generate(context)
            fallback_evidence = dict(fallback_result.evidence)
            fallback_evidence["fallback"] = {
                "requested_provider": self.primary.provider_name,
                "requested_model": self.primary.model_name,
                "reason": type(exc).__name__,
            }
            return replace(fallback_result, evidence=fallback_evidence)


def create_provider_by_name(provider_name: str) -> ExplanationProvider:
    normalized = provider_name.strip().lower()
    if normalized == "rules_based":
        return RulesBasedExplanationProvider(model_name=settings.explanation_model)
    if normalized == "openai":
        return OpenAIExplanationProvider(
            api_key=settings.openai_api_key,
            model_name=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    if normalized == "gemini":
        return GeminiExplanationProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
            base_url=settings.gemini_base_url,
            timeout_seconds=settings.gemini_timeout_seconds,
        )
    raise ValueError(f"Unsupported explanation provider: {provider_name}")


def get_explanation_provider() -> ExplanationProvider:
    fallback_name = settings.explanation_fallback_provider.strip().lower()
    primary = create_provider_by_name(settings.explanation_provider)

    if (
        settings.explanation_allow_fallback
        and fallback_name
        and fallback_name != settings.explanation_provider.strip().lower()
    ):
        fallback = create_provider_by_name(fallback_name)
        return FallbackExplanationProvider(primary, fallback)

    return primary


def load_explanation_context(db: Session, anomaly_id: int) -> ExplanationContext | None:
    anomaly_query = text(
        """
        SELECT
            a.id AS anomaly_id,
            a.dataset_id,
            d.name AS dataset_name,
            d.symbol AS dataset_symbol,
            d.frequency AS dataset_frequency,
            a.timestamp,
            a.severity_score,
            a.direction,
            a.detection_method,
            COALESCE(ac.span_days, 0) AS cluster_span_days,
            COALESCE(ac.anomaly_count, 1) AS cluster_anomaly_count,
            COALESCE(ac.dataset_count, 1) AS cluster_dataset_count,
            COALESCE(ac.frequency_mix, d.frequency || '_only') AS cluster_frequency_mix,
            COALESCE(ac.episode_kind, 'isolated_signal') AS cluster_episode_kind,
            COALESCE(ac.quality_band, 'low') AS cluster_quality_band
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        LEFT JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
        LEFT JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
        WHERE a.id = :anomaly_id
        """
    )
    anomaly = db.execute(anomaly_query, {"anomaly_id": anomaly_id}).mappings().first()
    if anomaly is None:
        return None

    correlation_query = text(
        """
        SELECT
            c.related_dataset_id,
            d.name AS related_dataset_name,
            c.correlation_score,
            c.lag_days,
            c.method
        FROM correlations AS c
        JOIN datasets AS d ON d.id = c.related_dataset_id
        WHERE c.anomaly_id = :anomaly_id
        ORDER BY ABS(c.correlation_score) DESC, c.related_dataset_id ASC
        """
    )
    correlation_rows = db.execute(correlation_query, {"anomaly_id": anomaly_id}).mappings().all()
    correlations = [CorrelationEvidence(**row) for row in correlation_rows]

    news_query = text(
        """
        SELECT
            provider,
            article_url,
            title,
            domain,
            language,
            source_country,
            published_at,
            search_query,
            relevance_rank,
            metadata ->> 'retrieval_scope' AS retrieval_scope,
            metadata ->> 'timing_relation' AS timing_relation,
            CAST(metadata ->> 'context_window_start' AS TIMESTAMPTZ) AS context_window_start,
            CAST(metadata ->> 'context_window_end' AS TIMESTAMPTZ) AS context_window_end,
            COALESCE(metadata -> 'event_themes', '[]'::jsonb) AS event_themes,
            metadata ->> 'primary_theme' AS primary_theme,
            metadata ->> 'source_kind' AS source_kind,
            metadata ->> 'historical_event_id' AS historical_event_id,
            metadata ->> 'historical_event_summary' AS historical_event_summary,
            metadata ->> 'historical_event_type' AS historical_event_type,
            COALESCE(metadata -> 'historical_event_regions', '[]'::jsonb) AS historical_event_regions,
            CAST(metadata ->> 'historical_event_confidence' AS DOUBLE PRECISION) AS historical_event_confidence,
            CAST(metadata ->> 'context_score' AS DOUBLE PRECISION) AS context_score
        FROM news_context
        WHERE anomaly_id = :anomaly_id
        ORDER BY
            CAST(COALESCE(metadata ->> 'context_score', '0') AS DOUBLE PRECISION) DESC,
            CASE provider
                WHEN 'macro_timeline' THEN 0
                WHEN 'gdelt' THEN 1
                ELSE 2
            END ASC,
            relevance_rank ASC,
            published_at DESC,
            id ASC
        """
    )
    news_rows = db.execute(news_query, {"anomaly_id": anomaly_id}).mappings().all()
    news_context = [NewsContextEvidence(**row) for row in news_rows]

    return ExplanationContext(
        anomaly_id=int(anomaly["anomaly_id"]),
        dataset_id=int(anomaly["dataset_id"]),
        dataset_name=str(anomaly["dataset_name"]),
        dataset_symbol=str(anomaly["dataset_symbol"]),
        dataset_frequency=str(anomaly["dataset_frequency"]),
        timestamp=anomaly["timestamp"],
        severity_score=float(anomaly["severity_score"]),
        direction=anomaly["direction"],
        detection_method=str(anomaly["detection_method"]),
        cluster_span_days=int(anomaly["cluster_span_days"]),
        cluster_anomaly_count=int(anomaly["cluster_anomaly_count"]),
        cluster_dataset_count=int(anomaly["cluster_dataset_count"]),
        cluster_frequency_mix=str(anomaly["cluster_frequency_mix"]),
        cluster_episode_kind=str(anomaly["cluster_episode_kind"]),
        cluster_quality_band=str(anomaly["cluster_quality_band"]),
        correlations=correlations,
        news_context=news_context,
    )


def replace_explanation(db: Session, anomaly_id: int, explanation: GeneratedExplanation) -> int:
    delete_query = text(
        """
        DELETE FROM explanations
        WHERE anomaly_id = :anomaly_id
          AND provider = :provider
          AND model = :model
        """
    )
    db.execute(
        delete_query,
        {
            "anomaly_id": anomaly_id,
            "provider": explanation.provider,
            "model": explanation.model,
        },
    )

    insert_query = text(
        """
        INSERT INTO explanations (anomaly_id, provider, model, generated_text, evidence)
        VALUES (:anomaly_id, :provider, :model, :generated_text, CAST(:evidence AS JSONB))
        """
    )
    db.execute(
        insert_query,
        {
            "anomaly_id": anomaly_id,
            "provider": explanation.provider,
            "model": explanation.model,
            "generated_text": explanation.generated_text,
            "evidence": json.dumps(explanation.evidence),
        },
    )
    return 1


def load_anomaly_ids(db: Session) -> list[int]:
    query = text(
        """
        SELECT id
        FROM anomalies
        ORDER BY timestamp DESC
        """
    )
    return [int(item) for item in db.execute(query).scalars().all()]


def run_explanation_for_anomaly(db: Session, anomaly_id: int) -> int:
    context = load_explanation_context(db, anomaly_id)
    if context is None:
        return 0
    provider = get_explanation_provider()
    explanation = provider.generate(context)
    return replace_explanation(db, anomaly_id, explanation)


def run_explanations_for_all_anomalies(db: Session) -> int:
    inserted = 0
    for anomaly_id in load_anomaly_ids(db):
        inserted += run_explanation_for_anomaly(db, anomaly_id)
    return inserted
