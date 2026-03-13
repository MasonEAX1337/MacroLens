import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.anomaly_detection import run_detection_for_dataset
from app.services.correlation_engine import run_correlation_for_all_anomalies
from app.services.explanations import run_explanations_for_all_anomalies
from app.services.ingestion import create_ingestion_run, upsert_data_points, upsert_dataset
from app.services.news_context import run_news_context_for_all_anomalies
from app.services.providers.coingecko import BITCOIN_DATASET, CoinGeckoClient
from app.services.providers.fred import FRED_SERIES, FredClient


def ingest_bitcoin(detect_anomalies: bool) -> tuple[str, int, int]:
    client = CoinGeckoClient()
    points = client.fetch_bitcoin_market_chart()
    with SessionLocal.begin() as session:
        dataset_id = upsert_dataset(session, BITCOIN_DATASET)
        inserted = upsert_data_points(session, dataset_id, points, replace_existing=True)
        detected = run_detection_for_dataset(session, dataset_id) if detect_anomalies else 0
        create_ingestion_run(session, BITCOIN_DATASET.source, BITCOIN_DATASET.key, "success", f"Loaded {inserted} rows")
    return BITCOIN_DATASET.key, inserted, detected


def ingest_fred(dataset_key: str, detect_anomalies: bool) -> tuple[str, int, int]:
    if not settings.fred_api_key:
        raise RuntimeError("FRED_API_KEY is required for FRED ingestion.")
    dataset = FRED_SERIES[dataset_key]
    client = FredClient(api_key=settings.fred_api_key)
    points = client.fetch_series(dataset)
    with SessionLocal.begin() as session:
        dataset_id = upsert_dataset(session, dataset)
        inserted = upsert_data_points(session, dataset_id, points, replace_existing=True)
        detected = run_detection_for_dataset(session, dataset_id) if detect_anomalies else 0
        create_ingestion_run(session, dataset.source, dataset.key, "success", f"Loaded {inserted} rows")
    return dataset.key, inserted, detected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest MacroLens source datasets into PostgreSQL.")
    parser.add_argument(
        "--dataset",
        action="append",
        choices=["bitcoin", *sorted(FRED_SERIES.keys())],
        required=True,
        help="Dataset key to ingest. Repeat for multiple datasets.",
    )
    parser.add_argument(
        "--skip-anomaly-detection",
        action="store_true",
        help="Load raw data points without recomputing anomalies.",
    )
    parser.add_argument(
        "--skip-correlation",
        action="store_true",
        help="Load and detect anomalies without recomputing cross-dataset correlations.",
    )
    parser.add_argument(
        "--skip-news-context",
        action="store_true",
        help="Load data, detect anomalies, and compute correlations without fetching stored news context.",
    )
    parser.add_argument(
        "--skip-explanations",
        action="store_true",
        help="Load data, detect anomalies, compute correlations, and fetch news context without generating explanations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_correlation = not args.skip_correlation
    run_news_context = not args.skip_news_context
    run_explanations = not args.skip_explanations
    for dataset_key in args.dataset:
        try:
            if dataset_key == "bitcoin":
                key, inserted, detected = ingest_bitcoin(detect_anomalies=not args.skip_anomaly_detection)
            else:
                key, inserted, detected = ingest_fred(dataset_key, detect_anomalies=not args.skip_anomaly_detection)
            print(f"{key}: loaded {inserted} rows, detected {detected} anomalies")
        except Exception as exc:  # noqa: BLE001
            with SessionLocal.begin() as session:
                source = "CoinGecko" if dataset_key == "bitcoin" else "FRED"
                create_ingestion_run(session, source, dataset_key, "failed", str(exc))
            raise

    if run_correlation:
        with SessionLocal.begin() as session:
            total_correlations = run_correlation_for_all_anomalies(session)
        print(f"correlations: stored {total_correlations} relationship rows")

    if run_news_context:
        with SessionLocal.begin() as session:
            total_news_articles = run_news_context_for_all_anomalies(session)
        print(f"news_context: stored {total_news_articles} article row(s)")

    if run_explanations:
        with SessionLocal.begin() as session:
            total_explanations = run_explanations_for_all_anomalies(session)
        print(f"explanations: stored {total_explanations} explanation rows")


if __name__ == "__main__":
    main()
