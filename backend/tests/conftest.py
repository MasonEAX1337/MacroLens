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
from app.services.clustering import run_clustering_for_all_anomalies
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
                    anomaly_cluster_members,
                    anomaly_clusters,
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
            "lag_days": 10,
            "method": "pearson_pct_change",
        },
    )
    target_anomaly_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method)
                RETURNING id
                """
            ),
            {
                "dataset_id": related_dataset_id,
                "timestamp": datetime(2026, 2, 16, tzinfo=timezone.utc),
                "severity_score": 2.91,
                "direction": "down",
                "detection_method": "z_score",
            },
        ).scalar_one()
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
            "metadata": '{"retrieval_scope":"episode","timing_relation":"during","context_window_start":"2026-02-06T00:00:00+00:00","context_window_end":"2026-02-16T00:00:00+00:00"}',
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
    run_clustering_for_all_anomalies(db_session, window_days=7)
    db_session.commit()

    return {
        "dataset_id": primary_dataset_id,
        "related_dataset_id": related_dataset_id,
        "anomaly_id": anomaly_id,
        "target_anomaly_id": target_anomaly_id,
    }


@pytest.fixture()
def seeded_leading_indicators(db_session: Session) -> dict[str, int]:
    target_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="cpi",
            name="Consumer Price Index",
            symbol="CPIAUCSL",
            source="FRED",
            description="Consumer Price Index for All Urban Consumers.",
            frequency="monthly",
        ),
    )
    oil_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="wti",
            name="WTI Oil Price",
            symbol="DCOILWTICO",
            source="FRED",
            description="Crude Oil Prices: West Texas Intermediate.",
            frequency="daily",
        ),
    )
    fed_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="fed_funds",
            name="Federal Funds Rate",
            symbol="FEDFUNDS",
            source="FRED",
            description="Effective Federal Funds Rate.",
            frequency="monthly",
        ),
    )

    anomaly_one_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method)
                RETURNING id
                """
            ),
            {
                "dataset_id": target_dataset_id,
                "timestamp": datetime(2025, 1, 15, tzinfo=timezone.utc),
                "severity_score": 3.1,
                "direction": "up",
                "detection_method": "z_score",
            },
        ).scalar_one()
    )
    anomaly_two_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method)
                RETURNING id
                """
            ),
            {
                "dataset_id": target_dataset_id,
                "timestamp": datetime(2025, 4, 15, tzinfo=timezone.utc),
                "severity_score": 3.0,
                "direction": "up",
                "detection_method": "z_score",
            },
        ).scalar_one()
    )
    anomaly_three_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method)
                RETURNING id
                """
            ),
            {
                "dataset_id": target_dataset_id,
                "timestamp": datetime(2025, 4, 18, tzinfo=timezone.utc),
                "severity_score": 2.7,
                "direction": "up",
                "detection_method": "change_point",
            },
        ).scalar_one()
    )

    db_session.execute(
        text(
            """
            INSERT INTO correlations (anomaly_id, related_dataset_id, correlation_score, lag_days, method)
            VALUES
                (:anomaly_one_id, :oil_dataset_id, 0.72, -20, 'pearson_pct_change'),
                (:anomaly_one_id, :fed_dataset_id, 0.44, -9, 'pearson_pct_change'),
                (:anomaly_two_id, :oil_dataset_id, 0.81, -18, 'pearson_pct_change'),
                (:anomaly_two_id, :fed_dataset_id, 0.45, -11, 'pearson_pct_change'),
                (:anomaly_three_id, :oil_dataset_id, 0.60, -25, 'pearson_pct_change')
            """
        ),
        {
            "anomaly_one_id": anomaly_one_id,
            "anomaly_two_id": anomaly_two_id,
            "anomaly_three_id": anomaly_three_id,
            "oil_dataset_id": oil_dataset_id,
            "fed_dataset_id": fed_dataset_id,
        },
    )

    run_clustering_for_all_anomalies(db_session, window_days=7)
    db_session.commit()

    return {
        "dataset_id": target_dataset_id,
        "oil_dataset_id": oil_dataset_id,
        "fed_dataset_id": fed_dataset_id,
    }


@pytest.fixture()
def seeded_episode_filter_graph(db_session: Session) -> dict[str, int]:
    cpi_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="cpi",
            name="Consumer Price Index",
            symbol="CPIAUCSL",
            source="FRED",
            description="Consumer Price Index for All Urban Consumers.",
            frequency="monthly",
        ),
    )
    house_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="house_prices",
            name="Case-Shiller U.S. National Home Price Index",
            symbol="CSUSHPISA",
            source="FRED",
            description="U.S. National Home Price Index.",
            frequency="monthly",
        ),
    )
    fed_dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="fed_funds",
            name="Federal Funds Rate",
            symbol="FEDFUNDS",
            source="FRED",
            description="Effective Federal Funds Rate.",
            frequency="monthly",
        ),
    )

    bridge_anomaly_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method, metadata)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method, CAST(:metadata AS JSONB))
                RETURNING id
                """
            ),
            {
                "dataset_id": cpi_dataset_id,
                "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "severity_score": 0.65,
                "direction": "up",
                "detection_method": "change_point",
                "metadata": '{"delta_mean": 0.001, "transformed_value": 0.0004, "transform": "percent_change"}',
            },
        ).scalar_one()
    )
    fed_anomaly_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method, metadata)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method, CAST(:metadata AS JSONB))
                RETURNING id
                """
            ),
            {
                "dataset_id": fed_dataset_id,
                "timestamp": datetime(2025, 1, 3, tzinfo=timezone.utc),
                "severity_score": 2.1,
                "direction": "up",
                "detection_method": "z_score",
                "metadata": "{}",
            },
        ).scalar_one()
    )
    suppressed_anomaly_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method, metadata)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method, CAST(:metadata AS JSONB))
                RETURNING id
                """
            ),
            {
                "dataset_id": house_dataset_id,
                "timestamp": datetime(2025, 3, 1, tzinfo=timezone.utc),
                "severity_score": 0.7,
                "direction": "down",
                "detection_method": "change_point",
                "metadata": '{"delta_mean": 0.002, "transformed_value": 0.001, "transform": "percent_change"}',
            },
        ).scalar_one()
    )

    run_clustering_for_all_anomalies(db_session, window_days=7)
    db_session.commit()

    return {
        "cpi_dataset_id": cpi_dataset_id,
        "house_dataset_id": house_dataset_id,
        "bridge_anomaly_id": bridge_anomaly_id,
        "fed_anomaly_id": fed_anomaly_id,
        "suppressed_anomaly_id": suppressed_anomaly_id,
    }
