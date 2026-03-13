import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.explanations import run_explanation_for_anomaly, run_explanations_for_all_anomalies


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate MacroLens explanations from stored anomaly evidence.")
    parser.add_argument(
        "--anomaly-id",
        type=int,
        default=None,
        help="Generate an explanation only for the specified anomaly id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal.begin() as session:
        if args.anomaly_id is not None:
            count = run_explanation_for_anomaly(session, args.anomaly_id)
            print(f"explanations: stored {count} explanation row for anomaly {args.anomaly_id}")
        else:
            count = run_explanations_for_all_anomalies(session)
            print(f"explanations: stored {count} explanation rows")


if __name__ == "__main__":
    main()
