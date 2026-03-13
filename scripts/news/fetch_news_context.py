import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.news_context import run_news_context_for_all_anomalies, run_news_context_for_anomaly


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and store MacroLens news context for anomalies.")
    parser.add_argument(
        "--anomaly-id",
        type=int,
        default=None,
        help="Fetch news context only for the specified anomaly id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal.begin() as session:
        if args.anomaly_id is not None:
            count = run_news_context_for_anomaly(session, args.anomaly_id)
            print(f"news_context: stored {count} article row(s) for anomaly {args.anomaly_id}")
        else:
            count = run_news_context_for_all_anomalies(session)
            print(f"news_context: stored {count} article row(s)")


if __name__ == "__main__":
    main()
