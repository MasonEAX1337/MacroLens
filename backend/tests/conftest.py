from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.main import app
from app.services.ingestion import DataPointRecord, DatasetDefinition, upsert_data_points, upsert_dataset


TEST_DATABASE_NAME = "macrolens_integration_test"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def _admin_url() -> URL:
    return make_url("postgresql+psycopg://postgres:postgres@localhost:5432/postgres")


def _test_url() -> URL:
    return _admin_url().set(database=TEST_DATABASE_NAME)


def _apply_schema(engine) -> None:  # noqa: ANN001
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.raw_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
        connection.commit()


@pytest.fixture(scope="session")
def integration_engine():
    admin_engine = create_engine(_admin_url(), future=True, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE_NAME},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    except SQLAlchemyError as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL not available for integration tests: {exc}")

    engine = create_engine(_test_url(), future=True, pool_pre_ping=True)
    _apply_schema(engine)
    yield engine
    engine.dispose()
    admin_engine.dispose()


@pytest.fixture()
def db_session(integration_engine) -> Generator[Session, None, None]:
    session_local = sessionmaker(bind=integration_engine, autoflush=False, autocommit=False, future=True)
    with session_local.begin() as session:
        session.execute(
            text(
                """
                TRUNCATE TABLE
                    explanations,
                    news_context,
                    correlations,
                    anomalies,
                    data_points,
                    datasets,
                    ingestion_runs
                RESTART IDENTITY CASCADE
                """
            )
        )
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_event_graph(db_session: Session) -> dict[str, int]:
    primary_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="bitcoin",
            name="Bitcoin Price",
            symbol="BTC",
            source="CoinGecko",
            description="Bitcoin spot price in USD.",
            frequency="daily",
        ),
    )
    related_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="sp500",
            name="S&P 500 Index",
            symbol="SP500",
            source="FRED",
            description="S&P 500 stock market index.",
            frequency="daily",
        ),
    )

    upsert_data_points(
        db_session,
        primary_dataset_id,
        [
            DataPointRecord(timestamp=datetime(2026, 2, day, tzinfo=timezone.utc), value=value)
            for day, value in [(1, 104000.0), (2, 101500.0), (3, 99500.0)]
        ],
    )
    upsert_data_points(
        db_session,
        related_dataset_id,
        [
            DataPointRecord(timestamp=datetime(2026, 1, day, tzinfo=timezone.utc), value=value)
            for day, value in [(31, 6100.0), (30, 6075.0), (29, 6050.0)]
        ],
    )

    anomaly_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method)
                RETURNING id
                """
            ),
            {
                "dataset_id": primary_dataset_id,
                "timestamp": datetime(2026, 2, 6, tzinfo=timezone.utc),
                "severity_score": 3.24,
                "direction": "down",
                "detection_method": "z_score",
            },
        ).scalar_one()
    )
    db_session.execute(
        text(
            """
            INSERT INTO correlations (anomaly_id, related_dataset_id, correlation_score, lag_days, method)
            VALUES (:anomaly_id, :related_dataset_id, :correlation_score, :lag_days, :method)
            """
        ),
        {
            "anomaly_id": anomaly_id,
            "related_dataset_id": related_dataset_id,
            "correlation_score": 0.66,
            "lag_days": -1,
            "method": "pearson_pct_change",
        },
    )
    db_session.execute(
        text(
            """
            INSERT INTO news_context (
                anomaly_id,
                provider,
                article_url,
                title,
                domain,
                language,
                source_country,
                published_at,
                search_query,
                relevance_rank,
                metadata
            )
            VALUES (
                :anomaly_id,
                :provider,
                :article_url,
                :title,
                :domain,
                :language,
                :source_country,
                :published_at,
                :search_query,
                :relevance_rank,
                CAST(:metadata AS JSONB)
            )
            """
        ),
        {
            "anomaly_id": anomaly_id,
            "provider": "gdelt",
            "article_url": "https://example.com/bitcoin-selloff",
            "title": "Bitcoin Selloff Deepens as Risk Assets Weaken",
            "domain": "example.com",
            "language": "English",
            "source_country": "United States",
            "published_at": datetime(2026, 2, 6, 12, 0, tzinfo=timezone.utc),
            "search_query": '("bitcoin" OR btc OR crypto) sourcelang:english',
            "relevance_rank": 1,
            "metadata": "{}",
        },
    )
    db_session.execute(
        text(
            """
            INSERT INTO explanations (anomaly_id, provider, model, generated_text, evidence)
            VALUES (:anomaly_id, :provider, :model, :generated_text, CAST(:evidence AS JSONB))
            """
        ),
        {
            "anomaly_id": anomaly_id,
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite-preview",
            "generated_text": "The strongest stored relationship was the S&P 500 Index, and a cited article provided contextual evidence for broader risk-off pressure.",
            "evidence": "{}",
        },
    )
    db_session.commit()

    return {
        "dataset_id": primary_dataset_id,
        "related_dataset_id": related_dataset_id,
        "anomaly_id": anomaly_id,
    }
