import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.anomaly_detection import run_detection_for_dataset
from app.services.clustering import run_clustering_for_all_anomalies
from app.services.correlation_engine import run_correlation_for_dataset
from app.services.correlation_engine import run_correlation_for_all_anomalies
from app.services.explanations import load_anomaly_ids as load_explanation_anomaly_ids
from app.services.explanations import run_explanation_for_anomaly
from app.services.news_context import load_anomaly_ids as load_news_anomaly_ids
from app.services.news_context import run_news_context_for_anomaly


@dataclass(frozen=True)
class StageTiming:
    name: str
    seconds: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute MacroLens evidence from stored data points without re-ingesting source datasets."
    )
    parser.add_argument(
        "--dataset",
        action="append",
        dest="dataset_symbols",
        help="Dataset symbol to recompute. Repeat for multiple symbols, for example --dataset CPIAUCSL --dataset CSUSHPISA.",
    )
    parser.add_argument(
        "--skip-anomaly-detection",
        action="store_true",
        help="Reuse the current anomaly set and start from downstream stages.",
    )
    parser.add_argument(
        "--skip-clustering",
        action="store_true",
        help="Recompute anomalies but skip rebuilding anomaly clusters.",
    )
    parser.add_argument(
        "--skip-correlation",
        action="store_true",
        help="Recompute anomalies and clusters but skip cross-dataset correlations.",
    )
    parser.add_argument(
        "--skip-news-context",
        action="store_true",
        help="Recompute anomalies, clusters, and correlations but skip news-context retrieval.",
    )
    parser.add_argument(
        "--skip-explanations",
        action="store_true",
        help="Recompute all structured evidence but skip explanation generation.",
    )
    return parser.parse_args()


def load_datasets(
    db: Session,
    *,
    dataset_symbols: list[str] | None = None,
) -> list[dict[str, object]]:
    rows = db.execute(
        text(
            """
            SELECT id, name, symbol, frequency
            FROM datasets
            ORDER BY id ASC
            """
        )
    ).mappings().all()
    datasets = [dict(row) for row in rows]
    if not dataset_symbols:
        return datasets

    normalized = {symbol.strip().upper() for symbol in dataset_symbols if symbol.strip()}
    filtered = [row for row in datasets if str(row["symbol"]).upper() in normalized]
    found = {str(row["symbol"]).upper() for row in filtered}
    missing = sorted(normalized - found)
    if missing:
        raise ValueError(f"Unknown dataset symbol(s): {', '.join(missing)}")
    return filtered


def build_dataset_ids(datasets: list[dict[str, object]]) -> list[int]:
    return [int(item["id"]) for item in datasets]


def load_anomaly_ids_for_dataset_ids(
    db: Session,
    dataset_ids: list[int],
) -> list[int]:
    if not dataset_ids:
        return []

    query = text(
        """
        SELECT a.id
        FROM anomalies AS a
        WHERE a.dataset_id = ANY(:dataset_ids)
        ORDER BY a.timestamp DESC, a.id DESC
        """
    )
    rows = db.execute(query, {"dataset_ids": dataset_ids}).scalars().all()
    return [int(row) for row in rows]


def load_cluster_scoped_anomaly_ids(
    db: Session,
    dataset_ids: list[int],
) -> list[int]:
    if not dataset_ids:
        return []

    query = text(
        """
        SELECT DISTINCT a.id
        FROM anomaly_cluster_members AS target_members
        JOIN anomaly_clusters AS clusters ON clusters.id = target_members.cluster_id
        JOIN anomaly_cluster_members AS all_members ON all_members.cluster_id = clusters.id
        JOIN anomalies AS a ON a.id = all_members.anomaly_id
        WHERE target_members.anomaly_id IN (
            SELECT source_anomalies.id
            FROM anomalies AS source_anomalies
            WHERE source_anomalies.dataset_id = ANY(:dataset_ids)
        )
        ORDER BY a.id DESC
        """
    )
    rows = db.execute(query, {"dataset_ids": dataset_ids}).scalars().all()
    return [int(row) for row in rows]


def resolve_news_context_target_anomaly_ids(
    db: Session,
    dataset_ids: list[int],
) -> list[int]:
    return load_anomaly_ids_for_dataset_ids(db, dataset_ids)


def resolve_explanation_target_anomaly_ids(
    db: Session,
    dataset_ids: list[int],
    *,
    clustering_ran: bool,
) -> list[int]:
    if clustering_ran:
        return load_cluster_scoped_anomaly_ids(db, dataset_ids)
    return load_anomaly_ids_for_dataset_ids(db, dataset_ids)


def recompute_anomalies(datasets: list[dict[str, object]]) -> int:
    total_inserted = 0
    for dataset in datasets:
        with SessionLocal.begin() as session:
            inserted = run_detection_for_dataset(session, int(dataset["id"]))
        total_inserted += inserted
        print(
            f"anomalies: dataset {dataset['symbol']} ({dataset['frequency']}) stored {inserted} row(s)"
        )
    return total_inserted


def recompute_correlations(datasets: list[dict[str, object]] | None = None) -> int:
    if not datasets:
        with SessionLocal.begin() as session:
            return run_correlation_for_all_anomalies(session)

    total_inserted = 0
    for dataset in datasets:
        with SessionLocal.begin() as session:
            inserted = run_correlation_for_dataset(session, int(dataset["id"]))
        total_inserted += inserted
        print(f"correlations: dataset {dataset['symbol']} stored {inserted} relationship row(s)")
    return total_inserted


def recompute_news_context(anomaly_ids: list[int] | None = None) -> int:
    if anomaly_ids is None:
        with SessionLocal() as session:
            anomaly_ids = load_news_anomaly_ids(session)
    total_inserted = 0
    for index, anomaly_id in enumerate(anomaly_ids, start=1):
        with SessionLocal.begin() as session:
            inserted = run_news_context_for_anomaly(session, anomaly_id)
        total_inserted += inserted
        print(f"news_context: anomaly {anomaly_id} stored {inserted} article row(s) [{index}/{len(anomaly_ids)}]")
    return total_inserted


def recompute_explanations(anomaly_ids: list[int] | None = None) -> int:
    if anomaly_ids is None:
        with SessionLocal() as session:
            anomaly_ids = load_explanation_anomaly_ids(session)
    total_inserted = 0
    for index, anomaly_id in enumerate(anomaly_ids, start=1):
        with SessionLocal.begin() as session:
            inserted = run_explanation_for_anomaly(session, anomaly_id)
        total_inserted += inserted
        print(f"explanations: anomaly {anomaly_id} stored {inserted} row(s) [{index}/{len(anomaly_ids)}]")
    return total_inserted


def measure_stage(timings: list[StageTiming], name: str, fn):  # noqa: ANN001
    started_at = perf_counter()
    result = fn()
    timings.append(StageTiming(name=name, seconds=perf_counter() - started_at))
    return result


def print_timing_summary(timings: list[StageTiming]) -> None:
    if not timings:
        return

    total_seconds = sum(item.seconds for item in timings)
    print("timing:")
    for item in timings:
        print(f"- {item.name}: {item.seconds:.2f}s")
    print(f"- total: {total_seconds:.2f}s")


def main() -> None:
    args = parse_args()
    timings: list[StageTiming] = []

    with SessionLocal() as session:
        datasets = measure_stage(
            timings,
            "load datasets",
            lambda: load_datasets(session, dataset_symbols=args.dataset_symbols),
        )
        selected_dataset_ids = build_dataset_ids(datasets)
        dataset_scoped_anomaly_ids = (
            resolve_news_context_target_anomaly_ids(session, selected_dataset_ids)
            if selected_dataset_ids
            else None
        )

    if args.dataset_symbols:
        scoped_symbols = ", ".join(str(item["symbol"]) for item in datasets)
        print(f"scope: datasets {scoped_symbols}")

    if not args.skip_anomaly_detection:
        total_anomalies = measure_stage(
            timings,
            "anomaly detection",
            lambda: recompute_anomalies(datasets),
        )
        print(f"anomalies: stored {total_anomalies} row(s) across all datasets")

    clustering_ran = False
    if not args.skip_clustering:
        clustering_result = measure_stage(
            timings,
            "clustering",
            lambda: _run_clustering(),
        )
        clustering_ran = True
        print(
            "clusters: stored "
            f"{clustering_result.cluster_count} cluster row(s) covering {clustering_result.member_count} anomaly membership row(s)"
        )

    if not args.skip_correlation:
        correlation_scope = datasets if args.dataset_symbols else None
        total_correlations = measure_stage(
            timings,
            "correlation rebuild",
            lambda: recompute_correlations(correlation_scope),
        )
        print(f"correlations: stored {total_correlations} relationship row(s)")
        if clustering_ran:
            clustering_result = measure_stage(
                timings,
                "cluster reconciliation",
                lambda: _run_clustering(),
            )
            print(
                "clusters: reconciled "
                f"{clustering_result.cluster_count} cluster row(s) covering {clustering_result.member_count} anomaly membership row(s)"
            )

    if not args.skip_news_context:
        if args.dataset_symbols:
            with SessionLocal() as session:
                dataset_scoped_anomaly_ids = resolve_news_context_target_anomaly_ids(session, selected_dataset_ids)
        total_news_articles = measure_stage(
            timings,
            "news-context refresh",
            lambda: recompute_news_context(dataset_scoped_anomaly_ids),
        )
        print(f"news_context: stored {total_news_articles} article row(s)")

    if not args.skip_explanations:
        explanation_scope: list[int] | None = None
        if args.dataset_symbols:
            with SessionLocal() as session:
                explanation_scope = resolve_explanation_target_anomaly_ids(
                    session,
                    selected_dataset_ids,
                    clustering_ran=clustering_ran,
                )
        total_explanations = measure_stage(
            timings,
            "explanation refresh",
            lambda: recompute_explanations(explanation_scope),
        )
        print(f"explanations: stored {total_explanations} explanation row(s)")

    print_timing_summary(timings)


def _run_clustering():
    with SessionLocal.begin() as session:
        return run_clustering_for_all_anomalies(session)


if __name__ == "__main__":
    main()
