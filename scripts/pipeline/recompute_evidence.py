import argparse
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.anomaly_detection import run_detection_for_dataset
from app.services.clustering import run_clustering_for_all_anomalies
from app.services.correlation_engine import run_correlation_for_all_anomalies
from app.services.explanations import load_anomaly_ids as load_explanation_anomaly_ids
from app.services.explanations import run_explanation_for_anomaly
from app.services.news_context import load_anomaly_ids as load_news_anomaly_ids
from app.services.news_context import run_news_context_for_anomaly


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute MacroLens evidence from stored data points without re-ingesting source datasets."
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


def load_datasets() -> list[dict[str, object]]:
    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT id, name, symbol, frequency
                FROM datasets
                ORDER BY id ASC
                """
            )
        ).mappings().all()
    return [dict(row) for row in rows]


def recompute_anomalies() -> int:
    total_inserted = 0
    for dataset in load_datasets():
        with SessionLocal.begin() as session:
            inserted = run_detection_for_dataset(session, int(dataset["id"]))
        total_inserted += inserted
        print(
            f"anomalies: dataset {dataset['symbol']} ({dataset['frequency']}) stored {inserted} row(s)"
        )
    return total_inserted


def recompute_news_context() -> int:
    with SessionLocal() as session:
        anomaly_ids = load_news_anomaly_ids(session)

    total_inserted = 0
    for index, anomaly_id in enumerate(anomaly_ids, start=1):
        with SessionLocal.begin() as session:
            inserted = run_news_context_for_anomaly(session, anomaly_id)
        total_inserted += inserted
        print(f"news_context: anomaly {anomaly_id} stored {inserted} article row(s) [{index}/{len(anomaly_ids)}]")
    return total_inserted


def recompute_explanations() -> int:
    with SessionLocal() as session:
        anomaly_ids = load_explanation_anomaly_ids(session)

    total_inserted = 0
    for index, anomaly_id in enumerate(anomaly_ids, start=1):
        with SessionLocal.begin() as session:
            inserted = run_explanation_for_anomaly(session, anomaly_id)
        total_inserted += inserted
        print(f"explanations: anomaly {anomaly_id} stored {inserted} row(s) [{index}/{len(anomaly_ids)}]")
    return total_inserted


def main() -> None:
    args = parse_args()

    if not args.skip_anomaly_detection:
        total_anomalies = recompute_anomalies()
        print(f"anomalies: stored {total_anomalies} row(s) across all datasets")

    if not args.skip_clustering:
        with SessionLocal.begin() as session:
            clustering_result = run_clustering_for_all_anomalies(session)
        print(
            "clusters: stored "
            f"{clustering_result.cluster_count} cluster row(s) covering {clustering_result.member_count} anomaly membership row(s)"
        )

    if not args.skip_correlation:
        with SessionLocal.begin() as session:
            total_correlations = run_correlation_for_all_anomalies(session)
        print(f"correlations: stored {total_correlations} relationship row(s)")

    if not args.skip_news_context:
        total_news_articles = recompute_news_context()
        print(f"news_context: stored {total_news_articles} article row(s)")

    if not args.skip_explanations:
        total_explanations = recompute_explanations()
        print(f"explanations: stored {total_explanations} explanation row(s)")


if __name__ == "__main__":
    main()
