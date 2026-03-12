import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass(frozen=True)
class CorrelationEvidence:
    related_dataset_id: int
    related_dataset_name: str
    correlation_score: float
    lag_days: int
    method: str


@dataclass(frozen=True)
class ExplanationContext:
    anomaly_id: int
    dataset_id: int
    dataset_name: str
    timestamp: datetime
    severity_score: float
    direction: str | None
    detection_method: str
    correlations: list[CorrelationEvidence]


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


class RulesBasedExplanationProvider:
    provider_name = "rules_based"

    def __init__(self, model_name: str = "macro-template-v1") -> None:
        self.model_name = model_name

    def generate(self, context: ExplanationContext) -> GeneratedExplanation:
        event_date = context.timestamp.strftime("%B %d, %Y")
        move_word = "increase" if context.direction == "up" else "decline" if context.direction == "down" else "move"

        if context.correlations:
            top = context.correlations[0]
            lag_phrase = "the same time" if top.lag_days == 0 else f"about {abs(top.lag_days)} day(s) later" if top.lag_days > 0 else f"about {abs(top.lag_days)} day(s) earlier"
            relationship = "moved in the same direction as" if top.correlation_score >= 0 else "moved opposite to"
            correlation_text = (
                f"The strongest related signal was {top.related_dataset_name}, which {relationship} "
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

        generated_text = (
            f"{context.dataset_name} showed an unusual {move_word} on {event_date} "
            f"with a severity score of {context.severity_score:.2f} using {context.detection_method} detection. "
            f"{correlation_text} {uncertainty}"
        )
        return GeneratedExplanation(
            provider=self.provider_name,
            model=self.model_name,
            generated_text=generated_text,
            evidence={
                "dataset_name": context.dataset_name,
                "timestamp": context.timestamp.isoformat(),
                "severity_score": context.severity_score,
                "direction": context.direction,
                "detection_method": context.detection_method,
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
            },
        )


def get_explanation_provider() -> ExplanationProvider:
    provider_name = settings.explanation_provider.strip().lower()
    if provider_name == "rules_based":
        return RulesBasedExplanationProvider(model_name=settings.explanation_model)
    raise ValueError(f"Unsupported explanation provider: {settings.explanation_provider}")


def load_explanation_context(db: Session, anomaly_id: int) -> ExplanationContext | None:
    anomaly_query = text(
        """
        SELECT
            a.id AS anomaly_id,
            a.dataset_id,
            d.name AS dataset_name,
            a.timestamp,
            a.severity_score,
            a.direction,
            a.detection_method
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
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

    return ExplanationContext(
        anomaly_id=int(anomaly["anomaly_id"]),
        dataset_id=int(anomaly["dataset_id"]),
        dataset_name=str(anomaly["dataset_name"]),
        timestamp=anomaly["timestamp"],
        severity_score=float(anomaly["severity_score"]),
        direction=anomaly["direction"],
        detection_method=str(anomaly["detection_method"]),
        correlations=correlations,
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
