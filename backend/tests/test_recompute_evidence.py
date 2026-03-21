import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text

from app.services.clustering import run_clustering_for_all_anomalies
from app.services.ingestion import DatasetDefinition, upsert_dataset


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "pipeline" / "recompute_evidence.py"
SPEC = importlib.util.spec_from_file_location("recompute_evidence_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
recompute_evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recompute_evidence)


def seed_clustered_pair(db_session):  # noqa: ANN001
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

    primary_anomaly_id = int(
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
    related_anomaly_id = int(
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
                "timestamp": datetime(2026, 2, 9, tzinfo=timezone.utc),
                "severity_score": 2.91,
                "direction": "down",
                "detection_method": "z_score",
            },
        ).scalar_one()
    )
    run_clustering_for_all_anomalies(db_session, window_days=7)
    db_session.commit()

    return {
        "primary_dataset_id": primary_dataset_id,
        "related_dataset_id": related_dataset_id,
        "primary_anomaly_id": primary_anomaly_id,
        "related_anomaly_id": related_anomaly_id,
    }


def test_load_datasets_filters_dataset_symbols(db_session) -> None:  # noqa: ANN001
    seed_clustered_pair(db_session)

    datasets = recompute_evidence.load_datasets(db_session, dataset_symbols=["btc"])

    assert len(datasets) == 1
    assert datasets[0]["symbol"] == "BTC"


def test_resolve_news_context_targets_only_selected_dataset_anomalies(db_session) -> None:  # noqa: ANN001
    seeded = seed_clustered_pair(db_session)

    anomaly_ids = recompute_evidence.resolve_news_context_target_anomaly_ids(
        db_session,
        [seeded["primary_dataset_id"]],
    )

    assert anomaly_ids == [seeded["primary_anomaly_id"]]


def test_resolve_explanation_targets_expand_to_cluster_scope_when_clustering_ran(db_session) -> None:  # noqa: ANN001
    seeded = seed_clustered_pair(db_session)

    scoped_ids = recompute_evidence.resolve_explanation_target_anomaly_ids(
        db_session,
        [seeded["primary_dataset_id"]],
        clustering_ran=True,
    )

    assert scoped_ids == [seeded["related_anomaly_id"], seeded["primary_anomaly_id"]]


def test_resolve_explanation_targets_stay_dataset_scoped_without_reclustering(db_session) -> None:  # noqa: ANN001
    seeded = seed_clustered_pair(db_session)

    scoped_ids = recompute_evidence.resolve_explanation_target_anomaly_ids(
        db_session,
        [seeded["primary_dataset_id"]],
        clustering_ran=False,
    )

    assert scoped_ids == [seeded["primary_anomaly_id"]]


def test_recompute_correlations_uses_dataset_scoped_runner(monkeypatch) -> None:
    class DummyBegin:
        def __enter__(self):  # noqa: ANN204
            return object()

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return False

    calls: list[int] = []

    monkeypatch.setattr(recompute_evidence.SessionLocal, "begin", lambda: DummyBegin())
    monkeypatch.setattr(
        recompute_evidence,
        "run_correlation_for_dataset",
        lambda session, dataset_id: calls.append(dataset_id) or dataset_id,
    )

    total = recompute_evidence.recompute_correlations(
        [
            {"id": 1, "symbol": "BTC"},
            {"id": 2, "symbol": "CPIAUCSL"},
        ]
    )

    assert calls == [1, 2]
    assert total == 3


def test_main_reconciles_clusters_after_correlation_rebuild(monkeypatch) -> None:
    class DummySessionContext:
        def __enter__(self):  # noqa: ANN204
            return object()

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return False

    class DummySessionLocal:
        def __call__(self):  # noqa: ANN204
            return DummySessionContext()

        def begin(self):  # noqa: ANN204
            return DummySessionContext()

    clustering_calls: list[str] = []

    monkeypatch.setattr(
        recompute_evidence,
        "parse_args",
        lambda: SimpleNamespace(
            dataset_symbols=["CPIAUCSL"],
            skip_anomaly_detection=True,
            skip_clustering=False,
            skip_correlation=False,
            skip_news_context=True,
            skip_explanations=True,
        ),
    )
    monkeypatch.setattr(recompute_evidence, "SessionLocal", DummySessionLocal())
    monkeypatch.setattr(
        recompute_evidence,
        "load_datasets",
        lambda session, dataset_symbols=None: [  # noqa: ARG005
            {"id": 1, "symbol": "CPIAUCSL", "frequency": "monthly"}
        ],
    )
    monkeypatch.setattr(
        recompute_evidence,
        "resolve_news_context_target_anomaly_ids",
        lambda session, dataset_ids: [101],  # noqa: ARG005
    )
    monkeypatch.setattr(
        recompute_evidence,
        "recompute_correlations",
        lambda datasets=None: 4,  # noqa: ARG005
    )
    monkeypatch.setattr(
        recompute_evidence,
        "_run_clustering",
        lambda: clustering_calls.append("cluster") or SimpleNamespace(cluster_count=2, member_count=3),
    )

    recompute_evidence.main()

    assert clustering_calls == ["cluster", "cluster"]
